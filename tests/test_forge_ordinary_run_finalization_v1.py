"""Ordinary episode run closes from its own saved stages, never new science."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from solana_alpha_lab.factory.hfic_ordinary_operation import _run_completion
from solana_alpha_lab.factory.hfic_representation_ladder import resolve_next_action

REP = "NORMALIZED_TRAJECTORY_EPISODES_V1"
MARKET = "a" * 64
BASE_SLOT, CHILD_SLOT = "b" * 64, "c" * 64
BASE, CHILD = "HFIC-SESS-BASE", "HFIC-SESS-CHILD"
JOURNAL = "d" * 64
OPENED = datetime(2026, 10, 26, tzinfo=UTC)


def completion_case():
    operation = {"owner_focus": "OPPORTUNITY_EPISODES:AUTO",
                 "market_evidence_epoch_sha256": MARKET,
                 "scientific_slot_sha256": CHILD_SLOT, "journal_scope": JOURNAL,
                 "representation": {"representation_id": REP,
                    "representation_semantic_version": "1.0", "parent_session_id": BASE,
                    "representation_payload_sha256": "e" * 64, "scope_applied_sha256": "f" * 64}}
    body = {"owner_focus": operation["owner_focus"], "market_evidence_epoch_sha256": MARKET,
            "scientific_slot_sha256": BASE_SLOT, "owner_class": "OWNER_FINAL",
            "owner_final": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "stages": [
                {"representation_id": "BASE", "session_id": BASE, "scientific_slot_sha256": BASE_SLOT},
                {"representation_id": REP, "representation_semantic_version": "1.0",
                 "session_id": CHILD, "session_state": "SYNTHESIS_COMPLETE", "scientific_slot_sha256": CHILD_SLOT,
                 "representation_payload_sha256": "e" * 64}]}
    receipt = {"body": body, "record_id": "SAVED_RUN", "recorded_at": OPENED + timedelta(seconds=1)}
    return operation, receipt, {BASE: {"base-journal"}, CHILD: {JOURNAL}}


class CompletionBindingTests(unittest.TestCase):
    def test_representation_operation_uses_own_stage_in_parent_run(self):
        operation, receipt, keys = completion_case()
        proof, reason = _run_completion(operation, opened_at=OPENED, receipts=[receipt], session_keys=keys)
        self.assertEqual(reason, "")
        self.assertEqual(proof["session_id"], CHILD)
        # OWNER_CANDIDATE can point at the child slot; both operations still
        # bind their own stage, not the aggregate's currently active slot.
        receipt["body"]["scientific_slot_sha256"] = CHILD_SLOT
        receipt["body"]["owner_final"] = "OWNER_CANDIDATE"
        self.assertIsNotNone(_run_completion(operation, opened_at=OPENED, receipts=[receipt], session_keys=keys)[0])
        base_operation = {**operation, "scientific_slot_sha256": BASE_SLOT, "journal_scope": "base-journal"}
        base_operation.pop("representation")
        self.assertIsNotNone(_run_completion(base_operation, opened_at=OPENED, receipts=[receipt], session_keys=keys)[0])

    def test_foreign_stage_or_run_cannot_complete_representation(self):
        operation, receipt, keys = completion_case()
        mutations = {
            "parent": lambda b: b["stages"][0].update(session_id="OTHER_BASE"),
            "market": lambda b: b.update(market_evidence_epoch_sha256="0" * 64),
            "root-slot": lambda b: b.update(scientific_slot_sha256="0" * 64),
            "stage-slot": lambda b: b["stages"][1].update(scientific_slot_sha256=BASE_SLOT),
            "payload": lambda b: b["stages"][1].update(representation_payload_sha256="0" * 64),
            "version": lambda b: b["stages"][1].update(representation_semantic_version="2.0"),
            "pending-child": lambda b: b["stages"][1].update(session_state="AWAITING_CLASSIFICATION"),
            "not-final": lambda b: b.update(owner_class="FORGE_RUN_IN_PROGRESS", owner_final=None),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                changed = copy.deepcopy(receipt); mutate(changed["body"])
                self.assertIsNone(_run_completion(operation, opened_at=OPENED, receipts=[changed], session_keys=keys)[0])
        self.assertIsNone(_run_completion(operation, opened_at=OPENED, receipts=[receipt], session_keys={CHILD: {"foreign"}})[0])
        receipt["recorded_at"] = OPENED - timedelta(seconds=1)
        self.assertIsNone(_run_completion(operation, opened_at=OPENED, receipts=[receipt], session_keys=keys)[0])

    def test_saved_base_draft_does_not_resume_an_unstarted_child(self):
        result = resolve_next_action([{"representation_id": "BASE", "execution_status": "REUSED_VALID",
            "session_state": "SYNTHESIS_COMPLETE", "effective_terminal": "NO_WORTHY_HYPOTHESIS",
            "draft_sha256": "9" * 64}], population="OPPORTUNITY_EPISODES", saved_draft_sha256="9" * 64)
        self.assertEqual(result["next_action"], "START_NORMALIZED_TRAJECTORY_EPISODES_V1")


class ChildReviewTerminalTests(unittest.TestCase):
    def test_review_rejection_stops_without_scientific_exhaustion(self):
        stages = [{"representation_id": "BASE", "session_state": "SYNTHESIS_COMPLETE",
                   "execution_status": "EXECUTED", "effective_terminal": "NO_WORTHY_HYPOTHESIS",
                   "input_scope": "ORDINARY_BASE", "stage_ref_sha256": "5" * 64},
                  {"representation_id": REP, "session_state": "SYNTHESIS_COMPLETE",
                   "execution_status": "EXECUTED", "effective_terminal": "KILL_STATISTICALLY_UNIDENTIFIABLE",
                   "stage_ref_sha256": "6" * 64}]
        result = resolve_next_action(stages, population="OPPORTUNITY_EPISODES")
        self.assertEqual(result["owner_final"], "NON_SCIENTIFIC_STOP")
        self.assertEqual(result["reason_code"], "KILL_STATISTICALLY_UNIDENTIFIABLE")
        for change in ({"stage_ref_sha256": None}, {"effective_terminal": "ALIEN_TERMINAL"}):
            changed = [stages[0], {**stages[1], **change}]
            self.assertEqual(resolve_next_action(changed, population="OPPORTUNITY_EPISODES")["owner_final"], "OBSERVABILITY_BLOCKED")
        pending = [stages[0], {**stages[1], "session_state": "FROZEN_AWAITING_CRITIC"}]
        self.assertIsNone(resolve_next_action(pending, population="OPPORTUNITY_EPISODES")["owner_final"])


class OperationProjectionBindingTests(unittest.TestCase):
    def test_paused_other_slot_cannot_override_active_child(self):
        from solana_alpha_lab.factory import hfic_ordinary_operation as owner
        with mock.patch.object(owner, "list_operations", return_value=[{
            "owner_focus": "OPPORTUNITY_EPISODES:AUTO", "market_evidence_epoch_sha256": MARKET,
            "scientific_slot_sha256": BASE_SLOT, "status": "PAUSED_CAP",
        }]):
            self.assertIsNone(owner.project_ordinary_operation(object(),
                owner_focus="OPPORTUNITY_EPISODES:AUTO", market_evidence_epoch_sha256=MARKET,
                scientific_slot_sha256=CHILD_SLOT))
        # A pause on this same slot still requires owner authority; no refund.
        merged = owner.merge_ordinary_readout({"next_action": "START_BASE"}, {
            "status": "PAUSED_CAP", "effective_state": "PAUSED_CAP", "owner_main_remaining": 0})
        self.assertEqual(merged["next_action"], "AUTHORIZE_ADDITIONAL_LOOKS")


class OrphanParentBindingTests(unittest.TestCase):
    def test_orphan_parent_is_selected_by_run_not_self_attested(self):
        from solana_alpha_lab.factory import hfic_session as owner
        kwargs = dict(market_evidence_epoch_sha256=MARKET, representation_id=REP,
                      representation_semantic_version="1.0", owner_focus="OPPORTUNITY_EPISODES:AUTO",
                      capability_epoch_sha256="1" * 64, memory_eligibility_sha256=None)
        with mock.patch.object(owner, "find_generated_draft", return_value={
            "control_session_id": "FOREIGN_BASE", "representation_payload_sha256": "2" * 64
        }), mock.patch.object(owner, "prefreeze_generated_draft_recovery", return_value=True) as validated:
            self.assertFalse(owner.orphan_prefreeze_draft_resumable(object(), **kwargs, control_session_id=BASE))
            self.assertFalse(owner.orphan_prefreeze_draft_resumable(object(), **kwargs))
            validated.assert_not_called()
            with mock.patch.object(owner, "list_hfic_sessions", return_value=[]), mock.patch.object(owner, "list_scientific_slot_admissions", return_value=[]):
                self.assertTrue(owner.orphan_prefreeze_draft_resumable(object(), **kwargs, control_session_id="FOREIGN_BASE"))
            self.assertEqual(validated.call_args.kwargs["control_session_id"], "FOREIGN_BASE")


class PersistenceReadoutTests(unittest.TestCase):
    def test_episode_resume_uses_own_saved_draft_and_native_instruction(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import format_forge_run_owner_readout
        body = {"next_action": "RESUME_" + REP, "owner_focus": "OPPORTUNITY_EPISODES:AUTO",
                "stages": [{"representation_id": "BASE", "draft_sha256": "3" * 64},
                           {"representation_id": REP, "draft_sha256": "4" * 64}]}
        text = format_forge_run_owner_readout(body)
        self.assertIn("status: NEXT — RESUME " + REP, text)
        self.assertIn("next: RESUME_EXISTING_SESSION", text)
        self.assertIn("--saved-draft-sha256 " + "4" * 64, text)
        self.assertNotIn("--saved-draft-sha256 " + "3" * 64, text)
        body["next_action"] = "RESUME_UNKNOWN_REPRESENTATION"
        self.assertNotIn("RESUME_EXISTING_SESSION", format_forge_run_owner_readout(body))

    def test_computed_final_is_not_a_persisted_receipt(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import format_forge_run_owner_readout
        body = {"owner_class": "OWNER_FINAL", "owner_final": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE",
                "next_action": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "receipt_sha256": "8" * 64,
                "writes": {"research_store": 0, "forge_run": 0, "session": 0}}
        text = format_forge_run_owner_readout(body)
        self.assertIn("status: NEXT — PERSIST_OWNER_FINAL", text)
        self.assertIn("persisted: NONE", text)
        self.assertIn("forge-run --persist --owner-focus", text)
        self.assertNotIn("persisted_receipt:", text)
        self.assertNotIn("status: DONE", text)
        body["persisted_receipt_sha256"] = "9" * 64
        text = format_forge_run_owner_readout(body)
        self.assertIn("status: READBACK", text)
        self.assertIn("persisted: READBACK", text)
        self.assertIn("persisted_receipt: " + "9" * 64, text)
        self.assertNotIn("persisted_receipt: " + "8" * 64, text)


class CompletedProvenanceScopeTests(unittest.TestCase):
    def test_aggregate_epoch_does_not_rebind_its_exact_saved_source_stage(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import _completed_readback_provenance_status

        stage = {"representation_id": "BASE", "session_id": BASE,
                 "scientific_slot_sha256": BASE_SLOT, "stage_ref_sha256": "1" * 64,
                 "capability_epoch_sha256": "2" * 64,
                 "execution_status": "REUSED_VALID",
                 "execution_provenance_status": "HISTORICAL_READBACK_UNKNOWN"}
        saved = {"capability_epoch_sha256": "3" * 64,
                 "scientific_slot_sha256": BASE_SLOT,
                 "execution_binding_sha256": None,
                 "execution_provenance_status": "NOT_APPLICABLE",
                 "stages": [copy.deepcopy(stage)]}
        original = copy.deepcopy(saved)
        def read(body):
            return _completed_readback_provenance_status(
                body, active_row=stage, scientific_slot_sha256=BASE_SLOT)

        self.assertEqual(read(saved), "HISTORICAL_READBACK_UNKNOWN")
        self.assertEqual(saved, original)
        changes = {
            "source-conflict": lambda b: b["stages"][0].update(capability_epoch_sha256="4" * 64),
            "malformed-aggregate": lambda b: b.update(capability_epoch_sha256="broken"),
            "malformed-binding": lambda b: b.update(execution_binding_sha256="broken"),
            "unbound-source": lambda b: b["stages"][0].update(session_id="FOREIGN"),
        }
        for name, mutate in changes.items():
            with self.subTest(name=name):
                changed = copy.deepcopy(saved)
                mutate(changed)
                self.assertEqual(read(changed), "EXECUTION_BINDING_CONFLICT")


class OrdinaryFinalizationVertical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests import test_hfic_list_aware_vertical_v1 as fixture
        cls.fixture = fixture
        fixture.ListAwareVerticalTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def call(self, *args):
        return self.fixture._forge_call(*args, data_root=self.plane)

    def save(self, name, body):
        p = self.work / name; p.write_text(json.dumps(body), encoding="utf-8"); return str(p)

    def test_existing_zero_candidate_stages_close_both_operations_without_new_looks(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_ordinary_operation import get_operation, operation_lifecycle
        from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
        from tests.test_hfic_cli import bind_draft
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
        f = self.fixture
        canonical = self.call("research-scope-resolve", "--spec", self.save("q.json", f.draft("LIST_CONTRAST", list_condition=f.AC)))["canonical_query"]
        pre = self.call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "FINALIZE")
        op = _operation(canonical, focus=pre["owner_focus"], journal=pre["search_key_sha256"], market=pre["market_evidence_epoch_sha256"],
                        text="One synthetic ordinary run to its terminal", cap={"main": None, "adaptive": None, "preview": None}, completion="SCIENTIFIC_TERMINAL")
        scope = {"estimand": "price_relative_proxy", "explanatory_condition": "LIST_CONTRAST"}
        first = f._discovery(self.plane, self.work, tag="base", spec=canonical, scope=scope, operation=op)
        self.assertEqual(first["_exit_code"], 0, first)
        fresh = self.call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"])
        template = json.loads((ROOT/"tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text())
        template["candidates"] = []
        for field in ("runner_up_candidate_ref", "strongest_rejected_alternative", "selected_candidate_ref"):
            template.pop(field, None)
        base_draft = bind_draft({**template, "owner_focus": pre["owner_focus"]}, fresh)
        base_draft["grounded_evidence"] = {k:v for k,v in first.items() if not k.startswith("_")}
        draft_path = self.save("base-draft.json", base_draft)
        self.call("persist-draft", "--draft", draft_path, "--preflight-receipt", self.save("pre.json", fresh), "--representation-id", "BASE")
        resume = self.call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"])
        base = self.call("freeze", "--draft", draft_path, "--preflight-receipt", self.save("resume.json", resume))
        started = self.call("forge-run", "--owner-focus", pre["owner_focus"], "--no-write")
        self.assertEqual(started["next_action"], "START_NORMALIZED_TRAJECTORY_EPISODES_V1")
        view = self.call("episode-normalized-view", "--spec", self.save("view.json", canonical), "--parent-session-id", base["session_id"], "--operation-sha256", first["operation_sha256"])
        child_pre = view["ladder_freeze_preflight"]
        child_op = {**op, "journal_scope": child_pre["search_key_sha256"], "representation": {
            "representation_id": REP, "representation_semantic_version": "1.0", "parent_session_id": base["session_id"],
            "representation_payload_sha256": view["representation_payload"]["representation_payload_sha256"],
            "scope_applied_sha256": view["representation_payload"]["scope_applied_sha256"]}}
        child_scope = {**scope, "representation_scope": REP}
        second = f._discovery(self.plane, self.work, tag="child", spec=canonical, scope=child_scope, operation=child_op)
        self.assertEqual(second["_exit_code"], 0, second)
        child_draft = bind_draft({**template, "owner_focus": pre["owner_focus"]}, child_pre)
        child_draft["grounded_evidence"] = {k:v for k,v in second.items() if not k.startswith("_")}
        child_path = self.save("child-draft.json", child_draft)
        child_pre_path = self.save("child-pre.json", child_pre)
        generated = self.call("persist-draft", "--draft", child_path, "--preflight-receipt", child_pre_path, "--representation-id", REP)
        from solana_alpha_lab.factory import hfic_evidence_identity as identity_owner
        from solana_alpha_lab.factory import hfic_representation_ladder as ladder
        from solana_alpha_lab.factory import hfic_session as session_owner
        with mock.patch.object(identity_owner, "resolve_scientific_admission", wraps=identity_owner.resolve_scientific_admission) as admission, mock.patch.object(session_owner, "orphan_prefreeze_draft_resumable", wraps=session_owner.orphan_prefreeze_draft_resumable) as orphan:
            pending = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
        self.assertTrue(any(call.kwargs.get("representation_id") == REP for call in admission.call_args_list))
        self.assertEqual(orphan.call_args.kwargs["control_session_id"], base["session_id"])
        self.assertEqual(pending["scientific_slot_sha256"], generated["scientific_slot_sha256"])
        self.assertEqual(pending["next_action"], "RESUME_NORMALIZED_TRAJECTORY_EPISODES_V1")
        self.assertIsNone(pending["owner_final"])
        self.assertIn("next: RESUME_EXISTING_SESSION", pending["owner_readout"])
        self.assertIn("--saved-draft-sha256 " + generated["payload_sha256"], pending["owner_readout"])
        actual_draft = ladder.find_generated_draft
        def incompatible_child(*args, **kwargs):
            found = actual_draft(*args, **kwargs)
            return {**found, "capability_epoch_sha256": "e" * 64} if found and found.get("ladder_representation_id") == REP else found
        with mock.patch.object(ladder, "find_generated_draft", side_effect=incompatible_child):
            refused = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
        self.assertEqual(refused["next_action"], "OBSERVABILITY_BLOCKED")
        self.assertIn("SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING", refused["blocking_reason_codes"])
        from solana_alpha_lab.factory import hfic_representation_ladder as ladder
        actual_input = ladder.build_forge_input_receipt
        def changed_capability(*args, **kwargs):
            body = actual_input(*args, **kwargs)
            body["capability_epoch_sha256"] = "0" * 64
            return body
        with mock.patch.object(ladder, "build_forge_input_receipt", side_effect=changed_capability):
            drifted_pending = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
        self.assertNotIn(drifted_pending["owner_final"], {"OWNER_CANDIDATE", "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "NON_SCIENTIFIC_STOP"})
        child = self.call("freeze", "--draft", child_path, "--preflight-receipt", child_pre_path)
        self.assertEqual(child["session_state"], "SYNTHESIS_COMPLETE")
        store = ResearchStore(self.plane)
        ids = [first["operation_sha256"], second["operation_sha256"]]
        before = store.diagnostics().committed_inventory_sha256
        looks = {p["search_key_sha256"]: list_discovery_looks(store, p["search_key_sha256"]) for p in (pre, child_pre)}
        original_parent = ladder._parent_control_id
        def foreign_parent(bundle, packet):
            return "FOREIGN_BASE" if bundle.get("session_id") == child["session_id"] else original_parent(bundle, packet)
        with mock.patch.object(ladder, "build_forge_input_receipt", side_effect=changed_capability):
            with mock.patch.object(ladder, "_parent_control_id", side_effect=foreign_parent):
                foreign = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
            self.assertNotIn(foreign["owner_final"], {"OWNER_CANDIDATE", "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "NON_SCIENTIFIC_STOP"})
            result = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
        self.assertEqual(result["owner_final"], "SEARCH_EXHAUSTED_CURRENT_EVIDENCE", result)
        self.assertIsNone(result["control_session_id"])
        self.assertIn("status: NEXT — PERSIST_OWNER_FINAL", result["owner_readout"])
        self.assertNotIn("persisted_receipt:", result["owner_readout"])
        self.assertEqual([s["session_id"] for s in result["stages"]], [base["session_id"], child["session_id"]])
        self.assertEqual(before, ResearchStore(self.plane).diagnostics().committed_inventory_sha256)
        for identity in ids:
            self.assertEqual(operation_lifecycle(store, get_operation(store, identity))["effective_state"], "OPEN")
        # Only the input epoch is a fixture seam. Persistence and each cold
        # evaluation use production owners with a fresh ResearchStore; the CLI
        # is a separate process and keeps its own actual current input epoch.
        with mock.patch.object(ladder, "build_forge_input_receipt", side_effect=changed_capability):
            persisted = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"], persist=True)
            self.assertEqual(persisted["owner_final"], "SEARCH_EXHAUSTED_CURRENT_EVIDENCE")
            self.assertEqual(persisted["capability_epoch_sha256"], "0" * 64)
            self.assertNotEqual(persisted["stages"][0]["capability_epoch_sha256"], "0" * 64)
            saved = ResearchStore(self.plane).diagnostics().committed_inventory_sha256
            readback = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"])
            repeated = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"], persist=True)
            explicit_context = ladder.evaluate_forge_run(ROOT, self.plane, owner_focus=pre["owner_focus"],
                execution_context={"model_provenance_sha256": "f" * 64}, persist=True)
        self.assertEqual(explicit_context["owner_class"], "OBSERVABILITY_BLOCKED")
        self.assertEqual(explicit_context["writes"], {"research_store": 0, "forge_run": 0, "session": 0})
        # _forge_call already refuses every nonzero subprocess exit.
        again = self.call("forge-run", "--owner-focus", pre["owner_focus"], "--persist")
        for replay in (readback, repeated, again):
            self.assertEqual(replay["owner_final"], "SEARCH_EXHAUSTED_CURRENT_EVIDENCE")
            self.assertEqual(replay["persisted_receipt_sha256"], persisted["receipt_sha256"])
            self.assertEqual(replay["execution_provenance_status"], "HISTORICAL_READBACK_UNKNOWN")
            self.assertEqual(replay["writes"], {"research_store": 0, "forge_run": 0, "session": 0})
        self.assertEqual(saved, ResearchStore(self.plane).diagnostics().committed_inventory_sha256, again)
        self.assertIn("status: DONE", persisted["owner_readout"])
        self.assertIn("status: READBACK", again["owner_readout"])
        self.assertIn("state=COMPLETED", again["owner_readout"])
        self.assertIn("persisted_receipt:", again["owner_readout"])
        for identity in ids:
            cold = ResearchStore(self.plane)
            self.assertEqual(operation_lifecycle(cold, get_operation(cold, identity))["effective_state"], "COMPLETED")
        for journal, rows in looks.items():
            self.assertEqual(rows, list_discovery_looks(ResearchStore(self.plane), journal))
        gate = self.call("universe-policy-status")
        self.assertFalse(gate["blocking_operations"], gate)


if __name__ == "__main__":
    unittest.main()
