"""Retained acceptance orchestration; all product state goes through native owners.

Run only in the bounded disposable filesystem container. This module is never
imported by production. Faults are OS process exits, not fabricated carriers.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq

from solana_alpha_lab.factory.application import FactoryApplication, ApplicationError
from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.list_a_confirmation import read_confirmation
from solana_alpha_lab.factory import list_a_confirmation as executor
from solana_alpha_lab.factory.list_a_confirmation_inputs import DEFINITION, records, finite_bytes
from solana_alpha_lab.factory.list_a_confirmation_method import digest
from solana_alpha_lab.factory.lane_classifier import classify_lane
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.research_workbench import parse_locator
from tests.fixtures.list_a_confirmation_v1.native import NOW
from tests.test_list_a_confirmation_vertical_v1 import bound

ROOT = Path(__file__).resolve().parents[3]
MODULE = "tests.fixtures.list_a_confirmation_v1.proof"
PLANE = Path("/proof/plane")
PROOF = Path("/proof/acceptance")
PLAN = (("positive", "POSITIVE", 0), ("null", "NULL", 0), ("missing8", "POSITIVE", 8),
        ("fault-reservation", "POSITIVE", 0), ("fault-bootstrap", "POSITIVE", 0),
        ("fault-publication", "POSITIVE", 0))


def put(name, body):
    path = PROOF / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = finite_bytes(body)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def get(name):
    return json.loads((PROOF / name).read_bytes())


def worker(case, attempt, fault=None, hold=False):
    store = ResearchStore(PLANE, create_if_missing=False)
    spec = load_experiment_spec(ROOT, DEFINITION)
    binding_id = get(case + "-binding.json")["binding_id"]
    counts = {"observation_decoder_calls": 0, "numeric_decoder_calls": 0, "evaluator_invocations": 0}
    path = PROOF / (attempt + "-reader-events.jsonl")
    original, evaluator = pq.read_table, executor.evaluate_native
    reservation_proof = None
    def log(body):
        with path.open("ab") as stream:
            stream.write(finite_bytes(body) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    def decoder(path, *args, **kwargs):
        nonlocal reservation_proof
        if Path(path).name == "observations.parquet":
            if reservation_proof is None:
                reservations = [r for r in records(store) if r["kind"] == "RESEARCH_ARTIFACT" and
                    r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
                    r["payload"].get("execution_binding_sha256") == binding_id]
                assert len(reservations) == 1, "PRE_RESERVE_DECODER_CANARY"
                reservation_proof = reservations[0]
            counts["observation_decoder_calls"] += 1
            counts["numeric_decoder_calls"] += int("typed_value" in kwargs["columns"])
            log({"event": "ACTUAL_DECODER", "columns": kwargs["columns"], "filters": kwargs.get("filters", []),
                 "reservation_id": reservation_proof["record_id"]})
        return original(path, *args, **kwargs)
    def evaluated(*args, **kwargs):
        counts["evaluator_invocations"] += 1
        log({"event": "ACTUAL_EVALUATOR_ENTRY"})
        return evaluator(*args, **kwargs)
    def phase(value):
        log({"event": "PHASE", "phase": value, **counts})
        if value == "AFTER_RESERVATION" and hold:
            put(attempt + "-lock-held.json", counts)
            end = time.monotonic() + 55
            while not (PROOF / (attempt + "-release.json")).exists():
                if time.monotonic() >= end:
                    os._exit(87)
                time.sleep(0.02)
        if value == fault:
            put(attempt + "-process-exit.json", {"phase": value, **counts})
            os._exit(86)
    try:
        with patch.object(pq, "read_table", decoder), patch.object(executor, "evaluate_native", evaluated):
            lane = classify_lane({"experiment_spec": spec, "execution_binding_id": binding_id}, root=ROOT, data_root=PLANE, as_of=NOW)
            response = DocumentRunner(root=ROOT, store=None).start_document(spec, spec_sha256="0" * 64,
                run_context=RunContext(PLANE, "0" * 64, lane), capture_hooks={"execution_context": {
                    "data_root": PLANE, "binding_id": binding_id, "now": NOW}, "phase": phase})
        put(attempt + "-response.json", {k:v for k,v in response.items() if k != "result"})
        put(attempt + "-counts.json", counts)
    except Exception as exc:
        put(attempt + "-refused.json", {"reason": getattr(exc, "code", type(exc).__name__), **counts})
        return 2
    return 0


def cold(case, attempt):
    store = ResearchStore(PLANE, create_if_missing=False)
    b = get(case + "-binding.json")["binding_id"]
    trial = next(r["payload"]["trial_id"] for r in records(store) if r["kind"] == "RESEARCH_ARTIFACT" and
                 r["payload"].get("type") == "CONFIRMATION_RESERVATION" and r["payload"].get("execution_binding_sha256") == b)
    before = store.diagnostics().committed_inventory_sha256
    def forbidden(*a, **kw): raise AssertionError("COLD_READ_WRITE_OR_EVALUATOR")
    with patch.object(pq, "read_table", forbidden), patch.object(executor, "evaluate_native", forbidden), patch.object(store, "append", forbidden):
        readback = read_confirmation(store, trial_id=trial, root=ROOT)
    assert before == store.diagnostics().committed_inventory_sha256
    result = readback.get("result")
    if result:
        actual = [{k:r[k] for k in ("episode_id","mint","group","decision_nominal_due")} for r in result["population"]["membership"]]
        expected = get(case + "-independent-membership.json")
        assert sorted(actual,key=lambda r:r["episode_id"]) == sorted(expected,key=lambda r:r["episode_id"])
        assert result["population"]["decision_denominators"] == {"A":128,"C":128}
        expected_terminal = "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY" if case == "null" else (
            "INSUFFICIENT" if case == "missing8" else "ASSOCIATION_SUPPORTED_CONDITIONAL")
        assert result["method"]["terminal"] == expected_terminal
        assert result["method"]["contrast"] == (0.0 if case == "null" else 0.125)
        if case != "missing8":
            assert all(p["interval"] == ([0.0,0.0] if case == "null" else [0.125,0.125]) for p in result["method"]["partitions"].values())
    put(attempt + "-cold-readback.json", {**{k:v for k,v in readback.items() if k != "result"},
        "result_digest_sha256":digest(result) if result else None,"inventory_unchanged":True,
        "actual_value_decoder_calls":0,"actual_evaluator_invocations":0,"actual_writes":0,
        "independent_native_membership": "PASS" if result else "PENDING"})
    return 0


def process(*args):
    return subprocess.Popen([sys.executable,"-B","-m",MODULE,*args],cwd=ROOT)


def campaign():
    PROOF.mkdir(parents=True,exist_ok=False)
    store = ResearchStore(PLANE)
    put("fixed-plan.json", {"cases":PLAN,"adaptive_allowance":0,"max_attempts_per_study":1,
        "domain":"SYNTHETIC","real_binding":"UNBOUND","real_value_read_authorized":False})
    original = pq.read_table
    def metadata_only(path,*args,**kwargs):
        assert Path(path).name != "observations.parquet", "PREPARE_VALUE_DECODER"
        return original(path,*args,**kwargs)
    for case, world, missing in PLAN:
        with patch.object(pq,"read_table",metadata_only):
            spec,b,oracle = bound(store,case=world,missing_a=missing,source_id="SYNTH-PROOF-"+case.upper())
        put(case+"-binding.json", b)
        put(case+"-independent-membership.json",[{k:r[k] for k in ("episode_id","mint","group","decision_nominal_due")} for r in oracle])
    first=process("worker","positive","positive-first","--fault","AFTER_COMPLETION","--hold")
    end=time.monotonic()+55
    while not (PROOF/"positive-first-lock-held.json").exists():
        assert first.poll() is None and time.monotonic()<end
        time.sleep(0.02)
    second=process("worker","positive","positive-contender")
    assert second.wait(timeout=30)==2
    assert get("positive-contender-refused.json")["reason"]=="STUDY_EVALUATOR_BUSY"
    put("positive-first-release.json", {"concurrent_second_refused":True})
    assert first.wait(timeout=60)==86
    assert process("cold","positive","positive-first").wait(timeout=30)==0
    assert process("worker","positive","positive-repeat").wait(timeout=30)==0
    assert get("positive-repeat-counts.json")=={"observation_decoder_calls":0,"numeric_decoder_calls":0,"evaluator_invocations":0}
    for case in ("null","missing8"):
        assert process("worker",case,case+"-first").wait(timeout=60)==0
        assert process("cold",case,case+"-first").wait(timeout=30)==0
    for case, point in (("fault-reservation","AFTER_RESERVATION"),("fault-bootstrap","AFTER_BOOTSTRAP"),("fault-publication","AFTER_RESULT_PUBLICATION")):
        assert process("worker",case,case+"-first","--fault",point).wait(timeout=60)==86
        assert process("cold",case,case+"-pending").wait(timeout=30)==0
        assert get(case+"-pending-cold-readback.json")["status"]=="INTERRUPTED"
        assert process("worker",case,case+"-resume").wait(timeout=60)==0
        assert process("cold",case,case+"-completed").wait(timeout=30)==0
    app=FactoryApplication(root=ROOT,research_data_root=PLANE)
    locator=parse_locator(spec["experiment_id"], "GIT", "EXPERIMENT_SPEC")
    dossier=app.research_detail(locator)["dossier"]
    assert next(o for o in dossier["obligations"] if o["code"]=="RESULT")["status"]=="PRESENT"
    assert len(dossier["result"]["trials"])==6 and not dossier["science_guard"]["allowed"]
    command={"entity_id":spec["experiment_id"],"truth_plane":"GIT","native_kind":"EXPERIMENT_SPEC",
        "expected_evidence_snapshot_sha256":dossier["evidence_snapshot_sha256"],"rationale":"Synthetic technical acceptance",
        "next_condition":"Exact real source and grant","decision_kind":"PROMOTE","promote_scientific_only":"1"}
    try: app.record_research_decision(command)
    except ApplicationError as exc: assert "PROMOTE_BLOCKED" in str(exc)
    else: raise AssertionError("SYNTHETIC_PROMOTE_ACCEPTED")
    command["decision_kind"]="PAUSE"
    assert app.record_research_decision(command)["decision_result"]["status"]=="DECISION_RECORDED"
    assert app.research_detail(locator)["dossier"]["planes"]["decision"]=="PAUSE"
    reservations=[r for r in records(store) if r["kind"]=="RESEARCH_ARTIFACT" and r["payload"].get("type")=="CONFIRMATION_RESERVATION"]
    assert len(reservations)==6 and len({r["payload"]["study_budget_sha256"] for r in reservations})==6
    put("completion.json",{"status":"PASS","scientific_attempts":6,"charges":6,"adaptive_allowance":0,
        "actual_evaluator_invocations":8,"cold_value_reads":0,"cold_evaluator_invocations":0,
        "concurrency":"ONE_EVALUATOR","crash_exact_resume":"PASS","ordinary_dossier":"PRESENT",
        "ordinary_pause":"RECORDED","promote":"BLOCKED","real_binding":"UNBOUND","real_executions":0,
        "cases":PLAN,"result_refs":[r["payload"]["result_ref"] for r in records(store) if r["kind"]=="RUN_COMPLETED"]})
    print("NATIVE_CONTAINED_ACCEPTANCE_PASS",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["campaign","worker","cold"])
    parser.add_argument("case",nargs="?")
    parser.add_argument("attempt",nargs="?")
    parser.add_argument("--fault")
    parser.add_argument("--hold",action="store_true")
    args=parser.parse_args()
    if args.command=="campaign": campaign()
    elif args.command=="worker": sys.exit(worker(args.case,args.attempt,args.fault,args.hold))
    else: sys.exit(cold(args.case,args.attempt))
