from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_information_sufficiency import (
    Task21InformationSufficiencyError,
    evaluate_information_sufficiency_rebase,
)


PLAN_PATH = ROOT / "configs" / "task21_information_sufficiency_rebase_v1.yaml"
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task21_information_sufficiency_rebase_contract_v1.md"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "information_sufficiency_rebase_acceptance_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21InformationSufficiencyRebaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))

    def test_protected_inputs_match_exact_bytes(self) -> None:
        for item in self.plan["protected_inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(_sha256(path), item["sha256"], item["path"])

    def test_exact_current_complete_member_count_excludes_h24(self) -> None:
        result = evaluate_information_sufficiency_rebase(self.plan)
        self.assertEqual(result["current_complete_base_members"], 0)
        self.assertEqual(self.plan["current_evidence"]["base_panels_exact"], 6)
        self.assertEqual(self.plan["current_evidence"]["supplemental_panels_exact"], 1)
        self.assertFalse(
            self.plan["current_evidence"][
                "supplemental_panels_count_toward_complete_member"
            ]
        )

    def test_budget_arithmetic_preserves_outer_caps(self) -> None:
        result = evaluate_information_sufficiency_rebase(self.plan)
        self.assertEqual(result["new_member_cap"], 5)
        self.assertEqual(result["new_base_panels_max"], 15)
        self.assertEqual(result["new_source_requests_max"], 4)
        self.assertEqual(result["new_quote_requests_max"], 120)
        self.assertEqual(result["projected_external_requests_max"], 184)
        self.assertEqual(result["external_request_headroom"], 8)
        self.assertEqual(result["response_bytes_remaining"], 25_079_733)
        self.assertEqual(result["stored_bytes_remaining"], 125_464_222)
        self.assertEqual(result["dataset_bytes_remaining"], 268_070_558)

    def test_calendar_wait_is_removed_not_shortened(self) -> None:
        result = evaluate_information_sufficiency_rebase(self.plan)
        sufficiency = self.plan["information_sufficiency"]
        self.assertFalse(result["calendar_wait_required"])
        self.assertIsNone(sufficiency["minimum_calendar_days"])
        self.assertIsNone(sufficiency["minimum_calendar_weeks"])
        self.assertFalse(self.plan["stop_rules"]["calendar_elapsed_alone_is_evidence"])

    def test_success_is_narrow_conditional_and_task22_stays_closed(self) -> None:
        result = evaluate_information_sufficiency_rebase(self.plan)
        self.assertEqual(result["verdict"], "BOUNDED_EVENT_TRIGGERED_EXTENSION_JUSTIFIED")
        self.assertFalse(result["dataset_ready"])
        self.assertFalse(result["task22_eligible"])
        self.assertEqual(
            self.plan["information_sufficiency"]["success_disposition"],
            "DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS",
        )
        self.assertFalse(
            self.plan["information_sufficiency"]["market_wide_prevalence_claim_allowed"]
        )
        self.assertFalse(self.plan["information_sufficiency"]["cross_regime_claim_allowed"])

    def test_adversarial_counting_h24_as_base_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["current_evidence"]["supplemental_panels_count_toward_complete_member"] = True
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "supplemental_sufficiency_inflation",
        ):
            evaluate_information_sufficiency_rebase(changed)

    def test_adversarial_calendar_week_gate_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["information_sufficiency"]["minimum_calendar_weeks"] = 3
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "calendar_week_gate_reintroduced",
        ):
            evaluate_information_sufficiency_rebase(changed)

    def test_adversarial_candidate_or_request_inflation_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["final_extension"]["batches"][1]["member_cap"] = 3
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "batch_member_cap_drift",
        ):
            evaluate_information_sufficiency_rebase(changed)

        changed = copy.deepcopy(self.plan)
        changed["budget"]["proposed_final_extension_max"]["quote_requests"] = 128
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "projected_quote_requests_drift",
        ):
            evaluate_information_sufficiency_rebase(changed)

    def test_adversarial_hypothesis_or_outcome_change_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["protected_history"]["primary_estimand_changed"] = True
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "primary_estimand_changed",
        ):
            evaluate_information_sufficiency_rebase(changed)

        changed = copy.deepcopy(self.plan)
        changed["protected_history"]["sealed_outcomes_read"] = True
        with self.assertRaisesRegex(
            Task21InformationSufficiencyError,
            "outcome_unsealed",
        ):
            evaluate_information_sufficiency_rebase(changed)

    def test_adversarial_authority_leak_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["authority"]["provider_api_rpc_wss_calls"] = 1
        with self.assertRaisesRegex(Task21InformationSufficiencyError, "authority_leak"):
            evaluate_information_sufficiency_rebase(changed)

        changed = copy.deepcopy(self.plan)
        changed["next_boundary"]["task22_authorized"] = True
        with self.assertRaisesRegex(Task21InformationSufficiencyError, "task22_authority_leak"):
            evaluate_information_sufficiency_rebase(changed)

    def test_contract_contains_decision_changing_rules(self) -> None:
        text = " ".join(CONTRACT_PATH.read_text(encoding="utf-8").split())
        for required in (
            "zero complete base members",
            "Calendar duration is not information",
            "two content-distinct nomination batches",
            "1,801 seconds",
            "184 / 192",
            "DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS",
            "There is no automatic extension",
            "zero provider/API/RPC/WSS or Drive calls",
        ):
            self.assertIn(required, text)

    def test_acceptance_receipt_binds_candidate_and_zero_actions(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "INFORMATION_SUFFICIENCY_REBASED_TO_EVENT_TRIGGERED_FINAL_COHORT",
        )
        self.assertEqual(receipt["targeted_validation"], "12_OF_12_PASS")
        for artifact in receipt["artifacts"]:
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        for value in receipt["actual_actions"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0)
        self.assertFalse(receipt["catalog"]["version_or_count_advanced"])
        self.assertFalse(receipt["next_boundary"]["authorized"])


if __name__ == "__main__":
    unittest.main()
