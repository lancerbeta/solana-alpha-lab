from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from solana_alpha_lab.task18_data_quality import (
    audit_narrow_data_quality,
    select_verdict,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task18"
    / "narrow_data_quality_contract_v1.json"
)
AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task18"
    / "narrow_data_quality_audit_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task18"
    / "narrow_data_quality_summary_v1.md"
)
FROZEN_CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
RAW_EVIDENCE_AVAILABLE = all(
    (ROOT / row["path"]).is_file()
    for row in FROZEN_CONTRACT["raw_inventory"]["files"]
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task18DataQualityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_actual_frozen_raw_returns_fit_with_limitations(self) -> None:
        result = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        self.assertEqual(result["verdict"], "FIT_WITH_LIMITATIONS")
        self.assertEqual(
            result["limitations"],
            [
                "BACKUP_INVENTORY_NOT_OBSERVED",
                "OVERWRITE_PREVENTION_NOT_PROVEN_BY_CURRENT_HASHES",
                "RESTORE_TEST_NOT_OBSERVED",
            ],
        )
        self.assertTrue(
            result["claims"]["narrow_quote_only_data_quality"]
        )
        self.assertFalse(result["claims"]["cross_token_generalization"])
        self.assertFalse(result["claims"]["fillable"])
        self.assertFalse(result["claims"]["net_return"])
        self.assertFalse(result["claims"]["alpha"])

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_coverage_and_quality_metrics_reconcile_exactly(self) -> None:
        result = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        coverage = result["coverage"]
        self.assertEqual(
            (
                coverage["members"],
                coverage["accepted_windows"],
                coverage["excluded_retained_windows"],
                coverage["files"],
                coverage["accepted_attempts"],
                coverage["excluded_retained_attempts"],
                coverage["total_attempts"],
                coverage["complete_quote_pairs"],
                coverage["received_bytes"],
                coverage["stored_bytes"],
            ),
            (1, 3, 1, 12, 24, 8, 32, 12, 51_958, 179_208),
        )
        metrics = result["quality_metrics"]
        self.assertEqual(metrics["unique_composite_identities"], 32)
        self.assertEqual(metrics["unique_quote_attempt_ids"], 32)
        self.assertEqual(metrics["unique_raw_event_ids"], 32)
        self.assertEqual(metrics["unique_content_hashes"], 32)
        self.assertEqual(metrics["duplicate_content_hashes"], 0)
        self.assertEqual(metrics["pit_violations"], 0)
        self.assertEqual(metrics["latency_mismatches"], 0)
        self.assertEqual(metrics["revision_conflicts"], 0)
        self.assertEqual(metrics["hard_failure_count"], 0)
        self.assertEqual(metrics["limitation_count"], 3)
        self.assertGreaterEqual(metrics["minimum_request_gap_seconds"], 2.2)
        self.assertEqual(
            len(metrics["accepted_trigger_separation_seconds"]),
            2,
        )
        self.assertTrue(
            all(
                value >= 1_800
                for value in metrics[
                    "accepted_trigger_separation_seconds"
                ]
            )
        )

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_all_hard_checks_pass_and_retention_is_the_only_limitation(
        self,
    ) -> None:
        result = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        checks = {row["check_id"]: row for row in result["checks"]}
        self.assertEqual(len(checks), 11)
        self.assertEqual(
            checks["RETENTION_AND_RESTORE"]["status"],
            "LIMITATION",
        )
        for check_id, row in checks.items():
            with self.subTest(check_id=check_id):
                if check_id != "RETENTION_AND_RESTORE":
                    self.assertEqual(row["status"], "PASS")
                    self.assertEqual(row["failures"], [])

    def test_missing_workspace_fails_closed_as_evidence_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = audit_narrow_data_quality(
                repository_root=Path(directory),
                contract_path=CONTRACT_PATH,
            )
        self.assertEqual(result["verdict"], "EVIDENCE_UNAVAILABLE")
        self.assertEqual(result["coverage"]["audited_attempts"], 0)
        inventory = result["checks"][0]
        self.assertEqual(inventory["check_id"], "INVENTORY_INTEGRITY")
        self.assertEqual(inventory["status"], "FAIL")
        self.assertGreater(len(inventory["failures"]), 0)

    def test_verdict_precedence_is_deterministic(self) -> None:
        self.assertEqual(
            select_verdict(
                availability_failures=["MISSING"],
                hard_failures=["PIT"],
                limitations=["BACKUP"],
            ),
            "EVIDENCE_UNAVAILABLE",
        )
        self.assertEqual(
            select_verdict(
                availability_failures=[],
                hard_failures=["PIT"],
                limitations=["BACKUP"],
            ),
            "NOT_FIT",
        )
        self.assertEqual(
            select_verdict(
                availability_failures=[],
                hard_failures=[],
                limitations=["BACKUP"],
            ),
            "FIT_WITH_LIMITATIONS",
        )
        self.assertEqual(
            select_verdict(
                availability_failures=[],
                hard_failures=[],
                limitations=[],
            ),
            "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND",
        )

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_audit_is_deterministic_and_matches_tracked_evidence(self) -> None:
        first = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        second = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        self.assertEqual(first, second)
        tracked = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(first, tracked)
        summary = SUMMARY_PATH.read_text(encoding="utf-8")
        self.assertIn(sha256(AUDIT_PATH), summary)
        self.assertIn("FIT_WITH_LIMITATIONS", summary)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_audit_does_not_mutate_frozen_raw_files(self) -> None:
        inventory = self.contract["raw_inventory"]["files"]
        before = {
            row["path"]: sha256(ROOT / row["path"])
            for row in inventory
        }
        audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        after = {
            row["path"]: sha256(ROOT / row["path"])
            for row in inventory
        }
        self.assertEqual(before, after)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_authority_and_next_gate_remain_bounded(self) -> None:
        result = audit_narrow_data_quality(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        for value in result["authority"].values():
            self.assertEqual(value, 0)
        self.assertEqual(result["next_gate"]["task_id"], "TASK-19")
        self.assertEqual(
            result["next_gate"]["status"],
            "ELIGIBLE_CONDITIONAL_ON_TASK18_ACCEPTANCE",
        )
        self.assertFalse(
            result["next_gate"]["replay_authorized_by_this_audit"]
        )


if __name__ == "__main__":
    unittest.main()
