from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/hypothesis_forge_independent_critic_v1.yaml"
TASK_CONTRACT_PATH = ROOT / "docs/tasks/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1.md"
OPERATOR_PATH = ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
CRITIC_SCHEMA_PATH = ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
HANDOFF_SCHEMA_PATH = ROOT / "catalog/schemas/hypothesis_forge_synthesis_handoff_v1.schema.json"
FORGE_SKILL_PATH = ROOT / ".agents/skills/hypothesis-forge/SKILL.md"
CRITIC_SKILL_PATH = ROOT / ".agents/skills/independent-hypothesis-critic/SKILL.md"
FORGE_COMMAND_PATH = ROOT / ".cursor/commands/hypothesis-forge.md"
CRITIC_COMMAND_PATH = ROOT / ".cursor/commands/independent-hypothesis-critic.md"
CRITIC_PACKET_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/critic_input_packet_valid_v1.json"
HANDOFF_PENDING_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/synthesis_handoff_pending_critic_v1.json"
HANDOFF_COMPLETE_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/synthesis_handoff_complete_v1.json"
HANDOFF_PASS_FAST_LANE_FIXTURE = (
    ROOT / "tests/fixtures/hypothesis_forge/synthesis_handoff_complete_pass_fast_lane_v1.json"
)

POST_CLASSIFICATION_TERMINALS = {
    "PASS_FAST_LANE_READY",
    "PASS_CHANGE_LANE_REQUIRED",
    "PASS_DATA_OPTION_REQUIRED",
}

BARE_LANE_NAMES = {"FAST_LANE", "CHANGE_LANE", "DATA_OPTION", "PROMOTION_LANE"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema_errors(document: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    return [error.message for error in Draft202012Validator(schema).iter_errors(document)]


class HypothesisForgeIndependentCriticV1Tests(unittest.TestCase):
    def test_config_binds_manual_forge_and_auto_critic(self) -> None:
        config = load_yaml(CONFIG_PATH)
        self.assertEqual(config["generator_mode"], "MANUAL_FALLBACK_UNTIL_GENERATOR")
        self.assertEqual(config["forge_invocation"]["mode"], "EXPLICIT_SLASH_ONLY")
        self.assertEqual(config["critic_launch"]["mode"], "AUTO_AFTER_SYNTHESIS")
        self.assertEqual(config["critic_launch"]["context_isolation"], "NEW_CONTEXT_REQUIRED")
        self.assertEqual(config["authority"]["git_mutation"], 0)
        self.assertEqual(config["authority"]["experiment_execution"], 0)
        self.assertEqual(config["authority"]["provider_api_rpc_wss_calls"], 0)

    def test_critic_input_packet_fixture_validates(self) -> None:
        packet = load_json(CRITIC_PACKET_FIXTURE)
        self.assertEqual(packet["packet_schema"], "smial.hypothesis-critic-input")
        self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.0")
        self.assertEqual(packet["packet_version"], "1.0")
        self.assertNotIn("session_id", packet)
        self.assertEqual(schema_errors(packet, CRITIC_SCHEMA_PATH), [])

    def test_v11_packet_rejects_missing_session_id(self) -> None:
        packet = load_json(CRITIC_PACKET_FIXTURE)
        packet["packet_version"] = "1.1"
        packet["generator_prompt_version"] = "HFIC-V1.1"
        self.assertNotIn("session_id", packet)
        self.assertNotEqual(schema_errors(packet, CRITIC_SCHEMA_PATH), [])
        packet["session_id"] = "HFIC-SESS-TESTBIND0001"
        self.assertEqual(schema_errors(packet, CRITIC_SCHEMA_PATH), [])
        packet["session_id"] = "HFIC-UNBOUND-548FED55D34C"
        self.assertNotEqual(schema_errors(packet, CRITIC_SCHEMA_PATH), [])

    def test_critic_packet_rejects_wrong_prompt_version(self) -> None:
        invalid = load_json(CRITIC_PACKET_FIXTURE)
        invalid["generator_prompt_version"] = "HFIC-V0.9"
        self.assertNotEqual(schema_errors(invalid, CRITIC_SCHEMA_PATH), [])

    def test_provisional_lane_never_assigns_bare_runtime_lane(self) -> None:
        schema = load_json(CRITIC_SCHEMA_PATH)
        lane_enum = schema["properties"]["provisional_lane"]["properties"]["value"]["enum"]
        self.assertTrue(BARE_LANE_NAMES.isdisjoint(set(lane_enum)))
        self.assertIn("PROMOTION_LANE_CANDIDATE", lane_enum)

    def test_handoff_pending_requires_packet_hash_and_no_critic(self) -> None:
        handoff = load_json(HANDOFF_PENDING_FIXTURE)
        self.assertEqual(handoff["synthesis_status"], "PENDING_CRITIC")
        self.assertIsNone(handoff["critic_terminal"])
        self.assertFalse(handoff["critic_report_present"])
        self.assertFalse(handoff["classifier_receipt_present"])
        self.assertEqual(schema_errors(handoff, HANDOFF_SCHEMA_PATH), [])

    def test_handoff_complete_kill_requires_no_classifier_receipt(self) -> None:
        handoff = load_json(HANDOFF_COMPLETE_FIXTURE)
        self.assertEqual(handoff["synthesis_status"], "SYNTHESIS_COMPLETE")
        self.assertNotIn(handoff["critic_terminal"], POST_CLASSIFICATION_TERMINALS)
        self.assertFalse(handoff["classifier_receipt_present"])
        self.assertIsNone(handoff["lane_classifier_terminal"])
        self.assertEqual(schema_errors(handoff, HANDOFF_SCHEMA_PATH), [])

    def test_handoff_complete_pass_fast_lane_requires_classifier_receipt(self) -> None:
        handoff = load_json(HANDOFF_PASS_FAST_LANE_FIXTURE)
        self.assertIn(handoff["critic_terminal"], POST_CLASSIFICATION_TERMINALS)
        self.assertTrue(handoff["classifier_receipt_present"])
        self.assertIsNotNone(handoff["lane_classifier_terminal"])
        self.assertEqual(schema_errors(handoff, HANDOFF_SCHEMA_PATH), [])

    def test_post_classification_without_classifier_receipt_rejected(self) -> None:
        invalid = load_json(HANDOFF_PASS_FAST_LANE_FIXTURE)
        invalid["classifier_receipt_present"] = False
        invalid["lane_classifier_terminal"] = None
        self.assertNotEqual(schema_errors(invalid, HANDOFF_SCHEMA_PATH), [])

    def test_synthesis_complete_without_critic_terminal_rejected(self) -> None:
        invalid = load_json(HANDOFF_COMPLETE_FIXTURE)
        invalid["critic_terminal"] = None
        self.assertNotEqual(schema_errors(invalid, HANDOFF_SCHEMA_PATH), [])

    def test_synthesis_complete_without_critic_report_rejected(self) -> None:
        invalid = load_json(HANDOFF_COMPLETE_FIXTURE)
        invalid["critic_report_present"] = False
        self.assertNotEqual(schema_errors(invalid, HANDOFF_SCHEMA_PATH), [])

    def test_forge_not_ready_rejects_complete_artifacts(self) -> None:
        invalid = {
            "schema": "smial.hypothesis-forge-synthesis-handoff",
            "schema_version": "1.0",
            "contract_id": "HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1",
            "prompt_version": "HFIC-V1.0",
            "generator_mode": "MANUAL_FALLBACK_UNTIL_GENERATOR",
            "forge_invocation": "EXPLICIT_SLASH_ONLY",
            "critic_launch": "AUTO_AFTER_SYNTHESIS",
            "synthesis_status": "FORGE_NOT_READY",
            "forge_report_present": True,
            "critic_input_packet_present": True,
            "critic_terminal": None,
            "critic_report_present": False,
            "classifier_receipt_present": False,
            "lane_classifier_terminal": None,
            "critic_context_isolation": "NEW_CONTEXT_REQUIRED",
            "authority": {
                "git_mutation": 0,
                "experiment_execution": 0,
                "provider_api_rpc_wss_calls": 0,
            },
        }
        self.assertNotEqual(schema_errors(invalid, HANDOFF_SCHEMA_PATH), [])

    def test_pending_critic_with_terminal_rejected(self) -> None:
        invalid = load_json(HANDOFF_PENDING_FIXTURE)
        invalid["critic_terminal"] = "KILL_MECHANISM"
        self.assertNotEqual(schema_errors(invalid, HANDOFF_SCHEMA_PATH), [])

    def test_forge_skill_mandates_auto_handoff(self) -> None:
        text = FORGE_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("MANUAL_FALLBACK_UNTIL_GENERATOR", text)
        self.assertIn("explicitly invokes", text)
        self.assertRegex(text, re.compile(r"auto.?handoff", re.IGNORECASE))
        self.assertIn("PENDING_CRITIC", text)
        self.assertIn("SYNTHESIS_COMPLETE", text)
        self.assertIn("classifier_receipt_present", text)
        self.assertIn("independent-hypothesis-critic", text)

    def test_forge_command_requires_auto_critic(self) -> None:
        text = FORGE_COMMAND_PATH.read_text(encoding="utf-8")
        self.assertIn("/hypothesis-forge", text)
        self.assertRegex(text, re.compile(r"auto.?launch", re.IGNORECASE))
        self.assertIn("incomplete", text.lower())

    def test_critic_skill_requires_pass_to_classification_before_post_lane(self) -> None:
        text = CRITIC_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("CRITIC_INPUT_PACKET", text)
        self.assertIn("PASS_TO_CLASSIFICATION", text)
        self.assertIn("classify_lane()", text)
        self.assertIn("lane_classifier_terminal", text)
        self.assertIn("copied/bound", text.casefold())
        self.assertIn("never generated", text.casefold())
        self.assertIn("HFIC-UNBOUND", text)
        self.assertIn("INCOMPLETE_CRITIC_INPUT_PACKET", text)
        self.assertIn("CRITIC_SESSION_MISMATCH", text)
        self.assertRegex(text, re.compile(r"Do not emit `PASS_FAST_LANE_READY`"))

    def test_operator_pack_contains_hfic_prompts(self) -> None:
        text = OPERATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("HFIC-V1.0", text)
        self.assertIn("/hypothesis-forge", text)
        self.assertIn("auto-handoff", text.casefold())
        self.assertIn("manual fallback", text.casefold())
        self.assertIn("BEGIN PROMPT A", text)
        self.assertIn("END PROMPT A", text)
        self.assertIn("BEGIN PROMPT B", text)
        self.assertIn("END PROMPT B", text)
        self.assertIn("CRITIC_INPUT_PACKET", text)

    def test_task_contract_write_set_covers_surface(self) -> None:
        front_matter = yaml.safe_load(TASK_CONTRACT_PATH.read_text(encoding="utf-8").split("---", 2)[1])
        write_set = set(front_matter["managed_write_set"])
        required = {
            str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(FORGE_SKILL_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(CRITIC_SKILL_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(FORGE_COMMAND_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(CRITIC_COMMAND_PATH.relative_to(ROOT)).replace("\\", "/"),
        }
        self.assertTrue(required.issubset(write_set))
        self.assertNotIn("catalog/assets/core.yaml", write_set)

    def test_packet_sha256_matches_pending_handoff_fixture(self) -> None:
        packet_bytes = CRITIC_PACKET_FIXTURE.read_bytes()
        expected = hashlib.sha256(packet_bytes).hexdigest()
        pending = load_json(HANDOFF_PENDING_FIXTURE)
        self.assertEqual(pending["critic_input_packet_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
