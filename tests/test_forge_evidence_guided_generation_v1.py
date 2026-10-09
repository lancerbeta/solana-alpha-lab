"""Evidence-guided generation: synthetic sources, production admission/freeze."""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.hfic_card_projection import project_material_card
from solana_alpha_lab.factory.hfic_identity import candidate_identity
from solana_alpha_lab.factory.hfic_memory_policy import iter_search_memory_hypothesis_payloads
from solana_alpha_lab.factory.hfic_prior_memory import PriorMemoryCapacityError, build_prior_memory_snapshot
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore
from tests import test_forge_research_flow_reliability_v1 as flow
from tests.test_hfic_critic_prior_memory_closure_v1 import _event
from solana_alpha_lab.factory.hfic_generation_context import (
    GenerationContextError, collect_verified_priors, rank_structural_priors,
    select_working_snapshot,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes


class SelectionSafetyTests(unittest.TestCase):
    def inventory(self, count=100):
        import tempfile
        holder=tempfile.TemporaryDirectory();self.addCleanup(holder.cleanup)
        store=ResearchStore(Path(holder.name).resolve())
        seed_history(store,count)
        return store,collect_verified_priors(store,as_of='2026-10-09T00:00:00Z')

    def test_archive_exceeds_packet_bound_and_mandatory_tail_remains_visible(self):
        store,archive=self.inventory()
        view=select_working_snapshot(archive,query={},inventory_digest=store.diagnostics().committed_inventory_sha256,max_records=8,consulted_refs=['HYP-EGG-00099'])
        self.assertEqual(view['archive_eligible_count'],100)
        self.assertEqual(view['emitted_count'],8)
        self.assertEqual(view['omitted_count'],92)
        self.assertFalse(view['archive_complete_in_packet'])
        self.assertTrue(view['selection_complete'])
        self.assertEqual(view['capsules'][0]['hypothesis_version_id'],'HYP-EGG-00099')
        self.assertEqual(view['bytes'],len(canonical_json_bytes(view)))
        self.assertNotIn('complete',view)

    def test_mandatory_overflow_fails_without_history_write(self):
        store,archive=self.inventory(9)
        before=store.diagnostics().committed_inventory_sha256
        with self.assertRaises(GenerationContextError) as caught:
            select_working_snapshot(archive,query={},inventory_digest=before,max_records=8,mandatory_ids=[c['hypothesis_version_id'] for c in archive['capsules']])
        self.assertEqual(caught.exception.code,'GENERATION_MANDATORY_CONTEXT_EXCEEDS_BOUND')
        self.assertEqual(before,store.diagnostics().committed_inventory_sha256)

    def test_parent_metadata_bytes_are_part_of_bound(self):
        store,archive=self.inventory(8)
        with self.assertRaises(GenerationContextError):
            select_working_snapshot(archive,query={},inventory_digest='f'*64,parent_budget_bytes=200,mandatory_ids=['HYP-EGG-00000'])

    def test_revision_keeps_optional_tail_removable_near_parent_byte_bound(self):
        from unittest.mock import patch
        from solana_alpha_lab.factory import hfic_generation_context as context
        store, archive = self.inventory(50)
        required = [f'HYP-EGG-{i:05d}' for i in range(8)]
        memory = select_working_snapshot(archive, query={}, inventory_digest='f'*64,
                                        mandatory_ids=required)
        parent = context.fit_working_packet({'prior_memory':memory,
            'generation_context':context.generation_brief(memory=memory), 'metadata':'x'*4000})
        frozen = copy.deepcopy(parent)
        with patch.object(context, 'collect_verified_priors', return_value=archive), \
             patch.object(context, 'check_full_prior_scope', return_value=({}, {})):
            _, revised, brief = context.candidate_working_view(store,
                preflight={'forge_context_packet':{'prior_memory_working_view':parent['prior_memory']}},
                card={}, evidence={}, cutoff=memory['research_log_cutoff'],
                inventory_digest='f'*64, repo_root=ROOT,
                preserve_selected_as_mandatory=False)
        self.assertEqual(revised['mandatory_count'],8)
        trial = {'prior_memory':revised, 'generation_context':brief, 'metadata':'x'*4000}
        trial = context.fit_working_packet(trial)
        before = trial['prior_memory']['emitted_count']
        trial['metadata'] += 'x'*(65537-len(canonical_json_bytes(trial)))
        fitted = context.fit_working_packet(trial)
        self.assertLess(fitted['prior_memory']['emitted_count'],before)
        self.assertLessEqual(len(canonical_json_bytes(fitted)),65536)
        self.assertEqual(fitted['prior_memory']['mandatory_count'],8)
        self.assertTrue(set(required).issubset({c['hypothesis_version_id'] for c in fitted['prior_memory']['capsules']}))
        self.assertEqual(parent,frozen)

    def test_structural_relevance_precedes_narrative_and_outcome_sign(self):
        rows=[{'hypothesis_version_id':'A','population':'OTHER','claim':'holders holders','reason_code':'PASS'},
              {'hypothesis_version_id':'B','population':'EPISODES','reason_code':'KILL_DATA_INFEASIBLE'}]
        self.assertEqual(rank_structural_priors(rows,query={'population':'EPISODES'},focus='holders')[0],'B')
        changed=[{**r,'reason_code':'PASS' if r['hypothesis_version_id']=='B' else 'KILL_DATA_INFEASIBLE'} for r in rows]
        self.assertEqual(rank_structural_priors(rows,query={'population':'EPISODES'},focus='holders'),rank_structural_priors(changed,query={'population':'EPISODES'},focus='holders'))

    def test_diversity_precedes_repeat_text_matches(self):
        rows=[{'hypothesis_version_id':f'A{i}','population':'EPISODES','field_id':'X','claim':'holders'} for i in range(3)]
        rows.append({'hypothesis_version_id':'B','population':'EPISODES','field_id':'Y','claim':'other'})
        ranked=rank_structural_priors(rows,query={'population':'EPISODES'},focus='holders')
        self.assertEqual(ranked[:2],['A0','B'])

    def test_both_research_clocks_and_own_session_control_eligibility(self):
        import tempfile
        holder=tempfile.TemporaryDirectory();self.addCleanup(holder.cleanup)
        store=ResearchStore(Path(holder.name).resolve());at=datetime(2026,10,8,tzinfo=UTC);future=datetime(2026,10,10,tzinfo=UTC)
        records=[]
        for hyp in ('VISIBLE','FUTURE_VALID','FUTURE_AVAILABLE'):
            payload={'hypothesis_version_id':hyp,'session_id':'OWN','claim':'Recorded premise'}
            event=_event(record_id=hyp,kind=RecordKind.HYPOTHESIS_VERSION,entity_id=hyp,hypothesis_version_id=hyp,payload=payload,created=at)
            if hyp=='FUTURE_VALID':event=event.model_copy(update={'effective_at':future})
            if hyp=='FUTURE_AVAILABLE':event=event.model_copy(update={'first_reliable_available_at':future})
            records.append(event)
        records.append(_event(record_id='FOREIGN-KILL',kind=RecordKind.DECISION_EVENT,entity_id='FOREIGN-KILL',hypothesis_version_id='VISIBLE',payload={'hypothesis_version_id':'VISIBLE','session_id':'FOREIGN','decision_kind':'REJECT','reason_code':'KILL_UNBOUND_EVIDENCE'},created=at))
        store.append(records,transaction_id='RESEARCH-TXN-PRIOR-MEM-001')
        archive=collect_verified_priors(store,as_of='2026-10-09T00:00:00Z')
        self.assertEqual([c['hypothesis_version_id'] for c in archive['capsules']],['VISIBLE'])
        self.assertIsNone(archive['capsules'][0]['reason_code'])


def seed_history(store: ResearchStore, count: int, *, exact: dict | None = None) -> list:
    """Author historical external source events; no production guard is patched."""
    created = datetime(2026, 10, 8, tzinfo=UTC)
    transaction = "RESEARCH-TXN-EGG-HISTORY"
    records = []
    for index in range(count):
        hyp_id = f"HYP-EGG-{index:05d}"
        payload = {
            "hypothesis_version_id": hyp_id,
            "definition_sha256": f"{index + 1:064x}",
            "claim": f"Historical observable {index}",
            "population": "HISTORICAL_DISTINCT_POPULATION",
            "decision_timestamp": "H900",
            "primary_x_family": f"FIELD-DISTINCT-{index % 11}",
            "primary_y": "HISTORICAL_TARGET",
            "horizon_notional": "H900 / no execution",
            "cheapest_falsifier": "Fixed historical comparison",
        }
        if exact is not None and index == count - 1:
            payload = {
                **project_material_card(exact),
                "hypothesis_version_id": hyp_id,
                "hfic_protocol": "HFIC-V1.2",
            }
            payload["definition_sha256"] = candidate_identity(payload).full_sha256
        records.append(_event(
            record_id=hyp_id, kind=RecordKind.HYPOTHESIS_VERSION,
            entity_id=hyp_id, hypothesis_version_id=hyp_id, payload=payload,
            created=created, transaction_id=transaction,
        ))
    store.append(records, transaction_id=transaction)
    return records


class OrdinaryWorkingMemoryTests(unittest.TestCase):
    setUpClass = classmethod(flow.EpisodeFlowTests.setUpClass.__func__)
    tearDownClass = classmethod(flow.EpisodeFlowTests.tearDownClass.__func__)
    setUp = flow.EpisodeFlowTests.setUp
    cli = flow.EpisodeFlowTests.cli
    write = flow.EpisodeFlowTests.write
    preflight = flow.EpisodeFlowTests.preflight
    look = flow.EpisodeFlowTests.look
    authored_draft = flow.EpisodeFlowTests.authored_draft
    persist_and_freeze = flow.EpisodeFlowTests.persist_and_freeze

    def test_fabricated_detail_receipt_cannot_move_cutoff_without_durable_context(self):
        from solana_alpha_lab.factory.hfic_session import canonical_preflight_receipt_sha256
        from solana_alpha_lab.factory.run_passport import canonical_sha256
        store=ResearchStore(self.plane);seed_history(store,2)
        pre=self.preflight('EGG_FORGED_DETAIL')
        before=store.diagnostics().committed_inventory_sha256
        forged=copy.deepcopy(pre)
        packet=forged['forge_context_packet']
        packet['prior_memory_working_view']['research_log_cutoff']='2099-01-01T00:00:00+00:00'
        forged['forge_context_packet_sha256']=canonical_sha256(packet)
        forged['preflight_receipt_sha256']=canonical_preflight_receipt_sha256(forged)
        query=packet['prior_memory_working_view']['selection_query_sha256']
        denied=self.cli('prior','--context-view','--preflight-receipt',self.write('forged-detail.json',forged),
                        '--selection-query-sha256',query,'--source-ref','HYP-EGG-00001',ok=False)
        self.assertEqual(denied['reason_code'],'FORGE_CONTEXT_ARTIFACT_MISSING')
        self.assertFalse(denied['writes'])
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)

    def test_mandatory_overflow_refuses_before_generated_draft_or_slot_write(self):
        store=ResearchStore(self.plane);seed_history(store,65)
        evidence,scope,_query,initial=self.look('EGG_MANDATORY_OVERFLOW')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        body['candidates'][0]['prior_work_refs']=[f'HYP-EGG-{i:05d}' for i in range(65)]
        before=store.diagnostics().committed_inventory_sha256
        denied=self.cli('persist-draft','--draft',self.write('overflow.json',body),
                        '--preflight-receipt',self.write('overflow-pre.json',pre),ok=False)
        self.assertEqual(denied['reason_code'],'GENERATION_MANDATORY_CONTEXT_EXCEEDS_BOUND',denied)
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)

    def test_episode_preview_reads_prefix_only_and_replay_spends_no_second_look(self):
        from tests.test_hfic_list_aware_vertical_v1 import draft
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        query=draft('NUMERIC_IN_SCOPE',features=[{'name':'holders_delta','op':'delta','field_id':'FIELD-HOLDER-COUNT-001','start':'E300','end':'E1800'}],all=[{'feature':'holders_delta','op':'gt','value':0}])
        query=self.cli('research-scope-resolve','--spec',self.write('preview-query.json',query))['canonical_query']
        pre=self.preflight('EGG_PREFIX_PREVIEW')
        operation=_operation(query,focus=pre['owner_focus'],journal=pre['search_key_sha256'],market=pre['market_evidence_epoch_sha256'],text='Authorized synthetic prefix-only test',cap={'main':1,'adaptive':0,'preview':1},completion='LIMITED_RESULT')
        args=('discovery-preview','--store',str(self.plane),'--spec',self.write('preview-canonical.json',query),
              '--journal-scope',pre['search_key_sha256'],'--operation',self.write('preview-operation.json',operation))
        first=self.cli(*args)
        self.assertFalse(first['target_included'])
        self.assertEqual(first['population'],'OPPORTUNITY_EPISODES')
        self.assertTrue(first['values_are_features_only'])
        self.assertNotIn('target',first['feature_recipe'])
        self.assertEqual(first['loaded_point_ids'],['E1800','E300'])
        before=journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256'])
        replay=self.cli(*args)
        self.assertEqual(replay['disposition'],'REPLAY')
        self.assertFalse(replay['values_loaded'])
        self.assertEqual(journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256']),before)

    def test_65_distinct_eligible_heads_do_not_block_fresh_ordinary_freeze(self):
        store = ResearchStore(self.plane)
        sources = seed_history(store, 65)
        evidence, scope, _query, initial = self.look("EGG_CAPACITY_ENTRY")
        original = {r.record_id: r.payload_sha256 for r in sources}
        body, pre = self.authored_draft(evidence, scope, initial["owner_focus"])
        eligible = len(list(iter_search_memory_hypothesis_payloads(store)))
        self.assertGreaterEqual(eligible, 65)
        self.assertLessEqual(len(pre["forge_context_packet"]["ranked_prior_entries"]), 8)
        with self.assertRaises(PriorMemoryCapacityError):
            build_prior_memory_snapshot(
                store, store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                repo_root=ROOT,
            )
        draft_path = self.write("capacity-draft.json", body)
        generated = self.cli("persist-draft", "--draft", draft_path,
                             "--preflight-receipt", self.write("capacity-pre.json", pre),
                             "--representation-id", "BASE", "--format", "json", ok=False)
        resume = self.preflight(initial["owner_focus"])
        frozen = self.cli("freeze", "--draft", draft_path,
                          "--preflight-receipt", self.write("capacity-resume.json", resume),
                          "--format", "json", ok=False)
        proof_path = os.environ.get("EGG_CAPACITY_PROOF")
        if proof_path:
            proof = {"eligible_heads": eligible, "seeded_distinct_heads": 65,
                     "ranked_count": len(pre["forge_context_packet"]["ranked_prior_entries"]),
                     "persist_status": generated.get("status"),
                     "persist_reason": generated.get("reason_code"),
                     "freeze_status": frozen.get("status"), "freeze_reason": frozen.get("reason_code"),
                     "mode": "SYNTHETIC_PRODUCTION_PATH", "native_calls": 0}
            Path(proof_path).write_text(json.dumps(proof, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(frozen.get("session_state"), "FROZEN_AWAITING_CRITIC", {"reason_code":frozen.get("reason_code"),"session_state":frozen.get("session_state")})
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["packet_version"], "1.5")
        self.assertEqual(packet["prior_memory"]["schema_version"], "1.1")
        self.assertFalse(packet["prior_memory"]["archive_complete_in_packet"])
        self.assertLessEqual(len(packet["prior_memory"]["capsules"]), 64)
        self.assertLessEqual(len(canonical_json_bytes(packet)),65536)
        self.assertEqual(packet['prior_memory']['bytes'],len(canonical_json_bytes(packet['prior_memory'])))
        self.assertEqual(packet['generation_context']['safety_receipt']['considered_count'],eligible)
        new_hypotheses=[r for r in store.iter_committed_records() if r.hypothesis_version_id==frozen['selected_candidate_id'] and r.record_kind==RecordKind.HYPOTHESIS_VERSION]
        self.assertTrue(new_hypotheses)
        cutoff=datetime.fromisoformat(packet['prior_memory']['research_log_cutoff'])
        self.assertTrue(all(r.first_reliable_available_at>cutoff for r in new_hypotheses))
        actual = {r.record_id: r.payload_sha256 for r in store.iter_committed_records()
                  if r.record_id in original}
        self.assertEqual(actual, original)

    def test_hidden_exact_prior_refuses_before_draft_persistence(self):
        evidence, scope, _query, initial = self.look("EGG_HIDDEN_EXACT_SEED")
        body, _pre = self.authored_draft(evidence, scope, initial["owner_focus"])
        store = ResearchStore(self.plane)
        seed_history(store, 65, exact=copy.deepcopy(body["candidates"][0]))
        body, pre = self.authored_draft(evidence, scope, "EGG_HIDDEN_EXACT_CHECK")
        # Full-scope guard authority is independent of any displayed working set.
        before = store.diagnostics().committed_inventory_sha256
        denied = self.cli("persist-draft", "--draft", self.write("hidden.json", body),
                          "--preflight-receipt", self.write("hidden-pre.json", pre), ok=False)
        self.assertEqual(denied.get("reason_code"), "EXACT_PRIOR_SCOPE_MATCH", denied)
        self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_bound_detail_is_read_only_and_writer_invalidates_locator(self):
        store=ResearchStore(self.plane);seed_history(store,5)
        pre=self.preflight('EGG_DETAIL_BINDING')
        view=pre['forge_context_packet']['prior_memory_working_view']
        receipt=self.write('detail-pre.json',pre)
        args=('prior','--context-view','--preflight-receipt',receipt,'--selection-query-sha256',view['selection_query_sha256'],'--source-ref','HYP-EGG-00004')
        before=store.diagnostics().committed_inventory_sha256
        detail=self.cli(*args)
        self.assertEqual(detail['status'],'READ_ONLY')
        self.assertFalse(detail['new_look'])
        self.assertEqual(detail['view']['capsules'][0]['hypothesis_version_id'],'HYP-EGG-00004')
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        record=_event(record_id='HYP-EGG-WRITER',kind=RecordKind.HYPOTHESIS_VERSION,entity_id='HYP-EGG-WRITER',hypothesis_version_id='HYP-EGG-WRITER',payload={'hypothesis_version_id':'HYP-EGG-WRITER','claim':'A distinct append'},created=datetime.now(UTC))
        store.append([record],transaction_id=record.transaction_id)
        denied=self.cli(*args,ok=False)
        self.assertEqual(denied['reason_code'],'GENERATION_CONTEXT_STALE_STORE_BINDING')
        resumed=self.preflight('EGG_DETAIL_BINDING')
        refreshed=resumed['forge_context_packet']['prior_memory_working_view']
        self.assertEqual(refreshed['research_log_cutoff'],view['research_log_cutoff'])
        self.assertEqual(refreshed['selection_query_sha256'],view['selection_query_sha256'])
        self.assertEqual(refreshed['capsules'],view['capsules'])
        self.assertEqual(refreshed['eligible_archive_sha256'],view['eligible_archive_sha256'])
        read=self.cli('prior','--context-view','--preflight-receipt',self.write('detail-resume.json',resumed),'--selection-query-sha256',refreshed['selection_query_sha256'],'--source-ref','HYP-EGG-00004')
        self.assertEqual(read['status'],'READ_ONLY')

    def test_bound_result_detail_preserves_shared_hypothesis_sources(self):
        evidence, scope, _query, _initial = self.look('EGG_SHARED_DETAIL_LOOK')
        store = ResearchStore(self.plane)
        sources = {'HYP-EGG-SHARED-PRIMARY', 'HYP-EGG-SHARED-RUNNER'}
        records = []
        for hyp in sorted(sources):
            payload = {**scope, 'hypothesis_version_id': hyp,
                       'session_id': 'SYNTHETIC-SHARED-' + hyp,
                       'claim': 'Shared saved result, separate hypothesis source.',
                       'saved_observation_evidence': evidence}
            record = _event(record_id=hyp, kind=RecordKind.HYPOTHESIS_VERSION,
                            entity_id=hyp, hypothesis_version_id=hyp,
                            payload=payload, created=datetime.now(UTC))
            records.append(record)
        store.append(records, transaction_id=records[0].transaction_id)
        pre = self.preflight('EGG_SHARED_DETAIL_READER')
        memory = pre['forge_context_packet']['prior_memory_working_view']
        before = store.diagnostics().committed_inventory_sha256
        detail = self.cli('prior', '--context-view', '--preflight-receipt',
                          self.write('shared-result-pre.json', pre),
                          '--selection-query-sha256', memory['selection_query_sha256'],
                          '--source-ref', evidence['result_refs'][0])
        self.assertEqual(detail['status'], 'READ_ONLY')
        self.assertFalse(detail['new_look'])
        self.assertEqual({c['hypothesis_version_id'] for c in detail['view']['capsules']}, sources)
        self.assertEqual(detail['view']['mandatory_count'], 2)
        self.assertTrue(all(c['selection_reason'] == 'MANDATORY_SOURCE_REF'
                            for c in detail['view']['capsules']))
        self.assertLessEqual(detail['view']['bytes'], 65536)
        self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_episode_binding_and_metadata_coverage_use_actual_collection_owner(self):
        before=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        binding=self.cli('discovery-binding','--collection','OPPORTUNITY_EPISODES')
        coverage=self.cli('discovery-coverage','--collection','OPPORTUNITY_EPISODES')
        self.assertFalse(binding['values_loaded'])
        self.assertFalse(coverage['values_loaded'])
        self.assertEqual(coverage['joint_coverage'],'NOT_MEASURED_METADATA_ONLY')
        self.assertEqual(before,ResearchStore(self.plane).diagnostics().committed_inventory_sha256)


if __name__ == "__main__":
    unittest.main()
