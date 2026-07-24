"""Deterministic dataset and partition manifest identity for TASK-06."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import TypeAlias

from pydantic import ValidationError

from solana_alpha_lab.contracts.schema_v1 import (
    DatasetManifest,
    PartitionManifest,
)

MANIFEST_IDENTITY_PROFILE = "smial-manifest-identity-v1"
DATASET_FINGERPRINT_PROFILE = "smial-dataset-fingerprint-v1"
DATASET_MANIFEST_CONTENT_PROFILE = "smial-dataset-manifest-content-v1"

JsonValue: TypeAlias = (
    None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]
)

_PUBLIC_IDENTIFIER_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/=-]{0,255}"
)
_LOGICAL_LOCATION_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._=/+-]{0,1023}"
)
_HASH64_RE = re.compile(r"[0-9a-f]{64}")
_WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:")
_DATASET_MANIFEST_ID_RE = re.compile(r"dataset-[0-9a-f]{64}")


class ManifestContractError(ValueError):
    """The caller supplied an incoherent public manifest claim."""


class ManifestIntegrityError(ManifestContractError):
    """A manifest no longer matches its deterministic identity."""


def _public_identifier(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or _PUBLIC_IDENTIFIER_RE.fullmatch(value) is None
        or value.startswith("/")
        or "\\" in value
        or "://" in value
        or _WINDOWS_DRIVE_RE.match(value) is not None
    ):
        raise ManifestContractError(f"{name}_must_be_public_identifier")
    return value


def _hash64(name: str, value: str) -> str:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise ManifestContractError(f"{name}_must_be_lowercase_sha256")
    return value


def _as_utc(name: str, value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ManifestContractError(f"{name}_must_be_datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ManifestContractError(f"{name}_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


def _timestamp_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _json_ready(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, datetime):
        utc_value = _as_utc("manifest_datetime", value)
        assert utc_value is not None
        return _timestamp_text(utc_value)
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManifestContractError(
                    "manifest_object_key_must_be_text"
                )
            result[key] = _json_ready(item)
        return result
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [_json_ready(item) for item in value]
    raise ManifestContractError("unsupported_manifest_value")


def _canonical_json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            _json_ready(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ManifestContractError(
            "manifest_canonicalization_failed"
        ) from exc
    return text.encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _logical_location(value: str) -> str:
    if (
        not isinstance(value, str)
        or _LOGICAL_LOCATION_RE.fullmatch(value) is None
    ):
        raise ManifestContractError("logical_location_invalid")
    if (
        value.startswith("/")
        or "\\" in value
        or "://" in value
        or "?" in value
        or "#" in value
        or _WINDOWS_DRIVE_RE.match(value) is not None
    ):
        raise ManifestContractError("logical_location_must_be_relative")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ManifestContractError("logical_location_has_unsafe_segment")
    if not value.endswith(".parquet"):
        raise ManifestContractError("logical_location_must_be_parquet")
    return value


def compute_dataset_manifest_id(
    dataset_id: str,
    dataset_version: str,
) -> str:
    """Return the stable identity for one immutable dataset version."""

    safe_dataset_id = _public_identifier("dataset_id", dataset_id)
    safe_dataset_version = _public_identifier(
        "dataset_version",
        dataset_version,
    )
    claim = {
        "dataset_id": safe_dataset_id,
        "dataset_version": safe_dataset_version,
        "profile": MANIFEST_IDENTITY_PROFILE,
    }
    return f"dataset-{_digest(claim)}"


def _partition_claim(
    *,
    dataset_manifest_id: str,
    partition_id: str,
    logical_location: str,
    file_sha256: str,
    content_sha256: str,
    row_count: int,
    min_event_time: datetime | None,
    max_event_time: datetime | None,
    min_available_to_strategy_at: datetime | None,
    max_available_to_strategy_at: datetime | None,
    first_reliable_available_at: datetime,
    created_at: datetime,
) -> dict[str, JsonValue]:
    return {
        "content_sha256": content_sha256,
        "created_at": _timestamp_text(created_at),
        "dataset_manifest_id": dataset_manifest_id,
        "file_sha256": file_sha256,
        "first_reliable_available_at": _timestamp_text(
            first_reliable_available_at
        ),
        "logical_location": logical_location,
        "max_available_to_strategy_at": _timestamp_text(
            max_available_to_strategy_at
        ),
        "max_event_time": _timestamp_text(max_event_time),
        "min_available_to_strategy_at": _timestamp_text(
            min_available_to_strategy_at
        ),
        "min_event_time": _timestamp_text(min_event_time),
        "partition_id": partition_id,
        "profile": MANIFEST_IDENTITY_PROFILE,
        "row_count": row_count,
    }


def build_partition_manifest(
    *,
    dataset_id: str,
    dataset_version: str,
    partition_id: str,
    logical_location: str,
    file_sha256: str,
    content_sha256: str,
    row_count: int,
    first_reliable_available_at: datetime,
    created_at: datetime,
    min_event_time: datetime | None = None,
    max_event_time: datetime | None = None,
    min_available_to_strategy_at: datetime | None = None,
    max_available_to_strategy_at: datetime | None = None,
) -> PartitionManifest:
    """Build a strict partition manifest without reading or writing a file."""

    dataset_manifest_id = compute_dataset_manifest_id(
        dataset_id,
        dataset_version,
    )
    safe_partition_id = _public_identifier("partition_id", partition_id)
    safe_location = _logical_location(logical_location)
    safe_file_hash = _hash64("file_sha256", file_sha256)
    safe_content_hash = _hash64("content_sha256", content_sha256)
    if (
        isinstance(row_count, bool)
        or not isinstance(row_count, int)
        or row_count < 0
    ):
        raise ManifestContractError("row_count_must_be_non_negative_integer")

    utc_min_event = _as_utc("min_event_time", min_event_time)
    utc_max_event = _as_utc("max_event_time", max_event_time)
    utc_min_available = _as_utc(
        "min_available_to_strategy_at",
        min_available_to_strategy_at,
    )
    utc_max_available = _as_utc(
        "max_available_to_strategy_at",
        max_available_to_strategy_at,
    )
    utc_reliable = _as_utc(
        "first_reliable_available_at",
        first_reliable_available_at,
    )
    utc_created = _as_utc("created_at", created_at)
    assert utc_reliable is not None
    assert utc_created is not None
    if (
        utc_max_available is not None
        and utc_created < utc_max_available
    ):
        raise ManifestContractError(
            "partition_created_before_available_content"
        )

    claim = _partition_claim(
        dataset_manifest_id=dataset_manifest_id,
        partition_id=safe_partition_id,
        logical_location=safe_location,
        file_sha256=safe_file_hash,
        content_sha256=safe_content_hash,
        row_count=row_count,
        min_event_time=utc_min_event,
        max_event_time=utc_max_event,
        min_available_to_strategy_at=utc_min_available,
        max_available_to_strategy_at=utc_max_available,
        first_reliable_available_at=utc_reliable,
        created_at=utc_created,
    )
    manifest = PartitionManifest(
        partition_manifest_id=f"partition-{_digest(claim)}",
        dataset_manifest_id=dataset_manifest_id,
        partition_id=safe_partition_id,
        logical_location=safe_location,
        file_sha256=safe_file_hash,
        content_sha256=safe_content_hash,
        row_count=row_count,
        min_event_time=utc_min_event,
        max_event_time=utc_max_event,
        min_available_to_strategy_at=utc_min_available,
        max_available_to_strategy_at=utc_max_available,
        first_reliable_available_at=utc_reliable,
        created_at=utc_created,
    )
    verify_partition_manifest(manifest)
    return manifest


def _partition_fingerprint_projection(
    manifest: PartitionManifest,
) -> dict[str, JsonValue]:
    claim = _partition_claim(
        dataset_manifest_id=manifest.dataset_manifest_id,
        partition_id=manifest.partition_id,
        logical_location=manifest.logical_location,
        file_sha256=manifest.file_sha256,
        content_sha256=manifest.content_sha256,
        row_count=manifest.row_count,
        min_event_time=manifest.min_event_time,
        max_event_time=manifest.max_event_time,
        min_available_to_strategy_at=(
            manifest.min_available_to_strategy_at
        ),
        max_available_to_strategy_at=(
            manifest.max_available_to_strategy_at
        ),
        first_reliable_available_at=manifest.first_reliable_available_at,
        created_at=manifest.created_at,
    )
    claim["partition_manifest_id"] = manifest.partition_manifest_id
    return claim


def verify_partition_manifest(manifest: PartitionManifest) -> None:
    """Fail if a partition claim and its deterministic identity disagree."""

    try:
        PartitionManifest.model_validate(
            manifest.model_dump(mode="python")
        )
        if (
            _DATASET_MANIFEST_ID_RE.fullmatch(
                manifest.dataset_manifest_id
            )
            is None
        ):
            raise ManifestContractError("dataset_manifest_id_invalid")
        _public_identifier("partition_id", manifest.partition_id)
        _logical_location(manifest.logical_location)
        _hash64("file_sha256", manifest.file_sha256)
        _hash64("content_sha256", manifest.content_sha256)
        if (
            isinstance(manifest.row_count, bool)
            or not isinstance(manifest.row_count, int)
            or manifest.row_count < 0
        ):
            raise ManifestContractError(
                "row_count_must_be_non_negative_integer"
            )
    except (AttributeError, ManifestContractError, ValidationError) as exc:
        raise ManifestIntegrityError("partition_claim_invalid") from exc

    claim = _partition_fingerprint_projection(manifest)
    claim.pop("partition_manifest_id")
    expected = f"partition-{_digest(claim)}"
    if manifest.partition_manifest_id != expected:
        raise ManifestIntegrityError("partition_manifest_id_mismatch")


def _ordered_partitions(
    partitions: Sequence[PartitionManifest],
) -> tuple[PartitionManifest, ...]:
    if isinstance(partitions, (str, bytes, bytearray)):
        raise ManifestContractError("partitions_must_be_a_sequence")
    prepared: list[PartitionManifest] = []
    for manifest in partitions:
        if not isinstance(manifest, PartitionManifest):
            raise ManifestContractError(
                "partition_must_be_partition_manifest"
            )
        verify_partition_manifest(manifest)
        prepared.append(manifest)

    for name, values in (
        (
            "partition_manifest_id",
            [item.partition_manifest_id for item in prepared],
        ),
        ("partition_id", [item.partition_id for item in prepared]),
        (
            "logical_location",
            [item.logical_location for item in prepared],
        ),
    ):
        if len(values) != len(set(values)):
            raise ManifestContractError(f"duplicate_{name}")

    return tuple(
        sorted(
            prepared,
            key=lambda item: (
                item.partition_id,
                item.logical_location,
                item.partition_manifest_id,
            ),
        )
    )


def compute_dataset_fingerprint(
    *,
    dataset_id: str,
    dataset_version: str,
    schema_id: str,
    schema_sha256: str,
    partitions: Sequence[PartitionManifest],
) -> str:
    """Hash an order-independent, exact partition inventory."""

    dataset_manifest_id = compute_dataset_manifest_id(
        dataset_id,
        dataset_version,
    )
    safe_schema_id = _public_identifier("schema_id", schema_id)
    safe_schema_hash = _hash64("schema_sha256", schema_sha256)
    ordered = _ordered_partitions(partitions)
    if any(
        item.dataset_manifest_id != dataset_manifest_id
        for item in ordered
    ):
        raise ManifestContractError("partition_parent_mismatch")
    claim = {
        "dataset_manifest_id": dataset_manifest_id,
        "partitions": [
            _partition_fingerprint_projection(item) for item in ordered
        ],
        "profile": DATASET_FINGERPRINT_PROFILE,
        "schema_id": safe_schema_id,
        "schema_sha256": safe_schema_hash,
    }
    return _digest(claim)


def _dataset_content_claim(
    manifest: DatasetManifest,
) -> dict[str, JsonValue]:
    return {
        "created_at": _timestamp_text(manifest.created_at),
        "dataset_fingerprint": manifest.dataset_fingerprint,
        "dataset_id": manifest.dataset_id,
        "dataset_manifest_id": manifest.dataset_manifest_id,
        "dataset_version": manifest.dataset_version,
        "first_reliable_available_at": _timestamp_text(
            manifest.first_reliable_available_at
        ),
        "generation_run_id": manifest.generation_run_id,
        "generation_task_id": manifest.generation_task_id,
        "profile": DATASET_MANIFEST_CONTENT_PROFILE,
        "schema_id": manifest.schema_id,
        "schema_sha256": manifest.schema_sha256,
        "validation_receipt_sha256": (
            manifest.validation_receipt_sha256
        ),
    }


def _validate_dataset_partition_times(
    created_at: datetime,
    partitions: Sequence[PartitionManifest],
) -> None:
    if any(
        created_at < item.first_reliable_available_at
        for item in partitions
    ):
        raise ManifestContractError(
            "dataset_created_before_partition_reliable"
        )


def build_dataset_manifest(
    *,
    dataset_id: str,
    dataset_version: str,
    schema_id: str,
    schema_sha256: str,
    generation_task_id: str,
    generation_run_id: str,
    validation_receipt_sha256: str,
    first_reliable_available_at: datetime,
    created_at: datetime,
    partitions: Sequence[PartitionManifest],
) -> DatasetManifest:
    """Build an immutable dataset root from already validated partitions."""

    dataset_manifest_id = compute_dataset_manifest_id(
        dataset_id,
        dataset_version,
    )
    safe_schema_id = _public_identifier("schema_id", schema_id)
    safe_schema_hash = _hash64("schema_sha256", schema_sha256)
    safe_task_id = _public_identifier(
        "generation_task_id",
        generation_task_id,
    )
    safe_run_id = _public_identifier(
        "generation_run_id",
        generation_run_id,
    )
    safe_receipt_hash = _hash64(
        "validation_receipt_sha256",
        validation_receipt_sha256,
    )
    utc_reliable = _as_utc(
        "first_reliable_available_at",
        first_reliable_available_at,
    )
    utc_created = _as_utc("created_at", created_at)
    assert utc_reliable is not None
    assert utc_created is not None
    ordered = _ordered_partitions(partitions)
    _validate_dataset_partition_times(utc_created, ordered)
    dataset_fingerprint = compute_dataset_fingerprint(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_id=safe_schema_id,
        schema_sha256=safe_schema_hash,
        partitions=ordered,
    )

    provisional = DatasetManifest(
        dataset_manifest_id=dataset_manifest_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_id=safe_schema_id,
        schema_sha256=safe_schema_hash,
        dataset_fingerprint=dataset_fingerprint,
        generation_task_id=safe_task_id,
        generation_run_id=safe_run_id,
        validation_receipt_sha256=safe_receipt_hash,
        first_reliable_available_at=utc_reliable,
        created_at=utc_created,
        content_sha256="0" * 64,
    )
    manifest = provisional.model_copy(
        update={"content_sha256": _digest(_dataset_content_claim(provisional))}
    )
    verify_dataset_manifest(manifest, partitions=ordered)
    return manifest


def verify_dataset_manifest(
    manifest: DatasetManifest,
    *,
    partitions: Sequence[PartitionManifest],
) -> None:
    """Fail if the dataset root, content hash or inventory disagree."""

    try:
        DatasetManifest.model_validate(manifest.model_dump(mode="python"))
        expected_id = compute_dataset_manifest_id(
            manifest.dataset_id,
            manifest.dataset_version,
        )
        _public_identifier("schema_id", manifest.schema_id)
        _hash64("schema_sha256", manifest.schema_sha256)
        _public_identifier(
            "generation_task_id",
            manifest.generation_task_id,
        )
        _public_identifier(
            "generation_run_id",
            manifest.generation_run_id,
        )
        _hash64(
            "validation_receipt_sha256",
            manifest.validation_receipt_sha256,
        )
        _hash64("dataset_fingerprint", manifest.dataset_fingerprint)
        _hash64("content_sha256", manifest.content_sha256)
        _validate_dataset_partition_times(
            manifest.created_at,
            partitions,
        )
        expected_fingerprint = compute_dataset_fingerprint(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.dataset_version,
            schema_id=manifest.schema_id,
            schema_sha256=manifest.schema_sha256,
            partitions=partitions,
        )
        expected_content_hash = _digest(_dataset_content_claim(manifest))
    except (AttributeError, ManifestContractError, ValidationError) as exc:
        raise ManifestIntegrityError("dataset_claim_invalid") from exc

    if manifest.dataset_manifest_id != expected_id:
        raise ManifestIntegrityError("dataset_manifest_id_mismatch")
    if manifest.dataset_fingerprint != expected_fingerprint:
        raise ManifestIntegrityError("dataset_fingerprint_mismatch")
    if manifest.content_sha256 != expected_content_hash:
        raise ManifestIntegrityError("dataset_content_hash_mismatch")


def canonical_manifest_bytes(
    manifest: DatasetManifest | PartitionManifest,
) -> bytes:
    """Serialize all model fields as deterministic UTF-8 JSON bytes."""

    if not isinstance(manifest, (DatasetManifest, PartitionManifest)):
        raise ManifestContractError("unsupported_manifest_type")
    return _canonical_json_bytes(manifest.model_dump(mode="python"))
