#!/usr/bin/env python3
"""Offline Phase A adjudication for HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.holder_concentration_top_quartile_veto import (  # noqa: E402
    PHASE_A_FAIL_TERMINAL,
    PHASE_A_SURVIVE_TERMINAL,
    score_phase_a_from_paths,
)

DEFAULT_RECEIPT = (
    ROOT / "docs/evidence/early_holder_concentration_actionability_rule_oos/a1_phase_a_receipt_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = score_phase_a_from_paths(args.root.resolve())
    args.write.parent.mkdir(parents=True, exist_ok=True)
    public = dict(result)
    public.pop("labeled_rows", None)
    public["labeled_row_counts"] = {
        window_id: len(rows) for window_id, rows in result.get("labeled_rows", {}).items()
    }
    args.write.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    survived = bool(result["adjudication"]["survived"])
    sys.stdout.write(
        json.dumps(
            {
                "terminal": result["terminal"],
                "phase_a_survived": survived,
                "receipt": str(args.write.as_posix()),
            },
            indent=2,
        )
        + "\n"
    )
    if result["terminal"] not in {PHASE_A_FAIL_TERMINAL, PHASE_A_SURVIVE_TERMINAL}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
