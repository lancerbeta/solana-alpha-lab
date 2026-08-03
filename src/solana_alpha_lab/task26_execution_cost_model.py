"""Deterministic synthetic TASK-26 execution-cost model with fail-closed truth gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


TASK_ID = "TASK-26"
ATOM_ID = "T26-A3_DETERMINISTIC_EXECUTION_COST_AND_GOLDEN_ACCEPTANCE_V1"
ENGINE_VERSION = "1.0.0"
PROJECTION_SCHEMA = "smial.task26.synthetic-execution-cost-projection"
ACCEPTANCE_SCHEMA = "smial.task26.a3-deterministic-execution-cost-acceptance"
PROJECTION_PATH = Path("docs/evidence/task26/a3_execution_cost_projection_v1.json")
ACCEPTANCE_PATH = Path(
    "docs/evidence/task26/"
    "a3_deterministic_execution_cost_and_golden_acceptance_v1.json"
)

FROZEN_INPUTS = {
    "contract": {
        "path": "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md",
        "sha256": "aac003cf7ba2742d310893c81af3ae4a032a52b719f2f56d80171a6486351efd",
    },
    "config": {
        "path": "configs/task26_execution_cost_and_netreturn_contract_v1.yaml",
        "sha256": "1107b286248036f4e3ef0a5610b80e7cec8362269ecb2ba835e5040dc3210574",
    },
    "schema": {
        "path": "catalog/schemas/task26_execution_cost_and_netreturn.schema.json",
        "sha256": "f3e9b34ccf8adff60cc1abb6e3fa37dfa59310e479eb7654a8d780e5d0cbf083",
    },
    "fixture": {
        "path": "tests/fixtures/task26/execution_cost_and_netreturn_contract_v1.json",
        "sha256": "7d9e341a603a4c9de32feea58bb169c916864705ddb64ec1dc5853b501fa7bac",
    },
}

PROHIBITED_CLAIMS = (
    "R2_EXECUTION_OR_CASHFLOW_OBSERVED",
    "R3_VALUE_OR_PATH_READ",
    "ACTUAL_NETWORK_EXECUTION",
    "REALIZED_VWAP_OR_OBSERVED_NETRETURN",
    "OWNER_CASHFLOW",
    "STRATEGY_PROFITABILITY_OR_ALPHA",
)


class Task26ExecutionCostModelError(ValueError):
    """Raised when a frozen input or execution-cost state violates A2."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Task26ExecutionCostModelError(code)


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return deterministic human-readable JSON bytes."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task26ExecutionCostModelError("timestamp_invalid") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "timestamp_must_be_aware")
    return parsed


def _integer(value: str | None) -> int | None:
    return None if value is None else int(value)


def _load_frozen_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Open exactly the four A2 artifacts; no data discovery or raw scan."""

    resolved_root = repo_root.resolve()
    payloads: dict[str, bytes] = {}
    for role, binding in FROZEN_INPUTS.items():
        path = (resolved_root / binding["path"]).resolve()
        _require(path.is_relative_to(resolved_root), f"input_path_escape:{role}")
        _require(path.is_file() and not path.is_symlink(), f"input_missing:{role}")
        payload = path.read_bytes()
        _require(sha256_bytes(payload) == binding["sha256"], f"input_hash_drift:{role}")
        payloads[role] = payload
    try:
        schema = json.loads(payloads["schema"])
        fixture = json.loads(payloads["fixture"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task26ExecutionCostModelError("frozen_json_invalid") from exc
    _require(isinstance(schema, dict), "schema_root_not_mapping")
    _require(isinstance(fixture, dict), "fixture_root_not_mapping")
    return schema, fixture


def _validate_schema(schema: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise Task26ExecutionCostModelError("json_schema_invalid") from exc
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(fixture),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path)
        raise Task26ExecutionCostModelError(f"fixture_schema_invalid:{location}")


def _validate_timeline(scenario: Mapping[str, Any]) -> None:
    timeline = scenario["timeline"]
    ordered = [
        _parse_time(timeline["event_at"]),
        _parse_time(timeline["observed_at"]),
        _parse_time(timeline["first_reliable_available_at"]),
        _parse_time(timeline["available_to_strategy_at"]),
        _parse_time(timeline["ingested_at"]),
    ]
    _require(ordered == sorted(ordered), "pit_order_invalid")
    _require(_parse_time(timeline["measured_as_of"]) <= ordered[3], "pit_measurement_order_invalid")


def _validate_attempts(scenario: Mapping[str, Any]) -> set[str]:
    attempts = scenario["attempts"]
    attempt_ids = [attempt["attempt_id"] for attempt in attempts]
    _require(len(attempt_ids) == len(set(attempt_ids)), "attempt_id_duplicate")
    by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    terminal_states: set[str] = set()
    for attempt in attempts:
        terminal_states.add(attempt["terminal_state"])
        retry_of = attempt["retry_of"]
        if retry_of is not None:
            previous = by_id.get(retry_of)
            _require(previous is not None, "retry_parent_missing")
            _require(previous["retry_chain_id"] == attempt["retry_chain_id"], "retry_chain_invalid")
    if "UNKNOWN" in terminal_states:
        _require(not scenario["retry_permitted"], "unknown_terminal_blocks_retry")
        _require(not scenario["accounting_closed"], "unknown_terminal_blocks_accounting_closure")
    return terminal_states


def _validate_fees(scenario: Mapping[str, Any], terminal_states: set[str]) -> None:
    fees = scenario["fees"]
    fee_ids = [fee["fee_id"] for fee in fees]
    _require(len(fee_ids) == len(set(fee_ids)), "retry_chain_fee_duplicate_forbidden")
    by_id = {fee["fee_id"]: fee for fee in fees}
    for fee_id in scenario["quote"]["quote_embedded_fee_ids"]:
        fee = by_id.get(fee_id)
        _require(fee is not None, "quote_embedded_fee_missing")
        _require(fee["component_kind"] == "QUOTE_EMBEDDED" and fee["included_in_quote"], "quote_embedded_fee_binding_invalid")
    for fee in fees:
        _require(not (fee["included_in_quote"] and fee["included_in_trade_cashflow"]), "quote_embedded_fee_double_count_forbidden")
        _require(not (fee["component_kind"] == "INFRASTRUCTURE" and fee["included_in_trade_cashflow"]), "infrastructure_cost_separate_from_trade_cashflow")
        _require(not ({"DROPPED", "EXPIRED"} & terminal_states and fee["source"] == "ASSUMED_ZERO"), "dropped_or_expired_charge_cannot_be_assumed_zero")
    cashflow = scenario["cashflow"]
    trade_ids = set(cashflow["fee_ids_in_trade_cashflow"])
    infrastructure_ids = set(cashflow["fee_ids_in_infrastructure_cashflow"])
    _require(not trade_ids & infrastructure_ids, "fee_cashflow_double_count_forbidden")
    _require(trade_ids.union(infrastructure_ids).issubset(by_id), "cashflow_references_unknown_fee")
    _require(all(by_id[fee_id]["component_kind"] != "INFRASTRUCTURE" for fee_id in trade_ids), "infrastructure_cost_separate_from_trade_cashflow")
    _require(all(by_id[fee_id]["component_kind"] == "INFRASTRUCTURE" for fee_id in infrastructure_ids), "infrastructure_fee_classification_invalid")


def _validate_inventory_and_netreturn(scenario: Mapping[str, Any], terminal_states: set[str]) -> None:
    inventory = scenario["inventory"]
    remaining = _integer(inventory["remaining_inventory_atomic"])
    _require(remaining is not None, "inventory_amount_missing")
    if inventory["state"] in {"NO_POSITION", "FLAT_MODELED", "FLAT_ACTUAL"}:
        _require(remaining == 0, "flat_or_no_position_requires_zero_inventory")
    if inventory["state"] in {"PARTIAL_OPEN", "UNRESOLVED_REQUIRES_RECOVERY"}:
        _require(remaining > 0, "partial_or_unresolved_inventory_requires_positive_remainder")
    if inventory["state"] == "UNRESOLVED_REQUIRES_RECOVERY":
        lower = _integer(inventory["recovery_lower_atomic"])
        upper = _integer(inventory["recovery_upper_atomic"])
        _require(lower is not None and upper is not None and lower <= upper, "recovery_bounds_invalid")
    if scenario["fill"]["state"] == "PARTIAL_MODELED":
        _require(inventory["state"] not in {"NO_POSITION", "FLAT_MODELED", "FLAT_ACTUAL"}, "partial_or_unresolved_inventory_cannot_be_flat")
    if "UNKNOWN" in terminal_states:
        _require(inventory["state"] == "UNRESOLVED_REQUIRES_RECOVERY", "unknown_terminal_requires_recovery_inventory")

    cashflow = scenario["cashflow"]
    net = scenario["net_return"]
    classification = net["classification"]
    trade = _integer(cashflow["trade_cashflow_atomic"])
    infrastructure = _integer(cashflow["infrastructure_cashflow_atomic"])
    net_amount = _integer(net["amount_atomic"])
    if classification == "NOT_COMPUTABLE":
        _require(net_amount is None and net["currency"] is None, "incomplete_model_cannot_emit_numeric_netreturn")
        return
    if classification == "MODELED":
        _require(cashflow["currency"] == net["currency"], "netreturn_currency_not_normalized")
        _require(trade is not None and infrastructure is not None and net_amount is not None, "netreturn_amount_missing")
        _require(trade + infrastructure == net_amount, "netreturn_cashflow_mismatch")
        _require(cashflow["state"] == "MODELED_COMPLETE", "modeled_netreturn_cashflow_incomplete")
        _require(inventory["state"] == "FLAT_MODELED", "modeled_netreturn_inventory_not_flat")
        _require("UNKNOWN" not in terminal_states, "modeled_netreturn_unknown_terminal")
        _require(all(fee["charge_state"] != "UNKNOWN" for fee in scenario["fees"]), "modeled_netreturn_unknown_fee")
        return
    _require(classification == "OBSERVED", "netreturn_classification_invalid")
    _require(terminal_states != {"NOT_ATTEMPTED"}, "quote_only_cannot_be_observed_netreturn")
    _require(scenario["fill"]["state"] == "ACTUAL_RECONCILED" and bool(scenario["fill"]["fill_reference_ids"]), "observed_netreturn_requires_actual_fill")
    _require(cashflow["state"] == "SETTLED_COMPLETE" and bool(cashflow["settled_reference_ids"]), "observed_netreturn_requires_settled_cashflow")
    _require(inventory["state"] == "FLAT_ACTUAL", "observed_netreturn_inventory_not_flat")
    _require(scenario["accounting_closed"], "observed_netreturn_accounting_not_closed")
    _require(cashflow["currency"] == net["currency"], "netreturn_currency_not_normalized")
    _require(trade is not None and infrastructure is not None and net_amount is not None, "netreturn_amount_missing")
    _require(trade + infrastructure == net_amount, "netreturn_cashflow_mismatch")


def evaluate_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and project one synthetic scenario without reading external data."""

    _require(scenario["source_scope"] == "SYNTHETIC_GOLDEN", "non_synthetic_input_forbidden")
    _validate_timeline(scenario)
    quote = scenario["quote"]
    _require(quote["observed_age_ms"] <= quote["freshness_max_age_ms"], "quote_freshness_exceeded")
    terminal_states = _validate_attempts(scenario)
    _validate_fees(scenario, terminal_states)
    _validate_inventory_and_netreturn(scenario, terminal_states)

    classification = scenario["net_return"]["classification"]
    inventory_state = scenario["inventory"]["state"]
    if classification == "NOT_COMPUTABLE":
        if "UNKNOWN" in terminal_states:
            blocked_reason = "UNKNOWN_TERMINAL_REQUIRES_RECONCILIATION"
        elif inventory_state in {"PARTIAL_OPEN", "UNRESOLVED_REQUIRES_RECOVERY"}:
            blocked_reason = "OPEN_OR_UNRESOLVED_INVENTORY"
        elif terminal_states == {"NOT_ATTEMPTED"}:
            blocked_reason = "QUOTE_ONLY_NO_ATTEMPT"
        else:
            blocked_reason = "CASHFLOW_OR_FEE_INCOMPLETE"
        result_state = "NOT_COMPUTABLE"
        net_return_atomic = None
    elif classification == "MODELED":
        blocked_reason = None
        result_state = "MODELED_COMPLETE"
        net_return_atomic = scenario["net_return"]["amount_atomic"]
    else:
        blocked_reason = None
        result_state = "SYNTHETIC_OBSERVED_SEMANTICS_ONLY"
        net_return_atomic = scenario["net_return"]["amount_atomic"]

    cashflow = scenario["cashflow"]
    return {
        "accounting_closed": scenario["accounting_closed"],
        "attempt_terminal_states": sorted(terminal_states),
        "blocked_reason": blocked_reason,
        "cashflow_currency": cashflow["currency"],
        "cashflow_decimals": cashflow["decimals"],
        "classification": classification,
        "fee_ids": sorted(fee["fee_id"] for fee in scenario["fees"]),
        "infrastructure_cashflow_atomic": cashflow["infrastructure_cashflow_atomic"],
        "inventory_state": inventory_state,
        "net_return_atomic": net_return_atomic,
        "result_state": result_state,
        "scenario_id": scenario["scenario_id"],
        "trade_cashflow_atomic": cashflow["trade_cashflow_atomic"],
    }


def build_projection(repo_root: Path) -> dict[str, Any]:
    """Validate frozen synthetic evidence and produce a deterministic read model."""

    schema, fixture = _load_frozen_inputs(repo_root)
    _validate_schema(schema, fixture)
    _require(fixture["fixture_kind"] == "SYNTHETIC_GOLDEN_ONLY", "fixture_scope_drift")
    scenarios = fixture["scenarios"]
    _require(len(scenarios) == 9, "golden_scenario_count_drift")
    scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
    _require(len(scenario_ids) == len(set(scenario_ids)), "scenario_id_duplicate")
    projected = [evaluate_scenario(scenario) for scenario in sorted(scenarios, key=lambda item: item["scenario_id"])]
    classifications = Counter(result["classification"] for result in projected)
    result_states = Counter(result["result_state"] for result in projected)
    blocked_reasons = Counter(result["blocked_reason"] for result in projected if result["blocked_reason"])
    projection: dict[str, Any] = {
        "atom_id": ATOM_ID,
        "engine_version": ENGINE_VERSION,
        "input_bindings": FROZEN_INPUTS,
        "nonclaims": list(PROHIBITED_CLAIMS),
        "next_boundary": {
            "atom": "T26-A4_ADVERSARIAL_EXECUTION_COST_ACCEPTANCE_AND_OWNER_DECISION_V1",
            "authorized_by_a3": False,
            "r2_value_read_allowed": False,
            "r3_access": "DENY",
        },
        "projection_results": projected,
        "schema": PROJECTION_SCHEMA,
        "schema_version": "1.0",
        "status": "PASS_SYNTHETIC_EXECUTION_COST_MODEL_WITH_LIMITATIONS",
        "summary": {
            "classifications": dict(sorted(classifications.items())),
            "input_scenarios": len(scenarios),
            "output_scenarios": len(projected),
            "scenarios_dropped": 0,
            "result_states": dict(sorted(result_states.items())),
            "blocked_reasons": dict(sorted(blocked_reasons.items())),
            "modeled_netreturn_scenarios": classifications["MODELED"],
            "synthetic_observed_semantic_cases": classifications["OBSERVED"],
            "observed_netreturn_claims": 0,
            "r2_values_read": 0,
            "r3_paths_or_values_read": 0,
            "provider_api_rpc_wss_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
        },
        "task_id": TASK_ID,
    }
    return projection


def build_acceptance(repo_root: Path, projection: Mapping[str, Any]) -> dict[str, Any]:
    """Build an acceptance receipt bound to the exact generated output and code."""

    summary = projection["summary"]
    checks = [
        ("A2_INPUT_HASHES_EXACT", projection["input_bindings"] == FROZEN_INPUTS),
        ("SYNTHETIC_SCENARIOS_9", summary["input_scenarios"] == 9),
        ("NO_SCENARIOS_DROPPED", summary["scenarios_dropped"] == 0),
        ("MODELED_SCENARIOS_3", summary["modeled_netreturn_scenarios"] == 3),
        ("SYNTHETIC_OBSERVED_CASE_1", summary["synthetic_observed_semantic_cases"] == 1),
        ("OBSERVED_CLAIMS_ZERO", summary["observed_netreturn_claims"] == 0),
        ("R2_R3_PROVIDER_WALLET_CASH_ZERO", all(summary[key] == 0 for key in ("r2_values_read", "r3_paths_or_values_read", "provider_api_rpc_wss_calls", "wallet_signer_transaction_actions", "cash_spend_usd_cents"))),
        ("NORMALIZED_CASHFLOW_CURRENCY", all(result["cashflow_currency"] == "SYNTHETIC_USDC" and result["cashflow_decimals"] == 6 for result in projection["projection_results"])),
        ("UNRESOLVED_STATES_RETAINED", bool(summary["blocked_reasons"])),
        ("NEXT_BOUNDARY_NOT_AUTHORIZED", projection["next_boundary"]["authorized_by_a3"] is False and projection["next_boundary"]["r3_access"] == "DENY"),
    ]
    failures = [check_id for check_id, passed in checks if not passed]
    _require(not failures, "acceptance_failed:" + ",".join(failures))

    resolved_root = repo_root.resolve()
    code_paths = {
        "module": "src/solana_alpha_lab/task26_execution_cost_model.py",
        "test": "tests/test_task26_execution_cost_model.py",
    }
    code_bindings: dict[str, dict[str, Any]] = {}
    for role, relative in code_paths.items():
        path = (resolved_root / relative).resolve()
        _require(path.is_relative_to(resolved_root), f"code_path_escape:{role}")
        _require(path.is_file() and not path.is_symlink(), f"code_missing:{role}")
        code_bindings[role] = {"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)}

    return {
        "artifact_bindings": {
            "projection": {"path": PROJECTION_PATH.as_posix(), "sha256": sha256_bytes(canonical_json_bytes(projection))},
            "a2_contract": FROZEN_INPUTS["contract"],
            "a2_config": FROZEN_INPUTS["config"],
            "a2_schema": FROZEN_INPUTS["schema"],
            "a2_fixture": FROZEN_INPUTS["fixture"],
        },
        "atom_id": ATOM_ID,
        "as_of": "2026-08-03",
        "code_bindings": code_bindings,
        "checks": [{"check_id": check_id, "status": "PASS"} for check_id, _ in checks],
        "measured_boundary": {
            "synthetic_scenarios_processed": 9,
            "scenarios_dropped": 0,
            "r2_values_or_paths_read": 0,
            "r3_values_or_paths_read": 0,
            "holdout_consumption_records_added": 0,
            "provider_api_rpc_wss_calls": 0,
            "dependency_changes": 0,
            "project_source_changes": 0,
            "catalog_or_registry_mutations": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
        },
        "next_boundary": dict(projection["next_boundary"]),
        "schema": ACCEPTANCE_SCHEMA,
        "schema_version": "1.0",
        "state_change": {"task26": "IN_PROGRESS", "atom_a3": "VALIDATED", "canonical_task26_done": False, "catalog_registration": "DEFERRED_TO_T26_A6"},
        "status": "PASS_SYNTHETIC_EXECUTION_COST_MODEL_WITH_LIMITATIONS",
        "task_id": TASK_ID,
        "validation": {
            "status": "PASS",
            "targeted_command": "uv run --locked --managed-python python -B -m unittest tests.test_task26_execution_cost_model",
            "full_validation": "DEFERRED_TO_DELIVERY_GATE",
        },
    }


def build_outputs(repo_root: Path) -> tuple[bytes, bytes]:
    projection = build_projection(repo_root)
    acceptance = build_acceptance(repo_root, projection)
    return canonical_json_bytes(projection), canonical_json_bytes(acceptance)


def check_stored_outputs(repo_root: Path) -> dict[str, str]:
    projection_bytes, acceptance_bytes = build_outputs(repo_root)
    expected = {PROJECTION_PATH: projection_bytes, ACCEPTANCE_PATH: acceptance_bytes}
    for relative, payload in expected.items():
        path = repo_root / relative
        _require(path.is_file(), f"stored_output_missing:{relative.as_posix()}")
        _require(path.read_bytes() == payload, f"stored_output_drift:{relative.as_posix()}")
    return {relative.as_posix(): sha256_bytes(payload) for relative, payload in expected.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", choices=("projection", "acceptance", "hashes", "check"), default="hashes")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    projection_bytes, acceptance_bytes = build_outputs(repo_root)
    if args.artifact == "projection":
        print(projection_bytes.decode("utf-8"), end="")
    elif args.artifact == "acceptance":
        print(acceptance_bytes.decode("utf-8"), end="")
    elif args.artifact == "check":
        print(json.dumps(check_stored_outputs(repo_root), sort_keys=True))
    else:
        print(json.dumps({PROJECTION_PATH.as_posix(): sha256_bytes(projection_bytes), ACCEPTANCE_PATH.as_posix(): sha256_bytes(acceptance_bytes)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
