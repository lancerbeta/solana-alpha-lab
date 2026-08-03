from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task26_execution_cost_and_netreturn_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task26_execution_cost_and_netreturn.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task26/execution_cost_and_netreturn_contract_v1.json"
RECEIPT_PATH = ROOT / "docs/evidence/task26/a2_execution_cost_and_netreturn_contract_acceptance_v1.json"

EXPECTED_WRITE_SET = [
    "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md",
    "configs/task26_execution_cost_and_netreturn_contract_v1.yaml",
    "catalog/schemas/task26_execution_cost_and_netreturn.schema.json",
    "tests/fixtures/task26/execution_cost_and_netreturn_contract_v1.json",
    "tests/test_task26_execution_cost_and_netreturn_contract.py",
    "docs/evidence/task26/a2_execution_cost_and_netreturn_contract_acceptance_v1.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def as_int(value: str | None) -> int | None:
    return None if value is None else int(value)


def apply_json_pointer(payload: dict[str, Any], pointer: str, replacement: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]
    target: Any = payload
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = replacement
    else:
        target[last] = replacement


def semantic_errors(scenario: dict[str, Any]) -> set[str]:
    errors: set[str] = set()

    timeline = scenario["timeline"]
    timestamps = [
        as_time(timeline["event_at"]),
        as_time(timeline["observed_at"]),
        as_time(timeline["first_reliable_available_at"]),
        as_time(timeline["available_to_strategy_at"]),
        as_time(timeline["ingested_at"]),
    ]
    if timestamps != sorted(timestamps) or as_time(timeline["measured_as_of"]) > timestamps[3]:
        errors.add("PIT_ORDER_INVALID")

    attempts = scenario["attempts"]
    attempt_ids = [attempt["attempt_id"] for attempt in attempts]
    if len(attempt_ids) != len(set(attempt_ids)):
        errors.add("ATTEMPT_ID_DUPLICATE")
    attempts_by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    for attempt in attempts:
        retry_of = attempt["retry_of"]
        if retry_of is not None:
            original = attempts_by_id.get(retry_of)
            if original is None or original["retry_chain_id"] != attempt["retry_chain_id"]:
                errors.add("RETRY_CHAIN_INVALID")

    terminal_states = {attempt["terminal_state"] for attempt in attempts}
    if "UNKNOWN" in terminal_states:
        if scenario["retry_permitted"]:
            errors.add("UNKNOWN_TERMINAL_BLOCKS_RETRY")
        if scenario["accounting_closed"]:
            errors.add("UNKNOWN_TERMINAL_BLOCKS_ACCOUNTING_CLOSURE")

    fees = scenario["fees"]
    fee_ids = [fee["fee_id"] for fee in fees]
    if len(fee_ids) != len(set(fee_ids)):
        errors.add("RETRY_CHAIN_FEE_DUPLICATE_FORBIDDEN")
    fee_by_id = {fee["fee_id"]: fee for fee in fees}
    quote_embedded_ids = set(scenario["quote"]["quote_embedded_fee_ids"])
    for fee_id in quote_embedded_ids:
        fee = fee_by_id.get(fee_id)
        if fee is None or fee["component_kind"] != "QUOTE_EMBEDDED" or not fee["included_in_quote"]:
            errors.add("QUOTE_EMBEDDED_FEE_BINDING_INVALID")
    for fee in fees:
        if fee["included_in_quote"] and fee["included_in_trade_cashflow"]:
            errors.add("QUOTE_EMBEDDED_FEE_DOUBLE_COUNT_FORBIDDEN")
        if fee["component_kind"] == "INFRASTRUCTURE" and fee["included_in_trade_cashflow"]:
            errors.add("INFRASTRUCTURE_COST_SEPARATE_FROM_TRADE_CASHFLOW")
        if (
            {"DROPPED", "EXPIRED"}.intersection(terminal_states)
            and fee["source"] == "ASSUMED_ZERO"
        ):
            errors.add("DROPPED_OR_EXPIRED_CHARGE_CANNOT_BE_ASSUMED_ZERO")

    cashflow = scenario["cashflow"]
    trade_fee_ids = set(cashflow["fee_ids_in_trade_cashflow"])
    infra_fee_ids = set(cashflow["fee_ids_in_infrastructure_cashflow"])
    if trade_fee_ids.intersection(infra_fee_ids):
        errors.add("FEE_CASHFLOW_DOUBLE_COUNT_FORBIDDEN")
    if any(fee_id not in fee_by_id for fee_id in trade_fee_ids.union(infra_fee_ids)):
        errors.add("CASHFLOW_REFERENCES_UNKNOWN_FEE")
    for fee_id in infra_fee_ids:
        if fee_by_id[fee_id]["component_kind"] != "INFRASTRUCTURE":
            errors.add("INFRASTRUCTURE_FEE_CLASSIFICATION_INVALID")

    inventory = scenario["inventory"]
    remaining = as_int(inventory["remaining_inventory_atomic"])
    if inventory["state"] in {"NO_POSITION", "FLAT_MODELED", "FLAT_ACTUAL"} and remaining != 0:
        errors.add("FLAT_OR_NO_POSITION_REQUIRES_ZERO_INVENTORY")
    if inventory["state"] in {"PARTIAL_OPEN", "UNRESOLVED_REQUIRES_RECOVERY"} and (remaining is None or remaining <= 0):
        errors.add("PARTIAL_OR_UNRESOLVED_INVENTORY_REQUIRES_POSITIVE_REMAINDER")
    if inventory["state"] == "UNRESOLVED_REQUIRES_RECOVERY":
        lower = as_int(inventory["recovery_lower_atomic"])
        upper = as_int(inventory["recovery_upper_atomic"])
        if lower is None or upper is None or lower > upper:
            errors.add("RECOVERY_BOUNDS_INVALID")
    if scenario["fill"]["state"] == "PARTIAL_MODELED" and inventory["state"] in {"FLAT_MODELED", "FLAT_ACTUAL", "NO_POSITION"}:
        errors.add("PARTIAL_OR_UNRESOLVED_INVENTORY_CANNOT_BE_FLAT")
    if "UNKNOWN" in terminal_states and inventory["state"] != "UNRESOLVED_REQUIRES_RECOVERY":
        errors.add("UNKNOWN_TERMINAL_REQUIRES_RECOVERY_INVENTORY")

    fill = scenario["fill"]
    net_return = scenario["net_return"]
    classification = net_return["classification"]
    if classification == "NOT_COMPUTABLE":
        if net_return["amount_atomic"] is not None or net_return["currency"] is not None:
            errors.add("INCOMPLETE_MODEL_CANNOT_EMIT_NUMERIC_NETRETURN")
    if classification == "MODELED":
        if cashflow["state"] != "MODELED_COMPLETE" or inventory["state"] != "FLAT_MODELED":
            errors.add("MODELED_NETRETURN_REQUIRES_COMPLETE_MODELED_CASHFLOW_AND_FLAT_INVENTORY")
        if "UNKNOWN" in terminal_states or any(fee["charge_state"] == "UNKNOWN" for fee in fees):
            errors.add("INCOMPLETE_MODEL_CANNOT_EMIT_NUMERIC_NETRETURN")
    if classification == "OBSERVED":
        if terminal_states == {"NOT_ATTEMPTED"}:
            errors.add("QUOTE_ONLY_CANNOT_BE_OBSERVED_NETRETURN")
        if fill["state"] != "ACTUAL_RECONCILED" or not fill["fill_reference_ids"]:
            errors.add("OBSERVED_NETRETURN_REQUIRES_ACTUAL_FILL")
        if cashflow["state"] != "SETTLED_COMPLETE" or not cashflow["settled_reference_ids"]:
            errors.add("OBSERVED_NETRETURN_REQUIRES_SETTLED_CASHFLOW")
        if inventory["state"] != "FLAT_ACTUAL":
            errors.add("OBSERVED_NETRETURN_REQUIRES_FLAT_ACTUAL_INVENTORY")
        if not scenario["accounting_closed"]:
            errors.add("OBSERVED_NETRETURN_REQUIRES_ACCOUNTING_CLOSURE")
    if cashflow["state"] in {"NOT_OBSERVED", "UNRESOLVED"} and classification != "NOT_COMPUTABLE":
        errors.add("INCOMPLETE_MODEL_CANNOT_EMIT_NUMERIC_NETRETURN")
    if classification in {"MODELED", "OBSERVED"}:
        trade = as_int(cashflow["trade_cashflow_atomic"])
        infrastructure = as_int(cashflow["infrastructure_cashflow_atomic"])
        net_amount = as_int(net_return["amount_atomic"])
        if (
            cashflow["currency"] != net_return["currency"]
            or trade is None
            or infrastructure is None
            or net_amount is None
            or trade + infrastructure != net_amount
        ):
            errors.add("NETRETURN_REQUIRES_NORMALIZED_ACCOUNTING_CURRENCY")

    return errors


class Task26ExecutionCostAndNetReturnContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.config_bytes = CONFIG_PATH.read_bytes()
        cls.config = yaml.safe_load(cls.config_bytes)
        cls.schema_bytes = SCHEMA_PATH.read_bytes()
        cls.schema = json.loads(cls.schema_bytes)
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_artifacts_are_exactly_content_bound_and_normalized(self) -> None:
        for payload in (self.contract_bytes, self.config_bytes, self.schema_bytes, self.fixture_bytes):
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r\n", payload)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_fixture_passes_draft_2020_12_schema(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        errors = sorted(self.validator.iter_errors(self.fixture), key=str)
        self.assertEqual([error.message for error in errors], [])

    def test_fixture_inventory_and_scope_are_exact(self) -> None:
        self.assertEqual(self.fixture["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")
        self.assertEqual(len(self.fixture["scenarios"]), 9)
        self.assertEqual(len(self.fixture["adversarial_mutations"]), 12)
        scenario_ids = [row["scenario_id"] for row in self.fixture["scenarios"]]
        mutation_ids = [row["mutation_id"] for row in self.fixture["adversarial_mutations"]]
        self.assertEqual(len(scenario_ids), len(set(scenario_ids)))
        self.assertEqual(len(mutation_ids), len(set(mutation_ids)))
        self.assertEqual({row["source_scope"] for row in self.fixture["scenarios"]}, {"SYNTHETIC_GOLDEN"})

    def test_all_valid_golden_scenarios_pass_independent_semantics(self) -> None:
        for scenario in self.fixture["scenarios"]:
            with self.subTest(scenario_id=scenario["scenario_id"]):
                self.assertEqual(semantic_errors(scenario), set())

    def test_adversarial_matrix_rejects_all_required_mutations(self) -> None:
        scenarios = {row["scenario_id"]: row for row in self.fixture["scenarios"]}
        expected = set(self.config["golden_matrix"]["required_rejections"])
        actual = {row["expected_error"] for row in self.fixture["adversarial_mutations"]}
        self.assertEqual(actual, expected)
        for mutation in self.fixture["adversarial_mutations"]:
            with self.subTest(mutation_id=mutation["mutation_id"]):
                changed = copy.deepcopy(scenarios[mutation["base_scenario_id"]])
                apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
                schema_errors = sorted(self.validator.iter_errors({
                    "fixture_kind": self.fixture["fixture_kind"],
                    "contract_id": self.fixture["contract_id"],
                    "task_id": self.fixture["task_id"],
                    "atom": self.fixture["atom"],
                    "scenarios": [changed],
                    "adversarial_mutations": self.fixture["adversarial_mutations"][:1],
                }), key=str)
                self.assertEqual([error.message for error in schema_errors], [])
                self.assertIn(mutation["expected_error"], semantic_errors(changed))

    def test_quote_attempt_fill_cashflow_and_netreturn_are_not_a_promotion_ladder(self) -> None:
        rows = {row["scenario_id"]: row for row in self.fixture["scenarios"]}
        quote_only = rows["quote_only_not_computable"]
        self.assertEqual(quote_only["attempts"][0]["terminal_state"], "NOT_ATTEMPTED")
        self.assertEqual(quote_only["fill"]["state"], "NOT_OBSERVED")
        self.assertEqual(quote_only["net_return"]["classification"], "NOT_COMPUTABLE")
        observed = rows["synthetic_observed_complete_reconciliation"]
        self.assertEqual(observed["fill"]["state"], "ACTUAL_RECONCILED")
        self.assertTrue(observed["fill"]["fill_reference_ids"])
        self.assertEqual(observed["cashflow"]["state"], "SETTLED_COMPLETE")
        self.assertTrue(observed["cashflow"]["settled_reference_ids"])

    def test_retry_unknown_and_partial_inventory_rules_are_explicit(self) -> None:
        rows = {row["scenario_id"]: row for row in self.fixture["scenarios"]}
        unknown = rows["unknown_terminal_blocks_retry_and_closure"]
        self.assertFalse(unknown["retry_permitted"])
        self.assertFalse(unknown["accounting_closed"])
        self.assertEqual(unknown["inventory"]["state"], "UNRESOLVED_REQUIRES_RECOVERY")
        partial = rows["partial_fill_residual_inventory"]
        self.assertEqual(partial["inventory"]["state"], "PARTIAL_OPEN")
        self.assertGreater(int(partial["inventory"]["remaining_inventory_atomic"]), 0)
        retry = rows["retry_chain_no_double_count"]
        self.assertEqual(retry["attempts"][1]["retry_of"], retry["attempts"][0]["attempt_id"])
        self.assertNotEqual(retry["fees"][0]["fee_id"], retry["fees"][1]["fee_id"])

    def test_fee_and_infrastructure_rules_are_separate(self) -> None:
        rows = {row["scenario_id"]: row for row in self.fixture["scenarios"]}
        modeled = rows["modeled_flat_round_trip_all_costs"]
        quote_fee = modeled["fees"][0]
        self.assertTrue(quote_fee["included_in_quote"])
        self.assertFalse(quote_fee["included_in_trade_cashflow"])
        dropped = rows["dropped_attempt_charge_unknown"]
        self.assertEqual(dropped["fees"][0]["charge_state"], "UNKNOWN")
        self.assertIsNone(dropped["fees"][0]["amount_atomic"])
        infrastructure = rows["infrastructure_cost_separate_from_trade_cashflow"]
        host_fee = next(fee for fee in infrastructure["fees"] if fee["component_kind"] == "INFRASTRUCTURE")
        self.assertFalse(host_fee["included_in_trade_cashflow"])
        self.assertIn(host_fee["fee_id"], infrastructure["cashflow"]["fee_ids_in_infrastructure_cashflow"])
        for scenario in self.fixture["scenarios"]:
            with self.subTest(scenario_id=scenario["scenario_id"]):
                self.assertEqual(scenario["cashflow"]["currency"], "SYNTHETIC_USDC")
                self.assertEqual(scenario["cashflow"]["decimals"], 6)

    def test_entry_bindings_managed_write_set_and_authority_are_closed(self) -> None:
        entry = self.config["entry_gate"]
        self.assertEqual(entry["accepted_main_commit"], "a1c7e40f4febeee78ab544ee89edf248c4cd0454")
        self.assertEqual(entry["accepted_main_tree"], "b4280469913ae6463a9fd3f97870f62c594795d8")
        self.assertEqual(entry["source_activation_receipt"], "ACTIVATION_CONFIRMED_USER_SMOKE")
        self.assertEqual(entry["active_time_gate"], "NONE")
        self.assertEqual(self.config["managed_write_set"], EXPECTED_WRITE_SET)
        authority = self.config["authority"]
        for key in ("r2_value_reads", "r2_paths_opened", "r3_value_or_path_reads", "holdout_consumption_records_added", "provider_api_rpc_wss_calls", "wallet_signer_transaction_actions", "cash_spend_usd_cents"):
            self.assertEqual(authority[key], 0, key)
        for key in ("credential_use", "dependency_changes", "project_source_changes", "catalog_or_registry_mutation", "deploy_or_release", "commit", "push", "pull_request", "merge"):
            self.assertFalse(authority[key], key)
        self.assertFalse(self.config["next_boundary"]["authorized_by_a2"])

    def test_frozen_upstream_bindings_are_exact(self) -> None:
        for binding in self.config["frozen_upstream_bindings"]:
            path = ROOT / binding["path"]
            with self.subTest(path=binding["path"]):
                self.assertEqual(path.stat().st_size, binding["bytes"])
                self.assertEqual(sha256(path), binding["sha256"])

    def test_acceptance_receipt_binds_artifacts_and_measured_zeroes(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS_VALIDATED_CONTRACT_ONLY")
        expected_paths = {
            "contract": CONTRACT_PATH,
            "config": CONFIG_PATH,
            "schema": SCHEMA_PATH,
            "fixture": FIXTURE_PATH,
            "test": Path(__file__).resolve(),
        }
        for name, path in expected_paths.items():
            with self.subTest(artifact=name):
                self.assertEqual(self.receipt["artifact_bindings"][name]["path"], str(path.relative_to(ROOT)).replace("\\", "/"))
                self.assertEqual(self.receipt["artifact_bindings"][name]["sha256"], sha256(path))
        measured = self.receipt["measured_boundary"]
        self.assertEqual(measured["synthetic_scenarios_validated"], 9)
        self.assertEqual(measured["adversarial_mutations_rejected"], 12)
        for key in ("r2_values_read", "r2_paths_opened", "r3_values_or_paths_read", "holdout_consumption_records_added", "provider_api_rpc_wss_calls", "dependency_changes", "project_source_changes", "catalog_or_registry_mutations", "wallet_signer_transaction_actions", "cash_spend_usd_cents"):
            self.assertEqual(measured[key], 0, key)

    def test_contract_contains_decision_critical_nonclaims(self) -> None:
        for marker in (
            "`QUOTE` does not imply\n`ATTEMPT`",
            "`UNKNOWN` blocks retry and accounting closure",
            "never both",
            "Observed NetReturn requires complete settled trading cashflow",
            "R3 remains sealed",
            "canonical TASK-26 `DONE`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_tracked_artifacts_have_no_secret_machine_path_or_r2_r3_value_surface(self) -> None:
        texts = {
            "contract": self.contract,
            "config": self.config_bytes.decode("utf-8"),
            "schema": self.schema_bytes.decode("utf-8"),
            "fixture": self.fixture_bytes.decode("utf-8"),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\s]+"),
            "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "credential_assignment": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[\"'][^\"']+[\"']"),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))
        fixture_text = self.fixture_bytes.decode("utf-8").lower()
        self.assertNotIn("t21_r2", fixture_text)
        self.assertNotIn("r3", fixture_text)
        self.assertNotIn("local/", fixture_text)


if __name__ == "__main__":
    unittest.main()
