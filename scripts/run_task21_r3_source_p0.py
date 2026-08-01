#!/usr/bin/env python3
"""Run the separately authorized TASK-21 R3 source and P0 capture."""

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

from solana_alpha_lab.task21_r3_event_triggered_capture import (
    ATOM_ID,
    Task21R3Error,
    Task21R3ExecutionGate,
    run_r3_source_p0_capture,
)


CONFIG = ROOT / "configs/task21_r3_event_triggered_source_p0_v1.yaml"


def _safe_code(exc: Exception) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(exc))[:200]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority")
    args = parser.parse_args()
    try:
        gate = (
            None
            if args.authority is None
            else Task21R3ExecutionGate(args.authority)
        )
        receipt = run_r3_source_p0_capture(
            gate=gate,
            repo_root=ROOT,
            config_path=CONFIG,
        )
    except (Task21R3Error, OSError, ValueError, KeyError) as exc:
        print("TASK21_R3_SOURCE_P0: FAIL")
        print("ERROR_CODE: " + _safe_code(exc))
        return 1
    print("TASK21_R3_SOURCE_P0: " + str(receipt["status"]))
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] in {"PASS", "STOPPED_NO_ADMISSION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
