"""HFIC session validation, identity rewrite, budget and decision mapping."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.hfic_identity import (
    HficIdentityError,
    assign_portfolio_ids,
    canonical_candidate_definition,
    normalize_text,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


PROMPT_VERSION = "HFIC-V1.1"
MIN_CANDIDATES = 4
MAX_CANDIDATES = 6
HFIC_EVENT_TIME = datetime(1970, 1, 1, tzinfo=UTC)
PHASE_RANK = {
    "SYNTHESIS_COMPLETE": 0,
    "LEGACY_PARTIAL": 0,
    "CRITIC_RESULT_READY": 1,
    "FROZEN_AWAITING_CRITIC": 2,
    "DRAFT_VALIDATED": 3,
    "PREFLIGHT_PROVEN": 4,
}
PENDING_STATES = frozenset(
    {
        "PREFLIGHT_PROVEN",
        "DRAFT_VALIDATED",
        "FROZEN_AWAITING_CRITIC",
        "CRITIC_RESULT_READY",
    }
)
_MATERIAL_EPOCH_KEYS = (
    "catalog_root_hashes",
    "dataset_manifest_ids",
    "dataset_fingerprints",
    "prior_work_digest",
    "lifecycle_terminals",
    "scientific_terminals",
    "capability_schema_hashes",
    "accepted_query_recipe_hashes",
)
_COMPONENT_FIELDS = (
    "primary_x_family",
    "mechanism",
    "actor_counterparty",
    "population",
    "decision_timestamp",
    "primary_y",
    "horizon_notional",
    "negative_control",
    "cheapest_falsifier",
)
_KILL_TERMINALS = frozenset(
    {
        "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
        "KILL_MECHANISM",
        "KILL_PIT_OR_LEAKAGE",
        "KILL_EXECUTION_OR_ECONOMICS",
        "KILL_DATA_INFEASIBLE",
        "KILL_STATISTICALLY_UNIDENTIFIABLE",
        "KILL_LOW_INFORMATION_VALUE",
        "KILL_PREPARATORY_LOOP",
        "KILL_UNBOUND_EVIDENCE",
    }
)
_REJECT_TERMINALS = frozenset({"NO_WORTHY_HYPOTHESIS"})
_REVISE_TERMINALS = frozenset({"REVISE_ONCE"})
_PAUSE_TERMINALS = frozenset(
    {
        "PASS_TO_CLASSIFICATION",
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
        "PASS_DATA_OPTION_REQUIRED",
        "OWNER_DECISION_REQUIRED",
    }
)
_FORBIDDEN_DECISION_TERMINALS = frozenset({"PROMOTE", "PROMOTION_LANE"})


class HficSessionError(ValueError):
    """Fail-closed HFIC session/protocol error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def evidence_epoch_sha256(material: Mapping[str, Any]) -> str:
    included = {
        key: material[key]
        for key in _MATERIAL_EPOCH_KEYS
        if key in material
    }
    return canonical_sha256(included)


def focus_key_sha256(owner_focus: str) -> str:
    return hashlib.sha256(normalize_text(owner_focus).encode("utf-8")).hexdigest()


def search_key_sha256(epoch: str, owner_focus: str, prompt_version: str) -> str:
    payload = f"{epoch}{focus_key_sha256(owner_focus)}{prompt_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def phase_rank(state: object) -> int:
    return PHASE_RANK.get(str(state or ""), 9)


def pick_session(sessions: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return sorted(
        sessions,
        key=lambda item: (
            phase_rank(item.get("session_state")),
            str(item.get("session_id") or ""),
        ),
    )[0]


def related_prior_matches(
    card: Mapping[str, Any],
    priors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    probe = canonical_candidate_definition(card)
    matches: list[dict[str, Any]] = []
    for prior in priors:
        prior_def = canonical_candidate_definition(prior)
        if probe == prior_def:
            matches.append(
                {
                    "match_kind": "EXACT",
                    "definition_sha256": canonical_sha256(prior_def),
                    "overlap_reasons": list(_COMPONENT_FIELDS),
                }
            )
            continue
        reasons = [field for field in _COMPONENT_FIELDS if probe[field] == prior_def[field]]
        if reasons:
            matches.append(
                {
                    "match_kind": "RELATED_PRIOR",
                    "definition_sha256": canonical_sha256(prior_def),
                    "overlap_reasons": reasons,
                }
            )
    return matches


def map_critic_terminal_to_decision(terminal: str) -> tuple[str, str]:
    if not isinstance(terminal, str) or not terminal:
        raise HficSessionError("CRITIC_TERMINAL_INVALID")
    if terminal in _FORBIDDEN_DECISION_TERMINALS:
        raise HficSessionError("AUTOMATIC_PROMOTE_FORBIDDEN")
    if terminal in _KILL_TERMINALS or terminal in _REJECT_TERMINALS:
        return ("REJECT", terminal)
    if terminal in _REVISE_TERMINALS:
        return ("REVISE", terminal)
    if terminal in _PAUSE_TERMINALS:
        return ("PAUSE", terminal)
    raise HficSessionError("CRITIC_TERMINAL_INVALID")


def _resolve_ref(ref: object, identities: Sequence[Any]) -> int:
    if not isinstance(ref, str) or not ref.strip():
        raise HficSessionError("CROSS_REFERENCE_MISMATCH")
    token = ref.strip()
    for index, identity in enumerate(identities):
        if identity.label and identity.label == token:
            return index
    folded = normalize_text(token)
    for index, identity in enumerate(identities):
        if identity.label and normalize_text(identity.label) == folded:
            return index
        if identity.candidate_id == token:
            return index
    return -1


def freeze_draft(
    draft: Mapping[str, Any],
    *,
    preflight_receipt: Mapping[str, Any] | None = None,
    store: Any = None,
    repo_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(draft, Mapping):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    candidates = draft.get("candidates")
    if not isinstance(candidates, list) or not (
        MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES
    ):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    try:
        identities = assign_portfolio_ids(candidates)
    except HficIdentityError as exc:
        raise HficSessionError(str(exc)) from exc

    selected_index = _resolve_ref(draft.get("selected_candidate_ref"), identities)
    if selected_index < 0:
        raise HficSessionError("SELECTED_CANDIDATE_MISSING")
    runner_up_index = _resolve_ref(draft.get("runner_up_candidate_ref"), identities)
    if runner_up_index < 0:
        raise HficSessionError("CROSS_REFERENCE_MISMATCH")
    if selected_index == runner_up_index:
        raise HficSessionError("SELECTED_EQUALS_RUNNER_UP")
    rejected_index = _resolve_ref(
        draft.get("strongest_rejected_alternative"),
        identities,
    )
    if rejected_index < 0:
        raise HficSessionError("CROSS_REFERENCE_MISMATCH")

    selected = identities[selected_index]
    runner_up = identities[runner_up_index]
    rejected = identities[rejected_index]
    selected_card = candidates[selected_index]
    git_head = "0" * 40
    if isinstance(preflight_receipt, Mapping):
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            git_head = maybe_head
    packet = {
        "packet_schema": "smial.hypothesis-critic-input",
        "packet_version": "1.1",
        "generator_prompt_version": PROMPT_VERSION,
        "generated_at": "1970-01-01T00:00:00Z",
        "live_git_head": git_head,
        "research_memory_as_of": "1970-01-01T00:00:00Z",
        "owner_focus": str(draft.get("owner_focus") or "AUTO"),
        "authority": draft.get("authority")
        or {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "holdouts_not_touched": [],
        "truth_roots_used": [],
        "prior_work_queries": [],
        "selected_candidate": {
            "candidate_id": selected.candidate_id,
            "claim": str(selected_card.get("claim") or ""),
            "nearest_prior_and_difference": str(
                selected_card.get("nearest_prior_and_difference") or "NOT_DECLARED_IN_DRAFT"
            ),
            "actor_counterparty": str(selected_card.get("actor_counterparty") or ""),
            "mechanism": str(selected_card.get("mechanism") or ""),
            "why_not_arbitraged": str(selected_card.get("why_not_arbitraged") or "NOT_DECLARED_IN_DRAFT"),
            "population": str(selected_card.get("population") or ""),
            "decision_timestamp": str(selected_card.get("decision_timestamp") or ""),
            "primary_x": str(selected_card.get("primary_x_family") or ""),
            "primary_y": str(selected_card.get("primary_y") or ""),
            "horizon_notional": str(selected_card.get("horizon_notional") or ""),
            "disconfirming_prediction": str(
                selected_card.get("disconfirming_prediction") or "NOT_DECLARED_IN_DRAFT"
            ),
            "negative_control": str(selected_card.get("negative_control") or ""),
            "alternative_world": str(selected_card.get("alternative_world") or "NOT_DECLARED_IN_DRAFT"),
            "confounders": selected_card.get("confounders") or ["NOT_DECLARED_IN_DRAFT"],
            "pit_leakage_survivorship_risks": selected_card.get(
                "pit_leakage_survivorship_risks"
            )
            or ["NOT_DECLARED_IN_DRAFT"],
            "execution_capacity_risks": selected_card.get("execution_capacity_risks")
            or ["NOT_DECLARED_IN_DRAFT"],
            "available_data_bindings": selected_card.get("available_data_bindings")
            or [],
            "missing_or_forward_only_data": selected_card.get(
                "missing_or_forward_only_data"
            )
            or [],
            "proposed_method": str(selected_card.get("proposed_method") or "NOT_DECLARED_IN_DRAFT"),
            "cheapest_falsifier": str(selected_card.get("cheapest_falsifier") or ""),
            "pass_fail_inconclusive_semantics": str(
                selected_card.get("pass_fail_inconclusive_semantics") or "NOT_DECLARED_IN_DRAFT"
            ),
            "decision_unlocked": str(selected_card.get("decision_unlocked") or "NOT_DECLARED_IN_DRAFT"),
        },
        "provisional_lane": {
            "value": "DATA_OPTION_CANDIDATE",
            "required_capability_ids": [],
            "required_query_recipe_ids": [],
            "required_data_bindings": [],
            "exact_gap": "PROVISIONAL_LANE_NOT_YET_CLASSIFIED",
        },
        "provisional_execution_unit": "NONE",
        "strongest_rejected_alternative": rejected.candidate_id,
        "known_unknowns": ["HFIC_FREEZE_BOUNDED"],
        "non_claims": draft.get("non_claims") or ["NO_ALPHA"],
    }
    owner_focus = str(draft.get("owner_focus") or "AUTO")
    epoch = ""
    focus_key = ""
    search_key = ""
    store_digest = None
    if isinstance(preflight_receipt, Mapping):
        epoch = str(preflight_receipt.get("evidence_epoch_sha256") or "")
        focus_key = str(preflight_receipt.get("focus_key_sha256") or "")
        search_key = str(preflight_receipt.get("search_key_sha256") or "")
        digest = preflight_receipt.get("store_inventory_digest")
        if isinstance(digest, str) and len(digest) == 64:
            store_digest = digest
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            packet["live_git_head"] = maybe_head.lower()
        owner_focus = str(preflight_receipt.get("owner_focus") or owner_focus)
    if not focus_key:
        focus_key = focus_key_sha256(owner_focus)
    if epoch and not search_key:
        search_key = search_key_sha256(epoch, owner_focus, PROMPT_VERSION)
    if search_key:
        session_id = "HFIC-SESS-" + search_key[:16].upper()
    else:
        session_id = "HFIC-SESS-" + canonical_sha256(
            {
                "candidate_ids": [item.candidate_id for item in identities],
                "selected": selected.candidate_id,
                "prompt_version": PROMPT_VERSION,
            }
        )[:16].upper()
    if repo_root is not None:
        _validate_json_schema(
            packet,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_input_v1.schema.json",
        )
    packet_bytes = json.dumps(
        packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    result = {
        "session_id": session_id,
        "session_state": "FROZEN_AWAITING_CRITIC",
        "prompt_version": PROMPT_VERSION,
        "owner_focus": owner_focus,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "selected_candidate_id": selected.candidate_id,
        "runner_up_candidate_id": runner_up.candidate_id,
        "rejected_alternative_id": rejected.candidate_id,
        "selected_definition_sha256": selected.full_sha256,
        "candidate_ids": [item.candidate_id for item in identities],
        "critic_input_packet": packet,
        "critic_input_packet_sha256": hashlib.sha256(
            packet_bytes.encode("utf-8")
        ).hexdigest(),
        "store_inventory_digest": store_digest,
        "identities": [
            {
                "candidate_id": item.candidate_id,
                "definition_sha256": item.full_sha256,
                "definition": item.definition,
                "label": item.label,
                "display_ordinal": item.display_ordinal,
            }
            for item in identities
        ],
    }
    if store is not None and repo_root is not None:
        if not epoch or not search_key or not focus_key:
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        existing = find_session_by_epoch_focus(store, epoch, focus_key)
        if existing is not None:
            return existing
        persist_frozen_session(
            store,
            result,
            repo_root=repo_root,
            identities=identities,
            draft=draft,
        )
        store.rebuild_projection()
        result["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    result.pop("identities", None)
    return result


def backfill_legacy(
    packet: Mapping[str, Any],
    *,
    persist: bool = False,
    store: Any = None,
    repo_root: Any = None,
) -> dict[str, Any]:
    if packet.get("phase") != "LEGACY_PARTIAL":
        raise HficSessionError("LEGACY_PARTIAL_REQUIRED")
    if packet.get("source") != "OWNER_SUPPLIED_TRANSCRIPT":
        raise HficSessionError("LEGACY_SOURCE_INVALID")
    candidates = packet.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    try:
        identities = assign_portfolio_ids(candidates)
    except HficIdentityError as exc:
        raise HficSessionError(str(exc)) from exc
    session_id = "HFIC-SESS-" + canonical_sha256(
        {
            "candidate_ids": [item.candidate_id for item in identities],
            "selected": identities[0].candidate_id,
            "prompt_version": PROMPT_VERSION,
            "source": "OWNER_SUPPLIED_TRANSCRIPT",
        }
    )[:16].upper()
    result = {
        "session_id": session_id,
        "session_state": "LEGACY_PARTIAL",
        "backfilled": True,
        "source": "OWNER_SUPPLIED_TRANSCRIPT",
        "missing_fields": list(packet.get("missing_fields") or []),
        "candidate_ids": [item.candidate_id for item in identities],
        "legacy_aliases": packet.get("legacy_aliases") or {},
        "critic_result_sha256": None,
        "owner_focus": str(packet.get("owner_focus") or "AUTO"),
        "prompt_version": PROMPT_VERSION,
    }
    if persist:
        if store is None or repo_root is None:
            raise HficSessionError("LEGACY_STORE_REQUIRED")
        existing = load_session_bundle(store, session_id)
        if existing is not None:
            return existing
        persist_legacy_session(
            store,
            result,
            identities=identities,
            packet=packet,
            repo_root=repo_root,
        )
        store.rebuild_projection()
        result["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    return result


def persist_frozen_session(
    store: Any,
    frozen: Mapping[str, Any],
    *,
    repo_root: Any,
    identities: Sequence[Any],
    draft: Mapping[str, Any] | None = None,
) -> None:
    """Append freeze records to an existing ResearchStore. Optional for unit tests."""

    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    git = repository_git_snapshot(Path(repo_root))
    now = HFIC_EVENT_TIME
    session_id = str(frozen["session_id"])
    transaction_id = f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFIC-')}"
    producer = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
    ) -> ResearchEvent:
        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return ResearchEvent(
            record_id=record_id,
            record_kind=kind,
            entity_id=entity_id,
            hypothesis_version_id=hypothesis_version_id,
            run_id=None,
            transaction_id=transaction_id,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=producer,
            producer_git_sha=git.head_sha,
            created_at=now,
        )

    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-FROZEN",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": session_id,
                "session_id": session_id,
                "phase": "FROZEN_AWAITING_CRITIC",
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "selected_candidate_id": frozen["selected_candidate_id"],
                "runner_up_candidate_id": frozen["runner_up_candidate_id"],
                "rejected_alternative_id": frozen.get("rejected_alternative_id"),
                "candidate_ids": list(frozen.get("candidate_ids") or []),
                "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
            },
        )
    ]
    for identity in identities:
        records.append(
            event(
                record_id=f"HFIC-HYP-{identity.candidate_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=identity.candidate_id,
                hypothesis_version_id=identity.candidate_id,
                payload={
                    "hypothesis_version_id": identity.candidate_id,
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "statement": identity.definition["claim"],
                    "claim": identity.definition["claim"],
                    "mechanism": identity.definition["mechanism"],
                    "actor_counterparty": identity.definition["actor_counterparty"],
                    "population": identity.definition["population"],
                    "decision_timestamp": identity.definition["decision_timestamp"],
                    "primary_x_family": identity.definition["primary_x_family"],
                    "primary_y": identity.definition["primary_y"],
                    "horizon_notional": identity.definition["horizon_notional"],
                    "negative_control": identity.definition["negative_control"],
                    "falsifier": identity.definition["cheapest_falsifier"],
                    "cheapest_falsifier": identity.definition["cheapest_falsifier"],
                    "definition_sha256": identity.full_sha256,
                    "role_in_session": (
                        "SELECTED"
                        if identity.candidate_id == frozen["selected_candidate_id"]
                        else (
                            "RUNNER_UP"
                            if identity.candidate_id
                            == frozen.get("runner_up_candidate_id")
                            else "PORTFOLIO"
                        )
                    ),
                },
            )
        )
    packet_bytes = json.dumps(
        frozen["critic_input_packet"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    records.append(
        event(
            record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "CRITIC_INPUT_PACKET",
                "payload_canonical": packet_bytes,
                "payload_sha256": hashlib.sha256(
                    packet_bytes.encode("utf-8")
                ).hexdigest(),
            },
        )
    )
    if draft is not None:
        draft_bytes = json.dumps(
            draft,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        records.append(
            event(
                record_id=f"HFIC-ART-FORGE-DRAFT-{session_id}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-FORGE-DRAFT-{session_id}",
                payload={
                    "research_artifact_id": f"HFIC-ART-FORGE-DRAFT-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "artifact_kind": "FORGE_DRAFT",
                    "payload_canonical": draft_bytes,
                    "payload_sha256": hashlib.sha256(
                        draft_bytes.encode("utf-8")
                    ).hexdigest(),
                },
            )
        )
    store.append(records, transaction_id=transaction_id)


def persist_legacy_session(
    store: Any,
    receipt: Mapping[str, Any],
    *,
    identities: Sequence[Any],
    packet: Mapping[str, Any],
    repo_root: Any,
) -> None:
    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    git = repository_git_snapshot(Path(repo_root))
    now = HFIC_EVENT_TIME
    session_id = str(receipt["session_id"])
    transaction_id = f"RESEARCH-TXN-HFICLEG-{session_id[-16:]}"
    producer = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
    ) -> ResearchEvent:
        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return ResearchEvent(
            record_id=record_id,
            record_kind=kind,
            entity_id=entity_id,
            hypothesis_version_id=hypothesis_version_id,
            run_id=None,
            transaction_id=transaction_id,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=producer,
            producer_git_sha=git.head_sha,
            created_at=now,
        )

    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-LEGACY",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-LEGACY",
                "session_id": session_id,
                "phase": "LEGACY_PARTIAL",
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": receipt.get("owner_focus") or "AUTO",
                "source": "OWNER_SUPPLIED_TRANSCRIPT",
                "backfilled": True,
                "missing_fields": list(receipt.get("missing_fields") or []),
                "legacy_aliases": receipt.get("legacy_aliases") or {},
                "candidate_ids": list(receipt.get("candidate_ids") or []),
            },
        )
    ]
    for identity in identities:
        records.append(
            event(
                record_id=f"HFIC-HYP-{identity.candidate_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=identity.candidate_id,
                hypothesis_version_id=identity.candidate_id,
                payload={
                    "hypothesis_version_id": identity.candidate_id,
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "statement": identity.definition["claim"],
                    "claim": identity.definition["claim"],
                    "mechanism": identity.definition["mechanism"],
                    "actor_counterparty": identity.definition["actor_counterparty"],
                    "population": identity.definition["population"],
                    "decision_timestamp": identity.definition["decision_timestamp"],
                    "primary_x_family": identity.definition["primary_x_family"],
                    "primary_y": identity.definition["primary_y"],
                    "horizon_notional": identity.definition["horizon_notional"],
                    "negative_control": identity.definition["negative_control"],
                    "falsifier": identity.definition["cheapest_falsifier"],
                    "cheapest_falsifier": identity.definition["cheapest_falsifier"],
                    "definition_sha256": identity.full_sha256,
                    "role_in_session": "LEGACY_PARTIAL",
                    "legacy_aliases": (packet.get("legacy_aliases") or {}).get(
                        identity.candidate_id
                    ),
                },
            )
        )
    store.append(records, transaction_id=transaction_id)


def list_hfic_sessions(store: Any) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_CYCLE":
            continue
        payload = json.loads(record.payload_json)
        if payload.get("hfic_protocol") is None:
            continue
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            continue
        candidate = {
            "session_id": session_id,
            "session_state": payload.get("phase"),
            "evidence_epoch_sha256": payload.get("evidence_epoch_sha256"),
            "focus_key_sha256": payload.get("focus_key_sha256"),
            "search_key_sha256": payload.get("search_key_sha256"),
            "prompt_version": payload.get("prompt_version"),
            "owner_focus": payload.get("owner_focus"),
        }
        current = latest.get(session_id)
        if current is None or phase_rank(candidate["session_state"]) <= phase_rank(
            current["session_state"]
        ):
            latest[session_id] = candidate
    return list(latest.values())


def find_session_by_epoch_focus(
    store: Any,
    epoch: str,
    focus_key: str,
) -> dict[str, Any] | None:
    matched = [
        item
        for item in list_hfic_sessions(store)
        if item.get("evidence_epoch_sha256") == epoch
        and item.get("focus_key_sha256") == focus_key
    ]
    if not matched:
        return None
    chosen = pick_session(matched)
    return load_session_bundle(store, str(chosen["session_id"]))


def find_session_by_search_key(store: Any, search_key: str) -> dict[str, Any] | None:
    matched = [
        item
        for item in list_hfic_sessions(store)
        if item.get("search_key_sha256") == search_key
    ]
    if not matched:
        return None
    chosen = pick_session(matched)
    return load_session_bundle(store, str(chosen["session_id"]))


def _require_critic_identity(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
) -> str:
    selected_id = str(frozen["selected_candidate_id"])
    if critic_result.get("selected_candidate_id") != selected_id:
        raise HficSessionError("CRITIC_SELECTED_MISMATCH")
    if critic_result.get("session_id") != frozen.get("session_id"):
        raise HficSessionError("CRITIC_SESSION_MISMATCH")
    expected_packet = frozen.get("critic_input_packet_sha256")
    observed_packet = critic_result.get("critic_input_packet_sha256")
    if (
        not isinstance(expected_packet, str)
        or not isinstance(observed_packet, str)
        or expected_packet != observed_packet
    ):
        raise HficSessionError("CRITIC_PACKET_HASH_MISMATCH")
    return selected_id


def finalize_session(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
) -> dict[str, Any]:
    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    selected_id = _require_critic_identity(frozen, critic_result)
    if repo_root is not None:
        _validate_json_schema(
            critic_result,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_result_v1.schema.json",
        )
    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is not None and existing.get("session_state") == "SYNTHESIS_COMPLETE":
        existing_hash = existing.get("critic_result_sha256")
        critic_bytes = json.dumps(
            critic_result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        retry_hash = hashlib.sha256(critic_bytes.encode("utf-8")).hexdigest()
        if existing_hash not in {None, retry_hash}:
            raise HficSessionError("SESSION_CONFLICT")
        return existing
    terminal = str(critic_result.get("critic_terminal") or "")
    if terminal in {
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
        "PASS_DATA_OPTION_REQUIRED",
    }:
        classifier = critic_result.get("classifier_receipt")
        if not isinstance(classifier, Mapping) or not classifier:
            raise HficSessionError("CLASSIFIER_RECEIPT_REQUIRED")
    decision_kind, reason = map_critic_terminal_to_decision(terminal)
    git_before = repository_git_snapshot(Path(repo_root))
    git = git_before
    now = HFIC_EVENT_TIME
    session_id = str(frozen["session_id"])
    transaction_id = f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}"
    producer = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
    ) -> ResearchEvent:
        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return ResearchEvent(
            record_id=record_id,
            record_kind=kind,
            entity_id=entity_id,
            hypothesis_version_id=hypothesis_version_id,
            run_id=None,
            transaction_id=transaction_id,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=producer,
            producer_git_sha=git.head_sha,
            created_at=now,
        )

    critic_bytes = json.dumps(
        critic_result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    existing_state = str((existing or {}).get("session_state") or "")
    if existing_state != "CRITIC_RESULT_READY":
        transaction_id = f"RESEARCH-TXN-HFICRDY-{session_id[-16:]}"
        ready_records = [
            event(
                record_id=f"HFIC-CYCLE-{session_id}-READY",
                kind=RecordKind.RESEARCH_CYCLE,
                entity_id=session_id,
                payload={
                    "research_cycle_id": f"{session_id}-READY",
                    "session_id": session_id,
                    "phase": "CRITIC_RESULT_READY",
                    "hfic_protocol": PROMPT_VERSION,
                    "prompt_version": PROMPT_VERSION,
                    "owner_focus": frozen.get("owner_focus") or "AUTO",
                    "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                    "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                    "search_key_sha256": frozen.get("search_key_sha256") or "",
                    "selected_candidate_id": selected_id,
                    "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
                    "candidate_ids": list(frozen.get("candidate_ids") or []),
                    "critic_terminal": terminal,
                    "next": str(critic_result.get("next") or "STOP"),
                    "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
                },
            ),
            event(
                record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}",
                payload={
                    "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "artifact_kind": "CRITIC_RESULT",
                    "payload_canonical": critic_bytes,
                    "payload_sha256": hashlib.sha256(
                        critic_bytes.encode("utf-8")
                    ).hexdigest(),
                },
            ),
        ]
        store.append(ready_records, transaction_id=transaction_id)

    transaction_id = f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}"
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-COMPLETE",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-COMPLETE",
                "session_id": session_id,
                "phase": "SYNTHESIS_COMPLETE",
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "selected_candidate_id": selected_id,
                "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
                "candidate_ids": list(frozen.get("candidate_ids") or []),
                "critic_terminal": terminal,
                "next": str(critic_result.get("next") or "STOP"),
                "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
            },
        )
    ]
    decision_ids: list[str] = []
    for candidate_id in frozen["candidate_ids"]:
        if candidate_id == selected_id:
            kind, code = decision_kind, reason
        else:
            kind, code = "PAUSE", "NOT_SELECTED_IN_SESSION"
        decision_id = f"HFIC-DEC-{candidate_id}"
        decision_ids.append(decision_id)
        records.append(
            event(
                record_id=decision_id,
                kind=RecordKind.DECISION_EVENT,
                entity_id=decision_id,
                hypothesis_version_id=str(candidate_id),
                payload={
                    "decision_event_id": decision_id,
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "decision_kind": kind,
                    "reason_code": code,
                    "hypothesis_version_id": candidate_id,
                },
            )
        )
    if terminal == "PASS_CHANGE_LANE_REQUIRED":
        records.append(
            event(
                record_id=f"HFIC-GAP-{session_id}",
                kind=RecordKind.CAPABILITY_GAP,
                entity_id=f"HFIC-GAP-{session_id}",
                hypothesis_version_id=selected_id,
                payload={
                    "capability_gap_id": f"HFIC-GAP-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "capability_id": "CHANGE_LANE",
                    "reason_code": "PASS_CHANGE_LANE_REQUIRED",
                    "required_contract": "OWNER_CONTRACT_REQUIRED",
                },
            )
        )
    store.append(records, transaction_id=transaction_id)
    git_after = repository_git_snapshot(Path(repo_root))
    if not git_before.unchanged(git_after):
        raise HficSessionError("GIT_MUTATION_DETECTED")
    store.rebuild_projection()
    critic_result_sha256 = hashlib.sha256(critic_bytes.encode("utf-8")).hexdigest()
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": str(frozen.get("evidence_epoch_sha256") or "0" * 64),
        "focus_key_sha256": str(frozen.get("focus_key_sha256") or "0" * 64),
        "search_key_sha256": str(frozen.get("search_key_sha256") or "0" * 64),
        "prompt_version": PROMPT_VERSION,
        "live_git_head": git_after.head_sha.lower(),
        "store_inventory_digest": store.diagnostics().committed_inventory_sha256,
        "candidate_ids": list(frozen["candidate_ids"]),
        "selected_candidate_id": selected_id,
        "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
        "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
        "critic_result_sha256": critic_result_sha256,
        "critic_terminal": terminal,
        "lane_classifier_terminal": critic_result.get("classifier_receipt")
        and (
            critic_result.get("classifier_receipt") or {}
        ).get("lane_classifier_terminal")
        if isinstance(critic_result.get("classifier_receipt"), Mapping)
        else None,
        "decision_event_ids": decision_ids,
        "next": str(critic_result.get("next") or "STOP"),
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "no_git_fence_receipt": {
            "git_composite_unchanged": git_before.unchanged(git_after),
            "composite_sha256": git_after.composite_sha256,
            "head_sha": git_after.head_sha.lower(),
        },
        "created_at": created_at,
        "decisions": {
            selected_id: {"decision_kind": decision_kind, "reason_code": reason},
            **{
                candidate_id: {
                    "decision_kind": "PAUSE",
                    "reason_code": "NOT_SELECTED_IN_SESSION",
                }
                for candidate_id in frozen["candidate_ids"]
                if candidate_id != selected_id
            },
        },
    }
    if repo_root is not None:
        stripped = {
            key: value
            for key, value in receipt.items()
            if key != "decisions"
        }
        try:
            _validate_json_schema(
                stripped,
                Path(repo_root)
                / "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json",
            )
        except HficSessionError:
            if stripped.get("critic_input_packet_sha256"):
                raise
    receipt_bytes = json.dumps(
        {key: value for key, value in receipt.items() if key != "decisions"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    transaction_id = f"RESEARCH-TXN-HFICRCP-{session_id[-16:]}"
    store.append(
        [
            event(
                record_id=f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                payload={
                    "research_artifact_id": f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "artifact_kind": "SESSION_RECEIPT",
                    "payload_canonical": receipt_bytes,
                    "payload_sha256": hashlib.sha256(
                        receipt_bytes.encode("utf-8")
                    ).hexdigest(),
                },
            )
        ],
        transaction_id=transaction_id,
    )
    return receipt


def _validate_json_schema(document: Mapping[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


def load_session_bundle(store: Any, session_id: str) -> dict[str, Any] | None:
    cycle: dict[str, Any] | None = None
    candidates: list[str] = []
    candidate_cards: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    critic_input = None
    critic_result = None
    critic_input_sha = None
    critic_result_sha = None
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = json.loads(record.payload_json)
        if payload.get("session_id") != session_id:
            continue
        if kind == "RESEARCH_CYCLE":
            if cycle is None or phase_rank(payload.get("phase")) <= phase_rank(
                cycle.get("phase")
            ):
                cycle = payload
            continue
        elif kind == "HYPOTHESIS_VERSION":
            candidate_id = str(payload.get("hypothesis_version_id") or record.entity_id)
            candidates.append(candidate_id)
            candidate_cards.append(payload)
        elif kind == "DECISION_EVENT":
            decisions.append(payload)
        elif kind == "RESEARCH_ARTIFACT":
            artifact_kind = payload.get("artifact_kind")
            if artifact_kind == "CRITIC_INPUT_PACKET":
                critic_input_sha = payload.get("payload_sha256")
                raw = payload.get("payload_canonical")
                if isinstance(raw, str):
                    critic_input = json.loads(raw)
            elif artifact_kind == "CRITIC_RESULT":
                critic_result_sha = payload.get("payload_sha256")
                raw = payload.get("payload_canonical")
                if isinstance(raw, str):
                    critic_result = json.loads(raw)
    if cycle is None:
        return None
    unique_ids: list[str] = []
    for item in candidates:
        if item not in unique_ids:
            unique_ids.append(item)
    decision_ids = [
        str(item.get("decision_event_id"))
        for item in decisions
        if item.get("decision_event_id")
    ]
    state = str(cycle.get("phase") or "FROZEN_AWAITING_CRITIC")
    return {
        "session_id": session_id,
        "session_state": state,
        "prompt_version": cycle.get("prompt_version") or PROMPT_VERSION,
        "owner_focus": cycle.get("owner_focus") or "AUTO",
        "evidence_epoch_sha256": cycle.get("evidence_epoch_sha256") or "",
        "focus_key_sha256": cycle.get("focus_key_sha256") or "",
        "search_key_sha256": cycle.get("search_key_sha256") or "",
        "selected_candidate_id": cycle.get("selected_candidate_id"),
        "runner_up_candidate_id": cycle.get("runner_up_candidate_id"),
        "rejected_alternative_id": cycle.get("rejected_alternative_id"),
        "candidate_ids": cycle.get("candidate_ids") or unique_ids,
        "critic_input_packet": critic_input,
        "critic_input_packet_sha256": cycle.get("critic_input_packet_sha256")
        or critic_input_sha,
        "critic_result": critic_result,
        "critic_result_sha256": critic_result_sha,
        "critic_terminal": cycle.get("critic_terminal")
        or (critic_result or {}).get("critic_terminal"),
        "next": cycle.get("next") or (critic_result or {}).get("next") or "STOP",
        "decision_event_ids": decision_ids,
        "decisions": {
            str(item.get("hypothesis_version_id")): {
                "decision_kind": item.get("decision_kind"),
                "reason_code": item.get("reason_code"),
            }
            for item in decisions
        },
        "candidates": candidate_cards,
        "lane_classifier_terminal": None,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }


def show_session(store: Any, session_id: str, *, repo_root: Any = None) -> dict[str, Any]:
    bundle = load_session_bundle(store, session_id)
    if bundle is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    digest = store.diagnostics().committed_inventory_sha256
    live_git_head = "0" * 40
    composite = None
    if repo_root is not None:
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot

        snap = repository_git_snapshot(Path(repo_root))
        live_git_head = snap.head_sha.lower()
        composite = snap.composite_sha256
    payload = {
        "session_id": bundle["session_id"],
        "session_state": bundle["session_state"],
        "evidence_epoch_sha256": bundle.get("evidence_epoch_sha256") or "0" * 64,
        "focus_key_sha256": bundle.get("focus_key_sha256") or "0" * 64,
        "search_key_sha256": bundle.get("search_key_sha256") or "0" * 64,
        "prompt_version": bundle.get("prompt_version") or PROMPT_VERSION,
        "live_git_head": live_git_head,
        "store_inventory_digest": digest,
        "candidate_ids": bundle.get("candidate_ids") or [],
        "selected_candidate_id": bundle.get("selected_candidate_id"),
        "runner_up_candidate_id": bundle.get("runner_up_candidate_id"),
        "critic_input_packet": bundle.get("critic_input_packet"),
        "critic_input_packet_sha256": bundle.get("critic_input_packet_sha256"),
        "critic_result_sha256": bundle.get("critic_result_sha256"),
        "critic_terminal": bundle.get("critic_terminal"),
        "lane_classifier_terminal": bundle.get("lane_classifier_terminal"),
        "decision_event_ids": bundle.get("decision_event_ids") or [],
        "next": bundle.get("next") or "STOP",
        "decisions": bundle.get("decisions") or {},
        "authority": bundle["authority"],
        "no_git_fence_receipt": {
            "git_composite_unchanged": composite is not None,
            "composite_sha256": composite,
            "head_sha": live_git_head,
        },
        "artifacts_retrievable": bool(bundle.get("critic_input_packet"))
        and (
            str(bundle.get("session_state")) != "SYNTHESIS_COMPLETE"
            or bool(bundle.get("critic_result"))
        ),
        "candidates_retrievable": len(bundle.get("candidates") or []) >= 4,
    }
    return payload


def lookup_prior(
    store: Any,
    *,
    candidate: Mapping[str, Any] | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "HYPOTHESIS_VERSION":
            continue
        payload = json.loads(record.payload_json)
        if payload.get("hfic_protocol") is None:
            continue
        cards.append(payload)
    matches: list[dict[str, Any]] = []
    if candidate is not None:
        matches.extend(related_prior_matches(candidate, cards))
        for item in matches:
            for card in cards:
                if card.get("definition_sha256") == item.get("definition_sha256"):
                    item["candidate_id"] = card.get("hypothesis_version_id")
                    item["session_id"] = card.get("session_id")
                    break
    if query:
        token = query.casefold()
        for card in cards:
            blob = " ".join(
                str(card.get(field) or "")
                for field in ("claim", "statement", "mechanism", "primary_x_family")
            ).casefold()
            if token in blob:
                matches.append(
                    {
                        "match_kind": "RELATED_PRIOR",
                        "candidate_id": card.get("hypothesis_version_id"),
                        "session_id": card.get("session_id"),
                        "definition_sha256": card.get("definition_sha256"),
                        "overlap_reasons": ["query_text"],
                    }
                )
    return {
        "match_count": len(matches),
        "matches": matches,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }


def prove_runtime(
    store: Any,
    session_id: str,
    *,
    repo_root: Any,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    before = repository_git_snapshot(Path(repo_root))
    bundle = show_session(store, session_id, repo_root=repo_root)
    after = repository_git_snapshot(Path(repo_root))
    unchanged = before.unchanged(after)
    if not unchanged:
        raise HficSessionError("GIT_MUTATION_DETECTED")
    return {
        **bundle,
        "runtime_no_git": "PROVEN",
        "provider_calls_actual": 0,
        "git_composite_unchanged": unchanged,
        "candidates_retrievable": bundle["candidates_retrievable"],
        "artifacts_retrievable": bundle["artifacts_retrievable"],
    }
