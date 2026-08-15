#!/usr/bin/env python3
"""Execute the TASK-36 RC002 H11 lifecycle-clock exploratory screen."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task36_h11_lifecycle_clock_screen import (  # noqa: E402
    ATOM_ID,
    H11Error,
    canonical_json,
    execute_screen,
    format_owner_readout,
    format_utc,
    load_policy,
    sha256_bytes,
)

CONFIG_PATH = ROOT / "configs/task36_rc002_h11_lifecycle_clock_screen_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task36/a1_h11_lifecycle_clock_screen_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task36/a1_h11_lifecycle_clock_screen_acceptance_v1.json"
)
READOUT_PATH = (
    ROOT / "docs/reports/task36/a1_h11_lifecycle_clock_screen_owner_readout_v1.md"
)


def _dump(path: Path, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")
    return sha256_bytes(encoded.encode("utf-8"))


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    measured = datetime.now(UTC).replace(microsecond=0)
    result = execute_screen(repo_root=ROOT, policy=policy)
    runtime = {
        "schema": "smial.task36.rc002-h11-lifecycle-clock-screen.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": format_utc(measured),
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "protocol_sha256": result["protocol_sha256"],
        "trial": result["trial"],
        "cohort": result["cohort"],
        "inventory": result["inventory"],
        "rc001_freeze": result["rc001_freeze"],
        "holdout": result["holdout"],
        "live_universe": result["live_universe"],
        "live_PIT_claim": result["live_PIT_claim"],
        "execution_claim": result["execution_claim"],
        "alpha_claim": result["alpha_claim"],
        "side_effects": result["side_effects"],
        "non_claims": result["non_claims"],
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    runtime_sha = _dump(RUNTIME_RECEIPT_PATH, runtime)
    acceptance = {
        "schema": "smial.task36.rc002-h11-lifecycle-clock-screen.acceptance",
        "schema_version": "1.0",
        "as_of": measured.date().isoformat(),
        "atom_id": ATOM_ID,
        "receipt_id": "EVIDENCE-T36-RC002-H11-LIFECYCLE-CLOCK-001",
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "protocol_sha256": result["protocol_sha256"],
        "trial_id": result["trial"]["record_id"],
        "trial_outcome": result["trial"]["outcome"],
        "live_universe_n": result["cohort"]["n"],
        "runtime_receipt_sha256": runtime_sha,
        "rc001_mutated": result["rc001_mutated"],
        "holdout_consumed": result["holdout_consumed"],
        "remaining_rc001_deprioritized": result["remaining_rc001_deprioritized"],
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
    sys.stdout.write(canonical_json({"terminal_decision": result["terminal_decision"]}).decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except H11Error as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
