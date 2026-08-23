"""Run Factory V1 live-ops hardening commissioning (local phase0 or live host)."""

from __future__ import annotations

import argparse
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
    clear_diagnostic_inject,
    prove_financial_boundary,
    prove_incident_lifecycle,
    prove_local_clean_rehost,
    prove_phase0_local,
    run_fault_matrix,
)
from solana_alpha_lab.factory.remote_ops import load_config, package_backup, write_heartbeat

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
        help="Merge live host proof fields into acceptance",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    phase0 = prove_phase0_local(root)
    acceptance = dict(phase0["acceptance_draft"])
    host_proof: dict[str, Any] | None = None
    if args.acceptance_from_json is not None:
        host_proof = json.loads(args.acceptance_from_json.read_text(encoding="utf-8"))
        runtime = dict(acceptance["runtime"])
        monitoring = dict(acceptance["monitoring"])
        security = dict(acceptance["security"])
        incident = dict(acceptance["incident_lifecycle"])
        if isinstance(host_proof.get("runtime"), dict):
            runtime.update(host_proof["runtime"])
        if isinstance(host_proof.get("monitoring"), dict):
            monitoring.update(host_proof["monitoring"])
        if isinstance(host_proof.get("security"), dict):
            security.update(host_proof["security"])
        if isinstance(host_proof.get("incident_lifecycle"), dict):
            incident.update(host_proof["incident_lifecycle"])
        acceptance = build_acceptance(
            runtime=runtime,
            monitoring=monitoring,
            incident_lifecycle=incident,
            security=security,
            side_effects=host_proof.get("side_effects") or acceptance["side_effects"],
        )

    if acceptance["terminal"] != PASS_TERMINAL:
        raise LiveOpsHardeningError("ACCEPTANCE_NOT_PASS")

    runtime_receipt = {
        "schema": "smial.factory-v1-live-ops-hardening.runtime-receipt",
        "schema_version": "1.0",
        "task_id": "FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1",
        "terminal": acceptance["terminal"],
        "phase0": {"terminal": phase0["terminal"], "alerts_delivered": phase0["alerts_delivered"]},
        "host_proof_bound": host_proof is not None,
        "side_effects": acceptance["side_effects"],
    }

    if args.write_evidence:
        out = root / EVIDENCE_DIR
        _write_json(out / "a1_runtime_receipt_v1.json", runtime_receipt)
        if host_proof is not None:
            _write_json(out / "a1_host_proof_v1.json", host_proof)
        _write_json(out / "a1_acceptance_v1.json", acceptance)

    print(json.dumps({"terminal": acceptance["terminal"], "phase0": phase0["terminal"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LiveOpsHardeningError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(2) from exc
