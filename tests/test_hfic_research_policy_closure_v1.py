"""FORGE_RESEARCH_POLICY_RUNTIME_V1 closure: owner-review P1-A..P1-D at the owner boundaries.

Each class is the RED/GREEN for one finding, against the real owners and a real ResearchStore.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import hfic_ordinary_operation as oo  # noqa: E402
from solana_alpha_lab.factory import hfic_research_policy as rp  # noqa: E402
from solana_alpha_lab.factory.hfic_memory_policy import cycle_search_key  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

JOURNAL = "a1" * 32
MARKET = "b2" * 32
GIT = "c" * 40


def _operation(store: ResearchStore, *, journal: str = JOURNAL, text: str = "closure run", **extra) -> dict:
    request = {
        "owner_request_text": text,
        "owner_focus": "AUTO",
        "journal_scope": journal,
        "market_evidence_epoch_sha256": MARKET,
        "owner_cap": {"main": None, "adaptive": None, "preview": None},
        "requested_completion": oo.LIMITED_RESULT,
    }
    request.update(extra)
    return oo.record_operation(store, request)


class ReservedPreviewResumeTests(unittest.TestCase):
    """P1-C: a reserved PREVIEW is not a completed REPEAT; a crash after reserve resumes without new spend."""

    def test_reserve_then_crash_then_retry_lands_the_same_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            operation = _operation(store)
            digest = str(operation["operation_sha256"])
            descriptor = "d1" * 32
            kwargs = dict(operation_sha256=digest, journal_scope=JOURNAL, descriptor_sha256=descriptor, verified_market=MARKET)

            first = oo.authorize_episode_view(store, **kwargs)  # reserve, then the process "crashes" before landing
            self.assertEqual(first["disposition"], "EXECUTE")
            pending = oo.journal_occupancy(store, JOURNAL)["preview"]
            self.assertEqual((pending["completed"], pending["pending"], pending["occupied"]), (0, 1, 1))
            with self.assertRaises(oo.OrdinaryOperationError) as blocked:
                oo.extension_parent(store, digest)
            self.assertEqual(blocked.exception.code, "EXTENSION_PARENT_HAS_PENDING_RESERVATION")

            fresh = ResearchStore(Path(raw), create_if_missing=False)  # a fresh process reads durable state only
            resumed = oo.authorize_episode_view(fresh, **kwargs)
            self.assertEqual(resumed["disposition"], "RESUME")
            self.assertTrue(resumed["writes"])
            still = oo.journal_occupancy(fresh, JOURNAL)["preview"]
            self.assertEqual((still["completed"], still["pending"], still["occupied"]), (0, 1, 1))

            oo.land_episode_view(
                fresh, operation_sha256=digest, journal_scope=JOURNAL, descriptor_sha256=descriptor,
                payload_sha256="e5" * 32, git_sha=GIT,
            )
            done = oo.journal_occupancy(fresh, JOURNAL)["preview"]
            self.assertEqual((done["completed"], done["pending"], done["occupied"]), (1, 0, 1))

            repeat = oo.authorize_episode_view(fresh, **kwargs)
            self.assertEqual((repeat["disposition"], repeat["writes"]), ("REPEAT", False))
            after = oo.journal_occupancy(fresh, JOURNAL)["preview"]
            self.assertEqual((after["completed"], after["pending"], after["occupied"]), (1, 0, 1))
            self.assertEqual(oo.extension_parent(fresh, digest)["operation_sha256"], digest)

    def test_a_pending_preview_of_another_operation_is_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            first = _operation(store, text="first")
            second = _operation(store, text="second")
            descriptor = "d2" * 32
            oo.authorize_episode_view(
                store, operation_sha256=str(first["operation_sha256"]), journal_scope=JOURNAL,
                descriptor_sha256=descriptor, verified_market=MARKET,
            )
            with self.assertRaises(oo.OrdinaryOperationError) as raised:
                oo.authorize_episode_view(
                    store, operation_sha256=str(second["operation_sha256"]), journal_scope=JOURNAL,
                    descriptor_sha256=descriptor, verified_market=MARKET,
                )
            self.assertEqual(raised.exception.code, "EPISODE_VIEW_PENDING_IN_OTHER_OPERATION")


def _guard(store: ResearchStore):
    """The CLI's live parent guard: run open, nothing pending, scope belongs to the run."""

    def _check(checked: dict) -> None:
        parent = oo.extension_parent(store, str(checked["parent_operation_sha256"]))
        allowed = {
            str(parent.get("accounting_root") or parent["journal_scope"]),
            rp.epoch_scope_key(str(parent["market_evidence_epoch_sha256"])),
        }
        if str(checked["scope_key"]) not in allowed:
            raise rp.ResearchPolicyError("RESEARCH_POLICY_EXTENSION_BINDING_INVALID", field="scope_key")

    return _check


def _set(store: ResearchStore, digest: str):
    epoch = rp.epoch_scope_key(MARKET)
    rp.ensure_scope_snapshot(store, JOURNAL)
    rp.ensure_scope_snapshot(store, epoch)
    journal = rp.propose_run_extension(store, scope_key=JOURNAL, parent_operation_sha256=digest, limits_delta={"main_total": 10})
    pool = rp.propose_run_extension(store, scope_key=epoch, parent_operation_sha256=digest, limits_delta={"auto_cycles_per_market": 2})
    return epoch, journal, pool


def _rows(store: ResearchStore) -> tuple[int, int]:
    return len(rp.read_scope_extensions(store, JOURNAL)), len(rp.read_scope_extensions(store, rp.epoch_scope_key(MARKET)))


class AtomicExtensionSetTests(unittest.TestCase):
    """P1-B: a supported multi-scope extension commits whole or not at all, re-checked under the lease."""

    def test_valid_first_and_invalid_second_commit_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            digest = str(_operation(store)["operation_sha256"])
            _epoch, journal, pool = _set(store, digest)
            broken = dict(pool)
            broken["resulting_limits"] = {**pool["resulting_limits"], "auto_cycles_per_market": 3}  # hash no longer matches
            before = store.diagnostics().committed_inventory_sha256
            with self.assertRaises(rp.ResearchPolicyError):
                rp.apply_run_extension_set(store, proposals=[journal, broken], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual(_rows(store), (0, 0))
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_legal_journal_and_epoch_set_with_a_conflict_on_the_second_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            digest = str(_operation(store)["operation_sha256"])
            epoch, journal, pool = _set(store, digest)
            rival = rp.propose_run_extension(store, scope_key=epoch, parent_operation_sha256=digest, limits_delta={"distinct_focuses_per_market": 5})
            rp.apply_run_extension_set(store, proposals=[rival], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual(_rows(store), (0, 1))
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_run_extension_set(store, proposals=[journal, pool], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_EXTENSION_STALE")
            self.assertEqual(_rows(store), (0, 1))  # the legal journal extension was not left behind

    def test_a_pending_reservation_after_preview_refuses_the_whole_set(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            digest = str(_operation(store)["operation_sha256"])
            _epoch, journal, pool = _set(store, digest)
            oo.authorize_episode_view(  # a reservation appears after the preview was taken
                store, operation_sha256=digest, journal_scope=JOURNAL, descriptor_sha256="f1" * 32, verified_market=MARKET
            )
            with self.assertRaises(oo.OrdinaryOperationError) as raised:
                rp.apply_run_extension_set(store, proposals=[journal, pool], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual(raised.exception.code, "EXTENSION_PARENT_HAS_PENDING_RESERVATION")
            self.assertEqual(_rows(store), (0, 0))

    def test_stopped_after_preview_refuses_the_whole_set(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            digest = str(_operation(store)["operation_sha256"])
            _epoch, journal, pool = _set(store, digest)
            preview = oo.preview_operation_stop(store, operation_sha256=digest, owner_request_text="stop it")
            oo.apply_operation_stop(store, proposal=preview["proposal"], confirm_append_only=True)
            with self.assertRaises(oo.OrdinaryOperationError) as raised:
                rp.apply_run_extension_set(store, proposals=[journal, pool], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual(raised.exception.code, "ORDINARY_OPERATION_STOPPED")
            self.assertEqual(_rows(store), (0, 0))

    def test_exact_repeat_after_reply_loss_is_idempotent_and_duplicates_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            digest = str(_operation(store)["operation_sha256"])
            _epoch, journal, pool = _set(store, digest)
            first = rp.apply_run_extension_set(store, proposals=[journal, pool], confirm_append_only=True, parent_guard=_guard(store))
            self.assertEqual([item["status"] for item in first], [rp.APPENDED, rp.APPENDED])
            self.assertEqual(_rows(store), (1, 1))
            fresh = ResearchStore(Path(raw), create_if_missing=False)  # the reply was lost; the owner repeats
            again = rp.apply_run_extension_set(fresh, proposals=[journal, pool], confirm_append_only=True, parent_guard=_guard(fresh))
            self.assertEqual([item["status"] for item in again], [rp.ALREADY_APPLIED, rp.ALREADY_APPLIED])
            self.assertEqual([item["writes"] for item in again], [{"research_store": 0}, {"research_store": 0}])
            self.assertEqual(_rows(fresh), (1, 1))
            with self.assertRaises(rp.ResearchPolicyError) as dup:
                rp.apply_run_extension_set(fresh, proposals=[journal, journal], confirm_append_only=True)
            self.assertEqual(dup.exception.code, "RESEARCH_POLICY_EXTENSION_SET_DUPLICATE_SCOPE")
            self.assertEqual(_rows(fresh), (1, 1))

    def test_a_legacy_scope_freeze_and_its_extension_share_one_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            legacy = "d4" * 32  # a pre-runtime scope: history but no snapshot
            proposal = rp.propose_run_extension(
                store, scope_key=legacy, parent_operation_sha256="e6" * 32, limits_delta={"main_total": 9}, has_history=True
            )
            result = rp.apply_run_extension_set(store, proposals=[proposal], confirm_append_only=True)
            self.assertEqual(result[0]["writes"], {"research_store": 2})
            self.assertEqual(rp.read_scope_snapshot(store, legacy)["source"], rp.SOURCE_LEGACY)
            self.assertEqual(rp.limits_for_frozen_run(store, legacy)["main_total"], 9)

ROOT_JOURNAL = "a1" * 32  # cycle 1's search key
CYCLE_JOURNAL = cycle_search_key(ROOT_JOURNAL, 2)  # cycle 2's own execution key


def _spend_main(store: ResearchStore, operation: dict, journal: str, count: int, *, prefix: str = "q") -> None:
    """Complete ``count`` MAIN looks of ``journal`` with durable result rows (what a real executed look leaves)."""

    from datetime import datetime, timezone

    from solana_alpha_lab.factory import hfic_grounded_discovery as gd

    for index in range(count):
        spec_sha = f"{prefix}{index:02d}".ljust(64, "0")
        gd._append_discovery_look(
            store,
            record_id=f"HFIC-ART-LOOK-{prefix}-{journal[:6]}-{index:02d}",
            journal_scope=journal,
            spec={"query_id": f"{prefix}-{index}"},
            spec_sha256=spec_sha,
            binding_sha="b" * 64,
            data_refs=[],
            digest=f"{prefix}{index:02d}".rjust(64, "1"),
            identity=f"{prefix}{journal[:8]}{index:02d}".ljust(32, "9"),
            summary={"query_id": f"{prefix}-{index}", "calculation_version": "x"},
            look={"look_class": "MAIN", "new_look": True},
            git_sha=GIT,
            clock=datetime(2026, 10, 7, tzinfo=timezone.utc),
            operation_sha256=str(operation["operation_sha256"]),
        )


def _cycle_two(store: ResearchStore, parent: dict, **overrides) -> dict:
    return _operation(
        store,
        journal=CYCLE_JOURNAL,
        text="cycle two",
        cycle_index=2,
        accounting_root=ROOT_JOURNAL,
        parent_operation_sha256=str(parent["operation_sha256"]),
        **overrides,
    )


class ContinuationAccountingTests(unittest.TestCase):
    """P1-A: a later AUTO cycle keeps its own execution identity but spends its lineage root's budget."""

    def _lineage(self, tmp: str):
        store = ResearchStore(Path(tmp))
        first = _operation(store, journal=ROOT_JOURNAL, text="cycle one")
        _spend_main(store, first, ROOT_JOURNAL, 6)
        return store, first

    def test_cycle_one_spent_main_6_of_6_so_cycle_two_starts_with_none_left(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            before = oo.journal_occupancy(store, ROOT_JOURNAL)["main"]
            self.assertEqual((before["limit"], before["completed"], before["remaining"]), (6, 6, 0))
            second = _cycle_two(store, first)
            self.assertNotEqual(second["operation_sha256"], first["operation_sha256"])  # its own execution identity
            self.assertEqual(second["accounting_root"], ROOT_JOURNAL)
            self.assertEqual(oo.accounting_root_of(store, CYCLE_JOURNAL), ROOT_JOURNAL)
            seen = oo.journal_occupancy(store, CYCLE_JOURNAL)["main"]
            self.assertEqual((seen["limit"], seen["completed"], seen["remaining"]), (6, 6, 0))
            self.assertEqual(oo.owner_allowance(store, second, "main"), 0)
            # Both views are one budget: the root sees the same lineage.
            self.assertEqual(oo.journal_occupancy(store, ROOT_JOURNAL)["main"], seen)
            # The linked cycle froze nothing of its own.
            self.assertIsNone(rp.read_scope_snapshot(store, CYCLE_JOURNAL))

    def test_allowing_a_second_auto_cycle_alone_opens_no_new_main_budget(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            epoch = rp.epoch_scope_key(MARKET)
            rp.ensure_scope_snapshot(store, epoch)
            pool = rp.propose_run_extension(
                store, scope_key=epoch, parent_operation_sha256=str(first["operation_sha256"]),
                limits_delta={"auto_cycles_per_market": 2},
            )
            rp.apply_run_extension_set(store, proposals=[pool], confirm_append_only=True, parent_guard=_guard(store))
            second = _cycle_two(store, first)
            self.assertEqual(oo.journal_occupancy(store, CYCLE_JOURNAL)["main"]["remaining"], 0)
            self.assertEqual(oo.owner_allowance(store, second, "main"), 0)

    def test_an_explicit_shared_total_of_10_leaves_4_for_the_second_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            second = _cycle_two(store, first)
            digest = str(second["operation_sha256"])
            # Extending from the cycle-2 operation raises the lineage root, not an empty journal of its own.
            proposal = rp.propose_run_extension(
                store, scope_key=str(second["accounting_root"]), parent_operation_sha256=digest, limits_delta={"main_total": 10}
            )
            rp.apply_run_extension_set(store, proposals=[proposal], confirm_append_only=True, parent_guard=_guard(store))
            seen = oo.journal_occupancy(store, CYCLE_JOURNAL)["main"]
            self.assertEqual((seen["limit"], seen["completed"], seen["remaining"]), (10, 6, 4))
            _spend_main(store, second, CYCLE_JOURNAL, 4, prefix="s")
            full = oo.journal_occupancy(store, ROOT_JOURNAL)["main"]
            self.assertEqual((full["completed"], full["remaining"]), (10, 0))
            self.assertEqual(oo.owner_allowance(store, second, "main"), 0)
            # A cycle-2 operation is guarded as a member of that lineage.
            self.assertEqual(_guard(store)({"parent_operation_sha256": digest, "scope_key": ROOT_JOURNAL}), None)

    def test_the_same_spec_in_both_cycles_is_one_look_not_two(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            second = _cycle_two(store, first)
            _spend_main(store, second, CYCLE_JOURNAL, 1, prefix="q")  # the identical spec ids q00 again
            main = oo.journal_occupancy(store, CYCLE_JOURNAL)["main"]
            self.assertEqual((main["completed"], main["remaining"]), (6, 0))

    def test_a_continuation_needs_its_root_a_live_parent_and_the_same_focus(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            with self.assertRaises(oo.OrdinaryOperationError) as missing:
                _operation(store, journal=CYCLE_JOURNAL, text="no root", cycle_index=2)
            self.assertEqual(missing.exception.code, "ORDINARY_OPERATION_ACCOUNTING_ROOT_REQUIRED")
            with self.assertRaises(oo.OrdinaryOperationError) as unknown:
                _operation(
                    store, journal=cycle_search_key("99" * 32, 2), text="unknown root", cycle_index=2, accounting_root="99" * 32,
                    parent_operation_sha256=str(first["operation_sha256"]),
                )
            self.assertEqual(unknown.exception.code, "ORDINARY_OPERATION_ACCOUNTING_ROOT_UNKNOWN")
            with self.assertRaises(oo.OrdinaryOperationError) as other_focus:
                _cycle_two(store, first, owner_focus="SOME_OTHER_FOCUS")
            self.assertEqual(other_focus.exception.code, "ORDINARY_OPERATION_LINEAGE_MISMATCH")

    def test_stopped_and_pending_parents_are_not_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            oo._reserve(store, first, spec_sha256="a9" * 32, look_class="preview")  # an unresolved reservation
            with self.assertRaises(oo.OrdinaryOperationError) as pending:
                _cycle_two(store, first)
            self.assertEqual(pending.exception.code, "EXTENSION_PARENT_HAS_PENDING_RESERVATION")

        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            preview = oo.preview_operation_stop(store, operation_sha256=str(first["operation_sha256"]), owner_request_text="stop")
            oo.apply_operation_stop(store, proposal=preview["proposal"], confirm_append_only=True)
            with self.assertRaises(oo.OrdinaryOperationError) as stopped:
                _cycle_two(store, first)
            self.assertEqual(stopped.exception.code, "ORDINARY_OPERATION_STOPPED")

    def test_a_forged_root_can_neither_borrow_nor_poison_a_budget(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, first = self._lineage(raw)
            other_root = "5a" * 32
            other_first = _operation(store, journal=other_root, text="another search")
            _spend_main(store, other_first, other_root, 1, prefix="z")
            # The journal is cycle 2 of ROOT, but the request names another valid root: refused, nothing stored.
            with self.assertRaises(oo.OrdinaryOperationError) as forged:
                _operation(
                    store, journal=CYCLE_JOURNAL, text="forged", cycle_index=2, accounting_root=other_root,
                    parent_operation_sha256=str(other_first["operation_sha256"]),
                )
            self.assertEqual(forged.exception.code, "ORDINARY_OPERATION_ACCOUNTING_ROOT_MISMATCH")
            self.assertEqual(oo.accounting_root_of(store, CYCLE_JOURNAL), CYCLE_JOURNAL)  # nothing poisoned
            second = _cycle_two(store, first)
            self.assertEqual(oo.accounting_root_of(store, CYCLE_JOURNAL), ROOT_JOURNAL)
            self.assertEqual(oo.journal_occupancy(store, CYCLE_JOURNAL)["main"]["completed"], 6)
            self.assertEqual(oo.journal_occupancy(store, other_root)["main"]["completed"], 1)  # no escape, no leak
            self.assertEqual(second["accounting_root"], ROOT_JOURNAL)

    def test_cycle_one_digests_are_unchanged_by_the_lineage_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            plain = _operation(store, journal=ROOT_JOURNAL, text="plain")
            self.assertNotIn("accounting_root", plain)
            self.assertNotIn("cycle_index", plain)
            self.assertEqual(oo.accounting_root_of(store, ROOT_JOURNAL), ROOT_JOURNAL)


class RepresentationContinuationOrderTests(unittest.TestCase):
    """Round 7: the derived root is stable for an idempotent re-request, and order cannot mint a second budget."""

    def test_the_root_is_stable_after_a_later_cycle_child_and_an_earlier_one_is_refused(self) -> None:
        from unittest import mock

        from solana_alpha_lab.factory import hfic_session

        focus, market = "OPPORTUNITY_EPISODES:AUTO", MARKET
        rep_id = "NORMALIZED_TRAJECTORY_EPISODES_V1"

        def row(journal: str, parent: str, recorded: str, **extra) -> dict:
            return {
                "journal_scope": journal, "owner_focus": focus, "market_evidence_epoch_sha256": market,
                "representation": {"representation_id": rep_id, "parent_session_id": parent},
                "_recorded_at": recorded, "status": "OPEN", **extra,
            }

        bundles = {
            "S1": {"owner_focus": focus}, "S1b": {"owner_focus": focus}, "S9": {"owner_focus": "OPPORTUNITY_EPISODES:OTHER"}, "S2": {"owner_focus": focus, "cycle_index": 2},
            "S3": {"owner_focus": focus, "cycle_index": 3},
        }
        c1 = row("11" * 32, "S1", "2026-10-07T01:00:00")
        c2 = row("22" * 32, "S2", "2026-10-07T02:00:00", accounting_root="11" * 32, lineage_kind=oo.REPRESENTATION_CONTINUATION)
        c3 = row("33" * 32, "S3", "2026-10-07T03:00:00", accounting_root="11" * 32, lineage_kind=oo.REPRESENTATION_CONTINUATION)

        def derive(parent: str, journal: str, existing: list) -> tuple:
            with mock.patch.object(oo, "list_operations", return_value=existing), mock.patch.object(
                hfic_session, "load_session_bundle", side_effect=lambda store, sid: bundles.get(sid)
            ), mock.patch.object(oo, "_unresolved_reservations", return_value=[]):
                return oo._representation_continuation_root(
                    object(), representation={"representation_id": rep_id, "parent_session_id": parent},
                    focus=focus, market=market, journal=journal,
                )

        # Cycle 2 continues cycle 1; after cycle 3 exists a re-request of cycle 2 derives the SAME root.
        self.assertEqual(derive("S2", c2["journal_scope"], [c1]), ("11" * 32, None))
        self.assertEqual(derive("S2", c2["journal_scope"], [c1, c2, c3]), ("11" * 32, None))
        # Cycle 3 with only a cycle-2 child plus the root continues the one root.
        self.assertEqual(derive("S3", c3["journal_scope"], [c2, c1]), ("11" * 32, None))
        # A SAME-cycle variant (another payload or selector under the cycle-1 parent) continues the same root.
        self.assertEqual(derive("S1", "55" * 32, [c1]), ("11" * 32, None))
        self.assertEqual(derive("S1", "55" * 32, [c1, c2]), ("11" * 32, None))
        # A cycle-1 child with no root at all arriving after a later cycle's child is refused (one budget).
        self.assertEqual(derive("S1", "44" * 32, [c2]), (None, "ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER"))
        # An UNLINKED later-cycle root (its cycle-2 child was recorded first, normal order is cycle 1 first) is never
        # taken as the root of a cycle-1 child: that child is refused, not given the later journal as its budget.
        c2_alone = row("22" * 32, "S2", "2026-10-07T02:00:00")
        self.assertEqual(derive("S1", "44" * 32, [c2_alone]), (None, "ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER"))
        # A journal that already carries an operation keeps the identity it was created with.
        self.assertEqual(derive("S1", c1["journal_scope"], [c1, c2]), (None, None))
        # Two historical unlinked roots are an ambiguous line: refused, never a fresh budget.
        c1b = row("77" * 32, "S1b", "2026-10-07T01:30:00")
        self.assertEqual(derive("S1", "66" * 32, [c1, c1b])[1], "ORDINARY_OPERATION_LINEAGE_AMBIGUOUS")
        # Another focus never joins the line.
        other_focus = row("88" * 32, "S9", "2026-10-07T00:30:00")
        other_focus["owner_focus"] = "OPPORTUNITY_EPISODES:OTHER"
        self.assertEqual(derive("S1", "99" * 32, [other_focus]), (None, None))


class LineageRaceUnderLeaseTests(unittest.TestCase):
    """Validator P1: the representation root is decided again under the ResearchStore writer lease."""

    FOCUS = "OPPORTUNITY_EPISODES:AUTO"
    REP = "NORMALIZED_TRAJECTORY_EPISODES_V1"

    def _request(self, journal: str, parent: str, text: str) -> dict:
        return {
            "owner_request_text": text, "owner_focus": self.FOCUS, "journal_scope": journal,
            "market_evidence_epoch_sha256": MARKET, "owner_cap": {"main": None, "adaptive": None, "preview": None},
            "requested_completion": oo.LIMITED_RESULT,
            "representation": {
                "representation_id": self.REP, "representation_semantic_version": "1.0", "parent_session_id": parent,
                "representation_payload_sha256": journal, "scope_applied_sha256": "ee" * 32,
            },
        }

    def _bundles(self):
        from unittest import mock

        from solana_alpha_lab.factory import hfic_session

        return mock.patch.object(hfic_session, "load_session_bundle", side_effect=lambda store, sid: {"owner_focus": self.FOCUS})

    def test_two_first_variants_racing_leave_exactly_one_root(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as raw, self._bundles():
            store = ResearchStore(Path(raw))
            first, second = "a7" * 32, "b8" * 32
            real_append = oo._append
            injected = {"done": False}

            def interleave(*args, **kwargs):
                # Process B has read "no root yet" and is about to commit; process A commits first.
                if not injected["done"] and kwargs.get("kind") == oo.OPERATION_KIND:
                    injected["done"] = True
                    oo.record_operation(store, self._request(first, "S1", "variant A"))
                return real_append(*args, **kwargs)

            with mock.patch.object(oo, "_append", side_effect=interleave):
                b = oo.record_operation(store, self._request(second, "S1", "variant B"))
            roots = [row for row in oo.list_operations(store) if isinstance(row.get("representation"), dict) and not row.get("accounting_root")]
            self.assertEqual([row["journal_scope"] for row in roots], [first])  # exactly one root
            self.assertEqual(b["accounting_root"], first)  # B was planned again and joined A's line
            self.assertEqual(oo.accounting_root_of(store, second), first)
            self.assertEqual(oo.journal_occupancy(store, second)["main"]["limit"], oo.journal_occupancy(store, first)["main"]["limit"])

    def test_a_stop_between_the_root_decision_and_the_commit_refuses_the_new_segment(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as raw, self._bundles():
            store = ResearchStore(Path(raw))
            first, second = "a7" * 32, "b8" * 32
            a = oo.record_operation(store, self._request(first, "S1", "variant A"))
            real_append = oo._append
            injected = {"done": False}

            def interleave(*args, **kwargs):
                if not injected["done"] and kwargs.get("kind") == oo.OPERATION_KIND:
                    injected["done"] = True
                    stop = oo.preview_operation_stop(store, operation_sha256=str(a["operation_sha256"]), owner_request_text="stop A")
                    oo.apply_operation_stop(store, proposal=stop["proposal"], confirm_append_only=True)
                return real_append(*args, **kwargs)

            with mock.patch.object(oo, "_append", side_effect=interleave):
                with self.assertRaises(oo.OrdinaryOperationError) as refused:
                    oo.record_operation(store, self._request(second, "S1", "variant B"))
            self.assertEqual(refused.exception.code, "ORDINARY_OPERATION_STOPPED")
            self.assertFalse([row for row in oo.list_operations(store) if row.get("journal_scope") == second])


if __name__ == "__main__":
    unittest.main()
