#!/usr/bin/env python3
"""Offline H11 Create six-field pubkey identity trial. No provider or credential calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    scan_retained_a4_create_pubkey_identity,
)


def main() -> int:
    result = scan_retained_a4_create_pubkey_identity(ROOT)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
