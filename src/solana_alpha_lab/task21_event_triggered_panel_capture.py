"""Reusable create-only quote-panel writer for TASK-21 event batches."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import HttpCapture
from solana_alpha_lab.task21_multi_horizon_capture import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


class EventPanelCaptureError(RuntimeError):
    """A panel cannot be persisted inside its bounded contract."""


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EventPanelCaptureError("panel_datetime_must_be_timezone_aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise EventPanelCaptureError("panel_create_only_collision") from exc


def _enum(value: object) -> str:
    return str(getattr(value, "value", value))


def _projection_envelope(
    projection: QuoteProjection,
    *,
    task_id: str,
    atom_id: str,
    batch_id: str,
    panel_id: str,
    hypothesis_version_id: str,
    member: Mapping[str, Any],
    window_id: str,
    ordinal: int,
) -> dict[str, Any]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": "1.0",
        "task_id": task_id,
        "atom_id": atom_id,
        "hypothesis_version_id": hypothesis_version_id,
        "batch_id": batch_id,
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "horizon_id": panel_id,
        "window_id": window_id,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": utc_text(quote.requested_at),
        "response_at": (
            None if quote.response_at is None else utc_text(quote.response_at)
        ),
        "first_reliable_available_at": utc_text(
            quote.first_reliable_available_at
        ),
        "available_to_strategy_at": utc_text(quote.available_to_strategy_at),
        "ingested_at": utc_text(quote.ingested_at),
        "latency_ms": quote.provider_latency_ms,
        "response_status": _enum(raw.response_status),
        "terminal_class": _enum(quote.status),
        "error_class": quote.error_class,
        "route_id": quote.route_id,
        "route_count": quote.route_count,
        "context_slot": quote.context_slot,
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def capture_quote_panel(
    *,
    run_root: Path,
    task_id: str,
    atom_id: str,
    batch_id: str,
    panel_id: str,
    hypothesis_version_id: str,
    config_hash: str,
    member: Mapping[str, Any],
    transport: Any,
    now: Callable[[], datetime],
    clock: Callable[[], float],
    wall_seconds_max: int,
    durable_bytes_max: int,
    provider_calls_max: int = 8,
) -> dict[str, Any]:
    """Capture one deterministic four-notional buy/dependent-sell panel."""

    if member.get("batch_id") != batch_id:
        raise EventPanelCaptureError("panel_member_batch_drift")
    if not isinstance(member.get("mint_decimals"), int):
        raise EventPanelCaptureError("panel_member_decimals_invalid")
    started = clock()
    triggered_at = utc_text(now())
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
        if clock() - started >= wall_seconds_max:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        buy_capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(
            buy_request, buy_capture.observation
        )
        projections.append(buy_projection)
        terminal_counts[_enum(buy_projection.quote_attempt.status)] += 1
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
        terminal_counts[_enum(sell_projection.quote_attempt.status)] += 1
        stop_reason = sell_capture.transport_stop_reason or sell_projection.stop_reason
        if stop_reason is not None:
            break
    if transport.attempts > provider_calls_max:
        raise EventPanelCaptureError("panel_provider_call_cap_exceeded")
    if not projections:
        raise EventPanelCaptureError("panel_has_no_evidence")

    member_id = member["member_id"]
    window_id = f"{member_id}-{panel_id}"
    window_root = run_root / f"member={member_id}" / f"horizon={panel_id}"
    envelopes = [
        _projection_envelope(
            projection,
            task_id=task_id,
            atom_id=atom_id,
            batch_id=batch_id,
            panel_id=panel_id,
            hypothesis_version_id=hypothesis_version_id,
            member=member,
            window_id=window_id,
            ordinal=ordinal,
        )
        for ordinal, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in envelopes
    )
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": "1.0",
        "task_id": task_id,
        "atom_id": atom_id,
        "batch_id": batch_id,
        "horizon_id": panel_id,
        "config_sha256": config_hash,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
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
    receipt = {
        "schema": "smial.task21.forward-quote-panel-receipt",
        "schema_version": "1.0",
        "task_id": task_id,
        "atom_id": atom_id,
        "batch_id": batch_id,
        "horizon_id": panel_id,
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "completed_at": utc_text(now()),
        "provider_calls": transport.attempts,
        "modeled_provider_credits": transport.attempts,
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "received_bytes": transport.received_bytes,
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
    if (
        directory_bytes(run_root)
        + len(raw_bytes)
        + len(manifest_bytes)
        + len(receipt_bytes)
        > durable_bytes_max
    ):
        raise EventPanelCaptureError("panel_durable_byte_cap_would_be_exceeded")
    write_new(window_root / "raw_events.jsonl", raw_bytes)
    write_new(window_root / "manifest.json", manifest_bytes)
    receipt_path = window_root / "receipt.json"
    write_new(receipt_path, receipt_bytes)
    return {
        **receipt,
        "stored_bytes": directory_bytes(window_root),
        "receipt_sha256": sha256_file(receipt_path),
    }
