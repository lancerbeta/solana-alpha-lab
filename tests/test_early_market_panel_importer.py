from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    LABELS_RELATIVE,
    MANIFEST_RELATIVE,
    MIN_USABLE_YIELD_ELIGIBLE,
    REQUIRED_LABELS,
    PUBLISHED_RELATIVE,
    SAMPLE_INVALID,
    SAMPLE_VALID,
    import_early_market_panel,
    inspect_canonical_targets,
    load_bound_panel,
)

FIXTURE = ROOT / "tests/fixtures/early_market_panel/temp_capture_v1"


def write_temp_capture(
    dest: Path,
    *,
    eligible: int,
    observed_at: str = "2026-08-24T00:24:22Z",
    extra_missing: int = 0,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for index in range(eligible):
        rows.append(
            {
                "id": f"Mint{index:039d}",
                "liquidity": 2800.0,
                "mcap": 2600.0,
                "usdPrice": 0.001,
                "updatedAt": "2026-08-24T00:24:16.000Z",
                "firstPool": {"id": f"pool{index}", "createdAt": "2026-08-24T00:19:15Z"},
                "stats5m": {"buyVolume": 100.0 + index, "sellVolume": 50.0},
            }
        )
    for index in range(extra_missing):
        rows.append(
            {
                "id": f"Miss{index:039d}",
                "liquidity": 1000.0,
                "mcap": 1000.0,
                "usdPrice": 0.001,
                "updatedAt": "2026-08-24T00:24:16.000Z",
                "firstPool": {"id": f"miss{index}", "createdAt": "2026-08-24T00:19:15Z"},
                "stats5m": {},
            }
        )
    body = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    (dest / "DISCOVERY_SEARCH_R0.body").write_bytes(body)
    envelope = {
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "observation_id": "DISCOVERY:SEARCH_R0",
        "observed_at": observed_at,
        "provider_calls": 0,
        "source_kind": "TEMP_FIXTURE",
    }
    envelope_bytes = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (dest / "DISCOVERY_SEARCH_R0.envelope.json").write_bytes(envelope_bytes)
    receipt = {
        "atom_id": "EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1",
        "schema": "smial.early-market-panel-temp-source-receipt",
        "schema_version": "1.0",
        "provider_requests": 0,
        "raw_retention": {
            "manifests": [
                {
                    "bytes": len(body),
                    "capture_envelope_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
                    "envelope_path": "DISCOVERY_SEARCH_R0.envelope.json",
                    "observation_id": "DISCOVERY:SEARCH_R0",
                    "observed_at": observed_at,
                    "path": "DISCOVERY_SEARCH_R0.body",
                    "retention": "A4_OUTSIDE_GIT",
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ]
        },
    }
    (dest / "source_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
            self.assertEqual(first["dataset_terminal"], SAMPLE_INVALID)
            self.assertFalse(first["feature_usable"])
            self.assertEqual(first["yield_eligible"], 1)
            self.assertLess(first["yield_eligible"], MIN_USABLE_YIELD_ELIGIBLE)
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
            self.assertFalse(bound["feature_usable"])

    def test_ten_eligible_rows_are_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_temp_capture(source, eligible=10)
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            result = import_early_market_panel(
                source_root=source,
                data_root=data_root,
                source_receipt_path=source / "source_receipt.json",
            )
            self.assertEqual(result["status"], "IMPORTED")
            self.assertEqual(result["dataset_terminal"], SAMPLE_VALID)
            self.assertTrue(result["feature_usable"])
            self.assertGreaterEqual(result["yield_eligible"], 10)

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

    def test_dataset_invisible_until_publish_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(first["status"], "IMPORTED")
            marker = data_root / PUBLISHED_RELATIVE
            payload = marker.read_bytes()
            marker.unlink()
            self.assertIsNone(load_bound_panel(data_root))
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "PARTIAL")
            marker.write_bytes(payload)
            bound = load_bound_panel(data_root)
            assert bound is not None
            self.assertEqual(bound["dataset_fingerprint"], first["dataset_fingerprint"])

    def test_injected_failure_before_publication_leaves_destination_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            before = {path.name: path.stat().st_mtime_ns for path in data_root.rglob("*") if path.is_file()}

            def fail() -> None:
                raise EarlyMarketPanelImportError("INJECTED_PUBLICATION_FAILURE")

            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=FIXTURE,
                    data_root=data_root,
                    source_receipt_path=FIXTURE / "source_receipt.json",
                    publication_hook=fail,
                )
            self.assertEqual(str(raised.exception), "INJECTED_PUBLICATION_FAILURE")
            self.assertIsNone(load_bound_panel(data_root))
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")
            after = {path.name: path.stat().st_mtime_ns for path in data_root.rglob("*") if path.is_file()}
            self.assertEqual(after, before)
            leftovers = list(data_root.parent.glob(".rdp.panel-import-*"))
            self.assertEqual(leftovers, [])

    def test_partial_existing_target_is_denied_and_bytes_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            labels = data_root / LABELS_RELATIVE
            original = labels.read_bytes()
            labels.unlink()
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=FIXTURE,
                    data_root=data_root,
                    source_receipt_path=FIXTURE / "source_receipt.json",
                )
            self.assertEqual(str(raised.exception), "EXISTING_TARGET_PARTIAL")
            manifest = data_root / MANIFEST_RELATIVE
            self.assertTrue(manifest.is_file())
            labels.write_bytes(original)
            bound = load_bound_panel(data_root)
            assert bound is not None
            self.assertEqual(bound["dataset_fingerprint"], first["dataset_fingerprint"])

    def test_corrupt_existing_target_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            labels = data_root / LABELS_RELATIVE
            original = labels.read_bytes()
            labels.write_bytes(b"{not-json")
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=FIXTURE,
                    data_root=data_root,
                    source_receipt_path=FIXTURE / "source_receipt.json",
                )
            self.assertEqual(str(raised.exception), "EXISTING_TARGET_CORRUPT")
            self.assertEqual(labels.read_bytes(), b"{not-json")
            labels.write_bytes(original)

    def test_repo_and_source_overlap_denied_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = ROOT / "tmp-hfic-overlap-should-not-exist"
            if data_root.exists():
                shutil.rmtree(data_root)
            with self.assertRaises(EarlyMarketPanelImportError) as raised:
                import_early_market_panel(
                    source_root=FIXTURE,
                    data_root=data_root,
                    source_receipt_path=FIXTURE / "source_receipt.json",
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INSIDE_GIT")
            self.assertFalse(data_root.exists())
            overlap_root = Path(tmp) / "overlap"
            shutil.copytree(FIXTURE, overlap_root)
            with self.assertRaises(EarlyMarketPanelImportError) as raised_overlap:
                import_early_market_panel(
                    source_root=overlap_root,
                    data_root=overlap_root,
                    source_receipt_path=overlap_root / "source_receipt.json",
                )
            self.assertEqual(str(raised_overlap.exception), "SOURCE_DATA_ROOT_OVERLAP")

    def test_symlink_data_root_denied_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "link"
            data_root.mkdir()
            original_is_symlink = Path.is_symlink

            def synthetic_symlink(path: Path) -> bool:
                try:
                    if path.resolve() == data_root.resolve():
                        return True
                except OSError:
                    pass
                return original_is_symlink(path)

            with patch.object(Path, "is_symlink", synthetic_symlink):
                with self.assertRaises(EarlyMarketPanelImportError) as raised:
                    import_early_market_panel(
                        source_root=FIXTURE,
                        data_root=data_root,
                        source_receipt_path=FIXTURE / "source_receipt.json",
                    )
                self.assertEqual(str(raised.exception), "DATA_ROOT_SYMLINK")
            self.assertEqual(inspect_canonical_targets(data_root)["state"], "ABSENT")

    def test_invalid_and_missing_observed_at_denied(self) -> None:
        cases = [
            ("", "OBSERVED_AT_MISSING"),
            ("2026-08-24 00:24:22", "OBSERVED_AT_INVALID"),
            ("2026-08-24T00:24:22", "OBSERVED_AT_NAIVE"),
            ("2020-01-01T00:00:00Z", "OBSERVED_AT_OUT_OF_WINDOW"),
        ]
        for observed_at, code in cases:
            with self.subTest(observed_at=observed_at, code=code):
                with tempfile.TemporaryDirectory() as tmp:
                    source = Path(tmp) / "source"
                    write_temp_capture(source, eligible=1, observed_at=observed_at)
                    if observed_at == "":
                        envelope = json.loads(
                            (source / "DISCOVERY_SEARCH_R0.envelope.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        del envelope["observed_at"]
                        body = json.dumps(
                            envelope,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        (source / "DISCOVERY_SEARCH_R0.envelope.json").write_bytes(body)
                        receipt = json.loads(
                            (source / "source_receipt.json").read_text(encoding="utf-8")
                        )
                        receipt["raw_retention"]["manifests"][0]["capture_envelope_sha256"] = (
                            hashlib.sha256(body).hexdigest()
                        )
                        receipt["raw_retention"]["manifests"][0]["observed_at"] = None
                        (source / "source_receipt.json").write_text(
                            json.dumps(receipt, indent=2) + "\n",
                            encoding="utf-8",
                        )
                    data_root = Path(tmp) / "rdp"
                    data_root.mkdir()
                    with self.assertRaises(EarlyMarketPanelImportError) as raised:
                        import_early_market_panel(
                            source_root=source,
                            data_root=data_root,
                            source_receipt_path=source / "source_receipt.json",
                        )
                    self.assertEqual(str(raised.exception), code)
                    self.assertIsNone(load_bound_panel(data_root))


if __name__ == "__main__":
    unittest.main()
