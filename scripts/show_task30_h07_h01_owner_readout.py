#!/usr/bin/env python3
"""Render the tracked, offline TASK-30 H07/H01 owner decision."""

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

from solana_alpha_lab.task30_h07_h01_owner_visible_vertical_slice import (  # noqa: E402
    evaluate_owner_visible_slice,
    render_owner_readout,
    validate_owner_visible_slice,
)


def load_yaml(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(path.as_posix())
    return document


def h07_h01_group(document: dict) -> dict:
    groups = document.get("hypothesis_groups")
    if not isinstance(groups, list):
        raise ValueError("hypothesis_groups")
    for group in groups:
        if isinstance(group, dict) and group.get("group_id") == (
            "RC001-H07-H01-LIQUIDITY-RETENTION"
        ):
            return group
    raise ValueError("RC001-H07-H01-LIQUIDITY-RETENTION")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)

    config = load_yaml(ROOT / "configs/task30_h07_h01_owner_visible_vertical_slice_v1.yaml")
    frozen_config = load_yaml(ROOT / "configs/task28_rc001_registry_freeze_v1.yaml")
    frozen_group = h07_h01_group(frozen_config)
    validate_owner_visible_slice(config, frozen_group)
    result = evaluate_owner_visible_slice(config, frozen_group)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_owner_readout(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
