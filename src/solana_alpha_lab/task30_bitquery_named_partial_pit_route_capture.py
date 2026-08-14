"""Bounded Bitquery capture primitives for TASK-30.

The module keeps policy validation, GraphQL construction, transport and slot
projection small enough to audit.  It deliberately has no retry, fallback,
credential persistence or automatic execution entry point.
"""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class CaptureContractError(ValueError):
    """Raised when the bounded capture contract cannot be satisfied."""


EXPECTED_ENDPOINT = "https://streaming.bitquery.io/graphql"
EXPECTED_DATASET = "archive"
EXPECTED_CUBE = "DEXTradeByTokens"
EXPECTED_INTERVAL_SECONDS = 900
EXPECTED_SLOTS = 96


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CaptureContractError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _policy_sections(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    route = _mapping(policy.get("provider_route"), "PROVIDER_ROUTE_INVALID")
    subject = _mapping(policy.get("reference_subject"), "REFERENCE_SUBJECT_INVALID")
    window = _mapping(policy.get("pilot_window"), "PILOT_WINDOW_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "RUNTIME_LIMITS_INVALID")
    controls = _mapping(policy.get("execution_controls"), "EXECUTION_CONTROLS_INVALID")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_INVALID")
    _require(route.get("dataset") == EXPECTED_DATASET, "DATASET_INVALID")
    _require(route.get("cube") == EXPECTED_CUBE, "CUBE_INVALID")
    _require(window.get("interval_seconds") == EXPECTED_INTERVAL_SECONDS, "INTERVAL_INVALID")
    _require(window.get("expected_slots") == EXPECTED_SLOTS, "EXPECTED_SLOTS_INVALID")
    _require(limits.get("max_provider_requests") == 1, "REQUEST_CAP_INVALID")
    _require(limits.get("max_response_bytes") == 2_000_000, "RESPONSE_CAP_INVALID")
    _require(limits.get("timeout_seconds") == 30, "TIMEOUT_INVALID")
    _require(controls.get("retry") is False, "RETRY_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_FORBIDDEN")
    _require(controls.get("redirect") is False, "REDIRECT_FORBIDDEN")
    return route, subject, window, limits, controls


def build_graphql_payload(policy: Mapping[str, Any]) -> dict[str, object]:
    """Build the only GraphQL request shape allowed by the tracked policy."""

    _route, subject, window, _limits, _controls = _policy_sections(policy)
    query = """query Task30BitqueryPIT(
  $since: DateTime!
  $till: DateTime!
  $pool: String!
  $base: String!
  $quote: String!
  $program: String!
) {
  Solana(dataset: archive) {
    bars: DEXTradeByTokens(
      where: {
        Block: {Time: {since: $since, till: $till}}
        Transaction: {Result: {Success: true}}
        Trade: {
          Currency: {MintAddress: {is: $base}}
          Side: {Currency: {MintAddress: {is: $quote}}}
          Market: {MarketAddress: {is: $pool}}
          Dex: {ProgramAddress: {is: $program}}
        }
      }
      orderBy: {ascendingByField: \"Block_Timefield\"}
      limit: {count: 96}
    ) {
      Block {Timefield: Time(interval: {count: 15, in: minutes})}
      Trade {
        open: PriceInUSD(minimum: Block_Slot)
        high: PriceInUSD(maximum: Trade_PriceInUSD)
        low: PriceInUSD(minimum: Trade_PriceInUSD)
        close: PriceInUSD(maximum: Block_Slot)
        Market {MarketAddress}
        Dex {ProtocolName ProgramAddress}
        Currency {MintAddress Symbol}
        Side {Currency {MintAddress Symbol}}
      }
      volume_usd: sum(of: Trade_Side_AmountInUSD)
      trade_count: count
    }
  }
}"""
    return {
        "query": query,
        "variables": {
            "since": window.get("since_inclusive"),
            "till": window.get("till_exclusive"),
            "pool": subject.get("pool_address"),
            "base": subject.get("base_mint"),
            "quote": subject.get("quote_mint"),
            "program": subject.get("program_address"),
        },
    }


def _parse_utc(value: object, code: str) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CaptureContractError(code) from exc
    _require(parsed.tzinfo == UTC, code)
    return parsed


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _nested(mapping: Mapping[str, Any], path: tuple[str, ...], code: str) -> Any:
    current: object = mapping
    for key in path:
        current = _mapping(current, code).get(key)
    return current


def _number_string(value: object, code: str) -> str:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), code)
    return str(value)


def project_slots(
    policy: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    raw_sha256: str,
    response_bytes: int,
    observed_at: str,
) -> dict[str, object]:
    """Project provider rows onto all 96 slots without imputing missing data."""

    route, subject, window, _limits, _controls = _policy_sections(policy)
    _require(isinstance(response, Mapping), "RESPONSE_SHAPE_INVALID")
    _require(not response.get("errors"), "GRAPHQL_ERRORS_RETURNED")
    try:
        bars = response["data"]["Solana"]["bars"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise CaptureContractError("RESPONSE_SHAPE_INVALID") from exc
    _require(isinstance(bars, list), "RESPONSE_SHAPE_INVALID")
    start = _parse_utc(window.get("since_inclusive"), "WINDOW_INVALID")
    end = _parse_utc(window.get("till_exclusive"), "WINDOW_INVALID")
    _require(end - start == timedelta(seconds=EXPECTED_INTERVAL_SECONDS * EXPECTED_SLOTS), "WINDOW_INVALID")
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    _require(isinstance(raw_sha256, str) and len(raw_sha256) == 64, "RAW_SHA256_INVALID")
    _require(isinstance(response_bytes, int) and not isinstance(response_bytes, bool) and response_bytes >= 0, "RESPONSE_BYTES_INVALID")

    observations: dict[datetime, dict[str, object]] = {}
    for value in bars:
        bar = _mapping(value, "RESPONSE_SHAPE_INVALID")
        slot_start = _parse_utc(_nested(bar, ("Block", "Timefield"), "RESPONSE_SHAPE_INVALID"), "SLOT_TIMESTAMP_INVALID")
        _require(start <= slot_start < end, "SLOT_OUTSIDE_WINDOW")
        elapsed = int((slot_start - start).total_seconds())
        _require(elapsed % EXPECTED_INTERVAL_SECONDS == 0, "SLOT_OFF_GRID")
        _require(slot_start not in observations, "DUPLICATE_SLOT")
        _require(
            _nested(bar, ("Trade", "Market", "MarketAddress"), "RESPONSE_SHAPE_INVALID")
            == subject.get("pool_address"),
            "POOL_IDENTITY_DRIFT",
        )
        _require(
            _nested(bar, ("Trade", "Currency", "MintAddress"), "RESPONSE_SHAPE_INVALID")
            == subject.get("base_mint"),
            "BASE_MINT_IDENTITY_DRIFT",
        )
        _require(
            _nested(bar, ("Trade", "Side", "Currency", "MintAddress"), "RESPONSE_SHAPE_INVALID")
            == subject.get("quote_mint"),
            "QUOTE_MINT_IDENTITY_DRIFT",
        )
        _require(
            _nested(bar, ("Trade", "Dex", "ProgramAddress"), "RESPONSE_SHAPE_INVALID")
            == subject.get("program_address"),
            "PROGRAM_IDENTITY_DRIFT",
        )
        trade = _mapping(bar.get("Trade"), "RESPONSE_SHAPE_INVALID")
        observations[slot_start] = {
            "slot_start": _format_utc(slot_start),
            "slot_end": _format_utc(slot_start + timedelta(seconds=EXPECTED_INTERVAL_SECONDS)),
            "state": "OBSERVATION",
            "source_route": route.get("route_id"),
            "open_usd": _number_string(trade.get("open"), "OHLC_INVALID"),
            "high_usd": _number_string(trade.get("high"), "OHLC_INVALID"),
            "low_usd": _number_string(trade.get("low"), "OHLC_INVALID"),
            "close_usd": _number_string(trade.get("close"), "OHLC_INVALID"),
            "volume_usd": _number_string(bar.get("volume_usd"), "VOLUME_INVALID"),
            "trade_count": _number_string(bar.get("trade_count"), "TRADE_COUNT_INVALID"),
        }

    slots: list[dict[str, object]] = []
    for offset in range(EXPECTED_SLOTS):
        slot_start = start + timedelta(seconds=offset * EXPECTED_INTERVAL_SECONDS)
        observed = observations.get(slot_start)
        if observed is not None:
            slots.append(observed)
        else:
            slots.append(
                {
                    "slot_start": _format_utc(slot_start),
                    "slot_end": _format_utc(slot_start + timedelta(seconds=EXPECTED_INTERVAL_SECONDS)),
                    "state": "MISSING_UNKNOWN",
                    "gap_type": "NO_OBSERVATION_RETURNED",
                    "source_route": route.get("route_id"),
                }
            )

    observed_count = len(observations)
    if observed_count == EXPECTED_SLOTS:
        terminal_outcome = "COMPLETE_96_SLOT_MARKET_PANEL"
    elif observed_count > 0:
        terminal_outcome = "PARTIAL_TYPED_GAP_PANEL"
    else:
        terminal_outcome = "ROUTE_UNKNOWN_STOP"
    return {
        "schema": "smial.task30.bitquery-named-partial-pit-route-capture.runtime-receipt",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": policy.get("atom_id"),
        "route_id": route.get("route_id"),
        "observed_at": observed_at,
        "raw_sha256": raw_sha256,
        "response_bytes": response_bytes,
        "window": {
            "since_inclusive": window.get("since_inclusive"),
            "till_exclusive": window.get("till_exclusive"),
            "interval_seconds": EXPECTED_INTERVAL_SECONDS,
        },
        "counts": {
            "slots": EXPECTED_SLOTS,
            "observed": observed_count,
            "typed_gaps": EXPECTED_SLOTS - observed_count,
        },
        "terminal_outcome": terminal_outcome,
        "slots": slots,
        "claims": dict(_mapping(policy.get("claims"), "CLAIMS_INVALID")),
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request:
        raise CaptureContractError("REDIRECT_FORBIDDEN")


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def perform_http_post_once(
    policy: Mapping[str, Any],
    payload: Mapping[str, Any],
    token: str,
    *,
    opener: object | None = None,
) -> dict[str, object]:
    """Perform one bounded POST and return no credential-bearing metadata."""

    route, _subject, _window, limits, _controls = _policy_sections(policy)
    _require(isinstance(token, str) and bool(token.strip()), "CREDENTIAL_REQUIRED")
    _require(set(payload) == {"query", "variables"}, "PAYLOAD_INVALID")
    request_body = _canonical_json_bytes(payload)
    outgoing = urllib.request.Request(
        str(route["endpoint"]),
        data=request_body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    selected_opener = opener or urllib.request.build_opener(_NoRedirectHandler())
    max_bytes = int(limits["max_response_bytes"])
    try:
        with selected_opener.open(outgoing, timeout=float(limits["timeout_seconds"])) as response:  # type: ignore[union-attr]
            status = int(response.getcode())
            body = response.read(max_bytes + 1)
            content_type = str(response.headers.get("Content-Type", ""))
    except CaptureContractError:
        raise
    except (urllib.error.URLError, ssl.SSLError, socket.gaierror, socket.timeout, TimeoutError, OSError) as exc:
        raise CaptureContractError("TRANSPORT_ERROR") from exc
    _require(len(body) <= max_bytes, "RESPONSE_BYTES_EXCEEDED")
    _require(status == 200, "HTTP_STATUS_ERROR")
    return {
        "body": body,
        "http_status": status,
        "content_type": content_type,
        "response_bytes": len(body),
        "request_body_sha256": hashlib.sha256(request_body).hexdigest(),
        "request_count": 1,
    }


def write_raw_artifacts(
    raw_root: Path,
    *,
    run_id: str,
    response_body: bytes,
    request_body_sha256: str,
    observed_at: str,
) -> dict[str, object]:
    """Persist exact provider bytes and a secret-free immutable manifest."""

    _require(isinstance(raw_root, Path), "RAW_ROOT_INVALID")
    _require(isinstance(run_id, str) and run_id and "/" not in run_id and "\\" not in run_id, "RUN_ID_INVALID")
    _require(isinstance(response_body, bytes), "RESPONSE_BODY_INVALID")
    _require(isinstance(request_body_sha256, str) and len(request_body_sha256) == 64, "REQUEST_SHA256_INVALID")
    _parse_utc(observed_at, "OBSERVED_AT_INVALID")
    run_root = raw_root / f"run={run_id}"
    try:
        run_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CaptureContractError("RUN_ALREADY_EXISTS") from exc
    raw_path = run_root / "raw_response.json"
    raw_path.write_bytes(response_body)
    manifest: dict[str, object] = {
        "schema": "smial.task30.bitquery-raw-manifest",
        "schema_version": "1.0",
        "run_id": run_id,
        "observed_at": observed_at,
        "raw_filename": raw_path.name,
        "response_bytes": len(response_body),
        "raw_sha256": hashlib.sha256(response_body).hexdigest(),
        "request_body_sha256": request_body_sha256,
        "retention_class": "A4_OUTSIDE_GIT",
    }
    (run_root / "raw_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
