"""TASK-06-valid LIVE CORPUS metadata publication (repair + import).

Not a second identity profile. Callers remain import_live_cohort /
repair_live_corpus_manifests.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.discovery_evidence_release import (
    _publish_bytes,
    _render_utc,
    sha256_bytes,
)
from solana_alpha_lab.factory.live_corpus_logical_rows import (
    CANONICAL_METADATA_SUFFIX,
    KIND_CENSUS,
    KIND_OBS,
    LOGICAL_ROW_PROFILE,
    VALIDATION_RECEIPT_SCHEMA,
    VALIDATION_RECEIPT_SCHEMA_VERSION,
    LiveCorpusLogicalRowError,
    LiveCorpusPartitionClaims,
    live_corpus_schema_sha256,
    measure_live_corpus_parquet,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    sha256_file_streaming,
    sha256_files_concat_streaming,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LIVE_EVIDENCE_ROLE,
    REQUIRED_LABELS,
    LiveCohortReleaseError,
    load_live_corpus_lineage,
    parse_live_corpus_utc,
    verify_live_cohort,
    write_live_corpus_lineage,
)
from solana_alpha_lab.factory.live_cohort_schedule_artifact import (
    OBSERVATION_SCHEDULE_ARTIFACT_NAME,
    RELEASE_SCHEMA_VERSION_SELF_CONTAINED,
    SCHEDULE_ARTIFACT_MISSING,
    SCHEDULE_PRODUCER_UNBOUND,
    decode_schedule_artifact,
)
from solana_alpha_lab.storage.manifests import (
    ManifestContractError,
    ManifestIntegrityError,
    build_dataset_manifest,
    build_partition_manifest,
    canonical_manifest_bytes,
    compute_dataset_fingerprint,
    compute_dataset_manifest_id,
    verify_dataset_manifest,
    verify_partition_manifest,
)

CORPUS_DATASET_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
CORPUS_SCHEMA_ID = "SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
CANONICAL_GENERATION_TASK_IMPORT = "LIVE-COHORT-DISCOVERY-RELEASE-SERIES-V1"
CANONICAL_GENERATION_TASK_REPAIR = "LIVE-CORPUS-MANIFEST-CONTRACT-REPAIR-V1"
LEGACY_CORPUS_REQUIRES_REPAIR = "CURRENT_CORPUS_LEGACY_METADATA_REQUIRES_REPAIR"
COMMIT_POINT_KIND = "LIVE_LIFECYCLE_DISCOVERY_CORPUS_PUBLICATION_V1"
REPAIR_GENERATION_REASON = "METADATA_CONTRACT_REPAIR"
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
RELEASE_MANIFEST_NAME = "release_manifest.json"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LiveCohortReleaseError(code)


def _stamp_utc(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def canonical_dataset_version(version: str) -> str:
    if not isinstance(version, str) or not version:
        raise LiveCohortReleaseError("DATASET_VERSION_INVALID")
    if version.endswith(CANONICAL_METADATA_SUFFIX):
        return version
    return f"{version}{CANONICAL_METADATA_SUFFIX}"


def repair_dataset_version(
    version: str, schema_sha256: str, composition: Sequence[Mapping[str, Any]],
) -> str:
    """LIVE-local metadata revision; TASK-06 identity itself is unchanged."""
    base = canonical_dataset_version(version).removesuffix(CANONICAL_METADATA_SUFFIX)
    base = re.sub(r"\.metadata-[0-9a-f]{64}$", "", base)
    metadata_sha = sha256_bytes(_canonical_receipt_bytes({
        "profile": "LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2",
        "metadata_contract": {
            "dataset_id": CORPUS_DATASET_ID,
            "schema_id": CORPUS_SCHEMA_ID,
            "schema_sha256": schema_sha256,
            "logical_row_profile": LOGICAL_ROW_PROFILE,
            "validation_receipt_schema": VALIDATION_RECEIPT_SCHEMA,
            "validation_receipt_schema_version": VALIDATION_RECEIPT_SCHEMA_VERSION,
            "publication_commit_point": COMMIT_POINT_KIND,
            "publication_clock_policy": "TARGET_FROZEN_CLOCK_V1",
            "canonical_metadata_suffix": CANONICAL_METADATA_SUFFIX,
            "repair_generation_task_id": CANONICAL_GENERATION_TASK_REPAIR,
            "repair_generation_reason": REPAIR_GENERATION_REASON,
            "required_labels": dict(REQUIRED_LABELS),
        },
        "composition": [{key: item[key] for key in ("cohort_id", "content_sha256", "release_id")}
                        for item in composition],
    }))
    return f"{base}.metadata-{metadata_sha}{CANONICAL_METADATA_SUFFIX}"


def _safe_path(data_root: Path, path: Path) -> None:
    root = Path(data_root).absolute()
    absolute = path.absolute()
    _require(absolute.is_relative_to(root), "LIVE_CORPUS_PATH_INTEGRITY")
    for item in (absolute, *absolute.parents):
        _require(not item.is_symlink() and not item.is_junction(), "LIVE_CORPUS_PATH_INTEGRITY")
        if item == root:
            break


def _publish_metadata(data_root: Path, path: Path, payload: bytes) -> None:
    _safe_path(data_root, path)
    _safe_path(data_root, path.with_name(f"{path.name}.tmp"))
    try:
        _publish_bytes(path, payload)
    except Exception as exc:
        if str(exc) == "CANONICAL_TARGET_CONFLICT":
            raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT") from exc
        raise


def _manifests_dir(data_root: Path) -> Path:
    return Path(data_root) / "datasets" / "manifests"


def _atomic_replace_json(path: Path, payload: Mapping[str, Any]) -> None:
    _require(not path.is_symlink() and not path.with_name(f"{path.name}.tmp").is_symlink(),
             "LIVE_CORPUS_PATH_INTEGRITY")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(encoded)
    tmp.replace(path)


def _wrap_logical(exc: LiveCorpusLogicalRowError) -> LiveCohortReleaseError:
    return LiveCohortReleaseError(exc.code)


def _wrap_manifest(exc: Exception, code: str) -> LiveCohortReleaseError:
    return LiveCohortReleaseError(code)


def _load_dataset_manifest(data_root: Path, dataset_manifest_id: str) -> DatasetManifest:
    path = _manifests_dir(data_root) / f"{dataset_manifest_id}.json"
    _require(path.is_file() and not path.is_symlink(), "DATASET_MANIFEST_MISSING")
    try:
        return DatasetManifest.model_validate_json(path.read_bytes())
    except Exception as exc:
        raise LiveCohortReleaseError("DATASET_MANIFEST_CORRUPT") from exc


def _load_partitions_for_dataset(
    data_root: Path, dataset_manifest_id: str
) -> list[PartitionManifest]:
    partition_dir = _manifests_dir(data_root) / "partitions"
    if not partition_dir.is_dir():
        return []
    found: list[PartitionManifest] = []
    for path in sorted(partition_dir.glob("partition-*.json")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("dataset_manifest_id") or "") != dataset_manifest_id:
            continue
        try:
            found.append(PartitionManifest.model_validate_json(path.read_bytes()))
        except Exception as exc:
            raise LiveCohortReleaseError("PARTITION_MANIFEST_CORRUPT") from exc
    found.sort(
        key=lambda item: (
            item.partition_id,
            item.logical_location,
            item.partition_manifest_id,
        )
    )
    return found


def _kind_for_partition_id(partition_id: str) -> str:
    if partition_id.endswith("-CENSUS"):
        return KIND_CENSUS
    if partition_id.endswith("-OBS"):
        return KIND_OBS
    raise LiveCohortReleaseError("LIVE_CORPUS_PARTITION_KIND_INVALID")


def claims_from_partition(part: PartitionManifest) -> LiveCorpusPartitionClaims:
    return LiveCorpusPartitionClaims(
        kind=_kind_for_partition_id(part.partition_id),
        partition_id=part.partition_id,
        logical_location=part.logical_location,
        file_sha256=part.file_sha256,
        content_sha256=part.content_sha256,
        row_count=part.row_count,
        min_event_time=part.min_event_time,
        max_event_time=part.max_event_time,
        min_available_to_strategy_at=part.min_available_to_strategy_at,
        max_available_to_strategy_at=part.max_available_to_strategy_at,
    )


def _canonical_receipt_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        text = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise LiveCohortReleaseError("VALIDATION_RECEIPT_CANONICALIZATION_FAILED") from exc
    return text.encode("utf-8")


def _freeze_publication_clock(
    data_root: Path,
    dataset_manifest_id: str,
    proposed: datetime,
) -> datetime:
    path = _manifests_dir(data_root) / f"{dataset_manifest_id}.publication-clock.json"
    _safe_path(data_root, path)
    encoded = json.dumps(
        {
            "created_at": _stamp_utc(proposed),
            "first_reliable_available_at": _stamp_utc(proposed),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if path.is_file() and not path.is_symlink():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LiveCohortReleaseError("PUBLICATION_CLOCK_CORRUPT") from exc
        _require(isinstance(loaded, Mapping), "PUBLICATION_CLOCK_CORRUPT")
        raw = loaded.get("created_at")
        _require(isinstance(raw, str) and raw, "PUBLICATION_CLOCK_CORRUPT")
        _require(loaded == {"created_at": raw, "first_reliable_available_at": raw},
                 "PUBLICATION_CLOCK_CORRUPT")
        return _parse_utc_local(raw)
    _publish_metadata(data_root, path, encoded)
    return proposed


def _parse_utc_local(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LiveCohortReleaseError("PUBLICATION_CLOCK_CORRUPT") from exc
    if parsed.tzinfo is None:
        raise LiveCohortReleaseError("PUBLICATION_CLOCK_CORRUPT")
    return parsed.astimezone(UTC)


def _published_marker_ok(published_path: Path, dataset: DatasetManifest) -> bool:
    if not published_path.is_file() or published_path.is_symlink():
        return False
    try:
        published = json.loads(published_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(published, dict)
        and published.get("dataset_fingerprint") == dataset.dataset_fingerprint
        and published.get("dataset_manifest_id") == dataset.dataset_manifest_id
        and published.get("published_at") == _stamp_utc(dataset.created_at)
        and published.get("metadata_clock_at") == _stamp_utc(dataset.created_at)
    )


def _cohorts_from_lineage(lineage: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = lineage.get("cohorts")
    _require(isinstance(raw, list) and raw, "CORPUS_LINEAGE_INCOMPLETE")
    out: list[dict[str, Any]] = []
    for item in raw:
        _require(isinstance(item, Mapping), "CORPUS_LINEAGE_INCOMPLETE")
        out.append(dict(item))
    return out


_IMPORT_PARQUET_BYTES = {"historical": 0, "new": 0}


def reset_import_parquet_accounting() -> None:
    _IMPORT_PARQUET_BYTES["historical"] = 0
    _IMPORT_PARQUET_BYTES["new"] = 0


def _parquet_size_path(data_root: Path, partition_id: str) -> Path:
    return _manifests_dir(data_root) / "partitions" / f"{partition_id}.bytes"


def _recorded_parquet_size(data_root: Path, partition_id: str) -> int | None:
    path = _parquet_size_path(data_root, partition_id)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
        size = int(text)
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if size < 0:
        return None
    return size


def _write_recorded_parquet_size(data_root: Path, partition_id: str, size: int) -> None:
    path = _parquet_size_path(data_root, partition_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish_bytes(path, str(int(size)).encode("utf-8"))


def import_parquet_accounting() -> dict[str, int]:
    return dict(_IMPORT_PARQUET_BYTES)


def _note_import_parquet_bytes(kind: str, nbytes: int) -> None:
    _IMPORT_PARQUET_BYTES[kind] = int(_IMPORT_PARQUET_BYTES.get(kind) or 0) + int(nbytes)


def inspect_canonical_root(
    data_root: Path,
    dataset_manifest_id: str,
    *,
    verify_parquet_bytes: bool = True,
    expected_schema_sha256: str | None = None,
) -> dict[str, Any]:
    """Return whether a LIVE CORPUS dataset root is TASK-06-valid and published."""

    manifests = _manifests_dir(data_root)
    published_path = manifests / f"{dataset_manifest_id}.published"
    labels_path = manifests / f"{dataset_manifest_id}.labels.json"
    validation_path = manifests / f"{dataset_manifest_id}.validation.json"
    dataset_path = manifests / f"{dataset_manifest_id}.json"
    empty = {
        "artifacts_ok": False,
        "complete": False,
        "dataset": None,
        "partitions": [],
        "reason": "MISSING",
    }
    if not dataset_path.is_file():
        return empty
    try:
        dataset = _load_dataset_manifest(data_root, dataset_manifest_id)
        partitions = _load_partitions_for_dataset(data_root, dataset_manifest_id)
    except Exception:
        return {**empty, "reason": "CORRUPT"}
    if dataset.schema_sha256 != (expected_schema_sha256 or live_corpus_schema_sha256()):
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "SCHEMA_SHA_MISMATCH"}
    if not str(dataset.dataset_version).endswith(CANONICAL_METADATA_SUFFIX):
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "LEGACY_VERSION"}
    if not validation_path.is_file() or validation_path.is_symlink():
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "RECEIPT_MISSING"}
    receipt_bytes = validation_path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "RECEIPT_CORRUPT"}
    if not isinstance(receipt, Mapping):
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "RECEIPT_CORRUPT"}
    if "content_sha256" in receipt or "dataset_content_sha256" in receipt:
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "RECEIPT_CYCLE"}
    if sha256_bytes(receipt_bytes) != dataset.validation_receipt_sha256:
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "RECEIPT_HASH_MISMATCH"}
    try:
        for part in partitions:
            verify_partition_manifest(part)
        verify_dataset_manifest(dataset, partitions=partitions)
    except (ManifestContractError, ManifestIntegrityError):
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "VERIFY_FAIL"}
    if receipt.get("dataset_fingerprint") != dataset.dataset_fingerprint:
        return {**empty, "dataset": dataset, "partitions": partitions, "reason": "FINGERPRINT_MISMATCH"}
    artifacts_ok = True
    labels_ok = False
    labels_payload = None
    if labels_path.is_file() and not labels_path.is_symlink():
        try:
            labels_payload = json.loads(labels_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            labels_payload = None
        labels_ok = (
            isinstance(labels_payload, dict)
            and isinstance(labels_payload.get("dataset_terminal"), str)
            and bool(labels_payload.get("dataset_terminal"))
        )
    published_ok = _published_marker_ok(published_path, dataset)
    composition = receipt.get("corpus_composition")
    if published_ok and labels_ok and isinstance(composition, list) and composition:
        latest_component = composition[-1]
        published_ok = isinstance(latest_component, Mapping) and json.loads(published_path.read_bytes()) == {
            "commit_point": COMMIT_POINT_KIND,
            "cohort_id": latest_component.get("cohort_id"),
            "corpus_version": labels_payload.get("corpus_version"),
            "cumulative_cohort_count": len(composition),
            "dataset_fingerprint": dataset.dataset_fingerprint,
            "dataset_manifest_id": dataset.dataset_manifest_id,
            "metadata_clock_at": _stamp_utc(dataset.created_at),
            "published_at": _stamp_utc(dataset.created_at),
            "release_id": latest_component.get("release_id"),
        }
    else:
        published_ok = False
    clock_path = manifests / f"{dataset_manifest_id}.publication-clock.json"
    _safe_path(data_root, clock_path)
    try:
        stored_clock = json.loads(clock_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        stored_clock = None
    clock_ok = stored_clock == {
        "created_at": _stamp_utc(dataset.created_at),
        "first_reliable_available_at": _stamp_utc(dataset.first_reliable_available_at),
    }
    clock_ok = clock_ok and receipt.get("published_at") == _stamp_utc(dataset.created_at)
    clock_ok = clock_ok and all(
        part.created_at == dataset.created_at and part.first_reliable_available_at == dataset.first_reliable_available_at
        for part in partitions
    )
    parquet_ok = True
    for part in partitions:
        parquet_path = Path(data_root) / part.logical_location
        _safe_path(data_root, parquet_path)
        if parquet_path.is_symlink() or not parquet_path.is_file():
            parquet_ok = False
            break
        size = int(parquet_path.stat().st_size)
        recorded = _recorded_parquet_size(data_root, part.partition_id)
        if recorded is not None and recorded != size:
            parquet_ok = False
            break
        if not verify_parquet_bytes and recorded == size:
            continue
        _note_import_parquet_bytes("historical", size)
        if sha256_file_streaming(parquet_path) != part.file_sha256:
            parquet_ok = False
            break
    complete = artifacts_ok and labels_ok and published_ok and parquet_ok and clock_ok
    if not labels_ok:
        reason = "LABELS_MISSING"
    elif not parquet_ok:
        reason = "CORPUS_PARQUET_SHA_MISMATCH"
    elif not published_ok:
        reason = "UNPUBLISHED"
    elif not clock_ok:
        reason = "PUBLICATION_CLOCK_CORRUPT"
    else:
        reason = "OK"
    return {
        "artifacts_ok": artifacts_ok,
        "complete": complete,
        "dataset": dataset,
        "partitions": partitions,
        "reason": reason,
    }


def _lineage_int(item: Mapping[str, Any], key: str) -> int:
    if key not in item or item[key] is None:
        raise LiveCohortReleaseError("CORPUS_LINEAGE_INCOMPLETE")
    try:
        return int(item[key])
    except (TypeError, ValueError) as exc:
        raise LiveCohortReleaseError("CORPUS_LINEAGE_INCOMPLETE") from exc


def _dataset_terminal_from_current(
    data_root: Path, current_mid: str, latest: Mapping[str, Any]
) -> str:
    labels_path = _manifests_dir(data_root) / f"{current_mid}.labels.json"
    if labels_path.is_file() and not labels_path.is_symlink():
        try:
            payload = json.loads(labels_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        else:
            if isinstance(payload, dict):
                terminal = payload.get("dataset_terminal")
                if isinstance(terminal, str) and terminal:
                    return terminal
    terminal = latest.get("dataset_terminal")
    _require(isinstance(terminal, str) and bool(terminal), "DATASET_TERMINAL_MISSING")
    return str(terminal)


def _measure_parquet(
    path: Path,
    *,
    kind: str,
    partition_id: str,
    logical_location: str,
    measured: list[str],
) -> LiveCorpusPartitionClaims:
    try:
        claims = measure_live_corpus_parquet(
            path,
            kind=kind,
            partition_id=partition_id,
            logical_location=logical_location,
        )
    except LiveCorpusLogicalRowError as exc:
        raise _wrap_logical(exc) from exc
    except (ValueError, TypeError, OSError) as exc:
        raise LiveCohortReleaseError("LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE") from exc
    measured.append(logical_location)
    return claims


def _build_partitions(
    *,
    dataset_version: str,
    claims: Sequence[LiveCorpusPartitionClaims],
    published_at: datetime,
) -> list[PartitionManifest]:
    built: list[PartitionManifest] = []
    try:
        for claim in claims:
            part = build_partition_manifest(
                dataset_id=CORPUS_DATASET_ID,
                dataset_version=dataset_version,
                partition_id=claim.partition_id,
                logical_location=claim.logical_location,
                file_sha256=claim.file_sha256,
                content_sha256=claim.content_sha256,
                row_count=claim.row_count,
                min_event_time=claim.min_event_time,
                max_event_time=claim.max_event_time,
                min_available_to_strategy_at=claim.min_available_to_strategy_at,
                max_available_to_strategy_at=claim.max_available_to_strategy_at,
                first_reliable_available_at=published_at,
                created_at=published_at,
            )
            verify_partition_manifest(part)
            built.append(part)
    except (ManifestContractError, ManifestIntegrityError) as exc:
        raise _wrap_manifest(exc, "CANONICAL_PARTITION_BUILD_FAILED") from exc
    return built


def _build_receipt(
    *,
    dataset_version: str,
    schema_sha256: str,
    composition: Sequence[Mapping[str, Any]],
    partitions: Sequence[PartitionManifest],
    dataset_fingerprint: str,
    generation_reason: str,
    published_at: datetime,
    superseded_dataset_manifest_id: str | None,
) -> tuple[dict[str, Any], bytes, str]:
    payload: dict[str, Any] = {
        "corpus_composition": [
            {
                "cohort_id": item["cohort_id"],
                "content_sha256": item["content_sha256"],
                "release_id": item["release_id"],
            }
            for item in composition
        ],
        "dataset_fingerprint": dataset_fingerprint,
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_version": dataset_version,
        "generation_reason": generation_reason,
        "logical_row_profile": LOGICAL_ROW_PROFILE,
        "partition_manifest_ids": [item.partition_manifest_id for item in partitions],
        "partitions": [
            {
                "content_sha256": item.content_sha256,
                "file_sha256": item.file_sha256,
                "logical_location": item.logical_location,
                "max_available_to_strategy_at": _stamp_utc(item.max_available_to_strategy_at)
                if item.max_available_to_strategy_at is not None
                else None,
                "max_event_time": _stamp_utc(item.max_event_time)
                if item.max_event_time is not None
                else None,
                "min_available_to_strategy_at": _stamp_utc(item.min_available_to_strategy_at)
                if item.min_available_to_strategy_at is not None
                else None,
                "min_event_time": _stamp_utc(item.min_event_time)
                if item.min_event_time is not None
                else None,
                "partition_id": item.partition_id,
                "partition_manifest_id": item.partition_manifest_id,
                "row_count": item.row_count,
            }
            for item in partitions
        ],
        "published_at": _stamp_utc(published_at),
        "schema": VALIDATION_RECEIPT_SCHEMA,
        "schema_id": CORPUS_SCHEMA_ID,
        "schema_sha256": schema_sha256,
        "schema_version": VALIDATION_RECEIPT_SCHEMA_VERSION,
        "superseded_dataset_manifest_id": superseded_dataset_manifest_id,
    }
    encoded = _canonical_receipt_bytes(payload)
    return payload, encoded, sha256_bytes(encoded)


def _build_dataset(
    *,
    dataset_version: str,
    schema_sha256: str,
    partitions: Sequence[PartitionManifest],
    validation_receipt_sha256: str,
    published_at: datetime,
    generation_task_id: str,
    generation_run_id: str,
) -> DatasetManifest:
    try:
        dataset = build_dataset_manifest(
            dataset_id=CORPUS_DATASET_ID,
            dataset_version=dataset_version,
            schema_id=CORPUS_SCHEMA_ID,
            schema_sha256=schema_sha256,
            generation_task_id=generation_task_id,
            generation_run_id=generation_run_id,
            validation_receipt_sha256=validation_receipt_sha256,
            first_reliable_available_at=published_at,
            created_at=published_at,
            partitions=partitions,
        )
        verify_dataset_manifest(dataset, partitions=partitions)
    except (ManifestContractError, ManifestIntegrityError) as exc:
        raise _wrap_manifest(exc, "CANONICAL_DATASET_BUILD_FAILED") from exc
    return dataset


def _install_parquet(src: Path, dest: Path, expected_sha: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        raise LiveCohortReleaseError("LIVE_CORPUS_PARQUET_SYMLINK")
    if dest.is_file():
        _note_import_parquet_bytes("new", int(dest.stat().st_size))
        if sha256_file_streaming(dest) != expected_sha:
            raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT")
        return
    shutil.copyfile(src, dest)
    _note_import_parquet_bytes("new", int(dest.stat().st_size))
    if dest.is_symlink() or sha256_file_streaming(dest) != expected_sha:
        dest.unlink(missing_ok=True)
        raise LiveCohortReleaseError("TRANSPORT_HASH_MISMATCH")


def _feature_union(components: Sequence[Mapping[str, Any]]) -> list[str]:
    from solana_alpha_lab.factory.tokens_v2_typed_projection import FEATURE_FAMILY_ORDER

    seen: set[str] = set()
    ordered: list[str] = []
    for component in components:
        for family in component.get("feature_families") or []:
            text = str(family)
            if text not in seen:
                seen.add(text)
                ordered.append(text)
    return [item for item in FEATURE_FAMILY_ORDER if item in seen] or ordered


def _reconcile_current_labels(
    *,
    data_root: Path,
    dataset_manifest_id: str,
    labels: Mapping[str, Any],
    lineage_out: Mapping[str, Any],
    previous_current_mid: str | None,
) -> None:
    root = Path(data_root)
    manifests = _manifests_dir(root)
    current_labels = {**labels, "is_current_corpus_version": True}
    current_path = manifests / f"{dataset_manifest_id}.labels.json"
    _safe_path(root, current_path)
    if json.loads(current_path.read_bytes()) != current_labels:
        _atomic_replace_json(current_path, current_labels)
    # A reused historical candidate may name an older provenance parent.
    # Every LIVE flag is derived from the one lineage pointer, not that parent.
    for prev_labels_path in sorted(manifests.glob("*.labels.json")):
        if prev_labels_path == current_path:
            continue
        _safe_path(root, prev_labels_path)
        try:
            old = json.loads(prev_labels_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (isinstance(old, dict) and old.get("logical_dataset_id") == CORPUS_DATASET_ID
                and old.get("is_current_corpus_version") is not False):
            old["is_current_corpus_version"] = False
            _atomic_replace_json(prev_labels_path, old)


def _commit_canonical_root(
    *,
    data_root: Path,
    dataset: DatasetManifest,
    partitions: Sequence[PartitionManifest],
    receipt_bytes: bytes,
    published: Mapping[str, Any],
    record_sizes: bool = True,
) -> None:
    root = Path(data_root)
    manifests = _manifests_dir(root)
    for part in partitions:
        _publish_metadata(root,
            manifests / "partitions" / f"{part.partition_manifest_id}.json",
            canonical_manifest_bytes(part),
        )
        parquet_path = root / part.logical_location
        if record_sizes and parquet_path.is_file() and not parquet_path.is_symlink():
            _write_recorded_parquet_size(
                root, part.partition_id, int(parquet_path.stat().st_size)
            )
    _publish_metadata(root,
        manifests / f"{dataset.dataset_manifest_id}.validation.json",
        receipt_bytes,
    )
    _publish_metadata(root,
        manifests / f"{dataset.dataset_manifest_id}.json",
        canonical_manifest_bytes(dataset),
    )
    _publish_metadata(root,
        manifests / f"{dataset.dataset_manifest_id}.published",
        json.dumps(dict(published), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        ),
    )


def _lineage_versions(cohorts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cohort_id": item["cohort_id"],
            "corpus_version": item["corpus_version"],
            "dataset_manifest_id": item["dataset_manifest_id"],
        }
        for item in cohorts
    ]


def _claims_for_cohort(
    *,
    data_root: Path,
    cohort: Mapping[str, Any],
    prior_by_id: Mapping[str, LiveCorpusPartitionClaims] | None,
    measured: list[str],
    allow_measure: bool,
) -> list[LiveCorpusPartitionClaims]:
    cohort_id = str(cohort["cohort_id"])
    out: list[LiveCorpusPartitionClaims] = []
    for kind, rel_key, sha_key, suffix in (
        (KIND_CENSUS, "census_rel", "census_sha256", "-CENSUS"),
        (KIND_OBS, "obs_rel", "observations_sha256", "-OBS"),
    ):
        part_id = f"PARTITION-LIVE-COHORT-{cohort_id}{suffix}"
        rel = str(cohort[rel_key])
        expected_file = str(cohort[sha_key])
        parquet_path = Path(data_root) / rel
        _require(parquet_path.is_file() and not parquet_path.is_symlink(), "LIVE_CORPUS_PARQUET_MISSING")
        if prior_by_id is not None and part_id in prior_by_id:
            claim = prior_by_id[part_id]
            _require(claim.file_sha256 == expected_file, "CORPUS_PARQUET_SHA_MISMATCH")
            _require(claim.logical_location == rel, "CORPUS_PARTITION_LOCATION_MISMATCH")
            size = int(parquet_path.stat().st_size)
            recorded = _recorded_parquet_size(data_root, part_id)
            if recorded is None:
                _note_import_parquet_bytes("historical", size)
                disk_sha = sha256_file_streaming(parquet_path)
                _require(disk_sha == expected_file, "CORPUS_PARQUET_SHA_MISMATCH")
                _write_recorded_parquet_size(data_root, part_id, size)
            elif recorded != size:
                raise LiveCohortReleaseError("CORPUS_PARQUET_SHA_MISMATCH")
            out.append(claim)
            continue
        _note_import_parquet_bytes("new", int(parquet_path.stat().st_size))
        disk_sha = sha256_file_streaming(parquet_path)
        _require(disk_sha == expected_file, "CORPUS_PARQUET_SHA_MISMATCH")
        _require(allow_measure, "HISTORICAL_LOGICAL_RESCAN_FORBIDDEN")
        claim = _measure_parquet(
            parquet_path,
            kind=kind,
            partition_id=part_id,
            logical_location=rel,
            measured=measured,
        )
        _require(claim.file_sha256 == expected_file, "CORPUS_PARQUET_SHA_MISMATCH")
        out.append(claim)
    return out


def _commit_visibility(
    *, data_root: Path, dataset_manifest_id: str, labels: Mapping[str, Any],
    lineage_out: Mapping[str, Any], expected_lineage: Mapping[str, Any] | None,
) -> None:
    """One LIVE-local lineage visibility switch followed by derived cleanup."""
    _safe_path(data_root, Path(data_root) / "datasets/live_lifecycle_corpus/lineage.json")
    _safe_path(data_root, Path(data_root) / "datasets/live_lifecycle_corpus/lineage.json.tmp")
    if expected_lineage is not None:
        _require(load_live_corpus_lineage(data_root) == expected_lineage, "CORPUS_CURRENT_BASIS_CHANGED")
    write_live_corpus_lineage(data_root, lineage_out)
    _reconcile_current_labels(data_root=data_root, dataset_manifest_id=dataset_manifest_id,
        labels=labels, lineage_out=lineage_out, previous_current_mid=None)


def _publish_from_claims(
    *,
    data_root: Path,
    dataset_version: str,
    generation_task_id: str,
    generation_run_id: str,
    generation_reason: str,
    published_at: datetime,
    composition: Sequence[Mapping[str, Any]],
    claims: Sequence[LiveCorpusPartitionClaims],
    labels: Mapping[str, Any],
    lineage_out: Mapping[str, Any],
    previous_current_mid: str | None,
    superseded_dataset_manifest_id: str | None,
    fault_before_visibility: Callable[[], None] | None,
    expected_lineage: Mapping[str, Any] | None = None,
) -> tuple[DatasetManifest, list[PartitionManifest], str]:
    schema_sha256 = live_corpus_schema_sha256()
    dataset_manifest_id = compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)
    clock = _freeze_publication_clock(data_root, dataset_manifest_id, published_at)
    partitions = _build_partitions(
        dataset_version=dataset_version,
        claims=claims,
        published_at=clock,
    )
    fingerprint = compute_dataset_fingerprint(
        dataset_id=CORPUS_DATASET_ID,
        dataset_version=dataset_version,
        schema_id=CORPUS_SCHEMA_ID,
        schema_sha256=schema_sha256,
        partitions=partitions,
    )
    _receipt, receipt_bytes, receipt_sha = _build_receipt(
        dataset_version=dataset_version,
        schema_sha256=schema_sha256,
        composition=composition,
        partitions=partitions,
        dataset_fingerprint=fingerprint,
        generation_reason=generation_reason,
        published_at=clock,
        superseded_dataset_manifest_id=superseded_dataset_manifest_id,
    )
    dataset = _build_dataset(
        dataset_version=dataset_version,
        schema_sha256=schema_sha256,
        partitions=partitions,
        validation_receipt_sha256=receipt_sha,
        published_at=clock,
        generation_task_id=generation_task_id,
        generation_run_id=generation_run_id,
    )
    _require(dataset.dataset_fingerprint == fingerprint, "DATASET_FINGERPRINT_MISMATCH")
    _require(dataset.dataset_manifest_id == dataset_manifest_id, "DATASET_MANIFEST_ID_MISMATCH")
    published = {
        "commit_point": COMMIT_POINT_KIND,
        "cohort_id": composition[-1]["cohort_id"] if composition else None,
        "corpus_version": lineage_out.get("current_corpus_version"),
        "cumulative_cohort_count": len(composition),
        "dataset_fingerprint": dataset.dataset_fingerprint,
        "dataset_manifest_id": dataset.dataset_manifest_id,
        "metadata_clock_at": _stamp_utc(clock),
        "published_at": _stamp_utc(clock),
        "release_id": composition[-1]["release_id"] if composition else None,
    }
    labels_path = _manifests_dir(data_root) / f"{dataset_manifest_id}.labels.json"
    staged_labels = {**labels, "is_current_corpus_version": False}
    if labels_path.exists():
        _safe_path(data_root, labels_path)
        try:
            existing = json.loads(labels_path.read_bytes())
        except (ValueError, UnicodeDecodeError) as exc:
            raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT") from exc
        _require(isinstance(existing, dict), "CANONICAL_TARGET_CONFLICT")
        _require({**existing, "is_current_corpus_version": False} == staged_labels,
                 "CANONICAL_TARGET_CONFLICT")
    else:
        _publish_metadata(data_root, labels_path, _canonical_receipt_bytes(staged_labels))
    _commit_canonical_root(
        data_root=data_root,
        dataset=dataset,
        partitions=partitions,
        receipt_bytes=receipt_bytes,
        published=published,
        record_sizes=generation_reason != REPAIR_GENERATION_REASON,
    )
    if fault_before_visibility is not None:
        fault_before_visibility()
    prepared = inspect_canonical_root(data_root, dataset_manifest_id,
        verify_parquet_bytes=generation_reason == REPAIR_GENERATION_REASON)
    _require(prepared["complete"], "CANDIDATE_VERIFICATION_FAILED")
    _require(prepared["dataset"] == dataset
             and prepared["partitions"] == sorted(partitions, key=lambda part: part.partition_id),
             "CANDIDATE_VERIFICATION_FAILED")
    _require((_manifests_dir(data_root) / f"{dataset_manifest_id}.validation.json").read_bytes() == receipt_bytes,
             "CANDIDATE_VERIFICATION_FAILED")
    _require(json.loads(labels_path.read_bytes()) == staged_labels
             or json.loads(labels_path.read_bytes()) == {**staged_labels, "is_current_corpus_version": True},
             "CANDIDATE_VERIFICATION_FAILED")
    _require(json.loads((_manifests_dir(data_root) / f"{dataset_manifest_id}.published").read_bytes()) == published,
             "CANDIDATE_VERIFICATION_FAILED")
    _commit_visibility(data_root=data_root, dataset_manifest_id=dataset_manifest_id,
        labels=labels, lineage_out=lineage_out, expected_lineage=expected_lineage)
    return dataset, list(partitions), fingerprint


def finish_unpublished_visibility(data_root: Path, dataset_manifest_id: str) -> DatasetManifest:
    """Compatibility entry; never retract or regenerate a broken current root."""
    lineage = load_live_corpus_lineage(data_root)
    _require(lineage.get("current_dataset_manifest_id") == dataset_manifest_id,
             "CURRENT_CORPUS_MISSING")
    result = repair_live_corpus_manifests(data_root=data_root)
    return _load_dataset_manifest(data_root, result["dataset_manifest_id"])


def repair_live_corpus_manifests(
    *,
    data_root: Path,
    published_at: datetime | None = None,
    fault_before_visibility: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Prepare/verify replacement metadata, then atomically select it in lineage."""
    root = Path(data_root)
    _safe_path(root, root / "datasets/manifests/partitions")
    _safe_path(root, root / "datasets/live_lifecycle_corpus/lineage.json")
    lineage = load_live_corpus_lineage(root)
    current_mid = lineage.get("current_dataset_manifest_id")
    _require(isinstance(current_mid, str) and bool(re.fullmatch(r"dataset-[0-9a-f]{64}", current_mid)),
             "CURRENT_CORPUS_MISSING")
    current = _load_dataset_manifest(root, current_mid)
    _require(current.dataset_id == CORPUS_DATASET_ID, "CORPUS_LINEAGE_INCOMPLETE")
    cohorts = _cohorts_from_lineage(lineage)
    for item in cohorts:
        for key in ("census_rel", "obs_rel", "census_sha256", "observations_sha256",
                    "sealed_at", "cohort_id", "release_id", "content_sha256",
                    "dataset_manifest_id", "corpus_version", "dataset_version"):
            _require(item.get(key), "CORPUS_LINEAGE_INCOMPLETE")
        for key in ("yield_eligible", "yield_missing", "census_row_count", "observation_row_count"):
            _lineage_int(item, key)
    version = lineage.get("current_corpus_version")
    _require(type(version) is int and version == len(cohorts), "CORPUS_LINEAGE_INCOMPLETE")
    _require(len({item["cohort_id"] for item in cohorts}) == len(cohorts)
             and len({item["release_id"] for item in cohorts}) == len(cohorts),
             "CORPUS_LINEAGE_INCOMPLETE")
    latest = cohorts[-1]
    _require(latest["corpus_version"] == version and latest["dataset_manifest_id"] == current_mid,
             "CORPUS_LINEAGE_INCOMPLETE")

    # Validate the old contract on its own terms. A schema mismatch alone is
    # repairable; invalid already-repaired history is never regenerated.
    old = inspect_canonical_root(root, current_mid, expected_schema_sha256=current.schema_sha256)
    is_canonical = current.dataset_version.endswith(CANONICAL_METADATA_SUFFIX)
    if is_canonical:
        _require(old["complete"], str(old["reason"]))
        old_receipt = json.loads((_manifests_dir(root) / f"{current_mid}.validation.json").read_bytes())
        _require(old_receipt.get("corpus_composition") == [
            {key: item[key] for key in ("cohort_id", "content_sha256", "release_id")}
            for item in cohorts], "CORPUS_LINEAGE_INCOMPLETE")
    labels_path = _manifests_dir(root) / f"{current_mid}.labels.json"
    _safe_path(root, labels_path)
    _require(labels_path.is_file(), "DATASET_LABELS_MISSING")
    try:
        labels = json.loads(labels_path.read_bytes())
    except (ValueError, UnicodeDecodeError) as exc:
        raise LiveCohortReleaseError("DATASET_LABELS_MISSING") from exc
    _require(isinstance(labels, dict), "DATASET_LABELS_MISSING")
    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError, require_live_scientific_labels,
    )
    try:
        require_live_scientific_labels(CORPUS_DATASET_ID, labels)
    except EvidenceIdentityError as exc:
        raise LiveCohortReleaseError(str(exc)) from exc
    _require(labels.get("corpus_version") == version, "CORPUS_LINEAGE_INCOMPLETE")
    schema = live_corpus_schema_sha256()
    measured: list[str] = []
    claims: list[LiveCorpusPartitionClaims] = []
    # Repair always measures parquet and logical rows; never fills a cache in
    # the old root. Lineage is an immutable scientific composition binding.
    for item in cohorts:
        cohort_claims = []
        for kind, rel_key, sha_key, count_key, suffix in (
            (KIND_CENSUS, "census_rel", "census_sha256", "census_row_count", "-CENSUS"),
            (KIND_OBS, "obs_rel", "observations_sha256", "observation_row_count", "-OBS"),
        ):
            rel = str(item[rel_key])
            _require(not Path(rel).is_absolute() and ".." not in Path(rel).parts,
                     "LIVE_CORPUS_PATH_INTEGRITY")
            path = root / rel
            _safe_path(root, path)
            _require(path.is_file(), "LIVE_CORPUS_PARQUET_MISSING")
            _require(sha256_file_streaming(path) == item[sha_key], "CORPUS_PARQUET_SHA_MISMATCH")
            claim = _measure_parquet(path, kind=kind,
                partition_id=f"PARTITION-LIVE-COHORT-{item['cohort_id']}{suffix}",
                logical_location=rel, measured=measured)
            _require(claim.row_count == int(item[count_key]), "LIVE_CORPUS_ROW_COUNT_MISMATCH")
            cohort_claims.append(claim)
        _require(sha256_files_concat_streaming([root / str(item["census_rel"]), root / str(item["obs_rel"])])
                 == item["content_sha256"], "CORPUS_PARQUET_SHA_MISMATCH")
        claims.extend(cohort_claims)
    if is_canonical:
        expected_claims = {part.partition_id: claims_from_partition(part) for part in old["partitions"]}
        _require({claim.partition_id: claim for claim in claims} == expected_claims,
                 "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")

    repaired_version = repair_dataset_version(current.dataset_version, schema, cohorts)
    has_metadata_revision = bool(re.search(r"\.metadata-[0-9a-f]{64}$",
                                          current.dataset_version.removesuffix(CANONICAL_METADATA_SUFFIX)))
    if (is_canonical and current.schema_sha256 == schema
            and (not has_metadata_revision or current.dataset_version == repaired_version)):
        _reconcile_current_labels(data_root=root, dataset_manifest_id=current_mid,
            labels=labels, lineage_out=lineage,
            previous_current_mid=latest.get("superseded_dataset_manifest_id"))
        return {"status": "IDEMPOTENT_REPAIR", "corpus_version": version,
            "corpus_version_before": version, "dataset_id": CORPUS_DATASET_ID,
            "dataset_manifest_id_before": current_mid, "dataset_manifest_id": current_mid,
            "dataset_version": current.dataset_version, "dataset_fingerprint": current.dataset_fingerprint,
            "logical_rows_measured_partitions": len(measured), "epoch_bump": False,
            "metadata_identity_changed": False, "scientific_epoch_changed": False,
            "candidate_disposition": "CURRENT_VERIFIED", "lineage_switched": False,
            "superseded_dataset_manifest_id": latest.get("superseded_dataset_manifest_id")}

    repaired_mid = compute_dataset_manifest_id(CORPUS_DATASET_ID, repaired_version)
    _require(repaired_mid != current_mid, "CANONICAL_TARGET_CONFLICT")
    latest["superseded_dataset_manifest_id"] = current_mid
    latest["dataset_manifest_id"] = repaired_mid
    latest["dataset_version"] = repaired_version
    lineage_out = {**lineage, "cohorts": cohorts,
        "current_dataset_manifest_id": repaired_mid, "versions": _lineage_versions(cohorts)}
    # A predecessor describes the visibility transition, not this immutable
    # target. Keep it in lineage and the result, never candidate root bytes.
    candidate_labels = {key: value for key, value in labels.items()
                        if key != "superseded_dataset_manifest_id"}
    candidate_labels["dataset_version"] = repaired_version
    composition = [{key: item[key] for key in ("cohort_id", "content_sha256", "release_id")}
                   for item in cohorts]
    candidate_path = _manifests_dir(root) / f"{repaired_mid}.json"
    candidate_marker = _manifests_dir(root) / f"{repaired_mid}.published"
    disposition = "BUILT"
    if candidate_path.exists() or candidate_marker.exists():
        candidate = inspect_canonical_root(root, repaired_mid)
        disposition = "REUSED" if candidate["complete"] else "REBUILT_PARTIAL"
    elif (_manifests_dir(root) / f"{repaired_mid}.publication-clock.json").exists():
        disposition = "REBUILT_PARTIAL"
    already = inspect_canonical_root(root, repaired_mid)
    if already["complete"]:
        dataset = already["dataset"]
        _require(dataset.dataset_version == repaired_version and dataset.schema_sha256 == schema,
                 "CANONICAL_TARGET_CONFLICT")
        _require({part.partition_id: claims_from_partition(part) for part in already["partitions"]}
                 == {claim.partition_id: claim for claim in claims}, "CANONICAL_TARGET_CONFLICT")
        stored_labels = json.loads((_manifests_dir(root) / f"{repaired_mid}.labels.json").read_bytes())
        administrative = {"is_current_corpus_version"}
        _require({key: value for key, value in stored_labels.items() if key not in administrative}
                 == {key: value for key, value in candidate_labels.items() if key not in administrative},
                 "CANONICAL_TARGET_CONFLICT")
        receipt = json.loads((_manifests_dir(root) / f"{repaired_mid}.validation.json").read_bytes())
        _require(receipt.get("corpus_composition") == composition
                 and receipt.get("logical_row_profile") == LOGICAL_ROW_PROFILE,
                 "CANONICAL_TARGET_CONFLICT")
        if fault_before_visibility is not None:
            fault_before_visibility()
        recheck = inspect_canonical_root(root, repaired_mid)
        _require(recheck["complete"] and recheck["dataset"] == dataset
                 and recheck["partitions"] == already["partitions"]
                 and json.loads((_manifests_dir(root) / f"{repaired_mid}.labels.json").read_bytes()) == stored_labels,
                 "CANDIDATE_VERIFICATION_FAILED")
        _commit_visibility(data_root=root, dataset_manifest_id=repaired_mid,
            labels=stored_labels, lineage_out=lineage_out, expected_lineage=lineage)
        fingerprint = dataset.dataset_fingerprint
        disposition = "REUSED"
    else:
        dataset, _parts, fingerprint = _publish_from_claims(
            data_root=root, dataset_version=repaired_version,
            generation_task_id=CANONICAL_GENERATION_TASK_REPAIR,
            generation_run_id=f"repair-{repaired_mid[8:]}",
            generation_reason=REPAIR_GENERATION_REASON,
            published_at=(published_at or datetime.now(tz=UTC)).astimezone(UTC),
            composition=composition, claims=claims, labels=candidate_labels,
            lineage_out=lineage_out, previous_current_mid=current_mid,
            superseded_dataset_manifest_id=None,
            fault_before_visibility=fault_before_visibility,
            expected_lineage=lineage,
        )
    return {"status": "REPAIRED", "corpus_version": version, "corpus_version_before": version,
        "dataset_id": CORPUS_DATASET_ID, "dataset_manifest_id_before": current_mid,
        "dataset_manifest_id": dataset.dataset_manifest_id, "dataset_version": dataset.dataset_version,
        "dataset_fingerprint": fingerprint, "logical_rows_measured_partitions": len(measured),
        "measured_logical_locations": measured, "superseded_dataset_manifest_id": current_mid,
        "cohort_count": len(cohorts), "epoch_bump": False,
        "metadata_identity_changed": True, "scientific_epoch_changed": False,
        "candidate_disposition": disposition, "lineage_switched": True}


def _producer_for_imported_schedule(manifest: Mapping[str, Any]) -> str:
    for key in (
        "schedule_producer_git_sha",
        "release_builder_git_sha",
        "producer_git_sha",
    ):
        value = str(manifest.get(key) or "")
        if len(value) == 40 and all(c in "0123456789abcdef" for c in value):
            return value
    raw = manifest.get("contributing_producer_git_shas")
    if isinstance(raw, list):
        for item in raw:
            value = str(item or "")
            if len(value) == 40 and all(c in "0123456789abcdef" for c in value):
                return value
    raise LiveCohortReleaseError(SCHEDULE_PRODUCER_UNBOUND)


def persist_imported_release_schedule(
    *,
    release_root: Path,
    data_root: Path,
    manifest: Mapping[str, Any],
    imported_at: datetime,
) -> None:
    """Bind the 1.1 schedule artifact into ResearchStore. Legacy 1.0 is a no-op."""

    version = str(manifest.get("schema_version") or "")
    if version != RELEASE_SCHEMA_VERSION_SELF_CONTAINED:
        return
    from solana_alpha_lab.factory.observation_panel_publisher import (
        ObservationPanelPublisherError,
        persist_observation_schedule,
    )

    artifact = Path(release_root) / OBSERVATION_SCHEDULE_ARTIFACT_NAME
    if not artifact.is_file() or artifact.is_symlink():
        raise LiveCohortReleaseError(SCHEDULE_ARTIFACT_MISSING)
    wanted = str(manifest.get("schedule_sha256") or "")
    expected_byte = str(manifest.get("observation_schedule_sha256") or "") or None
    try:
        document = decode_schedule_artifact(
            artifact.read_bytes(),
            wanted_sha=wanted,
            expected_byte_sha256=expected_byte,
        )
    except ValueError as exc:
        raise LiveCohortReleaseError(str(exc)) from exc
    persist_doc = dict(document)
    persist_doc["schedule_sha256"] = wanted
    producer = _producer_for_imported_schedule(manifest)
    activation = str(manifest.get("activation_id") or "") or None
    try:
        persist_observation_schedule(
            data_root=data_root,
            schedule=persist_doc,
            now=imported_at,
            producer_git_sha=producer,
            activation_id=activation,
        )
    except ObservationPanelPublisherError as exc:
        raise LiveCohortReleaseError(str(exc)) from exc


def import_live_cohort_canonical(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
    fault_before_visibility: Callable[[], None] | None = None,
) -> dict[str, Any]:
    reset_import_parquet_accounting()
    manifest = verify_live_cohort(release_root)
    imported_at = (import_time or datetime.now(tz=UTC)).astimezone(UTC)
    sealed_at = parse_live_corpus_utc(str(manifest["sealed_at"]))
    _require(imported_at >= sealed_at, "IMPORT_BEFORE_SEAL")
    release_id = str(manifest["release_id"])
    cohort_id = str(manifest["cohort_id"])
    census_path = Path(release_root) / CENSUS_NAME
    obs_path = Path(release_root) / OBSERVATIONS_NAME
    content_sha = sha256_files_concat_streaming([census_path, obs_path])
    census_sha = sha256_file_streaming(census_path)
    obs_sha = sha256_file_streaming(obs_path)

    lineage = load_live_corpus_lineage(data_root)
    current_mid = lineage.get("current_dataset_manifest_id")
    raw_cohorts = lineage.get("cohorts")
    existing_cohorts: list[dict[str, Any]] = []
    if current_mid or raw_cohorts:
        existing_cohorts = _cohorts_from_lineage(lineage)
    matching = next(
        (prior for prior in existing_cohorts if prior.get("release_id") == release_id),
        None,
    )
    current_mid = lineage.get("current_dataset_manifest_id")
    current_inspection: dict[str, Any] | None = None
    if existing_cohorts:
        _require(
            isinstance(current_mid, str) and current_mid,
            "CURRENT_CORPUS_MISSING",
        )
        current_inspection = inspect_canonical_root(
            data_root, str(current_mid), verify_parquet_bytes=False
        )
        if current_inspection.get("reason") == "CORPUS_PARQUET_SHA_MISMATCH":
            raise LiveCohortReleaseError("CORPUS_PARQUET_SHA_MISMATCH")
        if not current_inspection["complete"]:
            if (
                matching is not None
                and matching.get("content_sha256") == content_sha
                and str(matching.get("dataset_manifest_id") or "") == current_mid
                and (
                    current_inspection["artifacts_ok"]
                    or str(matching.get("dataset_version") or "").endswith(
                        CANONICAL_METADATA_SUFFIX
                    )
                )
            ):
                persist_imported_release_schedule(
                    release_root=Path(release_root),
                    data_root=Path(data_root),
                    manifest=manifest,
                    imported_at=imported_at,
                )
                rebuilt = repair_live_corpus_manifests(
                    data_root=data_root,
                    published_at=imported_at,
                )
                return {
                    "status": "IMPORTED",
                    "cohort_id": cohort_id,
                    "release_id": release_id,
                    "corpus_version": rebuilt.get("corpus_version"),
                    "dataset_manifest_id": rebuilt["dataset_manifest_id"],
                    "evidence_role": LIVE_EVIDENCE_ROLE,
                    "logical_rows_measured_partitions": rebuilt.get(
                        "logical_rows_measured_partitions", 0
                    ),
                    "epoch_bump": bool(rebuilt.get("epoch_bump")),
                }
            if (
                matching is not None
                and matching.get("content_sha256") != content_sha
                and current_inspection["artifacts_ok"]
            ):
                raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT")
            raise LiveCohortReleaseError(LEGACY_CORPUS_REQUIRES_REPAIR)
        if matching is not None:
            if matching.get("content_sha256") != content_sha:
                raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT")
            persist_imported_release_schedule(
                release_root=Path(release_root),
                data_root=Path(data_root),
                manifest=manifest,
                imported_at=imported_at,
            )
            return {
                "status": "IDEMPOTENT_REIMPORT",
                "cohort_id": cohort_id,
                "release_id": release_id,
                "corpus_version": matching.get("corpus_version"),
                "dataset_manifest_id": matching.get("dataset_manifest_id"),
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "logical_rows_measured_partitions": 0,
                "epoch_bump": False,
            }
    for prior in existing_cohorts:
        if prior.get("cohort_id") == cohort_id:
            raise LiveCohortReleaseError("COHORT_ALREADY_IMPORTED")

    prior_by_id: dict[str, LiveCorpusPartitionClaims] | None = None
    previous_current_mid: str | None = None
    if existing_cohorts:
        previous_current_mid = str(current_mid)
        _require(current_inspection is not None, "CURRENT_CORPUS_MISSING")
        prior_by_id = {
            part.partition_id: claims_from_partition(part)
            for part in current_inspection["partitions"]
        }
        for prior in existing_cohorts:
            for key in (
                "census_rel",
                "obs_rel",
                "census_sha256",
                "observations_sha256",
                "sealed_at",
                "cohort_id",
                "release_id",
                "content_sha256",
                "dataset_manifest_id",
                "corpus_version",
            ):
                _require(prior.get(key), "CORPUS_LINEAGE_INCOMPLETE")

    version_n = len(existing_cohorts) + 1
    dataset_version = canonical_dataset_version(f"corpus-v{version_n}-{cohort_id}")
    # A prepared first-import candidate already froze its publication clock.
    # Retry reuses it rather than changing immutable metadata under the same ID.
    frozen_clock = _manifests_dir(data_root) / (
        f"{compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)}.publication-clock.json"
    )
    if frozen_clock.exists():
        imported_at = _freeze_publication_clock(
            data_root, compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version), imported_at
        )
    census_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS"
    obs_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-OBS"
    date_key = imported_at.strftime("%Y-%m-%d")
    census_rel = (
        f"datasets/partitions/date={date_key}/{census_part_id}-{release_id[:16]}.parquet"
    )
    obs_rel = (
        f"datasets/partitions/date={date_key}/{obs_part_id}-{release_id[:16]}.parquet"
    )
    dest_census = Path(data_root) / census_rel
    dest_obs = Path(data_root) / obs_rel
    persist_imported_release_schedule(
        release_root=Path(release_root),
        data_root=Path(data_root),
        manifest=manifest,
        imported_at=imported_at,
    )
    _install_parquet(census_path, dest_census, census_sha)
    _install_parquet(obs_path, dest_obs, obs_sha)

    measured: list[str] = []
    claims: list[LiveCorpusPartitionClaims] = []
    for prior in existing_cohorts:
        claims.extend(
            _claims_for_cohort(
                data_root=data_root,
                cohort=prior,
                prior_by_id=prior_by_id,
                measured=measured,
                allow_measure=False,
            )
        )
    new_component = {
        "census_rel": census_rel,
        "census_row_count": int(manifest["census_row_count"]),
        "census_sha256": census_sha,
        "cohort_id": cohort_id,
        "content_sha256": content_sha,
        "corpus_version": version_n,
        "dataset_manifest_id": compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version),
        "dataset_version": dataset_version,
        "discovery_coverage_class": manifest.get("discovery_coverage_class"),
        "feature_families": list(manifest["feature_families"]),
        "first_reliable_available_at": _render_utc(imported_at),
        "imported_at": _render_utc(imported_at),
        "obs_rel": obs_rel,
        "observation_row_count": int(manifest["observation_row_count"]),
        "observations_sha256": obs_sha,
        **(
            {"allowed_lateness_seconds": int(manifest["allowed_lateness_seconds"])}
            if isinstance(manifest.get("allowed_lateness_seconds"), int)
            and not isinstance(manifest.get("allowed_lateness_seconds"), bool)
            else {}
        ),
        "readiness_state": manifest.get("readiness_state"),
        "release_id": release_id,
        "sealed_at": _render_utc(sealed_at),
        "superseded_dataset_manifest_id": previous_current_mid,
        "yield_eligible": int(manifest["yield_eligible"]),
        "yield_missing": int(manifest["yield_missing"]),
    }
    claims.extend(
        _claims_for_cohort(
            data_root=data_root,
            cohort=new_component,
            prior_by_id=None,
            measured=measured,
            allow_measure=True,
        )
    )
    cumulative = existing_cohorts + [new_component]
    composition = [
        {
            "cohort_id": item["cohort_id"],
            "content_sha256": item["content_sha256"],
            "release_id": item["release_id"],
        }
        for item in cumulative
    ]
    feature_union = _feature_union(cumulative)
    yield_eligible_sum = sum(_lineage_int(item, "yield_eligible") for item in cumulative)
    yield_missing_sum = sum(_lineage_int(item, "yield_missing") for item in cumulative)
    census_rows_sum = sum(_lineage_int(item, "census_row_count") for item in cumulative)
    obs_rows_sum = sum(_lineage_int(item, "observation_row_count") for item in cumulative)
    labels = {
        **REQUIRED_LABELS,
        "accepted_hypothesis_id": None,
        "census_row_count_cumulative": census_rows_sum,
        "cohort_id": cohort_id,
        "cohort_lineage": [str(item["cohort_id"]) for item in cumulative],
        "corpus_version": version_n,
        "cumulative_composition": True,
        "dataset_terminal": "SAMPLE_VALID",
        "dataset_version": dataset_version,
        "discovery_coverage_class": manifest.get("discovery_coverage_class"),
        "feature_families": feature_union,
        "feature_hint": None,
        "imported_at": _render_utc(imported_at),
        "is_current_corpus_version": True,
        "observation_row_count_cumulative": obs_rows_sum,
        "readiness_state": manifest.get("readiness_state"),
        "release_id": release_id,
        "yield_eligible": yield_eligible_sum,
        "yield_missing": yield_missing_sum,
    }
    lineage_out = {
        "cohorts": cumulative,
        "corpus_dataset_id": CORPUS_DATASET_ID,
        "current_corpus_version": version_n,
        "current_dataset_manifest_id": compute_dataset_manifest_id(
            CORPUS_DATASET_ID, dataset_version
        ),
        "versions": _lineage_versions(cumulative),
    }
    dataset, _parts, fingerprint = _publish_from_claims(
        data_root=data_root,
        dataset_version=dataset_version,
        generation_task_id=CANONICAL_GENERATION_TASK_IMPORT,
        generation_run_id=f"import-{release_id[:16]}",
        generation_reason="CUMULATIVE_COHORT_IMPORT",
        published_at=imported_at,
        composition=composition,
        claims=claims,
        labels=labels,
        lineage_out=lineage_out,
        previous_current_mid=previous_current_mid,
        superseded_dataset_manifest_id=previous_current_mid,
        fault_before_visibility=fault_before_visibility,
    )
    return {
        "status": "IMPORTED",
        "cohort_id": cohort_id,
        "release_id": release_id,
        "corpus_version": version_n,
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_version": dataset.dataset_version,
        "dataset_manifest_id": dataset.dataset_manifest_id,
        "dataset_fingerprint": fingerprint,
        "cohort_lineage": [str(item["cohort_id"]) for item in cumulative],
        "evidence_role": LIVE_EVIDENCE_ROLE,
        "feature_families": feature_union,
        "imported_at": _render_utc(imported_at),
        "epoch_bump": True,
        "cumulative_census_rows": census_rows_sum,
        "cumulative_observation_rows": obs_rows_sum,
        "logical_rows_measured_partitions": len(measured),
        "measured_logical_locations": measured,
        "historical_parquet_bytes_hashed": import_parquet_accounting()["historical"],
        "new_cohort_parquet_bytes_hashed": import_parquet_accounting()["new"],
    }
