from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_identity import (  # noqa: E402
    HficIdentityError,
    assign_portfolio_ids,
    candidate_identity,
    canonical_candidate_definition,
)


def candidate_card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "display_ordinal": 1,
        "label": "early-cohort-pathrisk",
        "claim": "Linked early cohort supply share raises H900 MEU.",
        "mechanism": "Synchronized unwind across linked wallets.",
        "actor_counterparty": "linked early-wallet cohort vs later buyers",
        "population": "ICP-EARLY-PUMPFUN-V1 age 300-899s",
        "decision_timestamp": "frozen T+5",
        "primary_x_family": "CORROBORATED_EARLY_COHORT_SUPPLY_SHARE",
        "primary_y": "MARKET_EXECUTION_UNAVAILABLE",
        "horizon_notional": "H900 / 0.01 SOL quote-only reverse sell",
        "negative_control": "service-signer-only links",
        "cheapest_falsifier": "fail TASK-24 reactivation floors before collection",
    }
    card.update(overrides)
    return card


class HficIdentityTests(unittest.TestCase):
    def test_identity_stable_across_ordinal_whitespace_and_order(self) -> None:
        first = candidate_identity(candidate_card())
        shuffled = candidate_identity(
            candidate_card(
                display_ordinal=9,
                label="  Early-Cohort-PathRisk  ",
                claim="  Linked early cohort supply share raises H900 MEU. ",
            )
        )
        self.assertEqual(first.full_sha256, shuffled.full_sha256)
        self.assertEqual(first.candidate_id, shuffled.candidate_id)
        self.assertTrue(first.candidate_id.startswith("HFIC-CAND-"))
        self.assertNotIn("C1", first.candidate_id)

    def test_material_mechanism_change_changes_full_hash(self) -> None:
        original = candidate_identity(candidate_card())
        changed = candidate_identity(
            candidate_card(mechanism="Creator-linked native outflow before T+5.")
        )
        self.assertNotEqual(original.full_sha256, changed.full_sha256)
        self.assertNotEqual(original.candidate_id, changed.candidate_id)

    def test_timestamp_and_model_are_not_identity_inputs(self) -> None:
        definition = canonical_candidate_definition(
            candidate_card(generated_at="2026-08-26T13:50:11Z", model="unused")
        )
        self.assertNotIn("generated_at", definition)
        self.assertNotIn("model", definition)
        self.assertNotIn("display_ordinal", definition)
        self.assertNotIn("label", definition)

    def test_duplicate_full_definitions_are_rejected(self) -> None:
        cards = [candidate_card(display_ordinal=1), candidate_card(display_ordinal=2)]
        with self.assertRaises(HficIdentityError) as raised:
            assign_portfolio_ids(cards)
        self.assertEqual(str(raised.exception), "DUPLICATE_CANDIDATE_DEFINITION")

    def test_prefix_collision_expands_deterministically(self) -> None:
        first = candidate_identity(candidate_card())
        colliding = candidate_identity(
            candidate_card(mechanism="Different mechanism, forced prefix collision.")
        )
        self.assertNotEqual(first.full_sha256, colliding.full_sha256)
        assigned = assign_portfolio_ids(
            [
                candidate_card(display_ordinal=1),
                candidate_card(
                    display_ordinal=2,
                    mechanism="Different mechanism, forced prefix collision.",
                    claim="Different claim for collision handling.",
                    actor_counterparty="creator vs LPs",
                    primary_x_family="CREATOR_LINKED_OUTFLOW",
                ),
            ]
        )
        ids = [item.candidate_id for item in assigned]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item.startswith("HFIC-CAND-") for item in ids))

    def test_live_git_sha_does_not_enter_identity(self) -> None:
        with_head = candidate_identity(candidate_card(live_git_head="a" * 40))
        without_head = candidate_identity(candidate_card())
        self.assertEqual(with_head.full_sha256, without_head.full_sha256)
        copied = copy.deepcopy(canonical_candidate_definition(candidate_card()))
        self.assertNotIn("live_git_head", copied)
