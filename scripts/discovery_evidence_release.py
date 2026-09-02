#!/usr/bin/env python
"""Zero-network Discovery Evidence Release CLI (seal / verify / import)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.discovery_evidence_release import (
    DiscoveryReleaseError,
    import_discovery_release,
    load_source_inventory,
    seal_discovery_release,
    verify_discovery_release,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LiveCohortReleaseError,
    build_live_observation_source_from_rdp,
    import_live_cohort,
    live_cohort_status,
    seal_live_cohort,
    verify_live_cohort,
)


def _parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    seal = sub.add_parser("seal", help="Seal a compact discovery release")
    seal.add_argument("--body", type=Path, required=True)
    seal.add_argument("--envelope", type=Path, required=True)
    seal.add_argument("--source-receipt", type=Path, default=None)
    seal.add_argument("--release-root", type=Path, required=True)
    seal.add_argument("--sealed-at", type=str, default=None)

    verify = sub.add_parser("verify", help="Verify a sealed release")
    verify.add_argument("--release-root", type=Path, required=True)

    imp = sub.add_parser("import", help="Import a verified release into an RDP root")
    imp.add_argument("--release-root", type=Path, required=True)
    imp.add_argument("--data-root", type=Path, required=True)
    imp.add_argument("--import-at", type=str, default=None)

    build_live = sub.add_parser(
        "build-live-source",
        help="Rebuild deterministic live source snapshot from Observation RDP",
    )
    build_live.add_argument("--observation-rdp", type=Path, required=True)
    build_live.add_argument("--schedule-sha256", required=True)
    build_live.add_argument("--activation-id", required=True)

    live_status = sub.add_parser(
        "live-status", help="Cohort readiness from immutable Observation RDP"
    )
    live_status.add_argument("--observation-rdp", type=Path, required=True)
    live_status.add_argument("--cohort-id", required=True)
    live_status.add_argument("--as-of", type=str, default=None)

    seal_live = sub.add_parser("seal-live-cohort", help="Seal a ready live cohort")
    seal_live.add_argument("--observation-rdp", type=Path, required=True)
    seal_live.add_argument("--cohort-id", required=True)
    seal_live.add_argument("--release-root", type=Path, required=True)
    seal_live.add_argument("--sealed-at", type=str, default=None)
    seal_live.add_argument("--as-of", type=str, default=None)

    verify_live = sub.add_parser("verify-live", help="Verify a sealed live cohort")
    verify_live.add_argument("--release-root", type=Path, required=True)

    import_live = sub.add_parser(
        "import-live", help="Import a verified live cohort into the LIVE CORPUS"
    )
    import_live.add_argument("--release-root", type=Path, required=True)
    import_live.add_argument("--data-root", type=Path, required=True)
    import_live.add_argument("--import-at", type=str, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            inventory = load_source_inventory(
                body_path=args.body,
                envelope_path=args.envelope,
                source_receipt_path=args.source_receipt,
            )
            result = seal_discovery_release(
                inventory=inventory,
                release_root=args.release_root,
                sealed_at=_parse_utc(args.sealed_at),
            )
        elif args.command == "verify":
            result = verify_discovery_release(args.release_root)
        elif args.command == "import":
            result = import_discovery_release(
                release_root=args.release_root,
                data_root=args.data_root,
                import_time=_parse_utc(args.import_at),
            )
        elif args.command == "build-live-source":
            result = build_live_observation_source_from_rdp(
                observation_rdp_root=args.observation_rdp,
                schedule_sha256=args.schedule_sha256,
                activation_id=args.activation_id,
            )
        elif args.command == "live-status":
            result = live_cohort_status(
                observation_rdp_root=args.observation_rdp,
                cohort_id=args.cohort_id,
                as_of=_parse_utc(args.as_of),
            )
        elif args.command == "seal-live-cohort":
            result = seal_live_cohort(
                observation_rdp_root=args.observation_rdp,
                cohort_id=args.cohort_id,
                release_root=args.release_root,
                sealed_at=_parse_utc(args.sealed_at),
                as_of=_parse_utc(args.as_of),
            )
        elif args.command == "verify-live":
            result = verify_live_cohort(args.release_root)
        else:
            result = import_live_cohort(
                release_root=args.release_root,
                data_root=args.data_root,
                import_time=_parse_utc(args.import_at),
            )
    except (DiscoveryReleaseError, LiveCohortReleaseError) as exc:
        print(json.dumps({"status": "FAIL", "code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "result": result}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
