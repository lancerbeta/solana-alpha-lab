#!/usr/bin/env python3
"""Run the single allowlisted TASK-12 offline supervisor falsifier."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pilot_supervisor import (  # noqa: E402
    PilotSupervisor,
    PilotSupervisorError,
    make_task11_offline_spec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run exactly one TASK-11 offline preflight under the frozen "
            "TASK-12 supervisor controls. No provider execution is exposed."
        )
    )
    parser.add_argument(
        "--window-start",
        help=(
            "UTC orchestration window as YYYY-MM-DDTHH:MM:SSZ; defaults to "
            "the current UTC minute"
        ),
    )
    parser.add_argument(
        "--attempt-sequence",
        type=int,
        default=1,
        help="positive local attempt number; default: 1",
    )
    return parser


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _default_window_start(now: datetime) -> str:
    return (
        now.astimezone(UTC)
        .replace(second=0, microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _safe_error_code(exc: BaseException) -> str:
    value = str(exc)
    if value and all(
        character.isalnum() or character in "_.:-"
        for character in value
    ):
        return value[:160]
    return "REDACTED"


def main(
    argv: Sequence[str] | None = None,
    *,
    now: datetime | None = None,
) -> int:
    args = _parser().parse_args(argv)
    current = now or datetime.now(UTC)
    window_start = args.window_start or _default_window_start(current)
    lock_root = (
        Path(tempfile.gettempdir())
        / "solana-alpha-lab-task12"
        / "locks"
    )
    stop = {"requested": False}

    def request_stop(_signum: int, _frame: object) -> None:
        stop["requested"] = True

    previous_handlers: dict[int, object] = {}
    for signal_name in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is None:
            continue
        previous_handlers[signal_value] = signal.getsignal(signal_value)
        signal.signal(signal_value, request_stop)

    try:
        spec = make_task11_offline_spec(
            ROOT,
            python_executable=Path(sys.executable),
        )
        result = PilotSupervisor(
            repo_root=ROOT,
            lock_root=lock_root,
        ).run(
            spec,
            utc_window_start=window_start,
            attempt_sequence=args.attempt_sequence,
            stop_requested=lambda: stop["requested"],
        )
    except (OSError, PilotSupervisorError, ValueError) as exc:
        print("TASK12_PILOT_SUPERVISOR: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        return 2
    finally:
        for signal_value, previous in previous_handlers.items():
            signal.signal(signal_value, previous)

    for event in result.events:
        print(_canonical_json(event))
    print(f"TASK12_PILOT_SUPERVISOR: {result.state}")
    print(_canonical_json(result.to_receipt()))
    return 0 if result.state == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
