"""Run Factory V1 live-ops hardening commissioning (local phase0 or live host)."""

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

from solana_alpha_lab.factory.live_ops_hardening import (
    PASS_TERMINAL,
    LiveOpsHardeningError,
    build_acceptance,
    prove_phase0_local,
    validate_host_proof,
)

EVIDENCE_DIR = Path("docs/evidence/factory_v1_live_ops_hardening")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--phase0-only", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument(
        "--acceptance-from-json",
        type=Path,
        help="Validated live host proof JSON; required for PASS acceptance",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    phase0 = prove_phase0_local(root)
    if args.phase0_only:
        print(json.dumps({"terminal": phase0["terminal"], "phase": 0}, indent=2))
        return 0

    if args.acceptance_from_json is None:
        raise LiveOpsHardeningError("HOST_PROOF_REQUIRED_FOR_PASS")

    host_path = args.acceptance_from_json.resolve()
    host_proof = validate_host_proof(json.loads(host_path.read_text(encoding="utf-8")))
    host_proof_sha256 = hashlib.sha256(host_path.read_bytes()).hexdigest()
    acceptance = build_acceptance(
        runtime={
            **dict(host_proof["runtime"]),
            "release_steps": host_proof["release_steps"],
            "host": host_proof["host"],
            "deploy_sha": host_proof["deploy_sha"],
        },
        monitoring=host_proof["monitoring"],
        incident_lifecycle=host_proof["incident_lifecycle"],
        security={
            **dict(host_proof["security"]),
            "financial_command_surface_hits": list(
                host_proof["security"].get("financial_command_surface_hits") or []
            ),
        },
        side_effects=host_proof.get("side_effects"),
        host=str(host_proof["host"]),
        deploy_sha=str(host_proof["deploy_sha"]),
        host_proof_sha256=host_proof_sha256,
        live_bound=True,
    )
    if acceptance["terminal"] != PASS_TERMINAL:
        raise LiveOpsHardeningError("ACCEPTANCE_NOT_PASS")

    runtime_receipt = {
        "schema": "smial.factory-v1-live-ops-hardening.runtime-receipt",
        "schema_version": "1.0",
        "task_id": "FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1",
        "terminal": acceptance["terminal"],
        "host": acceptance["host"],
        "deploy_sha": acceptance["deploy_sha"],
        "host_proof_sha256": host_proof_sha256,
        "host_proof_bound": True,
        "release_sequence": {
            "start_sha": acceptance["runtime"]["start_sha"],
            "previous_sha": acceptance["runtime"]["previous_sha"],
            "target_sha": acceptance["runtime"]["target_sha"],
            "live_deploy_rollback": True,
            "live_forward_restore": True,
            "live_clean_rehost": True,
            "release_steps": host_proof["release_steps"],
            "left_on_rollback_sha": False,
        },
        "phase0": {
            "terminal": phase0["terminal"],
            "alerts_delivered": phase0["alerts_delivered"],
        },
        "side_effects": acceptance["side_effects"],
        "non_claims": acceptance["non_claims"],
    }

    if args.write_evidence:
        out = root / EVIDENCE_DIR
        _write_json(out / "a1_runtime_receipt_v1.json", runtime_receipt)
        _write_json(out / "a1_host_proof_v1.json", dict(host_proof))
        _write_json(out / "a1_acceptance_v1.json", acceptance)

    print(
        json.dumps(
            {
                "terminal": acceptance["terminal"],
                "phase0": phase0["terminal"],
                "host": acceptance["host"],
                "deploy_sha": acceptance["deploy_sha"],
                "host_proof_bound": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LiveOpsHardeningError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(2) from exc
