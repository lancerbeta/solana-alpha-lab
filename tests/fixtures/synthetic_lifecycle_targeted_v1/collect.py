"""Produce compact audit facts from exact retained runs; never grant missing PASS."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

TASK='SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1_TARGETED_CONTINUATION'
ORIGINAL_HEAD='e6141191c185a5aa02c0bc3178b2efeaa534417b'
BASE='94b391d658b52035ae88e2da05f1ea25ff17b0f8'

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--retained',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[3];retained=a.retained.resolve();out=a.output.resolve()
    assert out.is_relative_to(root) and retained.is_dir()
    out.mkdir(parents=True,exist_ok=True)
    def original(path):
        raw=subprocess.check_output(['git','show',ORIGINAL_HEAD+':'+path],cwd=root)
        return json.loads(raw),hashlib.sha256(raw).hexdigest()
    diagnosis=read(retained/'sls-tc-v1-diagnose-a3/diagnosis.json')
    for item in diagnosis['records']:
        family=item['family'];critic,h=original(f'docs/evidence/synthetic_lifecycle_smoke_v1/{family}-critic-result.json')
        finalized=read(retained/f'sls-v1-finalize-a1/{family}-finalize.json')
        item.update(original_critic_result_sha256=h,original_critic_terminal=critic['critic_terminal'],
            original_material_defects=critic['material_defects'],
            original_classifier_receipt=critic['classifier_receipt'],
            original_classifier_reason_codes=critic['classifier_receipt'].get('reason_codes') if critic['classifier_receipt'] else None,
            original_classifier_reason_codes_presence='ABSENT',
            original_saved_decision=finalized['decisions'],original_saved_diagnostics=finalized['diagnostics'],
            classifier_probe_schema_version='1.1',spec13_probe_schema_version='1.3')
        packet=read(retained/f'sls-v1-world-a3/native-world/{family}-critic-packet.json')
        card=packet['selected_candidate']
        item['pit_component_provenance']=card.get('pit_component_provenance')
        item['authored_pit_risks']=card.get('pit_leakage_survivorship_risks')
        assert critic['classifier_receipt'] is None and finalized['diagnostics']['lane_classifier_terminal'] is None
    dump(out/'old-kill-diagnosis.json',diagnosis)
    episode=read(retained/'sls-tc-v1-episode-resume-a1/episode-summary.json')
    revision=read(retained/'sls-tc-v1-revise-a1/critic-stage-summary.json')
    terminal=read(retained/'sls-tc-v1-finalize-a1/critic-stage-summary.json')
    legacy=read(retained/'sls-tc-v1-legacy-a2/legacy-summary.json')
    boundary=read(retained/'sls-tc-v1-episode-resume-a1/contract-boundary.json')
    assert all(x['status']=='PASS' for x in (episode,revision,terminal,legacy))
    assert boundary['status']=='PROVED_CONTRACT_GAP' and legacy['science_guard']['allowed'] is False
    assert terminal['new_look_count']==0 and terminal['cold_inventory_unchanged'] is True
    assert legacy['science_guard']['allowed'] is False
    rows=[];pins=[]
    for directory in sorted(retained.iterdir()):
        if not directory.is_dir() or not directory.name.startswith(('sls-tc-v1-','kit-sls-tc-v1-','critic-sls-tc-')):continue
        if (directory/'terminal.json').is_file():
            t=read(directory/'terminal.json');phase=read(directory/'phase-terminal.json') if (directory/'phase-terminal.json').is_file() else None
            rows.append({'attempt_id':directory.name,'exit_code':t['exit_code'],'running':t['running'],
                'status':phase['status'] if phase else 'INVALID_HARNESS',
                'source_unchanged':phase['source_unchanged'] if phase else 'UNKNOWN',
                'elapsed_seconds':phase['seconds'] if phase else None,'stop_reason':t['stop_reason']})
            assert not t['running']
        for file in sorted(directory.rglob('*')):
            if file.is_file():pins.append({'artifact':file.relative_to(retained).as_posix(),'bytes':file.stat().st_size,'sha256':digest(file)})
    dump(out/'retention-pins.json',{'scope':'ALL_TARGETED_HOST_ATTEMPTS_AND_KIT_SNAPSHOTS','pins':pins,
        'linux_world':'OWNED_sls-v1-scratch_sls-tc-episode-world-v1','linux_lineage':'native source packet hashes and frozen input manifests; physical allocation measured separately',
        'deleted':False,'original_head_preserved':ORIGINAL_HEAD})
    dump(out/'attempts.json',{'all_attempts_preserved':True,'attempts':rows,
        'invalid_attempt_causes':{'sls-tc-v1-diagnose-a1':'AUDIT_LAUNCHER_VOLUME_ALIAS_CREATED_EMPTY_REPO',
            'sls-tc-v1-episode-a1':'AUDIT_OBSERVER_WRONG_COMPARATOR_FIELD_AFTER_VALID_NATIVE_LOOK',
            'sls-tc-v1-legacy-a1':'AUDIT_OBSERVER_EXPECTED_GLOBAL_CONFLICT_SET_EMPTY_IN_SHARED_SYNTHETIC_STORE'}})
    docker=read(retained/'targeted-docker-footprint.json');host=read(retained/'targeted-host-footprint.json')
    assert docker['all_campaign_containers_stopped'] and not host['measurement_errors']
    total=host['allocated_unique_owned_bytes']+sum(x['allocated_bytes'] for x in docker['volumes'].values())+docker['container_writable_layers_bytes']
    if docker['logs_allocated_bytes'] is not None:total+=docker['logs_allocated_bytes']
    footprint={'measured_at':docker['measured_at'],'host':host,'docker':docker,'known_allocated_bytes':total,
        'known_allocated_gib':round(total/(1024**3),4),'new_images_bytes':0,'uv_shared_cache_growth':None,
        'uv_shared_cache_growth_status':'UNKNOWN_NO_PRE_CAMPAIGN_BASELINE','deleted':False,
        'limit':'Snapshot includes both campaigns and continuation worktree. Existing image/VHDX excluded; hardlinks can overstate incremental allocation; final metadata/log growth excluded.'}
    dump(out/'footprint.json',footprint)
    dump(out/'contract-boundary.json',boundary)
    dump(out/'legacy-segment.json',legacy)
    coverage,coverage_sha=original('docs/evidence/synthetic_lifecycle_smoke_v1/coverage.json')
    coverage['original_evidence_commit']=ORIGINAL_HEAD;coverage['original_coverage_sha256']=coverage_sha
    coverage['native_full_product_path']=False
    coverage['targeted_continuation']=[
        {'boundary':'episode ingress -> native Forge -> persist/freeze','status':'PASS','fidelity':'SEGMENT_PRODUCT_PATH','benchmark_id':'SLS-TC-EPISODE-NATIVE-V1'},
        {'boundary':'genuine packet Critic -> native revision -> genuine packet Critic -> saved terminal','status':'PASS','fidelity':'SEGMENT_PRODUCT_PATH','scientific_acceptance':False,'terminal':terminal['critic_terminal']},
        {'boundary':'native episode required outcomes -> mandatory ExperimentSpec 1.3','status':'BLOCKED','reason_code':boundary['native_error_code'],'class':'PRODUCT_CONTRACT_GAP'},
        {'boundary':'same recipe -> accepted legacy Spec 1.1 -> registered runner -> DIRECT runtime records','status':'PASS','fidelity':'SEGMENT_PRODUCT_PATH','semantically_equivalent_to_required_1_3':False},
        {'boundary':'legacy runtime DIRECT -> qualifying science -> StrategyVersion','status':'BLOCKED','reason_code':'PROMOTE_BLOCKED','class':'EXPECTED_SAFETY_REFUSAL'},
        {'boundary':'original BR-01 -> ordinary PAPER -> reconciliation','status':'PASS','fidelity':'SEGMENT_PRODUCT_PATH','original_evidence_commit':ORIGINAL_HEAD,'new_native_candidate_consumed':False},
        {'boundary':'blind Actor','status':'AGENT_BEHAVIOR_UNVERIFIED','class':'AUDIT_ENVIRONMENT_LIMITATION'},
        {'boundary':'independent chronological validation','status':'NOT_ACCEPTED','class':'SCIENTIFIC_BINDING_AND_SUPPORT_GAP','validation_values_read':False}]
    dump(out/'coverage.json',coverage)
    campaign={'task_id':TASK,'status':'EARLIEST_REQUIRED_OUTCOME_CONTRACT_GAP_PROVED','product_base':BASE,
        'original_audit_pr':401,'original_audit_head':ORIGINAL_HEAD,'original_evidence_preserved':True,
        'native_full_product_path':False,'episode_prefix':episode,'revision':revision,'terminal':terminal,
        'earliest_observed_scientific_stop':terminal['critic_terminal'],
        'earliest_product_contract_gap':boundary,
        'product_gap_proof_scope':'Necessary ExperimentSpec 1.3 outcome expressibility constraint, independently probed; this candidate stopped earlier at Critic and was not advanced through it.',
        'downstream_probe':legacy,
        'scientific_acceptance':False,'blind_actor':'AGENT_BEHAVIOR_UNVERIFIED',
        'oracle_scope':'Aggregate n/means/contrast independent Decimal checks; individual selected-ID membership not emitted and remains UNVERIFIED.',
        'benchmark_history':'Original raw benchmark plus separately registered episode v1; unchanged values/seed/thresholds after first look.',
        'clock_limit':'Fixture commissioning generated_at/research_memory_as_of are synthetic nonchronological metadata, not real PIT availability proof.',
        'holdout_limit':'Later source packet captured but never imported/decoded by evaluation; dependent synthetic template and one day/group do not satisfy accepted chronological inference.',
        'fidelity':'SEGMENT_PRODUCT_PATH','known_retained_gib':footprint['known_allocated_gib'],
        'protected_actions':{'product_repair':0,'manual_scientific_promote':0,'provider':0,'production_writes':0,'deploy':0,'cash':0,'merge':0,'cleanup':0}}
    dump(out/'campaign.json',campaign)
    print(json.dumps({'status':campaign['status'],'attempts':len(rows),'retention_pins':len(pins),'known_retained_gib':footprint['known_allocated_gib']}))

if __name__=='__main__':main()
