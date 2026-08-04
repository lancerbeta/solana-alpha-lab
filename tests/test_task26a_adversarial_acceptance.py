from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task26a_adversarial_acceptance import (  # noqa: E402
    MUTATIONS,
    run_adversarial,
)


RECEIPT_PATH = ROOT / "docs/evidence/task26a/a2_adversarial_acceptance_v1.json"
MATRIX_PATH = ROOT / "tests/fixtures/task26a/execution_evidence_adversarial_matrix_v1.json"


class Task26AAdversarialAcceptanceTests(unittest.TestCase):
    def test_01_all_mutations_rejected(self) -> None:
        receipt = run_adversarial(ROOT)
        self.assertEqual(receipt["status"], "PASS_ALL_MUTATIONS_REJECTED")
        self.assertEqual(len(receipt["adversarial_cases"]), 8)
        self.assertEqual(len(MUTATIONS), 8)
        for case in receipt["adversarial_cases"]:
            with self.subTest(mutation_id=case["mutation_id"]):
                self.assertEqual(case["status"], "PASS_EXACT_REJECTION")
                self.assertEqual(case["expected_error"], case["observed_error"])
        self.assertEqual(receipt["decision"]["result"], "EXTEND_EXECUTION_EVIDENCE")
        self.assertFalse(receipt["decision"]["task27_authority"])

    def test_02_written_receipt_and_matrix_agree(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(receipt["adversarial_cases"]), len(matrix["mutations"]))
        expected = {row["mutation_id"]: row["expected_error"] for row in matrix["mutations"]}
        for case in receipt["adversarial_cases"]:
            self.assertEqual(expected[case["mutation_id"]], case["expected_error"])


if __name__ == "__main__":
    unittest.main()
