"""LIVE CORPUS local logical-row identity for census/observations parquet.

Current release writer and frozen stored-partition projections are distinct.
Only CENSUS-20, OBS-21 and OBS-24 are supported. Streaming / bounded-memory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from numbers import Integral
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.live_cohort_source_bundle import (
    BATCH_SIZE,
    CENSUS_RELEASE_SCHEMA,
    OBS_RELEASE_SCHEMA,
    iter_parquet_row_batches,
    parquet_row_count,
    sha256_file_streaming,
    write_parquet_from_row_batches,
)

LOGICAL_ROW_PROFILE = "smial-live-corpus-logical-rows-v1"
SCHEMA_PROFILE = "smial-live-corpus-schema-v1"
VALIDATION_RECEIPT_SCHEMA = "smial.live-corpus-dataset-validation-receipt"
VALIDATION_RECEIPT_SCHEMA_VERSION = "1.0"
CANONICAL_METADATA_SUFFIX = ".canonical-v1"
KIND_CENSUS = "CENSUS"
KIND_OBS = "OBS"

# Frozen layouts, not a projection of a future writer schema. In particular,
# ABSENT legacy clock columns and explicit current NULL columns hash differently.
CENSUS20_SCHEMA = pa.schema([(name, pa.string()) for name in (
    "release_id", "cohort_id", "source_schedule_sha256", "activation_id",
    "producer_git_sha", "mint", "discovery_first_reliable_available_at",
    "authoritative_anchor", "candidate_state", "membership_state",
    "denominator_state", "sampling_policy", "sampling_seed",
    "inclusion_probability", "selected_or_excluded", "exclusion_reason",
    "discovery_coverage_class", "source_request_sha256", "source_response_sha256",
    "evidence_role",
)])
OBS21_SCHEMA = pa.schema([
    ("release_id", pa.string()), ("cohort_id", pa.string()), ("mint", pa.string()),
    ("point_id", pa.string()), ("primitive_id", pa.string()), ("field_id", pa.string()),
    ("value_kind", pa.string()), ("typed_value", pa.string()), ("state", pa.string()),
    ("missing_reason", pa.string()), ("event_time", pa.string()),
    ("request_started_at", pa.string()), ("response_received_at", pa.string()),
    ("first_reliable_available_at", pa.string()), ("request_sha256", pa.string()),
    ("response_sha256", pa.string()), ("call_occurrence_id", pa.string()),
    ("http_status", pa.int64()), ("http_class", pa.string()),
    ("evidence_role", pa.string()), ("confirmatory_reuse_forbidden", pa.bool_()),
])
OBS24_SCHEMA = pa.schema([
    ("release_id", pa.string()), ("cohort_id", pa.string()), ("mint", pa.string()),
    ("point_id", pa.string()), ("primitive_id", pa.string()), ("field_id", pa.string()),
    ("value_kind", pa.string()), ("typed_value", pa.string()), ("state", pa.string()),
    ("missing_reason", pa.string()), ("event_time", pa.string()),
    ("request_started_at", pa.string()), ("response_received_at", pa.string()),
    ("first_reliable_available_at", pa.string()), ("request_sha256", pa.string()),
    ("response_sha256", pa.string()), ("call_occurrence_id", pa.string()),
    ("http_status", pa.int64()), ("http_class", pa.string()),
    ("observation_clock_policy", pa.string()), ("source_price_event_time", pa.string()),
    ("member_anchor", pa.string()), ("evidence_role", pa.string()),
    ("confirmatory_reuse_forbidden", pa.bool_()),
])


class LiveCorpusLogicalRowError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LiveCorpusLogicalRowError(code)


def _arrow_logical_type(field: pa.Field) -> str:
    if pa.types.is_string(field.type) or pa.types.is_large_string(field.type):
        return "string"
    if pa.types.is_int64(field.type):
        return "int64"
    if pa.types.is_boolean(field.type):
        return "bool"
    raise LiveCorpusLogicalRowError("LIVE_CORPUS_SCHEMA_TYPE_UNSUPPORTED")


def schema_field_projection(schema: pa.Schema) -> list[dict[str, Any]]:
    return [
        {
            "name": field.name,
            "nullable": bool(field.nullable),
            "type": _arrow_logical_type(field),
        }
        for field in schema
    ]


def live_corpus_schema_projection() -> dict[str, Any]:
    return {
        "census": schema_field_projection(CENSUS_RELEASE_SCHEMA),
        "logical_row_profile": LOGICAL_ROW_PROFILE,
        "observations": schema_field_projection(OBS_RELEASE_SCHEMA),
        "profile": SCHEMA_PROFILE,
        "schema_id": "SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
        "stored_partition_projections": {
            "CENSUS-20": schema_field_projection(CENSUS20_SCHEMA),
            "OBS-21": schema_field_projection(OBS21_SCHEMA),
            "OBS-24": schema_field_projection(OBS24_SCHEMA),
        },
    }


def select_stored_partition_projection(kind: str, physical_schema: pa.Schema) -> pa.Schema:
    """Exact fields/types/nullability; never guess a layout from row values."""
    _require(kind in {KIND_CENSUS, KIND_OBS}, "LIVE_CORPUS_PARTITION_KIND_INVALID")
    supported = (CENSUS20_SCHEMA,) if kind == KIND_CENSUS else (OBS21_SCHEMA, OBS24_SCHEMA)
    for frozen in supported:
        if physical_schema.equals(frozen, check_metadata=False):
            return frozen
    raise LiveCorpusLogicalRowError("LIVE_CORPUS_PARTITION_SCHEMA_UNSUPPORTED")


def live_corpus_schema_sha256() -> str:
    payload = json.dumps(
        live_corpus_schema_projection(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_value(value: Any, logical_type: str) -> Any:
    if value is None:
        return None
    if logical_type == "string":
        if isinstance(value, str):
            return value
        return str(value)
    if logical_type == "int64":
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise LiveCorpusLogicalRowError("LIVE_CORPUS_LOGICAL_ROW_TYPE_INVALID")
        return int(value)
    if logical_type == "bool":
        if not isinstance(value, bool):
            raise LiveCorpusLogicalRowError("LIVE_CORPUS_LOGICAL_ROW_TYPE_INVALID")
        return bool(value)
    raise LiveCorpusLogicalRowError("LIVE_CORPUS_SCHEMA_TYPE_UNSUPPORTED")


def _canonical_row_bytes(record: Mapping[str, Any], schema: pa.Schema) -> bytes:
    normalized: dict[str, Any] = {}
    for field in schema:
        logical_type = _arrow_logical_type(field)
        normalized[field.name] = _normalize_value(record.get(field.name), logical_type)
    try:
        text = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise LiveCorpusLogicalRowError("LIVE_CORPUS_LOGICAL_ROW_CANONICALIZATION_FAILED") from exc
    return text.encode("utf-8")


def _table_from_batch(batch: Sequence[Mapping[str, Any]], schema: pa.Schema) -> pa.Table:
    return pa.Table.from_pylist([dict(item) for item in batch], schema=schema)


def hash_logical_row_batches(
    batches: Iterator[Sequence[Mapping[str, Any]]],
    *,
    schema: pa.Schema,
) -> str:
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    for batch in batches:
        if not batch:
            continue
        table = _table_from_batch(batch, schema)
        for record in table.to_pylist():
            if not first:
                digest.update(b",")
            first = False
            digest.update(_canonical_row_bytes(record, schema))
    digest.update(b"]")
    return digest.hexdigest()


def hash_logical_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    schema: pa.Schema,
) -> str:
    def _batches() -> Iterator[Sequence[Mapping[str, Any]]]:
        batch: list[Mapping[str, Any]] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []
        if batch:
            yield batch

    return hash_logical_row_batches(_batches(), schema=schema)


def _parse_optional_utc(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _fold_bound(
    current_min: datetime | None,
    current_max: datetime | None,
    value: datetime,
) -> tuple[datetime | None, datetime | None]:
    if current_min is None or value < current_min:
        current_min = value
    if current_max is None or value > current_max:
        current_max = value
    return current_min, current_max


@dataclass(frozen=True, slots=True)
class LiveCorpusPartitionClaims:
    kind: str
    partition_id: str
    logical_location: str
    file_sha256: str
    content_sha256: str
    row_count: int
    min_event_time: datetime | None
    max_event_time: datetime | None
    min_available_to_strategy_at: datetime | None
    max_available_to_strategy_at: datetime | None

    def pit_payload(self) -> dict[str, str | None]:
        def _stamp(value: datetime | None) -> str | None:
            if value is None:
                return None
            return (
                value.astimezone(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )

        return {
            "max_available_to_strategy_at": _stamp(self.max_available_to_strategy_at),
            "max_event_time": _stamp(self.max_event_time),
            "min_available_to_strategy_at": _stamp(self.min_available_to_strategy_at),
            "min_event_time": _stamp(self.min_event_time),
        }


def measure_live_corpus_parquet(
    path: Path,
    *,
    kind: str,
    partition_id: str,
    logical_location: str,
    stored_claims: LiveCorpusPartitionClaims | None = None,
) -> LiveCorpusPartitionClaims:
    _require(kind in {KIND_CENSUS, KIND_OBS}, "LIVE_CORPUS_PARTITION_KIND_INVALID")
    parquet_path = Path(path)
    _require(parquet_path.is_file() and not parquet_path.is_symlink(), "LIVE_CORPUS_PARQUET_MISSING")
    schema = select_stored_partition_projection(kind, pq.ParquetFile(parquet_path).schema_arrow)
    file_sha256 = sha256_file_streaming(parquet_path)
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    min_event: datetime | None = None
    max_event: datetime | None = None
    min_available: datetime | None = None
    max_available: datetime | None = None
    event_representable = True
    available_representable = True
    row_count = 0
    for batch in iter_parquet_row_batches(parquet_path, batch_size=BATCH_SIZE):
        if not batch:
            continue
        table = _table_from_batch(batch, schema)
        records = table.to_pylist()
        row_count += len(records)
        for record in records:
            if not first:
                digest.update(b",")
            first = False
            digest.update(_canonical_row_bytes(record, schema))
            if kind == KIND_OBS:
                event = _parse_optional_utc(record.get("event_time"))
                if event is None:
                    event_representable = False
                else:
                    min_event, max_event = _fold_bound(min_event, max_event, event)
                available = _parse_optional_utc(record.get("first_reliable_available_at"))
                if available is None:
                    available_representable = False
                else:
                    min_available, max_available = _fold_bound(
                        min_available, max_available, available
                    )
            else:
                available = _parse_optional_utc(
                    record.get("discovery_first_reliable_available_at")
                )
                if available is None:
                    available_representable = False
                else:
                    min_available, max_available = _fold_bound(
                        min_available, max_available, available
                    )
    digest.update(b"]")
    counted = parquet_row_count(parquet_path)
    _require(counted == row_count, "LIVE_CORPUS_ROW_COUNT_MISMATCH")
    if kind == KIND_CENSUS or not event_representable:
        min_event, max_event = None, None
    if not available_representable:
        min_available, max_available = None, None
    claims = LiveCorpusPartitionClaims(
        kind=kind,
        partition_id=partition_id,
        logical_location=logical_location,
        file_sha256=file_sha256,
        content_sha256=digest.hexdigest(),
        row_count=row_count,
        min_event_time=min_event,
        max_event_time=max_event,
        min_available_to_strategy_at=min_available,
        max_available_to_strategy_at=max_available,
    )
    if stored_claims is not None:
        _require(claims.file_sha256 == stored_claims.file_sha256, "CORPUS_PARQUET_SHA_MISMATCH")
        _require(claims == stored_claims, "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
    return claims


def write_parquet_and_confirm_logical_hash(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    schema: pa.Schema,
    write_kwargs: Mapping[str, Any],
) -> str:
    """Write deterministic parquet and require pre/post logical hashes equal."""

    if schema.equals(CENSUS_RELEASE_SCHEMA):
        kind = KIND_CENSUS
    elif schema.equals(OBS_RELEASE_SCHEMA):
        kind = KIND_OBS
    else:
        raise LiveCorpusLogicalRowError("LIVE_CORPUS_SCHEMA_TYPE_UNSUPPORTED")
    before = hash_logical_rows(rows, schema=schema)
    write_parquet_from_row_batches(
        path,
        iter([list(rows)]),
        schema=schema,
        write_kwargs=write_kwargs,
    )
    after = measure_live_corpus_parquet(
        path,
        kind=kind,
        partition_id="PROBE",
        logical_location=path.name,
    ).content_sha256
    if before != after:
        raise LiveCorpusLogicalRowError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
    return before
