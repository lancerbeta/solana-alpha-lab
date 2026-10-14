"""Owned faults after an actual READY; never change the saved positive world."""
import shutil
from common import OUT,dump,load
from execution import run,state,clone_plane

def check():
    from tests.test_opportunity_episodes_harness_v1 import write_assignment
    from solana_alpha_lab.factory.hfic_session import load_session_bundle
    from solana_alpha_lab.factory.research_store import ExistingResearchStoreReader
    receipts={}
    for variant in ('source-missing','source-stale','definition-foreign','protection'):
        overlay='negative-'+variant
        plane=OUT/overlay/'plane'
        clone_plane(OUT/'base-v2'/'classified-plane',plane)
        def mutate(root,spec):
            if variant=='source-missing':
                path=root/spec['parameters']['temporal_recipe']['frozen_input'][0]['observations_rel']
                path.rename(path.with_name(path.name+'.retained'))
            elif variant=='source-stale':
                path=root/spec['parameters']['temporal_recipe']['frozen_input'][0]['observations_rel']
                # Exact bytes preserved, altered source retained; hash guard must refuse.
                shutil.copy2(path,path.with_name(path.name+'.original'))
                with path.open('ab') as handle:handle.write(b'OWNED_FAULT')
            elif variant=='definition-foreign':return {'definition_override':'0'*64}
            else:
                import pyarrow.parquet as pq
                item=spec['parameters']['temporal_recipe']['frozen_input'][0]
                mint=pq.read_table(root/item['census_rel'],columns=['mint']).column('mint')[0].as_py()
                write_assignment(root,[{'identity_kind':'MINT','identity':mint,'role':'UNTOUCHED_FORWARD_HOLDOUT','scope':{'kind':'ALL_TIME'}}])
        receipt=run(world='base-v2',overlay=overlay,mutate=mutate)
        assert receipt['response']['status']=='INVALID_EVIDENCE',receipt['response']
        assert receipt['reads']['evaluator_invocations']==0 and receipt['reads']['decoded_target_value_rows']==0
        assert receipt['before']==receipt['after'],'DENIAL_WROTE_BUSINESS_RECORDS'
        receipts[variant]=receipt
    # Historical results remain readable after current protection revocation.
    overlay='negative-protection-completed'
    plane=OUT/overlay/'plane'
    clone_plane(OUT/'base-v2'/'plane',plane)
    from execution import case
    spec,frozen=case('base-v2','LIST_CONTRAST')
    rows=tuple(ExistingResearchStoreReader(plane).iter_committed_records())
    completed_before=state(plane)['completion_ids']
    receipt=run(world='base-v2',overlay=overlay,mutate=mutate)
    assert receipt['response']['status']=='INVALID_EVIDENCE'
    assert state(plane)['completion_ids']==completed_before
    assert receipt['reads']['evaluator_invocations']==0 and receipt['reads']['decoded_target_value_rows']==0
    receipts['historical-protection']=receipt
    dump(OUT/'negative-receipts.json',receipts)
    return {'status':'PASS','cases':list(receipts),'native_guard_refusals':True}
