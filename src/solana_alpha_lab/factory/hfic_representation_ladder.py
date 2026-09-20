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
    list_hfic_sessions,
    load_session_bundle,
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
        "PASS_TO_CLASSIFICATION",
    }
)

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
    if base_state in RESUME_STATES:
        return {
            "next_action": ACTION_RESUME_BASE,
            "owner_final": None,
            "reason_code": base_state,
            "draft_sha256": saved_draft_sha256 or base.get("draft_sha256"),
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
            "owner_final": ACTION_KEEP_PAUSE if action == ACTION_KEEP_PAUSE else None,
            "reason_code": base_state or str(base_terminal),
        }
    if isinstance(base_terminal, str) and base_terminal in PASS_TERMINALS:
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
    if isinstance(base_terminal, str) and base_terminal in CASE_A_TERMINALS:
        return {
            "next_action": ACTION_OWNER_CANDIDATE,
            "owner_final": ACTION_OWNER_CANDIDATE,
            "reason_code": base_terminal,
        }

    v1_row = by_id.get("NORMALIZED_TRAJECTORY_V1")
    v1_stage = stage_map.get("NORMALIZED_TRAJECTORY_V1")
    if (
        v1_row
        and v1_row["status"] == "ACTIVE"
        and isinstance(base_terminal, str)
        and base_terminal in set(v1_row["trigger_terminals"])
        and control_probe_permitted(base_terminal)
    ):
        if str(base.get("evidence_surface_mode") or "") != CURRENT_REPRESENTATION_CONTROL_V1:
            return {
                "next_action": ACTION_CONTROL_REQUIRED,
                "owner_final": ACTION_CONTROL_REQUIRED,
                "reason_code": "CONTROL_REQUIRED",
            }
        if v1_stage is None or str(v1_stage.get("execution_status") or EXEC_NOT_RUN) == EXEC_NOT_RUN:
            if saved_draft_sha256:
                return {
                    "next_action": ACTION_RESUME_V1,
                    "owner_final": None,
                    "reason_code": "SAVED_DRAFT_PRESENT",
                    "draft_sha256": saved_draft_sha256,
                }
            return {
                "next_action": ACTION_START_V1,
                "owner_final": None,
                "reason_code": ACTION_START_V1,
            }
        v1_status = str(v1_stage.get("execution_status") or EXEC_NOT_RUN)
        v1_terminal = v1_stage.get("effective_terminal")
        if v1_status == EXEC_BLOCKED:
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": str(
                    v1_stage.get("reason_code") or ACTION_OBSERVABILITY_BLOCKED
                ),
            }
        v1_state = str(v1_stage.get("session_state") or "")
        if v1_state in RESUME_STATES:
            return {
                "next_action": ACTION_RESUME_V1,
                "owner_final": None,
                "reason_code": v1_state,
                "draft_sha256": saved_draft_sha256 or v1_stage.get("draft_sha256"),
            }
        if v1_state in PAUSE_STATES:
            return {
                "next_action": ACTION_KEEP_PAUSE,
                "owner_final": ACTION_KEEP_PAUSE,
                "reason_code": v1_state,
            }
        if isinstance(v1_terminal, str) and v1_terminal in PASS_TERMINALS:
            return {
                "next_action": ACTION_OWNER_CANDIDATE,
                "owner_final": ACTION_OWNER_CANDIDATE,
                "reason_code": v1_terminal,
            }
        if isinstance(v1_terminal, str) and v1_terminal in CASE_C_KILL_TERMINALS:
            return {
                "next_action": ACTION_NON_SCIENTIFIC_STOP,
                "owner_final": ACTION_NON_SCIENTIFIC_STOP,
                "reason_code": v1_terminal,
            }
        if v1_status in {EXEC_EXECUTED, EXEC_REUSED} and not isinstance(v1_terminal, str):
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": "V1_TERMINAL_MISSING",
            }
        next_rep = _next_active_after(
            active, "NORMALIZED_TRAJECTORY_V1", str(v1_terminal or "")
        )
        if next_rep is not None:
            return {
                "next_action": f"START_{next_rep}",
                "owner_final": None,
                "reason_code": str(v1_terminal or "NEXT_ACTIVE"),
            }
        if not isinstance(v1_terminal, str) or v1_terminal not in (
            KNOWN_SCIENTIFIC_NEGATIVES | CASE_C_KILL_TERMINALS | PASS_TERMINALS
        ):
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": "V1_TERMINAL_UNMATCHED",
            }
        stage_ref = v1_stage.get("stage_ref_sha256")
        if not isinstance(stage_ref, str) or len(stage_ref) != 64:
            return {
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "reason_code": "V1_STAGE_REF_MISSING",
            }
        return {
            "next_action": ACTION_SEARCH_EXHAUSTED,
            "owner_final": ACTION_SEARCH_EXHAUSTED,
            "reason_code": v1_terminal,
        }

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
    if baseline.context_kind == CONTROL_CONTEXT_KIND_FORGE:
        return {
            "next_action": ACTION_START_V1,
            "control_context_kind": CONTROL_CONTEXT_KIND_FORGE,
            "challenger": challenger,
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
        "lifecycle": lifecycle,
        "critic_input_packet": packet,
        "control_session_id": lifecycle.get("control_session_id"),
        "representation_search_key_sha256": challenger.get(
            "representation_search_key_sha256"
        ),
        "probe_executed": False,
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
    elif next_action in {ACTION_KEEP_PAUSE, ACTION_CONTROL_REQUIRED}:
        status = "NEXT — typed pause or CONTROL required; evening not success"
    elif owner_final:
        status = "DONE — bounded-run owner-final; do not continue"
    elif next_action == ACTION_START_V1:
        status = "NEXT — continue V1 envelope; do not treat WAIT as done"
    elif next_action in {ACTION_START_BASE, ACTION_RESUME_BASE, ACTION_RESUME_V1}:
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
    lines.append(
        "non_claim: scoped search result on completed representations; "
        "not alpha and not proof of generator recall"
    )
    return "\n".join(lines)


def _stage_from_session(
    bundle: Mapping[str, Any],
    *,
    representation_id: str,
    used_cohort_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    terminal = effective_control_terminal(receipt) or effective_control_terminal(bundle)
    mode = session_evidence_surface_mode(receipt) or session_evidence_surface_mode(bundle)
    state = str(bundle.get("session_state") or "")
    status = EXEC_REUSED if state == "SYNTHESIS_COMPLETE" else EXEC_EXECUTED
    if state in PAUSE_STATES or state in RESUME_STATES:
        status = EXEC_EXECUTED
    draft = bundle.get("draft_sha256") or receipt.get("draft_sha256")
    return {
        "representation_id": representation_id,
        "execution_status": status,
        "effective_terminal": terminal or None,
        "input_scope": (
            CURRENT_REPRESENTATION_CONTROL_V1
            if mode == CURRENT_REPRESENTATION_CONTROL_V1
            else "ORDINARY_BASE"
        ),
        "session_id": bundle.get("session_id"),
        "session_state": state,
        "evidence_surface_mode": mode,
        "selected_candidate_id": bundle.get("selected_candidate_id"),
        "runner_up_candidate_id": bundle.get("runner_up_candidate_id"),
        "stage_ref_sha256": bundle.get("session_receipt_sha256")
        if isinstance(bundle.get("session_receipt_sha256"), str)
        else None,
        "used_cohort_ids": list(used_cohort_ids or []),
        "draft_sha256": draft if isinstance(draft, str) else None,
        "reason_code": None,
    }


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
    receipt_doc = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
    digest = bundle.get("forge_context_packet_sha256") or receipt_doc.get(
        "forge_context_packet_sha256"
    )
    packet = bundle.get("forge_context_packet")
    if not isinstance(packet, Mapping) and isinstance(digest, str):
        packet = load_forge_context_packet(data_root, digest, store=store)
    critic = bundle.get("critic_input_packet")
    mode = (
        session_evidence_surface_mode(receipt_doc)
        or session_evidence_surface_mode(bundle)
        or (packet.get("evidence_surface_mode") if isinstance(packet, Mapping) else None)
    )
    return {
        "session_id": bundle.get("session_id"),
        "session_receipt": receipt_doc or None,
        "critic_input_packet": critic,
        "critic_input_packet_sha256": bundle.get("critic_input_packet_sha256")
        or receipt_doc.get("critic_input_packet_sha256"),
        "forge_context_packet": packet,
        "forge_context_packet_sha256": digest,
        "final_session_terminal": bundle.get("final_session_terminal")
        or receipt_doc.get("final_session_terminal"),
        "critic_terminal": bundle.get("critic_terminal") or receipt_doc.get("critic_terminal"),
        "evidence_epoch_sha256": bundle.get("evidence_epoch_sha256")
        or receipt_doc.get("evidence_epoch_sha256"),
        "evidence_surface_mode": mode,
        "prompt_version": bundle.get("prompt_version") or receipt_doc.get("prompt_version"),
        "search_key_sha256": bundle.get("search_key_sha256") or receipt_doc.get("search_key_sha256"),
        "focus_key_sha256": bundle.get("focus_key_sha256") or receipt_doc.get("focus_key_sha256"),
        "memory_eligibility_sha256": bundle.get("memory_eligibility_sha256")
        or receipt_doc.get("memory_eligibility_sha256"),
    }


def _lookup_run_artifact(
    store: ResearchStore, identity: str
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
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
    return latest


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


def evaluate_forge_run(
    repo_root: Path,
    data_root: Path,
    *,
    owner_focus: str = "AUTO",
    persist: bool = False,
    registry: Mapping[str, Any] | None = None,
    preferred_control_session_id: str | None = EXISTING_V1_CONTROL_SESSION_ID,
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
        resolved_stages = []
        control_candidates: list[tuple[str, dict[str, Any], Mapping[str, Any]]] = []
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
            receipt_doc = (
                bundle.get("session_receipt")
                if isinstance(bundle.get("session_receipt"), Mapping)
                else None
            )
            mode = (
                session_evidence_surface_mode(receipt_doc)
                or session_evidence_surface_mode(item)
                or session_evidence_surface_mode(bundle)
            )
            if mode != CURRENT_REPRESENTATION_CONTROL_V1:
                packet = bundle.get("forge_context_packet")
                digest = bundle.get("forge_context_packet_sha256") or (
                    receipt_doc.get("forge_context_packet_sha256")
                    if isinstance(receipt_doc, Mapping)
                    else None
                )
                if not isinstance(packet, Mapping) and isinstance(digest, str):
                    try:
                        packet = load_forge_context_packet(
                            Path(data_root), digest, store=store
                        )
                    except (LadderError, OSError, ValueError):
                        packet = None
                if isinstance(packet, Mapping):
                    mode = session_evidence_surface_mode(packet)
            if mode != CURRENT_REPRESENTATION_CONTROL_V1:
                continue
            stage = _stage_from_session(
                bundle, representation_id="BASE", used_cohort_ids=visible
            )
            stage["evidence_surface_mode"] = CURRENT_REPRESENTATION_CONTROL_V1
            stage["input_scope"] = CURRENT_REPRESENTATION_CONTROL_V1
            control_candidates.append((sid, stage, bundle))
        chosen: tuple[str, dict[str, Any], Mapping[str, Any]] | None = None
        if preferred_control_session_id:
            for sid, stage, bundle in control_candidates:
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
                    chosen = (
                        preferred_control_session_id,
                        _stage_from_session(
                            preferred_bundle,
                            representation_id="BASE",
                            used_cohort_ids=visible,
                        ),
                        preferred_bundle,
                    )
        if chosen is None and len(control_candidates) == 1:
            chosen = control_candidates[0]
        if chosen is None:
            base_stage = {
                "representation_id": "BASE",
                "execution_status": EXEC_NOT_RUN,
                "effective_terminal": None,
                "input_scope": (
                    CURRENT_REPRESENTATION_CONTROL_V1
                    if control_candidates
                    else "ORDINARY_BASE"
                ),
                "session_id": None,
                "used_cohort_ids": [],
                "reason_code": ACTION_CONTROL_REQUIRED if control_candidates else None,
            }
        else:
            control_session_id, base_stage, _bundle = chosen
            legacy_epoch = _bundle.get("evidence_epoch_sha256")
            if (
                str(base_stage.get("evidence_surface_mode") or "")
                == CURRENT_REPRESENTATION_CONTROL_V1
            ):
                base_stage["input_scope"] = CURRENT_REPRESENTATION_CONTROL_V1
            if not list(base_stage.get("used_cohort_ids") or []):
                base_stage["used_cohort_ids"] = list(visible)
        resolved_stages.append(base_stage)
        if (
            control_session_id
            and str(base_stage.get("effective_terminal") or "")
            in {"NO_WORTHY_HYPOTHESIS", "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED"}
        ):
            v1_status = EXEC_NOT_RUN
            v1_terminal = None
            v1_reason = None
            v1_used: list[str] = []
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
                            snapshot["evidence_epoch_matches"] = (
                                _evidence_epoch_matches(control_receipt, v1_snapshot)
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
            resolved_stages.append(
                {
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
            )

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
    if existing is not None and not saved_draft_sha256:
        for row in existing.get("stages") or []:
            if isinstance(row, Mapping) and isinstance(row.get("draft_sha256"), str):
                saved_draft_sha256 = row["draft_sha256"]
                break
        by_id = {
            str(row.get("representation_id")): row
            for row in existing.get("stages") or []
            if isinstance(row, Mapping)
        }
        for live in resolved_stages:
            saved = by_id.get(str(live.get("representation_id")))
            if not isinstance(saved, Mapping):
                continue
            if not live.get("session_state") and saved.get("session_state"):
                live["session_state"] = saved["session_state"]
            if not live.get("draft_sha256") and saved.get("draft_sha256"):
                live["draft_sha256"] = saved["draft_sha256"]
            if not live.get("stage_ref_sha256") and saved.get("stage_ref_sha256"):
                live["stage_ref_sha256"] = saved["stage_ref_sha256"]

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
            }
        )
        used_cohorts.extend(list(row.get("used_cohort_ids") or []))

    if persist and existing is None:
        writes = {"research_store": 1, "forge_run": 1, "session": 0}

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

    if persist and existing is None:
        _persist_run_receipt(store, unsigned, repo_root=Path(repo_root))
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
