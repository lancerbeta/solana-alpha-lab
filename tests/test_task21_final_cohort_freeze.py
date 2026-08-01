from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_final_cohort_freeze import (
    Task21FinalCohortFreezeError,
    evaluate_final_cohort_freeze,
    inventory_evidence_roots,
)


PLAN_PATH = ROOT / "configs" / "task21_final_cohort_freeze_v1.yaml"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "task21_final_cohort_freeze_contract_v1.md"
ACCEPTANCE_PATH = (
    ROOT / "docs" / "evidence" / "task21" / "final_cohort_freeze_acceptance_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21FinalCohortFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
        cls.evidence = {}
        for item in cls.plan["protected_inputs"]:
            if item["path"].endswith(".json"):
                cls.evidence[item["role"]] = json.loads(
                    (ROOT / item["path"]).read_text(encoding="utf-8")
                )

    def test_protected_inputs_match_exact_bytes(self) -> None:
        for item in self.plan["protected_inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(_sha256(path), item["sha256"], item["path"])

    def test_review_freezes_evidence_but_not_dataset(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["cohort_evidence_frozen"])
        self.assertFalse(result["dataset_frozen"])
        self.assertTrue(result["a7_review_eligible"])
        self.assertFalse(result["task22_eligible"])

    def test_exact_five_member_cohort(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertEqual(result["new_members_complete"], 5)
        self.assertEqual(len(set(result["member_ids"])), 5)
        self.assertEqual(len(set(result["mints"])), 5)
        self.assertEqual(result["maximum_member_share_one_batch"], 0.6)

    def test_exact_panel_and_quote_counts(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertEqual(result["complete_panels"], 15)
        self.assertEqual(result["complete_quote_pairs"], 60)
        self.assertEqual(result["complete_quote_attempts"], 120)

    def test_three_novel_source_batches(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertEqual(result["independent_nomination_batches_total"], 3)
        ids = [item["source_observation_id"] for item in self.plan["source_batches"]]
        hashes = [item["source_content_sha256"] for item in self.plan["source_batches"]]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(len(set(hashes)), 3)

    def test_exact_usage_and_remaining_caps(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertEqual(result["extension_usage"]["provider_api_rpc_wss_calls"], 124)
        self.assertEqual(result["extension_usage"]["source_requests"], 4)
        self.assertEqual(result["extension_usage"]["jupiter_calls"], 120)
        self.assertEqual(result["extension_usage"]["local_file_count"], 59)
        self.assertEqual(result["whole_task_usage_at_stop"]["external_requests"], 184)
        self.assertEqual(result["whole_task_usage_at_stop"]["quote_requests"], 176)

    def test_outcomes_stay_sealed_and_recovery_gap_is_explicit(self) -> None:
        result = evaluate_final_cohort_freeze(self.plan, self.evidence)
        self.assertFalse(result["quote_route_price_cost_values_read"])
        self.assertTrue(result["full_dataset_remote_restore_required"])
        self.assertFalse(self.plan["recovery"]["r3_p2_included_in_that_restore"])
        self.assertFalse(
            self.plan["recovery"]["entire_final_dataset_included_in_that_restore"]
        )

    def test_local_authority_has_no_external_or_delivery_actions(self) -> None:
        evaluate_final_cohort_freeze(self.plan, self.evidence)
        for key, value in self.plan["authority"].items():
            if key in {"class", "source", "gate_phrase", "managed_files"}:
                continue
            if isinstance(value, bool):
                self.assertFalse(value, key)
            else:
                self.assertEqual(value, 0, key)

    def test_adversarial_member_substitution_fails(self) -> None:
        evidence = copy.deepcopy(self.evidence)
        evidence["R3_SOURCE_P0_RUNTIME_ACCEPTANCE"]["admission"]["members"][0][
            "member_id"
        ] = "T21-WATCH-SUBSTITUTED"
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "member_drift"):
            evaluate_final_cohort_freeze(self.plan, evidence)

    def test_adversarial_early_panel_fails(self) -> None:
        evidence = copy.deepcopy(self.evidence)
        p0 = evidence["R3_SOURCE_P0_RUNTIME_ACCEPTANCE"]["p0"]["windows"][0]
        p1 = evidence["R3_P1_RUNTIME_ACCEPTANCE"]["p1"]["windows"][0]
        p1["triggered_at"] = p0["completed_at"]
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "p1_too_early"):
            evaluate_final_cohort_freeze(self.plan, evidence)

    def test_adversarial_source_reuse_fails(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["source_batches"][2]["source_observation_id"] = plan["source_batches"][1][
            "source_observation_id"
        ]
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "source_id_collision"):
            evaluate_final_cohort_freeze(plan, self.evidence)

    def test_adversarial_budget_overrun_fails(self) -> None:
        plan = copy.deepcopy(self.plan)
        evidence = copy.deepcopy(self.evidence)
        plan["whole_task_usage_at_stop"]["external_requests"] = 193
        evidence["R3_P2_RUNTIME_ACCEPTANCE"]["budget_after_p2"][
            "external_requests"
        ] = 193
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "cap_breach"):
            evaluate_final_cohort_freeze(plan, evidence)

    def test_adversarial_outcome_or_recovery_drift_fails(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["protected_history"]["outcome_blindness_preserved"] = False
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "outcome_unsealed"):
            evaluate_final_cohort_freeze(plan, self.evidence)

        evidence = copy.deepcopy(self.evidence)
        evidence["R3_PRE_P2_RECOVERY_ACCEPTANCE"]["status"] = "STALE"
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "recovery_not_proven"):
            evaluate_final_cohort_freeze(self.plan, evidence)

    def test_adversarial_authority_expansion_fails(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["authority"]["provider_api_rpc_wss_calls"] = 1
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "authority_leak"):
            evaluate_final_cohort_freeze(plan, self.evidence)

        plan = copy.deepcopy(self.plan)
        plan["next_boundary"]["status"] = "AUTHORIZED"
        with self.assertRaisesRegex(Task21FinalCohortFreezeError, "a7_authorized"):
            evaluate_final_cohort_freeze(plan, self.evidence)

    def test_inventory_is_content_addressed_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "one"
            second = root / "two"
            first.mkdir()
            second.mkdir()
            (first / "a.bin").write_bytes(b"alpha")
            (second / "b.bin").write_bytes(b"beta")
            inventory = inventory_evidence_roots(
                root,
                (
                    {"root": "one", "file_count": 1, "stored_bytes": 5},
                    {"root": "two", "file_count": 1, "stored_bytes": 4},
                ),
            )
            self.assertEqual(inventory["root_count"], 2)
            self.assertEqual(inventory["file_count"], 2)
            self.assertEqual(inventory["stored_bytes"], 9)
            with self.assertRaisesRegex(
                Task21FinalCohortFreezeError, "inventory_stored_bytes_drift"
            ):
                inventory_evidence_roots(
                    root,
                    ({"root": "one", "file_count": 1, "stored_bytes": 6},),
                )

    def test_contract_contains_decision_changing_rules(self) -> None:
        text = " ".join(CONTRACT_PATH.read_text(encoding="utf-8").split())
        for required in (
            "evidence-set freeze",
            "not yet the final dataset freeze",
            "Five exact new members",
            "120 terminal quote attempts",
            "3 / 5 = 0.6",
            "1,801 seconds",
            "184 / 192 external requests",
            "full final-dataset recovery",
            "zero provider/API/RPC/WSS or Drive calls",
            "task22_eligible=false",
        ):
            self.assertIn(required, text)

    def test_acceptance_receipt_binds_candidate_and_zero_actions(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "FINAL_COHORT_COMPLETE_AND_EVIDENCE_SET_FROZEN_PENDING_A7_RECOVERY",
        )
        self.assertEqual(receipt["targeted_validation"], "17_OF_17_PASS")
        for artifact in receipt["artifacts"]:
            self.assertEqual(_sha256(ROOT / artifact["path"]), artifact["sha256"])
        self.assertEqual(receipt["local_inventory"]["file_count"], 59)
        self.assertEqual(receipt["local_inventory"]["stored_bytes"], 807082)
        for value in receipt["actual_actions"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0)
        self.assertFalse(receipt["review_result"]["dataset_frozen"])
        self.assertFalse(receipt["next_boundary"]["authorized"])


if __name__ == "__main__":
    unittest.main()
