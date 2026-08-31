#!/usr/bin/env python3
"""Print the proposed PathRisk capture packet. Does not call a provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.pathrisk_calibration import (  # noqa: E402
    ATOM_ID,
    PathRiskCalibrationError,
    load_policy,
    proposed_capture_packet,
)
from solana_alpha_lab.factory.pathrisk_live import (  # noqa: E402
    PathRiskLiveError,
    run_live_window,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    packet = sub.add_parser(
        "capture-packet",
        help="print the proposed packet JSON; not a live calibration",
    )
    packet.add_argument("--root", type=Path, default=ROOT)
    packet.add_argument(
        "--main-sha",
        required=True,
        help="exact 40-hex main SHA after guarded merge; placeholders are refused",
    )
    live = sub.add_parser(
        "live-run",
        help="authority-gated PathRisk live window; fixture opener is required unless explicitly live",
    )
    live.add_argument("--root", type=Path, default=ROOT)
    live.add_argument("--main-sha", required=True)
    live.add_argument("--owner-phrase", required=True)
    live.add_argument("--data-root", type=Path, required=True)
    live.add_argument("--producer-git-sha", required=True)
    live.add_argument("--fake-provider-fixture", type=Path, required=True)
    live.add_argument("--now", default="2026-09-01T00:10:00Z")
    live.add_argument("--stop-after", default=None)
    args = parser.parse_args()
    if args.command == "capture-packet":
        policy = load_policy(args.root)
        if policy.get("atom_id") != ATOM_ID:
            raise SystemExit("ATOM_DRIFT")
        if policy.get("external_authority", {}).get("capture_authorized") is True:
            raise SystemExit("LIVE_CAPTURE_NOT_IN_THIS_COMMAND")
        try:
            document = proposed_capture_packet(root=args.root, main_sha=args.main_sha)
        except PathRiskCalibrationError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    if args.command == "live-run":
        from solana_alpha_lab.factory.observation_schedule import parse_utc
        from solana_alpha_lab.factory.pathrisk_live import FixtureWindowOpener

        policy = load_policy(args.root)
        if policy.get("atom_id") != ATOM_ID:
            raise SystemExit("ATOM_DRIFT")
        fixture = json.loads(args.fake_provider_fixture.read_text(encoding="utf-8"))
        opener = FixtureWindowOpener(fixture)
        try:
            result = run_live_window(
                root=args.root,
                data_root=args.data_root,
                opener=opener,
                producer_git_sha=args.producer_git_sha,
                owner_phrase=args.owner_phrase,
                main_sha=args.main_sha,
                now=parse_utc(args.now),
                stop_after=args.stop_after,
            )
        except (PathRiskCalibrationError, PathRiskLiveError) as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(
            {key: value for key, value in result.items() if key not in {"readout", "h900_tick", "t0_tick"}},
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0
    raise SystemExit("COMMAND_UNKNOWN")


if __name__ == "__main__":
    raise SystemExit(main())
