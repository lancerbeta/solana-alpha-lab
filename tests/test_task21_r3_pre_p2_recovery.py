from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_recovery import (  # noqa: E402
    materialize_archive,
    verify_and_restore_archive,
)


CONFIG = ROOT / "configs/task21_r3_pre_p2_recovery_refresh_v1.yaml"


class Task21R3PreP2RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    def test_live_inventory_materializes_deterministically_and_restores(self) -> None:
        if any(
            not (ROOT / relative).is_dir()
            for relative in self.config["source_roots"]
        ):
            self.skipTest("requires excluded exact local R3 P0/P1 evidence")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            first = materialize_archive(
                repository_root=ROOT,
                source_roots=self.config["source_roots"],
                output_directory=temp / "package",
                atom_id=self.config["atom_id"],
                archive_prefix=self.config["local"]["archive_prefix"],
            )
            second = materialize_archive(
                repository_root=ROOT,
                source_roots=self.config["source_roots"],
                output_directory=temp / "package",
                atom_id=self.config["atom_id"],
                archive_prefix=self.config["local"]["archive_prefix"],
            )
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["manifest"]["file_count"], 18)
            self.assertEqual(first["manifest"]["stored_bytes"], 237983)
            self.assertEqual(first["manifest"]["atom_id"], self.config["atom_id"])
            restored = verify_and_restore_archive(
                archive_path=first["path"],
                expected_archive_sha256=first["sha256"],
                restore_root=temp / "restore",
                source_repository_root=ROOT,
            )
            self.assertEqual(restored["restored_file_count"], 18)
            self.assertTrue(restored["source_unchanged"])

    def test_authority_forbids_overwrite_delete_and_sensitive_actions(self) -> None:
        authority = self.config["authority"]
        self.assertEqual(authority["google_drive_writes_max"], 1)
        self.assertEqual(authority["jupiter_calls_max_after_recovery"], 16)
        for key in (
            "credentials",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
        ):
            self.assertEqual(authority[key], 0)
        self.assertFalse(authority["delete"])
        self.assertFalse(authority["overwrite"])
        self.assertFalse(authority["merge"])


if __name__ == "__main__":
    unittest.main()
