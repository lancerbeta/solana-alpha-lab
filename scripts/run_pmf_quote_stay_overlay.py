#!/usr/bin/env python3
"""Offline PMF quote stay-overlay binder. No provider calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pmf_quote_stay_overlay import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    bind_pmf_quote_stay_overlay,
    format_owner_readout,
)

ACCEPTANCE_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json"
)
RUNTIME_PATH = ROOT / (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_runtime_receipt_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/pmf_quote_slice/a1_stay_overlay_owner_readout_v1.md"


def main() -> int:
    result = bind_pmf_quote_stay_overlay(ROOT)
    runtime = {
        "schema": "smial.pmf-quote-stay-overlay.runtime-receipt",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-PMF-QUOTE-STAY-OVERLAY-001",
        "atom_id": ATOM_ID,
        **result,
    }
    acceptance = {
        "schema": "smial.pmf-quote-stay-overlay.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "EVIDENCE-PMF-QUOTE-STAY-OVERLAY-001",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-20",
        "owner_decision": "ACCEPT_TOUCH_FILLABLE_FEES_NOT_EVIDENCED_QUOTE_ONLY_KEEP_SCREENING_EXHAUSTED",
        "owner_phrase": AUTHORITY_PHRASE,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "provider_requests": 0,
        "credential_reads": 0,
        "cash_spend_usd_cents": 0,
        "historical_receipts_rewritten": False,
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "non_claims": [
            "NO_LIVE_PIT_CLAIM",
            "NO_EXECUTION_CLAIM",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_TOUCH_OR_FILLABLE",
            "NO_FEE_ZERO_FROM_ABSENCE",
            "NO_FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY",
            "NO_QUOTE_ONLY_KEEP_6_PLUS_6",
            "NO_TOUCH_FACT_STARTED",
            "NO_FEE_FACT_STARTED",
            "NO_ATOM_2",
            "NO_FACTORY_V1_OPERATIONAL_READY",
            "NO_RC001_MUTATION",
            "NO_H11_UNPARK",
            "NO_H13_OR_H02_TRIAL",
            "NO_PROVIDER_CALL",
            "NO_CREDENTIAL_READ",
            "NO_CANONICAL_DONE",
            "NO_EXECUTE_PHRASE_AUTHORIZED",
        ],
        **result,
    }
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PATH.write_text(
        json.dumps(runtime, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    ACCEPTANCE_PATH.write_text(
        json.dumps(acceptance, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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
