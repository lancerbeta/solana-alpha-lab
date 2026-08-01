"""Deterministic TASK-21 bounded checkpoint decision and local recovery."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from solana_alpha_lab.task21_forward_recovery import (
    build_source_inventory,
    canonical_json_bytes,
    md5_bytes,
    sha256_bytes,
)


JsonObject = dict[str, Any]
MANIFEST_ENTRY = "TASK21_BOUNDED_PANEL_CHECKPOINT_MANIFEST_v1.json"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644


class Task21CheckpointError(RuntimeError):
    """The bounded checkpoint cannot be evaluated or preserved safely."""


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = ZIP_MODE << 16
    return info


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise Task21CheckpointError(f"unsafe_relative_path:{value}")
    return path


def evaluate_checkpoint(
    *,
    run_plan: JsonObject,
    owner_pulse: JsonObject,
    observed: JsonObject,
) -> JsonObject:
    """Return a fail-closed decision without reading sealed quote outcomes."""

    if run_plan.get("task_id") != "TASK-21":
        raise Task21CheckpointError("run_plan_task_drift")
    if owner_pulse.get("task_id") != "TASK-21":
        raise Task21CheckpointError("owner_pulse_task_drift")
    state = owner_pulse.get("task21_forward_state", {})
    if state.get("real_admissions") != observed.get("real_admissions"):
        raise Task21CheckpointError("real_admission_count_drift")
    if state.get("panels_captured") != observed.get("captured_panels"):
        raise Task21CheckpointError("captured_panel_count_drift")
    if state.get("state") != "H24_CAPTURED_FUTURE_SENTINELS_TRIGGER_ONLY":
        raise Task21CheckpointError("forward_state_drift")

    thresholds = run_plan["information_sufficiency"]
    comparisons = {
        "MINIMUM_COMPLETE_MEMBERS": (
            int(observed["complete_members_upper_bound"]),
            int(thresholds["minimum_complete_members"]),
        ),
        "MINIMUM_COMPLETE_PANELS": (
            int(observed["captured_panels"]),
            int(thresholds["minimum_complete_panels"]),
        ),
        "MINIMUM_DISTINCT_ADMISSION_DATES_UTC": (
            int(observed["distinct_admission_dates_utc_upper_bound"]),
            int(thresholds["minimum_distinct_admission_dates_utc"]),
        ),
        "MINIMUM_DISTINCT_ADMISSION_WEEKS_UTC": (
            int(observed["distinct_admission_weeks_utc_upper_bound"]),
            int(thresholds["minimum_distinct_admission_weeks_utc"]),
        ),
    }
    shortfalls = [
        name
        for name, (actual, required) in comparisons.items()
        if actual < required
    ]
    if not observed.get("observed_market_states_established"):
        shortfalls.append("MULTIPLE_OBSERVED_MARKET_STATES_NOT_ESTABLISHED")

    disposition = "EXTEND_EVIDENCE" if shortfalls else "DATASET_READY_CANDIDATE"
    return {
        "disposition": disposition,
        "checkpoint_class": "BOUNDED_FORWARD_PILOT_NOT_RESEARCH_GRADE",
        "shortfalls": sorted(shortfalls),
        "comparisons": {
            key: {"observed_upper_bound": value[0], "required": value[1]}
            for key, value in sorted(comparisons.items())
        },
        "dataset_ready": False,
        "task22_eligible": False,
        "hypothesis_outcomes_read": False,
        "h72_h168_required": False,
    }


def build_checkpoint_archive_bytes(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
    decision: JsonObject,
) -> tuple[bytes, JsonObject]:
    roots = list(source_roots)
    files = build_source_inventory(
        repository_root=repository_root,
        source_roots=roots,
    )
    manifest = {
        "schema": "smial.task21.bounded-panel-checkpoint-manifest",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": "T21-A7A_BOUNDED_PANEL_CHECKPOINT_AND_EXTEND_EVIDENCE_V1",
        "disposition": decision["disposition"],
        "checkpoint_class": decision["checkpoint_class"],
        "source_roots": roots,
        "file_count": len(files),
        "stored_bytes": sum(int(row["bytes"]) for row in files),
        "source_inventory_sha256": sha256_bytes(canonical_json_bytes(files)),
        "files": files,
        "outcome_blindness": "SEALED",
        "contains_raw_market_data": True,
        "contains_secrets": False,
        "source_mutation_allowed": False,
        "source_deletion_allowed": False,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            _zip_info(MANIFEST_ENTRY),
            canonical_json_bytes(manifest) + b"\n",
        )
        for row in files:
            value = (repository_root / row["path"]).read_bytes()
            if sha256_bytes(value) != row["sha256"]:
                raise Task21CheckpointError(
                    f"source_changed_during_packaging:{row['path']}"
                )
            archive.writestr(_zip_info(str(row["path"])), value)
    return buffer.getvalue(), manifest


def materialize_checkpoint_archive(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
    decision: JsonObject,
    output_directory: Path,
    archive_prefix: str,
) -> JsonObject:
    archive_bytes, manifest = build_checkpoint_archive_bytes(
        repository_root=repository_root,
        source_roots=source_roots,
        decision=decision,
    )
    archive_sha256 = sha256_bytes(archive_bytes)
    filename = f"{archive_prefix}_{archive_sha256}.zip"
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / filename
    created = False
    if path.exists():
        if path.read_bytes() != archive_bytes:
            raise Task21CheckpointError("existing_archive_bytes_drift")
    else:
        with path.open("xb") as handle:
            handle.write(archive_bytes)
        created = True
    after = build_source_inventory(
        repository_root=repository_root,
        source_roots=manifest["source_roots"],
    )
    if after != manifest["files"]:
        raise Task21CheckpointError("source_mutation_detected")
    return {
        "path": path,
        "filename": filename,
        "created": created,
        "bytes": len(archive_bytes),
        "sha256": archive_sha256,
        "md5": md5_bytes(archive_bytes),
        "manifest": manifest,
        "source_mutations": 0,
        "source_deletions": 0,
    }

def verify_and_restore_checkpoint(
    *,
    archive_path: Path,
    expected_archive_sha256: str,
    restore_root: Path,
    source_repository_root: Path | None = None,
) -> JsonObject:
    archive_bytes = archive_path.read_bytes()
    actual_sha256 = sha256_bytes(archive_bytes)
    if actual_sha256 != expected_archive_sha256:
        raise Task21CheckpointError("archive_sha256_drift")
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = archive.namelist()
        if not names or names.count(MANIFEST_ENTRY) != 1:
            raise Task21CheckpointError("checkpoint_manifest_missing_or_duplicate")
        manifest = json.loads(archive.read(MANIFEST_ENTRY).decode("utf-8"))
        files = manifest.get("files")
        if not isinstance(files, list):
            raise Task21CheckpointError("checkpoint_inventory_invalid")
        expected_names = [MANIFEST_ENTRY, *(str(row["path"]) for row in files)]
        if names != expected_names or len(set(names)) != len(names):
            raise Task21CheckpointError("checkpoint_entry_inventory_drift")
        if sha256_bytes(canonical_json_bytes(files)) != manifest.get(
            "source_inventory_sha256"
        ):
            raise Task21CheckpointError("checkpoint_inventory_hash_drift")

        restore_root = restore_root.resolve()
        restore_root.mkdir(parents=True, exist_ok=True)
        restored: list[JsonObject] = []
        for row in files:
            relative = _safe_relative(str(row["path"])).as_posix()
            value = archive.read(relative)
            if len(value) != row["bytes"] or sha256_bytes(value) != row["sha256"]:
                raise Task21CheckpointError(f"checkpoint_entry_drift:{relative}")
            destination = (restore_root / relative).resolve()
            if not destination.is_relative_to(restore_root):
                raise Task21CheckpointError(f"restore_path_escape:{relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.read_bytes() != value:
                    raise Task21CheckpointError(
                        f"existing_restore_bytes_drift:{relative}"
                    )
            else:
                with destination.open("xb") as handle:
                    handle.write(value)
            restored.append(
                {"path": relative, "bytes": len(value), "sha256": sha256_bytes(value)}
            )

    if restored != files:
        raise Task21CheckpointError("restored_inventory_drift")
    source_unchanged = None
    if source_repository_root is not None:
        source_unchanged = build_source_inventory(
            repository_root=source_repository_root,
            source_roots=manifest["source_roots"],
        ) == files
        if not source_unchanged:
            raise Task21CheckpointError("source_mutation_detected")
    return {
        "archive_sha256": actual_sha256,
        "archive_bytes": len(archive_bytes),
        "restored_file_count": len(restored),
        "restored_stored_bytes": sum(int(row["bytes"]) for row in restored),
        "restored_inventory_sha256": sha256_bytes(canonical_json_bytes(restored)),
        "source_unchanged": source_unchanged,
        "source_mutations": 0,
        "source_deletions": 0,
    }
