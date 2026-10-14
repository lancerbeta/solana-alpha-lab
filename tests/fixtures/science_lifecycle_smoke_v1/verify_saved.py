"""Offline audit verification: independent arithmetic and actual persistence witnesses."""
import argparse
import hashlib
import json
from pathlib import Path
from oracle import check_summary
from chronology_oracle import verify as verify_chronology


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def verify_run(run, rows, kind):
    response = run['response']
    assert response['status'] == 'COMPLETE' and response['scientific_terminal'] == 'INCONCLUSIVE'
    passport = response['passport']
    result = response['capability_result']
    artifact = dict(run['artifact'])
    assert artifact.pop('capability_result_sha256') == digest(result), 'ARTIFACT_RESULT_MISMATCH'
    artifact['capability_result']=result
    assert artifact['research_artifact_id'] == passport['result_artifact_id']
    artifact_bytes=json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
    assert hashlib.sha256(artifact_bytes).hexdigest()==run['artifact_file_sha256'], 'ARTIFACT_FILE_HASH_MISMATCH'
    assert digest(result) == passport['result_digest_sha256'], 'RESULT_DIGEST_MISMATCH'
    assert run['reads']['evaluator_invocations'] == 1, 'NO_ACTUAL_EVALUATOR'
    assert run['reads']['decoded_target_value_rows'] > 0, 'NO_ACTUAL_TARGET_READ'
    assert run['spec_pin']['canonical_sha256'] == passport['experiment_spec_sha256']
    classifier=run['classifier'];binding=classifier['episode_outcome_binding']
    assert classifier['lane_classifier_terminal']=='FAST_LANE_READY'
    assert classifier['experiment_spec_sha256']==passport['experiment_spec_sha256']
    assert classifier['selected_definition_sha256']==passport['hypothesis_definition_sha256']
    assert (binding['admissions_n'],binding['decision_n'],binding['matched_n'],binding['comparator_n'])==(24,20,10,10 if kind=='LIST_CONTRAST' else 20)
    assert binding['reads']['target_value_cells_materialized']==binding['reads']['outcome_evaluations']==0
    roles=('episode_id','decision_eligible','matched','comparator')
    expected_roles=[{k:r[k] for k in roles} for r in rows]
    if kind=='MIXED_LIST_NUMERIC':
        for r in expected_roles:r['comparator']=r['decision_eligible']
    assert [{k:r[k] for k in roles} for r in binding['membership']]==expected_roles, 'MEMBERSHIP_ORACLE_MISMATCH'
    assert passport['experiment_id'] == run['experiment_id']
    assert passport['source_lineage']['execution_kind'] == 'FROZEN_EVIDENCE_REPLAY'
    assert passport['source_lineage']['new_scientific_look'] is False
    assert passport['provider_calls_actual'] == 0 and passport['cash_spend_usd_cents'] == 0
    completions = [r for r in run['records'] if r['kind'] == 'RUN_COMPLETED']
    assert len(completions) == 1, 'NO_UNIQUE_COMMITTED_COMPLETION'
    assert completions[0]['payload']['run_id'] == passport['run_id']
    for key, value in passport.items():
        assert completions[0]['payload'][key] == value, 'COMMITTED_PASSPORT_MISMATCH'
    artifacts = [r for r in run['records'] if r['id'] == passport['result_artifact_id']]
    assert len(artifacts) == 1 and artifacts[0]['kind'] == 'RESEARCH_ARTIFACT'
    assert artifacts[0]['payload']['capability_result_sha256'] == digest(result)
    transactions = {r['transaction_id'] for r in run['records']}
    assert len(transactions) == 1, 'COMPLETION_TRANSACTION_MISMATCH'
    for record in run['records']:
        payload=dict(record['payload'])
        if 'capability_result_sha256' in payload:
            assert payload.pop('capability_result_sha256')==digest(result)
            payload['capability_result']=result
        assert digest(payload) == record['payload_sha256'], 'RECORD_PAYLOAD_HASH_MISMATCH'
    replay = run['replay']
    assert replay['entry_lane'] == 'REPLAY_AVAILABLE'
    assert replay['before'] == replay['after'], 'REPLAY_CHANGED_COMMITTED_STATE'
    assert replay['reads']['evaluator_invocations'] == replay['reads']['decoded_target_value_rows'] == 0
    assert replay['run_id'] == passport['run_id']
    return check_summary(result['summary'], rows, kind)


def verify_failure_receipts(consumer):
    expected_negatives = {
        'definition-foreign': 'EPISODE_CLASSIFIER_CONTEXT_MISMATCH',
        'historical-protection': 'HOLDOUT_PROTECTED',
        'protection': 'HOLDOUT_PROTECTED',
        'source-missing': 'EPISODE_SOURCE_UNAVAILABLE',
        'source-stale': 'FROZEN_INPUT_MISMATCH',
    }
    negatives=consumer['negative_runner_receipts']
    assert set(negatives)==set(expected_negatives), 'REQUIRED_NEGATIVE_WITNESSES_MISSING'
    for name, reason in expected_negatives.items():
        receipt=negatives[name]
        assert receipt['response']['status']=='INVALID_EVIDENCE'
        assert reason in receipt['response']['reason_codes'], 'NEGATIVE_REASON_MISMATCH'
        assert receipt['before']==receipt['after']
        assert receipt['reads']['evaluator_invocations']==receipt['reads']['decoded_target_value_rows']==0
    missing=consumer['missing_403']
    assert missing['status']=='PASS_EXPECTED_REFUSAL' and missing['fidelity']=='RETAINED_403_WORLD_MISSING_A7'
    receipt=missing['receipt']
    assert receipt['response']['status']=='INVALID_EVIDENCE', 'MISSING_SPECIMEN_FALSE_SUCCESS'
    assert 'EPISODE_OUTCOME_COVERAGE_UNRESOLVED' in receipt['response']['reason_codes']
    assert receipt['before']==receipt['after'], 'MISSING_SPECIMEN_CHANGED_STATE'
    assert receipt['reads']['evaluator_invocations']==receipt['reads']['decoded_target_value_rows']==0
    assert receipt['reads']['target_projection_calls']==0
    faults=consumer['faults']
    assert set(faults)=={'before-commit','after-commit'}, 'REQUIRED_FAULT_WITNESSES_MISSING'
    expected_boundaries={'before-commit':'RESULT_FILE_WRITTEN_BEFORE_COMPLETION_COMMIT',
        'after-commit':'COMPLETION_COMMITTED_BEFORE_CALLER_RESPONSE'}
    for mode, fault in faults.items():
        assert fault['interruption']['boundary']==expected_boundaries[mode], 'FAULT_BOUNDARY_MISMATCH'
        recovery=fault['recovery']
        assert fault['matching_committed_completions']==1
        assert fault['interruption']['reads']['evaluator_invocations']==1
        assert recovery['response']['status']=='COMPLETE'
        assert recovery['reads']['evaluator_invocations']==(1 if mode=='before-commit' else 0)
        if mode=='after-commit':
            assert recovery['entry_lane']=='REPLAY_AVAILABLE' and recovery['before']==recovery['after']
            assert recovery['reads']['decoded_target_value_rows']==0
            assert fault['interruption']['state']==recovery['after']
        else:
            assert recovery['before']==fault['interruption']['state']
            assert len(recovery['after']['completion_ids'])==len(fault['interruption']['state']['completion_ids'])+1


def verify_sc06(base, changed):
    assert changed['world']=='changed' and changed['tested_git_sha']==base['tested_git_sha']
    assert changed['registered_input']['negative_world'] is True
    roles=('episode_id','cohort_id','t0','decision_eligible','matched','comparator')
    assert [{k:r[k] for k in roles} for r in base['oracle_rows']]==[{k:r[k] for k in roles} for r in changed['oracle_rows']], 'SC06_ORACLE_MEMBERSHIP_CHANGED'
    from fractions import Fraction
    for old,new in zip(base['oracle_rows'],changed['oracle_rows']):
        if old['decision_eligible']:
            assert Fraction(new['return'])==Fraction(old['return'])-(Fraction(1,5) if old['matched'] else 0), 'SC06_FUTURE_ORACLE_NOT_REGISTERED_DELTA'
    prefix=changed['prefix_oracle']
    assert prefix['status']=='PASS_CAPTURED_PREFIX_INVARIANCE'
    assert prefix['base']['prefix_sha256']==prefix['changed']['prefix_sha256'], 'SC06_DECISION_PREFIX_CHANGED'
    assert prefix['base']['prefix_rows']==prefix['changed']['prefix_rows']>0
    for item in ('base','changed'):
        assert prefix[item]['prefix_episode_count']==24
        assert prefix[item]['target_value_cells_read']==prefix[item]['evaluator_invocations']==0
    assert set(changed['runs'])==set(base['runs'])
    contrasts={}
    for kind,run in changed['runs'].items():
        old=base['runs'][kind]
        result=verify_run(run,changed['oracle_rows'],kind)
        contrasts[kind]=str(result['contrast'])
        before=old['classifier']['episode_outcome_binding'];after=run['classifier']['episode_outcome_binding']
        # Content-addressed release identity must change with future source bytes.
        # Every other native membership field, including role and episode ID, stays exact.
        stable=lambda rows:[{k:v for k,v in r.items() if k!='release_id'} for r in rows]
        assert stable(before['membership'])==stable(after['membership']), 'SC06_NATIVE_MEMBERSHIP_CHANGED'
        assert any(x['release_id']!=y['release_id'] for x,y in zip(before['membership'],after['membership'])), 'SC06_RELEASE_IDENTITY_UNCHANGED'
        assert all(before[k]==after[k] for k in ('admissions_n','decision_n','matched_n','comparator_n')), 'SC06_DENOMINATOR_CHANGED'
        assert old['response']['capability_result']['summary']!=run['response']['capability_result']['summary'], 'SC06_NUMERIC_RESULT_UNCHANGED'
        assert old['response']['passport']['result_digest_sha256']!=run['response']['passport']['result_digest_sha256']
        assert prefix['changed']['source_pins']==after['sources'], 'SC06_PREFIX_SOURCE_BINDING_MISMATCH'
    assert prefix['base']['source_pins']==base['runs']['LIST_CONTRAST']['classifier']['episode_outcome_binding']['sources']
    return contrasts


def verify(directory):
    directory = Path(directory)
    numeric = json.loads((directory/'numerical.json').read_text(encoding='utf-8'))
    outcomes = {kind: verify_run(run, numeric['oracle_rows'], kind) for kind, run in numeric['runs'].items()}
    assert set(outcomes) == {'LIST_CONTRAST', 'MIXED_LIST_NUMERIC'}
    prior=json.loads((directory/'prior-version-v2.json').read_text(encoding='utf-8'))
    for kind,run in numeric['runs'].items():
        assert prior['runs'][kind]['sources']==run['classifier']['episode_outcome_binding']['sources']
        assert prior['runs'][kind]['recipe_scientific_identity']==run['classifier']['episode_outcome_binding']['recipe_scientific_identity']
    geometry=json.loads((directory/'chronology-geometry.json').read_text(encoding='utf-8'))
    assert verify_chronology(geometry)
    pinned={s['cohort_id']:{k:s[k] for k in ('cohort_id','census_sha256','observations_sha256','schedule_sha256')}
        for s in numeric['runs']['LIST_CONTRAST']['classifier']['episode_outcome_binding']['sources']}
    assert {s['cohort_id']:s for s in geometry['source_hashes']}==pinned, 'CHRONOLOGY_SOURCE_PIN_MISMATCH'
    matched={r['episode_id']:(r['cohort_id'],r['t0']) for r in numeric['oracle_rows'] if r['matched']}
    assert {r['episode_id']:(r['cohort_id'],r['t0']) for r in geometry['cells']}==matched, 'CHRONOLOGY_MEMBERSHIP_MISMATCH'
    source_asof=json.loads((directory/'registered-input.json').read_text(encoding='utf-8'))['source_asof']
    from chronology_oracle import utc
    assert all(utc(point['first_reliable_available_at'])<=utc(source_asof)
        for cell in geometry['cells'] for point in cell['points'].values()), 'OBSERVATION_AFTER_SOURCE_ASOF'
    ledger = [json.loads(line) for line in (directory/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    native = [r for r in ledger if r['ledger_kind'] == 'native_charge']
    assert [r['event']['sequence'] for r in native] == list(range(1, len(native)+1))
    binding=json.loads((directory/'source-binding.json').read_text(encoding='utf-8'))
    native_bytes=''.join(json.dumps(r['event'],sort_keys=True)+'\n' for r in native).encode()
    assert hashlib.sha256(native_bytes).hexdigest()==binding['native_ledger_sha256'], 'NATIVE_LEDGER_HASH_MISMATCH'
    assert hashlib.sha256((directory/'chronology-geometry.json').read_bytes()).hexdigest()==binding['chronology_geometry_sha256'], 'CHRONOLOGY_RECEIPT_HASH_MISMATCH'
    counts = {kind: sum(r['event']['kind'] == kind for r in native) for kind in ('main', 'evaluator', 'confirmation')}
    assert numeric['charges']=={'main':4,'evaluator':8,'confirmation':0}, 'PRIMARY_SNAPSHOT_CHARGE_MISMATCH'
    assert counts['main'] <= 6 and counts['evaluator'] <= 12 and counts['confirmation'] == 0
    summary = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    assert summary['campaign_status'] == 'COMPLETE_WITH_FINDINGS'
    assert summary['coverage']['SC06']['status'] == 'PASS_ENGINEERING'
    assert counts==summary['charges']=={'main':6,'evaluator':10,'confirmation':0}, 'LEDGER_CHARGE_MISMATCH'
    sc06=verify_sc06(numeric,json.loads((directory/'sc06.json').read_text(encoding='utf-8')))
    budget=json.loads((directory/'budget-continuation.json').read_text(encoding='utf-8'))
    assert budget['original_cap_bytes']==536870912 and budget['original_breach_bytes']==169797456
    assert budget['original_post_hook_known_allocation_bytes']==706668368 and budget['history_recomputed'] is False
    assert budget['forward_only_cap_bytes']==671088640 and budget['cleanup_performed'] is True
    footprint=json.loads((directory/'footprint.json').read_text(encoding='utf-8'))
    assert footprint['frozen_cap_bytes']==671088640 and footprint['known_file_remaining_bytes']>=0, 'FORWARD_STORAGE_CAP_EXCEEDED'
    assert all(summary['coverage'][s]['status'] == 'BLOCKED_PRODUCT_CONTRACT' for s in ('SC10','SC11','SC12'))
    assert all(value is False for value in summary['science'].values())
    chronology = json.loads((directory/'chronology.json').read_text(encoding='utf-8'))
    assert chronology['native_terminal'] is None and chronology['B_attempts'] == 0
    assert chronology['not_only_sample_unbound'] is True
    consumer = json.loads((directory/'readback.json').read_text(encoding='utf-8'))
    verify_failure_receipts(consumer)
    assert consumer['guard_refusals'] == {'stale':'STALE_EVIDENCE_SNAPSHOT','promote':'PROMOTE_BLOCKED'}
    assert consumer['cold_pause']['result']['disposition'] == 'REPLAY_IDENTICAL'
    assert consumer['cold_pause']['business_state_unchanged'] is True
    assert consumer['cold_dossier']['planes']['decision'] == 'PAUSE'
    assert consumer['cold_dossier']['science_guard']['allowed'] is False
    assert consumer['cold_dossier']['planes']['evidence']=='BLOCKED'
    assert next(o['status'] for o in consumer['cold_dossier']['obligations'] if o['code']=='PIT_AVAILABILITY')=='UNKNOWN'
    tested=consumer['cold_dossier']['tested']
    assert 'E1800' in tested['estimand'] and 'E14400' in tested['estimand']
    assert tested['method']=='frozen_episode_price_relative_proxy'
    direct = {r['record_id'] for r in consumer['cold_dossier']['direct_evidence']}
    list_completion = next(r['id'] for r in numeric['runs']['LIST_CONTRAST']['records'] if r['kind']=='RUN_COMPLETED')
    assert list_completion in direct, 'ACTUAL_A_COMPLETION_NOT_DIRECT'
    return {'status':'PASS_SAVED_A_C_SC06_WITH_PROVED_B_BOUNDARY', 'charges':counts,
        'numeric_checks':{k:str(v['contrast']) for k,v in outcomes.items()},'sc06_numeric_checks':sc06}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().evidence), sort_keys=True))
