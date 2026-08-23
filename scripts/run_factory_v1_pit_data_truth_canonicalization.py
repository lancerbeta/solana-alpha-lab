"""Generate the zero-network A4 PIT canonicalization evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.pit_data_truth_canonicalization import (
    FACTORY_RUNNER_RELATIVE,
    FACTORY_RUNNER_SHA256,
    PIT_TERMINAL,
    SOURCE_RUNTIME_RELATIVE,
    SOURCE_RUNTIME_SHA256,
    canonicalize_from_repository,
)


OUTPUT_RELATIVE = (
    "docs/evidence/factory_v1_pit_data_truth_canonicalization"
)
ACCEPTANCE_NAME = "a1_acceptance_v1.json"
RUNTIME_NAME = "a1_runtime_receipt_v1.json"


def build_runtime_receipt(acceptance: dict[str, Any]) -> dict[str, Any]:
    projection = acceptance["projection"]
    return {
        "schema": "smial.factory-v1-pit-data-truth-canonicalization.runtime-receipt",
        "schema_version": "1.0",
        "task_id": "FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1",
        "terminal": PIT_TERMINAL,
        "source": {
            "path": SOURCE_RUNTIME_RELATIVE,
            "sha256": SOURCE_RUNTIME_SHA256,
            "retention": "A4_OUTSIDE_GIT_RAW_BYTES_NOT_IMPORTED",
        },
        "projection": {
            "candidate_count": projection["candidate_count"],
            "eligible_count": projection["eligible_count"],
            "missing_count": projection["missing_count"],
            "missing_reason_counts": projection["missing_reason_counts"],
            "decision_snapshot_at": projection["decision_snapshot_at"],
        },
        "factory_runner": {
            "path": FACTORY_RUNNER_RELATIVE,
            "sha256": FACTORY_RUNNER_SHA256,
            "changed": False,
        },
        "side_effects": {
            "provider_calls": 0,
            "credential_reads": 0,
            "network_calls": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
        },
    }


def _write_json(
    path: Path,
    value: dict[str, Any],
    *,
    allow_current_evidence_rewrite: bool,
    expected_existing_sha256: str | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    encoded = payload.encode("utf-8")
    if path.exists():
        if path.read_bytes() == encoded:
            return
        if not allow_current_evidence_rewrite:
            raise RuntimeError(f"EVIDENCE_REWRITE_FORBIDDEN:{path.as_posix()}")
        actual_existing_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_existing_sha256 != actual_existing_sha256:
            raise RuntimeError(
                f"EVIDENCE_REWRITE_PRECONDITION_FAILED:{path.as_posix()}"
            )
    path.write_bytes(encoded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--rewrite-current-evidence", action="store_true")
    parser.add_argument("--expected-existing-acceptance-sha256")
    parser.add_argument("--expected-existing-runtime-sha256")
    args = parser.parse_args()

    root = args.root.resolve()
    acceptance = canonicalize_from_repository(root)
    runtime_receipt = build_runtime_receipt(acceptance)
    if args.write_evidence:
        output_dir = root / OUTPUT_RELATIVE
        _write_json(
            output_dir / ACCEPTANCE_NAME,
            acceptance,
            allow_current_evidence_rewrite=args.rewrite_current_evidence,
            expected_existing_sha256=args.expected_existing_acceptance_sha256,
        )
        _write_json(
            output_dir / RUNTIME_NAME,
            runtime_receipt,
            allow_current_evidence_rewrite=args.rewrite_current_evidence,
            expected_existing_sha256=args.expected_existing_runtime_sha256,
        )
    print(json.dumps(acceptance, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
