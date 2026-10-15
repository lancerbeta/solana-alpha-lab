"""Opt-in >=5.3 GB I2 rehearsal, excluded from normal unittest discovery.

Run with locked Python: build; ledger-before --baseline; production-metadata;
ledger-final --package; interrupt. Writes only local/i2_capture. No provider IO.
The SQLite file is allocated native history, never a sparse size-only stand-in.
"""
from __future__ import annotations
import contextlib, hashlib, json, os, shutil, sqlite3, subprocess, sys, threading, time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from solana_alpha_lab.factory import remote_ops as r
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, SyntheticMarket, cli_tick, nominate, synth_mint, token_object
BASE = ROOT/'local/i2_capture'
PRODUCER = BASE/'producer-ledger'
RDP = 'local/factory_v1/observation_rdp'
OPS = RDP+'/observation_schedule_state.sqlite'
CONFIG = {'schema_version':'1.1','backup':{'source_relative_paths':[OPS],
    'recursive_relative_paths':[RDP+'/datasets/publication_jobs'],
    'same_parent_forbidden':True,'independent_sink_relative':'local/factory_v1_backup_sink'}}
START = datetime(2026,10,5,tzinfo=UTC)

def emit(path, value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def build():
    BASE.mkdir(exist_ok=True)
    if (BASE/'fixture-ledger.json').exists(): return
    assert not (PRODUCER/OPS).exists(), 'incomplete fixture: inspect, do not overwrite'
    sc = EpisodeScenario(PRODUCER/RDP,start=START,stops=START+timedelta(hours=12))
    mint=synth_mint('I2-scale')
    row=token_object(mint,price=1,liquidity=10000,holders=60)
    nominate(sc.market,START,{'toporganicscore':[row],'toptraded':[],'toptrending':[]})
    sc.market.series[mint]=lambda now:row
    tick=sc.tick(START+timedelta(seconds=5),fault='AFTER_MANIFEST')
    assert tick['_exit_code'] != 0
    path=PRODUCER/OPS
    t=time.monotonic()
    # Real allocated SQLite pages and native schema, not a sparse/faked file.
    # Repeated synthetic JSON approximates retained structured runtime payloads.
    payload=json.dumps({'fixture':'SYNTHETIC_NO_LIVE_DATA','body':'0123456789abcdef'*4094})
    with contextlib.closing(sqlite3.connect(path)) as c:
        c.execute('PRAGMA wal_autocheckpoint=1000')
        for batch in range(84):
            c.executemany('INSERT INTO call_ledger(request_sha256,call_occurrence_id,attempt_id,state,primitive_id,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                [(hashlib.sha256(f'scale-{batch}-{i}'.encode()).hexdigest(),f'SCALE-{batch}-{i}',f'SCALE-{batch}-{i}',
                  'COMPLETED','I2-SYNTHETIC',payload,'2026-10-05T00:00:00Z','2026-10-05T00:00:00Z') for i in range(1000)])
            c.commit()
        c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    jobs=PRODUCER/RDP/'datasets/publication_jobs/completed'
    jobs.mkdir(parents=True,exist_ok=True)
    for i in range(8120):
        (jobs/f'scale-{i:06}.json').write_text(json.dumps({'stage':'COMPLETE','fixture':i}),encoding='utf-8')
    emit(BASE/'fixture-ledger.json',{'db_bytes':path.stat().st_size,'closed_call_ledger_rows':84000,
        'metadata_files':8120,'build_seconds':time.monotonic()-t,'synthetic':True,
        'schema':'native ObservationScheduleStore','native_open_job_stage':'MANIFEST'})

def writer(label):
    started=time.monotonic(); observations=[]; n=0
    clock_path=BASE/'writer-next-ledger.json'
    offset=json.loads(clock_path.read_text())['seconds'] if clock_path.exists() else 40
    ready=BASE/(label+'.writer-ready'); go=BASE/(label+'.writer-go'); stop=BASE/(label+'.writer-stop')
    store=ObservationScheduleStore(PRODUCER/OPS)
    market=SyntheticMarket(); mint=synth_mint('I2-scale')
    row=token_object(mint,price=1,liquidity=10000,holders=60)
    nominate(market,START,{'toporganicscore':[row],'toptraded':[],'toptrending':[]})
    market.series[mint]=lambda now:row
    ready.touch()
    while not go.exists(): time.sleep(.01)
    while not stop.exists():
        t=time.monotonic()
        try:
            store.record_event('I2_CONCURRENT_NATIVE_WRITER',{'n':n})
            write={'ok':True}
        except Exception as exc:
            write={'ok':False,'error':type(exc).__name__}
            store.close();store=ObservationScheduleStore(PRODUCER/OPS)
        observations.append({'kind':'write','start':t-started,'elapsed':time.monotonic()-t,**write})
        if n%8==0:
            t=time.monotonic()
            try:
                result=cli_tick(PRODUCER/RDP,market,START+timedelta(seconds=offset+n))
                pub=result.get('publications',[])
                tick={'ok':result['_exit_code']==0,'exit_code':result['_exit_code'],
                    'terminal':result.get('terminal'),'stop_reason':result.get('stop_reason'),
                    'publications':len(pub) if isinstance(pub,list) else pub}
            except Exception as exc: tick={'ok':False,'error':type(exc).__name__}
            observations.append({'kind':'publication_tick','start':t-started,'elapsed':time.monotonic()-t,**tick})
        n+=1; time.sleep(.1)
    store.close()
    emit(clock_path,{'seconds':offset+n+10})
    emit(BASE/(label+'.writer.json'),{'observations':observations,'wall_seconds':time.monotonic()-started})

def production_metadata():
    # A bounded read-only host probe measured 8214 immutable completed receipts,
    # total 8953548 bytes, maximum 1096. Match/exceed both count and byte scale.
    directory=PRODUCER/RDP/'datasets/publication_jobs/completed'
    assert directory.resolve().is_relative_to((ROOT/'local').resolve())
    body={'stage':'COMPLETE','fixture':'SYNTHETIC_COMPLETED_METADATA_SCALE','padding':'x'*1010}
    total=0
    for i in range(8214):
        data=json.dumps({**body,'fixture_index':i},sort_keys=True).encode()
        path=directory/f'scale-{i:06}.json'
        assert not path.is_symlink()
        path.write_bytes(data);total+=len(data)
    assert total>=8953548
    emit(BASE/'metadata-scale.json',{'synthetic_completed_files':8214,'synthetic_completed_bytes':total,
        'source':'PRODUCTION_METADATA_ONLY_PROBE','market_payload_reads':0})

def run(label, package=False):
    BASE.mkdir(exist_ok=True)
    assert (PRODUCER/OPS).stat().st_size>=5_300_000_000
    events=[]; active=[]; start=time.monotonic(); lock={'held':False}; sizes={'peak_wal_bytes':0,'peak_staging_bytes':0,'min_free_bytes':shutil.disk_usage(BASE).free}
    done=threading.Event()
    def monitor():
        while not done.wait(.1):
            wal=Path(str(PRODUCER/OPS)+'-wal')
            sizes['peak_wal_bytes']=max(sizes['peak_wal_bytes'],wal.stat().st_size if wal.exists() else 0)
            parent=PRODUCER/r.BACKUP_SNAPSHOT_STAGING_RELATIVE
            try:
                sizes['peak_staging_bytes']=max(sizes['peak_staging_bytes'],sum(p.stat().st_size for p in parent.rglob('*') if p.is_file()))
            except FileNotFoundError: pass
            sizes['min_free_bytes']=min(sizes['min_free_bytes'],shutil.disk_usage(BASE).free)
    def measured(name, original):
        def call(*args,**kwargs):
            t=time.monotonic(); event={'phase':name,'start':t-start,'writer_fenced':lock['held']}
            if name in ('sqlite_copy','sha256'):
                p=Path(args[0]); event['bytes']=p.stat().st_size; event['source']=p.name
            active.append(name)
            try:
                value=original(*args,**kwargs)
                if name=='enumeration':event['count']=len(value)
                return value
            except BaseException as exc:
                event['error']=str(exc) if isinstance(exc,r.RemoteOpsError) else type(exc).__name__
                raise
            finally:
                active.pop(); event['elapsed']=time.monotonic()-t
                if name=='sha256' and event.get('bytes',0)<1024*1024:
                    key='small_file_sha256'
                    summary=next((x for x in events if x['phase']==key),None)
                    if summary is None:
                        summary={'phase':key,'count':0,'bytes':0,'elapsed':0};events.append(summary)
                    summary['count']+=1;summary['bytes']+=event.get('bytes',0);summary['elapsed']+=event['elapsed']
                else: events.append(event)
        return call
    original_fence=r._capture_writer_fences
    @contextlib.contextmanager
    def fence(sources):
        t=time.monotonic()
        try:
            with original_fence(sources):
                acquired=time.monotonic(); events.append({'phase':'fence_wait','elapsed':acquired-t,'count':len(sources)})
                lock['held']=True; (BASE/(label+'.writer-go')).touch()
                try: yield
                finally:
                    lock['held']=False
                    events.append({'phase':'fence_hold','elapsed':time.monotonic()-acquired})
        finally: events.append({'phase':'fence_total','elapsed':time.monotonic()-t})
    patches=[patch.object(r,'_capture_writer_fences',fence)]
    if '--baseline' in sys.argv:
        import importlib.util
        saved=BASE/'baseline_remote_ops.py'
        saved.write_bytes(subprocess.check_output(['git','show','304b16e682fb5b5760229d4fd39fcab7a35aa307:src/solana_alpha_lab/factory/remote_ops.py'],cwd=ROOT))
        spec=importlib.util.spec_from_file_location('i2_baseline_remote',saved)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        globals()['r']=module
        original_fence=r._capture_writer_fences
        patches=[patch.object(r,'_capture_writer_fences',fence)]
    for attr,name in [('_backup_source_paths','enumeration'),('consistent_sqlite_backup','sqlite_copy'),
        ('_sha256_file','sha256'),('_capture_recovery_dependencies','dependencies'),('_verify_recovery_control','control_verify')]:
        patches.append(patch.object(r,attr,measured(name,getattr(r,attr))))
    for suffix in ('writer-ready','writer-go','writer-stop'):
        (BASE/(label+'.'+suffix)).unlink(missing_ok=True)
    worker=subprocess.Popen([sys.executable,'-B',__file__,'writer',label],cwd=ROOT,
        stdout=(BASE/(label+'.worker.log')).open('w'),stderr=subprocess.STDOUT)
    deadline=time.monotonic()+30
    while not (BASE/(label+'.writer-ready')).exists():
        assert worker.poll() is None
        assert time.monotonic()<deadline
        time.sleep(.02)
    thread=threading.Thread(target=monitor,daemon=True); thread.start()
    result={'label':label,'db_bytes':(PRODUCER/OPS).stat().st_size,'config':CONFIG}
    try:
        with contextlib.ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            with r.backup_payload_snapshot(PRODUCER,CONFIG) as snapshot:
                result['capture_seconds']=time.monotonic()-start
                result['native_capture_trace']=getattr(snapshot,'capture_trace',None)
                inv=r.scan_backup_inventory(PRODUCER,config=CONFIG,snapshot=snapshot)
                result['inventory_sha256']=inv['inventory_sha256'];result['entries']=len(inv['entries'])
                result['snapshot_db_sha256']=snapshot.entry(OPS)['sha256']
                with contextlib.closing(sqlite3.connect(snapshot.staged_path(OPS).as_uri()+'?mode=ro&immutable=1',uri=True)) as c:
                    result['snapshot_native_events']=c.execute("SELECT count(*) FROM runtime_events WHERE kind='I2_CONCURRENT_NATIVE_WRITER'").fetchone()[0]
                if package:
                    pack_started=time.monotonic()
                    packed=r.package_backup(PRODUCER,config=CONFIG,sink_override=BASE/'sink',snapshot=snapshot,prune_superseded=False)
                    result['packaging_seconds']=time.monotonic()-pack_started
                    result['package']={k:v for k,v in packed.items() if k!='entries'}
                    result['backup_ready_seconds']=time.monotonic()-start
                    restore_started=time.monotonic()
                    subprocess.run([sys.executable,'-B',__file__,'restore-only',label,
                        packed['bundle'],inv['inventory_sha256']],cwd=ROOT,check=True,timeout=10800)
                    result['restore_seconds']=time.monotonic()-restore_started
                    result['restore']=json.loads((BASE/(label+'.restore.json')).read_text())
                result['outcome']='PASS'
    except BaseException as exc:
        result['outcome']='FAIL';result['failure']=str(exc) if isinstance(exc,r.RemoteOpsError) else type(exc).__name__
        import traceback;traceback.print_exc()
    finally:
        result['capture_cleanup_wall_seconds']=time.monotonic()-start
        (BASE/(label+'.writer-go')).touch();time.sleep(3)
        (BASE/(label+'.writer-stop')).touch();worker.wait(timeout=30)
        done.set();thread.join(2)
        result.update(sizes);result['trace']=events
        observations=json.loads((BASE/(label+'.writer.json')).read_text())['observations']
        result['writer']={kind:{'successes':sum(x['kind']==kind and x['ok'] for x in observations),
            'failures':sum(x['kind']==kind and not x['ok'] for x in observations),
            'max_seconds':max((x['elapsed'] for x in observations if x['kind']==kind),default=0)}
            for kind in ('write','publication_tick')}
        result['writer']['publications']=sum(x.get('publications',0) or 0 for x in observations)
        if '--baseline' not in sys.argv and any(not x['ok'] for x in observations):
            result['outcome']='FAIL_NATIVE_WRITER_OR_PUBLICATION'
        result['staging_remaining']=len(list((PRODUCER/r.BACKUP_SNAPSHOT_STAGING_RELATIVE).glob('capture-*')))
        emit(BASE/(label+'.json'),result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('config','package','restore','trace','native_capture_trace')},sort_keys=True))

def restore_only(label, bundle, inventory):
    dest=BASE/(label+'.restored')
    def deny_producer(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            if Path(os.fsdecode(args[0])).absolute().is_relative_to(PRODUCER):
                raise PermissionError('ISOLATED_PRODUCER_READ_FORBIDDEN')
    sys.addaudithook(deny_producer)
    try:
        (PRODUCER/OPS).open('rb')
    except PermissionError: pass
    else: raise AssertionError('source isolation failed')
    value=r.restore_incremental_chain_isolated(full_bundle=BASE/'sink'/bundle,deltas=[],
        dest_root=dest,expected_inventory_sha256=inventory)
    control=r._verify_recovery_control(dest)
    assert value['raw_inventory_sha256']==inventory
    assert control['transitions']>=1 and control['authorities']>=1
    emit(BASE/(label+'.restore.json'),{'raw_inventory_sha256':value['raw_inventory_sha256'],
        'control':control,'producer_reads':'FORBIDDEN_VERIFIED','fresh_process':True})

def interrupt():
    def hashes():
        return {p.name:hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in (BASE/'sink').glob('BACKUP_*.zip')}
    before=hashes();assert before, 'requires verified prior isolated bundle'
    child=subprocess.Popen([sys.executable,'-B',__file__,'capture-only','--interrupt-self'],cwd=ROOT,
        stdout=(BASE/'interrupt-child.log').open('w'),stderr=subprocess.STDOUT)
    stage=PRODUCER/r.BACKUP_SNAPSHOT_STAGING_RELATIVE
    assert child.wait(90)==73, 'fault must terminate actual capture interpreter'
    fault=json.loads((BASE/'interrupted-process.json').read_text())
    partial=fault['partial_copy_bytes']
    t=time.monotonic()
    peer=ObservationScheduleStore(PRODUCER/OPS)
    peer.record_event('I2_CAPTURE_INTERRUPTED_NATIVE_WRITE',{'synthetic':True});peer.close()
    release=time.monotonic()-t
    orphans=len(list(stage.glob('capture-*')));assert orphans==1
    restart=time.monotonic()
    # Native ownership cleanup and next real capture, with no manual state fix.
    with r.backup_payload_snapshot(PRODUCER,CONFIG) as snapshot:
        inventory=r.scan_backup_inventory(PRODUCER,config=CONFIG,snapshot=snapshot)
        assert snapshot.entry(OPS)['bytes']>=5_300_000_000
        r._verify_recovery_control(snapshot.staged_path(OPS).parents[3])
    after=hashes();assert after==before
    assert not list(stage.glob('capture-*'))
    emit(BASE/'interrupt.json',{'partial_copy_bytes_at_kill':partial,'orphan_count_before_native_restart':orphans,
        'fault':'OS_EXIT_73_IN_ACTUAL_CAPTURE_PROCESS','launcher_pid':child.pid,'actual_capture_pid':fault['pid'],
        'writer_commit_after_kill_seconds':release,'next_capture_seconds':time.monotonic()-restart,
        'last_good_bundle_hashes_unchanged':True,'next_inventory_sha256':inventory['inventory_sha256'],
        'staging_remaining':0,'manual_state_fix':False})

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='build':build()
    elif mode=='production-metadata':production_metadata()
    elif mode=='writer':writer(sys.argv[2])
    elif mode=='restore-only':restore_only(*sys.argv[2:5])
    elif mode=='capture-only':
        if '--interrupt-self' in sys.argv:
            def exit_during_copy():
                stage=PRODUCER/r.BACKUP_SNAPSHOT_STAGING_RELATIVE
                until=time.monotonic()+80
                while time.monotonic()<until:
                    for marker in stage.glob('capture-*/.capture-owner.json'):
                        try:
                            if json.loads(marker.read_text()).get('pid')!=os.getpid(): continue
                            db=marker.parent/OPS
                            if db.exists() and db.stat().st_size>16*1024*1024:
                                emit(BASE/'interrupted-process.json',{'pid':os.getpid(),'partial_copy_bytes':db.stat().st_size})
                                os._exit(73)
                        except FileNotFoundError: pass
                    time.sleep(.01)
            threading.Thread(target=exit_during_copy,daemon=True).start()
        with r.backup_payload_snapshot(PRODUCER,CONFIG): pass
    elif mode=='interrupt':interrupt()
    else:run(mode,package='--package' in sys.argv)
