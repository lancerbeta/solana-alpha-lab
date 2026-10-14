"""Native synthetic ingress and frozen candidate for the bounded 1.4 proof."""
from __future__ import annotations

import copy
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from tests import test_hfic_list_aware_vertical_v1 as lav
from tests.test_forge_research_flow_reliability_v1 import EpisodeFlowTests
from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment
from tests.test_opportunity_episodes_harness_v1 import token_object, write_assignment
from tests.test_opportunity_episodes_vertical_v1 import AS_OF
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy, apply_universe_policy
from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_episode_binding
from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
from solana_alpha_lab.factory.hfic_session import load_session_bundle

ROOT = Path(__file__).resolve().parents[3]


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def prepare(work: Path, *, target_price: float = 1.10, missing_target: bool = False, reuse_ingress: Path | None = None):
    """24 admissions, frozen oracle before MAIN; only market ingress is authored."""
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    descriptor = {"benchmark": "EPISODE-NATIVE-REQUIRED-OUTCOMES-V1", "target_price": target_price, "missing_target": missing_target,
                  "admissions_n": 24, "decision_n": 20, "matched_n": 10, "comparator_n": 10,
                  "fixture_setup_looks": 2, "scientific_acceptance": False,
                  "ingress_reused": reuse_ingress is not None}
    if (work / "fixture.json").exists():
        saved = json.loads((work / "fixture.json").read_text())
        saved.setdefault("missing_target", False)
        saved.setdefault("ingress_reused", False)
        if reuse_ingress is None:
            descriptor["ingress_reused"] = saved["ingress_reused"]
            for key in ("ingress_reuse_mode", "ingress_source_world"):
                if key in saved:
                    descriptor[key] = saved[key]
        assert saved == descriptor
        return
    dump(work / "oracle-plan.json", descriptor)
    tables = {group: {f"repair{group}{i:02d}": ("A" if i % 2 == 0 else "B", i % 2 == 0, target_price - 1)
                       for i in range(12)} for group in ("A", "B")}
    # One mint re-enters in another allowed weekly cycle, never a second active episode.
    tables["B"]["repairA00"] = tables["B"].pop("repairB00")

    def market_row(mint, now, start, signal, target):
        offset = (now - start).total_seconds()
        index = next(i for i in range(12) if f"{i:02d}" in mint)
        price = 1.0 if offset < 10000 else 1.0 + target
        holders = 60 if offset < 1100 else (75 if signal else 55)
        if 1500 <= offset < 10000:
            if index == 10:
                holders = 40  # known universe fail, admission retained
            if index == 11:
                price = None  # known non-eligible decision price, admission retained
        if missing_target and index == 0 and start == lav.DAY_A and 10000 <= offset < 16000:
            price = None  # exactly one required future cell; repeated mint in B stays observed
        return token_object(mint, price=price, liquidity=12000, holders=holders)

    if reuse_ingress is not None:
        # Reuse the exact already registered source; native unpack/verify/import
        # owns the new mirror/consumer. Do not duplicate immutable capture bytes.
        previous = json.loads((reuse_ingress / "fixture.json").read_text())
        assert previous["target_price"] == target_price and previous["missing_target"] == missing_target
        capture = reuse_ingress.resolve() / "capture"
        assert capture.is_dir()
        source = capture / "rdp"
        packets = sorted(str(path) for path in capture.glob("packet-*.json"))
        descriptor["ingress_reuse_mode"] = "SHARED_REGISTERED_SOURCE_NATIVE_IMPORT"
        descriptor["ingress_source_world"] = reuse_ingress.name
    else:
        with patch.object(lav, "COHORT_A", tables["A"]), patch.object(lav, "COHORT_B", tables["B"]), patch.object(lav, "market_row", market_row):
            source, packets = lav._capture_fresh(work)
    plane = work / "plane"
    plane.mkdir()
    store = ResearchStore(plane)
    store.prepare_write_lookup()
    imported = lav._consume(packets, source=source, mirror=work / "mirror", plane=plane)
    assert imported["_exit_code"] == 0, imported
    # Controlled synthetic consumer's explicit current completeness proof.
    # Frozen admission metadata alone is not current protection authority.
    write_assignment(plane, [])
    proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
    apply_universe_policy(store, repo_root=ROOT, proposal=proposal, confirm_append_only=True)
    # Independent membership oracle: input label truth, native source identity;
    # never classifier output, and frozen before any discovery/classification.
    import pyarrow.parquet as pq
    expected = []
    binding = resolve_published_episode_binding(plane)
    for item in binding["cohorts"]:
        for row in pq.read_table(plane / item["census_rel"], columns=["episode_id", "mint"]).to_pylist():
            index = next(i for i in range(12) if f"{i:02d}" in row["mint"])
            expected.append({"episode_id": row["episode_id"], "decision_eligible": index < 10,
                             "matched": index < 10 and index % 2 == 0,
                             "comparator": index < 10 and index % 2 == 1})
    dump(work / "membership-oracle.json", sorted(expected, key=lambda x: x["episode_id"]))
    assert len(expected) == 24
    for kind in ("LIST_CONTRAST", "MIXED_LIST_NUMERIC"):
        case = EpisodeFlowTests()
        case.plane, case.work = plane, work / kind
        case.work.mkdir()
        query = lav.draft(kind, list_condition={"clauses": [{"all_of": ["A"]}]}, **(lav.NUMERIC if kind != "LIST_CONTRAST" else {}))
        evidence, scope, _query, pre = case.look("REPAIR-" + kind, query=query)
        body, ready = case.authored_draft(evidence, scope, pre["owner_focus"])
        _generated, frozen = case.persist_and_freeze(body, ready)
        bundle = load_session_bundle(ResearchStore(plane), frozen["session_id"])
        spec = _bind_experiment(evidence["result"]["experiment_recipe"], plane)
        spec.update(schema_version="1.4", population="OPPORTUNITY_EPISODES",
                    experiment_id="EXP-EPISODE-REPAIR-" + kind.replace("_", "-"),
                    hypothesis_version="HYP-" + frozen["selected_candidate_id"],
                    as_of=(AS_OF + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                    availability_cutoff=(AS_OF + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                    observation_request={"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"},
                    required_outcomes=[{"point_id": "E14400", "field_ids": [lav.PRICE], "role": "PRIMARY"}])
        spec["parameters"]["hfic_replay_session_id"] = frozen["session_id"]
        dump(case.work / "spec.json", spec)
        dump(case.work / "frozen.json", bundle)
    dump(work / "fixture.json", descriptor)


def load_case(work, kind="LIST_CONTRAST"):
    base = Path(work) / kind
    spec, frozen = json.loads((base / "spec.json").read_text()), json.loads((base / "frozen.json").read_text())
    spec["parameters"]["hfic_replay_session_id"] = frozen["session_id"]
    return spec, frozen
