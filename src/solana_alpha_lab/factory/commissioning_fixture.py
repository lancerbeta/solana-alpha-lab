"""Deterministic commissioning fixture dataset published manifest-last outside Git."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

COMMISSIONING_DATASET_MANIFEST_ID = "DATASET-MANIFEST-FAST-LANE-COMMISSIONING-001"
COMMISSIONING_DATASET_ID = "DATASET-FAST-LANE-COMMISSIONING-001"
COMMISSIONING_PARTITION_ID = "PARTITION-FAST-LANE-COMMISSIONING-001"
COMMISSIONING_SCHEMA_ID = "SCHEMA-FAST-LANE-COMMISSIONING-001"
COMMISSIONING_FIXTURE_RELATIVE = (
    "tests/fixtures/fast_lane/commissioning_manifest_v1.json"
)
FIXTURE_TIMESTAMP = datetime(2026, 8, 25, 0, 0, 0, tzinfo=UTC)
COMMISSIONING_DATASET_FINGERPRINT = (
    "94a78df31a2707dec5cc8a32de429598abfd2f34bb45bc107b77ec85ee6f883c"
)


def _schema_sha256() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "columns": [
                    {"name": "observation_id", "type": "string"},
                    {"name": "metric_value", "type": "float64"},
                    {"name": "observed_at", "type": "timestamp[us, tz=UTC]"},
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _deterministic_parquet_bytes() -> bytes:
    table = pa.table(
        {
            "observation_id": pa.array(
                ["OBS-001", "OBS-002", "OBS-003"],
                type=pa.string(),
            ),
            "metric_value": pa.array([0.15, 0.22, 0.19], type=pa.float64()),
            "observed_at": pa.array(
                [FIXTURE_TIMESTAMP, FIXTURE_TIMESTAMP, FIXTURE_TIMESTAMP],
                type=pa.timestamp("us", tz="UTC"),
            ),
        }
    )
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


def _fixture_manifests() -> tuple[PartitionManifest, DatasetManifest]:
    parquet_bytes = _deterministic_parquet_bytes()
    logical_location = (
        "datasets/partitions/date=2026-08-25/"
        f"{COMMISSIONING_PARTITION_ID}.parquet"
    )
    file_sha256 = hashlib.sha256(parquet_bytes).hexdigest()
    partition_manifest = PartitionManifest(
        partition_manifest_id="PARTITION-MANIFEST-FAST-LANE-COMMISSIONING-001",
        dataset_manifest_id=COMMISSIONING_DATASET_MANIFEST_ID,
        partition_id=COMMISSIONING_PARTITION_ID,
        logical_location=logical_location,
        file_sha256=file_sha256,
        content_sha256=file_sha256,
        row_count=3,
        min_event_time=FIXTURE_TIMESTAMP,
        max_event_time=FIXTURE_TIMESTAMP,
        min_available_to_strategy_at=FIXTURE_TIMESTAMP,
        max_available_to_strategy_at=FIXTURE_TIMESTAMP,
        first_reliable_available_at=FIXTURE_TIMESTAMP,
        created_at=FIXTURE_TIMESTAMP,
    )
    dataset_manifest = DatasetManifest(
        dataset_manifest_id=COMMISSIONING_DATASET_MANIFEST_ID,
        dataset_id=COMMISSIONING_DATASET_ID,
        dataset_version="1.0",
        schema_id=COMMISSIONING_SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=COMMISSIONING_DATASET_FINGERPRINT,
        generation_task_id="HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1",
        generation_run_id="RUN-FAST-LANE-COMMISSIONING-FIXTURE-001",
        validation_receipt_sha256=hashlib.sha256(b"commissioning-fixture-v1").hexdigest(),
        first_reliable_available_at=FIXTURE_TIMESTAMP,
        created_at=FIXTURE_TIMESTAMP,
        content_sha256=hashlib.sha256(
            json.dumps(
                {
                    "dataset_fingerprint": COMMISSIONING_DATASET_FINGERPRINT,
                    "partition_file_sha256": file_sha256,
                    "profile": "fast-lane-commissioning-fixture-v1",
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    )
    return partition_manifest, dataset_manifest


def publish_commissioning_dataset(data_root: Path) -> DatasetManifest:
    """Publish immutable parquet bytes and manifest-last dataset inventory."""

    partition_manifest, dataset_manifest = _fixture_manifests()
    parquet_path = data_root / partition_manifest.logical_location
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.write_bytes(_deterministic_parquet_bytes())

    partition_manifest_path = (
        data_root
        / "datasets"
        / "manifests"
        / "partitions"
        / f"{partition_manifest.partition_manifest_id}.json"
    )
    partition_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    partition_manifest_path.write_bytes(canonical_manifest_bytes(partition_manifest))

    dataset_manifest_path = (
        data_root
        / "datasets"
        / "manifests"
        / f"{COMMISSIONING_DATASET_MANIFEST_ID}.json"
    )
    dataset_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_manifest_path.write_bytes(canonical_manifest_bytes(dataset_manifest))

    return dataset_manifest


def commissioning_dataset_fingerprint(root: Path) -> str:
    fixture_path = root / COMMISSIONING_FIXTURE_RELATIVE
    if fixture_path.is_file():
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        fingerprint = payload.get("dataset_fingerprint")
        if isinstance(fingerprint, str) and len(fingerprint) == 64:
            return fingerprint
    return COMMISSIONING_DATASET_FINGERPRINT


__all__ = [
    "COMMISSIONING_DATASET_FINGERPRINT",
    "COMMISSIONING_DATASET_MANIFEST_ID",
    "publish_commissioning_dataset",
    "commissioning_dataset_fingerprint",
]
