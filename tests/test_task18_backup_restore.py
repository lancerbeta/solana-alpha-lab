from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from solana_alpha_lab.task18_backup_restore import (
    MANIFEST_ENTRY,
    Task18BackupError,
    build_archive_bytes,
    materialize_archive,
    verify_and_restore_archive,
)

ROOT = Path(__file__).resolve().parents[1]
REPAIR_CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task18"
    / "content_addressed_backup_restore_contract_v1.json"
)
REPAIR_RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task18"
    / "content_addressed_backup_restore_receipt_v1.json"
)
FROZEN_REPAIR_CONTRACT = json.loads(
    REPAIR_CONTRACT_PATH.read_text(encoding="utf-8")
)
QUALITY_CONTRACT_PATH = (
    ROOT
    / FROZEN_REPAIR_CONTRACT["frozen_inputs"]["quality_contract_path"]
)
FROZEN_QUALITY_CONTRACT = json.loads(
    QUALITY_CONTRACT_PATH.read_text(encoding="utf-8")
)
RAW_EVIDENCE_AVAILABLE = all(
    (ROOT / row["path"]).is_file()
    for row in FROZEN_QUALITY_CONTRACT["raw_inventory"]["files"]
)


class Task18BackupRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            REPAIR_CONTRACT_PATH.read_text(encoding="utf-8")
        )

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_archive_bytes_are_deterministic_and_exact(self) -> None:
        first, first_manifest = build_archive_bytes(
            repository_root=ROOT,
            repair_contract_path=REPAIR_CONTRACT_PATH,
        )
        second, second_manifest = build_archive_bytes(
            repository_root=ROOT,
            repair_contract_path=REPAIR_CONTRACT_PATH,
        )
        self.assertEqual(first, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_manifest["file_count"], 12)
        self.assertEqual(first_manifest["stored_bytes"], 179_208)
        self.assertFalse(first_manifest["contains_secrets"])
        self.assertFalse(first_manifest["source_mutation_allowed"])

        with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
            names = archive.namelist()
            self.assertEqual(names[0], MANIFEST_ENTRY)
            self.assertEqual(len(names), 13)
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_materialized_archive_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = materialize_archive(
                repository_root=ROOT,
                repair_contract_path=REPAIR_CONTRACT_PATH,
                output_directory=Path(directory),
            )
            self.assertTrue(result["path"].is_file())
            self.assertEqual(result["path"].stat().st_size, result["bytes"])
            self.assertEqual(
                result["filename"],
                f"TASK18_RAW_BACKUP_v1_{result['sha256']}.zip",
            )
            repeated = materialize_archive(
                repository_root=ROOT,
                repair_contract_path=REPAIR_CONTRACT_PATH,
                output_directory=Path(directory),
            )
            self.assertEqual(result["sha256"], repeated["sha256"])
            self.assertEqual(result["path"], repeated["path"])

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_local_restore_reproduces_a3_quality_result(self) -> None:
        with tempfile.TemporaryDirectory() as output_directory:
            with tempfile.TemporaryDirectory() as restore_directory:
                archive = materialize_archive(
                    repository_root=ROOT,
                    repair_contract_path=REPAIR_CONTRACT_PATH,
                    output_directory=Path(output_directory),
                )
                restored = verify_and_restore_archive(
                    archive_path=archive["path"],
                    source_repository_root=ROOT,
                    repair_contract_path=REPAIR_CONTRACT_PATH,
                    restore_root=Path(restore_directory),
                )
        self.assertEqual(restored["archive_sha256"], archive["sha256"])
        self.assertEqual(restored["archive_md5"], archive["md5"])
        self.assertEqual(restored["restored_file_count"], 12)
        self.assertEqual(restored["restored_stored_bytes"], 179_208)
        self.assertEqual(
            restored["restored_audit_verdict"],
            "FIT_WITH_LIMITATIONS",
        )
        self.assertEqual(restored["restored_hard_failure_count"], 0)
        self.assertEqual(restored["source_mutations"], 0)
        self.assertEqual(restored["source_deletions"], 0)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_tampered_archive_fails_closed(self) -> None:
        archive_bytes, _manifest = build_archive_bytes(
            repository_root=ROOT,
            repair_contract_path=REPAIR_CONTRACT_PATH,
        )
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "tampered.zip"
            source = zipfile.ZipFile(io.BytesIO(archive_bytes), "r")
            with zipfile.ZipFile(archive_path, "w") as tampered:
                changed = False
                for info in source.infolist():
                    value = source.read(info.filename)
                    if not changed and info.filename != MANIFEST_ENTRY:
                        value += b" "
                        changed = True
                    tampered.writestr(info, value)
            source.close()
            with self.assertRaises(
                (Task18BackupError, zipfile.BadZipFile),
            ):
                verify_and_restore_archive(
                    archive_path=archive_path,
                    source_repository_root=ROOT,
                    repair_contract_path=REPAIR_CONTRACT_PATH,
                    restore_root=Path(directory) / "restore",
                )

    def test_authority_is_exact_and_zero_delete(self) -> None:
        authority = self.contract["authority"]
        self.assertEqual(
            authority["class"],
            "LOCAL_WRITE_PLUS_GOOGLE_DRIVE_WRITE",
        )
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["source_raw_deletions"], 0)
        self.assertEqual(authority["source_raw_mutations"], 0)
        self.assertEqual(authority["google_drive_file_uploads_max"], 1)
        self.assertEqual(authority["google_drive_file_updates"], 0)
        self.assertEqual(authority["google_drive_deletions"], 0)
        self.assertEqual(authority["sharing_changes"], 0)
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_drive_receipt_matches_deterministic_archive(self) -> None:
        receipt = json.loads(
            REPAIR_RECEIPT_PATH.read_text(encoding="utf-8")
        )
        archive_bytes, _manifest = build_archive_bytes(
            repository_root=ROOT,
            repair_contract_path=REPAIR_CONTRACT_PATH,
        )
        archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
        archive_md5 = hashlib.md5(
            archive_bytes,
            usedforsecurity=False,
        ).hexdigest()

        self.assertEqual(receipt["verdict"], "PASS")
        self.assertEqual(receipt["archive"]["bytes"], len(archive_bytes))
        self.assertEqual(receipt["archive"]["sha256"], archive_sha256)
        self.assertEqual(receipt["archive"]["md5"], archive_md5)
        readback = receipt["google_drive"]["raw_readback"]
        self.assertEqual(readback["decoded_bytes"], len(archive_bytes))
        self.assertEqual(readback["sha256"], archive_sha256)
        self.assertEqual(readback["md5"], archive_md5)
        self.assertTrue(readback["complete_byte_identity"])
        self.assertFalse(receipt["google_drive"]["file"]["shared"])
        self.assertEqual(
            receipt["google_drive"]["file"]["visibility"],
            "not_shared",
        )
        self.assertEqual(
            receipt["restore"]["restored_a3_verdict"],
            "FIT_WITH_LIMITATIONS",
        )
        self.assertEqual(
            receipt["reconciliation"]["reconciled_verdict"],
            "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND",
        )
        self.assertFalse(
            receipt["reconciliation"][
                "task19_replay_authorized_by_this_repair"
            ]
        )

    def test_drive_receipt_respects_external_authority(self) -> None:
        receipt = json.loads(
            REPAIR_RECEIPT_PATH.read_text(encoding="utf-8")
        )
        authority = receipt["authority_receipt"]
        self.assertEqual(authority["source_raw_mutations"], 0)
        self.assertEqual(authority["source_raw_deletions"], 0)
        self.assertEqual(authority["google_drive_folder_creates"], 1)
        self.assertEqual(authority["google_drive_file_uploads"], 1)
        self.assertEqual(authority["google_drive_file_updates"], 0)
        self.assertEqual(authority["google_drive_file_deletions"], 0)
        self.assertEqual(authority["google_drive_sharing_changes"], 0)
        self.assertEqual(authority["google_drive_public_links_created"], 0)
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)
        self.assertFalse(authority["commit"])
        self.assertFalse(authority["push"])
        self.assertFalse(authority["pull_request"])
        self.assertFalse(authority["merge"])

    def test_missing_raw_source_fails_closed(self) -> None:
        repair = FROZEN_REPAIR_CONTRACT
        with tempfile.TemporaryDirectory() as directory:
            clean_root = Path(directory)
            for key in ("quality_contract_path", "quality_audit_path"):
                relative = repair["frozen_inputs"][key]
                destination = clean_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            with self.assertRaisesRegex(
                Task18BackupError,
                "^source_missing:",
            ):
                build_archive_bytes(
                    repository_root=clean_root,
                    repair_contract_path=REPAIR_CONTRACT_PATH,
                )


if __name__ == "__main__":
    unittest.main()
