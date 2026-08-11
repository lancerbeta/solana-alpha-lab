"""Render the TASK-30 A12 offline forward raw-trade route readout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_forward_raw_trade_route import (
    evaluate_forward_coverage,
    render_forward_raw_trade_route_readout,
)


def load_yaml(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"YAML_OBJECT_REQUIRED:{path}")
    return document


def frozen_group(path: Path) -> dict:
    for group in load_yaml(path)["hypothesis_groups"]:
        if isinstance(group, dict) and group.get("group_id") == "RC001-H07-H01-LIQUIDITY-RETENTION":
            return group
    raise ValueError("FROZEN_GROUP_MISSING")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "task30" / "forward_raw_trade_route_v1.json").read_text(
            encoding="utf-8"
        )
    )
    result = evaluate_forward_coverage(
        load_yaml(ROOT / "configs" / "task30_forward_raw_trade_route_contract_v1.yaml"),
        frozen_group(ROOT / "configs" / "task28_rc001_registry_freeze_v1.yaml"),
        fixture["complete_events"],
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_forward_raw_trade_route_readout(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
