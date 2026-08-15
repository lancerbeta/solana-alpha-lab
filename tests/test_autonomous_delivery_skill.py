from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents/skills/autonomous-delivery"
SKILL = SKILL_DIR / "SKILL.md"
HARNESS_SKILL = ROOT / ".agents/skills/delivery-harness/SKILL.md"
CONTRACT_REF = SKILL_DIR / "references/product-system-contract.md"
ROADMAP_REF = SKILL_DIR / "references/roadmap-challenge.md"
AGENTS = ROOT / "AGENTS.md"
CTRL = ROOT / "docs/tasks/CTRL-AUTONOMOUS-DELIVERY-SKILL-V1.md"
TASK_SCHEMA = ROOT / "catalog/schemas/delivery_harness_task_contract.schema.json"
FORBIDDEN_TOUCH = (
    "scripts/validate_ci.py",
    "tests/test_ci.py",
    "delivery-harness/policies/solana-alpha-lab.md",
    "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
)
VERDICTS = (
    "CONTINUE",
    "REPLAN",
    "SELECT",
    "STRATEGY",
    "BOTTLENECK",
    "RESEARCH",
    "OWNER_DECISION",
)


def frontmatter(path: Path) -> dict[object, object]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if match is None:
        raise AssertionError(f"frontmatter missing: {path}")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise AssertionError(f"frontmatter mapping required: {path}")
    return value


class AutonomousDeliverySkillTests(unittest.TestCase):
    def test_skill_identity_allows_automatic_and_slash_invoke(self) -> None:
        self.assertEqual(SKILL_DIR.name, "autonomous-delivery")
        self.assertTrue(SKILL.is_file())
        metadata = frontmatter(SKILL)
        self.assertEqual(metadata["name"], "autonomous-delivery")
        description = metadata["description"]
        self.assertIsInstance(description, str)
        self.assertIn(
            "continue autonomous project delivery or choose the next best project step",
            description,
        )
        self.assertNotIn("disable-model-invocation", metadata)
        self.assertNotIn("paths", metadata)
        self.assertFalse((ROOT / ".cursor/skills/autonomous-delivery").exists())

    def test_controller_adopts_harness_and_keeps_one_atom_routing(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn(".agents/skills/delivery-harness/SKILL.md", text)
        self.assertIn("not a second control plane", text)
        self.assertIn("Never take the next `TASK-XX` by number", text)
        self.assertIn("No owner menu", text)
        self.assertIn("references/product-system-contract.md", text)
        self.assertIn("references/roadmap-challenge.md", text)
        self.assertIn("KEEP | PATCH | REORDER | REBASE", text)
        self.assertIn("MERGE_READY=", text)
        for verdict in VERDICTS:
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, text)
        self.assertTrue(HARNESS_SKILL.is_file())
        self.assertLess(len(text), len(HARNESS_SKILL.read_text(encoding="utf-8")) * 4)

    def test_phase_references_map_existing_contract_and_revisable_roadmap(self) -> None:
        self.assertTrue(CONTRACT_REF.is_file())
        self.assertTrue(ROADMAP_REF.is_file())
        contract = CONTRACT_REF.read_text(encoding="utf-8")
        roadmap = ROADMAP_REF.read_text(encoding="utf-8")
        self.assertIn("catalog/schemas/delivery_harness_task_contract.schema.json", contract)
        self.assertIn("not a second standard", contract)
        self.assertIn("prd_lite:", contract)
        self.assertIn("ssd_lite:", contract)
        self.assertIn("managed_write_set", contract)
        self.assertIn("KEEP", roadmap)
        self.assertIn("PATCH", roadmap)
        self.assertIn("REORDER", roadmap)
        self.assertIn("REBASE", roadmap)
        self.assertIn("Silent divergence is forbidden", roadmap)
        self.assertIn("do not REBASE because", roadmap)

    def test_agents_pointer_is_tiny_and_non_authorizing(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("## AUTONOMOUS_DELIVERY_CONTINUE", text)
        self.assertIn(".agents/skills/autonomous-delivery/SKILL.md", text)
        self.assertIn("never overrides Delivery Harness authority", text)
        self.assertLessEqual(len(AGENTS.read_bytes()), 12 * 1024)
        block = text.split("## AUTONOMOUS_DELIVERY_CONTINUE", 1)[1]
        block = block.split("\n## ", 1)[0]
        self.assertLessEqual(len(block.encode("utf-8")), 900)

    def test_control_contract_is_schema_valid_and_write_set_closed(self) -> None:
        metadata = frontmatter(CTRL)
        schema_doc = json.loads(TASK_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(metadata, schema_doc)
        self.assertEqual(metadata["task_id"], "CTRL-AUTONOMOUS-DELIVERY-SKILL-V1")
        write_set = set(metadata["managed_write_set"])
        expected = {
            "docs/tasks/CTRL-AUTONOMOUS-DELIVERY-SKILL-V1.md",
            ".agents/skills/autonomous-delivery/SKILL.md",
            ".agents/skills/autonomous-delivery/references/product-system-contract.md",
            ".agents/skills/autonomous-delivery/references/roadmap-challenge.md",
            "AGENTS.md",
            "tests/test_autonomous_delivery_skill.py",
        }
        self.assertEqual(write_set, expected)
        for path in FORBIDDEN_TOUCH:
            self.assertNotIn(path, write_set)


if __name__ == "__main__":
    unittest.main()
