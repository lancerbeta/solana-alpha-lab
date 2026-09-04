"""Semantic proofs for the 97d storage architecture research/design atom."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRD = ROOT / "docs" / "architecture" / "FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md"
READOUT = (
    ROOT
    / "docs"
    / "reports"
    / "factory_97d_storage_architecture_proof_v1"
    / "a1_owner_readout_v1.md"
)
FORENSICS = (
    ROOT
    / "docs"
    / "evidence"
    / "factory_97d_storage_architecture_proof_v1"
    / "a1_live_byte_forensics_v1.json"
)
MODEL = (
    ROOT
    / "docs"
    / "evidence"
    / "factory_97d_storage_architecture_proof_v1"
    / "a1_structural_97d_model_v1.json"
)
ADOPT = (
    ROOT
    / "docs"
    / "evidence"
    / "factory_97d_storage_architecture_proof_v1"
    / "a1_adopt_wrap_decision_v1.json"
)
POLICY = ROOT / "delivery-harness" / "policies" / "solana-alpha-lab.md"
OFFHOST = ROOT / "src" / "solana_alpha_lab" / "factory" / "offhost_backup.py"
PUBLISHER = ROOT / "src" / "solana_alpha_lab" / "factory" / "observation_panel_publisher.py"


class Factory97dStorageArchitectureProofTests(unittest.TestCase):
    def test_terminal_is_blocked_and_does_not_claim_capacity_pass(self) -> None:
        prd = PRD.read_text(encoding="utf-8")
        readout = READOUT.read_text(encoding="utf-8")
        self.assertIn("STORAGE_ARCHITECTURE_BLOCKED", prd)
        self.assertIn("STORAGE_ARCHITECTURE_BLOCKED", readout)
        self.assertIn("canonical content = immutable forever", prd)
        self.assertIn("hot local residency = 90d", prd)
        self.assertIn("cold durability = indefinite", prd)
        self.assertNotIn("pass 40 gib: yes", readout.lower())
        self.assertIn("HOST_UNREACHABLE", readout)
        forensics = json.loads(FORENSICS.read_text(encoding="utf-8"))
        self.assertEqual(forensics["this_atom_live_probe"]["status"], "HOST_UNREACHABLE")
        self.assertFalse(forensics["credential_values_read"])
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        self.assertIsNone(model["pass_target_40_gib"])
        self.assertIsNone(model["pass_hard_50_gib"])
        self.assertEqual(model["capacity_horizon_days"], 97)
        self.assertEqual(model["terminal_gate"], "STORAGE_ARCHITECTURE_BLOCKED")

    def test_selected_architecture_rejects_new_platforms_and_size_only_verify(self) -> None:
        prd = PRD.read_text(encoding="utf-8")
        adopt = json.loads(ADOPT.read_text(encoding="utf-8"))
        by_name = {row["candidate"]: row["decision"] for row in adopt["decisions"]}
        self.assertEqual(by_name["pyarrow_parquet_zstd_batching"], "WRAP")
        self.assertEqual(by_name["duckdb_multi_file_parquet"], "WRAP")
        self.assertEqual(by_name["rclone_drive_sha256"], "ADOPT")
        self.assertEqual(by_name["apache_iceberg_delta_hudi"], "REJECT")
        self.assertEqual(by_name["minio_gcs_s3_new_cloud"], "REJECT")
        self.assertEqual(by_name["current_sqlite_plus_rdp_unchanged"], "REJECT")
        self.assertIn("FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1", prd)
        self.assertIn("REMOTE_CONTENT_SHA256_VERIFIED", prd)
        self.assertIn("Never use filesystem mtime", prd)
        offhost = OFFHOST.read_text(encoding="utf-8")
        self.assertIn("OFFHOST_REMOTE_IDENTITY_CONFLICT", offhost)
        self.assertIn('int(existing["bytes"])', offhost)
        self.assertIn("rclone hashsum sha256", prd)
        self.assertIn("--download", prd)

    def test_does_not_silently_reinterpret_immutable_or_bloat_sqlite(self) -> None:
        prd = PRD.read_text(encoding="utf-8")
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("DATA_RESOLUTION_ECONOMY", policy)
        self.assertIn("Do **not** solve 90d RAW by `raw_retention_days` 31→90", prd)
        self.assertIn("hot_local_residency_days", prd)
        self.assertIn("SCIENTIFIC_RDP_LOCAL_EVICTION_FORBIDDEN_UNDER_CURRENT_IMMUTABLE_CONST", prd)
        self.assertIn("Never use the **minimum**", prd)
        self.assertIn("isolated temporary data_root", prd)
        self.assertIn("STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE", prd)
        publisher = PUBLISHER.read_text(encoding="utf-8")
        self.assertIn("pq.write_table(table, tmp)", publisher)
        self.assertNotIn("compression=", publisher.split("def _write_parquet", 1)[1][:400])
        self.assertIn("no architecture implementation", prd.lower())
        self.assertIn("Destructive eviction is a **later** gate", prd)
