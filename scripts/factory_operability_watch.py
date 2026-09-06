#!/usr/bin/env python
"""Local operability watch. Independent of the collector tick."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    git_sha,
    load_runtime_config,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.operability_watch import evaluate_operability  # noqa: E402
from solana_alpha_lab.factory.remote_ops import load_config_v1_1  # noqa: E402


def _unit_status() -> dict[str, str]:
    units = (
        "factory-observation-schedule.timer",
        "factory-remote-backup.timer",
        "factory-collector-owner-pulse.timer",
        "factory-hot90-closed-day-archive.timer",
    )
    status: dict[str, str] = {}
    for unit in units:
        completed = subprocess.run(
            ["systemctl", "is-active", unit],
            check=False,
            capture_output=True,
            text=True,
        )
        status[unit] = (completed.stdout or "").strip() or "unknown"
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "emit"), default="dry-run")
    parser.add_argument(
        "--runtime-config",
        default="configs/observation_schedule_runtime_v1.yaml",
    )
    parser.add_argument("--now")
    parser.add_argument("--skip-systemd", action="store_true")
    args = parser.parse_args(argv)
    runtime = load_runtime_config(ROOT, args.runtime_config)
    store = ObservationScheduleStore((ROOT / str(runtime["ops_store_relative"])).resolve())
    now = parse_utc(args.now) if args.now else datetime.now().astimezone()
    result = evaluate_operability(
        root=ROOT,
        store=store,
        now=now,
        deploy_git_sha=git_sha(ROOT, runtime.get("producer_git_sha")),
        observation_rdp=ROOT / str(runtime["data_root"]),
        remote_config=load_config_v1_1(ROOT),
        unit_status=None if args.skip_systemd else _unit_status(),
        emit=args.mode == "emit",
        persist=args.mode == "emit",
        environ=os.environ,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
