"""Frozen quote-surface retention projector. Owns no capture and no Git truth."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median, quantiles
from typing import Any, Mapping

import yaml

RULE_ID = "QUOTE_SURFACE_RETENTION_DELTA_NONNEGATIVE_V1"
X_FIELD = "retention_delta"
Y_FIELD = "forward_quoted_return_h900_h3600"
PASS_TERMINAL = "FRESH_OOS_REPLICATION_EARNED"
FAIL_TERMINAL = "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY"
INCONCLUSIVE_TERMINAL = "SAMPLE_INVALID_REPLAN_REQUIRED"
KEEP_KIND = "RETENTION_DELTA_GE_ZERO_AND_H900_ROUTES_EXIST"
VETO_KIND = "RETENTION_DELTA_LT_ZERO_OR_H900_NO_ROUTE"
MIN_PER_STRATUM = 4
NO_ROUTE = "NO_ROUTE"
QUOTE_OBSERVED = "QUOTE_OBSERVED"


class QuoteSurfaceRetentionError(ValueError):
    """Raised when the frozen retention rule cannot be applied fail-closed."""


def load_quote_surface_retention_rule(root: Path, relative: str) -> dict[str, Any]:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise QuoteSurfaceRetentionError("RETENTION_RULE_PATH_UNSAFE")
    loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise QuoteSurfaceRetentionError("RETENTION_RULE_INVALID")
    bind_quote_surface_retention_rule(loaded)
    return loaded


def bind_quote_surface_retention_rule(rule: Mapping[str, Any]) -> None:
    if str(rule.get("rule_id") or "") != RULE_ID:
        raise QuoteSurfaceRetentionError("RETENTION_RULE_ID_DRIFT")
    if str(rule.get("x_field") or "") != X_FIELD:
        raise QuoteSurfaceRetentionError("RETENTION_X_FIELD_DRIFT")
    if str(rule.get("y_field") or "") != Y_FIELD:
        raise QuoteSurfaceRetentionError("RETENTION_Y_FIELD_DRIFT")
    if str(rule.get("keep") or "") != KEEP_KIND:
        raise QuoteSurfaceRetentionError("RETENTION_KEEP_DRIFT")
    if str(rule.get("veto") or "") != VETO_KIND:
        raise QuoteSurfaceRetentionError("RETENTION_VETO_DRIFT")
    if str(rule.get("unknown") or "") != "TRANSPORT_SCHEMA_OR_DATA_UNCERTAINTY":
        raise QuoteSurfaceRetentionError("RETENTION_UNKNOWN_DRIFT")
    if rule.get("unknown_is_not_veto") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_UNKNOWN_IS_VETO")
    if rule.get("unknown_is_not_numeric_zero") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_UNKNOWN_IS_ZERO")
    if str(rule.get("h3600_no_route") or "") != "PATH_RISK_NEVER_NUMERIC_ZERO":
        raise QuoteSurfaceRetentionError("RETENTION_H3600_ZERO_DRIFT")
    if str(rule.get("tie_at_zero") or "") != "KEEP":
        raise QuoteSurfaceRetentionError("RETENTION_TIE_DRIFT")
    if int(rule.get("min_complete_decision_outcome_per_stratum") or 0) != MIN_PER_STRATUM:
        raise QuoteSurfaceRetentionError("RETENTION_FLOOR_DRIFT")
    if str(rule.get("pass_terminal") or "") != PASS_TERMINAL:
        raise QuoteSurfaceRetentionError("RETENTION_PASS_TERMINAL_DRIFT")
    if str(rule.get("fail_terminal") or "") != FAIL_TERMINAL:
        raise QuoteSurfaceRetentionError("RETENTION_FAIL_TERMINAL_DRIFT")
    if str(rule.get("inconclusive_terminal") or "") != INCONCLUSIVE_TERMINAL:
        raise QuoteSurfaceRetentionError("RETENTION_INCONCLUSIVE_DRIFT")
    if rule.get("post_hoc_threshold_search") is not False:
        raise QuoteSurfaceRetentionError("RETENTION_POST_HOC_NOT_FORBIDDEN")
    if rule.get("traded_only_rescue") is not False:
        raise QuoteSurfaceRetentionError("RETENTION_TRADED_RESCUE_NOT_FORBIDDEN")
    if str(rule.get("primary_analysis") or "") != "STRATA_SEPARATE_NO_POOLED_PASS":
        raise QuoteSurfaceRetentionError("RETENTION_POOLED_PASS_NOT_FORBIDDEN")
    required = rule.get("pass_requires")
    if not isinstance(required, Mapping):
        raise QuoteSurfaceRetentionError("RETENTION_PASS_REQUIRES_MISSING")
    if required.get("median_y_kept_gt_median_y_baseline") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_MEDIAN_REQUIREMENT_DRIFT")
    if required.get("p90_y_kept_ge_p90_y_baseline") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_TAIL_REQUIREMENT_DRIFT")
    if required.get("both_recent_and_traded_kept") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_STRATUM_REQUIREMENT_DRIFT")
    if required.get("same_direction_in_both_strata") is not True:
        raise QuoteSurfaceRetentionError("RETENTION_DIRECTION_REQUIREMENT_DRIFT")


def apply_quote_surface_retention_to_receipt(
    receipt: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    bind_quote_surface_retention_rule(rule)
    overlaid = dict(receipt)
    capture = overlaid.get("capture")
    if isinstance(capture, Mapping) and capture.get("accepted") is not True:
        return overlaid
    terminal = str(overlaid.get("terminal_outcome") or overlaid.get("terminal") or "")
    if terminal in {
        "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        "RATE_LIMITED",
        "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED",
        "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
        "BLOCKED_AUTHORITY",
    }:
        return overlaid
    observations = overlaid.get("observations")
    mechanism = overlaid.get("mechanism")
    frozen = overlaid.get("frozen_cells")
    frozen_cells = list(frozen) if isinstance(frozen, list) else []
    if isinstance(observations, list) and observations:
        mechanism = score_retention_observations(
            observations,
            frozen_cells=frozen_cells,
        )
        overlaid["mechanism"] = mechanism
    if not isinstance(mechanism, Mapping) or not isinstance(mechanism.get("cells"), list):
        raise QuoteSurfaceRetentionError("RETENTION_OBSERVATIONS_MISSING")
    retention = classify_quote_surface_retention(
        mechanism=mechanism if isinstance(mechanism, Mapping) else {},
        frozen_cells=list(overlaid.get("frozen_cells") or []),
        rule=rule,
    )
    overlaid["retention"] = retention
    overlaid["terminal_outcome"] = str(retention["terminal"])
    overlaid["terminal"] = str(retention["terminal"])
    return overlaid


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed


def _ratio(out_amount: object, in_amount: object) -> Decimal | None:
    out_value = _decimal(out_amount)
    in_value = _decimal(in_amount)
    if out_value is None or in_value is None or in_value == 0:
        return None
    return out_value / in_value - Decimal(1)


def _quote_out(row: Mapping[str, Any] | None) -> str | None:
    if not isinstance(row, Mapping):
        return None
    quote = row.get("quote")
    if not isinstance(quote, Mapping):
        return None
    out_amount = quote.get("out_amount")
    return str(out_amount) if type(out_amount) is str and out_amount else None


def _p90(values: list[Decimal]) -> Decimal:
    if not values:
        raise QuoteSurfaceRetentionError("RETENTION_TAIL_EMPTY")
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    ranks = quantiles(ordered, n=10, method="inclusive")
    return ranks[8]


def score_retention_observations(
    observations: list[Mapping[str, Any]],
    *,
    frozen_cells: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    strata = {
        str(cell.get("identity_id")): str(cell.get("stratum") or "")
        for cell in list(frozen_cells or [])
        if isinstance(cell, Mapping) and cell.get("identity_id")
    }
    by_identity: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in observations:
        if not isinstance(row, Mapping):
            continue
        identity_id = str(row.get("identity_id") or "")
        kind = str(row.get("kind") or "")
        if identity_id and kind in {
            "BUY_T0",
            "REVERSE_T0",
            "BUY_H900",
            "REVERSE_H900",
            "SELL_H3600",
        }:
            by_identity.setdefault(identity_id, {})[kind] = row
    cells: list[dict[str, Any]] = []
    for identity_id, kinds in by_identity.items():
        buy_t0 = kinds.get("BUY_T0")
        reverse_t0 = kinds.get("REVERSE_T0")
        buy_h900 = kinds.get("BUY_H900")
        reverse_h900 = kinds.get("REVERSE_H900")
        sell = kinds.get("SELL_H3600")
        rtf_t0 = None
        if (
            isinstance(buy_t0, Mapping)
            and buy_t0.get("terminal") == QUOTE_OBSERVED
            and isinstance(reverse_t0, Mapping)
            and reverse_t0.get("terminal") == QUOTE_OBSERVED
        ):
            rtf_t0 = _ratio(_quote_out(reverse_t0), buy_t0.get("amount"))
        h900_buy_ok = isinstance(buy_h900, Mapping) and buy_h900.get("terminal") == QUOTE_OBSERVED
        h900_rev_ok = (
            isinstance(reverse_h900, Mapping) and reverse_h900.get("terminal") == QUOTE_OBSERVED
        )
        h900_no_route = any(
            isinstance(row, Mapping) and str(row.get("terminal") or "") == NO_ROUTE
            for row in (buy_h900, reverse_h900)
        )
        rtf_h900 = (
            _ratio(_quote_out(reverse_h900), buy_h900.get("amount") if isinstance(buy_h900, Mapping) else None)
            if h900_buy_ok and h900_rev_ok
            else None
        )
        t0_unknown = rtf_t0 is None
        h900_unknown = (
            not h900_no_route
            and not (h900_buy_ok and h900_rev_ok)
        )
        if t0_unknown or h900_unknown:
            decision = "UNKNOWN"
            delta = None
        elif h900_no_route:
            decision = "VETO"
            delta = None
        elif rtf_h900 is None:
            decision = "UNKNOWN"
            delta = None
        else:
            delta = rtf_h900 - rtf_t0
            decision = "KEEP" if delta >= 0 else "VETO"
        y_status = "MISSING"
        y_value = None
        y_path_risk = False
        if isinstance(sell, Mapping) and sell.get("terminal") == QUOTE_OBSERVED and h900_buy_ok:
            y_value = _ratio(_quote_out(sell), buy_h900.get("amount") if isinstance(buy_h900, Mapping) else None)
            y_status = "OBSERVED" if y_value is not None else "UNKNOWN"
        elif isinstance(sell, Mapping) and str(sell.get("terminal") or "") == NO_ROUTE:
            y_status = "PATH_RISK"
            y_path_risk = True
        elif isinstance(sell, Mapping) and str(sell.get("terminal") or "") not in {"SCHEDULED", "NOT_REACHED", ""}:
            y_status = "UNKNOWN"
        reverse_out = _quote_out(reverse_h900) if h900_rev_ok else None
        sell_out = _quote_out(sell) if isinstance(sell, Mapping) and sell.get("terminal") == QUOTE_OBSERVED else None
        time_separated = (
            y_status == "OBSERVED" and reverse_out is not None and sell_out is not None and reverse_out != sell_out
        )
        cells.append(
            {
                "identity_id": identity_id,
                "stratum": strata.get(identity_id, ""),
                "rtf_t0": str(rtf_t0) if rtf_t0 is not None else None,
                "rtf_h900": str(rtf_h900) if rtf_h900 is not None else None,
                "retention_delta": str(delta) if delta is not None else None,
                "decision": decision,
                "x_status": "OBSERVED" if delta is not None or decision == "VETO" else "UNKNOWN",
                "y_status": y_status,
                "y_path_risk": y_path_risk,
                "forward_quoted_return_h900_h3600": str(y_value) if y_value is not None else None,
                "time_separated": time_separated,
                "h900_no_route": h900_no_route,
            }
        )
    return {
        "scored": True,
        "searchable_y_kind": "SELL_H3600_FROM_BUY_H900",
        "cells": cells,
    }


def classify_quote_surface_retention(
    *,
    mechanism: Mapping[str, Any],
    frozen_cells: list[Mapping[str, Any]] | None = None,
    rule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rule is not None:
        bind_quote_surface_retention_rule(rule)
    cells = mechanism.get("cells")
    if not isinstance(cells, list):
        raise QuoteSurfaceRetentionError("MECHANISM_CELLS_MISSING")
    strata = {
        str(cell.get("identity_id")): str(cell.get("stratum") or "")
        for cell in list(frozen_cells or [])
        if isinstance(cell, Mapping) and cell.get("identity_id")
    }
    complete: list[dict[str, Any]] = []
    for cell in cells:
        if not isinstance(cell, Mapping):
            continue
        decision = str(cell.get("decision") or "")
        if decision not in {"KEEP", "VETO"}:
            continue
        if str(cell.get("y_status") or "") != "OBSERVED":
            continue
        y_value = _decimal(cell.get(Y_FIELD))
        if y_value is None:
            continue
        if cell.get("time_separated") is not True:
            continue
        identity = str(cell.get("identity_id") or "")
        complete.append(
            {
                "identity_id": identity,
                "stratum": str(cell.get("stratum") or strata.get(identity) or ""),
                "decision": decision,
                "y": y_value,
            }
        )
    recent_n = sum(1 for item in complete if item["stratum"] == "RECENT")
    traded_n = sum(1 for item in complete if item["stratum"] == "TRADED")
    if recent_n < MIN_PER_STRATUM or traded_n < MIN_PER_STRATUM:
        return {
            "rule_id": RULE_ID,
            "terminal": INCONCLUSIVE_TERMINAL,
            "reason": "INSUFFICIENT_VALID_CELLS_PER_STRATUM",
            "baseline_n": len(complete),
            "kept_n": 0,
            "vetoed_n": 0,
            "recent_valid_n": recent_n,
            "traded_valid_n": traded_n,
            "stratum_unstable": False,
        }
    kept = [item for item in complete if item["decision"] == "KEEP"]
    vetoed = [item for item in complete if item["decision"] == "VETO"]
    if not kept or not vetoed:
        return {
            "rule_id": RULE_ID,
            "terminal": FAIL_TERMINAL,
            "reason": "KEEP_OR_VETO_SPLIT_EMPTY",
            "baseline_n": len(complete),
            "kept_n": len(kept),
            "vetoed_n": len(vetoed),
            "recent_valid_n": recent_n,
            "traded_valid_n": traded_n,
            "stratum_unstable": False,
        }
    baseline_y = [item["y"] for item in complete]
    kept_y = [item["y"] for item in kept]
    median_y_baseline = median(baseline_y)
    median_y_kept = median(kept_y)
    p90_baseline = _p90(baseline_y)
    p90_kept = _p90(kept_y)
    kept_strata = {item["stratum"] for item in kept if item["stratum"]}
    stratum_unstable = not {"RECENT", "TRADED"}.issubset(kept_strata)
    improves = median_y_kept > median_y_baseline and p90_kept >= p90_baseline
    stratum_signs: list[bool] = []
    for stratum in ("RECENT", "TRADED"):
        baseline_s = [item["y"] for item in complete if item["stratum"] == stratum]
        kept_s = [item["y"] for item in kept if item["stratum"] == stratum]
        if not baseline_s or not kept_s:
            stratum_signs.append(False)
            continue
        stratum_signs.append(median(kept_s) > median(baseline_s))
    same_direction = len(set(stratum_signs)) == 1
    terminal = (
        PASS_TERMINAL
        if improves and not stratum_unstable and same_direction and all(stratum_signs)
        else FAIL_TERMINAL
    )
    reason = "MEDIAN_TAIL_AND_BOTH_STRATA_IMPROVE"
    if stratum_unstable:
        reason = "STRATUM_UNSTABLE"
    elif not same_direction:
        reason = "STRATUM_DIRECTION_CONFLICT"
    elif not improves:
        reason = "NO_MEDIAN_OR_TAIL_UPLIFT"
    return {
        "rule_id": RULE_ID,
        "x_field": X_FIELD,
        "y_field": Y_FIELD,
        "baseline_n": len(complete),
        "kept_n": len(kept),
        "vetoed_n": len(vetoed),
        "recent_valid_n": recent_n,
        "traded_valid_n": traded_n,
        "median_y_baseline": str(median_y_baseline),
        "median_y_kept": str(median_y_kept),
        "p90_y_baseline": str(p90_baseline),
        "p90_y_kept": str(p90_kept),
        "kept_strata": sorted(kept_strata),
        "stratum_unstable": stratum_unstable,
        "same_direction": same_direction,
        "reason": reason,
        "terminal": terminal,
    }
