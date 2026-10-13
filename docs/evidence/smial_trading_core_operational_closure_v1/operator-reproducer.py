import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from contextlib import closing, redirect_stdout, redirect_stderr
from datetime import UTC, datetime

root=Path(__file__).resolve().parents[3]
own=Path(__file__).parent
e=root/'docs/evidence/smial_trading_core_operational_closure_v1'
sys.path[:0]=[str(root/'src'),str(root/'tests'),str(root)]
from solana_alpha_lab.factory.hfic_research_scope import sha256_of
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
import test_trading_core_operational_closure_v1 as fixture
output=Path(sys.argv[1]) if len(sys.argv)>1 else e/'operator-proof.json'
required=json.loads((e/'executed-tests.json').read_text(encoding='utf8'))['source_pins']
def pins(): return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in required}
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path,body): path.write_text(json.dumps(body,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8',newline='\n')
def sql(path,query):
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row;conn.execute('PRAGMA query_only=ON')
        return [dict(r) for r in conn.execute(query)]
def family(path):
    return {suffix: {'present':Path(str(path)+suffix).is_file(),
        'sha256':sha(Path(str(path)+suffix).read_bytes()) if Path(str(path)+suffix).is_file() else 'ABSENT',
        'bytes':Path(str(path)+suffix).stat().st_size if Path(str(path)+suffix).is_file() else None}
        for suffix in ('','-wal','-shm','-journal')}

before=pins();start=time.perf_counter();steps=[];canaries=[];out=io.StringIO()
case=fixture.OperatingDriverTests();case.setUp();owned=Path(case.tmp.name)
try:
    preparation=time.perf_counter()
    with redirect_stdout(out),redirect_stderr(out):
        case.prepare(operating=True,suffix='-COLD-FINAL',exit_point='E3600')
    prep_elapsed=round(time.perf_counter()-preparation,6)
    donor=case.data;restored=case.root/'local/cold-final-restored'
    profile={'schema_version':'1.0','mode':'PAPER',
        'source':{'root':str(case.source.data_root),'file':'observation_schedule_state.sqlite',
            'schedule_sha256':case.admission['schedule_sha256'],'activation_id':case.admission['activation_id']},
        'batch_size':2,'poll_seconds':0.02,'source_max_age_seconds':900,'progress_max_age_seconds':60,
        'observation_max_age_seconds':900,
        'envelope':{'schema_version':'1.0','mode':'PAPER','basis':'OUTSTANDING_OBLIGATIONS_V1',
            'max_outstanding_positions':1,'max_outstanding_cost_basis_usd':'30'},
        'model':{'version':'TIMELY_OBSERVATION_MODEL_V1','missing_input':'UNKNOWN','latency_seconds':0,'additional_cost_usd':'0.01'},
        'quote':{'timeout_seconds':1,'max_response_bytes':8192,'funding_mint':'So11111111111111111111111111111111111111112',
            'asset_metadata_file':'assets.json','funding_observation_file':'funding.json','max_exit_input_raw':None},
        'network_authorized':False}
    save(donor/'profile.json',profile)
    (donor/'independent-effect-receipts.json').write_text('[]\n',encoding='utf8')
    def command(name, *, target=donor, mode='PAPER', expected=0, canary=False, **arguments):
        argv=[sys.executable,'-B',str(root/'scripts/trading_continuity.py'),name,
              '--repository-root',str(case.root),'--data-root',str(target),'--mode',mode]
        for key,value in arguments.items():
            argv+=['--'+key.replace('_','-')]
            if value is not True: argv+=[str(value)]
        db=target/'paper_plane.sqlite'; original=family(db) if canary else None
        tick=time.perf_counter(); proc=subprocess.run(argv,cwd=root,capture_output=True,timeout=30)
        elapsed=round(time.perf_counter()-tick,6)
        assert proc.returncode==expected,(name,proc.returncode,proc.stdout.decode('utf8'),proc.stderr.decode('utf8'))
        if canary:
            final=family(db)
            assert final==original,(name,'READONLY_PHYSICAL_CANARY',original,final)
            canaries.append({'sequence':len(steps)+1,'command':name,'physical_family_byte_exact':True,
                             'wal_bytes':original['-wal']['bytes'],'family_sha256':sha256_of(original)})
        text=proc.stdout.decode('utf8')
        body=json.loads(text) if arguments.get('format')!='human' else None
        safe={k:('<retained-native-backup>' if k=='backup' else str(v)) for k,v in arguments.items()}
        steps.append({'sequence':len(steps)+1,'command':name,'runtime_scope':'DONOR' if target==donor else 'RESTORED',
            'mode':mode,'arguments':safe,'exit_code':proc.returncode,'expected_exit_code':expected,
            'elapsed_seconds':elapsed,'stdout_sha256':sha(proc.stdout),'stderr_sha256':sha(proc.stderr),
            'status':body.get('status') if body else 'HUMAN_STATUS_RENDERED',
            'native_command_binding_sha256':sha256_of({'command':name,'scope':'DONOR' if target==donor else 'RESTORED','arguments':safe,'mode':mode})})
        return body if body is not None else text

    at='2026-10-05T12:40:00Z'
    checked=command('check',strategy=case.strategy_rel,profile='profile.json',as_of=at)
    assert checked['activation_created'] is False
    command('operating-activate',strategy=case.strategy_rel,profile='profile.json',epoch=case.epoch,
            as_of=case.manifest['decision_effective_at'],switch_key='COLD-FINAL-INITIAL')
    command('run',ticks=1,as_of=at)
    # Native holder stabilizes empty-WAL coordination before strict GET canaries.
    holder=PaperPlaneStore(donor/'paper_plane.sqlite')
    try:
        with closing(PaperPlaneStore(donor/'paper_plane.sqlite',readonly=True)) as reader: reader.positions()
        status=command('status',as_of=at,canary=True)
        positions=sql(donor/'paper_plane.sqlite','SELECT * FROM positions')
        assert len(positions)==1 and positions[0]['state']=='OPEN'
        pid=positions[0]['position_id'];bot=positions[0]['bot_instance_id']
        command('pause',bot_instance_id=bot,idempotency_key='COLD-FINAL-PAUSE')
        command('status',as_of=at,format='human',canary=True)
        backup=command('backup',destination='backups/cold-final.sqlite')
        backup_path=donor/'backups/cold-final.sqlite'
        backup_sha=sha(backup_path.read_bytes())
        config_before=sql(donor/'paper_plane.sqlite',"SELECT event_id,event_type,payload_json FROM execution_events WHERE event_type IN ('OPERATING_ENVELOPE_ACCEPTED','TRADING_RUNTIME_POLICY_ACCEPTED') ORDER BY event_id")
        command('export-cut',backup=backup_path,input='independent-effect-receipts.json',external_cut_id='COLD-FINAL-NO-POST-BACKUP-EFFECTS',
                complete_after_backup=True,as_of=at,destination='external-cut-input.json')
    finally: holder.close()
    command('init',target=restored)
    command('restore',target=restored,backup=backup_path)
    (restored/'external-cut-input.json').write_bytes((donor/'external-cut-input.json').read_bytes())
    sealed=command('seal-cut',target=restored,input='external-cut-input.json',destination='complete-external-cut.json')
    command('reconcile',target=restored,input='complete-external-cut.json')
    restored_holder=PaperPlaneStore(restored/'paper_plane.sqlite')
    try:
        with closing(PaperPlaneStore(restored/'paper_plane.sqlite',readonly=True)) as reader: reader.positions()
        fenced=command('status',target=restored,as_of=at,canary=True)
        command('status',target=restored,as_of=at,format='human',canary=True)
        assert fenced['restore_guard'] is True or fenced['restore_guard']==1
        inventory=fenced['inventory_sha256']
        command('ack-restore',target=restored,input='complete-external-cut.json',inventory_sha256=inventory,as_of=at)
        acked=command('status',target=restored,as_of=at,canary=True)
        assert not acked['restore_guard']
        control=sql(restored/'paper_plane.sqlite',"SELECT entries_paused FROM bot_instances")
        assert control and control[0]['entries_paused']==1
        command('resume',target=restored,bot_instance_id=bot,idempotency_key='COLD-FINAL-RESUME')
        command('drain',target=restored,bot_instance_id=bot,idempotency_key='COLD-FINAL-DRAIN')
    finally: restored_holder.close()
    exit_started=time.perf_counter()
    with redirect_stdout(out),redirect_stderr(out): case.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
    exit_elapsed=round(time.perf_counter()-exit_started,6)
    command('run',target=restored,ticks=1,as_of='2026-10-05T13:10:00Z')
    final=command('readback',target=restored)
    assert [p['state'] for p in final['positions']]==['RECONCILED']
    assert len(final['modeled_attempts'])==len(final['modeled_results'])==2
    assert len({r['payload']['attempt_id'] for r in final['modeled_attempts']})==2
    assert config_before==sql(restored/'paper_plane.sqlite',"SELECT event_id,event_type,payload_json FROM execution_events WHERE event_type IN ('OPERATING_ENVELOPE_ACCEPTED','TRADING_RUNTIME_POLICY_ACCEPTED') ORDER BY event_id")
    shadow=json.loads(json.dumps(profile));shadow['mode']=shadow['envelope']['mode']='SHADOW'
    shadow['quote']['asset_metadata_file']=None
    save(donor/'shadow-profile.json',shadow)
    missing=command('check',mode='SHADOW',strategy=case.strategy_rel,profile='shadow-profile.json',as_of=at,format='human',expected=2)
    assert 'FUNDING' in missing or 'funding' in missing
    save(case.source.data_root/'funding.json',{'mint':profile['quote']['funding_mint'],'decimals':9,
        'unit_price_usd':'100','observed_at':at,'available_at':at})
    configured=command('check',mode='SHADOW',strategy=case.strategy_rel,profile='shadow-profile.json',as_of=at)
    assert configured['activation_created'] is False
    command('check',mode='SHADOW',strategy=case.strategy_rel,profile='shadow-profile.json',as_of='2026-10-05T13:10:00Z',format='human',expected=2)
    invalid=json.loads(json.dumps(profile));invalid['envelope'].pop('max_outstanding_positions');invalid['envelope'].pop('max_outstanding_cost_basis_usd')
    save(donor/'bad-envelope-profile.json',invalid)
    command('check',strategy=case.strategy_rel,profile='bad-envelope-profile.json',as_of=at,format='human',expected=2)
    assert len(steps)==24 and len(canaries)==5 and before==pins()
except Exception as error:
    negative={'schema':'smial.native-cli-helper-negative','status':'FAIL','error_type':type(error).__name__,
        'completed_command_count':len(steps),'completed_commands':[r['command'] for r in steps],
        'source_pins':before,'provider_calls':False,'credential_reads':False}
    raise
finally:
    case.tearDown()
    if 'negative' in locals():
        negative['owned_fixture_absent']=not owned.exists();negative['receipt_sha256']=sha256_of(negative)
        save(output.parent/'operator-helper-negative.json',negative)
assert not owned.exists()
body={'schema':'smial.independent-ordinary-cli-proof','schema_version':'1.0','task_id':'SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1',
    'journey_status':'PASS','role':'ROOT_NATIVE_PROOF_NOT_CRITIC_VERDICT','total_command_count':24,
    'base_journey_command_count':22,'additional_drain_control_command_count':1,'additional_readonly_configuration_diagnostic_count':1,
    'steps':steps,'elapsed_seconds':round(time.perf_counter()-start,6),'cli_elapsed_seconds':round(sum(r['elapsed_seconds'] for r in steps),6),
    'fixture_preparation_elapsed_seconds':prep_elapsed,'source_exit_producer_elapsed_seconds':exit_elapsed,
    'fixture_stdout_sha256':sha(out.getvalue().encode('utf8')),'manual_trade_stage_calls':0,'manual_binding_construction':False,
    'manual_token_json':False,'source_exit_producer_prepared_natively':True,'final_state':'RECONCILED_STOPPED',
    'no_entry_resend_verified':True,'ack_pause_value':1,'ack_pause_value_type':'SQLITE_INTEGER','explicit_resume_executed':True,
    'readonly_canaries':canaries,'readonly_status_canary_count':5,'readonly_status_canaries_verified':True,
    'configuration_recovery':{'original_policy_envelope_events_exact':True,'post_backup_configuration_extension_exercised':False},
    'external_cut_basis':'EMPTY_INDEPENDENT_EFFECT_LEDGER_NO_POST_BACKUP_EFFECTS_CALLER_ASSERTED_COMPLETE',
    'identities':{'activation_epoch_id':case.epoch,'position_id':pid,'bot_instance_id':bot,'inventory_sha256':inventory,
        'cut_sha256':sealed['cut_sha256'],'attempt_ids':[r['payload']['attempt_id'] for r in final['modeled_attempts']],
        'backup_database_sha256':backup_sha},
    'source_pins_before':before,'source_pins_after':pins(),'source_pins_unchanged':True,
    'semantic_navigation':{'status':'PENDING_FINAL_DOCS_CATALOG_NATIVE_READBACK'},
    'cleanup':{'owned_root_absent':not owned.exists(),'native_fixture_root_absent':not owned.exists()},
    'provider_calls':False,'credential_reads':False,'live_authority':False,'evidence_class':'SYNTHETIC_OFFLINE'}
body['reproducer_sha256']=sha(Path(__file__).read_bytes())
body['reproducer_ref']=Path(__file__).relative_to(root).as_posix()
body['receipt_sha256']=sha256_of(body);save(output,body)
print(json.dumps({'status':'PASS','commands':24,'readonly_canaries':5,'elapsed_seconds':body['elapsed_seconds'],'owned_fixture_absent':True}))
