"""Prove R0_TAKER_VOLUME_MIX semantics before any dataset bind.

Official Jupiter Tokens V2 SwapStats lists buyVolume/sellVolume as optional
numbers with no unit annotation. liquidity and mcap are documented as USD.
The bound feature is the dimensionless R0-only mix ratio, not raw volumes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FEATURE_ID = "R0_TAKER_VOLUME_MIX"
FIELD_SEMANTICS_TERMINAL = "R0_TAKER_VOLUME_MIX_RATIO_PROVEN"
FIELD_SEMANTICS_UNPROVEN = "FIELD_SEMANTICS_UNPROVEN"
RAW_VOLUME_UNIT_STATUS = "OFFICIAL_UNANNOTATED"
RATIO_UNIT = "DIMENSIONLESS_UNIT_INTERVAL"
WINDOW = "stats5m"
BUY_FIELD = "buyVolume"
SELL_FIELD = "sellVolume"
OFFICIAL_CITATION = (
    "https://developers.jup.ag/docs/guides/how-to-get-token-information"
)
OFFICIAL_FACTS = {
    "liquidity_documented_unit": "USD",
    "mcap_documented_unit": "USD",
    "swapstats_buy_volume_documented_unit": None,
    "swapstats_sell_volume_documented_unit": None,
    "swapstats_windows": ["stats5m", "stats1h", "stats6h", "stats24h"],
    "swapstats_shape": "same optional number fields in one object",
}


class FieldSemanticsError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def classify_r0_mix(row: Mapping[str, Any]) -> tuple[float | None, str | None]:
    stats = row.get("stats5m")
    if stats is None:
        return None, "STATS5M_ABSENT"
    if not isinstance(stats, Mapping):
        return None, "STATS5M_NOT_OBJECT"
    if "stats5m" in row and any(key in row for key in ("stats5m_r1", "r1_stats5m")):
        raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
    if BUY_FIELD not in stats:
        return None, "BUY_VOLUME_ABSENT"
    if SELL_FIELD not in stats:
        return None, "SELL_VOLUME_ABSENT"
    buy = _finite_number(stats.get(BUY_FIELD))
    sell = _finite_number(stats.get(SELL_FIELD))
    if buy is None:
        return None, "BUY_VOLUME_NON_FINITE"
    if sell is None:
        return None, "SELL_VOLUME_NON_FINITE"
    if buy < 0 or sell < 0:
        return None, "NEGATIVE_VOLUME"
    total = buy + sell
    if total <= 0:
        return None, "ZERO_DENOMINATOR"
    return buy / total, None


def prove_r0_taker_volume_mix_semantics(
    rows: Sequence[Mapping[str, Any]],
    *,
    x_source_observation: str,
) -> dict[str, Any]:
    if x_source_observation != "DISCOVERY:SEARCH_R0":
        raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
    if not rows:
        raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
    eligible = 0
    missing_codes: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
        if any(key.startswith("r1.") or key.endswith("_r1") for key in row):
            raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
        value, code = classify_r0_mix(row)
        if code is None:
            eligible += 1
            continue
        missing_codes[code] = missing_codes.get(code, 0) + 1
    if eligible < 1:
        raise FieldSemanticsError(FIELD_SEMANTICS_UNPROVEN)
    return {
        "feature_id": FEATURE_ID,
        "terminal": FIELD_SEMANTICS_TERMINAL,
        "window": WINDOW,
        "buy_field": f"{WINDOW}.{BUY_FIELD}",
        "sell_field": f"{WINDOW}.{SELL_FIELD}",
        "ratio_definition": "buyVolume / (buyVolume + sellVolume) from the same stats5m object",
        "ratio_unit": RATIO_UNIT,
        "raw_volume_unit_status": RAW_VOLUME_UNIT_STATUS,
        "same_swapstats_object": True,
        "same_optional_number_type": True,
        "same_unknown_unit_for_both_legs": True,
        "official_volume_unit_annotated": False,
        "x_uses_r0_only": True,
        "x_source_observation": x_source_observation,
        "availability": "R0_ONLY",
        "yield_eligible": eligible,
        "yield_missing": sum(missing_codes.values()),
        "missingness_codes": missing_codes,
        "official_citation": OFFICIAL_CITATION,
        "official_facts": OFFICIAL_FACTS,
        "non_claims": [
            "NOT_USD_CLAIM_FOR_RAW_VOLUMES",
            "NOT_CONFIRMATORY_FALSIFIER",
            "NO_X_Y_SCORE",
            "NO_HYP_EARLY_TAKER_VOLUME_MIX_REGISTERED",
        ],
    }


__all__ = [
    "FEATURE_ID",
    "FIELD_SEMANTICS_TERMINAL",
    "FIELD_SEMANTICS_UNPROVEN",
    "FieldSemanticsError",
    "classify_r0_mix",
    "prove_r0_taker_volume_mix_semantics",
]
