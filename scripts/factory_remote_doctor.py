#!/usr/bin/env python3
"""Agent-readable Factory remote-ops doctor. No secrets in output. No VPS."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    RemoteOpsError,
    doctor_packet,
    load_config,
    package_backup,
    write_heartbeat,
)


def _git_sha(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", default=True)
    parser.add_argument("--heartbeat", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--process-alive", action="store_true", default=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        config = load_config(root)
        if args.heartbeat:
            path = write_heartbeat(root, config=config)
            print(json.dumps({"heartbeat": path.as_posix()}, indent=2, sort_keys=True))
            return 0
        if args.backup:
            packed = package_backup(root, config=config)
            print(json.dumps(packed, indent=2, sort_keys=True))
            return 0
        while True:
            packet = doctor_packet(
                root,
                process_alive=args.process_alive,
                config=config,
                git_sha=_git_sha(root),
            )
            print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
            if args.loop is False:
                return 0
            time.sleep(60)
    except RemoteOpsError as exc:
        print(json.dumps({"error": str(exc), "verdict": "UNHEALTHY"}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
