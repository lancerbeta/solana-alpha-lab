"""Real Spec -> source -> prefix -> classifier -> durable HFIC proof.

Scripted Critic is a test entry boundary, never scientific acceptance. Reader
instrumentation observes real reads; source/binder/classifier/storage are real.
"""
from __future__ import annotations

import copy
import hashlib
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
    preview_classification_correction,
)
from solana_alpha_lab.factory.experiment_spec import validate_experiment_document, ExperimentSpecError
from solana_alpha_lab.factory.hfic_grounded_discovery import GroundedDiscoveryError
from solana_alpha_lab.factory.lane_classifier import classify_lane
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.opportunity_episodes import point_offset, resolve_point
from tests.test_hfic_session import _critic_result
from tests.test_opportunity_episodes_vertical_v1 import AS_OF
from tests.test_opportunity_episodes_harness_v1 import write_assignment
from solana_alpha_lab.factory.run_passport import canonical_sha256 as canonical


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
        from tests.test_opportunity_episodes_vertical_v1 import install_current_fixture
        install_current_fixture(self.plane, reset_root_binding=True)
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
            expected = copy.deepcopy(oracle)
            # The native numeric contrast permits overlap: comparator is D.
            if kind == "MIXED_LIST_NUMERIC":
                for row in expected:
                    row["comparator"] = row["decision_eligible"]
            recorder = ReaderOracle()
            with patch("pyarrow.parquet.read_table", recorder.read), patch(
                    "solana_alpha_lab.factory.hfic_temporal_discovery._target_projection", side_effect=AssertionError("OUTCOME_EVALUATOR")), patch(
                    "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery", side_effect=AssertionError("MAIN")):
                result = project_episode_required_outcomes(spec, data_root=self.plane, definition_sha256=frozen["selected_definition_sha256"])
            self.assertEqual(membership_view(result["membership"]), expected)
            self.assertEqual((result["admissions_n"], result["decision_n"], result["matched_n"], result["comparator_n"]), (24, 20, 10, 20 if kind == "MIXED_LIST_NUMERIC" else 10))
            self.assertEqual(result["readiness"], "COMPLETE")
            values = [t for t in recorder.trace if "typed_value" in t["columns"]]
            self.assertEqual(sum(len(t["filters"]) == 4 for t in values), result["reads"]["prefix_value_cells_read"])
            self.assertEqual(result["reads"]["target_value_cells_materialized"], 0)
            corrupt = copy.deepcopy(result["membership"])
            corrupt[0]["matched"] = not corrupt[0]["matched"]
            with self.assertRaises(AssertionError):
                self.assertEqual(membership_view(corrupt), expected)
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

    def test_identical_source_dedup_and_conflicting_identity(self):
        baseline = self.project()
        spec = copy.deepcopy(self.spec)
        recipe = spec["parameters"]["temporal_recipe"]
        recipe["frozen_input"].append(copy.deepcopy(recipe["frozen_input"][0]))
        duplicate = self.project(spec)
        self.assertEqual(duplicate["membership"], baseline["membership"])
        self.assertEqual(duplicate["required_coverage"], baseline["required_coverage"])
        recipe["frozen_input"][-1]["observations_sha256"] = "0" * 64
        with self.assertRaisesRegex(GroundedDiscoveryError, "EPISODE_SOURCE_BINDING_CONFLICT"):
            self.project(spec)

    def test_explicit_single_pair_uses_same_current_gate_before_loader(self):
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        binding = discovery.resolve_published_episode_binding(self.plane)
        item = binding["cohorts"][0]
        single = {**binding, "cohorts": [item]}
        kwargs = dict(data_root=None, binding_doc=single, partitions=None,
                      census_path=self.plane / item["census_rel"],
                      observations_path=self.plane / item["observations_rel"])
        loaded = discovery.load_admitted_partition_rows(**kwargs)
        self.assertTrue(loaded["values_loaded"])
        self.assertGreater(len(loaded["census"]), 0)
        (self.plane / "protection/current_research.json").rename(self.work / "missing-current-pointer")
        with patch.object(discovery, "load_parquet_rows", side_effect=AssertionError("UNSAFE_FALLBACK_VALUE_LOADER")) as loader:
            with self.assertRaisesRegex(GroundedDiscoveryError, "HOLDOUT_UNRESOLVED"):
                discovery.load_admitted_partition_rows(**kwargs)
        loader.assert_not_called()

    def test_relabelled_episode_bytes_cannot_use_legacy_value_entry(self):
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        original = discovery.resolve_published_episode_binding(self.plane)
        item = original["cohorts"][0]
        for strip_population in (False, True):
            relabel = {**item, "dataset_id": discovery.LIVE_DATASET_ID}
            if strip_population:
                relabel.pop("population", None)
            for explicit_pair in (False, True):
                kwargs = dict(data_root=None, binding_doc={"cohorts": [relabel]},
                    partitions=None if explicit_pair else [(item["cohort_id"], self.plane/item["census_rel"], self.plane/item["observations_rel"])],
                    census_path=self.plane/item["census_rel"] if explicit_pair else None,
                    observations_path=self.plane/item["observations_rel"] if explicit_pair else None)
                with self.subTest(strip=strip_population, pair=explicit_pair), patch.object(
                        discovery, "load_parquet_rows", side_effect=AssertionError("RELABELLED_VALUE_LOADER")) as loader:
                    with self.assertRaisesRegex(GroundedDiscoveryError, "HOLDOUT_UNRESOLVED"):
                        discovery.load_admitted_partition_rows(**kwargs)
                loader.assert_not_called()

    def test_mixed_legacy_and_relabelled_episode_refuse_before_any_loader(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
        item = discovery.resolve_published_episode_binding(self.plane)["cohorts"][0]
        relabel = {**item, "dataset_id": discovery.LIVE_DATASET_ID}
        relabel.pop("population", None)
        census, observations = self.work/"legacy-census.parquet", self.work/"legacy-observations.parquet"
        for path in (census, observations): pq.write_table(pa.table({"mint": ["SyntheticLegacyMint"]}), path)
        legacy = {"dataset_id": discovery.LIVE_DATASET_ID, "evidence_role": "EXPLORATORY_REUSE", "holdout": False,
                  "cohort_id": "LEGACY-FIRST", "release_id": "LEGACY-RELEASE",
                  "census_sha256": sha256_file_streaming(census), "observations_sha256": sha256_file_streaming(observations)}
        pairs = [(legacy["cohort_id"], census, observations), (item["cohort_id"], self.plane/item["census_rel"], self.plane/item["observations_rel"])]
        for ordered in (pairs, list(reversed(pairs))):
            with patch.object(discovery, "load_parquet_rows", side_effect=AssertionError("PARTIAL_VALUE_READ")) as loader:
                with self.assertRaisesRegex(GroundedDiscoveryError, "HOLDOUT_UNRESOLVED"):
                    discovery.load_admitted_partition_rows(data_root=None, binding_doc={"cohorts": [legacy, relabel]},
                        partitions=ordered, census_path=None, observations_path=None)
            loader.assert_not_called()

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

    def test_current_protection_missing_empty_unreadable_refuses_before_values(self):
        from tests.test_opportunity_episodes_harness_v1 import ASSIGNMENT_ID
        assignment_dir = self.plane / "protection/assignments"
        backup = self.work / "current-protection-backup"
        assignment_dir.rename(backup)
        for variant in ("missing", "empty", "unreadable"):
            if variant == "empty":
                assignment_dir.mkdir()
            elif variant == "unreadable":
                (assignment_dir / f"{ASSIGNMENT_ID}.json").write_bytes(b"{")
            recorder = ReaderOracle()
            with self.subTest(variant=variant), patch("pyarrow.parquet.read_table", recorder.read):
                decision = self.classify()
            self.assertEqual(decision.terminal, "BLOCKED_DATA")
            self.assertIn("HOLDOUT_UNRESOLVED", decision.reason_codes)
            self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))

    def test_conflicting_admission_reader_injection_refuses_before_values(self):
        import pyarrow as pa
        from solana_alpha_lab.factory.opportunity_episode_release import EPISODE_CENSUS_COLUMNS
        recorder = ReaderOracle()

        def corrupt_metadata(path, *args, **kwargs):
            table = recorder.read(path, *args, **kwargs)
            # Test-only reader fault after the real pinned source checks. This
            # proves the identity guard, not a valid republished source claim.
            if Path(path).name == "census.parquet" and kwargs.get("columns") == list(EPISODE_CENSUS_COLUMNS):
                row = table.slice(0, 1).to_pylist()[0]
                row["mint"] = "conflicting-test-mint"
                return pa.concat_tables([table, pa.Table.from_pylist([row], schema=table.schema)])
            return table

        with patch("pyarrow.parquet.read_table", corrupt_metadata):
            decision = self.classify()
        self.assertEqual(decision.terminal, "DENY_INTEGRITY_MISMATCH")
        self.assertIn("EPISODE_ADMISSION_IDENTITY_CONFLICT", decision.reason_codes)
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))

    def test_authoritative_persistence_exact_repeat_cold_readback_and_guard(self):
        from solana_alpha_lab.factory.experiment_evidence import science_guard, _build_obligations
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
        classification_trace = recorder.trace
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
        lineage = _frozen_hfic_replay_lineage(self.spec, RunContext(self.plane, self.definition, decision))
        self.assertFalse(lineage["new_scientific_look"])
        self.assertEqual(lineage["session_id"], self.frozen["session_id"])
        from solana_alpha_lab.factory.document_runner import DocumentRunner
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        # Corrupt native schedule after READY. Real direct dispatch must refuse
        # before any evaluator, value materialization or new store event.
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        source_dir = (self.plane / item["census_rel"]).parent
        from solana_alpha_lab.factory.live_cohort_schedule_artifact import OBSERVATION_SCHEDULE_ARTIFACT_NAME
        schedule_path = source_dir / OBSERVATION_SCHEDULE_ARTIFACT_NAME
        schedule_bytes = schedule_path.read_bytes()
        schedule_path.write_bytes(schedule_bytes + b" ")
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read), patch(
                "solana_alpha_lab.factory.hfic_temporal_discovery.run_temporal_fixed_time_from_spec", side_effect=AssertionError("NUMERIC_RUN")):
            from solana_alpha_lab.factory.operational_store import OperationalStore
            operational = OperationalStore(self.work / "direct-ops.sqlite")
            self.addCleanup(operational.close)
            refused = DocumentRunner(root=ROOT, store=operational).start_document(self.spec,
                spec_sha256=experiment_spec_sha256(self.spec), run_context=RunContext(self.plane, self.definition, decision, AS_OF + timedelta(hours=3)))
        self.assertEqual(refused["status"], "INVALID_EVIDENCE")
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        schedule_path.write_bytes(schedule_bytes)
        # Optional retained proof is outside Git; compact receipt has no host paths.
        if os.environ.get("ERNOC_PROOF_OUT"):
            out = Path(os.environ["ERNOC_PROOF_OUT"])
            out.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.plane, out / "classified-plane", dirs_exist_ok=True)
            (out / "positive.json").write_text(json.dumps({
                "classifier_receipt": bundle["classifier_receipt"], "cold_inventory_sha256": before,
                "cold_readback_equal": True, "repeat_write_count": 0,
                "reader_trace": classification_trace, "direct_refusal_trace": recorder.trace, "direct_lineage": lineage,
            }, indent=2, default=str) + "\n", encoding="utf-8")
        # Native promotion gate remains semantic; accepted schema reaches it.
        guard = science_guard(_build_obligations(self.spec, entity={},
            direct=[{"record_kind": "RESEARCH_ARTIFACT", "payload": bundle["classifier_receipt"]}],
            records=tuple(self.store.iter_committed_records()), records_status="AVAILABLE", root=ROOT))
        self.assertFalse(guard["allowed"])
        self.assertEqual(guard["meaning"], "PROMOTE_BLOCKED")
        if os.environ.get("ERNOC_PROOF_OUT"):
            (Path(os.environ["ERNOC_PROOF_OUT"]) / "science-guard.json").write_text(
                json.dumps(guard, indent=2, default=str) + "\n", encoding="utf-8")
        forged = copy.deepcopy(self.spec)
        forged["parameters"]["temporal_recipe"]["scientific_identity"] = "0" * 64
        with self.assertRaisesRegex(HficSessionError, "EPISODE_FROZEN_RECIPE_MISMATCH"):
            run_live_classifier({"experiment_spec_packet": self.packet(forged)}, self.frozen, repo_root=ROOT, data_root=self.plane)
        import pyarrow.parquet as pq
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        mint = pq.read_table(self.plane / item["census_rel"], columns=["mint"]).column("mint")[0].as_py()
        write_assignment(self.plane, [{"identity_kind": "MINT", "identity": mint, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}])
        guarded_inventory = self.store.diagnostics().committed_inventory_sha256
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read), self.assertRaisesRegex(HficSessionError, "EPISODE_CLASSIFICATION_REVALIDATION_DENIED"):
            apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
        self.assertEqual(load_session_bundle(self.store, self.frozen["session_id"])["classifier_receipt"], bundle["classifier_receipt"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, guarded_inventory)
        for forged_packet in ({}, {"experiment_spec": {"schema_version": "1.3"}}):
            with self.assertRaisesRegex(HficSessionError, "EPISODE_CLASSIFICATION_REVALIDATION_DENIED"):
                apply_classification(self.frozen, forged_packet, store=self.store, repo_root=ROOT, data_root=self.plane)
        (self.plane / "protection/assignments").rename(self.work / "unavailable-current-after-persist")
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read), self.assertRaisesRegex(HficSessionError, "EPISODE_CLASSIFICATION_REVALIDATION_DENIED"):
            apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, guarded_inventory)

    def _pass(self):
        critic = _critic_result(self.frozen, "PASS_TO_CLASSIFICATION")
        critic["non_claims"].append("SCRIPTED_TEST_CRITIC_NOT_SCIENTIFIC_ACCEPTANCE")
        return finalize_session(self.frozen, critic, store=self.store, repo_root=ROOT, data_root=self.plane)

    def _future_packet(self):
        future = copy.deepcopy(self.spec)
        future["as_of"] = future["availability_cutoff"] = (AS_OF + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
        return self.packet(future)

    def _look_counts(self):
        counts = {}
        for record in self.store.iter_committed_records():
            body = json.loads(record.payload_json)
            kind = str(body.get("artifact_kind") or "")
            if "LOOK" in kind or "RESERVATION" in kind or kind == "ORDINARY_OPERATION_V1":
                counts[kind] = counts.get(kind, 0) + 1
        return counts

    def test_malformed_spec_is_input_refusal_and_session_stays_pending(self):
        from datetime import UTC, datetime
        from tests.test_forge_research_flow_reliability_v1 import public_cli
        self._pass()
        sid = self.frozen["session_id"]
        before = self.store.diagnostics().committed_inventory_sha256
        with self.assertRaisesRegex(HficSessionError, "CLASSIFICATION_INPUT_INVALID") as caught:
            apply_classification(self.frozen, self._future_packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        self.assertEqual(caught.exception.detail["reason_code"], "SPEC_AS_OF_AFTER_EVALUATION")
        self.assertEqual(caught.exception.detail["fields"], ["as_of", "availability_cutoff"])
        self.assertFalse(caught.exception.detail["writes"])
        # Public classify: one JSON object, measured zero writes, same pending session.
        future_spec = copy.deepcopy(self.spec)
        future_spec["as_of"] = future_spec["availability_cutoff"] = "2099-01-01T00:00:00Z"
        path = self.work / "future-spec.json"
        path.write_text(json.dumps({"experiment_spec": future_spec, "hypothesis_definition_sha256": self.definition}), encoding="utf-8")
        code, refused = public_cli(self.plane, "classify", "--session-id", sid, "--experiment-spec", str(path), "--format", "json")
        self.assertEqual((code, refused["reason_code"], refused["writes"]["research_store"]), (2, "CLASSIFICATION_INPUT_INVALID", 0))
        self.assertEqual((refused["detail"]["stage"], refused["detail"]["fields"]), ("CLASSIFICATION_INPUT", ["as_of", "availability_cutoff"]))
        # A future evaluation clock cannot unlock that Spec.
        path.write_text(json.dumps({"experiment_spec": future_spec, "hypothesis_definition_sha256": self.definition,
                                    "classifier_evaluated_at": "2099-01-02T00:00:00Z"}), encoding="utf-8")
        code, clock = public_cli(self.plane, "classify", "--session-id", sid, "--experiment-spec", str(path), "--format", "json")
        self.assertEqual((code, clock["reason_code"], clock["detail"]["reason_code"], clock["writes"]["research_store"]),
                         (2, "CLASSIFIER_CLOCK_INVALID", "CLASSIFIER_CLOCK_AFTER_RUNTIME", 0))
        naive = {**self.packet(), "classifier_evaluated_at": datetime.now(UTC).replace(tzinfo=None).isoformat()}
        with self.assertRaisesRegex(HficSessionError, "CLASSIFIER_CLOCK_INVALID"):
            apply_classification(self.frozen, naive, store=self.store, repo_root=ROOT, data_root=self.plane)
        # A registry outage is configuration, not a verdict: nothing is written.
        with patch("solana_alpha_lab.factory.lane_classifier._load_capabilities", side_effect=ValueError("REGISTRY")):
            with self.assertRaisesRegex(HficSessionError, "CLASSIFIER_CONFIG_UNAVAILABLE"):
                apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        self.assertEqual(ResearchStore(self.plane).diagnostics().committed_inventory_sha256, before)
        pending = load_session_bundle(self.store, sid)
        self.assertEqual(pending["session_state"], "AWAITING_CLASSIFICATION")
        self.assertEqual(pending["critic_terminal"], "PASS_TO_CLASSIFICATION")
        apply_classification(self.frozen, self.packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        done = load_session_bundle(self.store, sid)
        self.assertEqual(done["classifier_receipt"]["lane_classifier_terminal"], "FAST_LANE_READY")
        # A correctly classified session is not a correction subject.
        with self.assertRaisesRegex(HficSessionError, "CLASSIFICATION_CORRECTION_NOT_INPUT_REFUSAL"):
            preview_classification_correction(self.store, sid, self._corrected_packet(),
                                              repo_root=ROOT, data_root=self.plane)

    def test_scientific_kill_is_not_a_correction_subject(self):
        finalize_session(self.frozen, _critic_result(self.frozen, "KILL_MECHANISM"), store=self.store, repo_root=ROOT,
                         data_root=self.plane)
        before = self.store.diagnostics().committed_inventory_sha256
        with self.assertRaisesRegex(HficSessionError, "CLASSIFICATION_CORRECTION_NOT_INPUT_REFUSAL"):
            preview_classification_correction(self.store, self.frozen["session_id"], self._corrected_packet(),
                                              repo_root=ROOT, data_root=self.plane)
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def _corrected_packet(self, *, delay_seconds=0):
        from datetime import UTC, datetime
        corrected = copy.deepcopy(self.spec)
        now = (datetime.now(UTC) - timedelta(seconds=delay_seconds)).replace(microsecond=0)
        corrected["as_of"] = corrected["availability_cutoff"] = now.isoformat().replace("+00:00", "Z")
        return {"experiment_spec": corrected, "hypothesis_definition_sha256": self.definition}

    def _legacy_refusal(self):
        """Reproduce the pre-repair writer: the envelope guard was absent there."""
        import inspect
        from solana_alpha_lab.factory import lane_classifier
        original = lane_classifier.spec_input_refusal
        def legacy(*args, **kwargs):
            if inspect.stack()[1].function == "run_live_classifier":
                return None
            return original(*args, **kwargs)
        self._pass()
        with patch.object(lane_classifier, "spec_input_refusal", legacy), patch(
                "solana_alpha_lab.factory.hfic_session._raise_classifier_config_refusal"):
            apply_classification(self.frozen, self._future_packet(), store=self.store, repo_root=ROOT, data_root=self.plane)
        refused = load_session_bundle(self.store, self.frozen["session_id"])
        self.assertEqual(refused["final_session_terminal"], "KILL_UNBOUND_EVIDENCE")
        self.assertEqual(refused["classifier_receipt"]["lane_classifier_terminal"], "DENY_INVALID_SPEC")
        return refused

    def test_recorded_input_refusal_correction_lineage_and_fragment(self):
        from solana_alpha_lab.factory.hfic_session import (
            preview_classification_correction as preview, apply_classification_correction as apply, show_session)
        from solana_alpha_lab.factory import research_fragments as fragments
        from solana_alpha_lab.factory.hfic_prior_memory import latest_hypothesis_decisions
        refused = self._legacy_refusal()
        sid = self.frozen["session_id"]
        candidate = self.frozen["selected_candidate_id"]
        packet = self._corrected_packet()
        for forged, code in (
            ({**packet, "classifier_evaluated_at": "2026-10-15T09:00:00Z"}, "CLASSIFICATION_CORRECTION_PACKET_INVALID"),
            ({**packet, "hypothesis_definition_sha256": "0" * 64}, "CLASSIFICATION_CORRECTION_PACKET_INVALID"),
            ({**packet, "experiment_spec": {**packet["experiment_spec"], "estimand": "changed"}}, "CLASSIFICATION_CORRECTION_SCOPE_FORBIDDEN"),
            ({**packet, "experiment_spec": {**packet["experiment_spec"], "as_of": "2026-10-15T07:00:00Z",
                                             "availability_cutoff": "2026-10-15T07:00:00Z"}}, "CLASSIFICATION_CORRECTION_TIME_RULE_VIOLATED"),
            ({**packet, "experiment_spec": {**packet["experiment_spec"], "availability_cutoff": "2026-10-15T09:30:00Z"}},
             "CLASSIFICATION_CORRECTION_TIME_RULE_VIOLATED"),
        ):
            with self.assertRaisesRegex(HficSessionError, code):
                preview(self.store, sid, forged, repo_root=ROOT, data_root=self.plane)
        from tests.test_forge_research_flow_reliability_v1 import public_cli
        code, template = public_cli(self.plane, "classification-correction-preview", "--session-id", sid, "--format", "json")
        self.assertEqual((code, template["status"]), (0, "TEMPLATE"), template)
        self.assertEqual(template["refused_experiment_spec_packet"], refused["critic_result"]["experiment_spec_packet"])
        self.assertEqual(template["correctable_fields"], ["as_of", "availability_cutoff"])
        focus = refused["owner_focus"]
        code, run_before = public_cli(self.plane, "forge-run", "--collection", "OPPORTUNITY_EPISODES",
                                      "--owner-focus", focus, "--no-write", "--format", "json")
        self.assertEqual(code, 0, run_before)
        base_before = next(r for r in run_before["stages"] if r["representation_id"] == "BASE")
        self.assertEqual(base_before["effective_terminal"], "KILL_UNBOUND_EVIDENCE")
        code, stopped = public_cli(self.plane, "forge-run", "--collection", "OPPORTUNITY_EPISODES",
                                   "--owner-focus", focus, "--persist", "--format", "json")
        self.assertEqual((code, stopped["owner_final"]), (0, "NON_SCIENTIFIC_STOP"), stopped)
        from datetime import UTC, datetime
        cutoff_before_correction = datetime.now(UTC)
        looks_before = self._look_counts()
        before = self.store.diagnostics().committed_inventory_sha256
        packet_path = self.work / "corrected-packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        with patch("solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
                   side_effect=AssertionError("no outcome evaluator")):
            ready = preview(self.store, sid, packet, repo_root=ROOT, data_root=self.plane)
        code, public_ready = public_cli(self.plane, "classification-correction-preview", "--session-id", sid,
                                        "--experiment-spec", str(packet_path), "--format", "json")
        self.assertEqual(code, 0, public_ready)
        self.assertEqual(ready["status"], "PREVIEW_READY")
        self.assertEqual(public_ready["proposal"]["correction"]["refused"], ready["proposal"]["correction"]["refused"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        body = ready["proposal"]["correction"]
        self.assertEqual(body["refused"]["cause"]["reason_code"], "SPEC_AS_OF_AFTER_EVALUATION")
        self.assertEqual([c["field"] for c in body["corrected"]["field_changes"]], ["as_of", "availability_cutoff"])
        with self.assertRaisesRegex(HficSessionError, "CONFIRM_APPEND_ONLY_REQUIRED"):
            apply(self.store, ready["proposal"], repo_root=ROOT, data_root=self.plane, confirm_append_only=False)
        stale = copy.deepcopy(ready["proposal"])
        stale["parent_session_receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(HficSessionError, "CLASSIFICATION_CORRECTION_PREVIEW_STALE"):
            apply(self.store, stale, repo_root=ROOT, data_root=self.plane, confirm_append_only=True)
        proposal_path = self.work / "correction-preview.json"
        proposal_path.write_text(json.dumps(public_ready), encoding="utf-8")
        code, refused_cli = public_cli(self.plane, "classification-correction-apply", "--proposal", str(proposal_path), "--format", "json")
        self.assertEqual((code, refused_cli["reason_code"], refused_cli["writes"]["research_store"], refused_cli["next_action"],
                          refused_cli["detail"]["stage"]),
                         (2, "CONFIRM_APPEND_ONLY_REQUIRED", 0, "RERUN_APPLY_WITH_CONFIRM_APPEND_ONLY", "CLASSIFICATION_CORRECTION_APPLY"))
        code, applied = public_cli(self.plane, "classification-correction-apply", "--proposal", str(proposal_path),
                                   "--confirm-append-only", "--format", "json")
        self.assertEqual(code, 0, applied)
        self.assertEqual((applied["status"], applied["writes"]["research_store"], applied["new_look"]), ("APPLIED", 1, False))
        self.assertEqual(applied["forge_run_args"][:2], ["--collection", "OPPORTUNITY_EPISODES"])
        self.store = ResearchStore(self.plane)
        corrected = load_session_bundle(self.store, sid)
        public_body = public_ready["proposal"]["correction"]
        self.assertEqual(corrected["final_session_terminal"], "PASS_FAST_LANE_READY")
        self.assertEqual(corrected["classifier_receipt"]["lane_classifier_terminal"], "FAST_LANE_READY")
        self.assertEqual(corrected["critic_input_packet_sha256"], refused["critic_input_packet_sha256"])
        self.assertEqual(corrected["selected_definition_sha256"], self.definition)
        self.assertEqual(corrected["decisions"][candidate]["decision_kind"], "PAUSE")
        self.assertEqual(corrected["classification_correction"], public_body)
        self.assertEqual(corrected["capability_epoch_sha256"], public_body["corrected"]["capability_epoch_sha256"])
        # Look ledger, operation and budget records are untouched by the correction.
        self.assertEqual(self._look_counts(), looks_before)
        # Memory at a cutoff before the correction keeps the historical REJECT.
        old = latest_hypothesis_decisions(self.store, as_of=cutoff_before_correction)
        new = latest_hypothesis_decisions(self.store)
        self.assertEqual(old[(candidate, sid)]["decision_kind"], "REJECT")
        self.assertEqual(new[(candidate, sid)]["decision_kind"], "PAUSE")
        shown = show_session(self.store, sid, repo_root=ROOT)["classification_correction"]
        self.assertEqual((shown["refused_final_session_terminal"], shown["corrected_final_session_terminal"]),
                         ("KILL_UNBOUND_EVIDENCE", "PASS_FAST_LANE_READY"))
        self.assertEqual([c["field"] for c in shown["field_changes"]], ["as_of", "availability_cutoff"])
        # A repeat (lost response) writes nothing.
        after = self.store.diagnostics().committed_inventory_sha256
        again = apply(self.store, public_ready["proposal"], repo_root=ROOT, data_root=self.plane, confirm_append_only=True)
        self.assertEqual(again["classification_correction_sha256"], corrected["classification_correction_sha256"])
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, after)
        self.assertEqual(preview(self.store, sid, packet, repo_root=ROOT, data_root=self.plane)["status"], "ALREADY_APPLIED")
        kinds = [json.loads(r.payload_json).get("artifact_kind") for r in self.store.iter_committed_records()
                 if json.loads(r.payload_json).get("session_id") == sid]
        self.assertEqual(kinds.count("CLASSIFIER_RECEIPT"), 2)
        self.assertEqual(kinds.count("SESSION_RECEIPT"), 2)
        code, cold = public_cli(self.plane, "show-session", "--session-id", sid, "--format", "json")
        self.assertEqual(code, 0, cold)
        self.assertEqual(cold["classification_correction"]["classification_correction_sha256"], corrected["classification_correction_sha256"])
        code, run_after = public_cli(self.plane, "forge-run", "--collection", "OPPORTUNITY_EPISODES",
                                     "--owner-focus", focus, "--no-write", "--format", "json")
        self.assertEqual(code, 0, run_after)
        base_after = next(r for r in run_after["stages"] if r["representation_id"] == "BASE")
        self.assertEqual(base_after["effective_terminal"], "PASS_FAST_LANE_READY", run_after.get("owner_readout"))
        self.assertEqual(base_after["session_id"], sid)
        self.assertEqual(run_after["owner_final"], "OWNER_CANDIDATE")
        code, persisted = public_cli(self.plane, "forge-run", "--collection", "OPPORTUNITY_EPISODES",
                                     "--owner-focus", focus, "--persist", "--format", "json")
        self.assertEqual((code, persisted["owner_final"]), (0, "OWNER_CANDIDATE"), persisted)
        self.assertNotEqual(persisted["receipt_sha256"], stopped["receipt_sha256"])
        receipts = [json.loads(json.loads(r.payload_json)["payload_canonical"]) for r in ResearchStore(self.plane).iter_committed_records()
                    if json.loads(r.payload_json).get("artifact_kind") == "FORGE_RUN_RECEIPT"]
        self.assertIn("NON_SCIENTIFIC_STOP", [r.get("owner_final") for r in receipts])
        code, replay = public_cli(self.plane, "forge-run", "--collection", "OPPORTUNITY_EPISODES",
                                  "--owner-focus", focus, "--no-write", "--format", "json")
        self.assertEqual((code, replay["next_action"], replay["owner_final"]), (0, "RETURN_EXISTING_RUN", "OWNER_CANDIDATE"))
        # The native shelf (public CLI) reads the corrected terminal and the exact list contrast.
        grounded = corrected["critic_input_packet"]["grounded_evidence"]
        request = {"title": "fixture list contrast", "role": "CONTEXT_FILTER", "session_id": sid,
                   "candidate_id": candidate, "definition_sha256": self.definition,
                   "result_ref": grounded["result_refs"][0], "result_sha256": grounded["result_sha256"]}
        request_path = self.work / "fragment-request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        shelf = [sys.executable, "-B", str(ROOT / "scripts/research_fragments.py")]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}
        for action, extra in (("registration-preview", []), ("register", ["--confirm-append-only"])):
            done = subprocess.run([*shelf, action, "--data-root", str(self.plane), "--input", str(request_path), *extra],
                                  cwd=ROOT, capture_output=True, encoding="utf-8", timeout=180, env=env)
            self.assertEqual(done.returncode, 0, done.stderr)
        card_id = json.loads(done.stdout)["fragment"]["fragment_version_id"]
        self.store = ResearchStore(self.plane)
        view = next(v for v in fragments.source_snapshot(self.store) if v["fragment_version_id"] == card_id)
        self.assertEqual(view["source_terminal"], "PASS_FAST_LANE_READY")
        summary = view["evidence_blocks"][0]["summary"]
        scope = summary["research_scope"]
        self.assertEqual(scope["contrast"]["kind"], "MATCHED_VS_ELIGIBLE_COMPLEMENT")
        self.assertEqual(scope["contrast"]["comparator"]["n"], scope["decision_eligible_n"] - scope["matched"]["n"])
        self.assertNotEqual(scope["contrast"]["comparator"]["n"], summary["baseline"]["eligible_n"])
        self.assertTrue(summary["baseline_may_include_matched"])
        # The ordinary prior capsule carries the same typed contrast.
        capsules = [{"hypothesis_version_id": candidate, "source_detail": {}}]
        fragments.enrich_prior_capsules(self.store, capsules, as_of=None)
        carried = capsules[0]["source_detail"]["research_fragments"][0]["evidence_blocks"][0]["summary"]["research_scope"]
        self.assertEqual(carried["contrast"]["comparator"]["n"], scope["contrast"]["comparator"]["n"])

    def test_correction_capability_drift_late_denial_and_race(self):
        from solana_alpha_lab.factory import hfic_evidence_identity as identity
        from solana_alpha_lab.factory.hfic_representation_ladder import evaluate_forge_run
        from solana_alpha_lab.factory.hfic_session import apply_classification_correction as apply
        from solana_alpha_lab.factory import research_fragments as fragments
        refused = self._legacy_refusal()
        sid, focus = self.frozen["session_id"], refused["owner_focus"]
        original = identity.compute_capability_epoch_for_repo
        def drifted(repo):
            digest, basis = original(repo)
            return hashlib.sha256((digest + ":post-merge").encode()).hexdigest(), basis
        before = self.store.diagnostics().committed_inventory_sha256
        # Late denial: a protection change after the refusal stops the correction before any write.
        import pyarrow.parquet as pq
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        mint = pq.read_table(self.plane / item["census_rel"], columns=["mint"]).column("mint")[0].as_py()
        write_assignment(self.plane, [{"identity_kind": "MINT", "identity": mint, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}])
        with self.assertRaises(HficSessionError) as denied:
            preview_classification_correction(self.store, sid, self._corrected_packet(), repo_root=ROOT, data_root=self.plane)
        self.assertIn(denied.exception.code, {"CLASSIFICATION_CORRECTION_CURRENT_GATE_DENIED", "EPISODE_SOURCE_BINDING_CONFLICT"})
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)
        write_assignment(self.plane, [])
        from tests.test_opportunity_episodes_vertical_v1 import install_current_fixture
        install_current_fixture(self.plane, reset_root_binding=True)
        self.store = ResearchStore(self.plane)
        with patch.object(identity, "compute_capability_epoch_for_repo", drifted):
            stopped = evaluate_forge_run(ROOT, self.plane, owner_focus=focus, persist=True)
            self.assertEqual(stopped["owner_final"], "NON_SCIENTIFIC_STOP")
            first = preview_classification_correction(self.store, sid, self._corrected_packet(delay_seconds=1),
                                                      repo_root=ROOT, data_root=self.plane)["proposal"]
            second = preview_classification_correction(self.store, sid, self._corrected_packet(),
                                                       repo_root=ROOT, data_root=self.plane)["proposal"]
            self.assertNotEqual(canonical(first["correction"]), canonical(second["correction"]))
            # Race: another apply lands between the second apply's proof and its append.
            original_append, raced = ResearchStore.append, []
            def racing(store_self, records, *, transaction_id, before_commit=None):
                if "CLSCORR" in transaction_id and not raced:
                    raced.append(transaction_id)
                    apply(ResearchStore(self.plane), first, repo_root=ROOT, data_root=self.plane, confirm_append_only=True)
                return original_append(store_self, records, transaction_id=transaction_id, before_commit=before_commit)
            with patch.object(ResearchStore, "append", racing):
                with self.assertRaisesRegex(HficSessionError, "CLASSIFICATION_CORRECTION_PREVIEW_STALE"):
                    apply(self.store, second, repo_root=ROOT, data_root=self.plane, confirm_append_only=True)
            bundle = load_session_bundle(ResearchStore(self.plane), sid)
            self.assertEqual(bundle["classification_correction_sha256"], canonical(first["correction"]))
            self.assertEqual(bundle["capability_epoch_sha256"], drifted(ROOT)[0])
            run = evaluate_forge_run(ROOT, self.plane, owner_focus=focus, persist=False)
            base = next(r for r in run["stages"] if r["representation_id"] == "BASE")
            self.assertEqual((base["effective_terminal"], run["owner_final"]), ("PASS_FAST_LANE_READY", "OWNER_CANDIDATE"))
        self.assertEqual(bundle["final_session_terminal"], "PASS_FAST_LANE_READY")
        grounded = bundle["critic_input_packet"]["grounded_evidence"]
        card = fragments.registration_preview(ResearchStore(self.plane), {
            "title": "drift", "role": "CONTEXT_FILTER", "session_id": sid, "candidate_id": self.frozen["selected_candidate_id"],
            "definition_sha256": self.definition, "result_ref": grounded["result_refs"][0], "result_sha256": grounded["result_sha256"]})
        self.assertFalse(card["writes"])

    def test_republished_numeric_values_and_missing_target_keep_denominator(self):
        variants = os.environ.get("ERNOC_VARIANTS")
        if not variants:
            self.skipTest("Native republished variant stores supplied by the reproducible proof campaign")
        baseline = self.project()
        for name, expected_observed in (("world-values-v2", 20), ("world-missing-v2", 19)):
            world = Path(variants) / name
            spec, frozen = load_case(world)
            # Older retained worlds predate the explicit current-proof guard.
            # Register the synthetic consumer's empty inventory in a test copy;
            # never alter the old benchmark or its source/trial history.
            variant_plane = self.work / name
            shutil.copytree(world / "plane", variant_plane)
            write_assignment(variant_plane, [])
            recorder = ReaderOracle()
            with patch("pyarrow.parquet.read_table", recorder.read):
                result = project_episode_required_outcomes(spec, data_root=variant_plane, definition_sha256=frozen["selected_definition_sha256"])
            self.assertEqual(membership_view(result["membership"]), membership_view(baseline["membership"]))
            self.assertEqual(result["decision_n"], 20)
            self.assertEqual(result["required_coverage"][0]["counts"]["OBSERVED"], expected_observed)
            self.assertEqual(result["readiness"], "COMPLETE" if expected_observed == 20 else "UNRESOLVED")
            self.assertNotEqual(result["sources"], baseline["sources"])
            self.assertTrue(all(point_offset(dict((k,v) for k,op,v in t["filters"] if op == "=")["point_id"]) <= 1800 for t in recorder.trace if "typed_value" in t["columns"]))

    def test_authoritative_missing_target_block_and_cold_readback(self):
        fixture = os.environ.get("ERNOC_MISSING_FIXTURE")
        if not fixture:
            self.skipTest("Current-candidate native missingness campaign fixture supplied explicitly")
        spec, frozen = load_case(fixture)
        plane = self.work / "missing-plane"
        shutil.copytree(Path(fixture) / "plane", plane)
        store = ResearchStore(plane)
        store.prepare_write_lookup()
        packet = {"experiment_spec": spec, "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
                  "classifier_evaluated_at": (AS_OF + timedelta(hours=3)).isoformat()}
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read):
            finalize_session(frozen, _critic_result(frozen, "PASS_TO_CLASSIFICATION"), store=store, repo_root=ROOT, data_root=plane)
            done = apply_classification(frozen, packet, store=store, repo_root=ROOT, data_root=plane)
        receipt = load_session_bundle(store, frozen["session_id"])["classifier_receipt"]
        self.assertEqual(receipt["lane_classifier_terminal"], "BLOCKED_DATA")
        binding = receipt["episode_outcome_binding"]
        self.assertEqual(binding["decision_n"], 20)
        self.assertEqual(binding["required_coverage"][0]["counts"]["OBSERVED"], 19)
        before = store.diagnostics().committed_inventory_sha256
        code = "from pathlib import Path; from solana_alpha_lab.factory.research_store import ResearchStore; from solana_alpha_lab.factory.hfic_session import load_session_bundle; import json,sys; s=ResearchStore(Path(sys.argv[1])); b=load_session_bundle(s,sys.argv[2]); print(json.dumps({'receipt':b['classifier_receipt'],'inventory':s.diagnostics().committed_inventory_sha256}))"
        cold = subprocess.run([sys.executable, "-B", "-c", code, str(plane), frozen["session_id"]], cwd=ROOT, capture_output=True, encoding="utf-8", timeout=180, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        self.assertEqual(cold.returncode, 0, cold.stderr)
        self.assertEqual(json.loads(cold.stdout), {"receipt": receipt, "inventory": before})
        if os.environ.get("ERNOC_PROOF_OUT"):
            out = Path(os.environ["ERNOC_PROOF_OUT"])
            out.mkdir(parents=True, exist_ok=True)
            shutil.copytree(plane, out / "blocked-plane", dirs_exist_ok=True)
            (out / "blocked.json").write_text(json.dumps({"classifier_receipt": receipt,
                "cold_inventory_sha256": before, "cold_readback_equal": True,
                "reader_trace": recorder.trace}, indent=2, default=str) + "\n", encoding="utf-8")

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

    def test_native_unexecuted_censored_metadata_is_not_corrupt_or_observed(self):
        import pyarrow.parquet as pq
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        rows = pq.read_table(self.plane / item["observations_rel"], filters=[("state", "=", "CENSORED"), ("field_id", "=", "FIELD-USD-PRICE-001")], columns=[
            "episode_id", "point_id", "state", "missing_reason", "first_reliable_available_at",
            "nominal_due_at", "assigned_at", "request_not_before", "availability_deadline"]).to_pylist()
        census = {r["episode_id"]: r for r in pq.read_table(self.plane / item["census_rel"], columns=["episode_id", "t0"]).to_pylist()}
        from solana_alpha_lab.factory.hfic_grounded_discovery import _parse_time
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(_metadata_status(row, item, _parse_time(census[row["episode_id"]]["t0"]), AS_OF), "CENSORED")

    def test_historical_publication_metadata_is_required(self):
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        prefix = self.plane / "datasets/manifests" / item["dataset_manifest_id"]
        for suffix in (".published", ".labels.json"):
            path = Path(str(prefix) + suffix)
            original = path.read_bytes()
            value = json.loads(original)
            if suffix == ".published": value["dataset_fingerprint"] = "0" * 64
            else: value["cohort_lineage"] = ["FOREIGN"]
            path.write_text(json.dumps(value), encoding="utf-8")
            recorder = ReaderOracle()
            with patch("pyarrow.parquet.read_table", recorder.read):
                self.assertNotEqual(self.classify().terminal, "FAST_LANE_READY")
            self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
            path.write_bytes(original)

    def test_completed_run_replay_fixture_rechecks_current_protection(self):
        from tests.test_fast_lane_classifier import completed_run_event
        decision = self.classify()
        self.assertEqual(decision.terminal, "FAST_LANE_READY")
        event = completed_run_event("RUN-EPISODE-REPLAY-FIXTURE", decision.run_key_sha256)
        payload = json.loads(event.payload_json)
        payload["non_claims"] = ["EXPLICIT_RUN_PASSPORT_FIXTURE_NO_EXPERIMENT_EXECUTION"]
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        import hashlib
        self.store.append([event.model_copy(update={"payload_json": text, "payload_sha256": hashlib.sha256(text.encode()).hexdigest()})], transaction_id=event.transaction_id)
        self.assertEqual(self.classify().terminal, "REPLAY_AVAILABLE")
        assignment = self.plane / "protection/assignments"
        unavailable = self.work / "unavailable-current-on-replay"
        assignment.rename(unavailable)
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read):
            refused = self.classify()
        self.assertEqual(refused.terminal, "BLOCKED_DATA")
        self.assertIn("HOLDOUT_UNRESOLVED", refused.reason_codes)
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
        unavailable.rename(assignment)
        import pyarrow.parquet as pq
        item = self.spec["parameters"]["temporal_recipe"]["frozen_input"][0]
        mint = pq.read_table(self.plane / item["census_rel"], columns=["mint"]).column("mint")[0].as_py()
        write_assignment(self.plane, [{"identity_kind": "MINT", "identity": mint, "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}])
        before = self.store.diagnostics().committed_inventory_sha256
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read):
            self.assertEqual(self.classify().terminal, "BLOCKED_DATA")
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))
        self.assertEqual(self.store.diagnostics().committed_inventory_sha256, before)

    def test_registered_unavailable_referenced_list_is_unknown_not_false(self):
        from solana_alpha_lab.factory import hfic_research_scope as rs, hfic_temporal_discovery as temporal
        from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_research_scope
        from tests.test_hfic_research_scope_v1 import _snapshot
        from tests.test_hfic_list_aware_vertical_v1 import draft
        spec = copy.deepcopy(self.spec)
        recipe = spec["parameters"]["temporal_recipe"]
        path = self.work / "snapshot.json"
        path.write_text(json.dumps(_snapshot(["irrelevant-mint"])), encoding="utf-8")
        rs.register_local_snapshot(self.plane, path, registered_at=AS_OF + timedelta(hours=1))
        evidence = rs.load_corpus_membership(self.plane, only_release_ids={i["release_id"] for i in recipe["frozen_input"]}, local_list_ids={"OWNER:D"})
        query = rs.canonicalize_query_scope(draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["OWNER:D"]}]}), evidence)
        pre = temporal.validate_temporal_query(query)
        recipe["spec"], recipe["scientific_identity"] = pre, pre["spec_sha256"]
        body = pre["scientific_body"]
        import pyarrow.parquet as pq
        census = [row for item in recipe["frozen_input"] for row in pq.read_table(self.plane / item["census_rel"]).to_pylist()]
        resolved = resolve_research_scope(body, self.plane, census, recipe["frozen_input"])
        self.assertEqual(resolved.coverage()["signal_unknown_n"], 24)
        recipe["research_scope_evidence"] = {"evidence_sha256": resolved.evidence_sha256, "bindings": resolved.evidence_bindings}
        recipe["research_scope_rule_sha256"] = resolved.rule_sha256
        recorder = ReaderOracle()
        with patch("pyarrow.parquet.read_table", recorder.read):
            refused = self.classify(spec)
        self.assertEqual(refused.reason_codes, ("SCOPE_COVERAGE_UNRESOLVED",))
        self.assertFalse(any("typed_value" in (t["columns"] or []) for t in recorder.trace))


if __name__ == "__main__":
    unittest.main()
