"""Bind the fixed charter denominator to retained evidence; never infer science."""
import hashlib
import argparse
import json
from pathlib import Path
import re
from collections import Counter
from oracles import evidence_witnesses, interaction_result

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/evidence/big_agentic_audit_v1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-root', type=Path, default=OUT)
    parser.add_argument('--output-root', type=Path, default=OUT)
    parser.add_argument('--refresh-baseline', action='store_true')
    args = parser.parse_args()
    if (args.output_root / 'coverage.json').exists() and not args.refresh_baseline:
        raise ValueError('OUTPUT_ALREADY_EXISTS_USE_NEW_REPLAY_OUTPUT')
    spec = ROOT / 'docs/reports/big_agentic_audit_v1/SPEC.md'
    inventory = re.findall(r'^\| ([A-F]\d\d) \| (.+?) \| (.+?) \|$', spec.read_text(encoding='utf-8'), re.M)
    assert len(inventory) == 56
    plan = json.loads((Path(__file__).parent / 'charter_bindings.json').read_text())
    ledger = json.loads((args.ledger_root / 'run-ledger.json').read_text(encoding='utf-8'))
    witnesses = evidence_witnesses(ledger)
    sequences = {r['id']: r for r in witnesses if r['kind'] == 'probe'
                 and r['id'].startswith('SEQ-')}
    bridges = [r for r in witnesses if r['id'] == 'F08-PRODUCER-DOSSIER-LINK']
    observed_link_gap = any(r.get('producer_complete_for_exact_spec') is True
                           and r.get('planes', {}).get('execution') == 'NO_RUN' for r in bridges)
    refusal = any(r.get('promotion_refusal_check') == 'PASS' for r in bridges)
    fixture_handoff = any(r.get('status') == 'PASS' and 'happy_path_vertical' in r['id']
                          for r in witnesses)
    rows = []
    for charter, goal, oracle in inventory:
        proposed, fidelity, selectors, limit = plan['bindings'][charter]
        refs, missing = [], []
        for selector in selectors:
            stem, _, subcheck = selector.partition('#')
            matching = [r for r in witnesses if stem in r['id']]
            # An initial failed harness attempt can be superseded only by a
            # retained successful exact-test attempt; it remains in the ledger.
            successful = [r for r in matching if r.get(subcheck or 'status') == 'PASS']
            valid = successful if proposed == 'PASS' else matching
            if not valid:
                missing.append(selector)
            for item in valid:
                refs.append({'attempt': item['attempt'], 'id': item['id'],
                             'kind': item['kind'], 'check': subcheck or 'status',
                             'observed': item.get(subcheck or 'status')})
        result = 'UNKNOWN' if proposed == 'PASS' and missing else proposed
        if proposed == 'FAIL' and not any(ref['observed'] == 'FAIL' for ref in refs):
            result = 'UNKNOWN'
        rows.append({'charter_id': charter, 'goal': goal, 'oracle': oracle,
            'result': result, 'fidelity': fidelity, 'visited': bool(refs),
            'evidence_refs': refs, 'unresolved_selectors': missing,
            'limitation': limit, 'full_product_path': False})
    payload = {'schema': 'baa.coverage.v1', 'audit_completion': 'PARTIAL_BLOCKED',
        'spec_sha256': hashlib.sha256(spec.read_bytes()).hexdigest(),
        'inventory_denominator': 56, 'inventory_accounted': len(rows),
        'visited_charters': sum(r['visited'] for r in rows),
        'charter_result_counts': dict(Counter(r['result'] for r in rows)),
        'full_product_path_proven': False, 'agent_behavior': 'AGENT_BEHAVIOR_UNVERIFIED',
        'mapping_timing': plan['mapping_timing'], 'charters': rows,
        'interactions': [
            {'factors': 'new evidence x pending reservation x resume', 'result': 'UNKNOWN', 'reason': 'Factors tested separately, complete three-factor schedule not executed'},
            {'factors': 'post-append crash x repeated request x second writer', **interaction_result(witnesses, 'D02-POSTAPPEND-REPEAT-SECOND-WRITER')},
            {'factors': 'late availability x normalized feature x chronological split', 'result': 'BLOCKED', 'reason': 'E03 no bound chronological runner'},
            {'factors': 'related prior x same display title x changed experiment hash', 'result': 'UNKNOWN', 'reason': 'Separate prior/title/hash controls only, not one joint schedule'},
            {'factors': 'primary KILL x frozen runner-up x interrupted Critic handoff', **interaction_result(witnesses, 'C03-KILL-FROZEN-RUNNERUP-CRASH')},
            {'factors': 'STOP x late result landing x changed universe profile', 'result': 'UNKNOWN', 'reason': 'STOP and result/cap/universe branches executed separately, joint race not executed'},
            {'factors': 'read-only view x concurrent writer x committed uncheckpointed state', **interaction_result(witnesses, 'D07-WAL-COMMITTED-VIEW')}],
        'sequence_exploration': {'seeds': sorted({r['seed'] for r in sequences.values()}),
                                 'sequences': len(sequences),
                                 'observed_steps': sorted({len(r['actions']) for r in sequences.values()}),
                                 'domain': 'ResearchStore append/replay/conflict/read-only'},
        'downstream_gap': 'OBSERVED_NATIVE_COMPLETED_RUN_TO_DOSSIER_NO_RUN' if observed_link_gap else 'UNKNOWN_NOT_OBSERVED_IN_THIS_LEDGER',
        'typed_science_refusal': 'PROMOTE_BLOCKED' if refusal else 'UNKNOWN_NOT_OBSERVED_IN_THIS_LEDGER',
        'fixture_handoff': 'SEGMENT_PRODUCT_PATH using authored downstream scientific records, skips upstream science' if fixture_handoff else 'UNKNOWN_NOT_OBSERVED_IN_THIS_LEDGER'}
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / 'coverage.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: payload[k] for k in ('charter_result_counts', 'visited_charters')}))
    print(json.dumps({r['charter_id']: r['unresolved_selectors'] for r in rows if r['unresolved_selectors']}))


if __name__ == '__main__':
    main()
