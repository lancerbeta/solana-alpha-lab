#!/usr/bin/env python
"""HOT90 activation show/set. SET is an operational mutation; this CLI grants no authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hot90_activation import (  # noqa: E402
    RUNTIME_RELATIVE,
    Hot90ActivationError,
    load_hot90_activation,
    write_hot90_runtime_state,
)


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def _parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise Hot90ActivationError("HOT90_ACTIVATION_INVALID")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    setter = sub.add_parser("set")
    setter.add_argument("--stage", required=True)
    setter.add_argument("--drive-writes", required=True, choices=("true", "false"))
    setter.add_argument("--compaction", required=True, choices=("true", "false"))
    setter.add_argument("--eviction", required=True, choices=("true", "false"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "show":
            loaded = load_hot90_activation(root)
            loaded["runtime_rel"] = RUNTIME_RELATIVE
            return _emit(loaded, 0)
        written = write_hot90_runtime_state(
            root,
            {
                "activation_stage": args.stage,
                "drive_writes_enabled": _parse_bool(args.drive_writes),
                "production_compaction_enabled": _parse_bool(args.compaction),
                "production_eviction_enabled": _parse_bool(args.eviction),
            },
        )
        written["runtime_rel"] = RUNTIME_RELATIVE
        return _emit(written, 0)
    except Hot90ActivationError as exc:
        return _emit({"error": str(exc), "runtime_rel": RUNTIME_RELATIVE}, 2)


if __name__ == "__main__":
    raise SystemExit(main())
