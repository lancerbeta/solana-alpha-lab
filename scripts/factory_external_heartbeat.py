#!/usr/bin/env python
"""External liveness heartbeat. Unconfigured is a typed no-op."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.external_heartbeat import run_external_heartbeat  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    result = run_external_heartbeat()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("terminal") in {"NOT_CONFIGURED", "HEARTBEAT_SENT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
