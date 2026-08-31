"""Compact sealed Discovery Evidence Release: seal → verify → RDP import.

Zero network. Historical replay shares Tokens V2 typed projection semantics
with ObservationSchedule but keeps distinct discovery-only provenance.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    FEATURE_FAMILY_ORDER,
    PROJECTION_ID,
    PROJECTION_VERSION,
    STATE_OBSERVED,
    TOKENS_V2_FIELD_KINDS,
    feature_families_from_typed_values,
    project_tokens_v2_row,
)
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

RELEASE_SCHEMA = "smial.discovery-evidence-release"
RELEASE_SCHEMA_VERSION = "1.0"
COMMIT_POINT_KIND = "DISCOVERY_EVIDENCE_RELEASE_PUBLICATION_V1"
DATASET_MANIFEST_ID = "DATASET-MANIFEST-DISCOVERY-EVIDENCE-RELEASE-001"
DATASET_ID = "DATASET-DISCOVERY-EVIDENCE-RELEASE-001"
SCHEMA_ID = "SCHEMA-DISCOVERY-EVIDENCE-RELEASE-001"
CENSUS_PARTITION_ID = "PARTITION-DISCOVERY-RELEASE-CENSUS-001"
CENSUS_PARTITION_MANIFEST_ID = "PARTITION-MANIFEST-DISCOVERY-RELEASE-CENSUS-001"
OBS_PARTITION_ID = "PARTITION-DISCOVERY-RELEASE-OBSERVATIONS-001"
OBS_PARTITION_MANIFEST_ID = "PARTITION-MANIFEST-DISCOVERY-RELEASE-OBSERVATIONS-001"
GENERATION_TASK_ID = "DISCOVERY_EVIDENCE_RELEASE_BRIDGE_V1"
HISTORICAL_EVIDENCE_ROLE = "DISCOVERY_ONLY_SECOND_LOOK"
SEARCH_PRIMITIVE_ID = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
POINT_ID = "R0"

RELEASE_MANIFEST_NAME = "release_manifest.json"
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
SOURCE_INVENTORY_NAME = "source_inventory.json"

REQUIRED_LABELS = {
    "evidence_role": HISTORICAL_EVIDENCE_ROLE,
    "outcome_previously_consumed": True,
    "confirmatory_reuse_forbidden": True,
    "provider_calls_for_bind": 0,
    "projection_id": PROJECTION_ID,
    "projection_version": PROJECTION_VERSION,
}


class DiscoveryReleaseError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DiscoveryReleaseError(code)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise DiscoveryReleaseError("CLOCK_NOT_AWARE")
    return parsed.astimezone(UTC)


def _render_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    )


def _parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
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
    return sink.getvalue().to_pybytes()


def _schema_sha256() -> str:
    return sha256_bytes(
        json.dumps(
            {
                "projection_id": PROJECTION_ID,
                "projection_version": PROJECTION_VERSION,
                "fields": sorted(TOKENS_V2_FIELD_KINDS),
                "tables": ["census", "observations"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _load_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscoveryReleaseError("SOURCE_BODY_CORRUPT") from exc
    if not isinstance(loaded, list) or not loaded:
        raise DiscoveryReleaseError("SOURCE_BODY_EMPTY")
    rows: list[dict[str, Any]] = []
    for item in loaded:
        if not isinstance(item, Mapping):
            raise DiscoveryReleaseError("SOURCE_ROW_INVALID")
        rows.append(dict(item))
    return rows


def load_source_inventory(
    *,
    body_path: Path,
    envelope_path: Path,
    source_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Build an explicit immutable source inventory from hash-bound raw."""
    _require(body_path.is_file() and not body_path.is_symlink(), "SOURCE_BODY_MISSING")
    _require(
        envelope_path.is_file() and not envelope_path.is_symlink(),
        "SOURCE_ENVELOPE_MISSING",
    )
    body = body_path.read_bytes()
    envelope_raw = envelope_path.read_bytes()
    try:
        envelope = json.loads(envelope_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscoveryReleaseError("SOURCE_ENVELOPE_CORRUPT") from exc
    _require(isinstance(envelope, Mapping), "SOURCE_ENVELOPE_CORRUPT")
    body_sha = sha256_bytes(body)
    expected = envelope.get("body_sha256")
    _require(isinstance(expected, str) and expected == body_sha, "SOURCE_HASH_MISMATCH")
    observed_at = envelope.get("observed_at")
    _require(isinstance(observed_at, str) and observed_at, "SOURCE_OBSERVED_AT_MISSING")
    # Event time alone never invents availability.
    _require("available_to_strategy_at" not in envelope, "RETROACTIVE_AVAILABILITY_FORBIDDEN")
    receipt_sha: str | None = None
    if source_receipt_path is not None:
        _require(
            source_receipt_path.is_file() and not source_receipt_path.is_symlink(),
            "SOURCE_RECEIPT_MISSING",
        )
        receipt_sha = sha256_bytes(source_receipt_path.read_bytes())
    rows = _load_rows(body)
    return {
        "body_path": str(body_path),
        "envelope_path": str(envelope_path),
        "body_sha256": body_sha,
        "envelope_sha256": sha256_bytes(envelope_raw),
        "source_receipt_sha256": receipt_sha,
        "observation_id": envelope.get("observation_id"),
        "observed_at": observed_at,
        "provider_calls": int(envelope.get("provider_calls") or 0),
        "source_kind": envelope.get("source_kind"),
        "row_count": len(rows),
        "rows": rows,
    }


def _release_id_for(inventory: Mapping[str, Any]) -> str:
    material = {
        "schema": RELEASE_SCHEMA,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
        "body_sha256": inventory["body_sha256"],
        "envelope_sha256": inventory["envelope_sha256"],
        "source_receipt_sha256": inventory.get("source_receipt_sha256"),
        "observed_at": inventory["observed_at"],
        "field_ids": sorted(TOKENS_V2_FIELD_KINDS),
    }
    return canonical_sha256(material)


def _build_tables(
    inventory: Mapping[str, Any],
    *,
    release_id: str,
) -> tuple[pa.Table, pa.Table, list[dict[str, Any]], list[str], int, int]:
    observed_at = str(inventory["observed_at"])
    rows = inventory["rows"]
    assert isinstance(rows, list)
    census_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    typed_all: list[dict[str, Any]] = []
    identity_fields = {
        "FIELD-TOKEN-MINT-001",
        "FIELD-FIRST-POOL-CREATED-AT-001",
        "FIELD-FIRST-POOL-SOURCE-001",
        "FIELD-FIRST-SEEN-AT-001",
    }
    mints_with_signal: set[str] = set()
    for row in rows:
        mint = row.get("id") or row.get("mint")
        _require(isinstance(mint, str) and mint, "TOKEN_MINT_MISSING")
        typed = project_tokens_v2_row(row)
        typed_all.extend(typed)
        first_pool = row.get("firstPool") if isinstance(row.get("firstPool"), Mapping) else {}
        census_rows.append(
            {
                "release_id": release_id,
                "source_schedule_sha256": None,
                "activation_id": None,
                "mint": mint,
                "discovery_first_reliable_available_at": None,
                "authoritative_anchor": first_pool.get("createdAt"),
                "candidate_state": "HISTORICAL_RETAINED",
                "membership_state": "INCLUDED",
                "sampling_policy": "FULL_SOURCE_BODY",
                "sampling_seed": None,
                "inclusion_probability": "1",
                "selected_or_excluded": "SELECTED",
                "exclusion_reason": None,
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "source_request_sha256": None,
                "source_response_sha256": inventory["body_sha256"],
                "evidence_role": HISTORICAL_EVIDENCE_ROLE,
            }
        )
        for item in typed:
            if item["state"] == STATE_OBSERVED and item["field_id"] not in identity_fields:
                mints_with_signal.add(mint)
            observation_rows.append(
                {
                    "release_id": release_id,
                    "mint": mint,
                    "point_id": POINT_ID,
                    "primitive_id": SEARCH_PRIMITIVE_ID,
                    "field_id": item["field_id"],
                    "value_kind": item["value_kind"],
                    "typed_value_or_null": (
                        None
                        if item["typed_value_or_null"] is None
                        else str(item["typed_value_or_null"])
                    ),
                    "state": item["state"],
                    "missing_reason": item["missing_reason"],
                    "event_time": observed_at,
                    "request_started_at": None,
                    "response_received_at": observed_at,
                    "first_reliable_available_at": None,
                    "request_sha256": None,
                    "call_occurrence_id": None,
                    "response_sha256": inventory["body_sha256"],
                    "source_dataset_manifest_id": None,
                    "evidence_role": HISTORICAL_EVIDENCE_ROLE,
                    "confirmatory_reuse_forbidden": True,
                }
            )
    families = feature_families_from_typed_values(typed_all)
    census = pa.Table.from_pylist(census_rows)
    observations = pa.Table.from_pylist(observation_rows)
    yield_eligible = len(mints_with_signal)
    yield_missing = max(0, len(census_rows) - yield_eligible)
    return census, observations, typed_all, families, yield_eligible, yield_missing


def seal_discovery_release(
    *,
    inventory: Mapping[str, Any],
    release_root: Path,
    sealed_at: datetime | None = None,
) -> dict[str, Any]:
    """Write a compact content-addressed release (manifest last)."""
    _require(inventory.get("provider_calls") == 0, "PROVIDER_CALLS_NOT_ZERO")
    if release_root.exists():
        if any(release_root.iterdir()):
            raise DiscoveryReleaseError("RELEASE_ROOT_NOT_EMPTY")
    else:
        release_root.mkdir(parents=True, exist_ok=True)
    sealed = (sealed_at or datetime.now(tz=UTC)).astimezone(UTC)
    release_id = _release_id_for(inventory)
    census, observations, typed_all, families, yield_eligible, yield_missing = (
        _build_tables(inventory, release_id=release_id)
    )
    census_bytes = _parquet_bytes(census)
    obs_bytes = _parquet_bytes(observations)
    (release_root / CENSUS_NAME).write_bytes(census_bytes)
    (release_root / OBSERVATIONS_NAME).write_bytes(obs_bytes)
    source_inventory = {
        "body_sha256": inventory["body_sha256"],
        "envelope_sha256": inventory["envelope_sha256"],
        "source_receipt_sha256": inventory.get("source_receipt_sha256"),
        "observation_id": inventory.get("observation_id"),
        "observed_at": inventory["observed_at"],
        "provider_calls": inventory["provider_calls"],
        "source_kind": inventory.get("source_kind"),
        "row_count": inventory["row_count"],
    }
    _write_json(release_root / SOURCE_INVENTORY_NAME, source_inventory)
    dataset_terminal = (
        "SAMPLE_VALID" if yield_eligible > 0 and families else "SAMPLE_INVALID"
    )
    manifest = {
        "schema": RELEASE_SCHEMA,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": release_id,
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
        "sealed_at": _render_utc(sealed),
        "source_observed_at": inventory["observed_at"],
        "evidence_role": HISTORICAL_EVIDENCE_ROLE,
        "outcome_previously_consumed": True,
        "confirmatory_reuse_forbidden": True,
        "provider_calls": 0,
        "feature_families": families,
        "feature_family_order": list(FEATURE_FAMILY_ORDER),
        "census_sha256": sha256_bytes(census_bytes),
        "observations_sha256": sha256_bytes(obs_bytes),
        "source_inventory_sha256": sha256_bytes(
            (release_root / SOURCE_INVENTORY_NAME).read_bytes()
        ),
        "census_row_count": census.num_rows,
        "observation_row_count": observations.num_rows,
        "yield_eligible": yield_eligible,
        "yield_missing": yield_missing,
        "dataset_terminal": dataset_terminal,
        "schema_sha256": _schema_sha256(),
        "release_state": "SEALED",
    }
    # Manifest last: partial trees without this file are invisible to import.
    _write_json(release_root / RELEASE_MANIFEST_NAME, manifest)
    return dict(manifest)


def verify_discovery_release(release_root: Path) -> dict[str, Any]:
    """Fail-closed content-addressed verify. Partial releases raise."""
    manifest_path = release_root / RELEASE_MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise DiscoveryReleaseError("RELEASE_PARTIAL_OR_MISSING_MANIFEST")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscoveryReleaseError("RELEASE_MANIFEST_CORRUPT") from exc
    _require(isinstance(manifest, dict), "RELEASE_MANIFEST_CORRUPT")
    for name, key in (
        (CENSUS_NAME, "census_sha256"),
        (OBSERVATIONS_NAME, "observations_sha256"),
        (SOURCE_INVENTORY_NAME, "source_inventory_sha256"),
    ):
        path = release_root / name
        _require(path.is_file() and not path.is_symlink(), "RELEASE_ARTIFACT_MISSING")
        digest = sha256_bytes(path.read_bytes())
        _require(digest == manifest.get(key), "RELEASE_HASH_MISMATCH")
    _require(manifest.get("release_state") == "SEALED", "RELEASE_NOT_SEALED")
    _require(manifest.get("confirmatory_reuse_forbidden") is True, "CONFIRMATION_CLAIM")
    _require(
        manifest.get("evidence_role") == HISTORICAL_EVIDENCE_ROLE,
        "EVIDENCE_ROLE_INVALID",
    )
    families = manifest.get("feature_families")
    _require(isinstance(families, list) and families, "FEATURE_FAMILIES_MISSING")
    recomputed = _release_id_for(
        {
            "body_sha256": json.loads(
                (release_root / SOURCE_INVENTORY_NAME).read_text(encoding="utf-8")
            )["body_sha256"],
            "envelope_sha256": json.loads(
                (release_root / SOURCE_INVENTORY_NAME).read_text(encoding="utf-8")
            )["envelope_sha256"],
            "source_receipt_sha256": json.loads(
                (release_root / SOURCE_INVENTORY_NAME).read_text(encoding="utf-8")
            ).get("source_receipt_sha256"),
            "observed_at": json.loads(
                (release_root / SOURCE_INVENTORY_NAME).read_text(encoding="utf-8")
            )["observed_at"],
        }
    )
    _require(recomputed == manifest.get("release_id"), "RELEASE_ID_MISMATCH")
    return manifest


def _publish_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != payload:
            raise DiscoveryReleaseError("CANONICAL_TARGET_CONFLICT")
        return
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(payload)
    try:
        if path.is_file():
            if path.read_bytes() != payload:
                raise DiscoveryReleaseError("CANONICAL_TARGET_CONFLICT")
        else:
            tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def import_discovery_release(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
) -> dict[str, Any]:
    """Import a verified sealed release into an RDP root (idempotent)."""
    manifest = verify_discovery_release(release_root)
    imported_at = (import_time or datetime.now(tz=UTC)).astimezone(UTC)
    # Forge availability is import time — never backdated to observation time.
    source_observed = _parse_utc(str(manifest["source_observed_at"]))
    _require(imported_at >= source_observed, "IMPORT_BEFORE_OBSERVATION")
    release_id = str(manifest["release_id"])
    date_key = imported_at.strftime("%Y-%m-%d")
    census_rel = (
        f"datasets/partitions/date={date_key}/"
        f"{CENSUS_PARTITION_ID}-{release_id[:16]}.parquet"
    )
    obs_rel = (
        f"datasets/partitions/date={date_key}/"
        f"{OBS_PARTITION_ID}-{release_id[:16]}.parquet"
    )
    census_bytes = (release_root / CENSUS_NAME).read_bytes()
    obs_bytes = (release_root / OBSERVATIONS_NAME).read_bytes()
    content_sha = sha256_bytes(census_bytes + obs_bytes)
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": DATASET_MANIFEST_ID,
            "release_id": release_id,
            "content_sha256": content_sha,
            "projection_id": PROJECTION_ID,
        }
    )
    created_at = imported_at
    available_at = imported_at
    dataset = DatasetManifest(
        dataset_manifest_id=DATASET_MANIFEST_ID,
        dataset_id=DATASET_ID,
        dataset_version="1.0",
        schema_id=SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id=GENERATION_TASK_ID,
        generation_run_id=f"import-{release_id[:16]}",
        validation_receipt_sha256=sha256_bytes(
            (release_root / RELEASE_MANIFEST_NAME).read_bytes()
        ),
        first_reliable_available_at=available_at,
        created_at=created_at,
        content_sha256=content_sha,
    )
    census_part = PartitionManifest(
        partition_manifest_id=CENSUS_PARTITION_MANIFEST_ID,
        dataset_manifest_id=DATASET_MANIFEST_ID,
        partition_id=CENSUS_PARTITION_ID,
        logical_location=census_rel,
        file_sha256=sha256_bytes(census_bytes),
        content_sha256=sha256_bytes(census_bytes),
        row_count=int(manifest["census_row_count"]),
        min_event_time=source_observed,
        max_event_time=source_observed,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=created_at,
    )
    obs_part = PartitionManifest(
        partition_manifest_id=OBS_PARTITION_MANIFEST_ID,
        dataset_manifest_id=DATASET_MANIFEST_ID,
        partition_id=OBS_PARTITION_ID,
        logical_location=obs_rel,
        file_sha256=sha256_bytes(obs_bytes),
        content_sha256=sha256_bytes(obs_bytes),
        row_count=int(manifest["observation_row_count"]),
        min_event_time=source_observed,
        max_event_time=source_observed,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=created_at,
    )
    labels = {
        **REQUIRED_LABELS,
        "release_id": release_id,
        "feature_families": list(manifest["feature_families"]),
        "feature_hint": None,
        "yield_eligible": int(manifest["yield_eligible"]),
        "yield_missing": int(manifest["yield_missing"]),
        "dataset_terminal": str(manifest.get("dataset_terminal") or "SAMPLE_INVALID"),
        "source_observed_at": manifest["source_observed_at"],
        "imported_at": _render_utc(imported_at),
        "accepted_hypothesis_id": None,
    }
    published = {
        "commit_point": COMMIT_POINT_KIND,
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "release_id": release_id,
        "imported_at": _render_utc(imported_at),
    }
    root = Path(data_root)
    _publish_bytes(root / census_rel, census_bytes)
    _publish_bytes(root / obs_rel, obs_bytes)
    _publish_bytes(
        root / f"datasets/manifests/partitions/{CENSUS_PARTITION_MANIFEST_ID}.json",
        canonical_manifest_bytes(census_part),
    )
    _publish_bytes(
        root / f"datasets/manifests/partitions/{OBS_PARTITION_MANIFEST_ID}.json",
        canonical_manifest_bytes(obs_part),
    )
    _publish_bytes(
        root / f"datasets/manifests/{DATASET_MANIFEST_ID}.labels.json",
        json.dumps(labels, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _publish_bytes(
        root / f"datasets/manifests/{DATASET_MANIFEST_ID}.json",
        canonical_manifest_bytes(dataset),
    )
    # Publication marker last so partial imports stay invisible.
    _publish_bytes(
        root / f"datasets/manifests/{DATASET_MANIFEST_ID}.published",
        json.dumps(published, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    return {
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "release_id": release_id,
        "feature_families": list(manifest["feature_families"]),
        "evidence_role": HISTORICAL_EVIDENCE_ROLE,
        "imported_at": _render_utc(imported_at),
        "yield_eligible": int(manifest["yield_eligible"]),
    }


def clear_imported_release(data_root: Path) -> None:
    """Test helper: remove imported discovery-release artifacts if present."""
    root = Path(data_root)
    for relative in (
        f"datasets/manifests/{DATASET_MANIFEST_ID}.json",
        f"datasets/manifests/{DATASET_MANIFEST_ID}.labels.json",
        f"datasets/manifests/{DATASET_MANIFEST_ID}.published",
        f"datasets/manifests/partitions/{CENSUS_PARTITION_MANIFEST_ID}.json",
        f"datasets/manifests/partitions/{OBS_PARTITION_MANIFEST_ID}.json",
    ):
        path = root / relative
        if path.is_file():
            path.unlink()
