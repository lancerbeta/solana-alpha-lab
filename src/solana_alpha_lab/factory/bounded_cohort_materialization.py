"""Bounded mature-cohort materialization: plan, lock, wall, progress, routing."""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.members_snapshot_delta import (
    LAYOUT_KIND,
    LEGACY_KIND,
    MembersDeltaError,
    _contained_data_path,
    read_member_layout,
)
from solana_alpha_lab.factory.research_store import (
    PidLiveness,
    probe_local_pid,
)

BOUNDED_WORK_CLASS = "BOUNDED_COHORT_WINDOW"
UNBOUNDED_PLAN = "UNBOUNDED_MATERIALIZATION_PLAN"
BUILD_ALREADY_RUNNING = "BUILD_ALREADY_RUNNING"
WALL_BUDGET_EXCEEDED = "MATERIALIZATION_WALL_BUDGET_EXCEEDED"
OBSERVATION_LINEAGE_INCOMPLETE = "OBSERVATION_LINEAGE_INCOMPLETE"
DEFAULT_WALL_BUDGET_S = 90 * 60
LOCK_NAME = ".materialize.lock"
PROGRESS_NAME = "progress.json"
GLOBAL_PUBLISHED_GLOB = "dataset-*.published"


class BoundedMaterializationError(ValueError):
    """Fail-closed bounded materialization error with a stable code."""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _render_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_lifecycle_instant(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def cohort_scratch_root(observation_rdp_root: Path, cohort_id: str) -> Path:
    return Path(observation_rdp_root) / "live_observation_rebuild" / f"cohort={cohort_id}"


def lock_path_for_cohort(observation_rdp_root: Path, cohort_id: str) -> Path:
    return cohort_scratch_root(observation_rdp_root, cohort_id) / LOCK_NAME


def directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += int((Path(root) / name).stat().st_size)
            except OSError:
                continue
    return total


@dataclass
class WallBudget:
    limit_s: float
    started_monotonic: float = field(default_factory=time.monotonic)

    def elapsed_s(self) -> float:
        return max(0.0, time.monotonic() - self.started_monotonic)

    def check(self, *, stage: str) -> None:
        del stage
        if self.elapsed_s() > float(self.limit_s):
            raise BoundedMaterializationError(WALL_BUDGET_EXCEEDED)


@dataclass
class MaterializationProgress:
    path: Path
    started_at: str
    stage: str = "start"
    units_total: int = 0
    units_completed: int = 0
    pit_targets_total: int = 0
    pit_targets_consumed: int = 0
    delta_files_planned: int = 0
    delta_files_applied: int = 0
    observation_files_planned: int = 0
    observation_files_completed: int = 0
    member_payload_bytes_read: int = 0
    observation_payload_bytes_read: int = 0
    scratch_current_bytes: int = 0
    scratch_peak_bytes: int = 0
    canonical_commit_started: bool = False
    canonical_commit_complete: bool = False
    _started_monotonic: float = field(default_factory=time.monotonic)

    def estimated_work_fraction(self) -> float:
        pieces = (
            self.units_total
            + self.pit_targets_total
            + self.delta_files_planned
            + self.observation_files_planned
        )
        if pieces <= 0:
            return 0.0
        done = (
            self.units_completed
            + self.pit_targets_consumed
            + self.delta_files_applied
            + self.observation_files_completed
        )
        return min(1.0, max(0.0, done / pieces))

    def snapshot(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "started_at": self.started_at,
            "updated_at": _render_utc(_utc_now()),
            "elapsed_s": round(time.monotonic() - self._started_monotonic, 3),
            "units_total": self.units_total,
            "units_completed": self.units_completed,
            "pit_targets_total": self.pit_targets_total,
            "pit_targets_consumed": self.pit_targets_consumed,
            "delta_files_planned": self.delta_files_planned,
            "delta_files_applied": self.delta_files_applied,
            "observation_files_planned": self.observation_files_planned,
            "observation_files_completed": self.observation_files_completed,
            "member_payload_bytes_read": self.member_payload_bytes_read,
            "observation_payload_bytes_read": self.observation_payload_bytes_read,
            "scratch_current_bytes": self.scratch_current_bytes,
            "scratch_peak_bytes": self.scratch_peak_bytes,
            "estimated_work_fraction": round(self.estimated_work_fraction(), 6),
            "canonical_commit_started": self.canonical_commit_started,
            "canonical_commit_complete": self.canonical_commit_complete,
        }

    def write(self, *, scratch_dir: Path | None = None) -> None:
        measured = Path(scratch_dir) if scratch_dir is not None else self.path.parent
        if measured.is_dir():
            current = directory_bytes(measured)
            self.scratch_current_bytes = current
            if current > self.scratch_peak_bytes:
                self.scratch_peak_bytes = current
        payload = self.snapshot()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)


class CohortBuildLock:
    """Atomic cohort-scoped local build lock. Recover only when holder PID is dead."""

    def __init__(
        self,
        observation_rdp_root: Path,
        cohort_id: str,
        *,
        run_id: str,
        command_identity: str,
    ) -> None:
        self.path = lock_path_for_cohort(observation_rdp_root, cohort_id)
        self.cohort_id = cohort_id
        self.run_id = run_id
        self.command_identity = command_identity
        self._acquired = False

    def _payload(self, *, worker_pid: int | None = None) -> dict[str, Any]:
        return {
            "schema": "smial.bounded-cohort-build-lock",
            "schema_version": "1.0",
            "pid": os.getpid(),
            "worker_pid": worker_pid,
            "host": socket.gethostname(),
            "started_at": _render_utc(_utc_now()),
            "cohort_id": self.cohort_id,
            "run_id": self.run_id,
            "command_identity": self.command_identity,
        }

    def _pid_blocking(self, payload: Mapping[str, Any]) -> bool:
        pids: list[int] = []
        for key in ("pid", "worker_pid"):
            raw = payload.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
                pids.append(raw)
        if not pids:
            return True
        for pid in pids:
            liveness = probe_local_pid(pid)
            if liveness is PidLiveness.ALIVE:
                return True
            if liveness is PidLiveness.UNKNOWN:
                return True
        return False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(self._payload(), sort_keys=True).encode("utf-8")
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            handle = os.open(self.path, flags, 0o644)
        except FileExistsError:
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise BoundedMaterializationError(BUILD_ALREADY_RUNNING) from None
            if not isinstance(existing, Mapping) or self._pid_blocking(existing):
                raise BoundedMaterializationError(BUILD_ALREADY_RUNNING)
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            try:
                handle = os.open(self.path, flags, 0o644)
            except FileExistsError as exc:
                raise BoundedMaterializationError(BUILD_ALREADY_RUNNING) from exc
        try:
            os.write(handle, encoded)
        finally:
            os.close(handle)
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        self._acquired = False


def select_member_batches(
    lifecycle_rows: Sequence[Mapping[str, Any]],
    *,
    window_start: datetime,
    closure_cutoff: datetime | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep window+cutoff MEMBER_BATCH rows plus exactly one predecessor."""

    windowed: list[dict[str, Any]] = []
    before: list[tuple[datetime, int, dict[str, Any]]] = []
    for index, row in enumerate(lifecycle_rows):
        if str(row.get("kind") or "") != "OBSERVATION_MEMBER_BATCH":
            continue
        instant = _parse_lifecycle_instant(row.get("effective_at"))
        if instant is None:
            continue
        payload = row.get("payload")
        if not isinstance(payload, Mapping) or not str(payload.get("member_location") or ""):
            continue
        if closure_cutoff is not None and instant > closure_cutoff:
            continue
        item = dict(row)
        item["_source_index"] = index
        if instant < window_start:
            before.append((instant, index, item))
            continue
        windowed.append(item)
    in_window = windowed
    predecessor: list[dict[str, Any]] = []
    if before:
        before.sort(key=lambda item: (item[0], item[1]))
        predecessor = [before[-1][2]]
    selected = list(in_window) + predecessor
    return selected, predecessor


def select_observation_batches(
    lifecycle_rows: Sequence[Mapping[str, Any]],
    *,
    window_start: datetime,
    closure_cutoff: datetime | None,
    member_dataset_ids: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    before: list[tuple[datetime, int, dict[str, Any]]] = []
    for index, row in enumerate(lifecycle_rows):
        if str(row.get("kind") or "") != "OBSERVATION_BATCH":
            continue
        instant = _parse_lifecycle_instant(row.get("effective_at"))
        if instant is None:
            continue
        if closure_cutoff is not None and instant > closure_cutoff:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        manifest_id = str(payload.get("dataset_manifest_id") or "")
        item = dict(row)
        item["_source_index"] = index
        paired = bool(manifest_id) and manifest_id in member_dataset_ids
        if paired or (window_start <= instant <= (closure_cutoff or instant)):
            selected.append(item)
            continue
        if instant < window_start:
            before.append((instant, index, item))
    if before and not any(
        str((row.get("payload") or {}).get("dataset_manifest_id") or "") in member_dataset_ids
        for row in selected
        if isinstance(row.get("payload"), Mapping)
    ):
        before.sort(key=lambda item: (item[0], item[1]))
        selected.append(before[-1][2])
    return selected


def _completed_observation_binding(
    root: Path,
    payload: Mapping[str, Any],
    manifest_id: str,
) -> tuple[str, str] | None:
    """Open the one completed publication receipt named by the batch identity."""

    content = str(payload.get("dataset_fingerprint") or payload.get("content_sha256") or "")
    if len(content) != 64 or any(char not in "0123456789abcdef" for char in content):
        return None
    from solana_alpha_lab.factory.observation_publication_jobs import completed_job_path

    path = completed_job_path(root, content)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(job, Mapping):
        return None
    if str(job.get("dataset_manifest_id") or "") not in {"", manifest_id}:
        return None
    relative = str(job.get("parquet_rel") or "").replace("\\", "/")
    file_sha = str(job.get("file_sha256") or "")
    if not relative or len(file_sha) != 64:
        return None
    return relative, file_sha


def sidecar_partitions_for_dataset(
    root: Path,
    manifest_id: str,
    *,
    index: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    grouped = index if index is not None else load_observation_partition_index(root)
    return [dict(item) for item in grouped.get(manifest_id) or ()]


def load_observation_partition_index(
    root: Path,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """One metadata pass over partition sidecar JSON; never dataset-*.published."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    partitions_dir = Path(root) / "datasets" / "manifests" / "partitions"
    if not partitions_dir.is_dir():
        return {}
    from solana_alpha_lab.factory.live_cohort_source_bundle import note_counter

    for path in partitions_dir.iterdir():
        if not path.is_file() or path.is_symlink() or path.suffix != ".json":
            continue
        note_counter("observation_partition_index_files_read", 1)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(document, Mapping):
            continue
        dataset_id = str(document.get("dataset_manifest_id") or "")
        if not dataset_id:
            continue
        grouped.setdefault(dataset_id, []).append(dict(document))
    return {key: tuple(items) for key, items in grouped.items()}


def resolve_observation_panel_location(
    observation_rdp_root: Path,
    payload: Mapping[str, Any],
    *,
    partition_index: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> tuple[Path, str]:
    """Resolve observation parquet via dataset_manifest_id. Never glob published markers."""

    root = Path(observation_rdp_root)
    manifest_id = str(payload.get("dataset_manifest_id") or "").strip()
    if not manifest_id:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    manifest_path = root / "datasets" / "manifests" / f"{manifest_id}.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE) from exc
    if not isinstance(document, Mapping):
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    if str(document.get("dataset_manifest_id") or "") not in {"", manifest_id}:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    raw_partitions = list(document.get("partitions") or [])
    if not raw_partitions:
        binding = _completed_observation_binding(root, payload, manifest_id)
        if binding is not None:
            location_rel, file_sha_bound = binding
            raw_partitions = [
                {
                    "logical_location": location_rel,
                    "file_sha256": file_sha_bound,
                    "partition_id": "observation",
                }
            ]
        elif partition_index is not None:
            raw_partitions = sidecar_partitions_for_dataset(
                root, manifest_id, index=partition_index
            )
    partitions = [
        item
        for item in raw_partitions
        if isinstance(item, Mapping)
        and not str(item.get("partition_id") or "").endswith("-members")
        and str(item.get("logical_location") or "")
    ]
    location = ""
    file_sha = ""
    if partitions:
        location = str(partitions[0].get("logical_location") or "")
        file_sha = str(partitions[0].get("file_sha256") or "")
    claimed = str(
        payload.get("observation_location") or payload.get("logical_location") or ""
    )
    if location and claimed and claimed != location:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    if not location:
        location = claimed
    if not location:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    if not file_sha:
        file_sha = str(payload.get("observation_sha256") or payload.get("file_sha256") or "")
    try:
        path = _contained_data_path(root, location)
    except MembersDeltaError as exc:
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE) from exc
    if not path.is_file() or path.is_symlink():
        raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    if len(file_sha) == 64:
        from solana_alpha_lab.factory.live_cohort_source_bundle import (
            sha256_file_streaming,
        )

        if sha256_file_streaming(path) != file_sha:
            raise BoundedMaterializationError(OBSERVATION_LINEAGE_INCOMPLETE)
    return path, location


def inspect_member_target(
    observation_rdp_root: Path, location: str
) -> dict[str, Any]:
    try:
        layout = read_member_layout(observation_rdp_root, location)
    except MembersDeltaError as exc:
        raise BoundedMaterializationError("LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE") from exc
    info: dict[str, Any] = {
        "location": location,
        "kind": str(layout.get("kind") or "") if isinstance(layout, Mapping) else "",
        "unit_rel": "",
        "dataset_manifest_id": "",
        "seq": None,
        "legacy": False,
        "snapshot_plus_delta": False,
    }
    if not isinstance(layout, Mapping):
        info["legacy"] = True
        return info
    kind = str(layout.get("kind") or "")
    info["kind"] = kind
    info["dataset_manifest_id"] = str(layout.get("dataset_manifest_id") or "")
    if kind == LAYOUT_KIND:
        info["snapshot_plus_delta"] = True
        info["unit_rel"] = str(layout.get("unit_rel") or "")
        unit_rel = info["unit_rel"]
        if not unit_rel:
            info["slow_fallback"] = True
            return info
        try:
            unit_path = _contained_data_path(Path(observation_rdp_root), unit_rel)
            unit = json.loads(unit_path.read_text(encoding="utf-8"))
        except MembersDeltaError as exc:
            raise BoundedMaterializationError(
                "LIVE_SOURCE_MEMBER_PROVENANCE_UNREADABLE"
            ) from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            info["slow_fallback"] = True
            return info
        if not isinstance(unit, Mapping):
            info["slow_fallback"] = True
            return info
        target_id = info["dataset_manifest_id"]
        seq = None
        for publication in unit.get("publications") or []:
            if not isinstance(publication, Mapping):
                continue
            if str(publication.get("dataset_manifest_id") or "") != target_id:
                continue
            try:
                seq = int(publication.get("seq"))
            except (TypeError, ValueError):
                seq = None
            break
        info["seq"] = seq
        info["unit"] = unit
        if seq is None:
            info["slow_fallback"] = True
        return info
    if kind == LEGACY_KIND:
        info["legacy"] = True
        return info
    info["slow_fallback"] = True
    return info


def predicted_prefix_work(unit: Mapping[str, Any], max_seq: int) -> tuple[int, int, int]:
    """Return (anchor_loads, delta_applications, predicted_input_bytes)."""

    publications = list(unit.get("publications") or [])
    bytes_total = 0
    deltas = 0
    for publication in publications:
        if not isinstance(publication, Mapping):
            continue
        try:
            seq = int(publication.get("seq"))
        except (TypeError, ValueError):
            continue
        if seq > max_seq:
            continue
        rel = str(publication.get("rel") or "")
        if rel:
            try:
                path = Path(rel)
                # Size is filled by caller with data_root join when available.
            except Exception:
                path = None
            del path
        if seq == 0:
            continue
        deltas += 1
    return (1 if max_seq >= 0 else 0, deltas, bytes_total)


def file_size_for_rel(observation_rdp_root: Path, rel: str) -> int:
    try:
        path = _contained_data_path(Path(observation_rdp_root), rel)
    except MembersDeltaError:
        return 0
    try:
        return int(path.stat().st_size) if path.is_file() else 0
    except OSError:
        return 0


def plan_is_unbounded(plan: Mapping[str, Any]) -> bool:
    if bool(plan.get("slow_fallback_required")):
        return True
    if str(plan.get("work_class") or "") != BOUNDED_WORK_CLASS:
        return True
    if int(plan.get("historical_independent_reconstruct_calls") or 0) != 0:
        return True
    if int(plan.get("global_manifest_markers_scanned") or 0) != 0:
        return True
    if bool(plan.get("full_historical_research_payload_scan")):
        return True
    if bool(plan.get("global_historical_observation_glob")):
        return True
    return False


__all__ = [
    "BOUNDED_WORK_CLASS",
    "BUILD_ALREADY_RUNNING",
    "BoundedMaterializationError",
    "CohortBuildLock",
    "DEFAULT_WALL_BUDGET_S",
    "GLOBAL_PUBLISHED_GLOB",
    "MaterializationProgress",
    "OBSERVATION_LINEAGE_INCOMPLETE",
    "PROGRESS_NAME",
    "UNBOUNDED_PLAN",
    "WALL_BUDGET_EXCEEDED",
    "WallBudget",
    "cohort_scratch_root",
    "directory_bytes",
    "file_size_for_rel",
    "inspect_member_target",
    "load_observation_partition_index",
    "lock_path_for_cohort",
    "plan_is_unbounded",
    "resolve_observation_panel_location",
    "select_member_batches",
    "select_observation_batches",
    "sidecar_partitions_for_dataset",
]
