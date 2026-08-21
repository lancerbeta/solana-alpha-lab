#!/usr/bin/env python3
"""Reconcile named Git H900 receipts into a population-fit decision. No network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.in_scope_population_fit_reconciliation import (  # noqa: E402
    ATOM_ID,
    build_acceptance,
    reconcile,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=ATOM_ID)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--runtime-out",
        default=str(
            ROOT / "docs/evidence/in_scope_population_fit_reconciliation/a1_runtime_receipt_v1.json"
        ),
    )
    parser.add_argument(
        "--acceptance-out",
        default=str(
            ROOT / "docs/evidence/in_scope_population_fit_reconciliation/a1_acceptance_v1.json"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    runtime = reconcile(root)
    # Keep Git receipt compact: matrix + decision, not every token row.
    stored = dict(runtime)
    stored["row_inventory_n"] = stored.pop("row_count")
    stored.pop("rows", None)
    acceptance = build_acceptance(runtime)
    runtime_path = Path(args.runtime_out)
    acceptance_path = Path(args.acceptance_out)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_bytes(
        (json.dumps(stored, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    acceptance_path.write_bytes(
        (json.dumps(acceptance, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    decision = runtime["decision"]
    print(
        json.dumps(
            {
                "atom_id": ATOM_ID,
                "terminal": decision["terminal"],
                "campaigns": len(runtime["campaign_matrix"]),
                "provider_api_rpc_wss_calls": 0,
                "runtime_out": str(runtime_path.relative_to(root)).replace("\\", "/"),
                "acceptance_out": str(acceptance_path.relative_to(root)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
