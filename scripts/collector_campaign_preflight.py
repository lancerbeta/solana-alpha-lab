#!/usr/bin/env python3
"""Zero-network collector campaign preflight. Never authorizes or activates."""

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

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    run_campaign_preflight,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--starts-at", required=True, help="UTC campaign start (…Z)")
    parser.add_argument(
        "--max-members-per-utc-day",
        type=int,
        default=150,
    )
    parser.add_argument(
        "--candidate-launches-per-utc-day",
        type=int,
        default=2000,
    )
    parser.add_argument(
        "--empirical-overlap-seconds",
        type=int,
        default=None,
    )
    args = parser.parse_args(argv)
    starts = parse_utc(args.starts_at)
    result = run_campaign_preflight(
        root=ROOT,
        starts_at=starts,
        max_members_per_utc_day=args.max_members_per_utc_day,
        candidate_launches_per_utc_day=args.candidate_launches_per_utc_day,
        empirical_overlap_seconds=args.empirical_overlap_seconds,
    )
    # Fail closed: never emit credential values (none are read).
    text = json.dumps(result, indent=2, sort_keys=True)
    # Fail closed on accidental credential-shaped values (never expected in A2).
    if '"x-api-key"' in text.casefold() or "bearer " in text.casefold():
        print(
            json.dumps(
                {
                    "terminal": "SECRET_SHAPE_LEAK_BLOCKED",
                    "live_authority_granted": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(text)
    if result.get("live_authority_granted") is True:
        return 2
    if result.get("terminal") == "STOP_FREE_TIER_CAPACITY_NOT_PROVEN":
        return 2
    return 0 if result.get("terminal") == "CAMPAIGN_PREFLIGHT_PROPOSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
