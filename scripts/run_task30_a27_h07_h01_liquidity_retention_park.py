#!/usr/bin/env python3
"""Execute the authorized TASK-30 A27 H07/H01 park-from-priority decision."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_h07_h01_liquidity_retention_park import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    A27Error,
    canonical_json,
    execute_park,
    format_owner_readout,
    format_utc,
    load_policy,
    sha256_bytes,
)

CONFIG_PATH = ROOT / "configs/task30_a27_h07_h01_liquidity_retention_park_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task30/a27_h07_h01_liquidity_retention_park_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json"
)
READOUT_PATH = (
    ROOT / "docs/reports/task30/a27_h07_h01_liquidity_retention_park_owner_readout_v1.md"
)


def _dump(path: Path, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")
    return sha256_bytes(encoded.encode("utf-8"))


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    if policy["external_authority"]["owner_phrase"] != AUTHORITY_PHRASE:
        raise A27Error("OWNER_PHRASE_DRIFT")
    measured = datetime.now(UTC).replace(microsecond=0)
    result = execute_park(repo_root=ROOT, policy=policy)
    runtime = {
        "schema": "smial.task30.a27-h07-h01-liquidity-retention-park.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": format_utc(measured),
        "terminal_decision": result["terminal_decision"],
        "task_state": result["task_state"],
        "family_status": result["family_status"],
        "selected_fork": result["selected_fork"],
        "priority_disposition": result["priority_disposition"],
        "science_disposition": result["science_disposition"],
        "deletion": result["deletion"],
        "frozen_a26": result["frozen_a26"],
        "retained_evidence": result["retained_evidence"],
        "rc001_freeze": result["rc001_freeze"],
        "forbidden_follow_ons": result["forbidden_follow_ons"],
        "side_effects": result["side_effects"],
        "claims": result["claims"],
        "non_claims": result["non_claims"],
        "project_sources_disposition": result["project_sources_disposition"],
    }
    runtime_sha = _dump(RUNTIME_RECEIPT_PATH, runtime)
    acceptance = {
        "schema": "smial.task30.a27-h07-h01-liquidity-retention-park.acceptance",
        "schema_version": "1.0",
        "as_of": measured.date().isoformat(),
        "atom_id": ATOM_ID,
        "receipt_id": "EVIDENCE-T30-A27-H07-H01-LIQUIDITY-RETENTION-PARK-001",
        "task_id": "TASK-30",
        "decision": result["terminal_decision"],
        "task_state": result["task_state"],
        "family_status": result["family_status"],
        "named_consumer": result["named_consumer"],
        "selected_fork": result["selected_fork"],
        "priority_disposition": result["priority_disposition"],
        "science_disposition": result["science_disposition"],
        "deletion": result["deletion"],
        "frozen_a26": result["frozen_a26"],
        "retained_evidence": result["retained_evidence"],
        "rc001_freeze": result["rc001_freeze"],
        "forbidden_follow_ons": result["forbidden_follow_ons"],
        "claims": result["claims"],
        "non_claims": result["non_claims"],
        "side_effects": result["side_effects"],
        "runtime_receipt_sha256": runtime_sha,
        "project_sources_disposition": result["project_sources_disposition"],
    }
    _dump(ACCEPTANCE_PATH, acceptance)
    READOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    READOUT_PATH.write_text(format_owner_readout(result), encoding="utf-8", newline="\n")
    print(canonical_json({"terminal_decision": result["terminal_decision"]}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
