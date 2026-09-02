"""Deterministic HFIC feature/capability grounding and session diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from solana_alpha_lab.factory.hfic_identity import HficIdentityError, normalize_text
from solana_alpha_lab.factory.market_feature_surface import (
    SURFACE_CONFIG_RELATIVE,
    feature_index,
    load_surface_config,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256

UNKNOWN_FEATURE_ID = "FORGE_CANDIDATE_UNKNOWN_FEATURE_ID"
UNKNOWN_CAPABILITY_ID = "FORGE_CANDIDATE_UNKNOWN_CAPABILITY_ID"
MISSING_RESEARCH_INPUT = "FORGE_CANDIDATE_MISSING_RESEARCH_INPUT"
NOT_AVAILABLE_LEGACY = "NOT_AVAILABLE_LEGACY"
DIAGNOSTICS_LAST_MAX = 20


class HficGroundingError(ValueError):
    """Fail-closed grounding / diagnostics error."""


def _surface_config_bytes(repo_root: Path) -> bytes:
    path = Path(repo_root) / SURFACE_CONFIG_RELATIVE
    try:
        return path.read_bytes()
    except OSError as exc:
        raise HficGroundingError("FEATURE_SURFACE_CONFIG_MISSING") from exc


def build_feature_grounding_projection(repo_root: Path | str) -> dict[str, Any]:
    """Compact deterministic feature-grounding projection for FORGE_CONTEXT_PACKET."""
    root = Path(repo_root)
    config_bytes = _surface_config_bytes(root)
    source_digest = hashlib.sha256(config_bytes).hexdigest()
    config = load_surface_config(root)
    index = feature_index(config)
    entries: list[dict[str, Any]] = []
    for feature_id in sorted(index):
        item = index[feature_id]
        entries.append(
            {
                "feature_id": feature_id,
                "availability_class": str(item.get("availability_class") or ""),
                "available_to_strategy_semantics": str(
                    item.get("available_to_strategy_semantics") or ""
                ),
                "entity_scope": str(item.get("entity_scope") or ""),
                "units": str(item.get("units") or ""),
            }
        )
    return {
        "feature_grounding_entries": entries,
        "feature_grounding_source_digest_sha256": source_digest,
        "feature_grounding_truncated": False,
        "dropped_feature_count": 0,
    }


def _value_status_for_availability(availability_class: str) -> str | None:
    if availability_class == "MISSING_CAPABILITY":
        return "MISSING_CAPABILITY"
    if availability_class == "MISSING":
        return "NOT_AVAILABLE"
    if availability_class == "PIT_READY":
        return "PIT_READY"
    if availability_class in {"HISTORICAL_RECONSTRUCTIBLE", "FORWARD_ONLY"}:
        return "UNKNOWN"
    return None


def ground_candidate(
    card: Mapping[str, Any],
    *,
    repo_root: Path | str,
    context_packet_sha256: str,
    accepted_capability_ids: Sequence[str],
) -> dict[str, Any]:
    """Resolve known FEAT/CAP IDs; allow typed unresolved requirements."""
    root = Path(repo_root)
    if not isinstance(context_packet_sha256, str) or len(context_packet_sha256) != 64:
        raise HficGroundingError("CONTEXT_PACKET_SHA256_INVALID")
    config = load_surface_config(root)
    index = feature_index(config)
    accepted = {str(item) for item in accepted_capability_ids if str(item)}

    raw_features = card.get("required_feature_ids") or []
    raw_caps = card.get("required_capability_ids") or []
    raw_unresolved = card.get("unresolved_requirements") or []
    if not isinstance(raw_features, list):
        raise HficGroundingError(UNKNOWN_FEATURE_ID)
    if not isinstance(raw_caps, list):
        raise HficGroundingError(UNKNOWN_CAPABILITY_ID)
    if not isinstance(raw_unresolved, list):
        raise HficGroundingError("UNRESOLVED_REQUIREMENTS_INVALID")

    feature_ids = [str(item) for item in raw_features]
    capability_ids = [str(item) for item in raw_caps]
    unresolved = [str(item).strip() for item in raw_unresolved if str(item).strip()]

    if not feature_ids and not unresolved:
        raise HficGroundingError(MISSING_RESEARCH_INPUT)

    feature_bindings: list[dict[str, Any]] = []
    for feature_id in feature_ids:
        feature = index.get(feature_id)
        if feature is None:
            raise HficGroundingError(UNKNOWN_FEATURE_ID)
        availability = str(feature.get("availability_class") or "")
        binding: dict[str, Any] = {
            "feature_id": feature_id,
            "availability_class": availability,
            "available_to_strategy_semantics": str(
                feature.get("available_to_strategy_semantics") or ""
            ),
        }
        value_status = _value_status_for_availability(availability)
        if value_status is not None:
            binding["value_status"] = value_status
        feature_bindings.append(binding)

    capability_bindings: list[dict[str, Any]] = []
    for capability_id in capability_ids:
        if capability_id not in accepted:
            raise HficGroundingError(UNKNOWN_CAPABILITY_ID)
        capability_bindings.append(
            {
                "capability_id": capability_id,
                "accepted": True,
                "authority_granted": False,
            }
        )

    terminal = "GROUNDED_WITH_GAPS" if unresolved else "GROUNDED"
    gap_classes = {
        str(item["availability_class"])
        for item in feature_bindings
        if item.get("availability_class")
        in {"MISSING", "MISSING_CAPABILITY", "FORWARD_ONLY", "HISTORICAL_RECONSTRUCTIBLE"}
    }
    if gap_classes and terminal == "GROUNDED":
        # Historical/forward/missing are typed availability, not invented IDs.
        # Only unresolved_requirements force GROUNDED_WITH_GAPS per design.
        pass

    return {
        "context_packet_sha256": context_packet_sha256.lower(),
        "feature_bindings": feature_bindings,
        "capability_bindings": capability_bindings,
        "unresolved_requirements": list(unresolved),
        "terminal": terminal,
    }


def structural_signature_v1_sha256(card: Mapping[str, Any]) -> str:
    """Diagnostics-only reduced structural signature. Not HFIC-CAND identity."""
    state = card.get("state_transition")
    if state is None:
        state_norm = "NOT_APPLICABLE"
    else:
        try:
            state_norm = normalize_text(state)
        except HficIdentityError as exc:
            raise HficGroundingError("STRUCTURAL_SIGNATURE_FIELD_INVALID") from exc
        if not state_norm:
            state_norm = "NOT_APPLICABLE"

    def _norm_required(key: str) -> str:
        try:
            return normalize_text(card.get(key) or "")
        except HficIdentityError as exc:
            raise HficGroundingError("STRUCTURAL_SIGNATURE_FIELD_INVALID") from exc

    feature_ids = sorted(str(item) for item in (card.get("required_feature_ids") or []))
    capability_ids = sorted(
        str(item) for item in (card.get("required_capability_ids") or [])
    )
    payload = {
        "actor_counterparty": _norm_required("actor_counterparty"),
        "mechanism": _norm_required("mechanism"),
        "population": _norm_required("population"),
        "decision_timestamp": _norm_required("decision_timestamp"),
        "state_transition": state_norm,
        "required_feature_ids": feature_ids,
        "required_capability_ids": capability_ids,
        "primary_y": _norm_required("primary_y"),
        "horizon_notional": _norm_required("horizon_notional"),
    }
    if any(
        not payload[key]
        for key in (
            "actor_counterparty",
            "mechanism",
            "population",
            "decision_timestamp",
            "primary_y",
            "horizon_notional",
        )
    ):
        raise HficGroundingError("STRUCTURAL_SIGNATURE_FIELD_INVALID")
    return canonical_sha256(payload)


def _unique_count(values: Sequence[str]) -> int:
    return len({item for item in values if item})


def session_diagnostics_from_candidates(
    candidates_with_grounding_and_signature: Sequence[Mapping[str, Any]],
    session_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic per-session diagnostics from frozen candidate contracts."""
    candidates = list(candidates_with_grounding_and_signature)
    candidate_count = len(candidates)

    known_feature_refs = 0
    known_cap_refs = 0
    with_unresolved = 0
    unresolved_count = 0
    pit_ready = 0
    historical_only = 0
    forward_only = 0
    missing_dep = 0
    with_prior = 0
    signatures: list[str] = []
    actors: list[str] = []
    mechanisms: list[str] = []
    state_transitions: list[str] = []
    x_families: list[str] = []
    horizons: list[str] = []

    for card in candidates:
        grounding = card.get("grounding") if isinstance(card.get("grounding"), Mapping) else {}
        feature_bindings = grounding.get("feature_bindings") or []
        capability_bindings = grounding.get("capability_bindings") or []
        unresolved = grounding.get("unresolved_requirements") or []
        if not isinstance(feature_bindings, list):
            feature_bindings = []
        if not isinstance(capability_bindings, list):
            capability_bindings = []
        if not isinstance(unresolved, list):
            unresolved = []

        known_feature_refs += len(feature_bindings)
        known_cap_refs += len(capability_bindings)
        if unresolved:
            with_unresolved += 1
            unresolved_count += len(unresolved)

        classes = {
            str(item.get("availability_class") or "")
            for item in feature_bindings
            if isinstance(item, Mapping)
        }
        if "PIT_READY" in classes:
            pit_ready += 1
        if "HISTORICAL_RECONSTRUCTIBLE" in classes:
            historical_only += 1
        if "FORWARD_ONLY" in classes:
            forward_only += 1
        if classes & {"MISSING", "MISSING_CAPABILITY"}:
            missing_dep += 1

        prior_refs = card.get("prior_work_refs") or []
        if isinstance(prior_refs, list) and any(str(item).strip() for item in prior_refs):
            with_prior += 1

        sig = str(card.get("structural_signature_v1_sha256") or "")
        if sig:
            signatures.append(sig)
        actors.append(str(card.get("actor_counterparty") or ""))
        mechanisms.append(str(card.get("mechanism") or ""))
        state = card.get("state_transition")
        state_transitions.append(
            "NOT_APPLICABLE" if state is None else str(state)
        )
        x_families.append(str(card.get("primary_x_family") or ""))
        horizons.append(str(card.get("horizon_notional") or ""))

    unique_sigs = _unique_count(signatures)
    repetition_count = max(0, len(signatures) - unique_sigs)
    repetition_ratio = (
        float(repetition_count) / float(len(signatures)) if signatures else 0.0
    )

    critic_terminal = str(session_meta.get("critic_terminal") or "")
    selected = session_meta.get("selected_candidate_id")
    selected_present = isinstance(selected, str) and bool(selected.strip())
    no_worthy = critic_terminal == "NO_WORTHY_HYPOTHESIS" or (
        session_meta.get("no_worthy_hypothesis") is True
    )

    diagnostics: dict[str, Any] = {
        "candidate_count": candidate_count,
        "known_feature_reference_count": known_feature_refs,
        "known_capability_reference_count": known_cap_refs,
        "candidate_with_unresolved_requirement_count": with_unresolved,
        "unresolved_requirement_count": unresolved_count,
        "candidate_with_pit_ready_dependency_count": pit_ready,
        "candidate_with_historical_only_dependency_count": historical_only,
        "candidate_with_forward_only_dependency_count": forward_only,
        "candidate_with_missing_dependency_count": missing_dep,
        "unique_structural_signature_count": unique_sigs,
        "structural_repetition_count": repetition_count,
        "structural_repetition_ratio": repetition_ratio,
        "unique_actor_counterparty_count": _unique_count(actors),
        "unique_mechanism_count": _unique_count(mechanisms),
        "unique_state_transition_count": _unique_count(state_transitions),
        "unique_primary_x_family_count": _unique_count(x_families),
        "unique_horizon_notional_count": _unique_count(horizons),
        "candidate_with_known_prior_ref_count": with_prior,
        "closed_or_suppressed_collision_count": int(
            session_meta.get("closed_or_suppressed_collision_count") or 0
        ),
        "critic_terminal": critic_terminal or None,
        "selected_candidate_present": selected_present,
        "no_worthy_hypothesis": bool(no_worthy),
        "lane_classifier_terminal": session_meta.get("lane_classifier_terminal"),
        "next_action_type_if_any": session_meta.get("next_action_type_if_any"),
    }
    if "context_packet_bytes" in session_meta:
        diagnostics["context_packet_bytes"] = session_meta.get("context_packet_bytes")
    if "draft_schema_repair_used" in session_meta:
        diagnostics["draft_schema_repair_used"] = bool(
            session_meta.get("draft_schema_repair_used")
        )
    if "resume_or_replay" in session_meta:
        diagnostics["resume_or_replay"] = bool(session_meta.get("resume_or_replay"))
    return diagnostics


def _receipt_diagnostics(receipt: Mapping[str, Any]) -> dict[str, Any] | str:
    diagnostics = receipt.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        return dict(diagnostics)
    prompt = str(receipt.get("prompt_version") or "")
    if prompt in {"HFIC-V1.0", "HFIC-V1.1"} or diagnostics is None:
        return NOT_AVAILABLE_LEGACY
    return NOT_AVAILABLE_LEGACY


def aggregate_diagnostics(
    receipts: Sequence[Mapping[str, Any]],
    last_n: int,
) -> dict[str, Any]:
    """Bounded longitudinal readout over existing session receipts."""
    if not isinstance(last_n, int) or last_n < 1 or last_n > DIAGNOSTICS_LAST_MAX:
        raise HficGroundingError("DIAGNOSTICS_LAST_N_OUT_OF_BOUNDS")

    ordered = sorted(
        [item for item in receipts if isinstance(item, Mapping)],
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )[:last_n]

    sessions_count = len(ordered)
    no_worthy_sessions = 0
    candidate_count = 0
    unresolved_candidates = 0
    total_candidates_for_rate = 0
    structural_repetition_sum = 0
    structural_denom = 0
    sessions_forward = 0
    sessions_missing = 0
    search_keys: list[str] = []
    prompt_versions: set[str] = set()

    for receipt in ordered:
        prompt = str(receipt.get("prompt_version") or "")
        if prompt:
            prompt_versions.add(prompt)
        search_key = str(receipt.get("search_key_sha256") or "")
        if search_key:
            search_keys.append(search_key)

        diagnostics = _receipt_diagnostics(receipt)
        critic_terminal = str(receipt.get("critic_terminal") or "")
        if critic_terminal == "NO_WORTHY_HYPOTHESIS" or (
            isinstance(diagnostics, Mapping) and diagnostics.get("no_worthy_hypothesis")
        ):
            no_worthy_sessions += 1

        if not isinstance(diagnostics, Mapping):
            continue

        cand_n = int(diagnostics.get("candidate_count") or 0)
        candidate_count += cand_n
        total_candidates_for_rate += cand_n
        unresolved_candidates += int(
            diagnostics.get("candidate_with_unresolved_requirement_count") or 0
        )
        structural_repetition_sum += int(
            diagnostics.get("structural_repetition_count") or 0
        )
        structural_denom += max(cand_n, 0)
        if int(diagnostics.get("candidate_with_forward_only_dependency_count") or 0) > 0:
            sessions_forward += 1
        if int(diagnostics.get("candidate_with_missing_dependency_count") or 0) > 0:
            sessions_missing += 1

    distinct_search_keys = len(set(search_keys))
    replayed_search_keys = max(0, len(search_keys) - distinct_search_keys)

    return {
        "sessions_count": sessions_count,
        "no_worthy_sessions": no_worthy_sessions,
        "no_worthy_rate": (
            float(no_worthy_sessions) / float(sessions_count) if sessions_count else 0.0
        ),
        "candidate_count": candidate_count,
        "candidate_with_unresolved_requirement_rate": (
            float(unresolved_candidates) / float(total_candidates_for_rate)
            if total_candidates_for_rate
            else 0.0
        ),
        "structural_repetition_rate": (
            float(structural_repetition_sum) / float(structural_denom)
            if structural_denom
            else 0.0
        ),
        "sessions_with_forward_only_dependencies": sessions_forward,
        "sessions_with_missing_dependencies": sessions_missing,
        "distinct_search_keys": distinct_search_keys,
        "replayed_search_keys": replayed_search_keys,
        "prompt_versions": sorted(prompt_versions),
        "last_n": last_n,
    }


def collect_session_receipts(store: Any) -> list[dict[str, Any]]:
    """Read-only extract of SESSION_RECEIPT payloads from ResearchStore."""
    receipts: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") != "SESSION_RECEIPT":
            continue
        canonical = payload.get("payload_canonical")
        if not isinstance(canonical, str) or not canonical:
            continue
        loaded = json.loads(canonical)
        if isinstance(loaded, dict):
            receipts.append(loaded)
    return receipts
