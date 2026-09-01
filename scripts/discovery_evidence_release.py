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
        else:
            result = import_discovery_release(
                release_root=args.release_root,
                data_root=args.data_root,
                import_time=_parse_utc(args.import_at),
            )
    except DiscoveryReleaseError as exc:
        print(json.dumps({"status": "FAIL", "code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "result": result}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
