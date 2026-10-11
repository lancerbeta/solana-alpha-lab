"""Ordinary model/quote adapters. Quotes never represent chain inventory.

The HTTP boundary is closed unless an exact bounded quote grant is supplied.
Tests replace only the lowest transport. No wallet, build or execute path exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import math
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError
from solana_alpha_lab.factory.hfic_research_scope import sha256_of

ENDPOINT = "https://api.jup.ag/swap/v2/order"
ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001"
REGISTRY_PATH = "configs/provider_route_capability_registry_v11.yaml"


def verified_quote_grant(root, raw):
    """Public authority bytes only. This never opens a credential or provider."""
    import yaml
    registry = yaml.safe_load((root / REGISTRY_PATH).read_text(encoding="utf-8"))
    route = next((item for item in registry["routes"] if item["route_id"] == ROUTE_ID), None)
    if (route is None or route["operation"] != "FREE_API_KEY_QUOTE_ONLY_ORDER_WITHOUT_TAKER"
        or raw.get("registry_path") != REGISTRY_PATH
        or raw.get("registry_sha256") != hashlib.sha256((root / REGISTRY_PATH).read_bytes()).hexdigest()):
        raise PaperPlaneError("QUOTE_ROUTE_REGISTRY_BINDING_CONFLICT")
    if raw.get("grant_sha256") != sha256_of({key: value for key, value in raw.items() if key != "grant_sha256"}):
        raise PaperPlaneError("QUOTE_GRANT_INTEGRITY_CONFLICT")
    return dict(raw)


def decimal_value(value, *, positive=True):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or (amount <= 0 if positive else amount < 0):
            raise ValueError()
        return amount
    except (ValueError, ArithmeticError):
        raise PaperPlaneError("ADAPTER_AMOUNT_INVALID") from None


def checked_observation(raw, *, mint, as_of, max_age_seconds):
    if raw.get("mint") != mint or type(raw.get("decimals")) is not int or not 0 <= raw["decimals"] <= 18:
        raise PaperPlaneError("EXECUTION_ASSET_IDENTITY_INVALID")
    now = parse_utc(as_of)
    observed, available = parse_utc(raw["observed_at"]), parse_utc(raw["available_at"])
    if observed > available or available > now or (now - observed).total_seconds() > max_age_seconds:
        raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
    return {**raw, "unit_price_usd": str(decimal_value(raw["unit_price_usd"]))}


class PaperModelAdapter:
    """Versioned deterministic model over frozen, timely observations."""
    def __init__(self, model):
        if model.get("version") != "TIMELY_OBSERVATION_MODEL_V1" or model.get("missing_input") != "UNKNOWN":
            raise PaperPlaneError("PAPER_MODEL_CONFIGURATION_REQUIRED")
        if type(model.get("latency_seconds")) not in {int, float} or not math.isfinite(model["latency_seconds"]) or not 0 <= model["latency_seconds"] <= 86400:
            raise PaperPlaneError("PAPER_MODEL_LATENCY_INVALID")
        self.model = dict(model)
        if model.get("additional_cost_usd") is not None:
            decimal_value(model["additional_cost_usd"], positive=False)

    def reconcile(self, attempt, request, *, as_of):
        if sha256_of({k: v for k, v in request.items() if k != "request_sha256"}) != request.get("request_sha256"):
            raise PaperPlaneError("ADAPTER_REQUEST_INTEGRITY_CONFLICT")
        # No source reads here: restart recomputes the same deterministic effect.
        price = request.get("unit_price_usd")
        result = {"attempt_id": attempt["attempt_id"],
                  "result_id": "MODEL-" + attempt["attempt_id"], "observed_at": request["result_at"],
                  "outcome": "LANDED_SUCCESS" if price is not None else "UNKNOWN_REQUIRES_RECONCILIATION",
                  "chargeable_cost_usd": self.model.get("additional_cost_usd")}
        if parse_utc(as_of) < parse_utc(request["result_at"]):
            return None
        if price is not None:
            result["unit_price_usd"] = str(decimal_value(price))
            if attempt["side"] == "ENTRY":
                result["filled_notional_usd"] = request["admitted_notional_usd"]
        return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def http_quote(request, *, timeout_seconds, max_response_bytes, api_key):
    """Exactly one real HTTPS GET; no redirect, retry or response exception text."""
    url = ENDPOINT + "?" + urllib.parse.urlencode(request)
    headers = {"Accept": "application/json", "User-Agent": "smial-shadow-quote/1.0"}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout_seconds) as response:
            body = response.read(max_response_bytes + 1)
            return {"status": response.status, "body": body, "url": response.geturl()}
    except urllib.error.HTTPError as error:
        return {"status": error.code, "body": b"", "url": url}
    except (OSError, TimeoutError):
        return {"status": None, "body": b"", "url": url}


class JupiterQuoteAdapter:
    def __init__(self, *, timeout_seconds, max_response_bytes, transport=None, grant=None, credential_supplier=None):
        if type(timeout_seconds) not in {int, float} or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120 or type(max_response_bytes) is not int or not 0 < max_response_bytes <= 1048576:
            raise PaperPlaneError("QUOTE_LIMIT_CONFIGURATION_INVALID")
        self.timeout, self.max_bytes = timeout_seconds, max_response_bytes
        self.transport = transport
        self.grant = grant
        self.credential_supplier = credential_supplier
        self.calls = 0

    def dispatch(self, attempt, request, *, as_of):
        as_of = self.result_clock() if getattr(self,"result_clock",None) else as_of
        if request.get("entry_send_valid_until") and parse_utc(as_of)>parse_utc(request["entry_send_valid_until"]):
            raise PaperPlaneError("QUOTE_ENTRY_SEND_EXPIRED")
        if request.get("funding_valid_until") and parse_utc(as_of)>parse_utc(request["funding_valid_until"]):
            raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
        raw_request = {key: request[key] for key in ("inputMint", "outputMint", "amount")}
        if any(not isinstance(raw_request[key], str) for key in raw_request):
            raise PaperPlaneError("QUOTE_REQUEST_INVALID")
        for key in ("inputMint", "outputMint"):
            if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", raw_request[key]):
                raise PaperPlaneError("QUOTE_MINT_INVALID")
        if raw_request["inputMint"] == raw_request["outputMint"] or not re.fullmatch(r"[1-9][0-9]{0,29}", raw_request["amount"]):
            raise PaperPlaneError("QUOTE_RAW_AMOUNT_INVALID")
        if sha256_of({k: v for k, v in request.items() if k != "request_sha256"}) != request.get("request_sha256"):
            raise PaperPlaneError("ADAPTER_REQUEST_INTEGRITY_CONFLICT")
        if any(type(request.get(key)) is not int or not 0 <= request[key] <= 18 for key in ("input_decimals", "output_decimals")):
            raise PaperPlaneError("QUOTE_DECIMALS_INVALID")
        credential = None
        if self.transport is None:
            grant = self.grant or {}
            if (grant.get("quote_calls_authorized") is not True or grant.get("route_id") != ROUTE_ID
                or grant.get("endpoint") != ENDPOINT or grant.get("registry_path") != REGISTRY_PATH
                or grant.get("mode") != "SHADOW" or grant.get("activation_epoch_id") != request["activation_epoch_id"]
                or grant.get("strategy_sha256") != request["strategy_sha256"]
                or grant.get("signing_authorized") is not False or grant.get("financial_authority") is not False
                or type(grant.get("calls_max")) is not int or not 0 < grant["calls_max"] <= 1000000 or self.calls >= grant["calls_max"]
                or parse_utc(as_of) > parse_utc(grant["expires_at"])):
                raise PaperPlaneError("QUOTE_EXTERNAL_AUTHORITY_REQUIRED")
            if self.credential_supplier is None:
                raise PaperPlaneError("QUOTE_CREDENTIAL_CONFIGURATION_REQUIRED")
            credential = self.credential_supplier()
        # Credential acquisition can itself block. Check physical validity at
        # the last reversible boundary immediately before the one HTTP call.
        as_of=self.result_clock() if getattr(self,"result_clock",None) else as_of
        if request.get("entry_send_valid_until") and parse_utc(as_of)>parse_utc(request["entry_send_valid_until"]):
            raise PaperPlaneError("QUOTE_ENTRY_SEND_EXPIRED")
        if request.get("funding_valid_until") and parse_utc(as_of)>parse_utc(request["funding_valid_until"]):
            raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
        if self.transport is None and parse_utc(as_of)>parse_utc(self.grant["expires_at"]):
            raise PaperPlaneError("QUOTE_EXTERNAL_AUTHORITY_REQUIRED")
        self.calls += 1
        response = (self.transport or http_quote)(raw_request, timeout_seconds=self.timeout,
            max_response_bytes=self.max_bytes, api_key=credential)
        completed = self.result_clock() if getattr(self,"result_clock",None) else as_of
        return self.project_response(attempt, request, response, as_of=completed)

    def project_response(self, attempt, request, response, *, as_of):
        """Project a retained original response; no request/retry/credential IO."""
        if sha256_of({k: v for k, v in request.items() if k != "request_sha256"}) != request.get("request_sha256"):
            raise PaperPlaneError("ADAPTER_REQUEST_INTEGRITY_CONFLICT")
        raw_request = {key: request[key] for key in ("inputMint", "outputMint", "amount")}
        result = {"attempt_id": attempt["attempt_id"], "result_id": "QUOTE-" + attempt["attempt_id"],
                  "observed_at": as_of, "outcome": "UNKNOWN_REQUIRES_RECONCILIATION"}
        expected_url = ENDPOINT + "?" + urllib.parse.urlencode(raw_request)
        if response.get("url") != expected_url:
            raise PaperPlaneError("QUOTE_REDIRECT_OR_HOST_REJECTED")
        status, body = response.get("status"), response.get("body")
        if status == 400:
            # Quote-only request rejection is a definitive model non-fill;
            # it cannot close an existing position or claim chain inventory.
            result.update(outcome="REJECTED_BEFORE_SEND", chargeable_cost_usd="0")
            return result, {"http_status": status, "request_sha256": request["request_sha256"], "reason": "QUOTE_REQUEST_REJECTED"}
        if status != 200:
            # HTTP/timeout is not definitive inventory evidence.
            return result, {"http_status": status, "request_sha256": request["request_sha256"], "reason": "QUOTE_HTTP_UNAVAILABLE"}
        if not isinstance(body, bytes) or len(body) > self.max_bytes:
            raise PaperPlaneError("QUOTE_RESPONSE_LIMIT_INVALID")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise PaperPlaneError("QUOTE_RESPONSE_SCHEMA_INVALID") from None
        if not isinstance(payload, dict) or "transaction" not in payload or payload["transaction"] is not None:
            # Never return/store transaction/error message bytes or their hashes.
            raise PaperPlaneError("QUOTE_ONLY_TRANSACTION_REJECTED")
        if payload.get("inputMint") != raw_request["inputMint"] or payload.get("outputMint") != raw_request["outputMint"]:
            raise PaperPlaneError("QUOTE_RESPONSE_MINT_CONFLICT")
        if payload.get("inAmount") != raw_request["amount"]:
            raise PaperPlaneError("QUOTE_RESPONSE_AMOUNT_CONFLICT")
        if payload.get("errorCode") is not None:
            raise PaperPlaneError("QUOTE_PROVIDER_TYPED_FAILURE")
        if not isinstance(payload.get("outAmount"), str) or not re.fullmatch(r"[1-9][0-9]{0,29}", payload["outAmount"]):
            raise PaperPlaneError("QUOTE_OUTPUT_AMOUNT_INVALID")
        if payload.get("router") not in {"metis", "jupiterz", "dflow", "okx"} or payload.get("mode") not in {"ultra", "manual"}:
            raise PaperPlaneError("QUOTE_ROUTE_IDENTITY_INVALID")
        if not isinstance(payload.get("requestId"), str) or not 1 <= len(payload["requestId"]) <= 128:
            raise PaperPlaneError("QUOTE_REQUEST_ID_MISSING")
        if type(payload.get("feeBps")) is not int or not 0 <= payload["feeBps"] <= 10000 or payload.get("feeMint") not in {raw_request["inputMint"], raw_request["outputMint"]}:
            raise PaperPlaneError("QUOTE_FEE_SEMANTICS_UNKNOWN")
        in_units = Decimal(raw_request["amount"]) / (10 ** request["input_decimals"])
        out_units = Decimal(payload["outAmount"]) / (10 ** request["output_decimals"])
        funding_price = decimal_value(request["funding_price_usd"])
        if attempt["side"] == "ENTRY":
            notional, quantity = in_units * funding_price, out_units
            if notional > decimal_value(request["admitted_notional_usd"]):
                raise PaperPlaneError("QUOTE_NOTIONAL_EXCEEDS_ADMISSION")
            result.update(filled_notional_usd=str(notional), quantity_filled=str(quantity), quantity_unit="TOKEN_UNITS")
        else:
            quantity, notional = in_units, out_units * funding_price
            remaining = decimal_value(request["remaining_quantity"]) - quantity
            if remaining < 0:
                raise PaperPlaneError("QUOTE_EXIT_OVERFILL")
            result.update(quantity_sold=str(quantity), remaining_quantity=str(remaining), quantity_unit="TOKEN_UNITS")
        full = notional == decimal_value(request["admitted_notional_usd"]) if attempt["side"] == "ENTRY" else remaining == 0
        result.update(schema_version="1.1", unit_price_usd=str(notional / quantity),
                      fee_semantics="INCLUDED_IN_UNIT_PRICE", outcome="LANDED_SUCCESS" if full else "PARTIAL")
        safe = {"request_sha256": request["request_sha256"], "response_sha256": hashlib.sha256(body).hexdigest(),
                "provider_request_id_sha256": hashlib.sha256(payload["requestId"].encode()).hexdigest(),
                "router": payload["router"], "fee_bps": payload["feeBps"], "fee_mint": payload["feeMint"],
                "observed_at": as_of, "evidence_class": "SHADOW_QUOTE_MODEL", "fill_claimed": False}
        return result, safe


def raw_amount(units, decimals):
    if type(decimals) is not int or not 0 <= decimals <= 18:
        raise PaperPlaneError("QUOTE_DECIMALS_INVALID")
    amount = (decimal_value(units) * (10 ** decimals)).to_integral_value(rounding=ROUND_DOWN)
    if amount <= 0:
        raise PaperPlaneError("QUOTE_RAW_AMOUNT_ZERO")
    return str(amount)
