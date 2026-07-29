"""Exact one-window timing repair for TASK-17A."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as TASK10_TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate,
)
from solana_alpha_lab.task17a_execution_capacity_panel import run_window

REPAIR_CONTRACT_SHA256 = (
    "cbb1899a52b4014b2470e58e061785c6842b8c903ec7bc1063a841bd16dc2b16"
)
EXTERNAL_AUTHORITY_PHRASE = "T17A-A3R_ONE_WINDOW_TIMING_REPAIR_V1"
ORIGINAL_LOGICAL_ROOT = "task17a_execution_capacity_quote_panel_v1"
REPAIR_LOGICAL_ROOT = "task17a_execution_capacity_quote_panel_v1_repair_01"
REPAIR_WINDOW_ID = "T17A-WINDOW-04-REPAIR-01"
MINIMUM_REPAIR_SEPARATION_SECONDS = 1801


class Task17ATimingRepairError(RuntimeError):
    """The repair cannot proceed under its frozen contract."""


@dataclass(frozen=True, slots=True)
class Task17ATimingRepairGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise Task17ATimingRepairError(
                "repair_external_authority_phrase_mismatch"
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_repair_contract(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != REPAIR_CONTRACT_SHA256:
        raise Task17ATimingRepairError("repair_contract_hash_mismatch")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise Task17ATimingRepairError("repair_contract_json_invalid") from exc
    if not isinstance(value, dict):
        raise Task17ATimingRepairError("repair_contract_root_invalid")
    expected = {
        "schema": "solana_alpha_lab.task17a_one_window_timing_repair_contract",
        "schema_version": "1.0",
        "task_id": "TASK-17A",
        "atom_id": "T17A-A3R_ONE_WINDOW_TIMING_REPAIR_V1",
        "status": "FROZEN_OFFLINE_REPAIR_CONTRACT",
    }
    for name, expected_value in expected.items():
        if value.get(name) != expected_value:
            raise Task17ATimingRepairError(f"repair_contract_{name}_drift")
    if value.get("authority", {}).get("network") is not False:
        raise Task17ATimingRepairError("repair_contract_pre_gate_network_drift")
    if value.get("caps", {}).get("provider_calls_max") != 8:
        raise Task17ATimingRepairError("repair_contract_call_cap_drift")
    return value


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Task17ATimingRepairError("original_trigger_time_invalid")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task17ATimingRepairError(
            "original_trigger_time_invalid"
        ) from exc


def repair_preflight(
    *,
    raw_root: Path,
    contract_path: Path,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    contract = load_repair_contract(contract_path)
    original_root = raw_root / ORIGINAL_LOGICAL_ROOT
    for item in (
        *contract["accepted_input_windows"],
        contract["excluded_but_retained_window"],
    ):
        window_root = original_root / f"window={item['window_id']}"
        expected = {
            "raw_events.jsonl": item["raw_events_sha256"],
            "manifest.json": item["manifest_sha256"],
            "receipt.json": item["receipt_sha256"],
        }
        for filename, sha256 in expected.items():
            path = window_root / filename
            if not path.is_file() or _sha256(path) != sha256:
                raise Task17ATimingRepairError(
                    f"original_evidence_drift:{item['window_id']}:{filename}"
                )
    window3_receipt = json.loads(
        (
            original_root
            / "window=T17A-WINDOW-03"
            / "receipt.json"
        ).read_text(encoding="utf-8")
    )
    trigger = _parse_utc(window3_receipt.get("triggered_at"))
    earliest = trigger + timedelta(
        seconds=MINIMUM_REPAIR_SEPARATION_SECONDS
    )
    observed_now = now().astimezone(UTC)
    repair_root = raw_root / REPAIR_LOGICAL_ROOT
    return {
        "contract_sha256": REPAIR_CONTRACT_SHA256,
        "earliest_replacement_trigger_at": earliest.isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
        "ready_by_wall_clock": observed_now >= earliest,
        "repair_output_exists": repair_root.exists(),
        "remaining_seconds": max(
            0.0, (earliest - observed_now).total_seconds()
        ),
        "provider_calls_max": 8,
        "network_enabled": False,
        "raw_live_writes": 0,
        "api_keys": 0,
        "accounts": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
    }


def run_repair(
    *,
    gate: Task17ATimingRepairGate,
    raw_root: Path,
    contract_path: Path,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    transport: Any | None = None,
) -> dict[str, Any]:
    if not isinstance(gate, Task17ATimingRepairGate):
        raise Task17ATimingRepairError("repair_runtime_gate_required")
    preflight = repair_preflight(
        raw_root=raw_root,
        contract_path=contract_path,
        now=now,
    )
    if not preflight["ready_by_wall_clock"]:
        raise Task17ATimingRepairError("repair_window_too_early")
    if preflight["repair_output_exists"]:
        raise Task17ATimingRepairError("repair_output_already_exists")
    exact_transport = (
        transport
        if transport is not None
        else BoundedQuoteTransport(
            gate=ExternalExecutionGate(
                authority_phrase=TASK10_TRANSPORT_AUTHORITY
            ),
            now=now,
        )
    )
    summary = run_window(
        raw_root=raw_root,
        window_id=REPAIR_WINDOW_ID,
        transport=exact_transport,
        now=now,
        logical_root=REPAIR_LOGICAL_ROOT,
    )
    return {
        "atom": EXTERNAL_AUTHORITY_PHRASE,
        "status": summary.status,
        "stop_reason": summary.stop_reason,
        "provider_calls": summary.provider_calls,
        "received_bytes": summary.received_bytes,
        "stored_bytes": summary.stored_bytes,
        "window": summary.safe_receipt(),
        "api_keys": 0,
        "accounts": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
    }
