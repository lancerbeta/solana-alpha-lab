#!/usr/bin/env python3
"""Write the offline RC001 H13 park-from-priority acceptance evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc001_h13_park_from_priority import (  # noqa: E402
    ATOM_ID,
    H13ParkError,
    bind_h13_park_from_priority,
    format_owner_readout,
)

AS_OF = "2026-08-18"
ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc001_h13_park_from_priority/"
    "a1_h13_park_from_priority_acceptance_v1.json"
)
READOUT_PATH = ROOT / (
    "docs/reports/rc001_h13_park_from_priority/a1_owner_readout_v1.md"
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    try:
        result = bind_h13_park_from_priority(ROOT)
    except H13ParkError as exc:
        json.dump(
            {
                "terminal": "H13_PARK_PREREQUISITES_DRIFT",
                "error_code": str(exc),
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 1
    acceptance = {
        "schema": "smial.rc001.h13-park-from-priority.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "EVIDENCE-RC001-H13-PARK-FROM-PRIORITY-001",
        "task_id": ATOM_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "non_claims": [
            "NO_RC001_FREEZE_MUTATION",
            "NO_H13_OR_H02_TRIAL",
            "NO_ENTITY_ROUTE_REDESIGN_OR_CAPTURE",
            "NO_CONTINUOUS_PIT_OR_EXECUTION_CAPTURE",
            "NO_H07_H01_UNPARK",
            "NO_HYPOTHESIS_NEGATIVE_OR_POSITIVE_INFERENCE",
            "NO_ALPHA_NETRETURN_OR_CASHFLOW",
            "NO_CANONICAL_DONE",
        ],
        **result,
    }
    _write_json(ACCEPTANCE_PATH, acceptance)
    READOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    READOUT_PATH.write_text(
        format_owner_readout(result),
        encoding="utf-8",
        newline="\n",
    )
    json.dump({"terminal": result["terminal"]}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
