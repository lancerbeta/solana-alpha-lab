#!/usr/bin/env python3
"""Offline-first launcher for the bounded TASK-09 PumpSwap Touch probe."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pumpswap_touch_decoder import (  # noqa: E402
    load_pinned_pumpswap_plan,
)
from solana_alpha_lab.pumpswap_touch_probe import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    DurableTouchProbeSink,
    ExternalExecutionGate,
    TouchProbeRunner,
    default_probe_run_id,
    safe_preflight_summary,
    stdlib_http_exchange,
    websockets_wss_exchange,
)

IDL_FIXTURE = (
    ROOT / "tests" / "fixtures" / "task09" / "pumpswap_idl_subset_v1.json"
)
RAW_ROOT = ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the TASK-09 Touch probe offline by default, or execute "
            "one exact 30-second public standard-Solana capture."
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--authority-phrase",
        default="",
        help="exact non-secret external-action tripwire",
    )
    return parser


def _safe_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _safe_error_code(exc: BaseException) -> str:
    value = str(exc)
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        return value
    return type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = load_pinned_pumpswap_plan(IDL_FIXTURE)
        summary = safe_preflight_summary(plan)
    except Exception as exc:
        print("TASK09_TOUCH_PROBE_PREFLIGHT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1
    if not args.execute:
        print("TASK09_TOUCH_PROBE_PREFLIGHT: PASS")
        print(_safe_json(summary))
        print("EXTERNAL_EXECUTION: BLOCKED_UNLESS_EXPLICIT_EXECUTE")
        return 0

    sink: DurableTouchProbeSink | None = None
    try:
        gate = ExternalExecutionGate(args.authority_phrase)
        gate.require()
        now = datetime.now(UTC)
        sink = DurableTouchProbeSink(
            raw_root=RAW_ROOT.resolve(),
            run_id=default_probe_run_id(now),
        )
        runner = TouchProbeRunner(
            plan=plan,
            gate=gate,
            sink=sink,
            wss_exchange=websockets_wss_exchange,
            http_exchange=stdlib_http_exchange,
        )
        result = runner.run()
    except Exception as exc:
        print("TASK09_TOUCH_PROBE: STOPPED")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        if sink is not None:
            print(_safe_json(sink.safe_receipt()))
        return 2

    print("TASK09_TOUCH_PROBE: CAPTURE_COMPLETE_REQUIRES_ACCEPTANCE")
    print(_safe_json(result.safe_receipt()))
    print(_safe_json(sink.safe_receipt()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
