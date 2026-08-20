#!/usr/bin/env python3
"""Join bound liquidity/mcap X to already-captured forward quote Y. No network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_market_pit_offline_xy_association import (  # noqa: E402
    PRODUCT_TERMINAL,
    associate_offline_xy,
    load_association_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_association_config(root)
    result = associate_offline_xy(root, config)
    payload = {
        "association_id": result["association_id"],
        "hypothesis_version": result["hypothesis_version"],
        "product_terminal": result["product_terminal"],
        "family_decision": result["family_decision"],
        "next_safe_action": result["next_safe_action"],
        "complete_xy_count": result["complete_xy_count"],
        "cell_count": result["cell_count"],
        "y_missing_identities": result["y_missing_identities"],
        "pit_ready_count": result["pit_ready_count"],
        "provider_api_rpc_wss_calls": result["provider_api_rpc_wss_calls"],
        "strata": result["strata"],
        "combined": result["combined"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result["product_terminal"] == PRODUCT_TERMINAL else 2


if __name__ == "__main__":
    raise SystemExit(main())
