#!/usr/bin/env python3
"""Validate TASK-03 Catalog foundation with deterministic LF checkout policy."""

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
BASE_COMMIT_OID = '399ef0365b017fcd9d7b81389218a63bf1e466c1'
BASE_TREE_OID = '8f5559723ca0aefb4fa706131d3b1839481be19d'
BASE_FILE_COUNT = 21
CURRENT_RECEIPT = ROOT / 'docs/evidence/task03_atom3a_catalog_foundation_receipt.json'
EXPECTED_REPOSITORY_FILE_COUNT = 32
EXPECTED_CHANGED_FILES = {'catalog/query_recipes.yaml', 'catalog/schemas/catalog_manifest.schema.json', '.gitattributes', 'catalog/schemas/asset_catalog.schema.json', 'docs/evidence/task03_atom3a_catalog_foundation_receipt.json', 'scripts/catalog_cli.py', 'scripts/validate_baseline.py', 'tests/test_baseline.py', 'catalog/assets/core.yaml', 'pyproject.toml', 'docs/tasks/TASK-03.md', 'scripts/validate_catalog.py', 'tests/test_catalog.py', 'catalog/schemas/query_recipe.schema.json', 'README.md', 'catalog/catalog_manifest.yaml', 'docs/decisions/ADR-001-project-asset-catalog-baseline.md', 'AGENTS.md', 'docs/handoffs/latest.md', 'scripts/validate.ps1', 'uv.lock'}
EXPECTED_STAGED_FILES = len(EXPECTED_CHANGED_FILES)
FINGERPRINT_FILES = EXPECTED_CHANGED_FILES - {'docs/evidence/task03_atom3a_catalog_foundation_receipt.json'}
EXPECTED_PYTHON = (3, 13, 14)
EXPECTED_POWERSHELL = "7.6.3"
EXPECTED_JSONSCHEMA = "4.26.0"
EXPECTED_PYYAML = "6.0.3"
RECOMMENDED_COMMIT_MESSAGE = 'feat: add project asset catalog foundation'
EXPECTED_PS1_RULE = "*.ps1 text eol=lf"
FORBIDDEN_PS1_RULE = "*.ps1 text eol=crlf"
EXPECTED_PS1_PATHS = {"scripts/validate.ps1"}
SUPERSEDED_RECEIPT_SHA256 = 'de34a4ccc39a89d8d1ae9ddbc394ba92603b2bbbed9fecaf9db9ab1bf920662d'
IGNORED_PARTS = {".git", ".venv", "__pycache__"}


def run(command: list[str], *, binary: bool = False):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["UV_MANAGED_PYTHON"] = "1"
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=not binary,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def command_set(command: list[str]) -> tuple[int, set[str]]:
    result = run(command)
    values = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return result.returncode, values


def repository_files() -> set[str]:
    result: set[str] = set()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        result.add(relative.as_posix())
    return result


def parse_index_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for record in records.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise AssertionError("non_zero_index_stage")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def parse_tree_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for record in records.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        if object_type != "blob":
            raise AssertionError("non_blob_tree_entry")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def source_entries(state: str) -> dict[str, tuple[str, str]]:
    if state == "CATALOG_FOUNDATION_STAGED":
        result = run(["git", "ls-files", "--stage", "-z"], binary=True)
        if result.returncode != 0:
            raise AssertionError("index_read_failed")
        return parse_index_entries(result.stdout)

    result = run(["git", "ls-tree", "-r", "-z", "HEAD"], binary=True)
    if result.returncode != 0:
        raise AssertionError("head_tree_read_failed")
    return parse_tree_entries(result.stdout)


def blob_bytes(state: str, path: str) -> bytes:
    reference = f":{path}" if state == "CATALOG_FOUNDATION_STAGED" else f"HEAD:{path}"
    result = run(["git", "show", reference], binary=True)
    if result.returncode != 0:
        raise AssertionError(f"blob_read_failed:{path}")
    return result.stdout


def fingerprints(state: str) -> tuple[str, str]:
    entries = source_entries(state)
    manifest = bytearray()
    content = bytearray()

    for path in sorted(FINGERPRINT_FILES):
        mode, oid = entries[path]
        manifest.extend(f"{mode} {oid} {path}\n".encode("utf-8"))
        blob = blob_bytes(state, path)
        encoded = path.encode("utf-8")
        content.extend(len(encoded).to_bytes(4, "big"))
        content.extend(encoded)
        content.extend(len(blob).to_bytes(8, "big"))
        content.extend(blob)

    return (
        hashlib.sha256(bytes(manifest)).hexdigest(),
        hashlib.sha256(bytes(content)).hexdigest(),
    )


def classify_state(
    *,
    head_oid: str,
    commit_count: int,
    parent_oid: str | None,
    tracked: set[str],
    staged: set[str],
    untracked: set[str],
    unstaged: set[str],
) -> str:
    if (
        head_oid == BASE_COMMIT_OID
        and commit_count == 1
        and tracked == repository_files()
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and staged == EXPECTED_CHANGED_FILES
        and not untracked
        and not unstaged
    ):
        return "CATALOG_FOUNDATION_STAGED"

    if (
        commit_count == 2
        and parent_oid == BASE_COMMIT_OID
        and tracked == repository_files()
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
    ):
        return "CATALOG_FOUNDATION_COMMITTED"

    return "INVALID_REPOSITORY_STATE"


def parse_eol_attribute(output: str, expected_path: str) -> str:
    prefix = f"{expected_path}: eol: "
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1 or not lines[0].startswith(prefix):
        raise AssertionError("unexpected_check_attr_output")
    return lines[0][len(prefix):].strip()


def is_lf_only(data: bytes) -> bool:
    return bool(data) and b"\r" not in data and b"\n" in data


def checkout_index_bytes(relative_path: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="smial_eol_checkout_") as temporary:
        prefix = Path(temporary).resolve().as_posix() + "/"
        result = run([
            "git", "checkout-index", "--all", "--force", f"--prefix={prefix}"
        ])
        if result.returncode != 0:
            raise AssertionError(
                "checkout_index_failed:" + result.stderr.strip()
            )
        return (Path(temporary) / relative_path).read_bytes()


def eol_evidence(state: str) -> dict[str, str]:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    if EXPECTED_PS1_RULE not in attributes or FORBIDDEN_PS1_RULE in attributes:
        raise AssertionError("gitattributes_ps1_rule_mismatch")

    tracked_ps1 = run(["git", "ls-files", "*.ps1"])
    if tracked_ps1.returncode != 0:
        raise AssertionError("ps1_inventory_failed")
    paths = {line.strip() for line in tracked_ps1.stdout.splitlines() if line.strip()}
    if paths != EXPECTED_PS1_PATHS:
        raise AssertionError(f"ps1_inventory_mismatch:{sorted(paths)}")

    path = next(iter(EXPECTED_PS1_PATHS))
    work_attr = run(["git", "check-attr", "eol", "--", path])
    cache_attr = run(["git", "check-attr", "--cached", "eol", "--", path])
    if work_attr.returncode != 0 or cache_attr.returncode != 0:
        raise AssertionError("check_attr_failed")
    work_value = parse_eol_attribute(work_attr.stdout, path)
    cache_value = parse_eol_attribute(cache_attr.stdout, path)
    if work_value != "lf" or cache_value != "lf":
        raise AssertionError(f"ps1_attribute_not_lf:{work_value}:{cache_value}")

    working = (ROOT / path).read_bytes()
    source = blob_bytes(state, path)
    roundtrip = checkout_index_bytes(path)
    if not is_lf_only(working):
        raise AssertionError("working_tree_ps1_not_lf")
    if not is_lf_only(source):
        raise AssertionError("source_ps1_not_lf")
    if not is_lf_only(roundtrip):
        raise AssertionError("checkout_roundtrip_ps1_not_lf")

    return {
        "gitattributes_rule": EXPECTED_PS1_RULE,
        "working_attribute": work_value,
        "cached_attribute": cache_value,
        "working_tree_bytes": "LF_NO_CR",
        "source_blob_bytes": "LF_NO_CR",
        "checkout_index_roundtrip": "LF_NO_CR",
    }


def assert_check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        suffix = f": {detail}" if detail else ""
        raise AssertionError(f"{name}{suffix}")
    print(f"{name}: PASS")


def validate() -> None:
    assert_check("repository_file_count", len(repository_files()) == EXPECTED_REPOSITORY_FILE_COUNT)

    branch = run(["git", "symbolic-ref", "--short", "HEAD"])
    assert_check("branch_main", branch.returncode == 0 and branch.stdout.strip() == "main")

    head = run(["git", "rev-parse", "HEAD"])
    assert_check("head_read", head.returncode == 0)
    head_oid = head.stdout.strip()

    count = run(["git", "rev-list", "--count", "HEAD"])
    assert_check("commit_count_read", count.returncode == 0)
    commit_count = int(count.stdout.strip())

    parent_oid: str | None = None
    if commit_count >= 2:
        parent = run(["git", "rev-parse", "HEAD^"])
        assert_check("parent_read", parent.returncode == 0)
        parent_oid = parent.stdout.strip()

    remote_code, remotes = command_set(["git", "remote"])
    tracked_code, tracked = command_set(["git", "ls-files"])
    staged_code, staged = command_set(["git", "diff", "--cached", "--name-only"])
    untracked_code, untracked = command_set(["git", "ls-files", "--others", "--exclude-standard"])
    unstaged_code, unstaged = command_set(["git", "diff", "--name-only"])

    assert_check(
        "git_inventory_commands",
        all(code == 0 for code in (remote_code, tracked_code, staged_code, untracked_code, unstaged_code)),
    )
    assert_check("remote_count_zero", not remotes)

    state = classify_state(
        head_oid=head_oid,
        commit_count=commit_count,
        parent_oid=parent_oid,
        tracked=tracked,
        staged=staged,
        untracked=untracked,
        unstaged=unstaged,
    )
    assert_check(
        "repository_state",
        state in {"CATALOG_FOUNDATION_STAGED", "CATALOG_FOUNDATION_COMMITTED"},
        state,
    )

    if state == "CATALOG_FOUNDATION_COMMITTED":
        message = run(["git", "log", "-1", "--pretty=%B"])
        assert_check(
            "catalog_commit_message",
            message.returncode == 0 and message.stdout.strip() == RECOMMENDED_COMMIT_MESSAGE,
            message.stdout.strip(),
        )

    assert_check("venv_present", (ROOT / ".venv").is_dir())
    assert_check("runtime_exact", sys.version_info[:3] == EXPECTED_PYTHON)
    assert_check("runtime_is_venv", Path(sys.prefix).resolve() == (ROOT / ".venv").resolve())
    assert_check("jsonschema_version", importlib.metadata.version("jsonschema") == EXPECTED_JSONSCHEMA)
    assert_check("pyyaml_version", importlib.metadata.version("PyYAML") == EXPECTED_PYYAML)

    with (ROOT / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)
    dependencies = set(metadata["project"]["dependencies"])
    assert_check(
        "dependency_contract",
        dependencies == {f"PyYAML=={EXPECTED_PYYAML}", f"jsonschema=={EXPECTED_JSONSCHEMA}"},
    )

    lock = run(["uv", "lock", "--check", "--managed-python"])
    assert_check("uv_lock_check", lock.returncode == 0, lock.stderr.strip())

    receipt = json.loads(CURRENT_RECEIPT.read_text(encoding="utf-8"))
    assert_check(
        "receipt_identity",
        receipt.get("task_id") == "TASK-03"
        and receipt.get("atom_id") == "TASK03-ATOM-3A-R"
        and receipt.get("result") == "PASS",
    )
    assert_check(
        "receipt_base_commit",
        receipt.get("base_commit_oid") == BASE_COMMIT_OID
        and receipt.get("base_tree_oid") == BASE_TREE_OID,
    )
    assert_check(
        "receipt_candidate_contract",
        receipt.get("candidate_state") == "CATALOG_FOUNDATION_STAGED"
        and receipt.get("post_commit_state_supported") == "CATALOG_FOUNDATION_COMMITTED"
        and receipt.get("recommended_commit_message") == RECOMMENDED_COMMIT_MESSAGE,
    )
    assert_check(
        "receipt_repair_lineage",
        receipt.get("supersedes_atom_id") == "TASK03-ATOM-3A"
        and receipt.get("supersedes_receipt_sha256") == SUPERSEDED_RECEIPT_SHA256,
    )
    assert_check("receipt_changed_count", receipt.get("staged_file_count") == EXPECTED_STAGED_FILES)
    assert_check("receipt_repository_count", receipt.get("repository_file_count") == EXPECTED_REPOSITORY_FILE_COUNT)

    manifest_hash, content_hash = fingerprints(state)
    assert_check("payload_manifest_fingerprint", receipt.get("payload_manifest_sha256") == manifest_hash)
    assert_check("payload_content_fingerprint", receipt.get("payload_content_sha256") == content_hash)
    assert_check(
        "receipt_lock_hash",
        receipt.get("uv_lock_sha256") == hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
    )

    entries = source_entries(state)
    assert_check("source_inventory", set(entries) == repository_files())
    assert_check("pre_commit_mode", entries[".githooks/pre-commit"][0] == "100755")

    evidence = eol_evidence(state)
    assert_check("gitattributes_ps1_rule", evidence["gitattributes_rule"] == EXPECTED_PS1_RULE)
    assert_check("ps1_eol_attribute_worktree", evidence["working_attribute"] == "lf")
    assert_check("ps1_eol_attribute_index", evidence["cached_attribute"] == "lf")
    assert_check("ps1_working_tree_lf", evidence["working_tree_bytes"] == "LF_NO_CR")
    assert_check("ps1_source_blob_lf", evidence["source_blob_bytes"] == "LF_NO_CR")
    assert_check("ps1_checkout_roundtrip_lf", evidence["checkout_index_roundtrip"] == "LF_NO_CR")
    assert_check("receipt_eol_contract", receipt.get("eol_contract") == evidence)

    if state == "CATALOG_FOUNDATION_STAGED":
        diff_check = run(["git", "diff", "--cached", "--check"])
        assert_check("staged_diff_check", diff_check.returncode == 0, diff_check.stdout.strip() + diff_check.stderr.strip())
    else:
        tree_check = run(["git", "diff-tree", "--check", "--root", "HEAD"])
        assert_check("committed_tree_check", tree_check.returncode == 0, tree_check.stdout.strip() + tree_check.stderr.strip())

    tests = run([
        sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"
    ])
    if tests.stdout.strip():
        print(tests.stdout.strip())
    if tests.stderr.strip():
        print(tests.stderr.strip())
    assert_check("unit_tests", tests.returncode == 0)

    print(f"REPOSITORY_STATE: {state}")
    print("EOL_CHECKOUT_CONTRACT: PASS")
    print("RESULT: PASS")


def main() -> int:
    print("=== TASK-03 ATOM 3A-R EOL CONTRACT VALIDATION ===")
    try:
        validate()
    except Exception as exc:
        print("RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
