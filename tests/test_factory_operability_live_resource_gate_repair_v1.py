"""The watch must seek recent calls and reuse immutable proof reads per packet."""

from __future__ import annotations

import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore, OPERABILITY_INDEX_SQL, OPERABILITY_TIME_SQL,
    reset_store_read_stats, store_read_stats,
)
from solana_alpha_lab.factory.research_store import (
    ResearchStore, reuse_lifecycle_reads_within_packet,
)


class OperabilityIndexTests(unittest.TestCase):
    def test_seek_margin_and_python_only_timestamps_do_not_enter_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ObservationScheduleStore(Path(temp, "ops.sqlite"))
            cutoff = datetime(2026, 10, 2, 12, tzinfo=UTC)
            stamps = ["2026-09-01T12:00:00,123Z", "2026-09-01T12:00:00.Z",
                      "2026-10-02T11:59:59.999999Z", "2026-02-30T12:00:00Z",
                      "2026-10-02T12:00:00Z", "2026-10-02T12:00:00.000001Z"]
            store._conn.executemany(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ((f"r{i}", f"c{i}", f"a{i}", "COMPLETED", "P", "{}", stamp, stamp)
                 for i, stamp in enumerate(stamps)))
            rows = list(store.iter_operability_calls(window_start=cutoff))
            self.assertEqual({r["updated_at"] for r in rows}, set(stamps[3:]))
            store.close()

    def test_old_history_is_not_examined_and_invalid_time_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ObservationScheduleStore(Path(temp, "ops.sqlite"))
            now = datetime(2026, 10, 3, 12, tzinfo=UTC)
            old = "2026-09-01T00:00:00Z"
            recent = "2026-10-03T11:00:00Z"
            store._conn.executemany(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ((f"r{i}", f"c{i}", f"a{i}", "COMPLETED", "P", "{}", old, old)
                 for i in range(5000)),
            )
            store._conn.execute(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("recent", "recent", "recent", "COMPLETED", "P", "{}", recent, recent),
            )
            store._conn.execute(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("invalid", "invalid", "invalid", "COMPLETED", "P", "{}",
                 "invalid", "invalid"),
            )
            store._conn.commit()
            reset_store_read_stats()
            rows = list(store.iter_operability_calls(window_start=now - timedelta(days=1)))
            self.assertEqual({r["updated_at"] for r in rows}, {recent, "invalid"})
            self.assertEqual(store_read_stats()["call_ledger_timestamp_rows_examined"], 0)
            self.assertEqual(store_read_stats()["call_diagnostics_index_candidates"], 2)
            plan = store._conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM call_ledger "
                f"WHERE {OPERABILITY_TIME_SQL} >= julianday(?)",
                ("2026-10-02T11:59:59Z",),
            ).fetchall()
            self.assertIn("idx_call_ledger_operability_time", str([tuple(r) for r in plan]))
            store.close()

    def test_index_allows_rollback_writer_without_custom_sql_function(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "ops.sqlite")
            ObservationScheduleStore(path).close()
            legacy = sqlite3.connect(path)
            legacy.execute(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("r", "c", "a", "COMPLETED", "P", "{}", "2026-10-03T11:00:00Z", "2026-10-03T11:00:00Z"),
            )
            legacy.execute("UPDATE call_ledger SET updated_at=? WHERE request_sha256='r'",
                           ("2026-10-03T11:01:00Z",))
            legacy.commit()
            legacy.close()
            reader = ObservationScheduleStore(path, readonly=True)
            self.assertEqual(len(list(reader.iter_operability_calls(
                window_start=datetime(2026, 10, 3, 11, tzinfo=UTC)))), 1)
            reader.close()

    def test_readonly_before_one_time_index_build_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "ops.sqlite")
            writer = ObservationScheduleStore(path)
            writer._conn.execute(
                "INSERT INTO call_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("old", "old", "old", "COMPLETED", "P", "{}",
                 "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z"),
            )
            writer._conn.execute("DROP INDEX idx_call_ledger_operability_time")
            writer._conn.commit()
            writer.close()
            reader = ObservationScheduleStore(path, readonly=True)
            rows = list(reader.iter_operability_calls(
                window_start=datetime(2026, 10, 3, tzinfo=UTC)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["diagnostics_payload_valid"], 0)
            reader.close()
            # Ordinary collector startup must not build the large index.
            migrated = ObservationScheduleStore(path)
            self.assertIsNone(migrated._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='idx_call_ledger_operability_time'"
            ).fetchone())
            migrated.close()
            from scripts.factory_prepare_operability_index import prepare
            self.assertEqual(prepare(path)["result"], "PASS")
            self.assertEqual(prepare(path)["result"], "PASS")
            migrated = ObservationScheduleStore(path)
            self.assertIsNotNone(migrated._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='idx_call_ledger_operability_time'"
            ).fetchone())
            migrated.close()

    def test_same_name_wrong_index_does_not_allow_historical_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ObservationScheduleStore(Path(temp, "ops.sqlite"))
            store._conn.execute("DROP INDEX idx_call_ledger_operability_time")
            store._conn.execute("CREATE INDEX idx_call_ledger_operability_time ON call_ledger(created_at)")
            rows = list(store.iter_operability_calls(window_start=datetime(2026, 10, 3, tzinfo=UTC)))
            self.assertEqual(rows[0]["diagnostics_payload_valid"], 0)
            store.close()


class PacketScopedImmutableReadTests(unittest.TestCase):
    def test_repeated_proofs_share_one_inventory_and_verified_partition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parquet = root / "research/events/proof.parquet"
            parquet.parent.mkdir(parents=True)
            parquet.write_bytes(b"proof")
            manifest = SimpleNamespace(
                partition_id="proof", partition_manifest_id="partition-proof",
                logical_location="research/events/proof.parquet",
            )
            with patch.object(ResearchStore, "_manifest_files", return_value=(root / "proof.json",)), \
                 patch.object(ResearchStore, "_read_manifest", return_value=manifest) as read, \
                 patch.object(ResearchStore, "_verify_partition", return_value=()) as verify:
                @reuse_lifecycle_reads_within_packet
                def packet() -> None:
                    for _ in range(3):
                        store = ResearchStore(root, create_if_missing=False)
                        self.assertEqual(store._committed_manifests(), (manifest,))
                        self.assertEqual(store._verify_partition_with_size(manifest), ((), 5))
                packet()
                self.assertEqual(read.call_count, 1)
                self.assertEqual(verify.call_count, 1)
                packet()  # A new packet must re-verify immutable truth.
                self.assertEqual(read.call_count, 2)
                self.assertEqual(verify.call_count, 2)


class CgroupProofGateTests(unittest.TestCase):
    def test_running_missing_peak_unknown_data_and_threshold_cannot_pass(self) -> None:
        import operability_bounded_call_profile as profile
        (ROOT / "local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "local") as temp:
            root = Path(temp)
            (root / "fixture.json").write_text(json.dumps({"old_call_rows": 5000, "immutable_manifests": 3}))
            fields = {"ActiveState": "active", "SubState": "exited", "Result": "success",
                      "ExecMainStatus": "0", "MemoryMax": str(768 * 1024**2),
                      "MemoryPeak": str(80 * 1024**2), "ExecMainStartTimestampMonotonic": "1000000",
                      "ExecMainExitTimestampMonotonic": "2000000"}
            measured = {"consumer": "watch", "baseline": False,
                        "store_read_stats": {"call_diagnostics_rows_returned": 128,
                                             "call_diagnostics_index_candidates": 128},
                        "result": {"cli_exit": 0, "observations_24h": 128, "call_diagnostics_status": "EXACT"},
                        "immutable_reads": {"partition_verifications": 3, "manifest_reads": 3}}
            cases = [(fields, measured, True), (dict(fields, SubState="running"), measured, False),
                     ({k: v for k, v in fields.items() if k != "MemoryPeak"}, measured, False),
                     (dict(fields, MemoryPeak=str(512 * 1024**2)), measured, False),
                     (dict(fields, ExecMainExitTimestampMonotonic="1000000"), measured, False),
                     (fields, dict(measured, result={"cli_exit": 0, "observations_24h": None,
                                                    "call_diagnostics_status": "UNKNOWN"}), False)]
            for state, result, expected in cases:
                def run(command, **kwargs):
                    output = ("\n".join(f"{k}={v}" for k, v in state.items()) if "show" in command
                              else json.dumps(result) if "journalctl" in command else "")
                    return SimpleNamespace(returncode=0, stdout=output, stderr="")
                with self.subTest(state=state, expected=expected), \
                     patch.object(profile.sys, "platform", "linux"), \
                     patch.object(profile.os, "posix_fadvise", create=True), \
                     patch.object(profile.os, "POSIX_FADV_DONTNEED", 4, create=True), \
                     patch.object(profile.subprocess, "run", side_effect=run):
                    self.assertEqual(profile.cgroup_gate(root, "watch")["pass"], expected)


if __name__ == "__main__":
    unittest.main()
