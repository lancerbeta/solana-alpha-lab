"""Replay evidence for contract freeze only; no empirical evaluator/store/API."""
from __future__ import annotations
import argparse
import copy
import hashlib
import itertools
import json
import math
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from fractions import Fraction as F
from pathlib import Path
import yaml

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'src'))
from solana_alpha_lab.factory.observation_schedule import canonical_sha256, parse_utc
from solana_alpha_lab.factory import hfic_research_scope as scope
from solana_alpha_lab.factory.opportunity_episodes import resolve_point
from probe_metadata import project_json

CONFIG=ROOT/'configs/list_a_chronological_confirmation_v1.yaml'
CONTRACT=ROOT/'docs/contracts/list_a_chronological_confirmation_v1.md'
TASK=ROOT/'docs/tasks/LIST_A_CONFIRMATION_PROTOCOL_FREEZE_V1.md'
BASE='ba87f8e339d5cc3aa55322801ae56e3f92369446'
NOT_READY='BOUND_CONTRACT_NOT_READY'


class UniqueLoader(yaml.SafeLoader): pass
def unique_mapping(loader,node,deep=False):
    result={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if key in result: raise ValueError('YAML_DUPLICATE_KEY')
        result[key]=loader.construct_object(value_node,deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)
def load_config(path=CONFIG):
    return yaml.load(path.read_text(encoding='utf-8'),Loader=UniqueLoader)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def require(condition,code):
    if not condition: raise ValueError(code)
def seed(core_hash,h): return int(hashlib.sha256(f'{core_hash}:{h}'.encode()).hexdigest()[:16],16)


def validate_design(cfg):
    require(sha(HERE/'source-contract.md')=='4931c4c569fb2630e9b403b33185bd86b9ffe9ff0df06dd9bb0bec41f5040510','OWNER_SOURCE_SPEC_HASH_MISMATCH')
    require(cfg['schema']=='smial.list-a-confirmation-protocol' and cfg['schema_version']=='1.0','SCHEMA_MISMATCH')
    core=cfg['protocol_core']; q=core['question']; inf=core['inference']; future=core['future_execution_contract']
    expected={'canonical_list_id':'JUPITER:toporganicscore:5m','population':'OPPORTUNITY_EPISODES',
              'membership_time':'EPISODE_T0','decision_point':'E1800','target_point':'E14400',
              'delta':'0','target_missingness_claim':'CONDITIONAL_ON_OBSERVED_TARGETS',
              'direction':'A_GREATER_THAN_COMPLEMENT','price_field_id':'FIELD-USD-PRICE-001',
              'coverage_policy':'REQUIRE_KNOWN_REFERENCED'}
    for key,value in expected.items(): require(q.get(key)==value,'QUESTION_DRIFT:'+key)
    require(q['list_condition']=={'all_of':['JUPITER:toporganicscore:5m']},'SELECTOR_DRIFT')
    require(core['purpose']=='FIRST_PREREGISTERED_TEST','PURPOSE_DRIFT')
    for key,value in {'replicates_per_partition':4096,'minimum_mints_overall':30,
                      'minimum_blocks_overall_each_partition':30,'minimum_mints_each_group':30,
                      'minimum_blocks_each_group_each_partition':30}.items():
        require(type(inf.get(key)) is int and inf[key]==value,'INTEGER_OR_SCREEN_DRIFT:'+key)
    require(inf['time_block_seconds']==[86400,172800] and all(type(x) is int for x in inf['time_block_seconds']),'PARTITION_DRIFT')
    for key,value in {'target_coverage_min':'0.95','missing_rate_gap_max':'0.05',
                      'method':'CROSSED_CLUSTER_PERCENTILE_BOOTSTRAP','quantile_method':'NEAREST_RANK_1BASED',
                      'seed_rule':'SHA256_PROTOCOL_CORE_COLON_BLOCK_SECONDS_FIRST16_HEX',
                      'empty_replicate_policy':'INSUFFICIENT_NO_REROLL',
                      'numeric_runtime':'CPYTHON_3_13_14_IEEE754_BINARY64_ORDERED_MATH_FSUM'}.items():
        require(inf.get(key)==value,'METHOD_DRIFT:'+key)
    require(inf['quantiles']==['0.025','0.975'],'QUANTILE_DRIFT')
    for key in ('calibrated_empirical_coverage_claim','missing_at_random_claim'): require(inf[key] is False,'STRONGER_CLAIM:'+key)
    for key in ('value_read_authorized','activation_authorized','reuse_exploratory_grant'): require(future[key] is False,'AUTHORITY_WIDENING:'+key)
    require(type(future['main_allowance']) is int and future['main_allowance']==1 and type(future['adaptive_allowance']) is int and future['adaptive_allowance']==0,'FUTURE_CAP_DRIFT')
    require(future['reserve_before_values'] is True and future['concurrent_evaluators_max']==1,'RESERVATION_CONTRACT_DRIFT')
    require(core['verdict']['supported']=='L24_GT_DELTA_AND_L48_GT_DELTA_AND_MIN_D_GT_DELTA','POSITIVE_RULE_DRIFT')
    require(core['verdict']['not_supported']=='U24_LE_DELTA_AND_U48_LE_DELTA_AND_MAX_D_LE_DELTA','NEGATIVE_RULE_DRIFT')
    require(core['verdict']['global_enum_mutation'] is False,'GLOBAL_ENUM_MUTATION')
    require(core['chronology']['comparison']=='VALIDATION_INFORMATION_START_STRICTLY_GREATER','CHRONOLOGY_DRIFT')
    metadata=json.loads((HERE/'metadata-bindings.json').read_text(encoding='utf-8'))
    definition=metadata['source_witnesses'][0]['list_a_definition']
    require(q['list_definition_sha256']==definition['definition_sha256'],'LIST_DEFINITION_BINDING_DRIFT')
    require(metadata['market_value_fields_deserialized']==0 and metadata['scientific_looks_created']==0,'SOURCE_SCOPE_VIOLATION')
    require(metadata['source_labels']['confirmatory_reuse_forbidden'] is True and metadata['first_blocker']=='CONFIRMATORY_REUSE_FORBIDDEN','ACTUAL_ROLE_RECEIPT_CONFLICT')
    return core


def fixture_readiness(meta):
    """Contract-only guard witness; assertions are NOT real provenance proof."""
    if meta.get('status')!='BOUND' or not meta.get('sources'): return NOT_READY,'SAMPLE_UNBOUND'
    if meta.get('confirmatory_reuse_forbidden') is not False: return NOT_READY,'CONFIRMATORY_REUSE_FORBIDDEN_OR_UNKNOWN'
    if meta.get('exposure')!='UNTOUCHED_COMPLETE_PROVENANCE' or meta.get('pending'): return NOT_READY,'EXPOSURE_UNRESOLVED_OR_PENDING'
    if meta.get('current_protection')!='EXACT_COMPATIBLE_SNAPSHOT': return NOT_READY,'CURRENT_PROTECTION_UNRESOLVED'
    if type(meta.get('potential_mints')) is not int or meta['potential_mints']<30 or min(meta.get('potential_blocks',[0]))<30: return NOT_READY,'INSUFFICIENT_POTENTIAL_SUPPORT'
    if not meta.get('chronology_valid'): return NOT_READY,'CHRONOLOGY_UNRESOLVED'
    return 'FROZEN_FOR_SEPARATE_AUTHORIZED_CONFIRMATION','SYNTHETIC_CONTRACT_WITNESS_ONLY'


def exact_fixture_source(frozen,inventory):
    matches=[row for row in inventory if row['cohort_id']==frozen['cohort_id'] and row['release_id']==frozen['release_id']]
    require(len(matches)==1,'EXACT_SOURCE_ABSENT_OR_AMBIGUOUS')
    require(matches[0]['source_sha256']==frozen['source_sha256'],'EXACT_SOURCE_HASH_CONFLICT')
    return matches[0]


def canonical_fixture_episodes(rows):
    """Contract-only duplicate witness; never opens actual episode values."""
    result={}
    for row in rows:
        key=row['episode_id']
        require(key not in result or result[key]==row,'CONFLICTING_EPISODE_COPY')
        result[key]=row
    return [result[key] for key in sorted(result)]


def actual_readiness(cfg,metadata):
    # This atom has no real approved scope/provenance producer. Never accept the
    # synthetic witness as actual source evidence or a toggle as a read grant.
    require(cfg['sample_binding']['status']=='UNBOUND' and cfg['sample_binding']['sources']==[], 'UNSUPPORTED_ACTUAL_SAMPLE_BINDING')
    reasons=[metadata['first_blocker']]
    if any(w['structural_feasibility']=='INSUFFICIENT_POTENTIAL_SUPPORT' for w in metadata['source_witnesses']): reasons.append('INSUFFICIENT_POTENTIAL_SUPPORT')
    reasons+=['EXACT_APPROVED_SAMPLE_SCOPE_AND_END_NOT_BOUND','COMPLETE_EXPOSURE_PROVENANCE_NOT_ESTABLISHED','CURRENT_PROTECTION_NOT_VALIDATED']
    return NOT_READY,reasons


def rule(ci24,ci48,diagnostics,*,bound=True,invalid=False,sufficient=True,delta=F(0)):
    if not bound:return NOT_READY
    if invalid:return 'INVALID_OR_BLOCKED'
    if not sufficient or not diagnostics:return 'INSUFFICIENT'
    vals=[*ci24,*ci48,*diagnostics]
    if any(isinstance(v,bool) or not math.isfinite(float(v)) for v in vals):return 'INSUFFICIENT'
    if ci24[0]>ci24[1] or ci48[0]>ci48[1]:return 'INVALID_OR_BLOCKED'
    if ci24[0]>delta and ci48[0]>delta and min(diagnostics)>delta:return 'ASSOCIATION_SUPPORTED_CONDITIONAL'
    if ci24[1]<=delta and ci48[1]<=delta and max(diagnostics)<=delta:return 'ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY'
    return 'INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION'


def tests(cfg):
    cases=[]
    def check(name,actual,expected,fidelity='CONTRACT_ONLY'):
        require(actual==expected,'ORACLE_FAILED:'+name)
        cases.append({'id':name,'expected':expected,'actual':actual,'status':'PASS','fidelity':fidelity})
    meta=json.loads((HERE/'metadata-bindings.json').read_text(encoding='utf-8'))
    e=scope.MembershipEvidence(); e.add_definition(meta['source_witnesses'][0]['list_a_definition'])
    selector=scope.canonical_list_condition({'clauses':[{'all_of':['A']}]},e,aliases={'A':'JUPITER:toporganicscore:5m'})
    a='JUPITER:toporganicscore:5m'; b='JUPITER:toptraded:5m'
    for name,states,expected in [('A',{a:'TRUE'},'TRUE'),('AB',{a:'TRUE',b:'TRUE'},'TRUE'),('B',{a:'FALSE',b:'TRUE'},'FALSE'),('UNKNOWN',{b:'TRUE'},'UNKNOWN')]:
        check('NATIVE_MEMBERSHIP_'+name,scope.evaluate_selector(selector,states),expected,'SEGMENT_PRODUCT_PATH_SYNTHETIC')
    log=[]; projected=project_json('{"cohort_id":"W-VALID","PRICE":{"TRIPWIRE":[999]},"target_observed":true,"observation_field_state_counts":{"missing":999}}',{'cohort_id':True},log)
    check('ALLOWLIST_IGNORES_VALUE_TOKENS',projected,{'cohort_id':'W-VALID'})
    check('VALUE_TOKEN_ACCESS_LOG',log,['/cohort_id'])
    good={'status':'BOUND','sources':['SYNTHETIC-SOURCE'],'confirmatory_reuse_forbidden':False,'exposure':'UNTOUCHED_COMPLETE_PROVENANCE','pending':False,'current_protection':'EXACT_COMPATIBLE_SNAPSHOT','potential_mints':60,'potential_blocks':[30,30],'chronology_valid':True}
    check('POSITIVE_GUARD_NON_VACUOUS',fixture_readiness(good)[0],'FROZEN_FOR_SEPARATE_AUTHORIZED_CONFIRMATION')
    for key,value,reason in [('exposure','UNKNOWN','EXPOSURE_UNRESOLVED_OR_PENDING'),('pending',True,'EXPOSURE_UNRESOLVED_OR_PENDING'),('current_protection','UNKNOWN','CURRENT_PROTECTION_UNRESOLVED'),('confirmatory_reuse_forbidden',True,'CONFIRMATORY_REUSE_FORBIDDEN_OR_UNKNOWN'),('potential_mints',24,'INSUFFICIENT_POTENTIAL_SUPPORT')]:
        changed={**good,key:value}; check('GUARD_'+key,fixture_readiness(changed),(NOT_READY,reason))
    check('FALSE_HOLDOUT_NOT_UNTOUCHED',fixture_readiness({**good,'holdout':False,'exposure':'UNKNOWN'}),(NOT_READY,'EXPOSURE_UNRESOLVED_OR_PENDING'))
    check('STRICTER_CURRENT_PROTECTION_REFUSED',fixture_readiness({**good,'current_protection':'PROTECTED_STRICTER'}),(NOT_READY,'CURRENT_PROTECTION_UNRESOLVED'))
    check('POTENTIAL_BLOCK_SCREEN_REFUSED',fixture_readiness({**good,'potential_blocks':[60,7]}),(NOT_READY,'INSUFFICIENT_POTENTIAL_SUPPORT'))
    reordered={key:cfg['protocol_core'][key] for key in reversed(cfg['protocol_core'])}
    core_hash=canonical_sha256(cfg['protocol_core'])
    check('CORE_REORDER_SAME',canonical_sha256(reordered),core_hash)
    changed=copy.deepcopy(cfg['protocol_core']); changed['question']['delta']='0.01'
    check('MEANING_CHANGE_DIFFERENT_CORE',canonical_sha256(changed)!=core_hash,True)
    changed=copy.deepcopy(cfg['protocol_core']);changed['inference']['time_block_seconds']=[86400,259200]
    check('BLOCK_CHANGE_DIFFERENT_CORE',canonical_sha256(changed)!=core_hash,True)
    bad=copy.deepcopy(cfg);bad['protocol_core']['inference']['replicates_per_partition']=True
    try:validate_design(bad);bool_refused=False
    except ValueError:bool_refused=True
    check('BOOL_NOT_INTEGER',bool_refused,True)
    frozen={'cohort_id':'SYNTHETIC-OLD','release_id':'r1','source_sha256':'a'*64}
    inventory=[frozen,{'cohort_id':'SYNTHETIC-NEWER','release_id':'r2','source_sha256':'b'*64}]
    check('NEW_UNRELATED_SOURCE_NO_FROZEN_SET_CHANGE',exact_fixture_source(frozen,inventory),frozen)
    try:exact_fixture_source(frozen,[{**frozen,'source_sha256':'b'*64}]);conflict=False
    except ValueError as error:conflict=str(error)=='EXACT_SOURCE_HASH_CONFLICT'
    check('EXACT_SOURCE_CHANGED_HASH_REFUSED',conflict,True)
    first={'episode_id':'SYNTHETIC-1','mint':'SYNTHETIC-MINT','membership':'TRUE'}
    check('IDENTICAL_EPISODE_COPY_DEDUP',canonical_fixture_episodes([first,first]),[first])
    try:canonical_fixture_episodes([first,{**first,'membership':'FALSE'}]);duplicate_conflict=False
    except ValueError as error:duplicate_conflict=str(error)=='CONFLICTING_EPISODE_COPY'
    check('CONFLICTING_EPISODE_COPY_REFUSED',duplicate_conflict,True)
    check('SOURCE_CHANGE_DIFFERENT_SAMPLE',canonical_sha256({'sources':['x'],'source_sha256':'a'*64})!=canonical_sha256({'sources':['x'],'source_sha256':'b'*64}),True)
    for h in (86400,172800):check('SEED_INDEPENDENT_BYTES_'+str(h),seed(core_hash,h),int.from_bytes(hashlib.sha256(f'{core_hash}:{h}'.encode()).digest()[:8],'big'))
    for p,expected in [(F(25,1000),103),(F(975,1000),3994)]:check('NEAREST_RANK_'+str(p),math.ceil(p*4096),expected,'MODEL_ONLY')
    check('POSITIVE_MEAN',str((F(1,10)+F(1,5))/2-(F(0)+F(-1,10))/2),'1/5','MODEL_ONLY')
    check('NEGATIVE_MEAN',str((F(-1,10)+F(-1,5))/2-(F(0)+F(1,10))/2),'-1/5','MODEL_ONLY')
    check('EPISODE_NOT_CLUSTER_WEIGHT',str((F(1,10)*3+F(9,10))/4),'3/10','MODEL_ONLY')
    valid=[];empty=0
    for md,td in itertools.product(itertools.product(range(2),repeat=2),repeat=2):
        mint=[md.count(i) for i in range(2)]; time=[td.count(i) for i in range(2)]
        if not all(mint):empty+=1;continue
        means=[]
        for group,returns in enumerate(((F(1,10),F(1,5)),(F(0),F(1,10)))):
            means.append(sum(returns[i]*mint[group]*time[i] for i in range(2))/(mint[group]*sum(time)))
        valid.append(means[0]-means[1])
    check('CROSSED_CHOICES',(len(valid),empty),(8,8),'MODEL_ONLY');check('SHARED_GROUP_WEIGHT_MEANS',all(v==F(1,10) for v in valid),True,'MODEL_ONLY')
    decision=datetime(2026,1,1,0,30,tzinfo=UTC); target=datetime(2026,1,1,4,5,tzinfo=UTC)
    boundary=max(target,decision+timedelta(seconds=14700))
    check('BOUNDARY_ANCHOR',boundary.isoformat(),'2026-01-01T04:35:00+00:00','MODEL_ONLY')
    check('STRICT_EQUALITY_REFUSED',boundary>boundary,False)
    check('OVERLAP_REFUSED',boundary-timedelta(seconds=1)>boundary,False)
    try:parse_utc('2026-01-01T04:35:00');naive=False
    except ValueError:naive=True
    check('NATIVE_NAIVE_TIME_REFUSED',naive,True,'SEGMENT_PRODUCT_PATH_SYNTHETIC')
    binding=meta['lineage_metadata']['cohorts'][0]['schedule_binding']
    point=resolve_point(binding,datetime(2026,1,1,tzinfo=UTC),'E14400')
    check('NATIVE_TARGET_DEADLINE',point.availability_deadline.isoformat(),'2026-01-01T04:05:00+00:00','SEGMENT_PRODUCT_PATH_SYNTHETIC')
    check('NOMINAL_HOLDING',14400-1800,12600,'MODEL_ONLY')
    check('14_DAY_BLOCK_UPPER_ALIGNED',14//2,7,'MODEL_ONLY')
    check('KNOWN_ACTUAL_UPPER_BELOW_SUPPORT',meta['source_witnesses'][0]['potential_mints_upper_bound']<30,True,'SEGMENT_PRODUCT_PATH_METADATA')
    check('COVERAGE_EXACT_190',F(190,200)>=F(95,100),True,'MODEL_ONLY');check('COVERAGE_EXACT_189',F(189,200)>=F(95,100),False,'MODEL_ONLY')
    tuples=[('SUPPORTED',(1,2),(1,3),[1],{},'ASSOCIATION_SUPPORTED_CONDITIONAL'),('NEGATIVE',(-2,0),(-3,0),[0],{},'ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY'),('48H_CROSS',(1,2),(-1,3),[1],{},'INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION'),('LEAVE_ONE_ZERO',(1,2),(1,2),[0],{},'INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION'),('TINY',(1,2),(1,2),[1],{'sufficient':False},'INSUFFICIENT'),('INVALID',(1,2),(1,2),[1],{'invalid':True},'INVALID_OR_BLOCKED'),('UNBOUND_PRECEDENCE',(1,2),(1,2),[1],{'bound':False,'invalid':True},NOT_READY),('EMPTY',(1,2),(1,2),[],{},'INSUFFICIENT')]
    for name,c24,c48,ds,flags,expected in tuples:check('RULE_'+name,rule(c24,c48,ds,**flags),expected)
    return cases


def readback(config_path=CONFIG):
    cfg=load_config(config_path);core=validate_design(cfg)
    require(cfg['fingerprints']['protocol_core_sha256']==canonical_sha256(core),'CORE_HASH_MISMATCH')
    require(cfg['fingerprints']['sample_binding_sha256']==canonical_sha256(cfg['sample_binding']),'SAMPLE_HASH_MISMATCH')
    require(cfg['derived_seeds']=={str(h):seed(canonical_sha256(core),h) for h in core['inference']['time_block_seconds']},'SEED_HASH_MISMATCH')
    meta=json.loads((HERE/'metadata-bindings.json').read_text(encoding='utf-8'))
    require(cfg['sample_binding']['metadata_evidence_sha256']==sha(HERE/'metadata-bindings.json'),'METADATA_RECEIPT_HASH_MISMATCH')
    receipt=json.loads((HERE/'freeze-receipt.json').read_text(encoding='utf-8'))
    for key,path in [('config_raw_sha256',config_path),('contract_raw_sha256',CONTRACT),('source_spec_raw_sha256',HERE/'source-contract.md'),('accepted_task_raw_sha256',TASK),('metadata_evidence_raw_sha256',HERE/'metadata-bindings.json')]:require(receipt[key]==sha(path),'RAW_BINDING_MISMATCH:'+key)
    identity={k:receipt[k] for k in ('protocol_core_sha256','sample_binding_sha256','accepted_task_raw_sha256','source_spec_raw_sha256','metadata_evidence_raw_sha256','validation_sha256')}
    require(receipt['freeze_receipt_identity_sha256']==canonical_sha256(identity),'FREEZE_RECEIPT_HASH_MISMATCH')
    require(receipt['validation_sha256']==sha(HERE/'validation.json'),'VALIDATION_HASH_MISMATCH')
    terminal,reasons=actual_readiness(cfg,meta)
    require(receipt['result']==terminal and receipt['binding_gaps']==reasons,'TERMINAL_READBACK_CONFLICT')
    return {'status':'PASS_COLD_ARTIFACT_CONSUMER','result':terminal,'binding_gaps':reasons,'protocol_core_sha256':canonical_sha256(core),'sample_binding_sha256':canonical_sha256(cfg['sample_binding']),'non_claims':core['non_claims'],'market_values_read':0,'scientific_looks':0}


def seal():
    cfg=load_config(); validate_design(cfg)
    owners=['hfic_research_scope.py','hfic_temporal_discovery.py','opportunity_episodes.py','observation_schedule.py','live_cohort_schedule_artifact.py']
    cfg['protocol_core']['source_owners']={f'src/solana_alpha_lab/factory/{name}':{'commit':BASE,'git_blob_sha256':hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'show',f'{BASE}:src/solana_alpha_lab/factory/{name}'])).hexdigest()} for name in owners}
    cfg['sample_binding']['metadata_evidence_sha256']=sha(HERE/'metadata-bindings.json')
    cfg['fingerprints']={'protocol_core_sha256':canonical_sha256(cfg['protocol_core']),'sample_binding_sha256':canonical_sha256(cfg['sample_binding'])}
    cfg['derived_seeds']={str(h):seed(cfg['fingerprints']['protocol_core_sha256'],h) for h in (86400,172800)}
    CONFIG.write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8',newline='\n')
    cases=tests(cfg);dump(HERE/'validation.json',{'scope':'CONTRACT_MODEL_AND_NAMED_SAFE_NATIVE_METADATA_PARSER_SEAMS','cases':cases,'product_confirmer_tests':'NOT_IMPLEMENTED_NOT_EXECUTED','scientific_looks':0})
    meta=json.loads((HERE/'metadata-bindings.json').read_text(encoding='utf-8'));terminal,reasons=actual_readiness(cfg,meta)
    receipt={**cfg['fingerprints'],'result':terminal,'design':'DESIGN_VALIDATED','binding_gaps':reasons,'accepted_task_raw_sha256':sha(TASK),'source_spec_raw_sha256':sha(HERE/'source-contract.md'),'metadata_evidence_raw_sha256':sha(HERE/'metadata-bindings.json'),'validation_sha256':sha(HERE/'validation.json'),'config_raw_sha256':sha(CONFIG),'contract_raw_sha256':sha(CONTRACT),'market_values_read':0,'scientific_looks':0,'runtime_writes':0,'provider_calls':0,'future_look_authorized':False}
    receipt['freeze_receipt_identity_sha256']=canonical_sha256({k:receipt[k] for k in ('protocol_core_sha256','sample_binding_sha256','accepted_task_raw_sha256','source_spec_raw_sha256','metadata_evidence_raw_sha256','validation_sha256')})
    dump(HERE/'freeze-receipt.json',receipt)
    print(json.dumps({'status':'SEALED_LIMITED_DESIGN','result':terminal,'checks':len(cases)}))


def canaries():
    baseline=readback(); results=[]
    with tempfile.TemporaryDirectory(prefix='list_a_contract_canary_') as temp:
        candidate=Path(temp)/'config.yaml'; raw=CONFIG.read_bytes()
        candidate.write_bytes(raw.replace(b"delta: '0'",b"delta: '1'"))
        require(candidate.read_bytes()!=raw,'CANARY_MUTATION_NOT_APPLIED')
        completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--verify','--config',str(candidate)],capture_output=True,text=True)
        require(completed.returncode!=0 and 'QUESTION_DRIFT:delta' in completed.stdout,'CANARY_DID_NOT_REACH_GUARD')
        results.append({'canary':'SAME_SHAPE_DELTA_TAMPER','returncode':completed.returncode,'detected_by':'QUESTION_DRIFT:delta'})
        modified=load_config();modified['fingerprints']['protocol_core_sha256']=sha(CONFIG)
        candidate.write_text(yaml.safe_dump(modified,sort_keys=False),encoding='utf-8')
        completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--verify','--config',str(candidate)],capture_output=True,text=True)
        require(completed.returncode!=0 and 'CORE_HASH_MISMATCH' in completed.stdout,'HASH_DOMAIN_CANARY_NOT_DETECTED')
        results.append({'canary':'RAW_CONFIG_HASH_AS_PROTOCOL_CORE','returncode':completed.returncode,'detected_by':'CORE_HASH_MISMATCH'})
        candidate.write_bytes(raw[:-40]);completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--verify','--config',str(candidate)],capture_output=True,text=True)
        require(completed.returncode!=0,'TRUNCATION_CANARY_NOT_DETECTED');results.append({'canary':'TRUNCATED_PERSISTED_CONFIG','returncode':completed.returncode})
    dump(HERE/'cold-readback.json',{'consumer':baseline,'adversarial_canaries':results,'owned_temp_root_removed':not Path(temp).exists(),'future_confirmer_reservation_tests':'NOT_EXECUTED_OUT_OF_SCOPE'})
    print(json.dumps({'status':'PASS_COLD_AND_TAMPER_CANARIES','result':baseline['result'],'temp_removed':not Path(temp).exists()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--seal',action='store_true');mode.add_argument('--verify',action='store_true');mode.add_argument('--canaries',action='store_true');parser.add_argument('--config',type=Path,default=CONFIG)
    args=parser.parse_args()
    try:
        if args.seal:seal()
        elif args.canaries:canaries()
        else:print(json.dumps(readback(args.config),ensure_ascii=False,allow_nan=False))
    except (ValueError,KeyError,TypeError,IndexError,yaml.YAMLError) as error:
        import re
        reason=str(error) if isinstance(error,ValueError) and re.fullmatch(r'[A-Z0-9_]+(?::[A-Za-z0-9_.]+)?',str(error)) else 'CONFIG_PARSE_OR_REQUIRED_FIELD_INVALID'
        print(json.dumps({'status':'NOT_READY_CHECK_FAILED','reason':reason}));sys.exit(1)
