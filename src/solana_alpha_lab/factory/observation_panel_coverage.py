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


def compute_evidence_role(
    *,
    hypothesis_registered_at: datetime,
    first_admission_at: datetime,
    first_y_available_at: datetime | None,
    closed_or_consumed: bool,
) -> str:
    if closed_or_consumed:
        return "CONSUMED_PRIOR_EVIDENCE"
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
    "schedule_covers",
    "source_population_key",
]
