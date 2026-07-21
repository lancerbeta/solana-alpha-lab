#!/usr/bin/env python3
"""Platform-neutral, fail-closed repository validation entrypoint."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
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


class CiValidationError(RuntimeError):
    """Fail-closed CI or repository contract violation."""


def expected_workflow() -> dict[str, Any]:
    return {
        "name": "Repository validation",
        "on": {"push": {"branches": ["main"]}},
        "permissions": {"contents": "read"},
        "concurrency": {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": "true",
        },
        "jobs": {
            "validate": {
                "runs-on": "ubuntu-24.04",
                "timeout-minutes": "10",
                "env": {
                    "UV_NO_ENV_FILE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "steps": [
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
                        "run": VALIDATION_COMMAND,
                    },
                ],
            }
        },
    }


def validate_workflow_text(text: str) -> None:
    lowered = text.lower()
    forbidden = (
        "secrets.",
        "pull_request_target",
        "workflow_dispatch",
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
    if uses != [CHECKOUT_PIN, SETUP_UV_PIN]:
        raise CiValidationError("workflow_action_set_mismatch")
    if any(not re.search(r"@[0-9a-f]{40}$", reference) for reference in uses):
        raise CiValidationError("workflow_action_not_immutable")


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


def child_commands() -> list[tuple[str, list[str]]]:
    python = sys.executable
    return [
        (
            "SECRET_REJECTION",
            [python, "-B", "scripts/secret_scan.py", "--self-test", "--scan-repository"],
        ),
        ("CATALOG_VALIDATION", [python, "-B", "scripts/validate_catalog.py"]),
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
        ("REPOSITORY_POLICY", [python, "-B", "scripts/validate_baseline.py"]),
        ("PRE_COMMIT_HOOK", ["git", "config", "--local", "--get", "core.hooksPath"]),
    ]


def run_checked(
    label: str,
    command: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    execute = runner or subprocess.run
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["UV_MANAGED_PYTHON"] = "1"
    completed = execute(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    if completed.returncode != 0:
        raise CiValidationError(f"{label.lower()}_failed:{completed.returncode}")
    print(f"{label}: PASS")
    return completed


def validate() -> None:
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

    for label, command in child_commands():
        completed = run_checked(label, command)
        if label == "CATALOG_RESOLUTION" and '"asset_id": "CATALOG-ROOT-001"' not in completed.stdout:
            raise CiValidationError("catalog_resolution_contract_mismatch")
        if label == "PRE_COMMIT_HOOK" and completed.stdout.strip() != ".githooks":
            raise CiValidationError("pre_commit_hook_config_mismatch")

    assert_lock_unchanged(before, LOCK_PATH.read_bytes())
    print("RESULT: PASS")


def main() -> int:
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
