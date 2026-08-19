#!/usr/bin/env python3
"""Run one offline Factory experiment from an ExperimentSpec."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--spec", default=None)
    parser.add_argument("--authority-phrase", default=None)
    args = parser.parse_args()
    app = FactoryApplication(
        root=args.root.resolve(),
        spec_relative=args.spec,
        authority_phrase=args.authority_phrase,
    )
    try:
        model = app.start()
    except ApplicationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(model, indent=2, sort_keys=True))
    return 0 if model["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
