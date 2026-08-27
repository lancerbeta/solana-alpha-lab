#!/usr/bin/env python3
"""Hash-verified offline importer for the early-market valuation-window panel."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import repository_git_snapshot
from solana_alpha_lab.factory.early_market_panel_importer import (
    EarlyMarketPanelImportError,
    GIT_RECEIPT_RELATIVE,
    GIT_RECEIPT_SHA256,
    import_early_market_panel,
)

_DRIVE_RE = re.compile(r"[A-Za-z]:\\")


def _emit(payload: dict, *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Capture directory that contains DISCOVERY_SEARCH_R0.body",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Throwaway TEMP root for PRE-MERGE proof; live RDP only after the post-merge bind phrase",
    )
    parser.add_argument(
        "--source-receipt",
        type=Path,
        required=True,
        help="Hash-bound receipt with raw_retention.manifests",
    )
    parser.add_argument("--expected-receipt-sha256")
    parser.add_argument("--generation-run-id", default="RUN-EARLY-MARKET-PANEL-TEMP-001")
    parser.add_argument(
        "--bind-stage",
        choices=("TEMP_PROOF", "POST_MERGE_OWNER_PHRASE"),
        default="TEMP_PROOF",
    )
    args = parser.parse_args()
    repo_root = args.root.resolve()
    git_before = repository_git_snapshot(repo_root)
    expected = args.expected_receipt_sha256
    if args.source_receipt.resolve() == (repo_root / GIT_RECEIPT_RELATIVE).resolve():
        expected = expected or GIT_RECEIPT_SHA256
    try:
        result = import_early_market_panel(
            source_root=args.source.resolve(),
            data_root=args.data_root.resolve(),
            source_receipt_path=args.source_receipt.resolve(),
            expected_receipt_sha256=expected,
            generation_run_id=args.generation_run_id,
        )
    except EarlyMarketPanelImportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        print("GIT_MUTATION_DETECTED", file=sys.stderr)
        return 2
    result["bind_stage"] = args.bind_stage
    result["generation_run_id"] = args.generation_run_id
    result["product_terminal"] = (
        "TEMP_PANEL_BOUND"
        if result.get("status") == "IMPORTED"
        else "TEMP_PANEL_ALREADY_BOUND"
    )
    result["next_safe_action"] = (
        "STOP_WAIT_OWNER_MERGE_THEN_BIND_PHRASE"
        if args.bind_stage == "TEMP_PROOF"
        else "STOP_DO_NOT_RUN_HYPOTHESIS_FORGE"
    )
    result["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    rendered = json.dumps(result, ensure_ascii=False)
    if _DRIVE_RE.search(rendered) or "SMIAL_DATA_ROOT" in rendered:
        print("PHYSICAL_PATH_LEAK", file=sys.stderr)
        return 2
    return _emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
