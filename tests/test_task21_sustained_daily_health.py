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

from solana_alpha_lab.task21_sustained_collection import (  # noqa: E402
    build_offline_acceptance,
    load_json as load_sustained_json,
)
from solana_alpha_lab.task21_sustained_daily_health import (  # noqa: E402
    ATOM_ID,
    SustainedDailyHealthError,
    build_daily_health,
    canonical_json_bytes,
    load_json,
    render_daily_health_text,
)

CONFIG = ROOT / "configs/task21_sustained_daily_health_read_model_v1.yaml"
INPUT = ROOT / "tests/fixtures/task21/sustained_daily_health_receipt_v1.json"
SUSTAINED_CONFIG = ROOT / "configs/task21_sustained_collection_v1.yaml"
SUSTAINED_SCENARIO = (
    ROOT / "tests/fixtures/task21/sustained_collection_offline_scenario_v1.json"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(
    daily: dict | None = None,
    state: dict | None = None,
) -> dict:
    return build_daily_health(
        repo_root=ROOT,
        config_path=CONFIG,
        daily_input_path=INPUT,
        daily_override=daily,
        state_receipt_override=state,
    )


def sustained_state(scenario: dict) -> dict:
    return build_offline_acceptance(
        repo_root=ROOT,
        config_path=SUSTAINED_CONFIG,
        scenario_path=SUSTAINED_SCENARIO,
        scenario_override=scenario,
    ).receipt


class Task21SustainedDailyHealthTests(unittest.TestCase):
    def test_config_freezes_inputs_and_zero_external_authority(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["atom_id"], ATOM_ID)
        self.assertEqual(config["truth_boundary"]["role"], "DERIVED_READ_MODEL_ONLY")
        self.assertFalse(
            config["truth_boundary"]["live_monitoring_claim_allowed"]
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
            "live_collection_actions",
            "forward_raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "dependency_changes",
            "wallet_signer_transaction_actions",
        ):
            self.assertEqual(authority[field], 0)
        self.assertFalse(authority["scheduler_or_background_process"])

    def test_base_projection_is_deterministic_and_requests_a7_review(self) -> None:
        first = build()
        second = build()
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["mode"], "OFFLINE_SYNTHETIC")
        self.assertEqual(first["truth_role"], "DERIVED_READ_MODEL_ONLY")
        self.assertEqual(first["coverage"]["complete_panels"], 15)
        self.assertEqual(first["coverage"]["missing_total"], 0)
        self.assertEqual(first["freshness"]["state"], "FRESH")
        self.assertTrue(first["recovery"]["healthy_for_new_windows"])
        self.assertEqual(
            first["owner_decision"]["exact_action_code"],
            "REQUEST_A7_FREEZE_REVIEW",
        )
        self.assertFalse(first["owner_decision"]["grants_runtime_authority"])

    def test_owner_text_is_compact_and_unambiguously_not_live(self) -> None:
        text = render_daily_health_text(build())
        self.assertIn("OFFLINE SYNTHETIC — НЕ LIVE-МОНИТОРИНГ", text)
        self.assertIn("Coverage: 15/15", text)
        self.assertIn("requests=120/192", text)
        self.assertIn("Действие владельца:", text)

    def test_explicit_gap_is_retained_without_backfill(self) -> None:
        scenario = load_sustained_json(SUSTAINED_SCENARIO)
        missed = scenario["panel_receipts"][-1]
        missed["status"] = "MISSED"
        for field in (
            "quote_pairs",
            "provider_calls",
            "provider_credits",
            "response_bytes",
            "stored_bytes",
        ):
            missed[field] = 0
        scenario["gap_events"].append(
            {
                "gap_event_id": "T21-SYN-GAP-001",
                "window_id": "T21-SYN-MEMBER-005-W3",
                "reason": "SYNTHETIC_MISSED_WINDOW",
            }
        )
        state = sustained_state(scenario)
        daily = load_json(INPUT)
        daily["retained_gap_event_ids"] = ["T21-SYN-GAP-001"]
        view = build(daily, state)
        self.assertEqual(view["coverage"]["missed_panels"], 1)
        self.assertEqual(view["coverage"]["unaccounted_due_panels"], 0)
        self.assertEqual(
            view["owner_decision"]["exact_action_code"],
            "REVIEW_GAPS_CONTINUE_NO_BACKFILL",
        )

    def test_unaccounted_due_panel_blocks_new_windows(self) -> None:
        scenario = load_sustained_json(SUSTAINED_SCENARIO)
        scenario["panel_receipts"] = scenario["panel_receipts"][:-1]
        state = sustained_state(scenario)
        view = build(state=state)
        self.assertEqual(view["coverage"]["missed_panels"], 0)
        self.assertEqual(view["coverage"]["unaccounted_due_panels"], 1)
        self.assertEqual(
            view["owner_decision"]["exact_action_code"],
            "RECONCILE_UNACCOUNTED_PANEL",
        )

    def test_missed_panel_requires_exact_gap_identity(self) -> None:
        state = copy.deepcopy(build()["coverage"])
        self.assertEqual(state["missed_panels"], 0)
        daily = load_json(INPUT)
        daily["retained_gap_event_ids"] = ["GAP-WITHOUT-MISSED-PANEL"]
        with self.assertRaisesRegex(
            SustainedDailyHealthError, "missed_panel_gap_evidence_mismatch"
        ):
            build(daily)

    def test_stale_collection_blocks_new_windows(self) -> None:
        daily = load_json(INPUT)
        daily["last_collection_event_at_utc"] = "2026-08-28T09:00:00Z"
        view = build(daily)
        self.assertEqual(view["freshness"]["state"], "STALE")
        self.assertEqual(
            view["owner_decision"]["exact_action_code"],
            "INVESTIGATE_STALE_COLLECTION",
        )

    def test_freshness_and_budget_warning_use_one_health_watch_action(self) -> None:
        source = json.loads(
            (ROOT / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json")
            .read_text(encoding="utf-8")
        )["offline_state_receipt"]
        source["simulated_elapsed_days"] = 29
        source["lifecycle"] = "ACTIVE"
        source["decision"] = "CONTINUE_UNCHANGED_TO_DAY30"
        daily = load_json(INPUT)
        daily["collection_day"] = 29
        daily["last_collection_event_at_utc"] = "2026-08-28T11:00:00Z"
        view = build(daily, source)
        self.assertEqual(view["freshness"]["state"], "WARNING")
        self.assertEqual(
            view["owner_decision"]["exact_action_code"], "WATCH_HEALTH_CONTINUE"
        )

        source["consumption"]["modeled_provider_calls"] = 160
        daily = load_json(INPUT)
        daily["collection_day"] = 29
        view = build(daily, source)
        self.assertEqual(
            view["quota_and_storage"]["provider_requests"]["state"], "WARNING"
        )
        self.assertEqual(
            view["owner_decision"]["exact_action_code"], "WATCH_HEALTH_CONTINUE"
        )

    def test_future_collection_timestamp_fails_closed(self) -> None:
        daily = load_json(INPUT)
        daily["last_collection_event_at_utc"] = "2026-08-29T12:00:01Z"
        with self.assertRaisesRegex(
            SustainedDailyHealthError, "collection_event_from_future"
        ):
            build(daily)

    def test_unhealthy_recovery_has_highest_priority(self) -> None:
        state = json.loads(canonical_json_bytes(build()).decode("utf-8"))
        self.assertEqual(state["owner_decision"]["operating_state"], "REVIEW_REQUIRED")
        source = json.loads(
            (ROOT / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json")
            .read_text(encoding="utf-8")
        )["offline_state_receipt"]
        source["recovery"]["backup_age_hours"] = 27
        source["recovery"]["healthy_for_new_windows"] = False
        view = build(state=source)
        self.assertEqual(view["owner_decision"]["operating_state"], "SAFE_STOP")
        self.assertIn(
            "RECOVERY_UNHEALTHY", view["owner_decision"]["reason_codes"]
        )

    def test_cap_breach_is_visible_and_safe_stops(self) -> None:
        source = json.loads(
            (ROOT / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json")
            .read_text(encoding="utf-8")
        )["offline_state_receipt"]
        source["consumption"]["modeled_provider_calls"] = 193
        view = build(state=source)
        self.assertEqual(
            view["quota_and_storage"]["provider_requests"]["state"], "BREACH"
        )
        self.assertEqual(view["owner_decision"]["operating_state"], "SAFE_STOP")

    def test_open_incident_blocks_new_windows(self) -> None:
        source = json.loads(
            (ROOT / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json")
            .read_text(encoding="utf-8")
        )["offline_state_receipt"]
        source["append_only_evidence"]["incident_events_retained"] = 1
        daily = load_json(INPUT)
        daily["retained_incident_event_ids"] = ["T21-SYN-INCIDENT-001"]
        view = build(daily, source)
        self.assertEqual(
            view["owner_decision"]["exact_action_code"], "RESOLVE_OPEN_INCIDENT"
        )

    def test_outcome_field_and_nonzero_synthetic_action_fail_closed(self) -> None:
        source = json.loads(
            (ROOT / "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json")
            .read_text(encoding="utf-8")
        )["offline_state_receipt"]
        source["pnl"] = 1
        with self.assertRaisesRegex(SustainedDailyHealthError, "outcome_field"):
            build(state=source)
        source.pop("pnl")
        source["actual_actions"]["network_calls"] = 1
        with self.assertRaisesRegex(
            SustainedDailyHealthError, "synthetic_source_has_external_action"
        ):
            build(state=source)

    def test_tracked_acceptance_matches_exact_projection(self) -> None:
        path = (
            ROOT
            / "docs/evidence/task21/sustained_daily_health_offline_acceptance_v1.json"
        )
        self.assertTrue(path.is_file())
        tracked = json.loads(path.read_text(encoding="utf-8"))
        view = build()
        self.assertEqual(tracked["projection"], view)
        self.assertEqual(
            tracked["projection_sha256"],
            hashlib.sha256(canonical_json_bytes(view)).hexdigest(),
        )
        artifact_paths = {
            "config": CONFIG,
            "contract": ROOT
            / "docs/contracts/task21_sustained_daily_health_read_model_contract_v1.md",
            "fixture": INPUT,
            "module": ROOT
            / "src/solana_alpha_lab/task21_sustained_daily_health.py",
            "script": ROOT / "scripts/show_task21_sustained_daily_health.py",
            "tests": Path(__file__),
        }
        for name, artifact_path in artifact_paths.items():
            self.assertEqual(tracked["artifact_sha256"][name], digest(artifact_path))


if __name__ == "__main__":
    unittest.main()
