"""Read native saved truth; export compact witnesses, never author product records."""
import json
from collections import Counter
from common import ROOT, OUT, BASE, dump, load, sha
from execution import state

def compact_artifact_record(record):
    from verify_saved import digest
    if record['kind']=='RESEARCH_ARTIFACT' and 'capability_result' in record['payload']:
        record['payload']['capability_result_sha256']=digest(record['payload'].pop('capability_result'))
        record['compact_payload']='RECONSTRUCT_ORIGINAL_WITH_RESPONSE_CAPABILITY_RESULT; ORIGINAL_NATIVE_HASH_RETAINED'
    return record

def compact_artifact(artifact):
    from verify_saved import digest
    artifact['capability_result_sha256']=digest(artifact.pop('capability_result'))
    return artifact


def compact_state(value):
    return {k:v for k,v in value.items() if k!='records'}


def compact_reads(value):
    reads = value['parquet_reads']
    return {**{k:v for k,v in value.items() if k!='parquet_reads'},
        'parquet_read_calls':len(reads), 'full_trace_sha256':__import__('verify_saved').digest(reads),
        'full_trace_retained':True}


def records(plane):
    from solana_alpha_lab.factory.research_store import ExistingResearchStoreReader
    return [{'id':r.record_id,'kind':str(r.record_kind),'run_id':r.run_id,
        'transaction_id':r.transaction_id,'producer_capability_id':r.producer_capability_id,
        'producer_git_sha':r.producer_git_sha,'payload_sha256':r.payload_sha256,
        'payload':json.loads(r.payload_json)} for r in ExistingResearchStoreReader(plane).iter_committed_records()]


def compact_run(receipt):
    return {'response':receipt['response'],'entry_lane':receipt['entry_lane'],
        'reads':compact_reads(receipt['reads']), 'before':compact_state(receipt['before']),
        'after':compact_state(receipt['after']), 'spec_sha256':receipt['spec_sha256']}


def export(world='base-v2'):
    plane=OUT/world/'plane'
    before=state(plane)
    all_records=records(plane)
    prefix='' if world=='base-v2' else world+'-'
    definition_file='definition-ingress'+('' if world=='base-v2' else '-'+world)+'.json'
    pins=load(OUT/definition_file)['pins']
    runs={}
    for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
        original=load(OUT/world/(kind+'-run.json'))
        repeat=load(OUT/world/(kind+'-replay.json'))
        response=original['response'];passport=response['passport']
        run_records=[r for r in all_records if r['run_id']==passport['run_id']]
        artifact_path=plane/'research/artifacts/results'/(passport['result_artifact_id']+'.json')
        frozen=load(OUT/world/kind/'classified.json')
        runs[kind]={'response':response,'experiment_id':passport['experiment_id'],
            'spec_pin':next(p for p in pins if p['experiment_id']==passport['experiment_id']),
            'artifact':compact_artifact(load(artifact_path)),'artifact_file_sha256':sha(artifact_path),
            'records':[compact_artifact_record(r) for r in run_records],'reads':compact_reads(original['reads']),
            'before':compact_state(original['before']),'after':compact_state(original['after']),
            'replay':{'entry_lane':repeat['entry_lane'],'run_id':repeat['response']['run_id_or_null'],
                'reads':compact_reads(repeat['reads']),'before':compact_state(repeat['before']),
                'after':compact_state(repeat['after'])},
            'classifier':frozen['classifier_receipt'],
            'lineage':passport['source_lineage']}
    ledger=[json.loads(line) for line in (OUT/'attempts.jsonl').read_text().splitlines()]
    charges={k:sum(r['kind']==k for r in ledger) for k in ('main','evaluator','confirmation')}
    baseline_ids=set(load(OUT/world/'LIST_CONTRAST-run.json')['before']['completion_ids'])
    baseline_run_ids={r['run_id'] for r in all_records if r['id'] in baseline_ids}
    baseline=[r for r in all_records if r['id'] in baseline_ids or
        (r['kind']=='EXPERIMENT_METRIC' and r['run_id'] in baseline_run_ids)]
    destination=OUT/('portable' if world=='base-v2' else 'portable-v3')
    dump(destination/'numerical.json',{'tested_git_sha':BASE,'primary_world':world,'oracle_rows':load(OUT/world/'membership-numeric-oracle.json'),
        'runs':runs,'charges':charges,'native_bootstrap_baseline':baseline,
        'bootstrap_claim':'Native commissioning canonical receipt replay; not A evaluator or B confirmation',
        'scope':'Spec1.4 -> actual saved numeric artifact/passport; explored replay, not OOS'})
    dump(destination/'chronology.json',load(OUT/'confirmation-reachability.json'))
    negative={name:compact_run(r) for name,r in load(OUT/'negative-receipts.json').items()}
    missing=load(OUT/'missing-check.json')
    missing['receipt']=compact_run(missing['receipt'])
    faults={}
    for mode in ('before-commit','after-commit'):
        root=OUT/('fault-'+mode)
        interruption=load(root/('LIST_CONTRAST-'+mode+'-interruption.json'))
        interruption['state']=compact_state(interruption['state'])
        interruption['reads']=compact_reads(interruption['reads'])
        suffix='replay' if mode=='after-commit' else 'run'
        recovery=load(root/('LIST_CONTRAST-'+suffix+'.json'))
        faults[mode]={'interruption':interruption,'recovery':compact_run(recovery),
            'matching_committed_completions':sum(r['kind']=='RUN_COMPLETED' and
                r['payload'].get('run_id')==recovery['response']['run_id_or_null'] for r in records(root/'plane'))}
    cold=load(OUT/(prefix+'cold-pause-replay.json'));cold['state']=compact_state(cold['state'])
    consumer=load(OUT/(prefix+'consumption-check.json'))
    dump(destination/'readback.json',{'negative_runner_receipts':negative,'missing_403':missing,'faults':faults,
        'cold_pause':cold,'cold_dossier':load(OUT/(prefix+'cold-dossier.json'))['dossier'],
        'foreign_dossier':load(OUT/(prefix+'foreign-dossier.json'))['dossier'],
        'guard_refusals':consumer['refusals'],'consumer_check':{k:v for k,v in consumer.items() if k!='state'},
        'definition_ingress':load(OUT/definition_file),
        'fault_specimen_world':'base-v2; same frozen recipe/source/masks; quote prose invalid for science; persistence/guard segment only'})
    for filename in ('containment-canaries.json','oracle-canaries.json','registered-input.json'):
        source=OUT/filename if filename!='registered-input.json' else OUT/world/filename
        dump(destination/filename,load(source))
    paths=['AGENTS.md','uv.lock','src/solana_alpha_lab/factory/episode_required_outcomes.py',
        'src/solana_alpha_lab/factory/hfic_session.py','src/solana_alpha_lab/factory/lane_classifier.py',
        'src/solana_alpha_lab/factory/run_passport.py','src/solana_alpha_lab/factory/research_store.py']
    dump(destination/'source-binding.json',{'tested_git_sha':BASE,'immutable_source_hashes':{p:sha(ROOT/p) for p in paths},
        'native_ledger_sha256':sha(OUT/'attempts.jsonl'), 'registered_before_MAIN':True,
        'operational_retention':'OWNED_RUNTIME_AND_VOLUMES; prior failed attempts retained; no automatic cleanup',
        'full_source_artifact_locators':{'volume':'science-lifecycle-v1-output','world':world,
            'preclassify_store':'base-v2/classified-plane','faults':['fault-before-commit','fault-after-commit']}})
    if world=='base-v3':
        prior=load(OUT/'portable/numerical.json')
        prior_runs={kind:{'experiment_id':r['experiment_id'],'spec_pin':r['spec_pin'],
            'run_id':r['response']['passport']['run_id'],'result_digest_sha256':r['response']['passport']['result_digest_sha256'],
            'artifact_file_sha256':r['artifact_file_sha256'],'lineage':r['lineage'],
            'recipe_scientific_identity':r['classifier']['episode_outcome_binding']['recipe_scientific_identity'],
            'sources':r['classifier']['episode_outcome_binding']['sources'],
            'mean_target':r['response']['capability_result']['summary']['mean_target'],
            'contrast':r['response']['capability_result']['summary']['research_scope']['contrast']['observed_target_difference']}
            for kind,r in prior['runs'].items()}
        dump(destination/'prior-version-v2.json',{'runs':prior_runs,
            'consumer_planes':load(OUT/'cold-dossier.json')['dossier']['planes'],
            'tested':load(OUT/'cold-dossier.json')['dossier']['tested'],
            'invalidated_semantic_claim':'Inherited quote question/estimand/prose and unrelated canonical binding; not primary A/C proof',
            'retained':True,'corrected_before_v3_classification_and_execution':True})
    # Original sequence is retained verbatim in each event; host attempts are joined separately.
    (destination/'attempts.jsonl').write_text(''.join(json.dumps({'ledger_kind':'native_charge','event':r},sort_keys=True)+'\n' for r in ledger))
    assert state(plane)==before,'SAVED_EXPORT_CHANGED_SCIENCE'
    return {'status':'SAVED_EXPORT_CREATED','files':len(list(destination.iterdir())),'charges':charges}
