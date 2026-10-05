"""Explicit derived write lookup preparation. Never invoked by an ordinary tick."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--isolated-copy", action="store_true", required=True)
    args = parser.parse_args()
    if not args.data_root.is_absolute() or not args.data_root.is_dir():
        print(json.dumps({"status": "REFUSED", "reason": "EXISTING_ABSOLUTE_COPY_REQUIRED"}))
        return 2
    started = time.perf_counter()
    try:
        result = ResearchStore(args.data_root, create_if_missing=False).prepare_write_lookup()
    except ResearchStoreError as exc:
        print(json.dumps({"status": "REFUSED", "reason": exc.code}))
        return 2
    result["wall_seconds"] = time.perf_counter() - started
    from scripts.prove_opportunity_episode_operability import peak_rss
    result["process_peak_rss_bytes"] = peak_rss()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
