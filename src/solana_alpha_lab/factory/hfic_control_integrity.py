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
PIT_READY_AVAILABILITY_CLASS = "PIT_READY"
DENY_HFIC_AVAILABILITY_GATE = "DENY_HFIC_AVAILABILITY_GATE"
UNRESOLVED_REQUIREMENT_REASON = "UNRESOLVED_REQUIREMENT"
PASS_FAST_LANE_READY_TERMINAL = "PASS_FAST_LANE_READY"
# Non-observation classifier terminals. The availability gate is not this
# table; it fires only when the mapped HFIC terminal is PASS_FAST_LANE_READY.
DIRECT_CLASSIFIER_HFIC_TERMINAL = {
    "FAST_LANE_READY": PASS_FAST_LANE_READY_TERMINAL,
    "REPLAY_AVAILABLE": PASS_FAST_LANE_READY_TERMINAL,
    "BLOCKED_DATA": "PASS_DATA_OPTION_REQUIRED",
    "CHANGE_LANE_CAPABILITY_GAP": "PASS_CHANGE_LANE_REQUIRED",
    "FAST_LANE_OWNER_GATE_REQUIRED": "OWNER_DECISION_REQUIRED",
    "PROMOTION_LANE_REQUIRED": "OWNER_DECISION_REQUIRED",
    "DENY_INVALID_SPEC": KILL_UNBOUND_EVIDENCE,
    "DENY_INTEGRITY_MISMATCH": KILL_UNBOUND_EVIDENCE,
    DENY_HFIC_AVAILABILITY_GATE: KILL_UNBOUND_EVIDENCE,
}
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


def classifier_route_requires_availability_gate(classifier_terminal: str) -> bool:
    """True when the shared mapping sends this raw terminal to PASS_FAST_LANE_READY."""

    from solana_alpha_lab.factory.observation_fast_lane_terminals import (
        hfic_terminal_for_classifier,
    )

    mapped = hfic_terminal_for_classifier(classifier_terminal)
    if mapped is None:
        mapped = DIRECT_CLASSIFIER_HFIC_TERMINAL.get(classifier_terminal)
    return mapped == PASS_FAST_LANE_READY_TERMINAL


def _unresolved_requirements(selected: Mapping[str, Any]) -> list[str]:
    unresolved = text_list(selected.get("unresolved_requirements"))
    if unresolved:
        return unresolved
    grounding = selected.get("grounding")
    if isinstance(grounding, Mapping):
        return text_list(grounding.get("unresolved_requirements"))
    return []


def fast_lane_availability_denial_codes(selected: Mapping[str, Any]) -> list[str]:
    """Typed denial codes. Empty means the PIT/unresolved gate allows the route."""

    codes: list[str] = []
    if _unresolved_requirements(selected):
        codes.append(UNRESOLVED_REQUIREMENT_REASON)
    raw_required = selected.get("required_feature_ids")
    if raw_required is None:
        return codes
    if not isinstance(raw_required, list):
        codes.append("REQUIRED_BINDING_NOT_PIT_READY")
        return codes
    required_ids: list[str] = []
    seen: set[str] = set()
    malformed = False
    for item in raw_required:
        if not isinstance(item, str) or not item:
            malformed = True
            continue
        if item in seen:
            continue
        seen.add(item)
        required_ids.append(item)
    if malformed:
        codes.append("REQUIRED_BINDING_NOT_PIT_READY")
    if not required_ids:
        return codes
    grounding = selected.get("grounding")
    bindings = grounding.get("feature_bindings") if isinstance(grounding, Mapping) else None
    by_id: dict[str, list[str]] = {}
    if isinstance(bindings, list):
        for item in bindings:
            if not isinstance(item, Mapping):
                continue
            feat = item.get("feature_id")
            if not isinstance(feat, str) or not feat:
                continue
            availability = item.get("availability_class")
            class_name = availability if isinstance(availability, str) else ""
            by_id.setdefault(feat, []).append(class_name)
    for feat in required_ids:
        observed = by_id.get(feat)
        if observed is None or len(observed) != 1 or observed[0] != PIT_READY_AVAILABILITY_CLASS:
            codes.append(f"REQUIRED_BINDING_NOT_PIT_READY:{feat}")
    return codes


def deny_unresolved_fast_lane(
    selected: Mapping[str, Any],
    classifier_terminal: str,
) -> None:
    if not classifier_route_requires_availability_gate(classifier_terminal):
        return
    if UNRESOLVED_REQUIREMENT_REASON in fast_lane_availability_denial_codes(selected):
        raise ValueError(KILL_UNBOUND_EVIDENCE)


def deny_non_pit_fast_lane(
    selected: Mapping[str, Any],
    classifier_terminal: str,
) -> None:
    """Refuse a PASS_FAST_LANE_READY route unless required bindings are PIT_READY.

    Packet 1.4 HFIC classify path only. The switch is the mapped HFIC terminal,
    not a hand-listed classifier set. Does not read
    available_to_strategy_semantics as the machine switch. Does not re-resolve
    Catalog or RDP. Extra unrelated bindings cannot substitute for a required
    feature.
    """
    if not classifier_route_requires_availability_gate(classifier_terminal):
        return
    pit_codes = [
        code
        for code in fast_lane_availability_denial_codes(selected)
        if code.startswith("REQUIRED_BINDING_NOT_PIT_READY")
    ]
    if pit_codes:
        raise ValueError(KILL_UNBOUND_EVIDENCE)


def resolve_control_corpus_yield(
    datasets: Sequence[Mapping[str, Any]],
    *,
    corpus_dataset_id: str,
    min_usable_yield_eligible: int,
    data_root: Any | None = None,
    repo_root: Any | None = None,
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
    raw = None
    census_rows = current.get("census_rows")
    observation_rows = current.get("observation_rows")
    if isinstance(census_rows, Sequence) and isinstance(observation_rows, Sequence):
        from solana_alpha_lab.factory.scientific_eligibility_projection import (
            project_scientific_eligibility,
            sanitize_projection_row,
        )

        projected = project_scientific_eligibility(
            [row for row in census_rows if isinstance(row, Mapping)],
            [
                sanitize_projection_row(row)
                for row in observation_rows
                if isinstance(row, Mapping)
            ],
        )
        raw = projected["base_x_population"]["n"]
    if raw is None and data_root is not None and repo_root is not None:
        from pathlib import Path

        from solana_alpha_lab.factory.scientific_eligibility_projection import (
            ScientificEligibilityError,
            try_project_scientific_eligibility_from_data_root,
        )

        try:
            projected = try_project_scientific_eligibility_from_data_root(
                Path(data_root),
                repo_root=Path(repo_root),
            )
        except ScientificEligibilityError:
            # Bound C1 identity with unproven/incompatible X300 geometry must
            # not fall back to a stamped yield / complete-case N.
            return CONTROL_CORPUS_UNRESOLVABLE, None
        if projected is not None:
            raw = projected["base_x_population"]["n"]
    if raw is None:
        raw = current.get("base_x_population_n", current.get("base_x_n"))
        if raw is None:
            labels = current.get("labels")
            if isinstance(labels, Mapping):
                raw = labels.get("base_x_population_n", labels.get("base_x_n"))
    if raw is None:
        return CONTROL_CORPUS_UNRESOLVABLE, None
    base_x_n = int(raw)
    if base_x_n < int(min_usable_yield_eligible):
        return CONTROL_YIELD_BELOW_MIN, base_x_n
    return "OK", base_x_n


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
