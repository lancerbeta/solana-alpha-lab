"""Ordinary registered native path, actual file reader and cold consumer oracle."""
from __future__ import annotations

import json
import copy
import contextlib
import io
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq

from solana_alpha_lab.factory.application import FactoryApplication, ApplicationError
from solana_alpha_lab.factory.capabilities import execute_capability
from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.list_a_confirmation import compose_confirmation_dossier, read_confirmation
from solana_alpha_lab.factory.list_a_confirmation_inputs import (
    DEFINITION, authorize_confirmation, prepare_confirmation, validate_confirmation_result, ConfirmationError, event,
)
from solana_alpha_lab.factory.list_a_confirmation_method import digest
from solana_alpha_lab.factory.lane_classifier import classify_lane
from solana_alpha_lab.factory.research_store import ResearchStore, RecordKind
from solana_alpha_lab.factory.research_workbench import parse_locator
from tests.fixtures.list_a_confirmation_v1.native import NOW, ingress
from scripts import list_a_confirmation as cli

ROOT = Path(__file__).resolve().parents[1]


def daily_ownership_oracle(store, sample_ref, expected, result=None):
    """Independent file/date/join oracle; no producer clock/membership functions."""
    sample = json.loads((store.root/sample_ref).read_bytes())
    assert sample["schema_version"] == "1.1" and "schedule_rel" not in sample
    for path, sha in sample["source_hashes"].items():
        assert hashlib.sha256((store.root/path).read_bytes()).hexdigest() == sha
    owners, days = {}, set()
    for owner in sample["schedule_set"]:
        doc = json.loads((store.root/owner["schedule_rel"]).read_bytes())
        sha = doc["schedule_sha256"]
        assert sha not in owners
        a, b = (datetime.fromisoformat(doc["activation"][k].replace("Z","+00:00")) for k in ("starts_at","stops_admitting_at"))
        assert b-a == timedelta(days=1) and a.hour == a.minute == a.second == 0
        assert a.date() not in days
        days.add(a.date())
        owners[sha] = (owner["activation_id"], a, b)
    admissions = json.loads((store.root/sample["admissions_rel"]).read_bytes())
    frames = json.loads((store.root/sample["frames_rel"]).read_bytes())
    census = pq.read_table(store.root/sample["census_rel"],columns=["episode_id","mint","t0","cohort_id","round_id"]).to_pylist()
    assert len(census) == len(admissions) == len(expected) == 256
    actual = {r["episode_id"]:r for r in census}
    assert len(actual) == 256 and set(actual) == set(admissions) == {r["episode_id"] for r in expected}
    for row in expected:
        eid = row["episode_id"]
        admission, source = admissions[eid], actual[eid]
        activation, a, b = owners[admission["schedule_sha256"]]
        assert admission["schedule_sha256"] == row["schedule_sha256"]
        assert admission["activation_id"] == row["activation_id"] == activation == frames[source["round_id"]]["activation_id"]
        assert a <= datetime.fromisoformat(source["t0"].replace("Z","+00:00")) < b
        assert source["cohort_id"] == row["cohort_id"] and source["mint"] == row["mint"]
    if result is not None:
        population = result["population"]
        assert population["admitted"] == population["scope_known"] == 256
        assert population["decision_denominators"] == {"A":128,"C":128}
        observed = [{k:r[k] for k in ("episode_id","mint","group","decision_nominal_due")} for r in population["membership"]]
        oracle = [{k:r[k] for k in ("episode_id","mint","group","decision_nominal_due")} for r in expected]
        assert sorted(observed,key=lambda r:r["episode_id"]) == sorted(oracle,key=lambda r:r["episode_id"])
    return {"schedule_owners":len(owners),"UTC_days":len(days),"admissions":len(actual),
            "original_schedule_activation_ownership":"PASS","full_population":"PASS"}


def bound(store, *, case="POSITIVE", missing_a=0, source_id="SYNTH-LIST-A-V1", origin_label=None, **source_options):
    sample, oracle = ingress(ROOT, store, case, missing_a=missing_a, source_id=source_id, origin_label=origin_label, **source_options)
    spec = load_experiment_spec(ROOT, DEFINITION)
    prepared = prepare_confirmation(spec, sample, root=ROOT, store=store, now=NOW)
    if prepared["status"] == "ALREADY_RESERVED":
        return spec, prepared, oracle
    authorize_confirmation(spec, prepared["binding_id"], root=ROOT, store=store, now=NOW,
        valid_until="2027-02-01T00:00:00Z", owner_phrase="AUTHORIZE SYNTHETIC LIST A " + prepared["request_sha256"])
    return spec, prepared, oracle


class ValueReader:
    """Observe actual decoder calls and fail an intentional pre-reserve canary."""
    def __init__(self, store):
        self.store, self.original, self.reads = store, pq.read_table, []

    def read(self, path, *args, **kwargs):
        if Path(path).name == "observations.parquet":
            reserved = any(r.record_kind == "RUN_STARTED" for r in self.store.iter_committed_records())
            assert reserved, "NUMERIC_READ_BEFORE_COMMITTED_RESERVATION"
            assert kwargs.get("columns") is not None
            fields = {k for k, _, _ in kwargs.get("filters", [])}
            if "typed_value" in kwargs["columns"]:
                assert {"episode_id", "cohort_id", "release_id", "field_id", "point_id"} <= fields
            self.reads.append({"columns": kwargs["columns"], "filters": kwargs.get("filters", [])})
        return self.original(path, *args, **kwargs)


class VerticalTests(unittest.TestCase):
    def test_native_daily_schedule_set_vertical_and_cold_dossier(self):
        with tempfile.TemporaryDirectory(prefix="list-a-daily-unit-") as tmp:
            store = ResearchStore(Path(tmp)/"plane")
            reader = ValueReader(store)
            with patch.object(pq, "read_table", reader.read):
                spec, prepared, oracle = bound(store, daily_schedules=True)
                self.assertEqual(reader.reads, [])
                sample_ref = "confirmation/sources/SYNTH-LIST-A-V1/sample.json"
                daily_ownership_oracle(store,sample_ref,oracle)
                lane = classify_lane({"experiment_spec":spec,"execution_binding_id":prepared["binding_id"]},
                    root=ROOT,data_root=store.root,as_of=NOW)
                self.assertEqual(lane.terminal,"FAST_LANE_READY")
                response = DocumentRunner(root=ROOT,store=None).start_document(spec,spec_sha256="0"*64,
                    run_context=RunContext(store.root,"0"*64,lane),capture_hooks={"execution_context":{
                        "binding_id":prepared["binding_id"],"now":NOW}})
            result = response["result"]
            self.assertEqual(result["method"]["contrast"],0.125)
            self.assertEqual(response["protocol_terminal"],"ASSOCIATION_SUPPORTED_CONDITIONAL")
            self.assertEqual(daily_ownership_oracle(store,sample_ref,oracle,result)["schedule_owners"],32)
            for group in ("A","C"):
                self.assertGreaterEqual(result["method"]["support"][group]["mints"],30)
                for h in ("86400","172800"):
                    self.assertGreaterEqual(result["method"]["support"][group]["blocks"][h],30)
            before = store.diagnostics().committed_inventory_sha256
            with patch.object(pq,"read_table",side_effect=AssertionError("COLD_NO_PARQUET")), patch(
                    "solana_alpha_lab.factory.list_a_confirmation.evaluate_native",side_effect=AssertionError("COLD_NO_EVALUATOR")), patch.object(
                    ResearchStore,"append",side_effect=AssertionError("COLD_NO_WRITES")):
                cold = read_confirmation(ResearchStore(store.root,create_if_missing=False),trial_id=response["trial_id"],root=ROOT)
                self.assertEqual(cold["new_evaluator_invocations"],0)
                dossier = FactoryApplication(root=ROOT,research_data_root=store.root).research_detail(
                    parse_locator(spec["experiment_id"],"GIT","EXPERIMENT_SPEC"))["dossier"]
                self.assertEqual(next(o for o in dossier["obligations"] if o["code"]=="RESULT")["status"],"PRESENT")
                self.assertFalse(dossier["science_guard"]["allowed"])
            self.assertEqual(before,store.diagnostics().committed_inventory_sha256)

    def test_positive_real_vertical_reader_dossier_pause_and_repeat(self):
        with tempfile.TemporaryDirectory(prefix="list-a-unit-") as tmp:
            store = ResearchStore(Path(tmp) / "plane")
            oracle_reader = ValueReader(store)
            with patch.object(pq, "read_table", oracle_reader.read):
                spec, prepared, oracle = bound(store)
                self.assertEqual(oracle_reader.reads, [])
                # Intentional forbidden decoder: instrumentation must catch it.
                with self.assertRaisesRegex(AssertionError, "BEFORE_COMMITTED"):
                    pq.read_table(store.root / "confirmation/sources/SYNTH-LIST-A-V1/observations.parquet")
                lane = classify_lane({"experiment_spec": spec, "execution_binding_id": prepared["binding_id"]},
                                     root=ROOT, data_root=store.root, as_of=NOW)
                self.assertEqual(lane.terminal, "FAST_LANE_READY")
                response = DocumentRunner(root=ROOT, store=None).start_document(spec,
                    spec_sha256="0" * 64, run_context=RunContext(store.root, "0" * 64, lane),
                    capture_hooks={"execution_context": {"binding_id": prepared["binding_id"], "now": NOW}})
            self.assertEqual(response["protocol_terminal"], "ASSOCIATION_SUPPORTED_CONDITIONAL")
            result = response["result"]
            self.assertEqual(result["method"]["contrast"], 0.125)
            self.assertEqual(result["method"]["support"]["A"]["mints"], 127)
            for h in ("86400", "172800"):
                self.assertEqual(result["method"]["partitions"][h]["interval"], [0.125, 0.125])
                self.assertEqual(result["method"]["partitions"][h]["valid_replicates"], 4096)
            actual = [{k: r[k] for k in ("episode_id", "mint", "group", "decision_nominal_due")} for r in result["population"]["membership"]]
            expected = [{k: r[k] for k in ("episode_id", "mint", "group", "decision_nominal_due")} for r in oracle]
            self.assertEqual(sorted(actual, key=lambda r: r["episode_id"]), sorted(expected, key=lambda r: r["episode_id"]))
            before = store.diagnostics().committed_inventory_sha256
            original_read = pq.read_table
            def cold_reader(path, *args, **kwargs):
                if Path(path).name == "observations.parquet":
                    raise AssertionError("COLD_VALUE_DECODER")
                return original_read(path, *args, **kwargs)
            with patch.object(pq, "read_table", cold_reader), patch(
                    "solana_alpha_lab.factory.list_a_confirmation.calculate_list_a", side_effect=AssertionError("COLD_EVALUATOR")), patch.object(
                    ResearchStore, "append", side_effect=AssertionError("COLD_STORE_WRITE")):
                saved = read_confirmation(store, trial_id=response["trial_id"], root=ROOT)
                self.assertEqual(saved["new_evaluator_invocations"], 0)
                repeated = execute_capability(spec, root=ROOT, capture_hooks={"execution_context": {
                    "binding_id": prepared["binding_id"], "data_root": store.root, "now": NOW}})
                self.assertEqual(repeated["new_evaluator_invocations"], 0)
            self.assertEqual(before, store.diagnostics().committed_inventory_sha256)
            app = FactoryApplication(root=ROOT, research_data_root=store.root)
            locator = parse_locator(spec["experiment_id"], "GIT", "EXPERIMENT_SPEC")
            detail = app.research_detail(locator)
            dossier = detail["dossier"]
            self.assertEqual(next(o for o in dossier["obligations"] if o["code"] == "RESULT")["status"], "PRESENT")
            self.assertFalse(dossier["science_guard"]["allowed"])
            command = {"entity_id": spec["experiment_id"], "truth_plane": "GIT", "native_kind": "EXPERIMENT_SPEC",
                "expected_evidence_snapshot_sha256": dossier["evidence_snapshot_sha256"], "rationale": "Synthetic technical validation only",
                "next_condition": "Exact real source and owner grant required", "decision_kind": "PROMOTE", "promote_scientific_only": "1"}
            with self.assertRaisesRegex(ApplicationError, "PROMOTE_BLOCKED"):
                app.record_research_decision(command)
            command["decision_kind"] = "PAUSE"
            paused = app.record_research_decision(command)
            self.assertEqual(paused["decision_result"]["status"], "DECISION_RECORDED")
            latest = app.research_detail(locator)["dossier"]
            self.assertEqual(latest["planes"]["decision"], "PAUSE")
            with self.assertRaisesRegex(ApplicationError, "STALE"):
                app.record_research_decision({**command, "decision_kind": "REJECT"})
            command.update(decision_kind="REJECT", expected_evidence_snapshot_sha256=latest["evidence_snapshot_sha256"])
            app.record_research_decision(command)
            self.assertEqual(app.research_detail(locator)["dossier"]["planes"]["decision"], "REJECT")
            forged = copy.deepcopy(result)
            forged["method"]["support"] = {}
            with self.assertRaisesRegex(ConfirmationError, "TYPED_RESULT_SCHEMA_INVALID"):
                validate_confirmation_result(forged, root=ROOT)
            forged = copy.deepcopy(result)
            forged["method"]["terminal"] = "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY"
            with self.assertRaisesRegex(ConfirmationError, "RESULT_TERMINAL_CONFLICT"):
                validate_confirmation_result(forged, root=ROOT)
            txn = "RESEARCH-TXN-LA-FOREIGN-CARRIER"
            store.append([event(ROOT, record_id="FOREIGN-LA-METRIC",kind=RecordKind.EXPERIMENT_METRIC,transaction_id=txn,
                payload={**result["identity"], "result_digest_sha256":"0"*64})],transaction_id=txn)
            with self.assertRaisesRegex(ConfirmationError, "TYPED_COMPLETION_CARRIER_CONFLICT"):
                read_confirmation(store,trial_id=response["trial_id"],root=ROOT)
            conflict = app.research_detail(locator)["dossier"]
            self.assertEqual(next(o for o in conflict["obligations"] if o["code"]=="RESULT")["status"],"CONFLICT")
            self.assertEqual(conflict["planes"]["execution"], "UNKNOWN")
            self.assertEqual(len(conflict["result"]["trials"]), 1)
            checkpoint = conflict["result"]["trials"][0]
            self.assertEqual((checkpoint["trial_id"], checkpoint["scientific_charge"], checkpoint["status"]),
                             (response["trial_id"], 1, "UNVERIFIABLE"))
            inventory = store.diagnostics().committed_inventory_sha256
            with patch.object(pq, "read_table", cold_reader), patch(
                    "solana_alpha_lab.factory.list_a_confirmation.evaluate_native", side_effect=AssertionError("NO_NEW_EVALUATOR")), patch.object(
                    ResearchStore, "append", side_effect=AssertionError("NO_NEW_WRITE")):
                for command in ("status", "show"):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        code = cli.main([command, "--data-root", str(store.root), "--trial-id", response["trial_id"]])
                    denied = json.loads(stdout.getvalue())
                    self.assertEqual(code, 2)
                    self.assertEqual(denied["status"], "UNVERIFIABLE")
                    self.assertEqual(denied["scientific_charge"], 1)
                    for key in ("trial_id", "run_id", "execution_binding_sha256"):
                        self.assertEqual(denied[key], response[key])
                    self.assertEqual(denied["next_action"], "VERIFY_SAVED_ARTIFACT_KEEP_CONSUMED_ALLOWANCE")
                passport = next(json.loads(r.payload_json) for r in store.iter_committed_records()
                                if str(r.record_kind) == "RUN_COMPLETED" and json.loads(r.payload_json).get("trial_id") == response["trial_id"])
                artifact = store.root / passport["result_ref"]
                backup = artifact.with_suffix(".unit-backup")
                artifact.rename(backup)
                try:
                    for command in ("status", "show"):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            code = cli.main([command, "--data-root", str(store.root), "--trial-id", response["trial_id"]])
                        unavailable = json.loads(stdout.getvalue())
                        self.assertEqual(code, 2)
                        self.assertEqual((unavailable["scientific_charge"], unavailable["trial_id"], unavailable["status"]),
                                         (1, response["trial_id"], "UNVERIFIABLE"))
                finally:
                    backup.rename(artifact)
            self.assertEqual(inventory, store.diagnostics().committed_inventory_sha256)

    def test_unavailable_history_preserves_unknown_execution_and_decision(self):
        spec = load_experiment_spec(ROOT, DEFINITION)
        locator = parse_locator(spec["experiment_id"], "GIT", "EXPERIMENT_SPEC")
        with patch.object(pq, "read_table", side_effect=AssertionError("NO_DECODER")), patch.object(
                ResearchStore, "append", side_effect=AssertionError("NO_WRITE")):
            unknown = compose_confirmation_dossier(spec=spec, locator=locator, root=ROOT, store=None,
                store_records=None, records_status="UNAVAILABLE")
            self.assertEqual(unknown["planes"], {"execution": "UNKNOWN", "evidence": "UNKNOWN", "decision": "UNKNOWN"})
            self.assertFalse(unknown["science_guard"]["allowed"])
            empty = compose_confirmation_dossier(spec=spec, locator=locator, root=ROOT, store=None,
                store_records=[], records_status="AVAILABLE")
            self.assertEqual(empty["planes"]["execution"], "NO_RUN")
            self.assertEqual(empty["planes"]["decision"], "NO_DECISION")

    def test_null_and_insufficient_native_path(self):
        fixed_mask = None
        for case, missing, terminal in (("NULL", 0, "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY"),
                                       ("POSITIVE", 8, "INSUFFICIENT"),
                                       ("EMPTY_DECISION_A", 0, "INSUFFICIENT")):
            with self.subTest(case=case, missing=missing), tempfile.TemporaryDirectory(prefix="list-a-unit-") as tmp:
                store = ResearchStore(Path(tmp) / "plane")
                spec, p, _ = bound(store, case=case, missing_a=missing)
                response = execute_capability(spec, root=ROOT, capture_hooks={"execution_context": {
                    "binding_id": p["binding_id"], "data_root": store.root, "now": NOW}})
                self.assertEqual(response["protocol_terminal"], terminal)
                self.assertEqual(response["result"]["population"]["decision_denominators"],
                                 {"A": 0 if case == "EMPTY_DECISION_A" else 128, "C": 128})
                if case != "EMPTY_DECISION_A":
                    mask = response["result"]["population"]["membership"]
                    if fixed_mask is None:
                        fixed_mask = mask
                    else:
                        self.assertEqual(mask, fixed_mask)
                if case == "EMPTY_DECISION_A":
                    self.assertIsNone(response["result"]["method"]["coverage"]["A"])
                    self.assertIn("EMPTY_DECISION_GROUP", response["reason_codes"])
                if missing:
                    self.assertEqual(response["result"]["method"]["coverage"]["A"], 0.9375)
                    self.assertEqual(response["result"]["method"]["partitions"], {})
