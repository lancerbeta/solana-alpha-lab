from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "configs"
    / "task21_admission_horizon_budget_reconciliation_v1.yaml"
)
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "task21_admission_horizon_budget_reconciliation_contract_v1.md"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "admission_horizon_budget_reconciliation_acceptance_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _errors(plan: dict) -> set[str]:
    errors: set[str] = set()
    close = plan["t1_capacity_close"]
    future = plan["future_tranches"]
    capture = plan["capture_allocation"]
    sentinel = capture["sentinel"]
    budget = plan["budget"]
    authority = plan["authority"]
    boundary = plan["next_boundary"]

    if plan["conflict_resolution"]["mode"] != "FORWARD_ONLY_OVERLAY":
        errors.add("NOT_FORWARD_ONLY")
    if plan["conflict_resolution"]["historical_artifacts_rewritten"]:
        errors.add("HISTORICAL_REWRITE")

    if (
        close["exact_frozen_nomination_count"] != 3
        or close["accepted_t1_active_member_cap"] != 3
        or not close["exact_set_sealed_before_reconciliation"]
        or close["quote_outcomes_observed_before_reconciliation"]
        or close["prior_relevant_quote_outcome_exposure"]
        or close["later_or_backdated_nomination_can_reorder"]
    ):
        errors.add("T1_EARLY_CLOSE_NOT_PROVEN")
    if close["entered_at"] != "ACTUAL_EVALUATION_AND_ADMISSION_TIME":
        errors.add("BACKDATED_ADMISSION_TIME")
    if close["original_future_close_used_as_entered_at"]:
        errors.add("FUTURE_CLOSE_USED_AS_ENTERED_AT")
    if close["enabled_for_external_execution"]:
        errors.add("EARLY_CLOSE_AUTHORITY_LEAK")

    expected_future = [
        {
            "tranche_id": "T2",
            "start_day_inclusive": 7,
            "end_day_exclusive": 14,
            "active_member_cap": 3,
        },
        {
            "tranche_id": "T3",
            "start_day_inclusive": 14,
            "end_day_exclusive": 21,
            "active_member_cap": 2,
        },
    ]
    if (
        future["anchor"] != "ORIGINAL_T1_ANCHOR"
        or future["schedule_compressed"]
        or future["unused_capacity_transfer_allowed"]
        or future["tranches"] != expected_future
    ):
        errors.add("T2_T3_SCHEDULE_DRIFT")

    base = [
        (item["window_id"], item["offset_seconds"])
        for item in capture["base_horizons"]
    ]
    supplemental = [
        (item["window_id"], item["offset_seconds"])
        for item in sentinel["supplemental_horizons"]
    ]
    if base != [("H0", 0), ("H1", 3600), ("H6", 21600)]:
        errors.add("BASE_HORIZON_DRIFT")
    if supplemental != [
        ("H24", 86400),
        ("H72", 259200),
        ("H168", 604800),
    ]:
        errors.add("SUPPLEMENTAL_HORIZON_DRIFT")
    if capture["base_panels_per_complete_member"] != 3:
        errors.add("COMPLETE_MEMBER_PANEL_COUNT_DRIFT")
    if capture["maximum_base_capture_members"] > 6:
        errors.add("CAPTURE_MEMBER_CAP_UNSAFE")
    if not capture["reserve_at_least_one_base_capture_slot_per_tranche"]:
        errors.add("TRANCHE_COVERAGE_NOT_RESERVED")
    if sentinel["maximum_members"] != 1:
        errors.add("SENTINEL_COUNT_DRIFT")
    if sentinel["selection_key"] != [
        "first_reliable_available_at",
        "observed_at",
        "nomination_event_id",
    ]:
        errors.add("SENTINEL_SELECTION_DRIFT")
    if sentinel["outcome_or_route_input_allowed"]:
        errors.add("OUTCOME_DEPENDENT_SENTINEL")
    if (
        sentinel["supplemental_panels_count_toward_complete_member"]
        or sentinel["supplemental_panels_count_toward_minimum_complete_panels"]
    ):
        errors.add("SUPPLEMENTAL_PANEL_SUFFICIENCY_INFLATION")
    if (
        capture["missed_window_policy"]
        != "RETAIN_EXPLICIT_GAP_NO_BACKFILL"
        or capture["silent_reschedule_allowed"]
        or capture["scheduler_or_background_process"]
    ):
        errors.add("TIME_WINDOW_OR_SCHEDULER_DRIFT")

    minimum = budget["minimum_sufficient_dataset"]
    maximum = budget["overlay_operational_maximum"]
    if budget["accepted_external_requests_whole_task_max"] != 192:
        errors.add("OUTER_REQUEST_CAP_DRIFT")
    if budget["source_requests_reserved_max"] != 8:
        errors.add("SOURCE_RESERVATION_DRIFT")
    if budget["quote_requests_reserved_max"] != 184:
        errors.add("QUOTE_RESERVATION_DRIFT")
    if budget["provider_calls_per_panel_max"] != 8:
        errors.add("PANEL_CALL_CAP_DRIFT")

    expected_minimum_base = (
        minimum["complete_members"]
        * capture["base_panels_per_complete_member"]
        * budget["provider_calls_per_panel_max"]
    )
    expected_sentinel = (
        len(sentinel["supplemental_horizons"])
        * budget["provider_calls_per_panel_max"]
    )
    expected_minimum_total = (
        budget["source_requests_reserved_max"]
        + expected_minimum_base
        + expected_sentinel
    )
    if (
        expected_minimum_base != 120
        or minimum["base_quote_calls_max"] != expected_minimum_base
        or minimum["sentinel_supplemental_quote_calls_max"] != expected_sentinel
        or minimum["source_plus_quote_calls_max"] != expected_minimum_total
        or minimum["outer_ceiling_headroom"] != 192 - expected_minimum_total
    ):
        errors.add("MINIMUM_BUDGET_ARITHMETIC_DRIFT")

    expected_maximum_base = (
        maximum["base_capture_members"]
        * capture["base_panels_per_complete_member"]
        * budget["provider_calls_per_panel_max"]
    )
    expected_maximum_quote = expected_maximum_base + expected_sentinel
    expected_maximum_total = (
        budget["source_requests_reserved_max"] + expected_maximum_quote
    )
    if (
        maximum["base_capture_members"]
        != capture["maximum_base_capture_members"]
        or maximum["base_quote_calls_max"] != expected_maximum_base
        or maximum["quote_calls_max"] != expected_maximum_quote
        or maximum["source_plus_quote_calls_max"] != expected_maximum_total
        or maximum["outer_ceiling_headroom"] != 192 - expected_maximum_total
        or expected_maximum_quote > budget["quote_requests_reserved_max"]
        or expected_maximum_total > 192
    ):
        errors.add("MAXIMUM_BUDGET_ARITHMETIC_DRIFT")

    h0 = budget["next_h0_stage"]
    if (
        h0["t1_candidate_admissions_max"] != 3
        or h0["h0_panels_max"] != 3
        or h0["quote_calls_max"] != 24
        or h0["authorized"]
    ):
        errors.add("H0_SCOPE_OR_AUTHORITY_DRIFT")

    zero_fields = (
        "network_calls",
        "provider_api_rpc_wss_calls",
        "drive_reads",
        "drive_writes",
        "credential_use",
        "candidate_admissions",
        "live_collector_executions",
        "raw_or_dataset_writes",
        "backup_executions",
        "restore_executions",
        "provider_credits",
        "cash_spend_usd_cents",
        "dependency_changes",
    )
    if any(authority[field] != 0 for field in zero_fields):
        errors.add("AUTHORITY_LEAK")
    false_fields = (
        "scheduler_or_background_process",
        "commit",
        "push",
        "pull_request",
        "merge",
        "wallet_actions",
        "signer_actions",
        "transaction_actions",
        "ui_changes",
        "destructive_actions",
    )
    if any(authority[field] for field in false_fields):
        errors.add("AUTHORITY_LEAK")
    if boundary["status"] != "NOT_AUTHORIZED":
        errors.add("NEXT_BOUNDARY_STATUS_DRIFT")
    boundary_false_fields = (
        "provider_endpoint_selected",
        "candidate_admissions_authorized",
        "provider_api_rpc_wss_calls_authorized",
        "jupiter_quote_calls_authorized",
        "raw_or_dataset_writes_authorized",
        "drive_actions_authorized",
        "scheduler_or_background_process_authorized",
        "a7_authorized",
    )
    if any(boundary[field] for field in boundary_false_fields):
        errors.add("NEXT_BOUNDARY_AUTHORITY_LEAK")
    return errors


class Task21AdmissionHorizonBudgetReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))

    def test_protected_inputs_match_exact_bytes(self) -> None:
        for item in self.plan["protected_inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(_sha256(path), item["sha256"], item["path"])
            if "bytes" in item:
                self.assertEqual(path.stat().st_size, item["bytes"])

    def test_reconciliation_is_semantically_valid(self) -> None:
        self.assertEqual(_errors(self.plan), set())

    def test_t1_early_close_is_exact_sealed_capacity_close(self) -> None:
        close = self.plan["t1_capacity_close"]
        self.assertEqual(
            close["disposition"],
            "EARLY_CAPACITY_CLOSE_FOR_EXACT_FROZEN_SET",
        )
        self.assertEqual(
            close["exact_frozen_nomination_count"],
            close["accepted_t1_active_member_cap"],
        )
        self.assertFalse(close["enabled_for_external_execution"])

    def test_budget_has_minimum_and_operational_headroom(self) -> None:
        budget = self.plan["budget"]
        self.assertEqual(
            budget["minimum_sufficient_dataset"]["source_plus_quote_calls_max"],
            152,
        )
        self.assertEqual(
            budget["minimum_sufficient_dataset"]["outer_ceiling_headroom"],
            40,
        )
        self.assertEqual(
            budget["overlay_operational_maximum"]["source_plus_quote_calls_max"],
            176,
        )
        self.assertEqual(
            budget["overlay_operational_maximum"]["outer_ceiling_headroom"],
            16,
        )

    def test_adversarial_all_members_get_six_horizons_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["capture_allocation"]["base_horizons"].extend(
            changed["capture_allocation"]["sentinel"]["supplemental_horizons"]
        )
        self.assertIn("BASE_HORIZON_DRIFT", _errors(changed))

    def test_adversarial_unsealed_early_close_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["t1_capacity_close"][
            "exact_set_sealed_before_reconciliation"
        ] = False
        self.assertIn("T1_EARLY_CLOSE_NOT_PROVEN", _errors(changed))

    def test_adversarial_t2_compression_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["future_tranches"]["tranches"][0]["start_day_inclusive"] = 0
        self.assertIn("T2_T3_SCHEDULE_DRIFT", _errors(changed))

    def test_adversarial_outcome_selected_sentinel_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["capture_allocation"]["sentinel"][
            "outcome_or_route_input_allowed"
        ] = True
        self.assertIn("OUTCOME_DEPENDENT_SENTINEL", _errors(changed))

    def test_adversarial_budget_inflation_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["capture_allocation"]["maximum_base_capture_members"] = 8
        self.assertIn("CAPTURE_MEMBER_CAP_UNSAFE", _errors(changed))
        self.assertIn("MAXIMUM_BUDGET_ARITHMETIC_DRIFT", _errors(changed))

    def test_adversarial_scheduler_or_authority_leak_fails(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["capture_allocation"]["scheduler_or_background_process"] = True
        changed["authority"]["provider_api_rpc_wss_calls"] = 1
        changed["next_boundary"]["candidate_admissions_authorized"] = True
        self.assertIn("TIME_WINDOW_OR_SCHEDULER_DRIFT", _errors(changed))
        self.assertIn("AUTHORITY_LEAK", _errors(changed))
        self.assertIn("NEXT_BOUNDARY_AUTHORITY_LEAK", _errors(changed))

    def test_contract_states_non_claims_and_forward_only_boundaries(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        for required in (
            "forward-only overlay",
            "remain byte-for-byte unchanged",
            "must not be used as `entered_at`",
            "Exactly one sentinel",
            "There is no background scheduler",
            "proposed caps, not authority",
            "zero provider/API/RPC/WSS calls",
            "pending `T21-A7`",
        ):
            self.assertIn(required, text)

    def test_acceptance_receipt_binds_artifacts_and_zero_actions(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha256(ACCEPTANCE_PATH),
            "6afa1908ad7e086c32fbe0cc429ea4de2516cef137fd5c5a190b99ba6870b77a",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "ADMISSION_HORIZON_BUDGET_RECONCILED_FORWARD_ONLY",
        )
        forward_evolved = {
            "configs/task21_admission_horizon_budget_reconciliation_v1.yaml",
            "tests/test_task21_admission_horizon_budget_reconciliation.py",
        }
        for artifact in receipt["artifacts"]:
            if artifact["path"] in forward_evolved:
                continue
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        self.assertEqual(set(receipt["actual_actions"].values()), {0, False})
        self.assertFalse(receipt["catalog"]["version_or_count_advanced"])
        self.assertFalse(receipt["next_boundary"]["authorized"])


if __name__ == "__main__":
    unittest.main()
