#!/usr/bin/env python3
"""Safe launcher for the exact bounded TASK-11 entity-input probe."""

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

from solana_alpha_lab.entity_input_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    AccessAttestation,
    BoundedEntityTransport,
    DurableEntityProbeSink,
    EntityPilotPlan,
    EntityProbeRunner,
    ExternalExecutionGate,
    HeliusCredential,
    default_run_id,
    load_entity_pilot_plan,
)
from solana_alpha_lab.entity_input_replay import (  # noqa: E402
    replay_entity_probe,
)

PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task11"
    / "entity_input_pilot_plan_v1.json"
)
RAW_ROOT = ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate TASK-11 A3 offline, or execute exactly one authorized "
            "three-call Helius standard-RPC holder probe."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help=(
            "prompt locally for the authority phrase, dashboard headroom "
            "and one hidden Helius credential, then run once"
        ),
    )
    mode.add_argument(
        "--replay-run",
        metavar="RUN_ID",
        help="verify and replay one retained run without network access",
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


def _load_plan() -> EntityPilotPlan:
    return load_entity_pilot_plan(PLAN_PATH)


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    raw_root: Path = RAW_ROOT,
) -> int:
    try:
        plan = _load_plan()
    except Exception as exc:
        print("TASK11_ENTITY_PROBE_PREFLIGHT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 1

    args = _parser().parse_args(argv)
    if args.replay_run is not None:
        try:
            result = replay_entity_probe(
                raw_root=raw_root.resolve(),
                plan=plan,
                run_id=args.replay_run,
            )
        except Exception as exc:
            print("TASK11_ENTITY_REPLAY: FAIL")
            print(f"ERROR_TYPE: {type(exc).__name__}")
            print(f"ERROR_CODE: {_safe_error_code(exc)}")
            return 3
        print("TASK11_ENTITY_REPLAY: PASS")
        print(_safe_json(result))
        return 0

    if not args.execute:
        print("TASK11_ENTITY_PROBE_PREFLIGHT: PASS")
        print(_safe_json(plan.safe_preflight()))
        print("EXTERNAL_EXECUTION: BLOCKED_UNLESS_EXPLICIT_EXECUTE")
        return 0

    sink: DurableEntityProbeSink | None = None
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
        sink = DurableEntityProbeSink(
            raw_root=raw_root.resolve(),
            run_id=run_id,
            plan=plan,
            credential=credential,
            now=now,
        )
        transport = BoundedEntityTransport(
            plan=plan,
            credential=credential,
            gate=gate,
        )
        result = EntityProbeRunner(
            plan=plan,
            transport=transport,
            sink=sink,
            access=access,
        ).run()
    except Exception as exc:
        print("TASK11_ENTITY_PROBE: STOPPED")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        if sink is not None:
            print("DURABLE_SINK_RECEIPT:")
            print(_safe_json(sink.safe_partial_receipt()))
        return 2
    finally:
        credential_value = ""

    print("TASK11_ENTITY_PROBE: COMPLETE_REQUIRES_ACCEPTANCE")
    print(_safe_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
