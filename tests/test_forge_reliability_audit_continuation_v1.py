"""Minimal synthetic reproducer for PREVIEW request accounting; no native/science PASS."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tests.test_hfic_research_policy_closure_v1 import (
    GIT, JOURNAL, MARKET, _guard, _operation, _spend_main,
)
from solana_alpha_lab.factory import hfic_ordinary_operation as oo
from solana_alpha_lab.factory import hfic_research_policy as rp
from solana_alpha_lab.factory.hfic_temporal_discovery import persist_feature_preview
from solana_alpha_lab.factory.research_store import ResearchStore


def descriptor(index: int) -> str:
    return hashlib.sha256(f"distinct-request-{index}".encode()).hexdigest()


def land(store, operation, index):
    digest = operation["operation_sha256"]
    gate = oo.authorize_episode_view(
        store, operation_sha256=digest, journal_scope=JOURNAL,
        descriptor_sha256=descriptor(index), verified_market=MARKET,
    )
    oo.land_episode_view(
        store, operation_sha256=digest, journal_scope=JOURNAL,
        descriptor_sha256=descriptor(index), payload_sha256="e5" * 32, git_sha=GIT,
    )
    return gate["disposition"]


class PreviewRequestAccountingTests(unittest.TestCase):
    def test_distinct_requests_same_payload_exhaust_protocol_and_preserve_repeat(self):
        # The BASE defect was independently observed 2/2 before this regression was added.
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            operation = _operation(store)
            self.assertEqual(land(store, operation, 0), "EXECUTE")
            self.assertEqual(land(store, operation, 1), "EXECUTE")
            fresh = ResearchStore(Path(tmp), create_if_missing=False)
            self.assertEqual(oo.journal_occupancy(fresh, JOURNAL)["preview"], {
                "limit": 2, "completed": 2, "pending": 0, "occupied": 2,
                "remaining": 0, "deficit": 0,
            })
            records = len(list(fresh.iter_committed_records()))
            with self.assertRaises(oo.OrdinaryOperationError) as stop:
                land(fresh, operation, 2)
            self.assertEqual(stop.exception.code, "OWNER_CAP_EXHAUSTED")
            self.assertEqual(land(fresh, operation, 0), "REPEAT")
            self.assertEqual(len(list(fresh.iter_committed_records())), records)

    def test_explicit_owner_cap_uses_request_identity_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            operation = _operation(store, owner_cap={"main": None, "adaptive": None, "preview": 2})
            proposal = rp.propose_run_extension(
                store, scope_key=JOURNAL, parent_operation_sha256=operation["operation_sha256"],
                limits_delta={"preview_total": 3},
            )
            rp.apply_run_extension_set(store, proposals=[proposal], confirm_append_only=True, parent_guard=_guard(store))
            land(store, operation, 0)
            land(store, operation, 1)
            self.assertEqual(oo.journal_occupancy(store, JOURNAL)["preview"]["remaining"], 1)
            self.assertEqual(oo.owner_allowance(store, operation, "preview"), 0)
            with self.assertRaises(oo.OrdinaryOperationError) as stop:
                land(store, operation, 2)
            self.assertEqual(stop.exception.code, "OWNER_CAP_EXHAUSTED")

    def test_completed_and_pending_requests_do_not_double_charge_on_landing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            operation = _operation(store)
            land(store, operation, 0)
            gate = oo.authorize_episode_view(
                store, operation_sha256=operation["operation_sha256"], journal_scope=JOURNAL,
                descriptor_sha256=descriptor(1), verified_market=MARKET,
            )
            self.assertEqual(gate["disposition"], "EXECUTE")
            before = oo.journal_occupancy(store, JOURNAL)["preview"]
            self.assertEqual((before["completed"], before["pending"], before["occupied"]), (1, 1, 2))
            self.assertEqual(land(store, operation, 1), "RESUME")
            after = oo.journal_occupancy(store, JOURNAL)["preview"]
            self.assertEqual((after["completed"], after["pending"], after["occupied"]), (2, 0, 2))

    def test_legacy_unkeyed_preview_keeps_its_charge_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            operation = _operation(store)
            persist_feature_preview(store, journal_scope=JOURNAL, preview={"preview_sha256": "e5" * 32}, git_sha=GIT)
            old = {row.record_id: row.payload_json for row in store.iter_committed_records()}
            self.assertEqual(oo.journal_occupancy(store, JOURNAL)["preview"]["completed"], 1)
            land(store, operation, 0)
            self.assertEqual(oo.journal_occupancy(store, JOURNAL)["preview"]["completed"], 2)
            new = {row.record_id: row.payload_json for row in store.iter_committed_records()}
            self.assertEqual({key: new[key] for key in old}, old)

    def test_main_five_completed_plus_two_pending_leave_three_of_ten(self):
        # Injected accounting control, deliberately not credited as a research journey.
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            operation = _operation(store)
            _spend_main(store, operation, JOURNAL, 5)
            proposal = rp.propose_run_extension(
                store, scope_key=JOURNAL, parent_operation_sha256=operation["operation_sha256"],
                limits_delta={"main_total": 10},
            )
            rp.apply_run_extension_set(store, proposals=[proposal], confirm_append_only=True, parent_guard=_guard(store))
            for index in (5, 6):
                oo._reserve(store, operation, spec_sha256=f"q{index:02d}".ljust(64, "0"))
            before = oo.journal_occupancy(store, JOURNAL)["main"]
            self.assertEqual((before["completed"], before["pending"], before["remaining"]), (5, 2, 3))
            _spend_main(store, operation, JOURNAL, 7)
            after = oo.journal_occupancy(store, JOURNAL)["main"]
            self.assertEqual((after["completed"], after["pending"], after["remaining"]), (7, 0, 3))


if __name__ == "__main__":
    unittest.main()
