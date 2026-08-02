#!/usr/bin/env python3
"""Build sanitized TASK-24 A5 graph outputs from one exact raw capture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task24_entity_linkage_projection import (  # noqa: E402
    build_task24_linkage_projection,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs/evidence/task24/a5_projection_v1",
    )
    args = parser.parse_args()
    result = build_task24_linkage_projection(
        repo_root=ROOT,
        raw_root=ROOT / "data/raw",
        run_id=args.run_id,
        receipt_sha256=args.receipt_sha256,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
