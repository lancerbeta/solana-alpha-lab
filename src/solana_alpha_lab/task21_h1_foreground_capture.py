"""Foreground-only H1 quote capture for the exact TASK-21 H0 population."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as TransportGate,
    HttpCapture,
)
from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_multi_horizon_capture import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_H1_FOREGROUND_CAPTURE_V1"
SCHEMA_VERSION = "1.0"
HORIZON_ID = "H1"
OUTPUT_RELATIVE_ROOT = "local/task21_forward/h1_capture"
CALLS_PER_PANEL_MAX = 8
CALLS_TOTAL_MAX = 24
RECEIVED_BYTES_MAX = 3_145_728
DURABLE_BYTES_MAX = 16_777_216
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
EXPECTED_MEMBER_IDS = (
    "T21-WATCH-4646910e9ea14e84d646",
    "T21-WATCH-7bfebd2c448c165d7527",
    "T21-WATCH-5630c96c741142a47a23",
)


class Task21H1Error(RuntimeError):
    """H1 cannot safely proceed."""


class Task21H1AuthorityRequired(Task21H1Error):
    """The exact provider authority is absent."""


@dataclass(frozen=True, slots=True)
class Task21H1ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21H1AuthorityRequired(
                "task21_h1_external_authority_phrase_mismatch"
            )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21H1Error("json_root_invalid")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21H1Error("config_root_invalid")
    return value


def _utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21H1Error(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21H1Error(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21H1Error(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise Task21H1Error("h1_create_only_collision") from exc


def _inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("schema") != "smial.task21_h1_foreground_capture"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
    ):
        raise Task21H1Error("h1_config_identity_drift")
    for item in config.get("protected_inputs", []):
        path = repo_root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise Task21H1Error(
                f"protected_input_hash_drift:{item.get('role', 'UNKNOWN')}"
            )
    gate = config.get("time_gate", {})
    if (
        gate.get("gate_id") != "TASK21-H1-2026-07-31T08-50-34Z"
        or gate.get("earliest_at") != "2026-07-31T08:50:34.414367Z"
        or gate.get("latest_at") != "2026-07-31T09:00:34.414367Z"
        or gate.get("after_latest")
        != "WRITE_EXPLICIT_GAP_NO_PROVIDER_NO_BACKFILL"
    ):
        raise Task21H1Error("h1_time_gate_drift")
    h1 = config.get("h1", {})
    if (
        h1.get("panels_max") != 3
        or h1.get("provider_calls_per_panel_max") != CALLS_PER_PANEL_MAX
        or h1.get("provider_calls_total_max") != CALLS_TOTAL_MAX
        or h1.get("durable_local_bytes_max") != DURABLE_BYTES_MAX
        or h1.get("notionals_usd") != [10, 25, 50, 100]
    ):
        raise Task21H1Error("h1_cap_drift")
    authority = config.get("authority", {})
    if (
        authority.get("exact_phrase") != ATOM_ID
        or authority.get("provider_api_rpc_wss_calls_max") != CALLS_TOTAL_MAX
        or authority.get("drive_reads") != 0
        or authority.get("drive_writes") != 0
        or authority.get("cash_spend_usd_cents") != 0
        or authority.get("wallet_signer_transaction_actions") != 0
        or authority.get("scheduler_or_background_process") is not False
    ):
        raise Task21H1Error("h1_authority_boundary_drift")


def _load_members(config: Mapping[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    admission_item = next(
        item
        for item in config["protected_inputs"]
        if item["role"] == "H0_ADMISSION_EVENTS"
    )
    members: list[dict[str, Any]] = []
    for line in (repo_root / admission_item["path"]).read_text(
        encoding="utf-8"
    ).splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Task21H1Error("h0_admission_event_invalid")
        members.append(value)
    if tuple(item.get("member_id") for item in members) != EXPECTED_MEMBER_IDS:
        raise Task21H1Error("h1_population_or_order_drift")
    if any(
        not isinstance(item.get("mint"), str)
        or not isinstance(item.get("mint_decimals"), int)
        or item.get("exited_at") is not None
        for item in members
    ):
        raise Task21H1Error("h1_member_contract_drift")
    return members


def _projection_envelope(
    projection: QuoteProjection,
    *,
    member: Mapping[str, Any],
    window_id: str,
    ordinal: int,
) -> dict[str, Any]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "horizon_id": HORIZON_ID,
        "hypothesis_version_id": member["hypothesis_version_id"],
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "window_id": window_id,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": _utc_text(quote.requested_at),
        "response_at": (
            None if quote.response_at is None else _utc_text(quote.response_at)
        ),
        "terminal_class": getattr(quote.status, "value", str(quote.status)),
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def _capture_member(
    *,
    run_root: Path,
    config_hash: str,
    member: Mapping[str, Any],
    transport: Any,
    now: Callable[[], datetime],
    clock: Callable[[], float],
) -> dict[str, Any]:
    triggered_at = _utc_text(now())
    started = clock()
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    for index, buy_request in enumerate(
        build_buy_panel_requests(
            selected_output_mint=member["mint"],
            output_decimals=member["mint_decimals"],
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    ):
        if clock() - started >= WALL_SECONDS_MAX:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        buy_capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(
            buy_request, buy_capture.observation
        )
        projections.append(buy_projection)
        terminal = getattr(
            buy_projection.quote_attempt.status,
            "value",
            str(buy_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = (
            buy_capture.transport_stop_reason or buy_projection.stop_reason
        )
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(
            buy_projection,
            attempt_ordinal=5 + index,
        )
        if sell.request is None:
            sell_not_attempted += 1
            continue
        sell_capture: HttpCapture = transport.execute(sell.request)
        sell_attempts += 1
        sell_projection = project_quote_observation(
            sell.request, sell_capture.observation
        )
        projections.append(sell_projection)
        terminal = getattr(
            sell_projection.quote_attempt.status,
            "value",
            str(sell_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = (
            sell_capture.transport_stop_reason or sell_projection.stop_reason
        )
        if stop_reason is not None:
            break
    if transport.attempts > CALLS_PER_PANEL_MAX:
        raise Task21H1Error("h1_panel_call_cap_exceeded")
    if not projections:
        raise Task21H1Error("h1_panel_has_no_evidence")

    member_id = member["member_id"]
    window_id = f"{member_id}-H1"
    window_root = run_root / f"member={member_id}" / "horizon=H1"
    envelopes = [
        _projection_envelope(
            projection,
            member=member,
            window_id=window_id,
            ordinal=index,
        )
        for index, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in envelopes
    )
    raw_path = window_root / "raw_events.jsonl"
    _write_new(raw_path, raw_bytes)
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "horizon_id": HORIZON_ID,
        "config_sha256": config_hash,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "triggered_at": triggered_at,
        "files": [
            {
                "logical_path": "raw_events.jsonl",
                "bytes": len(raw_bytes),
                "sha256": sha256_bytes(raw_bytes),
            }
        ],
    }
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    manifest_path = window_root / "manifest.json"
    _write_new(manifest_path, manifest_bytes)
    receipt = {
        "schema": "smial.task21.forward-quote-panel-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "horizon_id": HORIZON_ID,
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "provider_calls": transport.attempts,
        "modeled_provider_credits": transport.attempts,
        "received_bytes": transport.received_bytes,
        "buy_attempts": buy_attempts,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "raw_events_sha256": sha256_file(raw_path),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, receipt_bytes)
    return {
        **receipt,
        "stored_bytes": sum(
            path.stat().st_size
            for path in window_root.rglob("*")
            if path.is_file()
        ),
        "receipt_sha256": sha256_file(receipt_path),
    }


def _gap_receipt(
    *,
    output_root: Path,
    observed_at: datetime,
    earliest: datetime,
    latest: datetime,
) -> dict[str, Any]:
    claim = {
        "atom_id": ATOM_ID,
        "observed_at": _utc_text(observed_at),
        "latest_at": _utc_text(latest),
    }
    run_id = "h1-gap-" + sha256_bytes(canonical_json_bytes(claim))[:16]
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21H1Error("h1_gap_output_already_exists")
    receipt = {
        "schema": "smial.task21.h1-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "GAP",
        "reason": "H1_WINDOW_MISSED_NO_BACKFILL",
        "observed_at": _utc_text(observed_at),
        "earliest_at": _utc_text(earliest),
        "latest_at": _utc_text(latest),
        "actual_actions": {
            "provider_api_rpc_wss_calls": 0,
            "modeled_provider_credits": 0,
            "local_live_windows": 0,
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "backfill": False,
        "rescheduled": False,
    }
    path = run_root / "gap_receipt.json"
    _write_new(path, canonical_json_bytes(receipt) + b"\n")
    receipt["local_evidence"] = {
        "root": run_root.as_posix(),
        "files": _inventory(run_root),
    }
    return receipt


def run_h1_foreground_capture(
    *,
    gate: Task21H1ExecutionGate,
    repo_root: Path,
    config_path: Path,
    recovery_receipt_path: Path,
    transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(gate, Task21H1ExecutionGate):
        raise Task21H1AuthorityRequired(
            "task21_h1_external_execution_gate_required"
        )
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Task21H1Error("runtime_now_must_be_timezone_aware")
    observed_at = observed_at.astimezone(UTC)
    earliest = _utc("earliest_at", config["time_gate"]["earliest_at"])
    latest = _utc("latest_at", config["time_gate"]["latest_at"])
    if observed_at < earliest:
        raise Task21H1Error("h1_window_not_open")
    if output_root_override is not None and transport_factory is None:
        raise Task21H1Error("output_override_requires_injected_transport")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else (repo_root / OUTPUT_RELATIVE_ROOT).resolve()
    )
    if observed_at > latest:
        return _gap_receipt(
            output_root=output_root,
            observed_at=observed_at,
            earliest=earliest,
            latest=latest,
        )

    recovery = _load_json(recovery_receipt_path)
    try:
        validate_recovery_freshness(recovery, now=observed_at)
    except Task21LiveShakedownError as exc:
        raise Task21H1Error(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(repo_root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21H1Error("h1_disk_pressure")
    members = _load_members(config, repo_root)
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": sha256_file(config_path),
        "started_at": _utc_text(observed_at),
    }
    run_id = (
        "h1-"
        + observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21H1Error("h1_run_output_already_exists")

    summaries: list[dict[str, Any]] = []
    started = clock()
    for index, member in enumerate(members):
        if index:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started >= WALL_SECONDS_MAX:
            break
        transport = (
            transport_factory(member)
            if transport_factory is not None
            else BoundedQuoteTransport(
                gate=TransportGate(TRANSPORT_AUTHORITY)
            )
        )
        summary = _capture_member(
            run_root=run_root,
            config_hash=sha256_file(config_path),
            member=member,
            transport=transport,
            now=now,
            clock=clock,
        )
        summaries.append(summary)
        if summary["status"] != "COMPLETE":
            break
    calls = sum(int(item["provider_calls"]) for item in summaries)
    received = sum(int(item["received_bytes"]) for item in summaries)
    if calls > CALLS_TOTAL_MAX:
        raise Task21H1Error("h1_total_call_cap_exceeded")
    if received > RECEIVED_BYTES_MAX:
        raise Task21H1Error("h1_total_received_byte_cap_exceeded")
    complete = len(summaries) == 3 and all(
        item["status"] == "COMPLETE" for item in summaries
    )
    h0_acceptance = _load_json(
        repo_root
        / next(
            item["path"]
            for item in config["protected_inputs"]
            if item["role"] == "H0_TRACKED_ACCEPTANCE"
        )
    )
    latest_h0 = max(
        _utc("h0_triggered_at", item["triggered_at"])
        for item in h0_acceptance["h0"]["windows"]
    )
    h6_earliest = latest_h0 + timedelta(seconds=21_600)
    receipt = {
        "schema": "smial.task21.h1-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "started_at": _utc_text(observed_at),
        "population": {
            "member_ids": list(EXPECTED_MEMBER_IDS),
            "changed": False,
            "outcome_or_route_selection_used": False,
        },
        "h1": {
            "panels_complete": sum(
                item["status"] == "COMPLETE" for item in summaries
            ),
            "panels_stopped": sum(
                item["status"] != "COMPLETE" for item in summaries
            ),
            "windows": summaries,
        },
        "actual_actions": {
            "provider_api_rpc_wss_calls": calls,
            "modeled_provider_credits": calls,
            "received_bytes": received,
            "local_live_windows": len(summaries),
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": {
            "atom_id": "T21-A6S_H6_FOREGROUND_CAPTURE_V1",
            "status": (
                "ACTIVE_WAITING_NOT_AUTHORIZED"
                if complete
                else "H1_STOPPED_REVIEW_REQUIRED"
            ),
            "earliest_at": _utc_text(h6_earliest),
            "latest_at": _utc_text(h6_earliest + timedelta(minutes=10)),
            "provider_api_rpc_wss_calls_authorized": False,
            "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        },
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_HYPOTHESIS_OUTCOME_UNSEALED",
            "NO_DRIVE_ACTION",
            "NO_A7_CATALOG_TRANSACTION",
        ],
    }
    local_receipt_path = run_root / "runtime_receipt.json"
    _write_new(local_receipt_path, canonical_json_bytes(receipt) + b"\n")
    stored = sum(
        path.stat().st_size for path in run_root.rglob("*") if path.is_file()
    )
    if stored > DURABLE_BYTES_MAX:
        raise Task21H1Error("h1_total_durable_byte_cap_exceeded")
    receipt["local_evidence"] = {
        "root": (
            run_root.relative_to(repo_root).as_posix()
            if output_root_override is None
            else f"TEST_OUTPUT_ROOT/run={run_id}"
        ),
        "stored_bytes": stored,
        "runtime_receipt_sha256": sha256_file(local_receipt_path),
        "files": _inventory(run_root),
        "tracked_in_git": False,
    }
    return receipt
