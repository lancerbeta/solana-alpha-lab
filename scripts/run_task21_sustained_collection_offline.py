"""Run the deterministic local TASK-21 sustained-control acceptance."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from solana_alpha_lab.task21_sustained_collection import (  # noqa: E402
    build_offline_acceptance,
    materialize_create_once,
)


def main() -> int:
    run = build_offline_acceptance(
        repo_root=REPO_ROOT,
        config_path=REPO_ROOT / "configs/task21_sustained_collection_v1.yaml",
        scenario_path=(
            REPO_ROOT
            / "tests/fixtures/task21/sustained_collection_offline_scenario_v1.json"
        ),
    )
    disposition = materialize_create_once(
        run,
        REPO_ROOT / "local/task21_collector/sustained_offline_acceptance",
    )
    print("TASK21_SUSTAINED_COLLECTION_LOCAL_CONTROL: PASS")
    print(
        json.dumps(
            {
                "disposition": disposition,
                "lifecycle": run.receipt["lifecycle"],
                "decision": run.receipt["decision"],
                "complete_members": run.receipt["coverage"]["complete_members"],
                "complete_panels": run.receipt["coverage"]["complete_panels"],
                "complete_quote_pairs": run.receipt["coverage"][
                    "complete_quote_pairs"
                ],
                "provider_api_rpc_wss_calls": 0,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
