"""Storage-agnostic filesystem snapshot export and restore for the Fast Lane data plane."""

from __future__ import annotations

import hashlib
import json
import shutil
import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from solana_alpha_lab.contracts.schema_v1 import PartitionManifest
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
from solana_alpha_lab.storage.manifests import (
    ManifestContractError,
    ManifestIntegrityError,
    verify_partition_manifest,
)

SNAPSHOT_MANIFEST_NAME = "SNAPSHOT-MANIFEST.json"
INVENTORY_NAME = "INVENTORY.json"
OBJECTS_DIR = "objects"
PAYLOAD_DIR = "payload"
EXCLUDED_RELATIVE_PREFIXES = (
    "projections/",
    "ops/",
    "locks/",
)
EXCLUDED_RELATIVE_NAMES = frozenset(
    {
        SNAPSHOT_MANIFEST_NAME,
        INVENTORY_NAME,
    }
)


class SnapshotError(ValueError):
    """Typed snapshot export or restore failure."""


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    logical_path: str
    content_sha256: str
    object_key: str


@dataclass(frozen=True, slots=True)
class SnapshotExport:
    snapshot_id: str
    snapshot_root: Path
    inventory_sha256: str
    created_at: str
    entry_count: int
    committed_inventory_sha256: str


@dataclass(frozen=True, slots=True)
class SnapshotRestore:
    snapshot_id: str
    destination_root: Path
    inventory_sha256: str
    entry_count: int
    committed_inventory_sha256: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _safe_relative_path(relative: str) -> str:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts:
        raise SnapshotError("LOGICAL_PATH_UNSAFE")
    return posix.as_posix()


def _is_excluded_relative(relative: str) -> bool:
    normalized = _safe_relative_path(relative)
    if normalized.startswith("_") or "/_" in normalized:
        return True
    if normalized.endswith(".tmp") or normalized.endswith(".duckdb") or normalized.endswith(".sqlite"):
        return True
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_RELATIVE_PREFIXES)


def _manifest_files(data_root: Path) -> tuple[Path, ...]:
    manifest_dir = data_root / "research" / "manifests" / "partitions"
    if not manifest_dir.exists():
        return ()
    if manifest_dir.is_symlink() or not manifest_dir.is_dir():
        raise SnapshotError("MANIFEST_DIRECTORY_UNSAFE")
    return tuple(sorted(manifest_dir.glob("partition-*.json")))


def _read_partition_manifest(path: Path) -> PartitionManifest:
    if path.is_symlink() or not path.is_file():
        raise SnapshotError("PARTITION_MANIFEST_UNSAFE")
    try:
        manifest = PartitionManifest.model_validate_json(path.read_bytes())
        verify_partition_manifest(manifest)
    except (
        OSError,
        ValidationError,
        ManifestContractError,
        ManifestIntegrityError,
    ) as exc:
        raise SnapshotError("PARTITION_MANIFEST_INVALID") from exc
    return manifest


def _object_key(content_sha256: str) -> str:
    if len(content_sha256) != 64:
        raise SnapshotError("CONTENT_SHA256_INVALID")
    return f"{OBJECTS_DIR}/{content_sha256[:2]}/{content_sha256}"


def _read_file_entry(data_root: Path, relative: str) -> SnapshotEntry:
    normalized = _safe_relative_path(relative)
    if _is_excluded_relative(normalized):
        raise SnapshotError("LOGICAL_PATH_EXCLUDED")
    source = data_root / normalized
    if source.is_symlink() or not source.is_file():
        raise SnapshotError("SNAPSHOT_SOURCE_MISSING")
    content = source.read_bytes()
    content_sha256 = _sha256_bytes(content)
    return SnapshotEntry(
        logical_path=normalized,
        content_sha256=content_sha256,
        object_key=_object_key(content_sha256),
    )


def _collect_inventory(data_root: Path) -> list[SnapshotEntry]:
    source_root = data_root.resolve()
    entries: dict[str, SnapshotEntry] = {}

    for manifest_path in _manifest_files(source_root):
        manifest = _read_partition_manifest(manifest_path)
        for relative in (
            manifest_path.relative_to(source_root).as_posix(),
            manifest.logical_location,
        ):
            entry = _read_file_entry(source_root, relative)
            entries[entry.logical_path] = entry

    artifacts_root = source_root / "research" / "artifacts" / "results"
    if artifacts_root.is_dir() and not artifacts_root.is_symlink():
        for artifact_path in sorted(artifacts_root.glob("*.json")):
            if artifact_path.is_symlink() or not artifact_path.is_file():
                continue
            relative = artifact_path.relative_to(source_root).as_posix()
            entry = _read_file_entry(source_root, relative)
            entries[entry.logical_path] = entry

    datasets_manifests = source_root / "datasets" / "manifests"
    if datasets_manifests.is_dir() and not datasets_manifests.is_symlink():
        for manifest_path in sorted(datasets_manifests.rglob("*.json")):
            if manifest_path.is_symlink() or not manifest_path.is_file():
                continue
            relative = manifest_path.relative_to(source_root).as_posix()
            if _is_excluded_relative(relative):
                continue
            entry = _read_file_entry(source_root, relative)
            entries[entry.logical_path] = entry

    datasets_partitions = source_root / "datasets" / "partitions"
    if datasets_partitions.is_dir() and not datasets_partitions.is_symlink():
        for parquet_path in sorted(datasets_partitions.rglob("*.parquet")):
            if parquet_path.is_symlink() or not parquet_path.is_file():
                continue
            relative = parquet_path.relative_to(source_root).as_posix()
            entry = _read_file_entry(source_root, relative)
            entries[entry.logical_path] = entry

    if not entries:
        raise SnapshotError("SNAPSHOT_INVENTORY_EMPTY")

    return [entries[key] for key in sorted(entries)]


def _inventory_payload(entries: Sequence[SnapshotEntry]) -> list[dict[str, str]]:
    return [
        {
            "content_sha256": entry.content_sha256,
            "logical_path": entry.logical_path,
            "object_key": entry.object_key,
        }
        for entry in entries
    ]


def _inventory_sha256(entries: Sequence[SnapshotEntry]) -> str:
    return _sha256_bytes(_canonical_json_bytes(_inventory_payload(entries)))


def _snapshot_id(*, created_at: datetime, inventory_sha256: str) -> str:
    compact = created_at.strftime("%Y%m%dT%H%M%SZ")
    return f"SNAPSHOT-{compact}-{inventory_sha256[:12].upper()}"


def export_snapshot(data_root: Path, destination: Path) -> SnapshotExport:
    """Export committed immutable bytes to a storage-agnostic snapshot directory."""

    source_root = data_root.resolve()
    destination_root = destination.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)

    entries = _collect_inventory(source_root)
    created_at = _utc_now()
    inventory_sha256 = _inventory_sha256(entries)
    snapshot_id = _snapshot_id(created_at=created_at, inventory_sha256=inventory_sha256)
    snapshot_root = destination_root / snapshot_id
    if snapshot_root.exists():
        raise SnapshotError("SNAPSHOT_DESTINATION_EXISTS")
    snapshot_root.mkdir(parents=True, exist_ok=False)

    copied_objects: set[str] = set()
    for entry in entries:
        source = source_root / entry.logical_path
        object_path = snapshot_root / entry.object_key
        if entry.content_sha256 not in copied_objects:
            object_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, object_path)
            observed = _sha256_bytes(object_path.read_bytes())
            if observed != entry.content_sha256:
                raise SnapshotError("OBJECT_HASH_MISMATCH")
            copied_objects.add(entry.content_sha256)

    inventory_path = snapshot_root / INVENTORY_NAME
    inventory_path.write_bytes(_canonical_json_bytes(_inventory_payload(entries)))

    store = ResearchStore(source_root)
    try:
        committed_inventory_sha256 = store.diagnostics().committed_inventory_sha256
    except ResearchStoreError as exc:
        raise SnapshotError("COMMITTED_INVENTORY_UNAVAILABLE") from exc

    snapshot_manifest = {
        "committed_inventory_sha256": committed_inventory_sha256,
        "created_at": _timestamp_text(created_at),
        "entry_count": len(entries),
        "inventory_sha256": inventory_sha256,
        "profile": "smial-fast-lane-snapshot-v1",
        "snapshot_id": snapshot_id,
    }
    manifest_path = snapshot_root / SNAPSHOT_MANIFEST_NAME
    manifest_path.write_bytes(_canonical_json_bytes(snapshot_manifest))

    return SnapshotExport(
        snapshot_id=snapshot_id,
        snapshot_root=snapshot_root,
        inventory_sha256=inventory_sha256,
        created_at=snapshot_manifest["created_at"],
        entry_count=len(entries),
        committed_inventory_sha256=committed_inventory_sha256,
    )


def _load_snapshot(snapshot_root: Path) -> tuple[dict[str, Any], list[SnapshotEntry]]:
    root = snapshot_root.resolve()
    manifest_path = root / SNAPSHOT_MANIFEST_NAME
    inventory_path = root / INVENTORY_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise SnapshotError("SNAPSHOT_MANIFEST_MISSING")
    if not inventory_path.is_file() or inventory_path.is_symlink():
        raise SnapshotError("SNAPSHOT_INVENTORY_MISSING")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        inventory_raw = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError("SNAPSHOT_METADATA_INVALID") from exc
    if not isinstance(manifest, dict) or not isinstance(inventory_raw, list):
        raise SnapshotError("SNAPSHOT_METADATA_INVALID")

    entries: list[SnapshotEntry] = []
    for item in inventory_raw:
        if not isinstance(item, dict):
            raise SnapshotError("SNAPSHOT_INVENTORY_INVALID")
        logical_path = item.get("logical_path")
        content_sha256 = item.get("content_sha256")
        object_key = item.get("object_key")
        if not isinstance(logical_path, str) or not isinstance(content_sha256, str):
            raise SnapshotError("SNAPSHOT_INVENTORY_INVALID")
        if not isinstance(object_key, str):
            object_key = _object_key(content_sha256)
        entries.append(
            SnapshotEntry(
                logical_path=_safe_relative_path(logical_path),
                content_sha256=content_sha256,
                object_key=_object_key(content_sha256),
            )
        )

    inventory_sha256 = _inventory_sha256(entries)
    if manifest.get("inventory_sha256") != inventory_sha256:
        raise SnapshotError("SNAPSHOT_INVENTORY_HASH_MISMATCH")
    if manifest.get("entry_count") != len(entries):
        raise SnapshotError("SNAPSHOT_ENTRY_COUNT_MISMATCH")
    return manifest, entries


def restore_snapshot(source: Path, destination: Path) -> SnapshotRestore:
    """Verify snapshot hashes and publish immutable bytes into a fresh data root."""

    snapshot_root = source.resolve()
    destination_root = destination.resolve()
    if destination_root.exists():
        for child in destination_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        destination_root.mkdir(parents=True, exist_ok=True)

    manifest, entries = _load_snapshot(snapshot_root)

    for entry in entries:
        if _is_excluded_relative(entry.logical_path):
            raise SnapshotError("SNAPSHOT_ENTRY_EXCLUDED")
        object_path = snapshot_root / entry.object_key
        if object_path.is_symlink() or not object_path.is_file():
            raise SnapshotError("SNAPSHOT_OBJECT_MISSING")
        content = object_path.read_bytes()
        observed = _sha256_bytes(content)
        if observed != entry.content_sha256:
            raise SnapshotError("SNAPSHOT_OBJECT_HASH_MISMATCH")

    for entry in entries:
        target = destination_root / entry.logical_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_root / entry.object_key, target)
        if _sha256_bytes(target.read_bytes()) != entry.content_sha256:
            raise SnapshotError("RESTORED_OBJECT_HASH_MISMATCH")

    store = ResearchStore(destination_root)
    restored_inventory_sha256 = store.diagnostics().committed_inventory_sha256
    expected_inventory = manifest.get("committed_inventory_sha256")
    if (
        isinstance(expected_inventory, str)
        and restored_inventory_sha256 != expected_inventory
    ):
        raise SnapshotError("RESTORED_INVENTORY_MISMATCH")

    snapshot_id = str(manifest.get("snapshot_id") or snapshot_root.name)
    inventory_sha256 = str(manifest.get("inventory_sha256") or _inventory_sha256(entries))
    return SnapshotRestore(
        snapshot_id=snapshot_id,
        destination_root=destination_root,
        inventory_sha256=inventory_sha256,
        entry_count=len(entries),
        committed_inventory_sha256=restored_inventory_sha256,
    )


__all__ = [
    "SnapshotError",
    "SnapshotExport",
    "SnapshotRestore",
    "export_snapshot",
    "restore_snapshot",
]
