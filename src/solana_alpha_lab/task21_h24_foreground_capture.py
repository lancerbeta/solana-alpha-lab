"""Foreground-only H24+ quote capture for one frozen TASK-21 sentinel."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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
ATOM_ID = "T21-A6S_H24_FOREGROUND_CAPTURE_V1"
SCHEMA_VERSION = "1.1"
HORIZON_ID = "H24"
OUTPUT_RELATIVE_ROOT = "local/task21_forward/h24_capture"
CALLS_PER_PANEL_MAX = 8
CALLS_TOTAL_MAX = 8
RECEIVED_BYTES_MAX = 3_145_728
DURABLE_BYTES_MAX = 16_777_216
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
EXPECTED_H0_MEMBER_IDS = (
    "T21-WATCH-4646910e9ea14e84d646",
    "T21-WATCH-7bfebd2c448c165d7527",
    "T21-WATCH-5630c96c741142a47a23",
)
EXPECTED_SENTINEL_MEMBER_ID = EXPECTED_H0_MEMBER_IDS[0]


class Task21H24Error(RuntimeError):
    """H24 cannot safely proceed."""


class Task21H24AuthorityRequired(Task21H24Error):
    """The exact provider authority is absent."""


@dataclass(frozen=True, slots=True)
class Task21H24ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21H24AuthorityRequired(
                "task21_h24_external_authority_phrase_mismatch"
            )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21H24Error("json_root_invalid")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21H24Error("config_root_invalid")
    return value


def _utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21H24Error(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21H24Error(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21H24Error(f"{name}_must_be_timezone_aware")
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
        raise Task21H24Error("h24_create_only_collision") from exc


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
        config.get("schema") != "smial.task21_h24_foreground_capture"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
    ):
        raise Task21H24Error("h24_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list) or not protected:
        raise Task21H24Error("h24_protected_inputs_missing")
    for item in protected:
        path = repo_root / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise Task21H24Error(
                f"protected_input_hash_drift:{item.get('role', 'UNKNOWN')}"
            )
    dynamic = config.get("dynamic_control", {})
    marker_path = repo_root / str(dynamic.get("path", ""))
    if (
        dynamic.get("role") != "ACTIVE_TIME_GATES"
        or dynamic.get("gate_id") != "TASK21-H24-2026-08-01T07-50-34Z"
        or dynamic.get("allowed_statuses") != ["ACTIVE_WAITING"]
        or not marker_path.is_file()
    ):
        raise Task21H24Error("h24_dynamic_control_contract_drift")
    marker = _load_json(marker_path)
    matching = [
        item
        for item in marker.get("gates", [])
        if item.get("gate_id") == dynamic["gate_id"]
    ]
    if len(matching) != 1 or matching[0].get("status") not in dynamic[
        "allowed_statuses"
    ]:
        raise Task21H24Error("h24_active_time_gate_drift")
    if matching[0].get("required_next_atom") != ATOM_ID:
        raise Task21H24Error("h24_required_atom_drift")
    recovery_prerequisite = matching[0].get("recovery_prerequisite", {})
    if recovery_prerequisite.get("status") != "SATISFIED_WITH_EVIDENCE":
        raise Task21H24Error("h24_recovery_prerequisite_not_satisfied")
    gate = config.get("time_gate", {})
    if (
        gate.get("gate_id") != "TASK21-H24-2026-08-01T07-50-34Z"
        or gate.get("earliest_at") != "2026-08-01T07:50:34.414367Z"
        or gate.get("eligibility_mode") != "MINIMUM_AGE_NO_EXPIRY"
        or gate.get("latest_at") is not None
        or gate.get("after_earliest")
        != "ELIGIBLE_WHEN_SEPARATELY_AUTHORIZED"
        or gate.get("late_capture_policy")
        != "ALLOW_AND_RECORD_ACTUAL_ELAPSED_SECONDS"
    ):
        raise Task21H24Error("h24_time_gate_drift")
    population = config.get("population", {})
    if (
        population.get("source") != "EXACT_H0_ADMISSION_EVENTS"
        or population.get("source_members") != 3
        or population.get("sentinel_members") != 1
        or population.get("member_ids") != [EXPECTED_SENTINEL_MEMBER_ID]
        or population.get("selection_key")
        != [
            "first_reliable_available_at",
            "observed_at",
            "nomination_event_id",
        ]
        or population.get("outcome_or_route_selection_allowed") is not False
    ):
        raise Task21H24Error("h24_sentinel_selection_drift")
    h24 = config.get("h24", {})
    if (
        h24.get("horizon_semantics") != "MINIMUM_AGE_24H_PLUS"
        or h24.get("panels_max") != 1
        or h24.get("provider_calls_per_panel_max") != CALLS_PER_PANEL_MAX
        or h24.get("provider_calls_total_max") != CALLS_TOTAL_MAX
        or h24.get("durable_local_bytes_max") != DURABLE_BYTES_MAX
        or h24.get("notionals_usd") != [10, 25, 50, 100]
    ):
        raise Task21H24Error("h24_cap_drift")
    recovery = config.get("recovery", {})
    if (
        recovery.get("required_health") != "HEALTHY"
        or recovery.get("backup_age_hours_max_at_start") != 24
        or recovery.get("restore_age_hours_max_at_start") != 168
        or recovery.get("drive_actions") != 0
    ):
        raise Task21H24Error("h24_recovery_boundary_drift")
    next_boundary = config.get("next_boundary", {})
    if (
        next_boundary.get("status") != "DEFERRED_TRIGGER_ONLY"
        or next_boundary.get("mandatory_horizons") != []
        or next_boundary.get("candidate_horizons") != ["H72", "H168"]
        or next_boundary.get("active_time_gate_created") is not False
        or next_boundary.get("provider_api_rpc_wss_calls_authorized") is not False
    ):
        raise Task21H24Error("h24_next_boundary_drift")
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
        raise Task21H24Error("h24_authority_boundary_drift")


def _load_members(config: Mapping[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    item = next(
        value
        for value in config["protected_inputs"]
        if value["role"] == "H0_ADMISSION_EVENTS"
    )
    members: list[dict[str, Any]] = []
    for line in (repo_root / item["path"]).read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Task21H24Error("h0_admission_event_invalid")
        members.append(value)
    if tuple(item.get("member_id") for item in members) != EXPECTED_H0_MEMBER_IDS:
        raise Task21H24Error("h24_population_or_order_drift")
    if any(
        not isinstance(item.get("mint"), str)
        or not isinstance(item.get("mint_decimals"), int)
        or item.get("exited_at") is not None
        for item in members
    ):
        raise Task21H24Error("h24_member_contract_drift")
    sentinel = members[0]
    if sentinel.get("member_id") != EXPECTED_SENTINEL_MEMBER_ID:
        raise Task21H24Error("h24_sentinel_selection_drift")
    return [sentinel]


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
        stop_reason = buy_capture.transport_stop_reason or buy_projection.stop_reason
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(buy_projection, attempt_ordinal=5 + index)
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
        stop_reason = sell_capture.transport_stop_reason or sell_projection.stop_reason
        if stop_reason is not None:
            break
    if transport.attempts > CALLS_PER_PANEL_MAX:
        raise Task21H24Error("h24_panel_call_cap_exceeded")
    if not projections:
        raise Task21H24Error("h24_panel_has_no_evidence")

    member_id = member["member_id"]
    window_id = f"{member_id}-{HORIZON_ID}"
    window_root = run_root / f"member={member_id}" / f"horizon={HORIZON_ID}"
    envelopes = [
        _projection_envelope(
            projection,
            member=member,
            window_id=window_id,
            ordinal=index,
        )
        for index, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(canonical_json_bytes(item) + b"\n" for item in envelopes)
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
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, canonical_json_bytes(receipt) + b"\n")
    return {
        **receipt,
        "stored_bytes": sum(
            path.stat().st_size for path in window_root.rglob("*") if path.is_file()
        ),
        "receipt_sha256": sha256_file(receipt_path),
    }


def run_h24_foreground_capture(
    *,
    gate: Task21H24ExecutionGate | None,
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
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Task21H24Error("runtime_now_must_be_timezone_aware")
    observed_at = observed_at.astimezone(UTC)
    earliest = _utc("earliest_at", config["time_gate"]["earliest_at"])
    if observed_at < earliest:
        raise Task21H24Error("h24_minimum_age_not_reached")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else (repo_root / OUTPUT_RELATIVE_ROOT).resolve()
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
    actual_elapsed_seconds = int((observed_at - latest_h0).total_seconds())
    if actual_elapsed_seconds < 86_400:
        raise Task21H24Error("h24_minimum_age_not_reached")
    recovery = _load_json(recovery_receipt_path)
    if not isinstance(gate, Task21H24ExecutionGate):
        raise Task21H24AuthorityRequired(
            "task21_h24_external_execution_gate_required"
        )
    if output_root_override is not None and transport_factory is None:
        raise Task21H24Error("output_override_requires_injected_transport")
    try:
        validate_recovery_freshness(recovery, now=observed_at)
    except Task21LiveShakedownError as exc:
        raise Task21H24Error(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(repo_root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21H24Error("h24_disk_pressure")
    members = _load_members(config, repo_root)
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": sha256_file(config_path),
        "started_at": _utc_text(observed_at),
    }
    run_id = (
        "h24-"
        + observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21H24Error("h24_run_output_already_exists")

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
            else BoundedQuoteTransport(gate=TransportGate(TRANSPORT_AUTHORITY))
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
        raise Task21H24Error("h24_total_call_cap_exceeded")
    if received > RECEIVED_BYTES_MAX:
        raise Task21H24Error("h24_total_received_byte_cap_exceeded")
    complete = len(summaries) == 1 and all(
        item["status"] == "COMPLETE" for item in summaries
    )
    receipt = {
        "schema": "smial.task21.h24-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "started_at": _utc_text(observed_at),
        "timing": {
            "semantics": "MINIMUM_AGE_24H_PLUS",
            "h0_anchor_at": _utc_text(latest_h0),
            "not_before_at": _utc_text(earliest),
            "actual_elapsed_seconds": actual_elapsed_seconds,
            "late_capture_allowed": True,
            "narrow_expiry_window_used": False,
        },
        "population": {
            "source_population_count": len(EXPECTED_H0_MEMBER_IDS),
            "member_ids": [EXPECTED_SENTINEL_MEMBER_ID],
            "sentinel_selection_key": list(
                config["population"]["selection_key"]
            ),
            "changed": False,
            "outcome_or_route_selection_used": False,
        },
        "h24": {
            "panels_complete": sum(item["status"] == "COMPLETE" for item in summaries),
            "panels_stopped": sum(item["status"] != "COMPLETE" for item in summaries),
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
            "status": (
                "DEFERRED_TRIGGER_ONLY"
                if complete
                else "H24_STOPPED_REVIEW_REQUIRED"
            ),
            "mandatory_horizons": [],
            "candidate_horizons": ["H72", "H168"],
            "active_time_gate_created": False,
            "provider_api_rpc_wss_calls_authorized": False,
            "activation_requires": [
                "NAMED_CONSUMER_OR_HYPOTHESIS_NEED",
                "FRESH_WHOLE_TASK_BUDGET_PROOF",
                "SEPARATE_EXACT_USER_AUTHORITY",
            ],
        },
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_HYPOTHESIS_OUTCOME_UNSEALED",
            "NO_DRIVE_ACTION_IN_H24",
            "NO_A7_CATALOG_TRANSACTION",
        ],
    }
    local_receipt_path = run_root / "runtime_receipt.json"
    _write_new(local_receipt_path, canonical_json_bytes(receipt) + b"\n")
    stored = sum(path.stat().st_size for path in run_root.rglob("*") if path.is_file())
    if stored > DURABLE_BYTES_MAX:
        raise Task21H24Error("h24_total_durable_byte_cap_exceeded")
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
