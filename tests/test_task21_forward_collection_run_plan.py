from __future__ import annotations

import copy
import hashlib
import json
import unittest
from datetime import date
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "configs" / "task21_forward_collection_run_plan_v1.yaml"
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task21_forward_collection_run_plan_contract_v1.md"
)
EXPECTED_NORMALIZED_SHA256 = (
    "29f8f08b26f3af3768741e09ba4e0a8881b187c7496f5a187d4ff49250ef5e3a"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _plan_errors(plan: dict) -> set[str]:
    errors: set[str] = set()
    supply = plan["candidate_supply"]
    watchlist = plan["watchlist"]
    window = plan["collection_window"]
    panel = plan["panel"]
    caps = plan["physical_caps"]
    sufficiency = plan["information_sufficiency"]
    blindness = plan["outcome_blindness"]
    recovery = plan["runtime_recovery_gate"]
    provider = plan["provider_boundary"]
    authority = plan["authority"]

    if supply["global_solana_feed"] or supply["market_wide_tick_capture"]:
        errors.add("MARKET_WIDE_CAPTURE")
    if supply["winner_only_retention_allowed"]:
        errors.add("SELECTION_BIAS_LAUNDERING")
    if set(supply["retain_evaluation_states"]) != {
        "EVALUATED_REJECTED",
        "EVALUATED_NOT_EVALUABLE",
        "WATCHLIST_ACTIVE",
        "WATCHLIST_EXITED",
    }:
        errors.add("INCOMPLETE_CANDIDATE_LINEAGE")
    if supply["max_unique_evaluated_candidates"] > 8:
        errors.add("CANDIDATE_CAP_EXPANDED")
    if watchlist["max_active_members"] > 8:
        errors.add("WATCHLIST_CAP_EXPANDED")
    if window["continuous_polling"] or window["always_on_market_feed"]:
        errors.add("CONTINUOUS_POLLING")
    if window["minimum_calendar_days"] != 30:
        errors.add("MINIMUM_WINDOW_DRIFT")
    if window["maximum_calendar_days"] != 45:
        errors.add("MAXIMUM_WINDOW_DRIFT")
    if window["automatic_extension_after_day_45"]:
        errors.add("SILENT_EXTENSION")

    expected_calls = (
        watchlist["max_active_members"]
        * panel["windows_per_member"]
        * len(panel["notionals_usd"])
        * panel["legs_per_notional"]
    )
    if expected_calls != 192 or caps["max_provider_requests"] != expected_calls:
        errors.add("PROVIDER_CALL_CAP_DRIFT")
    if panel["retries"] != 0 or caps["max_retries"] != 0:
        errors.add("RETRY_AUTHORITY_LEAK")
    if panel["concurrency"] != 1 or caps["max_concurrency"] != 1:
        errors.add("CONCURRENCY_DRIFT")
    if caps["cash_spend_usd_cents"] != 0:
        errors.add("CASH_AUTHORITY_LEAK")
    if caps["wallet_signer_transaction_actions"] != 0:
        errors.add("WALLET_AUTHORITY_LEAK")
    if caps["unlimited_or_missing_cap_allowed"]:
        errors.add("UNLIMITED_CAP")

    if sufficiency["earliest_decision_day"] < 30:
        errors.add("EARLY_DECISION")
    if sufficiency["hard_stop_day"] != 45:
        errors.add("HARD_STOP_DRIFT")
    if sufficiency["positive_hypothesis_result_required"]:
        errors.add("SUCCESS_QUOTA")
    if sufficiency["provider_failure_quota_required"]:
        errors.add("FAILURE_QUOTA")
    if (
        sufficiency["minimum_complete_panels"]
        != sufficiency["minimum_complete_members"]
        * sufficiency["panels_per_complete_member"]
    ):
        errors.add("PANEL_SUFFICIENCY_MATH")
    if (
        sufficiency["minimum_complete_quote_pairs"]
        != sufficiency["minimum_complete_panels"]
        * sufficiency["quote_pairs_per_complete_panel"]
    ):
        errors.add("PAIR_SUFFICIENCY_MATH")

    if not blindness["active"] or blindness["tuning_during_collection_allowed"]:
        errors.add("OUTCOME_TUNING")
    if not recovery["must_pass_before_first_forward_write"]:
        errors.add("RECOVERY_GATE_BYPASS")
    if recovery["status"] != "REQUIRED_NOT_EXECUTED":
        errors.add("FALSE_RUNTIME_RECOVERY_CLAIM")
    if provider["selected_provider"] is not None:
        errors.add("PROVIDER_PRESELECTED")
    if not provider["refresh_required_before_live_shakedown"]:
        errors.add("STALE_PROVIDER_FACTS_ALLOWED")
    if provider["purchase_authority"] or provider["credentials_authorized"]:
        errors.add("PROVIDER_AUTHORITY_LEAK")

    zero_authority = {
        "network_calls",
        "provider_api_rpc_wss_calls",
        "drive_reads",
        "drive_writes",
        "credential_use",
        "candidate_admissions",
        "collector_executions",
        "raw_or_dataset_writes",
        "backup_executions",
        "restore_executions",
        "cash_spend_usd_cents",
        "provider_credits",
        "dependency_changes",
    }
    if any(authority[key] != 0 for key in zero_authority):
        errors.add("ATOM2_EXTERNAL_AUTHORITY_LEAK")
    if any(
        authority[key]
        for key in (
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
    ):
        errors.add("ATOM2_MUTATION_AUTHORITY_LEAK")
    return errors


class TestTask21ForwardCollectionRunPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))

    def test_frozen_inputs_are_exact(self) -> None:
        for item in self.plan["frozen_inputs"]:
            path = ROOT / item["path"]
            assert path.is_file(), item["asset_id"]
            assert _sha256(path) == item["sha256"], item["asset_id"]

    def test_plan_is_byte_stable_and_contract_is_bounded(self) -> None:
        normalized = _canonical_bytes(self.plan)
        assert hashlib.sha256(normalized).hexdigest() == EXPECTED_NORMALIZED_SHA256
        assert _canonical_bytes(yaml.safe_load(PLAN_PATH.read_text("utf-8"))) == normalized
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        assert "whole 30–45-day task, not per day" in contract
        assert "TASK21_PRE_COLLECTION_RUNTIME_RECOVERY_GATE" in contract

    def test_population_retains_rejections_and_states_scope(self) -> None:
        supply = self.plan["candidate_supply"]
        assert supply["mode"] == "REGISTERED_FORWARD_CANDIDATE_NOMINATION_EVENTS"
        assert supply["max_unique_evaluated_candidates"] == 8
        assert supply["generalization_boundary"] == (
            "DOCUMENTED_NOMINATION_AND_ADMISSION_PROCESS_ONLY"
        )
        assert supply["market_wide_prevalence_claim_allowed"] is False
        assert supply["winner_only_retention_allowed"] is False

    def test_192_call_cap_is_derived_not_asserted_in_isolation(self) -> None:
        panel = self.plan["panel"]
        watchlist = self.plan["watchlist"]
        expected = (
            watchlist["max_active_members"]
            * panel["windows_per_member"]
            * len(panel["notionals_usd"])
            * panel["legs_per_notional"]
        )
        assert expected == 192
        assert self.plan["physical_caps"]["max_provider_requests"] == expected
        assert self.plan["physical_caps"]["max_response_bytes"] == 24 * 1_048_576
        assert self.plan["physical_caps"]["max_stored_bytes"] == 24 * 5_242_880

    def test_information_sufficiency_is_outcome_independent(self) -> None:
        gate = self.plan["information_sufficiency"]
        assert gate["earliest_decision_day"] == 30
        assert gate["hard_stop_day"] == 45
        assert gate["minimum_complete_members"] == 5
        assert gate["minimum_complete_panels"] == 15
        assert gate["minimum_complete_quote_pairs"] == 60
        assert gate["positive_hypothesis_result_required"] is False
        assert gate["provider_failure_quota_required"] is False

    def test_provider_snapshot_is_advisory_and_refresh_gated(self) -> None:
        provider = self.plan["provider_boundary"]
        snapshot = provider["pricing_snapshot"]
        assert provider["selected_provider"] is None
        assert provider["purchase_authority"] is False
        assert provider["refresh_required_before_live_shakedown"] is True
        assert date.fromisoformat(snapshot["as_of"]) == date(2026, 7, 29)
        assert date.fromisoformat(snapshot["expires_at"]) == date(2026, 8, 28)

    def test_recovery_gate_blocks_first_forward_write(self) -> None:
        recovery = self.plan["runtime_recovery_gate"]
        assert recovery["status"] == "REQUIRED_NOT_EXECUTED"
        assert recovery["must_pass_before_first_forward_write"] is True
        assert set(recovery["minimum_evidence"]) == {
            "PRIVATE_SEPARATE_FAILURE_DOMAIN_DESTINATION",
            "CREATE_ONLY_CONTENT_ADDRESSED_BACKUP",
            "EXACT_REMOTE_READBACK",
            "ISOLATED_SAMPLE_RESTORE",
            "BACKUP_AND_RESTORE_HEALTH_ALERTS",
            "NO_SECRET_MATERIAL_IN_EVIDENCE",
        }

    def test_frozen_plan_passes_and_adversarial_mutations_fail_closed(self) -> None:
        assert _plan_errors(self.plan) == set()
        vectors: list[tuple[str, str, dict]] = []

        candidate = copy.deepcopy(self.plan)
        candidate["candidate_supply"]["market_wide_tick_capture"] = True
        vectors.append(("market_wide", "MARKET_WIDE_CAPTURE", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["candidate_supply"]["winner_only_retention_allowed"] = True
        vectors.append(("winner_only", "SELECTION_BIAS_LAUNDERING", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["physical_caps"]["max_provider_requests"] = 193
        vectors.append(("call_inflation", "PROVIDER_CALL_CAP_DRIFT", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["collection_window"]["continuous_polling"] = True
        vectors.append(("continuous", "CONTINUOUS_POLLING", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["outcome_blindness"]["tuning_during_collection_allowed"] = True
        vectors.append(("tuning", "OUTCOME_TUNING", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["runtime_recovery_gate"][
            "must_pass_before_first_forward_write"
        ] = False
        vectors.append(("recovery_bypass", "RECOVERY_GATE_BYPASS", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["provider_boundary"]["selected_provider"] = "JUPITER"
        vectors.append(("provider_preselected", "PROVIDER_PRESELECTED", candidate))

        candidate = copy.deepcopy(self.plan)
        candidate["authority"]["network_calls"] = 1
        vectors.append(
            ("external_authority", "ATOM2_EXTERNAL_AUTHORITY_LEAK", candidate)
        )

        assert len(vectors) == 8
        for vector_id, expected_error, candidate in vectors:
            assert expected_error in _plan_errors(candidate), vector_id
