"""Ordinary grounded discovery.

The numeric recipe reads production-shaped census and observation rows.
It does not accept pre-labeled ``in_base_x`` or ``synthetic_target`` as the
production entry. Live market Forge is not this module's job. A recorded
look is a ResearchStore artifact, not a scientific-slot reservation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ORDINARY_GROUNDED_DISCOVERY_V1 = "ORDINARY_GROUNDED_DISCOVERY_V1"
DISCOVERY_CONTRACT_VERSION = "FORGE_GROUNDED_DISCOVERY_V1"
ORDINARY_DISCOVERY_READY = "ORDINARY_DISCOVERY_READY"
LIVE_DATASET_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
LIVE_EVIDENCE_ROLE = "EXPLORATORY_REUSE"
PRICE = "FIELD-USD-PRICE-001"
LIQUIDITY = "FIELD-LIQUIDITY-USD-001"
ALLOWED_FIELDS = frozenset({PRICE, LIQUIDITY})
POINT_OFFSET = {
    "X300": 300,
    "Y900": 900,
    "Y1800": 1800,
    "Y3600": 3600,
    "Y7200": 7200,
    "Y14400": 14400,
    "Y43200": 43200,
    "Y86400": 86400,
}
MAX_MAIN_QUERY_SPECS = 6
MAX_ADAPTIVE_REFINEMENTS = 2
MAX_EXPLANATORY = 3
CALCULATION_VERSION = "FORGE_GROUNDED_DISCOVERY_CALC_V1"
PIT_LATENESS_SECONDS = 300
_CONTENT_AXES = ("population", "decision_timestamp", "target", "estimand")
_BLOCKING_RELATIONS = frozenset({"EXACT_SCOPE_MATCH", "EXACT_VALID_CLOSE"})
_REL_RE = re.compile(
    r"^REL-(\d{8}T\d{6}Z)-(\d{8}T\d{6}Z)$"
)


class GroundedDiscoveryError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def query_spec_sha256(spec: Mapping[str, Any]) -> str:
    body = {key: spec[key] for key in sorted(spec) if key != "spec_sha256"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _point_offset(point_id: object) -> int:
    if not isinstance(point_id, str) or point_id not in POINT_OFFSET:
        raise GroundedDiscoveryError("POINT_NOT_IN_ALLOWLIST")
    return POINT_OFFSET[point_id]


def validate_query_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed before any value read. Cohort id is not an explanatory feature."""

    if not isinstance(spec, Mapping):
        raise GroundedDiscoveryError("QUERY_SPEC_INVALID")
    decision_points = spec.get("decision_points")
    decision_fields = spec.get("decision_fields")
    explanatory = spec.get("explanatory") or []
    if not isinstance(decision_points, list) or not decision_points:
        raise GroundedDiscoveryError("DECISION_POINTS_REQUIRED")
    if not isinstance(decision_fields, list) or not decision_fields:
        raise GroundedDiscoveryError("DECISION_FIELDS_REQUIRED")
    if len(decision_points) + len(decision_fields) > 6:
        raise GroundedDiscoveryError("QUERY_TOO_WIDE")
    if not isinstance(explanatory, list) or len(explanatory) > MAX_EXPLANATORY:
        raise GroundedDiscoveryError("EXPLANATORY_LIMIT")
    if any(str(item) == "cohort_id" for item in explanatory):
        raise GroundedDiscoveryError("COHORT_NOT_A_FEATURE")
    for point in decision_points:
        _point_offset(point)
    for field in decision_fields:
        if field not in ALLOWED_FIELDS:
            raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")
    target_point = spec.get("target_point")
    target_field = spec.get("target_field")
    target_offset = _point_offset(target_point)
    if target_field not in ALLOWED_FIELDS:
        raise GroundedDiscoveryError("FIELD_NOT_IN_ALLOWLIST")
    if target_offset <= max(_point_offset(point) for point in decision_points):
        raise GroundedDiscoveryError("TARGET_NOT_AFTER_DECISION")
    query_id = spec.get("query_id")
    if not isinstance(query_id, str) or not query_id.strip():
        raise GroundedDiscoveryError("QUERY_ID_REQUIRED")
    population = spec.get("population")
    if population != "BASE_X":
        raise GroundedDiscoveryError("POPULATION_NOT_BASE_X")
    return {
        "query_id": query_id,
        "decision_points": list(decision_points),
        "decision_fields": list(decision_fields),
        "target_point": target_point,
        "target_field": target_field,
        "explanatory": [str(item) for item in explanatory],
        "population": "BASE_X",
        "spec_sha256": query_spec_sha256(spec),
    }


def admit_discovery_binding(cohorts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Metadata gate. Ambiguous role stops before value read and before a slot."""

    if not cohorts:
        raise GroundedDiscoveryError("DISCOVERY_BINDING_EMPTY")
    admitted = []
    for item in cohorts:
        role = item.get("evidence_role")
        dataset_id = item.get("dataset_id")
        if role != LIVE_EVIDENCE_ROLE or dataset_id != LIVE_DATASET_ID:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
        for key in ("cohort_id", "release_id", "census_sha256", "observations_sha256"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise GroundedDiscoveryError("DISCOVERY_BINDING_INCOMPLETE")
        if item.get("holdout") is True:
            raise GroundedDiscoveryError("HOLDOUT_PROTECTED")
        admitted.append(
            {
                "cohort_id": item["cohort_id"],
                "release_id": item["release_id"],
                "census_sha256": item["census_sha256"],
                "observations_sha256": item["observations_sha256"],
                "evidence_role": LIVE_EVIDENCE_ROLE,
            }
        )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "population": "BASE_X",
        "not_all_census_rows": True,
        "allowed_fields": sorted(ALLOWED_FIELDS),
        "cohorts": admitted,
        "holdouts_not_touched": ["UNTOUCHED_FORWARD_HOLDOUT"],
    }


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _flag_token(flags: Mapping[str, Any], name: str) -> str:
    if name not in flags or flags.get(name) is None:
        return "MISSING"
    value = flags.get(name)
    if value is True:
        return "True"
    if value is False:
        return "False"
    raise GroundedDiscoveryError("EXPLANATORY_INVALID")


def summarize_discovery_query(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    *,
    overlap_members: Sequence[str] | None = None,
    required_cohorts: Sequence[str] | None = None,
    overlapping_cohorts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Pooled, cohort, and calendar summaries. Never emits an alpha claim.

    Every requested cohort stays in the table, including a zero usable count.
    A missing explanatory flag stays ``MISSING`` and is not coerced to false.
    """

    bound = validate_query_spec(spec)
    overlap_known = overlap_members is not None
    overlap = set(overlap_members or [])
    blocked = set(overlapping_cohorts or [])
    missing = {"absent": 0, "censored_late": 0, "missing_typed": 0, "other": 0, "leaked": 0}
    exclusions: dict[str, int] = defaultdict(int)
    by_cohort: dict[str, list[float]] = defaultdict(list)
    by_block: dict[str, list[float]] = defaultdict(list)
    by_flag: dict[str, list[float]] = defaultdict(list)
    cohort_denoms: dict[str, int] = defaultdict(int)
    block_denoms: dict[str, int] = defaultdict(int)
    flag_denoms: dict[str, int] = defaultdict(int)
    cohort_admissible: dict[str, int] = defaultdict(int)
    cohort_overlap: dict[str, int] = defaultdict(int)
    block_overlap: dict[str, int] = defaultdict(int)
    for cohort in required_cohorts or []:
        cohort_denoms.setdefault(str(cohort), 0)
    base_n = 0
    admissible_n = 0
    pooled_values: list[float] = []
    for member in members:
        if member.get("in_base_x") is not True:
            reason = str(member.get("exclusion_reason") or "NOT_BASE_X")
            exclusions[reason] += 1
            continue
        base_n += 1
        cohort = str(member.get("cohort_id") or "UNKNOWN")
        block = str(member.get("calendar_block") or "UNBLOCKED")
        cohort_denoms[cohort] += 1
        block_denoms[block] += 1
        if str(member.get("member_id") or "") in overlap:
            cohort_overlap[cohort] += 1
            block_overlap[block] += 1
        flags = member.get("explanatory") or {}
        if not isinstance(flags, Mapping):
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
        flag_key = ",".join(
            f"{name}={_flag_token(flags, name)}" for name in bound["explanatory"]
        ) or "NONE"
        flag_denoms[flag_key] += 1
        if member.get("decision_ready") is not True:
            exclusions["DECISION_NOT_READY"] += 1
            continue
        admissible_n += 1
        cohort_admissible[cohort] += 1
        decision_at = _parse_time(member.get("decision_at"))
        target_at = _parse_time(member.get("target_at"))
        state = str(member.get("target_state") or "ABSENT")
        if decision_at is None:
            missing["other"] += 1
            exclusions["DECISION_TIME_MISSING"] += 1
            continue
        if target_at is not None and target_at <= decision_at:
            missing["leaked"] += 1
            exclusions["LEAKED"] += 1
            continue
        if state == "ABSENT":
            missing["absent"] += 1
            exclusions["ABSENT"] += 1
            continue
        if state == "CENSORED_LATE":
            missing["censored_late"] += 1
            exclusions["CENSORED_LATE"] += 1
            continue
        if state == "MISSING_TYPED":
            missing["missing_typed"] += 1
            exclusions["MISSING_TYPED"] += 1
            continue
        if state != "OBSERVED" or target_at is None:
            missing["other"] += 1
            exclusions["TARGET_NOT_OBSERVED"] += 1
            continue
        raw = member.get("target_value", member.get("synthetic_target"))
        if raw is None:
            missing["missing_typed"] += 1
            exclusions["MISSING_TYPED"] += 1
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise GroundedDiscoveryError("TARGET_VALUE_INVALID") from exc
        pooled_values.append(value)
        by_cohort[cohort].append(value)
        by_block[block].append(value)
        by_flag[flag_key].append(value)

    def _view(
        name: str,
        values: Sequence[float],
        denominator: int,
        *,
        independent: bool,
        admissible: int | None = None,
    ) -> dict[str, Any]:
        mean = _mean(list(values))
        return {
            "view": name,
            "denominator_base_x": denominator,
            "feature_admissible": denominator if admissible is None else admissible,
            "target_observed_after_decision": len(values),
            "mean_target": mean,
            "mean_synthetic_target": mean,
            "independent_replication": independent,
        }

    overlap_n = sum(
        1
        for item in members
        if item.get("in_base_x") is True and str(item.get("member_id") or "") in overlap
    )
    calendar_overlap = bool(blocked)
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "query_id": bound["query_id"],
        "spec_sha256": bound["spec_sha256"],
        "population": "BASE_X",
        "base_x_n": base_n,
        "feature_admissible_n": admissible_n,
        "later_target_observed_n": len(pooled_values),
        "not_per_cell_denominator": True,
        "engine_emits_alpha": False,
        "missing_is_not_zero": True,
        "cohort_id_is_not_a_feature": True,
        "missing": missing,
        "exclusion_reasons": dict(sorted(exclusions.items())),
        "pooled": _view(
            "pooled",
            pooled_values,
            base_n,
            independent=overlap_known and overlap_n == 0 and not calendar_overlap,
            admissible=admissible_n,
        ),
        "by_cohort": [
            _view(
                key,
                by_cohort.get(key, []),
                cohort_denoms[key],
                independent=(
                    overlap_known
                    and cohort_overlap[key] == 0
                    and key not in blocked
                    and not calendar_overlap
                ),
                admissible=cohort_admissible[key],
            )
            for key in sorted(cohort_denoms)
        ],
        "by_calendar_block": [
            _view(
                key,
                by_block.get(key, []),
                block_denoms[key],
                independent=overlap_known and block_overlap[key] == 0 and not calendar_overlap,
            )
            for key in sorted(block_denoms)
        ],
        "by_explanatory": [
            _view(key, by_flag.get(key, []), flag_denoms[key], independent=False)
            for key in sorted(flag_denoms)
        ],
        "overlap_exposed_base_x": overlap_n,
        "overlap_is_not_independent_replication": overlap_n > 0 or calendar_overlap,
        "calendar_overlap_is_not_independent_replication": calendar_overlap,
    }


def classify_query_look(
    previous: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Cost budget. Same bytes are a retry. A changed question is a new variant."""

    bound = validate_query_spec(spec)
    digest = bound["spec_sha256"]
    mains = [
        item
        for item in previous
        if item.get("look_class") == "MAIN" and item.get("new_look") is True
    ]
    adaptive = [
        item
        for item in previous
        if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True
    ]
    if any(item.get("spec_sha256") == digest for item in previous):
        return {
            "spec_sha256": digest,
            "new_look": False,
            "look_class": "RETRY_SAME_BYTES",
            "main_count": len(mains),
            "adaptive_count": len(adaptive),
        }
    same_family = [
        item for item in previous if item.get("query_id") == bound["query_id"] and item.get("new_look") is True
    ]
    look_class = "ADAPTIVE" if same_family else "MAIN"
    if look_class == "MAIN" and len(mains) >= MAX_MAIN_QUERY_SPECS:
        raise GroundedDiscoveryError("QUERY_MAIN_BUDGET_EXHAUSTED")
    if look_class == "ADAPTIVE" and len(adaptive) >= MAX_ADAPTIVE_REFINEMENTS:
        raise GroundedDiscoveryError("QUERY_ADAPTIVE_BUDGET_EXHAUSTED")
    return {
        "query_id": bound["query_id"],
        "spec_sha256": digest,
        "new_look": True,
        "look_class": look_class,
        "main_count": len(mains) + int(look_class == "MAIN"),
        "adaptive_count": len(adaptive) + int(look_class == "ADAPTIVE"),
    }


def _scope_missing(scope: Mapping[str, Any], *, prefix: str) -> list[str]:
    missing = [
        f"{prefix}{key}"
        for key in _CONTENT_AXES
        if scope.get(key) in (None, "")
    ]
    if scope.get("evidence_surface_mode") in (None, ""):
        missing.append(f"{prefix}evidence_surface_mode")
    return missing


def _valid_close(prior: Mapping[str, Any]) -> bool:
    status = str(prior.get("memory_status") or "")
    reason = str(prior.get("reason_code") or "")
    if status in {"HARD_CLOSE", "PARK"}:
        return True
    return reason.startswith("KILL_") or reason.startswith("CLOSE_") or reason.startswith("PARK_")


def bind_prior_scope_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Attach relations. Equivalent valid closes and unknown axes stop freeze."""

    body = dict(evidence)
    candidate_scope = body.get("candidate_scope")
    priors = body.get("priors")
    if not isinstance(candidate_scope, Mapping) or not isinstance(priors, list):
        return body
    relations = []
    for prior in priors:
        if not isinstance(prior, Mapping):
            continue
        relation = prior_scope_relation(candidate_scope, prior)
        if relation in _BLOCKING_RELATIONS:
            raise GroundedDiscoveryError("EXACT_PRIOR_SCOPE_MATCH")
        if relation == "UNKNOWN_SCOPE_NEEDS_RESOLUTION":
            raise GroundedDiscoveryError("UNKNOWN_PRIOR_SCOPE")
        relations.append(
            {
                "question_id": prior.get("question_id"),
                "hypothesis_version_id": prior.get("hypothesis_version_id"),
                "relation": relation,
                "question_id_is_not_a_scientific_difference": True,
            }
        )
    body["prior_scope_relations"] = relations
    return body


def prior_scope_relation(
    candidate: Mapping[str, Any],
    prior: Mapping[str, Any],
) -> str:
    """Question id is not a scientific axis.

    A missing required axis is unresolved, not a match and not a free pass.
    A CONTROL representation-bound negative does not close an unseen richer
    ordinary scope. The same content on the same surface still blocks,
    including a rename of ``question_id``.
    """

    missing = _scope_missing(candidate, prefix="") + _scope_missing(prior, prefix="prior.")
    if missing:
        return "UNKNOWN_SCOPE_NEEDS_RESOLUTION"
    content_same = all(candidate.get(key) == prior.get(key) for key in _CONTENT_AXES)
    surface_same = candidate.get("evidence_surface_mode") == prior.get("evidence_surface_mode")
    prior_surface = str(prior.get("evidence_surface_mode") or "")
    candidate_surface = str(candidate.get("evidence_surface_mode") or "")
    candidate_scope = candidate.get("representation_scope")
    prior_scope = prior.get("representation_scope")
    richer_ordinary = (
        prior_surface == "CURRENT_REPRESENTATION_CONTROL_V1"
        and candidate_surface == ORDINARY_GROUNDED_DISCOVERY_V1
        and candidate_scope not in (None, "")
        and candidate_scope != prior_scope
    )
    if content_same and surface_same:
        if _valid_close(prior):
            return "EXACT_VALID_CLOSE"
        return "EXACT_SCOPE_MATCH"
    if not content_same:
        return "SCOPE_DISTINCT"
    if richer_ordinary:
        return "SCOPED_CONTROL_DOES_NOT_BLOCK"
    return "SCOPE_DISTINCT"


def _cohort_window(cohort_id: str) -> tuple[datetime, datetime] | None:
    match = _REL_RE.match(cohort_id)
    if match is None:
        return None
    start = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ")
    end = datetime.strptime(match.group(2), "%Y%m%dT%H%M%SZ")
    return start, end


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deadline(anchor: datetime, offset_seconds: int) -> datetime:
    return anchor + timedelta(seconds=offset_seconds + PIT_LATENESS_SECONDS)


def _latest_cells(observations: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    best: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in observations:
        mint = str(row.get("mint") or "")
        point = str(row.get("point_id") or "")
        field = str(row.get("field_id") or "")
        if not mint or not point or not field:
            continue
        key = (mint, point, field)
        previous = best.get(key)
        if previous is None:
            best[key] = row
            continue
        current_at = _parse_time(row.get("first_reliable_available_at"))
        previous_at = _parse_time(previous.get("first_reliable_available_at"))
        if current_at is not None and (previous_at is None or current_at >= previous_at):
            best[key] = row
    return best


def _window_overlaps(cohorts: Sequence[Mapping[str, Any]]) -> set[str]:
    parsed: list[tuple[str, datetime, datetime]] = []
    for item in cohorts:
        cohort_id = str(item.get("cohort_id") or "")
        start = _parse_time(item.get("window_start"))
        end = _parse_time(item.get("window_end"))
        if start is None or end is None:
            inferred = _cohort_window(cohort_id)
            if inferred is None:
                continue
            start, end = inferred
        parsed.append((cohort_id, start, end))
    blocked: set[str] = set()
    for index, (left_id, left_start, left_end) in enumerate(parsed):
        for right_id, right_start, right_end in parsed[index + 1 :]:
            if max(left_start, right_start) < min(left_end, right_end):
                blocked.add(left_id)
                blocked.add(right_id)
    return blocked


def _explanatory_flags(
    cells: Mapping[tuple[str, str, str], Mapping[str, Any]],
    mint: str,
    rules: Sequence[Mapping[str, Any]],
    *,
    anchor: datetime,
) -> dict[str, bool | None]:
    flags: dict[str, bool | None] = {}
    for rule in rules:
        name = str(rule.get("name") or "")
        if not name or name == "cohort_id":
            raise GroundedDiscoveryError("COHORT_NOT_A_FEATURE")
        point = str(rule.get("point_id") or "X300")
        field = str(rule.get("field_id") or "")
        cell = cells.get((mint, point, field))
        if cell is None or str(cell.get("state") or "") != "OBSERVED":
            flags[name] = None
            continue
        available = _parse_time(cell.get("first_reliable_available_at"))
        if available is None or available > _deadline(anchor, _point_offset(point)):
            flags[name] = None
            continue
        observed = _as_float(cell.get("typed_value"))
        threshold = rule.get("threshold")
        if observed is None or threshold is None:
            flags[name] = None
            continue
        op = str(rule.get("op") or "gte")
        if op == "gte":
            flags[name] = observed >= float(threshold)
        elif op == "lt":
            flags[name] = observed < float(threshold)
        else:
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    return flags


def execute_discovery_from_rows(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute BASE_X, PIT features and a later target from production-shaped rows.

    Role and holdout come from ``binding``. They are not defaulted here.
    Eligibility does not look at the target. Traders are not required.
    """

    bound_spec = validate_query_spec(spec)
    for item in binding:
        if "holdout" not in item:
            raise GroundedDiscoveryError("HOLDOUT_UNRESOLVED")
        if "evidence_role" not in item:
            raise GroundedDiscoveryError("DISCOVERY_ROLE_AMBIGUOUS")
    admitted = admit_discovery_binding(binding)
    rules = spec.get("explanatory_rules") or []
    if not isinstance(rules, list):
        raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    rule_names = [str(item.get("name")) for item in rules if isinstance(item, Mapping)]
    if rule_names != list(bound_spec["explanatory"]):
        raise GroundedDiscoveryError("EXPLANATORY_INVALID")
    cells = _latest_cells(observations)
    decision_offset = max(_point_offset(point) for point in bound_spec["decision_points"])
    members: list[dict[str, Any]] = []
    cohort_ids = [str(item["cohort_id"]) for item in admitted["cohorts"]]
    for row in census:
        mint = str(row.get("mint") or "")
        if not mint:
            continue
        cohort = str(row.get("cohort_id") or "UNKNOWN")
        anchor = _parse_time(row.get("authoritative_anchor"))
        state = str(row.get("candidate_state") or "")
        block = str(row.get("calendar_block") or "")
        if not block and anchor is not None:
            block = anchor.date().isoformat()
        if not block:
            block = "UNANCHORED"
        exclusion = None
        in_base = False
        if state != "X_ELIGIBLE" or anchor is None:
            exclusion = "NOT_X_ELIGIBLE" if state != "X_ELIGIBLE" else "ANCHOR_MISSING"
        else:
            liquidity = cells.get((mint, "X300", LIQUIDITY))
            available = (
                _parse_time(liquidity.get("first_reliable_available_at"))
                if isinstance(liquidity, Mapping)
                else None
            )
            liquid_ok = (
                isinstance(liquidity, Mapping)
                and str(liquidity.get("state") or "") == "OBSERVED"
                and available is not None
                and available <= _deadline(anchor, 300)
            )
            if not liquid_ok:
                exclusion = "PIT_LIQUIDITY_MISSING"
            else:
                in_base = True
        decision_ready = False
        decision_at = None
        flags: dict[str, bool | None] = {}
        if in_base and anchor is not None:
            decision_at = _deadline(anchor, decision_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
            decision_ready = True
            for point in bound_spec["decision_points"]:
                for field in bound_spec["decision_fields"]:
                    cell = cells.get((mint, str(point), str(field)))
                    cell_at = (
                        _parse_time(cell.get("first_reliable_available_at"))
                        if isinstance(cell, Mapping)
                        else None
                    )
                    if (
                        not isinstance(cell, Mapping)
                        or str(cell.get("state") or "") != "OBSERVED"
                        or cell_at is None
                        or cell_at > _deadline(anchor, _point_offset(point))
                    ):
                        decision_ready = False
            flags = _explanatory_flags(cells, mint, [item for item in rules if isinstance(item, Mapping)], anchor=anchor)
        target_state = "ABSENT"
        target_at = None
        target_value = None
        if in_base and anchor is not None:
            target = cells.get((mint, str(bound_spec["target_point"]), str(bound_spec["target_field"])))
            if not isinstance(target, Mapping):
                target_state = "ABSENT"
            else:
                target_state = str(target.get("state") or "ABSENT")
                target_at_dt = _parse_time(target.get("first_reliable_available_at"))
                deadline = _deadline(anchor, decision_offset)
                if target_at_dt is not None and target_at_dt <= deadline:
                    target_state = "LEAKED"
                    target_at = target_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                elif target_state == "OBSERVED":
                    target_value = _as_float(target.get("typed_value"))
                    if target_value is None:
                        target_state = "MISSING_TYPED"
                    elif target_at_dt is not None:
                        target_at = target_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    else:
                        target_state = "ABSENT"
        members.append(
            {
                "member_id": mint,
                "cohort_id": cohort,
                "calendar_block": block,
                "in_base_x": in_base,
                "decision_ready": decision_ready,
                "decision_at": decision_at,
                "target_state": target_state if in_base else "ABSENT",
                "target_at": target_at,
                "target_value": target_value,
                "explanatory": flags,
                "exclusion_reason": exclusion,
            }
        )
    summary = summarize_discovery_query(
        members,
        spec,
        overlap_members=[],
        required_cohorts=cohort_ids,
        overlapping_cohorts=sorted(_window_overlaps(binding)),
    )
    summary["traders_complete_required"] = False
    summary["eligibility_uses_target"] = False
    summary["calculation_version"] = CALCULATION_VERSION
    return {
        "admitted": admitted,
        "summary": summary,
        "members_projected": len(members),
    }


def result_sha256(summary: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(summary).encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def data_binding_sha256(
    admitted: Mapping[str, Any],
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
) -> str:
    body = {
        "admitted": admitted,
        "calculation_version": CALCULATION_VERSION,
        "census": _jsonable(list(census)),
        "observations": _jsonable(list(observations)),
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _look_identity(spec_sha: str, binding_sha: str, journal_scope: str) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "spec_sha256": spec_sha,
                "data_binding_sha256": binding_sha,
                "calculation_version": CALCULATION_VERSION,
                "journal_scope": journal_scope,
            }
        ).encode("utf-8")
    ).hexdigest()


def list_discovery_looks(store: Any, journal_scope: str) -> list[dict[str, Any]]:
    """Read committed discovery looks. Does not reserve a scientific slot."""

    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        try:
            wrapper = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(wrapper, Mapping):
            continue
        if wrapper.get("artifact_kind") != "DISCOVERY_QUERY_LOOK":
            continue
        try:
            body = json.loads(str(wrapper.get("payload_canonical") or ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(body, dict) and body.get("journal_scope") == journal_scope:
            body["record_id"] = str(getattr(record, "record_id", "") or "")
            found.append(body)
    return found


def assert_computed_grounded_evidence(store: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze gate: evidence refs must match a durable computed artifact."""

    bound = bind_prior_scope_evidence(evidence)
    refs = bound.get("result_refs")
    if not isinstance(refs, list) or not refs:
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    summary = bound.get("result")
    if not isinstance(summary, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    expected = result_sha256(summary)
    if bound.get("result_sha256") != expected:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    if bound.get("calculation_version") != CALCULATION_VERSION:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    journal_scope = str(bound.get("journal_scope") or "")
    looks = {item.get("record_id"): item for item in list_discovery_looks(store, journal_scope)}
    last = looks.get(str(refs[-1]))
    if not isinstance(last, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    if last.get("result_sha256") != expected:
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    if last.get("data_binding_sha256") != bound.get("data_binding_sha256"):
        raise GroundedDiscoveryError("GROUNDED_RESULT_MISMATCH")
    for ref in refs:
        if str(ref) not in looks:
            raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    return bound


def no_worthy_scope_record(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """A no-candidate stop keeps the computed scope. It is not a raw-corpus negative."""

    return {
        "terminal": "NO_WORTHY_HYPOTHESIS",
        "technical_failure": False,
        "raw_corpus_negative": False,
        "not_run": False,
        "journal_scope": evidence.get("journal_scope"),
        "result_refs": list(evidence.get("result_refs") or []),
        "queries": list(evidence.get("queries") or []),
        "budget": evidence.get("budget"),
        "candidate_scope": evidence.get("candidate_scope"),
        "result_sha256": evidence.get("result_sha256"),
    }


def format_discovery_readout(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Owner readout for one computed query. Does not claim alpha."""

    result = evidence.get("result")
    if not isinstance(result, Mapping):
        raise GroundedDiscoveryError("GROUNDED_RESULT_UNBOUND")
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "engine_emits_alpha": False,
        "result_refs": list(evidence.get("result_refs") or []),
        "pooled_mean_target": (result.get("pooled") or {}).get("mean_target"),
        "by_cohort": result.get("by_cohort"),
        "by_calendar_block": result.get("by_calendar_block"),
        "by_explanatory": result.get("by_explanatory"),
        "exclusion_reasons": result.get("exclusion_reasons"),
        "calendar_overlap_is_not_independent_replication": result.get(
            "calendar_overlap_is_not_independent_replication"
        ),
        "non_claims": ["NO_ALPHA", "NO_CAUSAL_IDENTIFICATION", "NO_MARKET_FORGE"],
    }


def run_recorded_discovery_query(
    store: Any,
    *,
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    binding: Sequence[Mapping[str, Any]],
    journal_scope: str,
    candidate_scope: Mapping[str, Any],
    priors: Sequence[Mapping[str, Any]] | None = None,
    git_sha: str,
    clock: datetime | None = None,
) -> dict[str, Any]:
    """Public production entry: compute, persist or resume, return evidence refs."""

    if not isinstance(journal_scope, str) or not journal_scope.strip():
        raise GroundedDiscoveryError("JOURNAL_SCOPE_REQUIRED")
    if not isinstance(git_sha, str) or len(git_sha) != 40:
        raise GroundedDiscoveryError("GIT_SHA_REQUIRED")
    computed = execute_discovery_from_rows(census, observations, spec, binding)
    summary = computed["summary"]
    binding_sha = data_binding_sha256(computed["admitted"], census, observations)
    digest = result_sha256(summary)
    identity = _look_identity(summary["spec_sha256"], binding_sha, journal_scope)
    previous = list_discovery_looks(store, journal_scope)
    existing = next(
        (
            item
            for item in previous
            if item.get("spec_sha256") == summary["spec_sha256"]
            and item.get("data_binding_sha256") == binding_sha
            and item.get("calculation_version") == CALCULATION_VERSION
        ),
        None,
    )
    budget_history = []
    for item in previous:
        if (
            item.get("spec_sha256") == summary["spec_sha256"]
            and item.get("data_binding_sha256") != binding_sha
        ):
            budget_history.append({**item, "spec_sha256": "DATA_BINDING_CHANGED"})
        else:
            budget_history.append(item)
    look = classify_query_look(budget_history, spec)
    if existing is not None:
        record_id = str(existing.get("record_id") or "")
        budget = {
            "spec_sha256": summary["spec_sha256"],
            "new_look": False,
            "look_class": "RETRY_SAME_BYTES",
            "main_count": look["main_count"],
            "adaptive_count": look["adaptive_count"],
        }
    else:
        record_id = f"HFIC-ART-DISCOVERY-{identity[:40].upper()}"
        budget = look
        _append_discovery_look(
            store,
            record_id=record_id,
            journal_scope=journal_scope,
            spec_sha256=summary["spec_sha256"],
            binding_sha=binding_sha,
            digest=digest,
            identity=identity,
            summary=summary,
            look=look,
            git_sha=git_sha,
            clock=clock,
        )
    evidence = {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "journal_scope": journal_scope,
        "data_binding_sha256": binding_sha,
        "result_sha256": digest,
        "result": summary,
        "result_refs": [record_id],
        "queries": [
            {
                "query_id": summary["query_id"],
                "spec_sha256": summary["spec_sha256"],
                "record_id": record_id,
                "look_class": budget["look_class"],
                "new_look": budget["new_look"],
            }
        ],
        "budget": {
            "main_count": budget["main_count"],
            "adaptive_count": budget["adaptive_count"],
            "main_limit": MAX_MAIN_QUERY_SPECS,
            "adaptive_limit": MAX_ADAPTIVE_REFINEMENTS,
        },
        "candidate_scope": dict(candidate_scope),
        "priors": [dict(item) for item in (priors or [])],
        "scientific_slot_reserved": False,
    }
    return assert_computed_grounded_evidence(store, evidence)


def _append_discovery_look(
    store: Any,
    *,
    record_id: str,
    journal_scope: str,
    spec_sha256: str,
    binding_sha: str,
    digest: str,
    identity: str,
    summary: Mapping[str, Any],
    look: Mapping[str, Any],
    git_sha: str,
    clock: datetime | None,
) -> None:
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise GroundedDiscoveryError("CLOCK_NAIVE")
    body = {
        "schema": "smial.discovery-query-look",
        "schema_version": "1.0",
        "journal_scope": journal_scope,
        "calculation_version": CALCULATION_VERSION,
        "query_id": summary.get("query_id"),
        "spec_sha256": spec_sha256,
        "data_binding_sha256": binding_sha,
        "result_sha256": digest,
        "result": summary,
        "look_class": look.get("look_class"),
        "new_look": True,
        "scientific_slot_reserved": False,
    }
    canonical = _canonical(body)
    payload = {
        "research_artifact_id": record_id,
        "session_id": f"HFIC-DISCOVERY-{journal_scope}",
        "hfic_protocol": "HFIC-V1.2",
        "artifact_kind": "DISCOVERY_QUERY_LOOK",
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
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
        transaction_id=f"RESEARCH-TXN-DISCOVERY-{identity[:24].upper()}",
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


def load_parquet_rows(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(Path(path))
    return table.to_pylist()


def live_state_only_coverage(data_root: Path) -> dict[str, Any]:
    """No-write joint coverage. Never selects typed_value."""

    import duckdb

    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        load_live_corpus_lineage,
    )

    lineage = load_live_corpus_lineage(Path(data_root))
    cohorts = [
        item
        for item in (lineage.get("cohorts") or [])
        if isinstance(item, Mapping)
    ]
    cohorts.sort(key=lambda item: int(item.get("corpus_version") or 0))
    binding = admit_discovery_binding(
        [
            {
                "dataset_id": LIVE_DATASET_ID,
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "cohort_id": item.get("cohort_id"),
                "release_id": item.get("release_id"),
                "census_sha256": item.get("census_sha256"),
                "observations_sha256": item.get("observations_sha256"),
                "holdout": False,
            }
            for item in cohorts
        ]
    )
    reports = []
    connection = duckdb.connect(database=":memory:")
    try:
        for item in cohorts:
            census = Path(data_root) / str(item["census_rel"])
            obs = Path(data_root) / str(item["obs_rel"])
            columns = {
                str(row[0])
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM read_parquet(?)",
                    [str(obs)],
                ).fetchall()
            }
            if "typed_value" in columns:
                columns.discard("typed_value")
            headline = connection.execute(
                f"""
                WITH census AS (
                  SELECT mint, candidate_state, authoritative_anchor
                  FROM read_parquet(?)
                ), x_elig AS (
                  SELECT mint, authoritative_anchor
                  FROM census WHERE candidate_state = 'X_ELIGIBLE'
                ), latest AS (
                  SELECT mint, point_id, field_id, state,
                         first_reliable_available_at AS available_at,
                         row_number() OVER (
                           PARTITION BY mint, point_id, field_id
                           ORDER BY first_reliable_available_at DESC NULLS LAST
                         ) AS rn
                  FROM read_parquet(?)
                  WHERE field_id IN ('{PRICE}', '{LIQUIDITY}')
                    AND point_id IN ('X300', 'Y900', 'Y1800', 'Y3600')
                ), cell AS (
                  SELECT * FROM latest WHERE rn = 1
                ), base AS (
                  SELECT x.mint
                  FROM x_elig x
                  JOIN cell liq
                    ON liq.mint = x.mint AND liq.point_id = 'X300'
                   AND liq.field_id = '{LIQUIDITY}' AND liq.state = 'OBSERVED'
                  WHERE try_cast(liq.available_at AS TIMESTAMPTZ)
                        <= try_cast(x.authoritative_anchor AS TIMESTAMPTZ)
                           + INTERVAL 600 SECOND
                ), joint AS (
                  SELECT b.mint
                  FROM base b
                  JOIN cell price
                    ON price.mint = b.mint AND price.point_id = 'X300'
                   AND price.field_id = '{PRICE}' AND price.state = 'OBSERVED'
                   AND price.available_at IS NOT NULL
                )
                SELECT
                  (SELECT count(*) FROM census),
                  (SELECT count(*) FROM x_elig),
                  (SELECT count(*) FROM base),
                  (SELECT count(*) FROM joint)
                """,
                [str(census), str(obs)],
            ).fetchone()
            prefix = connection.execute(
                f"""
                WITH census AS (
                  SELECT mint, candidate_state, authoritative_anchor
                  FROM read_parquet(?)
                ), x_elig AS (
                  SELECT mint, authoritative_anchor
                  FROM census WHERE candidate_state = 'X_ELIGIBLE'
                ), latest AS (
                  SELECT mint, point_id, field_id, state,
                         first_reliable_available_at AS available_at,
                         row_number() OVER (
                           PARTITION BY mint, point_id, field_id
                           ORDER BY first_reliable_available_at DESC NULLS LAST
                         ) AS rn
                  FROM read_parquet(?)
                  WHERE field_id IN ('{PRICE}', '{LIQUIDITY}')
                    AND point_id IN ('X300', 'Y900', 'Y1800')
                ), cell AS (
                  SELECT * FROM latest WHERE rn = 1
                ), base AS (
                  SELECT x.mint
                  FROM x_elig x
                  JOIN cell liq
                    ON liq.mint = x.mint AND liq.point_id = 'X300'
                   AND liq.field_id = '{LIQUIDITY}' AND liq.state = 'OBSERVED'
                  WHERE try_cast(liq.available_at AS TIMESTAMPTZ)
                        <= try_cast(x.authoritative_anchor AS TIMESTAMPTZ)
                           + INTERVAL 600 SECOND
                )
                SELECT count(*) FROM (
                  SELECT cell.mint
                  FROM cell
                  JOIN base ON base.mint = cell.mint
                  WHERE cell.state = 'OBSERVED' AND cell.available_at IS NOT NULL
                  GROUP BY cell.mint
                  HAVING count(*) = 6
                )
                """,
                [str(census), str(obs)],
            ).fetchone()
            reports.append(
                {
                    "cohort_id": item.get("cohort_id"),
                    "release_id": item.get("release_id"),
                    "evidence_role": LIVE_EVIDENCE_ROLE,
                    "census_rows": int(headline[0]),
                    "x_eligible": int(headline[1]),
                    "base_x_like": int(headline[2]),
                    "joint_x300_price_and_liquidity": int(headline[3]),
                    "joint_prefix_price_liquidity_through_y1800": int(prefix[0]),
                    "typed_value_selected": False,
                }
            )
    finally:
        connection.close()
    windows = []
    for item in cohorts:
        parsed = _cohort_window(str(item.get("cohort_id") or ""))
        if parsed is not None:
            windows.append((str(item.get("cohort_id")), parsed[0], parsed[1]))
    overlaps = []
    for index, (left_id, left_start, left_end) in enumerate(windows):
        for right_id, right_start, right_end in windows[index + 1 :]:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if start < end:
                overlaps.append(
                    {
                        "left_cohort_id": left_id,
                        "right_cohort_id": right_id,
                        "overlap_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "overlap_end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "independent_replication": False,
                    }
                )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "scientific_writes": 0,
        "typed_value_selected": False,
        "binding": binding,
        "cohorts": reports,
        "collection_window_overlaps": overlaps,
        "first_supported_scope": [
            "X300_PRICE_LIQUIDITY_BASELINE",
            "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
        ],
        "excluded_from_first_scope": ["TRADERS_COMPLETE_PREFIX"],
        "denominator_note": "joint counts are inside base_x-like PIT liquidity, not census rows and not per-cell margins",
    }
