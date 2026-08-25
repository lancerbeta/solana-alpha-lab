"""Cold-copy proof helpers built on storage-agnostic snapshot export/restore."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.fast_lane_snapshot import (
    SnapshotError,
    export_snapshot,
    restore_snapshot,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchStore,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


class ColdCopyError(ValueError):
    """Typed cold-copy failure surfaced to CLI and tests."""


@dataclass(frozen=True, slots=True)
class ColdCopyBackup:
    backup_root: Path
    committed_inventory_sha256: str
    file_count: int
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class ColdCopyProof:
    source_inventory_sha256: str
    restored_inventory_sha256: str
    source_projection_digest_sha256: str | None
    restored_projection_digest_sha256: str | None
    source_result_digest_sha256: str
    restored_result_digest_sha256: str
    source_result_payload_sha256: str
    restored_result_payload_sha256: str
    run_id: str
    snapshot_id: str


def backup_committed_inventory(data_root: Path, backup_root: Path) -> ColdCopyBackup:
    """Export an immutable snapshot into a storage-agnostic destination folder."""

    try:
        exported = export_snapshot(data_root, backup_root)
    except SnapshotError as exc:
        raise ColdCopyError(str(exc)) from exc
    return ColdCopyBackup(
        backup_root=exported.snapshot_root,
        committed_inventory_sha256=exported.committed_inventory_sha256,
        file_count=exported.entry_count,
        snapshot_id=exported.snapshot_id,
    )


def restore_committed_inventory(backup_root: Path, target_root: Path) -> None:
    """Restore a verified snapshot into a fresh data root without derived state."""

    try:
        restore_snapshot(backup_root, target_root)
    except SnapshotError as exc:
        raise ColdCopyError(str(exc)) from exc


def load_run_result_artifact(data_root: Path, passport: dict[str, Any]) -> dict[str, Any]:
    artifact_id = passport.get("result_artifact_id")
    run_id = passport.get("run_id")
    logical_uri = passport.get("result_artifact_logical_uri")
    if not isinstance(artifact_id, str) or not isinstance(logical_uri, str):
        raise ColdCopyError("RESULT_ARTIFACT_REFERENCE_MISSING")
    if isinstance(run_id, str):
        store = ResearchStore(data_root)
        for record in store.iter_committed_records():
            if record.record_kind != RecordKind.RESEARCH_ARTIFACT:
                continue
            if record.run_id != run_id:
                continue
            try:
                payload = json.loads(record.payload_json)
            except (OSError, json.JSONDecodeError) as exc:
                raise ColdCopyError("RESULT_ARTIFACT_INVALID") from exc
            if not isinstance(payload, dict):
                raise ColdCopyError("RESULT_ARTIFACT_INVALID")
            if payload.get("research_artifact_id") != artifact_id:
                continue
            capability_result = payload.get("capability_result")
            if isinstance(capability_result, dict):
                return {
                    "research_artifact_id": artifact_id,
                    "logical_uri": logical_uri,
                    "capability_result": capability_result,
                }
    if not logical_uri.startswith("smial-data://"):
        raise ColdCopyError("RESULT_ARTIFACT_URI_INVALID")
    relative = logical_uri.removeprefix("smial-data://")
    artifact_path = data_root / relative
    if artifact_path.is_symlink() or not artifact_path.is_file():
        raise ColdCopyError("RESULT_ARTIFACT_UNAVAILABLE")
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ColdCopyError("RESULT_ARTIFACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise ColdCopyError("RESULT_ARTIFACT_INVALID")
    if payload.get("research_artifact_id") != artifact_id:
        raise ColdCopyError("RESULT_ARTIFACT_ID_MISMATCH")
    return payload


def prove_cold_copy(
    source_root: Path,
    snapshot_root: Path,
    *,
    run_id: str,
    restored_root: Path,
) -> ColdCopyProof:
    """Restore an existing snapshot to a fresh root, rebuild projection, and compare values."""

    source_store = ResearchStore(source_root)
    source_diag = source_store.diagnostics()
    source_row = source_store.find_completed_run_by_id(run_id)
    if source_row is None:
        raise ColdCopyError("SOURCE_RUN_NOT_FOUND")
    source_passport = dict(source_row.payload)
    source_artifact = load_run_result_artifact(source_root, source_passport)
    source_result_payload_sha256 = canonical_sha256(source_artifact["capability_result"])

    if restored_root.exists():
        shutil.rmtree(restored_root)
    restore_committed_inventory(snapshot_root, restored_root)

    restored_store = ResearchStore(restored_root)
    restored_store.rebuild_projection()
    restored_diag = restored_store.diagnostics()
    restored_row = restored_store.find_completed_run_by_id(run_id)
    if restored_row is None:
        raise ColdCopyError("RESTORED_RUN_NOT_FOUND")
    restored_passport = dict(restored_row.payload)
    restored_artifact = load_run_result_artifact(restored_root, restored_passport)
    restored_result_payload_sha256 = canonical_sha256(
        restored_artifact["capability_result"]
    )

    if source_diag.committed_inventory_sha256 != restored_diag.committed_inventory_sha256:
        raise ColdCopyError("INVENTORY_DIGEST_MISMATCH")
    if source_diag.projection_digest_sha256 != restored_diag.projection_digest_sha256:
        raise ColdCopyError("PROJECTION_DIGEST_MISMATCH")
    if source_passport["result_digest_sha256"] != restored_passport["result_digest_sha256"]:
        raise ColdCopyError("RESULT_DIGEST_MISMATCH")
    if source_result_payload_sha256 != restored_result_payload_sha256:
        raise ColdCopyError("RESULT_PAYLOAD_MISMATCH")

    return ColdCopyProof(
        source_inventory_sha256=source_diag.committed_inventory_sha256,
        restored_inventory_sha256=restored_diag.committed_inventory_sha256,
        source_projection_digest_sha256=source_diag.projection_digest_sha256,
        restored_projection_digest_sha256=restored_diag.projection_digest_sha256,
        source_result_digest_sha256=str(source_passport["result_digest_sha256"]),
        restored_result_digest_sha256=str(restored_passport["result_digest_sha256"]),
        source_result_payload_sha256=source_result_payload_sha256,
        restored_result_payload_sha256=restored_result_payload_sha256,
        run_id=run_id,
        snapshot_id=snapshot_root.name,
    )


__all__ = [
    "ColdCopyBackup",
    "ColdCopyError",
    "ColdCopyProof",
    "backup_committed_inventory",
    "load_run_result_artifact",
    "prove_cold_copy",
    "restore_committed_inventory",
]
