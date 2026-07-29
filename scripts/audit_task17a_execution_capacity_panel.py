#!/usr/bin/env python3
"""Print or write the deterministic TASK-17A audit receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task17a_execution_capacity_audit import (  # noqa: E402
    audit_repaired_panel,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)
RAW_ROOT = (ROOT / "data" / "raw").resolve()
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_audit_v1.json"
)
REPAIR_CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "one_window_timing_repair_contract_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    receipt = audit_repaired_panel(
        raw_root=RAW_ROOT,
        contract_path=CONTRACT_PATH,
        repair_contract_path=REPAIR_CONTRACT_PATH,
    )
    payload = json.dumps(
        receipt,
        ensure_ascii=False,
        indent=2 if args.pretty or args.write else None,
        sort_keys=True,
        separators=None if args.pretty or args.write else (",", ":"),
    )
    if args.write:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
        print(f"TASK17A_AUDIT_WRITE: {AUDIT_PATH.relative_to(ROOT)}")
        return 0
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
