from __future__ import annotations
import hashlib,json,shutil,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests.test_hfic_research_policy_closure_v1 import _operation,MARKET,GIT
from solana_alpha_lab.factory import hfic_ordinary_operation as oo
from solana_alpha_lab.factory.research_store import ResearchStore,reuse_lifecycle_reads_within_packet

def generate(n):
    target=ROOT/'local'/f'flow-history-{n*4}'
    if (target/'descriptor.json').exists():
        return
    ResearchStore(target)
    chosen=None
    for i in range(n):
        with tempfile.TemporaryDirectory() as temp:
            shard=Path(temp);store=ResearchStore(shard)
            journal=hashlib.sha256(f'flow-resource-journal-{i}'.encode()).hexdigest()
            descriptor=hashlib.sha256(f'flow-resource-preview-{i}'.encode()).hexdigest()
            op=_operation(store,journal=journal,text=f'flow-resource-{i}',owner_cap={'main':None,'adaptive':None,'preview':1})
            oo.authorize_episode_view(store,operation_sha256=op['operation_sha256'],journal_scope=journal,descriptor_sha256=descriptor,verified_market=MARKET)
            oo.land_episode_view(store,operation_sha256=op['operation_sha256'],journal_scope=journal,descriptor_sha256=descriptor,payload_sha256='e5'*32,git_sha=GIT)
            assert len(list(store.iter_committed_records()))==4
            for directory in ('events','manifests'):
                shutil.copytree(shard/'research'/directory,target/'research'/directory,dirs_exist_ok=True)
            if chosen is None:
                chosen={'operation':op['operation_sha256'],'journal':journal}
    chosen['records']=n*4
    (target/'descriptor.json').write_text(json.dumps(chosen),encoding='utf-8')
    assert len(list(ResearchStore(target).iter_committed_records()))==n*4
    print(json.dumps({'created_records':n*4}),flush=True)

def measure(records,mode):
    target=ROOT/'local'/f'flow-history-{records}';desc=json.loads((target/'descriptor.json').read_text())
    counts={'full_history_calls':0,'yielded_rows':0,'partition_verifications':0}
    old_iter=ResearchStore.iter_committed_records;old_verify=ResearchStore._verify_partition
    def counted_iter(self):
        counts['full_history_calls']+=1
        for row in old_iter(self):
            counts['yielded_rows']+=1;yield row
    def counted_verify(self,manifest):
        counts['partition_verifications']+=1
        return old_verify(self,manifest)
    ResearchStore.iter_committed_records=counted_iter;ResearchStore._verify_partition=counted_verify
    def read():
        store=ResearchStore(target,create_if_missing=False)
        operation=oo.get_operation(store,desc['operation'])
        occupancy=oo.journal_occupancy(store,desc['journal'])
        allowance=oo.owner_allowance(store,operation,'preview')
        return {'operation':operation,'occupancy':occupancy,'allowance':allowance}
    start=time.perf_counter()
    result=reuse_lifecycle_reads_within_packet(read)() if mode=='scoped' else read()
    elapsed=time.perf_counter()-start
    canonical=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    print(json.dumps({'mode':mode,'records':records,'read_wall_seconds':elapsed,**counts,'result_sha256':hashlib.sha256(canonical).hexdigest()}),flush=True)

if sys.argv[1]=='generate':
    generate(10);generate(100)
else:
    measure(int(sys.argv[1]),sys.argv[2])
