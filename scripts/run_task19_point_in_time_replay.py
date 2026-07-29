"""Run the deterministic offline TASK-19 point-in-time replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task19_point_in_time_replay import (
    audit_point_in_time_replay,
    build_summary,
    canonical_json_bytes,
)

DEFAULT_CONTRACT = (
    ROOT
    / "tests"
    / "fixtures"
    / "task19"
    / "point_in_time_replay_contract_v1.json"
)
DEFAULT_RECEIPT = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "point_in_time_replay_v1.json"
)
DEFAULT_SUMMARY = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "point_in_time_replay_summary_v1.md"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    receipt = audit_point_in_time_replay(
        repository_root=args.repository_root.resolve(),
        contract_path=args.contract.resolve(),
    )
    receipt_bytes = canonical_json_bytes(receipt)
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if args.write:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_bytes(receipt_bytes)
        args.summary.write_text(
            build_summary(receipt, receipt_sha256),
            encoding="utf-8",
            newline="\n",
        )
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["verdict"] == "REPLAY_SAFE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
