"""Typed Jupiter /swap/v2/order quote-surface projection.

Donor semantics come from historical ``project_quote`` in
``quote_native_evidence_fit_panel.py``. That panel is not an authority here
and is never imported or reactivated.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.factory.observation_schedule import canonical_json_bytes, canonical_sha256

ABSENT = "ABSENT"
NULL = "NULL"
UNKNOWN = "UNKNOWN"
OBSERVED = "OBSERVED"
OPTIONAL_STATUSES = frozenset({ABSENT, NULL, UNKNOWN, OBSERVED})


class QuoteSurfaceProjectionError(ValueError):
    """Typed quote-surface projection failure."""


def optional_field(payload: Mapping[str, Any], key: str) -> dict[str, object]:
    if key not in payload:
        return {"status": ABSENT, "value": None}
    value = payload[key]
    if value is None:
        return {"status": NULL, "value": None}
    return {"status": OBSERVED, "value": value}


def _render_scalar(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int)):
        text = str(value)
        return text if text else None
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else str(value)
    if isinstance(value, Mapping) or isinstance(value, list):
        return canonical_json_bytes(value).decode("utf-8")
    return None


def _typed_scalar(payload: Mapping[str, Any], key: str) -> dict[str, object]:
    raw = optional_field(payload, key)
    if raw["status"] != OBSERVED:
        return raw
    rendered = _render_scalar(raw["value"])
    if rendered is None:
        return {"status": UNKNOWN, "value": None}
    return {"status": OBSERVED, "value": rendered}


def project_quote_surface(
    payload: Mapping[str, Any],
    *,
    response_sha256: str | None = None,
) -> dict[str, dict[str, object]]:
    if payload.get("transaction") is not None:
        raise QuoteSurfaceProjectionError("QUOTE_RETURNED_TRANSACTION")
    route_plan = optional_field(payload, "routePlan")
    hop_count: dict[str, object]
    fee_amounts_present: dict[str, object]
    if route_plan["status"] == ABSENT:
        hop_count = {"status": ABSENT, "value": None}
        fee_amounts_present = {"status": ABSENT, "value": None}
    elif route_plan["status"] == NULL:
        hop_count = {"status": NULL, "value": None}
        fee_amounts_present = {"status": NULL, "value": None}
    elif not isinstance(route_plan["value"], list):
        hop_count = {"status": UNKNOWN, "value": None}
        fee_amounts_present = {"status": UNKNOWN, "value": None}
    else:
        hops = route_plan["value"]
        present = False
        for hop in hops:
            if isinstance(hop, Mapping):
                info = hop.get("swapInfo")
                if isinstance(info, Mapping) and info.get("feeAmount") not in {None, ""}:
                    present = True
                    break
        hop_count = {"status": OBSERVED, "value": str(len(hops))}
        fee_amounts_present = {
            "status": OBSERVED,
            "value": "true" if present else "false",
        }
    pointer = (
        {"status": OBSERVED, "value": response_sha256}
        if isinstance(response_sha256, str) and len(response_sha256) == 64
        else {"status": ABSENT, "value": None}
    )
    return {
        "in_amount": _typed_scalar(payload, "inAmount"),
        "out_amount": _typed_scalar(payload, "outAmount"),
        "price_impact_pct": _typed_scalar(payload, "priceImpactPct"),
        "fee_bps": _typed_scalar(payload, "feeBps"),
        "platform_fee": _typed_scalar(payload, "platformFee"),
        "router": _typed_scalar(payload, "router"),
        "mode": _typed_scalar(payload, "mode"),
        "route_hop_count": hop_count,
        "route_fee_amounts_present": fee_amounts_present,
        "response_sha256": pointer,
    }


def hash_raw_response(body: object) -> str:
    return canonical_sha256(body)


def projection_never_zero_for_missing(projection: Mapping[str, Mapping[str, object]]) -> bool:
    for item in projection.values():
        status = item.get("status")
        value = item.get("value")
        if status in {ABSENT, NULL, UNKNOWN} and value in {0, "0", 0.0, "0.0"}:
            return False
    return True


def load_quote_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteSurfaceProjectionError("QUOTE_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise QuoteSurfaceProjectionError("QUOTE_JSON_INVALID")
    return payload


__all__ = [
    "ABSENT",
    "NULL",
    "OBSERVED",
    "OPTIONAL_STATUSES",
    "QuoteSurfaceProjectionError",
    "UNKNOWN",
    "hash_raw_response",
    "load_quote_payload",
    "optional_field",
    "project_quote_surface",
    "projection_never_zero_for_missing",
]
