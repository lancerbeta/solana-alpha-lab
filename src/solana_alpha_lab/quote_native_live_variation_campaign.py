"""Live outcome-blind quote-native variation campaign on Jupiter Tokens V2 plus /order."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from solana_alpha_lab.pmf_quote_slice_one_shot import (
    EXPECTED_HOST,
    QuoteShotError,
    QuoteShotTerminalError,
    credential_free_preflight,
)
from solana_alpha_lab.quote_native_evidence_fit_panel import (
    A24_MINT,
    EXPECTED_ENDPOINT,
    PanelError,
    ROUTE_ID,
    T21_MINTS,
    WRAPPED_SOL,
    execute_observation,
)
from solana_alpha_lab.quote_native_friction_h900_falsifier import (
    R3_MINTS,
    score_mechanism,
)

ATOM_ID = "QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1: Jupiter Tokens V2 /recent plus "
    "/toptraded/1h control keyless, quote-only /swap/v2/order, taker omitted, "
    "execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no "
    "retry/fallback, pace >=2s, call cap 60, bind order route "
    "JUPITER-SOLANA-SWAP-V2-ORDER-001, registry v8 additive after first "
    "observation, live outcome-blind sample, no T21 freeze reuse, no A24, "
    "+15m and +60m sells, +240m explicit gap"
)
CONFIG_RELATIVE = "configs/quote_native_live_variation_campaign_v1.yaml"
V7_RELATIVE = "configs/provider_route_capability_registry_v7.yaml"
RECENT_ENDPOINT = "https://api.jup.ag/tokens/v2/recent"
TRADED_ENDPOINT = "https://api.jup.ag/tokens/v2/toptraded/1h"
RECENT_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-RECENT-001"
TRADED_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-001"
USER_AGENT = "smial-quote-native-live-variation/1.0"
CALL_CAP = 60
DISCOVERY_CAP = 2
MIN_INTERVAL = 3
NOTIONAL = "10000000"
RECENT_N = 6
TRADED_N = 6
LIQUIDITY_FLOOR = 1000
H900 = 900
H3600 = 3600
H14400 = 14400
SLACK = 120
SCHEDULE_COUNT = 60
FORBIDDEN_MINTS = (A24_MINT, *T21_MINTS, *R3_MINTS)
CONTINUABLE = frozenset({"SCHEDULED", "NOT_REACHED"})
ALLOWED_TOKEN_PATHS = frozenset({"/tokens/v2/recent", "/tokens/v2/toptraded/1h"})


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> urllib.request.Request | None:
        return None


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PanelError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    _require(type(value) is str and bool(value), "CLOCK_INVALID")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    quote_route = _mapping(policy.get("quote_route"), "ROUTE_INVALID")
    discovery = _mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    recent = _mapping(discovery.get("recent"), "DISCOVERY_INVALID")
    traded = _mapping(discovery.get("traded"), "DISCOVERY_INVALID")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    kill = _mapping(policy.get("control_kill"), "KILL_INVALID")
    success = _mapping(policy.get("success"), "SUCCESS_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(authority.get("capture_authorized") is True, "CAPTURE_NOT_AUTHORIZED")
    _require(authority.get("credential_reads") is False, "CREDENTIAL_READ_NOT_FORBIDDEN")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(int(authority.get("call_cap", 0)) == CALL_CAP, "CALL_CAP_DRIFT")
    _require(int(authority.get("cash_cap_usd_cents", -1)) == 0, "CASH_CAP_DRIFT")
    _require(quote_route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(quote_route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_DRIFT")
    _require(quote_route.get("method") == "GET", "METHOD_DRIFT")
    _require(quote_route.get("host") == EXPECTED_HOST, "HOST_DRIFT")
    _require(quote_route.get("registry") == V7_RELATIVE, "REGISTRY_BIND_DRIFT")
    v7_route = _v7_order_route(root)
    _require(v7_route.get("access_class") == "KEYLESS", "V7_ACCESS_CLASS_DRIFT")
    _require(recent.get("intended_route_id") == RECENT_ROUTE_ID, "RECENT_ROUTE_DRIFT")
    _require(recent.get("endpoint") == RECENT_ENDPOINT, "RECENT_ENDPOINT_DRIFT")
    _require(traded.get("intended_route_id") == TRADED_ROUTE_ID, "TRADED_ROUTE_DRIFT")
    _require(traded.get("endpoint") == TRADED_ENDPOINT, "TRADED_ENDPOINT_DRIFT")
    _require(policy.get("wrapped_sol_mint") == WRAPPED_SOL, "SOL_MINT_DRIFT")
    _require(str(policy.get("notional_atomic")) == NOTIONAL, "NOTIONAL_DRIFT")
    _require(int(policy.get("recent_cell_count", 0)) == RECENT_N, "RECENT_COUNT_DRIFT")
    _require(int(policy.get("traded_cell_count", 0)) == TRADED_N, "TRADED_COUNT_DRIFT")
    _require(int(policy.get("liquidity_floor_usd", 0)) == LIQUIDITY_FLOOR, "FLOOR_DRIFT")
    _require(int(policy.get("min_interval_seconds", 0)) == MIN_INTERVAL, "PACE_DRIFT")
    _require(
        tuple(int(item) for item in policy.get("observable_horizon_seconds") or []) == (H900, H3600),
        "HORIZON_DRIFT",
    )
    _require(
        tuple(int(item) for item in policy.get("gap_horizon_seconds") or []) == (H14400,),
        "GAP_HORIZON_DRIFT",
    )
    _require(int(policy.get("lateness_slack_seconds", 0)) == SLACK, "SLACK_DRIFT")
    _require(int(kill.get("min_complete_cells", 0)) == 6, "KILL_COMPLETE_DRIFT")
    _require(str(kill.get("min_time_separated_share")) == "0.5", "KILL_SHARE_DRIFT")
    _require(int(success.get("min_complete_xy", 0)) == 10, "SUCCESS_COMPLETE_DRIFT")
    _require(int(success.get("min_time_separated", 0)) == 6, "SUCCESS_SEPARATED_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("dex_screener") is False, "DEXSCREENER_NOT_FORBIDDEN")
    _require(controls.get("t21_freeze_reuse") is False, "T21_FREEZE_REUSED_AS_SAMPLE")
    _require(controls.get("live_tokens_v2_discovery") is True, "DISCOVERY_NOT_AUTHORIZED")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER_FORBIDDEN")
    _require(controls.get("background_scheduler") is False, "BACKGROUND_SCHEDULER")
    _require(int(controls.get("provider_requests_max", 0)) == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(int(controls.get("discovery_provider_requests_max", 0)) == DISCOVERY_CAP, "DISCOVERY_BUDGET_DRIFT")


def _v7_order_route(root: Path) -> Mapping[str, Any]:
    document = yaml.safe_load((root / V7_RELATIVE).read_text(encoding="utf-8"))
    _require(isinstance(document, Mapping), "V7_INVALID")
    routes = document.get("routes")
    _require(isinstance(routes, list), "V7_INVALID")
    for raw in routes:
        route = _mapping(raw, "V7_INVALID")
        if route.get("route_id") == ROUTE_ID:
            return route
    raise PanelError("V7_ROUTE_MISSING")


def _order_policy(policy: Mapping[str, Any]) -> dict[str, object]:
    route = _mapping(policy.get("quote_route"), "ROUTE_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    return {
        "provider_route": {
            "endpoint": route["endpoint"],
            "host": route["host"],
            "method": "GET",
        },
        "slippage_bps": policy.get("slippage_bps"),
        "runtime_limits": dict(limits),
    }


def perform_keyless_get(
    url: str,
    limits: Mapping[str, Any],
    *,
    opener: object | None = None,
) -> dict[str, object]:
    _require("taker" not in url.lower(), "TAKER_IN_URL")
    _require("api-key" not in url.lower(), "API_KEY_IN_URL")
    parsed = urlsplit(url)
    _require(parsed.scheme == "https", "ENDPOINT_DRIFT")
    _require(parsed.hostname == EXPECTED_HOST, "HOST_DRIFT")
    _require(parsed.path in ALLOWED_TOKEN_PATHS, "TOKEN_PATH_DRIFT")
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    outgoing = urllib.request.Request(url, method="GET", headers=headers)
    _require("x-api-key" not in {key.lower() for key in outgoing.headers}, "API_KEY_HEADER")
    selected = opener or urllib.request.build_opener(_NoRedirectHandler())
    max_bytes = int(limits["max_response_bytes"])
    try:
        with selected.open(outgoing, timeout=float(limits["timeout_seconds"])) as response:  # type: ignore[union-attr]
            status = int(response.getcode())
            body = response.read(max_bytes + 1)
            content_type = str(response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read(max_bytes + 1)
        content_type = str(exc.headers.get("Content-Type", "")) if exc.headers is not None else ""
    except (urllib.error.URLError, ssl.SSLError, socket.gaierror, socket.timeout, TimeoutError, OSError) as exc:
        raise QuoteShotTerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "content_type": None,
                    "response_bytes": None,
                    "response_sha256": None,
                    "request_count": 1,
                    "url_has_taker": False,
                    "url_has_api_key": False,
                },
                "body": None,
            },
        ) from exc
    _require(len(body) <= max_bytes, "RESPONSE_BYTES_EXCEEDED")
    return {
        "http_status": status,
        "content_type": content_type,
        "body": body,
        "response_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "request_count": 1,
        "url": url,
        "url_has_taker": False,
        "url_has_api_key": False,
    }


def _liquidity(item: Mapping[str, Any]) -> float | None:
    value = item.get("liquidity")
    if type(value) is bool:
        return None
    if type(value) is int or type(value) is float:
        return float(value)
    if type(value) is str:
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _created_at(item: Mapping[str, Any]) -> datetime | None:
    pool = item.get("firstPool")
    if not isinstance(pool, Mapping):
        return None
    raw = pool.get("createdAt")
    if type(raw) is not str or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def select_cohort(
    recent_payload: list[Mapping[str, Any]],
    traded_payload: list[Mapping[str, Any]],
) -> dict[str, object]:
    def eligible(item: Mapping[str, Any], *, require_created: bool) -> bool:
        mint = item.get("id")
        if type(mint) is not str or not mint:
            return False
        if mint in FORBIDDEN_MINTS or mint == WRAPPED_SOL:
            return False
        liquidity = _liquidity(item)
        if liquidity is None or liquidity < LIQUIDITY_FLOOR:
            return False
        if require_created and _created_at(item) is None:
            return False
        return True

    recent_ranked = sorted(
        [item for item in recent_payload if eligible(item, require_created=True)],
        key=lambda item: _created_at(item) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    recent_cells: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in recent_ranked:
        mint = str(item["id"])
        if mint in seen:
            continue
        seen.add(mint)
        created = _created_at(item)
        recent_cells.append(
            {
                "identity_id": f"RECENT_{len(recent_cells) + 1}",
                "mint": mint,
                "stratum": "RECENT",
                "notional_atomic": NOTIONAL,
                "liquidity": _liquidity(item),
                "first_pool_created_at": _format_utc(created) if created else None,
                "source_kind": "LIVE_TOKENS_V2_RECENT",
            }
        )
        if len(recent_cells) == RECENT_N:
            break
    traded_cells: list[dict[str, object]] = []
    for item in traded_payload:
        if not eligible(item, require_created=False):
            continue
        mint = str(item["id"])
        if mint in seen:
            continue
        seen.add(mint)
        created = _created_at(item)
        traded_cells.append(
            {
                "identity_id": f"TRADED_{len(traded_cells) + 1}",
                "mint": mint,
                "stratum": "TRADED",
                "notional_atomic": NOTIONAL,
                "liquidity": _liquidity(item),
                "first_pool_created_at": _format_utc(created) if created else None,
                "source_kind": "LIVE_TOKENS_V2_TOPTRADED",
            }
        )
        if len(traded_cells) == TRADED_N:
            break
    sufficient = len(recent_cells) == RECENT_N and len(traded_cells) == TRADED_N
    return {
        "sufficient": sufficient,
        "cells": recent_cells + traded_cells if sufficient else recent_cells + traded_cells,
        "recent_eligible": len(recent_cells),
        "traded_eligible": len(traded_cells),
    }


def build_schedule(
    cells: list[Mapping[str, Any]],
    *,
    panel_started_at: datetime,
) -> list[dict[str, object]]:
    started = _format_utc(panel_started_at)
    rows: list[dict[str, object]] = []
    for cell in cells:
        mapped = _mapping(cell, "CELL_INVALID")
        identity_id = str(mapped["identity_id"])
        mint = str(mapped["mint"])
        _require(mint not in FORBIDDEN_MINTS, "A24_OR_T21_FREEZE_SELECTED")
        buy_id = f"{identity_id}:{NOTIONAL}:BUY_T0"
        rows.append(
            {
                "observation_id": buy_id,
                "identity_id": identity_id,
                "mint": mint,
                "stratum": mapped["stratum"],
                "kind": "BUY_T0",
                "wave": "t0",
                "input_mint": WRAPPED_SOL,
                "output_mint": mint,
                "amount": NOTIONAL,
                "parent_id": None,
                "due_at": started,
                "horizon_seconds": 0,
            }
        )
        rows.append(
            {
                "observation_id": f"{identity_id}:{NOTIONAL}:REVERSE_T0",
                "identity_id": identity_id,
                "mint": mint,
                "stratum": mapped["stratum"],
                "kind": "REVERSE_T0",
                "wave": "t0",
                "input_mint": mint,
                "output_mint": WRAPPED_SOL,
                "amount": None,
                "parent_id": buy_id,
                "due_at": started,
                "horizon_seconds": 0,
            }
        )
        for horizon, kind, wave, terminal in (
            (H900, "SELL_H900", "horizon", None),
            (H3600, "SELL_H3600", "horizon", None),
            (H14400, "SELL_H14400", "gap", "EXPLICIT_GAP"),
        ):
            due = panel_started_at.astimezone(UTC) + timedelta(seconds=horizon)
            row: dict[str, object] = {
                "observation_id": f"{identity_id}:{NOTIONAL}:{kind}",
                "identity_id": identity_id,
                "mint": mint,
                "stratum": mapped["stratum"],
                "kind": kind,
                "wave": wave,
                "input_mint": mint,
                "output_mint": WRAPPED_SOL,
                "amount": None,
                "parent_id": buy_id,
                "due_at": _format_utc(due),
                "horizon_seconds": horizon,
                "lateness_slack_seconds": SLACK,
            }
            if terminal is not None:
                row["terminal"] = terminal
                row["consumed_call"] = False
            rows.append(row)
    _require(len(rows) == SCHEDULE_COUNT, "SCHEDULE_COUNT_DRIFT")
    return rows


def score_campaign(observations: list[Mapping[str, Any]]) -> dict[str, object]:
    mechanism = score_mechanism(observations)
    cells = mechanism.get("cells")
    _require(isinstance(cells, list), "MECHANISM_CELLS_INVALID")
    traded_complete = 0
    traded_separated = 0
    recent_complete = 0
    recent_separated = 0
    for raw in cells:
        cell = _mapping(raw, "MECHANISM_CELL_INVALID")
        identity_id = str(cell.get("identity_id") or "")
        complete = cell.get("x_status") == "OBSERVED" and cell.get("y_status") == "OBSERVED"
        separated = complete and cell.get("y_equals_x") is False
        if identity_id.startswith("TRADED_"):
            traded_complete += int(complete)
            traded_separated += int(separated)
        elif identity_id.startswith("RECENT_"):
            recent_complete += int(complete)
            recent_separated += int(separated)
    traded_share = (
        str(Decimal(traded_separated) / Decimal(traded_complete)) if traded_complete else None
    )
    kill = traded_complete >= 6 and traded_separated / traded_complete < 0.5
    success = (
        int(mechanism.get("complete_xy_count") or 0) >= 10
        and int(mechanism.get("time_separated_complete_xy_count") or 0) >= 6
        and recent_complete > 0
        and traded_complete > 0
    )
    if kill:
        verdict = "VARIATION_ABSENT_ON_TRADED_CONTROL"
    elif success:
        verdict = "VARIATION_PRESENT_NOT_MECHANISM"
    else:
        verdict = "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
    h3600_moved = 0
    h3600_same = 0
    by_identity: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in observations:
        identity_id = str(row.get("identity_id") or "")
        kind = str(row.get("kind") or "")
        if identity_id and kind in {"BUY_T0", "REVERSE_T0", "SELL_H3600"}:
            by_identity.setdefault(identity_id, {})[kind] = row
    for kinds in by_identity.values():
        buy = kinds.get("BUY_T0")
        reverse = kinds.get("REVERSE_T0")
        sell = kinds.get("SELL_H3600")
        if not (
            isinstance(buy, Mapping)
            and buy.get("terminal") == "QUOTE_OBSERVED"
            and isinstance(reverse, Mapping)
            and reverse.get("terminal") == "QUOTE_OBSERVED"
            and isinstance(sell, Mapping)
            and sell.get("terminal") == "QUOTE_OBSERVED"
        ):
            continue
        reverse_quote = reverse.get("quote") if isinstance(reverse.get("quote"), Mapping) else None
        sell_quote = sell.get("quote") if isinstance(sell.get("quote"), Mapping) else None
        reverse_out = reverse_quote.get("out_amount") if reverse_quote else None
        sell_out = sell_quote.get("out_amount") if sell_quote else None
        if reverse_out == sell_out:
            h3600_same += 1
        else:
            h3600_moved += 1
    return {
        "verdict": verdict,
        "campaign_verdict": verdict,
        "complete_xy_count": int(mechanism.get("complete_xy_count") or 0),
        "time_separated_complete_xy_count": int(
            mechanism.get("time_separated_complete_xy_count") or 0
        ),
        "y_equals_x_count": int(mechanism.get("y_equals_x_count") or 0),
        "h900_quote_observed_count": int(mechanism.get("h900_quote_observed_count") or 0),
        "h900_no_route_count": int(mechanism.get("h900_no_route_count") or 0),
        "cells": cells,
        "recent_complete_xy_count": recent_complete,
        "recent_time_separated_count": recent_separated,
        "traded_complete_xy_count": traded_complete,
        "traded_time_separated_count": traded_separated,
        "traded_time_separated_share": traded_share,
        "h3600_moved_count": h3600_moved,
        "h3600_y_equals_x_count": h3600_same,
        "family_close": False,
        "non_claims": [
            "NOT_NETRETURN",
            "NOT_ALPHA",
            "NO_THRESHOLD_FIT",
            "NO_FAMILY_CLOSE_ON_SAMPLE_INVALID",
            "NO_DIRECTIONAL_HINT_FROM_THIS_ATOM",
            "NO_MOVE_2_EARNED",
        ],
    }


def _transport_from_raw(raw: Mapping[str, Any], *, terminal: str, error: str | None) -> dict[str, object]:
    return {
        "terminal": terminal,
        "terminal_error": error,
        "transport": {
            "http_status": raw.get("http_status"),
            "content_type": raw.get("content_type"),
            "response_bytes": raw.get("response_bytes"),
            "response_sha256": raw.get("response_sha256"),
            "request_count": 1,
            "url_has_taker": False,
            "url_has_api_key": False,
        },
        "body": raw.get("body"),
    }


def _classify_discovery(raw: Mapping[str, Any]) -> dict[str, object]:
    status = int(raw.get("http_status") or 0)
    body = raw.get("body")
    if status in {401, 403}:
        return _transport_from_raw(raw, terminal="CREDENTIAL_REQUIRED_NOT_AUTHORIZED", error=f"HTTP_{status}")
    if status == 429:
        return _transport_from_raw(raw, terminal="RATE_LIMITED", error="HTTP_429")
    if status != 200:
        return _transport_from_raw(raw, terminal="PROVIDER_TYPED_FAILURE", error=f"HTTP_{status}")
    try:
        payload = json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else b"")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return _transport_from_raw(raw, terminal="TOKEN_LIST_SHAPE_INVALID", error="JSON")
    if not isinstance(payload, list):
        return _transport_from_raw(raw, terminal="TOKEN_LIST_NOT_ARRAY", error="SHAPE")
    mapped = [item for item in payload if isinstance(item, Mapping)]
    result = _transport_from_raw(raw, terminal="TOKEN_LIST_OBSERVED", error=None)
    result["payload"] = mapped
    return result


def _pace(
    *,
    last_call_at: str | None,
    now: datetime,
    sleeper: Callable[[float], None],
) -> None:
    if last_call_at is None:
        return
    elapsed = (now - _parse_utc(last_call_at)).total_seconds()
    wait = MIN_INTERVAL - elapsed
    if wait > 0:
        sleeper(wait)


def _halted_remainder(row: Mapping[str, Any], *, results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    recorded = dict(row)
    recorded["consumed_call"] = False
    parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
    if str(row.get("wave")) == "horizon" and str(recorded.get("terminal") or "SCHEDULED") == "SCHEDULED":
        recorded["terminal"] = "SCHEDULED"
        return recorded
    if str(row.get("kind")) != "BUY_T0" and isinstance(parent, Mapping):
        parent_terminal = str(parent.get("terminal") or "")
        if parent.get("consumed_call") and parent_terminal != "QUOTE_OBSERVED":
            recorded["terminal"] = "SKIPPED_NO_ENTRY"
            recorded["quote"] = None
            return recorded
        if parent_terminal == "SKIPPED_NO_ENTRY":
            recorded["terminal"] = "SKIPPED_NO_ENTRY"
            recorded["quote"] = None
            return recorded
    recorded["terminal"] = "NOT_REACHED"
    return recorded


def _ticking_clock(start: datetime) -> Callable[[], datetime]:
    state = {"n": 0}

    def _tick() -> datetime:
        current = start + timedelta(seconds=state["n"])
        state["n"] += 1
        return current

    return _tick


def run_wave(
    policy: Mapping[str, Any],
    *,
    root: Path,
    wave: str,
    now: datetime,
    opener: object | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    prior_receipt: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, object]:
    validate_policy(policy, root=root)
    _require(wave in {"discovery", "t0", "due"}, "WAVE_INVALID")
    if wave != "discovery":
        _require(isinstance(prior_receipt, Mapping), "PRIOR_RECEIPT_REQUIRED")
        assert prior_receipt is not None
        _require(prior_receipt.get("atom_id") == ATOM_ID, "OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED")
    started_at = now.astimezone(UTC)
    tick = clock or _ticking_clock(started_at)
    wait = sleeper or (lambda _seconds: None)
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    preflight = dict(
        preflight_fn(
            {
                "provider_route": {
                    "endpoint": RECENT_ENDPOINT if wave == "discovery" else EXPECTED_ENDPOINT,
                    "host": EXPECTED_HOST,
                    "method": "GET",
                }
            },
            observed_at=_format_utc(started_at),
        )
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    if wave == "discovery":
        return _run_discovery(
            policy,
            started_at=started_at,
            tick=tick,
            wait=wait,
            opener=opener,
            preflight=preflight,
            limits=limits,
        )
    assert prior_receipt is not None
    if wave == "t0":
        return _run_quotes(
            policy,
            prior_receipt=prior_receipt,
            started_at=started_at,
            tick=tick,
            wait=wait,
            opener=opener,
            preflight=preflight,
            select_horizon=False,
        )
    return _run_quotes(
        policy,
        prior_receipt=prior_receipt,
        started_at=started_at,
        tick=tick,
        wait=wait,
        opener=opener,
        preflight=preflight,
        select_horizon=True,
    )


def _run_discovery(
    policy: Mapping[str, Any],
    *,
    started_at: datetime,
    tick: Callable[[], datetime],
    wait: Callable[[float], None],
    opener: object | None,
    preflight: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> dict[str, object]:
    last_call_at: str | None = None
    raw_bodies: dict[str, bytes] = {}
    discovery_rows: list[dict[str, object]] = []
    provider_requests = 0

    def _call(url: str, observation_id: str) -> dict[str, object]:
        nonlocal last_call_at, provider_requests
        _require(provider_requests < DISCOVERY_CAP, "CALL_CAP_EXCEEDED")
        observed_at = tick()
        _pace(last_call_at=last_call_at, now=observed_at, sleeper=wait)
        observed_at = tick()
        try:
            raw = perform_keyless_get(url, limits, opener=opener)
        except QuoteShotTerminalError as exc:
            evidence = dict(exc.evidence)
            classified = {
                "terminal": "TRANSPORT_OR_QUOTE_UNKNOWN",
                "terminal_error": str(exc),
                "transport": dict(evidence.get("transport") or {"request_count": 1}),
                "body": evidence.get("body"),
                "payload": None,
            }
            raw_local: Mapping[str, Any] = {"body": None}
        except QuoteShotError as exc:
            classified = {
                "terminal": "TRANSPORT_OR_QUOTE_UNKNOWN",
                "terminal_error": str(exc),
                "transport": {"request_count": 1},
                "body": None,
                "payload": None,
            }
            raw_local = {"body": None}
        else:
            classified = _classify_discovery(raw)
            raw_local = raw
        provider_requests += 1
        last_call_at = _format_utc(observed_at)
        body = classified.pop("body", None)
        payload = classified.pop("payload", None)
        if isinstance(body, (bytes, bytearray)):
            raw_bodies[observation_id] = bytes(body)
        row = {
            "observation_id": observation_id,
            "kind": observation_id.replace("DISCOVERY:", "DISCOVERY_"),
            "wave": "discovery",
            "observed_at": last_call_at,
            "url": url,
            "consumed_call": True,
            "payload_count": len(payload) if isinstance(payload, list) else None,
            **classified,
        }
        if isinstance(payload, list):
            row["_payload"] = payload
        discovery_rows.append(row)
        return row

    recent_row = _call(RECENT_ENDPOINT, "DISCOVERY:RECENT")
    if str(recent_row.get("terminal")) == "CREDENTIAL_REQUIRED_NOT_AUTHORIZED":
        return _discovery_receipt(
            started_at=started_at,
            preflight=preflight,
            provider_requests=provider_requests,
            last_call_at=last_call_at,
            discovery_rows=discovery_rows,
            raw_bodies=raw_bodies,
            cells=[],
            terminal="DISCOVERY_CREDENTIAL_REQUIRED_NOT_AUTHORIZED",
        )
    if str(recent_row.get("terminal")) != "TOKEN_LIST_OBSERVED":
        terminal = (
            "PANEL_RATE_LIMITED"
            if recent_row.get("terminal") == "RATE_LIMITED"
            else "SAMPLE_INVALID_INSUFFICIENT_DISCOVERY"
        )
        return _discovery_receipt(
            started_at=started_at,
            preflight=preflight,
            provider_requests=provider_requests,
            last_call_at=last_call_at,
            discovery_rows=discovery_rows,
            raw_bodies=raw_bodies,
            cells=[],
            terminal=terminal,
        )
    traded_row = _call(TRADED_ENDPOINT, "DISCOVERY:TRADED")
    if str(traded_row.get("terminal")) == "CREDENTIAL_REQUIRED_NOT_AUTHORIZED":
        return _discovery_receipt(
            started_at=started_at,
            preflight=preflight,
            provider_requests=provider_requests,
            last_call_at=last_call_at,
            discovery_rows=discovery_rows,
            raw_bodies=raw_bodies,
            cells=[],
            terminal="CONTROL_STRATUM_CREDENTIAL_REQUIRED_NOT_AUTHORIZED",
        )
    if str(traded_row.get("terminal")) != "TOKEN_LIST_OBSERVED":
        terminal = (
            "PANEL_RATE_LIMITED"
            if traded_row.get("terminal") == "RATE_LIMITED"
            else "SAMPLE_INVALID_INSUFFICIENT_DISCOVERY"
        )
        return _discovery_receipt(
            started_at=started_at,
            preflight=preflight,
            provider_requests=provider_requests,
            last_call_at=last_call_at,
            discovery_rows=discovery_rows,
            raw_bodies=raw_bodies,
            cells=[],
            terminal=terminal,
        )
    recent_payload = list(recent_row.pop("_payload", []))
    traded_payload = list(traded_row.pop("_payload", []))
    selected = select_cohort(recent_payload, traded_payload)
    cells = list(selected["cells"]) if isinstance(selected["cells"], list) else []
    terminal = (
        "DISCOVERY_COHORT_FROZEN"
        if selected.get("sufficient")
        else "SAMPLE_INVALID_INSUFFICIENT_DISCOVERY"
    )
    return _discovery_receipt(
        started_at=started_at,
        preflight=preflight,
        provider_requests=provider_requests,
        last_call_at=last_call_at,
        discovery_rows=discovery_rows,
        raw_bodies=raw_bodies,
        cells=cells,
        terminal=terminal,
        selection=selected,
    )


def _discovery_receipt(
    *,
    started_at: datetime,
    preflight: Mapping[str, Any],
    provider_requests: int,
    last_call_at: str | None,
    discovery_rows: list[dict[str, object]],
    raw_bodies: dict[str, bytes],
    cells: list[Any],
    terminal: str,
    selection: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    cleaned = []
    for row in discovery_rows:
        item = dict(row)
        item.pop("_payload", None)
        cleaned.append(item)
    return {
        "schema": "smial.quote-native-live-variation-campaign.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "route_id": ROUTE_ID,
        "owner_phrase": AUTHORITY_PHRASE,
        "terminal_outcome": terminal,
        "started_at": _format_utc(started_at),
        "panel_started_at": None,
        "wave": "discovery",
        "preflight": dict(preflight),
        "provider_requests": provider_requests,
        "new_provider_requests": provider_requests,
        "last_provider_call_at": last_call_at,
        "retries": 0,
        "fallbacks": 0,
        "credential_reads": 0,
        "execute_calls": 0,
        "frozen_cells": cells,
        "selection": dict(selection) if selection is not None else None,
        "discovery_observations": cleaned,
        "observations": [],
        "campaign": None,
        "raw_bodies": raw_bodies,
        "non_claims": _non_claims(),
        "limitations": ["LIVE_SAMPLE_NOT_A_CONFIRMATORY_TRIAL"],
    }


def _non_claims() -> list[str]:
    return [
        "NO_EXECUTE",
        "NO_TAKER_OR_SIGNER",
        "NO_TRANSACTION_BYTES_IN_GIT",
        "NO_ALPHA",
        "NO_NETRETURN",
        "NO_CANONICAL_DONE",
        "NO_H13_OR_H02_TRIAL",
        "NO_DIRECTIONAL_HINT_FROM_THIS_ATOM",
        "NO_T21_FREEZE_REUSE",
        "NO_H14400_OBSERVATION",
        "NO_FAMILY_CLOSE_ON_SAMPLE_INVALID",
        "NO_MOVE_2_EARNED",
    ]


def _run_quotes(
    policy: Mapping[str, Any],
    *,
    prior_receipt: Mapping[str, Any],
    started_at: datetime,
    tick: Callable[[], datetime],
    wait: Callable[[float], None],
    opener: object | None,
    preflight: Mapping[str, Any],
    select_horizon: bool,
) -> dict[str, object]:
    prior_requests = int(prior_receipt.get("provider_requests", 0))
    last_call_at = prior_receipt.get("last_provider_call_at")
    last_call = str(last_call_at) if type(last_call_at) is str else None
    if select_horizon:
        raw_schedule = prior_receipt.get("observations")
        _require(isinstance(raw_schedule, list) and len(raw_schedule) == SCHEDULE_COUNT, "PRIOR_SCHEDULE_INVALID")
        schedule = [dict(item) for item in raw_schedule if isinstance(item, Mapping)]
        _require(len(schedule) == SCHEDULE_COUNT, "SCHEDULE_COUNT_DRIFT")
        panel_started = str(prior_receipt.get("panel_started_at") or "")
        _require(bool(panel_started), "PANEL_START_MISSING")
    else:
        _require(
            prior_receipt.get("terminal_outcome") == "DISCOVERY_COHORT_FROZEN",
            "DISCOVERY_NOT_FROZEN",
        )
        cells = prior_receipt.get("frozen_cells")
        _require(isinstance(cells, list) and len(cells) == RECENT_N + TRADED_N, "CELL_COUNT_DRIFT")
        for cell in cells:
            mapped = _mapping(cell, "CELL_INVALID")
            _require(str(mapped.get("mint")) not in FORBIDDEN_MINTS, "A24_OR_T21_FREEZE_SELECTED")
        schedule = build_schedule(
            [item for item in cells if isinstance(item, Mapping)],
            panel_started_at=started_at,
        )
        panel_started = _format_utc(started_at)
    results: dict[str, dict[str, Any]] = {}
    selected_ids: list[str] = []
    for row in schedule:
        observation_id = str(row["observation_id"])
        due_at = datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00"))
        terminal = row.get("terminal")
        already_consumed = bool(row.get("consumed_call")) or (
            terminal not in {None, ""} and str(terminal) not in CONTINUABLE
        )
        parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
        parent_quoted = isinstance(parent, Mapping) and parent.get("terminal") == "QUOTE_OBSERVED"
        if not select_horizon:
            selected = str(row["wave"]) == "t0" and not already_consumed
        else:
            late = started_at > due_at + timedelta(seconds=SLACK)
            selected = (
                str(row["wave"]) == "horizon"
                and str(row["kind"]) in {"SELL_H900", "SELL_H3600"}
                and not already_consumed
                and str(terminal or "SCHEDULED") in CONTINUABLE
                and due_at <= started_at
                and not late
                and parent_quoted
            )
            if (
                str(row["wave"]) == "horizon"
                and str(terminal or "SCHEDULED") in CONTINUABLE
                and parent_quoted
                and late
            ):
                row["terminal"] = "MISSED_OFFSET"
                row["consumed_call"] = False
        if selected:
            selected_ids.append(observation_id)
        elif not select_horizon and str(row["wave"]) == "horizon":
            row["terminal"] = "SCHEDULED"
            row["consumed_call"] = False
        elif not select_horizon and str(row["wave"]) == "gap":
            row["terminal"] = "EXPLICIT_GAP"
            row["consumed_call"] = False
        results[observation_id] = dict(row)

    provider_requests = 0
    stop_code: str | None = None
    remaining_cap = CALL_CAP - prior_requests
    _require(remaining_cap >= 0, "CALL_CAP_EXCEEDED")
    halted = False
    order_policy = _order_policy(policy)
    for row in schedule:
        observation_id = str(row["observation_id"])
        if observation_id not in selected_ids:
            continue
        if halted:
            results[observation_id] = _halted_remainder(row, results=results)
            continue
        parent = results.get(str(row["parent_id"])) if row.get("parent_id") else None
        amount = row.get("amount")
        if row["kind"] != "BUY_T0":
            parent_quote = parent.get("quote") if parent else None
            parent_ok = (
                isinstance(parent, Mapping)
                and parent.get("terminal") == "QUOTE_OBSERVED"
                and isinstance(parent_quote, Mapping)
                and type(parent_quote.get("out_amount")) is str
                and bool(parent_quote.get("out_amount"))
            )
            if not parent_ok:
                results[observation_id] = {
                    **row,
                    "terminal": "SKIPPED_NO_ENTRY",
                    "consumed_call": False,
                    "quote": None,
                }
                continue
            amount = parent_quote["out_amount"]
        if provider_requests >= remaining_cap:
            stop_code = "CALL_CAP_EXCEEDED"
            halted = True
            results[observation_id] = _halted_remainder(row, results=results)
            continue
        request = {
            "input_mint": str(row["input_mint"]),
            "output_mint": str(row["output_mint"]),
            "amount": str(amount),
        }
        observed_at = tick()
        _pace(last_call_at=last_call, now=observed_at, sleeper=wait)
        observed_at = tick()
        observed = execute_observation(order_policy, request, opener=opener)
        provider_requests += 1
        last_call = _format_utc(observed_at)
        terminal = str(observed["terminal"])
        body = observed.get("body")
        results[observation_id] = {
            **row,
            "amount": request["amount"],
            "observed_at": last_call,
            "terminal": terminal,
            "terminal_error": observed.get("terminal_error"),
            "transport": observed.get("transport"),
            "quote": observed.get("quote"),
            "raw_sha256": hashlib.sha256(body).hexdigest() if isinstance(body, (bytes, bytearray)) else None,
            "body": body,
            "consumed_call": True,
        }
        if terminal in {"CREDENTIAL_REQUIRED_NOT_AUTHORIZED", "PANEL_PROTOCOL_FAIL"}:
            stop_code = terminal
            halted = True
            continue
        if terminal in {"RATE_LIMITED", "TRANSPORT_OR_QUOTE_UNKNOWN"}:
            stop_code = "PANEL_RATE_LIMITED" if terminal == "RATE_LIMITED" else "PANEL_TRANSPORT_UNKNOWN"
            halted = True

    observations = []
    raw_bodies: dict[str, bytes] = {}
    for row in schedule:
        recorded = dict(results[str(row["observation_id"])])
        body = recorded.pop("body", None)
        if isinstance(body, (bytes, bytearray)):
            raw_bodies[str(row["observation_id"])] = bytes(body)
        observations.append(recorded)
    campaign = score_campaign(observations)
    t0_buys_quoted = sum(
        1
        for item in observations
        if str(item.get("kind")) == "BUY_T0" and str(item.get("terminal")) == "QUOTE_OBSERVED"
    )
    if stop_code is None:
        if not select_horizon:
            stop_code = "T0_VARIATION_CLOCK_ARMED" if t0_buys_quoted >= 2 else "SECOND_IDENTITY_PROTOCOL_FAIL"
        else:
            stop_code = str(campaign["campaign_verdict"])
    prior_discovery = prior_receipt.get("discovery_observations")
    prior_cells = prior_receipt.get("frozen_cells")
    return {
        "schema": "smial.quote-native-live-variation-campaign.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "route_id": ROUTE_ID,
        "owner_phrase": AUTHORITY_PHRASE,
        "terminal_outcome": stop_code,
        "started_at": _format_utc(started_at),
        "panel_started_at": panel_started,
        "wave": "due" if select_horizon else "t0",
        "preflight": dict(preflight),
        "provider_requests": prior_requests + provider_requests,
        "new_provider_requests": provider_requests,
        "last_provider_call_at": last_call,
        "retries": 0,
        "fallbacks": 0,
        "credential_reads": 0,
        "execute_calls": 0,
        "frozen_cells": list(prior_cells) if isinstance(prior_cells, list) else [],
        "discovery_observations": list(prior_discovery) if isinstance(prior_discovery, list) else [],
        "observations": observations,
        "campaign": campaign,
        "raw_bodies": raw_bodies,
        "non_claims": _non_claims(),
        "limitations": ["LIVE_SAMPLE_NOT_A_CONFIRMATORY_TRIAL", "H14400_EXPLICIT_GAP_NO_BACKFILL"],
    }
