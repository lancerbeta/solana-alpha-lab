from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_bounded_panel_checkpoint import (  # noqa: E402
    build_checkpoint_archive_bytes,
    evaluate_checkpoint,
    sha256_bytes,
    verify_and_restore_checkpoint,
)
from solana_alpha_lab.task21_owner_pulse import build_owner_pulse  # noqa: E402


CONFIG_PATH = ROOT / "configs/task21_bounded_panel_checkpoint_v1.yaml"
RUN_PLAN_PATH = ROOT / "configs/task21_forward_collection_run_plan_v1.yaml"
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task21/bounded_panel_checkpoint_acceptance_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21BoundedPanelCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_bytes())
        cls.run_plan = yaml.safe_load(RUN_PLAN_PATH.read_bytes())
        cls.pulse = build_owner_pulse(repository_root=ROOT)
        cls.acceptance = json.loads(ACCEPTANCE_PATH.read_bytes())

    def test_frozen_inputs_and_current_decision_are_exact(self) -> None:
        for binding in self.config["frozen_inputs"].values():
            if isinstance(binding, dict) and "sha256" in binding:
                self.assertEqual(sha256(ROOT / binding["path"]), binding["sha256"])
        decision = evaluate_checkpoint(
            run_plan=self.run_plan,
            owner_pulse=self.pulse,
            observed=self.config["observed_operational_evidence"],
        )
        self.assertEqual(decision["disposition"], "EXTEND_EVIDENCE")
        self.assertFalse(decision["dataset_ready"])
        self.assertFalse(decision["task22_eligible"])
        self.assertFalse(decision["hypothesis_outcomes_read"])
        self.assertFalse(decision["h72_h168_required"])
        self.assertEqual(
            set(decision["shortfalls"]),
            {
                "MINIMUM_COMPLETE_MEMBERS",
                "MINIMUM_COMPLETE_PANELS",
                "MINIMUM_DISTINCT_ADMISSION_DATES_UTC",
                "MINIMUM_DISTINCT_ADMISSION_WEEKS_UTC",
                "MULTIPLE_OBSERVED_MARKET_STATES_NOT_ESTABLISHED",
            },
        )

    def test_archive_is_deterministic_and_create_only_restorable(self) -> None:
        roots = self.config["source_roots"]
        if not all((ROOT / relative).is_dir() for relative in roots):
            self.skipTest("TASK21_LOCAL_RAW_NOT_PRESENT")
        decision = evaluate_checkpoint(
            run_plan=self.run_plan,
            owner_pulse=self.pulse,
            observed=self.config["observed_operational_evidence"],
        )
        first, manifest = build_checkpoint_archive_bytes(
            repository_root=ROOT,
            source_roots=roots,
            decision=decision,
        )
        second, repeated_manifest = build_checkpoint_archive_bytes(
            repository_root=ROOT,
            source_roots=roots,
            decision=decision,
        )
        self.assertEqual(first, second)
        self.assertEqual(manifest, repeated_manifest)
        self.assertEqual(manifest["outcome_blindness"], "SEALED")
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "checkpoint.zip"
            archive_path.write_bytes(first)
            restored = verify_and_restore_checkpoint(
                archive_path=archive_path,
                expected_archive_sha256=sha256_bytes(first),
                restore_root=Path(directory) / "restore",
                source_repository_root=ROOT,
            )
        self.assertEqual(restored["restored_file_count"], manifest["file_count"])
        self.assertEqual(restored["restored_stored_bytes"], manifest["stored_bytes"])
        self.assertTrue(restored["source_unchanged"])
        self.assertEqual(restored["source_mutations"], 0)
        self.assertEqual(restored["source_deletions"], 0)

    def test_no_external_or_promotion_authority_leaks(self) -> None:
        authority = self.config["authority"]
        self.assertTrue(authority["local_writes"])
        for key, value in authority.items():
            if key != "local_writes":
                self.assertIn(value, (0, False), key)
        decision = self.config["decision"]
        self.assertFalse(decision["dataset_ready"])
        self.assertFalse(decision["task22_eligible"])
        self.assertEqual(decision["catalog_status"], "PENDING_FINAL_T21_A7")
        self.assertEqual(
            self.config["local_recovery"]["remote_status_after_local_pass"],
            "REMOTE_RECOVERY_PENDING",
        )

    def test_acceptance_receipt_binds_tracked_and_local_evidence(self) -> None:
        receipt = self.acceptance
        self.assertEqual(
            receipt["status"],
            "PASS_LOCAL_CHECKPOINT_REMOTE_RECOVERY_PENDING",
        )
        self.assertEqual(receipt["decision"]["disposition"], "EXTEND_EVIDENCE")
        self.assertFalse(receipt["decision"]["dataset_ready"])
        self.assertFalse(receipt["decision"]["task22_eligible"])
        for artifact in receipt["tracked_artifacts"]:
            path = ROOT / artifact["path"]
            self.assertEqual(path.stat().st_size, artifact["bytes"])
            self.assertEqual(sha256(path), artifact["sha256"])
        checkpoint = receipt["local_checkpoint"]
        archive_path = ROOT / checkpoint["archive_path"]
        if not archive_path.is_file():
            self.skipTest("TASK21_LOCAL_CHECKPOINT_ARCHIVE_NOT_PRESENT")
        self.assertEqual(archive_path.stat().st_size, checkpoint["archive_bytes"])
        self.assertEqual(sha256(archive_path), checkpoint["archive_sha256"])
        self.assertEqual(
            checkpoint["source_inventory_sha256"],
            checkpoint["restored_inventory_sha256"],
        )
        self.assertEqual(checkpoint["remote_recovery_status"], "REMOTE_RECOVERY_PENDING")
        self.assertFalse(
            receipt["product_vision_gate"]["terminal_result_recorded"]
        )
        self.assertIn("NO_TASK21_DONE", receipt["non_claims"])


if __name__ == "__main__":
    unittest.main()
