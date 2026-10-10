"""Per-test explanation follows native reservations, without a second ledger."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary
from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_hfic_ordinary_operation_v1 import _operation, _simple_spec, JOURNAL, MARKET


class PendingAuthoredBasisTests(unittest.TestCase):
    """A real durable native reservation survives a new immutable request."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ResearchStore(Path(self.tmp.name) / "plane")
        self.spec = _simple_spec()
        self.request = _operation(self.spec, completion="LIMITED_RESULT", cap_main=1)
        self.request["question_text"] = "P1: before values; a failure leaves the question unresolved."
        self.operation = ordinary.record_operation(self.store, self.request)
        self.spec_sha = validate_temporal_query(self.spec)["spec_sha256"]
        ordinary._reserve(self.store, self.operation, spec_sha256=self.spec_sha)

    def gate(self, operation):
        # Only the independent admission boundary is isolated. The durable
        # request, reservation, accounting and gate under test are native.
        with patch.object(ordinary, "_admit", return_value={"action": "CONTINUE"}):
            return ordinary.gate_before_values(self.store,
                operation_sha256=operation["operation_sha256"], spec=self.spec,
                journal_scope=JOURNAL, verified_market=MARKET)

    def test_original_pending_request_resumes_without_another_reservation(self):
        before = self.store.diagnostics().committed_inventory_sha256
        answer = self.gate(self.operation)
        self.assertEqual(answer["disposition"], "RESUME")
        self.assertFalse(answer["values_loaded"])
        self.assertFalse(answer["writes"])
        self.assertEqual(answer["operation"]["question_text"], self.request["question_text"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        self.assertEqual(len(ordinary._iter_kind(self.store, ordinary.RESERVATION_KIND)), 1)

    def test_changed_supported_basis_cannot_take_another_operations_pending_spec(self):
        changed = copy.deepcopy(self.request)
        changed["question_text"] = "Conflicting P1: authored after the original reservation."
        other = ordinary.record_operation(self.store, changed)
        self.assertNotEqual(other["operation_sha256"], self.operation["operation_sha256"])
        before = self.store.diagnostics().committed_inventory_sha256
        with self.assertRaises(ordinary.OrdinaryOperationError) as stopped:
            self.gate(other)
        self.assertEqual(stopped.exception.code, "ORDINARY_LOOK_PENDING_IN_OTHER_OPERATION")
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        reservations = ordinary._iter_kind(self.store, ordinary.RESERVATION_KIND)
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["operation_sha256"], self.operation["operation_sha256"])
        occupancy = ordinary.journal_occupancy(self.store, JOURNAL)
        self.assertEqual((occupancy["main"]["completed"], occupancy["main"]["pending"]), (0, 1))

    def test_reservation_commit_rechecks_foreign_pending_under_the_writer_lease(self):
        changed = copy.deepcopy(self.request)
        changed["question_text"] = "Another request that raced the original durable reservation."
        other = ordinary.record_operation(self.store, changed)
        before = self.store.diagnostics().committed_inventory_sha256
        with self.assertRaises(ordinary.OrdinaryOperationError) as stopped:
            ordinary._reserve(self.store, other, spec_sha256=self.spec_sha)
        self.assertEqual(stopped.exception.code, "ORDINARY_LOOK_PENDING_IN_OTHER_OPERATION")
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        self.assertEqual(len(ordinary._iter_kind(self.store, ordinary.RESERVATION_KIND)), 1)

    def test_legacy_duplicate_pending_has_no_automatic_original_to_resume(self):
        changed = copy.deepcopy(self.request)
        changed["question_text"] = "Legacy second request for the same occupied scientific spec."
        other = ordinary.record_operation(self.store, changed)
        # Reproduce only the predecessor's missing guard. Both records still
        # come from the native reservation writer, never injected ref joins.
        with patch.object(ordinary, "_assert_no_foreign_pending", return_value=None):
            ordinary._reserve(self.store, other, spec_sha256=self.spec_sha)
        before = self.store.diagnostics().committed_inventory_sha256
        reservations = ordinary._iter_kind(self.store, ordinary.RESERVATION_KIND)
        self.assertEqual(len(reservations), 2)
        for operation in (self.operation, other):
            with self.subTest(operation=operation["operation_sha256"]), self.assertRaises(ordinary.OrdinaryOperationError) as stopped:
                self.gate(operation)
            self.assertEqual(stopped.exception.code, "ORDINARY_LOOK_PENDING_BINDING_CONFLICT")
            self.assertEqual(stopped.exception.detail["next_action"], "RESOLVE_PENDING_BINDING_CONFLICT")
            bindings = stopped.exception.detail["pending_bindings"]
            self.assertEqual({row["operation_sha256"] for row in bindings},
                {self.operation["operation_sha256"], other["operation_sha256"]})
            self.assertEqual({row["reservation_ref"] for row in bindings},
                {row["record_id"] for row in reservations})
            self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_identical_spec_in_an_unrelated_accounting_root_is_not_foreign_pending(self):
        unrelated = copy.deepcopy(self.request)
        unrelated["journal_scope"] = "ef" * 32
        unrelated["owner_focus"] = "UNRELATED_SYNTHETIC_FOCUS"
        unrelated["question_text"] = "Independent authorized fixture root; no continuation link."
        other = ordinary.record_operation(self.store, unrelated)
        ordinary._reserve(self.store, other, spec_sha256=self.spec_sha)
        self.assertEqual(ordinary.accounting_root_of(self.store, JOURNAL), JOURNAL)
        self.assertEqual(ordinary.accounting_root_of(self.store, unrelated["journal_scope"]), unrelated["journal_scope"])
        self.assertEqual(self.gate(self.operation)["disposition"], "RESUME")
        self.assertEqual(len(ordinary._iter_kind(self.store, ordinary.RESERVATION_KIND)), 2)

    def test_public_projection_of_pending_request_has_one_archive_enumeration_and_no_values(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import discovery_detail
        owner = self
        class CountedStore:
            calls = 0
            def iter_committed_records(self):
                self.calls += 1
                return owner.store.iter_committed_records()
        counted = CountedStore()
        before = self.store.diagnostics().committed_inventory_sha256
        with patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows", side_effect=AssertionError("VALUES_FORBIDDEN")), \
             patch("solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery", side_effect=AssertionError("EVALUATOR_FORBIDDEN")):
            answer = discovery_detail(counted, operation_sha256=self.operation["operation_sha256"], current_market=MARKET)
        self.assertEqual(counted.calls, 1)
        self.assertEqual(answer["entries"], [])
        self.assertEqual(answer["total_results"], 0)
        self.assertEqual(answer["operation_request"]["question_text"], self.request["question_text"])
        self.assertEqual(len(answer["pending_reservations"]), 1)
        self.assertFalse(answer["values_loaded"])
        self.assertEqual(answer["writes"], {"research_store": 0})
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_unreadable_native_request_or_reservation_is_not_empty_pending(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        records = tuple(self.store.iter_committed_records())
        before = self.store.diagnostics().committed_inventory_sha256
        class View:
            def __init__(self, target): self.target = target
            def iter_committed_records(self):
                return iter(record.model_copy(update={"payload_json": "{"}) if record.record_id == self.target else record for record in records)
        valid = discovery_detail(View(None), operation_sha256=self.operation["operation_sha256"])
        self.assertEqual(len(valid["pending_reservations"]), 1)
        request_ref = ordinary.get_operation(self.store, self.operation["operation_sha256"])["record_id"]
        for target in (request_ref, ordinary._reservations(self.store, self.operation["operation_sha256"])[0]["record_id"]):
            self.assertIn(target, {record.record_id for record in records})
            with self.subTest(target=target):
                with self.assertRaises(DiscoveryDetailError) as stopped:
                    discovery_detail(View(target), operation_sha256=self.operation["operation_sha256"])
                self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
        self.assertEqual(discovery_detail(View(None), operation_sha256=self.operation["operation_sha256"]), valid)
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)


from tests.test_hfic_scientific_disposition_continuity_v1 import _Base, _ctx, question_packet


class NativeSavedSourceProjectionTests(_Base):
    """Portable real producer bytes; view faults never fabricate a result join."""

    def setUp(self):
        self.ctx = _ctx(self.workspace())
        self.store = ResearchStore(self.ctx["root"], create_if_missing=False)
        self.records = tuple(self.store.iter_committed_records())
        self.look = self.ctx["q1"]

    def view(self, transform=None):
        owner = self
        class View:
            calls = 0
            def iter_committed_records(self):
                self.calls += 1
                return iter(transform(owner.records) if transform else owner.records)
        return View()

    def test_unscoped_disposition_source_cannot_look_absent_or_leave_a_clean_prior_head(self):
        from solana_alpha_lab.factory import hfic_scientific_disposition as disp
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        self.store.prepare_write_lookup()
        packet = question_packet(self.ctx, self.look)
        first = disp.record_disposition(self.store, packet, current_market=self.ctx["market"])
        successor = copy.deepcopy(packet)
        successor["judgement"].update(verdict="INSUFFICIENT_EVIDENCE", recommendation="REVIEW_BOUNDED_SCOPE")
        successor["supersedes"] = {"record_id": first["record_id"], "disposition_sha256": first["disposition_sha256"]}
        second = disp.record_disposition(self.store, successor, current_market=self.ctx["market"])
        withdrawal = {"entry": "WITHDRAWAL", "subject": packet["subject"],
            "withdrawal": {"reason": "Synthetic source-integrity counterpart."},
            "supersedes": {"record_id": second["record_id"], "disposition_sha256": second["disposition_sha256"]},
            "provenance": {"author_role": "OPERATOR", "source_episode": "SYNTHETIC-SOURCE-FAULT", "source_refs": []}}
        last = disp.record_disposition(self.store, withdrawal, current_market=self.ctx["market"])
        self.records = tuple(self.store.iter_committed_records())
        before = self.store.diagnostics().committed_inventory_sha256
        valid = discovery_detail(self.view(), result_ref=self.look["record_id"], current_market=self.ctx["market"])
        self.assertEqual(valid["entries"][0]["scientific_disposition"]["status"], "WITHDRAWN")
        import hashlib
        def unscoped(records):
            for record in records:
                if record.record_id != last["record_id"]:
                    yield record
                    continue
                wrapper = json.loads(record.payload_json)
                wrapper.update(payload_canonical="{}", payload_sha256=hashlib.sha256(b"{}").hexdigest())
                yield record.model_copy(update={"payload_json": json.dumps(wrapper)})
        self.assertTrue(any(not item["readable"] and not item.get("subject_key") for item in disp._View(self.view(unscoped)).dispositions))
        with self.assertRaises(DiscoveryDetailError) as stopped:
            discovery_detail(self.view(unscoped), operation_sha256=self.look["operation_sha256"], current_market=self.ctx["market"])
        self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
        def unrelated(records):
            yield from records
            yield records[0].model_copy(update={"record_id": "UNRELATED-RESEARCH-READ-CANARY", "record_kind": "RESEARCH_ARTIFACT", "payload_json": "{"})
        self.assertEqual(discovery_detail(self.view(unrelated), result_ref=self.look["record_id"], current_market=self.ctx["market"]), valid)
        for target in [first["record_id"], second["record_id"], last["record_id"]]:
            def corrupted(records):
                for record in records:
                    yield record.model_copy(update={"payload_json": "{"}) if record.record_id == target else record
            for locator in ({"result_ref": self.look["record_id"]}, {"operation_sha256": self.look["operation_sha256"]}):
                with self.subTest(target=target, locator=locator):
                    with self.assertRaises(DiscoveryDetailError) as stopped:
                        discovery_detail(self.view(corrupted), **locator, current_market=self.ctx["market"])
                    self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
        self.assertEqual(discovery_detail(self.view(), result_ref=self.look["record_id"], current_market=self.ctx["market"]), valid)
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def new_reservation_request(self, text):
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation as native_request
        from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_discovery_binding
        # Relocation rebuilds only the native lookup, never producer records.
        inventory = self.store.diagnostics().committed_inventory_sha256
        self.store.prepare_write_lookup()
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, inventory)
        original = ordinary.get_operation(self.store, self.look["operation_sha256"])
        spec = json.loads(original["spec_canonical"])
        operation = ordinary.record_operation(self.store, native_request(spec,
            focus=original["owner_focus"], journal=self.ctx["journal"], market=self.ctx["market"],
            text=text, cap={"main": 1, "adaptive": 1, "preview": 0}))
        fingerprint = ordinary.binding_fingerprint(resolve_published_discovery_binding(self.ctx["root"])["cohorts"])
        self.assertTrue(fingerprint)
        return ordinary._stamp_fingerprint(self.store, operation["operation_sha256"], fingerprint)

    def test_landed_native_result_refuses_another_reservation_before_append(self):
        operation = self.new_reservation_request("Same native corpus and policy; new authored request.")
        before = self.store.diagnostics().committed_inventory_sha256
        for kind in ("main", "adaptive"):
            with self.subTest(kind=kind), self.assertRaises(ordinary.OrdinaryOperationError) as stopped:
                ordinary._reserve(self.store, operation, spec_sha256=self.look["spec_sha256"], look_class=kind)
            self.assertEqual(stopped.exception.code, "ORDINARY_LOOK_LANDED_DURING_RESERVATION")
            self.assertEqual(stopped.exception.detail, {
                "original_operation_sha256": self.look["operation_sha256"],
                "original_result_ref": self.look["record_id"], "result_sha256": self.look["result_sha256"],
                "spec_sha256": self.look["spec_sha256"], "next_action": "REPLAY_SAVED_RESULT"})
        self.assertEqual(ordinary._reservations(self.store, operation["operation_sha256"]), [])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_real_policy_change_is_not_blanket_blocked_by_same_spec(self):
        from solana_alpha_lab.factory.hfic_research_universe_policy import effective_policy, ensure_profile
        self.store.prepare_write_lookup()
        prior = effective_policy(self.store)["semantic_sha256"]
        changed = ensure_profile(self.store, repo_root=ROOT, min_holders=1, min_liquidity_usd=0)
        self.assertNotEqual(changed["semantic_sha256"], prior)
        # Policy changes precede a new active operation, as the policy owner
        # requires; the producer's original paused operations stay intact.
        operation = self.new_reservation_request("Native policy-change reservation seam counterpart.")
        # Exercise the reservation seam, not a claim about full public admission.
        # The existing matcher and native policy reader are never replaced.
        ordinary._reserve(self.store, operation, spec_sha256=self.look["spec_sha256"], look_class="adaptive")
        reservations = ordinary._reservations(self.store, operation["operation_sha256"])
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["look_class"], "ADAPTIVE")
        self.assertEqual(ordinary._operation_result(ordinary._looks(self.store, self.ctx["journal"]),
            self.look["operation_sha256"], self.look["spec_sha256"])["result_sha256"], self.look["result_sha256"])

    def test_real_added_cohort_is_not_blanket_blocked_by_same_spec(self):
        from tests.test_hfic_temporal_production_runner_v1 import _publish
        from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_discovery_binding
        original = ordinary.get_operation(self.store, self.look["operation_sha256"])
        self.store.prepare_write_lookup()
        # A genuine new sealed/imported/published cohort changes corpus metadata;
        # no look or operation/result relationship is injected or corrupted.
        _publish(self.ctx["root"], self.ctx["root"].parent, week=1)
        actual = ordinary.binding_fingerprint(resolve_published_discovery_binding(self.ctx["root"])["cohorts"])
        self.assertNotEqual(actual, original["corpus_fingerprint"])
        operation = self.new_reservation_request("Native added-cohort reservation seam counterpart.")
        self.assertEqual(operation["corpus_fingerprint"], actual)
        ordinary._reserve(self.store, operation, spec_sha256=self.look["spec_sha256"])
        reservations = ordinary._reservations(self.store, operation["operation_sha256"])
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["look_class"], "MAIN")
        self.assertEqual(ordinary._operation_result(ordinary._looks(self.store, self.ctx["journal"]),
            self.look["operation_sha256"], self.look["spec_sha256"])["result_sha256"], self.look["result_sha256"])

    def test_real_saved_sources_have_single_scan_and_addressed_empty_page_is_read_only(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import discovery_detail
        before = self.store.diagnostics().committed_inventory_sha256
        view = self.view()
        answer = discovery_detail(view, result_ref=self.look["record_id"], current_market=self.ctx["market"])
        self.assertEqual(view.calls, 1)
        entry = answer["entries"][0]
        self.assertEqual(entry["result_sha256"], self.look["result_sha256"])
        self.assertEqual(entry["operation_sha256"], self.look["operation_sha256"])
        self.assertEqual(entry["authored_basis_status"], "RECORDED_REQUEST")
        self.assertEqual(validate_temporal_query(entry["canonical_query"])["spec_sha256"], self.look["spec_sha256"])
        self.assertEqual(entry["scientific_disposition"], {"status": "NOT_RECORDED"})
        self.assertEqual(entry["assessment_history"], [])
        page = discovery_detail(self.view(), operation_sha256=self.look["operation_sha256"], offset=1, limit=1)
        self.assertEqual(page["entries"], [])
        self.assertEqual(page["total_results"], 1)
        self.assertIsNone(page["next_offset"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_produced_then_unavailable_operation_is_typed_missing_and_never_inferred(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        def missing(records):
            for record in records:
                try:
                    wrapper = json.loads(record.payload_json)
                    body = json.loads(wrapper.get("payload_canonical", "null"))
                except (ValueError, TypeError):
                    body = None
                if isinstance(body, dict) and body.get("artifact_kind") == ordinary.OPERATION_KIND \
                        and body.get("operation_sha256") == self.look["operation_sha256"]:
                    continue
                yield record
        before = self.store.diagnostics().committed_inventory_sha256
        with self.assertRaises(DiscoveryDetailError) as stopped:
            discovery_detail(self.view(missing), result_ref=self.look["record_id"], current_market=self.ctx["market"])
        self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_OPERATION_SOURCE_MISSING")
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_foreign_locator_and_missing_result_ref_do_not_guess_the_result(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        for locator, code in (({"result_ref": self.look["record_id"], "operation_sha256": "ff" * 32}, "DISCOVERY_DETAIL_LOCATOR_MISMATCH"),
                              ({"result_ref": "HFIC-ART-DISCOVERY-ABSENT"}, "DISCOVERY_DETAIL_RESULT_NOT_FOUND")):
            with self.subTest(locator=locator), self.assertRaises(DiscoveryDetailError) as stopped:
                discovery_detail(self.view(), **locator)
            self.assertEqual(stopped.exception.code, code)

    def test_unreadable_saved_result_view_is_typed_and_never_reconstructed(self):
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        # Read-boundary corruption canary over a real producer record. The
        # native committed store remains intact; this is neither a new result
        # nor a fabricated operation/result relationship.
        def corrupted(records):
            for record in records:
                yield record.model_copy(update={"payload_json": "{"}) if record.record_id == self.look["record_id"] else record
        before = self.store.diagnostics().committed_inventory_sha256
        for locator in ({"result_ref": self.look["record_id"]},
                        {"operation_sha256": self.look["operation_sha256"]},
                        {"operation_sha256": self.look["operation_sha256"], "offset": 1, "limit": 1}):
            with self.subTest(locator=locator):
                with self.assertRaises(DiscoveryDetailError) as stopped:
                    discovery_detail(self.view(corrupted), **locator, current_market=self.ctx["market"])
                self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
        # The same native snapshot contains q2 from a different operation.
        # Once unreadable, its affiliation cannot be trusted to exempt q1.
        other_ref = self.ctx["q2"]["record_id"]
        def ambiguous(records):
            for record in records:
                yield record.model_copy(update={"payload_json": "{"}) if record.record_id == other_ref else record
        with self.assertRaises(DiscoveryDetailError) as stopped:
            discovery_detail(self.view(ambiguous), operation_sha256=self.look["operation_sha256"], limit=1)
        self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_result_integrity_is_checked_before_pagination(self):
        import hashlib
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        def corrupted(records):
            for record in records:
                if record.record_id != self.look["record_id"]:
                    yield record
                    continue
                wrapper = json.loads(record.payload_json)
                body = json.loads(wrapper["payload_canonical"])
                body["result_sha256"] = "ff" * 32
                canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
                wrapper.update(payload_canonical=canonical, payload_sha256=hashlib.sha256(canonical.encode()).hexdigest())
                yield record.model_copy(update={"payload_json": json.dumps(wrapper)})
        before = self.store.diagnostics().committed_inventory_sha256
        for locator in ({"result_ref": self.look["record_id"], "offset": 1},
                        {"operation_sha256": self.look["operation_sha256"], "offset": 1}):
            with self.subTest(locator=locator):
                with self.assertRaises(DiscoveryDetailError) as stopped:
                    discovery_detail(self.view(corrupted), **locator)
                self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_RESULT_HASH_MISMATCH")
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_malformed_saved_query_pin_refuses_with_a_valid_source_counterpart(self):
        import hashlib
        from solana_alpha_lab.factory.hfic_discovery_detail import DiscoveryDetailError, discovery_detail
        def malformed_query(records):
            for record in records:
                wrapper = json.loads(record.payload_json)
                body = json.loads(wrapper.get("payload_canonical", "null"))
                if isinstance(body, dict) and body.get("artifact_kind") == ordinary.OPERATION_KIND \
                        and body.get("operation_sha256") == self.look["operation_sha256"]:
                    # Keep the real immutable identity and all ref joins; only
                    # the saved query read boundary is corrupted, in this view.
                    body["spec_canonical"] = "{"
                    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    wrapper.update(payload_canonical=canonical, payload_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest())
                    payload = json.dumps(wrapper, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    yield record.model_copy(update={"payload_json": payload,
                        "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()})
                else:
                    yield record
        before = self.store.diagnostics().committed_inventory_sha256
        valid = discovery_detail(self.view(), result_ref=self.look["record_id"], current_market=self.ctx["market"])
        with self.assertRaises(DiscoveryDetailError) as stopped:
            discovery_detail(self.view(malformed_query), result_ref=self.look["record_id"], current_market=self.ctx["market"])
        self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_QUERY_UNAVAILABLE")
        self.assertEqual(discovery_detail(self.view(), result_ref=self.look["record_id"], current_market=self.ctx["market"]), valid)
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)


if __name__ == "__main__":
    unittest.main()
