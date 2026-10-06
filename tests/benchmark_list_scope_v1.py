"""Bounded workstation benchmark for the list scope (PRD V2 D24). Not a unit test.

Reproduce:  uv run --locked --managed-python python -B tests/benchmark_list_scope_v1.py

10k synthetic episodes, 5 lists, 8 explicit slices against the existing temporal
evaluator. Prints wall time, peak resident memory and the observation-index pass
count for: no scope, scope, then double the episodes and double the slices
separately, so a hidden quadratic repeat shows up as a ratio, not a number to trust.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import hfic_research_scope as rs  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    execute_temporal_discovery,
    validate_temporal_query,
)
from tests.test_opportunity_episodes_contract_v1 import (  # noqa: E402
    COHORT,
    HOLD,
    LIQ,
    PRICE,
    RELEASE,
    binding_item,
)

LISTS = [f"L:{x}" for x in "ABCDE"]
T0 = "2026-10-05T00:02:10Z"
AVAILABLE = {"E300": "2026-10-05T00:10:04Z", "E1800": "2026-10-05T00:35:09Z", "E14400": "2026-10-05T04:05:08Z"}


def peak_rss_bytes() -> int | None:
    from tests.test_opportunity_episodes_vertical_v1 import peak_rss_bytes as measure

    return measure()


def corpus(n: int, seed: int = 7):
    rng = random.Random(seed)
    census, rows = [], []
    base = datetime(2026, 10, 5, 0, 10, 4, tzinfo=UTC)
    for i in range(n):
        episode = f"EP{i:07d}"
        mint = f"M{i:07d}".ljust(40, "x")
        census.append({"cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "t0": T0})
        holders_rise = rng.random() < 0.5
        for point, hold, price in (("E300", 60, 1.0), ("E1800", 75 if holders_rise else 55, 1.0), ("E14400", 80, 1.0 + rng.uniform(-0.2, 0.4))):
            for field, value in ((PRICE, price), (HOLD, hold), (LIQ, 12000)):
                request = datetime.fromisoformat(AVAILABLE[point].replace("Z", "+00:00")) - timedelta(seconds=4)
                response = request + timedelta(seconds=3)
                rows.append(
                    {
                        "cohort_id": COHORT, "release_id": RELEASE, "episode_id": episode, "mint": mint, "point_id": point, "field_id": field,
                        "typed_value": str(value), "state": "OBSERVED",
                        "request_started_at": request.strftime("%Y-%m-%dT%H:%M:%SZ"), "response_received_at": response.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "first_reliable_available_at": AVAILABLE[point], "request_sha256": "33" * 32, "call_occurrence_id": ("44" * 31) + point[-2:].rjust(2, "0").replace("E", "0")[:2],
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001", "observation_clock_policy": "PROVIDER_REPORTED_SNAPSHOT_V1", "source_price_event_time": "UNKNOWN",
                    }
                )
    del base
    return census, rows


def evidence(census):
    ev = rs.MembershipEvidence()
    for list_id in LISTS:
        body = {"list_id": list_id, "definition_version": "1", "provider_or_owner": "BENCH", "kind": "BENCH", "semantics": {}, "adapter": "BENCH"}
        ev.add_definition({**body, "aliases": [], "definition_sha256": rs.sha256_of(body)})
    rng = random.Random(11)
    for row in census:
        ev.states[row["episode_id"]] = {list_id: (rs.TRUE if rng.random() < 0.4 else rs.FALSE) for list_id in LISTS}
        ev.t0[row["episode_id"]] = datetime(2026, 10, 5, 0, 2, 10, tzinfo=UTC)
    ev.bindings.append({"adapter": "BENCH"})
    return ev


def query(ev, slices: int):
    aliases = {x: f"L:{x}" for x in "ABCDE"}
    selectors = [{"clauses": [{"all_of": [a]}]} for a in "ABCDE"] + [
        {"clauses": [{"count": {"of": list("ABCDE"), "min": 2, "max": 5}}]},
        {"clauses": [{"all_of": ["A", "C"], "none_of": ["B"]}]},
        {"clauses": [{"any_of": ["D", "E"]}]},
    ]
    spec = {
        "schema": "smial.hfic-temporal-query", "schema_version": "1.2", "query_id": "BENCH", "population": "OPPORTUNITY_EPISODES", "anchor_kind": "NOMINATION_T0",
        "time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1", "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT"},
        "search_tier": "COMPOUND_SCREEN", "budget_allocation": "COMPOUND_FIRST", "decision": {"point_id": "E1800"},
        "features": [{"name": "d", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"}],
        "all": [{"feature": "d", "op": "gt", "value": 0}],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400", "field_id": PRICE},
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
        "hypothesis_kind": "MIXED_LIST_NUMERIC", "research_scope": {}, "list_aliases": aliases,
        "list_condition": {"clauses": [{"all_of": ["A", "C"]}]},
        "diagnostic_slices": [{"slice_id": f"S{i}", "selector": selectors[i % len(selectors)]} for i in range(slices)],
    }
    return rs.canonicalize_query_scope(spec, ev)


def run(n: int, slices: int, *, scoped: bool):
    census, rows = corpus(n)
    ev = evidence(census)
    q = query(ev, slices)
    started = time.perf_counter()
    if scoped:
        body = validate_temporal_query(q)["scientific_body"]
        resolved = rs.ResolvedScope(scope=body["research_scope"], list_condition=body["list_condition"], evidence=ev,
                                    episode_ids=[r["episode_id"] for r in census], slices=body["diagnostic_slices"])
        resolve_s = time.perf_counter() - started
        t = time.perf_counter()
        out = execute_temporal_discovery(census, rows, q, [binding_item()], research_scope=resolved)["summary"]
        eval_s = time.perf_counter() - t
    else:
        legacy = {k: v for k, v in q.items() if k not in {"research_scope", "list_condition", "hypothesis_kind", "diagnostic_slices", "contrast"}}
        legacy["schema_version"] = "1.1"
        resolve_s = 0.0
        t = time.perf_counter()
        out = execute_temporal_discovery(census, rows, legacy, [binding_item()])["summary"]
        eval_s = time.perf_counter() - t
    return {
        "episodes": n, "slices": slices if scoped else 0, "scoped": scoped, "resolve_s": round(resolve_s, 3), "evaluate_s": round(eval_s, 3),
        "observation_index_passes": out["observation_index_passes"], "matched_n": out["matched_n"], "peak_rss_mb": round((peak_rss_bytes() or 0) / 2**20, 1),
    }


def main() -> None:
    results = [
        run(10_000, 0, scoped=False),
        run(10_000, 4, scoped=True),
        run(20_000, 4, scoped=True),
        run(10_000, 8, scoped=True),
    ]
    total = [item["evaluate_s"] + item["resolve_s"] for item in results]
    summary = {
        "results": results,
        "scope_overhead_ratio_vs_unscoped": round(total[1] / max(1e-9, total[0]), 3),
        "double_episodes_ratio": round(total[2] / max(1e-9, total[1]), 3),
        "double_slices_ratio": round(total[3] / max(1e-9, total[1]), 3),
        "note": "ratios near 2.0 for episodes and near 1.0 for slices mean no hidden quadratic repeat; slices are capped at 8 by the validator",
    }
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
