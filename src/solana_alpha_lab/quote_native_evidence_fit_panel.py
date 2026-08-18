"""Quote-native Jupiter V2 /order measurement panel, keyless and quote-only."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import yaml

from solana_alpha_lab.pmf_quote_slice_one_shot import (
    EXPECTED_HOST,
    QuoteShotError,
    QuoteShotTerminalError,
    credential_free_preflight,
    perform_http_get_once,
)

ATOM_ID = "QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1: Jupiter /swap/v2/order quote-only, "
    "taker omitted, execute forbidden, wallet/signer/transaction forbidden, "
    "cash cap $0, no retry/fallback, call cap 40, bind registry v7 route "
    "JUPITER-SOLANA-SWAP-V2-ORDER-001"
)
CONFIG_RELATIVE = "configs/quote_native_evidence_fit_panel_v1.yaml"
ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_ENDPOINT = "https://api.jup.ag/swap/v2/order"
WRAPPED_SOL = "So11111111111111111111111111111111111111112"
A24_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
T21_MINTS = (
    "2Ezm4w3gFdymRAyhx9KEsbJV9NA79Y7UoiNWeXNFpump",
    "2HU2VftbJ7Fp9P5pEbneNsRhax8boHhTVS1KLnYrpump",
    "2JdM5MHiXjsQz5QgnSQfbidZDTVXCLki74jMYgJapump",
)
NOTIONALS = ("10000000", "1000000")
HORIZONS = (900, 3600, 14400)
CALL_CAP = 40
T0_CALL_CAP = 16
V7_RELATIVE = "configs/provider_route_capability_registry_v7.yaml"
SLICE_RELATIVE = "configs/pmf_quote_slice_v1.yaml"
T21_RELATIVE = "configs/task21_final_cohort_freeze_v1.yaml"
PROTOCOL_COMPARABLE = frozenset({"QUOTE_OBSERVED", "NO_ROUTE", "PROVIDER_TYPED_FAILURE"})
CONTINUABLE = frozenset({"SCHEDULED", "NOT_REACHED"})


class PanelError(ValueError):
    """The bounded quote-native panel cannot be satisfied."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PanelError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _optional_field(payload: Mapping[str, Any], key: str) -> dict[str, object]:
    if key not in payload:
        return {"status": "ABSENT", "value": None}
    value = payload[key]
    if value is None:
        return {"status": "NULL", "value": None}
    return {"status": "OBSERVED", "value": value}


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    route = _mapping(policy.get("provider_route"), "ROUTE_INVALID")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    identities = policy.get("identities")
    notionals = policy.get("notionals_atomic")
    horizons = policy.get("horizon_seconds")
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
    _require(route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_DRIFT")
    _require(route.get("method") == "GET", "METHOD_DRIFT")
    _require(route.get("host") == EXPECTED_HOST, "HOST_DRIFT")
    _require(route.get("registry") == V7_RELATIVE, "REGISTRY_BIND_DRIFT")
    v7_route = _v7_route(root)
    _require(v7_route.get("access_class") == "KEYLESS", "V7_ACCESS_CLASS_DRIFT")
    _require(v7_route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(policy.get("wrapped_sol_mint") == WRAPPED_SOL, "SOL_MINT_DRIFT")
    _require(str(policy.get("slippage_bps")) == "100", "SLIPPAGE_DRIFT")
    _require(isinstance(identities, list) and len(identities) == 4, "IDENTITY_COUNT_DRIFT")
    _require(tuple(str(item) for item in notionals) == NOTIONALS, "NOTIONAL_DRIFT")
    _require(tuple(int(item) for item in horizons) == HORIZONS, "HORIZON_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("live_market_discovery") is False, "LIVE_DISCOVERY_NOT_FORBIDDEN")
    _require(int(controls.get("provider_requests_max", 0)) == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(int(controls.get("t0_provider_requests_max", 0)) == T0_CALL_CAP, "T0_BUDGET_DRIFT")
    _require(float(limits.get("timeout_seconds", 0)) > 0, "TIMEOUT_INVALID")
    _require(int(limits.get("max_response_bytes", 0)) > 0, "MAX_BYTES_INVALID")
    observed_mints: list[str] = []
    for index, raw_identity in enumerate(identities):
        identity = _mapping(raw_identity, "IDENTITY_INVALID")
        _require(identity.get("source_kind") == "GIT_FROZEN", "LIVE_DISCOVERY_NOT_FORBIDDEN")
        mint = str(identity.get("mint"))
        observed_mints.append(mint)
        source_path = root / str(identity.get("source_path"))
        _require(source_path.is_file(), "IDENTITY_SOURCE_MISSING")
        _require(mint in source_path.read_text(encoding="utf-8"), "IDENTITY_SOURCE_DRIFT")
        if index == 0:
            _require(mint == A24_MINT, "A24_IDENTITY_DRIFT")
            _require(identity.get("identity_id") == "A24_POST_MIGRATION", "A24_ID_DRIFT")
            _require(str(identity.get("source_path")) == SLICE_RELATIVE, "A24_SOURCE_DRIFT")
    _require(tuple(observed_mints[1:]) == T21_MINTS, "T21_IDENTITY_DRIFT")
    _require(len(set(observed_mints)) == 4, "IDENTITY_NOT_INDEPENDENT")


def _v7_route(root: Path) -> Mapping[str, Any]:
    document = yaml.safe_load((root / V7_RELATIVE).read_text(encoding="utf-8"))
    _require(isinstance(document, Mapping), "V7_INVALID")
    routes = document.get("routes")
    _require(isinstance(routes, list), "V7_INVALID")
    for raw in routes:
        route = _mapping(raw, "V7_INVALID")
        if route.get("route_id") == ROUTE_ID:
            return route
    raise PanelError("V7_ROUTE_MISSING")


def bind_identity_sources(root: Path) -> dict[str, str]:
    route = _v7_route(root)
    _require(route.get("access_class") == "KEYLESS", "V7_ACCESS_CLASS_DRIFT")
    return {
        "provider_route_registry_v7_sha256": _sha256_file(root / V7_RELATIVE),
        "v7_access_class": "KEYLESS",
        "task21_final_cohort_freeze_sha256": _sha256_file(root / T21_RELATIVE),
    }


def build_order_url(
    *,
    input_mint: str,
    output_mint: str,
    amount: str,
    slippage_bps: str = "100",
) -> str:
    query = urlencode(
        [
            ("inputMint", input_mint),
            ("outputMint", output_mint),
            ("amount", amount),
            ("slippageBps", slippage_bps),
        ]
    )
    url = f"{EXPECTED_ENDPOINT}?{query}"
    _require("taker" not in url.lower(), "TAKER_IN_URL")
    parsed = urlsplit(url)
    _require(parsed.scheme == "https", "ENDPOINT_DRIFT")
    _require(parsed.hostname == EXPECTED_HOST, "HOST_DRIFT")
    _require(parsed.path == "/swap/v2/order", "ENDPOINT_DRIFT")
    return url


def project_quote(body: bytes) -> dict[str, object]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PanelError("QUOTE_JSON_INVALID") from exc
    _require(isinstance(payload, dict), "QUOTE_JSON_INVALID")
    _require(payload.get("transaction") is None, "QUOTE_RETURNED_TRANSACTION")
    error_code = payload.get("errorCode") or payload.get("error")
    in_amount = payload.get("inAmount")
    out_amount = payload.get("outAmount")
    router = payload.get("router")
    mode = payload.get("mode")
    route_plan = _optional_field(payload, "routePlan")
    hop_count = None
    fee_amounts_present = False
    if route_plan["status"] == "OBSERVED" and isinstance(route_plan["value"], list):
        hop_count = len(route_plan["value"])
        for hop in route_plan["value"]:
            if isinstance(hop, Mapping):
                info = hop.get("swapInfo")
                if isinstance(info, Mapping) and info.get("feeAmount") not in {None, ""}:
                    fee_amounts_present = True
                    break
    quote = {
        "in_amount": in_amount if type(in_amount) is str and in_amount else None,
        "out_amount": out_amount if type(out_amount) is str and out_amount else None,
        "router": router if type(router) is str and router else None,
        "mode": mode if type(mode) is str and mode else None,
        "transaction_present": False,
        "request_id_present": type(payload.get("requestId")) is str and bool(payload.get("requestId")),
        "error_code": error_code if error_code not in {None, ""} else None,
        "price_impact_pct": _optional_field(payload, "priceImpactPct"),
        "platform_fee": _optional_field(payload, "platformFee"),
        "fee_bps": _optional_field(payload, "feeBps"),
        "route_plan": {
            "status": route_plan["status"],
            "hop_count": hop_count,
            "fee_amounts_present": fee_amounts_present,
        },
    }
    if quote["in_amount"] and quote["out_amount"] and quote["router"] and quote["mode"]:
        quote["surface"] = "QUOTE_OBSERVED"
        return quote
    if quote["error_code"]:
        code = str(quote["error_code"]).upper()
        quote["surface"] = "NO_ROUTE" if "ROUTE" in code else "PROVIDER_TYPED_FAILURE"
        return quote
    raise PanelError("QUOTE_SHAPE_INCOMPARABLE")


def _one_shot_policy(panel_policy: Mapping[str, Any], request: Mapping[str, str]) -> dict[str, object]:
    route = _mapping(panel_policy.get("provider_route"), "ROUTE_INVALID")
    limits = _mapping(panel_policy.get("runtime_limits"), "LIMITS_INVALID")
    return {
        "provider_route": {
            "endpoint": route["endpoint"],
            "host": route["host"],
            "method": "GET",
        },
        "request": {
            "inputMint": request["input_mint"],
            "outputMint": request["output_mint"],
            "amount": request["amount"],
            "slippageBps": str(panel_policy.get("slippage_bps")),
        },
        "runtime_limits": dict(limits),
    }


def build_schedule(policy: Mapping[str, Any], *, panel_started_at: datetime) -> list[dict[str, object]]:
    identities = policy.get("identities")
    _require(isinstance(identities, list), "IDENTITY_INVALID")
    started = panel_started_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows: list[dict[str, object]] = []
    for identity in identities:
        mapped = _mapping(identity, "IDENTITY_INVALID")
        mint = str(mapped["mint"])
        identity_id = str(mapped["identity_id"])
        for notional in NOTIONALS:
            buy_id = f"{identity_id}:{notional}:BUY_T0"
            rows.append(
                {
                    "observation_id": buy_id,
                    "identity_id": identity_id,
                    "mint": mint,
                    "kind": "BUY_T0",
                    "wave": "t0",
                    "input_mint": WRAPPED_SOL,
                    "output_mint": mint,
                    "amount": notional,
                    "parent_id": None,
                    "due_at": started,
                    "horizon_seconds": 0,
                }
            )
            rows.append(
                {
                    "observation_id": f"{identity_id}:{notional}:REVERSE_T0",
                    "identity_id": identity_id,
                    "mint": mint,
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
            for horizon in HORIZONS:
                due = panel_started_at.astimezone(UTC) + timedelta(seconds=horizon)
                rows.append(
                    {
                        "observation_id": f"{identity_id}:{notional}:SELL_H{horizon}",
                        "identity_id": identity_id,
                        "mint": mint,
                        "kind": f"SELL_H{horizon}",
                        "wave": "horizon",
                        "input_mint": mint,
                        "output_mint": WRAPPED_SOL,
                        "amount": None,
                        "parent_id": buy_id,
                        "due_at": due.isoformat(timespec="seconds").replace("+00:00", "Z"),
                        "horizon_seconds": horizon,
                    }
                )
    _require(len(rows) == 40, "SCHEDULE_COUNT_DRIFT")
    return rows


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def execute_observation(
    panel_policy: Mapping[str, Any],
    request: Mapping[str, str],
    *,
    opener: object | None = None,
) -> dict[str, object]:
    shot_policy = _one_shot_policy(panel_policy, request)
    build_order_url(
        input_mint=request["input_mint"],
        output_mint=request["output_mint"],
        amount=request["amount"],
        slippage_bps=str(panel_policy.get("slippage_bps")),
    )
    try:
        raw = perform_http_get_once(shot_policy, "", opener=opener)
    except QuoteShotTerminalError as exc:
        evidence = dict(exc.evidence)
        return {
            "terminal": "TRANSPORT_OR_QUOTE_UNKNOWN",
            "terminal_error": str(exc),
            "transport": dict(evidence.get("transport") or {"request_count": 1}),
            "quote": None,
            "body": evidence.get("body"),
        }
    except QuoteShotError as exc:
        return {
            "terminal": "TRANSPORT_OR_QUOTE_UNKNOWN",
            "terminal_error": str(exc),
            "transport": {"request_count": 1},
            "quote": None,
            "body": None,
        }
    transport = {
        "http_status": raw["http_status"],
        "content_type": raw["content_type"],
        "response_bytes": raw["response_bytes"],
        "response_sha256": raw["response_sha256"],
        "request_count": 1,
        "url_has_taker": "taker" in str(raw["url"]).lower(),
        "url_has_api_key": False,
    }
    status = int(raw["http_status"])
    body = raw["body"]
    if status in {401, 403}:
        return {
            "terminal": "CREDENTIAL_REQUIRED_NOT_AUTHORIZED",
            "terminal_error": "HTTP_STATUS_ERROR",
            "transport": transport,
            "quote": None,
            "body": body,
        }
    if status == 429:
        return {
            "terminal": "RATE_LIMITED",
            "terminal_error": "HTTP_429",
            "transport": transport,
            "quote": None,
            "body": body,
        }
    try:
        quote = project_quote(body) if isinstance(body, (bytes, bytearray)) else None
    except PanelError as exc:
        terminal = "PANEL_PROTOCOL_FAIL" if str(exc) == "QUOTE_RETURNED_TRANSACTION" else "QUOTE_SHAPE_INCOMPARABLE"
        return {
            "terminal": terminal,
            "terminal_error": str(exc),
            "transport": transport,
            "quote": None,
            "body": body,
        }
    assert quote is not None
    terminal = str(quote["surface"])
    if status != 200 and terminal == "QUOTE_OBSERVED":
        terminal = "PROVIDER_TYPED_FAILURE"
    return {
        "terminal": terminal,
        "terminal_error": None if status == 200 and terminal == "QUOTE_OBSERVED" else f"HTTP_{status}",
        "transport": transport,
        "quote": quote,
        "body": body,
    }


def _identity_status(policy: Mapping[str, Any]) -> dict[str, str]:
    identities = policy.get("identities")
    _require(isinstance(identities, list), "IDENTITY_INVALID")
    status: dict[str, str] = {}
    for raw in identities:
        identity = _mapping(raw, "IDENTITY_INVALID")
        status[str(identity["identity_id"])] = str(identity["post_migration_status"])
    return status


def _ticking_clock(start: datetime) -> Callable[[], datetime]:
    state = {"n": 0}

    def _tick() -> datetime:
        current = start + timedelta(seconds=state["n"])
        state["n"] += 1
        return current

    return _tick


def _halted_remainder(
    row: Mapping[str, Any],
    *,
    results: Mapping[str, Mapping[str, Any]],
    status_by_id: Mapping[str, str],
) -> dict[str, Any]:
    observation_id = str(row["observation_id"])
    recorded = dict(results.get(observation_id) or row)
    recorded["post_migration_status"] = status_by_id[str(row["identity_id"])]
    recorded["consumed_call"] = False
    if str(row.get("wave")) == "horizon":
        if str(recorded.get("terminal") or "SCHEDULED") == "SCHEDULED":
            recorded["terminal"] = "SCHEDULED"
        return recorded
    parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
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
) -> dict[str, object]:
    validate_policy(policy, root=root)
    _require(wave in {"t0", "due"}, "WAVE_INVALID")
    if wave == "due":
        _require(isinstance(prior_receipt, Mapping), "PRIOR_RECEIPT_REQUIRED")
    bindings = bind_identity_sources(root)
    started_at = now.astimezone(UTC)
    tick = clock or _ticking_clock(started_at)
    status_by_id = _identity_status(policy)
    prior_requests = 0
    if wave == "due":
        assert prior_receipt is not None
        raw_schedule = prior_receipt.get("observations")
        _require(isinstance(raw_schedule, list) and raw_schedule, "PRIOR_SCHEDULE_INVALID")
        schedule = [dict(item) for item in raw_schedule if isinstance(item, Mapping)]
        _require(len(schedule) == 40, "SCHEDULE_COUNT_DRIFT")
        prior_requests = int(prior_receipt.get("provider_requests", 0))
        _require(prior_requests >= 0, "PRIOR_REQUESTS_INVALID")
    else:
        schedule = build_schedule(policy, panel_started_at=started_at)
    preflight = dict(
        preflight_fn(
            {
                "provider_route": {
                    "endpoint": EXPECTED_ENDPOINT,
                    "host": EXPECTED_HOST,
                    "method": "GET",
                }
            },
            observed_at=_format_utc(started_at),
        )
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    results: dict[str, dict[str, Any]] = {}
    selected_ids: list[str] = []
    for row in schedule:
        observation_id = str(row["observation_id"])
        row["post_migration_status"] = status_by_id[str(row["identity_id"])]
        due_at = datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00"))
        terminal = row.get("terminal")
        already_consumed = bool(row.get("consumed_call")) or (
            terminal not in {None, ""} and str(terminal) not in CONTINUABLE
        )
        parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
        parent_quoted = isinstance(parent, Mapping) and parent.get("terminal") == "QUOTE_OBSERVED"
        if wave == "t0":
            selected = str(row["wave"]) == "t0" and not already_consumed
        else:
            selected = (
                str(row["wave"]) == "horizon"
                and not already_consumed
                and str(terminal) in CONTINUABLE
                and due_at <= started_at
                and parent_quoted
            )
        if selected:
            selected_ids.append(observation_id)
        elif wave == "t0" and str(row["wave"]) != "t0":
            row["terminal"] = "SCHEDULED"
            row["consumed_call"] = False
        results[observation_id] = dict(row)

    provider_requests = 0
    stop_code: str | None = None
    comparable_identities: list[str] = []
    quoted_identities: list[str] = []
    for item in results.values():
        identity_id = str(item["identity_id"])
        terminal = str(item.get("terminal") or "")
        if identity_id not in comparable_identities and terminal in PROTOCOL_COMPARABLE:
            comparable_identities.append(identity_id)
        if identity_id not in quoted_identities and terminal == "QUOTE_OBSERVED":
            quoted_identities.append(identity_id)
    remaining_cap = (T0_CALL_CAP if wave == "t0" else CALL_CAP) - prior_requests
    _require(remaining_cap >= 0, "CALL_CAP_EXCEEDED")
    halted = False
    for row in schedule:
        observation_id = str(row["observation_id"])
        if observation_id not in selected_ids:
            continue
        if halted:
            results[observation_id] = _halted_remainder(
                row,
                results=results,
                status_by_id=status_by_id,
            )
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
                    "post_migration_status": status_by_id[str(row["identity_id"])],
                }
                continue
            amount = parent_quote["out_amount"]
        if provider_requests >= remaining_cap:
            stop_code = "CALL_CAP_EXCEEDED"
            halted = True
            results[observation_id] = _halted_remainder(
                row,
                results=results,
                status_by_id=status_by_id,
            )
            continue
        request = {
            "input_mint": str(row["input_mint"]),
            "output_mint": str(row["output_mint"]),
            "amount": str(amount),
        }
        observed_at = tick()
        observed = execute_observation(policy, request, opener=opener)
        provider_requests += 1
        identity_id = str(row["identity_id"])
        terminal = str(observed["terminal"])
        if identity_id not in comparable_identities and terminal in PROTOCOL_COMPARABLE:
            comparable_identities.append(identity_id)
        if identity_id not in quoted_identities and terminal == "QUOTE_OBSERVED":
            quoted_identities.append(identity_id)
        body = observed.get("body")
        results[observation_id] = {
            **row,
            "amount": request["amount"],
            "observed_at": _format_utc(observed_at),
            "terminal": terminal,
            "terminal_error": observed.get("terminal_error"),
            "transport": observed.get("transport"),
            "quote": observed.get("quote"),
            "raw_sha256": hashlib.sha256(body).hexdigest() if isinstance(body, (bytes, bytearray)) else None,
            "body": body,
            "consumed_call": True,
            "post_migration_status": status_by_id[identity_id],
        }
        if terminal in {"CREDENTIAL_REQUIRED_NOT_AUTHORIZED", "PANEL_PROTOCOL_FAIL"}:
            stop_code = terminal
            halted = True
            continue
        if terminal in {"RATE_LIMITED", "TRANSPORT_OR_QUOTE_UNKNOWN"}:
            stop_code = (
                "RATE_LIMIT_STOPPED_REMAINING"
                if terminal == "RATE_LIMITED"
                else "TRANSPORT_STOPPED_REMAINING"
            )
            halted = True
            continue
        if terminal == "QUOTE_SHAPE_INCOMPARABLE" and identity_id != "A24_POST_MIGRATION":
            stop_code = "SECOND_IDENTITY_PROTOCOL_FAIL"
            halted = True

    for observation_id, item in list(results.items()):
        if str(item.get("wave")) != "horizon":
            continue
        if str(item.get("terminal") or "SCHEDULED") != "SCHEDULED":
            continue
        parent = results.get(str(item.get("parent_id") or ""))
        if not isinstance(parent, Mapping):
            continue
        parent_terminal = str(parent.get("terminal") or "")
        if parent_terminal in {"QUOTE_OBSERVED", "NOT_REACHED", "SCHEDULED", ""}:
            continue
        results[observation_id] = {
            **item,
            "terminal": "SKIPPED_NO_ENTRY",
            "consumed_call": False,
            "quote": None,
            "post_migration_status": status_by_id[str(item["identity_id"])],
        }

    second_protocol = "T21_R2_MINT_A" in comparable_identities
    if stop_code in {None, "RATE_LIMIT_STOPPED_REMAINING", "TRANSPORT_STOPPED_REMAINING"}:
        if "A24_POST_MIGRATION" in quoted_identities and second_protocol:
            stop_code = "T0_PANEL_OBSERVED"
        elif stop_code == "RATE_LIMIT_STOPPED_REMAINING":
            stop_code = "PANEL_RATE_LIMITED"
        elif stop_code == "TRANSPORT_STOPPED_REMAINING":
            stop_code = "PANEL_TRANSPORT_UNKNOWN"
        elif "T21_R2_MINT_A" not in comparable_identities and not any(
            item.get("identity_id") == "T21_R2_MINT_A" and item.get("consumed_call")
            for item in results.values()
        ):
            stop_code = "SECOND_IDENTITY_PROTOCOL_FAIL"
        else:
            stop_code = "PANEL_PROTOCOL_FAIL"

    observations = []
    raw_bodies: dict[str, bytes] = {}
    for row in schedule:
        recorded = dict(results[str(row["observation_id"])])
        body = recorded.pop("body", None)
        if isinstance(body, (bytes, bytearray)):
            raw_bodies[str(row["observation_id"])] = bytes(body)
        observations.append(recorded)

    return {
        "schema": "smial.quote-native-evidence-fit-panel.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "route_id": ROUTE_ID,
        "owner_phrase": AUTHORITY_PHRASE,
        "terminal_outcome": stop_code,
        "started_at": _format_utc(started_at),
        "panel_started_at": (
            str(prior_receipt.get("panel_started_at") or prior_receipt.get("started_at"))
            if wave == "due" and prior_receipt is not None
            else _format_utc(started_at)
        ),
        "wave": wave,
        "identity_bindings": bindings,
        "preflight": preflight,
        "provider_requests": prior_requests + provider_requests,
        "new_provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "credential_reads": 0,
        "execute_calls": 0,
        "comparable_identities": comparable_identities,
        "quoted_identities": quoted_identities,
        "limitations": ["RATE_LIMIT_STOPPED_REMAINING_CELLS"]
        if any(item.get("terminal") == "RATE_LIMITED" for item in results.values())
        else [],
        "observations": observations,
        "raw_bodies": raw_bodies,
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_CANONICAL_DONE",
            "NO_H13_OR_H02_TRIAL",
            "NOT_A_HYPOTHESIS_TRIAL",
            "NO_POST_MIGRATION_INFERENCE_FOR_UNPROVEN_T21",
        ],
    }
