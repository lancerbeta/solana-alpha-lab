from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PACKET_PATH = ROOT / "configs" / "task30_two_slot_live_shakedown_owner_packet_v1.yaml"
SCHEMA_PATH = ROOT / "catalog" / "schemas" / "task30_two_slot_live_shakedown_owner_packet.schema.json"
SCRIPT_PATH = ROOT / "scripts" / "show_task30_two_slot_live_shakedown_owner_packet.py"
REPORT_PATH = ROOT / "docs" / "reports" / "task30" / "two_slot_live_shakedown_owner_packet_readout_v1.md"
TASK_PATH = ROOT / "docs" / "tasks" / "TASK-30-two-slot-live-shakedown-owner-packet.md"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "task30_two_slot_live_shakedown_owner_packet_contract_v1.md"
MODULE_PATH = ROOT / "src" / "solana_alpha_lab" / "task30_two_slot_live_shakedown_owner_packet.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "task30" / "two_slot_live_shakedown_owner_packet_v1.json"
ACCEPTANCE_PATH = ROOT / "docs" / "evidence" / "task30" / "a11b_two_slot_live_shakedown_owner_packet_acceptance_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog" / "assets" / "core.yaml"
DESIGN_PATH = ROOT / "docs" / "superpowers" / "specs" / "2026-08-11-task30-two-slot-live-shakedown-owner-packet-design.md"
PLAN_PATH = ROOT / "docs" / "superpowers" / "plans" / "2026-08-11-task30-two-slot-live-shakedown-owner-packet.md"

ARTIFACT_PATHS = {
    "task": TASK_PATH,
    "contract": CONTRACT_PATH,
    "configuration": PACKET_PATH,
    "schema": SCHEMA_PATH,
    "module": MODULE_PATH,
    "script": SCRIPT_PATH,
    "fixture": FIXTURE_PATH,
    "report": REPORT_PATH,
    "test": Path(__file__),
    "design": DESIGN_PATH,
    "plan": PLAN_PATH,
}

try:
    from solana_alpha_lab.task30_two_slot_live_shakedown_owner_packet import (
        TwoSlotOwnerPacketError,
        render_owner_packet_markdown,
        validate_owner_packet,
    )
except ImportError:
    TwoSlotOwnerPacketError = None
    render_owner_packet_markdown = None
    validate_owner_packet = None


def load_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30TwoSlotLiveShakedownOwnerPacketTests(unittest.TestCase):
    def test_packet_is_only_a_candidate_and_cannot_authorize_external_capture(self) -> None:
        self.assertIsNotNone(
            validate_owner_packet,
            "the fail-closed owner-packet validator must exist",
        )
        packet = load_yaml(PACKET_PATH)
        jsonschema.validate(packet, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        result = validate_owner_packet(packet)
        self.assertEqual(result["status"], "OWNER_APPROVAL_REQUIRED")
        self.assertFalse(result["external_capture_authorized"])
        self.assertEqual(result["max_provider_gets"], 8)
        self.assertEqual(
            result["next_boundary"],
            "EXACT_OWNER_EXTERNAL_READ_AUTHORIZATION",
        )

    def test_readout_states_eight_get_cap_and_no_external_authority(self) -> None:
        self.assertIsNotNone(
            render_owner_packet_markdown,
            "the owner-packet readout renderer must exist",
        )
        markdown = render_owner_packet_markdown(load_yaml(PACKET_PATH))
        self.assertIn("8 публичных GET", markdown)
        self.assertIn("не разрешает внешний запрос", markdown)
        self.assertIn("OWNER_INPUT_REQUIRED", markdown)

    def test_cli_and_checked_in_russian_readout_are_deterministic(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT_PATH), "--format", "markdown"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(REPORT_PATH.read_text(encoding="utf-8"), completed.stdout)

    def test_provider_promotion_or_unsafe_recovery_is_rejected(self) -> None:
        packet = load_yaml(PACKET_PATH)
        unsafe_changes = (
            ("provider_selected", True),
            ("external_capture_authorized", True),
            ("future_request_proposal.retry", True),
            ("shakedown_shape.max_provider_gets", 9),
            ("shakedown_shape.second_slot_requires_prior_receipt", False),
            ("retention.raw_manifest_required_after_every_response", False),
            ("monitoring.stop_on_monitoring_loss", False),
        )
        for dotted_path, value in unsafe_changes:
            with self.subTest(dotted_path=dotted_path):
                changed = copy.deepcopy(packet)
                target = changed
                *parents, leaf = dotted_path.split(".")
                for parent in parents:
                    target = target[parent]
                target[leaf] = value
                with self.assertRaises(TwoSlotOwnerPacketError):
                    validate_owner_packet(changed)

    def test_acceptance_binds_artifacts_and_zero_side_effects(self) -> None:
        self.assertTrue(ACCEPTANCE_PATH.is_file(), "acceptance receipt must exist")
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["validation_status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(receipt["non_claims"]["external_capture_authorized"])
        for name, path in ARTIFACT_PATHS.items():
            self.assertEqual(receipt["artifact_bindings"][name]["path"], str(path.relative_to(ROOT)).replace("\\", "/"))
            self.assertEqual(receipt["artifact_bindings"][name]["sha256"], sha256(path))

    def test_catalog_registers_every_owner_packet_artifact(self) -> None:
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))
        asset_ids = {asset["asset_id"] for asset in catalog["records"]}
        expected = {
            "CONTRACT-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "CONFIG-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "SCHEMA-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "MODULE-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "SCRIPT-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "FIXTURE-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "REPORT-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "TEST-T30-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
            "EVIDENCE-T30-A11B-TWO-SLOT-LIVE-SHAKEDOWN-OWNER-PACKET-001",
        }
        self.assertTrue(expected.issubset(asset_ids))


if __name__ == "__main__":
    unittest.main()
