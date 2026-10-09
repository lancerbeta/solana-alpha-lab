"""HFIC session validation, identity rewrite, budget and decision mapping."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
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
from solana_alpha_lab.factory.hfic_prior_memory import (
    PriorMemoryCapacityError,
    PriorMemoryUnidentifiedError,
    build_prior_memory_snapshot,
)
from solana_alpha_lab.factory.hfic_suppression_semantics import (
    candidate_hard_close_entry,
    family_hard_close_terminals,
    ledger_from_receipt,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


_SCHEMA_VALIDATORS: dict[str, Draft202012Validator] = {}
PROMPT_VERSION = "HFIC-V1.2"
PROMPT_VERSION_V1_1 = "HFIC-V1.1"
SUPPORTED_PROMPT_VERSIONS = frozenset({PROMPT_VERSION_V1_1, PROMPT_VERSION})
CRITIC_PACKET_VERSION_V11 = "1.1"
CRITIC_PACKET_VERSION_V13_HISTORICAL = "1.3"
CRITIC_PACKET_VERSION_CURRENT = "1.4"
DRAFT_SCHEMA_BY_PACKET_VERSION = {
    "1.1": "catalog/schemas/hypothesis_forge_draft_v1.schema.json",
    "1.2": "catalog/schemas/hypothesis_forge_draft_v1_2.schema.json",
    # Additive: same HFIC-V1.2 grounding and prompt, a wider structural
    # candidate-count ceiling for a journal whose research policy raised
    # candidates.max_generated above the shipped default of 6.
    "1.3": "catalog/schemas/hypothesis_forge_draft_v1_3.schema.json",
}
SESSION_RECEIPT_SCHEMA_BY_PROMPT = {
    PROMPT_VERSION_V1_1: "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json",
    PROMPT_VERSION: "catalog/schemas/hypothesis_forge_session_receipt_v1_2.schema.json",
}
# Same shape as the historical v1_2 receipt, a wider candidate_ids ceiling: the receipt of a
# negative terminal (no selected candidate) whose draft carried more than the shipped 6.
SESSION_RECEIPT_SCHEMA_V1_2_WIDE = (
    "catalog/schemas/hypothesis_forge_session_receipt_v1_2_wide.schema.json"
)
SESSION_RECEIPT_SCHEMA_V1_3 = (
    "catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json"
)
# Additive: same v1_3 receipt shape, a wider candidate_ids ceiling for a
# journal whose research policy raised candidates.max_generated above 6.
SESSION_RECEIPT_SCHEMA_V1_4_WIDE = (
    "catalog/schemas/hypothesis_forge_session_receipt_v1_4.schema.json"
)
RUNNER_UP_AWAITING_CRITIC = "RUNNER_UP_AWAITING_CRITIC"
RUNNER_UP_REVISION_REQUIRED = "RUNNER_UP_REVISION_REQUIRED"
MIN_CANDIDATES = 0
MAX_CANDIDATES = 6


def _max_candidates_for(store: Any, journal_scope: object) -> int:
    """The journal's frozen candidate ceiling; the shipped 6 for a journal never frozen."""

    from solana_alpha_lab.factory.hfic_research_policy import limits_or_defaults

    return int(limits_or_defaults(store, journal_scope)["max_generated"])


PHASE_RANK = {
    "SYNTHESIS_COMPLETE": 0,
    "LEGACY_PARTIAL": 0,
    "AWAITING_CLASSIFICATION": 1,
    RUNNER_UP_AWAITING_CRITIC: 1,
    "REVISED_AWAITING_CRITIC": 3,
    "REVISION_REQUIRED": 4,
    "CRITIC_RESULT_READY": 5,
    "FROZEN_AWAITING_CRITIC": 6,
    "DRAFT_VALIDATED": 7,
    "PREFLIGHT_PROVEN": 8,
}
PENDING_STATES = frozenset(
    {
        "PREFLIGHT_PROVEN",
        "DRAFT_VALIDATED",
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        RUNNER_UP_AWAITING_CRITIC,
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
    "semantic_capability_digest_sha256",
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

    def __init__(self, code: str, *, uncovered_count: int | None = None,
                 detail: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.uncovered_count = uncovered_count
        self.detail = dict(detail or {})
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


def search_key_sha256(
    epoch: str,
    owner_focus: str,
    prompt_version: str,
    memory_eligibility_sha256: str | None = None,
    evidence_surface_mode: str | None = None,
) -> str:
    from solana_alpha_lab.factory.hfic_memory_policy import search_identity_sha256

    return search_identity_sha256(
        epoch,
        owner_focus,
        prompt_version,
        memory_eligibility_sha256,
        evidence_surface_mode,
    )


def _split_identity_fields(
    *sources: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Copy A5 market/capability stamps from the first source that carries them."""

    out: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in (
            "market_evidence_epoch_sha256",
            "capability_epoch_sha256",
        ):
            if key in out:
                continue
            value = source.get(key)
            if isinstance(value, str) and len(value) == 64:
                out[key] = value
    return out


def _stamp_split_identity(
    target: dict[str, Any],
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any]:
    fields = _split_identity_fields(*sources)
    if fields:
        target.update(fields)
    return target


def _market_evidence_basis_from_sources(
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the production A3 market basis retained for lifecycle readback."""

    for source in sources:
        if not isinstance(source, Mapping):
            continue
        direct = source.get("market_evidence_basis")
        if isinstance(direct, Mapping):
            return dict(direct)
        nested = source.get("forge_input_receipt")
        if isinstance(nested, Mapping):
            basis = nested.get("market_evidence_basis")
            if isinstance(basis, Mapping):
                return dict(basis)
    return None


def _stamp_market_evidence_basis(
    target: dict[str, Any],
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any]:
    basis = _market_evidence_basis_from_sources(*sources)
    if basis is not None:
        target["market_evidence_basis"] = basis
    return target


def _first_valid_hash(
    sources: Sequence[Mapping[str, Any] | None], key: str
) -> str | None:
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        value = source.get(key)
        if isinstance(value, str) and len(value) == 64 and re.fullmatch(
            r"[0-9a-f]{64}", value
        ):
            return value
    return None


def _consistent_valid_hash(
    sources: Sequence[Mapping[str, Any] | None], key: str
) -> str | None:
    """Return one hash only when every observed valid value agrees.

    A lifecycle writer may receive the same identity through the outer
    receipt, the forge-input receipt, and the context packet.  First-wins
    would let a stale outer value silently mask a newer production value.
    Conflicting valid values are therefore an admission conflict, not a
    preference decision.
    """

    observed: list[str] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        if key not in source:
            continue
        value = source.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            if value not in observed:
                observed.append(value)
            continue
        # A malformed nested identity is not equivalent to an absent legacy
        # field.  Silently dropping it could let a valid outer receipt mask a
        # corrupted production context.
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    if len(observed) > 1:
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    return observed[0] if observed else None


def _consistent_hash_state(
    sources: Sequence[Mapping[str, Any] | None], key: str
) -> tuple[str | None, bool]:
    """Return (known value, explicit unknown) without resurrecting UNKNOWN."""

    observed: list[str] = []
    explicit_unknown = False
    for source in sources:
        if not isinstance(source, Mapping) or key not in source:
            continue
        value = source.get(key)
        if value in (None, ""):
            explicit_unknown = True
            continue
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            if value not in observed:
                observed.append(value)
            continue
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    if len(observed) > 1 or (explicit_unknown and observed):
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    return (observed[0] if observed else None), explicit_unknown


def _execution_identity_fields(
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project one immutable slot/provenance binding from production inputs."""

    source_list = [source for source in sources if isinstance(source, Mapping)]
    expanded: list[Mapping[str, Any] | None] = list(source_list)
    for source in source_list:
        packet = source.get("forge_context_packet")
        if isinstance(packet, Mapping):
            expanded.append(packet)
        normalized = source.get("normalized_trajectory_v1")
        if isinstance(normalized, Mapping):
            expanded.append(normalized)

    initial_representation, initial_parent = _preflight_ladder_slot(
        source_list[0] if source_list else None
    )
    observed_representations: list[str] = []
    observed_parents: list[str] = []
    if initial_representation != "BASE":
        observed_representations.append(initial_representation)
    if initial_parent:
        observed_parents.append(initial_parent)
    for source in expanded:
        observed, observed_parent = _mapping_ladder_slot(source)
        if observed != "BASE":
            observed_representations.append(observed)
        if observed_parent:
            observed_parents.append(observed_parent)
    if len(set(observed_representations)) > 1 or len(set(observed_parents)) > 1:
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    representation = observed_representations[0] if observed_representations else "BASE"
    parent = observed_parents[0] if observed_parents else None

    semantic_version: str | None = None
    for source in expanded:
        if not isinstance(source, Mapping):
            continue
        for key in (
            "representation_semantic_version",
            "semantic_version",
            "representation_version",
        ):
            value = source.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                rendered = str(value).strip()
                if rendered:
                    semantic_version = rendered
                    break
        if semantic_version:
            break
    if semantic_version is None and representation == "BASE":
        semantic_version = PROMPT_VERSION

    fields: dict[str, Any] = {
        "ladder_representation_id": representation,
    }
    if parent:
        fields["control_session_id"] = parent
    if semantic_version:
        fields["representation_semantic_version"] = semantic_version

    market = _consistent_valid_hash(expanded, "market_evidence_epoch_sha256")
    capability = _consistent_valid_hash(expanded, "capability_epoch_sha256")
    focus_key = _consistent_valid_hash(expanded, "focus_key_sha256")
    focus_values: list[tuple[str, str]] = []
    for source in expanded:
        if isinstance(source, Mapping) and isinstance(source.get("owner_focus"), str):
            raw_focus = str(source["owner_focus"])
            focus_values.append((normalize_text(raw_focus), raw_focus))
    if len({normalized for normalized, _raw in focus_values}) > 1:
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    owner_focus = focus_values[0][1] if focus_values else "AUTO"
    if focus_key is None:
        focus_key = focus_key_sha256(owner_focus)
    payload_sha = _consistent_valid_hash(expanded, "representation_payload_sha256")
    memory_sha = _consistent_valid_hash(expanded, "memory_eligibility_sha256")
    model_sha = _consistent_valid_hash(expanded, "model_provenance_sha256")
    stored_binding, binding_unknown = _consistent_hash_state(
        expanded, "execution_binding_sha256"
    )
    cycles = {
        source.get("cycle_index")
        for source in expanded
        if isinstance(source, Mapping)
        and isinstance(source.get("cycle_index"), int)
        and not isinstance(source.get("cycle_index"), bool)
        and source.get("cycle_index") > 1
    }
    if len(cycles) > 1:
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    cycle_index = next(iter(cycles)) if cycles else 1
    if cycle_index > 1:
        # Only an explicitly authorized additional cycle carries an index; cycle 1 is unmarked.
        fields["cycle_index"] = cycle_index
    if market and semantic_version:
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            execution_binding_sha256,
            scientific_slot_sha256,
        )

        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id=representation,
            representation_semantic_version=semantic_version,
            owner_focus=owner_focus,
            cycle_index=cycle_index,
        )
        fields["scientific_slot_sha256"] = slot
        # A binding digest is provenance for an actual execution context.  A
        # tuple of null payload/memory/model fields is still UNKNOWN and must
        # not be upgraded into a readiness-looking hash.  The parent control
        # session is part of the binding whenever a representation is bound.
        fields["execution_binding_sha256"] = stored_binding
        if binding_unknown:
            # An explicit durable UNKNOWN is authoritative; complete sibling
            # fields do not grant permission to mint a new binding.
            fields["execution_binding_sha256"] = None
        elif capability and payload_sha and memory_sha and model_sha:
            expected_binding = execution_binding_sha256(
                scientific_slot_sha256=slot,
                capability_epoch_sha256=capability,
                control_session_id=parent,
                representation_payload_sha256=payload_sha,
                memory_eligibility_sha256=memory_sha,
                model_provenance_sha256=model_sha,
            )
            if stored_binding is not None and stored_binding != expected_binding:
                raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
            fields["execution_binding_sha256"] = expected_binding
        elif stored_binding is None and binding_unknown:
            fields["execution_binding_sha256"] = None
    elif stored_binding is not None or binding_unknown:
        fields["execution_binding_sha256"] = stored_binding
    if payload_sha:
        fields["representation_payload_sha256"] = payload_sha
    if model_sha:
        fields["model_provenance_sha256"] = model_sha
    return fields


def _stamp_execution_identity(
    target: dict[str, Any],
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any]:
    fields = _execution_identity_fields(target, *sources)
    target.update(fields)
    return target


def _stamp_prefreeze_capability_repair(
    target: dict[str, Any],
    receipt: Mapping[str, Any] | None,
) -> None:
    """Record original and current capability epochs as two different facts."""

    if not isinstance(receipt, Mapping) or receipt.get("prefreeze_capability_repair") is not True:
        return
    original = receipt.get("generated_draft_capability_epoch_sha256")
    current = target.get("capability_epoch_sha256") or receipt.get("capability_epoch_sha256")
    if (
        not _hash64(original)
        or not _hash64(current)
        or original == current
    ):
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
    target["prefreeze_capability_repair"] = True
    target["generated_draft_capability_epoch_sha256"] = original
    target["generated_draft_execution_binding_sha256"] = receipt.get(
        "generated_draft_execution_binding_sha256"
    )
    target["recovery_capability_epoch_sha256"] = current
    target["recovery_execution_binding_sha256"] = target.get("execution_binding_sha256")


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


def _effective_at_key(value: object) -> str:
    if isinstance(value, datetime):
        instant = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return instant.isoformat()
    return str(value or "")


def _cycle_better(candidate: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """Match projection: phase_rank ASC, hfic_cycle_seq DESC, effective_at DESC, record_id ASC.

    Repair-continuation cycles outrank older completes by sequence so a new
    terminal written under an authorized disposition becomes the active bundle.
    """
    cand_repair = bool(candidate.get("repair_continuation_disposition_sha256"))
    cur_repair = bool(current.get("repair_continuation_disposition_sha256"))
    if cand_repair or cur_repair:
        cand_seq = int(candidate.get("hfic_cycle_seq") or 0)
        cur_seq = int(current.get("hfic_cycle_seq") or 0)
        if cand_seq != cur_seq:
            return cand_seq > cur_seq
    cand_rank = phase_rank(candidate.get("phase") or candidate.get("session_state"))
    cur_rank = phase_rank(current.get("phase") or current.get("session_state"))
    if cand_rank != cur_rank:
        return cand_rank < cur_rank
    cand_seq = int(candidate.get("hfic_cycle_seq") or 0)
    cur_seq = int(current.get("hfic_cycle_seq") or 0)
    if cand_seq != cur_seq:
        return cand_seq > cur_seq
    cand_at = _effective_at_key(candidate.get("effective_at"))
    cur_at = _effective_at_key(current.get("effective_at"))
    if cand_at != cur_at:
        return cand_at > cur_at
    return str(candidate.get("record_id") or "") < str(current.get("record_id") or "")


def _next_cycle_seq(existing: Mapping[str, Any] | None) -> int:
    if existing is None:
        return 1
    return int(existing.get("hfic_cycle_seq") or 0) + 1


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
    require_current_market_identity: bool = False,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.commissioning_proof import (
        CommissioningProofError,
        prove_fast_lane_commissioned,
    )
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    action = receipt.get("action")
    if action not in {
        "START_NEW_SESSION",
        "RESUME_EXISTING_SESSION",
        "RESUME_REPAIR_CONTINUATION",
    }:
        raise HficSessionError("PREFLIGHT_ACTION_INVALID")
    if receipt.get("prompt_version") != PROMPT_VERSION:
        raise HficSessionError("PREFLIGHT_PROMPT_VERSION_INVALID")
    _reject_stale_fresh_session_draft(draft, receipt)
    if action == "RESUME_EXISTING_SESSION":
        draft_sha = hashlib.sha256(_canonical_bytes(draft)).hexdigest()
        if receipt.get("draft_lifecycle") != "GENERATED_BEFORE_FREEZE":
            raise HficSessionError("PREFLIGHT_ACTION_INVALID")
        if receipt.get("generated_draft_sha256") != draft_sha:
            raise HficSessionError("GENERATED_DRAFT_CONFLICT")
    elif action == "RESUME_REPAIR_CONTINUATION":
        if not str(receipt.get("session_id") or ""):
            raise HficSessionError("PREFLIGHT_ACTION_INVALID")
    observed_hash = receipt.get("preflight_receipt_sha256")
    expected_hash = canonical_preflight_receipt_sha256(receipt)
    if observed_hash != expected_hash:
        raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    if action == "RESUME_EXISTING_SESSION":
        # A generated draft is immutable across restart. Its reference points
        # to the original preflight, while this newly issued receipt records
        # the verified restart/readback. Persist both links; never rewrite the
        # draft merely to make its bytes resemble the restart receipt.
        source_receipt_id = receipt.get(
            "generated_draft_source_preflight_receipt_id"
        )
        source_receipt_hash = receipt.get(
            "generated_draft_source_preflight_receipt_sha256"
        )
        if draft.get("preflight_receipt_id") != source_receipt_id:
            raise HficSessionError("PREFLIGHT_RECEIPT_ID_MISMATCH")
        if draft.get("preflight_receipt_sha256") != source_receipt_hash:
            raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    else:
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
    if (require_current_store_digest and receipt_digest != digest
            and not _matching_orphan_reservation_only_delta(store, receipt, draft)):
        raise HficSessionError("PREFLIGHT_STORE_DIGEST_MISMATCH")
    from solana_alpha_lab.factory.hfic_memory_policy import (
        effective_policy,
        session_memory_eligibility,
    )

    current_memory = str(effective_policy(store)["memory_eligibility_sha256"])
    receipt_memory = session_memory_eligibility(receipt)
    if receipt.get("memory_eligibility_sha256") and receipt_memory != current_memory:
        raise HficSessionError("PREFLIGHT_STORE_DIGEST_MISMATCH")
    _validate_split_identity_binding(
        receipt,
        repo_root=Path(repo_root),
        data_root=data_root,
        require_current_market_identity=require_current_market_identity,
    )
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
        "memory_eligibility_sha256": current_memory,
        "research_memory_as_of": _require_memory_timestamp(
            receipt.get("research_memory_as_of")
        ),
        "commissioning_run_id": proof.get("run_id"),
        "provider_calls_actual": 0,
        "session_started_at": render_canonical_utc(started),
        **_split_identity_fields(receipt),
    }


def _validate_split_identity_binding(
    receipt: Mapping[str, Any],
    *,
    repo_root: Path,
    data_root: Path | None = None,
    require_current_market_identity: bool = False,
) -> None:
    """Verify split stamps against the production receipt before freeze writes."""

    market = receipt.get("market_evidence_epoch_sha256")
    capability = receipt.get("capability_epoch_sha256")
    forge_input = receipt.get("forge_input_receipt")
    if not isinstance(market, str) or re.fullmatch(r"[0-9a-f]{64}", market) is None:
        raise HficSessionError("MARKET_IDENTITY_UNAVAILABLE")
    if not isinstance(capability, str) or re.fullmatch(r"[0-9a-f]{64}", capability) is None:
        raise HficSessionError("CAPABILITY_IDENTITY_UNAVAILABLE")

    # The normal production preflight carries the no-write Forge-input
    # receipt.  Rehash its market basis instead of trusting a caller-provided
    # stamp.  This also keeps lineage UNKNOWN/FAIL from becoming an admission.
    if not isinstance(forge_input, Mapping):
        raise HficSessionError("MARKET_IDENTITY_BASIS_MISSING")
    input_market = forge_input.get("market_evidence_epoch_sha256")
    if input_market != market:
        raise HficSessionError("MARKET_IDENTITY_DRIFT")
    if forge_input.get("forge_runnable") is not True:
        raise HficSessionError("MARKET_IDENTITY_DRIFT")
    basis = forge_input.get("market_evidence_basis")
    if not isinstance(basis, Mapping):
        raise HficSessionError("MARKET_IDENTITY_BASIS_MISSING")
    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError,
        market_evidence_epoch_sha256,
    )

    try:
        if market_evidence_epoch_sha256(basis) != market:
            raise HficSessionError("MARKET_IDENTITY_DRIFT")
    except EvidenceIdentityError as exc:
        raise HficSessionError(str(exc)) from exc

    if require_current_market_identity:
        if data_root is None:
            raise HficSessionError("MARKET_IDENTITY_BASIS_MISSING")
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            compute_market_epoch_for_data_root,
        )

        try:
            current_market, _current_basis = compute_market_epoch_for_data_root(
                repo_root, data_root
            )
        except EvidenceIdentityError as exc:
            raise HficSessionError(str(exc)) from exc
        if current_market != market:
            raise HficSessionError("MARKET_IDENTITY_DRIFT")

    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError,
        compute_capability_epoch_for_repo,
    )

    try:
        computed_capability, _basis = compute_capability_epoch_for_repo(repo_root)
    except EvidenceIdentityError as exc:
        raise HficSessionError(str(exc)) from exc
    if computed_capability != capability:
        raise HficSessionError("CAPABILITY_IDENTITY_DRIFT")


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


def _reject_stale_fresh_session_draft(
    draft: Mapping[str, Any],
    receipt: Mapping[str, Any] | None,
) -> None:
    """Fresh START_NEW_SESSION on the current prompt must not persist a legacy draft.

    Historical V1.1 freeze without a current START_NEW_SESSION preflight stays
    readable. Do not coerce packet_version labels: V1.2 grounding is absent in V1.1.
    """
    if not isinstance(receipt, Mapping):
        return
    if receipt.get("action") != "START_NEW_SESSION":
        return
    if receipt.get("prompt_version") != PROMPT_VERSION:
        return
    packet_version = str(draft.get("packet_version") or "")
    declared = str(draft.get("generator_prompt_version") or "")
    if packet_version in ("1.2", "1.3") and declared == PROMPT_VERSION:
        return
    raise HficSessionError("FRESH_SESSION_DRAFT_VERSION_MISMATCH")


def _draft_packet_version(draft: Mapping[str, Any]) -> str:
    version = str(draft.get("packet_version") or "1.1")
    if version not in DRAFT_SCHEMA_BY_PACKET_VERSION:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    return version


def _draft_prompt_version(draft: Mapping[str, Any]) -> str:
    packet_version = _draft_packet_version(draft)
    declared = str(draft.get("generator_prompt_version") or "")
    expected = PROMPT_VERSION if packet_version in ("1.2", "1.3") else PROMPT_VERSION_V1_1
    if declared and declared != expected:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    return expected


def _critic_packet_version(draft_packet_version: str) -> str:
    """Map Forge draft version to Critic transport version.

    Fresh HFIC-V1.2 freeze emits critic packet 1.4. Historical draft 1.1 stays
    critic 1.1. Do not mint an HFIC-V1.3 or HFIC-V1.4 Prompt A: draft
    packet_version 1.3 is a wider candidate-count transport for the same
    HFIC-V1.2 prompt, not a new prompt, and also emits critic packet 1.4.
    """
    if draft_packet_version in ("1.2", "1.3"):
        return CRITIC_PACKET_VERSION_CURRENT
    return CRITIC_PACKET_VERSION_V11


def _draft_schema_path(repo_root: Any, draft: Mapping[str, Any]) -> Path:
    return Path(repo_root) / DRAFT_SCHEMA_BY_PACKET_VERSION[_draft_packet_version(draft)]


def _session_receipt_schema_path(
    repo_root: Any,
    prompt_version: str,
    *,
    selected_path: bool = True,
    wide_candidates: bool = False,
) -> Path:
    if selected_path and prompt_version == PROMPT_VERSION:
        if wide_candidates:
            return Path(repo_root) / SESSION_RECEIPT_SCHEMA_V1_4_WIDE
        return Path(repo_root) / SESSION_RECEIPT_SCHEMA_V1_3
    if wide_candidates and not selected_path and prompt_version == PROMPT_VERSION:
        return Path(repo_root) / SESSION_RECEIPT_SCHEMA_V1_2_WIDE
    relative = SESSION_RECEIPT_SCHEMA_BY_PROMPT.get(prompt_version)
    if relative is None:
        relative = SESSION_RECEIPT_SCHEMA_BY_PROMPT[PROMPT_VERSION_V1_1]
    return Path(repo_root) / relative


def _copy_feature_bindings(raw: object) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        binding: dict[str, Any] = {
            "feature_id": str(item.get("feature_id") or ""),
            "availability_class": str(item.get("availability_class") or ""),
            "available_to_strategy_semantics": str(
                item.get("available_to_strategy_semantics") or ""
            ),
        }
        value_status = item.get("value_status")
        if isinstance(value_status, str) and value_status:
            binding["value_status"] = value_status
        out.append(binding)
    return out


def _copy_capability_bindings(raw: object) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        out.append(
            {
                "capability_id": str(item.get("capability_id") or ""),
                "accepted": bool(item.get("accepted")),
                "authority_granted": bool(item.get("authority_granted")),
            }
        )
    return out


def _freeze_owned_grounding_fields(card: Mapping[str, Any]) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_control_integrity import (
        CRITIC_PACKET_GROUNDING_MISMATCH,
        text_list,
    )

    grounding = card.get("grounding")
    if not isinstance(grounding, Mapping):
        raise HficSessionError(CRITIC_PACKET_GROUNDING_MISMATCH)
    copied = {
        "context_packet_sha256": str(grounding.get("context_packet_sha256") or ""),
        "feature_bindings": _copy_feature_bindings(grounding.get("feature_bindings")),
        "capability_bindings": _copy_capability_bindings(
            grounding.get("capability_bindings")
        ),
        "unresolved_requirements": text_list(grounding.get("unresolved_requirements")),
        "terminal": str(grounding.get("terminal") or ""),
    }
    state = card.get("state_transition")
    if state is not None and not isinstance(state, str):
        state = str(state)
    return {
        "estimand": str(card.get("estimand") or ""),
        "state_transition": state,
        "required_feature_ids": [
            str(item) for item in (card.get("required_feature_ids") or []) if item
        ],
        "required_capability_ids": [
            str(item) for item in (card.get("required_capability_ids") or []) if item
        ],
        "unresolved_requirements": text_list(card.get("unresolved_requirements")),
        "grounding": copied,
    }


def _copy_evidence_surface_mode(
    target: dict[str, Any],
    source: Mapping[str, Any] | None,
) -> None:
    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
        session_evidence_surface_mode,
    )

    mode = session_evidence_surface_mode(source)
    if mode == CURRENT_REPRESENTATION_CONTROL_V1:
        target["evidence_surface_mode"] = mode


def _discovery_candidate_scope(frozen: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(frozen, Mapping):
        return {}
    grounded = frozen.get("grounded_evidence")
    if not isinstance(grounded, Mapping):
        return {}
    scope = grounded.get("candidate_scope")
    if not isinstance(scope, Mapping):
        return {}
    kept: dict[str, Any] = {}
    for key in (
        "population",
        "decision_timestamp",
        "target",
        "estimand",
        "explanatory_condition",
        "evidence_surface_mode",
        "representation_scope",
    ):
        value = scope.get(key)
        if isinstance(value, str) and value:
            kept[key] = value
    return kept


def _hypothesis_scope_fields(
    frozen: Mapping[str, Any] | None,
    definition: Mapping[str, Any] | None,
    card: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Persist only scope axes proven on this candidate.

    A session-wide ``grounded_evidence.candidate_scope`` is not copied onto
    every hypothesis. ``evidence_surface_mode`` may come from the session
    because it is not a per-candidate target or estimand.
    """

    out: dict[str, str] = {}
    sources: list[Mapping[str, Any]] = []
    if isinstance(card, Mapping):
        sources.append(card)
    if isinstance(definition, Mapping):
        sources.append(definition)
    for source in sources:
        for key in (
            "estimand",
            "target",
            "explanatory_condition",
            "representation_scope",
            "evidence_surface_mode",
            "research_scope_rule_sha256",
        ):
            if key in out:
                continue
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                out[key] = value
    if "evidence_surface_mode" not in out and isinstance(frozen, Mapping):
        mode = frozen.get("evidence_surface_mode")
        if isinstance(mode, str) and mode.strip():
            out["evidence_surface_mode"] = mode
    return out


def _cards_for_identities(
    identities: Sequence[Any],
    frozen: Mapping[str, Any] | None,
    draft: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    grounded = frozen.get("grounded_candidates") if isinstance(frozen, Mapping) else None
    if isinstance(grounded, list):
        for card in grounded:
            if isinstance(card, Mapping) and card.get("candidate_id"):
                by_id[str(card["candidate_id"])] = card
    draft_cards: list[Mapping[str, Any]] = []
    if isinstance(draft, Mapping) and isinstance(draft.get("candidates"), list):
        draft_cards = [
            card if isinstance(card, Mapping) else {}
            for card in draft["candidates"]
        ]
    aligned: list[Mapping[str, Any]] = []
    for index, identity in enumerate(identities):
        card = by_id.get(str(getattr(identity, "candidate_id", "") or ""))
        if card is None and index < len(draft_cards):
            card = draft_cards[index]
        aligned.append(card or {})
    return aligned


def _selected_candidate_block(
    identity: Any,
    card: Mapping[str, Any],
    *,
    packet_version: str | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_card_projection import CardProjectionError, project_material_card

    # Persist validates authored bindings; this direct packet helper keeps a
    # malformed outer shape intact so the Critic schema can reject it.
    authored_bindings = card.get("available_data_bindings")
    has_bindings = "available_data_bindings" in card
    projection_source = dict(card)
    projection_source.pop("available_data_bindings", None)
    try:
        card = project_material_card(projection_source)
    except CardProjectionError as exc:
        raise HficSessionError(exc.code, detail=exc.detail) from exc
    if has_bindings:
        card["available_data_bindings"] = authored_bindings
    required_caps = card.get("required_capability_ids") or []
    if not isinstance(required_caps, list):
        required_caps = []
    decision_unlocked = str(card.get("decision_unlocked") or "NOT_DECLARED_IN_DRAFT")
    disconfirming = str(card.get("disconfirming_prediction") or "NOT_DECLARED_IN_DRAFT")
    bindings = card.get("available_data_bindings", [])
    if isinstance(bindings, list):
        # The direct Critic transport still validates each list item. Only an
        # invalid outer shape is left intact for the packet schema to reject.
        try:
            project_material_card({"available_data_bindings": bindings})
        except CardProjectionError as exc:
            raise HficSessionError(exc.code, detail=exc.detail) from exc
        # Critic strings are narrative transport, never typed resolver input.
        # Encode authored objects reversibly; retain legacy strings verbatim.
        bindings = [
            _canonical_bytes(item).decode("utf-8") if isinstance(item, Mapping) else item
            for item in bindings
        ]
    block: dict[str, Any] = {
        "candidate_id": identity.candidate_id,
        "claim": str(card.get("claim") or ""),
        "nearest_prior_and_difference": str(
            card.get("nearest_prior_and_difference")
            or card.get("material_difference_from_prior")
            or "NOT_DECLARED_IN_DRAFT"
        ),
        "actor_counterparty": str(card.get("actor_counterparty") or ""),
        "mechanism": str(card.get("mechanism") or ""),
        "claim_form": str(card.get("claim_form") or "CAUSAL"),
        "why_not_arbitraged": str(card.get("why_not_arbitraged") or "NOT_DECLARED_IN_DRAFT"),
        "population": str(card.get("population") or ""),
        "decision_timestamp": str(card.get("decision_timestamp") or ""),
        "primary_x": str(card.get("primary_x_family") or ""),
        "primary_y": str(card.get("primary_y") or ""),
        "horizon_notional": str(card.get("horizon_notional") or ""),
        "disconfirming_prediction": disconfirming,
        "negative_control": str(card.get("negative_control") or ""),
        "alternative_world": str(card.get("alternative_world") or "NOT_DECLARED_IN_DRAFT"),
        "confounders": card["confounders"],
        "pit_leakage_survivorship_risks": card["pit_leakage_survivorship_risks"],
        "execution_capacity_risks": card["execution_capacity_risks"],
        "available_data_bindings": bindings,
        "missing_or_forward_only_data": card["missing_or_forward_only_data"],
        "proposed_method": str(card.get("proposed_method") or "NOT_DECLARED_IN_DRAFT"),
        "cheapest_falsifier": str(card.get("cheapest_falsifier") or ""),
        "pass_fail_inconclusive_semantics": str(
            card.get("pass_fail_inconclusive_semantics") or "NOT_DECLARED_IN_DRAFT"
        ),
        "decision_unlocked": decision_unlocked,
        "_required_capability_ids": [str(item) for item in required_caps],
    }
    if "pit_component_provenance" in card:
        block["pit_component_provenance"] = card["pit_component_provenance"]
    if "mundane_alternative" in card:
        block["mundane_alternative"] = card["mundane_alternative"]
    if packet_version == CRITIC_PACKET_VERSION_CURRENT:
        block.update(_freeze_owned_grounding_fields(card))
    from solana_alpha_lab.factory.hfic_grounded_discovery import card_claim_scope

    block.update(card_claim_scope(card))
    # A list-scoped candidate carries its machine rule and statement on every packet version; text cannot widen it.
    if card.get("research_scope_rule_sha256") is not None:
        block["research_scope_rule_sha256"] = str(card["research_scope_rule_sha256"])
        block["research_scope_statement"] = str(card.get("research_scope_statement") or "")
    return block


def _provisional_lane(required_caps: Sequence[str]) -> dict[str, Any]:
    return {
        "value": "DATA_OPTION_CANDIDATE",
        "required_capability_ids": [str(item) for item in required_caps],
        "required_query_recipe_ids": [],
        "required_data_bindings": [],
        "exact_gap": "PROVISIONAL_LANE_NOT_YET_CLASSIFIED",
    }


def _build_runner_up_critic_packet(
    primary_packet: Mapping[str, Any],
    *,
    runner_up: Any,
    runner_up_card: Mapping[str, Any],
    packet_version: str,
) -> dict[str, Any]:
    packet = copy.deepcopy(dict(primary_packet))
    if "prior_memory" in primary_packet:
        packet["prior_memory"] = primary_packet["prior_memory"]
    selected = _selected_candidate_block(
        runner_up,
        runner_up_card,
        packet_version=packet_version,
    )
    required_caps = selected.pop("_required_capability_ids")
    packet["selected_candidate"] = selected
    packet["provisional_lane"] = _provisional_lane(required_caps)
    _rebind_runner_up_grounded_evidence(packet, runner_up_card)
    return packet


def _proven_runner_scope(
    card: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> dict[str, str]:
    """Scope axes that belong to this runner-up card, not the primary candidate."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import card_claim_scope

    proven = card_claim_scope(card)
    mode = card.get("evidence_surface_mode")
    if isinstance(mode, str) and mode.strip():
        proven["evidence_surface_mode"] = mode
    if "evidence_surface_mode" not in proven:
        grounded = packet.get("grounded_evidence")
        scope = grounded.get("candidate_scope") if isinstance(grounded, Mapping) else None
        mode = scope.get("evidence_surface_mode") if isinstance(scope, Mapping) else None
        if not isinstance(mode, str) or not mode.strip():
            mode = packet.get("evidence_surface_mode")
        if isinstance(mode, str) and mode.strip():
            proven["evidence_surface_mode"] = mode
    return proven


_COMPUTED_LOOK_KEYS = (
    "descriptive_readout",
    "result",
    "result_sha256",
    "result_refs",
    "queries",
    "priors",
)


def _executed_scope_matches(executed: Mapping[str, Any], proven: Mapping[str, str]) -> bool:
    """True only when every labeled axis on both sides is the same look.

    An axis present on only one side is a mismatch. A sparse executed scope
    must not keep its result under a runner-up target or estimand it never had.
    """

    from solana_alpha_lab.factory.hfic_grounded_discovery import relate_look_scope

    return relate_look_scope(executed, proven) == "LOOK_SCOPE_MATCH" and (
        str(executed.get("evidence_surface_mode") or "").strip()
        == str(proven.get("evidence_surface_mode") or "").strip()
    )


def _rebind_runner_up_grounded_evidence(
    packet: dict[str, Any],
    card: Mapping[str, Any],
) -> None:
    """Keep discovery numbers only when they were computed for this candidate.

    A copied primary packet otherwise drops the executed scope, its prior
    relations, and the computed look. A complete runner-up scope is recorded
    on its own and is not a relabel of the primary result.
    """

    grounded = packet.get("grounded_evidence")
    if not isinstance(grounded, Mapping):
        return
    executed = grounded.get("candidate_scope")
    executed_scope = executed if isinstance(executed, Mapping) else {}
    proven = _proven_runner_scope(card, packet)
    same_look = _executed_scope_matches(executed_scope, proven)
    drop = {"candidate_scope", "prior_scope_relations", "canonical_prior_comparison"}
    if not same_look:
        drop.update(_COMPUTED_LOOK_KEYS)
    body = {key: value for key, value in grounded.items() if key not in drop}
    if not same_look:
        from solana_alpha_lab.factory.hfic_grounded_discovery import relate_look_scope

        body["look_confirms_selected"] = False
        body["look_scope_relation"] = relate_look_scope(executed_scope, proven)
        body["look_context_result_refs"] = list(
            grounded.get("result_refs") or grounded.get("look_context_result_refs") or []
        )
    from solana_alpha_lab.factory.hfic_grounded_discovery import _scope_missing

    if not _scope_missing(proven, prefix=""):
        body["candidate_scope"] = dict(proven)
        if not same_look:
            body["priors"] = []
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            bind_prior_scope_evidence,
        )

        capsules = list((packet.get("prior_memory") or {}).get("capsules") or [])
        try:
            body = bind_prior_scope_evidence(body, canonical_priors=capsules)
        except GroundedDiscoveryError as exc:
            raise HficSessionError(exc.code) from exc
    packet["grounded_evidence"] = body


def _blank_optional(value: object) -> bool:
    return value is None or value == "" or value == []


def _attach_runner_up_fields(
    payload: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    for key in (
        "runner_up_critic_input_packet_sha256",
        "runner_up_definition_sha256",
        "runner_up_display_ordinal",
        "primary_critic_input_packet_sha256",
        "primary_critic_result_sha256",
        "primary_critic_terminal",
        "runner_up_failover_used",
        "critic_screen_count",
    ):
        if key in source and source[key] is not None:
            payload[key] = source[key]


def _session_state_of(
    existing: Mapping[str, Any] | None,
    frozen: Mapping[str, Any],
) -> str:
    if existing is not None:
        return str(existing.get("session_state") or "")
    return str(frozen.get("session_state") or "")


def _screening_identity(
    frozen: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
) -> tuple[str, str, str]:
    """Return (candidate_id, packet_sha, definition_sha) for the active Critic bind."""
    source = existing if existing is not None else frozen
    state = _session_state_of(existing, frozen)
    failover_started = state == RUNNER_UP_AWAITING_CRITIC
    if not failover_started and state == "AWAITING_CLASSIFICATION":
        pending = source.get("critic_result")
        runner_up_id = str(source.get("runner_up_candidate_id") or "")
        if (
            isinstance(pending, Mapping)
            and runner_up_id
            and pending.get("selected_candidate_id") == runner_up_id
        ):
            failover_started = True
    if failover_started:
        candidate_id = str(source.get("runner_up_candidate_id") or "")
        packet_sha = str(source.get("runner_up_critic_input_packet_sha256") or "")
        definition_sha = str(source.get("runner_up_definition_sha256") or "")
        if not candidate_id or len(packet_sha) != 64 or len(definition_sha) != 64:
            raise HficSessionError("RUNNER_UP_PACKET_MISSING")
        return candidate_id, packet_sha, definition_sha
    candidate_id = str(source.get("selected_candidate_id") or "")
    packet_sha = str(source.get("critic_input_packet_sha256") or "")
    definition_sha = str(source.get("selected_definition_sha256") or "")
    return candidate_id, packet_sha, definition_sha


def _require_declared_runner_up_packet(*sources: Mapping[str, Any] | None) -> None:
    prompt_version = ""
    declared_sha: str | None = None
    packet: Mapping[str, Any] | None = None
    for source in sources:
        if source is None:
            continue
        prompt_version = str(source.get("prompt_version") or prompt_version or "")
        observed_sha = source.get("runner_up_critic_input_packet_sha256")
        if isinstance(observed_sha, str) and len(observed_sha) == 64:
            declared_sha = observed_sha
        observed_packet = source.get("runner_up_critic_input_packet")
        if isinstance(observed_packet, Mapping):
            packet = observed_packet
    if (
        prompt_version == PROMPT_VERSION
        and declared_sha is not None
        and packet is None
    ):
        raise HficSessionError("RUNNER_UP_PACKET_MISSING")


def _require_fresh_v12_runner_up_declaration(
    existing: Mapping[str, Any] | None,
    frozen: Mapping[str, Any],
) -> None:
    if existing is not None:
        return
    if str(frozen.get("prompt_version") or "") != PROMPT_VERSION:
        return
    if not frozen.get("selected_candidate_id"):
        return
    if not frozen.get("runner_up_candidate_id"):
        return
    declared_sha = frozen.get("runner_up_critic_input_packet_sha256")
    if not (isinstance(declared_sha, str) and len(declared_sha) == 64):
        raise HficSessionError("RUNNER_UP_PACKET_MISSING")


def _runner_up_failover_eligible(
    frozen: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
    terminal: str,
) -> bool:
    if terminal not in _KILL_TERMINALS:
        return False
    state = _session_state_of(existing, frozen)
    if state == RUNNER_UP_AWAITING_CRITIC:
        return False
    source = existing if existing is not None else frozen
    if state == "AWAITING_CLASSIFICATION":
        pending = source.get("critic_result")
        runner_up_id = source.get("runner_up_candidate_id")
        if (
            isinstance(pending, Mapping)
            and isinstance(runner_up_id, str)
            and pending.get("selected_candidate_id") == runner_up_id
        ):
            return False
    elif state not in {
        "",
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        "CRITIC_RESULT_READY",
    }:
        return False
    runner_up_id = source.get("runner_up_candidate_id")
    packet_sha = source.get("runner_up_critic_input_packet_sha256")
    packet = source.get("runner_up_critic_input_packet")
    definition_sha = source.get("runner_up_definition_sha256")
    if not isinstance(runner_up_id, str) or not runner_up_id:
        return False
    if not isinstance(packet_sha, str) or len(packet_sha) != 64:
        return False
    if not isinstance(definition_sha, str) or len(definition_sha) != 64:
        return False
    if not isinstance(packet, Mapping):
        return False
    return True


def _computed_look_linked(evidence: Mapping[str, Any]) -> bool:
    """True when this packet still carries the look it was computed for."""

    refs = evidence.get("result_refs")
    result = evidence.get("result")
    digest = evidence.get("result_sha256")
    if not isinstance(refs, list) or not refs:
        return False
    if not all(isinstance(item, str) and item.strip() for item in refs):
        return False
    if not isinstance(result, Mapping) or not isinstance(digest, str) or not digest.strip():
        return False
    from solana_alpha_lab.factory.hfic_grounded_discovery import result_sha256

    return digest == result_sha256(result)


def _runner_up_missing_own_computed_look(frozen: Mapping[str, Any]) -> bool:
    """A runner-up discovery packet with no linked look must not pass as science.

    Packets that never carried grounded evidence stay on the ordinary classifier
    path. A same-scope runner-up that still has the computed result, its hash,
    and result refs is linked and is not this case.
    """

    runner_id = frozen.get("runner_up_candidate_id")
    if not isinstance(runner_id, str) or not runner_id:
        return False
    if frozen.get("selected_candidate_id") != runner_id:
        return False
    packet = frozen.get("critic_input_packet")
    if not isinstance(packet, Mapping):
        return False
    evidence = packet.get("grounded_evidence")
    if not isinstance(evidence, Mapping):
        return False
    return not _computed_look_linked(evidence)


def _classifier_frozen_view(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
) -> dict[str, Any]:
    view = dict(frozen)
    runner_up_id = frozen.get("runner_up_candidate_id")
    if (
        runner_up_id
        and critic_result.get("selected_candidate_id") == runner_up_id
    ):
        view["selected_candidate_id"] = runner_up_id
        view["selected_definition_sha256"] = frozen.get("runner_up_definition_sha256")
        view["critic_input_packet_sha256"] = frozen.get(
            "runner_up_critic_input_packet_sha256"
        )
        packet = frozen.get("runner_up_critic_input_packet")
        if isinstance(packet, Mapping):
            view["critic_input_packet"] = packet
    return view


def _accepted_capability_ids_from_preflight(
    preflight_receipt: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(preflight_receipt, Mapping):
        return []
    packet = preflight_receipt.get("forge_context_packet")
    if not isinstance(packet, Mapping):
        return []
    ids = packet.get("capability_ids") or []
    if not isinstance(ids, list):
        return []
    return [str(item) for item in ids if isinstance(item, str) and item]


def _context_packet_sha_from_preflight(
    preflight_receipt: Mapping[str, Any] | None,
) -> str:
    if not isinstance(preflight_receipt, Mapping):
        return "0" * 64
    digest = preflight_receipt.get("forge_context_packet_sha256")
    if isinstance(digest, str) and len(digest) == 64:
        return digest.lower()
    packet = preflight_receipt.get("forge_context_packet")
    if isinstance(packet, Mapping):
        return hashlib.sha256(_canonical_bytes(packet)).hexdigest()
    return "0" * 64


def _ground_v12_candidates(
    candidates: Sequence[Mapping[str, Any]],
    identities: Sequence[Any],
    *,
    repo_root: Any,
    preflight_receipt: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.hfic_grounding import (
        HficGroundingError,
        ground_candidate,
        structural_signature_v1_sha256,
    )

    accepted = _accepted_capability_ids_from_preflight(preflight_receipt)
    if not accepted and repo_root is not None:
        from solana_alpha_lab.factory.hfic_preflight import (
            enumerate_accepted_capabilities,
        )

        accepted = [
            str(item["capability_id"])
            for item in enumerate_accepted_capabilities(Path(repo_root))
        ]
    context_sha = _context_packet_sha_from_preflight(preflight_receipt)
    enriched: list[dict[str, Any]] = []
    for card, identity in zip(candidates, identities, strict=True):
        try:
            grounding = ground_candidate(
                card,
                repo_root=Path(repo_root),
                context_packet_sha256=context_sha,
                accepted_capability_ids=accepted,
            )
            signature = structural_signature_v1_sha256(card)
        except HficGroundingError as exc:
            raise HficSessionError(str(exc)) from exc
        enriched_card = dict(card)
        enriched_card["candidate_id"] = identity.candidate_id
        enriched_card["grounding"] = grounding
        enriched_card["structural_signature_v1_sha256"] = signature
        enriched.append(enriched_card)
    return enriched


def _diagnostics_for_receipt(
    *,
    prompt_version: str,
    grounded_candidates: Sequence[Mapping[str, Any]] | None,
    session_meta: Mapping[str, Any],
) -> dict[str, Any] | None:
    if prompt_version != PROMPT_VERSION:
        return None
    from solana_alpha_lab.factory.hfic_grounding import (
        session_diagnostics_from_candidates,
    )

    return session_diagnostics_from_candidates(
        list(grounded_candidates or []),
        session_meta,
    )


def _assert_vision_integrity_for_surface(
    preflight_receipt: Mapping[str, Any] | None,
    *,
    prompt_version: str | None = None,
) -> None:
    """NO_WORTHY / selected-candidate paths require VISION_INTEGRITY=PASS.

    Fresh HFIC sessions under the current protocol must not persist a
    scientifically interpretable terminal from a packet whose declared
    evidence surface was silently incomplete.  A vision failure is typed
    FORGE_VISION_INTEGRITY_BLOCKED, never NO_WORTHY_HYPOTHESIS.

    Fail-closed: for drafts under the current protocol, an absent or
    malformed ``vision_integrity`` receipt is BLOCKED, not PASS.  Legacy
    drafts predating vision receipts are out of scope here and are already
    fenced by the fresh-session stale-draft rejection.
    """
    if not isinstance(preflight_receipt, Mapping):
        # A missing receipt on a freeze under the current protocol is a
        # malformed machine path, but legacy drafts legitimately carry no
        # machine preflight receipt at all; the stale-fresh-session fence
        # covers the fresh-session case, so absence stays out of scope here.
        return
    packet = preflight_receipt.get("forge_context_packet")
    if not isinstance(packet, Mapping):
        if prompt_version == PROMPT_VERSION:
            raise HficSessionError("FORGE_VISION_INTEGRITY_BLOCKED")
        return
    vision = packet.get("vision_integrity")
    if prompt_version == PROMPT_VERSION and not isinstance(vision, Mapping):
        # Fail closed: a current-protocol packet without a vision receipt
        # is not provably complete — absence is not PASS.
        raise HficSessionError("FORGE_VISION_INTEGRITY_BLOCKED")
    if isinstance(vision, Mapping) and vision.get("status") != "PASS":
        raise HficSessionError("FORGE_VISION_INTEGRITY_BLOCKED")


def _ordinary_discovery_requested(
    draft: Mapping[str, Any],
    preflight_receipt: Mapping[str, Any] | None,
) -> bool:
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        DISCOVERY_CONTRACT_VERSION,
        ORDINARY_GROUNDED_DISCOVERY_V1,
    )

    surface = ""
    contract = ""
    if isinstance(preflight_receipt, Mapping):
        surface = str(preflight_receipt.get("evidence_surface_mode") or "")
        contract = str(preflight_receipt.get("discovery_contract_version") or "")
    machine_contract = (
        str(draft.get("discovery_contract_version") or "") == DISCOVERY_CONTRACT_VERSION
        or surface == ORDINARY_GROUNDED_DISCOVERY_V1
        or contract == DISCOVERY_CONTRACT_VERSION
    )
    return machine_contract


def _bind_selected_look(
    grounded: Mapping[str, Any],
    selected_card: Mapping[str, Any],
    *,
    store: Any,
    strict: bool = True,
) -> dict[str, Any]:
    """Keep a confirming look, detach a narrower idea, stop a contradiction.

    The durable look owns its scope. A selected card that names a different
    population or decision moment stops. A different or one-sided label is
    not a scientific record and is saved later as an idea, without that result.
    """

    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        card_claim_scope,
        relate_look_scope,
        stored_look_scope,
    )

    look_scope = stored_look_scope(store, grounded) if store is not None else None
    if look_scope is None:
        raw = grounded.get("candidate_scope")
        look_scope = dict(raw) if isinstance(raw, Mapping) else {}
    relation = relate_look_scope(look_scope, card_claim_scope(selected_card))
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_holder_claim_identity

    result = grounded.get("result")
    identity = temporal_holder_claim_identity(result) if isinstance(result, Mapping) else {}
    if identity and any(selected_card.get(key) != value for key, value in identity.items()):
        raise HficSessionError("LOOK_SCOPE_CONTRADICTION")
    if relation == "LOOK_SCOPE_CONTRADICTION" and strict:
        raise HficSessionError("LOOK_SCOPE_CONTRADICTION")
    if relation == "LOOK_SCOPE_MATCH":
        body = dict(grounded)
        body["candidate_scope"] = dict(look_scope)
        body["look_scope_relation"] = relation
        body["look_confirms_selected"] = True
        return body
    kept = {
        key: value
        for key, value in grounded.items()
        if key
        not in {
            "descriptive_readout",
            "result",
            "result_sha256",
            "result_refs",
            "queries",
            "priors",
            "prior_scope_relations",
            "canonical_prior_comparison",
            "candidate_scope",
        }
    }
    kept["candidate_scope"] = card_claim_scope(selected_card)
    kept["look_scope_relation"] = relation
    kept["look_confirms_selected"] = False
    kept["look_context_result_refs"] = list(grounded.get("result_refs") or [])
    return kept


def _foreign_look_blocks_scientific_terminal(
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
) -> bool:
    view = _classifier_frozen_view(frozen, critic_result)
    packet = view.get("critic_input_packet")
    if not isinstance(packet, Mapping):
        return False
    evidence = packet.get("grounded_evidence")
    return isinstance(evidence, Mapping) and evidence.get("look_confirms_selected") is False


def _enforce_ordinary_grounded_evidence(
    draft: Mapping[str, Any],
    *,
    preflight_receipt: Mapping[str, Any] | None,
    store: Any,
) -> None:
    if not _ordinary_discovery_requested(draft, preflight_receipt):
        return
    evidence = draft.get("grounded_evidence")
    if not isinstance(evidence, Mapping):
        raise HficSessionError("GROUNDED_EVIDENCE_REQUIRED")
    if store is None:
        raise HficSessionError("GROUNDED_STORE_REQUIRED")
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        assert_computed_grounded_evidence,
    )

    try:
        expected_scope = None
        if isinstance(preflight_receipt, Mapping):
            expected_scope = preflight_receipt.get("search_key_sha256")
        assert_computed_grounded_evidence(
            store,
            evidence,
            expected_journal_scope=(
                str(expected_scope) if isinstance(expected_scope, str) else None
            ),
        )
    except GroundedDiscoveryError as exc:
        raise HficSessionError(exc.code) from exc


def _no_worthy_grounded_evidence(draft: Mapping[str, Any]) -> dict[str, Any] | None:
    evidence = draft.get("grounded_evidence")
    if not isinstance(evidence, Mapping):
        return None
    from solana_alpha_lab.factory.hfic_grounded_discovery import no_worthy_scope_record

    return no_worthy_scope_record(evidence)


def _project_draft_cards(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.hfic_card_projection import CardProjectionError, project_material_card

    cards = draft.get("candidates")
    if not isinstance(cards, list):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    projected = []
    for index, card in enumerate(cards):
        if not isinstance(card, Mapping):
            raise HficSessionError("HFIC_PROTOCOL_INVALID")
        try:
            projected.append(project_material_card(card))
        except CardProjectionError as exc:
            detail = {**exc.detail, "candidate_ordinal": index + 1,
                      "candidate_label": card.get("label") if isinstance(card.get("label"), str) else None}
            if "field_path" in detail:
                detail["field_path"] = f"candidates[{index}].{detail['field_path']}"
            raise HficSessionError(exc.code, detail=detail) from exc
    return projected


def freeze_draft(
    draft: Mapping[str, Any],
    *,
    preflight_receipt: Mapping[str, Any] | None = None,
    store: Any = None,
    repo_root: Any = None,
    next_action_draft: Mapping[str, Any] | None = None,
    verify_current_market_identity: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    if not isinstance(draft, Mapping):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    _reject_stale_fresh_session_draft(draft, preflight_receipt)
    packet_version = _draft_packet_version(draft)
    prompt_version = _draft_prompt_version(draft)
    if repo_root is not None:
        _validate_json_schema(draft, _draft_schema_path(repo_root, draft))
    candidates = _project_draft_cards(draft)
    floor = 0 if _ordinary_discovery_requested(draft, preflight_receipt) else 4
    journal_for_cap = (preflight_receipt or {}).get("search_key_sha256")
    ceiling = _max_candidates_for(store, journal_for_cap)
    if not isinstance(candidates, list) or not (floor <= len(candidates) <= ceiling):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    try:
        identities = assign_portfolio_ids(candidates)
    except HficIdentityError as exc:
        raise HficSessionError(str(exc)) from exc

    _enforce_ordinary_grounded_evidence(
        draft,
        preflight_receipt=preflight_receipt,
        store=store,
    )
    _validate_fresh_draft_scopes(draft, store=store, identities=identities)
    grounded_candidates: list[dict[str, Any]] | None = None
    if packet_version in ("1.2", "1.3"):
        if repo_root is None:
            raise HficSessionError("HFIC_PROTOCOL_INVALID")
        grounded_candidates = _ground_v12_candidates(
            candidates,
            identities,
            repo_root=repo_root,
            preflight_receipt=preflight_receipt,
        )

    selected_ref = draft.get("selected_candidate_ref")
    if selected_ref in (None, ""):
        return _freeze_no_worthy(
            draft,
            identities=identities,
            preflight_receipt=preflight_receipt,
            store=store,
            repo_root=repo_root,
            next_action_draft=next_action_draft,
            grounded_candidates=grounded_candidates,
            prompt_version=prompt_version,
            packet_version=packet_version,
            verify_current_market_identity=verify_current_market_identity,
            persist=persist,
        )

    if next_action_draft is not None:
        raise HficSessionError("HFIC_NEXT_ACTION_FORBIDDEN_FOR_SELECTED")

    _assert_vision_integrity_for_surface(
        preflight_receipt, prompt_version=prompt_version
    )
    selected_index = _resolve_ref(selected_ref, identities)
    if selected_index < 0:
        raise HficSessionError("SELECTED_CANDIDATE_MISSING")
    optional_single = (
        _ordinary_discovery_requested(draft, preflight_receipt)
        and len(identities) == 1
        and not str(draft.get("runner_up_candidate_ref") or "").strip()
        and not str(draft.get("strongest_rejected_alternative") or "").strip()
    )
    if optional_single:
        runner_up_index = -1
        rejected_index = -1
    else:
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
    runner_up = None if runner_up_index < 0 else identities[runner_up_index]
    rejected = None if rejected_index < 0 else identities[rejected_index]
    selected_card = candidates[selected_index]
    runner_up_card = None if runner_up_index < 0 else candidates[runner_up_index]
    closed_family_ledger = ledger_from_receipt(
        preflight_receipt if isinstance(preflight_receipt, Mapping) else None
    )
    closed_or_suppressed_collision_count: int | None = None
    if store is not None and closed_family_ledger:
        closed_or_suppressed_collision_count = 0
        for card in candidates:
            hit = candidate_hard_close_entry(card, closed_family_ledger)
            if hit is not None:
                closed_or_suppressed_collision_count += 1
                raise HficSessionError("CLOSED_FAMILY_REOPEN", detail={
                    "stage": "CANDIDATE_SUPPRESSION", "source_terminal": hit.get("terminal"),
                    "scope_kind": hit.get("scope_kind"), "scope_id": hit.get("scope_id"),
                    "source_receipt": hit.get("source_receipt"),
                    "next_action": "KEEP_TYPED_CLOSE_SELECT_AUTHORIZED_DISTINCT_SCOPE",
                })
    elif store is not None:
        closed_or_suppressed_collision_count = 0
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
        preflight_receipt, existing_ladder, bound = _bind_store_freeze_preflight(
            draft,
            preflight_receipt,
            store=store,
            repo_root=repo_root,
            memory_as_of=memory_as_of,
            verify_current_market_identity=verify_current_market_identity,
        )
        if existing_ladder is not None:
            return existing_ladder
    git_head = "0" * 40
    if bound is not None:
        git_head = str(bound["live_git_head"])
    elif isinstance(preflight_receipt, Mapping):
        maybe_head = preflight_receipt.get("live_git_head")
        if isinstance(maybe_head, str) and len(maybe_head) == 40:
            git_head = maybe_head.lower()
    critic_packet_version = _critic_packet_version(packet_version)
    selected_transport = (
        grounded_candidates[selected_index]
        if grounded_candidates is not None
        else selected_card
    )
    selected_block = _selected_candidate_block(
        selected,
        selected_transport,
        packet_version=critic_packet_version,
    )
    if critic_packet_version == CRITIC_PACKET_VERSION_CURRENT:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CRITIC_PACKET_GROUNDING_MISMATCH,
            assert_packet_grounding_consistent,
        )

        context_sha = _context_packet_sha_from_preflight(preflight_receipt)
        grounding = selected_transport.get("grounding")
        if not isinstance(grounding, Mapping):
            raise HficSessionError(CRITIC_PACKET_GROUNDING_MISMATCH)
        try:
            assert_packet_grounding_consistent(
                selected_block,
                selected_card,
                grounding,
                context_sha,
            )
        except ValueError as exc:
            raise HficSessionError(str(exc)) from exc
    selected_required_caps = selected_block.pop("_required_capability_ids")
    packet = {
        "packet_schema": "smial.hypothesis-critic-input",
        "packet_version": critic_packet_version,
        "generator_prompt_version": prompt_version,
        "generated_at": memory_as_of,
        "live_git_head": git_head,
        "research_memory_as_of": memory_as_of,
        "owner_focus": str(draft.get("owner_focus") or "AUTO"),
        "authority": _authority_zero(draft.get("authority")),
        "holdouts_not_touched": list(draft.get("holdouts_not_touched") or []),
        "truth_roots_used": truth_roots,
        "prior_work_queries": prior_work,
        "selected_candidate": selected_block,
        "provisional_lane": _provisional_lane(selected_required_caps),
        "provisional_execution_unit": "NONE",
        "strongest_rejected_alternative": (
            "NONE" if rejected is None else rejected.candidate_id
        ),
        "known_unknowns": critic_known_unknowns_with_closed_families(
            family_hard_close_terminals(closed_family_ledger)
        ),
        "non_claims": draft.get("non_claims") or ["NO_ALPHA"],
    }
    if isinstance(preflight_receipt, Mapping):
        forge_packet = preflight_receipt.get("forge_context_packet")
        if (
            isinstance(forge_packet, Mapping)
            and forge_packet.get("ladder_representation_id")
            == "NORMALIZED_TRAJECTORY_V1"
        ):
            from solana_alpha_lab.factory.hfic_representation_ladder import (
                stamp_verified_v1_fields_onto_mapping,
            )

            stamp_verified_v1_fields_onto_mapping(packet, forge_packet)
        elif (
            isinstance(forge_packet, Mapping)
            and forge_packet.get("ladder_representation_id") == "NORMALIZED_TRAJECTORY_EPISODES_V1"
            and isinstance(forge_packet.get("normalized_trajectory_episodes_v1"), Mapping)
        ):
            # The episode profile is context for the Critic: scope-bound, anonymous, prefix only.
            from solana_alpha_lab.factory.normalized_trajectory_episodes_v1 import (
                EpisodeProfileError,
                validate_episode_payload,
            )

            try:
                validate_episode_payload(
                    forge_packet["normalized_trajectory_episodes_v1"],
                    expected_rule_sha256=selected_block.get("research_scope_rule_sha256"),
                )
            except EpisodeProfileError as exc:
                raise HficSessionError(exc.code) from exc
            packet["ladder_representation_id"] = "NORMALIZED_TRAJECTORY_EPISODES_V1"
            packet["normalized_trajectory_episodes_v1"] = dict(forge_packet["normalized_trajectory_episodes_v1"])
            packet["representation_payload_sha256"] = str(forge_packet.get("representation_payload_sha256") or "")
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
    _stamp_split_identity(packet, bound, preflight_receipt)
    if epoch:
        packet.setdefault("evidence_epoch_sha256", epoch)
    if not focus_key:
        focus_key = focus_key_sha256(owner_focus)
    if epoch and not search_key:
        search_key = search_key_sha256(
            epoch,
            owner_focus,
            prompt_version,
            (
                str(bound.get("memory_eligibility_sha256") or "")
                if bound is not None
                else (
                    str(preflight_receipt.get("memory_eligibility_sha256") or "")
                    if isinstance(preflight_receipt, Mapping)
                    else None
                )
            )
            or None,
            (
                str(preflight_receipt.get("evidence_surface_mode") or "")
                if isinstance(preflight_receipt, Mapping)
                else None
            )
            or None,
        )
    if search_key:
        session_id = "HFIC-SESS-" + search_key[:16].upper()
    else:
        session_id = "HFIC-SESS-" + canonical_sha256(
            {
                "candidate_ids": [item.candidate_id for item in identities],
                "selected": selected.candidate_id,
                "prompt_version": prompt_version,
            }
        )[:16].upper()
    _bind_packet_session_id(packet, session_id)
    if critic_packet_version == CRITIC_PACKET_VERSION_CURRENT:
        from solana_alpha_lab.factory.hfic_memory_policy import HficMemoryPolicyError

        snapshot_digest = store_digest if isinstance(store_digest, str) else "0" * 64
        try:
            packet["prior_memory"] = build_prior_memory_snapshot(
                store,
                store_inventory_digest=snapshot_digest,
                repo_root=repo_root,
                as_of=bound["session_started_at"] if bound is not None else None,
            )
        except (PriorMemoryCapacityError, PriorMemoryUnidentifiedError, HficMemoryPolicyError) as exc:
            raise HficSessionError(exc.code) from exc
    grounded = draft.get("grounded_evidence")
    if isinstance(grounded, Mapping):
        from solana_alpha_lab.factory.hfic_grounded_discovery import stored_look_scope

        look_scope = stored_look_scope(store, grounded) if store is not None else None
        if look_scope or (
            isinstance(grounded.get("result_refs"), list) and grounded.get("result_refs")
        ):
            grounded = _bind_selected_look(
                grounded,
                selected_card if isinstance(selected_card, Mapping) else {},
                store=store,
            )
    if isinstance(grounded, Mapping) and grounded.get("look_confirms_selected") is not False:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            bind_prior_scope_evidence,
        )

        try:
            packet["grounded_evidence"] = bind_prior_scope_evidence(
                grounded,
                canonical_priors=list(
                    (packet.get("prior_memory") or {}).get("capsules") or []
                ),
            )
        except GroundedDiscoveryError as exc:
            raise HficSessionError(exc.code) from exc
    elif isinstance(grounded, Mapping):
        packet["grounded_evidence"] = grounded
    handed = packet.get("grounded_evidence")
    if isinstance(handed, Mapping):
        from solana_alpha_lab.factory.hfic_research_universe_policy import claim_fields

        bound_policy = claim_fields(handed.get("result") if isinstance(handed.get("result"), Mapping) else None)
        if bound_policy:
            handed = {**dict(handed), "universe_policy": bound_policy}
            packet["grounded_evidence"] = handed
    if isinstance(handed, Mapping) and store is not None:
        result = handed.get("result") if isinstance(handed.get("result"), Mapping) else {}
        if isinstance(result, Mapping) and result.get("schema") == "smial.hfic-temporal-query":
            from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks

            journal = str(handed.get("journal_scope") or "")
            viewed = [
                {
                    "query_id": item.get("query_id") or (item.get("result") or {}).get("query_id"),
                    "spec_sha256": item.get("spec_sha256"),
                    "search_tier": item.get("search_tier"),
                    "look_class": item.get("look_class"),
                    "new_look": item.get("new_look"),
                    "result_sha256": item.get("result_sha256"),
                }
                for item in list_discovery_looks(store, journal)
            ]
            packet["grounded_evidence"] = {**dict(handed), "viewed_queries": viewed}
    if repo_root is not None:
        _validate_json_schema(
            packet,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_input_v1.schema.json",
        )
    runner_up_packet = None
    if runner_up is None:
        runner_up_transport = None
    else:
        runner_up_transport = (
            grounded_candidates[runner_up_index]
            if grounded_candidates is not None
            else runner_up_card
        )
    if runner_up is not None and critic_packet_version == CRITIC_PACKET_VERSION_CURRENT:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CRITIC_PACKET_GROUNDING_MISMATCH,
            assert_packet_grounding_consistent,
        )

        runner_grounding = runner_up_transport.get("grounding")
        if not isinstance(runner_grounding, Mapping):
            raise HficSessionError(CRITIC_PACKET_GROUNDING_MISMATCH)
        runner_up_packet = _build_runner_up_critic_packet(
            packet,
            runner_up=runner_up,
            runner_up_card=runner_up_transport,
            packet_version=critic_packet_version,
        )
        source_evidence = draft.get("grounded_evidence")
        if isinstance(source_evidence, Mapping) and (
            isinstance(source_evidence.get("result_refs"), list)
            and source_evidence.get("result_refs")
        ):
            built_evidence = runner_up_packet.get("grounded_evidence")
            rebound = _bind_selected_look(
                source_evidence,
                runner_up_card if isinstance(runner_up_card, Mapping) else {},
                store=store,
                strict=False,
            )
            if (
                rebound.get("look_confirms_selected") is False
                and isinstance(built_evidence, Mapping)
            ):
                if "prior_scope_relations" in built_evidence:
                    rebound["prior_scope_relations"] = built_evidence["prior_scope_relations"]
                if built_evidence.get("canonical_prior_comparison") is True:
                    rebound["canonical_prior_comparison"] = True
            if rebound.get("look_confirms_selected") is not False:
                from solana_alpha_lab.factory.hfic_grounded_discovery import (
                    GroundedDiscoveryError,
                    bind_prior_scope_evidence,
                )

                try:
                    rebound = bind_prior_scope_evidence(
                        rebound,
                        canonical_priors=list(
                            (packet.get("prior_memory") or {}).get("capsules") or []
                        ),
                    )
                except GroundedDiscoveryError as exc:
                    raise HficSessionError(exc.code) from exc
            runner_up_packet["grounded_evidence"] = rebound
        try:
            assert_packet_grounding_consistent(
                runner_up_packet["selected_candidate"],
                runner_up_card,
                runner_grounding,
                _context_packet_sha_from_preflight(preflight_receipt),
            )
        except ValueError as exc:
            raise HficSessionError(str(exc)) from exc
    elif runner_up is not None:
        runner_up_packet = _build_runner_up_critic_packet(
            packet,
            runner_up=runner_up,
            runner_up_card=runner_up_card,
            packet_version=critic_packet_version,
        )
    if runner_up_packet is not None:
        _bind_packet_session_id(runner_up_packet, session_id)
        if repo_root is not None:
            _validate_json_schema(
                runner_up_packet,
                Path(repo_root) / "catalog/schemas/hypothesis_critic_input_v1.schema.json",
            )
    packet_bytes = json.dumps(
        packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    runner_up_packet_bytes = json.dumps(
        {} if runner_up_packet is None else runner_up_packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    result = {
        "session_id": session_id,
        "session_state": "FROZEN_AWAITING_CRITIC",
        "prompt_version": prompt_version,
        "owner_focus": owner_focus,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "memory_eligibility_sha256": (
            str(bound.get("memory_eligibility_sha256") or "")
            if bound is not None
            else (
                str(preflight_receipt.get("memory_eligibility_sha256") or "")
                if isinstance(preflight_receipt, Mapping)
                else ""
            )
        )
        or None,
        "selected_candidate_id": selected.candidate_id,
        "runner_up_candidate_id": None if runner_up is None else runner_up.candidate_id,
        "rejected_alternative_id": None if rejected is None else rejected.candidate_id,
        "selected_definition_sha256": selected.full_sha256,
        "selected_display_ordinal": selected.display_ordinal,
        "runner_up_definition_sha256": None if runner_up is None else runner_up.full_sha256,
        "runner_up_display_ordinal": None if runner_up is None else runner_up.display_ordinal,
        "candidate_ids": [item.candidate_id for item in identities],
        "critic_input_packet": packet,
        "critic_input_packet_sha256": hashlib.sha256(
            packet_bytes.encode("utf-8")
        ).hexdigest(),
        "primary_critic_input_packet_sha256": hashlib.sha256(
            packet_bytes.encode("utf-8")
        ).hexdigest(),
        "runner_up_critic_input_packet": runner_up_packet,
        "runner_up_critic_input_packet_sha256": (
            None
            if runner_up_packet is None
            else hashlib.sha256(runner_up_packet_bytes.encode("utf-8")).hexdigest()
        ),
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
    if grounded_candidates is not None:
        result["grounded_candidates"] = grounded_candidates
    _copy_evidence_surface_mode(
        result,
        preflight_receipt if isinstance(preflight_receipt, Mapping) else None,
    )
    _stamp_ladder_slot(result, preflight_receipt if isinstance(preflight_receipt, Mapping) else None)
    _stamp_split_identity(result, bound, preflight_receipt)
    _stamp_market_evidence_basis(result, bound, preflight_receipt)
    _stamp_execution_identity(result, bound, preflight_receipt)
    _stamp_prefreeze_capability_repair(
        result, preflight_receipt if isinstance(preflight_receipt, Mapping) else None
    )
    if closed_or_suppressed_collision_count is not None:
        result["closed_or_suppressed_collision_count"] = (
            closed_or_suppressed_collision_count
        )
    if persist and store is not None and repo_root is not None:
        if not epoch or not search_key or not focus_key:
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        slot_rep, slot_parent = _preflight_ladder_slot(
            preflight_receipt if isinstance(preflight_receipt, Mapping) else None
        )
        existing = find_session_by_epoch_focus(
            store,
            epoch,
            focus_key,
            memory_eligibility_sha256=(
                str(bound.get("memory_eligibility_sha256") or "")
                if bound is not None
                else (
                    str(preflight_receipt.get("memory_eligibility_sha256") or "")
                    if isinstance(preflight_receipt, Mapping)
                    else ""
                )
            )
            or None,
            evidence_surface_mode=(
                str(preflight_receipt.get("evidence_surface_mode") or "")
                if isinstance(preflight_receipt, Mapping)
                else None
            )
            or None,
            ladder_representation_id=slot_rep,
            control_session_id=slot_parent,
            # An explicitly authorized additional cycle is its own slot; cycle 1 is unchanged.
            scientific_slot_sha256=(
                str(result.get("scientific_slot_sha256") or "") or None
                if int(result.get("cycle_index") or 1) > 1
                else None
            ),
            cycle_index=int(result.get("cycle_index") or 1),
        )
        if existing is not None and (
            not isinstance(preflight_receipt, Mapping)
            or preflight_receipt.get("action") != "RESUME_REPAIR_CONTINUATION"
        ):
            # A completed parent is the readback for an ordinary re-freeze.
            # An authorized repair preflight is a new terminal on that session.
            return existing
        persist_frozen_session(
            store,
            result,
            repo_root=repo_root,
            identities=identities,
            draft=draft,
            preflight_receipt=preflight_receipt,
            stage_time=bound_session_started_at(preflight_receipt),
        )
        store.rebuild_projection()
        result["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    result.pop("identities", None)
    return result


def _assert_temporal_search_closed(draft: Mapping[str, Any], store: Any) -> None:
    """NO_WORTHY is a search closure. An optional flag is not the authority."""

    evidence = draft.get("grounded_evidence")
    if not isinstance(evidence, Mapping) or store is None:
        return
    result = evidence.get("result") if isinstance(evidence.get("result"), Mapping) else {}
    if not isinstance(result, Mapping) or result.get("schema") != "smial.hfic-temporal-query":
        return
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError,
        list_discovery_looks,
    )
    from solana_alpha_lab.factory.hfic_temporal_discovery import (
        assert_search_exhaustion_claim,
        assess_tier_progress,
    )

    journal = str(evidence.get("journal_scope") or "")
    decision = str(evidence.get("tier_decision") or "")
    try:
        from solana_alpha_lab.factory.hfic_research_policy import limits_or_defaults

        progress = assess_tier_progress(
            list_discovery_looks(store, journal),
            freeze_worthy=decision == "WORTHY_SIMPLE",
            compound_applicable=decision != "COMPOUND_INAPPLICABLE",
            main_total=int(limits_or_defaults(store, journal)["main_total"]),
        )
        assert_search_exhaustion_claim(progress, claim_search_exhausted=True)
    except GroundedDiscoveryError as exc:
        raise HficSessionError(exc.code) from exc


def _freeze_no_worthy(
    draft: Mapping[str, Any],
    *,
    identities: Sequence[Any],
    preflight_receipt: Mapping[str, Any] | None,
    store: Any,
    repo_root: Any,
    next_action_draft: Mapping[str, Any] | None = None,
    grounded_candidates: Sequence[Mapping[str, Any]] | None = None,
    prompt_version: str = PROMPT_VERSION_V1_1,
    packet_version: str = "1.1",
    verify_current_market_identity: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    _assert_vision_integrity_for_surface(
        preflight_receipt, prompt_version=prompt_version
    )
    _assert_temporal_search_closed(draft, store)
    empty_ordinary = not identities and _ordinary_discovery_requested(
        draft, preflight_receipt
    )
    if empty_ordinary:
        runner_up_index = -1
        rejected_index = -1
    else:
        runner_up_index = _resolve_ref(draft.get("runner_up_candidate_ref"), identities)
        rejected_index = _resolve_ref(
            draft.get("strongest_rejected_alternative"),
            identities,
        )
        if runner_up_index < 0 or rejected_index < 0:
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
    closed_family_ledger = ledger_from_receipt(
        preflight_receipt if isinstance(preflight_receipt, Mapping) else None
    )
    closed_or_suppressed_collision_count: int | None = None
    draft_candidates = draft.get("candidates")
    if store is not None and closed_family_ledger and isinstance(draft_candidates, list):
        closed_or_suppressed_collision_count = 0
        for card in draft_candidates:
            if not isinstance(card, Mapping):
                continue
            hit = candidate_hard_close_entry(card, closed_family_ledger)
            if hit is not None:
                closed_or_suppressed_collision_count += 1
                raise HficSessionError("CLOSED_FAMILY_REOPEN", detail={
                    "stage": "CANDIDATE_SUPPRESSION", "source_terminal": hit.get("terminal"),
                    "scope_kind": hit.get("scope_kind"), "scope_id": hit.get("scope_id"),
                    "source_receipt": hit.get("source_receipt"),
                    "next_action": "KEEP_TYPED_CLOSE_SELECT_AUTHORIZED_DISTINCT_SCOPE",
                })
    elif store is not None:
        closed_or_suppressed_collision_count = 0
    bound: dict[str, Any] | None = None
    if store is not None:
        if repo_root is None or not isinstance(preflight_receipt, Mapping):
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        preflight_receipt, existing_ladder, bound = _bind_store_freeze_preflight(
            draft,
            preflight_receipt,
            store=store,
            repo_root=repo_root,
            memory_as_of=memory_as_of,
            verify_current_market_identity=verify_current_market_identity,
        )
        if existing_ladder is not None:
            return existing_ladder
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
        search_key = search_key_sha256(
            epoch,
            owner_focus,
            prompt_version,
            (
                str(bound.get("memory_eligibility_sha256") or "")
                if bound is not None
                else (
                    str(preflight_receipt.get("memory_eligibility_sha256") or "")
                    if isinstance(preflight_receipt, Mapping)
                    else None
                )
            )
            or None,
            (
                str(preflight_receipt.get("evidence_surface_mode") or "")
                if isinstance(preflight_receipt, Mapping)
                else None
            )
            or None,
        )
    if search_key:
        session_id = "HFIC-SESS-" + search_key[:16].upper()
    else:
        session_id = "HFIC-SESS-" + canonical_sha256(
            {
                "candidate_ids": [item.candidate_id for item in identities],
                "selected": None,
                "prompt_version": prompt_version,
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
        "prompt_version": prompt_version,
        "owner_focus": owner_focus,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "memory_eligibility_sha256": (
            str(bound.get("memory_eligibility_sha256") or "")
            if bound is not None
            else (
                str(preflight_receipt.get("memory_eligibility_sha256") or "")
                if isinstance(preflight_receipt, Mapping)
                else ""
            )
        )
        or None,
        "selected_candidate_id": None,
        "runner_up_candidate_id": (
            None if runner_up_index < 0 else identities[runner_up_index].candidate_id
        ),
        "rejected_alternative_id": (
            None if rejected_index < 0 else identities[rejected_index].candidate_id
        ),
        "selected_definition_sha256": None,
        "candidate_ids": [item.candidate_id for item in identities],
        "critic_input_packet": None,
        "critic_input_packet_sha256": None,
        "critic_launched": False,
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "grounded_evidence": _no_worthy_grounded_evidence(draft),
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
    if grounded_candidates is not None:
        result["grounded_candidates"] = list(grounded_candidates)
    _copy_evidence_surface_mode(
        result,
        preflight_receipt if isinstance(preflight_receipt, Mapping) else None,
    )
    _stamp_ladder_slot(result, preflight_receipt if isinstance(preflight_receipt, Mapping) else None)
    _stamp_split_identity(result, bound, preflight_receipt)
    _stamp_market_evidence_basis(result, bound, preflight_receipt)
    _stamp_execution_identity(result, bound, preflight_receipt)
    _stamp_prefreeze_capability_repair(
        result, preflight_receipt if isinstance(preflight_receipt, Mapping) else None
    )
    if closed_or_suppressed_collision_count is not None:
        result["closed_or_suppressed_collision_count"] = (
            closed_or_suppressed_collision_count
        )
    if persist and store is not None and repo_root is not None:
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
    elif persist and repo_root is not None:
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
    representation_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    repair_admission = None
    if existing is not None:
        try:
            repair_admission = _assert_scientific_admission(
                store,
                frozen,
                repo_root=repo_root,
                representation_registry=representation_registry,
            )
        except HficSessionError:
            repair_admission = None
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            ACTION_RESUME_REPAIR_CONTINUATION,
        )

        if (
            not isinstance(repair_admission, Mapping)
            or repair_admission.get("action") != ACTION_RESUME_REPAIR_CONTINUATION
        ):
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
    if repair_admission is None:
        repair_admission = _assert_scientific_admission(
            store,
            frozen,
            repo_root=repo_root,
            representation_registry=representation_registry,
        )
    if (
        isinstance(existing, Mapping)
        and isinstance(repair_admission, Mapping)
        and repair_admission.get("action") == "RESUME_REPAIR_CONTINUATION"
    ):
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            _disposition_bound_repair_completion,
        )

        disp = str(repair_admission.get("repair_continuation_disposition_sha256") or "")
        target = _repair_disposition_for_session(store, existing)
        if (
            target is not None
            and target.get("disposition_sha256") == disp
            and _disposition_bound_repair_completion(existing, target) is not None
        ):
            # Same transaction and record ids must not be appended again with
            # a higher cycle sequence. The stored repair terminal is the retry.
            _assert_repair_retry_evidence(existing, draft)
            stored_action = existing.get("next_action")
            if isinstance(stored_action, Mapping):
                return dict(stored_action)
            return {"action_type": str(existing.get("next") or "STOP")}
    # Admission is the first lifecycle boundary: legacy combined-only input
    # must receive SCIENTIFIC_ADMISSION_REQUIRED before any current-protocol
    # provenance diagnosis.  Once the split slot is admissible, recheck the
    # nested A3 no-write receipt so a caller cannot replace production lineage
    # with two self-proclaimed 64-hex stamps.
    if (
        isinstance(preflight_receipt, Mapping)
        and isinstance(preflight_receipt.get("forge_input_receipt"), Mapping)
    ):
        _validate_split_identity_binding(
            preflight_receipt,
            repo_root=Path(repo_root),
        )
    git = repository_git_snapshot(Path(repo_root))
    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else bound_session_started_at(preflight_receipt)
    )
    transaction_id = f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFICNW-')}"
    if isinstance(repair_admission, Mapping):
        repair_tx = repair_admission.get("repair_continuation_disposition_sha256")
        if isinstance(repair_tx, str) and repair_tx:
            transaction_id = (
                f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFICNW-')}"
                f"-REPAIR-{repair_tx[:12].upper()}"
            )
    producer = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
        supersedes_record_id: str | None = None,
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
            supersedes_record_id=supersedes_record_id,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=producer,
            producer_git_sha=git.head_sha,
            created_at=now,
        )

    repair_context = (
        isinstance(repair_admission, Mapping)
        and repair_admission.get("action") == "RESUME_REPAIR_CONTINUATION"
    )
    packet = (
        preflight_receipt.get("forge_context_packet")
        if isinstance(preflight_receipt, Mapping) else None
    )
    context_digest = frozen.get("forge_context_packet_sha256")
    if not repair_context and isinstance(packet, Mapping):
        if not isinstance(context_digest, str) or len(context_digest) != 64:
            context_digest = hashlib.sha256(_canonical_bytes(packet)).hexdigest()
    created_at = render_canonical_utc(now)
    started_at = str(frozen.get("session_started_at") or created_at)
    if not isinstance(context_digest, str) or len(context_digest) != 64:
        raise HficSessionError("HFIC_NEXT_ACTION_CONTEXT_MISMATCH")
    bind_input = {
        **dict(frozen),
        "forge_context_packet_sha256": context_digest,
        "session_started_at": started_at,
    }
    context_dependencies = ()
    if repair_context:
        # The admitted repair receipt describes current context, while the
        # parent next-action remains bound to its original saved dependency.
        # Validate both coherent pairs; never splice a fresh inline packet
        # onto the historical digest or rewrite the parent binding.
        fresh_context = dict(preflight_receipt or {})
        _verify_required_context_dependency(store, fresh_context)
        _verify_required_context_dependency(store, bind_input)
        context_dependencies = (fresh_context,)
    else:
        _verify_required_context_dependency(
            store, {**bind_input, "forge_context_packet": packet}
            if isinstance(packet, Mapping) else bind_input,
        )
    if isinstance(draft, Mapping):
        _validate_fresh_draft_scopes(draft, store=store, identities=identities)
    action = bind_next_epistemic_action(
        next_action_draft,
        frozen_no_worthy=bind_input,
        identities=identities,
        repo_root=Path(repo_root),
        created_at=created_at,
    )
    repair_disposition = None
    if isinstance(repair_admission, Mapping):
        repair_disposition = repair_admission.get(
            "repair_continuation_disposition_sha256"
        )
    action_bytes = _canonical_bytes(action)
    action_sha = hashlib.sha256(action_bytes).hexdigest()
    prompt_version = str(frozen.get("prompt_version") or PROMPT_VERSION)
    cycle_seq = _next_cycle_seq(existing)
    cycle_suffix = "NO-WORTHY"
    if isinstance(repair_disposition, str) and repair_disposition:
        cycle_suffix = f"REPAIR-{repair_disposition[:12].upper()}"
    receipt = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": str(frozen.get("evidence_epoch_sha256") or "0" * 64),
        "focus_key_sha256": str(frozen.get("focus_key_sha256") or "0" * 64),
        "search_key_sha256": str(frozen.get("search_key_sha256") or "0" * 64),
        "prompt_version": prompt_version,
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
        "decision_event_ids": [f"HFIC-DEC-{session_id}-{cycle_suffix}"],
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
    _stamp_split_identity(receipt, frozen)
    _stamp_execution_identity(receipt, frozen, preflight_receipt)
    diagnostics = _diagnostics_for_receipt(
        prompt_version=prompt_version,
        grounded_candidates=frozen.get("grounded_candidates")
        if isinstance(frozen.get("grounded_candidates"), list)
        else None,
        session_meta={
            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
            "selected_candidate_id": None,
            "no_worthy_hypothesis": True,
            "lane_classifier_terminal": None,
            "next_action_type_if_any": action["action_type"],
            **(
                {
                    "closed_or_suppressed_collision_count": frozen[
                        "closed_or_suppressed_collision_count"
                    ]
                }
                if "closed_or_suppressed_collision_count" in frozen
                else {}
            ),
        },
    )
    if diagnostics is not None:
        receipt["diagnostics"] = diagnostics
    if repo_root is not None:
        _validate_json_schema(
            receipt,
            _session_receipt_schema_path(
                repo_root,
                prompt_version,
                selected_path=False,
                wide_candidates=len(receipt.get("candidate_ids") or []) > MAX_CANDIDATES,
            ),
        )
    receipt_bytes = _canonical_bytes(receipt)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-{cycle_suffix}",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload={
                "research_cycle_id": f"{session_id}-{cycle_suffix}",
                "session_id": session_id,
                "phase": "SYNTHESIS_COMPLETE",
                "hfic_protocol": prompt_version,
                "prompt_version": prompt_version,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "memory_eligibility_sha256": frozen.get("memory_eligibility_sha256"),
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
                "ladder_representation_id": frozen.get("ladder_representation_id"),
                "control_session_id": frozen.get("control_session_id"),
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": 0,
                "hfic_cycle_seq": cycle_seq,
                **(
                    {
                        "repair_continuation_disposition_sha256": repair_disposition,
                        "parent_cycle_seq": int(existing.get("hfic_cycle_seq") or 0)
                        if isinstance(existing, Mapping)
                        else 0,
                        **(
                            {
                                "grounded_result_sha256": (
                                    draft.get("grounded_evidence") or {}
                                ).get("result_sha256"),
                                "grounded_result_refs": list(
                                    (draft.get("grounded_evidence") or {}).get(
                                        "result_refs"
                                    )
                                    or []
                                ),
                            }
                            if isinstance(draft, Mapping)
                            and isinstance(draft.get("grounded_evidence"), Mapping)
                            else {}
                        ),
                    }
                    if isinstance(repair_disposition, str) and repair_disposition
                    else {}
                ),
                **_execution_identity_fields(frozen),
                **_split_identity_fields(frozen),
                **(
                    {"market_evidence_basis": dict(frozen["market_evidence_basis"])}
                    if isinstance(frozen.get("market_evidence_basis"), Mapping)
                    else {}
                ),
                **(
                    {"evidence_surface_mode": frozen["evidence_surface_mode"]}
                    if frozen.get("evidence_surface_mode")
                    else {}
                ),
                **(
                    {"discovery_candidate_scope": _discovery_candidate_scope(frozen)}
                    if _discovery_candidate_scope(frozen)
                    else {}
                ),
            },
        ),
        event(
            record_id=(
                f"HFIC-ART-NEXT-ACTION-{session_id}-{cycle_suffix}-{action_sha[:12]}"
                if isinstance(repair_disposition, str) and repair_disposition
                else f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}"
            ),
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=(
                f"HFIC-ART-NEXT-ACTION-{session_id}-{cycle_suffix}-{action_sha[:12]}"
                if isinstance(repair_disposition, str) and repair_disposition
                else f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}"
            ),
            payload={
                "research_artifact_id": (
                    f"HFIC-ART-NEXT-ACTION-{session_id}-{cycle_suffix}-{action_sha[:12]}"
                    if isinstance(repair_disposition, str) and repair_disposition
                    else f"HFIC-ART-NEXT-ACTION-{session_id}-{action_sha[:12]}"
                ),
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "NEXT_EPISTEMIC_ACTION",
                "payload_canonical": action_bytes.decode("utf-8"),
                "payload_sha256": action_sha,
            },
        ),
        event(
            record_id=f"HFIC-ART-SESSION-RECEIPT-{session_id}-{cycle_suffix}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-SESSION-RECEIPT-{session_id}-{cycle_suffix}",
            payload={
                "research_artifact_id": f"HFIC-ART-SESSION-RECEIPT-{session_id}-{cycle_suffix}",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "SESSION_RECEIPT",
                "payload_canonical": receipt_bytes.decode("utf-8"),
                "payload_sha256": receipt_sha,
            },
        ),
        event(
            record_id=f"HFIC-DEC-{session_id}-{cycle_suffix}",
            kind=RecordKind.DECISION_EVENT,
            entity_id=f"HFIC-DEC-{session_id}-{cycle_suffix}",
            payload={
                "decision_event_id": f"HFIC-DEC-{session_id}-{cycle_suffix}",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "decision_kind": "REJECT",
                "reason_code": "NO_WORTHY_HYPOTHESIS",
                "hypothesis_version_id": None,
            },
        ),
    ]
    # Repair re-entry must not rewrite durable parent hypothesis cards / drafts.
    # Those record_ids are already committed; only the new cycle/receipt/decision
    # (and a fresh next-action) belong to the repair terminal write set.
    if not (isinstance(repair_disposition, str) and repair_disposition):
        cards = _cards_for_identities(identities, frozen, draft)
        for identity, card in zip(identities, cards, strict=True):
            records.append(
                event(
                    record_id=_session_hypothesis_record_id(identity.candidate_id, session_id),
                    kind=RecordKind.HYPOTHESIS_VERSION,
                    entity_id=identity.candidate_id,
                    hypothesis_version_id=identity.candidate_id,
                supersedes_record_id=_session_hypothesis_supersedes(store, identity.candidate_id, identity.full_sha256),
                    payload={
                        "hypothesis_version_id": identity.candidate_id,
                        "session_id": session_id,
                        "hfic_protocol": prompt_version,
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
                        **_hypothesis_scope_fields(frozen, identity.definition, card),
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
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "FORGE_DRAFT",
                    "payload_canonical": draft_bytes,
                    "payload_sha256": hashlib.sha256(
                        draft_bytes.encode("utf-8")
                    ).hexdigest(),
                },
            )
        )
    _append_session_records_with_slot(
        store, records, transaction_id=transaction_id, binding=bind_input,
        repo_root=repo_root, stage_time=now,
        representation_registry=representation_registry,
        reserve_slot=not bool(repair_disposition),
        context_dependencies=context_dependencies,
    )
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


def _existing_scientific_slot_admission(
    store: Any,
    scientific_slot_sha256: str,
) -> dict[str, Any] | None:
    for body in list_scientific_slot_admissions(store):
        if body.get("scientific_slot_sha256") == scientific_slot_sha256:
            return dict(body)
    return None


def _matching_orphan_reservation_only_delta(
    store: Any, receipt: Mapping[str, Any], draft: Mapping[str, Any],
) -> bool:
    """Accept a stale preflight digest only for its own sole slot reservation.

    The committed inventory is a hash of sorted partition manifests. Removing
    exactly the one-record reservation partition must reproduce the preflight
    digest; any concurrent research write keeps the ordinary stale refusal.
    """

    if receipt.get("action") != "START_NEW_SESSION":
        return False
    search_key = receipt.get("search_key_sha256")
    receipt_digest = receipt.get("store_inventory_digest")
    if (not isinstance(search_key, str) or re.fullmatch(r"[0-9a-f]{64}", search_key) is None
            or not isinstance(receipt_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", receipt_digest) is None):
        return False
    session_id = "HFIC-SESS-" + search_key[:16].upper()
    if draft.get("session_id") not in (None, "", session_id):
        return False
    try:
        slot = _execution_identity_fields(receipt).get("scientific_slot_sha256")
    except HficSessionError:
        return False
    if not isinstance(slot, str) or re.fullmatch(r"[0-9a-f]{64}", slot) is None:
        return False
    reservation = _existing_scientific_slot_admission(store, slot)
    if (reservation is None or reservation.get("session_id") != session_id
            or not _scientific_slot_admission_matches_binding(
                reservation, {**receipt, "session_id": session_id}
            )):
        return False
    manifest_reader = getattr(store, "_committed_manifests", None)
    if not callable(manifest_reader):
        return False
    manifests = manifest_reader(fresh=True)
    reservation_txn = f"RESEARCH-TXN-SLOT-{slot.upper()}"
    reserved = [item for item in manifests if item.partition_id == reservation_txn]
    if len(reserved) != 1 or reserved[0].row_count != 1:
        return False
    prior_inventory = [
        {
            "content_sha256": item.content_sha256,
            "file_sha256": item.file_sha256,
            "logical_location": item.logical_location,
            "partition_manifest_id": item.partition_manifest_id,
        }
        for item in manifests if item.partition_id != reservation_txn
    ]
    encoded = json.dumps(
        prior_inventory, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest() == receipt_digest


def _scientific_slot_admission_matches_binding(
    admission: Mapping[str, Any], binding: Mapping[str, Any]
) -> bool:
    """Require an orphan reservation to retain its complete immutable bind.

    A pre-freeze capability repair compares the reservation to the original
    capability and execution binding. The current recovery capability stays on
    the lifecycle row and is not written back onto the reservation.
    """

    if admission.get("identity_binding_status") == "CONFLICT":
        return False
    compared: Mapping[str, Any] = binding
    if binding.get("prefreeze_capability_repair") is True:
        original_capability = binding.get("generated_draft_capability_epoch_sha256")
        current_capability = binding.get("recovery_capability_epoch_sha256") or binding.get(
            "capability_epoch_sha256"
        )
        if not _hash64(original_capability) or not _hash64(current_capability):
            return False
        if original_capability == current_capability:
            return False
        repaired = dict(binding)
        repaired["capability_epoch_sha256"] = original_capability
        repaired["execution_binding_sha256"] = binding.get(
            "generated_draft_execution_binding_sha256"
        )
        compared = repaired
    try:
        observed = _execution_identity_fields(admission)
        expected = _execution_identity_fields(compared)
    except HficSessionError:
        return False
    for key in (
        "scientific_slot_sha256",
        "ladder_representation_id",
        "representation_semantic_version",
        "control_session_id",
        "representation_payload_sha256",
        "model_provenance_sha256",
        "execution_binding_sha256",
    ):
        if observed.get(key) != expected.get(key):
            return False
    for key in (
        "market_evidence_epoch_sha256",
        "capability_epoch_sha256",
        "memory_eligibility_sha256",
        "focus_key_sha256",
    ):
        if _first_valid_hash([admission], key) != _first_valid_hash([compared], key):
            return False
    if normalize_text(str(admission.get("owner_focus") or "AUTO")) != normalize_text(
        str(compared.get("owner_focus") or "AUTO")
    ):
        return False
    return admission.get("evidence_surface_mode") == compared.get(
        "evidence_surface_mode"
    )


def _build_scientific_slot_admission_event(
    binding: Mapping[str, Any],
    *,
    repo_root: Any,
    transaction_id: str,
    stage_time: datetime | None = None,
    git_snapshot: Any = None,
) -> tuple[dict[str, Any], Any]:
    """Build, but do not append, the durable occupancy event."""

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    fields = _execution_identity_fields(binding)
    slot = fields.get("scientific_slot_sha256")
    if not isinstance(slot, str) or re.fullmatch(r"[0-9a-f]{64}", slot) is None:
        raise HficSessionError("SCIENTIFIC_SLOT_REQUIRED")
    session_id = str(binding.get("session_id") or "")
    if not session_id:
        raise HficSessionError("SCIENTIFIC_SLOT_SESSION_REQUIRED")
    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else _stage_datetime(None)
    )
    git = git_snapshot or repository_git_snapshot(Path(repo_root))
    body: dict[str, Any] = {
        "schema": "smial.scientific-slot-admission",
        "schema_version": "1.0",
        "scientific_slot_sha256": slot,
        "session_id": session_id,
        "market_evidence_epoch_sha256": _first_valid_hash(
            [binding], "market_evidence_epoch_sha256"
        ),
        "ladder_representation_id": fields.get("ladder_representation_id"),
        "representation_semantic_version": fields.get(
            "representation_semantic_version"
        ),
        "owner_focus": binding.get("owner_focus") or "AUTO",
        "focus_key_sha256": _first_valid_hash([binding], "focus_key_sha256"),
        "evidence_surface_mode": binding.get("evidence_surface_mode"),
        "control_session_id": fields.get("control_session_id"),
        "representation_payload_sha256": fields.get("representation_payload_sha256"),
        "capability_epoch_sha256": _first_valid_hash(
            [binding], "capability_epoch_sha256"
        ),
        "memory_eligibility_sha256": _first_valid_hash(
            [binding], "memory_eligibility_sha256"
        ),
        "model_provenance_sha256": fields.get("model_provenance_sha256"),
        "execution_binding_sha256": fields.get("execution_binding_sha256"),
        "admission_state": "RESERVED",
        **({"cycle_index": fields["cycle_index"]} if fields.get("cycle_index") else {}),
    }
    canonical = _canonical_bytes(body)
    digest = hashlib.sha256(canonical).hexdigest()
    record_id = f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}"
    payload = {
        "research_artifact_id": record_id,
        "session_id": session_id,
        "hfic_protocol": str(binding.get("prompt_version") or PROMPT_VERSION),
        "artifact_kind": "SCIENTIFIC_SLOT_ADMISSION",
        "payload_canonical": canonical.decode("utf-8"),
        "payload_sha256": digest,
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git.head_sha,
        created_at=now,
    )
    return body, event


def _append_session_records_with_slot(
    store: Any,
    records: Sequence[Any],
    *,
    transaction_id: str,
    binding: Mapping[str, Any],
    repo_root: Any,
    stage_time: datetime,
    representation_registry: Mapping[str, Any] | None,
    reserve_slot: bool,
    context_dependencies: Sequence[Mapping[str, Any]] = (),
) -> None:
    """Commit a new reservation and its lifecycle in one existing store lease."""

    slot = _execution_identity_fields(binding).get("scientific_slot_sha256")
    admission_event = None
    if reserve_slot and isinstance(slot, str) and len(slot) == 64:
        _, admission_event = _build_scientific_slot_admission_event(
            binding, repo_root=repo_root, transaction_id=transaction_id,
            stage_time=stage_time,
        )
    append_records = list(records)

    def reservation_belongs_to_this_transaction() -> bool:
        try:
            saved = store.find_record(admission_event.record_id)
        except Exception as exc:
            if getattr(exc, "code", None) != "WRITE_LOOKUP_PENDING":
                raise
            # A published reservation is canonical even when its derived
            # lookup journal still awaits append's recovery under the lease.
            # This exceptional read must neither heal the index nor hide
            # other integrity errors.
            saved = next((item for item in store.iter_committed_records()
                          if item.record_id == admission_event.record_id), None)
        if saved is None:
            raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
        return saved.transaction_id == transaction_id

    if admission_event is not None:
        observed = _existing_scientific_slot_admission(store, slot)
        if observed is None or reservation_belongs_to_this_transaction():
            append_records.insert(0, admission_event)

    def recheck() -> None:
        _verify_required_context_dependency(store, binding)
        for dependency in context_dependencies:
            _verify_required_context_dependency(store, dependency)
        if admission_event is None:
            return
        observed = _existing_scientific_slot_admission(store, slot)
        if observed is not None:
            if str(observed.get("session_id") or "") != str(binding.get("session_id") or ""):
                raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
            if not _scientific_slot_admission_matches_binding(observed, binding):
                raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING")
            has_admission = any(item.record_id == admission_event.record_id for item in append_records)
            if has_admission != reservation_belongs_to_this_transaction():
                raise HficSessionError("SESSION_RESERVATION_APPEARED")
            return
        _assert_scientific_admission(
            store, binding, repo_root=repo_root,
            representation_registry=representation_registry,
        )

    for attempt in range(4):
        try:
            store.append(append_records, transaction_id=transaction_id, before_commit=recheck)
            return
        except Exception as exc:
            if getattr(exc, "code", None) == "SESSION_RESERVATION_APPEARED":
                append_records = list(records)
                continue
            if getattr(exc, "code", None) == "WRITER_BUSY" and attempt < 3:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
    raise HficSessionError("WRITER_BUSY")


def list_scientific_slot_admissions(store: Any) -> list[dict[str, Any]]:
    """Read append-only slot reservations, including pre-freeze reservations."""

    rows: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    unscoped_conflicts: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        record_id = str(getattr(record, "record_id", "") or "")
        record_slot_match = re.fullmatch(
            r"HFIC-ART-SLOT-ADMISSION-([0-9A-Fa-f]{64})", record_id
        )
        record_slot = record_slot_match.group(1).lower() if record_slot_match else None
        try:
            wrapper = json.loads(record.payload_json)
            if not isinstance(wrapper, Mapping):
                if record_slot:
                    conflicts.add(record_slot)
                    rows.setdefault(
                        record_slot,
                        {
                            "scientific_slot_sha256": record_slot,
                            "identity_binding_status": "CONFLICT",
                            "identity_conflict_fields": [
                                "scientific_slot_admission_integrity"
                            ],
                        },
                    )
                continue
            if wrapper.get("artifact_kind") != "SCIENTIFIC_SLOT_ADMISSION":
                if record_slot:
                    conflicts.add(record_slot)
                    rows.setdefault(
                        record_slot,
                        {
                            "scientific_slot_sha256": record_slot,
                            "identity_binding_status": "CONFLICT",
                            "identity_conflict_fields": [
                                "scientific_slot_admission_integrity"
                            ],
                        },
                    )
                continue
            raw = wrapper.get("payload_canonical")
            digest = wrapper.get("payload_sha256")
            body = json.loads(raw) if isinstance(raw, str) else None
        except (TypeError, ValueError, json.JSONDecodeError):
            if record_slot:
                conflicts.add(record_slot)
                rows.setdefault(
                    record_slot,
                    {
                        "scientific_slot_sha256": record_slot,
                        "identity_binding_status": "CONFLICT",
                        "identity_conflict_fields": [
                            "scientific_slot_admission_integrity"
                        ],
                    },
                )
            continue
        if not isinstance(body, Mapping):
            if record_slot:
                conflicts.add(record_slot)
                rows.setdefault(
                    record_slot,
                    {
                        "scientific_slot_sha256": record_slot,
                        "identity_binding_status": "CONFLICT",
                        "identity_conflict_fields": [
                            "scientific_slot_admission_integrity"
                        ],
                    },
                )
            continue
        body_slot = body.get("scientific_slot_sha256")
        slot = body_slot
        if not isinstance(slot, str) or re.fullmatch(r"[0-9a-f]{64}", slot) is None:
            slot = record_slot
        market = body.get("market_evidence_epoch_sha256")
        if not isinstance(market, str) or re.fullmatch(r"[0-9a-f]{64}", market) is None:
            market = None
        valid_inner = (
            slot is not None
            and isinstance(raw, str)
            and isinstance(digest, str)
            and hashlib.sha256(raw.encode("utf-8")).hexdigest() == digest
            and hashlib.sha256(_canonical_bytes(body)).hexdigest() == digest
            and body_slot == slot
            and (record_slot is None or record_slot == slot)
        )
        if not valid_inner:
            conflict_slots = {
                value
                for value in (record_slot, slot)
                if isinstance(value, str)
                and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            }
            if conflict_slots:
                for conflict_slot in conflict_slots:
                    conflicts.add(conflict_slot)
                    rows.setdefault(
                        conflict_slot,
                        {
                            "scientific_slot_sha256": conflict_slot,
                            "identity_binding_status": "CONFLICT",
                            "identity_conflict_fields": [
                                "scientific_slot_admission_integrity"
                            ],
                        },
                    )
            else:
                unscoped_conflicts.append(
                    {
                        "session_id": str(
                            wrapper.get("session_id") or body.get("session_id") or ""
                        )
                        or None,
                        "identity_binding_status": "CONFLICT",
                        "identity_conflict_fields": [
                            "scientific_slot_admission_integrity"
                        ],
                    }
                )
            continue
        wrapper_session = str(wrapper.get("session_id") or "")
        body_session = str(body.get("session_id") or "")
        if wrapper_session and body_session and wrapper_session != body_session:
            conflicts.add(slot)
            continue
        observed = rows.get(slot)
        if observed is not None and observed != dict(body):
            conflicts.add(slot)
            continue
        rows[slot] = dict(body)
    for slot in conflicts:
        body = dict(rows.get(slot) or {})
        body["scientific_slot_sha256"] = slot
        # Any integrity conflict invalidates market ownership derived from the
        # same damaged row; admission cannot scope it away as another market.
        body.pop("market_evidence_epoch_sha256", None)
        body["identity_binding_status"] = "CONFLICT"
        body["identity_conflict_fields"] = ["scientific_slot_admission"]
        rows[slot] = body
    return [*rows.values(), *unscoped_conflicts]


def _assert_scientific_admission(
    store: Any,
    binding: Mapping[str, Any],
    *,
    repo_root: Any | None = None,
    representation_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Apply the shared admission rule before freeze/lifecycle writes."""

    fields = _execution_identity_fields(binding)
    market = _first_valid_hash([binding], "market_evidence_epoch_sha256")
    version = fields.get("representation_semantic_version")
    if not isinstance(market, str) or not isinstance(version, str):
        # Legacy combined-only receipts remain read-only; they cannot mint a
        # new A5 slot without a current market split from production preflight.
        raise HficSessionError("SCIENTIFIC_ADMISSION_REQUIRED")
    from solana_alpha_lab.factory.hfic_evidence_identity import (
        resolve_scientific_admission,
    )
    from solana_alpha_lab.factory.hfic_repair_continuation import (
        ACTION_RESUME_REPAIR_CONTINUATION,
        list_repair_continuation_dispositions,
    )

    visible_cohort_ids = binding.get("visible_cohort_ids")
    if not isinstance(visible_cohort_ids, list):
        input_receipt = binding.get("forge_input_receipt")
        active_set = (
            input_receipt.get("active_evidence_set")
            if isinstance(input_receipt, Mapping)
            else None
        )
        visible_cohort_ids = (
            active_set.get("visible_cohort_ids")
            if isinstance(active_set, Mapping)
            else None
        )
    from solana_alpha_lab.factory.hfic_research_policy import epoch_limits

    # The AUTO/focus pool is the market epoch's own frozen scope, never a journal's.
    pool = epoch_limits(store, market)
    admission = resolve_scientific_admission(
        list_hfic_sessions(store),
        reservations=list_scientific_slot_admissions(store),
        market_evidence_epoch=market,
        market_evidence_basis=_market_evidence_basis_from_sources(binding),
        representation_id=str(fields.get("ladder_representation_id") or "BASE"),
        representation_semantic_version=version,
        owner_focus=str(binding.get("owner_focus") or "AUTO"),
        representation_registry=representation_registry,
        repo_root=Path(repo_root) if repo_root is not None else None,
        memory_eligibility_sha256=(
            str(binding.get("memory_eligibility_sha256"))
            if isinstance(binding.get("memory_eligibility_sha256"), str)
            else None
        ),
        evidence_surface_mode=(
            str(binding.get("evidence_surface_mode"))
            if isinstance(binding.get("evidence_surface_mode"), str)
            else None
        ),
        current_visible_cohort_ids=(
            list(visible_cohort_ids or [])
            if isinstance(visible_cohort_ids, list)
            else None
        ),
        execution_context={
            key: fields.get(key) or binding.get(key)
            for key in (
                "capability_epoch_sha256",
                "representation_payload_sha256",
                "model_provenance_sha256",
            )
            if isinstance(fields.get(key) or binding.get(key), str)
        },
        repair_continuations=list_repair_continuation_dispositions(store),
        auto_sessions_per_market=pool["auto_cycles_per_market"],
        max_distinct_focuses=pool["distinct_focuses_per_market"],
        requested_cycle_index=int(fields.get("cycle_index") or 1),
    )
    action = str(admission.get("action") or "")
    if action == "STOP" and str(admission.get("reason_code") or "") == (
        "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING"
    ):
        draft = find_generated_draft(
            store,
            market_evidence_epoch_sha256=market,
            owner_focus=str(binding.get("owner_focus") or "AUTO"),
            representation_id=str(fields.get("ladder_representation_id") or "BASE"),
            representation_semantic_version=version,
            scientific_slot_sha256=str(fields.get("scientific_slot_sha256") or ""),
        )
        draft_session = str(draft.get("session_id") or "") if draft else ""
        session_id = str(binding.get("session_id") or "")
        admission_session = str(admission.get("session_id") or "")
        if draft_session and draft_session == session_id == admission_session:
            match_kwargs = {
                "market_evidence_epoch_sha256": market,
                "scientific_slot_sha256": str(fields.get("scientific_slot_sha256") or ""),
                "representation_id": str(fields.get("ladder_representation_id") or "BASE"),
                "representation_semantic_version": version,
                "owner_focus": str(binding.get("owner_focus") or "AUTO"),
                "capability_epoch_sha256": (
                    str(fields.get("capability_epoch_sha256") or binding.get("capability_epoch_sha256"))
                    if fields.get("capability_epoch_sha256") or binding.get("capability_epoch_sha256")
                    else None
                ),
                "memory_eligibility_sha256": (
                    str(binding.get("memory_eligibility_sha256"))
                    if isinstance(binding.get("memory_eligibility_sha256"), str)
                    else None
                ),
                "evidence_surface_mode": (
                    str(binding.get("evidence_surface_mode"))
                    if isinstance(binding.get("evidence_surface_mode"), str)
                    else None
                ),
                "control_session_id": (
                    str(fields.get("control_session_id"))
                    if isinstance(fields.get("control_session_id"), str)
                    else None
                ),
                "representation_payload_sha256": (
                    str(fields.get("representation_payload_sha256"))
                    if isinstance(fields.get("representation_payload_sha256"), str)
                    else None
                ),
                "execution_binding_sha256": (
                    str(fields.get("execution_binding_sha256"))
                    if isinstance(fields.get("execution_binding_sha256"), str)
                    else None
                ),
                "model_provenance_sha256": (
                    str(fields.get("model_provenance_sha256"))
                    if isinstance(fields.get("model_provenance_sha256"), str)
                    else None
                ),
            }
            draft_matches = generated_draft_matches_preflight_context(draft, **match_kwargs)
            if not draft_matches:
                # Capability repair is only this orphan-draft branch. A
                # lifecycle row takes the strict path above and never arrives
                # here, because its admission is not READBACK_MISSING.
                draft_matches = prefreeze_generated_draft_recovery(
                    draft,
                    sessions=list_hfic_sessions(store),
                    reservations=list_scientific_slot_admissions(store),
                    **match_kwargs,
                )
            if draft_matches:
                return {
                    **admission,
                    "action": "RESUME_EXISTING_SESSION",
                    "reason_code": "GENERATED_DRAFT_READBACK",
                    "session_id": session_id,
                    "occupancy": "OCCUPIED_RESUMABLE_DRAFT",
                }
            raise HficSessionError(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
            )
    if action == "START_NEW_SESSION":
        return admission
    session_id = str(binding.get("session_id") or "")
    admitted_id = str(admission.get("session_id") or "")
    if admitted_id == session_id and action in {
        "RESUME_EXISTING_SESSION",
        "RETURN_EXISTING_SESSION",
        ACTION_RESUME_REPAIR_CONTINUATION,
    }:
        return admission
    raise HficSessionError(
        str(admission.get("reason_code") or "SCIENTIFIC_SLOT_OCCUPIED")
    )


def persist_scientific_slot_admission(
    store: Any,
    binding: Mapping[str, Any],
    *,
    repo_root: Any,
    stage_time: datetime | None = None,
    representation_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Atomically reserve a scientific slot before lifecycle artifacts are written."""

    fields = _execution_identity_fields(binding)
    slot = fields.get("scientific_slot_sha256")
    if not isinstance(slot, str) or len(slot) != 64:
        return None
    session_id = str(binding.get("session_id") or "")
    if not session_id:
        raise HficSessionError("SCIENTIFIC_SLOT_SESSION_REQUIRED")
    existing = _existing_scientific_slot_admission(store, slot)
    if existing is not None:
        if str(existing.get("session_id") or "") != session_id:
            raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
        if not _scientific_slot_admission_matches_binding(existing, binding):
            raise HficSessionError(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
            )
        return existing

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else bound_session_started_at(binding)
        if isinstance(binding.get("session_started_at"), str)
        and str(binding.get("session_started_at") or "").strip()
        else _stage_datetime(None)
    )
    git = repository_git_snapshot(Path(repo_root))
    body: dict[str, Any] = {
        "schema": "smial.scientific-slot-admission",
        "schema_version": "1.0",
        "scientific_slot_sha256": slot,
        "session_id": session_id,
        "market_evidence_epoch_sha256": _first_valid_hash(
            [binding], "market_evidence_epoch_sha256"
        ),
        "ladder_representation_id": fields.get("ladder_representation_id"),
        "representation_semantic_version": fields.get(
            "representation_semantic_version"
        ),
        "owner_focus": binding.get("owner_focus") or "AUTO",
        "focus_key_sha256": _first_valid_hash([binding], "focus_key_sha256"),
        "evidence_surface_mode": binding.get("evidence_surface_mode"),
        "control_session_id": fields.get("control_session_id"),
        "representation_payload_sha256": fields.get("representation_payload_sha256"),
        "capability_epoch_sha256": _first_valid_hash(
            [binding], "capability_epoch_sha256"
        ),
        "memory_eligibility_sha256": _first_valid_hash(
            [binding], "memory_eligibility_sha256"
        ),
        "model_provenance_sha256": fields.get("model_provenance_sha256"),
        "execution_binding_sha256": fields.get("execution_binding_sha256"),
        "admission_state": "RESERVED",
        **({"cycle_index": fields["cycle_index"]} if fields.get("cycle_index") else {}),
    }
    canonical = _canonical_bytes(body)
    digest = hashlib.sha256(canonical).hexdigest()
    transaction_id = f"RESEARCH-TXN-SLOT-{slot.upper()}"
    payload = {
        "research_artifact_id": f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
        "session_id": session_id,
        "hfic_protocol": str(binding.get("prompt_version") or PROMPT_VERSION),
        "artifact_kind": "SCIENTIFIC_SLOT_ADMISSION",
        "payload_canonical": canonical.decode("utf-8"),
        "payload_sha256": digest,
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    event = ResearchEvent(
        record_id=f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git.head_sha,
        created_at=now,
    )

    def _recheck_admission_under_writer_lease() -> None:
        # The budget/readback decision must be made while ResearchStore's
        # cross-process writer lease is held.  A pre-check outside the lease
        # alone allows two different slots to both observe the same free AUTO
        # budget and then append.
        if binding.get("forge_context_packet_sha256") is not None:
            _verify_required_context_dependency(store, binding)
        observed = _existing_scientific_slot_admission(store, slot)
        if observed is not None:
            if str(observed.get("session_id") or "") != session_id:
                raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
            if not _scientific_slot_admission_matches_binding(observed, binding):
                raise HficSessionError(
                    "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
                )
            return
        _assert_scientific_admission(
            store,
            binding,
            repo_root=repo_root,
            representation_registry=representation_registry,
        )

    for attempt in range(4):
        try:
            store.append(
                [event],
                transaction_id=transaction_id,
                before_commit=_recheck_admission_under_writer_lease,
            )
            break
        except Exception as exc:
            # A competing writer may hold the lease briefly. Re-read after a
            # bounded retry so the loser reports the occupied slot instead of
            # leaking an implementation-level WRITER_BUSY error.
            observed = _existing_scientific_slot_admission(store, slot)
            if observed is not None:
                if str(observed.get("session_id") or "") != session_id:
                    raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
                if not _scientific_slot_admission_matches_binding(observed, binding):
                    raise HficSessionError(
                        "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
                    )
                return observed
            if (
                getattr(exc, "code", None) == "WRITER_BUSY"
                and attempt < 3
            ):
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
    return body


def find_generated_draft(
    store: Any,
    *,
    market_evidence_epoch_sha256: str,
    owner_focus: str,
    representation_id: str | None = None,
    representation_semantic_version: str | None = None,
    scientific_slot_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Read a pre-freeze generator artifact; never treats embedded old drafts as new."""

    wanted_focus = focus_key_sha256(owner_focus)
    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if wrapper.get("artifact_kind") != "FORGE_DRAFT":
            continue
        if wrapper.get("draft_lifecycle") != "GENERATED_BEFORE_FREEZE":
            continue
        if wrapper.get("market_evidence_epoch_sha256") != market_evidence_epoch_sha256:
            continue
        if wrapper.get("focus_key_sha256") != wanted_focus:
            continue
        if representation_id is not None and wrapper.get("ladder_representation_id") != representation_id:
            continue
        if (
            representation_semantic_version is not None
            and wrapper.get("representation_semantic_version")
            != representation_semantic_version
        ):
            continue
        if (
            scientific_slot_sha256 is not None
            and wrapper.get("scientific_slot_sha256") != scientific_slot_sha256
        ):
            continue
        raw = wrapper.get("payload_canonical")
        digest = wrapper.get("payload_sha256")
        if not isinstance(raw, str) or not isinstance(digest, str):
            continue
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
            continue
        try:
            draft = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(draft, Mapping):
            continue
        if hashlib.sha256(_canonical_bytes(draft)).hexdigest() != digest:
            continue
        found.append({**dict(wrapper), "draft": dict(draft)})
    if not found:
        return None
    found.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return found[0]


def generated_draft_matches_preflight_context(
    generated_draft: Mapping[str, Any],
    *,
    market_evidence_epoch_sha256: str,
    scientific_slot_sha256: str,
    representation_id: str,
    representation_semantic_version: str,
    owner_focus: str,
    capability_epoch_sha256: str | None,
    memory_eligibility_sha256: str | None,
    evidence_surface_mode: str | None,
    control_session_id: str | None = None,
    representation_payload_sha256: str | None = None,
    execution_binding_sha256: str | None = None,
    model_provenance_sha256: str | None = None,
    allow_prefreeze_capability_repair: bool = False,
) -> bool:
    """Validate that a durable pre-freeze draft still belongs to this entry.

    The draft bytes and their source-preflight reference are immutable. A new
    preflight may resume them only while market, slot, memory, representation
    and focus identities still agree. Capability epoch may differ only when
    ``allow_prefreeze_capability_repair`` is set, and only for the pre-freeze
    orphan checked by ``prefreeze_generated_draft_recovery``.
    """

    if not isinstance(generated_draft, Mapping):
        return False
    raw_draft = generated_draft.get("draft")
    if not isinstance(raw_draft, Mapping):
        raw = generated_draft.get("payload_canonical")
        if not isinstance(raw, str):
            return False
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(parsed, Mapping):
            return False
        raw_draft = parsed
    digest = generated_draft.get("payload_sha256")
    if (
        not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or hashlib.sha256(_canonical_bytes(raw_draft)).hexdigest() != digest
    ):
        return False
    source_id = generated_draft.get("source_preflight_receipt_id")
    source_sha = generated_draft.get("source_preflight_receipt_sha256")
    if (
        not isinstance(source_id, str)
        or not source_id
        or not isinstance(source_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_sha) is None
        or raw_draft.get("preflight_receipt_id") != source_id
        or raw_draft.get("preflight_receipt_sha256") != source_sha
    ):
        return False
    expected = {
        "market_evidence_epoch_sha256": market_evidence_epoch_sha256,
        "scientific_slot_sha256": scientific_slot_sha256,
        "focus_key_sha256": focus_key_sha256(owner_focus),
        "ladder_representation_id": representation_id,
        "representation_semantic_version": representation_semantic_version,
        "memory_eligibility_sha256": memory_eligibility_sha256,
        "evidence_surface_mode": evidence_surface_mode,
        "control_session_id": control_session_id,
        "representation_payload_sha256": representation_payload_sha256,
    }
    if not allow_prefreeze_capability_repair:
        expected["capability_epoch_sha256"] = capability_epoch_sha256
        expected["execution_binding_sha256"] = execution_binding_sha256
    if any(generated_draft.get(key) != value for key, value in expected.items()):
        return False
    model = generated_draft.get("model_provenance_sha256")
    if model not in (None, "") and (
        not isinstance(model, str) or re.fullmatch(r"[0-9a-f]{64}", model) is None
    ):
        return False
    if model_provenance_sha256 is not None and model != model_provenance_sha256:
        return False
    if not allow_prefreeze_capability_repair:
        return True
    # A known model on the saved draft is part of the execution identity.
    # Capability repair may proceed only when the caller repeats that same
    # model. Omitting it is not "unknown"; it is a different binding.
    if _hash64(model) and model_provenance_sha256 != model:
        return False
    return _prefreeze_capability_drift_is_consistent(
        generated_draft,
        scientific_slot_sha256=scientific_slot_sha256,
        capability_epoch_sha256=capability_epoch_sha256,
        memory_eligibility_sha256=memory_eligibility_sha256,
        control_session_id=control_session_id,
        representation_payload_sha256=representation_payload_sha256,
        execution_binding_sha256=execution_binding_sha256,
        model_provenance_sha256=model if _hash64(model) else None,
    )


def _hash64(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _prefreeze_capability_drift_is_consistent(
    generated_draft: Mapping[str, Any],
    *,
    scientific_slot_sha256: str,
    capability_epoch_sha256: str | None,
    memory_eligibility_sha256: str | None,
    control_session_id: str | None,
    representation_payload_sha256: str | None,
    execution_binding_sha256: str | None,
    model_provenance_sha256: str | None,
) -> bool:
    """Allow a capability-only change while the original binding stays readable.

    Unknown execution bindings (no model provenance) may differ in capability
    epoch alone. A known binding must still be the digest of the capability
    epoch that wrote it, and the caller's current binding must be the digest
    of the capability epoch performing recovery. The two epochs are not
    rewritten to look equal.
    """

    stored_capability = generated_draft.get("capability_epoch_sha256")
    stored_binding = generated_draft.get("execution_binding_sha256")
    if not _hash64(stored_capability) or not _hash64(capability_epoch_sha256):
        return False
    if (
        stored_capability == capability_epoch_sha256
        and stored_binding == execution_binding_sha256
    ):
        return True
    if stored_binding in (None, "") and execution_binding_sha256 in (None, ""):
        return True
    if not all(
        _hash64(value)
        for value in (
            representation_payload_sha256,
            memory_eligibility_sha256,
            model_provenance_sha256,
            stored_binding,
            execution_binding_sha256,
        )
    ):
        return False
    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError,
        execution_binding_sha256 as execution_binding_digest,
    )

    try:
        original_binding = execution_binding_digest(
            scientific_slot_sha256=scientific_slot_sha256,
            capability_epoch_sha256=stored_capability,
            control_session_id=control_session_id,
            representation_payload_sha256=representation_payload_sha256,
            memory_eligibility_sha256=memory_eligibility_sha256,
            model_provenance_sha256=model_provenance_sha256,
        )
        current_binding = execution_binding_digest(
            scientific_slot_sha256=scientific_slot_sha256,
            capability_epoch_sha256=capability_epoch_sha256,
            control_session_id=control_session_id,
            representation_payload_sha256=representation_payload_sha256,
            memory_eligibility_sha256=memory_eligibility_sha256,
            model_provenance_sha256=model_provenance_sha256,
        )
    except EvidenceIdentityError:
        return False
    return stored_binding == original_binding and execution_binding_sha256 == current_binding


def prefreeze_generated_draft_recovery(
    generated_draft: Mapping[str, Any] | None,
    *,
    sessions: Sequence[Mapping[str, Any]],
    reservations: Sequence[Mapping[str, Any]],
    market_evidence_epoch_sha256: str,
    scientific_slot_sha256: str,
    representation_id: str,
    representation_semantic_version: str,
    owner_focus: str,
    capability_epoch_sha256: str | None,
    memory_eligibility_sha256: str | None,
    evidence_surface_mode: str | None,
    control_session_id: str | None = None,
    representation_payload_sha256: str | None = None,
    execution_binding_sha256: str | None = None,
    model_provenance_sha256: str | None = None,
    assert_evidence_surface: bool = True,
) -> bool:
    """True only for one exact pre-freeze draft whose lifecycle row does not exist.

    Capability epoch may differ. Market, slot, representation, focus, memory,
    evidence surface, model provenance, draft bytes and the original
    reservation may not. A later lifecycle row loses this exception.
    """

    if not isinstance(generated_draft, Mapping):
        return False
    if generated_draft.get("draft_lifecycle") != "GENERATED_BEFORE_FREEZE":
        return False
    session_id = str(generated_draft.get("session_id") or "")
    if not session_id:
        return False
    if any(
        str(item.get("session_id") or "") == session_id
        for item in sessions
        if isinstance(item, Mapping)
    ):
        return False
    reservation = next(
        (
            item
            for item in reservations
            if isinstance(item, Mapping)
            and str(item.get("session_id") or "") == session_id
            and item.get("scientific_slot_sha256") == scientific_slot_sha256
        ),
        None,
    )
    if not isinstance(reservation, Mapping):
        return False
    if reservation.get("identity_binding_status") == "CONFLICT":
        return False
    if reservation.get("capability_epoch_sha256") != generated_draft.get(
        "capability_epoch_sha256"
    ):
        return False
    if reservation.get("execution_binding_sha256") != generated_draft.get(
        "execution_binding_sha256"
    ):
        return False
    if reservation.get("market_evidence_epoch_sha256") != generated_draft.get(
        "market_evidence_epoch_sha256"
    ):
        return False
    if reservation.get("evidence_surface_mode") != generated_draft.get(
        "evidence_surface_mode"
    ):
        return False
    if reservation.get("memory_eligibility_sha256") != generated_draft.get(
        "memory_eligibility_sha256"
    ):
        return False
    if reservation.get("ladder_representation_id") != generated_draft.get(
        "ladder_representation_id"
    ):
        return False
    if reservation.get("representation_semantic_version") != generated_draft.get(
        "representation_semantic_version"
    ):
        return False
    if reservation.get("focus_key_sha256") != generated_draft.get("focus_key_sha256"):
        return False
    draft_focus = generated_draft.get("owner_focus")
    if isinstance(draft_focus, str) and draft_focus.strip():
        if normalize_text(str(reservation.get("owner_focus") or "AUTO")) != normalize_text(
            draft_focus
        ):
            return False
    surface = evidence_surface_mode
    if not assert_evidence_surface:
        surface = (
            str(generated_draft.get("evidence_surface_mode"))
            if isinstance(generated_draft.get("evidence_surface_mode"), str)
            else None
        )
    return generated_draft_matches_preflight_context(
        generated_draft,
        market_evidence_epoch_sha256=market_evidence_epoch_sha256,
        scientific_slot_sha256=scientific_slot_sha256,
        representation_id=representation_id,
        representation_semantic_version=representation_semantic_version,
        owner_focus=owner_focus,
        capability_epoch_sha256=capability_epoch_sha256,
        memory_eligibility_sha256=memory_eligibility_sha256,
        evidence_surface_mode=surface,
        control_session_id=control_session_id,
        representation_payload_sha256=representation_payload_sha256,
        execution_binding_sha256=execution_binding_sha256,
        model_provenance_sha256=model_provenance_sha256,
        allow_prefreeze_capability_repair=True,
    )


def orphan_prefreeze_draft_resumable(
    store: Any,
    *,
    market_evidence_epoch_sha256: str,
    representation_id: str,
    representation_semantic_version: str,
    owner_focus: str,
    capability_epoch_sha256: str | None,
    memory_eligibility_sha256: str | None,
    model_provenance_sha256: str | None = None,
) -> bool:
    """Forge-run readback: an orphan generated draft is resumable, not missing.

    Surface mode is not asserted here. Preflight remains the mode gate.
    """

    from solana_alpha_lab.factory.hfic_evidence_identity import (
        scientific_slot_sha256 as slot_digest,
    )

    representation = representation_id
    if representation in {"CURRENT_REPRESENTATION_CONTROL_V1", "ORDINARY_BASE"}:
        representation = "BASE"
    if not _hash64(market_evidence_epoch_sha256):
        return False
    slot = slot_digest(
        market_evidence_epoch_sha256=market_evidence_epoch_sha256,
        representation_id=representation,
        representation_semantic_version=representation_semantic_version,
        owner_focus=owner_focus,
    )
    draft = find_generated_draft(
        store,
        market_evidence_epoch_sha256=market_evidence_epoch_sha256,
        owner_focus=owner_focus,
        representation_id=representation,
        representation_semantic_version=representation_semantic_version,
        scientific_slot_sha256=slot,
    )
    if draft is None:
        return False
    return prefreeze_generated_draft_recovery(
        draft,
        sessions=list_hfic_sessions(store),
        reservations=list_scientific_slot_admissions(store),
        market_evidence_epoch_sha256=market_evidence_epoch_sha256,
        scientific_slot_sha256=slot,
        representation_id=representation,
        representation_semantic_version=representation_semantic_version,
        owner_focus=owner_focus,
        capability_epoch_sha256=capability_epoch_sha256,
        memory_eligibility_sha256=memory_eligibility_sha256,
        evidence_surface_mode=None,
        model_provenance_sha256=model_provenance_sha256,
        assert_evidence_surface=False,
    )


def persist_generated_draft(
    store: Any,
    draft: Mapping[str, Any],
    *,
    preflight_receipt: Mapping[str, Any],
    repo_root: Any,
    representation_id: str = "BASE",
    model_provenance_sha256: str | None = None,
    stage_time: datetime | None = None,
    representation_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist generator bytes before freeze so restart resumes the same draft."""

    if not isinstance(draft, Mapping):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if preflight_receipt.get("action") != "START_NEW_SESSION":
        raise HficSessionError("PREFLIGHT_ACTION_INVALID")
    receipt = dict(preflight_receipt)
    receipt["ladder_representation_id"] = representation_id
    if model_provenance_sha256 is not None:
        receipt["model_provenance_sha256"] = model_provenance_sha256
    source_receipt_id = receipt.get("receipt_id")
    source_receipt_hash = receipt.get("preflight_receipt_sha256")
    if not isinstance(source_receipt_id, str) or not source_receipt_id:
        raise HficSessionError("PREFLIGHT_RECEIPT_ID_MISMATCH")
    if (
        not isinstance(source_receipt_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_receipt_hash) is None
        or source_receipt_hash != canonical_preflight_receipt_sha256(preflight_receipt)
    ):
        raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    if draft.get("preflight_receipt_id") != source_receipt_id:
        raise HficSessionError("PREFLIGHT_RECEIPT_ID_MISMATCH")
    if draft.get("preflight_receipt_sha256") != source_receipt_hash:
        raise HficSessionError("PREFLIGHT_RECEIPT_HASH_MISMATCH")
    if repo_root is None:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    _reject_stale_fresh_session_draft(draft, receipt)
    _validate_json_schema(draft, _draft_schema_path(repo_root, draft))
    _draft_prompt_version(draft)
    candidates = _project_draft_cards(draft)
    if not isinstance(candidates, list) or not (
        MIN_CANDIDATES <= len(candidates) <= _max_candidates_for(store, receipt.get("search_key_sha256"))
    ):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    try:
        identities = assign_portfolio_ids(candidates)
    except HficIdentityError as exc:
        raise HficSessionError(str(exc)) from exc
    selected_ref = draft.get("selected_candidate_ref")
    runner_up_index = -1
    if selected_ref not in (None, ""):
        selected_index = _resolve_ref(selected_ref, identities)
        optional_single = (
            _ordinary_discovery_requested(draft, receipt)
            and len(identities) == 1
            and not str(draft.get("runner_up_candidate_ref") or "").strip()
            and not str(draft.get("strongest_rejected_alternative") or "").strip()
        )
        if optional_single:
            if selected_index < 0:
                raise HficSessionError("SELECTED_CANDIDATE_MISSING")
        else:
            runner_up_index = _resolve_ref(draft.get("runner_up_candidate_ref"), identities)
            rejected_index = _resolve_ref(
                draft.get("strongest_rejected_alternative"), identities
            )
            if min(selected_index, runner_up_index, rejected_index) < 0:
                raise HficSessionError("CROSS_REFERENCE_MISMATCH")
            if selected_index == runner_up_index:
                raise HficSessionError("SELECTED_EQUALS_RUNNER_UP")
    _nonempty_str_list(draft.get("truth_roots_used"), code="TRUTH_ROOTS_REQUIRED")
    _nonempty_str_list(
        draft.get("prior_work_receipts") or draft.get("prior_work_queries"),
        code="PRIOR_WORK_RECEIPTS_REQUIRED",
    )
    _require_memory_timestamp(draft.get("research_memory_as_of"))
    _authority_zero(draft.get("authority"))
    context_bound = {
        "owner_focus": str(receipt.get("owner_focus") or "AUTO"),
        "evidence_epoch_sha256": str(receipt.get("evidence_epoch_sha256") or ""),
        "search_key_sha256": str(receipt.get("search_key_sha256") or ""),
    }
    _validate_draft_forge_context_binding(draft, receipt, context_bound)
    fields = _execution_identity_fields(receipt)
    slot = fields.get("scientific_slot_sha256")
    if not isinstance(slot, str) or re.fullmatch(r"[0-9a-f]{64}", slot) is None:
        raise HficSessionError("SCIENTIFIC_SLOT_REQUIRED")
    search_key = str(receipt.get("search_key_sha256") or "")
    if re.fullmatch(r"[0-9a-f]{64}", search_key) is None:
        raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
    market = str(
        receipt.get("market_evidence_epoch_sha256")
        or receipt.get("evidence_epoch_sha256")
        or ""
    )
    version = fields.get("representation_semantic_version")
    capability = fields.get("capability_epoch_sha256") or receipt.get(
        "capability_epoch_sha256"
    )
    memory = fields.get("memory_eligibility_sha256") or receipt.get(
        "memory_eligibility_sha256"
    )
    evidence_mode = receipt.get("evidence_surface_mode")
    if (
        re.fullmatch(r"[0-9a-f]{64}", market) is None
        or not isinstance(version, str)
        or not isinstance(capability, str)
        or not isinstance(memory, str)
    ):
        raise HficSessionError("SCIENTIFIC_ADMISSION_REQUIRED")
    data_root = getattr(store, "_root", None)
    if data_root is None:
        raise HficSessionError("MARKET_IDENTITY_BASIS_MISSING")
    from solana_alpha_lab.factory.research_store import (
        ResearchStoreError,
        assert_no_physical_paths,
    )

    try:
        assert_no_physical_paths(draft)
    except ResearchStoreError as exc:
        raise HficSessionError(exc.code) from exc
    _validate_split_identity_binding(
        receipt,
        repo_root=Path(repo_root),
        data_root=Path(data_root),
        require_current_market_identity=True,
    )
    _validate_fresh_draft_scopes(draft, store=store, identities=identities)
    _verify_required_context_dependency(store, receipt)
    session_id = "HFIC-SESS-" + search_key[:16].upper()
    binding = {**receipt, **fields, "session_id": session_id}
    draft_bytes = _canonical_bytes(draft)
    draft_sha = hashlib.sha256(draft_bytes).hexdigest()
    existing = find_generated_draft(
        store,
        market_evidence_epoch_sha256=market,
        owner_focus=str(receipt.get("owner_focus") or "AUTO"),
        representation_id=representation_id,
        representation_semantic_version=version,
        scientific_slot_sha256=slot,
    )
    if existing is not None:
        if (
            existing.get("payload_sha256") == draft_sha
            and existing.get("session_id") == session_id
            and existing.get("model_provenance_sha256")
            == fields.get("model_provenance_sha256")
            and generated_draft_matches_preflight_context(
                existing,
                market_evidence_epoch_sha256=market,
                scientific_slot_sha256=slot,
                representation_id=representation_id,
                representation_semantic_version=version,
                owner_focus=str(receipt.get("owner_focus") or "AUTO"),
                capability_epoch_sha256=capability,
                memory_eligibility_sha256=memory,
                evidence_surface_mode=(
                    str(evidence_mode) if isinstance(evidence_mode, str) else None
                ),
                control_session_id=(
                    str(fields.get("control_session_id"))
                    if isinstance(fields.get("control_session_id"), str)
                    else None
                ),
                representation_payload_sha256=(
                    str(fields.get("representation_payload_sha256"))
                    if isinstance(fields.get("representation_payload_sha256"), str)
                    else None
                ),
                execution_binding_sha256=(
                    str(fields.get("execution_binding_sha256"))
                    if isinstance(fields.get("execution_binding_sha256"), str)
                    else None
                ),
                model_provenance_sha256=(
                    str(fields.get("model_provenance_sha256"))
                    if isinstance(fields.get("model_provenance_sha256"), str)
                    else None
                ),
            )
        ):
            return existing
        raise HficSessionError("GENERATED_DRAFT_CONFLICT")
    # A crash may leave only the immutable slot reservation. Check its
    # execution identity before freeze's ordinary preflight digest check:
    # the reservation itself advances the store digest, while a different
    # model bind must retain the specific occupied-slot refusal.
    current_reservation = _existing_scientific_slot_admission(store, slot)
    if current_reservation is not None:
        if current_reservation.get("identity_binding_status") == "CONFLICT":
            raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
        if str(current_reservation.get("session_id") or "") != session_id:
            raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
        if not _scientific_slot_admission_matches_binding(current_reservation, binding):
            raise HficSessionError(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
            )
    # Typed family closure is frozen in the preflight receipt and remains an
    # admission gate even when the store has changed through a saved look.
    closed_family_ledger = ledger_from_receipt(receipt)
    for card in candidates:
        hit = candidate_hard_close_entry(card, closed_family_ledger)
        if hit is not None:
            raise HficSessionError("CLOSED_FAMILY_REOPEN", detail={
                "stage": "CANDIDATE_SUPPRESSION", "source_terminal": hit.get("terminal"),
                "scope_kind": hit.get("scope_kind"), "scope_id": hit.get("scope_id"),
                "source_receipt": hit.get("source_receipt"),
                "next_action": "KEEP_TYPED_CLOSE_SELECT_AUTHORIZED_DISTINCT_SCOPE",
            })
    # Check exact prior scope before saving, using the current visible history.
    # A full freeze here would incorrectly compare the pre-look receipt with the
    # store after its authorized discovery writes.
    grounded = draft.get("grounded_evidence")
    if selected_ref not in (None, "") and isinstance(grounded, Mapping):
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError, bind_prior_scope_evidence,
        )
        from solana_alpha_lab.factory.hfic_memory_policy import HficMemoryPolicyError

        selected_card = candidates[selected_index]
        selected_grounded = _bind_selected_look(grounded, selected_card, store=store)
        if selected_grounded.get("look_confirms_selected") is not False or runner_up_index >= 0:
            try:
                prior = build_prior_memory_snapshot(
                    store,
                    store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                    repo_root=repo_root,
                    as_of=receipt.get("session_started_at"),
                )
                if selected_grounded.get("look_confirms_selected") is not False:
                    bind_prior_scope_evidence(
                        selected_grounded, canonical_priors=prior["capsules"]
                    )
                if runner_up_index >= 0:
                    _rebind_runner_up_grounded_evidence(
                        {"grounded_evidence": dict(grounded),
                         "prior_memory": {"capsules": prior["capsules"]}},
                        candidates[runner_up_index],
                    )
            except (GroundedDiscoveryError, PriorMemoryCapacityError,
                    PriorMemoryUnidentifiedError, HficMemoryPolicyError) as exc:
                raise HficSessionError(exc.code) from exc
    if not _ordinary_discovery_requested(draft, receipt):
        freeze_draft(
            draft, preflight_receipt=preflight_receipt, store=store,
            repo_root=repo_root, verify_current_market_identity=True, persist=False,
        )
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else _stage_datetime(None)
    )
    git = repository_git_snapshot(Path(repo_root))
    transaction_id = f"RESEARCH-TXN-GENERATED-DRAFT-{slot.upper()}"
    admission, admission_event = _build_scientific_slot_admission_event(
        binding,
        repo_root=repo_root,
        transaction_id=transaction_id,
        stage_time=now,
        git_snapshot=git,
    )
    payload = {
        "research_artifact_id": f"HFIC-ART-FORGE-DRAFT-GENERATED-{draft_sha[:16].upper()}",
        "session_id": session_id,
        "owner_focus": str(receipt.get("owner_focus") or "AUTO"),
        "hfic_protocol": str(receipt.get("prompt_version") or PROMPT_VERSION),
        "artifact_kind": "FORGE_DRAFT",
        "draft_lifecycle": "GENERATED_BEFORE_FREEZE",
        "source_preflight_receipt_id": source_receipt_id,
        "source_preflight_receipt_sha256": source_receipt_hash,
        "ladder_representation_id": representation_id,
        "scientific_slot_sha256": slot,
        "market_evidence_epoch_sha256": receipt.get("market_evidence_epoch_sha256")
        or receipt.get("evidence_epoch_sha256"),
        "focus_key_sha256": receipt.get("focus_key_sha256") or focus_key_sha256(
            str(receipt.get("owner_focus") or "AUTO")
        ),
        "representation_semantic_version": fields.get("representation_semantic_version"),
        "control_session_id": fields.get("control_session_id"),
        "capability_epoch_sha256": capability,
        "memory_eligibility_sha256": memory,
        "evidence_surface_mode": evidence_mode,
        "representation_payload_sha256": fields.get("representation_payload_sha256"),
        "execution_binding_sha256": fields.get("execution_binding_sha256"),
        "model_provenance_sha256": fields.get("model_provenance_sha256"),
        "payload_canonical": draft_bytes.decode("utf-8"),
        "payload_sha256": draft_sha,
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    event = ResearchEvent(
        record_id=f"HFIC-ART-FORGE-DRAFT-GENERATED-{draft_sha[:16].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-FORGE-DRAFT-GENERATED-{draft_sha[:16].upper()}",
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git.head_sha,
        created_at=now,
    )
    def _recheck_generated_draft_under_writer_lease() -> None:
        _verify_required_context_dependency(store, receipt)
        observed_draft = find_generated_draft(
            store,
            market_evidence_epoch_sha256=market,
            owner_focus=str(receipt.get("owner_focus") or "AUTO"),
            representation_id=representation_id,
            representation_semantic_version=version,
            scientific_slot_sha256=slot,
        )
        if observed_draft is not None:
            if (
                observed_draft.get("payload_sha256") == draft_sha
                and observed_draft.get("session_id") == session_id
                and observed_draft.get("model_provenance_sha256")
                == fields.get("model_provenance_sha256")
                and generated_draft_matches_preflight_context(
                    observed_draft,
                    market_evidence_epoch_sha256=market,
                    scientific_slot_sha256=slot,
                    representation_id=representation_id,
                    representation_semantic_version=version,
                    owner_focus=str(receipt.get("owner_focus") or "AUTO"),
                    capability_epoch_sha256=capability,
                    memory_eligibility_sha256=memory,
                    evidence_surface_mode=(
                        str(evidence_mode)
                        if isinstance(evidence_mode, str)
                        else None
                    ),
                    control_session_id=(
                        str(fields.get("control_session_id"))
                        if isinstance(fields.get("control_session_id"), str)
                        else None
                    ),
                    representation_payload_sha256=(
                        str(fields.get("representation_payload_sha256"))
                        if isinstance(fields.get("representation_payload_sha256"), str)
                        else None
                    ),
                    execution_binding_sha256=(
                        str(fields.get("execution_binding_sha256"))
                        if isinstance(fields.get("execution_binding_sha256"), str)
                        else None
                    ),
                    model_provenance_sha256=(
                        str(fields.get("model_provenance_sha256"))
                        if isinstance(fields.get("model_provenance_sha256"), str)
                        else None
                    ),
                )
            ):
                raise HficSessionError("GENERATED_DRAFT_ALREADY_PERSISTED")
            raise HficSessionError("GENERATED_DRAFT_CONFLICT")
        observed_reservation = _existing_scientific_slot_admission(store, slot)
        if observed_reservation is not None:
            if observed_reservation.get("identity_binding_status") == "CONFLICT":
                raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
            if str(observed_reservation.get("session_id") or "") != session_id:
                raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED")
            if not _scientific_slot_admission_matches_binding(
                observed_reservation, binding
            ):
                raise HficSessionError(
                    "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
                )
            if (not _ordinary_discovery_requested(draft, receipt)
                    and not _matching_orphan_reservation_only_delta(
                        store, receipt, draft
                    )):
                raise HficSessionError("PREFLIGHT_STORE_DIGEST_MISMATCH")
            if any(item.record_id == admission_event.record_id for item in append_records):
                raise HficSessionError("GENERATED_DRAFT_RESERVATION_APPEARED")
            return
        _assert_scientific_admission(
            store,
            binding,
            repo_root=repo_root,
            representation_registry=representation_registry,
        )

    append_records = [event]
    if current_reservation is None:
        append_records.insert(0, admission_event)
    for attempt in range(4):
        try:
            store.append(
                append_records,
                transaction_id=transaction_id,
                before_commit=_recheck_generated_draft_under_writer_lease,
            )
            break
        except HficSessionError as exc:
            if str(exc) == "GENERATED_DRAFT_RESERVATION_APPEARED":
                append_records = [event]
                continue
            if str(exc) == "GENERATED_DRAFT_ALREADY_PERSISTED":
                replay = find_generated_draft(
                    store,
                    market_evidence_epoch_sha256=market,
                    owner_focus=str(receipt.get("owner_focus") or "AUTO"),
                    representation_id=representation_id,
                    representation_semantic_version=version,
                    scientific_slot_sha256=slot,
                )
                if replay is not None:
                    return replay
            raise
        except Exception as exc:
            if (
                getattr(exc, "code", None) == "WRITER_BUSY"
                and attempt < 3
            ):
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
    return payload


def _session_hypothesis_record_id(candidate_id: str, session_id: str) -> str:
    """A semantic candidate can have immutable cards in several evidence sessions.

    Keep candidate identity stable; scope only the append-only record identity.
    Historical unsuffixed records remain readable without migration.
    """
    return f"HFIC-HYP-{candidate_id}-{session_id}"


def _session_hypothesis_supersedes(store: Any, candidate_id: str, definition_sha256: str) -> str | None:
    """Link the same definition's new evidence binding to its immutable history."""
    prior = []
    for record in store.iter_committed_records():
        if str(getattr(record.record_kind, "value", record.record_kind)) != "HYPOTHESIS_VERSION":
            continue
        payload = json.loads(record.payload_json)
        if str(payload.get("hypothesis_version_id") or record.entity_id) != candidate_id:
            continue
        if payload.get("definition_sha256") != definition_sha256:
            raise HficSessionError("HFIC_HYPOTHESIS_HISTORY_IDENTITY_UNBOUND")
        prior.append(record)
    if not prior:
        return None
    roots = [row for row in prior if row.supersedes_record_id is None]
    legacy_roots = (
        {row.record_id for row in roots}
        if len(roots) > 1 and len({row.payload_sha256 for row in roots}) == 1
        else set()
    )
    superseded = {row.supersedes_record_id for row in prior}
    if legacy_roots.intersection(superseded):
        superseded.update(legacy_roots)
    heads = [row for row in prior if row.record_id not in superseded]
    if len(heads) > 1 and {row.record_id for row in heads} == legacy_roots:
        return min(legacy_roots)
    if len(heads) != 1:
        raise HficSessionError("HFIC_HYPOTHESIS_HISTORY_IDENTITY_UNBOUND")
    return heads[0].record_id


def _persisted_session_rejection_id(store: Any, session_id: str, candidate_id: str, prior: Mapping[str, Any]) -> str:
    matches = []
    for record in store.iter_committed_records():
        if str(getattr(record.record_kind, "value", record.record_kind)) != "DECISION_EVENT":
            continue
        payload = json.loads(record.payload_json)
        if (payload.get("session_id") == session_id
            and payload.get("hypothesis_version_id") == candidate_id
            and payload.get("decision_kind") == "REJECT"
            and payload.get("reason_code") == prior.get("reason_code")
            and payload.get("decision_event_id") == record.record_id):
            matches.append(record.record_id)
    if len(matches) != 1:
        raise HficSessionError("DECISION_REFERENCE_UNRESOLVED")
    return matches[0]


def _session_decision_record_id(candidate_id: str, session_id: str) -> str:
    return f"HFIC-DEC-{candidate_id}-{session_id}"


def persist_frozen_session(
    store: Any,
    frozen: Mapping[str, Any],
    *,
    repo_root: Any,
    identities: Sequence[Any],
    draft: Mapping[str, Any] | None = None,
    preflight_receipt: Mapping[str, Any] | None = None,
    stage_time: datetime | None = None,
    representation_registry: Mapping[str, Any] | None = None,
) -> None:
    """Append freeze records to an existing ResearchStore. Optional for unit tests."""

    from pathlib import Path

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    repair_admission = None
    if existing is not None:
        try:
            repair_admission = _assert_scientific_admission(
                store,
                frozen,
                repo_root=repo_root,
                representation_registry=representation_registry,
            )
        except HficSessionError:
            repair_admission = None
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            ACTION_RESUME_REPAIR_CONTINUATION,
        )

        if (
            not isinstance(repair_admission, Mapping)
            or repair_admission.get("action") != ACTION_RESUME_REPAIR_CONTINUATION
        ):
            return
    if stage_time is not None:
        _stage_datetime(lambda: stage_time)
    if repair_admission is None:
        repair_admission = _assert_scientific_admission(
            store,
            frozen,
            repo_root=repo_root,
            representation_registry=representation_registry,
        )
    context_binding = dict(frozen)
    if preflight_receipt is not None:
        if preflight_receipt.get("forge_context_packet_sha256") != frozen.get("forge_context_packet_sha256"):
            raise HficSessionError("FORGE_CONTEXT_HASH_MISMATCH")
        context_binding["forge_context_packet"] = preflight_receipt.get("forge_context_packet")
    _verify_required_context_dependency(store, context_binding)
    if isinstance(draft, Mapping):
        _validate_fresh_draft_scopes(draft, store=store, identities=identities)
    else:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError, stored_look_scope, validate_fresh_card_scope,
        )
        for key in ("critic_input_packet", "runner_up_critic_input_packet"):
            packet = frozen.get(key)
            if not isinstance(packet, Mapping):
                continue
            evidence = packet.get("grounded_evidence")
            look = stored_look_scope(store, evidence) if isinstance(evidence, Mapping) else None
            try:
                validate_fresh_card_scope(packet["selected_candidate"], look_scope=look,
                                          require_look_axes=bool(look))
            except GroundedDiscoveryError as exc:
                raise HficSessionError(exc.code, detail=exc.detail) from exc
    repair_disposition = None
    if isinstance(repair_admission, Mapping):
        repair_disposition = repair_admission.get(
            "repair_continuation_disposition_sha256"
        )
    # Authorized repair keeps the parent slot reservation; a new capability /
    # execution binding must not rewrite or collide with the reserved digest.
    git = repository_git_snapshot(Path(repo_root))
    now = (
        _stage_datetime(lambda: stage_time)
        if stage_time is not None
        else bound_session_started_at(frozen)
    )
    transaction_id = f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFIC-')}"
    if isinstance(repair_disposition, str) and repair_disposition:
        transaction_id = (
            f"RESEARCH-TXN-{session_id.replace('HFIC-SESS-', 'HFIC-')}"
            f"-REPAIR-{repair_disposition[:12].upper()}"
        )
    producer = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

    def event(
        *,
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: dict[str, Any],
        hypothesis_version_id: str | None = None,
        supersedes_record_id: str | None = None,
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
            supersedes_record_id=supersedes_record_id,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=producer,
            producer_git_sha=git.head_sha,
            created_at=now,
        )

    prompt_version = str(frozen.get("prompt_version") or PROMPT_VERSION)
    cycle_payload = {
                "research_cycle_id": session_id,
                "session_id": session_id,
                "phase": "FROZEN_AWAITING_CRITIC",
                "hfic_protocol": prompt_version,
                "prompt_version": prompt_version,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "memory_eligibility_sha256": frozen.get("memory_eligibility_sha256"),
                "selected_candidate_id": frozen["selected_candidate_id"],
                "runner_up_candidate_id": frozen["runner_up_candidate_id"],
                "rejected_alternative_id": frozen.get("rejected_alternative_id"),
                "candidate_ids": list(frozen.get("candidate_ids") or []),
                "critic_input_packet_sha256": frozen.get("critic_input_packet_sha256"),
                "primary_critic_input_packet_sha256": frozen.get(
                    "primary_critic_input_packet_sha256"
                )
                or frozen.get("critic_input_packet_sha256"),
                "runner_up_critic_input_packet_sha256": frozen.get(
                    "runner_up_critic_input_packet_sha256"
                ),
                "runner_up_definition_sha256": frozen.get("runner_up_definition_sha256"),
                "runner_up_display_ordinal": frozen.get("runner_up_display_ordinal"),
                "selected_definition_sha256": frozen.get("selected_definition_sha256"),
                "selected_display_ordinal": frozen.get("selected_display_ordinal"),
                "forge_context_packet_sha256": frozen.get("forge_context_packet_sha256"),
                "ladder_representation_id": frozen.get("ladder_representation_id"),
                "control_session_id": frozen.get("control_session_id"),
                "git_composite_sha256": frozen.get("git_composite_sha256"),
                "research_memory_as_of": frozen.get("research_memory_as_of"),
                "revision_count": int(frozen.get("revision_count") or 0),
                "hfic_cycle_seq": _next_cycle_seq(existing),
                **_execution_identity_fields(frozen),
            }
    if (
        isinstance(repair_admission, Mapping)
        and isinstance(
            repair_admission.get("repair_continuation_disposition_sha256"), str
        )
        and repair_admission.get("repair_continuation_disposition_sha256")
    ):
        cycle_payload["repair_continuation_disposition_sha256"] = repair_admission[
            "repair_continuation_disposition_sha256"
        ]
        if isinstance(existing, Mapping):
            cycle_payload["parent_cycle_seq"] = int(existing.get("hfic_cycle_seq") or 0)
    _copy_evidence_surface_mode(cycle_payload, frozen)
    _stamp_split_identity(cycle_payload, frozen)
    _stamp_market_evidence_basis(cycle_payload, frozen)
    discovered_scope = _discovery_candidate_scope(frozen)
    if discovered_scope:
        cycle_payload["discovery_candidate_scope"] = discovered_scope
    if isinstance(frozen.get("grounded_candidates"), list):
        cycle_payload["grounded_candidates"] = list(frozen["grounded_candidates"])
    if "closed_or_suppressed_collision_count" in frozen:
        cycle_payload["closed_or_suppressed_collision_count"] = frozen[
            "closed_or_suppressed_collision_count"
        ]
    if frozen.get("prefreeze_capability_repair") is True:
        cycle_payload["prefreeze_capability_repair"] = True
        cycle_payload["generated_draft_capability_epoch_sha256"] = frozen.get(
            "generated_draft_capability_epoch_sha256"
        )
        cycle_payload["generated_draft_execution_binding_sha256"] = frozen.get(
            "generated_draft_execution_binding_sha256"
        )
        cycle_payload["recovery_capability_epoch_sha256"] = frozen.get(
            "recovery_capability_epoch_sha256"
        )
        cycle_payload["recovery_execution_binding_sha256"] = frozen.get(
            "recovery_execution_binding_sha256"
        )
    freeze_suffix = "FROZEN"
    repair_disp = cycle_payload.get("repair_continuation_disposition_sha256")
    if isinstance(repair_disp, str) and repair_disp:
        freeze_suffix = f"REPAIR-FROZEN-{repair_disp[:12].upper()}"
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-{freeze_suffix}",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload=cycle_payload,
        )
    ]
    # Repair re-entry must not rewrite durable parent hypothesis cards. New
    # selected cards use disposition-scoped record ids for append-only replay.
    cards = _cards_for_identities(identities, frozen, draft)
    for identity, card in zip(identities, cards, strict=True):
        hyp_id = (
            f"{_session_hypothesis_record_id(identity.candidate_id, session_id)}-REPAIR-{repair_disp[:12].upper()}"
            if isinstance(repair_disp, str) and repair_disp
            else _session_hypothesis_record_id(identity.candidate_id, session_id)
        )
        records.append(
            event(
                record_id=hyp_id,
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=identity.candidate_id,
                hypothesis_version_id=identity.candidate_id,
                supersedes_record_id=_session_hypothesis_supersedes(store, identity.candidate_id, identity.full_sha256),
                payload={
                    "hypothesis_version_id": identity.candidate_id,
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
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
                    **_hypothesis_scope_fields(frozen, identity.definition, card),
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
    critic_input_id = (
        f"HFIC-ART-CRITIC-INPUT-{session_id}-{freeze_suffix}"
        if isinstance(repair_disp, str) and repair_disp
        else f"HFIC-ART-CRITIC-INPUT-{session_id}"
    )
    records.append(
        event(
            record_id=critic_input_id,
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=critic_input_id,
            payload={
                "research_artifact_id": critic_input_id,
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "CRITIC_INPUT_PACKET",
                "payload_canonical": packet_bytes,
                "payload_sha256": hashlib.sha256(
                    packet_bytes.encode("utf-8")
                ).hexdigest(),
            },
        )
    )
    runner_up_packet = frozen.get("runner_up_critic_input_packet")
    if isinstance(runner_up_packet, Mapping):
        runner_up_bytes = json.dumps(
            runner_up_packet,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        runner_up_id = (
            f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{freeze_suffix}"
            if isinstance(repair_disp, str) and repair_disp
            else f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP"
        )
        records.append(
            event(
                record_id=runner_up_id,
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=runner_up_id,
                payload={
                    "research_artifact_id": runner_up_id,
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "CRITIC_INPUT_PACKET",
                    "payload_canonical": runner_up_bytes,
                    "payload_sha256": hashlib.sha256(
                        runner_up_bytes.encode("utf-8")
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
        draft_id = (
            f"HFIC-ART-FORGE-DRAFT-{session_id}-{freeze_suffix}"
            if isinstance(repair_disp, str) and repair_disp
            else f"HFIC-ART-FORGE-DRAFT-{session_id}"
        )
        records.append(
            event(
                record_id=draft_id,
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=draft_id,
                payload={
                    "research_artifact_id": draft_id,
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "FORGE_DRAFT",
                    "payload_canonical": draft_bytes,
                    "payload_sha256": hashlib.sha256(
                        draft_bytes.encode("utf-8")
                    ).hexdigest(),
                },
            )
        )
    _append_session_records_with_slot(
        store, records, transaction_id=transaction_id, binding=context_binding,
        repo_root=repo_root, stage_time=now,
        representation_registry=representation_registry,
        reserve_slot=not bool(repair_disposition),
    )


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
        cycle_row = {
                "session_id": session_id,
                "session_state": payload.get("phase"),
                "phase": payload.get("phase"),
                "evidence_epoch_sha256": payload.get("evidence_epoch_sha256"),
                "focus_key_sha256": payload.get("focus_key_sha256"),
                "search_key_sha256": payload.get("search_key_sha256"),
                "memory_eligibility_sha256": payload.get("memory_eligibility_sha256"),
                "prompt_version": payload.get("prompt_version"),
                "owner_focus": payload.get("owner_focus"),
                "effective_at": getattr(record, "effective_at", ""),
                "record_id": str(getattr(record, "record_id", "") or ""),
                "hfic_cycle_seq": int(payload.get("hfic_cycle_seq") or 0),
                "evidence_surface_mode": payload.get("evidence_surface_mode"),
                "market_evidence_epoch_sha256": payload.get(
                    "market_evidence_epoch_sha256"
                ),
                "market_evidence_basis": payload.get("market_evidence_basis"),
                "capability_epoch_sha256": payload.get("capability_epoch_sha256"),
                "ladder_representation_id": payload.get("ladder_representation_id"),
                "control_session_id": payload.get("control_session_id"),
                "representation_semantic_version": payload.get(
                    "representation_semantic_version"
                ),
                "representation_payload_sha256": payload.get(
                    "representation_payload_sha256"
                ),
                "scientific_slot_sha256": payload.get("scientific_slot_sha256"),
                "execution_binding_sha256": payload.get(
                    "execution_binding_sha256"
                ),
                "model_provenance_sha256": payload.get("model_provenance_sha256"),
                "cycle_index": payload.get("cycle_index"),
                "critic_terminal": payload.get("critic_terminal"),
                "final_session_terminal": payload.get("final_session_terminal"),
                "selected_candidate_id": payload.get("selected_candidate_id"),
                "run_id": payload.get("run_id") or payload.get("forge_run_id"),
                "repair_continuation_disposition_sha256": payload.get(
                    "repair_continuation_disposition_sha256"
                ),
                "session_receipt_sha256": payload.get("session_receipt_sha256"),
                "parent_cycle_seq": payload.get("parent_cycle_seq"),
            }
        cycle_row["_identity_fields_present"] = {
            key
            for key in (
                "evidence_epoch_sha256",
                "market_evidence_epoch_sha256",
                "market_evidence_basis",
                "capability_epoch_sha256",
                "ladder_representation_id",
                "control_session_id",
                "representation_semantic_version",
                "representation_payload_sha256",
                "scientific_slot_sha256",
                "execution_binding_sha256",
                "model_provenance_sha256",
                "cycle_index",
            )
            if key in payload
        }
        cycles.append(cycle_row)
    latest: dict[str, dict[str, Any]] = {}
    for candidate in cycles:
        session_id = str(candidate["session_id"])
        phase = _effective_cycle_phase(
            candidate.get("session_state"),
            has_receipt=session_id in receipt_ids,
            has_critic=session_id in critic_ids,
        )
        candidate = {**candidate, "session_state": phase, "phase": phase}
        current = latest.get(session_id)
        if current is None or _cycle_better(candidate, current):
            latest[session_id] = candidate
    # Immutable admission: restore identity from an earlier stamped cycle only
    # when the complete history remains self-consistent.  A partial head must
    # not be assembled from contradictory market/slot/binding rows.
    by_session_cycles: dict[str, list[dict[str, Any]]] = {}
    for candidate in cycles:
        by_session_cycles.setdefault(str(candidate["session_id"]), []).append(candidate)
    identity_fields = (
        "market_evidence_epoch_sha256",
        "market_evidence_basis",
        "capability_epoch_sha256",
        "ladder_representation_id",
        "control_session_id",
        "representation_semantic_version",
        "representation_payload_sha256",
        "scientific_slot_sha256",
        "execution_binding_sha256",
        "model_provenance_sha256",
        "cycle_index",
    )
    for sid, rows in by_session_cycles.items():
        head = latest.get(sid)
        if head is None:
            continue
        head_present = set(head.pop("_identity_fields_present", set()))
        ordered = sorted(rows, key=lambda item: int(item.get("hfic_cycle_seq") or 0))
        conflicts: set[str] = set()
        head_is_repair = bool(head.get("repair_continuation_disposition_sha256"))
        repair_mutable = {
            "capability_epoch_sha256",
            "execution_binding_sha256",
            "model_provenance_sha256",
            "representation_payload_sha256",
        }
        for row in ordered:
            fields = {
                **_split_identity_fields(row),
                **{
                    key: row[key]
                    for key in identity_fields
                    if row.get(key) not in (None, "")
                },
            }
            if not fields:
                continue
            for key, value in fields.items():
                current = head.get(key)
                if key in head_present:
                    if current not in (None, "") and current != value:
                        # Authorized repair may carry a new capability/execution
                        # binding while keeping the scientific slot; parent
                        # values must not trip CONFLICT against the repair head.
                        if head_is_repair and key in repair_mutable:
                            continue
                        conflicts.add(key)
                    elif current in (None, ""):
                        # A durable explicit UNKNOWN is not reconstructable
                        # from an older cycle.  Keep it unknown and surface a
                        # conflict instead of reviving a current slot.
                        conflicts.add(key)
                else:
                    head[key] = value
        # An explicit slot must reproduce from its durable market,
        # representation, version and focus fields.  Otherwise this history
        # is occupied-but-unresolved, never a free budget slot.
        if head.get("scientific_slot_sha256") not in (None, ""):
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                session_scientific_slot_sha256,
            )

            if session_scientific_slot_sha256(head) is None:
                conflicts.add("scientific_slot_sha256")
        if conflicts:
            head["identity_binding_status"] = "CONFLICT"
            head["identity_conflict_fields"] = sorted(conflicts)
            known_markets: set[str] = set()
            market_scope_complete = True
            for row in rows:
                present = set(row.get("_identity_fields_present", set()))
                has_a5_identity = bool(present.intersection(identity_fields))
                value = row.get("market_evidence_epoch_sha256")
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                    known_markets.add(value)
                elif has_a5_identity:
                    market_scope_complete = False
            head["identity_conflict_market_epochs"] = sorted(known_markets)
            head["identity_conflict_market_scope_complete"] = (
                market_scope_complete and bool(known_markets)
            )
    return list(latest.values())


_LADDER_REPRESENTATION_IDS = frozenset(
    {"NORMALIZED_TRAJECTORY_V1", "SYNTHETIC_LATER_V2", "NORMALIZED_TRAJECTORY_EPISODES_V1"}
)


def _mapping_ladder_slot(source: Mapping[str, Any] | None) -> tuple[str, str | None]:
    representation = "BASE"
    parent: str | None = None
    if not isinstance(source, Mapping):
        return representation, parent
    rid = source.get("ladder_representation_id") or source.get("representation_id")
    if rid in _LADDER_REPRESENTATION_IDS:
        representation = str(rid)
    elif source.get("normalized_trajectory_v1"):
        representation = "NORMALIZED_TRAJECTORY_V1"
    sid = source.get("control_session_id")
    if isinstance(sid, str) and sid:
        parent = sid
    if representation == "BASE" and parent:
        representation = "NORMALIZED_TRAJECTORY_V1"
    return representation, parent


def bundle_ladder_slot(
    bundle: Mapping[str, Any], packet: Mapping[str, Any] | None = None
) -> tuple[str, str | None]:
    embedded = (
        bundle.get("forge_context_packet")
        if isinstance(bundle.get("forge_context_packet"), Mapping)
        else None
    )
    receipt = (
        bundle.get("session_receipt")
        if isinstance(bundle.get("session_receipt"), Mapping)
        else None
    )
    representation = "BASE"
    parent: str | None = None
    for source in (packet, embedded, receipt, bundle):
        observed_rep, observed_parent = _mapping_ladder_slot(
            source if isinstance(source, Mapping) else None
        )
        if observed_rep != "BASE":
            representation = observed_rep
        if observed_parent:
            parent = observed_parent
    session_id = str(bundle.get("session_id") or "")
    if parent == session_id:
        parent = None
    return representation, parent


# Compatibility alias for historical internal callers; new production code
# uses the explicit public seam above.
_bundle_ladder_slot = bundle_ladder_slot


def _preflight_ladder_slot(
    preflight: Mapping[str, Any] | None,
) -> tuple[str, str | None]:
    if not isinstance(preflight, Mapping):
        return "BASE", None
    packet = (
        preflight.get("forge_context_packet")
        if isinstance(preflight.get("forge_context_packet"), Mapping)
        else None
    )
    representation = "BASE"
    parent: str | None = None
    for source in (packet, preflight):
        observed_rep, observed_parent = _mapping_ladder_slot(
            source if isinstance(source, Mapping) else None
        )
        if observed_rep != "BASE":
            representation = observed_rep
        if observed_parent:
            parent = observed_parent
    return representation, parent


def _is_ladder_challenger_preflight(preflight: Mapping[str, Any] | None) -> bool:
    if not isinstance(preflight, Mapping):
        return False
    representation, parent = _preflight_ladder_slot(preflight)
    return representation in _LADDER_REPRESENTATION_IDS and bool(parent)


def _repair_disposition_for_session(
    store: Any,
    session: Mapping[str, Any],
) -> dict[str, Any] | None:
    """One store disposition for this session and slot. Several matches are not guessed."""

    from solana_alpha_lab.factory.hfic_repair_continuation import (
        list_repair_continuation_dispositions,
    )

    session_id = str(session.get("session_id") or "")
    slot = session.get("scientific_slot_sha256")
    if not session_id:
        return None
    matches = []
    for item in list_repair_continuation_dispositions(store):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("parent_session_id") or "") != session_id:
            continue
        if isinstance(slot, str) and item.get("scientific_slot_sha256") != slot:
            continue
        if item.get("status") not in {"AUTHORIZED", "CLOSED"}:
            continue
        matches.append(dict(item))
    if len(matches) != 1:
        return None
    return matches[0]


def _selected_draft_cannot_inherit_repair(
    bundle: Mapping[str, Any],
    draft: Mapping[str, Any] | None,
) -> bool:
    """A selected draft does not inherit a no-worthy repair terminal."""

    if not isinstance(draft, Mapping):
        return False
    if not str(draft.get("selected_candidate_ref") or "").strip():
        return False
    return not str(bundle.get("selected_candidate_id") or "").strip()


def _assert_repair_retry_evidence(
    bundle: Mapping[str, Any],
    draft: Mapping[str, Any] | None,
) -> None:
    """A repeated repair freeze must name the stored result, not a different look."""

    if not isinstance(draft, Mapping):
        return
    evidence = draft.get("grounded_evidence")
    stored_sha = bundle.get("grounded_result_sha256")
    stored_refs = bundle.get("grounded_result_refs")
    if not isinstance(evidence, Mapping):
        if isinstance(stored_sha, str) and stored_sha:
            raise HficSessionError("GROUNDED_RESULT_MISMATCH")
        return
    observed_sha = evidence.get("result_sha256")
    if not isinstance(stored_sha, str) or stored_sha != observed_sha:
        raise HficSessionError("GROUNDED_RESULT_MISMATCH")
    if isinstance(stored_refs, list) and list(evidence.get("result_refs") or []) != list(
        stored_refs
    ):
        raise HficSessionError("GROUNDED_RESULT_MISMATCH")


def _lookup_existing_freeze_session(
    store: Any,
    preflight_receipt: Mapping[str, Any],
    draft: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    epoch_hint = str(preflight_receipt.get("evidence_epoch_sha256") or "")
    focus_hint = str(preflight_receipt.get("focus_key_sha256") or "")
    if not epoch_hint or not focus_hint:
        return None
    identity = _execution_identity_fields(preflight_receipt)
    execution_context: dict[str, str] = {}
    for key in (
        "capability_epoch_sha256",
        "representation_payload_sha256",
        "model_provenance_sha256",
    ):
        value = preflight_receipt.get(key)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            value = identity.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            execution_context[key] = value

    lookup_args = dict(
        memory_eligibility_sha256=str(
            preflight_receipt.get("memory_eligibility_sha256") or ""
        )
        or None,
        evidence_surface_mode=str(preflight_receipt.get("evidence_surface_mode") or "")
        or None,
        ladder_representation_id=_preflight_ladder_slot(preflight_receipt)[0],
        control_session_id=_preflight_ladder_slot(preflight_receipt)[1],
        representation_semantic_version=identity.get("representation_semantic_version"),
        scientific_slot_sha256=identity.get("scientific_slot_sha256"),
        cycle_index=int(identity.get("cycle_index") or 1),
    )
    existing = find_session_by_epoch_focus(
        store,
        epoch_hint,
        focus_hint,
        **lookup_args,
        execution_context=execution_context or None,
    )
    if existing is not None:
        # A stamped repair result must match this draft. The parent cycle has
        # no grounded hash, so the first repair freeze — including a selected
        # candidate — still proceeds.
        if isinstance(existing.get("grounded_result_sha256"), str) and existing.get(
            "grounded_result_sha256"
        ):
            if _selected_draft_cannot_inherit_repair(existing, draft):
                raise HficSessionError(
                    "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
                )
            _assert_repair_retry_evidence(existing, draft)
        return existing
    # Occupied historical rows stay occupied even when the caller has no
    # execution stamp. Returning None here used to look like a free slot.
    historical = find_session_by_epoch_focus(
        store,
        epoch_hint,
        focus_hint,
        **{
            **lookup_args,
            "memory_eligibility_sha256": None,
            "execution_context": None,
            "ignore_memory_eligibility": True,
            "ignore_evidence_surface_mode": True,
        },
    )
    if historical is None:
        return None
    # Capability/model drift against a legacy parent is not a second session.
    # Only a store disposition for this session and slot may continue, and an
    # already bound repair terminal is that saved result — not the parent
    # NO_WORTHY that predates the grant. A selected draft does not inherit a
    # no-worthy grant. Market identity is unchanged here: the historical row
    # was found on the same evidence epoch.
    disposition = _repair_disposition_for_session(store, historical)
    if disposition is None:
        raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING")
    from solana_alpha_lab.factory.hfic_repair_continuation import (
        _disposition_bound_repair_completion,
    )

    bundle = load_session_bundle(store, str(historical.get("session_id") or ""))
    if not isinstance(bundle, Mapping):
        raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING")
    if _disposition_bound_repair_completion(bundle, disposition) is not None:
        if _selected_draft_cannot_inherit_repair(bundle, draft):
            raise HficSessionError(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
            )
        _assert_repair_retry_evidence(bundle, draft)
        return bundle
    if str(disposition.get("status") or "") != "AUTHORIZED":
        raise HficSessionError("SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING")
    return None


def _bound_from_ladder_challenger_preflight(
    preflight: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    memory_as_of: str,
    verify_current_market_identity: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist a stamped V1/V2 freeze without START_NEW_SESSION bind.

    Marker + parent alone are insufficient for V1: require verified
    representation payload hashes embedded on the forge_context_packet.
    Reuses scientific challenger revalidation when the envelope is present.
    """

    packet = preflight.get("forge_context_packet")
    if not isinstance(packet, Mapping) or not packet:
        raise HficSessionError("FORGE_CONTEXT_REQUIRED")
    representation, parent = _preflight_ladder_slot(preflight)
    if representation == "NORMALIZED_TRAJECTORY_V1":
        from solana_alpha_lab.factory.hfic_representation_probe import (
            RepresentationProbeError,
            _assert_challenger_bound_to_control,
            _validate_challenger_packet,
            control_baseline_from_receipt,
        )

        challenger = preflight.get("ladder_challenger_packet")
        if not isinstance(challenger, Mapping) or not challenger:
            raise HficSessionError("LADDER_CHALLENGER_PACKET_REQUIRED")
        control_receipt = preflight.get("ladder_control_receipt")
        if not isinstance(control_receipt, Mapping) or not control_receipt:
            raise HficSessionError("LADDER_CONTROL_RECEIPT_REQUIRED")
        try:
            validated, rep = _validate_challenger_packet(challenger)
        except RepresentationProbeError as exc:
            raise HficSessionError(f"LADDER_CHALLENGER_INVALID:{exc}") from exc
        if parent and validated.get("control_session_id") != parent:
            raise HficSessionError("LADDER_CHALLENGER_PARENT_MISMATCH")
        try:
            baseline = control_baseline_from_receipt(control_receipt)
            _assert_challenger_bound_to_control(validated, baseline)
        except RepresentationProbeError as exc:
            raise HficSessionError(f"LADDER_CHALLENGER_CONTROL_UNBOUND:{exc}") from exc
        if parent and baseline.session_id != parent:
            raise HficSessionError("LADDER_CHALLENGER_PARENT_MISMATCH")
        for key in (
            "normalized_trajectory_v1",
            "representation_payload_sha256",
            "representation_search_key_sha256",
        ):
            if packet.get(key) != validated.get(key):
                raise HficSessionError("LADDER_CHALLENGER_PACKET_DRIFT")
        corpus = rep.get("corpus_binding") if isinstance(rep, Mapping) else None
        cohort = corpus.get("cohort_id") if isinstance(corpus, Mapping) else None
        bound_ids = packet.get("bound_visible_cohort_ids")
        if isinstance(cohort, str) and cohort.strip():
            if bound_ids != [cohort.strip()]:
                raise HficSessionError("LADDER_CHALLENGER_SCOPE_DRIFT")
        else:
            raise HficSessionError("LADDER_CHALLENGER_COHORT_MISSING")
        # Outer freeze identity must equal verified CONTROL / representation keys
        # before any store write; mutable receipt JSON cannot rebind the search.
        epoch = str(preflight.get("evidence_epoch_sha256") or "")
        focus_key = str(preflight.get("focus_key_sha256") or "")
        search_key_bound = str(preflight.get("search_key_sha256") or "")
        if not epoch or not focus_key or not search_key_bound:
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
        rep_search = str(validated.get("representation_search_key_sha256") or "")
        if search_key_bound != rep_search:
            raise HficSessionError("LADDER_SEARCH_KEY_DRIFT")
        if epoch != baseline.evidence_epoch_sha256:
            raise HficSessionError("LADDER_EVIDENCE_EPOCH_DRIFT")
        baseline_focus = baseline.focus_key_sha256
        if isinstance(baseline_focus, str) and baseline_focus and focus_key != baseline_focus:
            raise HficSessionError("LADDER_FOCUS_KEY_DRIFT")
        # Validate the production A3 market/capability receipt only after the
        # ladder envelope's own immutable keys.  A caller that mutates the
        # outer search key must receive the precise ladder drift reason before
        # any market-basis diagnosis, and no write may occur either way.
        _validate_split_identity_binding(
            preflight,
            repo_root=Path(repo_root),
            data_root=Path(getattr(store, "_root")),
            require_current_market_identity=verify_current_market_identity,
        )
    else:
        epoch = str(preflight.get("evidence_epoch_sha256") or "")
        focus_key = str(preflight.get("focus_key_sha256") or "")
        search_key_bound = str(preflight.get("search_key_sha256") or "")
        if not epoch or not focus_key or not search_key_bound:
            raise HficSessionError("PREFLIGHT_RECEIPT_REQUIRED")
    from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet

    digest = persist_forge_context_packet(
        Path(getattr(store, "_root")),
        dict(packet),
        store=store,
        repo_root=Path(repo_root) if repo_root is not None else None,
    )
    receipt = dict(preflight)
    receipt["forge_context_packet"] = dict(packet)
    receipt["forge_context_packet_sha256"] = digest
    bound = {
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key_bound,
        "owner_focus": str(preflight.get("owner_focus") or "AUTO"),
        "live_git_head": str(preflight.get("live_git_head") or "0" * 40).lower(),
        "git_composite_sha256": preflight.get("git_composite_sha256"),
        "store_inventory_digest": store.diagnostics().committed_inventory_sha256,
        "memory_eligibility_sha256": preflight.get("memory_eligibility_sha256"),
        "session_started_at": preflight.get("session_started_at"),
        "research_memory_as_of": memory_as_of,
        "forge_context_packet_sha256": digest,
    }
    return receipt, bound


def _bind_store_freeze_preflight(
    draft: Mapping[str, Any],
    preflight_receipt: Mapping[str, Any],
    *,
    store: Any,
    repo_root: Any,
    memory_as_of: str,
    verify_current_market_identity: bool = False,
) -> tuple[Mapping[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Return (receipt, existing_bundle, bound). Ladder slots skip START_NEW_SESSION."""

    # Existing ladder rows are a readback shortcut, not a way around the
    # current-input identity boundary.  The normal freeze path may reuse a
    # historical row, but callers that explicitly require current-market
    # verification must validate it before returning the existing bundle.
    if _is_ladder_challenger_preflight(preflight_receipt) and verify_current_market_identity:
        _validate_split_identity_binding(
            preflight_receipt,
            repo_root=Path(repo_root),
            data_root=Path(getattr(store, "_root")),
            require_current_market_identity=True,
        )

    existing = _lookup_existing_freeze_session(
        store, preflight_receipt, draft
    )
    if (
        existing is not None
        and isinstance(existing.get("repair_continuation_disposition_sha256"), str)
        and existing.get("repair_continuation_disposition_sha256")
        and not _is_ladder_challenger_preflight(preflight_receipt)
    ):
        # AUTHORIZED retry and CLOSED readback both return the stored terminal.
        # Neither may skip preflight integrity, draft/context binding, or the
        # caller's current-market check. Store digest lags the first freeze
        # write, so it is not the currency proof. A failed check writes nothing.
        # CLOSED is not a new execution: the grant stays closed.
        disposition = _repair_disposition_for_session(store, existing)
        if disposition is None or str(disposition.get("status") or "") not in {
            "AUTHORIZED",
            "CLOSED",
        }:
            raise HficSessionError(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
            )
        bound = bind_preflight_receipt(
            preflight_receipt,
            draft,
            store=store,
            repo_root=repo_root,
            require_current_store_digest=False,
            require_current_market_identity=verify_current_market_identity,
        )
        if bound["research_memory_as_of"] != memory_as_of:
            raise HficSessionError("RESEARCH_MEMORY_AS_OF_MISMATCH")
        _validate_draft_forge_context_binding(draft, preflight_receipt, bound)
        readback = dict(existing)
        if verify_current_market_identity:
            readback["current_market_identity"] = "VERIFIED"
        else:
            # Historical bytes are not a current-market confirmation.
            readback["current_market_identity"] = "NOT_VERIFIED"
        readback["repair_readback_status"] = str(disposition.get("status"))
        return preflight_receipt, readback, None
    if existing is not None and _is_ladder_challenger_preflight(preflight_receipt):
        return preflight_receipt, existing, None
    if _is_ladder_challenger_preflight(preflight_receipt):
        if str(draft.get("owner_focus") or "AUTO") != str(
            preflight_receipt.get("owner_focus") or "AUTO"
        ):
            raise HficSessionError("FOCUS_CONTEXT_DRIFT")
        receipt, bound = _bound_from_ladder_challenger_preflight(
            preflight_receipt,
            store=store,
            repo_root=repo_root,
            memory_as_of=memory_as_of,
            verify_current_market_identity=verify_current_market_identity,
        )
        return receipt, None, bound
    bound = bind_preflight_receipt(
        preflight_receipt,
        draft,
        store=store,
        repo_root=repo_root,
        require_current_store_digest=existing is None,
        require_current_market_identity=verify_current_market_identity,
    )
    if bound["research_memory_as_of"] != memory_as_of:
        raise HficSessionError("RESEARCH_MEMORY_AS_OF_MISMATCH")
    _validate_draft_forge_context_binding(draft, preflight_receipt, bound)
    return preflight_receipt, None, bound


def _stamp_ladder_slot(
    result: dict[str, Any], preflight: Mapping[str, Any] | None
) -> None:
    if not isinstance(preflight, Mapping):
        return
    representation, parent = _preflight_ladder_slot(preflight)
    result["ladder_representation_id"] = representation
    if parent:
        result["control_session_id"] = parent
    packet = preflight.get("forge_context_packet")
    if isinstance(packet, Mapping):
        result["forge_context_packet"] = dict(packet)


def find_session_by_epoch_focus(
    store: Any,
    epoch: str,
    focus_key: str,
    memory_eligibility_sha256: str | None = None,
    evidence_surface_mode: str | None = None,
    ladder_representation_id: str | None = None,
    control_session_id: str | None = None,
    representation_semantic_version: str | None = None,
    scientific_slot_sha256: str | None = None,
    execution_context: Mapping[str, Any] | None = None,
    ignore_memory_eligibility: bool = False,
    ignore_evidence_surface_mode: bool = False,
    cycle_index: int = 1,
) -> dict[str, Any] | None:
    from solana_alpha_lab.factory.hfic_control_integrity import (
        session_evidence_surface_mode,
    )
    from solana_alpha_lab.factory.hfic_memory_policy import session_memory_eligibility

    expected_mode = session_evidence_surface_mode(
        {"evidence_surface_mode": evidence_surface_mode}
        if evidence_surface_mode
        else None
    )
    wanted_rep = ladder_representation_id or "BASE"
    wanted_parent = control_session_id if isinstance(control_session_id, str) and control_session_id else None
    matched: list[dict[str, Any]] = []
    for item in list_hfic_sessions(store):
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            session_matches_epoch_for_lookup,
        )

        if not session_matches_epoch_for_lookup(item, epoch):
            continue
        if item.get("focus_key_sha256") != focus_key:
            continue
        if not ignore_memory_eligibility and session_memory_eligibility(
            item
        ) != session_memory_eligibility(
            {"memory_eligibility_sha256": memory_eligibility_sha256}
        ):
            continue
        if (
            not ignore_evidence_surface_mode
            and session_evidence_surface_mode(item) != expected_mode
        ):
            continue
        if isinstance(execution_context, Mapping):
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                session_slot_matches_execution_context,
            )

            if not session_slot_matches_execution_context(
                item,
                memory_eligibility_sha256=memory_eligibility_sha256,
                evidence_surface_mode=expected_mode,
                execution_context=execution_context,
            ):
                continue
        bundle = load_session_bundle(store, str(item.get("session_id") or ""))
        if bundle is None:
            continue
        packet = None
        digest = bundle.get("forge_context_packet_sha256")
        receipt = bundle.get("session_receipt") if isinstance(bundle.get("session_receipt"), Mapping) else {}
        if not isinstance(digest, str):
            digest = receipt.get("forge_context_packet_sha256") if isinstance(receipt, Mapping) else None
        if isinstance(digest, str) and len(digest) == 64:
            from solana_alpha_lab.factory.hfic_preflight import FORGE_CONTEXT_ARTIFACT_DIR

            blob = Path(store._root) / FORGE_CONTEXT_ARTIFACT_DIR / f"{digest}.json"
            if blob.is_file() and not blob.is_symlink():
                try:
                    loaded = json.loads(blob.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    loaded = None
                if isinstance(loaded, dict):
                    packet = loaded
        observed_rep, observed_parent = _bundle_ladder_slot(bundle, packet)
        if observed_rep != wanted_rep:
            continue
        if observed_parent != wanted_parent:
            continue
        if (
            representation_semantic_version is not None
            and bundle.get("representation_semantic_version")
            != representation_semantic_version
        ):
            continue
        if (
            scientific_slot_sha256 is not None
            and bundle.get("scientific_slot_sha256") != scientific_slot_sha256
        ):
            # Split-era BASE rows may predate the explicit slot stamp. They
            # remain a known occupied market look and must not be duplicated.
            # An explicitly authorized additional cycle never inherits an unstamped cycle-1 row.
            if not (
                wanted_rep == "BASE"
                and cycle_index <= 1
                and not bundle.get("scientific_slot_sha256")
                and item.get("market_evidence_epoch_sha256") == epoch
            ):
                continue
        matched.append(item)
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
    *,
    existing: Mapping[str, Any] | None = None,
) -> str:
    selected_id, expected_packet, expected_def = _screening_identity(frozen, existing)
    if critic_result.get("selected_candidate_id") != selected_id:
        raise HficSessionError("CRITIC_SELECTED_MISMATCH")
    if critic_result.get("session_id") != frozen.get("session_id"):
        raise HficSessionError("CRITIC_SESSION_MISMATCH")
    observed_packet = critic_result.get("critic_input_packet_sha256")
    if (
        not isinstance(expected_packet, str)
        or not isinstance(observed_packet, str)
        or expected_packet != observed_packet
    ):
        raise HficSessionError("CRITIC_PACKET_HASH_MISMATCH")
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
        supersedes_record_id: str | None = None,
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
            supersedes_record_id=supersedes_record_id,
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
    if session_receipt.get("runner_up_failover_used"):
        ru_result = str(session_receipt.get("runner_up_critic_result_sha256") or "")
        cycle_ru = str(cycle.get("runner_up_critic_result_sha256") or "")
        ru_input = str(session_receipt.get("runner_up_critic_input_packet_sha256") or "")
        cycle_ru_input = str(cycle.get("runner_up_critic_input_packet_sha256") or "")
        if len(ru_result) != 64 or ru_result != cycle_ru:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
        if len(ru_input) != 64 or ru_input != cycle_ru_input:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
        if ru_result == receipt_result:
            raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")


def _verify_failover_receipt_identity(receipt: Mapping[str, Any]) -> None:
    if not receipt.get("runner_up_failover_used"):
        return
    if receipt.get("selected_candidate_id") != receipt.get("primary_selected_candidate_id"):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if receipt.get("critic_terminal") != receipt.get("primary_critic_terminal"):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if receipt.get("critic_result_sha256") != receipt.get("primary_critic_result_sha256"):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if receipt.get("critic_input_packet_sha256") != receipt.get(
        "primary_critic_input_packet_sha256"
    ):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    ru_result = receipt.get("runner_up_critic_result_sha256")
    if not isinstance(ru_result, str) or len(ru_result) != 64:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if ru_result == receipt.get("critic_result_sha256"):
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


def _verify_runner_up_result_bind(
    result: Mapping[str, Any],
    *,
    session_id: str,
    runner_up_id: str,
    packet_sha: str,
    definition_sha: str,
) -> None:
    if str(result.get("session_id") or "") != session_id:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if str(result.get("selected_candidate_id") or "") != runner_up_id:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")
    if str(result.get("critic_input_packet_sha256") or "") != packet_sha:
        raise HficSessionError("CRITIC_INPUT_HASH_MISMATCH")
    if definition_sha and str(result.get("selected_definition_sha256") or "") != definition_sha:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


def candidate_reference_gaps(
    *,
    claimed_ids: Sequence[Any],
    durable_ids: Collection[str],
    selected_candidate_id: Any = None,
    runner_up_candidate_id: Any = None,
) -> list[str]:
    """Candidate references this session claims that do not durably resolve.

    Answers "are the candidate artifacts this exact session claims to own
    resolvable and internally consistent?", never "did it produce at least N
    candidates?". Portfolio size is not a reference property: a legitimate
    zero- or one-candidate session has no gaps. An absent selection or
    runner-up is valid; a named one that does not resolve is a gap.
    """

    known = {str(item) for item in durable_ids if str(item)}
    gaps: list[str] = []
    for item in claimed_ids or ():
        candidate_id = str(item or "")
        if candidate_id and candidate_id not in known:
            gaps.append(f"CANDIDATE:{candidate_id}")
    for role, value in (
        ("SELECTED", selected_candidate_id),
        ("RUNNER_UP", runner_up_candidate_id),
    ):
        candidate_id = str(value or "")
        if candidate_id and candidate_id not in known:
            gaps.append(f"{role}:{candidate_id}")
    return gaps


def _bundle_candidate_reference_gaps(bundle: Mapping[str, Any]) -> list[str]:
    """Gaps in what this bundle claims, with no tolerance for a lost card.

    This is not a completeness proof of the portfolio. ``candidate_ids``
    falls back to the durable ids when a cycle never recorded its own claim,
    so for those cycles the listed-id check is vacuous and only a named
    selection or runner-up still fails closed. Closing that needs claim-list
    provenance the current schema does not carry.
    """

    durable = [
        str(card.get("hypothesis_version_id") or "")
        for card in (bundle.get("candidates") or [])
        if isinstance(card, Mapping)
    ]
    return candidate_reference_gaps(
        claimed_ids=list(bundle.get("candidate_ids") or []),
        durable_ids=durable,
        selected_candidate_id=bundle.get("selected_candidate_id"),
        runner_up_candidate_id=bundle.get("runner_up_candidate_id"),
    )


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
    # Loading a bundle stays possible for a store that never persisted this
    # session's cards, which is how legacy and control-surface sessions were
    # written; refusing to load them would hide a readable lifecycle. Once
    # the store carries any card, an incomplete claim fails closed, so the
    # count of what was found never excuses a missing reference. Whether
    # those artifacts are good enough to prove is the proof gate's question,
    # and `candidates_retrievable` answers it without this tolerance.
    if known_hypothesis and candidate_reference_gaps(
        claimed_ids=candidate_ids,
        durable_ids=known_hypothesis,
        selected_candidate_id=bundle.get("selected_candidate_id"),
        runner_up_candidate_id=bundle.get("runner_up_candidate_id"),
    ):
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
        FORGE_CONTEXT_ARTIFACT_DIR,
        verify_forge_context_packet,
    )

    data_root = Path(store._root)
    try:
        verify_forge_context_packet(data_root, digest)
    except HficPreflightError as exc:
        safe_digest = digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None
        raise HficSessionError(str(exc), detail={
            "stage": "SAVED_CONTEXT_DEPENDENCY",
            "required_context_sha256": safe_digest,
            "relative_locator": f"{FORGE_CONTEXT_ARTIFACT_DIR}/{safe_digest}.json" if safe_digest else None,
            "next_action": "RESTORE_EXACT_SAVED_CONTEXT_DEPENDENCY",
        }) from exc


def _verify_required_context_dependency(store: Any, binding: Mapping[str, Any]) -> None:
    digest = binding.get("forge_context_packet_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise HficSessionError("FORGE_CONTEXT_REQUIRED")
    inline = binding.get("forge_context_packet")
    if inline is not None and (not isinstance(inline, Mapping) or canonical_sha256(inline) != digest):
        raise HficSessionError("FORGE_CONTEXT_HASH_MISMATCH")
    _verify_forge_context_artifact(store, digest)


def _validate_fresh_draft_scopes(draft: Mapping[str, Any], *, store: Any,
                               identities: Sequence[Any]) -> None:
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        GroundedDiscoveryError, stored_look_scope, validate_fresh_card_scope,
    )

    evidence = draft.get("grounded_evidence")
    selected_ref = draft.get("selected_candidate_ref")
    selected = _resolve_ref(selected_ref, identities) if selected_ref else -1
    look = stored_look_scope(store, evidence) if store is not None and isinstance(evidence, Mapping) else None
    for index, card in enumerate(_project_draft_cards(draft)):
        if not isinstance(card, Mapping):
            raise HficSessionError("HFIC_PROTOCOL_INVALID")
        try:
            validate_fresh_card_scope(card, look_scope=look,
                                      require_look_axes=index == selected and bool(look))
        except GroundedDiscoveryError as exc:
            raise HficSessionError(exc.code, detail={"candidate_ordinal": index + 1, **exc.detail}) from exc


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
    from solana_alpha_lab.factory.hfic_control_integrity import (
        DIRECT_CLASSIFIER_HFIC_TERMINAL,
    )
    from solana_alpha_lab.factory.observation_fast_lane_terminals import (
        hfic_terminal_for_classifier,
    )

    observation_mapped = hfic_terminal_for_classifier(outcome)
    if observation_mapped is not None:
        return observation_mapped
    mapped = DIRECT_CLASSIFIER_HFIC_TERMINAL.get(outcome)
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


def _caller_hypothesis_definition_sha256(
    critic_result: Mapping[str, Any],
    submission: Mapping[str, Any],
) -> str | None:
    """Hash the caller actually passed. Never the frozen candidate hash."""

    raw: list[object] = []
    if "experiment_spec" in submission:
        raw.append(submission.get("hypothesis_definition_sha256"))
    raw.append(critic_result.get("hypothesis_definition_sha256"))
    present = [item for item in raw if item is not None]
    if not present:
        return None
    if any(not isinstance(item, str) or not item for item in present):
        return None
    unique = list(dict.fromkeys(str(item) for item in present))
    if len(unique) != 1:
        return None
    return unique[0]


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
        submission = {"experiment_spec": dict(submission)}
    if not isinstance(submission, Mapping) or "experiment_spec" not in submission:
        raise HficSessionError("EXPERIMENT_SPEC_REQUIRED")
    caller_hash = _caller_hypothesis_definition_sha256(critic_result, submission)
    spec = submission["experiment_spec"]
    if not isinstance(spec, Mapping):
        raise HficSessionError("EXPERIMENT_SPEC_REQUIRED")
    try:
        validated = validate_experiment_document(dict(spec), root=Path(repo_root))
    except ExperimentSpecError as exc:
        raise HficSessionError("EXPERIMENT_SPEC_INVALID") from exc
    spec_sha = experiment_spec_sha256(validated)
    packet_in = frozen.get("critic_input_packet")
    if (
        isinstance(packet_in, Mapping)
        and packet_in.get("packet_version") == CRITIC_PACKET_VERSION_CURRENT
    ):
        from solana_alpha_lab.factory.hfic_control_integrity import (
            assert_experiment_spec_grounding,
        )

        selected = packet_in.get("selected_candidate")
        if not isinstance(selected, Mapping):
            raise HficSessionError("EXPERIMENT_SPEC_GROUNDING_MISMATCH")
        try:
            assert_experiment_spec_grounding(validated, selected)
        except ValueError as exc:
            raise HficSessionError(str(exc)) from exc
    else:
        selected = None
    expected_hash = frozen.get("selected_definition_sha256")
    if not isinstance(caller_hash, str) or caller_hash != expected_hash:
        raise HficSessionError("HYPOTHESIS_DEFINITION_UNBOUND")
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
    packet["hypothesis_definition_sha256"] = caller_hash
    from solana_alpha_lab.factory.scientific_eligibility_projection import (
        ScientificEligibilityError,
        try_project_scientific_eligibility_from_data_root,
    )

    request = validated.get("observation_request")
    try:
        projected = try_project_scientific_eligibility_from_data_root(
            Path(data_root),
            repo_root=Path(repo_root),
            spec=validated,
            schedule=request if isinstance(request, Mapping) else None,
        )
    except ScientificEligibilityError:
        projected = None
    if projected is not None:
        packet["scientific_eligibility_projection"] = projected
    decision = classify_lane(
        packet,
        root=Path(repo_root),
        data_root=Path(data_root),
        as_of=as_of,
    )
    receipt = build_classifier_receipt(
        frozen=frozen,
        decision=decision,
        spec_sha256=spec_sha,
    )
    receipt["hypothesis_version"] = validated.get("hypothesis_version")
    if (
        _runner_up_missing_own_computed_look(frozen)
        and _classifier_to_hfic_terminal(receipt) in _FINAL_PASS_TERMINALS
    ):
        receipt = {
            **receipt,
            "lane": "DENY",
            "lane_classifier_terminal": "DENY_INTEGRITY_MISMATCH",
            "reason_codes": ["GROUNDED_RESULT_UNBOUND"],
            "classifier_route_terminal": str(decision.terminal),
        }
    if selected is not None and _classifier_to_hfic_terminal(receipt) == "PASS_FAST_LANE_READY":
        from solana_alpha_lab.factory.hfic_control_integrity import (
            DENY_HFIC_AVAILABILITY_GATE,
            fast_lane_availability_denial_codes,
        )

        reasons = fast_lane_availability_denial_codes(selected)
        if reasons:
            receipt = {
                **receipt,
                "lane": "DENY",
                "lane_classifier_terminal": DENY_HFIC_AVAILABILITY_GATE,
                "reason_codes": reasons,
                "classifier_route_terminal": str(decision.terminal),
            }
    return receipt


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
        "hypothesis_version",
        "lane",
        "lane_classifier_terminal",
        "classifier_route_terminal",
        "network_free",
    ):
        if observed.get(key) != expected.get(key):
            raise HficSessionError("CLASSIFIER_RECEIPT_INVALID")
    if list(observed.get("reason_codes") or []) != list(expected.get("reason_codes") or []):
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
    cycle_seq = _next_cycle_seq(existing)
    phase_token = "REV" if phase == "REVISION_REQUIRED" else "CLS"
    transaction_id = (
        f"RESEARCH-TXN-HFICINT-{phase_token}-{session_id[-12:]}-{cycle_seq:04d}"
    )
    event = _make_event_factory(
        repo_root,
        git,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
    prompt_version = str(frozen.get("prompt_version") or PROMPT_VERSION)
    intermediate_cycle = {
                "research_cycle_id": f"{session_id}-{phase}-{cycle_seq}",
                "session_id": session_id,
                "phase": phase,
                "hfic_protocol": prompt_version,
                "prompt_version": prompt_version,
                "owner_focus": frozen.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": frozen.get("focus_key_sha256") or "",
                "search_key_sha256": frozen.get("search_key_sha256") or "",
                "memory_eligibility_sha256": frozen.get("memory_eligibility_sha256"),
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
                "forge_context_packet_sha256": frozen.get("forge_context_packet_sha256")
                or (
                    existing.get("forge_context_packet_sha256")
                    if isinstance(existing, Mapping)
                    else None
                ),
                "ladder_representation_id": frozen.get("ladder_representation_id")
                or (
                    existing.get("ladder_representation_id")
                    if isinstance(existing, Mapping)
                    else None
                ),
                "control_session_id": frozen.get("control_session_id")
                or (
                    existing.get("control_session_id")
                    if isinstance(existing, Mapping)
                    else None
                ),
                "hfic_cycle_seq": cycle_seq,
                **_execution_identity_fields(existing, frozen),
            }
    source = existing if existing is not None else frozen
    _attach_runner_up_fields(intermediate_cycle, source)
    _attach_runner_up_fields(intermediate_cycle, frozen)
    _copy_evidence_surface_mode(intermediate_cycle, source)
    _copy_evidence_surface_mode(intermediate_cycle, frozen)
    _stamp_split_identity(intermediate_cycle, source, frozen)
    _stamp_market_evidence_basis(intermediate_cycle, source, frozen)
    repair_disp = None
    if isinstance(existing, Mapping):
        repair_disp = existing.get("repair_continuation_disposition_sha256")
    if not (isinstance(repair_disp, str) and repair_disp) and isinstance(
        frozen, Mapping
    ):
        repair_disp = frozen.get("repair_continuation_disposition_sha256")
    if isinstance(repair_disp, str) and repair_disp:
        intermediate_cycle["repair_continuation_disposition_sha256"] = repair_disp
        intermediate_cycle["parent_cycle_seq"] = int(
            (existing or {}).get("hfic_cycle_seq") or 0
        )
    if isinstance(frozen.get("grounded_candidates"), list):
        intermediate_cycle["grounded_candidates"] = list(frozen["grounded_candidates"])
    if "closed_or_suppressed_collision_count" in frozen:
        intermediate_cycle["closed_or_suppressed_collision_count"] = frozen[
            "closed_or_suppressed_collision_count"
        ]
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-{phase}-{cycle_seq}",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload=intermediate_cycle,
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "CRITIC_RESULT",
                "payload_canonical": critic_bytes.decode("utf-8"),
                "payload_sha256": hashlib.sha256(critic_bytes).hexdigest(),
            },
            transaction_id=transaction_id,
        ),
    ]
    known_input_shas = {
        str((existing or {}).get(key) or "")
        for key in (
            "critic_input_packet_sha256",
            "primary_critic_input_packet_sha256",
            "runner_up_critic_input_packet_sha256",
        )
    }
    packet = frozen.get("critic_input_packet")
    if isinstance(packet, Mapping):
        packet_bytes = _canonical_bytes(packet)
        digest = hashlib.sha256(packet_bytes).hexdigest()
        if digest not in known_input_shas:
            records.append(
                event(
                    record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                    kind=RecordKind.RESEARCH_ARTIFACT,
                    entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                    payload={
                        "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-{digest[:12].upper()}",
                        "session_id": session_id,
                        "hfic_protocol": prompt_version,
                        "artifact_kind": "CRITIC_INPUT_PACKET",
                        "payload_canonical": packet_bytes.decode("utf-8"),
                        "payload_sha256": digest,
                    },
                    transaction_id=transaction_id,
                )
            )
    runner_up_packet = frozen.get("runner_up_critic_input_packet")
    if isinstance(runner_up_packet, Mapping) and not (
        existing and existing.get("runner_up_critic_input_packet")
    ):
        runner_bytes = _canonical_bytes(runner_up_packet)
        runner_digest = hashlib.sha256(runner_bytes).hexdigest()
        records.append(
            event(
                record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                payload={
                    "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "CRITIC_INPUT_PACKET",
                    "payload_canonical": runner_bytes.decode("utf-8"),
                    "payload_sha256": runner_digest,
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
            _draft_schema_path(repo_root, revised_draft),
        )
    _validate_revision_context_lock(existing, revised_draft)
    candidates = _project_draft_cards(revised_draft)
    if not isinstance(candidates, list) or not (
        MIN_CANDIDATES
        <= len(candidates)
        <= _max_candidates_for(store, existing.get("search_key_sha256"))
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
    runner_up_id = None
    runner_up_ref = revised_draft.get("runner_up_candidate_ref")
    if existing.get("runner_up_candidate_id") is not None or runner_up_ref is not None:
        runner_up_index = _resolve_ref(runner_up_ref, draft_identities)
        if runner_up_index < 0:
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
        runner_up_id = draft_identities[runner_up_index].candidate_id
        if runner_up_id != existing.get("runner_up_candidate_id"):
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    rejected_id_existing = existing.get("rejected_alternative_id")
    if not rejected_id_existing and isinstance(packet_in, Mapping):
        rejected_id_existing = packet_in.get("strongest_rejected_alternative")
    if rejected_id_existing == "NONE" and len(existing.get("candidate_ids") or []) == 1:
        rejected_id_existing = None
    rejected_id = None
    rejected_ref = revised_draft.get("strongest_rejected_alternative")
    if rejected_id_existing is not None or rejected_ref is not None:
        rejected_index = _resolve_ref(rejected_ref, draft_identities)
        if rejected_index < 0:
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
        rejected_id = draft_identities[rejected_index].candidate_id
        if rejected_id != rejected_id_existing:
            raise HficSessionError("REVISION_PORTFOLIO_CHANGED")
    original_selected: dict[str, Any] = {}
    if isinstance(packet_in, Mapping):
        selected_card = packet_in.get("selected_candidate")
        if isinstance(selected_card, Mapping):
            original_selected = dict(selected_card)
    selected_card = candidates[selected_index]
    rebuilt_selected = _selected_candidate_block(selected_identity, selected_card)
    rebuilt_selected.pop("_required_capability_ids", None)
    if (
        isinstance(packet_in, Mapping)
        and packet_in.get("packet_version") == CRITIC_PACKET_VERSION_CURRENT
    ):
        for key in (
            "estimand",
            "state_transition",
            "required_feature_ids",
            "required_capability_ids",
            "unresolved_requirements",
            "grounding",
        ):
            if key in original_selected:
                rebuilt_selected[key] = copy.deepcopy(original_selected[key])
        for key in ("research_scope_rule_sha256", "research_scope_statement"):
            if key in original_selected or selected_card.get(key) is not None:
                rebuilt_selected[key] = str(selected_card.get(key) or "")
                if original_selected.get(key) != rebuilt_selected[key]:
                    # Changing the list scope is a scientific adaptation, never a wording revision.
                    raise HficSessionError("REVISION_MECHANISM_CHANGED")
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
    from solana_alpha_lab.factory.hfic_grounded_discovery import card_claim_scope

    locked_scope = card_claim_scope(original_selected)
    source_evidence = packet_in.get("grounded_evidence")
    if isinstance(source_evidence, Mapping) and source_evidence.get("look_confirms_selected") is True:
        # Saved confirming scope supplies locks for older readable projections;
        # it never supplies a missing fresh declaration or a new result.
        locked_scope.update(card_claim_scope(source_evidence.get("candidate_scope")))
    if card_claim_scope(selected_card) != locked_scope or (
        str(selected_card.get("claim_form") or "CAUSAL") != str(original_selected.get("claim_form") or "CAUSAL")
    ):
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
    packet["strongest_rejected_alternative"] = "NONE" if rejected_id is None else rejected_id
    source_evidence = packet.get("grounded_evidence")
    if isinstance(source_evidence, Mapping) and source_evidence.get("result_refs"):
        rebound = _bind_selected_look(
            source_evidence,
            selected_card if isinstance(selected_card, Mapping) else {},
            store=store,
            strict=False,
        )
        if rebound.get("look_confirms_selected") is not False:
            from solana_alpha_lab.factory.hfic_grounded_discovery import (
                GroundedDiscoveryError,
                bind_prior_scope_evidence,
            )

            try:
                rebound = bind_prior_scope_evidence(
                    rebound,
                    canonical_priors=list(
                        (packet.get("prior_memory") or {}).get("capsules") or []
                    ),
                )
            except GroundedDiscoveryError as exc:
                raise HficSessionError(exc.code) from exc
        packet["grounded_evidence"] = rebound
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
    prompt_version = str(
        existing.get("prompt_version") or frozen.get("prompt_version") or PROMPT_VERSION
    )
    revision_cycle = {
                "research_cycle_id": f"{session_id}-REVISED",
                "session_id": session_id,
                "phase": "REVISED_AWAITING_CRITIC",
                "hfic_protocol": prompt_version,
                "prompt_version": prompt_version,
                "owner_focus": existing.get("owner_focus") or "AUTO",
                "evidence_epoch_sha256": existing.get("evidence_epoch_sha256") or "",
                "focus_key_sha256": existing.get("focus_key_sha256") or "",
                "search_key_sha256": existing.get("search_key_sha256") or "",
                "memory_eligibility_sha256": existing.get(
                    "memory_eligibility_sha256"
                )
                or frozen.get("memory_eligibility_sha256"),
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
                "forge_context_packet_sha256": existing.get("forge_context_packet_sha256")
                or frozen.get("forge_context_packet_sha256"),
                "hfic_cycle_seq": _next_cycle_seq(existing),
                **_execution_identity_fields(existing, frozen),
            }
    _attach_runner_up_fields(revision_cycle, existing)
    _attach_runner_up_fields(revision_cycle, frozen)
    _copy_evidence_surface_mode(revision_cycle, existing)
    _copy_evidence_surface_mode(revision_cycle, frozen)
    _stamp_split_identity(revision_cycle, existing, frozen)
    _stamp_market_evidence_basis(revision_cycle, existing, frozen)
    if prompt_version == PROMPT_VERSION and repo_root is not None:
        grounded_candidates = _ground_v12_candidates(
            candidates,
            draft_identities,
            repo_root=repo_root,
            preflight_receipt={
                "forge_context_packet_sha256": revision_cycle.get(
                    "forge_context_packet_sha256"
                )
                or ("0" * 64),
            },
        )
        revision_cycle["grounded_candidates"] = grounded_candidates
    elif isinstance(existing.get("grounded_candidates"), list):
        revision_cycle["grounded_candidates"] = list(existing["grounded_candidates"])
    if "closed_or_suppressed_collision_count" in existing:
        revision_cycle["closed_or_suppressed_collision_count"] = existing[
            "closed_or_suppressed_collision_count"
        ]
    elif "closed_or_suppressed_collision_count" in frozen:
        revision_cycle["closed_or_suppressed_collision_count"] = frozen[
            "closed_or_suppressed_collision_count"
        ]
    records = [
        event(
            record_id=f"HFIC-CYCLE-{session_id}-REVISED",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload=revision_cycle,
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-REV1",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
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
                record_id=_session_hypothesis_record_id(selected_identity.candidate_id, session_id),
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=selected_identity.candidate_id,
                hypothesis_version_id=selected_identity.candidate_id,
                supersedes_record_id=_session_hypothesis_supersedes(store, selected_identity.candidate_id, selected_identity.full_sha256),
                payload={
                    "hypothesis_version_id": selected_identity.candidate_id,
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
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
                    **_hypothesis_scope_fields(
                        frozen, selected_identity.definition, selected_card
                    ),
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


def _recipe_scope_rule(experiment_spec_packet: Mapping[str, Any]) -> str | None:
    nested = experiment_spec_packet.get("experiment_spec")
    if isinstance(nested, Mapping):
        experiment_spec_packet = nested
    parameters = experiment_spec_packet.get("parameters")
    recipe = parameters.get("temporal_recipe") if isinstance(parameters, Mapping) else None
    if not isinstance(recipe, Mapping):
        recipe = experiment_spec_packet.get("experiment_recipe")
    rule = recipe.get("research_scope_rule_sha256") if isinstance(recipe, Mapping) else None
    return str(rule) if rule else None


def _require_recipe_preserves_research_scope(
    view: Mapping[str, Any], experiment_spec_packet: Mapping[str, Any]
) -> None:
    """Classification never turns a list-scoped hypothesis into a pooled (or other) experiment."""

    packet = view.get("critic_input_packet")
    selected = packet.get("selected_candidate") if isinstance(packet, Mapping) else None
    frozen_rule = selected.get("research_scope_rule_sha256") if isinstance(selected, Mapping) else None
    if _recipe_scope_rule(experiment_spec_packet) != (str(frozen_rule) if frozen_rule else None):
        raise HficSessionError("RESEARCH_SCOPE_RECIPE_MISMATCH")


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
    view = _classifier_frozen_view(existing, critic_result)
    _require_recipe_preserves_research_scope(view, experiment_spec_packet)
    receipt = validate_live_classifier_receipt(
        critic_result,
        view,
        repo_root=repo_root,
        data_root=data_root,
    )
    terminal = _classifier_to_hfic_terminal(receipt)
    critic_result["classifier_receipt"] = receipt
    critic_result["critic_terminal"] = terminal
    critic_result["next"] = "PAUSE" if terminal in _PAUSE_TERMINALS else "STOP"
    return finalize_session(
        existing,
        critic_result,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
        clock=clock,
    )


def persist_primary_kill_awaiting_runner_up(
    store: Any,
    frozen: Mapping[str, Any],
    critic_result: Mapping[str, Any],
    *,
    repo_root: Any,
    clock: Clock | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind

    session_id = str(frozen["session_id"])
    existing = load_session_bundle(store, session_id)
    if existing is not None and existing.get("session_state") == RUNNER_UP_AWAITING_CRITIC:
        return existing
    if existing is not None:
        merged = dict(frozen)
        for key in (
            "runner_up_candidate_id",
            "runner_up_critic_input_packet",
            "runner_up_critic_input_packet_sha256",
            "runner_up_definition_sha256",
            "runner_up_display_ordinal",
            "primary_critic_input_packet_sha256",
            "git_composite_sha256",
            "selected_candidate_id",
            "selected_definition_sha256",
            "candidate_ids",
            "prompt_version",
            "evidence_epoch_sha256",
            "focus_key_sha256",
            "search_key_sha256",
            "research_memory_as_of",
            "forge_context_packet_sha256",
            "owner_focus",
            "grounded_candidates",
            "closed_or_suppressed_collision_count",
            "revision_count",
            "rejected_alternative_id",
            "selected_display_ordinal",
        ):
            stored = existing.get(key)
            if stored is not None and stored != "":
                merged[key] = stored
        frozen = merged
    git = repository_git_snapshot(Path(repo_root))
    preflight_composite = frozen.get("git_composite_sha256")
    if not isinstance(preflight_composite, str) or len(preflight_composite) != 64:
        raise HficSessionError("GIT_COMPOSITE_CHANGED")
    if preflight_composite != git.composite_sha256:
        raise HficSessionError("GIT_COMPOSITE_CHANGED")
    stage_time = _stage_datetime(clock)
    transaction_id = f"RESEARCH-TXN-HFICRU-{session_id[-12:]}"
    event = _make_event_factory(
        repo_root,
        git,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
    prompt_version = str(frozen.get("prompt_version") or PROMPT_VERSION)
    primary_id = str(frozen["selected_candidate_id"])
    terminal = str(critic_result.get("critic_terminal") or "")
    primary_packet_sha = str(
        critic_result.get("critic_input_packet_sha256")
        or frozen.get("critic_input_packet_sha256")
        or ""
    )
    runner_up_packet_sha = str(frozen.get("runner_up_critic_input_packet_sha256") or "")
    pending_cycle = {
        "research_cycle_id": f"{session_id}-RUNNER-UP-AWAITING",
        "session_id": session_id,
        "phase": RUNNER_UP_AWAITING_CRITIC,
        "hfic_protocol": prompt_version,
        "prompt_version": prompt_version,
        "owner_focus": frozen.get("owner_focus") or "AUTO",
        "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
        "focus_key_sha256": frozen.get("focus_key_sha256") or "",
        "search_key_sha256": frozen.get("search_key_sha256") or "",
        "memory_eligibility_sha256": frozen.get("memory_eligibility_sha256")
        or (existing.get("memory_eligibility_sha256") if existing else None),
        "selected_candidate_id": primary_id,
        "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
        "rejected_alternative_id": frozen.get("rejected_alternative_id"),
        "candidate_ids": list(frozen.get("candidate_ids") or []),
        "critic_terminal": terminal,
        "next": "RESUME_CRITIC",
        "critic_input_packet_sha256": runner_up_packet_sha,
        "primary_critic_input_packet_sha256": primary_packet_sha,
        "primary_critic_result_sha256": critic_result_sha256,
        "primary_critic_terminal": terminal,
        "runner_up_critic_input_packet_sha256": runner_up_packet_sha,
        "runner_up_definition_sha256": frozen.get("runner_up_definition_sha256"),
        "runner_up_display_ordinal": frozen.get("runner_up_display_ordinal"),
        "selected_definition_sha256": frozen.get("selected_definition_sha256"),
        "selected_display_ordinal": frozen.get("selected_display_ordinal"),
        "git_composite_sha256": frozen.get("git_composite_sha256"),
        "research_memory_as_of": frozen.get("research_memory_as_of"),
        "revision_count": int(frozen.get("revision_count") or 0),
        "forge_context_packet_sha256": frozen.get("forge_context_packet_sha256"),
        "runner_up_failover_used": True,
        "critic_claimed_terminal": frozen.get("critic_claimed_terminal"),
        "critic_screen_count": 1,
        "hfic_cycle_seq": _next_cycle_seq(existing),
        **_execution_identity_fields(existing, frozen),
    }
    _copy_evidence_surface_mode(pending_cycle, existing)
    _copy_evidence_surface_mode(pending_cycle, frozen)
    _stamp_split_identity(pending_cycle, existing, frozen)
    _stamp_market_evidence_basis(pending_cycle, existing, frozen)
    repair_disp = None
    if isinstance(existing, Mapping):
        repair_disp = existing.get("repair_continuation_disposition_sha256")
    if not (isinstance(repair_disp, str) and repair_disp) and isinstance(
        frozen, Mapping
    ):
        repair_disp = frozen.get("repair_continuation_disposition_sha256")
    if isinstance(repair_disp, str) and repair_disp:
        pending_cycle["repair_continuation_disposition_sha256"] = repair_disp
        pending_cycle["parent_cycle_seq"] = int(
            (existing or {}).get("hfic_cycle_seq") or 0
        )
    if isinstance(frozen.get("grounded_candidates"), list):
        pending_cycle["grounded_candidates"] = list(frozen["grounded_candidates"])
    if "closed_or_suppressed_collision_count" in frozen:
        pending_cycle["closed_or_suppressed_collision_count"] = frozen[
            "closed_or_suppressed_collision_count"
        ]
    runner_up_cycle_id = f"HFIC-CYCLE-{session_id}-RUNNER-UP-AWAITING"
    if isinstance(repair_disp, str) and repair_disp:
        runner_up_cycle_id = (
            f"HFIC-CYCLE-{session_id}-REPAIR-RU-{repair_disp[:12].upper()}"
        )
    records = [
        event(
            record_id=runner_up_cycle_id,
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            payload=pending_cycle,
            transaction_id=transaction_id,
        ),
        event(
            record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "CRITIC_RESULT",
                "payload_canonical": critic_bytes.decode("utf-8"),
                "payload_sha256": critic_result_sha256,
            },
            transaction_id=transaction_id,
        ),
        event(
            record_id=_session_decision_record_id(primary_id, session_id),
            kind=RecordKind.DECISION_EVENT,
            entity_id=_session_decision_record_id(primary_id, session_id),
            hypothesis_version_id=primary_id,
            payload={
                "decision_event_id": _session_decision_record_id(primary_id, session_id),
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "decision_kind": "REJECT",
                "reason_code": terminal,
                "hypothesis_version_id": primary_id,
            },
            transaction_id=transaction_id,
        ),
    ]
    runner_up_packet = frozen.get("runner_up_critic_input_packet")
    existing_runner = existing.get("runner_up_critic_input_packet") if existing else None
    if isinstance(runner_up_packet, Mapping) and not isinstance(existing_runner, Mapping):
        runner_bytes = _canonical_bytes(runner_up_packet)
        runner_digest = hashlib.sha256(runner_bytes).hexdigest()
        records.append(
            event(
                record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                payload={
                    "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}-RUNNER-UP-{runner_digest[:12].upper()}",
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "CRITIC_INPUT_PACKET",
                    "payload_canonical": runner_bytes.decode("utf-8"),
                    "payload_sha256": runner_digest,
                },
                transaction_id=transaction_id,
            )
        )
        primary_packet = frozen.get("critic_input_packet")
        if isinstance(primary_packet, Mapping) and existing is None:
            primary_bytes = _canonical_bytes(primary_packet)
            records.append(
                event(
                    record_id=f"HFIC-ART-CRITIC-INPUT-{session_id}",
                    kind=RecordKind.RESEARCH_ARTIFACT,
                    entity_id=f"HFIC-ART-CRITIC-INPUT-{session_id}",
                    payload={
                        "research_artifact_id": f"HFIC-ART-CRITIC-INPUT-{session_id}",
                        "session_id": session_id,
                        "hfic_protocol": prompt_version,
                        "artifact_kind": "CRITIC_INPUT_PACKET",
                        "payload_canonical": primary_bytes.decode("utf-8"),
                        "payload_sha256": hashlib.sha256(primary_bytes).hexdigest(),
                    },
                    transaction_id=transaction_id,
                )
            )
    store.append(records, transaction_id=transaction_id)
    store.rebuild_projection()
    loaded = load_session_bundle(store, session_id)
    if loaded is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    return loaded


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

    existing = load_session_bundle(store, str(frozen["session_id"]))
    if existing is not None and existing.get("session_state") == "SYNTHESIS_COMPLETE":
        retry_payload = dict(critic_result)
        if (
            existing.get("runner_up_failover_used")
            and str(retry_payload.get("critic_terminal") or "") == "REVISE_ONCE"
        ):
            retry_payload["next"] = "STOP"
        retry_hash = hashlib.sha256(_canonical_bytes(retry_payload)).hexdigest()
        if existing.get("runner_up_failover_used"):
            completing = str(existing.get("runner_up_critic_result_sha256") or "")
            if completing and retry_hash == completing:
                return existing
            raise HficSessionError("SESSION_CONFLICT")
        existing_hash = existing.get("critic_result_sha256")
        if existing_hash not in {None, retry_hash}:
            raise HficSessionError("SESSION_CONFLICT")
        return existing
    _require_fresh_v12_runner_up_declaration(existing, frozen)
    selected_id = _require_critic_identity(frozen, critic_result, existing=existing)
    if repo_root is not None:
        _validate_json_schema(
            critic_result,
            Path(repo_root) / "catalog/schemas/hypothesis_critic_result_v1.schema.json",
        )
    if existing is not None and existing.get("session_state") == RUNNER_UP_AWAITING_CRITIC:
        frozen = {**dict(frozen), **{
            key: existing[key]
            for key in (
                "runner_up_candidate_id",
                "runner_up_critic_input_packet",
                "runner_up_critic_input_packet_sha256",
                "runner_up_definition_sha256",
                "runner_up_display_ordinal",
                "primary_critic_input_packet_sha256",
                "primary_critic_result_sha256",
                "primary_critic_terminal",
                "selected_candidate_id",
                "selected_definition_sha256",
                "critic_input_packet",
                "critic_input_packet_sha256",
                "candidate_ids",
                "session_id",
                "prompt_version",
                "evidence_epoch_sha256",
                "focus_key_sha256",
                "search_key_sha256",
                "git_composite_sha256",
                "research_memory_as_of",
                "forge_context_packet_sha256",
                "owner_focus",
                "session_started_at",
                "grounded_candidates",
                "closed_or_suppressed_collision_count",
                "revision_count",
            )
            if key in existing and existing.get(key) is not None
        }}
    _require_declared_runner_up_packet(existing, frozen)
    observed_terminal = str(critic_result.get("critic_terminal") or "")
    screening_is_runner_up = selected_id == str(frozen.get("runner_up_candidate_id") or "")
    runner_up_revision_pause = (
        observed_terminal == "REVISE_ONCE" and screening_is_runner_up
    )
    if runner_up_revision_pause:
        critic_result = dict(critic_result)
        critic_result["next"] = "STOP"
    terminal = (
        RUNNER_UP_REVISION_REQUIRED if runner_up_revision_pause else observed_terminal
    )
    if observed_terminal == "REVISE_ONCE" and not screening_is_runner_up:
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
        if _foreign_look_blocks_scientific_terminal(frozen, critic_result):
            terminal = "KILL_UNBOUND_EVIDENCE"
            observed_terminal = terminal
            critic_result = dict(critic_result)
            critic_result["critic_terminal"] = terminal
            critic_result["next"] = "STOP"
        else:
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
    claimed_terminal = None
    classifier_view = _classifier_frozen_view(frozen, critic_result)
    if terminal in _FINAL_PASS_TERMINALS:
        root_for_data = data_root if data_root is not None else getattr(store, "_root")
        classifier_receipt = validate_live_classifier_receipt(
            critic_result,
            classifier_view,
            repo_root=repo_root,
            data_root=root_for_data,
        )
        critic_result = dict(critic_result)
        critic_result["classifier_receipt"] = classifier_receipt
        mapped = _classifier_to_hfic_terminal(classifier_receipt)
        if terminal != mapped:
            from solana_alpha_lab.factory.hfic_control_integrity import (
                DENY_HFIC_AVAILABILITY_GATE,
            )

            if (
                mapped == "KILL_UNBOUND_EVIDENCE"
                and classifier_receipt.get("lane_classifier_terminal")
                == DENY_HFIC_AVAILABILITY_GATE
            ):
                claimed_terminal = terminal
                terminal = mapped
                critic_result["critic_terminal"] = mapped
                critic_result["next"] = "STOP"
            else:
                raise HficSessionError("CLASSIFIER_TERMINAL_MISMATCH")
    if _foreign_look_blocks_scientific_terminal(frozen, critic_result) and (
        terminal in _FINAL_PASS_TERMINALS
        or (terminal in _KILL_TERMINALS and terminal != "KILL_UNBOUND_EVIDENCE")
    ):
        terminal = "KILL_UNBOUND_EVIDENCE"
        observed_terminal = terminal
        critic_result = dict(critic_result)
        critic_result["critic_terminal"] = terminal
        critic_result["next"] = "STOP"
    if _runner_up_failover_eligible(frozen, existing, terminal):
        if claimed_terminal is not None:
            frozen = {**dict(frozen), "critic_claimed_terminal": claimed_terminal}
        return persist_primary_kill_awaiting_runner_up(
            store,
            frozen,
            critic_result,
            repo_root=repo_root,
            clock=clock,
        )
    if terminal in _FINAL_PASS_TERMINALS:
        pass
    else:
        observed = critic_result.get("classifier_receipt")
        if isinstance(observed, Mapping) and observed.get("schema") == _CLASSIFIER_RECEIPT_SCHEMA:
            classifier_receipt = dict(observed)
    if terminal == RUNNER_UP_REVISION_REQUIRED:
        decision_kind, reason = "PAUSE", RUNNER_UP_REVISION_REQUIRED
    else:
        decision_kind, reason = map_critic_terminal_to_decision(terminal)
    git_before = repository_git_snapshot(Path(repo_root))
    session_id = str(frozen["session_id"])
    stage_time = _stage_datetime(clock)
    created_at = render_canonical_utc(stage_time)
    repair_disp_for_txn = None
    if isinstance(existing, Mapping):
        repair_disp_for_txn = existing.get("repair_continuation_disposition_sha256")
    transaction_id = f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}"
    if isinstance(repair_disp_for_txn, str) and repair_disp_for_txn:
        transaction_id = (
            f"RESEARCH-TXN-HFICFIN-{session_id[-16:]}-REPAIR-"
            f"{repair_disp_for_txn[:12].upper()}"
        )
    event = _make_event_factory(
        repo_root,
        git_before,
        session_id,
        "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        stage_time,
    )
    critic_bytes = _canonical_bytes(critic_result)
    critic_result_sha256 = hashlib.sha256(critic_bytes).hexdigest()
    prompt_version = str(frozen.get("prompt_version") or PROMPT_VERSION)
    decision_ids: list[str] = []
    records = [
        event(
            record_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id=f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
            payload={
                "research_artifact_id": f"HFIC-ART-CRITIC-RESULT-{session_id}-{hashlib.sha256(critic_bytes).hexdigest()[:12].upper()}",
                "session_id": session_id,
                "hfic_protocol": prompt_version,
                "artifact_kind": "CRITIC_RESULT",
                "payload_canonical": critic_bytes.decode("utf-8"),
                "payload_sha256": critic_result_sha256,
            },
            transaction_id=transaction_id,
        )
    ]
    packets_to_store = []
    primary_packet = frozen.get("critic_input_packet") or frozen.get(
        "primary_critic_input_packet"
    )
    existing_primary = existing.get("critic_input_packet") if existing else None
    existing_primary_alt = (
        existing.get("primary_critic_input_packet") if existing else None
    )
    if isinstance(primary_packet, Mapping) and not isinstance(
        existing_primary, Mapping
    ) and not isinstance(existing_primary_alt, Mapping):
        packets_to_store.append(primary_packet)
    runner_packet = frozen.get("runner_up_critic_input_packet")
    existing_runner = existing.get("runner_up_critic_input_packet") if existing else None
    if isinstance(runner_packet, Mapping) and not isinstance(existing_runner, Mapping):
        packets_to_store.append(runner_packet)
    for packet in packets_to_store:
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
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "CRITIC_INPUT_PACKET",
                    "payload_canonical": packet_bytes.decode("utf-8"),
                    "payload_sha256": digest,
                },
                transaction_id=transaction_id,
            )
        )
    for candidate_id in frozen["candidate_ids"]:
        prior = ((existing or {}).get("decisions") or {}).get(str(candidate_id))
        if isinstance(prior, Mapping) and prior.get("decision_kind") == "REJECT":
            decision_ids.append(_persisted_session_rejection_id(store, session_id, str(candidate_id), prior))
            continue
        if candidate_id == selected_id:
            kind, code = decision_kind, reason
        else:
            kind, code = "PAUSE", "NOT_SELECTED_IN_SESSION"
        decision_id = _session_decision_record_id(str(candidate_id), session_id)
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
                    "hfic_protocol": prompt_version,
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
                    "hfic_protocol": prompt_version,
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
                    "hfic_protocol": prompt_version,
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
    forge_selected_id = str(frozen.get("selected_candidate_id") or selected_id)
    failover_used = bool(frozen.get("runner_up_failover_used")) or (
        existing is not None
        and existing.get("session_state") == RUNNER_UP_AWAITING_CRITIC
    )
    c2_packet_sha = frozen.get("runner_up_critic_input_packet_sha256")
    live_packet_sha = critic_result.get("critic_input_packet_sha256") or frozen.get(
        "critic_input_packet_sha256"
    )
    if failover_used:
        live_packet_sha = c2_packet_sha or live_packet_sha
        _verify_runner_up_result_bind(
            critic_result,
            session_id=session_id,
            runner_up_id=str(frozen.get("runner_up_candidate_id") or ""),
            packet_sha=str(c2_packet_sha or ""),
            definition_sha=str(frozen.get("runner_up_definition_sha256") or ""),
        )
    primary_packet_sha = frozen.get("primary_critic_input_packet_sha256") or (
        frozen.get("critic_input_packet_sha256") if not failover_used else None
    )
    if failover_used:
        receipt_packet_sha = primary_packet_sha or live_packet_sha
        receipt_result_sha = frozen.get("primary_critic_result_sha256") or critic_result_sha256
        receipt_terminal = frozen.get("primary_critic_terminal") or observed_terminal
    else:
        receipt_packet_sha = live_packet_sha
        receipt_result_sha = critic_result_sha256
        receipt_terminal = observed_terminal
    survivor_id = None
    if decision_kind == "PAUSE" and reason != RUNNER_UP_REVISION_REQUIRED:
        survivor_id = selected_id
    receipt = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": str(frozen.get("evidence_epoch_sha256") or "0" * 64),
        "focus_key_sha256": str(frozen.get("focus_key_sha256") or "0" * 64),
        "search_key_sha256": str(frozen.get("search_key_sha256") or "0" * 64),
        "prompt_version": prompt_version,
        "live_git_head": git_after.head_sha.lower(),
        "store_inventory_digest": store.diagnostics().committed_inventory_sha256,
        "candidate_ids": list(frozen["candidate_ids"]),
        "selected_candidate_id": forge_selected_id,
        "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
        "critic_input_packet_sha256": receipt_packet_sha,
        "critic_result_sha256": receipt_result_sha,
        "critic_terminal": receipt_terminal,
        "lane_classifier_terminal": (
            None
            if failover_used
            else (
                classifier_receipt.get("lane_classifier_terminal")
                if classifier_receipt is not None
                else None
            )
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
    if prompt_version == PROMPT_VERSION:
        receipt["receipt_schema_version"] = "1.3"
        receipt["primary_selected_candidate_id"] = forge_selected_id
        receipt["primary_critic_terminal"] = (
            frozen.get("primary_critic_terminal") if failover_used else observed_terminal
        )
        receipt["primary_critic_result_sha256"] = (
            frozen.get("primary_critic_result_sha256")
            if failover_used
            else critic_result_sha256
        )
        receipt["primary_critic_input_packet_sha256"] = primary_packet_sha
        receipt["runner_up_failover_used"] = failover_used
        receipt["runner_up_critic_input_packet_sha256"] = frozen.get(
            "runner_up_critic_input_packet_sha256"
        )
        receipt["runner_up_critic_terminal"] = (
            observed_terminal if failover_used else None
        )
        receipt["runner_up_critic_result_sha256"] = (
            critic_result_sha256 if failover_used else None
        )
        receipt["final_survivor_candidate_id"] = survivor_id
        receipt["final_session_terminal"] = terminal
        receipt["critic_screen_count"] = 2 if failover_used else 1
        from solana_alpha_lab.factory.hfic_control_integrity import (
            effective_control_terminal,
        )

        receipt["effective_control_terminal"] = effective_control_terminal(receipt)
    started = frozen.get("session_started_at")
    if isinstance(started, str) and started.strip():
        receipt["session_started_at"] = started
    _copy_evidence_surface_mode(receipt, frozen)
    _stamp_split_identity(receipt, frozen, existing)
    _stamp_execution_identity(receipt, frozen, existing)
    diagnostics = _diagnostics_for_receipt(
        prompt_version=prompt_version,
        grounded_candidates=frozen.get("grounded_candidates")
        if isinstance(frozen.get("grounded_candidates"), list)
        else None,
        session_meta={
            "critic_terminal": receipt_terminal,
            "selected_candidate_id": forge_selected_id,
            "no_worthy_hypothesis": False,
            "lane_classifier_terminal": receipt.get("lane_classifier_terminal"),
            "next_action_type_if_any": None,
            **(
                {
                    "closed_or_suppressed_collision_count": frozen[
                        "closed_or_suppressed_collision_count"
                    ]
                }
                if "closed_or_suppressed_collision_count" in frozen
                else {}
            ),
        },
    )
    if diagnostics is not None:
        if isinstance(classifier_receipt, Mapping):
            route = classifier_receipt.get("classifier_route_terminal")
            if isinstance(route, str) and route:
                diagnostics["classifier_route_terminal"] = route
            reasons = classifier_receipt.get("reason_codes")
            if isinstance(reasons, list) and reasons:
                diagnostics["availability_gate_reason_codes"] = list(reasons)
        if claimed_terminal:
            diagnostics["critic_claimed_terminal"] = claimed_terminal
        receipt["diagnostics"] = diagnostics
    if repo_root is not None:
        _verify_failover_receipt_identity(receipt)
        _validate_json_schema(
            receipt,
            _session_receipt_schema_path(
                repo_root,
                prompt_version,
                wide_candidates=len(receipt.get("candidate_ids") or []) > MAX_CANDIDATES,
            ),
        )
    receipt_bytes = _canonical_bytes(receipt)
    complete_cycle = {
        "research_cycle_id": f"{session_id}-COMPLETE",
        "session_id": session_id,
        "phase": "SYNTHESIS_COMPLETE",
        "hfic_protocol": prompt_version,
        "prompt_version": prompt_version,
        "owner_focus": frozen.get("owner_focus") or "AUTO",
        "evidence_epoch_sha256": frozen.get("evidence_epoch_sha256") or "",
        "focus_key_sha256": frozen.get("focus_key_sha256") or "",
        "search_key_sha256": frozen.get("search_key_sha256") or "",
        "memory_eligibility_sha256": frozen.get("memory_eligibility_sha256"),
        "selected_candidate_id": forge_selected_id,
        "runner_up_candidate_id": frozen.get("runner_up_candidate_id"),
        "candidate_ids": list(frozen.get("candidate_ids") or []),
        "critic_terminal": receipt_terminal,
        "final_session_terminal": terminal,
        "effective_control_terminal": terminal,
        "next": str(critic_result.get("next") or "STOP"),
        "critic_input_packet_sha256": receipt_packet_sha,
        "critic_result_sha256": receipt_result_sha,
        "session_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "selected_definition_sha256": frozen.get("selected_definition_sha256"),
        "git_composite_sha256": git_after.composite_sha256,
        "research_memory_as_of": frozen.get("research_memory_as_of"),
        "revision_count": int(frozen.get("revision_count") or 0),
        "primary_critic_input_packet_sha256": receipt.get(
            "primary_critic_input_packet_sha256"
        )
        or frozen.get("primary_critic_input_packet_sha256"),
        "primary_critic_result_sha256": receipt.get("primary_critic_result_sha256")
        or frozen.get("primary_critic_result_sha256"),
        "primary_critic_terminal": receipt.get("primary_critic_terminal")
        or frozen.get("primary_critic_terminal"),
        "runner_up_critic_input_packet_sha256": frozen.get(
            "runner_up_critic_input_packet_sha256"
        ),
        "runner_up_critic_result_sha256": (
            critic_result_sha256 if failover_used else None
        ),
        "runner_up_critic_terminal": (
            observed_terminal if failover_used else None
        ),
        "runner_up_definition_sha256": frozen.get("runner_up_definition_sha256"),
        "runner_up_failover_used": failover_used,
        "critic_screen_count": 2 if failover_used else 1,
        "hfic_cycle_seq": _next_cycle_seq(existing),
        "forge_context_packet_sha256": frozen.get("forge_context_packet_sha256")
        or (
            existing.get("forge_context_packet_sha256")
            if isinstance(existing, Mapping)
            else None
        ),
        "ladder_representation_id": frozen.get("ladder_representation_id")
        or (
            existing.get("ladder_representation_id")
            if isinstance(existing, Mapping)
            else None
        ),
        "control_session_id": frozen.get("control_session_id")
        or (
            existing.get("control_session_id")
            if isinstance(existing, Mapping)
            else None
        ),
        **_execution_identity_fields(existing, frozen, receipt),
    }
    _copy_evidence_surface_mode(complete_cycle, frozen)
    _stamp_split_identity(complete_cycle, frozen, existing, receipt)
    _stamp_market_evidence_basis(complete_cycle, frozen, existing, receipt)
    repair_disp = None
    if isinstance(existing, Mapping):
        repair_disp = existing.get("repair_continuation_disposition_sha256")
    if not (isinstance(repair_disp, str) and repair_disp) and isinstance(
        frozen, Mapping
    ):
        repair_disp = frozen.get("repair_continuation_disposition_sha256")
    if isinstance(repair_disp, str) and repair_disp:
        complete_cycle["repair_continuation_disposition_sha256"] = repair_disp
        complete_cycle["parent_cycle_seq"] = int(
            (existing or {}).get("hfic_cycle_seq") or 0
        )
    complete_suffix = "COMPLETE"
    receipt_artifact_id = f"HFIC-ART-SESSION-RECEIPT-{session_id}"
    if isinstance(repair_disp, str) and repair_disp:
        complete_suffix = f"REPAIR-COMPLETE-{repair_disp[:12].upper()}"
        receipt_artifact_id = (
            f"HFIC-ART-SESSION-RECEIPT-{session_id}-{complete_suffix}"
        )
    records.extend(
        [
            event(
                record_id=receipt_artifact_id,
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=receipt_artifact_id,
                payload={
                    "research_artifact_id": receipt_artifact_id,
                    "session_id": session_id,
                    "hfic_protocol": prompt_version,
                    "artifact_kind": "SESSION_RECEIPT",
                    "payload_canonical": receipt_bytes.decode("utf-8"),
                    "payload_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                },
                transaction_id=transaction_id,
            ),
            event(
                record_id=f"HFIC-CYCLE-{session_id}-{complete_suffix}",
                kind=RecordKind.RESEARCH_CYCLE,
                entity_id=session_id,
                payload=complete_cycle,
                transaction_id=transaction_id,
            ),
        ]
    )
    store.append(records, transaction_id=transaction_id)
    store.rebuild_projection()
    receipt["store_inventory_digest"] = store.diagnostics().committed_inventory_sha256
    decisions: dict[str, dict[str, str]] = {}
    prior_decisions = dict((existing or {}).get("decisions") or {})
    for candidate_id in frozen["candidate_ids"]:
        prior = prior_decisions.get(str(candidate_id))
        if isinstance(prior, Mapping) and prior.get("decision_kind") == "REJECT":
            decisions[str(candidate_id)] = {
                "decision_kind": "REJECT",
                "reason_code": str(prior.get("reason_code") or ""),
            }
        elif candidate_id == selected_id:
            decisions[str(candidate_id)] = {
                "decision_kind": decision_kind,
                "reason_code": reason,
            }
        else:
            decisions[str(candidate_id)] = {
                "decision_kind": "PAUSE",
                "reason_code": "NOT_SELECTED_IN_SESSION",
            }
    receipt["decisions"] = decisions
    return receipt


def _validate_json_schema(document: Mapping[str, Any], schema_path: Path) -> None:
    if schema_path.name.startswith("hypothesis_forge_draft_"):
        document = {**document, "candidates": _project_draft_cards(document)}
    key = str(schema_path)
    validator = _SCHEMA_VALIDATORS.get(key)
    if validator is None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        _SCHEMA_VALIDATORS[key] = validator
    errors = list(validator.iter_errors(document))
    if errors:
        raise HficSessionError("HFIC_PROTOCOL_INVALID")


_READ_IDENTITY_FIELDS = (
    "evidence_epoch_sha256",
    "memory_eligibility_sha256",
    "market_evidence_epoch_sha256",
    "capability_epoch_sha256",
    "market_evidence_basis",
    "representation_semantic_version",
    "representation_payload_sha256",
    "scientific_slot_sha256",
    "execution_binding_sha256",
    "model_provenance_sha256",
)


def load_session_bundle(
    store: Any,
    session_id: str,
    *,
    read_mode: bool = False,
) -> dict[str, Any] | None:
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
            cycles.append(
                {
                    **payload,
                    "effective_at": getattr(record, "effective_at", ""),
                    "record_id": str(getattr(record, "record_id", "") or ""),
                }
            )
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
        ranked = {
            **payload,
            "phase": effective,
            "effective_at": payload.get("effective_at"),
            "record_id": payload.get("record_id"),
        }
        if cycle is None or _cycle_better(ranked, cycle):
            cycle = ranked
    if cycle is None:
        return None

    _MISSING_IDENTITY = object()
    identity_conflict_fields: list[str] = []

    def _historical_identity_value(key: str) -> Any:
        """Read immutable identity across cycles without reviving explicit UNKNOWN."""

        observed: list[Any] = []
        explicit_unknown = False
        for row in cycles:
            if key not in row:
                continue
            value = row.get(key)
            if value in (None, ""):
                explicit_unknown = True
                continue
            if value not in observed:
                observed.append(value)
        repair_authorized = any(
            isinstance(row.get("repair_continuation_disposition_sha256"), str)
            and row.get("repair_continuation_disposition_sha256")
            for row in cycles
        )
        repair_mutable = {
            "capability_epoch_sha256",
            "execution_binding_sha256",
            "model_provenance_sha256",
            "representation_payload_sha256",
        }
        if len(observed) > 1 or (explicit_unknown and observed):
            if repair_authorized and key in repair_mutable:
                head_value = cycle.get(key) if isinstance(cycle, Mapping) else None
                if head_value not in (None, ""):
                    return head_value
            if read_mode and key in _READ_IDENTITY_FIELDS:
                identity_conflict_fields.append(key)
                return None
            raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
        if explicit_unknown:
            return None
        return observed[0] if observed else _MISSING_IDENTITY

    def _durable_identity_value(key: str) -> Any:
        value = _historical_identity_value(key)
        if value is not _MISSING_IDENTITY:
            return value
        if isinstance(session_receipt, Mapping) and key in session_receipt:
            return session_receipt.get(key)
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
    runner_up_result = None
    runner_up_result_sha = str(cycle.get("runner_up_critic_result_sha256") or "")
    if expected_input_sha:
        _wrapper, critic_input, critic_input_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_INPUT_PACKET",
            expected_sha=expected_input_sha,
        )
    runner_up_packet = None
    runner_up_packet_sha = str(cycle.get("runner_up_critic_input_packet_sha256") or "")
    if runner_up_packet_sha:
        _wrapper, runner_up_packet, runner_up_packet_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_INPUT_PACKET",
            expected_sha=runner_up_packet_sha,
        )
    primary_packet = None
    primary_packet_sha = str(cycle.get("primary_critic_input_packet_sha256") or "")
    if primary_packet_sha and primary_packet_sha == (expected_input_sha or ""):
        primary_packet = critic_input
        primary_packet_sha = critic_input_sha or primary_packet_sha
    elif primary_packet_sha:
        _wrapper, primary_packet, primary_packet_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_INPUT_PACKET",
            expected_sha=primary_packet_sha,
        )
    if expected_result_sha:
        _wrapper, critic_result, critic_result_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_RESULT",
            expected_sha=expected_result_sha,
        )
    if runner_up_result_sha:
        _wrapper, runner_up_result, runner_up_result_sha = _load_artifact_by_sha(
            artifacts,
            artifact_kind="CRITIC_RESULT",
            expected_sha=runner_up_result_sha,
        )
        _verify_runner_up_result_bind(
            runner_up_result,
            session_id=session_id,
            runner_up_id=str(cycle.get("runner_up_candidate_id") or ""),
            packet_sha=str(cycle.get("runner_up_critic_input_packet_sha256") or ""),
            definition_sha=str(cycle.get("runner_up_definition_sha256") or ""),
        )
    primary_result_sha = str(cycle.get("primary_critic_result_sha256") or "")
    primary_critic_result = None
    if len(primary_result_sha) == 64:
        if critic_result is not None and primary_result_sha == (critic_result_sha or ""):
            primary_critic_result = critic_result
        else:
            _wrapper, primary_critic_result, _primary_loaded = _load_artifact_by_sha(
                artifacts,
                artifact_kind="CRITIC_RESULT",
                expected_sha=primary_result_sha,
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
            _verify_failover_receipt_identity(session_receipt)
    if isinstance(session_receipt, Mapping):
        for wrapper, raw in artifacts:
            if wrapper.get("artifact_kind") != "CLASSIFIER_RECEIPT":
                continue
            if isinstance(raw, str):
                classifier_receipt = json.loads(raw)
            break
    else:
        for source in (critic_result, primary_critic_result):
            if not isinstance(source, Mapping):
                continue
            embedded = source.get("classifier_receipt")
            if isinstance(embedded, Mapping):
                classifier_receipt = dict(embedded)
                break
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
        "evidence_epoch_sha256": _durable_identity_value("evidence_epoch_sha256")
        or "",
        "focus_key_sha256": cycle.get("focus_key_sha256") or "",
        "search_key_sha256": cycle.get("search_key_sha256") or "",
        "memory_eligibility_sha256": _durable_identity_value(
            "memory_eligibility_sha256"
        ),
        "market_evidence_epoch_sha256": _durable_identity_value(
            "market_evidence_epoch_sha256"
        ),
        "capability_epoch_sha256": _durable_identity_value(
            "capability_epoch_sha256"
        ),
        "market_evidence_basis": _durable_identity_value("market_evidence_basis"),
        "selected_candidate_id": cycle.get("selected_candidate_id"),
        "runner_up_candidate_id": cycle.get("runner_up_candidate_id"),
        "rejected_alternative_id": cycle.get("rejected_alternative_id"),
        "selected_definition_sha256": cycle.get("selected_definition_sha256"),
        "selected_display_ordinal": cycle.get("selected_display_ordinal"),
        "candidate_ids": cycle.get("candidate_ids") or unique_ids,
        "critic_input_packet": critic_input,
        "critic_input_packet_sha256": expected_input_sha or critic_input_sha,
        "primary_critic_input_packet": primary_packet,
        "primary_critic_input_packet_sha256": primary_packet_sha or cycle.get(
            "primary_critic_input_packet_sha256"
        ),
        "primary_critic_result_sha256": cycle.get("primary_critic_result_sha256"),
        "primary_critic_terminal": cycle.get("primary_critic_terminal"),
        "runner_up_critic_input_packet": runner_up_packet,
        "runner_up_critic_input_packet_sha256": runner_up_packet_sha or cycle.get(
            "runner_up_critic_input_packet_sha256"
        ),
        "runner_up_definition_sha256": cycle.get("runner_up_definition_sha256"),
        "runner_up_display_ordinal": cycle.get("runner_up_display_ordinal"),
        "runner_up_failover_used": bool(cycle.get("runner_up_failover_used")),
        "critic_screen_count": cycle.get("critic_screen_count"),
        "final_session_terminal": cycle.get("final_session_terminal")
        or (session_receipt or {}).get("final_session_terminal"),
        "runner_up_critic_terminal": cycle.get("runner_up_critic_terminal")
        or (session_receipt or {}).get("runner_up_critic_terminal"),
        "hfic_cycle_seq": int(cycle.get("hfic_cycle_seq") or 0),
        "repair_continuation_disposition_sha256": cycle.get(
            "repair_continuation_disposition_sha256"
        ),
        "grounded_result_sha256": cycle.get("grounded_result_sha256"),
        "grounded_result_refs": list(cycle.get("grounded_result_refs") or [])
        if isinstance(cycle.get("grounded_result_refs"), list)
        else None,
        "parent_cycle_seq": cycle.get("parent_cycle_seq"),
        "critic_result": critic_result,
        "critic_result_sha256": critic_result_sha,
        "runner_up_critic_result": runner_up_result,
        "runner_up_critic_result_sha256": runner_up_result_sha or cycle.get(
            "runner_up_critic_result_sha256"
        ),
        "session_receipt": session_receipt,
        "session_receipt_sha256": expected_receipt_sha or None,
        "classifier_receipt": classifier_receipt,
        "critic_claimed_terminal": cycle.get("critic_claimed_terminal")
        or (
            session_receipt.get("diagnostics", {}).get("critic_claimed_terminal")
            if isinstance(session_receipt, Mapping)
            and isinstance(session_receipt.get("diagnostics"), Mapping)
            else None
        ),
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
        "lane_classifier_terminal": (
            None
            if bool(cycle.get("runner_up_failover_used"))
            else (
                (classifier_receipt or {}).get("lane_classifier_terminal")
                or (session_receipt or {}).get("lane_classifier_terminal")
            )
        ),
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
        "ladder_representation_id": cycle.get("ladder_representation_id"),
        "control_session_id": cycle.get("control_session_id"),
        "representation_semantic_version": _durable_identity_value(
            "representation_semantic_version"
        ),
        "representation_payload_sha256": _durable_identity_value(
            "representation_payload_sha256"
        ),
        "scientific_slot_sha256": _durable_identity_value(
            "scientific_slot_sha256"
        ),
        "execution_binding_sha256": _durable_identity_value(
            "execution_binding_sha256"
        ),
        "model_provenance_sha256": _durable_identity_value(
            "model_provenance_sha256"
        ),
        "next_action": None,
        "next_action_status": "LEGACY_NOT_RECORDED",
        "grounded_candidates": cycle.get("grounded_candidates"),
        "closed_or_suppressed_collision_count": cycle.get(
            "closed_or_suppressed_collision_count"
        ),
    }
    from solana_alpha_lab.factory.hfic_control_integrity import (
        effective_control_terminal,
    )

    bundle["effective_control_terminal"] = effective_control_terminal(bundle)
    if not isinstance(bundle.get("grounded_candidates"), list):
        bundle.pop("grounded_candidates", None)
    if "closed_or_suppressed_collision_count" not in cycle:
        bundle.pop("closed_or_suppressed_collision_count", None)
    stamped_cycles = {
        int(row["cycle_index"])
        for row in cycles
        if isinstance(row.get("cycle_index"), int)
        and not isinstance(row.get("cycle_index"), bool)
        and row["cycle_index"] > 1
    }
    if len(stamped_cycles) == 1:
        # Only an explicitly authorized additional cycle is marked; cycle 1 stays unmarked.
        bundle["cycle_index"] = next(iter(stamped_cycles))
    elif len(stamped_cycles) > 1:
        raise HficSessionError("SCIENTIFIC_IDENTITY_CONFLICT")
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
    if read_mode:
        if identity_conflict_fields:
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                DISPOSITION_UNRESOLVED,
            )

            bundle["identity_status"] = DISPOSITION_UNRESOLVED
            bundle["identity_conflict_fields"] = list(identity_conflict_fields)
            for key in identity_conflict_fields:
                bundle[key] = None
        else:
            bundle["identity_status"] = "BOUND"
            bundle["identity_conflict_fields"] = []
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


def _classification_owner_readout(bundle: Mapping[str, Any]) -> str:
    receipt = bundle.get("classifier_receipt")
    route = None
    reasons: list[str] = []
    classifier_terminal = bundle.get("lane_classifier_terminal")
    if isinstance(receipt, Mapping):
        route = receipt.get("classifier_route_terminal")
        raw_reasons = receipt.get("reason_codes")
        if isinstance(raw_reasons, list):
            reasons = [str(item) for item in raw_reasons]
        if not classifier_terminal:
            classifier_terminal = receipt.get("lane_classifier_terminal")
    claimed = bundle.get("critic_claimed_terminal")
    if bundle.get("runner_up_failover_used"):
        parts = [
            f"primary_terminal={bundle.get('primary_critic_terminal')}",
            f"final_terminal={bundle.get('final_session_terminal') or bundle.get('critic_terminal')}",
        ]
    else:
        parts = [
            f"terminal={bundle.get('critic_terminal') or bundle.get('final_session_terminal')}",
            f"classifier={classifier_terminal}",
        ]
        if isinstance(route, str) and route:
            parts.append(f"route={route}")
        if reasons:
            parts.append("reasons=" + ",".join(reasons))
    if isinstance(claimed, str) and claimed:
        parts.append(f"critic_claimed={claimed}")
    if (
        bundle.get("critic_terminal") == "KILL_UNBOUND_EVIDENCE"
        or bundle.get("primary_critic_terminal") == "KILL_UNBOUND_EVIDENCE"
        or classifier_terminal == "DENY_HFIC_AVAILABILITY_GATE"
    ):
        parts.append("gate_denial=persisted_KILL_not_error")
    return " ".join(parts)


def show_session(store: Any, session_id: str, *, repo_root: Any = None) -> dict[str, Any]:
    bundle = load_session_bundle(store, session_id, read_mode=True)
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
    from solana_alpha_lab.factory.hfic_memory_policy import quarantined_session_ids

    payload = {
        "session_id": bundle["session_id"],
        "session_state": bundle["session_state"],
        "evidence_epoch_sha256": bundle.get("evidence_epoch_sha256") or "0" * 64,
        "market_evidence_epoch_sha256": bundle.get("market_evidence_epoch_sha256"),
        "scientific_slot_sha256": bundle.get("scientific_slot_sha256"),
        "session_receipt_sha256": bundle.get("session_receipt_sha256"),
        "terminal_receipt_sha256": bundle.get("session_receipt_sha256"),
        "focus_key_sha256": bundle.get("focus_key_sha256") or "0" * 64,
        "search_key_sha256": bundle.get("search_key_sha256") or "0" * 64,
        "journal_scope": bundle.get("search_key_sha256") or "0" * 64,
        "memory_eligibility_sha256": bundle.get("memory_eligibility_sha256"),
        "search_memory_quarantined": session_id in set(quarantined_session_ids(store)),
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
        "primary_critic_terminal": bundle.get("primary_critic_terminal"),
        "final_session_terminal": bundle.get("final_session_terminal"),
        "runner_up_critic_terminal": bundle.get("runner_up_critic_terminal"),
        "runner_up_failover_used": bool(bundle.get("runner_up_failover_used")),
        "critic_screen_count": bundle.get("critic_screen_count"),
        "lane_classifier_terminal": bundle.get("lane_classifier_terminal"),
        "classifier_route_terminal": (bundle.get("classifier_receipt") or {}).get(
            "classifier_route_terminal"
        )
        if isinstance(bundle.get("classifier_receipt"), Mapping)
        else None,
        "availability_gate_reason_codes": list(
            (bundle.get("classifier_receipt") or {}).get("reason_codes") or []
        )
        if isinstance(bundle.get("classifier_receipt"), Mapping)
        else [],
        "critic_claimed_terminal": bundle.get("critic_claimed_terminal"),
        "repair_continuation_disposition_sha256": bundle.get(
            "repair_continuation_disposition_sha256"
        ),
        "grounded_result_sha256": bundle.get("grounded_result_sha256"),
        "grounded_result_refs": bundle.get("grounded_result_refs"),
        "owner_readout": _classification_owner_readout(bundle),
        "decision_event_ids": bundle.get("decision_event_ids") or [],
        "next": bundle.get("next") or "STOP",
        "next_action": bundle.get("next_action"),
        "next_action_status": bundle.get("next_action_status") or "LEGACY_NOT_RECORDED",
        "decisions": bundle.get("decisions") or {},
        "authority": bundle["authority"],
        "session_receipt": _display_session_receipt(
            bundle.get("session_receipt"), provenance_status
        ),
        "identity_status": bundle.get("identity_status"),
        "identity_conflict_fields": list(bundle.get("identity_conflict_fields") or []),
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
                        and (
                            not bundle.get("runner_up_failover_used")
                            or bool(bundle.get("runner_up_critic_result"))
                        )
                    )
                )
            )
        ),
        "candidates_retrievable": not _bundle_candidate_reference_gaps(bundle),
    }
    journal = str(payload.get("journal_scope") or "")
    if re.fullmatch(r"[0-9a-f]{64}", journal) is not None:
        try:
            from solana_alpha_lab.factory.hfic_repair_continuation import (
                spent_looks_from_journal,
            )

            spent = spent_looks_from_journal(store, journal)
            payload["spent_main_looks"] = int(spent["spent_main_looks"])
            payload["spent_adaptive_looks"] = int(spent["spent_adaptive_looks"])
            payload["spent_preview_looks"] = int(spent["spent_preview_looks"])
            payload["spent_look_ids"] = list(spent["allowed_look_ids"])
        except Exception:
            pass
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
    from solana_alpha_lab.factory.hfic_memory_policy import (
        iter_search_memory_hypothesis_payloads,
    )

    cards: list[dict[str, Any]] = []
    for payload in iter_search_memory_hypothesis_payloads(store):
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
    bundle = load_session_bundle(store, session_id, read_mode=True)
    if bundle is None:
        raise HficSessionError("SESSION_NOT_FOUND")
    if bundle.get("identity_status") == "UNRESOLVED_BINDING":
        from solana_alpha_lab.factory.hfic_provenance import store_provenance_label

        shown = show_session(store, session_id, repo_root=repo_root)
        return {
            **shown,
            "runtime_no_git": "UNRESOLVED_BINDING",
            "proof_status": "NOT_A_PROOF",
            "store_provenance_time_status": store_provenance_label(store),
        }
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
        if receipt.get("runner_up_failover_used"):
            _verify_failover_receipt_identity(receipt)
            ru_result = str(receipt.get("runner_up_critic_result_sha256") or "")
            if (
                len(ru_result) != 64
                or bundle.get("runner_up_critic_result") is None
                or str(bundle.get("runner_up_critic_result_sha256") or "") != ru_result
            ):
                raise HficSessionError("SESSION_RECEIPT_HASH_MISMATCH")
            ru_input = str(receipt.get("runner_up_critic_input_packet_sha256") or "")
            if (
                len(ru_input) != 64
                or bundle.get("runner_up_critic_input_packet") is None
                or str(bundle.get("runner_up_critic_input_packet_sha256") or "") != ru_input
            ):
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
        provenance_status_for_session,
        store_provenance_label,
    )

    provenance_status = provenance_status_for_session(store, session_id)
    store_provenance = store_provenance_label(store)
    warning = ""
    if store_provenance.startswith("INVALID:") and provenance_status == "VALID":
        warning = f" store_provenance={store_provenance} warning=UNRELATED_HISTORY"
    payload = {
        **shown,
        "runtime_no_git": "PROVEN",
        "proof_status": "PROVEN",
        "provider_calls_actual": provider_calls,
        "git_composite_unchanged": True,
        "candidates_retrievable": shown["candidates_retrievable"],
        "artifacts_retrievable": shown["artifacts_retrievable"],
        "provenance_time_status": provenance_status,
        "store_provenance_time_status": store_provenance,
        "owner_readout": str(shown.get("owner_readout") or "") + warning,
        "recovered_exact_time": False,
    }
    if provenance_status == PROVENANCE_CORRECTED:
        payload["original_exact_time_status"] = "UNKNOWN"
        payload["chronological_use_forbidden"] = True
    return payload
