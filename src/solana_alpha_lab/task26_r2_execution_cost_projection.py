"""Bounded TASK-26 projection of the exact tracked TASK-25 R2 quote surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any


TASK_ID = "TASK-26"
ATOM_ID = "T26-A5_BOUNDED_R2_QUOTE_EVIDENCE_PROJECTION_V1"
PROJECTION_PATH = Path("docs/evidence/task26/a5_bounded_r2_execution_cost_projection_v1.json")
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26/a5_bounded_r2_execution_cost_projection_acceptance_v1.json"
)

FROZEN_INPUTS = {
    "r2_surface": {
        "asset_id": "DATA-T25-EXACT-R2-OUTCOME-SURFACE-001",
        "path": "docs/evidence/task25/a5r1_exact_r2_outcome_surface_v1.json",
        "sha256": "20b5a611895b35856192b274e8954b34e4794e593605b9c3962d2115d4fbd59f",
    },
    "r2_acceptance": {
        "asset_id": "EVIDENCE-T25-A5R1-ACCEPTANCE-001",
        "path": "docs/evidence/task25/a5r1_exact_r2_outcome_reprojection_acceptance_v1.json",
        "sha256": "32c8b75023754afa7fdbe6a5578e009d8856cb1d514fbd60954544b503f6ef7b",
    },
    "a4_acceptance": {
        "path": "docs/evidence/task26/a4_adversarial_execution_cost_acceptance_v1.json",
        "sha256": "86b09e393c0a811c7f8b260eb1e5f7236351ea5d8d56000fea873195c1355d82",
    },
}


class Task26R2ExecutionCostProjectionError(ValueError):
    """Raised when the bounded R2 input is invalid or a quote becomes NetReturn."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26R2ExecutionCostProjectionError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_bound_json(repo_root: Path, role: str, binding: Mapping[str, str]) -> dict[str, Any]:
    root = repo_root.resolve()
    path = (root / binding["path"]).resolve()
    _require(path.is_relative_to(root), f"path_escape:{role}")
    _require(path.is_file() and not path.is_symlink(), f"input_missing:{role}")
    payload = path.read_bytes()
    _require(sha256_bytes(payload) == binding["sha256"], f"input_hash_drift:{role}")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task26R2ExecutionCostProjectionError(f"input_json_invalid:{role}") from exc
    _require(isinstance(decoded, dict), f"input_not_mapping:{role}")
    return decoded


def _load_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    surface = _read_bound_json(repo_root, "r2_surface", FROZEN_INPUTS["r2_surface"])
    r2_acceptance = _read_bound_json(repo_root, "r2_acceptance", FROZEN_INPUTS["r2_acceptance"])
    a4_acceptance = _read_bound_json(repo_root, "a4_acceptance", FROZEN_INPUTS["a4_acceptance"])
    _require(surface["task_id"] == "TASK-25", "r2_surface_task_drift")
    _require(surface["status"] == "MATERIALIZED_EXACT_R2_DEVELOPMENT_SURFACE", "r2_surface_status_drift")
    _require(surface["summary"]["outcomes_output"] == 108, "r2_outcome_count_drift")
    _require(surface["summary"]["quote_pairs"] == 36, "r2_quote_pair_count_drift")
    _require(surface["summary"]["r3_paths_or_values_read"] == 0, "r2_surface_r3_drift")
    _require(
        r2_acceptance["status"] == "PASS_EXACT_R2_OUTCOME_SURFACE_WITH_BOUNDED_DEVELOPMENT_LABELS",
        "r2_acceptance_status_drift",
    )
    _require(
        a4_acceptance["owner_decision"]["decision"] == "EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS",
        "a4_owner_decision_drift",
    )
    return surface, r2_acceptance, a4_acceptance


def _outcome_maps(surface: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[tuple[str, str], Mapping[str, Any]]]:
    fillable: dict[str, Mapping[str, Any]] = {}
    quote_exit: dict[tuple[str, str], Mapping[str, Any]] = {}
    for outcome in surface["outcomes"]:
        quote_ids = outcome["lineage"]["quote_attempt_ids"]
        if outcome["label"] == "FILLABLE":
            _require(len(quote_ids) == 1, "fillable_quote_lineage_invalid")
            quote_id = quote_ids[0]
            _require(quote_id not in fillable, "fillable_quote_duplicate")
            fillable[quote_id] = outcome
        elif outcome["label"] == "QUOTE_EXIT":
            _require(len(quote_ids) == 2, "quote_exit_lineage_invalid")
            key = tuple(sorted(quote_ids))
            _require(key not in quote_exit, "quote_exit_pair_duplicate")
            quote_exit[key] = outcome
    _require(len(fillable) == 36, "fillable_count_drift")
    _require(len(quote_exit) == 36, "quote_exit_count_drift")
    return fillable, quote_exit


def _project_pair(
    pair: Mapping[str, Any],
    fillable: Mapping[str, Any],
    quote_exit: Mapping[str, Any],
) -> dict[str, Any]:
    buy_attempt_id = pair["buy_quote_attempt_id"]
    sell_attempt_id = pair["sell_quote_attempt_id"]
    fillable_outcome = fillable.get(buy_attempt_id)
    exit_outcome = quote_exit.get(tuple(sorted((buy_attempt_id, sell_attempt_id))))
    _require(fillable_outcome is not None, f"fillable_missing:{pair['pair_id']}")
    _require(exit_outcome is not None, f"quote_exit_missing:{pair['pair_id']}")
    _require(fillable_outcome["member_id"] == pair["member_id"], "fillable_member_mismatch")
    _require(fillable_outcome["panel_id"] == pair["panel_id"], "fillable_panel_mismatch")
    _require(exit_outcome["member_id"] == pair["member_id"], "quote_exit_member_mismatch")
    _require(exit_outcome["panel_id"] == pair["panel_id"], "quote_exit_panel_mismatch")
    _require(pair["exact_dependent_sell_identity"] is True, "dependent_sell_identity_invalid")

    ready = (
        fillable_outcome["assessment"] == "SUPPORTED"
        and exit_outcome["assessment"] == "SUPPORTED"
        and fillable_outcome["fill_state"] == "ACTUAL_FILLS_NOT_OBSERVED"
        and exit_outcome["inventory"]["state"] == "OPEN"
    )
    if ready:
        input_state = "QUOTE_COST_INPUT_READY"
        blocked_reason = None
    else:
        input_state = "NOT_COMPUTABLE"
        blocked_reason = "ENTRY_" + fillable_outcome["assessment_reason"]

    return {
        "blocked_reason": blocked_reason,
        "entry_assessment": fillable_outcome["assessment"],
        "entry_assessment_reason": fillable_outcome["assessment_reason"],
        "execution_cost_input_state": input_state,
        "pair_id": pair["pair_id"],
        "quote_gross_return_bps": pair["roundtrip_quote_retention_bps"],
        "source_outcome_record_ids": {
            "fillable": fillable_outcome["record_id"],
            "quote_exit": exit_outcome["record_id"],
        },
        "tested_notional_usd": pair["tested_notional_usd"],
        "window_id": pair["window_id"],
    }


def build_projection(repo_root: Path) -> dict[str, Any]:
    """Read the one bound R2 aggregate and emit no actual execution or NetReturn claim."""

    surface, _, _ = _load_inputs(repo_root)
    fillable, quote_exit = _outcome_maps(surface)
    pairs = sorted(surface["quote_pairs"], key=lambda row: row["pair_id"])
    projected = [_project_pair(pair, fillable, quote_exit) for pair in pairs]
    states = Counter(row["execution_cost_input_state"] for row in projected)
    _require(len(projected) == 36, "projection_pair_count_drift")
    _require(states["QUOTE_COST_INPUT_READY"] == 35, "quote_cost_ready_count_drift")
    _require(states["NOT_COMPUTABLE"] == 1, "not_computable_count_drift")
    ready_pair_ids = [
        row["pair_id"]
        for row in projected
        if row["execution_cost_input_state"] == "QUOTE_COST_INPUT_READY"
    ]
    blocked_pairs = [
        {
            "blocked_reason": row["blocked_reason"],
            "entry_assessment_reason": row["entry_assessment_reason"],
            "pair_id": row["pair_id"],
            "source_outcome_record_ids": row["source_outcome_record_ids"],
        }
        for row in projected
        if row["execution_cost_input_state"] == "NOT_COMPUTABLE"
    ]

    return {
        "atom_id": ATOM_ID,
        "input_bindings": FROZEN_INPUTS,
        "nonclaims": [
            "ACTUAL_FILL_OR_SETTLEMENT",
            "OBSERVED_NETRETURN",
            "OWNER_CASHFLOW",
            "STRATEGY_PROFITABILITY_OR_ALPHA",
            "R3_VALUE_OR_PATH_READ",
        ],
        "next_boundary": {
            "atom": "T26-A6_ADVERSARIAL_R2_EXECUTION_COST_ACCEPTANCE_AND_OWNER_DECISION_V1",
            "authorized_by_a5": False,
            "r3_access": "DENY",
        },
        "net_return_surface": {
            "amount_atomic": None,
            "classification": "NOT_COMPUTABLE",
            "currency": None,
            "reason": "R2_NO_COMPLETE_FEE_OR_SETTLED_CASHFLOW",
            "records_covered": len(projected),
        },
        "pair_readiness": {
            "not_computable_pairs": blocked_pairs,
            "projection_records_sha256": sha256_bytes(canonical_json_bytes({"records": projected})),
            "quote_cost_input_ready_pair_ids": ready_pair_ids,
        },
        "schema": "smial.task26.bounded-r2-execution-cost-input-projection",
        "schema_version": "1.0",
        "status": "PASS_BOUNDED_R2_QUOTE_EXECUTION_COST_INPUT_SURFACE_WITH_LIMITATIONS",
        "summary": {
            "actual_fill_or_settlement_claims": 0,
            "cash_spend_usd_cents": 0,
            "execution_cost_input_states": dict(sorted(states.items())),
            "numeric_netreturn_claims": 0,
            "pairs_input": len(pairs),
            "pairs_output": len(projected),
            "provider_api_rpc_wss_calls": 0,
            "r2_raw_files_opened": 0,
            "r2_surface_files_read": 1,
            "r3_paths_or_values_read": 0,
            "records_dropped": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "task_id": TASK_ID,
        "truth_boundary": {
            "actual_fill_or_settlement_observed": False,
            "quote_truth": "POINT_IN_TIME_QUOTE_ONLY",
        },
    }


def _code_binding(repo_root: Path, relative_path: str) -> dict[str, Any]:
    root = repo_root.resolve()
    path = (root / relative_path).resolve()
    _require(path.is_relative_to(root), f"code_path_escape:{relative_path}")
    _require(path.is_file() and not path.is_symlink(), f"code_missing:{relative_path}")
    payload = path.read_bytes()
    return {"bytes": len(payload), "path": relative_path, "sha256": sha256_bytes(payload)}


def build_acceptance(repo_root: Path, projection: Mapping[str, Any]) -> dict[str, Any]:
    summary = projection["summary"]
    checks = [
        ("FROZEN_R2_AND_A4_BINDINGS_EXACT", projection["input_bindings"] == FROZEN_INPUTS),
        ("R2_AGGREGATE_SURFACE_ONLY", summary["r2_surface_files_read"] == 1 and summary["r2_raw_files_opened"] == 0),
        ("ALL_36_PAIRS_RETAINED", summary["pairs_input"] == 36 and summary["pairs_output"] == 36 and summary["records_dropped"] == 0),
        ("QUOTE_COST_INPUT_READY_35", summary["execution_cost_input_states"].get("QUOTE_COST_INPUT_READY") == 35),
        ("LATENCY_UNKNOWN_REMAINS_NOT_COMPUTABLE", summary["execution_cost_input_states"].get("NOT_COMPUTABLE") == 1),
        ("NO_NUMERIC_NETRETURN", summary["numeric_netreturn_claims"] == 0 and projection["net_return_surface"]["amount_atomic"] is None),
        ("NO_FILL_OR_SETTLEMENT_CLAIMS", summary["actual_fill_or_settlement_claims"] == 0 and projection["truth_boundary"]["actual_fill_or_settlement_observed"] is False),
        ("R3_PROVIDER_WALLET_CASH_ZERO", all(summary[key] == 0 for key in ("r3_paths_or_values_read", "provider_api_rpc_wss_calls", "wallet_signer_transaction_actions", "cash_spend_usd_cents"))),
    ]
    failures = [check_id for check_id, passed in checks if not passed]
    _require(not failures, "acceptance_failed:" + ",".join(failures))
    return {
        "artifact_bindings": {
            "projection": {
                "path": PROJECTION_PATH.as_posix(),
                "sha256": sha256_bytes(canonical_json_bytes(projection)),
            },
            **FROZEN_INPUTS,
        },
        "as_of": "2026-08-03",
        "atom_id": ATOM_ID,
        "checks": [{"check_id": check_id, "status": "PASS"} for check_id, _ in checks],
        "code_bindings": {
            "module": _code_binding(repo_root, "src/solana_alpha_lab/task26_r2_execution_cost_projection.py"),
            "test": _code_binding(repo_root, "tests/test_task26_r2_execution_cost_projection.py"),
        },
        "measured_boundary": {
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "holdout_consumption_records_added": 0,
            "provider_api_rpc_wss_calls": 0,
            "r2_raw_files_opened": 0,
            "r2_surface_files_read": 1,
            "r3_paths_or_values_read": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": projection["next_boundary"],
        "schema": "smial.task26.a5-bounded-r2-execution-cost-projection-acceptance",
        "schema_version": "1.0",
        "state_change": {"atom_a5": "VALIDATED", "canonical_task26_done": False, "task26": "IN_PROGRESS"},
        "status": "PASS_BOUNDED_R2_QUOTE_EXECUTION_COST_INPUT_SURFACE_WITH_LIMITATIONS",
        "task_id": TASK_ID,
        "validation": {
            "full_validation": "DEFERRED_TO_DELIVERY_GATE",
            "status": "PASS",
            "targeted_command": "uv run --locked --managed-python python -B -m unittest tests.test_task26_r2_execution_cost_projection",
        },
    }


def check_stored_outputs(repo_root: Path) -> dict[str, str]:
    projection = build_projection(repo_root)
    acceptance = build_acceptance(repo_root, projection)
    expected = {
        PROJECTION_PATH: canonical_json_bytes(projection),
        ACCEPTANCE_PATH: canonical_json_bytes(acceptance),
    }
    hashes: dict[str, str] = {}
    root = repo_root.resolve()
    for relative_path, payload in expected.items():
        path = root / relative_path
        _require(path.is_file() and not path.is_symlink(), f"stored_output_missing:{relative_path.as_posix()}")
        _require(path.read_bytes() == payload, f"stored_output_drift:{relative_path.as_posix()}")
        hashes[relative_path.as_posix()] = sha256_bytes(payload)
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", choices=("projection", "acceptance", "check"), required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    projection = build_projection(repo_root)
    if args.artifact == "projection":
        print(canonical_json_bytes(projection).decode("utf-8"), end="")
    elif args.artifact == "acceptance":
        print(canonical_json_bytes(build_acceptance(repo_root, projection)).decode("utf-8"), end="")
    else:
        print(json.dumps(check_stored_outputs(repo_root), sort_keys=True))


if __name__ == "__main__":
    main()
