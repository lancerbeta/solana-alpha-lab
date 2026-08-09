#!/usr/bin/env python3
"""Fail-closed local gate for one combined Project Sources task close."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, NamedTuple

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "control/control_only_task_close_fast_path_v1.yaml"
DEFAULT_REGISTRY = ROOT / "docs/project_sources/release_registry_v1.yaml"


class FastPathError(RuntimeError):
    """A control-only candidate did not satisfy the closed fast-path contract."""


class Classification(NamedTuple):
    eligible: bool
    receipt_path: str | None
    errors: tuple[str, ...]


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FastPathError(f"MAPPING_REQUIRED:{path.as_posix()}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FastPathError(f"MAPPING_REQUIRED:{path.as_posix()}")
    return value


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def classify_change_set(
    changes: list[tuple[str, str]], policy: dict[str, Any]
) -> Classification:
    contract = policy["eligible_change_set"]
    receipt_pattern = re.compile(contract["receipt_path_pattern"])
    required = set(contract["required_modified_paths"])
    errors: set[str] = set()
    observed_paths: set[str] = set()
    receipt_paths: list[str] = []

    for raw_status, raw_path in changes:
        status = raw_status.strip()
        path = normalize_path(raw_path.strip())
        if not path or path in observed_paths:
            errors.add("FAST_PATH_DUPLICATE_OR_EMPTY_PATH")
            continue
        observed_paths.add(path)

        if status.startswith("R"):
            errors.add("FAST_PATH_RENAME_FORBIDDEN")
            continue
        if status == "D":
            errors.add("FAST_PATH_DELETE_FORBIDDEN")
            continue
        if receipt_pattern.fullmatch(path):
            receipt_paths.append(path)
            if status != "A":
                errors.add("FAST_PATH_RECEIPT_MUST_BE_ADDED")
            continue
        if path not in required:
            errors.add("FAST_PATH_CHANGED_PATH_FORBIDDEN")
            continue
        if status != "M":
            errors.add("FAST_PATH_REQUIRED_PATH_MUST_BE_MODIFIED")

    if len(receipt_paths) != contract["added_receipt_count"]:
        errors.add("FAST_PATH_RECEIPT_COUNT_MISMATCH")
    missing = required - observed_paths
    if missing:
        errors.add("FAST_PATH_REQUIRED_PATH_MISSING")

    receipt_path = receipt_paths[0] if len(receipt_paths) == 1 else None
    return Classification(not errors, receipt_path, tuple(sorted(errors)))


def release_by_id(registry: dict[str, Any], release_id: Any) -> dict[str, Any] | None:
    releases = registry.get("releases")
    if not isinstance(releases, list):
        return None
    return next(
        (
            release
            for release in releases
            if isinstance(release, dict) and release.get("release_id") == release_id
        ),
        None,
    )


def validate_combined_receipt(
    receipt: dict[str, Any],
    registry: dict[str, Any],
    policy: dict[str, Any],
) -> set[str]:
    contract = policy["combined_receipt"]
    errors: set[str] = set()
    task_id = receipt.get("task_id")
    task_match = re.fullmatch(r"TASK-([0-9]+[A-Z]?)", str(task_id))
    if not task_match:
        errors.add("FAST_PATH_TASK_ID_INVALID")
        task_label = "INVALID"
    else:
        task_label = task_match.group(1)

    if receipt.get("schema") != contract["schema"]:
        errors.add("FAST_PATH_RECEIPT_SCHEMA_MISMATCH")
    if str(receipt.get("schema_version")) != contract["schema_version"]:
        errors.add("FAST_PATH_RECEIPT_VERSION_MISMATCH")
    if receipt.get("status") != "ACTIVATED_BY_OWNER_SMOKE":
        errors.add("FAST_PATH_RECEIPT_STATUS_INVALID")

    release = release_by_id(registry, receipt.get("release_id"))
    if release is None:
        errors.add("FAST_PATH_RELEASE_UNKNOWN")
    else:
        if release.get("task_id") != task_id:
            errors.add("FAST_PATH_RELEASE_TASK_MISMATCH")
        if release.get("status") != "ACTIVATED_BY_OWNER_SMOKE":
            errors.add("FAST_PATH_RELEASE_NOT_ACTIVE")
        if registry.get("active_ui_release_id") != release.get("release_id"):
            errors.add("FAST_PATH_ACTIVE_POINTER_MISMATCH")
        if registry.get("active_ui_state") != "REGISTRY_ACTIVATION_CONFIRMED":
            errors.add("FAST_PATH_ACTIVE_STATE_MISMATCH")
        if registry.get("latest_candidate_release_id") is not None:
            errors.add("FAST_PATH_CANDIDATE_POINTER_NOT_CLEARED")
        if receipt.get("manifest_binding") != release.get("artifact_bindings", {}).get(
            "canonical_manifest"
        ):
            errors.add("FAST_PATH_MANIFEST_BINDING_MISMATCH")

    expected_source = contract["source_smoke_template"].format(task_label=task_label)
    expected_terminal = contract["owner_terminal_template"].format(
        task_label=task_label
    )
    owner_terminal = receipt.get("owner_terminal")
    if not isinstance(owner_terminal, dict):
        errors.add("FAST_PATH_OWNER_TERMINAL_REQUIRED")
    else:
        if owner_terminal.get("source_smoke") != expected_source:
            errors.add("FAST_PATH_SOURCE_SMOKE_CLAUSE_MISMATCH")
        if owner_terminal.get("done_acceptance") != contract["done_acceptance"]:
            errors.add("FAST_PATH_DONE_ACCEPTANCE_CLAUSE_MISMATCH")
        if owner_terminal.get("reported_terminal") != expected_terminal:
            errors.add("FAST_PATH_REPORTED_TERMINAL_MISMATCH")

    activation = receipt.get("activation_evidence")
    if not isinstance(activation, dict):
        errors.add("FAST_PATH_ACTIVATION_EVIDENCE_REQUIRED")
    else:
        if activation.get("class") != contract["evidence_class"]:
            errors.add("FAST_PATH_EVIDENCE_CLASS_MISMATCH")
        if activation.get("smoke_outcome") != contract["smoke_outcome"]:
            errors.add("FAST_PATH_SMOKE_NOT_PASS")
        if activation.get("reported_terminal") != expected_terminal:
            errors.add("FAST_PATH_ACTIVATION_TERMINAL_MISMATCH")

    decision = receipt.get("decision")
    if not isinstance(decision, dict):
        errors.add("FAST_PATH_DECISION_REQUIRED")
    else:
        if decision.get("task_status") != contract["task_status"]:
            errors.add("FAST_PATH_TASK_STATUS_NOT_DONE")
        if decision.get("canonical_task_done") is not contract["canonical_task_done"]:
            errors.add("FAST_PATH_CANONICAL_DONE_NOT_TRUE")
        if decision.get("next_task_selected") is not contract["next_task_selected"]:
            errors.add("FAST_PATH_NEXT_TASK_SELECTED")

    authority = receipt.get("authority")
    if not isinstance(authority, dict):
        errors.add("FAST_PATH_AUTHORITY_REQUIRED")
    else:
        for field in contract["required_zero_authority_fields"]:
            if authority.get(field) != 0:
                errors.add(f"FAST_PATH_AUTHORITY_NOT_ZERO:{field}")

    verdict = receipt.get("factory_fit", {}).get("verdict")
    if verdict not in contract["allowed_factory_fit_verdicts"]:
        errors.add("FAST_PATH_FACTORY_FIT_NOT_PASS")

    disposition = receipt.get("project_sources_disposition")
    if not isinstance(disposition, dict):
        errors.add("FAST_PATH_SOURCE_DISPOSITION_REQUIRED")
    else:
        if disposition.get("kind") != contract["disposition_kind"]:
            errors.add("FAST_PATH_SOURCE_DISPOSITION_KIND_MISMATCH")
        if disposition.get("release_id") != receipt.get("release_id"):
            errors.add("FAST_PATH_SOURCE_DISPOSITION_RELEASE_MISMATCH")
        if disposition.get("registry_path") != contract["registry_path"]:
            errors.add("FAST_PATH_SOURCE_DISPOSITION_REGISTRY_MISMATCH")

    return errors


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def run_process(
    command: list[str],
    *,
    root: Path,
    runner: ProcessRunner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    completed = runner(
        command,
        cwd=root,
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
        raise FastPathError(
            f"FAST_PATH_COMMAND_FAILED:{command[0]}:{completed.returncode}"
        )
    return completed


def git_output(
    args: list[str],
    *,
    root: Path,
    runner: ProcessRunner = subprocess.run,
) -> str:
    command = ["git", *args]
    completed = runner(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise FastPathError(
            f"FAST_PATH_COMMAND_FAILED:git:{completed.returncode}"
        )
    return completed.stdout.strip()


def parse_name_status(text: str) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            changes.append((parts[0], parts[1]))
        elif len(parts) == 3 and parts[0].startswith(("R", "C")):
            changes.append((parts[0], parts[2]))
        elif line.strip():
            changes.append(("INVALID", line.strip()))
    return changes


def run_fast_path(
    *,
    base_ref: str = "origin/main",
    root: Path = ROOT,
    policy_path: Path | None = None,
    runner: ProcessRunner = subprocess.run,
) -> dict[str, Any]:
    policy = load_yaml(policy_path or (root / DEFAULT_POLICY.relative_to(ROOT)))
    tracked_dirty = git_output(
        ["status", "--porcelain=v1", "--untracked-files=no"],
        root=root,
        runner=runner,
    )
    if tracked_dirty:
        raise FastPathError("FAST_PATH_TRACKED_WORKTREE_DIRTY")

    candidate = git_output(["rev-parse", "HEAD"], root=root, runner=runner)
    tree = git_output(
        ["show", "-s", "--format=%T", "HEAD"], root=root, runner=runner
    )
    base = git_output(["merge-base", base_ref, "HEAD"], root=root, runner=runner)
    diff = git_output(
        ["diff", "--name-status", f"{base}..HEAD"], root=root, runner=runner
    )
    classification = classify_change_set(parse_name_status(diff), policy)
    if not classification.eligible or classification.receipt_path is None:
        detail = ",".join(classification.errors) or "UNKNOWN"
        fallback = policy["validation"]["fallback_command"]
        raise FastPathError(f"FAST_PATH_INELIGIBLE:{detail};FALLBACK:{fallback}")

    receipt = load_json(root / classification.receipt_path)
    registry = load_yaml(root / policy["combined_receipt"]["registry_path"])
    receipt_errors = validate_combined_receipt(receipt, registry, policy)
    if receipt_errors:
        raise FastPathError(
            "FAST_PATH_RECEIPT_INVALID:" + ",".join(sorted(receipt_errors))
        )

    commands = [
        ["git", "diff", "--check", f"{base}..HEAD"],
        [
            sys.executable,
            "-B",
            "scripts/secret_scan.py",
            "--self-test",
            "--scan-repository",
        ],
        [sys.executable, "-B", "scripts/validate_catalog.py"],
        [sys.executable, "-B", "scripts/generate_navigation.py", "--check"],
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "tests.test_project_sources_release_registry",
            "tests.test_control_only_task_close_fast_path",
        ],
    ]
    for command in commands:
        run_process(command, root=root, runner=runner)

    result = {
        "schema": "smial.control_only_task_close_fast_path.receipt",
        "schema_version": "1.0",
        "decision": "ELIGIBLE_FOCUSED_GATE_PASS",
        "candidate_commit": candidate,
        "candidate_tree": tree,
        "base_commit": base,
        "combined_receipt": classification.receipt_path,
        "full_validation_owner": policy["validation"]["full_validation_owner"],
        "post_merge_validation": policy["validation"]["post_merge_validation"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print("RESULT: PASS")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_fast_path(base_ref=args.base_ref, policy_path=args.policy)
    except Exception as exc:
        print("RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
