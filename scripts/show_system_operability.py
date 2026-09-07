#!/usr/bin/env python3
"""Read-only SystemOperabilityProjectionV2. Same composer as Workbench /system."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.system_operability import (  # noqa: E402
    compose_system_operability,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the derived system operability projection without writing stores."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="JSON is the authoritative output.",
    )
    return parser.parse_args()


def main() -> int:
    _arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    projection = compose_system_operability(root=ROOT, http_self="NOT_APPLICABLE")
    print(json.dumps(projection, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
