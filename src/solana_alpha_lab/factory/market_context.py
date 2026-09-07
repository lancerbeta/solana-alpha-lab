"""Pure MarketContextProjector. Derived read model. Persists nowhere."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from solana_alpha_lab.factory.market_evidence import (
    coverage_class_for,
    empty_evidence_bundle,
    read_market_evidence,
)
from solana_alpha_lab.factory.market_feature_surface import load_surface_config
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    PROJECTION_ID,
    PROJECTION_VERSION,
)

SCHEMA = "smial.market-context-projection"
SCHEMA_VERSION = "1.0"
DEFINITION_RELATIVE = "configs/market_context_definition_v1.yaml"
DEFINITION_SCHEMA_RELATIVE = "catalog/schemas/market_context_definition_v1.schema.json"

REGIME_TOKENS = frozenset(
    {
        "BULL",
        "BEAR",
        "RISK_ON",
        "RISK_OFF",
        "GOOD_REGIME",
        "BAD_REGIME",
    }
)
PURITY = {
    "provider_calls": 0,
    "research_rdp_writes": 0,
    "observation_schedule_writes": 0,
    "paper_plane_writes": 0,
    "operational_store_writes": 0,
    "git_writes": 0,
    "store_create": 0,
    "migration": 0,
    "manifest_publication": 0,
    "lineage_mutation": 0,
}


class MarketContextError(ValueError):
    """Typed Market Context fault."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if not number.is_finite():
        return None
    return number


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketContextError("AS_OF_NOT_UTC")
    return value.astimezone(UTC)


def load_market_context_definition(root: Path) -> dict[str, Any]:
    path = root / DEFINITION_RELATIVE
    schema_path = root / DEFINITION_SCHEMA_RELATIVE
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MarketContextError("DEFINITION_MISSING") from exc
    if not isinstance(loaded, dict) or not isinstance(schema, dict):
        raise MarketContextError("DEFINITION_INVALID")
    try:
        jsonschema.validate(loaded, schema)
    except jsonschema.ValidationError as exc:
        raise MarketContextError("DEFINITION_SCHEMA_INVALID") from exc
    return loaded


def context_compatibility_sha256(
    definition: Mapping[str, Any],
    schedule_semantics: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(schedule_semantics, Mapping) or not schedule_semantics:
        return None
    payload = {
        "definition_id": definition["definition_id"],
        "definition_version": definition["definition_version"],
        "tokens_projection_id": str(
            (definition.get("tokens_projection") or {}).get("projection_id") or PROJECTION_ID
        ),
        "tokens_projection_version": str(
            (definition.get("tokens_projection") or {}).get("projection_version")
            or PROJECTION_VERSION
        ),
        "semantics": json.loads(_canonical_bytes(dict(schedule_semantics)).decode("utf-8")),
    }
    return _canonical_sha256(payload)


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def _quantile(values: Sequence[Decimal], q: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        return ordered[0]
    position = q * Decimal(n - 1)
    lower = int(position.to_integral_value(rounding=ROUND_HALF_EVEN))
    lower = min(max(lower, 0), n - 1)
    upper = min(lower + 1, n - 1)
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _direction(previous: Decimal, current: Decimal) -> str:
    if current > previous:
        return "UP"
    if current < previous:
        return "DOWN"
    return "FLAT"


def _in_window(available: datetime | None, start: datetime, end: datetime) -> bool:
    if available is None:
        return False
    return start < available <= end


def _parse_available(row: Mapping[str, Any]) -> datetime | None:
    raw = row.get("first_reliable_available_at")
    if not raw:
        return None
    try:
        return parse_utc(str(raw))
    except Exception:
        return None


def _field_map(row: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = row.get("field_values")
    mapped: dict[str, dict[str, Any]] = {}
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, Mapping):
                continue
            field_id = str(item.get("field_id") or "")
            if field_id:
                mapped[field_id] = dict(item)
    field_id = str(row.get("field_id") or "")
    if field_id and field_id not in mapped:
        mapped[field_id] = {
            "field_id": field_id,
            "typed_value_or_null": row.get("typed_value_or_null"),
            "state": row.get("state"),
        }
    return mapped


def _relative_state(
    current: Decimal | None,
    reference_values: Sequence[Decimal],
    *,
    n_in_scope: int,
    n_observed: int,
    definition: Mapping[str, Any],
    comparable: bool,
    incomparable_reason: str = "REFERENCE_SCOPE_MISMATCH",
) -> tuple[str, str | None, int]:
    if not comparable:
        return "UNKNOWN", incomparable_reason, 0
    min_n = int(definition["minimum_current_n"])
    min_cov = Decimal(str(definition["minimum_current_coverage"]))
    min_buckets = int(definition["minimum_historical_buckets"])
    observed_fraction = (
        (Decimal(n_observed) / Decimal(n_in_scope)) if n_in_scope else Decimal(0)
    )
    if current is None or n_observed < min_n or observed_fraction < min_cov:
        return "UNKNOWN", "COVERAGE_INSUFFICIENT", len(reference_values)
    if len(reference_values) < min_buckets:
        return "UNKNOWN", "REFERENCE_INSUFFICIENT", len(reference_values)
    low_q = Decimal(str(definition["reference_low_quantile"]))
    high_q = Decimal(str(definition["reference_high_quantile"]))
    low = _quantile(reference_values, low_q)
    high = _quantile(reference_values, high_q)
    if low is None or high is None:
        return "UNKNOWN", "REFERENCE_INSUFFICIENT", len(reference_values)
    if current < low:
        return "LOW_RELATIVE", None, len(reference_values)
    if current > high:
        return "HIGH_RELATIVE", None, len(reference_values)
    return "MID_RELATIVE", None, len(reference_values)


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _observed_number(field: Mapping[str, Any] | None) -> Decimal | None:
    if not isinstance(field, Mapping):
        return None
    if str(field.get("state") or "") != "OBSERVED":
        return None
    return _dec(field.get("typed_value_or_null"))


def _entity_metric(
    axis: Mapping[str, Any],
    current_row: Mapping[str, Any] | None,
    previous_row: Mapping[str, Any] | None,
) -> tuple[Decimal | None, str]:
    aggregation = str(axis["aggregation"])
    current_fields = _field_map(current_row) if current_row else {}
    if aggregation == "MEDIAN_OBSERVED":
        field_id = str(axis["field_ids"][0])
        number = _observed_number(current_fields.get(field_id))
        return number, "OBSERVED" if number is not None else "MISSING"
    if aggregation == "UP_SHARE_VS_PREVIOUS":
        field_id = str(axis["field_ids"][0])
        current = _observed_number(current_fields.get(field_id))
        previous_fields = _field_map(previous_row) if previous_row else {}
        previous = _observed_number(previous_fields.get(field_id))
        if current is None or previous is None:
            return None, "MISSING"
        direction = _direction(previous, current)
        return Decimal(1) if direction == "UP" else Decimal(0), direction
    if aggregation == "MEDIAN_BUY_SELL_BALANCE":
        buys = _observed_number(current_fields.get(str(axis["field_ids"][0])))
        sells = _observed_number(current_fields.get(str(axis["field_ids"][1])))
        if buys is None or sells is None:
            return None, "UNKNOWN"
        denom = buys + sells
        if denom <= 0:
            return None, "NO_ACTIVITY"
        return (buys - sells) / denom, "OBSERVED"
    raise MarketContextError("UNKNOWN_AGGREGATION")


def _coverage_counts(
    rows: Sequence[Mapping[str, Any]],
    member_ids: set[str],
    axis: Mapping[str, Any],
) -> dict[str, int]:
    classes: dict[str, int] = {
        "observed": 0,
        "typed_missing": 0,
        "disappeared": 0,
        "censored": 0,
        "capacity_excluded": 0,
        "sampling_excluded": 0,
        "x_ineligible": 0,
        "unknown": 0,
    }
    seen: set[str] = set()
    field_id = str(axis["field_ids"][0])
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        fields = _field_map(row)
        field = fields.get(field_id)
        state = (field or {}).get("state") or row.get("state")
        classes[coverage_class_for(state)] += 1
    for entity_id in member_ids:
        if entity_id in seen:
            continue
        seen.add(entity_id)
        classes["unknown"] += 1
    n_in_scope = sum(classes.values())
    return {
        **classes,
        "n_in_scope": n_in_scope,
        "n_observed": classes["observed"],
        "n_missing": n_in_scope - classes["observed"],
    }


def _bucket_start(available: datetime, origin: datetime, bucket_seconds: int) -> datetime:
    elapsed = int((available - origin).total_seconds())
    index = elapsed // bucket_seconds
    return origin + timedelta(seconds=index * bucket_seconds)


def _select_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    start: datetime,
    end: datetime,
    point_id: str | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        available = _parse_available(row)
        if not _in_window(available, start, end):
            continue
        if point_id is not None and str(row.get("point_id") or "") != point_id:
            continue
        selected.append(dict(row))
    return selected


def _latest_by_entity(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if not entity_id:
            continue
        current = latest.get(entity_id)
        if current is None:
            latest[entity_id] = dict(row)
            continue
        left = _parse_available(row)
        right = _parse_available(current)
        if left is not None and (right is None or left >= right):
            latest[entity_id] = dict(row)
    return latest


def _axis_value(
    axis: Mapping[str, Any],
    current_rows: Sequence[Mapping[str, Any]],
    previous_rows: Sequence[Mapping[str, Any]],
) -> tuple[Decimal | None, list[str]]:
    current_by = _latest_by_entity(current_rows)
    previous_by = _latest_by_entity(previous_rows)
    values: list[Decimal] = []
    details: list[str] = []
    for entity_id, row in sorted(current_by.items()):
        number, detail = _entity_metric(axis, row, previous_by.get(entity_id))
        details.append(detail)
        if number is not None:
            values.append(number)
    if str(axis["aggregation"]) == "UP_SHARE_VS_PREVIOUS":
        valid = [item for item in details if item in {"UP", "FLAT", "DOWN"}]
        if not valid:
            return None, details
        up = sum(1 for item in valid if item == "UP")
        return Decimal(up) / Decimal(len(valid)), details
    return _median(values), details


def _previous_lookback_seconds(landmark: Mapping[str, Any], landmarks: Sequence[Mapping[str, Any]]) -> int:
    previous_id = str(landmark["previous_point_id"])
    current_offset = int(landmark["due_offset_seconds"])
    for item in landmarks:
        if str(item["point_id"]) == previous_id:
            return max(current_offset - int(item["due_offset_seconds"]), 1)
    return current_offset


def _reference_bucket_values(
    axis: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    point_id: str,
    previous_point_id: str,
    previous_lookback_seconds: int,
    ref_start: datetime,
    ref_end: datetime,
    bucket_seconds: int,
) -> list[Decimal]:
    values: list[Decimal] = []
    cursor = ref_start
    while cursor < ref_end:
        bucket_end = min(cursor + timedelta(seconds=bucket_seconds), ref_end)
        current_rows = _select_rows(
            observations, start=cursor, end=bucket_end, point_id=point_id
        )
        previous_rows = _select_rows(
            observations,
            start=cursor - timedelta(seconds=previous_lookback_seconds),
            end=bucket_end,
            point_id=previous_point_id,
        )
        metric, _details = _axis_value(axis, current_rows, previous_rows)
        if metric is not None:
            values.append(metric)
        cursor = bucket_end
    return values


def _schedule_sha_set(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("schedule_sha256") or "")
            for row in rows
            if str(row.get("schedule_sha256") or "")
        }
    )


def _activation_set(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("activation_id") or "")
            for row in rows
            if str(row.get("activation_id") or "")
        }
    )


def _latest_clock(rows: Sequence[Mapping[str, Any]]) -> str | None:
    clocks = [item for item in (_parse_available(row) for row in rows) if item is not None]
    if not clocks:
        return None
    return render_utc(max(clocks))


def project_market_context(
    definition: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    clock = _as_utc(as_of)
    as_of_text = render_utc(clock)
    current_seconds = int(definition["current_window_seconds"])
    lookback_seconds = int(definition["reference_lookback_seconds"])
    bucket_seconds = int(definition["reference_bucket_seconds"])
    current_start = clock - timedelta(seconds=current_seconds)
    reference_start = current_start - timedelta(seconds=lookback_seconds)
    observations = [
        dict(row)
        for row in (evidence.get("observations") or [])
        if isinstance(row, Mapping)
    ]
    members = [
        dict(row) for row in (evidence.get("members") or []) if isinstance(row, Mapping)
    ]
    schedules = evidence.get("schedules") if isinstance(evidence.get("schedules"), Mapping) else {}
    source_status = str(evidence.get("source_status") or "NOT_PRESENT")
    landmarks = list(definition["lifecycle_landmarks"])
    axes = list(definition["axes"])
    present_points = {
        str(row.get("point_id") or "")
        for row in observations
        if str(row.get("point_id") or "")
    }
    for item in landmarks:
        present_points.add(str(item["previous_point_id"]))

    current_obs = _select_rows(observations, start=current_start, end=clock)
    fingerprints: set[str] = set()
    fingerprint_by_sha: dict[str, str | None] = {}
    for digest, semantics in schedules.items():
        fingerprint = context_compatibility_sha256(definition, semantics)
        fingerprint_by_sha[str(digest)] = fingerprint
        if fingerprint:
            fingerprints.add(fingerprint)
    if not fingerprints:
        for row in current_obs:
            digest = str(row.get("schedule_sha256") or "")
            semantics = schedules.get(digest) if digest else None
            if isinstance(row.get("schedule_semantics"), Mapping):
                semantics = row.get("schedule_semantics")
            fingerprint = context_compatibility_sha256(
                definition, semantics if isinstance(semantics, Mapping) else None
            )
            if digest:
                fingerprint_by_sha[digest] = fingerprint
            if fingerprint:
                fingerprints.add(fingerprint)

    current_fingerprint = next(iter(sorted(fingerprints)), None)
    comparable_history = True
    incomparable_reason = "REFERENCE_SCOPE_MISMATCH"
    history_obs = _select_rows(observations, start=reference_start, end=current_start)
    if source_status != "PRESENT":
        comparable_history = False
        incomparable_reason = "SOURCE_NOT_PRESENT"
    elif current_fingerprint is None:
        comparable_history = False
        incomparable_reason = "SCHEDULE_SEMANTICS_MISSING"
    else:
        history_prints = set()
        for row in history_obs:
            digest = str(row.get("schedule_sha256") or "")
            semantics = row.get("schedule_semantics")
            if not isinstance(semantics, Mapping):
                semantics = schedules.get(digest)
            fingerprint = context_compatibility_sha256(
                definition, semantics if isinstance(semantics, Mapping) else None
            )
            if fingerprint:
                history_prints.add(fingerprint)
        if history_obs and history_prints and history_prints != {current_fingerprint}:
            comparable_history = False
            incomparable_reason = "REFERENCE_SCOPE_MISMATCH"
        elif history_obs and not history_prints:
            comparable_history = False
            incomparable_reason = "REFERENCE_SCOPE_MISMATCH"

    slices: list[dict[str, Any]] = []
    for landmark in landmarks:
        point_id = str(landmark["point_id"])
        previous_id = str(landmark["previous_point_id"])
        landmark_present = point_id in {
            str(row.get("point_id") or "") for row in observations
        } or point_id in {
            str(row.get("point_id") or "") for row in current_obs
        }
        if not landmark_present and point_id not in {
            str(row.get("point_id") or "") for row in observations
        }:
            landmark_status = "LANDMARK_NOT_IN_EVIDENCE"
        else:
            landmark_status = "PRESENT"
        current_at_point = _select_rows(
            current_obs, start=current_start, end=clock, point_id=point_id
        )
        previous_at_point = _select_rows(
            observations, start=reference_start, end=clock, point_id=previous_id
        )
        member_ids = {
            str(row.get("entity_id") or "")
            for row in members
            if str(row.get("entity_id") or "")
        }
        axis_cells: list[dict[str, Any]] = []
        for axis in axes:
            current_value, details = _axis_value(
                axis, current_at_point, previous_at_point
            )
            coverage = _coverage_counts(current_at_point, member_ids, axis)
            reference_values = (
                _reference_bucket_values(
                    axis,
                    observations,
                    point_id=point_id,
                    previous_point_id=previous_id,
                    previous_lookback_seconds=_previous_lookback_seconds(landmark, landmarks),
                    ref_start=reference_start,
                    ref_end=current_start,
                    bucket_seconds=bucket_seconds,
                )
                if comparable_history
                else []
            )
            relative, reason, bucket_count = _relative_state(
                current_value,
                reference_values,
                n_in_scope=int(coverage["n_in_scope"]),
                n_observed=int(coverage["n_observed"]),
                definition=definition,
                comparable=comparable_history,
                incomparable_reason=incomparable_reason,
            )
            observed_fraction = (
                str(
                    (Decimal(coverage["n_observed"]) / Decimal(coverage["n_in_scope"]))
                    .quantize(Decimal("0.0001"))
                )
                if coverage["n_in_scope"]
                else "0"
            )
            axis_cells.append(
                {
                    "axis_id": axis["axis_id"],
                    "unit": axis["unit"],
                    "aggregation": axis["aggregation"],
                    "field_ids": list(axis["field_ids"]),
                    "raw_value": _format_decimal(current_value),
                    "relative_state": relative,
                    "relative_reason": reason,
                    "n_in_scope": coverage["n_in_scope"],
                    "n_observed": coverage["n_observed"],
                    "n_missing": coverage["n_missing"],
                    "observed_fraction": observed_fraction,
                    "coverage_classes": {
                        key: coverage[key]
                        for key in (
                            "observed",
                            "typed_missing",
                            "disappeared",
                            "censored",
                            "capacity_excluded",
                            "sampling_excluded",
                            "x_ineligible",
                            "unknown",
                        )
                    },
                    "reference_bucket_count": bucket_count,
                    "latest_available_at": _latest_clock(current_at_point),
                    "detail_states": sorted(set(details)),
                }
            )
        slices.append(
            {
                "point_id": point_id,
                "due_offset_seconds": landmark["due_offset_seconds"],
                "previous_point_id": previous_id,
                "owner_label": landmark["owner_label"],
                "landmark_status": landmark_status,
                "axes": axis_cells,
            }
        )

    gaps: list[str] = []
    if source_status != "PRESENT":
        gaps.append("SOURCE_NOT_PRESENT" if source_status == "NOT_PRESENT" else source_status)
    if current_fingerprint is None and source_status == "PRESENT":
        gaps.append("SCHEDULE_SEMANTICS_MISSING")
    if (
        not comparable_history
        and source_status == "PRESENT"
        and incomparable_reason == "REFERENCE_SCOPE_MISMATCH"
    ):
        gaps.append("REFERENCE_SCOPE_MISMATCH")
    elif source_status == "PRESENT" and comparable_history and not history_obs:
        gaps.append("REFERENCE_INSUFFICIENT")
    if not current_obs and source_status == "PRESENT":
        gaps.append("NO_CURRENT_OBSERVATIONS")

    snapshot_identity = {
        "definition_id": definition["definition_id"],
        "definition_version": definition["definition_version"],
        "as_of": as_of_text,
        "context_compatibility_sha256": current_fingerprint,
        "source_status": source_status,
        "slices": [
            {
                "point_id": item["point_id"],
                "axes": [
                    {
                        "axis_id": cell["axis_id"],
                        "raw_value": cell["raw_value"],
                        "relative_state": cell["relative_state"],
                        "n_observed": cell["n_observed"],
                        "n_in_scope": cell["n_in_scope"],
                    }
                    for cell in item["axes"]
                ],
            }
            for item in slices
        ],
    }
    population = definition["population"]
    interpretation = {
        "kind": "CONTEXT_VECTOR",
        "composite_regime": False,
        "market_wide_claim": bool(population["market_wide_claim"]),
        "tested_context_binding": definition["tested_context_binding"],
        "default_landmark_id": definition["owner_default_landmark_id"],
    }
    for token in REGIME_TOKENS:
        if token in json.dumps(interpretation):
            raise MarketContextError("REGIME_TOKEN_FORBIDDEN")

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "definition_id": definition["definition_id"],
        "definition_version": definition["definition_version"],
        "as_of": as_of_text,
        "current_window": {
            "start": render_utc(current_start),
            "end": as_of_text,
            "seconds": current_seconds,
        },
        "reference_window": {
            "start": render_utc(reference_start),
            "end": render_utc(current_start),
            "seconds": lookback_seconds,
            "bucket_seconds": bucket_seconds,
        },
        "scope": {
            "population_description": population["description"],
            "market_wide_claim": False,
            "sampling_policy": (
                next(iter(schedules.values()), {}).get("sampling", {}).get("policy")
                if schedules
                else None
            ),
            "tokens_projection_id": str(
                (definition.get("tokens_projection") or {}).get("projection_id") or PROJECTION_ID
            ),
            "tokens_projection_version": str(
                (definition.get("tokens_projection") or {}).get("projection_version")
                or PROJECTION_VERSION
            ),
        },
        "source_status": source_status,
        "source_error": evidence.get("source_error"),
        "source_provenance": {
            "schedule_sha256": _schedule_sha_set(current_obs or observations),
            "activation_id": _activation_set(current_obs or observations),
            "partitions_read": evidence.get("partitions_read") or 0,
        },
        "context_compatibility_sha256": current_fingerprint,
        "context_snapshot_sha256": _canonical_sha256(snapshot_identity),
        "reference_status": (
            "COMPARABLE"
            if comparable_history and current_fingerprint
            else "REFERENCE_SCOPE_MISMATCH"
            if source_status == "PRESENT"
            else "NOT_APPLICABLE"
        ),
        "lifecycle_slices": slices,
        "gaps": gaps,
        "nonclaims": list(definition["non_claims"]),
        "interpretation": interpretation,
        "latest_evidence_available_at": _latest_clock(observations),
        "purity": dict(PURITY),
        "authority": {
            "pause_bot": False,
            "activate_bot": False,
            "modify_bot": False,
            "provider_calls": False,
            "deploy": False,
        },
    }


def git_data_capability(root: Path) -> dict[str, Any]:
    """Git market-feature availability. Never live market values."""

    try:
        config = load_surface_config(root)
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "error": str(getattr(exc, "args", [type(exc).__name__])[0]),
            "features": [],
        }
    features = []
    for item in config.get("features") or []:
        if not isinstance(item, Mapping):
            continue
        features.append(
            {
                "feature_id": item.get("feature_id"),
                "availability": item.get("availability_class") or item.get("availability"),
                "family": item.get("family"),
            }
        )
    return {
        "status": "GIT_CAPABILITY",
        "contract_id": config.get("contract_id"),
        "features": features,
        "not_live_market_values": True,
    }


def compose_market_context(
    root: Path,
    *,
    as_of: datetime | None = None,
    evidence: Mapping[str, Any] | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    definition = load_market_context_definition(root)
    clock = as_of or datetime.now(UTC)
    bundle = evidence or read_market_evidence(
        root, as_of=clock, definition=definition, data_root=data_root
    )
    if not isinstance(bundle, Mapping):
        bundle = empty_evidence_bundle(source_status="NOT_PRESENT")
    projection = project_market_context(definition, bundle, as_of=clock)
    projection["data_capability"] = git_data_capability(root)
    return projection
