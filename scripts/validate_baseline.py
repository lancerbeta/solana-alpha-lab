#!/usr/bin/env python3
"""Validate TASK-03 commit-ready and first-commit repository states."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT / "docs/evidence/task03_atom2f_commit_ready_receipt.json"
)

EXPECTED_FILES = {
    ".gitattributes",
    ".gitignore",
    ".env.example",
    ".python-version",
    ".githooks/pre-commit",
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    "uv.lock",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
    "docs/evidence/task03_atom2_baseline_receipt.json",
    "docs/evidence/task03_atom2_python_lock_receipt.json",
    "docs/evidence/task03_atom2d_quality_gate_receipt.json",
    "docs/evidence/task03_atom2e_staging_receipt.json",
    "docs/evidence/task03_atom2f_commit_ready_receipt.json",
    "scripts/validate_baseline.py",
    "scripts/validate.ps1",
    "scripts/secret_scan.py",
    "tests/test_baseline.py",
    "tests/test_secret_scan.py",
}
FINGERPRINT_FILES = EXPECTED_FILES - {
    "docs/evidence/task03_atom2f_commit_ready_receipt.json"
}
IGNORED_PARTS = {".git", ".venv", "__pycache__"}
EXPECTED_PYTHON = (3, 13, 14)
EXPECTED_REQUIRES_PYTHON = ">=3.13,<3.14"
EXPECTED_POWERSHELL = "7.6.3"
EXPECTED_HOOKS_PATH = ".githooks"
RECOMMENDED_COMMIT_MESSAGE = (
    "chore: establish local repository baseline"
)


def run(
    command: list[str],
    *,
    binary: bool = False,
) -> subprocess.CompletedProcess:
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def command_set(command: list[str]) -> tuple[int, set[str]]:
    completed = run(command)
    values = {
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    }
    return completed.returncode, values


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


def classify_repository_state(
    *,
    head_exists: bool,
    commit_count: int,
    tracked: set[str],
    staged: set[str],
    untracked: set[str],
    unstaged: set[str],
) -> str:
    if (
        not head_exists
        and commit_count == 0
        and tracked == EXPECTED_FILES
        and staged == EXPECTED_FILES
        and not untracked
        and not unstaged
    ):
        return "COMMIT_READY_STAGED"

    if (
        head_exists
        and commit_count == 1
        and tracked == EXPECTED_FILES
        and not staged
        and not untracked
        and not unstaged
    ):
        return "COMMITTED_BASELINE"

    return "INVALID_REPOSITORY_STATE"


def parse_index_entries(
    records: bytes,
) -> dict[str, tuple[str, str]]:
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


def parse_tree_entries(
    records: bytes,
) -> dict[str, tuple[str, str]]:
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
    if state == "COMMIT_READY_STAGED":
        completed = run(
            ["git", "ls-files", "--stage", "-z"],
            binary=True,
        )
        if completed.returncode != 0:
            raise AssertionError("index_read_failed")
        return parse_index_entries(completed.stdout)

    if state == "COMMITTED_BASELINE":
        completed = run(
            ["git", "ls-tree", "-r", "-z", "HEAD"],
            binary=True,
        )
        if completed.returncode != 0:
            raise AssertionError("head_tree_read_failed")
        return parse_tree_entries(completed.stdout)

    raise AssertionError("unsupported_fingerprint_state")


def blob_bytes(state: str, path: str) -> bytes:
    reference = f":{path}"
    if state == "COMMITTED_BASELINE":
        reference = f"HEAD:{path}"

    completed = run(
        ["git", "show", reference],
        binary=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"blob_read_failed:{path}")
    return completed.stdout


def fingerprints_for_state(state: str) -> tuple[str, str]:
    entries = source_entries(state)
    selected = {
        path: entries[path]
        for path in sorted(FINGERPRINT_FILES)
    }

    manifest = bytearray()
    content = bytearray()

    for path, (mode, oid) in selected.items():
        manifest.extend(
            f"{mode} {oid} {path}\n".encode("utf-8")
        )

        blob = blob_bytes(state, path)
        encoded_path = path.encode("utf-8")
        content.extend(len(encoded_path).to_bytes(4, "big"))
        content.extend(encoded_path)
        content.extend(len(blob).to_bytes(8, "big"))
        content.extend(blob)

    return (
        sha256_bytes(bytes(manifest)),
        sha256_bytes(bytes(content)),
    )


def contains_forbidden_absolute_user_path(text: str) -> bool:
    slash = "/"
    backslash = "\\"
    patterns = (
        re.compile(
            r"(?i)[A-Z]:"
            + re.escape(backslash)
            + "Users"
            + re.escape(backslash)
            + r"[^\\\s]+"
        ),
        re.compile(
            re.escape(slash)
            + "home"
            + re.escape(slash)
            + r"[^/\s]+",
            re.IGNORECASE,
        ),
        re.compile(
            re.escape(slash)
            + "Users"
            + re.escape(slash)
            + r"[^/\s]+",
            re.IGNORECASE,
        ),
    )
    return any(pattern.search(text) for pattern in patterns)


def validate_env_example(text: str) -> list[str]:
    errors: list[str] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line_{number}_missing_equals")
            continue
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            errors.append(f"line_{number}_invalid_key")
        if value.strip():
            errors.append(f"line_{number}_non_empty_value")

    return errors


def assert_check(
    name: str,
    condition: bool,
    detail: str = "",
) -> None:
    if not condition:
        suffix = f": {detail}" if detail else ""
        raise AssertionError(f"{name}{suffix}")
    print(f"{name}: PASS")


def validate() -> None:
    assert_check(
        "file_set",
        repository_files() == EXPECTED_FILES,
    )

    branch = run(["git", "symbolic-ref", "--short", "HEAD"])
    assert_check(
        "branch_main",
        branch.returncode == 0
        and branch.stdout.strip() == "main",
    )

    head = run(["git", "rev-parse", "--verify", "HEAD"])
    head_exists = head.returncode == 0

    commit_count = 0
    if head_exists:
        count = run(["git", "rev-list", "--count", "HEAD"])
        assert_check(
            "commit_count_read",
            count.returncode == 0,
        )
        commit_count = int(count.stdout.strip())

    remote_code, remotes = command_set(["git", "remote"])
    assert_check(
        "remote_count_zero",
        remote_code == 0 and not remotes,
    )

    tracked_code, tracked = command_set(["git", "ls-files"])
    staged_code, staged = command_set(
        ["git", "diff", "--cached", "--name-only"]
    )
    untracked_code, untracked = command_set(
        ["git", "ls-files", "--others", "--exclude-standard"]
    )
    unstaged_code, unstaged = command_set(
        ["git", "diff", "--name-only"]
    )

    assert_check(
        "git_inventory_commands",
        all(
            code == 0
            for code in (
                tracked_code,
                staged_code,
                untracked_code,
                unstaged_code,
            )
        ),
    )

    state = classify_repository_state(
        head_exists=head_exists,
        commit_count=commit_count,
        tracked=tracked,
        staged=staged,
        untracked=untracked,
        unstaged=unstaged,
    )
    assert_check(
        "repository_state",
        state
        in {
            "COMMIT_READY_STAGED",
            "COMMITTED_BASELINE",
        },
        state,
    )

    assert_check("venv_present", (ROOT / ".venv").is_dir())

    pin_text = (
        ROOT / ".python-version"
    ).read_text(encoding="utf-8")
    assert_check(
        "python_version_file",
        pin_text == "3.13.14\n",
    )

    with (ROOT / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)

    project = metadata.get("project", {})
    tool_state = (
        metadata.get("tool", {}).get("solana-alpha-lab", {})
    )

    assert_check(
        "requires_python",
        project.get("requires-python")
        == EXPECTED_REQUIRES_PYTHON,
    )
    assert_check(
        "exact_python_pin",
        tool_state.get("exact_python_pin") == "3.13.14",
    )
    assert_check(
        "exact_powershell_pin",
        tool_state.get("exact_powershell_pin")
        == EXPECTED_POWERSHELL,
    )
    assert_check(
        "runtime_exact",
        sys.version_info[:3] == EXPECTED_PYTHON,
    )
    assert_check(
        "runtime_is_venv",
        Path(sys.prefix).resolve() == (ROOT / ".venv").resolve(),
    )

    managed = run(
        ["uv", "python", "find", "--managed-python", "3.13.14"]
    )
    assert_check(
        "managed_python_present",
        managed.returncode == 0,
    )

    lock = run(
        ["uv", "lock", "--check", "--managed-python"]
    )
    assert_check(
        "uv_lock_check",
        lock.returncode == 0,
        lock.stderr.strip(),
    )

    hooks = run(
        [
            "git",
            "config",
            "--local",
            "--get",
            "core.hooksPath",
        ]
    )
    assert_check(
        "hooks_path_config",
        hooks.returncode == 0
        and hooks.stdout.strip() == EXPECTED_HOOKS_PATH,
    )

    hook_text = (
        ROOT / ".githooks/pre-commit"
    ).read_text(encoding="utf-8")
    assert_check(
        "pre_commit_execution_policy",
        "-ExecutionPolicy Bypass" in hook_text,
    )

    entries = source_entries(state)
    assert_check(
        "source_inventory",
        set(entries) == EXPECTED_FILES,
    )
    assert_check(
        "pre_commit_mode",
        entries[".githooks/pre-commit"][0] == "100755",
        entries[".githooks/pre-commit"][0],
    )

    if state == "COMMIT_READY_STAGED":
        diff_check = run(["git", "diff", "--cached", "--check"])
        assert_check(
            "staged_diff_check",
            diff_check.returncode == 0,
            diff_check.stdout.strip() + diff_check.stderr.strip(),
        )
    else:
        parents = run(
            ["git", "rev-list", "--parents", "-n", "1", "HEAD"]
        )
        parent_tokens = parents.stdout.strip().split()
        assert_check(
            "single_root_commit",
            parents.returncode == 0
            and commit_count == 1
            and len(parent_tokens) == 1,
        )

        tree_check = run(
            ["git", "diff-tree", "--check", "--root", "HEAD"]
        )
        assert_check(
            "committed_tree_check",
            tree_check.returncode == 0,
            tree_check.stdout.strip() + tree_check.stderr.strip(),
        )

    env_errors = validate_env_example(
        (ROOT / ".env.example").read_text(encoding="utf-8")
    )
    assert_check(
        "env_example_placeholder_only",
        not env_errors,
        str(env_errors),
    )
    assert_check("real_env_absent", not (ROOT / ".env").exists())

    text_files: Iterable[Path] = (
        ROOT / relative for relative in EXPECTED_FILES
    )
    line_endings: list[str] = []
    absolute_paths: list[str] = []

    for path in text_files:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        relative = path.relative_to(ROOT).as_posix()

        if b"\r\n" in raw or b"\r" in raw:
            line_endings.append(relative)
        if contains_forbidden_absolute_user_path(text):
            absolute_paths.append(relative)

    assert_check(
        "lf_line_endings",
        not line_endings,
        str(line_endings),
    )
    assert_check(
        "no_absolute_user_paths",
        not absolute_paths,
        str(absolute_paths),
    )

    receipt = json.loads(
        RECEIPT_PATH.read_text(encoding="utf-8")
    )
    allow_pending = (
        os.environ.get(
            "TASK03_ALLOW_PENDING_COMMIT_READY"
        )
        == "1"
    )
    receipt_result = receipt.get("result")

    assert_check(
        "receipt_identity",
        receipt.get("task_id") == "TASK-03"
        and receipt.get("atom_id") == "TASK03-ATOM-2F"
        and (
            receipt_result == "PASS"
            or (
                allow_pending
                and receipt_result == "PENDING"
            )
        ),
        str(receipt_result),
    )
    assert_check(
        "receipt_state_contract",
        receipt.get("prepared_state")
        == "COMMIT_READY_STAGED"
        and receipt.get("post_commit_state_supported")
        == "COMMITTED_BASELINE",
    )
    assert_check(
        "receipt_commit_policy",
        receipt.get("recommended_commit_message")
        == RECOMMENDED_COMMIT_MESSAGE
        and receipt.get("author_identity_status")
        == "PENDING_ATOM_2G",
    )

    expected_hashes = receipt.get("static_file_sha256", {})
    observed_hashes = {
        relative: sha256(ROOT / relative)
        for relative in sorted(FINGERPRINT_FILES)
    }
    assert_check(
        "receipt_hashes",
        expected_hashes == observed_hashes,
    )

    manifest_hash, content_hash = fingerprints_for_state(state)
    assert_check(
        "payload_manifest_fingerprint",
        receipt.get("payload_manifest_sha256")
        == manifest_hash,
    )
    assert_check(
        "payload_content_fingerprint",
        receipt.get("payload_content_sha256")
        == content_hash,
    )
    assert_check(
        "receipt_file_count",
        receipt.get("expected_file_count")
        == len(EXPECTED_FILES),
    )

    tests = run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ]
    )
    if tests.stdout.strip():
        print(tests.stdout.strip())
    if tests.stderr.strip():
        print(tests.stderr.strip())
    assert_check("unit_tests", tests.returncode == 0)

    print(f"REPOSITORY_STATE: {state}")
    print("RESULT: PASS")


def main() -> int:
    print("=== TASK-03 ATOM 2F COMMIT-READY VALIDATION ===")
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
