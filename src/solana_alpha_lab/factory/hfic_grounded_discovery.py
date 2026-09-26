"""Ordinary grounded discovery: state-only coverage, bounded queries, scope.

Does not read market typed values, does not run Prompt A, and does not reserve
a scientific slot. ``synthetic_target`` is fixture-only and is never loaded
from live parquet.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
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
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def summarize_discovery_query(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    *,
    overlap_members: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Pooled, cohort, and calendar summaries. Never emits an alpha claim."""

    bound = validate_query_spec(spec)
    overlap = set(overlap_members or [])
    groups: dict[str, list[Mapping[str, Any]]] = {
        "pooled": [],
        "decision_admissible": [],
        "target_observed_after": [],
    }
    missing = {"absent": 0, "censored_late": 0, "missing_typed": 0, "other": 0, "leaked": 0}
    by_cohort: dict[str, list[float]] = defaultdict(list)
    by_block: dict[str, list[float]] = defaultdict(list)
    by_flag: dict[str, list[float]] = defaultdict(list)
    cohort_denoms: dict[str, int] = defaultdict(int)
    block_denoms: dict[str, int] = defaultdict(int)
    flag_denoms: dict[str, int] = defaultdict(int)
    base_n = 0
    for member in members:
        if member.get("in_base_x") is not True:
            continue
        base_n += 1
        cohort = str(member.get("cohort_id") or "UNKNOWN")
        block = str(member.get("calendar_block") or "UNBLOCKED")
        cohort_denoms[cohort] += 1
        block_denoms[block] += 1
        flags = member.get("explanatory") or {}
        if not isinstance(flags, Mapping):
            raise GroundedDiscoveryError("EXPLANATORY_INVALID")
        flag_key = ",".join(
            f"{name}={bool(flags.get(name))}" for name in bound["explanatory"]
        ) or "NONE"
        flag_denoms[flag_key] += 1
        if member.get("decision_ready") is not True:
            continue
        decision_at = _parse_time(member.get("decision_at"))
        target_at = _parse_time(member.get("target_at"))
        state = str(member.get("target_state") or "ABSENT")
        if decision_at is None:
            missing["other"] += 1
            continue
        if target_at is not None and target_at <= decision_at:
            missing["leaked"] += 1
            continue
        if state == "ABSENT":
            missing["absent"] += 1
            continue
        if state == "CENSORED_LATE":
            missing["censored_late"] += 1
            continue
        if state == "MISSING_TYPED":
            missing["missing_typed"] += 1
            continue
        if state != "OBSERVED" or target_at is None:
            missing["other"] += 1
            continue
        raw = member.get("synthetic_target")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise GroundedDiscoveryError("SYNTHETIC_TARGET_INVALID") from exc
        groups["target_observed_after"].append(member)
        by_cohort[cohort].append(value)
        by_block[block].append(value)
        by_flag[flag_key].append(value)
    observed = groups["target_observed_after"]
    pooled_values = [
        float(item["synthetic_target"])
        for item in observed
        if item.get("synthetic_target") is not None
    ]

    def _view(name: str, values: Sequence[float], denominator: int) -> dict[str, Any]:
        return {
            "view": name,
            "denominator_base_x": denominator,
            "target_observed_after_decision": len(values),
            "mean_synthetic_target": _mean(list(values)),
            "independent_replication": name not in overlap and not name.endswith(":OVERLAP"),
        }

    overlap_n = sum(
        1
        for item in members
        if item.get("in_base_x") is True and str(item.get("member_id") or "") in overlap
    )
    return {
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "query_id": bound["query_id"],
        "spec_sha256": bound["spec_sha256"],
        "population": "BASE_X",
        "base_x_n": base_n,
        "not_per_cell_denominator": True,
        "engine_emits_alpha": False,
        "missing_is_not_zero": True,
        "missing": missing,
        "pooled": _view("pooled", pooled_values, base_n),
        "by_cohort": [
            _view(key, values, cohort_denoms[key]) for key, values in sorted(by_cohort.items())
        ],
        "by_calendar_block": [
            _view(key, values, block_denoms[key]) for key, values in sorted(by_block.items())
        ],
        "by_explanatory": [
            _view(key, values, flag_denoms[key]) for key, values in sorted(by_flag.items())
        ],
        "overlap_exposed_base_x": overlap_n,
        "overlap_is_not_independent_replication": overlap_n > 0,
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


def prior_scope_relation(
    candidate: Mapping[str, Any],
    prior: Mapping[str, Any],
) -> str:
    """Exact duplicate blocks. A CONTROL kill does not close a different raw question."""

    axes = ("population", "decision_timestamp", "target", "estimand", "question_id")
    same = all(candidate.get(key) == prior.get(key) for key in axes)
    prior_surface = str(prior.get("evidence_surface_mode") or "")
    if same:
        return "EXACT_SCOPE_MATCH"
    if prior_surface == "CURRENT_REPRESENTATION_CONTROL_V1":
        return "SCOPED_CONTROL_DOES_NOT_BLOCK"
    return "SCOPE_DISTINCT"


def _cohort_window(cohort_id: str) -> tuple[datetime, datetime] | None:
    match = _REL_RE.match(cohort_id)
    if match is None:
        return None
    start = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ")
    end = datetime.strptime(match.group(2), "%Y%m%dT%H%M%SZ")
    return start, end


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
                WITH latest AS (
                  SELECT mint, point_id, field_id, state,
                         first_reliable_available_at AS available_at,
                         row_number() OVER (
                           PARTITION BY mint, point_id, field_id
                           ORDER BY first_reliable_available_at DESC NULLS LAST
                         ) AS rn
                  FROM read_parquet(?)
                  WHERE field_id IN ('{PRICE}', '{LIQUIDITY}')
                    AND point_id IN ('X300', 'Y900', 'Y1800')
                )
                SELECT count(*) FROM (
                  SELECT mint
                  FROM latest
                  WHERE rn = 1 AND state = 'OBSERVED' AND available_at IS NOT NULL
                  GROUP BY mint
                  HAVING count(*) = 6
                )
                """,
                [str(obs)],
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
