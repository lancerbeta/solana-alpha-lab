"""Bounded real admission and H0 capture for TASK-21."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeAlias

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
    EXTERNAL_AUTHORITY_PHRASE as TASK10_TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as Task10TransportGate,
    HttpCapture,
)
from solana_alpha_lab.pilot_supervisor import SupervisorLimits
from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_real_nomination import (
    ATOM_ID as NOMINATION_ATOM_ID,
    evaluate_offline_batch,
)


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1"
SCHEMA_VERSION = "1.0"
OUTPUT_RELATIVE_ROOT = "local/task21_forward/h0_capture"
PROVIDER_CALLS_PER_PANEL_MAX = 8
PROVIDER_CALLS_TOTAL_MAX = 24
RECEIVED_BYTES_TOTAL_MAX = 3_145_728
DURABLE_BYTES_TOTAL_MAX = 16_777_216
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
H1_OFFSET = timedelta(hours=1)
H1_GRACE = timedelta(minutes=10)
BACKUP_MAX_AGE_FROM_H0 = timedelta(hours=24)


class Task21MultiHorizonError(RuntimeError):
    """The bounded admission or H0 capture cannot safely proceed."""


class Task21MultiHorizonAuthorityRequired(Task21MultiHorizonError):
    """The exact user gate for real admissions and provider calls is absent."""


@dataclass(frozen=True, slots=True)
class Task21H0ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21MultiHorizonAuthorityRequired(
                "task21_h0_external_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True)
class H0WindowSummary:
    member_id: str
    nomination_event_id: str
    window_id: str
    triggered_at: str
    status: str
    stop_reason: str | None
    provider_calls: int
    received_bytes: int
    buy_attempts: int
    sell_attempts: int
    sell_not_attempted: int
    terminal_counts: dict[str, int]
    stored_bytes: int
    raw_events_sha256: str
    manifest_sha256: str
    receipt_sha256: str

    def safe_receipt(self) -> dict[str, JsonValue]:
        return {
            "buy_attempts": self.buy_attempts,
            "manifest_sha256": self.manifest_sha256,
            "member_id": self.member_id,
            "nomination_event_id": self.nomination_event_id,
            "provider_calls": self.provider_calls,
            "raw_events_sha256": self.raw_events_sha256,
            "receipt_sha256": self.receipt_sha256,
            "received_bytes": self.received_bytes,
            "sell_attempts": self.sell_attempts,
            "sell_not_attempted": self.sell_not_attempted,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "stored_bytes": self.stored_bytes,
            "terminal_counts": dict(sorted(self.terminal_counts.items())),
            "triggered_at": self.triggered_at,
            "window_id": self.window_id,
        }


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Task21MultiHorizonError("json_canonicalization_failed") from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21MultiHorizonError("config_root_invalid")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21MultiHorizonError("json_root_invalid")
    return value


def _utc_datetime(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21MultiHorizonError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21MultiHorizonError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21MultiHorizonError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _enum_text(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raise Task21MultiHorizonError("enum_text_invalid")
    return raw


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Task21MultiHorizonError("immutable_output_already_exists") from exc


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("stage_id") != "H0_ADMISSION_AND_CAPTURE"
        or config.get("status")
        != "FROZEN_FOR_EXACT_USER_AUTHORIZED_H0_EXECUTION"
    ):
        raise Task21MultiHorizonError("config_identity_or_status_drift")
    frozen = config.get("protected_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise Task21MultiHorizonError("protected_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping):
            raise Task21MultiHorizonError("protected_input_invalid")
        relative = item.get("path")
        expected = item.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise Task21MultiHorizonError("protected_input_identity_invalid")
        path = repo_root / relative
        if not path.is_file():
            raise Task21MultiHorizonError(
                f"protected_input_missing:{relative}"
            )
        if sha256_file(path) != expected:
            raise Task21MultiHorizonError(
                f"protected_input_hash_drift:{relative}"
            )
        if "bytes" in item and path.stat().st_size != item["bytes"]:
            raise Task21MultiHorizonError(
                f"protected_input_byte_drift:{relative}"
            )
    admission = config.get("admission")
    provider = config.get("provider")
    h0 = config.get("h0")
    recovery = config.get("recovery")
    authority = config.get("authority")
    later = config.get("later_horizons")
    if not all(
        isinstance(item, Mapping)
        for item in (admission, provider, h0, recovery, authority, later)
    ):
        raise Task21MultiHorizonError("config_section_missing")
    if (
        admission.get("source") != "EXACT_FROZEN_T1_REPLAY_ONLY"
        or admission.get("frozen_nomination_count") != 3
        or admission.get("candidate_admissions_max") != 3
        or admission.get("outcome_or_route_input_allowed") is not False
        or admission.get("original_future_close_used_as_entered_at") is not False
    ):
        raise Task21MultiHorizonError("admission_boundary_drift")
    if (
        provider.get("base_url") != "https://api.jup.ag"
        or provider.get("path") != "/swap/v1/quote"
        or provider.get("method") != "GET"
        or provider.get("keyless") is not True
        or provider.get("credentials") != 0
        or provider.get("accounts") != 0
        or provider.get("fallback_provider") is not None
        or provider.get("minimum_interval_seconds") != MINIMUM_INTERVAL_SECONDS
        or provider.get("retries") != 0
        or provider.get("concurrency") != 1
    ):
        raise Task21MultiHorizonError("provider_boundary_drift")
    expected_h0 = {
        "panels_max": 3,
        "provider_calls_per_panel_max": PROVIDER_CALLS_PER_PANEL_MAX,
        "provider_calls_total_max": PROVIDER_CALLS_TOTAL_MAX,
        "modeled_provider_credits_max": PROVIDER_CALLS_TOTAL_MAX,
        "wall_seconds_max": WALL_SECONDS_MAX,
        "received_response_bytes_max": RECEIVED_BYTES_TOTAL_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_TOTAL_MAX,
        "local_output_root": OUTPUT_RELATIVE_ROOT,
    }
    if any(h0.get(key) != value for key, value in expected_h0.items()):
        raise Task21MultiHorizonError("h0_cap_drift")
    if (
        recovery.get("required_health") != "HEALTHY"
        or recovery.get("backup_age_hours_max_at_start") != 24
        or recovery.get("restore_age_hours_max_at_start") != 168
        or recovery.get("drive_actions_in_h0") != 0
    ):
        raise Task21MultiHorizonError("recovery_boundary_drift")
    if (
        later.get("scheduler_or_background_process") is not False
        or later.get("foreground_only") is not True
        or later.get("missed_window_policy")
        != "RETAIN_EXPLICIT_GAP_NO_BACKFILL"
        or later["h1"].get("offset_seconds") != 3600
        or later["h1"].get("grace_seconds") != 600
        or later["h1"].get("authority_granted_by_h0") is not False
    ):
        raise Task21MultiHorizonError("later_horizon_boundary_drift")
    if (
        authority.get("exact_phrase") != ATOM_ID
        or authority.get("stage") != "H0_ONLY"
        or authority.get("candidate_admissions_max") != 3
        or authority.get("provider_api_rpc_wss_calls_max")
        != PROVIDER_CALLS_TOTAL_MAX
        or authority.get("drive_reads") != 0
        or authority.get("drive_writes") != 0
        or authority.get("credential_use") != 0
        or authority.get("cash_spend_usd_cents") != 0
        or authority.get("scheduler_or_background_process") is not False
        or authority.get("wallet_signer_transaction_actions") != 0
    ):
        raise Task21MultiHorizonError("authority_boundary_drift")


def _preflight_disk(repo_root: Path, available_disk_bytes: int | None) -> None:
    free = (
        shutil.disk_usage(repo_root).free
        if available_disk_bytes is None
        else available_disk_bytes
    )
    limits = SupervisorLimits(
        predicted_child_write_bytes_max=DURABLE_BYTES_TOTAL_MAX,
        start_reserve_fixed_bytes=536_870_912,
        runtime_reserve_fixed_bytes=268_435_456,
    )
    limits.validate()
    if (
        isinstance(free, bool)
        or not isinstance(free, int)
        or free < MIN_FREE_SPACE_AFTER_WRITE + limits.start_required_bytes
    ):
        raise Task21MultiHorizonError("disk_pressure_blocks_h0_capture")


def _protected_path(config: Mapping[str, Any], role: str) -> str:
    for item in config["protected_inputs"]:
        if item["role"] == role:
            return item["path"]
    raise Task21MultiHorizonError(f"protected_role_missing:{role}")


def build_admissions(
    *,
    repo_root: Path,
    config: Mapping[str, Any],
    admitted_at: datetime,
) -> tuple[list[dict[str, Any]], dict[str, JsonValue]]:
    """Evaluate and admit only the frozen T1 set before any quote is observed."""

    if admitted_at.tzinfo is None or admitted_at.utcoffset() is None:
        raise Task21MultiHorizonError("admitted_at_must_be_timezone_aware")
    replay = _load_json(
        repo_root / _protected_path(config, "FROZEN_T1_REPLAY")
    )
    events = replay.get("nomination_events")
    if not isinstance(events, list) or len(events) != 3:
        raise Task21MultiHorizonError("frozen_nomination_count_drift")
    expected_order = sorted(
        events,
        key=lambda event: (
            _utc_datetime(
                "first_reliable_available_at",
                event.get("first_reliable_available_at"),
            ),
            _utc_datetime("observed_at", event.get("observed_at")),
            event.get("nomination_event_id"),
        ),
    )
    if events != expected_order:
        raise Task21MultiHorizonError("frozen_nomination_order_drift")
    for event in events:
        inputs = event.get("exact_rule_input_values")
        if (
            not isinstance(inputs, Mapping)
            or inputs.get("tranche_id") != "T1"
            or inputs.get("prior_relevant_quote_outcome_exposure") is not False
            or inputs.get("uses_task21_quote_route_or_price_outcome") is not False
        ):
            raise Task21MultiHorizonError("frozen_nomination_scope_drift")

    anchor = _utc_datetime(
        "original_t1_anchor_at", config["admission"]["original_t1_anchor_at"]
    )
    batch = {
        "schema": "smial.task21.real-nomination-policy-offline-batch",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": NOMINATION_ATOM_ID,
        "synthetic_only": True,
        "contains_market_data": False,
        "hypothesis_outcome_unsealed": False,
        "anchor_at": _utc_text(anchor),
        "tranche_closed_at": {
            "T1": _utc_text(anchor + timedelta(days=7)),
            "T2": _utc_text(anchor + timedelta(days=14)),
            "T3": _utc_text(anchor + timedelta(days=21)),
        },
        "nomination_events": events,
    }
    evaluation = evaluate_offline_batch(
        repo_root=repo_root,
        config_path=repo_root / _protected_path(config, "REAL_NOMINATION_POLICY"),
        batch_path=(
            repo_root
            / "tests/fixtures/task21/real_nomination_policy_offline_batch_v1.json"
        ),
        batch_override=batch,
    ).receipt
    memberships = evaluation["membership_events"]
    if (
        evaluation["evaluated_nominations"] != 3
        or len(memberships) != 3
        or evaluation["state_counts"] != {"WATCHLIST_ACTIVE": 3}
    ):
        raise Task21MultiHorizonError("frozen_t1_not_exactly_three_admissible")
    by_nomination = {
        event["nomination_event_id"]: event for event in events
    }
    admitted: list[dict[str, Any]] = []
    for member in memberships:
        event = by_nomination[member["nomination_event_id"]]
        admitted.append(
            {
                **member,
                "entered_at": _utc_text(admitted_at),
                "first_reliable_available_at": event[
                    "first_reliable_available_at"
                ],
                "reason_codes": [
                    "POLICY_ELIGIBLE_PREOUTCOME_NOMINATION",
                    "T1_EARLY_CAPACITY_CLOSE_FORWARD_ONLY_OVERLAY",
                ],
            }
        )
    admission_receipt: dict[str, JsonValue] = {
        "schema": "smial.task21.real-t1-admission-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS",
        "admitted_at": _utc_text(admitted_at),
        "evaluated_nominations": 3,
        "real_candidate_admissions": 3,
        "member_ids": [item["member_id"] for item in admitted],
        "nomination_event_ids": [
            item["nomination_event_id"] for item in admitted
        ],
        "ordering": list(config["admission"]["order"]),
        "outcome_or_route_input_used": False,
        "original_future_close_used_as_entered_at": False,
        "provider_calls_before_admission_persisted": 0,
    }
    return admitted, admission_receipt


def _projection_envelope(
    projection: QuoteProjection,
    *,
    member: Mapping[str, Any],
    window_id: str,
    call_ordinal: int,
) -> dict[str, JsonValue]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "hypothesis_version_id": member["hypothesis_version_id"],
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "horizon_id": "H0",
        "window_id": window_id,
        "call_ordinal": call_ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": _utc_text(quote.requested_at),
        "response_at": (
            None if quote.response_at is None else _utc_text(quote.response_at)
        ),
        "first_reliable_available_at": _utc_text(
            quote.first_reliable_available_at
        ),
        "available_to_strategy_at": _utc_text(
            quote.available_to_strategy_at
        ),
        "ingested_at": _utc_text(quote.ingested_at),
        "latency_ms": quote.provider_latency_ms,
        "response_status": _enum_text(raw.response_status),
        "terminal_class": _enum_text(quote.status),
        "error_class": quote.error_class,
        "route_id": quote.route_id,
        "route_count": quote.route_count,
        "context_slot": quote.context_slot,
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def _persist_window(
    *,
    run_root: Path,
    config_sha256: str,
    member: Mapping[str, Any],
    triggered_at: str,
    projections: list[QuoteProjection],
    provider_calls: int,
    received_bytes: int,
    buy_attempts: int,
    sell_attempts: int,
    sell_not_attempted: int,
    terminal_counts: Counter[str],
    stop_reason: str | None,
) -> H0WindowSummary:
    if not projections:
        raise Task21MultiHorizonError("h0_window_has_no_raw_evidence")
    member_id = member["member_id"]
    window_id = f"{member_id}-H0"
    window_root = run_root / f"member={member_id}" / "horizon=H0"
    if window_root.exists():
        raise Task21MultiHorizonError("h0_window_output_already_exists")
    envelopes = [
        _projection_envelope(
            projection,
            member=member,
            window_id=window_id,
            call_ordinal=index,
        )
        for index, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        canonical_json_bytes(envelope) + b"\n" for envelope in envelopes
    )
    raw_path = window_root / "raw_events.jsonl"
    _write_new(raw_path, raw_bytes)
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "config_sha256": config_sha256,
        "horizon_id": "H0",
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "triggered_at": triggered_at,
        "files": [
            {
                "bytes": len(raw_bytes),
                "logical_path": "raw_events.jsonl",
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
        "horizon_id": "H0",
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "provider_calls": provider_calls,
        "modeled_provider_credits": provider_calls,
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "received_bytes": received_bytes,
        "buy_attempts": buy_attempts,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "raw_events_sha256": sha256_bytes(raw_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, receipt_bytes)
    stored_bytes = sum(
        path.stat().st_size for path in window_root.rglob("*") if path.is_file()
    )
    if stored_bytes > 5_242_880:
        raise Task21MultiHorizonError("h0_window_durable_byte_cap_exhausted")
    if sha256_file(raw_path) != manifest["files"][0]["sha256"]:
        raise Task21MultiHorizonError("h0_raw_readback_hash_mismatch")
    if sha256_file(manifest_path) != receipt["manifest_sha256"]:
        raise Task21MultiHorizonError("h0_manifest_readback_hash_mismatch")
    return H0WindowSummary(
        member_id=member_id,
        nomination_event_id=member["nomination_event_id"],
        window_id=window_id,
        triggered_at=triggered_at,
        status=receipt["status"],
        stop_reason=stop_reason,
        provider_calls=provider_calls,
        received_bytes=received_bytes,
        buy_attempts=buy_attempts,
        sell_attempts=sell_attempts,
        sell_not_attempted=sell_not_attempted,
        terminal_counts=dict(terminal_counts),
        stored_bytes=stored_bytes,
        raw_events_sha256=sha256_file(raw_path),
        manifest_sha256=sha256_file(manifest_path),
        receipt_sha256=sha256_file(receipt_path),
    )


def _run_member_h0(
    *,
    run_root: Path,
    config_sha256: str,
    member: Mapping[str, Any],
    transport: Any,
    clock: Callable[[], float],
    now: Callable[[], datetime],
) -> H0WindowSummary:
    started = clock()
    triggered_at = _utc_text(now())
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    requests = build_buy_panel_requests(
        selected_output_mint=member["mint"],
        output_decimals=member["mint_decimals"],
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
    )
    for panel_index, buy_request in enumerate(requests):
        if clock() - started >= WALL_SECONDS_MAX:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(
            buy_request, capture.observation
        )
        projections.append(buy_projection)
        terminal_counts[_enum_text(buy_projection.quote_attempt.status)] += 1
        stop_reason = capture.transport_stop_reason or buy_projection.stop_reason
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(
            buy_projection,
            attempt_ordinal=5 + panel_index,
        )
        if sell.request is None:
            sell_not_attempted += 1
            continue
        capture = transport.execute(sell.request)
        sell_attempts += 1
        sell_projection = project_quote_observation(
            sell.request, capture.observation
        )
        projections.append(sell_projection)
        terminal_counts[_enum_text(sell_projection.quote_attempt.status)] += 1
        stop_reason = capture.transport_stop_reason or sell_projection.stop_reason
        if stop_reason is not None:
            break
    if transport.attempts > PROVIDER_CALLS_PER_PANEL_MAX:
        raise Task21MultiHorizonError("h0_panel_provider_call_cap_exceeded")
    return _persist_window(
        run_root=run_root,
        config_sha256=config_sha256,
        member=member,
        triggered_at=triggered_at,
        projections=projections,
        provider_calls=transport.attempts,
        received_bytes=transport.received_bytes,
        buy_attempts=buy_attempts,
        sell_attempts=sell_attempts,
        sell_not_attempted=sell_not_attempted,
        terminal_counts=terminal_counts,
        stop_reason=stop_reason,
    )


def _file_inventory(root: Path) -> list[dict[str, JsonValue]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def run_h0_capture(
    *,
    gate: Task21H0ExecutionGate,
    repo_root: Path,
    config_path: Path,
    recovery_receipt_path: Path,
    transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, JsonValue]:
    """Admit the exact T1 set and execute no more than three H0 panels."""

    if not isinstance(gate, Task21H0ExecutionGate):
        raise Task21MultiHorizonAuthorityRequired(
            "task21_h0_external_execution_gate_required"
        )
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    started_at = now()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise Task21MultiHorizonError("runtime_now_must_be_timezone_aware")
    started_at = started_at.astimezone(UTC)
    recovery = _load_json(recovery_receipt_path)
    try:
        validate_recovery_freshness(recovery, now=started_at)
    except Task21LiveShakedownError as exc:
        raise Task21MultiHorizonError(str(exc)) from exc
    _preflight_disk(repo_root, available_disk_bytes)
    if output_root_override is not None and transport_factory is None:
        raise Task21MultiHorizonError(
            "output_override_requires_injected_transport"
        )
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else (repo_root / OUTPUT_RELATIVE_ROOT).resolve()
    )
    config_sha256 = sha256_file(config_path)
    run_claim = {
        "admitted_at": _utc_text(started_at),
        "atom_id": ATOM_ID,
        "config_sha256": config_sha256,
        "replay_sha256": next(
            item["sha256"]
            for item in config["protected_inputs"]
            if item["role"] == "FROZEN_T1_REPLAY"
        ),
    }
    run_id = (
        "h0-"
        + started_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(run_claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21MultiHorizonError("h0_run_output_already_exists")

    admissions, admission_receipt = build_admissions(
        repo_root=repo_root,
        config=config,
        admitted_at=started_at,
    )
    admission_bytes = b"".join(
        canonical_json_bytes(member) + b"\n" for member in admissions
    )
    admission_path = run_root / "admission_events.jsonl"
    _write_new(admission_path, admission_bytes)
    admission_receipt_bytes = canonical_json_bytes(admission_receipt) + b"\n"
    admission_receipt_path = run_root / "admission_receipt.json"
    _write_new(admission_receipt_path, admission_receipt_bytes)

    summaries: list[H0WindowSummary] = []
    started_monotonic = clock()
    for index, member in enumerate(admissions):
        if index > 0:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started_monotonic >= WALL_SECONDS_MAX:
            break
        transport = (
            transport_factory(member)
            if transport_factory is not None
            else BoundedQuoteTransport(
                gate=Task10TransportGate(TASK10_TRANSPORT_AUTHORITY)
            )
        )
        summary = _run_member_h0(
            run_root=run_root,
            config_sha256=config_sha256,
            member=member,
            transport=transport,
            clock=clock,
            now=now,
        )
        summaries.append(summary)
        if summary.status != "COMPLETE":
            break

    provider_calls = sum(item.provider_calls for item in summaries)
    received_bytes = sum(item.received_bytes for item in summaries)
    if provider_calls > PROVIDER_CALLS_TOTAL_MAX:
        raise Task21MultiHorizonError("h0_total_provider_call_cap_exceeded")
    if received_bytes > RECEIVED_BYTES_TOTAL_MAX:
        raise Task21MultiHorizonError("h0_total_received_byte_cap_exceeded")

    completed = len(summaries) == 3 and all(
        item.status == "COMPLETE" for item in summaries
    )
    missing_members = [
        member["member_id"]
        for member in admissions
        if member["member_id"]
        not in {summary.member_id for summary in summaries}
    ]
    if completed:
        latest_h0 = max(
            _utc_datetime("triggered_at", item.triggered_at)
            for item in summaries
        )
        h1_earliest = latest_h0 + H1_OFFSET
        next_boundary: dict[str, JsonValue] = {
            "atom_id": "T21-A6S_H1_FOREGROUND_CAPTURE_V1",
            "status": "ACTIVE_WAITING_NOT_AUTHORIZED",
            "earliest_at": _utc_text(h1_earliest),
            "latest_at": _utc_text(h1_earliest + H1_GRACE),
            "calendar_wait_required": True,
            "provider_api_rpc_wss_calls_authorized": False,
            "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        }
        backup_due_at: str | None = _utc_text(
            latest_h0 + BACKUP_MAX_AGE_FROM_H0
        )
    else:
        next_boundary = {
            "atom_id": "T21-A6S_H0_INCOMPLETE_REVIEW_V1",
            "status": "STOPPED_NO_BACKFILL",
            "calendar_wait_required": False,
            "provider_api_rpc_wss_calls_authorized": False,
            "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        }
        backup_due_at = (
            None
            if not summaries
            else _utc_text(
                max(
                    _utc_datetime("triggered_at", item.triggered_at)
                    for item in summaries
                )
                + BACKUP_MAX_AGE_FROM_H0
            )
        )

    runtime_receipt = {
        "schema": "smial.task21.h0-admission-capture-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "PASS" if completed else "STOPPED",
        "started_at": _utc_text(started_at),
        "admission": {
            "evaluated_nominations": 3,
            "real_candidate_admissions": len(admissions),
            "member_ids": [item["member_id"] for item in admissions],
            "admission_events_sha256": sha256_file(admission_path),
            "admission_receipt_sha256": sha256_file(admission_receipt_path),
            "persisted_before_first_provider_call": True,
            "outcome_or_route_input_used": False,
        },
        "h0": {
            "panels_complete": sum(
                item.status == "COMPLETE" for item in summaries
            ),
            "panels_stopped": sum(
                item.status != "COMPLETE" for item in summaries
            ),
            "missing_member_ids": missing_members,
            "windows": [item.safe_receipt() for item in summaries],
        },
        "actual_actions": {
            "provider_api_rpc_wss_calls": provider_calls,
            "modeled_provider_credits": provider_calls,
            "provider_billed_credit_claim": (
                "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT"
            ),
            "received_bytes": received_bytes,
            "real_candidate_admissions": len(admissions),
            "local_live_windows": len(summaries),
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "backup": {
            "status": "PENDING_WITHIN_RECOVERY_WINDOW",
            "destination_folder_id": config["recovery"]["backup_destination"][
                "folder_id"
            ],
            "due_at": backup_due_at,
            "performed_in_h0": False,
        },
        "outcome_blindness": {
            "hypothesis_outcome_unsealed": False,
            "cost_curve_or_token_rank_in_sanitized_receipt": False,
            "tuning_during_capture": False,
        },
        "next_boundary": next_boundary,
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_MARKET_WIDE_GENERALIZATION",
            "NO_LATER_HORIZON_EXECUTED",
            "NO_DRIVE_BACKUP_PERFORMED_IN_H0",
            "NO_A7_CATALOG_TRANSACTION",
        ],
    }
    runtime_receipt_bytes = canonical_json_bytes(runtime_receipt) + b"\n"
    local_runtime_receipt_path = run_root / "runtime_receipt.json"
    _write_new(local_runtime_receipt_path, runtime_receipt_bytes)
    stored_bytes = sum(
        path.stat().st_size for path in run_root.rglob("*") if path.is_file()
    )
    if stored_bytes > DURABLE_BYTES_TOTAL_MAX:
        raise Task21MultiHorizonError("h0_total_durable_byte_cap_exceeded")
    evidence_root = (
        run_root.relative_to(repo_root).as_posix()
        if output_root_override is None
        else f"TEST_OUTPUT_ROOT/run={run_id}"
    )
    runtime_receipt["local_evidence"] = {
        "root": evidence_root,
        "stored_bytes": stored_bytes,
        "runtime_receipt_sha256": sha256_file(local_runtime_receipt_path),
        "files": _file_inventory(run_root),
        "tracked_in_git": False,
    }
    return runtime_receipt
