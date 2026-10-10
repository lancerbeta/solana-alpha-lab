"""Source and post-run evidence bindings; no scientific or delivery acceptance."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/evidence/big_agentic_audit_v1'
BASE = '90ba76e37515b3d521478a6d05a149fb0f1d2b75'
OWNERS = ['AGENTS.md', 'delivery-harness/harness.yaml', 'delivery-harness/project-profile.yaml',
    'delivery-harness/context-map.yaml', 'delivery-harness/policies/solana-alpha-lab.md',
    'docs/agent/DELIVERY_HARNESS_PROTOCOL.md', 'control/owner_attention_gate_v2.yaml',
    'control/active_time_gates.json', 'configs/experiment_capability_registry_v2.yaml',
    'configs/factory_semantic_operability_v1.yaml',
    'docs/contracts/forge_native_lifecycle_closure_v1.md',
    'docs/contracts/forge_ordinary_operation_lifecycle_v1.md',
    'docs/contracts/experiment_evidence_decision_v1.md', 'docs/contracts/science_to_strategy_handoff_v1.md',
    'src/solana_alpha_lab/factory/document_runner.py',
    'src/solana_alpha_lab/factory/experiment_evidence.py',
    'src/solana_alpha_lab/factory/operational_store.py',
    'src/solana_alpha_lab/factory/lifecycle_projection.py',
    'src/solana_alpha_lab/factory/promotion_handoff.py', 'uv.lock', 'pyproject.toml', '.python-version']


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--aux-root', type=Path, required=True)
    args = parser.parse_args()
    ledger = json.loads((OUT / 'run-ledger.json').read_text(encoding='utf-8'))
    coverage = json.loads((OUT / 'coverage.json').read_text(encoding='utf-8'))
    source = {path: hashlib.sha256(subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE + ':' + path])).hexdigest()
              for path in OWNERS}
    auxiliary = []
    for phase in ('smoke-a1', 'smoke-a2'):
        folder = args.aux_root / phase
        files = [{'ref': p.relative_to(args.aux_root).as_posix(), 'bytes': p.stat().st_size,
                  'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(folder.glob('smoke-*.json*'))]
        auxiliary.append({'attempt': phase, 'refs': files,
            'status': 'HARNESS_READBACK_LOCATOR_INVALID' if phase == 'smoke-a1' else 'PASS_TWO_CONTROLS',
            'closure_claim': phase == 'smoke-a2'})
    dump('auxiliary-attempts.json', {'schema': 'baa.auxiliary-attempts.v1',
         'retained_root_logical': 'AUX_EVIDENCE_ROOT', 'smoke': auxiliary,
         'preflight_attempts': [{'id': 'preflight-a1', 'result': 'HARNESS_DEFECT_PERMISSION_PROBE_HANDLING',
                                  'retained_in': 'owned Docker logs; no product reached'},
                                 {'id': 'preflight-a2', 'result': 'PASS', 'ref': 'AUX_EVIDENCE_ROOT/safety-preflight.json'}]})
    post = json.loads((args.evidence_root / 'post-run.json').read_text(encoding='utf-8'))
    clocks = [(datetime.fromisoformat(row['started'].replace('Z', '+00:00')),
               datetime.fromisoformat(row['finished'].replace('Z', '+00:00')))
              for row in post['states'] if row.get('started') and row.get('finished')]
    dump('post-run.json', post)
    manifest = {'schema': 'baa.campaign-manifest.v1', 'campaign_id': 'BAA-2026-10-10-V1',
        'base_commit': BASE, 'base_tree': '46c7f35c1d57a8f2491cfc3cf44af51bb14d5097',
        'attachment_research_base': 'd2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc',
        'attachment_sha256': coverage['spec_sha256'], 'source_bindings': source,
        'route': 'DIRECT_CODEX_DELIVERY', 'actor': 'CODEX', 'entry': 'START_WITH_PATCH',
        'source_migration': 'Paused audit restarted from current main including FORGE_NATIVE_LIFECYCLE_CLOSURE_V1; old conclusions not carried as acceptance',
        'evidence_roots': ['EVIDENCE_ROOT', 'AUX_EVIDENCE_ROOT'],
        'bootstrap': {'owner_approved': True, 'sources': ['official python image', 'official astral uv image', 'managed CPython distribution via pinned uv', 'existing uv.lock distributions'],
            'python_image': 'python:3.13.14-bookworm@sha256:8b9a8b28d9cc221c6ab5d40e9cfcd99429959f6a8f5171612a99147975ab043f',
            'uv_image': 'ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc',
            'dependency_changes': 0, 'network_during_product_runs': 'NONE'},
        'budget': {'product_run_wall_cap_seconds': 7200, 'memory_per_container': 2147483648,
            'cpu_per_container': 2, 'pids_per_container': 128, 'evidence_cap_bytes': 2147483648,
            'generated_sequences_cap': 200, 'generated_sequences_actual': 24, 'external_model_calls': 0,
            'native_evidence_bytes': post['native_evidence_bytes'], 'archives_bytes': ledger['retained_archives_bytes'],
            'observed_campaign_wall_seconds': (max(end for _, end in clocks) - min(start for start, _ in clocks)).total_seconds(),
            'sum_product_container_seconds': sum((end - start).total_seconds() for start, end in clocks),
            'enforcement': 'Docker RAM/CPU/PID and network/rootfs limits enforced; campaign time/storage monitored by builder, not a disk quota or deterministic scheduler'},
        'worlds': [
            {'id': 'EPISODE_LIST_INPUT', 'source': 'tests.test_forge_research_flow_reliability_v1.create_episode_fixture', 'input': 'controlled external market/collector transport; actual consumer-facing admitted corpus', 'claim': 'Fixture provisioning before audit input boundary; collection not audited'},
            {'id': 'MINIMAL_SESSION_INPUT', 'source': 'tests.test_hfic_session helpers', 'input': 'authored intermediate session/preflight', 'claim': 'CONTRACT_ONLY unless exact persistence segment separately demonstrated'},
            {'id': 'DOWNSTREAM_SCIENCE_INPUT', 'source': 'tests.test_experiment_evidence_decision_v1._eligible_records', 'input': 'authored eligible scientific records/binding', 'claim': 'SEGMENT_PRODUCT_PATH from downstream input, skips scientific producer; never FULL_PRODUCT_PATH'},
            {'id': 'WAL_AND_CRASH', 'source': 'product_probes.py', 'input': 'fresh synthetic owned stores; actual OS child exits', 'claim': 'SEGMENT_PRODUCT_PATH'},
            {'id': 'PAIRED_METRIC', 'source': 'metric_probe.py', 'input': 'declared row/binding inputs for actual mean metric', 'claim': 'CONTRACT_ONLY'}],
        'boundary_graph': [
            {'edge': 'Forge-ready scope -> real grounded look -> frozen candidates', 'status': 'TESTED_SEGMENT', 'evidence': 'spine/producer/branches'},
            {'edge': 'freeze -> Critic -> revision/runner-up -> classifier', 'status': 'TESTED_SCRIPTED_TRANSPORT', 'evidence': 'spine/critic/interactions'},
            {'edge': 'candidate -> operator-authored frozen ExperimentSpec -> real fixed-time runner', 'status': 'TESTED_SEGMENT', 'evidence': 'producer/spine'},
            {'edge': 'real completed runner -> owner dossier', 'status': 'FAIL', 'evidence': 'BAA-002'},
            {'edge': 'fixed-time proxy -> chronological/OOS successor', 'status': 'BLOCKED_PRODUCT_ROUTE', 'evidence': 'BAA-003'},
            {'edge': 'authored downstream scientific records -> owner decision -> frozen handoff -> CHECK/RENDER/VERIFY', 'status': 'TESTED_SEGMENT', 'evidence': 'core/science_to_strategy_handoff tests'},
            {'edge': 'new agent discovers and executes routes', 'status': 'BLOCKED_ENVIRONMENT', 'evidence': 'actor_missions.json'}],
        'exclusions': ['collector/release internals', 'real providers/RPC/WSS', 'production databases', 'real holdout', 'real science trials', 'strategy activation/execution', 'wallet/signer/money', 'runtime health/alpha claims'],
        'clock_model': 'Product synthetic UTC clocks are fixed in selected fixtures; host wall clock controls bounded run time. No deterministic OS scheduling claim.',
        'fidelity_policy': 'Existing mocked/hand-bound unit assertions are CONTRACT_ONLY. Product-path and downstream-fixture segments never sum to FULL_PRODUCT_PATH.',
        'genuine_actor': 'BLOCKED_ENVIRONMENT; all tool lanes must be confined before invoking actors'}
    dump('campaign-manifest.json', manifest)
    successful = {r['test_id'] for r in ledger['test_attempts'] if r['status'] == 'PASS'}
    dump('campaign-summary.json', {'schema': 'baa.campaign-summary.v1', 'task_id': 'BIG_AGENTIC_AUDIT_V1',
        'base_commit': BASE, 'audit_completion': 'PARTIAL_BLOCKED',
        'inventory_denominator': 56, 'accounted_charters': 56, 'visited_charters': coverage['visited_charters'],
        'charter_result_counts': coverage['charter_result_counts'], 'unique_test_ids': ledger['unique_test_ids'],
        'unique_test_ids_ever_passed': len(successful), 'test_attempt_counts': ledger['test_attempt_counts'],
        'product_defects': ['BAA-001', 'BAA-002'], 'product_route_gaps': ['BAA-003'],
        'completed_native_runs': sum(r['status'] == 'COMPLETE' for r in ledger['runs']),
        'full_product_path_proven': False, 'genuine_actor': 'AGENT_BEHAVIOR_UNVERIFIED',
        'recommended_now': 'BAA-002 source-bound native run-to-dossier linkage; scientific promotion refusal preserved',
        'production_mutations': 0, 'product_source_repairs': 0, 'owned_background_processes': post['owned_background_processes'],
        'external_product_calls': 0, 'synthetic_alpha_claim': False,
        'non_claims': ['AUDIT_FULL_DOD_INCOMPLETE', 'NO_SCIENCE_ACCEPTANCE', 'NO_STRATEGY_ACTIVATION', 'NO_PRODUCTION_HEALTH', 'NO_MERGE']})


if __name__ == '__main__':
    main()
