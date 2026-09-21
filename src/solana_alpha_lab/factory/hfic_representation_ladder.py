"""Bounded Forge representation ladder over existing HFIC sessions.

A3 remains the only input/visibility owner. This module selects the next
allowed action or owner-final from frozen registry + stage receipts. It does
not run Prompt A/B/C, Independent Critic, or the scientific V1 probe.
"""

from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.forge_input_receipt import (
    OWNER_CLASS_INPUT_NOT_READY,
    OWNER_CLASS_OBSERVABILITY_BLOCKED,
    build_forge_input_receipt,
)
from solana_alpha_lab.factory.hfic_control_integrity import (
    CASE_A_TERMINALS,
    CASE_C_KILL_TERMINALS,
    CURRENT_REPRESENTATION_CONTROL_V1,
    control_probe_permitted,
    effective_control_terminal,
    session_evidence_surface_mode,
)
from solana_alpha_lab.factory.hfic_preflight import (
    FORGE_CONTEXT_ARTIFACT_DIR,
    FORGE_CONTEXT_ARTIFACT_KIND,
)
from solana_alpha_lab.factory.hfic_representation_probe import (
    CONTROL_CONTEXT_KIND_FORGE,
    RepresentationProbeError,
    build_challenger_packet,
    control_baseline_from_receipt,
    existing_hfic_lifecycle_fixture_input,
    representation_status,
)
from solana_alpha_lab.factory.hfic_session import (
    RUNNER_UP_AWAITING_CRITIC,
    RUNNER_UP_REVISION_REQUIRED,
    focus_key_sha256,
    list_hfic_sessions,
    load_session_bundle,
    pick_session,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256

SCHEMA = "smial.forge-run-receipt"
SCHEMA_VERSION = "1.0"
LADDER_CONFIG_RELATIVE = "configs/hfic_representation_ladder_v1.yaml"
FORGE_RUN_ARTIFACT_KIND = "FORGE_RUN_RECEIPT"
EXISTING_V1_CONTROL_SESSION_ID = "HFIC-SESS-4F80F1151844EC1B"
LADDER_REPRESENTATION_PACKET_KEY = "ladder_representation_id"
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[3] / LADDER_CONFIG_RELATIVE
RECEIPT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "catalog/schemas/forge_run_receipt_v1.schema.json"
)

HANDLER_BASE_HFIC = "BASE_HFIC"
HANDLER_NORMALIZED_TRAJECTORY_V1 = "NORMALIZED_TRAJECTORY_V1"
HANDLER_SYNTHETIC_LATER_V2 = "SYNTHETIC_LATER_V2"
KNOWN_HANDLERS = frozenset(
    {
        HANDLER_BASE_HFIC,
        HANDLER_NORMALIZED_TRAJECTORY_V1,
        HANDLER_SYNTHETIC_LATER_V2,
    }
)

ACTION_INPUT_NOT_READY = "INPUT_NOT_READY"
ACTION_OBSERVABILITY_BLOCKED = "OBSERVABILITY_BLOCKED"
ACTION_START_BASE = "START_BASE"
ACTION_RESUME_BASE = "RESUME_BASE"
ACTION_OWNER_CANDIDATE = "OWNER_CANDIDATE"
ACTION_FINISH_RUNNER_UP = "FINISH_RUNNER_UP"
ACTION_KEEP_PAUSE = "KEEP_PAUSE"
ACTION_NON_SCIENTIFIC_STOP = "NON_SCIENTIFIC_STOP"
ACTION_START_V1 = "START_V1"
ACTION_RESUME_V1 = "RESUME_V1"
ACTION_SEARCH_EXHAUSTED = "SEARCH_EXHAUSTED_CURRENT_EVIDENCE"
ACTION_RETURN_EXISTING = "RETURN_EXISTING_RUN"
ACTION_CONTROL_REQUIRED = "CONTROL_REQUIRED"
ACTION_UNKNOWN_REPRESENTATION = "UNKNOWN_ACTIVE_REPRESENTATION"

OWNER_CLASS_IN_PROGRESS = "FORGE_RUN_IN_PROGRESS"
OWNER_CLASS_FINAL = "OWNER_FINAL"

EXEC_EXECUTED = "EXECUTED"
EXEC_REUSED = "REUSED_VALID"
EXEC_NOT_RUN = "NOT_RUN"
EXEC_BLOCKED = "BLOCKED"

PAUSE_STATES = frozenset(
    {
        RUNNER_UP_REVISION_REQUIRED,
        RUNNER_UP_AWAITING_CRITIC,
    }
)
RESUME_STATES = frozenset(
    {
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        "DRAFT_VALIDATED",
        "PREFLIGHT_PROVEN",
        "CRITIC_RESULT_READY",
        "REVISION_REQUIRED",
        "AWAITING_CLASSIFICATION",
    }
)
KNOWN_SCIENTIFIC_NEGATIVES = frozenset(
    {
        "NO_WORTHY_HYPOTHESIS",
        "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
        "KILL_MECHANISM",
    }
)
PASS_TERMINALS = frozenset(
    {
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
        "PASS_DATA_OPTION_REQUIRED",
    }
)
# Critic intermediate: session stays AWAITING_CLASSIFICATION until classify/finalize.
INTERMEDIATE_PASS_TERMINALS = frozenset({"PASS_TO_CLASSIFICATION"})

_RECEIPT_VALIDATOR: Draft202012Validator | None = None


class LadderError(ValueError):
    """Typed ladder failure; message is a stable reason code."""


def load_ladder_registry(path: Path | None = None) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path or DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LadderError("LADDER_REGISTRY_INVALID")
    rows = raw.get("representations")
    if not isinstance(rows, list) or not rows:
        raise LadderError("LADDER_REGISTRY_EMPTY")
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise LadderError("LADDER_REGISTRY_INVALID")
        rep_id = str(item.get("id") or "")
        handler = str(item.get("handler") or "")
        status = str(item.get("status") or "")
        if not rep_id or rep_id in seen:
            raise LadderError("LADDER_REGISTRY_DUPLICATE_OR_MISSING_ID")
        seen.add(rep_id)
        if status == "ACTIVE" and handler not in KNOWN_HANDLERS:
            raise LadderError("UNKNOWN_ACTIVE_REPRESENTATION")
        triggers = item.get("trigger_terminals") or []
        if not isinstance(triggers, list) or any(
            not isinstance(code, str) or not code for code in triggers
        ):
            raise LadderError("LADDER_REGISTRY_TRIGGER_INVALID")
        ordered.append(
            {
                "id": rep_id,
                "version": str(item.get("version") or ""),
                "order": int(item.get("order") or 0),
                "status": status,
                "reuse_class": str(item.get("reuse_class") or ""),
                "handler": handler,
                "trigger_terminals": [str(code) for code in triggers],
            }
        )
    ordered.sort(key=lambda row: (row["order"], row["id"]))
    return {
        "ladder_id": str(raw.get("ladder_id") or "HFIC_REPRESENTATION_LADDER_V1"),
        "legacy_epoch_binding": str(
            raw.get("legacy_epoch_binding") or "EXISTING_CONTROL_EVIDENCE_EPOCH_SHA256"
        ),
        "representations": ordered,
    }


def eligible_representation_ids(registry: Mapping[str, Any]) -> list[str]:
    return [
        str(row["id"])
        for row in registry.get("representations") or []
        if str(row.get("status") or "") == "ACTIVE"
    ]


def _validator() -> Draft202012Validator:
    global _RECEIPT_VALIDATOR
    if _RECEIPT_VALIDATOR is None:
        schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
        _RECEIPT_VALIDATOR = Draft202012Validator(schema)
    return _RECEIPT_VALIDATOR


def _start_action(representation_id: str) -> str:
    if representation_id == "NORMALIZED_TRAJECTORY_V1":
        return ACTION_START_V1
    return f"START_{representation_id}"


def _resume_action(representation_id: str) -> str:
    if representation_id == "NORMALIZED_TRAJECTORY_V1":
        return ACTION_RESUME_V1
    return f"RESUME_{representation_id}"


def _terminal_codes(representation_id: str) -> tuple[str, str, str]:
    if representation_id == "NORMALIZED_TRAJECTORY_V1":
        return ("V1_TERMINAL_MISSING", "V1_TERMINAL_UNMATCHED", "V1_STAGE_REF_MISSING")
    return ("STAGE_TERMINAL_MISSING", "STAGE_TERMINAL_UNMATCHED", "STAGE_REF_MISSING")


def _consume_representation_chain(
    *,
    registry: Mapping[str, Any],
    stage_map: Mapping[str, Mapping[str, Any]],
    start_id: str,
    saved_draft_sha256: str | None,
) -> dict[str, Any]:
    current_id = start_id
    while current_id:
        stage = stage_map.get(current_id)
        status = str((stage or {}).get("execution_status") or EXEC_NOT_RUN)
        if stage is None or status == EXEC_NOT_RUN:
            if saved_draft_sha256:
                return {
                    "next_action": _resume_action(current_id),
                    "owner_final": None,
                    "reason_code": "SAVED_DRAFT_PRESENT",
                    "draft_sha256": saved_draft_sha256,
                }
            start = _start_action(current_id)
            return {
                "next_action": start,
                "owner_final": None,
                "reason_code": start,
            }
        terminal = stage.get("effective_terminal")
        state = str(stage.get("session_state") or "")
        missing, unmatched, ref_missing = _terminal_codes(current_id)
        if status == EXEC_BLOCKED:
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": str(stage.get("reason_code") or ACTION_OBSERVABILITY_BLOCKED),
            }
        if state in RESUME_STATES or (
            isinstance(terminal, str) and terminal in INTERMEDIATE_PASS_TERMINALS
        ):
            return {
                "next_action": _resume_action(current_id),
                "owner_final": None,
                "reason_code": state
                if state in RESUME_STATES
                else str(terminal),
                "draft_sha256": saved_draft_sha256 or stage.get("draft_sha256"),
            }
        if isinstance(terminal, str) and (
            terminal in PASS_TERMINALS or terminal in CASE_A_TERMINALS
        ):
            return {
                "next_action": ACTION_OWNER_CANDIDATE,
                "owner_final": ACTION_OWNER_CANDIDATE,
                "reason_code": terminal,
            }
        if state in PAUSE_STATES:
            return {
                "next_action": ACTION_KEEP_PAUSE,
                "owner_final": None,
                "reason_code": state,
            }
        if isinstance(terminal, str) and terminal in CASE_C_KILL_TERMINALS:
            return {
                "next_action": ACTION_NON_SCIENTIFIC_STOP,
                "owner_final": ACTION_NON_SCIENTIFIC_STOP,
                "reason_code": terminal,
            }
        if status in {EXEC_EXECUTED, EXEC_REUSED} and not isinstance(terminal, str):
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": missing,
            }
        next_rep = _next_active_after(registry, current_id, str(terminal or ""))
        if next_rep is not None:
            current_id = next_rep
            continue
        if not isinstance(terminal, str) or terminal not in (
            KNOWN_SCIENTIFIC_NEGATIVES | CASE_C_KILL_TERMINALS | PASS_TERMINALS
        ):
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": unmatched,
            }
        stage_ref = stage.get("stage_ref_sha256")
        if not isinstance(stage_ref, str) or len(stage_ref) != 64:
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": ref_missing,
            }
        return {
            "next_action": ACTION_SEARCH_EXHAUSTED,
            "owner_final": ACTION_SEARCH_EXHAUSTED,
            "reason_code": terminal,
        }
    return {
        "next_action": ACTION_SEARCH_EXHAUSTED,
        "owner_final": ACTION_SEARCH_EXHAUSTED,
        "reason_code": "NO_ELIGIBLE_NEXT_REPRESENTATION",
    }


def resolve_next_action(
    stages: Sequence[Mapping[str, Any]],
    *,
    registry: Mapping[str, Any] | None = None,
    input_owner_class: str | None = None,
    existing_completed: bool = False,
    saved_draft_sha256: str | None = None,
) -> dict[str, Any]:
    """Pure transition: one next action or owner-final from stage receipts."""

    if existing_completed:
        return {
            "next_action": ACTION_RETURN_EXISTING,
            "owner_final": None,
            "reason_code": "RUN_ALREADY_COMPLETED",
        }
    if input_owner_class == OWNER_CLASS_INPUT_NOT_READY:
        return {
            "next_action": ACTION_INPUT_NOT_READY,
            "owner_final": ACTION_INPUT_NOT_READY,
            "reason_code": ACTION_INPUT_NOT_READY,
        }
    if input_owner_class == OWNER_CLASS_OBSERVABILITY_BLOCKED:
        return {
            "next_action": ACTION_OBSERVABILITY_BLOCKED,
            "owner_final": ACTION_OBSERVABILITY_BLOCKED,
            "reason_code": ACTION_OBSERVABILITY_BLOCKED,
        }

    active = load_ladder_registry() if registry is None else dict(registry)
    by_id = {str(row["id"]): row for row in active["representations"]}
    stage_map = {str(row.get("representation_id")): dict(row) for row in stages}

    base = stage_map.get("BASE") or {
        "representation_id": "BASE",
        "execution_status": EXEC_NOT_RUN,
        "effective_terminal": None,
        "session_state": None,
    }
    base_status = str(base.get("execution_status") or EXEC_NOT_RUN)
    base_terminal = base.get("effective_terminal")
    base_state = str(base.get("session_state") or "")

    if base_status == EXEC_NOT_RUN:
        stage_reason = str(base.get("reason_code") or "")
        if stage_reason in {"CONTROL_SURFACE_REQUIRED", ACTION_CONTROL_REQUIRED}:
            # Discovery found ordinary/incomplete BASE but no CONTROL-compatible
            # session — agent must start CONTROL surface, not bare ordinary Prompt A.
            return {
                "next_action": ACTION_START_BASE,
                "owner_final": None,
                "reason_code": "CONTROL_SURFACE_REQUIRED",
                "base_evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            }
        return {
            "next_action": ACTION_START_BASE,
            "owner_final": None,
            "reason_code": ACTION_START_BASE,
        }
    if base_status == EXEC_BLOCKED:
        return {
            "next_action": ACTION_OBSERVABILITY_BLOCKED,
            "owner_final": ACTION_OBSERVABILITY_BLOCKED,
            "reason_code": str(base.get("reason_code") or ACTION_OBSERVABILITY_BLOCKED),
        }
    if (
        base.get("runner_up_candidate_id")
        and base_state == RUNNER_UP_AWAITING_CRITIC
    ) or (
        base_state in PAUSE_STATES or base_terminal == RUNNER_UP_REVISION_REQUIRED
    ):
        action = (
            ACTION_FINISH_RUNNER_UP
            if base_state == RUNNER_UP_AWAITING_CRITIC
            else ACTION_KEEP_PAUSE
        )
        return {
            "next_action": action,
            "owner_final": None,
            "reason_code": base_state or str(base_terminal),
        }
    if base_state in RESUME_STATES or (
        isinstance(base_terminal, str) and base_terminal in INTERMEDIATE_PASS_TERMINALS
    ):
        return {
            "next_action": ACTION_RESUME_BASE,
            "owner_final": None,
            "reason_code": base_state
            if base_state in RESUME_STATES
            else str(base_terminal),
            "draft_sha256": saved_draft_sha256 or base.get("draft_sha256"),
        }
    if isinstance(base_terminal, str) and (
        base_terminal in PASS_TERMINALS or base_terminal in CASE_A_TERMINALS
    ):
        return {
            "next_action": ACTION_OWNER_CANDIDATE,
            "owner_final": ACTION_OWNER_CANDIDATE,
            "reason_code": base_terminal,
        }
    if isinstance(base_terminal, str) and (
        base_terminal in CASE_C_KILL_TERMINALS or base_terminal == "KILL_UNBOUND_EVIDENCE"
    ):
        return {
            "next_action": ACTION_NON_SCIENTIFIC_STOP,
            "owner_final": ACTION_NON_SCIENTIFIC_STOP,
            "reason_code": base_terminal,
        }

    v1_row = by_id.get("NORMALIZED_TRAJECTORY_V1")
    if (
        v1_row
        and v1_row["status"] == "ACTIVE"
        and isinstance(base_terminal, str)
        and base_terminal in set(v1_row["trigger_terminals"])
        and control_probe_permitted(base_terminal)
    ):
        if str(base.get("evidence_surface_mode") or "") != CURRENT_REPRESENTATION_CONTROL_V1:
            # V1 needs CONTROL-compatible BASE inside the same slash — not evening DONE.
            return {
                "next_action": ACTION_START_BASE,
                "owner_final": None,
                "reason_code": "CONTROL_SURFACE_REQUIRED",
                "base_evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            }
        return _consume_representation_chain(
            registry=active,
            stage_map=stage_map,
            start_id="NORMALIZED_TRAJECTORY_V1",
            saved_draft_sha256=saved_draft_sha256,
        )

    if not isinstance(base_terminal, str):
        return {
            "next_action": ACTION_OBSERVABILITY_BLOCKED,
            "owner_final": ACTION_OBSERVABILITY_BLOCKED,
            "reason_code": "BASE_TERMINAL_MISSING",
        }
    known_base = (
        KNOWN_SCIENTIFIC_NEGATIVES
        | CASE_C_KILL_TERMINALS
        | PASS_TERMINALS
        | CASE_A_TERMINALS
        | {RUNNER_UP_REVISION_REQUIRED, "KILL_UNBOUND_EVIDENCE"}
    )
    if base_terminal not in known_base:
        return {
            "next_action": ACTION_OBSERVABILITY_BLOCKED,
            "owner_final": ACTION_OBSERVABILITY_BLOCKED,
            "reason_code": "BASE_TERMINAL_UNMATCHED",
        }
    if not control_probe_permitted(base_terminal):
        action = (
            ACTION_NON_SCIENTIFIC_STOP
            if base_terminal in CASE_C_KILL_TERMINALS
            else ACTION_SEARCH_EXHAUSTED
        )
        return {
            "next_action": action,
            "owner_final": action,
            "reason_code": base_terminal,
        }
    return {
        "next_action": ACTION_SEARCH_EXHAUSTED,
        "owner_final": ACTION_SEARCH_EXHAUSTED,
        "reason_code": "NO_ELIGIBLE_NEXT_REPRESENTATION",
    }


def consume_start_v1_envelope(
    receipt: Mapping[str, Any],
    *,
    control_receipt: Mapping[str, Any],
    representation: Mapping[str, Any],
    cohort_readiness_receipt: Mapping[str, Any] | None = None,
    base_x_population_n: int | None = None,
) -> dict[str, Any]:
    """Fixture-plane V1 envelope from a START_V1 routing receipt.

    Builds the challenger packet and existing HFIC lifecycle seam. Does not
    run Prompt A or the scientific V1 probe.
    """

    if receipt.get("next_action") != ACTION_START_V1:
        raise LadderError("START_V1_REQUIRED")
    if receipt.get("owner_final") is not None:
        raise LadderError("START_V1_OWNER_FINAL_FORBIDDEN")
    baseline = control_baseline_from_receipt(control_receipt)
    challenger = build_challenger_packet(
        baseline,
        representation,
        cohort_readiness_receipt=cohort_readiness_receipt,
        base_x_population_n=base_x_population_n,
    )
    # Orchestration marker stays outside the frozen challenger bytes/schema.
    if baseline.context_kind == CONTROL_CONTEXT_KIND_FORGE:
        return {
            "next_action": ACTION_START_V1,
            "control_context_kind": CONTROL_CONTEXT_KIND_FORGE,
            "challenger": challenger,
            LADDER_REPRESENTATION_PACKET_KEY: HANDLER_NORMALIZED_TRAJECTORY_V1,
            "lifecycle": None,
            "critic_input_packet": None,
            "control_session_id": challenger.get("control_session_id"),
            "representation_search_key_sha256": challenger.get(
                "representation_search_key_sha256"
            ),
            "probe_executed": False,
            "fake_critic_packet": False,
        }
    lifecycle = existing_hfic_lifecycle_fixture_input(
        challenger,
        control_receipt=control_receipt,
        cohort_readiness_receipt=cohort_readiness_receipt,
        base_x_population_n=base_x_population_n,
    )
    packet = lifecycle.get("critic_input_packet")
    return {
        "next_action": ACTION_START_V1,
        "control_context_kind": baseline.context_kind,
        LADDER_REPRESENTATION_PACKET_KEY: HANDLER_NORMALIZED_TRAJECTORY_V1,
        "lifecycle": lifecycle,
        "challenger": challenger,
        "critic_input_packet": packet,
        "control_session_id": lifecycle.get("control_session_id"),
        "representation_search_key_sha256": challenger.get(
            "representation_search_key_sha256"
        ),
        "probe_executed": False,
    }


def prepare_ladder_freeze_preflight(
    control_preflight: Mapping[str, Any],
    *,
    representation_id: str,
    control_session_id: str,
    challenger: Mapping[str, Any] | None = None,
    control_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Copy CONTROL preflight into a freeze receipt that cannot collide with BASE.

    For NORMALIZED_TRAJECTORY_V1, ``challenger`` and ``control_receipt`` are
    required: marker/parent alone do not prove representation input. Embed
    verified payload hashes from the envelope so freeze/Critic bind the same
    challenger. Scientific bind checks always run against the exact CONTROL.
    """

    if representation_id not in {HANDLER_NORMALIZED_TRAJECTORY_V1, HANDLER_SYNTHETIC_LATER_V2}:
        raise LadderError("LADDER_FREEZE_PREFLIGHT_REPRESENTATION_INVALID")
    if not isinstance(control_session_id, str) or not control_session_id:
        raise LadderError("LADDER_FREEZE_PREFLIGHT_CONTROL_REQUIRED")
    receipt = dict(control_preflight)
    packet = dict(receipt.get("forge_context_packet") or {})
    packet[LADDER_REPRESENTATION_PACKET_KEY] = representation_id
    packet["control_session_id"] = control_session_id
    packet.pop("evidence_surface_mode", None)
    packet.pop("visible_cohort_ids", None)
    # Do not inherit BASE CONTROL used scope; V1 release-local comes from
    # verified representation corpus_binding after challenger revalidation.
    packet.pop("bound_visible_cohort_ids", None)
    if representation_id == HANDLER_NORMALIZED_TRAJECTORY_V1:
        if not isinstance(challenger, Mapping) or not challenger:
            raise LadderError("LADDER_FREEZE_CHALLENGER_REQUIRED")
        if not isinstance(control_receipt, Mapping) or not control_receipt:
            raise LadderError("LADDER_FREEZE_CONTROL_RECEIPT_REQUIRED")
        _embed_challenger_into_ladder_packet(
            packet,
            challenger,
            control_session_id,
            control_receipt=control_receipt,
        )
        receipt["ladder_challenger_packet"] = dict(challenger)
        receipt["ladder_control_receipt"] = dict(control_receipt)
        search = packet.get("representation_search_key_sha256")
        if not isinstance(search, str) or len(search) != 64:
            raise LadderError("LADDER_FREEZE_CHALLENGER_SEARCH_KEY_MISSING")
        receipt["search_key_sha256"] = search
    else:
        base_key = str(receipt.get("search_key_sha256") or "")
        receipt["search_key_sha256"] = hashlib.sha256(
            f"{base_key}:{representation_id}:{control_session_id}".encode("utf-8")
        ).hexdigest()
    receipt["forge_context_packet"] = packet
    receipt["control_session_id"] = control_session_id
    receipt[LADDER_REPRESENTATION_PACKET_KEY] = representation_id
    receipt.pop("evidence_surface_mode", None)
    receipt.pop("forge_context_packet_sha256", None)
    return receipt


def _embed_challenger_into_ladder_packet(
    packet: dict[str, Any],
    challenger: Mapping[str, Any],
    control_session_id: str,
    *,
    control_receipt: Mapping[str, Any] | None = None,
) -> None:
    """Stamp verified V1 representation fields onto the freeze packet.

    Reuses scientific challenger validators: hashes must match payload bytes and,
    when ``control_receipt`` is provided, the challenger must remain bound to that
    exact CONTROL. Release-local used scope comes from verified
    ``corpus_binding.cohort_id``, not BASE lists.
    """

    from solana_alpha_lab.factory.hfic_representation_probe import (
        RepresentationProbeError,
        _assert_challenger_bound_to_control,
        _validate_challenger_packet,
        control_baseline_from_receipt,
    )

    try:
        validated, representation = _validate_challenger_packet(challenger)
    except RepresentationProbeError as exc:
        raise LadderError(f"LADDER_FREEZE_CHALLENGER_INVALID:{exc}") from exc
    parent = validated.get("control_session_id")
    if parent != control_session_id:
        raise LadderError("LADDER_FREEZE_CHALLENGER_PARENT_MISMATCH")
    if control_receipt is None:
        raise LadderError("LADDER_FREEZE_CONTROL_RECEIPT_REQUIRED")
    try:
        baseline = control_baseline_from_receipt(control_receipt)
        _assert_challenger_bound_to_control(validated, baseline)
    except RepresentationProbeError as exc:
        raise LadderError(f"LADDER_FREEZE_CHALLENGER_CONTROL_UNBOUND:{exc}") from exc
    if baseline.session_id != control_session_id:
        raise LadderError("LADDER_FREEZE_CHALLENGER_PARENT_MISMATCH")

    payload = validated.get("normalized_trajectory_v1")
    payload_sha = validated.get("representation_payload_sha256")
    search_key = validated.get("representation_search_key_sha256")
    if not isinstance(payload, Mapping) or not payload:
        raise LadderError("LADDER_FREEZE_CHALLENGER_PAYLOAD_MISSING")
    if not isinstance(payload_sha, str) or len(payload_sha) != 64:
        raise LadderError("LADDER_FREEZE_CHALLENGER_PAYLOAD_HASH_MISSING")
    if not isinstance(search_key, str) or len(search_key) != 64:
        raise LadderError("LADDER_FREEZE_CHALLENGER_SEARCH_KEY_MISSING")
    packet["normalized_trajectory_v1"] = dict(payload)
    packet["representation_payload_sha256"] = payload_sha
    packet["representation_search_key_sha256"] = search_key
    probe_id = validated.get("probe_identity_sha256")
    if isinstance(probe_id, str) and len(probe_id) == 64:
        packet["probe_identity_sha256"] = probe_id
    control_packet_sha = validated.get("control_packet_sha256")
    if isinstance(control_packet_sha, str) and len(control_packet_sha) == 64:
        packet["control_packet_sha256"] = control_packet_sha
    corpus = representation.get("corpus_binding")
    cohort_id = None
    if isinstance(corpus, Mapping):
        raw = corpus.get("cohort_id")
        if isinstance(raw, str) and raw.strip():
            cohort_id = raw.strip()
    if cohort_id is None:
        raise LadderError("LADDER_FREEZE_CHALLENGER_COHORT_MISSING")
    packet["bound_visible_cohort_ids"] = [cohort_id]


def stamp_verified_v1_fields_onto_mapping(
    target: dict[str, Any], source: Mapping[str, Any]
) -> None:
    """Copy verified compact V1 fields onto Critic/forge mappings (shared keys)."""

    payload = source.get("normalized_trajectory_v1")
    if isinstance(payload, Mapping) and payload:
        target["normalized_trajectory_v1"] = dict(payload)
    for key in (
        "representation_payload_sha256",
        "representation_search_key_sha256",
        "probe_identity_sha256",
    ):
        value = source.get(key)
        if isinstance(value, str) and len(value) == 64:
            target[key] = value
    if source.get(LADDER_REPRESENTATION_PACKET_KEY) == HANDLER_NORMALIZED_TRAJECTORY_V1 or (
        isinstance(payload, Mapping) and payload
    ):
        target[LADDER_REPRESENTATION_PACKET_KEY] = HANDLER_NORMALIZED_TRAJECTORY_V1


def attach_ladder_freeze_preflight(
    payload: dict[str, Any],
    *,
    data_root: Path,
    store: ResearchStore,
) -> dict[str, Any]:
    """Attach freeze receipt for START_V1/RESUME_V1/later ACTIVE, or block."""

    next_action = str(payload.get("next_action") or "")
    control_sid = payload.get("control_session_id")
    if next_action not in {
        ACTION_START_V1,
        ACTION_RESUME_V1,
        "START_SYNTHETIC_LATER_V2",
    } or not isinstance(control_sid, str) or not control_sid:
        return payload
    bundle = load_session_bundle(store, control_sid)
    packet = _packet_for_bundle(Path(data_root), bundle, store) if bundle is not None else None
    if isinstance(packet, dict) and packet:
        representation_id = (
            HANDLER_SYNTHETIC_LATER_V2
            if "SYNTHETIC_LATER_V2" in next_action
            else HANDLER_NORMALIZED_TRAJECTORY_V1
        )
        challenger = payload.get("ladder_challenger") or payload.get("challenger")
        if not isinstance(challenger, Mapping):
            challenger = None
        try:
            payload["ladder_freeze_preflight"] = prepare_ladder_freeze_preflight(
                control_preflight_from_bundle(bundle, packet),
                representation_id=representation_id,
                control_session_id=control_sid,
                challenger=challenger,
                control_receipt=control_receipt_from_bundle(
                    Path(data_root), bundle, store=store
                ),
            )
        except LadderError as exc:
            code = str(exc)
            if representation_id == HANDLER_NORMALIZED_TRAJECTORY_V1:
                # Soft-pend only when the envelope is not supplied yet.
                if challenger is None and code in {
                    "LADDER_FREEZE_CHALLENGER_REQUIRED",
                    "LADDER_FREEZE_CONTROL_RECEIPT_REQUIRED",
                }:
                    payload.pop("ladder_freeze_preflight", None)
                    payload["ladder_freeze_pending_reason"] = code
                    payload.pop("owner_readout", None)
                    payload.pop("receipt_sha256", None)
                    payload["receipt_sha256"] = canonical_sha256(
                        {
                            key: value
                            for key, value in payload.items()
                            if key != "owner_readout"
                        }
                    )
                    payload["owner_readout"] = format_forge_run_owner_readout(payload)
                    return payload
                # Present challenger that fails scientific bind/validation is
                # integrity/observability, not "continue envelope construction".
                if challenger is not None and (
                    code
                    in {
                        "LADDER_FREEZE_CHALLENGER_PAYLOAD_MISSING",
                        "LADDER_FREEZE_CHALLENGER_PAYLOAD_HASH_MISSING",
                        "LADDER_FREEZE_CHALLENGER_SEARCH_KEY_MISSING",
                        "LADDER_FREEZE_CHALLENGER_PARENT_MISMATCH",
                        "LADDER_FREEZE_CHALLENGER_COHORT_MISSING",
                        "LADDER_FREEZE_CONTROL_RECEIPT_REQUIRED",
                    }
                    or code.startswith("LADDER_FREEZE_CHALLENGER_INVALID:")
                    or code.startswith("LADDER_FREEZE_CHALLENGER_CONTROL_UNBOUND:")
                ):
                    payload.pop("ladder_freeze_preflight", None)
                    payload["next_action"] = ACTION_OBSERVABILITY_BLOCKED
                    payload["owner_final"] = ACTION_OBSERVABILITY_BLOCKED
                    payload["owner_class"] = ACTION_OBSERVABILITY_BLOCKED
                    payload["blocking_reason_codes"] = [code]
                    payload["ladder_freeze_pending_reason"] = code
                    payload.pop("owner_readout", None)
                    payload.pop("receipt_sha256", None)
                    payload["receipt_sha256"] = canonical_sha256(
                        {
                            key: value
                            for key, value in payload.items()
                            if key != "owner_readout"
                        }
                    )
                    payload["owner_readout"] = format_forge_run_owner_readout(payload)
                    return payload
            raise
        return payload
    payload["next_action"] = ACTION_OBSERVABILITY_BLOCKED
    payload["owner_final"] = ACTION_OBSERVABILITY_BLOCKED
    payload["owner_class"] = ACTION_OBSERVABILITY_BLOCKED
    payload["blocking_reason_codes"] = ["FORGE_CONTEXT_ARTIFACT_MISSING"]
    payload.pop("ladder_freeze_preflight", None)
    payload.pop("owner_readout", None)
    payload.pop("receipt_sha256", None)
    payload["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "owner_readout"}
    )
    payload["owner_readout"] = format_forge_run_owner_readout(payload)
    return payload


def control_preflight_from_bundle(
    bundle: Mapping[str, Any], packet: Mapping[str, Any] | None
) -> dict[str, Any]:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    return {
        "evidence_epoch_sha256": bundle.get("evidence_epoch_sha256") or receipt.get("evidence_epoch_sha256"),
        "focus_key_sha256": bundle.get("focus_key_sha256") or receipt.get("focus_key_sha256"),
        "search_key_sha256": bundle.get("search_key_sha256") or receipt.get("search_key_sha256"),
        "owner_focus": bundle.get("owner_focus") or receipt.get("owner_focus") or "AUTO",
        "live_git_head": bundle.get("live_git_head") or receipt.get("live_git_head"),
        "git_composite_sha256": bundle.get("git_composite_sha256") or receipt.get("git_composite_sha256"),
        "session_started_at": bundle.get("session_started_at") or receipt.get("session_started_at"),
        "evidence_surface_mode": (
            session_evidence_surface_mode(receipt)
            or session_evidence_surface_mode(bundle)
            or (session_evidence_surface_mode(packet) if packet else None)
        ),
        "forge_context_packet": dict(packet) if isinstance(packet, Mapping) else {},
        "forge_context_packet_sha256": bundle.get("forge_context_packet_sha256")
        or receipt.get("forge_context_packet_sha256"),
        "memory_eligibility_sha256": bundle.get("memory_eligibility_sha256")
        or receipt.get("memory_eligibility_sha256"),
    }


def _next_active_after(
    registry: Mapping[str, Any], current_id: str, terminal: str
) -> str | None:
    rows = list(registry.get("representations") or [])
    passed = False
    for row in rows:
        if str(row.get("id")) == current_id:
            passed = True
            continue
        if not passed:
            continue
        if str(row.get("status") or "") != "ACTIVE":
            continue
        triggers = set(row.get("trigger_terminals") or [])
        if terminal in triggers and str(row.get("handler") or "") in KNOWN_HANDLERS:
            return str(row["id"])
        if str(row.get("handler") or "") not in KNOWN_HANDLERS:
            raise LadderError("UNKNOWN_ACTIVE_REPRESENTATION")
    return None


def format_forge_run_owner_readout(receipt: Mapping[str, Any]) -> str:
    stages = receipt.get("stages") or []
    writes = receipt.get("writes") if isinstance(receipt.get("writes"), Mapping) else {}
    persist_note = (
        "RESEARCH_ARTIFACT FORGE_RUN_RECEIPT"
        if int(writes.get("forge_run") or 0) > 0
        else "NONE"
    )
    persisted_sha = receipt.get("persisted_receipt_sha256") or receipt.get("receipt_sha256")
    next_action = receipt.get("next_action")
    owner_class = str(receipt.get("owner_class") or "")
    owner_final = receipt.get("owner_final")
    if owner_class in {ACTION_INPUT_NOT_READY, ACTION_OBSERVABILITY_BLOCKED} or next_action in {
        ACTION_INPUT_NOT_READY,
        ACTION_OBSERVABILITY_BLOCKED,
    }:
        status = "BLOCKED — stop; not a scientific negative"
    elif next_action == ACTION_RETURN_EXISTING or receipt.get("persisted_receipt_sha256"):
        status = "READBACK — same run; do not start a second trial"
    elif next_action == ACTION_KEEP_PAUSE:
        status = "NEXT — typed pause; evening not success"
    elif next_action == ACTION_CONTROL_REQUIRED:
        status = (
            "NEXT — CONTROL-compatible BASE required for V1; "
            "not evening DONE; use CONTROL surface inside this slash"
        )
    elif next_action == ACTION_START_BASE and "CONTROL_SURFACE_REQUIRED" in {
        str(item) for item in (receipt.get("blocking_reason_codes") or [])
    }:
        status = (
            "NEXT — start CONTROL-compatible BASE for V1 ladder; "
            "not ordinary evening DONE"
        )
    elif owner_final:
        status = "DONE — bounded-run owner-final; do not continue"
    elif next_action == ACTION_START_V1:
        status = "NEXT — continue V1 envelope; do not treat WAIT as done"
    elif next_action in {ACTION_START_BASE, ACTION_RESUME_BASE, ACTION_RESUME_V1}:
        reasons = {str(item) for item in (receipt.get("blocking_reason_codes") or [])}
        stage_reasons = {
            str(stage.get("reason_code") or "")
            for stage in (receipt.get("stages") or [])
            if isinstance(stage, Mapping)
        }
        if reasons & {"AWAITING_CLASSIFICATION", "PASS_TO_CLASSIFICATION"} or stage_reasons & {
            "AWAITING_CLASSIFICATION",
            "PASS_TO_CLASSIFICATION",
        }:
            status = (
                "NEXT — classify then finalize; PASS_TO_CLASSIFICATION is not owner-final"
            )
        else:
            status = "NEXT — resume or start the named stage from saved artifacts"
    elif next_action == ACTION_FINISH_RUNNER_UP:
        status = "NEXT — finish already frozen runner-up; do not start V1"
    else:
        status = "IN_PROGRESS — follow next_action; evening not complete"
    next_note = ""
    if next_action == ACTION_START_V1:
        next_note = "  # V1 eligible; not WAIT; not exhaustion"
    elif next_action == ACTION_RETURN_EXISTING:
        next_note = "  # readback; no second trial"
    lines = [
        "FORGE RUN",
        f"status: {status}",
        f"run_id: {receipt.get('run_id')}",
        f"owner_class: {receipt.get('owner_class') or 'NONE'}",
        f"visible_cohorts: {', '.join(receipt.get('visible_cohort_ids') or []) or 'NONE'}",
        f"used_cohorts: {', '.join(receipt.get('used_cohort_ids') or []) or 'NONE'}",
        f"legacy_epoch: {(receipt.get('legacy_epoch_sha256') or 'NONE')[:16]}",
    ]
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        used = ", ".join(stage.get("used_cohort_ids") or []) or "NONE"
        draft = stage.get("draft_sha256")
        draft_note = f" draft={(draft[:16] if isinstance(draft, str) else 'NONE')}"
        lines.append(
            "stage {id}: {status} terminal={term} scope={scope} used={used}{draft}".format(
                id=stage.get("representation_id"),
                status=stage.get("execution_status"),
                term=stage.get("effective_terminal") or "NONE",
                scope=stage.get("input_scope"),
                used=used,
                draft=draft_note,
            )
        )
        selected = stage.get("selected_candidate_id")
        mechanism = stage.get("candidate_mechanism")
        declined = stage.get("declined_candidate_ids") or []
        identity = stage.get("critic_identity")
        critic_term = stage.get("critic_terminal")
        critic_reason = stage.get("critic_decisive_reason")
        if selected or mechanism:
            lines.append(
                "  candidate: {cid} mechanism={mech}".format(
                    cid=selected or "NONE",
                    mech=(mechanism[:80] if isinstance(mechanism, str) else "NONE"),
                )
            )
        if declined:
            lines.append("  declined: " + ", ".join(str(item) for item in declined))
        elif selected:
            lines.append("  declined: NONE")
        if selected:
            if not identity and not critic_term:
                lines.append("  critic: UNKNOWN")
            else:
                lines.append(
                    "  critic: {who} terminal={term} reason={reason}".format(
                        who=identity or "UNKNOWN",
                        term=critic_term or "UNKNOWN",
                        reason=(
                            critic_reason[:120]
                            if isinstance(critic_reason, str) and critic_reason
                            else (critic_term or "UNKNOWN")
                        ),
                    )
                )
        else:
            lines.append("  critic: NOT_RUN_NO_SELECTED_CANDIDATE")
    lines.append(f"next_action: {next_action}{next_note}")
    lines.append(f"owner_final: {receipt.get('owner_final') or 'NONE'}")
    blocking = [str(item) for item in (receipt.get("blocking_reason_codes") or []) if item]
    lines.append(f"blocked_by: {', '.join(blocking) if blocking else 'NONE'}")
    lines.append(
        "writes: store={store} forge_run={forge} session={session}".format(
            store=int(writes.get("research_store") or 0),
            forge=int(writes.get("forge_run") or 0),
            session=int(writes.get("session") or 0),
        )
    )
    lines.append(f"persisted: {persist_note}")
    if isinstance(persisted_sha, str) and persisted_sha:
        lines.append(f"persisted_receipt: {persisted_sha[:16]}")
    pending = receipt.get("ladder_freeze_pending_reason")
    if isinstance(pending, str) and pending.strip():
        # Soft-pend keeps START_V1; integrity stop must not reuse "pending".
        if next_action == ACTION_OBSERVABILITY_BLOCKED or owner_final == ACTION_OBSERVABILITY_BLOCKED:
            lines.append(f"freeze_block: {pending.strip()}")
        else:
            lines.append(f"freeze_pending: {pending.strip()}")
    lines.append(
        "non_claim: scoped search result on completed representations; "
        "not alpha and not proof of generator recall"
    )
    return "\n".join(lines)


def _stage_ref_sha256(bundle: Mapping[str, Any]) -> str | None:
    for key in (
        "session_receipt_sha256",
        "critic_result_sha256",
        "critic_input_packet_sha256",
        "forge_context_packet_sha256",
    ):
        value = bundle.get(key)
        if isinstance(value, str) and len(value) == 64:
            return value
    receipt = bundle.get("session_receipt")
    if isinstance(receipt, Mapping):
        return canonical_sha256(receipt)
    packet = bundle.get("critic_input_packet")
    if isinstance(packet, Mapping):
        return canonical_sha256(packet)
    return None


def _stage_from_session(
    bundle: Mapping[str, Any],
    *,
    representation_id: str,
    used_cohort_ids: Sequence[str] | None = None,
    packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    terminal = effective_control_terminal(receipt) or effective_control_terminal(bundle)
    mode = session_evidence_surface_mode(receipt) or session_evidence_surface_mode(bundle)
    state = str(bundle.get("session_state") or "")
    bound = list(used_cohort_ids or [])
    if not bound:
        bound = _bound_cohort_ids(bundle, packet)
    applicable = bool(bound)
    status = EXEC_REUSED if state == "SYNTHESIS_COMPLETE" and applicable else EXEC_EXECUTED
    if state in PAUSE_STATES or state in RESUME_STATES:
        status = EXEC_EXECUTED
    stage_ref = _stage_ref_sha256(bundle)
    draft = bundle.get("draft_sha256") or receipt.get("draft_sha256")
    critic_terminal = bundle.get("critic_terminal") or receipt.get("critic_terminal")
    if not isinstance(critic_terminal, str):
        critic_terminal = terminal if isinstance(terminal, str) else None
    selected = bundle.get("selected_candidate_id") or receipt.get("selected_candidate_id")
    mechanism = _candidate_mechanism(bundle)
    identity = _critic_identity(bundle)
    declined = _declined_candidate_ids(bundle, selected if isinstance(selected, str) else None)
    decisive = _critic_decisive_reason(bundle) or critic_terminal
    input_scope = (
        CURRENT_REPRESENTATION_CONTROL_V1
        if representation_id == "BASE" and mode == CURRENT_REPRESENTATION_CONTROL_V1
        else ("REPRESENTATION_RELEASE_LOCAL" if representation_id != "BASE" else "ORDINARY_BASE")
    )
    return {
        "representation_id": representation_id,
        "execution_status": status,
        "effective_terminal": terminal or None,
        "input_scope": input_scope,
        "session_id": bundle.get("session_id"),
        "session_state": state,
        "evidence_surface_mode": mode,
        "selected_candidate_id": selected,
        "runner_up_candidate_id": bundle.get("runner_up_candidate_id"),
        "stage_ref_sha256": stage_ref,
        "used_cohort_ids": bound,
        "draft_sha256": draft if isinstance(draft, str) else None,
        "reason_code": None,
        "critic_terminal": critic_terminal if isinstance(critic_terminal, str) else None,
        "critic_decisive_reason": decisive if isinstance(decisive, str) else None,
        "critic_identity": identity,
        "declined_candidate_ids": declined,
        "candidate_mechanism": mechanism,
    }


def _candidate_mechanism(bundle: Mapping[str, Any]) -> str | None:
    packet = bundle.get("critic_input_packet")
    if not isinstance(packet, Mapping):
        return None
    selected = packet.get("selected_candidate")
    if not isinstance(selected, Mapping):
        return None
    for key in ("mechanism", "claim", "primary_x_family"):
        value = selected.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _critic_identity(bundle: Mapping[str, Any]) -> str | None:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    critic_result = bundle.get("critic_result") if isinstance(bundle.get("critic_result"), Mapping) else {}
    for source in (critic_result, receipt, bundle):
        if not isinstance(source, Mapping):
            continue
        for key in ("critic_prompt_version", "critic_id"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _critic_decisive_reason(bundle: Mapping[str, Any]) -> str | None:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    critic_result = bundle.get("critic_result") if isinstance(bundle.get("critic_result"), Mapping) else {}
    for source in (critic_result, receipt, bundle):
        if not isinstance(source, Mapping):
            continue
        for key in ("decisive_reason", "critic_decisive_reason"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _declined_candidate_ids(
    bundle: Mapping[str, Any], selected: str | None
) -> list[str]:
    packet = bundle.get("critic_input_packet")
    if not isinstance(packet, Mapping):
        return []
    declined: list[str] = []
    for card in packet.get("candidates") or []:
        if not isinstance(card, Mapping):
            continue
        cid = card.get("candidate_id")
        if isinstance(cid, str) and cid and cid != selected:
            declined.append(cid)
    return declined


def _bound_cohort_ids(
    bundle: Mapping[str, Any], packet: Mapping[str, Any] | None
) -> list[str]:
    sources: list[Mapping[str, Any]] = []
    if isinstance(packet, Mapping):
        sources.append(packet)
    receipt = bundle.get("session_receipt")
    if isinstance(receipt, Mapping):
        sources.append(receipt)
    sources.append(bundle)
    for source in sources:
        for key in ("bound_visible_cohort_ids", "visible_cohort_ids", "used_cohort_ids"):
            raw = source.get(key)
            if isinstance(raw, list) and raw:
                return [str(item) for item in raw if item]
    return []


def _ladder_representation_id(
    bundle: Mapping[str, Any], packet: Mapping[str, Any] | None
) -> str:
    sources: list[Mapping[str, Any]] = []
    if isinstance(packet, Mapping):
        sources.append(packet)
    receipt = bundle.get("session_receipt")
    if isinstance(receipt, Mapping):
        sources.append(receipt)
    sources.append(bundle)
    for source in sources:
        rid = source.get(LADDER_REPRESENTATION_PACKET_KEY) or source.get("representation_id")
        if rid in {"NORMALIZED_TRAJECTORY_V1", "SYNTHETIC_LATER_V2"}:
            return str(rid)
        if source.get("normalized_trajectory_v1"):
            return "NORMALIZED_TRAJECTORY_V1"
    parent = _parent_control_id(bundle, packet)
    session_id = str(bundle.get("session_id") or "")
    if parent and parent != session_id:
        return "NORMALIZED_TRAJECTORY_V1"
    return "BASE"


def _focus_matches(
    bundle: Mapping[str, Any],
    packet: Mapping[str, Any] | None,
    owner_focus: str,
) -> bool:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    observed_focus = (
        bundle.get("owner_focus")
        or (packet or {}).get("owner_focus")
        or receipt.get("owner_focus")
    )
    if str(observed_focus or "") == owner_focus:
        return True
    observed_key = (
        bundle.get("focus_key_sha256")
        or (packet or {}).get("focus_key_sha256")
        or receipt.get("focus_key_sha256")
    )
    return observed_key == focus_key_sha256(owner_focus)


def _cohorts_cover_current(bound: Sequence[str], visible: Sequence[str]) -> bool:
    if not bound:
        return False
    return set(bound) == set(visible)


def _packet_for_bundle(
    data_root: Path, bundle: Mapping[str, Any], store: ResearchStore
) -> dict[str, Any] | None:
    packet = bundle.get("forge_context_packet")
    if isinstance(packet, Mapping):
        return dict(packet)
    digest = bundle.get("forge_context_packet_sha256")
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    if not isinstance(digest, str):
        digest = receipt.get("forge_context_packet_sha256")
    if not isinstance(digest, str):
        return None
    try:
        loaded = load_forge_context_packet(data_root, digest, store=store)
    except (LadderError, OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _stage_rank(row: Mapping[str, Any]) -> int:
    status = str(row.get("execution_status") or EXEC_NOT_RUN)
    terminal = row.get("effective_terminal")
    draft = row.get("draft_sha256")
    if status == EXEC_NOT_RUN:
        return 0
    if status == EXEC_BLOCKED:
        return 1
    if isinstance(draft, str) and not isinstance(terminal, str):
        return 2
    if status in {EXEC_EXECUTED, EXEC_REUSED} and not isinstance(terminal, str):
        return 3
    if isinstance(terminal, str):
        return 4
    return 2


def _prefer_stage(
    live: Mapping[str, Any] | None, saved: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    if live is None and saved is None:
        return None
    if live is None:
        return dict(saved or {})
    if saved is None:
        return dict(live)
    return dict(live if _stage_rank(live) >= _stage_rank(saved) else saved)


def _progress_signature(receipt: Mapping[str, Any]) -> tuple[Any, ...]:
    stages = []
    for row in receipt.get("stages") or []:
        if not isinstance(row, Mapping):
            continue
        stages.append(
            (
                row.get("representation_id"),
                row.get("execution_status"),
                row.get("effective_terminal"),
                row.get("session_state"),
                row.get("draft_sha256"),
                row.get("stage_ref_sha256"),
                row.get("session_id"),
            )
        )
    return (receipt.get("next_action"), receipt.get("owner_final"), tuple(stages))


def load_forge_context_packet(
    data_root: Path,
    digest: str,
    *,
    store: ResearchStore,
) -> dict[str, Any]:
    if not isinstance(digest, str) or len(digest) != 64:
        raise LadderError("FORGE_CONTEXT_HASH_MISMATCH")
    blob = Path(data_root) / FORGE_CONTEXT_ARTIFACT_DIR / f"{digest}.json"
    if blob.is_symlink() or not blob.is_file():
        raise LadderError("FORGE_CONTEXT_ARTIFACT_MISSING")
    body = blob.read_bytes()
    loaded = json.loads(body.decode("utf-8"))
    if not isinstance(loaded, dict) or canonical_sha256(loaded) != digest:
        raise LadderError("FORGE_CONTEXT_HASH_MISMATCH")
    found = False
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") != FORGE_CONTEXT_ARTIFACT_KIND:
            continue
        if payload.get("payload_sha256") == digest:
            found = True
            break
    if not found:
        raise LadderError("FORGE_CONTEXT_ARTIFACT_MISSING")
    return loaded


def control_receipt_from_bundle(
    data_root: Path,
    bundle: Mapping[str, Any],
    *,
    store: ResearchStore,
) -> dict[str, Any]:
    """Rebuild a probe-compatible CONTROL receipt from a persisted session bundle."""

    receipt_doc = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    digest = bundle.get("forge_context_packet_sha256") or receipt_doc.get(
        "forge_context_packet_sha256"
    )
    packet = bundle.get("forge_context_packet")
    if not isinstance(packet, Mapping) and isinstance(digest, str):
        packet = load_forge_context_packet(data_root, digest, store=store)
    critic = bundle.get("critic_input_packet")
    critic_sha = bundle.get("critic_input_packet_sha256") or receipt_doc.get(
        "critic_input_packet_sha256"
    )
    mode = (
        session_evidence_surface_mode(receipt_doc)
        or session_evidence_surface_mode(bundle)
        or (packet.get("evidence_surface_mode") if isinstance(packet, Mapping) else None)
    )
    terminal = (
        effective_control_terminal(receipt_doc)
        or effective_control_terminal(bundle)
        or receipt_doc.get("final_session_terminal")
        or bundle.get("final_session_terminal")
    )
    out: dict[str, Any] = {
        "session_id": bundle.get("session_id") or receipt_doc.get("session_id"),
        "session_receipt": receipt_doc or None,
        "final_session_terminal": terminal,
        "effective_control_terminal": terminal,
        "critic_terminal": bundle.get("critic_terminal")
        or receipt_doc.get("critic_terminal"),
        "evidence_epoch_sha256": bundle.get("evidence_epoch_sha256")
        or receipt_doc.get("evidence_epoch_sha256"),
        "evidence_surface_mode": mode,
        "prompt_version": bundle.get("prompt_version")
        or receipt_doc.get("prompt_version"),
        "search_key_sha256": bundle.get("search_key_sha256")
        or receipt_doc.get("search_key_sha256"),
        "focus_key_sha256": bundle.get("focus_key_sha256")
        or receipt_doc.get("focus_key_sha256"),
        "memory_eligibility_sha256": bundle.get("memory_eligibility_sha256")
        or receipt_doc.get("memory_eligibility_sha256"),
        "memory_policy_head_sha256": bundle.get("memory_policy_head_sha256")
        or receipt_doc.get("memory_policy_head_sha256"),
    }
    memory = bundle.get("memory_baseline_sha256") or receipt_doc.get(
        "memory_baseline_sha256"
    )
    if isinstance(memory, str) and len(memory) == 64:
        out["memory_baseline_sha256"] = memory
    # Prefer critic context when present (selected CONTROL); else forge (NO_WORTHY).
    if isinstance(critic, Mapping) and critic and isinstance(critic_sha, str) and len(critic_sha) == 64:
        out["critic_input_packet"] = dict(critic)
        out["critic_input_packet_sha256"] = critic_sha
        out["forge_context_packet"] = packet if isinstance(packet, Mapping) else None
        out["forge_context_packet_sha256"] = digest
    else:
        out["critic_input_packet"] = None
        out["critic_input_packet_sha256"] = None
        out["forge_context_packet"] = packet if isinstance(packet, Mapping) else None
        out["forge_context_packet_sha256"] = digest
    return out


def _lookup_run_artifact(
    store: ResearchStore, identity: str
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    completed: dict[str, Any] | None = None
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") != FORGE_RUN_ARTIFACT_KIND:
            continue
        raw = payload.get("payload_canonical")
        if not isinstance(raw, str):
            continue
        body = json.loads(raw)
        if isinstance(body, dict) and body.get("run_identity_sha256") == identity:
            latest = body
            if body.get("owner_final"):
                completed = body
    return completed or latest


def _persist_run_receipt(
    store: ResearchStore,
    receipt: Mapping[str, Any],
    *,
    repo_root: Path,
) -> None:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    body = canonical_json_bytes(receipt).decode("utf-8")
    digest = receipt["receipt_sha256"]
    now = datetime.now(tz=UTC)
    git_sha = repository_git_snapshot(Path(repo_root)).head_sha.lower()
    artifact = {
        "research_artifact_id": f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        "hfic_protocol": "HFIC-V1.2",
        "artifact_kind": FORGE_RUN_ARTIFACT_KIND,
        "payload_canonical": body,
        "payload_sha256": digest,
    }
    payload_json = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    transaction_id = f"RESEARCH-TXN-FORGERUN-{digest[:16].upper()}"
    event = ResearchEvent(
        record_id=f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-FORGE-RUN-{digest[:16].upper()}",
        hypothesis_version_id=None,
        run_id=receipt.get("run_id"),
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git_sha,
        created_at=now,
    )
    store.append([event], transaction_id=transaction_id)


def _discover_ladder_stages(
    *,
    data_root: Path,
    store: ResearchStore,
    owner_focus: str,
    visible: Sequence[str],
    preferred_control_session_id: str | None,
    saved_draft_sha256: str | None,
    v1_snapshot: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    grouped: dict[str, list[tuple[str, dict[str, Any], Mapping[str, Any]]]] = {}
    for item in list_hfic_sessions(store):
        sid = str(item.get("session_id") or "")
        if not sid:
            continue
        try:
            bundle = load_session_bundle(store, sid)
        except Exception:
            continue
        if bundle is None:
            continue
        packet = _packet_for_bundle(Path(data_root), bundle, store)
        receipt_doc = (
            bundle.get("session_receipt")
            if isinstance(bundle.get("session_receipt"), Mapping)
            else None
        )
        mode = (
            session_evidence_surface_mode(receipt_doc)
            or session_evidence_surface_mode(item)
            or session_evidence_surface_mode(bundle)
            or (session_evidence_surface_mode(packet) if packet else None)
        )
        rep_id = _ladder_representation_id(bundle, packet)
        stage = _stage_from_session(
            bundle, representation_id=rep_id, packet=packet
        )
        if mode == CURRENT_REPRESENTATION_CONTROL_V1 and rep_id == "BASE":
            stage["evidence_surface_mode"] = CURRENT_REPRESENTATION_CONTROL_V1
            stage["input_scope"] = CURRENT_REPRESENTATION_CONTROL_V1
        grouped.setdefault(rep_id, []).append((sid, stage, bundle))

    chosen: tuple[str, dict[str, Any], Mapping[str, Any]] | None = None
    if preferred_control_session_id:
        for sid, stage, bundle in grouped.get("BASE", []):
            if sid == preferred_control_session_id:
                chosen = (sid, stage, bundle)
                break
        if chosen is None:
            try:
                preferred_bundle = load_session_bundle(
                    store, preferred_control_session_id
                )
            except Exception:
                preferred_bundle = None
            if preferred_bundle is not None:
                packet = _packet_for_bundle(Path(data_root), preferred_bundle, store)
                chosen = (
                    preferred_control_session_id,
                    _stage_from_session(
                        preferred_bundle, representation_id="BASE", packet=packet
                    ),
                    preferred_bundle,
                )
    if chosen is None:
        applicable: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
        for sid, stage, bundle in grouped.get("BASE", []):
            packet = _packet_for_bundle(Path(data_root), bundle, store)
            bound = list(stage.get("used_cohort_ids") or [])
            if not _focus_matches(bundle, packet, owner_focus):
                continue
            if str(stage.get("evidence_surface_mode") or "") != CURRENT_REPRESENTATION_CONTROL_V1:
                continue
            if not _cohorts_cover_current(bound, visible):
                continue
            applicable.append((sid, stage, bundle))
        if applicable:
            picked = pick_session(
                [{"session_id": sid, "session_state": stage.get("session_state")} for sid, stage, _ in applicable]
            )
            pick_id = str(picked.get("session_id") or "")
            chosen = next(item for item in applicable if item[0] == pick_id)

    control_session_id = None
    legacy_epoch = None
    resolved: list[dict[str, Any]] = []
    if chosen is None:
        # No CONTROL-applicable BASE. Keep honest ordinary sessions in focus:
        # pending → RESUME; final PASS → OWNER_CANDIDATE readback; V1-trigger
        # negatives → resolve emits CONTROL_SURFACE_REQUIRED. Fresh / unmatched
        # always pre-selects CONTROL-compatible START_BASE (not bare ordinary).
        ordinary_pending: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
        ordinary_pass: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
        ordinary_trigger: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
        for sid, stage, bundle in grouped.get("BASE", []):
            if str(stage.get("evidence_surface_mode") or "") == CURRENT_REPRESENTATION_CONTROL_V1:
                continue
            packet = _packet_for_bundle(Path(data_root), bundle, store)
            if not _focus_matches(bundle, packet, owner_focus):
                continue
            row = (sid, dict(stage), bundle)
            state = str(stage.get("session_state") or "")
            terminal = stage.get("effective_terminal")
            if state in RESUME_STATES or state in PAUSE_STATES:
                ordinary_pending.append(row)
            elif isinstance(terminal, str) and (
                terminal in PASS_TERMINALS or terminal in CASE_A_TERMINALS
            ):
                ordinary_pass.append(row)
            elif isinstance(terminal, str) and terminal in {
                "NO_WORTHY_HYPOTHESIS",
                "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
            }:
                ordinary_trigger.append(row)
        ordinary_pick = ordinary_pending or ordinary_pass or ordinary_trigger
        if ordinary_pick:
            picked = pick_session(
                [
                    {
                        "session_id": sid,
                        "session_state": stage.get("session_state"),
                    }
                    for sid, stage, _ in ordinary_pick
                ]
            )
            pick_id = str(picked.get("session_id") or "")
            _sid, base_stage, _bundle = next(
                item for item in ordinary_pick if item[0] == pick_id
            )
            if str(base_stage.get("session_state") or "") == "SYNTHESIS_COMPLETE":
                base_stage["execution_status"] = EXEC_REUSED
            base_stage["input_scope"] = "ORDINARY_BASE"
            resolved.append(base_stage)
        else:
            resolved.append(
                {
                    "representation_id": "BASE",
                    "execution_status": EXEC_NOT_RUN,
                    "effective_terminal": None,
                    "input_scope": "ORDINARY_BASE",
                    "session_id": None,
                    "used_cohort_ids": [],
                    "reason_code": "CONTROL_SURFACE_REQUIRED",
                }
            )
    else:
        control_session_id, base_stage, chosen_bundle = chosen
        bound = list(base_stage.get("used_cohort_ids") or [])
        packet = _packet_for_bundle(Path(data_root), chosen_bundle, store)
        if _cohorts_cover_current(bound, visible) and _focus_matches(
            chosen_bundle, packet, owner_focus
        ):
            if str(base_stage.get("session_state") or "") == "SYNTHESIS_COMPLETE":
                base_stage["execution_status"] = EXEC_REUSED
        else:
            base_stage["execution_status"] = EXEC_EXECUTED
        if (
            str(base_stage.get("evidence_surface_mode") or "")
            == CURRENT_REPRESENTATION_CONTROL_V1
        ):
            base_stage["input_scope"] = CURRENT_REPRESENTATION_CONTROL_V1
        legacy_epoch = chosen_bundle.get("evidence_epoch_sha256")
        resolved.append(base_stage)

    v1_used: list[str] = []
    v1_status = EXEC_NOT_RUN
    v1_terminal = None
    v1_reason = None
    v1_stage: dict[str, Any] | None = None
    v1_rows = grouped.get("NORMALIZED_TRAJECTORY_V1") or []
    if control_session_id:
        matching = [
            row for row in v1_rows
            if _parent_control_id(row[2], _packet_for_bundle(Path(data_root), row[2], store))
            == control_session_id
        ]
        if matching:
            picked = pick_session(
                [{"session_id": sid, "session_state": stage.get("session_state")} for sid, stage, _ in matching]
            )
            pick_id = str(picked.get("session_id") or "")
            _, v1_stage, _ = next(item for item in matching if item[0] == pick_id)
    if v1_stage is None and (
        control_session_id
        and str(resolved[0].get("effective_terminal") or "")
        in {"NO_WORTHY_HYPOTHESIS", "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED"}
    ):
        if v1_snapshot:
            try:
                bundle = load_session_bundle(store, control_session_id)
                if bundle is not None:
                    control_receipt = control_receipt_from_bundle(
                        Path(data_root), bundle, store=store
                    )
                    snapshot = {
                        "control_present": True,
                        "control_receipt": control_receipt,
                        "control_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                    }
                    snapshot.update(dict(v1_snapshot))
                    if "evidence_epoch_matches" not in snapshot:
                        snapshot["evidence_epoch_matches"] = _evidence_epoch_matches(
                            control_receipt, v1_snapshot
                        )
                    status = representation_status(snapshot)
                    code = str(status.get("reason_code") or status.get("status") or "")
                    if status.get("status") == "RUNNER_UP_PAUSE":
                        v1_status = EXEC_BLOCKED
                        v1_reason = RUNNER_UP_REVISION_REQUIRED
                    elif status.get("status") in {
                        "OBSERVABILITY_BLOCKED",
                        "CONTROL_REQUIRED",
                    }:
                        v1_status = EXEC_BLOCKED
                        v1_reason = code
            except (
                LadderError,
                RepresentationProbeError,
                ResearchStoreError,
                OSError,
                ValueError,
            ) as exc:
                v1_status = EXEC_BLOCKED
                v1_reason = str(exc)
        v1_stage = {
            "representation_id": "NORMALIZED_TRAJECTORY_V1",
            "execution_status": v1_status,
            "effective_terminal": v1_terminal,
            "input_scope": "REPRESENTATION_RELEASE_LOCAL",
            "session_id": None,
            "used_cohort_ids": v1_used,
            "reason_code": v1_reason,
            "stage_ref_sha256": None,
            "draft_sha256": saved_draft_sha256,
        }
    if v1_stage is not None:
        resolved.append(v1_stage)

    for rep_id, rows in grouped.items():
        if rep_id in {"BASE", "NORMALIZED_TRAJECTORY_V1"}:
            continue
        if not control_session_id:
            continue
        matching = [
            row for row in rows
            if _parent_control_id(row[2], _packet_for_bundle(Path(data_root), row[2], store))
            == control_session_id
        ]
        if not matching:
            continue
        picked = pick_session(
            [{"session_id": sid, "session_state": stage.get("session_state")} for sid, stage, _ in matching]
        )
        pick_id = str(picked.get("session_id") or "")
        _, stage, _ = next(item for item in matching if item[0] == pick_id)
        resolved.append(stage)
    return resolved, control_session_id, legacy_epoch if isinstance(legacy_epoch, str) else None


def _parent_control_id(
    bundle: Mapping[str, Any], packet: Mapping[str, Any] | None
) -> str | None:
    for source in (packet, bundle.get("session_receipt"), bundle):
        if not isinstance(source, Mapping):
            continue
        sid = source.get("control_session_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def evaluate_forge_run(
    repo_root: Path,
    data_root: Path,
    *,
    owner_focus: str = "AUTO",
    persist: bool = False,
    registry: Mapping[str, Any] | None = None,
    preferred_control_session_id: str | None = None,
    stages: Sequence[Mapping[str, Any]] | None = None,
    existing_completed: bool = False,
    saved_draft_sha256: str | None = None,
    v1_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble A3 input + existing sessions into one bounded run receipt.

    persist=False never writes. persist=True is for disposable/fixture stores
    or an already-authorized slash; this delivery does not run science.
    """

    registry_doc = dict(registry) if registry is not None else load_ladder_registry()
    frozen_ids = eligible_representation_ids(registry_doc)
    input_receipt = build_forge_input_receipt(
        Path(data_root), repo_root=Path(repo_root), owner_focus=owner_focus
    )
    visible = list(input_receipt.get("active_evidence_set", {}).get("visible_cohort_ids") or [])
    writes = {"research_store": 0, "forge_run": 0, "session": 0}
    owner_class_input = str(input_receipt.get("owner_class") or "")
    if stages is not None:
        owner_class_input = ""

    store = ResearchStore(Path(data_root), create_if_missing=False)
    resolved_stages: list[dict[str, Any]]
    control_session_id = None
    legacy_epoch = None
    used_cohorts: list[str] = []
    if stages is not None:
        resolved_stages = [dict(row) for row in stages]
        for row in resolved_stages:
            if row.get("representation_id") == "BASE":
                control_session_id = row.get("session_id")
                legacy_epoch = row.get("legacy_epoch_sha256")
            used_cohorts.extend(list(row.get("used_cohort_ids") or []))
    else:
        resolved_stages, control_session_id, legacy_epoch = _discover_ladder_stages(
            data_root=Path(data_root),
            store=store,
            owner_focus=owner_focus,
            visible=visible,
            preferred_control_session_id=preferred_control_session_id,
            saved_draft_sha256=saved_draft_sha256,
            v1_snapshot=v1_snapshot,
        )
        for row in resolved_stages:
            used_cohorts.extend(list(row.get("used_cohort_ids") or []))

    identity_material = {
        "input_receipt_sha256": input_receipt.get("receipt_sha256"),
        "frozen_representation_ids": frozen_ids,
        "owner_focus": owner_focus,
        "legacy_epoch_sha256": legacy_epoch,
        "control_session_id": control_session_id,
    }
    run_identity = canonical_sha256(identity_material)
    existing = None
    try:
        existing = _lookup_run_artifact(store, run_identity)
    except ResearchStoreError:
        existing = None
    if existing is not None and existing.get("owner_final"):
        return _readback_existing_run(existing)
    if existing is not None:
        if not saved_draft_sha256:
            for row in existing.get("stages") or []:
                if isinstance(row, Mapping) and isinstance(row.get("draft_sha256"), str):
                    saved_draft_sha256 = row["draft_sha256"]
                    break
        saved_by_id = {
            str(row.get("representation_id")): row
            for row in existing.get("stages") or []
            if isinstance(row, Mapping)
        }
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in resolved_stages:
            rid = str(row.get("representation_id"))
            seen.add(rid)
            preferred = _prefer_stage(row, saved_by_id.get(rid))
            if preferred is not None:
                merged.append(preferred)
        for rid, saved in saved_by_id.items():
            if rid not in seen:
                merged.append(dict(saved))
        resolved_stages = merged

    decision = resolve_next_action(
        resolved_stages,
        registry=registry_doc,
        input_owner_class=owner_class_input if owner_class_input in {
            OWNER_CLASS_INPUT_NOT_READY,
            OWNER_CLASS_OBSERVABILITY_BLOCKED,
        } else None,
        existing_completed=existing_completed,
        saved_draft_sha256=saved_draft_sha256,
    )

    owner_final = decision.get("owner_final")
    next_action = str(decision.get("next_action"))
    if owner_class_input == OWNER_CLASS_INPUT_NOT_READY:
        owner_class = OWNER_CLASS_INPUT_NOT_READY
    elif owner_class_input == OWNER_CLASS_OBSERVABILITY_BLOCKED or next_action == ACTION_OBSERVABILITY_BLOCKED:
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED
    elif owner_final:
        owner_class = OWNER_CLASS_FINAL
    else:
        owner_class = OWNER_CLASS_IN_PROGRESS

    run_id = f"FORGE-RUN-{run_identity[:16].upper()}"
    blocking = []
    if decision.get("reason_code"):
        blocking.append(str(decision["reason_code"]))
    if not input_receipt.get("forge_runnable"):
        blocking.extend(list(input_receipt.get("blocking_reason_codes") or []))

    stage_out = []
    used_cohorts = []
    for row in resolved_stages:
        stage_out.append(
            {
                "representation_id": row.get("representation_id"),
                "execution_status": row.get("execution_status") or EXEC_NOT_RUN,
                "effective_terminal": row.get("effective_terminal"),
                "input_scope": row.get("input_scope") or "UNDECLARED",
                "session_id": row.get("session_id"),
                "session_state": row.get("session_state"),
                "selected_candidate_id": row.get("selected_candidate_id"),
                "runner_up_candidate_id": row.get("runner_up_candidate_id"),
                "stage_ref_sha256": row.get("stage_ref_sha256"),
                "used_cohort_ids": list(row.get("used_cohort_ids") or []),
                "draft_sha256": row.get("draft_sha256") or decision.get("draft_sha256"),
                "reason_code": row.get("reason_code"),
                "critic_terminal": row.get("critic_terminal"),
                "critic_decisive_reason": row.get("critic_decisive_reason")
                or row.get("critic_terminal"),
                "critic_identity": row.get("critic_identity"),
                "declined_candidate_ids": list(row.get("declined_candidate_ids") or []),
                "candidate_mechanism": row.get("candidate_mechanism"),
            }
        )
        used_cohorts.extend(list(row.get("used_cohort_ids") or []))

    unsigned = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_identity_sha256": run_identity,
        "owner_class": owner_class,
        "next_action": next_action,
        "owner_final": owner_final,
        "input_receipt_sha256": input_receipt.get("receipt_sha256"),
        "visible_cohort_ids": visible,
        "used_cohort_ids": list(dict.fromkeys(used_cohorts)),
        "frozen_representation_ids": frozen_ids,
        "stages": stage_out,
        "legacy_epoch_sha256": legacy_epoch if isinstance(legacy_epoch, str) else None,
        "control_session_id": control_session_id,
        "blocking_reason_codes": blocking,
        "writes": writes,
    }
    unsigned["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in unsigned.items() if key != "owner_readout"}
    )
    unsigned["owner_readout"] = format_forge_run_owner_readout(unsigned)
    errors = list(_validator().iter_errors(unsigned))
    if errors:
        raise LadderError("FORGE_RUN_RECEIPT_INVALID")

    if persist and (
        existing is None
        or _progress_signature(unsigned) != _progress_signature(existing)
    ):
        writes = {"research_store": 1, "forge_run": 1, "session": 0}
        unsigned["writes"] = writes
        unsigned.pop("receipt_sha256", None)
        unsigned["receipt_sha256"] = canonical_sha256(
            {key: value for key, value in unsigned.items() if key != "owner_readout"}
        )
        unsigned["owner_readout"] = format_forge_run_owner_readout(unsigned)
        errors = list(_validator().iter_errors(unsigned))
        if errors:
            raise LadderError("FORGE_RUN_RECEIPT_INVALID")
        _persist_run_receipt(store, unsigned, repo_root=Path(repo_root))
        store.rebuild_projection()
    return unsigned


def _readback_existing_run(existing: Mapping[str, Any]) -> dict[str, Any]:
    overlay = dict(existing)
    original_sha = overlay.get("receipt_sha256")
    overlay["next_action"] = ACTION_RETURN_EXISTING
    overlay["persisted_receipt_sha256"] = (
        original_sha if isinstance(original_sha, str) else None
    )
    overlay.pop("receipt_sha256", None)
    overlay.pop("owner_readout", None)
    overlay["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in overlay.items() if key != "owner_readout"}
    )
    overlay["owner_readout"] = format_forge_run_owner_readout(overlay)
    return overlay


def _evidence_epoch_matches(
    control_receipt: Mapping[str, Any], extra: Mapping[str, Any] | None
) -> bool:
    if extra is not None and "evidence_epoch_matches" in extra:
        return extra.get("evidence_epoch_matches") is True
    control_epoch = control_receipt.get("evidence_epoch_sha256")
    extra_epoch = extra.get("evidence_epoch_sha256") if extra else None
    if extra_epoch is None and extra:
        nested = extra.get("control_receipt")
        if isinstance(nested, Mapping):
            extra_epoch = nested.get("evidence_epoch_sha256")
    return bool(
        isinstance(control_epoch, str)
        and isinstance(extra_epoch, str)
        and control_epoch == extra_epoch
    )


def representation_status_snapshot(
    control_receipt: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = {
        "control_present": True,
        "control_receipt": dict(control_receipt),
        "control_mode": CURRENT_REPRESENTATION_CONTROL_V1,
    }
    if extra:
        snapshot.update(dict(extra))
    if "evidence_epoch_matches" not in snapshot:
        snapshot["evidence_epoch_matches"] = _evidence_epoch_matches(
            control_receipt, extra
        )
    return representation_status(snapshot)
