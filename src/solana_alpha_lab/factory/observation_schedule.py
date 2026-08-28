"""ObservationSchedule v1.0 identity, canonical hashing and document load."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SCHEMA_RELATIVE = "catalog/schemas/observation_schedule_v1.schema.json"
MAX_OFFSET_SECONDS = 2_592_000
ALLOWED_PERIODS = frozenset({60, 300, 900, 3600, 86400})
UNSAFE_RUNTIME_RE = re.compile(
    r"(https?://)|(\bSELECT\b)|(\bDROP\b)|(\blambda\b)|(\beval\b)|(\bexec\b)"
    r"|(__import__)|(\bjavascript:)",
    re.IGNORECASE,
)
_HASH_EXCLUDE = frozenset(
    {
        "schedule_key",
        "schedule_sha256",
        "experiment_id",
        "hypothesis_version",
        "question",
        "estimand",
        "falsifier",
        "method",
        "parameters",
        "terminal_outcomes",
        "what_changed",
        "requested_evidence_role",
        "estimator_id",
        "collection_mode",
    }
)


class ObservationScheduleError(ValueError):
    """Typed ObservationSchedule contract failure."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ObservationScheduleError("TIMESTAMP_INVALID")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ObservationScheduleError("TIMESTAMP_INVALID")
    return parsed.astimezone(UTC)


def render_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ObservationScheduleError("TIMESTAMP_INVALID")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_schema(root: Path) -> dict[str, Any]:
    path = root / SCHEMA_RELATIVE
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_INVALID")
    return loaded


def _reject_unsafe(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ObservationScheduleError("DENY_UNSAFE_RUNTIME_CODE")
            lowered = key.casefold()
            if lowered in {"url", "sql", "python", "expression", "code", "eval", "exec"}:
                raise ObservationScheduleError("DENY_UNSAFE_RUNTIME_CODE")
            _reject_unsafe(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_unsafe(item)
        return
    if isinstance(value, str) and UNSAFE_RUNTIME_RE.search(value):
        raise ObservationScheduleError("DENY_UNSAFE_RUNTIME_CODE")


def collection_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the hashable collection subset, excluding scientific identity."""

    if not isinstance(document, Mapping):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_INVALID")
    projection = {
        key: value
        for key, value in document.items()
        if isinstance(key, str) and key not in _HASH_EXCLUDE
    }
    return json.loads(canonical_json_bytes(projection).decode("utf-8"))


def schedule_sha256(document: Mapping[str, Any]) -> str:
    return canonical_sha256(collection_projection(document))


def validate_schedule_semantics(document: Mapping[str, Any]) -> None:
    _reject_unsafe(document)
    x_point = document["x_point"]
    y_points = list(document["y_points"])
    if not isinstance(x_point, Mapping) or not y_points:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    seen_ids: set[str] = set()
    previous = int(x_point["due_offset_seconds"])
    x_id = str(x_point["point_id"])
    if not x_id.startswith("X"):
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    seen_ids.add(x_id)
    if previous < 0 or previous > MAX_OFFSET_SECONDS:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    if "relative_to" in x_point or "after_x" in x_point:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    for point in y_points:
        if not isinstance(point, Mapping):
            raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
        if "relative_to" in point or "after_x" in point:
            raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
        point_id = str(point["point_id"])
        if not point_id.startswith("Y") or point_id in seen_ids:
            raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
        seen_ids.add(point_id)
        offset = int(point["due_offset_seconds"])
        if offset <= previous or offset > MAX_OFFSET_SECONDS:
            raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
        previous = offset
    period = int(document["source_poll"]["period_seconds"])
    if period not in ALLOWED_PERIODS:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    activation = document["activation"]
    starts = parse_utc(activation["starts_at"])
    stops = parse_utc(activation["stops_admitting_at"])
    if stops <= starts:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    budgets = document["budgets"]
    if str(budgets["cash_usd_max"]) != "0" or budgets["retry"] is not False or budgets["fallback"] is not False:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    max_y = int(y_points[-1]["due_offset_seconds"])
    required_retention = math.ceil(max_y / 86400) + 7
    if int(document["retention"]["raw_retention_days"]) < required_retention:
        raise ObservationScheduleError("BLOCKED_BUDGET")
    sampling = document["sampling"]
    try:
        probability = Decimal(str(sampling["inclusion_probability"]))
    except (InvalidOperation, ValueError) as exc:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP") from exc
    if probability < 0 or probability > 1:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    if sampling["policy"] == "ALL_UNDER_CAP" and probability != Decimal("1.0") and probability != Decimal("1"):
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")


def validate_observation_schedule(
    document: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_INVALID")
    try:
        jsonschema.validate(dict(document), _load_schema(root))
    except jsonschema.ValidationError as exc:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_INVALID") from exc
    validate_schedule_semantics(document)
    payload = dict(document)
    digest = schedule_sha256(payload)
    existing = payload.get("schedule_sha256")
    if existing is not None and existing != digest:
        raise ObservationScheduleError("INVALID_IDENTITY")
    payload["schedule_sha256"] = digest
    return payload


def load_observation_schedule(root: Path, relative: str) -> dict[str, Any]:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_PATH_UNSAFE")
    try:
        loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_INVALID")
    return validate_observation_schedule(loaded, root=root)


def schedule_from_observation_request(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_INVALID")
    _reject_unsafe(request)
    document = {
        "schema": "smial.observation-schedule",
        "schema_version": "1.0",
        "schedule_key": request["schedule_key"],
        "activation": dict(request["activation"]),
        "source_poll": dict(request["source_poll"]),
        "population": dict(request["population"]),
        "sampling": dict(request["sampling"]),
        "x_point": dict(request["x_point"]),
        "y_points": [dict(item) for item in request["y_points"]],
        "missingness": dict(request["missingness"]),
        "disappearance": dict(request["disappearance"]),
        "budgets": dict(request["budgets"]),
        "retention": dict(request["retention"]),
        "authority": dict(request["authority"]),
        "outputs": dict(request["outputs"]),
    }
    return document


__all__ = [
    "ALLOWED_PERIODS",
    "MAX_OFFSET_SECONDS",
    "ObservationScheduleError",
    "canonical_json_bytes",
    "canonical_sha256",
    "collection_projection",
    "load_observation_schedule",
    "parse_utc",
    "render_utc",
    "schedule_from_observation_request",
    "schedule_sha256",
    "validate_observation_schedule",
    "validate_schedule_semantics",
]
