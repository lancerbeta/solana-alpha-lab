"""I3 seam proof: managed daily children through the existing release verify/import/preflight.

Four managed UTC days across a Monday-UTC cycle boundary on one disposable corpus. The existing
owners do everything: ordinary ticks (with one child failing once), capture/freeze/export, the
production ``unpack-next-live-cohort`` verify+import entry and the Forge discovery preflight.
Oracles are raw SQL and authored dates. This does not widen the unit-level suite; it proves that
managed children are exportable, typed where unobserved and never a fragmented cohort.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import tests.test_opportunity_episodes_vertical_v1 as vertical
from solana_alpha_lab.factory.live_cohort_vanilla_path import capture_freeze_export
from solana_alpha_lab.factory.live_cohort_discovery_release import LiveCohortReleaseError
from solana_alpha_lab.factory.observation_scheduler import ObservationSchedulerError
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_managed_collection_continuity_v1 import ManagedScenario, SCOPE, sql
from tests.test_opportunity_episodes_harness_v1 import nominate, synth_mint, token_object

SEED_DAY = datetime(2026, 10, 10, tzinfo=UTC)  # Saturday, cycle starting Monday 2026-10-05
DAYS = [SEED_DAY + timedelta(days=n) for n in range(5)]  # seed bridge, then Sun 11, Mon 12, Tue 13, Wed 14
END = datetime(2026, 10, 18, 6, 0, 5, tzinfo=UTC)
ROUNDS = 3


class ManagedReleaseSeamTests(unittest.TestCase):
    def test_four_managed_days_weekly_boundary_release_import_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_seam(Path(tmp))

    def run_seam(self, tmp: Path) -> None:
        from solana_alpha_lab.factory.remote_ops import BACKUP_SINK_ENV

        sc = ManagedScenario(tmp / "rdp", start=DAYS[0], stops=DAYS[1])
        sc.market = vertical_market(self, sc)
        with patch.dict("os.environ", {BACKUP_SINK_ENV: str(sc.sink)}):
            sc.commission_account(DAYS[0])
            plan = sc.plan(DAYS[0] + timedelta(hours=1), not_before=DAYS[1])
            self.assertEqual(plan["terminal"], "MANAGED_PLAN_READY", plan)
            sc.proposal = plan
            applied = sc.cmd(DAYS[0] + timedelta(hours=1), "collection-apply", *sc.profile_args(not_before=DAYS[1]),
                             "--expected-proposal-sha256", plan["proposal_sha256"],
                             "--phrase", plan["exact_owner_phrase"])
            self.assertEqual(applied["terminal"], "MANAGED_APPLIED", applied)
            known: set[str] = {sc.activation_id}
            failed_once = {"done": False}
            import scripts.observation_schedule as cli
            real_tick = cli.tick_once

            def flaky(**kwargs):
                if kwargs["activation_id"] not in known and not failed_once["done"]:
                    failed_once["done"] = True
                    raise ObservationSchedulerError("SIMULATED_CHILD_FAILURE")
                return real_tick(**kwargs)

            tails_served = []
            for at in tick_times():
                sc.backup(at)  # the existing backup owner keeps running
                if at == DAYS[3] + timedelta(seconds=5):
                    known |= {row[2] for row in sc.children()}
                    with patch.object(cli, "tick_once", side_effect=flaky):
                        result = sc.tick(at)
                    self.assertTrue(failed_once["done"])
                    # One failing child never stops the bridge and the earlier children's tails.
                    outcomes = {item["activation_id"]: item["terminal"] for item in result["activations"]}
                    failing = [aid for aid, terminal in outcomes.items() if terminal == "SIMULATED_CHILD_FAILURE"]
                    self.assertEqual(len(failing), 1, outcomes)
                    healthy = [aid for aid, terminal in outcomes.items() if terminal in {"TICK_COMPLETE", "TICK_PARTIAL"}]
                    self.assertGreaterEqual(len(healthy), 1, outcomes)
                    self.assertEqual(result["_exit_code"], 2)
                    tails_served = healthy
                else:
                    result = sc.tick(at)
                if result.get("_exit_code") not in (0, 2) or str(result.get("terminal")) == "TICK_REFUSED_NO_LIVE_DEFAULT":
                    # every obligation terminal and nothing live: the corpus is fully drained
                    if str(result.get("terminal")) != "TICK_REFUSED_NO_LIVE_DEFAULT":
                        self.fail(result)
            self.assertTrue(tails_served)
            self.assert_corpus_truth(sc)
            self.release_import_preflight(sc, tmp)

    def assert_corpus_truth(self, sc: ManagedScenario) -> None:
        rows = sc.children()
        self.assertEqual([row[0] for row in rows][:4], ["2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"])
        # The controller keeps owning later days (no nominations there): one child per UTC day, no gaps.
        self.assertEqual([row[0] for row in rows], [(datetime(2026, 10, 11, tzinfo=UTC) + timedelta(days=n)).date().isoformat()
                                                   for n in range(len(rows))])
        late = {row[2] for row in rows[4:]}
        self.assertEqual(sql(sc.ops_path, "SELECT COUNT(*) FROM episode_admissions WHERE activation_id IN (%s)" % ",".join(
            "'%s'" % item for item in late))[0][0], 0)
        # No fragmented cohort: exactly one scope owns every UTC-day cohort.
        scopes = sql(sc.ops_path, "SELECT cohort_id, COUNT(DISTINCT schedule_sha256||activation_id) FROM episode_admissions GROUP BY 1")
        self.assertTrue(scopes and all(n == 1 for _cohort, n in scopes), scopes)
        self.assertEqual(len(scopes), 5)  # bridge day + four managed days
        # Weekly boundary: the Monday-UTC cycle changes between 2026-10-11 and 2026-10-12.
        cycles = sql(sc.ops_path, "SELECT substr(t0,1,10), json_extract(record_json,'$.cycle_start') FROM episode_admissions ORDER BY t0")
        by_day = {}
        for day, cycle in cycles:
            by_day.setdefault(day, set()).add(cycle[:10])
        self.assertEqual(by_day["2026-10-11"], {"2026-10-05"})
        self.assertEqual(by_day["2026-10-12"], {"2026-10-12"})
        # Missingness is never zero: every non-observed obligation is terminal and typed.
        states = dict(sql(sc.ops_path, "SELECT state, COUNT(*) FROM due_observations GROUP BY state"))
        self.assertFalse({"PENDING", "DUE", "CLAIMED"} & set(states), states)
        untyped = sql(sc.ops_path, "SELECT COUNT(*) FROM due_observations WHERE state != 'OBSERVED' AND "
                                    "COALESCE(json_extract(payload_json,'$.missing_reason'),'') = ''")[0][0]
        self.assertEqual(untyped, 0)
        self.assertGreater(states.get("OBSERVED", 0), 0)
        self.assertGreater(sum(count for state, count in states.items() if state != "OBSERVED"), 0)

    def release_import_preflight(self, sc: ManagedScenario, tmp: Path) -> None:
        packets, imported = [], set()
        for _ in range(8):
            try:
                packet = capture_freeze_export(observation_rdp=sc.data_root, ops_store=sc.ops_path,
                                               imported_cohort_ids=set(imported), as_of=END,
                                               collection="OPPORTUNITY_EPISODES")
            except LiveCohortReleaseError as exc:
                self.assertEqual(str(exc), "NO_MATURE_UNIMPORTED_COHORT")
                break
            path = tmp / f"packet-{packet['cohort_id']}.json"
            path.write_text(json.dumps(packet, default=str), encoding="utf-8")
            packets.append(str(path))
            imported.add(str(packet["cohort_id"]))
        self.assertEqual(len(packets), 5, imported)
        plane, mirror = tmp / "plane", tmp / "mirror"
        plane.mkdir()
        ResearchStore(plane).prepare_write_lookup()
        with patch.object(vertical, "AS_OF", END + timedelta(hours=1)):
            vertical._import_legacy(plane, tmp)
            consumed = vertical._consume(packets, source=sc.data_root, mirror=mirror, plane=plane)
        self.assertEqual(consumed["_exit_code"], 0, consumed)
        statuses = [item.get("import_status") for item in consumed["result"]["cohorts"]]
        self.assertEqual(len(statuses), 5, consumed)
        self.assertTrue(all(status == "IMPORTED" for status in statuses), statuses)
        # Existing Forge discovery preflight reads the imported managed corpus.
        from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy

        store = ResearchStore(plane)
        proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
        apply_universe_policy(store, repo_root=vertical.ROOT, proposal=proposal, confirm_append_only=True)
        pre = vertical._forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES",
                                   "--owner-focus", vertical.FOCUS, data_root=plane)
        card = pre["forge_context_packet"].get("population_card")
        self.assertTrue(card, pre["forge_context_packet"].keys())
        self.assertIn("episode_query_capabilities", pre["forge_context_packet"])


def tick_times() -> list[datetime]:
    """Only the instants the proof needs; every other slot terminalizes as an explicit typed gap."""

    times: set[datetime] = set()
    for day in DAYS:
        times.add(day + timedelta(seconds=5))
        for index in range(ROUNDS):
            start = day + timedelta(minutes=15 * index)
            times.add(start + timedelta(seconds=5))
            for offset in (300, 1800, 14400):
                times.add(start + timedelta(seconds=offset + 300 + 5))
    cursor = DAYS[0] + timedelta(hours=12, seconds=5)
    while cursor < END:
        times.add(cursor)
        cursor += timedelta(hours=12)
    times.add(END)
    return sorted(times)


def vertical_market(case: unittest.TestCase, sc: ManagedScenario):
    """Nominations on the first rounds of each day; prices move after the nomination."""

    market = sc.market
    for day_index, day in enumerate(DAYS):
        for index in range(ROUNDS):
            start = day + timedelta(minutes=15 * index)
            mint = synth_mint(f"Seam{day_index}x{index}")
            signal = index % 2 == 0
            row0 = token_object(mint, price=1.0, liquidity=10000, holders=60)
            nominate(market, start, {"toporganicscore": [row0], "toptraded": [], "toptrending": []})

            def series(now, start=start, mint=mint, signal=signal):
                if now < start:
                    return None
                return vertical.market_row(mint, now, signal, start, tiny=False)

            market.series[mint] = series
    return market


if __name__ == "__main__":
    unittest.main()
