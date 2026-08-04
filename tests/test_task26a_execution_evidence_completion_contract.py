from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/contracts/task26a_execution_evidence_completion_contract_v1.md"
CONFIG = ROOT / "configs/task26a_execution_evidence_completion_contract_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/task26a_execution_evidence_completion.schema.json"
FIXTURE = ROOT / "tests/fixtures/task26a/execution_evidence_inventory_v1.json"
TASK_DOC = ROOT / "docs/tasks/TASK-26A-execution-evidence-completion.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task26AContractTests(unittest.TestCase):
    def test_01_contract_config_schema_and_fixture_exist(self) -> None:
        for path in (CONTRACT, CONFIG, SCHEMA, FIXTURE, TASK_DOC):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file())

    def test_02_config_bindings_are_hash_exact(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["task_id"], "TASK-26A")
        self.assertIn("EXTEND_EXECUTION_EVIDENCE", config["result_enum"])
        self.assertEqual(config["authority"]["numeric_modeled_netreturn"], "forbidden")
        for binding in config["frozen_input_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_03_fixture_validates_against_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(fixture)
        self.assertEqual(fixture["decision"]["result"], "EXTEND_EXECUTION_EVIDENCE")
        self.assertEqual(fixture["population_summary"]["quote_pairs"], 36)
        self.assertEqual(
            fixture["population_summary"]["pairs_with_complete_fee_evidence"],
            0,
        )
        self.assertEqual(
            fixture["population_summary"]["numeric_modeled_netreturn_claims"],
            0,
        )

    def test_04_contract_forbids_numeric_netreturn_and_task27(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("numeric NetReturn", text)
        self.assertIn("EXTEND_EXECUTION_EVIDENCE", text)
        self.assertIn("tracked repository bytes only", text.lower())


if __name__ == "__main__":
    unittest.main()
