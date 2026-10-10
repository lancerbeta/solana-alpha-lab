"""Executor-only negative probes of quiescent actual frozen native state."""
import argparse, hashlib, json, os, shutil, subprocess, sys
from dataclasses import asdict
from pathlib import Path

p=argparse.ArgumentParser()
for name in ('eval','source','out','freeze','critic','snapshot'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
assert not a.out.exists(), 'FRESH_PROBE_LOCATION_REQUIRED'
a.out.mkdir(parents=True)
code=a.out/'evaluation';plane=a.out/'plane'
shutil.copytree(a.eval,code,ignore=shutil.ignore_patterns('.venv','__pycache__'))
shutil.copytree(a.source,plane)
sys.path.insert(0,str(code/'src'))
from solana_alpha_lab.factory.git_write_fence import repository_git_snapshot
from solana_alpha_lab.factory.research_store import ResearchStore
expected=json.loads(a.snapshot.read_text(encoding='utf-8'))
assert asdict(repository_git_snapshot(code))==expected,'COPIED_CODE_IDENTITY_MISMATCH'
frozen=json.loads(a.freeze.read_text(encoding='utf-8-sig'))
session=frozen['session_id']
env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONPATH':str(code/'src'),'SMIAL_DATA_ROOT':str(plane)}
base=[sys.executable,'-B',str(code/'scripts/hypothesis_forge.py'),'--root',str(code),'--data-root',str(plane)]
def inventory():
    return {r.record_id:r.payload_sha256 for r in ResearchStore(plane).iter_committed_records()}
initial=inventory()
def call(name,args,reason=None):
    r=subprocess.run([*base,*args],cwd=code,env=env,capture_output=True,timeout=240)
    (a.out/(name+'.stdout.json')).write_bytes(r.stdout)
    (a.out/(name+'.stderr.txt')).write_bytes(r.stderr)
    if reason:
        assert r.returncode!=0,(name,'UNEXPECTED_SUCCESS')
        assert reason in (r.stdout+r.stderr).decode('utf-8'),(name,r.stdout,r.stderr)
        assert inventory()==initial,(name,'LOGICAL_STORE_CHANGED')
    else: assert r.returncode==0,(name,r.stdout,r.stderr)
    return r
prepare=subprocess.run([sys.executable,'-B',str(code/'scripts/prepare_research_write_lookup.py'),'--data-root',str(plane),'--isolated-copy'],cwd=code,env=env,capture_output=True,timeout=240)
(a.out/'copy-lookup-preparation.stdout.json').write_bytes(prepare.stdout)
assert prepare.returncode==0 and inventory()==initial
args=['finalize','--session-id',session,'--critic-result',str(a.critic),'--format','json']
before=json.loads(call('before','show-session --session-id'.split()+[session,'--format','json']).stdout)
assert before['session_state']=='FROZEN_AWAITING_CRITIC'
marker=code/'AGENTS.md';raw=marker.read_bytes()
try:
    marker.write_bytes(raw+b'\n<!-- EXECUTOR_ONLY_CONTEXT_DRIFT_PROBE -->\n')
    call('changed-code-refusal',args,'GIT_COMPOSITE_CHANGED')
finally: marker.write_bytes(raw)
assert asdict(repository_git_snapshot(code))==expected
context=plane/'research/artifacts/forge_context'/(frozen['forge_context_packet_sha256']+'.json')
context_raw=context.read_bytes()
context_hash=hashlib.sha256(context_raw).hexdigest()
backup=context.with_suffix('.probe-backup')
try:
    context.rename(backup)
    call('missing-context-refusal',args,'FORGE_CONTEXT_ARTIFACT_MISSING')
finally: backup.rename(context)
try:
    context.write_bytes(b'{}\n')
    call('corrupt-context-refusal',args,'FORGE_CONTEXT_HASH_MISMATCH')
finally: context.write_bytes(context_raw)
bad=json.loads(a.critic.read_text(encoding='utf-8-sig'))
bad['selected_definition_sha256']='0'*64
badfile=a.out/'wrong-definition-test-only.json'
badfile.write_text(json.dumps(bad)+'\n',encoding='utf-8')
call('wrong-definition-refusal',['finalize','--session-id',session,'--critic-result',str(badfile),'--format','json'],'CRITIC_DEFINITION_HASH_MISMATCH')
after=json.loads(call('restored-fresh-state','show-session --session-id'.split()+[session,'--format','json']).stdout)
assert after['session_state']==before['session_state'] and after['critic_input_packet_sha256']==before['critic_input_packet_sha256']
assert inventory()==initial
assert hashlib.sha256(context.read_bytes()).hexdigest()==context_hash
assert asdict(repository_git_snapshot(a.eval))==expected
proof={'status':'PASS','scope':'ACTUAL_FROZEN_NATIVE_ARTIFACTS_DISPOSABLE_COPY','session_id':session,'checks':['GIT_COMPOSITE_CHANGED','FORGE_CONTEXT_ARTIFACT_MISSING','FORGE_CONTEXT_HASH_MISMATCH','CRITIC_DEFINITION_HASH_MISMATCH'],'logical_store_changes':0,'new_main':0,'new_preview':0,'new_generator':0,'new_critic':0,'original_context_restored_exactly':True,'original_execution_snapshot_unchanged':True,'copied_state_before':before['session_state'],'copied_state_after':after['session_state'],'git_composite_sha256':expected['composite_sha256']}
(a.out/'proof.json').write_bytes((json.dumps(proof,indent=2)+'\n').encode())
print(json.dumps(proof))
