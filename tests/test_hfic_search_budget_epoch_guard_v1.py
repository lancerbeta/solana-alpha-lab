"""HFIC search-budget accounting is per evidence epoch, not memory eligibility."""

from __future__ import annotations

import unittest

from solana_alpha_lab.factory.hfic_memory_policy import GENESIS_MEMORY_ELIGIBILITY_SHA256
from solana_alpha_lab.factory.hfic_preflight import (
    AUTO_SESSIONS_PER_EPOCH,
    MAX_DISTINCT_FOCUSES_PER_EPOCH,
    decide_preflight_action,
    epoch_search_budget_usage,
    focus_key_sha256,
    search_key_sha256,
)
from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION

EPOCH_A = "aa" * 32
EPOCH_B = "bb" * 32
MEM_Q1 = "11" * 32
MEM_Q2 = "22" * 32
MEM_Q3 = "33" * 32


def _session(
    *,
    session_id: str,
    epoch: str,
    owner_focus: str,
    memory_eligibility: str,
    state: str = "SYNTHESIS_COMPLETE",
) -> dict:
    focus_key = focus_key_sha256(owner_focus)
    return {
        "session_id": session_id,
        "session_state": state,
        "evidence_epoch_sha256": epoch,
        # A5 budget is stamp-only on market_evidence_epoch_sha256.
        "market_evidence_epoch_sha256": epoch,
        "owner_focus": owner_focus,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key_sha256(
            epoch, owner_focus, PROMPT_VERSION, memory_eligibility
        ),
        "memory_eligibility_sha256": memory_eligibility,
        "prompt_version": PROMPT_VERSION,
    }


class HficSearchBudgetEpochGuardTests(unittest.TestCase):
    def test_constants_match_canonical_contract(self) -> None:
        self.assertEqual(AUTO_SESSIONS_PER_EPOCH, 1)
        self.assertEqual(MAX_DISTINCT_FOCUSES_PER_EPOCH, 3)

    def test_changed_memory_eligibility_does_not_grant_second_auto(self) -> None:
        sessions = [
            _session(
                session_id="HFIC-SESS-AUTO1",
                epoch=EPOCH_A,
                owner_focus="AUTO",
                memory_eligibility=MEM_Q1,
            )
        ]
        action, terminal = decide_preflight_action(
            sessions,
            search_key=search_key_sha256(
                EPOCH_A, "AUTO", PROMPT_VERSION, MEM_Q2
            ),
            evidence_epoch=EPOCH_A,
            focus_key=focus_key_sha256("AUTO"),
            owner_focus="AUTO",
            memory_eligibility_sha256=MEM_Q2,
        )
        self.assertEqual(action, "STOP")
        self.assertEqual(terminal, "SEARCH_BUDGET_EXHAUSTED")
        usage = epoch_search_budget_usage(sessions, evidence_epoch=EPOCH_A)
        self.assertEqual(usage["auto_sessions_used"], 1)

    def test_child_representation_does_not_consume_second_auto_slot(self) -> None:
        base = _session(
            session_id="HFIC-SESS-AUTO-BASE",
            epoch=EPOCH_A,
            owner_focus="AUTO",
            memory_eligibility=MEM_Q1,
        )
        child = {
            **base,
            "session_id": "HFIC-SESS-AUTO-V1",
            "ladder_representation_id": "NORMALIZED_TRAJECTORY_V1",
            "representation_semantic_version": "1.0",
        }
        usage = epoch_search_budget_usage(
            [base, child], evidence_epoch=EPOCH_A
        )
        self.assertEqual(usage["auto_sessions_used"], 1)

    def test_three_distinct_focuses_across_eligibility_exhaust_epoch(self) -> None:
        focuses = ("FOCUS_ONE", "FOCUS_TWO", "FOCUS_THREE")
        sessions = [
            _session(
                session_id=f"HFIC-SESS-{idx}",
                epoch=EPOCH_A,
                owner_focus=focus,
                memory_eligibility=mem,
            )
            for idx, (focus, mem) in enumerate(
                zip(focuses, (MEM_Q1, MEM_Q2, MEM_Q3), strict=True), start=1
            )
        ]
        action, terminal = decide_preflight_action(
            sessions,
            search_key=search_key_sha256(
                EPOCH_A, "FOCUS_FOUR", PROMPT_VERSION, GENESIS_MEMORY_ELIGIBILITY_SHA256
            ),
            evidence_epoch=EPOCH_A,
            focus_key=focus_key_sha256("FOCUS_FOUR"),
            owner_focus="FOCUS_FOUR",
            memory_eligibility_sha256=GENESIS_MEMORY_ELIGIBILITY_SHA256,
        )
        self.assertEqual(action, "STOP")
        self.assertEqual(terminal, "SEARCH_BUDGET_EXHAUSTED")
        usage = epoch_search_budget_usage(sessions, evidence_epoch=EPOCH_A)
        self.assertEqual(usage["distinct_focus_used"], 3)
        self.assertEqual(usage["distinct_focus_remaining"], 0)

    def test_exact_search_identity_returns_existing_session(self) -> None:
        session = _session(
            session_id="HFIC-SESS-EXACT",
            epoch=EPOCH_A,
            owner_focus="IDENTIFIABLE_NOW",
            memory_eligibility=MEM_Q1,
        )
        action, sid = decide_preflight_action(
            [session],
            search_key=session["search_key_sha256"],
            evidence_epoch=EPOCH_A,
            focus_key=session["focus_key_sha256"],
            owner_focus="IDENTIFIABLE_NOW",
            memory_eligibility_sha256=MEM_Q1,
        )
        self.assertEqual(action, "RETURN_EXISTING_SESSION")
        self.assertEqual(sid, "HFIC-SESS-EXACT")

    def test_same_focus_new_eligibility_keeps_identity_but_counts_epoch_budget(
        self,
    ) -> None:
        existing = _session(
            session_id="HFIC-SESS-FOCUS-OLD-MEM",
            epoch=EPOCH_A,
            owner_focus="IDENTIFIABLE_NOW",
            memory_eligibility=MEM_Q1,
        )
        # New eligibility => new search identity; same focus_key still counts in budget.
        action, sid = decide_preflight_action(
            [existing],
            search_key=search_key_sha256(
                EPOCH_A, "IDENTIFIABLE_NOW", PROMPT_VERSION, MEM_Q2
            ),
            evidence_epoch=EPOCH_A,
            focus_key=focus_key_sha256("IDENTIFIABLE_NOW"),
            owner_focus="IDENTIFIABLE_NOW",
            memory_eligibility_sha256=MEM_Q2,
        )
        # same_focus requires matching memory eligibility, so not RETURN via same_focus;
        # exact search_key also differs. Focus key already present in epoch budget →
        # START_NEW_SESSION still allowed (same focus does not consume an extra slot).
        self.assertEqual(action, "START_NEW_SESSION")
        self.assertIsNone(sid)
        usage = epoch_search_budget_usage([existing], evidence_epoch=EPOCH_A)
        self.assertEqual(usage["distinct_focus_used"], 1)
        self.assertEqual(usage["distinct_focus_remaining"], 2)

        # Fill remaining two distinct keys under other eligibility values.
        peers = [
            _session(
                session_id="HFIC-SESS-F2",
                epoch=EPOCH_A,
                owner_focus="FOCUS_TWO",
                memory_eligibility=MEM_Q2,
            ),
            _session(
                session_id="HFIC-SESS-F3",
                epoch=EPOCH_A,
                owner_focus="FOCUS_THREE",
                memory_eligibility=MEM_Q3,
            ),
        ]
        exhausted, terminal = decide_preflight_action(
            [existing, *peers],
            search_key=search_key_sha256(
                EPOCH_A, "FOCUS_FOUR", PROMPT_VERSION, MEM_Q1
            ),
            evidence_epoch=EPOCH_A,
            focus_key=focus_key_sha256("FOCUS_FOUR"),
            owner_focus="FOCUS_FOUR",
            memory_eligibility_sha256=MEM_Q1,
        )
        self.assertEqual(exhausted, "STOP")
        self.assertEqual(terminal, "SEARCH_BUDGET_EXHAUSTED")

    def test_new_evidence_epoch_starts_fresh_budget(self) -> None:
        prior = [
            _session(
                session_id=f"HFIC-SESS-OLD-{idx}",
                epoch=EPOCH_A,
                owner_focus=focus,
                memory_eligibility=MEM_Q1,
            )
            for idx, focus in enumerate(
                ("FOCUS_ONE", "FOCUS_TWO", "FOCUS_THREE"), start=1
            )
        ]
        action, sid = decide_preflight_action(
            prior,
            search_key=search_key_sha256(
                EPOCH_B, "AUTO", PROMPT_VERSION, MEM_Q1
            ),
            evidence_epoch=EPOCH_B,
            focus_key=focus_key_sha256("AUTO"),
            owner_focus="AUTO",
            memory_eligibility_sha256=MEM_Q1,
        )
        self.assertEqual(action, "START_NEW_SESSION")
        self.assertIsNone(sid)
        usage = epoch_search_budget_usage(prior, evidence_epoch=EPOCH_B)
        self.assertEqual(usage["auto_sessions_used"], 0)
        self.assertEqual(usage["distinct_focus_used"], 0)

    def test_other_epoch_session_does_not_consume_current_budget(self) -> None:
        other_epoch = _session(
            session_id="HFIC-SESS-DEFECT-OTHER-EPOCH",
            epoch=EPOCH_B,
            owner_focus="AUTO",
            memory_eligibility=MEM_Q1,
        )
        action, sid = decide_preflight_action(
            [other_epoch],
            search_key=search_key_sha256(
                EPOCH_A, "AUTO", PROMPT_VERSION, MEM_Q1
            ),
            evidence_epoch=EPOCH_A,
            focus_key=focus_key_sha256("AUTO"),
            owner_focus="AUTO",
            memory_eligibility_sha256=MEM_Q1,
        )
        self.assertEqual(action, "START_NEW_SESSION")
        usage = epoch_search_budget_usage([other_epoch], evidence_epoch=EPOCH_A)
        self.assertEqual(usage["auto_sessions_used"], 0)
        self.assertEqual(usage["distinct_focus_used"], 0)


class ResearchPolicyRaisedAutoBudgetTests(unittest.TestCase):
    """AUTO 1->2 through the production admission path (representation BASE).

    A raised cap never starts a cycle by itself. A second AUTO cycle is a
    separate, explicitly requested slot of the same market; the pool that caps
    it is frozen per market epoch, not per journal.
    """

    @staticmethod
    def _row(session_id: str, *, cycle: int = 1, state: str = "SYNTHESIS_COMPLETE", seq: int = 3, **extra) -> dict:
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256

        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=EPOCH_A,
            representation_id="BASE",
            representation_semantic_version=PROMPT_VERSION,
            owner_focus="AUTO",
            cycle_index=cycle,
        )
        row = {
            "session_id": session_id,
            "session_state": state,
            "owner_focus": "AUTO",
            "focus_key_sha256": focus_key_sha256("AUTO"),
            "market_evidence_epoch_sha256": EPOCH_A,
            "evidence_epoch_sha256": EPOCH_A,
            "scientific_slot_sha256": slot,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": PROMPT_VERSION,
            "hfic_cycle_seq": seq,
            "effective_at": f"2026-10-0{cycle}T00:00:00Z",
            "record_id": session_id,
            "search_key_sha256": search_key_sha256(EPOCH_A, "AUTO", PROMPT_VERSION, MEM_Q1),
        }
        if cycle > 1:
            row["cycle_index"] = cycle
        row.update(extra)
        return row

    @staticmethod
    def _admit(rows, **kwargs) -> dict:
        from pathlib import Path

        from solana_alpha_lab.factory.hfic_evidence_identity import resolve_scientific_admission

        root = Path(__file__).resolve().parents[1]
        return resolve_scientific_admission(
            rows,
            market_evidence_epoch=EPOCH_A,
            representation_id="BASE",
            representation_semantic_version=PROMPT_VERSION,
            owner_focus="AUTO",
            repo_root=root,
            **kwargs,
        )

    def test_a_plain_repeat_never_starts_a_second_cycle_at_any_cap(self) -> None:
        for cap in (1, 2, 8):
            admission = self._admit([self._row("S1")], auto_sessions_per_market=cap)
            self.assertEqual(admission["action"], "RETURN_EXISTING_SESSION", cap)

    def test_explicit_additional_cycle_is_denied_at_cap_1_started_at_cap_2_and_third_is_denied(self) -> None:
        first = self._row("S1")
        denied = self._admit([first], auto_sessions_per_market=1, additional_cycle=True)
        self.assertEqual((denied["action"], denied["reason_code"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))
        started = self._admit([first], auto_sessions_per_market=2, additional_cycle=True)
        self.assertEqual(started["action"], "START_NEW_SESSION")
        self.assertEqual(started["cycle_index"], 2)
        self.assertEqual(started["reason_code"], "ADDITIONAL_CYCLE_AUTHORIZED")
        # Cycle 2 has its own scientific slot; cycle 1 keeps the unchanged V1 slot hash.
        self.assertNotEqual(started["scientific_slot_sha256"], first["scientific_slot_sha256"])
        second = self._row("S2", cycle=2)
        third = self._admit([first, second], auto_sessions_per_market=2, additional_cycle=True)
        self.assertEqual((third["action"], third["reason_code"]), ("STOP", "SEARCH_BUDGET_EXHAUSTED"))

    def test_a_pending_additional_cycle_resumes_and_does_not_open_a_third(self) -> None:
        rows = [self._row("S1"), self._row("S2", cycle=2, state="FROZEN_AWAITING_CRITIC", seq=1)]
        resumed = self._admit(rows, auto_sessions_per_market=8, additional_cycle=True)
        self.assertEqual((resumed["action"], resumed["session_id"]), ("RESUME_EXISTING_SESSION", "S2"))
        exact = self._admit(rows, auto_sessions_per_market=8, requested_cycle_index=2)
        self.assertEqual((exact["action"], exact["session_id"]), ("RESUME_EXISTING_SESSION", "S2"))

    def test_a_child_representation_row_is_not_a_second_cycle(self) -> None:
        child = self._row(
            "S1-CHILD",
            ladder_representation_id="NORMALIZED_TRAJECTORY_V1",
            representation_semantic_version="1.0",
        )
        child.pop("scientific_slot_sha256")
        admission = self._admit([self._row("S1"), child], auto_sessions_per_market=2, additional_cycle=True)
        self.assertEqual(admission["action"], "START_NEW_SESSION")
        self.assertEqual(admission["cycle_index"], 2)

    def test_an_episode_representation_of_cycle_two_climbs_the_ladder_and_is_not_a_third_auto(self) -> None:
        from pathlib import Path

        from solana_alpha_lab.factory.hfic_evidence_identity import resolve_scientific_admission
        from solana_alpha_lab.factory.hfic_representation_ladder import load_ladder_registry

        root = Path(__file__).resolve().parents[1]
        episodes = next(
            row for row in load_ladder_registry(root / "configs" / "hfic_representation_ladder_v1.yaml")["representations"]
            if row["id"] == "NORMALIZED_TRAJECTORY_EPISODES_V1"
        )
        base = [self._row("S1"), self._row("S2", cycle=2)]
        episode = resolve_scientific_admission(
            base,
            market_evidence_epoch=EPOCH_A,
            representation_id="NORMALIZED_TRAJECTORY_EPISODES_V1",
            representation_semantic_version=str(episodes["version"]),
            owner_focus="AUTO",
            auto_sessions_per_market=2,
            repo_root=root,
        )
        self.assertEqual(episode["action"], "START_NEW_SESSION", episode)
        self.assertNotEqual(episode.get("reason_code"), "SEARCH_BUDGET_EXHAUSTED")
        # Its slot is its own: neither BASE cycle's slot, and not an AUTO cycle of its own.
        self.assertNotIn(episode["scientific_slot_sha256"], {row["scientific_slot_sha256"] for row in base})
        self.assertEqual(self._admit(base, auto_sessions_per_market=2, additional_cycle=True)["reason_code"], "SEARCH_BUDGET_EXHAUSTED")

    def test_an_additional_cycle_without_a_prior_cycle_is_refused(self) -> None:
        admission = self._admit([], auto_sessions_per_market=8, requested_cycle_index=2)
        self.assertEqual(admission["reason_code"], "ADDITIONAL_CYCLE_WITHOUT_PRIOR_CYCLE")

    def test_the_cap_comes_from_the_epoch_pool_and_only_an_epoch_extension_raises_it(self) -> None:
        import tempfile
        from pathlib import Path

        from solana_alpha_lab.factory import hfic_research_policy as rp
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            pool = rp.epoch_scope_key(EPOCH_A)
            frozen = rp.ensure_scope_snapshot(store, pool)
            self.assertEqual(frozen["limits"]["auto_cycles_per_market"], 1)
            preview = rp.preview_policy_change(store, limits_delta={"auto_cycles_per_market": 2})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            cap = rp.epoch_limits(store, EPOCH_A)["auto_cycles_per_market"]
            self.assertEqual(cap, 1)
            denied = self._admit([self._row("S1")], auto_sessions_per_market=cap, additional_cycle=True)
            self.assertEqual(denied["action"], "STOP")
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.propose_run_extension(
                    store, scope_key=pool, parent_operation_sha256="7" * 64, limits_delta={"main_total": 10}
                )
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_FIELD_NOT_IN_SCOPE")
            extension = rp.propose_run_extension(
                store, scope_key=pool, parent_operation_sha256="7" * 64, limits_delta={"auto_cycles_per_market": 2}
            )
            rp.apply_run_extension(store, proposal=extension, confirm_append_only=True)
            cap = rp.epoch_limits(store, EPOCH_A)["auto_cycles_per_market"]
            self.assertEqual(cap, 2)
            started = self._admit([self._row("S1")], auto_sessions_per_market=cap, additional_cycle=True)
            self.assertEqual((started["action"], started["cycle_index"]), ("START_NEW_SESSION", 2))
            third = self._admit(
                [self._row("S1"), self._row("S2", cycle=2)], auto_sessions_per_market=cap, additional_cycle=True
            )
            self.assertEqual(third["action"], "STOP")

    def test_a_new_epoch_freezes_at_the_active_policy_and_an_epoch_with_history_at_the_defaults(self) -> None:
        import tempfile
        from pathlib import Path

        from solana_alpha_lab.factory import hfic_research_policy as rp
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"auto_cycles_per_market": 2})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            fresh = rp.ensure_scope_snapshot(store, rp.epoch_scope_key(EPOCH_B), has_history=False)
            self.assertEqual(fresh["limits"]["auto_cycles_per_market"], 2)
            legacy = rp.ensure_scope_snapshot(store, rp.epoch_scope_key(EPOCH_A), has_history=True)
            self.assertEqual(legacy["limits"]["auto_cycles_per_market"], 1)
            self.assertEqual(legacy["source"], rp.SOURCE_LEGACY)

    def test_the_read_only_pool_resolver_writes_nothing_and_reports_the_first_touch_value(self) -> None:
        import tempfile
        from pathlib import Path

        from solana_alpha_lab.factory import hfic_research_policy as rp
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"auto_cycles_per_market": 2})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            before = store.diagnostics().committed_inventory_sha256
            self.assertEqual(rp.pool_limits_read_only(store, EPOCH_B, [])["auto_cycles_per_market"], 2)
            self.assertEqual(rp.pool_limits_read_only(store, EPOCH_A, [self._row("S1")])["auto_cycles_per_market"], 1)
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)


if __name__ == "__main__":
    unittest.main()
