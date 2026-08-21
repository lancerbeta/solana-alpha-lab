#!/usr/bin/env python3
"""Offline Failed-to-get-quotes MEU reproject for the frozen early-path receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_recent_early_path_h900_failed_quotes_meu_reproject import (  # noqa: E402
    ATOM_ID,
    build_acceptance,
    reproject,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=ATOM_ID)
    parser.add_argument(
        "--config",
        default=str(
            ROOT
            / "configs/ordinary_recent_early_path_h900_failed_quotes_meu_reproject_v1.yaml"
        ),
    )
    parser.add_argument(
        "--runtime-out",
        default=str(
            ROOT
            / "docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject"
            / "a1_ordinary_recent_early_path_h900_failed_quotes_meu_reproject_runtime_receipt_v1.json"
        ),
    )
    parser.add_argument(
        "--acceptance-out",
        default=str(
            ROOT
            / "docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject"
            / "a1_ordinary_recent_early_path_h900_failed_quotes_meu_reproject_acceptance_v1.json"
        ),
    )
    args = parser.parse_args()
    policy = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    runtime = reproject(root=ROOT, policy=policy)
    acceptance = build_acceptance(runtime)
    runtime_path = Path(args.runtime_out)
    acceptance_path = Path(args.acceptance_out)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    acceptance_path.write_text(
        json.dumps(acceptance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "atom_id": ATOM_ID,
                "terminal": runtime["score"]["terminal"],
                "failed_quotes_remapped_to_meu": runtime["failed_quotes_remapped_to_meu"],
                "runtime_out": str(runtime_path.relative_to(ROOT)).replace("\\", "/"),
                "acceptance_out": str(acceptance_path.relative_to(ROOT)).replace("\\", "/"),
                "provider_requests": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
