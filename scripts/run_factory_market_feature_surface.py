#!/usr/bin/env python3
"""Compose the three offline market-feature archetype ExperimentSpecs."""

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
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402

SPECS = (
    "configs/experiment_specs/market_feature_price_path_archetype_v1.yaml",
    "configs/experiment_specs/market_feature_liquidity_archetype_v1.yaml",
    "configs/experiment_specs/market_feature_creator_pressure_archetype_v1.yaml",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    store = OperationalStore(root / "local/factory_v1/feature_surface_ops.sqlite")
    jobs = []
    for spec in SPECS:
        app = FactoryApplication(root=root, store=store, spec_relative=spec)
        job = app.start()
        jobs.append(
            {
                "spec": spec,
                "status": job.get("status"),
                "terminal": job.get("terminal_result"),
                "blocker": job.get("blocker"),
            }
        )
        if job.get("status") != "COMPLETE":
            print(json.dumps({"jobs": jobs}, indent=2, sort_keys=True))
            return 1
    print(json.dumps({"jobs": jobs, "terminal": "FEATURE_SURFACE_COMPOSITION_PASS"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
