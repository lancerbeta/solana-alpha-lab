"""Fail-closed integrity readback of one owned synthetic entry terminal.

Exit zero means retained bytes and native joins agree. It does not establish
product acceptance, scientific validity, choice quality, or alpha.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))


class InvalidTerminal(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise InvalidTerminal(code)


def load(path: Path) -> dict | list:
    require(path.is_file() and not path.is_symlink(), "MISSING_ARTIFACT")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise InvalidTerminal("UNREADABLE_JSON") from None


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "INVALID_ARTIFACT_PATH")
    path = root / relative
    require(path.resolve().is_relative_to(root) and not Path(relative).is_absolute(), "INVALID_ARTIFACT_PATH")
    require(not path.is_symlink(), "SYMLINK_ARTIFACT")
    return path


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for p in sorted(root.rglob("*")):
        require(not p.is_symlink(), "SYMLINK_ARTIFACT")
        if p.is_file():
            result[p.relative_to(root).as_posix()] = digest(p)
    return result


def body(record: object) -> dict:
    wrapper = json.loads(record.payload_json)
    canonical = wrapper.get("payload_canonical")
    require(isinstance(canonical, str), "NATIVE_PAYLOAD_MISSING")
    require(hashlib.sha256(canonical.encode("utf-8")).hexdigest() == wrapper.get("payload_sha256"),
            "NATIVE_WRAPPER_HASH_MISMATCH")
    payload = json.loads(canonical)
    require(isinstance(payload, dict), "NATIVE_BODY_INVALID")
    payload["__wrapper_artifact_kind__"] = wrapper.get("artifact_kind")
    return payload


def verify(out: Path) -> dict:
    require((out / "terminal.json").is_file(), "MISSING_TERMINAL")
    terminal = load(out / "terminal.json")
    require(isinstance(terminal, dict), "TERMINAL_INVALID")
    require(terminal.get("task_id") == "FORGE_DECISION_LINK_V1"
            and terminal.get("status") == "ENTRY_EXISTING_PATH_VERIFIED"
            and terminal.get("retention_version") == "2.1", "INCOMPLETE_TERMINAL")
    required = {"operation_sha256", "reservation_ref", "result_ref", "result_sha256", "assessment_ref",
                "journal_scope", "market_evidence_epoch_sha256", "source_records", "source_sha256",
                "store_inventory_sha256", "store_files_artifact", "artifacts", "commands", "resource", "checks"}
    required |= {"helper", "verifier", "baseline_commit", "execution_head"}
    require(required <= terminal.keys(), "INCOMPLETE_TERMINAL")
    require(isinstance(terminal["checks"], dict) and bool(terminal["checks"]), "INCOMPLETE_TERMINAL")

    artifacts = terminal["artifacts"]
    require(isinstance(artifacts, dict) and bool(artifacts), "ARTIFACT_MANIFEST_MISSING")
    actual = {rel: sha for rel, sha in inventory(out).items()
              if rel != "terminal.json" and not rel.startswith("fixture/")}
    require(actual == artifacts, "ARTIFACT_HASH_OR_INVENTORY_MISMATCH")
    sources = terminal["source_sha256"]
    require(isinstance(sources, dict) and bool(sources), "SOURCE_FINGERPRINTS_MISSING")
    for rel, sha in sources.items():
        require(digest(child(ROOT, rel)) == sha, "SOURCE_HASH_MISMATCH")
    require(terminal["helper"] == {"path": "tests/fixtures/forge_decision_link_v1/entry_probe.py", "version": "2.1",
                                  "sha256": sources["tests/fixtures/forge_decision_link_v1/entry_probe.py"]}, "HELPER_BINDING_MISMATCH")
    require(terminal["verifier"] == {"path": "tests/fixtures/forge_decision_link_v1/verify_terminal.py",
                                    "sha256": digest(Path(__file__))}, "VERIFIER_BINDING_MISMATCH")

    summaries = [load(p) for p in sorted((out / "invocations").glob("*/summary.json"))]
    require(bool(summaries), "INVOCATION_HISTORY_MISSING")
    require(len(summaries) == len(list((out / "invocations").iterdir())), "INVOCATION_INCOMPLETE")
    starts = [load(p) for p in sorted((out / "invocations").glob("*/start.json"))]
    require(len(starts) == len(summaries) and starts[-1]["source_sha256"] == sources, "SOURCE_INPUT_HISTORY_MISMATCH")
    require(starts[-1]["expected_head"] == terminal["execution_head"], "EXECUTION_HEAD_BINDING_MISMATCH")
    final_source_inputs = out / "invocations" / f"{len(summaries):04d}" / "source-inputs"
    for rel, sha in sources.items():
        require(digest(child(final_source_inputs, rel + ".txt")) == sha, "RETAINED_SOURCE_HASH_MISMATCH")
    commands = [c for summary in summaries for c in summary["commands"]]
    require(commands == terminal["commands"], "COMMAND_HISTORY_MISMATCH")
    for command in commands:
        command_dir = child(out, command["command_directory"])
        require(load(command_dir / "command.json") == command, "COMMAND_ENTRY_MISMATCH")
        require(digest(command_dir / "stdout.txt") == command["stdout_sha256"]
                and digest(command_dir / "stderr.txt") == command["stderr_sha256"], "COMMAND_OUTPUT_HASH_MISMATCH")
        request = load(command_dir / "request.json")
        require(request["argv"] == command["argv"], "COMMAND_ARGV_MISMATCH")
        for rel, sha in request["input_sha256"].items():
            require(digest(child(command_dir / "inputs", rel)) == sha, "ORIGINAL_INPUT_HASH_MISMATCH")
    resource = terminal["resource"]
    require(resource["invocation_count"] == len(summaries), "RESOURCE_HISTORY_MISMATCH")
    require(math.isclose(resource["cumulative_measured_subprocess_wall_seconds"],
                         sum(c["subprocess_wall_seconds"] for c in commands), abs_tol=1e-9), "PROCESS_TIME_MISMATCH")
    require(math.isclose(resource["cumulative_invocation_wall_seconds"],
                         sum(s["invocation_wall_seconds"] for s in summaries), abs_tol=1e-9), "INVOCATION_TIME_MISMATCH")
    require(resource["elapsed_window_seconds"] >= resource["cumulative_measured_subprocess_wall_seconds"],
            "ELAPSED_WINDOW_INVALID")

    plane = out / "fixture" / "plane"
    before = load(out / "cold-store-before.json")
    after = load(child(out, terminal["store_files_artifact"]))
    require(before == after == inventory(plane), "STORE_ARTIFACT_HASH_OR_INVENTORY_MISMATCH")
    from solana_alpha_lab.factory.research_store import ResearchStore
    from solana_alpha_lab.factory.hfic_ordinary_operation import OPERATION_KIND, RESERVATION_KIND, get_operation
    from solana_alpha_lab.factory.hfic_grounded_discovery import result_sha256

    store = ResearchStore(plane, create_if_missing=False)
    require(store.diagnostics().committed_inventory_sha256 == terminal["store_inventory_sha256"], "STORE_INVENTORY_MISMATCH")
    source_records = terminal["source_records"]
    require(isinstance(source_records, dict) and bool(source_records), "NATIVE_FINGERPRINTS_MISSING")
    required_refs = {terminal["reservation_ref"], terminal["result_ref"], terminal["assessment_ref"]}
    require(required_refs <= source_records.keys(), "REFERENCE_NOT_FINGERPRINTED")
    native = {}
    operation_refs = set()
    for record in store.iter_committed_records():
        if record.record_id not in source_records:
            continue
        expected = source_records[record.record_id]
        observed = {"payload_sha256": hashlib.sha256(record.payload_json.encode("utf-8")).hexdigest(),
                    "stored_payload_sha256": record.payload_sha256, "producer_git_sha": record.producer_git_sha,
                    "producer_capability_id": record.producer_capability_id}
        require(observed == expected and observed["payload_sha256"] == observed["stored_payload_sha256"],
                "NATIVE_SOURCE_FINGERPRINT_MISMATCH")
        native[record.record_id] = body(record)
        if native[record.record_id].get("artifact_kind") == OPERATION_KIND:
            require(native[record.record_id]["operation_sha256"] == terminal["operation_sha256"], "WRONG_OPERATION_LINK")
            operation_refs.add(record.record_id)
    require(set(native) == set(source_records) == required_refs | operation_refs and bool(operation_refs), "NATIVE_REFS_MISMATCH")
    reservation, result, disposition = (native[terminal[key]] for key in ("reservation_ref", "result_ref", "assessment_ref"))
    require(reservation.get("artifact_kind") == RESERVATION_KIND
            and result.get("__wrapper_artifact_kind__") == "DISCOVERY_QUERY_LOOK", "NATIVE_REF_KIND_MISMATCH")
    operation = get_operation(store, terminal["operation_sha256"])
    require(reservation.get("operation_sha256") == result.get("operation_sha256") == operation["operation_sha256"], "WRONG_OPERATION_LINK")
    require(reservation.get("spec_sha256") == result.get("spec_sha256") == operation["spec_sha256"], "WRONG_SPEC_LINK")
    require(reservation.get("journal_scope") == result.get("journal_scope") == terminal["journal_scope"], "WRONG_JOURNAL_LINK")
    require(operation["market_evidence_epoch_sha256"] == terminal["market_evidence_epoch_sha256"], "WRONG_MARKET_LINK")
    require(result["result_sha256"] == result_sha256(result["result"]) == terminal["result_sha256"], "RESULT_HASH_MISMATCH")
    basis, subject = disposition["basis"], disposition["subject"]
    require(basis.get("operation_sha256") == terminal["operation_sha256"], "WRONG_DISPOSITION_OPERATION_LINK")
    require(basis["result_refs"] == [{"result_ref": terminal["result_ref"], "result_sha256": terminal["result_sha256"],
                                      "calculation_version": result["calculation_version"]}], "WRONG_DISPOSITION_RESULT_LINK")
    require(subject["journal_scope"] == terminal["journal_scope"]
            and subject["market_evidence_epoch_sha256"] == terminal["market_evidence_epoch_sha256"]
            and subject["question_spec_sha256"] == result["spec_sha256"], "WRONG_DISPOSITION_SUBJECT_LINK")
    require(disposition["ingestion"]["writer_module_sha256"] == sources["src/solana_alpha_lab/factory/hfic_scientific_disposition.py"],
            "PERSISTED_WRITER_SOURCE_MISMATCH")
    require(inventory(plane) == after, "VERIFIER_STORE_WRITE_DETECTED")
    return {"status": "INTEGRITY_VERIFIED", "product_verdict": "NOT_EVALUATED_BY_VERIFIER",
            "choice_quality": "UNVERIFIED", "result_ref": terminal["result_ref"],
            "operation_sha256": terminal["operation_sha256"], "assessment_ref": terminal["assessment_ref"],
            "terminal_sha256": digest(out / "terminal.json"), "verifier_source_sha256": digest(Path(__file__)),
            "invocation_count": len(summaries)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        answer = verify(args.output.resolve())
    except Exception as exc:
        answer = {"status": "HARNESS_ERROR", "integrity": "INVALID", "product_verdict": "NOT_EVALUATED_BY_VERIFIER",
                  "reason": str(exc) if isinstance(exc, InvalidTerminal) else type(exc).__name__}
        print(json.dumps(answer, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(answer, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
