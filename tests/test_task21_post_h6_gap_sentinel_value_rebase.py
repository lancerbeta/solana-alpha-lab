from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_owner_pulse import build_owner_pulse


REBASE_PATH = (
    ROOT / "configs" / "task21_post_h6_gap_sentinel_value_rebase_v1.yaml"
)
H24_CONFIG_PATH = ROOT / "configs" / "task21_h24_foreground_capture_v1.yaml"
MARKER_PATH = ROOT / "control" / "active_time_gates.json"
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "post_h6_gap_sentinel_value_rebase_acceptance_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21PostH6GapSentinelValueRebaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rebase = yaml.safe_load(REBASE_PATH.read_text(encoding="utf-8"))
        cls.h24 = yaml.safe_load(H24_CONFIG_PATH.read_text(encoding="utf-8"))
        cls.marker = json.loads(MARKER_PATH.read_text(encoding="utf-8"))

    def test_protected_history_and_historical_core_are_exact(self) -> None:
        history = self.rebase["protected_history"]
        self.assertFalse(history["historical_receipts_rewritten"])
        self.assertFalse(history["h0_h1_h6_runtime_evidence_rewritten"])
        original = history["original_admission_reconciliation"]
        self.assertEqual(
            original["sha256"],
            "51c5f404f54f587a1be4aa405f329266ee11ec971a96908c35bbd9d7f7f21c66",
        )
        historical_core = history["historical_future_core"]
        self.assertEqual(
            _sha256(ROOT / historical_core["path"]), historical_core["sha256"]
        )
        old_acceptance = history["superseded_h24_acceptance"]
        self.assertEqual(
            _sha256(ROOT / old_acceptance["path"]), old_acceptance["sha256"]
        )

    def test_post_gap_budget_is_exact_and_bounded(self) -> None:
        budget = self.rebase["post_gap_budget"]
        expected = (
            budget["requests_used_before_rebase"]
            + budget["future_base_quote_calls_max"]
            + budget["h24_sentinel_quote_calls_max"]
        )
        self.assertEqual(expected, 180)
        self.assertEqual(budget["outer_external_requests_max"], 192)
        self.assertEqual(budget["remaining_headroom"], 12)
        self.assertEqual(budget["mandatory_h72_h168_quote_calls"], 0)
        self.assertFalse(budget["minimum_complete_members_reduced"])
        self.assertFalse(budget["minimum_distinct_tranches_reduced"])

    def test_h24_is_one_minimum_age_sentinel_without_expiry(self) -> None:
        gate = self.h24["time_gate"]
        population = self.h24["population"]
        h24 = self.h24["h24"]
        self.assertEqual(gate["eligibility_mode"], "MINIMUM_AGE_NO_EXPIRY")
        self.assertIsNone(gate["latest_at"])
        self.assertEqual(population["source_members"], 3)
        self.assertEqual(population["sentinel_members"], 1)
        self.assertEqual(len(population["member_ids"]), 1)
        self.assertFalse(population["outcome_or_route_selection_allowed"])
        self.assertEqual(h24["panels_max"], 1)
        self.assertEqual(h24["provider_calls_total_max"], 8)

    def test_h72_h168_are_trigger_only_without_active_gate(self) -> None:
        boundary = self.h24["next_boundary"]
        self.assertEqual(boundary["status"], "DEFERRED_TRIGGER_ONLY")
        self.assertEqual(boundary["mandatory_horizons"], [])
        self.assertFalse(boundary["active_time_gate_created"])
        active_ids = {
            gate["gate_id"]
            for gate in self.marker["gates"]
            if gate["status"] == "ACTIVE_WAITING"
        }
        self.assertEqual(active_ids, set())
        self.assertFalse(any("H72" in gate_id or "H168" in gate_id for gate_id in active_ids))

    def test_active_marker_uses_not_before_without_expiry_or_authority(self) -> None:
        gate = self.marker["gates"][3]
        self.assertEqual(
            gate["time_semantics"],
            "MINIMUM_AGE_NO_EXPIRY_RECORD_ACTUAL_ELAPSED_SECONDS",
        )
        self.assertIsNone(gate["latest_at"])
        self.assertEqual(gate["capture_prep"]["sentinel_members_exact"], 1)
        self.assertEqual(
            gate["capture_prep"]["provider_api_rpc_wss_calls_max"], 8
        )
        self.assertTrue(
            all(value == 0 for value in gate["authority_granted_by_marker"].values())
        )

    def test_owner_pulse_retains_resolved_h24_without_future_activation(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=datetime(2026, 8, 2, 8, 5, tzinfo=timezone.utc),
            free_disk_bytes=9_000_000_000,
        )
        gate = pulse["active_time_gates"][0]
        self.assertEqual(gate["state"], "RESOLVED_WITH_EVIDENCE")
        schedule = pulse["observation_schedule"]
        self.assertEqual(schedule["status"], "H24_CAPTURED_H72_H168_TRIGGER_ONLY")
        self.assertFalse(schedule["narrow_expiry_window_used"])
        self.assertEqual(schedule["windows"][1]["state"], "DEFERRED_TRIGGER_ONLY")
        self.assertEqual(schedule["windows"][2]["state"], "DEFERRED_TRIGGER_ONLY")

    def test_narrow_windows_require_causal_justification(self) -> None:
        rule = self.rebase["time_gate_design_rule"]
        self.assertEqual(rule["default"], "NOT_BEFORE_PLUS_ACTUAL_ELAPSED_TIME")
        self.assertEqual(len(rule["narrow_window_allowed_only_when"]), 3)
        self.assertEqual(rule["operator_lateness_without_causal_window"], "NOT_A_DATA_GAP")

    def test_local_only_authority_and_catalog_hold(self) -> None:
        authority = self.rebase["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        for key, value in authority.items():
            if key in {"class", "source", "gate_phrase"}:
                continue
            if isinstance(value, bool):
                self.assertFalse(value, key)
            else:
                self.assertEqual(value, 0, key)
        self.assertFalse(self.rebase["catalog"]["version_or_count_advanced"])

    def test_acceptance_binds_exact_candidate(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha256(ACCEPTANCE_PATH),
            "755a00c3642a8a6f5a3d9bdb0dd8db486aafa6e7ea41d5261e1d3893c154a34f",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "POST_H6_GAP_SENTINEL_VALUE_REBASE_ACCEPTED_FORWARD_ONLY",
        )
        self.assertEqual(receipt["targeted_validation"], "9_OF_9_PASS")
        forward_evolved = {
            "control/active_time_gates.json",
            "src/solana_alpha_lab/task21_owner_pulse.py",
            "tests/test_task21_h24_foreground_capture.py",
            "tests/test_task21_owner_pulse.py",
            "tests/test_task21_post_h6_gap_sentinel_value_rebase.py",
        }
        for artifact in receipt["artifacts"]:
            if artifact["path"] in forward_evolved:
                continue
            self.assertEqual(
                _sha256(ROOT / artifact["path"]), artifact["sha256"], artifact["path"]
            )
        for value in receipt["actual_actions"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
