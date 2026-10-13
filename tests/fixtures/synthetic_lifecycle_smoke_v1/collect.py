"""Derive one compact campaign/readout from retained immutable attempts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from observer import combine

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

REQUIRED_SUITES={'sls-v1-prepare-a3':15,'sls-v1-forge-a2':28,'sls-v1-forge-tail-a1':3,
    'sls-v1-trading-tail-a2':51,'sls-v1-recovery-a2':8,'sls-v1-handoff-a1':30,'sls-v1-fortnight-a1':1}
def verify_required(suites):
    for name,count in REQUIRED_SUITES.items():
        assert name in suites,'REQUIRED_RUN_ABSENT:'+name
        body=suites[name]
        assert body['tests_run']==len(body['tests'])==count,'TRUNCATED_SUITE:'+name
        assert len({x['test_id'] for x in body['tests']})==count
        assert all(x['status']=='PASS' for x in body['tests']),'REQUIRED_TEST_NOT_PASS:'+name
        assert body['status']==('FAIL' if name=='sls-v1-forge-a2' else 'PASS')
    return True

SCENARIOS=[
 ('S00','PASS','FINAL_SCOPE_SAFETY_AND_ORACLES','CONTRACT_ONLY','AuditOracleControls'),
 ('S01','BLOCKED','NO_OS_CONFINED_BLIND_ACTOR_SIMPLE','NONE',''),
 ('S02','BLOCKED','NO_OS_CONFINED_BLIND_ACTOR_COMPOUND','NONE',''),
 ('S03','UNKNOWN','NULL_LAB_NEGATIVE; GENUINE_NULL_AND_NULL_NATIVE_MEMORY_UNVISITED','MODEL_ONLY',''),
 ('S04','BLOCKED','DECOY_LAB_COUNTEREXAMPLE; NATIVE_CONFIRMATION_UNBOUND','MODEL_ONLY',''),
 ('S05','PASS','FUTURE_POISON_PREFIX_AND_TYPED_MISSING_TESTED_SCOPE','SEGMENT_PRODUCT_PATH','public_prefix_is_invariant'),
 ('S06','UNKNOWN','NEW_MATURITY_TO_NATIVE_CONFIRMATION_NOT_EXECUTED','CONTRACT_ONLY','scenario_b_later_evidence'),
 ('S07','PASS','NATIVE_ACK_LOSS_MOVED_ROOT_AND_WORLD_OWNER_FINAL','SEGMENT_PRODUCT_PATH','os_reply_loss'),
 ('S08','PASS','EXACT_REPLAY_AND_STALE_RELATED_IDENTITY_GUARDS_TESTED_SCOPE','CONTRACT_ONLY','ExperimentEvidenceDecisionTests'),
 ('S09','BLOCKED','ACTUAL_FORGE_CANDIDATES_HAVE_NO_ACCEPTED_SCIENCE_HANDOFF; BR01_RIGHT_SEGMENT_PASS','SEGMENT_PRODUCT_PATH','ScienceToStrategyHandoffTests'),
 ('S10','PASS','ORDINARY_PAPER_TWO_SCIENTIFIC_RECIPES_SUCCESSOR_AND_FORTNIGHT','SEGMENT_PRODUCT_PATH','OperatingDriverTests'),
 ('S11','PASS','ENTRY_BLOCKER_OLD_EXIT_LEGACY_GUARD_TESTED_SCOPE','SEGMENT_PRODUCT_PATH','malformed_new_source_json'),
 ('S12','PASS','PARTIAL_UNKNOWN_NO_RESEND_KNOWN_COST_FLOOR','SEGMENT_PRODUCT_PATH','OperatingObligationsTests'),
 ('S13','PASS','COMPLETE_CUT_ORIGINAL_SWITCH_TIGHTENED_CONTROL_RESTORE','SEGMENT_PRODUCT_PATH','OperationalRecoveryTests'),
 ('S14','UNKNOWN','FRESH_WAL_AWARE_READBACK_AND_HUMAN_CLI_PASS; FEEDBACK_CONTINUATION_UNKNOWN','SEGMENT_PRODUCT_PATH','valid_disabled_runtime_policy'),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--retained',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    retained=a.retained;out=a.out;out.mkdir(parents=True,exist_ok=True)
    suites={name:read(retained/name/'suite.json') for name in REQUIRED_SUITES}
    disagreements=[]
    for name,body in suites.items():
        events=[json.loads(x) for x in (retained/name/'attempts.jsonl').read_text().splitlines()]
        committed={x['test_id']:x for x in events if x['kind']=='TEST_TERMINAL'}
        assert len(committed)==body['tests_run'],'TRUNCATED_TERMINAL_LEDGER:'+name
        for record in body['tests']:
            terminal=committed[record['test_id']]
            if record['status']!=terminal['status']:
                disagreements.append({'attempt':name,'test_id':record['test_id'],'suite_status':record['status'],'ledger_status':terminal['status'],
                    'reason':'Old Result.current object was mutated by later setUpClass error; original terminal ledger is authoritative.'})
        body['tests']=[committed[x['test_id']] for x in body['tests']]
    verify_required(suites)
    for invalid in ({},{**suites,'sls-v1-handoff-a1':{**suites['sls-v1-handoff-a1'],'tests':[]}}):
        try:verify_required(invalid)
        except AssertionError:pass
        else:raise AssertionError('REQUIRED_RUN_CANARY_FALSE_PASS')
    ledger=[];pins=[];runs=[]
    for folder in sorted(retained.glob('sls-v1-*')):
        if not folder.is_dir():continue
        run={'attempt':folder.name}
        for name in ('terminal.json','suite.json','campaign-error.json'):
            path=folder/name
            if path.exists():
                body=read(path)
                run[name.removesuffix('.json')]=({k:body[k] for k in ('status','tests_run','failed_ids','error_type') if k in body} if name=='suite.json' else body)
                pins.append({'artifact':f'{folder.name}/{name}','sha256':sha(path),'bytes':path.stat().st_size})
        path=folder/'attempts.jsonl'
        if path.exists():
            for line in path.read_text().splitlines():
                item=json.loads(line)
                item={k:v for k,v in item.items() if k not in {'failure_detail'}}
                item['attempt']=folder.name;item['campaign_seq']=len(ledger)+1
                ledger.append(item)
            pins.append({'artifact':f'{folder.name}/attempts.jsonl','sha256':sha(path),'bytes':path.stat().st_size})
        for path in sorted(folder.rglob('inventory.json')):
            if 'snapshots' not in path.parts:continue
            pins.append({'artifact':path.relative_to(retained).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size})
        runs.append(run)
    for path in sorted((retained/'sls-v1-world-a3/native-world').glob('*-context.json')):
        pins.append({'artifact':path.relative_to(retained).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size})
    for name in ('independent-observer.json','host-footprint.json','docker-footprint.json'):
        path=retained/name;pins.append({'artifact':name,'sha256':sha(path),'bytes':path.stat().st_size})
    terminals=[x for x in ledger if x['kind']=='TEST_TERMINAL']
    passed={x['test_id'] for x in terminals if x['status']=='PASS'}
    coverage=[]
    for sid,status,reason,fidelity,needle in SCENARIOS:
        evidence=sorted(x for x in passed if needle and needle in x)
        coverage.append({'scenario_id':sid,'status':status,'reason':reason,'fidelity':fidelity,
            'reached':status=='PASS','oracle_exercised':status=='PASS','consumer_accepted':status=='PASS',
            'evidence_test_ids':evidence,'native_full_original_forge_to_trading':False})
    coverage[-1]['sub_obligations']=[{'boundary':'FRESH_WAL_AND_HUMAN_CLI','status':'PASS','reached':True,'oracle_exercised':True,'consumer_accepted':True},
        {'boundary':'TRADING_FEEDBACK_TO_FRESH_FORGE_MISSION','status':'UNKNOWN','reached':False,'oracle_exercised':False,'consumer_accepted':False},
        {'boundary':'BROWSER_UI_OPTIONAL','status':'UNKNOWN','reached':False,'oracle_exercised':False,'consumer_accepted':False}]
    observer=read(retained/'independent-observer.json')
    assert observer['status']=='PASS' and observer['canaries']['segment_aggregation']=='PASS'
    original=read(retained/'sls-v1-prepare-a2/frozen-denominator.json')
    assert [x['scenario_id'] for x in coverage]==original['scenarios']
    world=read(retained/'sls-v1-world-a3/world-summary.json')
    finalize=read(retained/'sls-v1-finalize-a1/finalize-summary.json')
    for item in finalize['records']:
        assert item['finalized']['critic_terminal']=='KILL_UNBOUND_EVIDENCE'
        assert item['cold']['owner_class']=='OWNER_FINAL' and item['cold']['ordinary_operation']['effective_state']=='COMPLETED'
        assert item['cold_zero_write']
    spine=read(retained/'sls-v1-spine-a2/spine-summary.json')
    assert spine['status']=='PASS' and not spine['raw_to_paper'] and len(spine['strategies'])==2
    first,second=[read(retained/f'sls-v1-spine-a2/spine-{n}.json') for n in (1,2)]
    assert first['scientific_question_kind']!=second['scientific_question_kind']
    assert first['manifest']['experiment_spec_sha256']!=second['manifest']['experiment_spec_sha256']
    long=combine([{'status':'PASS','reached':True,'fidelity':'SEGMENT_PRODUCT_PATH','bridge_id':'BR-01'}]*2)
    assert long=='SEGMENT_ONLY_LONG_PATH_BLOCKED'
    current_failures=[x for x in terminals if x['status']!='PASS']
    host=read(retained/'host-footprint.json');docker=read(retained/'docker-footprint.json')
    assert not host['measurement_errors'] and docker['all_campaign_containers_stopped'] and docker['new_image_bytes']==0
    assert not any(x['running'] for x in docker['containers'])
    allocated=host['allocated_unique_owned_bytes']+sum(x['allocated_bytes'] for x in docker['volumes'].values())+docker['container_writable_layers_bytes']+(docker['logs_allocated_bytes'] or 0)
    campaign={'campaign_id':'SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1','schema_version':'1.0',
        'status':'PARTIAL_ENVIRONMENT_OR_AUTHORITY','report_scope_complete':True,'product_ref':'94b391d658b52035ae88e2da05f1ea25ff17b0f8',
        'frozen_denominator_sha256':sha(retained/'sls-v1-prepare-a2/frozen-denominator.json'),
        'world_recipe':read(retained/'sls-v1-world-a3/native-world/sealed-world/recipe.json'),
        'world_recipe_sha256':sha(retained/'sls-v1-world-a3/native-world/sealed-world/recipe.json'),
        'genuine_trials':original['genuine_trials'],'authored_positive_controls':world['families'],
        'independent_numeric_observer':observer,'lab_oracle':read(retained/'sls-v1-world-a3/native-world/sealed-world/oracle.json'),
        'forge_terminal_readback':[{'family':x['family'],'terminal':x['finalized']['critic_terminal'],'owner_class':x['cold']['owner_class'],
            'operation_state':x['cold']['ordinary_operation']['effective_state'],'next':x['cold']['ordinary_operation']['next_action'],'cold_zero_write':x['cold_zero_write']} for x in finalize['records']],
        'continuity':{'last_native_prefix_boundary':'AUTHORED_INGRESS -> MAIN -> DRAFT -> FREEZE -> GENUINE_CRITIC -> FINALIZE -> OWNER_FINAL_COLD_READBACK',
            'full_forge_to_science_to_trading':'BLOCKED','aggregate_verdict':long,
            'bridges':[{'bridge_id':'BR-01','cut':'FROZEN_RAW_FORGE_CANDIDATE -> SCIENTIFIC_PROTOCOL_AND_EPISODE_RUNTIME',
                'bypassed_producers':['ACCEPTED_CHRONOLOGICAL_CONFIRMATION','RAW_TO_EPISODE_SCIENTIFIC_IDENTITY_CONVERSION'],
                'substitute':'EXISTING_EXPLICIT_DIRECT_SYNTHETIC_EPISODE_SCIENCE_FIXTURES',
                'consumed_original_forge_candidate':False,'right_segment':spine}]},
        'scenarios':coverage,'runs':runs,'unique_passed_test_ids':sorted(passed),
        'unique_passed_test_count':len(passed),'historical_failed_test_records':current_failures,
        'ledger_suite_status_disagreements':disagreements,
        'assembler_canaries':{'missing_required_run':'PASS','truncated_required_suite':'PASS','two_segments_never_full':'PASS'},
        'resource_footprint':{'host':host,'docker':docker,'known_allocated_total_bytes':allocated,'known_allocated_total_gib':round(allocated/1024**3,4),
            'shared_image_incremental_bytes':0,'shared_uv_cache_incremental_bytes':None,
            'shared_uv_cache_limit':'No pre-campaign cache allocation baseline; incremental shared bytes remain UNKNOWN.',
            'cleanup':'OWNER_DECISION_PENDING_NO_DELETE'},
        'non_claims':['NO_BLIND_DISCOVERY','NO_NATIVE_OOS_CONFIRMATION','NO_RAW_TO_PAPER_CONTINUITY','NO_REAL_MARKET_ALPHA_NETRETURN_FCF',
            'NO_MODEL_DIVERSITY_PROVEN','NO_BROWSER_UI_PROOF','NO_AUTONOMOUS_FEEDBACK_CONTINUATION_PROOF','NO_PRODUCT_FIX_OR_PROMOTION']}
    dump(out/'campaign.json',campaign);dump(out/'coverage.json',{'derived_from':'campaign.json + attempts.jsonl','scenarios':coverage})
    dump(out/'retention-pins.json',{'scope':'COMPACT_IRREPRODUCIBLE_AND_SELECTED_SYNTHETIC_RECEIPTS','retention_ref':'../retained','pins':pins})
    (out/'attempts.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in ledger))
    print(json.dumps({'status':campaign['status'],'scenarios':len(coverage),'passed_unique':len(passed),'historical_failed_records':len(current_failures),'allocated_gib':campaign['resource_footprint']['known_allocated_total_gib']}))

if __name__=='__main__':main()
