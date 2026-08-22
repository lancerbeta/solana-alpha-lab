#!/usr/bin/env python3
"""Dry-run Factory remote-ops installer. Apply is owner-packet gated. No secrets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    RemoteOpsError,
    load_config,
    verify_security_templates,
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
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        config = load_config(root)
        security = verify_security_templates(root, config)
    except RemoteOpsError as exc:
        print(json.dumps({"error": str(exc), "apply": False}, indent=2, sort_keys=True))
        return 2
    packet = {
        "mode": "DRY_RUN",
        "apply": False,
        "git_sha": _git_sha(root),
        "sku": config["target"]["sku"],
        "rejected_sku": config["target"]["rejected_sku"],
        "purchase": config["target"]["purchase"],
        "os": config["target"]["os"],
        "workbench_bind": config["workbench"]["bind"],
        "workbench_access": config["workbench"]["access"],
        "security": security,
        "next_safe_action": "OWNER_INFRASTRUCTURE_PACKET",
        "implementation": config["implementation"],
    }
    if args.apply:
        if os.environ.get("FACTORY_REMOTE_APPLY") != "OWNER_PACKET_CONFIRMED":
            packet["error"] = "APPLY_REQUIRES_OWNER_PACKET"
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 2
        if os.name == "nt":
            packet["error"] = "APPLY_NOT_ON_WINDOWS"
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 2
        packet["error"] = "APPLY_LIVE_HOST_NOT_IN_THIS_WRITE_SET"
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 2
    print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
