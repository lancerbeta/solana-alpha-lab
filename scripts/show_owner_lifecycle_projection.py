#!/usr/bin/env python3
"""Read-only inspection of LifecycleProjectionV1. Not the owner UX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.lifecycle_projection import (  # noqa: E402
    build_lifecycle_projection,
    render_lifecycle_projection_table,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the derived owner lifecycle projection without writing stores."
    )
    parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="json",
        help="json is the authoritative output; table is compact inspection only.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    projection = build_lifecycle_projection(ROOT)
    if args.format == "table":
        sys.stdout.write(render_lifecycle_projection_table(projection))
        return 0
    sys.stdout.write(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
