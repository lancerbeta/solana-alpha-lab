#!/usr/bin/env python3
"""Scoped static analysis for active Factory Python code."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY_ROOT = ROOT / "src" / "solana_alpha_lab" / "factory"


def main() -> int:
    if not FACTORY_ROOT.is_dir():
        print("FACTORY_STATIC: FAIL")
        print("ERROR: factory package missing")
        return 1
    sources = sorted(path for path in FACTORY_ROOT.rglob("*.py") if path.is_file())
    if not sources:
        print("FACTORY_STATIC: FAIL")
        print("ERROR: factory python sources missing")
        return 1
    for path in sources:
        relative = path.relative_to(ROOT).as_posix()
        try:
            compile(path.read_text(encoding="utf-8"), relative, "exec")
        except SyntaxError as exc:
            print(f"FACTORY_STATIC: FAIL {relative}:{exc.lineno}")
            print(f"ERROR: {exc.msg}")
            return 1
    print("FACTORY_STATIC: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
