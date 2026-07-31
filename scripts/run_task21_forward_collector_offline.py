"""Run the one authorized synthetic TASK-21 collector dry run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from solana_alpha_lab.task21_forward_collector import (  # noqa: E402
    build_offline_run,
    materialize_create_once,
)


def main() -> int:
    run = build_offline_run(
        repo_root=REPO_ROOT,
        config_path=REPO_ROOT / "configs/task21_thin_collector_offline_v1.yaml",
        population_path=(
            REPO_ROOT
            / "tests/fixtures/task21/forward_collector_offline_population_v1.json"
        ),
        recovery_receipt_path=(
            REPO_ROOT
            / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
        ),
    )
    disposition = materialize_create_once(
        run,
        REPO_ROOT / "local/task21_collector/offline_dry_run",
    )
    summary = {
        "disposition": disposition,
        "run_id": run.receipt["run_id"],
        "active_members": run.receipt["active_members"],
        "complete_panels": run.receipt["complete_panels"],
        "complete_quote_pairs": run.receipt["complete_quote_pairs"],
        "offline_adapter_calls": run.receipt["offline_adapter_calls"],
        "provider_api_rpc_wss_calls": 0,
    }
    print("TASK21_THIN_COLLECTOR_OFFLINE_DRY_RUN: PASS")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
