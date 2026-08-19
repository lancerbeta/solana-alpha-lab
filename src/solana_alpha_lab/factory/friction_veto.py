"""Frozen baseline-vs-friction-veto projector. Owns no capture and no Git truth."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median, quantiles
from typing import Any, Mapping

import yaml

RULE_ID = "FRICTION_VETO_WORSE_THAN_SAMPLE_MEDIAN_X_V1"
X_FIELD = "x_quoted_roundtrip_friction"
Y_FIELD = "y_quoted_liquidation_recovery"
MORE_NEGATIVE_IS_WORSE = True
PASS_TERMINAL = "EXTEND_TO_SHADOW"
FAIL_TERMINAL = "CLOSE_EXACT_FRICTION_VETO_FAMILY"
VETO_KIND = "X_LT_SAMPLE_MEDIAN_COMPLETE_XY"
SCORABLE_AUDITION_TERMINALS = frozenset(
    {
        "DIRECTIONAL_HINT_NOT_CONFIRMATION",
        "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM",
    }
)


class FrictionVetoError(ValueError):
    """Raised when the frozen veto rule cannot be applied fail-closed."""


def load_friction_veto_rule(root: Path, relative: str) -> dict[str, Any]:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise FrictionVetoError("VETO_RULE_PATH_UNSAFE")
    loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise FrictionVetoError("VETO_RULE_INVALID")
    bind_friction_veto_rule(loaded)
    return loaded


def bind_friction_veto_rule(rule: Mapping[str, Any]) -> None:
    if str(rule.get("rule_id") or "") != RULE_ID:
        raise FrictionVetoError("VETO_RULE_ID_DRIFT")
    if str(rule.get("x_field") or "") != X_FIELD:
        raise FrictionVetoError("VETO_X_FIELD_DRIFT")
    if str(rule.get("y_field") or "") != Y_FIELD:
        raise FrictionVetoError("VETO_Y_FIELD_DRIFT")
    if str(rule.get("direction") or "") != "MORE_NEGATIVE_IS_WORSE":
        raise FrictionVetoError("VETO_DIRECTION_DRIFT")
    if str(rule.get("veto") or "") != VETO_KIND:
        raise FrictionVetoError("VETO_KIND_DRIFT")
    if str(rule.get("tie") or "") != "KEEP":
        raise FrictionVetoError("VETO_TIE_DRIFT")
    if rule.get("post_hoc_threshold_search") is not False:
        raise FrictionVetoError("VETO_POST_HOC_NOT_FORBIDDEN")
    if str(rule.get("pass_terminal") or "") != PASS_TERMINAL:
        raise FrictionVetoError("VETO_PASS_TERMINAL_DRIFT")
    if str(rule.get("fail_terminal") or "") != FAIL_TERMINAL:
        raise FrictionVetoError("VETO_FAIL_TERMINAL_DRIFT")
    required = rule.get("pass_requires")
    if not isinstance(required, Mapping):
        raise FrictionVetoError("VETO_PASS_REQUIRES_MISSING")
    if required.get("median_y_kept_gt_median_y_baseline") is not True:
        raise FrictionVetoError("VETO_MEDIAN_REQUIREMENT_DRIFT")
    if required.get("p90_y_kept_ge_p90_y_baseline") is not True:
        raise FrictionVetoError("VETO_TAIL_REQUIREMENT_DRIFT")
    if required.get("both_recent_and_traded_kept") is not True:
        raise FrictionVetoError("VETO_STRATUM_REQUIREMENT_DRIFT")


def apply_friction_veto_to_receipt(
    receipt: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    bind_friction_veto_rule(rule)
    overlaid = dict(receipt)
    audition_terminal = str(
        overlaid.get("audition_terminal")
        or overlaid.get("terminal_outcome")
        or overlaid.get("terminal")
        or ""
    )
    overlaid["audition_terminal"] = audition_terminal
    if isinstance(overlaid.get("veto"), Mapping) and str(
        overlaid["veto"].get("rule_id") or ""
    ) == RULE_ID:
        return overlaid
    if audition_terminal not in SCORABLE_AUDITION_TERMINALS:
        return overlaid
    mechanism = overlaid.get("mechanism")
    if not isinstance(mechanism, Mapping):
        raise FrictionVetoError("MECHANISM_MISSING")
    frozen = overlaid.get("frozen_cells")
    veto = classify_baseline_vs_friction_veto(
        mechanism=mechanism,
        frozen_cells=list(frozen) if isinstance(frozen, list) else [],
        rule=rule,
    )
    overlaid["veto"] = veto
    overlaid["terminal_outcome"] = str(veto["terminal"])
    overlaid["terminal"] = str(veto["terminal"])
    return overlaid


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed


def _complete_cells(
    mechanism_cells: list[Mapping[str, Any]],
    frozen_cells: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    strata = {
        str(cell.get("identity_id")): str(cell.get("stratum") or "")
        for cell in frozen_cells
        if isinstance(cell, Mapping) and cell.get("identity_id")
    }
    complete: list[dict[str, Any]] = []
    for cell in mechanism_cells:
        if not isinstance(cell, Mapping):
            continue
        if cell.get("x_status") != "OBSERVED" or cell.get("y_status") != "OBSERVED":
            continue
        x_value = _decimal(cell.get(X_FIELD))
        y_value = _decimal(cell.get(Y_FIELD))
        if x_value is None or y_value is None:
            continue
        identity = str(cell.get("identity_id") or "")
        complete.append(
            {
                "identity_id": identity,
                "stratum": strata.get(identity, ""),
                "x": x_value,
                "y": y_value,
            }
        )
    return complete


def _p90(values: list[Decimal]) -> Decimal:
    if not values:
        raise FrictionVetoError("VETO_TAIL_EMPTY")
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    ranks = quantiles(ordered, n=10, method="inclusive")
    return ranks[8]


def classify_baseline_vs_friction_veto(
    *,
    mechanism: Mapping[str, Any],
    frozen_cells: list[Mapping[str, Any]] | None = None,
    rule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rule is not None:
        bind_friction_veto_rule(rule)
    cells = mechanism.get("cells")
    if not isinstance(cells, list):
        raise FrictionVetoError("MECHANISM_CELLS_MISSING")
    complete = _complete_cells(cells, list(frozen_cells or []))
    if len(complete) < 2:
        return {
            "rule_id": RULE_ID,
            "terminal": FAIL_TERMINAL,
            "reason": "INSUFFICIENT_COMPLETE_XY",
            "baseline_n": len(complete),
            "kept_n": 0,
            "vetoed_n": 0,
        }
    x_values = [item["x"] for item in complete]
    x_median = median(x_values)
    vetoed = [item for item in complete if item["x"] < x_median]
    kept = [item for item in complete if item["x"] >= x_median]
    if not kept or not vetoed:
        return {
            "rule_id": RULE_ID,
            "terminal": FAIL_TERMINAL,
            "reason": "VETO_SPLIT_EMPTY",
            "x_median": str(x_median),
            "baseline_n": len(complete),
            "kept_n": len(kept),
            "vetoed_n": len(vetoed),
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
    terminal = PASS_TERMINAL if improves and not stratum_unstable else FAIL_TERMINAL
    reason = "MEDIAN_AND_TAIL_IMPROVE"
    if stratum_unstable:
        reason = "STRATUM_UNSTABLE"
    elif not improves:
        reason = "NO_MEDIAN_OR_TAIL_UPLIFT"
    return {
        "rule_id": RULE_ID,
        "x_field": X_FIELD,
        "y_field": Y_FIELD,
        "x_median": str(x_median),
        "baseline_n": len(complete),
        "kept_n": len(kept),
        "vetoed_n": len(vetoed),
        "median_y_baseline": str(median_y_baseline),
        "median_y_kept": str(median_y_kept),
        "p90_y_baseline": str(p90_baseline),
        "p90_y_kept": str(p90_kept),
        "kept_strata": sorted(kept_strata),
        "stratum_unstable": stratum_unstable,
        "reason": reason,
        "terminal": terminal,
    }
