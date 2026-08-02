from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task25_outcome_label_and_pit_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task25_outcome_label_and_pit_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task25_outcome_evidence.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task25/outcome_label_contract_v1.json"
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/task25/a2_outcome_label_and_pit_contract_acceptance_v1.json"
)
CATALOG_MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"

EXPECTED_CONTRACT_SHA256 = (
    "04e4397e69d554463a09564bdb1cbbb2ac41ce8662277d05e4565c178e94c801"
)
EXPECTED_CONFIG_SHA256 = (
    "18a605cc3380d060b6e443430e33b22b49a59fca6d20ddc28078faec2ae5a483"
)
EXPECTED_SCHEMA_SHA256 = (
    "d8c4cae7f5e8004a6d7606acc78e344186bf24a95ccb1696cce5575979c4aff3"
)
EXPECTED_FIXTURE_SHA256 = (
    "269896634d1225f9b606cc12c13fcea6e624143bfe35413c3ad1acf9b8dcb917"
)
ORIGINAL_A2_TEST_SHA256 = (
    "998380f55482fa9a7be5506be133b7432519635af6fcd54e9f9e338d3332fe43"
)

EXPECTED_WRITE_SET = [
    "docs/contracts/task25_outcome_label_and_pit_contract_v1.md",
    "configs/task25_outcome_label_and_pit_contract_v1.yaml",
    "catalog/schemas/task25_outcome_evidence.schema.json",
    "tests/fixtures/task25/outcome_label_contract_v1.json",
    "tests/test_task25_outcome_label_and_pit_contract.py",
    "docs/evidence/task25/a2_outcome_label_and_pit_contract_acceptance_v1.json",
]

EXPECTED_ADVERSARIAL_ERRORS = {
    "TOUCH_DOES_NOT_IMPLY_FILLABLE",
    "QUOTE_DOES_NOT_IMPLY_SETTLEMENT",
    "MISSING_IS_NOT_ZERO",
    "SPARSE_ABSENCE_CANNOT_REFUTE_CONTINUOUS_TOUCH",
    "SPARSE_PANEL_CANNOT_CLAIM_CONTINUOUS_PATH",
    "PROVIDER_FAILURE_IS_NOT_NO_ROUTE",
    "PIT_ORDER_INVALID",
    "EXACT_NOTIONAL_REQUIRED",
    "STALE_QUOTE_CANNOT_SUPPORT_FILLABLE",
    "ACTUAL_EXECUTION_REFERENCES_REQUIRED",
    "SETTLED_CASHFLOW_REQUIRED",
    "UNRESOLVED_INVENTORY_MUST_BE_POSITIVE",
}

EXPECTED_UPSTREAM_BINDINGS = {
    "schemas/schema_v1.sql": (
        "eae9d1544b11cffc03afba1e263153168a11dc6f648df9117a55a4cae5d23f09",
        28962,
    ),
    "docs/contracts/jupiter_quote_observation_contract_v1.md": (
        "86e7a5264ae6a2cde3e95fe450f853d9e2cda01623164f39bde55162a6c3aa64",
        8913,
    ),
    "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json": (
        "29c1ad28d06430b74864b745ef50bf0315fcbfcfb5a7534e54b1692a3f15a019",
        9593,
    ),
    "docs/evidence/task23/a3_projection_v1_attempt_02/projection_manifest_v1.json": (
        "06702bba94e9a895d340598f2fa722eeed6dd5ce9cd324d699918ac6a8a95ff9",
        6658,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def apply_json_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target: Any = document
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = copy.deepcopy(value)


def semantic_errors(record: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    label = record["label"]
    assessment = record["assessment"]
    basis = record["evidence_basis"]
    route = record["route_state"]
    fill = record["fill_state"]
    cashflow = record["cashflow_state"]
    path_state = record["path_state"]
    claim_scope = record["claim_scope"]
    flags = set(record["quality_flags"])
    lineage = record["lineage"]

    if assessment in {"UNKNOWN", "NOT_APPLICABLE"} and (
        record["value_decimal"] is not None or record["unit"] is not None
    ):
        errors.add("MISSING_IS_NOT_ZERO")

    times = record["timestamps"]
    ordered = [
        parse_time(times["observed_at"]),
        parse_time(times["first_reliable_available_at"]),
        parse_time(times["available_to_strategy_at"]),
        parse_time(times["ingested_at"]),
    ]
    if any(left > right for left, right in zip(ordered, ordered[1:])):
        errors.add("PIT_ORDER_INVALID")
    if times["event_at"] is not None and parse_time(times["event_at"]) > ordered[0]:
        errors.add("PIT_ORDER_INVALID")
    if parse_time(times["measured_as_of"]) > parse_time(
        times["available_to_strategy_at"]
    ):
        errors.add("PIT_ORDER_INVALID")

    if label == "TOUCH":
        if basis not in {"REFERENCE_PRICE_PATH", "DISCRETE_PANEL_GRID"}:
            errors.add("TOUCH_BASIS_INVALID")
        if record["notional"] is not None or route != "NOT_APPLICABLE":
            errors.add("TOUCH_EXECUTION_STATE_FORBIDDEN")
        if (
            basis == "DISCRETE_PANEL_GRID"
            and "NO_OBSERVED_THRESHOLD_CROSS" in flags
            and assessment == "REFUTED"
        ):
            errors.add("SPARSE_ABSENCE_CANNOT_REFUTE_CONTINUOUS_TOUCH")

    if label in {"FILLABLE", "QUOTE_EXIT"}:
        if basis != "CONTEMPORANEOUS_QUOTE":
            errors.add("TOUCH_DOES_NOT_IMPLY_FILLABLE")
        notional = record["notional"]
        if notional is None:
            errors.add("EXACT_NOTIONAL_REQUIRED")
        if assessment == "SUPPORTED":
            if route == "STALE_QUOTE" or (
                notional is not None
                and notional["observed_age_ms"] > notional["freshness_max_age_ms"]
            ):
                errors.add("STALE_QUOTE_CANNOT_SUPPORT_FILLABLE")
            elif route != "QUOTE_AVAILABLE":
                errors.add("QUOTE_STATE_CANNOT_SUPPORT_FILLABILITY")
        if assessment == "REFUTED" and route != "NO_ROUTE":
            errors.add("NO_ROUTE_REQUIRED_FOR_REFUTATION")
        if route in {"PROVIDER_ERROR", "INVALID_RESPONSE", "TIMEOUT", "STALE_QUOTE"}:
            if assessment != "UNKNOWN":
                errors.add("QUOTE_FAILURE_MUST_REMAIN_UNKNOWN")
        if label == "QUOTE_EXIT" and assessment == "SUPPORTED":
            if record["inventory"]["state"] in {"FLAT", "RECOVERED"}:
                errors.add("QUOTE_EXIT_DOES_NOT_IMPLY_FLAT")

    if "PROVIDER_ERROR_OBSERVED" in flags and route == "NO_ROUTE":
        errors.add("PROVIDER_FAILURE_IS_NOT_NO_ROUTE")

    if label == "REALIZED_VWAP":
        if basis == "CONTEMPORANEOUS_QUOTE" or (
            fill != "ACTUAL_FILLS_RECONCILED" and route == "QUOTE_AVAILABLE"
        ):
            errors.add("QUOTE_DOES_NOT_IMPLY_SETTLEMENT")
        if assessment == "SUPPORTED":
            if basis != "ACTUAL_RECONCILED_FILLS" or fill != "ACTUAL_FILLS_RECONCILED":
                errors.add("ACTUAL_FILLS_REQUIRED")
            if not lineage["execution_attempt_ids"]:
                errors.add("ACTUAL_EXECUTION_REFERENCES_REQUIRED")

    if label == "NET" and assessment == "SUPPORTED":
        if (
            basis != "SETTLED_CASHFLOW"
            or cashflow != "SETTLED_COMPLETE"
            or not lineage["cashflow_reference_ids"]
        ):
            errors.add("SETTLED_CASHFLOW_REQUIRED")

    if label == "PATH_RISK":
        if basis not in {
            "REFERENCE_PRICE_PATH",
            "DISCRETE_PANEL_GRID",
            "PATH_STATE_EVIDENCE",
        }:
            errors.add("PATH_RISK_BASIS_INVALID")
        if path_state == "SPARSE_DISCRETE" and claim_scope == "CONTINUOUS_PATH_METRICS":
            errors.add("SPARSE_PANEL_CANNOT_CLAIM_CONTINUOUS_PATH")

    inventory = record["inventory"]
    if inventory["state"] == "UNRESOLVED_REQUIRES_RECOVERY":
        if int(inventory["remaining_inventory_atomic"]) <= 0:
            errors.add("UNRESOLVED_INVENTORY_MUST_BE_POSITIVE")
        lower = Decimal(inventory["recovery_lower_bound_decimal"])
        upper = Decimal(inventory["recovery_upper_bound_decimal"])
        if lower > upper:
            errors.add("RECOVERY_BOUNDS_INVALID")
        if path_state in {"POOL_DEAD", "MISSING_EXIT"} and not inventory["failed_exit_state"]:
            errors.add("FAILED_EXIT_STATE_REQUIRED")

    if record["source_scope"] == "T21_R2_DEVELOPMENT" and label in {
        "REALIZED_VWAP",
        "NET",
    } and assessment == "SUPPORTED":
        errors.add("R2_EXECUTION_OR_CASHFLOW_CLAIM_FORBIDDEN")

    return errors


class Task25OutcomeLabelAndPitContractTests(unittest.TestCase):
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
        cls.catalog_manifest = yaml.safe_load(
            CATALOG_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def test_artifacts_are_exactly_content_bound_and_normalized(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(CONFIG_PATH), EXPECTED_CONFIG_SHA256)
        self.assertEqual(sha256(SCHEMA_PATH), EXPECTED_SCHEMA_SHA256)
        self.assertEqual(sha256(FIXTURE_PATH), EXPECTED_FIXTURE_SHA256)
        for payload in (
            self.contract_bytes,
            self.config_bytes,
            self.schema_bytes,
            self.fixture_bytes,
        ):
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r\n", payload)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_fixture_passes_draft_2020_12_schema(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        errors = sorted(self.validator.iter_errors(self.fixture), key=str)
        self.assertEqual([error.message for error in errors], [])

    def test_fixture_identity_inventory_and_scope_are_exact(self) -> None:
        self.assertEqual(self.fixture["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")
        self.assertEqual(len(self.fixture["records"]), 14)
        self.assertEqual(len(self.fixture["adversarial_mutations"]), 12)
        record_ids = [row["record_id"] for row in self.fixture["records"]]
        case_ids = [row["case_id"] for row in self.fixture["records"]]
        self.assertEqual(len(record_ids), len(set(record_ids)))
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual({row["source_scope"] for row in self.fixture["records"]}, {"SYNTHETIC_GOLDEN"})

    def test_all_valid_golden_records_pass_independent_semantics(self) -> None:
        for record in self.fixture["records"]:
            with self.subTest(record_id=record["record_id"]):
                self.assertEqual(semantic_errors(record), set())

    def test_adversarial_golden_matrix_rejects_all_required_mutations(self) -> None:
        records = {row["record_id"]: row for row in self.fixture["records"]}
        actual_expected = {
            mutation["expected_error"]
            for mutation in self.fixture["adversarial_mutations"]
        }
        self.assertEqual(actual_expected, EXPECTED_ADVERSARIAL_ERRORS)
        for mutation in self.fixture["adversarial_mutations"]:
            with self.subTest(mutation_id=mutation["mutation_id"]):
                changed = copy.deepcopy(records[mutation["base_record_id"]])
                apply_json_pointer(
                    changed,
                    mutation["json_pointer"],
                    mutation["replacement"],
                )
                self.assertIn(
                    mutation["expected_error"],
                    semantic_errors(changed),
                )

    def test_label_taxonomy_is_complete_and_not_a_promotion_ladder(self) -> None:
        by_label: dict[str, list[dict[str, Any]]] = {}
        for row in self.fixture["records"]:
            by_label.setdefault(row["label"], []).append(row)
        self.assertEqual(
            set(by_label),
            {"TOUCH", "FILLABLE", "QUOTE_EXIT", "REALIZED_VWAP", "NET", "PATH_RISK"},
        )
        touch = next(row for row in by_label["TOUCH"] if row["assessment"] == "SUPPORTED")
        self.assertEqual(touch["route_state"], "NOT_APPLICABLE")
        self.assertEqual(touch["fill_state"], "NOT_APPLICABLE")
        fillable = next(row for row in by_label["FILLABLE"] if row["assessment"] == "SUPPORTED")
        self.assertEqual(fillable["fill_state"], "ACTUAL_FILLS_NOT_OBSERVED")

    def test_sparse_panels_do_not_create_false_negative_or_continuous_path(self) -> None:
        rows = {row["case_id"]: row for row in self.fixture["records"]}
        no_cross = rows["touch_sparse_no_cross_unknown"]
        self.assertEqual(no_cross["assessment"], "UNKNOWN")
        self.assertIsNone(no_cross["value_decimal"])
        self.assertEqual(no_cross["path_state"], "SPARSE_DISCRETE")
        path = rows["path_risk_sparse_grid_partial"]
        self.assertEqual(path["claim_scope"], "DISCRETE_PATH_GRID")
        self.assertNotEqual(path["claim_scope"], "CONTINUOUS_PATH_METRICS")

    def test_quote_claims_require_exact_notional_and_preserve_route_states(self) -> None:
        quote_rows = [
            row
            for row in self.fixture["records"]
            if row["label"] in {"FILLABLE", "QUOTE_EXIT"}
        ]
        for row in quote_rows:
            with self.subTest(record_id=row["record_id"]):
                self.assertIsNotNone(row["notional"])
                self.assertEqual(row["evidence_basis"], "CONTEMPORANEOUS_QUOTE")
        states = {row["route_state"] for row in quote_rows}
        self.assertTrue({"QUOTE_AVAILABLE", "NO_ROUTE", "PROVIDER_ERROR", "STALE_QUOTE"}.issubset(states))
        failures = [row for row in quote_rows if row["route_state"] in {"PROVIDER_ERROR", "STALE_QUOTE"}]
        self.assertTrue(all(row["assessment"] == "UNKNOWN" for row in failures))

    def test_realized_and_net_require_actual_truth_owners(self) -> None:
        rows = {row["case_id"]: row for row in self.fixture["records"]}
        realized = rows["realized_vwap_supported_reconciled_fills"]
        self.assertEqual(realized["evidence_basis"], "ACTUAL_RECONCILED_FILLS")
        self.assertTrue(realized["lineage"]["execution_attempt_ids"])
        quote_only = rows["realized_vwap_unknown_without_fills"]
        self.assertEqual(quote_only["assessment"], "UNKNOWN")
        net_unknown = rows["net_unknown_fee_model_unavailable"]
        self.assertIsNone(net_unknown["value_decimal"])
        net = rows["net_supported_settled_cashflow"]
        self.assertEqual(net["cashflow_state"], "SETTLED_COMPLETE")
        self.assertTrue(net["lineage"]["cashflow_reference_ids"])

    def test_missing_exit_and_pool_death_retain_recovery_inventory(self) -> None:
        unresolved = [
            row
            for row in self.fixture["records"]
            if row["inventory"]["state"] == "UNRESOLVED_REQUIRES_RECOVERY"
        ]
        self.assertEqual({row["path_state"] for row in unresolved}, {"MISSING_EXIT", "POOL_DEAD"})
        for row in unresolved:
            inventory = row["inventory"]
            self.assertGreater(int(inventory["remaining_inventory_atomic"]), 0)
            self.assertLessEqual(
                Decimal(inventory["recovery_lower_bound_decimal"]),
                Decimal(inventory["recovery_upper_bound_decimal"]),
            )

    def test_point_in_time_order_is_valid_for_every_record(self) -> None:
        for row in self.fixture["records"]:
            with self.subTest(record_id=row["record_id"]):
                self.assertNotIn("PIT_ORDER_INVALID", semantic_errors(row))

    def test_entry_base_source_activation_and_catalog_checkpoint_are_exact(self) -> None:
        entry = self.config["entry_gate"]
        self.assertEqual(entry["accepted_main_commit"], "be15889e103caaf92b7e34c9f98b7fd6378eed2e")
        self.assertEqual(entry["accepted_main_tree"], "ed5d2a788080f1535074e78e0f66ffbe07afbab8")
        self.assertEqual(entry["source_activation_receipt"], "ACTIVATION_CONFIRMED_USER_SMOKE")
        self.assertEqual(entry["source_manifest_version"], "4.1")
        self.assertEqual(entry["active_time_gate"], "NONE")
        self.assertEqual(entry["catalog_checkpoint"]["version"], "0.29.2")

    def test_managed_write_set_and_authority_are_closed(self) -> None:
        self.assertEqual(self.config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(len(set(self.config["managed_write_set"])), 6)
        authority = self.config["authority"]
        for key in (
            "r2_value_reads",
            "r3_value_or_path_reads",
            "provider_api_rpc_wss_calls",
            "entity_graph_reads",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(authority[key], 0, key)
        for key in (
            "credential_use",
            "dependency_changes",
            "project_source_changes",
            "catalog_or_registry_mutation",
            "deploy_or_release",
            "commit",
            "push",
            "pull_request",
            "merge",
        ):
            self.assertFalse(authority[key], key)
        self.assertFalse(self.config["next_boundary"]["authorized_by_a2"])

    def test_upstream_bindings_exist_with_exact_hashes_and_sizes(self) -> None:
        actual = {
            item["path"]: (item["sha256"], item["bytes"])
            for item in self.config["frozen_upstream_bindings"]
        }
        self.assertEqual(actual, EXPECTED_UPSTREAM_BINDINGS)
        for relative_path, (expected_hash, expected_size) in actual.items():
            path = ROOT / relative_path
            self.assertEqual(path.stat().st_size, expected_size, relative_path)
            self.assertEqual(sha256(path), expected_hash, relative_path)

    def test_schema_registration_is_deferred_from_a2_to_a6(self) -> None:
        self.assertGreaterEqual(
            tuple(map(int, self.catalog_manifest["catalog_version"].split("."))),
            (0, 30, 0),
        )
        self.assertGreaterEqual(
            self.catalog_manifest["current_checkpoint"]["schemas"], 8
        )
        self.assertIn(
            "catalog/schemas/task25_outcome_evidence.schema.json",
            self.catalog_manifest["root_resolver"]["schemas"],
        )
        impact = self.config["catalog_impact"]
        self.assertFalse(impact["root_resolver_changed_in_a2"])
        self.assertFalse(impact["asset_registration_changed_in_a2"])

    def test_acceptance_receipt_binds_artifacts_and_measured_zeroes(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS_VALIDATED_CONTRACT_ONLY")
        expected = {
            "contract": EXPECTED_CONTRACT_SHA256,
            "config": EXPECTED_CONFIG_SHA256,
            "schema": EXPECTED_SCHEMA_SHA256,
            "fixture": EXPECTED_FIXTURE_SHA256,
            "test": ORIGINAL_A2_TEST_SHA256,
        }
        actual = {
            key: value["sha256"]
            for key, value in self.receipt["artifact_bindings"].items()
        }
        self.assertEqual(actual, expected)
        measured = self.receipt["measured_boundary"]
        self.assertEqual(measured["synthetic_records_validated"], 14)
        self.assertEqual(measured["adversarial_mutations_rejected"], 12)
        for key in (
            "r2_values_read",
            "r2_paths_opened",
            "r3_values_or_paths_read",
            "holdout_consumption_records_added",
            "provider_api_rpc_wss_calls",
            "dependency_changes",
            "project_source_changes",
            "entity_graph_values_read",
            "catalog_or_registry_mutations",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(measured[key], 0, key)

    def test_contract_contains_decision_critical_nonclaims(self) -> None:
        for marker in (
            "`TOUCH` does not imply `FILLABLE`",
            "a quote does not imply `REALIZED_VWAP`",
            "missing evidence does not imply the numeric value zero",
            "continuous MAE/MFE",
            "`UNRESOLVED_REQUIRES_RECOVERY`",
            "R3 remains default-deny and unopened",
            "canonical TASK-25 `DONE`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_tracked_artifacts_have_no_secret_machine_path_or_entity_field(self) -> None:
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
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))
        fixture_text = self.fixture_bytes.decode("utf-8").lower()
        self.assertNotIn("entity_", fixture_text)
        self.assertNotIn("r3", fixture_text)
        self.assertNotIn("local/", fixture_text)


if __name__ == "__main__":
    unittest.main()
