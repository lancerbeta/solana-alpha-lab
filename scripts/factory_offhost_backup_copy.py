#!/usr/bin/env python3
"""Stage-2 off-host copy: local BACKUP_<sha256>.zip -> Google Drive (copy-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
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
        choices=("copy-newest", "daily", "weekly", "plan-prune", "verify-remote-restore", "apply-remote-prune"),
        default="daily",
    )
    parser.add_argument("--objects-json", type=Path)
    parser.add_argument("--retain-checkpoint", action="append", default=[])
    parser.add_argument("--pin", action="append", default=[])
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--isolated-root", type=Path)
    parser.add_argument("--plan-json", type=Path)
    parser.add_argument("--restore-proof-json", type=Path, action="append", default=[])
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--authorize-remote-delete", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.mode in {"plan-prune", "verify-remote-restore", "apply-remote-prune"}:
            from solana_alpha_lab.factory.offhost_backup import (
                apply_remote_backup_prune,
                load_offhost_config, plan_checkpoint_prune, verify_remote_checkpoint_restore,
            )

            config = load_offhost_config(root)
            if config is None:
                raise OffhostBackupError("OFFHOST_NOT_CONFIGURED")
            if args.mode == "plan-prune":
                if args.objects_json is None:
                    raise OffhostBackupError("PRUNE_EXACT_OBJECT_INVENTORY_REQUIRED")
                objects = json.loads(args.objects_json.read_text(encoding="utf-8"))
                if not isinstance(objects, list) or any(not isinstance(name, str) for name in objects):
                    raise OffhostBackupError("PRUNE_OBJECT_INVENTORY_INVALID")
                receipt = plan_checkpoint_prune(root, config=config, objects=objects,
                    retained_checkpoint_filenames=args.retain_checkpoint, scientific_pins=args.pin,
                    restore_proof_artifacts=args.restore_proof_json)
            elif args.mode == "verify-remote-restore":
                if args.checkpoint is None or args.isolated_root is None:
                    raise OffhostBackupError("REMOTE_RESTORE_EXACT_PATHS_REQUIRED")
                receipt = verify_remote_checkpoint_restore(checkpoint_path=args.checkpoint,
                    isolated_root=args.isolated_root, config=config)
            else:
                if args.plan_json is None:
                    raise OffhostBackupError("PRUNE_EXACT_PLAN_REQUIRED")
                receipt = apply_remote_backup_prune(root, config=config,
                    plan=json.loads(args.plan_json.read_text(encoding="utf-8")),
                    remote_delete_authorized=args.authorize_remote_delete,
                    approved_plan_sha256=args.approved_plan_sha256,
                    restore_proof_artifacts=args.restore_proof_json)
        elif args.mode == "copy-newest":
            receipt = copy_offhost_backup(root, deploy_git_sha=_git_sha(root))
        else:
            from solana_alpha_lab.factory.offhost_backup import run_scheduled_offhost_checkpoint

            receipt = run_scheduled_offhost_checkpoint(
                root, mode=args.mode, deploy_git_sha=_git_sha(root)
            )
            if receipt.get("terminal") not in {"DEFERRED", "COPY_FAILED"} and not receipt.get("scheduled_coalesced"):
                # The checkpoint owner has released its backup-plane lock. The
                # native policy is default-off; optional failure cannot discard
                # the successful independent backup.
                try:
                    from solana_alpha_lab.factory.offhost_backup import run_checkpoint_maintenance

                    receipt["maintenance"] = run_checkpoint_maintenance(
                        root, receipt, now=datetime.now(UTC)
                    )
                except Exception:
                    receipt["maintenance"] = {
                        "status": "FAILED", "reason": "OPTIONAL_MAINTENANCE_FAILED"
                    }
        print(json.dumps(receipt, indent=2, sort_keys=True, default=str))
        return 2 if receipt.get("terminal") in {"DEFERRED", "COPY_FAILED"} else 0
    except (OffhostBackupError, RemoteOpsError) as exc:
        print(
            json.dumps({"error": str(exc), "terminal": "COPY_FAILED"}, indent=2, sort_keys=True)
        )
        return 2
    except (OSError, ValueError, TypeError):
        print(json.dumps({"error": "OFFHOST_INPUT_OR_IO_FAILED", "terminal": "COPY_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
