"""I2: captured-byte, ordered-chain and recovery-control acceptance oracles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest
import zipfile
from contextlib import closing, contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import remote_ops as remote  # noqa: E402

OPS = "local/factory_v1/observation_schedule_state.sqlite"
RDP = "local/factory_v1/observation_rdp"
LEGACY_PRODUCER_BASE = "b3fb9d8ecffbffda468dccabaa81ca3392da6f15"


def _raw_sql_readback(path: Path, *, isolated: bool = False) -> dict:
    """Independent row/ROWID oracle; the restore marker is the only decoration."""
    uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if isolated else "")
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'restore_markers' ORDER BY name")]
        result = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            try:
                rows = list(conn.execute(f"SELECT rowid,* FROM {quoted} ORDER BY rowid"))
            except sqlite3.OperationalError:
                rows = sorted(list(conn.execute(f"SELECT * FROM {quoted}")), key=repr)
            result[table] = {"rows": len(rows), "sha256": hashlib.sha256(
                json.dumps(rows, separators=(",", ":"), default=str).encode()).hexdigest()}
        result["activation_rows"] = list(conn.execute(
            "SELECT schedule_sha256,activation_id,state,last_transition_event_id,transition_sequence,"
            "authority_receipt_sha256,payload_json FROM schedule_activations ORDER BY rowid"))
        return json.loads(json.dumps(result))


class I2BackupLegacyStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "producer"
        self.sink = Path(self.temp.name) / "sink"
        self.root.mkdir()
        (self.root / RDP).mkdir(parents=True)
        self.config = {"schema_version": "1.1", "backup": {
            "source_relative_paths": [OPS], "recursive_relative_paths": [RDP],
            "same_parent_forbidden": True,
            "independent_sink_relative": "local/factory_v1_backup_sink",
        }}
        path = self.root / OPS
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE semantic_state(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_revision INTEGER, provider_calls INTEGER, credits INTEGER,
                    desired_state TEXT, payload TEXT);
                INSERT INTO semantic_state VALUES(27,1,1199,1200,'RUN','original');
                CREATE TABLE cursor_identity(name TEXT);
                INSERT INTO cursor_identity(rowid,name) VALUES(77,'tail-cursor');
            """)
            conn.commit()
        (self.root / RDP / "keep.json").write_text('{"body":"before"}', encoding="utf-8")

    def full(self) -> dict:
        return remote.package_backup(self.root, config=self.config, sink_override=self.sink,
                                     prune_superseded=False)

    def delta(self, base: dict) -> tuple[dict, dict]:
        with remote.backup_payload_snapshot(self.root, self.config) as snapshot:
            inventory = remote.scan_backup_inventory(self.root, config=self.config, snapshot=snapshot)
            packed = remote.package_delta_backup(self.root, base_manifest=base,
                current_entries=inventory["entries"], sink=self.sink, snapshot=snapshot)
        return packed, inventory

    def mutate(self, value: str) -> None:
        with closing(sqlite3.connect(self.root / OPS)) as conn:
            conn.execute("UPDATE semantic_state SET payload=? WHERE id=27", (value,))
            conn.commit()

    def rewrite(self, bundle: Path, *, manifest_change=None, omit=(), extra=(), duplicate=None,
                stored: bool = False, corrupt=None) -> Path:
        target = self.sink / f"rewrite-{time.time_ns()}.zip"
        manifest_name = "DELTA_MANIFEST.json" if bundle.name.startswith("DELTA_") else "BACKUP_MANIFEST.json"
        with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(target, "w") as dest:
            for name in source.namelist():
                if name in omit:
                    continue
                data = source.read(name)
                if name == manifest_name and manifest_change:
                    body = json.loads(data)
                    manifest_change(body)
                    data = json.dumps(body, sort_keys=True).encode()
                if name == corrupt:
                    data = b"corruption" + data[10:]
                dest.writestr(name, data, compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,
                              compresslevel=None if stored else 1)
            for name, data in extra:
                dest.writestr(name, data)
            if duplicate:
                dest.writestr(duplicate, source.read(duplicate))
        prefix = "DELTA" if manifest_name.startswith("DELTA") else "BACKUP"
        named = self.sink / f"{prefix}_{hashlib.sha256(target.read_bytes()).hexdigest()}.zip"
        target.replace(named)
        return named

    def test_concurrent_writer_after_inventory_cannot_change_checkpoint_or_membership(self) -> None:
        with patch.object(remote, "consistent_sqlite_backup", wraps=remote.consistent_sqlite_backup) as backup:
            with remote.backup_payload_snapshot(self.root, self.config) as snapshot:
                inventory = remote.scan_backup_inventory(self.root, config=self.config, snapshot=snapshot)
                self.mutate("committed after inventory")
                (self.root / RDP / "keep.json").unlink()
                (self.root / RDP / "new.json").write_text("new path", encoding="utf-8")
                packed = remote.package_backup(self.root, config=self.config, snapshot=snapshot,
                    sink_override=self.sink, prune_superseded=False)
                self.assertEqual(backup.call_count, 1)
                self.assertEqual(packed["inventory_sha256"], inventory["inventory_sha256"])
                with zipfile.ZipFile(self.sink / packed["bundle"]) as archive:
                    self.assertNotIn(f"{RDP}/new.json", archive.namelist())
                    self.assertIn(f"{RDP}/keep.json", archive.namelist())
                    self.assertEqual(hashlib.sha256(archive.read(OPS)).hexdigest(), snapshot.entry(OPS)["sha256"])
                    self.assertEqual({info.compress_type for info in archive.infolist()}, {zipfile.ZIP_DEFLATED})
                staged = snapshot.staged_path(OPS)
                self.assertIn("backup_snapshot_staging", staged.parts)
            self.assertFalse(staged.exists())
        restored = Path(self.temp.name) / "restored"
        result = remote.restore_incremental_chain_isolated(full_bundle=self.sink / packed["bundle"],
            deltas=[], dest_root=restored, expected_inventory_sha256=inventory["inventory_sha256"])
        self.assertEqual(result["raw_inventory_sha256"], inventory["inventory_sha256"])
        with closing(sqlite3.connect(restored / OPS)) as conn:
            self.assertEqual(conn.execute("SELECT * FROM semantic_state").fetchone(),
                             (27, 1, 1199, 1200, "RUN", "original"))
            self.assertEqual(conn.execute("SELECT rowid,name FROM cursor_identity").fetchone(), (77, "tail-cursor"))
            self.assertEqual(conn.execute("SELECT seq FROM sqlite_sequence WHERE name='semantic_state'").fetchone(), (27,))
            self.assertEqual(conn.execute("SELECT resolved FROM restore_markers WHERE marker_id='UNRESOLVED'").fetchone(), (0,))

    def test_nested_native_open_wal_cannot_override_captured_main_after_restore(self) -> None:
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

        nested=f"{RDP}/observation_schedule_state.sqlite"
        store=ObservationScheduleStore(self.root/nested)
        self.addCleanup(store.close)
        store.record_event("BEFORE_CAPTURE",{"n":1})
        self.config["backup"]["source_relative_paths"]=[nested]
        original=remote._capture_writer_fences
        @contextmanager
        def after_capture(sources):
            with original(sources):
                yield
            store.record_event("AFTER_CAPTURE",{"n":2})
            self.assertTrue(Path(str(store.path)+"-wal").is_file())
        with patch.object(remote,"_capture_writer_fences",after_capture):
            packed=self.full()
        self.assertFalse(any(item["path"].endswith((".sqlite-wal",".sqlite-shm",".sqlite-journal")) for item in packed["entries"]))
        restored=Path(self.temp.name)/"open-wal-restored"
        remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"],deltas=[],
            dest_root=restored,expected_inventory_sha256=packed["inventory_sha256"])
        with closing(sqlite3.connect(restored/nested)) as conn:
            self.assertEqual(list(conn.execute("SELECT kind FROM runtime_events ORDER BY event_id")),[("BEFORE_CAPTURE",)])
            self.assertEqual(conn.execute("SELECT resolved FROM restore_markers").fetchone(),(0,))

    def _native_reclaim_backup_fixture(self, *, nested: bool, finalize: bool,
                                       phase: str = "SWITCHED") -> tuple[Path, str, Path]:
        from solana_alpha_lab.factory import observation_schedule_retention as retention
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

        relative = f"{RDP}/observation_schedule_state.sqlite" if nested else OPS
        path = self.root/relative
        # Reclaim deliberately accepts only the native operational schema.
        (self.root/OPS).unlink()
        self.config["backup"]["source_relative_paths"] = [relative]
        if not nested:
            self.config["backup"]["recursive_relative_paths"] = [f"{RDP}/datasets/publication_jobs"]
            (self.root/RDP/"datasets/publication_jobs").mkdir(parents=True)
        store = ObservationScheduleStore(path)
        try:
            store.record_event("BEFORE_RECLAIM", {"debit":17})
            store._conn.execute("UPDATE runtime_events SET event_id=77")
            store._conn.execute("UPDATE sqlite_sequence SET seq=88 WHERE name='runtime_events'")
            store._conn.commit()
            proof = retention.create_cold_archive(store,
                archive_path=Path(self.temp.name)/"final-native.sqlite",
                restored_path=Path(self.temp.name)/"final-native-verified.sqlite", routine_roots=[self.root])
            plan = retention.build_reclaim_plan(store, data_root=self.root/RDP, backup_root=self.root)
            arguments = dict(plan=plan, approved_plan_sha256=plan["plan_id"], data_root=self.root/RDP,
                backup_root=self.root, writers_quiesced=True, independent_recovery_proof=proof,
                now=datetime.now(UTC)-timedelta(minutes=5))
            if phase == "ORIGINAL_MOVED":
                with self.assertRaisesRegex(retention.ObservationScheduleRetentionError, "RECLAIM_INJECTED_CRASH"):
                    retention.apply_physical_reclaim(store, **arguments, failpoint=phase)
            else:
                result = retention.apply_physical_reclaim(store, **arguments)
                self.assertEqual(result["status"], "SWITCHED_AWAITING_NATIVE_READBACK")
            if finalize:
                retention.recover_physical_reclaim(path, data_root=self.root/RDP,
                    action="resume", approved_plan_sha256=plan["plan_id"])
        finally:
            store.close()
        intent = retention._reclaim_paths(path)[2]
        self.assertEqual(json.loads(intent.read_text())["state"], "FINALIZED" if finalize else phase)
        return path, relative, intent

    def test_finalized_reclaim_nested_full_restore_allows_native_writer(self) -> None:
        self._assert_finalized_reclaim_backup_restores(nested=True)

    def test_finalized_reclaim_sibling_mutable_restore_allows_native_writer(self) -> None:
        self._assert_finalized_reclaim_backup_restores(nested=False)

    def _assert_finalized_reclaim_backup_restores(self, *, nested: bool) -> None:
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

        source, relative, intent = self._native_reclaim_backup_fixture(nested=nested, finalize=True)
        expected = _raw_sql_readback(source)
        self.assertEqual(json.loads(intent.read_text())["final_db_binding"]["inode"], source.stat().st_ino)
        packed = self.full()
        restored = Path(self.temp.name)/"finalized-reclaim-restored"
        remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"], deltas=[],
            dest_root=restored, expected_inventory_sha256=packed["inventory_sha256"])
        self.assertNotEqual((restored/relative).stat().st_ino, source.stat().st_ino)
        with closing(ObservationScheduleStore(restored/relative)) as writer:
            self.assertEqual(_raw_sql_readback(restored/relative), expected)
            self.assertTrue(writer.restore_marker_unresolved())
            self.assertEqual(writer.mark_recovery_gap(cutoff=datetime.now(UTC)), 0)
            writer.resolve_restore_marker()
            self.assertFalse(writer.restore_marker_unresolved())
            writer.record_event("AFTER_RESTORE", {"debit":18})
            rows = list(writer._conn.execute("SELECT kind FROM runtime_events ORDER BY event_id"))
            self.assertEqual([row[0] for row in rows], ["BEFORE_RECLAIM", "AFTER_RESTORE"])
            self.assertEqual([row[0] for row in writer._conn.execute(
                "SELECT event_id FROM runtime_events ORDER BY event_id")], [77,89])
        self.assertFalse(any(".i2-reclaim" in item["path"] for item in packed["entries"]))
        self.assertTrue(intent.exists())
        if os.environ.get("I2_PRINT_RECLAIM_BACKUP_ORACLE"):
            print(json.dumps({"layout":"nested/full" if nested else "sibling/mutable",
                "trace":["native:FINALIZED","terminal-binding:verified","backup:PASS",
                         "restore:raw-PASS","new-inode:verified","native:open",
                         "recovery-gap:0","marker:resolved","writer:event-89"],
                "inventory_sha256":packed["inventory_sha256"],
                "source_receipt_preserved":intent.exists(),"receipt_in_backup":False,
                "source_inode":source.stat().st_ino,"restored_inode":(restored/relative).stat().st_ino,
                "rows_and_ROWIDs_preserved":True,"runtime_event_ids":[77,89]}, sort_keys=True))

    def test_unfinished_native_reclaim_refuses_before_snapshot_sqlite_capture(self) -> None:
        _source, _relative, intent = self._native_reclaim_backup_fixture(nested=True, finalize=False)
        before = intent.read_bytes()
        with patch.object(remote, "consistent_sqlite_backup", wraps=remote.consistent_sqlite_backup) as capture:
            with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_RECLAIM_RECOVERY_REQUIRED"):
                self.full()
            capture.assert_not_called()
        self.assertEqual(intent.read_bytes(), before)
        self.assertEqual(list(self.sink.glob("BACKUP_*.zip")), [])

    def test_unfinished_native_reclaim_refuses_direct_sqlite_backup(self) -> None:
        source, _relative, _intent = self._native_reclaim_backup_fixture(nested=False, finalize=False)
        target = Path(self.temp.name)/"must-not-capture.sqlite"
        with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_RECLAIM_RECOVERY_REQUIRED"):
            remote.consistent_sqlite_backup(source, target)
        self.assertFalse(target.exists())

    def test_native_reclaim_missing_main_rename_gap_refuses_before_capture(self) -> None:
        source, _relative, intent = self._native_reclaim_backup_fixture(
            nested=True, finalize=False, phase="ORIGINAL_MOVED")
        before = intent.read_bytes()
        self.assertFalse(source.exists())
        with patch.object(remote, "consistent_sqlite_backup", wraps=remote.consistent_sqlite_backup) as capture:
            with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_RECLAIM_RECOVERY_REQUIRED"):
                self.full()
            capture.assert_not_called()
        self.assertFalse(source.exists())
        self.assertEqual(intent.read_bytes(), before)
        self.assertEqual(list(self.sink.glob("BACKUP_*.zip")), [])

    def test_reclaim_terminal_receipt_wrong_inode_is_not_silently_excluded(self) -> None:
        _source, _relative, intent = self._native_reclaim_backup_fixture(nested=True, finalize=True)
        stale = json.loads(intent.read_text())
        stale["final_db_binding"]["inode"] += 1
        intent.write_text(json.dumps(stale), encoding="utf-8")
        with patch.object(remote, "consistent_sqlite_backup", wraps=remote.consistent_sqlite_backup) as capture:
            with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_RECLAIM_RECOVERY_REQUIRED"):
                self.full()
            capture.assert_not_called()
        self.assertEqual(json.loads(intent.read_text()), stale)

    def test_old_api_backup_with_sqlite_sidecar_is_rejected_before_decoration(self) -> None:
        packed=self.full()
        relative=OPS+"-wal"
        payload=b"incompatible-live-sidecar"
        def add_sidecar(body):
            body["entries"].append({"path":relative,"bytes":len(payload),
                "sha256":hashlib.sha256(payload).hexdigest(),"kind":"FILE_SNAPSHOT"})
            body["inventory_sha256"]=remote.logical_inventory_sha256(body["entries"])
        bundle=self.rewrite(self.sink/packed["bundle"],manifest_change=add_sidecar,extra=[(relative,payload)])
        with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_SQLITE_SIDECAR_CONFLICT"):
            remote.restore_backup_isolated(bundle=bundle,dest_root=Path(self.temp.name)/"old-sidecar-refused")

    def chain(self) -> tuple[Path, list[Path], dict]:
        extra = "local/factory_v1/deleted.sqlite"
        shutil.copyfile(self.root / OPS, self.root / extra)
        self.config["backup"]["source_relative_paths"].append(extra)
        packed = self.full()
        full = self.rewrite(self.sink / packed["bundle"], stored=True)
        self.mutate("delta one")
        (self.root / RDP / "keep.json").unlink()
        (self.root / RDP / "added.json").write_text("added", encoding="utf-8")
        first, first_inventory = self.delta(packed)
        self.mutate("delta two")
        (self.root / extra).unlink()
        self.config["backup"]["source_relative_paths"].remove(extra)
        second, final_inventory = self.delta(first_inventory)
        return full, [self.sink / first["bundle"], self.sink / second["bundle"]], final_inventory

    def test_mixed_chain_changed_and_deleted_sqlite_final_marker_and_keys(self) -> None:
        full, deltas, inventory = self.chain()
        restored = Path(self.temp.name) / "chain-restored"
        result = remote.restore_incremental_chain_isolated(full_bundle=full, deltas=deltas,
            dest_root=restored, expected_inventory_sha256=inventory["inventory_sha256"])
        self.assertEqual(result["raw_inventory_sha256"], inventory["inventory_sha256"])
        self.assertTrue(result["restore_marker_unresolved"])
        self.assertFalse((restored / RDP / "keep.json").exists())
        self.assertFalse((restored / "local/factory_v1/deleted.sqlite").exists())
        with closing(sqlite3.connect(restored / OPS)) as conn:
            self.assertEqual(conn.execute("SELECT payload,provider_calls,credits FROM semantic_state").fetchone(), ("delta two",1199,1200))
            self.assertEqual(conn.execute("SELECT resolved FROM restore_markers").fetchone(), (0,))
        self.assertNotEqual(remote._sha256_file(restored / OPS), next(item["sha256"] for item in inventory["entries"] if item["path"] == OPS))

    def test_missing_reordered_and_wrong_expected_inventory_refuse_without_marker(self) -> None:
        full, deltas, inventory = self.chain()
        cases = [(deltas[1:], inventory["inventory_sha256"]),
                 (list(reversed(deltas)), inventory["inventory_sha256"]),
                 (deltas[:1], inventory["inventory_sha256"]),
                 (deltas, "0" * 64)]
        for index, (ordered, expected) in enumerate(cases):
            with self.subTest(case=index):
                restored = Path(self.temp.name) / f"refused-{index}"
                with self.assertRaisesRegex(remote.RemoteOpsError, "RESTORE_INVENTORY_MISMATCH"):
                    remote.restore_incremental_chain_isolated(full_bundle=full, deltas=ordered,
                        dest_root=restored, expected_inventory_sha256=expected)
                with closing(sqlite3.connect(restored / OPS)) as conn:
                    self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='restore_markers'").fetchone())

    def test_full_declared_inventory_and_extracted_bytes_are_both_checked(self) -> None:
        packed = self.full()
        source = self.sink / packed["bundle"]
        variants = [self.rewrite(source, manifest_change=lambda body: body.update(inventory_sha256="0"*64)),
                    self.rewrite(source, corrupt=OPS),
                    self.rewrite(source, omit=[OPS]),
                    self.rewrite(source, extra=[("unexpected.txt", b"extra")]),
                    self.rewrite(source, duplicate=OPS)]
        for index, bundle in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(remote.RemoteOpsError):
                remote.restore_backup_isolated(bundle=bundle, dest_root=Path(self.temp.name)/f"bad-full-{index}")

    def test_delta_rejects_omitted_corrupt_unexpected_duplicate_and_unsafe_entries(self) -> None:
        full, deltas, inventory = self.chain()
        source = deltas[0]
        variants = [self.rewrite(source, omit=[OPS]), self.rewrite(source, corrupt=OPS),
                    self.rewrite(source, extra=[("unexpected.txt", b"extra")]),
                    self.rewrite(source, duplicate=OPS),
                    self.rewrite(source, manifest_change=lambda body: body["changed"][0].update(path="../escape")),
                    self.rewrite(source, manifest_change=lambda body: body["deleted"].append("not-present")),
                    self.rewrite(source, manifest_change=lambda body: body.update(result_inventory_sha256="0"*64))]
        for index, delta in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(remote.RemoteOpsError):
                remote.restore_incremental_chain_isolated(full_bundle=full, deltas=[delta, deltas[1]],
                    dest_root=Path(self.temp.name)/f"bad-delta-{index}", expected_inventory_sha256=inventory["inventory_sha256"])

    def test_delta_packaging_refuses_false_base_and_live_sqlite_recapture(self) -> None:
        packed = self.full()
        self.mutate("changed")
        with remote.backup_payload_snapshot(self.root, self.config) as snapshot:
            inventory = remote.scan_backup_inventory(self.root, config=self.config, snapshot=snapshot)
            with self.assertRaisesRegex(remote.RemoteOpsError, "DELTA_BASE_INVENTORY_MISMATCH"):
                remote.package_delta_backup(self.root, base_manifest={**packed,"inventory_sha256":"0"*64},
                    current_entries=inventory["entries"], sink=self.sink, snapshot=snapshot)
        self.mutate("newer than inventory")
        with self.assertRaisesRegex(remote.RemoteOpsError, "SNAPSHOT_BYTES_MISMATCH"):
            remote.package_delta_backup(self.root, base_manifest=packed,
                current_entries=inventory["entries"], sink=self.sink)

    def test_capture_budget_and_active_writer_defer_cleanly(self) -> None:
        with patch.object(remote, "BACKUP_CAPTURE_FENCE_SECONDS", -1):
            with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED"):
                with remote.backup_payload_snapshot(self.root, self.config):
                    self.fail("over-budget capture admitted")
        self.assertEqual(list((self.root / remote.BACKUP_SNAPSHOT_STAGING_RELATIVE).glob("capture-*")), [])
        with closing(sqlite3.connect(self.root / OPS)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(remote.RemoteOpsError, "WRITER_BUSY"):
                with remote.backup_payload_snapshot(self.root, self.config):
                    self.fail("active write admitted")
            conn.rollback()
        self.mutate("writer recovers after refused capture")

    def test_fresh_process_crash_capture_is_reclaimed_before_next_checkpoint(self) -> None:
        child = """
import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from solana_alpha_lab.factory import remote_ops as remote
root,sink,config=Path(sys.argv[2]),Path(sys.argv[3]),json.loads(sys.argv[4])
if sys.argv[5]=='crash':
    with remote.backup_plane_lock(root):
        with remote.backup_payload_snapshot(root,config):
            os._exit(23)
print(json.dumps(remote.package_backup(root,config=config,sink_override=sink,prune_superseded=False)))
"""
        staging=self.root/remote.BACKUP_SNAPSHOT_STAGING_RELATIVE
        for attempt in range(2):
            crashed=subprocess.run([sys.executable,"-c",child,str(ROOT/"src"),str(self.root),str(self.sink),
                json.dumps(self.config),"crash"],capture_output=True,text=True,timeout=20)
            self.assertEqual(crashed.returncode,23,crashed.stderr)
            orphans=list(staging.glob("capture-*"))
            self.assertEqual(len(orphans),1)
            self.assertTrue((orphans[0]/OPS).is_file())
            recovered=subprocess.run([sys.executable,"-c",child,str(ROOT/"src"),str(self.root),str(self.sink),
                json.dumps(self.config),"full"],capture_output=True,text=True,timeout=20)
            self.assertEqual(recovered.returncode,0,recovered.stderr)
            self.assertEqual(list(staging.glob("capture-*")),[],f"capture leaked after recovery {attempt}")
            result=json.loads(recovered.stdout)
            self.assertTrue((self.sink/result["bundle"]).is_file())

    def test_unknown_capture_is_preserved_and_blocks_new_allocation(self) -> None:
        staging=self.root/remote.BACKUP_SNAPSHOT_STAGING_RELATIVE
        unknown=staging/"capture-unknown-owner"
        unknown.mkdir(parents=True)
        evidence=unknown/"source.sqlite"
        evidence.write_bytes(b"unknown immutable evidence")
        with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED"):
            self.full()
        self.assertEqual(evidence.read_bytes(),b"unknown immutable evidence")
        self.assertEqual(list(staging.glob("capture-*")),[unknown])

    def test_active_capture_is_preserved_and_defers_other_capture(self) -> None:
        with remote.backup_payload_snapshot(self.root,self.config) as snapshot:
            staged=snapshot.staged_path(OPS)
            with self.assertRaisesRegex(remote.RemoteOpsError,"WRITER_BUSY"):
                self.full()
            self.assertTrue(staged.is_file())
        self.assertFalse(staged.exists())
        self.full()

    def test_interrupted_apply_is_disposable_and_fresh_retry_restores_same_bytes(self) -> None:
        full, deltas, inventory = self.chain()
        broken = Path(self.temp.name)/"interrupted"
        real = remote.apply_delta_bundle
        def interrupted(delta, root, **kwargs):
            with patch.object(remote, "_stream_copy_hashed", side_effect=OSError("injected isolated disk failure")):
                return real(delta, root, **kwargs)
        with patch.object(remote, "apply_delta_bundle", side_effect=interrupted):
            with self.assertRaises(OSError):
                remote.restore_incremental_chain_isolated(full_bundle=full, deltas=deltas,
                    dest_root=broken, expected_inventory_sha256=inventory["inventory_sha256"])
        result = remote.restore_incremental_chain_isolated(full_bundle=full,deltas=deltas,
            dest_root=Path(self.temp.name)/"retry",expected_inventory_sha256=inventory["inventory_sha256"])
        self.assertEqual(result["raw_inventory_sha256"], inventory["inventory_sha256"])

    def _seed_real_control_activation(self) -> tuple[dict, dict]:
        from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            activate_schedule, authorize_schedule, prepare_schedule_authority)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        self.config["backup"]["recursive_relative_paths"] = [f"{RDP}/datasets/publication_jobs"]
        (self.root/RDP/"datasets/publication_jobs").mkdir(parents=True)
        now = datetime(2026,9,1,0,10,tzinfo=UTC)
        document = load_observation_schedule(ROOT,"tests/fixtures/observation_schedule/x300_y900.yaml")
        store = ObservationScheduleStore(self.root/OPS)
        try:
            prepared = prepare_schedule_authority(root=ROOT,data_root=self.root/RDP,store=store,
                document=document,now=now,producer_git_sha="c"*40)
            authorized = authorize_schedule(root=ROOT,data_root=self.root/RDP,store=store,
                schedule_sha256=document["schedule_sha256"], phrase=prepared["authority_request"]["exact_owner_phrase"],
                now=now,producer_git_sha="c"*40)
            activate_schedule(data_root=self.root/RDP,store=store,schedule_sha256=document["schedule_sha256"],
                activation_id="ACT-I2-RESTORE",now=now,producer_git_sha="c"*40)
            activation = store.get_activation(document["schedule_sha256"],"ACT-I2-RESTORE")
        finally:
            store.close()
        return activation, authorized

    def _assert_recovery_closure_deadline(self, phase: str) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore
        self._seed_real_control_activation()
        before = _raw_sql_readback(self.root/OPS)
        read = ResearchStore._read_manifest
        fences = remote._capture_writer_fences
        clock = {}
        reads, blocked = [], []

        @contextmanager
        def observed_fence(sources):
            clock["start"] = time.monotonic()
            with fences(sources):
                yield

        def delayed_native_read(store, path):
            live = path.is_relative_to(self.root/RDP)
            if live != (phase == "dependencies"):
                return read(store,path)
            reads.append(time.monotonic()-clock["start"])
            with closing(sqlite3.connect(self.root/OPS,timeout=0)) as peer:
                try:
                    peer.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    blocked.append(True)
                else:
                    blocked.append(False)
                    peer.rollback()
            time.sleep(0.06)
            return read(store,path)

        started = time.monotonic()
        with patch.object(remote,"BACKUP_CAPTURE_FENCE_SECONDS",0.10), patch.object(
                remote,"_capture_writer_fences",observed_fence), patch.object(
                ResearchStore,"_read_manifest",delayed_native_read):
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED"):
                self.full()
        elapsed = time.monotonic()-started
        print("I2_CAPTURE_CLOSURE_DEADLINE "+json.dumps({"phase":phase,"budget_seconds":0.10,
            "injected_native_read_seconds":0.06,"manifest_read_starts_seconds":reads,
            "writer_blocked_during_reads":blocked,"refusal_wall_seconds":round(elapsed,3)}))
        self.assertTrue(reads)
        self.assertEqual(blocked,[True]*len(reads))
        self.assertLessEqual(len(reads),2)
        self.assertTrue(all(stamp < 0.10 for stamp in reads))
        self.assertEqual(_raw_sql_readback(self.root/OPS),before)
        with closing(sqlite3.connect(self.root/OPS,timeout=0)) as peer:
            peer.execute("BEGIN IMMEDIATE")
            peer.rollback()
        self.assertFalse(self.sink.exists() and list(self.sink.glob("*.zip")))
        staging = self.root/remote.BACKUP_SNAPSHOT_STAGING_RELATIVE
        self.assertFalse(list(staging.glob("capture-*")))
        self.assertFalse(list(self.root.rglob("*.published")))

    def test_recovery_closure_checks_deadline_before_next_native_manifest_read(self) -> None:
        self._assert_recovery_closure_deadline("dependencies")

    def test_control_lookup_checks_deadline_inside_native_history(self) -> None:
        self._assert_recovery_closure_deadline("control")

    def test_recovery_manifest_census_refuses_before_materialized_native_reads(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore
        self._seed_real_control_activation()
        directory=self.root/RDP/"research/manifests/partitions"
        for number in range(3):
            (directory/f"unmatched-{number}.txt").write_text("unmatched",encoding="utf-8")
        with patch.object(remote,"BACKUP_PARTITION_SCAN_MAX_FILES",3), patch.object(
                ResearchStore,"_read_manifest",side_effect=AssertionError("native read after capped census")) as read:
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED"):
                self.full()
        self.assertEqual(read.call_count,0)
        self.assertFalse(self.sink.exists())

    def test_recovery_partition_size_refuses_before_native_materialization(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore
        self._seed_real_control_activation()
        source = sorted((self.root/RDP/"research/manifests/partitions").glob("partition-*.json"))[0]
        manifest = ResearchStore(self.root/RDP)._read_manifest(source)
        partition = self.root/RDP/manifest.logical_location
        maximum = source.stat().st_size + partition.stat().st_size - 1
        with patch.object(remote,"BACKUP_PARTITION_SCAN_MAX_BYTES",maximum), patch.object(
                ResearchStore,"_verify_partition",side_effect=AssertionError("oversized native materialization")) as verify:
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED"):
                self.full()
        self.assertEqual(verify.call_count,0)
        self.assertFalse(self.sink.exists())

    def test_expired_capture_sql_interrupt_keeps_budget_refusal_and_releases_writer(self) -> None:
        token = remote._CAPTURE_CLOSURE_BUDGET.set({
            "deadline":time.monotonic()+0.02,"counts":{},"bytes":0})
        try:
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED"):
                with remote._capture_writer_fences([(OPS,self.root/OPS,True)]):
                    with closing(sqlite3.connect(":memory:")) as conn, remote._capture_sql_deadline(conn):
                        conn.execute("WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT SUM(x) FROM n").fetchone()
        finally:
            remote._CAPTURE_CLOSURE_BUDGET.reset(token)
        with closing(sqlite3.connect(self.root/OPS,timeout=0)) as peer:
            peer.execute("BEGIN IMMEDIATE")
            peer.rollback()

    def test_actual_parquet_rows_and_uncompressed_bytes_refuse_before_native_verifier(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq
        from solana_alpha_lab.factory.research_store import ResearchStore
        self._seed_real_control_activation()
        source = sorted((self.root/RDP/"research/manifests/partitions").glob("partition-*.json"))[0]
        manifest = ResearchStore(self.root/RDP)._read_manifest(source)
        path = self.root/RDP/manifest.logical_location
        original = pq.read_table(path)
        for kind in ("actual_rows", "uncompressed_bytes"):
            with self.subTest(kind=kind):
                if kind == "actual_rows":
                    table = pa.concat_tables([original,original])
                else:
                    table = original.set_column(original.schema.get_field_index("payload_json"),
                        "payload_json",pa.array(["x"*65536]))
                pq.write_table(table,path,compression="zstd")
                metadata = pq.ParquetFile(path).metadata
                uncompressed = sum(metadata.row_group(i).column(j).total_uncompressed_size
                    for i in range(metadata.num_row_groups) for j in range(metadata.num_columns))
                maximum = path.stat().st_size + uncompressed - 1
                token = remote._CAPTURE_CLOSURE_BUDGET.set({
                    "deadline":time.monotonic()+5,"counts":{},"bytes":0})
                try:
                    with patch.object(remote,"BACKUP_SOURCE_SCAN_MAX_PATHS",1 if kind == "actual_rows" else 65536), patch.object(
                            remote,"BACKUP_PARTITION_SCAN_MAX_BYTES",maximum), patch.object(
                            ResearchStore,"_verify_partition",side_effect=AssertionError("unbounded native materialization")) as verify:
                        expected = ("BACKUP_RECOVERY_DEPENDENCY_BUDGET_EXCEEDED" if kind == "actual_rows"
                            else "BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED")
                        with self.assertRaisesRegex(remote.RemoteOpsError,expected):
                            remote._capture_research_store(self.root/RDP)._verify_partition(manifest)
                    self.assertEqual(verify.call_count,0)
                finally:
                    remote._CAPTURE_CLOSURE_BUDGET.reset(token)

    def test_control_root_scan_charges_unmatched_directories(self) -> None:
        isolated=Path(self.temp.name)/"unmatched-control-root"
        isolated.mkdir()
        for number in range(3):
            (isolated/f"unmatched-{number}").mkdir()
        token=remote._CAPTURE_CLOSURE_BUDGET.set({
            "deadline":time.monotonic()+5,"counts":{},"bytes":0})
        try:
            with patch.object(remote,"BACKUP_SOURCE_SCAN_MAX_PATHS",2):
                with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_RECOVERY_DEPENDENCY_BUDGET_EXCEEDED"):
                    remote._verify_recovery_control(isolated)
        finally:
            remote._CAPTURE_CLOSURE_BUDGET.reset(token)

    def test_real_control_event_closure_survives_mutable_only_restore(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore
        activation,authorized = self._seed_real_control_activation()
        packed = self.full()
        self.assertNotIn(f"{RDP}/keep.json", {item["path"] for item in packed["entries"]})
        self.assertTrue(any("research/manifests/partitions/" in item["path"] for item in packed["entries"]))
        self.assertFalse(any("write_lookup_v1" in item["path"] for item in packed["entries"]))
        restored = Path(self.temp.name)/"control-restored"
        result = remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"],deltas=[],
            dest_root=restored,expected_inventory_sha256=packed["inventory_sha256"])
        self.assertEqual(result["recovery_control"],{"transitions":1,"authorities":1})
        research = ResearchStore(restored/RDP,create_if_missing=False)
        self.assertIsNotNone(research.find_record(activation["last_transition_event_id"]))
        self.assertIsNotNone(research.find_record(f"OBS-AUTHZ-{authorized['receipt_sha256'][:16].upper()}"))
        # A persisted ACTIVE row without the independently committed event is a gap.
        manifests = list((self.root/RDP/"research/manifests/partitions").glob("*.json"))
        for path in manifests:
            body = json.loads(path.read_text(encoding="utf-8"))
            if body["partition_id"].startswith("RESEARCH-TXN-OBS-TRANS-"):
                path.unlink()
        with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_RECOVERY_TRANSITION_EVENT_MISSING"):
            self.full()

    def _legacy_control_checkpoint(self, state: str) -> dict:
        """Run the pinned, unmodified pre-I2 producer, then today's daily caller."""
        from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
        from solana_alpha_lab.factory import offhost_backup as offhost
        from solana_alpha_lab.factory.hot90_activation import write_hot90_runtime_state
        from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
        from solana_alpha_lab.factory.research_store import ResearchStore

        # Native lifecycle, SQLite schema and packaging all come from the exact
        # historical producer. No new retention tables/source UUID enter it.
        modules = {}
        producer_hashes = {}
        for filename in ("observation_schedule_store", "observation_schedule_lifecycle",
                         "remote_ops", "offhost_backup"):
            relative = f"src/solana_alpha_lab/factory/{filename}.py"
            source = subprocess.run(["git", "show", f"{LEGACY_PRODUCER_BASE}:{relative}"],
                cwd=ROOT, check=True, capture_output=True).stdout
            producer_hashes[filename] = hashlib.sha256(source).hexdigest()
            name = f"_i2_legacy_{filename}_{id(self)}"
            module = types.ModuleType(name)
            module.__file__ = str(ROOT/relative)
            sys.modules[name] = module
            self.addCleanup(sys.modules.pop, name, None)
            bindings = {f"solana_alpha_lab.factory.{key}": value for key, value in modules.items()}
            with patch.dict(sys.modules, bindings):
                exec(compile(source, f"{LEGACY_PRODUCER_BASE}:{relative}", "exec"), module.__dict__)
            modules[filename] = module
        lifecycle = modules["observation_schedule_lifecycle"]
        _seed_tree(self.root)
        for relative in ("configs/observation_schedule_runtime_v1.yaml",
                         "catalog/schemas/observation_schedule_runtime_v1.schema.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        (self.root/RDP/"datasets/publication_jobs").mkdir(parents=True)
        write_hot90_runtime_state(self.root, {"activation_stage": "DURABILITY_CUTOVER",
            "production_compaction_enabled": False, "production_eviction_enabled": False,
            "drive_writes_enabled": True})
        now = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
        document = load_observation_schedule(ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml")
        with closing(modules["observation_schedule_store"].ObservationScheduleStore(self.root/OPS)) as store:
            prepared = lifecycle.prepare_schedule_authority(root=ROOT, data_root=self.root/RDP, store=store,
                document=document, now=now, producer_git_sha="c"*40)
            authorized = lifecycle.authorize_schedule(root=ROOT, data_root=self.root/RDP, store=store,
                schedule_sha256=document["schedule_sha256"],
                phrase=prepared["authority_request"]["exact_owner_phrase"], now=now, producer_git_sha="c"*40)
            lifecycle.activate_schedule(data_root=self.root/RDP, store=store,
                schedule_sha256=document["schedule_sha256"], activation_id="ACT-LEGACY-I2",
                now=now, producer_git_sha="c"*40)
            if state == "DRAINING":
                drained = lifecycle.drain_expired_admission(data_root=self.root/RDP, store=store,
                    schedule_sha256=document["schedule_sha256"], activation_id="ACT-LEGACY-I2",
                    now=datetime(2026, 9, 2, 0, 1, tzinfo=UTC), producer_git_sha="c"*40)
                self.assertEqual(drained["terminal"], "DRAINED")
        expected_sql = _raw_sql_readback(self.root/OPS)
        self.assertEqual(expected_sql["activation_rows"][0][2], state)
        self.assertNotIn("retention_control", expected_sql)
        event_ids = [expected_sql["activation_rows"][0][3],
                     f"OBS-AUTHZ-{authorized['receipt_sha256'][:16].upper()}"]
        research = ResearchStore(self.root/RDP, create_if_missing=False)
        expected_events = {identity: research.find_record(identity).model_dump(mode="json")
                           for identity in event_ids}

        credentials = self.root/"fixture-rclone.conf"
        credentials.write_text("[factory-gdrive]\ntype = drive\n", encoding="utf-8")
        credentials.chmod(0o600)
        runner = FakeRcloneRunner()
        legacy = modules["offhost_backup"]
        legacy_config = replace(legacy.load_offhost_config(self.root), rclone_config_absolute=credentials)
        environment = {remote.BACKUP_SINK_ENV: str(self.sink)}
        old_receipt = legacy.run_offhost_checkpoint(self.root, mode="daily", config=legacy_config,
            environ=environment, runner=runner, now=datetime(2026, 9, 3, 0, 45, tzinfo=UTC))
        legacy_chain = json.loads((self.root/legacy_config.chain_relative).read_text(encoding="utf-8"))
        self.assertEqual(legacy_chain["ordered_deltas"], [])
        base = legacy_chain["base_full"]
        with zipfile.ZipFile(self.sink/base["filename"]) as archive:
            old_manifest = json.loads(archive.read("BACKUP_MANIFEST.json"))
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
            self.assertFalse(any("/research/" in item["path"] for item in old_manifest["entries"]))
        self.assertEqual(len(old_manifest["entries"]), 3)
        config = replace(offhost.load_offhost_config(self.root), rclone_config_absolute=credentials)
        receipt = offhost.run_offhost_checkpoint(self.root, mode="daily", config=config,
            environ=environment, runner=runner, now=datetime(2026, 9, 4, 0, 45, tzinfo=UTC))
        self.assertEqual(receipt["terminal"], "DAILY_DELTA_VERIFIED")
        chain = offhost.read_chain_state(self.root, config)
        self.assertEqual(chain["base_full"], base)
        self.assertEqual(len(chain["ordered_deltas"]), 1)
        # This is a separate transport view containing only remotely committed bytes.
        independent = Path(self.temp.name)/"independent-remote"
        independent.mkdir()
        for remote_name, payload in runner.payloads.items():
            (independent/Path(remote_name).name).write_bytes(payload)
        expected_files = [{key: item[key] for key in ("path", "sha256", "bytes")}
                          for item in chain["tip_entries"]]
        self.assertEqual(_raw_sql_readback(self.root/OPS), expected_sql)
        self.root.rename(self.root.with_name("source-unavailable"))
        return {"base": base, "legacy_receipt": old_receipt, "receipt": receipt,
                "objects": independent, "chain": chain, "sql": expected_sql,
                "events": expected_events, "files": expected_files, "producer_sha256": producer_hashes}

    def test_actual_legacy_active_full_new_daily_delta_restores_final_control_closure(self) -> None:
        self._assert_actual_legacy_checkpoint_restores("ACTIVE")

    def test_actual_legacy_draining_full_new_daily_delta_restores_final_control_closure(self) -> None:
        self._assert_actual_legacy_checkpoint_restores("DRAINING")

    def test_actual_legacy_full_and_final_missing_control_event_refuse_without_marker(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStoreError

        fixture = self._legacy_control_checkpoint("ACTIVE")
        full = fixture["objects"]/fixture["base"]["filename"]
        for label in ("standalone", "chain-without-closure"):
            target = Path(self.temp.name)/label
            with self.subTest(label=label), patch.object(remote, "_decorate_restore") as marker:
                with self.assertRaisesRegex(ResearchStoreError, "RESEARCH_STORE_NOT_PRESENT"):
                    if label == "standalone":
                        remote.restore_backup_isolated(bundle=full, dest_root=target)
                    else:
                        remote.restore_incremental_chain_isolated(full_bundle=full, deltas=[], dest_root=target)
                marker.assert_not_called()
                with closing(sqlite3.connect((target/OPS).as_uri()+"?mode=ro&immutable=1", uri=True)) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM restore_markers").fetchone()[0], 0)

        delta = fixture["objects"]/fixture["chain"]["ordered_deltas"][0]["filename"]
        with zipfile.ZipFile(delta) as archive:
            missing = next(name for name in archive.namelist()
                if "/research/manifests/partitions/" in name and
                json.loads(archive.read(name))["partition_id"].startswith("RESEARCH-TXN-OBS-TRANS-"))
        # Preserve valid raw-link hashes/membership while omitting a required
        # native event descriptor: byte integrity alone must not grant recovery.
        expected = [item for item in fixture["files"] if item["path"] != missing]
        inventory = hashlib.sha256(json.dumps(sorted(expected, key=lambda item:item["path"]),
            separators=(",", ":"), sort_keys=True).encode()).hexdigest()
        def omit_control(manifest):
            manifest["changed"] = [item for item in manifest["changed"] if item["path"] != missing]
            manifest["result_inventory_sha256"] = inventory
        incomplete = self.rewrite(delta, manifest_change=omit_control, omit=(missing,))
        target = Path(self.temp.name)/"final-missing-control"
        with patch.object(remote, "apply_delta_bundle", wraps=remote.apply_delta_bundle) as apply:
            with patch.object(remote, "_decorate_restore") as marker:
                with self.assertRaisesRegex(remote.RemoteOpsError, "BACKUP_RECOVERY_TRANSITION_EVENT_MISSING"):
                    remote.restore_incremental_chain_isolated(full_bundle=full, deltas=[incomplete],
                        dest_root=target, expected_inventory_sha256=inventory)
                marker.assert_not_called()
            self.assertEqual(apply.call_count, 1)
        actual = sorted([{"path":path.relative_to(target).as_posix(), "bytes":path.stat().st_size,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for path in target.rglob("*")
            if path.is_file()], key=lambda item:item["path"])
        self.assertEqual(actual, sorted(expected, key=lambda item:item["path"]))
        with closing(sqlite3.connect((target/OPS).as_uri()+"?mode=ro&immutable=1", uri=True)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM restore_markers").fetchone()[0], 0)

    def _assert_actual_legacy_checkpoint_restores(self, state: str) -> None:
        fixture = self._legacy_control_checkpoint(state)
        destination = Path(self.temp.name)/"independent-restored"
        program = r'''
import hashlib, json, sqlite3, sys
from contextlib import closing
from pathlib import Path
from tests.test_i2_backup_legacy_storage_v1 import _raw_sql_readback, OPS, RDP
from solana_alpha_lab.factory import remote_ops as remote
from solana_alpha_lab.factory.offhost_backup import restore_from_recovery_checkpoint
from solana_alpha_lab.factory.research_store import ResearchStore
objects, checkpoint, destination = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
trace, raw = [], {}
def files():
    return sorted([{'path':p.relative_to(destination).as_posix(), 'bytes':p.stat().st_size,
                    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in destination.rglob('*') if p.is_file()], key=lambda item:item['path'])
apply, control, marker = remote.apply_delta_bundle, remote._verify_recovery_control, remote._decorate_restore
def traced_apply(*args, **kwargs):
    trace.append('delta:start')
    value = apply(*args, **kwargs)
    trace.append('delta:raw-verified')
    return value
def traced_control(*args, **kwargs):
    trace.append('control:start')
    value = control(*args, **kwargs)
    trace.append('control:verified')
    return value
def traced_marker(*args, **kwargs):
    raw['files'] = files()
    raw['sql'] = _raw_sql_readback(destination/OPS, isolated=True)
    trace.append('marker:last')
    return marker(*args, **kwargs)
remote.apply_delta_bundle, remote._verify_recovery_control, remote._decorate_restore = traced_apply, traced_control, traced_marker
try:
    restored = restore_from_recovery_checkpoint(checkpoint_path=objects/checkpoint,
        objects_dir=objects, dest_root=destination)
    research = ResearchStore(destination/RDP, create_if_missing=False)
    events = {event.record_id:event.model_dump(mode='json') for event in research.iter_committed_records()}
    with closing(sqlite3.connect(destination/OPS)) as conn:
        markers = list(conn.execute('SELECT marker_id,resolved FROM restore_markers'))
    print(json.dumps({'ok':True,'trace':trace,'raw':raw,'events':events,
        'markers':markers,'sql_after':_raw_sql_readback(destination/OPS),
        'inventory_sha256':restored['raw_inventory_sha256'], 'control':restored['recovery_control']}))
except Exception as exc:
    print(json.dumps({'ok':False,'trace':trace,'error':type(exc).__name__+':'+str(exc),
                      'partial_files':files()}))
'''
        environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT/"src"), str(ROOT))))
        result = subprocess.run([sys.executable, "-B", "-c", program, str(fixture["objects"]),
            fixture["receipt"]["checkpoint_filename"], str(destination)],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        oracle = json.loads(result.stdout)
        if os.environ.get("I2_PRINT_LEGACY_ORACLE"):
            print(json.dumps({"state":state,"producer_base":LEGACY_PRODUCER_BASE,
                "producer_sha256":fixture["producer_sha256"],"base":fixture["base"],
                "legacy_terminal":fixture["legacy_receipt"]["terminal"],
                "new_receipt":fixture["receipt"],"oracle":oracle}, sort_keys=True))
        self.assertTrue(oracle["ok"], {"state":state,"oracle":oracle})
        self.assertEqual(oracle["trace"], ["delta:start", "delta:raw-verified",
            "control:start", "control:verified", "marker:last"])
        self.assertEqual(oracle["raw"]["files"], sorted(fixture["files"], key=lambda item:item["path"]))
        self.assertEqual(oracle["raw"]["sql"], fixture["sql"])
        self.assertEqual(oracle["sql_after"], fixture["sql"])
        self.assertEqual(oracle["inventory_sha256"], fixture["chain"]["tip_inventory_sha256"])
        self.assertEqual(oracle["control"], {"transitions":1,"authorities":1})
        self.assertEqual(oracle["markers"], [["UNRESOLVED",0]])
        for event_id, payload in fixture["events"].items():
            self.assertEqual(oracle["events"][event_id], payload)

    def test_open_publication_artifact_and_member_prefix_closure(self) -> None:
        self.config["backup"]["recursive_relative_paths"] = [f"{RDP}/datasets/publication_jobs"]
        job_root = self.root/RDP/"datasets/publication_jobs/open"
        job_root.mkdir(parents=True)
        artifacts = {"datasets/observations/data.parquet":b"observation",
                     "datasets/members/day/second.parquet":b"second",
                     "datasets/members/day/first.parquet":b"first"}
        for relative,payload in artifacts.items():
            path=self.root/RDP/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(payload)
        sidecar=self.root/RDP/"datasets/members/day/members.layout.json"
        sidecar.write_text(json.dumps({"unit_rel":"datasets/members/day/unit.json"}),encoding="utf-8")
        unit=self.root/RDP/"datasets/members/day/unit.json"
        unit.write_text(json.dumps({"publications":[{"rel":path,"sha256":hashlib.sha256(artifacts[path]).hexdigest()}
            for path in ("datasets/members/day/first.parquet","datasets/members/day/second.parquet")]}),encoding="utf-8")
        (job_root/(("a"*64)+".json")).write_text(json.dumps({"stage":"ARTIFACTS","content_sha256":"a"*64,
            "parquet_rel":"datasets/observations/data.parquet","member_rel":"datasets/members/day/second.parquet",
            "dataset_manifest_id":"dataset-one"}),encoding="utf-8")
        packed=self.full()
        paths={item["path"] for item in packed["entries"]}
        self.assertTrue({f"{RDP}/{relative}" for relative in artifacts} <= paths)
        self.assertIn(sidecar.relative_to(self.root).as_posix(),paths)
        self.assertIn(unit.relative_to(self.root).as_posix(),paths)
        (self.root/RDP/"datasets/members/day/first.parquet").unlink()
        with self.assertRaises(remote.RemoteOpsError):
            self.full()

    def test_managed_revocation_shared_debits_child_and_open_publication_recovery_without_source(self) -> None:
        from tests.test_managed_collection_continuity_v1 import D0,D1,ManagedScenario
        from solana_alpha_lab.factory.observation_panel_publisher import repair_open_publication_jobs
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.observation_schedule_lifecycle import activation_transition_research_event_proven

        sc=ManagedScenario(self.root/RDP)
        with patch.dict(os.environ,{remote.BACKUP_SINK_ENV:str(sc.sink)}):
            sc.commission_account()
            self.assertEqual(sc.apply(D0+timedelta(hours=1))["terminal"],"MANAGED_APPLIED")
            sc.backup(D1-timedelta(hours=1))
            sc.nominate_round(D1,"I2-Managed",count=1)
            crashed=sc.tick(D1+timedelta(seconds=5),fault="AFTER_ONE_RDP_EVENT")
            self.assertNotEqual(crashed["_exit_code"],0)
            self.assertGreater(sc.unpublished(),0)
            stopped=sc.cmd(D1+timedelta(minutes=2),"collection-stop-intake","--expected-revision","1")
            self.assertEqual(stopped["terminal"],"MANAGED_INTAKE_STOPPED",stopped)
        ops_relative=sc.ops_path.relative_to(self.root).as_posix()
        paper_relative="local/factory_v1/paper_plane_state.sqlite"
        with closing(sqlite3.connect(self.root/paper_relative)) as conn:
            conn.execute("CREATE TABLE paper_positions(id TEXT PRIMARY KEY,state TEXT,source_activation TEXT)")
            conn.execute("INSERT INTO paper_positions VALUES('paper-27','OPEN',?)",(sc.activation_id,))
            conn.commit()
        self.config["backup"]["source_relative_paths"]=[ops_relative,paper_relative]
        self.config["backup"]["recursive_relative_paths"]=[f"{RDP}/datasets/publication_jobs"]
        tables=("managed_profiles","managed_control","managed_children","account_budget_scopes",
                "account_budget_policies","account_budget_members","accounting_counters","lifetime_counters",
                "authority_receipts","schedule_activations","episode_admissions","episode_outbox","due_observations")
        with closing(sqlite3.connect(sc.ops_path)) as conn:
            expected={table:list(conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid")) for table in tables}
            self.assertTrue(list(conn.execute("SELECT intake_revoked_at FROM managed_control"))[0][0])
            self.assertGreater(conn.execute("SELECT SUM(provider_calls) FROM accounting_counters").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM managed_children").fetchone()[0],1)
        packed=self.full()
        self.assertFalse(any(item["path"].endswith(".published") for item in packed["entries"]))
        sc.data_root.rename(sc.data_root.with_name("source-unavailable"))
        restored=Path(self.temp.name)/"managed-restored"
        result=remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"],deltas=[],
            dest_root=restored,expected_inventory_sha256=packed["inventory_sha256"])
        self.assertGreaterEqual(result["recovery_control"]["transitions"],1)
        with closing(sqlite3.connect(restored/ops_relative)) as conn:
            for table in tables:
                self.assertEqual(list(conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid")),expected[table],table)

        with closing(sqlite3.connect(restored/paper_relative)) as conn:
            self.assertEqual(conn.execute("SELECT * FROM paper_positions").fetchone(),("paper-27","OPEN",sc.activation_id))
        restored_store=ObservationScheduleStore(restored/ops_relative,readonly=True,immutable=False)
        try:
            self.assertTrue(restored_store.restore_marker_unresolved())
            # Named native identities come from the restored rows, never the producer filesystem.
            child_row=restored_store._conn.execute("SELECT schedule_sha256,activation_id FROM managed_children").fetchone()
            document=restored_store.get_registered_schedule(child_row[0])["document"]
            activation=restored_store.get_activation(child_row[0],child_row[1])
            self.assertTrue(activation_transition_research_event_proven(restored/RDP,activation,now=D1+timedelta(minutes=2)))
        finally:
            restored_store.close()
        jobs=list((restored/RDP/"datasets/publication_jobs/open").glob("*.json"))
        self.assertEqual(len(jobs),1)
        job=json.loads(jobs[0].read_text(encoding="utf-8"))
        research=ResearchStore(restored/RDP,create_if_missing=False)
        self.assertTrue(any(record.transaction_id==f"RESEARCH-TXN-OBS-{job['content_sha256'][:12].upper()}"
                            for record in research.iter_committed_records()))
        repaired=repair_open_publication_jobs(data_root=restored/RDP,root=ROOT,schedule=document,
            activation_id=child_row[1],now=D1+timedelta(minutes=3),producer_git_sha="d"*40)
        self.assertEqual(len(repaired),1)
        self.assertEqual(list((restored/RDP/"datasets/publication_jobs/open").glob("*.json")),[])
        self.assertEqual(len(list((restored/RDP/"datasets/publication_jobs/completed").glob("*.json"))),1)
        with closing(sqlite3.connect(restored/ops_relative)) as conn:
            for table in ("managed_profiles","managed_control","managed_children","accounting_counters","lifetime_counters"):
                self.assertEqual(list(conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid")),expected[table],table)

    def test_after_manifest_restore_repairs_and_rebuilds_native_panel_with_partition_manifests(self) -> None:
        self._publication_partition_recovery("AFTER_MANIFEST")

    def test_after_marker_restore_repairs_and_rebuilds_native_panel_with_partition_manifests(self) -> None:
        self._publication_partition_recovery("AFTER_MARKER")

    def test_native_after_manifest_between_membership_and_fence_preserves_exact_source(self) -> None:
        self._publication_arrives_before_fence("AFTER_MANIFEST")

    def test_native_after_marker_between_membership_and_fence_preserves_exact_source(self) -> None:
        self._publication_arrives_before_fence("AFTER_MARKER")

    def _publication_arrives_before_fence(self, fault: str) -> None:
        from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario,nominate,synth_mint,token_object
        from solana_alpha_lab.factory.observation_panel_publisher import (
            repair_open_publication_jobs,rebuild_observation_panel_from_rdp)
        import pyarrow.parquet as pq

        start=datetime(2026,10,5,tzinfo=UTC)
        sc=EpisodeScenario(self.root/RDP,start=start,stops=start+timedelta(hours=1))
        mint=synth_mint("I2-fence-race")
        row=token_object(mint,price=1,liquidity=10000,holders=60)
        nominate(sc.market,start,{"toporganicscore":[row],"toptraded":[],"toptrending":[]})
        sc.market.series[mint]=lambda _now:row
        jobs_root=sc.data_root/"datasets/publication_jobs"
        jobs_root.mkdir(parents=True,exist_ok=True)
        self.config["backup"]["source_relative_paths"]=[sc.ops_path.relative_to(self.root).as_posix()]
        self.config["backup"]["recursive_relative_paths"]=[f"{RDP}/datasets/publication_jobs"]
        original_fence=remote._capture_writer_fences
        observed={}
        @contextmanager
        def publish_before_fence(sources):
            self.assertEqual(list(jobs_root.rglob("*.json")),[])
            crashed=sc.tick(start+timedelta(seconds=5),fault=fault)
            self.assertNotEqual(crashed["_exit_code"],0)
            job_path=next((jobs_root/"open").glob("*.json"))
            job=json.loads(job_path.read_text(encoding="utf-8"))
            manifest=sc.data_root/"datasets/manifests"/(job["dataset_manifest_id"]+".json")
            observed.update(job=job,job_path=job_path.relative_to(self.root).as_posix(),
                job_bytes=job_path.read_bytes(),manifest_bytes=manifest.read_bytes(),
                observations=pq.read_table(sc.data_root/job["parquet_rel"]).to_pylist(),
                members=pq.read_table(sc.data_root/job["member_rel"]).to_pylist())
            with original_fence(sources):
                yield
        with patch.object(remote,"_capture_writer_fences",publish_before_fence):
            with patch.object(remote,"consistent_sqlite_backup",wraps=remote.consistent_sqlite_backup) as capture:
                packed=self.full()
                self.assertEqual(capture.call_count,1)
        self.assertIn(observed["job_path"],{item["path"] for item in packed["entries"]})
        with zipfile.ZipFile(self.sink/packed["bundle"]) as archive:
            self.assertEqual(archive.read(observed["job_path"]),observed["job_bytes"])
        sc.data_root.rename(sc.data_root.with_name("race-source-unavailable"))
        restored=Path(self.temp.name)/"race-restored"
        remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"],deltas=[],
            dest_root=restored,expected_inventory_sha256=packed["inventory_sha256"])
        repaired=repair_open_publication_jobs(data_root=restored/RDP,root=ROOT,schedule=sc.schedule,
            activation_id=sc.activation_id,now=start+timedelta(days=2),producer_git_sha="d"*40)
        self.assertEqual(len(repaired),1)
        job=observed["job"]
        self.assertEqual(repaired[0]["dataset_manifest_id"],job["dataset_manifest_id"])
        restored_manifest=restored/RDP/"datasets/manifests"/(job["dataset_manifest_id"]+".json")
        self.assertEqual(restored_manifest.read_bytes(),observed["manifest_bytes"])
        manifest=json.loads(restored_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["first_reliable_available_at"],json.loads(observed["manifest_bytes"])["first_reliable_available_at"])
        self.assertTrue(manifest["first_reliable_available_at"].startswith("2026-10-05"))
        panel=rebuild_observation_panel_from_rdp(data_root=restored/RDP,schedule_sha256=sc.schedule["schedule_sha256"])
        canonical=lambda rows:sorted(json.dumps(item,sort_keys=True,default=str) for item in rows)
        self.assertEqual(canonical(panel["observations"]),canonical(observed["observations"]))
        self.assertEqual(canonical(panel["members"]),canonical(observed["members"]))
        self.assertEqual(panel["dataset_manifest_ids"],[job["dataset_manifest_id"]])

    def test_new_sqlite_after_provisional_scan_is_not_captured_without_fence(self) -> None:
        original_fence=remote._capture_writer_fences
        @contextmanager
        def introduce_sqlite(sources):
            with closing(sqlite3.connect(self.root/RDP/"new-store.sqlite")) as conn:
                conn.execute("CREATE TABLE new_state(id INTEGER PRIMARY KEY)")
                conn.commit()
            with original_fence(sources):
                yield
        with patch.object(remote,"_capture_writer_fences",introduce_sqlite):
            with patch.object(remote,"consistent_sqlite_backup",wraps=remote.consistent_sqlite_backup) as capture:
                with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_UNFENCED_SQLITE_DISCOVERED"):
                    self.full()
                self.assertEqual(capture.call_count,0)

    def test_authoritative_membership_scan_uses_original_fence_deadline(self) -> None:
        original_scan=remote._backup_source_paths
        clock=[0.0]
        scans=[0]
        def slow_authoritative_scan(*args,**kwargs):
            scans[0]+=1
            if scans[0]==2:
                clock[0]=2.0
            return original_scan(*args,**kwargs)
        with patch.object(remote.time,"monotonic",side_effect=lambda:clock[0]):
            with patch.object(remote,"BACKUP_CAPTURE_FENCE_SECONDS",1.0):
                with patch.object(remote,"_backup_source_paths",slow_authoritative_scan):
                    with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED"):
                        self.full()
        self.assertEqual(scans[0],2)

    def _publication_partition_recovery(self, fault: str) -> None:
        from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario,nominate,synth_mint,token_object
        from solana_alpha_lab.factory.observation_panel_publisher import (
            repair_open_publication_jobs,rebuild_observation_panel_from_rdp)
        import pyarrow.parquet as pq

        start=datetime(2026,10,5,tzinfo=UTC)
        sc=EpisodeScenario(self.root/RDP,start=start,stops=start+timedelta(hours=1))
        mint=synth_mint("I2-after-manifest")
        market_row=token_object(mint,price=1,liquidity=10000,holders=60)
        nominate(sc.market,start,{"toporganicscore":[market_row],"toptraded":[],"toptrending":[]})
        sc.market.series[mint]=lambda _now:market_row
        crashed=sc.tick(start+timedelta(seconds=5),fault=fault)
        self.assertNotEqual(crashed["_exit_code"],0)
        jobs=list((sc.data_root/"datasets/publication_jobs/open").glob("*.json"))
        self.assertEqual(len(jobs),1)
        job=json.loads(jobs[0].read_text(encoding="utf-8"))
        self.assertEqual(job["stage"],"MANIFEST" if fault=="AFTER_MANIFEST" else "MARKER")
        expected_observations=pq.read_table(sc.data_root/job["parquet_rel"]).to_pylist()
        expected_members=pq.read_table(sc.data_root/job["member_rel"]).to_pylist()
        source_parts={path.relative_to(self.root).as_posix() for path in
            (sc.data_root/"datasets/manifests/partitions").glob("partition-*.json")
            if json.loads(path.read_text(encoding="utf-8"))["dataset_manifest_id"]==job["dataset_manifest_id"]}
        self.assertEqual(len(source_parts),2)
        self.config["backup"]["source_relative_paths"]=[sc.ops_path.relative_to(self.root).as_posix()]
        self.config["backup"]["recursive_relative_paths"]=[f"{RDP}/datasets/publication_jobs"]
        with patch.object(remote,"BACKUP_PARTITION_SCAN_MAX_FILES",0):
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED"):
                self.full()
        removed=self.root/sorted(source_parts)[0]
        exact_partition=removed.read_bytes()
        removed.unlink()
        try:
            with self.assertRaisesRegex(remote.RemoteOpsError,"BACKUP_PUBLICATION_PARTITION_INVALID"):
                self.full()
        finally:
            removed.write_bytes(exact_partition)
        packed=self.full()
        self.assertTrue(source_parts <= {item["path"] for item in packed["entries"]})
        sc.data_root.rename(sc.data_root.with_name("manifest-source-unavailable"))
        restored=Path(self.temp.name)/"after-manifest-restored"
        remote.restore_incremental_chain_isolated(full_bundle=self.sink/packed["bundle"],deltas=[],
            dest_root=restored,expected_inventory_sha256=packed["inventory_sha256"])
        repaired=repair_open_publication_jobs(data_root=restored/RDP,root=ROOT,schedule=sc.schedule,
            activation_id=sc.activation_id,now=start+timedelta(seconds=40),producer_git_sha="d"*40)
        self.assertEqual(len(repaired),1)
        panel=rebuild_observation_panel_from_rdp(data_root=restored/RDP,schedule_sha256=sc.schedule["schedule_sha256"])
        canonical=lambda rows:sorted(json.dumps(row,sort_keys=True,default=str) for row in rows)
        self.assertEqual(canonical(panel["observations"]),canonical(expected_observations))
        self.assertEqual(canonical(panel["members"]),canonical(expected_members))
        self.assertEqual(panel["dataset_manifest_ids"],[job["dataset_manifest_id"]])
        self.assertGreater(len(panel["observations"]),0)
        self.assertGreater(len(panel["members"]),0)
    def test_whole_same_snapshot_deflate_reduction(self) -> None:
        with closing(sqlite3.connect(self.root/OPS)) as conn:
            payload=json.dumps({"decoded_response":{"items":[{"entity":"fixture","price":17}]*5000}},sort_keys=True)
            conn.executemany("INSERT INTO semantic_state(profile_revision,provider_calls,credits,desired_state,payload) VALUES(1,0,0,'PAUSED',?)",[(payload,)]*12)
            conn.commit()
        start_cpu,start_wall=time.process_time(),time.monotonic()
        with remote.backup_payload_snapshot(self.root,self.config) as snapshot:
            stage=snapshot.staged_path(OPS)
            for _part in Path(OPS).parts:
                stage=stage.parent
            stage_files=[path for path in stage.rglob("*") if path.is_file()]
            captured_stage_bytes=sum(path.stat().st_size for path in stage_files)
            captured_file_count=len(stage_files)
            packed=remote.package_backup(self.root,config=self.config,snapshot=snapshot,
                sink_override=self.sink,prune_superseded=False)
            simultaneous_transient_bytes=captured_stage_bytes+packed["bytes"]
        self.assertFalse(stage.exists())
        elapsed_cpu,elapsed_wall=time.process_time()-start_cpu,time.monotonic()-start_wall
        stored=self.rewrite(self.sink/packed["bundle"],stored=True)
        self.assertLess(packed["bytes"], stored.stat().st_size//4)
        with zipfile.ZipFile(self.sink/packed["bundle"]) as archive:
            sql=archive.getinfo(OPS)
            self.assertEqual(sql.compress_type,zipfile.ZIP_DEFLATED)
            self.assertLess(sql.compress_size,sql.file_size//4)
        for index,bundle in enumerate((stored,self.sink/packed["bundle"])):
            result=remote.restore_incremental_chain_isolated(full_bundle=bundle,deltas=[],
                dest_root=Path(self.temp.name)/f"compression-{index}",expected_inventory_sha256=packed["inventory_sha256"])
            self.assertEqual(result["raw_inventory_sha256"],packed["inventory_sha256"])
        if os.environ.get("I2_PRINT_BENCHMARK")=="1":
            print(json.dumps({"scope":"ISOLATED_WHOLE_SYNTHETIC_CHECKPOINT_SAME_CAPTURE",
                "stored_bytes":stored.stat().st_size,"deflated_bytes":packed["bytes"],
                "uncompressed_logical_bytes":sum(item["bytes"] for item in packed["entries"]),
                "ratio":stored.stat().st_size/packed["bytes"],"capture_pack_verify_cpu_seconds":elapsed_cpu,
                "capture_pack_verify_wall_seconds":elapsed_wall,"compression_method":8,"compression_level":1,
                "phase_capture_staging_bytes":captured_stage_bytes,"phase_capture_staging_file_count":captured_file_count,
                "phase_local_verified_transient_bytes":simultaneous_transient_bytes,
                "phase_upload_ready_transient_bytes":packed["bytes"],"phase_upload_ready_capture_bytes":0,
                "production_claim":False},sort_keys=True))


if __name__ == "__main__":
    unittest.main()
