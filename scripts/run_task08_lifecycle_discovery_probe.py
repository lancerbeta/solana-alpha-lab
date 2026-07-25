#!/usr/bin/env python3
"""Safe launcher for the bounded TASK-08 lifecycle discovery probe."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery import (  # noqa: E402
    load_frozen_discovery_plan,
)
from solana_alpha_lab.lifecycle_discovery_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    DurableProbeSink,
    ExternalExecutionGate,
    HttpExchange,
    ProbeAccessAttestation,
    ProbeCredentials,
    ProbeTransportRunner,
    WssExchange,
    default_probe_run_id,
    safe_preflight_summary,
    stdlib_http_exchange,
    websockets_wss_exchange,
)
from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    load_pinned_pump_event_plan,
)

DISCOVERY_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "lifecycle_discovery_contract_v1.json"
)
EVENT_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "pump_event_idl_subset_v1.json"
)
RAW_ROOT = ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the TASK-08 boundary offline by default, or execute "
            "one explicitly authorized bounded T08-A5 probe."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "prompt locally for the authority phrase, provider dashboard "
            "headroom and two hidden API keys, then run once"
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


def _safe_error_code(exc: BaseException) -> str:
    value = str(exc)
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        return value
    return "REDACTED"


def _non_negative_integer(name: str, value: str) -> int:
    if re.fullmatch(r"[0-9]{1,12}", value) is None:
        raise ValueError(f"{name}_must_be_non_negative_integer")
    return int(value)


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
    wss_exchange: WssExchange = websockets_wss_exchange,
    http_exchange: HttpExchange = stdlib_http_exchange,
    clock: Callable[[], float] = time.monotonic,
    pace: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] | None = None,
    raw_root: Path = RAW_ROOT,
) -> int:
    now_fn = now or (lambda: datetime.now(UTC))
    try:
        plan = load_frozen_discovery_plan(DISCOVERY_FIXTURE)
        event_plan = load_pinned_pump_event_plan(EVENT_FIXTURE)
        summary = safe_preflight_summary(plan, event_plan)
    except Exception as exc:
        print("TASK08_PROBE_PREFLIGHT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1

    if not _parser().parse_args(argv).execute:
        print("TASK08_PROBE_PREFLIGHT: PASS")
        print(_safe_json(summary))
        print("EXTERNAL_EXECUTION: BLOCKED_UNLESS_EXPLICIT_EXECUTE")
        return 0

    try:
        phrase = input_fn("External authority phrase: ")
        gate = ExternalExecutionGate(authority_phrase=phrase)
        gate.require()
        helius_remaining = _non_negative_integer(
            "helius_credits_remaining",
            input_fn("Helius dashboard credits remaining: "),
        )
        tracker_remaining = _non_negative_integer(
            "solana_tracker_requests_remaining",
            input_fn("Solana Tracker dashboard requests remaining: "),
        )
        access = ProbeAccessAttestation(
            dashboard_readback_completed=True,
            helius_credits_remaining=helius_remaining,
            solana_tracker_requests_remaining=tracker_remaining,
        )
        access.require(plan)
    except Exception as exc:
        print("TASK08_PROBE: BLOCKED_PREFLIGHT")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 2

    helius_key = ""
    tracker_key = ""
    sink: DurableProbeSink | None = None
    runner: ProbeTransportRunner | None = None
    try:
        helius_key = secret_input_fn("Helius API key (hidden): ")
        tracker_key = secret_input_fn("Solana Tracker API key (hidden): ")
        credentials = ProbeCredentials(
            helius_api_key=helius_key,
            solana_tracker_api_key=tracker_key,
        )
        run_id = default_probe_run_id(now_fn())
        sink = DurableProbeSink(
            raw_root=raw_root.resolve(),
            run_id=run_id,
            credentials=credentials,
        )
        runner = ProbeTransportRunner(
            plan=plan,
            event_plan=event_plan,
            credentials=credentials,
            access=access,
            gate=gate,
            wss_exchange=wss_exchange,
            http_exchange=http_exchange,
            evidence_sink=sink,
            clock=clock,
            pace=pace,
            now=now_fn,
        )
        result = runner.run()
    except Exception as exc:
        print("TASK08_PROBE: STOPPED")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        if runner is not None:
            usage_receipt = runner.safe_failure_receipt()
            if usage_receipt is not None:
                print("SAFE_USAGE_RECEIPT:")
                print(_safe_json(usage_receipt))
        if sink is not None:
            print("DURABLE_SINK_RECEIPT:")
            print(_safe_json(sink.safe_receipt()))
        return 3
    finally:
        helius_key = ""
        tracker_key = ""

    print("TASK08_PROBE: CAPTURE_COMPLETE_REQUIRES_WORK_ACCEPTANCE")
    print(_safe_json(result.safe_receipt()))
    print(_safe_json(sink.safe_receipt()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
