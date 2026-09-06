"""Lossless SNAPSHOT_PLUS_DELTA member representation and reconstruction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.observation_schedule import canonical_sha256

LAYOUT_KIND = "SNAPSHOT_PLUS_DELTA"
LEGACY_KIND = "LEGACY_FULL"
UNIT_SCHEMA = "smial.members-snapshot-plus-delta-unit"
DELTA_SCHEMA = "smial.members-snapshot-delta"
DELTA_SCHEMA_VERSION_V1 = "1.0"
DELTA_SCHEMA_VERSION_V2 = "2.0"
SUPPORTED_DELTA_SCHEMA_VERSIONS = frozenset(
    {DELTA_SCHEMA_VERSION_V1, DELTA_SCHEMA_VERSION_V2}
)

_FINGERPRINT_WORK = {"snapshot_fingerprint": 0, "row_fingerprint": 0}


class MembersDeltaError(ValueError):
    """Typed SNAPSHOT_PLUS_DELTA failure."""


def reset_fingerprint_work() -> None:
    _FINGERPRINT_WORK["snapshot_fingerprint"] = 0
    _FINGERPRINT_WORK["row_fingerprint"] = 0


def fingerprint_work() -> dict[str, int]:
    return dict(_FINGERPRINT_WORK)


def row_fingerprint(row: Mapping[str, Any]) -> str:
    _FINGERPRINT_WORK["row_fingerprint"] += 1
    return canonical_sha256(dict(row))


def snapshot_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    _FINGERPRINT_WORK["snapshot_fingerprint"] += 1
    ordered = [dict(row) for row in sorted(rows, key=lambda item: str(item.get("entity_id") or ""))]
    return canonical_sha256(ordered)


def diff_member_snapshots(
    previous: Sequence[Mapping[str, Any]],
    current: Sequence[Mapping[str, Any]],
    *,
    include_unchanged: bool = False,
) -> dict[str, Any]:
    prev_by = {str(row.get("entity_id") or ""): dict(row) for row in previous}
    curr_by = {str(row.get("entity_id") or ""): dict(row) for row in current}
    if "" in prev_by or "" in curr_by:
        raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
    if len(prev_by) != len(previous) or len(curr_by) != len(current):
        raise MembersDeltaError("DUPLICATE_ENTITY_ID")
    prev_fp = {entity_id: row_fingerprint(row) for entity_id, row in prev_by.items()}
    added: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged: list[dict[str, str]] = []
    for entity_id, row in curr_by.items():
        digest = row_fingerprint(row)
        if entity_id not in prev_by:
            added.append(row)
            continue
        if prev_fp[entity_id] != digest:
            changed.append(row)
        elif include_unchanged:
            unchanged.append({"entity_id": entity_id, "fingerprint": digest})
    removed: list[dict[str, str]] = []
    for entity_id, row in prev_by.items():
        if entity_id not in curr_by:
            removed.append({"entity_id": entity_id, "fingerprint": prev_fp[entity_id]})
    payload = {
        "added": added,
        "removed": removed,
        "changed": changed,
    }
    if include_unchanged:
        payload["unchanged"] = unchanged
    return payload


def apply_member_delta(
    base_rows: Sequence[Mapping[str, Any]],
    delta: Mapping[str, Any],
    *,
    previous_fingerprint: str | None = None,
    verify_unchanged: bool = False,
    verify_base_hash: bool = False,
) -> list[dict[str, Any]]:
    by_id = {str(row.get("entity_id") or ""): dict(row) for row in base_rows}
    expected_previous = str(delta.get("previous_fingerprint") or "")
    if previous_fingerprint is not None and expected_previous != str(previous_fingerprint):
        raise MembersDeltaError("DELTA_HASH_MISMATCH")
    if verify_base_hash:
        if snapshot_fingerprint(base_rows) != expected_previous:
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
    for item in delta.get("removed") or []:
        entity_id = str(item.get("entity_id") or "")
        if entity_id not in by_id:
            raise MembersDeltaError("DELTA_REMOVE_MISSING")
        if row_fingerprint(by_id[entity_id]) != str(item.get("fingerprint") or ""):
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        del by_id[entity_id]
    for row in list(delta.get("changed") or []) + list(delta.get("added") or []):
        payload = dict(row)
        entity_id = str(payload.get("entity_id") or "")
        if not entity_id:
            raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
        by_id[entity_id] = payload
    if verify_unchanged:
        for item in delta.get("unchanged") or []:
            entity_id = str(item.get("entity_id") or "")
            if entity_id not in by_id:
                raise MembersDeltaError("DELTA_UNCHANGED_MISSING")
            if row_fingerprint(by_id[entity_id]) != str(item.get("fingerprint") or ""):
                raise MembersDeltaError("DELTA_HASH_MISMATCH")
    return [by_id[key] for key in sorted(by_id)]


def _write_parquet_zstd(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([dict(row) for row in rows])
    tmp = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=3)
    payload = tmp.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    tmp.replace(path)
    return digest


def write_snapshot_unit(
    data_root: Path,
    *,
    utc_day: str,
    dataset_manifest_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unit_dir = data_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    _require_unique_entity_ids(rows)
    rel = f"datasets/members_snapshot_plus_delta/{utc_day}/snapshot/{dataset_manifest_id}/members.parquet"
    path = data_root / rel
    file_sha256 = _write_snapshot_or_reuse(path, rows)
    unit = {
        "schema": UNIT_SCHEMA,
        "schema_version": "1.0",
        "layout": LAYOUT_KIND,
        "utc_day": utc_day,
        "anchor_dataset_manifest_id": dataset_manifest_id,
        "publications": [
            {
                "seq": 0,
                "dataset_manifest_id": dataset_manifest_id,
                "kind": "snapshot",
                "rel": rel.replace("\\", "/"),
                "sha256": file_sha256,
                "row_count": len(rows),
                "snapshot_fingerprint": snapshot_fingerprint(rows),
            }
        ],
    }
    _write_unit(unit_dir / "unit.json", unit)
    _write_layout_sidecar(path, unit, dataset_manifest_id)
    return unit


def append_delta_publication(
    data_root: Path,
    *,
    utc_day: str,
    dataset_manifest_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unit_dir = data_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    unit_path = unit_dir / "unit.json"
    if unit_path.is_file() is False:
        raise MembersDeltaError("ANCHOR_MISSING")
    _require_unique_entity_ids(rows)
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    if not isinstance(unit, dict) or unit.get("layout") != LAYOUT_KIND:
        raise MembersDeltaError("UNIT_LAYOUT_INVALID")
    previous_id = str(unit["publications"][-1]["dataset_manifest_id"])
    reconstructed = reconstruct_publication(data_root, unit, previous_id)
    previous_fp = str(unit["publications"][-1]["snapshot_fingerprint"])
    delta = diff_member_snapshots(reconstructed, rows, include_unchanged=False)
    current_fp = snapshot_fingerprint(rows)
    delta_payload = {
        "schema": DELTA_SCHEMA,
        "schema_version": DELTA_SCHEMA_VERSION_V2,
        "dataset_manifest_id": dataset_manifest_id,
        "previous_dataset_manifest_id": previous_id,
        "previous_fingerprint": previous_fp,
        "current_fingerprint": current_fp,
        "added": delta["added"],
        "changed": delta["changed"],
        "removed": delta["removed"],
        "counts": {
            "added": len(delta["added"]),
            "changed": len(delta["changed"]),
            "removed": len(delta["removed"]),
            "previous_row_count": len(reconstructed),
            "current_row_count": len(rows),
        },
    }
    seq = int(unit["publications"][-1]["seq"]) + 1
    rel = (
        f"datasets/members_snapshot_plus_delta/{utc_day}/deltas/"
        f"{seq:04d}-{dataset_manifest_id}/members.parquet"
    )
    path = data_root / rel
    digest = persist_delta_payload(path, delta_payload)
    applied = apply_member_delta(
        reconstructed,
        delta_payload,
        previous_fingerprint=previous_fp,
        verify_unchanged=False,
        verify_base_hash=False,
    )
    if snapshot_fingerprint(applied) != current_fp:
        raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
    unit["publications"].append(
        {
            "seq": seq,
            "dataset_manifest_id": dataset_manifest_id,
            "kind": "delta",
            "rel": rel.replace("\\", "/"),
            "sha256": digest,
            "row_count": len(rows),
            "snapshot_fingerprint": current_fp,
            "delta_schema_version": DELTA_SCHEMA_VERSION_V2,
        }
    )
    _write_unit(unit_path, unit)
    _write_layout_sidecar(path, unit, dataset_manifest_id)
    return unit


def reconstruct_publication(
    data_root: Path,
    unit: Mapping[str, Any],
    dataset_manifest_id: str,
) -> list[dict[str, Any]]:
    publications = list(unit.get("publications") or [])
    if not publications:
        raise MembersDeltaError("ANCHOR_MISSING")
    anchor = publications[0]
    try:
        anchor_seq = int(anchor.get("seq"))
    except (TypeError, ValueError):
        raise MembersDeltaError("ANCHOR_MISSING") from None
    if str(anchor.get("kind") or "") != "snapshot" or anchor_seq != 0:
        raise MembersDeltaError("ANCHOR_MISSING")
    snapshot_path = data_root / str(anchor["rel"])
    if snapshot_path.is_file() is False:
        raise MembersDeltaError("ANCHOR_MISSING")
    observed = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if observed != str(anchor.get("sha256") or ""):
        raise MembersDeltaError("DELTA_HASH_MISMATCH")
    current = [dict(row) for row in pq.read_table(snapshot_path).to_pylist()]
    running_fp = snapshot_fingerprint(current)
    if running_fp != str(anchor.get("snapshot_fingerprint") or ""):
        raise MembersDeltaError("DELTA_HASH_MISMATCH")
    previous_id = str(anchor.get("dataset_manifest_id") or "")
    if previous_id == dataset_manifest_id:
        return current
    for index, item in enumerate(publications[1:], start=1):
        try:
            item_seq = int(item.get("seq"))
        except (TypeError, ValueError):
            raise MembersDeltaError("DELTA_SEQUENCE_INVALID") from None
        if item_seq != index:
            raise MembersDeltaError("DELTA_SEQUENCE_INVALID")
        if str(item.get("kind") or "") != "delta":
            raise MembersDeltaError("UNIT_LAYOUT_INVALID")
        rel = str(item.get("rel") or "")
        path = data_root / rel
        if path.is_file() is False:
            raise MembersDeltaError("DELTA_MISSING")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != str(item.get("sha256") or ""):
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        delta = _read_delta_payload(path, payload)
        schema_version = str(delta.get("schema_version") or DELTA_SCHEMA_VERSION_V1)
        if schema_version not in SUPPORTED_DELTA_SCHEMA_VERSIONS:
            raise MembersDeltaError("DELTA_SCHEMA_UNSUPPORTED")
        if str(delta.get("previous_dataset_manifest_id") or "") != previous_id:
            raise MembersDeltaError("DELTA_SEQUENCE_INVALID")
        if str(delta.get("dataset_manifest_id") or "") != str(item.get("dataset_manifest_id") or ""):
            raise MembersDeltaError("DELTA_SEQUENCE_INVALID")
        if str(delta.get("previous_fingerprint") or "") != running_fp:
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        current = apply_member_delta(
            current,
            delta,
            previous_fingerprint=running_fp,
            verify_unchanged=False,
            verify_base_hash=False,
        )
        unit_fp = str(item.get("snapshot_fingerprint") or "")
        current_fp = str(delta.get("current_fingerprint") or "")
        is_target = str(item.get("dataset_manifest_id") or "") == dataset_manifest_id
        if schema_version == DELTA_SCHEMA_VERSION_V2:
            if not current_fp:
                raise MembersDeltaError("DELTA_CORRUPT")
            if unit_fp and current_fp != unit_fp:
                raise MembersDeltaError("DELTA_HASH_MISMATCH")
        if is_target:
            observed_fp = snapshot_fingerprint(current)
            if unit_fp and observed_fp != unit_fp:
                raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
            if schema_version == DELTA_SCHEMA_VERSION_V2 and observed_fp != current_fp:
                raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
            return current
        running_fp = current_fp or unit_fp
        if not running_fp:
            raise MembersDeltaError("DELTA_CORRUPT")
        previous_id = str(item.get("dataset_manifest_id") or "")
    raise MembersDeltaError("PUBLICATION_NOT_IN_UNIT")


def load_member_rows_for_location(data_root: Path, logical_location: str) -> list[dict[str, Any]]:
    path = data_root / logical_location
    sidecar = path.with_name("members.layout.json")
    if sidecar.is_file():
        layout = json.loads(sidecar.read_text(encoding="utf-8"))
        kind = str(layout.get("kind") or "")
        if kind == LAYOUT_KIND:
            unit_rel = str(layout.get("unit_rel") or "")
            unit_path = data_root / unit_rel
            if unit_path.is_file() is False:
                raise MembersDeltaError("ANCHOR_MISSING")
            unit = json.loads(unit_path.read_text(encoding="utf-8"))
            if not isinstance(unit, dict):
                raise MembersDeltaError("UNIT_LAYOUT_INVALID")
            return reconstruct_publication(
                data_root,
                unit,
                str(layout.get("dataset_manifest_id") or ""),
            )
        if kind != LEGACY_KIND:
            raise MembersDeltaError("UNIT_LAYOUT_INVALID")
    if path.is_file() is False:
        raise MembersDeltaError("MEMBER_FILE_MISSING")
    table = pq.read_table(path)
    if "entity_id" not in table.column_names:
        raise MembersDeltaError("LAYOUT_SIDECAR_MISSING")
    return [dict(row) for row in table.to_pylist()]


def persist_delta_payload(path: Path, delta_payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(delta_payload, sort_keys=True, separators=(",", ":"))
    table = pa.table({"delta_json": [encoded]})
    tmp = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=3)
    payload = tmp.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    tmp.replace(path)
    return digest


def _write_delta_parquet(path: Path, delta_payload: Mapping[str, Any]) -> str:
    return persist_delta_payload(path, delta_payload)


def _read_delta_payload(path: Path, payload: bytes) -> dict[str, Any]:
    try:
        if path.suffix == ".json":
            delta = json.loads(payload.decode("utf-8"))
        else:
            rows = pq.read_table(path).to_pylist()
            if len(rows) != 1 or not isinstance(rows[0].get("delta_json"), str):
                raise MembersDeltaError("DELTA_CORRUPT")
            delta = json.loads(str(rows[0]["delta_json"]))
    except MembersDeltaError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, pa.ArrowException, OSError) as exc:
        raise MembersDeltaError("DELTA_CORRUPT") from exc
    if not isinstance(delta, dict):
        raise MembersDeltaError("DELTA_CORRUPT")
    return delta


def _write_snapshot_or_reuse(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    return _write_parquet_zstd(path, rows)


def _require_unique_entity_ids(rows: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if not entity_id:
            raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
        if entity_id in seen:
            raise MembersDeltaError("DUPLICATE_ENTITY_ID")
        seen.add(entity_id)


def _write_unit(path: Path, unit: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(unit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_layout_sidecar(artifact: Path, unit: Mapping[str, Any], dataset_manifest_id: str) -> None:
    sidecar = artifact.with_name("members.layout.json")
    payload = {
        "kind": LAYOUT_KIND,
        "utc_day": unit["utc_day"],
        "dataset_manifest_id": dataset_manifest_id,
        "unit_rel": f"datasets/members_snapshot_plus_delta/{unit['utc_day']}/unit.json",
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
