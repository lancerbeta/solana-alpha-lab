"""Replay original native artifacts after an OS reply-loss boundary; no model/look."""
import argparse, hashlib, json, os, shutil, subprocess, sys
from dataclasses import asdict
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--eval', type=Path, required=True)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--session', required=True)
p.add_argument('--critic', type=Path, required=True)
p.add_argument('--snapshot', type=Path, required=True)
p.add_argument('--operation', required=True)
p.add_argument('--resume-uncommitted-probe', action='store_true')
p.add_argument('--experiment-spec', type=Path)
a=p.parse_args()
sys.path.insert(0,str(a.eval/'src'))
from solana_alpha_lab.factory.git_write_fence import repository_git_snapshot
from solana_alpha_lab.factory.research_store import ResearchStore
original_snapshot=json.loads(a.snapshot.read_text(encoding='utf-8-sig'))
assert asdict(repository_git_snapshot(a.eval)) == original_snapshot, 'EXECUTION_SNAPSHOT_CHANGED'
plane=a.out/'plane'
if a.resume_uncommitted_probe:
    assert plane.is_dir(), 'EXISTING_DISPOSABLE_COPY_REQUIRED'
else:
    assert not a.out.exists(), 'FRESH_RECOVERY_LOCATION_REQUIRED'
    a.out.mkdir(parents=True)
    shutil.copytree(a.source,plane)
critic_sha=hashlib.sha256(a.critic.read_bytes()).hexdigest()
env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONPATH':str(a.eval/'src'),'SMIAL_DATA_ROOT':str(plane)}
base=[sys.executable,'-B',str(a.eval/'scripts/hypothesis_forge.py'),'--root',str(a.eval),'--data-root',str(plane)]
def call(name,*args):
    result=subprocess.run([*base,*args],cwd=a.eval,env=env,capture_output=True,timeout=240)
    (a.out/(name+'.stdout.json')).write_bytes(result.stdout)
    (a.out/(name+'.stderr.txt')).write_bytes(result.stderr)
    assert result.returncode==0,(name,result.returncode,result.stdout[:300])
    return json.loads(result.stdout)
def inventory():
    records=list(ResearchStore(plane).iter_committed_records())
    return {r.record_id:(r.record_kind,r.payload_sha256) for r in records}
before=call('prepared-before-restart','show-session','--session-id',a.session,'--format','json')
initial=inventory()
prepare=subprocess.run([sys.executable,'-B',str(a.eval/'scripts/prepare_research_write_lookup.py'),'--data-root',str(plane),'--isolated-copy'],cwd=a.eval,env=env,capture_output=True,timeout=240)
(a.out/'explicit-isolated-copy-preparation.stdout.json').write_bytes(prepare.stdout)
(a.out/'explicit-isolated-copy-preparation.stderr.txt').write_bytes(prepare.stderr)
assert prepare.returncode==0, 'COPY_LOOKUP_PREPARATION_FAILED'
assert inventory()==initial, 'DERIVED_PREPARATION_CHANGED_LOGICAL_RECORDS'
initial_policy=call('policy-before','research-policy-status','--for-operation',a.operation,'--format','json')
assert before['session_state'] != 'SYNTHESIS_COMPLETE', before['session_state']
critic_body=json.loads(a.critic.read_text(encoding='utf-8-sig'))
if critic_body['critic_terminal']=='PASS_TO_CLASSIFICATION':
    assert a.experiment_spec is not None,'BOUND_EXPERIMENT_SPEC_REQUIRED'
    awaiting=call('prepare-offline-classification','finalize','--session-id',a.session,'--critic-result',str(a.critic),'--format','json')
    assert awaiting['session_state']=='AWAITING_CLASSIFICATION'
    call('offline-classifier','classify','--session-id',a.session,'--experiment-spec',str(a.experiment_spec),'--format','json')
    initial=inventory()

# Wrapper receives child success then exits before exposing the response to caller.
crash_code="import os,pathlib,subprocess,sys; r=subprocess.run(sys.argv[2:],capture_output=True); p=pathlib.Path(sys.argv[1]); (p/'fault-child.stdout.json').write_bytes(r.stdout); (p/'fault-child.stderr.txt').write_bytes(r.stderr); os._exit(73 if r.returncode==0 else 74)"
lost=subprocess.run([sys.executable,'-B','-c',crash_code,str(a.out),*base,'finalize','--session-id',a.session,'--critic-result',str(a.critic),'--format','json'],cwd=a.eval,env=env,capture_output=True,timeout=240)
assert lost.returncode==73,(lost.returncode,lost.stderr[:300])
assert lost.stdout==b''
committed=inventory()
readback=call('after-reply-loss','show-session','--session-id',a.session,'--format','json')
assert readback['session_state']=='SYNTHESIS_COMPLETE',readback['session_state']
retry=call('identical-finalize-retry','finalize','--session-id',a.session,'--critic-result',str(a.critic),'--format','json')
assert retry['session_state']=='SYNTHESIS_COMPLETE'
assert inventory()==committed,'RETRY_ADDED_OR_CHANGED_LOGICAL_RECORDS'
final_policy=call('policy-after','research-policy-status','--for-operation',a.operation,'--format','json')
assert final_policy['occupancy']==initial_policy['occupancy'],'SCIENTIFIC_OCCUPANCY_CHANGED'
assert all(committed.get(k)==v for k,v in initial.items()),'ORIGINAL_RECORD_MUTATED'
different=json.loads(a.critic.read_text(encoding='utf-8-sig'))
different['non_claims'].append('DETERMINISTIC_RECOVERY_CONFLICT_TEST_ONLY')
import jsonschema
schema=json.loads((a.eval/'catalog/schemas/hypothesis_critic_result_v1.schema.json').read_text(encoding='utf-8'))
jsonschema.validate(different,schema)
conflict_file=a.out/'different-result-test-only.json'
conflict_file.write_text(json.dumps(different,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
conflict=subprocess.run([*base,'finalize','--session-id',a.session,'--critic-result',str(conflict_file),'--format','json'],cwd=a.eval,env=env,capture_output=True,timeout=240)
(a.out/'different-result-refusal.stdout.json').write_bytes(conflict.stdout)
(a.out/'different-result-refusal.stderr.txt').write_bytes(conflict.stderr)
assert conflict.returncode!=0,'DIFFERENT_RESULT_ACCEPTED'
if conflict.stdout.strip():
    conflict_body=json.loads(conflict.stdout)
    assert 'SESSION_CONFLICT' in json.dumps(conflict_body),'WRONG_CONFLICT_REFUSAL'
else:
    assert conflict.stderr.decode('utf-8').strip()=='SESSION_CONFLICT','WRONG_CONFLICT_REFUSAL'
    conflict_body={'reason':'SESSION_CONFLICT','channel':'STDERR'}
assert inventory()==committed,'CONFLICT_CHANGED_STORE'
assert hashlib.sha256(a.critic.read_bytes()).hexdigest()==critic_sha,'CRITIC_BYTES_CHANGED'
assert asdict(repository_git_snapshot(a.eval))==original_snapshot,'EXECUTION_SNAPSHOT_CHANGED'
assert len(readback['decision_event_ids'])==1,'DUPLICATE_LOGICAL_TERMINAL'
added={k:v for k,v in committed.items() if k not in initial}
proof={'status':'PASS','scope':'RECOVERY_OF_ORIGINAL_NATIVE_ARTIFACTS_NO_NEW_SCIENTIFIC_INDEPENDENCE','session_id':a.session,'critic_bytes_sha256':critic_sha,'restart_before_finalize':True,'lost_reply_exit':lost.returncode,'lost_reply_stdout_bytes':len(lost.stdout),'fresh_readback_state':readback['session_state'],'critic_terminal':readback['critic_terminal'],'terminal_decision_count':len(readback['decision_event_ids']),'identical_retry_state':retry['session_state'],'different_result_refusal':conflict_body,'different_result_store_changes':0,'retry_added_records':0,'original_records_changed':0,'finalize_added_records':added,'occupancy_before':initial_policy['occupancy'],'occupancy_after':final_policy['occupancy'],'new_generator':0,'new_critic':0,'new_main':0,'new_preview':0,'new_adaptive':0,'same_git_composite':original_snapshot['composite_sha256'],'clone_semantics':'SAME_SAVED_ARTIFACTS_RECOVERY_NOT_INDEPENDENT_SCIENCE'}
(a.out/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
