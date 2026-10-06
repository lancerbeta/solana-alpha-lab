"""Explicit derived write lookup preparation. Never invoked by an ordinary tick."""
from __future__ import annotations

import argparse
import json
import sys
import time
import re
import sqlite3
from datetime import UTC, datetime
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore, ObservationScheduleStoreError,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--isolated-copy", action="store_true")
    modes.add_argument("--production-commissioning", action="store_true")
    parser.add_argument("--operate-authority-ref")
    parser.add_argument("--verified-backup-sha256")
    parser.add_argument("--copy-rehearsal-sha256")
    parser.add_argument("--quiesced-writers", action="store_true")
    parser.add_argument("--ops-store", type=Path)
    args = parser.parse_args()
    if not args.data_root.is_absolute() or not args.data_root.is_dir():
        print(json.dumps({"status": "REFUSED", "reason": "EXISTING_ABSOLUTE_ROOT_REQUIRED"}))
        return 2
    if args.production_commissioning and not (
        re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", args.operate_authority_ref or "") and args.quiesced_writers
        and re.fullmatch(r"[0-9a-f]{64}", args.verified_backup_sha256 or "")
        and re.fullmatch(r"[0-9a-f]{64}", args.copy_rehearsal_sha256 or "")
        and args.ops_store and args.ops_store.is_absolute() and args.ops_store.is_file()
    ):
        print(json.dumps({"status": "REFUSED", "reason": "COMMISSIONING_ATTESTATIONS_REQUIRED"}))
        return 2
    started = time.perf_counter()
    try:
        research = ResearchStore(args.data_root, create_if_missing=False)
        if args.isolated_copy:
            result = research.prepare_write_lookup()
        else:
            with closing(ObservationScheduleStore(args.ops_store)) as ops:
                lease = ops.acquire_lease("explicit-research-lookup-commissioning", clock=datetime.now(UTC))
                if lease is None:
                    raise ResearchStoreError("WRITER_BUSY")
                try:
                    with ops.fenced_maintenance():
                        result = research.prepare_write_lookup()
                finally:
                    ops.release_lease(lease)
        result["mode"] = "ISOLATED_COPY" if args.isolated_copy else "PRODUCTION_COMMISSIONING"
        result["authority_semantics"] = "OPERATOR_ATTESTED_SEPARATE_OPERATE_REQUIRED"
    except (ResearchStoreError, ObservationScheduleStoreError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": getattr(exc, "code", str(exc))}))
        return 2
    except sqlite3.OperationalError:
        print(json.dumps({"status": "REFUSED", "reason": "OPS_STORE_UNAVAILABLE_OR_BUSY"}))
        return 2
    except OSError:
        print(json.dumps({"status": "REFUSED", "reason": "COMMISSIONING_INPUT_UNREADABLE"}))
        return 2
    result["wall_seconds"] = time.perf_counter() - started
    from scripts.prove_opportunity_episode_operability import peak_rss
    result["process_peak_rss_bytes"] = peak_rss()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
