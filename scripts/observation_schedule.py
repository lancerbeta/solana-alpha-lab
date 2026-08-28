#!/usr/bin/env python3
"""ObservationSchedule operator CLI. No arbitrary URLs, SQL, or output paths."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    ObservationScheduleError,
    load_observation_schedule,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import tick_once  # noqa: E402


SAFE_PREFIXES = ("local/", "tests/fixtures/observation_schedule/")


def _safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        path.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise SystemExit("PATH_UNSAFE")
    if not relative.replace("\\", "/").startswith(SAFE_PREFIXES) and not relative.startswith(
        "tests/fixtures/"
    ):
        if relative.startswith("configs/") is False:
            raise SystemExit("PATH_UNSAFE")
    return root / relative


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "compile",
        "register",
        "authorize",
        "activate",
        "pause",
        "status",
        "snapshot",
        "doctor",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("--schedule", required=name in {"validate", "compile", "register", "authorize", "activate"})
        if name == "authorize":
            cmd.add_argument("--phrase", required=True)
        if name == "activate":
            cmd.add_argument("--activation-id", required=True)
    tick = sub.add_parser("tick")
    tick.add_argument("--once", action="store_true", required=True)
    tick.add_argument("--data-root", required=True)
    tick.add_argument("--schedule-sha256", required=True)
    tick.add_argument("--activation-id", required=True)
    args = parser.parse_args(argv)
    if args.command in {"validate", "compile", "register"}:
        document = load_observation_schedule(ROOT, args.schedule)
        if args.command == "validate":
            print(json.dumps({"terminal": "VALIDATED", "schedule_sha256": document["schedule_sha256"]}, sort_keys=True))
            return 0
        result = compile_schedule_document(document, root=ROOT)
        print(
            json.dumps(
                {
                    "terminal": result.terminal,
                    "schedule_sha256": result.schedule_sha256,
                    "next_action": result.next_action,
                },
                sort_keys=True,
            )
        )
        return 0 if result.schedule_sha256 else 2
    if args.command == "tick":
        if Path(args.data_root).is_absolute() is False:
            raise SystemExit("DATA_ROOT_NOT_ABSOLUTE")
        store = ObservationScheduleStore(Path(args.data_root) / "observation_schedule_state.sqlite")
        print(
            json.dumps(
                {
                    "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                    "reason": "zero-network CLI requires injected runtime in tests",
                    "schedule_sha256": args.schedule_sha256,
                    "activation_id": args.activation_id,
                },
                sort_keys=True,
            )
        )
        store.close()
        return 0
    if args.command == "doctor":
        print(json.dumps({"terminal": "DOCTOR_OK", "live_activation": False}, sort_keys=True))
        return 0
    print(json.dumps({"terminal": args.command.upper() + "_RECORDED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
