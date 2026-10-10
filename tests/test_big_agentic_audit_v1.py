"""Controls against vacuous PASS and swallowed evidence failures."""
import json
import unittest
import tempfile
import subprocess
import sys
from pathlib import Path
from tests.fixtures.big_agentic_audit_v1.oracles import (
    grade, collect_findings, grade_bridge, grade_wal,
    evidence_witnesses, interaction_result)


class AuditOracleControls(unittest.TestCase):
    def setUp(self):
        self.trace = [{'seq': 1, 'kind': 'HEADER'}, {'seq': 2, 'kind': 'CAMPAIGN_TERMINAL'}]

    def evaluate(self, **changes):
        return grade(**dict(dict(visited=True, expected='COMPLETE', state='COMPLETE',
                                 readout='COMPLETE', trace=self.trace), **changes))

    def test_valid_control(self):
        self.assertEqual(self.evaluate()['status'], 'PASS')

    def test_observer_rejects_state_readout_disagreement(self):
        self.assertEqual(self.evaluate(readout='RUNNING')['status'], 'FAIL')

    def test_unvisited_boundary_cannot_pass(self):
        self.assertEqual(self.evaluate(visited=False)['status'], 'UNKNOWN')

    def test_truncated_and_dropped_traces_are_incomplete(self):
        for trace in (self.trace[:1], self.trace[1:],
                      [self.trace[0], {'seq': 3, 'kind': 'CAMPAIGN_TERMINAL'}]):
            with self.subTest(trace=trace):
                self.assertFalse(self.evaluate(trace=trace)['trace_complete'])

    def test_known_failure_survives_aggregation(self):
        rows = [self.evaluate(), self.evaluate(state='RUNNING', readout='RUNNING')]
        findings = collect_findings(rows)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['classification'], 'PRODUCT_DEFECT')

    def test_bridge_requires_execution_refusal_and_readonly_guards(self):
        good = {'producer_complete_for_exact_spec': True,
                'planes': {'execution': 'COMPLETED'},
                'promotion_refusal_check': 'PASS', 'readonly_check': 'PASS'}
        self.assertEqual(grade_bridge(good), 'PASS')
        for change in ({'producer_complete_for_exact_spec': False},
                       {'planes': {'execution': 'NO_RUN'}},
                       {'promotion_refusal_check': 'FAIL'}, {'readonly_check': 'FAIL'}):
            self.assertEqual(grade_bridge({**good, **change}), 'FAIL')

    def test_wal_requires_fresh_readers_and_unchanged_inventory(self):
        good = {'expected': 'COMPLETE', 'operational_store_actual': 'COMPLETE',
                'lifecycle_projection_actual': 'COMPLETE',
                'read_only_physical_inventory_unchanged': True}
        self.assertEqual(grade_wal(good), 'PASS')
        for change in ({'operational_store_actual': 'RUNNING'},
                       {'lifecycle_projection_actual': 'RUNNING'},
                       {'read_only_physical_inventory_unchanged': False}):
            self.assertEqual(grade_wal({**good, **change}), 'FAIL')

    def test_summary_without_complete_trace_cannot_close_unittest_coverage(self):
        ledger = {'runs': [{'attempt': 'a', 'status': 'COMPLETE', 'trace_complete': False}],
                  'test_attempts': [{'attempt': 'a', 'test_id': 'real-test', 'status': 'PASS'}],
                  'probes': []}
        self.assertEqual(evidence_witnesses(ledger), [])
        ledger['runs'][0]['trace_complete'] = True
        self.assertEqual(len(evidence_witnesses(ledger)), 1)
        ledger['test_attempts'][0]['valid_for_coverage'] = False
        self.assertEqual(evidence_witnesses(ledger), [])

    def test_interactions_require_completed_actual_proof_and_preserve_failure(self):
        ledger = {'runs': [{'attempt': 'a', 'status': 'INCOMPLETE'}],
                  'test_attempts': [], 'probes': [{'attempt': 'a', 'id': 'triple', 'status': 'PASS'}]}
        self.assertEqual(interaction_result(evidence_witnesses(ledger), 'triple')['result'], 'UNKNOWN')
        ledger['runs'][0]['status'] = 'COMPLETE'
        self.assertEqual(interaction_result(evidence_witnesses(ledger), 'triple')['result'], 'PASS')
        ledger['probes'][0]['status'] = 'FAIL'
        self.assertEqual(interaction_result(evidence_witnesses(ledger), 'triple')['result'], 'FAIL')
        self.assertEqual(interaction_result(evidence_witnesses(ledger), 'missing')['result'], 'UNKNOWN')

    def test_replay_collector_preserves_existing_output(self):
        from tests.fixtures.big_agentic_audit_v1.collect_evidence import collect
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.baa-evidence-owner').write_text('BAA-2026-10-10-V1')
            output = root / 'replay'
            output.mkdir()
            ledger = output / 'run-ledger.json'
            ledger.write_text('original campaign')
            with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_EXISTS'):
                collect(root, output)
            self.assertEqual(ledger.read_text(), 'original campaign')

    def test_empty_replay_does_not_inherit_baseline_failure_or_observations(self):
        script = Path(__file__).parent / 'fixtures/big_agentic_audit_v1/assemble_coverage.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'run-ledger.json').write_text(json.dumps(
                {'runs': [], 'test_attempts': [], 'probes': []}))
            subprocess.run([sys.executable, '-B', str(script), '--ledger-root', str(root),
                            '--output-root', str(root)], check=True, capture_output=True)
            coverage = json.loads((root / 'coverage.json').read_text(encoding='utf-8'))
            rows = {row['charter_id']: row for row in coverage['charters']}
            self.assertEqual(rows['D07']['result'], 'UNKNOWN')
            self.assertEqual(rows['F08']['result'], 'UNKNOWN')
            self.assertEqual(coverage['sequence_exploration']['sequences'], 0)
            self.assertEqual(coverage['typed_science_refusal'], 'UNKNOWN_NOT_OBSERVED_IN_THIS_LEDGER')
            self.assertEqual(coverage['fixture_handoff'], 'UNKNOWN_NOT_OBSERVED_IN_THIS_LEDGER')
            self.assertFalse(any(row['result'] in ('PASS', 'FAIL') for row in rows.values()))

    def test_committed_coverage_never_grants_unvisited_pass(self):
        path = Path(__file__).resolve().parents[1] / 'docs/evidence/big_agentic_audit_v1/coverage.json'
        if not path.exists():
            self.skipTest('coverage not finalized yet')
        coverage = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(coverage['charters']), 56)
        for row in coverage['charters']:
            if row['result'] == 'PASS':
                self.assertTrue(row['visited'])
                self.assertTrue(row['evidence_refs'])

    def test_retained_material_failures_have_backlog_records(self):
        root = Path(__file__).resolve().parents[1] / 'docs/evidence/big_agentic_audit_v1'
        ledger = json.loads((root / 'run-ledger.json').read_text(encoding='utf-8'))
        findings = [json.loads(line) for line in (root / 'findings.jsonl').read_text(encoding='utf-8').splitlines()]
        represented = set().union(*(set(row.get('attempts', [])) for row in findings))
        for probe in ledger['probes']:
            if probe['status'] == 'FAIL':
                self.assertIn(probe['attempt'], represented)


if __name__ == '__main__':
    unittest.main()
