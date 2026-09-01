#!/usr/bin/env python
"""ObservationSchedule operational retention status / dry-run / apply."""

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

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    parse_utc,
)
from solana_alpha_lab.factory.observation_schedule_retention import (  # noqa: E402
    apply_retention,
    evaluate_retention,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    load_runtime_config,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("status", "dry-run", "apply"),
        help="status/dry-run are default-safe; apply requires --i-understand-apply",
    )
    parser.add_argument(
        "--runtime-config",
        default="configs/observation_schedule_runtime_v1.yaml",
    )
    parser.add_argument(
        "--schedule",
        default="",
        help="Optional schedule YAML providing retention.raw_retention_days",
    )
    parser.add_argument("--raw-retention-days", type=int, default=None)
    parser.add_argument("--now")
    parser.add_argument(
        "--i-understand-apply",
        action="store_true",
        help="Required exact flag for apply mode",
    )
    args = parser.parse_args(argv)

    runtime = load_runtime_config(ROOT, args.runtime_config)
    store = ObservationScheduleStore((ROOT / str(runtime["ops_store_relative"])).resolve())
    now = parse_utc(args.now) if args.now else datetime.now().astimezone()
    if args.raw_retention_days is not None:
        days = int(args.raw_retention_days)
    elif args.schedule:
        schedule = load_observation_schedule(ROOT, args.schedule)
        days = int(schedule["retention"]["raw_retention_days"])
    else:
        days = 31

    if args.command in {"status", "dry-run"}:
        result = apply_retention(
            store, now=now, raw_retention_days=days, dry_run=True
        )
        if args.command == "status":
            result = evaluate_retention(store, now=now, raw_retention_days=days)
    else:
        if not args.i_understand_apply:
            print(
                "APPLY_REQUIRES_FLAG: --i-understand-apply",
                file=sys.stderr,
            )
            store.close()
            return 2
        result = apply_retention(
            store, now=now, raw_retention_days=days, dry_run=False
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
