from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_recovery import (
    MANIFEST_ENTRY,
    Task21ForwardRecoveryError,
    build_archive_bytes,
    materialize_archive,
    verify_and_restore_archive,
)


CONFIG_PATH = ROOT / "configs/task21_pre_h24_recovery_refresh_v1.yaml"
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/task21/pre_h24_recovery_refresh_acceptance_v1.json"
)


LOCAL_SOURCE_TESTS = {
    "test_exact_live_source_inventory_is_frozen",
    "test_create_only_materialize_and_isolated_restore",
    "test_hash_drift_and_path_escape_fail_closed",
}


def _local_source_inventory_exact(config: dict) -> bool:
    files = []
    for relative in config["source_roots"]:
        root = ROOT / relative
        if not root.is_dir():
            return False
        files.extend(path for path in root.rglob("*") if path.is_file())
    return (
        len(files) == config["expected_source"]["file_count"]
        and sum(path.stat().st_size for path in files)
        == config["expected_source"]["stored_bytes"]
    )


class Task21ForwardRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        if (
            self._testMethodName in LOCAL_SOURCE_TESTS
            and not _local_source_inventory_exact(self.config)
        ):
            self.skipTest("requires excluded exact local TASK-21 evidence")

    def test_exact_live_source_inventory_is_frozen(self) -> None:
        first, manifest = build_archive_bytes(
            repository_root=ROOT,
            source_roots=self.config["source_roots"],
        )
        second, repeated = build_archive_bytes(
            repository_root=ROOT,
            source_roots=self.config["source_roots"],
        )
        self.assertEqual(first, second)
        self.assertEqual(manifest, repeated)
        self.assertEqual(
            manifest["file_count"], self.config["expected_source"]["file_count"]
        )
        self.assertEqual(
            manifest["stored_bytes"],
            self.config["expected_source"]["stored_bytes"],
        )
        self.assertEqual(manifest["provider_api_rpc_wss_calls"], 0)

    def test_create_only_materialize_and_isolated_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            result = materialize_archive(
                repository_root=ROOT,
                source_roots=self.config["source_roots"],
                output_directory=temp / "package",
            )
            self.assertTrue(result["created"])
            repeated = materialize_archive(
                repository_root=ROOT,
                source_roots=self.config["source_roots"],
                output_directory=temp / "package",
            )
            self.assertFalse(repeated["created"])
            self.assertEqual(result["sha256"], repeated["sha256"])
            restored = verify_and_restore_archive(
                archive_path=result["path"],
                expected_archive_sha256=result["sha256"],
                restore_root=temp / "restore",
                source_repository_root=ROOT,
            )
            self.assertEqual(
                restored["restored_file_count"],
                self.config["expected_source"]["file_count"],
            )
            self.assertTrue(restored["source_unchanged"])
            self.assertEqual(restored["source_mutations"], 0)
            self.assertEqual(restored["source_deletions"], 0)

    def test_hash_drift_and_path_escape_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            result = materialize_archive(
                repository_root=ROOT,
                source_roots=self.config["source_roots"],
                output_directory=temp / "package",
            )
            with self.assertRaisesRegex(
                Task21ForwardRecoveryError, "archive_sha256_drift"
            ):
                verify_and_restore_archive(
                    archive_path=result["path"],
                    expected_archive_sha256="0" * 64,
                    restore_root=temp / "restore-hash",
                )

            unsafe = temp / "unsafe.zip"
            manifest = {
                "file_count": 1,
                "stored_bytes": 1,
                "source_inventory_sha256": "unused",
                "files": [{"path": "../escape", "bytes": 1, "sha256": "x"}],
            }
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr(MANIFEST_ENTRY, json.dumps(manifest))
                archive.writestr("../escape", b"x")
            unsafe_hash = hashlib.sha256(unsafe.read_bytes()).hexdigest()
            with self.assertRaises(Task21ForwardRecoveryError):
                verify_and_restore_archive(
                    archive_path=unsafe,
                    expected_archive_sha256=unsafe_hash,
                    restore_root=temp / "restore-unsafe",
                )

    def test_authority_and_h24_boundary_are_zero_provider(self) -> None:
        authority = self.config["authority"]
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)
        self.assertFalse(authority["overwrite"])
        self.assertFalse(authority["source_deletion"])
        self.assertFalse(self.config["h24"]["provider_authority_granted"])

    def test_acceptance_proves_remote_identity_and_full_restore(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["verdict"], "PASS")
        self.assertEqual(
            receipt["google_drive"]["file"]["id"],
            "1dQDC9fHSaDo8fOEJXm5Ecs3pF_ghLBRv",
        )
        self.assertTrue(
            receipt["google_drive"]["raw_readback"]["complete_byte_identity"]
        )
        self.assertEqual(
            receipt["google_drive"]["raw_readback"]["sha256"],
            receipt["archive"]["sha256"],
        )
        self.assertEqual(receipt["isolated_restore"]["restored_file_count"], 23)
        self.assertTrue(receipt["isolated_restore"]["source_unchanged"])
        self.assertEqual(receipt["provider_api_rpc_wss_calls"], 0)


if __name__ == "__main__":
    unittest.main()
