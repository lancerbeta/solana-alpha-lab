#!/usr/bin/env python3
"""CLI for EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1. Live run is post-merge only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.early_icp_first_hit_mix_falsifier import (  # noqa: E402
    AUTHORITY_PHRASE,
    FirstHitError,
    credential_free_first_hit_preflight,
    run_first_hit_mix_falsifier,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    load_process_credential,
)


def _emit(payload: dict[str, object], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_early_icp_first_hit_mix_falsifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Post-merge only. Do not retry IN_FLIGHT_CALL_INDETERMINATE.\n"
            "STAGING_INSIDE_RDP: staging-root must be outside data-root.\n"
            "Owner-visible terminals: SLEEP_ELIGIBLE_BELOW_10, "
            "INVALID_EVIDENCE_REPLAN, CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY, "
            "EARN_ONE_CONFIRMATORY_FRESH_OOS.\n"
            "Exact owner phrase is configs/early_icp_first_hit_mix_falsifier_v1.yaml "
            "external_authority.owner_phrase; reprint it after merge, do not invent one.\n"
            "Example run:\n"
            "  python scripts/run_early_icp_first_hit_mix_falsifier.py "
            "--data-root <RDP> --staging-root <OUTSIDE_RDP> run --owner-phrase '<PHRASE>'"
        ),
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--staging-root",
        type=Path,
        default=None,
        help="Journal/raw staging outside the active RDP. Required for run.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    run = sub.add_parser("run")
    run.add_argument("--owner-phrase", required=True)
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    data_root = args.data_root
    try:
        if args.command == "preflight":
            return _emit(credential_free_first_hit_preflight(repo_root))
        if args.command == "run":
            if args.staging_root is None:
                return _emit({"status": "STAGING_ROOT_REQUIRED", "provider_requests": 0}, 2)
            receipt = run_first_hit_mix_falsifier(
                repo_root=repo_root,
                data_root=data_root,
                staging_root=args.staging_root,
                authority_phrase=args.owner_phrase,
                credential_loader=lambda: load_process_credential(os.environ),
            )
            return _emit(receipt)
    except FirstHitError as exc:
        return _emit(
            {
                "status": str(exc),
                "provider_requests": int(getattr(exc, "provider_requests", 0) or 0),
                "credential_reads": 0,
            },
            2,
        )
    return _emit({"status": "HFIC_COMMAND_NOT_READY"}, 2)


if __name__ == "__main__":
    sys.exit(main())
