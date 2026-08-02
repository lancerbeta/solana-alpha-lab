from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task24_entity_graph_and_false_positive_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task24_entity_graph_v1.yaml"
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/task24/a2_frozen_entity_graph_contract_acceptance_v1.json"
)

EXPECTED_CONTRACT_SHA256 = (
    "14614796dfc17aeef907e6b1d863814cbfb52e8f188704b70f17d99a78b862a8"
)
EXPECTED_CONFIG_SHA256 = (
    "a294d9c8507777581bec8217f4127e16a76788b243250a1eb57e6bff9b69ed25"
)

EXPECTED_INPUTS = {
    "docs/contracts/entity_input_observation_contract_v1.md": (
        "5d92f8dae8860043dae3115fb5a7cb4deb50de48c8efb2a6bca46fc47987d8e4",
        7635,
    ),
    "docs/evidence/task11/entity_input_pilot_execution_receipt_v1.json": (
        "324c9ace8c49668864c274de19c09d42a7e794169f9a5ad619df8b47f3209ff4",
        5950,
    ),
    "tests/fixtures/task11/entity_input_live_evidence_v1.json": (
        "2c0e00c1aacb32a75cbe5807517e5e514751cec0271a540594147390e8fbf7b2",
        6805,
    ),
    "schemas/schema_v1.sql": (
        "eae9d1544b11cffc03afba1e263153168a11dc6f648df9117a55a4cae5d23f09",
        28962,
    ),
    "src/solana_alpha_lab/contracts/schema_v1.py": (
        "ef9435fc0aa6df1d880714e97d3312e068dc82806a8c6ba1ed2d74c9929684ad",
        32794,
    ),
    "docs/reports/task23_cohort_diagnostics_v1.md": (
        "2964fc1c6051772b1d9fef2d973df49d1155e89efb30207263f91297630b898f",
        3337,
    ),
    "docs/evidence/task23/a5_catalog_repository_factory_fit_v1.json": (
        "7f840ac5fbdc6481dec592e529588b99d53a65e314587adeee98605dc94bab14",
        13979,
    ),
}

EXPECTED_NODE_TYPES = [
    "TOKEN_MINT",
    "TOKEN_ACCOUNT",
    "WALLET",
    "PROGRAM_OR_POOL",
    "TRANSACTION",
    "ENTITY_CANDIDATE",
]

EXPECTED_EDGE_TYPES = {
    "RAW_TOKEN_ACCOUNT_FOR_MINT": ("RAW_ONCHAIN", ["DIRECT"]),
    "RAW_TOKEN_ACCOUNT_OWNER": ("RAW_ONCHAIN", ["DIRECT"]),
    "RAW_MINT_CREATED_BY_WALLET": ("RAW_ONCHAIN", ["DIRECT"]),
    "RAW_IMMEDIATE_FUNDER": ("RAW_ONCHAIN", ["DIRECT"]),
    "RAW_COMMON_TRANSACTION_SIGNER": ("RAW_ONCHAIN", ["DIRECT"]),
    "RAW_SAME_BUNDLE_MEMBERSHIP": ("RAW_ONCHAIN", ["DIRECT"]),
    "DERIVED_SHARED_IMMEDIATE_FUNDER": (
        "DERIVED_ADJUSTED",
        ["CORROBORATED", "INFERRED"],
    ),
    "VENDOR_BUNDLE_LABEL": ("VENDOR_LABEL", ["VENDOR_ONLY"]),
    "PROJECT_ENTITY_MEMBERSHIP_CANDIDATE": (
        "PROJECT_INFERENCE",
        ["CORROBORATED", "INFERRED", "UNKNOWN"],
    ),
}

EXPECTED_WRITE_SET = [
    "docs/contracts/task24_entity_graph_and_false_positive_contract_v1.md",
    "configs/task24_entity_graph_v1.yaml",
    "tests/test_task24_entity_graph_contract.py",
    "docs/evidence/task24/a2_frozen_entity_graph_contract_acceptance_v1.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_errors(document: dict) -> set[str]:
    errors: set[str] = set()
    if document["promotion_rules"]["vendor_to_raw"]:
        errors.add("VENDOR_PROMOTED_TO_RAW")
    if document["graph_contract"]["destructive_node_merge"]:
        errors.add("DESTRUCTIVE_NODE_MERGE")
    if document["exclusion_contract"]["vendor_only_can_exclude"]:
        errors.add("VENDOR_ONLY_EXCLUSION")
    if document["point_in_time_contract"]["r3_allowed"]:
        errors.add("R3_ACCESS")
    if document["false_positive_audit"]["tune_on_validation_sample"]:
        errors.add("VALIDATION_SAMPLE_TUNING")
    if document["authority"]["provider_api_rpc_wss_calls"]:
        errors.add("EXTERNAL_PROVIDER_AUTHORITY")
    if document["next_boundary"]["authorized_by_a2"]:
        errors.add("A3_AUTO_AUTHORIZED")
    return errors


class Task24EntityGraphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.contract = cls.contract_bytes.decode("utf-8")
        cls.config_bytes = CONFIG_PATH.read_bytes()
        cls.config = yaml.safe_load(cls.config_bytes)
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    def test_contract_and_config_are_exactly_content_bound(self) -> None:
        self.assertEqual(sha256(CONTRACT_PATH), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(sha256(CONFIG_PATH), EXPECTED_CONFIG_SHA256)
        for payload in (self.contract_bytes, self.config_bytes):
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r\n", payload)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_acceptance_receipt_binds_contract_config_and_measured_zeroes(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS_VALIDATED_CONTRACT_ONLY")
        bindings = self.receipt["artifact_bindings"]
        self.assertEqual(bindings["contract"]["sha256"], EXPECTED_CONTRACT_SHA256)
        self.assertEqual(bindings["config"]["sha256"], EXPECTED_CONFIG_SHA256)
        measured = self.receipt["measured_boundary"]
        for key in (
            "new_entity_values_read",
            "owner_addresses_in_tracked_task11_fixture",
            "tracked_provider_bodies_read",
            "graph_nodes_materialized",
            "graph_edges_materialized",
            "entity_candidates_materialized",
            "holder_exclusions_changed",
            "r3_or_outcome_reads",
        ):
            self.assertEqual(measured[key], 0, key)

    def test_entry_gate_is_bound_to_accepted_main_and_deps(self) -> None:
        entry = self.config["entry_gate"]
        self.assertEqual(entry["verdict"], "START_WITH_PATCH")
        self.assertEqual(entry["route_owner"], "LOCAL_WORK_PRIMARY")
        self.assertEqual(entry["execution_route"], "LOCAL_WORK_CODEX")
        self.assertEqual(
            entry["accepted_main_commit"],
            "31c01640499be6b7e86a2fe638d9217c202861cc",
        )
        self.assertEqual(
            entry["accepted_main_tree"],
            "6677878eb2b8195018ab217c6a9a429de5726563",
        )
        self.assertEqual(entry["dependencies"]["TASK-21"], "DONE")
        self.assertEqual(
            entry["dependencies"]["TASK-23"],
            "DONE_DIAGNOSTICS_READY_WITH_LIMITATIONS",
        )
        self.assertEqual(entry["canonical_task_source_activation"], "NOT_CLAIMED")

    def test_managed_write_set_is_exact_and_a2_only(self) -> None:
        self.assertEqual(self.config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(len(set(self.config["managed_write_set"])), 4)
        self.assertFalse(
            any(path.startswith("catalog/") for path in self.config["managed_write_set"])
        )
        self.assertFalse(
            any(path.startswith("registries/") for path in self.config["managed_write_set"])
        )

    def test_all_frozen_inputs_exist_with_exact_hashes_and_sizes(self) -> None:
        frozen = {
            item["path"]: (item["sha256"], item["bytes"])
            for item in self.config["frozen_inputs"]
        }
        self.assertEqual(frozen, EXPECTED_INPUTS)
        for relative_path, (expected_hash, expected_size) in EXPECTED_INPUTS.items():
            path = ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertEqual(path.stat().st_size, expected_size, relative_path)
            self.assertEqual(sha256(path), expected_hash, relative_path)

    def test_data_feasibility_fails_closed_without_addresses_or_raw_runtime(self) -> None:
        feasibility = self.config["data_feasibility"]
        self.assertFalse(feasibility["value_read_in_a2"])
        self.assertEqual(feasibility["new_entity_values_read_in_a2"], 0)
        fixture = feasibility["tracked_task11_fixture"]
        self.assertEqual(fixture["owner_addresses"], 0)
        self.assertIn("GRAPH_CONSTRUCTION", fixture["forbidden_use"])
        self.assertIn("ADDRESS_RECONSTRUCTION_FROM_HASHES", fixture["forbidden_use"])
        raw = feasibility["task11_logical_raw_runtime"]
        self.assertEqual(raw["status"], "NOT_AVAILABLE_CURRENT_WORKSPACE_AT_ENTRY_GATE")
        self.assertFalse(raw["fabricate_or_infer_from_hashes"])
        self.assertTrue(feasibility["pre_read_manifest_required_for_a3"])

    def test_evidence_classes_and_promotion_rules_match_task11(self) -> None:
        self.assertEqual(
            self.config["evidence_classes"],
            ["RAW_ONCHAIN", "DERIVED_ADJUSTED", "VENDOR_LABEL", "PROJECT_INFERENCE"],
        )
        promotion = self.config["promotion_rules"]
        self.assertFalse(promotion["vendor_to_raw"])
        self.assertFalse(promotion["inference_to_raw"])
        self.assertFalse(promotion["confidence_repairs_missing_provenance"])
        self.assertTrue(promotion["preserve_raw_after_derivation"])
        self.assertTrue(promotion["preserve_conflicts"])

    def test_node_vocabulary_and_required_provenance_are_closed(self) -> None:
        graph = self.config["graph_contract"]
        self.assertEqual(graph["node_types"], EXPECTED_NODE_TYPES)
        self.assertEqual(len(set(graph["node_types"])), 6)
        required = set(graph["node_required_fields"])
        self.assertTrue(
            {
                "node_id",
                "node_type",
                "business_key",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "evidence_class",
                "revision_number",
                "content_sha256",
            }.issubset(required)
        )
        self.assertFalse(graph["destructive_node_merge"])

    def test_edge_taxonomy_has_exact_types_evidence_and_confidence(self) -> None:
        edges = self.config["graph_contract"]["edge_types"]
        actual = {
            edge["id"]: (edge["evidence_class"], edge["allowed_confidence"])
            for edge in edges
        }
        self.assertEqual(actual, EXPECTED_EDGE_TYPES)
        self.assertEqual(len(edges), len({edge["id"] for edge in edges}))
        required = set(self.config["graph_contract"]["edge_required_fields"])
        self.assertTrue(
            {
                "supporting_raw_event_ids",
                "supporting_edge_ids",
                "rule_version",
                "conflict_set_id",
                "content_sha256",
            }.issubset(required)
        )

    def test_semantic_guards_and_confidence_do_not_claim_ownership(self) -> None:
        guards = self.config["graph_contract"]["semantic_guards"]
        self.assertFalse(guards["immediate_funder_is_ultimate_funder"])
        self.assertFalse(guards["mint_creator_is_beneficial_owner"])
        self.assertFalse(guards["common_signer_is_common_owner"])
        self.assertFalse(guards["bundle_label_is_common_owner"])
        self.assertEqual(guards["missing_evidence_representation"], "NOT_TESTABLE")
        confidence = self.config["confidence_contract"]
        self.assertEqual(confidence["corroborated_minimum_independent_raw_edge_families"], 2)
        self.assertFalse(confidence["duplicate_providers_same_event_are_independent"])
        self.assertFalse(confidence["vendor_only_can_merge_exclude_veto_or_trade"])
        self.assertFalse(confidence["unknown_can_merge_exclude_veto_or_trade"])

    def test_point_in_time_and_revision_contract_blocks_hindsight(self) -> None:
        pit = self.config["point_in_time_contract"]
        self.assertEqual(
            pit["derived_availability_rule"],
            "MAX_OF_ALL_REQUIRED_INPUT_AVAILABILITY",
        )
        self.assertEqual(len(pit["required_timestamps"]), 5)
        self.assertFalse(pit["future_labels_allowed"])
        self.assertFalse(pit["strategy_outcomes_allowed"])
        self.assertFalse(pit["pnl_or_netreturn_allowed"])
        self.assertFalse(pit["r3_allowed"])
        self.assertTrue(pit["revisions_append_only"])
        self.assertFalse(pit["overwrite_raw_observations"])
        self.assertTrue(pit["conflict_set_required_on_disagreement"])

    def test_exclusions_require_complete_inventory_and_strong_evidence(self) -> None:
        exclusion = self.config["exclusion_contract"]
        self.assertTrue(exclusion["raw_and_adjusted_are_separate_durable_fields"])
        self.assertTrue(exclusion["adjusted_requires_complete_inventory"])
        self.assertTrue(exclusion["adjusted_requires_direct_or_corroborated_evidence"])
        self.assertFalse(exclusion["unresolved_is_excluded"])
        for key in (
            "vendor_only_can_exclude",
            "common_funder_alone_can_exclude",
            "common_signer_alone_can_exclude",
            "bundle_label_alone_can_exclude",
            "entity_candidate_alone_can_exclude",
        ):
            self.assertFalse(exclusion[key], key)
        self.assertIn("raw_metric", exclusion["retained_fields"])
        self.assertIn("adjusted_metric", exclusion["retained_fields"])

    def test_false_positive_sample_is_frozen_deterministic_and_blinded(self) -> None:
        audit = self.config["false_positive_audit"]
        self.assertTrue(audit["frozen_before_graph_value_read"])
        self.assertEqual(audit["seed"], "TASK24_FALSE_POSITIVE_AUDIT_V1")
        self.assertEqual(audit["within_stratum_selection"], "LOWEST_HASHES")
        self.assertEqual(audit["target_sample_size"], 24)
        self.assertEqual([item["target"] for item in audit["strata"]], [8, 8, 8])
        self.assertEqual(
            audit["undersized_stratum_rule"],
            "USE_ALL_WITHOUT_CROSS_STRATUM_SUBSTITUTION",
        )
        self.assertEqual(
            set(audit["reviewer_blinding"]),
            {
                "STRATEGY_IDENTITY",
                "ENTRY_EXIT_DECISIONS",
                "OUTCOME",
                "PNL",
                "NETRETURN",
                "R3_MEMBERSHIP",
                "FUTURE_VENDOR_LABELS",
            },
        )

    def test_false_positive_gate_is_explicit_and_cannot_tune_on_sample(self) -> None:
        audit = self.config["false_positive_audit"]
        acceptance = audit["acceptance"]
        self.assertEqual(audit["minimum_reviewed_predicted_positive"], 12)
        self.assertEqual(acceptance["max_critical_violations"], 0)
        self.assertEqual(acceptance["max_false_positive_count"], 1)
        self.assertEqual(acceptance["max_ambiguous_share"], 0.25)
        self.assertTrue(acceptance["report_wilson_95_interval"])
        self.assertFalse(audit["tune_on_validation_sample"])
        self.assertTrue(audit["changed_rule_requires_new_version_and_sample_epoch"])
        self.assertEqual(len(audit["critical_violations"]), 4)

    def test_owner_decision_authority_nonclaims_and_next_boundary_are_closed(self) -> None:
        decision = self.config["owner_decision"]
        self.assertEqual(len(decision["allowed_terminal_decisions"]), 4)
        self.assertIn("CANONICAL_TASK24_DONE", decision["forbidden_claims"])
        self.assertIn("R3_OR_OUTCOME_ACCESS", decision["forbidden_claims"])
        authority = self.config["authority"]
        self.assertTrue(authority["local_declared_write_set"])
        self.assertTrue(authority["offline_validation"])
        for key in (
            "provider_api_rpc_wss_calls",
            "credential_use",
            "dependency_changes",
            "catalog_or_registry_mutation",
            "r3_or_outcome_access",
            "wallet_signer_transaction_actions",
            "deploy_or_release",
            "commit",
            "push",
            "pull_request",
            "merge",
        ):
            self.assertFalse(authority[key], key)
        next_boundary = self.config["next_boundary"]
        self.assertFalse(next_boundary["authorized_by_a2"])
        self.assertIn("EXACT_PRE_READ_MANIFEST_PASS", next_boundary["preconditions"])
        for marker in (
            "evidence read model, not an ownership truth store",
            "is destructively merged, and raw evidence remains queryable",
            "fabricated or reconstructed\nfrom hashes",
            "canonical TASK-24 `DONE`",
        ):
            self.assertIn(marker, self.contract)

    def test_adversarial_forbidden_mutations_are_rejected(self) -> None:
        self.assertEqual(policy_errors(self.config), set())
        mutations = [
            ("promotion_rules", "vendor_to_raw", "VENDOR_PROMOTED_TO_RAW"),
            ("graph_contract", "destructive_node_merge", "DESTRUCTIVE_NODE_MERGE"),
            ("exclusion_contract", "vendor_only_can_exclude", "VENDOR_ONLY_EXCLUSION"),
            ("point_in_time_contract", "r3_allowed", "R3_ACCESS"),
            (
                "false_positive_audit",
                "tune_on_validation_sample",
                "VALIDATION_SAMPLE_TUNING",
            ),
            ("authority", "provider_api_rpc_wss_calls", "EXTERNAL_PROVIDER_AUTHORITY"),
            ("next_boundary", "authorized_by_a2", "A3_AUTO_AUTHORIZED"),
        ]
        for section, key, expected_error in mutations:
            with self.subTest(section=section, key=key):
                changed = copy.deepcopy(self.config)
                changed[section][key] = True
                self.assertIn(expected_error, policy_errors(changed))


if __name__ == "__main__":
    unittest.main()
