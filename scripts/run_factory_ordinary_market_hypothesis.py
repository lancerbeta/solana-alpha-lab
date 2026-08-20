#!/usr/bin/env python3
"""Compose one ordinary market-feature hypothesis ExperimentSpec."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402

DEFAULT_SPEC = "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml"
NOT_A_PROMOTION_STOP = "NOT_AN_ORDINARY_PROMOTION_STOP"


def product_terminal(spec: dict, model: dict) -> str:
    declared = str((spec.get("parameters") or {}).get("product_terminal") or "")
    next_action = str((spec.get("parameters") or {}).get("next_safe_action") or "")
    unknown_blockers = [
        item
        for item in model.get("required_features") or []
        if isinstance(item, dict)
        and item.get("value_status") == "UNKNOWN"
        and item.get("value") is None
    ]
    if (
        model.get("status") == "COMPLETE"
        and model.get("terminal_result") == "FEATURE_SURFACE_COMPOSITION_PASS"
        and next_action == "DO_NOT_PROMOTE"
        and declared
        and unknown_blockers
    ):
        return declared
    return NOT_A_PROMOTION_STOP


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--spec", default=DEFAULT_SPEC)
    args = parser.parse_args()
    root = args.root.resolve()
    spec_relative = args.spec
    spec = load_experiment_spec(root, spec_relative)
    store = OperationalStore(root / "local/factory_v1/ordinary_hypothesis_ops.sqlite")
    try:
        app = FactoryApplication(root=root, store=store, spec_relative=spec_relative)
        model = app.start()
        classified = product_terminal(spec, model)
        payload = {
            "spec": spec_relative,
            "experiment_id": spec["experiment_id"],
            "hypothesis_version": model.get("hypothesis"),
            "status": model.get("status"),
            "capability_terminal": model.get("terminal_result"),
            "product_terminal": classified,
            "next_safe_action": model.get("next_safe_action"),
            "required_features": model.get("required_features") or [],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        declared = str((spec.get("parameters") or {}).get("product_terminal") or "")
        if payload["status"] != "COMPLETE":
            return 1
        if not declared or classified != declared:
            return 1
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
