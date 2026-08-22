#!/usr/bin/env python3
"""Scoped static analysis for active Factory Python code."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY_ROOT = ROOT / "src" / "solana_alpha_lab" / "factory"


def main() -> int:
    if not FACTORY_ROOT.is_dir():
        print("FACTORY_STATIC: FAIL")
        print("ERROR: factory package missing")
        return 1
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--managed-python",
            "--group",
            "dev",
            "ruff",
            "check",
            str(FACTORY_ROOT.relative_to(ROOT)).replace("\\", "/"),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    if completed.returncode != 0:
        print("FACTORY_STATIC: FAIL")
        return completed.returncode
    print("FACTORY_STATIC: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
