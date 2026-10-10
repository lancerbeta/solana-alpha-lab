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


from tests.test_hfic_scientific_disposition_continuity_v1 import _Base, _ctx


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
        with self.assertRaises(DiscoveryDetailError) as stopped:
            discovery_detail(self.view(corrupted), result_ref=self.look["record_id"], current_market=self.ctx["market"])
        self.assertEqual(stopped.exception.code, "DISCOVERY_DETAIL_SOURCE_UNREADABLE")
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
