#!/usr/bin/env python3
"""Validate TASK-03 staged or committed pre-Git import state."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT_OID = 'ee6119ae0b7750710c7f822c50137ed95b4977e9'
BASE_TREE_OID = '47181f0595e687858a3c3f790ae2f79415aed4a2'
BASE_PARENT_OID = '399ef0365b017fcd9d7b81389218a63bf1e466c1'
BASE_FILE_COUNT = 32
BASE_COMMIT_COUNT = 2
CURRENT_RECEIPT = ROOT / 'docs/evidence/task03_atom4b_pre_git_import_receipt.json'
EXPECTED_REPOSITORY_FILE_COUNT = 58
EXPECTED_CHANGED_FILES = {'docs/tasks/TASK-03.md', 'tests/test_baseline.py', 'docs/evidence/pre_git/task02/operator_observation_receipt.json', 'scripts/validate_catalog.py', 'catalog/assets/pre_git.yaml', 'docs/evidence/pre_git/task01/validation_report.txt', 'docs/evidence/pre_git/task02/validation_receipt.json', 'docs/evidence/pre_git/task01/sources_v1.yaml', 'docs/evidence/task03_atom4b_pre_git_import_receipt.json', 'docs/evidence/pre_git/task01/provider_cost_snapshot_v1.csv', 'docs/evidence/pre_git/task01/provider_smoke_spec_v1.yaml', 'catalog/assets/core.yaml', 'catalog/query_recipes.yaml', 'docs/evidence/pre_git/task02/bootstrap_check.py', 'docs/evidence/pre_git/task02/env_report.txt', 'docs/architecture/intents/ARCH-INTENT-001-hypothesis-factory-and-regime-aware-orchestration.md', 'tests/test_pre_git_import.py', 'catalog/schemas/asset_catalog.schema.json', 'docs/evidence/pre_git/task01/provider_decision_v1.md', 'docs/evidence/pre_git/task01/hypothesis_data_coverage_matrix_v1.md', 'docs/evidence/pre_git/task01/task_01_completion_record_v1.md', 'scripts/validate.ps1', 'docs/handoffs/latest.md', 'docs/evidence/pre_git/task02/TASK02_COMPLETION_SUMMARY.md', 'docs/evidence/pre_git/task02/tool_versions.json', 'docs/evidence/pre_git/task01/task_01_final_gap_audit_v1.md', 'catalog/catalog_manifest.yaml', 'catalog/assets/architecture.yaml', 'docs/evidence/pre_git/task02/CHECKSUMS_SHA256.txt', 'scripts/validate_baseline.py', 'scripts/validate_pre_git_import.py', 'tests/test_catalog.py', 'README.md', 'catalog/schemas/catalog_manifest.schema.json', 'docs/evidence/pre_git/task01/provider_account_checklist_v1.md', 'docs/evidence/pre_git/task01/reuse_candidate_registry.yaml', 'docs/evidence/pre_git/task01/CHECKSUMS_SHA256.txt', 'AGENTS.md', 'docs/evidence/pre_git/task01/data_option_tiers_v1.yaml', 'docs/evidence/pre_git/task02/task_02_workstation_bootstrap.md'}
FINGERPRINT_FILES = EXPECTED_CHANGED_FILES - {'docs/evidence/task03_atom4b_pre_git_import_receipt.json'}
EXACT_IMPORT_FILES = {
    path
    for path in EXPECTED_CHANGED_FILES
    if path.startswith("docs/evidence/pre_git/task01/")
    or path.startswith("docs/evidence/pre_git/task02/")
}
STYLE_CHECKED_CHANGED_FILES = EXPECTED_CHANGED_FILES - EXACT_IMPORT_FILES
EXPECTED_EXACT_IMPORT_COUNT = 20
EXACT_IMPORT_WHITESPACE_POLICY = (
    "PRESERVE_EXACT_BYTES_HASH_VERIFIED_STYLE_EXEMPT"
)
EXPECTED_PYTHON = (3, 13, 14)
EXPECTED_POWERSHELL = "7.6.3"
EXPECTED_JSONSCHEMA = "4.26.0"
EXPECTED_PYYAML = "6.0.3"
RECOMMENDED_COMMIT_MESSAGE = 'feat: import pre-git evidence and register architecture intent'
EXPECTED_GITATTRIBUTES = "* text=auto eol=lf\n*.ps1 text eol=lf\n*.bat text eol=crlf\n*.cmd text eol=crlf\n"
PS1_PROBE = "scripts/validate.ps1"
IGNORED_PARTS = {".git", ".venv", "__pycache__"}


def run(command: list[str], *, binary: bool = False):
    env = os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"] = "1"; env["UV_MANAGED_PYTHON"] = "1"
    return subprocess.run(command, cwd=ROOT, env=env, text=not binary, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def command_set(command: list[str]) -> tuple[int, set[str]]:
    result = run(command)
    return result.returncode, {line.strip() for line in result.stdout.splitlines() if line.strip()}


def repository_files() -> set[str]:
    result = set()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in IGNORED_PARTS for part in relative.parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        result.add(relative.as_posix())
    return result


def parse_index_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result = {}
    for record in records.split(b"\0"):
        if not record: continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        if stage != "0": raise AssertionError("non_zero_index_stage")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def parse_tree_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result = {}
    for record in records.split(b"\0"):
        if not record: continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        if object_type != "blob": raise AssertionError("non_blob_tree_entry")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def source_entries(state: str) -> dict[str, tuple[str, str]]:
    if state == "PRE_GIT_IMPORT_STAGED":
        result = run(["git","ls-files","--stage","-z"], binary=True)
        if result.returncode != 0: raise AssertionError("index_read_failed")
        return parse_index_entries(result.stdout)
    result = run(["git","ls-tree","-r","-z","HEAD"], binary=True)
    if result.returncode != 0: raise AssertionError("head_tree_read_failed")
    return parse_tree_entries(result.stdout)


def blob_bytes(state: str, path: str) -> bytes:
    reference = f":{path}" if state == "PRE_GIT_IMPORT_STAGED" else f"HEAD:{path}"
    result = run(["git","show",reference], binary=True)
    if result.returncode != 0: raise AssertionError(f"blob_read_failed:{path}")
    return result.stdout


def fingerprints(state: str) -> tuple[str, str]:
    entries = source_entries(state); manifest = bytearray(); content = bytearray()
    for path in sorted(FINGERPRINT_FILES):
        mode, oid = entries[path]
        manifest.extend(f"{mode} {oid} {path}\n".encode("utf-8"))
        blob = blob_bytes(state, path); encoded = path.encode("utf-8")
        content.extend(len(encoded).to_bytes(4,"big")); content.extend(encoded); content.extend(len(blob).to_bytes(8,"big")); content.extend(blob)
    return hashlib.sha256(bytes(manifest)).hexdigest(), hashlib.sha256(bytes(content)).hexdigest()


def classify_state(*, head_oid: str, commit_count: int, parent_oid: str | None, tracked: set[str], staged: set[str], untracked: set[str], unstaged: set[str]) -> str:
    if head_oid == BASE_COMMIT_OID and commit_count == BASE_COMMIT_COUNT and tracked == repository_files() and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT and staged == EXPECTED_CHANGED_FILES and not untracked and not unstaged:
        return "PRE_GIT_IMPORT_STAGED"
    if commit_count == BASE_COMMIT_COUNT + 1 and parent_oid == BASE_COMMIT_OID and tracked == repository_files() and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT and not staged and not untracked and not unstaged:
        return "PRE_GIT_IMPORT_COMMITTED"
    return "INVALID_REPOSITORY_STATE"


def parse_check_attr_z(output: bytes) -> tuple[str,str,str]:
    parts = output.split(b"\0"); parts = parts[:-1] if parts and parts[-1] == b"" else parts
    if len(parts) != 3: raise AssertionError("check_attr_triplet_invalid")
    return tuple(part.decode("utf-8") for part in parts)


def validate_eol(state: str) -> None:
    if (ROOT/".gitattributes").read_text(encoding="utf-8") != EXPECTED_GITATTRIBUTES: raise AssertionError("gitattributes_policy_mismatch")
    attr = run(["git","check-attr","--cached","-z","eol","--",PS1_PROBE], binary=True)
    if attr.returncode != 0 or parse_check_attr_z(attr.stdout) != (PS1_PROBE,"eol","lf"): raise AssertionError("cached_eol_mismatch")
    if b"\r" in (ROOT/PS1_PROBE).read_bytes() or b"\r" in blob_bytes(state, PS1_PROBE): raise AssertionError("ps1_contains_cr")
    with tempfile.TemporaryDirectory(prefix="smial_atom4b_checkout_") as temporary:
        result = run(["git","checkout-index","--all","--force",f"--prefix={Path(temporary).as_posix().rstrip('/')}/"])
        if result.returncode != 0 or b"\r" in (Path(temporary)/PS1_PROBE).read_bytes(): raise AssertionError("checkout_roundtrip_eol_failed")


def assert_check(name: str, condition: bool, detail: str = "") -> None:
    if not condition: raise AssertionError(name + ((": " + detail) if detail else ""))
    print(f"{name}: PASS")


def validate_staged_style_policy() -> None:
    """Apply whitespace style checks only to repository-authored changes.

    Exact pre-Git evidence is immutable, hash-verified source material. Rewriting
    or rejecting it for style would violate exact-byte provenance. Its hashes, LF
    encoding, secret/path scan, source bundle lineage, and availability are
    validated separately by validate_pre_git_import.py.
    """
    assert_check(
        "exact_import_style_exempt_count",
        len(EXACT_IMPORT_FILES) == EXPECTED_EXACT_IMPORT_COUNT,
        str(len(EXACT_IMPORT_FILES)),
    )
    assert_check(
        "style_policy_partition",
        not (EXACT_IMPORT_FILES & STYLE_CHECKED_CHANGED_FILES)
        and (EXACT_IMPORT_FILES | STYLE_CHECKED_CHANGED_FILES)
        == EXPECTED_CHANGED_FILES,
    )
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(STYLE_CHECKED_CHANGED_FILES),
        ]
    )
    assert_check(
        "staged_style_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )
    print("immutable_exact_import_style_policy: PASS")


def validate() -> None:
    assert_check("repository_file_count", len(repository_files()) == EXPECTED_REPOSITORY_FILE_COUNT)
    branch = run(["git","symbolic-ref","--short","HEAD"]); assert_check("branch_main", branch.returncode == 0 and branch.stdout.strip() == "main")
    head = run(["git","rev-parse","HEAD"]); assert_check("head_read", head.returncode == 0); head_oid = head.stdout.strip()
    count = run(["git","rev-list","--count","HEAD"]); assert_check("commit_count_read", count.returncode == 0); commit_count = int(count.stdout.strip())
    parent_oid = None
    if commit_count >= 2:
        parent = run(["git","rev-parse","HEAD^"]); assert_check("parent_read", parent.returncode == 0); parent_oid = parent.stdout.strip()
    remote_code, remotes = command_set(["git","remote"])
    tracked_code, tracked = command_set(["git","ls-files"])
    staged_code, staged = command_set(["git","diff","--cached","--name-only"])
    untracked_code, untracked = command_set(["git","ls-files","--others","--exclude-standard"])
    unstaged_code, unstaged = command_set(["git","diff","--name-only"])
    assert_check("git_inventory_commands", all(c == 0 for c in (remote_code,tracked_code,staged_code,untracked_code,unstaged_code)))
    assert_check("remote_count_zero", not remotes)
    state = classify_state(head_oid=head_oid,commit_count=commit_count,parent_oid=parent_oid,tracked=tracked,staged=staged,untracked=untracked,unstaged=unstaged)
    assert_check("repository_state", state in {"PRE_GIT_IMPORT_STAGED","PRE_GIT_IMPORT_COMMITTED"}, state)
    if state == "PRE_GIT_IMPORT_COMMITTED":
        message = run(["git","log","-1","--pretty=%B"])
        assert_check("import_commit_message", message.returncode == 0 and message.stdout.strip() == RECOMMENDED_COMMIT_MESSAGE, message.stdout.strip())
    assert_check("venv_present", (ROOT/".venv").is_dir())
    assert_check("runtime_exact", sys.version_info[:3] == EXPECTED_PYTHON)
    assert_check("runtime_is_venv", Path(sys.prefix).resolve() == (ROOT/".venv").resolve())
    assert_check("jsonschema_version", importlib.metadata.version("jsonschema") == EXPECTED_JSONSCHEMA)
    assert_check("pyyaml_version", importlib.metadata.version("PyYAML") == EXPECTED_PYYAML)
    with (ROOT/"pyproject.toml").open("rb") as handle: metadata = tomllib.load(handle)
    assert_check("dependency_contract", set(metadata["project"]["dependencies"]) == {f"PyYAML=={EXPECTED_PYYAML}",f"jsonschema=={EXPECTED_JSONSCHEMA}"})
    lock = run(["uv","lock","--check","--managed-python"]); assert_check("uv_lock_check", lock.returncode == 0, lock.stderr.strip())
    receipt = json.loads(CURRENT_RECEIPT.read_text(encoding="utf-8"))
    assert_check("receipt_identity", receipt.get("task_id") == "TASK-03" and receipt.get("atom_id") == "TASK03-ATOM-4B" and receipt.get("result") == "PASS")
    assert_check("receipt_base_commit", receipt.get("base_commit_oid") == BASE_COMMIT_OID and receipt.get("base_tree_oid") == BASE_TREE_OID)
    assert_check("receipt_candidate_contract", receipt.get("candidate_state") == "PRE_GIT_IMPORT_STAGED" and receipt.get("post_commit_state_supported") == "PRE_GIT_IMPORT_COMMITTED" and receipt.get("recommended_commit_message") == RECOMMENDED_COMMIT_MESSAGE)
    assert_check("receipt_counts", receipt.get("repository_file_count") == EXPECTED_REPOSITORY_FILE_COUNT and receipt.get("staged_file_count") == len(EXPECTED_CHANGED_FILES) and receipt.get("imported_exact_file_count") == 20 and receipt.get("catalog_asset_count") == 44)
    assert_check(
        "receipt_exact_import_style_policy",
        receipt.get("exact_import_whitespace_policy")
        == EXACT_IMPORT_WHITESPACE_POLICY
        and receipt.get("exact_import_style_exempt_file_count")
        == EXPECTED_EXACT_IMPORT_COUNT,
    )
    manifest_hash, content_hash = fingerprints(state)
    assert_check("payload_manifest_fingerprint", receipt.get("payload_manifest_sha256") == manifest_hash)
    assert_check("payload_content_fingerprint", receipt.get("payload_content_sha256") == content_hash)
    assert_check("source_inventory", set(source_entries(state)) == repository_files())
    assert_check("pre_commit_mode", source_entries(state)[".githooks/pre-commit"][0] == "100755")
    validate_eol(state); print("eol_checkout_contract: PASS")
    if state == "PRE_GIT_IMPORT_STAGED":
        validate_staged_style_policy()
    tests = run([sys.executable,"-B","-m","unittest","discover","-s","tests","-p","test_*.py"])
    if tests.stdout.strip(): print(tests.stdout.strip())
    if tests.stderr.strip(): print(tests.stderr.strip())
    assert_check("unit_tests", tests.returncode == 0)
    print(f"REPOSITORY_STATE: {state}")
    print("RESULT: PASS")


def main() -> int:
    print("=== TASK-03 ATOM 4B REPOSITORY VALIDATION ===")
    try: validate()
    except Exception as exc:
        print("RESULT: FAIL"); print(f"ERROR_TYPE: {type(exc).__name__}"); print(f"ERROR: {exc}"); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
