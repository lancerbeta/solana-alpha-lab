#!/usr/bin/env python3
"""Offline H11 early six-field Create layout trial. No provider or credential calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pump_event_decoder import load_pinned_pump_event_plan
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (
    IDL_RELATIVE,
    scan_retained_a4_create_early_six_field_layout,
)


def main() -> int:
    pinned = load_pinned_pump_event_plan(ROOT / IDL_RELATIVE)
    result = scan_retained_a4_create_early_six_field_layout(ROOT, pinned=pinned)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
