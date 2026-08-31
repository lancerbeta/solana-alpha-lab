"""Vertical zero-network Discovery Evidence Release Bridge proof."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.discovery_evidence_release import (  # noqa: E402
    DATASET_MANIFEST_ID,
    DiscoveryReleaseError,
    HISTORICAL_EVIDENCE_ROLE,
    import_discovery_release,
    load_source_inventory,
    seal_discovery_release,
    verify_discovery_release,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    assert_capability_registry_v2_superset,
    build_forge_context_packet,
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from solana_alpha_lab.factory.observation_scheduler import _row_field  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.tokens_v2_typed_projection import (  # noqa: E402
    project_tokens_v2_row,
    project_tokens_v2_scalar,
)

FIXTURE = ROOT / "tests/fixtures/early_market_panel/temp_capture_v1"
BODY = FIXTURE / "DISCOVERY_SEARCH_R0.body"
ENVELOPE = FIXTURE / "DISCOVERY_SEARCH_R0.envelope.json"
RECEIPT = FIXTURE / "source_receipt.json"
IMPORT_AT = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
SEAL_AT = datetime(2026, 9, 1, 11, 0, 0, tzinfo=UTC)


class DiscoveryEvidenceReleaseBridgeTests(unittest.TestCase):
    def test_schedule_preserves_excluded_ambiguous_state(self) -> None:
        from solana_alpha_lab.factory.observation_scheduler import (
            _typed_observation_values,
        )

        values = {
            item["field_id"]: item
            for item in _typed_observation_values(
                claim={
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "point_id": "X300",
                    "event_time": "2026-09-01T00:05:00Z",
                    "first_reliable_available_at": "2026-09-01T00:05:07Z",
                    "request_sha256": "a" * 64,
                    "call_occurrence_id": "b" * 64,
                },
                state="OBSERVED",
                response_payload={
                    "id": "MintZ",
                    "fdv": 99.0,
                    "stats5m": {"buyVolume": 1.0, "sellVolume": 1.0},
                },
                buy_out=None,
                missing_reason=None,
            )
        }
        self.assertEqual(
            values["FIELD-MARKET-CAP-USD-001"]["state"], "EXCLUDED_AMBIGUOUS"
        )
        self.assertEqual(
            values["FIELD-MARKET-CAP-USD-001"]["missing_reason"],
            "FDV_NOT_MARKET_CAP",
        )
        self.assertEqual(
            values["FIELD-STATS5M-TAKER-VOLUME-001"]["state"],
            "EXCLUDED_AMBIGUOUS",
        )
        proof = assert_capability_registry_v2_superset(ROOT)
        self.assertEqual(
            proof["intentional_v2_additions"],
            ["CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"],
        )
        self.assertEqual(
            proof["active_registry"],
            "configs/experiment_capability_registry_v2.yaml",
        )

    def test_replay_and_schedule_projection_match_on_fixture_row(self) -> None:
        rows = json.loads(BODY.read_text(encoding="utf-8"))
        row = rows[0]
        typed = project_tokens_v2_row(row)
        for item in typed:
            field_id = item["field_id"]
            scalar = project_tokens_v2_scalar(row, field_id)
            schedule = _row_field(row, field_id)
            if item["state"] == "OBSERVED":
                self.assertEqual(scalar, schedule)
                self.assertEqual(item["typed_value_or_null"], scalar)
            else:
                self.assertIsNone(scalar)
                self.assertIsNone(schedule)

    def test_vertical_seal_import_hfic_epoch_and_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            release_root = tmp_path / "release"
            data_root = tmp_path / "rdp"
            data_root.mkdir()
            epoch_before = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            inventory = load_source_inventory(
                body_path=BODY,
                envelope_path=ENVELOPE,
                source_receipt_path=RECEIPT,
            )
            sealed = seal_discovery_release(
                inventory=inventory,
                release_root=release_root,
                sealed_at=SEAL_AT,
            )
            verified = verify_discovery_release(release_root)
            self.assertEqual(sealed["release_id"], verified["release_id"])
            self.assertIn("PRICE_PATH", sealed["feature_families"])
            self.assertIn("ACTIVITY_VOLUME", sealed["feature_families"])
            self.assertEqual(sealed["evidence_role"], HISTORICAL_EVIDENCE_ROLE)
            self.assertTrue(sealed["confirmatory_reuse_forbidden"])

            # Partial release (no manifest) is invisible.
            partial = tmp_path / "partial"
            partial.mkdir()
            shutil.copy2(release_root / "census.parquet", partial / "census.parquet")
            with self.assertRaises(DiscoveryReleaseError) as raised:
                verify_discovery_release(partial)
            self.assertEqual(str(raised.exception), "RELEASE_PARTIAL_OR_MISSING_MANIFEST")

            imported = import_discovery_release(
                release_root=release_root,
                data_root=data_root,
                import_time=IMPORT_AT,
            )
            # Idempotent re-import of identical bytes.
            again = import_discovery_release(
                release_root=release_root,
                data_root=data_root,
                import_time=IMPORT_AT,
            )
            self.assertEqual(imported["dataset_fingerprint"], again["dataset_fingerprint"])

            datasets, warnings = enumerate_rdp_datasets(data_root)
            self.assertEqual(warnings, [])
            self.assertEqual(len(datasets), 1)
            entry = datasets[0]
            self.assertEqual(entry["dataset_manifest_id"], DATASET_MANIFEST_ID)
            self.assertEqual(entry["evidence_role"], HISTORICAL_EVIDENCE_ROLE)
            self.assertIn("PRICE_PATH", entry["feature_families"])
            self.assertIn("VALUATION", entry["feature_families"])
            self.assertTrue(
                entry["labels"]["confirmatory_reuse_forbidden"]
            )
            # Event time does not become Forge availability.
            self.assertEqual(
                entry["labels"]["source_observed_at"],
                "2026-08-24T00:24:22Z",
            )
            self.assertEqual(entry["labels"]["imported_at"], "2026-09-01T12:00:00Z")

            epoch_after = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            self.assertNotEqual(epoch_before, epoch_after)

            store = ResearchStore(data_root)
            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch=epoch_after,
                search_key="0" * 64,
                commissioning_status="NO_GIT_FAST_LANE_PROVEN",
                research_memory_as_of="2026-09-01T12:00:00Z",
                store=store,
                stage_time=IMPORT_AT,
            )
            family_ids = [item["feature_family"] for item in packet["feature_families"]]
            self.assertIn("PRICE_PATH", family_ids)
            self.assertIn("ACTIVITY_VOLUME", family_ids)
            self.assertTrue(
                any(
                    item.get("confirmatory_reuse_forbidden")
                    for item in packet["feature_families"]
                )
            )
            # Closed families stay present; release is not a confirmation surface.
            self.assertTrue(packet["closed_family_ledger"])
            self.assertIn(
                "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
                packet["capability_ids"],
            )

    def test_conflicting_bytes_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            release_root = tmp_path / "release"
            data_root = tmp_path / "rdp"
            data_root.mkdir()
            inventory = load_source_inventory(
                body_path=BODY,
                envelope_path=ENVELOPE,
                source_receipt_path=RECEIPT,
            )
            seal_discovery_release(
                inventory=inventory,
                release_root=release_root,
                sealed_at=SEAL_AT,
            )
            import_discovery_release(
                release_root=release_root,
                data_root=data_root,
                import_time=IMPORT_AT,
            )
            # Corrupt one published parquet after import path settled.
            published = next((data_root / "datasets" / "partitions").rglob("*.parquet"))
            published.write_bytes(b"not-the-same-bytes")
            with self.assertRaises(DiscoveryReleaseError) as raised:
                import_discovery_release(
                    release_root=release_root,
                    data_root=data_root,
                    import_time=IMPORT_AT,
                )
            self.assertEqual(str(raised.exception), "CANONICAL_TARGET_CONFLICT")

    def test_census_preserves_all_source_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_root = Path(tmp) / "release"
            inventory = load_source_inventory(
                body_path=BODY,
                envelope_path=ENVELOPE,
                source_receipt_path=RECEIPT,
            )
            sealed = seal_discovery_release(
                inventory=inventory,
                release_root=release_root,
                sealed_at=SEAL_AT,
            )
            self.assertEqual(sealed["census_row_count"], 3)
            self.assertEqual(inventory["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
