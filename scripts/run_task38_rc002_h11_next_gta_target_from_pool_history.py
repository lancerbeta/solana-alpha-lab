#!/usr/bin/env python3
"""Execute the TASK-38 RC002 H11 next bounded GTA target scan."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task37_h11_migration_clock_capture import (  # noqa: E402
    CaptureError,
)
from solana_alpha_lab.task38_h11_next_gta_target_from_pool_history import (  # noqa: E402
    ATOM_ID,
    canonical_json,
    execute_target,
    format_owner_readout,
    format_utc,
    load_policy,
    sha256_bytes,
)

CONFIG_PATH = ROOT / "configs/task38_rc002_h11_next_gta_target_from_pool_history_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task38/a1_h11_next_gta_target_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = ROOT / "docs/evidence/task38/a1_h11_next_gta_target_acceptance_v1.json"
READOUT_PATH = ROOT / "docs/reports/task38/a1_h11_next_gta_target_owner_readout_v1.md"


def _dump(path: Path, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")
    return sha256_bytes(encoded.encode("utf-8"))


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    measured = datetime.now(UTC).replace(microsecond=0)
    result = execute_target(repo_root=ROOT, policy=policy)
    runtime = {
        "schema": "smial.task38.rc002-h11-next-gta-target.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": format_utc(measured),
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "resolver_sha256": result["resolver_sha256"],
        "trial": result["trial"],
        "named_target": result["named_target"],
        "scan": result["scan"],
        "rc001_freeze": result["rc001_freeze"],
        "holdout": result["holdout"],
        "live_universe": result["live_universe"],
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "network_authorized": False,
        "side_effects": result["side_effects"],
        "non_claims": result["non_claims"],
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    runtime_sha = _dump(RUNTIME_RECEIPT_PATH, runtime)
    acceptance = {
        "schema": "smial.task38.rc002-h11-next-gta-target.acceptance",
        "schema_version": "1.0",
        "as_of": measured.date().isoformat(),
        "atom_id": ATOM_ID,
        "receipt_id": "EVIDENCE-T38-RC002-H11-NEXT-GTA-001",
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "resolver_sha256": result["resolver_sha256"],
        "trial_id": result["trial"]["record_id"],
        "trial_outcome": result["trial"]["outcome"],
        "named_target_kind": result["named_target"]["kind"],
        "named_target_address": result["named_target"]["address"],
        "network_authorized": False,
        "live_universe_txs": result["scan"]["transaction_count"],
        "runtime_receipt_sha256": runtime_sha,
        "rc001_mutated": False,
        "holdout_consumed": False,
        "remaining_rc001_deprioritized": True,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "side_effects": result["side_effects"],
        "non_claims": result["non_claims"],
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    _dump(ACCEPTANCE_PATH, acceptance)
    READOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    READOUT_PATH.write_text(format_owner_readout(result), encoding="utf-8", newline="\n")
    sys.stdout.write(
        canonical_json(
            {
                "terminal_decision": result["terminal_decision"],
                "named_target": result["named_target"],
                "network_authorized": False,
            }
        ).decode("utf-8")
        + "\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaptureError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
