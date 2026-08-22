"""COMMISSIONING_ONLY unattended SHADOW tick over pinned offline cohort."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.paper_plane import run_shadow_tick
from solana_alpha_lab.factory.remote_ops import write_heartbeat

FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = (
    "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
)
DEFAULT_CONFIG = "configs/factory_unattended_shadow_vertical_slice_v1.yaml"


class UnattendedShadowError(ValueError):
    """Fail-closed unattended shadow commissioning errors."""


def load_shadow_config(root: Path, relative: str = DEFAULT_CONFIG) -> dict[str, Any]:
    path = root / relative
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise UnattendedShadowError("CONFIG_INVALID")
    return loaded


def assert_factory_runner_pin(root: Path, config: Mapping[str, Any]) -> None:
    expected = str(config.get("factory_runner_sha256") or "")
    if expected != FACTORY_RUNNER_SHA256:
        raise UnattendedShadowError("FACTORY_RUNNER_PIN_DRIFT")
    relative = str(config.get("factory_runner") or FACTORY_RUNNER)
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if digest != FACTORY_RUNNER_SHA256:
        raise UnattendedShadowError("FACTORY_RUNNER_HASH_DRIFT")


def run_unattended_shadow_tick(
    root: Path,
    *,
    config_relative: str = DEFAULT_CONFIG,
    store_path: Path | None = None,
) -> dict[str, Any]:
    config = load_shadow_config(root, config_relative)
    assert_factory_runner_pin(root, config)
    if config.get("scientific_promotion") != "FORBIDDEN_AFTER_ATOM1_CLOSE":
        raise UnattendedShadowError("SCIENTIFIC_PROMOTION_NOT_FORBIDDEN")

    fixture_rel = str(config.get("cohort_fixture_relative") or "")
    if not fixture_rel:
        raise UnattendedShadowError("COHORT_FIXTURE_MISSING")
    fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
    if not isinstance(fixture, dict) or not isinstance(fixture.get("rows"), list):
        raise UnattendedShadowError("COHORT_FIXTURE_INVALID")
    cohort = [row for row in fixture["rows"] if isinstance(row, dict)]
    if not cohort:
        raise UnattendedShadowError("COHORT_FIXTURE_EMPTY")
    store = store_path or (root / str(config["paper_plane_store_relative"]))
    tick = run_shadow_tick(
        root,
        strategy_relative=str(config["strategy_relative"]),
        store_path=store,
        cohort=cohort,
        max_rows=int(config.get("max_rows_per_tick") or 8),
    )

    remote_config = yaml.safe_load(
        (root / str(config["remote_ops_config_relative"])).read_text(encoding="utf-8")
    )
    if not isinstance(remote_config, dict):
        raise UnattendedShadowError("REMOTE_OPS_CONFIG_INVALID")
    heartbeat_path = write_heartbeat(
        root,
        config=remote_config,
        kind=str(config.get("heartbeat_kind") or "SHADOW_HEARTBEAT"),
        progress_at=str(tick["progress_at"]),
    )
    operations = {
        "strategy": tick["strategy_id"],
        "bot": tick["bot_instance_id"],
        "mode": "SHADOW",
        "signal": "SHADOW_EXECUTABLE" if tick["shadow_observations"] else "NO_SIGNAL",
        "position": "NONE_OPEN" if tick["open_positions"] == 0 else "HAS_OPEN",
        "exit_readiness": "IDLE",
        "reconciliation": "CLEAN" if tick["open_positions"] == 0 else "PENDING",
        "blocker": "NONE",
        "next_safe_action": "CONTINUE_SHADOW_COMMISSIONING",
    }
    return {
        "atom_id": config["atom_id"],
        "commissioning_only": True,
        "scientific_shadow_pass": False,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
        "factory_core_python_changed": False,
        "tick": tick,
        "heartbeat_path": str(heartbeat_path.relative_to(root)).replace("\\", "/"),
        "operations_view": operations,
        "cohort_rows_available": len(cohort),
        "non_claims": dict(config.get("non_claims") or {}),
    }


def dump_receipt(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
