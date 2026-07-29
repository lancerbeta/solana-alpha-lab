"""Deterministic fail-closed audit for the bounded TASK-17A quote panel."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

from solana_alpha_lab.jupiter_quote_logger import (
    PROVIDER,
    PROVIDER_VERSION,
    USDC_MINT,
)
from solana_alpha_lab.task17a_execution_capacity_panel import (
    CONTRACT_SHA256,
    DURABLE_BYTES_PER_WINDOW_MAX,
    DURABLE_BYTES_TOTAL_MAX,
    HYPOTHESIS_VERSION_ID,
    LOGICAL_ROOT,
    MEMBER_ID,
    MINIMUM_WINDOW_SEPARATION_SECONDS,
    PROVIDER_CALLS_PER_WINDOW_MAX,
    PROVIDER_CALLS_TOTAL_MAX,
    SELECTED_MINT,
    TOTAL_SPAN_SECONDS_MAX,
    WATCHLIST_ID,
    WATCHLIST_VERSION,
    WINDOW_IDS,
    load_frozen_contract,
)
from solana_alpha_lab.task17a_timing_repair import (
    REPAIR_CONTRACT_SHA256,
    REPAIR_LOGICAL_ROOT,
    REPAIR_WINDOW_ID,
    load_repair_contract,
)

NOTIONALS_USD = (10, 25, 50, 100)
NOTIONALS_ATOMIC = tuple(value * 1_000_000 for value in NOTIONALS_USD)


class Task17AAuditError(RuntimeError):
    """Observed evidence violates the frozen TASK-17A contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Task17AAuditError(f"json_load_failed:{path.name}") from exc
    if not isinstance(value, dict):
        raise Task17AAuditError(f"json_root_invalid:{path.name}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise Task17AAuditError("raw_jsonl_load_failed") from exc
    for index, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Task17AAuditError(
                f"raw_json_invalid:{index}"
            ) from exc
        if not isinstance(value, dict):
            raise Task17AAuditError(f"raw_record_invalid:{index}")
        records.append(value)
    return records


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Task17AAuditError(f"{name}_must_be_utc_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task17AAuditError(f"{name}_invalid") from exc
    if parsed.utcoffset() is None:
        raise Task17AAuditError(f"{name}_timezone_missing")
    return parsed


def _assert_equal(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise Task17AAuditError(code)


def _audit_record_identity(
    record: dict[str, Any],
    *,
    window_id: str,
    ordinal: int,
) -> None:
    expected = {
        "schema": "solana_alpha_lab.task17a_quote_panel_raw",
        "schema_version": "1.0",
        "hypothesis_version_id": HYPOTHESIS_VERSION_ID,
        "watchlist_id": WATCHLIST_ID,
        "watchlist_version": WATCHLIST_VERSION,
        "window_id": window_id,
        "member_id": MEMBER_ID,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "endpoint_version": PROVIDER_VERSION,
        "stop_reason": None,
        "terminal_class": "QUOTE_AVAILABLE",
        "error_class": None,
        "response_status": "SUCCESS",
    }
    for key, value in expected.items():
        _assert_equal(record.get(key), value, f"record_{key}_drift")
    quote = record.get("quote_attempt")
    raw = record.get("raw_event")
    if not isinstance(quote, dict) or not isinstance(raw, dict):
        raise Task17AAuditError("embedded_projection_missing")
    _assert_equal(
        record.get("request_hash"),
        quote.get("request_hash"),
        "request_hash_projection_mismatch",
    )
    _assert_equal(
        record.get("idempotency_key"),
        quote.get("idempotency_key"),
        "idempotency_projection_mismatch",
    )
    _assert_equal(
        record.get("raw_content_sha256"),
        raw.get("content_sha256"),
        "raw_content_hash_mismatch",
    )
    _assert_equal(
        record.get("raw_content_sha256"),
        quote.get("response_content_sha256"),
        "quote_content_hash_mismatch",
    )
    _assert_equal(
        raw.get("endpoint_or_method"),
        "GET /swap/v1/quote",
        "endpoint_drift",
    )
    _assert_equal(raw.get("source"), PROVIDER, "raw_provider_drift")
    _assert_equal(
        raw.get("provider_version"),
        PROVIDER_VERSION,
        "raw_provider_version_drift",
    )
    if record.get("route_count", 0) < 1 or not record.get("route_id"):
        raise Task17AAuditError("available_quote_route_identity_missing")
    timestamps = [
        _parse_utc(record.get(name), name=name)
        for name in (
            "requested_at",
            "response_at",
            "first_reliable_available_at",
            "available_to_strategy_at",
            "ingested_at",
        )
    ]
    if timestamps != sorted(timestamps):
        raise Task17AAuditError("pit_timestamp_order_invalid")
    if record.get("latency_ms") is None or record["latency_ms"] < 0:
        raise Task17AAuditError("latency_invalid")


def _audit_pair(
    buy_record: dict[str, Any],
    sell_record: dict[str, Any],
    *,
    notional_atomic: int,
) -> Decimal:
    buy = buy_record["quote_attempt"]
    sell = sell_record["quote_attempt"]
    _assert_equal(buy.get("side"), "BUY", "buy_side_drift")
    _assert_equal(sell.get("side"), "SELL", "sell_side_drift")
    _assert_equal(buy.get("input_mint"), USDC_MINT, "buy_input_mint_drift")
    _assert_equal(
        buy.get("output_mint"), SELECTED_MINT, "buy_output_mint_drift"
    )
    _assert_equal(
        buy.get("input_requested_atomic"),
        notional_atomic,
        "buy_notional_drift",
    )
    _assert_equal(
        sell.get("input_mint"), SELECTED_MINT, "sell_input_mint_drift"
    )
    _assert_equal(
        sell.get("output_mint"), USDC_MINT, "sell_output_mint_drift"
    )
    _assert_equal(
        sell.get("input_requested_atomic"),
        buy.get("output_quoted_atomic"),
        "dependent_sell_input_mismatch",
    )
    output = sell.get("output_quoted_atomic")
    if isinstance(output, bool) or not isinstance(output, int) or output <= 0:
        raise Task17AAuditError("sell_output_invalid")
    return (
        Decimal(10_000)
        * (Decimal(notional_atomic) - Decimal(output))
        / Decimal(notional_atomic)
    )


def audit_panel(
    *,
    raw_root: Path,
    contract_path: Path,
    window_sources: tuple[tuple[str, str], ...] | None = None,
) -> dict[str, Any]:
    """Audit exact raw evidence and return one sanitized deterministic receipt."""

    load_frozen_contract(contract_path)
    sources = (
        tuple((LOGICAL_ROOT, window_id) for window_id in WINDOW_IDS)
        if window_sources is None
        else window_sources
    )
    if len(sources) != 3:
        raise Task17AAuditError("accepted_window_source_count_drift")
    if window_sources is None:
        panel_root = raw_root / LOGICAL_ROOT
        if not panel_root.is_dir():
            raise Task17AAuditError("panel_root_missing")
        actual_windows = tuple(
            path.name.removeprefix("window=")
            for path in sorted(panel_root.iterdir())
            if path.is_dir()
        )
        _assert_equal(actual_windows, WINDOW_IDS, "window_inventory_drift")

    windows: list[dict[str, Any]] = []
    trigger_times: list[datetime] = []
    all_request_times: list[datetime] = []
    composite_attempt_ids: set[tuple[str, str]] = set()
    total_calls = 0
    total_received = 0
    total_stored = 0
    complete_monotonic_panels = 0
    deltas: list[Decimal] = []
    all_costs: dict[str, list[Decimal]] = {}

    for logical_root, window_id in sources:
        window_root = raw_root / logical_root / f"window={window_id}"
        raw_path = window_root / "raw_events.jsonl"
        manifest_path = window_root / "manifest.json"
        receipt_path = window_root / "receipt.json"
        if set(path.name for path in window_root.iterdir()) != {
            "raw_events.jsonl",
            "manifest.json",
            "receipt.json",
        }:
            raise Task17AAuditError("window_file_inventory_drift")
        manifest = _load_json(manifest_path)
        receipt = _load_json(receipt_path)
        records = _load_jsonl(raw_path)
        _assert_equal(len(records), 8, "window_attempt_count_drift")
        _assert_equal(
            receipt.get("provider_calls"),
            PROVIDER_CALLS_PER_WINDOW_MAX,
            "window_receipt_call_count_drift",
        )
        _assert_equal(receipt.get("status"), "COMPLETE", "window_not_complete")
        _assert_equal(receipt.get("stop_reason"), None, "window_stop_present")
        _assert_equal(
            receipt.get("terminal_counts"),
            {"QUOTE_AVAILABLE": 8},
            "window_terminal_counts_drift",
        )
        _assert_equal(
            receipt.get("api_keys_used"), 0, "api_key_use_detected"
        )
        _assert_equal(
            receipt.get("accounts_used"), 0, "account_use_detected"
        )
        _assert_equal(
            receipt.get("cash_spend_usd_cents"), 0, "cash_spend_detected"
        )
        _assert_equal(
            receipt.get("wallet_signer_transaction_actions"),
            0,
            "wallet_signer_transaction_action_detected",
        )
        _assert_equal(
            _sha256(raw_path),
            receipt.get("raw_events_sha256"),
            "raw_receipt_hash_mismatch",
        )
        _assert_equal(
            _sha256(manifest_path),
            receipt.get("manifest_sha256"),
            "manifest_receipt_hash_mismatch",
        )
        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list) or len(manifest_files) != 1:
            raise Task17AAuditError("manifest_file_set_invalid")
        _assert_equal(
            manifest_files[0].get("sha256"),
            _sha256(raw_path),
            "manifest_raw_hash_mismatch",
        )
        _assert_equal(
            manifest_files[0].get("bytes"),
            raw_path.stat().st_size,
            "manifest_raw_size_mismatch",
        )
        _assert_equal(
            manifest.get("contract_sha256"),
            CONTRACT_SHA256,
            "manifest_contract_hash_drift",
        )
        triggered_at = _parse_utc(
            receipt.get("triggered_at"), name="triggered_at"
        )
        trigger_times.append(triggered_at)
        costs: list[Decimal] = []
        previous_request: datetime | None = None
        for ordinal, record in enumerate(records, start=1):
            _audit_record_identity(
                record,
                window_id=window_id,
                ordinal=ordinal,
            )
            requested_at = _parse_utc(
                record["requested_at"], name="requested_at"
            )
            all_request_times.append(requested_at)
            if previous_request is not None:
                if (requested_at - previous_request).total_seconds() < 2.2:
                    raise Task17AAuditError("request_pacing_below_2_2_seconds")
            previous_request = requested_at
            composite = (window_id, record["idempotency_key"])
            if composite in composite_attempt_ids:
                raise Task17AAuditError("composite_attempt_identity_duplicate")
            composite_attempt_ids.add(composite)
        for index, notional_atomic in enumerate(NOTIONALS_ATOMIC):
            costs.append(
                _audit_pair(
                    records[index * 2],
                    records[index * 2 + 1],
                    notional_atomic=notional_atomic,
                )
            )
        if all(left < right for left, right in zip(costs, costs[1:])):
            complete_monotonic_panels += 1
        deltas.append(costs[-1] - costs[0])
        all_costs[window_id] = costs
        stored_bytes = sum(
            path.stat().st_size for path in window_root.iterdir() if path.is_file()
        )
        if stored_bytes > DURABLE_BYTES_PER_WINDOW_MAX:
            raise Task17AAuditError("window_durable_bytes_exceeded")
        total_calls += receipt["provider_calls"]
        total_received += receipt["received_bytes"]
        total_stored += stored_bytes
        windows.append(
            {
                "window_id": window_id,
                "triggered_at": receipt["triggered_at"],
                "provider_calls": receipt["provider_calls"],
                "received_bytes": receipt["received_bytes"],
                "stored_bytes": stored_bytes,
                "raw_events_sha256": _sha256(raw_path),
                "manifest_sha256": _sha256(manifest_path),
                "receipt_sha256": _sha256(receipt_path),
                "terminal_counts": receipt["terminal_counts"],
                "cost_bps_by_notional": {
                    str(notional): format(cost.quantize(Decimal("0.0001")), "f")
                    for notional, cost in zip(NOTIONALS_USD, costs)
                },
                "adjacent_cost_increases": [
                    left < right for left, right in zip(costs, costs[1:])
                ],
                "delta_cost_bps_usd100_minus_usd10": format(
                    (costs[-1] - costs[0]).quantize(Decimal("0.0001")),
                    "f",
                ),
            }
        )

    separations = [
        (right - left).total_seconds()
        for left, right in zip(trigger_times, trigger_times[1:])
    ]
    if any(value < MINIMUM_WINDOW_SEPARATION_SECONDS for value in separations):
        raise Task17AAuditError("window_separation_below_minimum")
    total_span = (trigger_times[-1] - trigger_times[0]).total_seconds()
    if total_span > TOTAL_SPAN_SECONDS_MAX:
        raise Task17AAuditError("total_span_exceeded")
    _assert_equal(
        total_calls, PROVIDER_CALLS_TOTAL_MAX, "total_provider_calls_drift"
    )
    if total_stored > DURABLE_BYTES_TOTAL_MAX:
        raise Task17AAuditError("total_durable_bytes_exceeded")
    if complete_monotonic_panels <= len(sources) / 2:
        hypothesis_result = "FALSIFIED_WITHIN_BOUNDED_PANEL"
    elif median(deltas) <= 0:
        hypothesis_result = "FALSIFIED_WITHIN_BOUNDED_PANEL"
    else:
        hypothesis_result = "SUPPORTED_WITHIN_ONE_MEMBER_THREE_WINDOWS_QUOTE_ONLY"

    return {
        "schema": "smial.task17a_execution_capacity_audit.v1",
        "schema_version": "1.0",
        "task": "TASK-17A",
        "atom": "T17A-A4_DETERMINISTIC_AUDIT_AND_CATALOG_V1",
        "verdict": "PASS",
        "contract_sha256": CONTRACT_SHA256,
        "raw_logical_roots": sorted(
            {logical_root for logical_root, _window_id in sources}
        ),
        "hypothesis_version_id": HYPOTHESIS_VERSION_ID,
        "watchlist_id": WATCHLIST_ID,
        "watchlist_version": WATCHLIST_VERSION,
        "member_ids": [MEMBER_ID],
        "coverage": {
            "members": 1,
            "windows": len(sources),
            "notionals_usd": list(NOTIONALS_USD),
            "provider_calls": total_calls,
            "complete_quote_pairs": len(sources) * 4,
            "typed_failures": 0,
            "outages": 0,
            "received_bytes": total_received,
            "stored_bytes": total_stored,
        },
        "timing": {
            "window_separation_seconds": [
                round(value, 6) for value in separations
            ],
            "total_span_seconds": round(total_span, 6),
            "first_requested_at": min(all_request_times)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            "last_requested_at": max(all_request_times)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
        },
        "windows": windows,
        "hypothesis_evaluation": {
            "estimand": (
                "MEDIAN_COST_BPS_USD100_MINUS_USD10_ACROSS_COMPLETE_MATCHED_PANELS"
            ),
            "median_delta_cost_bps": format(
                Decimal(median(deltas)).quantize(Decimal("0.0001")), "f"
            ),
            "complete_monotonic_panels": complete_monotonic_panels,
            "complete_panels": len(sources),
            "result": hypothesis_result,
            "current_state": "PAUSED",
            "promotion_authorized": False,
            "task18_quality_gate_eligible": True,
        },
        "claims": {
            "quote_only_temporal_replication": True,
            "cross_token_generalization": False,
            "data_quality": False,
            "fillable": False,
            "realized_vwap": False,
            "net_return": False,
            "alpha": False,
            "signal_or_strategy": False,
        },
        "authority": {
            "provider_api_calls": total_calls,
            "modeled_generic_credits": total_calls,
            "billed_credits_claim": "NOT_AVAILABLE_KEYLESS",
            "api_keys": 0,
            "accounts": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
            "retries": 0,
            "concurrency": 1,
        },
    }


def audit_repaired_panel(
    *,
    raw_root: Path,
    contract_path: Path,
    repair_contract_path: Path,
) -> dict[str, Any]:
    """Audit the frozen repaired window set and reconcile all provider calls."""

    repair = load_repair_contract(repair_contract_path)
    accepted_ids = tuple(repair["accepted_window_set_after_repair"])
    expected_ids = (
        "T17A-WINDOW-01",
        "T17A-WINDOW-03",
        REPAIR_WINDOW_ID,
    )
    _assert_equal(
        accepted_ids,
        expected_ids,
        "repair_accepted_window_set_drift",
    )
    result = audit_panel(
        raw_root=raw_root,
        contract_path=contract_path,
        window_sources=(
            (LOGICAL_ROOT, accepted_ids[0]),
            (LOGICAL_ROOT, accepted_ids[1]),
            (REPAIR_LOGICAL_ROOT, accepted_ids[2]),
        ),
    )
    excluded = repair["excluded_but_retained_window"]
    excluded_root = (
        raw_root / LOGICAL_ROOT / f"window={excluded['window_id']}"
    )
    for filename, field in (
        ("raw_events.jsonl", "raw_events_sha256"),
        ("manifest.json", "manifest_sha256"),
        ("receipt.json", "receipt_sha256"),
    ):
        _assert_equal(
            _sha256(excluded_root / filename),
            excluded[field],
            f"excluded_window_{field}_drift",
        )
    excluded_receipt = _load_json(excluded_root / "receipt.json")
    repair_receipt = _load_json(
        raw_root
        / REPAIR_LOGICAL_ROOT
        / f"window={REPAIR_WINDOW_ID}"
        / "receipt.json"
    )
    original_trigger_1 = _parse_utc(
        _load_json(
            raw_root
            / LOGICAL_ROOT
            / "window=T17A-WINDOW-01"
            / "receipt.json"
        )["triggered_at"],
        name="original_window_01_triggered_at",
    )
    original_trigger_2 = _parse_utc(
        excluded_receipt["triggered_at"],
        name="original_window_02_triggered_at",
    )
    exact_shortfall = Decimal("1800") - Decimal(
        str((original_trigger_2 - original_trigger_1).total_seconds())
    )
    result["repair"] = {
        "repair_contract_sha256": REPAIR_CONTRACT_SHA256,
        "root_cause": repair["defect"]["root_cause"],
        "post_hoc_tolerance_allowed": False,
        "excluded_but_retained_window": {
            "window_id": excluded["window_id"],
            "reason": excluded["reason"],
            "provider_calls": excluded_receipt["provider_calls"],
            "trigger_separation_shortfall_seconds": format(
                exact_shortfall.quantize(Decimal("0.000001")), "f"
            ),
            "raw_events_sha256": excluded["raw_events_sha256"],
            "manifest_sha256": excluded["manifest_sha256"],
            "receipt_sha256": excluded["receipt_sha256"],
        },
        "replacement_window": {
            "window_id": REPAIR_WINDOW_ID,
            "provider_calls": repair_receipt["provider_calls"],
            "raw_events_sha256": repair_receipt["raw_events_sha256"],
            "manifest_sha256": repair_receipt["manifest_sha256"],
            "receipt_sha256": _sha256(
                raw_root
                / REPAIR_LOGICAL_ROOT
                / f"window={REPAIR_WINDOW_ID}"
                / "receipt.json"
            ),
        },
    }
    result["coverage"]["excluded_provider_calls"] = excluded_receipt[
        "provider_calls"
    ]
    result["authority"]["provider_api_calls"] = (
        PROVIDER_CALLS_TOTAL_MAX + repair_receipt["provider_calls"]
    )
    result["authority"]["modeled_generic_credits"] = result["authority"][
        "provider_api_calls"
    ]
    result["authority"]["approved_atoms"] = [
        "T17A-A3_BOUNDED_EXTERNAL_QUOTE_PANEL_V1",
        "T17A-A3R_ONE_WINDOW_TIMING_REPAIR_V1",
    ]
    return result
