"""Holder point feature: closed policy and production owner path, disposable data only."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import sys
import contextlib
import io
import os
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
from solana_alpha_lab.factory.hfic_grounded_discovery import (
    GroundedDiscoveryError, execute_discovery_from_rows,
)
from tests.test_hfic_temporal_discovery_v1 import (
    ANCHOR, LIQ, PRICE, _binding, _census, _path, _spec,
)

ROOT = Path(__file__).resolve().parents[1]
HOLDER = "FIELD-HOLDER-COUNT-001"
FOCUS = "EARLY_HOLDER_STATE_TO_PRICE_PATH_15M_TO_4H"


def holder_spec(**updates):
    return _spec(
        tier="SIMPLE_SCREEN", query_id=FOCUS,
        decision={"point_id": "Y900", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        features=[{"name": "holder_y900", "op": "point_value", "field_id": HOLDER, "point": "Y900"}],
        all=[{"feature": "holder_y900", "op": "gte", "value": 3}],
        target={"kind": "PRICE_RELATIVE_PROXY", "reference_point": "Y900", "exit_point": "Y14400", "field_id": PRICE},
        **updates,
    )


def row(mint, point, field, value, *, state="OBSERVED", late=0):
    offset = {"X300": 300, "Y900": 900, "Y14400": 14400}[point]
    stamp = (ANCHOR + timedelta(seconds=offset + 300 + late)).isoformat()
    return {"mint": mint, "cohort_id": _binding()[0]["cohort_id"],
            "release_id": _binding()[0]["release_id"], "point_id": point,
            "field_id": field, "state": state, "event_time": stamp,
            "first_reliable_available_at": stamp, "typed_value": value}


def synthetic_rows():
    census, observations = [], []
    for mint, value, state, late, exit_price in (
        ("match", 3, "OBSERVED", 0, 1.2),
        ("missing", None, "FIELD_ABSENT", 0, 1.5),
        ("zero", 0, "OBSERVED", 0, 0.5),
        ("late", 8, "OBSERVED", 1, 1.8),
    ):
        census.append(_census(mint))
        observations.extend([row(mint, "X300", LIQ, 1000), row(mint, "Y900", PRICE, 1),
                             row(mint, "Y900", HOLDER, value, state=state, late=late),
                             row(mint, "Y14400", PRICE, exit_price)])
    return census, observations


def old_cases():
    return {
        "price": _spec(),
        "liquidity": _spec(tier="SIMPLE_SCREEN", features=[{"name": "liq", "op": "point_value", "field_id": LIQ, "point": "Y3600"}], all=[{"feature": "liq", "op": "gte", "value": 3}]),
    }


class HolderPolicyTests(unittest.TestCase):
    def test_preview_mixed_point_deadline_matches_canonical_feature(self):
        from solana_alpha_lab.factory.hfic_grounded_discovery import _grouped_cells

        binding = _binding()
        binding[0]["schedule_point_due_offset_seconds"] = {"X300": 300, "Y900": 900, "Y1800": 1800}
        binding[0]["schedule_point_lateness"] = {"X300": 300, "Y900": 1800, "Y1800": 300}
        self.assertEqual(temporal._clock(binding[0], "Y900", 300), (900, 1800))
        feature = {"name": "h", "op": "point_value", "field_id": HOLDER, "point": "Y900"}
        spec = {"decision": {"point_id": "Y1800"}, "schedule": {"points": ["Y900", "Y1800"], "lateness_seconds": 300}, "features": [feature], "seed": "mixed-clock"}
        observations = [row("match", "X300", LIQ, 1000), row("match", "Y900", HOLDER, 3, late=1300)]
        preview = temporal.build_feature_preview([_census("match")], observations, spec, binding)
        value, _lineage = temporal._feature_value_with_lineage(_grouped_cells(observations), cohort=binding[0]["cohort_id"],
            release=binding[0]["release_id"], mint="match", anchor=ANCHOR, feature=feature, lateness=300,
            decision_deadline=temporal._deadline_for(ANCHOR, "Y1800", 300),
            due_offset_for=lambda point: temporal._clock(binding[0], point, 300)[0],
            lateness_for=lambda point: temporal._clock(binding[0], point, 300)[1])
        self.assertIsNone(value)
        self.assertIsNone(preview["examples"][0]["feature_values"]["h"])
        self.assertEqual(preview["examples"][0]["feature_status"]["h"], "ABSENT")

    def test_preview_default_clock_normalization_matches_query(self):
        spec = {"decision": {"point_id": "Y900"}, "schedule": {"points": ["Y900"], "lateness_seconds": 300}, "features": holder_spec()["features"], "seed": "default-clock"}
        census, observations = synthetic_rows()
        base = temporal.build_feature_preview(census, observations, spec, _binding())
        for default in (None, ""):
            query = holder_spec(schedule={"lateness_seconds": 300, "observation_clock_policy": default})
            self.assertEqual(temporal.validate_temporal_query(query)["scientific_body"]["observation_clock_policy"], temporal.OBSERVATION_CLOCK_EVENT_TIME_V1)
            variant = copy.deepcopy(spec)
            variant["schedule"]["observation_clock_policy"] = default
            self.assertEqual(temporal.build_feature_preview(census, observations, variant, _binding()), base)

    def test_numeric_card_labels_are_lossless_and_wrong_threshold_refuses(self):
        from solana_alpha_lab.factory.hfic_session import _bind_selected_look, HficSessionError

        census, observations = synthetic_rows()
        identities = []
        results = []
        for threshold in (3, 3.0000001, 1000001, 1000002):
            spec = holder_spec()
            spec["all"][0]["value"] = threshold
            result = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
            results.append(result)
            identities.append(temporal.temporal_holder_claim_identity(result))
        self.assertEqual(len({identity["primary_x_family"] for identity in identities}), 4)
        self.assertEqual((results[0]["matched_n"], results[1]["matched_n"]), (1, 0))
        self.assertNotEqual(results[0]["spec_sha256"], results[1]["spec_sha256"])
        with self.assertRaises(HficSessionError) as refusal:
            _bind_selected_look({"result": results[1], "candidate_scope": identities[1]}, identities[0], store=None)
        self.assertEqual(str(refusal.exception), "LOOK_SCOPE_CONTRADICTION")

    def test_feature_only_cli_refuses_policy_before_loader(self):
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge

        cli = _forge()
        spec = {"decision": {"point_id": "Y900"}, "schedule": {"points": ["Y900"], "lateness_seconds": 300}, "seed": "negative-policy"}
        bad_features = [
            {"name": "h", "op": "ratio", "field_id": HOLDER, "numerator": "Y900", "denominator": "X300"},
            {"name": "h", "op": "point_value", "field_id": HOLDER, "point": "Y1800"},
        ]
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "preview.json"
            for feature, code in zip(bad_features, ("FEATURE_OP_UNSUPPORTED", "FEATURE_AFTER_DECISION")):
                path.write_text(json.dumps({**spec, "features": [feature]}), encoding="utf-8")
                with self.subTest(feature=feature), mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows", side_effect=AssertionError("invalid preview loaded values")) as loader, contextlib.redirect_stderr(io.StringIO()) as output:
                    status = cli.cmd_discovery_preview(ROOT, explicit_data_root=Path(raw), spec_path=path, binding_path=None,
                        census_path=None, observations_path=None, cohort_partitions=None, prior_preview_hash=None)
                self.assertEqual(status, 1)
                self.assertIn(code, output.getvalue())
                loader.assert_not_called()

    def test_holder_is_point_only_and_projection_is_query_local(self):
        self.assertIn(HOLDER, temporal.validate_temporal_query(holder_spec())["decision_fields"])
        self.assertNotIn(HOLDER, temporal.validate_temporal_query(_spec())["decision_fields"])
        for op, params in (
            ("ratio", {"numerator": "Y900", "denominator": "X300"}),
            ("return_ratio", {"start": "X300", "end": "Y900"}),
            ("drawdown_from_grid_max", {"points": ["X300", "Y900"], "at": "Y900"}),
            ("rebound_from_grid_min", {"points": ["X300", "Y900"], "at": "Y900"}),
        ):
            feature = {"name": "holder_y900", "field_id": HOLDER, "op": op, **params}
            spec = holder_spec()
            spec["features"] = [feature]
            with self.subTest(op=op), mock.patch.object(temporal, "ALLOWED_FIELDS", temporal.ALLOWED_FIELDS | {HOLDER}):
                with self.assertRaises(GroundedDiscoveryError):
                    temporal.validate_temporal_query(spec)
        spec = holder_spec()
        spec["target"]["field_id"] = HOLDER
        with self.assertRaises(GroundedDiscoveryError):
            temporal.validate_temporal_query(spec)
        spec = holder_spec()
        spec["features"][0]["point"] = "Y1800"
        with self.assertRaises(GroundedDiscoveryError) as stop:
            temporal.validate_temporal_query(spec)
        self.assertEqual(stop.exception.code, "FEATURE_AFTER_DECISION")

    def test_pit_missing_zero_late_and_price_present_holder_absent(self):
        census, observations = synthetic_rows()
        result = execute_discovery_from_rows(census, observations, holder_spec(), _binding())["summary"]
        self.assertEqual(result["matched_n"], 1)
        self.assertEqual(result["observed_target_n"], 1)
        self.assertAlmostEqual(result["mean_target"], 0.2)
        self.assertEqual(result["feature_unknown_n"], 2)
        self.assertEqual(result["calculation_version"], temporal.TEMPORAL_CALCULATION_VERSION_V5)
        self.assertIn("downside", result)
        from solana_alpha_lab.factory.hfic_grounded_discovery import _grouped_cells
        zero = temporal._cell(_grouped_cells(observations), (_binding()[0]["cohort_id"], _binding()[0]["release_id"], "zero", "Y900", HOLDER), temporal._deadline_for(ANCHOR, "Y900", 300))
        self.assertEqual((zero["status"], zero["value"]), ("OBSERVED", 0))

    def test_old_frozen_specs_and_results_are_exact(self):
        for name, spec in old_cases().items():
            golden = json.loads((ROOT / f"tests/fixtures/forge_holder_point_v1/old_{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(temporal.canonical_temporal_spec(spec), golden["canonical_spec"])
            self.assertEqual(temporal.validate_temporal_query(spec)["spec_sha256"], golden["spec_sha256"])
            result = execute_discovery_from_rows([_census("old")], _path("old", [1, 1.5, 2, 1.6], (10000, 9000), 1.92), spec, _binding())["summary"]
            self.assertEqual(result, golden["result"])

    def test_snapshot_lineage_and_same_occurrence_are_preserved(self):
        census, observations = synthetic_rows()
        observations = temporal.stamp_provider_reported_snapshot_transport(observations)
        for item in observations:
            item["call_occurrence_id"] = hashlib.sha256(f"{item['mint']}:{item['point_id']}".encode()).hexdigest()
        spec = holder_spec(schedule={"lateness_seconds": 300, "observation_clock_policy": temporal.OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1})
        result = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        self.assertEqual(result["matched_n"], 1)
        damaged = copy.deepcopy(observations)
        for item in damaged:
            if item["field_id"] == HOLDER and item["mint"] == "match":
                item.pop("call_occurrence_id")
        blocked = execute_discovery_from_rows(census, damaged, spec, _binding())["summary"]
        self.assertEqual(blocked["matched_n"], 0)
        self.assertGreater(blocked["feature_unknown_n"], result["feature_unknown_n"])
        self.assertIn("SNAPSHOT_", json.dumps(blocked))

    def test_duplicate_holder_conflict_uses_existing_integrity_owner(self):
        census, observations = synthetic_rows()
        duplicate = dict(next(item for item in observations if item["mint"] == "match" and item["field_id"] == HOLDER))
        duplicate["typed_value"] = 9
        result = execute_discovery_from_rows(census, [*observations, duplicate], holder_spec(), _binding())["summary"]
        self.assertEqual(result["matched_n"], 0)
        self.assertEqual(result["feature_unknown_n"], 3)
        from solana_alpha_lab.factory.hfic_grounded_discovery import _grouped_cells
        conflict = temporal._cell(_grouped_cells([*observations, duplicate]), (_binding()[0]["cohort_id"], _binding()[0]["release_id"], "match", "Y900", HOLDER), temporal._deadline_for(ANCHOR, "Y900", 300))
        self.assertEqual(conflict["status"], "CONFLICT")

    def test_forbidden_holder_queries_never_touch_rows(self):
        class UnreadableRows:
            def __iter__(self):
                raise AssertionError("invalid query read values")
        negatives = []
        for op, params in (("ratio", {"numerator": "Y900", "denominator": "X300"}),
                           ("return_ratio", {"start": "X300", "end": "Y900"}),
                           ("drawdown_from_grid_max", {"points": ["X300", "Y900"], "at": "Y900"}),
                           ("rebound_from_grid_min", {"points": ["X300", "Y900"], "at": "Y900"})):
            spec = holder_spec()
            spec["features"] = [{"name": "holder_y900", "field_id": HOLDER, "op": op, **params}]
            negatives.append(spec)
        target = holder_spec()
        target["target"]["field_id"] = HOLDER
        negatives.append(target)
        future = holder_spec()
        future["features"][0]["point"] = "Y1800"
        negatives.append(future)
        with mock.patch.object(temporal, "ALLOWED_FIELDS", temporal.ALLOWED_FIELDS | {HOLDER}):
            for spec in negatives:
                with self.subTest(spec=spec), self.assertRaises(GroundedDiscoveryError):
                    execute_discovery_from_rows(UnreadableRows(), UnreadableRows(), spec, [])


def publish_holder(workspace):
    """Synthetic transport input; publication, hashes and binding are production-owned."""
    from tests import test_hfic_temporal_production_runner_v1 as runner
    from tests.test_live_cohort_discovery_release_series import _snapshot_for_week, _obs, CAMPAIGN_STARTS
    from solana_alpha_lab.factory.observation_schedule import schedule_sha256, validate_observation_schedule

    schedule = runner._schedule()
    schedule.pop("schedule_sha256")
    schedule["y_points"].append({"point_id": "Y14400", "due_offset_seconds": 14400,
        "allowed_lateness_seconds": runner.DOCUMENT_LATENESS, "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"]})
    schedule = validate_observation_schedule(schedule, root=ROOT)
    schedule["schedule_sha256"] = schedule_sha256(schedule)

    def snapshot(week):
        snapshot = _snapshot_for_week(week)
        anchor = CAMPAIGN_STARTS + timedelta(days=7 * week)
        admission = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
        template = snapshot["members"][0]
        snapshot["members"], snapshot["observations"] = [], []
        for i, holder in enumerate((3, None, 0, 6)):
            mint = f"holder-w{week}-{i}"
            snapshot["members"].append({**template, "mint": mint, "candidate_state": "X_ELIGIBLE"})
            for point, field, value in (("X300", LIQ, 1000), ("X300", PRICE, 1), ("Y900", PRICE, 1),
                                        ("Y900", HOLDER, holder), ("Y14400", PRICE, 1.2 if i == 0 else 1.0)):
                item = _obs(mint, point, admission, missing=value is None)
                offset = {"X300": 300, "Y900": 900, "Y14400": 14400}[point]
                stamp = (anchor + timedelta(seconds=offset + runner.DOCUMENT_LATENESS)).strftime("%Y-%m-%dT%H:%M:%SZ")
                item.update(field_id=field, typed_value=None if value is None else str(value), event_time=stamp,
                            first_reliable_available_at=stamp, missing_reason="FIELD_ABSENT" if value is None else None)
                snapshot["observations"].append(item)
        stamped = temporal.stamp_provider_reported_snapshot_transport(snapshot["observations"])
        for item in stamped:
            item["call_occurrence_id"] = hashlib.sha256(f"{item['mint']}:{item['point_id']}".encode()).hexdigest()
        snapshot["observations"] = stamped
        return snapshot

    data_root = workspace / "rdp"
    with mock.patch.object(runner, "_snapshot_for_week", side_effect=snapshot), mock.patch.object(runner, "_schedule", return_value=schedule):
        for week in range(4):
            runner._publish(data_root, workspace, week=week)
    return data_root


class HolderVerticalTests(unittest.TestCase):
    def test_public_full_query_preview_accepts_default_clock_spellings(self):
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation
        from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS
        from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = publish_holder(workspace)
            pre = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root)
            self.assertEqual(pre.returncode, 0, pre.stdout + pre.stderr)
            receipt = json.loads(pre.stdout)
            journal, market = receipt["search_key_sha256"], receipt["market_evidence_epoch_sha256"]
            previews = []
            for default in (None, ""):
                spec = holder_spec(schedule={"lateness_seconds": DOCUMENT_LATENESS, "observation_clock_policy": default})
                spec_path, op_path = workspace / "spec.json", workspace / "operation.json"
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                op_path.write_text(json.dumps(_operation(spec, focus=FOCUS, journal=journal, market=market,
                    text="Synthetic two-spelling default-clock preview only", cap={"main": 0, "adaptive": 0, "preview": 2})), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = _forge().cmd_discovery_preview(ROOT, explicit_data_root=data_root, spec_path=spec_path, binding_path=None,
                        census_path=None, observations_path=None, cohort_partitions=None, prior_preview_hash=None,
                        store_root=data_root, journal_scope=journal, operation_path=op_path)
                self.assertEqual(code, 0, output.getvalue())
                previews.append(json.loads(output.getvalue().splitlines()[-1]))
            self.assertEqual(previews[0]["preview_sha256"], previews[1]["preview_sha256"])
            self.assertEqual(list_discovery_looks(ResearchStore(data_root), journal), [])

    def test_public_preview_discovery_replay_packets_and_registered_capability(self):
        from tests.test_hfic_cli import bind_draft, run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation
        from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            load_admitted_partition_rows, list_discovery_looks, format_discovery_readout,
        )
        from solana_alpha_lab.factory.hfic_session import freeze_draft, HficSessionError
        from solana_alpha_lab.factory.research_store import ResearchStore
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = publish_holder(workspace)
            pre = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root)
            self.assertEqual(pre.returncode, 0, pre.stdout + pre.stderr)
            receipt = json.loads(pre.stdout)
            journal, market = receipt["search_key_sha256"], receipt["market_evidence_epoch_sha256"]
            spec = holder_spec(schedule={"lateness_seconds": DOCUMENT_LATENESS, "observation_clock_policy": temporal.OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1})
            scope = {"population": "BASE_X", "decision_timestamp": "Y900", "target": temporal.temporal_target_label(spec),
                     "estimand": "price_relative_proxy", "explanatory_condition": "holder_y900", "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
            spec_path, scope_path, op_path = (workspace / f"{name}.json" for name in ("spec", "scope", "operation"))
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            op_path.write_text(json.dumps(_operation(spec, focus=FOCUS, journal=journal, market=market,
                text="Synthetic proof of the frozen early holder question", cap={"main": 1, "adaptive": 0, "preview": 1})), encoding="utf-8")
            cli = _forge()
            captured_rows = []
            original_read = pq.read_table
            def read_features(*args, **kwargs):
                table = original_read(*args, **kwargs)
                if "field_id" in table.column_names and "typed_value" in table.column_names:
                    self.assertIsNotNone(kwargs.get("filters"))
                    captured_rows.extend(table.to_pylist())
                return table
            output = io.StringIO()
            with mock.patch.object(pq, "read_table", side_effect=read_features), contextlib.redirect_stdout(output):
                code = cli.cmd_discovery_preview(ROOT, explicit_data_root=data_root, spec_path=spec_path, binding_path=None,
                    census_path=None, observations_path=None, cohort_partitions=None, prior_preview_hash=None,
                    store_root=data_root, journal_scope=journal, operation_path=op_path)
            self.assertEqual(code, 0, output.getvalue())
            preview = json.loads(output.getvalue().splitlines()[-1])
            self.assertFalse(preview["target_included"])
            self.assertTrue(captured_rows)
            self.assertTrue(all(item["point_id"] in {"X300", "Y900"} for item in captured_rows))
            self.assertTrue(any(e["feature_values"]["holder_y900"] is None for e in preview["examples"]))
            self.assertEqual(len(list_discovery_looks(ResearchStore(data_root), journal)), 0)
            # Lose the public reply after the ordinary owner has landed the look.
            # Cold recovery must use the committed output, without evaluator glue.
            with mock.patch.object(cli, "emit", side_effect=RuntimeError("reply-lost")):
                with self.assertRaisesRegex(RuntimeError, "reply-lost"):
                    cli.cmd_discovery_execute(ROOT, store_root=data_root, census_path=None, observations_path=None,
                        binding_path=None, spec_path=spec_path, journal_scope=journal, candidate_scope_path=scope_path,
                        cohort_partitions=None, explicit_data_root=data_root, operation_path=op_path)
            self.assertEqual(len(list_discovery_looks(ResearchStore(data_root), journal)), 1)
            completed = run_cli("discovery-execute", "--store", str(data_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal, "--operation", str(op_path), "--format", "json", data_root=data_root)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            evidence = json.loads(completed.stdout)
            result = evidence["result"]
            self.assertEqual(result["matched_n"], 8)
            self.assertEqual(result["feature_unknown_n"], 4)
            self.assertEqual(result["downside"]["zero_n"], 4)
            self.assertEqual(len(result["by_cohort"]), 4)
            self.assertEqual(result["calculation_version"], temporal.TEMPORAL_CALCULATION_VERSION_V5)
            self.assertEqual(result["cost"]["source_status"], "ASSUMPTION_NOT_CALIBRATED")
            inventory = ResearchStore(data_root).diagnostics().committed_inventory_sha256
            with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_parquet_rows", side_effect=AssertionError("cold replay loaded values")), contextlib.redirect_stdout(io.StringIO()) as replay_output:
                replay_code = cli.cmd_discovery_execute(ROOT, store_root=data_root, census_path=None, observations_path=None,
                    binding_path=None, spec_path=spec_path, journal_scope=journal, candidate_scope_path=scope_path,
                    cohort_partitions=None, explicit_data_root=data_root, operation_path=op_path)
            self.assertEqual(replay_code, 0, replay_output.getvalue())
            replay = json.loads(replay_output.getvalue().splitlines()[-1])
            self.assertEqual(replay["result_sha256"], evidence["result_sha256"])
            self.assertFalse(replay["queries"][0]["new_look"])
            self.assertEqual(ResearchStore(data_root).diagnostics().committed_inventory_sha256, inventory)
            cold = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root)
            self.assertEqual(cold.returncode, 0, cold.stdout + cold.stderr)
            receipt = json.loads(cold.stdout)
            identity = temporal.temporal_holder_claim_identity(result)
            self.assertEqual(identity["primary_x_family"], f"{HOLDER} point_value Y900 >= 3.0")
            self.assertEqual(identity["primary_y"], "PRICE_RELATIVE_PROXY Y900 -> Y14400")
            prompt = receipt["forge_context_packet"]["grounded_readouts"][-1]
            self.assertEqual(prompt["descriptive_readout"]["scientific_identity"], identity)
            source = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
            card = {**source["candidates"][0], **scope, **identity,
                    "label": "HOLDER-POINT-Y900-EXPLORATORY",
                    "novelty_class": "REFORMULATION",
                    "claim_form": "PREDICTIVE",
                    "mundane_alternative": "Activity and price staleness explain the association; holder state may have no positive directional information.",
                    "actor_counterparty": "BASE_X holders and later buyers; ownership concentration unmeasured",
                    "state_transition": "Y900 holder state -> Y14400 relative price mark; association only",
                    "required_feature_ids": [], "unresolved_requirements": ["HOLDER_POINT_FEATURE_EXPLORATORY"],
                    "claim": "The fixed early holder group may have positive later price direction.",
                    "mechanism": "Early holder state may mark participation; activity and price staleness are known confounds, causality unknown.",
                    "prior_work_refs": [],
                    "material_difference_from_prior": "Prior D2 on C1-C4 exposed activity/staleness confounding; this frozen >=3 holder question remains exploratory.",
                    "disconfirming_prediction": "Holder >=3 has no supported positive directional price contrast after descriptive activity decomposition.",
                    "negative_control": "Baseline-minus-matched additive complement only after subset proof; UNKNOWN and missing retain V5 semantics, no second look or new sample.",
                    "alternative_world": "Holder changes mark activity without a positive directional price signal.",
                    "confounders": ["activity", "price staleness", "prior D2 outcome exposure on C1-C4"],
                    "why_not_arbitraged": "UNKNOWN; no alpha or causal mechanism established by this exploratory association.",
                    "pit_leakage_survivorship_risks": ["Unavailable, late, conflicting or bad-lineage cells stay UNKNOWN", "Retain BASE_X denominator and V5 missingness; no survivor-only sample"],
                    "execution_capacity_risks": ["Mark-price proxy has no fill, route, latency, size or realized NetReturn proof", "BASE cost stress is ASSUMPTION_NOT_CALIBRATED"],
                    "missing_or_forward_only_data": ["Holder UNKNOWN remains UNKNOWN; no zero fallback", "Future target support remains a separate real-MAIN question"],
                    "proposed_method": "Exactly one separately authorized MAIN: BASE_X, Y900, holder >=3, PRICE_RELATIVE_PROXY Y900->Y14400; descriptive activity decomposition and additive subset complement only.",
                    "pass_fail_inconclusive_semantics": "Frozen task taxonomy: HOLDER_NO_POSITIVE_ENTRY_EDGE | HOLDER_ACTIVITY_ONLY | HOLDER_DIRECTIONAL_EDGE_COHORT_UNSTABLE | HOLDER_DIRECTIONAL_EDGE_OOS_WORTHY | HOLDER_RESULT_INCONCLUSIVE. C1-C4 EXPLORATORY; no threshold adaptation or automatic promotion.",
                    "cheapest_falsifier": "One separately authorized fixed holder Y900 >=3 PRICE_RELATIVE_PROXY Y900->Y14400 MAIN with frozen taxonomy.",
                    "kill_if": ["PIT holder selection or lineage is invalid; return technical/inconclusive stop, never zero", "Frozen taxonomy finds no positive directional edge or activity-only association"],
                    "decision_unlocked": "Whether the exploratory fixed holder question merits a separately authorized new chronological OOS; no entry edge or promotion.",
                    "required_capability_ids": [temporal.TEMPORAL_CAPABILITY_ID]}
            draft = bind_draft({**source, "owner_focus": FOCUS, "candidates": [card]}, receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            frozen = freeze_draft(draft, preflight_receipt=receipt, store=ResearchStore(data_root), repo_root=ROOT)
            packet = frozen["critic_input_packet"]
            self.assertNotIn("MEU", json.dumps(packet["selected_candidate"]))
            self.assertNotIn("liquidity", json.dumps(packet["selected_candidate"]).lower())
            self.assertEqual(packet["selected_candidate"]["claim_form"], "PREDICTIVE")
            for field in ("confounders", "negative_control", "pass_fail_inconclusive_semantics", "pit_leakage_survivorship_risks", "proposed_method"):
                self.assertEqual(packet["selected_candidate"][field], card[field])
            self.assertEqual(result["baseline"]["observed_n"] - result["observed_target_n"], 8)
            self.assertNotIn("Known-holder <3", packet["selected_candidate"]["negative_control"])
            self.assertEqual(packet["selected_candidate"]["primary_x"], identity["primary_x_family"])
            self.assertEqual(packet["selected_candidate"]["primary_y"], identity["primary_y"])
            self.assertEqual(packet["grounded_evidence"]["descriptive_readout"]["scientific_identity"], identity)
            owner = format_discovery_readout(evidence)
            self.assertEqual(owner["descriptive_readout"]["scientific_identity"], identity)
            for key, bad in (("primary_x_family", identity["primary_x_family"].replace(HOLDER, PRICE)),
                             ("primary_x_family", identity["primary_x_family"].replace("Y900", "Y1800")),
                             ("primary_x_family", identity["primary_x_family"].replace(">= 3", ">= 4")),
                             ("primary_y", identity["primary_y"].replace("Y14400", "Y7200")),
                             ("target", identity["target"].replace("Y14400", "Y7200"))):
                tampered = copy.deepcopy(draft)
                tampered["candidates"][0][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(HficSessionError) as refusal:
                    freeze_draft(tampered, preflight_receipt=receipt, store=ResearchStore(data_root), repo_root=ROOT)
                self.assertEqual(str(refusal.exception), "LOOK_SCOPE_CONTRADICTION")
            offline_inventory = ResearchStore(data_root).diagnostics().committed_inventory_sha256
            offline = temporal.run_registered_fixed_time_proxy(root=ROOT, registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
                recipe=result["experiment_recipe"], data_root=data_root)
            self.assertEqual(offline["spec_sha256"], result["spec_sha256"])
            self.assertEqual(offline["summary"], result)
            self.assertEqual(offline["provider_api_rpc_wss_calls"], 0)
            self.assertFalse(offline["labeled_net_return"])
            self.assertEqual(ResearchStore(data_root).diagnostics().committed_inventory_sha256, offline_inventory)
            export = os.environ.get("FORGE_HOLDER_PROOF_DIR")
            if export:
                out = Path(export)
                out.mkdir(parents=True, exist_ok=True)
                artifacts = {"preview": preview, "discovery": evidence, "prompt_a": prompt,
                             "critic_packet": packet, "owner": owner, "offline": offline,
                             "proof": {"status": "PASS", "namespace": "DISPOSABLE_SYNTHETIC_ONLY",
                                       "interrupted_reply_recovered": True, "loader_free_cold_replay": True,
                                       "tampered_bindings_refused": 5, "main_looks": 1, "real_looks": 0}}
                for name, payload in artifacts.items():
                    (out / f"synthetic_{name}.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
