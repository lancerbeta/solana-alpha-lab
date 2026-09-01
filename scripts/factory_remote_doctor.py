#!/usr/bin/env python3
"""Agent-readable Factory remote-ops doctor. No secrets in output."""

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

from solana_alpha_lab.factory.offhost_backup import offhost_recovery_readout  # noqa: E402
from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    RemoteOpsError,
    doctor_packet,
    emit_health_alert,
    load_config,
    package_backup,
    write_heartbeat,
)

WORKBENCH_UNIT = "factory-v1-workbench.service"


def _git_sha(root: Path) -> str | None:
    pin = root / ".factory_deploy_sha"
    if pin.is_file():
        value = pin.read_text(encoding="utf-8").strip()
        if len(value) == 40:
            return value
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def observe_workbench_alive() -> bool:
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", "--quiet", WORKBENCH_UNIT],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return completed.returncode == 0
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--heartbeat", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument(
        "--offhost-status",
        action="store_true",
        help="Read-only off-host durability recovery readout (no Drive writes)",
    )
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--process-alive", action="store_true")
    parser.add_argument("--process-down", action="store_true")
    args = parser.parse_args()
    if args.process_alive and args.process_down:
        print(
            json.dumps(
                {"error": "PROCESS_ALIVE_FLAGS_CONFLICT", "verdict": "UNHEALTHY"},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
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
        if args.offhost_status:
            readout = offhost_recovery_readout(root, deploy_git_sha=_git_sha(root))
            dumped = json.dumps(readout)
            for forbidden in ("access_token", "refresh_token", "client_secret", "BEGIN PRIVATE"):
                if forbidden in dumped:
                    raise RemoteOpsError("SECRET_LEAK_IN_OFFHOST_READOUT")
            print(json.dumps(readout, indent=2, sort_keys=True))
            return 0
        if args.process_alive:
            process_alive = True
        elif args.process_down:
            process_alive = False
        else:
            process_alive = observe_workbench_alive()
        while True:
            packet = doctor_packet(
                root,
                process_alive=process_alive,
                config=config,
                git_sha=_git_sha(root),
            )
            try:
                alert = emit_health_alert(root=root, packet=packet, config=config)
            except RemoteOpsError as exc:
                alert = {"delivered": False, "error": str(exc)}
            packet["alert_emit"] = alert
            print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
            if args.loop is False:
                return 0
            time.sleep(60)
            process_alive = observe_workbench_alive()
    except RemoteOpsError as exc:
        print(json.dumps({"error": str(exc), "verdict": "UNHEALTHY"}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
