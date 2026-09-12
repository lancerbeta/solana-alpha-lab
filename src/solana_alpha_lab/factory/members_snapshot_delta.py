"""Lossless SNAPSHOT_PLUS_DELTA member representation and reconstruction."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sqlite3
import tempfile
from collections.abc import Iterator, Mapping, Sequence
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
_MEMBER_BATCH_SIZE = 2048

_FINGERPRINT_WORK = {"snapshot_fingerprint": 0, "row_fingerprint": 0}
_RECONSTRUCT_STATS = {"peak_sqlite_rows": 0, "reconstruct_calls": 0}


class MembersDeltaError(ValueError):
    """Typed SNAPSHOT_PLUS_DELTA failure."""


def reset_fingerprint_work() -> None:
    _FINGERPRINT_WORK["snapshot_fingerprint"] = 0
    _FINGERPRINT_WORK["row_fingerprint"] = 0
    _RECONSTRUCT_STATS["peak_sqlite_rows"] = 0
    _RECONSTRUCT_STATS["reconstruct_calls"] = 0


def fingerprint_work() -> dict[str, int]:
    return dict(_FINGERPRINT_WORK)


def reconstruct_stats() -> dict[str, int]:
    return dict(_RECONSTRUCT_STATS)


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
    spill, conn = _spill_member_sequence(rows)
    try:
        return _write_parquet_zstd_from_conn(path, conn)
    finally:
        conn.close()
        spill.unlink(missing_ok=True)


def _spill_member_sequence(
    rows: Sequence[Mapping[str, Any]] | Iterator[Mapping[str, Any]],
) -> tuple[Path, sqlite3.Connection]:
    spill, conn = _spill_members_db()
    batch: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    try:
        for row in rows:
            payload = dict(row)
            entity_id = str(payload.get("entity_id") or "")
            if not entity_id:
                raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
            if entity_id in seen:
                raise MembersDeltaError("DUPLICATE_ENTITY_ID")
            seen.add(entity_id)
            batch.append(
                (entity_id, pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
            )
            if len(batch) >= _MEMBER_BATCH_SIZE:
                conn.executemany(
                    "INSERT INTO members(entity_id, payload) VALUES (?,?)", batch
                )
                batch = []
        if batch:
            conn.executemany(
                "INSERT INTO members(entity_id, payload) VALUES (?,?)", batch
            )
        conn.commit()
    except Exception:
        conn.close()
        spill.unlink(missing_ok=True)
        raise
    return spill, conn


def _arrow_schema_from_members(conn: sqlite3.Connection) -> pa.Schema:
    schema: pa.Schema | None = None
    batch: list[dict[str, Any]] = []
    for (blob,) in conn.execute("SELECT payload FROM members ORDER BY entity_id"):
        batch.append(dict(pickle.loads(blob)))
        if len(batch) >= _MEMBER_BATCH_SIZE:
            table = pa.Table.from_pylist(batch)
            schema = table.schema if schema is None else pa.unify_schemas([schema, table.schema])
            batch = []
    if batch:
        table = pa.Table.from_pylist(batch)
        schema = table.schema if schema is None else pa.unify_schemas([schema, table.schema])
    if schema is None:
        return pa.schema([])
    return schema


def _write_parquet_zstd_from_conn(path: Path, conn: sqlite3.Connection) -> str:
    return _write_members_parquet_from_conn(path, conn, compression="zstd")


def _write_members_parquet_from_conn(
    path: Path,
    conn: sqlite3.Connection,
    *,
    compression: str | None = "zstd",
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    schema = _arrow_schema_from_members(conn)
    writer: pq.ParquetWriter | None = None
    try:
        batch: list[dict[str, Any]] = []
        for (blob,) in conn.execute("SELECT payload FROM members ORDER BY entity_id"):
            batch.append(dict(pickle.loads(blob)))
            if len(batch) >= _MEMBER_BATCH_SIZE:
                table = pa.Table.from_pylist(batch, schema=schema)
                if writer is None:
                    kwargs: dict[str, Any] = {}
                    if compression == "zstd":
                        kwargs = {"compression": "zstd", "compression_level": 3}
                    writer = pq.ParquetWriter(tmp, schema, **kwargs)
                writer.write_table(table)
                batch = []
        if batch:
            table = pa.Table.from_pylist(batch, schema=schema)
            if writer is None:
                kwargs = {}
                if compression == "zstd":
                    kwargs = {"compression": "zstd", "compression_level": 3}
                writer = pq.ParquetWriter(tmp, schema, **kwargs)
            writer.write_table(table)
        if writer is None:
            write_kwargs: dict[str, Any] = {}
            if compression == "zstd":
                write_kwargs = {"compression": "zstd", "compression_level": 3}
            pq.write_table(schema.empty_table(), tmp, **write_kwargs)
    finally:
        if writer is not None:
            writer.close()
    digest = _sha256_file_streaming(tmp)
    tmp.replace(path)
    return digest


def write_snapshot_unit(
    data_root: Path,
    *,
    utc_day: str,
    dataset_manifest_id: str,
    rows: Sequence[Mapping[str, Any]] | Iterator[Mapping[str, Any]],
) -> dict[str, Any]:
    spill, conn = _spill_member_sequence(rows)
    try:
        return _write_snapshot_unit_from_conn(
            data_root,
            utc_day=utc_day,
            dataset_manifest_id=dataset_manifest_id,
            conn=conn,
        )
    finally:
        conn.close()
        spill.unlink(missing_ok=True)


def _write_snapshot_unit_from_conn(
    data_root: Path,
    *,
    utc_day: str,
    dataset_manifest_id: str,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    unit_dir = data_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    rel = f"datasets/members_snapshot_plus_delta/{utc_day}/snapshot/{dataset_manifest_id}/members.parquet"
    path = data_root / rel
    file_sha256 = _write_parquet_zstd_from_conn(path, conn)
    row_count = int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
    fingerprint = _fingerprint_sqlite(conn)
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
                "row_count": row_count,
                "snapshot_fingerprint": fingerprint,
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
    rows: Sequence[Mapping[str, Any]] | Iterator[Mapping[str, Any]] | None = None,
    member_conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    unit_dir = data_root / "datasets" / "members_snapshot_plus_delta" / utc_day
    unit_path = unit_dir / "unit.json"
    if unit_path.is_file() is False:
        raise MembersDeltaError("ANCHOR_MISSING")
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    if not isinstance(unit, dict) or unit.get("layout") != LAYOUT_KIND:
        raise MembersDeltaError("UNIT_LAYOUT_INVALID")
    previous_id = str(unit["publications"][-1]["dataset_manifest_id"])
    previous_fp = str(unit["publications"][-1]["snapshot_fingerprint"])
    prev_spill, prev_conn = _reconstruct_to_sqlite(data_root, unit, previous_id)
    owned_curr = member_conn is None
    if owned_curr:
        if rows is None:
            raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
        curr_spill, curr_conn = _spill_member_sequence(rows)
    else:
        curr_spill = None
        curr_conn = member_conn
    replay_spill: Path | None = None
    replay_conn: sqlite3.Connection | None = None
    try:
        observed_prev = _fingerprint_sqlite(prev_conn)
        if observed_prev != previous_fp:
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        delta = _diff_sqlite_members(prev_conn, curr_conn)
        current_fp = _fingerprint_sqlite(curr_conn)
        current_count = int(curr_conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
        previous_count = int(prev_conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
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
                "previous_row_count": previous_count,
                "current_row_count": current_count,
            },
        }
        seq = int(unit["publications"][-1]["seq"]) + 1
        rel = (
            f"datasets/members_snapshot_plus_delta/{utc_day}/deltas/"
            f"{seq:04d}-{dataset_manifest_id}/members.parquet"
        )
        path = data_root / rel
        digest = persist_delta_payload(path, delta_payload)
        replay_spill, replay_conn = _clone_members_db(prev_conn)
        _apply_delta_sqlite(replay_conn, delta_payload)
        if _fingerprint_sqlite(replay_conn) != current_fp:
            raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
        unit["publications"].append(
            {
                "seq": seq,
                "dataset_manifest_id": dataset_manifest_id,
                "kind": "delta",
                "rel": rel.replace("\\", "/"),
                "sha256": digest,
                "row_count": current_count,
                "snapshot_fingerprint": current_fp,
                "delta_schema_version": DELTA_SCHEMA_VERSION_V2,
            }
        )
        _write_unit(unit_path, unit)
        _write_layout_sidecar(path, unit, dataset_manifest_id)
        return unit
    finally:
        prev_conn.close()
        prev_spill.unlink(missing_ok=True)
        if owned_curr:
            curr_conn.close()
            if curr_spill is not None:
                curr_spill.unlink(missing_ok=True)
        if replay_conn is not None:
            replay_conn.close()
        if replay_spill is not None:
            replay_spill.unlink(missing_ok=True)


def _diff_sqlite_members(
    prev_conn: sqlite3.Connection,
    curr_conn: sqlite3.Connection,
) -> dict[str, list[Any]]:
    curr_ids: set[str] = set()
    added: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for entity_id, blob in curr_conn.execute("SELECT entity_id, payload FROM members"):
        entity = str(entity_id)
        curr_ids.add(entity)
        curr_row = dict(pickle.loads(blob))
        loaded = prev_conn.execute(
            "SELECT payload FROM members WHERE entity_id=?", (entity,)
        ).fetchone()
        if loaded is None:
            added.append(curr_row)
            continue
        prev_row = dict(pickle.loads(loaded[0]))
        if row_fingerprint(curr_row) != row_fingerprint(prev_row):
            changed.append(curr_row)
    removed: list[dict[str, str]] = []
    for entity_id, blob in prev_conn.execute("SELECT entity_id, payload FROM members"):
        entity = str(entity_id)
        if entity in curr_ids:
            continue
        removed.append(
            {
                "entity_id": entity,
                "fingerprint": row_fingerprint(dict(pickle.loads(blob))),
            }
        )
    return {"added": added, "changed": changed, "removed": removed}


def _clone_members_db(conn: sqlite3.Connection) -> tuple[Path, sqlite3.Connection]:
    spill, clone = _spill_members_db()
    try:
        batch: list[tuple[str, bytes]] = []
        for entity_id, blob in conn.execute("SELECT entity_id, payload FROM members"):
            batch.append((str(entity_id), blob))
            if len(batch) >= _MEMBER_BATCH_SIZE:
                clone.executemany(
                    "INSERT INTO members(entity_id, payload) VALUES (?,?)", batch
                )
                batch = []
        if batch:
            clone.executemany(
                "INSERT INTO members(entity_id, payload) VALUES (?,?)", batch
            )
        clone.commit()
    except Exception:
        clone.close()
        spill.unlink(missing_ok=True)
        raise
    return spill, clone


def _sha256_file_streaming(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _spill_members_db() -> tuple[Path, sqlite3.Connection]:
    handle, name = tempfile.mkstemp(prefix="members-delta-", suffix=".sqlite")
    os.close(handle)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE members (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT NOT NULL UNIQUE,
            payload BLOB NOT NULL
        )
        """
    )
    return path, conn


def _load_anchor_into_sqlite(conn: sqlite3.Connection, snapshot_path: Path) -> None:
    pf = pq.ParquetFile(snapshot_path)
    for batch in pf.iter_batches(batch_size=_MEMBER_BATCH_SIZE):
        rows = []
        for row in batch.to_pylist():
            payload = dict(row)
            entity_id = str(payload.get("entity_id") or "")
            if not entity_id:
                raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
            rows.append((entity_id, pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)))
        conn.executemany("INSERT INTO members(entity_id, payload) VALUES (?,?)", rows)
    conn.commit()


def _apply_delta_sqlite(
    conn: sqlite3.Connection,
    delta: Mapping[str, Any],
    *,
    removed_out: list[dict[str, Any]] | None = None,
    removed_at_seq: int | None = None,
) -> None:
    for item in delta.get("removed") or []:
        entity_id = str(item.get("entity_id") or "")
        loaded = conn.execute(
            "SELECT payload FROM members WHERE entity_id=?", (entity_id,)
        ).fetchone()
        if loaded is None:
            raise MembersDeltaError("DELTA_REMOVE_MISSING")
        current = pickle.loads(loaded[0])
        if row_fingerprint(current) != str(item.get("fingerprint") or ""):
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        if removed_out is not None:
            payload = dict(current)
            if removed_at_seq is not None:
                payload["_delta_removed_at_seq"] = int(removed_at_seq)
            removed_out.append(payload)
        conn.execute("DELETE FROM members WHERE entity_id=?", (entity_id,))
    for row in list(delta.get("changed") or []) + list(delta.get("added") or []):
        payload = dict(row)
        entity_id = str(payload.get("entity_id") or "")
        if not entity_id:
            raise MembersDeltaError("MEMBER_ENTITY_ID_REQUIRED")
        conn.execute(
            "INSERT OR REPLACE INTO members(entity_id, payload) VALUES (?,?)",
            (entity_id, pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)),
        )
    conn.commit()


def _fingerprint_sqlite(conn: sqlite3.Connection) -> str:
    """Same digest as snapshot_fingerprint, without materializing the census list."""
    _FINGERPRINT_WORK["snapshot_fingerprint"] += 1
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    for (blob,) in conn.execute("SELECT payload FROM members ORDER BY entity_id"):
        encoded = json.dumps(
            dict(pickle.loads(blob)),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if not first:
            digest.update(b",")
        first = False
        digest.update(encoded)
    digest.update(b"]")
    return digest.hexdigest()


def _reconstruct_to_sqlite(
    data_root: Path,
    unit: Mapping[str, Any],
    dataset_manifest_id: str,
    *,
    removed_out: list[dict[str, Any]] | None = None,
) -> tuple[Path, sqlite3.Connection]:
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
    observed = _sha256_file_streaming(snapshot_path)
    if observed != str(anchor.get("sha256") or ""):
        raise MembersDeltaError("DELTA_HASH_MISMATCH")
    spill, conn = _spill_members_db()
    try:
        _load_anchor_into_sqlite(conn, snapshot_path)
        n_rows = int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
        _RECONSTRUCT_STATS["reconstruct_calls"] += 1
        if n_rows > _RECONSTRUCT_STATS["peak_sqlite_rows"]:
            _RECONSTRUCT_STATS["peak_sqlite_rows"] = n_rows
        running_fp = _fingerprint_sqlite(conn)
        if running_fp != str(anchor.get("snapshot_fingerprint") or ""):
            raise MembersDeltaError("DELTA_HASH_MISMATCH")
        previous_id = str(anchor.get("dataset_manifest_id") or "")
        reached = previous_id == dataset_manifest_id
        if not reached:
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
                file_sha = _sha256_file_streaming(path)
                if file_sha != str(item.get("sha256") or ""):
                    raise MembersDeltaError("DELTA_HASH_MISMATCH")
                payload = path.read_bytes() if path.suffix == ".json" else b""
                delta = _read_delta_payload(path, payload)
                schema_version = str(delta.get("schema_version") or DELTA_SCHEMA_VERSION_V1)
                if schema_version not in SUPPORTED_DELTA_SCHEMA_VERSIONS:
                    raise MembersDeltaError("DELTA_SCHEMA_UNSUPPORTED")
                if str(delta.get("previous_dataset_manifest_id") or "") != previous_id:
                    raise MembersDeltaError("DELTA_SEQUENCE_INVALID")
                if str(delta.get("dataset_manifest_id") or "") != str(
                    item.get("dataset_manifest_id") or ""
                ):
                    raise MembersDeltaError("DELTA_SEQUENCE_INVALID")
                if str(delta.get("previous_fingerprint") or "") != running_fp:
                    raise MembersDeltaError("DELTA_HASH_MISMATCH")
                _apply_delta_sqlite(
                    conn, delta, removed_out=removed_out, removed_at_seq=item_seq
                )
                n_rows = int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
                if n_rows > _RECONSTRUCT_STATS["peak_sqlite_rows"]:
                    _RECONSTRUCT_STATS["peak_sqlite_rows"] = n_rows
                unit_fp = str(item.get("snapshot_fingerprint") or "")
                current_fp = str(delta.get("current_fingerprint") or "")
                is_target = str(item.get("dataset_manifest_id") or "") == dataset_manifest_id
                if schema_version == DELTA_SCHEMA_VERSION_V2:
                    if not current_fp:
                        raise MembersDeltaError("DELTA_CORRUPT")
                    if unit_fp and current_fp != unit_fp:
                        raise MembersDeltaError("DELTA_HASH_MISMATCH")
                if is_target:
                    observed_fp = _fingerprint_sqlite(conn)
                    if unit_fp and observed_fp != unit_fp:
                        raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
                    if schema_version == DELTA_SCHEMA_VERSION_V2 and observed_fp != current_fp:
                        raise MembersDeltaError("DELTA_REPLAY_MISMATCH")
                    reached = True
                    break
                running_fp = current_fp or unit_fp
                if not running_fp:
                    raise MembersDeltaError("DELTA_CORRUPT")
                previous_id = str(item.get("dataset_manifest_id") or "")
        if not reached:
            raise MembersDeltaError("PUBLICATION_NOT_IN_UNIT")
        return spill, conn
    except Exception:
        conn.close()
        spill.unlink(missing_ok=True)
        raise


def iter_reconstructed_publication_batches(
    data_root: Path,
    unit: Mapping[str, Any],
    dataset_manifest_id: str,
    *,
    columns: Sequence[str] | None = None,
    batch_size: int = _MEMBER_BATCH_SIZE,
    removed_out: list[dict[str, Any]] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Replay SNAPSHOT_PLUS_DELTA into process-owned SQLite; yield bounded batches."""
    spill, conn = _reconstruct_to_sqlite(
        data_root, unit, dataset_manifest_id, removed_out=removed_out
    )
    try:
        batch: list[dict[str, Any]] = []
        for (blob,) in conn.execute("SELECT payload FROM members ORDER BY entity_id"):
            row = pickle.loads(blob)
            if columns is None:
                batch.append(dict(row))
            else:
                batch.append({key: row.get(key) for key in columns})
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        conn.close()
        spill.unlink(missing_ok=True)


def iter_spilled_member_rows(
    conn: sqlite3.Connection,
) -> Iterator[dict[str, Any]]:
    for (blob,) in conn.execute("SELECT payload FROM members ORDER BY seq"):
        yield dict(pickle.loads(blob))


def reconstruct_publication(
    data_root: Path,
    unit: Mapping[str, Any],
    dataset_manifest_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in iter_reconstructed_publication_batches(
        data_root, unit, dataset_manifest_id
    ):
        rows.extend(batch)
    return rows


def publication_seq_for_location(
    data_root: Path, logical_location: str, layout: Mapping[str, Any] | None
) -> int | None:
    if not isinstance(layout, Mapping):
        return None
    unit_rel = str(layout.get("unit_rel") or "")
    manifest = str(layout.get("dataset_manifest_id") or "")
    if not unit_rel or not manifest:
        return None
    unit_path = Path(data_root) / unit_rel
    if not unit_path.is_file():
        return None
    try:
        unit = json.loads(unit_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(unit, Mapping):
        return None
    for item in unit.get("publications") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("dataset_manifest_id") or "") != manifest:
            continue
        try:
            return int(item.get("seq"))
        except (TypeError, ValueError):
            return None
    return None


def read_member_layout(data_root: Path, logical_location: str) -> dict[str, Any] | None:
    sidecar = (Path(data_root) / logical_location).with_name("members.layout.json")
    if not sidecar.is_file() or sidecar.is_symlink():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def iter_member_row_batches_for_location(
    data_root: Path,
    logical_location: str,
    *,
    columns: Sequence[str] | None = None,
    batch_size: int = _MEMBER_BATCH_SIZE,
    removed_out: list[dict[str, Any]] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Yield bounded member-row dict batches. Delta layout reconstructs via SQLite spill."""
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
            yield from iter_reconstructed_publication_batches(
                data_root,
                unit,
                str(layout.get("dataset_manifest_id") or ""),
                columns=columns,
                batch_size=batch_size,
                removed_out=removed_out,
            )
            return
        if kind != LEGACY_KIND:
            raise MembersDeltaError("UNIT_LAYOUT_INVALID")
    if path.is_file() is False:
        raise MembersDeltaError("MEMBER_FILE_MISSING")
    pf = pq.ParquetFile(path)
    names = list(pf.schema_arrow.names)
    if "entity_id" not in names:
        raise MembersDeltaError("LAYOUT_SIDECAR_MISSING")
    use_cols = None
    if columns is not None:
        use_cols = [name for name in columns if name in names]
        if not use_cols:
            return
    for batch in pf.iter_batches(batch_size=batch_size, columns=use_cols):
        yield batch.to_pylist()


def load_member_rows_for_location(data_root: Path, logical_location: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for batch in iter_member_row_batches_for_location(data_root, logical_location):
        out.extend(batch)
    return out


def persist_delta_payload(path: Path, delta_payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(delta_payload, sort_keys=True, separators=(",", ":"))
    table = pa.table({"delta_json": [encoded]})
    tmp = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=3)
    digest = _sha256_file_streaming(tmp)
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
