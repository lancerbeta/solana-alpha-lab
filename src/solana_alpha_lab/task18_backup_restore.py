"""Deterministic content-addressed backup and restore helpers for TASK-18."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from solana_alpha_lab.task18_data_quality import audit_narrow_data_quality

JsonObject = dict[str, Any]
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644
MANIFEST_ENTRY = "BACKUP_MANIFEST.json"


class Task18BackupError(RuntimeError):
    """Backup or restore evidence does not match the frozen repair contract."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _md5_bytes(value: bytes) -> str:
    return hashlib.md5(value, usedforsecurity=False).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task18BackupError(f"json_root_invalid:{path.name}")
    return value


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = ZIP_MODE << 16
    return info


def _verify_repair_contract(
    repository_root: Path,
    repair_contract_path: Path,
) -> tuple[JsonObject, JsonObject]:
    repair = _load_json(repair_contract_path)
    if repair.get("status") != "FROZEN_REPAIR_CONTRACT":
        raise Task18BackupError("repair_contract_status_drift")
    frozen = repair["frozen_inputs"]
    quality_contract_path = repository_root / frozen["quality_contract_path"]
    quality_audit_path = repository_root / frozen["quality_audit_path"]
    if _sha256(quality_contract_path) != frozen["quality_contract_sha256"]:
        raise Task18BackupError("quality_contract_hash_drift")
    if _sha256(quality_audit_path) != frozen["quality_audit_sha256"]:
        raise Task18BackupError("quality_audit_hash_drift")
    quality_contract = _load_json(quality_contract_path)
    quality_audit = _load_json(quality_audit_path)
    if quality_audit.get("verdict") != frozen["quality_audit_verdict"]:
        raise Task18BackupError("quality_audit_verdict_drift")
    return repair, quality_contract


def build_backup_manifest(
    *,
    repository_root: Path,
    repair_contract_path: Path,
) -> JsonObject:
    """Resolve and verify the exact frozen raw inventory."""

    repair, quality_contract = _verify_repair_contract(
        repository_root,
        repair_contract_path,
    )
    inventory = quality_contract["raw_inventory"]
    files: list[JsonObject] = []
    source_hashes_before: dict[str, str] = {}
    for row in inventory["files"]:
        relative = row["path"]
        path = (repository_root / relative).resolve()
        if not path.is_relative_to(repository_root.resolve()):
            raise Task18BackupError(f"path_outside_repository:{relative}")
        if not path.is_file():
            raise Task18BackupError(f"source_missing:{relative}")
        value = path.read_bytes()
        actual_sha256 = _sha256_bytes(value)
        if actual_sha256 != row["sha256"]:
            raise Task18BackupError(f"source_hash_drift:{relative}")
        if len(value) != row["bytes"]:
            raise Task18BackupError(f"source_size_drift:{relative}")
        if row["kind"] == "RAW_EVENTS_JSONL":
            actual_rows = len(value.decode("utf-8").splitlines())
            if actual_rows != row["rows"]:
                raise Task18BackupError(f"source_row_drift:{relative}")
        source_hashes_before[relative] = actual_sha256
        files.append(
            {
                "path": relative,
                "bytes": len(value),
                "sha256": actual_sha256,
            }
        )

    if len(files) != repair["frozen_inputs"]["raw_file_count"]:
        raise Task18BackupError("source_file_count_drift")
    if sum(row["bytes"] for row in files) != repair["frozen_inputs"][
        "raw_stored_bytes"
    ]:
        raise Task18BackupError("source_stored_bytes_drift")
    return {
        "schema": repair["archive"]["schema"],
        "schema_version": repair["archive"]["schema_version"],
        "task": "TASK-18",
        "atom": "T18-A3R_CONTENT_ADDRESSED_BACKUP_RESTORE_PROOF_V1",
        "as_of": repair["as_of"],
        "quality_contract_sha256": repair["frozen_inputs"][
            "quality_contract_sha256"
        ],
        "quality_audit_sha256": repair["frozen_inputs"][
            "quality_audit_sha256"
        ],
        "file_count": len(files),
        "stored_bytes": sum(row["bytes"] for row in files),
        "files": sorted(files, key=lambda row: row["path"]),
        "contains_raw_data": True,
        "contains_secrets": False,
        "source_mutation_allowed": False,
        "source_hashes_before": dict(sorted(source_hashes_before.items())),
    }


def build_archive_bytes(
    *,
    repository_root: Path,
    repair_contract_path: Path,
) -> tuple[bytes, JsonObject]:
    """Build byte-identical ZIP_STORED output from frozen inputs."""

    manifest = build_backup_manifest(
        repository_root=repository_root,
        repair_contract_path=repair_contract_path,
    )
    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(_zip_info(MANIFEST_ENTRY), manifest_bytes)
        for row in manifest["files"]:
            value = (repository_root / row["path"]).read_bytes()
            archive.writestr(_zip_info(row["path"]), value)
    return buffer.getvalue(), manifest


def materialize_archive(
    *,
    repository_root: Path,
    repair_contract_path: Path,
    output_directory: Path,
) -> JsonObject:
    """Write one content-addressed archive, never replacing existing bytes."""

    archive_bytes, manifest = build_archive_bytes(
        repository_root=repository_root,
        repair_contract_path=repair_contract_path,
    )
    archive_sha256 = _sha256_bytes(archive_bytes)
    archive_md5 = _md5_bytes(archive_bytes)
    filename = f"TASK18_RAW_BACKUP_v1_{archive_sha256}.zip"
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / filename
    if path.exists():
        if path.read_bytes() != archive_bytes:
            raise Task18BackupError("existing_archive_bytes_drift")
    else:
        with path.open("xb") as handle:
            handle.write(archive_bytes)
    return {
        "path": path,
        "filename": filename,
        "bytes": len(archive_bytes),
        "sha256": archive_sha256,
        "md5": archive_md5,
        "manifest": manifest,
    }


def verify_and_restore_archive(
    *,
    archive_path: Path,
    source_repository_root: Path,
    repair_contract_path: Path,
    restore_root: Path,
) -> JsonObject:
    """Restore exact bytes and rerun the A3 auditor in an isolated root."""

    repair, quality_contract = _verify_repair_contract(
        source_repository_root,
        repair_contract_path,
    )
    archive_bytes = archive_path.read_bytes()
    expected_entries = {
        MANIFEST_ENTRY,
        *(row["path"] for row in quality_contract["raw_inventory"]["files"]),
    }
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = archive.namelist()
        if set(names) != expected_entries or len(names) != len(expected_entries):
            raise Task18BackupError("archive_entry_inventory_drift")
        manifest = json.loads(archive.read(MANIFEST_ENTRY).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise Task18BackupError("archive_manifest_invalid")
        if manifest.get("file_count") != repair["restore"][
            "expected_file_count"
        ]:
            raise Task18BackupError("archive_manifest_file_count_drift")
        restored_files: list[JsonObject] = []
        for row in manifest["files"]:
            relative = row["path"]
            if relative.startswith("/") or ".." in Path(relative).parts:
                raise Task18BackupError(f"unsafe_archive_path:{relative}")
            value = archive.read(relative)
            if _sha256_bytes(value) != row["sha256"]:
                raise Task18BackupError(f"archive_entry_hash_drift:{relative}")
            if len(value) != row["bytes"]:
                raise Task18BackupError(f"archive_entry_size_drift:{relative}")
            destination = (restore_root / relative).resolve()
            if not destination.is_relative_to(restore_root.resolve()):
                raise Task18BackupError(f"restore_path_escape:{relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.read_bytes() != value:
                    raise Task18BackupError(
                        f"existing_restore_bytes_drift:{relative}"
                    )
            else:
                with destination.open("xb") as handle:
                    handle.write(value)
            restored_files.append(
                {
                    "path": relative,
                    "bytes": len(value),
                    "sha256": _sha256_bytes(value),
                }
            )

    for tracked in quality_contract["tracked_inputs"]:
        source = source_repository_root / tracked["path"]
        destination = restore_root / tracked["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise Task18BackupError(
                    f"existing_tracked_restore_drift:{tracked['path']}"
                )
        else:
            shutil.copyfile(source, destination)

    quality_contract_path = (
        source_repository_root
        / repair["frozen_inputs"]["quality_contract_path"]
    )
    restored_audit = audit_narrow_data_quality(
        repository_root=restore_root,
        contract_path=quality_contract_path,
    )
    if restored_audit["verdict"] != repair["restore"][
        "required_a3_verdict"
    ]:
        raise Task18BackupError("restored_audit_verdict_drift")
    if restored_audit["quality_metrics"]["hard_failure_count"] != repair[
        "restore"
    ]["required_hard_failure_count"]:
        raise Task18BackupError("restored_hard_failure_count_drift")

    source_hashes_after = {
        row["path"]: _sha256(source_repository_root / row["path"])
        for row in quality_contract["raw_inventory"]["files"]
    }
    if source_hashes_after != manifest["source_hashes_before"]:
        raise Task18BackupError("source_mutation_detected")
    return {
        "archive_sha256": _sha256_bytes(archive_bytes),
        "archive_md5": _md5_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "restored_file_count": len(restored_files),
        "restored_stored_bytes": sum(
            row["bytes"] for row in restored_files
        ),
        "restored_files": sorted(
            restored_files,
            key=lambda row: row["path"],
        ),
        "restored_audit_verdict": restored_audit["verdict"],
        "restored_hard_failure_count": restored_audit["quality_metrics"][
            "hard_failure_count"
        ],
        "source_mutations": 0,
        "source_deletions": 0,
    }
