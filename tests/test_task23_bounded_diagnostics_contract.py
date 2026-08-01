from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path, PurePosixPath

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task23_bounded_diagnostics_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task23_bounded_diagnostics_v1.yaml"

EXPECTED_CONTRACT_SHA256 = "0b8327b9926506a4ea57afee291a7217222ff7dd5aa10c77044db6dcaba64780"
EXPECTED_CONFIG_SHA256 = "33cd3cd81833d578c0a3be240fa443f196a5b3dca946f4ba8315749c7b67f0bf"

EXPECTED_INPUTS = {
    "configs/task22_task23_consumer_time_profile_v1.yaml": (
        "71a253d8b94f32a954d0195d2d544fdfb94e1b41ae680313bb48caa115ed01a0",
        5118,
    ),
    "docs/evidence/task22/dataset_split_manifest_v2.json": (
        "973a9ff6dd2a376e62dee9289a57cbb62f06c8efb5a619fa6b7b2a7914dd0683",
        7266,
    ),
    "docs/evidence/task22/holdout_access_ledger_v2.json": (
        "2282e5d1eac09a0ce940a5700f04b03ff4d75fc9cd4d65e08e5fe7deda88ca51",
        1852,
    ),
    "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json": (
        "29c1ad28d06430b74864b745ef50bf0315fcbfcfb5a7534e54b1692a3f15a019",
        9593,
    ),
    "src/solana_alpha_lab/task21_event_triggered_panel_capture.py": (
        "cbce387163a5625a0be124559987e50577375c517b5939db838e4660236aa8c4",
        9741,
    ),
    "src/solana_alpha_lab/task21_event_triggered_followup_capture.py": (
        "06783b78eba49d8dc85e28e47de12c310cf2a07f194abab4ad4b92fcfa35b264",
        36124,
    ),
    "src/solana_alpha_lab/jupiter_quote_logger.py": (
        "811f08e43eb26c99ef93dccfade372cbae5adb1c1ee718c7ff6d3ce543a9d507",
        39800,
    ),
    "src/solana_alpha_lab/contracts/schema_v1.py": (
        "ef9435fc0aa6df1d880714e97d3312e068dc82806a8c6ba1ed2d74c9929684ad",
        32794,
    ),
    "registries/global_trial_ledger.yaml": (
        "41b2f3cd1e2303f90318d0295c36c390999c7539031cb52db1a03779be56b671",
        179,
    ),
}

EXPECTED_MEMBERS = [
    "T21-WATCH-29e2b75994975253bd74",
    "T21-WATCH-6f21dec76d05f5831216",
    "T21-WATCH-61ce24fc3fa04e3eaba7",
]

EXPECTED_MANAGED_WRITE_SET = [
    "docs/contracts/task23_bounded_diagnostics_contract_v1.md",
    "configs/task23_bounded_diagnostics_v1.yaml",
    "tests/test_task23_bounded_diagnostics_contract.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task23BoundedDiagnosticsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.config_bytes = CONFIG_PATH.read_bytes()
        cls.config = yaml.safe_load(cls.config_bytes)

    def test_contract_and_config_are_content_bound(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(CONFIG_PATH), EXPECTED_CONFIG_SHA256)
        self.assertTrue(self.contract_bytes.endswith(b"\n"))
        self.assertTrue(self.config_bytes.endswith(b"\n"))
        self.assertNotIn(b"\r\n", self.contract_bytes)
        self.assertNotIn(b"\r\n", self.config_bytes)
        self.assertFalse(self.contract_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(self.config_bytes.startswith(b"\xef\xbb\xbf"))

    def test_entry_gate_is_bound_to_accepted_main(self) -> None:
        entry = self.config["entry_gate"]
        self.assertEqual(entry["route_owner"], "LOCAL_WORK_PRIMARY")
        self.assertEqual(entry["execution_route"], "LOCAL_WORK_CODEX")
        self.assertEqual(entry["verdict"], "START_AS_WRITTEN")
        self.assertEqual(entry["source_activation"], "ACTIVATION_CONFIRMED_READBACK")
        self.assertEqual(
            entry["accepted_main_commit"],
            "90575accefbba7da534a6bd89b3652b2644a278b",
        )
        self.assertEqual(
            entry["accepted_main_tree"],
            "f9cdd82ad8df427abe35e577889adaaca22b2d12",
        )
        self.assertEqual(entry["catalog_checkpoint"]["version"], "0.27.1")
        self.assertEqual(entry["catalog_checkpoint"]["assets"], 396)

    def test_frozen_inputs_exist_with_exact_hashes_and_sizes(self) -> None:
        frozen = {
            item["path"]: (item["sha256"], item["bytes"])
            for item in self.config["frozen_inputs"]
        }
        self.assertEqual(frozen, EXPECTED_INPUTS)
        for relative_path, (expected_hash, expected_size) in EXPECTED_INPUTS.items():
            path = ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            if relative_path == "registries/global_trial_ledger.yaml":
                ledger_input = next(
                    item
                    for item in self.config["frozen_inputs"]
                    if item["path"] == relative_path
                )
                self.assertEqual(
                    ledger_input["mutation_policy"],
                    "APPEND_ONLY_AFTER_A2",
                )
                self.assertGreaterEqual(path.stat().st_size, expected_size)
            else:
                self.assertEqual(path.stat().st_size, expected_size, relative_path)
                self.assertEqual(sha256(path), expected_hash, relative_path)

    def test_dataset_identity_is_frozen_before_the_first_read(self) -> None:
        identity = self.config["dataset_identity"]
        self.assertEqual(
            identity,
            {
                "dataset_inventory_sha256": "aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae",
                "split_id": "T22-SPLIT-T21-FROZEN-002",
                "split_manifest_sha256": "973a9ff6dd2a376e62dee9289a57cbb62f06c8efb5a619fa6b7b2a7914dd0683",
                "split_content_sha256": "63b6d63895bdd6d25b68501619bca21e10f476a95ad8d27611f356a26cccee2d",
                "consumer_profile_id": "TASK23-COHORT-DIAGNOSTICS-THREE-PANEL-001",
            },
        )

    def test_population_is_exactly_r2_and_r3_is_fail_closed(self) -> None:
        population = self.config["population"]
        primary = population["primary_development"]
        self.assertEqual(primary["split"], "R2")
        self.assertEqual(primary["batch_id"], "T21-R2")
        self.assertEqual(primary["cluster_count"], 1)
        self.assertEqual(primary["member_count"], 3)
        self.assertEqual(primary["members"], EXPECTED_MEMBERS)

        auxiliary = population["auxiliary_gap_metadata_only"]
        self.assertEqual(auxiliary["split"], "R1")
        self.assertEqual(auxiliary["allowed_use"], "GAP_AND_COVERAGE_METADATA_ONLY")
        self.assertFalse(auxiliary["value_read"])
        self.assertFalse(auxiliary["pool_with_primary"])

        self.assertEqual(population["validation"]["split"], "NONE")
        self.assertEqual(population["validation"]["member_count"], 0)
        self.assertFalse(population["validation"]["value_read"])

        holdout = population["untouched_holdout"]
        self.assertEqual(holdout["split"], "R3")
        self.assertEqual(holdout["batch_id"], "T21-R3")
        self.assertEqual(holdout["state"], "UNTOUCHED")
        self.assertEqual(holdout["access"], "DENY")
        for key in (
            "path_discovery",
            "value_read",
            "outcome_read",
            "statistics",
            "joins",
            "derived_inspection",
            "ledger_mutation_in_a2",
        ):
            self.assertFalse(holdout[key], key)

    def test_r2_roots_are_exact_and_cannot_route_to_r1_r3_or_outcomes(self) -> None:
        boundary = self.config["r2_read_boundary"]
        self.assertFalse(boundary["value_read_in_a2"])
        self.assertEqual(boundary["allowed_value_filename"], "raw_events.jsonl")
        roots = boundary["allowed_roots_after_a3_pre_read_receipt"]
        self.assertEqual(len(roots), 3)
        for root in roots:
            pure = PurePosixPath(root)
            self.assertFalse(pure.is_absolute())
            self.assertTrue(root.startswith("local/task21_forward/final_cohort/r2/"))
            lowered = f"/{root.lower().strip('/')}/"
            self.assertNotIn("/r1/", lowered)
            self.assertNotIn("/r3/", lowered)
            self.assertNotIn("outcomes", lowered)
        bindings = boundary["root_bindings"]
        self.assertEqual([item["panel_id"] for item in bindings], ["P0", "P1", "P2"])
        self.assertEqual([item["root"] for item in bindings], roots)
        self.assertEqual(
            set(boundary["acceptance_receipts"]),
            {"P0", "P1", "P2"},
        )

    def test_diagnostic_questions_and_decisions_are_closed(self) -> None:
        self.assertEqual(
            [item["id"] for item in self.config["diagnostic_questions"]],
            [
                "Q1_PANEL_COMPLETENESS",
                "Q2_ROUTE_AVAILABILITY",
                "Q3_QUOTE_NOTIONAL_CAPACITY_PROXY",
                "Q4_ACTUAL_TIME_CHANGE",
                "Q5_INFORMATION_LIMITS",
            ],
        )
        self.assertEqual(
            self.config["owner_decision"]["allowed_terminal_decisions"],
            [
                "DIAGNOSTICS_READY_WITH_LIMITATIONS",
                "EXTEND_EVIDENCE",
                "REDESIGN_DATA",
                "STOP_NO_INFORMATION",
            ],
        )
        self.assertIn(
            "POPULATION_GENERALIZATION",
            self.config["owner_decision"]["forbidden_claims"],
        )

    def test_time_semantics_use_actual_timestamps_only(self) -> None:
        semantics = self.config["time_semantics"]
        self.assertEqual(semantics["window_ids"], ["P0", "P1", "P2"])
        self.assertFalse(semantics["window_ids_are_nominal_horizons"])
        self.assertEqual(semantics["elapsed_unit"], "seconds")
        self.assertEqual(
            semantics["required_timestamp_fields"],
            [
                "requested_at",
                "response_at",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            ],
        )
        self.assertEqual(
            semantics["ordering_policy"],
            "INVALID_ORDER_IS_TYPED_FAILURE_NO_IMPUTATION",
        )

    def test_quote_panel_dependency_and_typed_states_are_frozen(self) -> None:
        panel = self.config["quote_panel"]
        self.assertEqual(panel["tested_notionals_usd"], [10, 25, 50, 100])
        self.assertEqual(
            panel["tested_input_atomic"],
            [10000000, 25000000, 50000000, 100000000],
        )
        self.assertEqual(panel["planned_pairs_per_panel"], 4)
        self.assertEqual(panel["maximum_provider_calls_per_panel"], 8)
        self.assertEqual(panel["sell_dependency"], "EXACT_ACCEPTED_BUY_OUTPUT_ATOMIC")
        self.assertEqual(panel["buy_failure_sell_state"], "SELL_NOT_ATTEMPTED")
        self.assertEqual(
            panel["quote_statuses"],
            [
                "QUOTE_AVAILABLE",
                "NO_ROUTE",
                "PROVIDER_ERROR",
                "INVALID_RESPONSE",
                "TIMEOUT",
            ],
        )

    def test_fields_metrics_and_nonclaims_are_explicit(self) -> None:
        fields = self.config["allowed_fields"]
        self.assertIn("raw_content_sha256", fields["envelope"])
        self.assertIn("first_reliable_available_at", fields["envelope"])
        self.assertIn("response_content_sha256", fields["quote_attempt"])
        self.assertIn("inputMint", fields["validated_raw_response"])
        self.assertIn("outputMint", fields["validated_raw_response"])
        self.assertIn("priceImpactPct", fields["validated_raw_response"])
        self.assertIn("routePlan", fields["validated_raw_response"])
        self.assertIn("timeTaken", fields["validated_raw_response"])
        self.assertEqual(
            fields["raw_route_plan_retention"],
            "ROUTE_COUNT_AND_CONTENT_HASH_ONLY",
        )
        self.assertEqual(fields["decimal_policy"], "DECIMAL_STRING_NO_BINARY_FLOAT")

        metrics = {item["id"]: item for item in self.config["derived_metrics"]}
        self.assertEqual(
            metrics["quote_notional_capacity_proxy_usd"]["censoring"],
            "TESTED_GRID_CENSORED",
        )
        self.assertEqual(metrics["roundtrip_quote_retention_bps"]["kind"], "quote_only")
        self.assertEqual(metrics["route_id_continuity"]["kind"], "descriptive_noncausal")

        required_nonclaims = (
            "not pool liquidity",
            "market depth",
            "fillable size",
            "realized VWAP",
            "NetReturn",
            "alpha",
            "owner cashflow",
        )
        for marker in required_nonclaims:
            self.assertIn(marker, self.contract)

    def test_denominators_missingness_and_dependence_are_fail_closed(self) -> None:
        denominators = self.config["denominators"]
        self.assertEqual(
            denominators["required"],
            [
                "planned_panels",
                "observed_panels",
                "planned_buy_legs",
                "observed_buy_legs",
                "eligible_dependent_sell_legs",
                "observed_dependent_sell_legs",
            ],
        )
        self.assertFalse(denominators["missing_is_zero"])
        for state in (
            "NO_ROUTE",
            "PROVIDER_ERROR",
            "INVALID_RESPONSE",
            "TIMEOUT",
            "SELL_NOT_ATTEMPTED",
            "PANEL_MISSING",
            "CAPTURE_DEAD",
            "CAPTURE_STOPPED",
            "TIMESTAMP_INVALID",
        ):
            self.assertIn(state, denominators["retained_states"])
        self.assertTrue(denominators["retain_negative_results"])

        dependence = self.config["dependence"]
        self.assertEqual(dependence["capture_clusters"], 1)
        self.assertEqual(dependence["members"], 3)
        self.assertFalse(dependence["iid_assumption"])
        self.assertEqual(dependence["mode"], "DESCRIPTIVE_ONLY")
        self.assertIn("CONFIDENCE_INTERVALS", dependence["forbidden"])
        self.assertIn("POPULATION_GENERALIZATION", dependence["forbidden"])

    def test_pre_read_and_trial_protocols_precede_result_use(self) -> None:
        pre_read = self.config["pre_read_protocol"]
        self.assertTrue(pre_read["required_before_first_value_open"])
        self.assertTrue(pre_read["write_before_open"])
        self.assertTrue(pre_read["fail_closed_on_write_failure"])
        self.assertFalse(pre_read["a2_receipt_created"])
        self.assertEqual(
            set(pre_read["immutable_receipt_fields"]),
            {
                "contract_sha256",
                "config_sha256",
                "frozen_input_hashes",
                "split",
                "allowed_roots",
                "member_set",
                "actor",
                "reason",
                "timestamp",
                "holdout_ledger_sha256",
                "r3_access_deny",
            },
        )

        trial = self.config["trial_protocol"]
        self.assertEqual(trial["ledger"], "registries/global_trial_ledger.yaml")
        self.assertFalse(trial["ledger_write_in_a2"])
        self.assertTrue(trial["append_only"])
        self.assertTrue(trial["log_before_result_use"])
        self.assertTrue(trial["query_and_config_content_addressed"])
        self.assertTrue(trial["retain_failed_runs"])

    def test_reuse_catalog_and_authority_boundaries(self) -> None:
        reuse = self.config["reuse_route"]
        self.assertEqual(reuse["FORK"], [])
        self.assertEqual(reuse["BUILD"], [])
        self.assertEqual(
            reuse["reuse_gate_status"],
            "PASS_EXISTING_COMPONENTS_SUFFICIENT_FOR_CONTRACT",
        )
        self.assertEqual(
            reuse["full_software_reuse_gate_status"],
            "NOT_TRIGGERED_NO_NEW_DEPENDENCY_OR_EXTERNAL_SERVICE",
        )

        catalog = self.config["catalog"]
        self.assertEqual(catalog["registration_stage"], "A5")
        self.assertFalse(catalog["mutation_in_a2"])

        authority = self.config["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["managed_write_set"], EXPECTED_MANAGED_WRITE_SET)
        self.assertTrue(authority["local_file_write"])
        self.assertTrue(authority["local_offline_test"])
        for key in (
            "network",
            "provider_call",
            "credential_use",
            "drive_read",
            "external_api",
            "dependency_change",
            "raw_value_read",
            "outcome_read",
            "r3_read",
            "wallet_or_signer",
            "cash_or_credits",
            "commit",
            "push",
            "pull_request",
            "merge",
            "next_atom_authorized",
        ):
            self.assertFalse(authority[key], key)

    def test_next_boundary_does_not_authorize_a3_or_holdout_access(self) -> None:
        boundary = self.config["next_boundary"]
        self.assertEqual(
            boundary["atom"],
            "T23-A3_DETERMINISTIC_R2_DIAGNOSTIC_PROJECTION_V1",
        )
        self.assertTrue(boundary["requires_separate_owner_continuation"])
        self.assertEqual(boundary["first_action"], "WRITE_IMMUTABLE_PRE_READ_RECEIPT")
        self.assertFalse(boundary["value_read_before_receipt"])
        self.assertEqual(boundary["r3_access"], "DENY")

    def test_contract_contains_required_fail_closed_markers_and_no_local_secrets(self) -> None:
        for marker in (
            "FROZEN_PRE_READ",
            "R1 values cannot be read",
            "R3 access is `DENY`",
            "`MISSING` is never `0`",
            "no IID assumption",
            "receipt must exist before any file-open operation",
            "This contract authorizes neither A3 nor any data-value read",
        ):
            self.assertIn(marker, self.contract)

        combined = self.contract + self.config_bytes.decode("utf-8")
        self.assertIsNone(re.search(r"(?i)C:\\\\Users\\\\[A-Za-z0-9._-]+", combined))
        self.assertIsNone(re.search(r"(?i)(api[_-]?key|private[_-]?key|seed phrase)\s*[:=]\s*\S+", combined))


if __name__ == "__main__":
    unittest.main()
