"""Frozen prior-Git t0 friction-screen projector. Owns no capture and no Git truth."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.friction_veto import (
    SCORABLE_AUDITION_TERMINALS,
    X_FIELD,
    Y_FIELD,
    _complete_cells,
    _p90,
)

RULE_ID = "PRIOR_GIT_T0_FRICTION_SCREEN_V1"
MORE_NEGATIVE_IS_WORSE = True
PASS_TERMINAL = "EXTEND_TO_SHADOW"
FAIL_TERMINAL = "CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY"
VETO_KIND = "X_LT_FROZEN_PRIOR_GIT_MEDIAN"
FROZEN_X_CUTOFF_TEXT = "-0.0205835"
FROZEN_X_CUTOFF = Decimal(FROZEN_X_CUTOFF_TEXT)
FORBIDDEN_PEEKED_CUTOFF_TEXT = "-0.0116887"
CUTOFF_N_COMPLETE_XY = 33
SOURCE_RECEIPT_SHA256 = {
    "docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json": (
        "75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e"
    ),
    "docs/evidence/quote_native_friction_h900_move2_oos/a1_quote_native_friction_h900_move2_oos_runtime_receipt_v1.json": (
        "a860888cd6c528c03cffb27146d07da6ed60770d0f1e13d47651b0d63f51b926"
    ),
    "docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_runtime_receipt_v1.json": (
        "f83968a0be381f874a38ed214c1f9ff1a5ac46bc433c502417d35d8f31727468"
    ),
}


class T0FrictionScreenError(ValueError):
    """Raised when the frozen prior-Git t0 screen cannot be applied fail-closed."""


def load_t0_friction_screen_rule(root: Path, relative: str) -> dict[str, Any]:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise T0FrictionScreenError("T0_SCREEN_RULE_PATH_UNSAFE")
    loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise T0FrictionScreenError("T0_SCREEN_RULE_INVALID")
    bind_t0_friction_screen_rule(loaded)
    return loaded


def bind_t0_friction_screen_rule(rule: Mapping[str, Any]) -> None:
    if str(rule.get("rule_id") or "") != RULE_ID:
        raise T0FrictionScreenError("T0_SCREEN_RULE_ID_DRIFT")
    if str(rule.get("x_field") or "") != X_FIELD:
        raise T0FrictionScreenError("T0_SCREEN_X_FIELD_DRIFT")
    if str(rule.get("y_field") or "") != Y_FIELD:
        raise T0FrictionScreenError("T0_SCREEN_Y_FIELD_DRIFT")
    if str(rule.get("direction") or "") != "MORE_NEGATIVE_IS_WORSE":
        raise T0FrictionScreenError("T0_SCREEN_DIRECTION_DRIFT")
    if str(rule.get("veto") or "") != VETO_KIND:
        raise T0FrictionScreenError("T0_SCREEN_KIND_DRIFT")
    if str(rule.get("tie") or "") != "KEEP":
        raise T0FrictionScreenError("T0_SCREEN_TIE_DRIFT")
    if rule.get("post_hoc_threshold_search") is not False:
        raise T0FrictionScreenError("T0_SCREEN_POST_HOC_NOT_FORBIDDEN")
    if str(rule.get("pass_terminal") or "") != PASS_TERMINAL:
        raise T0FrictionScreenError("T0_SCREEN_PASS_TERMINAL_DRIFT")
    if str(rule.get("fail_terminal") or "") != FAIL_TERMINAL:
        raise T0FrictionScreenError("T0_SCREEN_FAIL_TERMINAL_DRIFT")
    cutoff = rule.get("frozen_x_cutoff")
    if not isinstance(cutoff, str) or cutoff != FROZEN_X_CUTOFF_TEXT:
        raise T0FrictionScreenError("T0_SCREEN_CUTOFF_DRIFT")
    peeked = rule.get("forbidden_peeked_cutoff")
    if not isinstance(peeked, str) or peeked != FORBIDDEN_PEEKED_CUTOFF_TEXT:
        raise T0FrictionScreenError("T0_SCREEN_PEEKED_CUTOFF_DRIFT")
    if cutoff == peeked:
        raise T0FrictionScreenError("T0_SCREEN_USES_PEEKED_ATOM5_MEDIAN")
    if int(rule.get("cutoff_n_complete_xy") or 0) != CUTOFF_N_COMPLETE_XY:
        raise T0FrictionScreenError("T0_SCREEN_CUTOFF_N_DRIFT")
    sources = rule.get("cutoff_source_receipts")
    if not isinstance(sources, list) or len(sources) != len(SOURCE_RECEIPT_SHA256):
        raise T0FrictionScreenError("T0_SCREEN_CUTOFF_SOURCES_DRIFT")
    observed: dict[str, str] = {}
    for item in sources:
        if not isinstance(item, Mapping):
            raise T0FrictionScreenError("T0_SCREEN_CUTOFF_SOURCES_DRIFT")
        observed[str(item.get("path") or "")] = str(item.get("sha256") or "")
    if observed != SOURCE_RECEIPT_SHA256:
        raise T0FrictionScreenError("T0_SCREEN_CUTOFF_SOURCES_DRIFT")
    required = rule.get("pass_requires")
    if not isinstance(required, Mapping):
        raise T0FrictionScreenError("T0_SCREEN_PASS_REQUIRES_MISSING")
    if required.get("median_y_kept_gt_median_y_baseline") is not True:
        raise T0FrictionScreenError("T0_SCREEN_MEDIAN_REQUIREMENT_DRIFT")
    if required.get("p90_y_kept_ge_p90_y_baseline") is not True:
        raise T0FrictionScreenError("T0_SCREEN_TAIL_REQUIREMENT_DRIFT")
    if required.get("both_recent_and_traded_kept") is not True:
        raise T0FrictionScreenError("T0_SCREEN_STRATUM_REQUIREMENT_DRIFT")


def apply_t0_friction_screen_to_receipt(
    receipt: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    bind_t0_friction_screen_rule(rule)
    overlaid = dict(receipt)
    audition_terminal = str(
        overlaid.get("audition_terminal")
        or overlaid.get("terminal_outcome")
        or overlaid.get("terminal")
        or ""
    )
    overlaid["audition_terminal"] = audition_terminal
    if isinstance(overlaid.get("t0_screen"), Mapping) and str(
        overlaid["t0_screen"].get("rule_id") or ""
    ) == RULE_ID:
        return overlaid
    if audition_terminal not in SCORABLE_AUDITION_TERMINALS:
        return overlaid
    mechanism = overlaid.get("mechanism")
    if not isinstance(mechanism, Mapping):
        raise T0FrictionScreenError("MECHANISM_MISSING")
    frozen = overlaid.get("frozen_cells")
    screen = classify_prior_git_t0_friction_screen(
        mechanism=mechanism,
        frozen_cells=list(frozen) if isinstance(frozen, list) else [],
        rule=rule,
    )
    overlaid["t0_screen"] = screen
    overlaid["terminal_outcome"] = str(screen["terminal"])
    overlaid["terminal"] = str(screen["terminal"])
    return overlaid


def classify_prior_git_t0_friction_screen(
    *,
    mechanism: Mapping[str, Any],
    frozen_cells: list[Mapping[str, Any]] | None = None,
    rule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rule is not None:
        bind_t0_friction_screen_rule(rule)
    cells = mechanism.get("cells")
    if not isinstance(cells, list):
        raise T0FrictionScreenError("MECHANISM_CELLS_MISSING")
    complete = _complete_cells(cells, list(frozen_cells or []))
    if len(complete) < 2:
        return {
            "rule_id": RULE_ID,
            "terminal": FAIL_TERMINAL,
            "reason": "INSUFFICIENT_COMPLETE_XY",
            "baseline_n": len(complete),
            "kept_n": 0,
            "vetoed_n": 0,
            "frozen_x_cutoff": FROZEN_X_CUTOFF_TEXT,
        }
    vetoed = [item for item in complete if item["x"] < FROZEN_X_CUTOFF]
    kept = [item for item in complete if item["x"] >= FROZEN_X_CUTOFF]
    if not kept or not vetoed:
        return {
            "rule_id": RULE_ID,
            "terminal": FAIL_TERMINAL,
            "reason": "VETO_SPLIT_EMPTY",
            "frozen_x_cutoff": FROZEN_X_CUTOFF_TEXT,
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
        "frozen_x_cutoff": FROZEN_X_CUTOFF_TEXT,
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
