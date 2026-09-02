#!/usr/bin/env python3
"""Stage-2 off-host copy: local BACKUP_<sha256>.zip -> Google Drive (copy-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.offhost_backup import (  # noqa: E402
    OffhostBackupError,
    copy_offhost_backup,
)
from solana_alpha_lab.factory.remote_ops import RemoteOpsError  # noqa: E402


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--mode",
        choices=("copy-newest", "daily", "weekly"),
        default="daily",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.mode == "copy-newest":
            receipt = copy_offhost_backup(root, deploy_git_sha=_git_sha(root))
        else:
            from solana_alpha_lab.factory.offhost_backup import run_offhost_checkpoint

            receipt = run_offhost_checkpoint(
                root, mode=args.mode, deploy_git_sha=_git_sha(root)
            )
        print(json.dumps(receipt, indent=2, sort_keys=True, default=str))
        return 0
    except (OffhostBackupError, RemoteOpsError) as exc:
        print(
            json.dumps({"error": str(exc), "terminal": "COPY_FAILED"}, indent=2, sort_keys=True)
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
