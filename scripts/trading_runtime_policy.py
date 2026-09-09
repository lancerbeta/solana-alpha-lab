"""Agent-facing SHOW/CHECK/APPLY/HISTORY/ROLLBACK for TradingRuntimePolicyV1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import paper_plane_store_path  # noqa: E402
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, PaperPlaneStore  # noqa: E402
from solana_alpha_lab.factory.trading_runtime_policy import (  # noqa: E402
    TradingRuntimePolicyError,
    apply_policy,
    check_policy,
    rollback_policy,
    show_policy,
)


def _load_json_arg(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    path = Path(raw)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mode", required=True, choices=("PAPER", "SHADOW"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("SHOW")
    sub.add_parser("HISTORY")
    check = sub.add_parser("CHECK")
    check.add_argument("--candidate-json", required=True)
    apply_cmd = sub.add_parser("APPLY")
    apply_cmd.add_argument("--candidate-json", required=True)
    apply_cmd.add_argument("--expected-current-sha256", required=True)
    apply_cmd.add_argument("--idempotency-key", required=True)
    apply_cmd.add_argument("--owner-authorization-phrase", required=True)
    apply_cmd.add_argument("--reason", required=True)
    rollback = sub.add_parser("ROLLBACK")
    rollback.add_argument("--expected-current-sha256", required=True)
    rollback.add_argument("--idempotency-key", required=True)
    rollback.add_argument("--owner-authorization-phrase", required=True)
    args = parser.parse_args(argv)

    store_path = paper_plane_store_path(args.root)
    if args.command in {"SHOW", "HISTORY", "CHECK"}:
        if not store_path.is_file():
            print(
                json.dumps(
                    {"status": "NOT_PRESENT", "mode": args.mode, "operation": args.command},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        store = PaperPlaneStore(store_path, readonly=True)
        try:
            if args.command in {"SHOW", "HISTORY"}:
                result = show_policy(store, args.mode)
            else:
                result = check_policy(
                    store, mode=args.mode, candidate_raw=_load_json_arg(args.candidate_json)
                )
        finally:
            store.close()
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
        return 0

    store_path.parent.mkdir(parents=True, exist_ok=True)
    store = PaperPlaneStore(store_path)
    try:
        if args.command == "APPLY":
            result = apply_policy(
                args.root,
                store,
                mode=args.mode,
                candidate_raw=_load_json_arg(args.candidate_json),
                expected_current_sha256=args.expected_current_sha256,
                idempotency_key=args.idempotency_key,
                owner_authorization_phrase=args.owner_authorization_phrase,
                reason=args.reason,
            )
        else:
            result = rollback_policy(
                args.root,
                store,
                mode=args.mode,
                expected_current_sha256=args.expected_current_sha256,
                idempotency_key=args.idempotency_key,
                owner_authorization_phrase=args.owner_authorization_phrase,
            )
    except (TradingRuntimePolicyError, PaperPlaneError) as exc:
        code = getattr(exc, "code", str(exc))
        print(json.dumps({"status": "DENIED", "error": code}, indent=2, sort_keys=True))
        return 2
    finally:
        store.close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
