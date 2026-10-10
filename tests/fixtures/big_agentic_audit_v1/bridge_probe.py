"""Consume the real producer's retained records without synthetic evidence joins."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
sys.path[:0] = ['/repo', '/repo/src', '/kit']
import yaml
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from solana_alpha_lab.factory.experiment_evidence import compose_experiment_dossier
from solana_alpha_lab.factory.research_workbench import LifecycleEntityLocatorV1
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
from safety_preflight import check
from oracles import grade_bridge


def main():
    assert check()['pass']
    candidates = []
    for path in Path('/input/tmp').glob('*/classify.json'):
        body = json.loads(path.read_text())
        if body.get('experiment_spec', {}).get('question', '').startswith('SCRIPTED_CRITIC_MECHANICAL:'):
            candidates.append(path)
    if len(candidates) != 1:
        raise SystemExit('BRIDGE_EXACT_PRODUCER_INPUT_NOT_UNIQUE')
    path = candidates[0]
    spec = json.loads(path.read_text())['experiment_spec']
    plane = path.parent / 'plane'
    store = ResearchStore(plane, create_if_missing=False)
    before = store.diagnostics().committed_inventory_sha256
    records = list(store.iter_committed_records())
    root = Path('/audit/bridge-source')
    root.mkdir()
    for name in ('catalog', 'configs'):
        shutil.copytree(Path('/repo') / name, root / name)
    specs = root / 'configs' / 'experiment_specs'
    # The only added input is the already-used operator-authored definition.
    # Production records, classifications and scientific obligations stay intact.
    for file in specs.glob('*.yaml'):
        file.unlink()
    (specs / 'BAA_RETAINED_OPERATOR_INPUT.yaml').write_text(yaml.safe_dump(spec))
    projection = build_lifecycle_projection(root, research_store=store,
        research_data_root=plane, projected_at='2026-10-16T00:00:00Z')
    dossier = compose_experiment_dossier(projection,
        LifecycleEntityLocatorV1(spec['experiment_id'], 'GIT', 'EXPERIMENT_SPEC'),
        root=root, records=records, records_status='AVAILABLE',
        write_capability={'read': 'AVAILABLE', 'write': 'UNAVAILABLE'})
    expected_hash = experiment_spec_sha256(spec)
    execution = []
    for record in records:
        if str(record.record_kind) in ('RUN_STARTED', 'RUN_COMPLETED'):
            payload = json.loads(record.payload_json)
            execution.append({'record_id': record.record_id, 'kind': str(record.record_kind),
                'run_id': record.run_id, 'payload_sha256': record.payload_sha256,
                'experiment_id': payload.get('experiment_id'),
                'experiment_spec_id': payload.get('experiment_spec_id'),
                'experiment_spec_sha256': payload.get('experiment_spec_sha256')})
    confirmed_completed = any(row['kind'] == 'RUN_COMPLETED' and
        row['experiment_spec_sha256'] == expected_hash for row in execution)
    result = {'schema': 'baa.producer-consumer-bridge.v1',
        'fidelity': 'SEGMENT_PRODUCT_PATH', 'input_producer_test':
        'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_scripted_positive_boundary_runs_real_classify_final_runner_replay',
        'authored_intermediate': 'ExperimentSpec from original classify.json; published only into disposable definition slot',
        'inserted_scientific_records': 0, 'operator_input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'planes': dossier['planes'], 'obligations': dossier['obligations'],
        'science_guard': dossier['science_guard'], 'records_n': len(records),
        'experiment_id': spec['experiment_id'], 'experiment_spec_sha256': expected_hash,
        'execution_records': execution, 'producer_complete_for_exact_spec': confirmed_completed,
        'expected_execution_plane': 'COMPLETED' if confirmed_completed else 'UNKNOWN',
        'inventory_before': before, 'inventory_after': store.diagnostics().committed_inventory_sha256}
    result['promotion_refusal_check'] = 'PASS' if not dossier['science_guard']['allowed'] else 'FAIL'
    result['readonly_check'] = 'PASS' if result['inventory_before'] == result['inventory_after'] else 'FAIL'
    result['status'] = grade_bridge(result)
    (Path('/audit') / 'bridge-summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'status': result['status'], 'planes': result['planes'], 'science_guard': result['science_guard']}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
