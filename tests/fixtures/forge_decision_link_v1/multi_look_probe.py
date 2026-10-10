"""Native parent/ADAPTIVE continuity, durable interruption and exact cold read.

Synthetic allowances are frozen before either look. Every product command runs
in a fresh child process; fault children stop after actual committed boundaries.
No operation/result/disposition join is injected into ResearchStore.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tests.fixtures.forge_decision_link_v1.entry_probe import BASE, Invocation, files, save, utc_now

FOCUS = "FORGE_DECISION_LINK_MULTI_SYNTHETIC"
PLAN_ONE = "P1_PRE_VALUE " + json.dumps({
    "question": "Does A membership separate the fixed synthetic price-relative outcome from its complement?",
    "alternatives": [
        {"id": "A_POSITIVE", "prediction": "Observed mean proxy return in A exceeds its complement."},
        {"id": "A_NONPOSITIVE", "prediction": "Observed mean proxy return in A is equal to or below its complement."}],
    "selected_discriminator": "One supported LIST_CONTRAST of A versus complement at E1800/E14400.",
    "choice_reason": "The fixed membership contrast can distinguish these descriptive predictions without selecting numeric thresholds.",
    "strongest_rejected_choice": "A numeric condition within A; it adds a condition before the simpler contrast is characterized.",
    "outcome_actions": {
        "PASS": "Retain only the bound positive descriptive contrast; B may be considered only through the already fixed ADAPTIVE allowance after R1.",
        "FAIL": "Reject the A-positive descriptive prediction on this bound fixture; do not close a family or transfer the conclusion to B.",
        "INCONCLUSIVE": "Keep missing-target/dependency uncertainty explicit; no forced candidate or scientific KILL. A B clarification can only be an exposed ADAPTIVE continuation.",
        "INFRA_FAILURE": "Repair and resume the original exact pending request; do not treat execution failure as a negative scientific result or grant another look."},
    "forbidden_claims": ["No alpha/OOS/economics", "Proxy return is not NetReturn", "No family close/PROMOTE/new scientific authority"],
    "authority": "Authored advisory only; the existing native request and accounting owners retain authority."
}, sort_keys=True)
PLAN_TWO = "P2_PRE_VALUE " + json.dumps({
    "question": "After R1, does the same positive descriptive contrast transfer to B?",
    "why_after_R1": "R1 has A mean .10 versus complement -.10, with only three of four A targets observed; transfer to another list is still unresolved.",
    "exposure": "R1 has been read. T2 is ADAPTIVE, not an independent preregistered MAIN; its adaptation_of names T1.",
    "alternatives": [
        {"id": "B_POSITIVE", "prediction": "B has a positive descriptive contrast as A did."},
        {"id": "B_NONPOSITIVE", "prediction": "B has a zero or negative contrast; A's contrast does not transfer to B."}],
    "selected_discriminator": "A materially distinct supported LIST_CONTRAST of B versus complement on the same clocks and proxy.",
    "choice_reason": "Change the list while preserving measurement to distinguish transfer from an A-bound pattern, spending the already fixed one ADAPTIVE allowance.",
    "strongest_rejected_choice": "Repeat A under a rewritten explanation; it cannot resolve B transfer and cannot replace the original occupied plan.",
    "outcome_actions": {
        "PASS": "Retain the bounded B-positive descriptive contrast; dependency/missingness still prevent alpha or transfer outside this fixture.",
        "FAIL": "Do not transfer A's positive contrast to B; retain the A result and B's own negative descriptive result separately, without a family ban.",
        "INCONCLUSIVE": "Leave B transfer unresolved and disclose target gaps; stop without inventing settled zero outcomes or an extra allowance.",
        "INFRA_FAILURE": "Preserve P2 and its exact reservation; diagnose infrastructure and resume the same request without a new science charge."},
    "forbidden_claims": ["No independent MAIN claim", "No new quota from explanation", "No family close/reopen/PROMOTE", "No alpha/OOS/economics"],
    "authority": "Conditional authored advice only; native result refs, applicability and budget gates remain authoritative."
}, sort_keys=True)
EXTRA_SOURCES = ["tests/fixtures/forge_decision_link_v1/multi_look_probe.py", "tests/test_forge_decision_link_v1.py",
    "src/solana_alpha_lab/factory/hfic_discovery_detail.py",
    "src/solana_alpha_lab/factory/hfic_card_projection.py",
    "src/solana_alpha_lab/factory/hfic_preflight.py",
    "src/solana_alpha_lab/factory/hfic_temporal_discovery.py",
    "configs/factory_semantic_operability_v1.yaml"]


def fault_child(mode: str, trace: Path, argv: list[str], barrier: Path | None = None) -> int:
    """Instrument ordering only; all writers, admissions and evaluators are real."""
    from scripts import hypothesis_forge as cli
    from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
    from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary

    state = {"mode": mode, "loader_calls": 0, "evaluator_calls": 0, "trace": []}
    native_loader = discovery.load_admitted_partition_rows
    def loader(*args, **kwargs):
        state["loader_calls"] += 1
        state["trace"].append("VALUES_LOADER")
        save(trace, state)
        return native_loader(*args, **kwargs)
    discovery.load_admitted_partition_rows = loader
    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
    native_evaluator = temporal.execute_temporal_discovery
    def evaluator(*args, **kwargs):
        state["evaluator_calls"] += 1
        state["trace"].append("EVALUATOR")
        save(trace, state)
        return native_evaluator(*args, **kwargs)
    temporal.execute_temporal_discovery = evaluator

    def stop(boundary, body, code):
        state["trace"].append(boundary)
        state["boundary"] = boundary
        state["native_boundary"] = body
        save(trace, state)
        print(json.dumps(state, ensure_ascii=False), flush=True)
        os._exit(code)

    if mode in {"reservation", "observe", "race"}:
        native = ordinary._reserve
        def reserve(store, operation, **kwargs):
            if mode == "race":
                if barrier is None:
                    raise ValueError("RACE_BARRIER_REQUIRED")
                save(barrier / (trace.parent.name + ".ready.json"), {
                    "operation_sha256": operation["operation_sha256"],
                    "question_text": operation["question_text"], "spec_sha256": kwargs["spec_sha256"],
                    "process_id": os.getpid()})
                state["precommit_barrier"] = "WAITING_BEFORE_NATIVE_RESERVATION"
                save(trace, state)
                began = time.monotonic()
                while not (barrier / "release.json").exists():
                    if time.monotonic() - began > 150:
                        raise AssertionError("RACE_BARRIER_WATCHDOG")
                    time.sleep(.02)
            native(store, operation, **kwargs)
            reservations = ordinary._iter_kind(store, ordinary.RESERVATION_KIND)
            boundary = {
                "operation": ordinary.get_operation(store, operation["operation_sha256"]),
                "reservations": reservations, "inventory_sha256": store.diagnostics().committed_inventory_sha256}
            if mode in {"reservation", "race"}:
                stop("DURABLE_RESERVATION_BEFORE_VALUES", boundary, 74)
            state["trace"].append("DURABLE_RESERVATION_BEFORE_VALUES")
            state["pre_value_boundary"] = boundary
            save(trace, state)
        ordinary._reserve = reserve
    elif mode == "result":
        native = discovery.run_recorded_discovery_query
        def recorded(store, **kwargs):
            answer = native(store, **kwargs)
            stop("DURABLE_RESULT_ACK_LOST", {"result_refs": answer["result_refs"],
                "result_sha256": answer["result_sha256"],
                "inventory_sha256": store.diagnostics().committed_inventory_sha256}, 75)
        discovery.run_recorded_discovery_query = recorded
    elif mode == "rollback":
        baseline = subprocess.check_output(["git", "show", BASE + ":scripts/hypothesis_forge.py"], cwd=ROOT)
        retained = trace.parent / "baseline-script.py.txt"
        retained.write_bytes(baseline)
        state.update({"baseline_ref": BASE, "baseline_script_sha256": hashlib.sha256(baseline).hexdigest(),
            "baseline_blob_command": ["git", "show", BASE + ":scripts/hypothesis_forge.py"],
            "scope": "FROZEN_PUBLIC_CLI_SCRIPT_WITH_CURRENT_UNCHANGED_SCIENTIFIC_DISPOSITION_OWNER"})
        source = "src/solana_alpha_lab/factory/hfic_scientific_disposition.py"
        original_owner = subprocess.check_output(["git", "show", BASE + ":" + source], cwd=ROOT)
        assert original_owner == (ROOT / source).read_bytes(), "ROLLBACK_OWNER_CHANGED_OUTSIDE_FROZEN_SCRIPT_SCOPE"
        state["unchanged_scientific_owner_sha256"] = hashlib.sha256(original_owner).hexdigest()
        save(trace, state)
        sys.argv = ["hypothesis_forge.py", *argv]
        scope = {"__name__": "__main__", "__file__": str(ROOT / "scripts/hypothesis_forge.py"),
            "__package__": None, "__cached__": None}
        try:
            exec(compile(baseline, scope["__file__"], "exec"), scope)
        except SystemExit as stopped:
            result = 0 if stopped.code is None else stopped.code
        else:
            result = 0
        save(trace, state)
        return result
    else:
        raise ValueError("FAULT_MODE_INVALID")
    sys.argv = ["hypothesis_forge.py", *argv]
    result = cli.main()
    save(trace, state)
    return result


class ProbeInvocation(Invocation):
    def __init__(self, out: Path, resume: bool):
        expected_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        super().__init__(out, resume, expected_head)
        self.sources.update({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in EXTRA_SOURCES})
        for relative in EXTRA_SOURCES:
            target = self.path / "source-inputs" / (relative + ".txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        start = json.loads((self.path / "start.json").read_text(encoding="utf-8"))
        start.update({"source_sha256": self.sources, "probe": "MULTI_LOOK_NATIVE_PARENT_CONTINUATION",
            "argv": ["<PYTHON>", "-B", "tests/fixtures/forge_decision_link_v1/multi_look_probe.py",
                *[self.normalize(a) for a in sys.argv[1:]]]})
        save(self.path / "start.json", start)

    def fault(self, plane: Path, name: str, mode: str, argv: tuple[str, ...], expected: int) -> dict:
        self.disk_guard()
        directory = self.path / f"{len(self.commands) + 1:03d}-{name}"
        directory.mkdir()
        inputs = {}
        for value in argv:
            candidate = Path(str(value))
            if candidate.is_file() and candidate.is_relative_to(self.out):
                relative = candidate.relative_to(self.out).as_posix()
                retained = directory / "inputs" / relative
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_bytes(candidate.read_bytes())
                inputs[relative] = hashlib.sha256(retained.read_bytes()).hexdigest()
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--fault-child", mode,
            "--trace", str(directory / "native-trace.json"), "--", "--root", str(ROOT),
            "--data-root", str(plane), *argv]
        safe = ["<PYTHON>", *[self.normalize(a) for a in command[1:]]]
        save(directory / "request.json", {"name": name, "argv": safe, "input_sha256": inputs,
            "expected_exit_code": expected, "watchdog_seconds": 180})
        began, started_at = time.monotonic(), utc_now()
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "SMIAL_DATA_ROOT": str(plane)}
        try:
            done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
            code, stdout, stderr, timeout = done.returncode, done.stdout, done.stderr, False
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr, timeout = None, exc.stdout or b"", exc.stderr or b"", True
        (directory / "stdout.txt").write_bytes(stdout)
        (directory / "stderr.txt").write_bytes(stderr)
        entry = {"artifact": name + ".json", "argv": safe, "exit_code": code, "started_at": started_at,
            "completed_at": utc_now(), "subprocess_wall_seconds": time.monotonic() - began,
            "timed_out": timeout, "command_directory": directory.relative_to(self.out).as_posix(),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
        save(directory / "command.json", entry)
        self.commands.append(entry)
        self.disk_guard()
        if timeout or code != expected:
            raise AssertionError(f"FAULT_STAGE_EXIT:{name}:{code}")
        body = json.loads(stdout)
        body["_native_trace"] = json.loads((directory / "native-trace.json").read_text(encoding="utf-8"))
        save(self.out / (name + ".json"), body)
        return body

    def race(self, plane: Path, actors: list[tuple[str, tuple[str, ...]]], *, unrelated_append) -> list[dict]:
        """The declared V07 race is the sole two-process product window."""
        barrier = self.path / "race-barrier"
        barrier.mkdir()
        children = []
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "SMIAL_DATA_ROOT": str(plane)}
        for name, argv in actors:
            self.disk_guard()
            directory = self.path / f"{len(self.commands) + len(children) + 1:03d}-{name}"
            directory.mkdir()
            inputs = {}
            for value in argv:
                candidate = Path(str(value))
                if candidate.is_file() and candidate.is_relative_to(self.out):
                    relative = candidate.relative_to(self.out).as_posix()
                    retained = directory / "inputs" / relative
                    retained.parent.mkdir(parents=True, exist_ok=True)
                    retained.write_bytes(candidate.read_bytes())
                    inputs[relative] = hashlib.sha256(retained.read_bytes()).hexdigest()
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--fault-child", "race",
                "--trace", str(directory / "native-trace.json"), "--barrier", str(barrier), "--",
                "--root", str(ROOT), "--data-root", str(plane), *argv]
            safe = ["<PYTHON>", *[self.normalize(value) for value in command[1:]]]
            save(directory / "request.json", {"name": name, "argv": safe, "input_sha256": inputs,
                "expected_exit_codes": [74, 2], "watchdog_seconds": 180})
            children.append((name, directory, safe, time.monotonic(), utc_now(),
                subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)))
        failure = None
        answers = []
        try:
            began = time.monotonic()
            while len(list(barrier.glob("*.ready.json"))) != len(actors):
                if time.monotonic() - began > 150 or any(child[-1].poll() is not None for child in children):
                    raise AssertionError("RACE_ACTOR_DID_NOT_REACH_PRECOMMIT_BARRIER")
                time.sleep(.02)
            unrelated_append()
            save(barrier / "release.json", {"released_at": utc_now(), "unrelated_append_completed": True})
        except Exception as exc:
            failure = exc
        finally:
            for name, directory, safe, began, started_at, process in children:
                timed_out = False
                if failure and process.poll() is None:
                    # This exact Popen handle belongs to this invocation. A
                    # failed barrier/callback never leaves a waiting writer.
                    process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=max(.1, 180 - (time.monotonic() - began)))
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    timed_out = True
                (directory / "stdout.txt").write_bytes(stdout)
                (directory / "stderr.txt").write_bytes(stderr)
                entry = {"artifact": name + ".json", "argv": safe, "exit_code": process.returncode,
                    "started_at": started_at, "completed_at": utc_now(), "subprocess_wall_seconds": time.monotonic() - began,
                    "timed_out": timed_out, "command_directory": directory.relative_to(self.out).as_posix(),
                    "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
                save(directory / "command.json", entry)
                self.commands.append(entry)
                try:
                    body = json.loads(stdout)
                    body["_exit_code"] = process.returncode
                    body["_native_trace"] = json.loads((directory / "native-trace.json").read_text(encoding="utf-8"))
                    save(self.out / (name + ".json"), body)
                    answers.append(body)
                except (ValueError, OSError):
                    failure = failure or AssertionError("RACE_ACTOR_OUTPUT_UNAVAILABLE")
                if timed_out:
                    failure = failure or AssertionError("RACE_ACTOR_WATCHDOG")
            self.disk_guard()
        if failure:
            raise failure
        return answers


def frozen_context_binding(plane, store, pre):
    """Verify existing source bytes and retain actual locators before values."""
    from solana_alpha_lab.factory.hfic_preflight import verify_forge_context_packet
    from solana_alpha_lab.factory.run_passport import canonical_sha256
    unsigned = {key: value for key, value in pre.items() if key != "preflight_receipt_sha256"}
    assert canonical_sha256(unsigned) == pre["preflight_receipt_sha256"]
    packet = verify_forge_context_packet(plane, pre["forge_context_packet_sha256"])
    assert packet == pre["forge_context_packet"]
    assert canonical_sha256(packet) == pre["forge_context_packet_sha256"]
    context_sources = []
    for record in store.iter_committed_records():
        if getattr(record.record_kind, "value", record.record_kind) != "RESEARCH_ARTIFACT":
            continue
        wrapper = json.loads(record.payload_json)
        if wrapper.get("artifact_kind") == "FORGE_CONTEXT_PACKET" \
                and wrapper.get("payload_sha256") == pre["forge_context_packet_sha256"]:
            assert canonical_sha256(json.loads(wrapper["payload_canonical"])) == pre["forge_context_packet_sha256"]
            context_sources.append(record.record_id)
    assert len(context_sources) == 1, "FROZEN_NATIVE_CONTEXT_SOURCE_NOT_UNIQUE"
    return {"preflight_receipt_ref": pre["receipt_id"],
        "preflight_receipt_sha256": pre["preflight_receipt_sha256"],
        "context_packet_ref": context_sources[0], "context_packet_sha256": pre["forge_context_packet_sha256"],
        "journal_scope": pre["search_key_sha256"], "owner_focus": pre["owner_focus"],
        "market_evidence_epoch_sha256": pre["market_evidence_epoch_sha256"],
        "context_verification": "EXACT_EXISTING_NATIVE_PACKET_AND_RECEIPT_BYTES"}


def authored_plan(text, query, context, *, prior_look=None):
    from solana_alpha_lab.factory.hfic_temporal_discovery import canonical_temporal_spec, validate_temporal_query
    from solana_alpha_lab.factory.run_passport import canonical_sha256
    refs = {**context, "canonical_temporal_spec_sha256": canonical_sha256(canonical_temporal_spec(query)),
        "query_hash_form": "NATIVE_NORMALIZED_ENVELOPE; raw ingress JSON bytes are not claimed",
        "scientific_spec_sha256": validate_temporal_query(query)["spec_sha256"],
        "authorship_state": "PRE_T1_VALUES" if prior_look is None else "POST_R1_EXPOSED_PRE_T2_VALUES"}
    if prior_look is not None:
        refs["prior_result"] = {"result_ref": prior_look["record_id"], "result_sha256": prior_look["result_sha256"],
            "prior_spec_sha256": prior_look["spec_sha256"],
            "observed_fact": prior_look["result"]["research_scope"]["matched"],
            "scientific_transfer": "NOT_ESTABLISHED_BY_DESCRIPTIVE_FACT"}
    return text + " BASIS_REFS=" + json.dumps(refs, ensure_ascii=False, sort_keys=True)


def execute(out: Path, invocation: ProbeInvocation, args) -> dict:
    from tests.test_forge_research_flow_reliability_v1 import create_episode_fixture
    from tests.test_hfic_list_aware_vertical_v1 import draft
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label, validate_temporal_query
    from solana_alpha_lab.factory.research_store import ResearchStore

    def input_file(name, body):
        path = out / (name + ".json")
        save(path, body)
        return str(path)
    if args.cold_only:
        pass
    elif args.fixture_source:
        import shutil
        shutil.copytree(args.fixture_source, out / "fixture")
    else:
        create_episode_fixture(out / "fixture")
    plane = out / "fixture" / "plane"
    store = ResearchStore(plane, create_if_missing=False)
    if args.fixture_source and not args.cold_only:
        # A relocated native fixture needs a local lookup preparation. This
        # rebuilds the index; it neither rewrites records nor resets accounting.
        inventory_before_prepare = store.diagnostics().committed_inventory_sha256
        store.prepare_write_lookup()
        assert store.diagnostics().committed_inventory_sha256 == inventory_before_prepare
        save(out / "fixture-reuse.json", {"source": invocation.normalize(args.fixture_source),
            "committed_inventory_sha256": inventory_before_prepare,
            "preparation": "NATIVE_LOCAL_WRITE_LOOKUP", "research_records_delta": 0})
    def cli(name, *argv, expected=0):
        return invocation.cli(plane, name, argv, expected)

    if args.race_only:
        return race_campaign(out, invocation, store, plane, cli, input_file)

    if args.cold_only:
        # Original files below are an independent expected-query oracle only.
        # The fresh product consumers receive existing-store native IDs alone.
        pre = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
        links = json.loads((out / "persisted-links.json").read_text(encoding="utf-8"))
        look1, look2 = links["looks"]
        op1, op2 = links["operations"]
        q1 = json.loads((out / "query-t1.json").read_text(encoding="utf-8"))
        q2 = json.loads((out / "query-t2.json").read_text(encoding="utf-8"))
        p1 = json.loads((out / "request-p1.json").read_text(encoding="utf-8"))
        p2 = json.loads((out / "request-p2.json").read_text(encoding="utf-8"))
        assert ordinary.journal_occupancy(store, pre["search_key_sha256"]) == links["occupancy"]
        return cold_consumer(plane, store, cli, invocation, journal=pre["search_key_sha256"],
            focus=pre["owner_focus"], look1=look1, look2=look2, op1=op1, op2=op2,
            q1=q1, q2=q2, plan1=p1["question_text"], plan2=p2["question_text"], occupancy=links["occupancy"])

    # Freeze both allowances before P1: no budget extension/reset after R1.
    save(out / "campaign.json", {"synthetic_only": True, "main": 1, "adaptive": 1, "preview": 0,
        "continuation": "PUBLIC_PARENT_REQUEST_SAME_JOURNAL", "scope": FOCUS,
        "plans": [PLAN_ONE, PLAN_TWO], "scientific_meaning": "fixed fixture descriptive contrasts only"})
    q1 = cli("resolve-t1", "research-scope-resolve", "--spec", input_file("draft-t1",
        draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]})))["canonical_query"]
    pre = cli("preflight", "preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES",
        "--owner-focus", FOCUS, "--format", "json")
    journal, market, focus = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"], pre["owner_focus"]
    context = frozen_context_binding(plane, store, pre)
    save(out / "frozen-context-bindings.json", context)
    scope = {"estimand": "price_relative_proxy", "explanatory_condition": "LIST_CONTRAST",
        "population": "OPPORTUNITY_EPISODES", "decision_timestamp": "E1800", "target": temporal_target_label(q1)}
    p1 = _operation(q1, focus=focus, journal=journal, market=market, text="Frozen synthetic MAIN then ADAPTIVE continuation.",
        cap={"main": 1, "adaptive": 0, "preview": 0})
    p1["question_text"] = authored_plan(PLAN_ONE, q1, context)
    query1, scopefile, request1 = input_file("query-t1", q1), input_file("scope", scope), input_file("request-p1", p1)
    base1 = ("discovery-execute", "--store", str(plane), "--spec", query1, "--candidate-scope", scopefile,
        "--journal-scope", journal, "--format", "json")
    reserved = invocation.fault(plane, "reservation-stop", "reservation", (*base1, "--operation", request1), 74)
    assert reserved["loader_calls"] == reserved["evaluator_calls"] == 0
    op1 = reserved["native_boundary"]["operation"]
    assert op1["question_text"] == p1["question_text"]
    reservations = ordinary._iter_kind(store, ordinary.RESERVATION_KIND)
    assert len([r for r in reservations if r["journal_scope"] == journal]) == 1
    pending_before = ordinary.journal_occupancy(store, journal)
    assert (pending_before["main"]["completed"], pending_before["main"]["pending"]) == (0, 1)
    pending_files, pending_inventory = files(plane), store.diagnostics().committed_inventory_sha256
    pending_read = cli("cold-pending", "discovery-show", "--operation-sha256", op1["operation_sha256"])
    assert pending_read["operation_request"]["question_text"] == p1["question_text"]
    assert pending_read["entries"] == [] and pending_read["total_results"] == 0
    assert pending_read["pending_reservations"][0]["operation_sha256"] == op1["operation_sha256"]
    assert pending_read["values_loaded"] is False and pending_read["writes"] == {"research_store": 0}
    assert files(plane) == pending_files and store.diagnostics().committed_inventory_sha256 == pending_inventory
    conflicting = copy.deepcopy(p1)
    conflicting["question_text"] = "CONFLICTING_SUPPORTED_TEXT: hindsight cannot replace P1."
    # The original failed counterpart remains retained if this typed assertion fails.
    try:
        negative = invocation.fault(plane, "pending-changed-text", "observe",
            (*base1, "--operation", input_file("request-conflict", conflicting)), 2)
    finally:
        save(out / "pending-counterpart-after.json", {"operations": ordinary.list_operations(store),
            "reservations": ordinary._iter_kind(store, ordinary.RESERVATION_KIND),
            "looks": list_discovery_looks(store, journal), "occupancy": ordinary.journal_occupancy(store, journal)})
    assert negative["reason_code"] == "ORDINARY_LOOK_PENDING_IN_OTHER_OPERATION"
    assert negative["detail"]["original_operation_sha256"] == op1["operation_sha256"]
    assert negative["detail"]["original_reservation_ref"] == pending_read["pending_reservations"][0]["record_id"]
    assert negative["detail"]["next_action"] == "RESUME_ORIGINAL_OPERATION"
    assert negative["values_loaded"] is False
    assert negative["_native_trace"]["loader_calls"] == negative["_native_trace"]["evaluator_calls"] == 0
    assert ordinary.journal_occupancy(store, journal) == pending_before
    assert not list_discovery_looks(store, journal)

    lost = invocation.fault(plane, "result-ack-lost", "result", (*base1, "--operation-sha256", op1["operation_sha256"]), 75)
    assert lost["loader_calls"] >= 1 and lost["evaluator_calls"] == 1
    r1 = cli("original-ack-recovery", *base1, "--operation-sha256", op1["operation_sha256"])
    assert r1["values_loaded"] is False and r1["replayed_without_evaluator"] is True
    assert r1["result_refs"] == lost["native_boundary"]["result_refs"]
    assert r1["result_sha256"] == lost["native_boundary"]["result_sha256"]
    assert r1["operation_sha256"] == op1["operation_sha256"]
    assert ordinary.get_operation(store, op1["operation_sha256"])["question_text"] == p1["question_text"]
    matched = r1["result"]["research_scope"]["matched"]
    assert (matched["n"], matched["target_observed_n"], matched["target_missing_n"]) == (4, 3, 1)
    assert math.isclose(matched["mean_target"], .1, abs_tol=1e-9)
    assert math.isclose(r1["result"]["research_scope"]["contrast"]["observed_target_difference"], .2, abs_tol=1e-9)

    before_landed = ordinary.journal_occupancy(store, journal)
    landed = invocation.fault(plane, "landed-changed-text", "observe",
        (*base1, "--operation", input_file("request-conflict", conflicting)), 0)
    assert landed["values_loaded"] is False and landed["replayed_without_evaluator"] is True
    assert landed["_native_trace"]["loader_calls"] == landed["_native_trace"]["evaluator_calls"] == 0
    assert landed["result_refs"] == r1["result_refs"] and landed["result_sha256"] == r1["result_sha256"]
    assert ordinary.journal_occupancy(store, journal) == before_landed
    # Native result source is authoritative even if the attempted request is new.
    assert landed["result_operation_sha256"] == op1["operation_sha256"], "LANDED_REPLAY_RETARGETED_TO_CONFLICTING_REQUEST"
    assert landed["question_text"] == p1["question_text"]
    assert landed["operation_sha256"] != op1["operation_sha256"]

    q2 = cli("resolve-t2", "research-scope-resolve", "--spec", input_file("draft-t2",
        draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["B"]}]})))["canonical_query"]
    q2["adaptation_of"] = validate_temporal_query(q1)["spec_sha256"]
    assert validate_temporal_query(q2)["spec_sha256"] != validate_temporal_query(q1)["spec_sha256"]
    p2 = _operation(q2, focus=focus, journal=journal, market=market, text=p1["owner_request_text"],
        cap={"main": 0, "adaptive": 1, "preview": 0})
    prior_look = next(look for look in list_discovery_looks(store, journal) if look["record_id"] == r1["result_refs"][0])
    p2["question_text"] = authored_plan(PLAN_TWO, q2, context, prior_look=prior_look)
    p2["parent_operation_sha256"] = op1["operation_sha256"]
    r2 = invocation.fault(plane, "adaptive-result", "observe", ("discovery-execute", "--store", str(plane),
        "--spec", input_file("query-t2", q2), "--candidate-scope", scopefile, "--journal-scope", journal,
        "--operation", input_file("request-p2", p2), "--format", "json"), 0)
    trace2 = r2["_native_trace"]
    assert trace2["trace"][0] == "DURABLE_RESERVATION_BEFORE_VALUES"
    assert trace2["pre_value_boundary"]["operation"]["question_text"] == p2["question_text"]
    assert trace2["evaluator_calls"] == 1
    looks = list_discovery_looks(store, journal)
    assert len(looks) == 2
    look1, look2 = [next(r for r in looks if r["record_id"] == result["result_refs"][0]) for result in (r1, r2)]
    op2 = ordinary.get_operation(store, look2["operation_sha256"])
    assert op2["parent_operation_sha256"] == op1["operation_sha256"]
    assert op2["question_text"] == p2["question_text"]
    assert look1["look_class"] == "MAIN" and look2["look_class"] == "ADAPTIVE"
    assert ordinary.accounting_root_of(store, journal) == journal
    occupancy = ordinary.journal_occupancy(store, journal)
    assert (occupancy["main"]["completed"], occupancy["adaptive"]["completed"], occupancy["preview"]["occupied"]) == (1, 1, 0)
    assert occupancy["main"]["pending"] == occupancy["adaptive"]["pending"] == 0
    matched2 = r2["result"]["research_scope"]["matched"]
    assert (matched2["n"], matched2["target_observed_n"], matched2["target_missing_n"]) == (4, 3, 1)
    assert math.isclose(matched2["mean_target"], -.2, abs_tol=1e-9)
    assert math.isclose(r2["result"]["research_scope"]["contrast"]["observed_target_difference"], -.325, abs_tol=1e-9)
    dispositions = []
    for index, look in enumerate((look1, look2), 1):
        packet = {"subject": {"subject_kind": "QUESTION", "market_evidence_epoch_sha256": market,
            "owner_focus": focus, "journal_scope": journal, "question_spec_sha256": look["spec_sha256"],
            "question_text": "Fixed synthetic list contrast " + str(index)},
            "basis": {"result_refs": [{"result_ref": look["record_id"], "result_sha256": look["result_sha256"],
                "calculation_version": look["calculation_version"]}], "saved_results_read": True,
                "values_loaded": False, "scientific_look_delta": 0},
            "judgement": {"verdict": "INSUFFICIENT_EVIDENCE", "recommendation": "REVIEW_BOUNDED_SCOPE",
                "source_wording": "Synthetic descriptive evidence only.",
                "rationale": ("P1 PASS as a descriptive contrast: A mean .10 versus complement -.10. One missing target and dependent synthetic templates leave economic/scientific transfer NOT_ESTABLISHED; B can only be an exposed separately bound adaptive clarification. No family close or new allowance."
                    if index == 1 else "P2 FAIL for B_POSITIVE: B mean -.20 versus complement .125, contrast -.325. Do not transfer A's positive contrast to B; keep each bound result. Missingness/dependent synthetic templates leave wider scientific conclusions NOT_ESTABLISHED. No family ban, reopen or further allowance."),
                "caveats": ["price relative proxy is not NetReturn", "No family close or new look authority"]},
            "provenance": {"author_role": "MODEL", "source_episode": "FORGE-DECISION-LINK-MULTI",
                "source_refs": ["tests/fixtures/forge_decision_link_v1/multi_look_probe.py"]}}
        dispositions.append(cli(f"assessment-{index}", "disposition-record", "--input", input_file(f"assessment-input-{index}", packet), "--format", "json"))
    save(out / "persisted-links.json", {"operations": [ordinary.get_operation(store, look["operation_sha256"]) for look in (look1, look2)],
        "looks": [look1, look2], "reservations": ordinary._iter_kind(store, ordinary.RESERVATION_KIND),
        "dispositions": dispositions, "occupancy": occupancy})
    return cold_consumer(plane, store, cli, invocation, journal=journal, focus=focus, look1=look1, look2=look2,
        op1=op1, op2=op2, q1=q1, q2=q2, plan1=p1["question_text"], plan2=p2["question_text"], occupancy=occupancy)


def race_campaign(out, invocation, store, plane, cli, input_file):
    """Native precommit race, separate from the MAIN/ADAPTIVE proof campaign."""
    from tests.test_hfic_list_aware_vertical_v1 import draft
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
    from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label, validate_temporal_query
    save(out / "campaign.json", {"synthetic_only": True, "purpose": "V07_TWO_AUTHOR_PRECOMMIT_RACE",
        "main": 1, "adaptive": 0, "preview": 0, "actors": 2,
        "unrelated_append": "NATIVE_METADATA_OPERATION_WITH_ZERO_ALLOWANCE",
        "continuity_claim": "NONE; the parent/ADAPTIVE proof is a separate campaign"})
    query = cli("race-resolve", "research-scope-resolve", "--spec", input_file("race-draft",
        draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]})))["canonical_query"]
    pre = cli("race-preflight", "preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES",
        "--owner-focus", FOCUS + "_RACE", "--format", "json")
    journal, market, focus = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"], pre["owner_focus"]
    scope = {"estimand": "price_relative_proxy", "explanatory_condition": "LIST_CONTRAST",
        "population": "OPPORTUNITY_EPISODES", "decision_timestamp": "E1800", "target": temporal_target_label(query)}
    query_path, scope_path = input_file("race-query", query), input_file("race-scope", scope)
    original = _operation(query, focus=focus, journal=journal, market=market,
        text="One fixed synthetic MAIN allowance contested by two authored immutable requests.",
        cap={"main": 1, "adaptive": 0, "preview": 0})
    actor_a, actor_b = copy.deepcopy(original), copy.deepcopy(original)
    actor_a["question_text"] = PLAN_ONE + " RACE_AUTHOR=A"
    actor_b["question_text"] = PLAN_ONE + " RACE_AUTHOR=B; cannot replace A's occupied request."
    base = ("discovery-execute", "--store", str(plane), "--spec", query_path, "--candidate-scope", scope_path,
        "--journal-scope", journal, "--format", "json")
    actors = [("race-author-a", (*base, "--operation", input_file("race-request-a", actor_a))),
              ("race-author-b", (*base, "--operation", input_file("race-request-b", actor_b)))]
    def unrelated_append():
        before = store.diagnostics().committed_inventory_sha256
        request = _operation(query, focus=focus, journal=journal, market=market,
            text="Unrelated metadata append during the native writer race; grants no science allowance.",
            cap={"main": 0, "adaptive": 0, "preview": 0})
        request["question_text"] = "UNRELATED_METADATA_ONLY; no test requested or values loaded."
        operation = ordinary.record_operation(store, request)
        after = store.diagnostics().committed_inventory_sha256
        assert before != after
        assert not [row for row in ordinary._iter_kind(store, ordinary.RESERVATION_KIND) if row["journal_scope"] == journal]
        save(out / "race-unrelated-append.json", {"request": request, "operation": operation,
            "before_inventory_sha256": before, "after_inventory_sha256": after,
            "reservation_delta": 0, "values_loaded": False})
    answers = invocation.race(plane, actors, unrelated_append=unrelated_append)
    assert sorted(answer["_exit_code"] for answer in answers) == [2, 74]
    winner = next(answer for answer in answers if answer["_exit_code"] == 74)
    loser = next(answer for answer in answers if answer["_exit_code"] == 2)
    for answer in answers:
        assert answer["_native_trace"]["loader_calls"] == answer["_native_trace"]["evaluator_calls"] == 0
    operation = winner["native_boundary"]["operation"]
    reservations = [row for row in ordinary._iter_kind(store, ordinary.RESERVATION_KIND) if row["journal_scope"] == journal]
    assert len(reservations) == 1 and reservations[0]["operation_sha256"] == operation["operation_sha256"]
    assert reservations[0]["spec_sha256"] == validate_temporal_query(query)["spec_sha256"]
    assert loser["reason_code"] == "ORDINARY_LOOK_PENDING_IN_OTHER_OPERATION"
    assert loser["values_loaded"] is False and loser["detail"]["next_action"] == "RESUME_ORIGINAL_OPERATION"
    assert loser["detail"]["original_operation_sha256"] == operation["operation_sha256"]
    assert loser["detail"]["original_reservation_ref"] == reservations[0]["record_id"]
    assert not list_discovery_looks(store, journal)
    occupancy = ordinary.journal_occupancy(store, journal)
    assert (occupancy["main"]["pending"], occupancy["main"]["completed"]) == (1, 0)
    assert occupancy["adaptive"]["occupied"] == occupancy["preview"]["occupied"] == 0
    before, inventory = files(plane), store.diagnostics().committed_inventory_sha256
    save(out / "race-cold-store-before.json", {"file_sha256": before, "committed_inventory_sha256": inventory})
    cold = cli("race-cold-original", "discovery-show", "--operation-sha256", operation["operation_sha256"])
    assert cold["operation_request"]["question_text"] == operation["question_text"]
    assert cold["entries"] == [] and cold["pending_reservations"][0]["record_id"] == reservations[0]["record_id"]
    assert cold["values_loaded"] is False and cold["writes"] == {"research_store": 0}
    after_files, after_inventory = files(plane), store.diagnostics().committed_inventory_sha256
    save(out / "race-cold-store-after.json", {"file_sha256": after_files, "committed_inventory_sha256": after_inventory})
    assert after_files == before and after_inventory == inventory
    save(out / "race-persisted-links.json", {"operations": ordinary.list_operations(store),
        "reservations": reservations, "occupancy": occupancy, "winner_operation_sha256": operation["operation_sha256"]})
    return {"status": "NATIVE_TWO_AUTHOR_RACE_VERIFIED", "gap": "REPAIRED_PRECOMMIT_PENDING_GUARD",
        "journal_scope": journal, "operation_sha256": operation["operation_sha256"],
        "reservation_ref": reservations[0]["record_id"], "occupancy": occupancy,
        "checks": {"both_outer_gates_before_reserve": "PASS", "unrelated_native_append": "PASS",
            "single_durable_reservation": "PASS", "typed_loser_original_locator": "PASS",
            "zero_loader_and_evaluator": "PASS", "cold_pending_zero_write": "PASS"},
        "technical_continuity": "VERIFIED_IN_SYNTHETIC_RACE_SCOPE", "choice_quality": "UNVERIFIED",
        "live_use": "NOT_EXECUTED", "market_alpha_oos_economics": "NOT_EVALUATED"}


def cold_consumer(plane, store, cli, invocation, *, journal, focus, look1, look2, op1, op2, q1, q2, plan1, plan2, occupancy):
    from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary
    from solana_alpha_lab.factory.hfic_temporal_discovery import canonical_temporal_spec, validate_temporal_query
    from solana_alpha_lab.factory.run_passport import canonical_sha256
    before = files(plane)
    inventory = store.diagnostics().committed_inventory_sha256
    save(invocation.out / "cold-store-before.json", {"file_sha256": before, "committed_inventory_sha256": inventory})
    detail = cli("cold-dispositions", "disposition-show", "--owner-focus", focus, "--journal-scope", journal, "--format", "json")
    assert len(detail["entries"]) == 2
    cold_entries = []
    for index, (look, plan, original_query) in enumerate(((look1, plan1, q1), (look2, plan2, q2)), 1):
        cold = cli(f"cold-result-{index}", "discovery-show", "--result-ref", look["record_id"])
        assert cold["values_loaded"] is False and cold["writes"] == {"research_store": 0}
        assert len(cold["entries"]) == 1
        entry = cold["entries"][0]
        cold_entries.append(entry)
        assert entry["operation_request"]["question_text"] == plan
        basis_refs = json.loads(plan.split(" BASIS_REFS=", 1)[1])
        assert basis_refs["canonical_temporal_spec_sha256"] == canonical_sha256(canonical_temporal_spec(entry["canonical_query"]))
        assert basis_refs["scientific_spec_sha256"] == entry["spec_sha256"]
        assert basis_refs["journal_scope"] == journal and basis_refs["owner_focus"] == focus
        assert entry["operation_sha256"] == look["operation_sha256"]
        assert entry["result_ref"] == look["record_id"] and entry["result_sha256"] == look["result_sha256"]
        assert entry["reservation_ref"] == next(r["record_id"] for r in ordinary._iter_kind(store, ordinary.RESERVATION_KIND)
            if r["operation_sha256"] == look["operation_sha256"] and r["spec_sha256"] == look["spec_sha256"])
        assert validate_temporal_query(entry["canonical_query"]) == validate_temporal_query(original_query)
        assert entry["result_readout"]["result_coherence"] == "COHERENT"
        assert entry["scientific_disposition"]["status"] == "CURRENT_FOR_BOUND_BASIS"
        assert entry["scientific_disposition"]["result_refs"] == [look["record_id"]]
        assert entry["assessment_history"][0]["body"]["basis"]["operation_sha256"] == look["operation_sha256"]
        assert entry["query_provenance"] == ("EXACT_SAVED_PUBLIC_QUERY" if index == 1 else "SOURCE_DERIVED_CANONICAL_QUERY")
        if index == 2:
            assert entry["parent_operation"]["operation_sha256"] == op1["operation_sha256"]
            assert entry["canonical_query"]["adaptation_of"] == look1["spec_sha256"]
            assert basis_refs["authorship_state"] == "POST_R1_EXPOSED_PRE_T2_VALUES"
            assert basis_refs["prior_result"]["result_ref"] == look1["record_id"]
            assert basis_refs["prior_result"]["result_sha256"] == look1["result_sha256"]
            assert basis_refs["prior_result"]["prior_spec_sha256"] == look1["spec_sha256"]
        addressed = cli(f"cold-operation-{index}", "discovery-show", "--operation-sha256", look["operation_sha256"])
        assert addressed["entries"] == cold["entries"] and addressed["pending_reservations"] == []
    rollback = invocation.fault(plane, "cold-baseline-script-rollback", "rollback",
        ("disposition-show", "--owner-focus", focus, "--journal-scope", journal, "--format", "json"), 0)
    assert rollback["_native_trace"]["loader_calls"] == rollback["_native_trace"]["evaluator_calls"] == 0
    assert {key: value for key, value in rollback.items() if key != "_native_trace"} == detail
    after_files, after_inventory = files(plane), store.diagnostics().committed_inventory_sha256
    save(invocation.out / "cold-store-after.json", {"file_sha256": after_files, "committed_inventory_sha256": after_inventory})
    assert after_files == before and after_inventory == inventory
    return {"status": "NATIVE_PARENT_CONTINUATION_VERIFIED", "gap": "REPAIRED_NATIVE_PENDING_AND_PUBLIC_READ",
        "journal_scope": journal, "accounting_root": journal, "operation_sha256": [op1["operation_sha256"], op2["operation_sha256"]],
        "result_refs": [look1["record_id"], look2["record_id"]], "occupancy": occupancy,
        "consumer_issue": "NONE_IN_TESTED_PER_TEST_SOURCE_QUERY_AND_ASSESSMENT_SCOPE",
        "checks": {"pending_conflict": "PASS", "result_ack_recovery": "PASS", "landed_original_source": "PASS",
            "per_test_pre_value_plan": "PASS", "common_accounting_lineage": "PASS", "two_literal_oracles": "PASS",
            "cold_read_zero_write": "PASS", "public_cold_per_test_recovery": "PASS",
            "frozen_script_legacy_disposition_read": "PASS", "frozen_context_and_query_refs": "PASS"},
        "technical_continuity": "VERIFIED_IN_SYNTHETIC_SCOPE", "choice_quality": "UNVERIFIED",
        "live_use": "NOT_EXECUTED", "market_alpha_oos_economics": "NOT_EVALUATED"}


class RetainedVerificationError(Exception):
    pass


def verify_retained(out: Path) -> dict:
    """Narrow b06 retained-proof audit; never invokes a product or store API."""
    def require(condition, code):
        if not condition:
            raise RetainedVerificationError(code)
    def artifact(relative):
        path = (out / relative).resolve()
        require(path.is_relative_to(out) and path.is_file(), "RETAINED_ARTIFACT_MISSING_OR_UNSAFE")
        return path
    def body(relative):
        try:
            return json.loads(artifact(relative).read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise RetainedVerificationError("RETAINED_ARTIFACT_JSON_INVALID") from None
    require((out / "terminal.json").is_file(), "RETAINED_TERMINAL_MISSING")
    terminal = body("terminal.json")
    require(terminal.get("status") == "NATIVE_PARENT_CONTINUATION_VERIFIED", "RETAINED_TERMINAL_NOT_VERIFIED")
    require(bool(terminal["artifacts"]), "RETAINED_ARTIFACT_MANIFEST_EMPTY")
    for relative, digest in terminal["artifacts"].items():
        require(hashlib.sha256(artifact(relative).read_bytes()).hexdigest() == digest,
            "RETAINED_ARTIFACT_HASH_MISMATCH")
    invocation = f"invocations/{terminal['resource']['invocation_count']:04d}"
    require(body(invocation + "/start.json")["source_sha256"] == terminal["source_sha256"],
        "RETAINED_SOURCE_PIN_MISMATCH")
    for relative, digest in terminal["source_sha256"].items():
        require(hashlib.sha256(artifact(invocation + "/source-inputs/" + relative + ".txt").read_bytes()).hexdigest() == digest,
            "RETAINED_SOURCE_SNAPSHOT_HASH_MISMATCH")
    require(all(value == "PASS" for value in terminal["checks"].values()), "RETAINED_CHECK_NOT_PASS")
    before, after = body("cold-store-before.json"), body("cold-store-after.json")
    require(before == after, "RETAINED_COLD_STORE_SNAPSHOT_MISMATCH")
    plane = out / "fixture/plane"
    require(files(plane) == after["file_sha256"], "RETAINED_NATIVE_STORE_FILE_HASH_MISMATCH")
    native = body("persisted-links.json")
    require(native["occupancy"] == terminal["occupancy"], "RETAINED_ACCOUNTING_LINK_MISMATCH")
    require(terminal["journal_scope"] == terminal["accounting_root"], "RETAINED_ACCOUNTING_ROOT_MISMATCH")
    require(len(terminal["result_refs"]) == len(terminal["operation_sha256"]) == 2, "RETAINED_TEST_COUNT_MISMATCH")
    for index in (1, 2):
        entry = body(f"cold-result-{index}.json")["entries"][0]
        look, operation = native["looks"][index - 1], native["operations"][index - 1]
        request = body(f"request-p{index}.json")
        require(entry["result_ref"] == look["record_id"] == terminal["result_refs"][index - 1]
            and entry["result_sha256"] == look["result_sha256"], "RETAINED_RESULT_LINK_MISMATCH")
        require(entry["operation_sha256"] == look["operation_sha256"] == operation["operation_sha256"]
            == terminal["operation_sha256"][index - 1], "RETAINED_OPERATION_LINK_MISMATCH")
        require(entry["operation_request"]["question_text"] == operation["question_text"] == request["question_text"],
            "RETAINED_AUTHORED_PLAN_LINK_MISMATCH")
        require(entry["spec_sha256"] == look["spec_sha256"], "RETAINED_SPEC_LINK_MISMATCH")
        reservations = [row for row in native["reservations"] if row["operation_sha256"] == operation["operation_sha256"]
            and row["spec_sha256"] == look["spec_sha256"]]
        require(len(reservations) == 1 and entry["reservation_ref"] == reservations[0]["record_id"],
            "RETAINED_RESERVATION_LINK_MISMATCH")
        require(entry["scientific_disposition"]["status"] == "CURRENT_FOR_BOUND_BASIS"
            and entry["scientific_disposition"]["result_refs"] == [look["record_id"]],
            "RETAINED_ASSESSMENT_LINK_MISMATCH")
        require(body(f"cold-operation-{index}.json")["entries"] == [entry], "RETAINED_PUBLIC_LOCATOR_LINK_MISMATCH")
    require(native["operations"][1]["parent_operation_sha256"] == native["operations"][0]["operation_sha256"],
        "RETAINED_PARENT_LINEAGE_MISMATCH")
    rollback = body("cold-baseline-script-rollback.json")
    require({key: value for key, value in rollback.items() if key != "_native_trace"} == body("cold-dispositions.json"),
        "RETAINED_ROLLBACK_READ_MISMATCH")
    require(rollback["_native_trace"]["loader_calls"] == rollback["_native_trace"]["evaluator_calls"] == 0,
        "RETAINED_ROLLBACK_VALUE_READ")
    return {"status": "RETAINED_NATIVE_PROOF_INTEGRITY_VERIFIED",
        "terminal_sha256": hashlib.sha256(artifact("terminal.json").read_bytes()).hexdigest(),
        "artifact_count": len(terminal["artifacts"]), "source_snapshot_count": len(terminal["source_sha256"]),
        "native_file_count": len(after["file_sha256"]), "committed_inventory_sha256": after["committed_inventory_sha256"],
        "result_refs": terminal["result_refs"], "values_loaded": False, "writes": {"research_store": 0},
        "verifier_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "RETAINED_B06_MANIFEST_SOURCE_LINKS_AND_FILE_SNAPSHOTS; no new scientific verdict"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture-source", type=Path, help="Reuse an already native-produced synthetic fixture into a new owned campaign")
    parser.add_argument("--cold-only", action="store_true", help="Read an existing native attempt; no setup, writers or value rerun")
    parser.add_argument("--race-only", action="store_true", help="Separate native two-author precommit race; no values are reached")
    parser.add_argument("--fault-child", choices=("reservation", "result", "observe", "race", "rollback"))
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--barrier", type=Path)
    parser.add_argument("--verify-retained", type=Path,
        help="Read-only integrity audit of an existing owned native parent-continuation proof; no product/store APIs")
    parser.add_argument("product_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.verify_retained:
        out = args.verify_retained.resolve()
        owned = (ROOT / "local/forge_decision_link_v1").resolve()
        if not out.is_relative_to(owned) or out == owned or args.output or args.fault_child or args.cold_only or args.race_only:
            parser.error("OWNED_RETAINED_PROOF_REQUIRED")
        try:
            result = verify_retained(out)
        except (RetainedVerificationError, KeyError, TypeError, OSError) as stopped:
            code = str(stopped) if isinstance(stopped, RetainedVerificationError) else "RETAINED_PROOF_STRUCTURE_INVALID"
            print(json.dumps({"status": "INVALID", "reason_code": code}))
            return 2
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.fault_child:
        if args.trace is None:
            parser.error("FAULT_TRACE_REQUIRED")
        product = args.product_argv[1:] if args.product_argv[:1] == ["--"] else args.product_argv
        return fault_child(args.fault_child, args.trace, product, args.barrier)
    if args.race_only and args.cold_only:
        parser.error("RACE_REQUIRES_NEW_CAMPAIGN")
    if args.output is None:
        parser.error("OUTPUT_REQUIRED")
    out, owned = args.output.resolve(), (ROOT / "local/forge_decision_link_v1").resolve()
    if not out.is_relative_to(owned) or out == owned or (out.exists() != args.cold_only):
        parser.error("NEW_OWNED_ATTEMPT_REQUIRED")
    if not args.cold_only:
        out.mkdir(parents=True)
        save(out / "terminal.json", {"status": "INCOMPLETE", "stage": "MULTI_LOOK"})
    invocation = ProbeInvocation(out, args.cold_only)
    def artifacts():
        return {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.rglob("*")) if p.is_file() and p != out / "terminal.json" and not p.is_relative_to(out / "fixture")}
    try:
        result = execute(out, invocation, args)
        assert invocation.sources == {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in invocation.sources}, "SOURCE_CHANGED_DURING_INVOCATION"
        invocation.finish("COMPLETE")
    except Exception as exc:
        invocation.finish("HARNESS_ERROR")
        save(out / "terminal.json", {"status": "HARNESS_ERROR", "stage": "MULTI_LOOK",
            "error_type": type(exc).__name__, "error_code": str(exc) if isinstance(exc, AssertionError) else "UNKNOWN",
            "invocation": invocation.path.relative_to(out).as_posix(), "source_sha256": invocation.sources,
            "artifacts": artifacts()})
        print(json.dumps({"status": "HARNESS_ERROR", "error_type": type(exc).__name__}))
        raise
    history = invocation.history()
    result.update({"source_sha256": invocation.sources, "resource": {"measured_subprocess_wall_seconds":
        sum(item["measured_subprocess_wall_seconds"] for item in history),
        "elapsed_window_seconds": (datetime.fromisoformat(utc_now()) - datetime.fromisoformat(history[0]["started_at"])).total_seconds(),
        "invocation_count": len(history), "cold_only_this_invocation": args.cold_only,
        "preparation_outside_helper_seconds": "UNKNOWN", "cpu_ram_peak": "UNKNOWN", "model_calls": 0,
        "watchdog_seconds": 180, "owned_output_guard_bytes": 1024 ** 3},
        "artifacts": artifacts()})
    save(out / "terminal.json", result)
    print(json.dumps({k: result[k] for k in ("status", "gap", "checks", "resource")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
