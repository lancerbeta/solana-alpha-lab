#!/usr/bin/env python3
"""Offline H11 Complete/Migration scan of Create 195 git history.

No provider or credential calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_complete_migration_from_retained_create_history import (
    bind_complete_migration_from_retained_create_history,
)


def main() -> int:
    result = bind_complete_migration_from_retained_create_history(ROOT)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
