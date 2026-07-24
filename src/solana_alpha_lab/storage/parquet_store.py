"""Atomic immutable Parquet storage port for redacted TASK-06 raw events."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

from solana_alpha_lab.contracts.schema_v1 import (
    PartitionManifest,
    RawApiEvent,
    RawResponseStatus,
)

from .budget import (
    StorageBudgetPolicy,
    StorageBudgetSnapshot,
    evaluate_storage_budget,
)
from .manifests import (
    ManifestContractError,
    ManifestIntegrityError,
    build_partition_manifest,
    verify_partition_manifest,
)
from .raw_envelope import (
    EnvelopeContractError,
    verify_raw_api_event,
)

RAW_PARQUET_PROFILE = "smial-raw-api-events-parquet-v1"
ArrowError = pa.ArrowException

_SCHEMA_METADATA = {
    b"smial.contract": b"RawApiEvent",
    b"smial.parquet_profile": RAW_PARQUET_PROFILE.encode("ascii"),
    b"smial.schema_id": b"raw-api-events-v1",
}
_TIMESTAMP_FIELDS = frozenset(
    {
        "event_time",
        "observed_at",
        "available_to_strategy_at",
        "ingested_at",
        "first_reliable_available_at",
    }
)
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

RAW_API_EVENT_ARROW_SCHEMA = pa.schema(
    [
        pa.field("raw_event_id", pa.string(), nullable=False),
        pa.field("idempotency_key", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("source_version", pa.string(), nullable=False),
        pa.field("endpoint_or_method", pa.string(), nullable=False),
        pa.field("request_hash", pa.string(), nullable=False),
        pa.field("response_status", pa.string(), nullable=False),
        pa.field("error_class", pa.string()),
        pa.field("redacted_body", pa.binary(), nullable=False),
        pa.field("content_sha256", pa.string(), nullable=False),
        pa.field("redaction_version", pa.string(), nullable=False),
        pa.field("event_time", pa.timestamp("us", tz="UTC")),
        pa.field(
            "observed_at",
            pa.timestamp("us", tz="UTC"),
            nullable=False,
        ),
        pa.field(
            "available_to_strategy_at",
            pa.timestamp("us", tz="UTC"),
            nullable=False,
        ),
        pa.field(
            "ingested_at",
            pa.timestamp("us", tz="UTC"),
            nullable=False,
        ),
        pa.field(
            "first_reliable_available_at",
            pa.timestamp("us", tz="UTC"),
            nullable=False,
        ),
        pa.field("provider_version", pa.string()),
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("protocol_version", pa.string()),
        pa.field("revision_number", pa.int64(), nullable=False),
        pa.field("revision_of", pa.string()),
        pa.field("quality_flags", pa.string()),
    ],
    metadata=_SCHEMA_METADATA,
)


class ParquetStoreError(RuntimeError):
    """Base error for the bounded raw Parquet port."""


class ParquetContractError(ParquetStoreError):
    """Input or target violates the accepted storage contract."""


class ParquetIntegrityError(ParquetStoreError):
    """Stored bytes, schema, rows or manifest no longer agree."""


class ParquetConflictError(ParquetStoreError):
    """An immutable logical location already contains different bytes."""


class AtomicPublicationError(ParquetStoreError):
    """The filesystem cannot provide the required no-clobber publication."""


class WriteDisposition(StrEnum):
    CREATED = "CREATED"
    REPLAY_IDENTICAL = "REPLAY_IDENTICAL"


@dataclass(frozen=True, slots=True)
class RawParquetWriteResult:
    """Sanitized result: no machine-specific physical path is retained."""

    manifest: PartitionManifest
    disposition: WriteDisposition
    file_size_bytes: int
    budget_snapshot: StorageBudgetSnapshot | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timestamp_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ParquetContractError("event_timestamp_must_be_timezone_aware")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _prepare_events(
    events: Sequence[RawApiEvent],
) -> tuple[RawApiEvent, ...]:
    if isinstance(events, (str, bytes, bytearray)):
        raise ParquetContractError("events_must_be_a_sequence")
    prepared: list[RawApiEvent] = []
    for event in events:
        if not isinstance(event, RawApiEvent):
            raise ParquetContractError("event_must_be_raw_api_event")
        try:
            strict_payload = event.model_dump(mode="python")
            strict_payload["response_status"] = RawResponseStatus(
                event.response_status
            )
            RawApiEvent.model_validate(strict_payload)
            verify_raw_api_event(event)
        except (
            AttributeError,
            EnvelopeContractError,
            ValidationError,
            ValueError,
        ) as exc:
            raise ParquetContractError("raw_event_integrity_invalid") from exc
        prepared.append(event)
    if not prepared:
        raise ParquetContractError("events_must_not_be_empty")

    for name, values in (
        ("raw_event_id", [item.raw_event_id for item in prepared]),
        (
            "idempotency_key",
            [item.idempotency_key for item in prepared],
        ),
    ):
        if len(values) != len(set(values)):
            raise ParquetContractError(f"duplicate_{name}")

    return tuple(sorted(prepared, key=lambda item: item.raw_event_id))


def _canonical_event_row(event: RawApiEvent) -> dict[str, object]:
    return {
        "available_to_strategy_at": _timestamp_text(
            event.available_to_strategy_at
        ),
        "content_sha256": event.content_sha256,
        "endpoint_or_method": event.endpoint_or_method,
        "error_class": event.error_class,
        "event_time": _timestamp_text(event.event_time),
        "first_reliable_available_at": _timestamp_text(
            event.first_reliable_available_at
        ),
        "idempotency_key": event.idempotency_key,
        "ingested_at": _timestamp_text(event.ingested_at),
        "observed_at": _timestamp_text(event.observed_at),
        "protocol_version": event.protocol_version,
        "provider_version": event.provider_version,
        "quality_flags": event.quality_flags,
        "raw_event_id": event.raw_event_id,
        "redacted_body_hex": event.redacted_body.hex(),
        "redaction_version": event.redaction_version,
        "request_hash": event.request_hash,
        "response_status": str(event.response_status),
        "revision_number": event.revision_number,
        "revision_of": event.revision_of,
        "schema_version": event.schema_version,
        "source": event.source,
        "source_version": event.source_version,
    }


def canonical_raw_event_rows_bytes(
    events: Sequence[RawApiEvent],
) -> bytes:
    """Return the format-independent logical row preimage."""

    prepared = _prepare_events(events)
    try:
        text = json.dumps(
            [_canonical_event_row(item) for item in prepared],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ParquetContractError(
            "raw_event_canonicalization_failed"
        ) from exc
    return text.encode("utf-8")


def _arrow_event_row(event: RawApiEvent) -> dict[str, object]:
    return {
        "raw_event_id": event.raw_event_id,
        "idempotency_key": event.idempotency_key,
        "source": event.source,
        "source_version": event.source_version,
        "endpoint_or_method": event.endpoint_or_method,
        "request_hash": event.request_hash,
        "response_status": str(event.response_status),
        "error_class": event.error_class,
        "redacted_body": event.redacted_body,
        "content_sha256": event.content_sha256,
        "redaction_version": event.redaction_version,
        "event_time": event.event_time,
        "observed_at": event.observed_at,
        "available_to_strategy_at": event.available_to_strategy_at,
        "ingested_at": event.ingested_at,
        "first_reliable_available_at": (
            event.first_reliable_available_at
        ),
        "provider_version": event.provider_version,
        "schema_version": event.schema_version,
        "protocol_version": event.protocol_version,
        "revision_number": event.revision_number,
        "revision_of": event.revision_of,
        "quality_flags": event.quality_flags,
    }


def _deterministic_parquet_bytes(
    events: Sequence[RawApiEvent],
) -> bytes:
    prepared = _prepare_events(events)
    table = pa.Table.from_pylist(
        [_arrow_event_row(item) for item in prepared],
        schema=RAW_API_EVENT_ARROW_SCHEMA,
    )
    sink = pa.BufferOutputStream()
    try:
        pq.write_table(
            table,
            sink,
            compression="NONE",
            use_dictionary=False,
            write_statistics=True,
            version="2.6",
            data_page_version="1.0",
            row_group_size=65536,
            coerce_timestamps="us",
            allow_truncated_timestamps=False,
            store_schema=True,
        )
    except (ArrowError, OSError, ValueError) as exc:
        raise ParquetContractError("parquet_encoding_failed") from exc
    return sink.getvalue().to_pybytes()


def _partition_bounds(
    events: Sequence[RawApiEvent],
) -> dict[str, datetime | None]:
    prepared = _prepare_events(events)
    event_times = [item.event_time for item in prepared]
    if any(value is None for value in event_times):
        min_event_time = None
        max_event_time = None
    else:
        known_event_times = [
            value for value in event_times if value is not None
        ]
        min_event_time = min(known_event_times)
        max_event_time = max(known_event_times)
    available_times = [
        item.available_to_strategy_at for item in prepared
    ]
    return {
        "min_event_time": min_event_time,
        "max_event_time": max_event_time,
        "min_available_to_strategy_at": min(available_times),
        "max_available_to_strategy_at": max(available_times),
    }


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _validated_root(root: Path) -> Path:
    if not isinstance(root, Path):
        raise ParquetContractError("root_must_be_path")
    if not root.is_absolute():
        raise ParquetContractError("root_must_be_absolute")
    if root.is_symlink():
        raise ParquetContractError("root_symlink_forbidden")
    if not root.exists():
        raise ParquetContractError("root_must_exist")
    if not root.is_dir():
        raise ParquetContractError("root_must_be_directory")
    return root.resolve(strict=True)


def _target_path(
    root: Path,
    logical_location: str,
    *,
    create_parents: bool,
) -> tuple[Path, tuple[Path, ...]]:
    resolved_root = _validated_root(root)
    logical = PurePosixPath(logical_location)
    if logical.is_absolute() or not logical.parts:
        raise ParquetContractError("logical_location_invalid")

    current = resolved_root
    created: list[Path] = []
    try:
        for segment in logical.parts[:-1]:
            candidate = current / segment
            if candidate.is_symlink() or candidate.exists():
                try:
                    resolved = candidate.resolve(strict=True)
                except OSError as exc:
                    raise ParquetContractError(
                        "logical_parent_unresolvable"
                    ) from exc
                if not _is_within(resolved, resolved_root):
                    raise ParquetContractError(
                        "logical_parent_escapes_root"
                    )
                if not resolved.is_dir():
                    raise ParquetContractError(
                        "logical_parent_must_be_directory"
                    )
                current = resolved
                continue
            if not create_parents:
                raise ParquetIntegrityError("logical_parent_missing")
            try:
                candidate.mkdir()
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise AtomicPublicationError(
                    "logical_parent_creation_failed"
                ) from exc
            if not _is_within(resolved, resolved_root):
                raise ParquetContractError(
                    "logical_parent_escapes_root"
                )
            created.append(resolved)
            current = resolved

        target = current / logical.parts[-1]
        if target.is_symlink():
            raise ParquetContractError("target_symlink_forbidden")
        return target, tuple(created)
    except Exception:
        _cleanup_empty_directories(created)
        raise


def _cleanup_empty_directories(paths: Sequence[Path]) -> None:
    for path in reversed(paths):
        try:
            path.rmdir()
        except OSError:
            pass


def _same_bytes(path: Path, expected: bytes) -> bool:
    if not path.is_file() or path.is_symlink():
        raise ParquetConflictError("immutable_target_not_regular_file")
    try:
        return path.read_bytes() == expected
    except OSError as exc:
        raise ParquetIntegrityError("immutable_target_unreadable") from exc


def _is_destination_exists_error(exc: OSError) -> bool:
    return (
        isinstance(exc, FileExistsError)
        or exc.errno == errno.EEXIST
        or getattr(exc, "winerror", None) == 183
    )


def _publish_immutable(path: Path, data: bytes) -> WriteDisposition:
    if path.is_symlink():
        raise ParquetConflictError("immutable_target_symlink")
    if path.exists():
        if _same_bytes(path, data):
            return WriteDisposition.REPLAY_IDENTICAL
        raise ParquetConflictError("immutable_target_conflict")

    temporary_path: Path | None = None
    created_final = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
            created_final = True
        except OSError as exc:
            if _is_destination_exists_error(exc):
                if _same_bytes(path, data):
                    return WriteDisposition.REPLAY_IDENTICAL
                raise ParquetConflictError(
                    "immutable_target_conflict"
                ) from exc
            raise AtomicPublicationError(
                "atomic_no_clobber_publication_failed"
            ) from exc
        return WriteDisposition.CREATED
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                if created_final:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as rollback_exc:
                        raise AtomicPublicationError(
                            "temporary_and_final_cleanup_failed"
                        ) from rollback_exc
                raise AtomicPublicationError(
                    "temporary_cleanup_failed"
                ) from exc


def _events_from_table(table: pa.Table) -> tuple[RawApiEvent, ...]:
    if not table.schema.equals(
        RAW_API_EVENT_ARROW_SCHEMA,
        check_metadata=True,
    ):
        raise ParquetIntegrityError("parquet_schema_mismatch")
    try:
        timezone_neutral = pa.Table.from_arrays(
            [
                table[name].cast(pa.int64())
                if name in _TIMESTAMP_FIELDS
                else table[name]
                for name in table.column_names
            ],
            names=table.column_names,
        )
        rows = timezone_neutral.to_pylist()
    except (ArrowError, OSError, ValueError) as exc:
        raise ParquetIntegrityError("parquet_rows_unreadable") from exc
    events: list[RawApiEvent] = []
    for row in rows:
        try:
            for name in _TIMESTAMP_FIELDS:
                value = row[name]
                row[name] = (
                    None
                    if value is None
                    else _UNIX_EPOCH + timedelta(microseconds=value)
                )
            row["response_status"] = RawResponseStatus(
                row["response_status"]
            )
            event = RawApiEvent.model_validate(row)
            verify_raw_api_event(event)
        except (
            EnvelopeContractError,
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise ParquetIntegrityError(
                "parquet_row_contract_invalid"
            ) from exc
        events.append(event)
    prepared = _prepare_events(events)
    if tuple(events) != prepared:
        raise ParquetIntegrityError("parquet_row_order_not_canonical")
    return prepared


def verify_raw_event_partition(
    *,
    root: Path,
    manifest: PartitionManifest,
) -> tuple[RawApiEvent, ...]:
    """Read back and verify one immutable raw-event Parquet piece."""

    try:
        verify_partition_manifest(manifest)
    except (ManifestContractError, ManifestIntegrityError) as exc:
        raise ParquetIntegrityError("partition_manifest_invalid") from exc
    path, _ = _target_path(
        root,
        manifest.logical_location,
        create_parents=False,
    )
    if path.is_symlink() or not path.is_file():
        raise ParquetIntegrityError("parquet_file_missing_or_unsafe")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ParquetIntegrityError("parquet_file_unreadable") from exc
    if _sha256(data) != manifest.file_sha256:
        raise ParquetIntegrityError("parquet_file_hash_mismatch")
    try:
        table = pq.ParquetFile(path).read()
    except (ArrowError, OSError, ValueError) as exc:
        raise ParquetIntegrityError("parquet_decode_failed") from exc
    events = _events_from_table(table)
    if len(events) != manifest.row_count:
        raise ParquetIntegrityError("parquet_row_count_mismatch")
    if _sha256(canonical_raw_event_rows_bytes(events)) != (
        manifest.content_sha256
    ):
        raise ParquetIntegrityError("parquet_content_hash_mismatch")

    bounds = _partition_bounds(events)
    for name, expected in bounds.items():
        if getattr(manifest, name) != expected:
            raise ParquetIntegrityError(f"parquet_{name}_mismatch")
    return events


def _write_raw_event_partition(
    *,
    root: Path,
    dataset_id: str,
    dataset_version: str,
    partition_id: str,
    logical_location: str,
    events: Sequence[RawApiEvent],
    created_at: datetime,
    first_reliable_available_at: datetime,
    budget_policy: StorageBudgetPolicy | None,
) -> RawParquetWriteResult:
    prepared = _prepare_events(events)
    parquet_data = _deterministic_parquet_bytes(prepared)
    logical_content = canonical_raw_event_rows_bytes(prepared)
    bounds = _partition_bounds(prepared)
    try:
        manifest = build_partition_manifest(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            partition_id=partition_id,
            logical_location=logical_location,
            file_sha256=_sha256(parquet_data),
            content_sha256=_sha256(logical_content),
            row_count=len(prepared),
            first_reliable_available_at=(
                first_reliable_available_at
            ),
            created_at=created_at,
            **bounds,
        )
    except (ManifestContractError, ValidationError) as exc:
        raise ParquetContractError("partition_manifest_claim_invalid") from exc

    budget_snapshot: StorageBudgetSnapshot | None = None
    if budget_policy is not None:
        budget_snapshot = evaluate_storage_budget(
            root=root,
            logical_location=manifest.logical_location,
            incoming_file_sha256=manifest.file_sha256,
            incoming_partition_bytes=len(parquet_data),
            policy=budget_policy,
        )

    path, created_directories = _target_path(
        root,
        manifest.logical_location,
        create_parents=True,
    )
    disposition: WriteDisposition | None = None
    try:
        disposition = _publish_immutable(path, parquet_data)
        observed = verify_raw_event_partition(
            root=root,
            manifest=manifest,
        )
        if observed != prepared:
            raise ParquetIntegrityError("parquet_replay_mismatch")
        if budget_policy is not None:
            budget_snapshot = evaluate_storage_budget(
                root=root,
                logical_location=manifest.logical_location,
                incoming_file_sha256=manifest.file_sha256,
                incoming_partition_bytes=len(parquet_data),
                policy=budget_policy,
            )
    except Exception:
        if disposition == WriteDisposition.CREATED:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                raise AtomicPublicationError(
                    "new_file_rollback_failed"
                ) from exc
        _cleanup_empty_directories(created_directories)
        raise

    return RawParquetWriteResult(
        manifest=manifest,
        disposition=disposition,
        file_size_bytes=len(parquet_data),
        budget_snapshot=budget_snapshot,
    )


def write_raw_event_partition(
    *,
    root: Path,
    dataset_id: str,
    dataset_version: str,
    partition_id: str,
    logical_location: str,
    events: Sequence[RawApiEvent],
    created_at: datetime,
    first_reliable_available_at: datetime,
) -> RawParquetWriteResult:
    """Publish through the low-level deterministic Parquet primitive."""

    return _write_raw_event_partition(
        root=root,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=partition_id,
        logical_location=logical_location,
        events=events,
        created_at=created_at,
        first_reliable_available_at=first_reliable_available_at,
        budget_policy=None,
    )


def write_budgeted_raw_event_partition(
    *,
    root: Path,
    dataset_id: str,
    dataset_version: str,
    partition_id: str,
    logical_location: str,
    events: Sequence[RawApiEvent],
    created_at: datetime,
    first_reliable_available_at: datetime,
    budget_policy: StorageBudgetPolicy,
) -> RawParquetWriteResult:
    """Publish only after explicit pre/post storage-budget checks."""

    if not isinstance(budget_policy, StorageBudgetPolicy):
        raise ParquetContractError(
            "budget_policy_must_be_storage_budget_policy"
        )
    return _write_raw_event_partition(
        root=root,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=partition_id,
        logical_location=logical_location,
        events=events,
        created_at=created_at,
        first_reliable_available_at=first_reliable_available_at,
        budget_policy=budget_policy,
    )
