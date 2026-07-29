#!/usr/bin/env python3
"""Run the exact-authority bounded TASK-17A external quote panel."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task17a_execution_capacity_panel import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    Task17AExecutionGate,
    load_frozen_contract,
    run_panel,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)
RAW_ROOT = (ROOT / "data" / "raw").resolve()


def _safe_error_code(exc: Exception) -> str:
    value = str(exc)
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        return value
    return "REDACTED"


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        contract = load_frozen_contract(CONTRACT_PATH)
        print("TASK17A_EXTERNAL_PREFLIGHT: PASS")
        print(
            json.dumps(
                {
                    "accounts": 0,
                    "api_keys": 0,
                    "cash_spend_usd_cents": 0,
                    "network_enabled": False,
                    "provider_calls_current_max": contract["caps"][
                        "provider_calls_current_max"
                    ],
                    "raw_live_writes": 0,
                    "wallet_signer_transaction_actions": 0,
                    "windows": contract["trigger_windows"]["window_ids"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        print("EXTERNAL_EXECUTION: BLOCKED_REQUIRES_RUNTIME_GATE")
        return 0
    phrase = input_fn("External authority phrase: ")
    try:
        summary = run_panel(
            gate=Task17AExecutionGate(authority_phrase=phrase),
            raw_root=RAW_ROOT,
            contract_path=CONTRACT_PATH,
        )
    except Exception as exc:
        print("TASK17A_EXTERNAL: FAIL_REQUIRES_ACCEPTANCE")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1
    print("TASK17A_EXTERNAL: COMPLETE_REQUIRES_ACCEPTANCE")
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
