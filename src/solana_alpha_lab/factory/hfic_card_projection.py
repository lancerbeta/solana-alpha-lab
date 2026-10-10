"""Finite, lossless authored-card view at the Forge transport boundary.

Never changes persisted bytes, scientific scope/target, resolver bindings or
attempt identity. Missing is a declared unknown; explicit empty stays empty.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

UNKNOWN = "NOT_DECLARED_IN_DRAFT"
RISK_FIELDS = (
    "confounders", "pit_leakage_survivorship_risks",
    "execution_capacity_risks", "missing_or_forward_only_data",
)
ALIASES = {
    "claim": ("one_sentence_claim",),
    "actor_counterparty": ("actor_and_counterparty",),
    "population": ("point_in_time_population",),
    "primary_x_family": ("primary_X",),
    "primary_y": ("primary_Y",),
    "horizon_notional": ("horizon_and_notional",),
    "alternative_world": ("strongest_alternative_world",),
    "execution_capacity_risks": ("execution_and_capacity_risk",),
    "missing_or_forward_only_data": ("forward_only_or_missing_data",),
    "nearest_prior_and_difference": ("material_difference_from_prior",),
}
# These two legacy fields are distinct components, in authored order.
PIT_COMPONENTS = ("PIT_and_leakage_risk", "survivorship_and_dependency_risk")
TEXT_FIELDS = (
    "claim", "actor_counterparty", "mechanism", "claim_form", "population",
    "decision_timestamp", "primary_x_family", "primary_y", "horizon_notional",
    "nearest_prior_and_difference", "why_not_arbitraged", "disconfirming_prediction",
    "negative_control", "alternative_world", "mundane_alternative", "proposed_method",
    "cheapest_falsifier", "pass_fail_inconclusive_semantics", "decision_unlocked",
)

class CardProjectionError(ValueError):
    def __init__(self, code: str, **detail: Any):
        self.code, self.detail = code, {"stage": "AUTHORING_TRANSPORT", **detail}
        super().__init__(code)

def _shape(field: str, value: Any, expected: str):
    raise CardProjectionError(
        "CARD_TRANSPORT_SHAPE_INVALID", field_path=field, expected_type=expected,
        actual_type=type(value).__name__, next_action="REPAIR_AUTHORED_INPUT_BEFORE_PERSIST",
    )

def _risk(field: str, value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    _shape(field, value, "string_or_array_of_strings")

def project_material_card(card: Mapping[str, Any]) -> dict[str, Any]:
    """Return a checked view; do not mutate or serialize the source card."""
    out = dict(card)
    out.pop("pit_component_provenance", None)  # transport-only, never author supplied
    for canonical, aliases in ALIASES.items():
        present = [key for key in (canonical, *aliases) if key in card]
        if not present:
            continue
        values = [(_risk(key, card[key]) if canonical in RISK_FIELDS else card[key]) for key in present]
        if any(value != values[0] for value in values[1:]):
            raise CardProjectionError("CARD_ALIAS_CONFLICT", field_paths=present,
                                      next_action="RESOLVE_AUTHORED_ALIAS_CONFLICT_BEFORE_PERSIST")
        out[canonical] = values[0]
    components = [key for key in PIT_COMPONENTS if key in card]
    if components:
        provenance = {
            key: _risk(key, card[key]) if key in card else None
            for key in PIT_COMPONENTS
        }
        combined = [value for key in components for value in provenance[key]]
        canonical = "pit_leakage_survivorship_risks"
        if canonical in card and _risk(canonical, card[canonical]) != combined:
            raise CardProjectionError("CARD_ALIAS_CONFLICT", field_paths=[canonical, *components],
                                      next_action="RESOLVE_AUTHORED_ALIAS_CONFLICT_BEFORE_PERSIST")
        out[canonical] = combined
        out["pit_component_provenance"] = provenance
    for field in RISK_FIELDS:
        out[field] = _risk(field, out[field]) if field in out else [UNKNOWN]
    for field in TEXT_FIELDS:
        if field in out and not isinstance(out[field], str):
            _shape(field, out[field], "string")
        if field in out and out[field] == "" and field not in {"actor_counterparty", "mechanism"}:
            raise CardProjectionError("CARD_TRANSPORT_EMPTY_TEXT", field_path=field,
                                      next_action="DECLARE_TEXT_OR_EXPLICIT_UNKNOWN_BEFORE_PERSIST")
    if "available_data_bindings" in out:
        bindings = out["available_data_bindings"]
        if not isinstance(bindings, list):
            _shape("available_data_bindings", bindings, "array_of_strings_or_typed_bindings")
        for index, binding in enumerate(bindings):
            if not isinstance(binding, (str, Mapping)):
                _shape(f"available_data_bindings[{index}]", binding, "string_or_typed_binding")
    return out


def authoring_contract() -> dict[str, Any]:
    """Compact ordinary packet contract; ceilings come from frozen policy."""
    return {
        "contract": "FORGE_RESEARCH_FLOW_RELIABILITY_V1",
        "draft_schema": "hypothesis_forge_draft_v1_3",
        "candidate_ceiling": "research_policy_context.this_search.limits.max_generated",
        "risk_fields": list(RISK_FIELDS),
        "risk_transport": "string -> one exact string; list[str] -> unchanged; absent -> [NOT_DECLARED_IN_DRAFT] (unknown); [] stays []; other types refuse before persist",
        "canonical_fields": ["claim", "population", "primary_x_family", "primary_y", "horizon_notional", "alternative_world", "proposed_method", "cheapest_falsifier", "available_data_bindings"],
        "legacy_aliases": {key: list(values) for key, values in ALIASES.items()},
        "pit_components": list(PIT_COMPONENTS),
        "pit_transport": "distinct components concatenated in declared order; optional provenance preserves each component, null=absent and []=authored empty; conflicts refuse",
        "predictive": "actor_counterparty and mechanism may be absent; do not invent causal identification",
        "bindings": "strings or typed objects; no prose-to-binding inference",
        "saved_look_bindings": {
            "condition": "selected candidate bound to a saved discovery-execute look",
            "placement": "copy exact emitted fields to candidate top level before persist",
            "required_top_level": ["population", "decision_timestamp", "target", "estimand", "explanatory_condition", "evidence_surface_mode"],
            "conditional_top_level": ["representation_scope", "research_scope_rule_sha256", "research_scope_statement"],
            "sources": {
                "population": "candidate_scope.population",
                "decision_timestamp": "candidate_scope.decision_timestamp",
                "target": "candidate_scope.target",
                "estimand": "candidate_scope.estimand",
                "explanatory_condition": "candidate_scope.explanatory_condition",
                "evidence_surface_mode": "candidate_scope.evidence_surface_mode",
                "representation_scope": "candidate_scope.representation_scope",
                "research_scope_rule_sha256": "candidate_scope.research_scope_rule_sha256",
                "research_scope_statement": "descriptive_readout.scientific_identity.research_scope_statement",
                "primary_x_family": "descriptive_readout.scientific_identity.primary_x_family",
                "primary_y": "descriptive_readout.scientific_identity.primary_y",
                "horizon_notional": "descriptive_readout.scientific_identity.horizon_notional",
            },
            "missing": "unavailable emitted field stays unavailable; never infer identity or scope from outcomes",
            "authored_semantics": "question, estimand and condition fixed before MAIN; copy bindings without changing claim, alternative or verdict",
        },
        "non_equivalent": ["primary_y != target", "mundane_alternative != alternative_world", "data_already_available != available_data_bindings", "candidate_method_family != proposed_method"],
    }
