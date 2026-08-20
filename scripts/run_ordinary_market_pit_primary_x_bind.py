#!/usr/bin/env python3
"""Replay Git-retained Tokens V2 cells through the liquidity/mcap bind. No network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_market_pit_primary_x import (  # noqa: E402
    bind_git_retained_cells,
    load_bind_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_bind_config(root)
    result = bind_git_retained_cells(root, config)
    payload = {
        "bind_id": result["bind_id"],
        "hypothesis_version": result["hypothesis_version"],
        "product_terminal": result["product_terminal"],
        "next_safe_action": result["next_safe_action"],
        "cell_count": result["cell_count"],
        "primary_x_bound_count": result["primary_x_bound_count"],
        "primary_x_unknown_count": result["primary_x_unknown_count"],
        "mcap_key_count": result["mcap_key_count"],
        "availability_class": result["availability_class"],
        "pit_ready_count": result["pit_ready_count"],
        "provider_api_rpc_wss_calls": result["provider_api_rpc_wss_calls"],
        "receipt_path": result["receipt_path"],
        "receipt_sha256": result["receipt_sha256"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result["product_terminal"] == "GIT_RETAINED_CELLS_CANNOT_BIND_PRIMARY_X" else 2


if __name__ == "__main__":
    raise SystemExit(main())
