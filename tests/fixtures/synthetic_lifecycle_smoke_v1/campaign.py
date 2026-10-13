"""Drive existing native seams, retain observations, never repair product."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import unittest
import signal
from contextlib import closing
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT=Path('/repo')
OUT=Path(os.environ.get('SLS_OUTPUT_ROOT','/audit'))
_native_run=subprocess.run
def bounded_run(*args,**kwargs):
    kwargs['timeout']=min(kwargs.get('timeout') or 180,180)
    return _native_run(*args,**kwargs)
subprocess.run=bounded_run
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests'),'/kit',str(ROOT/'tests/fixtures/big_agentic_audit_v1')]
from safety import check
from world import generate, oracle, prepare

PHASES={
 'fortnight':['test_trading_core_operational_closure_v1.OperatingDriverTests.test_C21_native_source_stream_over_virtual_two_weeks'],
 'prepare':['tests.test_big_agentic_audit_v1.AuditOracleControls',
   'tests.test_research_store.ResearchStoreTests.test_payload_hash_mismatch_is_rejected',
   'test_trading_core_operational_closure_v1.OperatingDriverTests.test_C01_C02_C03_C05_C06_native_loop_full_money_oracle'],
 'forge':['tests.test_forge_composite_feature_recipes_v1',
   'tests.test_forge_ordinary_operation_lifecycle_v1',
   'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_os_reply_loss_then_moved_root_resume_uses_original_draft_and_charge',
   'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_public_prefix_is_invariant_to_produced_future_poison_but_authorized_numeric_changes',
   'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_scripted_positive_boundary_runs_real_classify_final_runner_replay'],
 'trading':['test_trading_core_operational_closure_v1.OperatingDriverTests',
   'test_trading_operational_obligations_v1.OperatingObligationsTests',
   'test_trading_operational_adapters_v1'],
 'recovery':['test_trading_operational_recovery_v1.OperationalRecoveryTests.test_complete_cut_restores_tighter_envelope_and_disabled_runtime_policy',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_configuration_chain_damage_or_omission_cannot_acknowledge_restore',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_cross_snapshot_original_switch_cut_ack_resume_admits_successor_and_services_old_exit',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_complete_cut_retains_known_cost_floor_before_later_unknown_total',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_unknown_entry_recovery_keeps_original_pending_identity_without_quote_resend',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_postclaim_entry_response_failure_keeps_original_pending_and_future_old_exit_in_same_run',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_original_entry_nonfill_recovery_clears_only_proved_incident_after_cold_restart',
   'test_trading_operational_recovery_v1.OperationalRecoveryTests.test_malformed_new_source_json_does_not_stop_ordinary_cli_before_future_old_exit'],
 'handoff':['tests.test_experiment_evidence_decision_v1','tests.test_science_to_strategy_handoff_v1'],
}

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,default=str)+'\n',encoding='utf-8')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def emit(kind,**fields):
    path=OUT/'attempts.jsonl'
    count=len(path.read_text().splitlines()) if path.exists() else 0
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps({'seq':count+1,'kind':kind,**fields},sort_keys=True,default=str)+'\n')

def source_pins():
    names=['src/solana_alpha_lab/factory/hfic_temporal_discovery.py',
      'src/solana_alpha_lab/factory/episode_decision.py','src/solana_alpha_lab/factory/trading_runner.py',
      'src/solana_alpha_lab/factory/trading_coordinator.py','src/solana_alpha_lab/factory/paper_plane.py',
      'configs/experiment_capability_registry_v2.yaml','uv.lock']
    return {name:sha(ROOT/name) for name in names}

def capture(test):
    # Retain selected real state before existing test-owned teardown. SQLite
    # backup sees committed WAL; business writes remain owned by the test.
    method=test.id().split('.')[-1]
    selected={'test_C01_C02_C03_C05_C06_native_loop_full_money_oracle',
      'test_C07_C08_C09_positive_successor_and_old_exit',
      'test_C18_C19_native_restore_before_effect_independent_ledger',
      'test_C09_C11_C12_shadow_failure_unknown_partial_remainder_drain',
      'test_cross_snapshot_original_switch_cut_ack_resume_admits_successor_and_services_old_exit',
      'test_complete_cut_restores_tighter_envelope_and_disabled_runtime_policy',
      'test_complete_cut_retains_known_cost_floor_before_later_unknown_total'}
    if method not in selected: return []
    owned=getattr(test,'tmp',None) or getattr(test,'_tmp',None)
    if owned is None: return []
    source=Path(owned.name)
    if not source.is_relative_to(OUT/'tmp'): raise AssertionError('RETAIN_ROOT_UNOWNED')
    sequence=len(list((OUT/'snapshots').glob('*'))) if (OUT/'snapshots').exists() else 0
    target=OUT/'snapshots'/f'{sequence+1:04d}-{method}'
    target.mkdir(parents=True,exist_ok=False)
    pins=[]
    for path in sorted(source.rglob('*')):
        if not path.is_file() or '.git' in path.parts or path.suffix not in {'.sqlite','.json','.yaml'}: continue
        if path.stat().st_size>16*1024*1024: continue
        destination=target/path.relative_to(source)
        destination.parent.mkdir(parents=True,exist_ok=True)
        if path.suffix=='.sqlite':
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as original,closing(sqlite3.connect(destination)) as backup:
                original.backup(backup)
        else: destination.write_bytes(path.read_bytes())
        pins.append({'path':str(destination.relative_to(OUT)),'sha256':sha(destination),'bytes':destination.stat().st_size})
    dump(target/'inventory.json',pins)
    return pins

def suite(phase):
    records=[]
    class Result(unittest.TextTestResult):
        def startTest(self,test):
            self.started=time.monotonic()
            self.current={'test_id':test.id(),'status':'UNKNOWN'}
            signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('NATIVE_TEST_DEADLINE')))
            signal.alarm(300 if phase=='recovery' else 180)
            original=test._callTearDown
            def teardown():
                self.current['snapshots']=capture(test)
                return original()
            test._callTearDown=teardown
            emit('TEST_START',test_id=test.id())
            super().startTest(test)
        def addSuccess(self,test): self.current['status']='PASS';super().addSuccess(test)
        def addFailure(self,test,error):
            if getattr(self,'current',{}).get('test_id')==test.id():
                self.current.update(status='FAIL',error_type=error[0].__name__,failure_detail=str(error[1]))
            else:emit('FRAMEWORK_ERROR',test_id=test.id(),error_type=error[0].__name__)
            super().addFailure(test,error)
        def addError(self,test,error):
            if getattr(self,'current',{}).get('test_id')==test.id():
                self.current.update(status='ERROR',error_type=error[0].__name__,failure_detail=str(error[1]))
            else:emit('FRAMEWORK_ERROR',test_id=test.id(),error_type=error[0].__name__)
            super().addError(test,error)
        def addSkip(self,test,reason): self.current['status']='SKIP';self.current['reason']=reason;super().addSkip(test,reason)
        def addSubTest(self,test,subtest,error):
            if error is not None:
                self.current['status']='FAIL' if issubclass(error[0],test.failureException) else 'ERROR'
                self.current.setdefault('failed_subtests',[]).append({'id':subtest.id(),'error_type':error[0].__name__})
            super().addSubTest(test,subtest,error)
        def stopTest(self,test):
            signal.alarm(0)
            self.current.update(seconds=round(time.monotonic()-self.started,6),metrics=getattr(test,'metrics',{}))
            records.append(self.current)
            emit('TEST_TERMINAL',**self.current)
            super().stopTest(test)
    names=PHASES['forge'][-3:] if phase=='forge-tail' else PHASES['trading' if phase=='trading-tail' else phase]
    selected=unittest.defaultTestLoader.loadTestsFromNames(names)
    if phase=='trading-tail':
        prior=[json.loads(line) for line in Path('/input/attempts.jsonl').read_text().splitlines()]
        complete={item['test_id'] for item in prior if item['kind']=='TEST_TERMINAL' and item['status']=='PASS'}
        deferred='test_C21_native_source_stream_over_virtual_two_weeks'
        def flat(items):
            for item in items:
                if isinstance(item,unittest.TestSuite): yield from flat(item)
                else: yield item
        tests=list(flat(selected))
        dump(OUT/'tail-selection.json',{'completed_prior':sorted(complete),'original_selected':[x.id() for x in tests],
            'budget_blocked':[x.id() for x in tests if x.id().endswith(deferred)],'denominator_reduced':False})
        selected=unittest.TestSuite(x for x in tests if x.id() not in complete and not x.id().endswith(deferred))
    result=unittest.TextTestRunner(verbosity=1,resultclass=Result).run(selected)
    receipt={'phase':phase,'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
       'tests':records,'failed_ids':[test.id() for test,_ in result.failures+result.errors],
       'fidelity':'CONTRACT_ONLY_UNLESS_BOUNDARY_SPECIFIC_EVIDENCE','actor_fidelity':'SCRIPTED','new_scientific_authority':False}
    dump(OUT/'suite.json',receipt)
    return receipt

def publish_discovery(world_rows,workspace):
    from tests.test_live_cohort_discovery_release_series import _member,_obs,_snapshot_for_week,CAMPAIGN_STARTS,ACTIVATION
    from tests.test_hfic_temporal_production_runner_v1 import _schedule,DOCUMENT_LATENESS
    from solana_alpha_lab.factory.observation_schedule import validate_observation_schedule,schedule_sha256
    from solana_alpha_lab.factory.live_cohort_discovery_release import write_observation_rdp_source,seal_live_cohort,import_live_cohort,cohort_id_for_admission
    from solana_alpha_lab.factory.observation_panel_publisher import persist_observation_schedule
    from solana_alpha_lab.factory.hfic_temporal_discovery import stamp_provider_reported_snapshot_transport
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy,apply_universe_policy
    from tests.test_opportunity_episodes_harness_v1 import synth_mint
    schedule=_schedule();schedule.pop('schedule_sha256')
    schedule['y_points'].append({'point_id':'Y14400','due_offset_seconds':14400,'allowed_lateness_seconds':DOCUMENT_LATENESS,'bundle_ids':['BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001']})
    schedule=validate_observation_schedule(schedule,root=ROOT);schedule['schedule_sha256']=schedule_sha256(schedule)
    data=workspace/'rdp'
    ingress=[]
    for cohort in range(4):
        snap=_snapshot_for_week(cohort)
        snap.update(producer_git_sha='94b391d658b52035ae88e2da05f1ea25ff17b0f8',schedule_sha256=schedule['schedule_sha256'],members=[],observations=[])
        anchor=CAMPAIGN_STARTS+timedelta(days=7*cohort)
        admission=anchor.strftime('%Y-%m-%dT%H:%M:%SZ')
        for item in [r for r in world_rows if r['cohort']==cohort]:
            mint=synth_mint(item['id'])
            member=_member(mint,admission);member.update(candidate_state='X_ELIGIBLE',inclusion_probability='1')
            snap['members'].append(member)
            cells=[('X300','FIELD-HOLDER-COUNT-001',item['h0']),('Y900','FIELD-HOLDER-COUNT-001',item['h1']),
                ('X300','FIELD-USD-PRICE-001',item['p0']),('Y900','FIELD-USD-PRICE-001',item['p1']),
                ('X300','FIELD-LIQUIDITY-USD-001',item['l0']),('Y900','FIELD-LIQUIDITY-USD-001',item['l1']),
                ('Y14400','FIELD-USD-PRICE-001',item['p_exit'])]
            for point,field,value in cells:
                stamp=(anchor+timedelta(seconds={'X300':300,'Y900':900,'Y14400':14400}[point]+DOCUMENT_LATENESS)).strftime('%Y-%m-%dT%H:%M:%SZ')
                row=_obs(mint,point,admission);row.update(field_id=field,typed_value=str(value),event_time=stamp,first_reliable_available_at=stamp,
                    request_started_at=stamp,response_received_at=stamp)
                row['request_sha256']=hashlib.sha256(f'{mint}:{point}'.encode()).hexdigest()
                row['response_sha256']=hashlib.sha256(json.dumps([cell for cell in cells if cell[0]==point],sort_keys=True).encode()).hexdigest()
                snap['observations'].append(row)
        snap['observations']=stamp_provider_reported_snapshot_transport(snap['observations'])
        for row in snap['observations']: row['call_occurrence_id']=hashlib.sha256(f"{row['mint']}:{row['point_id']}".encode()).hexdigest()
        cid=cohort_id_for_admission(anchor,starts_at=CAMPAIGN_STARTS,stops_admitting_at=CAMPAIGN_STARTS+timedelta(days=84))
        source=workspace/f'observation-{cohort}';released=workspace/f'release-{cohort}'
        write_observation_rdp_source(source,snap,cohort_id=cid)
        now=anchor+timedelta(days=10)
        seal_live_cohort(observation_rdp_root=source,cohort_id=cid,release_root=released,sealed_at=now,as_of=now)
        imported=import_live_cohort(release_root=released,data_root=data,import_time=now+timedelta(hours=1))
        assert imported['status']=='IMPORTED'
        ingress.append({'cohort':cohort,'cohort_id':cid,'members':32,'observations':len(snap['observations']),'status':imported['status']})
        if cohort==0: persist_observation_schedule(data_root=data,schedule=schedule,now=now,producer_git_sha=snap['producer_git_sha'],activation_id=ACTIVATION)
    store=ResearchStore(data)
    proposal=preview_universe_policy(store,min_holders=50,min_liquidity_usd=5000)['proposal']
    apply_universe_policy(store,repo_root=ROOT,proposal=proposal,confirm_append_only=True)
    dump(workspace/'ingress.json',{'status':'PASS','partition':'DISCOVERY','validation_admitted':False,'mint_n':128,'cohorts':ingress})
    return data

def world_run():
    from tests.test_hfic_cli import run_cli,bind_draft
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
    from tests.test_forge_composite_feature_recipes_v1 import mixed_spec
    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
    from solana_alpha_lab.factory.research_store import ResearchStore
    workspace=OUT/'native-world';workspace.mkdir()
    prepare(workspace/'sealed-world')
    data=publish_discovery(generate(),workspace)
    def call(name,*args):
        done=run_cli(name,*args,'--format','json',data_root=data)
        if done.returncode!=0:
            dump(workspace/f'failed-{name}.json',{'code':done.returncode,'stdout':done.stdout,'stderr':done.stderr})
            raise RuntimeError(f'NATIVE_CLI_REFUSAL:{name}:SEE_RETAINED_COMMAND_OUTPUT')
        body=json.loads(done.stdout)
        dump(workspace/f'{name}-{len(list(workspace.glob(name+"-*.json")))}.json',body)
        return body
    outputs=[]
    policy=call('research-policy-preview','--main-total','4','--adaptive-total','0','--preview-total','2',
        '--simple-before-compound','2','--max-generated','6')
    policy_path=workspace/'synthetic-policy-proposal.json';dump(policy_path,policy['proposal'])
    call('research-policy-apply','--proposal',str(policy_path),'--confirm-append-only')
    for family in ('SIMPLE','COMPOUND'):
        focus='SLS_AUDIT_AUTHORED_'+family
        receipt=call('preflight','--discovery-contract','--owner-focus',focus)
        spec=mixed_spec('return_ratio');spec['query_id']=focus;spec['budget_allocation']='AUTO'
        spec['all']=[{'feature':'holders','op':'gte','value':.20}] if family=='SIMPLE' else [
           {'feature':'price','op':'lte','value':-.02},{'feature':'liquidity','op':'gte','value':1.05}]
        if family=='SIMPLE': spec['features']=spec['features'][:1];spec['search_tier']='SIMPLE_SCREEN'
        scope={'population':'BASE_X','decision_timestamp':'Y900','target':temporal.temporal_target_label(spec),
           'estimand':'price_relative_proxy','explanatory_condition':'holders' if family=='SIMPLE' else 'price_and_liquidity',
           'evidence_surface_mode':'ORDINARY_GROUNDED_DISCOVERY_V1'}
        operation=_operation(spec,focus=focus,journal=receipt['search_key_sha256'],market=receipt['market_evidence_epoch_sha256'],
           text='Synthetic audit authored frozen predicate; no blind discovery claim.',cap={'main':4,'adaptive':0,'preview':1},completion='SCIENTIFIC_TERMINAL')
        files={name:workspace/f'{family}-{name}.json' for name in ('spec','scope','operation')}
        for name,body in [('spec',spec),('scope',scope),('operation',operation)]:dump(files[name],body)
        # Entire authorial request is fixed before the first value-bearing MAIN.
        evidence=call('discovery-execute','--store',str(data),'--spec',str(files['spec']),
           '--journal-scope',receipt['search_key_sha256'],'--candidate-scope',str(files['scope']),'--operation',str(files['operation']))
        result=evidence['result'];expected=oracle(generate(),family,'DISCOVERY')
        assert result['decision_eligible_n']==128 and result['matched_n']==expected['n']
        fresh=call('preflight','--discovery-contract','--owner-focus',focus)
        source=json.loads((ROOT/'tests/fixtures/hypothesis_forge/draft_v1_2_valid.json').read_text())
        identity=temporal.temporal_holder_claim_identity(result)
        card={**source['candidates'][0],**scope,**identity,'label':focus,'claim_form':'PREDICTIVE','novelty_class':'REFORMULATION',
          'claim':'Fixed synthetic predecision condition distinguishes later PRICE_RELATIVE_PROXY; no market claim.',
          'mechanism':'Predictive synthetic association only; causal mechanism UNKNOWN.',
          'mundane_alternative':'Selection, common activity and timing can explain the association.',
          'actor_counterparty':'Synthetic token observations; causal actor unknown.',
          'state_transition':'X300 to Y900 condition -> Y14400 price mark.',
          'proposed_method':'Frozen predicate, same decision-eligible comparator; lab validation separately labeled.',
          'negative_control':'NULL and DECOY independent synthetic fixtures.',
          'confounders':['selection','common activity'],'required_capability_ids':[temporal.TEMPORAL_CAPABILITY_ID],
          'required_feature_ids':[],'cheapest_falsifier':'Compare the frozen supported predicate with SAME_DECISION_ELIGIBLE without retuning.',
          'disconfirming_prediction':'No positive price contrast at the fixed target.',
          'decision_unlocked':'Whether a separately accepted chronological validation route is needed.',
          'kill_if':['PIT identity invalid','Frozen contrast fails'],'prior_work_refs':[],
          'material_difference_from_prior':'Campaign-owned synthetic authored positive control.','unresolved_requirements':[]}
        draft=bind_draft({**source,'owner_focus':focus,'candidates':[card]},fresh)
        draft.pop('runner_up_candidate_ref',None);draft.pop('strongest_rejected_alternative',None)
        draft['selected_candidate_ref']=card['label'];draft['grounded_evidence']=evidence
        dpath=workspace/f'{family}-draft.json';rpath=workspace/f'{family}-preflight.json';dump(dpath,draft);dump(rpath,fresh)
        persisted=call('persist-draft','--draft',str(dpath),'--preflight-receipt',str(rpath),'--representation-id','BASE')
        resume=call('preflight','--discovery-contract','--owner-focus',focus);dump(rpath,resume)
        frozen=call('freeze','--draft',str(dpath),'--preflight-receipt',str(rpath))
        dump(workspace/f'{family}-critic-packet.json',frozen['critic_input_packet'])
        dump(workspace/f'{family}-context.json',{'focus':focus,'data_root':str(data),'spec':spec,'evidence':evidence,'frozen':frozen,'persisted':persisted})
        replay=temporal.run_registered_fixed_time_proxy(root=ROOT,registry_path=ROOT/'configs/experiment_capability_registry_v2.yaml',
           recipe=result['experiment_recipe'],data_root=data)
        assert replay['summary']==result
        before=ResearchStore(data).diagnostics().committed_inventory_sha256
        repeat=call('discovery-execute','--store',str(data),'--spec',str(files['spec']),
           '--journal-scope',receipt['search_key_sha256'],'--candidate-scope',str(files['scope']),'--operation',str(files['operation']))
        assert not repeat['values_loaded'] and ResearchStore(data).diagnostics().committed_inventory_sha256==before
        outputs.append({'family':family,'matched_n':result['matched_n'],'population_n':128,'independent_oracle':expected,
           'session_id':frozen['session_id'],'grounding':frozen['critic_input_packet']['selected_candidate']['grounding']['terminal'],
           'registered_replay':'PASS','exact_request_replay_zero_write':True,'origin':'AUDIT_AUTHORED_FIXTURE','actor_fidelity':'SCRIPTED'})
    receipt={'status':'PASS','path_fidelity':'SEGMENT_PRODUCT_PATH','left_boundary':'AUDIT_AUTHORED_SYNTHETIC_SOURCE',
       'right_boundary':'NATIVE_FROZEN_CRITIC_PACKET_AND_REGISTERED_PROXY_REPLAY','families':outputs,
       'native_scientific_oos':False,'blind_discovery':False,'validation_admitted':False}
    dump(OUT/'world-summary.json',receipt)
    return receipt

def spine_run():
    from tests.test_trading_core_operational_closure_v1 import OperatingDriverTests
    from tests.test_opportunity_episodes_harness_v1 import token_object
    from datetime import UTC,datetime
    results=[]
    # Explicit bridge: existing legal episode fixture authors its own science
    # records. It is not a conversion or validation of either raw candidate.
    for index in (1,2):
        case=OperatingDriverTests('test_C01_C02_C03_C05_C06_native_loop_full_money_oracle')
        case.setUp()
        case.start_operating(suffix='' if index==1 else '-B',list_only=index==2)
        entry=case.invoke('run',ticks=2,as_of='2026-10-05T12:40:00Z')
        before=case.invoke('readback')
        assert entry['status']=='GRACEFUL_SHUTDOWN' and len(before['positions'])==1
        assert before['positions'][0]['state']=='OPEN'
        # Price path is an external-world stimulus, not a fill/result override.
        item=next(r for r in generate() if r['partition']=='PAPER_FORWARD' and r['hidden'][0] and r['hidden'][1]*r['hidden'][2])
        target_return=Decimal(item['p_exit'])/Decimal(item['p1'])-1
        decision=Decimal(str(case.decision_price));exit_price=decision*(1+target_return)
        case.source.market.series[case.mint]=lambda now:token_object(case.mint,price=float(exit_price),liquidity=10000,holders=case.holders_end)
        case.source.tick(datetime(2026,10,5,13,5,tzinfo=UTC))
        finished=case.invoke('run',ticks=2,as_of='2026-10-05T13:10:00Z')
        after=case.invoke('readback')
        position=after['positions'][0]
        assert position['state']=='RECONCILED' and len(after['modeled_attempts'])==2 and len(after['modeled_results'])==2
        # Native decimal path owns accepted units; independent accounting uses
        # the accepted entry/exit price witnesses, known quantity and fee model.
        cents=lambda x:x.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        gross_exit=cents(Decimal('10000000')*Decimal(str(float(exit_price))))
        entry_fee=cents(Decimal('30')*Decimal('.002'))
        exit_fee=cents(gross_exit*Decimal('.002'))
        expected=cents(gross_exit-Decimal('30')-entry_fee-exit_fee-Decimal('.02'))
        actual=Decimal(after['modeled_net_after_additional_costs_usd'])
        dump(OUT/f'spine-{index}-observer.json',{'entry':before,'exit':after,'expected':str(expected),'actual':str(actual),
            'cash_units':'USD_CENTS','rounding':'ROUND_HALF_UP_EACH_LEG','gross_exit':str(gross_exit),'entry_fee':str(entry_fee),'exit_fee':str(exit_fee)})
        capture(case)
        assert actual==expected,(str(actual),str(expected))
        packet={'bridge_id':'BR-01','fidelity':'SEGMENT_PRODUCT_PATH','origin':'AUDIT_AUTHORED_FIXTURE',
           'native_raw_candidate_consumed':False,'scientific_protocol_producer_bypassed':True,
           'recipe_population':'OPPORTUNITY_EPISODES','operating_activation':'PERSISTED',
           'scientific_question_kind':'MIXED_LIST_NUMERIC' if index==1 else 'LIST_CONTRAST',
           'strategy_version':case.runner.strategy,'manifest':case.manifest,'execution_binding':case.binding,
           'entry_readback':before,'exit_readback':after,'accounting_oracle':{'modeled_net':str(expected),'actual_modeled_net':str(actual)},
           'source_world_ref':item['id'],'source_world_future_return':str(target_return),'long_path_from_forge':False}
        dump(OUT/f'spine-{index}.json',packet)
        case.tearDown()
        results.append({'strategy':index,'state':position['state'],'attempts':2,'modeled_net':str(actual),
           'native_raw_candidate_consumed':False,'right_boundary':'ORDINARY_PAPER_RECONCILIATION_AND_FRESH_PROCESS_READBACK'})
    receipt={'status':'PASS','bridge_id':'BR-01','fidelity':'SEGMENT_PRODUCT_PATH','strategies':results,
       'source_to_reconciliation':True,'raw_to_paper':False,'science_evidence_origin':'EXPLICIT_EXISTING_SYNTHETIC_FIXTURE'}
    dump(OUT/'spine-summary.json',receipt)
    return receipt

def seams_run():
    from tests.test_forge_composite_feature_recipes_v1 import mixed_spec
    from tests.test_opportunity_episodes_contract_v1 import episode_spec
    from solana_alpha_lab.factory.episode_decision import bound_recipe_body
    from solana_alpha_lab.factory import hfic_research_scope as scope
    raw=mixed_spec('return_ratio')
    episode=episode_spec(schema_version='1.2',hypothesis_kind='NUMERIC_IN_SCOPE',research_scope={})
    episode=scope.canonicalize_query_scope(episode,scope.MembershipEvidence())
    cases=[]
    def probe(name,query,expected,population='OPPORTUNITY_EPISODES',strategy_population='OPPORTUNITY_EPISODES'):
        document={'population':population,'parameters':{'episode_query':query}}
        try:
            result=bound_recipe_body(document,strategy={'population_ref':strategy_population})
            actual='ACCEPTED'
        except Exception as error:
            actual=getattr(error,'reason_code',None) or getattr(error,'code',None) or str(error)
        assert actual==expected,(name,actual,expected)
        cases.append({'case':name,'expected':expected,'actual':actual,'status':'PASS','positive_runtime_boundary_reached':actual=='ACCEPTED'})
    probe('EXACT_RAW_RECIPE',raw,'BOUND_EPISODE_RECIPE_REQUIRED')
    translated=copy.deepcopy(episode);translated['decision']['point_id']='Y900'
    probe('EPISODE_SCHEMA_WITH_RAW_POINT',translated,'POINT_NOT_IN_ALLOWLIST')
    selected=copy.deepcopy(episode);selected['research_scope']['evidence_selection']['cohort_ids']=['REL-20261005T000000Z-20261006T000000Z']
    probe('EXPLICIT_RESEARCH_COHORT',selected,'RUNTIME_COHORT_SELECTION_UNSUPPORTED')
    probe('WRONG_STRATEGY_POPULATION',episode,'RECIPE_POPULATION_MISMATCH',strategy_population='BASE_X')
    probe('SEPARATE_LEGAL_EPISODE_FIXTURE',episode,'ACCEPTED')
    receipt={'status':'PASS','fidelity':'CONTRACT_ONLY','cases':cases,'product_mutation':False,
        'raw_to_episode_bridge':'BLOCKED','semantic_identity_conversion':'NOT_PROVED','store_writes':0}
    dump(OUT/'seams.json',receipt);return receipt

def finalize_run():
    from tests.test_hfic_cli import run_cli
    from solana_alpha_lab.factory.research_store import ResearchStore
    workspace=Path('/audit/native-world');data=workspace/'rdp';records=[]
    def call(tag,name,*args):
        result=run_cli(name,*args,'--format','json',data_root=data)
        body=json.loads(result.stdout)
        dump(OUT/f'{tag}.json',body)
        assert result.returncode==0,(name,body)
        return body
    for family in ('SIMPLE','COMPOUND'):
        context=json.loads((workspace/f'{family}-context.json').read_text())
        critic=Path('/input')/f'{family}-critic-result.json'
        finalized=call(f'{family}-finalize','finalize','--session-id',context['frozen']['session_id'],'--critic-result',str(critic))
        persisted=call(f'{family}-forge-persist','forge-run','--owner-focus',context['focus'],'--persist')
        before=ResearchStore(data).diagnostics().committed_inventory_sha256
        cold=call(f'{family}-cold-readback','forge-run','--owner-focus',context['focus'],'--no-write')
        assert ResearchStore(data).diagnostics().committed_inventory_sha256==before
        records.append({'family':family,'session_id':context['frozen']['session_id'],'finalized':finalized,
            'persisted':persisted,'cold':cold,'cold_zero_write':True,'additional_main_calls':0})
    receipt={'status':'PASS','fidelity':'SEGMENT_PRODUCT_PATH','critics':'GENUINE_PACKET_ONLY_FRESH_CONTEXT',
        'scientific_positive':False,'main_repeated':False,'records':records}
    dump(OUT/'finalize-summary.json',receipt);return receipt

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True);args=parser.parse_args()
    (OUT/'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR']=str(OUT/'tmp')
    import tempfile;tempfile.tempdir=str(OUT/'tmp')
    safety=check();dump(OUT/'safety.json',safety)
    if not safety['pass']: raise SystemExit('INVALID_HARNESS_ISOLATION')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()=='94b391d658b52035ae88e2da05f1ea25ff17b0f8'
    initial=source_pins();started=time.monotonic()
    emit('HEADER',phase=args.phase,product_ref='94b391d658b52035ae88e2da05f1ea25ff17b0f8',source_pins=initial)
    receipt={'status':'HARNESS_ERROR'}
    try:
        if args.phase=='prepare':
            prepare(OUT/'sealed-world')
            dump(OUT/'frozen-denominator.json',{'scenarios':[f'S{x:02}' for x in range(15)],'phases':PHASES,
              'genuine_trials':[{'trial':x,'status':'BLOCKED_ENVIRONMENT','reason':'NO_OS_CONFINED_FRESH_ACTOR'} for x in ['POS-1','POS-2','POS-3','NULL-1']]})
            receipt=suite(args.phase)
        elif args.phase=='world': receipt=world_run()
        elif args.phase=='spine': receipt=spine_run()
        elif args.phase=='seams': receipt=seams_run()
        elif args.phase=='finalize': receipt=finalize_run()
        else: receipt=suite(args.phase)
        assert source_pins()==initial
    except Exception as error:
        receipt={'status':'HARNESS_ERROR','error_type':type(error).__name__}
        dump(OUT/'campaign-error.json',receipt)
        raise
    finally:
        elapsed=round(time.monotonic()-started,6)
        emit('CAMPAIGN_TERMINAL',status=receipt['status'],phase=args.phase,seconds=elapsed,source_unchanged=source_pins()==initial)
    from scripts.prove_trading_core_operational_closure import peak_rss_bytes
    print(json.dumps({'phase':args.phase,'status':receipt['status'],'tests_run':receipt.get('tests_run'),
       'seconds':elapsed,'peak_rss_bytes':peak_rss_bytes()}))
    return 0 if receipt['status']=='PASS' else 1

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        ledger=OUT/'attempts.jsonl'
        terminal=json.loads(ledger.read_text().splitlines()[-1]) if ledger.exists() else {}
        if terminal.get('kind')!='CAMPAIGN_TERMINAL':
            emit('CAMPAIGN_TERMINAL',status='HARNESS_ERROR',error_type=type(error).__name__,source_unchanged='UNKNOWN')
        raise
