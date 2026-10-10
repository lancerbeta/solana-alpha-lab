"""S0 characterization of existing decision transport using synthetic producers.

This is not patch qualification. All product commands run in fresh processes.
No link is injected into ResearchStore and no scientific Critic is simulated.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
BASE = "76993054cfaeeee7e9fb6e7b718add8cf27e404a"
FOCUS = "FORGE_DECISION_LINK_S0_SYNTHETIC"
MARKER = "S0_AUTHORED_PRETEST_PLAN_DISTINCT_MARKER"
HELPER_VERSION = "2.1"
SOURCE_PATHS = ["scripts/hypothesis_forge.py", "src/solana_alpha_lab/factory/hfic_ordinary_operation.py",
                "src/solana_alpha_lab/factory/hfic_grounded_discovery.py", "src/solana_alpha_lab/factory/hfic_scientific_disposition.py",
                "src/solana_alpha_lab/factory/hfic_generation_context.py", "tests/test_forge_research_flow_reliability_v1.py",
                "tests/test_hfic_list_aware_vertical_v1.py", "tests/test_hfic_ordinary_operation_acceptance_v1.py",
                "tests/fixtures/forge_decision_link_v1/entry_probe.py",
                "tests/fixtures/forge_decision_link_v1/verify_terminal.py"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_hashes() -> dict[str, str]:
    return {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in SOURCE_PATHS}


def save(path: Path, body: object, *, archive_previous: bool = True) -> str:
    content = (json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if archive_previous and path.exists() and path.read_bytes() != content:
        previous = path.read_bytes()
        history = path.parent / "output-history"
        history.mkdir(exist_ok=True)
        archived = history / f"{path.stem}-{hashlib.sha256(previous).hexdigest()}.json"
        if not archived.exists():
            archived.write_bytes(previous)
    path.write_bytes(content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class Invocation:
    """A new directory per invocation; prior commands and terminals stay intact."""

    def __init__(self, out: Path, resume: bool, expected_head: str) -> None:
        self.out, self.started, self.started_at = out, time.monotonic(), utc_now()
        invocations = out / "invocations"
        invocations.mkdir(exist_ok=True)
        self.path = invocations / f"{len(list(invocations.iterdir())) + 1:04d}"
        self.path.mkdir()  # Never reuse/overwrite another invocation.
        self.commands: list[dict] = []
        self.sources = source_hashes()
        self.finished = False
        save(self.path / "start.json", {"started_at": self.started_at, "resume_cold": resume,
             "argv": ["<PYTHON>", "-B", "tests/fixtures/forge_decision_link_v1/entry_probe.py",
                      "--output", out.relative_to(ROOT).as_posix(), *(["--resume-cold"] if resume else []),
                      *(["--expected-head", expected_head] if "--expected-head" in sys.argv else [])],
             "python_version": sys.version, "helper_version": HELPER_VERSION, "expected_head": expected_head,
             "source_sha256": self.sources})
        for relative in self.sources:
            target = self.path / "source-inputs" / (relative + ".txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        terminal = out / "terminal.json"
        if terminal.exists():
            (self.path / "prior-terminal.json").write_bytes(terminal.read_bytes())

    def normalize(self, value: object) -> str:
        return str(value).replace(str(self.out), "<ATTEMPT>").replace(str(ROOT), "<REPOSITORY>")

    def disk_guard(self) -> int:
        retained = sum(p.stat().st_size for p in self.out.rglob("*") if p.is_file())
        if retained > 1024 ** 3:
            raise AssertionError("OWNED_OUTPUT_DISK_GUARD")
        return retained

    def cli(self, plane: Path, name: str, argv: tuple[str, ...], expected: int) -> dict:
        self.disk_guard()
        command_dir = self.path / f"{len(self.commands) + 1:03d}-{name}"
        command_dir.mkdir()
        input_refs = {}
        for value in argv:
            candidate = Path(str(value))
            if candidate.is_file() and candidate.is_relative_to(self.out):
                relative = candidate.relative_to(self.out).as_posix()
                retained = command_dir / "inputs" / relative
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_bytes(candidate.read_bytes())
                input_refs[relative] = hashlib.sha256(retained.read_bytes()).hexdigest()
        command = [sys.executable, "-B", str(ROOT / "scripts/hypothesis_forge.py"),
                   "--root", str(ROOT), "--data-root", str(plane), *argv]
        safe_command = ["<PYTHON>", *[self.normalize(v) for v in command[1:]]]
        save(command_dir / "request.json", {"name": name, "argv": safe_command, "cwd": "<REPOSITORY>",
             "input_sha256": input_refs, "expected_exit_code": expected, "watchdog_seconds": 180})
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "SMIAL_DATA_ROOT": str(plane)}
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        command_started, started_at = time.monotonic(), utc_now()
        timed_out = False
        try:
            done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
            code, stdout, stderr = done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
        elapsed = time.monotonic() - command_started
        (command_dir / "stdout.txt").write_bytes(stdout)
        (command_dir / "stderr.txt").write_bytes(stderr)
        entry = {"artifact": name + ".json", "argv": safe_command, "exit_code": code,
                 "started_at": started_at, "completed_at": utc_now(), "subprocess_wall_seconds": elapsed,
                 "timed_out": timed_out, "command_directory": command_dir.relative_to(self.out).as_posix(),
                 "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
        save(command_dir / "command.json", entry)
        self.commands.append(entry)
        self.disk_guard()
        if timed_out:
            raise AssertionError(f"PUBLIC_STAGE_WATCHDOG:{name}")
        try:
            body = json.loads(stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AssertionError(f"PUBLIC_STAGE_NON_JSON:{name}:{code}") from None
        save(self.out / (name + ".json"), body)
        if code != expected:
            raise AssertionError(f"PUBLIC_STAGE_EXIT:{name}:{code}")
        return body

    def finish(self, status: str) -> None:
        if not self.finished:
            save(self.path / "summary.json", {"status": status, "started_at": self.started_at,
                 "completed_at": utc_now(), "invocation_wall_seconds": time.monotonic() - self.started,
                 "invocation_wall_window": "entry through summary finalization; terminal serialization excluded",
                 "measured_subprocess_wall_seconds": sum(c["subprocess_wall_seconds"] for c in self.commands),
                 "preparation_outside_helper_seconds": "UNKNOWN", "cpu_ram_peak": "UNKNOWN", "model_calls": 0,
                 "commands": self.commands})
            self.finished = True

    def history(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.out / "invocations").glob("*/summary.json"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-cold", action="store_true", help="Read the existing attempt after a cold-command repair; no fixture or writer rerun")
    parser.add_argument("--expected-head", default=BASE, help="Exact 40-hex candidate HEAD; default is the original baseline")
    args = parser.parse_args()
    out = args.output.resolve()
    owned = (ROOT / "local" / "forge_decision_link_v1").resolve()
    if not out.is_relative_to(owned) or out == owned or (out.exists() != args.resume_cold):
        parser.error("NEW_OWNED_ATTEMPT_REQUIRED")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_head) or head != args.expected_head:
        parser.error("EXACT_EXPECTED_HEAD_REQUIRED")
    if not args.resume_cold:
        out.mkdir(parents=True)
        save(out / "terminal.json", {"status": "INCOMPLETE", "stage": "S0_SETUP"})
    elif not (out / "invocations").is_dir():
        parser.error("RETAINED_INVOCATION_HISTORY_REQUIRED")
    invocation = Invocation(out, args.resume_cold, args.expected_head)
    try:
        return execute(args, out, head, invocation)
    except Exception as exc:
        invocation.finish("HARNESS_ERROR")
        save(out / "terminal.json", {"task_id": "FORGE_DECISION_LINK_V1", "status": "HARNESS_ERROR",
             "stage": "S0", "error_type": type(exc).__name__, "checks": "INCOMPLETE",
             "invocation": invocation.path.relative_to(out).as_posix()})
        print(json.dumps({"status": "HARNESS_ERROR", "error_type": type(exc).__name__}))
        raise


def execute(args: argparse.Namespace, out: Path, head: str, invocation: Invocation) -> int:
    started = time.monotonic()
    from tests.test_forge_research_flow_reliability_v1 import create_episode_fixture
    from tests.test_hfic_list_aware_vertical_v1 import draft
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label
    from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
    from solana_alpha_lab.factory.hfic_ordinary_operation import RESERVATION_KIND, _iter_kind, list_operations, journal_occupancy, get_operation
    from solana_alpha_lab.factory.research_store import ResearchStore

    if not args.resume_cold:
        create_episode_fixture(out / "fixture")
    plane = out / "fixture" / "plane"
    artifacts: dict[str, str] = {}

    def cli(name: str, *argv: str, expected: int = 0) -> dict:
        if args.resume_cold and name in {"resolve", "preflight-before", "result", "assessment", "unsupported-update", "cold-preflight"}:
            # These are completed before the failed cold status command. Never
            # replay setup/writers, overwrite original output, or repeat values.
            return json.loads((out / (name + ".json")).read_text(encoding="utf-8"))
        return invocation.cli(plane, name, argv, expected)

    def input_file(name: str, body: object) -> str:
        path = out / (name + ".json")
        artifacts[path.name] = save(path, body)
        return str(path)

    query = draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]})
    canonical = cli("resolve", "research-scope-resolve", "--spec", input_file("query", query))["canonical_query"]
    pre = cli("preflight-before", "preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES",
              "--owner-focus", FOCUS, "--format", "json")
    journal, market = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"]
    effective_focus = pre["owner_focus"]  # collection routing scopes the stored focus
    scope = {"population": "OPPORTUNITY_EPISODES", "decision_timestamp": "E1800",
             "target": temporal_target_label(canonical), "estimand": "price_relative_proxy",
             "explanatory_condition": canonical["hypothesis_kind"], "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
    request = _operation(canonical, focus=pre["owner_focus"], journal=journal, market=market,
                         text="One supported synthetic list contrast; no market authority.",
                         cap={"main": 1, "adaptive": 0, "preview": 0}, completion="LIMITED_RESULT")
    request["decision_basis"] = {
        "schema_version": "1.0", "decision_question": MARKER,
        "basis_refs": [{"ref": pre["receipt_id"], "sha256": pre["preflight_receipt_sha256"]}],
        "alternatives": [{"id": "A", "prediction": "A membership has a descriptive contrast."},
                         {"id": "B", "prediction": "Missingness or dependency prevents a justified next scientific test."}],
        "test_choices": [{"id": "T1", "query_ref": canonical["query_id"],
                          "discriminator": "The existing fixed A/complement price-relative contrast.",
                          "outcome_actions": [{"outcome": "INSUFFICIENT", "proposed_next": "Keep uncertainty; do not close the family."},
                                              {"outcome": "INFRA_FAILURE", "proposed_next": "Diagnose execution without a market negative."}]}],
        "selected_choice_id": "T1", "choice_reason": "An existing supported discriminator with a fixed fixture oracle.",
        "strongest_rejected_choice_id": None, "rejected_choice_status": "NO_OTHER_ADMISSIBLE_CHOICE",
        "prior_links": [], "authority_granted": False,
    }
    # Strong existing-first control: use a supported public carrier, not only
    # a proposed field. This is a concise outward plan, never hidden reasoning.
    request["question_text"] = "Public pre-test choice: " + json.dumps(request["decision_basis"], ensure_ascii=False, sort_keys=True)
    query_path, scope_path = input_file("canonical", canonical), input_file("scope", scope)
    request_path = input_file("request-authored", request)
    execute_args = ("discovery-execute", "--store", str(plane), "--spec", query_path,
                    "--candidate-scope", scope_path, "--journal-scope", journal, "--format", "json")
    evidence = cli("result", *execute_args, "--operation", request_path)
    actual = evidence["result"]["research_scope"]
    assert (actual["matched"]["n"], actual["matched"]["target_observed_n"], actual["matched"]["target_missing_n"]) == (4, 3, 1)
    assert math.isclose(actual["matched"]["mean_target"], .10, abs_tol=1e-9)
    assert math.isclose(actual["contrast"]["observed_target_difference"], .20, abs_tol=1e-9)
    store = ResearchStore(plane, create_if_missing=False)
    looks = list_discovery_looks(store, journal)
    assert len(looks) == 1 and looks[0]["record_id"] == evidence["result_refs"][0]
    look = looks[0]
    operations, reservations = list_operations(store), _iter_kind(store, RESERVATION_KIND)
    # list_operations returns immutable creation/stamp/transition events,
    # not a deduplicated list of logical operations.
    assert len({item["operation_sha256"] for item in operations}) == len(reservations) == 1
    persisted = {"operations": operations, "reservations": reservations, "looks": looks}
    artifacts["persisted-before-assessment.json"] = save(out / "persisted-before-assessment.json", persisted)
    serialized = json.dumps(persisted)
    assert MARKER in serialized
    assert all("decision_basis" not in item for group in persisted.values() for item in group)
    assert json.loads(operations[0]["question_text"].removeprefix("Public pre-test choice: ")) == request["decision_basis"]
    assert reservations[0]["operation_sha256"] == look["operation_sha256"] == operations[0]["operation_sha256"]
    assert reservations[0]["spec_sha256"] == look["spec_sha256"] == operations[0]["spec_sha256"]
    occupancy_before = journal_occupancy(store, journal)

    packet = {
        "subject": {"subject_kind": "QUESTION", "market_evidence_epoch_sha256": market,
                    "owner_focus": effective_focus, "journal_scope": journal, "question_spec_sha256": look["spec_sha256"],
                    "question_text": "Does the fixed synthetic A/complement contrast justify a scientific conclusion?"},
        "basis": {"result_refs": [{"result_ref": look["record_id"], "result_sha256": look["result_sha256"],
                                   "calculation_version": look["calculation_version"]}],
                  "saved_results_read": True, "values_loaded": False, "scientific_look_delta": 0},
        "judgement": {"verdict": "INSUFFICIENT_EVIDENCE", "recommendation": "REVIEW_BOUNDED_SCOPE",
                      "source_wording": "Synthetic descriptive contrast only.",
                      "rationale": "Compared with the pre-test plan: the descriptive contrast is present, but dependent synthetic templates and a missing target leave the subclaim NOT_ESTABLISHED. Reconsider only after independent admissible evidence under current authority.",
                      "caveats": ["price-relative proxy is not NetReturn", "No family close or fresh look authorized"]},
        "provenance": {"author_role": "MODEL", "source_episode": "FORGE-DECISION-LINK-S0",
                       "source_refs": ["tests/fixtures/forge_decision_link_v1/entry_probe.py"]},
    }
    written = cli("assessment", "disposition-record", "--input", input_file("assessment-input", packet), "--format", "json")
    # This proposed field is characterized separately. It is not an existing API.
    update_packet = copy.deepcopy(packet)
    update_packet["decision_update"] = {"schema_version": "1.0", "surviving_subclaim": "NOT_ESTABLISHED",
                                        "reconsideration_condition": "Independent admissible evidence under current authority.",
                                        "forbidden_inference": "No alpha, close or reopen.", "advice_authority": "AUTHORED_ADVISORY_ONLY"}
    before_refusal = store.diagnostics().committed_inventory_sha256
    refused = cli("unsupported-update", "disposition-record", "--input", input_file("proposed-update-input", update_packet),
                  "--format", "json", expected=2)
    assert refused.get("refusal_code") == "DISPOSITION_PACKET_UNKNOWN_FIELD"
    assert store.diagnostics().committed_inventory_sha256 == before_refusal

    # Preflight is an existing context writer/reissuer. Do not call it read-only
    # or include it inside the zero-write reader envelope.
    next_pre = cli("cold-preflight", "preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES",
                   "--owner-focus", FOCUS, "--format", "json")
    before_reads = files(plane)
    before_read_inventory = store.diagnostics().committed_inventory_sha256
    save(out / "cold-store-before.json", before_reads)
    detail = cli("cold-disposition", "disposition-show", "--owner-focus", effective_focus, "--journal-scope", journal, "--format", "json")
    operation_readout = cli("cold-operation", "research-policy-status", "--for-operation", operations[0]["operation_sha256"])
    changed = copy.deepcopy(request)
    changed["decision_basis"]["decision_question"] = "Changed explanation for the same occupied look."
    replay = cli("changed-story-replay", *execute_args, "--operation", input_file("request-changed", changed))
    assert replay["replayed_without_evaluator"] is True and replay["values_loaded"] is False
    assert replay["result_refs"] == evidence["result_refs"] and replay["result_sha256"] == evidence["result_sha256"]
    for key in ("search_key_sha256", "market_evidence_epoch_sha256"):
        assert pre[key] == next_pre[key]
    original_op = operations[0]
    current_op = get_operation(store, original_op["operation_sha256"])
    for key in ("operation_sha256", "market_evidence_epoch_sha256", "scientific_slot_sha256", "journal_scope", "accounting_root"):
        assert original_op.get(key) == current_op.get(key)
    assert journal_occupancy(store, journal) == occupancy_before
    assert store.diagnostics().committed_inventory_sha256 == before_read_inventory
    after_reads = files(plane)
    assert before_reads == after_reads
    assert len(detail["entries"]) == 1 and detail["entries"][0]["status"] == "CURRENT_FOR_BOUND_BASIS"
    capsule = next_pre["forge_context_packet"]["scientific_disposition_context"]
    assert capsule["advisory_only"] is True and capsule["authority_granted"] is False
    assert len(capsule["entries"]) == 1 and capsule["entries"][0]["result_refs"] == evidence["result_refs"]
    bound = detail["records"][0]["body"]
    assert bound["basis"]["operation_sha256"] == operations[0]["operation_sha256"]
    assert bound["basis"]["result_refs"][0]["result_ref"] == look["record_id"]
    assert "NOT_ESTABLISHED" in bound["judgement"]["rationale"] and "Reconsider only" in bound["judgement"]["rationale"]
    # Policy status is a budget surface, not the plan reader. Reconstruct the
    # accepted inputs from source-owned saved result bytes, never the author's
    # original request file, and address its operation by the native bound ref.
    # look.spec is the normalized scientific body, not public ingress grammar.
    # The existing exact operation owns the original canonical public query.
    cold_spec = input_file("source-derived-query", json.loads(current_op["spec_canonical"]))
    cold_scope = input_file("source-derived-scope", look["candidate_scope"])
    addressed_replay = cli("cold-addressed-result", "discovery-execute", "--store", str(plane),
                          "--spec", cold_spec, "--candidate-scope", cold_scope, "--journal-scope", journal,
                          "--operation-sha256", bound["basis"]["operation_sha256"], "--format", "json")
    assert MARKER in addressed_replay["ordinary_operation_readout"]["question_text"] and MARKER in json.dumps(replay)
    assert addressed_replay["values_loaded"] is False and addressed_replay["replayed_without_evaluator"] is True
    assert addressed_replay["result_refs"] == evidence["result_refs"]
    assert store.diagnostics().committed_inventory_sha256 == before_read_inventory and files(plane) == before_reads
    assert capsule["detail_query"]  # bounded advice points to full exact detail
    save(out / "cold-store-after.json", files(plane))
    native_record_refs = {item["record_id"] for item in operations} | {
        reservations[0]["record_id"], look["record_id"], written["record_id"]}
    source_records = {}
    for record in store.iter_committed_records():
        if record.record_id in native_record_refs:
            source_records[record.record_id] = {
                "payload_sha256": hashlib.sha256(record.payload_json.encode("utf-8")).hexdigest(),
                "stored_payload_sha256": record.payload_sha256,
                "producer_git_sha": record.producer_git_sha,
                "producer_capability_id": record.producer_capability_id,
            }
    assert set(source_records) == native_record_refs
    assert all(v["payload_sha256"] == v["stored_payload_sha256"] for v in source_records.values())
    assert invocation.sources == source_hashes(), "SOURCE_CHANGED_DURING_INVOCATION"
    invocation.finish("COMPLETE")
    invocation_history = invocation.history()
    commands = [c for item in invocation_history for c in item["commands"]]
    # Build this only after every command/history file has its final bytes.
    artifacts = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.rglob("*")) if p.is_file() and p != out / "terminal.json"
                 and not p.is_relative_to(out / "fixture")}
    retained_bytes = invocation.disk_guard()
    first_started = datetime.fromisoformat(invocation_history[0]["started_at"])
    completed_at = utc_now()
    elapsed_window = (datetime.fromisoformat(completed_at) - first_started).total_seconds()
    terminal = {
        "task_id": "FORGE_DECISION_LINK_V1", "status": "ENTRY_EXISTING_PATH_VERIFIED", "stage": "S0",
        "baseline_commit": BASE, "execution_head": head, "gap": "NO_GAP", "gap_scope": "exact single-test ordinary OPPORTUNITY_EPISODES BASE textual carrier",
        "proposed_input_not_existing_api": True, "source_only_packet_field_absence": "decision_update rejected at current public boundary",
        "existing_capability": "question_text plan -> exact operation/spec -> reservation -> native result -> auto-bound disposition -> exact saved-result replay/detail/context",
        "missing_capability": "NOT_ESTABLISHED in the tested exact single-test scope; multi-look per-attempt plan semantics remain untested",
        "result_ref": look["record_id"], "result_sha256": look["result_sha256"],
        "operation_sha256": operations[0]["operation_sha256"], "reservation_ref": reservations[0]["record_id"],
        "assessment_ref": written.get("record_id"), "journal_scope": journal, "market_evidence_epoch_sha256": market,
        "source_records": source_records,
        "store_inventory_sha256": before_read_inventory,
        "store_files_artifact": "cold-store-after.json",
        "oracle": {"matched": 4, "observed": 3, "missing": 1, "mean": .10, "contrast": .20},
        "checks": {"literal_result_oracle": "PASS", "original_result_disposition_join": "PASS",
                   "cold_context_original_advice": "PASS", "supported_textual_plan_persisted_and_cold_readable": "PASS",
                   "native_auto_bound_assessment_to_operation": "PASS", "unsupported_proposed_field_ignored": "CHARACTERIZED_ONLY",
                   "ignored_proposed_field_replay_no_values_no_extra_charge": "PASS", "unsupported_update_zero_writes": "PASS",
                   "cold_file_inventory_unchanged": "PASS", "science_keys_unchanged_by_assessment": "PASS"},
        "fidelity": "SEGMENT_PRODUCT_PATH", "technical_continuity": "NO_MATERIAL_DELTA_IN_TESTED_SCOPE", "choice_quality": "UNVERIFIED",
        "live_use": "NOT_EXECUTED", "market_alpha_oos_economics": "NOT_EVALUATED",
        "scientific_looks": "one synthetic MAIN; no real-market look", "candidate_and_critic": "NOT_EXECUTED",
        "supported_text_edit_identity_and_v05": "NOT_RUN",
        "preflight_is_read_only": False,
        "preflight_observed_writes": next_pre.get("writes"),
        "zero_write_scope": ["disposition-show", "research-policy-status --for-operation (budget only)", "saved discovery-execute replay by native operation ref and source-derived query/scope"],
        "cold_recovery": {"resumed_existing_attempt": args.resume_cold, "fixture_or_writer_rerun": False if args.resume_cold else None},
        "retention_version": HELPER_VERSION, "completed_at": completed_at,
        "helper": {"path": "tests/fixtures/forge_decision_link_v1/entry_probe.py", "version": HELPER_VERSION,
                   "sha256": invocation.sources["tests/fixtures/forge_decision_link_v1/entry_probe.py"]},
        "verifier": {"path": "tests/fixtures/forge_decision_link_v1/verify_terminal.py",
                     "sha256": invocation.sources["tests/fixtures/forge_decision_link_v1/verify_terminal.py"]},
        "resource": {"current_helper_work_seconds_before_terminal": round(time.monotonic() - started, 3),
                     "cumulative_invocation_wall_seconds": sum(i["invocation_wall_seconds"] for i in invocation_history),
                     "cumulative_measured_subprocess_wall_seconds": sum(i["measured_subprocess_wall_seconds"] for i in invocation_history),
                     "elapsed_window_seconds": elapsed_window, "invocation_count": len(invocation_history),
                     "retained_bytes_before_terminal": retained_bytes,
                     "preparation_outside_helper_seconds": "UNKNOWN", "cpu_ram_peak": "UNKNOWN", "model_calls": 0,
                     "watchdog_seconds": 180, "owned_output_guard_bytes": 1024 ** 3},
        "source_sha256": invocation.sources,
        "artifacts": artifacts, "commands": commands,
    }
    # Invocation.prior-terminal already retains the exact previous bytes. Do
    # not create another archive after hashing the final artifact inventory.
    save(out / "terminal.json", terminal, archive_previous=False)
    print(json.dumps({k: terminal[k] for k in ("status", "gap", "checks", "resource")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
