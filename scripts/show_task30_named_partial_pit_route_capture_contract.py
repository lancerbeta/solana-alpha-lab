"""Render the TASK-30 A9 offline owner packet without any external transport."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_named_partial_pit_route_capture_contract import (
    evaluate_capture_contract,
    render_capture_contract_readout,
)


def load_yaml(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"YAML_OBJECT_REQUIRED:{path}")
    return document


def frozen_group(path: Path) -> dict:
    for group in load_yaml(path)["hypothesis_groups"]:
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION":
            if not isinstance(group, dict):
                break
            return group
    raise ValueError("FROZEN_GROUP_MISSING")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs/task30_named_partial_pit_route_capture_contract_v1.yaml",
    )
    parser.add_argument(
        "--frozen-definition",
        type=Path,
        default=ROOT / "configs/task28_rc001_registry_freeze_v1.yaml",
    )
    args = parser.parse_args()

    result = evaluate_capture_contract(load_yaml(args.config), frozen_group(args.frozen_definition))
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_capture_contract_readout(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
