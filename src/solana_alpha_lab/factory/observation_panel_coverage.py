"""Coverage resolver and computed scientific evidence roles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from solana_alpha_lab.factory.observation_schedule import (
    collection_projection,
    parse_utc,
    schedule_sha256,
)


def source_population_key(schedule: Mapping[str, Any]) -> str:
    projection = collection_projection(schedule)
    key = {
        "source_poll": projection["source_poll"],
        "population": projection["population"],
        "sampling": {
            "policy": projection["sampling"]["policy"],
            "seed": projection["sampling"]["seed"],
        },
    }
    return schedule_sha256({"schema": "smial.coverage-key", "schema_version": "1.0", **key})


def _sampling_cover_compatible(requested: Mapping[str, Any], available: Mapping[str, Any]) -> bool:
    req = requested["sampling"]
    avail = available["sampling"]
    if str(req["inclusion_probability"]) != str(avail["inclusion_probability"]):
        return False
    if int(req["max_members_per_utc_day"]) > int(avail["max_members_per_utc_day"]):
        return False
    if int(req["max_candidates_per_utc_day"]) > int(avail["max_candidates_per_utc_day"]):
        return False
    return True


def _x_cover_compatible(requested: Mapping[str, Any], available: Mapping[str, Any]) -> bool:
    if not _lateness_compatible(requested["x_point"], available["x_point"]):
        return False
    return set(requested["x_point"]["bundle_ids"]).issubset(set(available["x_point"]["bundle_ids"]))


SCIENTIFIC_CLOSED_DUE_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "DISAPPEARED",
        "CENSORED",
        "CENSORED_LATE",
        "X_POPULATION_INELIGIBLE",
        "DEPENDENCY_MISSING",
    }
)
UNRESOLVED_REQUIRED_DUE_STATES = frozenset(
    {
        "PENDING",
        "DUE",
        "CLAIMED",
        "IN_FLIGHT_CALL_INDETERMINATE",
    }
)


def required_point_ids(contract: Mapping[str, Any]) -> tuple[str, ...]:
    """X plus each requested Y point_id from a schedule or pending payload."""

    points: list[str] = []
    x_point = contract.get("required_x_point") or contract.get("x_point")
    if isinstance(x_point, Mapping) and x_point.get("point_id"):
        points.append(str(x_point["point_id"]))
    y_points = contract.get("required_y_points") or contract.get("y_points") or []
    if isinstance(y_points, Sequence):
        for item in y_points:
            if isinstance(item, Mapping) and item.get("point_id"):
                points.append(str(item["point_id"]))
    return tuple(points)


def _manifest_observation_paths(root, loaded: Mapping[str, Any]) -> list:
    import json

    manifest_id = str(loaded.get("dataset_manifest_id") or "")
    candidates = []
    if manifest_id:
        candidates.append(root / "datasets" / "parquet" / manifest_id / "observations.parquet")
    partitions_dir = root / "datasets" / "manifests" / "partitions"
    if partitions_dir.is_dir():
        for path in partitions_dir.glob("*.json"):
            part = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(part, Mapping):
                continue
            if str(part.get("dataset_manifest_id") or "") != manifest_id:
                continue
            partition_id = str(part.get("partition_id") or "").lower()
            location = part.get("logical_location")
            if not location or "member" in partition_id:
                continue
            candidates.append(root / str(location))
    return candidates


def _manifest_point_ids(root, loaded: Mapping[str, Any]) -> set[str]:
    import pyarrow.parquet as pq

    found: set[str] = set()
    for parquet_path in _manifest_observation_paths(root, loaded):
        if not parquet_path.is_file():
            continue
        table = pq.read_table(parquet_path)
        if "point_id" not in table.column_names:
            continue
        for value in table.column("point_id").to_pylist():
            if value is not None:
                found.add(str(value))
    return found


def _manifest_has_y_observation(root, loaded: Mapping[str, Any]) -> bool:
    return any(point_id.startswith("Y") for point_id in _manifest_point_ids(root, loaded))


def snapshot_manifest_point_ids(data_root, snapshot: Mapping[str, Any]) -> set[str]:
    """Point ids actually present in a snapshot's published observation parquet."""

    from pathlib import Path

    import json

    root = Path(data_root)
    found: set[str] = set()
    published = root / "datasets" / "manifests"
    for manifest_id in snapshot.get("dataset_manifest_ids") or []:
        manifest_path = published / f"{manifest_id}.json"
        if not manifest_path.is_file():
            continue
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, Mapping):
            continue
        found.update(_manifest_point_ids(root, loaded))
    return found


def due_rows_prove_required_points(
    due_rows: Sequence[Mapping[str, Any]],
    *,
    covering_schedule_sha256: str,
    required_points: Sequence[str],
) -> bool:
    """Fail closed unless every required point has only scientific terminal due rows."""

    if not required_points:
        return False
    scoped = [
        row
        for row in due_rows
        if str(row.get("schedule_sha256") or "") == covering_schedule_sha256
    ]
    if not scoped:
        return False
    by_point: dict[str, list[Mapping[str, Any]]] = {}
    for row in scoped:
        by_point.setdefault(str(row.get("point_id") or ""), []).append(row)
    for point_id in required_points:
        rows = by_point.get(str(point_id)) or []
        if not rows:
            return False
        if any(str(row.get("state") or "") in UNRESOLVED_REQUIRED_DUE_STATES for row in rows):
            return False
        if any(str(row.get("state") or "") == "BLOCKED_BUDGET" for row in rows):
            return False
        if not all(
            str(row.get("state") or "") in SCIENTIFIC_CLOSED_DUE_STATES for row in rows
        ):
            return False
    return True


def snapshot_proves_required_points(
    *,
    data_root,
    snapshot: Mapping[str, Any],
    covering_schedule_sha256: str,
    required_points: Sequence[str],
    due_rows: Sequence[Mapping[str, Any]] | None = None,
) -> bool:
    """An existing snapshot is reusable only if it independently proves this consumer."""

    schedule = snapshot.get("schedule")
    if isinstance(schedule, Mapping):
        digest = str(schedule.get("schedule_sha256") or "")
        if digest and digest != covering_schedule_sha256:
            return False
    if not required_points:
        return False
    parquet_points = snapshot_manifest_point_ids(data_root, snapshot)
    if parquet_points:
        return set(required_points).issubset(parquet_points)
    if due_rows is not None:
        return due_rows_prove_required_points(
            due_rows,
            covering_schedule_sha256=covering_schedule_sha256,
            required_points=required_points,
        )
    return False


def pending_consumer_satisfiable(
    *,
    data_root,
    covering_schedule_sha256: str,
    required_points: Sequence[str],
    due_rows: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any] | None = None,
    publication_complete: bool,
) -> bool:
    """Fail-closed WAITING_FOR_PANEL → SATISFIED gate from committed due/RDP truth."""

    if not covering_schedule_sha256 or not required_points:
        return False
    if not publication_complete:
        return False
    if not due_rows_prove_required_points(
        due_rows,
        covering_schedule_sha256=covering_schedule_sha256,
        required_points=required_points,
    ):
        return False
    if snapshot is not None:
        return snapshot_proves_required_points(
            data_root=data_root,
            snapshot=snapshot,
            covering_schedule_sha256=covering_schedule_sha256,
            required_points=required_points,
            due_rows=due_rows,
        )
    return True


def derive_first_y_available_at(
    data_root,
    schedule_sha256: str,
) -> tuple[datetime | None, bool]:
    """Return (first_y_available_at, proven_from_rdp). Unproven never promotes OOS."""
    from pathlib import Path

    import json

    from solana_alpha_lab.factory.observation_schedule import parse_utc
    from solana_alpha_lab.factory.research_store import ResearchStore

    root = Path(data_root)
    published = root / "datasets" / "manifests"
    if published.is_dir() is False:
        return None, False
    store = ResearchStore(root)
    batch_ids: set[str] = set()
    member_ids: set[str] = set()
    for record in store.iter_committed_records():
        kind = str(record.record_kind)
        payload = json.loads(record.payload_json)
        if payload.get("schedule_sha256") != schedule_sha256:
            continue
        if kind == "OBSERVATION_BATCH":
            batch_ids.add(str(payload.get("dataset_manifest_id") or ""))
        if kind == "OBSERVATION_MEMBER_BATCH":
            member_ids.add(str(payload.get("dataset_manifest_id") or ""))
    earliest: datetime | None = None
    proven = False
    for manifest_id in batch_ids:
        marker = published / f"{manifest_id}.published"
        manifest_path = published / f"{manifest_id}.json"
        if not marker.is_file() or not manifest_path.is_file():
            continue
        if manifest_id not in member_ids:
            continue
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not _manifest_has_y_observation(root, loaded):
            continue
        available = loaded.get("first_reliable_available_at")
        if not available:
            continue
        try:
            instant = parse_utc(available) if isinstance(available, str) else None
        except Exception:
            instant = None
        if instant is None:
            continue
        proven = True
        if earliest is None or instant < earliest:
            earliest = instant
    return earliest, proven


def load_coverage_from_rdp(data_root) -> CoverageIndex:
    """Rebuild CoverageIndex from committed RDP schedule, state and snapshot events."""
    from pathlib import Path

    import json

    from solana_alpha_lab.factory.observation_schedule import parse_utc
    from solana_alpha_lab.factory.research_store import ResearchStore

    root = Path(data_root)
    index = CoverageIndex()
    try:
        store = ResearchStore(root)
    except Exception:
        return index
    schedules: dict[str, dict[str, Any]] = {}
    snapshots: list[dict[str, Any]] = []
    state_records: list[tuple[str, str, str, int, str]] = []
    for record in store.iter_committed_records():
        kind = str(record.record_kind)
        payload = json.loads(record.payload_json)
        if kind == "OBSERVATION_SCHEDULE":
            digest = str(payload.get("schedule_sha256") or "")
            document = payload.get("schedule")
            if digest and isinstance(document, Mapping):
                schedules[digest] = dict(document)
        elif kind == "OBSERVATION_PANEL_SNAPSHOT":
            if isinstance(payload, Mapping):
                snapshots.append(dict(payload))
        elif kind == "OBSERVATION_SCHEDULE_STATE":
            state_records.append(
                (
                    str(payload.get("schedule_sha256") or ""),
                    str(payload.get("activation_id") or ""),
                    str(payload.get("state") or ""),
                    int(payload.get("transition_sequence") or 0),
                    record.record_id,
                )
            )
    states: dict[tuple[str, str], str] = {}
    for schedule_digest, activation_id, state, sequence, record_id in sorted(
        state_records,
        key=lambda item: (item[0], item[1], item[3], item[4]),
    ):
        del sequence, record_id
        states[(schedule_digest, activation_id)] = state
    for digest, _activation in {key for key, state in states.items() if state == "ACTIVE"}:
        document = schedules.get(digest)
        if document is not None:
            index.add_active_schedule(document)
    for snap in snapshots:
        digest = str(snap.get("schedule_sha256") or "")
        document = schedules.get(digest)
        cutoff_raw = snap.get("availability_cutoff")
        snapshot_sha = snap.get("snapshot_sha256")
        if document is None or not isinstance(cutoff_raw, str) or not snapshot_sha:
            continue
        try:
            cutoff = parse_utc(cutoff_raw)
        except Exception:
            continue
        index.add_snapshot(
            snapshot_sha256=str(snapshot_sha),
            schedule=document,
            availability_cutoff=cutoff,
            dataset_manifest_ids=list(snap.get("dataset_manifest_ids") or []),
            dataset_fingerprints=list(snap.get("dataset_fingerprints") or []),
        )
    return index


def compute_evidence_role(
    *,
    hypothesis_registered_at: datetime | None,
    first_admission_at: datetime,
    first_y_available_at: datetime | None,
    closed_or_consumed: bool,
    y_availability_proven: bool = True,
) -> str:
    if closed_or_consumed:
        return "CONSUMED_PRIOR_EVIDENCE"
    if hypothesis_registered_at is None:
        return "EXPLORATORY_REUSE"
    if not y_availability_proven:
        return "EXPLORATORY_REUSE"
    if first_y_available_at is not None and hypothesis_registered_at >= first_y_available_at:
        return "EXPLORATORY_REUSE"
    if hypothesis_registered_at < first_admission_at:
        return "PROSPECTIVE_OOS"
    return "PROSPECTIVE_OUTCOME_BLIND_CONDITIONAL"


def admission_window_open(schedule: Mapping[str, Any], now: datetime) -> bool:
    """True only while new admission/discovery is still authorized."""

    activation = schedule.get("activation")
    if not isinstance(activation, Mapping):
        return False
    starts = parse_utc(activation["starts_at"])
    stops = parse_utc(activation["stops_admitting_at"])
    return starts <= now < stops


def resolve_authoritative_hypothesis_registered_at(
    data_root,
    *,
    hypothesis_version_id: str | None = None,
    hypothesis_definition_sha256: str | None = None,
) -> datetime | None:
    """Resolve immutable HFIC/RDP hypothesis registration time. Never uses spec.as_of."""

    from pathlib import Path

    import json

    from solana_alpha_lab.factory.research_store import ResearchStore

    if not hypothesis_version_id and not hypothesis_definition_sha256:
        return None
    try:
        store = ResearchStore(Path(data_root))
    except Exception:
        return None
    earliest: datetime | None = None
    for record in store.iter_committed_records():
        if str(record.record_kind) != "HYPOTHESIS_VERSION":
            continue
        payload = json.loads(record.payload_json)
        if not isinstance(payload, Mapping):
            continue
        version_match = bool(hypothesis_version_id) and (
            str(payload.get("hypothesis_version_id") or "") == hypothesis_version_id
            or str(record.entity_id) == hypothesis_version_id
            or str(record.hypothesis_version_id or "") == hypothesis_version_id
        )
        definition_match = bool(hypothesis_definition_sha256) and str(
            payload.get("definition_sha256") or ""
        ) == hypothesis_definition_sha256
        if not version_match and not definition_match:
            continue
        instant = record.created_at
        payload_created = payload.get("created_at")
        if isinstance(payload_created, str):
            try:
                instant = min(instant, parse_utc(payload_created))
            except Exception:
                pass
        if earliest is None or instant < earliest:
            earliest = instant
    return earliest


def _lateness_compatible(requested: Mapping[str, Any], available: Mapping[str, Any]) -> bool:
    if int(available["due_offset_seconds"]) != int(requested["due_offset_seconds"]):
        return False
    return int(available["allowed_lateness_seconds"]) <= int(
        requested["allowed_lateness_seconds"]
    )


def schedule_covers(requested: Mapping[str, Any], available: Mapping[str, Any]) -> bool:
    if collection_projection(requested) == collection_projection(available):
        return True
    if source_population_key(requested) != source_population_key(available):
        return False
    if not _sampling_cover_compatible(requested, available):
        return False
    if not _x_cover_compatible(requested, available):
        return False
    available_y = {str(item["point_id"]): item for item in available["y_points"]}
    for point in requested["y_points"]:
        match = available_y.get(str(point["point_id"]))
        if match is None:
            return False
        if not _lateness_compatible(point, match):
            return False
        requested_bundles = set(point["bundle_ids"])
        if not requested_bundles.issubset(set(match["bundle_ids"])):
            return False
    return True


@dataclass
class CoverageIndex:
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_schedules: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_snapshot(
        self,
        *,
        snapshot_sha256: str,
        schedule: Mapping[str, Any],
        availability_cutoff: datetime,
        first_y_available_at: datetime | None = None,
        dataset_manifest_ids: Sequence[str] | None = None,
        dataset_fingerprints: Sequence[str] | None = None,
    ) -> None:
        self.snapshots[snapshot_sha256] = {
            "schedule": dict(schedule),
            "availability_cutoff": availability_cutoff,
            "snapshot_sha256": snapshot_sha256,
            "first_y_available_at": first_y_available_at,
            "dataset_manifest_ids": list(dataset_manifest_ids or []),
            "dataset_fingerprints": list(dataset_fingerprints or []),
        }

    def add_active_schedule(self, schedule: Mapping[str, Any]) -> None:
        digest = str(schedule.get("schedule_sha256") or schedule_sha256(schedule))
        self.active_schedules[digest] = dict(schedule)

    def covering_snapshot_record(
        self,
        requested: Mapping[str, Any],
        cutoff: datetime,
        *,
        data_root=None,
        due_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        required = required_point_ids(requested)
        for snapshot_sha256, item in sorted(self.snapshots.items()):
            if item["availability_cutoff"] > cutoff:
                continue
            if not schedule_covers(requested, item["schedule"]):
                continue
            covering = str(
                item["schedule"].get("schedule_sha256")
                or schedule_sha256(item["schedule"])
            )
            live_due = [
                row
                for row in (due_rows or ())
                if str(row.get("schedule_sha256") or "") == covering
            ]
            if live_due:
                if not snapshot_proves_required_points(
                    data_root=data_root,
                    snapshot=item,
                    covering_schedule_sha256=covering,
                    required_points=required,
                    due_rows=live_due,
                ):
                    continue
            return dict(item)
        return None

    def covering_snapshot(
        self,
        requested: Mapping[str, Any],
        cutoff: datetime,
        *,
        data_root=None,
        due_rows: Sequence[Mapping[str, Any]] | None = None,
    ) -> str | None:
        record = self.covering_snapshot_record(
            requested,
            cutoff,
            data_root=data_root,
            due_rows=due_rows,
        )
        if record is None:
            return None
        return str(record["snapshot_sha256"])

    def covering_active_schedule(
        self,
        requested: Mapping[str, Any],
        now: datetime | None = None,
    ) -> str | None:
        digest = schedule_sha256(requested)
        candidates: list[tuple[str, dict[str, Any]]] = []
        if digest in self.active_schedules:
            candidates.append((digest, self.active_schedules[digest]))
        for existing_digest, schedule in self.active_schedules.items():
            if existing_digest == digest:
                continue
            if schedule_covers(requested, schedule):
                candidates.append((existing_digest, schedule))
        for existing_digest, schedule in candidates:
            if now is not None and not admission_window_open(schedule, now):
                continue
            return existing_digest
        return None

    def admission_overlap_predecessor(self, requested: Mapping[str, Any]) -> str | None:
        requested_key = source_population_key(requested)
        requested_digest = schedule_sha256(requested)
        for digest, schedule in self.active_schedules.items():
            if digest == requested_digest:
                continue
            if source_population_key(schedule) == requested_key:
                return digest
        return None


__all__ = [
    "CoverageIndex",
    "SCIENTIFIC_CLOSED_DUE_STATES",
    "UNRESOLVED_REQUIRED_DUE_STATES",
    "admission_window_open",
    "compute_evidence_role",
    "derive_first_y_available_at",
    "due_rows_prove_required_points",
    "load_coverage_from_rdp",
    "pending_consumer_satisfiable",
    "required_point_ids",
    "resolve_authoritative_hypothesis_registered_at",
    "schedule_covers",
    "snapshot_proves_required_points",
    "source_population_key",
]
