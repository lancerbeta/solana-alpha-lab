"""TASK-06-valid LIVE CORPUS metadata publication (repair + import).

Not a second identity profile. Callers remain import_live_cohort /
repair_live_corpus_manifests.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.discovery_evidence_release import (
    _publish_bytes,
    _render_utc,
    _require,
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
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
RELEASE_MANIFEST_NAME = "release_manifest.json"


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


def _manifests_dir(data_root: Path) -> Path:
    return Path(data_root) / "datasets" / "manifests"


def _atomic_replace_json(path: Path, payload: Mapping[str, Any]) -> None:
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
        return _parse_utc_local(raw)
    _publish_bytes(path, encoded)
    return proposed


def _parse_utc_local(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise LiveCohortReleaseError("CLOCK_NOT_AWARE")
    return parsed.astimezone(UTC)


def inspect_canonical_root(data_root: Path, dataset_manifest_id: str) -> dict[str, Any]:
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
    if dataset.schema_sha256 != live_corpus_schema_sha256():
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
    complete = (
        artifacts_ok
        and labels_path.is_file()
        and not labels_path.is_symlink()
        and published_path.is_file()
        and not published_path.is_symlink()
    )
    return {
        "artifacts_ok": artifacts_ok,
        "complete": complete,
        "dataset": dataset,
        "partitions": partitions,
        "reason": "OK" if complete else "UNPUBLISHED",
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
    if dest.is_file():
        if sha256_file_streaming(dest) != expected_sha:
            raise LiveCohortReleaseError("CANONICAL_TARGET_CONFLICT")
        return
    shutil.copyfile(src, dest)
    if sha256_file_streaming(dest) != expected_sha:
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


def _stage_labels_and_lineage(
    *,
    data_root: Path,
    dataset_manifest_id: str,
    labels: Mapping[str, Any],
    lineage_out: Mapping[str, Any],
    previous_current_mid: str | None,
) -> None:
    root = Path(data_root)
    manifests = _manifests_dir(root)
    _atomic_replace_json(manifests / f"{dataset_manifest_id}.labels.json", labels)
    if previous_current_mid and previous_current_mid != dataset_manifest_id:
        prev_labels_path = manifests / f"{previous_current_mid}.labels.json"
        if prev_labels_path.is_file() and not prev_labels_path.is_symlink():
            try:
                old = json.loads(prev_labels_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                old = None
            if isinstance(old, dict):
                old["is_current_corpus_version"] = False
                _atomic_replace_json(prev_labels_path, old)
    write_live_corpus_lineage(root, lineage_out)


def _commit_canonical_root(
    *,
    data_root: Path,
    dataset: DatasetManifest,
    partitions: Sequence[PartitionManifest],
    receipt_bytes: bytes,
    published: Mapping[str, Any],
) -> None:
    root = Path(data_root)
    manifests = _manifests_dir(root)
    for part in partitions:
        _publish_bytes(
            manifests / "partitions" / f"{part.partition_manifest_id}.json",
            canonical_manifest_bytes(part),
        )
    _publish_bytes(
        manifests / f"{dataset.dataset_manifest_id}.validation.json",
        receipt_bytes,
    )
    _publish_bytes(
        manifests / f"{dataset.dataset_manifest_id}.json",
        canonical_manifest_bytes(dataset),
    )
    _publish_bytes(
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
        if prior_by_id is not None and part_id in prior_by_id:
            claim = prior_by_id[part_id]
            _require(claim.file_sha256 == expected_file, "CORPUS_PARQUET_SHA_MISMATCH")
            _require(claim.logical_location == rel, "CORPUS_PARTITION_LOCATION_MISMATCH")
            out.append(claim)
            continue
        _require(allow_measure, "HISTORICAL_LOGICAL_RESCAN_FORBIDDEN")
        parquet_path = Path(data_root) / rel
        _require(parquet_path.is_file() and not parquet_path.is_symlink(), "LIVE_CORPUS_PARQUET_MISSING")
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
) -> tuple[DatasetManifest, list[PartitionManifest], str]:
    schema_sha256 = live_corpus_schema_sha256()
    dataset_manifest_id = compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)
    _stage_labels_and_lineage(
        data_root=data_root,
        dataset_manifest_id=dataset_manifest_id,
        labels=labels,
        lineage_out=lineage_out,
        previous_current_mid=previous_current_mid,
    )
    if fault_before_visibility is not None:
        fault_before_visibility()
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
    _commit_canonical_root(
        data_root=data_root,
        dataset=dataset,
        partitions=partitions,
        receipt_bytes=receipt_bytes,
        published=published,
    )
    return dataset, list(partitions), fingerprint


def _retract_unpublished_canonical_metadata(
    data_root: Path, dataset_manifest_id: str
) -> None:
    """Drop unpublished TASK-06 files so a retry can freeze a new visibility clock.

    Never deletes parquet, labels, lineage, or a root that already has .published.
    Never deletes a legacy (non-canonical) current dataset.json.
    """

    manifests = _manifests_dir(data_root)
    published_path = manifests / f"{dataset_manifest_id}.published"
    if published_path.is_file() and not published_path.is_symlink():
        return
    dataset_path = manifests / f"{dataset_manifest_id}.json"
    dataset: DatasetManifest | None = None
    if dataset_path.is_file() and not dataset_path.is_symlink():
        try:
            dataset = _load_dataset_manifest(data_root, dataset_manifest_id)
        except Exception:
            dataset = None
        if dataset is not None and not str(dataset.dataset_version).endswith(
            CANONICAL_METADATA_SUFFIX
        ):
            return
    for path in (
        dataset_path,
        manifests / f"{dataset_manifest_id}.validation.json",
        manifests / f"{dataset_manifest_id}.publication-clock.json",
    ):
        if path.is_file() and not path.is_symlink():
            path.unlink()
    part_dir = manifests / "partitions"
    if not part_dir.is_dir():
        return
    for path in part_dir.glob("partition-*.json"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if payload.get("dataset_manifest_id") == dataset_manifest_id:
            path.unlink()


def finish_unpublished_visibility(
    data_root: Path, dataset_manifest_id: str
) -> DatasetManifest:
    """Recover an unpublished canonical root with a new visibility clock."""

    inspection = inspect_canonical_root(data_root, dataset_manifest_id)
    if inspection["complete"] and inspection.get("dataset") is not None:
        return inspection["dataset"]
    labels_path = _manifests_dir(data_root) / f"{dataset_manifest_id}.labels.json"
    _require(labels_path.is_file() and not labels_path.is_symlink(), "DATASET_LABELS_MISSING")
    _retract_unpublished_canonical_metadata(data_root, dataset_manifest_id)
    repaired = repair_live_corpus_manifests(data_root=data_root)
    rebuilt = inspect_canonical_root(data_root, str(repaired["dataset_manifest_id"]))
    dataset = rebuilt.get("dataset")
    _require(rebuilt["complete"] and dataset is not None, "CANONICAL_ROOT_INCOMPLETE")
    return dataset


def repair_live_corpus_manifests(
    *,
    data_root: Path,
    published_at: datetime | None = None,
    fault_before_visibility: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Republish current LIVE CORPUS composition as TASK-06-valid metadata."""

    lineage = load_live_corpus_lineage(data_root)
    current_mid = lineage.get("current_dataset_manifest_id")
    _require(isinstance(current_mid, str) and current_mid, "CURRENT_CORPUS_MISSING")
    inspection = inspect_canonical_root(data_root, current_mid)
    if inspection["complete"]:
        dataset = inspection["dataset"]
        return {
            "status": "IDEMPOTENT_REPAIR",
            "corpus_version": lineage.get("current_corpus_version"),
            "dataset_id": CORPUS_DATASET_ID,
            "dataset_manifest_id": current_mid,
            "dataset_version": dataset.dataset_version if dataset is not None else None,
            "dataset_fingerprint": dataset.dataset_fingerprint if dataset is not None else None,
            "logical_rows_measured_partitions": 0,
            "superseded_dataset_manifest_id": None,
            "epoch_bump": False,
        }
    _retract_unpublished_canonical_metadata(data_root, str(current_mid))

    existing_cohorts = [dict(item) for item in lineage.get("cohorts") or [] if isinstance(item, Mapping)]
    _require(existing_cohorts, "CURRENT_CORPUS_MISSING")
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
        ):
            _require(prior.get(key), "CORPUS_LINEAGE_INCOMPLETE")

    current_version = lineage.get("current_corpus_version")
    latest = existing_cohorts[-1]
    for item in existing_cohorts:
        if item.get("corpus_version") == current_version:
            latest = item
            break
    raw_version = str(latest.get("dataset_version") or "")
    if not raw_version:
        raw_version = f"corpus-v{int(latest.get('corpus_version') or 1)}-{latest['cohort_id']}"
    repaired_version = canonical_dataset_version(raw_version)
    repaired_mid = compute_dataset_manifest_id(CORPUS_DATASET_ID, repaired_version)
    already = inspect_canonical_root(data_root, repaired_mid)
    repaired_labels = _manifests_dir(data_root) / f"{repaired_mid}.labels.json"
    if already["complete"] and already["dataset"] is not None and repaired_labels.is_file():
        dataset = already["dataset"]
        latest["superseded_dataset_manifest_id"] = latest.get(
            "superseded_dataset_manifest_id"
        ) or current_mid
        latest["dataset_manifest_id"] = repaired_mid
        latest["dataset_version"] = repaired_version
        lineage_out = {
            "cohorts": existing_cohorts,
            "corpus_dataset_id": CORPUS_DATASET_ID,
            "current_corpus_version": current_version,
            "current_dataset_manifest_id": repaired_mid,
            "versions": _lineage_versions(existing_cohorts),
        }
        write_live_corpus_lineage(data_root, lineage_out)
        return {
            "status": "IDEMPOTENT_REPAIR",
            "corpus_version": current_version,
            "dataset_id": CORPUS_DATASET_ID,
            "dataset_manifest_id": repaired_mid,
            "dataset_version": dataset.dataset_version,
            "dataset_fingerprint": dataset.dataset_fingerprint,
            "logical_rows_measured_partitions": 0,
            "superseded_dataset_manifest_id": latest.get("superseded_dataset_manifest_id"),
            "epoch_bump": False,
        }
    _retract_unpublished_canonical_metadata(data_root, repaired_mid)

    measured: list[str] = []
    claims: list[LiveCorpusPartitionClaims] = []
    for cohort in existing_cohorts:
        claims.extend(
            _claims_for_cohort(
                data_root=data_root,
                cohort=cohort,
                prior_by_id=None,
                measured=measured,
                allow_measure=True,
            )
        )
    superseded = latest.get("superseded_dataset_manifest_id")
    if not str(latest.get("dataset_version") or "").endswith(CANONICAL_METADATA_SUFFIX):
        superseded = str(current_mid)
    else:
        superseded = str(superseded or current_mid)
    latest["superseded_dataset_manifest_id"] = superseded
    latest["dataset_manifest_id"] = repaired_mid
    latest["dataset_version"] = repaired_version
    version_n = int(current_version or latest.get("corpus_version") or 1)
    composition = [
        {
            "cohort_id": item["cohort_id"],
            "content_sha256": item["content_sha256"],
            "release_id": item["release_id"],
        }
        for item in existing_cohorts
    ]
    feature_union = _feature_union(existing_cohorts)
    yield_eligible_sum = sum(_lineage_int(item, "yield_eligible") for item in existing_cohorts)
    yield_missing_sum = sum(_lineage_int(item, "yield_missing") for item in existing_cohorts)
    census_rows_sum = sum(_lineage_int(item, "census_row_count") for item in existing_cohorts)
    obs_rows_sum = sum(_lineage_int(item, "observation_row_count") for item in existing_cohorts)
    clock_proposed = (published_at or datetime.now(tz=UTC)).astimezone(UTC)
    labels = {
        **REQUIRED_LABELS,
        "accepted_hypothesis_id": None,
        "census_row_count_cumulative": census_rows_sum,
        "cohort_id": latest["cohort_id"],
        "cohort_lineage": [str(item["cohort_id"]) for item in existing_cohorts],
        "corpus_version": version_n,
        "cumulative_composition": True,
        "dataset_terminal": _dataset_terminal_from_current(
            data_root, str(current_mid), latest
        ),
        "dataset_version": repaired_version,
        "discovery_coverage_class": latest.get("discovery_coverage_class"),
        "feature_families": feature_union,
        "feature_hint": None,
        "imported_at": _render_utc(clock_proposed),
        "is_current_corpus_version": True,
        "observation_row_count_cumulative": obs_rows_sum,
        "readiness_state": latest.get("readiness_state"),
        "release_id": latest["release_id"],
        "superseded_dataset_manifest_id": superseded,
        "yield_eligible": yield_eligible_sum,
        "yield_missing": yield_missing_sum,
    }
    lineage_out = {
        "cohorts": existing_cohorts,
        "corpus_dataset_id": CORPUS_DATASET_ID,
        "current_corpus_version": version_n,
        "current_dataset_manifest_id": repaired_mid,
        "versions": _lineage_versions(existing_cohorts),
    }
    dataset, _parts, fingerprint = _publish_from_claims(
        data_root=data_root,
        dataset_version=repaired_version,
        generation_task_id=CANONICAL_GENERATION_TASK_REPAIR,
        generation_run_id=f"repair-{current_mid[8:24]}" if current_mid.startswith("dataset-") else "repair-canonical-v1",
        generation_reason="METADATA_CONTRACT_REPAIR",
        published_at=clock_proposed,
        composition=composition,
        claims=claims,
        labels=labels,
        lineage_out=lineage_out,
        previous_current_mid=superseded,
        superseded_dataset_manifest_id=superseded,
        fault_before_visibility=fault_before_visibility,
    )
    return {
        "status": "REPAIRED",
        "corpus_version": version_n,
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_manifest_id": dataset.dataset_manifest_id,
        "dataset_version": dataset.dataset_version,
        "dataset_fingerprint": fingerprint,
        "logical_rows_measured_partitions": len(measured),
        "measured_logical_locations": measured,
        "superseded_dataset_manifest_id": superseded,
        "cohort_count": len(existing_cohorts),
        "epoch_bump": True,
    }


def import_live_cohort_canonical(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
    fault_before_visibility: Callable[[], None] | None = None,
) -> dict[str, Any]:
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
    existing_cohorts = [dict(item) for item in lineage.get("cohorts") or [] if isinstance(item, Mapping)]
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
        current_inspection = inspect_canonical_root(data_root, str(current_mid))
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
                    "epoch_bump": True,
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
            ):
                _require(prior.get(key), "CORPUS_LINEAGE_INCOMPLETE")

    version_n = len(existing_cohorts) + 1
    dataset_version = canonical_dataset_version(f"corpus-v{version_n}-{cohort_id}")
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
        "readiness_state": manifest.get("readiness_state"),
        "release_id": release_id,
        "sealed_at": _render_utc(sealed_at),
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
    }
