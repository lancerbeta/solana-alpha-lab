from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/contracts/task21_checkpoint_remote_recovery_contract_v1.md"
RECEIPT = (
    ROOT
    / "docs/evidence/task21/checkpoint_remote_recovery_acceptance_v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


class Task21CheckpointRemoteRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = _receipt()

    def test_exact_remote_object_and_raw_identity_are_bound(self) -> None:
        archive = self.receipt["archive"]
        drive = self.receipt["google_drive"]
        self.assertEqual(self.receipt["verdict"], "PASS")
        self.assertEqual(self.receipt["status"], "PASS_REMOTE_RECOVERY_PROVEN")
        self.assertEqual(
            drive["pre_create_exact_name_check"],
            {"result": "ABSENT", "collision": False},
        )
        self.assertEqual(
            drive["file"]["parent_folder_id"],
            "1EISgmsB8nt2pkU4uBUO6Sav1Fzbo6Hw3",
        )
        self.assertFalse(drive["file"]["existing_file_updated"])
        self.assertTrue(drive["raw_readback"]["complete_byte_identity"])
        self.assertEqual(drive["raw_readback"]["decoded_bytes"], archive["bytes"])
        self.assertEqual(drive["raw_readback"]["sha256"], archive["sha256"])

    def test_isolated_restore_matches_frozen_inventory_without_source_mutation(
        self,
    ) -> None:
        archive = self.receipt["archive"]
        restored = self.receipt["isolated_restore"]
        self.assertEqual(restored["archive_sha256"], archive["sha256"])
        self.assertEqual(
            restored["restored_file_count"], archive["source_file_count"]
        )
        self.assertEqual(restored["restored_file_count"], 32)
        self.assertEqual(
            restored["restored_stored_bytes"], archive["source_stored_bytes"]
        )
        self.assertEqual(
            restored["restored_inventory_sha256"],
            archive["source_inventory_sha256"],
        )
        self.assertTrue(restored["source_unchanged"])
        self.assertEqual(restored["source_mutations"], 0)
        self.assertEqual(restored["source_deletions"], 0)
        self.assertEqual(restored["restore_overwrites"], 0)

    def test_scope_and_next_boundary_remain_fail_closed(self) -> None:
        state = self.receipt["checkpoint_state_after"]
        actions = self.receipt["actual_actions"]
        self.assertEqual(_sha256(CONTRACT), self.receipt["contract"]["sha256"])
        self.assertEqual(state["remote_recovery_status"], "REMOTE_RECOVERY_PROVEN")
        self.assertEqual(state["disposition"], "EXTEND_EVIDENCE")
        self.assertFalse(state["dataset_ready"])
        self.assertFalse(state["task22_eligible"])
        self.assertEqual(actions["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(actions["cash_spend_usd_cents"], 0)
        self.assertEqual(actions["wallet_signer_transaction_actions"], 0)
        self.assertEqual(actions["drive_updates"], 0)
        self.assertEqual(actions["drive_deletions"], 0)
        self.assertEqual(
            self.receipt["next_boundary"]["atom_id"],
            "T21-A6S_INFORMATION_SUFFICIENCY_REBASE_V1",
        )


if __name__ == "__main__":
    unittest.main()
