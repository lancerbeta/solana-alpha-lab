"""Reuse capture/import/Forge owners; only authored ingress and orchestration."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from fractions import Fraction
from common import ROOT, OUT, charge, dump, load

RETURNS = {'A': ['.10','-.04','.11','-.03','.12','-.02','.13','-.01','.14','0'],
           'B': ['.06','-.02','.07','-.01','.08','0','.09','.01','.10','.02']}

def prepare(name='base', negative=False, reuse_capture=False):
    from tests import test_hfic_list_aware_vertical_v1 as lav
    from tests import test_opportunity_episodes_vertical_v1 as vertical
    from tests.test_forge_research_flow_reliability_v1 import EpisodeFlowTests
    from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment
    from tests.test_opportunity_episodes_harness_v1 import token_object, write_assignment
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy, apply_universe_policy
    from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_episode_binding
    from solana_alpha_lab.factory.hfic_session import load_session_bundle
    import pyarrow.parquet as pq
    work=OUT/name
    assert not work.exists(), 'REGISTERED_WORLD_ALREADY_EXISTS'
    work.mkdir()
    day_a=datetime(2026,10,1,tzinfo=UTC)
    day_b=datetime(2026,10,5,tzinfo=UTC)
    source_asof=datetime(2026,10,8,6,tzinfo=UTC)
    table={g:{f'science{g}{i:02d}':('A' if i%2==0 else 'B',i%2==0,
        float(Fraction(RETURNS[g][i])-(Fraction(1,5) if negative and i%2==0 else 0)) if i<10 else .03)
        for i in range(12)} for g in ('A','B')}
    table['B']['scienceA00']=table['B'].pop('scienceB00')
    descriptor={'benchmark':'SCIENCE-LIFECYCLE-'+name,'table':table,'admissions_n':24,
        'decision_n':20,'matched_n':10,'list_comparator_n':10,'mixed_comparator_n':20,
        'negative_world':negative,'source_asof':source_asof,'new_fixture_main_cap':2,
        'scientific_acceptance':False,'clock_mode':'NATIVE_ASOF_AND_CLOCK_PARAMETERS; NO_SYSTEM_CLOCK_CHANGE'}
    dump(work/'registered-input.json',descriptor)  # before capture, MAIN, classification
    def market_row(mint,now,start,signal,target):
        i=next(i for i in range(12) if f'{i:02d}' in mint)
        offset=(now-start).total_seconds()
        price=1.0 if offset<10000 else 1.0+target
        holders=60 if offset<1100 else 75 if signal else 55
        if 1500<=offset<10000:
            if i==10: holders=40
            if i==11: price=None
        return token_object(mint,price=price,liquidity=12000,holders=holders)
    if reuse_capture:
        assert not negative, 'CHANGED_VALUES_REQUIRE_FRESH_CAPTURE'
        source=OUT/'base-v2/capture/rdp'
        packets=[str(p) for p in sorted((OUT/'base-v2/capture').glob('packet-*.json'))]
        assert len(packets)==2
        from common import sha
        source_inventory={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
        dump(work/'capture-reuse.json',{'source_world':'base-v2','source_file_hashes':source_inventory,
            'source_role':'ALREADY_EXPLORED_SYNTHETIC; NO_UNTOUCHED_SAMPLE',
            'version_reason':'Correct inherited quote prose and unrelated binding before native classification/execution',
            'previous_attempts_retained':True})
    else:
        with patch.multiple(lav,COHORT_A=table['A'],COHORT_B=table['B'],market_row=market_row,
            DAY_A=day_a,DAY_B=day_b,STOPS=day_b+timedelta(hours=3),
            END=source_asof-timedelta(hours=2)+timedelta(seconds=5),AS_OF=source_asof):
            source,packets=lav._capture_fresh(work)
    plane=work/'plane'
    plane.mkdir()
    store=ResearchStore(plane)
    store.prepare_write_lookup()
    with patch.object(vertical,'AS_OF',source_asof):
        imported=lav._consume(packets,source=source,mirror=work/'mirror',plane=plane)
    dump(work/'native-import.json',imported)
    assert imported['_exit_code']==0, imported
    write_assignment(plane,[])
    proposal=preview_universe_policy(store,min_holders=50,min_liquidity_usd=5000)['proposal']
    apply_universe_policy(store,repo_root=ROOT,proposal=proposal,confirm_append_only=True)
    oracle=[]
    binding=resolve_published_episode_binding(plane)
    for cohort in binding['cohorts']:
        rows=pq.read_table(plane/cohort['census_rel'],columns=['episode_id','mint','t0']).to_pylist()
        for row in rows:
            i=next(i for i in range(12) if f'{i:02d}' in row['mint'])
            group='A' if datetime.fromisoformat(row['t0'].replace('Z','+00:00')).date()==day_a.date() else 'B'
            oracle.append({'episode_id':row['episode_id'],'cohort_id':cohort['cohort_id'],
                'input_label':f'{group}{i:02d}','t0':row['t0'],'decision_eligible':i<10,
                'matched':i<10 and i%2==0,'comparator':i<10 and i%2==1,
                'return':str(Fraction(RETURNS[group][i])-(Fraction(1,5) if negative and i%2==0 else 0)) if i<10 else None})
    assert len(oracle)==24 and sum(r['decision_eligible'] for r in oracle)==20
    dump(work/'membership-numeric-oracle.json',sorted(oracle,key=lambda r:r['episode_id']))
    for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
        case=EpisodeFlowTests()
        case.plane,case.work=plane,work/kind
        case.work.mkdir()
        query=lav.draft(kind,list_condition={'clauses':[{'all_of':['A']}]},**(lav.NUMERIC if kind!='LIST_CONTRAST' else {}))
        charge('main',world=name,kind_name=kind)
        evidence,scope,_query,pre=case.look('SCIENCE-'+name+'-'+kind,query=query)
        body,ready=case.authored_draft(evidence,scope,pre['owner_focus'])
        generated,frozen=case.persist_and_freeze(body,ready)
        bundle=load_session_bundle(store,frozen['session_id'])
        spec=_bind_experiment(evidence['result']['experiment_recipe'],plane)
        asof=datetime.now(UTC)+timedelta(minutes=1)
        spec.update(schema_version='1.4',population='OPPORTUNITY_EPISODES',
            experiment_id='EXP-SCIENCE-'+name.upper()+'-'+kind.replace('_','-'),
            hypothesis_version='HYP-'+frozen['selected_candidate_id'],
            as_of=asof.isoformat().replace('+00:00','Z'),availability_cutoff=asof.isoformat().replace('+00:00','Z'),
            observation_request={'collection_mode':'REUSE_ONLY','requested_evidence_role':'EXPLORATORY_REUSE'},
            required_outcomes=[{'point_id':'E14400','field_ids':[lav.PRICE],'role':'PRIMARY'}])
        spec['parameters']['hfic_replay_session_id']=frozen['session_id']
        # The legacy helper supplies runner wiring. Author episode semantics before freeze/classification.
        comparator='eligible complement of list A' if kind=='LIST_CONTRAST' else 'all decision-eligible episodes D'
        spec.update(question='Does list A separate the frozen E1800 to E14400 price-relative proxy from '+comparator+'?',
            estimand='Mean(P(E14400)/P(E1800)-1 | matched list A) minus mean of the same proxy in '+comparator,
            method='frozen_episode_price_relative_proxy',
            falsifier='No supported fixed contrast, incorrect prefix membership, unavailable required outcome or PIT failure.',
            holdout_policy='EXPLORATORY_REUSE of already explored synthetic releases; no new holdout or scientific confirmation.')
        spec['data_bindings']=[r for r in spec['data_bindings'] if r['source_kind']=='DATASET_MANIFEST']
        dump(case.work/'spec.json',spec)
        dump(case.work/'frozen.json',bundle)
        dump(case.work/'upstream.json',{'discovery':evidence,'generated':generated,'freeze':frozen,
            'fidelity':'SCRIPTED_UPSTREAM_FIXTURE; NATIVE_CAPTURE_IMPORT_MAIN_PERSIST_FREEZE'})
    dump(work/'fixture-complete.json',descriptor)
    if reuse_capture:
        assert source_inventory=={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}, 'REUSED_CAPTURE_CHANGED'
    return {'world':name,'new_MAIN':2,'oracle_before_MAIN':True}
