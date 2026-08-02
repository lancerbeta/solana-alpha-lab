from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/task24_data_redesign_or_stop_decision_v1.yaml"
DECISION_PATH = ROOT / "docs/decisions/task24_data_redesign_or_stop_decision_v1.md"
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/task24/a6_bounded_data_redesign_or_stop_decision_v1.json"
)
EXPECTED_WRITE_SET = [
    "docs/decisions/task24_data_redesign_or_stop_decision_v1.md",
    "configs/task24_data_redesign_or_stop_decision_v1.yaml",
    "tests/test_task24_data_redesign_or_stop_decision.py",
    "docs/evidence/task24/a6_bounded_data_redesign_or_stop_decision_v1.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_errors(config: dict[str, object]) -> set[str]:
    errors: set[str] = set()
    result = config["measured_result"]
    deficit = config["structural_deficit"]
    disposition = config["partial_asset_disposition"]
    authority = config["authority"]
    next_boundary = config["next_boundary"]

    if config["owner_decision"] != "STOP_NO_RELIABLE_ENTITY_SIGNAL":
        errors.add("STOP_DECISION_CHANGED")
    if result["selected_predicted_positive_capacity"] >= result[
        "false_positive_minimum_reviewed_positive"
    ]:
        errors.add("INSUFFICIENT_CAPACITY_ERASED")
    if deficit["minimum_corroborated_required"] < 4:
        errors.add("CORROBORATED_FLOOR_RELAXED")
    if deficit["population_expansion_alone_can_open_gate"]:
        errors.add("INFERRED_ONLY_FALSE_CLOSURE")
    if deficit["same_provider_pagination_is_independent_family"]:
        errors.add("PAGINATION_FALSE_INDEPENDENCE")
    if deficit["duplicate_provider_same_event_is_independent_family"]:
        errors.add("DUPLICATE_PROVIDER_FALSE_INDEPENDENCE")
    if deficit["vendor_label_can_create_corroborated"]:
        errors.add("VENDOR_PROMOTED_TO_CORROBORATED")
    if deficit["threshold_relaxation_allowed_after_value_read"]:
        errors.add("POST_VALUE_THRESHOLD_TUNING")
    for key in (
        "adjusted_concentration_change",
        "holder_exclusion_or_eligibility_change",
        "strategy_veto_or_enablement",
        "ownership_truth_claim",
    ):
        if disposition[key] != "FORBIDDEN":
            errors.add(f"DOWNSTREAM_ACTION_ENABLED:{key}")
    for key in (
        "provider_api_rpc_wss_calls",
        "credential_uses",
        "provider_credits_consumed",
        "catalog_or_registry_mutations",
        "r3_or_outcome_reads",
        "wallet_signer_transaction_actions",
        "cash_spend_usd_cents",
    ):
        if authority[key] != 0:
            errors.add(f"EXTERNAL_OR_FORBIDDEN_AUTHORITY:{key}")
    if next_boundary["authorized"]:
        errors.add("A7_AUTO_AUTHORIZED")
    return errors


class Task24DataRedesignOrStopDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.decision = DECISION_PATH.read_text(encoding="utf-8")
        cls.receipt = json.loads(RECEIPT_PATH.read_bytes())

    def test_decision_is_stop_for_v1_without_claiming_task_done(self) -> None:
        self.assertEqual(
            self.config["atom"],
            "T24-A6_BOUNDED_DATA_REDESIGN_OR_STOP_DECISION_V1",
        )
        self.assertEqual(
            self.config["owner_decision"], "STOP_NO_RELIABLE_ENTITY_SIGNAL"
        )
        self.assertEqual(self.config["state_change"]["task24"], "IN_PROGRESS")
        self.assertFalse(self.config["state_change"]["canonical_task24_done"])
        self.assertIn("CANONICAL_TASK24_DONE", self.config["non_claims"])

    def test_all_frozen_input_hashes_match(self) -> None:
        for name, binding in self.config["frozen_inputs"].items():
            with self.subTest(name=name):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_measured_capacity_and_structural_deficit_are_exact(self) -> None:
        measured = self.config["measured_result"]
        self.assertEqual(measured["provider_calls"], 21)
        self.assertEqual(measured["truncated_subjects"], 21)
        self.assertEqual(measured["corroborated_positive_claims"], 0)
        self.assertEqual(measured["inferred_or_vendor_positive_claims"], 4)
        self.assertEqual(measured["selected_predicted_positive_capacity"], 4)
        self.assertEqual(measured["false_positive_minimum_reviewed_positive"], 12)
        deficit = self.config["structural_deficit"]
        self.assertEqual(
            deficit["capacity_formula"],
            "MIN(CORROBORATED_COUNT,8)+MIN(INFERRED_OR_VENDOR_COUNT,8)",
        )
        self.assertEqual(deficit["minimum_additional_eligible_claims"], 8)
        self.assertEqual(deficit["minimum_corroborated_required"], 4)

    def test_rejected_routes_do_not_fake_independent_evidence(self) -> None:
        routes = {
            item["id"]: item for item in self.config["route_decision"]["alternatives"]
        }
        self.assertEqual(routes["SAME_PROVIDER_PAGINATION"]["disposition"], "REJECT_CURRENT_TASK")
        self.assertEqual(routes["DUPLICATE_PROVIDER_READ"]["disposition"], "REJECT")
        self.assertEqual(
            routes["VENDOR_CLUSTER_OR_BUNDLE_LABELS"]["disposition"],
            "REJECT_AS_CORROBORATION",
        )
        self.assertEqual(routes["RELAX_AUDIT_OR_CONFIDENCE_THRESHOLDS"]["disposition"], "FORBIDDEN")

    def test_partial_outputs_cannot_change_owner_actions(self) -> None:
        disposition = self.config["partial_asset_disposition"]
        self.assertEqual(disposition["inferred_candidates"], "VALIDATED_PARTIAL_REVERSIBLE")
        self.assertEqual(disposition["blinded_false_positive_audit"], "NOT_OPENED")
        self.assertEqual(disposition["downstream_decision_admissibility"], "NOT_ADMISSIBLE")
        for key in (
            "adjusted_concentration_change",
            "holder_exclusion_or_eligibility_change",
            "strategy_veto_or_enablement",
            "ownership_truth_claim",
        ):
            self.assertEqual(disposition[key], "FORBIDDEN")

    def test_reactivation_requires_new_prospective_contract(self) -> None:
        reactivation = self.config["reactivation_contract"]
        self.assertTrue(reactivation["new_versioned_objective_required"])
        self.assertFalse(reactivation["rewrite_a2_through_a6_receipts"])
        requirements = set(reactivation["requirements"])
        self.assertIn("NAMED_DOWNSTREAM_HYPOTHESIS_OR_OWNER_DECISION", requirements)
        self.assertIn("SECOND_INDEPENDENT_RAW_EVENT_FAMILY_AVAILABLE", requirements)
        self.assertIn("CREDIBLE_PATH_TO_AT_LEAST_4_CORROBORATED_POSITIVES", requirements)
        self.assertIn("SEPARATE_EXTERNAL_AUTHORITY_WHEN_APPLICABLE", requirements)

    def test_authority_write_set_and_next_boundary_are_closed(self) -> None:
        self.assertEqual(self.config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(len(set(EXPECTED_WRITE_SET)), 4)
        self.assertEqual(policy_errors(self.config), set())
        self.assertEqual(
            self.config["next_boundary"]["atom"],
            "T24-A7_REGISTER_PARTIAL_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1",
        )
        self.assertFalse(self.config["next_boundary"]["authorized"])

    def test_receipt_binds_decision_config_and_zero_external_actions(self) -> None:
        self.assertEqual(self.receipt["status"], "PASS_VALIDATED_STOP_DECISION_ONLY")
        self.assertEqual(
            self.receipt["artifact_bindings"]["decision"]["sha256"],
            sha256(DECISION_PATH),
        )
        self.assertEqual(
            self.receipt["artifact_bindings"]["config"]["sha256"],
            sha256(CONFIG_PATH),
        )
        self.assertEqual(self.receipt["authority"]["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(self.receipt["authority"]["catalog_or_registry_mutations"], 0)
        self.assertEqual(self.receipt["authority"]["r3_or_outcome_reads"], 0)

    def test_decision_text_preserves_stop_and_reactivation_boundaries(self) -> None:
        for marker in (
            "`STOP_NO_RELIABLE_ENTITY_SIGNAL`",
            "`C=0, I=4`",
            "Adding inferred claims alone",
            "target-driven rule tuning after value read",
            "not admissible",
            "new versioned task or contract",
            "canonical TASK-24 `DONE`",
        ):
            self.assertIn(marker, self.decision)

    def test_adversarial_policy_mutations_are_rejected(self) -> None:
        mutations = [
            (("structural_deficit", "same_provider_pagination_is_independent_family"), True, "PAGINATION_FALSE_INDEPENDENCE"),
            (("structural_deficit", "duplicate_provider_same_event_is_independent_family"), True, "DUPLICATE_PROVIDER_FALSE_INDEPENDENCE"),
            (("structural_deficit", "vendor_label_can_create_corroborated"), True, "VENDOR_PROMOTED_TO_CORROBORATED"),
            (("structural_deficit", "threshold_relaxation_allowed_after_value_read"), True, "POST_VALUE_THRESHOLD_TUNING"),
            (("next_boundary", "authorized"), True, "A7_AUTO_AUTHORIZED"),
            (("authority", "provider_api_rpc_wss_calls"), 1, "EXTERNAL_OR_FORBIDDEN_AUTHORITY:provider_api_rpc_wss_calls"),
        ]
        for path, value, expected in mutations:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.config)
                changed[path[0]][path[1]] = value
                self.assertIn(expected, policy_errors(changed))


if __name__ == "__main__":
    unittest.main()
