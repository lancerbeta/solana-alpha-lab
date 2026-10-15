"""I2 isolated native retirement, crash recovery and real CLI rehearsal."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT/'src') not in sys.path:
    sys.path.insert(0,str(ROOT/'src'))
from solana_alpha_lab.factory import observation_schedule_retention as owner
from solana_alpha_lab.factory.observation_schedule import render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore, ObservationScheduleStoreError
NOW = datetime(2026,10,15,12,tzinfo=UTC)
OLD = NOW-timedelta(days=40)
SAFE = {'safe':True,'cpu_safe':True,'ram_safe':True,'io_safe':True}


def _rehearsal_peak_rss_bytes():
    """Actual executing interpreter, rather than the Windows venv launcher."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                *[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]]
        counters=Counters(); counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.PeakWorkingSetSize)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)


def policy(scope='LEGACY', enabled=False):
    return {'schema':owner.POLICY_SCHEMA,'revision':1,'enabled':enabled,
        'allowed_scopes':[{'schedule_sha256':'a'*64,'activation_id':scope}],
        'allowed_classes':['call_ledger','poll_slots'],'min_age_days':31,'frozen_min_age_days':31,
        'max_rows':256,'max_bytes':8*1024*1024,'max_wall_seconds':5,
        'cadence_seconds':60,'due_guard_seconds':120,'physical_reclaim':False,'retained_restore_points':2}


def add_scope(store, activation='LEGACY', state='PAUSED_OPERATOR', schedule='a'*64):
    document={'retention':{'raw_retention_days':31},'schedule_sha256':schedule,
        'schedule_key':'fixture-'+schedule[:4]}
    store._conn.execute('INSERT OR IGNORE INTO registered_schedules VALUES(?,?,?,?,?)',
        (schedule,document['schedule_key'],json.dumps(document),owner.policy_sha256(document),render_utc(OLD)))
    store._conn.commit()
    store.upsert_activation({'schedule_sha256':schedule,'activation_id':activation,'schedule_key':'fixture',
        'state':state,'starts_at':render_utc(OLD),'stops_admitting_at':render_utc(OLD+timedelta(hours=1)),
        'payload':{'desired_state':'RUN'}},clock=OLD)


def add_call(store, occurrence='OCC-1', scope='LEGACY', size=100000, rowid=None, state='COMPLETED', raw=None, clock=OLD):
    request=hashlib.sha256(occurrence.encode()).hexdigest()
    payload={'status':'OBSERVED','response_sha256':'e'*64,'rows':[{'id':'m','value':'x'*size}],
        'entities':{'m':{'value':3}},'missing_reason':None,'raw_body_rel':raw}
    store.start_call(request_sha256=request,call_occurrence_id=occurrence,attempt_id='ATT-'+occurrence,
        primitive_id='PRIM',payload={},clock=clock)
    if state=='COMPLETED':
        store.complete_call(request_sha256=request,call_occurrence_id=occurrence,attempt_id='ATT-'+occurrence,
            payload=payload,clock=clock)
    if rowid is not None:
        store._conn.execute('UPDATE call_ledger SET rowid=? WHERE call_occurrence_id=?',(rowid,occurrence))
        store._conn.commit()
    store.insert_due({'schedule_sha256':'a'*64,'activation_id':scope,'entity_id':occurrence,
        'point_id':'P','primitive_id':'PRIM','state':'OBSERVED','due_at':render_utc(clock),
        'deadline_at':render_utc(clock+timedelta(minutes=1)), 'request_sha256':request,
        'call_occurrence_id':occurrence,'payload':{'status':'OBSERVED'}},clock=clock)
    return request


class NativeFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.hot=self.base/'hot'
        self.hot.mkdir()
        self.path=self.hot/'ops.sqlite'
        self.store=ObservationScheduleStore(self.path)
        add_scope(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def archive(self):
        return owner.create_cold_archive(self.store,archive_path=self.base/'cold'/'original.sqlite',
            restored_path=self.base/'independent'/'restored.sqlite',routine_roots=[self.hot])

    def commission(self, proof=None, enabled=False, **changes):
        proof=proof or self.archive()
        retirement={'schedule_sha256':'a'*64,'activation_id':'LEGACY','disallow_resume':True,
            'operation_mode':'ISOLATED_REHEARSAL','archive_proof':proof,'retire_pending_due':True}
        owner.install_retirement(self.store,retirement=retirement,approved_sha256=owner.policy_sha256(retirement),now=NOW)
        document=policy(enabled=enabled)
        document.update(changes)
        owner.install_maintenance_policy(self.store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)
        return document

    def plan(self, document):
        return owner.build_retirement_plan(self.store,now=NOW,policy=document)

    def apply(self, plan):
        return owner.apply_retirement_plan(self.store,plan=plan,approved_plan_sha256=plan['plan_id'],now=NOW)


class NativeRetentionTests(NativeFixture):
    def discovery_policy(self):
        document=policy(scope='TARGET',enabled=True)
        document.update(max_rows=2,auto_retire_terminal=True,allowed_classes=['call_ledger'],
            archive_refresh={'enabled':True,'max_objects':32,'max_bytes':16*1024*1024,
                'max_wall_seconds':30,'cold_root_relative':'cold','minimum_interval_seconds':1})
        owner.install_maintenance_policy(self.store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)
        return document

    def refresh_signal(self, now):
        with patch('solana_alpha_lab.factory.observation_schedule_runtime.load_runtime_config',return_value={'ops_store_relative':'ops.sqlite'}):
            return owner.checkpoint_archive_refresh_required(self.hot,now=now)

    def test_archive_discovery_advances_past_protected_prefix_and_survives_restart(self):
        add_scope(self.store,'OTHER','COMPLETE')
        add_scope(self.store,'TARGET','COMPLETE')
        add_call(self.store,'PREFIX-1',scope='OTHER',size=100)
        add_call(self.store,'PREFIX-2',scope='OTHER',size=100)
        add_call(self.store,'TARGET-CALL',scope='TARGET',size=100)
        self.discovery_policy()
        owner.run_maintenance_step(self.store,now=NOW,pressure=SAFE)
        self.assertFalse(self.refresh_signal(NOW)['required'])
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        owner.run_maintenance_step(self.store,now=NOW+timedelta(minutes=2),pressure=SAFE)
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        signal=self.refresh_signal(NOW+timedelta(minutes=2))
        self.assertTrue(signal['required'],signal)
        self.assertEqual(signal['reason'],'DURABLE_TERMINAL_ARCHIVE_DISCOVERY')
        discovery=owner._control(self.store,'maintenance')['archive_discovery']
        self.assertEqual([row['call_occurrence_id'] for row in discovery],['TARGET-CALL'])
        self.assertIn('rows',self.store.call_payload('TARGET-CALL'))  # No invented archive.

    def test_archive_discovery_rewinds_for_newly_aged_naturally_closed_scope(self):
        add_scope(self.store,'OTHER','COMPLETE')
        add_scope(self.store,'TARGET','ACTIVE')
        add_call(self.store,'PREFIX-1',scope='OTHER',size=100)
        add_call(self.store,'PREFIX-2',scope='OTHER',size=100)
        add_call(self.store,'FUTURE-CALL',scope='TARGET',size=100,clock=NOW)
        self.discovery_policy()
        for minute in (0,2):
            owner.run_maintenance_step(self.store,now=NOW+timedelta(minutes=minute),pressure=SAFE)
        self.assertFalse(self.refresh_signal(NOW+timedelta(minutes=2))['required'])
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        future=NOW+timedelta(days=32)
        self.store.transition_activation(schedule_sha256='a'*64,activation_id='TARGET',new_state='DRAINING',clock=future)
        self.store.transition_activation(schedule_sha256='a'*64,activation_id='TARGET',new_state='COMPLETE',clock=future)
        for minute in (0,2):
            owner.run_maintenance_step(self.store,now=future+timedelta(minutes=minute),pressure=SAFE)
        self.assertTrue(self.refresh_signal(future+timedelta(minutes=2))['required'])
        row=self.store._conn.execute('SELECT created_at,updated_at FROM call_ledger WHERE call_occurrence_id=?',('FUTURE-CALL',)).fetchone()
        self.assertEqual(tuple(row),(render_utc(NOW),render_utc(NOW)))

    def test_exact_archived_retirement_preserves_source_and_denominator(self):
        add_call(self.store,rowid=101)
        self.store._conn.execute("INSERT INTO lifetime_counters VALUES(?,?,?,?,?)",('a'*64,'LEGACY',17,987,render_utc(OLD)))
        self.store._conn.commit()
        document=self.commission()
        original=self.store._conn.execute('SELECT created_at,updated_at,state FROM call_ledger').fetchone()
        result=self.apply(self.plan(document))
        self.assertEqual(result['applied_call_compactions'],1)
        current=self.store._conn.execute('SELECT created_at,updated_at,state FROM call_ledger').fetchone()
        self.assertEqual(tuple(current),tuple(original))
        self.assertEqual(self.store._conn.execute('SELECT provider_calls FROM lifetime_counters').fetchone()[0],17)
        payload=self.store.call_payload('OCC-1')
        self.assertEqual(payload['raw_payload_retention'],owner.COMPACTION_MARKER)
        self.assertEqual(payload['entities'],{'m':{'value':3}})
        self.assertNotIn('rows',payload)
        with self.assertRaisesRegex(ObservationScheduleStoreError,'RETIRED_SCOPE_RESUME_DISALLOWED'):
            self.store.transition_activation(schedule_sha256='a'*64,activation_id='LEGACY',new_state='ACTIVE',clock=NOW)
        self.assertEqual(self.apply(self.plan(document))['applied_call_compactions'],0)

    def test_age_without_owner_or_archive_cannot_apply(self):
        add_call(self.store)
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'EXACT_ARCHIVE_BOUND_PLAN_REQUIRED'):
            owner.apply_retention(self.store,now=NOW,raw_retention_days=31,dry_run=False)
        self.assertEqual(owner.evaluate_retention(self.store,now=NOW,raw_retention_days=31)['eligible_call_compactions'],0)
        proof=self.archive()
        document={'schedule_sha256':'a'*64,'activation_id':'LEGACY','disallow_resume':True,
            'operation_mode':'OPERATE','archive_proof':proof}
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'INDEPENDENT_COLD_OPERATE_PROOF_REQUIRED'):
            owner.install_retirement(self.store,retirement=document,approved_sha256=owner.policy_sha256(document),now=NOW)

    def test_candidate_stale_refuses_but_other_active_updates_do_not(self):
        add_call(self.store)
        document=self.commission()
        plan=self.plan(document)
        add_scope(self.store,'ACTIVE','ACTIVE',schedule='b'*64)
        self.assertEqual(self.apply(plan)['applied_call_compactions'],1)
        # A separate exact source tests a changed candidate before any effect.
        self.store._conn.execute("UPDATE call_ledger SET payload_json=?",(json.dumps({'rows':[1,2,3]}),))
        self.store._conn.commit()
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'PLAN_STALE_CANDIDATE'):
            self.apply(plan)

    def test_round_outbox_unknown_raw_and_frozen_protect(self):
        request=add_call(self.store)
        document=self.commission()
        self.store.record_episode_round(round_id='R',schedule_sha256='a'*64,activation_id='LEGACY',
            lineage_id='L',round_started_at=render_utc(OLD),state='STARTED',frame={},clock=NOW)
        self.assertIn('ROUND_RECOVERY',self.plan(document)['exclusions'])
        plan=self.plan(document)
        self.assertFalse(plan['candidates'])
        self.store._conn.execute("DELETE FROM episode_rounds")
        self.store._conn.execute("UPDATE due_observations SET state='UNKNOWN'")
        self.store._conn.commit()
        self.assertIn('UNRESOLVED_OR_NONTERMINAL_DUE',self.plan(document)['exclusions'])
        self.store._conn.execute("UPDATE due_observations SET state='OBSERVED',payload_json='{\"export_pin\":true}'")
        self.store._conn.commit()
        self.assertIn('FROZEN_EXPORT_CAPTURE_PIN',self.plan(document)['exclusions'])

    def test_payload_budget_prevents_decode_and_rows_use_keyset(self):
        add_call(self.store,size=100000)
        document=self.commission(max_bytes=1024)
        self.store._conn.set_trace_callback(lambda sql: self.fail('oversized payload fetched') if 'SELECT payload_json FROM call_ledger WHERE rowid' in sql else None)
        plan=self.plan(document)
        self.store._conn.set_trace_callback(None)
        self.assertIn('OVERSIZE_PAYLOAD_REFUSED',plan['exclusions'])
        self.assertEqual(plan['scanned_rows'],1)
        self.assertTrue(plan['selection_complete'])
        self.assertEqual(plan['next_cursor']['call_ledger'],1)

    def test_oversize_refusal_advances_to_small_after_restart_and_stays_unhealthy(self):
        add_call(self.store,'OVERSIZE',size=100000)
        add_call(self.store,'SMALL',size=10)
        self.commission(enabled=True,max_bytes=1024,max_rows=1)
        first=owner.run_maintenance_step(self.store,now=NOW,pressure=SAFE)
        self.assertEqual(first['reason'],'OVERSIZE_PAYLOAD_REFUSED')
        self.assertEqual(first['status'],'PROGRESS')
        self.assertEqual(owner.retention_status(self.store)['state'],'FAILED')
        self.assertEqual(owner._control(self.store,'maintenance')['next_cursor']['call_ledger'],1)
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        second=owner.run_maintenance_step(self.store,now=NOW+timedelta(minutes=2),pressure=SAFE)
        self.assertEqual(second['applied_call_compactions'],1)
        self.assertEqual(self.store.call_payload('SMALL')['raw_payload_retention'],owner.COMPACTION_MARKER)
        self.assertIn('rows',self.store.call_payload('OVERSIZE'))
        self.assertEqual(owner.retention_status(self.store)['state'],'FAILED')
        self.assertEqual(second['refused_rows'],1)

    def test_resume_committed_chunk_after_crash(self):
        add_call(self.store,'OCC-1')
        add_call(self.store,'OCC-2')
        document=self.commission()
        plan=self.plan(document)
        original=owner._archive_candidate_matches
        calls=0
        def crash(candidate):
            nonlocal calls
            calls+=1
            if calls==2:
                raise RuntimeError('isolated interruption')
            original(candidate)
        with patch.object(owner,'_archive_candidate_matches',side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.apply(plan)
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        self.assertEqual(self.apply(plan)['applied_call_compactions'],1)
        self.assertEqual(self.apply(plan)['applied_call_compactions'],0)

    def test_native_reclaim_shrinks_preserves_rowids_sequences_sibling_root(self):
        add_call(self.store,size=2*1024*1024,rowid=101)
        document=self.commission()
        self.apply(self.plan(document))
        self.store.record_event('BEFORE',{'counter':17},clock=NOW)
        self.store._conn.execute("UPDATE runtime_events SET event_id=77")
        self.store._conn.execute("UPDATE sqlite_sequence SET seq=88 WHERE name='runtime_events'")
        for rowid in (7,19):
            self.store._conn.execute('INSERT INTO episode_admissions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('EP-'+str(rowid),'a'*64,'LEGACY','L','C','mint-'+str(rowid),render_utc(OLD),'COHORT',
                 render_utc(OLD),'d'*64,'{}','R',render_utc(OLD)))
            self.store._conn.execute('UPDATE episode_admissions SET rowid=? WHERE episode_id=?',(rowid,'EP-'+str(rowid)))
        self.store._conn.commit()
        self.store._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        rdp=self.hot/'observation_rdp'
        rdp.mkdir()
        inode=rdp.stat().st_ino
        final_proof=owner.create_cold_archive(self.store,archive_path=self.base/'final-current.sqlite',
            restored_path=self.base/'final-current-restored.sqlite',routine_roots=[self.hot])
        plan=owner.build_reclaim_plan(self.store,data_root=rdp)
        fingerprint=plan['fingerprint']
        result=owner.apply_physical_reclaim(self.store,plan=plan,approved_plan_sha256=plan['plan_id'],
            data_root=rdp,writers_quiesced=True,independent_recovery_proof=final_proof,now=NOW)
        self.assertLess(result['after_bytes'],result['before_bytes']//2)
        with owner._sqlite_connection(self.path) as connection:
            self.assertEqual(owner.native_identity_fingerprint(connection),fingerprint)
            self.assertEqual(connection.execute('SELECT rowid FROM call_ledger').fetchone()[0],101)
            self.assertEqual([row[0] for row in connection.execute('SELECT rowid FROM episode_admissions ORDER BY rowid')],[7,19])
        self.assertEqual(rdp.stat().st_ino,inode)
        owner.recover_physical_reclaim(self.path,data_root=rdp,action='resume',approved_plan_sha256=plan['plan_id'])
        self.store=ObservationScheduleStore(self.path)
        self.store.record_event('AFTER',{'counter':18},clock=NOW)
        self.assertEqual(self.store._conn.execute('SELECT max(event_id) FROM runtime_events').fetchone()[0],89)
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'ROLLBACK_AFTER_RESUME'):
            owner.recover_physical_reclaim(self.path,data_root=rdp,action='rollback',approved_plan_sha256=plan['plan_id'])

    def test_default_disabled_pressure_due_and_checkpoint_yield(self):
        self.assertEqual(owner.run_maintenance_step(self.store,now=NOW)['status'],'DISABLED')
        add_call(self.store)
        self.commission(enabled=True)
        self.assertEqual(owner.run_maintenance_step(self.store,now=NOW,pressure=SAFE,checkpoint_active=True)['reason'],'CHECKPOINT_ACTIVE')
        self.assertEqual(owner.run_maintenance_step(self.store,now=NOW)['reason'],'PRESSURE_UNKNOWN_OR_UNSAFE')
        self.assertEqual(owner.run_maintenance_step(self.store,now=NOW,pressure=SAFE)['applied_call_compactions'],1)
        self.store.close()
        self.store=ObservationScheduleStore(self.path)
        self.assertEqual(owner.run_maintenance_step(self.store,now=NOW+timedelta(seconds=10),pressure=SAFE)['reason'],'CADENCE_WAIT')

    def test_registered_lower_bound_cannot_be_forged(self):
        document=policy()
        document.update(min_age_days=14,frozen_min_age_days=14)
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'FROZEN_RETENTION_LOWER_BOUND'):
            owner.install_maintenance_policy(self.store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)

    def test_plan_revalidates_new_recovery_dependency_before_effect(self):
        add_call(self.store)
        document=self.commission()
        plan=self.plan(document)
        self.store.record_episode_round(round_id='R',schedule_sha256='a'*64,activation_id='LEGACY',
            lineage_id='L',round_started_at=render_utc(OLD),state='STARTED',frame={},clock=NOW)
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'PLAN_STALE_PROTECTED:ROUND_RECOVERY'):
            self.apply(plan)
        self.assertIn('rows',self.store.call_payload('OCC-1'))

    def test_cli_status_and_plan_current_wal_without_store_mutation(self):
        add_call(self.store)
        document=self.commission()
        before=self.path.read_bytes()
        wal=Path(str(self.path)+'-wal').read_bytes()
        command=[sys.executable,'-B',str(ROOT/'scripts/observation_schedule_retention.py'),
            'status','--store',str(self.path),'--now',render_utc(NOW)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['eligible_call_compactions'],1)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(Path(str(self.path)+'-wal').read_bytes(),wal)
        missing=self.base/'missing'/'ops.sqlite'
        command[command.index(str(self.path))]=str(missing)
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertFalse(missing.parent.exists())

    def test_read_only_status_request_budgets_narrow_installed_policy(self):
        for index in range(3):
            add_call(self.store,'BUDGET-'+str(index),size=10000)
        self.commission()
        before=self.path.read_bytes()
        wal_path=Path(str(self.path)+'-wal')
        wal_before=wal_path.read_bytes()
        approved=owner._control(self.store,'policy')
        script=ROOT/'scripts/observation_schedule_retention.py'
        def status(*arguments):
            result=subprocess.run([sys.executable,'-B',str(script),'status','--store',str(self.path),
                '--now',render_utc(NOW),*map(str,arguments)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        rows=status('--max-rows',1)
        self.assertEqual(rows['scanned_rows'],1)
        self.assertEqual(rows['read_only_budget']['max_rows'],1)
        self.assertFalse(rows['selection_complete'])
        byte_limited=status('--max-rows',1,'--max-bytes',512)
        self.assertLessEqual(byte_limited['scanned_bytes'],512)
        self.assertEqual(byte_limited['read_only_budget']['max_bytes'],512)
        self.assertIn('OVERSIZE_PAYLOAD_REFUSED',byte_limited['exclusions'])
        wall=status('--max-wall-seconds','0.000000000001')
        self.assertEqual(wall['scanned_rows'],0)
        self.assertEqual(wall['read_only_budget']['max_wall_seconds'],1e-12)
        self.assertEqual(owner._control(self.store,'policy'),approved)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(wal_path.read_bytes(),wal_before)

class AutomaticMaintenanceTests(unittest.TestCase):
    def test_three_same_scope_raw_batches_finish_through_ordinary_caller_after_restart(self):
        from contextlib import ExitStack, closing
        from dataclasses import replace
        import os
        from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
        from solana_alpha_lab.factory import offhost_backup as backup, hot90_closed_day_loop as closed_day
        from solana_alpha_lab.factory.hot90_activation import write_hot90_runtime_state
        from solana_alpha_lab.factory.remote_ops import load_config_v1_1
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as cleanup:
            base=Path(temporary); root=_seed_tree(base/'factory')
            for relative in ('configs/observation_schedule_runtime_v1.yaml',
                             'catalog/schemas/observation_schedule_runtime_v1.schema.json'):
                target=root/relative; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/relative).read_bytes())
            loaded=load_config_v1_1(root)
            for relative in loaded['backup']['mutable_only_recursive_relative_paths']:
                (root/relative).mkdir(parents=True,exist_ok=True)
            write_hot90_runtime_state(root,{'activation_stage':'DURABILITY_CUTOVER',
                'production_compaction_enabled':False,'production_eviction_enabled':False,'drive_writes_enabled':True})
            credentials=root/'rclone-fixture.conf'; credentials.write_text('[fixture]\ntype = drive\n',encoding='utf-8')
            credentials.chmod(0o600)
            config=replace(backup.load_offhost_config(root),rclone_config_absolute=credentials)
            remote=FakeRcloneRunner()
            def transport(argv):
                sub=remote._subcommand(argv)
                if sub=='copyto' and argv[-2] in remote.payloads:
                    target=Path(argv[-1]); target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(remote.payloads[argv[-2]])
                    return subprocess.CompletedProcess(argv,0,'','')
                if sub=='copyto' and argv[-2].startswith(config.remote_prefix):
                    return subprocess.CompletedProcess(argv,1,'','object absent')
                if sub=='hashsum' and 'sha256' in argv:
                    payload=remote.payloads.get(argv[-1])
                    return subprocess.CompletedProcess(argv,1,'','object absent') if payload is None else subprocess.CompletedProcess(
                        argv,0,hashlib.sha256(payload).hexdigest()+'  '+Path(argv[-1]).name+'\n','')
                return remote(argv)
            path=root/'local/factory_v1/observation_schedule_state.sqlite'
            with owner._sqlite_connection(path) as fixture:
                fixture.execute('DROP TABLE activations')
            store=ObservationScheduleStore(path); cleanup.callback(store.close)
            add_scope(store,'LEGACY','COMPLETE')
            for number in range(3):
                relative='datasets/raw_evidence/20260905/raw'+str(number)+'.json'
                raw=root/'local/factory_v1/observation_rdp'/relative
                raw.parent.mkdir(parents=True,exist_ok=True); raw.write_text(json.dumps({'source':number}),encoding='utf-8')
                add_call(store,'C'+str(number),size=1000,raw=relative)
            document=policy(enabled=True); document.update(max_rows=1,auto_retire_terminal=True,
                archive_refresh={'enabled':True,'max_objects':128,'max_bytes':64*1024*1024,
                    'max_wall_seconds':120,'cold_root_relative':'local/factory_v1/retirement_cold',
                    'minimum_interval_seconds':60,'local_cache_retained':1})
            owner.install_maintenance_policy(store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)
            store.close(); store=ObservationScheduleStore(path); cleanup.callback(store.close); store.close()
            original_read_text=Path.read_text
            def host_read_text(path,*args,**kwargs):
                if path.as_posix()=='/proc/meminfo': return 'MemAvailable: 1048576 kB\n'
                if path.as_posix()=='/proc/pressure/io': return 'some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n'
                return original_read_text(path,*args,**kwargs)
            remaining=[]; outcomes=[]; cache_counts=[]
            with patch.object(backup,'load_offhost_config',return_value=config), patch.object(
                    closed_day,'load_offhost_config',return_value=config), patch.object(
                    os,'getloadavg',return_value=(0,0,0),create=True), patch.object(Path,'read_text',new=host_read_text):
                archived=closed_day.process_one_day(root,'20260905',now=NOW,rclone_runner=transport,allow_drive=True)
                self.assertEqual(archived['terminal'],'REMOTE_CONTENT_SHA256_VERIFIED',archived)
                for cycle in range(10):
                    now=NOW+timedelta(days=cycle)
                    receipt=backup.run_offhost_checkpoint(root,mode='daily',config=config,runner=transport,now=now)
                    outcome=backup.run_checkpoint_maintenance(root,receipt,now=now,runner=transport)
                    outcomes.append(outcome)
                    with closing(ObservationScheduleStore(path,readonly=True,immutable=False)) as restarted:
                        count=restarted._conn.execute("SELECT count(*) FROM call_ledger WHERE json_extract(payload_json,'$.raw_payload_retention') IS NULL").fetchone()[0]
                        remaining.append(count)
                        self.assertEqual(owner.retention_status(restarted)['approved_policy_sha256'],owner.policy_sha256(document))
                        self.assertLessEqual((remaining[-2] if len(remaining)>1 else 3)-count,document['max_rows'])
                    cache_root=root/document['archive_refresh']['cold_root_relative']
                    caches=[item for item in cache_root.iterdir() if item.is_dir()] if cache_root.is_dir() else []
                    cache_counts.append(len(caches))
                    self.assertLessEqual(len(caches),2,(remaining,outcomes))
                    if 'scanned_rows' in outcome:
                        self.assertLessEqual(outcome['scanned_rows'],document['max_rows'])
                        self.assertLessEqual(outcome['scanned_bytes'],document['max_bytes'])
                    if count==0: break
            self.assertEqual(remaining[-1],0,(remaining,outcomes))
            self.assertEqual(cache_counts[-1],1)
            with closing(ObservationScheduleStore(path,readonly=True,immutable=False)) as restarted:
                retired=owner._scope_retirement(restarted,('a'*64,'LEGACY'))
                self.assertIsNotNone(retired)
                for filename in retired['archive_proof']['pin_objects']:
                    self.assertIsNotNone(restarted._conn.execute('SELECT 1 FROM retention_archive_pins WHERE object_name=?',(filename,)).fetchone())
                    self.assertIn(config.remote_object(filename),remote.payloads)
                self.assertFalse(Path(retired['archive_proof']['cache_root']).exists())
            self.assertEqual(len(list((root/'local/factory_v1/observation_rdp/datasets/raw_evidence/20260905').glob('*.json'))),3)
            print('I2_MULTI_BATCH_REHEARSAL '+json.dumps({'remaining_bodies_after_ordinary_cycles':remaining,
                'cache_generations_after_cycles':cache_counts,'max_rows':1,'old_remote_proof_pins':'PRESERVED',
                'old_local_cache':'RELEASED','hot_raw_files':3}))

    def test_forged_restore_cache_cannot_register_rows_absent_from_remote_objects(self):
        from contextlib import ExitStack
        from dataclasses import replace
        from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
        from solana_alpha_lab.factory import offhost_backup as backup
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as cleanup:
            base=Path(temporary)
            root=_seed_tree(base/'factory')
            credentials=root/'rclone-fixture.conf'
            credentials.write_text('[fixture]\ntype = drive\n',encoding='utf-8')
            credentials.chmod(0o600)
            config=replace(backup.load_offhost_config(root),rclone_config_absolute=credentials)
            runner=FakeRcloneRunner()
            def transport(argv):
                if runner._subcommand(argv)=='copyto' and argv[-2] in runner.payloads:
                    target=Path(argv[-1]); target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(runner.payloads[argv[-2]])
                    return subprocess.CompletedProcess(argv,0,'','')
                return runner(argv)
            path=root/'local/factory_v1/observation_schedule_state.sqlite'
            with owner._sqlite_connection(path) as fixture:
                fixture.execute('DROP TABLE activations')
            store=ObservationScheduleStore(path); cleanup.callback(store.close)
            add_scope(store,'LEGACY','COMPLETE')
            add_call(store,'IN_REMOTE',size=1000)
            document=policy(enabled=True); document['auto_retire_terminal']=True
            owner.install_maintenance_policy(store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)
            store.close(); store=ObservationScheduleStore(path); cleanup.callback(store.close)
            receipt=backup.run_offhost_checkpoint(root,mode='daily',config=config,runner=transport,now=NOW)
            checkpoint=next(root.rglob(receipt['checkpoint_filename']))
            isolated=base/'independent'
            proof=backup.verify_remote_checkpoint_restore(checkpoint_path=checkpoint,isolated_root=isolated,config=config,runner=transport)
            actual_remote_hashes={item.name:owner._file_hash(item) for item in (isolated/'objects').iterdir()}
            archived=isolated/'restored/local/factory_v1/observation_schedule_state.sqlite'
            original_cached_bytes=archived.read_bytes()
            add_call(store,'NEVER_IN_REMOTE',size=1000)
            for mutation in ('new_call','counter','admission','same_count_body'):
                with self.subTest(mutation=mutation):
                    archived.write_bytes(original_cached_bytes)
                    if mutation=='new_call':
                        with owner._sqlite_connection(archived) as copied:
                            store._conn.backup(copied)
                    else:
                        cached=ObservationScheduleStore(archived)
                        try:
                            if mutation=='counter':
                                cached.save_lifetime(schedule_sha256='a'*64,activation_id='LEGACY',
                                    provider_calls=19,canonical_bytes=29,clock=NOW)
                            elif mutation=='admission':
                                cached.commit_episode_admission(record={'episode_id':'NEVER_IN_REMOTE',
                                    'schedule_sha256':'a'*64,'activation_id':'LEGACY','collection_lineage_id':'L',
                                    'cycle_start':render_utc(NOW),'mint':'m','t0':render_utc(NOW),
                                    'cohort_id':'C','round_id':'R'},content_sha256='e'*64,
                                    final_deadline_at=render_utc(NOW+timedelta(minutes=5)),clock=NOW)
                            else:
                                cached._conn.execute("UPDATE call_ledger SET payload_json=? WHERE call_occurrence_id='IN_REMOTE'",
                                    (json.dumps({'status':'OBSERVED','rows':['BODY_NEVER_IN_REMOTE']}),))
                                cached._conn.commit()
                            cached._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                        finally:
                            cached.close()
                    # Self-rebinding supplied JSON cannot turn a local copy
                    # into an independently reconstructed remote archive.
                    proof['operational_inventory']=[{'path':item.relative_to(isolated/'restored').as_posix(),
                        'bytes':item.stat().st_size,'sha256':owner._file_hash(item)}
                        for item in sorted((isolated/'restored').rglob('*')) if item.is_file()]
                    (isolated/'.remote-restore-proof.json').write_text(json.dumps(proof),encoding='utf-8')
                    with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'CHECKPOINT_ARCHIVE_RECONSTRUCTION_MISMATCH'):
                        owner.register_checkpoint_retirement_archive(store,proof=proof,isolated_root=isolated,source_root=root,now=NOW)
                    self.assertFalse((isolated/'.prune-verify').exists())
            self.assertIsNone(owner._control(store,'checkpoint_archive'))
            self.assertIn('rows',store.call_payload('NEVER_IN_REMOTE'))
            self.assertEqual({item.name:owner._file_hash(item) for item in (isolated/'objects').iterdir()},actual_remote_hashes)

    def test_two_explicit_terminal_scopes_repeat_after_restart(self):
        from contextlib import ExitStack
        from dataclasses import replace
        from tests.test_factory_offhost_backup import FakeRcloneRunner, _seed_tree
        from solana_alpha_lab.factory import offhost_backup as backup
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as cleanup:
            base=Path(temporary)
            root=_seed_tree(base/'factory')
            credentials=root/'rclone-fixture.conf'
            credentials.write_text('[fixture]\ntype = drive\n',encoding='utf-8')
            credentials.chmod(0o600)
            config=replace(backup.load_offhost_config(root),rclone_config_absolute=credentials)
            runner=FakeRcloneRunner()
            def transport(argv):
                if runner._subcommand(argv)=='copyto' and argv[-2] in runner.payloads:
                    target=Path(argv[-1]); target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(runner.payloads[argv[-2]])
                    return subprocess.CompletedProcess(argv,0,'','')
                return runner(argv)
            path=root/'local/factory_v1/observation_schedule_state.sqlite'
            with owner._sqlite_connection(path) as fixture:
                fixture.execute('DROP TABLE activations')  # Offhost fixture stub, replaced by native schema.
            store=ObservationScheduleStore(path)
            cleanup.callback(store.close)
            add_scope(store,'CHILD-0','COMPLETE')
            document=policy(enabled=True)
            document.update(allowed_scopes=[{'schedule_sha256':'a'*64,'activation_id':'CHILD-'+str(i)} for i in range(2)],auto_retire_terminal=True)
            owner.install_maintenance_policy(store,policy=document,approved_sha256=owner.policy_sha256(document),now=NOW)
            store.close()
            store=ObservationScheduleStore(path)  # Complete fixture schedule-alias bootstrap before capture.
            cleanup.callback(store.close)
            for day in range(2):
                scope='CHILD-'+str(day)
                add_scope(store,scope,'COMPLETE')
                rawrel='datasets/raw_evidence/20260901/raw-'+str(day)+'.json'
                raw=root/'local/factory_v1/observation_rdp'/rawrel
                raw.parent.mkdir(parents=True,exist_ok=True)
                raw.write_text(json.dumps({'m':{'value':'x'*100000}}),encoding='utf-8')
                add_call(store,'AUTO-'+str(day),scope=scope,size=1,raw=rawrel)
                store._conn.execute('UPDATE call_ledger SET payload_json=? WHERE call_occurrence_id=?',
                    (json.dumps({'entities':{'m':{'value':'x'*100000}},'status':'OBSERVED','raw_body_rel':rawrel,'response_sha256':'e'*64}),'AUTO-'+str(day)))
                store._conn.commit()
                store.managed_upsert_child(lineage='L',utc_day='2026-09-0'+str(day+1),state='ACTIVATED',
                    profile_revision=1,schedule_sha256='a'*64,activation_id=scope,payload={'profile_hash':'frozen'},clock=OLD)
                # Real native backup/chain pack + actual independent download/restore.
                receipt=backup.run_offhost_checkpoint(root,mode='daily',config=config,runner=transport,now=NOW+timedelta(days=day))
                checkpoint=next(root.rglob(receipt['checkpoint_filename']))
                isolated=base/('independent-'+str(day))
                proof=backup.verify_remote_checkpoint_restore(checkpoint_path=checkpoint,isolated_root=isolated,config=config,runner=transport)
                if day==0:
                    proof_path=base/'independent-restore-proof.json'
                    record_path=base/'registered-cold-record.json'
                    proof_path.write_text(json.dumps(proof),encoding='utf-8')
                    command=[sys.executable,'-B',str(ROOT/'scripts/observation_schedule_retention.py'),
                        'register-checkpoint-archive','--store',str(path),'--factory-root',str(root),
                        '--isolated-root',str(isolated),'--input',str(proof_path),'--output',str(record_path),
                        '--now',render_utc(NOW)]
                    refused=subprocess.run(command,capture_output=True,text=True)
                    self.assertEqual(refused.returncode,2)
                    self.assertFalse(record_path.exists())
                    registered=subprocess.run([*command,'--i-understand-apply'],capture_output=True,text=True)
                    self.assertEqual(registered.returncode,0,registered.stderr)
                    record=json.loads(record_path.read_text(encoding='utf-8'))
                    first_record=record
                    self.assertEqual(record,owner._control(store,'checkpoint_archive'))
                    self.assertEqual(record['proof_class'],'REMOTE_CHECKPOINT_RESTORE_VERIFIED')
                    self.assertEqual(record['source_id'],owner._control(store,'source_identity')['source_id'])
                    owner.verify_cold_archive(record,deep=False)
                    with owner._sqlite_connection(Path(record['archive_path']).as_uri()+'?mode=ro&immutable=1',uri=True) as recovered:
                        self.assertEqual(owner.native_identity_fingerprint(recovered,recovery_causal=True),
                            owner.native_identity_fingerprint(store._conn,recovery_causal=True))
                    store.record_event('AFTER_REMOTE_ARCHIVE',{'counter':19},clock=NOW)
                    operate_plan=owner.build_reclaim_plan(store,
                        data_root=root/'local/factory_v1/observation_rdp',backup_root=root,operation_mode='OPERATE')
                    with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'RECLAIM_RECOVERY_NOT_FINAL_CURRENT'):
                        owner.apply_physical_reclaim(store,plan=operate_plan,approved_plan_sha256=operate_plan['plan_id'],
                            data_root=root/'local/factory_v1/observation_rdp',backup_root=root,
                            writers_quiesced=True,independent_recovery_proof=record,now=NOW)
                else:
                    owner.register_checkpoint_retirement_archive(store,proof=proof,isolated_root=isolated,source_root=root,now=NOW+timedelta(days=day))
                    current_record=owner._control(store,'checkpoint_archive')
                    owner._set_control(store,'active_plan',{'archive_registry':{'old':first_record}})
                    store._conn.commit()
                    self.assertEqual(owner.checkpoint_archive_cache_releasable(store)['reason'],'CHECKPOINT_CACHE_ACTIVE_CONSUMER')
                    owner._set_control(store,'active_plan',{'archive_registry':{'current':current_record}})
                    store._conn.commit()
                    self.assertEqual(owner.checkpoint_archive_cache_releasable(store)['status'],'RELEASABLE')
                    store._conn.execute("DELETE FROM retention_control WHERE control_key='active_plan'")
                    store._conn.commit()
                store.close()
                store=ObservationScheduleStore(path)
                cleanup.callback(store.close)
                result=owner.run_maintenance_step(store,now=NOW+timedelta(days=day),pressure=SAFE)
                self.assertEqual(result['status'],'COMPLETE',result)
                payload=store.call_payload('AUTO-'+str(day))
                self.assertEqual(payload['entities_retention'],owner.COMPACTION_MARKER)
                self.assertNotIn('entities',payload)
                self.assertEqual(payload['raw_body_rel'],rawrel)
                self.assertTrue(raw.is_file())
                self.assertEqual(store.get_activation('a'*64,scope)['state'],'COMPLETE')
                self.assertGreater(store._conn.execute('SELECT count(*) FROM retention_archive_pins').fetchone()[0],0)
            # A fresh normal checkpoint contains no retired decoded body.
            receipt=backup.run_offhost_checkpoint(root,mode='daily',config=config,runner=transport,now=NOW+timedelta(days=3))
            checkpoint=next(root.rglob(receipt['checkpoint_filename']))
            proof=backup.verify_remote_checkpoint_restore(checkpoint_path=checkpoint,isolated_root=base/'logical-next',config=config,runner=transport)
            restored=base/'logical-next/restored/local/factory_v1/observation_schedule_state.sqlite'
            with owner._sqlite_connection(restored) as connection:
                for (payload,) in connection.execute('SELECT payload_json FROM call_ledger'):
                    self.assertNotIn('entities',json.loads(payload))
            store.close()

class NativeCutoverAndCLITests(NativeFixture):
    def test_reclaim_requires_recovery_of_final_current_native_state(self):
        def event():
            self.store.record_event('AFTER_ARCHIVE',{'counter':19},clock=NOW)
        def counter():
            self.store.save_lifetime(schedule_sha256='a'*64,activation_id='LEGACY',
                provider_calls=19,canonical_bytes=29,clock=NOW)
        def admission():
            self.assertEqual(self.store.commit_episode_admission(record={
                'episode_id':'AFTER_ARCHIVE','schedule_sha256':'a'*64,'activation_id':'LEGACY',
                'collection_lineage_id':'L','cycle_start':render_utc(NOW),'mint':'m',
                't0':render_utc(NOW),'cohort_id':'C','round_id':'R'},content_sha256='e'*64,
                final_deadline_at=render_utc(NOW+timedelta(minutes=5)),clock=NOW),'COMMITTED')
        for name,mutate in [('event',event),('counter',counter),('admission',admission)]:
            with self.subTest(name=name):
                proof=owner.create_cold_archive(self.store,archive_path=self.base/(name+'-archive.sqlite'),
                    restored_path=self.base/(name+'-restored.sqlite'),routine_roots=[self.hot])
                mutate()
                plan=owner.build_reclaim_plan(self.store,data_root=self.hot)
                with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'RECLAIM_RECOVERY_NOT_FINAL_CURRENT'):
                    owner.apply_physical_reclaim(self.store,plan=plan,approved_plan_sha256=plan['plan_id'],
                        data_root=self.hot,writers_quiesced=True,independent_recovery_proof=proof,now=NOW)
                self.assertFalse(any(path.exists() for path in owner._reclaim_paths(self.path)))

    def test_crash_recovery_and_new_write_boundary(self):
        for phase in ('PREPARED','ORIGINAL_MOVED','SWITCHED'):
            with self.subTest(phase=phase):
                root=self.base/phase
                root.mkdir()
                path=root/'ops.sqlite'
                store=ObservationScheduleStore(path)
                store.record_event('CURRENT',{'counter':17},clock=NOW)
                archive=owner.create_cold_archive(store,archive_path=self.base/(phase+'-archive.sqlite'),
                    restored_path=self.base/(phase+'-restored.sqlite'),routine_roots=[root])
                plan=owner.build_reclaim_plan(store,data_root=root)
                with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'RECLAIM_INJECTED_CRASH'):
                    owner.apply_physical_reclaim(store,plan=plan,approved_plan_sha256=plan['plan_id'],
                        data_root=root,writers_quiesced=True,independent_recovery_proof=archive,now=NOW,failpoint=phase)
                store.close()
                owner.recover_physical_reclaim(path,data_root=root,action='rollback',approved_plan_sha256=plan['plan_id'])
                with owner._sqlite_connection(path) as connection:
                    self.assertEqual(owner.native_identity_fingerprint(connection),plan['fingerprint'])
        root=self.base/'after-writes'; root.mkdir()
        path=root/'ops.sqlite'
        store=ObservationScheduleStore(path)
        archive=owner.create_cold_archive(store,archive_path=self.base/'writes-archive.sqlite',
            restored_path=self.base/'writes-restored.sqlite',routine_roots=[root])
        plan=owner.build_reclaim_plan(store,data_root=root)
        owner.apply_physical_reclaim(store,plan=plan,approved_plan_sha256=plan['plan_id'],
            data_root=root,writers_quiesced=True,independent_recovery_proof=archive,now=NOW)
        with owner._sqlite_connection(path) as connection:
            connection.execute("INSERT INTO runtime_events(kind,created_at,payload_json) VALUES('NEW',?,'{}')",(render_utc(NOW),))
        with self.assertRaisesRegex(owner.ObservationScheduleRetentionError,'NEW_WRITES_FORWARD_REPAIR_REQUIRED'):
            owner.recover_physical_reclaim(path,data_root=root,action='rollback',approved_plan_sha256=plan['plan_id'])

    def test_full_real_cli_plan_apply_reclaim_and_next_writer(self):
        add_call(self.store,size=2*1024*1024,rowid=313)
        self.commission()
        original=self.store.call_payload('OCC-1')
        original_body_bytes=len(json.dumps(original['rows'],sort_keys=True,separators=(',',':')).encode())
        original_payload_bytes=self.store._conn.execute('SELECT length(CAST(payload_json AS BLOB)) FROM call_ledger').fetchone()[0]
        proof=json.loads(self.store._conn.execute('SELECT payload_json FROM retirement_scopes').fetchone()[0])['archive_proof']
        proofpath=self.base/'cold-proof.json'; proofpath.write_text(json.dumps(proof),encoding='utf-8')
        self.store.close()
        wal_path=Path(str(self.path)+'-wal')
        wal_before=wal_path.stat().st_size if wal_path.is_file() else 0
        files_before=sum(path.is_file() for path in self.hot.rglob('*'))
        cli_started=time.perf_counter()
        script=ROOT/'scripts/observation_schedule_retention.py'
        def cli(command,*arguments):
            result=subprocess.run([sys.executable,'-B',str(script),command,'--store',str(self.path),
                '--now',render_utc(NOW),*map(str,arguments)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        planpath=self.base/'retirement-plan.json'
        plan=cli('plan','--output',planpath)
        result=cli('apply','--plan',planpath,'--approved-sha256',plan['plan_id'],'--i-understand-apply')
        self.assertEqual(result['applied_call_compactions'],1)
        self.store=ObservationScheduleStore(self.path)
        final_proof=owner.create_cold_archive(self.store,archive_path=self.base/'final-current.sqlite',
            restored_path=self.base/'final-current-restored.sqlite',routine_roots=[self.hot])
        proofpath.write_text(json.dumps(final_proof),encoding='utf-8')
        self.store.close()
        rdp=self.hot/'observation_rdp'; rdp.mkdir()
        inode=rdp.stat().st_ino
        reclaimpath=self.base/'reclaim-plan.json'
        reclaim=cli('reclaim-plan','--data-root',rdp,'--max-wall-seconds',30,'--output',reclaimpath)
        result=cli('reclaim-apply','--plan',reclaimpath,'--input',proofpath,
            '--approved-sha256',reclaim['plan_id'],'--data-root',rdp,'--writers-quiesced','--i-understand-apply')
        self.assertLess(result['after_bytes'],result['before_bytes']//2)
        cli('reclaim-resume','--data-root',rdp,'--approved-sha256',reclaim['plan_id'],'--i-understand-apply')
        self.store=ObservationScheduleStore(self.path)
        self.store.record_event('NATIVE_SUCCESSOR',{'counter':18},clock=NOW)
        self.assertEqual(self.store._conn.execute('SELECT rowid FROM call_ledger').fetchone()[0],313)
        self.assertEqual(rdp.stat().st_ino,inode)
        projected=self.store.call_payload('OCC-1')
        projected_body_bytes=len(json.dumps(projected['rows']).encode()) if 'rows' in projected else 0
        projected_payload_bytes=self.store._conn.execute('SELECT length(CAST(payload_json AS BLOB)) FROM call_ledger').fetchone()[0]
        self.store.close()
        elapsed=time.perf_counter()-cli_started
        wal_after=wal_path.stat().st_size if wal_path.is_file() else 0
        files_after=sum(path.is_file() for path in self.hot.rglob('*'))
        from solana_alpha_lab.factory import remote_ops
        import zipfile
        source_relative=self.path.relative_to(self.base).as_posix()
        config={'schema_version':'1.1','backup':{'source_relative_paths':[source_relative],
            'recursive_relative_paths':[],'same_parent_forbidden':True,
            'independent_sink_relative':'next-checkpoint'}}
        checkpoint_started=time.perf_counter()
        packed=remote_ops.package_backup(self.base,config=config,
            sink_override=self.base/'next-checkpoint',prune_superseded=False)
        independent_db=self.base/'independent-next-checkpoint.sqlite'
        with zipfile.ZipFile(Path(packed['sink'])/packed['bundle']) as archive:
            independent_db.write_bytes(archive.read(source_relative))
            manifest=json.loads(archive.read('BACKUP_MANIFEST.json'))
        self.assertEqual([entry['path'] for entry in manifest['entries']],[source_relative])
        self.assertEqual(manifest['entries'][0]['kind'],'SQLITE_BACKUP_API')
        with owner._sqlite_connection(independent_db) as independent:
            retired_body_count=independent.execute("""SELECT count(*) FROM call_ledger WHERE
                json_type(payload_json,'$.rows') IS NOT NULL OR json_type(payload_json,'$.body') IS NOT NULL OR
                json_type(payload_json,'$.raw_body') IS NOT NULL OR json_type(payload_json,'$.response_body') IS NOT NULL OR
                json_type(payload_json,'$.payload_rows') IS NOT NULL""").fetchone()[0]
            self.assertEqual(retired_body_count,0)
            self.assertEqual(independent.execute('SELECT rowid FROM call_ledger').fetchone()[0],313)
            self.assertEqual(independent.execute("SELECT count(*) FROM runtime_events WHERE kind='NATIVE_SUCCESSOR'").fetchone()[0],1)
        checkpoint_elapsed=time.perf_counter()-checkpoint_started
        print('I2_CLI_REHEARSAL '+json.dumps({'before_bytes':result['before_bytes'],'after_bytes':result['after_bytes'],
            'rowid':313,'next_native_writer':'PASS','root_inode':'PRESERVED',
            'logical_retired_body_before_bytes':original_body_bytes,'logical_retired_body_after_bytes':projected_body_bytes,
            'call_payload_before_bytes':original_payload_bytes,'provenance_payload_after_bytes':projected_payload_bytes,
            'sqlite_wal_before_bytes':wal_before,'sqlite_wal_after_bytes':wal_after,
            'hot_root_files_before':files_before,'hot_root_files_after':files_after,
            'cli_chain_wall_seconds':round(elapsed,3),
            'next_full_checkpoint_bytes':packed['bytes'],'independent_checkpoint_retired_body_count':retired_body_count,
            'next_full_checkpoint_wall_seconds':round(checkpoint_elapsed,3),
            'rehearsal_process_peak_rss_bytes':_rehearsal_peak_rss_bytes(),
            'rss_scope':'ACTUAL_TEST_INTERPRETER_EXCLUDES_CLI_CHILDREN',
            'cli_child_peak_rss_bytes':'UNKNOWN'}))

if __name__ == '__main__':
    unittest.main()
