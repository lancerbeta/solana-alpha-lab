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

from solana_alpha_lab.task21_real_nomination import (  # noqa: E402
    ATOM_ID,
    NominationPolicyError,
    evaluate_offline_batch,
    load_json,
)
from solana_alpha_lab.task21_forward_collector import (  # noqa: E402
    validate_population,
)

CONFIG = ROOT / "configs/task21_real_nomination_policy_v1.yaml"
BATCH = ROOT / "tests/fixtures/task21/real_nomination_policy_offline_batch_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(batch: dict | None = None):
    return evaluate_offline_batch(
        repo_root=ROOT,
        config_path=CONFIG,
        batch_path=BATCH,
        batch_override=batch,
    )


class Task21RealNominationPolicyTests(unittest.TestCase):
    def test_config_hashes_tranches_and_zero_external_authority(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["atom_id"], ATOM_ID)
        self.assertEqual(config["entry_gate"]["verdict"], "START_WITH_PATCH")
        self.assertEqual(
            [item["active_member_cap"] for item in config["tranches"]["order"]],
            [3, 3, 2],
        )
        for item in config["frozen_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        authority = config["authority"]
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "real_candidate_nominations",
            "real_candidate_admissions",
            "live_collector_executions",
            "forward_raw_or_dataset_writes",
            "provider_credits",
            "cash_spend_usd_cents",
            "dependency_changes",
        ):
            self.assertEqual(authority[field], 0)
        self.assertFalse(authority["scheduler_or_background_process"])

    def test_base_batch_is_deterministic_and_sufficient(self) -> None:
        first = evaluate()
        second = evaluate()
        self.assertEqual(first.receipt_bytes, second.receipt_bytes)
        receipt = first.receipt
        self.assertEqual(receipt["evaluated_nominations"], 8)
        self.assertEqual(
            receipt["state_counts"],
            {
                "EVALUATED_NOT_EVALUABLE": 1,
                "EVALUATED_REJECTED": 2,
                "WATCHLIST_ACTIVE": 5,
            },
        )
        self.assertEqual(receipt["active_members_by_tranche"], {"T1": 2, "T2": 2, "T3": 1})
        self.assertEqual(receipt["active_tranches"], 3)
        self.assertTrue(receipt["synthetic_dataset_population_sufficient"])

    def test_input_order_does_not_change_chronological_evaluation(self) -> None:
        batch = load_json(BATCH)
        batch["nomination_events"].reverse()
        receipt = evaluate(batch).receipt
        self.assertEqual(
            [item["nomination_event_id"] for item in receipt["evaluations"]],
            [f"T21-A6R-SYN-NOM-{ordinal:03d}" for ordinal in range(1, 9)],
        )

    def test_prior_exposure_and_unknown_decimals_are_retained(self) -> None:
        receipt = evaluate().receipt
        by_id = {
            item["nomination_event_id"]: item for item in receipt["evaluations"]
        }
        self.assertEqual(
            by_id["T21-A6R-SYN-NOM-003"]["evaluation_state"],
            "EVALUATED_REJECTED",
        )
        self.assertIn(
            "PRIOR_RELEVANT_QUOTE_OUTCOME_EXPOSURE",
            by_id["T21-A6R-SYN-NOM-003"]["reason_codes"],
        )
        self.assertEqual(
            by_id["T21-A6R-SYN-NOM-005"]["evaluation_state"],
            "EVALUATED_NOT_EVALUABLE",
        )
        self.assertIn(
            "MINT_DECIMALS_UNKNOWN",
            by_id["T21-A6R-SYN-NOM-005"]["reason_codes"],
        )

    def test_duplicate_mint_first_nomination_wins(self) -> None:
        receipt = evaluate().receipt
        last = receipt["evaluations"][-1]
        self.assertEqual(last["evaluation_state"], "EVALUATED_REJECTED")
        self.assertIn(
            "DUPLICATE_MINT_FIRST_NOMINATION_WINS", last["reason_codes"]
        )
        member_mints = [item["mint"] for item in receipt["membership_events"]]
        self.assertEqual(len(member_mints), len(set(member_mints)))

    def test_reference_asset_and_outcome_dependent_selection_are_rejected(self) -> None:
        batch = load_json(BATCH)
        first_inputs = batch["nomination_events"][0]["exact_rule_input_values"]
        first_inputs["mint"] = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        receipt = evaluate(batch).receipt
        self.assertIn(
            "REFERENCE_ASSET_EXCLUDED",
            receipt["evaluations"][0]["reason_codes"],
        )
        batch = load_json(BATCH)
        batch["nomination_events"][0]["exact_rule_input_values"][
            "uses_task21_quote_route_or_price_outcome"
        ] = True
        receipt = evaluate(batch).receipt
        self.assertIn(
            "OUTCOME_DEPENDENT_SELECTION_FORBIDDEN",
            receipt["evaluations"][0]["reason_codes"],
        )

    def test_forbidden_outcome_payload_field_fails_closed(self) -> None:
        batch = load_json(BATCH)
        batch["nomination_events"][0]["exact_rule_input_values"]["pnl"] = 1
        with self.assertRaisesRegex(
            NominationPolicyError, "exact_rule_input_fields_drift"
        ):
            evaluate(batch)
        batch = load_json(BATCH)
        batch["nomination_events"][0]["exact_rule_input_values"][
            "selection_basis_codes"
        ] = ["HIGH_PRICE"]
        with self.assertRaisesRegex(
            NominationPolicyError, "outcome_dependent_selection_basis_code"
        ):
            evaluate(batch)
        batch = load_json(BATCH)
        batch["nomination_events"][0]["reason_codes"] = [
            {"score": 1}
        ]
        with self.assertRaisesRegex(NominationPolicyError, "reason_codes_invalid"):
            evaluate(batch)

    def test_exact_duplicate_deduplicates_and_conflict_fails(self) -> None:
        batch = load_json(BATCH)
        batch["nomination_events"].pop()
        batch["nomination_events"].append(
            copy.deepcopy(batch["nomination_events"][0])
        )
        receipt = evaluate(batch).receipt
        self.assertEqual(receipt["exact_duplicate_events_deduplicated"], 1)
        batch["nomination_events"][-1]["reason_codes"] = ["CONFLICT"]
        with self.assertRaisesRegex(
            NominationPolicyError, "conflicting_duplicate"
        ):
            evaluate(batch)

    def test_tranche_cap_rejects_fourth_eligible_member(self) -> None:
        batch = load_json(BATCH)
        event3 = batch["nomination_events"][2]["exact_rule_input_values"]
        event3["prior_relevant_quote_outcome_exposure"] = False
        event5 = batch["nomination_events"][4]
        event5["observed_at"] = "2026-08-06T01:00:00Z"
        event5["first_reliable_available_at"] = "2026-08-06T01:00:01Z"
        event5["exact_rule_input_values"]["tranche_id"] = "T1"
        event5["exact_rule_input_values"]["mint_decimals"] = 6
        receipt = evaluate(batch).receipt
        by_id = {
            item["nomination_event_id"]: item for item in receipt["evaluations"]
        }
        self.assertIn(
            "TRANCHE_ACTIVE_MEMBER_CAP_REACHED",
            by_id["T21-A6R-SYN-NOM-005"]["reason_codes"],
        )
        self.assertEqual(receipt["active_members_by_tranche"]["T1"], 3)

    def test_late_event_is_rejected_and_close_time_drift_fails(self) -> None:
        batch = load_json(BATCH)
        batch["nomination_events"][0]["observed_at"] = "2026-08-10T00:00:00Z"
        batch["nomination_events"][0][
            "first_reliable_available_at"
        ] = "2026-08-10T00:00:01Z"
        receipt = evaluate(batch).receipt
        by_id = {
            item["nomination_event_id"]: item for item in receipt["evaluations"]
        }
        self.assertIn(
            "OUTSIDE_DECLARED_TRANCHE",
            by_id["T21-A6R-SYN-NOM-001"]["reason_codes"],
        )
        batch = load_json(BATCH)
        batch["tranche_closed_at"]["T1"] = "2026-08-09T00:00:00Z"
        with self.assertRaisesRegex(NominationPolicyError, "close_time_drift"):
            evaluate(batch)

    def test_unsealed_outcome_and_more_than_eight_events_fail(self) -> None:
        batch = load_json(BATCH)
        batch["hypothesis_outcome_unsealed"] = True
        with self.assertRaisesRegex(NominationPolicyError, "batch_identity"):
            evaluate(batch)
        batch = load_json(BATCH)
        ninth = copy.deepcopy(batch["nomination_events"][-1])
        ninth["nomination_event_id"] = "T21-A6R-SYN-NOM-009"
        batch["nomination_events"].append(ninth)
        with self.assertRaisesRegex(NominationPolicyError, "count_outside"):
            evaluate(batch)

    def test_membership_identity_and_fields_are_stable(self) -> None:
        memberships = evaluate().receipt["membership_events"]
        self.assertEqual(len(memberships), 5)
        self.assertEqual(len({item["member_id"] for item in memberships}), 5)
        required = {
            "member_id",
            "mint",
            "mint_decimals",
            "nomination_event_id",
            "hypothesis_version_id",
            "policy_version",
            "entered_at",
            "exited_at",
            "first_reliable_available_at",
            "reason_codes",
            "evidence_checkpoint",
        }
        for item in memberships:
            self.assertEqual(set(item), required)
            self.assertIsNone(item["exited_at"])

    def test_output_is_compatible_with_frozen_collector_population_contract(
        self,
    ) -> None:
        batch = load_json(BATCH)
        receipt = evaluate().receipt
        evaluations = {
            item["nomination_event_id"]: item for item in receipt["evaluations"]
        }
        members = {
            item["nomination_event_id"]: item
            for item in receipt["membership_events"]
        }
        population = {
            "task_id": "TASK-21",
            "atom_id": "T21-A4_THIN_COLLECTOR_AND_OFFLINE_DRY_RUN_V1",
            "synthetic_only": True,
            "contains_market_data": False,
            "candidates": [
                {
                    "nomination": event,
                    "evaluation_state": evaluations[
                        event["nomination_event_id"]
                    ]["evaluation_state"],
                    "member": members.get(event["nomination_event_id"]),
                }
                for event in batch["nomination_events"]
            ],
        }
        self.assertEqual(len(validate_population(population)), 5)

    def test_receipt_has_zero_real_and_external_actions(self) -> None:
        receipt = evaluate().receipt
        self.assertEqual(
            receipt["real_world_state"],
            {
                "real_candidate_admissions_created": 0,
                "real_candidate_nominations_created": 0,
                "real_collection_authorized": False,
                "real_watchlist_member_count": 0,
            },
        )
        for value in receipt["actual_actions"].values():
            self.assertIn(value, (0, False))
        self.assertFalse(receipt["next_boundary"]["authorized"])
        self.assertIn("NO_REAL_TOKEN_SELECTED", receipt["non_claims"])

    def test_tracked_acceptance_matches_deterministic_receipt(self) -> None:
        path = (
            ROOT
            / "docs/evidence/task21/"
            "real_nomination_policy_offline_acceptance_v1.json"
        )
        self.assertTrue(path.is_file())
        tracked = json.loads(path.read_text(encoding="utf-8"))
        run = evaluate()
        self.assertEqual(tracked["offline_receipt"], run.receipt)
        self.assertEqual(
            tracked["offline_receipt_sha256"],
            hashlib.sha256(run.receipt_bytes).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
