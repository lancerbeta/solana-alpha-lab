from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_real_nomination_source import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    Task21NominationSourceGate,
    replay_t1_from_retained_partition,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay retained TASK-21 T1 source bytes with Token-2022 support. "
            "This command performs no network request."
        )
    )
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    result = replay_t1_from_retained_partition(
        gate=Task21NominationSourceGate(args.authority),
        repo_root=ROOT,
        config_path=ROOT / "configs/task21_real_nomination_source_v1.yaml",
        recovery_receipt_path=(
            ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
        ),
        now=datetime.now(UTC),
    )
    print(
        json.dumps(
            result.safe_receipt(ROOT),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    if "--authority" not in sys.argv:
        raise SystemExit("exact --authority is required")
    if EXTERNAL_AUTHORITY_PHRASE not in sys.argv:
        raise SystemExit("exact authority phrase mismatch")
    raise SystemExit(main())
