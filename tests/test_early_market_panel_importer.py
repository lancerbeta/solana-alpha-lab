from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.early_market_panel_field_semantics import (
    FIELD_SEMANTICS_TERMINAL,
    FIELD_SEMANTICS_UNPROVEN,
    FieldSemanticsError,
    prove_r0_taker_volume_mix_semantics,
)
from solana_alpha_lab.factory.early_market_panel_importer import (
    DATASET_MANIFEST_ID,
    EarlyMarketPanelImportError,
    FEATURE_ID,
    FORBIDDEN_HYPOTHESIS_ID,
    REQUIRED_LABELS,
    import_early_market_panel,
    load_bound_panel,
)

FIXTURE = ROOT / "tests/fixtures/early_market_panel/temp_capture_v1"


class FieldSemanticsTests(unittest.TestCase):
    def test_r0_ratio_is_proven_and_r1_is_rejected(self) -> None:
        rows = json.loads((FIXTURE / "DISCOVERY_SEARCH_R0.body").read_text(encoding="utf-8"))
        proof = prove_r0_taker_volume_mix_semantics(
            rows, x_source_observation="DISCOVERY:SEARCH_R0"
        )
        self.assertEqual(proof["terminal"], FIELD_SEMANTICS_TERMINAL)
        self.assertEqual(proof["ratio_unit"], "DIMENSIONLESS_UNIT_INTERVAL")
        self.assertEqual(proof["raw_volume_unit_status"], "OFFICIAL_UNANNOTATED")
        self.assertTrue(proof["x_uses_r0_only"])
        self.assertGreaterEqual(proof["yield_eligible"], 1)
        with self.assertRaises(FieldSemanticsError) as raised:
            prove_r0_taker_volume_mix_semantics(
                rows, x_source_observation="DISCOVERY:SEARCH_R1"
            )
        self.assertEqual(str(raised.exception), FIELD_SEMANTICS_UNPROVEN)


class ImporterTests(unittest.TestCase):
    def test_import_is_idempotent_and_labels_discovery_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(first["status"], "IMPORTED")
            self.assertEqual(first["dataset_manifest_id"], DATASET_MANIFEST_ID)
            self.assertEqual(first["provider_calls_actual"], 0)
            self.assertTrue(first["epoch_material_changed"])
            self.assertEqual(first["labels"]["evidence_role"], "DISCOVERY_ONLY_SECOND_LOOK")
            self.assertTrue(first["labels"]["outcome_previously_consumed"])
            self.assertTrue(first["labels"]["confirmatory_reuse_forbidden"])
            self.assertEqual(first["labels"]["provider_calls_for_bind"], 0)
            self.assertIsNone(first["labels"]["accepted_hypothesis_id"])
            self.assertEqual(first["labels"]["feature_hint"], FEATURE_ID)
            self.assertEqual(first["labels"]["forbidden_hypothesis_id"], FORBIDDEN_HYPOTHESIS_ID)
            self.assertNotIn("tau_b", json.dumps(first))
            self.assertNotIn(FORBIDDEN_HYPOTHESIS_ID, first["dataset_manifest_id"])
            second = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(second["status"], "IDEMPOTENT_REUSE")
            self.assertEqual(second["dataset_fingerprint"], first["dataset_fingerprint"])
            self.assertEqual(second["row_count"], first["row_count"])
            self.assertFalse(second["epoch_material_changed"])
            bound = load_bound_panel(data_root)
            assert bound is not None
            for key, expected in REQUIRED_LABELS.items():
                self.assertEqual(bound["labels"][key], expected)

    def test_hash_corruption_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            shutil.copytree(FIXTURE, source)
            body = source / "DISCOVERY_SEARCH_R0.body"
            payload = body.read_bytes()
            body.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0x01]))
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=source,
                    data_root=data_root,
                    source_receipt_path=source / "source_receipt.json",
                )
            self.assertEqual(str(raised.exception), "R0_BODY_HASH_MISMATCH")
            self.assertIsNone(load_bound_panel(data_root))

    def test_source_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EarlyMarketPanelImportError):
                import_early_market_panel(
                    source_root=Path(tmp) / "missing",
                    data_root=Path(tmp) / "rdp",
                    source_receipt_path=FIXTURE / "source_receipt.json",
                )


if __name__ == "__main__":
    unittest.main()
