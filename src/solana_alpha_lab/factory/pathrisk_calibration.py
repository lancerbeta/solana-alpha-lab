"""EARLY quote-surface PathRisk calibration capability. Zero-network by default."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.observation_schedule import (
    ObservationScheduleError,
    canonical_sha256,
    parse_utc,
)

ATOM_ID = "EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_V1"
CONFIG_RELATIVE = "configs/early_quote_surface_pathrisk_calibration_v1.yaml"
ICP_ID = "ICP-EARLY-PUMPFUN-V1"
NOTIONAL_10M = "10000000"
NOTIONAL_1M = "1000000"
NOTIONALS = (NOTIONAL_1M, NOTIONAL_10M)
SAMPLE_FLOOR = 4
COMPLETE_DUAL_FLOOR = 3
BUY_10M = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001"
BUY_1M = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-1M-001"
REVERSE_10M = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
REVERSE_1M = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-1M-001"
BUY_BY_NOTIONAL = {NOTIONAL_10M: BUY_10M, NOTIONAL_1M: BUY_1M}
REVERSE_BY_NOTIONAL = {NOTIONAL_10M: REVERSE_10M, NOTIONAL_1M: REVERSE_1M}
REVERSE_FOR_BUY = {BUY_10M: REVERSE_10M, BUY_1M: REVERSE_1M}
X_POINT_ID = "X300"
Y_POINT_ID = "Y900"
CREDENTIAL_MODE = "LOCAL_ENV_CREDENTIAL_JUPITER_FREE_API_KEY"

TERMINAL_INFORMATIVE = "PATHRISK_SURFACE_INFORMATIVE"
TERMINAL_DEGENERATE = "PATHRISK_SURFACE_STILL_DEGENERATE"
TERMINAL_PARTIAL = "CALIBRATION_PARTIAL_INSUFFICIENT_COVERAGE"
TERMINAL_INVALID = "CALIBRATION_PROVIDER_OR_SCHEMA_INVALID"
TERMINAL_BELOW_FLOOR = "CALIBRATION_ELIGIBLE_BELOW_FLOOR"

QUOTE_NET_PROXY = "QUOTE_NET_PROXY"
QUOTE_PATH_CHANGE = "QUOTE_PATH_CHANGE"


class PathRiskCalibrationError(ValueError):
    """Typed PathRisk calibration failure."""


def load_policy(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise PathRiskCalibrationError("CALIBRATION_POLICY_INVALID")
    return dict(loaded)


def parse_integer_amount(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text[0] in "+-" and text[1:].isdigit():
        return int(text)
    if text.isdigit():
        return int(text)
    return None


def quote_ratio_minus_one(numerator: int, denominator: int) -> Fraction:
    if denominator == 0:
        raise PathRiskCalibrationError("CALIBRATION_PROVIDER_OR_SCHEMA_INVALID")
    return Fraction(numerator, denominator) - 1


def render_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def population_eligible(
    row: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    as_of: datetime | None = None,
) -> bool:
    source = row.get("firstPool") if isinstance(row.get("firstPool"), Mapping) else {}
    launchpad = str(source.get("source") or row.get("source") or "")
    if launchpad != str(policy["population"]["launchpad"]):
        return False
    liquidity = row.get("liquidity")
    if liquidity is None:
        liquidity = row.get("liquidityUsd")
    try:
        liq = Decimal(str(liquidity))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if liq < Decimal(str(policy["population"]["liquidity_usd_min"])):
        return False
    mint = str(row.get("id") or row.get("mint") or "")
    if not mint:
        return False
    seasoning = int(policy["population"].get("seasoning_seconds") or 0)
    if seasoning > 0:
        if as_of is None:
            return False
        created_raw = source.get("createdAt") or row.get("first_seen_at")
        if not created_raw:
            return False
        try:
            created = parse_utc(str(created_raw))
        except (ObservationScheduleError, TypeError, ValueError):
            return False
        if (as_of - created).total_seconds() < seasoning:
            return False
    return True


def select_r0_sample(
    rows: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    as_of: datetime | None = None,
) -> dict[str, Any]:
    eligible = [
        str(row.get("id") or row.get("mint"))
        for row in rows
        if isinstance(row, Mapping) and population_eligible(row, policy=policy, as_of=as_of)
    ]
    ordered = sorted({mint for mint in eligible if mint})
    floor = int(policy["sample"]["floor"])
    if len(ordered) < floor:
        return {
            "terminal": TERMINAL_BELOW_FLOOR,
            "eligible_count": len(ordered),
            "mints": ordered,
            "quote_calls": 0,
        }
    return {
        "terminal": None,
        "eligible_count": len(ordered),
        "mints": ordered[:floor],
        "quote_calls": None,
    }


def _field_amount(row: Mapping[str, Any], field_id: str) -> int | None:
    for item in row.get("field_values") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("field_id")) != field_id:
            continue
        if str(item.get("state")) != "OBSERVED":
            return None
        return parse_integer_amount(item.get("typed_value_or_null"))
    fallback_key = (
        "buy_out_amount" if "BUY" in field_id else "sell_out_amount"
    )
    return parse_integer_amount(row.get(fallback_key))


def _observation_index(
    observations: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in observations:
        if not isinstance(row, Mapping):
            continue
        key = (
            str(row.get("entity_id") or ""),
            str(row.get("point_id") or ""),
            str(row.get("primitive_id") or ""),
        )
        indexed[key] = row
    return indexed


def _typed_missing(reason: str) -> dict[str, object]:
    return {"status": "UNKNOWN", "value": None, "reason": reason}


SURFACE_READOUT_FIELDS = (
    "FIELD-QUOTE-FEE-BPS-001",
    "FIELD-QUOTE-PRICE-IMPACT-PCT-001",
    "FIELD-QUOTE-PLATFORM-FEE-001",
    "FIELD-QUOTE-ROUTER-001",
    "FIELD-QUOTE-MODE-001",
    "FIELD-QUOTE-ROUTE-HOP-COUNT-001",
    "FIELD-QUOTE-ROUTE-FEE-AMOUNTS-PRESENT-001",
)


def _typed_field(row: Mapping[str, Any] | None, field_id: str) -> dict[str, object]:
    if row is None:
        return _typed_missing("MISSING_TYPED")
    for item in row.get("field_values") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("field_id")) != field_id:
            continue
        if str(item.get("state")) == "OBSERVED":
            return {"status": "OBSERVED", "value": item.get("typed_value_or_null")}
        return _typed_missing(str(item.get("missing_reason") or item.get("state") or "UNKNOWN"))
    return _typed_missing("ABSENT")


def _surface_block(row: Mapping[str, Any] | None) -> dict[str, dict[str, object]]:
    return {field_id: _typed_field(row, field_id) for field_id in SURFACE_READOUT_FIELDS}


def _route_impact_delta(
    t0: Mapping[str, Mapping[str, object]],
    h900: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    delta: dict[str, dict[str, object]] = {}
    for field_id in SURFACE_READOUT_FIELDS:
        left = dict(t0[field_id])
        right = dict(h900[field_id])
        changed = (
            left.get("status") == "OBSERVED"
            and right.get("status") == "OBSERVED"
            and left.get("value") != right.get("value")
        )
        delta[field_id] = {"t0": left, "h900": right, "changed": changed}
    return delta


def _cell_metrics(
    *,
    mint: str,
    notional: str,
    observations: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    buy_prim = BUY_BY_NOTIONAL[notional]
    reverse_prim = REVERSE_BY_NOTIONAL[notional]
    buy = observations.get((mint, X_POINT_ID, buy_prim))
    t0_reverse = observations.get((mint, X_POINT_ID, reverse_prim))
    h900 = observations.get((mint, Y_POINT_ID, reverse_prim))
    original = parse_integer_amount(notional)
    buy_out = _field_amount(buy, "FIELD-QUOTE-BUY-OUT-AMOUNT-001") if buy else None
    t0_out = (
        _field_amount(t0_reverse, "FIELD-QUOTE-SELL-OUT-AMOUNT-001") if t0_reverse else None
    )
    h900_out = _field_amount(h900, "FIELD-QUOTE-SELL-OUT-AMOUNT-001") if h900 else None
    buy_state = str((buy or {}).get("state") or "MISSING_TYPED")
    reverse_state = str((t0_reverse or {}).get("state") or "MISSING_TYPED")
    h900_state = str((h900 or {}).get("state") or "MISSING_TYPED")
    schema_invalid = False
    if buy is not None and buy_state == "OBSERVED" and buy_out is None:
        schema_invalid = True
    if t0_reverse is not None and reverse_state == "OBSERVED" and t0_out is None:
        schema_invalid = True
    if h900 is not None and h900_state == "OBSERVED" and h900_out is None:
        schema_invalid = True
    if original == 0 or t0_out == 0:
        schema_invalid = True
    if h900_out is None or original is None or original == 0:
        net_proxy: dict[str, object] = _typed_missing(
            "CALIBRATION_PROVIDER_OR_SCHEMA_INVALID" if original == 0 else h900_state
        )
    else:
        value = quote_ratio_minus_one(h900_out, original)
        net_proxy = {
            "status": "OBSERVED",
            "value": render_fraction(value),
            "exact": True,
        }
    if h900_out is None or t0_out is None or t0_out == 0:
        reason = (
            "CALIBRATION_PROVIDER_OR_SCHEMA_INVALID"
            if t0_out == 0
            else (reverse_state if t0_out is None else h900_state)
        )
        path_change: dict[str, object] = _typed_missing(reason)
    else:
        value = quote_ratio_minus_one(h900_out, t0_out)
        path_change = {
            "status": "OBSERVED",
            "value": render_fraction(value),
            "exact": True,
        }
    complete = (
        buy_state == "OBSERVED"
        and reverse_state == "OBSERVED"
        and h900_state == "OBSERVED"
        and buy_out is not None
        and t0_out is not None
        and h900_out is not None
        and original is not None
        and not schema_invalid
    )
    t0_surface = _surface_block(t0_reverse)
    h900_surface = _surface_block(h900)
    return {
        "mint": mint,
        "notional_lamports": notional,
        "original_sol_input": original,
        "token_buy_output": buy_out,
        "t0_reverse_sol_output": t0_out,
        "h900_sol_output": h900_out,
        "buy_state": buy_state,
        "t0_reverse_state": reverse_state,
        "h900_state": h900_state,
        QUOTE_NET_PROXY: net_proxy,
        QUOTE_PATH_CHANGE: path_change,
        "complete": complete,
        "schema_invalid": schema_invalid,
        "fee_fields": {
            "t0": t0_surface["FIELD-QUOTE-FEE-BPS-001"],
            "h900": h900_surface["FIELD-QUOTE-FEE-BPS-001"],
            "platform_fee_t0": t0_surface["FIELD-QUOTE-PLATFORM-FEE-001"],
            "platform_fee_h900": h900_surface["FIELD-QUOTE-PLATFORM-FEE-001"],
        },
        "impact_fields": {
            "t0": t0_surface["FIELD-QUOTE-PRICE-IMPACT-PCT-001"],
            "h900": h900_surface["FIELD-QUOTE-PRICE-IMPACT-PCT-001"],
        },
        "route_fields": {
            "t0": {
                "router": t0_surface["FIELD-QUOTE-ROUTER-001"],
                "mode": t0_surface["FIELD-QUOTE-MODE-001"],
                "hop_count": t0_surface["FIELD-QUOTE-ROUTE-HOP-COUNT-001"],
                "fee_amounts_present": t0_surface["FIELD-QUOTE-ROUTE-FEE-AMOUNTS-PRESENT-001"],
            },
            "h900": {
                "router": h900_surface["FIELD-QUOTE-ROUTER-001"],
                "mode": h900_surface["FIELD-QUOTE-MODE-001"],
                "hop_count": h900_surface["FIELD-QUOTE-ROUTE-HOP-COUNT-001"],
                "fee_amounts_present": h900_surface["FIELD-QUOTE-ROUTE-FEE-AMOUNTS-PRESENT-001"],
            },
        },
        "t0_vs_h900_route_impact_delta": _route_impact_delta(t0_surface, h900_surface),
        "missingness": {
            "buy": buy_state,
            "t0_reverse": reverse_state,
            "h900": h900_state,
        },
    }


def _detect_cross_bind(cells: Sequence[Mapping[str, Any]]) -> bool:
    by_mint: dict[str, list[Mapping[str, Any]]] = {}
    for cell in cells:
        by_mint.setdefault(str(cell["mint"]), []).append(cell)
    for group in by_mint.values():
        buy_outs = [
            item.get("token_buy_output")
            for item in group
            if item.get("token_buy_output") is not None
        ]
        notionals = {
            str(item["notional_lamports"])
            for item in group
            if item.get("token_buy_output") is not None
        }
        if len(buy_outs) >= 2 and len(set(buy_outs)) == 1 and len(notionals) == 2:
            return True
    return False


def classify_terminal(readout: Mapping[str, Any]) -> str:
    if readout.get("below_floor"):
        return TERMINAL_BELOW_FLOOR
    if readout.get("schema_invalid") or readout.get("cross_bound"):
        return TERMINAL_INVALID
    complete_mints = list(readout.get("complete_dual_notional_mints") or [])
    if len(complete_mints) < COMPLETE_DUAL_FLOOR:
        return TERMINAL_PARTIAL
    values = list(readout.get("complete_path_change_values") or [])
    distinct = set(values)
    scale_differs = bool(readout.get("scale_response_differs"))
    if len(distinct) > 1 or scale_differs:
        return TERMINAL_INFORMATIVE
    return TERMINAL_DEGENERATE


def build_readout(
    *,
    mints: Sequence[str],
    observations: Sequence[Mapping[str, Any]],
    below_floor: bool = False,
    provider_calls: int = 0,
) -> dict[str, Any]:
    indexed = _observation_index(observations)
    cells = [
        _cell_metrics(mint=mint, notional=notional, observations=indexed)
        for mint in mints
        for notional in NOTIONALS
    ]
    cross_bound = _detect_cross_bind(cells)
    schema_invalid = any(cell.get("schema_invalid") for cell in cells)
    complete_by_mint: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        if cell["complete"]:
            complete_by_mint.setdefault(str(cell["mint"]), []).append(cell)
    complete_dual = [
        mint for mint, group in complete_by_mint.items() if len(group) == 2
    ]
    path_values = [
        str(cell[QUOTE_PATH_CHANGE]["value"])
        for mint in complete_dual
        for cell in complete_by_mint[mint]
        if cell[QUOTE_PATH_CHANGE].get("status") == "OBSERVED"
    ]
    scale_response_differs = False
    for mint in complete_dual:
        pair = {
            str(item["notional_lamports"]): str(item[QUOTE_PATH_CHANGE]["value"])
            for item in complete_by_mint[mint]
            if item[QUOTE_PATH_CHANGE].get("status") == "OBSERVED"
        }
        if (
            pair.get(NOTIONAL_1M)
            and pair.get(NOTIONAL_10M)
            and pair[NOTIONAL_1M] != pair[NOTIONAL_10M]
        ):
            scale_response_differs = True
            break
    net_values = [
        str(cell[QUOTE_NET_PROXY]["value"])
        for mint in complete_dual
        for cell in complete_by_mint[mint]
        if cell[QUOTE_NET_PROXY].get("status") == "OBSERVED"
    ]
    t0_values = [
        cell.get("t0_reverse_sol_output")
        for mint in complete_dual
        for cell in complete_by_mint[mint]
    ]
    distinct_counts = {
        "path_change": len(set(path_values)),
        "net_proxy": len(set(net_values)),
        "t0_reverse": len({item for item in t0_values if item is not None}),
    }
    modal_share = None
    if path_values:
        counts: dict[str, int] = {}
        for value in path_values:
            counts[value] = counts.get(value, 0) + 1
        modal = max(counts.values())
        modal_share = f"{modal}/{len(path_values)}"
    payload: dict[str, Any] = {
        "schema": "smial.early-quote-surface-pathrisk-calibration-readout",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "below_floor": below_floor,
        "mints": list(mints),
        "cells": cells,
        "complete_dual_notional_mints": complete_dual,
        "complete_path_change_values": path_values,
        "distinct_counts": distinct_counts,
        "modal_share": modal_share,
        "scale_response_differs": scale_response_differs,
        "schema_invalid": schema_invalid,
        "cross_bound": cross_bound,
        "informative_complete_dual_notional_floor": COMPLETE_DUAL_FLOOR,
        "surface_fields_are_diagnostic_not_terminal": True,
        "provider_calls": provider_calls,
        "non_claims": [
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_REALIZED_VWAP",
            "NO_FILL",
            "QUOTE_ONLY",
            "PATHRISK_PROXY_NOT_PROFITABILITY",
        ],
    }
    payload["terminal"] = classify_terminal(payload)
    payload["readout_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "readout_sha256"}
    )
    return payload


def require_exact_main_sha(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise PathRiskCalibrationError("MAIN_SHA_NOT_EXACT_40_HEX")
    return value


def proposed_capture_packet(
    *,
    root: Path,
    main_sha: str,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = policy or load_policy(root)
    exact_sha = require_exact_main_sha(main_sha)
    registry_path = root / str(document["registry"])
    packet = {
        "schema": "smial.early-quote-surface-pathrisk-calibration-capture-packet",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "current_main_sha": exact_sha,
        "provider_route_registry": str(document["registry"]),
        "provider_route_registry_sha256": hashlib.sha256(
            registry_path.read_bytes()
        ).hexdigest(),
        "provider_route_asset_id": "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
        "route_id": str(document["routes"]["quote"]["route_id"]),
        "credential_mode": CREDENTIAL_MODE,
        "population": str(document["population"]["icp_id"]),
        "notionals_lamports": list(document["notionals_lamports"]),
        "sample_floor": int(document["sample"]["floor"]),
        "max_calls": int(document["runtime_limits"]["max_calls"]),
        "pace_seconds": int(document["runtime_limits"]["min_interval_seconds"]),
        "raw_retention": dict(document["raw_retention"]),
        "forbidden_actions": list(document["forbidden_actions"]),
        "future_owner_phrase": str(document["external_authority"]["future_owner_phrase"]),
        "live_authorized": False,
        "live_window": dict(document.get("live_window") or {}),
        "informative_complete_dual_notional_floor": COMPLETE_DUAL_FLOOR,
        "provider_calls_this_pr": 0,
        "credential_reads_this_pr": 0,
        "cash_this_pr": 0,
    }
    packet["packet_sha256"] = canonical_sha256(
        {key: value for key, value in packet.items() if key != "packet_sha256"}
    )
    return packet


__all__ = [
    "ATOM_ID",
    "BUY_1M",
    "BUY_10M",
    "COMPLETE_DUAL_FLOOR",
    "ICP_ID",
    "NOTIONAL_1M",
    "NOTIONAL_10M",
    "PathRiskCalibrationError",
    "REVERSE_1M",
    "REVERSE_10M",
    "REVERSE_FOR_BUY",
    "SAMPLE_FLOOR",
    "TERMINAL_BELOW_FLOOR",
    "TERMINAL_DEGENERATE",
    "TERMINAL_INFORMATIVE",
    "TERMINAL_INVALID",
    "TERMINAL_PARTIAL",
    "build_readout",
    "classify_terminal",
    "load_policy",
    "parse_integer_amount",
    "population_eligible",
    "proposed_capture_packet",
    "quote_ratio_minus_one",
    "require_exact_main_sha",
    "render_fraction",
    "select_r0_sample",
]
