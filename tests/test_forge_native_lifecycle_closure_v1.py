"""The public descriptor must suffice to transport an actual saved look."""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(os.environ.get('SMIAL_TEST_REPO_ROOT', Path(__file__).resolve().parents[1]))
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from solana_alpha_lab.factory.hfic_card_projection import authoring_contract, project_material_card
from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError, validate_fresh_card_scope


class PublicBindingContractTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(os.environ.get('SMIAL_PUBLIC_EVIDENCE_FIXTURE', ROOT / 'tests/fixtures/forge_native_lifecycle_closure_v1/public_evidence.json'))
        self.evidence = json.loads(fixture.read_text(encoding='utf-8'))

    def card(self):
        contract = authoring_contract()['saved_look_bindings']
        card = {'claim': 'A fixed observed contrast; descriptive synthetic evidence only.'}
        for field, source in contract['sources'].items():
            value = self.evidence
            for key in source.split('.'):
                if not isinstance(value, dict) or key not in value:
                    break
                value = value[key]
            else:
                card[field] = value
        return project_material_card(card)

    def test_public_bindings_satisfy_actual_fresh_scope_ingress(self):
        card = self.card()
        scope = validate_fresh_card_scope(card, look_scope=self.evidence['candidate_scope'], require_look_axes=True)
        self.assertEqual(scope['target'], self.evidence['candidate_scope']['target'])
        self.assertEqual(scope['research_scope_rule_sha256'], self.evidence['candidate_scope']['research_scope_rule_sha256'])
        self.assertEqual(card['primary_x_family'], self.evidence['descriptive_readout']['scientific_identity']['primary_x_family'])

    def test_missing_public_identity_remains_typed_refusal_not_inferred_scope(self):
        del self.evidence['descriptive_readout']['scientific_identity']['research_scope_statement']
        card = self.card()
        self.assertNotIn('research_scope_statement', card)
        with self.assertRaises(GroundedDiscoveryError) as caught:
            validate_fresh_card_scope(card, look_scope=self.evidence['candidate_scope'], require_look_axes=True)
        self.assertEqual(caught.exception.code, 'CANDIDATE_SCOPE_FIELDS_REQUIRED')
        self.assertIn('research_scope_statement', caught.exception.detail['missing_top_level'])


class OrdinarySavedModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / 'tests/fixtures/forge_native_lifecycle_closure_v1/public_mode_regression.json').read_text(encoding='utf-8'))

    def test_omitted_ordinary_mode_can_reach_the_actual_prior_guard(self):
        from solana_alpha_lab.factory.hfic_grounded_discovery import scope_bound_to_spec, bind_prior_scope_evidence
        scope = scope_bound_to_spec(self.fixture['canonical_query'], self.fixture['candidate_scope'])
        evidence = bind_prior_scope_evidence({'candidate_scope': scope}, [self.fixture['technical_prior']])
        self.assertEqual(evidence['candidate_scope']['evidence_surface_mode'], 'ORDINARY_GROUNDED_DISCOVERY_V1')
        self.assertEqual(evidence['prior_scope_relations'][0]['relation'], 'NON_BLOCKING_PRIOR')

    def test_explicit_malformed_mode_is_not_treated_as_omission(self):
        from solana_alpha_lab.factory.hfic_grounded_discovery import scope_bound_to_spec
        for value in (None, '', '   ', 0, False, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(GroundedDiscoveryError) as caught:
                    scope_bound_to_spec(self.fixture['canonical_query'], {**self.fixture['candidate_scope'], 'evidence_surface_mode': value})
                self.assertEqual(caught.exception.code, 'CANDIDATE_SCOPE_FIELDS_REQUIRED')

    def test_explicit_mode_is_not_overwritten_to_hide_a_contradiction(self):
        from solana_alpha_lab.factory.hfic_grounded_discovery import scope_bound_to_spec
        authored = {**self.fixture['candidate_scope'], 'evidence_surface_mode': 'CURRENT_REPRESENTATION_CONTROL_V1'}
        conflicting = scope_bound_to_spec(self.fixture['canonical_query'], authored)
        self.assertEqual(conflicting['evidence_surface_mode'], authored['evidence_surface_mode'])
        from solana_alpha_lab.factory.hfic_session import _bind_selected_look, HficSessionError
        # Actual ordinary preflight publishes no authoritative mode: legacy
        # explicit labels are retained, not silently coerced or newly authorized.
        ordinary_ingress = _bind_selected_look({'candidate_scope': conflicting}, conflicting, store=None, evidence_surface_mode=None)
        self.assertEqual(ordinary_ingress['candidate_scope']['evidence_surface_mode'], authored['evidence_surface_mode'])
        self.assertEqual(ordinary_ingress['look_scope_relation'], 'LOOK_SCOPE_MATCH')
        # Only an actually published authoritative ingress mode enforces conflict.
        ordinary = {**conflicting, 'evidence_surface_mode': 'ORDINARY_GROUNDED_DISCOVERY_V1'}
        with self.assertRaises(HficSessionError) as caught:
            _bind_selected_look({'candidate_scope': conflicting}, conflicting, store=None, evidence_surface_mode=ordinary['evidence_surface_mode'])
        self.assertEqual(caught.exception.code, 'LOOK_SCOPE_CONTRADICTION')


class LosslessCaptureTests(unittest.TestCase):
    def test_timeout_keeps_partial_bytes_unknown_effect_and_reserved_name(self):
        import io
        import runpy
        import subprocess
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            argv = ['capture', '--eval', str(work / 'eval'), '--data', str(work / 'plane'), '--out', str(work / 'outputs'), '--name', 'original-attempt', '--', 'show-session', '--session-id', 'saved-session', '--format', 'json']
            partial_out, partial_err = b'{"partial":', b'partial diagnostic\n'
            timeout = subprocess.TimeoutExpired(['public-command'], 240, output=partial_out, stderr=partial_err)
            script = ROOT / 'tests/fixtures/forge_native_lifecycle_closure_v1/capture_cli.py'
            with patch.object(sys, 'argv', argv), patch.object(sys, 'stdout', SimpleNamespace(buffer=io.BytesIO())), patch.object(sys, 'stderr', SimpleNamespace(buffer=io.BytesIO())), patch('subprocess.run', side_effect=timeout), self.assertRaises(SystemExit) as stopped:
                runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(stopped.exception.code, 124)
            out = work / 'outputs'
            self.assertEqual((out / 'original-attempt.stdout.json').read_bytes(), partial_out)
            self.assertEqual((out / 'original-attempt.stderr.txt').read_bytes(), partial_err)
            action = json.loads((out / 'cli-actions.jsonl').read_text(encoding='utf-8'))
            self.assertTrue(action['timed_out'])
            self.assertEqual(action['side_effect_status'], 'UNKNOWN_READ_SAVED_STATE_FIRST')
            with patch.object(sys, 'argv', argv), patch('subprocess.run') as child, self.assertRaises(SystemExit) as duplicate:
                runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(duplicate.exception.code, 'CAPTURE_EXISTS_USE_NEW_INVOCATION_NAME')
            child.assert_not_called()


if __name__ == '__main__':
    unittest.main()
