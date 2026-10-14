"""Real Spec -> source -> prefix -> classifier -> durable HFIC proof.

Scripted Critic is a test entry boundary, never scientific acceptance. Reader
instrumentation observes real reads; source/binder/classifier/storage are real.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tests.fixtures.episode_native_required_outcomes_v1.proof import prepare, load_case
from solana_alpha_lab.factory.episode_required_outcomes import project_episode_required_outcomes, _metadata_status
from solana_alpha_lab.factory.hfic_session import (
    finalize_session, apply_classification, load_session_bundle, run_live_classifier, HficSessionError,
)
from solana_alpha_lab.factory.experiment_spec import validate_experiment_document, ExperimentSpecError
from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
from solana_alpha_lab.factory.lane_classifier import classify_lane
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.opportunity_episodes import point_offset, resolve_point
from tests.test_hfic_session import _critic_result
from tests.test_opportunity_episodes_vertical_v1 import AS_OF
from tests.test_opportunity_episodes_harness_v1 import write_assignment


def membership_view(rows):
    return [{k: r[k] for k in ("episode_id", "decision_eligible", "matched", "comparator")} for r in rows]


class ReaderOracle:
    """Real file boundary, requested columns + exact prefix keys; unsafe canary fails."""
    def __init__(self):
        import pyarrow.parquet as pq
        self.original = pq.read_table
        self.trace = []

    def read(self, path, *args, **kwargs):
        if Path(path).name == "observations.parquet":
            columns, filters = kwargs.get("columns"), kwargs.get("filters", [])
            self.trace.append({"columns": columns, "filters": filters})
            if columns is None or "typed_value" in columns:
                exact = {key: value for key, op, value in filters if op in {"=", "=="}}
                assert columns is not None and "episode_id" in exact and "field_id" in exact and "point_id" in exact, "UNBOUNDED_VALUE_READER"
                assert point_offset(exact["point_id"]) <= 1800, "TARGET_VALUE_READER"
                assert any(key == "first_reliable_available_at" and op == "<=" for key, op, _ in filters), "UNBOUND_PREFIX_CLOCK"
        return self.original(path, *args, **kwargs)


class EpisodeRequiredOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.holder = tempfile.TemporaryDirectory()
        cls.template = Path(os.environ.get("ERNOC_FIXTURE", Path(cls.holder.name) / "native")).resolve()
        prepare(cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.holder.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.plane = self.work / "plane"
        shutil.copytree(self.template / "plane", self.plane)
        self.store = ResearchStore(self.plane)
        self.store.prepare_write_lookup()
        self.spec, self.frozen = load_case(self.template)
        self.definition = self.frozen["selected_definition_sha256"]

    def project(self, spec=None):
        return project_episode_required_outcomes(spec or self.spec, data_root=self.plane, definition_sha256=self.definition)

    def packet(self, spec=None):
        return {"experiment_spec": spec or self.spec, "hypothesis_definition_sha256": self.definition,
                "classifier_evaluated_at": (AS_OF + timedelta(hours=3)).isoformat()}

    def classify(self, spec=None):
        return classify_lane(self.packet(spec), root=ROOT, data_root=self.plane, as_of=AS_OF + timedelta(hours=3))

    def test_list_and_numeric_masks_no_target_reader_and_canaries(self):
        oracle = json.loads((self.template / "membership-oracle.json").read_text())
        before = self.store.diagnostics().committed_inventory_sha256
        for kind in ("LIST_CONTRAST", "MIXED_LIST_NUMERIC"):
            spec, frozen = load_case(self.template, kind)
            recorder = ReaderOracle()
            with patch("pyarrow.parquet.read_table", recorder.read), patch(
                    "solana_alpha_lab.factory.hfic_temporal_discovery._target_projection", side_effect=AssertionError("OUTCOME_EVALUATOR")), patch(
                    "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery", side_effect=AssertionError("MAIN")):
                result = project_episode_required_outcomes(spec, data_root=self.plane, definition_sha256=frozen["selected_definition_sha256"])
            self.assertEqual(membership_view(result["membership"]), oracle)
            self.assertEqual((result["admissions_n"], result["decision_n"], result["matched_n"], result["comparator_n"]), (24, 20, 10, 10))
            self.assertEqual(result["readiness"], "COMPLETE")
            values = [t for t in recorder.trace if "typed_value" in t["columns"]]
            self.assertEqual(sum(len(t["filters"]) == 4 for t in values), result["reads"]["prefix_value_cells_read"])
            self.assertEqual(result["reads"]["target_value_cells_materialized"], 0)
            corrupt = copy.deepcopy(result["membership"])
            corrupt[0]["matched"] = not corrupt[0]["matched"]
            with self.assertRaises(AssertionError):
                self.assertEqual(membership_view(corrupt), oracle)
            with self.assertRaisesRegex(AssertionError, "TARGET_VALUE_READER"):
                recorder.read(Path("observations.parquet"), columns=["typed_value"], filters=[("episode_id", "=", "canary"), ("field_id", "=", "FIELD-USD-PRICE-001"), ("point_id", "=", "E14400")])
            with self.assertRaisesRegex(AssertionError, "UNBOUNDED_VALUE_READER"):
                recorder.read(Path("observations.parquet"))
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_version_and_required_target_refusals(self):
        for change in ("legacy", "raw", "unknown", "population", "primary", "duplicate", "field", "scheduler"):
            spec = copy.deepcopy(self.spec)
            if change == "legacy": spec["schema_version"] = "1.3"
            elif change == "raw": spec["required_outcomes"][0]["point_id"] = "Y14400"
            elif change == "unknown": spec["required_outcomes"][0]["point_id"] = "E14401"
            elif change == "population": spec["population"] = "TOKEN_MINT"
            elif change == "primary": spec["required_outcomes"][0]["point_id"] = "E1800"
            elif change == "duplicate": spec["required_outcomes"].append({**spec["required_outcomes"][0], "role": "AUXILIARY"})
            elif change == "field": spec["required_outcomes"][0]["field_ids"] = ["FIELD-HOLDER-COUNT-001"]
            else: spec["observation_request"]["x_point"] = {"point_id": "X300"}
            with self.subTest(change=change):
                self.assertNotEqual(self.classify(spec).terminal, "FAST_LANE_READY")
        for point in ("E000300", "Y14400"):
            spec = copy.deepcopy(self.spec); spec["required_outcomes"][0]["point_id"] = point
            with self.assertRaises(ExperimentSpecError): validate_experiment_document(spec, root=ROOT)

    def test_frozen_source_query_schedule_and_safe_path_integrity(self):
        for change in ("query", "release", "manifest", "schedule", "path", "anchor", "clock", "cutoff"):
            spec = copy.deepcopy(self.spec)
            recipe = spec["parameters"]["temporal_recipe"]
            item = recipe["frozen_input"][0]
            if change == "query": recipe["scientific_identity"] = "0" * 64
            elif change == "release": item["release_id"] = "FOREIGN-RELEASE"
            elif change == "manifest": item["dataset_manifest_id"] = "dataset-" + "0" * 64
            elif change == "schedule": item["schedule_binding"]["availability_grace_seconds"] += 1
            elif change == "path": item["census_rel"] = "../foreign.parquet"
            elif change == "anchor": recipe["spec"]["scientific_body"]["anchor_kind"] = "TOKEN_CREATED_AT"
            elif change == "clock": recipe["spec"]["scientific_body"]["time_contract"]["time_feature_clock"] = "NOMINAL_TIME"
            else: spec["availability_cutoff"] = "2020-01-01T00:00:00Z"
            recorder = ReaderOracle()
            with self.subTest(change=change), patch("pyarrow.parquet.read_table", recorder.read):
                self.assertNotEqual(self.classify(spec).terminal, "FAST_LANE_READY")
                self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))

    def test_source_change_and_forged_projection_are_not_authority(self):
        packet = self.packet()
        packet["episode_outcome_binding"] = {"readiness": "COMPLETE", "decision_n": 999}
        decision = classify_lane(packet, root=ROOT, data_root=self.plane, as_of=AS_OF + timedelta(hours=3))
        self.assertEqual(decision.episode_outcome_binding["decision_n"], 20)
        path = self.plane / self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]["observations_rel"]
        with path.open("ab") as stream: stream.write(b"SOURCE-DRIFT")
        self.assertEqual(self.classify().terminal, "DENY_INTEGRITY_MISMATCH")

    def test_current_protection_denies_before_values(self):
        import pyarrow.parquet as pq
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        mint = pq.read_table(self.plane / item["census_rel"], columns=["mint"]).column("mint")[0].as_py()
        for complete in (True, False):
            write_assignment(self.plane, [{"identity_kind": "MINT", "identity": mint, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}], complete=complete)
            recorder = ReaderOracle()
            with patch("pyarrow.parquet.read_table", recorder.read):
                decision = self.classify()
            self.assertEqual(decision.terminal, "BLOCKED_DATA")
            self.assertIn(decision.reason_codes[0], {"HOLDOUT_PROTECTED", "HOLDOUT_UNRESOLVED"})
            self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))

    def test_authoritative_persistence_exact_repeat_cold_readback_and_guard(self):
        from solana_alpha_lab.factory.experiment_evidence import science_guard
        from solana_alpha_lab.factory.document_runner import _frozen_hfic_replay_lineage, RunContext
        validated = validate_experiment_document(self.spec, root=ROOT)
        self.assertEqual(validated["schema_version"], "1.4")
        decision = self.classify()
        self.assertEqual(decision.terminal, "FAST_LANE_READY", decision)
        recorder = ReaderOracle()
        critic = _critic_result(self.frozen, "PASS_TO_CLASSIFICATION")
        critic["non_claims"].append("SCRIPTED_TEST_CRITIC_NOT_SCIENTIFIC_ACCEPTANCE")
        with patch("pyarrow.parquet.read_table", recorder.read):
            finalized = finalize_session(self.frozen, critic, store=self.store, repo_root=ROOT, data_root=self.plane)
            done = apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        bundle = load_session_bundle(self.store, self.frozen["session_id"])
        self.assertEqual(bundle["session_state"], "SYNTHESIS_COMPLETE")
        self.assertEqual(bundle["classifier_receipt"]["lane_classifier_terminal"], "FAST_LANE_READY")
        binding = bundle["classifier_receipt"]["episode_outcome_binding"]
        self.assertEqual(binding["decision_n"], 20)
        before = self.store.diagnostics().committed_inventory_sha256
        repeated = apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        self.assertEqual(repeated["classifier_receipt"], bundle["classifier_receipt"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        code = "from pathlib import Path; from solana_alpha_lab.factory.research_store import ResearchStore; from solana_alpha_lab.factory.hfic_session import load_session_bundle; import json,sys; s=ResearchStore(Path(sys.argv[1])); b=load_session_bundle(s,sys.argv[2]); print(json.dumps({'receipt':b['classifier_receipt'],'inventory':s.diagnostics().committed_inventory_sha256}))"
        cold = subprocess.run([sys.executable, "-B", "-c", code, str(self.plane), self.frozen["session_id"]], cwd=ROOT, capture_output=True, encoding="utf-8", timeout=180, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        self.assertEqual(cold.returncode, 0, cold.stderr)
        readback = json.loads(cold.stdout)
        self.assertEqual(readback["receipt"], bundle["classifier_receipt"])
        self.assertEqual(readback["inventory"], before)
        # Native promotion gate remains semantic; accepted schema reaches it.
        guard = science_guard([])
        self.assertFalse(guard["allowed"])
        self.assertEqual(guard["terminal"], "PROMOTE_BLOCKED")
        forged = copy.deepcopy(self.spec)
        forged["parameters"]["temporal_recipe"]["scientific_identity"] = "0" * 64
        with self.assertRaisesRegex(HficSessionError, "EPISODE_FROZEN_RECIPE_MISMATCH"):
            run_live_classifier({"experiment_spec_packet": self.packet(forged)}, self.frozen, repo_root=ROOT, data_root=self.plane)

    def test_off_grid_deadline_boundaries_use_native_clock(self):
        import pyarrow.parquet as pq
        from datetime import UTC, datetime
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        t0 = datetime(2026, 10, 8, 12, 0, 7, tzinfo=UTC)
        window = resolve_point(item["schedule_binding"], t0, "E1800")
        self.assertEqual(window.nominal_due.isoformat(), "2026-10-08T12:30:07+00:00")
        self.assertEqual(window.assigned_at.isoformat(), "2026-10-08T12:35:00+00:00")
        self.assertEqual(window.availability_deadline.isoformat(), "2026-10-08T12:40:00+00:00")
        row = pq.read_table(self.plane / item["observations_rel"], filters=[("point_id", "=", "E1800"), ("field_id", "=", "FIELD-USD-PRICE-001")]).to_pylist()[0]
        for key, value in (("nominal_due_at", window.nominal_due), ("assigned_at", window.assigned_at), ("request_not_before", window.request_not_before), ("availability_deadline", window.availability_deadline), ("request_started_at", window.request_not_before), ("response_received_at", window.request_not_before)):
            row[key] = value.isoformat()
        for delta, expected in ((-1, "OBSERVED"), (0, "OBSERVED"), (1, "LATE")):
            row["first_reliable_available_at"] = (window.availability_deadline + timedelta(microseconds=delta)).isoformat()
            self.assertEqual(_metadata_status(row, item, t0, AS_OF), expected)


if __name__ == "__main__":
    unittest.main()
