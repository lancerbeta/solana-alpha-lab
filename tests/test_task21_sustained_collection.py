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

from solana_alpha_lab.task21_sustained_collection import (  # noqa: E402
    ATOM_ID,
    SustainedCollectionError,
    build_offline_acceptance,
    load_json,
    materialize_create_once,
)

CONFIG = ROOT / "configs/task21_sustained_collection_v1.yaml"
SCENARIO = (
    ROOT / "tests/fixtures/task21/sustained_collection_offline_scenario_v1.json"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(scenario: dict | None = None):
    return build_offline_acceptance(
        repo_root=ROOT,
        config_path=CONFIG,
        scenario_path=SCENARIO,
        scenario_override=scenario,
    )


class Task21SustainedCollectionTests(unittest.TestCase):
    def test_config_freezes_inputs_and_zero_external_authority(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["atom_id"], ATOM_ID)
        self.assertEqual(config["entry_gate"]["verdict"], "START_WITH_PATCH")
        self.assertTrue(config["entry_gate"]["patch"]["real_launch_blocked"])
        self.assertEqual(config["population"]["real_current_member_count"], 0)
        for item in config["frozen_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        authority = config["authority"]
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "real_candidate_admissions",
            "live_collector_executions",
            "forward_raw_or_dataset_writes",
            "backup_executions",
            "restore_executions",
            "provider_credits",
            "cash_spend_usd_cents",
            "dependency_changes",
        ):
            self.assertEqual(authority[field], 0)
        self.assertFalse(authority["scheduler_or_background_process"])

    def test_day30_base_scenario_is_deterministic_and_sufficient(self) -> None:
        first = build()
        second = build()
        self.assertEqual(first.file_bytes, second.file_bytes)
        receipt = first.receipt
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["lifecycle"], "DAY30_REVIEW")
        self.assertEqual(
            receipt["decision"],
            "DATASET_READY_FOR_A7_FREEZE_REQUIRES_SEPARATE_AUTHORITY",
        )
        self.assertTrue(receipt["information_sufficient"])
        coverage = receipt["coverage"]
        self.assertEqual(coverage["active_members"], 5)
        self.assertEqual(coverage["complete_members"], 5)
        self.assertEqual(coverage["complete_panels"], 15)
        self.assertEqual(coverage["complete_quote_pairs"], 60)
        self.assertEqual(coverage["distinct_admission_dates_utc"], 3)
        self.assertEqual(coverage["distinct_admission_weeks_utc"], 3)
        self.assertEqual(receipt["consumption"]["modeled_provider_calls"], 120)

    def test_day29_continues_and_day45_stops_without_autoextension(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["simulated_elapsed_days"] = 29
        receipt = build(scenario).receipt
        self.assertEqual(receipt["lifecycle"], "ACTIVE")
        self.assertEqual(receipt["decision"], "CONTINUE_UNCHANGED_TO_DAY30")
        scenario["simulated_elapsed_days"] = 45
        receipt = build(scenario).receipt
        self.assertEqual(receipt["lifecycle"], "DAY45_STOPPED")
        self.assertEqual(
            receipt["decision"],
            "STOPPED_READY_FOR_A7_REQUIRES_SEPARATE_AUTHORITY",
        )

    def test_day30_insufficient_continues_unchanged_to_day45(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["panel_receipts"] = scenario["panel_receipts"][:-1]
        scenario["gap_events"].append(
            {
                "gap_event_id": "T21-SYN-GAP-001",
                "window_id": "T21-SYN-MEMBER-005-W3",
                "reason": "SYNTHETIC_MISSED_WINDOW",
            }
        )
        receipt = build(scenario).receipt
        self.assertFalse(receipt["information_sufficient"])
        self.assertEqual(receipt["decision"], "CONTINUE_UNCHANGED_TO_DAY45")
        self.assertEqual(receipt["append_only_evidence"]["gap_events_retained"], 1)

    def test_unhealthy_recovery_blocks_sufficiency(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["health"]["backup_age_hours"] = 27
        receipt = build(scenario).receipt
        self.assertFalse(receipt["recovery"]["healthy_for_new_windows"])
        self.assertFalse(receipt["information_sufficient"])
        self.assertEqual(receipt["decision"], "CONTINUE_UNCHANGED_TO_DAY45")

    def test_physical_cap_breach_fails_closed(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["panel_receipts"][0]["provider_calls"] = 9
        with self.assertRaisesRegex(SustainedCollectionError, "per_panel_cap"):
            build(scenario)
        scenario = load_json(SCENARIO)
        scenario["health"]["free_disk_bytes"] = 1
        with self.assertRaisesRegex(
            SustainedCollectionError, "physical_cap_exceeded:free_disk"
        ):
            build(scenario)

    def test_outcome_fields_and_technical_probe_carry_are_rejected(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["pnl"] = 1
        with self.assertRaisesRegex(SustainedCollectionError, "outcome_field"):
            build(scenario)
        scenario = load_json(SCENARIO)
        scenario["technical_probe_automatic_carry_forward"] = True
        with self.assertRaisesRegex(SustainedCollectionError, "scenario_identity"):
            build(scenario)

    def test_exact_duplicate_deduplicates_and_conflict_fails(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["nomination_events"].append(
            copy.deepcopy(scenario["nomination_events"][0])
        )
        receipt = build(scenario).receipt
        self.assertEqual(
            receipt["append_only_evidence"][
                "exact_duplicate_nominations_deduplicated"
            ],
            1,
        )
        scenario["nomination_events"][-1]["reason_codes"] = ["CONFLICT"]
        with self.assertRaisesRegex(SustainedCollectionError, "conflicting_duplicate"):
            build(scenario)

    def test_incident_is_retained_without_outcome_claim(self) -> None:
        scenario = load_json(SCENARIO)
        scenario["incident_events"].append(
            {
                "incident_event_id": "T21-SYN-INCIDENT-001",
                "class": "SYNTHETIC_PROVIDER_UNAVAILABLE",
            }
        )
        receipt = build(scenario).receipt
        self.assertEqual(
            receipt["append_only_evidence"]["incident_events_retained"], 1
        )
        self.assertIn("NO_HYPOTHESIS_RESULT_UNSEALED", receipt["non_claims"])

    def test_exact_restart_is_idempotent_and_conflict_fails(self) -> None:
        run = build()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "acceptance"
            self.assertEqual(
                materialize_create_once(run, output),
                "CREATED_AND_READBACK_VERIFIED",
            )
            before = {
                item.name: (item.stat().st_mtime_ns, item.read_bytes())
                for item in output.iterdir()
            }
            self.assertEqual(
                materialize_create_once(run, output),
                "EXACT_DUPLICATE_RESTART_DEDUPLICATED",
            )
            after = {
                item.name: (item.stat().st_mtime_ns, item.read_bytes())
                for item in output.iterdir()
            }
            self.assertEqual(before, after)
            (output / "manifest.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(
                SustainedCollectionError, "conflicting_or_incomplete_restart"
            ):
                materialize_create_once(run, output)

    def test_real_launch_and_a7_remain_blocked(self) -> None:
        receipt = build().receipt
        self.assertFalse(receipt["real_launch"]["authorized"])
        self.assertEqual(receipt["real_launch"]["real_task21_watchlist_members"], 0)
        self.assertEqual(receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(receipt["actual_actions"]["drive_writes"], 0)
        self.assertFalse(
            receipt["actual_actions"]["scheduler_or_background_process"]
        )
        self.assertIn("NO_A7_FREEZE_OR_CATALOG_TRANSACTION", receipt["non_claims"])

    def test_tracked_acceptance_matches_deterministic_run(self) -> None:
        path = (
            ROOT
            / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json"
        )
        self.assertTrue(path.is_file())
        tracked = json.loads(path.read_text(encoding="utf-8"))
        run = build()
        self.assertEqual(tracked["offline_state_receipt"], run.receipt)
        self.assertEqual(
            tracked["runtime_state_receipt_sha256"],
            hashlib.sha256(run.receipt_bytes).hexdigest(),
        )
        self.assertEqual(
            tracked["runtime_manifest_sha256"],
            hashlib.sha256(run.manifest_bytes).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
