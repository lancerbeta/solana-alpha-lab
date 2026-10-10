"""Audit-only independent grading. No production enum or policy replacement."""
from __future__ import annotations


def grade(*, visited: bool, expected, state, readout, trace: list[dict]) -> dict:
    complete = bool(trace) and trace[0].get('kind') == 'HEADER' and trace[-1].get('kind') == 'CAMPAIGN_TERMINAL'
    complete = complete and [r.get('seq') for r in trace] == list(range(1, len(trace) + 1))
    if not visited:
        return {'status': 'UNKNOWN', 'trace_complete': complete, 'finding': None}
    if not complete:
        return {'status': 'UNKNOWN', 'trace_complete': False, 'finding': 'HARNESS_DEFECT:INCOMPLETE_TRACE'}
    if state != expected or readout != state:
        return {'status': 'FAIL', 'trace_complete': True,
                'finding': {'classification': 'PRODUCT_DEFECT', 'expected': expected,
                            'state': state, 'readout': readout}}
    return {'status': 'PASS', 'trace_complete': True, 'finding': None}


def collect_findings(results: list[dict]) -> list:
    return [row['finding'] for row in results if row.get('finding') is not None]


def grade_bridge(result: dict) -> str:
    return 'PASS' if (result.get('producer_complete_for_exact_spec') is True
        and result.get('planes', {}).get('execution') == 'COMPLETED'
        and result.get('promotion_refusal_check') == 'PASS'
        and result.get('readonly_check') == 'PASS') else 'FAIL'


def grade_wal(proof: dict) -> str:
    return 'PASS' if (proof.get('expected') == 'COMPLETE'
        and proof.get('operational_store_actual') == proof['expected']
        and proof.get('lifecycle_projection_actual') == proof['expected']
        and proof.get('read_only_physical_inventory_unchanged') is True) else 'FAIL'


def evidence_witnesses(ledger: dict) -> list[dict]:
    complete = {r['attempt'] for r in ledger['runs'] if r['status'] == 'COMPLETE'}
    traced = {r['attempt'] for r in ledger['runs'] if r['status'] == 'COMPLETE'
              and r.get('trace_complete') is True}
    return [dict(r, id=r['test_id'], kind='unittest') for r in ledger['test_attempts']
            if r['attempt'] in traced and r.get('valid_for_coverage', True)] + [
            dict(r, kind='probe') for r in ledger['probes'] if r['attempt'] in complete]


def interaction_result(witnesses: list[dict], proof_id: str) -> dict:
    rows = [r for r in witnesses if r['id'] == proof_id and r['kind'] == 'probe']
    failed = [r for r in rows if r.get('status') == 'FAIL']
    passed = [r for r in rows if r.get('status') == 'PASS']
    result = 'FAIL' if failed else 'PASS' if passed else 'UNKNOWN'
    return {'result': result, 'evidence': proof_id,
            'evidence_refs': [{'attempt': r['attempt'], 'id': proof_id,
                               'observed': r.get('status')} for r in rows]}
