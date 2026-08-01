from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from solana_alpha_lab.task21_event_triggered_final_cohort import (
    Task21FinalCohortError,
    evaluate_nomination_observation,
    evaluate_panel_trigger,
    initial_runtime_state,
    prepare_offline_scenario,
    validate_protected_inputs,
    validate_runtime_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs/task21_event_triggered_final_cohort_runtime_v1.yaml"
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/task21/event_triggered_final_cohort_offline_v1.json"
)


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class Task21EventTriggeredFinalCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_yaml(CONFIG_PATH)
        cls.scenario = load_json(FIXTURE_PATH)

    def _happy_result(self) -> dict:
        return prepare_offline_scenario(
            config=deepcopy(self.config), scenario=deepcopy(self.scenario)
        )

    def _first_member(self) -> dict:
        state = initial_runtime_state(self.config)
        result = evaluate_nomination_observation(
            config=self.config,
            state=state,
            observation=deepcopy(self.scenario["happy_path_observations"][0]),
            admitted_at="2026-08-01T11:00:00Z",
        )
        return result["members"][0]

    def _panel_decision(self, **overrides: object) -> dict:
        arguments: dict[str, object] = {
            "config": self.config,
            "member": self._first_member(),
            "panel_history": [],
            "requested_panel": "P0",
            "now": "2026-08-01T11:00:00Z",
            "recovery_health": "HEALTHY",
            "response_bytes_used": 86_091,
            "stored_bytes_used": 364_898,
            "dataset_bytes_used": 364_898,
            "free_disk_bytes": 186_280_022_016,
            "remaining_reserved_provider_calls": 24,
        }
        arguments.update(overrides)
        return evaluate_panel_trigger(**arguments)  # type: ignore[arg-type]

    def test_config_is_strictly_local_and_transport_free(self) -> None:
        validate_runtime_config(self.config)
        self.assertIsNone(self.config["transport"])
        self.assertIsNone(self.config["scheduler"])
        self.assertEqual(self.config["authority"]["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(self.config["next_boundary"]["task22_authorized"])

    def test_protected_inputs_match_actual_hashes(self) -> None:
        validate_protected_inputs(repo_root=REPO_ROOT, config=self.config)

    def test_happy_path_is_exact_three_plus_two(self) -> None:
        receipt = self._happy_result()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual([len(row["members"]) for row in receipt["batch_receipts"]], [3, 2])
        self.assertEqual(receipt["new_members"], 5)
        self.assertEqual(receipt["planned_panels"], 15)
        self.assertEqual(receipt["planned_quote_pairs"], 60)
        self.assertEqual(
            receipt["projected_budget"],
            {"external_requests": 184, "source_requests": 8, "quote_requests": 176},
        )
        self.assertEqual(receipt["external_request_headroom"], 8)
        self.assertFalse(receipt["dataset_ready"])
        self.assertEqual(receipt["provider_calls_performed"], 0)

    def test_member_identity_is_deterministic(self) -> None:
        first = self._happy_result()
        second = self._happy_result()
        first_ids = [
            member["member_id"]
            for batch in first["batch_receipts"]
            for member in batch["members"]
        ]
        second_ids = [
            member["member_id"]
            for batch in second["batch_receipts"]
            for member in batch["members"]
        ]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(set(first_ids)), 5)

    def test_duplicate_source_id_is_retained_and_stops(self) -> None:
        state = initial_runtime_state(self.config)
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["source_observation_id"] = state["accepted_source_observations"][0][
            "source_observation_id"
        ]
        result = evaluate_nomination_observation(
            config=self.config,
            state=state,
            observation=observation,
            admitted_at=observation["observed_at"],
        )
        self.assertEqual(result["status"], "STOPPED_NO_ADMISSION")
        self.assertEqual(result["reason"], "SOURCE_OBSERVATION_ID_NOT_NEW")
        self.assertEqual(result["state"]["budget"]["used"]["source_requests"], 6)
        self.assertEqual(len(result["state"]["retained_source_observations"]), 1)

    def test_duplicate_source_content_is_retained_and_stops(self) -> None:
        state = initial_runtime_state(self.config)
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["source_content_sha256"] = state["accepted_source_observations"][0][
            "source_content_sha256"
        ]
        result = evaluate_nomination_observation(
            config=self.config,
            state=state,
            observation=observation,
            admitted_at=observation["observed_at"],
        )
        self.assertEqual(result["reason"], "SOURCE_CONTENT_NOT_NOVEL")
        self.assertEqual(result["members"], [])

    def test_stale_observation_stops_without_admission(self) -> None:
        state = initial_runtime_state(self.config)
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["observed_at"] = "2026-07-30T16:28:59.084Z"
        result = evaluate_nomination_observation(
            config=self.config,
            state=state,
            observation=observation,
            admitted_at="2026-08-01T11:00:00Z",
        )
        self.assertEqual(result["reason"], "OBSERVED_AT_NOT_STRICTLY_AFTER_PRIOR_BATCH")

    def test_candidate_order_drift_fails_closed(self) -> None:
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["candidates"].reverse()
        with self.assertRaisesRegex(Task21FinalCohortError, "candidate_sort_order_drift"):
            evaluate_nomination_observation(
                config=self.config,
                state=initial_runtime_state(self.config),
                observation=observation,
                admitted_at=observation["observed_at"],
            )

    def test_outcome_field_fails_closed_before_admission(self) -> None:
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["candidates"][0]["price_usd"] = 17
        with self.assertRaisesRegex(Task21FinalCohortError, "outcome_field_forbidden"):
            evaluate_nomination_observation(
                config=self.config,
                state=initial_runtime_state(self.config),
                observation=observation,
                admitted_at=observation["observed_at"],
            )

    def test_seen_mint_is_retained_as_rejected(self) -> None:
        observation = deepcopy(self.scenario["happy_path_observations"][0])
        observation["candidates"] = [observation["candidates"][0]]
        observation["candidates"][0]["mint"] = self.config["initial_state"]["seen_mints"][0]
        result = evaluate_nomination_observation(
            config=self.config,
            state=initial_runtime_state(self.config),
            observation=observation,
            admitted_at=observation["observed_at"],
        )
        self.assertEqual(result["status"], "STOPPED_NO_ADMISSION")
        self.assertEqual(
            result["candidate_states"][0]["state"],
            "EVALUATED_REJECTED_DUPLICATE_MINT",
        )
        self.assertEqual(result["state"]["evaluated_candidates_used"], 4)

    def test_source_budget_cap_fails_closed(self) -> None:
        state = initial_runtime_state(self.config)
        state["budget"]["used"]["source_requests"] = 8
        with self.assertRaisesRegex(Task21FinalCohortError, "source_request_cap_exceeded"):
            evaluate_nomination_observation(
                config=self.config,
                state=state,
                observation=deepcopy(self.scenario["happy_path_observations"][0]),
                admitted_at="2026-08-01T11:00:00Z",
            )

    def test_p0_is_ready_only_for_separate_authority(self) -> None:
        decision = self._panel_decision()
        self.assertEqual(decision["status"], "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY")
        self.assertEqual(decision["provider_api_rpc_wss_calls_max"], 8)
        self.assertFalse(decision["external_actions_authorized"])

    def test_p1_waits_for_exact_minimum_separation(self) -> None:
        history = [{"panel_id": "P0", "completed_at": "2026-08-01T11:00:10Z"}]
        early = self._panel_decision(
            panel_history=history,
            requested_panel="P1",
            now="2026-08-01T11:30:10Z",
        )
        self.assertEqual(early["status"], "WAIT_MINIMUM_SEPARATION")
        self.assertEqual(early["eligible_at"], "2026-08-01T11:30:11Z")
        due = self._panel_decision(
            panel_history=history,
            requested_panel="P1",
            now="2026-08-01T11:30:11Z",
        )
        self.assertEqual(due["status"], "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY")

    def test_expired_member_retains_gap_without_backfill(self) -> None:
        decision = self._panel_decision(now="2026-08-02T11:00:01Z")
        self.assertEqual(decision["status"], "RETAIN_GAP_STOP_NO_BACKFILL")
        self.assertEqual(decision["reason"], "MEMBER_TOTAL_SPAN_EXPIRED")

    def test_recovery_budget_and_physical_caps_stop_safely(self) -> None:
        cases = (
            ({"recovery_health": "STALE"}, "RECOVERY_HEALTH_NOT_HEALTHY"),
            ({"remaining_reserved_provider_calls": 7}, "REMAINING_BUDGET_CANNOT_COMPLETE_PANEL"),
            ({"response_bytes_used": 25_165_824}, "RESPONSE_BYTE_CAP_REACHED"),
            ({"stored_bytes_used": 125_829_120}, "STORED_BYTE_CAP_REACHED"),
            ({"dataset_bytes_used": 268_435_456}, "DATASET_BYTE_CAP_REACHED"),
            ({"free_disk_bytes": 2_147_483_647}, "FREE_DISK_FLOOR_NOT_MET"),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                decision = self._panel_decision(**overrides)
                self.assertEqual(decision["status"], "STOPPED_SAFELY")
                self.assertEqual(decision["reason"], reason)
                self.assertFalse(decision["external_actions_authorized"])

    def test_next_boundary_is_exact_and_unauthorized(self) -> None:
        receipt = self._happy_result()
        self.assertEqual(
            receipt["next_boundary"]["atom_id"],
            "T21-A6S_R2_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1",
        )
        self.assertEqual(receipt["next_boundary"]["status"], "NOT_AUTHORIZED")
        self.assertTrue(
            receipt["next_boundary"]["requires_separate_external_authority"]
        )


if __name__ == "__main__":
    unittest.main()
