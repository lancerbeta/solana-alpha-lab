#!/usr/bin/env python3
"""Offline EARLY state hypothesis + paper-plane commissioning. No network."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_state_hypothesis import (  # noqa: E402
    ATOM_ID,
    evaluate,
    load_config,
    build_cohort,
    project_operational_view,
)
from solana_alpha_lab.factory.paper_plane import run_commissioning  # noqa: E402

RUNTIME_OUT = ROOT / "docs/evidence/early_state_paper/a1_runtime_receipt_v1.json"
ACCEPTANCE_OUT = ROOT / "docs/evidence/early_state_paper/a1_acceptance_v1.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=ATOM_ID)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_config(root)

    scientific = evaluate(root, config)
    cohort, _extras = build_cohort(root, config)
    commissioning = run_commissioning(
        root,
        strategy_relatives=list(config["strategies"]),
        store_path=root / config["paper_plane_store_relative"],
        cohort=cohort,
    )
    ops_view = project_operational_view(root, config, commissioning)

    runtime = {
        "atom_id": ATOM_ID,
        "stage": config["stage"],
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "factory_core_python_changed": False,
        "factory_runner_sha256": config["factory_runner_sha256"],
        "scientific": scientific,
        "commissioning": commissioning,
        "operations_view": ops_view,
        "non_claims": scientific["non_claims"],
    }
    _write_json(RUNTIME_OUT, runtime)

    fills_by_strategy = {
        item["strategy_id"]: item["simulated_fills"]
        for item in commissioning["per_strategy"]
    }
    leverage_ok = len(set(fills_by_strategy.values())) == len(fills_by_strategy) and len(
        fills_by_strategy
    ) == 2
    acceptance = {
        "schema": "smial.early-state-paper.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "EARLY-STATE-PAPER-ACCEPTANCE-001",
        "as_of": "2026-08-21",
        "task_id": ATOM_ID,
        "scientific_terminal": scientific["terminal"],
        "product_terminal": (
            "GENERIC_RESEARCH_TO_PAPER_PLANE_PASS"
            if leverage_ok
            else "REPLAN_BESPOKE_PIPELINE_REQUIRED"
        ),
        "strategy_versions_commissioned": len(commissioning["per_strategy"]),
        "simulated_fills_by_strategy": fills_by_strategy,
        "leverage_config_only_pass": leverage_ok,
        "operations_view": ops_view,
        "micro_live_authorized": False,
        "promotable": False,
        "provider_api_rpc_wss_calls": 0,
        "next_safe_action": "ATOM3_FACTORY_REMOTE_OPERATIONS_V1",
        "non_claims": scientific["non_claims"],
        "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    _write_json(ACCEPTANCE_OUT, acceptance)
    print(
        json.dumps(
            {
                "atom_id": ATOM_ID,
                "scientific_terminal": scientific["terminal"],
                "product_terminal": acceptance["product_terminal"],
                "leverage_config_only_pass": leverage_ok,
                "runtime_out": str(RUNTIME_OUT.relative_to(root)).replace("\\", "/"),
                "acceptance_out": str(ACCEPTANCE_OUT.relative_to(root)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
