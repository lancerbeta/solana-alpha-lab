"""Native lock/restore proofs, with synthetic source bytes and lowest HTTP seam."""
from __future__ import annotations

from contextlib import closing, redirect_stdout
from datetime import UTC, datetime, timedelta
import copy
import hashlib
import io
from decimal import Decimal
import json
import os
import shutil
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from scripts.prove_trading_core_operational_closure import RecordingQuoteAdapter
from tests import test_trading_core_operational_closure_v1 as closure_fixture
from solana_alpha_lab.factory.hfic_research_scope import sha256_of
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, PaperPlaneStore
from solana_alpha_lab.factory.trading_adapters import (
    ENDPOINT, REGISTRY_PATH, ROUTE_ID, JupiterQuoteAdapter,
    verified_quote_grant,
)
from solana_alpha_lab.factory.trading_coordinator import TradingCoordinator, restore_native_backup
from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner


class _GrantedRecordingAdapter(JupiterQuoteAdapter):
    """Retain original effects independently while keeping production quota checks."""
    def __init__(self, ledger, grant):
        self.ledger = ledger
        super().__init__(timeout_seconds=1, max_response_bytes=8192, grant=grant,
            credential_supplier=lambda: None)

    def dispatch(self, attempt, request, *, as_of):
        result, proof = super().dispatch(attempt, request, as_of=as_of)
        receipt = {"attempt": attempt, "request": request, "result": result}
        receipt["receipt_sha256"] = sha256_of(receipt)
        with closing(sqlite3.connect(self.ledger)) as connection:
            connection.execute("INSERT INTO calls(attempt_id,receipt_json) VALUES (?,?)",
                (attempt["attempt_id"], json.dumps(receipt, sort_keys=True)))
            connection.commit()
        return result, proof


class OperationalRecoveryTests(unittest.TestCase):
    # Compose only fixture helpers; inherited driver tests would duplicate the suite.
    setUp = closure_fixture.OperatingDriverTests.setUp
    tearDown = closure_fixture.OperatingDriverTests.tearDown
    prepare = closure_fixture.OperatingDriverTests.prepare
    start_operating = closure_fixture.OperatingDriverTests.start_operating
    quote_inputs = closure_fixture.OperatingDriverTests.quote_inputs
    wire_files = closure_fixture.OperatingDriverTests.wire_files
    ledger_receipts = closure_fixture.OperatingDriverTests.ledger_receipts
    recovery_cut = closure_fixture.OperatingDriverTests.recovery_cut

    def fresh_restore_runner(self, suffix):
        destination=self.root/"local"/suffix
        destination.mkdir()
        shutil.copyfile(self.data/"offline_runtime.json",destination/"offline_runtime.json")
        return TradingContinuityRunner(self.root,data_root=destination)

    def test_restore_all_destination_artifact_collisions_preserve_regular_and_hardlink_bytes(self):
        self.start_operating()
        self.coordinator.backup(destination_relative="backups/restore-collisions.sqlite")
        backup=self.data/"backups/restore-collisions.sqlite"
        cases=[]
        for index,suffix in enumerate(("","-journal","-wal","-shm")):
            for kind in ("regular","hardlink"):
                with self.subTest(suffix=suffix,kind=kind):
                    runner=self.fresh_restore_runner("restore-"+str(index)+"-"+kind)
                    artifact=type(backup)(str(runner.store_path)+suffix)
                    victim=self.root/("restore-victim-"+str(index)+"-"+kind+".txt")
                    victim.write_bytes(b"SYNTHETIC_RESTORE_NON_TARGET")
                    if kind=="hardlink":
                        os.link(victim,artifact)
                    else:
                        artifact.write_bytes(victim.read_bytes())
                    before={p.name:p.read_bytes() for p in runner.data_root.iterdir() if p.is_file()}
                    with self.assertRaisesRegex(PaperPlaneError,"RESTORE_REQUIRES_FRESH_ROOT|OFFLINE_STORE_ALIAS_FORBIDDEN|OPERATING_CHILD_ALIAS_FORBIDDEN"):
                        restore_native_backup(backup_path=backup,destination_runner=runner)
                    self.assertEqual({p.name:p.read_bytes() for p in runner.data_root.iterdir() if p.is_file()},before)
                    self.assertEqual(victim.read_bytes(),b"SYNTHETIC_RESTORE_NON_TARGET")
                    self.assertEqual(list(runner.data_root.glob(".native-restore-*")),[])
                    cases.append({"suffix":suffix,"kind":kind,"nontarget_unchanged":True,"native_final_write":False})
        self.metrics={"destination_collisions":cases,"artifact_cases":8}

    def test_two_ordinary_restore_cycles_preserve_original_history_and_each_new_snapshot_fence(self):
        self.start_operating()
        self.coordinator.tick()
        original=self.runner.readback()
        self.coordinator.backup(destination_relative="backups/cycle-one.sqlite")
        first_backup=self.data/"backups/cycle-one.sqlite"
        first_cut=self.production_cut(first_backup)
        first_runner,first=self.restored(first_backup,suffix="restore-cycle-one",mode="PAPER")
        first.reconcile_cut(first_cut)
        self.acknowledge(first,first_cut)
        with closing(PaperPlaneStore(first_runner.store_path,readonly=True)) as store:
            original_events=store.execution_events()
        first.backup(destination_relative="backups/cycle-two.sqlite")
        second_backup=first_runner.data_root/"backups/cycle-two.sqlite"
        second_cut=first.export_recovery_cut(backup_path=second_backup,effects=[],
            external_cut_id="SYNTHETIC_SECOND_COMPLETE_CUT",as_of=first_cut["as_of"])
        second_cut={**second_cut,"cut_sha256":sha256_of(second_cut)}
        second_runner,second=self.restored(second_backup,suffix="restore-cycle-two",mode="PAPER")
        self.assertTrue(second.status()["restore_guard"])
        self.assertEqual(second_runner.readback()["positions"],original["positions"])
        self.assertEqual(second_runner.readback()["modeled_attempts"],original["modeled_attempts"])
        self.assertEqual(second_runner.readback()["modeled_results"],original["modeled_results"])
        self.assertEqual(second.status()["inventory"],first.status()["inventory"])
        with self.assertRaisesRegex(PaperPlaneError,"RESTORE_EXTERNAL_CUT_BACKUP_CONFLICT"):
            second.reconcile_cut(first_cut)
        self.assertTrue(second.status()["restore_guard"])
        with closing(PaperPlaneStore(first_runner.store_path,readonly=True)) as store:
            first_events=store.filtered_execution_events(event_type="RESTORE_SNAPSHOT_BOUND")
        with closing(PaperPlaneStore(second_runner.store_path,readonly=True)) as store:
            second_events=store.filtered_execution_events(event_type="RESTORE_SNAPSHOT_BOUND")
            self.assertEqual(store.execution_events()[:-1],original_events)
            self.assertTrue(all(bot["entries_paused"] for bot in store.bots()))
        self.assertEqual(len(first_events),1)
        self.assertEqual(len(second_events),2)
        self.assertEqual(second_events[0],first_events[0])
        self.assertEqual(second_events[1]["payload"],{"database_sha256":hashlib.sha256(second_backup.read_bytes()).hexdigest()})
        second.reconcile_cut(second_cut)
        self.acknowledge(second,second_cut)
        self.acknowledge(second,second_cut)
        with closing(PaperPlaneStore(second_runner.store_path,readonly=True)) as store:
            acks=store.filtered_execution_events(event_type="RESTORE_RECONCILIATION_ACKNOWLEDGED")
            self.assertEqual(len(acks),2)
            self.assertNotEqual(acks[0]["event_id"],acks[1]["event_id"])
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now=datetime(2026,10,5,13,10,tzinfo=UTC)
        second.tick()
        self.assertEqual(second_runner.readback()["positions"][0]["state"],"RECONCILED")
        self.assertEqual(len(second_runner.readback()["modeled_attempts"]),2)
        self.metrics={"ordinary_restore_cycles":2,"original_history_retained":True,"snapshot_events":2,
            "each_new_fence":True,"prior_cut_denied":True,"same_inventory_and_ack_clock":True,
            "distinct_restore_acks":2,"second_ack_repeat":"IDEMPOTENT",
            "original_exit_after_second_ack":"RECONCILED"}

    def test_restore_exclusive_reservation_late_auxiliary_and_native_failure_preserve_non_targets(self):
        self.start_operating()
        self.coordinator.backup(destination_relative="backups/restore-races.sqlite")
        backup=self.data/"backups/restore-races.sqlite"
        for seam in ("RESERVATION","LATE_AUXILIARY","NATIVE_FAILURE"):
            with self.subTest(seam=seam):
                runner=self.fresh_restore_runner("restore-"+seam.lower())
                artifact=runner.store_path if seam=="RESERVATION" else type(backup)(str(runner.store_path)+"-shm")
                victim=self.root/("restore-race-victim-"+seam+".txt")
                victim.write_bytes(b"SYNTHETIC_RESTORE_RACE_NON_TARGET")
                if seam=="RESERVATION":
                    native_open=os.open
                    def reserve(path,flags,*args,**kwargs):
                        if str(path)==str(runner.store_path):
                            os.link(victim,path)
                        return native_open(path,flags,*args,**kwargs)
                    context=patch("solana_alpha_lab.factory.trading_coordinator.os.open",side_effect=reserve)
                    expected=PaperPlaneError
                    reason="RESTORE_REQUIRES_FRESH_ROOT"
                else:
                    native_connect=sqlite3.connect
                    def connect(database,*args,**kwargs):
                        if str(database).endswith("restored.sqlite"):
                            if seam=="NATIVE_FAILURE":
                                raise RuntimeError("SYNTHETIC_NATIVE_RESTORE_FAILURE")
                            artifact.write_bytes(victim.read_bytes())
                        return native_connect(database,*args,**kwargs)
                    context=patch("solana_alpha_lab.factory.trading_coordinator.sqlite3.connect",side_effect=connect)
                    expected=RuntimeError if seam=="NATIVE_FAILURE" else PaperPlaneError
                    reason="SYNTHETIC_NATIVE_RESTORE_FAILURE" if seam=="NATIVE_FAILURE" else "RESTORE_REQUIRES_FRESH_ROOT"
                with context,self.assertRaisesRegex(expected,reason):
                    restore_native_backup(backup_path=backup,destination_runner=runner)
                self.assertEqual(victim.read_bytes(),b"SYNTHETIC_RESTORE_RACE_NON_TARGET")
                if seam!="NATIVE_FAILURE":
                    self.assertEqual(artifact.read_bytes(),victim.read_bytes())
                if seam!="RESERVATION":
                    self.assertFalse(runner.store_path.exists())
                self.assertEqual(list(runner.data_root.glob(".native-restore-*")),[])
        self.metrics={"reservation_race":"DENY_NON_TARGET_UNCHANGED","late_auxiliary":"DENY_NON_TARGET_UNCHANGED",
            "native_failure":"ONLY_OWNED_MAIN_REMOVED","native_staging_roots_absent":True}

    def test_restore_sealed_source_rejects_unsigned_wal_and_preserves_standalone_legacy_lineage(self):
        from solana_alpha_lab.factory.trading_runtime_policy import configure_operating_envelope,read_operating_envelope
        self.start_operating()
        self.coordinator.tick()
        original=self.runner.readback()
        self.coordinator.backup(destination_relative="backups/source-seal.sqlite")
        base=self.data/"backups/source-seal.sqlite"
        manifest=json.loads(type(base)(str(base)+".json").read_text())
        legacy=base.parent/"legacy-format.sqlite"
        shutil.copyfile(base,legacy)
        with closing(PaperPlaneStore(legacy)):
            pass
        sealed_hash=hashlib.sha256(legacy.read_bytes()).hexdigest()
        type(base)(str(legacy)+".json").write_text(json.dumps({**manifest,"database_sha256":sealed_hash}),encoding="utf-8")
        # A complete standalone WAL-header carrier remains compatible. Only
        # native source format is old; no historical whole binary is claimed.
        runner=self.fresh_restore_runner("restore-legacy-standalone")
        restored=restore_native_backup(backup_path=legacy,destination_runner=runner)
        self.assertEqual(restored["status"],"RESTORED_RECONCILIATION_REQUIRED")
        with closing(PaperPlaneStore(runner.store_path,readonly=True)) as store:
            self.assertEqual(store.positions(),original["positions"])
            self.assertEqual(store.get_execution_event("RESTORE-SNAPSHOT")["payload"],{"database_sha256":sealed_hash})
            self.assertTrue(all(b["entries_paused"] for b in store.bots()))
            self.assertEqual(read_operating_envelope(store,"PAPER")["revision"],1)
            self.assertTrue(store._conn.execute("SELECT restore_guard FROM ordinary_state").fetchone()[0])
        self.assertEqual(list(legacy.parent.glob(legacy.name+"-"+"*")),[])
        with closing(PaperPlaneStore(legacy)) as writer:
            current=read_operating_envelope(writer,"PAPER")
            configure_operating_envelope(writer,mode="PAPER",candidate_raw={**current["envelope"],
                "max_outstanding_positions":3,"max_outstanding_cost_basis_usd":"90"},
                expected_current_sha256=current["envelope_sha256"],idempotency_key="UNSIGNED_SOURCE_WAL",
                as_of="2026-10-05T12:41:00Z")
            self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(),sealed_hash)
            shutil.copyfile(type(base)(str(legacy)+"-wal"),type(base)(str(base)+"-wal"))
            shutil.copyfile(type(base)(str(legacy)+"-shm"),type(base)(str(base)+"-shm"))
            for index,source in enumerate((legacy,base)):
                source_family={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.glob(source.name+"*")}
                destination=self.fresh_restore_runner("restore-source-wal-"+str(index))
                with self.assertRaisesRegex(PaperPlaneError,"BACKUP_CONTENT_CONFLICT"):
                    restore_native_backup(backup_path=source,destination_runner=destination)
                self.assertFalse(destination.store_path.exists())
                self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.glob(source.name+"*")},source_family)
        for index,bad in enumerate((None,[],7)):
            malformed=base.parent/("malformed-"+str(index)+".sqlite")
            shutil.copyfile(base,malformed)
            type(base)(str(malformed)+".json").write_text(json.dumps(bad),encoding="utf-8")
            destination=self.fresh_restore_runner("restore-manifest-"+str(index))
            with self.assertRaisesRegex(PaperPlaneError,"BACKUP_CONTENT_CONFLICT"):
                restore_native_backup(backup_path=malformed,destination_runner=destination)
            self.assertFalse(destination.store_path.exists())
        self.metrics={"unsigned_wal_sources_denied":2,"original_sealed_limit":"30","unsigned_limit_not_imported":"90",
            "source_artifacts_unchanged":True,"standalone_legacy_format":"ORIGINAL_IDENTITIES_FENCE_PAUSE_PRESERVED",
            "malformed_manifest_shapes":3}

    def two_native_open_positions(self, *, mode="PAPER"):
        activate=TradingCoordinator.activate
        def expand(coordinator,**kwargs):
            kwargs["profile"]["envelope"].update(max_outstanding_positions=2,max_outstanding_cost_basis_usd="60")
            return activate(coordinator,**kwargs)
        with patch.object(TradingCoordinator,"activate",new=expand):
            self.start_operating(mode=mode)
        ledger=None
        if mode=="SHADOW":
            ledger,plan=self.wire_files([{"outAmount":"10000000000000"},{"outAmount":"10000000000000"},
                {"outAmount":"330000000"},{"outAmount":"330000000"}])
            self.coordinator.quote_adapter=RecordingQuoteAdapter(ledger,json.loads(plan.read_text()))
        first=self.epoch
        self.coordinator.tick()
        self.coordinator.activate(epoch_id=first+"-OTHER",at="2026-10-05T12:40:00Z",profile=self.profile,
            switch_key="BACKUP-ORIGIN-HEALTHY-NEIGHBOR",expected_current_epoch=first)
        self.coordinator.tick()
        self.assertEqual([p["state"] for p in self.runner.readback()["positions"]],["OPEN","OPEN"])
        self.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        self.now=datetime(2026,10,5,13,10,tzinfo=UTC)
        if mode=="SHADOW":
            self.quote_inputs(at="2026-10-05T13:10:00Z")
        return first,ledger

    def test_backup_all_final_artifact_collisions_preserve_owned_non_targets_before_write(self):
        self.start_operating()
        results=[]
        for index,suffix in enumerate(("",".json","-journal","-wal","-shm")):
            for kind in ("regular","hardlink"):
                with self.subTest(suffix=suffix,kind=kind):
                    target=self.data/"backups"/(str(index)+"-"+kind+".sqlite")
                    target.parent.mkdir(exist_ok=True)
                    artifact=target if not suffix else type(target)(str(target)+suffix)
                    victim=self.root/("synthetic-victim-"+str(index)+"-"+kind+".txt")
                    victim.write_bytes(b"SYNTHETIC_NON_TARGET_MUST_REMAIN_UNCHANGED")
                    if kind=="hardlink":
                        os.link(victim,artifact)
                    else:
                        artifact.write_bytes(victim.read_bytes())
                    before=artifact.read_bytes()
                    with self.assertRaisesRegex(PaperPlaneError,"BACKUP_DESTINATION_MUST_BE_NEW|OPERATING_CHILD_ALIAS_FORBIDDEN"):
                        self.coordinator.backup(destination_relative=target.relative_to(self.data).as_posix())
                    self.assertEqual(victim.read_bytes(),b"SYNTHETIC_NON_TARGET_MUST_REMAIN_UNCHANGED")
                    self.assertEqual(artifact.read_bytes(),before)
                    if suffix:
                        self.assertFalse(target.exists())
                    self.assertEqual(list(target.parent.glob(".native-backup-*")),[])
                    results.append({"suffix":suffix,"kind":kind,"denied":True,"nontarget_unchanged":True})
        self.metrics={"artifact_collisions":results,"native_destination_writes":0}

    def test_backup_exclusive_sidecar_race_and_native_failure_remove_only_reserved_outputs(self):
        self.start_operating()
        target=self.data/"backups/race.sqlite"
        victim=self.root/"synthetic-race-victim.txt"
        victim.write_bytes(b"SYNTHETIC_NON_TARGET")
        native_open=os.open
        def race(path,flags,*args,**kwargs):
            if str(path)==str(target)+".json":
                os.link(victim,path)
            return native_open(path,flags,*args,**kwargs)
        with patch("solana_alpha_lab.factory.trading_coordinator.os.open",side_effect=race):
            with self.assertRaisesRegex(PaperPlaneError,"BACKUP_DESTINATION_MUST_BE_NEW"):
                self.coordinator.backup(destination_relative="backups/race.sqlite")
        self.assertFalse(target.exists())
        self.assertEqual(victim.read_bytes(),b"SYNTHETIC_NON_TARGET")
        self.assertEqual(type(target)(str(target)+".json").read_bytes(),b"SYNTHETIC_NON_TARGET")
        native_connect=sqlite3.connect
        def fail_staging(database,*args,**kwargs):
            if str(database).endswith("snapshot.sqlite"):
                raise RuntimeError("SYNTHETIC_NATIVE_BACKUP_FAILURE")
            return native_connect(database,*args,**kwargs)
        with patch("solana_alpha_lab.factory.trading_coordinator.sqlite3.connect",side_effect=fail_staging):
            with self.assertRaisesRegex(RuntimeError,"SYNTHETIC_NATIVE_BACKUP_FAILURE"):
                self.coordinator.backup(destination_relative="backups/native-failure.sqlite")
        self.assertEqual(list(target.parent.glob("native-failure.sqlite*")),[])
        self.assertEqual(list(target.parent.glob(".native-backup-*")),[])
        manifest=self.coordinator.backup(destination_relative="backups/standalone.sqlite")
        standalone=target.parent/"standalone.sqlite"
        self.assertEqual(hashlib.sha256(standalone.read_bytes()).hexdigest(),manifest["database_sha256"])
        self.assertEqual({p.name for p in target.parent.glob("standalone.sqlite*")},{"standalone.sqlite","standalone.sqlite.json"})
        runner,coordinator=self.restored(standalone,mode="PAPER")
        self.assertTrue(coordinator.status()["restore_guard"])
        with closing(sqlite3.connect(standalone.as_uri()+"?mode=ro",uri=True)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0],"delete")
        self.metrics={"sidecar_race":"DENY_NON_TARGET_UNCHANGED","native_failure":"OWNED_OUTPUTS_REMOVED",
            "standalone_backup_restore":"PASS","final_auxiliary_files":0}

    def test_malformed_origin_shapes_are_typed_readonly_and_do_not_starve_healthy_due_exit(self):
        first,_=self.two_native_open_positions()
        with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
            original_position=next(p for p in store.positions() if p["activation_epoch_id"]==first)
            original=store.get_execution_event("SRC-"+original_position["signal_decision_id"])
        variants=[("packet",value) for value in (None,7,[],False)]
        for field in ("decision","provenance"):
            for value in (None,7,[],False,0,{}):
                body=copy.deepcopy(original["payload"])
                body[field]=value
                variants.append((field,body))
        for field,bad in variants:
            with self.subTest(field=field,shape=type(bad).__name__):
                with closing(PaperPlaneStore(self.runner.store_path)) as store:
                    store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",(json.dumps(bad),original["event_id"]))
                    with self.assertRaisesRegex(PaperPlaneError,"SOURCE_DECISION_PROVENANCE_CONFLICT"):
                        self.runner.for_epoch(first)._origin(store,original_position)
                self.coordinator.tick()
                def database_bytes():
                    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        (self.runner.store_path,type(self.runner.store_path)(str(self.runner.store_path)+"-wal")) if p.is_file()}
                # Keep the native WAL lifecycle pinned while measuring the
                # read-only consumer; SHM reader locks are not DB/WAL content.
                with closing(PaperPlaneStore(self.runner.store_path)):
                    before=database_bytes()
                    view=self.coordinator.status()
                    self.assertEqual(database_bytes(),before)
                self.assertEqual(view["status"],"ACTION_REQUIRED")
                self.assertEqual(view["inventory"]["inventory_status"],"UNKNOWN")
                self.assertIn("SOURCE_DECISION_PROVENANCE_CONFLICT",{x["reason"] for x in view["incidents"] if x["active"]})
                positions={p["activation_epoch_id"]:p for p in self.runner.readback()["positions"]}
                self.assertEqual(positions[first]["state"],"OPEN")
                self.assertEqual(positions[first+"-OTHER"]["state"],"RECONCILED")
                with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
                    self.assertEqual(store.get_execution_event(original["event_id"])["payload"],bad)
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",(json.dumps(original["payload"]),original["event_id"]))
        self.coordinator.tick()
        self.assertEqual([p["state"] for p in self.runner.readback()["positions"]],["RECONCILED","RECONCILED"])
        self.assertEqual(self.coordinator.status()["status"],"READY")
        self.metrics={"shape_variants":len(variants),"healthy_neighbor":"RECONCILED","status_db_wal_readonly":True,
            "exact_original_restore":"READY"}

    def test_malformed_original_capture_and_callback_quarantine_without_resend_or_neighbor_starvation(self):
        first,ledger=self.two_native_open_positions(mode="SHADOW")
        def stop(point):
            if point=="AFTER_RESULT_CAPTURE":
                raise RuntimeError("SYNTHETIC_STOP_AFTER_ORIGINAL_CAPTURE")
        self.coordinator.fault=stop
        with self.assertRaisesRegex(RuntimeError,"SYNTHETIC_STOP_AFTER_ORIGINAL_CAPTURE"):
            self.coordinator.tick()
        self.coordinator.fault=lambda point:None
        with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
            capture=store.filtered_execution_events(event_type="ADAPTER_RESULT_CAPTURED")[-1]
            attempt=store.get_execution_event(capture["event_id"].removeprefix("CAPTURE-"))
        bodies=[None,7,[],False]
        for field in ("result","provenance"):
            body=copy.deepcopy(capture["payload"])
            body[field]=[]
            body["capture_sha256"]=sha256_of({k:v for k,v in body.items() if k!="capture_sha256"})
            bodies.append(body)
        for bad in bodies:
            with self.subTest(capture_shape=type(bad).__name__):
                with closing(PaperPlaneStore(self.runner.store_path)) as store:
                    store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",(json.dumps(bad),capture["event_id"]))
                self.coordinator.tick()
                view=self.coordinator.status()
                self.assertEqual(view["status"],"ACTION_REQUIRED")
                self.assertEqual(view["pending_attempts"],1)
                self.assertEqual(view["inventory"]["inventory_status"],"UNKNOWN")
                self.assertIn("ADAPTER_CAPTURE_INTEGRITY_CONFLICT",{x["reason"] for x in view["incidents"] if x["active"]})
                self.assertEqual(len(self.ledger_receipts(ledger)),4)
                with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
                    self.assertEqual(store.get_execution_event(capture["event_id"])["payload"],bad)
                rows={p["activation_epoch_id"]:p for p in self.runner.readback()["positions"]}
                self.assertEqual(rows[first]["state"],"EXITING")
                self.assertEqual(rows[first+"-OTHER"]["state"],"RECONCILED")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",(json.dumps(capture["payload"]),capture["event_id"]))
            store._conn.execute("UPDATE execution_events SET payload_json='null' WHERE event_id=?",(attempt["event_id"],))
        self.coordinator.tick()
        self.assertIn("RECOVERY_ATTEMPT_CONTENT_CONFLICT",{x["reason"] for x in self.coordinator.status()["incidents"] if x["active"]})
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",(json.dumps(attempt["payload"]),attempt["event_id"]))
        inbox=self.data/"result-inbox"
        inbox.mkdir(exist_ok=True)
        callback=inbox/(attempt["event_id"]+".json")
        for bad in (None,7,[],{"attempt_id":attempt["event_id"],"result_id":"SYNTHETIC","outcome":[],"observed_at":"2026-10-05T13:10:00Z"}):
            callback.write_text(json.dumps(bad),encoding="utf-8")
            self.coordinator.tick()
            self.assertEqual(self.coordinator.status()["pending_attempts"],1)
            self.assertEqual(len(self.ledger_receipts(ledger)),4)
        callback.unlink()
        self.coordinator.tick()
        self.assertEqual([p["state"] for p in self.runner.readback()["positions"]],["RECONCILED","RECONCILED"])
        self.assertEqual(self.coordinator.status()["status"],"READY")
        self.assertEqual(len(self.ledger_receipts(ledger)),4)
        self.metrics={"capture_variants":len(bodies),"callback_variants":4,"malformed_attempt":"TYPED_QUARANTINE",
            "fake_quote_effects":4,"repeated_http_calls":0,"healthy_neighbor":"RECONCILED","original_capture_restore":"READY"}

    def source_corruption_over_future_exit(self, damage):
        """Ordinary CLI, native owners; only the synthetic clock/sleep advances."""
        from scripts import trading_continuity as cli
        import signal
        self.start_operating()
        self.coordinator.tick()
        original = self.runner.readback()
        original_position = original["positions"][0]
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        source_path = self.source.data_root / "observation_schedule_state.sqlite"
        with closing(sqlite3.connect(source_path)) as source:
            source.row_factory = sqlite3.Row
            raw = dict(source.execute("SELECT * FROM episode_admissions LIMIT 1").fetchone())
            raw["episode_id"] += "-MALFORMED"
            record = json.loads(raw["record_json"])
            record["episode_id"] = raw["episode_id"]
            if damage == "json":
                raw["record_json"] = "{"
            else:
                if damage == "array":
                    record = []
                elif damage == "nested":
                    record["t0"] = []
                elif damage == "identity":
                    record["episode_id"] += "-CONFLICT"
                raw["record_json"] = json.dumps(record, sort_keys=True)
                raw["content_sha256"] = sha256_of(record)
                if damage == "hash":
                    raw["content_sha256"] = "0" * 64
            source.execute("INSERT INTO episode_admissions (" + ",".join(raw) + ") VALUES (" +
                ",".join("?" for _ in raw) + ")", list(raw.values()))
            source.commit()
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            cursor = store._conn.execute("SELECT discovery_rowid,rescan_rowid FROM ordinary_state WHERE mode='PAPER'").fetchone()
            original_events = store.execution_events()
        clock = self.data / "source-isolation-clock.json"
        clock.write_text(json.dumps({"as_of": "2026-10-05T12:41:00Z"}), encoding="utf-8")
        sleeps = []
        def advance(delay):
            sleeps.append(delay)
            clock.write_text(json.dumps({"as_of": "2026-10-05T13:10:00Z"}), encoding="utf-8")
        handlers = {name: signal.getsignal(getattr(signal, name)) for name in ("SIGINT", "SIGTERM", "SIGBREAK")
            if hasattr(signal, name)}
        output = io.StringIO()
        try:
            with patch("solana_alpha_lab.factory.trading_coordinator.time.sleep", side_effect=advance), redirect_stdout(output):
                code = cli.main(["run", "--repository-root", str(self.root), "--data-root", str(self.data),
                    "--mode", "PAPER", "--ticks", "3", "--clock-file", clock.name])
        finally:
            for name, handler in handlers.items():
                signal.signal(getattr(signal, name), handler)
        self.metrics = {"damage": damage, "cli_exit_code": code, "cli_response": json.loads(output.getvalue()),
            "positions": [{"position_id": row["position_id"], "state": row["state"]} for row in self.runner.readback()["positions"]],
            "attempt_count": len(self.runner.readback()["modeled_attempts"]), "clock_advances": len(sleeps)}
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(json.loads(output.getvalue()), {"status": "GRACEFUL_SHUTDOWN", "ticks": 3, "activation_created": False})
        self.assertEqual(len(sleeps), 2)
        after = self.runner.readback()
        self.assertEqual(after["positions"][0]["position_id"], original_position["position_id"])
        self.assertEqual(after["positions"][0]["state"], "RECONCILED")
        self.assertEqual(len(after["modeled_attempts"]), 2)
        self.assertEqual(after["modeled_attempts"][0], original["modeled_attempts"][0])
        self.assertEqual(after["modeled_results"][0], original["modeled_results"][0])
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        view = self.coordinator.status()
        self.assertEqual(view["status"], "ACTION_REQUIRED")
        source_incident = next(row for row in view["incidents"] if row["incident_key"] == "SOURCE-PAPER")
        self.assertTrue(source_incident["active"])
        self.assertIn(source_incident["reason"], {"EPISODE_ADMISSION_INVALID", "EPISODE_ADMISSION_HASH_CONFLICT",
            "EPISODE_ADMISSION_IDENTITY_CONFLICT"})
        self.assertEqual(view["input_reason"], source_incident["reason"])
        self.assertFalse(view["input_fresh"])
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            self.assertEqual(tuple(store._conn.execute("SELECT discovery_rowid,rescan_rowid FROM ordinary_state WHERE mode='PAPER'").fetchone()), tuple(cursor))
            current = {event["event_id"]: event for event in store.execution_events()}
            self.assertTrue(all(current[event["event_id"]] == event for event in original_events))
            self.assertIsNone(store._conn.execute("SELECT 1 FROM ordinary_work WHERE episode_id=?", (raw["episode_id"],)).fetchone())
        with closing(sqlite3.connect(source_path)) as source:
            source.row_factory = sqlite3.Row
            self.assertEqual(dict(source.execute("SELECT * FROM episode_admissions WHERE episode_id=?", (raw["episode_id"],)).fetchone()), raw)
            source.execute("DELETE FROM episode_admissions WHERE episode_id=?", (raw["episode_id"],))
            source.commit()
        self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 2)
        return {"damage": damage, "cli_ticks": 3, "clock_crossed_due_time": True, "original_position": "RECONCILED",
            "source_reason": source_incident["reason"], "cursor_unchanged": True, "source_bytes_preserved": True,
            "attempts": 2, "exact_source_repair": "READY"}

    def test_malformed_new_source_json_does_not_stop_ordinary_cli_before_future_old_exit(self):
        self.metrics = self.source_corruption_over_future_exit("json")

    def test_source_shape_hash_and_identity_conflicts_isolate_page_and_keep_old_exit_service(self):
        metrics = []
        for damage in ("array", "nested", "identity", "hash"):
            with self.subTest(damage=damage):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    metrics.append(case.source_corruption_over_future_exit(damage))
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def retained_request_corruption_with_healthy_exit(self, damage):
        first, ledger = self.two_native_open_positions(mode="SHADOW")
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            position = next(row for row in store.positions() if row["activation_epoch_id"] == first)
            original = store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND", position_ids=[position["position_id"]])[0]
            original_events = store.execution_events()
        bad = copy.deepcopy(original["payload"])
        if damage == "array":
            bad = []
        elif damage == "nested":
            bad["asset_metadata"] = []
            bad["asset_metadata_sha256"] = sha256_of(bad["asset_metadata"])
            bad["request_sha256"] = sha256_of({key: value for key, value in bad.items() if key != "request_sha256"})
        elif damage == "hash":
            bad["request_sha256"] = "0" * 64
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(bad), original["event_id"]))
        self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
        sleeps = []
        def advance(delay):
            sleeps.append(delay)
            self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        try:
            with patch("solana_alpha_lab.factory.trading_coordinator.time.sleep", side_effect=advance):
                result = self.coordinator.run(ticks=3)
        finally:
            self.metrics = {"damage": damage, "positions": [{"position_id": row["position_id"], "state": row["state"]}
                for row in self.runner.readback()["positions"]], "attempt_count": len(self.runner.readback()["modeled_attempts"]),
                "fake_quote_effects": len(self.ledger_receipts(ledger)), "clock_advances": len(sleeps)}
        self.assertEqual(result["ticks"], 3)
        self.assertEqual(len(sleeps), 2)
        rows = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
        self.assertEqual(rows[first]["state"], "EXIT_REQUIRED")
        self.assertEqual(rows[first + "-OTHER"]["state"], "RECONCILED")
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        view = self.coordinator.status()
        self.assertEqual(view["status"], "ACTION_REQUIRED")
        self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
        self.assertEqual(Decimal(view["inventory"]["known_cost_basis_floor_usd"]), Decimal("30"))
        self.assertIn("ADAPTER_REQUEST_INTEGRITY_CONFLICT" if damage == "array" else "EXECUTION_ASSET_METADATA_INTEGRITY_CONFLICT",
            {row["reason"] for row in view["incidents"] if row["active"]})
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            self.assertEqual(store.get_execution_event(original["event_id"])["payload"], bad)
            self.assertEqual(len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[position["position_id"]])), 1)
            current = {event["event_id"]: event for event in store.execution_events()}
            self.assertTrue(all(current[event["event_id"]] == event for event in original_events if event["event_id"] != original["event_id"]))
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(original["payload"]), original["event_id"]))
        self.coordinator.run(ticks=2)
        self.assertEqual([row["state"] for row in self.runner.readback()["positions"]], ["RECONCILED", "RECONCILED"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 4)
        self.assertEqual(self.coordinator.status()["status"], "READY")
        return {"damage": damage, "native_run_ticks": 3, "clock_crossed_due_time": True,
            "bad_request": "RETAINED_UNKNOWN_NO_RESEND", "healthy_neighbor": "RECONCILED", "effects_during_quarantine": 3,
            "original_bad_position_attempts_during_quarantine": 1, "known_cost_basis_floor_usd": "30",
            "exact_request_restored": "READY", "final_effects": 4}

    def test_retained_request_array_quarantines_original_position_without_starving_healthy_exit(self):
        self.metrics = self.retained_request_corruption_with_healthy_exit("array")

    def test_retained_request_nested_shape_and_hash_conflicts_keep_neighbor_exit_running(self):
        metrics = []
        for damage in ("nested", "hash"):
            with self.subTest(damage=damage):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    metrics.append(case.retained_request_corruption_with_healthy_exit(damage))
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def entry_grant_blocker_over_future_origin_exit(self, damage):
        """One native run with real scoped grants and only the HTTP seam fake."""
        native_activate = TradingCoordinator.activate
        def envelope_two(coordinator, **kwargs):
            kwargs["profile"]["envelope"].update(max_outstanding_positions=2, max_outstanding_cost_basis_usd="60")
            return native_activate(coordinator, **kwargs)
        with patch.object(TradingCoordinator, "activate", new=envelope_two):
            self.start_operating(mode="SHADOW")
        first_runner, first_epoch, first_source, first_profile = self.runner, self.epoch, self.source, copy.deepcopy(self.profile)
        grant_a = self.scoped_grant(first_epoch, first_runner.strategy["spec_sha256"])
        calls, credentials = [], []
        def adapter(grant, profile):
            return JupiterQuoteAdapter(timeout_seconds=profile["quote"]["timeout_seconds"],
                max_response_bytes=profile["quote"]["max_response_bytes"], grant=grant,
                credential_supplier=lambda: credentials.append(grant["grant_sha256"]))
        def wire(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            body = {"transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
                "inAmount": raw["amount"], "outAmount": "330000000" if raw["inputMint"] != first_profile["quote"]["funding_mint"] else "10000000000000",
                "router": "metis", "mode": "ultra", "feeBps": 20, "feeMint": raw["outputMint"],
                "requestId": "SYNTHETIC-ENTRY-BOUNDARY-" + str(len(calls))}
            if damage == "postclaim" and raw["outputMint"] == closure_fixture.synth_mint("GrantB"):
                # The independently controlled provider model has the original
                # result, but this process receives an unreadable response.
                # The engine must not invent nonfill or resend this attempt.
                return {"status": 200, "body": b"{", "url": ENDPOINT + "?" + urlencode(raw)}
            if damage == "postclaim-router" and raw["outputMint"] == closure_fixture.synth_mint("GrantB"):
                body["router"] = []
            return {"status": 200, "body": json.dumps(body).encode(), "url": ENDPOINT + "?" + urlencode(raw)}
        self.coordinator.quote_adapter = adapter(grant_a, first_profile)
        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=wire):
            self.coordinator.tick()
            original = first_runner.readback()
            self.assertEqual(original["positions"][0]["state"], "OPEN")
            self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
            start = datetime(2026, 10, 5, 12, 16, 6, tzinfo=UTC)
            feed = closure_fixture.EpisodeScenario(self.data / "grant-successor-source", start=start, stops=start + timedelta(hours=3))
            mint = closure_fixture.synth_mint("GrantB")
            obj = closure_fixture.token_object(mint, price=.000003, liquidity=10000, holders=66)
            closure_fixture.nominate(feed.market, start, {"toptraded": [obj], "toptrending": [obj]})
            feed.market.series[mint] = lambda now: closure_fixture.token_object(mint, price=.000003, liquidity=10000,
                holders=60 if now >= datetime(2026, 10, 5, 12, 50, tzinfo=UTC) else 66)
            for tick in (start, datetime(2026, 10, 5, 12, 25, tzinfo=UTC), datetime(2026, 10, 5, 12, 50, tzinfo=UTC)):
                feed.tick(tick)
            self.profile = {**copy.deepcopy(first_profile), "source": {"root": str(feed.data_root),
                "file": "observation_schedule_state.sqlite", "schedule_sha256": feed.schedule["schedule_sha256"],
                "activation_id": feed.activation_id}}
            self.source, self.mint = feed, mint
            self.now = datetime(2026, 10, 5, 12, 55, tzinfo=UTC)
            self.quote_inputs(at="2026-10-05T12:55:00Z")
            self.coordinator = TradingCoordinator(self.runner, mode="SHADOW", clock=lambda: self.now)
            self.coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:55:00Z", profile=self.profile,
                switch_key="ENTRY-GRANT-BLOCKER-B", expected_current_epoch=first_epoch)
            grant_b = self.scoped_grant(self.epoch, self.runner.strategy["spec_sha256"],
                expires="2026-10-05T15:00:00Z" if damage in {"postclaim", "postclaim-router", "asset-array", "funding-zero"} else "2026-10-05T12:54:00Z")
            selected = [adapter(grant_a, first_profile)] + ([adapter(grant_b, self.profile)] if damage != "missing" else [])
            coordinator = TradingCoordinator(self.runner, mode="SHADOW", clock=lambda: self.now, quote_adapters=selected)
            original_pid = os.getpid()
            sleeps = []
            first_source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
            (first_source.data_root / "funding.json").write_text(json.dumps({"mint": first_profile["quote"]["funding_mint"],
                "decimals": 9, "unit_price_usd": "100", "observed_at": "2026-10-05T13:10:00Z",
                "available_at": "2026-10-05T13:10:00Z"}), encoding="utf-8")
            def advance(delay):
                sleeps.append(delay)
                self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
            asset_path = self.source.data_root / "assets.json"
            original_assets = asset_path.read_bytes()
            funding_path = self.source.data_root / "funding.json"
            original_funding = funding_path.read_bytes()
            if damage == "asset-array":
                asset_path.write_text("[]", encoding="utf-8")
            elif damage == "funding-zero":
                funding = json.loads(original_funding)
                funding.update(decimals=0, unit_price_usd="1000")
                funding_path.write_text(json.dumps(funding), encoding="utf-8")
            try:
                with patch("solana_alpha_lab.factory.trading_coordinator.time.sleep", side_effect=advance):
                    result = coordinator.run(ticks=3)
            finally:
                self.metrics = {"grant": damage, "positions": [{"position_id": row["position_id"],
                    "epoch": row["activation_epoch_id"], "state": row["state"]} for row in self.runner.readback()["positions"]],
                    "attempt_count": len(self.runner.readback()["modeled_attempts"]), "quote_claims": len(self.claims(self.runner)),
                    "fake_http_calls": len(calls), "clock_advances": len(sleeps), "same_process": os.getpid() == original_pid}
            self.assertEqual(result["ticks"], 3)
            self.assertEqual(os.getpid(), original_pid)
            self.assertEqual(len(sleeps), 2)
            rows = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
            self.assertEqual(rows[first_epoch]["state"], "RECONCILED")
            self.assertEqual(rows[first_epoch]["position_id"], original["positions"][0]["position_id"])
            if damage in {"postclaim", "postclaim-router"}:
                self.assertEqual(rows[self.epoch]["state"], "ATTEMPTING")
                self.assertEqual(len(calls), 3)
                claims = self.claims(self.runner)
                self.assertEqual([row["payload"]["grant_sha256"] for row in claims],
                    [grant_a["grant_sha256"], grant_b["grant_sha256"], grant_a["grant_sha256"]])
                view = coordinator.status()
                self.assertEqual(view["pending_attempts"], 1)
                self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
                postclaim_reason = "QUOTE_ROUTE_IDENTITY_INVALID" if damage == "postclaim-router" else "QUOTE_RESPONSE_SCHEMA_INVALID"
                self.assertIn(postclaim_reason, {row["reason"] for row in view["entry_blockers"]})
                with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                    attempt = store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[rows[self.epoch]["position_id"]])[0]
                    request = store.get_execution_event("REQUEST-" + attempt["event_id"])
                    self.assertIsNone(store.get_execution_event("FINAL-" + attempt["event_id"]))
                inbox = self.data / "result-inbox"
                inbox.mkdir(exist_ok=True)
                callback = {"attempt_id": attempt["event_id"], "result_id": "SYNTHETIC-ORIGINAL-B-QUOTE",
                    "outcome": "LANDED_SUCCESS", "observed_at": "2026-10-05T12:55:00Z", "schema_version": "1.1",
                    "filled_notional_usd": "30", "quantity_filled": "10000000", "quantity_unit": "TOKEN_UNITS",
                    "unit_price_usd": "0.000003", "fee_semantics": "INCLUDED_IN_UNIT_PRICE"}
                (inbox / (attempt["event_id"] + ".json")).write_text(json.dumps(callback), encoding="utf-8")
                coordinator.tick()
                coordinator.tick()
                self.assertEqual(len(calls), 3)
                self.assertEqual(self.claims(self.runner), claims)
                final = self.runner.readback()
                self.assertEqual(len(final["modeled_attempts"]), 3)
                self.assertEqual({row["activation_epoch_id"]: row["state"] for row in final["positions"]},
                    {first_epoch: "RECONCILED", self.epoch: "OPEN"})
                with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                    self.assertEqual(store.get_execution_event(attempt["event_id"]), attempt)
                    self.assertEqual(store.get_execution_event("REQUEST-" + attempt["event_id"]), request)
                    self.assertIsNotNone(store.get_execution_event("FINAL-" + attempt["event_id"]))
                    accepted = [event["payload"]["result"] for event in store.filtered_execution_events(
                        event_type="MODELED_RESULT_ACCEPTED", position_ids=[rows[self.epoch]["position_id"]])]
                    self.assertEqual(accepted, [callback])
                self.assertEqual(coordinator.status()["pending_attempts"], 0)
                self.assertEqual(coordinator.status()["entry_blockers"], [])
                return {"native_run_ticks": 3, "same_process": True, "original_A": "RECONCILED",
                    "B_after_bad_response": "ATTEMPTING_PENDING_ORIGINAL", "B_attempts": 1, "B_grant_claims": 1,
                    "fake_http_calls": 3, "callback_original_clock": "2026-10-05T12:55:00Z", "same_request_after_callback": True,
                    "callback_result": "LANDED_SUCCESS", "B_after_callback": "OPEN", "pending_after_callback": 0,
                    "resends": 0, "fabricated_nonfills": 0, "entry_reason": postclaim_reason}
            self.assertEqual(rows[self.epoch]["state"], "WATCHED")
            self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 2)
            self.assertEqual(self.runner.readback()["modeled_attempts"][0], original["modeled_attempts"][0])
            claims = self.claims(self.runner)
            self.assertEqual([row["payload"]["grant_sha256"] for row in claims], [grant_a["grant_sha256"], grant_a["grant_sha256"]])
            self.assertEqual(len(calls), 2)
            self.assertEqual(credentials, [grant_a["grant_sha256"], grant_a["grant_sha256"]])
            with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                b_requests = store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND",
                    position_ids=[rows[self.epoch]["position_id"]])
                b_attempts = store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED",
                    position_ids=[rows[self.epoch]["position_id"]])
            self.assertEqual(b_requests, [])
            self.assertEqual(b_attempts, [])
            view = coordinator.status()
            self.assertEqual(view["status"], "ACTION_REQUIRED")
            self.assertTrue(view["exit_reconciliation_healthy"])
            self.assertFalse(view["entries_enabled"])
            entry_reason = "EXECUTION_ASSET_IDENTITY_INVALID" if damage == "asset-array" else "QUOTE_RAW_AMOUNT_ZERO" if damage == "funding-zero" else "QUOTE_EXTERNAL_AUTHORITY_REQUIRED"
            self.assertIn(entry_reason, {row["reason"] for row in view["entry_blockers"]})
            self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
            self.assertEqual(view["next_safe_action"], "CHECK_EXECUTION_QUOTE_INPUTS" if damage == "asset-array"
                else "VERIFY_ORIGINAL_ENTRY_GRANT_OR_INPUT")
            # Restore only B's explicitly granted dependency; no quota reset or
            # fresh activation. Its expired signal must not become a new effect.
            if damage == "asset-array":
                asset_path.write_bytes(original_assets)
            elif damage == "funding-zero":
                funding_path.write_bytes(original_funding)
            else:
                grant_b = self.scoped_grant(self.epoch, self.runner.strategy["spec_sha256"])
                coordinator.quote_adapters[("SHADOW", self.epoch)] = adapter(grant_b, self.profile)
            coordinator.tick()
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(self.claims(self.runner)), 2)
            self.assertEqual(credentials, [grant_a["grant_sha256"], grant_a["grant_sha256"]])
            retained_incident = next(row for row in coordinator.status()["incidents"]
                if row["incident_key"] == "ENTRY-SHADOW-" + rows[self.epoch]["position_id"])
            self.assertEqual(retained_incident["reason"], entry_reason)
            self.assertEqual(retained_incident["first_at"], "2026-10-05T12:55:00Z")
        return {"grant": damage, "native_run_ticks": 3, "same_process": True, "clock_crossed_origin_exit_due": True,
            "original_A": "RECONCILED", "B_preclaim_attempts": 0, "B_preclaim_quote_claims": 0,
            "A_grant_claims": 2, "B_grant_claims": 0, "fake_http_calls": 2,
            "exit_health_with_entry_blocker": True, "inventory_with_entry_blocker": "KNOWN",
            "signal_stale_after_dependency_repair_no_effect": True, "entry_reason": entry_reason,
            "B_credential_reads": 0, "B_requests": 0, "incident_audit_retained": True,
            "clock_advances": len(sleeps), "position_rows": [{"position_id": row["position_id"],
                "activation_epoch_id": row["activation_epoch_id"], "state": row["state"]} for row in rows.values()],
            "B_request_rows": b_requests, "B_attempt_rows": b_attempts,
            "quote_claim_rows": [{"event_id": row["event_id"], "position_id": row["position_id"],
                "payload": row["payload"]} for row in claims], "retained_incident": dict(retained_incident)}

    def test_invalid_successor_asset_array_keeps_same_native_run_servicing_future_origin_exit(self):
        self.metrics = self.entry_grant_blocker_over_future_origin_exit("asset-array")

    def test_valid_successor_funding_raw_zero_keeps_future_original_exit_without_preclaim_effect(self):
        self.metrics = self.entry_grant_blocker_over_future_origin_exit("funding-zero")

    def test_unhashable_postclaim_router_keeps_original_pending_callback_and_future_exit_without_resend(self):
        self.metrics = self.entry_grant_blocker_over_future_origin_exit("postclaim-router")

    def test_current_asset_file_shapes_are_typed_before_native_claim_or_credential(self):
        self.start_operating(mode="SHADOW")
        reads, calls = [], []
        grant = self.scoped_grant(self.epoch, self.runner.strategy["spec_sha256"])
        self.coordinator.quote_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
            grant=grant, credential_supplier=lambda: reads.append(True))
        asset_path = self.source.data_root / "assets.json"
        valid = json.loads(asset_path.read_text(encoding="utf-8"))
        variants = [("missing", None, "EXECUTION_ASSET_IDENTITY_INVALID"),
            ("json", "{", "EXECUTION_ASSET_IDENTITY_INVALID"),
            ("array", "[]", "EXECUTION_ASSET_IDENTITY_INVALID"),
            ("missing-mint", "{}", "EXECUTION_ASSET_IDENTITY_INVALID"),
            ("row-array", json.dumps({self.mint: []}), "EXECUTION_ASSET_IDENTITY_INVALID")]
        for label, fields, reason in (("missing-decimals", {"decimals": None}, "EXECUTION_ASSET_IDENTITY_INVALID"),
                ("boolean-decimals", {"decimals": True}, "EXECUTION_ASSET_IDENTITY_INVALID"),
                ("wrong-mint", {"mint": closure_fixture.synth_mint("Wrong")}, "EXECUTION_ASSET_IDENTITY_INVALID"),
                ("missing-time", {"observed_at": None}, "EXECUTION_OBSERVATION_STALE_OR_FUTURE"),
                ("invalid-time", {"available_at": []}, "EXECUTION_OBSERVATION_STALE_OR_FUTURE"),
                ("future-time", {"available_at": "2026-10-05T12:41:00Z"}, "EXECUTION_OBSERVATION_STALE_OR_FUTURE")):
            variants.append((label, json.dumps({self.mint: {**valid[self.mint], **fields}}), reason))
        reasons = []
        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=lambda *a, **k: calls.append(True)):
            for label, content, reason in variants:
                with self.subTest(input=label):
                    if content is None:
                        asset_path.unlink()
                    else:
                        asset_path.write_text(content, encoding="utf-8")
                    tick = self.coordinator.tick()
                    self.assertEqual(tick["status"], "TICK_COMPLETE")
                    self.assertFalse(tick["entries_enabled"])
                    view = self.runner.readback()
                    self.assertEqual(view["modeled_attempts"], [])
                    self.assertEqual(view["positions"][0]["state"], "WATCHED")
                    with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                        incident = store._conn.execute("SELECT reason FROM ordinary_incidents WHERE active=1 AND incident_key=?",
                            ("ENTRY-SHADOW-" + view["positions"][0]["position_id"],)).fetchone()
                        self.assertEqual(incident["reason"], reason)
                        self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"), [])
                    reasons.append({"input": label, "reason": reason})
        self.assertEqual(self.claims(self.runner), [])
        self.assertEqual(reads, [])
        self.assertEqual(calls, [])
        self.metrics = {"typed_inputs": reasons, "attempts": 0, "requests": 0,
            "quote_claims": 0, "credential_reads": 0, "fake_http_calls": 0}

    def test_current_witness_outer_shape_is_typed_before_native_claim(self):
        self.witness_operating()
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        witness = self.source.data_root / self.admission["witness_raw_body_rel"]
        def corrupt(point):
            if point == "AFTER_DECISION_COMMIT":
                witness.write_text("[]", encoding="utf-8")
        self.coordinator.fault = corrupt
        for content in ("[]", "{"):
            if content == "{":
                witness.write_text(content, encoding="utf-8")
            tick = self.coordinator.tick()
            self.assertEqual(tick["status"], "TICK_COMPLETE")
            self.assertFalse(tick["entries_enabled"])
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])
        self.assertEqual(self.claims(self.runner), [])
        self.assertFalse(ledger.exists())
        self.assertIn("EXECUTION_ASSET_WITNESS_INTEGRITY_CONFLICT",
            {row["reason"] for row in self.coordinator.status()["entry_blockers"]})
        self.metrics = {"witness_shapes": ["ARRAY", "INVALID_JSON"], "attempts": 0,
            "requests": 0, "quote_claims": 0, "fake_http_calls": 0}

    def test_expired_and_missing_successor_grants_keep_same_native_run_servicing_future_origin_exit(self):
        metrics = []
        for damage in ("expired", "missing"):
            with self.subTest(grant=damage):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    metrics.append(case.entry_grant_blocker_over_future_origin_exit(damage))
                finally:
                    self.metrics = {"cases": metrics, "last_case": getattr(case, "metrics", {})}
                    case.tearDown()

    @patch("solana_alpha_lab.factory.paper_shadow_operations._now", new=lambda: "2026-10-05T12:40:00Z")
    def test_shared_store_failure_remains_fatal_and_atomic_in_ordinary_run(self):
        self.start_operating()
        self.coordinator.tick()
        before = self.runner.readback()
        # This named shared owner fails before any new effects. Source failures
        # and per-position inputs have separate continuation semantics.
        with patch.object(PaperPlaneStore, "obligation_positions", side_effect=sqlite3.OperationalError("SYNTHETIC_SHARED_STORE_FAILURE")):
            with self.assertRaises(sqlite3.OperationalError):
                self.coordinator.run(ticks=3)
        self.assertEqual(self.runner.readback(), before)
        with patch.object(PaperPlaneStore, "immediate_write", side_effect=sqlite3.OperationalError("SYNTHETIC_SHARED_DISCOVERY_WRITE_FAILURE")):
            with self.assertRaises(sqlite3.OperationalError):
                self.coordinator.run(ticks=3)
        self.assertEqual(self.runner.readback(), before)
        self.metrics = {"shared_store": "FATAL", "shared_discovery_write": "FATAL", "new_attempts": 0,
            "new_effects": 0, "readback_unchanged": True}

    def test_postclaim_entry_response_failure_keeps_original_pending_and_future_old_exit_in_same_run(self):
        self.metrics = self.entry_grant_blocker_over_future_origin_exit("postclaim")

    def empty_ledger(self):
        ledger, _ = self.wire_files()
        with closing(sqlite3.connect(ledger)) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS calls(call_id INTEGER PRIMARY KEY,attempt_id TEXT NOT NULL,receipt_json TEXT)")
            connection.commit()
        return ledger

    def restored(self, backup, *, suffix="restored", adapter=None, mode="SHADOW"):
        destination = self.root / "local" / suffix
        destination.mkdir()
        shutil.copyfile(self.data / "offline_runtime.json", destination / "offline_runtime.json")
        runner = TradingContinuityRunner(self.root, data_root=destination)
        outcome = restore_native_backup(backup_path=backup, destination_runner=runner)
        self.assertFalse(outcome["new_effects_enabled"])
        coordinator = TradingCoordinator(runner, mode=mode, clock=lambda: self.now,
            quote_adapter=adapter)
        self.assertTrue(coordinator.status()["restore_guard"])
        return runner, coordinator

    def acknowledge(self, coordinator, cut):
        inventory = coordinator.status()["inventory"]
        coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(inventory),
            as_of=cut["as_of"], cut=cut)
        self.assertFalse(coordinator.status()["restore_guard"])

    def claims(self, runner):
        with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
            return store.filtered_execution_events(event_type="QUOTE_CALL_CLAIMED")

    def witness_operating(self):
        original_inputs = self.quote_inputs

        def witness_profile(**kwargs):
            self.profile["quote"]["asset_metadata_file"] = None
            original_inputs(**kwargs)

        with patch.object(self, "quote_inputs", side_effect=witness_profile):
            self.start_operating(mode="SHADOW")
        self.assertIsNone(self.profile["quote"]["asset_metadata_file"])

    def original_grant(self):
        grant = {"quote_calls_authorized": True, "route_id": ROUTE_ID, "endpoint": ENDPOINT,
            "registry_path": REGISTRY_PATH, "mode": "SHADOW", "activation_epoch_id": self.epoch,
            "strategy_sha256": self.runner.strategy["spec_sha256"], "signing_authorized": False,
            "financial_authority": False, "calls_max": 1, "expires_at": "2026-10-05T14:00:00Z"}
        return {**grant, "grant_sha256": sha256_of(grant)}

    def production_cut(self, backup, *, effects=()):
        cut = self.coordinator.export_recovery_cut(backup_path=backup, effects=list(effects),
            external_cut_id="INDEPENDENT-SYNTHETIC-DELAYED-CUT", as_of=self.now.isoformat().replace("+00:00", "Z"))
        return {**cut, "cut_sha256": sha256_of(cut)}

    def partial_shadow(self):
        self.start_operating(mode="SHADOW", exit_cap="4000000000000")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "120000000"},
                                      {"outAmount": "132000000"}, {"outAmount": "60000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()
        original = self.runner.readback()["positions"][0]
        self.assertEqual(Decimal(original["remaining_qty_dec"]), Decimal("6000000"))
        self.assertEqual(Decimal(original["remaining_cost_basis_usd_dec"]), Decimal("18"))
        return ledger, original

    def pending_entry(self):
        self.start_operating(mode="SHADOW")
        self.coordinator.quote_adapter = RecordingQuoteAdapter(self.empty_ledger(), [])
        def stop(point):
            if point == "AFTER_ATTEMPT_COMMIT":
                raise RuntimeError("SYNTHETIC_STOP_BEFORE_EFFECT")
        self.coordinator.fault = stop
        with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_STOP_BEFORE_EFFECT"):
            self.coordinator.tick()
        self.coordinator.fault = lambda _point: None
        self.coordinator.tick()
        return self.runner.readback()["modeled_attempts"][0]["event_id"]

    def original_callback(self, attempt_id, *, outcome, version="1.1"):
        result = {"attempt_id":attempt_id, "result_id":"SYNTHETIC-NONFILL-"+outcome,
            "outcome":outcome, "observed_at":"2026-10-05T12:40:00Z", "chargeable_cost_usd":"0"}
        if version == "1.1":
            result["schema_version"] = version
        inbox = self.data / "result-inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / (attempt_id+".json")).write_text(json.dumps(result), encoding="utf-8")
        return result

    def test_original_entry_nonfill_recovery_clears_only_proved_incident_after_cold_restart(self):
        outcomes = [("1.1", outcome) for outcome in ("NO_ROUTE", "REJECTED_BEFORE_SEND",
            "DROPPED_OR_EXPIRED_NOT_PROCESSED", "LANDED_FAILED")] + [("1.0", "NO_ROUTE")]
        observations = []
        for version, outcome in outcomes:
            with self.subTest(version=version, outcome=outcome):
                case = OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    aid = case.pending_entry()
                    original = case.original_callback(aid, outcome=outcome, version=version)
                    case.coordinator.tick()
                    case.coordinator.tick()
                    case.coordinator.tick()
                    cold_runner = TradingContinuityRunner(case.root, data_root=case.data)
                    cold = TradingCoordinator(cold_runner, mode="SHADOW", clock=lambda:case.now)
                    view, readback = cold.status(), cold_runner.readback()
                    self.assertEqual(view["status"], "READY")
                    self.assertTrue(view["integrity_verified"])
                    self.assertTrue(view["exit_reconciliation_healthy"])
                    self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
                    self.assertEqual(view["inventory"]["position_count"], 0)
                    self.assertEqual(view["pending_attempts"], 0)
                    self.assertEqual(len(readback["modeled_attempts"]), 1)
                    self.assertEqual(readback["modeled_results"][0]["payload"]["result"], original)
                    self.assertEqual(readback["positions"][0]["state"], "CANCELLED")
                    with closing(PaperPlaneStore(cold_runner.store_path, readonly=True)) as store:
                        incidents = store._conn.execute("SELECT reason,active FROM ordinary_incidents WHERE incident_key=?", (aid,)).fetchall()
                    self.assertEqual([(row[0],row[1]) for row in incidents], [("ATTEMPT_RECONCILIATION_REQUIRED",0)])
                    observations.append({"version":version,"outcome":outcome,"status":view["status"],"attempts":1,"pending":0})
                finally:
                    case.tearDown()
        self.metrics = {"cases":observations,"quote_effects":0}

    def test_nonfill_corrupt_witness_remains_active_and_truthful_restore_recovers(self):
        from solana_alpha_lab.factory.paper_plane import assert_quantity_inventory_witness
        aid = self.pending_entry()
        self.original_callback(aid, outcome="NO_ROUTE")
        original_result = self.runner.result
        originals = {}
        def accept_then_damage(result):
            accepted = original_result(result)
            with closing(PaperPlaneStore(self.runner.store_path)) as store:
                final = store.get_execution_event("FINAL-"+aid)
                originals["final"] = final
                store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (final["event_id"],))
            return accepted
        with patch.object(self.runner, "for_epoch", return_value=self.runner), patch.object(self.runner, "result", side_effect=accept_then_damage):
            self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"], "ACTION_REQUIRED")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            position = store.positions()[0]
            with self.assertRaisesRegex(PaperPlaneError,"EXIT_INVENTORY_WITNESS_CONFLICT"):
                assert_quantity_inventory_witness(store, position)
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                (json.dumps(originals["final"]["payload"]), "FINAL-"+aid))
            accepted=store.get_execution_event(originals["final"]["payload"]["result_event_id"])
            damaged=copy.deepcopy(accepted["payload"])
            damaged["result"]["quantity_filled"]="1"
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                (json.dumps(damaged),accepted["event_id"]))
        self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"],"ACTION_REQUIRED")
        self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"],"UNKNOWN")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                (json.dumps(accepted["payload"]),accepted["event_id"]))
            for field, value in (("remaining_qty_dec","1"),("entry_fee_usd_dec",".01"),("entered_notional_usd_dec","30")):
                store._conn.execute("UPDATE positions SET "+field+"=? WHERE position_id=?", (value,position["position_id"]))
                with self.assertRaisesRegex(PaperPlaneError,"EXIT_INVENTORY_WITNESS_CONFLICT"):
                    assert_quantity_inventory_witness(store,store.positions()[0])
                store._conn.execute("UPDATE positions SET "+field+"=? WHERE position_id=?", (position[field],position["position_id"]))
        self.coordinator.tick()
        self.coordinator.tick()
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]),1)
        self.metrics={"damaged_final":"ACTION_REQUIRED","damaged_result":"UNKNOWN_ACTION_REQUIRED",
            "damaged_caches":3,"truthful_restore":"READY","quote_effects":0}

    def scoped_grant(self, epoch, strategy_sha, *, calls_max=10, expires="2026-10-05T15:00:00Z"):
        path = self.root / REGISTRY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(closure_fixture.ROOT / REGISTRY_PATH, path)
        grant = {"quote_calls_authorized":True,"route_id":ROUTE_ID,"endpoint":ENDPOINT,
            "registry_path":REGISTRY_PATH,"registry_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "mode":"SHADOW","activation_epoch_id":epoch,"strategy_sha256":strategy_sha,
            "signing_authorized":False,"financial_authority":False,"calls_max":calls_max,"expires_at":expires}
        return verified_quote_grant(self.root,{**grant,"grant_sha256":sha256_of(grant)})

    def test_unknown_entry_recovery_keeps_original_pending_identity_without_quote_resend(self):
        aid=self.pending_entry()
        original=self.original_callback(aid,outcome="UNKNOWN_REQUIRES_RECONCILIATION")
        self.coordinator.tick()
        self.coordinator.tick()
        cold=TradingCoordinator(TradingContinuityRunner(self.root,data_root=self.data),mode="SHADOW",clock=lambda:self.now)
        self.assertEqual(cold.status()["pending_attempts"],1)
        self.assertEqual(cold.status()["inventory"]["inventory_status"],"UNKNOWN")
        self.assertEqual(cold.status()["status"],"ACTION_REQUIRED")
        view=self.runner.readback()
        self.assertEqual(len(view["modeled_attempts"]),1)
        self.assertEqual(view["modeled_results"][0]["payload"]["result"],original)
        self.assertEqual(view["positions"][0]["state"],"UNKNOWN")
        self.metrics={"pending":1,"attempts":1,"fake_http_calls":0}

    def test_invalid_quote_scope_and_expiry_deny_before_native_attempt_and_credential(self):
        self.start_operating(mode="SHADOW")
        reads,calls=[],[]
        grant=self.scoped_grant(self.epoch,self.runner.strategy["spec_sha256"])
        for change in ({"mode":"PAPER"},{"activation_epoch_id":"ACTIVATION-EPOCH-WRONG"},
            {"strategy_sha256":"b"*64},{"expires_at":"2026-10-05T12:39:59Z"},{"calls_max":0},None):
            with self.subTest(change=change):
                body={k:v for k,v in grant.items() if k!="grant_sha256"}
                if change is not None:
                    body.update(change)
                    candidate=verified_quote_grant(self.root,{**body,"grant_sha256":sha256_of(body)})
                else:
                    candidate=None
                self.coordinator.quote_adapter=JupiterQuoteAdapter(timeout_seconds=1,max_response_bytes=8192,
                    grant=candidate,credential_supplier=lambda:reads.append(True))
                with patch("solana_alpha_lab.factory.trading_adapters.http_quote",side_effect=lambda *a,**k:calls.append(True)):
                    tick=self.coordinator.tick()
                self.assertEqual(tick["status"],"TICK_COMPLETE")
                self.assertFalse(tick["entries_enabled"])
                view=self.runner.readback()
                self.assertEqual(view["modeled_attempts"],[])
                self.assertEqual(view["modeled_results"],[])
                self.assertEqual(view["positions"][0]["state"],"WATCHED")
                with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
                    blocker=store._conn.execute("SELECT reason,active FROM ordinary_incidents WHERE incident_key=?",
                        ("ENTRY-SHADOW-"+view["positions"][0]["position_id"],)).fetchone()
                    self.assertEqual(dict(blocker),{"reason":"QUOTE_EXTERNAL_AUTHORITY_REQUIRED","active":1})
                    self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"),[])
                self.assertEqual(self.claims(self.runner),[])
                self.assertEqual(reads,[])
                self.assertEqual(calls,[])
        valid=JupiterQuoteAdapter(timeout_seconds=1,max_response_bytes=8192,grant=grant,credential_supplier=lambda:None)
        conflict={**grant,"calls_max":11}
        conflict["grant_sha256"]=sha256_of({k:v for k,v in conflict.items() if k!="grant_sha256"})
        other=JupiterQuoteAdapter(timeout_seconds=1,max_response_bytes=8192,grant=conflict,credential_supplier=lambda:None)
        with self.assertRaisesRegex(PaperPlaneError,"QUOTE_GRANT_SELECTION_CONFLICT"):
            TradingCoordinator(self.runner,mode="SHADOW",quote_adapters=[valid,other])
        self.assertEqual(len(TradingCoordinator(self.runner,mode="SHADOW",quote_adapters=[valid,valid]).quote_adapters),1)
        self.metrics={"preclaim_denials":6,"conflicting_duplicate":"DENY","identical_duplicate":"ONE_SCOPE",
            "tick_status":"TICK_COMPLETE","entries_enabled":False,"entry_reason":"QUOTE_EXTERNAL_AUTHORITY_REQUIRED",
            "attempts":0,"requests":0,"results":0,"quote_claims":0,"credential_reads":0,"fake_http_calls":0}

    def test_quote_expiry_rechecked_at_atomic_claim_and_last_http_boundary(self):
        cases=[]
        for seam in ("BEFORE_CLAIM","AFTER_ATTEMPT_COMMIT"):
            with self.subTest(seam=seam):
                case=OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    case.start_operating(mode="SHADOW")
                    grant=case.scoped_grant(case.epoch,case.runner.strategy["spec_sha256"],expires="2026-10-05T12:40:00Z")
                    reads,calls=[],[]
                    case.coordinator.quote_adapter=JupiterQuoteAdapter(timeout_seconds=1,max_response_bytes=8192,
                        grant=grant,credential_supplier=lambda:reads.append(True))
                    if seam=="BEFORE_CLAIM":
                        inputs=case.coordinator._inputs
                        def prepare_then_expire(*args):
                            result=inputs(*args)
                            case.now+=timedelta(seconds=1)
                            return result
                        context=patch.object(case.coordinator,"_inputs",side_effect=prepare_then_expire)
                    else:
                        context=patch.object(case.coordinator,"fault",side_effect=lambda point:setattr(case,"now",case.now+timedelta(seconds=1))
                            if point=="AFTER_ATTEMPT_COMMIT" else None)
                    with context,patch("solana_alpha_lab.factory.trading_adapters.http_quote",side_effect=lambda *a,**k:calls.append(True)):
                        tick=case.coordinator.tick()
                    self.assertEqual(tick["status"],"TICK_COMPLETE")
                    self.assertFalse(tick["entries_enabled"])
                    expected=0 if seam=="BEFORE_CLAIM" else 1
                    original=case.runner.readback()
                    original_claims=case.claims(case.runner)
                    self.assertEqual(len(original["modeled_attempts"]),expected)
                    self.assertEqual(original["modeled_results"],[])
                    self.assertEqual(len(original_claims),expected)
                    with closing(PaperPlaneStore(case.runner.store_path,readonly=True)) as store:
                        blocker=store._conn.execute("SELECT reason,active FROM ordinary_incidents WHERE incident_key=?",
                            ("ENTRY-SHADOW-"+original["positions"][0]["position_id"],)).fetchone()
                        self.assertEqual(dict(blocker),{"reason":"QUOTE_EXTERNAL_AUTHORITY_REQUIRED","active":1})
                        original_requests=store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND")
                        self.assertEqual(len(original_requests),expected)
                    self.assertEqual(reads,[])
                    self.assertEqual(calls,[])
                    if expected:
                        with patch("solana_alpha_lab.factory.trading_adapters.http_quote",side_effect=lambda *a,**k:calls.append(True)):
                            repeated=case.coordinator.tick()
                        self.assertEqual(repeated["status"],"TICK_COMPLETE")
                        self.assertFalse(repeated["entries_enabled"])
                        self.assertEqual(case.coordinator.status()["pending_attempts"],1)
                        self.assertEqual(case.coordinator.status()["inventory"]["inventory_status"],"UNKNOWN")
                        self.assertEqual(len(case.claims(case.runner)),1)
                        self.assertEqual(case.claims(case.runner),original_claims)
                        self.assertEqual(case.runner.readback()["modeled_attempts"],original["modeled_attempts"])
                        self.assertEqual(case.runner.readback()["modeled_results"],[])
                        self.assertEqual(case.runner.readback()["positions"][0]["position_id"],original["positions"][0]["position_id"])
                        with closing(PaperPlaneStore(case.runner.store_path,readonly=True)) as store:
                            self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"),original_requests)
                        self.assertEqual(reads,[])
                        self.assertEqual(calls,[])
                    cases.append({"seam":seam,"tick_status":tick["status"],"entries_enabled":tick["entries_enabled"],
                        "entry_reason":dict(blocker)["reason"],"attempts":expected,"requests":len(original_requests),
                        "quote_claims":len(original_claims),"results":0,"credential_reads":len(reads),"fake_http_calls":len(calls),
                        "original_attempt_id":None if not expected else original["modeled_attempts"][0]["payload"]["attempt_id"],
                        "original_request_sha256":None if not expected else original_requests[0]["payload"]["request_sha256"],
                        "original_pending_recovery":"RETAINED_WITHOUT_RESEND" if expected else "NO_ATTEMPT"})
                finally:
                    case.tearDown()
        self.metrics={"preclaim_expired_attempts":0,"postclaim_expired_attempts":1,"credential_reads":0,"fake_http_calls":0,
            "cases":cases}

    def test_cli_repeated_quote_grant_paths_bind_original_profiles_and_reject_conflicting_scope(self):
        from scripts import trading_continuity as cli
        self.start_operating(mode="SHADOW")
        first_epoch,first_runner,first_profile=self.epoch,self.runner,copy.deepcopy(self.profile)
        grant_a=self.scoped_grant(first_epoch,first_runner.strategy["spec_sha256"])
        self.prepare(operating=True,suffix="-B",negative=True,exit_point="E3600")
        second_profile=copy.deepcopy(first_profile)
        second_profile["quote"].update(timeout_seconds=2,max_response_bytes=4096)
        self.coordinator=TradingCoordinator(self.runner,mode="SHADOW",clock=lambda:self.now)
        self.coordinator.activate(epoch_id=self.epoch,at="2026-10-05T12:40:00Z",profile=second_profile,
            switch_key="CLI-REPEAT-GRANTS",expected_current_epoch=first_epoch)
        grant_b=self.scoped_grant(self.epoch,self.runner.strategy["spec_sha256"])
        for filename,grant in (("grant-a.json",grant_a),("grant-b.json",grant_b)):
            (self.data/filename).write_text(json.dumps(grant),encoding="utf-8")
        (self.data/"operating_runtime.json").write_text(json.dumps({"schema":"smial.operating-runtime",
            "schema_version":"1.0","evidence_class":"OBSERVED"}),encoding="utf-8")
        argv=["tick","--repository-root",str(self.root),"--data-root",str(self.data),"--scope-root",str(self.root/"local"),
            "--mode","SHADOW","--credential-env","SYNTHETIC_UNUSED","--quote-grant","grant-a.json","--quote-grant","grant-b.json"]
        with (patch("solana_alpha_lab.factory.trading_coordinator.datetime",wraps=datetime) as physical,
                patch("solana_alpha_lab.factory.trading_adapters.JupiterQuoteAdapter",wraps=JupiterQuoteAdapter) as constructor):
            physical.now.return_value=self.now
            output=io.StringIO()
            with redirect_stdout(output):
                code=cli.main(argv)
            self.assertEqual(code,0,output.getvalue())
            configured=[call.kwargs for call in constructor.call_args_list if call.kwargs.get("grant")]
            self.assertEqual([(c["grant"]["activation_epoch_id"],c["timeout_seconds"],c["max_response_bytes"]) for c in configured],
                [(first_epoch,1,8192),(self.epoch,2,4096)])
        conflict={**grant_a,"calls_max":11}
        conflict["grant_sha256"]=sha256_of({k:v for k,v in conflict.items() if k!="grant_sha256"})
        (self.data/"grant-conflict.json").write_text(json.dumps(conflict),encoding="utf-8")
        with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
            before=store.execution_events()
        output=io.StringIO()
        with redirect_stdout(output):
            code=cli.main(argv+["--quote-grant","grant-conflict.json"])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(output.getvalue())["reason_code"],"QUOTE_GRANT_SELECTION_CONFLICT")
        with closing(PaperPlaneStore(self.runner.store_path,readonly=True)) as store:
            self.assertEqual(store.execution_events(),before)
        self.assertEqual(self.runner.readback()["modeled_attempts"],[])
        self.assertEqual(self.claims(self.runner),[])
        self.metrics={"repeat_paths":2,"original_profile_bounds":[[1,8192],[2,4096]],"conflicting_scope":"DENY_BEFORE_WRITE",
            "credential_reads":0,"fake_http_calls":0}

    def test_separate_original_quote_grants_close_predecessor_and_admit_successor_with_cold_quota(self):
        self.start_operating(mode="SHADOW")
        first_runner, first_epoch, first_source, first_profile = self.runner, self.epoch, self.source, copy.deepcopy(self.profile)
        grant_a = self.scoped_grant(first_epoch, first_runner.strategy["spec_sha256"])
        credential_reads, calls = [], []
        def adapter(grant, profile):
            return JupiterQuoteAdapter(timeout_seconds=profile["quote"]["timeout_seconds"],
                max_response_bytes=profile["quote"]["max_response_bytes"], grant=grant,
                credential_supplier=lambda:credential_reads.append(grant["grant_sha256"]))
        def fake_http(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append({"request":dict(raw),"timeout_seconds":limits["timeout_seconds"],"max_response_bytes":limits["max_response_bytes"]})
            output = "330000000" if raw["inputMint"] != first_profile["quote"]["funding_mint"] else "10000000000000"
            body = {"transaction":None,"inputMint":raw["inputMint"],"outputMint":raw["outputMint"],
                "inAmount":raw["amount"],"outAmount":output,"router":"metis","mode":"ultra",
                "feeBps":20,"feeMint":raw["outputMint"],"requestId":"SYNTHETIC-SCOPED-"+str(len(calls))}
            return {"status":200,"body":json.dumps(body).encode(),"url":ENDPOINT+"?"+urlencode(raw)}
        self.coordinator.quote_adapter=adapter(grant_a,first_profile)
        with patch("solana_alpha_lab.factory.trading_adapters.http_quote",side_effect=fake_http):
            self.coordinator.tick()
            first_position=first_runner.readback()["positions"][0]
            self.assertEqual(first_position["state"],"OPEN")
            self.prepare(operating=True,suffix="-B",negative=True,exit_point="E3600")
            start=datetime(2026,10,5,12,16,6,tzinfo=UTC)
            feed=closure_fixture.EpisodeScenario(self.data/"successor-source",start=start,stops=start+timedelta(hours=3))
            blocked,new=closure_fixture.synth_mint("DeniedB"),closure_fixture.synth_mint("NewB")
            obj=closure_fixture.token_object(blocked,price=.000003,liquidity=10000,holders=66)
            closure_fixture.nominate(feed.market,start,{"toptraded":[obj],"toptrending":[obj]})
            feed.market.series[blocked]=lambda now:closure_fixture.token_object(blocked,price=.000003,liquidity=10000,
                holders=60 if now>=datetime(2026,10,5,12,50,tzinfo=UTC) else 66)
            feed.tick(start)
            feed.tick(datetime(2026,10,5,12,25,tzinfo=UTC))
            self.profile={**copy.deepcopy(first_profile),"source":{"root":str(feed.data_root),"file":"observation_schedule_state.sqlite",
                "schedule_sha256":feed.schedule["schedule_sha256"],"activation_id":feed.activation_id}}
            self.profile["quote"].update(timeout_seconds=2,max_response_bytes=4096)
            self.source,self.mint=feed,blocked
            self.now=datetime(2026,10,5,12,41,tzinfo=UTC)
            self.quote_inputs(at="2026-10-05T12:41:00Z")
            self.coordinator=TradingCoordinator(self.runner,mode="SHADOW",clock=lambda:self.now)
            switched=self.coordinator.activate(epoch_id=self.epoch,at="2026-10-05T12:41:00Z",profile=self.profile,
                switch_key="SCOPED-GRANTS-B",expected_current_epoch=first_epoch)
            self.assertEqual(switched["generation"],2)
            grant_b=self.scoped_grant(self.epoch,self.runner.strategy["spec_sha256"],calls_max=1)
            invalid_b={**grant_b,"strategy_sha256":"b"*64}
            invalid_b["grant_sha256"]=sha256_of({k:v for k,v in invalid_b.items() if k!="grant_sha256"})
            cold_runner=TradingContinuityRunner(self.root,data_root=self.data)
            cold=TradingCoordinator(cold_runner,mode="SHADOW",clock=lambda:self.now,
                quote_adapters=[adapter(grant_a,first_profile),adapter(invalid_b,self.profile)])
            first_source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
            self.now=datetime(2026,10,5,13,10,tzinfo=UTC)
            (first_source.data_root/"funding.json").write_text(json.dumps({"mint":first_profile["quote"]["funding_mint"],
                "decimals":9,"unit_price_usd":"100","observed_at":"2026-10-05T13:10:00Z","available_at":"2026-10-05T13:10:00Z"}),encoding="utf-8")
            cold.tick()
            self.assertEqual(cold_runner.readback()["positions"][0]["state"],"RECONCILED")
            later=datetime(2026,10,5,13,16,6,tzinfo=UTC)
            row=closure_fixture.token_object(new,price=.000003,liquidity=10000,holders=66)
            closure_fixture.nominate(feed.market,later,{"toptraded":[row],"toptrending":[row]})
            feed.market.series[new]=lambda now:closure_fixture.token_object(new,price=.000003,liquidity=10000,
                holders=60 if now>=datetime(2026,10,5,13,50,tzinfo=UTC) else 66)
            for tick in (later,datetime(2026,10,5,13,25,tzinfo=UTC),datetime(2026,10,5,13,50,tzinfo=UTC)):
                feed.tick(tick)
            self.now=datetime(2026,10,5,13,55,tzinfo=UTC)
            self.mint=new
            self.quote_inputs(at="2026-10-05T13:55:00Z")
            blocked_tick = cold.tick()
            self.assertEqual(blocked_tick["status"], "TICK_COMPLETE")
            self.assertFalse(blocked_tick["entries_enabled"])
            self.assertIn("QUOTE_EXTERNAL_AUTHORITY_REQUIRED", {row["reason"] for row in cold.status()["entry_blockers"]})
            self.assertEqual(len(cold_runner.readback()["modeled_attempts"]),2)
            self.assertEqual(len(self.claims(cold_runner)),2)
            self.assertEqual(len(calls),2)
            cold=TradingCoordinator(cold_runner,mode="SHADOW",clock=lambda:self.now,
                quote_adapters=[adapter(grant_a,first_profile),adapter(grant_b,self.profile)])
            cold.tick()
            view=cold_runner.readback()
            self.assertEqual({(p["activation_epoch_id"],p["state"]) for p in view["positions"]},
                {(first_epoch,"RECONCILED"),(self.epoch,"OPEN")})
            claims=self.claims(cold_runner)
            self.assertEqual([sum(c["payload"]["grant_sha256"]==g["grant_sha256"] for c in claims) for g in (grant_a,grant_b)],[2,1])
            self.assertEqual(len(calls),3)
            self.assertEqual([(c["timeout_seconds"],c["max_response_bytes"]) for c in calls],[(1,8192),(1,8192),(2,4096)])
            restart=TradingCoordinator(TradingContinuityRunner(self.root,data_root=self.data),mode="SHADOW",clock=lambda:self.now,
                quote_adapters=[adapter(grant_a,first_profile),adapter(grant_b,self.profile)])
            restart.tick()
            self.assertEqual(self.claims(cold_runner),claims)
            self.assertEqual(len(calls),3)
            with closing(PaperPlaneStore(cold_runner.store_path,readonly=True)) as store:
                with self.assertRaisesRegex(PaperPlaneError,"QUOTE_CALL_CAP_EXHAUSTED"):
                    restart._quote_quota(store,restart.quote_adapters[("SHADOW",self.epoch)])
            self.metrics={"claims_A":2,"claims_B":1,"fake_http_calls":3,"cold_repeat_calls":0,
                "origin_epochs":[first_epoch,self.epoch],"profile_bounds_A":[1,8192],"profile_bounds_B":[2,4096],
                "invalid_B":"DENY_WITH_NO_ATTEMPT_OR_CLAIM","healthy_A_exit_with_invalid_B":"RECONCILED"}

    def test_partial_projection_damage_blocks_ordinary_quote_until_truthful_restoration(self):
        metrics = []
        for field, bad in (("remaining_qty_dec", "9000000"), ("remaining_cost_basis_usd_dec", "99"),
                           ("realized_net_pnl_usd_dec", "99")):
            with self.subTest(field=field):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    ledger, original = case.partial_shadow()
                    before = case.runner.readback()
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        with store.immediate_write():
                            store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (bad, original["position_id"]))
                    case.coordinator.run(ticks=2)
                    view = case.coordinator.status()
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
                    self.assertEqual(view["inventory"]["position_count"], 1)
                    self.assertIsNone(view["inventory"]["outstanding_cost_basis_usd"])
                    self.assertEqual(len(case.ledger_receipts(ledger)), 2)
                    self.assertEqual(case.runner.readback()["modeled_attempts"], before["modeled_attempts"])
                    self.assertEqual(case.runner.readback()["modeled_results"], before["modeled_results"])
                    self.assertIn("EXIT_INVENTORY_WITNESS_CONFLICT", {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        self.assertEqual(store.get_position(original["position_id"])[field], bad)
                        with store.immediate_write():
                            store._conn.execute("UPDATE positions SET " + field + "=? WHERE position_id=?", (original[field], original["position_id"]))
                    case.coordinator.tick()
                    next_partial = case.runner.readback()["positions"][0]
                    self.assertEqual(Decimal(next_partial["remaining_qty_dec"]), Decimal("2000000"))
                    self.assertEqual(Decimal(next_partial["remaining_cost_basis_usd_dec"]), Decimal("6"))
                    self.assertEqual(Decimal(next_partial["realized_net_pnl_usd_dec"]), Decimal("1.20"))
                    self.assertEqual(Decimal(case.ledger_receipts(ledger)[-1]["attempt"]["remaining_quantity"]), Decimal("6000000"))
                    case.coordinator.tick()
                    final = case.runner.readback()["positions"][0]
                    self.assertEqual(final["state"], "RECONCILED")
                    self.assertEqual(Decimal(final["remaining_qty_dec"]), 0)
                    self.assertEqual(Decimal(final["remaining_cost_basis_usd_dec"]), 0)
                    self.assertEqual(Decimal(final["remaining_entry_fee_usd_dec"]), 0)
                    self.assertEqual(Decimal(final["realized_net_pnl_usd_dec"]), Decimal("1.20"))
                    self.assertEqual(case.coordinator.status()["status"], "READY")
                    self.assertEqual(len(case.ledger_receipts(ledger)), 4)
                    metrics.append({"damaged": field, "denied_extra_quotes": 0, "restored_second_partial_quantity": "2000000",
                        "restored_second_partial_cost_usd": "6", "terminal_net_usd": "1.20"})
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def test_native_projection_race_between_preflight_and_claim_denies_before_attempt(self):
        ledger, original = self.partial_shadow()
        before = self.runner.readback()
        native_inputs = self.coordinator._inputs
        reached = []

        def corrupt_after_preflight(*args):
            request = native_inputs(*args)
            if args[-2] == "EXIT":
                reached.append(request["remaining_quantity"])
                with closing(PaperPlaneStore(self.runner.store_path)) as writer:
                    with writer.immediate_write():
                        writer._conn.execute("UPDATE positions SET remaining_qty_dec='9000000' WHERE position_id=?", (original["position_id"],))
            return request

        with patch.object(self.coordinator, "_inputs", side_effect=corrupt_after_preflight):
            self.coordinator.tick()
        self.assertEqual([Decimal(value) for value in reached], [Decimal("6000000")])
        self.assertEqual(self.runner.readback()["modeled_attempts"], before["modeled_attempts"])
        self.assertEqual(self.runner.readback()["modeled_results"], before["modeled_results"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            with store.immediate_write():
                store._conn.execute("UPDATE positions SET remaining_qty_dec=? WHERE position_id=?",
                    (original["remaining_qty_dec"], original["position_id"]))
            stale_request = native_inputs(self.runner.for_epoch(original["activation_epoch_id"]), store, original,
                self.profile, "EXIT", "2026-10-05T13:10:00Z")
        # A genuine ordinary result now consumes another 4M. The older request
        # is internally intact, but its 6M reservation cannot send against 2M.
        self.coordinator.tick()
        self.assertEqual(Decimal(self.runner.readback()["positions"][0]["remaining_qty_dec"]), Decimal("2000000"))
        original_attempts = self.runner.readback()["modeled_attempts"]
        with patch.object(self.coordinator, "_inputs", return_value=stale_request):
            self.coordinator.tick()
        self.assertEqual(self.runner.readback()["modeled_attempts"], original_attempts)
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.coordinator.tick()
        self.assertEqual(len(self.ledger_receipts(ledger)), 4)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "RECONCILED")
        self.metrics = {"preflight_proved_quantity": "6000000", "native_writer_mutation": "9000000",
            "new_committed_attempts_while_corrupt": 0, "new_quote_effects_while_corrupt": 0, "atomic_claim_guard": "DENY",
            "genuine_result_reduces_quantity_to": "2000000", "stale_larger_request_extra_quotes": 0}

    def test_native_projection_race_after_claim_retains_original_capture_without_resend(self):
        ledger, original = self.partial_shadow()
        before = self.runner.readback()
        adapter = self.coordinator.quote_adapter
        native_dispatch = adapter.dispatch
        captured = []

        def corrupt_after_effect(*args, **kwargs):
            result, proof = native_dispatch(*args, **kwargs)
            captured.append(result)
            with closing(PaperPlaneStore(self.runner.store_path)) as writer:
                with writer.immediate_write():
                    writer._conn.execute("UPDATE positions SET entered_notional_usd_dec='31' WHERE position_id=?", (original["position_id"],))
            return result, proof

        with patch.object(adapter, "dispatch", side_effect=corrupt_after_effect):
            self.coordinator.tick()
        damaged = self.runner.readback()
        self.assertEqual(damaged["modeled_results"], before["modeled_results"])
        self.assertEqual(len(damaged["modeled_attempts"]), len(before["modeled_attempts"]) + 1)
        pending = damaged["modeled_attempts"][-1]["payload"]
        self.assertEqual(Decimal(pending["remaining_quantity"]), Decimal("6000000"))
        self.assertEqual(damaged["positions"][0]["state"], "EXITING")
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.coordinator.run(ticks=2)
        self.assertEqual(self.runner.readback()["modeled_results"], before["modeled_results"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.assertEqual(self.coordinator.status()["pending_attempts"], 1)
        self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            retained = store.get_execution_event("CAPTURE-" + pending["attempt_id"])
            self.assertEqual(retained["payload"]["result"], captured[0])
            with store.immediate_write():
                store._conn.execute("UPDATE positions SET entered_notional_usd_dec=? WHERE position_id=?",
                    (original["entered_notional_usd_dec"], original["position_id"]))
        self.coordinator.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 4)
        self.assertEqual(len({row["attempt"]["attempt_id"] for row in receipts}), 4)
        self.assertEqual(sum(row["attempt"]["attempt_id"] == pending["attempt_id"] for row in receipts), 1)
        restored = self.runner.readback()
        self.assertIn(captured[0], [event["payload"]["result"] for event in restored["modeled_results"]])
        self.assertEqual(restored["positions"][0]["state"], "RECONCILED")
        self.assertEqual(Decimal(restored["positions"][0]["realized_net_pnl_usd_dec"]), Decimal("1.20"))
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.metrics = {"original_claim_quantity": "6000000", "corrupt_original_entry_cost_usd": "31",
            "unaccepted_capture_retained": True, "pending_attempts_while_corrupt": 1,
            "repeat_original_quote_effects": 0, "truthful_restoration_terminal_net_usd": "1.20"}

    def test_partial_original_result_damage_blocks_quote_and_healthy_neighbor_continues(self):
        native_activate = TradingCoordinator.activate

        def two_positions(coordinator, **kwargs):
            kwargs["profile"]["envelope"].update(max_outstanding_positions=2, max_outstanding_cost_basis_usd="60")
            return native_activate(coordinator, **kwargs)

        with patch.object(TradingCoordinator, "activate", new=two_positions):
            self.start_operating(mode="SHADOW", exit_cap="4000000000000")
        first_epoch = self.epoch
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "10000000000000"},
            {"outAmount": "120000000"}, {"outAmount": "120000000"}, {"outAmount": "132000000"}, {"outAmount": "60000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        second_epoch = first_epoch + "-OTHER"
        self.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:40:00Z", profile=self.profile,
            switch_key="SECOND-PARTIAL-CANDIDATE", expected_current_epoch=first_epoch)
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.tick()
        positions = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
        self.assertTrue(all(Decimal(row["remaining_qty_dec"]) == Decimal("6000000") for row in positions.values()))
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            results = store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED", position_ids=[positions[first_epoch]["position_id"]])
            original = results[-1]
            damaged = copy.deepcopy(original["payload"])
            damaged["result"]["quantity_sold"] = "1"
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(damaged), original["event_id"]))
        self.coordinator.tick()
        self.coordinator.tick()
        after = {row["activation_epoch_id"]: row for row in self.runner.readback()["positions"]}
        self.assertEqual(Decimal(after[first_epoch]["remaining_qty_dec"]), Decimal("6000000"))
        self.assertEqual(after[second_epoch]["state"], "RECONCILED")
        self.assertEqual(Decimal(after[second_epoch]["realized_net_pnl_usd_dec"]), Decimal("1.20"))
        view = self.coordinator.status()
        self.assertEqual(view["inventory"]["position_count"], 1)
        self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
        self.assertEqual(len(self.ledger_receipts(ledger)), 6)
        bad_quotes = [row for row in self.ledger_receipts(ledger) if row["attempt"]["position_id"] == positions[first_epoch]["position_id"]]
        self.assertEqual(len(bad_quotes), 2)
        self.metrics = {"corrupt_original_result_extra_quotes": 0, "healthy_other_exit": "RECONCILED",
            "healthy_terminal_net_usd": "1.20", "unknown_position_count": 1}

    def test_transient_exit_funding_recovers_without_stale_active_incident(self):
        metrics = []
        for damage in ("MISSING", "MALFORMED", "STALE"):
            with self.subTest(funding=damage):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    case.start_operating(mode="SHADOW")
                    ledger, plan = case.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
                    case.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
                    case.coordinator.run(ticks=1)
                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    funding = case.source.data_root / "funding.json"
                    if damage == "MISSING":
                        funding.unlink()
                    elif damage == "MALFORMED":
                        funding.write_text("{", encoding="utf-8")
                    case.coordinator.tick()
                    failed = case.coordinator.status()
                    incident = next(row for row in failed["incidents"] if row["active"] and row["incident_key"].startswith("EXIT-INPUT-"))
                    self.assertEqual(incident["reason"], "EXECUTION_FUNDING_INPUT_UNAVAILABLE" if damage == "MISSING" else "EXECUTION_FUNDING_INPUT_INVALID")
                    self.assertEqual(failed["inventory"]["inventory_status"], "KNOWN")
                    self.assertTrue(failed["integrity_verified"])
                    self.assertFalse(failed["exit_reconciliation_healthy"])
                    self.assertEqual(len(case.ledger_receipts(ledger)), 1)
                    case.quote_inputs(at="2026-10-05T13:10:00Z")
                    case.coordinator.run(ticks=3)
                    cold = TradingCoordinator(TradingContinuityRunner(case.root, data_root=case.data),
                        mode="SHADOW", clock=lambda: case.now)
                    after = cold.status()
                    self.assertEqual(after["status"], "READY")
                    self.assertTrue(after["integrity_verified"])
                    self.assertTrue(after["exit_reconciliation_healthy"])
                    self.assertEqual(after["inventory"]["position_count"], 0)
                    self.assertEqual(after["pending_attempts"], 0)
                    self.assertEqual(case.runner.readback()["positions"][0]["state"], "RECONCILED")
                    retained = next(row for row in after["incidents"] if row["incident_key"] == incident["incident_key"])
                    self.assertEqual(retained["reason"], incident["reason"])
                    self.assertEqual(retained["first_at"], incident["first_at"])
                    self.assertEqual(retained["active"], 0)
                    self.assertEqual(len(case.ledger_receipts(ledger)), 2)
                    metrics.append({"funding": damage, "after": after["status"], "effects": 2,
                        "active_exit_input_incidents": 0, "audit_incident_retained": True})
                finally:
                    case.tearDown()
        self.metrics = {"cases": metrics}

    def test_corrupt_exit_request_stays_unknown_until_exact_owner_witness_restored(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        (self.source.data_root / "funding.json").unlink()
        self.coordinator.tick()
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            original = store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND")[0]
            damaged = {**original["payload"], "asset_metadata_sha256": "0" * 64}
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                    (json.dumps(damaged), original["event_id"]))
        self.coordinator.tick()
        self.coordinator.tick()
        failed = self.coordinator.status()
        self.assertEqual(failed["status"], "ACTION_REQUIRED")
        self.assertEqual(failed["inventory"]["inventory_status"], "UNKNOWN")
        self.assertIsNone(failed["inventory"]["outstanding_cost_basis_usd"])
        self.assertEqual(Decimal(failed["inventory"]["known_cost_basis_floor_usd"]), Decimal("30"))
        self.assertFalse(failed["integrity_verified"])
        self.assertFalse(failed["exit_reconciliation_healthy"])
        self.assertIn("EXECUTION_ASSET_METADATA_INTEGRITY_CONFLICT", {row["reason"] for row in failed["incidents"] if row["active"]})
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                    (json.dumps(original["payload"]), original["event_id"]))
        self.coordinator.run(ticks=3)
        self.assertEqual(self.coordinator.status()["status"], "READY")
        self.assertTrue(all(not row["active"] for row in self.coordinator.status()["incidents"]))
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.metrics = {"damaged_witness": "UNKNOWN", "known_floor_usd": "30",
            "corrupt_witness_extra_effects": 0, "exact_restored_witness": "READY", "audit_retained": True}

    def test_complete_cut_restores_tighter_envelope_and_disabled_runtime_policy(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        for control in ("ENVELOPE", "RUNTIME_POLICY"):
            with self.subTest(control=control):
                case = OperationalRecoveryTests()
                case.setUp()
                try:
                    case.start_operating(mode="SHADOW")
                    ledger = case.empty_ledger()
                    case.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, [{"outAmount": "10000000000000"}])
                    backup = case.data / "backups/pre-config-revision.sqlite"
                    case.coordinator.backup(destination_relative="backups/pre-config-revision.sqlite")
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if control == "ENVELOPE":
                            current = policy_owner.read_operating_envelope(store, "SHADOW")
                            policy_owner.configure_operating_envelope(store, mode="SHADOW",
                                candidate_raw={**case.profile["envelope"], "max_outstanding_cost_basis_usd": "10"},
                                expected_current_sha256=current["envelope_sha256"], idempotency_key="TIGHTER-10",
                                as_of="2026-10-05T12:40:00Z")
                        else:
                            with patch.object(policy_owner, "_now", return_value="2026-10-05T12:40:00Z"):
                                policy_owner.apply_policy(closure_fixture.ROOT, store, mode="SHADOW",
                                    candidate_raw={"new_entries_enabled": False}, expected_current_sha256="0" * 64,
                                    idempotency_key="DISABLE-AFTER-BACKUP",
                                    owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                                    reason="SYNTHETIC_RECOVERY_POLICY")
                    case.coordinator.tick()
                    self.assertEqual(case.runner.readback()["modeled_attempts"], [])
                    cut = case.production_cut(backup)
                    self.assertEqual(cut["effects"], [])
                    self.assertEqual(cut["pending_attempts"], [])
                    runner, coordinator = case.restored(backup, adapter=RecordingQuoteAdapter(ledger, [{"outAmount": "10000000000000"}]))
                    coordinator.reconcile_cut(cut)
                    self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
                    case.acknowledge(coordinator, cut)
                    with closing(PaperPlaneStore(runner.store_path)) as store:
                        self.assertEqual(policy_owner.operating_configuration_snapshot(store, mode="SHADOW", as_of=cut["as_of"]), cut["operating_configuration"])
                    bot = coordinator.status()["instances"][0]["bot_instance_id"]
                    runner.command({"command_type": "RESUME_NEW_ENTRIES", "idempotency_key": "RESTORED-RESUME", "bot_instance_id": bot})
                    coordinator.run(ticks=2)
                    self.assertEqual(runner.readback()["modeled_attempts"], [])
                    self.assertEqual(case.ledger_receipts(ledger), [])
                    if control == "ENVELOPE":
                        self.assertEqual(coordinator.status()["envelope"]["revision"], 2)
                        self.assertEqual(coordinator.status()["envelope"]["envelope"]["max_outstanding_cost_basis_usd"], "10")
                    else:
                        with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
                            current = policy_owner.resolve_current_policy(store, "SHADOW")
                        self.assertEqual(current["revision"], 1)
                        self.assertFalse(current["policy"]["new_entries_enabled"])
                finally:
                    case.tearDown()
        self.metrics = {"controls": ["ENVELOPE_REVISION_2_10_USD", "RUNTIME_POLICY_ENTRIES_DISABLED"],
            "original_attempts": 0, "restored_attempts": 0, "external_effects": 0, "idempotent_reconcile": True}

    def test_recovered_funding_with_unknown_exit_keeps_attempt_and_inventory_fence(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"status": 503}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        (self.source.data_root / "funding.json").unlink()
        self.coordinator.tick()
        self.quote_inputs(at="2026-10-05T13:10:00Z")
        self.coordinator.run(ticks=3)
        after = self.coordinator.status()
        self.assertEqual(after["status"], "ACTION_REQUIRED")
        self.assertEqual(after["inventory"]["inventory_status"], "UNKNOWN")
        self.assertEqual(after["pending_attempts"], 1)
        self.assertFalse(after["exit_reconciliation_healthy"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 2)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "UNRESOLVED")
        self.assertFalse(any(row["active"] for row in after["incidents"] if row["incident_key"].startswith("EXIT-INPUT-")))
        self.assertIn("ATTEMPT_RECONCILIATION_REQUIRED", {row["reason"] for row in after["incidents"] if row["active"]})
        self.metrics = {"input_cause_recovered": True, "exit_outcome": "UNKNOWN", "pending_attempts": 1,
            "repeated_quote_effects": 0, "inventory_status": "UNKNOWN"}

    def test_configuration_chain_damage_or_omission_cannot_acknowledge_restore(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-config-negative.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-config-negative.sqlite")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            current = policy_owner.read_operating_envelope(store, "SHADOW")
            policy_owner.configure_operating_envelope(store, mode="SHADOW",
                candidate_raw={**self.profile["envelope"], "max_outstanding_cost_basis_usd": "10"},
                expected_current_sha256=current["envelope_sha256"], idempotency_key="TIGHTER-NEGATIVE",
                as_of="2026-10-05T12:40:00Z")
            with patch.object(policy_owner, "_now", return_value="2026-10-05T12:40:00Z"):
                policy_owner.apply_policy(closure_fixture.ROOT, store, mode="SHADOW",
                    candidate_raw={"new_entries_enabled": False}, expected_current_sha256="0" * 64,
                    idempotency_key="DISABLE-NEGATIVE", owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                    reason="SYNTHETIC_RECOVERY_POLICY")
        cut = self.production_cut(backup)
        outcomes = []
        for damage in ("MISSING", "TRUNCATED_ENVELOPE", "TRUNCATED_POLICY", "HASH", "FOREIGN_MODE", "FUTURE_CLOCK"):
            with self.subTest(damage=damage):
                bad = copy.deepcopy(cut)
                config = bad["operating_configuration"]
                if damage == "MISSING":
                    del bad["operating_configuration"]
                elif damage == "TRUNCATED_ENVELOPE":
                    config["envelope_events"].pop()
                elif damage == "TRUNCATED_POLICY":
                    config["policy_revisions"].clear()
                elif damage == "HASH":
                    config["envelope_events"][-1]["payload"]["envelope_sha256"] = "0" * 64
                elif damage == "FOREIGN_MODE":
                    config["mode"] = "PAPER"
                else:
                    config["policy_revisions"][-1]["created_at"] = "2026-10-05T12:41:00Z"
                bad["cut_sha256"] = sha256_of({key: value for key, value in bad.items() if key != "cut_sha256"})
                runner, coordinator = self.restored(backup, suffix="negative-" + damage.lower())
                expected = "RESTORE_OPERATING_CONFIGURATION_REQUIRED" if damage == "MISSING" else "RESTORE_OPERATING_CONFIGURATION_INVALID"
                with self.assertRaisesRegex(PaperPlaneError, "^" + expected + "$"):
                    coordinator.reconcile_cut(bad)
                with self.assertRaisesRegex(PaperPlaneError, "^" + expected + "$"):
                    coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(coordinator.status()["inventory"]), as_of=bad["as_of"], cut=bad)
                bot = coordinator.status()["instances"][0]["bot_instance_id"]
                runner.command({"command_type": "RESUME_NEW_ENTRIES", "idempotency_key": "UNSAFE-RESUME", "bot_instance_id": bot})
                coordinator.tick()
                self.assertTrue(coordinator.status()["restore_guard"])
                self.assertEqual(runner.readback()["positions"], [])
                self.assertEqual(runner.readback()["modeled_attempts"], [])
                outcomes.append({"damage": damage, "reason": expected, "attempts": 0, "guard": True})
        self.metrics = {"cases": outcomes}

    def test_configuration_restore_preserves_later_local_authority_and_detects_damage(self):
        from solana_alpha_lab.factory import trading_runtime_policy as policy_owner
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-config-extension.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-config-extension.sqlite")

        def configure(runner, amount, key):
            with closing(PaperPlaneStore(runner.store_path)) as store:
                current = policy_owner.read_operating_envelope(store, "SHADOW")
                return policy_owner.configure_operating_envelope(store, mode="SHADOW",
                    candidate_raw={**self.profile["envelope"], "max_outstanding_cost_basis_usd": amount},
                    expected_current_sha256=current["envelope_sha256"], idempotency_key=key,
                    as_of="2026-10-05T12:40:00Z")

        configure(self.runner, "10", "CUT-10")
        cut = self.production_cut(backup)
        runner, coordinator = self.restored(backup, suffix="conflicting-local")
        configure(runner, "20", "LOCAL-20")
        with self.assertRaisesRegex(PaperPlaneError, "^RESTORE_OPERATING_CONFIGURATION_CONFLICT$"):
            coordinator.reconcile_cut(cut)
        self.assertTrue(coordinator.status()["restore_guard"])
        self.assertEqual(coordinator.status()["envelope"]["envelope"]["max_outstanding_cost_basis_usd"], "20")
        runner, coordinator = self.restored(backup, suffix="later-local")
        coordinator.reconcile_cut(cut)
        extended = configure(runner, "5", "LATER-5")
        self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
        self.acknowledge(coordinator, cut)
        self.assertEqual(coordinator.status()["envelope"]["envelope_sha256"], extended["envelope_sha256"])
        self.assertEqual(coordinator.status()["envelope"]["revision"], 3)
        runner, coordinator = self.restored(backup, suffix="ack-damage")
        coordinator.reconcile_cut(cut)
        with closing(PaperPlaneStore(runner.store_path)) as store:
            original = store.get_execution_event("OPERATING-ENVELOPE-SHADOW-2")
            with store.immediate_write():
                store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", (original["event_id"],))
        with self.assertRaisesRegex(PaperPlaneError, "^RESTORE_OPERATING_CONFIGURATION_INVALID$"):
            self.acknowledge(coordinator, cut)
        self.assertTrue(coordinator.status()["restore_guard"])
        self.assertEqual(runner.readback()["modeled_attempts"], [])
        self.metrics = {"conflicting_local_revision": "DENY", "later_local_revision": 3,
            "later_cap_preserved_usd": "5", "post_import_damage_ack": "DENY", "attempts": 0}

    def test_sqlite_writer_wait_cannot_authorize_entry_after_ttl(self):
        self.start_operating(clock_at=datetime(2026, 10, 5, 12, 40, 29, 750000, tzinfo=UTC))
        base = self.now
        started = []
        ready = threading.Event()
        errors = []
        threads = []
        original_inputs = self.coordinator._inputs

        def writer():
            try:
                with closing(sqlite3.connect(self.runner.store_path, timeout=5)) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    ready.set()
                    time.sleep(1.4)
                    connection.commit()
            except BaseException as error:
                errors.append(error)
                ready.set()

        def contend(*args):
            request = original_inputs(*args)
            self.assertEqual(args[-2], "ENTRY")
            started.append(time.monotonic())
            thread = threading.Thread(target=writer)
            threads.append(thread)
            thread.start()
            self.assertTrue(ready.wait(timeout=5), "NATIVE_SQLITE_WRITER_NOT_READY")
            return request

        self.coordinator.clock = lambda: base + timedelta(seconds=time.monotonic() - started[0]) if started else base
        with patch.object(self.coordinator, "_inputs", side_effect=contend):
            try:
                self.coordinator.tick()
            finally:
                for thread in threads:
                    thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(started), 1)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertGreaterEqual((self.coordinator.clock() - base).total_seconds(), 1.3)
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempts"], [])
        self.assertEqual(view["modeled_results"], [])
        self.assertEqual({position["state"] for position in view["positions"]}, {"CANCELLED"})
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"), [])
        self.metrics = {"sqlite_writer_hold_seconds": 1.4, "entry_ttl_seconds": 30, "expired_attempts": 0}

    def test_cross_snapshot_original_switch_cut_ack_resume_admits_successor_and_services_old_exit(self):
        self.start_operating(mode="SHADOW", envelope_limits={"max_outstanding_positions": 2, "max_outstanding_cost_basis_usd": "60"})
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        original = self.runner.readback()["positions"][0]
        old_epoch, old_source, old_profile = self.epoch, self.source, self.profile
        backup = self.data / "backups/switch-lineage.sqlite"
        self.coordinator.backup(destination_relative="backups/switch-lineage.sqlite")
        self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
        start = datetime(2026, 10, 5, 12, 16, 6, tzinfo=UTC)
        feed = closure_fixture.EpisodeScenario(self.data / "recovery-successor-source", start=start, stops=start + timedelta(hours=3))
        mint = closure_fixture.synth_mint("RecoveryB")
        obj = closure_fixture.token_object(mint, price=.000003, liquidity=10000, holders=66)
        closure_fixture.nominate(feed.market, start, {"toptraded": [obj], "toptrending": [obj]})
        feed.market.series[mint] = lambda now: closure_fixture.token_object(mint, price=.000003, liquidity=10000,
            holders=60 if now >= datetime(2026, 10, 5, 12, 50, tzinfo=UTC) else 66)
        for at in (start, datetime(2026, 10, 5, 12, 25, tzinfo=UTC), datetime(2026, 10, 5, 12, 50, tzinfo=UTC)):
            feed.tick(at)
        self.source, self.mint = feed, mint
        self.now = datetime(2026, 10, 5, 12, 55, tzinfo=UTC)
        self.profile = {**old_profile, "source": {"root": str(feed.data_root),
            "file": "observation_schedule_state.sqlite", "schedule_sha256": feed.schedule["schedule_sha256"], "activation_id": feed.activation_id}}
        self.quote_inputs(at="2026-10-05T12:55:00Z")
        self.coordinator = TradingCoordinator(self.runner, mode="SHADOW", clock=lambda: self.now)
        self.coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:55:00Z", profile=self.profile,
            switch_key="EXACT-LINEAGE-B", expected_current_epoch=old_epoch)
        cut = self.production_cut(backup, effects=self.ledger_receipts(ledger))
        self.assertEqual(len(cut["operating_switches"]), 2)
        runner, coordinator = self.restored(backup, suffix="exact-lineage-restored",
            adapter=RecordingQuoteAdapter(ledger, json.loads(plan.read_text())))
        denied = []
        for alteration in ("OLD_CUT_MISSING", "EMPTY", "CAS", "INITIAL_CAS", "STRATEGY", "GENERATION", "CHAIN_COUNT", "CONFLICT"):
            bad = copy.deepcopy(cut)
            if alteration == "OLD_CUT_MISSING":
                del bad["operating_switches"]
            elif alteration == "EMPTY":
                bad["operating_switches"] = []
            elif alteration == "CAS":
                bad["operating_switches"][-1]["payload"]["expected_current_epoch"] = "ACTIVATION-EPOCH-WRONG"
            elif alteration == "INITIAL_CAS":
                bad["operating_switches"][0]["payload"]["expected_current_epoch"] = "ACTIVATION-EPOCH-NONEXISTENT"
            elif alteration == "STRATEGY":
                bad["operating_switches"][-1]["payload"]["strategy_sha256"] = "f" * 64
            elif alteration == "GENERATION":
                bad["current_entry"]["generation"] = 3
            elif alteration == "CHAIN_COUNT":
                bad["operating_switches"] = bad["operating_switches"][-1:]
            else:
                bad["operating_switches"][0]["event_id"] = "SWITCH-" + "f" * 64
            bad["cut_sha256"] = sha256_of({key: value for key, value in bad.items() if key != "cut_sha256"})
            with closing(PaperPlaneStore(runner.store_path, readonly=True)) as observer:
                before = list(observer._conn.iterdump())
            with self.assertRaisesRegex(PaperPlaneError, "^RECOVERY_(OPERATING_BINDING_INVALID|BINDING_CONTENT_CONFLICT)$"):
                coordinator.reconcile_cut(bad)
            with closing(PaperPlaneStore(runner.store_path, readonly=True)) as observer:
                self.assertEqual(list(observer._conn.iterdump()), before)
            self.assertTrue(coordinator.status()["restore_guard"])
            self.assertEqual(len(self.ledger_receipts(ledger)), 1)
            denied.append(alteration)
        coordinator.reconcile_cut(cut)
        self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
        after_cut = coordinator.status()
        self.assertEqual(after_cut["next_safe_action"], "ACKNOWLEDGE_RESTORED_INVENTORY")
        self.assertEqual(after_cut["inventory"]["inventory_status"], "KNOWN")
        # Genuine older cut is accepted only after exact native history exists.
        legacy = {key: value for key, value in cut.items() if key not in {"operating_switches", "cut_sha256"}}
        legacy["cut_sha256"] = sha256_of(legacy)
        coordinator.reconcile_cut(legacy)
        self.acknowledge(coordinator, legacy)
        self.assertTrue(all(bot["entries_paused"] for bot in coordinator.status()["instances"]))
        bot = next(bot for bot in coordinator.status()["instances"] if bot["activation_epoch_id"] == self.epoch)
        runner.command({"command_type": "RESUME_NEW_ENTRIES", "idempotency_key": "RESUME-EXACT-B", "bot_instance_id": bot["bot_instance_id"]})
        tick = coordinator.tick()
        self.metrics = {"successor_tick": tick, "admission_reasons": [row["payload"]["reason_code"] for row in runner.readback()["admission_refusals"]]}
        rows = {row["activation_epoch_id"]: row for row in runner.readback()["positions"]}
        self.assertEqual(rows[self.epoch]["state"], "OPEN")
        self.assertEqual(tick["attempts"], 1)
        self.assertTrue(tick["entries_enabled"])
        with closing(PaperPlaneStore(runner.store_path, readonly=True)) as observer:
            self.assertEqual(observer.filtered_execution_events(event_type="OPERATING_SWITCH_COMMITTED"), cut["operating_switches"])
        coordinator.reconcile_cut(cut)
        coordinator.tick()
        self.assertEqual(len(self.ledger_receipts(ledger)), 2)
        old_source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        funding_path = old_source.data_root / "funding.json"
        funding = json.loads(funding_path.read_text())
        funding.update(observed_at="2026-10-05T13:10:00Z", available_at="2026-10-05T13:10:00Z")
        funding_path.write_text(json.dumps(funding), encoding="utf-8")
        coordinator.run(ticks=2)
        final = {row["activation_epoch_id"]: row for row in runner.readback()["positions"]}
        self.assertEqual(final[old_epoch]["state"], "RECONCILED")
        self.assertEqual(final[old_epoch]["position_id"], original["position_id"])
        self.assertEqual(len(self.ledger_receipts(ledger)), 3)
        self.metrics = {"original_switch_events_retained_exact": True, "atomic_lineage_denials": denied,
            "old_cut_missing_lineage": "DENIED", "old_cut_exact_retained_history": "ACCEPTED",
            "restore_ack": "PASS_CONTROLS_PAUSED", "explicit_resume_B": "OPEN", "B_attempts": 1,
            "original_A_exit": "RECONCILED", "wire_calls": 3, "resends": 0, "cut_repeat": "IDEMPOTENT",
            "cut_as_of": cut["as_of"], "generation": cut["current_entry"]["generation"],
            "switch_rows": [{"event_id": event["event_id"], "created_at": event["created_at"],
                "payload_sha256": sha256_of(event["payload"]), "epoch_id": event["payload"]["epoch_id"],
                "expected_current_epoch": event["payload"]["expected_current_epoch"]} for event in cut["operating_switches"]]}

    def test_native_paper_v1_0_original_inventory_projection_cannot_free_headroom(self):
        from solana_alpha_lab.factory.paper_plane import assert_quantity_inventory_witness
        from solana_alpha_lab.factory.trading_runtime_policy import obligation_summary, enforce_operating_envelope
        self.start_operating(envelope_limits={"max_outstanding_positions": 2, "max_outstanding_cost_basis_usd": "40"})
        self.assertEqual(self.coordinator.tick()["attempts"], 1)
        rows = []
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            original = store.positions()[0]
            pid = original["position_id"]
            journal = store.filtered_execution_events(position_ids=[pid])
            accepted = next(event for event in journal if event["event_type"] == "MODELED_RESULT_ACCEPTED")
            self.assertNotIn("schema_version", accepted["payload"]["result"])
            self.assertIsNone(original["entry_fee_semantics"])
            self.assertEqual(Decimal(original["qty_dec"]), Decimal("10000000"))
            self.assertEqual(Decimal(obligation_summary(store, mode="PAPER")["outstanding_cost_basis_usd"]), Decimal("30"))
            self.assertEqual(enforce_operating_envelope(store, mode="PAPER", admitted_notional_usd="30")["reason_code"], "OUTSTANDING_COST_BASIS_LIMIT")
            for label, values in (("COHERENT_TUPLE", {"remaining_qty_dec": "1000000", "remaining_cost_basis_usd_dec": "3", "remaining_entry_fee_usd_dec": "0.01"}),
                                  ("COST_ONLY", {"remaining_cost_basis_usd_dec": "3"}),
                                  ("QUANTITY_ONLY", {"remaining_qty_dec": "1000000"}),
                                  ("FEE_ONLY", {"remaining_entry_fee_usd_dec": "0.01"})):
                with self.subTest(alteration=label):
                    store._conn.execute("UPDATE positions SET " + ",".join(key + "=?" for key in values) + " WHERE position_id=?", [*values.values(), pid])
                    with self.assertRaisesRegex(PaperPlaneError, "^EXIT_INVENTORY_WITNESS_CONFLICT$"):
                        assert_quantity_inventory_witness(store, store.get_position(pid), allow_pending=True)
                    inventory = obligation_summary(store, mode="PAPER")
                    self.assertEqual(inventory["inventory_status"], "UNKNOWN")
                    self.assertIsNone(inventory["outstanding_cost_basis_usd"])
                    self.assertEqual(Decimal(inventory["known_cost_basis_floor_usd"]), Decimal("30"))
                    self.assertEqual(enforce_operating_envelope(store, mode="PAPER", admitted_notional_usd="30")["reason_code"], "OUTSTANDING_OBLIGATIONS_UNKNOWN")
                    view = self.coordinator.status()
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertFalse(view["entries_enabled"])
                    self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
                    self.assertEqual(self.coordinator.tick()["attempts"], 0)
                    self.assertEqual(store.filtered_execution_events(position_ids=[pid]), journal)
                    rows.append({"alteration": label, "inventory": "UNKNOWN", "known_floor_usd": inventory["known_cost_basis_floor_usd"],
                        "new30": "OUTSTANDING_OBLIGATIONS_UNKNOWN", "original_journal_unchanged": True, "additional_attempts": 0})
                    store._conn.execute("UPDATE positions SET " + ",".join(key + "=?" for key in values) + " WHERE position_id=?", [*(original[key] for key in values), pid])
            assert_quantity_inventory_witness(store, store.get_position(pid))
            self.assertEqual(store.filtered_execution_events(position_ids=[pid]), journal)
            self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "KNOWN")
        self.metrics = {"adapter": "NATIVE_PAPER_MODEL_V1_0", "original_cost_usd": original["entered_notional_usd_dec"], "original_quantity": original["qty_dec"],
            "cap_usd": "40", "cases": rows, "legacy_remaining_tuple": "ABSENT_AND_UNCHANGED", "original_payload_sha256": sha256_of(accepted["payload"])}

    def test_native_paper_v1_0_damaged_origin_exit_isolated_from_healthy_neighbor(self):
        self.two_native_open_positions(mode="PAPER")
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            original, healthy = store.positions()
            journal = store.filtered_execution_events(position_ids=[original["position_id"]])
            store._conn.execute("UPDATE positions SET remaining_qty_dec='1000000',remaining_cost_basis_usd_dec='3',remaining_entry_fee_usd_dec='0.01' WHERE position_id=?", (original["position_id"],))
            ticks = self.coordinator.run(ticks=2)
            self.assertEqual(ticks["ticks"], 2)
            damaged = store.get_position(original["position_id"])
            completed = store.get_position(healthy["position_id"])
            self.assertEqual(damaged["state"], "EXIT_REQUIRED")
            self.assertEqual(completed["state"], "RECONCILED")
            for event in journal:
                self.assertEqual(store.get_execution_event(event["event_id"]), event)
            attempts = store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED", position_ids=[original["position_id"]])
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["payload"]["side"], "ENTRY")
            self.assertEqual(len(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND", position_ids=[original["position_id"]])), 1)
            self.assertEqual(len(store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED", position_ids=[original["position_id"]])), 1)
            self.assertEqual((damaged["remaining_qty_dec"], damaged["remaining_cost_basis_usd_dec"], damaged["remaining_entry_fee_usd_dec"]), ("1000000", "3", "0.01"))
            self.assertEqual(store._conn.execute("SELECT reason FROM ordinary_incidents WHERE incident_key=? AND active=1", (original["position_id"],)).fetchone()[0], "EXIT_INVENTORY_WITNESS_CONFLICT")
            self.assertEqual(self.coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
            self.assertFalse(self.coordinator.status()["entries_enabled"])
            self.assertEqual(len(store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED")), 3)
        self.metrics = {"adapter": "NATIVE_PAPER_MODEL_V1_0", "native_ticks": ticks["ticks"], "damaged_origin": "EXIT_REQUIRED_NO_EXIT_EFFECT",
            "retained_original_events_unchanged": True, "new_origin_exit_attempt_request_result": 0,
            "typed_reason": "EXIT_INVENTORY_WITNESS_CONFLICT", "healthy_neighbor": "RECONCILED", "total_attempts": 3, "inventory": "UNKNOWN"}

    def test_restore_without_effects_imports_successor_binding_and_generation_paused(self):
        self.start_operating(mode="SHADOW")
        predecessor_epoch, old_profile = self.epoch, self.profile
        backup = self.data / "backups/pre-switch.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-switch.sqlite")
        ledger = self.empty_ledger()
        self.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
        profile = {**old_profile, "source": {"root": str(self.source.data_root),
            "file": "observation_schedule_state.sqlite", "schedule_sha256": self.admission["schedule_sha256"],
            "activation_id": self.admission["activation_id"]}}
        self.coordinator = TradingCoordinator(self.runner, mode="SHADOW", clock=lambda: self.now)
        switched = self.coordinator.activate(epoch_id=self.epoch, at="2026-10-05T12:40:00Z",
            profile=profile, switch_key="RECOVERY-B", expected_current_epoch=predecessor_epoch)
        self.assertEqual(switched["generation"], 2)
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["effects"], [])
        self.assertEqual(cut["quote_claims"], [])
        self.assertEqual(len(cut["operating_bindings"]), 2)
        runner, coordinator = self.restored(backup)
        self.assertEqual(coordinator.status()["activation_epoch_id"], predecessor_epoch)
        coordinator.reconcile_cut(cut)
        imported = coordinator.status()
        self.assertEqual(imported["activation_epoch_id"], self.epoch)
        self.assertEqual(imported["generation"], 2)
        self.assertEqual({bot["activation_epoch_id"] for bot in imported["instances"]}, {predecessor_epoch, self.epoch})
        self.assertTrue(all(bot["entries_paused"] for bot in imported["instances"]))
        self.acknowledge(coordinator, cut)
        coordinator.tick()
        self.assertEqual(runner.readback()["positions"], [])
        self.assertTrue(all(bot["entries_paused"] for bot in coordinator.status()["instances"]))
        self.assertEqual(self.ledger_receipts(ledger), [])

    def test_post_restore_stop_survives_older_complete_cut(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-stop.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-stop.sqlite")
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["controls"][0]["status"], "RUNNING")
        runner, coordinator = self.restored(backup)
        bot_id = coordinator.status()["instances"][0]["bot_instance_id"]
        stopped = runner.command({"command_type": "STOP_BOT", "idempotency_key": "POST-RESTORE-STOP",
            "bot_instance_id": bot_id})
        self.assertEqual(stopped["bot_status"], "STOPPED")
        coordinator.reconcile_cut(cut)
        self.acknowledge(coordinator, cut)
        coordinator.reconcile_cut(cut)
        coordinator.tick()
        bot = coordinator.status()["instances"][0]
        self.assertEqual(bot["status"], "STOPPED")
        self.assertTrue(bot["entries_paused"])
        self.assertEqual(runner.readback()["positions"], [])

    def test_post_restore_drain_with_inventory_survives_older_complete_cut(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        backup = self.data / "backups/pre-drain.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-drain.sqlite")
        cut = self.recovery_cut(ledger, backup)
        self.assertEqual(cut["controls"][0]["status"], "RUNNING")
        runner, coordinator = self.restored(backup)
        bot_id = coordinator.status()["instances"][0]["bot_instance_id"]
        draining = runner.command({"command_type": "STOP_BOT", "idempotency_key": "POST-RESTORE-DRAIN",
            "bot_instance_id": bot_id})
        self.assertEqual(draining["bot_status"], "DRAINING")
        coordinator.reconcile_cut(cut)
        self.acknowledge(coordinator, cut)
        coordinator.reconcile_cut(cut)
        bot = coordinator.status()["instances"][0]
        self.assertEqual(bot["status"], "DRAINING")
        self.assertTrue(bot["entries_paused"])
        self.assertEqual(coordinator.status()["inventory"]["position_count"], 1)
        self.assertEqual(runner.readback()["positions"][0]["state"], "OPEN")
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)

    def test_complete_cut_restores_consumed_quote_grant_and_exit_cannot_resend(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-quote-claim.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-quote-claim.sqlite")
        self.assertEqual(self.claims(self.runner), [])
        grant = self.original_grant()
        self.coordinator.quote_adapter = _GrantedRecordingAdapter(ledger, grant)
        calls = []

        def fake_http(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            body = {"transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
                "inAmount": raw["amount"], "outAmount": "10000000000000", "router": "metis", "mode": "ultra",
                "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "SYNTHETIC-GRANTED-ORIGINAL"}
            return {"status": 200, "body": json.dumps(body).encode(), "url": ENDPOINT + "?" + urlencode(raw)}

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=fake_http):
            self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            original_claims = self.claims(self.runner)
            self.assertEqual(len(original_claims), 1)
            self.assertEqual(original_claims[0]["payload"]["grant_sha256"], grant["grant_sha256"])
            cut = self.recovery_cut(ledger, backup)
            self.assertEqual(cut["quote_claims"], original_claims)
            fresh_adapter = _GrantedRecordingAdapter(ledger, grant)
            self.assertEqual(fresh_adapter.calls, 0)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            self.assertEqual(self.claims(runner), [])
            coordinator.reconcile_cut(cut)
            coordinator.reconcile_cut(cut)
            self.assertEqual(self.claims(runner), original_claims)
            self.acknowledge(coordinator, cut)
            self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
            self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
            self.quote_inputs(at="2026-10-05T13:10:00Z")
            coordinator.tick()
            coordinator.tick()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.assertEqual(self.claims(runner), original_claims)
        self.assertEqual(fresh_adapter.calls, 0)
        self.assertEqual(coordinator.status()["inventory"]["position_count"], 1)
        self.assertIn("QUOTE_CALL_CAP_EXHAUSTED", {incident["reason"] for incident in coordinator.status()["incidents"]})
        self.metrics = {"original_claims": 1, "restored_claims": 1, "synthetic_http_calls": 1,
            "fresh_adapter_calls": 0, "provider_calls": 0}

    def test_native_witness_metadata_survives_source_deletion_for_due_exit(self):
        self.witness_operating()
        ledger, plan = self.wire_files([{"outAmount": "10000000000000"}, {"outAmount": "330000000"}])
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        entry_receipt = self.ledger_receipts(ledger)[0]
        request = entry_receipt["request"]
        asset = request["asset_metadata"]
        self.assertEqual(asset["mint"], self.mint)
        self.assertEqual(asset["decimals"], 6)
        self.assertEqual(request["asset_metadata_sha256"], sha256_of(asset))
        self.assertEqual(request["output_decimals"], 6)
        origin = request["recovery_closure"]["origin"]["provenance"]["origin_admission"]
        self.assertEqual(asset["witness_response_sha256"], origin["witness_response_sha256"])
        self.assertEqual(asset["witness_object_sha256"], origin["witness_object_sha256"])
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "OPEN")
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        funding_path = self.source.data_root / "funding.json"
        funding = json.loads(funding_path.read_text())
        funding.update(observed_at="2026-10-05T13:10:00Z", available_at="2026-10-05T13:10:00Z")
        funding_path.write_text(json.dumps(funding), encoding="utf-8")
        witness_path = self.source.data_root / origin["witness_raw_body_rel"]
        witness_path.unlink()
        (self.source.data_root / "assets.json").unlink()
        cold = TradingCoordinator(TradingContinuityRunner(self.root, data_root=self.data), mode="SHADOW",
            clock=lambda: self.now, quote_adapter=RecordingQuoteAdapter(ledger, json.loads(plan.read_text())))
        cold.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[1]["attempt"]["side"], "EXIT")
        self.assertEqual(receipts[1]["request"]["asset_metadata"], asset)
        self.assertEqual(receipts[1]["request"]["asset_metadata_sha256"], request["asset_metadata_sha256"])
        self.assertEqual(receipts[1]["request"]["input_decimals"], 6)
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "RECONCILED")
        self.assertEqual(cold.status()["inventory"]["position_count"], 0)
        self.assertFalse(witness_path.exists())
        self.assertFalse((self.source.data_root / "assets.json").exists())

    def test_native_witness_hash_conflict_denies_before_quote_effect(self):
        self.witness_operating()
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        reached = []

        def corrupt_witness(point):
            if point == "AFTER_DECISION_COMMIT":
                reached.append(point)
                witness = self.source.data_root / self.admission["witness_raw_body_rel"]
                witness.write_bytes(witness.read_bytes() + b" ")

        self.coordinator.fault = corrupt_witness
        tick = self.coordinator.tick()
        self.assertEqual(tick["status"], "TICK_COMPLETE")
        self.assertFalse(tick["entries_enabled"])
        self.assertEqual(reached, ["AFTER_DECISION_COMMIT"])
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempts"], [])
        self.assertEqual(view["modeled_results"], [])
        self.assertEqual(view["positions"][0]["state"], "WATCHED")
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            blocker = store._conn.execute("SELECT reason,active FROM ordinary_incidents WHERE incident_key=?",
                ("ENTRY-SHADOW-"+view["positions"][0]["position_id"],)).fetchone()
            self.assertEqual(dict(blocker), {"reason": "EXECUTION_ASSET_WITNESS_INTEGRITY_CONFLICT", "active": 1})
            self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"), [])
        self.assertEqual(self.claims(self.runner), [])
        self.assertFalse(ledger.exists())
        self.metrics={"tick_status":tick["status"],"entries_enabled":tick["entries_enabled"],
            "entry_reason":dict(blocker)["reason"],"attempts":0,"requests":0,"results":0,"quote_claims":0,"fake_http_calls":0}

    def test_authored_vendor_witness_boolean_decimals_denied_before_quote_effect(self):
        original_object = closure_fixture.continuity_fixture.token_object

        def malformed_vendor_object(*args, **kwargs):
            return {**original_object(*args, **kwargs), "decimals": True}

        with patch.object(closure_fixture.continuity_fixture, "token_object", side_effect=malformed_vendor_object):
            self.witness_operating()
        ledger, plan = self.wire_files()
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        tick = self.coordinator.tick()
        self.assertEqual(tick["status"], "TICK_COMPLETE")
        self.assertFalse(tick["entries_enabled"])
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempts"], [])
        self.assertEqual(view["modeled_results"], [])
        self.assertEqual(view["positions"][0]["state"], "WATCHED")
        with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
            blocker = store._conn.execute("SELECT reason,active FROM ordinary_incidents WHERE incident_key=?",
                ("ENTRY-SHADOW-"+view["positions"][0]["position_id"],)).fetchone()
            self.assertEqual(dict(blocker), {"reason": "EXECUTION_ASSET_IDENTITY_INVALID", "active": 1})
            self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND"), [])
        self.assertEqual(self.claims(self.runner), [])
        self.assertFalse(ledger.exists())
        self.metrics={"tick_status":tick["status"],"entries_enabled":tick["entries_enabled"],
            "entry_reason":dict(blocker)["reason"],"attempts":0,"requests":0,"results":0,"quote_claims":0,"fake_http_calls":0}

    def test_pending_quote_claim_restores_unknown_without_manufacturing_result_or_resend(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-pending-attempt.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-attempt.sqlite")
        self.assertEqual(self.claims(self.runner), [])
        grant = self.original_grant()
        self.coordinator.quote_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
            grant=grant, credential_supplier=lambda: None)
        calls = []

        def effect_without_result(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            raise RuntimeError("SYNTHETIC_LOSS_BEFORE_RESULT_CAPTURE")

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=effect_without_result):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_RESULT_CAPTURE"):
                self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            original = self.runner.readback()
            self.assertEqual(original["positions"][0]["state"], "ATTEMPTING")
            self.assertIsNone(original["positions"][0]["qty_dec"])
            self.assertEqual(original["modeled_results"], [])
            cut = self.recovery_cut(ledger, backup)
            self.assertEqual(cut["effects"], [])
            self.assertEqual(len(cut["pending_attempts"]), 1)
            self.assertEqual(cut["pending_attempts"][0]["attempt"], original["modeled_attempts"][0]["payload"])
            original_claims = self.claims(self.runner)
            self.assertEqual(cut["quote_claims"], original_claims)
            self.assertEqual(len(original_claims), 1)
            fresh_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
                grant=grant, credential_supplier=lambda: None)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            coordinator.reconcile_cut(cut)
            view = runner.readback()
            self.assertEqual(view["positions"][0]["position_id"], original["positions"][0]["position_id"])
            self.assertEqual(view["positions"][0]["state"], "ATTEMPTING")
            self.assertIsNone(view["positions"][0]["qty_dec"])
            self.assertEqual(view["modeled_attempts"][0]["payload"], original["modeled_attempts"][0]["payload"])
            with closing(PaperPlaneStore(runner.store_path, readonly=True)) as store:
                self.assertEqual(store.get_execution_event("REQUEST-" + cut["pending_attempts"][0]["attempt"]["attempt_id"])["payload"],
                    cut["pending_attempts"][0]["request"])
                self.assertEqual(store.filtered_execution_events(event_type="ADAPTER_RESULT_CAPTURED"), [])
            self.assertEqual(view["modeled_results"], [])
            self.assertEqual(self.claims(runner), original_claims)
            inventory = coordinator.status()["inventory"]
            self.assertEqual(inventory["inventory_status"], "UNKNOWN")
            self.assertEqual(Decimal(inventory["known_cost_basis_floor_usd"]), Decimal("30"))
            with self.assertRaisesRegex(PaperPlaneError, "RESTORE_RECONCILIATION_REQUIRED"):
                coordinator.acknowledge_restore(expected_inventory_sha256=sha256_of(inventory), as_of=cut["as_of"], cut=cut)
            coordinator.tick()
            coordinator.tick()
            self.assertTrue(coordinator.status()["restore_guard"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(fresh_adapter.calls, 0)
            self.assertEqual(self.ledger_receipts(ledger), [])
            self.assertEqual(self.claims(runner), original_claims)
            self.assertEqual(runner.readback()["positions"][0]["state"], "ATTEMPTING")
        self.metrics = {"original_pending_attempts": 1, "synthetic_effects_without_result": 1,
            "known_fills": 0, "restored_claims": 1, "repeated_http_calls": 0, "ack_denied": True}

    def test_later_paper_cut_preserves_original_pending_model_result_clock(self):
        self.start_operating()
        backup = self.data / "backups/pre-pending-paper.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-paper.sqlite")

        def after_attempt(point):
            if point == "AFTER_ATTEMPT_COMMIT":
                raise RuntimeError("SYNTHETIC_LOSS_BEFORE_PAPER_MODEL")

        self.coordinator.fault = after_attempt
        with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_PAPER_MODEL"):
            self.coordinator.tick()
        original = self.runner.readback()
        self.assertEqual(original["positions"][0]["state"], "ATTEMPTING")
        self.assertEqual(original["modeled_results"], [])
        self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
        cut = self.production_cut(backup)
        self.assertEqual(cut["effects"], [])
        self.assertEqual(cut["quote_claims"], [])
        self.assertEqual(len(cut["pending_attempts"]), 1)
        self.assertEqual(cut["pending_attempts"][0]["request"]["result_at"], "2026-10-05T12:40:00Z")
        runner, coordinator = self.restored(backup, mode="PAPER")
        coordinator.reconcile_cut(cut)
        before = runner.readback()
        self.assertEqual(before["positions"][0]["state"], "ATTEMPTING")
        self.assertEqual(before["modeled_results"], [])
        self.assertEqual(before["modeled_attempts"][0]["payload"], original["modeled_attempts"][0]["payload"])
        self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
        coordinator.tick()
        after = runner.readback()
        self.assertEqual(after["positions"][0]["state"], "OPEN")
        self.assertEqual(len(after["modeled_attempts"]), 1)
        self.assertEqual(len(after["modeled_results"]), 1)
        result = after["modeled_results"][0]["payload"]["result"]
        self.assertEqual(result["attempt_id"], original["modeled_attempts"][0]["payload"]["attempt_id"])
        self.assertEqual(result["observed_at"], "2026-10-05T12:40:00Z")
        self.assertEqual(result["outcome"], "LANDED_SUCCESS")
        self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "KNOWN")
        self.acknowledge(coordinator, cut)
        coordinator.tick()
        self.assertEqual(len(runner.readback()["modeled_attempts"]), 1)

    def test_later_shadow_pending_cut_accepts_original_earlier_definitive_receipt(self):
        self.start_operating(mode="SHADOW")
        ledger = self.empty_ledger()
        backup = self.data / "backups/pre-pending-shadow.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-pending-shadow.sqlite")
        grant = self.original_grant()
        self.coordinator.quote_adapter = _GrantedRecordingAdapter(ledger, grant)
        calls = []

        def fake_http(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            body = {"transaction": None, "inputMint": raw["inputMint"], "outputMint": raw["outputMint"],
                "inAmount": raw["amount"], "outAmount": "10000000000000", "router": "metis", "mode": "ultra",
                "feeBps": 20, "feeMint": raw["outputMint"], "requestId": "SYNTHETIC-OLD-DEFINITIVE-QUOTE"}
            return {"status": 200, "body": json.dumps(body).encode(), "url": ENDPOINT + "?" + urlencode(raw)}

        def after_effect(point):
            if point == "AFTER_ADAPTER_EFFECT":
                raise RuntimeError("SYNTHETIC_LOSS_BEFORE_NATIVE_CAPTURE")

        self.coordinator.fault = after_effect
        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=fake_http):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_LOSS_BEFORE_NATIVE_CAPTURE"):
                self.coordinator.tick()
            original = self.runner.readback()
            self.assertEqual(original["modeled_results"], [])
            self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
            cut = self.production_cut(backup)
            self.assertEqual(cut["effects"], [])
            self.assertEqual(len(cut["pending_attempts"]), 1)
            self.assertEqual(len(cut["quote_claims"]), 1)
            fresh_adapter = _GrantedRecordingAdapter(ledger, grant)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            self.assertEqual(runner.readback()["positions"][0]["state"], "ATTEMPTING")
            self.assertEqual(runner.readback()["modeled_results"], [])
            self.assertEqual(coordinator.status()["inventory"]["inventory_status"], "UNKNOWN")
            receipt = self.ledger_receipts(ledger)[0]
            self.assertEqual(receipt["result"]["observed_at"], "2026-10-05T12:40:00Z")
            accepted = coordinator.reconcile_restored_effect(receipt)
            self.assertFalse(accepted["send_permitted"])
            self.assertTrue(coordinator.reconcile_restored_effect(receipt)["idempotent"])
            self.assertEqual(runner.readback()["positions"][0]["state"], "OPEN")
            self.assertEqual(len(runner.readback()["modeled_attempts"]), 1)
            self.assertEqual(runner.readback()["modeled_results"][0]["payload"]["result"], receipt["result"])
            self.acknowledge(coordinator, cut)
            coordinator.tick()
            coordinator.tick()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger_receipts(ledger)), 1)
        self.assertEqual(fresh_adapter.calls, 0)

    def test_export_cut_denies_known_after_backup_result_omission_or_conflict(self):
        self.start_operating(mode="SHADOW")
        ledger, plan = self.wire_files()
        backup = self.data / "backups/pre-final-export.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-final-export.sqlite")
        self.coordinator.quote_adapter = RecordingQuoteAdapter(ledger, json.loads(plan.read_text()))
        self.coordinator.tick()
        receipts = self.ledger_receipts(ledger)
        self.assertEqual(len(receipts), 1)
        before = self.runner.readback()
        with self.assertRaisesRegex(PaperPlaneError, "RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING"):
            self.production_cut(backup)
        conflicting = json.loads(json.dumps(receipts[0]))
        conflicting["result"]["unit_price_usd"] = "0.5"
        conflicting["receipt_sha256"] = sha256_of({key: value for key, value in conflicting.items() if key != "receipt_sha256"})
        with self.assertRaisesRegex(PaperPlaneError, "RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING"):
            self.production_cut(backup, effects=[conflicting])
        valid = self.production_cut(backup, effects=receipts)
        self.assertEqual(valid["effects"], receipts)
        self.assertEqual(valid["pending_attempts"], [])
        self.assertEqual(self.runner.readback(), before)

    def test_corrupt_predecessor_binding_does_not_starve_other_due_exit(self):
        native_activate = TradingCoordinator.activate

        def two_positions(coordinator, **kwargs):
            profile = kwargs["profile"]
            profile["envelope"].update(max_outstanding_positions=2, max_outstanding_cost_basis_usd="60")
            return native_activate(coordinator, **kwargs)

        with patch.object(TradingCoordinator, "activate", new=two_positions):
            self.start_operating()
        first_epoch = self.epoch
        self.coordinator.tick()
        profile = self.profile
        second_epoch = first_epoch + "-OTHER"
        self.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:40:00Z", profile=profile,
            switch_key="SECOND-SAME-CANDIDATE", expected_current_epoch=first_epoch)
        self.coordinator.tick()
        self.assertEqual({position["activation_epoch_id"] for position in self.runner.readback()["positions"]},
            {first_epoch, second_epoch})
        self.assertEqual(self.coordinator.status()["inventory"]["position_count"], 2)
        self.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
        self.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
        with closing(PaperPlaneStore(self.runner.store_path)) as store:
            store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", ("OPERATING-" + first_epoch,))
        self.coordinator.tick()
        positions = {position["activation_epoch_id"]: position for position in self.runner.readback()["positions"]}
        self.assertEqual(positions[first_epoch]["state"], "OPEN")
        self.assertEqual(positions[second_epoch]["state"], "RECONCILED")
        self.assertEqual(self.coordinator.status()["inventory"]["position_count"], 1)
        self.assertIn(positions[first_epoch]["position_id"],
            {incident["incident_key"] for incident in self.coordinator.status()["incidents"]})

    def test_active_successor_profile_failure_does_not_starve_predecessor_exit(self):
        for damage in ("missing", "corrupt"):
            with self.subTest(profile=damage):
                case = OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    case.start_operating()
                    case.coordinator.tick()
                    first_epoch, first_runner = case.epoch, case.runner
                    first_profile = json.loads(json.dumps(case.profile))
                    before = first_runner.readback()
                    self.assertEqual([row["state"] for row in before["positions"]], ["OPEN"])
                    with closing(PaperPlaneStore(first_runner.store_path, readonly=True)) as store:
                        retained_profile = store.get_execution_event("PROFILE-" + first_epoch)

                    case.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
                    self.assertNotEqual(case.runner.strategy["strategy_id"], first_runner.strategy["strategy_id"])
                    self.assertNotEqual(case.runner.strategy["spec_sha256"], first_runner.strategy["spec_sha256"])
                    second_epoch = case.epoch
                    case.coordinator = TradingCoordinator(case.runner, mode="PAPER", clock=lambda: case.now)
                    switched = case.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:41:00Z",
                        profile=first_profile, switch_key="PROFILE-GAP-B", expected_current_epoch=first_epoch)
                    self.assertEqual(switched["generation"], 2)
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if damage == "missing":
                            store._conn.execute("DELETE FROM execution_events WHERE event_id=?", ("PROFILE-" + second_epoch,))
                        else:
                            profile_event = store.get_execution_event("PROFILE-" + second_epoch)
                            payload = profile_event["payload"]
                            payload["profile"]["poll_seconds"] = 0.03
                            # Retain the original hash: valid JSON with a corrupt native binding.
                            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                                (json.dumps(payload, sort_keys=True), "PROFILE-" + second_epoch))

                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    cold_runner = TradingContinuityRunner(case.root, data_root=case.data)
                    cold = TradingCoordinator(cold_runner, mode="PAPER", clock=lambda: case.now)
                    outcome = cold.run(ticks=2)
                    self.assertEqual(outcome["status"], "GRACEFUL_SHUTDOWN")
                    self.assertEqual(outcome["ticks"], 2)
                    after = cold_runner.readback()
                    self.assertEqual([(row["activation_epoch_id"], row["state"]) for row in after["positions"]],
                        [(first_epoch, "RECONCILED")])
                    self.assertEqual(len(after["modeled_attempts"]), 2)
                    self.assertEqual(len(after["modeled_results"]), 2)
                    self.assertEqual({row["position_id"] for row in after["modeled_attempts"]},
                        {before["positions"][0]["position_id"]})
                    self.assertEqual([row["payload"]["side"] for row in after["modeled_attempts"]], ["ENTRY", "EXIT"])
                    view = cold.status()
                    self.assertEqual(view["activation_epoch_id"], second_epoch)
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["inventory"]["position_count"], 0)
                    self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
                    self.assertEqual(view["input_reason"], "OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT")
                    self.assertIsNone(view["profile_sha256"])
                    self.assertIsNone(view["process_alive"])
                    self.assertIsNone(view["progress_moving"])
                    self.assertFalse(view["input_fresh"])
                    self.assertIn("OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT",
                        {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(cold_runner.store_path, readonly=True)) as store:
                        self.assertEqual(store.get_execution_event("PROFILE-" + first_epoch), retained_profile)
                        state = store._conn.execute("SELECT source_status FROM ordinary_state WHERE mode='PAPER'").fetchone()
                        self.assertEqual(state[0], "ACTIVE_PROFILE_UNAVAILABLE")
                finally:
                    case.tearDown()

    def test_active_successor_binding_failure_does_not_starve_predecessor_exit(self):
        for damage in ("missing", "corrupt"):
            with self.subTest(binding=damage):
                case = OperationalRecoveryTests(methodName=self._testMethodName)
                case.setUp()
                try:
                    case.start_operating()
                    case.coordinator.tick()
                    first_epoch, first_runner = case.epoch, case.runner
                    first_profile = json.loads(json.dumps(case.profile))
                    before = first_runner.readback()
                    self.assertEqual([row["state"] for row in before["positions"]], ["OPEN"])
                    with closing(PaperPlaneStore(first_runner.store_path, readonly=True)) as store:
                        retained = {prefix: store.get_execution_event(prefix + first_epoch)
                            for prefix in ("PROFILE-", "OPERATING-")}

                    case.prepare(operating=True, suffix="-B", negative=True, exit_point="E3600")
                    self.assertNotEqual(case.runner.strategy["spec_sha256"], first_runner.strategy["spec_sha256"])
                    second_epoch = case.epoch
                    case.coordinator = TradingCoordinator(case.runner, mode="PAPER", clock=lambda: case.now)
                    switched = case.coordinator.activate(epoch_id=second_epoch, at="2026-10-05T12:41:00Z",
                        profile=first_profile, switch_key="BINDING-GAP-B", expected_current_epoch=first_epoch)
                    self.assertEqual(switched["generation"], 2)
                    with closing(PaperPlaneStore(case.runner.store_path)) as store:
                        if damage == "missing":
                            store._conn.execute("DELETE FROM execution_events WHERE event_id=?", ("OPERATING-" + second_epoch,))
                        else:
                            # Preserve event identity anchors while corrupting only disposable payload bytes.
                            store._conn.execute("UPDATE execution_events SET payload_json='null' WHERE event_id=?",
                                ("OPERATING-" + second_epoch,))

                    case.source.tick(datetime(2026, 10, 5, 13, 5, tzinfo=UTC))
                    case.now = datetime(2026, 10, 5, 13, 10, tzinfo=UTC)
                    cold_runner = TradingContinuityRunner(case.root, data_root=case.data)
                    cold = TradingCoordinator(cold_runner, mode="PAPER", clock=lambda: case.now)
                    inventory = cold.status()["inventory"]
                    self.assertEqual(inventory["position_count"], 1)
                    self.assertEqual(inventory["inventory_status"], "UNKNOWN")
                    self.assertIsNone(inventory["outstanding_cost_basis_usd"])
                    self.assertEqual(Decimal(inventory["known_cost_basis_floor_usd"]), Decimal("30"))
                    outcome = cold.tick()
                    self.assertEqual(outcome["status"], "TICK_COMPLETE")
                    self.assertEqual(outcome["exits"], 1)
                    self.assertFalse(outcome["entries_enabled"])
                    self.assertEqual(outcome["source_status"], "ACTIVE_PROFILE_UNAVAILABLE")
                    self.assertEqual(cold.run(ticks=2)["status"], "GRACEFUL_SHUTDOWN")
                    after = cold_runner.readback()
                    self.assertEqual([(row["activation_epoch_id"], row["state"]) for row in after["positions"]],
                        [(first_epoch, "RECONCILED")])
                    self.assertEqual(len(after["modeled_results"]), 2)
                    self.assertEqual([row["payload"]["side"] for row in after["modeled_attempts"]], ["ENTRY", "EXIT"])
                    self.assertEqual({row["position_id"] for row in after["modeled_attempts"]},
                        {before["positions"][0]["position_id"]})
                    view = cold.status()
                    self.assertEqual(view["status"], "ACTION_REQUIRED")
                    self.assertEqual(view["activation_epoch_id"], second_epoch)
                    self.assertFalse(view["integrity_verified"])
                    self.assertEqual(view["inventory"]["position_count"], 0)
                    self.assertEqual(view["inventory"]["inventory_status"], "KNOWN")
                    self.assertIn({"epoch_id": second_epoch, "status": "INTEGRITY_CONFLICT"}, view["integrity_gaps"])
                    self.assertIn("OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT",
                        {row["reason"] for row in view["incidents"] if row["active"]})
                    with closing(PaperPlaneStore(cold_runner.store_path, readonly=True)) as store:
                        for prefix, event in retained.items():
                            self.assertEqual(store.get_execution_event(prefix + first_epoch), event)
                finally:
                    case.tearDown()

    def test_complete_cut_retains_known_cost_floor_before_later_unknown_total(self):
        self.start_operating(mode="SHADOW")
        backup = self.data / "backups/pre-unknown-cost-attempt.sqlite"
        self.coordinator.backup(destination_relative="backups/pre-unknown-cost-attempt.sqlite")
        grant = self.original_grant()
        self.coordinator.quote_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
            grant=grant, credential_supplier=lambda: None)
        calls = []

        def lose_response(raw, **limits):
            self.assertIsNone(limits["api_key"])
            calls.append(dict(raw))
            raise RuntimeError("SYNTHETIC_UNKNOWN_COST_CALLBACK_REQUIRED")

        with patch("solana_alpha_lab.factory.trading_adapters.http_quote", side_effect=lose_response):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_UNKNOWN_COST_CALLBACK_REQUIRED"):
                self.coordinator.tick()
            self.assertEqual(len(calls), 1)
            pending = self.runner.readback()
            self.assertEqual(pending["positions"][0]["state"], "ATTEMPTING")
            self.assertEqual(pending["modeled_results"], [])
            attempt = pending["modeled_attempts"][0]["payload"]
            with closing(PaperPlaneStore(self.runner.store_path, readonly=True)) as store:
                request = store.get_execution_event("REQUEST-" + attempt["attempt_id"])["payload"]
            results = [{"attempt_id": attempt["attempt_id"], "result_id": identity,
                "outcome": "UNKNOWN_REQUIRES_RECONCILIATION", "observed_at": at,
                "chargeable_cost_usd": cost} for identity, at, cost in (
                    ("C20-COST-KNOWN", "2026-10-05T12:40:10Z", "0.25"),
                    ("C20-COST-UNKNOWN", "2026-10-05T12:40:20Z", None))]
            self.runner.result(results[0])
            self.assertEqual(Decimal(self.runner.readback()["modeled_attempt_costs"]["known_additional_cost_usd"]),
                Decimal("0.25"))
            self.runner.result(results[1])
            original = self.runner.readback()
            self.assertEqual(original["positions"][0]["state"], "UNKNOWN")
            self.assertEqual(original["modeled_attempt_costs"]["additional_cost_status"], "UNKNOWN")
            self.assertEqual(Decimal(original["modeled_attempt_costs"]["known_additional_cost_usd"]), Decimal("0.25"))
            self.assertEqual([event["payload"]["result"] for event in original["modeled_results"]], results)
            self.assertEqual([event["created_at"] for event in original["modeled_results"]],
                [result["observed_at"] for result in results])
            receipt = {"attempt": attempt, "request": request, "result": results[-1]}
            receipt["receipt_sha256"] = sha256_of(receipt)
            self.now = datetime(2026, 10, 5, 12, 41, tzinfo=UTC)
            cut = self.production_cut(backup, effects=[receipt])
            self.assertEqual(cut["effects"], [receipt])
            self.assertEqual(cut["result_observations"], original["modeled_results"])
            original_claims = self.claims(self.runner)
            self.assertEqual(len(original_claims), 1)
            self.assertEqual(cut["quote_claims"], original_claims)
            fresh_adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192,
                grant=grant, credential_supplier=lambda: None)
            runner, coordinator = self.restored(backup, adapter=fresh_adapter)
            coordinator.reconcile_cut(cut)
            self.assertTrue(coordinator.reconcile_cut(cut)["idempotent"])
            restored = runner.readback()
            self.assertEqual(restored["modeled_attempts"], original["modeled_attempts"])
            self.assertEqual(restored["modeled_results"], original["modeled_results"])
            self.assertEqual(restored["modeled_attempt_costs"], original["modeled_attempt_costs"])
            self.assertEqual(restored["positions"][0]["position_id"], original["positions"][0]["position_id"])
            self.assertEqual(restored["positions"][0]["state"], "UNKNOWN")
            self.assertIsNone(restored["positions"][0]["qty_dec"])
            self.assertEqual(self.claims(runner), original_claims)
            view = coordinator.status()
            self.assertEqual(view["inventory"]["inventory_status"], "UNKNOWN")
            self.assertEqual(Decimal(view["inventory"]["known_cost_basis_floor_usd"]), Decimal("30"))
            self.assertEqual(Decimal(view["economics"][0]["additional_costs"]["known_additional_cost_usd"]), Decimal("0.25"))
            coordinator.tick()
            coordinator.tick()
            self.assertEqual(runner.readback()["modeled_results"], original["modeled_results"])
            self.assertEqual(runner.readback()["modeled_attempt_costs"], original["modeled_attempt_costs"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(fresh_adapter.calls, 0)
            self.assertTrue(coordinator.status()["restore_guard"])
        self.metrics = {"original_observations": 2, "restored_observations": 2,
            "known_additional_cost_floor_usd": "0.25", "unknown_total_retained": True,
            "original_http_calls": 1, "repeated_http_calls": 0}
