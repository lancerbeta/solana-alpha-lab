"""HOT90 IMPL: SNAPSHOT_PLUS_DELTA, verify, hydrate, eviction, admission, no production mutation."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hot90_activation import (  # noqa: E402
    STAGE_CURRENT_SAFE,
    STAGE_WRITE_ONLY_SHADOW,
    Hot90ActivationError,
    load_hot90_activation,
)
from solana_alpha_lab.factory.hot90_archive import (  # noqa: E402
    Hot90ArchiveError,
    hydrate_closed_day_archive,
    package_closed_day_archive,
    reconstruct_members_from_hydrated,
)
from solana_alpha_lab.factory.hot90_eviction import (  # noqa: E402
    EVICTION_FORBIDDEN,
    Hot90EvictionError,
    execute_exact_delete,
    plan_exact_eviction,
)
from solana_alpha_lab.factory.hot90_mutable_backup import mutable_backup_sources  # noqa: E402
from solana_alpha_lab.factory.hot90_remote_verify import (  # noqa: E402
    REMOTE_CONTENT_SHA256_VERIFIED,
    verify_remote_content_sha256,
)
from solana_alpha_lab.factory.offhost_backup import OffhostBackupError, OffhostConfig  # noqa: E402
from solana_alpha_lab.factory.hot90_sqlite_eligibility import (  # noqa: E402
    sqlite_body_compaction_eligible,
)
from solana_alpha_lab.factory.hot90_storage_admission import (  # noqa: E402
    HARD_BYTES,
    project_storage_runway,
)
from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    MembersDeltaError,
    append_delta_publication,
    load_member_rows_for_location,
    reconstruct_publication,
    snapshot_fingerprint,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    publish_observation_batch,
    rebuild_observation_panel_from_rdp,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    load_observation_schedule,
)
from solana_alpha_lab.factory.raw_evidence_plane import (  # noqa: E402
    extract_canonical_body,
    materialize_canonical_raw,
)

import pyarrow.parquet as pq  # noqa: E402


GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 2, 0, 10, tzinfo=UTC)


def _member(entity_id: str, state: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "schedule_sha256": "a" * 64,
        "activation_id": "ACT-1",
        "entity_id": entity_id,
        "membership_state": state,
        "event_time": "2026-09-02T00:05:00Z",
        "first_reliable_available_at": "2026-09-02T00:10:00Z",
        "field_values": [
            {
                "field_id": "F1",
                "value_kind": "STRING",
                "typed_value_or_null": extra.get("value"),
                "state": "OBSERVED" if extra.get("value") is not None else "MISSING",
                "missing_reason": None if extra.get("value") is not None else "UNAVAILABLE",
            }
        ],
    }
    row.update({key: value for key, value in extra.items() if key != "value"})
    return row


class FakeRun:
    def __init__(self, code: int, stdout: str = "") -> None:
        self.returncode = code
        self.stdout = stdout
        self.stderr = ""


class Hot90ActivationTests(unittest.TestCase):
    def test_default_current_safe_forbids_destructive_flags(self) -> None:
        loaded = load_hot90_activation(ROOT)
        self.assertEqual(loaded["activation_stage"], STAGE_CURRENT_SAFE)
        self.assertEqual(loaded["members_layout"], "LEGACY_PER_PUBLICATION")
        self.assertFalse(loaded["new_write_zstd"])
        with self.assertRaises(Hot90ActivationError):
            load_hot90_activation(
                ROOT,
                override={
                    "activation_stage": STAGE_CURRENT_SAFE,
                    "production_eviction_enabled": True,
                    "production_compaction_enabled": False,
                    "drive_writes_enabled": False,
                },
            )


class SnapshotPlusDeltaTests(unittest.TestCase):
    def test_reconstruct_added_removed_changed_and_identity(self) -> None:
        first = [_member("A", "INCLUDED", value="x"), _member("B", "INCLUDED", value="y")]
        second = [
            _member("A", "INCLUDED", value="x"),
            _member("C", "INCLUDED", value="z"),
            _member("B", "EXCLUDED", value="y2"),
        ]
        third = [_member("C", "INCLUDED", value="z"), _member("D", "INCLUDED", value="d")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            unit = write_snapshot_unit(
                data_root, utc_day="20260902", dataset_manifest_id="dataset-aaa", rows=first
            )
            unit = append_delta_publication(
                data_root, utc_day="20260902", dataset_manifest_id="dataset-bbb", rows=second
            )
            unit = append_delta_publication(
                data_root, utc_day="20260902", dataset_manifest_id="dataset-ccc", rows=third
            )
            got0 = reconstruct_publication(data_root, unit, "dataset-aaa")
            got1 = reconstruct_publication(data_root, unit, "dataset-bbb")
            got2 = reconstruct_publication(data_root, unit, "dataset-ccc")
            self.assertEqual(snapshot_fingerprint(got0), snapshot_fingerprint(first))
            self.assertEqual(snapshot_fingerprint(got1), snapshot_fingerprint(second))
            self.assertEqual(snapshot_fingerprint(got2), snapshot_fingerprint(third))
            self.assertEqual({row["entity_id"] for row in got1}, {"A", "B", "C"})
            self.assertEqual(
                next(row for row in got1 if row["entity_id"] == "B")["membership_state"],
                "EXCLUDED",
            )
            sidecar = data_root / unit["publications"][1]["rel"]
            loaded = load_member_rows_for_location(
                data_root, str(Path(unit["publications"][1]["rel"]).as_posix())
            )
            self.assertEqual(snapshot_fingerprint(loaded), snapshot_fingerprint(second))
            self.assertTrue(sidecar.with_name("members.layout.json").is_file())

    def test_fail_closed_missing_anchor_and_corrupt_delta(self) -> None:
        rows = [_member("A", "INCLUDED", value="x")]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.assertRaises(MembersDeltaError) as missing:
                append_delta_publication(
                    data_root, utc_day="20260902", dataset_manifest_id="dataset-bbb", rows=rows
                )
            self.assertEqual(str(missing.exception), "ANCHOR_MISSING")
            unit = write_snapshot_unit(
                data_root, utc_day="20260902", dataset_manifest_id="dataset-aaa", rows=rows
            )
            delta_path = data_root / unit["publications"][0]["rel"]
            # corrupt by rewriting unit sha
            unit["publications"][0]["sha256"] = "0" * 64
            with self.assertRaises(MembersDeltaError) as hashed:
                reconstruct_publication(data_root, unit, "dataset-aaa")
            self.assertEqual(str(hashed.exception), "DELTA_HASH_MISMATCH")
            self.assertTrue(delta_path.is_file())

    def test_legacy_per_publication_members_still_readable(self) -> None:
        rows = [_member("A", "INCLUDED", value="x")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "datasets" / "parquet" / "dataset-legacy" / "members.parquet"
            path.parent.mkdir(parents=True)
            import pyarrow as pa

            table = pa.Table.from_pylist(rows)
            pq.write_table(table, path)
            loaded = load_member_rows_for_location(
                Path(tmp), "datasets/parquet/dataset-legacy/members.parquet"
            )
            self.assertEqual(snapshot_fingerprint(loaded), snapshot_fingerprint(rows))

    def test_zstd_and_snappy_semantic_equality(self) -> None:
        rows = [_member("A", "INCLUDED", value="x"), _member("B", "EXCLUDED", value=None)]
        with tempfile.TemporaryDirectory() as tmp:
            snappy_path = Path(tmp) / "snappy.parquet"
            zstd_path = Path(tmp) / "zstd.parquet"
            import pyarrow as pa

            table = pa.Table.from_pylist(rows)
            pq.write_table(table, snappy_path)
            pq.write_table(table, zstd_path, compression="zstd", compression_level=3)
            self.assertEqual(
                pq.read_table(snappy_path).to_pylist(),
                pq.read_table(zstd_path).to_pylist(),
            )
            self.assertEqual(pq.read_metadata(zstd_path).row_group(0).column(0).compression, "ZSTD")
            self.assertEqual(
                pq.read_metadata(snappy_path).row_group(0).column(0).compression, "SNAPPY"
            )

    def test_deterministic_replay_same_fingerprint(self) -> None:
        rows = [_member("A", "INCLUDED", value="x"), _member("C", "INCLUDED", value="z")]
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"
            unit_a = write_snapshot_unit(
                first, utc_day="20260902", dataset_manifest_id="dataset-aaa", rows=rows
            )
            unit_b = write_snapshot_unit(
                second, utc_day="20260902", dataset_manifest_id="dataset-aaa", rows=rows
            )
            self.assertEqual(
                reconstruct_publication(first, unit_a, "dataset-aaa"),
                reconstruct_publication(second, unit_b, "dataset-aaa"),
            )
            self.assertEqual(
                unit_a["publications"][0]["snapshot_fingerprint"],
                unit_b["publications"][0]["snapshot_fingerprint"],
            )


class PublisherCompatibilityTests(unittest.TestCase):
    def test_current_safe_publish_keeps_snappy_and_rebuild(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            published = publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
                members=[{"schedule_sha256": digest, "entity_id": "MintA"}],
                observations=[
                    {
                        "schedule_sha256": digest,
                        "entity_id": "MintA",
                        "point_id": "X300",
                        "state": "OBSERVED",
                        "event_time": "2026-09-02T00:05:00Z",
                        "first_reliable_available_at": "2026-09-02T00:10:00Z",
                    }
                ],
            )
            member_path = next((data_root / "datasets" / "parquet").rglob("members.parquet"))
            compression = pq.read_metadata(member_path).row_group(0).column(0).compression
            self.assertEqual(compression, "SNAPPY")
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root, schedule_sha256=digest
            )
            self.assertEqual(rebuilt["dataset_manifest_ids"], [published["dataset_manifest_id"]])
            self.assertEqual(rebuilt["members"][0]["entity_id"], "MintA")

    def test_write_only_snapshot_plus_delta_round_trip(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        digest = schedule["schedule_sha256"]
        shadow = {
            "activation_stage": STAGE_WRITE_ONLY_SHADOW,
            "production_compaction_enabled": False,
            "production_eviction_enabled": False,
            "drive_writes_enabled": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            with patch(
                "solana_alpha_lab.factory.observation_panel_publisher.load_hot90_activation",
                return_value=load_hot90_activation(ROOT, override=shadow),
            ):
                first = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                    members=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "membership_state": "INCLUDED",
                        }
                    ],
                    observations=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "point_id": "X300",
                            "state": "OBSERVED",
                            "event_time": "2026-09-02T00:05:00Z",
                            "first_reliable_available_at": "2026-09-02T00:10:00Z",
                        }
                    ],
                )
                second = publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=datetime(2026, 9, 2, 0, 20, tzinfo=UTC),
                    producer_git_sha=GIT_SHA,
                    members=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintA",
                            "membership_state": "EXCLUDED",
                        },
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintB",
                            "membership_state": "INCLUDED",
                        },
                    ],
                    observations=[
                        {
                            "schedule_sha256": digest,
                            "entity_id": "MintB",
                            "point_id": "X300",
                            "state": "OBSERVED",
                            "event_time": "2026-09-02T00:15:00Z",
                            "first_reliable_available_at": "2026-09-02T00:20:00Z",
                        }
                    ],
                )
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root, schedule_sha256=digest
            )
            self.assertIn(first["dataset_manifest_id"], rebuilt["dataset_manifest_ids"])
            self.assertIn(second["dataset_manifest_id"], rebuilt["dataset_manifest_ids"])
            by_entity = {row["entity_id"]: row for row in rebuilt["members"]}
            self.assertEqual(by_entity["MintA"]["membership_state"], "EXCLUDED")
            self.assertEqual(by_entity["MintB"]["membership_state"], "INCLUDED")
            obs = next((data_root / "datasets" / "parquet").rglob("observations.parquet"))
            self.assertEqual(pq.read_metadata(obs).row_group(0).column(0).compression, "ZSTD")


class RawPlaneAndSqliteTests(unittest.TestCase):
    def test_materialize_and_extract_and_disabled_compaction(self) -> None:
        body = {"rows": [{"n": 1}]}
        digest = canonical_sha256(body)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            result = materialize_canonical_raw(
                data_root,
                utc_day="20260902",
                call_occurrence_id="CALL-1",
                request_sha256="b" * 64,
                response_sha256=digest,
                body=body,
                first_reliable_available_at="2026-09-02T00:10:00Z",
                event_time="2026-09-02T00:05:00Z",
                primitive_id="P1",
            )
            extracted = extract_canonical_body(data_root, result["occurrence"])
            self.assertEqual(canonical_sha256(json.loads(extracted.decode("utf-8"))), digest)
            gate = sqlite_body_compaction_eligible(
                call_state="COMPLETED",
                raw_materialized=True,
                extracted_sha256=digest,
                expected_response_sha256=digest,
                unresolved_recovery=False,
                publication_open=False,
                production_compaction_enabled=False,
            )
            self.assertFalse(gate["eligible"])
            self.assertEqual(gate["reason"], "PRODUCTION_COMPACTION_DISABLED")
            ok = sqlite_body_compaction_eligible(
                call_state="COMPLETED",
                raw_materialized=True,
                extracted_sha256=digest,
                expected_response_sha256=digest,
                unresolved_recovery=False,
                publication_open=False,
                production_compaction_enabled=True,
            )
            self.assertTrue(ok["eligible"])


class ArchiveHydrateVerifyEvictTests(unittest.TestCase):
    def test_archive_hydrate_verify_evict_fixture_only(self) -> None:
        rows = [_member("A", "INCLUDED", value="x")]
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live"
            isolated = Path(tmp) / "isolated"
            dest = Path(tmp) / "archives"
            live.mkdir()
            unit = write_snapshot_unit(
                live, utc_day="20260902", dataset_manifest_id="dataset-aaa", rows=rows
            )
            rel = str(unit["publications"][0]["rel"])
            sidecar_rel = str(Path(rel).with_name("members.layout.json").as_posix())
            unit_rel = "datasets/members_snapshot_plus_delta/20260902/unit.json"
            packed = package_closed_day_archive(
                live,
                utc_day="20260902",
                relative_paths=[rel, sidecar_rel, unit_rel],
                dest_dir=dest,
            )
            self.assertTrue(packed["filename"].startswith("ARCHIVE_"))
            hydrated = hydrate_closed_day_archive(
                packed["path"], isolated_data_root=isolated, live_data_root=live
            )
            self.assertTrue(hydrated["live_unchanged"])
            restored = reconstruct_members_from_hydrated(isolated, rel)
            self.assertEqual(snapshot_fingerprint(restored), snapshot_fingerprint(rows))
            digest = hashlib.sha256((live / rel).read_bytes()).hexdigest()
            config = OffhostConfig(
                remote_name="factory-gdrive",
                destination_root="solana-alpha-lab/factory-backups",
                rclone_config_absolute=Path(tmp) / "rclone.conf",
                rclone_bin=Path("/usr/bin/rclone"),
                receipt_relative="local/factory_v1/offhost_backup_receipt.json",
                freshness_current_max_seconds=86400,
                freshness_degraded_max_seconds=172800,
            )
            (Path(tmp) / "rclone.conf").write_text("[factory-gdrive]\ntype = drive\n", encoding="utf-8")

            def runner(argv: list[str]) -> FakeRun:
                if "hashsum" in argv and "--download" not in argv:
                    return FakeRun(0, f"{digest} ARCHIVE.bin\n")
                return FakeRun(1, "")

            verified = verify_remote_content_sha256(
                config=config,
                remote_object="factory-gdrive:solana-alpha-lab/factory-backups/ARCHIVE.bin",
                local_sha256=digest,
                runner=runner,
                root=ROOT,
                allow_drive=True,
            )
            self.assertEqual(verified["terminal"], REMOTE_CONTENT_SHA256_VERIFIED)
            with self.assertRaises(OffhostBackupError):
                verify_remote_content_sha256(
                    config=config,
                    remote_object="factory-gdrive:solana-alpha-lab/factory-backups/ARCHIVE.bin",
                    local_sha256=digest,
                    runner=runner,
                    root=ROOT,
                    allow_drive=False,
                )
            with self.assertRaises(Hot90EvictionError) as missing_clock:
                plan_exact_eviction(
                    root=ROOT,
                    retention={
                        "canonical_panel_retention": "IMMUTABLE",
                        "hot_local_residency_days": 90,
                    },
                    unit={
                        "terminal": "CLOSED",
                        "first_reliable_available_at": "2026-01-01T00:00:00Z",
                        "closed_at": "2026-01-01T00:00:00Z",
                    },
                    now=datetime(2026, 9, 5, tzinfo=UTC),
                    unresolved_call_or_due=False,
                    open_publication=False,
                    remote_verify_terminal=REMOTE_CONTENT_SHA256_VERIFIED,
                    source_paths=[rel],
                    data_root=live,
                    plan_hashes={rel: digest},
                    fixture_destructive=True,
                )
            self.assertEqual(str(missing_clock.exception), "AVAILABILITY_CLOCK_MISSING")
            with self.assertRaises(Hot90EvictionError) as forbidden:
                plan_exact_eviction(
                    root=ROOT,
                    retention={"canonical_panel_retention": "IMMUTABLE"},
                    unit={
                        "terminal": "CLOSED",
                        "first_reliable_available_at": "2026-01-01T00:00:00Z",
                        "max_available_to_strategy_at": "2026-01-01T00:00:00Z",
                        "closed_at": "2026-01-01T00:00:00Z",
                    },
                    now=datetime(2026, 9, 5, tzinfo=UTC),
                    unresolved_call_or_due=False,
                    open_publication=False,
                    remote_verify_terminal=REMOTE_CONTENT_SHA256_VERIFIED,
                    source_paths=[rel],
                    data_root=live,
                    plan_hashes={rel: digest},
                    fixture_destructive=True,
                )
            self.assertEqual(str(forbidden.exception), EVICTION_FORBIDDEN)
            planned = plan_exact_eviction(
                root=ROOT,
                retention={
                    "canonical_panel_retention": "IMMUTABLE",
                    "hot_local_residency_days": 90,
                },
                unit={
                    "terminal": "CLOSED",
                    "first_reliable_available_at": "2026-01-01T00:00:00Z",
                    "max_available_to_strategy_at": "2026-01-01T00:00:00Z",
                    "closed_at": "2026-01-01T00:00:00Z",
                },
                now=datetime(2026, 9, 5, tzinfo=UTC),
                unresolved_call_or_due=False,
                open_publication=False,
                remote_verify_terminal=REMOTE_CONTENT_SHA256_VERIFIED,
                source_paths=[rel],
                data_root=live,
                plan_hashes={rel: digest},
                fixture_destructive=True,
            )
            deleted = execute_exact_delete(
                data_root=live,
                exact_paths=planned["exact_paths"],
                plan_hashes={rel: digest},
                fixture_destructive=True,
            )
            self.assertEqual(deleted["deleted"], [rel])
            self.assertFalse((live / rel).exists())
            with self.assertRaises(Hot90EvictionError):
                execute_exact_delete(
                    data_root=live,
                    exact_paths=[rel],
                    plan_hashes={rel: digest},
                    fixture_destructive=False,
                )
            with self.assertRaises(Hot90EvictionError):
                execute_exact_delete(
                    data_root=live,
                    exact_paths=["../escape.bin"],
                    plan_hashes={"../escape.bin": "0" * 64},
                    fixture_destructive=True,
                )

    def test_hydrate_rejects_parent_path_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live"
            isolated = Path(tmp) / "isolated"
            live.mkdir()
            isolated.mkdir()
            marker = live / "keep.bin"
            marker.write_bytes(b"keep")
            zip_path = Path(tmp) / "bad.zip"
            entries = [{"path": "../escape.bin", "sha256": hashlib.sha256(b"x").hexdigest(), "bytes": 1}]
            from solana_alpha_lab.factory.observation_schedule import canonical_sha256

            manifest = {
                "kind": "FACTORY_HOT90_CLOSED_DAY_ARCHIVE",
                "utc_day": "20260902",
                "inventory_sha256": canonical_sha256(entries),
                "entries": entries,
            }
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "ARCHIVE_MANIFEST.json",
                    json.dumps(manifest, sort_keys=True, separators=(",", ":")),
                )
                archive.writestr("../escape.bin", b"x")
            with self.assertRaises(Hot90ArchiveError) as raised:
                hydrate_closed_day_archive(
                    zip_path, isolated_data_root=isolated, live_data_root=live
                )
            self.assertEqual(str(raised.exception), "HYDRATE_PATH_ESCAPE")
            self.assertFalse((Path(tmp) / "escape.bin").exists())
            self.assertEqual(marker.read_bytes(), b"keep")


class AdmissionBackupDocsTests(unittest.TestCase):
    def test_runway_and_mutable_sources_and_docs(self) -> None:
        ok = project_storage_runway(
            incremental_compressed_bytes_per_day=1,
            current_same_volume_factory_bytes=0,
            mutable_backup_peak_bytes=0,
            staging_peak_bytes=0,
            retention_class="HOT90",
        )
        self.assertEqual(ok["status"], "OK")
        self.assertFalse(ok["telegram"])
        hard = project_storage_runway(
            incremental_compressed_bytes_per_day=HARD_BYTES,
            current_same_volume_factory_bytes=0,
            mutable_backup_peak_bytes=0,
            staging_peak_bytes=0,
            retention_class="HOT90",
        )
        self.assertEqual(hard["status"], "ACTION_REQUIRED")
        live = mutable_backup_sources(
            {
                "source_relative_paths": ["local/factory_v1/operational_state.sqlite"],
                "recursive_relative_paths": ["local/factory_v1/observation_rdp"],
            },
            activation_stage=STAGE_CURRENT_SAFE,
        )
        self.assertTrue(live["includes_full_observation_rdp"])
        cut = mutable_backup_sources(
            {
                "source_relative_paths": ["local/factory_v1/operational_state.sqlite"],
                "recursive_relative_paths": ["local/factory_v1/observation_rdp"],
                "mutable_only_source_relative_paths": [
                    "local/factory_v1/operational_state.sqlite",
                    "local/factory_v1/paper_plane_state.sqlite",
                    "local/factory_v1/observation_schedule_state.sqlite",
                ],
                "mutable_only_recursive_relative_paths": [
                    "local/factory_v1/observation_rdp/datasets/publication_jobs"
                ],
            },
            activation_stage="DURABILITY_CUTOVER",
        )
        self.assertFalse(cut["includes_full_observation_rdp"])
        collector = (ROOT / "docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("CONTENT IMMUTABLE FOREVER", collector)
        self.assertIn("hot_local_residency_days", collector)
        policy = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("97d resident bytes", policy)
        self.assertIn("TARGET <= 40 GiB", policy)
        commissioning = (
            ROOT / "docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("PREPARED_NOT_EXECUTED", commissioning)
        self.assertIn("WRITE_ONLY_SHADOW", commissioning)
        cleanup = (
            ROOT / "docs/operator/FACTORY_HOT90_CLEANUP_PRECONDITIONS_V1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("BACKUP_*.zip", cleanup)
        self.assertIn("PREPARED_NOT_EXECUTED", cleanup)


if __name__ == "__main__":
    unittest.main()
