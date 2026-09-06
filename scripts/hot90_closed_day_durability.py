#!/usr/bin/env python
"""Closed-day HOT90 durability loop. Never deletes scientific source."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hot90_closed_day_loop import (  # noqa: E402
    run_closed_day_durability,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--now")
    parser.add_argument("--max-days", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    now = parse_utc(args.now) if args.now else datetime.now().astimezone()
    result = run_closed_day_durability(
        args.root.resolve(),
        now=now,
        max_days=args.max_days,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
