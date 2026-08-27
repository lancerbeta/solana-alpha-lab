"""Hash-verified offline importer for the 2026-08-24 valuation-window panel.

Explicit source only. No provider/API/RPC/WSS. Raw bodies stay outside Git.
X is R0-only. Dataset role is DISCOVERY_ONLY_SECOND_LOOK.
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
from solana_alpha_lab.factory.early_market_panel_field_semantics import (
    FEATURE_ID,
    FIELD_SEMANTICS_UNPROVEN,
    FieldSemanticsError,
    classify_r0_mix,
    prove_r0_taker_volume_mix_semantics,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

DATASET_MANIFEST_ID = "DATASET-MANIFEST-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
DATASET_ID = "DATASET-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
PARTITION_ID = "PARTITION-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
PARTITION_MANIFEST_ID = "PARTITION-MANIFEST-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
SCHEMA_ID = "SCHEMA-EARLY-MARKET-PANEL-VALUATION-WINDOW-001"
CAPTURE_ATOM_ID = "EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1"
R0_OBSERVATION_ID = "DISCOVERY:SEARCH_R0"
REQUIRED_LABELS = {
    "evidence_role": "DISCOVERY_ONLY_SECOND_LOOK",
    "outcome_previously_consumed": True,
    "confirmatory_reuse_forbidden": True,
    "provider_calls_for_bind": 0,
}
FORBIDDEN_HYPOTHESIS_ID = "HYP-EARLY-TAKER-VOLUME-MIX-H900-V1"
CLOSED_FAMILY = "CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY"
GIT_RECEIPT_RELATIVE = (
    "docs/evidence/early_valuation_liquidity_divergence_confirmation/"
    "a1_runtime_receipt_v1.json"
)
GIT_RECEIPT_SHA256 = "a8c8df4a7c02a8e6cf4d2be2fe004f2cfbff170efcf5645064788ea20f12db63"
PANEL_CREATED_AT = datetime(2026, 8, 24, 0, 24, 22, tzinfo=UTC)
LOGICAL_LOCATION = (
    "datasets/partitions/date=2026-08-24/"
    f"{PARTITION_ID}.parquet"
)
LABELS_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.labels.json"


class EarlyMarketPanelImportError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EarlyMarketPanelImportError(code)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _schema_sha256() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "columns": [
                    {"name": "mint", "type": "string"},
                    {"name": "observed_at", "type": "timestamp[us, tz=UTC]"},
                    {"name": "available_to_strategy_at", "type": "timestamp[us, tz=UTC]"},
                    {"name": "r0_taker_volume_mix", "type": "float64"},
                    {"name": "missingness_code", "type": "string"},
                    {"name": "buy_volume_present", "type": "bool"},
                    {"name": "sell_volume_present", "type": "bool"},
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _load_json_bytes(path: Path) -> tuple[bytes, object]:
    _require(path.is_file() and not path.is_symlink(), "SOURCE_FILE_MISSING")
    payload = path.read_bytes()
    try:
        loaded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarlyMarketPanelImportError("SOURCE_JSON_INVALID") from exc
    return payload, loaded


def _index_receipt_manifests(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_retention = receipt.get("raw_retention")
    _require(isinstance(raw_retention, Mapping), "RAW_RETENTION_MISSING")
    manifests = raw_retention.get("manifests")
    _require(isinstance(manifests, list) and manifests, "RAW_MANIFESTS_MISSING")
    index: dict[str, dict[str, Any]] = {}
    for row in manifests:
        _require(isinstance(row, Mapping), "RAW_MANIFEST_INVALID")
        observation_id = row.get("observation_id")
        _require(isinstance(observation_id, str) and observation_id, "RAW_MANIFEST_INVALID")
        _require(observation_id not in index, "RAW_MANIFEST_DUPLICATE")
        index[observation_id] = dict(row)
    return index


def _resolve_r0_body(source_root: Path, binding: Mapping[str, Any]) -> Path:
    relative = binding.get("path")
    _require(isinstance(relative, str) and relative, "R0_PATH_MISSING")
    name = Path(relative.replace("\\", "/")).name
    _require(name == "DISCOVERY_SEARCH_R0.body", "R0_PATH_INVALID")
    root = source_root.resolve()
    candidate = (source_root / name).resolve()
    _require(candidate.is_relative_to(root), "R0_PATH_ESCAPE")
    _require(candidate.is_file() and not candidate.is_symlink(), "R0_BODY_MISSING")
    return candidate


def _parse_rows(payload: object) -> list[dict[str, Any]]:
    _require(isinstance(payload, list) and payload, "R0_BODY_NOT_LIST")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        _require(isinstance(item, Mapping), "R0_ROW_INVALID")
        mint = item.get("id")
        _require(isinstance(mint, str) and mint, "R0_MINT_INVALID")
        _require(mint not in seen, "R0_MINT_DUPLICATE")
        seen.add(mint)
        rows.append(dict(item))
    return rows


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        return PANEL_CREATED_AT
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return PANEL_CREATED_AT
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalized_table(
    rows: list[dict[str, Any]],
    *,
    available_at: datetime,
) -> pa.Table:
    mints: list[str] = []
    observed: list[datetime] = []
    available: list[datetime] = []
    mixes: list[float | None] = []
    codes: list[str] = []
    buy_present: list[bool] = []
    sell_present: list[bool] = []
    for row in rows:
        mix, code = classify_r0_mix(row)
        stats = row.get("stats5m") if isinstance(row.get("stats5m"), Mapping) else {}
        mints.append(str(row["id"]))
        observed.append(available_at)
        available.append(available_at)
        mixes.append(mix)
        codes.append(code or "")
        buy_present.append(isinstance(stats, Mapping) and "buyVolume" in stats)
        sell_present.append(isinstance(stats, Mapping) and "sellVolume" in stats)
    return pa.table(
        {
            "mint": pa.array(mints, type=pa.string()),
            "observed_at": pa.array(observed, type=pa.timestamp("us", tz="UTC")),
            "available_to_strategy_at": pa.array(
                available, type=pa.timestamp("us", tz="UTC")
            ),
            "r0_taker_volume_mix": pa.array(mixes, type=pa.float64()),
            "missingness_code": pa.array(codes, type=pa.string()),
            "buy_volume_present": pa.array(buy_present, type=pa.bool_()),
            "sell_volume_present": pa.array(sell_present, type=pa.bool_()),
        }
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


def dataset_labels() -> dict[str, Any]:
    return {
        **REQUIRED_LABELS,
        "feature_hint": FEATURE_ID,
        "accepted_hypothesis_id": None,
        "closed_family": CLOSED_FAMILY,
        "capture_atom_id": CAPTURE_ATOM_ID,
        "x_uses_r0_only": True,
        "forbidden_hypothesis_id": FORBIDDEN_HYPOTHESIS_ID,
    }


def load_bound_panel(data_root: Path) -> dict[str, Any] | None:
    manifest_path = Path(data_root) / "datasets" / "manifests" / f"{DATASET_MANIFEST_ID}.json"
    labels_path = Path(data_root) / LABELS_RELATIVE
    partition_path = (
        Path(data_root)
        / "datasets"
        / "manifests"
        / "partitions"
        / f"{PARTITION_MANIFEST_ID}.json"
    )
    if not manifest_path.is_file() or not labels_path.is_file() or not partition_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    partition = json.loads(partition_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(labels, dict) or not isinstance(partition, dict):
        return None
    for key, expected in REQUIRED_LABELS.items():
        if labels.get(key) != expected:
            return None
    if labels.get("accepted_hypothesis_id") is not None:
        return None
    fingerprint = manifest.get("dataset_fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        return None
    parquet_rel = partition.get("logical_location")
    expected_file = partition.get("file_sha256")
    if not isinstance(parquet_rel, str) or not isinstance(expected_file, str):
        return None
    parquet_path = Path(data_root) / parquet_rel
    if not parquet_path.is_file() or parquet_path.is_symlink():
        return None
    if sha256_bytes(parquet_path.read_bytes()) != expected_file:
        return None
    return {
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "labels": labels,
        "row_count": int(labels.get("row_count") or 0),
        "yield_eligible": int(labels.get("yield_eligible") or 0),
        "yield_missing": int(labels.get("yield_missing") or 0),
        "feature_hint": FEATURE_ID,
    }


def import_early_market_panel(
    *,
    source_root: Path,
    data_root: Path,
    source_receipt_path: Path,
    expected_receipt_sha256: str | None = None,
    generation_task_id: str = "HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1",
    generation_run_id: str = "RUN-EARLY-MARKET-PANEL-TEMP-001",
) -> dict[str, Any]:
    _require(source_root is not None, "SOURCE_REQUIRED")
    _require(source_root.is_dir() and not source_root.is_symlink(), "SOURCE_INVALID")
    receipt_bytes, receipt_obj = _load_json_bytes(source_receipt_path)
    _require(isinstance(receipt_obj, dict), "SOURCE_RECEIPT_INVALID")
    receipt: dict[str, Any] = receipt_obj
    observed_receipt_sha = sha256_bytes(receipt_bytes)
    if expected_receipt_sha256 is not None:
        _require(observed_receipt_sha == expected_receipt_sha256, "RECEIPT_HASH_MISMATCH")
    index = _index_receipt_manifests(receipt)
    r0_binding = index.get(R0_OBSERVATION_ID)
    _require(isinstance(r0_binding, Mapping), "R0_BINDING_MISSING")
    expected_body_sha = r0_binding.get("sha256")
    _require(isinstance(expected_body_sha, str) and len(expected_body_sha) == 64, "R0_HASH_MISSING")
    body_path = _resolve_r0_body(source_root, r0_binding)
    _require(body_path.is_file() and not body_path.is_symlink(), "R0_BODY_MISSING")
    body_bytes = body_path.read_bytes()
    _require(sha256_bytes(body_bytes) == expected_body_sha, "R0_BODY_HASH_MISMATCH")
    try:
        body_obj = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarlyMarketPanelImportError("R0_BODY_JSON_INVALID") from exc
    envelope_name = r0_binding.get("envelope_path")
    _require(isinstance(envelope_name, str) and envelope_name, "R0_ENVELOPE_PATH_MISSING")
    envelope_path = (source_root / Path(str(envelope_name).replace("\\", "/")).name).resolve()
    _require(envelope_path.is_relative_to(source_root.resolve()), "R0_PATH_ESCAPE")
    _require(envelope_path.is_file() and not envelope_path.is_symlink(), "R0_ENVELOPE_MISSING")
    envelope_bytes, envelope_obj = _load_json_bytes(envelope_path)
    expected_envelope = r0_binding.get("capture_envelope_sha256")
    _require(
        isinstance(expected_envelope, str) and len(expected_envelope) == 64,
        "R0_ENVELOPE_HASH_MISSING",
    )
    _require(sha256_bytes(envelope_bytes) == expected_envelope, "R0_ENVELOPE_HASH_MISMATCH")
    available_at = PANEL_CREATED_AT
    if isinstance(envelope_obj, Mapping) and envelope_obj.get("observed_at"):
        available_at = _parse_timestamp(envelope_obj.get("observed_at"))
    elif isinstance(r0_binding.get("observed_at"), str):
        available_at = _parse_timestamp(r0_binding.get("observed_at"))
    rows = _parse_rows(body_obj)
    try:
        semantics = prove_r0_taker_volume_mix_semantics(
            rows, x_source_observation=R0_OBSERVATION_ID
        )
    except FieldSemanticsError as exc:
        raise EarlyMarketPanelImportError(FIELD_SEMANTICS_UNPROVEN) from exc
    table = _normalized_table(rows, available_at=available_at)
    parquet_bytes = _parquet_bytes(table)
    file_sha256 = sha256_bytes(parquet_bytes)
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": DATASET_MANIFEST_ID,
            "r0_body_sha256": expected_body_sha,
            "parquet_sha256": file_sha256,
            "feature_id": FEATURE_ID,
            "evidence_role": REQUIRED_LABELS["evidence_role"],
            "confirmatory_reuse_forbidden": True,
            "outcome_previously_consumed": True,
        }
    )
    labels = {
        **dataset_labels(),
        "row_count": table.num_rows,
        "yield_eligible": semantics["yield_eligible"],
        "yield_missing": semantics["yield_missing"],
        "missingness_codes": semantics["missingness_codes"],
        "source_receipt_sha256": observed_receipt_sha,
        "r0_body_sha256": expected_body_sha,
        "dataset_fingerprint": fingerprint,
        "field_semantics_terminal": semantics["terminal"],
        "provider_calls_actual": 0,
    }
    existing = load_bound_panel(data_root)
    if existing is not None and existing["dataset_fingerprint"] == fingerprint:
        return {
            "status": "IDEMPOTENT_REUSE",
            "dataset_manifest_id": DATASET_MANIFEST_ID,
            "dataset_fingerprint": fingerprint,
            "row_count": existing["row_count"],
            "yield_eligible": existing["yield_eligible"],
            "yield_missing": existing["yield_missing"],
            "provider_calls_actual": 0,
            "field_semantics": semantics,
            "labels": existing["labels"],
            "epoch_material_changed": False,
        }
    if existing is not None and existing["dataset_fingerprint"] != fingerprint:
        raise EarlyMarketPanelImportError("DATASET_FINGERPRINT_CONFLICT")

    partition_manifest = PartitionManifest(
        partition_manifest_id=PARTITION_MANIFEST_ID,
        dataset_manifest_id=DATASET_MANIFEST_ID,
        partition_id=PARTITION_ID,
        logical_location=LOGICAL_LOCATION,
        file_sha256=file_sha256,
        content_sha256=file_sha256,
        row_count=table.num_rows,
        min_event_time=available_at,
        max_event_time=available_at,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=available_at,
    )
    dataset_manifest = DatasetManifest(
        dataset_manifest_id=DATASET_MANIFEST_ID,
        dataset_id=DATASET_ID,
        dataset_version="1.0",
        schema_id=SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id=generation_task_id,
        generation_run_id=generation_run_id,
        validation_receipt_sha256=canonical_sha256(
            {
                "field_semantics_terminal": semantics["terminal"],
                "r0_body_sha256": expected_body_sha,
            }
        ),
        first_reliable_available_at=available_at,
        created_at=available_at,
        content_sha256=canonical_sha256(
            {
                "dataset_fingerprint": fingerprint,
                "partition_file_sha256": file_sha256,
                "labels": REQUIRED_LABELS,
            }
        ),
    )
    parquet_path = Path(data_root) / LOGICAL_LOCATION
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.write_bytes(parquet_bytes)
    partition_path = (
        Path(data_root)
        / "datasets"
        / "manifests"
        / "partitions"
        / f"{PARTITION_MANIFEST_ID}.json"
    )
    partition_path.parent.mkdir(parents=True, exist_ok=True)
    partition_path.write_bytes(canonical_manifest_bytes(partition_manifest))
    manifest_path = Path(data_root) / "datasets" / "manifests" / f"{DATASET_MANIFEST_ID}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(canonical_manifest_bytes(dataset_manifest))
    labels_path = Path(data_root) / LABELS_RELATIVE
    labels_path.write_text(
        json.dumps(labels, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "IMPORTED",
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
        "row_count": table.num_rows,
        "yield_eligible": semantics["yield_eligible"],
        "yield_missing": semantics["yield_missing"],
        "provider_calls_actual": 0,
        "field_semantics": semantics,
        "labels": labels,
        "epoch_material_changed": True,
    }


__all__ = [
    "CAPTURE_ATOM_ID",
    "CLOSED_FAMILY",
    "DATASET_MANIFEST_ID",
    "EarlyMarketPanelImportError",
    "FEATURE_ID",
    "FORBIDDEN_HYPOTHESIS_ID",
    "GIT_RECEIPT_RELATIVE",
    "GIT_RECEIPT_SHA256",
    "REQUIRED_LABELS",
    "import_early_market_panel",
    "load_bound_panel",
]
