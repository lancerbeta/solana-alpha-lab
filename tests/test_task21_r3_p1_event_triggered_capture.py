from __future__ import annotations

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

from solana_alpha_lab.task21_event_triggered_followup_capture import (
    R3_P1_ATOM_ID,
    Task21FollowupAuthorityRequired,
    Task21FollowupExecutionGate,
    validate_followup_config,
)


CONFIG = ROOT / "configs/task21_r3_p1_event_triggered_capture_v1.yaml"
ACCEPTANCE = ROOT / "docs/evidence/task21/r3_p1_event_triggered_capture_offline_acceptance_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21R3P1CaptureTests(unittest.TestCase):
    def test_frozen_binding_is_exact_two_members_and_sixteen_calls(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["atom_id"], R3_P1_ATOM_ID)
        self.assertEqual(config["panel"]["batch_id"], "T21-R3")
        self.assertEqual(config["panel"]["population_members_exact"], 2)
        self.assertEqual(config["capture"]["provider_calls_total_max"], 16)
        self.assertEqual(config["authority"]["jupiter_calls_max"], 16)
        self.assertEqual(config["budget"]["used_before_p1"]["quote_requests"], 144)

    def test_authority_gate_accepts_only_supported_exact_atom(self) -> None:
        self.assertEqual(Task21FollowupExecutionGate(R3_P1_ATOM_ID).authority_phrase, R3_P1_ATOM_ID)
        with self.assertRaises(Task21FollowupAuthorityRequired):
            Task21FollowupExecutionGate("T21-A6S_R3_P2_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1")

    def test_live_config_validates_when_ignored_inputs_are_present(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        admission = ROOT / config["protected_inputs"][2]["path"]
        if not admission.is_file():
            self.skipTest("ignored R3 runtime evidence is not present")
        validate_followup_config(config, ROOT)

    def test_offline_acceptance_binds_exact_artifacts(self) -> None:
        if not ACCEPTANCE.is_file():
            self.skipTest("offline acceptance is generated after implementation")
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["actual_actions"]["provider_api_rpc_wss_calls"], 0)
        for item in receipt["artifacts"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])


if __name__ == "__main__":
    unittest.main()
