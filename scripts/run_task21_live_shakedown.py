"""Run the separately authorized TASK-21 bounded live shakedown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from solana_alpha_lab.task21_live_shakedown import (  # noqa: E402
    Task21LiveExecutionGate,
    run_live_shakedown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    arguments = parser.parse_args()
    receipt = run_live_shakedown(
        gate=Task21LiveExecutionGate(arguments.authority),
        repo_root=REPO_ROOT,
        config_path=REPO_ROOT / "configs/task21_live_shakedown_v1.yaml",
        recovery_receipt_path=(
            REPO_ROOT
            / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
        ),
    )
    print("TASK21_BOUNDED_LIVE_SHAKEDOWN: " + str(receipt["status"]))
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] in {"COMPLETE", "STOPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
