"""Real managed children through the ordinary mutable-only backup caller."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import yaml

from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
from tests.test_managed_collection_continuity_v1 import D0, D1, D2, ManagedScenario
from solana_alpha_lab.factory import hot90_closed_day_loop as archive
from solana_alpha_lab.factory import observation_schedule_retention as retention
from solana_alpha_lab.factory import offhost_backup as backup
from solana_alpha_lab.factory.hot90_activation import write_hot90_runtime_state
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.remote_ops import BACKUP_SINK_ENV, load_config_v1_1

ROOT = Path(__file__).resolve().parents[1]
RDP = "local/factory_v1/observation_rdp"


class ManagedMaintenancePipelineTests(unittest.TestCase):
    def test_generated_children_use_one_policy_and_ordinary_caller_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = _seed_tree(Path(name) / "factory")
            for relative in ("configs/observation_schedule_runtime_v1.yaml",
                             "catalog/schemas/observation_schedule_runtime_v1.schema.json"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            sc = ManagedScenario(root / RDP)
            with patch.dict(os.environ, {BACKUP_SINK_ENV: str(sc.sink)}):
                sc.commission_account()
                applied = sc.apply(D0 + timedelta(hours=1))
                self.assertEqual(applied["terminal"], "MANAGED_APPLIED", applied)
                # Commission one lineage policy before either future child
                # exists. No daily child IDs or later policy replacement.
                store = ObservationScheduleStore(sc.ops_path)
                try:
                    lineage = store.managed_lineages()[0]
                    minimum = int(sc.schedule["retention"]["raw_retention_days"])
                    policy = {"schema": retention.POLICY_SCHEMA, "revision": 1, "enabled": True,
                        "allowed_scopes": [], "allowed_managed_lineages": [lineage], "auto_retire_terminal": True,
                        "allowed_classes": ["call_ledger", "poll_slots"], "min_age_days": minimum,
                        "frozen_min_age_days": minimum, "max_rows": 256, "max_bytes": 8 * 1024 * 1024,
                        "max_wall_seconds": 5, "cadence_seconds": 60, "due_guard_seconds": 120,
                        "physical_reclaim": False, "retained_restore_points": 2,
                        "archive_refresh": {"enabled": True, "max_objects": 128, "max_bytes": 64 * 1024 * 1024,
                            "max_wall_seconds": 120, "cold_root_relative": "local/factory_v1/retirement_cold",
                            "minimum_interval_seconds": 60, "local_cache_retained": 1}}
                    retention.install_maintenance_policy(store, policy=policy,
                        approved_sha256=retention.policy_sha256(policy), now=D0 + timedelta(hours=2))
                finally:
                    store.close()
                sc.backup(D1 - timedelta(hours=1))
                sc.nominate_round(D1, "C1", count=1)
                tick = sc.tick(D1 + timedelta(seconds=5))
                self.assertEqual(tick["managed"]["terminal"], "RECONCILE_CHILD_ACTIVATED", tick)
                # At least one real SEARCH response, rather than only a
                # nomination witness, exercises the heavy decoded-body path.
                observed = sc.tick(D1 + timedelta(minutes=5, seconds=35))
                self.assertEqual(observed["_exit_code"], 0, observed.get("terminal"))
                # Settle expired observations while original tail authority is
                # still valid. Gaps remain honest native MISSED states; this
                # storage rehearsal makes no full-coverage science claim.
                finish = D2 + timedelta(days=4, hours=1)
                for next_at in (D2 + timedelta(seconds=5),
                                D1 + timedelta(days=3, minutes=2),
                                D2 + timedelta(days=3, minutes=2), finish):
                    if next_at == D2 + timedelta(seconds=5):
                        sc.nominate_round(D2, "C2", count=1)
                    sc.backup(next_at - timedelta(hours=1))
                    result = sc.tick(next_at)
                    self.assertEqual(result["_exit_code"], 0, result.get("error") or result.get("terminal"))
                    if next_at == D2 + timedelta(seconds=5):
                        # Slot offsets are native schedule assignments, not a
                        # fixture assumption that every child has :05:35 T5.
                        child_store = ObservationScheduleStore(sc.ops_path, readonly=True, immutable=False)
                        try:
                            due = child_store._conn.execute(
                                "SELECT min(d.due_at) FROM due_observations d JOIN managed_children m "
                                "USING(schedule_sha256,activation_id) WHERE m.utc_day=? AND d.due_at>?",
                                (D2.date().isoformat(), next_at.isoformat().replace('+00:00','Z'))).fetchone()[0]
                        finally:
                            child_store.close()
                        self.assertIsNotNone(due)
                        observed = sc.tick(parse_utc(due) + timedelta(seconds=1))
                        self.assertEqual(observed["_exit_code"], 0, observed)

            loaded = load_config_v1_1(root)
            ops_relative = sc.ops_path.relative_to(root).as_posix()
            loaded["stores"]["observation_schedule_relative"] = ops_relative
            sources = ["local/factory_v1/operational_state.sqlite",
                       "local/factory_v1/paper_plane_state.sqlite", ops_relative]
            loaded["backup"]["source_relative_paths"] = sources
            loaded["backup"]["mutable_only_source_relative_paths"] = sources
            (root / "configs/factory_remote_operations_v1_1.yaml").write_text(
                yaml.safe_dump(loaded, sort_keys=False), encoding="utf-8")
            runtime_path = root / "configs/observation_schedule_runtime_v1.yaml"
            runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
            runtime["ops_store_relative"] = ops_relative
            runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
            write_hot90_runtime_state(root, {"activation_stage": "DURABILITY_CUTOVER",
                "production_compaction_enabled": False, "production_eviction_enabled": False,
                "drive_writes_enabled": True})

            credentials = root / "rclone-fixture.conf"
            credentials.write_text("[fixture]\ntype = drive\n", encoding="utf-8")
            credentials.chmod(0o600)
            config = replace(backup.load_offhost_config(root), rclone_config_absolute=credentials)
            remote = FakeRcloneRunner()

            def transport(argv):
                sub = remote._subcommand(argv)
                if sub == "copyto" and argv[-2] in remote.payloads:
                    target = Path(argv[-1])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(remote.payloads[argv[-2]])
                    remote.calls.append(list(argv))
                    return subprocess.CompletedProcess(argv, 0, "", "")
                if sub == "copyto" and argv[-2].startswith(config.remote_prefix):
                    remote.calls.append(list(argv))
                    return subprocess.CompletedProcess(argv, 1, "", "object absent")
                if sub == "hashsum" and "sha256" in argv:
                    remote.calls.append(list(argv))
                    payload = remote.payloads.get(argv[-1])
                    if payload is None:
                        return subprocess.CompletedProcess(argv, 1, "", "object absent")
                    return subprocess.CompletedProcess(argv, 0,
                        hashlib.sha256(payload).hexdigest() + "  " + Path(argv[-1]).name + "\n", "")
                return remote(argv)

            store = ObservationScheduleStore(sc.ops_path)
            try:
                children = store._conn.execute(
                    "SELECT m.schedule_sha256,m.activation_id,m.state,a.state FROM managed_children m "
                    "JOIN schedule_activations a USING(schedule_sha256,activation_id) ORDER BY m.utc_day"
                ).fetchall()
                self.assertGreaterEqual(len(children), 2)
                self.assertEqual([row[3] for row in children[:2]], ["COMPLETE", "COMPLETE"],
                                 [tuple(row) for row in children])
                self.assertEqual([row[2] for row in children[:2]], ["TAIL_COMPLETE", "TAIL_COMPLETE"])
                admissions = {row[0]: row[1] for row in store._conn.execute(
                    "SELECT activation_id,count(*) FROM episode_admissions GROUP BY activation_id")}
                self.assertTrue(all(admissions.get(row[1], 0) >= 1 for row in children[:2]), admissions)
                original = {table: list(store._conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid"))
                            for table in ("managed_profiles", "managed_control", "managed_children",
                                          "accounting_counters", "lifetime_counters", "account_budget_members")}
                now = finish + timedelta(days=minimum + 2)
                raw_days = sorted({p.parent.name for p in (sc.data_root / "datasets/raw_evidence").rglob("*")
                                   if p.is_file() and p.parent.name.isdigit() and len(p.parent.name) == 8})
                self.assertTrue(raw_days)
            finally:
                store.close()

            original_read_text = Path.read_text

            def host_read_text(path, *args, **kwargs):
                if path.as_posix() == "/proc/meminfo":
                    return "MemAvailable: 1048576 kB\n"
                if path.as_posix() == "/proc/pressure/io":
                    return "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
                return original_read_text(path, *args, **kwargs)

            with patch.object(backup, "load_offhost_config", return_value=config), patch.object(
                archive, "load_offhost_config", return_value=config
            ), patch.object(os, "getloadavg", return_value=(0, 0, 0), create=True), patch.object(
                Path, "read_text", new=host_read_text
            ):
                for day in raw_days:
                    result = archive.process_one_day(root, day, now=now, rclone_runner=transport, allow_drive=True)
                    self.assertEqual(result["terminal"], "REMOTE_CONTENT_SHA256_VERIFIED", result)
                receipt = backup.run_offhost_checkpoint(root, mode="daily", config=config, runner=transport, now=now)
                # Explicit cutover exercises production mutable-only membership.
                self.assertFalse(any("/raw_evidence/" in item["path"]
                                     for item in backup.read_chain_state(root, config)["tip_entries"]))
                result = backup.run_checkpoint_maintenance(root, receipt, now=now, runner=transport)
                # Restart the entire store/caller, retaining the exact policy.
                result2 = backup.run_checkpoint_maintenance(root, receipt, now=now + timedelta(seconds=61), runner=transport)

            store = ObservationScheduleStore(sc.ops_path, readonly=True, immutable=False)
            try:
                for table, rows in original.items():
                    self.assertEqual([tuple(row) for row in store._conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid")],
                                     [tuple(row) for row in rows], table)
                compacted = store._conn.execute(
                    "SELECT count(*) FROM call_ledger WHERE json_extract(payload_json,'$.entities_retention')=?",
                    (retention.COMPACTION_MARKER,)).fetchone()[0]
                retired = {tuple(row) for row in store._conn.execute(
                    "SELECT schedule_sha256,activation_id FROM retirement_scopes")}
                calls = [tuple(row) for row in store._conn.execute(
                    "SELECT call_occurrence_id,json_extract(payload_json,'$.entities_retention'),"
                    "length(payload_json) FROM call_ledger ORDER BY rowid")]
                self.assertGreaterEqual(compacted, 2, (calls, retired, result, result2))
                self.assertTrue({(row[0], row[1]) for row in children[:2]}.issubset(retired),
                                (retired, result, result2))
                self.assertEqual(retention.retention_status(store)["approved_policy_sha256"], retention.policy_sha256(policy))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
