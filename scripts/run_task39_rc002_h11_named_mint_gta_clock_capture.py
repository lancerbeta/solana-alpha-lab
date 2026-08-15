#!/usr/bin/env python3
"""Execute the owner-authorized TASK-39 named-mint Helius GTA and clock scan."""

from __future__ import annotations

import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task39_h11_named_mint_gta_clock_capture import (  # noqa: E402
    ATOM_ID,
    OWNER_PHRASE,
    MintGtaError,
    canonical_json,
    credential_free_preflight,
    execute_capture,
    execute_live_pages,
    format_owner_readout,
    format_utc,
    load_api_key,
    load_policy,
    sha256_bytes,
)

CONFIG_PATH = ROOT / "configs/task39_rc002_h11_named_mint_gta_clock_capture_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task39/a1_h11_named_mint_gta_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task39/a1_h11_named_mint_gta_acceptance_v1.json"
)
READOUT_PATH = ROOT / "docs/reports/task39/a1_h11_named_mint_gta_owner_readout_v1.md"
RAW_ROOT = ROOT / "local/task39_rc002_h11_named_mint_gta"


def _dump(path: Path, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")
    return sha256_bytes(encoded.encode("utf-8"))


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    if policy["external_authority"]["owner_phrase"] != OWNER_PHRASE:
        raise MintGtaError("OWNER_PHRASE_DRIFT")
    measured = datetime.now(UTC).replace(microsecond=0)
    observed = format_utc(measured)
    credential_free_preflight(policy, observed_at=observed)
    credential_value = load_api_key()
    run_id = measured.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    rows, live_meta = execute_live_pages(
        repo_root=ROOT,
        policy=policy,
        credential=credential_value,
        raw_root=RAW_ROOT,
        run_id=run_id,
    )
    result = execute_capture(
        repo_root=ROOT,
        policy=policy,
        pages=rows,
        live_meta=live_meta,
    )
    runtime = {
        "schema": "smial.task39.rc002-h11-named-mint-gta.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": observed,
        "run_id": run_id,
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "clock_sha256": result["clock_sha256"],
        "trial": result["trial"],
        "cohort": result["cohort"],
        "scan": result["scan"],
        "rc001_freeze": result["rc001_freeze"],
        "holdout": result["holdout"],
        "live_universe": True,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "side_effects": result["side_effects"],
        "non_claims": result["non_claims"],
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    runtime_sha = _dump(RUNTIME_RECEIPT_PATH, runtime)
    acceptance = {
        "schema": "smial.task39.rc002-h11-named-mint-gta.acceptance",
        "schema_version": "1.0",
        "as_of": measured.date().isoformat(),
        "atom_id": ATOM_ID,
        "receipt_id": "EVIDENCE-T39-RC002-H11-NAMED-MINT-GTA-001",
        "terminal_decision": result["terminal_decision"],
        "research_cycle_id": result["research_cycle_id"],
        "clock_sha256": result["clock_sha256"],
        "trial_id": result["trial"]["record_id"],
        "trial_outcome": result["trial"]["outcome"],
        "live_universe_txs": result["scan"]["transaction_count"],
        "named_mint": result["scan"]["mint_address"],
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
                "transaction_count": result["scan"]["transaction_count"],
                "create_events": result["scan"]["create_events"],
                "migration_events": result["scan"]["migration_events"],
                "provider_requests": result["side_effects"]["provider_requests"],
                "run_id": run_id,
            }
        ).decode("utf-8")
        + "\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MintGtaError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
