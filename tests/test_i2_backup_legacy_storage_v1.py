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
import unittest
import zipfile
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import remote_ops as remote  # noqa: E402

OPS = "local/factory_v1/observation_schedule_state.sqlite"
RDP = "local/factory_v1/observation_rdp"


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

    def test_real_control_event_closure_survives_mutable_only_restore(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            activate_schedule, authorize_schedule, prepare_schedule_authority)
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from solana_alpha_lab.factory.research_store import ResearchStore

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
