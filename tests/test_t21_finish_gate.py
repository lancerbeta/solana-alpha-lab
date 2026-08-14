from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.t21_finish_gate import (  # noqa: E402
    build_t21_finish_gate_pulse,
    render_t21_finish_gate_text,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class T21FinishGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pulse = build_t21_finish_gate_pulse(
            repository_root=ROOT,
            as_of=datetime(2026, 8, 1, 18, 15, tzinfo=timezone.utc),
            free_disk_bytes=1_000_000_000,
        )
        cls.config = yaml.safe_load(
            (ROOT / "configs/t21_finish_gate_read_model_v1.yaml").read_bytes()
        )

    def test_a8_delivery_is_exact_and_task22_remains_closed(self) -> None:
        self.assertEqual(self.config["schema_version"], "1.1")
        self.assertEqual(self.config["read_model_version"], "1.1")
        self.assertEqual(self.config["policy_reconciled_on"], "2026-08-14")
        self.assertEqual(self.pulse["policy_reconciled_on"], "2026-08-14")
        self.assertEqual(
            self.pulse["historical_delivery_as_of"], "2026-08-01T18:02:15Z"
        )
        delivery = self.pulse["repository_delivery"]
        self.assertEqual(delivery, self.config["required_repository_delivery"] | {
            "status": "MERGED_MAIN_CI_PASS",
            "resolved_at": "2026-08-01T18:02:15Z",
            "task22_started": False,
            "next_boundary": "TERMINAL_NO_OWNER_ACTION",
        })
        self.assertFalse(self.pulse["task21_forward_state"]["task22_started"])
        self.assertEqual(self.pulse["active_time_gates"], [])

    def test_cloud_export_is_terminal_optional_and_never_an_owner_action(self) -> None:
        self.assertEqual(self.pulse["attention"], [])
        self.assertEqual(
            self.pulse["task21_forward_state"]["state"],
            "A8_MERGED_TERMINAL_OWNER_EXPORT_OPTIONAL",
        )
        self.assertEqual(
            self.pulse["recovery_and_storage"]["analysis_promotion_blocker"],
            "NONE_FROM_TASK21_CLOUD_EXPORT",
        )
        self.assertEqual(
            self.pulse["finish_gate"]["source_activation"],
            "OWNER_MANAGED_OPTIONAL_EXPORT",
        )

    def test_a7_frozen_artifacts_remain_byte_identical(self) -> None:
        receipt = self.pulse["a7_acceptance"]
        self.assertEqual(receipt["status"], "PASS")
        frozen = __import__("json").loads(
            (ROOT / "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json").read_bytes()
        )["frozen_artifacts"]
        for binding in frozen:
            self.assertEqual(_sha256(ROOT / binding["path"]), binding["sha256"])

    def test_finish_review_authority_and_text_are_bounded(self) -> None:
        self.assertEqual(
            self.pulse["finish_gate"]["factory_fit"],
            "PASS_WITH_DURABLE_FOLLOWUPS",
        )
        self.assertTrue(
            all(value in (0, False) for value in self.pulse["side_effects"].values())
        )
        text = render_t21_finish_gate_text(self.pulse)
        self.assertIn("A8 смерджен", text)
        self.assertNotIn("SMOKE=PASS", text)
        self.assertNotIn("активировать replacement bundle", text)
        self.assertIn("не требует действий владельца", text)


if __name__ == "__main__":
    unittest.main()
