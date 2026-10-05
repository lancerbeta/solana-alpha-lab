"""Compound temporal discovery on the ordinary grounded path.

Pure operations, a relative price target and an explicit cost proxy.
This module does not own a store, a lifecycle or a second Forge.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.hfic_grounded_discovery import (
    LIQUIDITY,
    MAX_ADAPTIVE_REFINEMENTS,
    MAX_MAIN_QUERY_SPECS,
    POINT_OFFSET,
    PRICE,
    GroundedDiscoveryError,
    _grouped_cells,
    _parse_time,
    admit_discovery_binding,
)

TEMPORAL_SCHEMA = "smial.hfic-temporal-query"
TEMPORAL_SCHEMA_VERSION = "1.0"
# Additive OPPORTUNITY_EPISODES query version. 1.0/BASE_X identity is unchanged.
TEMPORAL_SCHEMA_VERSION_EPISODES = "1.1"
EPISODE_POPULATION = "OPPORTUNITY_EPISODES"
EPISODE_ANCHOR_KIND = "NOMINATION_T0"
EPISODE_TIME_FEATURE_CLOCK = "FIRST_RELIABLE_AVAILABLE_AT"
TEMPORAL_CALCULATION_VERSION_V1 = "HFIC_TEMPORAL_DISCOVERY_CALC_V1"
TEMPORAL_CALCULATION_VERSION_V2 = "HFIC_TEMPORAL_DISCOVERY_CALC_V2"
TEMPORAL_CALCULATION_VERSION_V3 = "HFIC_TEMPORAL_DISCOVERY_CALC_V3"
# V4: by_cohort reads the same matched sample as pooled and calendar.
TEMPORAL_CALCULATION_VERSION_V4 = "HFIC_TEMPORAL_DISCOVERY_CALC_V4"
# V5 adds a fixed descriptive downside readout to the same admitted sample.
TEMPORAL_CALCULATION_VERSION_V5 = "HFIC_TEMPORAL_DISCOVERY_CALC_V5"
TEMPORAL_CALCULATION_VERSION = TEMPORAL_CALCULATION_VERSION_V5
# V5 arithmetic read through the episode point/clock resolver binding.
TEMPORAL_CALCULATION_VERSION_EPISODES_V1 = "HFIC_TEMPORAL_DISCOVERY_CALC_EPISODES_V1"
TEMPORAL_CALCULATION_VERSIONS_READABLE = frozenset(
    {
        TEMPORAL_CALCULATION_VERSION_EPISODES_V1,
        TEMPORAL_CALCULATION_VERSION_V1,
        TEMPORAL_CALCULATION_VERSION_V2,
        TEMPORAL_CALCULATION_VERSION_V3,
        TEMPORAL_CALCULATION_VERSION_V4,
        TEMPORAL_CALCULATION_VERSION_V5,
        TEMPORAL_CALCULATION_VERSION,
    }
)
COHORT_CONDITIONAL_SAMPLE_CORRECTION = "COHORT_CONDITIONAL_SAMPLE_V4"
RESULT_COHERENCE_TOLERANCE = 1e-9
DOWNSIDE_PROFILE = "DOWNSIDE_DESCRIPTIVE_V1"
TEMPORAL_CAPABILITY_ID = "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"
OBSERVATION_CLOCK_EVENT_TIME_V1 = "EVENT_TIME_V1"
OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1 = "PROVIDER_REPORTED_SNAPSHOT_V1"
OBSERVATION_CLOCK_POLICIES = frozenset(
    {
        OBSERVATION_CLOCK_EVENT_TIME_V1,
        OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
    }
)
# Versioned read-path interpretation: legacy rows may omit the explicit policy
# column when sealed transport/occurrence lineage already proves snapshot
# semantics under a PROVIDER_REPORTED_SNAPSHOT_V1 query. Never invent clocks
# or hashes; insufficient lineage is SNAPSHOT_LINEAGE_UNINTERPRETABLE.
SNAPSHOT_ROW_INTERPRETATION_V1 = "SNAPSHOT_ROW_INTERPRETATION_V1"
SNAPSHOT_LINEAGE_BLOCKERS = frozenset(
    {
        "SNAPSHOT_POLICY_MISMATCH",
        "SNAPSHOT_OCCURRENCE_UNBOUND",
        "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
        "MISSING_ACQUISITION_CLOCK",
        "CLOCK_ORDER_INVALID",
        "ACQUISITION_BEFORE_POINT_DUE",
        "AVAILABILITY_AFTER_DEADLINE",
        "ACQUISITION_AFTER_CUTOFF",
    }
)
PREVIEW_BYTE_LIMIT = 64 * 1024
PREVIEW_EXAMPLE_LIMIT = 24
MAX_PREVIEW_SPECS = 2
SIMPLE_MAIN_RESERVE = 3
MAX_PREDICATES = 6
MAX_FEATURES = 12
MAX_SCHEDULE_POINTS = 8
ALLOWED_FIELDS = frozenset({PRICE, LIQUIDITY})
HOLDER_COUNT = "FIELD-HOLDER-COUNT-001"
HOLDER_OPS = frozenset({"point_value", "delta", "return_ratio"})
TIERS = frozenset({"SIMPLE_SCREEN", "COMPOUND_SCREEN"})
FEATURE_OPS = frozenset(
    {
        "point_value",
        "delta",
        "ratio",
        "return_ratio",
        "drawdown_from_grid_max",
        "rebound_from_grid_min",
        "elapsed_seconds",
        "utc_hour",
    }
)
COMPARISONS = frozenset({"gt", "gte", "lt", "lte", "between"})


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def is_temporal_query(spec: Mapping[str, Any] | object) -> bool:
    return isinstance(spec, Mapping) and spec.get("schema") == TEMPORAL_SCHEMA


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _point(value: object) -> str:
    if not isinstance(value, str) or value not in POINT_OFFSET:
        raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST")
    return value


def _field(value: object) -> str:
    if value in ALLOWED_FIELDS:
        return str(value)
    text = str(value or "")
    if "VOLUME" in text:
        raise GroundedDiscoveryError("UNSUPPORTED_REQUIREMENT")
    raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")


def _require_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GroundedDiscoveryError(code)
    return value


def default_assumption_stress_profile() -> dict[str, Any]:
    """Design ranges for sensitivity. Not a Solana fee measurement."""

    return {
        "kind": "ASSUMPTION_STRESS_ONLY",
        "source_status": "ASSUMPTION_NOT_CALIBRATED",
        "notional_units": "FRACTION_OF_NOTIONAL",
        "haircut_basis": "MARK_NOT_QUOTE",
        "included_components": ["ROUND_TRIP_HAIRCUT", "EXIT_FAILURE_STRESS", "SEPARATE_CASH_F"],
        "excluded_components": ["LIVE_FEE_SCHEDULE", "OBSERVED_FILL", "INFRASTRUCTURE_OVERHEAD"],
        "scenarios": {
            "LOW": {"h": 0.03, "q": 0.0, "f": 0.0, "r_fail": -1.0},
            "BASE": {"h": 0.10, "q": 0.05, "f": 0.005, "r_fail": -1.0},
            "STRESS": {"h": 0.25, "q": 0.20, "f": 0.020, "r_fail": -1.0},
        },
    }


def _canonical_feature(
    feature: Mapping[str, Any],
    *,
    point_fn: Any = None,
    offset_fn: Any = None,
) -> dict[str, Any]:
    _point_of = point_fn or _point
    _offset_of = offset_fn or (lambda item: POINT_OFFSET[item])
    name = feature.get("name")
    op = feature.get("op")
    if not isinstance(name, str) or not name.strip() or name in {"cohort_id", "mint"}:
        raise GroundedDiscoveryError("FEATURE_INVALID")
    if op not in FEATURE_OPS:
        raise GroundedDiscoveryError("FEATURE_OP_UNSUPPORTED")
    body: dict[str, Any] = {"name": name, "op": op}
    if op in {"point_value", "delta", "ratio", "return_ratio", "drawdown_from_grid_max", "rebound_from_grid_min"}:
        # Field x operator policy is independent of the broad legacy allowlist.
        if feature.get("field_id") == HOLDER_COUNT:
            if op not in HOLDER_OPS:
                raise GroundedDiscoveryError("FEATURE_OP_UNSUPPORTED")
            if op != "point_value" and set(feature) != {"name", "op", "field_id", "start", "end"}:
                raise GroundedDiscoveryError("FEATURE_PARAMETERS_INVALID")
            body["field_id"] = HOLDER_COUNT
        else:
            if op == "delta":
                raise GroundedDiscoveryError("FEATURE_OP_UNSUPPORTED")
            body["field_id"] = _field(feature.get("field_id"))
    if op == "point_value":
        body["point"] = _point_of(feature.get("point"))
    elif op == "ratio":
        body["numerator"] = _point_of(feature.get("numerator"))
        body["denominator"] = _point_of(feature.get("denominator"))
    elif op in {"delta", "return_ratio"}:
        body["start"] = _point_of(feature.get("start"))
        body["end"] = _point_of(feature.get("end"))
        if body["field_id"] == HOLDER_COUNT and _offset_of(body["start"]) >= _offset_of(body["end"]):
            raise GroundedDiscoveryError("FEATURE_WINDOW_INVALID")
    elif op in {"drawdown_from_grid_max", "rebound_from_grid_min"}:
        points = feature.get("points")
        if not isinstance(points, list) or not points:
            raise GroundedDiscoveryError("FEATURE_INVALID")
        body["points"] = [_point_of(item) for item in points]
        body["at"] = _point_of(feature.get("at"))
        if body["at"] not in body["points"]:
            raise GroundedDiscoveryError("FEATURE_INVALID")
    elif op == "elapsed_seconds":
        body["start"] = _point_of(feature.get("start"))
        body["end"] = _point_of(feature.get("end"))
    elif op == "utc_hour":
        body["point"] = _point_of(feature.get("point"))
    return body


def _canonical_predicate(predicate: Mapping[str, Any]) -> dict[str, Any]:
    feature = predicate.get("feature")
    op = predicate.get("op")
    if not isinstance(feature, str) or not feature:
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    if op not in COMPARISONS:
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    if op == "between":
        lower = _finite_number(predicate.get("lower"))
        upper = _finite_number(predicate.get("upper"))
        closed = predicate.get("closed", "left")
        if lower is None or upper is None or not lower < upper or closed != "left":
            raise GroundedDiscoveryError("PREDICATE_INVALID")
        return {"feature": feature, "op": "between", "lower": lower, "upper": upper, "closed": "left"}
    value = _finite_number(predicate.get("value"))
    if value is None:
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    return {"feature": feature, "op": op, "value": value}


def _canonical_cost(profile: object) -> dict[str, Any] | None:
    if profile is None:
        return None
    if not isinstance(profile, Mapping):
        raise GroundedDiscoveryError("COST_PROFILE_INVALID")
    kind = profile.get("kind")
    if kind != "ASSUMPTION_STRESS_ONLY":
        raise GroundedDiscoveryError("COST_PROFILE_INVALID")
    scenarios = profile.get("scenarios")
    if not isinstance(scenarios, Mapping) or set(scenarios) != {"LOW", "BASE", "STRESS"}:
        raise GroundedDiscoveryError("COST_PROFILE_INVALID")
    basis = str(profile.get("haircut_basis") or "MARK_NOT_QUOTE")
    if basis not in {"MARK_NOT_QUOTE", "QUOTE_ALREADY_NET"}:
        raise GroundedDiscoveryError("COST_PROFILE_INVALID")
    canonical_scenarios: dict[str, dict[str, float]] = {}
    for name in ("LOW", "BASE", "STRESS"):
        row = scenarios.get(name)
        if not isinstance(row, Mapping):
            raise GroundedDiscoveryError("COST_PROFILE_INVALID")
        h = _finite_number(row.get("h"))
        q = _finite_number(row.get("q"))
        f = _finite_number(row.get("f"))
        r_fail = _finite_number(row.get("r_fail"))
        if h is None or q is None or f is None or r_fail is None:
            raise GroundedDiscoveryError("COST_PROFILE_INVALID")
        if not 0 <= h < 1 or not 0 <= q <= 1 or f < 0:
            raise GroundedDiscoveryError("COST_PROFILE_INVALID")
        if basis == "QUOTE_ALREADY_NET" and h != 0:
            raise GroundedDiscoveryError("COST_DOUBLE_COUNT")
        canonical_scenarios[name] = {"h": h, "q": q, "f": f, "r_fail": r_fail}
    included = profile.get("included_components")
    excluded = profile.get("excluded_components")
    if not isinstance(included, list) or not isinstance(excluded, list):
        raise GroundedDiscoveryError("COST_PROFILE_INVALID")
    return {
        "kind": "ASSUMPTION_STRESS_ONLY",
        "source_status": "ASSUMPTION_NOT_CALIBRATED",
        "haircut_basis": basis,
        "included_components": sorted(str(item) for item in included),
        "excluded_components": sorted(str(item) for item in excluded),
        "scenarios": canonical_scenarios,
    }


def _collect_points(features: Sequence[Mapping[str, Any]], decision: str, target: Mapping[str, Any]) -> set[str]:
    points = {decision, str(target["reference_point"]), str(target["exit_point"])}
    for feature in features:
        for key in ("point", "start", "end", "numerator", "denominator", "at"):
            if key in feature:
                points.add(str(feature[key]))
        for point in feature.get("points") or []:
            points.add(str(point))
    return points


def _episode_point(value: object) -> str:
    from solana_alpha_lab.factory.opportunity_episodes import (
        OpportunityEpisodeError,
        point_offset,
    )

    if not isinstance(value, str):
        raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST")
    try:
        point_offset(value)
    except OpportunityEpisodeError as exc:
        raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST") from exc
    return value


def _episode_offset(point: str) -> int:
    from solana_alpha_lab.factory.opportunity_episodes import point_offset

    return point_offset(point)


def _episode_scientific_body(spec: Mapping[str, Any]) -> dict[str, Any]:
    """OPPORTUNITY_EPISODES question identity (query 1.1). Never BASE_X."""

    from solana_alpha_lab.factory.opportunity_episodes import (
        SCHEDULE_CONTRACT,
        V1_DENSE_STEP,
        V1_DENSE_UNTIL,
        V1_HOURLY_STEP,
    )

    if spec.get("any") is not None:
        raise GroundedDiscoveryError("OR_NOT_A_PREDICATE")
    if spec.get("population") != EPISODE_POPULATION:
        raise GroundedDiscoveryError("POPULATION_CONTRACT_UNKNOWN")
    if spec.get("anchor_kind") != EPISODE_ANCHOR_KIND:
        raise GroundedDiscoveryError("ANCHOR_KIND_UNKNOWN")
    time_contract = _require_mapping(spec.get("time_contract"), "TIME_CONTRACT_INVALID")
    if (
        time_contract.get("schedule_contract") != SCHEDULE_CONTRACT
        or time_contract.get("time_feature_clock") != EPISODE_TIME_FEATURE_CLOCK
        or set(time_contract) != {"schedule_contract", "time_feature_clock"}
    ):
        raise GroundedDiscoveryError("TIME_CONTRACT_INVALID")
    tier = spec.get("search_tier")
    if tier not in TIERS:
        raise GroundedDiscoveryError("SEARCH_TIER_INVALID")
    query_id = spec.get("query_id")
    if not isinstance(query_id, str) or not query_id.strip():
        raise GroundedDiscoveryError("QUERY_ID_REQUIRED")
    decision = _require_mapping(spec.get("decision"), "DECISION_INVALID")
    decision_point = _episode_point(decision.get("point_id"))
    if decision.get("time_policy") not in (None, "RESOLVER_AVAILABILITY_CUTOFF"):
        raise GroundedDiscoveryError("DECISION_INVALID")
    schedule = _require_mapping(spec.get("schedule") or {}, "SCHEDULE_INVALID")
    if set(schedule) - {"observation_clock_policy"}:
        raise GroundedDiscoveryError("SCHEDULE_INVALID")
    clock_policy = (
        schedule.get("observation_clock_policy")
        or OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
    )
    if clock_policy != OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1:
        raise GroundedDiscoveryError("OBSERVATION_CLOCK_POLICY_INVALID")
    features_in = spec.get("features")
    predicates_in = spec.get("all")
    if not isinstance(features_in, list) or not features_in or len(features_in) > MAX_FEATURES:
        raise GroundedDiscoveryError("FEATURE_INVALID")
    if not isinstance(predicates_in, list) or not predicates_in or len(predicates_in) > MAX_PREDICATES:
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    features = [
        _canonical_feature(
            _require_mapping(item, "FEATURE_INVALID"),
            point_fn=_episode_point,
            offset_fn=_episode_offset,
        )
        for item in features_in
    ]
    names = [item["name"] for item in features]
    if len(names) != len(set(names)) or any(
        name in {"episode_id", "cohort_id", "mint"} for name in names
    ):
        raise GroundedDiscoveryError("FEATURE_INVALID")
    predicates = [
        _canonical_predicate(_require_mapping(item, "PREDICATE_INVALID")) for item in predicates_in
    ]
    if any(item["feature"] not in set(names) for item in predicates):
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    target = _require_mapping(spec.get("target"), "TARGET_INVALID")
    if target.get("kind") != "PRICE_RELATIVE_PROXY":
        raise GroundedDiscoveryError("UNSUPPORTED_REQUIREMENT")
    reference = _episode_point(target.get("reference_point"))
    exit_point = _episode_point(target.get("exit_point"))
    if _field(target.get("field_id")) != PRICE:
        raise GroundedDiscoveryError("TARGET_INVALID")
    entry = _require_mapping(spec.get("entry_model"), "ENTRY_MODEL_INVALID")
    if entry.get("kind") != "LAST_AVAILABLE_MARK_WITH_HAIRCUT":
        raise GroundedDiscoveryError("UNSUPPORTED_REQUIREMENT")
    latency = entry.get("assumed_latency_seconds")
    if isinstance(latency, bool) or not isinstance(latency, int) or latency < 0:
        raise GroundedDiscoveryError("ENTRY_MODEL_INVALID")
    decision_offset = _episode_offset(decision_point)
    if _episode_offset(reference) > decision_offset:
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION")
    # The assigned exit must lie strictly after the decision cutoff for every
    # admission instant: worst cutoff = T0 + decision + grid step + grace.
    decision_step = V1_DENSE_STEP if decision_offset <= V1_DENSE_UNTIL else V1_HOURLY_STEP
    if _episode_offset(exit_point) <= decision_offset + decision_step + 300 + int(latency):
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION_CUTOFF")
    for feature in features:
        used = [
            feature[key]
            for key in ("point", "start", "end", "numerator", "denominator", "at")
            if key in feature
        ]
        used.extend(feature.get("points") or [])
        if any(_episode_offset(str(point)) > decision_offset for point in used):
            raise GroundedDiscoveryError("FEATURE_AFTER_DECISION")
    target_body = {
        "kind": "PRICE_RELATIVE_PROXY",
        "reference_point": reference,
        "exit_point": exit_point,
        "field_id": PRICE,
    }
    if len(_collect_points(features, decision_point, target_body)) > MAX_SCHEDULE_POINTS:
        raise GroundedDiscoveryError("QUERY_TOO_WIDE")
    evaluation = spec.get("evaluation") or {}
    if not isinstance(evaluation, Mapping):
        raise GroundedDiscoveryError("EVALUATION_INVALID")
    allocation = spec.get("budget_allocation") or "AUTO"
    if allocation not in {"AUTO", "COMPOUND_FIRST"}:
        raise GroundedDiscoveryError("BUDGET_ALLOCATION_INVALID")
    return {
        "population": EPISODE_POPULATION,
        "anchor_kind": EPISODE_ANCHOR_KIND,
        "time_contract": {
            "schedule_contract": SCHEDULE_CONTRACT,
            "time_feature_clock": EPISODE_TIME_FEATURE_CLOCK,
        },
        "decision_point": decision_point,
        "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        "features": sorted(features, key=lambda item: str(item["name"])),
        "predicates": sorted(predicates, key=_canonical),
        "target": target_body,
        "entry_model": {
            "kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT",
            "assumed_latency_seconds": latency,
        },
        "cost_profile": _canonical_cost(spec.get("cost_profile")),
        "evaluation": {
            "baseline": str(evaluation.get("baseline") or "SAME_DECISION_ELIGIBLE"),
            "ablations": str(evaluation.get("ablations") or "DROP_ONE_CONDITION"),
            "calendar_block": str(evaluation.get("calendar_block") or "UTC_DAY_OF_DECISION"),
        },
        "query_id": query_id,
        "search_tier": tier,
        "budget_allocation": allocation,
        "adaptation_of": spec.get("adaptation_of") if isinstance(spec.get("adaptation_of"), str) else None,
    }


def is_episode_body(body: Mapping[str, Any] | object) -> bool:
    return isinstance(body, Mapping) and body.get("population") == EPISODE_POPULATION


def scientific_body(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Question identity. Display id, tier and predicate order are not part of it."""

    if not is_temporal_query(spec):
        raise GroundedDiscoveryError("QUERY_SPEC_INVALID")
    if spec.get("schema_version") == TEMPORAL_SCHEMA_VERSION_EPISODES:
        return _episode_scientific_body(spec)
    if spec.get("schema_version") != TEMPORAL_SCHEMA_VERSION:
        raise GroundedDiscoveryError("QUERY_SPEC_INVALID")
    if spec.get("any") is not None:
        raise GroundedDiscoveryError("OR_NOT_A_PREDICATE")
    population = spec.get("population")
    if population != "BASE_X":
        raise GroundedDiscoveryError("POPULATION_NOT_BASE_X")
    tier = spec.get("search_tier")
    if tier not in TIERS:
        raise GroundedDiscoveryError("SEARCH_TIER_INVALID")
    query_id = spec.get("query_id")
    if not isinstance(query_id, str) or not query_id.strip():
        raise GroundedDiscoveryError("QUERY_ID_REQUIRED")
    decision = _require_mapping(spec.get("decision"), "DECISION_INVALID")
    decision_point = _point(decision.get("point_id"))
    if decision.get("time_policy") not in (None, "BOUND_SCHEDULE_CUTOFF"):
        raise GroundedDiscoveryError("DECISION_INVALID")
    schedule = _require_mapping(spec.get("schedule"), "SCHEDULE_INVALID")
    lateness = schedule.get("lateness_seconds")
    if isinstance(lateness, bool) or not isinstance(lateness, int) or lateness < 0:
        raise GroundedDiscoveryError("SCHEDULE_INVALID")
    clock_policy = schedule.get("observation_clock_policy")
    if clock_policy in (None, ""):
        clock_policy = OBSERVATION_CLOCK_EVENT_TIME_V1
    if clock_policy not in OBSERVATION_CLOCK_POLICIES:
        raise GroundedDiscoveryError("OBSERVATION_CLOCK_POLICY_INVALID")
    features_in = spec.get("features")
    predicates_in = spec.get("all")
    if not isinstance(features_in, list) or not features_in or len(features_in) > MAX_FEATURES:
        raise GroundedDiscoveryError("FEATURE_INVALID")
    if not isinstance(predicates_in, list) or not predicates_in or len(predicates_in) > MAX_PREDICATES:
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    features = [_canonical_feature(_require_mapping(item, "FEATURE_INVALID")) for item in features_in]
    names = [item["name"] for item in features]
    if len(names) != len(set(names)):
        raise GroundedDiscoveryError("FEATURE_INVALID")
    predicates = [
        _canonical_predicate(_require_mapping(item, "PREDICATE_INVALID")) for item in predicates_in
    ]
    known = set(names)
    if any(item["feature"] not in known for item in predicates):
        raise GroundedDiscoveryError("PREDICATE_INVALID")
    target = _require_mapping(spec.get("target"), "TARGET_INVALID")
    if target.get("kind") != "PRICE_RELATIVE_PROXY":
        raise GroundedDiscoveryError("UNSUPPORTED_REQUIREMENT")
    reference = _point(target.get("reference_point"))
    exit_point = _point(target.get("exit_point"))
    field_id = _field(target.get("field_id"))
    if field_id != PRICE:
        raise GroundedDiscoveryError("TARGET_INVALID")
    if POINT_OFFSET[reference] > POINT_OFFSET[decision_point]:
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION")
    if POINT_OFFSET[exit_point] <= POINT_OFFSET[decision_point]:
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION")
    for feature in features:
        used = [feature[key] for key in ("point", "start", "end", "numerator", "denominator", "at") if key in feature]
        used.extend(feature.get("points") or [])
        if any(POINT_OFFSET[str(point)] > POINT_OFFSET[decision_point] for point in used):
            raise GroundedDiscoveryError("FEATURE_AFTER_DECISION")
    points = _collect_points(features, decision_point, target)
    if len(points) > MAX_SCHEDULE_POINTS:
        raise GroundedDiscoveryError("QUERY_TOO_WIDE")
    entry = _require_mapping(spec.get("entry_model"), "ENTRY_MODEL_INVALID")
    if entry.get("kind") != "LAST_AVAILABLE_MARK_WITH_HAIRCUT":
        raise GroundedDiscoveryError("UNSUPPORTED_REQUIREMENT")
    latency = entry.get("assumed_latency_seconds")
    if isinstance(latency, bool) or not isinstance(latency, int) or latency < 0:
        raise GroundedDiscoveryError("ENTRY_MODEL_INVALID")
    evaluation = spec.get("evaluation") or {}
    if not isinstance(evaluation, Mapping):
        raise GroundedDiscoveryError("EVALUATION_INVALID")
    allocation = spec.get("budget_allocation") or "AUTO"
    if allocation not in {"AUTO", "COMPOUND_FIRST"}:
        raise GroundedDiscoveryError("BUDGET_ALLOCATION_INVALID")
    return {
        "population": "BASE_X",
        "decision_point": decision_point,
        "schedule_lateness_seconds": lateness,
        "observation_clock_policy": str(clock_policy),
        "features": sorted(features, key=lambda item: str(item["name"])),
        "predicates": sorted(predicates, key=_canonical),
        "target": {
            "kind": "PRICE_RELATIVE_PROXY",
            "reference_point": reference,
            "exit_point": exit_point,
            "field_id": field_id,
        },
        "entry_model": {
            "kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT",
            "assumed_latency_seconds": latency,
        },
        "cost_profile": _canonical_cost(spec.get("cost_profile")),
        "evaluation": {
            "baseline": str(evaluation.get("baseline") or "SAME_DECISION_ELIGIBLE"),
            "ablations": str(evaluation.get("ablations") or "DROP_ONE_CONDITION"),
            "calendar_block": str(evaluation.get("calendar_block") or "UTC_DAY_OF_DECISION"),
        },
        "query_id": query_id,
        "search_tier": tier,
        "budget_allocation": allocation,
        "adaptation_of": spec.get("adaptation_of") if isinstance(spec.get("adaptation_of"), str) else None,
    }


def _validate_episode_temporal_query(body: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        key: body[key]
        for key in body
        if key not in {"query_id", "search_tier", "budget_allocation", "adaptation_of"}
    }
    identity["schema_version"] = TEMPORAL_SCHEMA_VERSION_EPISODES
    digest = _sha256(identity)
    runtime_body = {key: value for key, value in identity.items() if key != "schema_version"}
    return {
        "query_id": body["query_id"],
        "schema_version": TEMPORAL_SCHEMA_VERSION_EPISODES,
        "decision_points": [body["decision_point"]],
        "decision_fields": [PRICE, LIQUIDITY] + (
            [HOLDER_COUNT] if any(f.get("field_id") == HOLDER_COUNT for f in body["features"]) else []
        ),
        "target_point": body["target"]["exit_point"],
        "target_field": PRICE,
        "explanatory": [],
        "population": EPISODE_POPULATION,
        "spec_sha256": digest,
        "target_label": (
            f"PRICE_RELATIVE_PROXY:{runtime_body['target']['reference_point']}:"
            f"{runtime_body['target']['exit_point']}:{runtime_body['target']['field_id']}"
        ),
        "search_tier": body["search_tier"],
        "budget_allocation": body["budget_allocation"],
        "adaptation_of": body["adaptation_of"],
        "scientific_body": runtime_body,
        "display": dict(body),
    }


def validate_temporal_query(spec: Mapping[str, Any]) -> dict[str, Any]:
    body = scientific_body(spec)
    if is_episode_body(body):
        return _validate_episode_temporal_query(body)
    identity = {
        key: body[key]
        for key in body
        if key not in {"query_id", "search_tier", "budget_allocation", "adaptation_of"}
    }
    # Default EVENT_TIME_V1 is omitted from identity so prior frozen digests
    # remain stable; any non-default policy enters scientific identity.
    if identity.get("observation_clock_policy") == OBSERVATION_CLOCK_EVENT_TIME_V1:
        identity = {
            key: value
            for key, value in identity.items()
            if key != "observation_clock_policy"
        }
    digest = _sha256(identity)
    runtime_body = dict(identity)
    runtime_body["observation_clock_policy"] = body["observation_clock_policy"]
    return {
        "query_id": body["query_id"],
        "decision_points": [body["decision_point"]],
        "decision_fields": [PRICE, LIQUIDITY] + (
            [HOLDER_COUNT] if any(f.get("field_id") == HOLDER_COUNT for f in body["features"]) else []
        ),
        "target_point": body["target"]["exit_point"],
        "target_field": PRICE,
        "explanatory": [],
        "population": "BASE_X",
        "spec_sha256": digest,
        "target_label": (
            f"PRICE_RELATIVE_PROXY:{runtime_body['target']['reference_point']}:"
            f"{runtime_body['target']['exit_point']}:{runtime_body['target']['field_id']}"
        ),
        "search_tier": body["search_tier"],
        "budget_allocation": body["budget_allocation"],
        "adaptation_of": body["adaptation_of"],
        "scientific_body": runtime_body,
        "display": body,
    }


def temporal_target_label(spec: Mapping[str, Any]) -> str:
    bound = validate_temporal_query(spec)
    target = bound["scientific_body"]["target"]
    return (
        f"{target['kind']}:{target['reference_point']}:{target['exit_point']}:{target['field_id']}"
    )


def canonical_temporal_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    bound = validate_temporal_query(spec)
    return {
        "schema": TEMPORAL_SCHEMA,
        "schema_version": bound.get("schema_version", TEMPORAL_SCHEMA_VERSION),
        "query_id": bound["query_id"],
        "search_tier": bound["search_tier"],
        "spec_sha256": bound["spec_sha256"],
        "scientific_body": bound["scientific_body"],
        "budget_allocation": bound["budget_allocation"],
        "adaptation_of": bound["adaptation_of"],
    }


def estimate_net_proxy(
    r_mark: float,
    *,
    h: float,
    q: float,
    r_fail: float,
    f: float,
) -> dict[str, float]:
    success = (1.0 + r_mark) * (1.0 - h) - 1.0
    proxy = (1.0 - q) * success + q * r_fail - f
    return {"r_success": success, "estimated_net_proxy": proxy}


def break_even_haircut(
    r_mark: float,
    *,
    q: float,
    f: float,
    r_fail: float = -1.0,
) -> dict[str, Any]:
    """Generalized haircut that zeros the proxy. Not clamped into [0, 1)."""

    denominator = (1.0 - q) * (1.0 + r_mark)
    if denominator == 0:
        return {"applicable": False, "h_break_even": None, "reason": "ZERO_DENOMINATOR"}
    value = 1.0 - ((1.0 - q) - q * r_fail + f) / denominator
    return {
        "applicable": True,
        "h_break_even": value,
        "inside_unit_interval": 0 <= value < 1,
        "reason": "INSIDE_UNIT_INTERVAL" if 0 <= value < 1 else "OUTSIDE_UNIT_INTERVAL",
    }


def _deadline_for(anchor: object, point: str, lateness: int, *, due_offset: int | None = None):
    parsed = _parse_time(anchor)
    if parsed is None:
        return None
    offset = POINT_OFFSET[point] if due_offset is None else due_offset
    return parsed + timedelta(seconds=offset + lateness)


_REGISTERED_PRIMITIVE_IDS: frozenset[str] | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _registered_primitive_ids() -> frozenset[str]:
    global _REGISTERED_PRIMITIVE_IDS
    if _REGISTERED_PRIMITIVE_IDS is not None:
        return _REGISTERED_PRIMITIVE_IDS
    from solana_alpha_lab.factory.observation_primitive_registry import (
        load_observation_primitive_registry,
    )

    registry = load_observation_primitive_registry(_repo_root())
    _REGISTERED_PRIMITIVE_IDS = frozenset(registry.primitives)
    return _REGISTERED_PRIMITIVE_IDS


def _is_hex64(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def stamp_provider_reported_snapshot_transport(
    observations: Sequence[Mapping[str, Any]],
    *,
    primitive_id: str = "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
    include_explicit_policy: bool = True,
    request_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """Stamp fake-transport snapshot lineage onto producer rows before publish.

    New-format corpora set ``observation_clock_policy`` explicitly. Legacy-format
    fixtures may omit the policy column while retaining occurrence/request and
    acquisition clocks so ``SNAPSHOT_ROW_INTERPRETATION_V1`` can derive policy.
    Never invent clocks when availability is already absent.
    """

    stamped: list[dict[str, Any]] = []
    default_request = request_sha256 if _is_hex64(request_sha256) else "dd" * 32
    for row in observations:
        body = dict(row)
        available = body.get("first_reliable_available_at") or body.get("event_time")
        if available not in (None, ""):
            # Producer fake-transport clocks are coherent: request=response=available.
            # Do not preserve pre-stamp request anchors that predate point due.
            body["request_started_at"] = available
            body["response_received_at"] = available
            body["first_reliable_available_at"] = available
        body["primitive_id"] = primitive_id or body.get("primitive_id") or (
            "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        )
        body["call_occurrence_id"] = hashlib.sha256(
            f"{body.get('mint')}:{body.get('point_id')}:{body.get('field_id')}:"
            f"{body.get('first_reliable_available_at')}".encode("utf-8")
        ).hexdigest()
        body["request_sha256"] = default_request
        body.setdefault("source_price_event_time", body.get("source_price_event_time") or "UNKNOWN")
        if include_explicit_policy:
            body["observation_clock_policy"] = (
                OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
            )
        else:
            body.pop("observation_clock_policy", None)
        stamped.append(body)
    return stamped


def _legacy_snapshot_lineage_complete(row: Mapping[str, Any]) -> bool:
    """True when retained transport/occurrence links can prove snapshot semantics."""

    primitive_id = str(row.get("primitive_id") or "")
    return bool(
        primitive_id
        and primitive_id in _registered_primitive_ids()
        and _is_hex64(row.get("call_occurrence_id"))
        and _is_hex64(row.get("request_sha256"))
        and _parse_time(row.get("request_started_at")) is not None
        and _parse_time(row.get("response_received_at")) is not None
        and _parse_time(row.get("first_reliable_available_at")) is not None
    )


def _effective_snapshot_row_policy(
    row: Mapping[str, Any], *, query_policy: str
) -> str | None:
    """Resolve row clock policy for snapshot admission.

    Explicit policy wins. Absent policy under a snapshot query may inherit the
    query policy only when ``SNAPSHOT_ROW_INTERPRETATION_V1`` lineage is
    complete. Otherwise return None (caller emits UNINTERPRETABLE).
    """

    explicit = row.get("observation_clock_policy")
    if explicit not in (None, ""):
        return str(explicit)
    if (
        query_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
        and _legacy_snapshot_lineage_complete(row)
    ):
        return query_policy
    return None


def _snapshot_lineage_reason(
    row: Mapping[str, Any],
    *,
    query_policy: str,
    point_due_at: object | None = None,
    outer_deadline: object | None = None,
) -> str | None:
    """Return exclusion code when snapshot lineage/policy/acquisition fails."""

    row_policy = _effective_snapshot_row_policy(row, query_policy=query_policy)
    if row_policy is None:
        if row.get("observation_clock_policy") in (None, ""):
            return "SNAPSHOT_LINEAGE_UNINTERPRETABLE"
        return "SNAPSHOT_POLICY_MISMATCH"
    if row_policy != query_policy:
        return "SNAPSHOT_POLICY_MISMATCH"
    primitive_id = str(row.get("primitive_id") or "")
    occurrence = str(row.get("call_occurrence_id") or "")
    request_digest = str(row.get("request_sha256") or "")
    if (
        not primitive_id
        or primitive_id not in _registered_primitive_ids()
        or not _is_hex64(occurrence)
        or not _is_hex64(request_digest)
    ):
        return "SNAPSHOT_OCCURRENCE_UNBOUND"
    request = _parse_time(row.get("request_started_at"))
    response = _parse_time(row.get("response_received_at"))
    available = _parse_time(row.get("first_reliable_available_at"))
    if request is None or response is None or available is None:
        return "MISSING_ACQUISITION_CLOCK"
    if not (request <= response <= available):
        return "CLOCK_ORDER_INVALID"
    if point_due_at is not None and request < point_due_at:
        return "ACQUISITION_BEFORE_POINT_DUE"
    if outer_deadline is not None and available > outer_deadline:
        return "AVAILABILITY_AFTER_DEADLINE"
    # Availability claimed inside the outer window must not hide request/response
    # that only arrive after that window (contradictory acquisition clocks).
    if (
        outer_deadline is not None
        and available <= outer_deadline
        and (request > outer_deadline or response > outer_deadline)
    ):
        return "ACQUISITION_AFTER_CUTOFF"
    return None


def _select_cell(rows: Sequence[Mapping[str, Any]], deadline: object) -> dict[str, Any]:
    if deadline is None:
        return {"status": "ABSENT"}
    chosen: list[tuple[object, Mapping[str, Any]]] = []
    for row in rows:
        available = _parse_time(row.get("first_reliable_available_at"))
        if available is None or available > deadline:
            continue
        chosen.append((available, row))
    if not chosen:
        return {"status": "ABSENT"}
    latest = max(item[0] for item in chosen)
    tied = [row for available, row in chosen if available == latest]
    parsed: list[tuple[str, float | None]] = []
    for row in tied:
        if str(row.get("state") or "") != "OBSERVED":
            parsed.append(("MISSING", None))
            continue
        number = _finite_number(row.get("typed_value"))
        if number is None:
            parsed.append(("MISSING", None))
        else:
            parsed.append(("NUM", number))
    if len(set(parsed)) != 1:
        return {"status": "CONFLICT", "available_at": latest}
    kind, number = parsed[0]
    if kind != "NUM" or number is None:
        return {"status": "MISSING", "available_at": latest}
    winner = tied[0]
    return {
        "status": "OBSERVED",
        "value": number,
        "available_at": latest,
        "source_price_event_time": winner.get("source_price_event_time") or "UNKNOWN",
        "primitive_id": winner.get("primitive_id"),
        "call_occurrence_id": winner.get("call_occurrence_id"),
        "request_sha256": winner.get("request_sha256"),
        "observation_clock_policy": winner.get("observation_clock_policy"),
    }


def _select_snapshot_cell(
    rows: Sequence[Mapping[str, Any]],
    *,
    query_policy: str,
    point_due_at: object | None,
    deadline: object,
) -> dict[str, Any]:
    """Availability-bound cell read with snapshot lineage/acquisition checks."""

    if deadline is None:
        return {"status": "ABSENT"}
    legal: list[tuple[object, Mapping[str, Any]]] = []
    seen_reasons: list[str] = []
    for row in rows:
        reason = _snapshot_lineage_reason(
            row,
            query_policy=query_policy,
            point_due_at=point_due_at,
            outer_deadline=deadline,
        )
        if reason is not None:
            seen_reasons.append(reason)
            continue
        available = _parse_time(row.get("first_reliable_available_at"))
        if available is None or available > deadline:
            continue
        if str(row.get("state") or "") != "OBSERVED":
            continue
        legal.append((available, row))
    if not legal:
        for code in (
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
            "SNAPSHOT_POLICY_MISMATCH",
            "SNAPSHOT_OCCURRENCE_UNBOUND",
            "MISSING_ACQUISITION_CLOCK",
            "CLOCK_ORDER_INVALID",
            "ACQUISITION_BEFORE_POINT_DUE",
            "AVAILABILITY_AFTER_DEADLINE",
            "ACQUISITION_AFTER_CUTOFF",
        ):
            if code in seen_reasons:
                return {"status": code}
        return {"status": "ABSENT"}
    return _select_cell([row for _, row in legal], deadline)


def _cell(
    grouped: Mapping[tuple[str, str, str, str, str], Sequence[Mapping[str, Any]]],
    key: tuple[str, str, str, str, str],
    deadline: object,
    *,
    snapshot_policy: str | None = None,
    point_due_at: object | None = None,
) -> dict[str, Any]:
    rows = tuple(grouped.get(key, ()))
    if snapshot_policy:
        return _select_snapshot_cell(
            rows,
            query_policy=snapshot_policy,
            point_due_at=point_due_at,
            deadline=deadline,
        )
    return _select_cell(rows, deadline)


def _predicate_holds(value: float | None, predicate: Mapping[str, Any]) -> bool | None:
    if value is None:
        return None
    op = str(predicate["op"])
    if op == "gt":
        return value > float(predicate["value"])
    if op == "gte":
        return value >= float(predicate["value"])
    if op == "lt":
        return value < float(predicate["value"])
    if op == "lte":
        return value <= float(predicate["value"])
    return float(predicate["lower"]) <= value < float(predicate["upper"])


def _feature_value_with_lineage(
    grouped: Mapping[Any, Sequence[Mapping[str, Any]]],
    *,
    cohort: str,
    release: str,
    mint: str,
    anchor: object,
    feature: Mapping[str, Any],
    lateness: int,
    decision_deadline: object,
    due_offset_for: Any = None,
    lateness_for: Any = None,
    snapshot_policy: str | None = None,
    detail: dict[str, Any] | None = None,
    point_window: Any = None,
    time_clock: str | None = None,
) -> tuple[float | None, str | None]:
    """Return (value, lineage_blocker). Lineage blockers stay visible for fitness.

    ``point_window(point) -> (request_not_before, availability_deadline)`` is
    the OPPORTUNITY_EPISODES resolver binding; ``time_clock`` set to
    ``FIRST_RELIABLE_AVAILABLE_AT`` reads time features from the actual
    availability of the selected PRICE cells. Both default to legacy meaning.
    """

    lineage: str | None = None

    def offset(point: str) -> int | None:
        if due_offset_for is None:
            return None
        return int(due_offset_for(point))

    def point_lateness(point: str) -> int:
        if lateness_for is None:
            return lateness
        return int(lateness_for(point))

    def read(point: str, field: str) -> dict[str, Any]:
        nonlocal lineage
        if point_window is not None:
            point_due_at, point_deadline = point_window(point)
        else:
            due = offset(point)
            point_deadline = _deadline_for(
                anchor, point, point_lateness(point), due_offset=due
            )
            point_due_at = _due_moment(anchor, int(due)) if due is not None else None
        if point_deadline is None or decision_deadline is None or point_deadline > decision_deadline:
            if detail is not None:
                detail.setdefault("reason", "ABSENT")
            return {"status": "ABSENT"}
        cell = _cell(
            grouped,
            (cohort, release, mint, point, field),
            point_deadline,
            snapshot_policy=snapshot_policy,
            point_due_at=point_due_at if snapshot_policy else None,
        )
        status = str(cell.get("status") or "")
        if detail is not None:
            detail.setdefault("sources", []).append({"point": point, "field_id": field, "status": status})
            if status != "OBSERVED":
                detail.setdefault("reason", status or "ABSENT")
        if lineage is None and status in SNAPSHOT_LINEAGE_BLOCKERS:
            lineage = status
        return cell

    op = str(feature["op"])
    if op == "point_value":
        cell = read(str(feature["point"]), str(feature["field_id"]))
        if cell.get("status") != "OBSERVED":
            return None, lineage
        return float(cell["value"]), lineage
    if time_clock == "FIRST_RELIABLE_AVAILABLE_AT" and op in {"utc_hour", "elapsed_seconds"}:
        # Episode interpretation: actual availability of the selected PRICE
        # cells, never the nominal or assigned schedule instant.
        if op == "utc_hour":
            cell = read(str(feature["point"]), PRICE)
            available = _parse_time(cell.get("available_at"))
            if cell.get("status") != "OBSERVED" or available is None:
                return None, lineage
            return float(available.hour), lineage
        start_cell = read(str(feature["start"]), PRICE)
        end_cell = read(str(feature["end"]), PRICE)
        start_at = _parse_time(start_cell.get("available_at"))
        end_at = _parse_time(end_cell.get("available_at"))
        if (
            start_cell.get("status") != "OBSERVED"
            or end_cell.get("status") != "OBSERVED"
            or start_at is None
            or end_at is None
        ):
            return None, lineage
        return float((end_at - start_at).total_seconds()), lineage
    if op == "utc_hour":
        moment = _deadline_for(
            anchor, str(feature["point"]), 0, due_offset=offset(str(feature["point"]))
        )
        if moment is None or decision_deadline is None or moment > decision_deadline:
            return None, lineage
        if read(str(feature["point"]), PRICE).get("status") != "OBSERVED":
            return None, lineage
        return float(moment.hour), lineage
    if op == "elapsed_seconds":
        start = _deadline_for(
            anchor, str(feature["start"]), 0, due_offset=offset(str(feature["start"]))
        )
        end = _deadline_for(
            anchor, str(feature["end"]), 0, due_offset=offset(str(feature["end"]))
        )
        if start is None or end is None:
            return None, lineage
        if read(str(feature["start"]), PRICE).get("status") != "OBSERVED":
            return None, lineage
        if read(str(feature["end"]), PRICE).get("status") != "OBSERVED":
            return None, lineage
        return float((end - start).total_seconds()), lineage
    if op in {"delta", "return_ratio"}:
        start = read(str(feature["start"]), str(feature["field_id"]))
        end = read(str(feature["end"]), str(feature["field_id"]))
        if start.get("status") != "OBSERVED" or end.get("status") != "OBSERVED":
            return None, lineage
        denominator = float(start["value"])
        if op == "delta":
            value = float(end["value"]) - denominator
            if not math.isfinite(value):
                if detail is not None:
                    detail["reason"] = "NONFINITE_RESULT"
                return None, lineage
            return value, lineage
        if denominator <= 0:
            if detail is not None:
                detail["reason"] = "NONPOSITIVE_DENOMINATOR"
            return None, lineage
        value = float(end["value"]) / denominator - 1.0
        if feature.get("field_id") == HOLDER_COUNT and not math.isfinite(value):
            if detail is not None:
                detail["reason"] = "NONFINITE_RESULT"
            return None, lineage
        return value, lineage
    if op == "ratio":
        numerator = read(str(feature["numerator"]), str(feature["field_id"]))
        denominator_cell = read(str(feature["denominator"]), str(feature["field_id"]))
        if numerator.get("status") != "OBSERVED" or denominator_cell.get("status") != "OBSERVED":
            return None, lineage
        denominator = float(denominator_cell["value"])
        if denominator <= 0:
            if detail is not None:
                detail["reason"] = "NONPOSITIVE_DENOMINATOR"
            return None, lineage
        return float(numerator["value"]) / denominator, lineage
    points = [str(item) for item in feature.get("points") or []]
    values: list[float] = []
    for point in points:
        cell = read(point, str(feature["field_id"]))
        if cell.get("status") != "OBSERVED":
            return None, lineage
        values.append(float(cell["value"]))
    at = read(str(feature["at"]), str(feature["field_id"]))
    if at.get("status") != "OBSERVED":
        return None, lineage
    if op == "drawdown_from_grid_max":
        base = max(values)
    else:
        base = min(values)
    if base <= 0:
        if detail is not None:
            detail["reason"] = "NONPOSITIVE_DENOMINATOR"
        return None, lineage
    return float(at["value"]) / base - 1.0, lineage


def _feature_value(
    grouped: Mapping[Any, Sequence[Mapping[str, Any]]],
    *,
    cohort: str,
    release: str,
    mint: str,
    anchor: object,
    feature: Mapping[str, Any],
    lateness: int,
    decision_deadline: object,
    due_offset_for: Any = None,
    lateness_for: Any = None,
    snapshot_policy: str | None = None,
) -> float | None:
    value, _lineage = _feature_value_with_lineage(
        grouped,
        cohort=cohort,
        release=release,
        mint=mint,
        anchor=anchor,
        feature=feature,
        lateness=lateness,
        decision_deadline=decision_deadline,
        due_offset_for=due_offset_for,
        lateness_for=lateness_for,
        snapshot_policy=snapshot_policy,
    )
    return value


def project_schedule_points(document: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    """Read due offset and lateness from the schedule points themselves."""

    points: list[Mapping[str, Any]] = []
    x_point = document.get("x_point")
    if isinstance(x_point, Mapping):
        points.append(x_point)
    for item in document.get("y_points") or []:
        if isinstance(item, Mapping):
            points.append(item)
    lateness: dict[str, int] = {}
    due: dict[str, int] = {}
    for point in points:
        point_id = str(point.get("point_id") or "")
        late = point.get("allowed_lateness_seconds")
        offset = point.get("due_offset_seconds")
        if (
            not point_id
            or isinstance(late, bool)
            or not isinstance(late, int)
            or isinstance(offset, bool)
            or not isinstance(offset, int)
        ):
            raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
        lateness[point_id] = late
        due[point_id] = offset
    if not lateness:
        raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
    return {
        "schedule_point_lateness": lateness,
        "schedule_point_due_offset_seconds": due,
    }


def _query_points(body: Mapping[str, Any]) -> list[str]:
    points = [
        str(body["decision_point"]),
        "X300",
    ]
    if body.get("target"):
        points.extend([str(body["target"]["reference_point"]), str(body["target"]["exit_point"])])
    for feature in body["features"]:
        if not isinstance(feature, Mapping):
            continue
        for key in ("point", "start", "end", "at", "numerator", "denominator"):
            if feature.get(key):
                points.append(str(feature[key]))
        for point in feature.get("points") or []:
            points.append(str(point))
    ordered: list[str] = []
    for point in points:
        if point not in ordered:
            ordered.append(point)
    return ordered


def _clock(item: Mapping[str, Any], point: str, query_lateness: int) -> tuple[int, int]:
    """Document point clocks win. A missing document does not fall back to a default.

    When the bound schedule carries per-point maps, each point uses its own
    ``(due_offset, allowed_lateness)``. The query scalar is a legacy uniform
    contract and is not forced onto mixed point maps.
    """

    gap = item.get("schedule_context_gap")
    if gap == "CANONICAL_SCHEDULE_UNBOUND":
        raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
    if isinstance(gap, str) and gap:
        raise GroundedDiscoveryError(gap)
    lateness_map = item.get("schedule_point_lateness")
    due_map = item.get("schedule_point_due_offset_seconds")
    if isinstance(lateness_map, Mapping) and isinstance(due_map, Mapping) and lateness_map:
        late = lateness_map.get(point)
        due = due_map.get(point)
        if (
            isinstance(late, bool)
            or not isinstance(late, int)
            or isinstance(due, bool)
            or not isinstance(due, int)
        ):
            raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
        # Query scalar remains the X300 envelope. Other points may differ.
        if point == "X300" and late != query_lateness:
            raise GroundedDiscoveryError("SCHEDULE_LATENESS_MISMATCH")
        return due, late
    declared = item.get("schedule_lateness_seconds")
    if isinstance(declared, bool) or not isinstance(declared, int):
        raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
    if declared != query_lateness:
        raise GroundedDiscoveryError("SCHEDULE_LATENESS_MISMATCH")
    if point not in POINT_OFFSET:
        raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
    return POINT_OFFSET[point], declared


def _due_moment(anchor: object, due_offset: int):
    parsed = _parse_time(anchor)
    if parsed is None:
        return None
    return parsed + timedelta(seconds=int(due_offset))


def _select_snapshot_exit(
    exit_rows: Sequence[Mapping[str, Any]],
    *,
    entry_at: object,
    exit_due_at: object,
    exit_deadline: object,
    query_policy: str = OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
) -> tuple[dict[str, Any], str | None]:
    """Select a provider-reported snapshot exit under acquisition clocks.

    Member anchor is not a market-event timestamp. Request must start after
    entry and not before the point due; clocks keep
    ``due ≤ request ≤ response ≤ availability ≤ deadline``.
    Occurrence must bind a registered primitive id plus request/occurrence
    hashes. Known source events that are malformed or stale fail closed.
    """

    if entry_at is None or exit_due_at is None:
        return {"status": "MISSING_ACQUISITION_CLOCK"}, "MISSING_ACQUISITION_CLOCK"
    legal: list[tuple[object, Mapping[str, Any]]] = []
    seen_reasons: list[str] = []
    for exit_row in exit_rows:
        lineage = _snapshot_lineage_reason(
            exit_row,
            query_policy=query_policy,
            point_due_at=exit_due_at,
            outer_deadline=exit_deadline,
        )
        if lineage is not None:
            seen_reasons.append(lineage)
            continue
        request = _parse_time(exit_row.get("request_started_at"))
        response = _parse_time(exit_row.get("response_received_at"))
        available = _parse_time(exit_row.get("first_reliable_available_at"))
        source_event = exit_row.get("source_price_event_time")
        if source_event not in (None, "", "UNKNOWN"):
            source_parsed = _parse_time(source_event)
            if source_parsed is None:
                seen_reasons.append("SOURCE_PRICE_EVENT_MALFORMED")
                continue
            if (
                exit_deadline is None
                or source_parsed > exit_deadline
                or (entry_at is not None and source_parsed <= entry_at)
            ):
                seen_reasons.append("SOURCE_PRICE_EVENT_STALE")
                continue
        if request is None or response is None or available is None:
            seen_reasons.append("MISSING_ACQUISITION_CLOCK")
            continue
        if request <= entry_at:
            seen_reasons.append("REQUEST_NOT_AFTER_ENTRY")
            continue
        if str(exit_row.get("state") or "") != "OBSERVED":
            seen_reasons.append("EXIT_NOT_OBSERVED")
            continue
        legal.append((available, exit_row))
    if not legal:
        if not seen_reasons:
            return {"status": "ABSENT"}, "EXIT_ABSENT"
        preferred = (
            "REQUEST_NOT_AFTER_ENTRY",
            "ACQUISITION_BEFORE_POINT_DUE",
            "ACQUISITION_AFTER_CUTOFF",
            "AVAILABILITY_AFTER_DEADLINE",
            "CLOCK_ORDER_INVALID",
            "SOURCE_PRICE_EVENT_STALE",
            "SOURCE_PRICE_EVENT_MALFORMED",
            "SNAPSHOT_LINEAGE_UNINTERPRETABLE",
            "SNAPSHOT_POLICY_MISMATCH",
            "SNAPSHOT_OCCURRENCE_UNBOUND",
            "MISSING_ACQUISITION_CLOCK",
            "EXIT_NOT_OBSERVED",
            "EXIT_ABSENT",
        )
        for code in preferred:
            if code in seen_reasons:
                return {"status": code}, code
        return {"status": seen_reasons[0]}, seen_reasons[0]
    latest_exit = max(item[0] for item in legal)
    tied_rows = [row for available, row in legal if available == latest_exit]
    selected = _select_cell(tied_rows, latest_exit)
    if selected.get("status") != "OBSERVED":
        return selected, "EXIT_NOT_OBSERVED"
    return selected, None


def _select_event_time_exit(
    exit_rows: Sequence[Mapping[str, Any]],
    *,
    entry_at: object,
    exit_deadline: object,
) -> tuple[dict[str, Any], str | None]:
    """Legacy event-time exit: known event must fall after entry within deadline."""

    legal = []
    for exit_row in exit_rows:
        available = _parse_time(exit_row.get("first_reliable_available_at"))
        if available is None or available <= entry_at:
            continue
        if exit_deadline is not None and available > exit_deadline:
            continue
        legal.append((available, exit_row))
    if not legal:
        return {"status": "ABSENT"}, "EXIT_ABSENT"
    latest_exit = max(item[0] for item in legal)
    tied_rows = [row for available, row in legal if available == latest_exit]
    selected = _select_cell(tied_rows, latest_exit)
    event_times = [
        _parse_time(row.get("event_time")) or _parse_time(row.get("observed_at"))
        for row in tied_rows
    ]
    if any(item is None for item in event_times):
        return {"status": "MISSING_EVENT_TIME"}, "MISSING_EVENT_TIME"
    if len(set(event_times)) != 1:
        return {"status": "EVENT_TIME_CONFLICT"}, "EVENT_TIME_CONFLICT"
    if entry_at is None or event_times[0] <= entry_at or selected.get("status") != "OBSERVED":
        return {"status": "NOT_AFTER_ENTRY"}, "EVENT_NOT_AFTER_ENTRY"
    return selected, None


def _require_bound_schedule(binding: Sequence[Mapping[str, Any]], body: Mapping[str, Any], lateness: int | None) -> None:
    """Preview and evaluation share the verified point clocks. A missing field does not skip the check."""

    if is_episode_body(body):
        # Episode clocks come from the frozen resolver binding of each cohort.
        from solana_alpha_lab.factory.opportunity_episodes import (
            OpportunityEpisodeError,
            require_binding,
        )

        for item in binding:
            if item.get("population") != EPISODE_POPULATION:
                raise GroundedDiscoveryError("POPULATION_BINDING_MISMATCH")
            try:
                require_binding(item.get("schedule_binding"))
            except OpportunityEpisodeError as exc:
                raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND") from exc
        return
    for item in binding:
        for point in _query_points(body):
            _clock(item, point, lateness)
        for feature in body["features"]:
            if feature.get("field_id") == HOLDER_COUNT and feature["op"] in {"delta", "return_ratio"}:
                start = _clock(item, feature["start"], lateness)[0]
                end = _clock(item, feature["end"], lateness)[0]
                decision = _clock(item, body["decision_point"], lateness)[0]
                if not start < end <= decision:
                    raise GroundedDiscoveryError("FEATURE_WINDOW_INVALID")


def _signature_index(observations: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], tuple]:
    """One pass over observations. Later census rows reuse this index."""

    buckets: dict[tuple[str, str, str], list[tuple]] = defaultdict(list)
    for row in observations:
        key = (
            str(row.get("mint") or ""),
            str(row.get("cohort_id") or ""),
            str(row.get("release_id") or ""),
        )
        buckets[key].append(
            (
                str(row.get("point_id") or ""),
                str(row.get("field_id") or ""),
                str(row.get("first_reliable_available_at") or ""),
                str(row.get("request_started_at") or ""),
                str(row.get("response_received_at") or ""),
                str(row.get("source_price_event_time") or ""),
                str(row.get("event_time") or row.get("observed_at") or ""),
                str(row.get("state") or ""),
                str(row.get("typed_value")),
            )
        )
    return {key: tuple(sorted(items)) for key, items in buckets.items()}


def _observation_signature(
    observations: Sequence[Mapping[str, Any]],
    mint: str,
    cohort: str,
    release: str,
) -> tuple:
    items = []
    for row in observations:
        if str(row.get("mint") or "") != mint:
            continue
        if str(row.get("cohort_id") or "") != cohort or str(row.get("release_id") or "") != release:
            continue
        items.append(
            (
                str(row.get("point_id") or ""),
                str(row.get("field_id") or ""),
                str(row.get("first_reliable_available_at") or ""),
                str(row.get("request_started_at") or ""),
                str(row.get("response_received_at") or ""),
                str(row.get("source_price_event_time") or ""),
                str(row.get("event_time") or row.get("observed_at") or ""),
                str(row.get("state") or ""),
                str(row.get("typed_value")),
            )
        )
    return tuple(sorted(items))


def _cohort_view(member: Mapping[str, Any]) -> dict[str, Any]:
    excluded = bool(member.get("integrity_excluded"))
    return {
        "in_base": bool(member.get("in_base")) and not excluded,
        "decision_eligible": bool(member.get("decision_eligible")) and not excluded,
        "matched": bool(member.get("matched")) and not excluded,
        "target_is_observed": bool(member.get("target_is_observed")) and not excluded,
        "target": None if excluded else member.get("target"),
        "target_exclusion": None if excluded else member.get("target_exclusion"),
        "feature_unknown": bool(member.get("feature_unknown")) and not excluded,
        "exclusion": member.get("exclusion"),
        "integrity_excluded": excluded,
        **({"feature_values": member.get("feature_values", {}), "feature_reasons": member["feature_reasons"],
            "universe_status": member.get("universe_status")} if "feature_reasons" in member else {}),
    }


def _note_cohort_membership(
    slots: dict[str, dict[tuple, dict[str, Any]]],
    cohort: str,
    identity: tuple,
    member: Mapping[str, Any],
) -> None:
    """One descriptive seat per cohort and decision.

    A later eligible copy may replace a non-conflicting ineligible seat.
    An integrity conflict stays excluded for the rest of the computation.
    """

    bucket = slots.setdefault(cohort, {})
    view = _cohort_view(member)
    current = bucket.get(identity)
    if current is None:
        bucket[identity] = view
        return
    if view.get("integrity_excluded"):
        bucket[identity] = view
        return
    if current.get("integrity_excluded"):
        return
    if not current.get("in_base") and view.get("in_base"):
        bucket[identity] = view


def _exclude_shared_identity(
    slots: dict[str, dict[tuple, dict[str, Any]]],
    identity: tuple,
) -> None:
    for bucket in slots.values():
        view = bucket.get(identity)
        if view is None:
            continue
        view["integrity_excluded"] = True
        view["in_base"] = False
        view["decision_eligible"] = False
        view["matched"] = False
        view["target_is_observed"] = False
        view["feature_unknown"] = False
        view["target"] = None


def _conditional_sample(
    members: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """The one conditional sample behind pooled, calendar and cohort views.

    Matched members without an integrity exclusion. Observed and missing
    split that set, so observed + missing is always matched. Unmatched
    members never enter a conditional view, whatever their target.
    """

    matched = [
        item for item in members if item.get("matched") and not item.get("integrity_excluded")
    ]
    observed = [
        item for item in matched if item.get("target_is_observed") and item.get("target") is not None
    ]
    missing = [
        item
        for item in matched
        if not (item.get("target_is_observed") and item.get("target") is not None)
    ]
    return matched, observed, missing


def _cohort_rows(
    slots: dict[str, dict[tuple, dict[str, Any]]],
    admitted_ids: Sequence[str],
) -> list[dict[str, Any]]:
    owners: dict[tuple, set[str]] = defaultdict(set)
    for cohort_id, bucket in slots.items():
        for identity, view in bucket.items():
            if view.get("integrity_excluded"):
                continue
            owners[identity].add(cohort_id)
    rows = []
    for cohort_id in admitted_ids:
        bucket = slots.get(cohort_id, {})
        views = list(bucket.values())
        active = [item for item in views if not item.get("integrity_excluded")]
        matched, observed_members, missing = _conditional_sample(active)
        observed = [float(item["target"]) for item in observed_members]
        exclusions: dict[str, int] = defaultdict(int)
        for item in views:
            if item.get("integrity_excluded"):
                exclusions["INTEGRITY_CONFLICT"] += 1
                continue
            reason = item.get("exclusion")
            if isinstance(reason, str) and reason:
                exclusions[reason] += 1
        shared = sum(
            1
            for identity, view in bucket.items()
            if not view.get("integrity_excluded") and len(owners.get(identity, ())) > 1
        )
        target_exclusions: dict[str, int] = defaultdict(int)
        for item in matched:
            reason = item.get("target_exclusion")
            if isinstance(reason, str) and reason and not item.get("target_is_observed"):
                target_exclusions[reason] += 1
        rows.append(
            {
                "view": cohort_id,
                "cohort_id": cohort_id,
                "population_n": sum(1 for item in active if item.get("in_base")),
                "base_x_n": sum(1 for item in active if item.get("in_base")),
                "decision_eligible_n": sum(1 for item in active if item.get("decision_eligible")),
                "matched_n": len(matched),
                "observed_target_n": len(observed),
                "missing_target_n": len(missing),
                "feature_unknown_n": sum(1 for item in active if item.get("feature_unknown")),
                "denominator_base_x": sum(1 for item in active if item.get("in_base")),
                "feature_admissible": sum(1 for item in active if item.get("decision_eligible")),
                "target_observed_after_decision": len(observed),
                "mean_target": _mean(observed),
                "median_target": _median(observed),
                "mean_target_kind": "PRICE_RELATIVE_PROXY",
                "downside": downside_descriptive(observed, missing_n=len(missing)),
                "exclusion_reasons": dict(sorted(exclusions.items())),
                "target_exclusion_reasons": dict(sorted(target_exclusions.items())),
                "independent_replication": False,
                "shared_decision_n": shared,
                "membership": "DESCRIPTIVE_NOT_INDEPENDENT",
            }
        )
    return rows


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def downside_descriptive(values: Sequence[float], *, missing_n: int) -> dict[str, Any]:
    """Fixed return-sign downside profile over one existing observed view."""

    if isinstance(missing_n, bool) or not isinstance(missing_n, int) or missing_n < 0:
        raise GroundedDiscoveryError("DOWNSIDE_SUPPORT_INVALID")
    if any(not math.isfinite(value) for value in values):
        raise GroundedDiscoveryError("TEMPORAL_TARGET_NONFINITE")
    ordered = sorted(values)
    n = len(ordered)
    negative = [-value for value in ordered if value < 0]
    negative_mass = sum(negative)
    count20 = sum(value <= -0.20 for value in ordered)
    count50 = sum(value <= -0.50 for value in ordered)

    def quantile(q: float) -> float | None:
        if not n:
            return None
        h = (n - 1) * q
        j = math.floor(h)
        g = h - j
        return (1 - g) * ordered[j] + g * ordered[min(j + 1, n - 1)]

    k, remainder = divmod(n, 10)
    tail_mass = n / 10 if n else None
    tail_total = sum(ordered[:k])
    if remainder:
        tail_total += (remainder / 10) * ordered[k]
    return {
        "profile": DOWNSIDE_PROFILE,
        "units": "DIMENSIONLESS_PRICE_RATIO_MINUS_ONE",
        "quantile_method": "HYNDMAN_FAN_TYPE_7_LINEAR",
        "es_method": "EMPIRICAL_LOWER_10_FRACTIONAL_MASS",
        "status": "OBSERVED" if n else "NO_OBSERVED_TARGET",
        "observed_n": n,
        "missing_n": missing_n,
        "negative_n": len(negative),
        "zero_n": sum(value == 0 for value in ordered),
        "p05": quantile(0.05),
        "p10": quantile(0.10),
        "p25": quantile(0.25),
        "le_minus_20_n": count20,
        "le_minus_20_rate": count20 / n if n else None,
        "le_minus_50_n": count50,
        "le_minus_50_rate": count50 / n if n else None,
        "es10_return": tail_total / tail_mass if n else None,
        "es10_tail_mass_n": tail_mass,
        "negative_mass": negative_mass if n else None,
        "worst_negative_share": max(negative) / negative_mass if negative_mass else None,
    }


def classify_temporal_look(
    previous: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    bound = validate_temporal_query(spec)
    digest = bound["spec_sha256"]
    tier = str(bound["search_tier"])
    mains = [item for item in previous if item.get("look_class") == "MAIN" and item.get("new_look") is True]
    adaptive = [
        item for item in previous if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True
    ]
    simple_mains = [item for item in mains if item.get("search_tier") == "SIMPLE_SCREEN"]
    compound_mains = [item for item in mains if item.get("search_tier") == "COMPOUND_SCREEN"]
    same_question = [item for item in previous if item.get("spec_sha256") == digest]
    if any(item.get("calculation_version") == TEMPORAL_CALCULATION_VERSION for item in same_question):
        return {
            "query_id": bound["query_id"],
            "spec_sha256": digest,
            "new_look": False,
            "look_class": "RETRY_SAME_BYTES",
            "search_tier": tier,
            "main_count": len(mains),
            "adaptive_count": len(adaptive),
            "simple_main_count": len(simple_mains),
            "compound_main_count": len(compound_mains),
        }
    if same_question:
        return {
            "query_id": bound["query_id"],
            "spec_sha256": digest,
            "new_look": False,
            "look_class": "CALCULATION_REVISION",
            "search_tier": tier,
            "main_count": len(mains),
            "adaptive_count": len(adaptive),
            "simple_main_count": len(simple_mains),
            "compound_main_count": len(compound_mains),
        }
    look_class = "ADAPTIVE" if bound.get("adaptation_of") else "MAIN"
    if (
        look_class == "MAIN"
        and tier == "SIMPLE_SCREEN"
        and bound["budget_allocation"] != "COMPOUND_FIRST"
        and len(simple_mains) >= SIMPLE_MAIN_RESERVE
        and len(compound_mains) == 0
    ):
        raise GroundedDiscoveryError("SIMPLE_BUDGET_RESERVED_FOR_COMPOUND")
    if look_class == "MAIN" and len(mains) >= MAX_MAIN_QUERY_SPECS:
        raise GroundedDiscoveryError("QUERY_MAIN_BUDGET_EXHAUSTED")
    if look_class == "ADAPTIVE" and len(adaptive) >= MAX_ADAPTIVE_REFINEMENTS:
        raise GroundedDiscoveryError("QUERY_ADAPTIVE_BUDGET_EXHAUSTED")
    return {
        "query_id": bound["query_id"],
        "spec_sha256": digest,
        "new_look": True,
        "look_class": look_class,
        "search_tier": tier,
        "main_count": len(mains) + int(look_class == "MAIN"),
        "adaptive_count": len(adaptive) + int(look_class == "ADAPTIVE"),
        "simple_main_count": len(simple_mains) + int(look_class == "MAIN" and tier == "SIMPLE_SCREEN"),
        "compound_main_count": len(compound_mains) + int(look_class == "MAIN" and tier == "COMPOUND_SCREEN"),
    }


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _means_differ(left: object, right: object) -> bool:
    if left is None or right is None:
        return (left is None) != (right is None)
    a = _finite_number(left)
    b = _finite_number(right)
    if a is None or b is None:
        return True
    return abs(a - b) > RESULT_COHERENCE_TOLERANCE * max(1.0, abs(a), abs(b))


def _view_issues(
    view: str,
    row: Mapping[str, Any],
    *,
    observed_key: str,
    matched_key: str | None,
    missing_key: str | None,
    aliases: Sequence[str] = (),
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    observed = _int_or_none(row.get(observed_key))
    if observed is None:
        return issues
    matched = _int_or_none(row.get(matched_key)) if matched_key else None
    missing = _int_or_none(row.get(missing_key)) if missing_key else None
    if matched is not None and missing is not None and observed + missing != matched:
        issues.append(
            {
                "view": view,
                "field": f"{observed_key}+{missing_key}",
                "expected": matched,
                "actual": observed + missing,
            }
        )
    for alias in aliases:
        if alias in row and _int_or_none(row.get(alias)) != observed:
            issues.append({"view": view, "field": alias, "expected": observed, "actual": row.get(alias)})
    if observed == 0 and row.get("mean_target") is not None:
        issues.append({"view": view, "field": "mean_target", "expected": None, "actual": row.get("mean_target")})
    if observed > 0 and "mean_target" in row and row.get("mean_target") is None:
        issues.append({"view": view, "field": "mean_target", "expected": "NUMBER", "actual": None})
    return issues


def _downside_issues(
    view: str,
    row: Mapping[str, Any],
    *,
    observed_key: str,
    missing_key: str | None = None,
) -> list[dict[str, Any]]:
    block = row.get("downside")
    issues: list[dict[str, Any]] = []

    def issue(field: str, expected: object, actual: object) -> None:
        issues.append({"view": view, "field": f"downside.{field}", "expected": expected, "actual": actual})

    def number(value: object) -> float | None:
        # Stored V5 statistics are JSON numbers, never string coercions.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return _finite_number(value)

    if not isinstance(block, Mapping):
        issue("block", "DOWNSIDE_DESCRIPTIVE_V1", block)
        return issues
    for field, expected in (
        ("profile", DOWNSIDE_PROFILE),
        ("units", "DIMENSIONLESS_PRICE_RATIO_MINUS_ONE"),
        ("quantile_method", "HYNDMAN_FAN_TYPE_7_LINEAR"),
        ("es_method", "EMPIRICAL_LOWER_10_FRACTIONAL_MASS"),
    ):
        if block.get(field) != expected:
            issue(field, expected, block.get(field))
    n = _int_or_none(block.get("observed_n"))
    m = _int_or_none(block.get("missing_n"))
    if n is None or n < 0 or n != _int_or_none(row.get(observed_key)):
        issue("observed_n", row.get(observed_key), block.get("observed_n"))
        return issues
    if m is None or m < 0:
        issue("missing_n", "NONNEGATIVE_INT", block.get("missing_n"))
    elif missing_key and m != _int_or_none(row.get(missing_key)):
        issue("missing_n", row.get(missing_key), m)
    counts = {}
    for field in ("negative_n", "zero_n", "le_minus_20_n", "le_minus_50_n"):
        value = _int_or_none(block.get(field))
        if value is None or not 0 <= value <= n:
            issue(field, f"INT_0_TO_{n}", block.get(field))
        else:
            counts[field] = value
    if len(counts) == 4:
        if not 0 <= counts["le_minus_50_n"] <= counts["le_minus_20_n"] <= counts["negative_n"] <= n:
            issue("event_counts", "k50<=k20<=negative_n<=observed_n", counts)
        if counts["negative_n"] + counts["zero_n"] > n:
            issue("zero_n", f"<= {n - counts['negative_n']}", counts["zero_n"])
    for count_field, rate_field in (
        ("le_minus_20_n", "le_minus_20_rate"),
        ("le_minus_50_n", "le_minus_50_rate"),
    ):
        actual = block.get(rate_field)
        expected = counts[count_field] / n if n and count_field in counts else None
        if expected is None:
            if actual is not None:
                issue(rate_field, None, actual)
        elif number(actual) is None or _means_differ(actual, expected):
            issue(rate_field, expected, actual)
    numeric_fields = ("p05", "p10", "p25", "es10_return", "es10_tail_mass_n")
    if n == 0:
        if block.get("status") != "NO_OBSERVED_TARGET":
            issue("status", "NO_OBSERVED_TARGET", block.get("status"))
        for field in (*numeric_fields, "worst_negative_share"):
            if block.get(field) is not None:
                issue(field, None, block.get(field))
    else:
        if block.get("status") != "OBSERVED":
            issue("status", "OBSERVED", block.get("status"))
        for field in numeric_fields:
            if number(block.get(field)) is None:
                issue(field, "FINITE_NUMBER", block.get(field))
        q = [number(block.get(field)) for field in ("p05", "p10", "p25")]
        if all(value is not None for value in q) and q != sorted(q):
            issue("quantiles", "p05<=p10<=p25", q)
        if _means_differ(block.get("es10_tail_mass_n"), n / 10):
            issue("es10_tail_mass_n", n / 10, block.get("es10_tail_mass_n"))
    median = row.get("median_target")
    if (n == 0 and median is not None) or (n > 0 and number(median) is None):
        issue("median_target", None if n == 0 else "FINITE_NUMBER", median)
    mass = number(block.get("negative_mass"))
    if n == 0:
        if block.get("negative_mass") is not None:
            issue("negative_mass", None, block.get("negative_mass"))
    elif mass is None or mass < 0:
        issue("negative_mass", "NONNEGATIVE_FINITE", block.get("negative_mass"))
    elif mass == 0:
        if counts.get("negative_n", 0) != 0:
            issue("negative_mass", "POSITIVE_WHEN_NEGATIVE_N", mass)
        if block.get("worst_negative_share") is not None:
            issue("worst_negative_share", None, block.get("worst_negative_share"))
    else:
        share = number(block.get("worst_negative_share"))
        if counts.get("negative_n", 0) == 0 or share is None or not 0 < share <= 1:
            issue("worst_negative_share", "FINITE_0_TO_1", block.get("worst_negative_share"))
    return issues


def temporal_result_coherence(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Do the stored conditional views read one matched, observed sample?

    Checks only fields the summary carries, so an older compact summary is
    read as it is. Passing does not prove the old calculation right in every
    other respect.
    """

    issues: list[dict[str, Any]] = []
    pooled_observed = _int_or_none(summary.get("observed_target_n"))
    pooled_mean = summary.get("mean_target")
    issues.extend(
        _view_issues(
            "summary",
            summary,
            observed_key="observed_target_n",
            matched_key="matched_n",
            missing_key="missing_target_n",
            aliases=("later_target_observed_n",),
        )
    )
    pooled = summary.get("pooled")
    if isinstance(pooled, Mapping) and pooled_observed is not None:
        if (
            "target_observed_after_decision" in pooled
            and _int_or_none(pooled.get("target_observed_after_decision")) != pooled_observed
        ):
            issues.append(
                {
                    "view": "pooled",
                    "field": "target_observed_after_decision",
                    "expected": pooled_observed,
                    "actual": pooled.get("target_observed_after_decision"),
                }
            )
        if "mean_target" in pooled and _means_differ(pooled.get("mean_target"), pooled_mean):
            issues.append(
                {"view": "pooled", "field": "mean_target", "expected": pooled_mean, "actual": pooled.get("mean_target")}
            )
    blocks = summary.get("by_calendar_block")
    if isinstance(blocks, list) and pooled_observed is not None:
        total = 0
        weighted = 0.0
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            label = f"by_calendar_block:{block.get('view')}"
            issues.extend(_view_issues(label, block, observed_key="observed_n", matched_key=None, missing_key=None))
            count = _int_or_none(block.get("observed_n")) or 0
            total += count
            mean = _finite_number(block.get("mean_target"))
            if count and mean is not None:
                weighted += mean * count
        if total != pooled_observed:
            issues.append(
                {"view": "by_calendar_block", "field": "observed_n_sum", "expected": pooled_observed, "actual": total}
            )
        elif total and _means_differ(weighted / total, pooled_mean):
            issues.append(
                {
                    "view": "by_calendar_block",
                    "field": "weighted_mean_target",
                    "expected": pooled_mean,
                    "actual": weighted / total,
                }
            )
    cohorts = summary.get("by_cohort")
    if isinstance(cohorts, list) and pooled_observed is not None:
        rows = [row for row in cohorts if isinstance(row, Mapping)]
        disjoint = all((_int_or_none(row.get("shared_decision_n")) or 0) == 0 for row in rows)
        sums = {"observed_target_n": 0, "matched_n": 0, "missing_target_n": 0}
        weighted = 0.0
        for row in rows:
            label = f"by_cohort:{row.get('cohort_id')}"
            issues.extend(
                _view_issues(
                    label,
                    row,
                    observed_key="observed_target_n",
                    matched_key="matched_n",
                    missing_key="missing_target_n",
                    aliases=("target_observed_after_decision",),
                )
            )
            observed = _int_or_none(row.get("observed_target_n")) or 0
            if observed > pooled_observed:
                issues.append(
                    {"view": label, "field": "observed_target_n", "expected": f"<={pooled_observed}", "actual": observed}
                )
            for key in sums:
                sums[key] += _int_or_none(row.get(key)) or 0
            mean = _finite_number(row.get("mean_target"))
            if observed and mean is not None:
                weighted += mean * observed
        if rows and disjoint:
            for key, total in sums.items():
                expected = _int_or_none(summary.get(key))
                if expected is not None and total != expected:
                    issues.append({"view": "by_cohort", "field": f"{key}_sum", "expected": expected, "actual": total})
            if sums["observed_target_n"] == pooled_observed and pooled_observed and _means_differ(
                weighted / pooled_observed, pooled_mean
            ):
                issues.append(
                    {
                        "view": "by_cohort",
                        "field": "weighted_mean_target",
                        "expected": pooled_mean,
                        "actual": weighted / pooled_observed,
                    }
                )
        elif rows and sums["observed_target_n"] < pooled_observed:
            # With overlap each unique decision sits in at least one cohort.
            issues.append(
                {
                    "view": "by_cohort",
                    "field": "observed_target_n_sum",
                    "expected": f">={pooled_observed}",
                    "actual": sums["observed_target_n"],
                }
            )
    if summary.get("calculation_version") in {
        TEMPORAL_CALCULATION_VERSION_V5,
        TEMPORAL_CALCULATION_VERSION_EPISODES_V1,
    }:
        issues.extend(
            _downside_issues(
                "summary", summary,
                observed_key="observed_target_n", missing_key="missing_target_n",
            )
        )
        if isinstance(pooled, Mapping):
            issues.extend(_downside_issues("pooled", pooled, observed_key="target_observed_after_decision"))
            if pooled.get("downside") != summary.get("downside"):
                issues.append({"view": "pooled", "field": "downside", "expected": "SUMMARY_ALIAS", "actual": pooled.get("downside")})
        else:
            issues.append({"view": "pooled", "field": "downside", "expected": "VIEW", "actual": pooled})
        baseline = summary.get("baseline")
        if isinstance(baseline, Mapping):
            issues.extend(_downside_issues("baseline", baseline, observed_key="observed_n"))
        else:
            issues.append({"view": "baseline", "field": "downside", "expected": "VIEW", "actual": baseline})
        for field in ("ablations", "by_calendar_block", "by_cohort"):
            rows = summary.get(field)
            if not isinstance(rows, list):
                issues.append({"view": field, "field": "downside", "expected": "VIEW_LIST", "actual": rows})
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    issues.append({"view": field, "field": "row", "expected": "VIEW", "actual": index})
                    continue
                observed_key = "observed_target_n" if field == "by_cohort" else "observed_n"
                issues.extend(
                    _downside_issues(
                        f"{field}:{row.get('view', index)}", row,
                        observed_key=observed_key,
                        missing_key="missing_target_n" if field == "by_cohort" else None,
                    )
                )
        if isinstance(blocks, list):
            block_missing = sum(
                (row.get("downside") or {}).get("missing_n", 0)
                for row in blocks if isinstance(row, Mapping) and isinstance(row.get("downside"), Mapping)
                and isinstance(row["downside"].get("missing_n"), int)
            )
            if block_missing != summary.get("missing_target_n"):
                issues.append({"view": "by_calendar_block", "field": "downside.missing_n_sum", "expected": summary.get("missing_target_n"), "actual": block_missing})
    return {
        "status": "INCOHERENT" if issues else "COHERENT",
        # COHERENT means no stored view contradicts another; absent fields are not checked.
        "basis": "STORED_FIELDS_ONLY",
        "issues": issues,
        "repair_action": "CALCULATION_REVISION" if issues else None,
    }


def require_coherent_temporal_result(summary: Mapping[str, Any]) -> None:
    if temporal_result_coherence(summary)["status"] != "COHERENT":
        raise GroundedDiscoveryError("TEMPORAL_RESULT_INCOHERENT")


def saved_downside_revision(
    looks: Sequence[Mapping[str, Any]], correction: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    """Read this atom's exact saved V5 revision independently of the writer."""

    for look in reversed(looks):
        lineage = look.get("revision_of")
        if not isinstance(lineage, Mapping):
            continue
        reason = lineage.get("reason")
        if (
            look.get("calculation_version") == TEMPORAL_CALCULATION_VERSION_V5
            and lineage.get("calculation_version") == TEMPORAL_CALCULATION_VERSION_V4
            and lineage.get("record_id") == correction.get("source_result_ref")
            and lineage.get("result_sha256") == correction.get("source_result_sha256")
            and isinstance(reason, Mapping)
            and reason.get("code") == "DOWNSIDE_READOUT_ADDED"
        ):
            return look
    return None


def verify_calculation_revision_source(
    looks: Sequence[Mapping[str, Any]],
    *,
    correction: Mapping[str, Any],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]] | None = None,
    operation_sha256: str | None = None,
    target_calculation_version: str | None = None,
) -> Mapping[str, Any]:
    """Bind one explicit correction to one saved look of the same question.

    A caller flag alone is not a revision. The source must be this journal's
    look with the given ref and hash, the same spec and operation, an older
    readable calculation version, and, when the binding is known, the same
    frozen input and per-point clocks.
    """

    ref = str(correction.get("source_result_ref") or "")
    digest = str(correction.get("source_result_sha256") or "")
    if not ref or not _is_hex64(digest):
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_REQUIRED")
    source = next((item for item in looks if str(item.get("record_id") or "") == ref), None)
    if source is None or not isinstance(source.get("result"), Mapping):
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_NOT_FOUND")
    if source.get("result_sha256") != digest or _sha256(source["result"]) != digest:
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_HASH_MISMATCH")
    bound = validate_temporal_query(spec)
    if source.get("spec_sha256") != bound["spec_sha256"]:
        raise GroundedDiscoveryError("CALCULATION_REVISION_SPEC_MISMATCH")
    owner = source.get("operation_sha256")
    if operation_sha256 and owner and owner != operation_sha256:
        raise GroundedDiscoveryError("CALCULATION_REVISION_OPERATION_MISMATCH")
    version = source.get("calculation_version")
    target_version = target_calculation_version or TEMPORAL_CALCULATION_VERSION
    if version == TEMPORAL_CALCULATION_VERSION_V4 and target_version != TEMPORAL_CALCULATION_VERSION_V5:
        raise GroundedDiscoveryError("CALCULATION_REVISION_UNSUPPORTED")
    if version == target_version:
        raise GroundedDiscoveryError("CALCULATION_REVISION_NOT_REQUIRED")
    if version not in TEMPORAL_CALCULATION_VERSIONS_READABLE:
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_UNREADABLE")
    if version == TEMPORAL_CALCULATION_VERSION_V4 and (
        temporal_result_coherence(source["result"])["status"] != "COHERENT"
        or source["result"].get("technical_failure") is True
        or source["result"].get("technical_stop") is not None
    ):
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_UNSAFE")
    recipe = source["result"].get("experiment_recipe")
    if not isinstance(recipe, Mapping) or not isinstance(recipe.get("frozen_input"), list):
        raise GroundedDiscoveryError("CALCULATION_REVISION_SOURCE_UNVERIFIABLE")
    if recipe.get("spec") != canonical_temporal_spec(spec):
        raise GroundedDiscoveryError("CALCULATION_REVISION_SPEC_MISMATCH")
    if binding is not None and list(recipe["frozen_input"]) != temporal_frozen_input(binding):
        raise GroundedDiscoveryError("CALCULATION_REVISION_INPUT_MISMATCH")
    return source


def assert_downside_revision_preserves_v4(
    source: Mapping[str, Any], candidate: Mapping[str, Any]
) -> None:
    """Check every stored V4 field before an output-only V5 append."""

    if source.get("calculation_version") != TEMPORAL_CALCULATION_VERSION_V4:
        return
    if candidate.get("calculation_version") != TEMPORAL_CALCULATION_VERSION_V5:
        raise GroundedDiscoveryError("CALCULATION_REVISION_UNSUPPORTED")

    def equal_old(left: Any, right: Any, path: tuple[str, ...] = ()) -> bool:
        if isinstance(left, Mapping):
            if not isinstance(right, Mapping):
                return False
            return all(
                key in right and (
                    path == () and key == "calculation_version"
                    or equal_old(value, right[key], (*path, str(key)))
                )
                for key, value in left.items()
            )
        if isinstance(left, list):
            if not isinstance(right, list):
                return False
            if path == ("viewed_variants",):
                return right == [*left, DOWNSIDE_PROFILE]
            if path == ("by_calendar_block",):
                old_views = {str(row.get("view")) for row in left if isinstance(row, Mapping)}
                indexed = {str(row.get("view")): row for row in right if isinstance(row, Mapping)}
                if len(indexed) != len(right):
                    return False
                for row in right:
                    if str(row.get("view")) not in old_views and row.get("observed_n") != 0:
                        return False
                return all(
                    isinstance(row, Mapping)
                    and str(row.get("view")) in indexed
                    and equal_old(row, indexed[str(row.get("view"))], (*path, str(row.get("view"))))
                    for row in left
                )
            return len(left) == len(right) and all(
                equal_old(a, b, (*path, str(i))) for i, (a, b) in enumerate(zip(left, right, strict=True))
            )
        return type(left) is type(right) and left == right

    if not equal_old(source, candidate):
        raise GroundedDiscoveryError("CALCULATION_REVISION_OLD_NUMERIC_CHANGED")


def calculation_revision_reason(source_result: Mapping[str, Any]) -> dict[str, Any]:
    """Why a revision was written: the exact incoherent fields, or a version change."""

    coherence = temporal_result_coherence(source_result)
    if coherence["status"] == "INCOHERENT":
        return {
            "code": COHORT_CONDITIONAL_SAMPLE_CORRECTION,
            "source_coherence": "INCOHERENT",
            "source_issue_fields": sorted({f"{item['view']}.{item['field']}" for item in coherence["issues"]}),
        }
    if source_result.get("calculation_version") == TEMPORAL_CALCULATION_VERSION_V4:
        return {
            "code": "DOWNSIDE_READOUT_ADDED",
            "source_coherence": "COHERENT",
            "source_issue_fields": [],
        }
    return {
        "code": "CALCULATION_VERSION_SUPERSEDED",
        "source_coherence": "COHERENT",
        "source_issue_fields": [],
    }


def technical_stop_record(code: str) -> dict[str, Any]:
    return {
        "terminal": "TECHNICAL_STOP",
        "reason_code": code,
        "scientific_negative": False,
        "technical_failure": True,
        "raw_corpus_negative": False,
    }


def snapshot_input_technical_stop(summary: Mapping[str, Any]) -> dict[str, Any] | None:
    """Recoverable metadata/data stop when snapshot input is wholly uninterpretable.

    Predicate fitness and matched-outcome fitness are separate:

    - Required cells for forming population / evaluating predicates (X300,
      decision, features) decide whether the eligible scope is interpretable.
    - Outcome cells (reference/exit) decide fitness only for the matched scope.
      Unmatched exit/reference lineage must not convert a valid zero-match into
      a technical stop.

    Partial lineage misses stay as exclusions. Interpretable zero-match
    (population formed; predicates evaluated false) is not a technical stop.
    Excluded census members (e.g. NOT_X_ELIGIBLE) do not decide fitness of the
    eligible scientific scope.
    """

    if int(summary.get("observed_target_n") or 0) > 0:
        return None
    membership = {
        str(code): int(count or 0)
        for code, count in dict(summary.get("exclusion_reasons") or {}).items()
        if int(count or 0) > 0
    }
    target_pooled = {
        str(code): int(count or 0)
        for code, count in dict(
            (summary.get("target_exclusion_reasons") or {}).get("pooled") or {}
        ).items()
        if int(count or 0) > 0
    }
    lineage_membership = {
        code: count
        for code, count in membership.items()
        if code in SNAPSHOT_LINEAGE_BLOCKERS
    }
    lineage_targets = {
        code: count
        for code, count in target_pooled.items()
        if code in SNAPSHOT_LINEAGE_BLOCKERS
    }
    other_targets = {
        code: count
        for code, count in target_pooled.items()
        if code not in SNAPSHOT_LINEAGE_BLOCKERS
    }
    population_n = int(summary.get("population_n") or 0)
    decision_eligible_n = int(summary.get("decision_eligible_n") or 0)
    matched_n = int(summary.get("matched_n") or 0)
    feature_unknown_n = int(summary.get("feature_unknown_n") or 0)
    if population_n == 0:
        # Predicate fitness: no base population. Lineage among census attempts
        # is a technical stop; companion scientific membership (e.g. PIT) must
        # not cancel it — same principle as eligible feature-unknown.
        if lineage_membership:
            primary = sorted(lineage_membership)[0]
            return technical_stop_record(primary)
        return None
    # Predicate fitness: base population formed but no decision-eligible path.
    # Lineage on the decision path is authoritative; companion non-eligible
    # scientific membership must not cancel this stop.
    if decision_eligible_n == 0:
        if lineage_membership:
            primary = sorted(lineage_membership)[0]
            return technical_stop_record(primary)
        return None
    # Predicate fitness: every decision-eligible member has uninterpretable
    # required feature cells (feature_unknown), so predicates cannot be judged.
    # Companion non-eligible membership codes must not cancel this stop — only
    # the eligible feature-unknown bag decides predicate interpretability.
    if (
        matched_n == 0
        and feature_unknown_n >= decision_eligible_n
        and lineage_membership
    ):
        primary = sorted(lineage_membership)[0]
        return technical_stop_record(primary)
    # Valid zero-match / partial cohort: predicates were interpretable enough
    # to leave unmatched members. Do not consult unmatched outcome lineage.
    if matched_n == 0:
        return None
    # Matched-outcome fitness: matched scope exists but every missing target is
    # a lineage blocker (no scientific TARGET_UNOBSERVED / REFERENCE_NOT_AVAILABLE).
    if lineage_targets and not other_targets:
        primary = sorted(lineage_targets)[0]
        return technical_stop_record(primary)
    return None


def look_counts_toward_scientific_search(item: Mapping[str, Any]) -> bool:
    """Technical/metadata-only looks must not authorize SEARCH_EXHAUSTED."""

    if item.get("new_look") is not True:
        return False
    result = item.get("result")
    if not isinstance(result, Mapping) or not result:
        # Opaque or empty look payloads must not credit scientific search.
        return False
    if result.get("technical_failure") is True:
        return False
    stop = result.get("technical_stop")
    if isinstance(stop, Mapping) and stop.get("technical_failure") is True:
        return False
    if snapshot_input_technical_stop(result) is not None:
        return False
    # A stamped discovery summary carries at least one fitness/denominator field.
    # Do not treat a lone technical_stop key as fitness proof — malformed
    # {"technical_stop": null} must not credit scientific search.
    if not any(
        key in result
        for key in (
            "population_n",
            "observed_target_n",
            "decision_eligible_n",
            "exclusion_reasons",
            "calculation_version",
        )
    ):
        return False
    return True


def look_revision_root(item: Mapping[str, Any]) -> str:
    """The attempt a look belongs to: its own record, or the one it revises."""

    lineage = item.get("revision_of")
    if isinstance(lineage, Mapping):
        root = str(lineage.get("root_record_id") or lineage.get("record_id") or "")
        if root:
            return root
    return str(item.get("record_id") or "")


def current_look_evidence(
    look: Mapping[str, Any],
    looks: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Newest evidence for one attempt: a current-version revision, else the look."""

    root = look_revision_root(look)
    if not root:
        return look
    family = [
        item
        for item in looks
        if look_revision_root(item) == root and isinstance(item.get("result"), Mapping)
    ]
    current = [item for item in family if item.get("calculation_version") == TEMPORAL_CALCULATION_VERSION]
    if current:
        return current[-1]
    revisions = [item for item in family if isinstance(item.get("revision_of"), Mapping)]
    return revisions[-1] if revisions else look


def look_evidence_is_science_ready(
    look: Mapping[str, Any],
    looks: Sequence[Mapping[str, Any]],
) -> bool:
    """Spend and fitness differ. A spent look is ready only on coherent evidence."""

    result = current_look_evidence(look, looks).get("result")
    return isinstance(result, Mapping) and temporal_result_coherence(result)["status"] == "COHERENT"


def assess_tier_progress(
    looks: Sequence[Mapping[str, Any]],
    *,
    freeze_worthy: bool,
    compound_applicable: bool = True,
) -> dict[str, Any]:
    """Pre-freeze tier state. A skipped compound tier is not an executed search.

    A spent look stays spent. Its evidence authorizes a tier terminal only
    when the look, or its calculation revision, is coherent.
    """

    simple = [
        item
        for item in looks
        if look_counts_toward_scientific_search(item)
        and item.get("search_tier") == "SIMPLE_SCREEN"
    ]
    compound = [
        item
        for item in looks
        if look_counts_toward_scientific_search(item)
        and item.get("search_tier") == "COMPOUND_SCREEN"
    ]
    technical_attempts = [
        item
        for item in looks
        if item.get("new_look") is True
        and not look_counts_toward_scientific_search(item)
    ]
    simple_ready = [item for item in simple if look_evidence_is_science_ready(item, looks)]
    compound_ready = [item for item in compound if look_evidence_is_science_ready(item, looks)]
    # Any spent look on unfit evidence is an unknown; one coherent sibling
    # does not let the search close over it.
    revision_required = len(simple_ready) < len(simple) or len(compound_ready) < len(compound)
    if revision_required:
        # A wrong saved summary justifies neither a terminal nor escalation.
        status = "TECHNICAL_BLOCKED"
        action = "CORRECT_CALCULATION_REVISION"
    elif not compound_applicable:
        # Compound N/A may close search only after scientific simple evidence.
        # Technical/metadata-only looks must not authorize SEARCH_EXHAUSTED via
        # the SKIPPED_INAPPLICABLE shortcut.
        if simple:
            status = "SKIPPED_INAPPLICABLE"
            action = "READY_TO_FREEZE"
        elif technical_attempts:
            status = "TECHNICAL_BLOCKED"
            action = "STOP_TECHNICAL_INPUT"
        else:
            status = "SKIPPED_INAPPLICABLE"
            action = "READY_TO_FREEZE"
    elif compound:
        status = "EXECUTED"
        action = "READY_TO_FREEZE"
    elif freeze_worthy and simple:
        status = "SKIPPED_WITH_WORTHY_SIMPLE"
        action = "READY_TO_FREEZE"
    elif not simple and not compound:
        if technical_attempts:
            status = "TECHNICAL_BLOCKED"
            action = "STOP_TECHNICAL_INPUT"
        else:
            status = "NOT_STARTED"
            action = "RUN_SIMPLE_OR_COMPOUND"
    else:
        mains = [
            item
            for item in looks
            if item.get("look_class") == "MAIN" and item.get("new_look") is True
        ]
        if len(mains) >= MAX_MAIN_QUERY_SPECS:
            status = "SKIPPED_BUDGET"
            action = "STOP_BUDGET"
        else:
            status = "NOT_STARTED"
            action = "ESCALATE_COMPOUND"
    exhausted_allowed = status in {"EXECUTED", "SKIPPED_INAPPLICABLE"}
    return {
        "action": action,
        "compound_status": status,
        "compound_executed": status == "EXECUTED",
        "simple_executed": bool(simple),
        "evidence_revision_required": revision_required,
        "search_exhausted_allowed": exhausted_allowed,
        "freeze_worthy": freeze_worthy,
    }


def assert_search_exhaustion_claim(progress: Mapping[str, Any], *, claim_search_exhausted: bool) -> None:
    if claim_search_exhausted and progress.get("search_exhausted_allowed") is not True:
        raise GroundedDiscoveryError("SEARCH_EXHAUSTED_WITHOUT_COMPOUND")


def _cost_views(r_mark: float | None, profile: Mapping[str, Any] | None) -> dict[str, Any]:
    if r_mark is None or profile is None:
        return {
            "status": "ABSENT",
            "source_status": None if profile is None else profile.get("source_status"),
            "scenarios": {},
            "decision_sensitivity": "NOT_EVALUATED",
            "labeled_net_return": False,
        }
    scenarios: dict[str, Any] = {}
    proxies: list[float] = []
    for name in ("LOW", "BASE", "STRESS"):
        row = profile["scenarios"][name]
        estimated = estimate_net_proxy(
            r_mark,
            h=float(row["h"]),
            q=float(row["q"]),
            r_fail=float(row["r_fail"]),
            f=float(row["f"]),
        )
        edge = break_even_haircut(
            r_mark,
            q=float(row["q"]),
            f=float(row["f"]),
            r_fail=float(row["r_fail"]),
        )
        scenarios[name] = {
            **estimated,
            "h_break_even": edge.get("h_break_even"),
            "h_break_even_applicable": edge.get("applicable"),
            "h_break_even_inside_unit_interval": edge.get("inside_unit_interval"),
            "basis": "OBSERVED_CASE_MEAN",
            "label": "ESTIMATED_NET_PROXY",
        }
        proxies.append(float(estimated["estimated_net_proxy"]))
    signs = {proxy > 0 for proxy in proxies}
    sensitivity = "FRAGILE" if len(signs) > 1 else "STABLE_ON_COST_RANGE"
    return {
        "status": "EVALUATED",
        "source_status": profile.get("source_status"),
        "haircut_basis": profile.get("haircut_basis"),
        "included_components": list(profile.get("included_components") or []),
        "excluded_components": list(profile.get("excluded_components") or []),
        "scenarios": scenarios,
        "decision_sensitivity": sensitivity,
        "labeled_net_return": False,
    }


def temporal_frozen_input(binding: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Recipe input identity: files, releases and per-point clocks. No values."""

    return [
        {
            "dataset_id": item.get("dataset_id"),
            "evidence_role": item.get("evidence_role"),
            "holdout": item.get("holdout"),
            "cohort_id": item.get("cohort_id"),
            "release_id": item.get("release_id"),
            "census_sha256": item.get("census_sha256"),
            "observations_sha256": item.get("observations_sha256"),
            "census_rel": item.get("census_rel"),
            "observations_rel": item.get("observations_rel") or item.get("obs_rel"),
            "dataset_manifest_id": item.get("dataset_manifest_id"),
            "schedule_sha256": item.get("schedule_sha256"),
            "schedule_lateness_seconds": item.get("schedule_lateness_seconds"),
            "schedule_point_lateness": item.get("schedule_point_lateness"),
            "schedule_point_due_offset_seconds": item.get("schedule_point_due_offset_seconds"),
            **(
                {
                    "population": item.get("population"),
                    "schedule_binding": item.get("schedule_binding"),
                }
                if item.get("population") == EPISODE_POPULATION
                else {}
            ),
        }
        for item in binding
    ]


def _feature_dependencies(feature: Mapping[str, Any]) -> list[tuple[str, str]]:
    field = str(feature.get("field_id") or PRICE)
    points = [str(feature[k]) for k in ("point", "start", "end", "numerator", "denominator", "at") if k in feature]
    points.extend(str(p) for p in feature.get("points", []))
    return list(dict.fromkeys((p, field) for p in points))


def _target_projection(grouped, body, item, *, cohort, release, mint, anchor, decision_deadline, matched=True, source_detail=None, point_window=None):
    """One target selector for evaluation and cross-delivery integrity; never used by preview.

    ``point_window`` is the OPPORTUNITY_EPISODES resolver binding; legacy
    bindings keep the schedule point clocks.
    """
    target_value, target_observed, target_exclusion = None, False, None
    selected_source_event = "UNKNOWN"
    clock_policy = body.get("observation_clock_policy")
    snapshot_policy = clock_policy if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1 else None
    def _due_late(_cohort, _release, point):
        return _clock(item, point, body["schedule_lateness_seconds"])
    entry_at = decision_deadline + timedelta(
        seconds=int(body["entry_model"]["assumed_latency_seconds"])
    )
    exit_point = str(body["target"]["exit_point"])
    if point_window is not None:
        exit_due_at, exit_deadline = point_window(exit_point)
    else:
        exit_due, exit_late = _due_late(cohort, release, exit_point)
        exit_deadline = _deadline_for(anchor, exit_point, exit_late, due_offset=exit_due)
        exit_due_at = _due_moment(anchor, exit_due)
    exit_rows = grouped.get((cohort, release, mint, exit_point, PRICE), ())
    if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1:
        selected, target_exclusion = _select_snapshot_exit(
            exit_rows,
            entry_at=entry_at,
            exit_due_at=exit_due_at,
            exit_deadline=exit_deadline,
            query_policy=clock_policy,
        )
    else:
        selected, target_exclusion = _select_event_time_exit(
            exit_rows,
            entry_at=entry_at,
            exit_deadline=exit_deadline,
        )
    reference_point = str(body["target"]["reference_point"])
    if point_window is not None:
        reference_due_at, reference_deadline = point_window(reference_point)
    else:
        reference_due, reference_late = _due_late(cohort, release, reference_point)
        reference_deadline = _deadline_for(
            anchor, reference_point, reference_late, due_offset=reference_due
        )
        reference_due_at = _due_moment(anchor, reference_due)
    # Snapshot policy: reference must also meet its own point deadline.
    # EVENT_TIME keeps decision_deadline-only cutoff for V1/V2 replay parity.
    use_strict_reference = (
        clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
    )
    if (
        use_strict_reference
        and reference_deadline is not None
        and decision_deadline is not None
        and reference_deadline < decision_deadline
    ):
        ref_cutoff = reference_deadline
    else:
        ref_cutoff = decision_deadline
    reference = _cell(
        grouped,
        (cohort, release, mint, reference_point, PRICE),
        ref_cutoff,
        snapshot_policy=snapshot_policy,
        point_due_at=reference_due_at if snapshot_policy else None,
    )
    if source_detail is not None:
        # Preserve selected lawful source cells before ratio arithmetic erases
        # their absolute prices. Delivery-local transport IDs are not cell truth.
        source_detail["selected_cells"] = tuple(
            (point, cell.get("status"), cell.get("value"), cell.get("available_at"),
             cell.get("source_price_event_time") or "UNKNOWN")
            for point, cell in ((reference_point, reference), (exit_point, selected))
        )
    if (
        selected.get("status") == "OBSERVED"
        and reference.get("status") == "OBSERVED"
        and float(reference["value"]) > 0
    ):
        target_value = float(selected["value"]) / float(reference["value"]) - 1.0
        target_observed = True
        target_exclusion = None
        source_event = selected.get("source_price_event_time")
        if source_event not in (None, ""):
            selected_source_event = str(source_event)
    elif selected.get("status") == "OBSERVED" and reference.get("status") != "OBSERVED":
        ref_status = str(reference.get("status") or "")
        if ref_status in SNAPSHOT_LINEAGE_BLOCKERS:
            target_exclusion = ref_status
        else:
            target_exclusion = "REFERENCE_NOT_AVAILABLE"
    elif matched and target_exclusion is None:
        target_exclusion = "TARGET_UNOBSERVED"
    return target_value, target_observed, target_exclusion, selected_source_event


def _prefix_copy_integrity(census, grouped, body, binding, *, universe_policy, prefix_only):
    """Compare legal dependency cells, keeping feature and target conflicts separate."""
    by = {(str(i["cohort_id"]), str(i["release_id"])): i for i in binding}
    decision = body["decision_point"]
    lateness = body["schedule_lateness_seconds"]
    snapshot_policy = body.get("observation_clock_policy")
    if snapshot_policy != OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1:
        snapshot_policy = None
    signatures = {}
    seats = defaultdict(list)
    for row in census:
        key = (str(row.get("mint") or ""), str(row.get("cohort_id") or ""), str(row.get("release_id") or ""))
        item = by.get(key[1:])
        if item is None or not key[0]:
            continue
        anchor = row.get("authoritative_anchor")
        due, late = _clock(item, decision, lateness)
        cutoff = _deadline_for(anchor, decision, late, due_offset=due)
        identity = (key[0], cutoff.strftime("%Y-%m-%dT%H:%M:%SZ") if cutoff else str(anchor or ""))
        def cells(pairs):
            values = []
            for point, field in pairs:
                offset, tolerance = _clock(item, point, lateness)
                deadline = _deadline_for(anchor, point, tolerance, due_offset=offset)
                cell = _cell(grouped, (*key[1:], key[0], point, field), deadline,
                             snapshot_policy=snapshot_policy, point_due_at=_due_moment(anchor, offset) if snapshot_policy else None)
                values.append((point, field, cell.get("status"), cell.get("value")))
            return tuple(values)
        membership = [("X300", LIQUIDITY), (decision, PRICE)]
        if universe_policy is not None:
            membership.extend([(decision, HOLDER_COUNT), (decision, LIQUIDITY)])
        signatures[key] = (str(row.get("candidate_state") or ""), cells(membership))
        features = {}
        for feature in body["features"]:
            # Cell values alone omit the bound clocks used by time features.
            # Reuse the actual feature owner; retain cells so arithmetic cannot
            # conceal contradictory operands with an equal derived value.
            projection = _feature_value_with_lineage(
                grouped, cohort=key[1], release=key[2], mint=key[0], anchor=anchor,
                feature=feature, lateness=lateness, decision_deadline=cutoff,
                due_offset_for=lambda point: _clock(item, point, lateness)[0],
                lateness_for=lambda point: _clock(item, point, lateness)[1],
                snapshot_policy=snapshot_policy,
            )
            features[feature["name"]] = (cells(_feature_dependencies(feature)), projection)
        target = None
        if not prefix_only:
            source_detail = {}
            projection = _target_projection(grouped, body, item, cohort=key[1], release=key[2],
                mint=key[0], anchor=anchor, decision_deadline=cutoff, source_detail=source_detail) if cutoff else (None, False, "DECISION_CLOCK_UNAVAILABLE", "UNKNOWN")
            target = (projection, source_detail.get("selected_cells"))
        seats[identity].append((features, target))
    feature_conflicts, target_conflicts = {}, set()
    for identity, copies in seats.items():
        feature_conflicts[identity] = {f["name"] for f in body["features"]
                                       if len({c[0][f["name"]] for c in copies}) > 1}
        if not prefix_only and len({c[1] for c in copies}) > 1:
            target_conflicts.add(identity)
    return signatures, feature_conflicts, target_conflicts


def _project_temporal_members(
    census, observations, body, binding, *, universe_policy=None, prefix_only=False,
):
    """The evaluator's membership and feature owner; no targets in prefix mode."""
    admitted = admit_discovery_binding(binding)
    lateness = int(body["schedule_lateness_seconds"])
    decision_point = str(body["decision_point"])
    binding_by = {(str(i.get("cohort_id")), str(i.get("release_id"))): i for i in binding}
    def _due_late(cohort, release, point):
        return _clock(binding_by[(cohort, release)], point, lateness)
    prefix_mode = prefix_only or any(f.get("field_id") == HOLDER_COUNT and f["op"] in {"delta", "return_ratio"} for f in body["features"])
    grouped = _grouped_cells(observations)
    prefix_signatures, feature_conflicts, target_conflicts = ({}, {}, set())
    if prefix_mode:
        prefix_signatures, feature_conflicts, target_conflicts = _prefix_copy_integrity(
            census, grouped, body, binding, universe_policy=universe_policy, prefix_only=prefix_only)
    signature_index = prefix_signatures if prefix_mode else _signature_index(observations)
    admitted_pairs = {
        (str(item["cohort_id"]), str(item["release_id"])) for item in admitted["cohorts"]
    }
    cohort_ids = [str(item["cohort_id"]) for item in admitted["cohorts"]]
    features = list(body["features"])
    predicates = list(body["predicates"])
    seen: set[tuple[str, str]] = set()
    signatures: dict[tuple[str, str], tuple] = {}
    conflicted: set[tuple[str, str]] = set()
    members: list[dict[str, Any]] = []
    cohort_membership: dict[str, dict[tuple, dict[str, Any]]] = {}
    duplicate_count = 0
    integrity_conflicts = 0
    for row in census:
        mint = str(row.get("mint") or "")
        if not mint:
            continue
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        anchor = row.get("authoritative_anchor")
        if (cohort, release) in admitted_pairs:
            decision_due, decision_late = _due_late(cohort, release, decision_point)
            decision_deadline = _deadline_for(
                anchor, decision_point, decision_late, due_offset=decision_due
            )
        else:
            decision_deadline = _deadline_for(anchor, decision_point, lateness)
        decision_key = decision_deadline.strftime("%Y-%m-%dT%H:%M:%SZ") if decision_deadline else str(anchor or "")
        identity = (mint, decision_key)
        block = decision_deadline.date().isoformat() if decision_deadline is not None else "UNANCHORED"
        if (cohort, release) not in admitted_pairs:
            members.append(
                {
                    "identity": identity,
                    "in_base": False,
                    "decision_eligible": False,
                    "feature_values": {},
                    "feature_unknown": False,
                    "matched": False,
                    "target": None,
                    "target_is_observed": False,
                    "block": block,
                    "exclusion": "BINDING_COHORT_MISMATCH",
                }
            )
            continue
        signature = signature_index.get((mint, cohort, release), ())
        if identity in seen:
            duplicate_count += 1
            if identity in conflicted or signatures.get(identity) != signature:
                if identity not in conflicted:
                    integrity_conflicts += 1
                    conflicted.add(identity)
                for member in members:
                    if member.get("identity") == identity:
                        member["integrity_excluded"] = True
                        member["in_base"] = False
                        member["decision_eligible"] = False
                        member["feature_unknown"] = False
                        member["matched"] = False
                        member["target_is_observed"] = False
                        member["target"] = None
                        if member.get("exclusion") != "BINDING_COHORT_MISMATCH":
                            member["exclusion"] = "INTEGRITY_CONFLICT"
                _exclude_shared_identity(cohort_membership, identity)
                _note_cohort_membership(
                    cohort_membership,
                    cohort,
                    identity,
                    {
                        "integrity_excluded": True,
                        "in_base": False,
                        "decision_eligible": False,
                        "matched": False,
                        "target_is_observed": False,
                        "feature_unknown": False,
                        "exclusion": "INTEGRITY_CONFLICT",
                        "target": None,
                    },
                )
                continue
            existing = next(
                item
                for item in members
                if item.get("identity") == identity and item.get("exclusion") != "BINDING_COHORT_MISMATCH"
            )
            if existing.get("integrity_excluded"):
                conflicted.add(identity)
                _exclude_shared_identity(cohort_membership, identity)
                _note_cohort_membership(
                    cohort_membership,
                    cohort,
                    identity,
                    {
                        "integrity_excluded": True,
                        "in_base": False,
                        "decision_eligible": False,
                        "matched": False,
                        "target_is_observed": False,
                        "feature_unknown": False,
                        "exclusion": "INTEGRITY_CONFLICT",
                        "target": None,
                    },
                )
                continue
            if existing.get("in_base"):
                _note_cohort_membership(cohort_membership, cohort, identity, existing)
                continue
            members.remove(existing)
            seen.remove(identity)
        seen.add(identity)
        signatures[identity] = signature
        exclusion = None
        in_base = False
        clock_policy = str(
            body.get("observation_clock_policy") or OBSERVATION_CLOCK_EVENT_TIME_V1
        )
        snapshot_policy = (
            clock_policy
            if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
            else None
        )
        if str(row.get("candidate_state") or "") != "X_ELIGIBLE" or decision_deadline is None:
            exclusion = "NOT_X_ELIGIBLE"
        else:
            x300_due, x300_late = _due_late(cohort, release, "X300")
            liquidity = _cell(
                grouped,
                (cohort, release, mint, "X300", LIQUIDITY),
                _deadline_for(
                    anchor,
                    "X300",
                    x300_late,
                    due_offset=x300_due,
                ),
                snapshot_policy=snapshot_policy,
                point_due_at=_due_moment(anchor, x300_due) if snapshot_policy else None,
            )
            if liquidity.get("status") != "OBSERVED":
                status = str(liquidity.get("status") or "")
                if status in SNAPSHOT_LINEAGE_BLOCKERS:
                    exclusion = status
                else:
                    exclusion = "PIT_LIQUIDITY_MISSING"
            else:
                in_base = True
        feature_values: dict[str, float | None] = {}
        feature_reasons: dict[str, str] = {}
        decision_eligible = False
        universe_status = None
        universe_reasons: list[str] = []
        search_base = in_base
        if in_base and universe_policy is not None:
            from solana_alpha_lab.factory.hfic_research_universe_policy import (
                classify_universe_cells,
            )

            decision_due, _decision_late = _due_late(cohort, release, decision_point)
            point_due = _due_moment(anchor, decision_due) if snapshot_policy else None
            holder_cell = _cell(
                grouped,
                (cohort, release, mint, decision_point, HOLDER_COUNT),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=point_due,
            )
            liquidity_cell = _cell(
                grouped,
                (cohort, release, mint, decision_point, LIQUIDITY),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=point_due,
            )
            verdict = classify_universe_cells(holder_cell, liquidity_cell, universe_policy)
            universe_status = str(verdict["status"])
            universe_reasons = list(verdict["reasons"])
            search_base = universe_status == "PASS"
        if search_base:
            decision_due, _decision_late = _due_late(cohort, release, decision_point)
            decision_price = _cell(
                grouped,
                (cohort, release, mint, decision_point, PRICE),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=_due_moment(anchor, decision_due) if snapshot_policy else None,
            )
            decision_status = str(decision_price.get("status") or "")
            decision_eligible = decision_status == "OBSERVED"
            if not decision_eligible and decision_status in SNAPSHOT_LINEAGE_BLOCKERS:
                # Preserve lineage fitness reasons on the eligible attempt; do
                # not let them collapse to an empty exclusion bag.
                exclusion = decision_status
            if decision_eligible:
                for feature in features:
                    detail = {}
                    value, feature_lineage = _feature_value_with_lineage(
                        grouped,
                        cohort=cohort,
                        release=release,
                        mint=mint,
                        anchor=anchor,
                        feature=feature,
                        lateness=lateness,
                        decision_deadline=decision_deadline,
                        due_offset_for=lambda point, cohort=cohort, release=release: _due_late(
                            cohort, release, point
                        )[0],
                        lateness_for=lambda point, cohort=cohort, release=release: _due_late(
                            cohort, release, point
                        )[1],
                        snapshot_policy=snapshot_policy,
                        detail=detail if prefix_mode else None,
                    )
                    if prefix_mode and feature["name"] in feature_conflicts.get(identity, set()):
                        value, feature_lineage = None, None
                        detail["reason"] = "DELIVERY_CONFLICT"
                    if prefix_mode and value is None:
                        feature_reasons[feature["name"]] = detail.get("reason") or "FEATURE_UNAVAILABLE"
                    feature_values[str(feature["name"])] = value
                    if (
                        feature_lineage in SNAPSHOT_LINEAGE_BLOCKERS
                        and exclusion not in SNAPSHOT_LINEAGE_BLOCKERS
                    ):
                        exclusion = feature_lineage
        hits = [
            _predicate_holds(feature_values.get(str(item["feature"])), item) for item in predicates
        ] if decision_eligible else []
        feature_unknown = decision_eligible and any(hit is None for hit in hits)
        matched = decision_eligible and not feature_unknown and all(hit is True for hit in hits)
        target_value = None
        target_observed = False
        target_exclusion = None
        selected_source_event = "UNKNOWN"
        if not prefix_only and identity in target_conflicts:
            target_exclusion = "TARGET_DELIVERY_CONFLICT"
        elif not prefix_only and search_base and decision_deadline is not None:
            target_value, target_observed, target_exclusion, selected_source_event = _target_projection(
                grouped, body, binding_by[(cohort, release)], cohort=cohort, release=release,
                mint=mint, anchor=anchor, decision_deadline=decision_deadline, matched=matched)
        # Outcome fitness is scoped to matched members only. Publishing exit /
        # reference lineage for unmatched members would let a false predicate
        # zero-match collapse into a technical stop.
        publish_target_exclusion = None
        if (
            matched
            and not target_observed
            and isinstance(target_exclusion, str)
            and target_exclusion
        ):
            publish_target_exclusion = target_exclusion
        members.append(
            {
                "identity": identity,
                "in_base": in_base,
                "decision_eligible": decision_eligible,
                "feature_values": feature_values,
                **({"feature_reasons": feature_reasons, "cohort_id": cohort, "release_id": release} if prefix_mode else {}),
                "feature_unknown": feature_unknown,
                "matched": matched,
                "target": target_value,
                "target_is_observed": target_observed,
                "target_exclusion": publish_target_exclusion,
                "source_price_event_time": selected_source_event,
                "block": block,
                "exclusion": exclusion,
                **(
                    {
                        "universe_status": universe_status,
                        "universe_reasons": universe_reasons,
                    }
                    if universe_policy is not None
                    else {}
                ),
            }
        )
        _note_cohort_membership(cohort_membership, cohort, identity, members[-1])
    return members, cohort_membership, seen, duplicate_count, integrity_conflicts


def _episode_point_window(item: Mapping[str, Any], t0: Any) -> Any:
    """Bind the frozen episode schedule to one admission instant."""

    from solana_alpha_lab.factory.opportunity_episodes import (
        OpportunityEpisodeError,
        require_binding,
        resolve_point,
    )

    schedule_binding = item.get("schedule_binding")
    try:
        require_binding(schedule_binding)
    except OpportunityEpisodeError as exc:
        raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND") from exc

    def window(point: str) -> tuple[Any, Any]:
        try:
            resolved = resolve_point(schedule_binding, t0, str(point))
        except OpportunityEpisodeError as exc:
            raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST") from exc
        return resolved.request_not_before, resolved.availability_deadline

    return window


def _episode_signature(rows: Sequence[Mapping[str, Any]]) -> tuple:
    return tuple(
        sorted(
            (
                str(row.get("point_id") or ""),
                str(row.get("field_id") or ""),
                str(row.get("first_reliable_available_at") or ""),
                str(row.get("request_started_at") or ""),
                str(row.get("response_received_at") or ""),
                str(row.get("state") or ""),
                str(row.get("typed_value")),
            )
            for row in rows
        )
    )


def _project_episode_members(
    census, observations, body, binding, *, universe_policy=None, prefix_only=False,
):
    """OPPORTUNITY_EPISODES membership and features. Base = every admission.

    Cells are keyed by episode identity; the true mint stays a census field.
    Clocks come from the one episode resolver; values reuse the shared cell,
    feature, predicate and target owners.
    """

    admitted = admit_discovery_binding(binding)
    admitted_pairs = {
        (str(item["cohort_id"]), str(item["release_id"])) for item in admitted["cohorts"]
    }
    binding_by = {(str(i.get("cohort_id")), str(i.get("release_id"))): i for i in binding}
    grouped: dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    by_episode: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        key = (
            str(row.get("cohort_id") or ""),
            str(row.get("release_id") or ""),
            str(row.get("episode_id") or ""),
        )
        grouped[(*key, str(row.get("point_id") or ""), str(row.get("field_id") or ""))].append(row)
        by_episode[key].append(row)
    decision_point = str(body["decision_point"])
    snapshot_policy = OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1
    prefix_mode = prefix_only or any(
        f.get("field_id") == HOLDER_COUNT and f["op"] in {"delta", "return_ratio"}
        for f in body["features"]
    )
    features = list(body["features"])
    predicates = list(body["predicates"])
    seen: set[tuple[str, str]] = set()
    signatures: dict[tuple[str, str], tuple] = {}
    members: list[dict[str, Any]] = []
    cohort_membership: dict[str, dict[tuple, dict[str, Any]]] = {}
    duplicate_count = 0
    integrity_conflicts = 0
    episode_mints: dict[str, str] = {}
    for row in census:
        episode = str(row.get("episode_id") or "")
        mint = str(row.get("mint") or "")
        if not episode or not mint:
            continue
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        t0 = _parse_time(row.get("t0"))
        if (cohort, release) not in admitted_pairs or t0 is None:
            members.append(
                {
                    "identity": (episode, "UNBOUND"),
                    "in_base": False,
                    "decision_eligible": False,
                    "feature_values": {},
                    "feature_unknown": False,
                    "matched": False,
                    "target": None,
                    "target_is_observed": False,
                    "block": "UNANCHORED",
                    "exclusion": "BINDING_COHORT_MISMATCH",
                }
            )
            continue
        item = binding_by[(cohort, release)]
        window = _episode_point_window(item, t0)
        decision_due_at, decision_deadline = window(decision_point)
        identity = (episode, decision_deadline.strftime("%Y-%m-%dT%H:%M:%SZ"))
        block = decision_deadline.date().isoformat()
        signature = _episode_signature(by_episode.get((cohort, release, episode), ()))
        if identity in seen:
            duplicate_count += 1
            if signatures.get(identity) == signature:
                continue
            integrity_conflicts += 1
            for member in members:
                if member.get("identity") == identity:
                    member.update(
                        integrity_excluded=True,
                        in_base=False,
                        decision_eligible=False,
                        feature_unknown=False,
                        matched=False,
                        target_is_observed=False,
                        target=None,
                        exclusion="INTEGRITY_CONFLICT",
                    )
            _exclude_shared_identity(cohort_membership, identity)
            continue
        seen.add(identity)
        signatures[identity] = signature
        episode_mints[episode] = mint
        exclusion = None
        feature_values: dict[str, float | None] = {}
        feature_reasons: dict[str, str] = {}
        universe_status = None
        universe_reasons: list[str] = []
        search_base = True
        if universe_policy is not None:
            from solana_alpha_lab.factory.hfic_research_universe_policy import (
                classify_universe_cells,
            )

            holder_cell = _cell(
                grouped,
                (cohort, release, episode, decision_point, HOLDER_COUNT),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=decision_due_at,
            )
            liquidity_cell = _cell(
                grouped,
                (cohort, release, episode, decision_point, LIQUIDITY),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=decision_due_at,
            )
            verdict = classify_universe_cells(holder_cell, liquidity_cell, universe_policy)
            universe_status = str(verdict["status"])
            universe_reasons = list(verdict["reasons"])
            search_base = universe_status == "PASS"
        decision_eligible = False
        if search_base:
            decision_price = _cell(
                grouped,
                (cohort, release, episode, decision_point, PRICE),
                decision_deadline,
                snapshot_policy=snapshot_policy,
                point_due_at=decision_due_at,
            )
            decision_status = str(decision_price.get("status") or "")
            decision_eligible = decision_status == "OBSERVED"
            if not decision_eligible:
                exclusion = decision_status or "DECISION_PRICE_ABSENT"
            else:
                for feature in features:
                    detail: dict[str, Any] = {}
                    value, feature_lineage = _feature_value_with_lineage(
                        grouped,
                        cohort=cohort,
                        release=release,
                        mint=episode,
                        anchor=t0,
                        feature=feature,
                        lateness=0,
                        decision_deadline=decision_deadline,
                        snapshot_policy=snapshot_policy,
                        detail=detail if prefix_mode else None,
                        point_window=window,
                        time_clock=EPISODE_TIME_FEATURE_CLOCK,
                    )
                    if prefix_mode and value is None:
                        feature_reasons[feature["name"]] = detail.get("reason") or "FEATURE_UNAVAILABLE"
                    feature_values[str(feature["name"])] = value
                    if feature_lineage in SNAPSHOT_LINEAGE_BLOCKERS and exclusion not in SNAPSHOT_LINEAGE_BLOCKERS:
                        exclusion = feature_lineage
        else:
            exclusion = "UNIVERSE_" + str(universe_status or "UNKNOWN")
        hits = [
            _predicate_holds(feature_values.get(str(item_p["feature"])), item_p) for item_p in predicates
        ] if decision_eligible else []
        feature_unknown = decision_eligible and any(hit is None for hit in hits)
        matched = decision_eligible and not feature_unknown and all(hit is True for hit in hits)
        target_value = None
        target_observed = False
        target_exclusion = None
        selected_source_event = "UNKNOWN"
        if not prefix_only and search_base:
            target_value, target_observed, target_exclusion, selected_source_event = _target_projection(
                grouped, body, item, cohort=cohort, release=release, mint=episode, anchor=t0,
                decision_deadline=decision_deadline, matched=matched, point_window=window)
        publish_target_exclusion = None
        if matched and not target_observed and isinstance(target_exclusion, str) and target_exclusion:
            publish_target_exclusion = target_exclusion
        members.append(
            {
                "identity": identity,
                "episode_id": episode,
                "mint": mint,
                "in_base": True,
                "decision_eligible": decision_eligible,
                "feature_values": feature_values,
                **({"feature_reasons": feature_reasons, "cohort_id": cohort, "release_id": release} if prefix_mode else {}),
                "feature_unknown": feature_unknown,
                "matched": matched,
                "target": target_value,
                "target_is_observed": target_observed,
                "target_exclusion": publish_target_exclusion,
                "source_price_event_time": selected_source_event,
                "block": block,
                "exclusion": exclusion,
                **(
                    {"universe_status": universe_status, "universe_reasons": universe_reasons}
                    if universe_policy is not None
                    else {}
                ),
            }
        )
        _note_cohort_membership(cohort_membership, cohort, identity, members[-1])
    return members, cohort_membership, seen, duplicate_count, integrity_conflicts, episode_mints


def execute_temporal_discovery(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
    *,
    universe_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute one temporal query. Binding is admitted before any value read."""

    for item in binding:
        if "holdout" not in item:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        if "evidence_role" not in item:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
    admitted = admit_discovery_binding(binding)
    frozen_source = temporal_frozen_input(binding)
    bound = validate_temporal_query(spec)
    body = bound["scientific_body"]
    episode_population = is_episode_body(body)
    if episode_population != (admitted.get("population") == EPISODE_POPULATION):
        raise GroundedDiscoveryError("POPULATION_BINDING_MISMATCH")
    episode_mints: dict[str, str] = {}
    if episode_population:
        (
            members,
            cohort_membership,
            seen,
            duplicate_count,
            integrity_conflicts,
            episode_mints,
        ) = _project_episode_members(census, observations, body, binding, universe_policy=universe_policy)
    else:
        lateness = int(body["schedule_lateness_seconds"])
        _require_bound_schedule(binding, body, lateness)
        members, cohort_membership, seen, duplicate_count, integrity_conflicts = _project_temporal_members(
            census, observations, body, binding, universe_policy=universe_policy)
    features, predicates = list(body["features"]), list(body["predicates"])
    cohort_ids = [str(item["cohort_id"]) for item in admitted["cohorts"]]
    base_members = [item for item in members if item["in_base"]]
    decision_members = [item for item in base_members if item["decision_eligible"]]
    matched_members, observed, missing_target = _conditional_sample(decision_members)
    observed_values = [float(item["target"]) for item in observed]
    observed_mean = _mean(observed_values)
    matched_downside = downside_descriptive(observed_values, missing_n=len(missing_target))
    known_source_events = [
        str(item.get("source_price_event_time"))
        for item in observed
        if item.get("source_price_event_time") not in (None, "", "UNKNOWN")
    ]
    summary_source_event = known_source_events[0] if known_source_events else "UNKNOWN"
    stress_values = observed_values + [-1.0 for _ in missing_target]
    ablations = []
    if body["evaluation"]["ablations"] == "DROP_ONE_CONDITION":
        for dropped in predicates:
            kept = [item for item in predicates if item is not dropped]
            subset_members = []
            for member in decision_members:
                hits = [
                    _predicate_holds(member["feature_values"].get(str(item["feature"])), item)
                    for item in kept
                ]
                if all(hit is True for hit in hits):
                    subset_members.append(member)
            subset = [
                float(member["target"])
                for member in subset_members
                if member["target_is_observed"] and member["target"] is not None
            ]
            ablations.append(
                {
                    "view": f"ABLATION_DROP_{dropped['feature']}",
                    "dropped_feature": dropped["feature"],
                    "observed_n": len(subset),
                    "mean_target": _mean(subset),
                    "median_target": _median(subset),
                    "mean_target_kind": "PRICE_RELATIVE_PROXY",
                    "selection_relevant": True,
                    "downside": downside_descriptive(
                        subset, missing_n=len(subset_members) - len(subset)
                    ),
                }
            )
    baseline_values = [
        float(item["target"])
        for item in decision_members
        if item["target_is_observed"] and item["target"] is not None
    ]
    by_block: dict[str, list[float]] = defaultdict(list)
    for item in observed:
        by_block[str(item["block"])].append(float(item["target"]))
    by_block_missing: dict[str, int] = defaultdict(int)
    for item in missing_target:
        by_block_missing[str(item["block"])] += 1
    profile = body["cost_profile"]
    costs = _cost_views(observed_mean, profile)
    viewed = ["MATCHED_OBSERVED", "BASELINE_DECISION_ELIGIBLE"]
    viewed.extend(item["view"] for item in ablations)
    if costs["status"] == "EVALUATED":
        viewed.extend(f"COST_{name}" for name in ("LOW", "BASE", "STRESS"))
        viewed.append("MISSING_STRESS_MODEL")
    viewed.append(DOWNSIDE_PROFILE)
    positive = [value for value in observed_values if value > 0]
    winner_share = max(positive) / sum(positive) if positive else None
    missing_mean_to_zero = None
    if missing_target and observed_values:
        missing_mean_to_zero = -sum(observed_values) / len(missing_target)
    clock_policy = str(body.get("observation_clock_policy") or OBSERVATION_CLOCK_EVENT_TIME_V1)
    target_exclusion_pooled: dict[str, int] = defaultdict(int)
    for item in members:
        reason = item.get("target_exclusion")
        if isinstance(reason, str) and reason:
            target_exclusion_pooled[reason] += 1
    by_cohort_rows = _cohort_rows(
        cohort_membership,
        list(dict.fromkeys(cohort_ids)),
    )
    summary = {
        "contract_version": "FORGE_GROUNDED_DISCOVERY_V1",
        "calculation_version": (
            TEMPORAL_CALCULATION_VERSION_EPISODES_V1
            if episode_population
            else TEMPORAL_CALCULATION_VERSION
        ),
        "schema": TEMPORAL_SCHEMA,
        "query_id": bound["query_id"],
        "spec_sha256": bound["spec_sha256"],
        "population": EPISODE_POPULATION if episode_population else "BASE_X",
        "search_tier": bound["search_tier"],
        "observation_clock_policy": clock_policy,
        "target_kind": "PRICE_RELATIVE_PROXY",
        "mean_target_kind": "PRICE_RELATIVE_PROXY",
        "mean_target_units": "DIMENSIONLESS_PRICE_RATIO_MINUS_ONE",
        "claim_level": "EXPLORATORY_PROXY",
        "labeled_net_return": False,
        "engine_emits_alpha": False,
        "eligibility_uses_target": False,
        "missing_is_not_zero": True,
        "source_price_event_time": summary_source_event,
        "population_n": len(base_members),
        "base_x_n": len(base_members),
        "decision_eligible_n": len(decision_members),
        "matched_n": len(matched_members),
        "feature_unknown_n": sum(1 for item in decision_members if item["feature_unknown"]),
        "observed_target_n": len(observed),
        "missing_target_n": len(missing_target),
        "duplicate_delivery_count": duplicate_count,
        "integrity_conflict_count": integrity_conflicts,
        "observation_index_passes": 1,
        "unique_mint_n": (
            len(set(episode_mints.values()))
            if episode_population
            else len({mint for mint, _decision in seen})
        ),
        "unique_decision_n": len(seen),
        "block_count": len({item["block"] for item in observed}),
        "independence": "UNKNOWN",
        "independent_replication": None,
        "later_target_observed_n": len(observed),
        "feature_admissible_n": len(decision_members),
        "mean_target": observed_mean,
        "median_target": _median(observed_values),
        "downside": matched_downside,
        "winner_share_of_positive": winner_share,
        "missing_target_mean_to_zero": missing_mean_to_zero,
        "missing_stress_model": {
            "label": "MODEL",
            "stress_return": -1.0,
            "mean_target": _mean(stress_values),
            "writes_raw_history": False,
        },
        "matched_feature_means": {
            str(feature["name"]): _mean(
                [
                    float(member["feature_values"][str(feature["name"])])
                    for member in matched_members
                    if member["feature_values"].get(str(feature["name"])) is not None
                ]
            )
            for feature in features
        },
        "baseline": {
            "view": "BASELINE_DECISION_ELIGIBLE",
            "observed_n": len(baseline_values),
            "mean_target": _mean(baseline_values),
            "median_target": _median(baseline_values),
            "mean_target_kind": "PRICE_RELATIVE_PROXY",
            "downside": downside_descriptive(
                baseline_values, missing_n=len(decision_members) - len(baseline_values)
            ),
        },
        "ablations": ablations,
        "by_calendar_block": [
            {
                "view": key,
                "observed_n": len(values),
                "mean_target": _mean(values),
                "median_target": _median(values),
                "mean_target_kind": "PRICE_RELATIVE_PROXY",
                "downside": downside_descriptive(values, missing_n=by_block_missing.get(key, 0)),
            }
            for key, values in sorted(
                (key, by_block.get(key, [])) for key in set(by_block) | set(by_block_missing)
            )
        ],
        "by_cohort": by_cohort_rows,
        "cohort_slices_are_descriptive": True,
        "cohort_independent_replication": False,
        "cost": costs,
        "viewed_variants": viewed,
        "downside_readout_exposure": {
            "profile": DOWNSIDE_PROFILE,
            "fixed_metrics": [
                "p05", "p10", "p25", "le_minus_20_rate", "le_minus_50_rate",
                "es10_return", "negative_mass", "worst_negative_share",
            ],
            "new_threshold_trials": False,
        },
        "main_question_count_includes_variants": False,
        "pooled": {
            "view": "pooled",
            "denominator_base_x": len(base_members),
            "feature_admissible": len(decision_members),
            "target_observed_after_decision": len(observed),
            "mean_target": observed_mean,
            "median_target": _median(observed_values),
            "downside": matched_downside,
            "mean_target_kind": "PRICE_RELATIVE_PROXY",
            "independent_replication": None,
        },
        "exclusion_reasons": dict(sorted(
            (key, sum(1 for item in members if item["exclusion"] == key))
            for key in {item["exclusion"] for item in members if item["exclusion"]}
        )),
        "target_exclusion_reasons": {
            "pooled": dict(sorted(target_exclusion_pooled.items())),
            "by_cohort": {
                str(row["cohort_id"]): dict(row.get("target_exclusion_reasons") or {})
                for row in by_cohort_rows
            },
        },
        "required_cohorts": cohort_ids,
        "experiment_recipe": {
            "capability_id": TEMPORAL_CAPABILITY_ID,
            "schema": TEMPORAL_SCHEMA,
            "schema_version": bound.get("schema_version", TEMPORAL_SCHEMA_VERSION),
            "scientific_identity": bound["spec_sha256"],
            "observation_clock_policy": clock_policy,
            "target_kind": "PRICE_RELATIVE_PROXY",
            "cost_label": "ESTIMATED_NET_PROXY" if costs["status"] == "EVALUATED" else "ABSENT",
            "labeled_net_return": False,
            "spec": canonical_temporal_spec(spec),
            "frozen_input": frozen_source,
        },
        "non_claims": [
            "NO_ALPHA",
            "NO_NET_RETURN",
            "NO_INTRABAR_STOP",
            "NO_CAUSAL_IDENTIFICATION",
            *(
                ["NO_SOURCE_PRICE_EVENT_TIME"]
                if summary_source_event in (None, "", "UNKNOWN")
                else []
            ),
        ],
    }
    if universe_policy is not None:
        from solana_alpha_lab.factory.hfic_research_universe_policy import snapshot

        counted = [item for item in members if item.get("in_base")]
        counts = {
            status: sum(1 for item in counted if item.get("universe_status") == status)
            for status in ("PASS", "FAIL", "UNKNOWN")
        }
        if sum(counts.values()) != len(counted):
            raise GroundedDiscoveryError("UNIVERSE_POLICY_COUNT_MISMATCH")
        bound_policy = snapshot(universe_policy)
        summary["universe_policy"] = {
            **bound_policy,
            "n_base": len(counted),
            "n_pass": counts["PASS"],
            "n_fail": counts["FAIL"],
            "n_unknown": counts["UNKNOWN"],
        }
        summary["experiment_recipe"]["universe_policy"] = bound_policy
    if episode_population:
        decision_members_all = [item for item in members if item.get("in_base") and item.get("decision_eligible")]
        summary["anchor_kind"] = EPISODE_ANCHOR_KIND
        summary["time_feature_clock"] = EPISODE_TIME_FEATURE_CLOCK
        summary["episode_counts"] = {
            "n_admitted": len(base_members),
            "n_decision_eligible": len(decision_members_all),
            "n_joint_feature_supported": sum(1 for item in decision_members_all if not item.get("feature_unknown")),
            "n_matched": len(matched_members),
            "n_target_available": len(observed),
            "unique_episode_n": len(seen),
            "unique_mint_n": len(set(episode_mints.values())),
            "repeated_mint_n": len(episode_mints) - len(set(episode_mints.values())),
        }
        summary["non_claims"] = list(summary["non_claims"]) + ["NO_IID_CLAIM", "NOT_NEWBORN_BIRTH_POPULATION"]
    stop = snapshot_input_technical_stop(summary)
    if stop is not None:
        summary["technical_stop"] = stop
        summary["technical_failure"] = True
        summary["terminal"] = stop["terminal"]
        summary["reason_code"] = stop["reason_code"]
        summary["scientific_negative"] = False
    require_coherent_temporal_result(summary)
    from solana_alpha_lab.factory.hfic_research_universe_policy import admitted_with_policy

    return {
        "admitted": admitted_with_policy(admitted, universe_policy),
        "summary": summary,
        "members_projected": len(members),
    }


def validate_feature_preview_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Pure pre-values policy shared by the CLI and feature-only evaluator."""

    if isinstance(spec, Mapping) and "target" in spec:
        raise GroundedDiscoveryError("PREVIEW_FORBIDS_TARGET")
    decision = _require_mapping(spec.get("decision"), "DECISION_INVALID")
    decision_point = _point(decision.get("point_id"))
    schedule = _require_mapping(spec.get("schedule"), "SCHEDULE_INVALID")
    lateness = schedule.get("lateness_seconds")
    if isinstance(lateness, bool) or not isinstance(lateness, int) or lateness < 0:
        raise GroundedDiscoveryError("SCHEDULE_INVALID")
    points = schedule.get("points")
    if not isinstance(points, list) or not points:
        raise GroundedDiscoveryError("SCHEDULE_INVALID")
    point_ids = [_point(item) for item in points]
    if any(POINT_OFFSET[item] > POINT_OFFSET[decision_point] for item in point_ids):
        raise GroundedDiscoveryError("FEATURE_AFTER_DECISION")
    features_in = spec.get("features", [])
    if not isinstance(features_in, list):
        raise GroundedDiscoveryError("FEATURE_INVALID")
    features = [_canonical_feature(_require_mapping(f, "FEATURE_INVALID")) for f in features_in]
    if len(features) > MAX_FEATURES or len({f["name"] for f in features}) != len(features):
        raise GroundedDiscoveryError("FEATURE_INVALID")
    raw_holder_recipe = any(f.get("field_id") == HOLDER_COUNT and f["op"] in {"delta", "return_ratio"} for f in features)
    for feature in features:
        if not raw_holder_recipe and feature["op"] != "point_value":
            raise GroundedDiscoveryError("FEATURE_OP_UNSUPPORTED")
        for point, _field_id in _feature_dependencies(feature):
            if POINT_OFFSET[point] > POINT_OFFSET[decision_point]:
                raise GroundedDiscoveryError("FEATURE_AFTER_DECISION")
            if point not in point_ids:
                raise GroundedDiscoveryError("SCHEDULE_INVALID")
    clock_policy = schedule.get("observation_clock_policy", OBSERVATION_CLOCK_EVENT_TIME_V1)
    if clock_policy in (None, ""):
        clock_policy = OBSERVATION_CLOCK_EVENT_TIME_V1
    if clock_policy not in OBSERVATION_CLOCK_POLICIES:
        raise GroundedDiscoveryError("OBSERVATION_CLOCK_POLICY_INVALID")
    seed = spec.get("seed")
    if not isinstance(seed, str) or not seed:
        raise GroundedDiscoveryError("PREVIEW_SEED_REQUIRED")
    return {"decision_point": decision_point, "lateness": lateness, "point_ids": point_ids,
            "features": features, "clock_policy": clock_policy, "seed": seed}


def universe_population_counts(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    binding: Sequence[Mapping[str, Any]],
    *,
    decision_point: str,
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    """Eligibility counts at one decision time. Does not read a future target."""

    from solana_alpha_lab.factory.hfic_grounded_discovery import admit_discovery_binding
    from solana_alpha_lab.factory.hfic_research_universe_policy import classify_universe_cells

    point = _point(decision_point)
    admitted = admit_discovery_binding(binding)
    grouped = _grouped_cells(observations)
    binding_by = {(str(item.get("cohort_id")), str(item.get("release_id"))): item for item in binding}
    admitted_pairs = {(str(item["cohort_id"]), str(item["release_id"])) for item in admitted["cohorts"]}
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    reason_counts: dict[str, int] = defaultdict(int)
    for row in census:
        mint = str(row.get("mint") or "")
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        if not mint or (cohort, release) not in admitted_pairs:
            continue
        item = binding_by.get((cohort, release))
        if item is None:
            raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
        late_map = item.get("schedule_point_lateness") if isinstance(item.get("schedule_point_lateness"), Mapping) else {}
        query_lateness = late_map.get("X300", item.get("schedule_lateness_seconds"))
        if isinstance(query_lateness, bool) or not isinstance(query_lateness, int):
            raise GroundedDiscoveryError("SCHEDULE_CONTEXT_UNBOUND")
        anchor = row.get("authoritative_anchor")
        decision_due, decision_late = _clock(item, point, query_lateness)
        decision_deadline = _deadline_for(anchor, point, decision_late, due_offset=decision_due)
        if str(row.get("candidate_state") or "") != "X_ELIGIBLE" or decision_deadline is None:
            continue
        x_due, x_late = _clock(item, "X300", query_lateness)
        liquidity = _cell(
            grouped,
            (cohort, release, mint, "X300", LIQUIDITY),
            _deadline_for(anchor, "X300", x_late, due_offset=x_due),
        )
        if liquidity.get("status") != "OBSERVED":
            continue
        clock_policy = str(item.get("observation_clock_policy") or OBSERVATION_CLOCK_EVENT_TIME_V1)
        snapshot_policy = clock_policy if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1 else None
        point_due = _due_moment(anchor, decision_due) if snapshot_policy else None
        verdict = classify_universe_cells(
            _cell(grouped, (cohort, release, mint, point, HOLDER_COUNT), decision_deadline, snapshot_policy=snapshot_policy, point_due_at=point_due),
            _cell(grouped, (cohort, release, mint, point, LIQUIDITY), decision_deadline, snapshot_policy=snapshot_policy, point_due_at=point_due),
            definition,
        )
        counts[str(verdict["status"])] += 1
        for reason in verdict["reasons"]:
            reason_counts[reason] += 1
    n_base = sum(counts.values())
    return {
        "decision_point": point,
        "n_base": n_base,
        "n_pass": counts["PASS"],
        "n_fail": counts["FAIL"],
        "n_unknown": counts["UNKNOWN"],
        "reason_counts": dict(sorted(reason_counts.items())),
        "future_outcomes_read": False,
    }


def build_feature_preview(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
    *,
    prior_preview_hashes: Sequence[str] = (),
    universe_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Feature-only preview. Target and survival labels are not computed."""

    checked = validate_feature_preview_spec(spec)
    if any(f.get("field_id") == HOLDER_COUNT and f["op"] in {"delta", "return_ratio"} for f in checked["features"]):
        return _build_recipe_preview(census, observations, spec, binding,
                                     prior_preview_hashes=prior_preview_hashes, universe_policy=universe_policy)
    admitted = admit_discovery_binding(binding)
    decision_point, lateness = checked["decision_point"], checked["lateness"]
    point_ids, features = checked["point_ids"], checked["features"]
    clock_policy, seed = checked["clock_policy"], checked["seed"]
    for item in binding:
        for point in ["X300", *point_ids]:
            _clock(item, point, lateness)
    from solana_alpha_lab.factory.hfic_research_universe_policy import (
        classify_universe_cells,
        snapshot,
    )

    policy_identity = snapshot(universe_policy)["semantic_sha256"] if universe_policy is not None else None
    identity = _sha256(
        {
            "decision_point": decision_point,
            "lateness_seconds": lateness,
            "points": point_ids,
            "seed": seed,
            "population": "BASE_X",
            **({"features": features} if features else {}),
            **({"observation_clock_policy": clock_policy} if clock_policy != OBSERVATION_CLOCK_EVENT_TIME_V1 else {}),
            **({"universe_policy_semantic_sha256": policy_identity} if policy_identity else {}),
        }
    )
    prior = [str(item) for item in prior_preview_hashes]
    if identity not in prior and len(set(prior)) >= MAX_PREVIEW_SPECS:
        raise GroundedDiscoveryError("PREVIEW_ENVELOPE_EXHAUSTED")
    grouped = _grouped_cells(observations)
    preview_binding = {
        (str(item.get("cohort_id")), str(item.get("release_id"))): item for item in binding
    }

    def preview_deadline(anchor: object, cohort_id: str, release_id: str, point: str):
        due, late = _clock(preview_binding[(cohort_id, release_id)], point, lateness)
        return _deadline_for(anchor, point, late, due_offset=due)

    admitted_pairs = {(str(item["cohort_id"]), str(item["release_id"])) for item in admitted["cohorts"]}
    examples: list[dict[str, Any]] = []
    total = 0
    universe_counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for row in census:
        mint = str(row.get("mint") or "")
        cohort = str(row.get("cohort_id") or "")
        release = str(row.get("release_id") or "")
        if not mint or (cohort, release) not in admitted_pairs:
            continue
        if str(row.get("candidate_state") or "") != "X_ELIGIBLE":
            continue
        anchor = row.get("authoritative_anchor")
        liquidity = _cell(
            grouped,
            (cohort, release, mint, "X300", LIQUIDITY),
            preview_deadline(anchor, cohort, release, "X300"),
        )
        if liquidity.get("status") != "OBSERVED":
            continue
        total += 1
        universe_verdict = None
        if universe_policy is not None:
            decision_deadline = preview_deadline(anchor, cohort, release, decision_point)
            due, _late = _clock(preview_binding[(cohort, release)], decision_point, lateness)
            point_due = _due_moment(anchor, due) if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1 else None
            universe_verdict = classify_universe_cells(
                _cell(
                    grouped,
                    (cohort, release, mint, decision_point, HOLDER_COUNT),
                    decision_deadline,
                    snapshot_policy=(clock_policy if point_due is not None else None),
                    point_due_at=point_due,
                ),
                _cell(
                    grouped,
                    (cohort, release, mint, decision_point, LIQUIDITY),
                    decision_deadline,
                    snapshot_policy=(clock_policy if point_due is not None else None),
                    point_due_at=point_due,
                ),
                universe_policy,
            )
            universe_counts[str(universe_verdict["status"])] += 1
        prices: dict[str, float | None] = {}
        missing: dict[str, str] = {}
        for point in point_ids:
            cell = _cell(
                grouped,
                (cohort, release, mint, point, PRICE),
                preview_deadline(anchor, cohort, release, point),
            )
            if cell.get("status") == "OBSERVED":
                prices[point] = float(cell["value"])
                missing[point] = "OBSERVED"
            else:
                prices[point] = None
                missing[point] = str(cell.get("status") or "ABSENT")
        observed_prices = [prices[point] for point in point_ids if prices[point] is not None]
        base_price = observed_prices[0] if observed_prices else None
        relative = {
            point: (None if prices[point] is None or base_price in (None, 0) else prices[point] / base_price - 1.0)
            for point in point_ids
        }
        anonymous = hashlib.sha256(f"{seed}:{cohort}:{mint}".encode("utf-8")).hexdigest()[:16]
        examples.append(
            {
                "anonymous_id": anonymous,
                "sample_key": hashlib.sha256(f"{seed}:{anonymous}".encode("utf-8")).hexdigest(),
                "price_relative": relative,
                "liquidity_absolute": liquidity.get("value"),
                "missing_mask": missing,
                **(
                    {"universe_status": universe_verdict["status"], "universe_reasons": universe_verdict["reasons"]}
                    if universe_verdict is not None
                    else {}
                ),
            }
        )
        if features:
            cells = {}
            for feature in features:
                point = feature["point"]
                due, _late = _clock(preview_binding[(cohort, release)], point, lateness)
                point_deadline = preview_deadline(anchor, cohort, release, point)
                decision_deadline = preview_deadline(anchor, cohort, release, decision_point)
                # Same fail-closed boundary as _feature_value_with_lineage.read.
                if point_deadline is None or decision_deadline is None or point_deadline > decision_deadline:
                    cells[feature["name"]] = {"status": "ABSENT"}
                    continue
                cells[feature["name"]] = _cell(
                    grouped, (cohort, release, mint, point, feature["field_id"]),
                    point_deadline,
                    snapshot_policy=(clock_policy if clock_policy == OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1 else None),
                    point_due_at=_due_moment(anchor, due),
                )
            examples[-1]["feature_values"] = {
                name: cell.get("value") if cell.get("status") == "OBSERVED" else None for name, cell in cells.items()
            }
            examples[-1]["feature_status"] = {name: cell.get("status") for name, cell in cells.items()}
    examples.sort(key=lambda item: str(item["sample_key"]))
    selected = examples[:PREVIEW_EXAMPLE_LIMIT]
    for item in selected:
        item.pop("sample_key", None)
    payload = {
        "schema": "smial.hfic-temporal-preview",
        "schema_version": "1.0",
        "preview_sha256": identity,
        "decision_point": decision_point,
        "target_included": False,
        "sampling_rule": "HASH_MEMBERSHIP_SEED",
        "selected_count": len(selected),
        "total_count": total,
        "silent_truncation": False,
        "examples": selected,
        **(
            {
                "universe_policy": snapshot(universe_policy),
                "universe_counts": universe_counts,
                "n_base": total,
            }
            if universe_policy is not None
            else {}
        ),
    }
    encoded = _canonical(payload).encode("utf-8")
    if len(encoded) > PREVIEW_BYTE_LIMIT:
        raise GroundedDiscoveryError("PREVIEW_TOO_LARGE")
    return payload


def _build_recipe_preview(census, observations, spec, binding, *, prior_preview_hashes, universe_policy):
    checked = validate_feature_preview_spec(spec)
    body = {"decision_point": checked["decision_point"], "schedule_lateness_seconds": checked["lateness"],
            "observation_clock_policy": checked["clock_policy"], "features": checked["features"], "predicates": []}
    _require_bound_schedule(binding, body, checked["lateness"])
    from solana_alpha_lab.factory.hfic_research_universe_policy import snapshot
    policy = snapshot(universe_policy) if universe_policy is not None else None
    frozen = temporal_frozen_input(binding)
    recipe = {"decision_point": checked["decision_point"], "features": sorted(checked["features"], key=lambda f: f["name"]),
              "schedule": {"points": checked["point_ids"], "lateness_seconds": checked["lateness"],
                           "observation_clock_policy": checked["clock_policy"]}}
    identity = _sha256({"recipe": recipe, "seed": checked["seed"], "input": frozen, "policy": policy})
    if identity not in prior_preview_hashes and len(set(prior_preview_hashes)) >= MAX_PREVIEW_SPECS:
        raise GroundedDiscoveryError("PREVIEW_ENVELOPE_EXHAUSTED")
    members, cohorts, _seen, duplicates, conflicts = _project_temporal_members(
        census, observations, body, binding, universe_policy=universe_policy, prefix_only=True)
    def counts(rows, *, detail):
        base = [r for r in rows if r.get("in_base")]
        eligible = [r for r in base if r.get("decision_eligible")]
        joint = sum(all(r.get("feature_values", {}).get(f["name"]) is not None for f in checked["features"]) for r in eligible)
        result = {"base_x_n": len(base), "universe": {s: sum(r.get("universe_status") == s for r in base) for s in ("PASS", "FAIL", "UNKNOWN")},
                  "decision_eligible_n": len(eligible), "joint_calculable_n": joint, "joint_unavailable_n": len(eligible)-joint}
        if detail:
            result["features"] = {}
            for f in checked["features"]:
                name = f["name"]
                n = sum(r.get("feature_values", {}).get(name) is not None for r in eligible)
                reasons = defaultdict(int)
                for r in eligible:
                    if r.get("feature_values", {}).get(name) is None:
                        reasons[r.get("feature_reasons", {}).get(name) or "FEATURE_UNAVAILABLE"] += 1
                result["features"][name] = {"calculable_n": n, "unavailable_n": len(eligible)-n, "reason_counts": dict(sorted(reasons.items()))}
        return result
    summary = {"grain": "UNIQUE_MINT_DECISION_TIMESTAMP", "scope": "ALL_ADMITTED_DEPENDENCY_PREFIX",
               "denominator": "DECISION_ELIGIBLE", "counts_truncated": False, "pooled": counts(members, detail=True),
               "by_cohort": [{"cohort_id": c, **counts(list(rows.values()), detail=False)} for c, rows in sorted((str(i["cohort_id"]), cohorts.get(str(i["cohort_id"]), {})) for i in admit_discovery_binding(binding)["cohorts"])],
               "duplicate_delivery_count": duplicates, "membership_integrity_conflict_count": conflicts,
               "unique_mint_n": len({r["identity"][0] for r in members if r.get("in_base")}),
               "unique_decision_n": sum(bool(r.get("in_base")) for r in members),
               "cohort_sums_are_independent": False, "independence": "UNKNOWN"}
    examples = []
    for r in members:
        if not r.get("decision_eligible"):
            continue
        anonymous = hashlib.sha256(f"{checked['seed']}:{r['identity']}".encode()).hexdigest()[:16]
        examples.append({"anonymous_id": anonymous, "feature_values": r["feature_values"],
                         "feature_status": {f["name"]: r.get("feature_reasons", {}).get(f["name"], "OBSERVED") for f in checked["features"]}})
    examples.sort(key=lambda r: r["anonymous_id"])
    payload = {"schema": "smial.hfic-temporal-preview", "schema_version": "1.0", "preview_sha256": identity,
               "decision_point": checked["decision_point"], "target_included": False, "sampling_rule": "HASH_MEMBERSHIP_SEED",
               "selected_count": min(len(examples), PREVIEW_EXAMPLE_LIMIT), "total_count": summary["pooled"]["base_x_n"],
               "sample_population_n": len(examples), "examples_truncated": len(examples)>PREVIEW_EXAMPLE_LIMIT,
               "silent_truncation": False, "examples": examples[:PREVIEW_EXAMPLE_LIMIT], "support_summary": summary,
               "feature_recipe": recipe, "feature_recipe_sha256": _sha256(recipe), "frozen_input": frozen,
               "input_sha256": _sha256({"input": frozen}), "universe_policy": policy}
    if len(_canonical(payload).encode()) > PREVIEW_BYTE_LIMIT:
        raise GroundedDiscoveryError("PREVIEW_TOO_LARGE")
    return payload


def recipe_capabilities() -> dict[str, Any]:
    """Descriptor derived from the validator's closed field/operator policy."""
    return {"fields": {HOLDER_COUNT: sorted(HOLDER_OPS), PRICE: sorted(FEATURE_OPS - {"delta"}),
                       LIQUIDITY: sorted(FEATURE_OPS - {"delta"})},
            "parameters": {"point_value": ["field_id", "point"], "delta": ["field_id", "start", "end"],
                           "return_ratio": ["field_id", "start", "end"], "ratio": ["field_id", "numerator", "denominator"],
                           "drawdown_from_grid_max": ["field_id", "points", "at"], "rebound_from_grid_min": ["field_id", "points", "at"],
                           "elapsed_seconds": ["start", "end"], "utc_hour": ["point"]},
            "units": {"holder_delta": "HOLDER_COUNT", "return_ratio": "DIMENSIONLESS_FRACTION"},
            "constraints": ["HOLDER_START_LT_END_LE_DECISION_BOUND_SCHEDULE", "PIT_LINEAGE_REQUIRED",
                            "MISSING_LATE_CONFLICT_UNAVAILABLE", "RETURN_DENOMINATOR_POSITIVE", "NO_EWM_NO_HOLDER_TARGET",
                            "SUPPORT_IS_NOT_ALPHA", "EXACT_RECIPE_NO_SWEEP"]}


def universe_question_guard(body: Mapping[str, Any], definition: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Prove only direct same-decision-cell dominance. Never edits the recipe."""
    if not isinstance(definition, Mapping):
        return []
    features = {f["name"]: f for f in body["features"]}
    redundant = []
    for predicate in body["predicates"]:
        f = features[predicate["feature"]]
        minima = {definition.get("holder_field_id"): definition.get("min_holders"),
                  definition.get("liquidity_field_id"): definition.get("min_liquidity_usd")}
        if f["op"] != "point_value" or f.get("point") != body["decision_point"] or f.get("field_id") not in minima:
            continue
        minimum = _finite_number(minima[f["field_id"]])
        if minimum is None:
            continue
        op, value = predicate["op"], predicate.get("value")
        impossible = (op == "lt" and value <= minimum) or (op == "lte" and value < minimum) or (op == "between" and predicate["upper"] <= minimum)
        if impossible:
            raise GroundedDiscoveryError("UNIVERSE_IMPOSSIBLE_QUESTION")
        if (op == "gte" and value <= minimum) or (op == "gt" and value < minimum):
            redundant.append(dict(predicate))
    if body["predicates"] and len(redundant) == len(body["predicates"]):
        raise GroundedDiscoveryError("UNIVERSE_NON_DISCRIMINATING_QUESTION")
    return [{"reason_code": "REDUNDANT_UNIVERSE_CONJUNCT", "predicate": p} for p in redundant]


def saved_feature_preview(store, *, journal_scope, operation_sha256, spec_sha256, binding):
    """Verified saved payload; metadata hashes may be read, scientific values never are."""
    from solana_alpha_lab.factory.hfic_research_universe_policy import snapshot
    for record in store.iter_committed_records():
        if getattr(record.record_kind, "value", record.record_kind) != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
            canonical = wrapper.get("payload_canonical", "")
            body = json.loads(canonical)
        except (ValueError, TypeError):
            continue
        if not isinstance(body, dict) or any(body.get(k) != v for k, v in {
            "artifact_kind": "DISCOVERY_FEATURE_PREVIEW", "journal_scope": journal_scope,
            "operation_sha256": operation_sha256, "spec_sha256": spec_sha256}.items()):
            continue
        if hashlib.sha256(record.payload_json.encode()).hexdigest() != record.payload_sha256 or hashlib.sha256(canonical.encode()).hexdigest() != wrapper.get("payload_sha256"):
            raise GroundedDiscoveryError("PREVIEW_PAYLOAD_INTEGRITY_MISMATCH")
        payload = body.get("preview_payload")
        if payload is None:
            return {"preview_sha256": body["preview_sha256"], "detail_status": "LEGACY_PREVIEW_DETAIL_UNAVAILABLE"}
        if not isinstance(payload, dict) or _sha256(payload) != body.get("preview_payload_sha256") or payload.get("preview_sha256") != body.get("preview_sha256"):
            raise GroundedDiscoveryError("PREVIEW_PAYLOAD_INTEGRITY_MISMATCH")
        if payload.get("frozen_input") != temporal_frozen_input(binding):
            raise GroundedDiscoveryError("PREVIEW_INPUT_IDENTITY_MISMATCH")
        policy = payload.get("universe_policy")
        if policy is not None and snapshot(policy) != policy:
            raise GroundedDiscoveryError("PREVIEW_POLICY_IDENTITY_MISMATCH")
        recipe = payload.get("feature_recipe")
        if not isinstance(recipe, dict) or _sha256(recipe) != payload.get("feature_recipe_sha256"):
            raise GroundedDiscoveryError("PREVIEW_RECIPE_IDENTITY_MISMATCH")
        return dict(payload)
    raise GroundedDiscoveryError("PREVIEW_SAVED_PAYLOAD_NOT_FOUND")


def stored_preview_hashes(store: Any, journal_scope: str) -> list[str]:
    found: list[str] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if (
            isinstance(body, dict)
            and body.get("artifact_kind") == "DISCOVERY_FEATURE_PREVIEW"
            and body.get("journal_scope") == journal_scope
            and isinstance(body.get("preview_sha256"), str)
        ):
            found.append(str(body["preview_sha256"]))
    return found


def persist_feature_preview(
    store: Any,
    *,
    journal_scope: str,
    preview: Mapping[str, Any],
    git_sha: str,
    input_sha256: str = "",
    operation_sha256: str | None = None,
    spec_sha256: str | None = None,
) -> None:
    """Remember a preview in the store. Identity includes the journal and the input."""

    digest = str(preview.get("preview_sha256") or "")
    if operation_sha256 and spec_sha256:
        for record in store.iter_committed_records():
            if getattr(record.record_kind, "value", record.record_kind) != "RESEARCH_ARTIFACT":
                continue
            try:
                existing = json.loads(json.loads(record.payload_json).get("payload_canonical", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(existing, dict) and all(existing.get(k) == v for k, v in {
                "artifact_kind": "DISCOVERY_FEATURE_PREVIEW", "journal_scope": journal_scope,
                "preview_sha256": digest, "operation_sha256": operation_sha256, "spec_sha256": spec_sha256}.items()):
                return
        identity = _sha256({"journal_scope": journal_scope, "preview_sha256": digest,
                            "input_sha256": input_sha256, "operation_sha256": operation_sha256, "spec_sha256": spec_sha256})
    else:
        if digest in stored_preview_hashes(store, journal_scope):
            return
        identity = hashlib.sha256(f"{journal_scope}:{digest}:{input_sha256}".encode("utf-8")).hexdigest()
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = datetime.now(timezone.utc)
    body = {
        "artifact_kind": "DISCOVERY_FEATURE_PREVIEW",
        "journal_scope": journal_scope,
        "preview_sha256": digest,
        "target_included": False,
        "selected_count": preview.get("selected_count"),
        "total_count": preview.get("total_count"),
    }
    if "support_summary" in preview:
        body.update(preview_payload=dict(preview), preview_payload_sha256=_sha256(preview), input_sha256=input_sha256)
    if operation_sha256:
        body["operation_sha256"] = operation_sha256
    if spec_sha256:
        body["spec_sha256"] = spec_sha256
    canonical = _canonical(body)
    payload = {
        "artifact_kind": "DISCOVERY_FEATURE_PREVIEW",
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    record_id = f"HFIC-ART-PREVIEW-{identity[:40].upper()}"
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-PREVIEW-{identity[:24].upper()}",
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
    store.append([event], transaction_id=event.transaction_id)


def _public_query_from_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    query = recipe.get("spec")
    if not isinstance(query, Mapping):
        raise GroundedDiscoveryError("EXPERIMENT_RECIPE_INVALID")
    body = query.get("scientific_body")
    if not isinstance(body, Mapping):
        raise GroundedDiscoveryError("EXPERIMENT_RECIPE_INVALID")
    if is_episode_body(body):
        if query.get("schema_version") != TEMPORAL_SCHEMA_VERSION_EPISODES:
            raise GroundedDiscoveryError("EXPERIMENT_RECIPE_INVALID")
        public_episode = {
            "schema": TEMPORAL_SCHEMA,
            "schema_version": TEMPORAL_SCHEMA_VERSION_EPISODES,
            "query_id": query.get("query_id") or "frozen-recipe",
            "population": EPISODE_POPULATION,
            "anchor_kind": body["anchor_kind"],
            "time_contract": dict(body["time_contract"]),
            "search_tier": query.get("search_tier") or "COMPOUND_SCREEN",
            "budget_allocation": query.get("budget_allocation") or "AUTO",
            "decision": {
                "point_id": body["decision_point"],
                "time_policy": "RESOLVER_AVAILABILITY_CUTOFF",
            },
            "schedule": {"observation_clock_policy": body["observation_clock_policy"]},
            "features": body["features"],
            "all": body["predicates"],
            "target": body["target"],
            "entry_model": body["entry_model"],
            "cost_profile": body.get("cost_profile"),
            "evaluation": body.get("evaluation") or {},
        }
        if query.get("adaptation_of") is not None:
            public_episode["adaptation_of"] = query["adaptation_of"]
        return public_episode
    schedule: dict[str, Any] = {"lateness_seconds": body["schedule_lateness_seconds"]}
    # Preserve non-default clock policy so recipe replay keeps snapshot
    # semantics and scientific identity. EVENT_TIME_V1 stays omitted.
    clock_policy = body.get("observation_clock_policy")
    if not clock_policy:
        clock_policy = recipe.get("observation_clock_policy")
    if (
        isinstance(clock_policy, str)
        and clock_policy
        and clock_policy != OBSERVATION_CLOCK_EVENT_TIME_V1
    ):
        schedule["observation_clock_policy"] = clock_policy
    public = {
        "schema": TEMPORAL_SCHEMA,
        "schema_version": TEMPORAL_SCHEMA_VERSION,
        "query_id": query.get("query_id") or "frozen-recipe",
        "population": "BASE_X",
        "search_tier": query.get("search_tier") or "COMPOUND_SCREEN",
        "budget_allocation": query.get("budget_allocation") or "AUTO",
        "decision": {"point_id": body["decision_point"], "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        "schedule": schedule,
        "features": body["features"],
        "all": body["predicates"],
        "target": body["target"],
        "entry_model": body["entry_model"],
        "cost_profile": body.get("cost_profile"),
        "evaluation": body.get("evaluation") or {},
    }
    if query.get("adaptation_of") is not None:
        public["adaptation_of"] = query["adaptation_of"]
    return public


def temporal_holder_claim_identity(result: Mapping[str, Any]) -> dict[str, str]:
    """Exact card labels derived from the saved recipe, only for the new surface.

    Legacy PRICE/LIQUIDITY packets keep their identities and readout bytes.
    This is display/binding, never a query parser or a second evaluator.
    """
    recipe = result.get("experiment_recipe")
    if not isinstance(recipe, Mapping):
        return {}
    saved = recipe.get("spec")
    body = saved.get("scientific_body") if isinstance(saved, Mapping) else None
    if not isinstance(body, Mapping) or not any(f.get("field_id") == HOLDER_COUNT for f in body.get("features", []) if isinstance(f, Mapping)):
        return {}
    public = _public_query_from_recipe(recipe)
    bound = validate_temporal_query(public)
    if bound["spec_sha256"] != result.get("spec_sha256") or bound["spec_sha256"] != recipe.get("scientific_identity"):
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    features, predicates = body["features"], body["predicates"]
    x = _canonical({"features": features, "predicates": predicates})
    if len(features) == len(predicates) == 1 and features[0]["op"] == "point_value" and predicates[0]["feature"] == features[0]["name"]:
        feature, predicate = features[0], predicates[0]
        symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}.get(predicate["op"])
        if symbol:
            threshold = json.dumps(predicate["value"], allow_nan=False)
            x = f"{feature['field_id']} point_value {feature['point']} {symbol} {threshold}"
    target = body["target"]
    horizon = f"{target['reference_point']} -> {target['exit_point']}"
    return {"primary_x_family": x, "primary_y": f"{target['kind']} {horizon}",
            "horizon_notional": f"{horizon}; {target['kind']}; no executable notional",
            "decision_timestamp": body["decision_point"], "target": temporal_target_label(public)}


def _require_manifest_and_cutoff(
    spec: Mapping[str, Any],
    frozen_input: Sequence[Mapping[str, Any]],
    data_root: Path,
) -> None:
    """A foreign manifest or an early cutoff stops before observation values are read."""

    cutoff = _parse_time(spec.get("availability_cutoff"))
    if cutoff is None:
        raise GroundedDiscoveryError("CUTOFF_REJECTED")
    bindings = spec.get("data_bindings")
    if not isinstance(bindings, list):
        raise GroundedDiscoveryError("MANIFEST_MISMATCH")
    manifest_ids: list[str] = []
    seen_ids: set[str] = set()
    for item in frozen_input:
        manifest_id = item.get("dataset_manifest_id") if isinstance(item, Mapping) else None
        if not isinstance(manifest_id, str) or not manifest_id:
            raise GroundedDiscoveryError("MANIFEST_MISMATCH")
        if manifest_id not in seen_ids:
            seen_ids.add(manifest_id)
            manifest_ids.append(manifest_id)
    for manifest_id in manifest_ids:
        match = [
            binding
            for binding in bindings
            if isinstance(binding, Mapping)
            and binding.get("source_kind") == "DATASET_MANIFEST"
            and binding.get("stable_id") == manifest_id
        ]
        if len(match) != 1:
            raise GroundedDiscoveryError("MANIFEST_MISMATCH")
        manifest_path = data_root / "datasets" / "manifests" / f"{manifest_id}.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GroundedDiscoveryError("MANIFEST_MISMATCH") from exc
        expected = match[0].get("expected_content_sha256_or_dataset_fingerprint")
        actual = manifest.get("dataset_fingerprint")
        if (
            not isinstance(expected, str)
            or not expected
            or not isinstance(actual, str)
            or not actual
            or actual != expected
        ):
            raise GroundedDiscoveryError("MANIFEST_MISMATCH")
        available = _parse_time(manifest.get("first_reliable_available_at"))
        if available is None or cutoff < available:
            raise GroundedDiscoveryError("CUTOFF_REJECTED")


def run_temporal_fixed_time_from_spec(
    spec: Mapping[str, Any],
    *,
    root: Path,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Production adapter. Identity is checked before the evaluator runs."""

    del root
    hooks = dict(capture_hooks or {})
    data_root = hooks.get("data_root")
    if not isinstance(data_root, Path):
        raise GroundedDiscoveryError("DATA_ROOT_REQUIRED")
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), Mapping) else {}
    recipe = parameters.get("temporal_recipe") if isinstance(parameters, Mapping) else None
    if not isinstance(recipe, Mapping):
        raise GroundedDiscoveryError("EXPERIMENT_RECIPE_INVALID")
    public = _public_query_from_recipe(recipe)
    pre = validate_temporal_query(public)
    stored_identity = str(recipe.get("scientific_identity") or "")
    if stored_identity and pre["spec_sha256"] != stored_identity:
        raise GroundedDiscoveryError("EXPERIMENT_RECIPE_IDENTITY_MISMATCH")
    frozen_input = recipe.get("frozen_input")
    if not isinstance(frozen_input, list) or not frozen_input:
        raise GroundedDiscoveryError("FROZEN_INPUT_REQUIRED")
    from solana_alpha_lab.factory.hfic_grounded_discovery import (
        load_admitted_partition_rows,
        result_sha256,
    )
    from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming

    if "data_bindings" in spec or "availability_cutoff" in spec:
        _require_manifest_and_cutoff(spec, frozen_input, data_root)
    partitions = []
    binding_cohorts = []
    for item in frozen_input:
        if not isinstance(item, Mapping):
            raise GroundedDiscoveryError("FROZEN_INPUT_MISMATCH")
        census_rel = item.get("census_rel")
        obs_rel = item.get("observations_rel")
        if not isinstance(census_rel, str) or not isinstance(obs_rel, str):
            raise GroundedDiscoveryError("FROZEN_INPUT_MISMATCH")
        census_path = data_root / census_rel
        obs_path = data_root / obs_rel
        if (
            sha256_file_streaming(census_path) != item.get("census_sha256")
            or sha256_file_streaming(obs_path) != item.get("observations_sha256")
        ):
            raise GroundedDiscoveryError("FROZEN_INPUT_MISMATCH")
        partitions.append((str(item.get("cohort_id")), census_path, obs_path))
        binding_cohorts.append(dict(item))
    loaded = load_admitted_partition_rows(
        data_root=None,
        binding_doc={"cohorts": binding_cohorts},
        partitions=partitions,
        census_path=None,
        observations_path=None,
    )
    from solana_alpha_lab.factory.hfic_research_universe_policy import (
        UniversePolicyError,
        recipe_policy,
    )

    try:
        frozen_policy = recipe_policy(recipe)
    except UniversePolicyError as exc:
        raise GroundedDiscoveryError(exc.code) from exc
    computed = execute_temporal_discovery(
        loaded["census"],
        loaded["observations"],
        public,
        loaded["cohorts"],
        universe_policy=frozen_policy,
    )
    summary = computed["summary"]
    return {
        "status": "COMPLETE",
        "terminal": "INCONCLUSIVE",
        "claim_level": summary.get("claim_level"),
        "provider_api_rpc_wss_calls": 0,
        "labeled_net_return": False,
        "target_kind": summary.get("target_kind"),
        "spec_sha256": summary.get("spec_sha256"),
        "result_sha256": result_sha256(summary),
        "summary": summary,
    }


def execute_fixed_time_proxy_capability(
    spec: Mapping[str, Any],
    *,
    root: Path,
    authority_phrase: str | None = None,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Registry entrypoint. The frozen recipe files are the only rows."""

    del authority_phrase
    hooks = dict(capture_hooks or {})
    data_root = hooks.get("data_root")
    if not isinstance(data_root, Path):
        raise GroundedDiscoveryError("DATA_ROOT_REQUIRED")
    recipe = spec.get("experiment_recipe") if isinstance(spec.get("experiment_recipe"), Mapping) else None
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), Mapping) else None
    if recipe is None and isinstance(parameters, Mapping):
        wrapped = spec
    elif isinstance(recipe, Mapping):
        wrapped = {"parameters": {"temporal_recipe": recipe}}
        if isinstance(spec.get("data_bindings"), list):
            wrapped["data_bindings"] = spec["data_bindings"]
        if "availability_cutoff" in spec:
            wrapped["availability_cutoff"] = spec["availability_cutoff"]
    else:
        raise GroundedDiscoveryError("EXPERIMENT_RECIPE_INVALID")
    computed = run_temporal_fixed_time_from_spec(
        wrapped,
        root=root,
        capture_hooks={"data_root": data_root},
    )
    computed["capability_id"] = TEMPORAL_CAPABILITY_ID
    computed["root_used"] = Path(root).name
    computed["labeled_net_return"] = False
    return computed


def run_registered_fixed_time_proxy(
    *,
    root: Path,
    registry_path: Path,
    recipe: Mapping[str, Any],
    data_root: Path,
    census: Sequence[Mapping[str, Any]] = (),
    observations: Sequence[Mapping[str, Any]] = (),
    binding: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    del census, observations, binding
    document = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8"))
    rows = document.get("capabilities") if isinstance(document, Mapping) else None
    if not isinstance(rows, list):
        raise GroundedDiscoveryError("CAPABILITY_REGISTRY_INVALID")
    found = next(
        (item for item in rows if isinstance(item, Mapping) and item.get("capability_id") == TEMPORAL_CAPABILITY_ID),
        None,
    )
    if not isinstance(found, Mapping):
        raise GroundedDiscoveryError("CAPABILITY_NOT_REGISTERED")
    if found.get("status") != "ACCEPTED" or int(found.get("max_provider_calls") or 0) != 0:
        raise GroundedDiscoveryError("CAPABILITY_NOT_ACCEPTED")
    entrypoint = str(found.get("entrypoint") or "")
    module_name, _, function_name = entrypoint.partition(":")
    if function_name != "execute_fixed_time_proxy_capability":
        raise GroundedDiscoveryError("CAPABILITY_ENTRYPOINT_MISMATCH")
    handler = getattr(importlib.import_module(module_name), function_name)
    return handler(
        {"experiment_recipe": recipe},
        root=root,
        capture_hooks={"data_root": data_root},
    )
