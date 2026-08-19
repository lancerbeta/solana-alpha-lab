#!/usr/bin/env python3
"""Prove or inspect the Factory v1 Linux-shaped production-lite runtime. No VPS."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.runtime import FactoryRuntime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("command", choices=("health", "prove", "rehost-isolated"))
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "health":
        runtime = FactoryRuntime(root=root, process_alive=True)
        print(json.dumps(runtime.health(), indent=2, ensure_ascii=False, sort_keys=True))
        runtime.close()
        return 0
    if args.command == "prove":
        runtime = FactoryRuntime(root=root)
        packet = runtime.prove()
        print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
        runtime.close()
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        runtime = FactoryRuntime(root=root, process_alive=True)
        hosted = runtime.rehost(Path(tmp) / "rehost")
        packet = hosted.health()
        print(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True))
        hosted.close()
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
