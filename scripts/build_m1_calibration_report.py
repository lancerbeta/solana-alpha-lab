#!/usr/bin/env python3
"""Build the deterministic M1 calibration report from immutable RDP lineage."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.m1_calibration_report import (  # noqa: E402
    build_m1_calibration_report,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--schedule-sha256", required=True)
    parser.add_argument("--activation-id", required=True)
    parser.add_argument("--availability-cutoff", required=True, help="UTC (…Z)")
    parser.add_argument("--population-ref", required=True)
    parser.add_argument("--sampling-file", type=Path, required=True)
    parser.add_argument("--lineage-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    sampling = json.loads(args.sampling_file.read_text(encoding="utf-8"))
    lineage = json.loads(args.lineage_file.read_text(encoding="utf-8"))
    report = build_m1_calibration_report(
        data_root=args.data_root,
        schedule_sha256=args.schedule_sha256,
        activation_id=args.activation_id,
        availability_cutoff=parse_utc(args.availability_cutoff),
        population_ref=args.population_ref,
        sampling_identity=sampling,
        source_lineage=lineage,
    )
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
