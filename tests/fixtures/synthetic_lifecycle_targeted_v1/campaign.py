"""Bounded native episode audit; no product edits or fabricated scientific PASS."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT=Path('/repo')
OUT=Path(os.environ.get('SLS_OUTPUT_ROOT','/audit'))
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests'),'/kit']
from safety import check

_native_run=subprocess.run
def bounded_run(*args,**kwargs):
    kwargs['timeout']=min(kwargs.get('timeout') or 180,180)
    return _native_run(*args,**kwargs)
subprocess.run=bounded_run

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def pins():
    return {p:sha(ROOT/p) for p in ('src/solana_alpha_lab/factory/hfic_session.py',
        'src/solana_alpha_lab/factory/hfic_temporal_discovery.py','src/solana_alpha_lab/factory/experiment_evidence.py',
        'configs/experiment_capability_registry_v2.yaml','uv.lock')}

def experiment(recipe,plane,candidate):
    from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment
    body=_bind_experiment(recipe,plane)
    body.update(experiment_id='EXP-SLS-TC-'+candidate.removeprefix('HFIC-CAND-'),
        as_of='2026-10-16T00:00:00Z',availability_cutoff='2026-10-16T00:00:00Z',
        hypothesis_version='HYP-'+candidate)
    body.pop('required_feature_ids',None) # Match the actual capability-only frozen grounding.
    return body

def classify_only(spec,frozen,plane):
    from solana_alpha_lab.factory.hfic_session import run_live_classifier
    submission={'experiment_spec':spec,'hypothesis_definition_sha256':frozen['selected_definition_sha256'],
        'classifier_evaluated_at':'2026-10-16T00:00:00Z'}
    return run_live_classifier({'experiment_spec_packet':submission},frozen,repo_root=ROOT,data_root=plane)

def diagnose():
    from solana_alpha_lab.factory.hfic_control_integrity import fast_lane_availability_denial_codes
    from solana_alpha_lab.factory.research_store import ResearchStore
    work=Path('/audit/native-world')
    shutil.copytree('/input/native-world',work)
    plane=work/'rdp'
    before=ResearchStore(plane).diagnostics().committed_inventory_sha256
    records=[]
    for index,family in enumerate(('SIMPLE','COMPOUND')):
        frozen=json.loads((work/f'freeze-{index}.json').read_text())
        selected=frozen['critic_input_packet']['selected_candidate']
        result=json.loads((work/f'{family}-context.json').read_text())['evidence']['result']
        spec=experiment(result['experiment_recipe'],plane,frozen['selected_candidate_id'])
        receipt=classify_only(spec,frozen,plane)
        dump(OUT/f'{family}-counterfactual-spec.json',spec)
        dump(OUT/f'{family}-classifier.json',receipt)
        request=raw_schema_control_request()
        request['y_points'].append({'point_id':'Y14400','due_offset_seconds':14400,'allowed_lateness_seconds':300,
            'bundle_ids':['BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001']})
        modern={**copy.deepcopy(spec),'schema_version':'1.3','observation_request':request,
            'required_outcomes':[{'point_id':'Y14400','field_ids':['FIELD-USD-PRICE-001'],'role':'PRIMARY'}]}
        from solana_alpha_lab.factory.experiment_spec import validate_experiment_document
        validate_experiment_document(modern,root=ROOT)
        try:modern_receipt=classify_only(modern,frozen,plane)
        except Exception as exc:
            if not hasattr(exc,'code'):raise
            modern_receipt={'status':'BLOCKED','reason_code':exc.code}
        dump(OUT/f'{family}-spec13-candidate.json',modern)
        dump(OUT/f'{family}-spec13-classifier.json',modern_receipt)
        records.append({'family':family,'original_packet_sha256':frozen['critic_input_packet_sha256'],
            'original_definition_sha256':frozen['selected_definition_sha256'],
            'original_classifier_receipt':None,'original_classifier_reason_codes':None,
            'required_feature_ids':selected.get('required_feature_ids'),
            'required_capability_ids':selected.get('required_capability_ids'),
            'grounding':selected.get('grounding'),'unresolved_requirements':selected.get('unresolved_requirements'),
            'native_availability_denial_codes':fast_lane_availability_denial_codes(selected),
            'counterfactual_classifier':receipt,'spec13_classifier':modern_receipt,
            'spec13_request_fidelity':'PUBLIC_RAW_SCHEMA_CONTROL_NOT_A_FROZEN_SOURCE_SCHEDULE_BINDING',
            'fidelity':'READ_ONLY_CLASSIFICATION_AUDIT_NOT_ORIGINAL_SESSION_ADVANCEMENT'})
    after=ResearchStore(plane).diagnostics().committed_inventory_sha256
    assert before==after
    body={'status':'PASS','records':records,'research_inventory_unchanged':True,
        'non_claims':['NO_OOS_PROOF_FROM_CRITIC_TEXT','NO_ORIGINAL_SCIENTIFIC_ACCEPTANCE','NO_REWRITE_OF_OLD_KILL']}
    dump(OUT/'diagnosis.json',body)
    return body

def episode(*, resume=False):
    from tests import test_hfic_list_aware_vertical_v1 as lav
    from tests.test_opportunity_episodes_harness_v1 import token_object
    from tests.test_forge_research_flow_reliability_v1 import EpisodeFlowTests
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy,apply_universe_policy
    from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query,episode_query_capabilities
    world=Path('/audit/tmp/sls-tc-episode-world-v1')
    assert world.exists() if resume else not world.exists(),'BENCHMARK_WORLD_STATE_MISMATCH'
    # A separately registered episode-native world. These replacements author
    # market input only; no admission/filter, evaluator, result or science callback.
    tables={phase:{f'tc{phase}{i:03}':('A' if i%2==0 else 'B',i%2==0,.14 if i%2==0 else -.04)
        for i in range(64)} for phase in ('D','V')}
    query=lav.draft('LIST_CONTRAST',list_condition={'clauses':[{'all_of':['A']}]})
    query['query_id']='SLS-TC-EPISODE-NATIVE-LIST-A-V1'
    benchmark={'benchmark_id':'SLS-TC-EPISODE-NATIVE-V1','version':1,'kind':'SYNTHETIC_MODEL_ONLY',
        'population':'OPPORTUNITY_EPISODES','tables':tables,'query':query,
        'oracle':{'discovery_n':64,'group_A_n':32,'complement_n':32,'mean_A':'.14','mean_C':'-.04','contrast':'.18'},
        'freeze_before_capture':True,'blind_actor':'AGENT_BEHAVIOR_UNVERIFIED',
        'validation':'SEPARATE_LATER_CAPTURE_NOT_ACCEPTED_SCIENTIFIC_CONFIRMATION'}
    dump(OUT/'benchmark.json',benchmark)
    dump(OUT/'grammar.json',{'status':'AUTHOR_QUERY_REQUIRES_NATIVE_SCOPE_RESOLUTION','capabilities':episode_query_capabilities()})
    def market_row(mint,now,start,signal,target):
        offset=(now-start).total_seconds()
        price=1. if offset<10000 else 1.+target
        holders=60 if offset<1100 else (68 if signal else 58) if offset<1500 else (75 if signal else 55)
        return token_object(mint,price=price,liquidity=12000,holders=holders)
    if resume:
        assert canonical(json.loads(Path('/input/benchmark.json').read_text()))==canonical(benchmark),'BENCHMARK_CHANGED'
        source=world/'capture'/'rdp';packets=[str(world/'capture'/f'packet-{i}.json') for i in range(2)]
    else:
        with patch.object(lav,'COHORT_A',tables['D']),patch.object(lav,'COHORT_B',tables['V']),patch.object(lav,'market_row',market_row):
            source,packets=lav._capture_fresh(world)
    plane=world/'plane'
    if not resume:
        plane.mkdir()
        store=ResearchStore(plane);store.prepare_write_lookup()
        imported=lav._consume(packets[:1],source=source,mirror=world/'mirror',plane=plane)
        assert imported['_exit_code']==0,imported
        proposal=preview_universe_policy(store,min_holders=50,min_liquidity_usd=5000)['proposal']
        apply_universe_policy(store,repo_root=ROOT,proposal=proposal,confirm_append_only=True)
    case=EpisodeFlowTests();case.plane=plane;case.work=OUT/'inputs';case.work.mkdir()
    evidence,scope,resolved,pre=case.look('SLS-TC-EPISODE-NATIVE-V1',query=query)
    dump(OUT/'evidence.json',evidence)
    if resume:
        assert all(q['new_look'] is False for q in evidence['queries']),'RESUME_STARTED_NEW_LOOK'
    dump(OUT/'grammar.json',{'status':'PASS','validated':validate_temporal_query(resolved),
        'capabilities':episode_query_capabilities(),'author_aliases_resolved_by_native_owner':True})
    result=evidence['result'];group=result['research_scope']['matched'];control=result['research_scope']['contrast']['comparator']
    assert group['n']==group['target_observed_n']==32 and control['n']==control['target_observed_n']==32
    assert abs(Decimal(str(group['mean_target']))-Decimal('.14'))<Decimal('1e-12')
    assert abs(Decimal(str(control['mean_target']))-Decimal('-.04'))<Decimal('1e-12')
    body,ready=case.authored_draft(evidence,scope,pre['owner_focus'])
    card=body['candidates'][0]
    card['label']='SLS-TC-EPISODE-AUTHORED'
    card['claim']='Within the admitted synthetic episode population, list-A membership predicts the fixed E14400/E1800 price-relative proxy. Independent validation remains required; no market claim.'
    body['selected_candidate_ref']=card['label']
    generated,frozen=case.persist_and_freeze(body,ready)
    spec=experiment(result['experiment_recipe'],plane,frozen['selected_candidate_id'])
    receipt=classify_only(spec,frozen,plane)
    dump(OUT/'evidence.json',evidence);dump(OUT/'frozen.json',frozen)
    dump(OUT/'critic-packet.json',frozen['critic_input_packet']);dump(OUT/'experiment-spec.json',spec)
    dump(OUT/'classifier-probe.json',receipt)
    boundary_probe(spec)
    summary={'status':'PASS','benchmark_sha256':sha(OUT/'benchmark.json'),'native_world_retained':'sls-v1-scratch:/sls-tc-episode-world-v1',
        'source_packets':[{'name':Path(p).name,'sha256':sha(Path(p))} for p in packets],
        'discovery_import_only':True,'validation_imported_or_decoded':False,
        'native_prefix':'EPISODE_NATIVE_CAPTURE -> IMPORT -> FORGE_MAIN -> PERSIST_DRAFT -> FREEZE',
        'genuine_actor':'AGENT_BEHAVIOR_UNVERIFIED','selected_candidate_id':frozen['selected_candidate_id'],
        'selected_definition_sha256':frozen['selected_definition_sha256'],'critic_input_packet_sha256':frozen['critic_input_packet_sha256'],
        'classifier_probe':receipt,'oracle':{'status':'PASS','n_A':32,'n_C':32,'mean_A':'.14','mean_C':'-.04','contrast':'.18'},
        'native_full_product_path':False,'pre_critic_classifier_probe':'MECHANICAL_ONLY_NO_CRITIC_OR_SCIENCE_ACCEPTANCE'}
    dump(OUT/'episode-summary.json',summary)
    return summary

def raw_schema_control_request():
    from tests.test_hfic_temporal_production_runner_v1 import _schedule
    request=_schedule()
    for key in ('schema','schema_version','schedule_sha256'):request.pop(key,None)
    return {**request,'collection_mode':'REUSE_ONLY','requested_evidence_role':'EXPLORATORY_REUSE'}

def boundary_probe(spec):
    """Necessary-contract proof; raw schedule is a schema control, never an adapter."""
    import jsonschema
    from solana_alpha_lab.factory.experiment_spec import validate_experiment_document,ExperimentSpecError
    schema_path=ROOT/'catalog/schemas/experiment_spec_v1_3.schema.json'
    schema=json.loads(schema_path.read_text())
    control={**copy.deepcopy(spec),'schema_version':'1.3',
        'observation_request':raw_schema_control_request(),
        'required_outcomes':[{'point_id':'Y7200','field_ids':['FIELD-USD-PRICE-001'],'role':'PRIMARY'}]}
    validate_experiment_document(control,root=ROOT)
    negative=copy.deepcopy(control);negative['required_outcomes'][0]['point_id']='E14400'
    errors=[{'instance_path':'/'.join(map(str,e.absolute_path)),
        'schema_path':'/'.join(map(str,e.absolute_schema_path)),'validator':e.validator,'validator_value':e.validator_value}
        for e in jsonschema.Draft202012Validator(schema).iter_errors(negative)]
    try:
        validate_experiment_document(negative,root=ROOT)
    except ExperimentSpecError as exc:
        native_code=str(exc)
    else:raise AssertionError('EXPECTED_E_OUTCOME_CONTRACT_REFUSAL')
    assert len(errors)==1 and errors[0]['instance_path']=='required_outcomes/0/point_id'
    points={p:jsonschema.Draft202012Validator(schema['properties']['required_outcomes']['items']['properties']['point_id']).is_valid(p)
        for p in ('E300','E900','E1800','E14400','X300','Y14400')}
    body={'status':'PROVED_CONTRACT_GAP','native_error_code':native_code,'schema_sha256':sha(schema_path),
        'required_episode_outcome':'E14400','errors':errors,'point_controls':points,
        'whole_spec_raw_schema_control':'VALID_NOT_SEMANTICALLY_EQUIVALENT_EPISODE_ROUTE',
        'legacy_1_1':'VALID_NATIVE_RESEARCH_ARTIFACT_ROUTE_WITHOUT_REQUIRED_OUTCOMES',
        'mandatory_method':'PROMPT_B_REQUIRES_EXPERIMENT_SPEC_1_3_WITH_REQUIRED_OUTCOMES',
        'non_claims':['NO_E_TO_XY_CONVERSION','NO_SCHEDULE_ADAPTER','NO_SCIENCE_OR_PROMOTION_ACCEPTANCE']}
    dump(OUT/'spec13-control.json',control);dump(OUT/'spec13-negative.json',negative)
    dump(OUT/'contract-boundary.json',body)
    return body

def critic_stage(*, revise=False):
    from tests.test_forge_research_flow_reliability_v1 import EpisodeFlowTests
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    frozen=json.loads(Path('/audit/frozen.json').read_text())
    plane=Path('/audit/tmp/sls-tc-episode-world-v1/plane')
    case=EpisodeFlowTests();case.plane=plane;case.work=OUT/'inputs';case.work.mkdir()
    critic=json.loads(Path('/input/critic-result.json').read_text())
    finalized=case.cli('finalize','--session-id',frozen['session_id'],'--critic-result','/input/critic-result.json','--format','json')
    dump(OUT/'finalized.json',finalized)
    store=ResearchStore(plane)
    looks_before=list_discovery_looks(store,frozen['search_key_sha256'])
    if revise:
        assert critic['critic_terminal']=='REVISE_ONCE'
        body=json.loads(Path('/audit/inputs/draft.json').read_text())
        card=body['candidates'][0]
        card['material_difference_from_prior']='Novelty UNKNOWN. Frozen full-archive scope guard established no current block; no first-question or family-novelty claim.'
        card['proposed_method']=(
            'Design only, not a run or native confirming consumer. Freeze LIST_A_CONFIRMATION_PROTOCOL_V1 '
            'protocol_core_sha256=3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252. '
            'Statistic: episode-weighted mean(P(E14400)/P(E1800)-1) in A minus the eligible known-FALSE complement; delta=0. '
            'Preserve E1800/E14400, EPISODE_T0 membership, admitted universe and FIRST_RELIABLE_AVAILABLE_AT. '
            'Current 32/32 and +.14/-.04 are discovery only; same-release replay is exploratory. '
            'An independently admitted later release with complete exposure/protection/source-role and strict information-time separation is required; none is accepted here. '
            'For future validation retain repeated mints and crossed mint/time dependence; use frozen 24h and 48h partitions, 4096 crossed-cluster bootstrap draws each and all mint/block leave-one contrasts. '
            'Require >=30 distinct mints and >=30 time blocks overall and per group in both partitions, target coverage >=.95 and missing-rate gap <=.05. '
            'Unsupported source/bindings => BOUND_CONTRACT_NOT_READY or INVALID_OR_BLOCKED; inadequate support/empty draws => INSUFFICIENT. '
            'PASS=both lower bounds and every leave-one contrast >0; FAIL=both upper bounds and every leave-one contrast <=0; otherwise INCONCLUSIVE. '
            'This one-block synthetic fixture is INSUFFICIENT for confirmation; no IID or market inference. '
            'Native commissioning generated_at/research_memory_as_of are synthetic nonchronological metadata; source/event-time provenance remains UNKNOWN for real PIT. '
            'No timestamp or source history is rewritten, no new look/outcomes, no validation values are read, no new execution authority.' )
        card['cheapest_falsifier']='Frozen List-A crossed mint/time contrast design above: PASS/FAIL/INCONCLUSIVE only on separately accepted chronological evidence. Current one-block synthetic discovery is INSUFFICIENT; replay cannot confirm it.'
        revised_path=case.write('revised-draft.json',body)
        current=case.cli('revise','--session-id',frozen['session_id'],'--draft',revised_path,'--format','json')
        dump(OUT/'frozen.json',current);dump(OUT/'critic-packet.json',current['critic_input_packet'])
    else:
        current=case.cli('show-session','--session-id',frozen['session_id'],'--format','json')
        dump(OUT/'cold-session.json',current)
    looks_after=list_discovery_looks(store,frozen['search_key_sha256'])
    assert looks_before==looks_after,'CRITIC_STAGE_CREATED_NEW_LOOK'
    before=store.diagnostics().committed_inventory_sha256
    cold=case.cli('preflight','--no-auto-commission','--discovery-contract','--collection','OPPORTUNITY_EPISODES',
        '--owner-focus',frozen['owner_focus'],'--format','json')
    after=store.diagnostics().committed_inventory_sha256
    assert before==after,'COLD_READBACK_WROTE_STATE'
    dump(OUT/'cold-preflight.json',cold)
    summary={'status':'PASS','critic_terminal':critic['critic_terminal'],'session_id':frozen['session_id'],
        'selected_candidate_id':current.get('selected_candidate_id'),'session_state':current.get('session_state'),
        'selected_definition_sha256':current.get('selected_definition_sha256'),
        'critic_input_packet_sha256':current.get('critic_input_packet_sha256'),
        'native_critic_finalized':True,'native_revision':revise,'new_look_count':0,'cold_inventory_unchanged':True,
        'cold_action':cold.get('action'),'path_fidelity':'SEGMENT_PRODUCT_PATH','scientific_acceptance':False}
    dump(OUT/'critic-stage-summary.json',summary)
    return summary

def legacy_probe():
    """Explicit downstream fixture probe; does not advance the rejected HFIC path."""
    from solana_alpha_lab.factory.document_runner import DocumentRunner,RunContext
    from solana_alpha_lab.factory.lane_classifier import classify_lane
    from solana_alpha_lab.factory.operational_store import OperationalStore
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
    from solana_alpha_lab.factory.hfic_session import load_session_bundle
    from solana_alpha_lab.factory import experiment_evidence as ee
    from solana_alpha_lab.factory.experiment_spec import validate_experiment_document
    plane=Path('/audit/tmp/sls-tc-episode-world-v1/plane');store=ResearchStore(plane)
    original=json.loads(Path('/audit/frozen.json').read_text())
    frozen=load_session_bundle(store,original['session_id'])
    recipe=frozen['critic_input_packet']['grounded_evidence']['result']['experiment_recipe']
    spec=experiment(recipe,plane,frozen['selected_candidate_id'])
    validate_experiment_document(spec,root=ROOT)
    digest=experiment_spec_sha256(spec)
    lane=classify_lane({'experiment_spec':spec,'hypothesis_definition_sha256':frozen['selected_definition_sha256']},
        root=ROOT,data_root=plane,as_of=datetime(2026,10,16,tzinfo=UTC))
    ops=OperationalStore(plane/'ops'/'legacy-probe.sqlite')
    try:
        result=DocumentRunner(root=ROOT,store=ops).start_document(spec,spec_sha256=digest,
            run_context=RunContext(data_root=plane,hypothesis_definition_sha256=frozen['selected_definition_sha256'],lane_decision=lane))
    finally:ops.close()
    dump(OUT/'legacy-spec.json',spec);dump(OUT/'legacy-run.json',result)
    assert result['status']=='COMPLETE' and result['provider_calls_actual']==0,result
    run_id=result['run_id_or_null']
    saved=json.loads((plane/'research/artifacts/results'/f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}.json").read_text())
    readout=saved['capability_result']['summary']
    assert readout==frozen['critic_input_packet']['grounded_evidence']['result'],'LEGACY_REPLAY_CHANGED_RECIPE_RESULT'
    records=tuple(store.iter_committed_records())
    conflicts=ee._conflicted_execution_keys(spec['experiment_id'],records,digest)
    trials=ee._conflicted_trial_keys(spec['experiment_id'],records,digest,conflicts)
    direct_runs,direct_trials=ee._collect_direct_ids(spec['experiment_id'],records,digest,conflicted_run_ids=conflicts,conflicted_trial_ids=trials)
    direct=[]
    for record in records:
        relation=ee.classify_record(record,experiment_id=spec['experiment_id'],hypothesis_version_id=spec['hypothesis_version'],
            direct_run_ids=direct_runs,direct_trial_ids=direct_trials,spec_digest=digest,conflicted_run_ids=conflicts,conflicted_trial_ids=trials)
        if relation=='DIRECT':direct.append(ee._record_card(record,relation))
    obligations=ee._build_obligations(spec,entity={'entity_id':spec['experiment_id']},direct=direct,records=records,records_status='AVAILABLE',root=ROOT)
    guard=ee.science_guard(obligations)
    dump(OUT/'legacy-obligations.json',{'science_guard':guard,'obligations':obligations,
        'target_run_conflicted':run_id in conflicts,'excluded_nonmatching_run_count':len(conflicts)})
    assert guard['allowed'] is False and run_id not in conflicts
    scientific=[x for x in direct if x['record_kind'] in ee.SCIENTIFIC_EVIDENCE_RECORD_KINDS]
    # EXPERIMENT_METRIC is a scientific-carrier kind, but terminal-match=1
    # carries no N/PIT/result/uncertainty qualification. Let native obligations
    # decide; never equate metric presence with scientific sufficiency.
    summary={'status':'PASS','path_fidelity':'SEGMENT_PRODUCT_PATH','fixture_id':'TC-LEGACY-1.1-REPLAY',
        'scope':'EXPLICIT_DOWNSTREAM_PROBE_NOT_CRITIC_APPROVED_ADVANCEMENT',
        'experiment_id':spec['experiment_id'],'experiment_spec_sha256':digest,'run_id':run_id,
        'hypothesis_definition_sha256':frozen['selected_definition_sha256'],'schema_version':'1.1',
        'classifier_terminal':lane.terminal,'run_terminal':result['status'],'exact_recipe_result_replayed':True,
        'scientific_terminal':result['scientific_terminal'],'target_run_conflicted':run_id in conflicts,
        'excluded_nonmatching_run_count':len(conflicts),
        'direct_records':[{k:x.get(k) for k in ('record_id','record_kind','entity_id','hypothesis_version_id','run_id','payload_sha256')} for x in direct],
        'direct_science_carrier_records':len(scientific),'science_guard':guard,
        'scientific_obligations_present':sum(x['status']=='PRESENT' and x['code']!='FALSIFIER' for x in obligations),
        'obligations':[{k:x.get(k) for k in ('code','status')} for x in obligations],
        'accepted_chronological_validation':False,'scientific_decision_written':False,'strategy_version_created':False,
        'synthetic_activation_or_paper_from_this_candidate':False,'confirmation_consumer':'ABSENT_IN_THIS_ROUTE'}
    dump(OUT/'legacy-summary.json',summary)
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('diagnose','episode','episode-resume','revise','finalize','legacy'),required=True);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();body={'status':'HARNESS_ERROR'}
    initial=None
    try:
        (OUT/'tmp').mkdir(exist_ok=True)
        os.environ['TMPDIR']=str(OUT/'tmp')
        import tempfile;tempfile.tempdir=str(OUT/'tmp')
        safety=check();dump(OUT/'safety.json',safety)
        assert safety['pass'],'INVALID_HARNESS_ISOLATION'
        initial=pins();dump(OUT/'source-pins.json',initial)
        if args.phase=='diagnose':body=diagnose()
        elif args.phase in ('episode','episode-resume'):body=episode(resume=args.phase=='episode-resume')
        elif args.phase in ('revise','finalize'):body=critic_stage(revise=args.phase=='revise')
        elif args.phase=='legacy':body=legacy_probe()
        assert pins()==initial
    except Exception as error:
        dump(OUT/'error.json',{'status':'HARNESS_ERROR','error_type':type(error).__name__})
        raise
    finally:
        dump(OUT/'phase-terminal.json',{'phase':args.phase,'status':body['status'],'seconds':round(time.monotonic()-start,6),
            'source_unchanged':pins()==initial if initial is not None else 'UNKNOWN'})
    print(json.dumps({'phase':args.phase,'status':body['status']}))
    return 0

if __name__=='__main__':raise SystemExit(main())
