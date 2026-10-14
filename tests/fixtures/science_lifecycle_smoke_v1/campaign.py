"""Bounded synthetic campaign. Product code stays in the immutable /repo."""
import sys
from common import OUT, charge, dump
from safety import check

def main():
    check()
    from oracle import canaries
    dump(OUT/'oracle-canaries.json',canaries())
    phase=sys.argv[1]
    charge('phase',phase=phase)
    if phase=='safety':
        dump(OUT/'entry.json',{'status':'CONTAINMENT_PASS','new_main':0,'numerical_invocations':0})
    elif phase in ('prepare','prepare-v2'):
        from fixture import prepare
        dump(OUT/(phase+'.json'),prepare('base' if phase=='prepare' else 'base-v2'))
    elif phase=='prepare-changed':
        from fixture import prepare
        dump(OUT/'prepare-changed.json',prepare('changed',negative=True))
    elif phase=='prepare-v3':
        from fixture import prepare
        dump(OUT/'prepare-v3.json',prepare('base-v3',reuse_capture=True))
    elif phase=='classify-v3':
        from execution import classify_world
        dump(OUT/'classified-v3.json',classify_world('base-v3',retain_pre_run=False))
    elif phase=='classify':
        from execution import classify_world
        from probe import confirmation
        dump(OUT/'confirmation-reachability.json',confirmation())
        dump(OUT/'classified.json',classify_world('base-v2'))
    elif phase in ('numeric','replay','numeric-v3','replay-v3','replay-changed'):
        from execution import run
        from oracle import check_summary
        for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
            world='changed' if phase=='replay-changed' else ('base-v3' if phase.endswith('-v3') else 'base-v2')
            receipt=run(world=world,kind=kind)
            response=receipt['response']
            assert response['status']=='COMPLETE' and response['scientific_terminal']=='INCONCLUSIVE',response
            if phase.startswith('numeric'):
                if receipt['entry_lane']=='REPLAY_AVAILABLE':
                    assert receipt['reads']['evaluator_invocations']==0
                    assert receipt['before']==receipt['after']
                    original=__import__('common').load(OUT/world/(kind+'-run.json'))
                    assert original['reads']['evaluator_invocations']==1
                    response=original['response']
                else:
                    assert receipt['reads']['evaluator_invocations']==1
                expected=check_summary(response['capability_result']['summary'],__import__('common').load(OUT/world/'membership-numeric-oracle.json'),kind)
                dump(OUT/world/kind/'numeric-oracle-check.json',expected)
            else:
                assert receipt['reads']['evaluator_invocations']==0 and receipt['reads']['decoded_target_value_rows']==0
                assert receipt['before']==receipt['after'],'REPLAY_BUSINESS_STATE_CHANGED'
    elif phase=='footprint':
        from footprint import measure
        dump(OUT/'volume-footprint.json',measure())
    elif phase=='chronology-oracle':
        from chronology_oracle import build
        dump(OUT/'chronology-geometry.json',build())
    elif phase in ('export-saved','export-saved-v3'):
        from export_saved import export
        dump(OUT/(phase+'.json'),export('base-v3' if phase.endswith('-v3') else 'base-v2'))
    elif phase=='export-sc06':
        from export_saved import export_sc06
        dump(OUT/'export-sc06.json',export_sc06())
    elif phase=='negatives':
        from negatives import check as negative_check
        dump(OUT/'negative-check.json',negative_check())
    elif phase=='missing':
        from execution import run
        (OUT/'missing-check').mkdir()
        receipt=run(world='retained-missing',retained='/missing',overlay='missing-check')
        assert receipt['response']['status']=='INVALID_EVIDENCE',receipt['response']
        assert receipt['reads']['evaluator_invocations']==0 and receipt['reads']['decoded_target_value_rows']==0
        assert receipt['before']==receipt['after']
        dump(OUT/'missing-check.json',{'status':'PASS_EXPECTED_REFUSAL','fidelity':'RETAINED_403_WORLD_MISSING_A7',
            'inherited_fixture_clocks':'PRESERVED; ONLY METADATA/PREFIX REVALIDATION; NO NEW VALUE EXPOSURE',
            'receipt':receipt})
    elif phase in ('consume','consume-cold','consume-finish','consume-v3','consume-cold-v3'):
        from consumption import consume,cold,finish_saved,configure
        action_phase=phase.removesuffix('-v3')
        if phase.endswith('-v3'):configure('base-v3')
        action={'consume':consume,'consume-cold':cold,'consume-finish':finish_saved}[action_phase]
        dump(OUT/(phase+'-summary.json'),action())
    elif phase=='changed':
        from execution import classify_world,run
        from oracle import check_summary
        from common import load
        dump(OUT/'changed-classified.json',classify_world('changed',retain_pre_run=False))
        from sc06_oracle import build
        dump(OUT/'sc06-prefix-oracle.json',build())
        original=load(OUT/'base-v3'/'membership-numeric-oracle.json')
        changed=load(OUT/'changed'/'membership-numeric-oracle.json')
        role_keys=('episode_id','decision_eligible','matched','comparator')
        assert [{k:r[k] for k in role_keys} for r in original]==[{k:r[k] for k in role_keys} for r in changed]
        for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
            receipt=run(world='changed',kind=kind)
            assert receipt['response']['status']=='COMPLETE' and receipt['reads']['evaluator_invocations']==1
            expected=check_summary(receipt['response']['capability_result']['summary'],changed,kind)
            old=load(OUT/'base-v3'/(kind+'-run.json'))['response']['capability_result']
            assert old['result_sha256']!=receipt['response']['capability_result']['result_sha256']
            dump(OUT/'changed'/kind/'numeric-oracle-check.json',expected)
    elif phase.startswith('fault-'):
        import shutil
        from execution import run,state,clone_plane
        mode=phase.removeprefix('fault-')
        overlay='fault-'+mode
        destination=OUT/overlay/'plane'
        if mode in ('before-commit','after-commit'):
            assert not destination.exists(),'FAULT_ATTEMPT_ALREADY_EXISTS'
            clone_plane(OUT/'base-v2'/'classified-plane',destination)
            run(world='base-v2',overlay=overlay,fault=mode)
            raise AssertionError('FAULT_DID_NOT_INTERRUPT')
        else:
            original=mode.removesuffix('-recover')
            if original=='before-commit':
                from solana_alpha_lab.factory.research_store import ResearchStore
                plane=OUT/('fault-'+original)/'plane'
                before=state(plane)
                ResearchStore(plane).prepare_write_lookup()
                assert before==state(plane),'OVERLAY_PREPARATION_CHANGED_COMMITTED_STATE'
            receipt=run(world='base-v2',overlay='fault-'+original)
            assert receipt['response']['status']=='COMPLETE'
            if original=='after-commit':
                assert receipt['entry_lane']=='REPLAY_AVAILABLE' and receipt['reads']['evaluator_invocations']==0
                assert receipt['before']==receipt['after']
            else:
                assert receipt['reads']['evaluator_invocations']==1
    else:
        raise AssertionError('UNKNOWN_PHASE')

if __name__=='__main__':
    main()
