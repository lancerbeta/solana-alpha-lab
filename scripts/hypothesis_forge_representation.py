#!/usr/bin/env python3
"""Read-only status surface for the dormant HFIC representation lane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    RepresentationProbeError,
    representation_status,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only NORMALIZED_TRAJECTORY_V1 representation status"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "representation-status"):
        status_parser = subparsers.add_parser(command, help="evaluate a supplied status snapshot")
        status_parser.add_argument(
            "--input",
            dest="input_path",
            required=True,
            help="JSON snapshot; no current runtime state is read by default",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        snapshot = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
        result = representation_status(snapshot)
    except (OSError, json.JSONDecodeError, RepresentationProbeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
