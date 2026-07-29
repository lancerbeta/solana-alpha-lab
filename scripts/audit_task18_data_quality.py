#!/usr/bin/env python3
"""Print or exclusively write the deterministic TASK-18 quality audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task18_data_quality import (  # noqa: E402
    audit_narrow_data_quality,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task18"
    / "narrow_data_quality_contract_v1.json"
)
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task18"
    / "narrow_data_quality_audit_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    receipt = audit_narrow_data_quality(
        repository_root=ROOT,
        contract_path=CONTRACT_PATH,
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
        print(f"TASK18_AUDIT_WRITE: {AUDIT_PATH.relative_to(ROOT)}")
        return 0
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
