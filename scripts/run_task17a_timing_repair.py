#!/usr/bin/env python3
"""Preflight or execute the exact TASK-17A one-window timing repair."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task17a_timing_repair import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    Task17ATimingRepairGate,
    repair_preflight,
    run_repair,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "one_window_timing_repair_contract_v1.json"
)
RAW_ROOT = (ROOT / "data" / "raw").resolve()


def _safe_error_code(exc: Exception) -> str:
    value = str(exc)
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", value):
        return value
    return "REDACTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("TASK17A_TIMING_REPAIR_PREFLIGHT: PASS")
        print(
            json.dumps(
                repair_preflight(
                    raw_root=RAW_ROOT,
                    contract_path=CONTRACT_PATH,
                ),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        print("EXTERNAL_EXECUTION: BLOCKED_REQUIRES_RUNTIME_GATE")
        return 0
    phrase = input("External authority phrase: ")
    try:
        result = run_repair(
            gate=Task17ATimingRepairGate(authority_phrase=phrase),
            raw_root=RAW_ROOT,
            contract_path=CONTRACT_PATH,
        )
    except Exception as exc:
        print("TASK17A_TIMING_REPAIR: FAIL_REQUIRES_ACCEPTANCE")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1
    print("TASK17A_TIMING_REPAIR: COMPLETE_REQUIRES_ACCEPTANCE")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
