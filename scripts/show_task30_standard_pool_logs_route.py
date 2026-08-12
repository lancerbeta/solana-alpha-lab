#!/usr/bin/env python3
"""Print the deterministic owner readout for TASK-30 A15."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_standard_pool_logs_route import (  # noqa: E402
    render_standard_pool_logs_route,
)


def main() -> int:
    config_path = ROOT / "configs" / "task30_standard_pool_logs_route_v1.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise SystemExit("A15 config must be a mapping")
    sys.stdout.write(render_standard_pool_logs_route(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
