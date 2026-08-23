#!/usr/bin/env python
"""Run FACTORY_V1 operational-readiness closeout evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.operational_readiness_closeout import (  # noqa: E402
    CloseoutError,
    apply_stage_reconciliation,
    evaluate_closeout,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--gate-receipt", type=Path, required=True)
    parser.add_argument(
        "--apply-stage-reconciliation",
        action="store_true",
        help="Rewrite current_product_stage (+ READY fields only if all predicates PASS).",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        gate = evaluate_closeout(root)
        if args.apply_stage_reconciliation:
            apply_stage_reconciliation(root, gate)
    except CloseoutError as exc:
        print(
            "CLOSEOUT_ERROR:"
            f"{exc}; foundation_freeze stays INACTIVE; do not claim READY; "
            "check runner pin / closeout config / evidence paths",
            file=sys.stderr,
        )
        return 2
    out = args.gate_receipt
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    gap_ids = [item.split(":", 1)[0] for item in gate.get("named_gaps") or []]
    owner_readout = (
        "docs/reports/factory_v1_operational_readiness_closeout/a1_owner_readout_v1.md"
    )
    print(
        json.dumps(
            {
                "terminal": gate["terminal"],
                "foundation_freeze": gate["foundation_freeze"],
                "factory_v1_operational_ready": gate["factory_v1_operational_ready"],
                "named_gap_count": len(gap_ids),
                "named_gaps": gap_ids,
                "next_safe_action": gate.get("next_safe_action"),
                "non_claims": gate.get("non_claims"),
                "gate_receipt": out.relative_to(root).as_posix(),
                "owner_readout": owner_readout,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
