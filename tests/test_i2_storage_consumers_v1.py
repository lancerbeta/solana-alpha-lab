"""I2 consumers: actual staging footprint, data-age and actionable incidents."""

from __future__ import annotations

import sys
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import managed_collection as mc  # noqa: E402
from solana_alpha_lab.factory import operability_watch as watch  # noqa: E402
# Load the native caller before these size-only tests replace its sink adapter.
import solana_alpha_lab.factory.offhost_backup  # noqa: E402,F401


class StorageConsumerTests(unittest.TestCase):
    def test_native_registered_cache_remains_charged_after_policy_root_revision_and_disable(self) -> None:
        from tests.test_i2_retention_maintenance_v1 import CheckpointRefreshPolicyRecoveryTests, NOW
        from solana_alpha_lab.factory import observation_schedule_retention as owner

        fixture = CheckpointRefreshPolicyRecoveryTests()
        fixture.setUp()
        try:
            document, _pending, remote = fixture.pending_checkpoint()
            result = fixture.ordinary_refresh_process(remote, NOW + timedelta(minutes=2))
            self.assertEqual(result["archive_refresh"]["status"], "REGISTERED", result)
            archive = owner._control(fixture.store, "checkpoint_archive")
            cache = Path(archive["cache_root"])
            actual = sum(path.stat().st_size for path in cache.rglob("*") if path.is_file())
            self.assertGreater(actual, 0)
            def measure():
                return mc.measure_whole_factory(store=fixture.store, root=fixture.hot,
                    data_root=fixture.hot / "local/factory_v1/observation_rdp", environ={})
            before = measure()["maintenance_staging_bytes"]
            revised = {**document, "revision": 2,
                "archive_refresh": {**document["archive_refresh"], "cold_root_relative": "cold-v2"}}
            owner.install_maintenance_policy(fixture.store, policy=revised,
                approved_sha256=owner.policy_sha256(revised), now=NOW + timedelta(minutes=3))
            after = measure()["maintenance_staging_bytes"]
            print("I2_COLD_CACHE_FOOTPRINT " + json.dumps({"actual_cache_bytes": actual,
                "before_root_revision": before, "after_root_revision": after}))
            self.assertEqual(before, actual)
            self.assertEqual(after, actual)
            disabled = {**revised, "revision": 3, "enabled": False}
            owner.install_maintenance_policy(fixture.store, policy=disabled,
                approved_sha256=owner.policy_sha256(disabled), now=NOW + timedelta(minutes=4))
            self.assertEqual(measure()["maintenance_staging_bytes"], actual)
            self.assertEqual(sum(path.stat().st_size for path in cache.rglob("*") if path.is_file()), actual)
            self.assertEqual(owner._control(fixture.store, "checkpoint_archive"), archive)
        finally:
            fixture.tearDown()

    def test_durable_current_pending_release_and_active_plan_cache_roots_are_charged(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rdp = root / "rdp"; rdp.mkdir()
            ops = root / "ops.sqlite"
            with closing(sqlite3.connect(ops)) as conn:
                conn.execute("CREATE TABLE retention_control(control_key TEXT PRIMARY KEY, payload_json TEXT)")
                roots = {}
                for relative, size in (("current/g0", 5), ("pending/g1", 7), ("release/g2", 11), ("active/g3", 13)):
                    path = root / relative; path.mkdir(parents=True)
                    (path / "bytes").write_bytes(b"x" * size)
                    roots[relative] = path
                records = {
                    "policy": {"policy": {"enabled": False, "archive_refresh": {"cold_root_relative": "absent-new-root"}}},
                    "checkpoint_archive": {"cache_root": str(roots["current/g0"])},
                    "checkpoint_archive_refresh_pending": {"cold_root_relative": "pending"},
                    "checkpoint_archive_cache_release": {"cache_root": str(roots["release/g2"])},
                    "active_plan": {"archive_registry": {"proof": {"proof_class": "REMOTE_CHECKPOINT_RESTORE_VERIFIED",
                        "cache_root": str(roots["active/g3"])}}},
                }
                conn.executemany("INSERT INTO retention_control VALUES(?,?)", [(key, json.dumps(value)) for key, value in records.items()])
                conn.commit()
                with patch("solana_alpha_lab.factory.remote_ops.load_config", return_value={"stores": {}}), patch(
                    "solana_alpha_lab.factory.remote_ops.resolve_backup_sink", return_value=root / "absent-sink"
                ):
                    def measure():
                        return mc.measure_whole_factory(store=SimpleNamespace(path=ops, _conn=conn), data_root=rdp, root=root)
                    self.assertEqual(measure()["maintenance_staging_bytes"], 36)
                    # Delete-before-ack leaves the durable token but no resident bytes.
                    (roots["release/g2"] / "bytes").unlink(); roots["release/g2"].rmdir()
                    self.assertEqual(measure()["maintenance_staging_bytes"], 25)

    def test_overlapping_cache_roots_exclude_already_charged_ops_rdp_sink_and_store(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            cache = root / "cache"; cache.mkdir()
            rdp = cache / "rdp"; rdp.mkdir()
            (rdp / "raw").write_bytes(b"r" * 47)
            sink = cache / "sink"; sink.mkdir()
            (sink / "backup").write_bytes(b"b" * 59)
            other = cache / "other.sqlite"; other.write_bytes(b"s" * 31)
            ops = cache / "ops.sqlite"
            with closing(sqlite3.connect(ops)) as conn:
                conn.execute("CREATE TABLE retention_control(control_key TEXT PRIMARY KEY, payload_json TEXT)")
                for relative, size in (("branch/pending", 19), ("branch/release", 23), ("unlisted", 29)):
                    path = cache / relative; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"c" * size)
                records = {
                    "policy": {"policy": {"archive_refresh": {"cold_root_relative": "cache/branch"}}},
                    "checkpoint_archive": {"cache_root": str(cache)},
                    "checkpoint_archive_refresh_pending": {"cold_root_relative": "cache/branch"},
                    "checkpoint_archive_cache_release": {"cache_root": str(cache / "branch")},
                }
                conn.executemany("INSERT INTO retention_control VALUES(?,?)", [(key, json.dumps(value)) for key, value in records.items()])
                conn.commit()
                with patch("solana_alpha_lab.factory.remote_ops.load_config", return_value={"stores": {"paper_relative": "cache/other.sqlite"}}), patch(
                    "solana_alpha_lab.factory.remote_ops.resolve_backup_sink", return_value=sink
                ):
                    measured = mc.measure_whole_factory(store=SimpleNamespace(path=ops, _conn=conn), data_root=rdp, root=root)
                self.assertEqual(measured["maintenance_staging_bytes"], 71)
                self.assertEqual(measured["other_store_bytes"], 31)
                self.assertEqual(measured["resident_rdp_bytes"], 47)
                self.assertEqual(measured["backup_sink_bytes"], 59)
                self.assertEqual(sum(measured[key] for key in ("sqlite_bytes", "other_store_bytes", "resident_rdp_bytes",
                    "backup_sink_bytes", "maintenance_staging_bytes", "staging_bytes")),
                    sum(path.stat().st_size for path in cache.rglob("*") if path.is_file()))

    def test_malformed_or_unsafe_durable_cache_references_are_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "factory"; root.mkdir()
            rdp = root / "rdp"; rdp.mkdir()
            ops = root / "ops.sqlite"
            with closing(sqlite3.connect(ops)) as conn:
                conn.execute("CREATE TABLE retention_control(control_key TEXT PRIMARY KEY, payload_json TEXT)")
                cases = (("checkpoint_archive", {"cache_root": str(root)}),
                    ("checkpoint_archive", {"cache_root": str(root.parent / "outside")}),
                    ("checkpoint_archive", {"cache_root": "relative-cache"}),
                    ("checkpoint_archive", {}), ("checkpoint_archive_cache_release", {"cache_root": None}),
                    ("checkpoint_archive_refresh_pending", {"cold_root_relative": "../outside"}),
                    ("active_plan", {"archive_registry": {"proof": {"proof_class": "REMOTE_CHECKPOINT_RESTORE_VERIFIED"}}}),
                    ("policy", {"policy": {"archive_refresh": {"cold_root_relative": None}}}),
                    ("checkpoint_archive", "not-an-object"))
                with patch("solana_alpha_lab.factory.remote_ops.load_config", return_value={"stores": {}}), patch(
                    "solana_alpha_lab.factory.remote_ops.resolve_backup_sink", return_value=root / "absent-sink"
                ):
                    for key, value in cases:
                        with self.subTest(key=key, value=value):
                            conn.execute("DELETE FROM retention_control")
                            conn.execute("INSERT INTO retention_control VALUES(?,?)", (key, json.dumps(value)))
                            conn.commit()
                            measured = mc.measure_whole_factory(store=SimpleNamespace(path=ops, _conn=conn), data_root=rdp, root=root)
                            self.assertEqual(measured["maintenance_staging_bytes"], "UNKNOWN")

    def test_missing_factory_configuration_never_zero_fills_topology(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rdp = root / "rdp"
            rdp.mkdir()
            ops = root / "ops.sqlite"
            ops.write_bytes(b"isolated size-only fixture")
            measured = mc.measure_whole_factory(store=SimpleNamespace(path=ops), data_root=rdp, root=root)
            self.assertEqual(measured["backup_sink_bytes"], "UNKNOWN")
            self.assertEqual(measured["other_store_bytes"], "UNKNOWN")
            self.assertEqual(measured["maintenance_staging_bytes"], "UNKNOWN")

    def test_approved_cold_cache_outside_rdp_is_charged(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rdp = root / "rdp"
            rdp.mkdir()
            cold = root / "local/retirement_cold/generation"
            cold.mkdir(parents=True)
            (cold / "captured.sqlite").write_bytes(b"c" * 456)
            ops = root / "ops.sqlite"
            conn = sqlite3.connect(ops)
            try:
                conn.execute("CREATE TABLE retention_control(control_key TEXT PRIMARY KEY, payload_json TEXT)")
                conn.execute("INSERT INTO retention_control VALUES('policy', ?)",
                             (json.dumps({"policy": {"archive_refresh": {"cold_root_relative": "local/retirement_cold"}}}),))
                conn.commit()
                with patch("solana_alpha_lab.factory.remote_ops.load_config", return_value={"stores": {}}), patch(
                    "solana_alpha_lab.factory.remote_ops.resolve_backup_sink", return_value=root / "absent-sink"
                ):
                    measured = mc.measure_whole_factory(store=SimpleNamespace(path=ops, _conn=conn), data_root=rdp, root=root)
                self.assertEqual(measured["maintenance_staging_bytes"], 456)
            finally:
                conn.close()

    def test_freshness_revision_requires_consistent_data_age_and_rpo(self) -> None:
        config = yaml.safe_load((ROOT / "configs/factory_remote_operations_v1_1.yaml").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "catalog/schemas/factory_remote_operations_v1_1.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(config, schema)
        self.assertEqual(config["backup"]["offhost"]["freshness_current_max_seconds"], 86400)
        config["backup"]["offhost"]["freshness_policy_revision"] = 2
        config["backup"]["offhost"]["freshness_current_max_seconds"] = 108000
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(config, schema)
        config["deploy"]["rpo_max"] = "30h"
        jsonschema.validate(config, schema)
        del config["backup"]["offhost"]["freshness_policy_revision"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(config, schema)

    def test_sibling_stores_capture_reclaim_and_sink_are_counted_once(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            ops = root / "local/factory_v1/observation_schedule_state.sqlite"
            ops.parent.mkdir(parents=True)
            ops.write_bytes(b"o" * 101)
            Path(str(ops) + "-wal").write_bytes(b"w" * 13)
            paper = ops.parent / "paper_plane_state.sqlite"
            paper.write_bytes(b"p" * 31)
            rdp = root / "rdp"
            rdp.mkdir()
            nested = rdp / "operational_state.sqlite"
            nested.write_bytes(b"r" * 47)
            sink = root / "sink"
            sink.mkdir()
            (sink / "pending.zip").write_bytes(b"z" * 59)
            capture = ops.parent / "backup_snapshot_staging/run1"
            capture.mkdir(parents=True)
            (capture / "snapshot.sqlite").write_bytes(b"s" * 71)
            reclaim = ops.parent / ("." + ops.name + ".i2-reclaim-new.sqlite")
            reclaim.write_bytes(b"n" * 83)
            config = {"stores": {"observation_schedule_relative": ops.relative_to(root).as_posix(),
                                  "paper_relative": paper.relative_to(root).as_posix(),
                                  "operational_relative": nested.relative_to(root).as_posix()}}
            with patch("solana_alpha_lab.factory.remote_ops.load_config", return_value=config), patch(
                "solana_alpha_lab.factory.remote_ops.resolve_backup_sink", return_value=sink
            ):
                measured = mc.measure_whole_factory(store=SimpleNamespace(path=ops), data_root=rdp, root=root)
            self.assertEqual(measured["sqlite_bytes"], 114)
            self.assertEqual(measured["resident_rdp_bytes"], 47)
            self.assertEqual(measured["backup_sink_bytes"], 59)
            self.assertEqual(measured["other_store_bytes"], 31)
            self.assertEqual(measured["maintenance_staging_bytes"], 154)

    def test_completion_of_old_zip_does_not_refresh_data_age(self) -> None:
        now = datetime(2026, 10, 15, 12, tzinfo=UTC)
        snapshot = {"configured": True, "offhost_backup_state": "CURRENT",
                    "offhost_last_verified_at": mc.render_utc(now),
                    "offhost_snapshot_data_as_of": mc.render_utc(now - timedelta(hours=25)),
                    "offhost_current_max_age_seconds": 86400, "offhost_last_sha256": "a" * 64}
        with patch("solana_alpha_lab.factory.offhost_backup.offhost_health_snapshot", return_value=snapshot):
            result = mc.read_verified_backup(root=ROOT, now=now,
                policy={"backup_source": "OFFHOST_VERIFIED", "backup_max_age_seconds": 108000})
        self.assertEqual(result["state"], "STALE")
        self.assertEqual(result["age_seconds"], 25 * 3600)
        self.assertEqual(result["max_age_seconds"], 86400)
        self.assertEqual(result["profile_max_age_seconds"], 108000)

    def test_failed_attempt_is_separate_incident_and_default_off_maintenance_is_quiet(self) -> None:
        packet = {"offhost_backup_state": "CURRENT", "offhost_last_attempt_terminal": "COPY_FAILED",
                  "maintenance": {"enabled": False, "state": "FAILED"}}
        incidents = watch.classify_incidents(packet)
        self.assertIn("MUTABLE_BACKUP_FAILED", incidents)
        self.assertNotIn("MAINTENANCE_FAILED", incidents)
        packet["offhost_last_attempt_terminal"] = "DAILY_DELTA_VERIFIED"
        packet["maintenance"] = {"enabled": True, "state": "FAILED"}
        incidents = watch.classify_incidents(packet)
        self.assertIn("MAINTENANCE_FAILED", incidents)
        self.assertNotIn("MUTABLE_BACKUP_FAILED", incidents)


if __name__ == "__main__":
    unittest.main()
