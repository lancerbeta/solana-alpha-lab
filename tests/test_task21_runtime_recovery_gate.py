from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_runtime_recovery import (
    Task21RecoveryError,
    content_addressed_filename,
    evaluate_recovery_health,
    materialize_content_addressed_probe,
    restore_probe,
    validate_probe_bytes,
)


CONFIG_PATH = ROOT / "configs" / "task21_runtime_recovery_gate_v1.yaml"
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "task21_runtime_recovery_gate_contract_v1.md"
)
PROBE_PATH = (
    ROOT / "tests" / "fixtures" / "task21" / "runtime_recovery_probe_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "runtime_recovery_gate_receipt_v1.json"
)
EXPECTED_NORMALIZED_CONFIG_SHA256 = (
    "2c3b1361b959c002f9a8cf69d95220efdb1dec14134dd1f687ada3454281ab77"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


class TestTask21RuntimeRecoveryGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_frozen_inputs_and_config_are_exact(self) -> None:
        for item in self.config["frozen_inputs"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["asset_id"])
            self.assertEqual(_sha256(path), item["sha256"], item["asset_id"])
        self.assertEqual(
            hashlib.sha256(_canonical_bytes(self.config)).hexdigest(),
            EXPECTED_NORMALIZED_CONFIG_SHA256,
        )

    def test_probe_is_deterministic_non_secret_and_content_addressed(self) -> None:
        value = PROBE_PATH.read_bytes()
        probe = validate_probe_bytes(value)
        expected = self.config["probe"]
        self.assertEqual(len(value), expected["bytes"])
        self.assertEqual(hashlib.sha256(value).hexdigest(), expected["sha256"])
        self.assertEqual(
            content_addressed_filename(value),
            expected["content_addressed_filename"],
        )
        self.assertFalse(probe["contains_secrets"])
        self.assertFalse(probe["contains_personal_data"])
        self.assertFalse(probe["contains_market_data"])
        self.assertFalse(probe["authorizes_forward_collection"])
        self.assertFalse(probe["authorizes_provider_calls"])

    def test_materialize_and_isolated_restore_are_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = materialize_content_addressed_probe(
                source_path=PROBE_PATH,
                output_directory=root / "out",
            )
            repeated = materialize_content_addressed_probe(
                source_path=PROBE_PATH,
                output_directory=root / "out",
            )
            self.assertEqual(first, repeated)
            restored = restore_probe(
                downloaded_path=first["path"],
                restore_root=root / "isolated",
                expected_sha256=first["sha256"],
            )
            self.assertEqual(restored["sha256"], first["sha256"])
            self.assertEqual(restored["bytes"], first["bytes"])
            self.assertEqual(restored["source_mutations"], 0)
            self.assertEqual(restored["source_deletions"], 0)

    def test_tampered_probe_and_remote_bytes_fail_closed(self) -> None:
        source = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
        source["authorizes_forward_collection"] = True
        changed = _canonical_bytes(source)
        with self.assertRaises(Task21RecoveryError):
            validate_probe_bytes(changed)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readback.json"
            path.write_bytes(PROBE_PATH.read_bytes() + b" ")
            with self.assertRaises(Task21RecoveryError):
                restore_probe(
                    downloaded_path=path,
                    restore_root=Path(directory) / "isolated",
                    expected_sha256=self.config["probe"]["sha256"],
                )

    def test_health_states_alerts_and_controls_are_fail_closed(self) -> None:
        now = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
        base = {
            "observed_at": now,
            "last_successful_backup_at": now,
            "last_successful_restore_at": now,
            "exact_readback_ok": True,
            "restore_ok": True,
        }

        healthy = evaluate_recovery_health(**base)
        self.assertEqual(healthy["health_state"], "HEALTHY")
        self.assertTrue(healthy["new_t2_admissions_allowed"])

        grace = evaluate_recovery_health(
            **{
                **base,
                "last_successful_backup_at": now - timedelta(hours=25),
            }
        )
        self.assertEqual(grace["health_state"], "HEALTHY")
        self.assertEqual(grace["alerts"], ["BACKUP_GRACE_WINDOW"])

        overdue = evaluate_recovery_health(
            **{
                **base,
                "last_successful_backup_at": now - timedelta(hours=27),
            }
        )
        self.assertEqual(overdue["health_state"], "BACKUP_OVERDUE")
        self.assertFalse(overdue["dataset_freeze_allowed"])
        self.assertTrue(overdue["new_t2_admissions_allowed"])

        overdue_48h = evaluate_recovery_health(
            **{
                **base,
                "last_successful_backup_at": now - timedelta(hours=74),
            }
        )
        self.assertFalse(overdue_48h["new_t2_admissions_allowed"])

        restore_overdue = evaluate_recovery_health(
            **{
                **base,
                "last_successful_restore_at": now - timedelta(hours=169),
            }
        )
        self.assertEqual(
            restore_overdue["health_state"],
            "RESTORE_OVERDUE",
        )

        at_risk = evaluate_recovery_health(
            **{**base, "exact_readback_ok": False}
        )
        self.assertEqual(at_risk["health_state"], "EVIDENCE_AT_RISK")
        self.assertFalse(at_risk["new_t2_admissions_allowed"])

        conflict = evaluate_recovery_health(
            **{**base, "evidence_conflict": True}
        )
        self.assertEqual(conflict["health_state"], "EVIDENCE_CONFLICT")

        hard_stop = evaluate_recovery_health(
            **{**base, "storage_hard_stop": True}
        )
        self.assertEqual(hard_stop["health_state"], "STORAGE_HARD_STOP")

    def test_authority_is_exact_and_zero_provider_collection_cash(self) -> None:
        authority = self.config["authority"]
        self.assertEqual(
            authority["class"],
            "LOCAL_WRITE_PLUS_GOOGLE_DRIVE_WRITE",
        )
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["google_drive_folder_creations_max"], 1)
        self.assertEqual(authority["google_drive_file_uploads_max"], 1)
        for key in (
            "google_drive_file_updates",
            "google_drive_deletions",
            "sharing_changes",
            "source_mutations",
            "source_deletions",
            "provider_api_rpc_wss_calls",
            "candidate_admissions",
            "collector_executions",
            "forward_raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
        ):
            self.assertEqual(authority[key], 0, key)
        for key in (
            "commit",
            "push",
            "pull_request",
            "merge",
            "wallet_actions",
            "signer_actions",
            "transaction_actions",
            "destructive_actions",
        ):
            self.assertFalse(authority[key], key)

    def test_drive_receipt_closes_all_six_evidence_classes(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        required = set(self.config["acceptance"]["required_evidence"])
        self.assertEqual(receipt["verdict"], "PASS")
        self.assertEqual(set(receipt["satisfied_evidence"]), required)
        self.assertEqual(receipt["probe"]["sha256"], self.config["probe"]["sha256"])
        self.assertEqual(receipt["probe"]["bytes"], self.config["probe"]["bytes"])
        self.assertFalse(receipt["probe"]["contains_secrets"])

        drive = receipt["google_drive"]
        self.assertEqual(
            drive["folder"]["name"],
            self.config["destination"]["folder_name"],
        )
        self.assertFalse(drive["folder"]["shared"])
        self.assertFalse(drive["file"]["shared"])
        self.assertEqual(
            drive["file"]["name"],
            self.config["probe"]["content_addressed_filename"],
        )
        self.assertEqual(drive["file"]["size"], self.config["probe"]["bytes"])
        self.assertEqual(
            drive["file"]["parent_folder_id"],
            drive["folder"]["id"],
        )
        self.assertTrue(drive["raw_readback"]["complete_byte_identity"])
        self.assertEqual(
            drive["raw_readback"]["sha256"],
            self.config["probe"]["sha256"],
        )

        restore = receipt["isolated_restore"]
        self.assertEqual(restore["sha256"], self.config["probe"]["sha256"])
        self.assertEqual(restore["bytes"], self.config["probe"]["bytes"])
        self.assertEqual(restore["source_mutations"], 0)
        self.assertEqual(restore["source_deletions"], 0)
        self.assertEqual(receipt["health"]["health_state"], "HEALTHY")
        self.assertEqual(receipt["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(receipt["cash_spend_usd_cents"], 0)
        self.assertEqual(receipt["wallet_signer_transaction_actions"], 0)
        self.assertNotIn("C:\\Users\\", json.dumps(receipt))

    def test_contract_states_probe_only_non_claim_and_next_boundary(self) -> None:
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        for text in (
            "claim that a future dataset is already backed up",
            "at total backup",
            "age of 74 hours",
            "NO_SECRET_MATERIAL_IN_EVIDENCE",
            "T21-A4_THIN_COLLECTOR_AND_OFFLINE_DRY_RUN_V1",
        ):
            self.assertIn(text, contract)
