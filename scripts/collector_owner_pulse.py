#!/usr/bin/env python
"""Daily Collector Owner Pulse CLI (dry-run default; emit is explicit)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_owner_pulse import (  # noqa: E402
    DAILY_PULSE_ON_CALENDAR,
    run_daily_owner_pulse,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    git_sha,
    load_runtime_config,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.remote_ops import load_config_v1_1  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("dry-run", "emit"),
        default="dry-run",
        help="dry-run: zero network / zero credential VALUE reads (default)",
    )
    parser.add_argument(
        "--runtime-config",
        default="configs/observation_schedule_runtime_v1.yaml",
    )
    parser.add_argument("--now")
    parser.add_argument(
        "--record-storage-history",
        action="store_true",
        help="Append measured storage observation (emit mode recommended)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    runtime = load_runtime_config(ROOT, args.runtime_config)
    ops_rel = str(runtime["ops_store_relative"])
    store = ObservationScheduleStore((ROOT / ops_rel).resolve())
    now = parse_utc(args.now) if args.now else datetime.now().astimezone()
    remote = load_config_v1_1(ROOT)

    result = run_daily_owner_pulse(
        root=ROOT,
        store=store,
        mode=args.mode,
        now=now,
        deploy_git_sha=git_sha(ROOT),
        observation_rdp=ROOT / str(runtime["data_root"]),
        remote_config=remote,
        record_storage_history=bool(args.record_storage_history and args.mode == "emit"),
    )
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "packet"}, indent=2))
        print(json.dumps({"packet": result["packet"]}, indent=2))
    else:
        sys.stdout.write(result["text"])
        if args.mode == "emit":
            delivery = result.get("delivery") or {}
            print(
                f"# delivery delivered={delivery.get('delivered')} "
                f"deduped={delivery.get('deduped')} "
                f"on_calendar={DAILY_PULSE_ON_CALENDAR}",
                file=sys.stderr,
            )
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
