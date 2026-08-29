from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    RemoteOpsError,
    _safe_relative,
    consistent_sqlite_backup,
    load_config,
    load_config_v1_1,
    package_backup,
    restore_backup_isolated,
    verify_security_templates,
    write_heartbeat,
)


class ObservationScheduleRemoteOpsTests(unittest.TestCase):
    def test_v1_config_bytes_and_load_remain_intact(self) -> None:
        v1 = ROOT / "configs/factory_remote_operations_v1.yaml"
        self.assertTrue(v1.is_file())
        load_config(ROOT)
        loaded = load_config_v1_1(ROOT)
        self.assertEqual(loaded["schema_version"], "1.1")
        self.assertIn("observation_schedule_relative", loaded["stores"])
        self.assertIn(
            "observation_schedule_service_relative",
            loaded["units"],
        )

    def test_v1_1_security_templates_include_observation_units(self) -> None:
        result = verify_security_templates(ROOT, load_config_v1_1(ROOT))
        self.assertFalse(result["password_ssh"])
        service = (
            ROOT / "configs/factory_remote_ops/factory-observation-schedule.service"
        ).read_text(encoding="utf-8")
        timer = (
            ROOT / "configs/factory_remote_ops/factory-observation-schedule.timer"
        ).read_text(encoding="utf-8")
        self.assertIn("tick --once", service)
        self.assertIn("OnUnitActiveSec=60s", timer)
        self.assertIn("Persistent=true", timer)

    def test_sqlite_backup_api_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.sqlite"
            dest = Path(tmp) / "dest.sqlite"
            conn = sqlite3.connect(source)
            conn.execute("CREATE TABLE t(x INTEGER)")
            conn.execute("INSERT INTO t VALUES (7)")
            conn.commit()
            conn.close()
            consistent_sqlite_backup(source, dest)
            replica = sqlite3.connect(dest)
            try:
                value = replica.execute("SELECT x FROM t").fetchone()[0]
            finally:
                replica.close()
            self.assertEqual(value, 7)
            self.assertNotEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                "0" * 64,
            )

    def test_wal_mutation_during_backup_restores_internally_consistent_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src.sqlite"
            dest = Path(tmp) / "dest.sqlite"
            writer = sqlite3.connect(source)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("CREATE TABLE t(x INTEGER PRIMARY KEY)")
                writer.execute("INSERT INTO t VALUES (1)")
                writer.commit()
                writer.execute("INSERT INTO t VALUES (2)")
                consistent_sqlite_backup(source, dest)
                writer.commit()
            finally:
                writer.close()
            replica = sqlite3.connect(dest)
            try:
                integrity = replica.execute("PRAGMA integrity_check").fetchone()[0]
                values = [row[0] for row in replica.execute("SELECT x FROM t ORDER BY x")]
            finally:
                replica.close()
            self.assertEqual(integrity, "ok")
            self.assertIn(values, ([1], [1, 2]))

    def test_isolated_restore_reproduces_rdp_inventory_and_blocks_tick(self) -> None:
        from datetime import UTC, datetime

        from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.observation_scheduler import (
            ObservationSchedulerError,
            tick_once,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            sqlite_rel = "local/factory_v1/observation_schedule_state.sqlite"
            rdp_rel = "local/factory_v1/observation_rdp/events/panel.json"
            source = root / sqlite_rel
            rdp = root / rdp_rel
            source.parent.mkdir(parents=True)
            rdp.parent.mkdir(parents=True)
            rdp.write_text('{"kind":"observation-panel"}', encoding="utf-8")
            sibling = root / "local/factory_v1/keep-me.txt"
            sibling.write_text("live-sibling", encoding="utf-8")
            store = ObservationScheduleStore(source)
            store.record_event("TICK", {"n": 1}, clock=datetime(2026, 9, 1, tzinfo=UTC))
            store.close()
            (root / "configs").mkdir()
            (root / "configs/factory_remote_operations_v1_1.yaml").write_text(
                "schema_version: '1.1'\n", encoding="utf-8"
            )
            sink = Path(tmp) / "backup"
            v1_1 = {
                "schema_version": "1.1",
                "backup": {
                    "source_relative_paths": [sqlite_rel],
                    "recursive_relative_paths": ["local/factory_v1/observation_rdp"],
                    "independent_sink_relative": "local/factory_v1_backup_sink",
                    "same_parent_forbidden": True,
                },
            }
            packed = package_backup(root, config=v1_1, sink_override=sink)
            bundle = sink / packed["bundle"]
            isolated = Path(tmp) / "isolated"
            isolated.mkdir()
            (isolated / "local/factory_v1").mkdir(parents=True)
            (isolated / "local/factory_v1/keep-me.txt").write_text(
                "live-sibling", encoding="utf-8"
            )
            restored = restore_backup_isolated(bundle=bundle, dest_root=isolated)
            self.assertGreaterEqual(restored["rdp_inventory"]["count"], 1)
            self.assertTrue(restored["restore_marker_unresolved"])
            self.assertEqual(
                (isolated / "local/factory_v1/keep-me.txt").read_text(encoding="utf-8"),
                "live-sibling",
            )
            restored_store = ObservationScheduleStore(isolated / sqlite_rel)
            try:
                self.assertTrue(restored_store.restore_marker_unresolved())
                schedule = load_observation_schedule(
                    ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
                )
                with self.assertRaisesRegex(
                    ObservationSchedulerError, "RESTORE_MARKER_UNRESOLVED"
                ):
                    tick_once(
                        root=ROOT,
                        data_root=isolated / "local/factory_v1/observation_rdp",
                        store=restored_store,
                        schedule=schedule,
                        activation_id="ACT-OBS-001",
                        now=datetime(2026, 9, 1, 0, 10, tzinfo=UTC),
                        producer_git_sha="c" * 40,
                    )
            finally:
                restored_store.close()

    def test_backup_path_rejects_symlinked_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            source = root / "source.sqlite"
            source.write_bytes(b"not-a-live-store")

            def fake_is_symlink(self: Path) -> bool:
                return self.name == "source.sqlite"

            with patch.object(Path, "is_symlink", fake_is_symlink):
                with self.assertRaisesRegex(RemoteOpsError, "REMOTE_PATH_UNSAFE"):
                    _safe_relative(root, "source.sqlite")

    def test_backup_package_dispatches_v1_1_for_legacy_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "configs").mkdir()
            (root / "configs/factory_remote_operations_v1_1.yaml").write_text(
                "schema_version: '1.1'\n", encoding="utf-8"
            )
            source = root / "observation_schedule_state.sqlite"
            conn = sqlite3.connect(source)
            conn.execute("CREATE TABLE t(x INTEGER)")
            conn.execute("INSERT INTO t VALUES (11)")
            conn.commit()
            conn.close()
            sink = Path(tmp) / "backup"
            legacy = {
                "schema_version": "1.0",
                "backup": {
                    "source_relative_paths": ["observation_schedule_state.sqlite"],
                    "recursive_relative_paths": [],
                    "same_parent_forbidden": True,
                },
            }
            v1_1 = {
                "schema_version": "1.1",
                "backup": {
                    "source_relative_paths": ["observation_schedule_state.sqlite"],
                    "recursive_relative_paths": [],
                    "same_parent_forbidden": True,
                },
            }
            with patch(
                "solana_alpha_lab.factory.remote_ops.load_config_v1_1",
                return_value=v1_1,
            ):
                packed = package_backup(root, config=legacy, sink_override=sink)
            self.assertEqual(packed["entries"][0]["kind"], "SQLITE_BACKUP_API")

    def test_production_doctor_backup_path_dispatches_v1_1(self) -> None:
        from scripts import factory_remote_doctor

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            source = root / "local" / "factory_v1" / "observation_schedule_state.sqlite"
            source.parent.mkdir(parents=True)
            (root / "configs").mkdir()
            (root / "configs" / "factory_remote_operations_v1_1.yaml").write_text(
                "schema_version: '1.1'\n", encoding="utf-8"
            )
            connection = sqlite3.connect(source)
            try:
                connection.execute("CREATE TABLE t(x INTEGER)")
                connection.execute("INSERT INTO t VALUES (13)")
                connection.commit()
            finally:
                connection.close()
            sink = root / "local" / "factory_v1_backup_sink"
            legacy = {"schema_version": "1.0"}
            v1_1 = {
                "schema_version": "1.1",
                "backup": {
                    "source_relative_paths": [
                        "local/factory_v1/observation_schedule_state.sqlite"
                    ],
                    "recursive_relative_paths": [],
                    "independent_sink_relative": "local/factory_v1_backup_sink",
                    "same_parent_forbidden": True,
                },
            }
            output = StringIO()
            original_argv = list(sys.argv)
            try:
                sys.argv = [
                    "factory_remote_doctor.py",
                    "--root",
                    str(root),
                    "--backup",
                ]
                with (
                    patch.object(factory_remote_doctor, "load_config", return_value=legacy),
                    patch(
                        "solana_alpha_lab.factory.remote_ops.load_config_v1_1",
                        return_value=v1_1,
                    ),
                    redirect_stdout(output),
                ):
                    code = factory_remote_doctor.main()
            finally:
                sys.argv = original_argv
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["entries"][0]["kind"], "SQLITE_BACKUP_API")

    def test_heartbeat_dispatches_v1_1_observation_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "configs").mkdir()
            (root / "configs/factory_remote_operations_v1_1.yaml").write_text(
                "schema_version: '1.1'\n", encoding="utf-8"
            )
            legacy = {
                "schema_version": "1.0",
                "monitoring": {"heartbeat_relative": "paper_heartbeat.json"},
                "deploy": {"version": "test"},
            }
            v1_1 = {
                "schema_version": "1.1",
                "monitoring": {
                    "heartbeat_relative": "paper_heartbeat.json",
                    "observation_heartbeat_relative": "observation_heartbeat.json",
                },
                "deploy": {"version": "test"},
            }
            with patch(
                "solana_alpha_lab.factory.remote_ops.load_config_v1_1",
                return_value=v1_1,
            ):
                write_heartbeat(root, config=legacy)
            self.assertTrue((root / "observation_heartbeat.json").is_file())


if __name__ == "__main__":
    unittest.main()
