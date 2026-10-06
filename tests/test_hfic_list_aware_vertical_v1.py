"""List-aware Forge vertical (PRD V2, D01-D24 subset) on production owners.

Only transport, clock and authored market bytes are synthetic. Registration,
activation, ticks, admission, frames, export, release, import, preflight,
scope resolution, discovery and every artifact in between are production
owners. Expected numbers are literals from the PRD fixture (section 17.1).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from tests.test_opportunity_episodes_vertical_v1 import (  # noqa: E402
    AS_OF,
    DAY_A,
    DAY_B,
    END,
    STOPS,
    _consume,
    _discovery,
    _forge_call,
)

PRICE, LIQ, HOLD = "FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001", "FIELD-HOLDER-COUNT-001"
CATEGORY = {"A": "toporganicscore", "B": "toptraded", "C": "toptrending"}
LIST_ID = {"A": "JUPITER:toporganicscore:5m", "B": "JUPITER:toptraded:5m", "C": "JUPITER:toptrending:5m"}
# label -> (lists, numeric signal, target return or None)  [PRD 17.1]
COHORT_A = {
    "e1": ("A", True, 0.10),
    "e2": ("B", False, -0.20),
    "e3": ("C", True, 0.30),
    "e4": ("AB", True, 0.40),
    "e5": ("AC", False, -0.10),
    "e6": ("BC", True, None),
    "e7": ("ABC", True, 0.20),
}
# next weekly cycle: e1 re-enters but only in C; its old A membership must not be inherited.
COHORT_B = {
    "e1": ("C", True, 0.05),
    "n1": ("AC", True, 0.30),
    "n2": ("B", True, -0.10),
}


def mint_of(label: str) -> str:
    from tests.test_opportunity_episodes_harness_v1 import synth_mint

    return synth_mint(f"LAV{label}x")


def rounds() -> list[tuple[str, str, datetime, tuple[str, bool, float | None]]]:
    out = []
    for index, (label, spec) in enumerate(COHORT_A.items()):
        out.append(("A", label, DAY_A + timedelta(minutes=15 * index), spec))
    for index, (label, spec) in enumerate(COHORT_B.items()):
        out.append(("B", label, DAY_B + timedelta(minutes=15 * index), spec))
    return out


def market_row(mint: str, now: datetime, start: datetime, signal: bool, target: float | None):
    from tests.test_opportunity_episodes_harness_v1 import token_object

    offset = (now - start).total_seconds()
    if offset < 1500:
        price, holders = 1.0, 60
    elif offset < 10000:
        price, holders = 1.0, (75 if signal else 55)
    else:
        if target is None:
            return None  # the mint vanishes before the exit: a gap, never a zero
        price, holders = 1.0 + target, 80
    return token_object(mint, price=price, liquidity=12000, holders=holders)


def build_market():
    from tests.test_opportunity_episodes_harness_v1 import SyntheticMarket, token_object

    market = SyntheticMarket()
    entries: dict[str, list[tuple[datetime, bool, float | None]]] = {}
    for _cohort, label, start, (lists, signal, target) in rounds():
        mint = mint_of(label)
        body = {CATEGORY[x]: [] for x in "ABC"}
        for letter in lists:
            body[CATEGORY[letter]].append(token_object(mint, price=1.0, liquidity=12000, holders=60))
        market.nominations[start] = body
        entries.setdefault(mint, []).append((start, signal, target))
    for mint, items in entries.items():
        items.sort()

        def series(now, items=items, mint=mint):
            latest = [item for item in items if item[0] <= now]
            if not latest:
                return None
            start, signal, target = latest[-1]
            return market_row(mint, now, start, signal, target)

        market.series[mint] = series
    return market


def tick_times() -> list[datetime]:
    times: set[datetime] = set()
    for _cohort, _label, start, _spec in rounds():
        times.add(start + timedelta(seconds=5))
        for offset in (300, 1800, 14400):
            times.add(start + timedelta(seconds=offset + 300 + 5))
    cursor = DAY_A + timedelta(hours=12, seconds=5)
    while cursor < END:
        times.add(cursor)
        cursor += timedelta(hours=12)
    times.add(END)
    return sorted(times)


def capture(work: Path) -> tuple[Path, list[str]]:
    from solana_alpha_lab.factory.live_cohort_vanilla_path import capture_freeze_export
    from tests.test_opportunity_episodes_harness_v1 import (
        build_schedule,
        cli_tick,
        register_authorize_activate,
        synth_mint,
        write_assignment,
    )
    from solana_alpha_lab.factory.research_store import ResearchStore

    data_root = work / "capture" / "rdp"
    data_root.mkdir(parents=True)
    assignment = write_assignment(
        data_root,
        [{"identity_kind": "MINT", "identity": synth_mint("KnownProtected"), "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}],
    )
    schedule = build_schedule(starts_at=DAY_A, stops_at=STOPS, assignment=assignment)
    register_authorize_activate(data_root, schedule, now=DAY_A)
    ResearchStore(data_root).prepare_write_lookup()
    market = build_market()
    for at in tick_times():
        result = cli_tick(data_root, market, at)
        if result.get("terminal") == "TICK_REFUSED_NO_LIVE_DEFAULT":
            break
        if result.get("_exit_code") != 0:
            raise AssertionError(f"tick failed at {at}: {result}")
    imported: set[str] = set()
    packets = []
    for index in range(2):
        packet = capture_freeze_export(
            observation_rdp=data_root,
            ops_store=data_root / "observation_schedule_state.sqlite",
            imported_cohort_ids=set(imported),
            as_of=AS_OF,
            collection="OPPORTUNITY_EPISODES",
        )
        path = work / "capture" / f"packet-{index}.json"
        path.write_text(json.dumps(packet, default=str), encoding="utf-8")
        packets.append(str(path))
        imported.add(str(packet["cohort_id"]))
    return data_root, packets


def draft(kind: str, **parts: Any) -> dict[str, Any]:
    body = {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.2",
        "query_id": f"LAV-{kind}",
        "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0",
        "time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1", "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT"},
        "search_tier": "COMPOUND_SCREEN",
        "budget_allocation": "COMPOUND_FIRST",
        "decision": {"point_id": "E1800"},
        "features": [],
        "all": [],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400", "field_id": PRICE},
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
        "hypothesis_kind": kind,
        "research_scope": {},
        # Display aliases only: the first-class identity is the definition.
        "list_aliases": {"A": LIST_ID["A"], "B": LIST_ID["B"], "C": LIST_ID["C"]},
    }
    body.update(parts)
    return body


NUMERIC = {
    "features": [{"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"}],
    "all": [{"feature": "d_holders", "op": "gt", "value": 0}],
}
AC = {"clauses": [{"all_of": ["A", "C"]}]}


class ListAwareVerticalTests(unittest.TestCase):
    maxDiff = None

    def _resolve(self, plane: Path, work: Path, tag: str, query: dict[str, Any]) -> dict[str, Any]:
        path = work / f"{tag}-draft.json"
        path.write_text(json.dumps(query), encoding="utf-8")
        return _forge_call("research-scope-resolve", "--spec", str(path), data_root=plane)

    def _run(self, plane: Path, work: Path, tag: str, query: dict[str, Any], *, focus: str) -> dict[str, Any]:
        from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

        resolved = self._resolve(plane, work, tag, query)
        canonical = resolved["canonical_query"]
        pre = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", focus, data_root=plane)
        scope = {
            "population": "OPPORTUNITY_EPISODES",
            "decision_timestamp": "E1800",
            "target": temporal.temporal_target_label(canonical),
            "estimand": "price_relative_proxy",
            "explanatory_condition": canonical["hypothesis_kind"],
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        operation = _operation(
            canonical,
            focus=pre["owner_focus"],
            journal=pre["search_key_sha256"],
            market=pre["market_evidence_epoch_sha256"],
            text=f"List-aware vertical {tag}",
            cap={"main": 1, "adaptive": 0, "preview": 0},
            completion="LIMITED_RESULT",
        )
        evidence = _discovery(plane, work, tag=tag, spec=canonical, scope=scope, operation=operation)
        evidence["_preflight"] = pre
        return evidence

    def test_full_vertical(self) -> None:
        from tests.test_hfic_cli import run_cli
        from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            source, packets = capture(work)
            plane, mirror = work / "plane", work / "mirror"
            plane.mkdir()
            ResearchStore(plane).prepare_write_lookup()
            first = _consume(packets[:1], source=source, mirror=mirror, plane=plane)
            self.assertEqual(first["_exit_code"], 0, first)
            store = ResearchStore(plane)
            proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
            apply_universe_policy(store, repo_root=ROOT, proposal=proposal, confirm_append_only=True)

            # D09: the axis is in the emitted Prompt-A packet before any candidate exists.
            pre = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "LAV_CONTEXT", data_root=plane)
            context = pre["forge_context_packet"]["list_dimension_context"]
            self.assertEqual(context["admitted_episodes_n"], 7)
            by_id = {item["list_id"]: item for item in context["definitions"]}
            self.assertEqual({k: v["episodes_true_n"] for k, v in by_id.items()}, {LIST_ID["A"]: 4, LIST_ID["B"]: 4, LIST_ID["C"]: 4})
            self.assertEqual(sum(item["episodes_unknown_n"] for item in by_id.values()), 0)
            signatures = {tuple(item["member_list_ids"]): item["episodes_n"] for item in context["overlap_signatures"]}
            self.assertEqual(signatures[(LIST_ID["A"], LIST_ID["B"], LIST_ID["C"])], 1)
            self.assertEqual(signatures[(LIST_ID["A"], LIST_ID["C"])], 1)
            self.assertNotIn("mean_target", json.dumps(context))

            # D10: list membership is the whole signal; no fake numeric predicate.
            contrast = self._run(plane, work, "contrast", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_CONTRAST")
            self.assertEqual(contrast["_exit_code"], 0, contrast)
            result = contrast["result"]
            scope = result["research_scope"]
            self.assertEqual(scope["base_admitted_n"], 7)
            self.assertEqual(scope["matched"]["n"], 2)
            self.assertAlmostEqual(scope["matched"]["mean_target"], 0.05, places=6)
            comp = scope["contrast"]["comparator"]
            self.assertEqual((comp["n"], comp["target_observed_n"], comp["target_missing_n"]), (5, 4, 1))
            self.assertAlmostEqual(comp["mean_target"], 0.15, places=6)
            self.assertAlmostEqual(scope["contrast"]["observed_target_difference"], -0.10, places=6)
            self.assertEqual(result["spec_sha256"], contrast["_preflight"].get("spec_sha256", result["spec_sha256"]))

            # D11: a numeric mechanism inside A and C.
            numeric = self._run(plane, work, "numeric", draft("NUMERIC_IN_SCOPE", research_scope={"universe_selector": AC}, **NUMERIC), focus="LAV_NUMERIC")
            self.assertEqual(numeric["_exit_code"], 0, numeric)
            n_result = numeric["result"]
            self.assertEqual(n_result["research_scope"]["universe_pass_n"], 2)
            self.assertEqual(n_result["matched_n"], 1)
            self.assertAlmostEqual(n_result["mean_target"], 0.20, places=6)
            self.assertAlmostEqual(n_result["baseline"]["mean_target"], 0.05, places=6)

            # D12: the missing target stays in the denominator, never zero.
            self.assertEqual(result["missing_is_not_zero"], True)

            # D16: unknown membership is a coverage refusal before any value.
            unknown = draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A", "Z"]}]})
            bad = self._resolve_expect_failure(plane, work, "unknown", unknown)
            self.assertIn("LIST_REF_UNKNOWN", bad)

            # D21: the next weekly cycle, same rule, new memberships; e1 does not inherit A.
            second = _consume(packets[1:], source=source, mirror=mirror, plane=plane)
            self.assertEqual(second["_exit_code"], 0, second)
            pre2 = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "LAV_NEXT", data_root=plane)
            context2 = pre2["forge_context_packet"]["list_dimension_context"]
            self.assertEqual(context2["admitted_episodes_n"], 10)
            next_run = self._run(plane, work, "next", draft("LIST_CONTRAST", list_condition=AC), focus="LAV_NEXT")
            self.assertEqual(next_run["_exit_code"], 0, next_run)
            matched = next_run["result"]["research_scope"]["matched"]
            # cohort A {e5,e7} + cohort B {n1}; e1 (C only) is not in A and C
            self.assertEqual(matched["n"], 3)
            self.assertEqual(matched["distinct_mint_n"], 3)
            self.assertNotEqual(next_run["result"]["spec_sha256"], "")
            self.assertEqual(next_run["result"]["research_scope"]["rule_sha256"], result["research_scope"]["rule_sha256"])
            self.assertNotEqual(next_run["result"]["research_scope"]["applied_sha256"], result["research_scope"]["applied_sha256"])

    def _resolve_expect_failure(self, plane: Path, work: Path, tag: str, query: dict[str, Any]) -> str:
        from tests.test_hfic_cli import run_cli

        path = work / f"{tag}-draft.json"
        path.write_text(json.dumps(query), encoding="utf-8")
        done = run_cli("research-scope-resolve", "--spec", str(path), "--format", "json", data_root=plane)
        self.assertNotEqual(done.returncode, 0)
        return done.stdout + done.stderr


if __name__ == "__main__":
    unittest.main()
