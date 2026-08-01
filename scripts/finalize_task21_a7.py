#!/usr/bin/env python3
"""Create the deterministic local TASK-21 A7 acceptance outputs."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_dataset_freeze_acceptance import (  # noqa: E402
    materialize_a7_outputs,
    sha256_file,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-generated",
        action="store_true",
        help="Refresh only the four deterministic A7 generated JSON outputs.",
    )
    args = parser.parse_args()
    paths = materialize_a7_outputs(
        ROOT, replace_generated=args.refresh_generated
    )
    result = {
        "status": "PASS",
        "atom_id": "T21-A7_DATASET_FREEZE_ACCEPTANCE_CATALOG_FACTORY_FIT_V1",
        "outputs": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in paths
        ],
        "provider_api_rpc_wss_calls": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
