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


if __name__ == "__main__":
    unittest.main()
