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


if __name__ == '__main__':
    unittest.main()
