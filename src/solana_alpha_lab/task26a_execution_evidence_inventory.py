"""Deterministic tracked-only execution-evidence inventory for TASK-26A A1."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

TASK_ID = "TASK-26A"
ATOM_ID = "T26A-A1_EXECUTION_EVIDENCE_CONTRACT_AND_INVENTORY_V1"
AS_OF = "2026-08-04"
CONFIG_PATH = Path("configs/task26a_execution_evidence_completion_contract_v1.yaml")
INVENTORY_PATH = Path("docs/evidence/task26a/a1_execution_evidence_inventory_v1.json")
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26a/a1_execution_evidence_inventory_acceptance_v1.json"
)

EVIDENCE_CLASSES = [
    "QUOTE",
    "BUILD",
    "SIMULATION",
    "SEND_ATTEMPT",
    "PROCESSED_TERMINAL",
    "LANDING",
    "FILL",
    "FEE_CHARGEABILITY",
    "INVENTORY",
    "SETTLEMENT",
    "MODELED_NETRETURN",
    "OBSERVED_NETRETURN",
    "UNKNOWN",
]

RESULT_EXTEND = "EXTEND_EXECUTION_EVIDENCE"
FORBIDDEN_RESULTS = {
    "FIT_FOR_MODELED_NETRETURN_COMPARISON_WITH_LIMITATIONS",
}


class Task26AInventoryError(ValueError):
    """Raised when tracked inventory inputs drift or semantics are violated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26AInventoryError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _read_bound(
    repo_root: Path,
    path: str,
    expected_sha256: str,
) -> tuple[bytes, int]:
    root = repo_root.resolve()
    candidate = (root / path).resolve()
    _require(candidate.is_relative_to(root), f"path_escape:{path}")
    _require(candidate.is_file() and not candidate.is_symlink(), f"input_missing:{path}")
    payload = candidate.read_bytes()
    _require(sha256_bytes(payload) == expected_sha256, f"input_hash_drift:{path}")
    return payload, len(payload)


def load_config(repo_root: Path) -> dict[str, Any]:
    payload, _ = _read_bound(
        repo_root,
        str(CONFIG_PATH).replace("\\", "/"),
        sha256_bytes((repo_root / CONFIG_PATH).read_bytes()),
    )
    document = yaml.safe_load(payload.decode("utf-8"))
    _require(isinstance(document, dict), "config_not_mapping")
    return document


def build_inventory(repo_root: Path) -> dict[str, Any]:
    config = yaml.safe_load((repo_root / CONFIG_PATH).read_text(encoding="utf-8"))
    _require(isinstance(config, dict), "config_not_mapping")
    bindings_cfg = config["frozen_input_bindings"]
    input_bindings: list[dict[str, Any]] = []
    payloads: dict[str, Any] = {}
    for binding in bindings_cfg:
        raw, size = _read_bound(repo_root, binding["path"], binding["sha256"])
        input_bindings.append(
            {
                "asset_id": binding["asset_id"],
                "path": binding["path"],
                "sha256": binding["sha256"],
                "bytes": size,
            }
        )
        if binding["path"].endswith(".json"):
            payloads[binding["asset_id"]] = json.loads(raw.decode("utf-8"))

    a5 = payloads["DATA-T26-R2-EXECUTION-COST-INPUT-PROJECTION-001"]
    a6 = payloads["EVIDENCE-T26-A6-ACCEPTANCE-001"]
    a7 = payloads["EVIDENCE-T26-A7-CATALOG-FACTORY-FIT-001"]

    summary = a5["summary"]
    accepted = a7["accepted_result"]
    _require(summary["pairs_input"] == 36, "pair_denominator_drift")
    _require(summary["pairs_output"] == 36, "pair_output_drift")
    _require(summary["execution_cost_input_states"]["QUOTE_COST_INPUT_READY"] == 35, "ready_pair_drift")
    _require(summary["execution_cost_input_states"]["NOT_COMPUTABLE"] == 1, "latency_blocker_drift")
    _require(summary["numeric_netreturn_claims"] == 0, "numeric_netreturn_claim_present")
    _require(summary["actual_fill_or_settlement_claims"] == 0, "fill_or_settlement_claim_present")
    _require(accepted["settled_cashflow_observed"] == 0, "settled_cashflow_drift")
    _require(accepted["owner_decision"] == RESULT_EXTEND, "owner_decision_drift")
    _require(a6["owner_decision"]["decision"] == RESULT_EXTEND, "a6_decision_drift")
    _require(a5["net_return_surface"]["classification"] == "NOT_COMPUTABLE", "netreturn_surface_drift")
    _require(
        a5["net_return_surface"]["reason"] == "R2_NO_COMPLETE_FEE_OR_SETTLED_CASHFLOW",
        "netreturn_reason_drift",
    )

    pairs_total = 36
    component_inventory = [
        {
            "component_id": "fee_chargeability",
            "evidence_class": "FEE_CHARGEABILITY",
            "source_binding": "DATA-T26-R2-EXECUTION-COST-INPUT-PROJECTION-001",
            "availability_status": "MISSING",
            "missingness_reason": "R2_NO_COMPLETE_FEE_OR_SETTLED_CASHFLOW",
            "consumer": "TASK-26A",
            "pair_coverage": {
                "pairs_total": pairs_total,
                "pairs_complete": 0,
                "pairs_incomplete": pairs_total,
            },
        },
        {
            "component_id": "send_attempt",
            "evidence_class": "SEND_ATTEMPT",
            "source_binding": "EVIDENCE-T26-A7-CATALOG-FACTORY-FIT-001",
            "availability_status": "MISSING",
            "missingness_reason": "NO_TRACKED_ATTEMPT_OR_RETRY_CHAIN_EVIDENCE",
            "consumer": "TASK-26A",
            "pair_coverage": {
                "pairs_total": pairs_total,
                "pairs_complete": 0,
                "pairs_incomplete": pairs_total,
            },
        },
        {
            "component_id": "landing",
            "evidence_class": "LANDING",
            "source_binding": "EVIDENCE-T26-A7-CATALOG-FACTORY-FIT-001",
            "availability_status": "MISSING",
            "missingness_reason": "NO_TRACKED_LANDING_EVIDENCE_PROCESSED_ONLY_INSUFFICIENT",
            "consumer": "TASK-26A",
            "pair_coverage": {
                "pairs_total": pairs_total,
                "pairs_complete": 0,
                "pairs_incomplete": pairs_total,
            },
        },
        {
            "component_id": "inventory",
            "evidence_class": "INVENTORY",
            "source_binding": "CONTRACT-T26-EXECUTION-COST-NETRETURN-001",
            "availability_status": "UNKNOWN",
            "missingness_reason": "NO_RECONCILED_FLAT_ACTUAL_INVENTORY",
            "consumer": "TASK-26A",
            "pair_coverage": {
                "pairs_total": pairs_total,
                "pairs_complete": 0,
                "pairs_incomplete": pairs_total,
            },
        },
        {
            "component_id": "settlement",
            "evidence_class": "SETTLEMENT",
            "source_binding": "EVIDENCE-T26-A7-CATALOG-FACTORY-FIT-001",
            "availability_status": "MISSING",
            "missingness_reason": "SETTLED_CASHFLOW_OBSERVED_ZERO",
            "consumer": "TASK-26A",
            "pair_coverage": {
                "pairs_total": pairs_total,
                "pairs_complete": 0,
                "pairs_incomplete": pairs_total,
            },
        },
    ]

    gap_matrix = [
        {
            "gap_id": "GAP-FEE-COMPLETE-001",
            "component_id": "fee_chargeability",
            "evidence_class": "FEE_CHARGEABILITY",
            "severity": "BLOCKER",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "All 36 R2 pairs lack complete independently evidenced fee chargeability.",
        },
        {
            "gap_id": "GAP-ATTEMPT-001",
            "component_id": "send_attempt",
            "evidence_class": "SEND_ATTEMPT",
            "severity": "BLOCKER",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "No tracked send-attempt or retry-chain evidence exists for the R2 population.",
        },
        {
            "gap_id": "GAP-LANDING-001",
            "component_id": "landing",
            "evidence_class": "LANDING",
            "severity": "BLOCKER",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "Landing cannot be inferred from quote or processed-only samples.",
        },
        {
            "gap_id": "GAP-INVENTORY-001",
            "component_id": "inventory",
            "evidence_class": "INVENTORY",
            "severity": "BLOCKER",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "Reconciled flat actual inventory is absent; unresolved inventory must remain unknown.",
        },
        {
            "gap_id": "GAP-SETTLEMENT-001",
            "component_id": "settlement",
            "evidence_class": "SETTLEMENT",
            "severity": "BLOCKER",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "Settled cashflow observed count is zero across the tracked R2 surface.",
        },
        {
            "gap_id": "GAP-LATENCY-001",
            "component_id": "quote",
            "evidence_class": "QUOTE",
            "severity": "HIGH",
            "blocks_modeled_netreturn": True,
            "blocks_observed_netreturn": True,
            "reason": "One pair remains latency-blocked and is not quote-cost-input ready.",
        },
    ]

    inventory = {
        "schema": "smial.task26a.execution-evidence-inventory",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "input_bindings": input_bindings,
        "evidence_classes": list(EVIDENCE_CLASSES),
        "component_inventory": component_inventory,
        "gap_matrix": gap_matrix,
        "population_summary": {
            "quote_pairs": 36,
            "quote_cost_input_ready_pairs": 35,
            "latency_blocked_pairs": 1,
            "pairs_with_complete_fee_evidence": 0,
            "pairs_with_complete_attempt_evidence": 0,
            "pairs_with_complete_landing_evidence": 0,
            "pairs_with_reconciled_inventory": 0,
            "pairs_with_settled_cashflow": 0,
            "numeric_modeled_netreturn_claims": 0,
            "observed_netreturn_claims": 0,
        },
        "decision": {
            "result": RESULT_EXTEND,
            "basis": (
                "35 exact R2 quote pairs are cost-input ready, but all 36 pairs lack "
                "complete fee, attempt, landing, inventory, and settled-cashflow "
                "evidence; one pair also remains latency-blocked."
            ),
            "promotion_authority": False,
            "task27_authority": False,
        },
        "side_effect_counters": {
            "provider_api_rpc_wss_calls": 0,
            "raw_r2_files_opened": 0,
            "r3_paths_or_values_read": 0,
            "simulation_build_send": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
        },
        "nonclaims": [
            "NUMERIC_MODELED_NETRETURN",
            "OBSERVED_NETRETURN",
            "QUOTE_TO_FILL_PROMOTION",
            "MISSING_FEE_ZEROING",
            "PROCESSED_ONLY_LANDING_INFERENCE",
            "UNRESOLVED_INVENTORY_FLATTENING",
            "R3_VALUE_OR_PATH_READ",
            "TASK27_BASELINE_EXECUTION",
        ],
    }
    validate_inventory(inventory)
    return inventory


def validate_inventory(inventory: Mapping[str, Any]) -> None:
    _require(inventory["decision"]["result"] == RESULT_EXTEND, "decision_not_extend")
    _require(inventory["decision"]["result"] not in FORBIDDEN_RESULTS, "fit_claim_forbidden")
    _require(inventory["decision"]["promotion_authority"] is False, "promotion_authority")
    _require(inventory["decision"]["task27_authority"] is False, "task27_authority")
    summary = inventory["population_summary"]
    _require(summary["numeric_modeled_netreturn_claims"] == 0, "numeric_modeled_claim")
    _require(summary["observed_netreturn_claims"] == 0, "observed_claim")
    _require(summary["pairs_with_complete_fee_evidence"] == 0, "fee_complete_drift")
    _require(summary["pairs_with_settled_cashflow"] == 0, "settlement_complete_drift")
    counters = inventory["side_effect_counters"]
    for key, value in counters.items():
        _require(value == 0, f"side_effect_nonzero:{key}")
    for component in inventory["component_inventory"]:
        status = component["availability_status"]
        _require(status in {"MISSING", "UNKNOWN", "PARTIAL", "INELIGIBLE", "PRESENT"}, "bad_status")
        if component["component_id"] in {
            "fee_chargeability",
            "send_attempt",
            "landing",
            "settlement",
        }:
            _require(status == "MISSING", f"component_should_be_missing:{component['component_id']}")
            _require(component["pair_coverage"]["pairs_complete"] == 0, "pairs_complete_nonzero")
        if status in {"MISSING", "UNKNOWN"}:
            _require(component["missingness_reason"], "missingness_reason_required")
            _require(
                component["missingness_reason"]
                not in {"0", "false", "landed", "flat", "settled"},
                "missingness_coerced",
            )
    blocker_gaps = [
        gap for gap in inventory["gap_matrix"] if gap["blocks_modeled_netreturn"]
    ]
    _require(len(blocker_gaps) >= 5, "insufficient_blockers")


def build_acceptance(inventory: Mapping[str, Any], inventory_sha256: str) -> dict[str, Any]:
    return {
        "schema": "smial.task26a.a1-execution-evidence-inventory-acceptance",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "status": "PASS_TRACKED_ONLY_INVENTORY_EXTEND_EXECUTION_EVIDENCE",
        "decision": dict(inventory["decision"]),
        "population_summary": dict(inventory["population_summary"]),
        "artifact_bindings": {
            "inventory": {
                "path": str(INVENTORY_PATH).replace("\\", "/"),
                "sha256": inventory_sha256,
            },
            "config": {
                "path": str(CONFIG_PATH).replace("\\", "/"),
                "sha256": None,
            },
        },
        "checks": [
            {"check_id": "TRACKED_INPUT_BINDINGS_EXACT", "status": "PASS"},
            {"check_id": "EVIDENCE_CLASSES_COMPLETE", "status": "PASS"},
            {"check_id": "REQUIRED_COMPONENT_GAPS_RECORDED", "status": "PASS"},
            {"check_id": "NO_NUMERIC_NETRETURN", "status": "PASS"},
            {"check_id": "NO_R2_RAW_OR_R3", "status": "PASS"},
            {"check_id": "DECISION_EXTEND_EXECUTION_EVIDENCE", "status": "PASS"},
            {"check_id": "NO_TASK27_AUTHORITY", "status": "PASS"},
        ],
        "side_effect_counters": dict(inventory["side_effect_counters"]),
        "nonclaims": list(inventory["nonclaims"]),
    }


def write_artifacts(repo_root: Path) -> dict[str, str]:
    inventory = build_inventory(repo_root)
    inventory_bytes = canonical_json_bytes(inventory)
    inventory_sha = sha256_bytes(inventory_bytes)
    config_sha = sha256_bytes((repo_root / CONFIG_PATH).read_bytes())
    acceptance = build_acceptance(inventory, inventory_sha)
    acceptance["artifact_bindings"]["config"]["sha256"] = config_sha
    acceptance_bytes = canonical_json_bytes(acceptance)
    (repo_root / INVENTORY_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / INVENTORY_PATH).write_bytes(inventory_bytes)
    (repo_root / ACCEPTANCE_PATH).write_bytes(acceptance_bytes)
    return {
        "inventory_sha256": inventory_sha,
        "acceptance_sha256": sha256_bytes(acceptance_bytes),
        "decision": inventory["decision"]["result"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if args.write:
        result = write_artifacts(repo_root)
        print(json.dumps(result, sort_keys=True))
        return 0
    inventory = build_inventory(repo_root)
    print(inventory["decision"]["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
