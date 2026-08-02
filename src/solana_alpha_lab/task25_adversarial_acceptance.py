"""Adversarial acceptance and one owner decision for TASK-25 A5."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


TASK_ID = "TASK-25"
ATOM_ID = "T25-A5_ADVERSARIAL_ACCEPTANCE_AND_OWNER_DECISION_V1"
DECISION = "REDESIGN_TRACKED_R2_OUTCOME_SURFACE_BEFORE_OWNER_COMPARISON"
NEXT_ATOM = "T25-A5R1_EXACT_R2_OUTCOME_SURFACE_REPROJECTION_V1"
ACCEPTANCE_PATH = PurePosixPath(
    "docs/evidence/task25/a5_adversarial_acceptance_and_owner_decision_v1.json"
)

FROZEN_INPUTS = {
    "a4_projection": {
        "path": "docs/evidence/task25/a4_r2_outcome_projection_v1.json",
        "sha256": "59cbb0bdeea6a80d184ea3c3fdbb3827ff2b23951d2a93a483198374d85da075",
    },
    "a4_receipt": {
        "path": "docs/evidence/task25/a4_bounded_r2_outcome_projection_and_read_receipt_v1.json",
        "sha256": "ec2ef9425911e116271b94ee65371ef88bdf52db9e5ba732b6fe2ffc97a358df",
    },
    "a4_engine": {
        "path": "src/solana_alpha_lab/task25_r2_outcome_projection.py",
        "sha256": "6675b1670dada0864e8553212e86117332fd7d192d05793d86886410e25ff4b5",
    },
    "decision": {
        "path": "docs/decisions/task25_r2_outcome_owner_decision_v1.md",
        "sha256": "5a0da8e9ef69d0900b5edda876dfce929ea08b8064621741435707caf245f978",
    },
    "adversarial_matrix": {
        "path": "tests/fixtures/task25/a5_r2_outcome_adversarial_matrix_v1.json",
        "sha256": "c4963a351e407e74ac07d637831bfed3a33dc52233f65307f73f2424ee48e0a6",
    },
    "task23_projection_engine": {
        "path": "src/solana_alpha_lab/task23_diagnostic_projection.py",
        "sha256": "728fa77fc82a3e27245a908cfecc2a50e7df82c5813e6b90d4ad8ff0870e57f9",
    },
    "quote_contract_model": {
        "path": "src/solana_alpha_lab/contracts/schema_v1.py",
        "sha256": "ef9435fc0aa6df1d880714e97d3312e068dc82806a8c6ba1ed2d74c9929684ad",
    },
}

OUTCOME_FIELDS = {
    "record_id",
    "member_id",
    "panel_id",
    "tested_notional_usd",
    "label",
    "assessment",
    "evidence_basis",
    "claim_scope",
    "value_decimal",
    "unit",
    "route_state_observed",
    "fill_state",
    "cashflow_state",
    "path_state",
    "first_reliable_available_at",
    "source_scope",
    "source_content_sha256",
    "quality_flags",
    "observed_measures",
}

EXPECTED_LABELS = Counter(
    {
        "FILLABLE": 36,
        "QUOTE_EXIT": 36,
        "TOUCH": 9,
        "REALIZED_VWAP": 9,
        "NET": 9,
        "PATH_RISK": 9,
    }
)
EXPECTED_ASSESSMENTS = Counter({"UNKNOWN": 99, "SUPPORTED": 9})


class Task25AdversarialAcceptanceError(ValueError):
    """Raised when A4 evidence or the A5 decision violates its frozen boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task25AdversarialAcceptanceError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _safe_path(repo_root: Path, relative: str | PurePosixPath) -> Path:
    rel = PurePosixPath(str(relative))
    _require(not rel.is_absolute(), "absolute_path_forbidden")
    root = repo_root.resolve()
    candidate = (root / rel).resolve()
    _require(candidate.is_relative_to(root), "path_outside_repository")
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Task25AdversarialAcceptanceError(f"json_unreadable:{path.name}") from exc
    _require(isinstance(value, dict), f"json_root_invalid:{path.name}")
    return value


def load_frozen_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    for role, binding in FROZEN_INPUTS.items():
        path = _safe_path(repo_root, binding["path"])
        _require(path.is_file(), f"frozen_input_missing:{role}")
        _require(sha256_file(path) == binding["sha256"], f"frozen_input_hash_drift:{role}")
    projection = _load_json(_safe_path(repo_root, FROZEN_INPUTS["a4_projection"]["path"]))
    matrix = _load_json(_safe_path(repo_root, FROZEN_INPUTS["adversarial_matrix"]["path"]))
    return projection, matrix


def validate_owner_decision(repo_root: Path) -> None:
    path = _safe_path(repo_root, FROZEN_INPUTS["decision"]["path"])
    text = path.read_text(encoding="utf-8")
    decision_lines = [line for line in text.splitlines() if line.startswith("- Decision: ")]
    _require(decision_lines == [f"- Decision: `{DECISION}`"], "owner_decision_not_exactly_one")
    required = (
        "This is a redesign of the tracked derivation surface, not a request for new collection.",
        "R3 authority: `DENY`",
        NEXT_ATOM,
        "It is not authorized by this decision.",
        "STOP_R2_OUTCOME_ROUTE_AS_NOT_DECISION_GRADE",
    )
    for marker in required:
        _require(marker in text, f"decision_marker_missing:{marker}")


def validate_upstream_field_capability(repo_root: Path) -> list[str]:
    parser_text = _safe_path(
        repo_root, FROZEN_INPUTS["task23_projection_engine"]["path"]
    ).read_text(encoding="utf-8")
    model_text = _safe_path(
        repo_root, FROZEN_INPUTS["quote_contract_model"]["path"]
    ).read_text(encoding="utf-8")
    parser_markers = (
        'response["inputMint"] != quote.input_mint',
        'response["outputMint"] != quote.output_mint',
        'int(response["inAmount"]) != quote.input_requested_atomic',
        'int(response["outAmount"]) != quote.output_quoted_atomic',
        "buy.output_quoted_atomic == quote.input_requested_atomic",
        "buy.output_mint == quote.input_mint",
        "buy.input_mint == quote.output_mint",
    )
    model_fields = (
        "quote_attempt_id: str",
        "input_mint: str",
        "input_requested_atomic: NonNegativeInt",
        "output_mint: str",
        "output_quoted_atomic: NonNegativeInt | None",
        "requested_at: AwareDatetime",
        "response_at: AwareDatetime | None",
        "available_to_strategy_at: AwareDatetime",
        "ingested_at: AwareDatetime",
        "first_reliable_available_at: AwareDatetime",
        "quote_age_ms: NonNegativeInt | None",
        "provider_latency_ms: NonNegativeInt | None",
    )
    for marker in parser_markers:
        _require(marker in parser_text, f"upstream_parser_capability_missing:{marker}")
    for marker in model_fields:
        _require(marker in model_text, f"upstream_model_capability_missing:{marker}")
    return [
        "EXACT_MINT_AND_ATOMIC_AMOUNT_VALIDATION_PRESENT",
        "EXACT_BUY_TO_DEPENDENT_SELL_LINK_VALIDATION_PRESENT",
        "QUOTE_ID_FRESHNESS_LATENCY_AND_PIT_FIELDS_PRESENT",
    ]


def _decimal_nonnegative(value: Any, code: str) -> None:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise Task25AdversarialAcceptanceError(code) from exc
    _require(parsed.is_finite() and parsed >= 0, code)


def validate_projection(projection: Mapping[str, Any]) -> None:
    _require(projection.get("schema") == "smial.task25.r2-outcome-projection", "projection_schema_drift")
    _require(projection.get("task_id") == TASK_ID, "projection_task_drift")
    dataset = projection.get("dataset_identity", {})
    _require(
        dataset.get("panel_semantics")
        == "ACTUAL_SPARSE_OBSERVATION_TIMES_NOT_EXACT_NOMINAL_HORIZONS",
        "nominal_horizon_claim_forbidden",
    )
    summary = projection.get("summary", {})
    _require(summary.get("r3_paths_or_values_read") == 0, "r3_access_forbidden")
    _require(summary.get("raw_r2_value_files_reopened") == 0, "a5_raw_r2_reopen_forbidden")

    outcomes = projection.get("outcomes")
    _require(isinstance(outcomes, list) and len(outcomes) == 108, "outcome_denominator_drift")
    ids = [row.get("record_id") for row in outcomes]
    _require(len(ids) == len(set(ids)), "duplicate_outcome_record_id")
    labels = Counter(row.get("label") for row in outcomes)
    _require(labels == EXPECTED_LABELS, "outcome_label_denominator_drift")

    for row in outcomes:
        _require(set(row) == OUTCOME_FIELDS, "outcome_field_set_drift")
        assessment = row["assessment"]
        label = row["label"]
        if assessment == "UNKNOWN":
            _require(
                row["value_decimal"] is None and row["unit"] is None,
                "unknown_coerced_to_value",
            )

        if label in {"FILLABLE", "QUOTE_EXIT"}:
            _require(
                not (
                    row["fill_state"] == "ACTUAL_FILLS_RECONCILED"
                    or row["cashflow_state"] == "SETTLED_COMPLETE"
                ),
                "quote_promoted_to_fill_or_settlement",
            )
            if row["route_state_observed"] in {
                "PROVIDER_ERROR",
                "INVALID_RESPONSE",
                "TIMEOUT",
            }:
                _require(assessment != "REFUTED", "provider_error_not_no_route")
            if label == "FILLABLE":
                _require(assessment != "SUPPORTED", "fillable_exact_identity_missing")
                _require(
                    "EXACT_OUTPUT_MINT_AND_FRESHNESS_BLOCK_NOT_RETAINED"
                    in row["quality_flags"],
                    "fillable_loss_flag_missing",
                )
            else:
                _require(assessment != "SUPPORTED", "quote_exit_exact_inventory_missing")
                _require(
                    "EXACT_SELL_INVENTORY_ATOMIC_IDENTITY_NOT_RETAINED"
                    in row["quality_flags"],
                    "quote_exit_loss_flag_missing",
                )
        elif label == "REALIZED_VWAP":
            _require(assessment != "SUPPORTED", "realized_vwap_requires_actual_fills")
        elif label == "NET":
            _require(assessment != "SUPPORTED", "net_requires_settled_cashflow")
        elif label == "TOUCH":
            _require(assessment != "SUPPORTED", "touch_threshold_evidence_missing")
        else:
            _require(label == "PATH_RISK", "unexpected_outcome_label")
            _require(
                row["claim_scope"] == "DISCRETE_PATH_GRID"
                and row["path_state"] == "SPARSE_DISCRETE",
                "sparse_projection_continuous_path_forbidden",
            )
            _require(assessment == "SUPPORTED", "discrete_path_risk_support_drift")
            _decimal_nonnegative(row["value_decimal"], "path_risk_value_invalid")

    assessments = Counter(row["assessment"] for row in outcomes)
    _require(assessments == EXPECTED_ASSESSMENTS, "outcome_assessment_denominator_drift")
    _require(summary.get("outcomes_output") == 108, "summary_outcome_denominator_drift")
    _require(summary.get("outcomes_dropped") == 0, "summary_dropped_outcomes")
    _require(summary.get("fillable_supported") == 0, "summary_fillable_support_drift")
    _require(summary.get("quote_exit_supported") == 0, "summary_quote_exit_support_drift")
    _require(summary.get("realized_vwap_supported") == 0, "summary_vwap_support_drift")
    _require(summary.get("net_supported") == 0, "summary_net_support_drift")
    _require(summary.get("path_risk_discrete_supported") == 9, "summary_path_risk_drift")


def validate_matrix(matrix: Mapping[str, Any]) -> None:
    _require(matrix.get("schema") == "smial.task25.r2-outcome-adversarial-matrix", "matrix_schema_drift")
    _require(matrix.get("task_id") == TASK_ID and matrix.get("atom_id") == ATOM_ID, "matrix_identity_drift")
    _require(matrix.get("decision") == DECISION, "matrix_decision_drift")
    _require(matrix.get("base_projection") == FROZEN_INPUTS["a4_projection"], "matrix_base_projection_drift")
    mutations = matrix.get("mutations")
    _require(isinstance(mutations, list) and len(mutations) == 14, "mutation_count_drift")
    ids = [item.get("mutation_id") for item in mutations]
    _require(ids == [f"A5-MUT-{index:03d}" for index in range(1, 15)], "mutation_id_sequence_drift")
    _require(len(set(item.get("expected_error") for item in mutations)) == 14, "mutation_error_coverage_drift")


def apply_mutation(projection: Mapping[str, Any], mutation: Mapping[str, Any]) -> dict[str, Any]:
    mutated = deepcopy(projection)
    operation = mutation["operation"]
    changes = mutation["changes"]
    if operation == "CHANGE_SUMMARY":
        mutated["summary"].update(changes)
    elif operation == "CHANGE_DATASET":
        mutated["dataset_identity"].update(changes)
    elif operation in {"CHANGE_RECORD", "DROP_RECORD"}:
        matches = [
            (index, row)
            for index, row in enumerate(mutated["outcomes"])
            if row["record_id"] == mutation["record_id"]
        ]
        _require(len(matches) == 1, "mutation_record_not_exact")
        index, row = matches[0]
        if operation == "DROP_RECORD":
            del mutated["outcomes"][index]
        else:
            row.update(changes)
    else:
        raise Task25AdversarialAcceptanceError("mutation_operation_invalid")
    return mutated


def run_adversarial_matrix(
    projection: Mapping[str, Any], matrix: Mapping[str, Any]
) -> list[dict[str, str]]:
    validate_projection(projection)
    validate_matrix(matrix)
    results: list[dict[str, str]] = []
    for mutation in matrix["mutations"]:
        mutated = apply_mutation(projection, mutation)
        observed_error: str | None = None
        try:
            validate_projection(mutated)
        except Task25AdversarialAcceptanceError as exc:
            observed_error = str(exc)
        _require(observed_error is not None, f"mutation_not_rejected:{mutation['mutation_id']}")
        _require(
            observed_error == mutation["expected_error"],
            f"mutation_wrong_error:{mutation['mutation_id']}:{observed_error}",
        )
        results.append(
            {
                "mutation_id": mutation["mutation_id"],
                "expected_error": mutation["expected_error"],
                "observed_error": observed_error,
                "status": "PASS_REJECTED",
            }
        )
    return results


def build_acceptance(repo_root: Path) -> dict[str, Any]:
    projection, matrix = load_frozen_inputs(repo_root)
    validate_owner_decision(repo_root)
    capability = validate_upstream_field_capability(repo_root)
    results = run_adversarial_matrix(projection, matrix)
    summary = projection["summary"]
    return {
        "schema": "smial.task25.adversarial-acceptance-owner-decision",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS_ADVERSARIAL_ACCEPTANCE_WITH_REDIRECTED_REDESIGN",
        "input_bindings": FROZEN_INPUTS,
        "baseline_acceptance": {
            "a4_status": projection["status"],
            "outcomes": summary["outcomes_output"],
            "supported": summary["path_risk_discrete_supported"],
            "unknown": projection["summary"]["assessments"]["UNKNOWN"],
            "fillable_supported": summary["fillable_supported"],
            "quote_exit_supported": summary["quote_exit_supported"],
            "realized_vwap_supported": summary["realized_vwap_supported"],
            "net_supported": summary["net_supported"],
            "raw_r2_value_files_reopened_in_a5": 0,
            "r3_paths_or_values_read": 0,
        },
        "adversarial_acceptance": {
            "mutations_declared": len(results),
            "mutations_rejected": len(results),
            "mutations_accepted": 0,
            "status": "PASS_14_OF_14_REJECTED",
            "results": results,
        },
        "upstream_capability": {
            "status": "PRESENT_IN_HASH_BOUND_CODE_NOT_REOPENED_AS_RAW_VALUES",
            "checks": capability,
            "inference": "LOSS_OCCURS_IN_TRACKED_TASK23_DERIVATION_SURFACE",
        },
        "owner_decision": {
            "decision_id": "T25-OWNER-DECISION-001",
            "count": 1,
            "decision": DECISION,
            "decision_scope": "R2_TRACKED_DERIVATION_ONLY",
            "current_projection_disposition": "ACCEPT_AS_NEGATIVE_RESULT_NOT_DECISION_SURFACE",
            "underlying_r2_disposition": "BOUNDED_REPROJECTION_CANDIDATE_NOT_YET_ACCEPTED",
            "r3_disposition": "UNTOUCHED_DENY",
        },
        "rejected_alternatives": [
            "ACCEPT_CURRENT_TRACKED_PROJECTION_FOR_OWNER_COMPARISON",
            "STOP_UNDERLYING_R2_AS_INFEASIBLE",
            "OPEN_R3_OR_COLLECT_MORE_DATA",
        ],
        "implementation": {
            "module": {
                "path": "src/solana_alpha_lab/task25_adversarial_acceptance.py",
                "sha256": sha256_file(
                    repo_root / "src/solana_alpha_lab/task25_adversarial_acceptance.py"
                ),
            },
            "tests": {
                "path": "tests/test_task25_adversarial_acceptance_and_owner_decision.py",
                "sha256": sha256_file(
                    repo_root
                    / "tests/test_task25_adversarial_acceptance_and_owner_decision.py"
                ),
            },
        },
        "side_effects": {
            "raw_r2_value_files_opened": 0,
            "r3_paths_or_values_read": 0,
            "provider_api_rpc_wss_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_or_credits_spent": 0,
            "dependencies_added": 0,
            "sources_changed": 0,
            "catalog_changed": 0,
            "commit_push_pr_merge_actions": 0,
        },
        "next_boundary": {
            "candidate_atom": NEXT_ATOM,
            "authorized_by_a5": False,
            "requires_new_pre_read_receipt": True,
            "raw_r2_scope": "NINE_HASH_BOUND_FILES_ONLY",
            "r3_access": "DENY",
        },
    }


def build_acceptance_bytes(repo_root: Path) -> bytes:
    return canonical_json_bytes(build_acceptance(repo_root))


def check_stored_output(repo_root: Path) -> str:
    payload = build_acceptance_bytes(repo_root)
    path = _safe_path(repo_root, ACCEPTANCE_PATH)
    _require(path.is_file(), "stored_acceptance_missing")
    _require(path.read_bytes() == payload, "stored_acceptance_drift")
    return sha256_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        choices=("acceptance", "hash", "write", "check"),
        default="check",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    payload = build_acceptance_bytes(repo_root)
    if args.artifact == "acceptance":
        print(payload.decode("utf-8"), end="")
    elif args.artifact == "hash":
        print(sha256_bytes(payload))
    elif args.artifact == "write":
        path = _safe_path(repo_root, ACCEPTANCE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print("WROTE_A5_ACCEPTANCE")
    else:
        print(check_stored_output(repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
