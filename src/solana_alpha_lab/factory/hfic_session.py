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
    "AWAITING_CLASSIFICATION": 1,
    "REVISED_AWAITING_CRITIC": 1,
    "REVISION_REQUIRED": 2,
    "CRITIC_RESULT_READY": 3,
    "FROZEN_AWAITING_CRITIC": 4,
    "DRAFT_VALIDATED": 5,
    "PREFLIGHT_PROVEN": 6,
}
PENDING_STATES = frozenset(
    {
        "PREFLIGHT_PROVEN",
        "DRAFT_VALIDATED",
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        "REVISION_REQUIRED",
        "AWAITING_CLASSIFICATION",
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
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
        "PASS_DATA_OPTION_REQUIRED",
        "OWNER_DECISION_REQUIRED",
    }
)
_FINAL_PASS_TERMINALS = frozenset(
    {
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
        "PASS_DATA_OPTION_REQUIRED",
    }
)
_CLASSIFIER_RECEIPT_SCHEMA = "smial.hfic-classifier-receipt"
_PLACEHOLDER_TIME = "1970-01-01T00:00:00Z"
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


def canonical_preflight_receipt_sha256(receipt: Mapping[str, Any]) -> str:
    body = {
        key: value
        for key, value in receipt.items()
        if key != "preflight_receipt_sha256"
    }
    return canonical_sha256(body)


def _nonempty_str_list(value: object, *, code: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise HficSessionError(code)
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise HficSessionError(code)
        items.append(item)
    return items


def _require_memory_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HficSessionError("RESEARCH_MEMORY_AS_OF_REQUIRED")
    text = value.strip()
    if text.startswith("1970-01-01"):
        raise HficSessionError("RESEARCH_MEMORY_AS_OF_PLACEHOLDER")
    if not text.startswith("20") or "T" not in text:
        raise HficSessionError("RESEARCH_MEMORY_AS_OF_REQUIRED")
    return text


def _authority_zero(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise HficSessionError("AUTHORITY_NONZERO")
    authority = {}
    for key in ("git_mutation", "experiment_execution", "provider_api_rpc_wss_calls"):
        raw = value.get(key)
        if raw is None or int(raw) != 0:
            raise HficSessionError("AUTHORITY_NONZERO")
        authority[key] = 0
    return authority


def bind_preflight_receipt(
    receipt: Mapping[str, Any],
    draft: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    require_current_store_digest: bool = True,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.commissioning_proof import (
        CommissioningProofError,
        prove_fast_lane_commissioned,
    )
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    if receipt.get("action") != "START_NEW_SESSION":
        raise HficSessionError("PREFLIGHT_ACTION_INVALID")
    if receipt.get("prompt_version") != PROMPT_VERSION:
        raise HficSessionError("PREFLIGHT_PROMPT_VERSION_INVALID")
    observed_hash = receipt.get("preflight_receipt_sha256")
    expected_hash = canonical_preflight_receipt_sha256(receipt)
    if observed_hash != expected_hash:
        raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    if draft.get("preflight_receipt_id") != receipt.get("receipt_id"):
        raise HficSessionError("PREFLIGHT_RECEIPT_ID_MISMATCH")
    if draft.get("preflight_receipt_sha256") != observed_hash:
        raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    _authority_zero(receipt.get("authority"))
    _authority_zero(draft.get("authority"))
    commissioning = receipt.get("commissioning")
    if not isinstance(commissioning, Mapping):
        raise HficSessionError("COMMISSIONING_PROOF_REQUIRED")
    if commissioning.get("status") != "NO_GIT_FAST_LANE_PROVEN":
        raise HficSessionError("COMMISSIONING_PROOF_REQUIRED")
    if int(commissioning.get("provider_calls_actual", -1)) != 0:
        raise HficSessionError("COMMISSIONING_PROVIDER_CALLS")
    if int(commissioning.get("git_mutation_count", -1)) != 0:
        raise HficSessionError("COMMISSIONING_GIT_MUTATION")
    data_root = Path(getattr(store, "_root"))
    try:
        proof = prove_fast_lane_commissioned(data_root)
    except CommissioningProofError as exc:
        raise HficSessionError(str(exc)) from exc
    if proof.get("run_id") != commissioning.get("run_id"):
        raise HficSessionError("COMMISSIONING_RUN_MISMATCH")
    digest = store.diagnostics().committed_inventory_sha256
    receipt_digest = receipt.get("store_inventory_digest") or receipt.get(
        "data_root_fingerprint_sha256"
    )
    if require_current_store_digest and receipt_digest != digest:
        raise HficSessionError("PREFLIGHT_STORE_DIGEST_MISMATCH")
    git = repository_git_snapshot(Path(repo_root))
    receipt_head = str(receipt.get("live_git_head") or "")
    if receipt_head != git.head_sha.lower():
        raise HficSessionError("PREFLIGHT_GIT_HEAD_MISMATCH")
    receipt_composite = receipt.get("git_composite_sha256")
    if receipt_composite != git.composite_sha256:
        raise HficSessionError("PREFLIGHT_GIT_COMPOSITE_MISMATCH")
    epoch = str(receipt.get("evidence_epoch_sha256") or "")
    focus_key = str(receipt.get("focus_key_sha256") or "")
    search_key = str(receipt.get("search_key_sha256") or "")
    if not epoch or not focus_key or not search_key:
        raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
    return {
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "owner_focus": str(receipt.get("owner_focus") or "AUTO"),
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "store_inventory_digest": digest,
        "research_memory_as_of": _require_memory_timestamp(
            receipt.get("research_memory_as_of")
        ),
        "commissioning_run_id": proof.get("run_id"),
        "provider_calls_actual": 0,
    }


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
    if repo_root is not None:
        _validate_json_schema(
            draft,
            Path(repo_root) / "catalog/schemas/hypothesis_forge_draft_v1.schema.json",
        )
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
    truth_roots = _nonempty_str_list(
        draft.get("truth_roots_used"),
        code="TRUTH_ROOTS_REQUIRED",
    )
    prior_work = _nonempty_str_list(
        draft.get("prior_work_receipts") or draft.get("prior_work_queries"),
        code="PRIOR_WORK_RECEIPTS_REQUIRED",
    )
    memory_as_of = _require_memory_timestamp(draft.get("research_memory_as_of"))
    bound: dict[str, Any] | None = None
    if store is not None:
        if repo_root is None or not isinstance(preflight_receipt, Mapping):
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        existing_before_bind = None
        epoch_hint = str(preflight_receipt.get("evidence_epoch_sha256") or "")
        focus_hint = str(preflight_receipt.get("focus_key_sha256") or "")
        if epoch_hint and focus_hint:
            existing_before_bind = find_session_by_epoch_focus(
                store, epoch_hint, focus_hint
            )
        bound = bind_preflight_receipt(
            preflight_receipt,
            draft,
            store=store,
            repo_root=repo_root,
            require_current_store_digest=existing_before_bind is None,
        )
        if bound["research_memory_as_of"] != memory_as_of:
            raise HficSessionError("RESEARCH_MEMORY_AS_OF_MISMATCH")
    git_head = "0" * 40
    if bound is not None:
        git_head = str(bound["live_git_head"])
    elif isinstance(preflight_receipt, Mapping):
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            git_head = maybe_head.lower()
    packet = {
        "packet_schema": "smial.hypothesis-critic-input",
        "packet_version": "1.1",
        "generator_prompt_version": PROMPT_VERSION,
        "generated_at": memory_as_of,
        "live_git_head": git_head,
        "research_memory_as_of": memory_as_of,
        "owner_focus": str(draft.get("owner_focus") or "AUTO"),
        "authority": _authority_zero(draft.get("authority")),
        "holdouts_not_touched": list(draft.get("holdouts_not_touched") or []),
        "truth_roots_used": truth_roots,
        "prior_work_queries": prior_work,
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
    git_composite = None
    if bound is not None:
        epoch = str(bound["evidence_epoch_sha256"])
        focus_key = str(bound["focus_key_sha256"])
        search_key = str(bound["search_key_sha256"])
        store_digest = bound["store_inventory_digest"]
        git_composite = bound["git_composite_sha256"]
        owner_focus = str(bound["owner_focus"])
    elif isinstance(preflight_receipt, Mapping):
        epoch = str(preflight_receipt.get("evidence_epoch_sha256") or "")
        focus_key = str(preflight_receipt.get("focus_key_sha256") or "")
        search_key = str(preflight_receipt.get("search_key_sha256") or "")
        digest = preflight_receipt.get("store_inventory_digest")
        if isinstance(digest, str) and len(digest) == 64:
            store_digest = digest
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            packet["live_git_head"] = maybe_head.lower()
        maybe_composite = preflight_receipt.get("git_composite_sha256")
        if isinstance(maybe_composite, str) and len(maybe_composite) == 64:
            git_composite = maybe_composite
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
        "selected_display_ordinal": selected.display_ordinal,
        "candidate_ids": [item.candidate_id for item in identities],
        "critic_input_packet": packet,
        "critic_input_packet_sha256": hashlib.sha256(
            packet_bytes.encode("utf-8")
        ).hexdigest(),
        "store_inventory_digest": store_digest,
        "git_composite_sha256": git_composite,
        "research_memory_as_of": memory_as_of,
        "revision_count": 0,
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
                "selected_definition_sha256": frozen.get("selected_definition_sha256"),
                "selected_display_ordinal": frozen.get("selected_display_ordinal"),
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": int(frozen.get("revision_count") or 0),
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
    receipt_ids: set[str] = set()
    critic_ids: set[str] = set()
    cycles: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = json.loads(record.payload_json)
        session_id = str(payload.get("session_id") or "")
        if kind == "RESEARCH_ARTIFACT" and payload.get("artifact_kind") == "SESSION_RECEIPT":
            if session_id:
                receipt_ids.add(session_id)
            continue
        if kind == "RESEARCH_ARTIFACT" and payload.get("artifact_kind") == "CRITIC_RESULT":
            if session_id:
                critic_ids.add(session_id)
            continue
        if kind != "RESEARCH_CYCLE":
            continue
        if payload.get("hfic_protocol") is None or not session_id:
            continue
        cycles.append(
            {
                "session_id": session_id,
                "session_state": payload.get("phase"),
                "evidence_epoch_sha256": payload.get("evidence_epoch_sha256"),
                "focus_key_sha256": payload.get("focus_key_sha256"),
                "search_key_sha256": payload.get("search_key_sha256"),
                "prompt_version": payload.get("prompt_version"),
                "owner_focus": payload.get("owner_focus"),
            }
        )
    latest: dict[str, dict[str, Any]] = {}
    for candidate in cycles:
        session_id = str(candidate["session_id"])
        phase = _effective_cycle_phase(
            candidate.get("session_state"),
            has_receipt=session_id in receipt_ids,
            has_critic=session_id in critic_ids,
        )
        candidate = {**candidate, "session_state": phase}
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
    expected_def = frozen.get("selected_definition_sha256")
    observed_def = critic_result.get("selected_definition_sha256")
    if (
        not isinstance(expected_def, str)
        or not isinstance(observed_def, str)
        or expected_def != observed_def
    ):
        raise HficSessionError("CRITIC_DEFINITION_HASH_MISMATCH")
    return selected_id


def _make_event_factory(repo_root: Any, git: Any, session_id: str, producer: str):
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = HFIC_EVENT_TIME

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
        transaction_id: str,
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

    return event


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _effective_cycle_phase(
    phase: object,
    *,
    has_receipt: bool,
    has_critic: bool,
) -> str:
    text = str(phase or "")
    if text == "SYNTHESIS_COMPLETE" and not has_receipt:
        return "CRITIC_RESULT_READY" if has_critic else "FROZEN_AWAITING_CRITIC"
    return text


def _classifier_to_hfic_terminal(receipt: Mapping[str, Any]) -> str:
    outcome = str(receipt.get("lane_classifier_terminal") or "")
    mapping = {
        "FAST_LANE_READY": "PASS_FAST_LANE_READY",
        "REPLAY_AVAILABLE": "PASS_FAST_LANE_READY",
        "BLOCKED_DATA": "PASS_DATA_OPTION_REQUIRED",
        "CHANGE_LANE_CAPABILITY_GAP": "PASS_CHANGE_LANE_REQUIRED",
        "FAST_LANE_OWNER_GATE_REQUIRED": "OWNER_DECISION_REQUIRED",
        "PROMOTION_LANE_REQUIRED": "OWNER_DECISION_REQUIRED",
        "DENY_INVALID_SPEC": "KILL_UNBOUND_EVIDENCE",
        "DENY_INTEGRITY_MISMATCH": "KILL_UNBOUND_EVIDENCE",
    }
    mapped = mapping.get(outcome)
    if mapped is None:
        raise HficSessionError("CLASSIFIER_TERMINAL_MISMATCH")
    return mapped


def build_classifier_receipt(
    *,
    frozen: Mapping[str, Any],
    decision: Any,
    spec_sha256: str,
) -> dict[str, Any]:
    lane = getattr(decision.lane, "value", str(decision.lane))
    return {
        "schema": _CLASSIFIER_RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "session_id": frozen["session_id"],
        "selected_candidate_id": frozen["selected_candidate_id"],
        "selected_definition_sha256": frozen["selected_definition_sha256"],
        "experiment_spec_sha256": spec_sha256,
        "lane": lane,
        "lane_classifier_terminal": decision.terminal,
        "reason_codes": list(decision.reason_codes),
        "next_action": decision.next_action,
        "provider_calls_actual": 0,
        "network_free": True,
    }


def run_live_classifier(
    critic_result: Mapping[str, Any],
    frozen: Mapping[str, Any],
    *,
    repo_root: Any,
    data_root: Any,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from solana_alpha_lab.factory.experiment_spec import (
        ExperimentSpecError,
        validate_experiment_document,
    )
    from solana_alpha_lab.factory.lane_classifier import classify_lane
    from solana_alpha_lab.factory.run_passport import experiment_spec_sha256

    submission = critic_result.get("experiment_spec_packet") or critic_result.get(
        "experiment_spec"
    )
    if isinstance(submission, Mapping) and "experiment_spec" not in submission:
        if submission.get("schema") == "smial.experiment-spec":
            submission = {
                "experiment_spec": dict(submission),
                "hypothesis_definition_sha256": frozen.get("selected_definition_sha256"),
            }
        else:
            submission = {
                "experiment_spec": dict(submission),
                "hypothesis_definition_sha256": frozen.get("selected_definition_sha256"),
            }
    if not isinstance(submission, Mapping) or "experiment_spec" not in submission:
        raise HficSessionError("EXPERIMENT_SPEC_REQUIRED")
    spec = submission["experiment_spec"]
    if not isinstance(spec, Mapping):
        raise HficSessionError("EXPERIMENT_SPEC_REQUIRED")
    try:
        validated = validate_experiment_document(dict(spec), root=Path(repo_root))
    except ExperimentSpecError as exc:
        raise HficSessionError("EXPERIMENT_SPEC_INVALID") from exc
    spec_sha = experiment_spec_sha256(validated)
    as_of_raw = str(validated.get("as_of") or frozen.get("research_memory_as_of") or "")
    if not as_of_raw:
        raise HficSessionError("EXPERIMENT_SPEC_INVALID")
    as_of = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00")).astimezone(UTC)
    packet = dict(submission)
    packet.setdefault("hypothesis_definition_sha256", frozen.get("selected_definition_sha256"))
    decision = classify_lane(
        packet,
        root=Path(repo_root),
        data_root=Path(data_root),
        as_of=as_of,
    )
    return build_classifier_receipt(
        frozen=frozen,
        decision=decision,
        spec_sha256=spec_sha,
    )


def validate_live_classifier_receipt(
    critic_result: Mapping[str, Any],
    frozen: Mapping[str, Any],
    *,
    repo_root: Any,
    data_root: Any,
) -> dict[str, Any]:
    observed = critic_result.get("classifier_receipt")
    if observed is not None and (
        not isinstance(observed, Mapping)
        or observed.get("schema") != _CLASSIFIER_RECEIPT_SCHEMA
    ):
        raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
    expected = run_live_classifier(
        critic_result,
        frozen,
        repo_root=repo_root,
        data_root=data_root,
    )
    if observed is None:
        return expected
    for key in (
        "schema",
        "session_id",
        "selected_candidate_id",
        "selected_definition_sha256",
        "experiment_spec_sha256",
        "lane",
        "lane_classifier_terminal",
        "network_free",
    ):
        if observed.get(key) != expected.get(key):
            raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
    if int(observed.get("provider_calls_actual", -1)) != 0:
        raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
    return expected


def persist_intermediate_cycle(
    store: Any,
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
    *,
    repo_root: Any,
    phase: str,
    extra_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    git = repository_git_snapshot(Path(repo_root))
    session_id = str(frozen["session_id"])
    transaction_id = f"RESEARCH-TXN-HFICINT-{session_id[-16:]}"
    event = _make_event_factory(
        repo_root, git, session_id, "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
    )
    critic_bytes = _canonical_bytes(critic_result)
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-{phase}",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-{phase}",
                "session_id": session_id,
                "phase": phase,
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "selected_candidate_id": frozen.get("selected_candidate_id"),
                "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
                "candidate_ids": list(frozen.get("candidate_ids") or []),
                "critic_terminal": critic_result.get("critic_terminal"),
                "next": str(critic_result.get("next") or "STOP"),
                "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
                "selected_definition_sha256": frozen.get("selected_definition_sha256"),
                "selected_display_ordinal": frozen.get("selected_display_ordinal"),
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": int(frozen.get("revision_count") or 0),
            },
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "CRITIC_RESULT",
                "payload_canonical": critic_bytes.decode("utf-8"),
                "payload_sha256": hashlib.sha256(critic_bytes).hexdigest(),
            },
            transaction_id=transaction_id,
        ),
    ]
    packet = frozen.get("critic_input_packet")
    if isinstance(packet, Mapping):
        packet_bytes = _canonical_bytes(packet)
        digest = hashlib.sha256(packet_bytes).hexdigest()
        records.append(
            event(
                record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                payload={
                    "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "artifact_kind": "CRITIC_INPUT_PACKET",
                    "payload_canonical": packet_bytes.decode("utf-8"),
                    "payload_sha256": digest,
                },
                transaction_id=transaction_id,
            )
        )
    for artifact in extra_artifacts or ():
        records.append(
            event(
                record_id=str(artifact["record_id"]),
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=str(artifact["record_id"]),
                payload=dict(artifact["payload"]),
                transaction_id=transaction_id,
            )
        )
    store.append(records, transaction_id=transaction_id)
    store.rebuild_projection()
    return {
        "session_id": session_id,
        "session_state": phase,
        "critic_terminal": critic_result.get("critic_terminal"),
        "next": str(critic_result.get("next") or "STOP"),
        "selected_candidate_id": frozen.get("selected_candidate_id"),
        "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }


def apply_revision(
    frozen: Mapping[str, Any],
    revised_draft: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
) -> dict[str, Any]:
    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    if existing.get("session_state") != "REVISION_REQUIRED":
        raise HficSessionError("REVISION_NOT_PENDING")
    if int(existing.get("revision_count") or 0) >= 1:
        raise HficSessionError("REVISION_BUDGET_EXHAUSTED")
    rebuilt = freeze_draft(revised_draft, preflight_receipt=None, store=None, repo_root=repo_root)
    original_ordinal = frozen.get("selected_display_ordinal")
    if original_ordinal is None:
        original_ordinal = existing.get("selected_display_ordinal")
    rebuilt_ordinal = rebuilt.get("selected_display_ordinal")
    if (
        original_ordinal is not None
        and rebuilt_ordinal is not None
        and original_ordinal != rebuilt_ordinal
    ):
        raise HficSessionError("REVISION_SELECTED_CHANGED")
    if original_ordinal is None and rebuilt["selected_candidate_id"] != frozen["selected_candidate_id"]:
        raise HficSessionError("REVISION_SELECTED_CHANGED")
    original_selected = {}
    packet_in = frozen.get("critic_input_packet")
    if isinstance(packet_in, Mapping):
        selected_card = packet_in.get("selected_candidate")
        if isinstance(selected_card, Mapping):
            original_selected = selected_card
    rebuilt_selected = rebuilt["critic_input_packet"]["selected_candidate"]
    from solana_alpha_lab.factory.hfic_identity import normalize_text

    for field in (
        "mechanism",
        "actor_counterparty",
        "population",
        "decision_timestamp",
        "primary_x",
        "primary_y",
        "horizon_notional",
    ):
        left = original_selected.get(field)
        right = rebuilt_selected.get(field)
        if not isinstance(left, str) or not isinstance(right, str):
            raise HficSessionError("REVISION_MECHANISM_CHANGED")
        if normalize_text(left) != normalize_text(right):
            raise HficSessionError("REVISION_MECHANISM_CHANGED")
    packet = rebuilt["critic_input_packet"]
    packet_bytes = _canonical_bytes(packet)
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    git = repository_git_snapshot(Path(repo_root))
    session_id = str(frozen["session_id"])
    transaction_id = f"RESEARCH-TXN-HFICREV-{session_id[-16:]}"
    event = _make_event_factory(
        repo_root, git, session_id, "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
    )
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-REVISED",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-REVISED",
                "session_id": session_id,
                "phase": "REVISED_AWAITING_CRITIC",
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "selected_candidate_id": rebuilt["selected_candidate_id"],
                "runner_up_candidate_id": rebuilt.get("runner_up_candidate_id"),
                "candidate_ids": list(rebuilt.get("candidate_ids") or []),
                "critic_input_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
                "selected_definition_sha256": rebuilt["selected_definition_sha256"],
                "selected_display_ordinal": rebuilt.get("selected_display_ordinal"),
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": 1,
            },
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "CRITIC_INPUT_PACKET",
                "payload_canonical": packet_bytes.decode("utf-8"),
                "payload_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            },
            transaction_id=transaction_id,
        ),
    ]
    store.append(records, transaction_id=transaction_id)
    store.rebuild_projection()
    updated = load_session_bundle(store, session_id)
    if updated is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    return updated


def apply_classification(
    frozen: Mapping[str, Any],
    experiment_spec_packet: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    data_root: Any,
) -> dict[str, Any]:
    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    if existing.get("session_state") != "AWAITING_CLASSIFICATION":
        raise HficSessionError("CLASSIFICATION_NOT_PENDING")
    critic_result = dict(existing.get("critic_result") or {})
    critic_result["experiment_spec_packet"] = dict(experiment_spec_packet)
    receipt = validate_live_classifier_receipt(
        critic_result,
        frozen,
        repo_root=repo_root,
        data_root=data_root,
    )
    terminal = _classifier_to_hfic_terminal(receipt)
    critic_result["classifier_receipt"] = receipt
    critic_result["critic_terminal"] = terminal
    critic_result["next"] = "PAUSE" if terminal in _PAUSE_TERMINALS else "STOP"
    return finalize_session(
        frozen,
        critic_result,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
    )


def finalize_session(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    data_root: Any = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    selected_id = _require_critic_identity(frozen, critic_result)
    if repo_root is not None:
        _validate_json_schema(
            critic_result,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_result_v1.schema.json",
        )
    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is not None and existing.get("session_state") == "SYNTHESIS_COMPLETE":
        existing_hash = existing.get("critic_result_sha256")
        retry_hash = hashlib.sha256(_canonical_bytes(critic_result)).hexdigest()
        if existing_hash not in {None, retry_hash}:
            raise HficSessionError("SESSION_CONFLICT")
        return existing
    terminal = str(critic_result.get("critic_terminal") or "")
    if terminal == "REVISE_ONCE":
        revision_count = int(frozen.get("revision_count") or 0)
        if existing is not None:
            revision_count = max(revision_count, int(existing.get("revision_count") or 0))
        if revision_count >= 1:
            raise HficSessionError("REVISION_BUDGET_EXHAUSTED")
        if not isinstance(critic_result.get("revision_receipt"), Mapping):
            raise HficSessionError("REVISION_RECEIPT_REQUIRED")
        return persist_intermediate_cycle(
            store,
            frozen,
            critic_result,
            repo_root=repo_root,
            phase="REVISION_REQUIRED",
        )
    if terminal == "PASS_TO_CLASSIFICATION":
        fake = critic_result.get("classifier_receipt")
        if fake:
            raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
        return persist_intermediate_cycle(
            store,
            frozen,
            critic_result,
            repo_root=repo_root,
            phase="AWAITING_CLASSIFICATION",
        )
    classifier_receipt = None
    if terminal in _FINAL_PASS_TERMINALS:
        root_for_data = data_root if data_root is not None else getattr(store, "_root")
        classifier_receipt = validate_live_classifier_receipt(
            critic_result,
            frozen,
            repo_root=repo_root,
            data_root=root_for_data,
        )
        critic_result = dict(critic_result)
        critic_result["classifier_receipt"] = classifier_receipt
        mapped = _classifier_to_hfic_terminal(classifier_receipt)
        if terminal != mapped:
            raise HficSessionError("CLASSIFIER_TERMINAL_MISMATCH")
    else:
        observed = critic_result.get("classifier_receipt")
        if isinstance(observed, Mapping) and observed.get("schema") == _CLASSIFIER_RECEIPT_SCHEMA:
            classifier_receipt = dict(observed)
    decision_kind, reason = map_critic_terminal_to_decision(terminal)
    git_before = repository_git_snapshot(Path(repo_root))
    session_id = str(frozen["session_id"])
    transaction_id = f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}"
    event = _make_event_factory(
        repo_root,
        git_before,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
    created_at = HFIC_EVENT_TIME.strftime("%Y-%m-%dT%H:%M:%SZ")
    decision_ids: list[str] = []
    records = [
        event(
            record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "CRITIC_RESULT",
                "payload_canonical": critic_bytes.decode("utf-8"),
                "payload_sha256": critic_result_sha256,
            },
            transaction_id=transaction_id,
        )
    ]
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
                transaction_id=transaction_id,
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
                transaction_id=transaction_id,
            )
        )
    if classifier_receipt is not None:
        classifier_bytes = _canonical_bytes(classifier_receipt)
        records.append(
            event(
                record_id=f"HFIC-ART-CLASSIFIER-{session_id}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-CLASSIFIER-{session_id}",
                payload={
                    "research_artifact_id": f"HFIC-ART-CLASSIFIER-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "artifact_kind": "CLASSIFIER_RECEIPT",
                    "payload_canonical": classifier_bytes.decode("utf-8"),
                    "payload_sha256": hashlib.sha256(classifier_bytes).hexdigest(),
                },
                transaction_id=transaction_id,
            )
        )
    git_after = repository_git_snapshot(Path(repo_root))
    if not git_before.unchanged(git_after):
        raise HficSessionError("GIT_MUTATION_DETECTED")
    preflight_composite = frozen.get("git_composite_sha256")
    if not isinstance(preflight_composite, str) or len(preflight_composite) != 64:
        raise HficSessionError("GIT_COMPOSITE_CHANGED")
    if preflight_composite != git_after.composite_sha256:
        raise HficSessionError("GIT_COMPOSITE_CHANGED")
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
        "lane_classifier_terminal": (
            classifier_receipt.get("lane_classifier_terminal")
            if classifier_receipt is not None
            else None
        ),
        "decision_event_ids": decision_ids,
        "next": str(critic_result.get("next") or "STOP"),
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "no_git_fence_receipt": {
            "preflight_git_composite_sha256": preflight_composite,
            "preflight_live_git_head": (
                frozen.get("live_git_head")
                or (
                    frozen.get("critic_input_packet", {}).get("live_git_head")
                    if isinstance(frozen.get("critic_input_packet"), Mapping)
                    else None
                )
            ),
            "final_git_composite_sha256": git_after.composite_sha256,
            "final_live_git_head": git_after.head_sha.lower(),
            "git_composite_unchanged": (
                isinstance(preflight_composite, str)
                and preflight_composite == git_after.composite_sha256
            ),
            "provider_calls_actual": 0,
        },
        "created_at": created_at,
    }
    if repo_root is not None:
        _validate_json_schema(
            receipt,
            Path(repo_root)
            / "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json",
        )
    receipt_bytes = _canonical_bytes(receipt)
    records.extend(
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
                    "payload_canonical": receipt_bytes.decode("utf-8"),
                    "payload_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                },
                transaction_id=transaction_id,
            ),
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
                    "critic_result_sha256": critic_result_sha256,
                    "session_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                    "selected_definition_sha256": frozen.get("selected_definition_sha256"),
                    "git_composite_sha256": git_after.composite_sha256,
                    "research_memory_as_of": frozen.get("research_memory_as_of"),
                    "revision_count": int(frozen.get("revision_count") or 0),
                },
                transaction_id=transaction_id,
            ),
        ]
    )
    store.append(records, transaction_id=transaction_id)
    store.rebuild_projection()
    receipt["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    receipt["decisions"] = {
        selected_id: {"decision_kind": decision_kind, "reason_code": reason},
        **{
            candidate_id: {
                "decision_kind": "PAUSE",
                "reason_code": "NOT_SELECTED_IN_SESSION",
            }
            for candidate_id in frozen["candidate_ids"]
            if candidate_id != selected_id
        },
    }
    return receipt


def _validate_json_schema(document: Mapping[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


def load_session_bundle(store: Any, session_id: str) -> dict[str, Any] | None:
    cycle: dict[str, Any] | None = None
    cycles: list[dict[str, Any]] = []
    candidates: list[str] = []
    candidate_cards: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    critic_input = None
    critic_result = None
    critic_input_sha = None
    critic_result_sha = None
    session_receipt = None
    classifier_receipt = None
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = json.loads(record.payload_json)
        if payload.get("session_id") != session_id:
            continue
        if kind == "RESEARCH_CYCLE":
            cycles.append(payload)
            continue
        elif kind == "HYPOTHESIS_VERSION":
            candidate_id = str(payload.get("hypothesis_version_id") or record.entity_id)
            candidates.append(candidate_id)
            candidate_cards.append(payload)
        elif kind == "DECISION_EVENT":
            decisions.append(payload)
        elif kind == "RESEARCH_ARTIFACT":
            artifact_kind = payload.get("artifact_kind")
            raw = payload.get("payload_canonical")
            expected_hash = payload.get("payload_sha256")
            if isinstance(raw, str) and isinstance(expected_hash, str):
                actual_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    raise HficSessionError("ARTIFACT_HASH_MISMATCH")
            if artifact_kind == "CRITIC_INPUT_PACKET":
                critic_input_sha = payload.get("payload_sha256")
                if isinstance(raw, str):
                    critic_input = json.loads(raw)
            elif artifact_kind == "CRITIC_RESULT":
                critic_result_sha = payload.get("payload_sha256")
                if isinstance(raw, str):
                    critic_result = json.loads(raw)
            elif artifact_kind == "SESSION_RECEIPT":
                if isinstance(raw, str):
                    session_receipt = json.loads(raw)
            elif artifact_kind == "CLASSIFIER_RECEIPT":
                if isinstance(raw, str):
                    classifier_receipt = json.loads(raw)
    has_receipt = isinstance(session_receipt, Mapping)
    has_critic = critic_result is not None
    for payload in cycles:
        effective = _effective_cycle_phase(
            payload.get("phase"),
            has_receipt=has_receipt,
            has_critic=has_critic,
        )
        ranked = {**payload, "phase": effective}
        if cycle is None or phase_rank(ranked.get("phase")) <= phase_rank(
            cycle.get("phase")
        ):
            cycle = ranked
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
    if state == "SYNTHESIS_COMPLETE" and not isinstance(session_receipt, Mapping):
        state = "CRITIC_RESULT_READY" if critic_result is not None else "FROZEN_AWAITING_CRITIC"
    if critic_input is not None and critic_input_sha:
        recomputed = hashlib.sha256(
            json.dumps(
                critic_input,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if recomputed != critic_input_sha:
            raise HficSessionError("CRITIC_INPUT_HASH_MISMATCH")
    if critic_result is not None and critic_result_sha:
        recomputed = hashlib.sha256(
            json.dumps(
                critic_result,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if recomputed != critic_result_sha:
            raise HficSessionError("CRITIC_RESULT_HASH_MISMATCH")
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
        "selected_definition_sha256": cycle.get("selected_definition_sha256"),
        "selected_display_ordinal": cycle.get("selected_display_ordinal"),
        "candidate_ids": cycle.get("candidate_ids") or unique_ids,
        "critic_input_packet": critic_input,
        "critic_input_packet_sha256": cycle.get("critic_input_packet_sha256")
        or critic_input_sha,
        "critic_result": critic_result,
        "critic_result_sha256": critic_result_sha,
        "session_receipt": session_receipt,
        "classifier_receipt": classifier_receipt,
        "revision_count": int(cycle.get("revision_count") or 0),
        "git_composite_sha256": cycle.get("git_composite_sha256"),
        "research_memory_as_of": cycle.get("research_memory_as_of"),
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
        "lane_classifier_terminal": (classifier_receipt or {}).get(
            "lane_classifier_terminal"
        )
        or (session_receipt or {}).get("lane_classifier_terminal"),
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
        "session_receipt": bundle.get("session_receipt"),
        "no_git_fence_receipt": (
            (bundle.get("session_receipt") or {}).get("no_git_fence_receipt")
            or {
                "preflight_git_composite_sha256": bundle.get("git_composite_sha256"),
                "final_git_composite_sha256": composite,
                "git_composite_unchanged": (
                    isinstance(bundle.get("git_composite_sha256"), str)
                    and bundle.get("git_composite_sha256") == composite
                ),
                "head_sha": live_git_head,
            }
        ),
        "artifacts_retrievable": bool(bundle.get("critic_input_packet"))
        and (
            str(bundle.get("session_state")) != "SYNTHESIS_COMPLETE"
            or (
                bool(bundle.get("critic_result"))
                and isinstance(bundle.get("session_receipt"), Mapping)
            )
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
    bundle = load_session_bundle(store, session_id)
    if bundle is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    receipt = bundle.get("session_receipt")
    if not isinstance(receipt, Mapping):
        raise HficSessionError("SESSION_RECEIPT_MISSING")
    if bundle.get("session_state") != "SYNTHESIS_COMPLETE":
        raise HficSessionError("SESSION_NOT_COMPLETE")
    shown = show_session(store, session_id, repo_root=repo_root)
    after = repository_git_snapshot(Path(repo_root))
    if not before.unchanged(after):
        raise HficSessionError("GIT_MUTATION_DETECTED")
    fence = receipt.get("no_git_fence_receipt")
    if not isinstance(fence, Mapping):
        raise HficSessionError("NO_GIT_FENCE_MISSING")
    preflight_composite = fence.get("preflight_git_composite_sha256")
    final_composite = fence.get("final_git_composite_sha256")
    if not isinstance(preflight_composite, str) or not isinstance(final_composite, str):
        raise HficSessionError("NO_GIT_FENCE_MISSING")
    if preflight_composite != final_composite:
        raise HficSessionError("GIT_COMPOSITE_CHANGED")
    if bundle.get("critic_input_packet") is None or bundle.get("critic_result") is None:
        raise HficSessionError("SESSION_ARTIFACT_MISSING")
    if not shown["artifacts_retrievable"] or not shown["candidates_retrievable"]:
        raise HficSessionError("SESSION_ARTIFACT_MISSING")
    provider_calls = int(fence.get("provider_calls_actual", -1))
    if provider_calls != 0:
        raise HficSessionError("PROVIDER_CALLS_NONZERO")
    return {
        **shown,
        "runtime_no_git": "PROVEN",
        "provider_calls_actual": provider_calls,
        "git_composite_unchanged": True,
        "candidates_retrievable": shown["candidates_retrievable"],
        "artifacts_retrievable": shown["artifacts_retrievable"],
    }
