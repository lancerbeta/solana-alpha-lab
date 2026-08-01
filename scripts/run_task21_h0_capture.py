"""Run the separately authorized TASK-21 T1 admission and H0 capture."""

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

from solana_alpha_lab.task21_multi_horizon_capture import (  # noqa: E402
    Task21H0ExecutionGate,
    run_h0_capture,
)


def _safe_code(exc: Exception) -> str:
    value = str(exc)
    return value if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,200}", value) else "REDACTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    try:
        receipt = run_h0_capture(
            gate=Task21H0ExecutionGate(args.authority),
            repo_root=ROOT,
            config_path=(
                ROOT
                / "configs/task21_bounded_admission_multi_horizon_capture_v1.yaml"
            ),
            recovery_receipt_path=(
                ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
            ),
        )
    except Exception as exc:
        print("TASK21_H0_CAPTURE: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_code(exc)}")
        return 1
    print("TASK21_H0_CAPTURE: " + str(receipt["status"]))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] in {"PASS", "STOPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
