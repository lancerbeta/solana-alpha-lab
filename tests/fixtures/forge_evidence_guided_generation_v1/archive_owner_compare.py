"""Cold unchanged-legacy versus new working-owner costs, not whole BASE CLI."""
from __future__ import annotations
import collections,hashlib,importlib.util,json,os,subprocess,sys,time
from datetime import UTC,datetime
from pathlib import Path
ROOT=Path.cwd();HOME=ROOT/'local/forge_evidence_guided_generation_v1';sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from solana_alpha_lab.factory.research_store import ResearchStore,reuse_lifecycle_reads_within_packet
from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot,PriorMemoryCapacityError
from solana_alpha_lab.factory.hfic_generation_context import collect_verified_priors,select_working_snapshot
from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo
from solana_alpha_lab.factory.run_passport import canonical_json_bytes
spec=importlib.util.spec_from_file_location('growth_rss',ROOT/'tests/fixtures/forge_evidence_guided_generation_v1/growth_probe.py');growth=importlib.util.module_from_spec(spec);spec.loader.exec_module(growth)
BASE='fb65d69f6e48c49b26937bb6caf324b3417b094e'
def measure(count,rep,arm,cutoff):
    source=HOME/'growth'/f'source-{count}';store=ResearchStore(source,create_if_missing=False)
    before=store.diagnostics().committed_inventory_sha256;opened=[];real=ResearchStore._verify_partition
    def verified(owner,manifest):
        value=real(owner,manifest);opened.append((manifest.partition_manifest_id,len(value),(owner._root/manifest.logical_location).stat().st_size));return value
    ResearchStore._verify_partition=verified
    @reuse_lifecycle_reads_within_packet
    def request():
        if arm=='BASE_LEGACY_OWNER':
            try:
                value=build_prior_memory_snapshot(store,store_inventory_digest=before,repo_root=ROOT,as_of=cutoff)
                return {'status':'SNAPSHOT','eligible':value['eligible_count'],'emitted':len(value['capsules']),'packet_bytes':len(canonical_json_bytes(value))}
            except PriorMemoryCapacityError as exc:
                return {'status':'REFUSAL','reason_code':exc.code,'eligible':exc.eligible_count,'emitted':exc.emitted_count,'max_records':exc.max_records,'max_bytes':exc.max_bytes}
        archive=collect_verified_priors(store,as_of=cutoff)
        value=select_working_snapshot(archive,query={},inventory_digest=before,max_records=8)
        return {'status':'BOUNDED_WORKING_VIEW','eligible':value['archive_eligible_count'],'emitted':len(value['capsules']),'packet_bytes':len(canonical_json_bytes(value))}
    start=time.perf_counter();value=request();seconds=time.perf_counter()-start
    ResearchStore._verify_partition=real
    after=store.diagnostics().committed_inventory_sha256
    repetitions=collections.Counter(x[0] for x in opened);cap,_=compute_capability_epoch_for_repo(ROOT)
    row={'mode':arm,'seeded_heads':count,'cold_process':rep,'pid':os.getpid(),'capability_epoch_sha256':cap,'same_immutable_root':f'growth/source-{count}','cutoff':cutoff,'inventory_before':before,'inventory_after':after,'inventory_unchanged':before==after,'timing_boundary':'One fresh verified-read scope plus production legacy snapshot/refusal or production verified collection/selection; excludes imports, diagnostics and process launch; separate process per arm','seconds':seconds,'physical_partition_reads':len(opened),'physical_record_decodes':sum(x[1] for x in opened),'bytes_hashed':sum(x[2] for x in opened),'distinct_physical_partitions':len(repetitions),'max_partition_verifications_in_one_scope':max(repetitions.values(),default=0),'peak_rss_bytes':growth.rss(),'result':value,'new_looks':0,'writes':0}
    assert before==after and max(repetitions.values(),default=0)<=1
    out=HOME/'archive-owner-cost';out.mkdir(exist_ok=True);(out/f'{count}-{rep}-{arm}.json').write_text(json.dumps(row,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(row),flush=True)
def parent():
    cutoff=datetime.now(UTC).isoformat();owners=[]
    for name in ['hfic_prior_memory.py','hfic_memory_policy.py','research_store.py']:
        p='src/solana_alpha_lab/factory/'+name
        old=subprocess.check_output(['git','show',BASE+':'+p],cwd=ROOT);now=subprocess.check_output(['git','show','HEAD:'+p],cwd=ROOT)
        assert old==now
        owners.append({'path':p,'base_blob_sha256':hashlib.sha256(old).hexdigest(),'current_blob_sha256':hashlib.sha256(now).hexdigest(),'git_blob_bytes_equal':True,'current_disk_sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()})
    rows=[]
    for count in [40,400,4000]:
        for rep in [1,2,3]:
            for arm in ['BASE_LEGACY_OWNER','CANDIDATE_WORKING_OWNER']:
                r=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),str(count),str(rep),arm,cutoff],cwd=ROOT,capture_output=True)
                if r.returncode:
                    sys.stdout.buffer.write(r.stdout+r.stderr);raise SystemExit(r.returncode)
                rows.append(json.loads(r.stdout))
    value={'schema':'smial.egg-cold-archive-owner-comparison','source_base_commit':BASE,'immutable_owner_bindings':owners,'actual_processes':18,'processes_per_arm_and_size':3,'rows':rows,'not_whole_baseline_generation_latency':True,'not_successful_gt64_baseline':True,'candidate_public_whole_path':'growth/summary.json','model_tokens_cost':'NOT_APPLICABLE_SCRIPTED_READ_ONLY','limits':['COLD_PROCESS_NOT_COLD_OS_CACHE','Source setup/diagnostics/imports excluded from timer','Legacy owner unchanged from base; candidate owner current; no whole frozen BASE CLI latency claim']}
    (HOME/'archive-owner-cost/summary.json').write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'processes':18,'summary_sha256':hashlib.sha256((HOME/'archive-owner-cost/summary.json').read_bytes()).hexdigest(),'max_rss':max(x['peak_rss_bytes'] for x in rows)}))
if __name__=='__main__':
    measure(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],sys.argv[4]) if len(sys.argv)==5 else parent()
