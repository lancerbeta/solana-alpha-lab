#!/usr/bin/env python3
"""Offline EARLY ICP freeze acceptance. No network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_icp_freeze_acceptance import (  # noqa: E402
    ATOM_ID,
    build_acceptance,
    reconcile,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=ATOM_ID)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--runtime-out",
        default=str(ROOT / "docs/evidence/early_icp_freeze/a1_runtime_receipt_v1.json"),
    )
    parser.add_argument(
        "--acceptance-out",
        default=str(ROOT / "docs/evidence/early_icp_freeze/a1_acceptance_v1.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    runtime = reconcile(root)
    _write_json(Path(args.runtime_out), runtime)
    _write_json(Path(args.acceptance_out), build_acceptance(runtime))
    print(
        json.dumps(
            {
                "atom_id": ATOM_ID,
                "terminal": runtime["decision"]["terminal"],
                "early_n": runtime["early_cohort"]["early_n"],
                "seasoned_branch_terminal": runtime["decision"]["seasoned_branch_terminal"],
                "provider_api_rpc_wss_calls": runtime["provider_api_rpc_wss_calls"],
                "runtime_out": str(Path(args.runtime_out).relative_to(root)).replace("\\", "/"),
                "acceptance_out": str(Path(args.acceptance_out).relative_to(root)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
