#!/usr/bin/env python3
"""Offline BUY-T0 quote microstructure association. No network."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.buy_decision_time_quote_microstructure_association import (  # noqa: E402
    TERMINALS,
    associate_from_capsule,
    load_association_config,
    load_capsule_jsonl,
    run_association,
    write_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--from-capsule",
        action="store_true",
        help="Recompute the mutex terminal from the Git capsule without local A4.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_association_config(root)
    if args.from_capsule:
        rows = load_capsule_jsonl(root / config["outputs"]["capsule_jsonl"])
        result = associate_from_capsule(rows, config)
        bundle = {"result": result, "rows": rows, "receipt": {"terminal": result["terminal"]}, "association_input": {}}
        if args.write:
            raise SystemExit("FROM_CAPSULE_WRITE_FORBIDDEN")
    else:
        bundle = run_association(root, config)
        if args.write:
            write_outputs(root, bundle, config)
    payload = {
        "atom_id": bundle["result"]["atom_id"],
        "terminal": bundle["result"]["terminal"],
        "next_action": bundle["result"]["next_action"],
        "automatic_next_started": False,
        "production_selector_authorized": False,
        "family_terminals": bundle["result"]["family_terminals"],
        "n_rows_primary_analysis": bundle["result"]["n_rows_primary_analysis"],
        "n_tokens": bundle["result"]["n_tokens"],
        "n_informative_windows_better": bundle["result"]["n_informative_windows_better"],
        "n_informative_windows_worse": bundle["result"]["n_informative_windows_worse"],
        "provider_api_rpc_wss_calls": 0,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if bundle["result"]["terminal"] in TERMINALS else 2


if __name__ == "__main__":
    raise SystemExit(main())
