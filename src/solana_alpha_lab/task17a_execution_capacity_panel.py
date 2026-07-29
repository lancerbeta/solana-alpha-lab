"""Bounded TASK-17A quote panel built on the accepted TASK-10 transport."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    USDC_MINT,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as TASK10_TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate,
    HttpCapture,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

CONTRACT_SHA256 = (
    "ac7a191f4a5888681fa2b90ea33261271d0d7d4a44c81653dbfc6d902fa6871f"
)
EXTERNAL_AUTHORITY_PHRASE = "T17A-A3_BOUNDED_EXTERNAL_QUOTE_PANEL_V1"
LOGICAL_ROOT = "task17a_execution_capacity_quote_panel_v1"
WINDOW_IDS = (
    "T17A-WINDOW-01",
    "T17A-WINDOW-02",
    "T17A-WINDOW-03",
)
MINIMUM_WINDOW_SEPARATION_SECONDS = 1800
WINDOW_SEPARATION_SAFETY_MARGIN_SECONDS = 1
TOTAL_SPAN_SECONDS_MAX = 86400
WINDOW_WALL_SECONDS_MAX = 300
PROVIDER_CALLS_PER_WINDOW_MAX = 8
PROVIDER_CALLS_TOTAL_MAX = 24
DURABLE_BYTES_PER_WINDOW_MAX = 5_242_880
DURABLE_BYTES_TOTAL_MAX = 15_728_640
MEMBER_ID = "HYP-WATCH-MEMBER-T10-001"
HYPOTHESIS_VERSION_ID = "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"
WATCHLIST_ID = "HYP-WATCHLIST-EXECUTION-CAPACITY-V1"
WATCHLIST_VERSION = "1.0"
SELECTED_MINT = "4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump"
SELECTED_MINT_DECIMALS = 6


class Task17APanelError(RuntimeError):
    """The bounded panel cannot proceed under its frozen contract."""


@dataclass(frozen=True, slots=True)
class Task17AExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise Task17APanelError("external_authority_phrase_mismatch")


@dataclass(frozen=True, slots=True)
class WindowSummary:
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
            "accounts_used": 0,
            "api_keys_used": 0,
            "buy_attempts": self.buy_attempts,
            "cash_spend_usd_cents": 0,
            "manifest_sha256": self.manifest_sha256,
            "provider_calls": self.provider_calls,
            "provider_credits_billed_claim": "NOT_AVAILABLE_KEYLESS",
            "raw_events_sha256": self.raw_events_sha256,
            "received_bytes": self.received_bytes,
            "receipt_sha256": self.receipt_sha256,
            "retries": 0,
            "sell_attempts": self.sell_attempts,
            "sell_not_attempted": self.sell_not_attempted,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "stored_bytes": self.stored_bytes,
            "terminal_counts": dict(sorted(self.terminal_counts.items())),
            "triggered_at": self.triggered_at,
            "wallet_signer_transaction_actions": 0,
            "window_id": self.window_id,
        }


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Task17APanelError("json_canonicalization_failed") from exc


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Task17APanelError("immutable_output_already_exists") from exc


def load_frozen_contract(path: Path) -> Mapping[str, Any]:
    payload = path.read_bytes()
    if _sha256_bytes(payload) != CONTRACT_SHA256:
        raise Task17APanelError("frozen_contract_hash_mismatch")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise Task17APanelError("frozen_contract_json_invalid") from exc
    if not isinstance(document, Mapping):
        raise Task17APanelError("frozen_contract_root_invalid")
    if (
        document.get("schema")
        != "solana_alpha_lab.bounded_execution_capacity_quote_panel_contract"
        or document.get("schema_version") != "1.0"
        or document.get("task_id") != "TASK-17A"
        or document.get("atom_id") != "T17A-A2_FROZEN_CAPTURE_CONTRACT_V1"
        or document.get("status") != "FROZEN_OFFLINE_CONTRACT"
    ):
        raise Task17APanelError("frozen_contract_identity_drift")
    if document.get("trigger_windows", {}).get("window_ids") != list(WINDOW_IDS):
        raise Task17APanelError("window_set_drift")
    if document.get("caps", {}).get("provider_calls_current_max") != 24:
        raise Task17APanelError("provider_call_cap_drift")
    if document.get("provider_surface", {}).get("credentials") != 0:
        raise Task17APanelError("credential_scope_drift")
    if document.get("authority", {}).get("next_external_atom") != (
        EXTERNAL_AUTHORITY_PHRASE
    ):
        raise Task17APanelError("external_atom_identity_drift")
    return document


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _enum_text(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raise Task17APanelError("enum_text_invalid")
    return raw


def _projection_envelope(
    projection: QuoteProjection,
    *,
    window_id: str,
    call_ordinal: int,
) -> dict[str, JsonValue]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    return {
        "schema": "solana_alpha_lab.task17a_quote_panel_raw",
        "schema_version": "1.0",
        "hypothesis_version_id": HYPOTHESIS_VERSION_ID,
        "watchlist_id": WATCHLIST_ID,
        "watchlist_version": WATCHLIST_VERSION,
        "window_id": window_id,
        "member_id": MEMBER_ID,
        "call_ordinal": call_ordinal,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "endpoint_version": PROVIDER_VERSION,
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
    raw_root: Path,
    window_id: str,
    triggered_at: str,
    projections: list[QuoteProjection],
    provider_calls: int,
    received_bytes: int,
    buy_attempts: int,
    sell_attempts: int,
    sell_not_attempted: int,
    terminal_counts: Counter[str],
    stop_reason: str | None,
    logical_root: str = LOGICAL_ROOT,
) -> WindowSummary:
    if not projections:
        raise Task17APanelError("window_has_no_raw_evidence")
    window_root = raw_root / logical_root / f"window={window_id}"
    if window_root.exists():
        raise Task17APanelError("window_output_already_exists")
    envelopes = [
        _projection_envelope(
            projection,
            window_id=window_id,
            call_ordinal=index,
        )
        for index, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        _canonical_json_bytes(envelope) + b"\n" for envelope in envelopes
    )
    raw_path = window_root / "raw_events.jsonl"
    _write_new(raw_path, raw_bytes)
    manifest = {
        "schema": "solana_alpha_lab.task17a_quote_panel_manifest",
        "schema_version": "1.0",
        "contract_sha256": CONTRACT_SHA256,
        "files": [
            {
                "bytes": len(raw_bytes),
                "logical_path": "raw_events.jsonl",
                "sha256": _sha256_bytes(raw_bytes),
            }
        ],
        "hypothesis_version_id": HYPOTHESIS_VERSION_ID,
        "member_id": MEMBER_ID,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "triggered_at": triggered_at,
        "watchlist_id": WATCHLIST_ID,
        "watchlist_version": WATCHLIST_VERSION,
        "window_id": window_id,
    }
    manifest_bytes = _canonical_json_bytes(manifest) + b"\n"
    manifest_path = window_root / "manifest.json"
    _write_new(manifest_path, manifest_bytes)
    provisional_receipt = {
        "schema": "solana_alpha_lab.task17a_quote_panel_receipt",
        "schema_version": "1.0",
        "accounts_used": 0,
        "api_keys_used": 0,
        "buy_attempts": buy_attempts,
        "cash_spend_usd_cents": 0,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "provider_calls": provider_calls,
        "provider_credits_billed_claim": "NOT_AVAILABLE_KEYLESS",
        "raw_events_sha256": _sha256_bytes(raw_bytes),
        "received_bytes": received_bytes,
        "retries": 0,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "triggered_at": triggered_at,
        "wallet_signer_transaction_actions": 0,
        "window_id": window_id,
    }
    receipt_bytes = _canonical_json_bytes(provisional_receipt) + b"\n"
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, receipt_bytes)
    stored_bytes = sum(
        path.stat().st_size for path in window_root.rglob("*") if path.is_file()
    )
    if stored_bytes > DURABLE_BYTES_PER_WINDOW_MAX:
        raise Task17APanelError("durable_window_byte_cap_exhausted")
    if _sha256_file(raw_path) != manifest["files"][0]["sha256"]:
        raise Task17APanelError("raw_readback_hash_mismatch")
    if _sha256_file(manifest_path) != provisional_receipt["manifest_sha256"]:
        raise Task17APanelError("manifest_readback_hash_mismatch")
    return WindowSummary(
        window_id=window_id,
        triggered_at=triggered_at,
        status=provisional_receipt["status"],
        stop_reason=stop_reason,
        provider_calls=provider_calls,
        received_bytes=received_bytes,
        buy_attempts=buy_attempts,
        sell_attempts=sell_attempts,
        sell_not_attempted=sell_not_attempted,
        terminal_counts=dict(terminal_counts),
        stored_bytes=stored_bytes,
        raw_events_sha256=_sha256_file(raw_path),
        manifest_sha256=_sha256_file(manifest_path),
        receipt_sha256=_sha256_file(receipt_path),
    )


def run_window(
    *,
    raw_root: Path,
    window_id: str,
    transport: Any,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    logical_root: str = LOGICAL_ROOT,
) -> WindowSummary:
    started = clock()
    triggered_at = _utc_text(now())
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    requests = build_buy_panel_requests(
        selected_output_mint=SELECTED_MINT,
        output_decimals=SELECTED_MINT_DECIMALS,
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
    )
    for panel_index, buy_request in enumerate(requests):
        if clock() - started >= WINDOW_WALL_SECONDS_MAX:
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
    if transport.attempts > PROVIDER_CALLS_PER_WINDOW_MAX:
        raise Task17APanelError("provider_call_window_cap_exceeded")
    return _persist_window(
        raw_root=raw_root,
        window_id=window_id,
        triggered_at=triggered_at,
        projections=projections,
        provider_calls=transport.attempts,
        received_bytes=transport.received_bytes,
        buy_attempts=buy_attempts,
        sell_attempts=sell_attempts,
        sell_not_attempted=sell_not_attempted,
        terminal_counts=terminal_counts,
        stop_reason=stop_reason,
        logical_root=logical_root,
    )


def run_panel(
    *,
    gate: Task17AExecutionGate,
    raw_root: Path,
    contract_path: Path,
    transport_factory: Callable[[], Any] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    emit: Callable[[str], None] = print,
) -> dict[str, JsonValue]:
    if not isinstance(gate, Task17AExecutionGate):
        raise Task17APanelError("task17a_external_execution_gate_required")
    load_frozen_contract(contract_path)
    if not raw_root.is_absolute():
        raise Task17APanelError("raw_root_must_be_absolute")
    panel_root = raw_root / LOGICAL_ROOT
    if panel_root.exists():
        raise Task17APanelError("panel_output_already_exists")
    started = clock()
    previous_window_started: float | None = None
    summaries: list[WindowSummary] = []
    for window_id in WINDOW_IDS:
        if previous_window_started is not None:
            while (
                clock() - previous_window_started
                < MINIMUM_WINDOW_SEPARATION_SECONDS
                + WINDOW_SEPARATION_SAFETY_MARGIN_SECONDS
            ):
                remaining = (
                    MINIMUM_WINDOW_SEPARATION_SECONDS
                    + WINDOW_SEPARATION_SAFETY_MARGIN_SECONDS
                    - (clock() - previous_window_started)
                )
                wait = min(45.0, remaining)
                emit(
                    "TASK17A_WAIT "
                    f"next={window_id} remaining_seconds={int(remaining)}"
                )
                sleeper(wait)
        if clock() - started > TOTAL_SPAN_SECONDS_MAX:
            raise Task17APanelError("total_span_cap_exhausted")
        previous_window_started = clock()
        transport = (
            transport_factory()
            if transport_factory is not None
            else BoundedQuoteTransport(
                gate=ExternalExecutionGate(
                    authority_phrase=TASK10_TRANSPORT_AUTHORITY
                )
            )
        )
        emit(f"TASK17A_WINDOW_START window_id={window_id}")
        summary = run_window(
            raw_root=raw_root,
            window_id=window_id,
            transport=transport,
            clock=clock,
            now=now,
        )
        summaries.append(summary)
        emit(
            "TASK17A_WINDOW_COMPLETE "
            f"window_id={window_id} status={summary.status} "
            f"provider_calls={summary.provider_calls}"
        )
        if summary.stop_reason is not None:
            break
    total_calls = sum(item.provider_calls for item in summaries)
    total_stored = sum(item.stored_bytes for item in summaries)
    if total_calls > PROVIDER_CALLS_TOTAL_MAX:
        raise Task17APanelError("provider_call_total_cap_exceeded")
    if total_stored > DURABLE_BYTES_TOTAL_MAX:
        raise Task17APanelError("durable_total_byte_cap_exhausted")
    return {
        "accounts_used": 0,
        "api_keys_used": 0,
        "cash_spend_usd_cents": 0,
        "completed_windows": len(summaries),
        "foreground_control_plane_invocation": True,
        "provider_calls": total_calls,
        "provider_credits_billed_claim": "NOT_AVAILABLE_KEYLESS",
        "scheduler_or_background_process": False,
        "status": (
            "COMPLETE"
            if len(summaries) == len(WINDOW_IDS)
            and all(item.stop_reason is None for item in summaries)
            else "STOPPED"
        ),
        "stop_reason": next(
            (item.stop_reason for item in summaries if item.stop_reason),
            None,
        ),
        "stored_bytes": total_stored,
        "wallet_signer_transaction_actions": 0,
        "windows": [item.safe_receipt() for item in summaries],
    }
