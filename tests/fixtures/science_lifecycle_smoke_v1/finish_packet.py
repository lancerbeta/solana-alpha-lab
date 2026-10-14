"""Derive the partial checkpoint from saved evidence and owned resource measurements."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def finish(evidence, runtime):
    assert (runtime/'.science-owner').read_text()=='SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1'
    output=runtime/'output'
    host=load(output/'host-footprint.json');volumes=load(output/'volume-footprint-latest.json')
    docker=load(output/'container-attempts.json')
    assert host['measurement_errors']==[]
    native_bytes=(output/'native-attempts-final.jsonl').read_bytes()
    native=[json.loads(line) for line in native_bytes.decode().splitlines()]
    numeric=load(evidence/'numerical.json');readback=load(evidence/'readback.json')
    from chronology_oracle import verify as verify_chronology
    assert verify_chronology(load(evidence/'chronology-geometry.json'))
    counts={kind:sum(r['kind']==kind for r in native) for kind in ('main','evaluator','confirmation')}
    assert counts==numeric['charges']=={'main':4,'evaluator':8,'confirmation':0}
    # Join operational failures without turning them into extra scientific charges.
    events=[{'ledger_kind':'native_charge','event':r} for r in native]+docker['operations']
    events += [{'ledger_kind':'pre_container_environment_attempt','attempt':name,
        'status':'INVALID_ENVIRONMENT_OR_HARNESS','scientific_charges':0,
        'timestamp':'UNKNOWN','retained':'HOST_TOOL_HISTORY; no product called'} for name in (
        'docker-user-installation-detection','docker-hidden-start-listener-failure',
        'git-local-snapshot-clone-sandbox-failure','context-route-enum-correction',
        'context-stale-main-rebind','context-future-evidence-path-correction')]
    (evidence/'attempts.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in events),encoding='utf-8')
    binding=load(evidence/'source-binding.json')
    binding['native_ledger_sha256']=hashlib.sha256(native_bytes).hexdigest()
    binding['chronology_geometry_sha256']=hashlib.sha256((evidence/'chronology-geometry.json').read_bytes()).hexdigest()
    binding['ledger_fidelity']='Original native sequence plus separately clocked owned operations; not an invented total causal order'
    write(evidence/'source-binding.json',binding)
    known=host['allocated_unique_bytes']+volumes['allocated_unique_bytes']+docker['container_rw_known_bytes']
    write(evidence/'footprint.json',{'host':host,'owned_volumes':volumes,
        'owned_container_metadata':{k:v for k,v in docker.items() if k!='operations'},
        'known_owned_file_allocation_bytes':known,'known_test_environment_excluding_checkout_bytes':known-host['groups']['elected_checkout']['allocated_unique_bytes'],
        'frozen_cap_bytes':536870912,'known_file_remaining_bytes':536870912-known,
        'shared_preexisting_image_bytes':533691498,'new_image_build_or_pull_bytes':0,
        'allocation_scope':'File blocks, identity-deduplicated; directory metadata and Docker log allocation UNKNOWN; not physical VHD growth',
        'no_automatic_cleanup':True})
    coverage={}
    for key in ('SC00','SC01','SC02','SC03','SC04','SC05A','SC05B','SC07','SC08'):
        coverage[key]={'status':'PASS_ENGINEERING','scope':'See native numerical/readback receipts'}
    coverage['SC00']['scope']='Actual OS/child canaries; scripted upstream, no blind Actor'
    coverage['SC01']['scope']='Primary corrected base-v3 Spec1.4 LIST/MIXED numerical artifact+passport+atomic records; independent 20-cell E1800/E14400 metadata chronology'
    coverage['SC02']['scope']='Fresh-container exact replay for both corrected specs, no evaluator/target decode or business write'
    for key in ('SC03','SC04','SC05A','SC05B'):
        coverage[key]['scope']='base-v2 persistence/guard segment; same frozen recipe/source/masks as corrected v3; quote prose invalidated for science'
    coverage['SC06']={'status':'BLOCKED_BUDGET','scope':'No changed-world capture/MAIN/numeric attempt; standard fresh world ~43 MiB before classification; insufficient frozen allocation'}
    coverage['SC07']['scope']='Actual corrected A RUN_COMPLETED DIRECT -> ordinary dossier COMPLETED/BLOCKED/PAUSE; cold identical decision zero writes'
    coverage['SC08']['scope']='Foreign run excluded by conflicting identity, same-hypothesis PAUSE RELATED; actual stale and PROMOTE guards zero forbidden writes'
    coverage['SC09']={'status':'PASS_REACHABILITY_PROBE','scope':'Pinned accepted registry, actual dispatch, accepted contract and substantive consumer; no sample values read'}
    for key in ('SC10','SC11','SC12'):
        coverage[key]={'status':'BLOCKED_PRODUCT_CONTRACT','scope':'Accepted chronological confirming producer/pre-values reservation missing; no custom confirmer'}
    write(evidence/'summary.json',{'campaign':'SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1','tested_git_sha':numeric['tested_git_sha'],
        'campaign_status':'PARTIAL_ENVIRONMENT','stop_reason':'FROZEN_OWNED_STORAGE_ENVELOPE; SC06_NOT_EXECUTED',
        'audit_delivery':'REVIEWABLE_PARTIAL_CHECKPOINT; FULL_CAMPAIGN_DOD_NOT_CLOSED',
        'lanes':{'numerical':'PASS','chronological':'BLOCKED_PRODUCT_CONTRACT','evidence_consumer':'PASS'},
        'primary_world':'base-v3','charges':counts,'coverage':coverage,
        'chronology_geometry':'PASS_METADATA_ONLY; 10 matched episodes, 20 E1800/E14400 cells, zero target-value reads',
        'fidelity_by_edge':{'scripted_upstream':'SEGMENT_PRODUCT_PATH','definition_ingress':'SEGMENT_PRODUCT_PATH',
            'Spec1.4_to_committed_numeric_artifact':'FULL_PRODUCT_PATH','actual_run_to_ordinary_dossier_PAUSE':'FULL_PRODUCT_PATH',
            'chronological_confirmation':'CONTRACT_ONLY'},
        'science':{'market_alpha_established':False,'synthetic_protocol_executed':False,'strategy_ready':False},
        'forbidden_side_effects':{'provider_calls':0,'new_dependencies':0,'real_data_reads':0,'cash_spend':0,
            'product_repairs':0,'strategy_version':0,'activation':0,'PAPER':0,'merge':0},
        'inherited_MAIN_looks':22,'inherited_new_charge':False,
        'historical_fixture_semantics':'base-v2 quote prose/binding invalidated for scientific interpretation; values and guard/recovery evidence retained',
        'owned_running_processes':docker['running_owned_processes']})
    write(evidence/'findings.json',{'findings':[
        {'id':'F01','class':'MISSING_PRODUCT_SEAM_CONTRACT_GAP','severity':'MATERIAL','confidence':'HIGH',
         'boundary':'accepted List A protocol -> native source-bound confirming producer/reservation -> substantive science evidence',
         'violated_promise':'Required lifecycle objective is unavailable; no claim that #403 promised the confirmer',
         'expected':'Native accepted producer reserves before values and emits protocol-owned evidence',
         'actual':'Accepted numerical route is explored frozen replay; RUN completion follows evaluator; confirming implementation explicitly absent',
         'proof':'chronology.json pinned registry/AST/contract/consumer + readback.json actual science refusal',
         'repair':'One separately authorized List A chronological producer/reservation/consumer atom; no repair performed'},
        {'id':'F02','class':'HARNESS_DEFECT_INVALID_RUN','severity':'MATERIAL','confidence':'HIGH',
         'boundary':'Legacy _bind_experiment helper -> audit-owned Spec prose/data bindings',
         'actual':'base-v2 carried quote question/estimand/falsifier and unrelated Catalog binding; dossier PIT CONFLICT',
         'fix':'New base-v3 registered before classification/run, proper episode question/estimand/method and only source corpus binding',
         'retention':'All v2 specs/runs/attempts retained; no counter refund; v2 not primary scientific interpretation'},
        {'id':'F03','class':'EXPECTED_SCIENTIFIC_OR_AUTHORITY_REFUSAL','severity':'EXPECTED','confidence':'HIGH',
         'actual':'Numeric INCONCLUSIVE; dossier evidence BLOCKED, PIT/population/HOLDOUT UNKNOWN, other qualifying obligations MISSING; PROMOTE_BLOCKED',
         'repair':'Do not lower scientific floor or author qualifying carriers; no guard repair'},
        {'id':'F04','class':'COVERAGE_GAP_UNKNOWN','severity':'MATERIAL','confidence':'HIGH',
         'boundary':'SC06 fresh market variation -> registered native capture',
         'actual':'Frozen storage cap leaves insufficient allocation after retained attempts; changed world not executed',
         'next_gate':'Owner budget replan required; all existing counters/history retained; no automatic cleanup'},
        {'id':'F05','class':'COVERAGE_GAP_UNKNOWN','severity':'LIMITATION','confidence':'HIGH',
         'actual':'Spec definition slot registered via explicit fixture; no ordinary authoring/registration edge proved',
         'repair':'No product seam fabricated; SEGMENT_PRODUCT_PATH on registration'}]})
    return {'known_owned_allocation_bytes':known,'charges':counts,'campaign_status':'PARTIAL_ENVIRONMENT'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(finish(args.evidence,args.runtime),sort_keys=True))
