#!/usr/bin/env python3
"""Run the separately authorized TASK-21 R3 P1 foreground capture."""

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

from solana_alpha_lab.task21_event_triggered_followup_capture import (  # noqa: E402
    Task21FollowupExecutionGate,
    run_event_triggered_followup_capture,
)


ATOM_ID = "T21-A6S_R3_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1"


def _safe_code(exc: Exception) -> str:
    value = str(exc)
    return value if re.fullmatch(r"[A-Za-z0-9_.:/,-]{1,320}", value) else "REDACTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority")
    args = parser.parse_args()
    try:
        receipt = run_event_triggered_followup_capture(
            gate=(
                None
                if args.authority is None
                else Task21FollowupExecutionGate(args.authority)
            ),
            repo_root=ROOT,
            config_path=(
                ROOT / "configs/task21_r3_p1_event_triggered_capture_v1.yaml"
            ),
        )
    except Exception as exc:
        print("TASK21_R3_P1_CAPTURE: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_code(exc)}")
        return 1
    print("TASK21_R3_P1_CAPTURE: " + str(receipt["status"]))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] in {"PASS", "STOPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
