#!/usr/bin/env python3
"""Read-only MarketContextProjectionV1. Same composer as Workbench /market."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.market_context import (  # noqa: E402
    compose_market_context,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the derived market context projection without writing stores."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON is the authoritative output.",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Optional UTC instant, for example 2026-09-07T12:00:00Z.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    as_of = parse_utc(args.as_of) if args.as_of else datetime.now(UTC)
    projection = compose_market_context(ROOT, as_of=as_of)
    print(json.dumps(projection, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
