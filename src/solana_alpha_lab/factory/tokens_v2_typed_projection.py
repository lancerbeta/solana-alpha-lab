"""Single Tokens V2 row → typed field projection for replay and ObservationSchedule.

Do not maintain a second field mapping elsewhere. Ambiguous substitutes
(for example fdv as market cap) are excluded, never silently aliased.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from solana_alpha_lab.factory.early_market_panel_field_semantics import (
    classify_r0_mix,
)

PROJECTION_ID = "TOKENS_V2_TYPED_PROJECTION_V1"
PROJECTION_VERSION = "1.0"

STATE_OBSERVED = "OBSERVED"
STATE_MISSING = "MISSING_TYPED"
STATE_EXCLUDED = "EXCLUDED_AMBIGUOUS"

# Coarse Forge-visible families (max eight).
FEATURE_FAMILY_PRICE_PATH = "PRICE_PATH"
FEATURE_FAMILY_LIQUIDITY_PATH = "LIQUIDITY_PATH"
FEATURE_FAMILY_VALUATION = "VALUATION"
FEATURE_FAMILY_ACTIVITY_VOLUME = "ACTIVITY_VOLUME"
FEATURE_FAMILY_TRADER_BREADTH = "TRADER_BREADTH"
FEATURE_FAMILY_HOLDER_STATE = "HOLDER_STATE"
FEATURE_FAMILY_LIFECYCLE_TIMING = "LIFECYCLE_TIMING"
FEATURE_FAMILY_MISSINGNESS = "MISSINGNESS_AVAILABILITY"

FEATURE_FAMILY_ORDER = (
    FEATURE_FAMILY_PRICE_PATH,
    FEATURE_FAMILY_LIQUIDITY_PATH,
    FEATURE_FAMILY_VALUATION,
    FEATURE_FAMILY_ACTIVITY_VOLUME,
    FEATURE_FAMILY_TRADER_BREADTH,
    FEATURE_FAMILY_HOLDER_STATE,
    FEATURE_FAMILY_LIFECYCLE_TIMING,
    FEATURE_FAMILY_MISSINGNESS,
)

FIELD_TO_FAMILY: dict[str, str] = {
    "FIELD-USD-PRICE-001": FEATURE_FAMILY_PRICE_PATH,
    "FIELD-LIQUIDITY-USD-001": FEATURE_FAMILY_LIQUIDITY_PATH,
    "FIELD-MARKET-CAP-USD-001": FEATURE_FAMILY_VALUATION,
    "FIELD-STATS5M-BUY-VOLUME-001": FEATURE_FAMILY_ACTIVITY_VOLUME,
    "FIELD-STATS5M-SELL-VOLUME-001": FEATURE_FAMILY_ACTIVITY_VOLUME,
    "FIELD-STATS5M-TAKER-VOLUME-001": FEATURE_FAMILY_ACTIVITY_VOLUME,
    "FIELD-R0-TAKER-VOLUME-MIX-001": FEATURE_FAMILY_ACTIVITY_VOLUME,
    "FIELD-STATS5M-NUM-BUYS-001": FEATURE_FAMILY_TRADER_BREADTH,
    "FIELD-STATS5M-NUM-SELLS-001": FEATURE_FAMILY_TRADER_BREADTH,
    "FIELD-STATS5M-NUM-TRADERS-001": FEATURE_FAMILY_TRADER_BREADTH,
    "FIELD-STATS5M-NUM-NET-BUYERS-001": FEATURE_FAMILY_TRADER_BREADTH,
    "FIELD-HOLDER-COUNT-001": FEATURE_FAMILY_HOLDER_STATE,
    "FIELD-FIRST-POOL-CREATED-AT-001": FEATURE_FAMILY_LIFECYCLE_TIMING,
    "FIELD-FIRST-POOL-SOURCE-001": FEATURE_FAMILY_LIFECYCLE_TIMING,
    "FIELD-TOKEN-MINT-001": FEATURE_FAMILY_LIFECYCLE_TIMING,
    "FIELD-FIRST-SEEN-AT-001": FEATURE_FAMILY_LIFECYCLE_TIMING,
}

# Tokens V2 discovery fields owned by this projection (quotes stay elsewhere).
TOKENS_V2_FIELD_KINDS: dict[str, str] = {
    "FIELD-TOKEN-MINT-001": "TOKEN_MINT",
    "FIELD-FIRST-POOL-CREATED-AT-001": "TIMESTAMP",
    "FIELD-FIRST-POOL-SOURCE-001": "TEXT",
    "FIELD-FIRST-SEEN-AT-001": "TIMESTAMP",
    "FIELD-USD-PRICE-001": "DECIMAL",
    "FIELD-LIQUIDITY-USD-001": "DECIMAL",
    "FIELD-MARKET-CAP-USD-001": "DECIMAL",
    "FIELD-HOLDER-COUNT-001": "DECIMAL",
    "FIELD-STATS5M-BUY-VOLUME-001": "DECIMAL",
    "FIELD-STATS5M-SELL-VOLUME-001": "DECIMAL",
    "FIELD-STATS5M-TAKER-VOLUME-001": "DECIMAL",
    "FIELD-STATS5M-NUM-BUYS-001": "DECIMAL",
    "FIELD-STATS5M-NUM-SELLS-001": "DECIMAL",
    "FIELD-STATS5M-NUM-TRADERS-001": "DECIMAL",
    "FIELD-STATS5M-NUM-NET-BUYERS-001": "DECIMAL",
    "FIELD-R0-TAKER-VOLUME-MIX-001": "DECIMAL",
}


class TokensV2ProjectionError(ValueError):
    """Fail-closed typed projection fault."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _first_non_none(*values: object) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.lstrip("-").isdigit():
                return int(text)
            number = float(text)
        except ValueError:
            return None
        if number != number or number in {float("inf"), float("-inf")}:
            return None
        if number.is_integer():
            return int(number)
        return number
    return None


def _stats_window(row: Mapping[str, Any], window: str) -> Mapping[str, Any]:
    return _as_mapping(row.get(window))


def project_tokens_v2_field(
    row: Mapping[str, Any],
    field_id: str,
) -> tuple[object | None, str, str | None]:
    """Return (typed_value_or_null, state, missing_reason)."""
    if field_id not in TOKENS_V2_FIELD_KINDS:
        raise TokensV2ProjectionError("UNKNOWN_TOKENS_V2_FIELD")
    # Ambiguous substitutes are never accepted.
    if field_id == "FIELD-MARKET-CAP-USD-001" and "mcap" not in row and "fdv" in row:
        return None, STATE_EXCLUDED, "FDV_NOT_MARKET_CAP"
    if field_id == "FIELD-USD-PRICE-001" and "usdPrice" not in row and "price" in row:
        return None, STATE_EXCLUDED, "AMBIGUOUS_PRICE_ALIAS"

    first_pool = _as_mapping(row.get("firstPool"))
    stats5m = _stats_window(row, "stats5m")

    raw: object | None
    if field_id == "FIELD-TOKEN-MINT-001":
        raw = _first_non_none(row.get("id"), row.get("mint"))
    elif field_id == "FIELD-FIRST-POOL-CREATED-AT-001":
        raw = first_pool.get("createdAt")
    elif field_id == "FIELD-FIRST-POOL-SOURCE-001":
        raw = _first_non_none(first_pool.get("source"), row.get("source"))
    elif field_id == "FIELD-FIRST-SEEN-AT-001":
        raw = row.get("first_seen_at")
    elif field_id == "FIELD-USD-PRICE-001":
        raw = row.get("usdPrice")
    elif field_id == "FIELD-LIQUIDITY-USD-001":
        raw = _first_non_none(row.get("liquidity"), row.get("liquidityUsd"))
    elif field_id == "FIELD-MARKET-CAP-USD-001":
        raw = row.get("mcap")
    elif field_id == "FIELD-HOLDER-COUNT-001":
        raw = row.get("holderCount")
    elif field_id == "FIELD-STATS5M-BUY-VOLUME-001":
        raw = stats5m.get("buyVolume")
    elif field_id == "FIELD-STATS5M-SELL-VOLUME-001":
        raw = stats5m.get("sellVolume")
    elif field_id == "FIELD-STATS5M-TAKER-VOLUME-001":
        raw = _first_non_none(
            row.get("stats5m_taker_volume"),
            row.get("takerVolume"),
            stats5m.get("takerVolume"),
            stats5m.get("taker_volume"),
        )
        # Do not invent takerVolume from buy+sell.
        if raw is None and (
            "buyVolume" in stats5m or "sellVolume" in stats5m or "volume" in stats5m
        ):
            return None, STATE_EXCLUDED, "TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL"
    elif field_id == "FIELD-STATS5M-NUM-BUYS-001":
        raw = stats5m.get("numBuys")
    elif field_id == "FIELD-STATS5M-NUM-SELLS-001":
        raw = stats5m.get("numSells")
    elif field_id == "FIELD-STATS5M-NUM-TRADERS-001":
        raw = stats5m.get("numTraders")
    elif field_id == "FIELD-STATS5M-NUM-NET-BUYERS-001":
        raw = stats5m.get("numNetBuyers")
    elif field_id == "FIELD-R0-TAKER-VOLUME-MIX-001":
        precomputed = _first_non_none(
            row.get("r0_taker_volume_mix"),
            row.get("r0TakerVolumeMix"),
            row.get("r0"),
            stats5m.get("r0"),
        )
        if precomputed is not None:
            raw = precomputed
        else:
            mix, code = classify_r0_mix(row)
            if code is None:
                return mix, STATE_OBSERVED, None
            return None, STATE_MISSING, code
    else:
        raise TokensV2ProjectionError("UNKNOWN_TOKENS_V2_FIELD")

    if raw is None:
        return None, STATE_MISSING, "FIELD_ABSENT"
    if TOKENS_V2_FIELD_KINDS[field_id] == "DECIMAL":
        number = _finite_number(raw)
        if number is None:
            return None, STATE_MISSING, "NON_FINITE"
        return number, STATE_OBSERVED, None
    return raw, STATE_OBSERVED, None


def project_tokens_v2_row(
    row: Mapping[str, Any],
    *,
    field_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Project one provider row into typed field records."""
    if not isinstance(row, Mapping):
        raise TokensV2ProjectionError("ROW_NOT_OBJECT")
    selected = list(field_ids) if field_ids is not None else list(TOKENS_V2_FIELD_KINDS)
    out: list[dict[str, Any]] = []
    for field_id in selected:
        value, state, missing = project_tokens_v2_field(row, field_id)
        out.append(
            {
                "field_id": field_id,
                "value_kind": TOKENS_V2_FIELD_KINDS[field_id],
                "typed_value_or_null": value,
                "state": state,
                "missing_reason": missing,
            }
        )
    return out


def project_tokens_v2_scalar(row: Mapping[str, Any], field_id: str) -> object | None:
    """Scalar extractor for scheduler predicates (observed values only)."""
    if field_id not in TOKENS_V2_FIELD_KINDS:
        return None
    value, state, _missing = project_tokens_v2_field(row, field_id)
    if state != STATE_OBSERVED:
        return None
    return value


def feature_families_from_typed_values(
    typed_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Derive compact coarse families present in a typed release."""
    observed: set[str] = set()
    missing_or_excluded = False
    for row in typed_rows:
        field_id = str(row.get("field_id") or "")
        state = str(row.get("state") or "")
        family = FIELD_TO_FAMILY.get(field_id)
        if state == STATE_OBSERVED and family is not None:
            observed.add(family)
        if state in {STATE_MISSING, STATE_EXCLUDED}:
            missing_or_excluded = True
    if missing_or_excluded:
        observed.add(FEATURE_FAMILY_MISSINGNESS)
    return [family for family in FEATURE_FAMILY_ORDER if family in observed]


def sanitize_tokens_v2_source_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Retain only projection-relevant Tokens V2 keys for durable payloads."""
    first_pool = row.get("firstPool")
    stats5m = row.get("stats5m")
    sanitized: dict[str, Any] = {
        "id": row.get("id"),
        "mint": row.get("mint"),
        "first_seen_at": row.get("first_seen_at"),
        "usdPrice": row.get("usdPrice"),
        "liquidity": row.get("liquidity"),
        "liquidityUsd": row.get("liquidityUsd"),
        "mcap": row.get("mcap"),
        "holderCount": row.get("holderCount"),
        "stats5m": dict(stats5m) if isinstance(stats5m, Mapping) else stats5m,
        "stats5m_taker_volume": row.get("stats5m_taker_volume"),
        "takerVolume": row.get("takerVolume"),
        "r0": row.get("r0"),
        "r0TakerVolumeMix": row.get("r0TakerVolumeMix"),
        "r0_taker_volume_mix": row.get("r0_taker_volume_mix"),
        "source": row.get("source"),
    }
    if isinstance(first_pool, Mapping):
        sanitized["firstPool"] = {
            "createdAt": first_pool.get("createdAt"),
            "source": first_pool.get("source"),
        }
    return {key: value for key, value in sanitized.items() if value is not None}
