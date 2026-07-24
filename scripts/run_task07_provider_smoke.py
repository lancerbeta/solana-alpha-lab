#!/usr/bin/env python3
"""Offline-by-default launcher for the bounded TASK-07 provider smoke."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.provider_smoke import load_frozen_smoke_plan  # noqa: E402
from solana_alpha_lab.provider_smoke_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    RAPTOR_TAIL_AUTHORITY_PHRASE,
    BoundedProviderTransport,
    DurableAttemptSink,
    ExternalExecutionGate,
    ProviderCredentials,
    RaptorTailExecutionGate,
    RaptorTailRunner,
    SmokeTransportRunner,
    default_run_id,
    prepare_raptor_tail_recovery,
    safe_preflight_summary,
)

SPEC_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "pre_git"
    / "task01"
    / "provider_smoke_spec_v1.yaml"
)
RAW_ROOT = ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate TASK-07 offline by default; live execution requires "
            "a separately approved atom and interactive credentials."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help="enter the separately authorized live execution path",
    )
    mode.add_argument(
        "--prepare-raptor-tail",
        metavar="PARENT_RUN_ID",
        help=(
            "offline-verify an immutable 33-attempt parent prefix and "
            "prepare only R04/R05"
        ),
    )
    mode.add_argument(
        "--execute-raptor-tail",
        metavar="PARENT_RUN_ID",
        help=(
            "enter the separately authorized keyless R04/R05 child path"
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
    secret_input_fn: Callable[[str], str] = getpass.getpass,
) -> int:
    args = _parser().parse_args(argv)
    plan = load_frozen_smoke_plan(SPEC_PATH)
    if args.prepare_raptor_tail is not None:
        try:
            recovery = prepare_raptor_tail_recovery(
                plan,
                raw_root=RAW_ROOT.resolve(),
                parent_run_id=args.prepare_raptor_tail,
            )
        except Exception as exc:
            print("TASK07_RAPTOR_TAIL_PREFLIGHT: FAIL")
            print(f"ERROR_TYPE: {type(exc).__name__}")
            print(f"ERROR_CODE: {_safe_error_code(exc)}")
            return 1
        print("TASK07_RAPTOR_TAIL_PREFLIGHT: PASS")
        print(
            _safe_json(
                {
                    "network_authorized": False,
                    "output_created": False,
                    "parent_run_id": recovery.parent_run_id,
                    "pending_attempts": list(recovery.pending_attempts),
                    "reclassified_attempts": [
                        list(item)
                        for item in recovery.reclassified_attempts
                    ],
                    "verified_attempts": len(
                        recovery.verified_attempts
                    ),
                    "verified_files": recovery.verified_file_count,
                }
            )
        )
        print("LIVE_EXECUTION: BLOCKED_REQUIRES_SEPARATE_ATOM")
        return 0

    if args.execute_raptor_tail is not None:
        try:
            recovery = prepare_raptor_tail_recovery(
                plan,
                raw_root=RAW_ROOT.resolve(),
                parent_run_id=args.execute_raptor_tail,
            )
        except Exception as exc:
            print("TASK07_RAPTOR_TAIL_PREFLIGHT: FAIL")
            print(f"ERROR_TYPE: {type(exc).__name__}")
            print(f"ERROR_CODE: {_safe_error_code(exc)}")
            return 1
        phrase = input_fn("Raptor tail authority phrase: ")
        if phrase != RAPTOR_TAIL_AUTHORITY_PHRASE:
            print("TASK07_RAPTOR_TAIL: BLOCKED_AUTHORITY_PHRASE")
            return 2
        try:
            child_run_id = default_run_id()
            RAW_ROOT.mkdir(parents=True, exist_ok=True)
            sink = DurableAttemptSink(
                raw_root=RAW_ROOT.resolve(),
                run_id=child_run_id,
            )
            transport = BoundedProviderTransport(
                gate=RaptorTailExecutionGate(
                    authority_phrase=phrase,
                )
            )
            runner = RaptorTailRunner(
                plan=plan,
                recovery=recovery,
                transport=transport,
                event_sink=sink,
            )
            summary = runner.run(child_run_id=child_run_id)
        except Exception as exc:
            print("TASK07_RAPTOR_TAIL: FAIL")
            print(f"ERROR_TYPE: {type(exc).__name__}")
            print(f"ERROR_CODE: {_safe_error_code(exc)}")
            return 1
        print("TASK07_RAPTOR_TAIL: COMPLETE_REQUIRES_ACCEPTANCE")
        print(
            _safe_json(
                {
                    "cash_spend_usd": summary.cash_spend_usd,
                    "child_run_id": summary.child_run_id,
                    "completed_attempts": summary.completed_attempts,
                    "output_logical_root": summary.output_logical_root,
                    "parent_run_id": summary.parent_run_id,
                    "planned_attempts": summary.planned_attempts,
                    "response_bytes": summary.response_bytes,
                    "terminal_counts": summary.terminal_counts,
                }
            )
        )
        return 0

    if not args.execute:
        print("TASK07_TRANSPORT_PREFLIGHT: PASS")
        print(_safe_json(safe_preflight_summary(plan)))
        print("LIVE_EXECUTION: BLOCKED_REQUIRES_SEPARATE_ATOM")
        return 0

    phrase = input_fn("External authority phrase: ")
    if phrase != EXTERNAL_AUTHORITY_PHRASE:
        print("TASK07_LIVE_SMOKE: BLOCKED_AUTHORITY_PHRASE")
        return 2

    helius_value = secret_input_fn("Helius research API key: ")
    tracker_value = secret_input_fn("Solana Tracker Data API key: ")
    try:
        h = helius_value
        t = tracker_value
        credentials = ProviderCredentials(
            helius_api_key=h,
            solana_tracker_api_key=t,
        )
        run_id = default_run_id()
        RAW_ROOT.mkdir(parents=True, exist_ok=True)
        sink = DurableAttemptSink(raw_root=RAW_ROOT.resolve(), run_id=run_id)
        transport = BoundedProviderTransport(
            gate=ExternalExecutionGate(
                authority_phrase=phrase,
            )
        )
        runner = SmokeTransportRunner(
            plan=plan,
            credentials=credentials,
            transport=transport,
            event_sink=sink,
        )
        summary = runner.run(run_id=run_id)
    except Exception as exc:
        print("TASK07_LIVE_SMOKE: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1
    finally:
        h = ""
        t = ""
        helius_value = ""
        tracker_value = ""

    print("TASK07_LIVE_SMOKE: COMPLETE_REQUIRES_ACCEPTANCE")
    print(
        _safe_json(
            {
                "cash_spend_usd": summary.cash_spend_usd,
                "completed_attempts": summary.completed_attempts,
                "helius_credits": summary.helius_credits,
                "output_logical_root": summary.output_logical_root,
                "planned_attempts": summary.planned_attempts,
                "response_bytes": summary.response_bytes,
                "run_id": summary.run_id,
                "terminal_counts": summary.terminal_counts,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
