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
    def test_terminal_is_ready_after_snapshot_plus_delta(self) -> None:
        prd = PRD.read_text(encoding="utf-8")
        readout = READOUT.read_text(encoding="utf-8")
        self.assertIn("Terminal of this atom: `STORAGE_97D_ARCHITECTURE_READY`", prd)
        self.assertIn("`STORAGE_97D_ARCHITECTURE_READY`", readout)
        self.assertNotIn(
            "Terminal of this atom: `STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE`",
            prd,
        )
        self.assertNotIn(
            "Terminal of this atom: `STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN`",
            prd,
        )
        self.assertNotIn("Terminal of this atom: `STORAGE_ARCHITECTURE_BLOCKED`", prd)
        self.assertIn("SNAPSHOT_PLUS_DELTA", prd)
        self.assertIn("canonical content = immutable forever", prd)
        self.assertIn("hot local residency = 90d", prd)
        self.assertIn("cold durability = indefinite", prd)
        self.assertIn("HOST_UNREACHABLE", readout)
        self.assertIn("NOT_OBSERVED_AFTER_HOST_UNREACHABLE", readout)
        forensics = json.loads(FORENSICS.read_text(encoding="utf-8"))
        self.assertEqual(forensics["this_atom_live_probe"]["status"], "POST_REBOOT_COHERENT")
        self.assertFalse(forensics["credential_values_read"])
        self.assertFalse(forensics["this_atom_live_probe"]["factory_data_mutated_by_this_atom"])
        self.assertEqual(
            forensics["historical_host_unreachable_probe"]["status"],
            "HOST_UNREACHABLE",
        )
        self.assertEqual(
            forensics["historical_host_unreachable_probe"]["factory_data_mutated"],
            "NOT_OBSERVED_AFTER_HOST_UNREACHABLE",
        )
        self.assertTrue(forensics["byte_attribution"]["backup_sink"]["same_st_dev_as_factory"])
        self.assertFalse(
            forensics["post_reboot_health"]["scientific_rdp_vs_14_17z"][
                "unexpected_loss_or_rollback"
            ]
        )
        overlap = forensics["byte_attribution"]["poll_slots_overlap"]
        self.assertEqual(overlap["poll_exact_payload_sha256_in_call"], 1286)
        self.assertEqual(overlap["poll_exact_payload_sha256_not_in_call"], 0)
        self.assertEqual(overlap["poll_nonoverlap_payload_bytes"], 0)
        self.assertEqual(overlap["decision"], "DEDUPE_KEEP")
        layout = forensics["byte_attribution"]["members_layout_probe"]
        self.assertEqual(layout["selected"], "SNAPSHOT_PLUS_DELTA")
        self.assertEqual(layout["reconstruction"]["2026-09-02"]["exact_ok"], 258)
        self.assertEqual(layout["reconstruction"]["2026-09-03"]["exact_ok"], 121)
        self.assertEqual(layout["snapshot_plus_delta_zstd3_bytes"]["2026-09-02"], 4909476)
        self.assertEqual(layout["snapshot_plus_delta_zstd3_bytes"]["2026-09-03"], 7119972)
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        self.assertEqual(model["schema_version"], "1.3")
        self.assertEqual(model["selected_members_layout"], "SNAPSHOT_PLUS_DELTA")
        self.assertTrue(model["pass_target_40_gib"])
        self.assertTrue(model["pass_hard_50_gib"])
        self.assertTrue(model["pass_target_40_gib_conservative_stress"])
        self.assertEqual(model["capacity_horizon_days"], 97)
        self.assertEqual(model["terminal_gate"], "STORAGE_97D_ARCHITECTURE_READY")
        self.assertEqual(model["TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D"], 5333085386)
        self.assertEqual(model["typical_mutable_local_backup_peak_bytes"], 1912711645)
        self.assertGreater(model["typical_mutable_local_backup_peak_bytes"], 0)
        self.assertLessEqual(
            model["TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D"],
            model["target_bytes"],
        )
        stress = model["conservative_measured_stress"]
        self.assertEqual(stress["total_97d_bytes"], 7539689255)
        self.assertEqual(stress["members_snapshot_plus_delta_day_bytes"], 7119972)
        self.assertEqual(stress["mutable_local_backup_peak_bytes"], 2759403096)
        self.assertEqual(stress["unarchived_tail_durability_bytes"], 20127063)
        self.assertLessEqual(stress["total_97d_bytes"], model["hard_bytes"])
        self.assertEqual(stress["margin_to_hard_50_bytes"], 46147401945)
        self.assertTrue(stress["pass_hard_50_gib"])
        pub = model["publication_rate"]
        self.assertEqual(pub["status"], "BOUNDED")
        self.assertEqual(pub["stress_publications_per_day"], 258)
        self.assertEqual(pub["n_clean_full_utc_days"], 2)
        self.assertNotIn("2026-09-04", pub["healthy_full_utc_days_used"])
        poll = model["poll_slots_overlap"]
        self.assertEqual(poll["poll_exact_payload_sha256_in_call"], 1286)
        self.assertEqual(poll["poll_nonoverlap_payload_bytes"], 0)
        self.assertEqual(poll["decision"], "DEDUPE_KEEP")
        self.assertIn("PRIMARY_HOT_97D + MUTABLE_LOCAL_BACKUP_PEAK", model["formulas"]["TOTAL_97D"])
        self.assertEqual(model["members_layout"]["typical_members_day_bytes"], 6014724)

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
