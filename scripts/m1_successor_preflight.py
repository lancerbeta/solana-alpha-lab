#!/usr/bin/env python3
"""Zero-network M1 successor preflight. Never authorizes or activates."""

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

from solana_alpha_lab.factory.m1_successor_preflight import (  # noqa: E402
    run_m1_successor_preflight,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    parse_utc,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predecessor-readback",
        required=True,
        type=Path,
        help="JSON readback of the current ACTIVE predecessor activation",
    )
    parser.add_argument(
        "--predecessor-schedule",
        required=True,
        help="Relative path of the immutable predecessor schedule YAML",
    )
    parser.add_argument("--target-members", type=int, default=100)
    parser.add_argument("--campaign-days", type=int, default=7)
    parser.add_argument("--inclusion-probability", default="1.0")
    parser.add_argument("--now", default=None, help="UTC override (…Z)")
    args = parser.parse_args(argv)

    readback = json.loads(args.predecessor_readback.read_text(encoding="utf-8"))
    predecessor = load_observation_schedule(ROOT, args.predecessor_schedule)
    now = parse_utc(args.now) if args.now else datetime.now(UTC)
    result = run_m1_successor_preflight(
        root=ROOT,
        predecessor_readback=readback,
        predecessor_schedule=predecessor,
        m1_campaign_request={
            "target_members": args.target_members,
            "campaign_days": args.campaign_days,
            "inclusion_probability": args.inclusion_probability,
        },
        now=now,
    )
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    # Fail closed: no credential-shaped values may ever appear here.
    if '"x-api-key"' in text.casefold() or "bearer " in text.casefold():
        print(
            json.dumps(
                {"terminal": "SECRET_SHAPE_LEAK_BLOCKED", "network_calls": 0},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(text)
    if result.get("terminal") == "M1_SUCCESSOR_PREFLIGHT_COMPATIBLE":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
