#!/usr/bin/env python3
"""Safe launcher for the bounded TASK-24 A5R1 exact-wire recapture."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task24_entity_linkage_capture import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    AccessAttestation,
    BoundedHistoryTransport,
    DurableHistorySink,
    ExternalExecutionGate,
    HeliusCredential,
    HistoryCapturePlan,
    HistoryCaptureRunner,
    default_run_id,
    load_frozen_population,
)

RAW_ROOT = ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate TASK-24 A5R1 offline, or execute a separately authorized "
            "21-call Helius exact-wire recapture with hidden local credential input."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="prompt locally for exact authority, credit headroom and hidden key",
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
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value) else "REDACTED"


def _non_negative_integer(name: str, value: str) -> int:
    if re.fullmatch(r"[0-9]{1,12}", value) is None:
        raise ValueError(f"{name}_must_be_non_negative_integer")
    return int(value)


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    raw_root: Path = RAW_ROOT,
) -> int:
    args = _parser().parse_args(argv)
    plan = HistoryCapturePlan()
    try:
        population = load_frozen_population(ROOT)
    except Exception as exc:
        print("TASK24_A5R1_PREFLIGHT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1

    if not args.execute:
        print("TASK24_A5R1_PREFLIGHT: PASS")
        print(
            _safe_json(
                {
                    "plan": plan.safe_preflight(),
                    "population": population.safe_receipt(),
                }
            )
        )
        print("EXTERNAL_EXECUTION: BLOCKED_UNLESS_EXPLICIT_EXECUTE")
        return 0

    sink: DurableHistorySink | None = None
    credential_value = ""
    try:
        phrase = input_fn(
            f"External authority phrase ({EXTERNAL_AUTHORITY_PHRASE}): "
        )
        gate = ExternalExecutionGate(authority_phrase=phrase)
        gate.require()
        credits_remaining = _non_negative_integer(
            "helius_credits_remaining",
            input_fn("Helius dashboard credits remaining: "),
        )
        access = AccessAttestation(
            dashboard_readback_completed=True,
            helius_credits_remaining=credits_remaining,
        )
        access.require(plan)
        credential_value = secret_input_fn("Helius API key (hidden): ")
        credential = HeliusCredential(credential_value)
        run_id = default_run_id(now())
        sink = DurableHistorySink(
            raw_root=raw_root.resolve(),
            run_id=run_id,
            plan=plan,
            population=population,
            credential=credential,
            now=now,
        )
        result = HistoryCaptureRunner(
            plan=plan,
            population=population,
            transport=BoundedHistoryTransport(
                plan=plan,
                credential=credential,
                gate=gate,
            ),
            sink=sink,
            access=access,
        ).run()
    except Exception as exc:
        print("TASK24_A5R1_CAPTURE: STOPPED")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        if sink is not None:
            print("DURABLE_SINK_RECEIPT:")
            print(_safe_json(sink.safe_partial_receipt()))
        return 2
    finally:
        credential_value = ""

    print("TASK24_A5R1_CAPTURE: COMPLETE_REQUIRES_PROJECTION_AND_ACCEPTANCE")
    print(_safe_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
