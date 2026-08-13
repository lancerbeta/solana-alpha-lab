#!/usr/bin/env python3
"""Render the offline TASK-30 terminal route decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_terminal_route_decision import (  # noqa: E402
    evaluate_terminal_decision,
    render_terminal_readout,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    config = yaml.safe_load((ROOT / "configs/task30_terminal_route_decision_v1.yaml").read_text(encoding="utf-8"))
    result = evaluate_terminal_decision(config)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_terminal_readout(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
