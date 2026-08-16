#!/usr/bin/env python3
"""Offline RC002 H11 park-from-priority. No provider calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_park_from_priority import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    bind_h11_park_from_priority,
    format_owner_readout,
)

ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/rc002_h11_park_from_priority/"
    "a1_h11_park_from_priority_acceptance_v1.json"
)
READOUT_PATH = ROOT / (
    "docs/reports/rc002_h11_park_from_priority/a1_owner_readout_v1.md"
)


def main() -> int:
    result = bind_h11_park_from_priority(ROOT)
    acceptance = {
        "schema": "smial.rc002.h11-park-from-priority.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "EVIDENCE-RC002-H11-PARK-FROM-PRIORITY-001",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-17",
        "owner_decision": "PARK_H11_FROM_PRIORITY",
        "owner_phrase": AUTHORITY_PHRASE,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "provider_requests": 0,
        "credential_reads": 0,
        "cash_spend_usd_cents": 0,
        "historical_receipts_rewritten": False,
        "pinned_decoder_mutated": False,
        "trial_ledger_rewritten": False,
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "non_claims": [
            "NO_LIVE_PIT_CLAIM",
            "NO_EXECUTION_CLAIM",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_RC001_MUTATION",
            "NO_HOLDOUT_CONSUMPTION",
            "NO_H11_EFFECT_SCREEN",
            "NO_H11_SCREEN_NEGATIVE_OR_POSITIVE",
            "NO_COHORT_READY_FROM_N1",
            "NO_PAID_CAPTURE",
            "NO_H13_OR_H02_TRIAL",
            "NO_CANONICAL_DONE",
            "NO_TRIAL_LEDGER_REWRITE",
            "NO_TASK36_37_40_RECEIPT_REWRITE",
        ],
        **result,
    }
    ACCEPTANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_PATH.write_text(
        json.dumps(acceptance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    READOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    READOUT_PATH.write_text(
        format_owner_readout(result), encoding="utf-8", newline="\n"
    )
    json.dump({"terminal": result["terminal"]}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
