"""Three cold, measured production CLI paths per distinct-HYP archive size.

Instrumentation delegates every integrity check; it never changes a verdict.
Scripted scientific cards are engineering controls, outside native grading.
"""
from __future__ import annotations
import contextlib, ctypes, importlib.util, io, json, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.run_passport import canonical_json_bytes
from tests import test_forge_research_flow_reliability_v1 as flow
from tests.test_forge_evidence_guided_generation_v1 import seed_history
HOME=ROOT/'local/forge_evidence_guided_generation_v1/growth'

def rss():
    if os.name!='nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('pagefaults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
    c=Counters();c.cb=ctypes.sizeof(c)
    process=ctypes.windll.kernel32.GetCurrentProcess
    process.restype=ctypes.c_void_p
    get=ctypes.windll.psapi.GetProcessMemoryInfo
    get.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    if not get(process(),ctypes.byref(c),c.cb):raise OSError('RSS_UNAVAILABLE')
    return int(c.peak_working)

def child(count,rep):
    attempt=1
    while (HOME/f'{count}-{rep}-attempt{attempt}').exists():attempt+=1
    work=HOME/f'{count}-{rep}-attempt{attempt}';work.mkdir(parents=True,exist_ok=False)
    plane=work/'plane';shutil.copytree(HOME/f'source-{count}',plane)
    ResearchStore(plane).prepare_write_lookup()
    spec=importlib.util.spec_from_file_location('public_forge',ROOT/'scripts/hypothesis_forge.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    original=ResearchStore._verify_partition
    physical=[];stages=[]
    def verified(store,manifest):
        result=original(store,manifest)
        physical.append((manifest.partition_manifest_id,len(result),int((store._root/manifest.logical_location).stat().st_size)))
        return result
    ResearchStore._verify_partition=verified
    h=flow.EpisodeFlowTests();h.work=work;h.plane=plane
    def call(*args,ok=True):
        start=time.perf_counter();n=len(physical);out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=cli.main(['--root',str(ROOT),'--data-root',str(plane),*[str(a) for a in args]])
        value=json.loads(out.getvalue()) if out.getvalue().strip() else {'status':'CLI_REFUSAL','reason_code':err.getvalue().strip()}
        opened=physical[n:]
        stages.append({'command':str(args[0]),'seconds':time.perf_counter()-start,'exit_code':code,'physical_partition_reads':len(opened),'physical_record_decodes':sum(r[1] for r in opened),'physical_bytes':sum(r[2] for r in opened),'serialized_output_bytes':len(canonical_json_bytes(value)),'peak_rss_bytes':rss(),'reason_code':value.get('reason_code')})
        if ok and code:raise AssertionError({'command':args[0],'reason_code':value.get('reason_code')})
        return value
    h.cli=call
    start=time.perf_counter()
    evidence,scope,_,initial=h.look(f'EGG_GROWTH_{count}_{rep}')
    body,pre=h.authored_draft(evidence,scope,initial['owner_focus'])
    view=pre['forge_context_packet']['prior_memory_working_view']
    call('prior','--context-view','--preflight-receipt',h.write('detail-pre.json',pre),'--selection-query-sha256',view['selection_query_sha256'],'--source-ref',f'HYP-EGG-{count-1:05d}')
    _,frozen=h.persist_and_freeze(body,pre)
    packet=frozen['critic_input_packet']
    row={'distinct_eligible_heads':count,'cold_process':rep,'pid':os.getpid(),'mode':'SCRIPTED_SYNTHETIC_PUBLIC_CLI','native_quality_numerator':False,'capability_epoch_sha256':pre['capability_epoch_sha256'],'seconds_total':time.perf_counter()-start,'initial_count':len(view['capsules']),'archive_eligible_count':packet['prior_memory']['archive_eligible_count'],'critic_capsules':len(packet['prior_memory']['capsules']),'critic_packet_bytes':len(canonical_json_bytes(packet)),'full_safety_count':packet['generation_context']['safety_receipt']['considered_count'],'peak_rss_bytes':rss(),'stages':stages,'terminal':frozen['session_state']}
    assert row['initial_count']<=8 and row['critic_capsules']<=64 and row['critic_packet_bytes']<=65536
    # The imported/commissioned source may itself contain an eligible prior.
    # Count it honestly rather than deleting it to force a round denominator.
    assert row['archive_eligible_count']>=count and row['full_safety_count']==row['archive_eligible_count']
    (work/'metrics_receipt.json').write_text(json.dumps(row,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k!='stages'}),flush=True)

def parent():
    HOME.mkdir(parents=True,exist_ok=True)
    from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo
    capability, _ = compute_capability_epoch_for_repo(ROOT)
    template=ROOT/'local/forge_evidence_guided_generation_v1/source-base/plane'
    for count in (40,400,4000):
        source=HOME/f'source-{count}'
        if not source.exists():
            shutil.copytree(template,source);store=ResearchStore(source);store.prepare_write_lookup();seed_history(store,count)
        for rep in range(1,4):
            if any(json.loads(p.read_text(encoding='utf-8')).get('capability_epoch_sha256')==capability
                   for p in HOME.glob(f'{count}-{rep}-attempt*/metrics_receipt.json')):continue
            done=subprocess.run([sys.executable,'-B',str(Path(__file__)),str(count),str(rep)],cwd=ROOT,env={**os.environ,'PYTHONUTF8':'1'},text=True,encoding='utf-8',capture_output=True)
            print(done.stdout,flush=True)
            if done.returncode:
                (HOME/f'failure-{count}-{rep}.txt').write_text(done.stderr,encoding='utf-8')
                raise AssertionError({'count':count,'rep':rep,'reason':'COLD_PATH_FAILED','stderr_tail':done.stderr[-300:]})
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(HOME.glob('*-*/metrics_receipt.json'))]
    rows=[r for r in rows if r.get('capability_epoch_sha256')==capability]
    (HOME/'summary.json').write_text(json.dumps(rows,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('GROWTH_COLD_PATHS_PASS',len(rows))

if __name__=='__main__':
    child(int(sys.argv[1]),int(sys.argv[2])) if len(sys.argv)==3 else parent()
