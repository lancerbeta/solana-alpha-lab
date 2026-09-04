"""Publication-job journal lifecycle for ObservationSchedule.

Routine tick repair reads only ``open/``. Proven terminals become compact
receipts in ``completed/``. Historical full JSON is moved byte-identical into
``legacy_full/`` and is never deleted by this module.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc

JOBS_RELATIVE = "datasets/publication_jobs"
OPEN_DIRNAME = "open"
COMPLETED_DIRNAME = "completed"
LEGACY_FULL_DIRNAME = "legacy_full"
STAGE_MARKER = "MARKER"
STAGE_COMPLETE = "COMPLETE"
CLASS_OPEN = "OPEN"
CLASS_PROVEN_COMPLETED = "PROVEN_COMPLETED"
CLASS_AMBIGUOUS = "AMBIGUOUS"
HOT_PATH_FORBIDDEN = "PUBLICATION_HOT_PATH_READ_FORBIDDEN"
AMBIGUOUS_BLOCKS_APPLY = "PUBLICATION_JOB_MIGRATION_AMBIGUOUS"
OPEN_JOB_CONFLICT = "OPEN_JOB_CONFLICT"
COMPLETED_RECEIPT_CONFLICT = "COMPLETED_RECEIPT_CONFLICT"
LEGACY_FULL_BYTE_MISMATCH = "LEGACY_FULL_BYTE_MISMATCH"
COMPACT_RECEIPT_UNCONSTRUCTABLE = "COMPACT_RECEIPT_UNCONSTRUCTABLE"
CONTENT_SHA256_INVALID = "CONTENT_SHA256_INVALID"
COLLECTOR_NOT_PAUSED = "COLLECTOR_NOT_PAUSED"
COLLECTOR_STORE_MISSING = "COLLECTOR_STORE_MISSING"
CONTENT_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UNAVAILABLE_FILESYSTEM_TRUTH = "UNAVAILABLE_FILESYSTEM_TRUTH"
UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET = "UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET"
COMPACT_IDENTITY_KEYS = (
    "content_sha256",
    "schedule_sha256",
    "activation_id",
    "utc_day",
    "dataset_version",
    "dataset_manifest_id",
    "parquet_rel",
    "member_rel",
    "file_sha256",
    "member_sha256",
)
APPLY_ACTIVE_STATES = frozenset({"ACTIVE", "DRAINING"})
COMPACT_FORBIDDEN_KEYS = frozenset(
    {"observations", "normalized_observations", "members"}
)
COMPACT_REQUIRED_KEYS = (
    "content_sha256",
    "schedule_sha256",
    "activation_id",
    "stage",
    "utc_day",
    "dataset_version",
    "dataset_manifest_id",
    "created_at",
    "completed_at",
    "parquet_rel",
    "member_rel",
    "file_sha256",
    "member_sha256",
    "observation_count",
    "member_count",
    "dataset_fingerprint",
)
DISK_WARNING_EARLY_PCT = 70


def collector_blocks_apply(activations: Sequence[Mapping[str, Any]]) -> bool:
    """APPLY is allowed only when no live ACTIVE/DRAINING collector remains."""

    return any(str(item.get("state") or "") in APPLY_ACTIVE_STATES for item in activations)


class PublicationJobError(ValueError):
    """Typed publication-job journal failure."""


def jobs_root(data_root: Path) -> Path:
    return Path(data_root) / JOBS_RELATIVE


def open_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / OPEN_DIRNAME


def completed_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / COMPLETED_DIRNAME


def legacy_full_dir(data_root: Path) -> Path:
    return jobs_root(data_root) / LEGACY_FULL_DIRNAME


def flat_legacy_path(data_root: Path, content: str) -> Path:
    return jobs_root(data_root) / f"{content}.json"


def open_job_path(data_root: Path, content: str) -> Path:
    return open_dir(data_root) / f"{content}.json"


def completed_job_path(data_root: Path, content: str) -> Path:
    return completed_dir(data_root) / f"{content}.json"


def legacy_full_path(data_root: Path, content: str) -> Path:
    return legacy_full_dir(data_root) / f"{content}.json"


def assert_routine_hot_path(path: Path) -> None:
    """Routine repair/has-open may only read ``open/`` job files."""

    parts = Path(path).parts
    if COMPLETED_DIRNAME in parts or LEGACY_FULL_DIRNAME in parts:
        raise PublicationJobError(HOT_PATH_FORBIDDEN)


def _dir_file_stats(directory: Path) -> tuple[int, int]:
    if not directory.is_dir():
        return 0, 0
    count = 0
    total = 0
    for child in directory.glob("*.json"):
        if not child.is_file() or child.is_symlink():
            continue
        count += 1
        try:
            total += int(child.stat().st_size)
        except OSError:
            continue
    return count, total


def _flat_legacy_stats(root: Path) -> tuple[int, int]:
    if not root.is_dir():
        return 0, 0
    count = 0
    total = 0
    for child in root.glob("*.json"):
        if not child.is_file() or child.is_symlink():
            continue
        count += 1
        try:
            total += int(child.stat().st_size)
        except OSError:
            continue
    return count, total


def journal_stats(data_root: Path) -> dict[str, int]:
    """Metadata/stat path: counts and bytes, no JSON body reads."""

    root = jobs_root(data_root)
    open_count, open_bytes = _dir_file_stats(open_dir(data_root))
    completed_count, completed_bytes = _dir_file_stats(completed_dir(data_root))
    legacy_count, legacy_bytes = _dir_file_stats(legacy_full_dir(data_root))
    flat_count, flat_bytes = _flat_legacy_stats(root)
    return {
        "publication_jobs_open_count": open_count,
        "publication_jobs_open_bytes": open_bytes,
        "publication_jobs_completed_count": completed_count,
        "publication_jobs_completed_bytes": completed_bytes,
        "publication_jobs_legacy_full_count": legacy_count,
        "publication_jobs_legacy_full_bytes": legacy_bytes,
        "publication_jobs_unmigrated_flat_count": flat_count,
        "publication_jobs_unmigrated_flat_bytes": flat_bytes,
    }


def rdp_bytes_excluding_publication_jobs(data_root: Path) -> int:
    total = 0
    root = Path(data_root)
    jobs = jobs_root(data_root)
    if not root.exists():
        return 0
    for child in root.rglob("*"):
        if not child.is_file() or child.is_symlink():
            continue
        try:
            child.relative_to(jobs)
        except ValueError:
            try:
                total += int(child.stat().st_size)
            except OSError:
                continue
    return total


def is_compact_receipt(job: Mapping[str, Any]) -> bool:
    if str(job.get("stage") or "") != STAGE_COMPLETE:
        return False
    if any(key in job for key in COMPACT_FORBIDDEN_KEYS):
        return False
    return all(key in job for key in COMPACT_REQUIRED_KEYS)


def compact_receipt_from_job(
    job: Mapping[str, Any],
    *,
    completed_at: datetime,
    dataset_fingerprint: str | None = None,
) -> dict[str, Any]:
    try:
        content = str(job["content_sha256"])
        receipt = {
            "content_sha256": content,
            "schedule_sha256": str(job["schedule_sha256"]),
            "activation_id": str(job["activation_id"]),
            "stage": STAGE_COMPLETE,
            "utc_day": str(job["utc_day"]),
            "dataset_version": str(job["dataset_version"]),
            "dataset_manifest_id": str(job["dataset_manifest_id"]),
            "created_at": str(job["created_at"]),
            "completed_at": render_utc(completed_at.astimezone(UTC)),
            "parquet_rel": str(job["parquet_rel"]),
            "member_rel": str(job["member_rel"]),
            "file_sha256": str(job["file_sha256"]),
            "member_sha256": str(job["member_sha256"]),
            "observation_count": int(job.get("observation_count") or 0),
            "member_count": int(job.get("member_count") or 0),
            "dataset_fingerprint": str(
                dataset_fingerprint or job.get("dataset_fingerprint") or content
            ),
        }
    except (KeyError, TypeError, ValueError):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE) from None
    if any(not str(receipt.get(key) or "") for key in COMPACT_IDENTITY_KEYS):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    if any(key in receipt for key in COMPACT_FORBIDDEN_KEYS):
        raise PublicationJobError("COMPACT_RECEIPT_CONTAINS_PAYLOAD")
    if not is_compact_receipt(receipt):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    return receipt


def _same_publication_identity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(str(left.get(key) or "") == str(right.get(key) or "") for key in COMPACT_IDENTITY_KEYS)


def _planned_compact_receipt(payload: Mapping[str, Any], content: str) -> dict[str, Any]:
    created = payload.get("created_at")
    try:
        completed_at = (
            parse_utc(str(payload.get("completed_at") or created))
            if (payload.get("completed_at") or created)
            else datetime.now(UTC)
        )
    except (TypeError, ValueError):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE) from None
    receipt = compact_receipt_from_job(
        payload,
        completed_at=completed_at,
        dataset_fingerprint=str(payload.get("dataset_fingerprint") or content),
    )
    if payload.get("completed_at"):
        receipt["completed_at"] = str(payload["completed_at"])
    if not is_compact_receipt(receipt):
        raise PublicationJobError(COMPACT_RECEIPT_UNCONSTRUCTABLE)
    return receipt


def _content_sha256(payload: Mapping[str, Any]) -> str:
    content = str(payload.get("content_sha256") or "")
    if CONTENT_SHA256_RE.fullmatch(content) is None:
        raise PublicationJobError(CONTENT_SHA256_INVALID)
    return content


def publication_artifacts_proven(
    data_root: Path,
    job: Mapping[str, Any],
) -> bool:
    """Durable scientific effects required before a job may leave ``open/``."""

    manifest_id = str(job.get("dataset_manifest_id") or "")
    if len(str(job.get("content_sha256") or "")) != 64 or not manifest_id:
        return False
    published = (
        Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.published"
    )
    manifest = Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.json"
    if not published.is_file() or not manifest.is_file():
        return False
    parquet_rel = str(job.get("parquet_rel") or "")
    member_rel = str(job.get("member_rel") or "")
    if not parquet_rel or not member_rel:
        return False
    parquet = Path(data_root) / parquet_rel
    member = Path(data_root) / member_rel
    return parquet.is_file() and member.is_file()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_job_by_content(data_root: Path, content: str) -> dict[str, Any] | None:
    """Exact content_sha256 lookup: completed, then open, then unmigrated flat."""

    for path in (
        completed_job_path(data_root, content),
        open_job_path(data_root, content),
        flat_legacy_path(data_root, content),
    ):
        if not path.is_file():
            continue
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise PublicationJobError("PUBLICATION_JOB_INVALID")
        return loaded
    return None


def save_open_job(data_root: Path, content: str, payload: Mapping[str, Any]) -> None:
    if str(payload.get("stage") or "") == STAGE_COMPLETE:
        raise PublicationJobError("COMPACT_RECEIPT_IN_OPEN")
    _atomic_write_json(open_job_path(data_root, content), payload)


def complete_publication_job(
    data_root: Path,
    job: Mapping[str, Any],
    *,
    completed_at: datetime,
    dataset_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Write compact receipt and remove the full open/flat job. Never rewrite RDP."""

    content = str(job["content_sha256"])
    destination = completed_job_path(data_root, content)
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(existing, dict) or not is_compact_receipt(existing):
            raise PublicationJobError("COMPLETED_RECEIPT_INVALID")
        if str(existing.get("dataset_manifest_id")) != str(job.get("dataset_manifest_id")):
            raise PublicationJobError("CONTENT_IDENTITY_INVALID")
        for leftover in (
            open_job_path(data_root, content),
            flat_legacy_path(data_root, content),
        ):
            leftover.unlink(missing_ok=True)
        return existing
    if not publication_artifacts_proven(data_root, job):
        raise PublicationJobError("PUBLICATION_NOT_PROVEN")
    receipt = compact_receipt_from_job(
        job,
        completed_at=completed_at,
        dataset_fingerprint=dataset_fingerprint,
    )
    _atomic_write_json(destination, receipt)
    for leftover in (
        open_job_path(data_root, content),
        flat_legacy_path(data_root, content),
    ):
        leftover.unlink(missing_ok=True)
    return receipt


def iter_open_job_paths(data_root: Path) -> list[Path]:
    directory = open_dir(data_root)
    if not directory.is_dir():
        return []
    paths = []
    for path in sorted(directory.glob("*.json")):
        if path.is_file() and not path.is_symlink():
            assert_routine_hot_path(path)
            paths.append(path)
    return paths


def classify_legacy_payload(
    payload: object,
    *,
    data_root: Path,
) -> str:
    if not isinstance(payload, dict):
        return CLASS_AMBIGUOUS
    content = str(payload.get("content_sha256") or "")
    if len(content) != 64:
        return CLASS_AMBIGUOUS
    if payload.get("activation_id") is None:
        return CLASS_AMBIGUOUS
    if not payload.get("schedule_sha256"):
        return CLASS_AMBIGUOUS
    if is_compact_receipt(payload) and publication_artifacts_proven(data_root, payload):
        return CLASS_PROVEN_COMPLETED
    if publication_artifacts_proven(data_root, payload):
        return CLASS_PROVEN_COMPLETED
    stage = str(payload.get("stage") or "")
    if stage in {STAGE_MARKER, STAGE_COMPLETE}:
        return CLASS_AMBIGUOUS
    members = payload.get("members")
    if not isinstance(members, list) or not members:
        return CLASS_AMBIGUOUS
    return CLASS_OPEN


def _iter_unmigrated_paths(data_root: Path) -> list[Path]:
    root = jobs_root(data_root)
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.glob("*.json")
        if path.is_file() and not path.is_symlink()
    )


def dry_run_migration(data_root: Path) -> dict[str, Any]:
    stats = journal_stats(data_root)
    classified = {
        CLASS_OPEN: 0,
        CLASS_PROVEN_COMPLETED: 0,
        CLASS_AMBIGUOUS: 0,
    }
    ambiguous_names: list[str] = []
    open_bytes = 0
    for path in _iter_unmigrated_paths(data_root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            classified[CLASS_AMBIGUOUS] += 1
            ambiguous_names.append(path.name)
            continue
        label = classify_legacy_payload(payload, data_root=data_root)
        classified[label] += 1
        if label == CLASS_AMBIGUOUS:
            ambiguous_names.append(path.name)
        elif label == CLASS_OPEN:
            open_bytes += int(path.stat().st_size)
    stats.update(
        {
            "old_unmigrated_count": sum(classified.values()),
            "classified_open": classified[CLASS_OPEN],
            "classified_proven_completed": classified[CLASS_PROVEN_COMPLETED],
            "classified_ambiguous": classified[CLASS_AMBIGUOUS],
            "projected_hot_path_bytes": stats["publication_jobs_open_bytes"] + open_bytes,
            "ambiguous_names": ambiguous_names,
            "provider_calls": 0,
            "scientific_writes": 0,
        }
    )
    return stats


def plan_migration(data_root: Path) -> list[dict[str, Any]]:
    """Inspect every unmigrated source. Fail before the caller mutates anything."""

    plan: list[dict[str, Any]] = []
    for path in _iter_unmigrated_paths(data_root):
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
        if not isinstance(payload, dict):
            raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
        content = _content_sha256(payload)
        label = classify_legacy_payload(payload, data_root=data_root)
        if label == CLASS_AMBIGUOUS:
            raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
        if label == CLASS_OPEN:
            destination = open_job_path(data_root, content)
            if destination.is_file() and destination.read_bytes() != raw:
                raise PublicationJobError(OPEN_JOB_CONFLICT)
            plan.append(
                {
                    "source": path,
                    "raw": raw,
                    "content": content,
                    "label": CLASS_OPEN,
                    "receipt": None,
                }
            )
            continue
        if label != CLASS_PROVEN_COMPLETED:
            raise PublicationJobError(AMBIGUOUS_BLOCKS_APPLY)
        receipt = _planned_compact_receipt(payload, content)
        completed = completed_job_path(data_root, content)
        if completed.is_file():
            try:
                existing = json.loads(completed.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            if not isinstance(existing, dict) or not is_compact_receipt(existing):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            if not _same_publication_identity(existing, receipt):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
        legacy = legacy_full_path(data_root, content)
        if legacy.is_file() and legacy.read_bytes() != raw:
            raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
        plan.append(
            {
                "source": path,
                "raw": raw,
                "content": content,
                "label": CLASS_PROVEN_COMPLETED,
                "receipt": receipt,
            }
        )
    return plan


def apply_migration(data_root: Path) -> dict[str, Any]:
    """Move unmigrated flat jobs after a complete preflight. No RDP rewrite."""

    plan = plan_migration(data_root)
    report = dry_run_migration(data_root)
    moved_open = 0
    moved_completed = 0
    for item in plan:
        path = item["source"]
        raw = item["raw"]
        content = item["content"]
        if item["label"] == CLASS_OPEN:
            destination = open_job_path(data_root, content)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_file():
                if destination.read_bytes() != raw:
                    raise PublicationJobError(OPEN_JOB_CONFLICT)
                path.unlink()
            else:
                os.replace(path, destination)
            moved_open += 1
            continue
        receipt = item["receipt"]
        completed = completed_job_path(data_root, content)
        if completed.is_file():
            existing = json.loads(completed.read_text(encoding="utf-8"))
            if not isinstance(existing, dict) or not is_compact_receipt(existing):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
            if not _same_publication_identity(existing, receipt):
                raise PublicationJobError(COMPLETED_RECEIPT_CONFLICT)
        else:
            _atomic_write_json(completed, receipt)
        legacy = legacy_full_path(data_root, content)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        if legacy.is_file():
            if legacy.read_bytes() != raw:
                raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
            path.unlink(missing_ok=True)
        else:
            os.replace(path, legacy)
            if legacy.read_bytes() != raw:
                raise PublicationJobError(LEGACY_FULL_BYTE_MISMATCH)
        moved_completed += 1
    report["moved_open"] = moved_open
    report["moved_completed"] = moved_completed
    report["legacy_full_deleted"] = False
    report.update(journal_stats(data_root))
    return report


def _measured_int(value: Any, *, allow_zero: bool) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if allow_zero:
        return value if value >= 0 else None
    return value if value > 0 else None


def project_7d_disk_used(
    *,
    disk_total_bytes: int | None,
    disk_used_bytes: int | None,
    sqlite_bytes: int | None,
    rdp_science_bytes: int | None,
    job_open_bytes: int,
    job_completed_bytes: int,
    job_legacy_bytes: int,
    elapsed_campaign_days: float | None,
    declared_raw_bytes_per_day: int | None,
    history_data_growth_24h_bytes: int | None,
) -> dict[str, Any]:
    """Conservative 7-day used-pct. UNKNOWN inputs cannot manufacture a PASS."""

    del elapsed_campaign_days
    sqlite = _measured_int(sqlite_bytes, allow_zero=True)
    science = _measured_int(rdp_science_bytes, allow_zero=True)
    live = (
        sqlite + science + int(job_open_bytes) + int(job_completed_bytes)
        if sqlite is not None and science is not None
        else None
    )
    total = _measured_int(disk_total_bytes, allow_zero=False)
    used = _measured_int(disk_used_bytes, allow_zero=True)
    daily_history = _measured_int(history_data_growth_24h_bytes, allow_zero=False)
    daily_declared = _measured_int(declared_raw_bytes_per_day, allow_zero=False)
    if daily_history is not None:
        daily = daily_history
        basis = "STORAGE_HISTORY_24H"
    elif daily_declared is not None:
        daily = daily_declared
        basis = "DECLARED_RAW_BYTES_PER_DAY"
    else:
        return {
            "projection_basis": UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET,
            "live_bytes": live,
            "legacy_full_bytes": job_legacy_bytes,
            "projected_7d_additional_bytes": None,
            "projected_7d_disk_used_bytes": None,
            "projected_7d_disk_used_pct": None,
            "projected_7d_disk_used_pass_70": False,
            "early_warning_pct": DISK_WARNING_EARLY_PCT,
        }
    if total is None or used is None:
        return {
            "projection_basis": UNAVAILABLE_FILESYSTEM_TRUTH,
            "live_bytes": live,
            "legacy_full_bytes": job_legacy_bytes,
            "projected_7d_additional_bytes": int(daily) * 7 * 2,
            "projected_7d_disk_used_bytes": None,
            "projected_7d_disk_used_pct": None,
            "projected_7d_disk_used_pass_70": False,
            "early_warning_pct": DISK_WARNING_EARLY_PCT,
        }
    extra_with_backup = int(daily) * 7 * 2
    projected_used = used + extra_with_backup
    projected_pct = 100.0 * projected_used / total
    return {
        "projection_basis": basis,
        "live_bytes": live,
        "legacy_full_bytes": job_legacy_bytes,
        "projected_7d_additional_bytes": extra_with_backup,
        "projected_7d_disk_used_bytes": projected_used,
        "projected_7d_disk_used_pct": round(projected_pct, 4),
        "projected_7d_disk_used_pass_70": projected_pct < DISK_WARNING_EARLY_PCT,
        "early_warning_pct": DISK_WARNING_EARLY_PCT,
    }


__all__ = [
    "AMBIGUOUS_BLOCKS_APPLY",
    "APPLY_ACTIVE_STATES",
    "CLASS_AMBIGUOUS",
    "CLASS_OPEN",
    "CLASS_PROVEN_COMPLETED",
    "COLLECTOR_NOT_PAUSED",
    "COLLECTOR_STORE_MISSING",
    "COMPACT_FORBIDDEN_KEYS",
    "COMPACT_RECEIPT_UNCONSTRUCTABLE",
    "COMPLETED_RECEIPT_CONFLICT",
    "CONTENT_SHA256_INVALID",
    "HOT_PATH_FORBIDDEN",
    "LEGACY_FULL_BYTE_MISMATCH",
    "OPEN_JOB_CONFLICT",
    "PublicationJobError",
    "STAGE_COMPLETE",
    "STAGE_MARKER",
    "UNAVAILABLE_FILESYSTEM_TRUTH",
    "UNAVAILABLE_NO_HISTORY_OR_DECLARED_BUDGET",
    "apply_migration",
    "assert_routine_hot_path",
    "collector_blocks_apply",
    "compact_receipt_from_job",
    "complete_publication_job",
    "completed_dir",
    "dry_run_migration",
    "is_compact_receipt",
    "iter_open_job_paths",
    "journal_stats",
    "legacy_full_dir",
    "load_job_by_content",
    "open_dir",
    "plan_migration",
    "project_7d_disk_used",
    "publication_artifacts_proven",
    "rdp_bytes_excluding_publication_jobs",
    "save_open_job",
]
