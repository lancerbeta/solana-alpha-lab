"""CONTROL decision-integrity helpers for HFIC packet 1.4 / F3 / yield.

Does not change HFIC-CAND identity, F3 receipt split, or generic lane_classifier.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CURRENT_REPRESENTATION_CONTROL_V1 = "CURRENT_REPRESENTATION_CONTROL_V1"
CONTROL_YIELD_BELOW_MIN = "CONTROL_YIELD_BELOW_MIN"
CONTROL_CORPUS_UNRESOLVABLE = "CONTROL_CORPUS_UNRESOLVABLE"
EXPERIMENT_SPEC_GROUNDING_MISMATCH = "EXPERIMENT_SPEC_GROUNDING_MISMATCH"
CRITIC_PACKET_GROUNDING_MISMATCH = "CRITIC_PACKET_GROUNDING_MISMATCH"
KILL_UNBOUND_EVIDENCE = "KILL_UNBOUND_EVIDENCE"

CASE_A_TERMINALS = frozenset(
    {
        "PASS_FAST_LANE_READY",
        "PASS_CHANGE_LANE_REQUIRED",
    }
)
PROBE_PERMIT_TERMINALS = frozenset(
    {
        "NO_WORTHY_HYPOTHESIS",
        "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
    }
)
FAST_LANE_CLASSIFIER_TERMINALS = frozenset(
    {
        "FAST_LANE_READY",
        "REPLAY_AVAILABLE",
    }
)
PIT_READY_AVAILABILITY_CLASS = "PIT_READY"
CASE_C_KILL_TERMINALS = frozenset(
    {
        "KILL_UNBOUND_EVIDENCE",
        "KILL_DATA_INFEASIBLE",
    }
)


def session_evidence_surface_mode(item: Mapping[str, Any] | None) -> str | None:
    if not isinstance(item, Mapping):
        return None
    raw = item.get("evidence_surface_mode")
    if raw == CURRENT_REPRESENTATION_CONTROL_V1:
        return CURRENT_REPRESENTATION_CONTROL_V1
    return None


def feat_id_set(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    out: set[str] = set()
    for item in values:
        if isinstance(item, str) and item:
            out.add(item)
    return out


def text_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if isinstance(item, str)]


def effective_control_terminal(receipt: Mapping[str, Any] | None) -> str:
    """Prereg/read-model terminal after F3.

    Prefer final_session_terminal when present and non-empty; otherwise
    critic_terminal. Do not rewrite historical receipts.
    """
    if not isinstance(receipt, Mapping):
        return ""
    final = receipt.get("final_session_terminal")
    if isinstance(final, str) and final.strip():
        return final
    critic = receipt.get("critic_terminal")
    if isinstance(critic, str):
        return critic
    return ""


def control_case_a(terminal: str) -> bool:
    return terminal in CASE_A_TERMINALS


def control_probe_permitted(terminal: str) -> bool:
    if terminal == "RUNNER_UP_REVISION_REQUIRED":
        return False
    if terminal in CASE_A_TERMINALS:
        return False
    return terminal in PROBE_PERMIT_TERMINALS


def control_case_c(terminal: str) -> bool:
    return terminal in CASE_C_KILL_TERMINALS


def selected_packet_from_frozen(frozen: Mapping[str, Any]) -> Mapping[str, Any] | None:
    packet = frozen.get("critic_input_packet")
    if isinstance(packet, Mapping):
        return packet
    return None


def assert_packet_grounding_consistent(
    selected: Mapping[str, Any],
    card: Mapping[str, Any],
    grounding: Mapping[str, Any],
    context_packet_sha256: str,
) -> None:
    card_feats = feat_id_set(card.get("required_feature_ids"))
    card_caps = feat_id_set(card.get("required_capability_ids"))
    card_unresolved = text_list(card.get("unresolved_requirements"))
    ground_unresolved = text_list(grounding.get("unresolved_requirements"))
    selected_unresolved = text_list(selected.get("unresolved_requirements"))
    if feat_id_set(selected.get("required_feature_ids")) != card_feats:
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    if feat_id_set(selected.get("required_capability_ids")) != card_caps:
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    if selected_unresolved != ground_unresolved or ground_unresolved != card_unresolved:
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    digest = str(grounding.get("context_packet_sha256") or "")
    if digest != str(context_packet_sha256 or "").lower():
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    packet_grounding = selected.get("grounding")
    if not isinstance(packet_grounding, Mapping):
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    if str(packet_grounding.get("context_packet_sha256") or "") != digest:
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)
    if text_list(packet_grounding.get("unresolved_requirements")) != ground_unresolved:
        raise ValueError(CRITIC_PACKET_GROUNDING_MISMATCH)


def assert_experiment_spec_grounding(
    spec: Mapping[str, Any],
    selected: Mapping[str, Any],
) -> None:
    cand_feats = feat_id_set(selected.get("required_feature_ids"))
    spec_feats = feat_id_set(spec.get("required_feature_ids"))
    if cand_feats:
        if spec_feats != cand_feats:
            raise ValueError(EXPERIMENT_SPEC_GROUNDING_MISMATCH)
        return
    if spec_feats:
        raise ValueError(EXPERIMENT_SPEC_GROUNDING_MISMATCH)


def deny_unresolved_fast_lane(
    selected: Mapping[str, Any],
    classifier_terminal: str,
) -> None:
    unresolved = text_list(selected.get("unresolved_requirements"))
    if not unresolved:
        grounding = selected.get("grounding")
        if isinstance(grounding, Mapping):
            unresolved = text_list(grounding.get("unresolved_requirements"))
    if unresolved and classifier_terminal in FAST_LANE_CLASSIFIER_TERMINALS:
        raise ValueError(KILL_UNBOUND_EVIDENCE)


def deny_non_pit_fast_lane(
    selected: Mapping[str, Any],
    classifier_terminal: str,
) -> None:
    """Refuse Fast Lane unless every required freeze-owned binding is PIT_READY.

    Packet 1.4 HFIC classify path only. Does not read
    available_to_strategy_semantics as the machine switch. Does not re-resolve
    Catalog or RDP. Extra unrelated bindings cannot substitute for a required
    feature.
    """
    if classifier_terminal not in FAST_LANE_CLASSIFIER_TERMINALS:
        return
    raw_required = selected.get("required_feature_ids")
    if raw_required is None:
        return
    if not isinstance(raw_required, list):
        raise ValueError(KILL_UNBOUND_EVIDENCE)
    required_ids: list[str] = []
    seen: set[str] = set()
    for item in raw_required:
        if not isinstance(item, str) or not item:
            raise ValueError(KILL_UNBOUND_EVIDENCE)
        if item in seen:
            continue
        seen.add(item)
        required_ids.append(item)
    if not required_ids:
        return
    grounding = selected.get("grounding")
    if not isinstance(grounding, Mapping):
        raise ValueError(KILL_UNBOUND_EVIDENCE)
    bindings = grounding.get("feature_bindings")
    if not isinstance(bindings, list):
        raise ValueError(KILL_UNBOUND_EVIDENCE)
    by_id: dict[str, list[str]] = {}
    for item in bindings:
        if not isinstance(item, Mapping):
            raise ValueError(KILL_UNBOUND_EVIDENCE)
        feat = item.get("feature_id")
        if not isinstance(feat, str) or not feat:
            raise ValueError(KILL_UNBOUND_EVIDENCE)
        availability = item.get("availability_class")
        class_name = availability if isinstance(availability, str) else ""
        by_id.setdefault(feat, []).append(class_name)
    for feat in required_ids:
        observed = by_id.get(feat)
        if observed is None or len(observed) != 1:
            raise ValueError(KILL_UNBOUND_EVIDENCE)
        if observed[0] != PIT_READY_AVAILABILITY_CLASS:
            raise ValueError(KILL_UNBOUND_EVIDENCE)


def resolve_control_corpus_yield(
    datasets: Sequence[Mapping[str, Any]],
    *,
    corpus_dataset_id: str,
    min_usable_yield_eligible: int,
) -> tuple[str, int | None]:
    current: Mapping[str, Any] | None = None
    for item in datasets:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("dataset_id") or "") != corpus_dataset_id:
            continue
        current = item
        break
    if current is None:
        return CONTROL_CORPUS_UNRESOLVABLE, None
    yield_eligible = int(current.get("yield_eligible") or 0)
    if yield_eligible < int(min_usable_yield_eligible):
        return CONTROL_YIELD_BELOW_MIN, yield_eligible
    return "OK", yield_eligible


def control_packet_has_raw_sequences(packet: Mapping[str, Any]) -> bool:
    forbidden = {
        "observations",
        "sequences",
        "trajectory",
        "normalized_trajectory_v1",
        "raw_rows",
        "motif",
        "parquet_rows",
    }
    return any(key in packet for key in forbidden)
