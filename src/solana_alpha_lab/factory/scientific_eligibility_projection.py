"""Pure ScientificEligibilityProjection over a verified release.

Base scientific population is X300-valid X_ELIGIBLE. Y completeness never
shrinks that denominator. Outcome missingness is coverage, not a second
population. Never materializes Y typed values.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import STATE_OBSERVED

SPEC_RELATIVE = "configs/scientific_eligibility_projection_v1.yaml"
PROJECTION_SCHEMA = "smial.scientific-eligibility-projection"
PROJECTION_SCHEMA_VERSION = "1.0"
RULE_ID = "BASE_X_X300_VALID_X_ELIGIBLE_V1"
X_POINT_ID = "X300"
X_FIELD_ID = "FIELD-LIQUIDITY-USD-001"
X_DUE_OFFSET_SECONDS = 300
X_ALLOWED_LATENESS_SECONDS = 300
MIN_USABLE_BASE_X_POPULATION = 10
READINESS_COMPLETE = "COMPLETE"
READINESS_MISSINGNESS_UNRESOLVED = "MISSINGNESS_UNRESOLVED"
READINESS_UNSPECIFIED = "UNSPECIFIED"
ELIGIBILITY_SCOPE_FULL_LIFECYCLE = "FULL_LIFECYCLE_COMPLETENESS"
ELIGIBILITY_SCOPE_BASE_X = "BASE_X_POPULATION"
Y_POINT_PREFIX = "Y"
RESOLVED_OBSERVATION_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "CENSORED_LATE",
        "CENSORED",
        "DISAPPEARED",
        "EXCLUDED_AMBIGUOUS",
    }
)
C1_EXPECTED = {
    "base_x_n": 475,
    "lifecycle_observed_n": 148,
    "lifecycle_censored_late_n": 327,
}


class ScientificEligibilityError(ValueError):
    """Fail-closed projection error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_projection_spec(root: Path, relative: str = SPEC_RELATIVE) -> dict[str, Any]:
    path = Path(root) / relative
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScientificEligibilityError("PROJECTION_SPEC_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ScientificEligibilityError("PROJECTION_SPEC_INVALID")
    return loaded


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _mint(row: Mapping[str, Any]) -> str:
    return str(row.get("mint") or row.get("entity_id") or "")


def _x300_pit_ok(
    *,
    available_at: object,
    anchor: object,
    due_offset_seconds: int,
    allowed_lateness_seconds: int,
) -> bool:
    observed_at = _parse_utc(available_at)
    member_anchor = _parse_utc(anchor)
    if observed_at is None or member_anchor is None:
        return False
    deadline = member_anchor + timedelta(
        seconds=int(due_offset_seconds) + int(allowed_lateness_seconds)
    )
    return observed_at <= deadline


def required_outcomes_from_spec(spec: Mapping[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(spec, Mapping):
        return []
    raw = spec.get("required_outcomes")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        point_id = str(item.get("point_id") or "")
        role = str(item.get("role") or "PRIMARY")
        field_ids = item.get("field_ids")
        if not point_id or not isinstance(field_ids, list):
            continue
        for field_id in field_ids:
            text = str(field_id or "")
            key = (point_id, text)
            if not text or key in seen:
                continue
            seen.add(key)
            out.append({"point_id": point_id, "field_id": text, "role": role})
    return out


def full_lifecycle_scope_equivalent(
    required_point_ids: Sequence[str] | None,
    schedule_y_point_ids: Sequence[str] | None,
) -> bool:
    """True only when required Y points exactly equal the bound schedule Y set."""

    if not required_point_ids or not schedule_y_point_ids:
        return False
    required = {str(item) for item in required_point_ids if str(item).startswith(Y_POINT_PREFIX)}
    scheduled = {str(item) for item in schedule_y_point_ids if str(item).startswith(Y_POINT_PREFIX)}
    return bool(required) and required == scheduled


def schedule_y_point_ids(schedule: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(schedule, Mapping):
        return ()
    points = schedule.get("y_points")
    if not isinstance(points, list):
        return ()
    out: list[str] = []
    for item in points:
        if not isinstance(item, Mapping):
            continue
        point_id = str(item.get("point_id") or "")
        if point_id.startswith(Y_POINT_PREFIX):
            out.append(point_id)
    return tuple(out)


def project_scientific_eligibility(
    census_rows: Sequence[Mapping[str, Any]],
    observation_rows: Sequence[Mapping[str, Any]],
    *,
    spec: Mapping[str, Any] | None = None,
    schedule: Mapping[str, Any] | None = None,
    release_binding: Mapping[str, Any] | None = None,
    x_due_offset_seconds: int = X_DUE_OFFSET_SECONDS,
    x_allowed_lateness_seconds: int = X_ALLOWED_LATENESS_SECONDS,
) -> dict[str, Any]:
    """Project base_x, lifecycle coverage, and typed outcome readiness.

    Observation rows may carry only mint/point_id/field_id/state/clocks.
    Y ``typed_value`` is never read.
    """

    if isinstance(schedule, Mapping):
        x_point = schedule.get("x_point")
        if isinstance(x_point, Mapping):
            if x_point.get("due_offset_seconds") is not None:
                x_due_offset_seconds = int(x_point["due_offset_seconds"])
            if x_point.get("allowed_lateness_seconds") is not None:
                x_allowed_lateness_seconds = int(x_point["allowed_lateness_seconds"])

    x300_by_mint: dict[str, Mapping[str, Any]] = {}
    obs_index: dict[tuple[str, str, str], str] = {}
    for row in observation_rows:
        if not isinstance(row, Mapping):
            continue
        mint = _mint(row)
        point_id = str(row.get("point_id") or "")
        field_id = str(row.get("field_id") or "")
        if not mint or not point_id or not field_id:
            continue
        state = str(row.get("state") or "")
        obs_index[(mint, point_id, field_id)] = state
        if (
            point_id == X_POINT_ID
            and field_id == X_FIELD_ID
            and mint not in x300_by_mint
        ):
            x300_by_mint[mint] = row

    base_mints: list[str] = []
    lifecycle = {
        "n_observed": 0,
        "n_censored_late": 0,
        "n_typed_missing": 0,
        "n_other": 0,
    }
    for row in census_rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("candidate_state") or "") != "X_ELIGIBLE":
            continue
        mint = _mint(row)
        if not mint:
            continue
        x300 = x300_by_mint.get(mint)
        if x300 is None:
            continue
        if str(x300.get("state") or "") != STATE_OBSERVED:
            continue
        if not _x300_pit_ok(
            available_at=x300.get("first_reliable_available_at"),
            anchor=row.get("authoritative_anchor"),
            due_offset_seconds=x_due_offset_seconds,
            allowed_lateness_seconds=x_allowed_lateness_seconds,
        ):
            continue
        base_mints.append(mint)
        denom = str(row.get("denominator_state") or "")
        if denom == "observed":
            lifecycle["n_observed"] += 1
        elif denom == "censored_late":
            lifecycle["n_censored_late"] += 1
        elif denom == "typed_missing":
            lifecycle["n_typed_missing"] += 1
        else:
            lifecycle["n_other"] += 1

    base_mints = sorted(set(base_mints))
    required = required_outcomes_from_spec(spec)
    coverage: list[dict[str, Any]] = []
    unresolved = 0
    if spec is None or (
        isinstance(spec, Mapping) and spec.get("schema_version") not in {"1.3"}
        and not required
    ):
        readiness = READINESS_UNSPECIFIED
    elif not required:
        readiness = READINESS_UNSPECIFIED
    else:
        for item in required:
            n_observed = 0
            n_censored_late = 0
            n_typed_missing = 0
            n_absent = 0
            n_other = 0
            for mint in base_mints:
                state = obs_index.get((mint, item["point_id"], item["field_id"]))
                if state is None:
                    n_absent += 1
                    unresolved += 1
                    continue
                if state not in RESOLVED_OBSERVATION_STATES:
                    n_other += 1
                    unresolved += 1
                    continue
                if state == STATE_OBSERVED:
                    n_observed += 1
                elif state in {"CENSORED_LATE", "CENSORED"}:
                    n_censored_late += 1
                elif state == "MISSING_TYPED":
                    n_typed_missing += 1
                else:
                    n_other += 1
            coverage.append(
                {
                    "point_id": item["point_id"],
                    "field_id": item["field_id"],
                    "role": item["role"],
                    "n_observed": n_observed,
                    "n_censored_late": n_censored_late,
                    "n_typed_missing": n_typed_missing,
                    "n_absent": n_absent,
                    "n_other": n_other,
                    "denominator_n": len(base_mints),
                }
            )
        readiness = (
            READINESS_MISSINGNESS_UNRESOLVED if unresolved else READINESS_COMPLETE
        )

    member_ids_sha256 = hashlib.sha256(
        ("\n".join(base_mints)).encode("utf-8")
    ).hexdigest()
    payload = {
        "schema": PROJECTION_SCHEMA,
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "rule_id": RULE_ID,
        "release_binding": dict(release_binding or {}),
        "experiment_spec_sha256": (
            None
            if spec is None
            else canonical_sha256(dict(spec))
        ),
        "base_x_population": {
            "rule_id": RULE_ID,
            "n": len(base_mints),
            "member_ids_sha256": member_ids_sha256,
            "x_point_id": X_POINT_ID,
            "x_field_id": X_FIELD_ID,
            "x_due_offset_seconds": int(x_due_offset_seconds),
            "x_allowed_lateness_seconds": int(x_allowed_lateness_seconds),
        },
        "lifecycle_coverage": {
            "owner": "membership_state/denominator_state",
            **lifecycle,
            "denominator_n": len(base_mints),
        },
        "outcome_coverage": coverage,
        "outcome_readiness": readiness,
        "invariants": {
            "missing_y_never_shrinks_base_x": True,
            "no_complete_case_population": True,
            "no_y_typed_value_read": True,
        },
    }
    payload["projection_sha256"] = canonical_sha256(payload)
    return payload


def y_columns_forbidden(row: Mapping[str, Any]) -> None:
    """Guard test/helpers: Y typed values must not enter the working set."""

    point_id = str(row.get("point_id") or "")
    if point_id.startswith(Y_POINT_PREFIX) and "typed_value" in row:
        raise ScientificEligibilityError("Y_TYPED_VALUE_READ")


def assert_c1_shape(projection: Mapping[str, Any]) -> None:
    base_n = int(projection["base_x_population"]["n"])
    life = projection["lifecycle_coverage"]
    if (
        base_n != C1_EXPECTED["base_x_n"]
        or int(life["n_observed"]) != C1_EXPECTED["lifecycle_observed_n"]
        or int(life["n_censored_late"]) != C1_EXPECTED["lifecycle_censored_late_n"]
    ):
        raise ScientificEligibilityError("C1_SHAPE_MISMATCH")
    if base_n != int(life["denominator_n"]):
        raise ScientificEligibilityError("BASE_X_LIFECYCLE_DENOMINATOR_DRIFT")


__all__ = [
    "C1_EXPECTED",
    "ELIGIBILITY_SCOPE_BASE_X",
    "ELIGIBILITY_SCOPE_FULL_LIFECYCLE",
    "MIN_USABLE_BASE_X_POPULATION",
    "READINESS_COMPLETE",
    "READINESS_MISSINGNESS_UNRESOLVED",
    "READINESS_UNSPECIFIED",
    "RULE_ID",
    "SPEC_RELATIVE",
    "ScientificEligibilityError",
    "X_ALLOWED_LATENESS_SECONDS",
    "X_DUE_OFFSET_SECONDS",
    "X_FIELD_ID",
    "X_POINT_ID",
    "assert_c1_shape",
    "full_lifecycle_scope_equivalent",
    "load_projection_spec",
    "project_scientific_eligibility",
    "required_outcomes_from_spec",
    "schedule_y_point_ids",
    "y_columns_forbidden",
]
