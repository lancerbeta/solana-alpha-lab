"""Offline R0_TAKER_VOLUME_MIX scoring over a frozen forward H900 capture dataset."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from solana_alpha_lab.factory.early_market_panel_field_semantics import classify_r0_mix
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    QUOTE_OBSERVED,
    _kendall_tau_b,
)

CLOSE_TERMINAL = "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY"
EARN_TERMINAL = "EARN_ONE_CONFIRMATORY_FRESH_OOS"
INVALID_TERMINAL = "INVALID_EVIDENCE_REPLAN"
MIN_ELIGIBLE = 10
MIN_RANKABLE = 8


def score_frozen_mix_dataset(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    missing: dict[str, int] = {}
    for raw in rows:
        search_row = raw.get("search_row")
        if not isinstance(search_row, Mapping):
            missing["SEARCH_ROW_ABSENT"] = missing.get("SEARCH_ROW_ABSENT", 0) + 1
            continue
        value, code = classify_r0_mix(search_row)
        if code is not None or value is None:
            missing[str(code or "MIX_UNKNOWN")] = missing.get(str(code or "MIX_UNKNOWN"), 0) + 1
            continue
        item = dict(raw)
        item["x"] = value
        scored.append(item)
    rankable = [
        row
        for row in scored
        if row.get("h900_terminal") == QUOTE_OBSERVED and isinstance(row.get("y"), (int, float))
    ]
    result: dict[str, Any] = {
        "mix_eligible": len(scored),
        "rankable_h900": len(rankable),
        "missingness": missing,
        "tau_b": None,
        "tau_b_floor": "forbidden",
        "quartile": False,
        "leave_one_out": False,
        "classifier": "classify_r0_mix",
        "classifier_context": "OFFLINE_FROZEN_DATASET_ONLY",
    }
    if len(scored) < MIN_ELIGIBLE or len(rankable) < MIN_RANKABLE:
        result["terminal"] = INVALID_TERMINAL
        return result
    tau = _kendall_tau_b(
        [{"x": float(row["x"]), "y": float(row["y"])} for row in rankable]
    )
    result["tau_b"] = tau
    if tau is None or tau <= 0:
        result["terminal"] = CLOSE_TERMINAL
    else:
        result["terminal"] = EARN_TERMINAL
    return result
