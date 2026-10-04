"""Bounded entry witnesses on disposable synthetic rows; never a live store."""
from __future__ import annotations

import copy
import json
import unittest
import contextlib
import hashlib
import io
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from tests.test_hfic_temporal_discovery_v1 import (
    ANCHOR, COHORT, COHORT_B, RELEASE, RELEASE_B, _bind, _member_path, _simple,
)
from solana_alpha_lab.factory.hfic_grounded_discovery import execute_discovery_from_rows
from solana_alpha_lab.factory.hfic_temporal_discovery import validate_temporal_query
from solana_alpha_lab.factory import hfic_temporal_discovery as temporal

ROOT = Path(__file__).resolve().parents[1]
HOLDER = temporal.HOLDER_COUNT
PRICE, LIQ = temporal.PRICE, temporal.LIQUIDITY


def mixed_spec(op="delta"):
    from tests.test_forge_temporal_holder_point_feature_v1 import holder_spec
    from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS
    spec = holder_spec()
    spec.update(search_tier="COMPOUND_SCREEN", budget_allocation="COMPOUND_FIRST",
        features=[{"name": "holders", "op": op, "field_id": HOLDER, "start": "X300", "end": "Y900"},
                  {"name": "price", "op": "return_ratio", "field_id": PRICE, "start": "X300", "end": "Y900"},
                  {"name": "liquidity", "op": "ratio", "field_id": LIQ, "numerator": "Y900", "denominator": "X300"}],
        all=[{"feature": "holders", "op": "gt", "value": 0}, {"feature": "price", "op": "gte", "value": 0},
             {"feature": "liquidity", "op": "gte", "value": 1}],
        schedule={"lateness_seconds": DOCUMENT_LATENESS, "observation_clock_policy": temporal.OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1})
    return spec


def publish_raw(workspace, *, reversed_window=False):
    """Only transport fixture input is authored; publisher/import own every binding."""
    from tests import test_hfic_temporal_production_runner_v1 as runner
    from tests.test_live_cohort_discovery_release_series import _snapshot_for_week, _obs, CAMPAIGN_STARTS
    from solana_alpha_lab.factory.observation_schedule import schedule_sha256, validate_observation_schedule
    from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy
    from solana_alpha_lab.factory.research_store import ResearchStore
    schedule = runner._schedule()
    schedule.pop("schedule_sha256")
    schedule["y_points"].append({"point_id": "Y14400", "due_offset_seconds": 14400,
        "allowed_lateness_seconds": runner.DOCUMENT_LATENESS, "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"]})
    if reversed_window:
        for point in schedule["y_points"]:
            if point["point_id"] in {"Y900", "Y1800"}:
                point["due_offset_seconds"] = {"Y900":1800, "Y1800":900}[point["point_id"]]
        schedule["y_points"].sort(key=lambda point: point["due_offset_seconds"])
    schedule = validate_observation_schedule(schedule, root=ROOT)
    schedule["schedule_sha256"] = schedule_sha256(schedule)
    def snapshot(week):
        body = _snapshot_for_week(week)
        template = body["members"][0]
        body["members"], body["observations"] = [], []
        anchor = CAMPAIGN_STARTS + timedelta(days=7*week)
        admission = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
        for i, (start, end) in enumerate([(60,120),(240,120),(0,60),(60,60),(20,80),(None,120),
                                         (60,120),(60,120),(60,None),(60,20),(60,120),(60,120)]):
            mint = f"raw-w{week}-{i}"
            body["members"].append({**template, "mint": mint, "candidate_state": "X_ELIGIBLE"})
            for point, field, value in [("X300",LIQ,1000),("X300",PRICE,1),("X300",HOLDER,start),
                                       ("Y900",LIQ,10000),("Y900",PRICE,None if i==10 else 1.1),
                                       ("Y900",HOLDER,end),("Y14400",PRICE,1.32)]:
                offset = {"X300":300,"Y900":900,"Y14400":14400}[point]
                late = int(i==6 and field==HOLDER and point=="X300")
                stamp = (anchor+timedelta(seconds=offset+runner.DOCUMENT_LATENESS+late)).strftime("%Y-%m-%dT%H:%M:%SZ")
                r = _obs(mint, point, admission, missing=value is None)
                r.update(field_id=field, typed_value=None if value is None else str(value), event_time=stamp,
                         first_reliable_available_at=stamp, missing_reason="FIELD_ABSENT" if value is None else None)
                body["observations"].append(r)
                if i==7 and point=="X300" and field==HOLDER:
                    body["observations"].append({**r, "typed_value":"50"})
        stamped = temporal.stamp_provider_reported_snapshot_transport(body["observations"])
        for r in stamped:
            r["call_occurrence_id"] = hashlib.sha256(f"{r['mint']}:{r['point_id']}".encode()).hexdigest()
        body["observations"] = stamped
        return body
    root = workspace / "rdp"
    with mock.patch.object(runner,"_snapshot_for_week",side_effect=snapshot), mock.patch.object(runner,"_schedule",return_value=schedule):
        for week in range(4):
            runner._publish(root,workspace,week=week,activate_universe=False)
    store = ResearchStore(root)
    proposal = preview_universe_policy(store,min_holders=50,min_liquidity_usd=5000)["proposal"]
    apply_universe_policy(store,repo_root=ROOT,proposal=proposal,confirm_append_only=True)
    return root


def future_prefix_witness() -> dict:
    """Only future Y7200 PRICE differs; every input cell through Y3600 agrees."""
    binding = [_bind(COHORT, RELEASE), _bind(COHORT_B, RELEASE_B)]
    a = _member_path("synthetic-shared", COHORT, RELEASE, ANCHOR,
                     [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44)
    b = _member_path("synthetic-shared", COHORT_B, RELEASE_B, ANCHOR,
                     [1.0, 1.2, 1.5, 1.2], (10000.0, 9000.0), 1.44)
    census = [a[0], b[0]]
    observations = a[1] + b[1]
    changed = copy.deepcopy(observations)
    differences = []
    for row in changed:
        if row["cohort_id"] == COHORT_B and row["point_id"] == "Y7200":
            differences.append({"point_id": row["point_id"], "field_id": row["field_id"],
                                "before": row["typed_value"], "after": 9.0})
            row["typed_value"] = 9.0
    assert len(differences) == 1
    prefix = lambda rows: [r for r in rows if r["point_id"] != "Y7200"]
    assert prefix(observations) == prefix(changed)
    query = _simple()
    run = lambda rows: execute_discovery_from_rows(census, rows, query, binding)["summary"]
    before, after = run(observations), run(changed)
    keys = ("population_n", "decision_eligible_n", "matched_n", "integrity_conflict_count",
            "duplicate_delivery_count")
    return {
        "decision": "Y3600", "changed_cells": differences, "predecision_cells_equal": True,
        "before": {key: before[key] for key in keys},
        "after": {key: after[key] for key in keys},
        "per_cohort_before": [{"cohort_id": r["cohort_id"], "decision_eligible_n": r["decision_eligible_n"]}
                              for r in before["by_cohort"]],
        "per_cohort_after": [{"cohort_id": r["cohort_id"], "decision_eligible_n": r["decision_eligible_n"]}
                             for r in after["by_cohort"]],
        "live_reads": 0, "provider_calls": 0, "store_writes": 0,
    }


def legacy_preview_fixture_inputs():
    from tests.test_hfic_temporal_discovery_v1 import _obs
    census, rows = _member_path("legacy-preview", COHORT, RELEASE, ANCHOR,
                               [1,1.2,1.5,1.2], (10000,9000), 1.44)
    rows.append({**_obs("legacy-preview","Y3600",HOLDER,120),"cohort_id":COHORT,"release_id":RELEASE})
    spec={"decision":_simple()["decision"],"schedule":{**_simple()["schedule"],"points":["X300","Y3600"]},
          "features":[{"name":"h","op":"point_value","field_id":HOLDER,"point":"Y3600"}],"seed":"legacy-base"}
    return [census], [r for r in rows if r["point_id"] in {"X300","Y3600"}], spec, [_bind(COHORT,RELEASE)]


class EntryWitness(unittest.TestCase):
    def test_capability_only_grounding_is_accepted_without_authority(self):
        from solana_alpha_lab.factory.hfic_grounding import ground_candidate, HficGroundingError
        from solana_alpha_lab.factory.hfic_control_integrity import fast_lane_availability_denial_codes
        card = {"required_feature_ids": [], "required_capability_ids": [temporal.TEMPORAL_CAPABILITY_ID],
                "unresolved_requirements": []}
        grounding = ground_candidate(card, repo_root=ROOT, context_packet_sha256="1"*64,
                                     accepted_capability_ids=[temporal.TEMPORAL_CAPABILITY_ID])
        self.assertEqual(grounding["terminal"], "GROUNDED")
        self.assertEqual(grounding["feature_bindings"], [])
        self.assertEqual(grounding["unresolved_requirements"], [])
        self.assertEqual(grounding["capability_bindings"], [{"capability_id": temporal.TEMPORAL_CAPABILITY_ID,
                        "accepted": True, "authority_granted": False}])
        self.assertEqual(fast_lane_availability_denial_codes({**card, "grounding": grounding}), [])
        for required, accepted in ((temporal.TEMPORAL_CAPABILITY_ID, []), ("CAP-UNKNOWN", [temporal.TEMPORAL_CAPABILITY_ID])):
            with self.subTest(required=required), self.assertRaisesRegex(HficGroundingError, "UNKNOWN_CAPABILITY"):
                ground_candidate({**card, "required_capability_ids": [required]}, repo_root=ROOT,
                                 context_packet_sha256="1"*64, accepted_capability_ids=accepted)

    def test_non_holder_dynamic_feature_preview_keeps_legacy_refusal(self):
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        spec = mixed_spec()
        spec["features"][0] = {"name":"holders", "op":"point_value", "field_id":HOLDER, "point":"Y900"}
        preview_spec = {"decision":spec["decision"], "schedule":{**spec["schedule"], "points":["X300","Y900"]},
                        "features":spec["features"], "seed":"legacy"}
        with mock.patch.object(temporal, "_build_recipe_preview", side_effect=AssertionError("raw owner invoked")):
            with self.assertRaisesRegex(GroundedDiscoveryError, "FEATURE_OP_UNSUPPORTED"):
                temporal.build_feature_preview([], [], preview_spec, [])

    def test_holder_raw_recipe_is_supported(self):
        spec = _simple()
        spec["features"] = [{"name": "impulse", "op": "delta", "field_id": "FIELD-HOLDER-COUNT-001",
                             "start": "X300", "end": "Y3600"}]
        validate_temporal_query(spec)

    def test_accepted_legacy_membership_depends_on_future_target(self):
        proof = future_prefix_witness()
        self.assertTrue(proof["predecision_cells_equal"])
        self.assertEqual(proof["before"]["decision_eligible_n"], 1)
        self.assertEqual(proof["after"]["decision_eligible_n"], 0)
        self.assertEqual(proof["after"]["integrity_conflict_count"], 1)


class RawArithmeticTests(unittest.TestCase):
    def test_legacy_preview_exact_base_output(self):
        expected=json.loads((ROOT/"tests/fixtures/forge_composite_feature_recipes_v1/legacy_preview_base_v1.json").read_text(encoding="utf-8"))
        with mock.patch.object(temporal,"_build_recipe_preview",side_effect=AssertionError("raw owner invoked")):
            actual=temporal.build_feature_preview(*legacy_preview_fixture_inputs())
        self.assertEqual(actual,expected["preview"])

    def test_equal_relative_targets_do_not_hide_source_copy_conflict(self):
        from tests.test_hfic_temporal_discovery_v1 import _obs
        copies=[]
        for cohort,release,reference,exit_price in [(COHORT,RELEASE,1,1.44),(COHORT_B,RELEASE_B,2,2.88)]:
            census,rows=_member_path("scaled-copy",cohort,release,ANCHOR,[reference,1.2,1.5,1.2],(10000,9000),exit_price)
            for point,value in [("X300",60),("Y3600",120)]:
                rows.append({**_obs("scaled-copy",point,HOLDER,value),"cohort_id":cohort,"release_id":release})
            copies.append((census,rows))
        query=_simple()
        query["target"]["reference_point"]="X300"
        query.update(features=[{"name":"h","op":"delta","field_id":HOLDER,"start":"X300","end":"Y3600"}],
                     all=[{"feature":"h","op":"gt","value":0}])
        projected={"decision":query["decision"],"schedule":{**query["schedule"],"points":["X300","Y3600"]},"features":query["features"],"seed":"scaled"}
        binding=[_bind(COHORT,RELEASE),_bind(COHORT_B,RELEASE_B)]
        outputs=[]
        for order in (copies,list(reversed(copies))):
            census=[c[0] for c in order];rows=[r for c in order for r in c[1]]
            result=execute_discovery_from_rows(census,rows,query,binding)["summary"]
            preview=temporal.build_feature_preview(census,[r for r in rows if r["point_id"] in {"X300","Y3600"}],projected,binding)
            self.assertEqual(result["decision_eligible_n"],1)
            self.assertEqual((result["observed_target_n"],result["missing_target_n"]),(0,1))
            self.assertEqual(result["target_exclusion_reasons"]["pooled"],{"TARGET_DELIVERY_CONFLICT":1})
            self.assertEqual(preview["support_summary"]["pooled"]["joint_calculable_n"],1)
            outputs.append(result)
        self.assertEqual(outputs[0],outputs[1])

    def test_same_value_target_clock_conflict_is_order_invariant(self):
        from tests.test_hfic_temporal_discovery_v1 import _obs
        copies=[]
        for cohort, release in [(COHORT,RELEASE),(COHORT_B,RELEASE_B)]:
            census, rows=_member_path("clock-shared",cohort,release,ANCHOR,[1,1.2,1.5,1.2],(10000,9000),1.44)
            for point,value in [("X300",60),("Y3600",120)]:
                rows.append({**_obs("clock-shared",point,HOLDER,value),"cohort_id":cohort,"release_id":release})
            copies.append((census,rows))
        exit_row=next(r for r in copies[1][1] if r["point_id"]=="Y7200")
        exit_row["event_time"]=(ANCHOR+timedelta(seconds=3900)).strftime("%Y-%m-%dT%H:%M:%SZ")
        query=_simple()
        query.update(features=[{"name":"h","op":"delta","field_id":HOLDER,"start":"X300","end":"Y3600"}],all=[{"feature":"h","op":"gt","value":0}])
        results=[]
        for order in (copies,list(reversed(copies))):
            result=execute_discovery_from_rows([c[0] for c in order],[r for c in order for r in c[1]],query,[_bind(COHORT,RELEASE),_bind(COHORT_B,RELEASE_B)])["summary"]
            self.assertEqual(result["decision_eligible_n"],1)
            self.assertEqual(result["observed_target_n"],0)
            self.assertEqual(result["target_exclusion_reasons"]["pooled"],{"TARGET_DELIVERY_CONFLICT":1})
            results.append(result)
        self.assertEqual(results[0],results[1])

    def test_preview_includes_empty_admitted_cohort(self):
        from tests.test_hfic_temporal_discovery_v1 import _obs
        census,rows=_member_path("only-first",COHORT,RELEASE,ANCHOR,[1,1.2,1.5,1.2],(10000,9000),1.44)
        for point,value in [("X300",60),("Y3600",120)]:
            rows.append({**_obs("only-first",point,HOLDER,value),"cohort_id":COHORT,"release_id":RELEASE})
        spec={"decision":_simple()["decision"],"schedule":{"points":["X300","Y3600"],"lateness_seconds":300},"features":[{"name":"h","op":"delta","field_id":HOLDER,"start":"X300","end":"Y3600"}],"seed":"empty"}
        preview=temporal.build_feature_preview([census],rows,spec,[_bind(COHORT,RELEASE),_bind(COHORT_B,RELEASE_B)])
        cohorts={c["cohort_id"]:c for c in preview["support_summary"]["by_cohort"]}
        self.assertEqual(set(cohorts),{COHORT,COHORT_B})
        self.assertEqual(cohorts[COHORT_B]["base_x_n"],0)
        self.assertEqual(cohorts[COHORT_B]["joint_calculable_n"],0)

    def test_raw_overlap_prefix_and_unavailable_suffix_are_order_invariant(self):
        from tests.test_hfic_temporal_discovery_v1 import _obs
        from solana_alpha_lab.factory.hfic_research_universe_policy import profile_definition
        binding=[_bind(COHORT,RELEASE),_bind(COHORT_B,RELEASE_B)]
        copies=[]
        for cohort,release,exit_price in [(COHORT,RELEASE,1.44),(COHORT_B,RELEASE_B,9)]:
            census,rows=_member_path("shared",cohort,release,ANCHOR,[1,1.2,1.5,1.2],(10000,9000),exit_price)
            for point,value in [("X300",60),("Y3600",120)]:
                rows.append({**_obs("shared",point,HOLDER,value),"cohort_id":cohort,"release_id":release})
            copies.append((census,rows))
        query=_simple()
        query.update(features=[{"name":"h","op":"delta","field_id":HOLDER,"start":"X300","end":"Y3600"}],
                     all=[{"feature":"h","op":"gt","value":0}])
        query["features"].extend([
            {"name":"p","op":"return_ratio","field_id":PRICE,"start":"X300","end":"Y3600"},
            {"name":"l","op":"ratio","field_id":LIQ,"numerator":"Y3600","denominator":"X300"}])
        projected={"decision":query["decision"],"schedule":{**query["schedule"],"points":["X300","Y3600"]},"features":query["features"],"seed":"prefix"}
        policy=profile_definition(50,5000)
        counts=[]
        for order in (copies,list(reversed(copies))):
            census=[c[0] for c in order]; rows=[r for c in order for r in c[1]]
            result=execute_discovery_from_rows(census,rows,query,binding,universe_policy=policy)["summary"]
            preview=temporal.build_feature_preview(census,[r for r in rows if r["point_id"] in {"X300","Y3600"}],projected,binding,universe_policy=policy)
            self.assertEqual(result["decision_eligible_n"],1)
            self.assertEqual((result["observed_target_n"],result["missing_target_n"]),(0,1))
            self.assertEqual(preview["support_summary"]["pooled"]["joint_calculable_n"],1)
            self.assertEqual(result["target_exclusion_reasons"]["pooled"],{"TARGET_DELIVERY_CONFLICT":1})
            counts.append(result)
        self.assertEqual(counts[0],counts[1])
        # Non-dependency point cannot alter numerical support.
        copies[1][1][2]["typed_value"]=999
        rows=[r for c in copies for r in c[1]]
        result=execute_discovery_from_rows([c[0] for c in copies],rows,query,binding,universe_policy=policy)["summary"]
        self.assertEqual(result["decision_eligible_n"],1)
        preview=temporal.build_feature_preview([c[0] for c in copies],rows,{**projected,"seed":"another"},binding,universe_policy=policy)
        self.assertEqual(preview["support_summary"]["pooled"]["joint_calculable_n"],1)
        original_preview=temporal.build_feature_preview([c[0] for c in copies],rows,projected,binding,universe_policy=policy)
        self.assertEqual(preview["support_summary"],original_preview["support_summary"])
        self.assertNotEqual(preview["examples"],original_preview["examples"])
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        for key,value in (("op","return_ratio"),("start","Y900"),("end","Y1800")):
            tampered=copy.deepcopy(result)
            tampered["experiment_recipe"]["spec"]["scientific_body"]["features"][0][key]=value
            with self.subTest(key=key),self.assertRaises(GroundedDiscoveryError):
                temporal.temporal_holder_claim_identity(tampered)
        for part,key,value in (("predicates","value",2),("target","exit_point","Y14400")):
            tampered=copy.deepcopy(result)
            body=tampered["experiment_recipe"]["spec"]["scientific_body"]
            (body[part][0] if isinstance(body[part],list) else body[part])[key]=value
            with self.subTest(part=part),self.assertRaises(GroundedDiscoveryError):
                temporal.temporal_holder_claim_identity(tampered)
        # Declared endpoint disagreement is unavailable feature, not a missing denominator.
        next(r for r in copies[1][1] if r["point_id"]=="X300" and r["field_id"]==HOLDER)["typed_value"]=40
        rows=[r for c in copies for r in c[1]]
        preview=temporal.build_feature_preview([c[0] for c in copies],rows,projected,binding,universe_policy=policy)
        self.assertEqual(preview["support_summary"]["pooled"]["decision_eligible_n"],1)
        self.assertEqual(preview["support_summary"]["pooled"]["features"]["h"]["reason_counts"],{"DELIVERY_CONFLICT":1})
    def test_oracles_and_typed_unavailable(self):
        from tests.test_forge_temporal_holder_point_feature_v1 import row
        from tests.test_hfic_temporal_discovery_v1 import _binding
        from solana_alpha_lab.factory.hfic_grounded_discovery import _grouped_cells
        for start,end,delta,relative in [(60,120,60,1),(240,120,-120,-.5),(0,60,60,None),(-1,60,61,None),(60,60,0,0),(20,80,60,3)]:
            observations=[row("m","X300",HOLDER,start),row("m","Y900",HOLDER,end)]
            for op,expected in [("delta",delta),("return_ratio",relative)]:
                feature={"name":"h","op":op,"field_id":HOLDER,"start":"X300","end":"Y900"}
                value,_=temporal._feature_value_with_lineage(_grouped_cells(observations),cohort=_binding()[0]["cohort_id"],
                    release=_binding()[0]["release_id"],mint="m",anchor=ANCHOR,feature=feature,lateness=300,
                    decision_deadline=temporal._deadline_for(ANCHOR,"Y900",300))
                self.assertEqual(value,expected)
        for bad in (True,float("nan"),float("inf"),None):
            observations=[row("m","X300",HOLDER,bad),row("m","Y900",HOLDER,120)]
            value=temporal._feature_value(_grouped_cells(observations),cohort=_binding()[0]["cohort_id"],
                release=_binding()[0]["release_id"],mint="m",anchor=ANCHOR,feature=feature,lateness=300,
                decision_deadline=temporal._deadline_for(ANCHOR,"Y900",300))
            self.assertIsNone(value)

    def test_closed_new_parameters_and_bound_schedule(self):
        from tests.test_hfic_temporal_discovery_v1 import _binding
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        for change in ({"start":"Y900"},{"start":"Y1800"},{"end":"Y1800"},{"half_life_seconds":60},{"field_id":PRICE}):
            spec=mixed_spec()
            spec["features"][0].update(change)
            with self.subTest(change=change),self.assertRaises(GroundedDiscoveryError):
                validate_temporal_query(spec)
        spec=mixed_spec()
        bound=validate_temporal_query(spec)
        binding=_binding()
        binding[0]["schedule_lateness_seconds"]=spec["schedule"]["lateness_seconds"]
        binding[0]["schedule_point_due_offset_seconds"]={"X300":950,"Y900":900,"Y14400":14400}
        binding[0]["schedule_point_lateness"]={"X300":300,"Y900":300,"Y14400":300}
        with self.assertRaises(GroundedDiscoveryError):
            temporal._require_bound_schedule(binding,bound["scientific_body"],spec["schedule"]["lateness_seconds"])


class PublicSupportTests(unittest.TestCase):
    def test_public_legacy_mixed_preview_projects_only_point_features(self):
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation
        with tempfile.TemporaryDirectory() as raw:
            workspace=Path(raw); root=publish_raw(workspace)
            pre=run_cli("preflight","--discovery-contract","--owner-focus","SYNTHETIC_LEGACY_PREVIEW","--format","json",data_root=root)
            self.assertEqual(pre.returncode,0,pre.stdout+pre.stderr)
            receipt=json.loads(pre.stdout)
            spec=mixed_spec()
            spec["features"][0]={"name":"holders","op":"point_value","field_id":HOLDER,"point":"Y900"}
            path,op_path=workspace/"legacy.json",workspace/"legacy.op.json"
            path.write_text(json.dumps(spec),encoding="utf-8")
            op_path.write_text(json.dumps(_operation(spec,focus="SYNTHETIC_LEGACY_PREVIEW",journal=receipt["search_key_sha256"],
                market=receipt["market_evidence_epoch_sha256"],text="Synthetic legacy projection",cap={"main":1,"adaptive":0,"preview":1})),encoding="utf-8")
            with mock.patch.object(temporal,"_build_recipe_preview",side_effect=AssertionError("raw owner invoked")),mock.patch.object(temporal,"build_feature_preview",wraps=temporal.build_feature_preview) as builder,contextlib.redirect_stdout(io.StringIO()) as out:
                code=_forge().cmd_discovery_preview(ROOT,explicit_data_root=root,spec_path=path,binding_path=None,census_path=None,observations_path=None,
                    cohort_partitions=None,prior_preview_hash=None,store_root=root,journal_scope=receipt["search_key_sha256"],operation_path=op_path)
            self.assertEqual(code,0,out.getvalue())
            projected=builder.call_args.args[2]
            self.assertEqual(projected["features"],[spec["features"][0]])
            self.assertEqual(projected["schedule"]["points"],["X300","Y900"])
            self.assertNotIn("target",projected)
            preview=json.loads(out.getvalue().splitlines()[-1])
            self.assertNotIn("support_summary",preview)
            self.assertNotIn("feature_recipe",preview)

    def test_identical_support_retains_each_operation_binding(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw)/"rdp")
            preview={"preview_sha256":"1"*64,"selected_count":0,"total_count":0}
            for op,spec in (("2"*64,"3"*64),("4"*64,"5"*64)):
                temporal.persist_feature_preview(store,journal_scope="shared-support",preview=preview,git_sha="27366b752cd0fae9683dd50373ea8ff8da5a6f6d",operation_sha256=op,spec_sha256=spec)
                saved=temporal.saved_feature_preview(store,journal_scope="shared-support",operation_sha256=op,spec_sha256=spec,binding=[])
                self.assertEqual(saved["preview_sha256"],preview["preview_sha256"])
            before=store.diagnostics().committed_inventory_sha256
            temporal.persist_feature_preview(store,journal_scope="shared-support",preview=preview,git_sha="27366b752cd0fae9683dd50373ea8ff8da5a6f6d",operation_sha256="4"*64,spec_sha256="5"*64)
            self.assertEqual(store.diagnostics().committed_inventory_sha256,before)

    def test_legacy_saved_preview_has_explicit_missing_detail(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        with tempfile.TemporaryDirectory() as raw:
            store=ResearchStore(Path(raw)/"rdp")
            temporal.persist_feature_preview(store,journal_scope="synthetic-legacy",preview={
                "preview_sha256":"1"*64,"selected_count":1,"total_count":1},
                git_sha="27366b752cd0fae9683dd50373ea8ff8da5a6f6d",operation_sha256="2"*64,spec_sha256="3"*64)
            saved=temporal.saved_feature_preview(store,journal_scope="synthetic-legacy",operation_sha256="2"*64,
                spec_sha256="3"*64,binding=[])
            self.assertEqual(saved,{"preview_sha256":"1"*64,"detail_status":"LEGACY_PREVIEW_DETAIL_UNAVAILABLE"})

    def test_public_support_and_loader_free_cold_preview(self):
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge,_operation
        from solana_alpha_lab.factory.hfic_grounded_discovery import load_admitted_partition_rows
        from solana_alpha_lab.factory.research_store import ResearchStore
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as raw:
            workspace=Path(raw)
            root=publish_raw(workspace)
            pre=run_cli("preflight","--discovery-contract","--owner-focus","SYNTHETIC_RAW_SUPPORT","--format","json",data_root=root)
            self.assertEqual(pre.returncode,0,pre.stdout+pre.stderr)
            receipt=json.loads(pre.stdout)
            self.assertIn("delta",receipt["forge_context_packet"]["temporal_recipe_capabilities"]["fields"][HOLDER])
            outputs=[]
            for op,n in [("delta",24),("return_ratio",20)]:
                spec=mixed_spec(op)
                path,op_path=workspace/f"{op}.json",workspace/f"{op}.op.json"
                path.write_text(json.dumps(spec),encoding="utf-8")
                op_path.write_text(json.dumps(_operation(spec,focus="SYNTHETIC_RAW_SUPPORT",journal=receipt["search_key_sha256"],
                    market=receipt["market_evidence_epoch_sha256"],text=f"Synthetic {op} support",cap={"main":1,"adaptive":0,"preview":1})),encoding="utf-8")
                cli=_forge()
                original=pq.read_table
                def trapped(*args,**kwargs):
                    table=original(*args,**kwargs)
                    if "typed_value" in table.column_names:
                        self.assertIsNotNone(kwargs.get("filters"))
                        self.assertTrue(all(r["point_id"] in {"X300","Y900"} for r in table.to_pylist()))
                    return table
                kwargs=dict(explicit_data_root=root,spec_path=path,binding_path=None,census_path=None,observations_path=None,
                    cohort_partitions=None,prior_preview_hash=None,store_root=root,journal_scope=receipt["search_key_sha256"],operation_path=op_path)
                with mock.patch.object(pq,"read_table",side_effect=trapped),contextlib.redirect_stdout(io.StringIO()) as out:
                    code=cli.cmd_discovery_preview(ROOT,**kwargs)
                self.assertEqual(code,0,out.getvalue())
                preview=json.loads(out.getvalue().splitlines()[-1]);outputs.append(preview)
                pooled=preview["support_summary"]["pooled"]
                self.assertEqual((pooled["base_x_n"],pooled["universe"],pooled["decision_eligible_n"]),(48,{"PASS":40,"FAIL":4,"UNKNOWN":4},36))
                self.assertEqual((pooled["joint_calculable_n"],pooled["joint_unavailable_n"]),(n,36-n))
                self.assertEqual(preview["selected_count"],24)
                self.assertEqual(sum(c["decision_eligible_n"] for c in preview["support_summary"]["by_cohort"]),36)
                inventory=ResearchStore(root).diagnostics().committed_inventory_sha256
                with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",side_effect=AssertionError("cold preview loaded values")),contextlib.redirect_stdout(io.StringIO()) as out:
                    code=_forge().cmd_discovery_preview(ROOT,**kwargs)
                self.assertEqual(code,0,out.getvalue())
                saved=json.loads(out.getvalue().splitlines()[-1])
                self.assertEqual(saved["support_summary"],preview["support_summary"])
                from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
                from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations
                binding=preview["frozen_input"]
                digest=hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
                operation=next(r for r in list_operations(ResearchStore(root)) if r["spec_sha256"]==validate_temporal_query(spec)["spec_sha256"])
                changed=copy.deepcopy(binding)
                changed[0]["observations_sha256"]="0"*64
                with self.assertRaisesRegex(GroundedDiscoveryError,"PREVIEW_INPUT_IDENTITY_MISMATCH"):
                    temporal.saved_feature_preview(ResearchStore(root),journal_scope=receipt["search_key_sha256"],
                        operation_sha256=operation["operation_sha256"],spec_sha256=digest,binding=changed)
                self.assertFalse(saved["values_loaded"])
                self.assertEqual(ResearchStore(root).diagnostics().committed_inventory_sha256,inventory)
            self.assertNotEqual(outputs[0]["support_summary"]["pooled"]["features"]["holders"],outputs[1]["support_summary"]["pooled"]["features"]["holders"])


class AdmissionTests(unittest.TestCase):
    def test_public_bound_window_refusal_precedes_reservation_and_loader(self):
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge,_operation
        from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_discovery_binding
        with tempfile.TemporaryDirectory() as raw:
            workspace=Path(raw); root=publish_raw(workspace,reversed_window=True)
            pre=run_cli("preflight","--discovery-contract","--owner-focus","SYNTHETIC_BOUND_WINDOW","--format","json",data_root=root)
            self.assertEqual(pre.returncode,0,pre.stdout+pre.stderr)
            receipt=json.loads(pre.stdout)
            spec=mixed_spec()
            spec["decision"]["point_id"]="Y3600"
            spec["target"]["reference_point"]="Y3600"
            spec["features"][0].update(start="Y900",end="Y1800")
            # Textual order is valid; the production-sealed point clocks reverse it.
            validate_temporal_query(spec)
            binding=resolve_published_discovery_binding(root)["cohorts"]
            self.assertTrue(all(b["schedule_point_due_offset_seconds"]["Y900"] > b["schedule_point_due_offset_seconds"]["Y1800"] for b in binding))
            paths=[workspace/f"window-{name}.json" for name in ("spec","scope","op")]
            scope={"population":"BASE_X","decision_timestamp":"Y3600","target":temporal.temporal_target_label(spec),
                   "estimand":"price_relative_proxy","explanatory_condition":"holders","evidence_surface_mode":"ORDINARY_GROUNDED_DISCOVERY_V1"}
            operation=_operation(spec,focus="SYNTHETIC_BOUND_WINDOW",journal=receipt["search_key_sha256"],
                market=receipt["market_evidence_epoch_sha256"],text="Synthetic incompatible bound window",cap={"main":1,"adaptive":0,"preview":1})
            for path,body in zip(paths,[spec,scope,operation]):path.write_text(json.dumps(body),encoding="utf-8")
            for command in ("main","preview"):
                with self.subTest(command=command),mock.patch("solana_alpha_lab.factory.hfic_ordinary_operation._reserve",side_effect=AssertionError("invalid window reserved")) as reserve, mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",side_effect=AssertionError("invalid window loaded")) as loader,contextlib.redirect_stdout(io.StringIO()) as out:
                    if command=="main":
                        code=_forge().cmd_discovery_execute(ROOT,store_root=root,census_path=None,observations_path=None,binding_path=None,
                            spec_path=paths[0],journal_scope=receipt["search_key_sha256"],candidate_scope_path=paths[1],explicit_data_root=root,operation_path=paths[2])
                    else:
                        code=_forge().cmd_discovery_preview(ROOT,explicit_data_root=root,spec_path=paths[0],binding_path=None,census_path=None,observations_path=None,
                            cohort_partitions=None,prior_preview_hash=None,store_root=root,journal_scope=receipt["search_key_sha256"],operation_path=paths[2])
                self.assertEqual(code,2,out.getvalue());self.assertIn("FEATURE_WINDOW_INVALID",out.getvalue())
                reserve.assert_not_called();loader.assert_not_called()

    def test_public_refusal_precedes_values_and_reservations(self):
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge,_operation
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.hfic_ordinary_operation import _reservations
        from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
        with tempfile.TemporaryDirectory() as raw:
            workspace=Path(raw); root=publish_raw(workspace)
            pre=run_cli("preflight","--discovery-contract","--owner-focus","SYNTHETIC_GUARD","--format","json",data_root=root)
            self.assertEqual(pre.returncode,0,pre.stderr)
            receipt=json.loads(pre.stdout)
            for op,threshold,reason in [("gte",3,"UNIVERSE_NON_DISCRIMINATING_QUESTION"),("lt",50,"UNIVERSE_IMPOSSIBLE_QUESTION")]:
                spec=mixed_spec();spec["features"]=[{"name":"h","op":"point_value","field_id":HOLDER,"point":"Y900"}]
                spec["all"]=[{"feature":"h","op":op,"value":threshold}]
                operation=_operation(spec,focus="SYNTHETIC_GUARD",journal=receipt["search_key_sha256"],market=receipt["market_evidence_epoch_sha256"],
                                     text=f"Synthetic guard {op}",cap={"main":1,"adaptive":0,"preview":0})
                paths=[workspace/f"{op}-{name}.json" for name in ("spec","scope","op")]
                scope={"population":"BASE_X","decision_timestamp":"Y900","target":temporal.temporal_target_label(spec),
                       "estimand":"price_relative_proxy","explanatory_condition":"h","evidence_surface_mode":"ORDINARY_GROUNDED_DISCOVERY_V1"}
                for path,body in zip(paths,[spec,scope,operation]):path.write_text(json.dumps(body),encoding="utf-8")
                with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",side_effect=AssertionError("guard loaded values")) as loader,contextlib.redirect_stdout(io.StringIO()) as out:
                    code=_forge().cmd_discovery_execute(ROOT,store_root=root,census_path=None,observations_path=None,binding_path=None,
                        spec_path=paths[0],journal_scope=receipt["search_key_sha256"],candidate_scope_path=paths[1],explicit_data_root=root,operation_path=paths[2])
                self.assertEqual(code,2,out.getvalue()); self.assertIn(reason,out.getvalue()); loader.assert_not_called()
                from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations
                self.assertTrue(all(not _reservations(ResearchStore(root), row["operation_sha256"]) for row in list_operations(ResearchStore(root))))
                self.assertEqual(list_discovery_looks(ResearchStore(root),receipt["search_key_sha256"]),[])
    def test_guard_table_does_not_rewrite_identity(self):
        from solana_alpha_lab.factory.hfic_research_universe_policy import profile_definition
        from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
        policy=profile_definition(50,5000)
        for op,params,reason in [("gte",{"value":3},"UNIVERSE_NON_DISCRIMINATING_QUESTION"),
                                 ("lt",{"value":50},"UNIVERSE_IMPOSSIBLE_QUESTION"),
                                 ("lte",{"value":49},"UNIVERSE_IMPOSSIBLE_QUESTION"),
                                 ("between",{"lower":3,"upper":50},"UNIVERSE_IMPOSSIBLE_QUESTION"),
                                 ("gte",{"value":100},None),("gt",{"value":50},None)]:
            spec=mixed_spec()
            spec["features"]=[{"name":"h","op":"point_value","field_id":HOLDER,"point":"Y900"}]
            spec["all"]=[{"feature":"h","op":op,**params}]
            body=validate_temporal_query(spec)["scientific_body"]
            if reason:
                with self.subTest(op=op),self.assertRaises(GroundedDiscoveryError) as error:
                    temporal.universe_question_guard(body,policy)
                self.assertEqual(error.exception.code,reason)
            else:
                self.assertEqual(temporal.universe_question_guard(body,policy),[])
        spec=mixed_spec()
        spec["features"].append({"name":"h","op":"point_value","field_id":HOLDER,"point":"Y900"})
        spec["all"].append({"feature":"h","op":"gte","value":50})
        original=copy.deepcopy(spec); sha=validate_temporal_query(spec)["spec_sha256"]
        warnings=temporal.universe_question_guard(validate_temporal_query(spec)["scientific_body"],policy)
        self.assertEqual(len(warnings),1);self.assertEqual(spec,original)
        self.assertEqual(validate_temporal_query(spec)["spec_sha256"],sha)
        spec["features"][-1]["point"]="X300"
        self.assertEqual(temporal.universe_question_guard(validate_temporal_query(spec)["scientific_body"],policy),[])


def prepare_scientific_path(test, workspace, *, focus="SYNTHETIC_RAW_SCIENTIFIC_PATH"):
    """Public production composition to freeze; returned objects are production outputs."""
    from tests.test_hfic_cli import run_cli,bind_draft
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge,_operation
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    root=publish_raw(workspace)
    def call(*args):
        done=run_cli(*args,"--format","json",data_root=root)
        test.assertEqual(done.returncode,0,done.stdout+done.stderr)
        return json.loads(done.stdout)
    receipt=call("preflight","--discovery-contract","--owner-focus",focus)
    spec=mixed_spec();spec["query_id"]=focus
    spec["features"].append({"name":"bound_holders","op":"point_value","field_id":HOLDER,"point":"Y900"})
    spec["all"].append({"feature":"bound_holders","op":"gte","value":50})
    scope={"population":"BASE_X","decision_timestamp":"Y900","target":temporal.temporal_target_label(spec),
           "estimand":"price_relative_proxy","explanatory_condition":"holders","evidence_surface_mode":"ORDINARY_GROUNDED_DISCOVERY_V1"}
    operation=_operation(spec,focus=focus,journal=receipt["search_key_sha256"],market=receipt["market_evidence_epoch_sha256"],
                         text="One synthetic mixed raw question through production lifecycle",cap={"main":1,"adaptive":0,"preview":1},completion="SCIENTIFIC_TERMINAL")
    paths=[workspace/f"native-{name}.json" for name in ("spec","scope","op")]
    for path,body in zip(paths,[spec,scope,operation]):path.write_text(json.dumps(body),encoding="utf-8")
    cli=_forge()
    kwargs=dict(store_root=root,census_path=None,observations_path=None,binding_path=None,spec_path=paths[0],journal_scope=receipt["search_key_sha256"],
                candidate_scope_path=paths[1],explicit_data_root=root,operation_path=paths[2])
    with mock.patch.object(cli,"emit",side_effect=RuntimeError("reply-lost")) as lost:
        with test.assertRaisesRegex(RuntimeError,"reply-lost"):cli.cmd_discovery_execute(ROOT,**kwargs)
    test.assertEqual(len(list_discovery_looks(ResearchStore(root),receipt["search_key_sha256"])),1)
    with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",side_effect=AssertionError("saved readback loaded values")),mock.patch.object(temporal,"execute_temporal_discovery",side_effect=AssertionError("saved readback evaluated")),contextlib.redirect_stdout(io.StringIO()) as out:
        code=_forge().cmd_discovery_execute(ROOT,**kwargs)
    test.assertEqual(code,0,out.getvalue()); evidence=json.loads(out.getvalue().splitlines()[-1])
    test.assertFalse(evidence["values_loaded"]);test.assertFalse(evidence["queries"][0]["new_look"])
    test.assertEqual(lost.call_args.args[0]["query_warnings"][0]["reason_code"],"REDUNDANT_UNIVERSE_CONJUNCT")
    test.assertEqual(evidence["spec_sha256"],validate_temporal_query(spec)["spec_sha256"])
    result=evidence["result"]
    test.assertEqual(result["decision_eligible_n"],36)
    fresh=call("preflight","--discovery-contract","--owner-focus",focus)
    identity=temporal.temporal_holder_claim_identity(result)
    source=json.loads((ROOT/"tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
    card={**source["candidates"][0],**scope,**identity,
          "label":focus,"claim_form":"PREDICTIVE","novelty_class":"REFORMULATION",
          "claim":"Fixed raw holder growth may discriminate later PRICE_RELATIVE_PROXY on the exact decision population; synthetic acceptance only.",
          "mechanism":"Increasing participation may precede a later price direction; activity and staleness remain confounders, causality UNKNOWN.",
          "mundane_alternative":"Activity and price staleness can produce the same association without predictive holder information.",
          "actor_counterparty":"BASE_X holders and subsequent buyers; no causal actor identification.",
          "state_transition":"X300 to Y900 holder growth -> fixed Y14400 price mark, no execution claim.",
          "proposed_method":"One frozen mixed raw recipe, no retuning, PRICE_RELATIVE_PROXY and existing cost proxy only.",
          "negative_control":"SAME_DECISION_ELIGIBLE baseline; no claim of independence or alpha.",
          "confounders":["activity","price staleness"],"required_capability_ids":[temporal.TEMPORAL_CAPABILITY_ID],
          "required_feature_ids":[],"cheapest_falsifier":"One frozen raw mixed PRICE_RELATIVE_PROXY contrast against SAME_DECISION_ELIGIBLE; no threshold sweep.",
          "disconfirming_prediction":"The fixed holder dynamics condition has no supported price contrast against the decision baseline.",
          "decision_unlocked":"Whether a separately authorized chronological validation is justified; synthetic acceptance grants no science permission.",
          "kill_if":["PIT lineage fails","No supported directional contrast"],
          "prior_work_refs":[],"material_difference_from_prior":"New raw holder dynamics, no prior exact close claimed.",
          "unresolved_requirements":[]}
    draft=bind_draft({**source,"owner_focus":focus,"candidates":[card]},fresh)
    draft.pop("runner_up_candidate_ref",None);draft.pop("strongest_rejected_alternative",None)
    draft["selected_candidate_ref"]=card["label"];draft["grounded_evidence"]=evidence
    from solana_alpha_lab.factory.hfic_grounded_discovery import assert_computed_grounded_evidence, GroundedDiscoveryError
    for key,value in (("op","return_ratio"),("start","Y900"),("end","Y1800"),("field_id",PRICE)):
        tampered=copy.deepcopy(evidence)
        next(f for f in tampered["result"]["experiment_recipe"]["spec"]["scientific_body"]["features"] if f["name"]=="holders")[key]=value
        with test.assertRaisesRegex(GroundedDiscoveryError,"GROUNDED_RESULT_MISMATCH"):
            assert_computed_grounded_evidence(ResearchStore(root),tampered,expected_journal_scope=receipt["search_key_sha256"])
    for part,key,value in (("predicates","value",2),("target","exit_point","Y7200")):
        tampered=copy.deepcopy(evidence);body=tampered["result"]["experiment_recipe"]["spec"]["scientific_body"]
        (body[part][0] if isinstance(body[part],list) else body[part])[key]=value
        with test.assertRaisesRegex(GroundedDiscoveryError,"GROUNDED_RESULT_MISMATCH"):
            assert_computed_grounded_evidence(ResearchStore(root),tampered,expected_journal_scope=receipt["search_key_sha256"])
    draft_path,receipt_path=workspace/"native-draft.json",workspace/"native-preflight.json"
    draft_path.write_text(json.dumps(draft),encoding="utf-8");receipt_path.write_text(json.dumps(fresh),encoding="utf-8")
    # Public freeze must still bind actual evidence even with an accepted capability.
    before=ResearchStore(root).diagnostics().committed_inventory_sha256
    for fault in ("unbound", "tampered", "unknown_cap"):
        refused=copy.deepcopy(draft)
        if fault == "unbound":
            refused.pop("grounded_evidence")
        elif fault == "tampered":
            refused["grounded_evidence"]["result"]["experiment_recipe"]["spec"]["scientific_body"]["features"][0]["op"]="return_ratio"
        else:
            refused["candidates"][0]["required_capability_ids"]=["CAP-UNKNOWN"]
        bad_path=workspace/f"refused-{fault}.json"
        bad_path.write_text(json.dumps(refused),encoding="utf-8")
        denied=run_cli("freeze","--draft",str(bad_path),"--preflight-receipt",str(receipt_path),"--format","json",data_root=root)
        test.assertNotEqual(denied.returncode,0,denied.stdout+denied.stderr)
        reason=json.loads(denied.stdout)["reason_code"]
        test.assertIn(reason,{"GROUNDED_EVIDENCE_REQUIRED","GROUNDED_RESULT_MISMATCH","FORGE_CANDIDATE_UNKNOWN_CAPABILITY_ID"},denied.stdout)
        test.assertEqual(ResearchStore(root).diagnostics().committed_inventory_sha256,before)
    persisted=call("persist-draft","--draft",str(draft_path),"--preflight-receipt",str(receipt_path),"--representation-id","BASE")
    resume=call("preflight","--discovery-contract","--owner-focus",focus)
    receipt_path.write_text(json.dumps(resume),encoding="utf-8")
    frozen=call("freeze","--draft",str(draft_path),"--preflight-receipt",str(receipt_path))
    packet=frozen["critic_input_packet"]
    from solana_alpha_lab.factory.hfic_control_integrity import fast_lane_availability_denial_codes
    selected=packet["selected_candidate"]
    test.assertEqual(selected["required_feature_ids"],[])
    test.assertEqual(selected["grounding"]["terminal"],"GROUNDED")
    test.assertEqual(selected["grounding"]["feature_bindings"],[])
    test.assertEqual(selected["grounding"]["unresolved_requirements"],[])
    test.assertEqual(selected["grounding"]["capability_bindings"],[{"capability_id":temporal.TEMPORAL_CAPABILITY_ID,"accepted":True,"authority_granted":False}])
    test.assertEqual(fast_lane_availability_denial_codes(selected),[])
    test.assertEqual(packet["selected_candidate"]["primary_x"],identity["primary_x_family"])
    test.assertEqual(packet["grounded_evidence"]["descriptive_readout"]["scientific_identity"],identity)
    packet_path=workspace/"native-critic-packet.json"
    packet_path.write_text(json.dumps(packet,sort_keys=True,indent=2),encoding="utf-8")
    (workspace/"native-presearch-packet.json").write_text(json.dumps(receipt["forge_context_packet"],sort_keys=True,indent=2),encoding="utf-8")
    export={"data_root":str(root),"focus":focus,"journal":receipt["search_key_sha256"],"evidence":evidence,"frozen":frozen,
            "spec":spec,"packet_path":str(packet_path),"evaluator_calls_saved_readback":0,"persisted_draft":persisted}
    (workspace/"native-context.json").write_text(json.dumps(export,sort_keys=True,indent=2),encoding="utf-8")
    return export


def finish_scientific_path(test, workspace, context, critic):
    from tests.test_hfic_cli import run_cli
    from tests.test_fast_lane_classifier import experiment_spec
    from solana_alpha_lab.factory.research_store import ResearchStore
    root=Path(context["data_root"])
    def call(*args):
        done=run_cli(*args,"--format","json",data_root=root)
        test.assertEqual(done.returncode,0,done.stdout+done.stderr)
        return json.loads(done.stdout)
    critic_path=workspace/"native-critic-result.json"
    critic_path.write_text(json.dumps(critic),encoding="utf-8")
    finished=call("finalize","--session-id",context["frozen"]["session_id"],"--critic-result",str(critic_path))
    if finished.get("session_state")=="AWAITING_CLASSIFICATION":
        packet={"experiment_spec":experiment_spec(),"hypothesis_definition_sha256":context["frozen"]["selected_definition_sha256"]}
        packet["experiment_spec"]["required_feature_ids"]=context["frozen"]["critic_input_packet"]["selected_candidate"]["required_feature_ids"]
        path=workspace/"native-classification.json";path.write_text(json.dumps(packet),encoding="utf-8")
        finished=call("classify","--session-id",context["frozen"]["session_id"],"--experiment-spec",str(path))
    owner=call("forge-run","--owner-focus",context["focus"],"--persist")
    before_cold=ResearchStore(root).diagnostics().committed_inventory_sha256
    with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",side_effect=AssertionError("cold values read")),mock.patch.object(temporal,"execute_temporal_discovery",side_effect=AssertionError("cold evaluator call")):
        cold=call("forge-run","--owner-focus",context["focus"],"--no-write")
    test.assertEqual(ResearchStore(root).diagnostics().committed_inventory_sha256,before_cold)
    test.assertEqual(cold["ordinary_operation"]["effective_state"],"COMPLETED",cold)
    before=ResearchStore(root).diagnostics().committed_inventory_sha256
    with mock.patch.object(temporal,"execute_temporal_discovery",wraps=temporal.execute_temporal_discovery) as evaluator:
        replay=temporal.run_registered_fixed_time_proxy(root=ROOT,registry_path=ROOT/"configs/experiment_capability_registry_v2.yaml",
            recipe=context["evidence"]["result"]["experiment_recipe"],data_root=root)
        test.assertEqual(evaluator.call_count,1)
    test.assertEqual(replay["summary"],context["evidence"]["result"])
    test.assertEqual(ResearchStore(root).diagnostics().committed_inventory_sha256,before)
    return {"finalized":finished,"owner":owner,"cold":cold,"registered_replay_evaluator_calls":1,"cold_readback_evaluator_calls":0,"cold_readback_value_loads":0}


class ScientificPathTests(unittest.TestCase):
    def test_serialized_scientific_identity_preserves_path_rejection(self):
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge
        cli=_forge()
        body={"primary_x_family":json.dumps({"features":mixed_spec()["features"]})}
        cli._assert_no_path_leak({"payload_canonical":json.dumps(body)})
        for path in (r"C:\private\capture",r"\private\capture",r"\\server\share\capture"):
            body={"primary_x_family":json.dumps({"features":[],"path":path})}
            with self.subTest(path=path),self.assertRaisesRegex(cli.HficCliError,"PHYSICAL_PATH_LEAK"):
                cli._assert_no_path_leak({"payload_canonical":json.dumps(body)})

    def test_public_raw_recovery_and_owner_final(self):
        from tests.test_hfic_cli import critic_result_from_packet_only
        from tests.test_forge_ordinary_operation_lifecycle_v1 import _cycle
        with tempfile.TemporaryDirectory() as raw:
            workspace=Path(raw)
            context=prepare_scientific_path(self,workspace)
            critic=critic_result_from_packet_only(context["frozen"]["critic_input_packet"],terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
            critic["non_claims"].append("SCRIPTED_CRITIC_MECHANICAL")
            result=finish_scientific_path(self,workspace,context,critic)
            next_cycle=_cycle(self,Path(context["data_root"]),workspace,"SYNTHETIC_LEGACY_AFTER_RAW")
            self.assertTrue(next_cycle["owner_final"])


if __name__ == "__main__":
    print(json.dumps(future_prefix_witness(), sort_keys=True, indent=2))
