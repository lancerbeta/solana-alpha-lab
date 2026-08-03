"""TASK-26 A6 adversarial acceptance over the frozen A5 R2 aggregate projection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


TASK_ID = "TASK-26"
ATOM_ID = "T26-A6_ADVERSARIAL_R2_EXECUTION_COST_ACCEPTANCE_AND_OWNER_DECISION_V1"
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26/"
    "a6_r2_adversarial_execution_cost_acceptance_v1.json"
)

FROZEN_INPUTS = {
    "a5_projection": {
        "path": "docs/evidence/task26/a5_bounded_r2_execution_cost_projection_v1.json",
        "sha256": "670d1b280aacdca0ef4db1994ff9bc535a8f640c4db2e688a4322ee9807b0b37",
    },
    "a5_acceptance": {
        "path": "docs/evidence/task26/a5_bounded_r2_execution_cost_projection_acceptance_v1.json",
        "sha256": "f14d2655b281fd2b1eb02adfc843bff2578632580109fe516b7f5fc88fa646b9",
    },
    "adversarial_fixture": {
        "path": "tests/fixtures/task26/r2_execution_cost_adversarial_matrix_v1.json",
        "sha256": "51f1664438eb17c3a2052d803ecd6a18eca059ef9637a73f1996e6ac22e9225e",
    },
}

EXPECTED_READY_PAIR_COUNT = 35
EXPECTED_BLOCKED_PAIR_ID = "T25-R2-PAIR-1afd5c77ae7cfe7c5287cf66"
EXPECTED_RECORDS_COMMITMENT = "d89dce360746d4cacb8b6336598142f3aa3e106dc4d57ca6abda453d3e99aab2"


class Task26R2AdversarialAcceptanceError(ValueError):
    """Raised when frozen A5 R2 evidence drifts or a false-positive is accepted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26R2AdversarialAcceptanceError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_bound_bytes(repo_root: Path, role: str, binding: Mapping[str, str]) -> bytes:
    root = repo_root.resolve()
    path = (root / binding["path"]).resolve()
    _require(path.is_relative_to(root), f"path_escape:{role}")
    _require(path.is_file() and not path.is_symlink(), f"input_missing:{role}")
    payload = path.read_bytes()
    _require(sha256_bytes(payload) == binding["sha256"], f"input_hash_drift:{role}")
    return payload


def _load_frozen_context(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = {
        role: _read_bound_bytes(repo_root, role, binding)
        for role, binding in FROZEN_INPUTS.items()
    }
    try:
        projection = json.loads(payloads["a5_projection"])
        acceptance = json.loads(payloads["a5_acceptance"])
        fixture = json.loads(payloads["adversarial_fixture"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task26R2AdversarialAcceptanceError("frozen_json_invalid") from exc
    _require(isinstance(projection, dict), "a5_projection_not_mapping")
    _require(isinstance(acceptance, dict), "a5_acceptance_not_mapping")
    _require(isinstance(fixture, dict), "adversarial_fixture_not_mapping")
    _require(
        acceptance.get("status")
        == "PASS_BOUNDED_R2_QUOTE_EXECUTION_COST_INPUT_SURFACE_WITH_LIMITATIONS",
        "a5_acceptance_status_drift",
    )
    _require(fixture.get("fixture_kind") == "SYNTHETIC_ADVERSARIAL_MUTATIONS_ONLY", "fixture_kind_drift")
    return projection, fixture


def _apply_json_pointer(payload: dict[str, Any], pointer: str, replacement: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]
    target: Any = payload
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final_part = parts[-1]
    if isinstance(target, list):
        target[int(final_part)] = replacement
    else:
        target[final_part] = replacement


def validate_projection(projection: Mapping[str, Any]) -> None:
    """Reject semantic inflation and evidence-boundary leaks in the A5 output."""

    _require(
        projection.get("atom_id") == "T26-A5_BOUNDED_R2_QUOTE_EVIDENCE_PROJECTION_V1",
        "a5_atom_id_drift",
    )
    _require(
        projection.get("status")
        == "PASS_BOUNDED_R2_QUOTE_EXECUTION_COST_INPUT_SURFACE_WITH_LIMITATIONS",
        "a5_projection_status_drift",
    )

    truth_boundary = projection["truth_boundary"]
    _require(
        truth_boundary["quote_truth"] == "POINT_IN_TIME_QUOTE_ONLY",
        "quote_truth_not_point_in_time_only",
    )
    _require(
        truth_boundary["actual_fill_or_settlement_observed"] is False,
        "actual_fill_or_settlement_claim_forbidden",
    )

    net_return = projection["net_return_surface"]
    _require(
        net_return["classification"] == "NOT_COMPUTABLE",
        "netreturn_classification_not_computable",
    )
    _require(
        net_return["amount_atomic"] is None and net_return["currency"] is None,
        "numeric_netreturn_forbidden",
    )
    _require(
        net_return["reason"] == "R2_NO_COMPLETE_FEE_OR_SETTLED_CASHFLOW",
        "netreturn_limitation_reason_drift",
    )
    _require(net_return["records_covered"] == 36, "netreturn_coverage_drift")

    summary = projection["summary"]
    _require(summary["pairs_input"] == 36 and summary["pairs_output"] == 36, "pair_count_drift")
    _require(summary["records_dropped"] == 0, "records_dropped_forbidden")
    states = summary["execution_cost_input_states"]
    _require(states.get("NOT_COMPUTABLE") == 1, "not_computable_count_invalid")
    _require(states.get("QUOTE_COST_INPUT_READY") == EXPECTED_READY_PAIR_COUNT, "ready_pair_count_invalid")
    _require(
        states == {"NOT_COMPUTABLE": 1, "QUOTE_COST_INPUT_READY": EXPECTED_READY_PAIR_COUNT},
        "execution_cost_state_surface_drift",
    )
    _require(summary["numeric_netreturn_claims"] == 0, "numeric_netreturn_claim_count_forbidden")
    _require(summary["actual_fill_or_settlement_claims"] == 0, "actual_fill_or_settlement_claim_count_forbidden")
    _require(summary["r2_raw_files_opened"] == 0, "r2_raw_files_opened_forbidden")
    _require(summary["r3_paths_or_values_read"] == 0, "r3_paths_or_values_read_forbidden")
    _require(summary["provider_api_rpc_wss_calls"] == 0, "provider_calls_forbidden")
    _require(summary["wallet_signer_transaction_actions"] == 0, "wallet_actions_forbidden")
    _require(summary["cash_spend_usd_cents"] == 0, "cash_spend_forbidden")

    next_boundary = projection["next_boundary"]
    _require(next_boundary["r3_access"] == "DENY", "r3_access_not_deny")
    _require(next_boundary["authorized_by_a5"] is False, "next_boundary_self_authorized")

    readiness = projection["pair_readiness"]
    _require(
        readiness["projection_records_sha256"] == EXPECTED_RECORDS_COMMITMENT,
        "projection_records_commitment_drift",
    )
    ready_pair_ids = readiness["quote_cost_input_ready_pair_ids"]
    _require(len(ready_pair_ids) == EXPECTED_READY_PAIR_COUNT, "ready_pair_count_invalid")
    _require(len(set(ready_pair_ids)) == len(ready_pair_ids), "ready_pair_id_duplicate")
    _require(EXPECTED_BLOCKED_PAIR_ID not in ready_pair_ids, "blocked_pair_marked_ready")

    blocked_pairs = readiness["not_computable_pairs"]
    _require(len(blocked_pairs) == 1, "not_computable_pair_count_invalid")
    blocked = blocked_pairs[0]
    _require(blocked["pair_id"] == EXPECTED_BLOCKED_PAIR_ID, "latency_blocked_pair_identity_drift")
    _require(
        blocked["blocked_reason"] == "ENTRY_PROVIDER_LATENCY_LIMIT_EXCEEDED",
        "latency_blocker_missing",
    )
    _require(
        blocked["entry_assessment_reason"] == "PROVIDER_LATENCY_LIMIT_EXCEEDED",
        "latency_assessment_reason_drift",
    )


def run_adversarial_cases(repo_root: Path) -> list[dict[str, str]]:
    """Reject all frozen false-positive mutations with their exact declared code."""

    projection, fixture = _load_frozen_context(repo_root)
    mutations = fixture["mutations"]
    _require(len(mutations) == 12, "adversarial_mutation_count_drift")
    validate_projection(projection)

    outcomes: list[dict[str, str]] = []
    for mutation in mutations:
        mutation_id = mutation["mutation_id"]
        changed = copy.deepcopy(projection)
        _apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
        try:
            validate_projection(changed)
        except Task26R2AdversarialAcceptanceError as exc:
            actual_error = str(exc).upper()
        else:
            actual_error = "NO_REJECTION"
        expected_error = mutation["expected_error"]
        _require(
            actual_error == expected_error,
            f"mutation_rejection_mismatch:{mutation_id}:{actual_error}",
        )
        outcomes.append(
            {
                "expected_error": expected_error,
                "mutation_id": mutation_id,
                "status": "PASS_EXACT_REJECTION",
            }
        )
    return outcomes


def _code_binding(repo_root: Path, relative_path: str) -> dict[str, Any]:
    root = repo_root.resolve()
    path = (root / relative_path).resolve()
    _require(path.is_relative_to(root), f"code_path_escape:{relative_path}")
    _require(path.is_file() and not path.is_symlink(), f"code_missing:{relative_path}")
    payload = path.read_bytes()
    return {"bytes": len(payload), "path": relative_path, "sha256": sha256_bytes(payload)}


def build_acceptance(repo_root: Path) -> dict[str, Any]:
    """Build the local A6 receipt and the constrained owner decision."""

    projection, _ = _load_frozen_context(repo_root)
    outcomes = run_adversarial_cases(repo_root)
    summary = projection["summary"]
    checks = [
        ("A5_AND_MATRIX_BINDINGS_EXACT", True),
        ("FROZEN_MUTATIONS_12", len(outcomes) == 12),
        (
            "EVERY_MUTATION_REJECTED_EXACT",
            all(row["status"] == "PASS_EXACT_REJECTION" for row in outcomes),
        ),
        ("QUOTE_CANNOT_BECOME_FILL_OR_NETRETURN", True),
        (
            "R2_EXECUTION_EVIDENCE_LIMITATION_RETAINED",
            projection["net_return_surface"]["amount_atomic"] is None
            and projection["net_return_surface"]["reason"]
            == "R2_NO_COMPLETE_FEE_OR_SETTLED_CASHFLOW",
        ),
        (
            "ALL_PAIRS_RETAINED_WITH_LATENCY_BLOCKER",
            summary["pairs_input"] == 36
            and summary["pairs_output"] == 36
            and summary["records_dropped"] == 0
            and summary["execution_cost_input_states"]["NOT_COMPUTABLE"] == 1,
        ),
        (
            "R3_PROVIDER_WALLET_CASH_ZERO",
            all(
                summary[key] == 0
                for key in (
                    "r3_paths_or_values_read",
                    "provider_api_rpc_wss_calls",
                    "wallet_signer_transaction_actions",
                    "cash_spend_usd_cents",
                )
            ),
        ),
    ]
    failures = [check_id for check_id, passed in checks if not passed]
    _require(not failures, "acceptance_failed:" + ",".join(failures))

    return {
        "adversarial_cases": outcomes,
        "as_of": "2026-08-03",
        "atom_id": ATOM_ID,
        "checks": [{"check_id": check_id, "status": "PASS"} for check_id, _ in checks],
        "code_bindings": {
            "a6_module": _code_binding(repo_root, "src/solana_alpha_lab/task26_r2_adversarial_acceptance.py"),
            "a6_test": _code_binding(repo_root, "tests/test_task26_r2_execution_cost_adversarial_acceptance.py"),
        },
        "frozen_input_bindings": FROZEN_INPUTS,
        "measured_boundary": {
            "a5_projection_files_read": 1,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "holdout_consumption_records_added": 0,
            "provider_api_rpc_wss_calls": 0,
            "r2_raw_files_opened": 0,
            "r2_surface_files_read_directly": 0,
            "r3_paths_or_values_read": 0,
            "synthetic_mutations_evaluated": len(outcomes),
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": {
            "atom": "T26-A7_REGISTER_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1",
            "authorized_by_a6": False,
            "r3_access": "DENY",
        },
        "owner_decision": {
            "decision": "EXTEND_EXECUTION_EVIDENCE",
            "decision_basis": "35 exact R2 quote pairs are cost-input ready, but all 36 pairs lack complete fee or settled-cashflow evidence and one pair remains latency-blocked.",
            "does_not_require_or_authorize": [
                "R3 read",
                "provider calls",
                "wallet, signing, or execution",
            ],
            "minimum_required_evidence": [
                "versioned fee components with units, source, timing, and normalization",
                "attempt or landing evidence with inventory reconciliation",
                "complete modeled-cost parameterization before any modeled numeric NetReturn",
            ],
        },
        "schema": "smial.task26.a6-r2-adversarial-execution-cost-acceptance",
        "schema_version": "1.0",
        "status": "PASS_R2_EXECUTION_COST_ADVERSARIAL_ACCEPTANCE_EXTEND_EVIDENCE",
        "task_id": TASK_ID,
        "validation": {
            "full_validation": "DEFERRED_TO_DELIVERY_GATE",
            "status": "PASS",
            "targeted_command": "uv run --locked --managed-python python -B -m unittest tests.test_task26_r2_execution_cost_adversarial_acceptance",
        },
    }


def check_stored_output(repo_root: Path) -> str:
    expected = canonical_json_bytes(build_acceptance(repo_root))
    path = repo_root.resolve() / ACCEPTANCE_PATH
    _require(path.is_file() and not path.is_symlink(), "stored_acceptance_missing")
    _require(path.read_bytes() == expected, "stored_acceptance_drift")
    return sha256_bytes(expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", choices=("acceptance", "check"), required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if args.artifact == "acceptance":
        print(canonical_json_bytes(build_acceptance(repo_root)).decode("utf-8"), end="")
    else:
        print(json.dumps({ACCEPTANCE_PATH.as_posix(): check_stored_output(repo_root)}, sort_keys=True))


if __name__ == "__main__":
    main()
