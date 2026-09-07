"""Bounded immutable Observation RDP reader for Market Context.

Normalizes current and historical rows to one evidence shape. Does not write.
Does not call providers. Does not treat operational SQLite as market truth.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from solana_alpha_lab.factory.data_root import resolve_existing_data_root
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc

COVERAGE_FROM_STATE = {
    "OBSERVED": "observed",
    "MISSING_TYPED": "typed_missing",
    "DISAPPEARED": "disappeared",
    "CENSORED": "censored",
    "CENSORED_LATE": "censored",
    "X_POPULATION_INELIGIBLE": "x_ineligible",
    "NOT_SELECTED_CAPACITY": "capacity_excluded",
    "CAPACITY_EXCLUDED": "capacity_excluded",
    "BLOCKED_BUDGET": "capacity_excluded",
    "NOT_SELECTED_SAMPLING": "sampling_excluded",
    "PREDICATE_REJECTED": "x_ineligible",
    "DEPENDENCY_MISSING": "typed_missing",
    "EXCLUDED_AMBIGUOUS": "unknown",
    "IN_FLIGHT_CALL_INDETERMINATE": "unknown",
    "ADMITTED": "unknown",
    "SAMPLED_MEMBER": "unknown",
    "SCHEDULED": "unknown",
}


class MarketEvidenceError(ValueError):
    """Typed market evidence read fault."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def coverage_class_for(state: object) -> str:
    return COVERAGE_FROM_STATE.get(str(state or ""), "unknown")


def coverage_class_for_member(state: object) -> str:
    mapped = coverage_class_for(state)
    if mapped == "observed":
        return "unknown"
    return mapped


def parse_market_clock(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        return parse_utc(text)
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def empty_evidence_bundle(*, source_status: str, source_error: str | None = None) -> dict[str, Any]:
    return {
        "source_status": source_status,
        "source_error": source_error,
        "observations": [],
        "members": [],
        "schedules": {},
        "partitions_read": 0,
        "provider_calls": 0,
        "writes": 0,
        "members_incomplete": False,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketEvidenceError("AS_OF_NOT_UTC")
    return value.astimezone(UTC)


def schedule_semantics_from_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Scientific subset for comparability. Excludes activation dates and budgets.

    Tokens projection identity and Market axis field IDs live on the Git
    definition fingerprint, not as retroactive stamps on historical schedules.
    Schedule-owned source identity is primitive_id / query_profile_id.
    """

    population = document.get("population") if isinstance(document.get("population"), Mapping) else {}
    sampling = document.get("sampling") if isinstance(document.get("sampling"), Mapping) else {}
    source_poll = document.get("source_poll") if isinstance(document.get("source_poll"), Mapping) else {}
    x_point = document.get("x_point") if isinstance(document.get("x_point"), Mapping) else {}
    y_points = [
        {
            "point_id": str(item.get("point_id") or ""),
            "due_offset_seconds": int(item.get("due_offset_seconds") or 0),
        }
        for item in (document.get("y_points") or [])
        if isinstance(item, Mapping)
    ]
    return {
        "population": {
            "entity_type": population.get("entity_type"),
            "entity_key_field_id": population.get("entity_key_field_id"),
            "anchor_field_id": population.get("anchor_field_id"),
            "source_predicates": list(population.get("source_predicates") or []),
            "x_eligibility_predicates": list(population.get("x_eligibility_predicates") or []),
        },
        "lifecycle": {
            "x_point": {
                "point_id": x_point.get("point_id"),
                "due_offset_seconds": x_point.get("due_offset_seconds"),
            },
            "y_points": y_points,
        },
        "sampling": {
            "policy": sampling.get("policy"),
            "inclusion_probability": sampling.get("inclusion_probability"),
            "max_candidates_per_utc_day": sampling.get("max_candidates_per_utc_day"),
            "max_members_per_utc_day": sampling.get("max_members_per_utc_day"),
            "overflow_state": sampling.get("overflow_state"),
            "seed": sampling.get("seed"),
        },
        "source_poll": {
            "primitive_id": source_poll.get("primitive_id"),
            "query_profile_id": source_poll.get("query_profile_id"),
            "period_seconds": source_poll.get("period_seconds"),
        },
    }


def horizon_start(as_of: datetime, definition: Mapping[str, Any]) -> datetime:
    current = int(definition["current_window_seconds"])
    lookback = int(definition["reference_lookback_seconds"])
    extra = max(
        int(item["due_offset_seconds"]) - int(previous)
        for item in definition["lifecycle_landmarks"]
        for previous in [next(
            (
                int(other["due_offset_seconds"])
                for other in definition["lifecycle_landmarks"]
                if other["point_id"] == item["previous_point_id"]
            ),
            0,
        )]
    )
    extra = max(extra, 300)
    return _as_utc(as_of) - timedelta(seconds=current + lookback + extra)


def _utc_day_set(start: datetime, end: datetime) -> set[str]:
    days: set[str] = set()
    cursor = start.astimezone(UTC).date()
    last = end.astimezone(UTC).date()
    while cursor <= last:
        days.add(cursor.isoformat())
        cursor = cursor + timedelta(days=1)
    return days


def _is_observation_panel_partition(payload: Mapping[str, Any]) -> bool:
    dataset_id = str(payload.get("dataset_id") or "")
    if dataset_id:
        return dataset_id.startswith("observation-panel-")
    return False


def _partition_available(payload: Mapping[str, Any]) -> datetime | None:
    return parse_market_clock(payload.get("first_reliable_available_at"))


def _publication_key(payload: Mapping[str, Any]) -> tuple[str, str] | None:
    day = _partition_day(str(payload.get("partition_id") or ""))
    if day is None:
        return None
    publication = str(
        payload.get("dataset_manifest_id") or payload.get("dataset_id") or ""
    )
    return day, publication


def _dataset_id_for_manifest(manifests_dir: Path, dataset_manifest_id: str) -> str:
    if not dataset_manifest_id:
        return ""
    path = manifests_dir / f"{dataset_manifest_id}.json"
    if path.is_file() is False:
        return ""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(loaded, Mapping):
        return ""
    return str(loaded.get("dataset_id") or "")


def _enrich_partition(payload: Mapping[str, Any], manifests_dir: Path) -> dict[str, Any]:
    item = dict(payload)
    if item.get("dataset_id"):
        return item
    dataset_id = _dataset_id_for_manifest(
        manifests_dir, str(item.get("dataset_manifest_id") or "")
    )
    if dataset_id:
        item["dataset_id"] = dataset_id
    return item


def _partition_day(partition_id: str) -> str | None:
    text = str(partition_id or "")
    if not text.startswith("utc-day-"):
        return None
    rest = text[len("utc-day-") :]
    if rest.endswith("-members"):
        rest = rest[: -len("-members")]
    compact = rest.replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return None


def _list_partition_payloads(data_root: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    manifests_dir = data_root / "datasets" / "manifests"
    partitions_dir = manifests_dir / "partitions"
    if partitions_dir.is_dir():
        for path in sorted(partitions_dir.glob("*.json")):
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(loaded, dict):
                payloads.append(_enrich_partition(loaded, manifests_dir))
        return payloads
    manifests_dir = data_root / "datasets" / "manifests"
    if not manifests_dir.is_dir():
        return []
    for marker in sorted(manifests_dir.glob("dataset-*.published")):
        try:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifest_id = str(marker_payload.get("dataset_manifest_id") or "")
        manifest_path = manifests_dir / f"{manifest_id}.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, Mapping):
            continue
        if str(manifest.get("dataset_id") or "").startswith("observation-panel-") is False:
            continue
        for partition in manifest.get("partitions") or []:
            if isinstance(partition, Mapping):
                payloads.append(dict(partition))
    return payloads


def _load_rows(data_root: Path, location: str, *, members: bool) -> list[dict[str, Any]]:
    if not location or Path(location).is_absolute() or ".." in Path(location).parts:
        return []
    path = data_root / location
    if members:
        try:
            from solana_alpha_lab.factory.members_snapshot_delta import (
                MembersDeltaError,
                load_member_rows_for_location,
            )

            try:
                rows = load_member_rows_for_location(data_root, location)
            except MembersDeltaError:
                if path.is_file() is False:
                    return []
                rows = pq.read_table(path).to_pylist()
        except Exception:
            if path.is_file() is False:
                return []
            rows = pq.read_table(path).to_pylist()
    else:
        if path.is_file() is False:
            return []
        rows = pq.read_table(path).to_pylist()
    return [_decode_loaded_row(row) for row in rows if isinstance(row, Mapping)]


def _decode_loaded_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for key in ("field_values", "schedule_semantics"):
        raw = item.get(key)
        if isinstance(raw, str):
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError:
                continue
            item[key] = loaded
    return item


def _load_schedules_from_projection(
    data_root: Path,
    needed: set[str],
    *,
    definition: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    projection = data_root / "projections" / "research_memory.duckdb"
    if not needed or projection.is_file() is False:
        return found
    try:
        import duckdb
    except ImportError:
        return found
    connection = None
    try:
        connection = duckdb.connect(
            str(projection.resolve(strict=True)),
            read_only=True,
            config={
                "enable_external_access": "false",
                "allow_unsigned_extensions": "false",
            },
        )
        connection.execute("SET TimeZone = 'UTC'")
        connection.execute("SET lock_configuration = true")
        placeholders = ",".join(["?"] * len(needed))
        rows = connection.execute(
            f"""
            SELECT entity_id, payload_json
            FROM _research_events
            WHERE record_kind = 'OBSERVATION_SCHEDULE'
              AND entity_id IN ({placeholders})
            """,
            list(needed),
        ).fetchall()
    except Exception:
        return found
    finally:
        if connection is not None:
            connection.close()
    for entity_id, payload_json in rows:
        try:
            payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, Mapping):
            continue
        document = payload.get("schedule")
        if not isinstance(document, Mapping):
            continue
        digest = str(entity_id or payload.get("schedule_sha256") or "")
        if digest in needed:
            found[digest] = schedule_semantics_from_document(document)
    return found


def read_market_evidence(
    root: Path,
    *,
    as_of: datetime,
    definition: Mapping[str, Any],
    data_root: Path | None = None,
    schedules: Mapping[str, Mapping[str, Any]] | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    members: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load only the 8-day-bounded observation-panel partitions needed for as_of."""

    if observations is not None:
        injected_schedules = {
            str(key): dict(value)
            for key, value in (schedules or {}).items()
        }
        return {
            "source_status": "PRESENT",
            "source_error": None,
            "observations": [dict(item) for item in observations],
            "members": [dict(item) for item in (members or [])],
            "schedules": injected_schedules,
            "partitions_read": 0,
            "provider_calls": 0,
            "writes": 0,
            "members_incomplete": False,
        }

    discovery = resolve_existing_data_root(root, explicit_data_root=data_root)
    if discovery.status != "PRESENT" or discovery.root is None:
        status = discovery.status if discovery.status in {"NOT_PRESENT", "UNAVAILABLE"} else "NOT_PRESENT"
        return empty_evidence_bundle(
            source_status=status,
            source_error=discovery.error or "RESEARCH_STORE_NOT_PRESENT",
        )

    clock = _as_utc(as_of)
    start = horizon_start(clock, definition)
    days = _utc_day_set(start, clock)
    selected: list[dict[str, Any]] = []
    for payload in _list_partition_payloads(discovery.root):
        if _is_observation_panel_partition(payload) is False:
            continue
        partition_available = _partition_available(payload)
        if partition_available is None or partition_available > clock:
            continue
        partition_id = str(payload.get("partition_id") or "")
        day = _partition_day(partition_id)
        if day is None or day not in days:
            continue
        selected.append(payload)

    observation_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    members_incomplete = False
    for payload in selected:
        location = str(payload.get("logical_location") or "")
        partition_id = str(payload.get("partition_id") or "")
        is_members = partition_id.endswith("-members")
        rows = _load_rows(discovery.root, location, members=is_members)
        if is_members and not rows:
            members_incomplete = True
        tagged = []
        day = _partition_day(partition_id)
        available = payload.get("first_reliable_available_at")
        for row in rows:
            item = dict(row)
            if day:
                item["_partition_day"] = day
            if available:
                item["_partition_available_at"] = available
            tagged.append(item)
        if is_members:
            member_rows.extend(tagged)
        else:
            observation_rows.extend(tagged)

    obs_keys: set[tuple[str, str]] = set()
    member_keys: set[tuple[str, str]] = set()
    for payload in selected:
        key = _publication_key(payload)
        if key is None:
            continue
        if str(payload.get("partition_id") or "").endswith("-members"):
            member_keys.add(key)
        else:
            obs_keys.add(key)
    if obs_keys - member_keys:
        members_incomplete = True

    needed = {
        str(row.get("schedule_sha256") or "")
        for row in (*observation_rows, *member_rows)
        if str(row.get("schedule_sha256") or "")
    }
    found_schedules = {
        str(key): dict(value)
        for key, value in (schedules or {}).items()
        if str(key) in needed
    }
    missing = needed - set(found_schedules)
    if missing:
        found_schedules.update(
            _load_schedules_from_projection(
                discovery.root, missing, definition=definition
            )
        )

    return {
        "source_status": "PRESENT",
        "source_error": None,
        "observations": observation_rows,
        "members": member_rows,
        "schedules": found_schedules,
        "partitions_read": len(selected),
        "provider_calls": 0,
        "writes": 0,
        "members_incomplete": members_incomplete,
        "horizon_start": render_utc(start),
        "as_of": render_utc(clock),
    }
