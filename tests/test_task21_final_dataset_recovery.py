from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_recovery import (
    build_archive_bytes,
    build_source_inventory,
    canonical_json_bytes,
    sha256_bytes,
)


CONFIG_PATH = ROOT / "configs" / "task21_final_dataset_recovery_v1.yaml"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "task21_final_dataset_recovery_contract_v1.md"
ACCEPTANCE_PATH = (
    ROOT / "docs" / "evidence" / "task21" / "final_dataset_recovery_acceptance_v1.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21FinalDatasetRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.roots = [
            root
            for component in cls.config["components"]
            for root in component["source_roots"]
        ]

    def test_protected_inputs_match_exact_bytes(self) -> None:
        for item in self.config["protected_inputs"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])

    def test_components_and_combined_inventory_match(self) -> None:
        for component in self.config["components"]:
            rows = build_source_inventory(
                repository_root=ROOT,
                source_roots=component["source_roots"],
            )
            self.assertEqual(len(rows), component["expected_file_count"])
            self.assertEqual(
                sum(int(row["bytes"]) for row in rows),
                component["expected_stored_bytes"],
            )
            self.assertEqual(
                sha256_bytes(canonical_json_bytes(rows)),
                component["expected_inventory_sha256"],
            )
        rows = build_source_inventory(repository_root=ROOT, source_roots=self.roots)
        identity = self.config["full_dataset_identity"]
        self.assertEqual(len(self.roots), identity["root_count"])
        self.assertEqual(len(rows), identity["file_count"])
        self.assertEqual(sum(int(row["bytes"]) for row in rows), identity["stored_bytes"])
        self.assertEqual(
            sha256_bytes(canonical_json_bytes(rows)),
            identity["source_inventory_sha256"],
        )

    def test_archive_is_deterministic_and_outcome_blind(self) -> None:
        first, first_manifest = build_archive_bytes(
            repository_root=ROOT,
            source_roots=self.roots,
            atom_id=self.config["atom_id"],
        )
        second, second_manifest = build_archive_bytes(
            repository_root=ROOT,
            source_roots=self.roots,
            atom_id=self.config["atom_id"],
        )
        self.assertEqual(first, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertFalse(self.config["full_dataset_identity"]["outcome_values_read"])
        self.assertEqual(first_manifest["file_count"], 91)

    def test_drive_authority_is_create_only_and_bounded(self) -> None:
        authority = self.config["authority"]
        self.assertEqual(authority["drive_reads_max"], 8)
        self.assertEqual(authority["drive_writes_max"], 1)
        self.assertEqual(authority["drive_file_creations_max"], 1)
        for key in (
            "drive_updates",
            "drive_deletions",
            "sharing_changes",
            "provider_api_rpc_wss_calls",
            "provider_credits",
            "cash_spend_usd_cents",
            "credential_or_permission_changes",
            "candidate_admissions",
            "collector_executions",
            "wallet_signer_transaction_actions",
        ):
            self.assertEqual(authority[key], 0, key)
        for key in (
            "catalog_mutation",
            "source_mutation",
            "commit",
            "push",
            "pull_request",
            "merge",
            "destructive_actions",
        ):
            self.assertFalse(authority[key], key)

    def test_contract_preserves_remote_proof_boundary(self) -> None:
        text = " ".join(CONTRACT_PATH.read_text(encoding="utf-8").split())
        for required in (
            "13 source roots, 91 files",
            "Drive metadata read-back",
            "Raw-byte read-back",
            "independently downloaded bytes",
            "zero source mutation or deletion",
            "does not open hypothesis outcomes",
            "does not",
            "authorize TASK-22",
        ):
            self.assertIn(required, text)

    def test_acceptance_binds_remote_bytes_and_isolated_restore(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS_REMOTE_RECOVERY_PROVEN")
        self.assertTrue(receipt["google_drive"]["raw_readback"]["complete_byte_identity"])
        self.assertEqual(receipt["isolated_restore"]["restored_file_count"], 91)
        self.assertEqual(receipt["isolated_restore"]["restored_stored_bytes"], 1263895)
        self.assertTrue(receipt["isolated_restore"]["source_unchanged"])
        self.assertEqual(receipt["actual_actions"]["drive_file_creations"], 1)
        self.assertEqual(receipt["actual_actions"]["drive_updates"], 0)
        self.assertEqual(receipt["actual_actions"]["drive_deletions"], 0)
        self.assertFalse(receipt["next_boundary"]["authorized"])

    def test_acceptance_artifact_hashes_and_zero_forbidden_actions(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        for artifact in receipt["artifacts"]:
            self.assertEqual(sha256_file(ROOT / artifact["path"]), artifact["sha256"])
        actions = receipt["actual_actions"]
        for key in (
            "provider_api_rpc_wss_calls",
            "provider_credits",
            "cash_spend_usd_cents",
            "credential_or_permission_changes",
            "candidate_admissions",
            "collector_executions",
            "wallet_signer_transaction_actions",
            "commit",
            "push",
            "pull_request",
            "merge",
            "destructive_actions",
        ):
            value = actions[key]
            self.assertFalse(value) if isinstance(value, bool) else self.assertEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
