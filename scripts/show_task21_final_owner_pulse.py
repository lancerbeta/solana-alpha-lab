#!/usr/bin/env python3
"""Render the final accepted TASK-21 owner pulse without side effects."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_final_owner_pulse import (  # noqa: E402
    build_final_owner_pulse,
    canonical_json_bytes,
    render_final_owner_pulse_text,
)
from solana_alpha_lab.task21_owner_pulse import parse_utc  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the final TASK-21 owner pulse without side effects."
    )
    parser.add_argument("--as-of", help="Optional exact UTC timestamp.")
    parser.add_argument("--json", action="store_true", help="Render canonical JSON.")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    observed_at = parse_utc(args.as_of) if args.as_of else datetime.now(timezone.utc)
    pulse = build_final_owner_pulse(repository_root=ROOT, as_of=observed_at)
    if args.json:
        sys.stdout.buffer.write(canonical_json_bytes(pulse))
    else:
        sys.stdout.write(render_final_owner_pulse_text(pulse))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
