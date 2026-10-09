"""Finite research-flow regressions; synthetic proof never establishes alpha."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from solana_alpha_lab.factory.hfic_session import HficSessionError, _selected_candidate_block
from tests.test_hfic_session import valid_draft

RISK_FIELDS = (
    "confounders", "pit_leakage_survivorship_risks",
    "execution_capacity_risks", "missing_or_forward_only_data",
)
# source -> transport -> identity. This finite table is also the field contract oracle.
FIELD_MAP = {
    "one_sentence_claim": ("claim", True),
    "actor_and_counterparty": ("actor_counterparty", True),
    "point_in_time_population": ("population", True),
    "primary_X": ("primary_x_family", True),
    "primary_Y": ("primary_y", True),
    "horizon_and_notional": ("horizon_notional", True),
    "strongest_alternative_world": ("alternative_world", False),
    "execution_and_capacity_risk": ("execution_capacity_risks", False),
    "forward_only_or_missing_data": ("missing_or_forward_only_data", False),
}

class CardTransportTests(unittest.TestCase):
    def project(self, **fields):
        card = {**valid_draft()["candidates"][0], **fields}
        return _selected_candidate_block(SimpleNamespace(candidate_id="HFIC-CAND-WITNESS"), card)

    def test_finite_author_aliases_preserve_material_fields_and_original_input(self):
        from solana_alpha_lab.factory.hfic_card_projection import project_material_card
        for alias,(canonical,_) in FIELD_MAP.items():
            with self.subTest(alias=alias):
                original={alias:'UNIQUE_'+alias}
                projected=project_material_card(original)
                expected=['UNIQUE_'+alias] if canonical in RISK_FIELDS else 'UNIQUE_'+alias
                self.assertEqual(projected[canonical],expected)
                self.assertEqual(original,{alias:'UNIQUE_'+alias})

    def test_material_risks_preserve_string_list_missing_and_empty(self):
        for field in RISK_FIELDS:
            for value, expected in (("A, B; C", ["A, B; C"]), (["A", "B"], ["A", "B"]), ([], [])):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.project(**{field: value})[field], expected)
            self.assertEqual(self.project()[field], ["NOT_DECLARED_IN_DRAFT"])

    def test_invalid_material_risks_fail_with_typed_field_locator(self):
        for field in RISK_FIELDS:
            for value in (False, 0, {}, [1], None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(HficSessionError) as caught:
                        self.project(**{field: value})
                    self.assertEqual(caught.exception.code, "CARD_TRANSPORT_SHAPE_INVALID")
                    self.assertEqual(caught.exception.detail["field_path"], field)

    def test_distinct_pit_and_dependency_markers_survive_together(self):
        block = self.project(PIT_and_leakage_risk="UNIQUE_PIT", survivorship_and_dependency_risk="UNIQUE_DEPENDENCY")
        self.assertEqual(block["pit_leakage_survivorship_risks"], ["UNIQUE_PIT", "UNIQUE_DEPENDENCY"])

    def test_pit_component_boundary_and_absence_survive_critic_transport(self):
        import jsonschema
        first=self.project(PIT_and_leakage_risk=['A','B'],survivorship_and_dependency_risk=['C'])
        second=self.project(PIT_and_leakage_risk=['A'],survivorship_and_dependency_risk=['B','C'])
        self.assertEqual(first['pit_leakage_survivorship_risks'],second['pit_leakage_survivorship_risks'])
        self.assertNotEqual(first['pit_component_provenance'],second['pit_component_provenance'])
        missing=self.project(PIT_and_leakage_risk=[])
        self.assertEqual(missing['pit_component_provenance'],{'PIT_and_leakage_risk':[],'survivorship_and_dependency_risk':None})
        schema=json.loads((ROOT/'catalog/schemas/hypothesis_critic_input_v1.schema.json').read_text(encoding='utf-8'))
        component_schema=schema['properties']['selected_candidate']['properties']['pit_component_provenance']
        jsonschema.validate(first['pit_component_provenance'],component_schema)
        jsonschema.validate(missing['pit_component_provenance'],component_schema)

    def test_alias_conflict_is_early_and_names_both_paths(self):
        with self.assertRaises(HficSessionError) as caught:
            self.project(one_sentence_claim="CONFLICTING CLAIM")
        self.assertEqual(caught.exception.code, "CARD_ALIAS_CONFLICT")
        self.assertEqual(caught.exception.detail["field_paths"], ["claim", "one_sentence_claim"])

    def test_typed_data_binding_is_reversible_without_coercing_invalid_item(self):
        binding = {"field_id": "FIELD-HOLDER-COUNT-001", "point": "E300"}
        block = self.project(available_data_bindings=[binding, "literal"])
        self.assertEqual(json.loads(block["available_data_bindings"][0]), binding)
        self.assertEqual(block["available_data_bindings"][1], "literal")
        with self.assertRaises(HficSessionError):
            self.project(available_data_bindings=[False])

    def test_projected_risk_shapes_satisfy_the_actual_critic_selected_schema(self):
        from jsonschema import Draft202012Validator
        schema=json.loads((ROOT/'catalog/schemas/hypothesis_critic_input_v1.schema.json').read_text(encoding='utf-8'))['properties']['selected_candidate']
        validator=Draft202012Validator(schema)
        for field in RISK_FIELDS:
            for value in ('A, B; C',['A','A','B'],[]):
                block=self.project(**{field:value})
                block['candidate_id']='HFIC-CAND-ABCDEF012345'
                block.pop('_required_capability_ids',None)
                self.assertEqual(list(validator.iter_errors(block)),[])

    def test_two_distinct_alternative_worlds_are_not_silently_collapsed(self):
        block = self.project(strongest_alternative_world="ALT_MARKER", mundane_alternative="MUNDANE_MARKER")
        self.assertEqual(block["alternative_world"], "ALT_MARKER")
        self.assertEqual(block["mundane_alternative"], "MUNDANE_MARKER")

# Synthetic input only. Producers, importers, admission, selectors and evaluators remain real.
TABLE = {
    "r1": ("A", True, .30), "r2": ("A", True, .10),
    "r3": ("AB", False, -.10), "r4": ("B", True, -.20),
    "r5": ("B", False, -.30), "r6": ("C", False, .00),
    "r7": ("AB", True, None), "r8": ("C", False, .10),
}
LITERAL_ORACLE = {
    "population": 8, "observed": 7, "missing": 1,
    "list_A": {"matched": 4, "observed": 3, "missing": 1, "mean": .10,
               "complement": 4, "complement_mean": -.10, "difference": .20},
    "numeric_in_A": {"matched": 3, "observed": 2, "missing": 1, "mean": .20, "baseline": .10},
    "mixed": {"matched": 3, "mean": .20, "pooled_baseline": -1/70, "drop_numeric": .10},
}

def create_episode_fixture(work: Path, *, future_shift: float=0.):
    """One production-produced two-cohort fixture, with PRD values fixed above."""
    from datetime import timedelta
    from unittest.mock import patch
    from tests import test_hfic_list_aware_vertical_v1 as lav
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy

    def authored_market_row(mint, now, start, signal, target):
        from tests.test_opportunity_episodes_harness_v1 import token_object
        offset = (now-start).total_seconds()
        if offset < 1100:
            price, holders = 1., 60
        elif offset < 1500:
            price, holders = 1., 68 if signal else 58
        elif offset < 10000:
            price, holders = 1., 75 if signal else 55
        else:
            if target is None:
                return None
            price, holders = 1.+target+future_shift, 80
        return token_object(mint, price=price, liquidity=12000, holders=holders)

    work.mkdir(parents=True, exist_ok=True)
    # These replacements author synthetic market bytes only, never a production filter/oracle.
    with patch.object(lav, "COHORT_A", TABLE), patch.object(lav, "COHORT_B", {"r1": ("C", True, -.40), "new": ("B", False, .05)}), patch.object(lav, "market_row", authored_market_row):
        source, packets = lav._capture_fresh(work)
    plane, mirror = work/"plane", work/"mirror"
    plane.mkdir(exist_ok=True)
    store = ResearchStore(plane)
    store.prepare_write_lookup()
    imported = lav._consume(packets[:1], source=source, mirror=mirror, plane=plane)
    if imported["_exit_code"] != 0:
        raise AssertionError(imported)
    proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
    apply_universe_policy(store, repo_root=ROOT, proposal=proposal, confirm_append_only=True)
    descriptor={"table":TABLE,"literal_oracle":LITERAL_ORACLE,"packets":[Path(p).name for p in packets]}
    (work/"fixture.json").write_text(json.dumps(descriptor,sort_keys=True),encoding="utf-8")
    return source, packets, plane, mirror

class ExplicitOutcomeTests(unittest.TestCase):
    def test_all_schema_terminals_have_explicit_source_preserving_semantics(self):
        from solana_alpha_lab.factory import hfic_suppression_semantics as semantics
        terminals=json.loads((ROOT/'catalog/schemas/hypothesis_critic_result_v1.schema.json').read_text())['properties']['critic_terminal']['enum']
        for terminal in terminals:
            body=semantics.interpret_critic_terminal(terminal)
            self.assertEqual(body['source_verdict'],terminal)
            self.assertNotEqual(body['outcome_class'],'UNMAPPED_OUTCOME')
            self.assertFalse(body['family_suppression_authority'])
        for terminal in ('KILL_FUTURE_UNKNOWN',None,False):
            self.assertEqual(semantics.interpret_critic_terminal(terminal)['outcome_class'],'UNMAPPED_OUTCOME')

    def test_review_rejection_does_not_imply_family_hard_close(self):
        from solana_alpha_lab.factory.hfic_prior_memory import classify_memory_status
        for terminal in ('KILL_STATISTICALLY_UNIDENTIFIABLE','KILL_LOW_INFORMATION_VALUE','KILL_MECHANISM','KILL_DATA_INFEASIBLE'):
            self.assertEqual(classify_memory_status(decision_kind='REJECT',reason_code=terminal,hfic_protocol='HFIC-V1.2'),'HISTORICAL')
        self.assertEqual(classify_memory_status(decision_kind='REJECT',reason_code='KILL_UNBOUND_EVIDENCE',hfic_protocol='HFIC-V1.2'),'TECHNICAL_STOP')

    def test_future_kill_is_unmapped_in_router_without_guessed_technical_negative(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import resolve_next_action
        body=resolve_next_action([{'representation_id':'BASE','execution_status':'EXECUTED','session_state':'SYNTHESIS_COMPLETE','effective_terminal':'KILL_FUTURE_UNKNOWN'}],population='OPPORTUNITY_EPISODES')
        self.assertEqual(body['reason_code'],'BASE_TERMINAL_UNMATCHED')
        self.assertEqual(body['next_action'],'OBSERVABILITY_BLOCKED')

    def test_readout_reports_verdict_authority_without_asserting_ledger_state(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import format_forge_run_owner_readout
        for terminal in ('KILL_DATA_INFEASIBLE','KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED','KILL_FUTURE_UNKNOWN'):
            text=format_forge_run_owner_readout({'stages':[{'critic_terminal':terminal}]})
            self.assertIn('family_suppression_authority=false',text)
            self.assertNotIn('family_closed=',text)
            self.assertIn('смысл:',text)
            self.assertNotIn('семейство не закрыто',text)
            self.assertIn('сам вердикт не закрывает семейство',text)

class SessionHistoryTests(unittest.TestCase):
    def test_empty_and_absent_session_ids_share_only_legacy_attribution(self):
        import tempfile
        import duckdb
        from tests.test_research_projection import event,completed_payload
        from tests.test_research_store import NOW
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.prior_work import query_hypotheses,query_data_plane_prior_work
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw))
            records=[
                event('HYP-EMPTY','HYPOTHESIS_VERSION',{'hypothesis_version_id':'HYP-EMPTY','session_id':'','definition_sha256':'1'*64,'origin_id':'ORIGIN-EMPTY'},hypothesis_version_id='HYP-EMPTY'),
                event('HYP-ABSENT','HYPOTHESIS_VERSION',{'hypothesis_version_id':'HYP-ABSENT','definition_sha256':'1'*64,'origin_id':'ORIGIN-ABSENT'},hypothesis_version_id='HYP-ABSENT'),
                event('ORIGIN-EMPTY','HYPOTHESIS_ORIGIN',{'origin_id':'ORIGIN-EMPTY','origin_kind':'EMPTY_HYP_ABSENT_ORIGIN'},hypothesis_version_id='HYP-EMPTY'),
                event('ORIGIN-ABSENT','HYPOTHESIS_ORIGIN',{'origin_id':'ORIGIN-ABSENT','session_id':'','origin_kind':'ABSENT_HYP_EMPTY_ORIGIN'},hypothesis_version_id='HYP-ABSENT'),
                event('DEC-EMPTY','DECISION_EVENT',{'decision_event_id':'DEC-EMPTY','hypothesis_version_id':'HYP-EMPTY','decision_kind':'REJECT','reason_code':'KILL_LOW_INFORMATION_VALUE'},hypothesis_version_id='HYP-EMPTY'),
            ]
            run_payload=completed_payload('RUN-EMPTY-SESSION','a'*64)
            run_payload.update({'hypothesis_version_id':'HYP-ABSENT','session_id':''})
            records.append(event('RUN-EMPTY-ROW','RUN_COMPLETED',run_payload,hypothesis_version_id='HYP-ABSENT',run_id='RUN-EMPTY-SESSION'))
            for index,row in enumerate(records):
                row=row.model_copy(update={'transaction_id':f'RESEARCH-TXN-EMPTY-{index}'})
                store.append([row],transaction_id=row.transaction_id)
            store.rebuild_projection()
            projection=Path(raw)/'projections'/'research_memory.duckdb'
            with duckdb.connect(str(projection),read_only=True) as db:
                direct=db.execute('SELECT hypothesis_version_id,session_id,origin_kind,derived_state FROM hypotheses').fetchall()
                self.assertEqual({r[0]:(r[1],r[2],r[3]) for r in direct},{'HYP-EMPTY':(None,'EMPTY_HYP_ABSENT_ORIGIN','REJECTED'),'HYP-ABSENT':(None,'ABSENT_HYP_EMPTY_ORIGIN','RETAINED')})
            rows=query_hypotheses(projection,'2026-08-25T12:30:10Z')
            self.assertEqual({r['hypothesis_version_id']:(r['session_id'],r['origin_kind'],r['derived_state']) for r in rows},{'HYP-EMPTY':(None,'EMPTY_HYP_ABSENT_ORIGIN','REJECTED'),'HYP-ABSENT':(None,'ABSENT_HYP_EMPTY_ORIGIN','RETAINED')})
            result=query_data_plane_prior_work(projection,{'query_id':'EMPTY-LEGACY-SESSION','as_of':'2026-08-25T12:30:10Z','max_results':10,'predicates':{'origin_kinds':['EMPTY_HYP_ABSENT_ORIGIN','ABSENT_HYP_EMPTY_ORIGIN']}})
            self.assertEqual(result['result_count'],2)

    def test_same_payload_stale_predecessor_refuses_before_publication(self):
        import tempfile
        from datetime import timedelta
        from tests.test_research_store import event_fixture,NOW
        from solana_alpha_lab.factory.research_store import ResearchStore,ResearchStoreError
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw))
            payload={'hypothesis_version_id':'HYP-SAME-BYTES','definition_sha256':'a'*64}
            first=event_fixture(record_id='HYP-FIRST',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-SAME-FIRST',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-SAME-BYTES'})
            store.append([first],transaction_id=first.transaction_id)
            before=store.diagnostics().committed_inventory_sha256
            for index,parent in enumerate((None,'ABSENT-PREDECESSOR')):
                stale=first.model_copy(update={'record_id':f'HYP-STALE-{index}','transaction_id':f'RESEARCH-TXN-SAME-STALE-{index}','effective_at':NOW+timedelta(seconds=index+1),'supersedes_record_id':parent})
                with self.subTest(parent=parent),self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
                    store.append([stale],transaction_id=stale.transaction_id)
                self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
            self.assertEqual(len(list(store.iter_committed_records())),1)

    def test_origin_fallback_and_search_facet_stay_in_their_session(self):
        from datetime import timedelta
        from tests.test_research_store import event_fixture,NOW
        from solana_alpha_lab.factory.prior_work import query_data_plane_prior_work,query_hypotheses
        import duckdb
        store=self._store_chain()
        for record_id,session,origin_kind in (('ORIGIN-OLD','SESS-0','OLD_ONLY_KIND'),('ORIGIN-UNBOUND',None,'LEGACY_ONLY_KIND')):
            payload={'origin_id':record_id,'origin_kind':origin_kind}
            if session is not None: payload['session_id']=session
            event=event_fixture(record_id=record_id,record_kind='HYPOTHESIS_ORIGIN',transaction_id='RESEARCH-TXN-'+record_id,payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-SAME'})
            if session is not None:
                event=event.model_copy(update={'effective_at':NOW+timedelta(seconds=5),'first_reliable_available_at':NOW+timedelta(seconds=5)})
            store.append([event],transaction_id=event.transaction_id)
        legacy=event_fixture(record_id='HYP-LEGACY',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-LEGACY',payload={'hypothesis_version_id':'HYP-LEGACY','definition_sha256':'b'*64,'origin_id':'ORIGIN-LEGACY'}).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-LEGACY'})
        origin=event_fixture(record_id='ORIGIN-LEGACY',record_kind='HYPOTHESIS_ORIGIN',transaction_id='RESEARCH-TXN-ORIGIN-LEGACY',payload={'origin_id':'ORIGIN-LEGACY','origin_kind':'LEGACY_MATCH'}).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-LEGACY'})
        for event in (legacy,origin): store.append([event],transaction_id=event.transaction_id)
        store.rebuild_projection()
        projection=Path(self.tmp.name)/'projections'/'research_memory.duckdb'
        before=query_hypotheses(projection,'2026-08-25T12:30:04Z')
        self.assertEqual({r['session_id']:r['origin_kind'] for r in before if r['hypothesis_version_id']=='HYP-SAME'},{'SESS-0':None,'SESS-1':None,'SESS-2':None})
        before_search=query_data_plane_prior_work(projection,{'query_id':'SESSION-ORIGIN-BEFORE','as_of':'2026-08-25T12:30:04Z','max_results':10,'predicates':{'origin_kinds':['OLD_ONLY_KIND']}})
        self.assertEqual(before_search['result_count'],0)
        with duckdb.connect(str(projection),read_only=True) as db:
            for view in ('hypotheses','prior_work'):
                rows=db.execute(f'SELECT hypothesis_version_id, session_id, origin_kind FROM {view}').fetchall()
                self.assertEqual({(h,s):k for h,s,k in rows},{('HYP-SAME','SESS-0'):'OLD_ONLY_KIND',('HYP-SAME','SESS-1'):None,('HYP-SAME','SESS-2'):None,('HYP-LEGACY',None):'LEGACY_MATCH'})
        result=query_data_plane_prior_work(projection,{'query_id':'SESSION-ORIGIN-001','as_of':'2026-08-25T12:30:10Z','max_results':10,'predicates':{'origin_kinds':['OLD_ONLY_KIND']}})
        self.assertEqual([(r['hypothesis_version_id'],r['session_id']) for r in result['results']],[('HYP-SAME','SESS-0')])
        after=query_hypotheses(projection,'2026-08-25T12:30:10Z')
        self.assertEqual({r['session_id']:r['origin_kind'] for r in after if r['hypothesis_version_id']=='HYP-SAME'},{'SESS-0':'OLD_ONLY_KIND','SESS-1':None,'SESS-2':None})

    def test_late_old_decision_does_not_erase_current_session_outcome(self):
        from datetime import timedelta
        from types import SimpleNamespace
        from tests.test_research_store import event_fixture,NOW
        from tests.test_hfic_forge_prior_context_capacity_repair_v1 import _fat_hfic_candidate,CONTROL_SESSION
        from solana_alpha_lab.factory.hfic_prior_memory import latest_hypothesis_decisions,compact_prior_entry
        from solana_alpha_lab.factory.hfic_reopened_prior_routing import ranked_prior_entries_for_ids
        hyp_id='HFIC-CAND-FAT0001DEADBEEF'
        records=[]
        for record_id,session,reason,second in (('DEC-NEW',CONTROL_SESSION,'KILL_LOW_INFORMATION_VALUE',1),('DEC-LATE-OLD','SESS-OLD','KILL_MECHANISM',2)):
            payload={'decision_event_id':record_id,'hypothesis_version_id':hyp_id,'session_id':session,'decision_kind':'REJECT','reason_code':reason}
            records.append(event_fixture(record_id=record_id,record_kind='DECISION_EVENT',payload=payload).model_copy(update={'hypothesis_version_id':hyp_id,'effective_at':NOW+timedelta(seconds=second)}))
        store=SimpleNamespace(iter_committed_records=lambda:iter(records))
        decision=latest_hypothesis_decisions(store)
        self.assertEqual(decision[(hyp_id,CONTROL_SESSION)]['reason_code'],'KILL_LOW_INFORMATION_VALUE')
        self.assertEqual(decision[(hyp_id,'SESS-OLD')]['reason_code'],'KILL_MECHANISM')
        payload=json.loads(_fat_hfic_candidate(1,transaction_id='RESEARCH-TXN-TEST').payload_json)
        self.assertEqual(compact_prior_entry(hyp_id,payload,decision[(hyp_id,CONTROL_SESSION)])['reason_code'],'KILL_LOW_INFORMATION_VALUE')
        entry=ranked_prior_entries_for_ids([hyp_id],[payload],store=store)[0]
        self.assertEqual(entry['reason_code'],'KILL_LOW_INFORMATION_VALUE')

    def test_two_session_compact_snapshot_keeps_new_verdict_after_late_old_decision(self):
        from datetime import timedelta
        from types import SimpleNamespace
        from tests.test_research_store import event_fixture,NOW
        from tests.test_hfic_forge_prior_context_capacity_repair_v1 import _fat_hfic_candidate,CONTROL_SESSION
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        hyp_id='HFIC-CAND-FAT0001DEADBEEF'
        body=json.loads(_fat_hfic_candidate(1,transaction_id='RESEARCH-TXN-TEST').payload_json)
        rows=[]
        for record_id,session,second in (('HYP-OLD','SESS-OLD',0),('HYP-NEW',CONTROL_SESSION,1)):
            payload={**body,'session_id':session}
            row=event_fixture(record_id=record_id,record_kind='HYPOTHESIS_VERSION',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':hyp_id,'effective_at':NOW+timedelta(seconds=second),'supersedes_record_id':'HYP-OLD' if record_id=='HYP-NEW' else None})
            rows.append(row)
        for record_id,session,reason,second in (('DEC-NEW',CONTROL_SESSION,'KILL_LOW_INFORMATION_VALUE',2),('DEC-LATE-OLD','SESS-OLD','KILL_MECHANISM',3)):
            payload={'decision_event_id':record_id,'hypothesis_version_id':hyp_id,'session_id':session,'decision_kind':'REJECT','reason_code':reason}
            rows.append(event_fixture(record_id=record_id,record_kind='DECISION_EVENT',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':hyp_id,'effective_at':NOW+timedelta(seconds=second)}))
        store=SimpleNamespace(iter_committed_records=lambda:iter(rows))
        snapshot=build_prior_memory_snapshot(store,store_inventory_digest='a'*64,repo_root=ROOT)
        self.assertEqual(snapshot['emitted_count'],1)
        self.assertEqual(snapshot['capsules'][0]['session_id'],CONTROL_SESSION)
        self.assertEqual(snapshot['capsules'][0]['reason_code'],'KILL_LOW_INFORMATION_VALUE')

    def _store_chain(self, *, fork=False, last_parent=None):
        import tempfile
        from datetime import timedelta
        from tests.test_research_store import event_fixture, NOW
        from solana_alpha_lab.factory.research_store import ResearchStore
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        store=ResearchStore(Path(self.tmp.name))
        for i in range(3):
            event=event_fixture(record_id=f'HYP-ROW-{i}',record_kind='HYPOTHESIS_VERSION',transaction_id=f'RESEARCH-TXN-HYP-{i}',payload={'hypothesis_version_id':'HYP-SAME','session_id':f'SESS-{i}','definition_sha256':'a'*64})
            event=event.model_copy(update={'run_id':None,'effective_at':NOW+timedelta(seconds=i),'supersedes_record_id':None if i==0 else f'HYP-ROW-{0 if fork else i-1}'})
            if i==2 and last_parent is not None:
                event=event.model_copy(update={'supersedes_record_id':last_parent})
            store.append([event],transaction_id=event.transaction_id)
        return store

    def test_three_session_history_is_one_explicit_append_only_chain(self):
        store=self._store_chain()
        store.rebuild_projection()
        self.assertEqual(len(list(store.iter_committed_records())),3)

    def test_backdated_successor_is_latest_compact_session_after_rebuild(self):
        from datetime import timedelta
        from tests.test_research_store import event_fixture, canonical_payload, NOW
        from solana_alpha_lab.factory.hfic_memory_policy import iter_search_memory_hypothesis_payloads
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        store=self._store_chain()
        latest=event_fixture(record_id='HYP-ROW-3',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-3',payload={'hypothesis_version_id':'HYP-SAME','session_id':'SESS-3','definition_sha256':'a'*64})
        latest=latest.model_copy(update={'run_id':None,'effective_at':NOW-timedelta(seconds=1),'supersedes_record_id':'HYP-ROW-2'})
        store.append([latest],transaction_id=latest.transaction_id)
        for session,reason in (('SESS-2','KILL_MECHANISM'),('SESS-3','KILL_LOW_INFORMATION_VALUE')):
            record_id=f'DEC-{session}'
            payload={'decision_event_id':record_id,'hypothesis_version_id':'HYP-SAME','session_id':session,'decision_kind':'REJECT','reason_code':reason}
            body,digest=canonical_payload(payload)
            row=event_fixture(record_id=record_id,record_kind='DECISION_EVENT',transaction_id=f'RESEARCH-TXN-{record_id}',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-SAME','payload_json':body,'payload_sha256':digest})
            store.append([row],transaction_id=row.transaction_id)
        for stage in ('before','after'):
            with self.subTest(stage=stage):
                if stage=='after':
                    store.rebuild_projection()
                selected=iter_search_memory_hypothesis_payloads(store)
                self.assertEqual(len(selected),1)
                self.assertEqual(selected[0]['session_id'],'SESS-3')
                snapshot=build_prior_memory_snapshot(store,store_inventory_digest=store.diagnostics().committed_inventory_sha256,repo_root=ROOT)
                self.assertEqual(snapshot['capsules'][0]['session_id'],'SESS-3')
                self.assertEqual(snapshot['capsules'][0]['reason_code'],'KILL_LOW_INFORMATION_VALUE')

    def test_compact_forge_and_critic_memory_obey_research_cutoff(self):
        import tempfile
        from datetime import timedelta
        from tests.test_research_store import event_fixture, NOW
        from tests.test_hfic_forge_prior_context_capacity_repair_v1 import _fat_hfic_candidate
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_memory_policy import iter_search_memory_hypothesis_payloads
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot, latest_hypothesis_decisions
        from solana_alpha_lab.factory.hfic_reopened_prior_routing import ranked_prior_entries_for_ids
        from solana_alpha_lab.factory.prior_work import query_hypotheses
        with tempfile.TemporaryDirectory() as temporary:
            store=ResearchStore(Path(temporary))
            body=json.loads(_fat_hfic_candidate(1,transaction_id='RESEARCH-TXN-TEMPLATE').payload_json)
            hyp_id=body['hypothesis_version_id']
            for record_id,session,parent,effective,available in (
                ('HYP-CUTOFF-A','SESS-A',None,NOW,NOW),
                ('HYP-CUTOFF-B','SESS-B','HYP-CUTOFF-A',NOW+timedelta(seconds=3),NOW+timedelta(seconds=1)),
            ):
                row=event_fixture(record_id=record_id,record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-'+record_id,payload={**body,'session_id':session}).model_copy(update={'run_id':None,'hypothesis_version_id':hyp_id,'supersedes_record_id':parent,'effective_at':effective,'first_reliable_available_at':available})
                store.append([row],transaction_id=row.transaction_id)
            for record_id,session,reason,effective,available in (
                ('DEC-CUTOFF-A','SESS-A','KILL_LOW_INFORMATION_VALUE',NOW,NOW),
                ('DEC-CUTOFF-A-FUTURE','SESS-A','KILL_MECHANISM',NOW+timedelta(seconds=3),NOW+timedelta(seconds=1)),
                ('DEC-CUTOFF-B','SESS-B','KILL_UNBOUND_EVIDENCE',NOW+timedelta(seconds=3),NOW+timedelta(seconds=1)),
            ):
                payload={'decision_event_id':record_id,'hypothesis_version_id':hyp_id,'session_id':session,'decision_kind':'REJECT','reason_code':reason}
                row=event_fixture(record_id=record_id,record_kind='DECISION_EVENT',transaction_id='RESEARCH-TXN-'+record_id,payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':hyp_id,'effective_at':effective,'first_reliable_available_at':available})
                store.append([row],transaction_id=row.transaction_id)
            store.rebuild_projection()
            projection=Path(temporary)/'projections'/'research_memory.duckdb'
            for as_of,session,reason in (
                ('2026-08-25T12:30:02Z','SESS-A','KILL_LOW_INFORMATION_VALUE'),
                ('2026-08-25T12:30:04Z','SESS-B','KILL_UNBOUND_EVIDENCE'),
            ):
                with self.subTest(as_of=as_of):
                    visible=iter_search_memory_hypothesis_payloads(store,as_of=as_of)
                    self.assertEqual(visible[0]['session_id'],session)
                    self.assertEqual(len(visible),1)
                    self.assertEqual(latest_hypothesis_decisions(store,as_of=as_of)[(hyp_id,session)]['reason_code'],reason)
                    snapshot=build_prior_memory_snapshot(store,store_inventory_digest=store.diagnostics().committed_inventory_sha256,repo_root=ROOT,as_of=as_of)
                    self.assertEqual((snapshot['capsules'][0]['session_id'],snapshot['capsules'][0]['reason_code']),(session,reason))
                    ranked=ranked_prior_entries_for_ids([hyp_id],visible,store=store,as_of=as_of)
                    self.assertEqual(ranked[0]['reason_code'],reason)
                    self.assertEqual(query_hypotheses(projection,as_of)[-1]['session_id'],session)

    def test_later_quarantine_cannot_retroactively_remove_cutoff_memory(self):
        import tempfile
        from datetime import timedelta
        from tests.test_research_store import event_fixture, NOW
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.run_passport import canonical_sha256
        from solana_alpha_lab.factory.hfic_memory_policy import (
            GENESIS_POLICY_SHA256, POLICY_ARTIFACT_KIND,
            genesis_policy_head, iter_search_memory_hypothesis_payloads,
            memory_eligibility_sha256,
        )
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        for delayed_axis in ('effective_at','first_reliable_available_at'):
          with self.subTest(delayed_axis=delayed_axis), tempfile.TemporaryDirectory() as temporary:
            store=ResearchStore(Path(temporary))
            payload={'hypothesis_version_id':'HYP-POLICY-PIT','session_id':'SESS-POLICY-PIT','hfic_protocol':'HFIC-V1','definition_sha256':'a'*64}
            hyp=event_fixture(record_id='HYP-POLICY-PIT',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-POLICY-PIT',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-POLICY-PIT'})
            store.append([hyp],transaction_id=hyp.transaction_id)
            later=NOW+timedelta(seconds=4)
            unsigned={
                'schema':'smial.hfic-search-memory-policy','schema_version':'1.0',
                'policy_id':'HFIC-MEMPOL-0001','policy_sequence':1,
                'previous_policy_sha256':GENESIS_POLICY_SHA256,
                'quarantined_session_ids':['SESS-POLICY-PIT'],
                'reason_code':'OWNER_CALIBRATION_RESET','created_at':later.isoformat(),
                'producer_git_sha':'a'*40,
                'memory_eligibility_sha256':memory_eligibility_sha256(['SESS-POLICY-PIT']),
                'authority':genesis_policy_head()['authority'],
                'non_claims':genesis_policy_head()['non_claims'],
            }
            policy={'research_artifact_id':'HFIC-MEMPOL-PIT','artifact_kind':POLICY_ARTIFACT_KIND,**unsigned,'policy_sha256':canonical_sha256(unsigned)}
            row=event_fixture(record_id='HFIC-MEMPOL-PIT',record_kind='RESEARCH_ARTIFACT',transaction_id='RESEARCH-TXN-HFIC-MEMPOL-PIT',payload=policy).model_copy(update={'run_id':None,'hypothesis_version_id':None,'effective_at':later if delayed_axis=='effective_at' else NOW+timedelta(seconds=1),'first_reliable_available_at':later,'created_at':later})
            store.append([row],transaction_id=row.transaction_id)
            cutoff=NOW+timedelta(seconds=2)
            self.assertEqual([item['session_id'] for item in iter_search_memory_hypothesis_payloads(store,as_of=cutoff)],['SESS-POLICY-PIT'])
            self.assertEqual(build_prior_memory_snapshot(store,store_inventory_digest=store.diagnostics().committed_inventory_sha256,repo_root=ROOT,as_of=cutoff)['emitted_count'],1)
            self.assertEqual(iter_search_memory_hypothesis_payloads(store,as_of=later),[])

    def test_ambiguous_hypothesis_memory_history_refuses_compaction(self):
        from types import SimpleNamespace
        from tests.test_research_store import event_fixture
        from solana_alpha_lab.factory.hfic_memory_policy import (
            HficMemoryPolicyError, iter_search_memory_hypothesis_payloads,
        )
        records=[event_fixture(record_id=f'HYP-UNRELATED-{i}',record_kind='HYPOTHESIS_VERSION',payload={'hypothesis_version_id':'HYP-SAME','session_id':f'SESS-{i}'}) for i in range(2)]
        store=SimpleNamespace(iter_committed_records=lambda:iter(records))
        with self.assertRaisesRegex(HficMemoryPolicyError,'HFIC_HYPOTHESIS_HISTORY_AMBIGUOUS'):
            iter_search_memory_hypothesis_payloads(store)

    def test_legacy_identical_unlinked_hypotheses_rebuild_and_read_without_new_fork(self):
        import tempfile
        from unittest.mock import patch
        from tests.test_research_store import event_fixture
        from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
        from solana_alpha_lab.factory.hfic_memory_policy import iter_search_memory_hypothesis_payloads
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        with tempfile.TemporaryDirectory() as temporary:
            store=ResearchStore(Path(temporary))
            payload={'hypothesis_version_id':'HYP-LEGACY-SAME','session_id':'SESS-LEGACY-SAME','hfic_protocol':'HFIC-V1','definition_sha256':'a'*64}
            for suffix in ('A','B'):
                row=event_fixture(record_id='HYP-LEGACY-'+suffix,record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-LEGACY-'+suffix,payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-LEGACY-SAME'})
                if suffix=='B':
                    # BASE permitted this immutable partition; only its old admission is simulated.
                    with patch('solana_alpha_lab.factory.research_store._assert_stable_id_lineage'):
                        store.append([row],transaction_id=row.transaction_id)
                else:
                    store.append([row],transaction_id=row.transaction_id)
            store.rebuild_projection()
            self.assertEqual([item['session_id'] for item in iter_search_memory_hypothesis_payloads(store)],['SESS-LEGACY-SAME'])
            self.assertEqual(build_prior_memory_snapshot(store,store_inventory_digest=store.diagnostics().committed_inventory_sha256,repo_root=ROOT)['emitted_count'],1)
            third=event_fixture(record_id='HYP-LEGACY-C',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-LEGACY-C',payload=payload).model_copy(update={'run_id':None,'hypothesis_version_id':'HYP-LEGACY-SAME'})
            before=store.diagnostics().committed_inventory_sha256
            with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
                store.append([third],transaction_id=third.transaction_id)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,before)

    def test_cyclic_legacy_hypothesis_history_refuses_compaction(self):
        from types import SimpleNamespace
        from tests.test_research_store import event_fixture
        from solana_alpha_lab.factory.hfic_memory_policy import (
            HficMemoryPolicyError, iter_search_memory_hypothesis_payloads,
        )
        records=[event_fixture(record_id=f'HYP-CYCLE-{i}',record_kind='HYPOTHESIS_VERSION',payload={'hypothesis_version_id':'HYP-SAME','session_id':f'SESS-{i}'}).model_copy(update={'supersedes_record_id':f'HYP-CYCLE-{1-i}'}) for i in range(2)]
        store=SimpleNamespace(iter_committed_records=lambda:iter(records))
        with self.assertRaisesRegex(HficMemoryPolicyError,'HFIC_HYPOTHESIS_HISTORY_AMBIGUOUS'):
            iter_search_memory_hypothesis_payloads(store)

    def test_branching_history_remains_a_stable_identity_conflict(self):
        from solana_alpha_lab.factory.research_store import ResearchStoreError
        with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
            self._store_chain(fork=True)

    def test_missing_and_cyclic_predecessors_cannot_legalize_history(self):
        from solana_alpha_lab.factory.research_store import ResearchStoreError
        for parent in ('ABSENT-PREDECESSOR','HYP-ROW-2'):
            with self.subTest(parent=parent):
                with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
                    self._store_chain(last_parent=parent)

    def test_dangling_first_hypothesis_parent_refuses_before_publication(self):
        import tempfile
        from tests.test_research_store import event_fixture
        from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
        with tempfile.TemporaryDirectory() as temporary:
            store=ResearchStore(Path(temporary))
            root=event_fixture(record_id='HYP-DANGLING-ROOT',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-DANGLING',payload={'hypothesis_version_id':'HYP-SAME','session_id':'SESS-ROOT','definition_sha256':'a'*64}).model_copy(update={'run_id':None,'supersedes_record_id':'HYP-ABSENT'})
            before=store.diagnostics().committed_inventory_sha256
            with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
                store.append([root],transaction_id=root.transaction_id)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,before)

    def test_foreign_first_hypothesis_parent_refuses_before_publication(self):
        import tempfile
        from tests.test_research_store import event_fixture
        from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
        with tempfile.TemporaryDirectory() as temporary:
            store=ResearchStore(Path(temporary))
            first=event_fixture(record_id='HYP-FOREIGN-A',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-FOREIGN-A',payload={'hypothesis_version_id':'HYP-A','session_id':'SESS-A','definition_sha256':'a'*64}).model_copy(update={'run_id':None})
            store.append([first],transaction_id=first.transaction_id)
            second=event_fixture(record_id='HYP-FOREIGN-B',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-FOREIGN-B',payload={'hypothesis_version_id':'HYP-B','session_id':'SESS-B','definition_sha256':'b'*64}).model_copy(update={'run_id':None,'supersedes_record_id':first.record_id})
            before=store.diagnostics().committed_inventory_sha256
            with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
                store.append([second],transaction_id=second.transaction_id)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
            store.rebuild_projection()

    def test_changed_definition_cannot_reuse_same_candidate_history(self):
        from solana_alpha_lab.factory.hfic_session import _session_hypothesis_supersedes,HficSessionError
        store=self._store_chain()
        before=store.diagnostics().committed_inventory_sha256
        with self.assertRaisesRegex(HficSessionError,'HFIC_HYPOTHESIS_HISTORY_IDENTITY_UNBOUND'):
            _session_hypothesis_supersedes(store,'HYP-SAME','b'*64)
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        self.assertEqual(_session_hypothesis_supersedes(store,'HYP-SAME','a'*64),'HYP-ROW-2')

    def test_pending_new_session_does_not_inherit_old_projection_or_prior_status(self):
        from datetime import timedelta
        from tests.test_research_store import event_fixture, canonical_payload, NOW
        from solana_alpha_lab.factory.prior_work import query_hypotheses, query_data_plane_prior_work
        store=self._store_chain()
        def decision(record_id, session, kind, second):
            payload={'decision_event_id':record_id,'hypothesis_version_id':'HYP-SAME','session_id':session,'decision_kind':kind,'reason_code':'SYNTHETIC_FIXTURE_ONLY'}
            body,digest=canonical_payload(payload)
            return event_fixture(record_id=record_id,record_kind='DECISION_EVENT',transaction_id='RESEARCH-TXN-'+record_id,payload=payload).model_copy(update={'hypothesis_version_id':'HYP-SAME','run_id':None,'payload_json':body,'payload_sha256':digest,'effective_at':NOW+timedelta(seconds=second)})
        run_payload={'run_id':'RUN-OLD','session_id':'SESS-0','scientific_terminal':'RETAINED'}
        run_body,run_digest=canonical_payload(run_payload)
        old_run=event_fixture(record_id='RUN-OLD-ROW',record_kind='RUN_COMPLETED',transaction_id='RESEARCH-TXN-RUN-OLD',payload=run_payload).model_copy(update={'run_id':'RUN-OLD','hypothesis_version_id':'HYP-SAME','payload_json':run_body,'payload_sha256':run_digest,'effective_at':NOW+timedelta(seconds=3)})
        store.append([old_run],transaction_id=old_run.transaction_id)
        projection=Path(self.tmp.name)/'projections'/'research_memory.duckdb'
        store.rebuild_projection()
        run_only=query_hypotheses(projection,'2026-08-25T12:30:10Z')
        self.assertEqual({row['session_id']:row['derived_state'] for row in run_only},{'SESS-0':'RETAINED','SESS-1':'NO_DECISION','SESS-2':'NO_DECISION'})
        old=decision('DEC-OLD','SESS-0','REJECT',4)
        store.append([old],transaction_id=old.transaction_id)
        store.rebuild_projection()
        def assert_states(expected):
            rows=query_hypotheses(projection,'2026-08-25T12:30:10Z')
            self.assertEqual({row['session_id']:row['derived_state'] for row in rows},expected)
            query={'query_id':'SESSION-BOUND-PRIOR-001','as_of':'2026-08-25T12:30:10Z','max_results':3,'predicates':{'hypothesis_version_ids':['HYP-SAME']}}
            result=query_data_plane_prior_work(projection,query)
            self.assertEqual(result['result_count'],3)
            self.assertEqual({row['session_id']:row['current_state_as_of'] for row in result['results']},expected)
            self.assertEqual({row['session_id']:row['decision_kinds'] for row in result['results']},{s:(['REJECT'] if state=='REJECTED' else ['PAUSE'] if state=='PAUSED' else []) for s,state in expected.items()})
        assert_states({'SESS-0':'REJECTED','SESS-1':'NO_DECISION','SESS-2':'NO_DECISION'})
        current=decision('DEC-NEW','SESS-2','PAUSE',4)
        store.append([current],transaction_id=current.transaction_id)
        store.rebuild_projection()
        assert_states({'SESS-0':'REJECTED','SESS-1':'NO_DECISION','SESS-2':'PAUSED'})

    def test_stale_hypothesis_predecessor_refuses_before_durable_append(self):
        from tests.test_research_store import event_fixture, NOW
        from datetime import timedelta
        from solana_alpha_lab.factory.research_store import ResearchStoreError
        store=self._store_chain()
        before=store.diagnostics().committed_inventory_sha256
        stale=event_fixture(record_id='HYP-ROW-STALE',record_kind='HYPOTHESIS_VERSION',transaction_id='RESEARCH-TXN-HYP-STALE',payload={'hypothesis_version_id':'HYP-SAME','session_id':'SESS-STALE','definition_sha256':'a'*64}).model_copy(update={'run_id':None,'effective_at':NOW+timedelta(seconds=5),'supersedes_record_id':'HYP-ROW-1'})
        with self.assertRaisesRegex(ResearchStoreError,'DUPLICATE_STABLE_ID_CONFLICT'):
            store.append([stale],transaction_id=stale.transaction_id)
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        self.assertEqual(len(list(store.iter_committed_records())),3)

    def test_other_session_decision_does_not_become_current_card_outcome(self):
        from solana_alpha_lab.factory.hfic_prior_memory import compact_prior_entry
        body={'hypothesis_version_id':'HYP-SAME','session_id':'SESS-NEW','hfic_protocol':'HFIC-V1.2','definition_sha256':'a'*64}
        decision={'session_id':'SESS-OLD','decision_kind':'REJECT','reason_code':'KILL_LOW_INFORMATION_VALUE'}
        capsule=compact_prior_entry('HYP-SAME',body,decision)
        self.assertIsNone(capsule['reason_code'])
        self.assertIsNone(capsule['decision_kind'])
        self.assertNotIn('outcome_semantics',capsule)
        same=compact_prior_entry('HYP-SAME',body,{**decision,'session_id':'SESS-NEW'})
        self.assertEqual(same['reason_code'],'KILL_LOW_INFORMATION_VALUE')
        from solana_alpha_lab.factory.hfic_prior_memory import compact_forge_prior_entry
        for card, outcome, retained in (
            (body, {k:v for k,v in decision.items() if k!='session_id'}, False),
            ({**body,'session_id':None}, decision, False),
            ({**body,'session_id':None}, {k:v for k,v in decision.items() if k!='session_id'}, True),
            (body, {**decision,'session_id':'SESS-NEW'}, True),
        ):
            for projection in (compact_prior_entry, compact_forge_prior_entry):
                with self.subTest(card=card.get('session_id'),decision=outcome.get('session_id'),projection=projection.__name__):
                    prior=projection('HYP-SAME',card,outcome)
                    self.assertEqual(prior.get('reason_code'), 'KILL_LOW_INFORMATION_VALUE' if retained else None)
                    self.assertEqual(prior.get('decision_kind'), 'REJECT' if retained else None)
                    self.assertEqual('outcome_semantics' in prior,retained)

class CapabilityBindingTests(unittest.TestCase):
    def test_changed_direct_owners_are_part_of_capability_provenance(self):
        from solana_alpha_lab.factory.hfic_evidence_identity import _CAPABILITY_PROTOCOL_FILES
        for owner in ('hfic_research_policy.py','hfic_ordinary_operation.py','hfic_card_projection.py','hfic_prior_memory.py','hfic_suppression_semantics.py','prior_work.py'):
            self.assertIn('src/solana_alpha_lab/factory/'+owner,_CAPABILITY_PROTOCOL_FILES)


def public_cli(plane: Path, *args: str, repo_root: Path=ROOT):
    """Actual unadapted public entry; no historical test output projection."""
    import os, subprocess
    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','SMIAL_DATA_ROOT':str(plane)}
    done=subprocess.run([sys.executable,'-B',str(repo_root/'scripts/hypothesis_forge.py'),'--root',str(repo_root),'--data-root',str(plane),*args],cwd=repo_root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=180)
    try:
        body=json.loads(done.stdout)
    except json.JSONDecodeError:
        raise AssertionError((done.returncode,done.stdout[-400:],done.stderr[-400:]))
    return done.returncode,body

class EpisodeFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os,tempfile
        cls.holder=tempfile.TemporaryDirectory()
        cls.template=Path(cls.holder.name)/'template'
        cache=os.environ.get('FLOW_CAPTURE_FIXTURE')
        if cache:
            import shutil
            source=Path(cache)
            descriptor=json.loads((source/'fixture.json').read_text())
            if descriptor['table']!=json.loads(json.dumps(TABLE)):
                raise AssertionError('EXACT_FIXTURE_TABLE_MISMATCH')
            shutil.copytree(source,cls.template)
        else:
            create_episode_fixture(cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.holder.cleanup()

    def setUp(self):
        import tempfile,shutil
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name)
        self.plane=self.work/'plane'
        shutil.copytree(self.template/'plane',self.plane)
        from solana_alpha_lab.factory.research_store import ResearchStore
        ResearchStore(self.plane).prepare_write_lookup()  # explicit verified preparation after a fixture copy
        self.source=self.template/'capture'/'rdp'
        self.packets=[str(self.template/'capture'/p) for p in json.loads((self.template/'fixture.json').read_text())['packets']]

    def cli(self,*args,ok=True):
        code,body=public_cli(self.plane,*args,repo_root=getattr(self,'producer_root',ROOT))
        if ok:self.assertEqual(code,0,body)
        return body

    def write(self,name,body):
        path=self.work/name;path.write_text(json.dumps(body,ensure_ascii=False),encoding='utf-8');return str(path)

    def preflight(self,focus):
        return self.cli('preflight','--discovery-contract','--collection','OPPORTUNITY_EPISODES','--owner-focus',focus,'--format','json')

    def look(self,focus,query=None,*,cap=None):
        from tests.test_hfic_list_aware_vertical_v1 import draft,NUMERIC
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label
        query=query or draft('LIST_CONTRAST',list_condition={'clauses':[{'all_of':['A']}]})
        resolved=self.cli('research-scope-resolve','--spec',self.write('query.json',query))['canonical_query']
        pre=self.preflight(focus)
        scope={'population':'OPPORTUNITY_EPISODES','decision_timestamp':'E1800','target':temporal_target_label(resolved),'estimand':'price_relative_proxy','explanatory_condition':resolved['hypothesis_kind'],'evidence_surface_mode':'ORDINARY_GROUNDED_DISCOVERY_V1'}
        operation=_operation(resolved,focus=pre['owner_focus'],journal=pre['search_key_sha256'],market=pre['market_evidence_epoch_sha256'],text='Research-flow synthetic '+focus,cap=cap or {'main':1,'adaptive':0,'preview':2},completion='LIMITED_RESULT')
        evidence=self.cli('discovery-execute','--store',str(self.plane),'--spec',self.write('canonical.json',resolved),'--candidate-scope',self.write('scope.json',scope),'--journal-scope',pre['search_key_sha256'],'--operation',self.write('operation.json',operation),'--format','json')
        return evidence,scope,resolved,pre

    def authored_draft(self,evidence,scope,focus,*,n=1):
        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_holder_claim_identity,TEMPORAL_CAPABILITY_ID
        pre=self.preflight(focus)
        exact=temporal_holder_claim_identity(evidence['result'])
        card={**scope,**exact,'display_ordinal':1,'label':'FLOW-1','claim':'List A membership separates the fixed E14400 price-relative proxy; synthetic engineering fixture only.',
              'novelty_class':'NEW_MEASUREMENT','claim_form':'PREDICTIVE','mundane_alternative':'Vendor selection and repeated template structure explain an apparent contrast.',
              'state_transition':None,'primary_x_family':exact.get('primary_x_family',exact['research_scope_statement']),'primary_y':exact.get('primary_y','PRICE_RELATIVE_PROXY E1800 -> E14400'),
              'horizon_notional':exact.get('horizon_notional','E1800 -> E14400; no executable notional'),'required_feature_ids':[],'required_capability_ids':[TEMPORAL_CAPABILITY_ID],
              'unresolved_requirements':[],'prior_work_refs':[],'material_difference_from_prior':'First bound question on this synthetic corpus.',
              'disconfirming_prediction':'No supported contrast against the eligible complement.','negative_control':'Eligible complement on the same evidence.',
              'cheapest_falsifier':'One fixed contrast; no retuning.','kill_if':['PIT failure','Insufficient independent observations'],
              'decision_unlocked':'Whether separately authorized validation would be justified; no science permission.',
              'confounders':'Confounding, dependency; retained exactly.','PIT_and_leakage_risk':'UNIQUE_PIT','survivorship_and_dependency_risk':'UNIQUE_DEPENDENCY',
              'execution_capacity_risks':[],'missing_or_forward_only_data':['Missing target remains missing'],
              'available_data_bindings':[{'field_id':'FIELD-HOLDER-COUNT-001','point':'E300'}]}
        cards=[{**copy.deepcopy(card),'display_ordinal':i,'label':f'FLOW-{i}','claim':card['claim']+f' Authored question {i}.'} for i in range(1,n+1)]
        context=pre['forge_context_packet']
        body={'packet_schema':'smial.hypothesis-forge-draft','packet_version':'1.3' if n>6 else '1.2','generator_prompt_version':'HFIC-V1.2',
              'owner_focus':pre['owner_focus'],'preflight_receipt_id':pre['receipt_id'],'preflight_receipt_sha256':pre['preflight_receipt_sha256'],
              'research_memory_as_of':pre['research_memory_as_of'],'truth_roots_used':context['truth_roots_used'],'prior_work_receipts':context['prior_work_receipts'],
              'authority':{'git_mutation':0,'experiment_execution':0,'provider_api_rpc_wss_calls':0},'candidates':cards,
              'selected_candidate_ref':cards[0]['label'],'pareto_factors':['grounding','falsifiability'],'non_claims':['NO_ALPHA','SYNTHETIC_DEPENDENT_TEMPLATE'],
              'grounded_evidence':evidence}
        if n>1:body.update(runner_up_candidate_ref=cards[-1]['label'],strongest_rejected_alternative=cards[-1]['label'])
        return body,pre

    def persist_and_freeze(self,body,pre):
        draft_path=self.write('draft.json',body);receipt_path=self.write('receipt.json',pre)
        generated=self.cli('persist-draft','--draft',draft_path,'--preflight-receipt',receipt_path,'--representation-id','BASE','--format','json')
        resume=self.preflight(pre['owner_focus'])
        frozen=self.cli('freeze','--draft',draft_path,'--preflight-receipt',self.write('resume.json',resume),'--format','json')
        return generated,frozen

    def test_primary_revision_projects_authored_aliases_and_keeps_same_look(self):
        from tests.test_hfic_cli import critic_result_from_packet_only
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        from solana_alpha_lab.factory.research_store import ResearchStore
        evidence,scope,query,initial=self.look('FLOW_REVISION')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        generated,frozen=self.persist_and_freeze(body,pre)
        budget=journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256'])
        critic=critic_result_from_packet_only(frozen['critic_input_packet'],terminal='REVISE_ONCE')
        critic['revision_receipt']={'scope':'claim_wording','attempt':1}
        waiting=self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('revise-critic.json',critic))
        self.assertEqual(waiting['session_state'],'REVISION_REQUIRED')
        changed=copy.deepcopy(body);card=changed['candidates'][0]
        card['one_sentence_claim']=card.pop('claim')+' This is descriptive association, no causal claim.'
        card['execution_and_capacity_risk']=card.pop('execution_capacity_risks')
        revised=self.cli('revise','--session-id',frozen['session_id'],'--draft',self.write('revision.json',changed))
        selected=revised['critic_input_packet']['selected_candidate']
        self.assertEqual(selected['claim'],card['one_sentence_claim'])
        self.assertEqual(selected['pit_leakage_survivorship_risks'],['UNIQUE_PIT','UNIQUE_DEPENDENCY'])
        self.assertEqual(selected['execution_capacity_risks'],[])
        self.assertEqual(revised['session_id'],frozen['session_id'])
        self.assertNotEqual(revised['selected_definition_sha256'],frozen['selected_definition_sha256'])
        self.assertEqual(journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256']),budget)
        killed=critic_result_from_packet_only(revised['critic_input_packet'],terminal='KILL_STATISTICALLY_UNIDENTIFIABLE')
        final=self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('revised-kill.json',killed))
        self.assertEqual(final['session_state'],'SYNTHESIS_COMPLETE')

    def test_public_missing_saved_context_identifies_dependency_in_ordinary_forge_run(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        evidence,scope,query,initial=self.look('FLOW_ORDINARY_CONTEXT')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        generated,frozen=self.persist_and_freeze(body,pre)
        digest=pre['forge_context_packet_sha256']
        relative='research/artifacts/forge_context/'+digest+'.json'
        (self.plane/relative).unlink()  # disposable exact-dependency loss only
        before=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        code,refused=public_cli(self.plane,'forge-run','--collection','OPPORTUNITY_EPISODES','--owner-focus',pre['owner_focus'],'--saved-draft-sha256',generated['payload_sha256'],'--no-write','--format','json')
        self.assertEqual(code,2,refused)
        self.assertEqual(refused['reason_code'],'FORGE_CONTEXT_ARTIFACT_MISSING')
        self.assertEqual(refused['status'],'BLOCKED')
        self.assertEqual(refused['next_action'],'RESTORE_EXACT_SAVED_CONTEXT_DEPENDENCY')
        self.assertEqual(refused['detail']['required_context_sha256'],digest)
        self.assertEqual(refused['detail']['relative_locator'],relative)
        self.assertIn(relative,refused['owner_readout'])
        self.assertIn(digest,refused['owner_readout'])
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,before)

    def test_persisted_prior_matrix_reaches_public_context_candidate_and_run(self):
        from datetime import UTC,datetime
        from tests.test_hfic_cli import critic_result_from_packet_only
        from tests.test_hfic_critic_prior_memory_closure_v1 import _event
        from solana_alpha_lab.factory.hfic_card_projection import project_material_card
        from solana_alpha_lab.factory.hfic_identity import candidate_identity
        from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        from solana_alpha_lab.factory.research_store import ResearchStore,RecordKind
        store=ResearchStore(self.plane)
        datasets,_=enumerate_rdp_datasets(self.plane)
        dataset=datasets[0]
        terminal='CLOSE_FLOW_BOUND_LIST_CONTRAST_FAMILY'
        decision={'schema':'smial.flow-prior-matrix.runtime-receipt','schema_version':'1.0','atom_id':'FLOW_BOUND_LIST_CONTRAST','scientific_terminal':terminal,'outcome_consumed':True,'dataset_fingerprint':dataset['dataset_fingerprint'],'score':{'terminal':terminal}}
        decision_path=self.plane/'datasets/manifests'/(dataset['dataset_manifest_id']+'.decision.json')
        decision_path.write_text(json.dumps(decision),encoding='utf-8')
        decision_bytes=decision_path.read_bytes()
        evidence,scope,query,initial=self.look('FLOW_PRIOR_MATRIX',cap={'main':2,'adaptive':0,'preview':2})
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        card=project_material_card(body['candidates'][0])
        old_evidence,old_scope=evidence,scope
        from tests.test_hfic_list_aware_vertical_v1 import draft,NUMERIC
        numeric=draft('MIXED_LIST_NUMERIC',list_condition={'clauses':[{'all_of':['A']}]},**NUMERIC)
        evidence,scope,query,_=self.look('FLOW_PRIOR_MATRIX',numeric,cap={'main':2,'adaptive':0,'preview':2})
        new_body,_=self.authored_draft(evidence,scope,initial['owner_focus'])
        current_card=project_material_card(new_body['candidates'][0])
        records=[]; expected={}
        variants=(('EXACT','KILL_STATISTICALLY_UNIDENTIFIABLE','HISTORICAL'),('RELATED','KILL_LOW_INFORMATION_VALUE','HISTORICAL'),('PARK','PARK_UNTIL_EVIDENCE','PARK'),('TECHNICAL','KILL_UNBOUND_EVIDENCE','TECHNICAL_STOP'))
        for label,reason,status in variants:
            prior=copy.deepcopy(card if label in {'EXACT','RELATED'} else current_card)
            if label=='RELATED':
                prior['primary_y']='Explicit distinct historical target E7200'
                prior['target']='Explicit distinct historical target E7200'
            elif label!='EXACT':
                prior['claim']+=' Historical '+label+' question.'
            identity=candidate_identity(prior);hyp_id='HYP-FLOW-MATRIX-'+label
            payload={**prior,'hypothesis_version_id':hyp_id,'definition_sha256':identity.full_sha256,'hfic_protocol':'HFIC-V1.2'}
            now=datetime(2026,10,8,tzinfo=UTC)
            records.append(_event(record_id='REC-'+hyp_id,kind=RecordKind.HYPOTHESIS_VERSION,entity_id=hyp_id,hypothesis_version_id=hyp_id,payload=payload,created=now))
            records.append(_event(record_id='DEC-'+hyp_id,kind=RecordKind.DECISION_EVENT,entity_id='DEC-'+hyp_id,hypothesis_version_id=hyp_id,payload={'hypothesis_version_id':hyp_id,'decision_kind':'PARK' if label=='PARK' else 'REJECT','reason_code':reason},created=now))
            expected[hyp_id]=(reason,status)
        store.append(records,transaction_id='RESEARCH-TXN-PRIOR-MEM-001')
        historical={r.record_id:r.payload_sha256 for r in records}
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        context=pre['forge_context_packet']
        rows={row['hypothesis_version_id']:row for row in context['ranked_prior_entries']}
        for hyp_id,(reason,status) in expected.items():
            self.assertEqual(rows[hyp_id]['reason_code'],reason)
            self.assertEqual(rows[hyp_id]['memory_status'],status)
            if status!='PARK':
                self.assertFalse(rows[hyp_id]['outcome_semantics']['family_suppression_authority'])
        related=rows['HYP-FLOW-MATRIX-RELATED']
        self.assertNotEqual(related['target'],body['candidates'][0]['target'])
        closed=[row for row in context['closed_family_ledger'] if row['terminal']==terminal]
        self.assertEqual(len(closed),1)
        self.assertEqual((closed[0]['suppression_class'],closed[0]['scope_kind'],closed[0]['reopen_forbidden']),('SCIENTIFIC_CLOSE_VALID','FAMILY',True))
        lookup=self.cli('prior','--candidate',json.dumps(card))
        matches={row.get('candidate_id'):row for row in lookup['matches']}
        self.assertEqual(matches['HYP-FLOW-MATRIX-EXACT']['match_kind'],'EXACT')
        self.assertIsNone(matches['HYP-FLOW-MATRIX-EXACT']['session_id'])
        self.assertEqual(matches['HYP-FLOW-MATRIX-RELATED']['match_kind'],'RELATED_PRIOR')
        budget=journal_occupancy(store,pre['search_key_sha256'])
        before=store.diagnostics().committed_inventory_sha256
        exact_body,exact_pre=self.authored_draft(old_evidence,old_scope,initial['owner_focus'])
        exact_denied=self.cli('persist-draft','--draft',self.write('exact.json',exact_body),'--preflight-receipt',self.write('exact-pre.json',exact_pre),ok=False)
        self.assertEqual(exact_denied['reason_code'],'EXACT_PRIOR_SCOPE_MATCH',exact_denied)
        self.assertEqual(exact_denied['status'],'BLOCKED')
        self.assertEqual(exact_denied['next_action'],'READ_EXACT_PRIOR_VERIFY_SESSION_OR_BLOCK')
        self.assertIn('session_id=null',exact_denied['owner_readout'])
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        blocked=copy.deepcopy(body)
        blocked['candidates'][0]['claim']+=' FLOW_BOUND_LIST_CONTRAST; renamed label cannot reopen.'
        blocked['candidates'][0]['label']='RENAMED-QUESTION';blocked['selected_candidate_ref']='RENAMED-QUESTION'
        denied=self.cli('persist-draft','--draft',self.write('closed.json',blocked),'--preflight-receipt',self.write('pre.json',pre),ok=False)
        self.assertEqual(denied['reason_code'],'CLOSED_FAMILY_REOPEN',denied)
        self.assertEqual(denied['detail']['scope_id'],closed[0]['scope_id'])
        self.assertEqual(denied['detail']['source_receipt'],closed[0]['source_receipt'])
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        generated,frozen=self.persist_and_freeze(body,pre)
        capsules={row['hypothesis_version_id']:row for row in frozen['critic_input_packet']['prior_memory']['capsules']}
        for hyp_id,(reason,status) in expected.items():
            self.assertEqual((capsules[hyp_id]['reason_code'],capsules[hyp_id]['memory_status']),(reason,status))
        critic=critic_result_from_packet_only(frozen['critic_input_packet'],terminal='KILL_UNBOUND_EVIDENCE')
        self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('technical.json',critic))
        run=self.cli('forge-run','--owner-focus',pre['owner_focus'],'--persist')
        self.assertEqual(run['next_action'],'NON_SCIENTIFIC_STOP')
        self.assertEqual(run['owner_final'],'NON_SCIENTIFIC_STOP')
        self.assertTrue(any(stage.get('critic_terminal')=='KILL_UNBOUND_EVIDENCE' for stage in run['stages']))
        self.assertIn('class=TECHNICAL_REFUSAL',run['owner_readout'])
        self.assertIn('family_suppression_authority=false',run['owner_readout'])
        before=store.diagnostics().committed_inventory_sha256
        saved=self.cli('forge-run','--owner-focus',pre['owner_focus'],'--no-write')
        self.assertEqual(saved['owner_final'],'NON_SCIENTIFIC_STOP')
        self.assertEqual(store.diagnostics().committed_inventory_sha256,before)
        self.assertEqual(journal_occupancy(store,pre['search_key_sha256']),budget)
        current={r.record_id:r.payload_sha256 for r in store.iter_committed_records() if r.record_id in historical}
        self.assertEqual(current,historical)
        self.assertEqual(decision_path.read_bytes(),decision_bytes)
        import os
        capture=os.environ.get('FLOW_CAPTURE_MATRIX_PROOF')
        if capture:
            proof={'schema':'smial.forge-flow-prior-matrix-proof','schema_version':'1.0','mode':'SYNTHETIC_MECHANICAL_NO_NATIVE_REROLL','test':'EpisodeFlowTests.test_persisted_prior_matrix_reaches_public_context_candidate_and_run','original_scope':old_scope,'distinct_scope':scope,'prior_states':{k:{'source_verdict':v[0],'memory_status':v[1]} for k,v in expected.items()},'typed_close':closed[0],'exact_refusal':exact_denied,'renamed_family_refusal':denied,'selected_candidate_id':frozen['selected_candidate_id'],'technical_source_terminal':'KILL_UNBOUND_EVIDENCE','run_next_action':run['next_action'],'run_owner_final':run['owner_final'],'current_question_prior_relations':frozen['critic_input_packet']['selected_candidate'].get('grounding',{}).get('prior_scope_relations'),'budget_before_final':budget,'budget_after_readback':journal_occupancy(store,pre['search_key_sha256']),'readback_inventory_unchanged':True,'historical_payload_hashes':historical,'history_and_typed_receipt_unchanged':True,'non_claims':['NO_ALPHA','NO_NEW_REAL_SCIENTIFIC_LOOK','NO_FAMILY_CLOSE_FROM_CRITIC','NO_DEFAULT_QUOTA_CHANGE']}
            Path(capture).write_text(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_direct_owner_mutation_changes_only_capability_not_market_or_charges(self):
        import subprocess,shutil
        from solana_alpha_lab.factory.hfic_evidence_identity import compute_capability_epoch_for_repo,compute_market_epoch_for_data_root,_CAPABILITY_PROTOCOL_FILES
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        from solana_alpha_lab.factory.research_store import ResearchStore
        evidence,scope,query,initial=self.look('FLOW_CAPABILITY')
        isolated=self.work/'capability-source'
        subprocess.run(['git','clone','--quiet','--no-hardlinks','--local',str(ROOT),str(isolated)],check=True,capture_output=True)
        for relative in _CAPABILITY_PROTOCOL_FILES:
            path=isolated/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,path)
        # Prompt section owner is in the declared capability surface.
        doc='docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md'
        shutil.copyfile(ROOT/doc,isolated/doc)
        initial_cap,_=compute_capability_epoch_for_repo(isolated)
        market,_=compute_market_epoch_for_data_root(isolated,self.plane)
        store=ResearchStore(self.plane);budget=journal_occupancy(store,initial['search_key_sha256'])
        inventory=store.diagnostics().committed_inventory_sha256
        for owner in ('hfic_research_policy.py','hfic_ordinary_operation.py','hfic_card_projection.py','hfic_prior_memory.py','hfic_suppression_semantics.py'):
            path=isolated/'src/solana_alpha_lab/factory'/owner;original=path.read_bytes()
            path.write_bytes(original+b'\n# Synthetic provenance mutation control.\n')
            changed,_=compute_capability_epoch_for_repo(isolated)
            self.assertNotEqual(changed,initial_cap,owner)
            current_market,_=compute_market_epoch_for_data_root(isolated,self.plane)
            self.assertEqual(current_market,market,owner)
            self.assertEqual(journal_occupancy(store,initial['search_key_sha256']),budget)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,inventory)
            path.write_bytes(original)

    def test_base_saved_string_draft_recovers_without_rewrite_or_new_look(self):
        import os,subprocess,hashlib
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        from solana_alpha_lab.factory.hfic_session import find_generated_draft
        from solana_alpha_lab.factory.research_store import ResearchStore
        base = os.environ.get('FLOW_BASE_SOURCE')
        if base:
            producer=Path(base)
        else:
            producer=self.work/'base-producer'
            subprocess.run(['git','clone','--quiet','--no-hardlinks','--local',str(ROOT),str(producer)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(producer),'checkout','--quiet','44eda5d72dccd569e9766a74046ce8b2ec47f417'],check=True,capture_output=True)
        self.producer_root=producer
        evidence,scope,query,initial=self.look('FLOW_HISTORICAL')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        draft=self.write('historical.json',body)
        source_bytes=Path(draft).read_bytes()
        generated=self.cli('persist-draft','--draft',draft,'--preflight-receipt',self.write('old-pre.json',pre))
        old_resume=self.preflight(pre['owner_focus'])
        old_resume_path=self.write('old-resume.json',old_resume)
        failure=subprocess.run([sys.executable,'-B',str(producer/'scripts/hypothesis_forge.py'),'--root',str(producer),'--data-root',str(self.plane),'freeze','--draft',draft,'--preflight-receipt',old_resume_path],env={**os.environ,'PYTHONUTF8':'1'},capture_output=True,text=True,encoding='utf-8',timeout=180)
        self.assertNotEqual(failure.returncode,0)
        self.assertEqual(failure.stderr.strip(),'HFIC_PROTOCOL_INVALID')
        store=ResearchStore(self.plane)
        saved=find_generated_draft(store,market_evidence_epoch_sha256=pre['market_evidence_epoch_sha256'],owner_focus=pre['owner_focus'])
        self.assertEqual(saved['payload_sha256'],generated['payload_sha256'])
        budget=journal_occupancy(store,pre['search_key_sha256'])
        self.producer_root=ROOT
        repaired=self.preflight(pre['owner_focus'])
        self.assertEqual(repaired['action'],'RESUME_EXISTING_SESSION')
        self.assertEqual(repaired['generated_draft_sha256'],saved['payload_sha256'])
        frozen=self.cli('freeze','--draft',draft,'--preflight-receipt',self.write('repair.json',repaired))
        self.assertEqual(frozen['critic_input_packet']['selected_candidate']['confounders'],[body['candidates'][0]['confounders']])
        self.assertEqual(Path(draft).read_bytes(),source_bytes)
        self.assertEqual(journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256']),budget)
        again=find_generated_draft(ResearchStore(self.plane),market_evidence_epoch_sha256=pre['market_evidence_epoch_sha256'],owner_focus=pre['owner_focus'])
        self.assertEqual(again['payload_canonical'],saved['payload_canonical'])
        self.assertEqual(again['scientific_slot_sha256'],saved['scientific_slot_sha256'])

    def test_new_admitted_cohort_changes_evidence_while_identical_import_does_not(self):
        from tests import test_hfic_list_aware_vertical_v1 as lav
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_cli import critic_result_from_packet_only
        evidence,scope,query,initial=self.look('FLOW_NEW_DATA')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        generated,frozen=self.persist_and_freeze(body,pre)
        critic=critic_result_from_packet_only(frozen['critic_input_packet'],terminal='KILL_STATISTICALLY_UNIDENTIFIABLE')
        self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('kill.json',critic))
        self.cli('forge-run','--owner-focus',pre['owner_focus'],'--persist')
        before=self.preflight(pre['owner_focus'])
        replay=lav._consume(self.packets[:1],source=self.source,mirror=self.work/'mirror',plane=self.plane)
        self.assertEqual(replay['_exit_code'],0,replay)
        identical=self.preflight(pre['owner_focus'])
        self.assertEqual(identical['market_evidence_epoch_sha256'],before['market_evidence_epoch_sha256'])
        self.assertEqual(identical['search_key_sha256'],before['search_key_sha256'])
        new=lav._consume(self.packets[1:],source=self.source,mirror=self.work/'mirror',plane=self.plane)
        self.assertEqual(new['_exit_code'],0,new)
        after=self.preflight(pre['owner_focus'])
        self.assertNotEqual(after['market_evidence_epoch_sha256'],before['market_evidence_epoch_sha256'])
        self.assertNotEqual(after['search_key_sha256'],before['search_key_sha256'])
        self.assertEqual(after['forge_context_packet']['list_dimension_context']['admitted_episodes_n'],10)
        prior=after['forge_context_packet']['ranked_prior_entries']
        chosen=[row for row in prior if row['hypothesis_version_id']==frozen['selected_candidate_id']]
        self.assertTrue(chosen)
        self.assertEqual(chosen[0]['reason_code'],'KILL_STATISTICALLY_UNIDENTIFIABLE')
        self.assertFalse(chosen[0]['outcome_semantics']['family_suppression_authority'])
        old_records={r.record_id:r.payload_sha256 for r in ResearchStore(self.plane).iter_committed_records()}
        fresh,fresh_scope,_,_=self.look('FLOW_NEW_DATA')
        self.assertNotEqual(fresh['result_sha256'],evidence['result_sha256'])
        self.assertEqual(fresh['result']['research_scope']['base_admitted_n'],10)
        fresh_body,fresh_pre=self.authored_draft(fresh,fresh_scope,pre['owner_focus'])
        fresh_generated,fresh_frozen=self.persist_and_freeze(fresh_body,fresh_pre)
        self.assertEqual(fresh_frozen['selected_candidate_id'],frozen['selected_candidate_id'])
        self.assertNotEqual(fresh_frozen['session_id'],frozen['session_id'])
        self.assertEqual(fresh_frozen['market_evidence_epoch_sha256'],after['market_evidence_epoch_sha256'])
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        occupancy=journal_occupancy(ResearchStore(self.plane),fresh_pre['search_key_sha256'])
        inventory=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        replay_frozen=self.cli('freeze','--draft',self.write('fresh-replay.json',fresh_body),'--preflight-receipt',str(self.work/'resume.json'),'--format','json')
        self.assertEqual(replay_frozen['session_id'],fresh_frozen['session_id'])
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,inventory)
        self.assertEqual(journal_occupancy(ResearchStore(self.plane),fresh_pre['search_key_sha256']),occupancy)
        fresh_critic=critic_result_from_packet_only(fresh_frozen['critic_input_packet'],terminal='KILL_LOW_INFORMATION_VALUE')
        self.cli('finalize','--session-id',fresh_frozen['session_id'],'--critic-result',self.write('fresh-kill.json',fresh_critic))
        current=self.cli('forge-run','--owner-focus',pre['owner_focus'],'--persist')
        self.assertEqual(current['stages'][0]['session_id'],fresh_frozen['session_id'])
        final_records=list(ResearchStore(self.plane).iter_committed_records())
        self.assertEqual({r.record_id:r.payload_sha256 for r in final_records if r.record_id in old_records},old_records)
        hypotheses=[json.loads(r.payload_json) for r in final_records if str(getattr(r.record_kind,'value',r.record_kind))=='HYPOTHESIS_VERSION' and r.hypothesis_version_id==frozen['selected_candidate_id']]
        self.assertEqual({row['session_id'] for row in hypotheses},{frozen['session_id'],fresh_frozen['session_id']})
        import os
        if os.environ.get('FLOW_D10_PROOF'):
            proof={'schema':'smial.forge-flow-new-data-proof.v1','synthetic_mechanical_only':True,'old_market_evidence_epoch_sha256':before['market_evidence_epoch_sha256'],'new_market_evidence_epoch_sha256':after['market_evidence_epoch_sha256'],'identical_import_changes_epoch':False,'old_session_id':frozen['session_id'],'new_session_id':fresh_frozen['session_id'],'same_semantic_candidate_id':frozen['selected_candidate_id'],'fresh_generated_draft_sha256':fresh_generated['payload_sha256'],'old_verdict':'KILL_STATISTICALLY_UNIDENTIFIABLE','new_verdict':'KILL_LOW_INFORMATION_VALUE','admitted_n':10,'historical_records_unchanged_n':len(old_records),'same_session_replay_writes':0,'same_session_replay_extra_looks':0,'ordinary_current_session_id':current['stages'][0]['session_id'],'alpha_or_scientific_acceptance':False}
            Path(os.environ['FLOW_D10_PROOF']).write_text(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_ten_cards_primary_nine_runner_ten_and_bad_runner_are_bound(self):
        from tests.test_hfic_cli import critic_result_from_packet_only
        from solana_alpha_lab.factory.hfic_identity import candidate_identity
        from solana_alpha_lab.factory.hfic_card_projection import project_material_card
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        change=self.cli('research-policy-preview','--max-generated','10')
        self.cli('research-policy-apply','--proposal',self.write('policy.json',change),'--confirm-append-only')
        evidence,scope,query,initial=self.look('FLOW_TEN')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'],n=10)
        self.assertEqual(pre['forge_context_packet']['research_policy_context']['this_search']['limits']['max_generated'],10)
        self.assertIn('candidate_authoring_contract',pre['forge_context_packet'])
        body['selected_candidate_ref']='FLOW-9'
        before=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        bad=copy.deepcopy(body);bad['candidates'][9]['confounders']={}
        refused=self.cli('persist-draft','--draft',self.write('bad-runner.json',bad),'--preflight-receipt',self.write('receipt.json',pre),ok=False)
        self.assertEqual(refused['detail']['field_path'],'candidates[9].confounders')
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,before)
        generated,frozen=self.persist_and_freeze(body,pre)
        expected=[candidate_identity(project_material_card(card)) for card in body['candidates']]
        self.assertEqual(frozen['candidate_ids'],[item.candidate_id for item in expected])
        self.assertEqual(frozen['selected_candidate_id'],expected[8].candidate_id)
        runner=frozen['runner_up_critic_input_packet']
        self.assertEqual(runner['selected_candidate']['candidate_id'],expected[9].candidate_id)
        self.assertEqual(runner['selected_candidate']['confounders'],[body['candidates'][9]['confounders']])
        first=critic_result_from_packet_only(frozen['critic_input_packet'],terminal='KILL_STATISTICALLY_UNIDENTIFIABLE')
        waiting=self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('primary-kill.json',first))
        self.assertEqual(waiting['session_state'],'RUNNER_UP_AWAITING_CRITIC')
        second=critic_result_from_packet_only(runner,terminal='REVISE_ONCE');second['revision_receipt']={'scope':'claim wording','attempt':1}
        final=self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('runner-revise.json',second))
        self.assertEqual(final['session_state'],'SYNTHESIS_COMPLETE')
        self.assertEqual(final['final_session_terminal'],'RUNNER_UP_REVISION_REQUIRED')
        memory=build_prior_memory_snapshot(ResearchStore(self.plane),store_inventory_digest=ResearchStore(self.plane).diagnostics().committed_inventory_sha256)
        rows={entry['hypothesis_version_id']:entry for entry in memory['capsules']}
        for identity in expected[:8]:
            self.assertEqual(rows[identity.candidate_id]['memory_status'],'NOT_SELECTED_IN_SESSION')
        self.assertNotEqual(rows[expected[8].candidate_id]['memory_status'],'HARD_CLOSE')

    def test_scripted_positive_boundary_runs_real_classify_final_runner_replay(self):
        from datetime import UTC,datetime
        from tests.test_hfic_cli import critic_result_from_packet_only
        from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment
        from solana_alpha_lab.factory.document_runner import DocumentRunner,RunContext
        from solana_alpha_lab.factory.operational_store import OperationalStore
        from solana_alpha_lab.factory.lane_classifier import classify_lane
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        evidence,scope,query,initial=self.look('FLOW_POSITIVE')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        generated,frozen=self.persist_and_freeze(body,pre)
        critic=critic_result_from_packet_only(frozen['critic_input_packet'],terminal='PASS_TO_CLASSIFICATION')
        critic['non_claims'].append('SCRIPTED_CRITIC_MECHANICAL')
        pending=self.cli('finalize','--session-id',frozen['session_id'],'--critic-result',self.write('critic.json',critic))
        self.assertEqual(pending['session_state'],'AWAITING_CLASSIFICATION')
        recipe=evidence['result']['experiment_recipe']
        experiment=_bind_experiment(recipe,self.plane)
        experiment.update(as_of='2026-10-16T00:00:00Z',availability_cutoff='2026-10-16T00:00:00Z',hypothesis_version='HYP-'+frozen['selected_candidate_id'])
        experiment.pop('required_feature_ids',None)
        experiment['question']='SCRIPTED_CRITIC_MECHANICAL: exact admitted episode list-A fixed-time proxy'
        classify={'experiment_spec':experiment,'hypothesis_definition_sha256':frozen['selected_definition_sha256'],'classifier_evaluated_at':'2026-10-16T00:00:00Z'}
        final=self.cli('classify','--session-id',frozen['session_id'],'--experiment-spec',self.write('classify.json',classify))
        self.assertEqual(final['session_state'],'SYNTHESIS_COMPLETE')
        at=datetime(2026,10,16,tzinfo=UTC)
        decision=classify_lane(classify,root=ROOT,data_root=self.plane,as_of=at)
        self.assertEqual(decision.terminal,'FAST_LANE_READY',decision.reason_codes)
        budget=journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256'])
        ops=OperationalStore(self.plane/'ops'/'operational_state.sqlite')
        self.addCleanup(ops.close)
        runner=DocumentRunner(root=ROOT,store=ops)
        context=RunContext(data_root=self.plane,hypothesis_definition_sha256=frozen['selected_definition_sha256'],lane_decision=decision,classifier_evaluated_at=at)
        result=runner.start_document(experiment,spec_sha256=experiment_spec_sha256(experiment),run_context=context)
        self.assertEqual(result['status'],'COMPLETE',result)
        run_id=result['run_id_or_null']
        artifact=self.plane/'research'/'artifacts'/'results'/('RESULT-ARTIFACT-'+run_id.removeprefix('RUN-')+'.json')
        actual=json.loads(artifact.read_text(encoding='utf-8'))['capability_result']['summary']['research_scope']
        self.assertEqual((actual['matched']['n'],actual['matched']['target_observed_n'],actual['matched']['target_missing_n']),(4,3,1))
        self.assertAlmostEqual(actual['matched']['mean_target'],.1,delta=1e-9)
        self.assertAlmostEqual(actual['contrast']['observed_target_difference'],.2,delta=1e-9)
        inventory=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        replay_decision=classify_lane(classify,root=ROOT,data_root=self.plane,as_of=at)
        self.assertEqual(replay_decision.terminal,'REPLAY_AVAILABLE',replay_decision.reason_codes)
        replay_context=RunContext(data_root=self.plane,hypothesis_definition_sha256=frozen['selected_definition_sha256'],lane_decision=replay_decision,classifier_evaluated_at=at)
        replay=runner.start_document(experiment,spec_sha256=experiment_spec_sha256(experiment),run_context=replay_context)
        self.assertEqual(replay['run_id_or_null'],run_id)
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,inventory)
        self.assertEqual(journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256']),budget)

    def test_os_reply_loss_then_moved_root_resume_uses_original_draft_and_charge(self):
        import subprocess,os,shutil,hashlib
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        from solana_alpha_lab.factory.hfic_session import find_generated_draft
        from solana_alpha_lab.factory.research_store import ResearchStore
        evidence,scope,query,initial=self.look('FLOW_OS_RECOVERY')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        draft_path=self.write('crash-draft.json',body);receipt=self.write('crash-receipt.json',pre)
        source_bytes=Path(draft_path).read_bytes()
        budget=journal_occupancy(ResearchStore(self.plane),pre['search_key_sha256'])
        script=self.work/'crash.py'
        script.write_text("import os,sys,importlib.util,io\nfrom contextlib import redirect_stdout\nfrom pathlib import Path\nsys.path[:0]=[sys.argv[1],str(Path(sys.argv[1])/'src')]\nspec=importlib.util.spec_from_file_location('cli',Path(sys.argv[1])/'scripts/hypothesis_forge.py')\nm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nwith redirect_stdout(io.StringIO()):\n    code=m.main(sys.argv[2:])\nos._exit(73 if code==0 else 74)\n",encoding='utf-8')
        done=subprocess.run([sys.executable,'-B',str(script),str(ROOT),'--root',str(ROOT),'--data-root',str(self.plane),'persist-draft','--draft',draft_path,'--preflight-receipt',receipt],env={**os.environ,'PYTHONUTF8':'1'},capture_output=True,timeout=180)
        self.assertEqual(done.returncode,73,done.stderr.decode('utf-8')[-800:])
        saved=find_generated_draft(ResearchStore(self.plane),owner_focus=pre['owner_focus'],market_evidence_epoch_sha256=pre['market_evidence_epoch_sha256'])
        self.assertIsNotNone(saved)
        moved=self.work/'moved-plane';self.plane.rename(moved);self.plane=moved
        ResearchStore(moved).prepare_write_lookup()
        resume=self.preflight(pre['owner_focus'])
        self.assertEqual(resume['generated_draft_sha256'],saved['payload_sha256'])
        read=self.cli('forge-run','--collection','OPPORTUNITY_EPISODES','--owner-focus',pre['owner_focus'],'--saved-draft-sha256',saved['payload_sha256'],'--no-write')
        frozen=self.cli('freeze','--draft',draft_path,'--preflight-receipt',self.write('cold-receipt.json',resume))
        self.assertEqual(Path(draft_path).read_bytes(),source_bytes)
        self.assertEqual(journal_occupancy(ResearchStore(moved),pre['search_key_sha256']),budget)
        self.assertEqual(frozen['critic_input_packet']['grounded_evidence']['result_sha256'],evidence['result_sha256'])

    def normalized_parent(self, focus="FLOW_PREFIX"):
        from tests.test_hfic_cli import bind_draft
        evidence, scope, query, initial = self.look(focus)
        pre = self.preflight(initial['owner_focus'])
        template = json.loads((ROOT/'tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json').read_text())
        template['candidates'] = []
        for key in ('runner_up_candidate_ref','strongest_rejected_alternative','selected_candidate_ref'):
            template.pop(key,None)
        body = bind_draft({**template,'owner_focus':pre['owner_focus']},pre)
        body['grounded_evidence'] = evidence
        generated, frozen = self.persist_and_freeze(body,pre)
        run = self.cli('forge-run','--owner-focus',pre['owner_focus'],'--no-write','--format','json')
        self.assertIn(run['next_action'],{'START_NORMALIZED_TRAJECTORY_EPISODES_V1','RESUME_NORMALIZED_TRAJECTORY_EPISODES_V1'})
        return evidence, query, pre, frozen

    def test_public_prefix_is_invariant_to_produced_future_poison_but_authorized_numeric_changes(self):
        first,query,pre,parent=self.normalized_parent('FLOW_POISON')
        view=self.cli('episode-normalized-view','--spec',self.write('view.json',query),'--parent-session-id',parent['session_id'],'--operation-sha256',first['operation_sha256'])
        original_view=view['representation_payload']
        old_mean=first['result']['research_scope']['matched']['mean_target']
        poison=self.work/'future-poison'
        create_episode_fixture(poison,future_shift=.55)
        self.plane=poison/'plane'
        changed,new_query,new_pre,new_parent=self.normalized_parent('FLOW_POISON')
        poisoned_view=self.cli('episode-normalized-view','--spec',self.write('view-poison.json',new_query),'--parent-session-id',new_parent['session_id'],'--operation-sha256',changed['operation_sha256'])['representation_payload']
        self.assertEqual(poisoned_view['panels'],original_view['panels'])
        self.assertEqual(poisoned_view['scope_counts'],original_view['scope_counts'])
        self.assertAlmostEqual(changed['result']['research_scope']['matched']['mean_target'],old_mean+.55,delta=1e-9)

    def test_real_normalized_prefix_reader_does_not_access_future_values(self):
        import importlib.util,io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from solana_alpha_lab.factory import hfic_grounded_discovery as gd
        evidence, query, pre, frozen = self.normalized_parent()
        path = self.write('prefix-query.json',query)
        args = ['--root',str(ROOT),'--data-root',str(self.plane),'episode-normalized-view','--spec',path,
                '--parent-session-id',frozen['session_id'],'--operation-sha256',evidence['operation_sha256'],'--format','json']
        spec = importlib.util.spec_from_file_location('flow_public_cli',ROOT/'scripts/hypothesis_forge.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        real = gd.load_parquet_rows; points=[]
        def observe(path,**kwargs):
            rows=real(path,**kwargs)
            points.extend(row['point_id'] for row in rows if 'point_id' in row)
            return rows
        output=io.StringIO()
        with patch.object(gd,'load_parquet_rows',observe),redirect_stdout(output):
            code=module.main(args)
        view=json.loads(output.getvalue());self.assertEqual(code,0,view)
        self.assertTrue(points)
        self.assertNotIn('E14400',set(points))
        self.assertTrue(set(points)<= {'E300','E900','E1800'})
        self.assertFalse(view['target_values_loaded'])
        again=self.cli(*args[4:])
        self.assertEqual(again['preview_accounting']['disposition'],'REPEAT')
        self.assertFalse(again['writes'])
        self.assertEqual(again['representation_payload'],view['representation_payload'])

    def test_public_invalid_risks_refuse_before_any_durable_acceptance(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        evidence,scope,query,initial=self.look('FLOW_INVALID')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        original=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        for field in RISK_FIELDS:
            bad=copy.deepcopy(body);bad['candidates'][0][field]=False
            result=self.cli('persist-draft','--draft',self.write('bad.json',bad),'--preflight-receipt',self.write('receipt.json',pre),'--format','json',ok=False)
            self.assertEqual(result['reason_code'],'CARD_TRANSPORT_SHAPE_INVALID')
            self.assertEqual(result['detail']['field_path'],f'candidates[0].{field}')
            self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,original)

    def test_string_draft_persist_is_unfrozen_and_repeat_is_zero_write(self):
        from solana_alpha_lab.factory.research_store import ResearchStore,RecordKind
        evidence,scope,query,initial=self.look('FLOW_PERSIST')
        body,pre=self.authored_draft(evidence,scope,initial['owner_focus'])
        args=('persist-draft','--draft',self.write('draft.json',body),'--preflight-receipt',self.write('receipt.json',pre),'--format','json')
        generated=self.cli(*args)
        records=list(ResearchStore(self.plane).iter_committed_records())
        self.assertFalse(any(row.record_kind==RecordKind.RESEARCH_CYCLE for row in records))
        self.assertEqual(json.loads(generated['payload_canonical'])['candidates'][0]['confounders'],body['candidates'][0]['confounders'])
        before=ResearchStore(self.plane).diagnostics().committed_inventory_sha256
        again=self.cli(*args)
        self.assertEqual(again['payload_sha256'],generated['payload_sha256'])
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256,before)
        resume=self.preflight(pre['owner_focus'])
        frozen=self.cli('freeze','--draft',str(self.work/'draft.json'),'--preflight-receipt',self.write('resume.json',resume),'--format','json')
        self.assertEqual(frozen['critic_input_packet']['selected_candidate']['confounders'],[body['candidates'][0]['confounders']])

    def test_literal_list_numeric_and_mixed_use_real_evaluator(self):
        from tests.test_hfic_list_aware_vertical_v1 import draft,NUMERIC
        a={'clauses':[{'all_of':['A']}]}
        queries=(draft('LIST_CONTRAST',list_condition=a),draft('NUMERIC_IN_SCOPE',research_scope={'universe_selector':a},**NUMERIC),draft('MIXED_LIST_NUMERIC',list_condition=a,**NUMERIC))
        outputs=[]
        for i,query in enumerate(queries):
            evidence,scope,resolved,pre=self.look(f'FLOW_NUMBERS_{i}',query)
            result=evidence['result'];outputs.append(result)
            self.assertEqual(result['research_scope']['base_admitted_n'],8)
            self.assertTrue(result['missing_is_not_zero'])
        scope=outputs[0]['research_scope']
        self.assertEqual((scope['matched']['n'],scope['matched']['target_observed_n'],scope['matched']['target_missing_n']),(4,3,1))
        self.assertAlmostEqual(scope['matched']['mean_target'],.1,delta=1e-9)
        self.assertAlmostEqual(scope['contrast']['observed_target_difference'],.2,delta=1e-9)
        self.assertEqual(outputs[1]['matched_n'],3)
        self.assertAlmostEqual(outputs[1]['mean_target'],.2,delta=1e-9)
        self.assertAlmostEqual(outputs[1]['baseline']['mean_target'],.1,delta=1e-9)
        self.assertAlmostEqual(outputs[2]['mean_target'],.2,delta=1e-9)
        self.assertAlmostEqual(outputs[2]['baseline']['mean_target'],-1/70,delta=1e-9)

class VerifiedReadScopeTests(unittest.TestCase):
    def test_one_verified_enumeration_is_reused_by_operation_and_budget_readers(self):
        import tempfile
        from unittest.mock import patch
        from tests.test_hfic_research_policy_closure_v1 import _operation,JOURNAL
        from solana_alpha_lab.factory import hfic_ordinary_operation as oo
        from solana_alpha_lab.factory.research_store import ResearchStore,reuse_lifecycle_reads_within_packet
        with tempfile.TemporaryDirectory() as temp:
            store=ResearchStore(Path(temp));op=_operation(store)
            partitions=store.diagnostics().partition_count
            real=ResearchStore._verify_partition;calls=[]
            def verified(owner,manifest):
                calls.append(manifest.partition_manifest_id)
                return real(owner,manifest)
            @reuse_lifecycle_reads_within_packet
            def read():
                return oo.get_operation(store,op['operation_sha256']),oo.journal_occupancy(store,JOURNAL),oo.owner_allowance(store,op,'main')
            with patch.object(ResearchStore,'_verify_partition',verified):
                first=read()
            self.assertEqual(len(calls),partitions)
            self.assertEqual(first[0]['operation_sha256'],op['operation_sha256'])

    def test_writer_refreshes_then_discards_the_request_snapshot(self):
        import tempfile
        from tests.test_hfic_research_policy_closure_v1 import _operation
        from solana_alpha_lab.factory import hfic_ordinary_operation as oo
        from solana_alpha_lab.factory.research_store import ResearchStore,reuse_lifecycle_reads_within_packet
        with tempfile.TemporaryDirectory() as temp:
            store=ResearchStore(Path(temp));initial=_operation(store)
            @reuse_lifecycle_reads_within_packet
            def request():
                self.assertEqual(len(oo.list_operations(store)),1)
                second=_operation(store,journal='d8'*32,text='A genuine authorized independent synthetic request')
                self.assertEqual(len(oo.list_operations(store)),2)
                self.assertEqual(oo.get_operation(store,second['operation_sha256'])['operation_sha256'],second['operation_sha256'])
            request()


    def test_suspended_iterator_cannot_republish_a_snapshot_after_writer_boundary(self):
        import tempfile
        from tests.test_hfic_research_policy_closure_v1 import _operation
        from solana_alpha_lab.factory import hfic_ordinary_operation as oo
        from solana_alpha_lab.factory.research_store import ResearchStore,reuse_lifecycle_reads_within_packet
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw));_operation(store)
            @reuse_lifecycle_reads_within_packet
            def interleave():
                pending=store.iter_committed_records();next(pending)
                _operation(store,journal='d8'*32,text='second genuinely independent synthetic operation')
                list(pending)
                self.assertEqual(len(oo.list_operations(store)),2)
            interleave()

class ReservedLandingTests(unittest.TestCase):
    def test_reserved_intent_and_result_publish_after_brief_other_process_lease(self):
        import os,subprocess,tempfile
        from datetime import datetime,UTC
        from tests.test_hfic_research_policy_closure_v1 import _operation,GIT
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory import hfic_ordinary_operation as oo
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            _append_temporal_intent,_append_discovery_look,list_discovery_looks,
        )
        with tempfile.TemporaryDirectory() as raw:
            plane=Path(raw);store=ResearchStore(plane);journal='19'*32;digest='29'*32
            op=_operation(store,journal=journal,owner_cap={'main':2,'adaptive':0,'preview':0})
            oo._reserve(store,op,spec_sha256=digest)
            self.assertEqual(oo.journal_occupancy(store,journal)['main']['pending'],1)
            code="""import sys,time
from pathlib import Path
from solana_alpha_lab.factory.research_store import ResearchStore
with ResearchStore(Path(sys.argv[1])).writer_lease():
 print('LOCKED',flush=True);time.sleep(.35)
"""
            kwargs={'record_id':'HFIC-ART-DISCOVERY-'+('A'*32),'journal_scope':journal,
                    'spec':{},'spec_sha256':digest,'binding_sha':'39'*32,'data_refs':[],
                    'digest':'49'*32,'identity':'59'*32,
                    'summary':{'query_id':'OS_RESERVED_LANDING','value':.2},
                    'look':{'look_class':'MAIN','new_look':True},'git_sha':GIT,
                    'clock':datetime(2026,10,8,tzinfo=UTC),
                    'operation_sha256':op['operation_sha256']}
            for phase in ('intent','result'):
                with self.subTest(phase=phase):
                    worker=subprocess.Popen([sys.executable,'-B','-c',code,str(plane)],
                        cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUTF8':'1'},
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
                    try:
                        self.assertEqual(worker.stdout.readline().strip(),'LOCKED')
                        if phase=='intent':
                            _append_temporal_intent(store,journal_scope=journal,spec_sha256=digest,
                                binding_sha='39'*32,search_tier='SIMPLE_SCREEN',git_sha=GIT)
                        else:
                            _append_discovery_look(store,**kwargs)
                    finally:
                        worker.wait(timeout=10);worker.stdout.close();worker.stderr.close()
            after=store.diagnostics().committed_inventory_sha256
            _append_discovery_look(store,**kwargs)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,after)
            looks=list_discovery_looks(store,journal)
            self.assertEqual(len(looks),1);self.assertEqual(looks[0]['result_sha256'],'49'*32)
            occupancy=oo.journal_occupancy(store,journal)['main']
            self.assertEqual((occupancy['completed'],occupancy['pending']),(1,0))

    def test_integrity_failure_is_not_retried_or_swallowed(self):
        from unittest.mock import Mock
        from solana_alpha_lab.factory.research_store import ResearchStoreError
        from solana_alpha_lab.factory.hfic_grounded_discovery import _append_reserved_discovery_event
        store=SimpleNamespace(append=Mock(side_effect=ResearchStoreError('PARTITION_HASH_MISMATCH')))
        with self.assertRaises(ResearchStoreError):
            _append_reserved_discovery_event(store,SimpleNamespace(transaction_id='FIXED_TXN'))
        self.assertEqual(store.append.call_count,1)


class ContextLocatorTests(unittest.TestCase):
    def test_missing_saved_context_names_exact_relative_dependency_without_writes(self):
        import tempfile
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_session import _verify_forge_context_artifact
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw))
            before=store.diagnostics().committed_inventory_sha256
            digest='93'*32
            with self.assertRaises(HficSessionError) as caught:
                _verify_forge_context_artifact(store,digest)
            self.assertEqual(caught.exception.code,'FORGE_CONTEXT_ARTIFACT_MISSING')
            self.assertEqual(caught.exception.detail['required_context_sha256'],digest)
            self.assertEqual(caught.exception.detail['relative_locator'],'research/artifacts/forge_context/'+digest+'.json')
            self.assertEqual(caught.exception.detail['next_action'],'RESTORE_EXACT_SAVED_CONTEXT_DEPENDENCY')
            self.assertEqual(store.diagnostics().committed_inventory_sha256,before)


if __name__ == "__main__":
    unittest.main()
