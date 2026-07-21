#!/usr/bin/env python3
"""Validate exact historical through Atom 7 pre-push repair states."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT_OID = 'ee6119ae0b7750710c7f822c50137ed95b4977e9'
BASE_TREE_OID = '47181f0595e687858a3c3f790ae2f79415aed4a2'
BASE_PARENT_OID = '399ef0365b017fcd9d7b81389218a63bf1e466c1'
BASE_FILE_COUNT = 32
BASE_COMMIT_COUNT = 2
IMPORT_COMMIT_OID = "e03639f4811d7e40f25b965ab79626c229c0fd8a"
IMPORT_COMMIT_COUNT = BASE_COMMIT_COUNT + 1
CURRENT_RECEIPT = ROOT / 'docs/evidence/task03_atom4b_pre_git_import_receipt.json'
EXPECTED_REPOSITORY_FILE_COUNT = 58
EXPECTED_CHANGED_FILES = {'docs/tasks/TASK-03.md', 'tests/test_baseline.py', 'docs/evidence/pre_git/task02/operator_observation_receipt.json', 'scripts/validate_catalog.py', 'catalog/assets/pre_git.yaml', 'docs/evidence/pre_git/task01/validation_report.txt', 'docs/evidence/pre_git/task02/validation_receipt.json', 'docs/evidence/pre_git/task01/sources_v1.yaml', 'docs/evidence/task03_atom4b_pre_git_import_receipt.json', 'docs/evidence/pre_git/task01/provider_cost_snapshot_v1.csv', 'docs/evidence/pre_git/task01/provider_smoke_spec_v1.yaml', 'catalog/assets/core.yaml', 'catalog/query_recipes.yaml', 'docs/evidence/pre_git/task02/bootstrap_check.py', 'docs/evidence/pre_git/task02/env_report.txt', 'docs/architecture/intents/ARCH-INTENT-001-hypothesis-factory-and-regime-aware-orchestration.md', 'tests/test_pre_git_import.py', 'catalog/schemas/asset_catalog.schema.json', 'docs/evidence/pre_git/task01/provider_decision_v1.md', 'docs/evidence/pre_git/task01/hypothesis_data_coverage_matrix_v1.md', 'docs/evidence/pre_git/task01/task_01_completion_record_v1.md', 'scripts/validate.ps1', 'docs/handoffs/latest.md', 'docs/evidence/pre_git/task02/TASK02_COMPLETION_SUMMARY.md', 'docs/evidence/pre_git/task02/tool_versions.json', 'docs/evidence/pre_git/task01/task_01_final_gap_audit_v1.md', 'catalog/catalog_manifest.yaml', 'catalog/assets/architecture.yaml', 'docs/evidence/pre_git/task02/CHECKSUMS_SHA256.txt', 'scripts/validate_baseline.py', 'scripts/validate_pre_git_import.py', 'tests/test_catalog.py', 'README.md', 'catalog/schemas/catalog_manifest.schema.json', 'docs/evidence/pre_git/task01/provider_account_checklist_v1.md', 'docs/evidence/pre_git/task01/reuse_candidate_registry.yaml', 'docs/evidence/pre_git/task01/CHECKSUMS_SHA256.txt', 'AGENTS.md', 'docs/evidence/pre_git/task01/data_option_tiers_v1.yaml', 'docs/evidence/pre_git/task02/task_02_workstation_bootstrap.md'}
WORK_ACCEPTANCE_SYNC_FILES = {
    "catalog/assets/core.yaml",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
}
WORK_ACCEPTANCE_COMMIT_COUNT = IMPORT_COMMIT_COUNT + 1
WORK_ACCEPTANCE_COMMIT_SUBJECT = "fix: validate Work acceptance checkpoint"
WORK_ACCEPTANCE_COMMIT_OID = "85ab008b762edacd335bba3d9776100bc52775ce"
ATOM5_COMMIT_COUNT = WORK_ACCEPTANCE_COMMIT_COUNT + 1
ATOM5_COMMIT_SUBJECT = "feat: add registry skeletons and generated navigation"
ATOM5_COMMIT_OID = "cd1465ea5de1fb33cee272422863b05d9459bd83"
ATOM5_MODIFIED_FILES = {
    "AGENTS.md",
    "catalog/catalog_manifest.yaml",
    "catalog/assets/core.yaml",
    "catalog/schemas/catalog_manifest.schema.json",
    "catalog/schemas/asset_catalog.schema.json",
    "scripts/validate_catalog.py",
    "scripts/validate.ps1",
    "scripts/validate_baseline.py",
    "tests/test_catalog.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
}
ATOM5_CREATED_FILES = {
    "catalog/assets/lifecycle.yaml",
    "catalog/schemas/lifecycle_registry.schema.json",
    "scripts/generate_navigation.py",
    "tests/test_lifecycle_registries.py",
    "tests/test_generate_navigation.py",
    "registries/research_cycles.yaml",
    "registries/hypotheses.yaml",
    "registries/global_trial_ledger.yaml",
    "registries/feature_catalog.yaml",
    "registries/holdout_consumption.yaml",
    "registries/strategies.yaml",
    "registries/bot_instances.yaml",
    "registries/reuse_candidates.yaml",
    "registries/decisions_negative_results.yaml",
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
}
ATOM5_CHANGED_FILES = ATOM5_MODIFIED_FILES | ATOM5_CREATED_FILES
ATOM5_EXPECTED_REPOSITORY_FILE_COUNT = (
    EXPECTED_REPOSITORY_FILE_COUNT + len(ATOM5_CREATED_FILES)
)
ATOM5_WORK_ACCEPTANCE_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
    "catalog/assets/core.yaml",
}
ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT = ATOM5_COMMIT_COUNT + 1
ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT = (
    "fix: validate Atom 5 Work acceptance"
)
ATOM5_WORK_ACCEPTANCE_COMMIT_OID = "9c021299b83804f5cb744c1d9dc9a8124de43f59"
ATOM7_LOCAL_CI_COMMIT_COUNT = ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT + 1
ATOM7_LOCAL_CI_COMMIT_SUBJECT = "ci: add pinned repository validation"
ATOM7_LOCAL_CI_COMMIT_OID = "4320b621f56bf86c8561be4a379dfc1d0e8937b2"
ATOM7_LOCAL_CI_MODIFIED_FILES = {
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "catalog/catalog_manifest.yaml",
    "catalog/query_recipes.yaml",
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "scripts/validate.ps1",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
}
ATOM7_LOCAL_CI_CREATED_FILES = {
    ".github/workflows/ci.yml",
    "scripts/validate_ci.py",
    "tests/test_ci.py",
}
ATOM7_LOCAL_CI_FILES = (
    ATOM7_LOCAL_CI_MODIFIED_FILES | ATOM7_LOCAL_CI_CREATED_FILES
)
ATOM7_EXPECTED_REPOSITORY_FILE_COUNT = (
    ATOM5_EXPECTED_REPOSITORY_FILE_COUNT + len(ATOM7_LOCAL_CI_CREATED_FILES)
)
ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT = ATOM7_LOCAL_CI_COMMIT_COUNT + 1
ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT = (
    "fix: validate repository publication states"
)
ATOM7_PRE_PUSH_REPAIR_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
}
EXPECTED_ORIGIN_URL = "https://github.com/lancerbeta/solana-alpha-lab.git"
EXPECTED_CI_ORIGIN_URLS = {
    EXPECTED_ORIGIN_URL,
    "https://github.com/lancerbeta/solana-alpha-lab",
}
EXPECTED_GITHUB_REPOSITORY = "lancerbeta/solana-alpha-lab"
EXPECTED_ORIGIN_FETCH_REFSPEC = "+refs/heads/*:refs/remotes/origin/*"
CODEX_CAPTURE_REF_PATTERN = re.compile(
    r"^refs/codex/turn-diffs/captures/[0-9]{13}/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/base$"
)
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


def command_lines(command: list[str]) -> tuple[int, tuple[str, ...]]:
    result = run(command)
    return result.returncode, tuple(
        line.strip() for line in result.stdout.splitlines() if line.strip()
    )


def origin_url_is_safe(url: str, *, github_actions: bool) -> bool:
    parsed = urlsplit(url)
    allowed_urls = EXPECTED_CI_ORIGIN_URLS if github_actions else {EXPECTED_ORIGIN_URL}
    return (
        url in allowed_urls
        and parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and not parsed.query
        and not parsed.fragment
    )


def policy_refs(all_refs: set[str]) -> set[str] | None:
    result = set()
    for ref in all_refs:
        if ref.startswith("refs/codex/"):
            if not CODEX_CAPTURE_REF_PATTERN.fullmatch(ref):
                return None
            continue
        result.add(ref)
    return result


def classify_git_topology(
    *,
    branch: str | None,
    head_oid: str,
    remotes: set[str],
    fetch_urls: tuple[str, ...],
    push_urls: tuple[str, ...],
    fetch_refspecs: tuple[str, ...],
    push_refspecs: tuple[str, ...],
    upstream: str | None,
    local_branches: set[str],
    remote_tracking_refs: set[str],
    tags: set[str],
    all_refs: set[str],
    github_actions: bool,
    github_repository: str | None,
    github_ref: str | None,
    github_sha: str | None,
) -> str:
    if tags or push_refspecs:
        return "INVALID_GIT_TOPOLOGY"
    repository_refs = policy_refs(all_refs)
    if repository_refs is None:
        return "INVALID_GIT_TOPOLOGY"

    if github_actions:
        origin_ok = (
            remotes == {"origin"}
            and len(fetch_urls) == 1
            and fetch_urls == push_urls
            and origin_url_is_safe(fetch_urls[0], github_actions=True)
            and fetch_refspecs == (EXPECTED_ORIGIN_FETCH_REFSPEC,)
        )
        refs_ok = (
            branch in {None, "main"}
            and local_branches <= {"main"}
            and remote_tracking_refs <= {"origin/main"}
            and repository_refs
            <= {"refs/heads/main", "refs/remotes/origin/main"}
        )
        upstream_ok = (
            (branch is None and upstream is None)
            or (branch == "main" and upstream in {None, "origin/main"})
        )
        context_ok = (
            github_repository == EXPECTED_GITHUB_REPOSITORY
            and github_ref == "refs/heads/main"
            and github_sha == head_oid
        )
        if origin_ok and refs_ok and upstream_ok and context_ok:
            return "GITHUB_ACTIONS_CHECKOUT"
        return "INVALID_GIT_TOPOLOGY"

    if branch != "main" or local_branches != {"main"}:
        return "INVALID_GIT_TOPOLOGY"

    if not remotes:
        if (
            not fetch_urls
            and not push_urls
            and not fetch_refspecs
            and upstream is None
            and not remote_tracking_refs
            and repository_refs == {"refs/heads/main"}
        ):
            return "PRE_REMOTE"
        return "INVALID_GIT_TOPOLOGY"

    origin_ok = (
        remotes == {"origin"}
        and fetch_urls == (EXPECTED_ORIGIN_URL,)
        and push_urls == (EXPECTED_ORIGIN_URL,)
        and origin_url_is_safe(fetch_urls[0], github_actions=False)
        and fetch_refspecs == (EXPECTED_ORIGIN_FETCH_REFSPEC,)
    )
    if not origin_ok:
        return "INVALID_GIT_TOPOLOGY"

    if (
        upstream is None
        and not remote_tracking_refs
        and repository_refs == {"refs/heads/main"}
    ):
        return "BOUND_PRE_PUSH"
    if (
        upstream == "origin/main"
        and remote_tracking_refs == {"origin/main"}
        and repository_refs
        == {"refs/heads/main", "refs/remotes/origin/main"}
    ):
        return "PUBLISHED_LOCAL"
    return "INVALID_GIT_TOPOLOGY"


def tree_files(treeish: str) -> set[str]:
    code, files = command_set(["git", "ls-tree", "-r", "--name-only", treeish])
    if code != 0:
        raise AssertionError(f"tree_inventory_read_failed:{treeish}")
    return files


def import_repository_files() -> set[str]:
    return tree_files(IMPORT_COMMIT_OID)


def work_acceptance_repository_files() -> set[str]:
    return tree_files(WORK_ACCEPTANCE_COMMIT_OID)


def atom5_repository_files() -> set[str]:
    return tree_files(ATOM5_COMMIT_OID)


def atom5_work_acceptance_repository_files() -> set[str]:
    return tree_files(ATOM5_WORK_ACCEPTANCE_COMMIT_OID)


def atom7_repository_files() -> set[str]:
    return (
        atom5_work_acceptance_repository_files()
        | ATOM7_LOCAL_CI_CREATED_FILES
    )


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
    result = run(["git","ls-tree","-r","-z",IMPORT_COMMIT_OID], binary=True)
    if result.returncode != 0: raise AssertionError("head_tree_read_failed")
    return parse_tree_entries(result.stdout)


def blob_bytes(state: str, path: str) -> bytes:
    if state == "PRE_GIT_IMPORT_STAGED":
        reference = f":{path}"
    else:
        reference = f"{IMPORT_COMMIT_OID}:{path}"
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


def classify_state(
    *,
    head_oid: str,
    commit_count: int,
    parent_oid: str | None,
    tracked: set[str],
    staged: set[str],
    untracked: set[str],
    unstaged: set[str],
    commit_subject: str | None = None,
    commit_changed: set[str] | None = None,
) -> str:
    import_files = import_repository_files()
    work_files = work_acceptance_repository_files()
    atom5_files = atom5_repository_files()
    atom5_acceptance_files = atom5_work_acceptance_repository_files()
    atom7_files = atom7_repository_files()
    if (
        head_oid == BASE_COMMIT_OID
        and commit_count == BASE_COMMIT_COUNT
        and parent_oid == BASE_PARENT_OID
        and tracked == import_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and staged == EXPECTED_CHANGED_FILES
        and not untracked
        and not unstaged
    ):
        return "PRE_GIT_IMPORT_STAGED"
    if (
        head_oid == IMPORT_COMMIT_OID
        and commit_count == IMPORT_COMMIT_COUNT
        and parent_oid == BASE_COMMIT_OID
        and tracked == import_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == RECOMMENDED_COMMIT_MESSAGE
        and commit_changed == EXPECTED_CHANGED_FILES
    ):
        return "PRE_GIT_IMPORT_COMMITTED"
    if (
        head_oid == IMPORT_COMMIT_OID
        and commit_count == IMPORT_COMMIT_COUNT
        and parent_oid == BASE_COMMIT_OID
        and tracked == work_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and staged == WORK_ACCEPTANCE_SYNC_FILES
        and not unstaged
        and not untracked
    ):
        return "WORK_ACCEPTANCE_SYNC_STAGED"
    if (
        head_oid == WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == IMPORT_COMMIT_OID
        and tracked == work_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == WORK_ACCEPTANCE_COMMIT_SUBJECT
        and commit_changed == WORK_ACCEPTANCE_SYNC_FILES
    ):
        return "WORK_ACCEPTANCE_SYNC_COMMITTED"
    if (
        head_oid == WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == IMPORT_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM5_CHANGED_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM5_REGISTRIES_NAVIGATION_STAGED"
    if (
        head_oid == ATOM5_COMMIT_OID
        and commit_count == ATOM5_COMMIT_COUNT
        and parent_oid == WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM5_COMMIT_SUBJECT
        and commit_changed == ATOM5_CHANGED_FILES
    ):
        return "ATOM5_REGISTRIES_NAVIGATION_COMMITTED"
    if (
        head_oid == ATOM5_COMMIT_OID
        and commit_count == ATOM5_COMMIT_COUNT
        and parent_oid == WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM5_WORK_ACCEPTANCE_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM5_WORK_ACCEPTANCE_STAGED"
    if (
        head_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and
        commit_count == ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == ATOM5_COMMIT_OID
        and tracked == atom5_acceptance_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT
        and commit_changed == ATOM5_WORK_ACCEPTANCE_FILES
    ):
        return "ATOM5_WORK_ACCEPTANCE_COMMITTED"
    if (
        head_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == ATOM5_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_LOCAL_CI_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM7_LOCAL_CI_CANDIDATE_STAGED"
    if (
        commit_count == ATOM7_LOCAL_CI_COMMIT_COUNT
        and parent_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_LOCAL_CI_COMMIT_SUBJECT
        and commit_changed == ATOM7_LOCAL_CI_FILES
    ):
        return "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED"
    if (
        head_oid == ATOM7_LOCAL_CI_COMMIT_OID
        and commit_count == ATOM7_LOCAL_CI_COMMIT_COUNT
        and parent_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_PRE_PUSH_REPAIR_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_LOCAL_CI_COMMIT_SUBJECT
        and commit_changed == ATOM7_LOCAL_CI_FILES
    ):
        return "ATOM7_PRE_PUSH_REPAIR_STAGED"
    if (
        commit_count == ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_LOCAL_CI_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_PRE_PUSH_REPAIR_FILES
    ):
        return "ATOM7_PRE_PUSH_REPAIR_COMMITTED"
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


def validate_work_acceptance_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(WORK_ACCEPTANCE_SYNC_FILES),
        ]
    )
    assert_check(
        "work_acceptance_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom5_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM5_CHANGED_FILES),
        ]
    )
    assert_check(
        "atom5_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom5_work_acceptance_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM5_WORK_ACCEPTANCE_FILES),
        ]
    )
    assert_check(
        "atom5_work_acceptance_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_local_ci_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_LOCAL_CI_FILES),
        ]
    )
    assert_check(
        "atom7_local_ci_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_pre_push_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_PRE_PUSH_REPAIR_FILES),
        ]
    )
    assert_check(
        "atom7_pre_push_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate() -> None:
    github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    branch_result = run(["git", "symbolic-ref", "--short", "HEAD"])
    branch_name = (
        branch_result.stdout.strip() if branch_result.returncode == 0 else None
    )
    assert_check(
        "branch_main_or_ci_detached",
        (branch_result.returncode == 0 and branch_name == "main")
        or (github_actions and branch_result.returncode != 0),
    )
    head = run(["git","rev-parse","HEAD"]); assert_check("head_read", head.returncode == 0); head_oid = head.stdout.strip()
    count = run(["git","rev-list","--count","HEAD"]); assert_check("commit_count_read", count.returncode == 0); commit_count = int(count.stdout.strip())
    parent_oid = None
    if commit_count >= 2:
        parent = run(["git","rev-parse","HEAD^"]); assert_check("parent_read", parent.returncode == 0); parent_oid = parent.stdout.strip()
    remote_code, remotes = command_set(["git", "remote"])
    fetch_url_code = push_url_code = fetch_refspec_code = push_refspec_code = 0
    fetch_urls: tuple[str, ...] = ()
    push_urls: tuple[str, ...] = ()
    fetch_refspecs: tuple[str, ...] = ()
    push_refspecs: tuple[str, ...] = ()
    if "origin" in remotes:
        fetch_url_code, fetch_urls = command_lines(
            ["git", "remote", "get-url", "--all", "origin"]
        )
        push_url_code, push_urls = command_lines(
            ["git", "remote", "get-url", "--push", "--all", "origin"]
        )
        fetch_refspec_code, fetch_refspecs = command_lines(
            ["git", "config", "--get-all", "remote.origin.fetch"]
        )
        push_refspec_code, push_refspecs = command_lines(
            ["git", "config", "--get-all", "remote.origin.push"]
        )
    upstream_result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    upstream = (
        upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    )
    local_branch_code, local_branches = command_set(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"]
    )
    remote_ref_code, remote_tracking_refs = command_set(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes"]
    )
    tag_code, tags = command_set(["git", "tag", "--list"])
    all_ref_code, all_refs = command_set(
        ["git", "for-each-ref", "--format=%(refname)"]
    )
    tracked_code, tracked = command_set(["git","ls-files"])
    staged_code, staged = command_set(["git","diff","--cached","--name-only"])
    untracked_code, untracked = command_set(["git","ls-files","--others","--exclude-standard"])
    unstaged_code, unstaged = command_set(["git","diff","--name-only"])
    subject = run(["git","show","-s","--format=%s","HEAD"])
    changed_code, commit_changed = command_set(["git","diff-tree","--no-commit-id","--name-only","-r","HEAD"])
    inventory_codes = (
        remote_code,
        fetch_url_code,
        push_url_code,
        fetch_refspec_code,
        local_branch_code,
        remote_ref_code,
        tag_code,
        all_ref_code,
        tracked_code,
        staged_code,
        untracked_code,
        unstaged_code,
        subject.returncode,
        changed_code,
    )
    assert_check(
        "git_inventory_commands",
        all(code == 0 for code in inventory_codes)
        and push_refspec_code in {0, 1}
        and (upstream_result.returncode == 0 or not upstream_result.stdout.strip()),
    )
    topology = classify_git_topology(
        branch=branch_name,
        head_oid=head_oid,
        remotes=remotes,
        fetch_urls=fetch_urls,
        push_urls=push_urls,
        fetch_refspecs=fetch_refspecs,
        push_refspecs=push_refspecs,
        upstream=upstream,
        local_branches=local_branches,
        remote_tracking_refs=remote_tracking_refs,
        tags=tags,
        all_refs=all_refs,
        github_actions=github_actions,
        github_repository=os.environ.get("GITHUB_REPOSITORY"),
        github_ref=os.environ.get("GITHUB_REF"),
        github_sha=os.environ.get("GITHUB_SHA"),
    )
    assert_check(
        "repository_topology",
        topology != "INVALID_GIT_TOPOLOGY",
        topology,
    )
    state = classify_state(
        head_oid=head_oid,
        commit_count=commit_count,
        parent_oid=parent_oid,
        tracked=tracked,
        staged=staged,
        untracked=untracked,
        unstaged=unstaged,
        commit_subject=subject.stdout.strip(),
        commit_changed=commit_changed,
    )
    valid_states = {
        "PRE_GIT_IMPORT_STAGED",
        "PRE_GIT_IMPORT_COMMITTED",
        "WORK_ACCEPTANCE_SYNC_STAGED",
        "WORK_ACCEPTANCE_SYNC_COMMITTED",
        "ATOM5_REGISTRIES_NAVIGATION_STAGED",
        "ATOM5_REGISTRIES_NAVIGATION_COMMITTED",
        "ATOM5_WORK_ACCEPTANCE_STAGED",
        "ATOM5_WORK_ACCEPTANCE_COMMITTED",
        "ATOM7_LOCAL_CI_CANDIDATE_STAGED",
        "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED",
        "ATOM7_PRE_PUSH_REPAIR_STAGED",
        "ATOM7_PRE_PUSH_REPAIR_COMMITTED",
    }
    assert_check("repository_state", state in valid_states, state)
    if state.startswith("ATOM7_"):
        expected_file_count = ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
    elif state.startswith("ATOM5_"):
        expected_file_count = ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
    else:
        expected_file_count = EXPECTED_REPOSITORY_FILE_COUNT
    assert_check("repository_file_count", len(repository_files()) == expected_file_count)
    if state == "PRE_GIT_IMPORT_COMMITTED":
        message = run(["git","log","-1","--pretty=%B"])
        assert_check("import_commit_message", message.returncode == 0 and message.stdout.strip() == RECOMMENDED_COMMIT_MESSAGE, message.stdout.strip())
    if state == "WORK_ACCEPTANCE_SYNC_COMMITTED":
        assert_check("work_acceptance_commit_contract", True)
    if state == "ATOM5_REGISTRIES_NAVIGATION_COMMITTED":
        assert_check("atom5_commit_contract", True)
    if state == "ATOM5_WORK_ACCEPTANCE_COMMITTED":
        assert_check("atom5_work_acceptance_commit_contract", True)
    if state == "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED":
        assert_check("atom7_local_ci_commit_contract", True)
    if state == "ATOM7_PRE_PUSH_REPAIR_COMMITTED":
        assert_check("atom7_pre_push_repair_commit_contract", True)
    assert_check("venv_present", (ROOT/".venv").is_dir())
    assert_check("runtime_exact", sys.version_info[:3] == EXPECTED_PYTHON)
    assert_check("runtime_is_venv", Path(sys.prefix).resolve() == (ROOT/".venv").resolve())
    assert_check("jsonschema_version", importlib.metadata.version("jsonschema") == EXPECTED_JSONSCHEMA)
    assert_check("pyyaml_version", importlib.metadata.version("PyYAML") == EXPECTED_PYYAML)
    with (ROOT/"pyproject.toml").open("rb") as handle: metadata = tomllib.load(handle)
    assert_check("dependency_contract", set(metadata["project"]["dependencies"]) == {f"PyYAML=={EXPECTED_PYYAML}",f"jsonschema=={EXPECTED_JSONSCHEMA}"})
    assert_check("uv_version_contract", metadata["tool"]["uv"].get("required-version") == "==0.11.29")
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
    assert_check(
        "source_inventory",
        set(source_entries(state)) == import_repository_files(),
    )
    assert_check("pre_commit_mode", source_entries(state)[".githooks/pre-commit"][0] == "100755")
    validate_eol(state); print("eol_checkout_contract: PASS")
    if state == "PRE_GIT_IMPORT_STAGED":
        validate_staged_style_policy()
    if state == "WORK_ACCEPTANCE_SYNC_STAGED":
        validate_work_acceptance_staged_style_policy()
    if state == "ATOM5_REGISTRIES_NAVIGATION_STAGED":
        validate_atom5_staged_style_policy()
    if state == "ATOM5_WORK_ACCEPTANCE_STAGED":
        validate_atom5_work_acceptance_staged_style_policy()
    if state == "ATOM7_LOCAL_CI_CANDIDATE_STAGED":
        validate_atom7_local_ci_staged_style_policy()
    if state == "ATOM7_PRE_PUSH_REPAIR_STAGED":
        validate_atom7_pre_push_repair_staged_style_policy()
    tests = run([sys.executable,"-B","-m","unittest","discover","-s","tests","-p","test_*.py"])
    if tests.stdout.strip(): print(tests.stdout.strip())
    if tests.stderr.strip(): print(tests.stderr.strip())
    assert_check("unit_tests", tests.returncode == 0)
    print(f"GIT_TOPOLOGY: {topology}")
    print(f"REPOSITORY_STATE: {state}")
    print("RESULT: PASS")


def main() -> int:
    print("=== TASK-03 REPOSITORY STATE VALIDATION ===")
    try: validate()
    except Exception as exc:
        print("RESULT: FAIL"); print(f"ERROR_TYPE: {type(exc).__name__}"); print(f"ERROR: {exc}"); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
