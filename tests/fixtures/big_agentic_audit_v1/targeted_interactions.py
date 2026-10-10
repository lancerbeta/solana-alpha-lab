"""Actual interrupted primary-KILL/frozen-runner-up handoff. External Critic scripted."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path[:0] = ['/repo', '/repo/src', '/kit']
from safety_preflight import check
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.hfic_session import load_session_bundle, finalize_session
from tests.test_hfic_cli import critic_result_from_packet_only


def main():
    assert check()['pass']
    root = Path('/audit/interactions')
    root.mkdir()
    child = """import os,json,sys
sys.path[:0]=['/repo','/repo/src']
from pathlib import Path
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.hfic_session import freeze_draft,finalize_session
from tests.test_hfic_session import valid_draft,_preflight_receipt
from tests.test_hfic_cli import critic_result_from_packet_only
root=Path(sys.argv[1]);s=ResearchStore(root/'plane')
f=freeze_draft(valid_draft(),preflight_receipt=_preflight_receipt(),repo_root=Path('/repo'))
p=finalize_session(f,critic_result_from_packet_only(f['critic_input_packet'],'KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED'),store=s,repo_root=Path('/repo'))
(root/'restart-input.json').write_text(json.dumps({'session_id':f['session_id'],'c1':f['selected_candidate_id'],'c2':f['runner_up_candidate_id'],'c2_packet_sha256':f['runner_up_critic_input_packet_sha256']}))
assert p['session_state']=='RUNNER_UP_AWAITING_CRITIC'
os._exit(73)
"""
    run = subprocess.run([sys.executable, '-B', '-c', child, str(root)], capture_output=True, timeout=60)
    if run.returncode != 73:
        raise SystemExit('INTERACTION_CHILD_NOT_AT_DECLARED_BOUNDARY')
    restart = json.loads((root / 'restart-input.json').read_text())
    store = ResearchStore(root / 'plane', create_if_missing=False)
    pending = load_session_bundle(store, restart['session_id'])
    before = store.diagnostics().committed_inventory_sha256
    critic = critic_result_from_packet_only(pending['critic_input_packet'], 'KILL_MECHANISM')
    final = finalize_session(pending, critic, store=store, repo_root=Path('/repo'))
    readback = load_session_bundle(ResearchStore(root / 'plane', create_if_missing=False), restart['session_id'])
    checks = {'child_abrupt_exit': run.returncode == 73,
        'same_frozen_c2': pending['critic_input_packet_sha256'] == restart['c2_packet_sha256'],
        'pending_stage': pending['session_state'] == 'RUNNER_UP_AWAITING_CRITIC',
        'terminal_persisted': readback['session_state'] == final['session_state'] == 'SYNTHESIS_COMPLETE',
        'c1_preserved': final['decisions'][restart['c1']]['reason_code'] == 'KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED',
        'c2_only': final['decisions'][restart['c2']]['reason_code'] == 'KILL_MECHANISM'}
    proof = {'id': 'C03-KILL-FROZEN-RUNNERUP-CRASH', 'fidelity': 'SEGMENT_PRODUCT_PATH',
        'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
        'schedule': ['authored bounded draft/preflight seam', 'real freeze', 'scripted primary KILL',
            'real pending handoff persisted', 'owned child os._exit73', 'independent reload',
            'scripted frozen C2 result', 'real finalize and independent readback'],
        'llm_behavior_tested': False, 'inventory_before_resume': before,
        'inventory_after_resume': store.diagnostics().committed_inventory_sha256,
        'record_ids': [r.record_id for r in store.iter_committed_records()]}
    (root / 'interactions-summary.json').write_text(json.dumps({'proofs': [proof]}, indent=2))
    print(json.dumps({'status': proof['status'], 'checks': checks}))
    return 0 if proof['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
