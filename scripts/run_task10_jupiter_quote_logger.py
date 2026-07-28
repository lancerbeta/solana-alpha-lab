#!/usr/bin/env python3
"""Bounded launcher for offline replay and authorized TASK-10 quote pilots."""

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

from solana_alpha_lab.jupiter_quote_logger import (  # noqa: E402
    load_synthetic_fixture,
    project_fixture_case,
    safe_preflight_summary as safe_fixture_preflight_summary,
)
from solana_alpha_lab.jupiter_quote_transport import (  # noqa: E402
    BoundedQuoteTransport,
    DurableQuotePilotSink,
    EXTERNAL_AUTHORITY_PHRASE,
    ExternalExecutionGate,
    QuotePilotRunner,
    load_pilot_plan,
    safe_preflight_summary,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_logger_cases_v1.json"
)
PILOT_PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_pilot_plan_v2.json"
)
RAW_ROOT = ROOT / "data" / "raw"
SCHEMA_PATH = ROOT / "schemas" / "schema_v1.sql"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and replay synthetic TASK-10 quotes offline, or enter "
            "one exact-authority bounded public quote pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--case",
        metavar="CASE_ID",
        help="project one synthetic fixture case without persistence",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help=(
            "enter the exact user-authorized bounded keyless external atom"
        ),
    )
    return parser


def _safe_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
    args = _parser().parse_args(argv)
    document = load_synthetic_fixture(FIXTURE_PATH)
    plan = load_pilot_plan(PILOT_PLAN_PATH)
    if args.execute:
        phrase = input_fn("External authority phrase: ")
        if phrase != EXTERNAL_AUTHORITY_PHRASE:
            print("TASK10_EXTERNAL: BLOCKED_AUTHORITY_PHRASE")
            return 2
        try:
            transport = BoundedQuoteTransport(
                gate=ExternalExecutionGate(
                    authority_phrase=phrase,
                )
            )
            sink = DurableQuotePilotSink(
                raw_root=RAW_ROOT.resolve(),
                schema_path=SCHEMA_PATH.resolve(),
                plan=plan,
            )
            summary = QuotePilotRunner(
                plan=plan,
                transport=transport,
                sink=sink,
            ).run()
        except Exception as exc:
            print("TASK10_EXTERNAL: FAIL_REQUIRES_ACCEPTANCE")
            print(f"ERROR_TYPE: {type(exc).__name__}")
            print(f"ERROR_CODE: {_safe_error_code(exc)}")
            return 1
        print("TASK10_EXTERNAL: COMPLETE_REQUIRES_ACCEPTANCE")
        print(_safe_json(summary.safe_receipt()))
        return 0

    if args.case is None:
        print("TASK10_QUOTE_LOGGER_PREFLIGHT: PASS")
        print(
            _safe_json(
                {
                    "fixture": safe_fixture_preflight_summary(document),
                    "pilot": safe_preflight_summary(plan),
                }
            )
        )
        print("EXTERNAL_EXECUTION: BLOCKED_REQUIRES_RUNTIME_GATE")
        return 0

    case = next(
        (item for item in document["cases"] if item["case_id"] == args.case),
        None,
    )
    if case is None:
        print("TASK10_QUOTE_LOGGER_REPLAY: FAIL_UNKNOWN_CASE")
        return 1
    projection = project_fixture_case(case)
    print("TASK10_QUOTE_LOGGER_REPLAY: PASS")
    print(
        _safe_json(
            {
                "case_id": args.case,
                "error_class": projection.quote_attempt.error_class,
                "network_enabled": False,
                "output_quoted_atomic": (
                    projection.quote_attempt.output_quoted_atomic
                ),
                "raw_data_written": False,
                "route_count": projection.quote_attempt.route_count,
                "status": projection.quote_attempt.status,
                "stop_reason": projection.stop_reason,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
