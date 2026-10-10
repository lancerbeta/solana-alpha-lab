"""Bounded offline replay of existing real seams with retained external observation.

Tests are witnesses of their exact assertions. They are never FULL_PRODUCT_PATH
merely because their names say vertical. Product functions are not substituted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path('/repo')
sys.path[:0] = [str(ROOT), str(ROOT / 'src'), '/kit']
from safety_preflight import check

PHASES = {
    'smoke': [
        'tests.test_research_store.ResearchStoreTests.test_payload_hash_mismatch_is_rejected',
        'tests.test_science_to_strategy_handoff_v1.ScienceToStrategyHandoffTests.test_scenario_a_happy_path_vertical',
    ],
    'core': [
        'tests.test_research_store',
        'tests.test_hfic_session',
        'tests.test_hfic_temporal_discovery_v1',
        'tests.test_forge_reliability_audit_continuation_v1',
        'tests.test_forge_ordinary_operation_lifecycle_v1.OperationCompletionBindingTests',
        'tests.test_forge_research_flow_reliability_v1.CardTransportTests',
        'tests.test_forge_research_flow_reliability_v1.SessionHistoryTests',
        'tests.test_forge_research_flow_reliability_v1.ExplicitOutcomeTests',
        'tests.test_forge_research_flow_reliability_v1.VerifiedReadScopeTests',
        'tests.test_experiment_evidence_decision_v1',
        'tests.test_science_to_strategy_handoff_v1',
        'tests.test_forge_native_lifecycle_closure_v1.ReplanV2AdmissionTests',
        'tests.test_forge_native_lifecycle_closure_v1.SourceDecimalRatioTests',
        'tests.test_forge_native_lifecycle_closure_v1.ExactEpisodeQuantileTests',
    ],
    'spine': [
        'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests',
        'tests.test_hfic_list_aware_vertical_v1.ListAwareVerticalTests',
    ],
    'branches': [
        'tests.test_hfic_ordinary_operation_v1',
        'tests.test_forge_ordinary_operation_lifecycle_v1.OrdinaryOperationLifecycleTests',
        'tests.test_hfic_research_policy_v1',
        'tests.test_hfic_research_policy_closure_v1',
        'tests.test_forge_composite_feature_recipes_v1',
        'tests.test_forge_representation_ladder_v1',
        'tests.test_hfic_critic_prior_memory_closure_v1',
        'tests.test_forge_research_flow_reliability_v1.ReservedLandingTests',
        'tests.test_forge_research_flow_reliability_v1.CrashReservationRecoveryTests',
    ],
    'recovery': [
        'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_base_saved_string_draft_recovers_without_rewrite_or_new_look',
        'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_direct_owner_mutation_changes_only_capability_not_market_or_charges',
    ],
    'science': [
        'tests.test_hfic_selection_robustness_gate_v1.SelectionRobustnessGateTests.test_synthetic_clear_multivariate_detected',
        'tests.test_hfic_selection_robustness_gate_v1.SelectionRobustnessGateTests.test_synthetic_no_separation_not_detected',
        'tests.test_hfic_selection_robustness_gate_v1.SelectionRobustnessGateTests.test_integrity_break_inconclusive',
        'tests.test_hfic_selection_robustness_gate_v1.SelectionRobustnessGateTests.test_seed_replay',
        'tests.test_hfic_censoring_ignorability_diagnostic_v1.HficCensoringIgnorabilityDiagnosticTests.test_no_shift_is_not_mar',
        'tests.test_hfic_censoring_ignorability_diagnostic_v1.HficCensoringIgnorabilityDiagnosticTests.test_y_point_values_are_not_read',
    ],
    'critic': [
        'tests.test_hfic_one_frozen_runner_up_failover_v1',
        'tests.test_hypothesis_forge_independent_critic_v1',
    ],
    'producer': [
        'tests.test_forge_research_flow_reliability_v1.EpisodeFlowTests.test_scripted_positive_boundary_runs_real_classify_final_runner_replay',
    ],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scrub(value):
    text = json.dumps(value, ensure_ascii=False, default=str)
    for source, target in (('/repo/', 'repo:'), ('/audit/', 'evidence:'), ('/kit/', 'kit:')):
        text = text.replace(source, target)
    return json.loads(text)


class Observer:
    def __init__(self, out: Path, phase: str):
        self.out, self.phase, self.current, self.seq = out, phase, 'SETUP', 0
        self.trace = (out / f'{phase}-trace.jsonl').open('x', encoding='utf-8')
        self.temporary_roots = []
        self.events = []

    def emit(self, kind: str, **fields):
        self.seq += 1
        row = scrub({'seq': self.seq, 'phase': self.phase, 'scenario': self.current,
                     'kind': kind, **fields})
        self.trace.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        self.trace.flush()

    def profile(self, frame, event, arg):
        if event != 'return':
            return
        file, name = frame.f_code.co_filename, frame.f_code.co_name
        product = '/solana_alpha_lab/factory/' in file
        helper = '/tests/' in file and name in {'public_cli', '_forge_call', '_discovery',
            '_consume', '_http', 'run_cli', '_bind_experiment'}
        if not helper and not (product and name in {'append', 'start_document', 'finalize_session',
            'freeze_draft', 'classify_lane', 'materialize_strategy_candidate',
            'record_research_decision', 'run_temporal_fixed_time_from_spec'}):
            return
        if isinstance(arg, dict):
            payload = arg
        elif hasattr(arg, 'code'):
            payload = {'code': arg.code}
        elif hasattr(arg, 'terminal'):
            payload = {'terminal': arg.terminal, 'reason_codes': getattr(arg, 'reason_codes', ())}
        elif isinstance(arg, tuple) and any(isinstance(v, dict) for v in arg):
            payload = [v for v in arg if isinstance(v, (dict, int))]
        else:
            payload = {'returned_type': type(arg).__name__}
        self.emit('BOUNDARY_RETURN', callable=file.removeprefix('/repo/') + ':' + name,
                  output=payload)

    def retain_tempdirs(self):
        original = tempfile.TemporaryDirectory
        observer = self

        class Retained(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                resolved = Path(self.name).resolve()
                if not resolved.is_relative_to(Path('/audit')):
                    raise RuntimeError('AUDIT_TEMPDIR_OUTSIDE_TEST_ROOT')
                observer.temporary_roots.append((observer.current, resolved))
                observer.emit('TEMP_ROOT', path=str(resolved))

            def cleanup(self):
                # Audit-only artifact retention, no product function replacement.
                self._finalizer.detach()

        tempfile.TemporaryDirectory = Retained

    def readback(self, test_id: str):
        # A second read path after unittest tearDown, independent of CLI replies.
        from solana_alpha_lab.factory.research_store import ResearchStore
        rows, inventories = [], []
        for scenario, temp_root in self.temporary_roots:
            if scenario != test_id:
                continue
            inventories.append({'root': str(temp_root), 'files': [
                {'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size}
                for p in sorted(temp_root.rglob('*')) if p.is_file()
                and '.git' not in p.parts and p.suffix not in {'.pyc', '.lock'}]})
            # Store root is inferred only from the product-owned commits location.
            for manifests in temp_root.glob('**/research/manifests/partitions'):
                data_root = manifests.parents[2]
                try:
                    store = ResearchStore(data_root, create_if_missing=False)
                    records = list(store.iter_committed_records())
                    rows.append({'root': str(data_root), 'records': [
                        {'record_id': r.record_id, 'record_kind': str(r.record_kind),
                         'entity_id': r.entity_id, 'run_id': r.run_id,
                         'payload_sha256': r.payload_sha256,
                         'payload': json.loads(r.payload_json)} for r in records]})
                except Exception as exc:
                    rows.append({'root': str(data_root), 'readback_error_type': type(exc).__name__})
        name = hashlib.sha256(test_id.encode()).hexdigest()[:16]
        path = self.out / f'{self.phase}-readback-{name}.json'
        path.write_text(json.dumps(scrub({'test_id': test_id, 'inventories': inventories,
                                        'stores': rows}), ensure_ascii=False, sort_keys=True), encoding='utf-8')
        return {'path': path.name, 'sha256': digest(path), 'roots_n': len(inventories), 'stores_n': len(rows)}


class Result(unittest.TestResult):
    def __init__(self, observer):
        super().__init__()
        self.observer, self.rows, self.started, self.outcomes = observer, [], {}, {}

    def startTest(self, test):
        super().startTest(test)
        name = test.id()
        self.observer.current = name
        self.started[name] = time.monotonic()
        self.observer.emit('START')

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = ('PASS', None)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = ('FAIL', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = ('ERROR', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = ('SKIP', reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = ('FAIL', self._exc_info_to_string(err, test))

    def stopTest(self, test):
        status, detail = self.outcomes.get(test.id(), ('UNKNOWN', None))
        proof = self.observer.readback(test.id())
        row = scrub({'test_id': test.id(), 'status': status, 'detail': detail,
                     'wall_seconds': round(time.monotonic() - self.started[test.id()], 3),
                     'independent_readback': proof})
        self.rows.append(row)
        self.observer.emit('TERMINAL', **row)
        print(json.dumps({'test': test.id(), 'status': status, 'seconds': row['wall_seconds']}), flush=True)
        super().stopTest(test)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--output', type=Path, default=Path('/audit'))
    args = parser.parse_args()
    preflight = check()
    if not preflight['pass']:
        raise SystemExit('AUDIT_CONTAINMENT_FAILED')
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    if (out / f'{args.phase}-summary.json').exists():
        raise SystemExit('AUDIT_ATTEMPT_ALREADY_EXISTS_USE_NEW_OUTPUT_ROOT')
    observer = Observer(out, args.phase)
    observer.retain_tempdirs()
    observer.emit('HEADER', base_commit='90ba76e37515b3d521478a6d05a149fb0f1d2b75',
                  runtime=sys.version, interpreter=sys.executable, preflight=preflight,
                  uv_lock_sha256=digest(ROOT / 'uv.lock'), runner_sha256=digest(Path(__file__)),
                  test_selectors=PHASES[args.phase], start_utc=datetime.now(UTC).isoformat())
    sys.setprofile(observer.profile)
    result = Result(observer)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in PHASES[args.phase])
    suite.run(result)
    sys.setprofile(None)
    # Class-setup/teardown failures are not necessarily represented by stopTest.
    omitted = [{'test_id': test.id(), 'status': 'ERROR', 'detail': text}
               for test, text in result.errors if test.id() not in {row['test_id'] for row in result.rows}]
    observer.emit('CAMPAIGN_TERMINAL', tests_run=result.testsRun, omitted_errors=omitted)
    observer.trace.close()
    summary = scrub({'phase': args.phase, 'rows': result.rows + omitted, 'tests_run': result.testsRun,
                     'unittest_success': result.wasSuccessful(), 'trace_complete': True,
                     'trace_sha256': digest(out / f'{args.phase}-trace.jsonl'),
                     'raw_fixture_retention': 'RETAINED_UNDER_EVIDENCE_TMP',
                     'llm_behavior_tested': False, 'full_product_path_claim': False})
    (out / f'{args.phase}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
