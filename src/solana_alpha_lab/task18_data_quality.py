"""Deterministic offline data-quality audit for the TASK-17A quote evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


class Task18ContractError(RuntimeError):
    """The frozen TASK-18 contract itself is invalid or drifted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_root_not_object")
    return value


def _load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"jsonl_row_not_object:{line_number}")
        rows.append(value)
    return rows


def _parse_utc(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name}_not_utc_text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError(f"{name}_timezone_missing")
    return parsed


def _contained_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ValueError("path_not_text")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("path_outside_repository_root")
    return candidate


def _check(
    checks: list[JsonObject],
    check_id: str,
    failures: list[str],
    metrics: JsonObject,
    *,
    limitations: list[str] | None = None,
) -> None:
    status = "FAIL" if failures else "PASS"
    if not failures and limitations:
        status = "LIMITATION"
    row: JsonObject = {
        "check_id": check_id,
        "status": status,
        "failures": sorted(set(failures)),
        "metrics": metrics,
    }
    if limitations:
        row["limitations"] = sorted(set(limitations))
    checks.append(row)


def select_verdict(
    *,
    availability_failures: list[str],
    hard_failures: list[str],
    limitations: list[str],
) -> str:
    """Apply the frozen TASK-18 verdict precedence."""

    if availability_failures:
        return "EVIDENCE_UNAVAILABLE"
    if hard_failures:
        return "NOT_FIT"
    if limitations:
        return "FIT_WITH_LIMITATIONS"
    return "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND"


def _base_receipt(
    contract: JsonObject,
    contract_path: Path,
) -> JsonObject:
    return {
        "schema": "smial.task18_narrow_data_quality_audit.v1",
        "schema_version": "1.0",
        "task": "TASK-18",
        "atom": "T18-A3_DETERMINISTIC_OFFLINE_QUALITY_AUDIT_V1",
        "as_of": contract["as_of"],
        "contract_id": contract["contract_id"],
        "contract_sha256": _sha256(contract_path),
        "estimand": contract["estimand"]["claim_scope"],
        "checks": [],
        "limitations": [],
        "claims": {
            "narrow_quote_only_data_quality": False,
            "cross_token_generalization": False,
            "provider_reliability": False,
            "fillable": False,
            "realized_vwap": False,
            "net_return": False,
            "signal_or_strategy": False,
            "alpha": False,
            "production_readiness": False,
        },
        "authority": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "collector_executions": 0,
            "raw_data_writes": 0,
            "credential_use": 0,
            "cash_spend_usd_cents": 0,
            "provider_credits": 0,
            "wallet_signer_transaction_actions": 0,
            "dependency_changes": 0,
        },
    }


def audit_narrow_data_quality(
    *,
    repository_root: Path,
    contract_path: Path,
) -> JsonObject:
    """Audit frozen raw bytes without changing them or using the network."""

    contract = _load_json(contract_path)
    if contract.get("contract_id") != "CONTRACT-T18-NARROW-DATA-QUALITY-001":
        raise Task18ContractError("contract_id_drift")
    if contract.get("status") != "FROZEN_OFFLINE_CONTRACT":
        raise Task18ContractError("contract_status_drift")

    receipt = _base_receipt(contract, contract_path)
    checks: list[JsonObject] = receipt["checks"]
    inventory = contract["raw_inventory"]
    inventory_rows = inventory["files"]

    availability_failures: list[str] = []
    resolved: dict[str, Path] = {}
    for row in inventory_rows:
        relative = row.get("path")
        try:
            path = _contained_path(repository_root, relative)
        except ValueError as exc:
            availability_failures.append(f"PATH_INVALID:{relative}:{exc}")
            continue
        resolved[relative] = path
        if not path.is_file():
            availability_failures.append(f"FILE_MISSING:{relative}")
            continue
        try:
            actual_size = path.stat().st_size
            actual_sha256 = _sha256(path)
        except OSError:
            availability_failures.append(f"FILE_UNREADABLE:{relative}")
            continue
        if actual_size != row.get("bytes"):
            availability_failures.append(f"SIZE_DRIFT:{relative}")
        if actual_sha256 != row.get("sha256"):
            availability_failures.append(f"SHA256_DRIFT:{relative}")

    tracked_input_hashes: dict[str, str] = {}
    for row in contract["tracked_inputs"]:
        relative = row["path"]
        try:
            path = _contained_path(repository_root, relative)
        except ValueError as exc:
            availability_failures.append(
                f"TRACKED_PATH_INVALID:{relative}:{exc}"
            )
            continue
        if not path.is_file():
            availability_failures.append(f"TRACKED_INPUT_MISSING:{relative}")
            continue
        actual = _sha256(path)
        tracked_input_hashes[relative] = actual
        if actual != row["sha256"]:
            availability_failures.append(f"TRACKED_INPUT_DRIFT:{relative}")

    parsed: dict[str, JsonObject | list[JsonObject]] = {}
    if not availability_failures:
        for row in inventory_rows:
            relative = row["path"]
            try:
                if row["kind"] == "RAW_EVENTS_JSONL":
                    value: JsonObject | list[JsonObject] = _load_jsonl(
                        resolved[relative]
                    )
                else:
                    value = _load_json(resolved[relative])
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                availability_failures.append(f"PARSE_FAILED:{relative}")
                continue
            parsed[relative] = value
            actual_rows = len(value) if isinstance(value, list) else 1
            if actual_rows != row["rows"]:
                availability_failures.append(f"ROW_COUNT_DRIFT:{relative}")

    _check(
        checks,
        "INVENTORY_INTEGRITY",
        availability_failures,
        {
            "expected_files": inventory["file_count"],
            "resolved_files": sum(
                1 for path in resolved.values() if path.is_file()
            ),
            "expected_stored_bytes": inventory["stored_bytes"],
            "expected_jsonl_attempt_rows": inventory["jsonl_attempt_rows"],
            "tracked_inputs_verified": len(tracked_input_hashes),
        },
    )

    if availability_failures:
        receipt["verdict"] = select_verdict(
            availability_failures=availability_failures,
            hard_failures=[],
            limitations=[],
        )
        receipt["coverage"] = {
            "expected_files": inventory["file_count"],
            "expected_attempts": inventory["jsonl_attempt_rows"],
            "audited_attempts": 0,
        }
        return receipt

    hard_failures: list[str] = []
    rows_by_window: dict[str, list[JsonObject]] = {}
    manifest_by_window: dict[str, JsonObject] = {}
    receipt_by_window: dict[str, JsonObject] = {}
    inventory_by_window: dict[str, dict[str, JsonObject]] = defaultdict(dict)
    for row in inventory_rows:
        window_id = row["window_id"]
        inventory_by_window[window_id][row["kind"]] = row
        value = parsed[row["path"]]
        if row["kind"] == "RAW_EVENTS_JSONL":
            if not isinstance(value, list):
                raise Task18ContractError("parsed_jsonl_not_list")
            rows_by_window[window_id] = value
        elif row["kind"] == "MANIFEST":
            if not isinstance(value, dict):
                raise Task18ContractError("parsed_manifest_not_object")
            manifest_by_window[window_id] = value
        elif row["kind"] == "RECEIPT":
            if not isinstance(value, dict):
                raise Task18ContractError("parsed_receipt_not_object")
            receipt_by_window[window_id] = value

    completeness_failures: list[str] = []
    expected_windows = {
        *contract["estimand"]["accepted_windows"],
        *contract["estimand"]["excluded_retained_windows"],
    }
    actual_windows = set(rows_by_window)
    if actual_windows != expected_windows:
        completeness_failures.append("WINDOW_MEMBERSHIP_DRIFT")

    total_rows = sum(len(rows) for rows in rows_by_window.values())
    for window_id in sorted(expected_windows):
        rows = rows_by_window.get(window_id, [])
        if len(rows) != 8:
            completeness_failures.append(
                f"ATTEMPT_COUNT_DRIFT:{window_id}"
            )
        ordinals = sorted(row.get("call_ordinal") for row in rows)
        if ordinals != list(range(1, 9)):
            completeness_failures.append(f"CALL_ORDINAL_DRIFT:{window_id}")
        if set(inventory_by_window.get(window_id, {})) != {
            "MANIFEST",
            "RAW_EVENTS_JSONL",
            "RECEIPT",
        }:
            completeness_failures.append(
                f"WINDOW_FILE_SET_DRIFT:{window_id}"
            )

    accepted_rows = sum(
        len(rows_by_window.get(window_id, []))
        for window_id in contract["estimand"]["accepted_windows"]
    )
    excluded_rows = sum(
        len(rows_by_window.get(window_id, []))
        for window_id in contract["estimand"]["excluded_retained_windows"]
    )
    completeness = contract["quality_dimensions"]["attempt_completeness"]
    if accepted_rows != completeness["accepted_attempts"]:
        completeness_failures.append("ACCEPTED_ATTEMPT_COUNT_DRIFT")
    if excluded_rows != completeness["excluded_retained_attempts"]:
        completeness_failures.append("EXCLUDED_ATTEMPT_COUNT_DRIFT")
    if total_rows != completeness["total_attempts"]:
        completeness_failures.append("TOTAL_ATTEMPT_COUNT_DRIFT")

    hard_failures.extend(completeness_failures)
    _check(
        checks,
        "ATTEMPT_COMPLETENESS",
        completeness_failures,
        {
            "windows": len(actual_windows),
            "accepted_attempts": accepted_rows,
            "excluded_retained_attempts": excluded_rows,
            "total_attempts": total_rows,
        },
    )

    identity_failures: list[str] = []
    pit_failures: list[str] = []
    provider_failures: list[str] = []
    revision_failures: list[str] = []
    composite_ids: set[tuple[object, ...]] = set()
    quote_attempt_ids: set[str] = set()
    raw_event_ids: set[str] = set()
    content_hashes: set[str] = set()
    latency_mismatch_count = 0
    pit_violation_count = 0
    request_gaps: list[float] = []
    trigger_times: dict[str, datetime] = {}
    linkage_failures: list[str] = []

    identity_fields = contract["quality_dimensions"]["stable_identity"][
        "composite_key"
    ]
    expected_provider = contract["quality_dimensions"]["provider_and_schema"]
    ordered_fields = contract["quality_dimensions"]["point_in_time"][
        "ordered_fields"
    ]
    latency_tolerance = contract["quality_dimensions"]["point_in_time"][
        "latency_tolerance_ms"
    ]
    expected_revision = contract["quality_dimensions"][
        "revision_and_overwrite"
    ]["expected_revision_number"]

    for window_id in sorted(expected_windows):
        manifest = manifest_by_window.get(window_id, {})
        window_receipt = receipt_by_window.get(window_id, {})
        rows = rows_by_window.get(window_id, [])
        raw_inventory_row = inventory_by_window[window_id].get(
            "RAW_EVENTS_JSONL",
            {},
        )
        manifest_inventory_row = inventory_by_window[window_id].get(
            "MANIFEST",
            {},
        )

        if manifest.get("window_id") != window_id:
            linkage_failures.append(f"MANIFEST_WINDOW_DRIFT:{window_id}")
        if window_receipt.get("window_id") != window_id:
            linkage_failures.append(f"RECEIPT_WINDOW_DRIFT:{window_id}")
        if manifest.get("triggered_at") != window_receipt.get("triggered_at"):
            linkage_failures.append(f"TRIGGER_IDENTITY_DRIFT:{window_id}")
        try:
            trigger_times[window_id] = _parse_utc(
                window_receipt.get("triggered_at"),
                "triggered_at",
            )
        except (TypeError, ValueError):
            linkage_failures.append(f"TRIGGER_TIME_INVALID:{window_id}")

        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list) or len(manifest_files) != 1:
            linkage_failures.append(f"MANIFEST_FILE_SET_INVALID:{window_id}")
        else:
            manifest_file = manifest_files[0]
            if manifest_file.get("logical_path") != "raw_events.jsonl":
                linkage_failures.append(
                    f"MANIFEST_LOGICAL_PATH_DRIFT:{window_id}"
                )
            if manifest_file.get("sha256") != raw_inventory_row.get("sha256"):
                linkage_failures.append(
                    f"MANIFEST_RAW_HASH_DRIFT:{window_id}"
                )
            if manifest_file.get("bytes") != raw_inventory_row.get("bytes"):
                linkage_failures.append(
                    f"MANIFEST_RAW_SIZE_DRIFT:{window_id}"
                )
        source_contract_sha256 = contract["tracked_inputs"][1]["sha256"]
        if manifest.get("contract_sha256") != source_contract_sha256:
            linkage_failures.append(
                f"MANIFEST_CONTRACT_HASH_DRIFT:{window_id}"
            )
        if (
            window_receipt.get("raw_events_sha256")
            != raw_inventory_row.get("sha256")
        ):
            linkage_failures.append(f"RECEIPT_RAW_HASH_DRIFT:{window_id}")
        if (
            window_receipt.get("manifest_sha256")
            != manifest_inventory_row.get("sha256")
        ):
            linkage_failures.append(
                f"RECEIPT_MANIFEST_HASH_DRIFT:{window_id}"
            )
        if window_receipt.get("provider_calls") != 8:
            linkage_failures.append(f"RECEIPT_CALL_COUNT_DRIFT:{window_id}")
        if window_receipt.get("terminal_counts") != {"QUOTE_AVAILABLE": 8}:
            linkage_failures.append(f"TERMINAL_COUNTS_DRIFT:{window_id}")
        if window_receipt.get("status") != "COMPLETE":
            linkage_failures.append(f"RECEIPT_STATUS_DRIFT:{window_id}")
        if window_receipt.get("stop_reason") is not None:
            linkage_failures.append(f"RECEIPT_STOP_REASON_PRESENT:{window_id}")
        for field in (
            "api_keys_used",
            "accounts_used",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "retries",
        ):
            if window_receipt.get(field) != 0:
                linkage_failures.append(
                    f"NONZERO_{field.upper()}:{window_id}"
                )

        previous_request: datetime | None = None
        for row_number, row in enumerate(rows, start=1):
            prefix = f"{window_id}:{row_number}"
            composite = tuple(row.get(field) for field in identity_fields)
            if any(value in (None, "") for value in composite):
                identity_failures.append(f"IDENTITY_FIELD_MISSING:{prefix}")
            if composite in composite_ids:
                identity_failures.append(f"COMPOSITE_ID_DUPLICATE:{prefix}")
            composite_ids.add(composite)

            quote = row.get("quote_attempt")
            raw = row.get("raw_event")
            if not isinstance(quote, dict) or not isinstance(raw, dict):
                identity_failures.append(f"EMBEDDED_RECORD_MISSING:{prefix}")
                continue

            quote_id = quote.get("quote_attempt_id")
            raw_id = raw.get("raw_event_id")
            if not isinstance(quote_id, str) or quote_id in quote_attempt_ids:
                identity_failures.append(f"QUOTE_ATTEMPT_ID_INVALID:{prefix}")
            else:
                quote_attempt_ids.add(quote_id)
            if not isinstance(raw_id, str) or raw_id in raw_event_ids:
                identity_failures.append(f"RAW_EVENT_ID_INVALID:{prefix}")
            else:
                raw_event_ids.add(raw_id)
            if quote.get("raw_event_id") != raw_id:
                identity_failures.append(f"RAW_EVENT_LINK_DRIFT:{prefix}")
            if (
                quote.get("request_hash") != row.get("request_hash")
                or raw.get("request_hash") != row.get("request_hash")
            ):
                identity_failures.append(
                    f"REQUEST_HASH_LINK_DRIFT:{prefix}"
                )
            if quote.get("idempotency_key") != row.get("idempotency_key"):
                identity_failures.append(
                    f"IDEMPOTENCY_KEY_LINK_DRIFT:{prefix}"
                )
            if raw_id != f"raw-{raw.get('idempotency_key')}":
                identity_failures.append(
                    f"RAW_IDEMPOTENCY_LINK_DRIFT:{prefix}"
                )

            content_hash = row.get("raw_content_sha256")
            if (
                content_hash != raw.get("content_sha256")
                or content_hash != quote.get("response_content_sha256")
            ):
                identity_failures.append(f"CONTENT_HASH_LINK_DRIFT:{prefix}")
            if isinstance(content_hash, str):
                content_hashes.add(content_hash)

            expected_top = {
                "schema": expected_provider["envelope_schema"],
                "schema_version": expected_provider["schema_version"],
                "provider": expected_provider["provider"],
                "provider_version": expected_provider["provider_version"],
                "endpoint_version": expected_provider["endpoint_version"],
                "window_id": window_id,
                "terminal_class": "QUOTE_AVAILABLE",
                "response_status": "SUCCESS",
                "error_class": None,
            }
            for field, expected in expected_top.items():
                if row.get(field) != expected:
                    provider_failures.append(f"{field.upper()}_DRIFT:{prefix}")
            nested_expected = {
                "quote_provider": (
                    quote.get("provider"),
                    expected_provider["provider"],
                ),
                "quote_provider_version": (
                    quote.get("provider_version"),
                    expected_provider["provider_version"],
                ),
                "quote_status": (
                    quote.get("status"),
                    "QUOTE_AVAILABLE",
                ),
                "raw_source": (
                    raw.get("source"),
                    expected_provider["provider"],
                ),
                "raw_provider_version": (
                    raw.get("provider_version"),
                    expected_provider["provider_version"],
                ),
                "raw_response_status": (
                    raw.get("response_status"),
                    "SUCCESS",
                ),
            }
            for field, (actual, expected) in nested_expected.items():
                if actual != expected:
                    provider_failures.append(
                        f"{field.upper()}_DRIFT:{prefix}"
                    )
            if (
                not isinstance(row.get("route_id"), str)
                or not isinstance(row.get("route_count"), int)
                or row["route_count"] < 1
                or not isinstance(row.get("context_slot"), int)
            ):
                provider_failures.append(f"ROUTE_IDENTITY_INVALID:{prefix}")

            try:
                times = [
                    _parse_utc(row.get(field), field)
                    for field in ordered_fields
                ]
            except (TypeError, ValueError):
                pit_failures.append(f"PIT_TIMESTAMP_INVALID:{prefix}")
                continue
            if times != sorted(times):
                pit_failures.append(f"PIT_ORDER_VIOLATION:{prefix}")
                pit_violation_count += 1
            latency = (times[1] - times[0]).total_seconds() * 1_000
            recorded_latency = row.get("latency_ms")
            quote_latency = quote.get("provider_latency_ms")
            if (
                not isinstance(recorded_latency, (int, float))
                or abs(latency - recorded_latency) > latency_tolerance
                or not isinstance(quote_latency, (int, float))
                or abs(latency - quote_latency) > latency_tolerance
            ):
                pit_failures.append(f"LATENCY_MISMATCH:{prefix}")
                latency_mismatch_count += 1
            for field in ordered_fields:
                if quote.get(field) != row.get(field):
                    pit_failures.append(
                        f"QUOTE_{field.upper()}_DRIFT:{prefix}"
                    )
            raw_times = (
                "observed_at",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            )
            try:
                parsed_raw_times = [
                    _parse_utc(raw.get(field), f"raw_{field}")
                    for field in raw_times
                ]
            except (TypeError, ValueError):
                pit_failures.append(f"RAW_PIT_TIMESTAMP_INVALID:{prefix}")
            else:
                if parsed_raw_times != sorted(parsed_raw_times):
                    pit_failures.append(f"RAW_PIT_ORDER_VIOLATION:{prefix}")
                event_time = raw.get("event_time")
                if event_time is not None:
                    try:
                        parsed_event_time = _parse_utc(
                            event_time,
                            "raw_event_time",
                        )
                    except (TypeError, ValueError):
                        pit_failures.append(
                            f"RAW_EVENT_TIME_INVALID:{prefix}"
                        )
                    else:
                        if parsed_event_time > parsed_raw_times[0]:
                            pit_failures.append(
                                f"RAW_EVENT_TIME_AFTER_OBSERVED:{prefix}"
                            )

            if previous_request is not None:
                request_gaps.append(
                    (times[0] - previous_request).total_seconds()
                )
            previous_request = times[0]

            for embedded_name, embedded in (("QUOTE", quote), ("RAW", raw)):
                if embedded.get("revision_number") != expected_revision:
                    revision_failures.append(
                        f"{embedded_name}_REVISION_NUMBER_DRIFT:{prefix}"
                    )
                if embedded.get("revision_of") is not None:
                    revision_failures.append(
                        f"{embedded_name}_REVISION_OF_DRIFT:{prefix}"
                    )

    hard_failures.extend(linkage_failures)
    _check(
        checks,
        "MANIFEST_RECEIPT_LINKAGE",
        linkage_failures,
        {
            "windows_reconciled": len(expected_windows),
            "manifests": len(manifest_by_window),
            "receipts": len(receipt_by_window),
            "raw_jsonl_files": len(rows_by_window),
            "nonzero_external_authority_receipts": sum(
                1
                for window_receipt in receipt_by_window.values()
                if any(
                    window_receipt.get(field) != 0
                    for field in (
                        "api_keys_used",
                        "accounts_used",
                        "cash_spend_usd_cents",
                        "wallet_signer_transaction_actions",
                        "retries",
                    )
                )
            ),
        },
    )

    duplicate_content_hashes = total_rows - len(content_hashes)
    hard_failures.extend(identity_failures)
    _check(
        checks,
        "STABLE_IDENTITY",
        identity_failures,
        {
            "unique_composite_identities": len(composite_ids),
            "unique_quote_attempt_ids": len(quote_attempt_ids),
            "unique_raw_event_ids": len(raw_event_ids),
            "unique_content_hashes": len(content_hashes),
            "duplicate_content_hashes": duplicate_content_hashes,
        },
    )

    pacing_floor = contract["quality_dimensions"]["temporal_membership"][
        "request_pacing_floor_seconds"
    ]
    pacing_failures = [
        f"REQUEST_PACING_BELOW_FLOOR:{value:.6f}"
        for value in request_gaps
        if value < pacing_floor
    ]
    pit_failures.extend(pacing_failures)
    hard_failures.extend(pit_failures)
    _check(
        checks,
        "POINT_IN_TIME_AND_LATENCY",
        pit_failures,
        {
            "pit_violations": pit_violation_count,
            "latency_mismatches": latency_mismatch_count,
            "request_gap_count": len(request_gaps),
            "minimum_request_gap_seconds": (
                round(min(request_gaps), 6) if request_gaps else None
            ),
        },
    )

    temporal_failures: list[str] = []
    accepted_windows = contract["estimand"]["accepted_windows"]
    accepted_trigger_gaps: list[float] = []
    for left, right in zip(accepted_windows, accepted_windows[1:]):
        if left not in trigger_times or right not in trigger_times:
            temporal_failures.append(f"TRIGGER_TIME_UNAVAILABLE:{left}:{right}")
            continue
        gap = (trigger_times[right] - trigger_times[left]).total_seconds()
        accepted_trigger_gaps.append(gap)
        if gap < 1_800:
            temporal_failures.append(
                f"ACCEPTED_TRIGGER_SEPARATION_BELOW_FLOOR:{left}:{right}"
            )
    excluded_window = contract["quality_dimensions"]["temporal_membership"][
        "excluded_window_id"
    ]
    if excluded_window not in contract["estimand"]["excluded_retained_windows"]:
        temporal_failures.append("EXCLUDED_WINDOW_MEMBERSHIP_DRIFT")
    hard_failures.extend(temporal_failures)
    _check(
        checks,
        "TEMPORAL_MEMBERSHIP",
        temporal_failures,
        {
            "accepted_window_ids": accepted_windows,
            "excluded_retained_window_ids": contract["estimand"][
                "excluded_retained_windows"
            ],
            "accepted_trigger_separation_seconds": [
                round(value, 6) for value in accepted_trigger_gaps
            ],
            "excluded_trigger_shortfall_seconds": contract[
                "quality_dimensions"
            ]["temporal_membership"]["excluded_trigger_shortfall_seconds"],
            "post_hoc_reclassification": False,
        },
    )

    hard_failures.extend(provider_failures)
    _check(
        checks,
        "PROVIDER_SCHEMA_AND_TYPED_OUTCOMES",
        provider_failures,
        {
            "provider": expected_provider["provider"],
            "provider_version": expected_provider["provider_version"],
            "terminal_counts": dict(
                sorted(
                    Counter(
                        row.get("terminal_class")
                        for rows in rows_by_window.values()
                        for row in rows
                    ).items()
                )
            ),
            "route_count_min": min(
                row["route_count"]
                for rows in rows_by_window.values()
                for row in rows
            ),
            "route_count_max": max(
                row["route_count"]
                for rows in rows_by_window.values()
                for row in rows
            ),
        },
    )

    byte_failures: list[str] = []
    total_received = 0
    total_stored = 0
    source_contract_path = repository_root / contract["tracked_inputs"][1][
        "path"
    ]
    source_contract = _load_json(source_contract_path)
    per_window_received_cap = source_contract["caps"][
        "received_response_bytes_per_window_max"
    ]
    per_window_stored_cap = source_contract["caps"][
        "durable_raw_bytes_per_window_max"
    ]
    for window_id in sorted(expected_windows):
        window_receipt = receipt_by_window[window_id]
        received = window_receipt.get("received_bytes")
        stored = sum(
            inventory_by_window[window_id][kind]["bytes"]
            for kind in ("MANIFEST", "RAW_EVENTS_JSONL", "RECEIPT")
        )
        if not isinstance(received, int) or received < 0:
            byte_failures.append(f"RECEIVED_BYTES_INVALID:{window_id}")
        else:
            total_received += received
            if received > per_window_received_cap:
                byte_failures.append(f"RECEIVED_BYTES_CAP_EXCEEDED:{window_id}")
        total_stored += stored
        if stored > per_window_stored_cap:
            byte_failures.append(f"STORED_BYTES_CAP_EXCEEDED:{window_id}")
    if total_stored != inventory["stored_bytes"]:
        byte_failures.append("TOTAL_STORED_BYTES_DRIFT")
    hard_failures.extend(byte_failures)
    _check(
        checks,
        "BYTES_RECEIPTS_AND_CAPS",
        byte_failures,
        {
            "total_received_bytes": total_received,
            "total_stored_bytes": total_stored,
            "provider_calls_reconciled": total_rows,
            "per_window_received_cap": per_window_received_cap,
            "per_window_stored_cap": per_window_stored_cap,
        },
    )

    hard_failures.extend(revision_failures)
    _check(
        checks,
        "REVISION_AND_OVERWRITE",
        revision_failures,
        {
            "expected_revision_number": expected_revision,
            "expected_revision_of": None,
            "observed_revision_conflicts": len(revision_failures),
            "current_hashes_match": True,
            "overwrite_prevention_proven": False,
        },
    )

    limitations: list[str] = []
    retention = contract["quality_dimensions"]["retention_and_restore"]
    if not retention["backup_inventory_observed"]:
        limitations.append("BACKUP_INVENTORY_NOT_OBSERVED")
    if not retention["restore_test_observed"]:
        limitations.append("RESTORE_TEST_NOT_OBSERVED")
    limitations.append("OVERWRITE_PREVENTION_NOT_PROVEN_BY_CURRENT_HASHES")
    _check(
        checks,
        "RETENTION_AND_RESTORE",
        [],
        {
            "current_local_availability": True,
            "backup_inventory_observed": retention[
                "backup_inventory_observed"
            ],
            "restore_test_observed": retention["restore_test_observed"],
            "raw_mutation_performed": False,
        },
        limitations=limitations,
    )

    source_audit = _load_json(
        repository_root / contract["tracked_inputs"][0]["path"]
    )
    audit_reconciliation_failures: list[str] = []
    source_windows = {
        row["window_id"]: row for row in source_audit.get("windows", [])
    }
    source_excluded = source_audit.get("repair", {}).get(
        "excluded_but_retained_window",
        {},
    )
    for window_id in accepted_windows:
        source = source_windows.get(window_id)
        if source is None:
            audit_reconciliation_failures.append(
                f"TRACKED_AUDIT_WINDOW_MISSING:{window_id}"
            )
            continue
        physical = inventory_by_window[window_id]
        for field, kind in (
            ("manifest_sha256", "MANIFEST"),
            ("raw_events_sha256", "RAW_EVENTS_JSONL"),
            ("receipt_sha256", "RECEIPT"),
        ):
            if source.get(field) != physical[kind]["sha256"]:
                audit_reconciliation_failures.append(
                    f"TRACKED_AUDIT_{field.upper()}_DRIFT:{window_id}"
                )
        current_receipt = receipt_by_window[window_id]
        current_stored = sum(
            physical[kind]["bytes"]
            for kind in ("MANIFEST", "RAW_EVENTS_JSONL", "RECEIPT")
        )
        if source.get("provider_calls") != current_receipt.get(
            "provider_calls"
        ):
            audit_reconciliation_failures.append(
                f"TRACKED_AUDIT_CALL_COUNT_DRIFT:{window_id}"
            )
        if source.get("received_bytes") != current_receipt.get(
            "received_bytes"
        ):
            audit_reconciliation_failures.append(
                f"TRACKED_AUDIT_RECEIVED_BYTES_DRIFT:{window_id}"
            )
        if source.get("stored_bytes") != current_stored:
            audit_reconciliation_failures.append(
                f"TRACKED_AUDIT_STORED_BYTES_DRIFT:{window_id}"
            )
    if source_excluded.get("window_id") != excluded_window:
        audit_reconciliation_failures.append(
            "TRACKED_AUDIT_EXCLUDED_WINDOW_DRIFT"
        )
    else:
        physical = inventory_by_window[excluded_window]
        for field, kind in (
            ("manifest_sha256", "MANIFEST"),
            ("raw_events_sha256", "RAW_EVENTS_JSONL"),
            ("receipt_sha256", "RECEIPT"),
        ):
            if source_excluded.get(field) != physical[kind]["sha256"]:
                audit_reconciliation_failures.append(
                    f"TRACKED_AUDIT_EXCLUDED_{field.upper()}_DRIFT"
                )
        if source_excluded.get("provider_calls") != receipt_by_window[
            excluded_window
        ].get("provider_calls"):
            audit_reconciliation_failures.append(
                "TRACKED_AUDIT_EXCLUDED_CALL_COUNT_DRIFT"
            )
    hard_failures.extend(audit_reconciliation_failures)
    _check(
        checks,
        "TRACKED_AUDIT_RECONCILIATION",
        audit_reconciliation_failures,
        {
            "tracked_audit_sha256": tracked_input_hashes[
                contract["tracked_inputs"][0]["path"]
            ],
            "accepted_windows_reconciled": len(source_windows),
            "excluded_window_reconciled": (
                source_excluded.get("window_id") == excluded_window
            ),
        },
    )

    receipt["limitations"] = sorted(set(limitations))
    receipt["verdict"] = select_verdict(
        availability_failures=[],
        hard_failures=hard_failures,
        limitations=limitations,
    )
    receipt["coverage"] = {
        "members": len(contract["estimand"]["member_ids"]),
        "accepted_windows": len(accepted_windows),
        "excluded_retained_windows": len(
            contract["estimand"]["excluded_retained_windows"]
        ),
        "files": len(inventory_rows),
        "accepted_attempts": accepted_rows,
        "excluded_retained_attempts": excluded_rows,
        "total_attempts": total_rows,
        "complete_quote_pairs": contract["estimand"]["complete_quote_pairs"],
        "received_bytes": total_received,
        "stored_bytes": total_stored,
    }
    receipt["quality_metrics"] = {
        "unique_composite_identities": len(composite_ids),
        "unique_quote_attempt_ids": len(quote_attempt_ids),
        "unique_raw_event_ids": len(raw_event_ids),
        "unique_content_hashes": len(content_hashes),
        "duplicate_content_hashes": duplicate_content_hashes,
        "pit_violations": pit_violation_count,
        "latency_mismatches": latency_mismatch_count,
        "minimum_request_gap_seconds": (
            round(min(request_gaps), 6) if request_gaps else None
        ),
        "accepted_trigger_separation_seconds": [
            round(value, 6) for value in accepted_trigger_gaps
        ],
        "revision_conflicts": len(revision_failures),
        "hard_failure_count": len(set(hard_failures)),
        "limitation_count": len(set(limitations)),
    }
    receipt["claims"]["narrow_quote_only_data_quality"] = (
        receipt["verdict"]
        in {
            "FIT_WITH_LIMITATIONS",
            "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND",
        }
    )
    receipt["next_gate"] = {
        "task_id": "TASK-19",
        "status": (
            "ELIGIBLE_CONDITIONAL_ON_TASK18_ACCEPTANCE"
            if receipt["claims"]["narrow_quote_only_data_quality"]
            else "BLOCKED_BY_TASK18_QUALITY"
        ),
        "replay_authorized_by_this_audit": False,
    }
    return receipt
