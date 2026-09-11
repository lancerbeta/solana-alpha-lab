"""Memory-bounded live cohort source bundle (manifest + parquet partitions).

Process-owned staging is not scientific truth. Hash large files by streaming.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.run_passport import canonical_sha256

SOURCE_BUNDLE_SCHEMA = "smial.live-cohort-source-bundle"
SOURCE_BUNDLE_SCHEMA_VERSION = "1.0"
SOURCE_REPRESENTATION_BUNDLE = "SOURCE_BUNDLE_V1"
SOURCE_REPRESENTATION_LEGACY_JSON = "LEGACY_SOURCE_SNAPSHOT_JSON"
SOURCE_MANIFEST_NAME = "source_manifest.json"
SOURCE_MEMBERS_NAME = "members.parquet"
SOURCE_OBSERVATIONS_NAME = "observations.parquet"
SOURCE_STAGING_PREFIX = ".build-"
BATCH_SIZE = 2048
HASH_CHUNK = 1024 * 1024
DEFAULT_AS_LIMIT_BYTES = 4096 * 1024 * 1024
SOURCE_BUILD_RSS_CEILING_BYTES = 1250 * 1024 * 1024
SOURCE_BUILD_WORKER_ENV = "LIVE_COHORT_SOURCE_BUILD_WORKER"
SOURCE_BUILD_AS_LIMIT_ENV = "LIVE_COHORT_SOURCE_BUILD_AS_LIMIT_BYTES"

PARQUET_WRITE_KWARGS: dict[str, Any] = {
    "compression": "zstd",
    "compression_level": 3,
    "use_dictionary": False,
    "write_statistics": True,
    "version": "2.6",
    "data_page_version": "1.0",
    "row_group_size": 65536,
    "coerce_timestamps": "us",
    "allow_truncated_timestamps": False,
    "store_schema": True,
}

RELEASE_PARQUET_WRITE_KWARGS: dict[str, Any] = {
    "compression": "NONE",
    "use_dictionary": False,
    "write_statistics": True,
    "version": "2.6",
    "data_page_version": "1.0",
    "row_group_size": 65536,
    "coerce_timestamps": "us",
    "allow_truncated_timestamps": False,
    "store_schema": True,
}

_EXTRACTION_COUNTERS = {
    "full_member_row_materializations": 0,
    "member_snapshot_full_column_scans": 0,
    "member_snapshot_admission_probes": 0,
    "member_parquet_files_opened": 0,
    "observation_panel_rows_decoded": 0,
}


def reset_extraction_counters() -> None:
    for key in _EXTRACTION_COUNTERS:
        _EXTRACTION_COUNTERS[key] = 0


def extraction_counters() -> dict[str, int]:
    return dict(_EXTRACTION_COUNTERS)


def note_member_file_open() -> None:
    _EXTRACTION_COUNTERS["member_parquet_files_opened"] += 1


def note_member_full_column_scan() -> None:
    _EXTRACTION_COUNTERS["member_snapshot_full_column_scans"] += 1


def note_full_member_rows(count: int) -> None:
    _EXTRACTION_COUNTERS["full_member_row_materializations"] += int(count)


def note_admission_probe_rows(count: int) -> None:
    _EXTRACTION_COUNTERS["member_snapshot_admission_probes"] += int(count)


def note_observation_rows(count: int) -> None:
    _EXTRACTION_COUNTERS["observation_panel_rows_decoded"] += int(count)


def sha256_file_streaming(path: Path, *, chunk_size: int = HASH_CHUNK) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_files_concat_streaming(paths: Sequence[Path], *, chunk_size: int = HASH_CHUNK) -> str:
    digest = hashlib.sha256()
    for path in paths:
        with Path(path).open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    return digest.hexdigest()


def parquet_row_count(path: Path) -> int:
    return int(pq.ParquetFile(path).metadata.num_rows)


def peak_rss_bytes() -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi")
        get_current = kernel32.GetCurrentProcess
        get_current.restype = wintypes.HANDLE
        get_info = psapi.GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        if not get_info(get_current(), ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)
    import resource

    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return rss
    return rss * 1024


def source_build_child_was_resource_killed(returncode: int) -> bool:
    """True only for SIGKILL/SIGSEGV-class OOM of the isolated builder."""
    return int(returncode) in {-9, -11, 137, 139}


def apply_source_build_address_limit(limit_bytes: int | None = None) -> int | None:
    """Fail the build process before host OOM. Linux RLIMIT_AS; no-op elsewhere.

    The cap is virtual address space, not RSS. PyArrow needs headroom above
    the 1.25 GiB RSS ceiling; 1.5 GiB AS aborts tiny publishes with SIGABRT.
    """
    if os.name != "posix":
        return None
    import resource

    raw = os.environ.get(SOURCE_BUILD_AS_LIMIT_ENV)
    if limit_bytes is None:
        if raw == "0":
            return None
        limit_bytes = int(raw) if raw else DEFAULT_AS_LIMIT_BYTES
    if int(limit_bytes) <= 0:
        return None
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    return limit_bytes


def cohort_source_dir(observation_rdp_root: Path, cohort_id: str) -> Path:
    return Path(observation_rdp_root) / "live_observation_rebuild" / f"cohort={cohort_id}"


def source_manifest_path(observation_rdp_root: Path, cohort_id: str) -> Path:
    return cohort_source_dir(observation_rdp_root, cohort_id) / SOURCE_MANIFEST_NAME


def iter_parquet_row_batches(
    path: Path,
    *,
    columns: Sequence[str] | None = None,
    batch_size: int = BATCH_SIZE,
) -> Iterator[list[dict[str, Any]]]:
    pf = pq.ParquetFile(path)
    names = list(pf.schema_arrow.names)
    use_cols = None
    if columns is not None:
        use_cols = [name for name in columns if name in names]
        if not use_cols:
            return
    for batch in pf.iter_batches(batch_size=batch_size, columns=use_cols):
        yield batch.to_pylist()


def write_parquet_from_rows(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    schema: pa.Schema | None = None,
    write_kwargs: Mapping[str, Any] | None = None,
) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    options = dict(write_kwargs or PARQUET_WRITE_KWARGS)
    if not rows:
        if schema is None:
            raise ValueError("empty parquet write requires schema")
        table = schema.empty_table()
        pq.write_table(table, path, **options)
        return 0
    table = pa.Table.from_pylist([dict(row) for row in rows], schema=schema)
    pq.write_table(table, path, **options)
    return table.num_rows


def _writer_kwargs(write_kwargs: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "compression",
        "compression_level",
        "use_dictionary",
        "write_statistics",
        "version",
        "data_page_version",
        "coerce_timestamps",
        "allow_truncated_timestamps",
        "store_schema",
    }
    return {key: value for key, value in write_kwargs.items() if key in allowed}


def write_parquet_from_row_batches(
    path: Path,
    batches: Iterator[Sequence[Mapping[str, Any]]],
    *,
    schema: pa.Schema,
    write_kwargs: Mapping[str, Any] | None = None,
) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    options = dict(write_kwargs or PARQUET_WRITE_KWARGS)
    writer: pq.ParquetWriter | None = None
    total = 0
    try:
        for batch in batches:
            if not batch:
                continue
            table = pa.Table.from_pylist([dict(row) for row in batch], schema=schema)
            if writer is None:
                writer = pq.ParquetWriter(path, schema, **_writer_kwargs(options))
            writer.write_table(table)
            total += table.num_rows
        if writer is None:
            pq.write_table(schema.empty_table(), path, **options)
            return 0
    finally:
        if writer is not None:
            writer.close()
    return total


def spill_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=FILE")
    return conn


def new_staging_dir(source_dir: Path) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    staging = source_dir / f"{SOURCE_STAGING_PREFIX}{secrets.token_hex(8)}"
    staging.mkdir(parents=False, exist_ok=False)
    return staging


def discard_stale_staging(source_dir: Path, *, keep: Path | None = None) -> None:
    if not source_dir.is_dir():
        return
    for item in source_dir.iterdir():
        if not item.is_dir():
            continue
        if not item.name.startswith(SOURCE_STAGING_PREFIX):
            continue
        if keep is not None and item.resolve() == keep.resolve():
            continue
        shutil.rmtree(item, ignore_errors=True)


def commit_source_bundle(
    *,
    source_dir: Path,
    staging: Path,
    manifest: Mapping[str, Any],
) -> Path:
    """Publish parquet then the small manifest last. Incomplete trees are not valid."""
    dest = Path(source_dir)
    dest.mkdir(parents=True, exist_ok=True)
    members_src = staging / SOURCE_MEMBERS_NAME
    obs_src = staging / SOURCE_OBSERVATIONS_NAME
    if not members_src.is_file() or not obs_src.is_file():
        raise OSError("SOURCE_BUNDLE_STAGING_INCOMPLETE")
    committed = dest / SOURCE_MANIFEST_NAME
    if committed.is_file() and not committed.is_symlink():
        try:
            existing = json.loads(committed.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, Mapping) and existing.get("source_sha256") == manifest.get(
            "source_sha256"
        ):
            try:
                members_ok = sha256_file_streaming(dest / SOURCE_MEMBERS_NAME) == existing.get(
                    "members_sha256"
                )
                obs_ok = sha256_file_streaming(dest / SOURCE_OBSERVATIONS_NAME) == existing.get(
                    "observations_sha256"
                )
            except OSError:
                members_ok = False
                obs_ok = False
            if members_ok and obs_ok:
                discard_stale_staging(dest)
                return committed
    os.replace(members_src, dest / SOURCE_MEMBERS_NAME)
    os.replace(obs_src, dest / SOURCE_OBSERVATIONS_NAME)
    manifest_bytes = json.dumps(
        dict(manifest), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    tmp_manifest = staging / SOURCE_MANIFEST_NAME
    tmp_manifest.write_bytes(manifest_bytes)
    os.replace(tmp_manifest, dest / SOURCE_MANIFEST_NAME)
    shutil.rmtree(staging, ignore_errors=True)
    discard_stale_staging(dest)
    return dest / SOURCE_MANIFEST_NAME


def compute_source_identity(manifest_body: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "schema": SOURCE_BUNDLE_SCHEMA,
            "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION,
            "schedule_sha256": manifest_body.get("schedule_sha256"),
            "activation_id": manifest_body.get("activation_id"),
            "cohort_id": manifest_body.get("cohort_id"),
            "window_start": manifest_body.get("window_start"),
            "window_end_exclusive": manifest_body.get("window_end_exclusive"),
            "starts_at": manifest_body.get("starts_at"),
            "stops_admitting_at": manifest_body.get("stops_admitting_at"),
            "closure_receipt_sha256": manifest_body.get("closure_receipt_sha256"),
            "closure_cutoff_at": manifest_body.get("closure_cutoff_at"),
            "discovery_coverage_class": manifest_body.get("discovery_coverage_class"),
            "member_count": manifest_body.get("member_count"),
            "observation_count": manifest_body.get("observation_count"),
            "members_sha256": manifest_body.get("members_sha256"),
            "observations_sha256": manifest_body.get("observations_sha256"),
            "contributing_producer_git_shas": manifest_body.get(
                "contributing_producer_git_shas"
            ),
            "schedule_producer_git_sha": manifest_body.get("schedule_producer_git_sha"),
            "admission_field": manifest_body.get("admission_field"),
            "open_publication": manifest_body.get("open_publication"),
            "unresolved_due": manifest_body.get("unresolved_due"),
            "in_flight": manifest_body.get("in_flight"),
            "budget_blocked": manifest_body.get("budget_blocked"),
        }
    )


def compact_source_view(source: Mapping[str, Any]) -> dict[str, Any]:
    out = {
        key: value
        for key, value in dict(source).items()
        if key not in {"members", "observations"}
    }
    out["source_representation"] = str(
        source.get("source_representation") or SOURCE_REPRESENTATION_BUNDLE
    )
    return out


MEMBER_COLUMNS = (
    "mint",
    "entity_id",
    "activation_id",
    "discovery_first_reliable_available_at",
    "authoritative_anchor",
    "candidate_state",
    "membership_state",
    "denominator_state",
    "sampling_policy",
    "sampling_seed",
    "inclusion_probability",
    "selected_or_excluded",
    "exclusion_reason",
    "source_request_sha256",
    "source_response_sha256",
    "discovery_coverage_class",
)
MEMBER_SCHEMA = pa.schema([pa.field(name, pa.string()) for name in MEMBER_COLUMNS])

OBSERVATION_COLUMNS = (
    "mint",
    "entity_id",
    "point_id",
    "primitive_id",
    "field_id",
    "value_kind",
    "typed_value",
    "state",
    "missing_reason",
    "event_time",
    "request_started_at",
    "response_received_at",
    "first_reliable_available_at",
    "request_sha256",
    "response_sha256",
    "call_occurrence_id",
    "http_status",
    "http_class",
)
OBSERVATION_SCHEMA = pa.schema(
    [
        pa.field("mint", pa.string()),
        pa.field("entity_id", pa.string()),
        pa.field("point_id", pa.string()),
        pa.field("primitive_id", pa.string()),
        pa.field("field_id", pa.string()),
        pa.field("value_kind", pa.string()),
        pa.field("typed_value", pa.string()),
        pa.field("state", pa.string()),
        pa.field("missing_reason", pa.string()),
        pa.field("event_time", pa.string()),
        pa.field("request_started_at", pa.string()),
        pa.field("response_received_at", pa.string()),
        pa.field("first_reliable_available_at", pa.string()),
        pa.field("request_sha256", pa.string()),
        pa.field("response_sha256", pa.string()),
        pa.field("call_occurrence_id", pa.string()),
        pa.field("http_status", pa.string()),
        pa.field("http_class", pa.string()),
    ]
)


def row_for_member_parquet(row: Mapping[str, Any]) -> dict[str, str | None]:
    return {name: _as_optional_str(row.get(name)) for name in MEMBER_COLUMNS}


def row_for_observation_parquet(row: Mapping[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in OBSERVATION_COLUMNS:
        value = row.get(name)
        if name == "typed_value" and value is not None and not isinstance(value, str):
            out[name] = json.dumps(value, sort_keys=True)
        elif name == "http_status" and value is not None:
            out[name] = str(value)
        else:
            out[name] = _as_optional_str(value)
    return out


def member_from_parquet_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = {name: _empty_to_none(row.get(name)) for name in MEMBER_COLUMNS}
    out["mint"] = str(row.get("mint") or row.get("entity_id") or "")
    out["entity_id"] = str(row.get("entity_id") or row.get("mint") or "")
    return out


def observation_from_parquet_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in OBSERVATION_COLUMNS:
        out[name] = _empty_to_none(row.get(name))
    status = row.get("http_status")
    if status not in (None, ""):
        try:
            out["http_status"] = int(status)
        except (TypeError, ValueError):
            out["http_status"] = status
    return out


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _empty_to_none(value: Any) -> Any:
    if value is None or value == "":
        return None
    return value


CENSUS_RELEASE_COLUMNS = (
    "release_id",
    "cohort_id",
    "source_schedule_sha256",
    "activation_id",
    "producer_git_sha",
    "mint",
    "discovery_first_reliable_available_at",
    "authoritative_anchor",
    "candidate_state",
    "membership_state",
    "denominator_state",
    "sampling_policy",
    "sampling_seed",
    "inclusion_probability",
    "selected_or_excluded",
    "exclusion_reason",
    "discovery_coverage_class",
    "source_request_sha256",
    "source_response_sha256",
    "evidence_role",
)
CENSUS_RELEASE_SCHEMA = pa.schema(
    [pa.field(name, pa.string()) for name in CENSUS_RELEASE_COLUMNS]
)

OBS_RELEASE_SCHEMA = pa.schema(
    [
        pa.field("release_id", pa.string()),
        pa.field("cohort_id", pa.string()),
        pa.field("mint", pa.string()),
        pa.field("point_id", pa.string()),
        pa.field("primitive_id", pa.string()),
        pa.field("field_id", pa.string()),
        pa.field("value_kind", pa.string()),
        pa.field("typed_value", pa.string()),
        pa.field("state", pa.string()),
        pa.field("missing_reason", pa.string()),
        pa.field("event_time", pa.string()),
        pa.field("request_started_at", pa.string()),
        pa.field("response_received_at", pa.string()),
        pa.field("first_reliable_available_at", pa.string()),
        pa.field("request_sha256", pa.string()),
        pa.field("response_sha256", pa.string()),
        pa.field("call_occurrence_id", pa.string()),
        pa.field("http_status", pa.int64()),
        pa.field("http_class", pa.string()),
        pa.field("evidence_role", pa.string()),
        pa.field("confirmatory_reuse_forbidden", pa.bool_()),
    ]
)
