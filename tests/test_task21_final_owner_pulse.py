from __future__ import annotations

import unittest
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_final_owner_pulse import (
    build_final_owner_pulse,
    render_final_owner_pulse_text,
)


class Task21FinalOwnerPulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pulse = build_final_owner_pulse(
            repository_root=ROOT,
            as_of=datetime(2026, 8, 1, 17, 0, tzinfo=timezone.utc),
            free_disk_bytes=1_000_000_000,
        )
        cls.config = yaml.safe_load(
            (ROOT / "configs/task21_final_owner_pulse_v1.yaml").read_bytes()
        )

    def test_final_truth_replaces_stale_pre_h24_projection(self) -> None:
        state = self.pulse["task21_forward_state"]
        self.assertEqual(state["state"], "A7_ACCEPTED_LOCAL_CANDIDATE_PENDING_A8")
        self.assertEqual(state["real_nominations"], 8)
        self.assertEqual(state["real_admissions"], 8)
        self.assertEqual(state["complete_members"], 5)
        self.assertEqual(state["complete_member_clusters"], 2)
        self.assertEqual(state["panels_captured"], 22)
        self.assertEqual(state["quote_pairs"], 88)
        self.assertEqual(state["quote_attempts"], 176)
        self.assertEqual(state["local_dataset_bytes"], 1263895)

    def test_recovery_and_next_action_are_owner_readable(self) -> None:
        self.assertEqual(self.pulse["active_time_gates"], [])
        self.assertEqual(
            self.pulse["attention"],
            [
                {
                    "severity": "INFO",
                    "code": "A7_ACCEPTED_PENDING_REPOSITORY_DELIVERY",
                    "action": "AUTHORIZE_T21_A8_REPOSITORY_DELIVERY",
                }
            ],
        )
        recovery = self.pulse["recovery_and_storage"]
        self.assertEqual(recovery["health_state"], "FINAL_DATASET_REMOTE_RECOVERY_PROVEN")
        self.assertTrue(recovery["exact_remote_readback"])
        self.assertTrue(recovery["isolated_full_restore"])
        self.assertFalse(recovery["dataset_analysis_promotion_allowed"])

    def test_cost_authority_and_side_effects_are_exact(self) -> None:
        usage = self.pulse["cost_and_authority"]
        self.assertEqual(usage["collection_external_requests_used"], 184)
        self.assertEqual(usage["separate_shakedown_requests"], 8)
        self.assertEqual(usage["task21_provider_api_rpc_wss_calls_total"], 192)
        self.assertEqual(usage["drive_reads_historical"], 34)
        self.assertEqual(usage["drive_writes_historical"], 6)
        self.assertFalse(usage["external_authority_granted_by_pulse"])
        side_effects = self.pulse["side_effects"]
        self.assertTrue(all(value in (0, False) for value in side_effects.values()))
        self.assertTrue(all(value in (0, False) for value in self.config["authority"].values() if not isinstance(value, str)))

    def test_text_is_compact_and_honest(self) -> None:
        text = render_final_owner_pulse_text(self.pulse)
        self.assertIn("A7 принят локально", text)
        self.assertIn("5 полных участников", text)
        self.assertIn("не alpha", text)
        self.assertIn("TASK-22 не запущен", text)


if __name__ == "__main__":
    unittest.main()
