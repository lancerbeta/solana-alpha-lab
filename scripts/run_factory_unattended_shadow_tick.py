#!/usr/bin/env python3
"""Run one COMMISSIONING_ONLY unattended SHADOW tick + real progress heartbeat."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.unattended_shadow import (  # noqa: E402
    dump_receipt,
    run_unattended_shadow_tick,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/factory_unattended_shadow_vertical_slice_v1.yaml",
    )
    parser.add_argument("--receipt", default="")
    parser.add_argument("--store", default="")
    args = parser.parse_args(argv)
    store = Path(args.store) if args.store else None
    if store is not None and not store.is_absolute():
        store = ROOT / store
    result = run_unattended_shadow_tick(
        ROOT,
        config_relative=args.config,
        store_path=store,
    )
    if args.receipt:
        receipt_path = Path(args.receipt)
        if not receipt_path.is_absolute():
            receipt_path = ROOT / receipt_path
        dump_receipt(receipt_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
