"""Immutable manifest-last research event storage for the Factory fast lane."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import socket
import tempfile
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from solana_alpha_lab.contracts.schema_v1 import PartitionManifest
from solana_alpha_lab.storage.manifests import (
    ManifestContractError,
    ManifestIntegrityError,
    build_partition_manifest,
    canonical_manifest_bytes,
    compute_dataset_manifest_id,
    verify_partition_manifest,
)


RESEARCH_DATASET_ID = "research-events"
RESEARCH_DATASET_VERSION = "1.0"
RESEARCH_PARQUET_PROFILE = "smial-research-event-envelope-parquet-v1"
RESEARCH_LOGICAL_URI_PREFIX = "smial-data://"
RESEARCH_PROJECTION_LOCATION = "projections/research_memory.duckdb"
RESEARCH_PROJECTION_LOGICAL_URI = (
    f"{RESEARCH_LOGICAL_URI_PREFIX}{RESEARCH_PROJECTION_LOCATION}"
)
_PROJECTION_DDL_PATH = (
    Path(__file__).resolve().parents[3]
    / "schemas"
    / "research_memory_projection_v1.sql"
)
_PROJECTION_VIEWS = (
    "hypotheses",
    "hypothesis_events",
    "experiment_runs",
    "experiment_metrics",
    "evidence_bindings",
    "promotion_candidates",
    "prior_work",
    "capability_gaps",
)
_PROJECTION_COLUMNS = (
    "record_id",
    "record_kind",
    "entity_id",
    "stable_id",
    "hypothesis_version_id",
    "run_id",
    "transaction_id",
    "effective_at",
    "first_reliable_available_at",
    "supersedes_record_id",
    "payload_json",
    "payload_sha256",
    "definition_sha256",
    "run_key_sha256",
    "schema_version",
    "producer_capability_id",
    "producer_git_sha",
    "created_at",
)
_LEASE_DURATION = timedelta(minutes=5)
_TRANSACTION_ID_RE = re.compile(
    r"RESEARCH-TXN-[A-Z0-9][A-Z0-9._-]{0,243}"
)
_SAFE_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_HASH64_RE = re.compile(r"[0-9a-f]{64}")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_TIMESTAMP_FIELDS = frozenset(
    {
        "effective_at",
        "first_reliable_available_at",
        "created_at",
    }
)
_SCHEMA_METADATA = {
    b"smial.contract": b"ResearchEvent",
    b"smial.parquet_profile": RESEARCH_PARQUET_PROFILE.encode("ascii"),
    b"smial.schema_id": b"research-event-envelope-v1",
}

Hash64 = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
GitSha = Annotated[
    str,
    Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$"),
]


class RecordKind(StrEnum):
    HYPOTHESIS_FAMILY = "HYPOTHESIS_FAMILY"
    HYPOTHESIS_ORIGIN = "HYPOTHESIS_ORIGIN"
    RESEARCH_CYCLE = "RESEARCH_CYCLE"
    HYPOTHESIS_VERSION = "HYPOTHESIS_VERSION"
    RESEARCH_ARTIFACT = "RESEARCH_ARTIFACT"
    TRIAL = "TRIAL"
    DECISION_EVENT = "DECISION_EVENT"
    DERIVATION_EDGE = "DERIVATION_EDGE"
    ACTIVATION_EPOCH = "ACTIVATION_EPOCH"
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_ABORTED = "RUN_ABORTED"
    RUN_INVALID = "RUN_INVALID"
    EXPERIMENT_METRIC = "EXPERIMENT_METRIC"
    EVIDENCE_BINDING = "EVIDENCE_BINDING"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"
    CAPABILITY_GAP = "CAPABILITY_GAP"


class ResearchEvent(BaseModel):
    """Typed durable envelope from PRD section 9.1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        use_enum_values=True,
    )

    record_id: Annotated[str, Field(min_length=1, max_length=256)]
    record_kind: RecordKind
    entity_id: Annotated[str, Field(min_length=1, max_length=256)]
    hypothesis_version_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ] | None
    run_id: Annotated[str, Field(min_length=1, max_length=256)] | None
    transaction_id: Annotated[
        str,
        Field(pattern=r"^RESEARCH-TXN-[A-Z0-9][A-Z0-9._-]{0,243}$"),
    ]
    effective_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    supersedes_record_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ] | None
    payload_json: str
    payload_sha256: Hash64
    schema_version: Annotated[str, Field(min_length=1, max_length=64)]
    producer_capability_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]
    producer_git_sha: GitSha
    created_at: AwareDatetime


RESEARCH_EVENT_ARROW_SCHEMA = pa.schema(
    [
        pa.field("record_id", pa.string(), nullable=False),
        pa.field("record_kind", pa.string(), nullable=False),
        pa.field("entity_id", pa.string(), nullable=False),
        pa.field("hypothesis_version_id", pa.string()),
        pa.field("run_id", pa.string()),
        pa.field("transaction_id", pa.string(), nullable=False),
        pa.field("effective_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field(
            "first_reliable_available_at",
            pa.timestamp("us", tz="UTC"),
            nullable=False,
        ),
        pa.field("supersedes_record_id", pa.string()),
        pa.field("payload_json", pa.string(), nullable=False),
        pa.field("payload_sha256", pa.string(), nullable=False),
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("producer_capability_id", pa.string(), nullable=False),
        pa.field("producer_git_sha", pa.string(), nullable=False),
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ],
    metadata=_SCHEMA_METADATA,
)


class ResearchStoreError(RuntimeError):
    """Typed fail-closed error raised at the research data-plane boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CommitDisposition(StrEnum):
    CREATED = "CREATED"
    REPLAY_IDENTICAL = "REPLAY_IDENTICAL"


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    transaction_id: str
    manifest: PartitionManifest
    disposition: CommitDisposition
    logical_uri: str
    record_count: int

    @property
    def partition_manifest_id(self) -> str:
        return self.manifest.partition_manifest_id


@dataclass(frozen=True, slots=True)
class ProjectionReceipt:
    status: str
    logical_uri: str
    projection_digest_sha256: str
    record_count: int
    partition_count: int


@dataclass(frozen=True, slots=True)
class RunPassport:
    run_id: str
    run_key_sha256: str
    payload: Mapping[str, Any]


class _PublishDisposition(StrEnum):
    CREATED = "CREATED"
    REPLAY_IDENTICAL = "REPLAY_IDENTICAL"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timestamp_text(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non_finite_json_constant:{value}")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_object_key")
        result[key] = value
    return result


def _validate_logical_uri(value: str) -> None:
    relative = value.removeprefix(RESEARCH_LOGICAL_URI_PREFIX)
    if not relative or "\\" in relative:
        raise ResearchStoreError("PHYSICAL_PATH_FORBIDDEN")
    logical = PurePosixPath(relative)
    if logical.is_absolute() or any(
        segment in {"", ".", ".."} for segment in logical.parts
    ):
        raise ResearchStoreError("PHYSICAL_PATH_FORBIDDEN")
    if len(logical.parts) < 2 or logical.parts[0] not in {
        "datasets",
        "research",
    }:
        raise ResearchStoreError("PHYSICAL_PATH_FORBIDDEN")


def _validate_no_physical_paths(value: Any, *, key: str | None = None) -> None:
    if key is not None and key.casefold() in {
        "physical_path",
        "data_root",
        "smial_data_root",
    }:
        raise ResearchStoreError("PHYSICAL_PATH_FORBIDDEN")
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise ResearchStoreError("PAYLOAD_JSON_INVALID")
            _validate_no_physical_paths(child_value, key=child_key)
        return
    if isinstance(value, list):
        for item in value:
            _validate_no_physical_paths(item)
        return
    if not isinstance(value, str):
        return
    if value.startswith(RESEARCH_LOGICAL_URI_PREFIX):
        _validate_logical_uri(value)
        return
    normalized = value.replace("\\", "/")
    if (
        value.startswith(("/", "\\"))
        or _WINDOWS_DRIVE_RE.match(value) is not None
        or _URI_SCHEME_RE.match(value) is not None
        or "://" in value
        or ".." in normalized.split("/")
    ):
        raise ResearchStoreError("PHYSICAL_PATH_FORBIDDEN")


def _canonical_payload(payload_json: str) -> tuple[str, str]:
    try:
        parsed = json.loads(
            payload_json,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
        _validate_no_physical_paths(parsed)
        canonical = json.dumps(
            parsed,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ResearchStoreError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResearchStoreError("PAYLOAD_JSON_INVALID") from exc
    return canonical, _sha256(canonical.encode("utf-8"))


def _safe_identifier(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or _SAFE_IDENTIFIER_RE.fullmatch(value) is None
        or _WINDOWS_DRIVE_RE.match(value) is not None
    ):
        raise ResearchStoreError(f"{name.upper()}_INVALID")


def _normalize_record(record: ResearchEvent) -> ResearchEvent:
    if not isinstance(record, ResearchEvent):
        raise ResearchStoreError("RECORD_MUST_BE_RESEARCH_EVENT")
    try:
        validated = ResearchEvent.model_validate(record.model_dump(mode="python"))
    except (AttributeError, ValidationError, ValueError) as exc:
        raise ResearchStoreError("RESEARCH_EVENT_INVALID") from exc
    for name in (
        "record_id",
        "entity_id",
        "schema_version",
        "producer_capability_id",
    ):
        _safe_identifier(name, getattr(validated, name))
    for name in (
        "hypothesis_version_id",
        "run_id",
        "supersedes_record_id",
    ):
        value = getattr(validated, name)
        if value is not None:
            _safe_identifier(name, value)
    if _TRANSACTION_ID_RE.fullmatch(validated.transaction_id) is None:
        raise ResearchStoreError("TRANSACTION_ID_INVALID")
    if _HASH64_RE.fullmatch(validated.payload_sha256) is None:
        raise ResearchStoreError("PAYLOAD_HASH_INVALID")
    if _GIT_SHA_RE.fullmatch(validated.producer_git_sha) is None:
        raise ResearchStoreError("PRODUCER_GIT_SHA_INVALID")
    canonical, observed_hash = _canonical_payload(validated.payload_json)
    if observed_hash != validated.payload_sha256:
        raise ResearchStoreError("PAYLOAD_HASH_MISMATCH")
    return validated.model_copy(
        update={
            "payload_json": canonical,
            "effective_at": validated.effective_at.astimezone(UTC),
            "first_reliable_available_at": (
                validated.first_reliable_available_at.astimezone(UTC)
            ),
            "created_at": validated.created_at.astimezone(UTC),
        }
    )


def _prepare_records(
    records: Sequence[ResearchEvent],
    *,
    transaction_id: str,
) -> tuple[ResearchEvent, ...]:
    if isinstance(records, (str, bytes, bytearray)):
        raise ResearchStoreError("RECORDS_MUST_BE_SEQUENCE")
    if _TRANSACTION_ID_RE.fullmatch(transaction_id) is None:
        raise ResearchStoreError("TRANSACTION_ID_INVALID")
    prepared = tuple(_normalize_record(record) for record in records)
    if not prepared:
        raise ResearchStoreError("RECORDS_MUST_NOT_BE_EMPTY")
    if any(record.transaction_id != transaction_id for record in prepared):
        raise ResearchStoreError("TRANSACTION_ID_MISMATCH")
    record_ids = [record.record_id for record in prepared]
    if len(record_ids) != len(set(record_ids)):
        raise ResearchStoreError("DUPLICATE_RECORD_ID")
    return tuple(sorted(prepared, key=lambda record: record.record_id))


def _canonical_record_row(record: ResearchEvent) -> dict[str, Any]:
    return {
        "created_at": _timestamp_text(record.created_at),
        "effective_at": _timestamp_text(record.effective_at),
        "entity_id": record.entity_id,
        "first_reliable_available_at": _timestamp_text(
            record.first_reliable_available_at
        ),
        "hypothesis_version_id": record.hypothesis_version_id,
        "payload_json": record.payload_json,
        "payload_sha256": record.payload_sha256,
        "producer_capability_id": record.producer_capability_id,
        "producer_git_sha": record.producer_git_sha,
        "record_id": record.record_id,
        "record_kind": str(record.record_kind),
        "run_id": record.run_id,
        "schema_version": record.schema_version,
        "supersedes_record_id": record.supersedes_record_id,
        "transaction_id": record.transaction_id,
    }


def _canonical_records_bytes(records: Sequence[ResearchEvent]) -> bytes:
    try:
        text = json.dumps(
            [_canonical_record_row(record) for record in records],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ResearchStoreError("RECORD_CANONICALIZATION_FAILED") from exc
    return text.encode("utf-8")


def _arrow_record_row(record: ResearchEvent) -> dict[str, Any]:
    return {
        "record_id": record.record_id,
        "record_kind": str(record.record_kind),
        "entity_id": record.entity_id,
        "hypothesis_version_id": record.hypothesis_version_id,
        "run_id": record.run_id,
        "transaction_id": record.transaction_id,
        "effective_at": record.effective_at,
        "first_reliable_available_at": record.first_reliable_available_at,
        "supersedes_record_id": record.supersedes_record_id,
        "payload_json": record.payload_json,
        "payload_sha256": record.payload_sha256,
        "schema_version": record.schema_version,
        "producer_capability_id": record.producer_capability_id,
        "producer_git_sha": record.producer_git_sha,
        "created_at": record.created_at,
    }


def _records_from_table(table: pa.Table) -> tuple[ResearchEvent, ...]:
    if not table.schema.equals(
        RESEARCH_EVENT_ARROW_SCHEMA,
        check_metadata=True,
    ):
        raise ResearchStoreError("PARQUET_SCHEMA_MISMATCH")
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
        for row in rows:
            for name in _TIMESTAMP_FIELDS:
                row[name] = _UNIX_EPOCH + timedelta(
                    microseconds=row[name]
                )
        records = tuple(
            _normalize_record(ResearchEvent.model_validate(row)) for row in rows
        )
    except (ResearchStoreError, ValidationError, ValueError, TypeError) as exc:
        if isinstance(exc, ResearchStoreError):
            raise
        raise ResearchStoreError("PARQUET_ROW_INVALID") from exc
    record_ids = [record.record_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ResearchStoreError("DUPLICATE_RECORD_ID")
    ordered = tuple(sorted(records, key=lambda record: record.record_id))
    if records != ordered:
        raise ResearchStoreError("PARQUET_ROW_ORDER_INVALID")
    return records


def _payload_object(record: ResearchEvent) -> dict[str, Any]:
    try:
        payload = json.loads(record.payload_json)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResearchStoreError("PAYLOAD_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ResearchStoreError("PAYLOAD_JSON_MUST_BE_OBJECT")
    return payload


_STABLE_ID_FIELDS = {
    RecordKind.HYPOTHESIS_FAMILY: "family_id",
    RecordKind.HYPOTHESIS_ORIGIN: "origin_id",
    RecordKind.RESEARCH_CYCLE: "research_cycle_id",
    RecordKind.HYPOTHESIS_VERSION: "hypothesis_version_id",
    RecordKind.RESEARCH_ARTIFACT: "research_artifact_id",
    RecordKind.TRIAL: "trial_id",
    RecordKind.DECISION_EVENT: "decision_event_id",
    RecordKind.DERIVATION_EDGE: "derivation_edge_id",
    RecordKind.ACTIVATION_EPOCH: "activation_epoch_id",
    RecordKind.EXPERIMENT_METRIC: "metric_id",
    RecordKind.EVIDENCE_BINDING: "evidence_binding_id",
    RecordKind.PROMOTION_CANDIDATE: "promotion_candidate_id",
    RecordKind.CAPABILITY_GAP: "capability_gap_id",
}


def _projection_stable_id(
    record: ResearchEvent,
    payload: Mapping[str, Any],
) -> str:
    if record.record_kind in {
        RecordKind.RUN_STARTED,
        RecordKind.RUN_COMPLETED,
        RecordKind.RUN_ABORTED,
        RecordKind.RUN_INVALID,
    }:
        candidate = payload.get("run_id", record.run_id)
    else:
        field = _STABLE_ID_FIELDS.get(RecordKind(record.record_kind))
        candidate = payload.get(field) if field is not None else None
    stable_id = candidate if isinstance(candidate, str) else record.entity_id
    if not stable_id:
        raise ResearchStoreError("PROJECTION_STABLE_ID_MISSING")
    return stable_id


def _projection_record_row(record: ResearchEvent) -> tuple[Any, ...]:
    payload = _payload_object(record)
    return (
        record.record_id,
        str(record.record_kind),
        record.entity_id,
        _projection_stable_id(record, payload),
        record.hypothesis_version_id,
        record.run_id,
        record.transaction_id,
        record.effective_at.astimezone(UTC).replace(tzinfo=None),
        record.first_reliable_available_at.astimezone(UTC).replace(tzinfo=None),
        record.supersedes_record_id,
        record.payload_json,
        record.payload_sha256,
        payload.get("definition_sha256") or payload.get("hypothesis_definition_sha256"),
        payload.get("run_key_sha256"),
        record.schema_version,
        record.producer_capability_id,
        record.producer_git_sha,
        record.created_at.astimezone(UTC).replace(tzinfo=None),
    )


def _projection_export_digest(
    connection: duckdb.DuckDBPyConnection,
    *,
    manifests: Sequence[PartitionManifest],
) -> str:
    exports: dict[str, Any] = {
        "manifests": [
            {
                "content_sha256": manifest.content_sha256,
                "file_sha256": manifest.file_sha256,
                "partition_manifest_id": manifest.partition_manifest_id,
            }
            for manifest in manifests
        ],
        "views": {},
    }
    for view in _PROJECTION_VIEWS:
        rows = connection.execute(
            f"""
            SELECT to_json(export_row)
            FROM (
                SELECT *
                FROM "{view}"
                ORDER BY ALL
                LIMIT 1000
            ) AS export_row
            """
        ).fetchall()
        exports["views"][view] = [row[0] for row in rows]
    canonical = json.dumps(
        exports,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(canonical)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _target_path(
    root: Path,
    logical_location: str,
    *,
    create_parents: bool,
) -> Path:
    if (
        not isinstance(logical_location, str)
        or "\\" in logical_location
        or "://" in logical_location
        or _WINDOWS_DRIVE_RE.match(logical_location) is not None
    ):
        raise ResearchStoreError("LOGICAL_LOCATION_INVALID")
    logical = PurePosixPath(logical_location)
    if logical.is_absolute() or not logical.parts or any(
        segment in {"", ".", ".."} for segment in logical.parts
    ):
        raise ResearchStoreError("LOGICAL_LOCATION_INVALID")

    current = root
    for segment in logical.parts[:-1]:
        candidate = current / segment
        if candidate.exists() or candidate.is_symlink():
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise ResearchStoreError("LOGICAL_PARENT_UNRESOLVABLE") from exc
            if not _is_within(resolved, root) or not resolved.is_dir():
                raise ResearchStoreError("LOGICAL_PARENT_UNSAFE")
            current = resolved
            continue
        if not create_parents:
            raise ResearchStoreError("LOGICAL_PARENT_MISSING")
        try:
            candidate.mkdir()
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ResearchStoreError("LOGICAL_PARENT_CREATION_FAILED") from exc
        if not _is_within(resolved, root):
            raise ResearchStoreError("LOGICAL_PARENT_UNSAFE")
        current = resolved

    target = current / logical.parts[-1]
    if target.is_symlink():
        raise ResearchStoreError("IMMUTABLE_TARGET_SYMLINK")
    return target


def _same_bytes(path: Path, expected: bytes) -> bool:
    if not path.is_file() or path.is_symlink():
        raise ResearchStoreError("IMMUTABLE_TARGET_NOT_REGULAR_FILE")
    try:
        return path.read_bytes() == expected
    except OSError as exc:
        raise ResearchStoreError("IMMUTABLE_TARGET_UNREADABLE") from exc


def _destination_exists(exc: OSError) -> bool:
    return (
        isinstance(exc, FileExistsError)
        or exc.errno == errno.EEXIST
        or getattr(exc, "winerror", None) == 183
    )


def _publish_immutable(path: Path, data: bytes) -> _PublishDisposition:
    if path.is_symlink():
        raise ResearchStoreError("IMMUTABLE_TARGET_SYMLINK")
    if path.exists():
        if _same_bytes(path, data):
            return _PublishDisposition.REPLAY_IDENTICAL
        raise ResearchStoreError("IMMUTABLE_TARGET_CONFLICT")

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
            if _destination_exists(exc):
                if _same_bytes(path, data):
                    return _PublishDisposition.REPLAY_IDENTICAL
                raise ResearchStoreError("IMMUTABLE_TARGET_CONFLICT") from exc
            raise ResearchStoreError(
                "ATOMIC_NO_CLOBBER_PUBLICATION_FAILED"
            ) from exc
        return _PublishDisposition.CREATED
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                if created_final:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as rollback_exc:
                        raise ResearchStoreError(
                            "TEMPORARY_AND_FINAL_CLEANUP_FAILED"
                        ) from rollback_exc
                raise ResearchStoreError("TEMPORARY_CLEANUP_FAILED") from exc


def _validated_data_root(data_root: Path) -> Path:
    if not isinstance(data_root, Path):
        raise ResearchStoreError("DATA_ROOT_MUST_BE_PATH")
    if not data_root.is_absolute():
        raise ResearchStoreError("DATA_ROOT_MUST_BE_ABSOLUTE")
    if data_root.is_symlink():
        raise ResearchStoreError("DATA_ROOT_SYMLINK_FORBIDDEN")
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        resolved = data_root.resolve(strict=True)
    except OSError as exc:
        raise ResearchStoreError("DATA_ROOT_UNAVAILABLE") from exc
    if not resolved.is_dir():
        raise ResearchStoreError("DATA_ROOT_MUST_BE_DIRECTORY")
    return resolved


class ResearchStore:
    """One-writer immutable research log rooted outside Git."""

    def __init__(self, data_root: Path) -> None:
        self._root = _validated_data_root(data_root)

    @contextmanager
    def writer_lease(self) -> Iterator[None]:
        lock_path = _target_path(
            self._root,
            "locks/research-writer.lock",
            create_parents=True,
        )
        token = uuid.uuid4().hex
        opened_at = datetime.now(UTC)
        lease = {
            "expiry": _timestamp_text(opened_at + _LEASE_DURATION),
            "host": socket.gethostname(),
            "opened_at": _timestamp_text(opened_at),
            "pid": os.getpid(),
            "token": token,
        }
        lease_bytes = json.dumps(
            lease,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        try:
            with lock_path.open("xb") as handle:
                handle.write(lease_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            if _destination_exists(exc):
                raise ResearchStoreError("WRITER_BUSY") from exc
            raise ResearchStoreError("WRITER_LEASE_CREATE_FAILED") from exc

        try:
            yield
        finally:
            try:
                observed = json.loads(lock_path.read_text(encoding="utf-8"))
                if not isinstance(observed, dict) or observed.get("token") != token:
                    raise ResearchStoreError("WRITER_LEASE_OWNERSHIP_LOST")
                lock_path.unlink()
            except ResearchStoreError:
                raise
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ResearchStoreError("WRITER_LEASE_RELEASE_FAILED") from exc

    def _stage_parquet(
        self,
        records: Sequence[ResearchEvent],
    ) -> tuple[bytes, tuple[ResearchEvent, ...]]:
        temporary_dir = _target_path(
            self._root,
            "research/.tmp/staged.parquet",
            create_parents=True,
        ).parent
        temporary_path: Path | None = None
        table = pa.Table.from_pylist(
            [_arrow_record_row(record) for record in records],
            schema=RESEARCH_EVENT_ARROW_SCHEMA,
        )
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".research-transaction.",
                suffix=".parquet.tmp",
                dir=temporary_dir,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
            pq.write_table(
                table,
                temporary_path,
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
            with temporary_path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            observed_table = pq.ParquetFile(temporary_path).read()
            observed_records = _records_from_table(observed_table)
            if observed_records != tuple(records):
                raise ResearchStoreError("PARQUET_READ_BACK_MISMATCH")
            return temporary_path.read_bytes(), observed_records
        except ResearchStoreError:
            raise
        except (OSError, ValueError, pa.ArrowException) as exc:
            raise ResearchStoreError("PARQUET_STAGING_FAILED") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as exc:
                    raise ResearchStoreError("TEMPORARY_CLEANUP_FAILED") from exc

    def _build_manifest(
        self,
        *,
        transaction_id: str,
        records: Sequence[ResearchEvent],
        parquet_bytes: bytes,
    ) -> PartitionManifest:
        event_date = min(record.created_at for record in records).date()
        logical_location = (
            f"research/events/date={event_date.isoformat()}/"
            f"{transaction_id}.parquet"
        )
        min_effective = min(record.effective_at for record in records)
        max_effective = max(record.effective_at for record in records)
        min_available = min(
            record.first_reliable_available_at for record in records
        )
        max_available = max(
            record.first_reliable_available_at for record in records
        )
        manifest_created = max(
            max(record.created_at for record in records),
            max_available,
        )
        manifest_reliable = max(manifest_created, max_available)
        try:
            return build_partition_manifest(
                dataset_id=RESEARCH_DATASET_ID,
                dataset_version=RESEARCH_DATASET_VERSION,
                partition_id=transaction_id,
                logical_location=logical_location,
                file_sha256=_sha256(parquet_bytes),
                content_sha256=_sha256(_canonical_records_bytes(records)),
                row_count=len(records),
                min_event_time=min_effective,
                max_event_time=max_effective,
                min_available_to_strategy_at=min_available,
                max_available_to_strategy_at=max_available,
                first_reliable_available_at=manifest_reliable,
                created_at=manifest_created,
            )
        except (ManifestContractError, ValidationError) as exc:
            raise ResearchStoreError("PARTITION_MANIFEST_INVALID") from exc

    def _manifest_files(self) -> tuple[Path, ...]:
        manifest_dir = self._root / "research/manifests/partitions"
        if not manifest_dir.exists():
            return ()
        if manifest_dir.is_symlink() or not manifest_dir.is_dir():
            raise ResearchStoreError("MANIFEST_DIRECTORY_UNSAFE")
        return tuple(sorted(manifest_dir.glob("partition-*.json")))

    def _read_manifest(self, path: Path) -> PartitionManifest:
        if path.is_symlink() or not path.is_file():
            raise ResearchStoreError("PARTITION_MANIFEST_UNSAFE")
        try:
            manifest = PartitionManifest.model_validate_json(path.read_bytes())
            verify_partition_manifest(manifest)
        except (
            OSError,
            ValidationError,
            ManifestContractError,
            ManifestIntegrityError,
        ) as exc:
            raise ResearchStoreError("PARTITION_MANIFEST_INVALID") from exc
        if (
            manifest.partition_manifest_id != path.stem
            or not manifest.logical_location.startswith("research/events/")
        ):
            raise ResearchStoreError("PARTITION_MANIFEST_INVALID")
        return manifest

    def _committed_manifests(self) -> tuple[PartitionManifest, ...]:
        manifests = tuple(
            self._read_manifest(path) for path in self._manifest_files()
        )
        partition_ids = [manifest.partition_id for manifest in manifests]
        if len(partition_ids) != len(set(partition_ids)):
            raise ResearchStoreError("DUPLICATE_COMMITTED_TRANSACTION")
        return tuple(
            sorted(
                manifests,
                key=lambda manifest: (
                    manifest.partition_id,
                    manifest.partition_manifest_id,
                ),
            )
        )

    def _verify_partition(
        self,
        manifest: PartitionManifest,
    ) -> tuple[ResearchEvent, ...]:
        try:
            verify_partition_manifest(manifest)
        except (ManifestContractError, ManifestIntegrityError) as exc:
            raise ResearchStoreError("PARTITION_MANIFEST_INVALID") from exc
        if manifest.dataset_manifest_id != compute_dataset_manifest_id(
            RESEARCH_DATASET_ID,
            RESEARCH_DATASET_VERSION,
        ):
            raise ResearchStoreError("PARTITION_DATASET_MISMATCH")
        path = _target_path(
            self._root,
            manifest.logical_location,
            create_parents=False,
        )
        if path.is_symlink() or not path.is_file():
            raise ResearchStoreError("COMMITTED_PARQUET_MISSING")
        try:
            parquet_bytes = path.read_bytes()
            table = pq.ParquetFile(path).read()
        except (OSError, ValueError, pa.ArrowException) as exc:
            raise ResearchStoreError("COMMITTED_PARQUET_UNREADABLE") from exc
        if _sha256(parquet_bytes) != manifest.file_sha256:
            raise ResearchStoreError("COMMITTED_PARQUET_HASH_MISMATCH")
        records = _records_from_table(table)
        if len(records) != manifest.row_count:
            raise ResearchStoreError("COMMITTED_PARQUET_ROW_COUNT_MISMATCH")
        if _sha256(_canonical_records_bytes(records)) != manifest.content_sha256:
            raise ResearchStoreError("COMMITTED_PARQUET_CONTENT_MISMATCH")
        if any(
            record.transaction_id != manifest.partition_id
            for record in records
        ):
            raise ResearchStoreError("COMMITTED_TRANSACTION_ID_MISMATCH")
        expected_bounds = {
            "min_event_time": min(record.effective_at for record in records),
            "max_event_time": max(record.effective_at for record in records),
            "min_available_to_strategy_at": min(
                record.first_reliable_available_at for record in records
            ),
            "max_available_to_strategy_at": max(
                record.first_reliable_available_at for record in records
            ),
        }
        for name, expected in expected_bounds.items():
            if getattr(manifest, name) != expected:
                raise ResearchStoreError(
                    f"COMMITTED_{name.upper()}_MISMATCH"
                )
        return records

    def _existing_transaction(
        self,
        transaction_id: str,
    ) -> PartitionManifest | None:
        matches = [
            manifest
            for manifest in self._committed_manifests()
            if manifest.partition_id == transaction_id
        ]
        if len(matches) > 1:
            raise ResearchStoreError("DUPLICATE_COMMITTED_TRANSACTION")
        return matches[0] if matches else None

    def _receipt(
        self,
        manifest: PartitionManifest,
        disposition: CommitDisposition,
    ) -> CommitReceipt:
        return CommitReceipt(
            transaction_id=manifest.partition_id,
            manifest=manifest,
            disposition=disposition,
            logical_uri=(
                f"{RESEARCH_LOGICAL_URI_PREFIX}{manifest.logical_location}"
            ),
            record_count=manifest.row_count,
        )

    def append(
        self,
        records: Sequence[ResearchEvent],
        *,
        transaction_id: str,
    ) -> CommitReceipt:
        with self.writer_lease():
            prepared = _prepare_records(
                records,
                transaction_id=transaction_id,
            )
            parquet_bytes, observed = self._stage_parquet(prepared)
            manifest = self._build_manifest(
                transaction_id=transaction_id,
                records=observed,
                parquet_bytes=parquet_bytes,
            )

            existing = self._existing_transaction(transaction_id)
            if existing is not None:
                self._verify_partition(existing)
                if (
                    existing.file_sha256 == manifest.file_sha256
                    and existing.content_sha256 == manifest.content_sha256
                    and existing.logical_location == manifest.logical_location
                ):
                    return self._receipt(
                        existing,
                        CommitDisposition.REPLAY_IDENTICAL,
                    )
                raise ResearchStoreError("TRANSACTION_CONFLICT")

            committed_ids = {
                record.record_id for record in self.iter_committed_records()
            }
            if committed_ids.intersection(
                record.record_id for record in prepared
            ):
                raise ResearchStoreError("DUPLICATE_RECORD_ID")

            parquet_path = _target_path(
                self._root,
                manifest.logical_location,
                create_parents=True,
            )
            try:
                parquet_disposition = _publish_immutable(
                    parquet_path,
                    parquet_bytes,
                )
            except ResearchStoreError as exc:
                if exc.code == "IMMUTABLE_TARGET_CONFLICT":
                    raise ResearchStoreError("TRANSACTION_CONFLICT") from exc
                raise
            self._verify_partition(manifest)

            manifest_location = (
                "research/manifests/partitions/"
                f"{manifest.partition_manifest_id}.json"
            )
            manifest_path = _target_path(
                self._root,
                manifest_location,
                create_parents=True,
            )
            manifest_disposition = _publish_immutable(
                manifest_path,
                canonical_manifest_bytes(manifest),
            )
            disposition = (
                CommitDisposition.REPLAY_IDENTICAL
                if parquet_disposition is _PublishDisposition.REPLAY_IDENTICAL
                and manifest_disposition
                is _PublishDisposition.REPLAY_IDENTICAL
                else CommitDisposition.CREATED
            )
            return self._receipt(manifest, disposition)

    def iter_committed_records(self) -> Iterator[ResearchEvent]:
        seen: set[str] = set()
        for manifest in self._committed_manifests():
            for record in self._verify_partition(manifest):
                if record.record_id in seen:
                    raise ResearchStoreError("DUPLICATE_RECORD_ID")
                seen.add(record.record_id)
                yield record

    def test_write_partition_without_manifest(
        self,
        records: Sequence[ResearchEvent],
        *,
        transaction_id: str | None = None,
    ) -> CommitReceipt:
        if not records:
            raise ResearchStoreError("RECORDS_MUST_NOT_BE_EMPTY")
        selected_transaction_id = transaction_id or records[0].transaction_id
        with self.writer_lease():
            prepared = _prepare_records(
                records,
                transaction_id=selected_transaction_id,
            )
            parquet_bytes, observed = self._stage_parquet(prepared)
            manifest = self._build_manifest(
                transaction_id=selected_transaction_id,
                records=observed,
                parquet_bytes=parquet_bytes,
            )
            parquet_path = _target_path(
                self._root,
                manifest.logical_location,
                create_parents=True,
            )
            disposition = _publish_immutable(parquet_path, parquet_bytes)
            self._verify_partition(manifest)
            return self._receipt(
                manifest,
                CommitDisposition(disposition),
            )

    def rebuild_projection(self) -> ProjectionReceipt:
        manifests = self._committed_manifests()
        records: list[ResearchEvent] = []
        for manifest in manifests:
            records.extend(self._verify_partition(manifest))

        stable_ids: dict[tuple[str, str], list[ResearchEvent]] = {}
        for record in records:
            payload = _payload_object(record)
            stable_id = _projection_stable_id(record, payload)
            key = (str(record.record_kind), stable_id)
            related = stable_ids.setdefault(key, [])
            for previous in related:
                if (
                    previous.payload_sha256 != record.payload_sha256
                    and previous.supersedes_record_id != record.record_id
                    and record.supersedes_record_id != previous.record_id
                ):
                    raise ResearchStoreError("DUPLICATE_STABLE_ID_CONFLICT")
            related.append(record)

        projection_path = _target_path(
            self._root,
            RESEARCH_PROJECTION_LOCATION,
            create_parents=True,
        )
        temporary_path = projection_path.with_name(
            f".{projection_path.name}.{uuid.uuid4().hex}.tmp"
        )
        connection: duckdb.DuckDBPyConnection | None = None
        try:
            try:
                ddl = _PROJECTION_DDL_PATH.read_text(encoding="utf-8")
            except OSError as exc:
                raise ResearchStoreError("PROJECTION_DDL_UNAVAILABLE") from exc
            connection = duckdb.connect(
                str(temporary_path),
                config={
                    "enable_external_access": "false",
                    "allow_unsigned_extensions": "false",
                },
            )
            connection.execute("SET TimeZone = 'UTC'")
            connection.execute(ddl)
            if records:
                load_table = pa.Table.from_pylist(
                    [
                        dict(
                            zip(
                                _PROJECTION_COLUMNS,
                                _projection_record_row(record),
                                strict=True,
                            )
                        )
                        for record in records
                    ]
                )
                connection.register("_projection_load", load_table)
                connection.execute(
                    """
                    INSERT INTO _research_events
                    SELECT * FROM _projection_load
                    """
                )
                connection.unregister("_projection_load")
            connection.execute("SET lock_configuration = true")

            observed_count = connection.execute(
                "SELECT count(*) FROM _research_events"
            ).fetchone()[0]
            if observed_count != len(records):
                raise ResearchStoreError("PROJECTION_RECORD_COUNT_MISMATCH")
            view_names = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT table_name
                    FROM information_schema.views
                    WHERE table_schema = 'main'
                    """
                ).fetchall()
            }
            if set(_PROJECTION_VIEWS) - view_names:
                raise ResearchStoreError("PROJECTION_VIEW_MISSING")
            invalid_negative = connection.execute(
                """
                SELECT count(*)
                FROM experiment_runs
                WHERE run_event_kind = 'RUN_INVALID'
                  AND trial_outcome = 'NEGATIVE'
                """
            ).fetchone()[0]
            if invalid_negative:
                raise ResearchStoreError("INVALID_IS_NOT_NEGATIVE")
            for view in _PROJECTION_VIEWS:
                connection.execute(
                    f'SELECT * FROM "{view}" ORDER BY ALL LIMIT 10'
                ).fetchall()

            projection_digest = _projection_export_digest(
                connection,
                manifests=manifests,
            )
            connection.execute(
                """
                INSERT INTO _projection_metadata VALUES (TRUE, ?, ?, ?, '1.0')
                """,
                [
                    projection_digest,
                    len(records),
                    len(manifests),
                ],
            )
            connection.execute("CHECKPOINT")
            connection.close()
            connection = None

            verification = duckdb.connect(
                str(temporary_path),
                read_only=True,
                config={
                    "enable_external_access": "false",
                    "allow_unsigned_extensions": "false",
                },
            )
            try:
                verification.execute("SET TimeZone = 'UTC'")
                verification.execute("SET lock_configuration = true")
                metadata = verification.execute(
                    """
                    SELECT
                        projection_digest_sha256,
                        record_count,
                        partition_count
                    FROM _projection_metadata
                    WHERE singleton = TRUE
                    """
                ).fetchone()
                if metadata != (
                    projection_digest,
                    len(records),
                    len(manifests),
                ):
                    raise ResearchStoreError("PROJECTION_METADATA_READBACK_MISMATCH")
                verification.execute(
                    "SELECT * FROM prior_work ORDER BY ALL LIMIT 10"
                ).fetchall()
            finally:
                verification.close()

            os.replace(temporary_path, projection_path)
            return ProjectionReceipt(
                status="READY",
                logical_uri=RESEARCH_PROJECTION_LOGICAL_URI,
                projection_digest_sha256=projection_digest,
                record_count=len(records),
                partition_count=len(manifests),
            )
        except ResearchStoreError:
            raise
        except (OSError, ValueError, duckdb.Error) as exc:
            raise ResearchStoreError("PROJECTION_REBUILD_FAILED") from exc
        finally:
            if connection is not None:
                connection.close()
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                raise ResearchStoreError("TEMPORARY_CLEANUP_FAILED") from exc

    def find_completed_run(
        self,
        run_key_sha256: str,
    ) -> RunPassport | None:
        if _HASH64_RE.fullmatch(run_key_sha256) is None:
            raise ResearchStoreError("RUN_KEY_SHA256_INVALID")
        projection_path = self._root / RESEARCH_PROJECTION_LOCATION
        if projection_path.is_file() and not projection_path.is_symlink():
            connection: duckdb.DuckDBPyConnection | None = None
            try:
                connection = duckdb.connect(
                    str(projection_path),
                    read_only=True,
                    config={
                        "enable_external_access": "false",
                        "allow_unsigned_extensions": "false",
                    },
                )
                connection.execute("SET TimeZone = 'UTC'")
                connection.execute("SET lock_configuration = true")
                row = connection.execute(
                    """
                    SELECT run_id, payload_json
                    FROM experiment_runs
                    WHERE run_event_kind = 'RUN_COMPLETED'
                      AND run_key_sha256 = ?
                    ORDER BY record_id
                    LIMIT 1
                    """,
                    [run_key_sha256],
                ).fetchone()
                if row is not None:
                    payload = json.loads(row[1])
                    if not isinstance(payload, dict):
                        raise ResearchStoreError("RUN_COMPLETED_PASSPORT_INVALID")
                    return RunPassport(
                        run_id=row[0],
                        run_key_sha256=run_key_sha256,
                        payload=payload,
                    )
            except ResearchStoreError:
                raise
            except (ValueError, json.JSONDecodeError, duckdb.Error) as exc:
                raise ResearchStoreError("PROJECTION_QUERY_FAILED") from exc
            finally:
                if connection is not None:
                    connection.close()
        for record in self.iter_committed_records():
            if record.record_kind != RecordKind.RUN_COMPLETED:
                continue
            try:
                payload = json.loads(record.payload_json)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ResearchStoreError("PAYLOAD_JSON_INVALID") from exc
            if (
                isinstance(payload, dict)
                and payload.get("run_key_sha256") == run_key_sha256
            ):
                run_id = payload.get("run_id", record.run_id)
                if not isinstance(run_id, str) or not run_id:
                    raise ResearchStoreError("RUN_COMPLETED_PASSPORT_INVALID")
                return RunPassport(
                    run_id=run_id,
                    run_key_sha256=run_key_sha256,
                    payload=payload,
                )
        return None


__all__ = [
    "CommitDisposition",
    "CommitReceipt",
    "ProjectionReceipt",
    "RESEARCH_EVENT_ARROW_SCHEMA",
    "RecordKind",
    "ResearchEvent",
    "ResearchStore",
    "ResearchStoreError",
    "RunPassport",
]
