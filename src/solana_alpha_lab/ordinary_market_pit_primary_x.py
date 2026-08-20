"""Fail-closed Tokens V2 snapshot bind for liquidity/mcap. Not Factory core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

BIND_ID = "ORDINARY-MARKET-PIT-PRIMARY-X-BIND-001"
PRODUCT_TERMINAL = "GIT_RETAINED_CELLS_CANNOT_BIND_PRIMARY_X"
PRIMARY_X_BOUND = "PRIMARY_X_BOUND"
PRIMARY_X_UNKNOWN = "PRIMARY_X_UNKNOWN"
AVAILABILITY_CLASS = "FORWARD_SNAPSHOT_NOT_PIT_READY"
CONFIG_RELATIVE = "configs/ordinary_market_pit_primary_x_bind_v1.yaml"
FORBIDDEN_SUBSTITUTES = ("fdv", "usdPrice", "circSupply", "totalSupply")
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"


class PrimaryXBindError(ValueError):
    """Raised when the bind config or receipt is not usable."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_bind_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PrimaryXBindError("BIND_CONFIG_INVALID")
    primary = loaded.get("primary_x")
    if not isinstance(primary, dict):
        raise PrimaryXBindError("BIND_CONFIG_INVALID")
    if primary.get("numerator_field") != "liquidity":
        raise PrimaryXBindError("NUMERATOR_NOT_LIQUIDITY")
    if primary.get("denominator_field") != "mcap":
        raise PrimaryXBindError("DENOMINATOR_NOT_MCAP")
    forbidden = tuple(primary.get("forbidden_substitutes") or ())
    if forbidden != FORBIDDEN_SUBSTITUTES:
        raise PrimaryXBindError("FORBIDDEN_SUBSTITUTES_DRIFT")
    if loaded.get("availability_class") != AVAILABILITY_CLASS:
        raise PrimaryXBindError("AVAILABILITY_CLASS_DRIFT")
    if int(loaded.get("evidence_budget", {}).get("provider_api_rpc_wss_calls", 1)) != 0:
        raise PrimaryXBindError("LIVE_CAPTURE_NOT_IN_SCOPE")
    return loaded


def _finite_number(value: object) -> float | None:
    if type(value) is bool:
        return None
    if type(value) is int or type(value) is float:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return None
        return number
    if type(value) is str:
        try:
            number = float(value)
        except ValueError:
            return None
        if number != number or number in {float("inf"), float("-inf")}:
            return None
        return number
    return None


def bind_primary_x(
    item: Mapping[str, Any],
    *,
    observed_at: str | None,
) -> dict[str, Any]:
    liquidity = _finite_number(item.get("liquidity"))
    mcap = _finite_number(item.get("mcap"))
    used_substitute = any(key in item and item.get("mcap") is None for key in FORBIDDEN_SUBSTITUTES)
    if liquidity is None or mcap is None or mcap == 0:
        return {
            "status": PRIMARY_X_UNKNOWN,
            "value": None,
            "liquidity": liquidity,
            "mcap": mcap,
            "availability_class": AVAILABILITY_CLASS,
            "observed_at": observed_at,
            "available_to_strategy_at": observed_at,
            "substitute_rejected": used_substitute,
            "pit_ready": False,
        }
    return {
        "status": PRIMARY_X_BOUND,
        "value": liquidity / mcap,
        "liquidity": liquidity,
        "mcap": mcap,
        "availability_class": AVAILABILITY_CLASS,
        "observed_at": observed_at,
        "available_to_strategy_at": observed_at,
        "substitute_rejected": False,
        "pit_ready": False,
    }


def bind_git_retained_cells(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    retained = config.get("git_retained_cells")
    if not isinstance(retained, dict):
        raise PrimaryXBindError("GIT_RETAINED_CELLS_INVALID")
    relative = retained.get("path")
    expected = retained.get("sha256")
    if type(relative) is not str or type(expected) is not str:
        raise PrimaryXBindError("GIT_RETAINED_CELLS_INVALID")
    payload = (root / relative).read_bytes()
    digest = sha256_bytes(payload)
    if digest != expected:
        raise PrimaryXBindError("GIT_RETAINED_RECEIPT_HASH_MISMATCH")
    receipt = json.loads(payload.decode("utf-8"))
    cells = receipt.get("frozen_cells")
    if not isinstance(cells, list) or not cells:
        raise PrimaryXBindError("FROZEN_CELLS_MISSING")
    rows = [bind_primary_x(cell, observed_at=None) for cell in cells if isinstance(cell, Mapping)]
    bound = sum(1 for row in rows if row["status"] == PRIMARY_X_BOUND)
    unknown = sum(1 for row in rows if row["status"] == PRIMARY_X_UNKNOWN)
    mcap_present = sum(1 for cell in cells if isinstance(cell, Mapping) and "mcap" in cell)
    terminal = PRODUCT_TERMINAL if bound == 0 and unknown == len(rows) else "PRIMARY_X_PRESENT_ON_GIT_CELLS"
    return {
        "bind_id": BIND_ID,
        "hypothesis_version": config.get("hypothesis_version"),
        "product_terminal": terminal,
        "next_safe_action": config.get("next_safe_action"),
        "cell_count": len(rows),
        "primary_x_bound_count": bound,
        "primary_x_unknown_count": unknown,
        "mcap_key_count": mcap_present,
        "receipt_path": relative,
        "receipt_sha256": digest,
        "availability_class": AVAILABILITY_CLASS,
        "pit_ready_count": 0,
        "provider_api_rpc_wss_calls": 0,
        "factory_runner_sha256": sha256_bytes((root / FACTORY_RUNNER).read_bytes()),
        "rows": rows,
    }
