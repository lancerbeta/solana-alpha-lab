"""Read-only retention and necessary-contract replay; never execute science."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import jsonschema

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--retained',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[3];retained=a.retained.resolve()
    evidence=root/'docs/evidence/synthetic_lifecycle_targeted_v1'
    manifest=read(evidence/'retention-pins.json');count=0
    for pin in manifest['pins']:
        path=(retained/pin['artifact']).resolve()
        assert path.is_relative_to(retained), 'RETENTION_PATH_ESCAPE'
        assert path.is_file() and path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],pin['artifact']
        count+=1
    boundary=read(evidence/'contract-boundary.json')
    schema_path=root/'catalog/schemas/experiment_spec_v1_3.schema.json'
    assert sha(schema_path)==boundary['schema_sha256'],'FROZEN_SCHEMA_DIVERGENCE'
    schema=read(schema_path);validator=jsonschema.Draft202012Validator(schema)
    control=read(retained/'sls-tc-v1-episode-resume-a1/spec13-control.json')
    negative=read(retained/'sls-tc-v1-episode-resume-a1/spec13-negative.json')
    assert validator.is_valid(control),'RAW_SCHEMA_CONTROL_INVALID'
    errors=list(validator.iter_errors(negative))
    assert len(errors)==1 and list(errors[0].absolute_path)==['required_outcomes',0,'point_id']
    assert errors[0].validator=='pattern' and errors[0].validator_value=='^[XY][0-9]{1,7}$'
    point_validator=jsonschema.Draft202012Validator(schema['properties']['required_outcomes']['items']['properties']['point_id'])
    assert {point:point_validator.is_valid(point) for point in boundary['point_controls']}==boundary['point_controls']
    campaign=read(evidence/'campaign.json');legacy=read(evidence/'legacy-segment.json')
    initial=read(retained/'sls-tc-v1-episode-resume-a1/frozen.json')
    revised=read(retained/'sls-tc-v1-revise-a1/frozen.json')
    for name,frozen,terminal in [('episode-critic-result.json',initial,'REVISE_ONCE'),
                                 ('revised-episode-critic-result.json',revised,'KILL_LOW_INFORMATION_VALUE')]:
        critic=read(evidence/name)
        assert critic['critic_terminal']==terminal
        for key in ('session_id','selected_candidate_id','selected_definition_sha256','critic_input_packet_sha256'):
            assert critic[key]==frozen[key],key
    assert campaign['native_full_product_path'] is False and campaign['scientific_acceptance'] is False
    assert campaign['terminal']['critic_terminal']=='KILL_LOW_INFORMATION_VALUE'
    assert campaign['terminal']['cold_inventory_unchanged'] and campaign['terminal']['new_look_count']==0
    assert legacy['science_guard']['allowed'] is False and legacy['scientific_terminal']=='INCONCLUSIVE'
    assert not legacy['target_run_conflicted'] and not legacy['strategy_version_created']
    assert not legacy['accepted_chronological_validation'] and not legacy['synthetic_activation_or_paper_from_this_candidate']
    print(json.dumps({'status':'PASS','retained_pins_verified':count,'necessary_contract_gap_replayed':True,
        'critic_bindings_verified':2,'full_product_path':False,'scientific_execution_count':0}))

if __name__=='__main__':main()
