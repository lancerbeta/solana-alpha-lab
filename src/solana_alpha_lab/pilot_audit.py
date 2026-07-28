"""Deterministic offline audit of the frozen TASK-13 evidence population."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path, PurePosixPath
from typing import Any, TypeAlias

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

AUDIT_RESULT_SCHEMA = "solana_alpha_lab.pilot_audit_result"
AUDIT_RESULT_SCHEMA_VERSION = "1.0"
EXPECTED_CONTRACT_ID = "CONTRACT-T13-PILOT-AUDIT-001"
EXPECTED_POPULATION_ID = "POPULATION-T13-BOUNDED-HISTORICAL-EVIDENCE-001"
EXPECTED_POPULATION_SHA256 = (
    "873cb9e17ee341fe0163e7dbef0a35559bc7f3fc0b5807418051a90d9c64e7e0"
)
RAW_COLUMNS = (
    "raw_event_id",
    "idempotency_key",
    "source",
    "response_status",
    "error_class",
    "content_sha256",
    "event_time",
    "observed_at",
    "first_reliable_available_at",
    "available_to_strategy_at",
    "ingested_at",
)
PIT_PAIRS = (
    ("event_time", "observed_at"),
    ("observed_at", "first_reliable_available_at"),
    ("first_reliable_available_at", "available_to_strategy_at"),
    ("available_to_strategy_at", "ingested_at"),
)
PROJECTION_TABLES = (
    "raw_api_events",
    "quote_attempts",
    "execution_attempts",
)


class PilotAuditContractError(ValueError):
    """Frozen population or retained evidence failed closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotAuditContractError(code)


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name}_must_be_mapping")
    return value


def _sequence(name: str, value: Any) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray)),
        f"{name}_must_be_sequence",
    )
    return value


def _integer(name: str, value: Any) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{name}_must_be_integer",
    )
    return value


def _text(name: str, value: Any) -> str:
    _require(isinstance(value, str) and bool(value), f"{name}_must_be_text")
    return value


def _sha256(name: str, value: Any) -> str:
    text = _text(name, value)
    _require(
        len(text) == 64
        and all(character in "0123456789abcdef" for character in text),
        f"{name}_must_be_lowercase_sha256",
    )
    return text


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _safe_input_path(repository_root: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    _require(
        not pure.is_absolute()
        and ".." not in pure.parts
        and "\\" not in relative_path,
        "input_path_unsafe",
    )
    root = repository_root.resolve()
    candidate = root.joinpath(*pure.parts)
    resolved = candidate.resolve()
    _require(resolved.is_relative_to(root), "input_path_escapes_repository")
    _require(
        candidate.is_file() and not candidate.is_symlink(),
        "input_missing_or_unsafe",
    )
    return candidate


def _load_population(
    repository_root: Path,
    population_path: str | Path,
    *,
    expected_sha256: str,
) -> tuple[Mapping[str, Any], str]:
    path_text = PurePosixPath(population_path).as_posix()
    path = _safe_input_path(repository_root, path_text)
    data = path.read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    _require(
        actual_sha256 == _sha256("expected_population_sha256", expected_sha256),
        "population_fixture_sha256_mismatch",
    )
    _require(data.endswith(b"\n"), "population_fixture_final_newline_required")
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PilotAuditContractError("population_fixture_json_invalid") from exc
    population = _mapping("population_fixture", document)
    _require(
        population.get("contract_id") == EXPECTED_CONTRACT_ID,
        "population_contract_id_drift",
    )
    _require(
        population.get("population_id") == EXPECTED_POPULATION_ID,
        "population_id_drift",
    )
    _require(
        population.get("status")
        == "FROZEN_BOUNDED_HISTORICAL_EVIDENCE_CONTRACT",
        "population_status_not_frozen",
    )
    _require(
        population.get("sustained_pilot_claim") is False,
        "sustained_pilot_claim_forbidden",
    )
    _require(
        population.get("provider_purchase_claim") is False,
        "provider_purchase_claim_forbidden",
    )
    return population, actual_sha256


def _verify_file_record(
    repository_root: Path,
    raw_record: Any,
) -> tuple[Mapping[str, Any], Path]:
    record = _mapping("data_file", raw_record)
    relative_path = _text("data_file.path", record.get("path"))
    path = _safe_input_path(repository_root, relative_path)
    expected_bytes = _integer("data_file.bytes", record.get("bytes"))
    _require(expected_bytes > 0, "data_file_bytes_not_positive")
    _require(path.stat().st_size == expected_bytes, "input_bytes_mismatch")
    expected_hash = _sha256("data_file.sha256", record.get("sha256"))
    _require(
        hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash,
        "input_sha256_mismatch",
    )
    kind = _text("data_file.kind", record.get("kind"))
    _require(
        kind in {"RAW_PARQUET", "DUCKDB_PROJECTION"},
        "data_file_kind_unknown",
    )
    _require(
        _integer("data_file.rows", record.get("rows")) > 0,
        "data_file_rows_not_positive",
    )
    _text("data_file.slice_id", record.get("slice_id"))
    _text("data_file.asset_id", record.get("asset_id"))
    return record, path


def _string_values(table: pa.Table, name: str) -> list[str | None]:
    _require(name in table.column_names, f"raw_column_{name}_missing")
    values = pc.cast(table[name], pa.string()).combine_chunks().to_pylist()
    return [None if value is None else str(value) for value in values]


def _timestamp_values(table: pa.Table, name: str) -> list[int | None]:
    _require(name in table.column_names, f"raw_column_{name}_missing")
    values = pc.cast(table[name], pa.int64()).combine_chunks().to_pylist()
    return [None if value is None else int(value) for value in values]


def _decimal_milliseconds(total_microseconds: int, count: int) -> str | None:
    if count == 0:
        return None
    with localcontext() as context:
        context.prec = 28
        value = Decimal(total_microseconds) / Decimal(count) / Decimal(1000)
        rendered = format(value.quantize(Decimal("0.000001")), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _status_counts(table: pa.Table) -> list[dict[str, JsonValue]]:
    sources = _string_values(table, "source")
    statuses = _string_values(table, "response_status")
    errors = _string_values(table, "error_class")
    counts: dict[tuple[str | None, str | None, str | None], int] = {}
    for key in zip(sources, statuses, errors, strict=True):
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "source": source,
            "response_status": status,
            "error_class": error,
            "rows": rows,
        }
        for (source, status, error), rows in sorted(
            counts.items(),
            key=lambda item: tuple("" if value is None else value for value in item[0]),
        )
    ]


def _status_map(
    rows: Sequence[Any],
) -> dict[tuple[str | None, str | None, str | None], int]:
    result: dict[tuple[str | None, str | None, str | None], int] = {}
    for raw_row in rows:
        row = _mapping("status_count", raw_row)
        key = (
            row.get("source"),
            row.get("response_status"),
            row.get("error_class"),
        )
        result[key] = _integer("status_count.rows", row.get("rows"))
    return result


def _audit_raw_slice(
    slice_record: Mapping[str, Any],
    paths: Sequence[Path],
    *,
    cutoff_microseconds: int,
) -> tuple[dict[str, JsonValue], set[str]]:
    _require(bool(paths), "slice_raw_files_missing")
    tables = [pq.read_table(path, columns=list(RAW_COLUMNS)) for path in paths]
    table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]

    raw_event_ids = _string_values(table, "raw_event_id")
    idempotency_keys = _string_values(table, "idempotency_key")
    content_hashes = _string_values(table, "content_sha256")
    missing_identity_rows = sum(
        1
        for values in zip(
            raw_event_ids,
            idempotency_keys,
            content_hashes,
            strict=True,
        )
        if any(value is None or value == "" for value in values)
    )
    unique_raw_event_ids = len({value for value in raw_event_ids if value})
    unique_idempotency_keys = len(
        {value for value in idempotency_keys if value}
    )
    unique_content_sha256 = len({value for value in content_hashes if value})

    timestamps = {
        name: _timestamp_values(table, name)
        for name in (
            "event_time",
            "observed_at",
            "first_reliable_available_at",
            "available_to_strategy_at",
            "ingested_at",
        )
    }
    pit_violation_rows: set[int] = set()
    pair_metrics: list[dict[str, JsonValue]] = []
    for earlier_name, later_name in PIT_PAIRS:
        denominator = 0
        violations = 0
        for index, (earlier, later) in enumerate(
            zip(
                timestamps[earlier_name],
                timestamps[later_name],
                strict=True,
            )
        ):
            if earlier is None or later is None:
                continue
            denominator += 1
            if earlier > later:
                violations += 1
                pit_violation_rows.add(index)
        pair_metrics.append(
            {
                "earlier": earlier_name,
                "later": later_name,
                "denominator": denominator,
                "violations": violations,
            }
        )

    lags_microseconds = [
        available - reliable
        for reliable, available in zip(
            timestamps["first_reliable_available_at"],
            timestamps["available_to_strategy_at"],
            strict=True,
        )
        if reliable is not None and available is not None
    ]
    rows_after_cutoff = sum(
        1
        for value in timestamps["first_reliable_available_at"]
        if value is not None and value > cutoff_microseconds
    )
    _require(
        rows_after_cutoff == 0,
        "slice_rows_after_global_pit_cutoff",
    )
    status_counts = _status_counts(table)
    non_success_rows = sum(
        _integer("status_count.rows", row["rows"])
        for row in status_counts
        if row["response_status"] != "SUCCESS"
    )
    result: dict[str, JsonValue] = {
        "slice_id": _text("slice.slice_id", slice_record.get("slice_id")),
        "raw_rows": table.num_rows,
        "identity_complete_rows": table.num_rows - missing_identity_rows,
        "missing_identity_rows": missing_identity_rows,
        "unique_raw_event_ids": unique_raw_event_ids,
        "duplicate_raw_event_id_rows": table.num_rows - unique_raw_event_ids,
        "unique_idempotency_keys": unique_idempotency_keys,
        "duplicate_idempotency_key_rows": table.num_rows
        - unique_idempotency_keys,
        "unique_content_sha256": unique_content_sha256,
        "repeated_content_rows": table.num_rows - unique_content_sha256,
        "pit_order_violations": len(pit_violation_rows),
        "rows_after_global_pit_cutoff": rows_after_cutoff,
        "pit_pair_metrics": pair_metrics,
        "availability_lag": {
            "unit": "milliseconds",
            "denominator": len(lags_microseconds),
            "minimum": (
                _decimal_milliseconds(min(lags_microseconds), 1)
                if lags_microseconds
                else None
            ),
            "maximum": (
                _decimal_milliseconds(max(lags_microseconds), 1)
                if lags_microseconds
                else None
            ),
            "mean": _decimal_milliseconds(
                sum(lags_microseconds),
                len(lags_microseconds),
            ),
        },
        "typed_failure_rows": non_success_rows,
        "status_counts": status_counts,
    }

    expected_fields = (
        "raw_rows",
        "missing_identity_rows",
        "unique_raw_event_ids",
        "unique_idempotency_keys",
        "unique_content_sha256",
        "pit_order_violations",
    )
    for field in expected_fields:
        _require(
            result[field] == slice_record.get(field),
            f"slice_{field}_drift",
        )
    expected_statuses = _sequence(
        "slice.status_counts",
        slice_record.get("status_counts"),
    )
    _require(
        _status_map(status_counts) == _status_map(expected_statuses),
        "slice_status_counts_drift",
    )
    return result, {value for value in raw_event_ids if value}


def _audit_projection(
    slice_record: Mapping[str, Any],
    path: Path,
    raw_event_ids: set[str],
) -> dict[str, JsonValue]:
    expected_rows = _mapping(
        "slice.projection_rows",
        slice_record.get("projection_rows"),
    )
    connection = duckdb.connect(str(path), read_only=True)
    try:
        table_rows = {
            table: int(
                connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[
                    0
                ]
            )
            for table in PROJECTION_TABLES
        }
        projected_raw_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT raw_event_id FROM raw_api_events"
            ).fetchall()
        }
        projected_quote_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT raw_event_id FROM quote_attempts"
            ).fetchall()
        }
    except duckdb.Error as exc:
        raise PilotAuditContractError("projection_query_failed") from exc
    finally:
        connection.close()

    for table in PROJECTION_TABLES:
        _require(
            table_rows[table]
            == _integer(
                f"projection_rows.{table}",
                expected_rows.get(table),
            ),
            "projection_row_count_drift",
        )
    _require(
        projected_raw_ids == raw_event_ids,
        "projection_raw_lineage_mismatch",
    )
    _require(
        projected_quote_ids == raw_event_ids,
        "projection_quote_lineage_mismatch",
    )
    return {
        "slice_id": _text("slice.slice_id", slice_record.get("slice_id")),
        "table_rows": table_rows,
        "raw_event_lineage_exact": True,
        "quote_event_lineage_exact": True,
        "quote_is_fill": False,
    }


def _verify_tracked_evidence(
    repository_root: Path,
    raw_rows: Any,
) -> dict[str, JsonValue]:
    rows = _sequence("tracked_evidence", raw_rows)
    asset_ids: list[str] = []
    for raw_row in rows:
        row = _mapping("tracked_evidence_row", raw_row)
        asset_id = _text("tracked_evidence.asset_id", row.get("asset_id"))
        path = _safe_input_path(
            repository_root,
            _text("tracked_evidence.path", row.get("path")),
        )
        _require(
            hashlib.sha256(path.read_bytes()).hexdigest()
            == _sha256("tracked_evidence.sha256", row.get("sha256")),
            "tracked_evidence_sha256_mismatch",
        )
        asset_ids.append(asset_id)
    _require(len(asset_ids) == len(set(asset_ids)), "tracked_asset_id_duplicate")
    return {
        "verified_count": len(asset_ids),
        "asset_ids": sorted(asset_ids),
    }


def audit_population(
    *,
    repository_root: Path,
    population_path: str | Path,
    expected_population_sha256: str = EXPECTED_POPULATION_SHA256,
) -> dict[str, JsonValue]:
    """Audit the exact frozen local evidence population without side effects."""

    started = time.monotonic()
    root = repository_root.resolve()
    fixture, fixture_sha256 = _load_population(
        root,
        population_path,
        expected_sha256=expected_population_sha256,
    )
    population = _mapping("population", fixture.get("population"))
    caps = _mapping("caps", fixture.get("caps"))
    cutoff = _text(
        "population.global_pit_cutoff",
        population.get("global_pit_cutoff"),
    )
    try:
        cutoff_timestamp = datetime.fromisoformat(
            cutoff.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise PilotAuditContractError("global_pit_cutoff_invalid") from exc
    _require(
        cutoff_timestamp.tzinfo is not None,
        "global_pit_cutoff_must_be_aware",
    )
    cutoff_delta = cutoff_timestamp.astimezone(UTC) - datetime(
        1970,
        1,
        1,
        tzinfo=UTC,
    )
    cutoff_microseconds = (
        cutoff_delta.days * 86_400_000_000
        + cutoff_delta.seconds * 1_000_000
        + cutoff_delta.microseconds
    )
    data_rows = _sequence("data_files", fixture.get("data_files"))
    _require(
        len(data_rows)
        == _integer("caps.data_files_exact", caps.get("data_files_exact")),
        "data_file_count_drift",
    )

    verified_files: list[tuple[Mapping[str, Any], Path]] = [
        _verify_file_record(root, raw_row) for raw_row in data_rows
    ]
    actual_input_bytes = sum(path.stat().st_size for _, path in verified_files)
    _require(
        actual_input_bytes
        == _integer("caps.input_bytes_exact", caps.get("input_bytes_exact")),
        "input_bytes_total_drift",
    )
    _require(
        actual_input_bytes == population.get("data_bytes"),
        "population_data_bytes_drift",
    )

    raw_paths_by_slice: dict[str, list[Path]] = {}
    projection_path_by_slice: dict[str, Path] = {}
    manifest_rows = 0
    for record, path in verified_files:
        slice_id = _text("data_file.slice_id", record.get("slice_id"))
        if record["kind"] == "RAW_PARQUET":
            raw_paths_by_slice.setdefault(slice_id, []).append(path)
            manifest_rows += _integer("data_file.rows", record.get("rows"))
        else:
            _require(
                slice_id not in projection_path_by_slice,
                "multiple_projection_files_per_slice",
            )
            projection_path_by_slice[slice_id] = path
    _require(
        manifest_rows
        == _integer("caps.raw_rows_exact", caps.get("raw_rows_exact")),
        "raw_row_manifest_total_drift",
    )
    _require(
        manifest_rows == population.get("raw_rows"),
        "population_raw_rows_drift",
    )

    slice_rows = _sequence("slices", fixture.get("slices"))
    slice_ids = [
        _text("slice.slice_id", _mapping("slice", row).get("slice_id"))
        for row in slice_rows
    ]
    _require(len(slice_ids) == len(set(slice_ids)), "slice_id_duplicate")
    _require(
        set(raw_paths_by_slice) == set(slice_ids),
        "slice_raw_file_mapping_drift",
    )

    raw_metrics: list[dict[str, JsonValue]] = []
    raw_ids_by_slice: dict[str, set[str]] = {}
    all_raw_ids: set[str] = set()
    all_idempotency_keys: set[str] = set()
    all_content_hashes: set[str] = set()
    for raw_slice in slice_rows:
        slice_record = _mapping("slice", raw_slice)
        slice_id = _text("slice.slice_id", slice_record.get("slice_id"))
        metrics, raw_ids = _audit_raw_slice(
            slice_record,
            raw_paths_by_slice[slice_id],
            cutoff_microseconds=cutoff_microseconds,
        )
        raw_metrics.append(metrics)
        raw_ids_by_slice[slice_id] = raw_ids
        all_raw_ids.update(raw_ids)
        for path in raw_paths_by_slice[slice_id]:
            table = pq.read_table(
                path,
                columns=["idempotency_key", "content_sha256"],
            )
            all_idempotency_keys.update(
                value
                for value in _string_values(table, "idempotency_key")
                if value
            )
            all_content_hashes.update(
                value
                for value in _string_values(table, "content_sha256")
                if value
            )

    _require(
        len(all_raw_ids) == population.get("unique_raw_event_ids"),
        "population_unique_raw_event_ids_drift",
    )
    _require(
        len(all_idempotency_keys) == population.get("unique_idempotency_keys"),
        "population_unique_idempotency_keys_drift",
    )
    _require(
        len(all_content_hashes) == population.get("unique_content_sha256"),
        "population_unique_content_sha256_drift",
    )

    projection_metrics: list[dict[str, JsonValue]] = []
    slices_by_id = {
        _text("slice.slice_id", row.get("slice_id")): row
        for row in (_mapping("slice", value) for value in slice_rows)
    }
    for slice_id in sorted(projection_path_by_slice):
        projection_metrics.append(
            _audit_projection(
                slices_by_id[slice_id],
                projection_path_by_slice[slice_id],
                raw_ids_by_slice[slice_id],
            )
        )

    tracked = _verify_tracked_evidence(
        root,
        fixture.get("tracked_evidence"),
    )
    input_manifest = [
        {
            "asset_id": record["asset_id"],
            "kind": record["kind"],
            "sha256": record["sha256"],
            "bytes": record["bytes"],
            "rows": record["rows"],
        }
        for record, _ in verified_files
    ]
    result: dict[str, JsonValue] = {
        "schema": AUDIT_RESULT_SCHEMA,
        "schema_version": AUDIT_RESULT_SCHEMA_VERSION,
        "contract_id": EXPECTED_CONTRACT_ID,
        "population_id": EXPECTED_POPULATION_ID,
        "population_version": fixture.get("population_version"),
        "population_fixture_sha256": fixture_sha256,
        "status": "PASS_FROZEN_BASELINE_REPRODUCED",
        "accepted_claim": "BOUNDED_HISTORICAL_EVIDENCE_INTEGRITY_REPRODUCED",
        "global_pit_cutoff": cutoff,
        "primary_slice_id": population.get("primary_slice_id"),
        "primary_consumer": population.get("primary_consumer"),
        "input_manifest_sha256": hashlib.sha256(
            _canonical_json_bytes({"data_files": input_manifest})
        ).hexdigest(),
        "totals": {
            "data_files": len(verified_files),
            "input_bytes": actual_input_bytes,
            "raw_rows": manifest_rows,
            "unique_raw_event_ids": len(all_raw_ids),
            "unique_idempotency_keys": len(all_idempotency_keys),
            "unique_content_sha256": len(all_content_hashes),
        },
        "slice_metrics": raw_metrics,
        "projection_reconciliation": projection_metrics,
        "tracked_evidence": tracked,
        "decision_boundary": {
            "valid_for": [
                "BOUNDED_RAW_EVIDENCE_INTEGRITY",
                "TYPED_FAILURE_PRESERVATION",
                "TASK10_RAW_PROJECTION_RECONCILIATION",
            ],
            "not_valid_for": [
                "SUSTAINED_24_48H_OPERATION",
                "PROVIDER_RELIABILITY_RATE",
                "PROVIDER_PURCHASE_REQUIREMENT",
                "FILL_OR_REALIZED_EXECUTION",
                "NET_RETURN_OR_ALPHA",
            ],
        },
        "side_effects": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "credential_use": 0,
            "raw_data_writes": 0,
            "cash_spend_usd_cents": 0,
            "provider_credits": 0,
            "wallet_signer_transaction_actions": 0,
        },
    }
    result["result_sha256"] = hashlib.sha256(
        _canonical_json_bytes(result)
    ).hexdigest()
    encoded = _canonical_json_bytes(result)
    _require(
        len(encoded)
        <= _integer(
            "caps.future_sanitized_output_bytes_max",
            caps.get("future_sanitized_output_bytes_max"),
        ),
        "sanitized_output_cap_exceeded",
    )
    _require(
        time.monotonic() - started
        <= _integer(
            "caps.future_local_wall_seconds_max",
            caps.get("future_local_wall_seconds_max"),
        ),
        "audit_wall_time_cap_exceeded",
    )
    return result
