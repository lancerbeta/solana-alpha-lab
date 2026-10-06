"""NORMALIZED_TRAJECTORY_EPISODES_V1 (PRD section 9): literal motifs on real episode points.

Expected strings are written by hand from the transition rule, not produced by the
module under test. Legacy NORMALIZED_TRAJECTORY_V1 is covered by its own golden tests
and is not touched by this representation.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import hfic_research_scope as rs  # noqa: E402
from solana_alpha_lab.factory import normalized_trajectory_episodes_v1 as nt  # noqa: E402
from tests.test_hfic_list_scope_executor_v1 import ALIASES, evidence  # noqa: E402
from tests.test_opportunity_episodes_contract_v1 import (  # noqa: E402
    COHORT,
    HOLD,
    LIQ,
    PRICE,
    RELEASE,
    binding_item,
    obs_row,
)

T0 = "2026-10-05T00:02:10Z"
AVAILABLE = {"E300": "2026-10-05T00:10:04Z", "E900": "2026-10-05T00:20:04Z", "E1800": "2026-10-05T00:35:09Z", "E14400": "2026-10-05T04:05:08Z"}
# episode -> (price, liquidity, holders) at E300,E900,E1800 ; None drops the point (missing)
PREFIX = {
    "e1": ((1.0, 0.99, 1.0), (12000, 12000, 13000), (60, 68, 75)),  # P:DU|L:FU|H:UU
    "e2": ((1.0, 1.01, 1.0), (12000, 12000, 12000), (60, 57, 55)),  # P:UD|L:FF|H:DD
    "e3": ((1.0, 0.99, 1.0), (12000, 12000, 13000), (60, 68, 75)),  # P:DU|L:FU|H:UU
    "e4": ((1.0, None, 1.0), (12000, 12000, 12000), (60, 60, 60)),  # P:MM|L:FF|H:FF  (E900 price missing)
    "e5": ((1.0, 1.0, 1.0), (12000, 0, 12000), (60, 61, 60)),  # P:FF|L:MM (non-positive)|H:UD
    "e6": ((1.0, 1.01, 1.0), (12000, 12000, 12000), (60, 57, 55)),  # P:UD|L:FF|H:DD
    "e7": ((1.0, 0.99, 1.0), (12000, 12000, 13000), (60, 68, 75)),  # P:DU|L:FU|H:UU
}
LISTS = {"e1": "A", "e2": "B", "e3": "C", "e4": "AB", "e5": "AC", "e6": "BC", "e7": "ABC"}


def corpus(*, target_price=7.77):
    census, rows = [], []
    for episode, (price, liq, holders) in PREFIX.items():
        mint = f"Mint{episode}".ljust(40, "x")
        census.append({"cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "t0": T0})
        for index, point in enumerate(("E300", "E900", "E1800")):
            for field, series in ((PRICE, price), (LIQ, liq), (HOLD, holders)):
                value = series[index]
                if value is None:
                    rows.append(obs_row(episode, mint, point, field, None, available=AVAILABLE[point], state="MISSING_TYPED"))
                else:
                    rows.append(obs_row(episode, mint, point, field, value, available=AVAILABLE[point]))
        for field in (PRICE, LIQ, HOLD):
            rows.append(obs_row(episode, mint, "E14400", field, target_price, available=AVAILABLE["E14400"]))
    return census, rows


def scope_for(selector=None, condition=None):
    ev = evidence()
    for episode, letters in LISTS.items():
        ev.states[episode] = {"JUPITER:toporganicscore:5m": rs.TRUE if "A" in letters else rs.FALSE,
                              "JUPITER:toptraded:5m": rs.TRUE if "B" in letters else rs.FALSE,
                              "JUPITER:toptrending:5m": rs.TRUE if "C" in letters else rs.FALSE}
    scope = rs.canonical_scope({"universe_selector": selector} if selector else {}, ev, aliases=ALIASES)
    cond = rs.canonical_list_condition(condition, ev, aliases=ALIASES) if condition else None
    return rs.ResolvedScope(scope=scope, list_condition=cond, evidence=ev, episode_ids=list(PREFIX))


class TransitionRuleTests(unittest.TestCase):
    def test_symbols(self) -> None:
        f = lambda a, b, positive=True: nt.transition_symbol(a, b, positive_required=positive)  # noqa: E731
        self.assertEqual(f(1.0, 2.0), "U")
        self.assertEqual(f(2.0, 1.0), "D")
        self.assertEqual(f(2.0, 2.0), "F")
        self.assertEqual(f(None, 2.0), "M")
        self.assertEqual(f(1.0, None), "M")
        self.assertEqual(f(0.0, 1.0), "M")  # log-ratio needs positive values
        self.assertEqual(f(-1.0, 1.0), "M")
        self.assertEqual(f(float("nan"), 1.0), "M")
        self.assertEqual(f(0.0, 5.0, positive=False), "U")  # holder counts may be zero

    def test_panel_never_drops_members_silently(self) -> None:
        motifs = [f"P:{a}{b}|L:FF|H:FF" for a in "UDFM" for b in "UDFM"]  # 16 distinct, 1 each
        panel = nt._panel(motifs + ["P:UU|L:FF|H:FF"] * 3)
        self.assertEqual(panel["members_n"], 19)
        self.assertEqual(len(panel["motifs"]), 8)
        self.assertEqual(panel["motifs"][0], {"motif": "P:UU|L:FF|H:FF", "n": 4})
        self.assertEqual(sum(item["n"] for item in panel["motifs"]) + panel["omitted_member_n"], 19)
        self.assertEqual(panel["omitted_motif_n"], 8)
        self.assertGreater(panel["missing_heavy_member_n"], 0)


class ProfileTests(unittest.TestCase):
    def test_literal_motifs_pooled_scope(self) -> None:
        census, rows = corpus()
        payload = nt.build_episode_normalized_profile(census, rows, [binding_item()], scope_for())
        panel = payload["panels"]["BASE"]
        by = {item["motif"]: item["n"] for item in panel["motifs"]}
        self.assertEqual(by, {
            "P:DU|L:FU|H:UU": 3,
            "P:UD|L:FF|H:DD": 2,
            "P:MM|L:FF|H:FF": 1,
            "P:FF|L:MM|H:UD": 1,
        })
        self.assertEqual(panel["members_n"], 7)
        self.assertEqual(panel["missing_heavy_member_n"], 2)
        self.assertEqual(payload["scope_counts"]["admitted_in_scope_n"], 7)
        self.assertEqual(payload["representation_id"], "NORMALIZED_TRAJECTORY_EPISODES_V1")
        self.assertEqual(payload["decision_point"], "E1800")
        self.assertEqual(len(payload["representation_payload_sha256"]), 64)

    def test_scope_is_applied_before_aggregation(self) -> None:
        census, rows = corpus()
        ac = {"clauses": [{"all_of": ["A", "C"]}]}
        payload = nt.build_episode_normalized_profile(census, rows, [binding_item()], scope_for(selector=ac))
        by = {item["motif"]: item["n"] for item in payload["panels"]["BASE"]["motifs"]}
        # only e5 (A and C) and e7 (A, B and C) are in scope
        self.assertEqual(by, {"P:FF|L:MM|H:UD": 1, "P:DU|L:FU|H:UU": 1})
        self.assertEqual(payload["scope_counts"]["admitted_in_scope_n"], 2)
        self.assertEqual(payload["research_scope_rule_sha256"], scope_for(selector=ac).rule_sha256)
        self.assertNotEqual(payload["research_scope_rule_sha256"], scope_for().rule_sha256)

    def test_signal_and_comparator_panels(self) -> None:
        census, rows = corpus()
        payload = nt.build_episode_normalized_profile(
            census, rows, [binding_item()], scope_for(condition={"clauses": [{"all_of": ["A", "C"]}]})
        )
        signal = {item["motif"]: item["n"] for item in payload["panels"]["SIGNAL"]["motifs"]}
        comparator = {item["motif"]: item["n"] for item in payload["panels"]["COMPARATOR"]["motifs"]}
        self.assertEqual(signal, {"P:FF|L:MM|H:UD": 1, "P:DU|L:FU|H:UU": 1})
        self.assertEqual(sum(comparator.values()), 5)
        self.assertEqual(payload["panels"]["BASE"]["members_n"], 7)

    def test_prefix_only_no_target_no_identity(self) -> None:
        census, rows = corpus(target_price=7.77)
        payload = nt.build_episode_normalized_profile(census, rows, [binding_item()], scope_for())
        text = json.dumps(payload)
        self.assertNotIn("7.77", text)
        self.assertNotIn("Mint", text)
        self.assertNotIn("e1\"", text)
        self.assertFalse(payload["motif_is_executable_feature"])
        self.assertEqual(payload["values_exposed"], "PREFIX_POINTS_AT_OR_BEFORE_DECISION_NO_TARGET")

    def test_repeated_mint_episodes_are_separate_members(self) -> None:
        census, rows = corpus()
        census = [dict(row, mint="SameMint".ljust(40, "z")) for row in census]
        rows = [dict(row, mint="SameMint".ljust(40, "z")) for row in rows]
        payload = nt.build_episode_normalized_profile(census, rows, [binding_item()], scope_for())
        self.assertEqual(payload["panels"]["BASE"]["members_n"], 7)

    def test_unscoped_input_is_refused(self) -> None:
        census, rows = corpus()
        with self.assertRaises(nt.EpisodeProfileError) as caught:
            nt.build_episode_normalized_profile(census, rows, [binding_item()], None)
        self.assertEqual(caught.exception.code, "RESEARCH_SCOPE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
