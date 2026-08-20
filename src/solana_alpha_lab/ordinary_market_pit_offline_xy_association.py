"""Join bound liquidity/mcap X to already-captured forward quote Y.

Not a PIT trial. Not Factory core. Not live capture. Quote is Y only.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.ordinary_market_pit_primary_x import (
    AVAILABILITY_CLASS,
    FACTORY_RUNNER,
    PRIMARY_X_BOUND,
    sha256_bytes,
)

ASSOCIATION_ID = "ORDINARY-MARKET-PIT-OFFLINE-XY-ASSOCIATION-001"
PRODUCT_TERMINAL = "EXPLORATORY_ASSOCIATION_NOT_PIT"
FAMILY_DECISION = "DEFER_FRESH_PIT_CAPTURE"
CONFIG_RELATIVE = "configs/ordinary_market_pit_offline_xy_association_v1.yaml"
Y_FIELD = "y_quoted_liquidation_recovery"
FORBIDDEN_Y_FIELDS = ("x_quoted_roundtrip_friction",)
MIN_STRATUM_N = 6
STRATA = ("RECENT", "TRADED")


class OfflineXyAssociationError(ValueError):
    """Raised when Git receipts cannot be joined fail-closed."""


def load_association_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise OfflineXyAssociationError("ASSOCIATION_CONFIG_INVALID")
    if loaded.get("y_field") != Y_FIELD:
        raise OfflineXyAssociationError("Y_FIELD_NOT_FORWARD_RECOVERY")
    forbidden = tuple(loaded.get("forbidden_y_fields") or ())
    if forbidden != FORBIDDEN_Y_FIELDS:
        raise OfflineXyAssociationError("FORBIDDEN_Y_FIELDS_DRIFT")
    if int(loaded.get("min_stratum_n") or 0) != MIN_STRATUM_N:
        raise OfflineXyAssociationError("MIN_STRATUM_N_DRIFT")
    if loaded.get("availability_class") != AVAILABILITY_CLASS:
        raise OfflineXyAssociationError("AVAILABILITY_CLASS_DRIFT")
    if loaded.get("family_decision") != FAMILY_DECISION:
        raise OfflineXyAssociationError("FAMILY_DECISION_NOT_DEFER")
    if loaded.get("product_terminal") != PRODUCT_TERMINAL:
        raise OfflineXyAssociationError("PRODUCT_TERMINAL_DRIFT")
    return loaded


def _load_pinned_json(root: Path, spec: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    rel = spec.get("path")
    expected = spec.get("sha256")
    if not isinstance(rel, str) or not isinstance(expected, str):
        raise OfflineXyAssociationError(f"{label}_PIN_INVALID")
    path = root / rel
    payload = path.read_bytes()
    digest = sha256_bytes(payload)
    if digest != expected:
        raise OfflineXyAssociationError(f"{label}_SHA256_MISMATCH")
    loaded = json.loads(payload.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise OfflineXyAssociationError(f"{label}_JSON_INVALID")
    return loaded


def _finite_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if not number.is_finite():
        return None
    return number


def kendall_comparable(xs: list[Decimal], ys: list[Decimal]) -> dict[str, Any]:
    if len(xs) != len(ys):
        raise OfflineXyAssociationError("KENDALL_LENGTH_MISMATCH")
    concordant = 0
    discordant = 0
    for i, x_i in enumerate(xs):
        for j in range(i + 1, len(xs)):
            dx = (x_i > xs[j]) - (x_i < xs[j])
            dy = (ys[i] > ys[j]) - (ys[i] < ys[j])
            if dx == 0 or dy == 0:
                continue
            if dx * dy > 0:
                concordant += 1
            else:
                discordant += 1
    comparable = concordant + discordant
    tau = (
        str((Decimal(concordant) - Decimal(discordant)) / Decimal(comparable))
        if comparable
        else None
    )
    if comparable == 0:
        hint = "NO_COMPARABLE_PAIRS"
    elif concordant > discordant:
        hint = "EXPLORATORY_POSITIVE"
    elif concordant < discordant:
        hint = "EXPLORATORY_NEGATIVE"
    else:
        hint = "EXPLORATORY_TIE"
    return {
        "concordant_pairs": concordant,
        "discordant_pairs": discordant,
        "comparable_pairs": comparable,
        "tau": tau,
        "hint": hint,
    }


def _campaign_cells(qualification: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    campaign = qualification.get("campaign")
    if not isinstance(campaign, Mapping):
        raise OfflineXyAssociationError("QUALIFICATION_CAMPAIGN_MISSING")
    cells = campaign.get("cells")
    if not isinstance(cells, list) or not cells:
        raise OfflineXyAssociationError("QUALIFICATION_CELLS_MISSING")
    by_id: dict[str, dict[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, Mapping):
            raise OfflineXyAssociationError("QUALIFICATION_CELL_INVALID")
        identity = cell.get("identity_id")
        if not isinstance(identity, str) or identity in by_id:
            raise OfflineXyAssociationError("QUALIFICATION_IDENTITY_INVALID")
        by_id[identity] = dict(cell)
    return by_id


def _join_status(*, x_bound: bool, y_observed: bool, x_value: Decimal | None, y_value: Decimal | None) -> str:
    if x_bound and y_observed and x_value is not None and y_value is not None:
        return "COMPLETE_XY"
    if x_bound and not y_observed:
        return "X_BOUND_Y_MISSING"
    if (not x_bound) and y_observed:
        return "X_MISSING_Y_OBSERVED"
    return "INCOMPLETE_XY"


def _stratum_block(rows: list[dict[str, Any]], *, min_n: int) -> dict[str, Any]:
    complete = [row for row in rows if row["join_status"] == "COMPLETE_XY"]
    n = len(complete)
    if n < min_n:
        return {
            "n_complete": n,
            "status": "INCONCLUSIVE_STRATUM",
            "concordant_pairs": None,
            "discordant_pairs": None,
            "comparable_pairs": None,
            "tau": None,
            "hint": "BELOW_MIN_STRATUM_N",
        }
    rank = kendall_comparable(
        [Decimal(str(row["x_value"])) for row in complete],
        [Decimal(str(row["y_value"])) for row in complete],
    )
    return {
        "n_complete": n,
        "status": "EXPLORATORY_RANK_COMPUTED",
        **rank,
    }


def associate_offline_xy(root: Path, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    loaded = dict(config or load_association_config(root))
    bind = _load_pinned_json(root, loaded["x_receipt"], label="X_RECEIPT")
    qualification = _load_pinned_json(root, loaded["y_receipt"], label="Y_RECEIPT")
    if bind.get("product_terminal") != "LOCAL_RAW_ENVELOPES_BIND_PRIMARY_X":
        raise OfflineXyAssociationError("X_RECEIPT_TERMINAL_DRIFT")
    cells = _campaign_cells(qualification)
    bind_rows = bind.get("rows")
    if not isinstance(bind_rows, list) or not bind_rows:
        raise OfflineXyAssociationError("X_ROWS_MISSING")

    rows: list[dict[str, Any]] = []
    for item in bind_rows:
        if not isinstance(item, Mapping):
            raise OfflineXyAssociationError("X_ROW_INVALID")
        identity = item.get("identity_id")
        if not isinstance(identity, str):
            raise OfflineXyAssociationError("X_IDENTITY_INVALID")
        cell = cells.get(identity)
        if cell is None:
            raise OfflineXyAssociationError(f"Y_CELL_MISSING:{identity}")
        x_bound = item.get("status") == PRIMARY_X_BOUND
        x_value = _finite_decimal(item.get("value")) if x_bound else None
        y_status = cell.get("y_status")
        y_observed = y_status == "OBSERVED"
        y_value = _finite_decimal(cell.get(Y_FIELD)) if y_observed else None
        if y_status != "OBSERVED" and y_value is not None:
            raise OfflineXyAssociationError("MISSING_Y_NUMERIC_LEAK")
        join_status = _join_status(
            x_bound=x_bound,
            y_observed=y_observed,
            x_value=x_value,
            y_value=y_value,
        )
        rows.append(
            {
                "identity_id": identity,
                "mint": item.get("mint"),
                "stratum": item.get("stratum"),
                "x_status": item.get("status"),
                "x_value": str(x_value) if x_value is not None else None,
                "y_status": y_status,
                "y_field": Y_FIELD,
                "y_value": str(y_value) if y_value is not None else None,
                "join_status": join_status,
                "pit_ready": False,
                "availability_class": AVAILABILITY_CLASS,
            }
        )

    complete_rows = [row for row in rows if row["join_status"] == "COMPLETE_XY"]
    missing_y = [row["identity_id"] for row in rows if row["join_status"] == "X_BOUND_Y_MISSING"]
    strata = {
        name: _stratum_block([row for row in rows if row["stratum"] == name], min_n=MIN_STRATUM_N)
        for name in STRATA
    }
    combined = _stratum_block(rows, min_n=MIN_STRATUM_N)
    # Combined n=10 meets min_n but still cannot decide the family: not PIT,
    # not outcome-blind for this X. Keep the rank as exploratory only.
    if combined["status"] == "EXPLORATORY_RANK_COMPUTED":
        combined["status"] = "EXPLORATORY_COMBINED_NOT_FAMILY_DECISION"

    return {
        "association_id": ASSOCIATION_ID,
        "hypothesis_version": loaded.get("hypothesis_version"),
        "product_terminal": PRODUCT_TERMINAL,
        "family_decision": FAMILY_DECISION,
        "next_safe_action": loaded.get("next_safe_action"),
        "availability_class": AVAILABILITY_CLASS,
        "cell_count": len(rows),
        "complete_xy_count": len(complete_rows),
        "x_bound_count": sum(1 for row in rows if row["x_status"] == PRIMARY_X_BOUND),
        "y_missing_identities": missing_y,
        "pit_ready_count": 0,
        "provider_api_rpc_wss_calls": 0,
        "y_field": Y_FIELD,
        "forbidden_y_fields": list(FORBIDDEN_Y_FIELDS),
        "min_stratum_n": MIN_STRATUM_N,
        "factory_runner": FACTORY_RUNNER,
        "x_receipt_sha256": loaded["x_receipt"]["sha256"],
        "y_receipt_sha256": loaded["y_receipt"]["sha256"],
        "strata": strata,
        "combined": combined,
        "rows": rows,
    }
