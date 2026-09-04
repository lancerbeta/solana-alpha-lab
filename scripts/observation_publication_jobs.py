#!/usr/bin/env python
"""Publication-job journal status / dry-run / apply.

Zero provider calls. APPLY refuses live ACTIVE/DRAINING collectors, writes no
RDP/Parquet/manifests, does not clean STARTED rows, and does not delete
legacy_full.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    AMBIGUOUS_BLOCKS_APPLY,
    COLLECTOR_NOT_PAUSED,
    COLLECTOR_STORE_MISSING,
    COMPACT_RECEIPT_UNCONSTRUCTABLE,
    COMPLETED_RECEIPT_CONFLICT,
    CONTENT_IDENTITY_COLLISION,
    CONTENT_SHA256_INVALID,
    LEGACY_FULL_BYTE_MISMATCH,
    OPEN_JOB_CONFLICT,
    SOURCE_CHANGED_AFTER_PLAN,
    PublicationJobError,
    apply_migration,
    collector_blocks_apply,
    dry_run_migration,
    journal_stats,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    load_runtime_config,
    resolve_data_root,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "dry-run", "apply"))
    parser.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
    parser.add_argument("--data-root")
    parser.add_argument("--ops-store")
    parser.add_argument(
        "--i-understand-apply",
        action="store_true",
        help="Required exact flag for apply mode",
    )
    args = parser.parse_args(argv)

    runtime = load_runtime_config(ROOT, args.runtime_config)
    data_root = (
        Path(args.data_root).resolve()
        if args.data_root
        else resolve_data_root(ROOT, str(runtime["data_root"]))
    )
    store_path = (
        Path(args.ops_store).resolve()
        if args.ops_store
        else (ROOT / str(runtime["ops_store_relative"])).resolve()
    )

    if args.command in {"status", "dry-run"}:
        report = dry_run_migration(data_root) if args.command == "dry-run" else journal_stats(data_root)
        if args.command == "status":
            report = dict(report)
            report.update(dry_run_migration(data_root))
        report["provider_calls"] = 0
        report["scientific_writes"] = 0
        report["legacy_full_deleted"] = False
        return _emit(report, 0)

    if not args.i_understand_apply:
        return _emit(
            {
                "terminal": "APPLY_REQUIRES_FLAG",
                "reason": "--i-understand-apply",
                "provider_calls": 0,
                "scientific_writes": 0,
            },
            2,
        )
    if not store_path.is_file():
        return _emit(
            {
                "terminal": COLLECTOR_STORE_MISSING,
                "provider_calls": 0,
                "scientific_writes": 0,
            },
            2,
        )
    store = ObservationScheduleStore(store_path)
    try:
        activations = store.list_activations()
    finally:
        store.close()
    if collector_blocks_apply(activations):
        return _emit(
            {
                "terminal": COLLECTOR_NOT_PAUSED,
                "provider_calls": 0,
                "scientific_writes": 0,
                "activation_states": [
                    str(item.get("state") or "") for item in activations
                ],
            },
            2,
        )
    try:
        report = apply_migration(data_root)
    except PublicationJobError as exc:
        text = str(exc)
        known = {
            AMBIGUOUS_BLOCKS_APPLY,
            OPEN_JOB_CONFLICT,
            COMPLETED_RECEIPT_CONFLICT,
            LEGACY_FULL_BYTE_MISMATCH,
            COMPACT_RECEIPT_UNCONSTRUCTABLE,
            CONTENT_IDENTITY_COLLISION,
            CONTENT_SHA256_INVALID,
            SOURCE_CHANGED_AFTER_PLAN,
        }
        terminal = text if text in known else "PUBLICATION_JOB_ERROR"
        return _emit(
            {
                "terminal": terminal,
                "reason": text,
                "provider_calls": 0,
                "scientific_writes": 0,
                "legacy_full_deleted": False,
            },
            2,
        )
    report["terminal"] = "PUBLICATION_JOB_MIGRATION_APPLIED"
    report["provider_calls"] = 0
    report["scientific_writes"] = 0
    return _emit(report, 0)


if __name__ == "__main__":
    raise SystemExit(main())
