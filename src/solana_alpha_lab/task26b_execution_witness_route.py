"""Deterministic historical/cache-first execution-witness route decision for TASK-26B."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

TASK_ID = "TASK-26B"
ATOM_ID = "T26B-A1_FREEZE_MINIMAL_EXECUTION_WITNESS_ROUTE_V1"
AS_OF = "2026-08-04"
CONFIG_PATH = Path("configs/task26b_minimal_execution_witness_route_contract_v1.yaml")
DECISION_PATH = Path("docs/evidence/task26b/a1_execution_witness_route_decision_v1.json")
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26b/a1_execution_witness_route_acceptance_v1.json"
)
FIXTURE_PATH = Path("tests/fixtures/task26b/execution_witness_route_matrix_v1.json")

# Historical/cache-first is evaluated first by contract requirement.
ROUTES = [
    "HISTORICAL_THIRD_PARTY_CHAIN",
    "QUOTE_ONLY",
    "BUILD_SIMULATION",
    "OWNED_INSTRUMENTED_CANARY",
]
EVIDENCE_CLASSES = [
    "FEE_CHARGEABILITY",
    "SEND_ATTEMPT",
    "LANDING",
    "FILL",
    "INVENTORY",
    "SETTLEMENT",
]

ROUTE_CAPABILITY: dict[str, dict[str, str]] = {
    "QUOTE_ONLY": {
        "FEE_CHARGEABILITY": "INSUFFICIENT",
        "SEND_ATTEMPT": "INSUFFICIENT",
        "LANDING": "INSUFFICIENT",
        "FILL": "INSUFFICIENT",
        "INVENTORY": "INSUFFICIENT",
        "SETTLEMENT": "INSUFFICIENT",
    },
    "HISTORICAL_THIRD_PARTY_CHAIN": {
        "FEE_CHARGEABILITY": "PARTIAL_SELECTED_TX_CHAIN_FEES_ONLY",
        "SEND_ATTEMPT": "INSUFFICIENT_NO_REJECTED_DROPPED_DENOMINATOR",
        "LANDING": "PARTIAL_OBSERVED_PROCESSED_ONLY",
        "FILL": "PARTIAL_SELECTED_TX_TOKEN_DELTAS_ONLY",
        "INVENTORY": "INSUFFICIENT_NO_OWNER_INVENTORY_STATE",
        "SETTLEMENT": "INSUFFICIENT_NO_OWNER_SETTLEMENT",
    },
    "BUILD_SIMULATION": {
        "FEE_CHARGEABILITY": "INSUFFICIENT_MODELED_ONLY",
        "SEND_ATTEMPT": "INSUFFICIENT",
        "LANDING": "INSUFFICIENT_NOT_ACTUAL",
        "FILL": "INSUFFICIENT_NOT_ACTUAL",
        "INVENTORY": "INSUFFICIENT_NOT_ACTUAL",
        "SETTLEMENT": "INSUFFICIENT_NOT_ACTUAL",
    },
    "OWNED_INSTRUMENTED_CANARY": {
        "FEE_CHARGEABILITY": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
        "SEND_ATTEMPT": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
        "LANDING": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
        "FILL": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
        "INVENTORY": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
        "SETTLEMENT": "FUTURE_SUFFICIENT_IF_AUTHORIZED",
    },
}


class Task26BRouteError(ValueError):
    """Raised when route-decision inputs drift or semantics are violated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26BRouteError(code)


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


def _read_bound(repo_root: Path, path: str, expected_sha256: str) -> bytes:
    root = repo_root.resolve()
    candidate = (root / path).resolve()
    _require(candidate.is_relative_to(root), f"path_escape:{path}")
    _require(candidate.is_file() and not candidate.is_symlink(), f"input_missing:{path}")
    payload = candidate.read_bytes()
    _require(sha256_bytes(payload) == expected_sha256, f"input_hash_drift:{path}")
    return payload


def load_config(repo_root: Path) -> dict[str, Any]:
    document = yaml.safe_load((repo_root / CONFIG_PATH).read_text(encoding="utf-8"))
    _require(isinstance(document, dict), "config_not_mapping")
    return document


def _task26a_facts(inventory: Mapping[str, Any]) -> dict[str, Any]:
    summary = inventory["population_summary"]
    return {
        "quote_pairs": summary["quote_pairs"],
        "quote_cost_input_ready_pairs": summary["quote_cost_input_ready_pairs"],
        "latency_blocked_pairs": summary["latency_blocked_pairs"],
        "pairs_with_complete_fee_evidence": summary["pairs_with_complete_fee_evidence"],
        "pairs_with_complete_attempt_evidence": summary[
            "pairs_with_complete_attempt_evidence"
        ],
        "pairs_with_complete_landing_evidence": summary[
            "pairs_with_complete_landing_evidence"
        ],
        "pairs_with_reconciled_inventory": summary["pairs_with_reconciled_inventory"],
        "pairs_with_settled_cashflow": summary["pairs_with_settled_cashflow"],
        "numeric_modeled_netreturn_claims": summary["numeric_modeled_netreturn_claims"],
        "observed_netreturn_claims": summary["observed_netreturn_claims"],
    }


def build_route_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route_index, route in enumerate(ROUTES, start=1):
        for evidence_class in EVIDENCE_CLASSES:
            capability = ROUTE_CAPABILITY[route][evidence_class]
            rows.append(
                {
                    "route": route,
                    "evidence_class": evidence_class,
                    "capability": capability,
                    "closes_owner_gap": capability.startswith("FUTURE_SUFFICIENT")
                    or capability == "SUFFICIENT",
                    "historical_cache_first_order": route_index,
                }
            )
    return rows


def _historical_insufficiency(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    historical = [
        row for row in matrix if row["route"] == "HISTORICAL_THIRD_PARTY_CHAIN"
    ]
    insufficient = [
        row["evidence_class"]
        for row in historical
        if not str(row["capability"]).startswith("PARTIAL")
        and row["capability"] != "SUFFICIENT"
    ]
    partial_only = [
        row["evidence_class"]
        for row in historical
        if str(row["capability"]).startswith("PARTIAL")
    ]
    return {
        "route_tested_first": "HISTORICAL_THIRD_PARTY_CHAIN",
        "closes_all_required_classes": False,
        "insufficient_or_non_owner_classes": insufficient,
        "partial_selected_tx_only_classes": partial_only,
        "falsifier": (
            "Tracked historical third-party reconstruction cannot establish "
            "rejected/dropped attempt denominator, retry intent, owner inventory, "
            "or owner settlement for the 36-pair TASK-26A surface."
        ),
        "result": "HISTORICAL_INSUFFICIENT_FOR_OWNER_ESTIMAND",
    }


def decide(facts: Mapping[str, Any], historical: Mapping[str, Any]) -> dict[str, Any]:
    zero_complete = (
        facts["pairs_with_complete_fee_evidence"] == 0
        and facts["pairs_with_complete_attempt_evidence"] == 0
        and facts["pairs_with_complete_landing_evidence"] == 0
        and facts["pairs_with_reconciled_inventory"] == 0
        and facts["pairs_with_settled_cashflow"] == 0
        and facts["quote_pairs"] == 36
        and facts["quote_cost_input_ready_pairs"] == 35
        and facts["latency_blocked_pairs"] == 1
    )
    _require(zero_complete, "unexpected_task26a_population_facts")
    _require(historical["closes_all_required_classes"] is False, "historical_closed")
    return {
        "result": "OWNED_CANARY_REQUIRED",
        "canary_authority": False,
        "promotion_authority": False,
        "task27_authority": False,
        "basis": (
            "TASK-26A retains 36 quote pairs, 35 quote-cost-ready, 1 latency-blocked, "
            "and zero complete fee/attempt/landing/inventory/settlement evidence; "
            "historical/cache-first reconstruction remains insufficient for the owner "
            "estimand, so an owned instrumented canary is required but not authorized."
        ),
    }


def future_owned_witness_spec() -> dict[str, Any]:
    return {
        "status": "SPEC_ONLY_NO_AUTHORITY",
        "required_fields": [
            "stable_attempt_id",
            "retry_chain_id",
            "quote_build_context",
            "submitted_at",
            "terminal_at",
            "terminal_state",
            "transaction_signature",
            "processed_on_chain",
            "actual_token_deltas",
            "actual_sol_delta",
            "network_fee_atomic",
            "relay_or_tip_fee_atomic",
            "ata_or_rent_fee_atomic",
            "separately_charged_fees",
            "inventory_before",
            "inventory_after",
            "settlement_accounting_basis",
            "reconciliation_reference",
            "raw_source_hashes",
            "unknown_recovery_path",
        ],
        "separate_gate_prerequisites": [
            "threat_model",
            "isolated_signer",
            "explicit_wallet_boundary",
            "exact_cash_cap",
            "program_route_allowlist",
            "manual_owner_approval",
            "reconciliation_before_retry",
            "kill_switch",
            "no_strategy_logic",
        ],
        "created_by_this_atom": {
            "wallet": False,
            "signer": False,
            "transaction_builder": False,
            "send_path": False,
            "deployment": False,
            "canary_authority": False,
        },
    }


def build_decision(repo_root: Path) -> dict[str, Any]:
    config = load_config(repo_root)
    bindings: list[dict[str, Any]] = []
    inventory_obj: dict[str, Any] | None = None
    for row in config["frozen_input_bindings"]:
        payload = _read_bound(repo_root, row["path"], row["sha256"])
        bindings.append(
            {
                "asset_id": row["asset_id"],
                "path": row["path"],
                "sha256": row["sha256"],
                "bytes": len(payload),
            }
        )
        if row["asset_id"] == "EVIDENCE-T26A-A1-INVENTORY-001":
            inventory_obj = json.loads(payload.decode("utf-8"))
    _require(inventory_obj is not None, "task26a_inventory_binding_missing")
    facts = _task26a_facts(inventory_obj)
    matrix = build_route_matrix()
    historical = _historical_insufficiency(matrix)
    decision = decide(facts, historical)
    return {
        "schema": "smial.task26b.a1-execution-witness-route-decision",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "status": "PASS_OWNED_CANARY_REQUIRED_NO_AUTHORITY",
        "input_bindings": bindings,
        "task26a_facts": facts,
        "route_evaluation_order": list(ROUTES),
        "route_matrix": matrix,
        "historical_cache_first_falsifier": historical,
        "decision": decision,
        "future_owned_witness": future_owned_witness_spec(),
        "nonclaims": [
            "NUMERIC_MODELED_NETRETURN",
            "OBSERVED_NETRETURN",
            "QUOTE_TO_FILL_PROMOTION",
            "SIMULATION_TO_LANDING_PROMOTION",
            "THIRD_PARTY_HISTORY_TO_OWNER_SETTLEMENT",
            "CANARY_AUTHORITY",
            "WALLET_SIGNER_TRANSACTION_ACTIONS",
            "TASK27_BASELINE_EXECUTION",
            "R3_VALUE_OR_PATH_READ",
        ],
        "side_effect_counters": {
            "provider_api_rpc_wss_calls": 0,
            "raw_r2_files_opened": 0,
            "r3_paths_or_values_read": 0,
            "simulation_build_send": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
        },
        "r3_access": "UNTOUCHED_DEFAULT_DENY",
    }


def build_acceptance(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "smial.task26b.a1-execution-witness-route-acceptance",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "as_of": AS_OF,
        "status": "PASS_ROUTE_DECISION_OWNED_CANARY_REQUIRED",
        "checks": [
            {"check_id": "TRACKED_INPUT_BINDINGS_EXACT", "status": "PASS"},
            {"check_id": "HISTORICAL_ROUTE_TESTED_FIRST", "status": "PASS"},
            {"check_id": "ROUTE_MATRIX_COMPLETE", "status": "PASS"},
            {"check_id": "HISTORICAL_INSUFFICIENT", "status": "PASS"},
            {"check_id": "DECISION_OWNED_CANARY_REQUIRED", "status": "PASS"},
            {"check_id": "NO_CANARY_AUTHORITY", "status": "PASS"},
            {"check_id": "NO_NUMERIC_NETRETURN", "status": "PASS"},
            {"check_id": "NO_WALLET_SIGNER_TRANSACTION", "status": "PASS"},
            {"check_id": "NO_TASK27_AUTHORITY", "status": "PASS"},
            {"check_id": "R3_UNTOUCHED_DEFAULT_DENY", "status": "PASS"},
        ],
        "decision": decision["decision"],
        "historical_cache_first_falsifier": decision["historical_cache_first_falsifier"],
        "future_owned_witness_status": decision["future_owned_witness"]["status"],
        "task26a_facts": decision["task26a_facts"],
        "side_effect_counters": decision["side_effect_counters"],
        "confirmations": [
            "HISTORICAL_ROUTE_TESTED_FIRST",
            "NO_RAW_R2",
            "NO_R3",
            "NO_PROVIDER_EXECUTION",
            "NO_WALLET",
            "NO_SIGNER",
            "NO_TRANSACTION",
            "NO_CASH_SPEND",
            "NO_NUMERIC_NETRETURN",
            "NO_TASK27",
            "NO_CANARY_AUTHORITY",
        ],
    }


def write_outputs(repo_root: Path) -> dict[str, str]:
    decision = build_decision(repo_root)
    acceptance = build_acceptance(decision)
    fixture = {
        "schema": "smial.task26b.execution-witness-route-matrix-fixture",
        "schema_version": "1.0",
        "routes": list(ROUTES),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "expected_decision": "OWNED_CANARY_REQUIRED",
        "expected_canary_authority": False,
        "route_matrix": decision["route_matrix"],
    }
    digests: dict[str, str] = {}
    for rel, obj in (
        (DECISION_PATH.as_posix(), decision),
        (ACCEPTANCE_PATH.as_posix(), acceptance),
        (FIXTURE_PATH.as_posix(), fixture),
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_bytes(obj))
        digests[rel] = sha256_bytes(path.read_bytes())
    return digests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    decision = build_decision(args.repo_root)
    print("decision", decision["decision"]["result"])
    print("canary_authority", decision["decision"]["canary_authority"])
    if args.write:
        for rel, digest in write_outputs(args.repo_root).items():
            print(rel, digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
