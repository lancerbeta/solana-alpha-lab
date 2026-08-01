"""Deterministic create-only backup and isolated restore for TASK-21 evidence."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


JsonObject = dict[str, Any]
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644
MANIFEST_ENTRY = "TASK21_FORWARD_RECOVERY_MANIFEST_v1.json"
ARCHIVE_PREFIX = "TASK21_H0_H1_H6_FORWARD_BACKUP_v1"


class Task21ForwardRecoveryError(RuntimeError):
    """The frozen TASK-21 recovery evidence cannot be proven safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def md5_bytes(value: bytes) -> str:
    return hashlib.md5(value, usedforsecurity=False).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = ZIP_MODE << 16
    return info


def _safe_relative(path: str) -> PurePosixPath:
    logical = PurePosixPath(path)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise Task21ForwardRecoveryError(f"unsafe_logical_path:{path}")
    return logical


def build_source_inventory(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
) -> list[JsonObject]:
    """Read the exact create-only evidence roots into a stable inventory."""

    repository_root = repository_root.resolve()
    files: list[JsonObject] = []
    seen: set[str] = set()
    for raw_root in source_roots:
        relative_root = _safe_relative(raw_root).as_posix()
        root = (repository_root / relative_root).resolve()
        if not root.is_relative_to(repository_root):
            raise Task21ForwardRecoveryError(
                f"source_root_outside_repository:{relative_root}"
            )
        if not root.is_dir():
            raise Task21ForwardRecoveryError(
                f"source_root_missing:{relative_root}"
            )
        root_files = sorted(path for path in root.rglob("*") if path.is_file())
        if not root_files:
            raise Task21ForwardRecoveryError(
                f"source_root_empty:{relative_root}"
            )
        for path in root_files:
            relative = path.relative_to(repository_root).as_posix()
            if relative in seen:
                raise Task21ForwardRecoveryError(
                    f"duplicate_source_path:{relative}"
                )
            seen.add(relative)
            value = path.read_bytes()
            files.append(
                {
                    "path": relative,
                    "bytes": len(value),
                    "sha256": sha256_bytes(value),
                }
            )
    return sorted(files, key=lambda row: str(row["path"]))


def build_backup_manifest(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
) -> JsonObject:
    roots = list(source_roots)
    files = build_source_inventory(
        repository_root=repository_root,
        source_roots=roots,
    )
    inventory_sha256 = sha256_bytes(canonical_json_bytes(files))
    return {
        "schema": "smial.task21.forward-recovery-manifest",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": "T21-A6S_PRE_H24_RECOVERY_REFRESH_AND_CAPTURE_PREP_V1",
        "source_roots": roots,
        "file_count": len(files),
        "stored_bytes": sum(int(row["bytes"]) for row in files),
        "source_inventory_sha256": inventory_sha256,
        "files": files,
        "contains_raw_market_data": True,
        "contains_secrets": False,
        "source_mutation_allowed": False,
        "source_deletion_allowed": False,
        "provider_api_rpc_wss_calls": 0,
        "wallet_signer_transaction_actions": 0,
    }


def build_archive_bytes(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
) -> tuple[bytes, JsonObject]:
    manifest = build_backup_manifest(
        repository_root=repository_root,
        source_roots=source_roots,
    )
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(_zip_info(MANIFEST_ENTRY), manifest_bytes)
        for row in manifest["files"]:
            value = (repository_root / row["path"]).read_bytes()
            if sha256_bytes(value) != row["sha256"]:
                raise Task21ForwardRecoveryError(
                    f"source_changed_during_packaging:{row['path']}"
                )
            archive.writestr(_zip_info(str(row["path"])), value)
    return buffer.getvalue(), manifest


def materialize_archive(
    *,
    repository_root: Path,
    source_roots: Iterable[str],
    output_directory: Path,
) -> JsonObject:
    """Create one content-addressed ZIP without replacing existing bytes."""

    archive_bytes, manifest = build_archive_bytes(
        repository_root=repository_root,
        source_roots=source_roots,
    )
    archive_sha256 = sha256_bytes(archive_bytes)
    filename = f"{ARCHIVE_PREFIX}_{archive_sha256}.zip"
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / filename
    created = False
    if path.exists():
        if path.read_bytes() != archive_bytes:
            raise Task21ForwardRecoveryError("existing_archive_bytes_drift")
    else:
        with path.open("xb") as handle:
            handle.write(archive_bytes)
        created = True
    after = build_source_inventory(
        repository_root=repository_root,
        source_roots=manifest["source_roots"],
    )
    if after != manifest["files"]:
        raise Task21ForwardRecoveryError("source_mutation_detected")
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


def verify_and_restore_archive(
    *,
    archive_path: Path,
    expected_archive_sha256: str,
    restore_root: Path,
    source_repository_root: Path | None = None,
) -> JsonObject:
    """Verify archive bytes and restore create-only into an isolated root."""

    archive_bytes = archive_path.read_bytes()
    actual_archive_sha256 = sha256_bytes(archive_bytes)
    if actual_archive_sha256 != expected_archive_sha256:
        raise Task21ForwardRecoveryError("archive_sha256_drift")
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = archive.namelist()
        if not names or names.count(MANIFEST_ENTRY) != 1:
            raise Task21ForwardRecoveryError("archive_manifest_missing_or_duplicate")
        manifest = json.loads(archive.read(MANIFEST_ENTRY).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise Task21ForwardRecoveryError("archive_manifest_invalid")
        files = manifest.get("files")
        if not isinstance(files, list):
            raise Task21ForwardRecoveryError("archive_inventory_invalid")
        expected_names = [MANIFEST_ENTRY, *(str(row["path"]) for row in files)]
        if names != expected_names or len(set(names)) != len(names):
            raise Task21ForwardRecoveryError("archive_entry_inventory_drift")
        if len(files) != manifest.get("file_count"):
            raise Task21ForwardRecoveryError("manifest_file_count_drift")
        if sum(int(row["bytes"]) for row in files) != manifest.get("stored_bytes"):
            raise Task21ForwardRecoveryError("manifest_stored_bytes_drift")
        if sha256_bytes(canonical_json_bytes(files)) != manifest.get(
            "source_inventory_sha256"
        ):
            raise Task21ForwardRecoveryError("manifest_inventory_hash_drift")

        restore_root = restore_root.resolve()
        restore_root.mkdir(parents=True, exist_ok=True)
        restored: list[JsonObject] = []
        for row in files:
            relative = _safe_relative(str(row["path"])).as_posix()
            value = archive.read(relative)
            if len(value) != row["bytes"]:
                raise Task21ForwardRecoveryError(
                    f"archive_entry_size_drift:{relative}"
                )
            if sha256_bytes(value) != row["sha256"]:
                raise Task21ForwardRecoveryError(
                    f"archive_entry_hash_drift:{relative}"
                )
            destination = (restore_root / relative).resolve()
            if not destination.is_relative_to(restore_root):
                raise Task21ForwardRecoveryError(
                    f"restore_path_escape:{relative}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.read_bytes() != value:
                    raise Task21ForwardRecoveryError(
                        f"existing_restore_bytes_drift:{relative}"
                    )
            else:
                with destination.open("xb") as handle:
                    handle.write(value)
            restored.append(
                {
                    "path": relative,
                    "bytes": len(value),
                    "sha256": sha256_bytes(value),
                }
            )

    if restored != files:
        raise Task21ForwardRecoveryError("restored_inventory_drift")
    source_unchanged = None
    if source_repository_root is not None:
        source_unchanged = build_source_inventory(
            repository_root=source_repository_root,
            source_roots=manifest["source_roots"],
        ) == files
        if not source_unchanged:
            raise Task21ForwardRecoveryError("source_mutation_detected")
    return {
        "archive_sha256": actual_archive_sha256,
        "archive_md5": md5_bytes(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "manifest": manifest,
        "restored_file_count": len(restored),
        "restored_stored_bytes": sum(int(row["bytes"]) for row in restored),
        "restored_inventory_sha256": sha256_bytes(canonical_json_bytes(restored)),
        "source_unchanged": source_unchanged,
        "source_mutations": 0,
        "source_deletions": 0,
    }
