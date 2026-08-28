from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import (  # noqa: E402
    consistent_sqlite_backup,
    load_config,
    load_config_v1_1,
    verify_security_templates,
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


if __name__ == "__main__":
    unittest.main()
