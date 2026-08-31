#!/usr/bin/env python3
"""Print the proposed PathRisk capture packet or run an authority-gated live window."""

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
    CREDENTIAL_ENV_NAME,
    PathRiskLiveError,
    SystemClock,
    TERMINAL_CREDENTIAL_MISSING,
    load_process_credential,
    require_transport_probe_phrase,
    run_live_window,
    run_transport_probe_recent,
    transport_probe_owner_phrase,
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
    preflight = sub.add_parser(
        "live-preflight",
        help="read-only production preflight; no credential value read, no provider",
    )
    preflight.add_argument("--root", type=Path, default=ROOT)
    preflight.add_argument("--main-sha", required=True)
    live = sub.add_parser(
        "live-run",
        help="authority-gated PathRisk live window; fixture or --real-provider",
    )
    live.add_argument("--root", type=Path, default=ROOT)
    live.add_argument("--main-sha", required=True)
    live.add_argument("--owner-phrase", required=True)
    live.add_argument("--data-root", type=Path, required=True)
    live.add_argument("--producer-git-sha", required=True)
    mode = live.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--fake-provider-fixture",
        type=Path,
        help="zero-network fixture JSON; never opens sockets",
    )
    mode.add_argument(
        "--real-provider",
        action="store_true",
        help="production Jupiter GET opener after non-secret gates",
    )
    live.add_argument("--now", default=None, help="fixture-only UTC timestamp; forbidden with --real-provider")
    live.add_argument(
        "--stop-after",
        default=None,
        help="test-only crash injection; forbidden with --real-provider",
    )
    probe = sub.add_parser(
        "transport-probe-recent",
        help="one-GET /tokens/v2/recent diagnostic; not a PathRisk window",
    )
    probe.add_argument("--root", type=Path, default=ROOT)
    probe.add_argument(
        "--print-phrase",
        action="store_true",
        help="print the probe owner phrase; no provider, no credential read",
    )
    probe.add_argument("--owner-phrase", default=None)
    probe_mode = probe.add_mutually_exclusive_group()
    probe_mode.add_argument(
        "--fake-provider-fixture",
        type=Path,
        help="zero-network fixture JSON; never opens sockets",
    )
    probe_mode.add_argument(
        "--real-provider",
        action="store_true",
        help="one real Jupiter GET after the probe owner phrase; not this PR",
    )
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
    if args.command == "live-preflight":
        policy = load_policy(args.root)
        if policy.get("atom_id") != ATOM_ID:
            raise SystemExit("ATOM_DRIFT")
        try:
            document = proposed_capture_packet(root=args.root, main_sha=args.main_sha)
        except PathRiskCalibrationError as exc:
            raise SystemExit(str(exc)) from exc
        print(
            json.dumps(
                {
                    "credential_env_name": CREDENTIAL_ENV_NAME,
                    "dotenv_read": False,
                    "production_clock": "SYSTEM_UTC",
                    "fake_fixture_required": False,
                    "live_authorized": False,
                    "capture_packet_sha256": document.get("packet_sha256"),
                    "max_calls": document.get("max_calls"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "live-run":
        from solana_alpha_lab.factory.observation_schedule import parse_utc
        from solana_alpha_lab.factory.pathrisk_live import FixtureWindowOpener

        policy = load_policy(args.root)
        if policy.get("atom_id") != ATOM_ID:
            raise SystemExit("ATOM_DRIFT")
        if args.real_provider:
            if args.now is not None:
                raise SystemExit("NOW_OVERRIDE_FORBIDDEN_IN_PRODUCTION")
            if args.stop_after is not None:
                raise SystemExit("STOP_AFTER_FORBIDDEN_IN_PRODUCTION")
            try:
                result = run_live_window(
                    root=args.root,
                    data_root=args.data_root,
                    opener=None,
                    producer_git_sha=args.producer_git_sha,
                    owner_phrase=args.owner_phrase,
                    main_sha=args.main_sha,
                    production=True,
                    clock=SystemClock(),
                    stop_after=args.stop_after,
                )
            except (PathRiskCalibrationError, PathRiskLiveError) as exc:
                raise SystemExit(str(exc)) from exc
        else:
            if args.now is None:
                raise SystemExit("FIXTURE_NOW_REQUIRED")
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
                    production=False,
                )
            except (PathRiskCalibrationError, PathRiskLiveError) as exc:
                raise SystemExit(str(exc)) from exc
        payload = {
            key: value
            for key, value in result.items()
            if key not in {"readout", "h900_tick", "t0_tick"}
        }
        payload["execution_mode"] = "PRODUCTION" if args.real_provider else "FIXTURE"
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        if result.get("terminal") == TERMINAL_CREDENTIAL_MISSING:
            return 1
        return 0
    if args.command == "transport-probe-recent":
        from solana_alpha_lab.factory.observation_schedule_runtime import (
            JupiterReadonlyOpener,
        )
        from solana_alpha_lab.factory.pathrisk_live import FixtureWindowOpener

        policy = load_policy(args.root)
        if args.print_phrase:
            if args.real_provider or args.fake_provider_fixture is not None:
                raise SystemExit("PROBE_PRINT_PHRASE_EXCLUSIVE")
            print(transport_probe_owner_phrase(policy))
            return 0
        if args.owner_phrase is None:
            raise SystemExit("OWNER_PHRASE_REQUIRED")
        try:
            require_transport_probe_phrase(policy, args.owner_phrase)
        except PathRiskLiveError as exc:
            raise SystemExit(str(exc)) from exc
        if args.real_provider:
            try:
                credential = load_process_credential(None)
            except PathRiskLiveError as exc:
                raise SystemExit(str(exc)) from exc
            opener: object = JupiterReadonlyOpener(credential)
        elif args.fake_provider_fixture is not None:
            fixture = json.loads(args.fake_provider_fixture.read_text(encoding="utf-8"))
            opener = FixtureWindowOpener(fixture)
        else:
            raise SystemExit("PROBE_MODE_REQUIRED")
        payload = run_transport_probe_recent(opener=opener, clock=SystemClock())
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    raise SystemExit("COMMAND_UNKNOWN")


if __name__ == "__main__":
    raise SystemExit(main())
