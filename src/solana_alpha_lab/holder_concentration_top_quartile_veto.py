"""Offline HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1 scorer.

Knows only ordinary {mint, x, x_status, h900_terminal, y} analytical rows.
No provider, network, campaign, H900, or Kendall orchestration.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


RULE_ID = "HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1"
ATOM_ID = "EARLY_HOLDER_CONCENTRATION_ACTIONABILITY_RULE_OOS_V1"
PASS = "PASS"
VETO_HIGH_X = "VETO_HIGH_X"
VETO_UNKNOWN = "VETO_UNKNOWN"
QUOTE_OBSERVED = "QUOTE_OBSERVED"
MARKET_EXECUTION_UNAVAILABLE = "MARKET_EXECUTION_UNAVAILABLE"
X_ELIGIBLE = "ELIGIBLE"
PHASE_A_FAIL_TERMINAL = "REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO"
PHASE_A_SURVIVE_TERMINAL = "PHASE_A_SURVIVES_TOP_QUARTILE_VETO"
PASS_COUNT_MIN = 12
VETO_FRACTION_DENOMINATOR = 4

WINDOW_A_ID = "EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1"
WINDOW_B_ID = "EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1"
WINDOW_A_RECEIPT = (
    "docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json"
)
WINDOW_B_RECEIPT = (
    "docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_runtime_receipt_v1.json"
)


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _p25(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * 0.25
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _strict_gt(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and left > right


def veto_count(valid_x_eligible_count: int) -> int:
    if valid_x_eligible_count <= 0:
        return 0
    return math.ceil(valid_x_eligible_count / VETO_FRACTION_DENOMINATOR)


def is_x_valid(row: Mapping[str, Any]) -> bool:
    return row.get("x_status") == X_ELIGIBLE and _finite_number(row.get("x"))


def is_rankable(row: Mapping[str, Any]) -> bool:
    return row.get("h900_terminal") == QUOTE_OBSERVED and _finite_number(row.get("y"))


def is_operational_bad(row: Mapping[str, Any]) -> bool:
    if row.get("h900_terminal") == MARKET_EXECUTION_UNAVAILABLE:
        return True
    return is_rankable(row) and float(row["y"]) < 0


def assign_rule_labels(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "mint": str(row.get("mint", "")),
            "x": row.get("x"),
            "x_status": row.get("x_status"),
            "h900_terminal": row.get("h900_terminal"),
            "y": row.get("y"),
        }
        if is_x_valid(item):
            valid.append(item)
        else:
            item["rule_label"] = VETO_UNKNOWN
            labeled.append(item)
    ordered = sorted(valid, key=lambda row: (-float(row["x"]), str(row["mint"])))
    n_veto = veto_count(len(ordered))
    for index, item in enumerate(ordered):
        item["rule_label"] = VETO_HIGH_X if index < n_veto else PASS
        labeled.append(item)
    return labeled


def _group(rows: Sequence[Mapping[str, Any]], label: str) -> list[Mapping[str, Any]]:
    return [row for row in rows if row.get("rule_label") == label]


def _rankable_y(rows: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(row["y"]) for row in rows if is_rankable(row)]


def summarize_labeled_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    x_valid = [row for row in rows if row.get("rule_label") in {PASS, VETO_HIGH_X}]
    pass_rows = _group(rows, PASS)
    veto_rows = _group(rows, VETO_HIGH_X)
    unknown_rows = _group(rows, VETO_UNKNOWN)
    pass_y = _rankable_y(pass_rows)
    veto_y = _rankable_y(veto_rows)
    all_y = _rankable_y(x_valid)

    def _availability(group: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        return {
            "h900_quote_available": sum(
                1 for row in group if row.get("h900_terminal") == QUOTE_OBSERVED
            ),
            "market_execution_unavailable": sum(
                1 for row in group if row.get("h900_terminal") == MARKET_EXECUTION_UNAVAILABLE
            ),
        }

    def _rates(group: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
        if not group:
            return {"negative_y_rate": None, "operational_bad_rate": None}
        rankable = [row for row in group if is_rankable(row)]
        negative = sum(1 for row in rankable if float(row["y"]) < 0)
        bad = sum(1 for row in group if is_operational_bad(row))
        return {
            "negative_y_rate": (negative / len(rankable)) if rankable else None,
            "operational_bad_rate": bad / len(group),
        }

    pass_rates = _rates(pass_rows)
    veto_rates = _rates(veto_rows)
    all_rates = _rates(x_valid)
    return {
        "decision_time_eligible_count": len(rows),
        "x_valid_count": len(x_valid),
        "x_missing_count": len(unknown_rows),
        "pass_count": len(pass_rows),
        "veto_high_x_count": len(veto_rows),
        "pass": {
            **_availability(pass_rows),
            "median_y": _median(pass_y),
            "mean_y": _mean(pass_y),
            "p25_y": _p25(pass_y),
            "rankable_count": len(pass_y),
            **pass_rates,
        },
        "veto_high_x": {
            **_availability(veto_rows),
            "median_y": _median(veto_y),
            "mean_y": _mean(veto_y),
            "p25_y": _p25(veto_y),
            "rankable_count": len(veto_y),
            **veto_rates,
        },
        "all_x_valid": {
            **_availability(x_valid),
            "median_y": _median(all_y),
            "mean_y": _mean(all_y),
            "p25_y": _p25(all_y),
            "rankable_count": len(all_y),
            **all_rates,
        },
    }


def adjudicate_phase_a_windows(
    window_summaries: Mapping[str, Mapping[str, Any]],
    *,
    pooled: Mapping[str, Any],
    pass_count_min: int = PASS_COUNT_MIN,
) -> dict[str, Any]:
    directional: dict[str, bool] = {}
    downside: dict[str, bool] = {}
    coverage: dict[str, bool] = {}
    for window_id, summary in window_summaries.items():
        pass_block = summary["pass"]
        veto_block = summary["veto_high_x"]
        all_block = summary["all_x_valid"]
        directional[window_id] = _strict_gt(
            pass_block["median_y"], veto_block["median_y"]
        ) and _strict_gt(pass_block["median_y"], all_block["median_y"])
        pass_bad = pass_block["operational_bad_rate"]
        all_bad = all_block["operational_bad_rate"]
        downside[window_id] = (
            pass_bad is not None and all_bad is not None and pass_bad < all_bad
        )
        coverage[window_id] = int(summary["pass_count"]) >= pass_count_min
    pooled_pass_median = pooled["pass"]["median_y"]
    economic = pooled_pass_median is not None and pooled_pass_median > 0
    survived = (
        all(directional.values())
        and all(downside.values())
        and all(coverage.values())
        and economic
    )
    return {
        "directional_utility": directional,
        "economic_plausibility_pooled_median_y_pass_gt_0": economic,
        "downside_utility": downside,
        "coverage": coverage,
        "survived": survived,
        "terminal": PHASE_A_SURVIVE_TERMINAL if survived else PHASE_A_FAIL_TERMINAL,
    }


def rows_from_runtime_receipt(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates = receipt.get("candidate_observations")
    observations = receipt.get("observations")
    if not isinstance(candidates, list):
        raise ValueError("CANDIDATE_OBSERVATIONS_REQUIRED")
    observed_by_mint: dict[str, Mapping[str, Any]] = {}
    if isinstance(observations, list):
        for row in observations:
            if isinstance(row, Mapping) and row.get("mint"):
                observed_by_mint[str(row["mint"])] = row
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        mint = str(candidate.get("mint", ""))
        observed = observed_by_mint.get(mint, {})
        rows.append(
            {
                "mint": mint,
                "x": candidate.get("x"),
                "x_status": candidate.get("x_status"),
                "h900_terminal": observed.get("h900_terminal"),
                "y": observed.get("y"),
            }
        )
    return rows


def score_window_receipt(receipt: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labeled = assign_rule_labels(rows_from_runtime_receipt(receipt))
    return labeled, summarize_labeled_rows(labeled)


def score_phase_a(
    receipts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    window_rows: dict[str, list[dict[str, Any]]] = {}
    window_summaries: dict[str, dict[str, Any]] = {}
    pooled_rows: list[dict[str, Any]] = []
    for window_id, receipt in receipts.items():
        labeled, summary = score_window_receipt(receipt)
        window_rows[window_id] = labeled
        window_summaries[window_id] = summary
        pooled_rows.extend(labeled)
    pooled = summarize_labeled_rows(pooled_rows)
    adjudication = adjudicate_phase_a_windows(window_summaries, pooled=pooled)
    return {
        "schema": "smial.holder-concentration-top-quartile-veto-phase-a",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "rule_id": RULE_ID,
        "network": False,
        "provider": False,
        "windows": window_summaries,
        "pooled": pooled,
        "adjudication": adjudication,
        "terminal": adjudication["terminal"],
        "mechanism_status": "HOLDER_CONCENTRATION_MECHANISM_REPLICATED",
        "non_claims": {
            "alpha": False,
            "netreturn": False,
            "execution": False,
            "strategy": False,
            "shadow": False,
            "paper": False,
        },
        "labeled_rows": window_rows,
    }


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("RECEIPT_MUST_BE_OBJECT")
    return payload


def score_phase_a_from_paths(root: Path) -> dict[str, Any]:
    receipts = {
        WINDOW_A_ID: load_json(root / WINDOW_A_RECEIPT),
        WINDOW_B_ID: load_json(root / WINDOW_B_RECEIPT),
    }
    result = score_phase_a(receipts)
    result["development_receipts"] = [WINDOW_A_RECEIPT, WINDOW_B_RECEIPT]
    return result
