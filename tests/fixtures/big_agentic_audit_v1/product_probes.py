"""Independent bounded store/recovery/read-model probes. No product fixes/mocks."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path[:0] = ['/repo', '/repo/src', '/kit']
from safety_preflight import check
from oracles import grade_wal
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from tests.test_research_store import event_fixture


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def wal_probe(root: Path):
    """Allowed schedule: checkpoint initial state, commit new state, keep writer open."""
    import shutil
    root.mkdir(parents=True)
    (root/'catalog').mkdir()
    shutil.copytree('/repo/catalog/schemas', root/'catalog/schemas')
    (root/'configs').mkdir()
    shutil.copy('/repo/configs/owner_lifecycle_projection_v1.yaml',root/'configs/owner_lifecycle_projection_v1.yaml')
    (root/'configs/factory_v1_product_kernel_v1.yaml').write_text('operational_store:\n  relative_path: ops.sqlite\n')
    path=root/'ops.sqlite'
    writer=OperationalStore(path)
    job={'job_id':'JOB-BAA-WAL-001','experiment_id':'EXP-BAA-WAL-001',
         'spec_relative':'configs/experiment_specs/BAA.yaml','spec_sha256':'a'*64,
         'status':'RUNNING','blocker':'','terminal':None,'evidence':{}}
    writer.upsert_job(job)
    writer._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    writer.upsert_job({**job,'status':'COMPLETE','terminal':'BAA_CONTROLLED_TERMINAL'})
    # Independent SQLite path observes committed truth while writer remains alive.
    reference=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    expected=reference.execute('SELECT status FROM jobs WHERE job_id=?',(job['job_id'],)).fetchone()[0]
    reference.close()
    before=inventory(root)
    reader=OperationalStore(path,readonly=True)
    observed=reader.get_job(job['job_id'])
    reader.close()
    projection=build_lifecycle_projection(root,projected_at='2026-10-10T12:00:00Z')
    entity=next((e for e in projection['entities'] if e['entity_id']==job['job_id']),None)
    after=inventory(root)
    proof={'id':'D07-WAL-COMMITTED-VIEW','fidelity':'SEGMENT_PRODUCT_PATH',
           'expected':expected,'operational_store_actual':observed['status'] if observed else None,
           'lifecycle_projection_actual':entity['native_state'] if entity else None,
           'read_only_physical_inventory_unchanged':before==after,
           'writer_alive_during_reads':True,'wal_bytes':Path(str(path)+'-wal').stat().st_size,
           'source_semantics':'OperationalStore owns current jobs; LifecycleProjection is derived current readback',
           'schedule':['initial RUNNING commit','checkpoint initial state','COMPLETE commit',
                       'independent mode=ro SELECT','public readonly store read','public lifecycle projection'],
           'before_inventory':before,'after_inventory':after}
    proof['status']=grade_wal(proof)
    writer.close()
    cold=OperationalStore(path,readonly=True)
    proof['after_writer_close_actual']=cold.get_job(job['job_id'])['status']
    cold.close()
    return proof


def crash_probes(root):
    root.mkdir(parents=True)
    child="""import os,sys
sys.path[:0]=['/repo','/repo/src']
from pathlib import Path
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_research_store import event_fixture
e=event_fixture(record_id='BAA-POSTAPPEND',transaction_id='RESEARCH-TXN-BAA-POSTAPPEND')
ResearchStore(Path(sys.argv[1])).append([e],transaction_id=e.transaction_id)
os._exit(73)
"""
    landed=root/'landed'
    run=subprocess.run([sys.executable,'-B','-c',child,str(landed)],capture_output=True,timeout=45)
    if run.returncode!=73:
        raise RuntimeError('CRASH_CONTROL_DID_NOT_REACH_POSTAPPEND')
    store=ResearchStore(landed,create_if_missing=False)
    actual=list(store.iter_committed_records())
    before=store.diagnostics().committed_inventory_sha256
    e=event_fixture(record_id='BAA-POSTAPPEND',transaction_id='RESEARCH-TXN-BAA-POSTAPPEND')
    with store.writer_lease():
        try:
            ResearchStore(landed).append([e],transaction_id=e.transaction_id)
        except ResearchStoreError as exc:
            busy=exc.code
        else:
            busy='NOT_REFUSED'
    store.append([e],transaction_id=e.transaction_id)
    after=store.diagnostics().committed_inventory_sha256
    landing={'id':'D02-POSTAPPEND-REPEAT-SECOND-WRITER','fidelity':'SEGMENT_PRODUCT_PATH',
             'child_exit':run.returncode,'records_after_crash':[r.record_id for r in actual],
             'writer_conflict':busy,'repeat_inventory_unchanged':before==after,
             'inventory_before':before,'inventory_after':after,
             'status':'PASS' if len(actual)==1 and before==after and busy=='WRITER_BUSY' else 'FAIL',
             'schedule':['owned child durable append','owned child os._exit before ack',
                         'independent committed read','second writer lease conflict','exact replay']}
    # Real scientific reservation survives abrupt child loss; no fabricated result.
    pending=root/'pending'
    reservation="""import os,sys
sys.path[:0]=['/repo','/repo/src']
from pathlib import Path
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.hfic_ordinary_operation import record_operation,gate_before_values
from tests.test_hfic_ordinary_operation_v1 import _simple_spec,_operation,JOURNAL,MARKET
s=ResearchStore(Path(sys.argv[1])); q=_simple_spec()
o=record_operation(s,_operation(q,completion='LIMITED_RESULT',cap_main=1))
gate_before_values(s,operation_sha256=o['operation_sha256'],spec=q,journal_scope=JOURNAL,verified_market=MARKET)
os._exit(73)
"""
    run=subprocess.run([sys.executable,'-B','-c',reservation,str(pending)],capture_output=True,timeout=45)
    if run.returncode!=73:
        raise RuntimeError('RESERVATION_CONTROL_FAILED:'+run.stderr.decode()[-600:])
    from solana_alpha_lab.factory.hfic_ordinary_operation import gate_before_values, journal_occupancy, list_operations
    from tests.test_hfic_ordinary_operation_v1 import _simple_spec,JOURNAL,MARKET
    store=ResearchStore(pending,create_if_missing=False)
    records=list(store.iter_committed_records())
    operation=list_operations(store)[0]
    before=store.diagnostics().committed_inventory_sha256
    budget=journal_occupancy(store,JOURNAL)
    resumed=gate_before_values(store,operation_sha256=operation['operation_sha256'],spec=_simple_spec(),journal_scope=JOURNAL,verified_market=MARKET)
    same=before==store.diagnostics().committed_inventory_sha256
    return [landing,{'id':'D01-RESERVATION-CRASH-RESUME','fidelity':'SEGMENT_PRODUCT_PATH',
         'status':'PASS' if resumed['disposition']=='RESUME' and same else 'FAIL',
         'resume_disposition':resumed['disposition'],'inventory_unchanged':same,
         'budget':budget,'records':[{'id':r.record_id,'kind':str(r.record_kind),'payload':json.loads(r.payload_json)} for r in records],
         'schedule':['real operation admission','reserve before values','owned child abrupt exit',
                     'independent journal read','resume exact reservation']}]


def sequences(root):
    results=[]
    for seed in (4129,6137,9011):
        rng=random.Random(seed)
        for seq in range(8):
            store=ResearchStore(root/f'{seed}-{seq}')
            events={}; actions=[]; assertions=[]
            for step in range(12):
                action=rng.choice(['append','append','replay','conflict','readonly'])
                if not events: action='append'
                before=store.diagnostics().committed_inventory_sha256
                if action=='append':
                    e=event_fixture(record_id=f'BAA-SEQ-{seed}-{seq}-{step}',transaction_id=f'RESEARCH-TXN-BAA-{seed}-{seq}-{step}')
                    store.append([e],transaction_id=e.transaction_id); events[e.record_id]=e
                elif action=='replay':
                    e=rng.choice(list(events.values()));store.append([e],transaction_id=e.transaction_id)
                    assertions.append(store.diagnostics().committed_inventory_sha256==before)
                elif action=='conflict':
                    e=rng.choice(list(events.values()))
                    forged=e.model_copy(update={'payload_sha256':'0'*64})
                    try:store.append([forged],transaction_id=e.transaction_id)
                    except ResearchStoreError: refused=True
                    else:refused=False
                    assertions.append(refused and store.diagnostics().committed_inventory_sha256==before)
                else:
                    list(ResearchStore(store._root,create_if_missing=False).iter_committed_records())
                    assertions.append(store.diagnostics().committed_inventory_sha256==before)
                actual=list(store.iter_committed_records())
                assertions.append({r.record_id for r in actual}==set(events))
                assertions.extend(hashlib.sha256(r.payload_json.encode()).hexdigest()==r.payload_sha256 for r in actual)
                actions.append(action)
            results.append({'id':f'SEQ-{seed}-{seq}','seed':seed,'actions':actions,
                            'record_ids':sorted(events),'checks_n':len(assertions),
                            'status':'PASS' if all(assertions) else 'FAIL','fidelity':'SEGMENT_PRODUCT_PATH'})
    return results


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if not check()['pass']: raise SystemExit('CONTAINMENT_FAIL')
    args.output.mkdir(parents=True)
    proofs=[]
    def retain(items):
        with (args.output/'probe-ledger.jsonl').open('a',encoding='utf-8') as ledger:
            for item in items:
                proofs.append(item)
                ledger.write(json.dumps(item,default=str)+'\n');ledger.flush()
    retain([wal_probe(args.output/'wal')])
    if args.phase != 'wal':
        retain(crash_probes(args.output/'crash'))
        retain(sequences(args.output/'sequences'))
    result={'schema':'baa.product-probes.v1','base_commit':'90ba76e37515b3d521478a6d05a149fb0f1d2b75',
            'proofs':proofs,'product_mutations':False,'llm_behavior_tested':False,
            'bounded_generated_sequences':0 if args.phase == 'wal' else 24,'steps_per_sequence':12}
    (args.output/'probes-summary.json').write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps({'proofs':len(proofs),'failures':[r['id'] for r in proofs if r['status']=='FAIL']}))
    return 1 if any(r['status']=='FAIL' for r in proofs) else 0


if __name__=='__main__':raise SystemExit(main())
