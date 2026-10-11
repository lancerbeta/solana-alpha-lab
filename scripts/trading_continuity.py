"""Ordinary synthetic offline PAPER/SHADOW continuity entry; no external execution."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PureWindowsPath
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner, OFFLINE_MARKER
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError
from solana_alpha_lab.factory.research_store import ResearchStoreError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "load", "activate", "episode", "attempt", "result", "exit", "operator", "readback"))
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--strategy", help="Repository-relative, exact materialized StrategyVersion")
    parser.add_argument("--mode", choices=("PAPER", "SHADOW", "LIVE"), default="PAPER")
    parser.add_argument("--epoch")
    parser.add_argument("--as-of")
    parser.add_argument("--episode-id")
    parser.add_argument("--source", default="source/observation_schedule_state.sqlite")
    parser.add_argument("--position-id")
    parser.add_argument("--side", choices=("ENTRY", "EXIT"))
    parser.add_argument("--attempt-key")
    parser.add_argument("--input", help="Offline-root-relative result or operator command JSON")
    args = parser.parse_args(argv)
    try:
        if args.mode == "LIVE":
            raise PaperPlaneError("LIVE_ROUTE_FORBIDDEN")
        if args.command == "init":
            local = (args.repository_root / "local").resolve(strict=True)
            target = args.data_root.resolve(strict=False)
            if target == local or not target.is_relative_to(local) or target != args.data_root.absolute():
                raise PaperPlaneError("OFFLINE_ROOT_UNSAFE")
            for item in (args.data_root, *args.data_root.parents):
                if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                    raise PaperPlaneError("OFFLINE_ROOT_LINK_FORBIDDEN")
                if item == local:
                    break
            if target.exists() and any(target.iterdir()):
                raise PaperPlaneError("OFFLINE_INIT_REQUIRES_EMPTY_ROOT")
            target.mkdir(parents=True, exist_ok=True)
            (target / "offline_runtime.json").write_text(json.dumps(OFFLINE_MARKER) + "\n", encoding="utf-8")
            result = {"status": "INITIALIZED", "evidence_class": "SYNTHETIC_OFFLINE", "activation_created": False}
        else:
            if not args.strategy:
                raise PaperPlaneError("EXACT_STRATEGY_PATH_REQUIRED")
            runner = TradingContinuityRunner(args.repository_root, data_root=args.data_root, strategy_relative=args.strategy)
            if args.command == "load":
                result = {"status": "LOADED_VERIFIED", "strategy_sha256": runner.strategy["spec_sha256"], "activation_created": False}
            elif args.command == "activate":
                result = runner.activate(epoch_id=args.epoch, mode=args.mode, at=args.as_of)
            elif args.command == "episode":
                result = runner.episode(source_relative=args.source, episode_id=args.episode_id, epoch_id=args.epoch, mode=args.mode, as_of=args.as_of)
            elif args.command == "attempt":
                result = runner.attempt(position_id=args.position_id, side=args.side, attempt_key=args.attempt_key, as_of=args.as_of)
            elif args.command == "exit":
                result = runner.exit(position_id=args.position_id, source_relative=args.source, as_of=args.as_of)
            elif args.command == "readback":
                result = runner.readback()
            else:
                relative = Path(args.input or "")
                if not args.input or relative.anchor or PureWindowsPath(args.input).anchor or ".." in relative.parts:
                    raise PaperPlaneError("OFFLINE_INPUT_PATH_UNSAFE")
                path = runner.data_root / relative
                runner._safe_path(path, strict=True)
                payload = json.loads(path.read_text(encoding="utf-8"))
                result = runner.result(payload) if args.command == "result" else runner.command(payload)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, sqlite3.DatabaseError, TypeError, KeyError, ResearchStoreError) as exc:
        # Typed domain errors are safe codes; native exceptions never expose paths.
        code, next_action = "OFFLINE_INPUT_SHAPE_INVALID", "CHECK_REQUIRED_INPUT_FIELDS"
        if isinstance(exc, FileNotFoundError):
            code, next_action = "OFFLINE_SOURCE_NOT_PRESENT", "RESTORE_EXACT_SOURCE_DO_NOT_BOOTSTRAP_READBACK"
        elif isinstance(exc, PermissionError):
            code, next_action = "OFFLINE_SOURCE_ACCESS_DENIED", "RESOLVE_LOCAL_ACCESS_WITHOUT_RECREATING_STATE"
        elif isinstance(exc, json.JSONDecodeError):
            code, next_action = "OFFLINE_INPUT_JSON_INVALID", "CORRECT_JSON_WITHOUT_REUSING_CONFLICTING_CONTENT_ID"
        elif isinstance(exc, sqlite3.DatabaseError):
            corrupt = getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}
            code = "OFFLINE_DATABASE_CORRUPT" if corrupt else "OFFLINE_DATABASE_READ_OR_LOCK_UNAVAILABLE"
            next_action = "RESTORE_EXACT_NATIVE_BACKUP" if corrupt else "CHECK_OWNED_HANDLES_AND_SOURCE_ACCESS"
        elif isinstance(exc, ResearchStoreError):
            code, next_action = "OFFLINE_BOUND_RESEARCH_UNAVAILABLE", "RESTORE_EXACT_BOUND_RESEARCH_INPUT"
        elif isinstance(exc, ValueError) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,119}", str(exc)):
            code, next_action = str(exc), "RESOLVE_REASON_AT_FROZEN_SOURCE_OWNER"
            next_action = {"SOURCE_NOT_PRESENT": "RESTORE_EXACT_SOURCE_DO_NOT_BOOTSTRAP_READBACK",
                "AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR": "REQUEST_CLOSE_POSITION_THEN_RECONCILE",
                "ATTEMPT_RECONCILIATION_REQUIRED": "RECONCILE_SAME_ATTEMPT_BEFORE_RETRY"}.get(code, next_action)
        print(json.dumps({"status": "BLOCKED", "reason_code": code, "next_safe_action": next_action,
                          "evidence_class": "SYNTHETIC_OFFLINE"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
