from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = (
    ROOT / "docs/decisions/task24_entity_linkage_evidence_extension_decision_v1.md"
)
CONFIG_PATH = ROOT / "configs/task24_entity_linkage_evidence_extension_v1.yaml"
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/task24/a4_bounded_entity_linkage_evidence_extension_decision_v1.json"
)

EXPECTED_DECISION_SHA256 = (
    "a13523b86272c39976ab6a11a0332180cced51fde54c185a381e0034ec416fda"
)
EXPECTED_CONFIG_SHA256 = (
    "2db333e179ecc54cced41128b5a8c97825fc970d46af66be8660db9ee963791b"
)
EXPECTED_WRITE_SET = [
    "docs/decisions/task24_entity_linkage_evidence_extension_decision_v1.md",
    "configs/task24_entity_linkage_evidence_extension_v1.yaml",
    "tests/test_task24_entity_linkage_evidence_extension_decision.py",
    "docs/evidence/task24/a4_bounded_entity_linkage_evidence_extension_decision_v1.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_errors(document: dict) -> set[str]:
    errors: set[str] = set()
    probe = document["probe_contract"]
    rules = document["evidence_family_rules"]
    route = {
        item["id"]: item for item in document["route_evaluation"]["candidates"]
    }
    if document["authority"]["provider_api_rpc_wss_calls"]:
        errors.add("EXTERNAL_CALL_AUTO_AUTHORIZED")
    if document["next_boundary"]["authorized"]:
        errors.add("A5_AUTO_AUTHORIZED")
    if probe["population"]["expansion_allowed"]:
        errors.add("POPULATION_AUTO_EXPANSION")
    if probe["request_parameters"]["pagination"]:
        errors.add("PAGINATION_INSIDE_PROBE")
    if probe["caps"]["cash_spend_usd_cents"] != 0:
        errors.add("CASH_SPEND")
    if rules["duplicate_provider_same_transaction_independent"]:
        errors.add("DUPLICATE_PROVIDER_FALSE_INDEPENDENCE")
    if rules["multiple_fields_same_transaction_independent"]:
        errors.add("SAME_EVENT_FALSE_INDEPENDENCE")
    if route["VENDOR_CLUSTER_LABEL"]["can_create_corroborated"]:
        errors.add("VENDOR_PROMOTED_TO_CORROBORATED")
    return errors


class Task24EntityLinkageEvidenceExtensionDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision_bytes = DECISION_PATH.read_bytes()
        cls.decision = cls.decision_bytes.decode("utf-8")
        cls.config_bytes = CONFIG_PATH.read_bytes()
        cls.config = yaml.safe_load(cls.config_bytes)
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    def test_decision_and_config_are_exactly_content_bound(self) -> None:
        self.assertEqual(sha256(DECISION_PATH), EXPECTED_DECISION_SHA256)
        self.assertEqual(sha256(CONFIG_PATH), EXPECTED_CONFIG_SHA256)
        for payload in (self.decision_bytes, self.config_bytes):
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r\n", payload)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))

    def test_entry_gate_and_a3_gap_are_exact(self) -> None:
        entry = self.config["entry_gate"]
        self.assertEqual(entry["verdict"], "START_AS_WRITTEN")
        self.assertEqual(entry["reasoning"], "VERY_HIGH_SUFFICIENT")
        self.assertEqual(entry["active_time_gates"], 0)
        self.assertEqual(
            entry["accepted_main_commit"],
            "31c01640499be6b7e86a2fe638d9217c202861cc",
        )
        self.assertEqual(
            entry["accepted_main_tree"],
            "6677878eb2b8195018ab217c6a9a429de5726563",
        )
        gap = self.config["measured_gap"]
        self.assertEqual(gap["population_wallets"], 20)
        self.assertEqual(gap["entity_candidates"], 0)
        self.assertEqual(gap["selected_predicted_positive_capacity"], 0)
        self.assertEqual(gap["false_positive_minimum_reviewed_positive"], 12)

    def test_frozen_inputs_still_exist_with_exact_hashes(self) -> None:
        for item in self.config["frozen_inputs"].values():
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256(path), item["sha256"], item["path"])

    def test_audit_capacity_proves_funder_only_is_insufficient(self) -> None:
        capacity = self.config["audit_capacity"]
        self.assertEqual(
            capacity["formula"],
            "MIN(CORROBORATED_COUNT,8)+MIN(INFERRED_OR_VENDOR_COUNT,8)",
        )
        self.assertEqual(capacity["minimum_to_open_gate"], 12)
        self.assertEqual(capacity["inferred_only_maximum_selected_positive"], 8)
        self.assertEqual(
            capacity["minimum_corroborated_when_other_positive_stratum_full"], 4
        )
        self.assertFalse(capacity["undersized_stratum_substitution_allowed"])
        self.assertFalse(capacity["vendor_labels_can_repair_corroborated_shortage"])

    def test_official_sources_are_public_read_only_and_currently_attributed(self) -> None:
        sources = self.config["official_sources"]
        self.assertEqual(sources["as_of"], "2026-08-02")
        self.assertTrue(sources["public_docs_only"])
        self.assertEqual(sources["credentialed_calls"], 0)
        by_id = {item["id"]: item for item in sources["sources"]}
        self.assertEqual(
            set(by_id),
            {
                "SOLANA_GET_SIGNATURES_FOR_ADDRESS",
                "SOLANA_GET_TRANSACTION",
                "HELIUS_GET_TRANSACTIONS_FOR_ADDRESS",
                "HELIUS_ENHANCED_TRANSACTIONS_OVERVIEW",
                "JITO_BUNDLE_API",
            },
        )
        self.assertIn(
            "DEPRECATED_FOR_NEW_INTEGRATIONS",
            by_id["HELIUS_ENHANCED_TRANSACTIONS_OVERVIEW"]["facts"],
        )
        self.assertIn(
            "STATUS_QUERY_REQUIRES_KNOWN_BUNDLE_ID",
            by_id["JITO_BUNDLE_API"]["facts"],
        )

    def test_route_adopts_raw_history_transport_not_provider_ownership_labels(self) -> None:
        evaluation = self.config["route_evaluation"]
        self.assertEqual(evaluation["selected"], "BOUNDED_RAW_HISTORY_FEASIBILITY_PROBE")
        routes = {item["id"]: item for item in evaluation["candidates"]}
        helius = routes["HELIUS_GET_TRANSACTIONS_FOR_ADDRESS"]
        self.assertTrue(helius["primary"])
        self.assertEqual(
            helius["adopt_wrap"],
            "ADOPT_TRANSPORT_WRAP_DETERMINISTIC_PROJECT_PARSER",
        )
        self.assertFalse(helius["provider_labels_as_raw"])
        self.assertEqual(routes["HELIUS_ENHANCED_TRANSACTIONS_V1"]["role"], "REJECTED")
        self.assertFalse(routes["VENDOR_CLUSTER_LABEL"]["can_create_corroborated"])

    def test_probe_population_request_and_cost_caps_are_closed(self) -> None:
        probe = self.config["probe_contract"]
        self.assertFalse(probe["authorized_by_a4"])
        self.assertEqual(probe["population"]["token_mints"], 1)
        self.assertEqual(probe["population"]["wallets"], 20)
        self.assertFalse(probe["population"]["expansion_allowed"])
        params = probe["request_parameters"]
        self.assertEqual(params["sortOrder"], "asc")
        self.assertEqual(params["limit"], 100)
        self.assertFalse(params["pagination"])
        caps = probe["caps"]
        self.assertEqual(caps["provider_api_rpc_calls"], 21)
        self.assertEqual(caps["returned_transactions"], 2100)
        self.assertEqual(caps["provider_credits"], 210)
        self.assertEqual(caps["retries"], 0)
        self.assertEqual(caps["cash_spend_usd_cents"], 0)

    def test_raw_retention_and_secret_boundary_fail_closed(self) -> None:
        retention = self.config["probe_contract"]["retention"]
        self.assertTrue(retention["exact_raw_response_bytes"])
        self.assertTrue(retention["sha256_and_bytes"])
        self.assertTrue(retention["pit_timestamps"])
        self.assertTrue(retention["truncation_null_and_error_flags"])
        self.assertFalse(retention["secrets_or_key_in_url"])
        self.assertFalse(retention["durable_raw_public_addresses"])
        self.assertTrue(
            self.config["next_boundary"]["no_secret_in_chat_repo_logs_or_retained_urls"]
        )

    def test_evidence_families_require_distinct_raw_events(self) -> None:
        rules = self.config["evidence_family_rules"]
        self.assertEqual(rules["independence_unit"], "DISTINCT_RAW_EVENT_FAMILY")
        self.assertFalse(rules["duplicate_provider_same_transaction_independent"])
        self.assertFalse(rules["multiple_fields_same_transaction_independent"])
        self.assertFalse(
            rules["common_signer"]["same_event_as_funder_counts_as_independent"]
        )
        self.assertFalse(rules["authoritative_bundle"]["available_initial_probe"])
        self.assertFalse(
            rules["authoritative_bundle"]["vendor_label_substitution_allowed"]
        )
        confidence = rules["candidate_confidence"]
        self.assertEqual(confidence["shared_immediate_funder_alone"], "INFERRED")
        self.assertEqual(confidence["corroborated_minimum_independent_raw_families"], 2)
        self.assertTrue(confidence["corroborated_requires_disjoint_raw_events"])

    def test_post_probe_decision_blocks_tuning_and_silent_expansion(self) -> None:
        decision = self.config["post_probe_decision"]
        self.assertEqual(
            decision["if_capacity_below_12"],
            "NO_AUTOMATIC_EXPANSION_OR_TUNING",
        )
        self.assertEqual(
            decision["valid_history_but_insufficient_structure"], "REDESIGN_DATA"
        )
        self.assertEqual(
            decision["incomplete_contradictory_or_unreliable_history"],
            "STOP_NO_RELIABLE_ENTITY_SIGNAL",
        )
        self.assertEqual(
            decision["wider_population_pagination_provider_or_credit_cap"],
            "NEW_USER_APPROVED_BOUNDARY",
        )

    def test_authority_write_set_nonclaims_and_next_gate_are_closed(self) -> None:
        self.assertEqual(self.config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(len(set(self.config["managed_write_set"])), 4)
        authority = self.config["authority"]
        self.assertTrue(authority["public_official_docs_read"])
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
        self.assertEqual(authority["provider_credits"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertIn("CANONICAL_TASK24_DONE", self.config["non_claims"])
        self.assertFalse(self.config["next_boundary"]["authorized"])

    def test_receipt_binds_decision_config_and_zero_external_side_effects(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS_VALIDATED_DECISION_ONLY")
        bindings = self.receipt["artifact_bindings"]
        self.assertEqual(bindings["decision"]["sha256"], EXPECTED_DECISION_SHA256)
        self.assertEqual(bindings["config"]["sha256"], EXPECTED_CONFIG_SHA256)
        authority = self.receipt["authority"]
        for key in (
            "provider_api_rpc_wss_calls",
            "credential_uses",
            "provider_credits_consumed",
            "catalog_or_registry_mutations",
            "r3_or_outcome_reads",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(authority[key], 0, key)

    def test_decision_text_preserves_critical_nonclaims_and_stop(self) -> None:
        for marker in (
            "`min(C, 8) + min(I, 8)`",
            "one event family for this purpose",
            "provider descriptions or labels are not raw ownership evidence",
            "The 21-call envelope is a cap, not authority",
            "do not add labels, tune rules, paginate, expand the population",
            "canonical TASK-24 `DONE`",
        ):
            self.assertIn(marker, self.decision)

    def test_adversarial_policy_mutations_are_rejected(self) -> None:
        self.assertEqual(policy_errors(self.config), set())
        mutations = [
            ("authority", "provider_api_rpc_wss_calls", True, "EXTERNAL_CALL_AUTO_AUTHORIZED"),
            ("next_boundary", "authorized", True, "A5_AUTO_AUTHORIZED"),
        ]
        for section, key, value, expected in mutations:
            with self.subTest(section=section, key=key):
                changed = copy.deepcopy(self.config)
                changed[section][key] = value
                self.assertIn(expected, policy_errors(changed))

        nested_mutations = [
            (
                ("probe_contract", "population", "expansion_allowed"),
                True,
                "POPULATION_AUTO_EXPANSION",
            ),
            (
                ("probe_contract", "request_parameters", "pagination"),
                True,
                "PAGINATION_INSIDE_PROBE",
            ),
            (
                ("probe_contract", "caps", "cash_spend_usd_cents"),
                1,
                "CASH_SPEND",
            ),
            (
                ("evidence_family_rules", "duplicate_provider_same_transaction_independent"),
                True,
                "DUPLICATE_PROVIDER_FALSE_INDEPENDENCE",
            ),
            (
                ("evidence_family_rules", "multiple_fields_same_transaction_independent"),
                True,
                "SAME_EVENT_FALSE_INDEPENDENCE",
            ),
        ]
        for path, value, expected in nested_mutations:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.config)
                cursor = changed
                for key in path[:-1]:
                    cursor = cursor[key]
                cursor[path[-1]] = value
                self.assertIn(expected, policy_errors(changed))

        changed = copy.deepcopy(self.config)
        routes = {
            item["id"]: item for item in changed["route_evaluation"]["candidates"]
        }
        routes["VENDOR_CLUSTER_LABEL"]["can_create_corroborated"] = True
        self.assertIn("VENDOR_PROMOTED_TO_CORROBORATED", policy_errors(changed))


if __name__ == "__main__":
    unittest.main()
