from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFLINE = ROOT / "docs/evidence/task21/r3_p2_event_triggered_capture_offline_acceptance_v1.json"
RUNTIME = ROOT / "docs/evidence/task21/r3_p2_event_triggered_capture_runtime_acceptance_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21R3P2AcceptanceTests(unittest.TestCase):
    def test_offline_acceptance_binds_every_declared_artifact(self) -> None:
        receipt = json.loads(OFFLINE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["offline_acceptance"]["targeted_tests_total"], 17)
        for item in receipt["artifacts"]:
            self.assertEqual((ROOT / item["path"]).stat().st_size, item["bytes"])
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])

    def test_runtime_acceptance_binds_tracked_inputs_and_final_boundary(self) -> None:
        receipt = json.loads(RUNTIME.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        for item in receipt["protected_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        self.assertEqual(receipt["p2"]["panels_complete"], 2)
        self.assertEqual(receipt["actual_actions"]["jupiter_calls"], 16)
        self.assertEqual(receipt["actual_actions"]["retries"], 0)
        self.assertEqual(
            receipt["next_boundary"]["status"],
            "R3_COMPLETE_FINAL_COHORT_REVIEW_AND_FREEZE_REQUIRED",
        )
        self.assertFalse(receipt["next_boundary"]["task22_authorized"])
        self.assertFalse(receipt["next_boundary"]["a7_authorized"])

    def test_local_runtime_evidence_matches_when_present(self) -> None:
        receipt = json.loads(RUNTIME.read_text(encoding="utf-8"))
        root = ROOT / receipt["local_evidence"]["root"]
        if not root.is_dir():
            self.skipTest("requires excluded exact local R3 P2 evidence")
        files = sorted(path for path in root.rglob("*") if path.is_file())
        self.assertEqual(len(files), receipt["local_evidence"]["file_count"])
        self.assertEqual(
            sum(path.stat().st_size for path in files),
            receipt["local_evidence"]["stored_bytes"],
        )
        self.assertEqual(
            digest(root / "runtime_receipt.json"),
            receipt["local_evidence"]["runtime_receipt_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
