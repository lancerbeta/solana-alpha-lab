from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from solana_alpha_lab.task26c_owned_execution_canary_readiness import (
    CanaryReadinessError,
    FakeSigner,
    FakeTransport,
    build_readiness_evidence,
    evaluate_case,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/task26c_owned_execution_canary_readiness_contract_v1.yaml"
CONTRACT = ROOT / "docs/contracts/task26c_owned_execution_canary_readiness_contract_v1.md"
TASK_DOC = ROOT / "docs/tasks/TASK-26C-minimal-owned-execution-canary-readiness.md"
SCHEMA = ROOT / "catalog/schemas/task26c_owned_execution_canary_readiness.schema.json"
FIXTURE = ROOT / "tests/fixtures/task26c/owned_execution_canary_readiness_matrix_v1.json"
EVIDENCE = ROOT / "docs/evidence/task26c/a2_owned_canary_readiness_acceptance_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task26COwnedExecutionCanaryReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_01_contract_and_bindings_are_exact(self) -> None:
        self.assertTrue(CONTRACT.is_file())
        self.assertTrue(TASK_DOC.is_file())
        self.assertEqual(self.config["task_id"], "TASK-26C")
        self.assertFalse(self.config["authority"]["canary_authority"])
        self.assertEqual(self.config["authority"]["task27"], "forbidden")
        for binding in self.config["frozen_input_bindings"]:
            with self.subTest(asset_id=binding["asset_id"]):
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])

    def test_02_fixture_cases_enforce_reconciliation_and_health(self) -> None:
        for case in self.fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                if "expected_error" in case:
                    with self.assertRaisesRegex(CanaryReadinessError, case["expected_error"]):
                        evaluate_case(case)
                else:
                    self.assertEqual(evaluate_case(case)["outcome"], case["expected_outcome"])

    def test_03_fake_doubles_cannot_sign_or_send(self) -> None:
        with self.assertRaisesRegex(CanaryReadinessError, "fake_signer_never_signs"):
            FakeSigner().sign(b"not-a-transaction")
        self.assertEqual(
            FakeTransport("LANDED_SUCCESS").observe("attempt-test"),
            {"attempt_id": "attempt-test", "terminal_state": "LANDED_SUCCESS"},
        )

    def test_04_evidence_validates_and_preserves_non_authority(self) -> None:
        evidence = build_readiness_evidence(ROOT)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(evidence)
        self.assertEqual(
            evidence["decision"]["result"],
            "READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS",
        )
        self.assertFalse(evidence["decision"]["canary_authority"])
        self.assertFalse(evidence["decision"]["task27_authority"])
        self.assertEqual(evidence["decision"]["numeric_netreturn"], "FORBIDDEN")
        self.assertIn("UNKNOWN_BLOCKS_RETRY", evidence["nonclaims"])
        self.assertEqual(len(evidence["case_results"]), 12)

    def test_05_written_evidence_is_deterministic(self) -> None:
        write_outputs(ROOT)
        written = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(written, build_readiness_evidence(ROOT))


if __name__ == "__main__":
    unittest.main()
