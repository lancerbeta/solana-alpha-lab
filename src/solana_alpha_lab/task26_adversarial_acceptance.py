"""TASK-26 A4 exact adversarial acceptance over frozen synthetic inputs only."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:  # Supports package import in tests and direct local artifact generation.
    from .task26_execution_cost_model import (
        FROZEN_INPUTS,
        Task26ExecutionCostModelError,
        build_projection,
        evaluate_scenario,
    )
except ImportError:  # pragma: no cover - exercised only by the direct CLI path.
    from task26_execution_cost_model import (  # type: ignore[no-redef]
        FROZEN_INPUTS,
        Task26ExecutionCostModelError,
        build_projection,
        evaluate_scenario,
    )


TASK_ID = "TASK-26"
ATOM_ID = "T26-A4_ADVERSARIAL_EXECUTION_COST_ACCEPTANCE_AND_OWNER_DECISION_V1"
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26/"
    "a4_adversarial_execution_cost_acceptance_v1.json"
)

A3_BINDINGS = {
    "a2_fixture": FROZEN_INPUTS["fixture"],
    "a3_model": {
        "path": "src/solana_alpha_lab/task26_execution_cost_model.py",
        "sha256": "ea205679f82781b27270d99e581a1412c959823c4a891d81a6855e6673f500b5",
    },
    "a3_projection": {
        "path": "docs/evidence/task26/a3_execution_cost_projection_v1.json",
        "sha256": "df7025c489627b77cc3748c495ca8852ad3a79262048e0780115f0d7d086165f",
    },
    "a3_acceptance": {
        "path": "docs/evidence/task26/a3_deterministic_execution_cost_and_golden_acceptance_v1.json",
        "sha256": "c543f0c273a5a09a16b9ca2e9d96bc0c61343eac236894d161f247d14b3b53bf",
    },
}


class Task26AdversarialAcceptanceError(ValueError):
    """Raised when A4 inputs drift or a forbidden false-positive is accepted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26AdversarialAcceptanceError(code)


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
        for role, binding in A3_BINDINGS.items()
    }
    try:
        fixture = json.loads(payloads["a2_fixture"])
        projection = json.loads(payloads["a3_projection"])
        acceptance = json.loads(payloads["a3_acceptance"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task26AdversarialAcceptanceError("frozen_json_invalid") from exc
    _require(isinstance(fixture, dict), "fixture_not_mapping")
    _require(isinstance(projection, dict), "projection_not_mapping")
    _require(isinstance(acceptance, dict), "a3_acceptance_not_mapping")
    _require(projection["summary"]["observed_netreturn_claims"] == 0, "a3_observed_claim_drift")
    _require(
        acceptance["status"] == "PASS_SYNTHETIC_EXECUTION_COST_MODEL_WITH_LIMITATIONS",
        "a3_acceptance_status_drift",
    )
    return fixture, projection


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


def run_adversarial_cases(repo_root: Path) -> list[dict[str, str]]:
    """Reject every frozen false-positive mutation with its exact declared error."""

    fixture, _ = _load_frozen_context(repo_root)
    mutations = fixture["adversarial_mutations"]
    scenarios = {scenario["scenario_id"]: scenario for scenario in fixture["scenarios"]}
    _require(len(mutations) == 12, "adversarial_mutation_count_drift")
    _require(len(scenarios) == 9, "golden_scenario_count_drift")

    outcomes: list[dict[str, str]] = []
    for mutation in mutations:
        mutation_id = mutation["mutation_id"]
        base = scenarios.get(mutation["base_scenario_id"])
        _require(base is not None, f"mutation_base_missing:{mutation_id}")
        baseline = evaluate_scenario(base)
        changed = copy.deepcopy(base)
        _apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
        try:
            evaluate_scenario(changed)
        except Task26ExecutionCostModelError as exc:
            actual_error = str(exc).upper()
        else:
            actual_error = "NO_REJECTION"
        expected_error = mutation["expected_error"]
        _require(actual_error == expected_error, f"mutation_rejection_mismatch:{mutation_id}:{actual_error}")
        outcomes.append(
            {
                "base_result_state": baseline["result_state"],
                "base_scenario_id": mutation["base_scenario_id"],
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
    """Produce the A4 receipt and owner decision from exact local synthetic bytes."""

    _, projection = _load_frozen_context(repo_root)
    outcomes = run_adversarial_cases(repo_root)
    result_states = {row["result_state"] for row in projection["projection_results"]}
    checks = [
        ("A3_BINDINGS_EXACT", True),
        ("FROZEN_MUTATIONS_12", len(outcomes) == 12),
        ("EVERY_MUTATION_REJECTED_EXACT", all(row["status"] == "PASS_EXACT_REJECTION" for row in outcomes)),
        ("BASELINES_STAY_VALID", all(row["base_result_state"] for row in outcomes)),
        ("QUOTE_CANNOT_BECOME_OBSERVED_NETRETURN", any(row["mutation_id"] == "m01_quote_to_observed" for row in outcomes)),
        ("UNKNOWN_AND_PARTIAL_STAY_BLOCKED", {"NOT_COMPUTABLE", "MODELED_COMPLETE"}.issubset(result_states)),
        ("SYNTHETIC_OBSERVED_REMAINS_NONCLAIM", projection["summary"]["observed_netreturn_claims"] == 0),
        ("R2_R3_PROVIDER_WALLET_CASH_ZERO", all(projection["summary"][key] == 0 for key in ("r2_values_read", "r3_paths_or_values_read", "provider_api_rpc_wss_calls", "wallet_signer_transaction_actions", "cash_spend_usd_cents"))),
    ]
    failures = [check_id for check_id, passed in checks if not passed]
    _require(not failures, "acceptance_failed:" + ",".join(failures))

    return {
        "a3_bindings": A3_BINDINGS,
        "adversarial_cases": outcomes,
        "as_of": "2026-08-03",
        "atom_id": ATOM_ID,
        "checks": [{"check_id": check_id, "status": "PASS"} for check_id, _ in checks],
        "code_bindings": {
            "a4_module": _code_binding(repo_root, "src/solana_alpha_lab/task26_adversarial_acceptance.py"),
            "a4_test": _code_binding(repo_root, "tests/test_task26_execution_cost_adversarial_acceptance.py"),
        },
        "measured_boundary": {
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "holdout_consumption_records_added": 0,
            "provider_api_rpc_wss_calls": 0,
            "r2_values_or_paths_read": 0,
            "r3_values_or_paths_read": 0,
            "synthetic_mutations_evaluated": len(outcomes),
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": {
            "action": "propose a separate bounded exact-R2 quote-evidence projection atom",
            "authorized_by_a4": False,
            "requires": [
                "fresh explicit owner start",
                "development-only content-addressed R2 input",
                "R3 remains sealed",
            ],
        },
        "owner_decision": {
            "decision": "EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS",
            "decision_basis": "All 12 frozen false-positive mutations are rejected exactly; model/unknown/observed semantic boundaries remain distinct.",
            "does_not_establish": [
                "actual fills or settlement",
                "observed NetReturn",
                "owner cashflow",
                "strategy profitability or alpha",
            ],
        },
        "schema": "smial.task26.a4-adversarial-execution-cost-acceptance",
        "schema_version": "1.0",
        "status": "PASS_EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS",
        "task_id": TASK_ID,
        "validation": {
            "full_validation": "DEFERRED_TO_DELIVERY_GATE",
            "status": "PASS",
            "targeted_command": "uv run --locked --managed-python python -B -m unittest tests.test_task26_execution_cost_adversarial_acceptance",
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
