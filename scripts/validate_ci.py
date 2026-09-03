#!/usr/bin/env python3
"""Platform-neutral, fail-closed repository validation entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/ci.yml"
LOCK_PATH = ROOT / "uv.lock"
EXPECTED_PYTHON = (3, 13, 14)
EXPECTED_UV = "0.11.29"
CHECKOUT_PIN = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SETUP_UV_PIN = "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990"
LINUX_UV_CHECKSUM = "04f8b82f5d47f0512dcd32c67a4a6f16a0ea27c81537c338fd0ad6b23cebe829"
VALIDATION_COMMAND = "uv run --locked --managed-python python -B scripts/validate_ci.py"
DELIVERY_PREFLIGHT_COMMAND = (
    VALIDATION_COMMAND + " --tracked-only-delivery"
)
DELIVERY_PREFLIGHT_SCHEMA = (
    "solana-alpha-lab.tracked-only-delivery-preflight.v1"
)
# Work jobs restore the fixed 15-minute wall after sharding. Tracked-only
# delivery preflight still runs the full sequential suite locally and keeps a
# separate 25-minute cap; that is measurement headroom for the local full
# gate, not the claimed exact-head performance fix.
GITHUB_VALIDATE_TIMEOUT_MINUTES = 15
GITHUB_AGGREGATOR_TIMEOUT_MINUTES = 5
DELIVERY_PREFLIGHT_TIMEOUT_MINUTES = 25
DELIVERY_PREFLIGHT_TIMEOUT_SECONDS = DELIVERY_PREFLIGHT_TIMEOUT_MINUTES * 60
CI_TEST_SHARDS_PLAN = ROOT / "configs/ci_test_shards_v1.json"
EXECUTION_DOMAIN_MANIFEST = ROOT / "configs/execution_domain_v1.json"
EXECUTION_DOMAIN_COMMAND = (
    "uv run --locked --managed-python python -B "
    "scripts/run_ci_execution_domain.py "
    "--manifest configs/execution_domain_v1.json"
)
SHARD_RUN_COMMAND_TEMPLATE = (
    "uv run --locked --managed-python python -B scripts/run_ci_test_shard.py "
    "--index ${{{{ matrix.shard }}}} --count {shard_count} "
    "--plan configs/ci_test_shards_v1.json "
    "--reserved-manifest configs/execution_domain_v1.json"
)
CORE_ONLY_COMMAND = VALIDATION_COMMAND + " --core-only"
AGGREGATOR_DENY_SCRIPT = """python - <<'PY'
import os
import sys

required = {
    "validate-core": os.environ.get("CORE_RESULT", ""),
    "validate-execution": os.environ.get("EXECUTION_RESULT", ""),
    "validate-tests": os.environ.get("TESTS_RESULT", ""),
}
failed = {name: value for name, value in required.items() if value != "success"}
if failed:
    print("AGGREGATOR_DENY:" + ",".join(f"{k}={v}" for k, v in sorted(failed.items())))
    sys.exit(1)
print("AGGREGATOR_OK")
PY
"""

DELIVERY_PREFLIGHT_RECEIPT_DIR = ROOT / "local/delivery_preflight"
CI_OWNED_DELIVERY_COMMAND = VALIDATION_COMMAND + " --ci-owned-delivery"
CI_OWNED_DELIVERY_SCHEMA = "solana-alpha-lab.ci-owned-delivery-preflight.v1"
CI_OWNED_DELIVERY_PILOT_ID = "CTRL-CI-OWNED-DELIVERY-PILOT-V1"
CI_OWNED_DELIVERY_TIMEOUT_SECONDS = 120
CI_OWNED_FULL_VALIDATION_OWNER = "GITHUB_PR_EXACT_HEAD_CI"
CI_OWNED_INELIGIBLE_EXACT_PATHS = frozenset(
    {
        ".cursorignore",
        ".github/pull_request_template.md",
        ".python-version",
        "AGENTS.md",
        "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
        "docs/agent/GITHUB_BATON_PROTOCOL.md",
        "pyproject.toml",
        "uv.lock",
        "scripts/control_only_task_close_fast_path.py",
        "scripts/catalog_cli.py",
        "scripts/generate_navigation.py",
        "scripts/owner_attention_gate.py",
        "scripts/secret_scan.py",
        "scripts/validate.ps1",
        "scripts/validate_baseline.py",
        "scripts/validate_baton.py",
        "scripts/validate_ci.py",
        "tests/test_baseline.py",
        "tests/test_baton_repository_policy.py",
        "tests/test_ci.py",
        "tests/test_control_only_task_close_fast_path.py",
        "tests/test_generate_navigation.py",
        "tests/test_owner_attention_gate_policy.py",
        "tests/test_pre_git_import.py",
        "tests/test_project_sources_release_registry.py",
        "tests/test_secret_scan.py",
        "tests/test_task04_core_stack.py",
    }
)
CI_OWNED_INELIGIBLE_PREFIXES = (
    ".cursor/",
    ".github/",
    ".githooks/",
    "control/",
    "docs/agent/",
    "docs/tasks/CTRL-",
    "migrations/",
    "scripts/baton_",
    "scripts/validate_",
    "schemas/",
    "src/solana_alpha_lab/contracts/migration_",
    "src/solana_alpha_lab/contracts/schema_",
    "tests/test_baton_",
    "tests/test_validate_",
)
CI_OWNED_INELIGIBLE_CATALOG_SCHEMA_NAMES = frozenset(
    {
        "asset_catalog.schema.json",
        "catalog_manifest.schema.json",
        "lifecycle_registry.schema.json",
        "owner_attention_gate_v2.schema.json",
        "project_sources_release_registry.schema.json",
        "query_recipe.schema.json",
    }
)
CI_OWNED_CATALOG_SCHEMAS_PREFIX = "catalog/schemas/"
CI_OWNED_ELIGIBLE_PRODUCT_RESEARCH_DDL_PATHS = frozenset(
    {
        "schemas/research_memory_projection_v1.sql",
    }
)
CI_OWNED_ELIGIBLE_PRODUCT_CURSOR_COMMAND_PATHS = frozenset(
    {
        ".cursor/commands/hypothesis-forge.md",
        ".cursor/commands/independent-hypothesis-critic.md",
    }
)
SANDBOX_UV_CACHE_MARKER = "cursor-sandbox-cache"
DELIVERY_SKIP_CALL = re.compile(
    r"(?:\.skipTest\s*\(|@(?:unittest\.)?skip(?:If|Unless)?\s*\("
    r"|pytest\.(?:skip|importorskip)\s*\()"
)
DELIVERY_SKIP_PROOF = re.compile(
    r"DELIVERY_PREFLIGHT_NONCRITICAL_SKIP:\s*([A-Za-z0-9_./-]+)"
)
DELIVERY_SKIP_PROOF_PREFIXES = ("docs/decisions/", "docs/evidence/")


class CiValidationError(RuntimeError):
    """Fail-closed CI or repository contract violation."""


def tracked_only_clone_environment(
    source: dict[str, str] | None = None,
) -> dict[str, str]:
    """Isolate tracked-only uv from Cursor sandbox caches; copy if hardlink cannot work."""

    environment = dict(os.environ if source is None else source)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["UV_MANAGED_PYTHON"] = "1"
    environment["UV_NO_ENV_FILE"] = "1"
    environment["UV_OFFLINE"] = "1"
    environment["SMIAL_TRACKED_ONLY_DELIVERY"] = "1"
    # uv falls back from hardlink to copy on cross-device/sandbox failure; do not skip the gate.
    environment["UV_LINK_MODE"] = "hardlink"
    environment.pop("VIRTUAL_ENV", None)
    cache_dir = environment.get("UV_CACHE_DIR", "")
    if SANDBOX_UV_CACHE_MARKER in cache_dir.replace("\\", "/").casefold():
        environment.pop("UV_CACHE_DIR", None)
    return environment


def ci_owned_ineligible_catalog_schema(path: str) -> bool:
    """Keep catalog/harness/validator schemas ineligible; product/task schemas pass."""

    if not path.startswith(CI_OWNED_CATALOG_SCHEMAS_PREFIX):
        return False
    name = path[len(CI_OWNED_CATALOG_SCHEMAS_PREFIX) :]
    if not name or "/" in name:
        return True
    if name in CI_OWNED_INELIGIBLE_CATALOG_SCHEMA_NAMES:
        return True
    return name.startswith("delivery_harness") and name.endswith(".schema.json")


def ci_owned_eligible_product_research_ddl(path: str) -> bool:
    """Admit named product research-memory DDL; keep blanket schemas/ ineligible."""

    return path in CI_OWNED_ELIGIBLE_PRODUCT_RESEARCH_DDL_PATHS


def ci_owned_eligible_product_cursor_command(path: str) -> bool:
    """Admit named product slash commands; keep blanket .cursor/ ineligible."""

    return path in CI_OWNED_ELIGIBLE_PRODUCT_CURSOR_COMMAND_PATHS


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def git_text(
    args: list[str],
    *,
    cwd: Path = ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str:
    execute = runner or subprocess.run
    completed = execute(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        suffix = detail[-1] if detail else "unknown"
        raise CiValidationError(f"git_command_failed:{args[0]}:{suffix}")
    return completed.stdout.strip()


def normalize_tracked_only_checkout(*, branch: str, checkout: Path) -> None:
    """Normalize only the temporary clone to the attached-main repository contract."""

    remote_refs = git_text(
        ["for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
        cwd=checkout,
    ).splitlines()
    if branch != "main":
        git_text(["branch", "-m", "main"], cwd=checkout)
    git_text(["branch", "--set-upstream-to=origin/main", "main"], cwd=checkout)
    for ref in remote_refs:
        if ref != "refs/remotes/origin/main":
            git_text(["update-ref", "-d", ref], cwd=checkout)


def parse_added_test_hunks(diff_text: str) -> list[tuple[str, list[str]]]:
    hunks: list[tuple[str, list[str]]] = []
    path: str | None = None
    additions: list[str] | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            additions = None
        elif line.startswith("@@"):
            if path and path.startswith("tests/") and path.endswith(".py"):
                additions = []
                hunks.append((path, additions))
            else:
                additions = None
        elif additions is not None and line.startswith("+"):
            additions.append(line[1:])
    return hunks


def validate_new_test_skip_policy(
    diff_text: str,
    *,
    proof_exists: Callable[[str], bool],
) -> list[dict[str, str]]:
    """Reject newly added skips unless a tracked non-critical proof is adjacent."""
    waivers: list[dict[str, str]] = []
    violations: list[str] = []
    for path, additions in parse_added_test_hunks(diff_text):
        for index, line in enumerate(additions):
            if not DELIVERY_SKIP_CALL.search(line):
                continue
            window = "\n".join(
                additions[max(0, index - 3) : min(len(additions), index + 4)]
            )
            match = DELIVERY_SKIP_PROOF.search(window)
            if not match:
                violations.append(f"{path}:{index + 1}:new_skip_without_proof")
                continue
            proof = match.group(1)
            if (
                proof.startswith("/")
                or "\\" in proof
                or ".." in Path(proof).parts
                or not proof.startswith(DELIVERY_SKIP_PROOF_PREFIXES)
                or not proof_exists(proof)
            ):
                violations.append(f"{path}:{index + 1}:invalid_skip_proof:{proof}")
                continue
            waivers.append({"test_path": path, "proof_path": proof})
    if violations:
        raise CiValidationError(
            "delivery_new_skip_policy_failed:" + ",".join(sorted(violations))
        )
    return waivers


def decode_delivery_output(output: bytes | None) -> str:
    """Decode child-process output without losing a successful full-gate result."""

    if output is None:
        return ""
    return output.decode("utf-8", errors="replace")


def emit_delivery_output(output: str, *, stream: Any = sys.stdout) -> None:
    """Emit diagnostics without letting a narrow Windows console break the gate."""

    text = output.strip()
    if not text:
        return
    encoding = getattr(stream, "encoding", None) or "utf-8"
    safe = text.encode(encoding, errors="backslashreplace").decode(encoding)
    stream.write(safe + "\n")


def parse_validation_summary(output: str) -> dict[str, Any]:
    test_counts = [int(value) for value in re.findall(r"Ran (\d+) tests?", output)]
    skip_counts = [
        int(value) for value in re.findall(r"OK \(skipped=(\d+)\)", output)
    ]
    missing_markers = (
        "ignored",
        "local",
        "raw",
        "excluded",
        "unavailable",
        "not present",
    )
    reasons = {
        match.strip()
        for match in re.findall(r"skipped ['\"]([^'\"]+)['\"]", output)
        if any(marker in match.lower() for marker in missing_markers)
    }
    diagnostic_patterns = (
        r"(?m)^(?:FAIL|ERROR): .+$",
        r"(?m)^(?:AssertionError|[A-Za-z][A-Za-z0-9_]*(?:Error|Exception)): .+$",
        r"(?m)^FAILED \(.+\)$",
    )
    failure_diagnostics: list[str] = []
    for pattern in diagnostic_patterns:
        for value in re.findall(pattern, output):
            normalized = " ".join(value.strip().split())[:500]
            if normalized and normalized not in failure_diagnostics:
                failure_diagnostics.append(normalized)
            if len(failure_diagnostics) == 20:
                break
        if len(failure_diagnostics) == 20:
            break
    return {
        "tests_run": max(test_counts) if test_counts else None,
        "skipped": max(skip_counts) if skip_counts else 0,
        "pass_labels": len(re.findall(r"(?m)^[-A-Z0-9_ ]+: PASS$", output)),
        "missing_local_inputs": sorted(reasons),
        "failure_diagnostics": failure_diagnostics,
    }


def write_delivery_receipt(
    payload: dict[str, Any],
    candidate: str,
    *,
    suffix: str = "",
) -> Path:
    DELIVERY_PREFLIGHT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = DELIVERY_PREFLIGHT_RECEIPT_DIR / f"{candidate}{suffix}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def validate_ci_owned_delivery_eligibility(
    changed_paths: list[str],
) -> list[str]:
    """Admit only objectively bounded candidates; ambiguity uses the legacy gate."""

    normalized: list[str] = []
    violations: list[str] = []
    for raw_path in changed_paths:
        path = raw_path.replace("\\", "/")
        parts = Path(path).parts
        if (
            not path
            or path.startswith("/")
            or path.startswith("../")
            or Path(path).is_absolute()
            or re.match(r"^[A-Za-z]:/", path) is not None
            or ".." in parts
        ):
            violations.append(f"unsafe:{raw_path}")
            continue
        normalized.append(path)
        if ci_owned_eligible_product_research_ddl(path):
            continue
        if ci_owned_eligible_product_cursor_command(path):
            continue
        if (
            path in CI_OWNED_INELIGIBLE_EXACT_PATHS
            or path.startswith(CI_OWNED_INELIGIBLE_PREFIXES)
            or ci_owned_ineligible_catalog_schema(path)
        ):
            violations.append(path)
    if not normalized:
        violations.append("no_changed_paths")
    if violations:
        raise CiValidationError(
            "ci_owned_delivery_ineligible_paths:" + ",".join(sorted(violations))
        )
    return normalized


def run_tracked_only_delivery_preflight(*, base_ref: str = "origin/main") -> None:
    started = time.monotonic()
    candidate = git_text(["rev-parse", "HEAD"])
    tree = git_text(["show", "-s", "--format=%T", candidate])
    branch = git_text(["symbolic-ref", "--quiet", "--short", "HEAD"])
    tracked_dirty = git_text(["status", "--porcelain=v1", "--untracked-files=no"])
    if tracked_dirty:
        raise CiValidationError("delivery_candidate_has_tracked_changes")
    base_commit = git_text(["merge-base", base_ref, candidate])
    tracked_count = len(
        git_text(["ls-tree", "-r", "--name-only", candidate]).splitlines()
    )
    origin_url = git_text(["remote", "get-url", "origin"])
    diff_text = git_text(
        ["diff", "--unified=3", f"{base_commit}..{candidate}", "--", "tests"]
    )

    def proof_exists(path: str) -> bool:
        completed = subprocess.run(
            ["git", "cat-file", "-e", f"{candidate}:{path}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,
        )
        return completed.returncode == 0

    waivers = validate_new_test_skip_policy(diff_text, proof_exists=proof_exists)
    status = "FAIL"
    checkout_removed = False
    summary: dict[str, Any] = {
        "tests_run": None,
        "skipped": None,
        "pass_labels": 0,
        "missing_local_inputs": [],
        "failure_diagnostics": [],
    }
    error: str | None = None
    temporary_root: Path | None = None
    exit_code: int | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="smial-delivery-preflight-") as tmp:
            temporary_root = Path(tmp)
            checkout = temporary_root / "checkout"
            clone = subprocess.run(
                [
                    "git",
                    "clone",
                    "--no-local",
                    "--branch",
                    branch,
                    str(ROOT),
                    str(checkout),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
            )
            if clone.returncode != 0:
                raise CiValidationError("delivery_tracked_clone_failed")
            git_text(["remote", "set-url", "origin", origin_url], cwd=checkout)
            git_text(
                ["update-ref", "refs/remotes/origin/main", base_commit],
                cwd=checkout,
            )
            normalize_tracked_only_checkout(branch=branch, checkout=checkout)
            git_text(
                [
                    "symbolic-ref",
                    "refs/remotes/origin/HEAD",
                    "refs/remotes/origin/main",
                ],
                cwd=checkout,
            )
            git_text(["config", "--local", "core.hooksPath", ".githooks"], cwd=checkout)
            observed_commit = git_text(["rev-parse", "HEAD"], cwd=checkout)
            observed_tree = git_text(["show", "-s", "--format=%T", "HEAD"], cwd=checkout)
            if observed_commit != candidate or observed_tree != tree:
                raise CiValidationError("delivery_tracked_clone_identity_mismatch")
            environment = tracked_only_clone_environment()
            try:
                completed = subprocess.run(
                    VALIDATION_COMMAND.split(),
                    cwd=checkout,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    shell=False,
                    timeout=DELIVERY_PREFLIGHT_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise CiValidationError("delivery_full_gate_timeout") from exc
            exit_code = completed.returncode
            output = (
                decode_delivery_output(completed.stdout)
                + "\n"
                + decode_delivery_output(completed.stderr)
            )
            emit_delivery_output(output)
            summary = parse_validation_summary(output)
            if completed.returncode != 0:
                raise CiValidationError(
                    f"delivery_full_gate_failed:{completed.returncode}"
                )
            status = "PASS"
        checkout_removed = temporary_root is not None and not temporary_root.exists()
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        if temporary_root is not None:
            checkout_removed = not temporary_root.exists()
        elapsed = round(time.monotonic() - started, 3)
        payload = {
            "schema": DELIVERY_PREFLIGHT_SCHEMA,
            "status": status,
            "observed_at": utc_now(),
            "candidate": {
                "branch": branch,
                "commit": candidate,
                "tree": tree,
                "base_ref": base_ref,
                "base_commit": base_commit,
                "tracked_file_count": tracked_count,
                "tracked_worktree_clean": True,
                "untracked_or_ignored_inputs_copied": False,
            },
            "gate": {
                "command": VALIDATION_COMMAND,
                "exit_code": exit_code,
                "timeout_seconds": DELIVERY_PREFLIGHT_TIMEOUT_SECONDS,
                "wall_seconds": elapsed,
                **summary,
            },
            "new_skip_policy": {
                "status": "PASS",
                "tracked_noncritical_waivers": waivers,
            },
            "cleanup": {"temporary_checkout_removed": checkout_removed},
            "network": {
                "repository_clone": "LOCAL_NO_LOCAL_OBJECT_COPY",
                "uv_offline": True,
            },
            "error": error,
        }
        receipt = write_delivery_receipt(payload, candidate)
        print(f"DELIVERY_PREFLIGHT_RECEIPT: {receipt.relative_to(ROOT).as_posix()}")
    print("TRACKED_ONLY_DELIVERY_PREFLIGHT: PASS")


def validate_python_version(version: tuple[int, int, int]) -> None:
    if version != EXPECTED_PYTHON:
        raise CiValidationError(f"python_version_mismatch:{version}")


def parse_uv_version(text: str) -> str:
    match = re.match(r"^uv\s+(\d+\.\d+\.\d+)(?:\s|$)", text.strip())
    if not match:
        raise CiValidationError("uv_version_unparseable")
    return match.group(1)


def validate_uv_version(text: str) -> None:
    observed = parse_uv_version(text)
    if observed != EXPECTED_UV:
        raise CiValidationError(f"uv_version_mismatch:{observed}")


def validate_project_contract(document: dict[str, Any]) -> None:
    if document["tool"]["uv"].get("required-version") != f"=={EXPECTED_UV}":
        raise CiValidationError("uv_required_version_contract_mismatch")
    if document["tool"]["solana-alpha-lab"].get("exact_python_pin") != ".".join(
        map(str, EXPECTED_PYTHON)
    ):
        raise CiValidationError("python_pin_contract_mismatch")


def assert_lock_unchanged(before: bytes, after: bytes) -> None:
    if before != after:
        raise CiValidationError("uv_lock_mutated")


def load_shard_plan() -> dict[str, Any]:
    if not CI_TEST_SHARDS_PLAN.is_file():
        raise CiValidationError("ci_test_shards_plan_missing")
    try:
        document = json.loads(CI_TEST_SHARDS_PLAN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CiValidationError("ci_test_shards_plan_invalid_json") from exc
    if not isinstance(document, dict):
        raise CiValidationError("ci_test_shards_plan_not_object")
    count = document.get("shard_count")
    shards = document.get("shards")
    if document.get("schema") != "smial.ci-test-shards.v1":
        raise CiValidationError("ci_test_shards_plan_schema_mismatch")
    if not isinstance(count, int) or count < 3 or count > 4:
        raise CiValidationError("ci_test_shards_plan_count_invalid")
    if not isinstance(shards, list) or len(shards) != count:
        raise CiValidationError("ci_test_shards_plan_shards_invalid")
    seen: set[str] = set()
    duplicates: set[str] = set()
    for shard in shards:
        if not isinstance(shard, list):
            raise CiValidationError("ci_test_shards_plan_shards_invalid")
        for path in shard:
            key = str(path).replace("\\", "/")
            if key in seen:
                duplicates.add(key)
            seen.add(key)
    if duplicates:
        raise CiValidationError("ci_test_shards_plan_duplicate_modules")
    if not seen:
        raise CiValidationError("ci_test_shards_plan_empty")
    if EXECUTION_DOMAIN_MANIFEST.is_file():
        try:
            manifest = json.loads(EXECUTION_DOMAIN_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CiValidationError("execution_domain_manifest_invalid_json") from exc
        reserved = {
            str(path).replace("\\", "/")
            for path in (manifest.get("required_fast_test_modules") or [])
        }
        overlap = sorted(seen & reserved)
        if overlap:
            raise CiValidationError(
                "ci_test_shards_plan_execution_overlap:" + ",".join(overlap[:20])
            )
    return document


def setup_steps(*, validate_command: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "Check out repository",
            "uses": CHECKOUT_PIN,
            "with": {
                "persist-credentials": "false",
                "fetch-depth": "0",
            },
        },
        {
            "name": "Install pinned uv and Python",
            "uses": SETUP_UV_PIN,
            "with": {
                "version": EXPECTED_UV,
                "checksum": LINUX_UV_CHECKSUM,
                "python-version": ".".join(map(str, EXPECTED_PYTHON)),
                "enable-cache": "false",
            },
        },
        {
            "name": "Configure local hooks",
            "run": "git config --local core.hooksPath .githooks",
        },
        {
            "name": "Validate repository",
            "run": validate_command,
        },
    ]


def expected_workflow() -> dict[str, Any]:
    plan = load_shard_plan()
    shard_count = plan["shard_count"]
    shard_values = [str(index) for index in range(shard_count)]
    shard_command = SHARD_RUN_COMMAND_TEMPLATE.format(shard_count=shard_count)
    return {
        "name": "Repository validation",
        "on": {
            "workflow_dispatch": "",
            "pull_request": {"branches": ["main"]},
            "push": {"branches": ["main"]},
        },
        "permissions": {"contents": "read"},
        "concurrency": {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": "true",
        },
        "jobs": {
            "validate-core": {
                "runs-on": "ubuntu-24.04",
                "timeout-minutes": str(GITHUB_VALIDATE_TIMEOUT_MINUTES),
                "env": {
                    "UV_NO_ENV_FILE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "steps": setup_steps(validate_command=CORE_ONLY_COMMAND),
            },
            "validate-execution": {
                "runs-on": "ubuntu-24.04",
                "timeout-minutes": str(GITHUB_VALIDATE_TIMEOUT_MINUTES),
                "needs": ["validate-core"],
                "env": {
                    "UV_NO_ENV_FILE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "steps": setup_steps(validate_command=EXECUTION_DOMAIN_COMMAND),
            },
            "validate-tests": {
                "runs-on": "ubuntu-24.04",
                "timeout-minutes": str(GITHUB_VALIDATE_TIMEOUT_MINUTES),
                "env": {
                    "UV_NO_ENV_FILE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "strategy": {
                    "fail-fast": "false",
                    "max-parallel": str(shard_count),
                    "matrix": {
                        "shard": shard_values,
                    },
                },
                "steps": setup_steps(validate_command=shard_command),
            },
            "validate": {
                "if": "${{ always() }}",
                "needs": ["validate-core", "validate-execution", "validate-tests"],
                "runs-on": "ubuntu-24.04",
                "timeout-minutes": str(GITHUB_AGGREGATOR_TIMEOUT_MINUTES),
                "env": {
                    "CORE_RESULT": "${{ needs.validate-core.result }}",
                    "EXECUTION_RESULT": "${{ needs.validate-execution.result }}",
                    "TESTS_RESULT": "${{ needs.validate-tests.result }}",
                },
                "steps": [
                    {
                        "name": "Deny non-success core or shard results",
                        "run": AGGREGATOR_DENY_SCRIPT,
                    }
                ],
            },
        },
    }


def validate_workflow_text(text: str) -> None:
    lowered = text.lower()
    forbidden = (
        "secrets.",
        "pull_request_target",
        "id-token:",
        "actions/cache@",
        "actions/upload-artifact@",
        "actions/download-artifact@",
    )
    for marker in forbidden:
        if marker in lowered:
            raise CiValidationError(f"forbidden_workflow_marker:{marker}")

    try:
        document = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        raise CiValidationError("workflow_yaml_invalid") from exc
    if document != expected_workflow():
        raise CiValidationError("workflow_exact_contract_mismatch")

    uses = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", text)
    expected_uses = [
        CHECKOUT_PIN,
        SETUP_UV_PIN,
        CHECKOUT_PIN,
        SETUP_UV_PIN,
        CHECKOUT_PIN,
        SETUP_UV_PIN,
    ]
    if uses != expected_uses:
        raise CiValidationError("workflow_action_set_mismatch")
    if any(not re.search(r"@[0-9a-f]{40}$", reference) for reference in uses):
        raise CiValidationError("workflow_action_not_immutable")
    if "if: ${{ always() }}" not in text and "if: always()" not in text:
        raise CiValidationError("workflow_aggregator_missing_always")
    if "fail-fast: false" not in text:
        raise CiValidationError("workflow_fail_fast_required")


def child_commands(*, policy_only_baseline: bool = False) -> list[tuple[str, list[str]]]:
    python = sys.executable
    baseline = [python, "-B", "scripts/validate_baseline.py"]
    if policy_only_baseline:
        baseline.append("--policy-only")
    return [
        (
            "SECRET_REJECTION",
            [python, "-B", "scripts/secret_scan.py", "--self-test", "--scan-repository"],
        ),
        ("BATON_VALIDATION", [python, "-B", "scripts/validate_baton.py"]),
        ("CATALOG_VALIDATION", [python, "-B", "scripts/validate_catalog.py"]),
        ("FACTORY_STATIC", [python, "-B", "scripts/validate_factory_static.py"]),
        (
            "CATALOG_RESOLUTION",
            [
                python,
                "-B",
                "scripts/catalog_cli.py",
                "resolve-asset",
                "CATALOG-ROOT-001",
                "--json",
            ],
        ),
        (
            "GENERATED_NAVIGATION",
            [python, "-B", "scripts/generate_navigation.py", "--check"],
        ),
        (
            "PRE_GIT_IMPORT_VALIDATION",
            [python, "-B", "scripts/validate_pre_git_import.py"],
        ),
        (
            "EXECUTION_DOMAIN_BOUNDARY",
            [
                python,
                "-B",
                "scripts/validate_execution_domain.py",
                "--manifest",
                "configs/execution_domain_v1.json",
            ],
        ),
        ("TASK04_ARCHITECTURE", [python, "-B", "scripts/validate_task04.py"]),
        ("REPOSITORY_POLICY", baseline),
        ("PRE_COMMIT_HOOK", ["git", "config", "--local", "--get", "core.hooksPath"]),
    ]



def ci_owned_child_commands() -> list[tuple[str, list[str]]]:
    """Focused local controls; GitHub PR CI owns full repository discovery."""

    focused: list[tuple[str, list[str]]] = []
    for label, command in child_commands():
        if label == "REPOSITORY_POLICY":
            continue
        if label == "BATON_VALIDATION":
            command = [*command, "--focused"]
        focused.append((label, command))
    return focused


def run_checked(
    label: str,
    command: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    timeout_seconds: float | None = None,
    offline: bool = False,
) -> subprocess.CompletedProcess[str]:
    execute = runner or subprocess.run
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["UV_MANAGED_PYTHON"] = "1"
    if offline:
        environment["UV_OFFLINE"] = "1"
        environment["UV_NO_ENV_FILE"] = "1"
    arguments: dict[str, Any] = {
        "cwd": ROOT,
        "env": environment,
        "text": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "check": False,
        "shell": False,
    }
    if timeout_seconds is not None:
        arguments["timeout"] = max(0.001, timeout_seconds)
    try:
        completed = execute(command, **arguments)
    except subprocess.TimeoutExpired as exc:
        raise CiValidationError(f"{label.lower()}_timeout") from exc
    combined = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part and part.strip()
    )
    if completed.returncode != 0:
        from ci_fail_closed_messages import derived_hash_drift_summary, is_derived_hash_drift

        if is_derived_hash_drift(combined):
            print(derived_hash_drift_summary())
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip())
        raise CiValidationError(f"{label.lower()}_failed:{completed.returncode}")
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    print(f"{label}: PASS")
    return completed


def ci_owned_remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CiValidationError("ci_owned_delivery_focused_gate_timeout")
    return remaining


def run_ci_owned_focused_gate(*, deadline: float) -> list[str]:
    validate_python_version(sys.version_info[:3])
    print("PYTHON_RUNTIME: PASS")

    uv = run_checked(
        "UV_RUNTIME",
        ["uv", "--version"],
        timeout_seconds=ci_owned_remaining_seconds(deadline),
        offline=True,
    )
    validate_uv_version(uv.stdout + uv.stderr)

    with (ROOT / "pyproject.toml").open("rb") as handle:
        validate_project_contract(tomllib.load(handle))
    print("EXECUTABLE_CONTRACT: PASS")

    validate_workflow_text(WORKFLOW_PATH.read_text(encoding="utf-8"))
    print("WORKFLOW_STATIC_VALIDATION: PASS")

    before = LOCK_PATH.read_bytes()
    run_checked(
        "PYTHON_LOCK",
        ["uv", "lock", "--check", "--managed-python"],
        timeout_seconds=ci_owned_remaining_seconds(deadline),
        offline=True,
    )
    assert_lock_unchanged(before, LOCK_PATH.read_bytes())
    print("UV_LOCK_IMMUTABLE: PASS")

    passed: list[str] = []
    for label, command in ci_owned_child_commands():
        completed = run_checked(
            label,
            command,
            timeout_seconds=ci_owned_remaining_seconds(deadline),
            offline=True,
        )
        if (
            label == "CATALOG_RESOLUTION"
            and '"asset_id": "CATALOG-ROOT-001"' not in completed.stdout
        ):
            raise CiValidationError("catalog_resolution_contract_mismatch")
        if label == "PRE_COMMIT_HOOK" and completed.stdout.strip() != ".githooks":
            raise CiValidationError("pre_commit_hook_config_mismatch")
        passed.append(label)

    assert_lock_unchanged(before, LOCK_PATH.read_bytes())
    ci_owned_remaining_seconds(deadline)
    print("CI_OWNED_FOCUSED_RESULT: PASS")
    return passed


def run_ci_owned_delivery_preflight(*, base_ref: str = "origin/main") -> None:
    started = time.monotonic()
    deadline = started + CI_OWNED_DELIVERY_TIMEOUT_SECONDS
    candidate = git_text(["rev-parse", "HEAD"])
    tree = git_text(["show", "-s", "--format=%T", candidate])
    branch = git_text(["symbolic-ref", "--quiet", "--short", "HEAD"])
    base_commit: str | None = None
    tracked_count: int | None = None
    tracked_clean = False
    changed_paths: list[str] = []
    waivers: list[dict[str, str]] = []
    focused_passes: list[str] = []
    status = "FAIL"
    eligibility_status = "NOT_RUN"
    skip_policy_status = "NOT_RUN"
    error: str | None = None
    try:
        tracked_dirty = git_text(
            ["status", "--porcelain=v1", "--untracked-files=no"]
        )
        if tracked_dirty:
            raise CiValidationError("ci_owned_delivery_candidate_has_tracked_changes")
        tracked_clean = True
        base_commit = git_text(["merge-base", base_ref, candidate])
        tracked_count = len(
            git_text(["ls-tree", "-r", "--name-only", candidate]).splitlines()
        )
        changed_paths = git_text(
            ["diff", "--name-only", f"{base_commit}..{candidate}"]
        ).splitlines()
        eligibility_status = "FAIL"
        changed_paths = validate_ci_owned_delivery_eligibility(changed_paths)
        eligibility_status = "PASS"

        diff_text = git_text(
            ["diff", "--unified=3", f"{base_commit}..{candidate}", "--", "tests"]
        )

        def proof_exists(path: str) -> bool:
            completed = subprocess.run(
                ["git", "cat-file", "-e", f"{candidate}:{path}"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
            )
            return completed.returncode == 0

        skip_policy_status = "FAIL"
        waivers = validate_new_test_skip_policy(
            diff_text,
            proof_exists=proof_exists,
        )
        skip_policy_status = "PASS"
        focused_passes = run_ci_owned_focused_gate(deadline=deadline)
        status = "PASS"
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        elapsed = round(time.monotonic() - started, 3)
        payload = {
            "schema": CI_OWNED_DELIVERY_SCHEMA,
            "pilot_id": CI_OWNED_DELIVERY_PILOT_ID,
            "status": status,
            "observed_at": utc_now(),
            "candidate": {
                "branch": branch,
                "commit": candidate,
                "tree": tree,
                "base_ref": base_ref,
                "base_commit": base_commit,
                "tracked_file_count": tracked_count,
                "tracked_worktree_clean": tracked_clean,
                "changed_paths": changed_paths,
            },
            "eligibility": {
                "status": eligibility_status,
                "asserted_class": "BOUNDED_OFFLINE_ROUTINE",
                "ambiguous_or_ineligible_fallback": DELIVERY_PREFLIGHT_COMMAND,
            },
            "focused_gate": {
                "command": CI_OWNED_DELIVERY_COMMAND,
                "timeout_seconds": CI_OWNED_DELIVERY_TIMEOUT_SECONDS,
                "wall_seconds": elapsed,
                "pass_labels": focused_passes,
                "full_repository_policy_executed": False,
            },
            "new_skip_policy": {
                "status": skip_policy_status,
                "tracked_noncritical_waivers": waivers,
            },
            "full_validation": {
                "owner": CI_OWNED_FULL_VALIDATION_OWNER,
                "state": "DELEGATED_PENDING",
                "clean_checkout": "REQUIRED_IN_PULL_REQUEST_CI",
                "required_before_merge": True,
            },
            "pilot": {
                "required_eligible_observations": 3,
                "success_first_head_ci": "3/3",
                "minimum_time_saved_minutes": 7,
                "rollback_on_missed_clean_checkout_or_local_data_defect": True,
            },
            "network": {"performed": False},
            "error": error,
        }
        receipt = write_delivery_receipt(
            payload,
            candidate,
            suffix=".ci-owned",
        )
        print(
            "CI_OWNED_DELIVERY_RECEIPT: "
            + receipt.relative_to(ROOT).as_posix()
        )
    print("CI_OWNED_DELIVERY_PREFLIGHT: PASS")


def validate(*, core_only: bool = False) -> None:
    validate_python_version(sys.version_info[:3])
    print("PYTHON_RUNTIME: PASS")

    uv = run_checked("UV_RUNTIME", ["uv", "--version"])
    validate_uv_version(uv.stdout + uv.stderr)

    with (ROOT / "pyproject.toml").open("rb") as handle:
        validate_project_contract(tomllib.load(handle))
    print("EXECUTABLE_CONTRACT: PASS")

    validate_workflow_text(WORKFLOW_PATH.read_text(encoding="utf-8"))
    print("WORKFLOW_STATIC_VALIDATION: PASS")

    before = LOCK_PATH.read_bytes()
    run_checked("PYTHON_LOCK", ["uv", "lock", "--check", "--managed-python"])
    assert_lock_unchanged(before, LOCK_PATH.read_bytes())
    print("UV_LOCK_IMMUTABLE: PASS")

    for label, command in child_commands(policy_only_baseline=core_only):
        completed = run_checked(label, command)
        if label == "CATALOG_RESOLUTION" and '"asset_id": "CATALOG-ROOT-001"' not in completed.stdout:
            raise CiValidationError("catalog_resolution_contract_mismatch")
        if label == "PRE_COMMIT_HOOK" and completed.stdout.strip() != ".githooks":
            raise CiValidationError("pre_commit_hook_config_mismatch")

    assert_lock_unchanged(before, LOCK_PATH.read_bytes())
    print("RESULT: PASS")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    delivery_mode = parser.add_mutually_exclusive_group()
    delivery_mode.add_argument(
        "--tracked-only-delivery",
        action="store_true",
        help="validate exact committed bytes in an isolated tracked-only clone",
    )
    delivery_mode.add_argument(
        "--control-only-task-close",
        action="store_true",
        help="run the fail-closed focused gate for an eligible combined task close",
    )
    delivery_mode.add_argument(
        "--ci-owned-delivery",
        action="store_true",
        help="run focused local controls and delegate the full clean-checkout suite to PR CI",
    )
    delivery_mode.add_argument(
        "--core-only",
        action="store_true",
        help="run all non-test validation commands for sharded CI core job",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="merge-base reference for new-test skip policy",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.tracked_only_delivery:
            run_tracked_only_delivery_preflight(base_ref=args.base_ref)
        elif args.control_only_task_close:
            from control_only_task_close_fast_path import run_fast_path

            run_fast_path(base_ref=args.base_ref)
        elif args.ci_owned_delivery:
            run_ci_owned_delivery_preflight(base_ref=args.base_ref)
        else:
            validate(core_only=args.core_only)
    except Exception as exc:
        print("RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
