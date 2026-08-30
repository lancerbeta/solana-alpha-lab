"""HFIC session validation, identity rewrite, budget and decision mapping."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    parse_hfic_timestamp,
    render_canonical_utc,
)
from solana_alpha_lab.factory.hfic_identity import (
    HficIdentityError,
    assign_portfolio_ids,
    canonical_candidate_definition,
    normalize_text,
)
from solana_alpha_lab.factory.hfic_suppression_semantics import (
    candidate_matches_hard_close,
    family_hard_close_terminals,
    ledger_from_receipt,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


_SCHEMA_VALIDATORS: dict[str, Draft202012Validator] = {}
PROMPT_VERSION = "HFIC-V1.1"
MIN_CANDIDATES = 4
MAX_CANDIDATES = 6
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
_CLOSED_FAMILY_MARKER_PREFIX = "CLOSED_FAMILY:"
_CLOSED_FAMILY_STEM_RE = re.compile(r"^(?:CLOSE|PARK)_(.+?)(?:_FAMILY)?$")
_FORBIDDEN_DECISION_TERMINALS = frozenset({"PROMOTE", "PROMOTION_LANE"})
_INTERMEDIATE_CRITIC_TERMINALS = frozenset({"REVISE_ONCE", "PASS_TO_CLASSIFICATION"})


class HficSessionError(ValueError):
    """Fail-closed HFIC session/protocol error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _wrap_clock_error(exc: HficClockError) -> HficSessionError:
    code = str(exc)
    if code == "HFIC_TIMESTAMP_MISSING":
        return HficSessionError("SESSION_STARTED_AT_REQUIRED")
    return HficSessionError(code)


def bound_session_started_at(receipt: Mapping[str, Any] | None) -> datetime:
    if not isinstance(receipt, Mapping):
        raise HficSessionError("SESSION_STARTED_AT_REQUIRED")
    try:
        return parse_hfic_timestamp(receipt.get("session_started_at"))
    except HficClockError as exc:
        raise _wrap_clock_error(exc) from exc


def _stage_datetime(clock: Clock | None) -> datetime:
    try:
        return capture_stage_time(clock)
    except HficClockError as exc:
        raise _wrap_clock_error(exc) from exc


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


def closed_family_terminals_from_receipt(receipt: Mapping[str, Any] | None) -> list[str]:
    return family_hard_close_terminals(ledger_from_receipt(receipt))


def _closed_family_stems(terminal: str) -> list[str]:
    match = _CLOSED_FAMILY_STEM_RE.fullmatch(terminal.strip())
    if match is None:
        return []
    stem = match.group(1)
    stems = [stem]
    parts = stem.split("_")
    if len(parts) >= 3:
        stems.append("_".join(parts[1:]))
    return stems


def _normalize_reopen_blob(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def candidate_reopens_closed_family(
    card: Mapping[str, Any],
    terminals: Sequence[str],
) -> str | None:
    blob = _normalize_reopen_blob(
        " ".join(
            str(card.get(key) or "")
            for key in ("primary_x_family", "claim", "mechanism")
        )
    )
    if not blob:
        return None
    for terminal in terminals:
        for stem in _closed_family_stems(terminal):
            compact = _normalize_reopen_blob(stem)
            if len(compact) < 12:
                continue
            if compact in blob:
                return terminal
    return None


def critic_known_unknowns_with_closed_families(terminals: Sequence[str]) -> list[str]:
    markers = [f"{_CLOSED_FAMILY_MARKER_PREFIX}{terminal}" for terminal in terminals]
    return ["HFIC_FREEZE_BOUNDED", *markers]


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
    if "git_mutation_count" not in commissioning:
        raise HficSessionError("COMMISSIONING_GIT_MUTATION_COUNT_MISSING")
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
    started = bound_session_started_at(receipt)
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
        "session_started_at": render_canonical_utc(started),
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
    next_action_draft: Mapping[str, Any] | None = None,
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

    selected_ref = draft.get("selected_candidate_ref")
    if selected_ref in (None, ""):
        return _freeze_no_worthy(
            draft,
            identities=identities,
            preflight_receipt=preflight_receipt,
            store=store,
            repo_root=repo_root,
            next_action_draft=next_action_draft,
        )

    if next_action_draft is not None:
        raise HficSessionError("HFIC_NEXT_ACTION_FORBIDDEN_FOR_SELECTED")

    selected_index = _resolve_ref(selected_ref, identities)
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
    closed_family_ledger = ledger_from_receipt(
        preflight_receipt if isinstance(preflight_receipt, Mapping) else None
    )
    if store is not None and closed_family_ledger:
        for card in candidates:
            hit = candidate_matches_hard_close(card, closed_family_ledger)
            if hit is not None:
                raise HficSessionError("CLOSED_FAMILY_REOPEN")
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
        _validate_draft_forge_context_binding(draft, preflight_receipt, bound)
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
        "known_unknowns": critic_known_unknowns_with_closed_families(
            family_hard_close_terminals(closed_family_ledger)
        ),
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
    _bind_packet_session_id(packet, session_id)
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
        "forge_context_packet_sha256": (
            preflight_receipt.get("forge_context_packet_sha256")
            if isinstance(preflight_receipt, Mapping)
            else None
        ),
        "session_started_at": (
            bound.get("session_started_at")
            if bound is not None
            else (
                preflight_receipt.get("session_started_at")
                if isinstance(preflight_receipt, Mapping)
                else None
            )
        ),
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
            stage_time=bound_session_started_at(preflight_receipt),
        )
        store.rebuild_projection()
        result["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    result.pop("identities", None)
    return result


def _freeze_no_worthy(
    draft: Mapping[str, Any],
    *,
    identities: Sequence[Any],
    preflight_receipt: Mapping[str, Any] | None,
    store: Any,
    repo_root: Any,
    next_action_draft: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runner_up_index = _resolve_ref(draft.get("runner_up_candidate_ref"), identities)
    if runner_up_index < 0:
        raise HficSessionError("CROSS_REFERENCE_MISMATCH")
    rejected_index = _resolve_ref(
        draft.get("strongest_rejected_alternative"),
        identities,
    )
    if rejected_index < 0:
        raise HficSessionError("CROSS_REFERENCE_MISMATCH")
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
        _validate_draft_forge_context_binding(draft, preflight_receipt, bound)
        if existing_before_bind is not None:
            return existing_before_bind
    owner_focus = str(draft.get("owner_focus") or "AUTO")
    epoch = ""
    focus_key = ""
    search_key = ""
    store_digest = None
    git_composite = None
    git_head = "0" * 40
    if bound is not None:
        epoch = str(bound["evidence_epoch_sha256"])
        focus_key = str(bound["focus_key_sha256"])
        search_key = str(bound["search_key_sha256"])
        store_digest = bound["store_inventory_digest"]
        git_composite = bound["git_composite_sha256"]
        owner_focus = str(bound["owner_focus"])
        git_head = str(bound["live_git_head"])
    elif isinstance(preflight_receipt, Mapping):
        epoch = str(preflight_receipt.get("evidence_epoch_sha256") or "")
        focus_key = str(preflight_receipt.get("focus_key_sha256") or "")
        search_key = str(preflight_receipt.get("search_key_sha256") or "")
        digest = preflight_receipt.get("store_inventory_digest")
        if isinstance(digest, str) and len(digest) == 64:
            store_digest = digest
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            git_head = maybe_head.lower()
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
                "selected": None,
                "prompt_version": PROMPT_VERSION,
                "terminal": "NO_WORTHY_HYPOTHESIS",
            }
        )[:16].upper()
    packet_digest = None
    if isinstance(preflight_receipt, Mapping):
        digest = preflight_receipt.get("forge_context_packet_sha256")
        if isinstance(digest, str) and len(digest) == 64:
            packet_digest = digest
        packet = preflight_receipt.get("forge_context_packet")
        if packet_digest is None and isinstance(packet, Mapping):
            packet_digest = packet.get("forge_context_packet_sha256")
            if not isinstance(packet_digest, str):
                packet_digest = canonical_sha256(packet)
    result = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "prompt_version": PROMPT_VERSION,
        "owner_focus": owner_focus,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "selected_candidate_id": None,
        "runner_up_candidate_id": identities[runner_up_index].candidate_id,
        "rejected_alternative_id": identities[rejected_index].candidate_id,
        "selected_definition_sha256": None,
        "candidate_ids": [item.candidate_id for item in identities],
        "critic_input_packet": None,
        "critic_input_packet_sha256": None,
        "critic_launched": False,
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "next": "STOP",
        "next_action": None,
        "next_action_status": None,
        "forge_context_packet_sha256": packet_digest,
        "store_inventory_digest": store_digest,
        "git_composite_sha256": git_composite,
        "live_git_head": git_head,
        "research_memory_as_of": memory_as_of,
        "revision_count": 0,
        "session_started_at": (
            bound.get("session_started_at")
            if bound is not None
            else (
                preflight_receipt.get("session_started_at")
                if isinstance(preflight_receipt, Mapping)
                else None
            )
        ),
        "truth_roots_used": truth_roots,
        "prior_work_receipts": prior_work,
    }
    if store is not None and repo_root is not None:
        if not epoch or not search_key or not focus_key:
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        persist_no_worthy_session(
            store,
            result,
            repo_root=repo_root,
            identities=identities,
            draft=draft,
            preflight_receipt=preflight_receipt,
            next_action_draft=next_action_draft,
            stage_time=bound_session_started_at(preflight_receipt),
        )
        store.rebuild_projection()
        result["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    elif repo_root is not None:
        action = bind_next_epistemic_action(
            next_action_draft,
            frozen_no_worthy=result,
            identities=identities,
            repo_root=Path(repo_root),
        )
        result["next"] = action["action_type"]
        result["next_action"] = action
        result["next_action_id"] = action["action_id"]
        result["next_action_type"] = action["action_type"]
        result["next_action_status"] = "RECORDED"
    return result


def bind_next_epistemic_action(
    draft: Mapping[str, Any] | None,
    *,
    frozen_no_worthy: Mapping[str, Any],
    identities: Sequence[Any],
    repo_root: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_prospects import (
        HficProspectError,
        query_prospects,
        validate_next_action_draft,
        validate_stored_next_action,
    )

    if frozen_no_worthy.get("critic_terminal") != "NO_WORTHY_HYPOTHESIS":
        raise HficSessionError("HFIC_NEXT_ACTION_FORBIDDEN_FOR_SELECTED")
    if frozen_no_worthy.get("selected_candidate_id") not in (None, ""):
        raise HficSessionError("HFIC_NEXT_ACTION_FORBIDDEN_FOR_SELECTED")
    session_id = str(frozen_no_worthy.get("session_id") or "")
    epoch = str(frozen_no_worthy.get("evidence_epoch_sha256") or "")
    focus_key = str(frozen_no_worthy.get("focus_key_sha256") or "")
    search_key = str(frozen_no_worthy.get("search_key_sha256") or "")
    context_digest = frozen_no_worthy.get("forge_context_packet_sha256")
    if (
        not session_id
        or len(epoch) != 64
        or len(focus_key) != 64
        or len(search_key) != 64
        or not isinstance(context_digest, str)
        or len(context_digest) != 64
    ):
        raise HficSessionError("HFIC_NEXT_ACTION_CONTEXT_MISMATCH")
    candidate_ids = [item.candidate_id for item in identities]
    known_candidates = set(candidate_ids)
    try:
        visible = query_prospects(
            Path(repo_root),
            trigger="POST_NO_WORTHY_REVIEW",
            max_results=3,
        )
    except HficProspectError as exc:
        raise HficSessionError(str(exc)) from exc
    known_prospects = {
        str(item.get("prospect_id") or "")
        for item in visible.get("records") or []
    }
    generation_mode = "MODEL_VALIDATED"
    source_draft: Mapping[str, Any]
    if draft is None:
        generation_mode = "DETERMINISTIC_SAFE_FALLBACK"
        source_draft = {
            "packet_schema": "smial.hfic-next-epistemic-action-draft",
            "packet_version": "1.0",
            "prompt_version": "HFIC-NEXT-V1.0",
            "action_type": "WAIT_FOR_NEW_EVIDENCE",
            "reason_code": "NEXT_ACTION_GENERATION_FALLBACK",
            "named_consumer": "HFIC-POST-NO-WORTHY-ROUTER",
            "basis_candidate_refs": [],
            "prospect_ids": [],
            "evidence_gap": "No validated next-action draft was supplied after NO_WORTHY_HYPOTHESIS.",
            "why_now": "Deterministic safe wait preserves replay identity without inventing a spend or capability atom.",
            "why_cheaper_option_is_insufficient": "WAIT is the cheapest honest option when the draft is missing or unrepaired.",
            "action_payload": {"wake_on": ["EVIDENCE_EPOCH_CHANGED"]},
            "owner_gate": {"required": False, "phrase_status": "NONE"},
            "authority": {
                "git_mutation": 0,
                "rdp_mutation_outside_freeze": 0,
                "experiment_execution": 0,
                "provider_api_rpc_wss_calls": 0,
                "credential_reads": 0,
                "cash_spend_usd_cents": 0,
                "wallet_signer_transaction_actions": 0,
            },
            "non_claims": [
                "NO_ALPHA",
                "NO_AUTONOMOUS_GENERATOR",
                "NO_DISCOVERY_RANKER_TRIGGER_PROVEN",
                "NO_ARCH_INTENT_006_FULL_IMPLEMENTATION",
                "NO_QUALITY_DIVERSITY_ENGINE",
                "NO_VOI_SCHEDULER",
                "NO_SEQUENTIAL_INFERENCE_ENGINE",
                "NO_PROVIDER_OR_EXPERIMENT_AUTHORITY",
            ],
        }
    else:
        source_draft = draft
    try:
        validated = validate_next_action_draft(
            source_draft,
            repo_root=Path(repo_root),
            known_candidate_ids=None,
            known_prospect_ids=known_prospects,
        )
    except HficProspectError as exc:
        raise HficSessionError(str(exc)) from exc
    resolved_refs: list[str] = []
    for ref in validated.get("basis_candidate_refs") or []:
        index = _resolve_ref(ref, identities)
        if index < 0:
            raise HficSessionError("HFIC_NEXT_ACTION_INVALID")
        resolved_refs.append(identities[index].candidate_id)
    if any(ref not in known_candidates for ref in resolved_refs):
        raise HficSessionError("HFIC_NEXT_ACTION_INVALID")
    if created_at:
        timestamp = created_at
    else:
        started = frozen_no_worthy.get("session_started_at")
        timestamp = (
            started.strip()
            if isinstance(started, str) and started.strip()
            else render_canonical_utc(_stage_datetime(None))
        )
    binding_basis = {
        "session_id": session_id,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "forge_context_packet_sha256": context_digest,
        "candidate_ids": candidate_ids,
        "source_terminal": "NO_WORTHY_HYPOTHESIS",
        "generation_mode": generation_mode,
        "action_type": validated["action_type"],
        "reason_code": validated["reason_code"],
        "named_consumer": validated["named_consumer"],
        "basis_candidate_refs": resolved_refs,
        "prospect_ids": list(validated.get("prospect_ids") or []),
        "evidence_gap": validated["evidence_gap"],
        "why_now": validated["why_now"],
        "why_cheaper_option_is_insufficient": validated["why_cheaper_option_is_insufficient"],
        "action_payload": validated["action_payload"],
        "owner_gate": validated["owner_gate"],
        "authority": validated["authority"],
        "non_claims": validated["non_claims"],
        "prompt_version": validated["prompt_version"],
    }
    action_id = "HFIC-NEXT-" + canonical_sha256(binding_basis)[:16].upper()
    stored = {
        "packet_schema": "smial.hfic-next-epistemic-action",
        "packet_version": "1.0",
        "prompt_version": "HFIC-NEXT-V1.0",
        "hfic_protocol": PROMPT_VERSION,
        "action_id": action_id,
        "session_id": session_id,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "forge_context_packet_sha256": context_digest,
        "candidate_ids": candidate_ids,
        "source_terminal": "NO_WORTHY_HYPOTHESIS",
        "generation_mode": generation_mode,
        "created_at": timestamp,
        "action_type": validated["action_type"],
        "reason_code": validated["reason_code"],
        "named_consumer": validated["named_consumer"],
        "basis_candidate_refs": resolved_refs,
        "prospect_ids": list(validated.get("prospect_ids") or []),
        "evidence_gap": validated["evidence_gap"],
        "why_now": validated["why_now"],
        "why_cheaper_option_is_insufficient": validated["why_cheaper_option_is_insufficient"],
        "action_payload": validated["action_payload"],
        "owner_gate": validated["owner_gate"],
        "authority": validated["authority"],
        "non_claims": validated["non_claims"],
    }
    try:
        return validate_stored_next_action(stored, repo_root=Path(repo_root))
    except HficProspectError as exc:
        raise HficSessionError(str(exc)) from exc


def persist_no_worthy_session(
    store: Any,
    frozen: Mapping[str, Any],
    *,
    repo_root: Any,
    identities: Sequence[Any],
    draft: Mapping[str, Any] | None = None,
    preflight_receipt: Mapping[str, Any] | None = None,
    next_action_draft: Mapping[str, Any] | None = None,
    stage_time: datetime | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    if existing is not None:
        action = existing.get("next_action")
        if isinstance(action, Mapping):
            return dict(action)
        receipt = existing.get("session_receipt")
        referenced = isinstance(receipt, Mapping) and receipt.get(
            "next_action_artifact_sha256"
        )
        if referenced:
            raise HficSessionError("HFIC_NEXT_ACTION_ARTIFACT_MISSING")
        return {"action_type": str(existing.get("next") or "STOP")}
    git = repository_git_snapshot(Path(repo_root))
    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else bound_session_started_at(preflight_receipt)
    )
    transaction_id = f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFICNW-')}"
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

    context_digest = frozen.get("forge_context_packet_sha256")
    context_bytes = None
    if isinstance(preflight_receipt, Mapping):
        packet = preflight_receipt.get("forge_context_packet")
        if isinstance(packet, Mapping):
            context_bytes = _canonical_bytes(packet)
            if not isinstance(context_digest, str) or len(context_digest) != 64:
                context_digest = hashlib.sha256(context_bytes).hexdigest()
    created_at = render_canonical_utc(now)
    started_at = str(frozen.get("session_started_at") or created_at)
    if not isinstance(context_digest, str) or len(context_digest) != 64:
        raise HficSessionError("HFIC_NEXT_ACTION_CONTEXT_MISMATCH")
    bind_input = {
        **dict(frozen),
        "forge_context_packet_sha256": context_digest,
        "session_started_at": started_at,
    }
    action = bind_next_epistemic_action(
        next_action_draft,
        frozen_no_worthy=bind_input,
        identities=identities,
        repo_root=Path(repo_root),
        created_at=created_at,
    )
    action_bytes = _canonical_bytes(action)
    action_sha = hashlib.sha256(action_bytes).hexdigest()
    receipt = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": str(frozen.get("evidence_epoch_sha256") or "0" * 64),
        "focus_key_sha256": str(frozen.get("focus_key_sha256") or "0" * 64),
        "search_key_sha256": str(frozen.get("search_key_sha256") or "0" * 64),
        "prompt_version": PROMPT_VERSION,
        "live_git_head": str(frozen.get("live_git_head") or git.head_sha.lower()),
        "store_inventory_digest": frozen.get("store_inventory_digest") or ("0" * 64),
        "candidate_ids": list(frozen.get("candidate_ids") or []),
        "selected_candidate_id": None,
        "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
        "critic_input_packet_sha256": None,
        "critic_result_sha256": None,
        "critic_launched": False,
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "lane_classifier_terminal": None,
        "decision_event_ids": [f"HFIC-DEC-{session_id}-NO-WORTHY"],
        "next": action["action_type"],
        "next_action_artifact_sha256": action_sha,
        "next_action_type": action["action_type"],
        "forge_context_packet_sha256": context_digest,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "no_git_fence_receipt": {
            "preflight_git_composite_sha256": frozen.get("git_composite_sha256"),
            "final_git_composite_sha256": git.composite_sha256,
            "provider_calls_actual": 0,
        },
        "created_at": created_at,
        "session_started_at": started_at,
    }
    if repo_root is not None:
        _validate_json_schema(
            receipt,
            Path(repo_root)
            / "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json",
        )
    receipt_bytes = _canonical_bytes(receipt)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-NO-WORTHY",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-NO-WORTHY",
                "session_id": session_id,
                "phase": "SYNTHESIS_COMPLETE",
                "hfic_protocol": PROMPT_VERSION,
                "prompt_version": PROMPT_VERSION,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "selected_candidate_id": None,
                "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
                "rejected_alternative_id": frozen.get("rejected_alternative_id"),
                "candidate_ids": list(frozen.get("candidate_ids") or []),
                "critic_launched": False,
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "next": action["action_type"],
                "next_action_artifact_sha256": action_sha,
                "critic_input_packet_sha256": None,
                "critic_result_sha256": None,
                "session_receipt_sha256": receipt_sha,
                "forge_context_packet_sha256": context_digest,
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": 0,
            },
        ),
        event(
            record_id=f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}",
            payload={
                "research_artifact_id": f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "NEXT_EPISTEMIC_ACTION",
                "payload_canonical": action_bytes.decode("utf-8"),
                "payload_sha256": action_sha,
            },
        ),
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
                "payload_sha256": receipt_sha,
            },
        ),
        event(
            record_id=f"HFIC-DEC-{session_id}-NO-WORTHY",
            kind=RecordKind.DECISION_EVENT,
            entity_id=f"HFIC-DEC-{session_id}-NO-WORTHY",
            payload={
                "decision_event_id": f"HFIC-DEC-{session_id}-NO-WORTHY",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "decision_kind": "REJECT",
                "reason_code": "NO_WORTHY_HYPOTHESIS",
                "hypothesis_version_id": None,
            },
        ),
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
                    "role_in_session": "CONSIDERED_UNSELECTED",
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
    if isinstance(frozen, dict):
        frozen["next"] = action["action_type"]
        frozen["next_action"] = action
        frozen["next_action_id"] = action["action_id"]
        frozen["next_action_type"] = action["action_type"]
        frozen["next_action_status"] = "RECORDED"
        frozen["forge_context_packet_sha256"] = context_digest
    return action


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
    stage_time: datetime | None = None,
) -> None:
    """Append freeze records to an existing ResearchStore. Optional for unit tests."""

    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    if existing is not None:
        return
    git = repository_git_snapshot(Path(repo_root))
    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else bound_session_started_at(frozen)
    )
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
                "forge_context_packet_sha256": frozen.get("forge_context_packet_sha256"),
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
    clock: Clock | None = None,
) -> None:
    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    git = repository_git_snapshot(Path(repo_root))
    now = _stage_datetime(clock)
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


def _make_event_factory(
    repo_root: Any,
    git: Any,
    session_id: str,
    producer: str,
    stage_time: datetime,
):
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = stage_time

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


def _canonical_json_hash(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(document)).hexdigest()


def _bind_packet_session_id(packet: dict[str, Any], session_id: str) -> None:
    existing = packet.get("session_id")
    if existing not in (None, "", session_id):
        raise HficSessionError("CRITIC_SESSION_MISMATCH")
    packet["session_id"] = session_id


def _validate_draft_forge_context_binding(
    draft: Mapping[str, Any],
    receipt: Mapping[str, Any],
    bound: Mapping[str, Any],
) -> None:
    forge = receipt.get("forge_context_packet")
    if not isinstance(forge, Mapping):
        raise HficSessionError("FORGE_CONTEXT_REQUIRED")
    draft_roots = _nonempty_str_list(
        draft.get("truth_roots_used"),
        code="TRUTH_ROOTS_REQUIRED",
    )
    forge_roots = _nonempty_str_list(
        forge.get("truth_roots_used"),
        code="FORGE_CONTEXT_REQUIRED",
    )
    if draft_roots != forge_roots:
        raise HficSessionError("TRUTH_ROOTS_MISMATCH")
    draft_prior = _nonempty_str_list(
        draft.get("prior_work_receipts") or draft.get("prior_work_queries"),
        code="PRIOR_WORK_RECEIPTS_REQUIRED",
    )
    forge_prior = _nonempty_str_list(
        forge.get("prior_work_receipts"),
        code="FORGE_CONTEXT_REQUIRED",
    )
    if draft_prior != forge_prior:
        raise HficSessionError("PRIOR_WORK_MISMATCH")
    draft_focus = str(draft.get("owner_focus") or "AUTO")
    if draft_focus != str(bound.get("owner_focus") or forge.get("owner_focus") or "AUTO"):
        raise HficSessionError("FOCUS_CONTEXT_DRIFT")
    forge_memory = forge.get("research_memory_as_of")
    if isinstance(forge_memory, str) and forge_memory.strip():
        if _require_memory_timestamp(draft.get("research_memory_as_of")) != forge_memory.strip():
            raise HficSessionError("RESEARCH_MEMORY_AS_OF_MISMATCH")
    forge_epoch = str(forge.get("evidence_epoch_sha256") or "")
    if forge_epoch and forge_epoch != str(bound.get("evidence_epoch_sha256") or ""):
        raise HficSessionError("EVIDENCE_EPOCH_DRIFT")
    forge_search = str(forge.get("search_key_sha256") or "")
    if forge_search and forge_search != str(bound.get("search_key_sha256") or ""):
        raise HficSessionError("SEARCH_KEY_DRIFT")


def _validate_revision_context_lock(
    existing: Mapping[str, Any],
    revised_draft: Mapping[str, Any],
) -> None:
    memory_as_of = _require_memory_timestamp(revised_draft.get("research_memory_as_of"))
    if memory_as_of != str(existing.get("research_memory_as_of") or ""):
        raise HficSessionError("RESEARCH_MEMORY_AS_OF_MISMATCH")
    draft_focus = str(revised_draft.get("owner_focus") or "AUTO")
    if draft_focus != str(existing.get("owner_focus") or "AUTO"):
        raise HficSessionError("FOCUS_CONTEXT_DRIFT")
    for key, code in (
        ("evidence_epoch_sha256", "EVIDENCE_EPOCH_DRIFT"),
        ("focus_key_sha256", "FOCUS_KEY_DRIFT"),
        ("search_key_sha256", "SEARCH_KEY_DRIFT"),
    ):
        left = str(existing.get(key) or "")
        right = str(revised_draft.get(key) or left)
        if right and left and right != left:
            raise HficSessionError(code)
    packet = existing.get("critic_input_packet")
    if not isinstance(packet, Mapping):
        raise HficSessionError("CRITIC_INPUT_ARTIFACT_MISSING")
    draft_roots = _nonempty_str_list(
        revised_draft.get("truth_roots_used"),
        code="TRUTH_ROOTS_REQUIRED",
    )
    packet_roots = _nonempty_str_list(
        packet.get("truth_roots_used"),
        code="CRITIC_INPUT_ARTIFACT_MISSING",
    )
    if draft_roots != packet_roots:
        raise HficSessionError("TRUTH_ROOTS_MISMATCH")
    draft_prior = _nonempty_str_list(
        revised_draft.get("prior_work_receipts") or revised_draft.get("prior_work_queries"),
        code="PRIOR_WORK_RECEIPTS_REQUIRED",
    )
    packet_prior = _nonempty_str_list(
        packet.get("prior_work_queries"),
        code="CRITIC_INPUT_ARTIFACT_MISSING",
    )
    if draft_prior != packet_prior:
        raise HficSessionError("PRIOR_WORK_MISMATCH")


def _artifact_missing_code(artifact_kind: str) -> str:
    mapping = {
        "CRITIC_INPUT_PACKET": "CRITIC_INPUT_ARTIFACT_MISSING",
        "CRITIC_RESULT": "CRITIC_RESULT_ARTIFACT_MISSING",
        "SESSION_RECEIPT": "SESSION_RECEIPT_MISSING",
        "NEXT_EPISTEMIC_ACTION": "HFIC_NEXT_ACTION_ARTIFACT_MISSING",
    }
    return mapping.get(artifact_kind, "SESSION_ARTIFACT_MISSING")


def _load_artifact_by_sha(
    artifacts: Sequence[tuple[dict[str, Any], str | None]],
    *,
    artifact_kind: str,
    expected_sha: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    missing = _artifact_missing_code(artifact_kind)
    matches: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for wrapper, raw in artifacts:
        if wrapper.get("artifact_kind") != artifact_kind:
            continue
        observed_sha = str(wrapper.get("payload_sha256") or "")
        if observed_sha != expected_sha:
            continue
        if not isinstance(raw, str):
            raise HficSessionError(missing)
        actual_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if actual_hash != expected_sha:
            raise HficSessionError(
                "HFIC_NEXT_ACTION_ARTIFACT_HASH_MISMATCH"
                if artifact_kind == "NEXT_EPISTEMIC_ACTION"
                else "ARTIFACT_HASH_MISMATCH"
            )
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise HficSessionError(missing)
        recomputed = _canonical_json_hash(parsed)
        if recomputed != expected_sha:
            hash_code = (
                "HFIC_NEXT_ACTION_ARTIFACT_HASH_MISMATCH"
                if artifact_kind == "NEXT_EPISTEMIC_ACTION"
                else (
                    "CRITIC_INPUT_HASH_MISMATCH"
                    if artifact_kind == "CRITIC_INPUT_PACKET"
                    else (
                        "CRITIC_RESULT_HASH_MISMATCH"
                        if artifact_kind == "CRITIC_RESULT"
                        else "SESSION_RECEIPT_HASH_MISMATCH"
                    )
                )
            )
            raise HficSessionError(hash_code)
        matches.append((wrapper, parsed, expected_sha))
    if not matches:
        raise HficSessionError(missing)
    return matches[0]


def _verify_complete_hash_chain(
    cycle: Mapping[str, Any],
    *,
    session_receipt: Mapping[str, Any],
    critic_input_sha: str,
    critic_result_sha: str,
    receipt_sha: str,
) -> None:
    cycle_input = str(cycle.get("critic_input_packet_sha256") or "")
    cycle_result = str(cycle.get("critic_result_sha256") or "")
    cycle_receipt = str(cycle.get("session_receipt_sha256") or "")
    receipt_input = str(session_receipt.get("critic_input_packet_sha256") or "")
    receipt_result = str(session_receipt.get("critic_result_sha256") or "")
    if not cycle_input or cycle_input != critic_input_sha:
        raise HficSessionError("CRITIC_INPUT_HASH_MISMATCH")
    if not cycle_result or cycle_result != critic_result_sha:
        raise HficSessionError("CRITIC_RESULT_HASH_MISMATCH")
    if not cycle_receipt or cycle_receipt != receipt_sha:
        raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
    if receipt_input != critic_input_sha:
        raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
    if receipt_result != critic_result_sha:
        raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
    for key in (
        "evidence_epoch_sha256",
        "focus_key_sha256",
        "search_key_sha256",
        "session_id",
        "selected_candidate_id",
    ):
        left = str(cycle.get(key) or "")
        right = str(session_receipt.get(key) or "")
        if left and right and left != right:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")


def _verify_store_reference_resolution(
    store: Any,
    bundle: Mapping[str, Any],
) -> None:
    known_hypothesis: set[str] = set()
    known_decisions: set[str] = set()
    session_id = str(bundle["session_id"])
    candidate_ids = [str(item) for item in (bundle.get("candidate_ids") or []) if str(item)]
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = json.loads(record.payload_json)
        if payload.get("session_id") != session_id:
            continue
        if kind == "HYPOTHESIS_VERSION":
            hyp_id = str(payload.get("hypothesis_version_id") or record.entity_id)
            known_hypothesis.add(hyp_id)
        elif kind == "DECISION_EVENT":
            decision_id = str(payload.get("decision_event_id") or record.entity_id)
            known_decisions.add(decision_id)
    if len(known_hypothesis) >= len(candidate_ids):
        for candidate_id in candidate_ids:
            if candidate_id not in known_hypothesis:
                raise HficSessionError("CANDIDATE_REFERENCE_UNRESOLVED")
    for decision_id in bundle.get("decision_event_ids") or []:
        if str(decision_id) not in known_decisions:
            raise HficSessionError("DECISION_REFERENCE_UNRESOLVED")
    digest = bundle.get("forge_context_packet_sha256")
    if isinstance(digest, str) and len(digest) == 64:
        _verify_forge_context_artifact(store, digest)


def _verify_forge_context_artifact(store: Any, digest: str) -> None:
    from solana_alpha_lab.factory.hfic_preflight import (
        HficPreflightError,
        verify_forge_context_packet,
    )

    data_root = Path(store._root)
    try:
        verify_forge_context_packet(data_root, digest)
    except HficPreflightError as exc:
        raise HficSessionError(str(exc)) from exc


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
    from solana_alpha_lab.factory.observation_fast_lane_terminals import (
        hfic_terminal_for_classifier,
    )

    observation_mapped = hfic_terminal_for_classifier(outcome)
    if observation_mapped is not None:
        return observation_mapped
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
    as_of_raw = ""
    for candidate in (
        submission.get("classifier_evaluated_at") if isinstance(submission, Mapping) else None,
        frozen.get("classifier_evaluated_at"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            as_of_raw = candidate.strip()
            break
    if as_of_raw:
        as_of = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00")).astimezone(UTC)
    else:
        as_of = datetime.now(UTC)
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
    clock: Clock | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    if existing is not None and existing.get("session_state") == phase:
        return existing
    git = repository_git_snapshot(Path(repo_root))
    stage_time = _stage_datetime(clock)
    phase_token = "REV" if phase == "REVISION_REQUIRED" else "CLS"
    transaction_id = f"RESEARCH-TXN-HFICINT-{phase_token}-{session_id[-12:]}"
    event = _make_event_factory(
        repo_root,
        git,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
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
                "critic_result_sha256": critic_result_sha256,
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
    clock: Clock | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    if existing.get("session_state") == "REVISED_AWAITING_CRITIC":
        return existing
    if existing.get("session_state") != "REVISION_REQUIRED":
        raise HficSessionError("REVISION_NOT_PENDING")
    if int(existing.get("revision_count") or 0) >= 1:
        raise HficSessionError("REVISION_BUDGET_EXHAUSTED")
    if repo_root is not None:
        _validate_json_schema(
            revised_draft,
            Path(repo_root) / "catalog/schemas/hypothesis_forge_draft_v1.schema.json",
        )
    _validate_revision_context_lock(existing, revised_draft)
    candidates = revised_draft.get("candidates")
    if not isinstance(candidates, list) or not (
        MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES
    ):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    try:
        draft_identities = assign_portfolio_ids(candidates)
    except HficIdentityError as exc:
        raise HficSessionError(str(exc)) from exc
    selected_index = _resolve_ref(
        revised_draft.get("selected_candidate_ref"),
        draft_identities,
    )
    if selected_index < 0:
        raise HficSessionError("REVISION_SELECTED_CHANGED")
    original_ordinal = frozen.get("selected_display_ordinal")
    if original_ordinal is None:
        original_ordinal = existing.get("selected_display_ordinal")
    selected_identity = draft_identities[selected_index]
    if (
        original_ordinal is not None
        and selected_identity.display_ordinal is not None
        and selected_identity.display_ordinal != original_ordinal
    ):
        raise HficSessionError("REVISION_SELECTED_CHANGED")
    original_selected_id = str(
        existing.get("selected_candidate_id") or frozen.get("selected_candidate_id") or ""
    )
    if not original_selected_id:
        raise HficSessionError("REVISION_SELECTED_CHANGED")
    stored_by_id = {
        str(card.get("hypothesis_version_id")): card
        for card in (existing.get("candidates") or [])
    }
    id_to_draft = {item.candidate_id: item for item in draft_identities}
    packet_in = existing.get("critic_input_packet")
    runner_up_index = _resolve_ref(
        revised_draft.get("runner_up_candidate_ref"),
        draft_identities,
    )
    if runner_up_index < 0:
        raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    runner_up_id = draft_identities[runner_up_index].candidate_id
    if runner_up_id != existing.get("runner_up_candidate_id"):
        raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    rejected_index = _resolve_ref(
        revised_draft.get("strongest_rejected_alternative"),
        draft_identities,
    )
    if rejected_index < 0:
        raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    rejected_id = draft_identities[rejected_index].candidate_id
    rejected_id_existing = existing.get("rejected_alternative_id")
    if not rejected_id_existing and isinstance(packet_in, Mapping):
        rejected_id_existing = packet_in.get("strongest_rejected_alternative")
    if rejected_id != rejected_id_existing:
        raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    original_selected: dict[str, Any] = {}
    if isinstance(packet_in, Mapping):
        selected_card = packet_in.get("selected_candidate")
        if isinstance(selected_card, Mapping):
            original_selected = dict(selected_card)
    selected_card = candidates[selected_index]
    rebuilt_selected = {
        "candidate_id": selected_identity.candidate_id,
        "claim": str(selected_card.get("claim") or ""),
        "nearest_prior_and_difference": str(
            selected_card.get("nearest_prior_and_difference") or "NOT_DECLARED_IN_DRAFT"
        ),
        "actor_counterparty": str(selected_card.get("actor_counterparty") or ""),
        "mechanism": str(selected_card.get("mechanism") or ""),
        "why_not_arbitraged": str(
            selected_card.get("why_not_arbitraged") or "NOT_DECLARED_IN_DRAFT"
        ),
        "population": str(selected_card.get("population") or ""),
        "decision_timestamp": str(selected_card.get("decision_timestamp") or ""),
        "primary_x": str(selected_card.get("primary_x_family") or ""),
        "primary_y": str(selected_card.get("primary_y") or ""),
        "horizon_notional": str(selected_card.get("horizon_notional") or ""),
        "disconfirming_prediction": str(
            selected_card.get("disconfirming_prediction") or "NOT_DECLARED_IN_DRAFT"
        ),
        "negative_control": str(selected_card.get("negative_control") or ""),
        "alternative_world": str(
            selected_card.get("alternative_world") or "NOT_DECLARED_IN_DRAFT"
        ),
        "confounders": selected_card.get("confounders") or ["NOT_DECLARED_IN_DRAFT"],
        "pit_leakage_survivorship_risks": selected_card.get(
            "pit_leakage_survivorship_risks"
        )
        or ["NOT_DECLARED_IN_DRAFT"],
        "execution_capacity_risks": selected_card.get("execution_capacity_risks")
        or ["NOT_DECLARED_IN_DRAFT"],
        "available_data_bindings": selected_card.get("available_data_bindings") or [],
        "missing_or_forward_only_data": selected_card.get("missing_or_forward_only_data")
        or [],
        "proposed_method": str(selected_card.get("proposed_method") or "NOT_DECLARED_IN_DRAFT"),
        "cheapest_falsifier": str(selected_card.get("cheapest_falsifier") or ""),
        "pass_fail_inconclusive_semantics": str(
            selected_card.get("pass_fail_inconclusive_semantics") or "NOT_DECLARED_IN_DRAFT"
        ),
        "decision_unlocked": str(
            selected_card.get("decision_unlocked") or "NOT_DECLARED_IN_DRAFT"
        ),
    }
    if not isinstance(packet_in, Mapping):
        raise HficSessionError("CRITIC_INPUT_ARTIFACT_MISSING")
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
    existing_ids = {
        str(item) for item in (existing.get("candidate_ids") or []) if str(item)
    }
    draft_ids = {item.candidate_id for item in draft_identities}
    non_selected_existing = existing_ids - {original_selected_id}
    non_selected_draft = draft_ids - {selected_identity.candidate_id}
    if non_selected_existing != non_selected_draft:
        raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    for candidate_id in non_selected_existing:
        stored = stored_by_id.get(candidate_id)
        draft_match = id_to_draft.get(candidate_id)
        if draft_match is None:
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
        if stored is not None and str(stored.get("definition_sha256") or "") != draft_match.full_sha256:
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    packet = dict(packet_in)
    packet["selected_candidate"] = rebuilt_selected
    packet["strongest_rejected_alternative"] = rejected_id
    packet["research_memory_as_of"] = str(existing.get("research_memory_as_of") or "")
    packet["owner_focus"] = str(existing.get("owner_focus") or "AUTO")
    packet["truth_roots_used"] = _nonempty_str_list(
        revised_draft.get("truth_roots_used"),
        code="TRUTH_ROOTS_REQUIRED",
    )
    packet["prior_work_queries"] = _nonempty_str_list(
        revised_draft.get("prior_work_receipts") or revised_draft.get("prior_work_queries"),
        code="PRIOR_WORK_RECEIPTS_REQUIRED",
    )
    _bind_packet_session_id(packet, str(frozen["session_id"]))
    if repo_root is not None:
        _validate_json_schema(
            packet,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_input_v1.schema.json",
        )
    packet_sha = _canonical_json_hash(packet)
    candidate_ids = [
        selected_identity.candidate_id if str(item) == original_selected_id else str(item)
        for item in (existing.get("candidate_ids") or [])
    ]
    git = repository_git_snapshot(Path(repo_root))
    session_id = str(frozen["session_id"])
    stage_time = _stage_datetime(clock)
    transaction_id = f"RESEARCH-TXN-HFICREV-{session_id[-16:]}"
    event = _make_event_factory(
        repo_root,
        git,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
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
                "owner_focus": existing.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": existing.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": existing.get("focus_key_sha256") or "",
                "search_key_sha256": existing.get("search_key_sha256") or "",
                "selected_candidate_id": selected_identity.candidate_id,
                "runner_up_candidate_id": runner_up_id,
                "rejected_alternative_id": rejected_id,
                "candidate_ids": candidate_ids,
                "critic_input_packet_sha256": packet_sha,
                "selected_definition_sha256": selected_identity.full_sha256,
                "selected_display_ordinal": selected_identity.display_ordinal,
                "git_composite_sha256": existing.get("git_composite_sha256"),
                "research_memory_as_of": existing.get("research_memory_as_of"),
                "revision_count": 1,
            },
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
                "session_id": session_id,
                "hfic_protocol": PROMPT_VERSION,
                "artifact_kind": "CRITIC_INPUT_PACKET",
                "payload_canonical": _canonical_bytes(packet).decode("utf-8"),
                "payload_sha256": packet_sha,
            },
            transaction_id=transaction_id,
        ),
    ]
    if selected_identity.candidate_id != original_selected_id:
        records.append(
            event(
                record_id=f"HFIC-HYP-{selected_identity.candidate_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=selected_identity.candidate_id,
                hypothesis_version_id=selected_identity.candidate_id,
                payload={
                    "hypothesis_version_id": selected_identity.candidate_id,
                    "session_id": session_id,
                    "hfic_protocol": PROMPT_VERSION,
                    "statement": selected_identity.definition["claim"],
                    "claim": selected_identity.definition["claim"],
                    "mechanism": selected_identity.definition["mechanism"],
                    "actor_counterparty": selected_identity.definition["actor_counterparty"],
                    "population": selected_identity.definition["population"],
                    "decision_timestamp": selected_identity.definition["decision_timestamp"],
                    "primary_x_family": selected_identity.definition["primary_x_family"],
                    "primary_y": selected_identity.definition["primary_y"],
                    "horizon_notional": selected_identity.definition["horizon_notional"],
                    "negative_control": selected_identity.definition["negative_control"],
                    "falsifier": selected_identity.definition["cheapest_falsifier"],
                    "cheapest_falsifier": selected_identity.definition["cheapest_falsifier"],
                    "definition_sha256": selected_identity.full_sha256,
                    "role_in_session": "SELECTED",
                    "supersedes_hypothesis_version_id": original_selected_id,
                },
                transaction_id=transaction_id,
            )
        )
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
    clock: Clock | None = None,
) -> dict[str, Any]:
    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    if existing.get("session_state") == "SYNTHESIS_COMPLETE":
        return existing
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
        clock=clock,
    )


def finalize_session(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    data_root: Any = None,
    clock: Clock | None = None,
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
        if existing is not None and existing.get("session_state") == "REVISION_REQUIRED":
            return existing
        if not isinstance(critic_result.get("revision_receipt"), Mapping):
            raise HficSessionError("REVISION_RECEIPT_REQUIRED")
        return persist_intermediate_cycle(
            store,
            frozen,
            critic_result,
            repo_root=repo_root,
            phase="REVISION_REQUIRED",
            clock=clock,
        )
    if terminal == "PASS_TO_CLASSIFICATION":
        fake = critic_result.get("classifier_receipt")
        if fake:
            raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
        if existing is not None and existing.get("session_state") == "AWAITING_CLASSIFICATION":
            return existing
        return persist_intermediate_cycle(
            store,
            frozen,
            critic_result,
            repo_root=repo_root,
            phase="AWAITING_CLASSIFICATION",
            clock=clock,
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
    stage_time = _stage_datetime(clock)
    created_at = render_canonical_utc(stage_time)
    transaction_id = f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}"
    event = _make_event_factory(
        repo_root,
        git_before,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
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
    started = frozen.get("session_started_at")
    if isinstance(started, str) and started.strip():
        receipt["session_started_at"] = started
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
    key = str(schema_path)
    validator = _SCHEMA_VALIDATORS.get(key)
    if validator is None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        _SCHEMA_VALIDATORS[key] = validator
    errors = list(validator.iter_errors(document))
    if errors:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


def load_session_bundle(store: Any, session_id: str) -> dict[str, Any] | None:
    cycles: list[dict[str, Any]] = []
    candidate_cards: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    artifacts: list[tuple[dict[str, Any], str | None]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = json.loads(record.payload_json)
        if payload.get("session_id") != session_id:
            continue
        if kind == "RESEARCH_CYCLE":
            cycles.append(payload)
            continue
        if kind == "HYPOTHESIS_VERSION":
            candidate_cards.append(payload)
        elif kind == "DECISION_EVENT":
            decisions.append(payload)
        elif kind == "RESEARCH_ARTIFACT":
            raw = payload.get("payload_canonical")
            expected_hash = payload.get("payload_sha256")
            if isinstance(raw, str) and isinstance(expected_hash, str):
                actual_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    if payload.get("artifact_kind") == "NEXT_EPISTEMIC_ACTION":
                        raise HficSessionError("HFIC_NEXT_ACTION_ARTIFACT_HASH_MISMATCH")
                    raise HficSessionError("ARTIFACT_HASH_MISMATCH")
            artifacts.append((payload, raw if isinstance(raw, str) else None))
    if not cycles:
        return None
    cycle: dict[str, Any] | None = None
    for payload in cycles:
        receipt_sha = str(payload.get("session_receipt_sha256") or "")
        result_sha = str(payload.get("critic_result_sha256") or "")
        has_receipt = bool(
            receipt_sha
            and any(
                wrapper.get("artifact_kind") == "SESSION_RECEIPT"
                and str(wrapper.get("payload_sha256") or "") == receipt_sha
                for wrapper, _raw in artifacts
            )
        )
        has_critic = bool(
            result_sha
            and any(
                wrapper.get("artifact_kind") == "CRITIC_RESULT"
                and str(wrapper.get("payload_sha256") or "") == result_sha
                for wrapper, _raw in artifacts
            )
        )
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
    for card in candidate_cards:
        item = str(card.get("hypothesis_version_id") or "")
        if item and item not in unique_ids:
            unique_ids.append(item)
    decision_ids = [
        str(item.get("decision_event_id"))
        for item in decisions
        if item.get("decision_event_id")
    ]
    expected_input_sha = str(cycle.get("critic_input_packet_sha256") or "")
    expected_result_sha = str(cycle.get("critic_result_sha256") or "")
    expected_receipt_sha = str(cycle.get("session_receipt_sha256") or "")
    critic_input = None
    critic_input_sha = None
    critic_result = None
    critic_result_sha = None
    session_receipt = None
    classifier_receipt = None
    if expected_input_sha:
        _wrapper, critic_input, critic_input_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_INPUT_PACKET",
            expected_sha=expected_input_sha,
        )
    if expected_result_sha:
        _wrapper, critic_result, critic_result_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_RESULT",
            expected_sha=expected_result_sha,
        )
    if expected_receipt_sha:
        _wrapper, session_receipt, receipt_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="SESSION_RECEIPT",
            expected_sha=expected_receipt_sha,
        )
        no_worthy = (
            isinstance(session_receipt, Mapping)
            and session_receipt.get("critic_terminal") == "NO_WORTHY_HYPOTHESIS"
            and session_receipt.get("critic_launched") is False
            and not session_receipt.get("selected_candidate_id")
        )
        if no_worthy:
            if session_receipt.get("critic_input_packet_sha256") or session_receipt.get(
                "critic_result_sha256"
            ):
                raise HficSessionError("CRITIC_LAUNCHED_FOR_NO_WORTHY")
        else:
            if critic_input_sha is None or critic_result_sha is None:
                raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
            _verify_complete_hash_chain(
                cycle,
                session_receipt=session_receipt,
                critic_input_sha=critic_input_sha,
                critic_result_sha=critic_result_sha,
                receipt_sha=receipt_sha,
            )
    if isinstance(session_receipt, Mapping):
        for wrapper, raw in artifacts:
            if wrapper.get("artifact_kind") != "CLASSIFIER_RECEIPT":
                continue
            if isinstance(raw, str):
                classifier_receipt = json.loads(raw)
            break
    elif isinstance(critic_result, Mapping):
        embedded = critic_result.get("classifier_receipt")
        if isinstance(embedded, Mapping):
            classifier_receipt = dict(embedded)
    state = str(cycle.get("phase") or "FROZEN_AWAITING_CRITIC")
    if state == "SYNTHESIS_COMPLETE" and not isinstance(session_receipt, Mapping):
        if cycle.get("critic_terminal") == "NO_WORTHY_HYPOTHESIS" and not cycle.get(
            "selected_candidate_id"
        ):
            raise HficSessionError("NO_WORTHY_RECEIPT_MISSING")
        state = "CRITIC_RESULT_READY" if critic_result is not None else "FROZEN_AWAITING_CRITIC"
    bundle = {
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
        "critic_input_packet_sha256": expected_input_sha or critic_input_sha,
        "critic_result": critic_result,
        "critic_result_sha256": critic_result_sha,
        "session_receipt": session_receipt,
        "session_receipt_sha256": expected_receipt_sha or None,
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
        "forge_context_packet_sha256": cycle.get("forge_context_packet_sha256")
        or (
            session_receipt.get("forge_context_packet_sha256")
            if isinstance(session_receipt, Mapping)
            else None
        ),
        "next_action": None,
        "next_action_status": "LEGACY_NOT_RECORDED",
    }
    expected_action_sha = None
    if isinstance(session_receipt, Mapping):
        maybe_sha = session_receipt.get("next_action_artifact_sha256")
        if isinstance(maybe_sha, str) and len(maybe_sha) == 64:
            expected_action_sha = maybe_sha
    if expected_action_sha is None:
        maybe_cycle_sha = cycle.get("next_action_artifact_sha256")
        if isinstance(maybe_cycle_sha, str) and len(maybe_cycle_sha) == 64:
            expected_action_sha = maybe_cycle_sha
    if expected_action_sha:
        _wrapper, next_action, _observed = _load_artifact_by_sha(
            artifacts,
            artifact_kind="NEXT_EPISTEMIC_ACTION",
            expected_sha=expected_action_sha,
        )
        for key in (
            "session_id",
            "evidence_epoch_sha256",
            "focus_key_sha256",
            "search_key_sha256",
            "forge_context_packet_sha256",
        ):
            left = str(next_action.get(key) or "")
            right = str(bundle.get(key) or "")
            if left and right and left != right:
                raise HficSessionError("HFIC_NEXT_ACTION_ARTIFACT_BINDING_MISMATCH")
        if next_action.get("source_terminal") != "NO_WORTHY_HYPOTHESIS":
            raise HficSessionError("HFIC_NEXT_ACTION_ARTIFACT_BINDING_MISMATCH")
        bundle["next_action"] = next_action
        bundle["next_action_status"] = "RECORDED"
        bundle["next"] = str(next_action.get("action_type") or bundle.get("next") or "STOP")
    context_digest = bundle.get("forge_context_packet_sha256")
    if isinstance(context_digest, str) and len(context_digest) == 64:
        _verify_forge_context_artifact(store, context_digest)
    if state == "SYNTHESIS_COMPLETE":
        _verify_store_reference_resolution(store, bundle)
    return bundle


def _redact_placeholder_times(value: object) -> object:
    from solana_alpha_lab.factory.hfic_clock import is_placeholder_timestamp

    if isinstance(value, Mapping):
        return {key: _redact_placeholder_times(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_placeholder_times(item) for item in value]
    if is_placeholder_timestamp(value):
        return "UNKNOWN"
    return value


def _display_session_receipt(receipt: object, status: str) -> object:
    from solana_alpha_lab.factory.hfic_clock import is_placeholder_timestamp
    from solana_alpha_lab.factory.hfic_provenance import PROVENANCE_CORRECTED

    if not isinstance(receipt, Mapping):
        return receipt
    displayed = dict(receipt)
    placeholder = is_placeholder_timestamp(displayed.get("created_at")) or is_placeholder_timestamp(
        displayed.get("session_started_at")
    )
    if status == PROVENANCE_CORRECTED or placeholder:
        if is_placeholder_timestamp(displayed.get("created_at")):
            displayed["created_at"] = "UNKNOWN"
        if is_placeholder_timestamp(displayed.get("session_started_at")):
            displayed["session_started_at"] = "UNKNOWN"
        displayed["original_exact_time_status"] = "UNKNOWN"
        displayed["chronological_use_forbidden"] = True
        displayed["recovered_exact_time"] = False
    return displayed


def _session_provenance_status(store: Any, session_id: str) -> str:
    from solana_alpha_lab.factory.hfic_provenance import provenance_status_for_session

    try:
        return provenance_status_for_session(store, session_id)
    except HficSessionError as exc:
        if str(exc) == "PROVENANCE_TIME_UNCOVERED":
            return "PLACEHOLDER_UNCOVERED"
        raise


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
    provenance_status = _session_provenance_status(store, session_id)
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
        "critic_input_packet": _redact_placeholder_times(bundle.get("critic_input_packet")),
        "critic_input_packet_sha256": bundle.get("critic_input_packet_sha256"),
        "critic_result_sha256": bundle.get("critic_result_sha256"),
        "critic_terminal": bundle.get("critic_terminal"),
        "lane_classifier_terminal": bundle.get("lane_classifier_terminal"),
        "decision_event_ids": bundle.get("decision_event_ids") or [],
        "next": bundle.get("next") or "STOP",
        "next_action": bundle.get("next_action"),
        "next_action_status": bundle.get("next_action_status") or "LEGACY_NOT_RECORDED",
        "decisions": bundle.get("decisions") or {},
        "authority": bundle["authority"],
        "session_receipt": _display_session_receipt(
            bundle.get("session_receipt"), provenance_status
        ),
        "provenance_time_status": provenance_status,
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
        "artifacts_retrievable": (
            (
                bundle.get("critic_terminal") == "NO_WORTHY_HYPOTHESIS"
                and not bundle.get("selected_candidate_id")
                and bundle.get("critic_input_packet") is None
                and isinstance(bundle.get("session_receipt"), Mapping)
            )
            or (
                bool(bundle.get("critic_input_packet"))
                and (
                    str(bundle.get("session_state")) != "SYNTHESIS_COMPLETE"
                    or (
                        bool(bundle.get("critic_result"))
                        and isinstance(bundle.get("session_receipt"), Mapping)
                    )
                )
            )
        ),
        "candidates_retrievable": len(bundle.get("candidates") or []) >= 4,
    }
    if provenance_status != "VALID":
        payload["original_exact_time_status"] = "UNKNOWN"
        payload["chronological_use_forbidden"] = True
        payload["recovered_exact_time"] = False
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
    terminal = str(bundle.get("critic_terminal") or "")
    if terminal in _INTERMEDIATE_CRITIC_TERMINALS:
        raise HficSessionError("CRITIC_RESULT_NOT_FINAL")
    no_worthy = (
        terminal == "NO_WORTHY_HYPOTHESIS"
        and not receipt.get("selected_candidate_id")
        and receipt.get("critic_launched") is False
    )
    receipt_input = str(receipt.get("critic_input_packet_sha256") or "")
    receipt_result = str(receipt.get("critic_result_sha256") or "")
    bundle_input = str(bundle.get("critic_input_packet_sha256") or "")
    bundle_result = str(bundle.get("critic_result_sha256") or "")
    if no_worthy:
        if receipt.get("critic_input_packet_sha256") or receipt.get("critic_result_sha256"):
            raise HficSessionError("CRITIC_LAUNCHED_FOR_NO_WORTHY")
        if bundle.get("critic_input_packet") is not None or bundle.get("critic_result") is not None:
            raise HficSessionError("CRITIC_LAUNCHED_FOR_NO_WORTHY")
    else:
        if not receipt_input or receipt_input != bundle_input:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
        if not receipt_result or receipt_result != bundle_result:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
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
    if not no_worthy:
        if bundle.get("critic_input_packet") is None or bundle.get("critic_result") is None:
            raise HficSessionError("SESSION_ARTIFACT_MISSING")
    if not shown["artifacts_retrievable"] or not shown["candidates_retrievable"]:
        raise HficSessionError("SESSION_ARTIFACT_MISSING")
    provider_calls = int(fence.get("provider_calls_actual", -1))
    if provider_calls != 0:
        raise HficSessionError("PROVIDER_CALLS_NONZERO")
    _verify_store_reference_resolution(store, bundle)
    from solana_alpha_lab.factory.hfic_provenance import (
        PROVENANCE_CORRECTED,
        resolve_provenance_status,
    )

    provenance_status = resolve_provenance_status(store)
    payload = {
        **shown,
        "runtime_no_git": "PROVEN",
        "provider_calls_actual": provider_calls,
        "git_composite_unchanged": True,
        "candidates_retrievable": shown["candidates_retrievable"],
        "artifacts_retrievable": shown["artifacts_retrievable"],
        "provenance_time_status": provenance_status,
        "recovered_exact_time": False,
    }
    if provenance_status == PROVENANCE_CORRECTED:
        payload["original_exact_time_status"] = "UNKNOWN"
        payload["chronological_use_forbidden"] = True
    return payload
