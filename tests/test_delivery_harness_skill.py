from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/delivery-harness/SKILL.md"
PORTABLE_SKILL = ROOT / "delivery-harness/templates/portable-core/dot-agents/skills/delivery-harness/SKILL.md"
PORTABLE_CURSOR_FINISH = ROOT / "delivery-harness/templates/portable-core/dot-cursor/commands/delivery-finish.md"
PRESSURE = ROOT / "tests/fixtures/delivery_harness/pressure_cases.yaml"


class DeliveryHarnessSkillTests(unittest.TestCase):
    def test_one_canonical_workflow_skill_has_exact_trigger_and_route(self) -> None:
        self.assertTrue(SKILL.is_file())
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        metadata = yaml.safe_load(match.group(1))
        self.assertEqual(metadata["name"], "delivery-harness")
        self.assertIn("starting, resuming, implementing, reviewing or finishing", metadata["description"])
        self.assertIn(
            "CHECK -> CONTEXT -> ENTRY/OUTCOME -> EXECUTE -> RISK-ROUTED REVIEW -> FINISH -> EXACT MERGE GATE -> READ-BACK",
            text,
        )
        self.assertIn("Do not use for orientation phrases", metadata["description"])
        self.assertIn("classifies the turn as `ORIENTATION`", text)
        self.assertIn("probe and fix that on the working path", text)
        self.assertIn("before Catalog, receipts, reviews", text)
        self.assertIn("Do not document a five-second mechanical miss", text)
        self.assertFalse((ROOT / ".cursor/skills").exists())

    def test_pre_commit_runs_staged_task_contract_schema_probe(self) -> None:
        text = (ROOT / "scripts/validate.ps1").read_text(encoding="utf-8")
        self.assertIn("check-task-contracts", text)
        self.assertIn("--staged", text)
        self.assertIn("PRE_COMMIT_TASK_CONTRACT_SCHEMA_INVALID", text)

    def test_skill_preserves_decision_atoms_replan_and_single_effort_advice(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for marker in (
            "DECISION_DELTA",
            "UNCERTAINTY_REMOVED",
            "CAPABILITY_OR_EVIDENCE",
            "STOP",
            "NEXT",
            "SPEC_ROUTE=NONE | PRD_LITE | DESIGN_SPEC | BOTH",
            "REPLAN_TRIGGER",
            "MODEL_EFFORT_RECOMMENDATION",
            "NEXT_MODEL_EFFORT",
        ):
            self.assertIn(marker, text)
        self.assertIn("once before a substantial chain", text)
        self.assertIn("never on microsteps", text)
        self.assertIn("--merge-readiness", text)
        self.assertIn("ready_for_owner_phrase", text)
        self.assertIn("IDENTITY_MODE_MISMATCH", text)
        self.assertIn("Do not widen those prefixes", text)

    def test_portable_skill_does_not_route_control_work_to_live_pr_head(self) -> None:
        text = PORTABLE_SKILL.read_text(encoding="utf-8")
        self.assertIn("Do not widen those prefixes", text)
        self.assertIn("task contract still uses `--contract`", text)
        self.assertNotIn("instead of a product task contract", text)

    def test_skill_routes_cloud_export_and_plugins_fail_closed(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("OWNER_MANAGED_OPTIONAL_EXPORT", text)
        self.assertIn("never request a bundle replacement or smoke", text)
        self.assertIn("CAPABILITY_RADAR_NOW=NONE", text)
        self.assertIn("does not grant install authority", text)

    def test_portable_codex_and_cursor_share_submission_bound_readback(self) -> None:
        codex = PORTABLE_SKILL.read_text(encoding="utf-8")
        cursor = PORTABLE_CURSOR_FINISH.read_text(encoding="utf-8")
        for text in (codex, cursor):
            self.assertIn("self-hashed submission", text)
            self.assertIn("--post-merge-readback", text)
            self.assertIn("--submission-receipt", text)
            self.assertIn("hash-bound receipt", text)

    def test_pressure_cases_have_stable_non_authorizing_outcomes(self) -> None:
        value = yaml.safe_load(PRESSURE.read_text(encoding="utf-8"))
        self.assertEqual(value["execution_status"], "PRESSURE_AGENT_UNAVAILABLE")
        cases = value["cases"]
        self.assertEqual(len(cases), 5)
        self.assertEqual(len({case["case_id"] for case in cases}), 5)
        self.assertEqual(
            {case["expected_code"] for case in cases},
            {
                "EXACT_TASK_CONTRACT_REQUIRED",
                "ROUTINE_IN_ENVELOPE",
                "CAPABILITY_RADAR_NONE",
                "MERGE_IDENTITY_MISMATCH",
                "ACTIVE_ROUTE_FORBIDDEN",
            },
        )
        self.assertTrue(all(case["authority_widened"] is False for case in cases))


if __name__ == "__main__":
    unittest.main()
