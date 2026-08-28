"""Coverage resolver and computed scientific evidence roles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from solana_alpha_lab.factory.observation_schedule import (
    collection_projection,
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


def _manifest_has_y_observation(root, loaded: Mapping[str, Any]) -> bool:
    import json

    import pyarrow.parquet as pq

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
    for parquet_path in candidates:
        if not parquet_path.is_file():
            continue
        table = pq.read_table(parquet_path)
        if "point_id" not in table.column_names:
            continue
        for value in table.column("point_id").to_pylist():
            if str(value).startswith("Y"):
                return True
    return False


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
    states: dict[tuple[str, str], str] = {}
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
            key = (
                str(payload.get("schedule_sha256") or ""),
                str(payload.get("activation_id") or ""),
            )
            states[key] = str(payload.get("state") or "")
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
    hypothesis_registered_at: datetime,
    first_admission_at: datetime,
    first_y_available_at: datetime | None,
    closed_or_consumed: bool,
    y_availability_proven: bool = True,
) -> str:
    if closed_or_consumed:
        return "CONSUMED_PRIOR_EVIDENCE"
    if not y_availability_proven:
        return "EXPLORATORY_REUSE"
    if first_y_available_at is not None and hypothesis_registered_at >= first_y_available_at:
        return "EXPLORATORY_REUSE"
    if hypothesis_registered_at < first_admission_at:
        return "PROSPECTIVE_OOS"
    return "PROSPECTIVE_OUTCOME_BLIND_CONDITIONAL"


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
    ) -> dict[str, Any] | None:
        for snapshot_sha256, item in sorted(self.snapshots.items()):
            if item["availability_cutoff"] > cutoff:
                continue
            if schedule_covers(requested, item["schedule"]):
                return dict(item)
        return None

    def covering_snapshot(
        self,
        requested: Mapping[str, Any],
        cutoff: datetime,
    ) -> str | None:
        record = self.covering_snapshot_record(requested, cutoff)
        if record is None:
            return None
        return str(record["snapshot_sha256"])

    def covering_active_schedule(self, requested: Mapping[str, Any]) -> str | None:
        digest = schedule_sha256(requested)
        if digest in self.active_schedules:
            return digest
        for existing_digest, schedule in self.active_schedules.items():
            if schedule_covers(requested, schedule):
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
    "compute_evidence_role",
    "derive_first_y_available_at",
    "load_coverage_from_rdp",
    "schedule_covers",
    "source_population_key",
]
