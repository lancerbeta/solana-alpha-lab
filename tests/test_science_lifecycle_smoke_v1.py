"""Verify real saved receipts and falsify status-only/incorrect numerical audit claims."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/'tests/fixtures/science_lifecycle_smoke_v1'
sys.path.insert(0,str(KIT))
from verify_saved import verify,verify_run,verify_failure_receipts

EVIDENCE=ROOT/'docs/evidence/science_lifecycle_smoke_v1'

class ScienceLifecycleSavedTests(unittest.TestCase):
    def setUp(self):
        self.numeric=json.loads((EVIDENCE/'numerical.json').read_text(encoding='utf-8'))

    def test_actual_saved_witnesses_and_partial_coverage(self):
        result=verify(EVIDENCE)
        self.assertEqual(result['charges'],{'main':4,'evaluator':8,'confirmation':0})

    def test_forged_complete_without_native_commit_is_rejected(self):
        run=copy.deepcopy(self.numeric['runs']['LIST_CONTRAST']);run['records']=[]
        with self.assertRaisesRegex(AssertionError,'NO_UNIQUE_COMMITTED_COMPLETION'):
            verify_run(run,self.numeric['oracle_rows'],'LIST_CONTRAST')

    def test_swapped_comparator_and_result_artifact_are_rejected(self):
        from oracle import check_summary
        summary=copy.deepcopy(self.numeric['runs']['LIST_CONTRAST']['response']['capability_result']['summary'])
        summary['research_scope']['contrast']['observed_target_difference']=.055
        with self.assertRaises(AssertionError):check_summary(summary,self.numeric['oracle_rows'],'LIST_CONTRAST')
        run=copy.deepcopy(self.numeric['runs']['LIST_CONTRAST'])
        run['artifact']['capability_result_sha256']='0'*64
        with self.assertRaises(AssertionError):verify_run(run,self.numeric['oracle_rows'],'LIST_CONTRAST')

    def test_wrong_membership_is_rejected_independently_of_correct_means(self):
        run=copy.deepcopy(self.numeric['runs']['MIXED_LIST_NUMERIC'])
        run['classifier']['episode_outcome_binding']['membership'][0]['matched']=False
        with self.assertRaisesRegex(AssertionError,'MEMBERSHIP_ORACLE_MISMATCH'):
            verify_run(run,self.numeric['oracle_rows'],'MIXED_LIST_NUMERIC')

    def test_required_guard_and_recovery_receipts_cannot_disappear(self):
        original=json.loads((EVIDENCE/'readback.json').read_text(encoding='utf-8'))
        for name in original['negative_runner_receipts']:
            corrupted=copy.deepcopy(original)
            del corrupted['negative_runner_receipts'][name]
            with self.subTest(negative=name),self.assertRaisesRegex(AssertionError,'REQUIRED_NEGATIVE_WITNESSES_MISSING'):
                verify_failure_receipts(corrupted)
        for mode in original['faults']:
            corrupted=copy.deepcopy(original)
            del corrupted['faults'][mode]
            with self.subTest(fault=mode),self.assertRaisesRegex(AssertionError,'REQUIRED_FAULT_WITNESSES_MISSING'):
                verify_failure_receipts(corrupted)
        corrupted=copy.deepcopy(original)
        corrupted['missing_403']['receipt']['response']['status']='COMPLETE'
        with self.assertRaisesRegex(AssertionError,'MISSING_SPECIMEN_FALSE_SUCCESS'):
            verify_failure_receipts(corrupted)

    def test_cohort_and_calendar_coverage_cannot_disappear_or_duplicate(self):
        from oracle import check_summary
        summary=self.numeric['runs']['LIST_CONTRAST']['response']['capability_result']['summary']
        for key in ('by_cohort','by_calendar_block'):
            for replacement in ([],[summary[key][0],summary[key][0]]):
                corrupted=copy.deepcopy(summary)
                corrupted[key]=replacement
                with self.subTest(group=key,replacement=len(replacement)),self.assertRaisesRegex(AssertionError,'COVERAGE_MISMATCH'):
                    check_summary(corrupted,self.numeric['oracle_rows'],'LIST_CONTRAST')

    def test_saved_time_geometry_rejects_wrong_deadline(self):
        from chronology_oracle import verify as verify_chronology
        receipt=json.loads((EVIDENCE/'chronology-geometry.json').read_text(encoding='utf-8'))
        receipt['cells'][1]['points']['E14400']['availability_deadline']='2026-10-30T04:40:00Z'
        with self.assertRaisesRegex(AssertionError,'INDEPENDENT_TIME_GEOMETRY_MISMATCH'):
            verify_chronology(receipt)

if __name__=='__main__':unittest.main()
