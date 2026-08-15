#!/usr/bin/env python3
"""Deterministic evaluator for versioned owner-attention policies."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "control" / "owner_attention_gate_v2.yaml"
PROJECT_PROFILE = ROOT / "delivery-harness" / "project-profile.yaml"
REQUEST_SCHEMA = "smial.owner-attention-request"
REQUEST_VERSION = "1.0"
REQUIRED_REVIEW_ROLES = {
    "CODE_REVIEWER",
    "GOAL_DOD_CRITIC",
    "ARCHITECTURE_CRITIC",
}
SINGLE_AGENT_REVIEW_FALLBACK = "SINGLE_AGENT_REVIEW_FALLBACK"


def review_records_single_agent_fallback(review: dict[str, Any]) -> bool:
    """True when the receipt admits author-as-reviewer. Merge must deny."""

    claims = review.get("non_claims")
    if isinstance(claims, list) and SINGLE_AGENT_REVIEW_FALLBACK in claims:
        return True
    for item in review.get("reviews") or []:
        if not isinstance(item, dict):
            continue
        findings = item.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if isinstance(finding, str) and SINGLE_AGENT_REVIEW_FALLBACK in finding:
                return True
    return False
CONTROL_RUNTIME_PATHS = (
    "scripts/owner_attention_gate.py",
    "scripts/delivery_harness.py",
    "delivery-harness/harness.yaml",
    "delivery-harness/context-map.yaml",
    "catalog/schemas/owner_attention_gate_v2.schema.json",
    "catalog/schemas/delivery_harness.schema.json",
    "catalog/schemas/delivery_harness_project_profile.schema.json",
    "catalog/schemas/delivery_harness_context_map.schema.json",
    "catalog/schemas/delivery_harness_context_receipt.schema.json",
    "catalog/schemas/delivery_harness_task_contract.schema.json",
    "catalog/schemas/delivery_harness_completion_evidence.schema.json",
    "catalog/schemas/delivery_harness_independent_review_evidence.schema.json",
)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_read(args: list[str], cwd: Path) -> bytes:
    completed = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, shell=False)
    if completed.returncode != 0:
        raise ValueError("LIVE_READBACK_FAILED")
    return completed.stdout


def decode_json_mapping(value: bytes, code: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(code)
            result[key] = item
        return result

    try:
        document = json.loads(
            value.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError(code)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError(code) from None
    if not isinstance(document, dict):
        raise ValueError(code)
    return document


def load_delivery_harness_runtime(root: Path) -> Any:
    script = root / "scripts/delivery_harness.py"
    spec = importlib.util.spec_from_file_location(
        "delivery_harness_runtime_for_merge", script
    )
    if spec is None or spec.loader is None:
        raise ValueError("CONTEXT_RUNTIME_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, ImportError, ValueError):
        raise ValueError("CONTEXT_RUNTIME_UNAVAILABLE") from None
    return module


def safe_repo_path(value: str, *, allow_prefix: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    prefix = value.endswith("/**")
    if prefix:
        if not allow_prefix:
            raise ValueError("MANAGED_WRITE_SET_INVALID")
        value = value[:-3]
    if not value or PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or parts[0].casefold() == ".git":
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    normalized = PurePosixPath(*parts).as_posix()
    return normalized + ("/**" if prefix else "")


def safe_evidence_json_path(value: str) -> str:
    normalized = safe_repo_path(value)
    if not normalized.startswith("docs/evidence/") or not normalized.endswith(".json"):
        raise ValueError("DELIVERY_EVIDENCE_PATH_INVALID")
    return normalized


def decode_nul_fields(value: bytes, code: str) -> list[str]:
    if not value:
        return []
    if not value.endswith(b"\0"):
        raise ValueError(code)
    try:
        fields = value[:-1].decode("utf-8", errors="strict").split("\0")
    except UnicodeDecodeError:
        raise ValueError(code) from None
    if any(not field for field in fields):
        raise ValueError(code)
    return fields


def decode_git_name_only(value: bytes) -> list[str]:
    fields = decode_nul_fields(value, "DELIVERY_DIFF_INVALID")
    paths = [safe_repo_path(field) for field in fields]
    if len(set(paths)) != len(paths):
        raise ValueError("DELIVERY_DIFF_INVALID")
    return paths


def decode_git_name_status(value: bytes) -> list[tuple[str, str]]:
    fields = decode_nul_fields(value, "DELIVERY_INVENTORY_INVALID")
    if len(fields) % 2:
        raise ValueError("DELIVERY_INVENTORY_INVALID")
    entries: list[tuple[str, str]] = []
    observed: set[str] = set()
    for index in range(0, len(fields), 2):
        status, raw_path = fields[index : index + 2]
        if status not in {"A", "M", "T", "D"}:
            raise ValueError("DELIVERY_INVENTORY_INVALID")
        path = safe_repo_path(raw_path)
        if path in observed:
            raise ValueError("DELIVERY_INVENTORY_INVALID")
        observed.add(path)
        entries.append((status, path))
    return entries


def _validation_command(value: Any, *, result_owner: bool) -> dict[str, Any] | None:
    if value is None:
        return None
    required = (
        {"argv", "result_owner", "trusted_paths"}
        if result_owner
        else {"argv", "trusted_paths"}
    )
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    argv = value.get("argv")
    if not (
        isinstance(argv, list)
        and bool(argv)
        and all(
            isinstance(item, str)
            and bool(item)
            and "\x00" not in item
            and "\n" not in item
            and "\r" not in item
            for item in argv
        )
    ):
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    if result_owner and value.get("result_owner") not in {
        "FOCUSED_PLUS_EXACT_PR_CI",
        "FULL_EXACT_HEAD",
    }:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    trusted_paths = value.get("trusted_paths")
    if not (
        isinstance(trusted_paths, list)
        and bool(trusted_paths)
        and all(isinstance(item, str) for item in trusted_paths)
    ):
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    try:
        normalized = [safe_repo_path(item) for item in trusted_paths]
    except ValueError:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID") from None
    if len(set(normalized)) != len(normalized):
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    return value


def _profile_validation(profile: dict[str, Any]) -> dict[str, Any]:
    validation = profile.get("validation")
    if not isinstance(validation, dict) or set(validation) != {
        "github_ci_bound",
        "primary",
        "fallback",
        "credential_scan",
    }:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    return validation


def load_base_bound_profile(
    root: Path, *, expected_base: str, runner=run_read
) -> dict[str, Any]:
    profile_path = root.resolve() / "delivery-harness" / "project-profile.yaml"
    try:
        profile = decode_json_mapping(
            profile_path.read_bytes(), "PROJECT_PROFILE_BASE_BINDING_INVALID"
        )
        base_profile = decode_json_mapping(
            runner(
                ["git", "show", f"{expected_base}:delivery-harness/project-profile.yaml"],
                root,
            ),
            "PROJECT_PROFILE_BASE_BINDING_INVALID",
        )
    except (OSError, ValueError):
        raise ValueError("PROJECT_PROFILE_BASE_BINDING_INVALID") from None
    if canonical_json_bytes(profile) != canonical_json_bytes(base_profile):
        raise ValueError("PROJECT_PROFILE_BASE_BINDING_INVALID")
    repository = profile.get("repository")
    if not isinstance(repository, dict) or set(repository) != {"name", "default_branch"}:
        raise ValueError("PROJECT_PROFILE_BASE_BINDING_INVALID")
    if not (
        isinstance(repository.get("name"), str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository["name"])
        and isinstance(repository.get("default_branch"), str)
        and re.fullmatch(r"[A-Za-z0-9._/-]+", repository["default_branch"])
    ):
        raise ValueError("PROJECT_PROFILE_BASE_BINDING_INVALID")
    return profile


def require_base_bound_control_runtime(
    root: Path, *, expected_base: str, runner=run_read
) -> None:
    for relative in CONTROL_RUNTIME_PATHS:
        candidate = root.resolve() / relative
        try:
            base_bytes = runner(["git", "show", f"{expected_base}:{relative}"], root)
        except ValueError:
            raise ValueError("CONTROL_RUNTIME_CHANGED") from None
        if not candidate.is_file() or candidate.read_bytes() != base_bytes:
            raise ValueError("CONTROL_RUNTIME_CHANGED")


def _trusted_path_matches_base(
    root: Path,
    relative: str,
    *,
    expected_base: str,
    runner,
    cache: dict[str, bool],
) -> bool:
    normalized = safe_repo_path(relative)
    cached = cache.get(normalized)
    if cached is not None:
        return cached
    candidate = root.resolve() / normalized
    matched = False
    if candidate.is_file():
        try:
            base_bytes = runner(
                ["git", "show", f"{expected_base}:{normalized}"], root
            )
        except ValueError:
            matched = False
        else:
            matched = candidate.read_bytes() == base_bytes
    cache[normalized] = matched
    return matched


def load_validation_bindings(
    root: Path, *, expected_base: str, runner=run_read
) -> dict[str, dict[str, Any] | None]:
    try:
        profile = load_base_bound_profile(root, expected_base=expected_base, runner=runner)
    except ValueError:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID") from None
    validation = _profile_validation(profile)
    if validation["github_ci_bound"] is not True:
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    bindings = {
        "primary": _validation_command(validation["primary"], result_owner=True),
        "fallback": _validation_command(validation["fallback"], result_owner=True),
        "credential_scan": _validation_command(
            validation["credential_scan"], result_owner=False
        ),
    }
    cache: dict[str, bool] = {}
    for name, command in bindings.items():
        if command is None:
            continue
        if not all(
            _trusted_path_matches_base(
                root,
                relative,
                expected_base=expected_base,
                runner=runner,
                cache=cache,
            )
            for relative in command["trusted_paths"]
        ):
            bindings[name] = None
    return bindings


def render_validation_command(command: dict[str, Any], expected_base: str) -> list[str]:
    rendered = [item.replace("{expected_base}", expected_base) for item in command["argv"]]
    if any("{" in item or "}" in item for item in rendered):
        raise ValueError("PROJECT_VALIDATION_BINDING_INVALID")
    return rendered


def load_base_bound_policy(
    root: Path, *, expected_base: str, runner=run_read
) -> dict[str, Any]:
    try:
        candidate = decode_json_mapping(
            (root.resolve() / "control" / "owner_attention_gate_v2.yaml").read_bytes(),
            "OWNER_POLICY_BASE_BINDING_INVALID",
        )
        base = decode_json_mapping(
            runner(
                [
                    "git", "show",
                    f"{expected_base}:control/owner_attention_gate_v2.yaml",
                ],
                root,
            ),
            "OWNER_POLICY_BASE_BINDING_INVALID",
        )
    except (OSError, ValueError):
        raise ValueError("OWNER_POLICY_BASE_BINDING_INVALID") from None
    if canonical_json_bytes(candidate) != canonical_json_bytes(base):
        raise ValueError("OWNER_POLICY_BASE_BINDING_INVALID")
    return candidate


def candidate_identity_unchanged(
    root: Path, *, head: str, tree: str, runner=run_read
) -> bool:
    try:
        observed_head = runner(["git", "rev-parse", "HEAD"], root).decode(
            "ascii", errors="strict"
        ).strip()
        observed_tree = runner(["git", "rev-parse", "HEAD^{tree}"], root).decode(
            "ascii", errors="strict"
        ).strip()
        dirty = bool(runner(["git", "status", "--porcelain=v1"], root).strip())
    except (UnicodeDecodeError, ValueError):
        return False
    return observed_head == head and observed_tree == tree and not dirty


def live_default_branch_oid(
    root: Path, *, repository: str, branch: str, runner=run_read
) -> str:
    try:
        value = runner(
            [
                "gh", "api", f"repos/{repository}/git/ref/heads/{branch}",
                "--jq", ".object.sha",
            ],
            root,
        ).decode("ascii", errors="strict").strip()
    except (UnicodeDecodeError, ValueError):
        raise ValueError("DEFAULT_BRANCH_READBACK_INVALID") from None
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("DEFAULT_BRANCH_READBACK_INVALID")
    return value


def parse_managed_write_set(plan_text: str, heading: str) -> list[str]:
    if heading != "Managed write set":
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    heading_pattern = re.compile(r"(?m)^## Managed write set\s*\r?$")
    matches = list(heading_pattern.finditer(plan_text))
    if len(matches) != 1:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    section_start = matches[0].end()
    next_heading = re.search(r"(?m)^##\s+", plan_text[section_start:])
    section_end = (
        section_start + next_heading.start() if next_heading is not None else len(plan_text)
    )
    section = plan_text[section_start:section_end]
    fence = re.search(r"(?ms)^```text\s*\r?\n(.*?)^```\s*\r?$", section)
    if fence is None:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    managed: list[str] = []
    for raw_line in fence.group(1).splitlines():
        candidate = re.sub(r"\s+#.*$", "", raw_line).strip()
        if not candidate:
            continue
        normalized = safe_repo_path(candidate, allow_prefix=True)
        if normalized in managed:
            raise ValueError("MANAGED_WRITE_SET_INVALID")
        managed.append(normalized)
    if not managed:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    return managed


def path_in_managed_write_set(path: str, managed: list[str]) -> bool:
    try:
        normalized = safe_repo_path(path)
    except ValueError:
        return False
    for entry in managed:
        if entry.endswith("/**"):
            prefix = entry[:-3]
            if normalized.startswith(prefix + "/"):
                return True
        elif normalized == entry:
            return True
    return False


def live_pr_delivery_scope(
    root: Path, receipt: dict[str, Any], *, runner=run_read
) -> tuple[str, str, str, list[str]]:
    module = load_delivery_harness_runtime(root)
    loader = getattr(module, "load_closed_document", None)
    if not callable(loader):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    try:
        harness = loader(
            root / "delivery-harness/harness.yaml",
            root / "catalog/schemas/delivery_harness.schema.json",
        )
        profile = decode_json_mapping(
            (root / "delivery-harness" / "project-profile.yaml").read_bytes(),
            "MANAGED_WRITE_SET_INVALID",
        )
    except (OSError, ValueError):
        raise ValueError("MANAGED_WRITE_SET_INVALID") from None
    merge_policy = harness.get("merge_policy") if isinstance(harness, dict) else None
    prefixes = merge_policy.get("harness_control_write_prefixes") if isinstance(merge_policy, dict) else None
    repository = profile.get("repository") if isinstance(profile, dict) else None
    default_branch = repository.get("default_branch") if isinstance(repository, dict) else None
    if not (
        isinstance(prefixes, list)
        and prefixes
        and all(isinstance(item, str) and item for item in prefixes)
        and isinstance(default_branch, str)
        and default_branch
    ):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    managed = [safe_repo_path(item, allow_prefix=True) for item in prefixes]
    if len(set(managed)) != len(managed):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    expected_upstream = f"origin/{default_branch}"
    try:
        expected_upstream_oid = runner(
            ["git", "rev-parse", expected_upstream], root
        ).decode("ascii", errors="strict").strip()
        expected_base = runner(
            ["git", "merge-base", "HEAD", expected_upstream], root
        ).decode("ascii", errors="strict").strip()
    except (UnicodeDecodeError, ValueError):
        raise ValueError("MANAGED_WRITE_SET_INVALID") from None
    if not (
        re.fullmatch(r"[0-9a-f]{40}", expected_base)
        and re.fullmatch(r"[0-9a-f]{40}", expected_upstream_oid)
    ):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    control = receipt.get("control_pr")
    if not (
        is_live_pr_head(receipt)
        and isinstance(control, dict)
    ):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    return expected_base, expected_upstream, expected_upstream_oid, managed


def task_delivery_scope(
    root: Path, receipt: dict[str, Any], *, runner=run_read
) -> tuple[str, str, str, list[str]]:
    if is_live_pr_head(receipt):
        return live_pr_delivery_scope(root, receipt, runner=runner)
    task = receipt.get("task")
    if not isinstance(task, dict) or not (
        isinstance(task.get("path"), str)
        and isinstance(task.get("task_id"), str)
    ):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    relative = safe_repo_path(task["path"])
    task_path = (root.resolve() / relative).resolve()
    if root.resolve() not in task_path.parents or not task_path.is_file():
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    try:
        module = load_delivery_harness_runtime(root)
        parser = getattr(module, "parse_task_contract", None)
        if callable(parser):
            metadata = parser(root, relative, task["task_id"])
        else:
            parser = getattr(module, "parse_task", None)
            if not callable(parser):
                raise ValueError("MANAGED_WRITE_SET_INVALID")
            parsed = parser(root, task["task_id"], relative)
            metadata = parsed[0] if isinstance(parsed, tuple) and parsed else None
    except (OSError, ValueError):
        raise ValueError("MANAGED_WRITE_SET_INVALID") from None
    if not isinstance(metadata, dict):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    binding = metadata.get("git_binding")
    managed_value = metadata.get("managed_write_set")
    if not isinstance(binding, dict):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    expected_base = binding.get("expected_base")
    expected_upstream = binding.get("expected_upstream")
    expected_upstream_oid = binding.get("expected_upstream_oid")
    if not isinstance(expected_base, str) or re.fullmatch(r"[0-9a-f]{40}", expected_base) is None:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    if not isinstance(expected_upstream, str) or not expected_upstream.startswith("origin/"):
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    if not isinstance(expected_upstream_oid, str) or re.fullmatch(
        r"[0-9a-f]{40}", expected_upstream_oid
    ) is None:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    if isinstance(managed_value, list):
        if not managed_value or any(not isinstance(item, str) for item in managed_value):
            raise ValueError("MANAGED_WRITE_SET_INVALID")
        managed = [safe_repo_path(item, allow_prefix=True) for item in managed_value]
        if len(set(managed)) != len(managed):
            raise ValueError("MANAGED_WRITE_SET_INVALID")
        return expected_base, expected_upstream, expected_upstream_oid, managed
    if not isinstance(managed_value, dict) or set(managed_value) != {"path", "heading"}:
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    plan_relative = safe_repo_path(managed_value["path"])
    plan_path = (root.resolve() / plan_relative).resolve()
    if root.resolve() not in plan_path.parents or not plan_path.is_file():
        raise ValueError("MANAGED_WRITE_SET_INVALID")
    return expected_base, expected_upstream, expected_upstream_oid, parse_managed_write_set(
        plan_path.read_text(encoding="utf-8"), managed_value["heading"]
    )


def guarded_delivery_scope(
    root: Path,
    receipt: dict[str, Any],
    *,
    repository: str,
    runner=run_read,
) -> tuple[str, str, list[str], str]:
    expected_base, expected_upstream, expected_upstream_oid, managed = (
        task_delivery_scope(root, receipt, runner=runner)
    )
    if expected_base != expected_upstream_oid:
        raise ValueError("STALE_BASE_CONTROL_PLANE")
    try:
        require_base_bound_control_runtime(
            root, expected_base=expected_base, runner=runner
        )
    except ValueError as exc:
        if str(exc) != "CONTROL_RUNTIME_CHANGED" or not is_live_pr_head(receipt):
            raise
    profile = load_base_bound_profile(
        root, expected_base=expected_base, runner=runner
    )
    profile_repository = profile["repository"]
    default_branch = profile_repository["default_branch"]
    if (
        profile_repository["name"] != repository
        or expected_upstream != f"origin/{default_branch}"
    ):
        raise ValueError("PROJECT_DEFAULT_BRANCH_BINDING_INVALID")
    return expected_base, expected_upstream_oid, managed, default_branch


def build_delivery_checks(
    root: Path,
    *,
    context_receipt: dict[str, Any],
    local_head: str,
    local_tree: str,
    ci_pass: bool,
    runner=run_read,
) -> dict[str, bool]:
    expected_base, _expected_upstream, _expected_upstream_oid, managed = task_delivery_scope(
        root, context_receipt, runner=runner
    )
    changed_bytes = runner(
        [
            "git", "diff", "--name-only", "--no-renames", "-z",
            f"{expected_base}...{local_head}",
        ],
        root,
    )
    try:
        changed = decode_git_name_only(changed_bytes)
    except ValueError:
        changed = []
    write_set_pass = bool(changed) and all(
        path_in_managed_write_set(path, managed) for path in changed
    )
    preflight = {"required_tests_pass": False, "full_gate_pass": False}
    try:
        bindings = load_validation_bindings(
            root, expected_base=expected_base, runner=runner
        )
    except ValueError:
        bindings = {"primary": None, "fallback": None, "credential_scan": None}
    identity_broken = False
    for name in ("primary", "fallback"):
        command = bindings[name]
        if command is None:
            continue
        try:
            runner(render_validation_command(command, expected_base), root)
        except ValueError:
            continue
        if not candidate_identity_unchanged(
            root, head=local_head, tree=local_tree, runner=runner
        ):
            identity_broken = True
            break
        if command["result_owner"] == "FULL_EXACT_HEAD":
            preflight = {"required_tests_pass": True, "full_gate_pass": True}
        else:
            preflight = {
                "required_tests_pass": ci_pass,
                "full_gate_pass": ci_pass,
            }
        break
    if (
        preflight["required_tests_pass"] is False
        and is_live_pr_head(context_receipt)
        and ci_pass is True
        and identity_broken is False
    ):
        preflight = {
            "required_tests_pass": True,
            "full_gate_pass": True,
        }
    secret_scan_pass = False
    secret_command = bindings["credential_scan"]
    if secret_command is not None and not identity_broken:
        try:
            runner(render_validation_command(secret_command, expected_base), root)
            secret_scan_pass = candidate_identity_unchanged(
                root, head=local_head, tree=local_tree, runner=runner
            )
        except ValueError:
            pass
    return {
        **preflight,
        "write_set_pass": write_set_pass,
        "secret_scan_pass": secret_scan_pass,
    }


def github_repository_from_origin(value: str) -> str:
    for pattern in (
        r"git@github\.com:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    ):
        match = re.fullmatch(pattern, value)
        if match is not None:
            return match.group(1)
    raise ValueError("LOCAL_REPOSITORY_IDENTITY_MISMATCH")


def is_live_pr_head(receipt: dict[str, Any]) -> bool:
    control = receipt.get("control_pr")
    return (
        isinstance(control, dict)
        and set(control) == {"pr_number", "identity_mode"}
        and type(control.get("pr_number")) is int
        and control["pr_number"] >= 1
        and control.get("identity_mode") == "LIVE_PR_HEAD"
        and "task" not in receipt
    )


def verify_context_receipt(root: Path, receipt: dict[str, Any]) -> None:
    live_pr = is_live_pr_head(receipt)
    required = {
        "schema", "schema_version", "harness_id", "route", "cloud_bundle_mode",
        "repository", "selected", "gaps", "budgets", "receipt_sha256",
    }
    required.add("control_pr" if live_pr else "task")
    if set(receipt) != required or not (
        receipt.get("schema") == "smial.delivery-context-receipt"
        and receipt.get("schema_version") == "1.0"
        and receipt.get("harness_id") == "DELIVERY_HARNESS_V1"
        and receipt.get("route") in {
            "DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY", "DESIGN_ONLY"
        }
        and receipt.get("cloud_bundle_mode") == "OWNER_MANAGED_OPTIONAL_EXPORT"
        and isinstance(receipt.get("repository"), dict)
        and isinstance(receipt.get("selected"), list)
        and isinstance(receipt.get("gaps"), list)
        and isinstance(receipt.get("budgets"), dict)
        and (
            live_pr
            or isinstance(receipt.get("task"), dict)
        )
    ):
        raise ValueError("CONTEXT_RECEIPT_INVALID")
    repository = receipt["repository"]
    if set(repository) != {"name", "head", "tree", "branch", "dirty"} or not (
        isinstance(repository["name"], str)
        and isinstance(repository["branch"], str)
        and type(repository["dirty"]) is bool
        and isinstance(repository["head"], str)
        and re.fullmatch(r"[0-9a-f]{40}", repository["head"])
        and isinstance(repository["tree"], str)
        and re.fullmatch(r"[0-9a-f]{40}", repository["tree"])
    ):
        raise ValueError("CONTEXT_RECEIPT_INVALID")
    if not live_pr:
        task = receipt["task"]
        if set(task) != {"task_id", "path", "sha256"} or not (
            isinstance(task["task_id"], str)
            and isinstance(task["path"], str)
            and isinstance(task["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", task["sha256"])
        ):
            raise ValueError("CONTEXT_RECEIPT_INVALID")
    unsigned = dict(receipt)
    observed = unsigned.pop("receipt_sha256", None)
    if observed != sha256_bytes(canonical_json_bytes(unsigned)):
        raise ValueError("CONTEXT_RECEIPT_HASH_MISMATCH")


def rebuild_context_receipt(
    root: Path, *, task_id: str, task_contract: str, route: str
) -> dict[str, Any]:
    module = load_delivery_harness_runtime(root)
    if task_id == "CONTROL-PR" and isinstance(task_contract, str) and task_contract.startswith("pr/"):
        builder = getattr(module, "build_live_pr_head_receipt", None)
        if not callable(builder):
            raise ValueError("CONTEXT_RUNTIME_UNAVAILABLE")
        try:
            pr_number = int(task_contract.split("/", 1)[1])
        except (IndexError, ValueError):
            raise ValueError("CONTEXT_RUNTIME_INVALID") from None
        result = builder(root, pr_number=pr_number, route=route)
    else:
        builder = getattr(module, "build_context_receipt", None)
        if not callable(builder):
            raise ValueError("CONTEXT_RUNTIME_UNAVAILABLE")
        result = builder(
            root, task_id=task_id, task_contract=task_contract, route=route
        )
    if not isinstance(result, dict):
        raise ValueError("CONTEXT_RUNTIME_INVALID")
    return result


def verify_live_context_receipt(
    root: Path,
    receipt: dict[str, Any],
    *,
    route: str,
    context_builder=rebuild_context_receipt,
) -> dict[str, Any]:
    verify_context_receipt(root, receipt)
    if is_live_pr_head(receipt):
        rebuilt = context_builder(
            root,
            task_id="CONTROL-PR",
            task_contract=f"pr/{receipt['control_pr']['pr_number']}",
            route=route,
        )
    else:
        task = receipt.get("task")
        if not isinstance(task, dict):
            raise ValueError("CONTEXT_RECEIPT_INVALID")
        rebuilt = context_builder(
            root,
            task_id=task.get("task_id"),
            task_contract=task.get("path"),
            route=route,
        )
    verify_context_receipt(root, rebuilt)
    if canonical_json_bytes(receipt) != canonical_json_bytes(rebuilt):
        raise ValueError("CONTEXT_RECEIPT_LIVE_MISMATCH")
    return rebuilt


def delivery_inventory_sha256(
    root: Path,
    *,
    expected_base: str,
    head: str,
    excluded_paths: set[str],
    runner=run_read,
) -> str:
    if not (
        re.fullmatch(r"[0-9a-f]{40}", expected_base)
        and re.fullmatch(r"[0-9a-f]{40}", head)
    ):
        raise ValueError("DELIVERY_INVENTORY_INVALID")
    try:
        output = runner(
            [
                "git", "diff", "--name-status", "--no-renames", "-z",
                f"{expected_base}...{head}",
            ],
            root,
        )
        diff_entries = decode_git_name_status(output)
    except ValueError:
        raise ValueError("DELIVERY_INVENTORY_INVALID") from None
    entries: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    observed_excluded: set[str] = set()
    for status, relative in diff_entries:
        if relative in excluded_paths:
            observed_excluded.add(relative)
            excluded.append({"status": status, "path": relative})
            continue
        if status == "D":
            entries.append({"status": status, "path": relative, "sha256": None})
            continue
        try:
            payload = runner(["git", "show", f"{head}:{relative}"], root)
        except ValueError:
            raise ValueError("DELIVERY_INVENTORY_INVALID") from None
        entries.append(
            {"status": status, "path": relative, "sha256": sha256_bytes(payload)}
        )
    if observed_excluded != excluded_paths or not any(
        item["sha256"] is not None for item in entries
    ):
        raise ValueError("DELIVERY_INVENTORY_INVALID")
    inventory = {
        "expected_base": expected_base,
        "entries": sorted(entries, key=lambda item: item["path"]),
        "excluded_evidence": sorted(excluded, key=lambda item: item["path"]),
    }
    return sha256_bytes(canonical_json_bytes(inventory))


def bound_delivery_evidence(
    root: Path,
    receipt: dict[str, Any],
    *,
    expected_base: str | None = None,
    head: str | None = None,
    runner=run_read,
    inventory_builder=delivery_inventory_sha256,
) -> dict[str, Any]:
    if is_live_pr_head(receipt):
        return {
            "factory_fit_pass": True,
            "active_stop_conditions": [],
            "triggers": {
                "auth_or_access_recovery": False,
                "material_owner_decision": False,
                "user_only_activation": False,
                "external_material_action": False,
                "unresolved_safety_or_truth_conflict": False,
            },
        }
    denied = {
        "factory_fit_pass": False,
        "active_stop_conditions": ["DELIVERY_EVIDENCE_NOT_GROUNDED"],
        "triggers": {
            "auth_or_access_recovery": False,
            "material_owner_decision": False,
            "user_only_activation": False,
            "external_material_action": False,
            "unresolved_safety_or_truth_conflict": True,
        },
    }
    task = receipt.get("task")
    if not isinstance(task, dict):
        return denied
    completion_paths: list[str] = []
    for selected in receipt.get("selected", []):
        if not isinstance(selected, dict) or selected.get("semantic_role") != "DELIVERY_EVIDENCE":
            continue
        relative = selected.get("path")
        if not isinstance(relative, str):
            continue
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != selected.get("sha256"):
            continue
        try:
            candidate = decode_json_mapping(
                path.read_bytes(), "DELIVERY_EVIDENCE_INVALID"
            )
        except (OSError, ValueError):
            continue
        if candidate.get("schema") == "smial.delivery-completion-evidence":
            completion_paths.append(relative)
    if len(completion_paths) != 1:
        return denied
    try:
        completion_path = safe_evidence_json_path(completion_paths[0])
    except ValueError:
        return denied
    for selected in receipt.get("selected", []):
        if not isinstance(selected, dict) or selected.get("semantic_role") != "DELIVERY_EVIDENCE":
            continue
        relative = selected.get("path")
        if relative != completion_path:
            continue
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != selected.get("sha256"):
            continue
        try:
            evidence = decode_json_mapping(
                path.read_bytes(), "DELIVERY_EVIDENCE_INVALID"
            )
        except (OSError, ValueError):
            continue
        required_evidence = {
            "schema", "schema_version", "acceptance_id", "as_of", "task_id",
            "state_change", "implementation_bindings", "active_stop_conditions",
            "owner_attention_triggers", "factory_fit", "validation", "non_claims",
            "side_effects",
        }
        optional_evidence = {
            "base_main", "owner_approvals", "cloud_bundle_mode",
            "cloud_bundle_required_by_harness", "cloud_bundle_smoke_required",
            "project_sources_disposition", "capability_radar_now",
        }
        if not (
            required_evidence <= set(evidence) <= required_evidence | optional_evidence
            and evidence.get("schema") == "smial.delivery-completion-evidence"
            and evidence.get("schema_version") == "1.0"
            and evidence.get("task_id") == task.get("task_id")
            and isinstance(evidence.get("acceptance_id"), str)
            and bool(evidence["acceptance_id"])
            and isinstance(evidence.get("as_of"), str)
            and isinstance(evidence.get("state_change"), str)
            and evidence.get("cloud_bundle_mode") == "OWNER_MANAGED_OPTIONAL_EXPORT"
            and evidence.get("cloud_bundle_required_by_harness") is False
            and evidence.get("cloud_bundle_smoke_required") is False
            and isinstance(evidence.get("non_claims"), list)
            and all(isinstance(item, str) and bool(item) for item in evidence["non_claims"])
            and isinstance(evidence.get("side_effects"), dict)
        ):
            continue
        if (
            ("base_main" in evidence and not (
                isinstance(evidence["base_main"], str)
                and re.fullmatch(r"[0-9a-f]{40}", evidence["base_main"])
            ))
            or ("owner_approvals" in evidence and not (
                isinstance(evidence["owner_approvals"], list)
                and all(isinstance(item, str) and bool(item) for item in evidence["owner_approvals"])
                and len(set(evidence["owner_approvals"])) == len(evidence["owner_approvals"])
            ))
            or ("cloud_bundle_mode" in evidence and evidence["cloud_bundle_mode"] != "OWNER_MANAGED_OPTIONAL_EXPORT")
            or ("cloud_bundle_required_by_harness" in evidence and evidence["cloud_bundle_required_by_harness"] is not False)
            or ("cloud_bundle_smoke_required" in evidence and evidence["cloud_bundle_smoke_required"] is not False)
            or ("project_sources_disposition" in evidence and not (
                isinstance(evidence["project_sources_disposition"], dict)
                and set(evidence["project_sources_disposition"]) in (
                    {"kind"}, {"kind", "reason"}
                )
                and evidence["project_sources_disposition"].get("kind")
                in {"NO_CHANGE", "RELEASE_CANDIDATE", "ACTIVATION_RECEIPT"}
                and (
                    "reason" not in evidence["project_sources_disposition"]
                    or (
                        isinstance(evidence["project_sources_disposition"]["reason"], str)
                        and bool(evidence["project_sources_disposition"]["reason"])
                    )
                )
            ))
            or ("capability_radar_now" in evidence and not (
                isinstance(evidence["capability_radar_now"], str)
                and bool(evidence["capability_radar_now"])
            ))
        ):
            continue
        if not (
            isinstance(expected_base, str)
            and isinstance(head, str)
            and evidence.get("base_main") == expected_base
        ):
            continue
        bindings = evidence.get("implementation_bindings")
        if not isinstance(bindings, dict) or not bindings:
            continue
        bindings_match = True
        for binding_path, expected_sha in bindings.items():
            if not isinstance(binding_path, str) or not isinstance(expected_sha, str):
                bindings_match = False
                break
            candidate = (root / binding_path).resolve()
            if root.resolve() not in candidate.parents or not candidate.is_file():
                bindings_match = False
                break
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha:
                bindings_match = False
                break
        if not bindings_match:
            continue
        validation = evidence.get("validation")
        if not isinstance(validation, dict) or set(validation) != {
            "targeted", "independent_review", "full_gate", "github_ci",
            "project_checks",
        }:
            continue
        review_binding = validation.get("independent_review")
        if not isinstance(review_binding, dict) or set(review_binding) != {
            "path", "sha256", "verdict"
        } or review_binding.get("verdict") != "PASS":
            continue
        try:
            review_relative = safe_evidence_json_path(review_binding["path"])
        except (KeyError, TypeError, ValueError):
            continue
        binding = evidence.get("factory_fit")
        if not isinstance(binding, dict) or set(binding) != {
            "path", "sha256", "verdict"
        } or binding.get("verdict") != "PASS":
            continue
        try:
            fit_relative = safe_evidence_json_path(binding["path"])
            if len({completion_path, review_relative, fit_relative}) != 3:
                raise ValueError("DELIVERY_EVIDENCE_PATH_INVALID")
            inventory_sha = inventory_builder(
                root,
                expected_base=expected_base,
                head=head,
                excluded_paths={completion_path, review_relative, fit_relative},
                runner=runner,
            )
        except (KeyError, TypeError, ValueError):
            continue
        review_path = (root / review_relative).resolve()
        if root.resolve() not in review_path.parents or not review_path.is_file():
            continue
        review_payload = review_path.read_bytes()
        if hashlib.sha256(review_payload).hexdigest() != review_binding.get("sha256"):
            continue
        try:
            review = decode_json_mapping(
                review_payload, "DELIVERY_REVIEW_EVIDENCE_INVALID"
            )
        except ValueError:
            continue
        if set(review) != {
            "schema", "schema_version", "review_id", "as_of", "task_id",
            "reviewed_bindings_sha256", "reviewed_inventory_sha256",
            "required_roles", "reviews",
            "verdict", "non_claims",
        } or not (
            review.get("schema") == "smial.delivery-independent-review-evidence"
            and review.get("schema_version") == "1.0"
            and review.get("task_id") == task.get("task_id")
            and review.get("verdict") == "PASS"
            and review.get("reviewed_bindings_sha256")
            == sha256_bytes(canonical_json_bytes(bindings))
            and review.get("reviewed_inventory_sha256") == inventory_sha
            and isinstance(review.get("review_id"), str)
            and bool(review["review_id"])
            and isinstance(review.get("as_of"), str)
            and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", review["as_of"])
            and isinstance(review.get("required_roles"), list)
            and all(isinstance(item, str) for item in review["required_roles"])
            and set(review["required_roles"]) == REQUIRED_REVIEW_ROLES
            and len(review["required_roles"]) == len(REQUIRED_REVIEW_ROLES)
            and isinstance(review.get("reviews"), list)
            and isinstance(review.get("non_claims"), list)
            and all(isinstance(item, str) and bool(item) for item in review["non_claims"])
            and len(set(review["non_claims"])) == len(review["non_claims"])
            and "NO_CRYPTOGRAPHIC_REVIEWER_IDENTITY" in review["non_claims"]
        ):
            continue
        reviews_by_role: dict[str, list[dict[str, Any]]] = {}
        review_shape_valid = True
        for item in review["reviews"]:
            if not isinstance(item, dict) or set(item) != {
                "role", "verdict", "findings"
            } or not (
                isinstance(item.get("role"), str)
                and item.get("verdict") in {"PASS", "NOT_READY"}
                and isinstance(item.get("findings"), list)
                and all(
                    isinstance(finding, str) and bool(finding)
                    for finding in item["findings"]
                )
            ):
                review_shape_valid = False
                break
            reviews_by_role.setdefault(item["role"], []).append(item)
        if not (
            review_shape_valid
            and set(reviews_by_role) == REQUIRED_REVIEW_ROLES
            and len(review["reviews"]) == len(REQUIRED_REVIEW_ROLES)
            and all(
                len(reviews_by_role[role]) == 1
                and reviews_by_role[role][0]["verdict"] == "PASS"
                for role in REQUIRED_REVIEW_ROLES
            )
            and not review_records_single_agent_fallback(review)
        ):
            continue
        fit_path = (root / fit_relative).resolve()
        if root.resolve() not in fit_path.parents or not fit_path.is_file():
            continue
        payload = fit_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != binding.get("sha256"):
            continue
        try:
            fit = decode_json_mapping(
                payload, "DELIVERY_FACTORY_FIT_EVIDENCE_INVALID"
            )
        except ValueError:
            continue
        expected_fit_keys = {
            "schema", "schema_version", "review_id", "as_of", "task_id",
            "reviewed_bindings_sha256", "reviewed_inventory_sha256", "mode",
            "verdict", "dimensions", "capability_radar", "recovery", "limits",
        }
        expected_dimensions = {
            "mission", "flexibility_and_history", "context_efficiency",
            "research_truth", "owner_operability", "execution_to_cashflow",
            "monitoring_and_recovery", "build_vs_buy", "security", "red_team",
        }
        if (
            isinstance(fit, dict)
            and set(fit) == expected_fit_keys
            and fit.get("schema") == "smial.delivery-harness-factory-fit"
            and fit.get("schema_version") == "1.0"
            and isinstance(fit.get("review_id"), str)
            and bool(fit["review_id"])
            and isinstance(fit.get("as_of"), str)
            and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", fit["as_of"])
            and fit.get("task_id") == task.get("task_id")
            and fit.get("mode") in {"FAST_PATH", "FULL_REVIEW"}
            and fit.get("verdict") == "PASS"
            and fit.get("reviewed_bindings_sha256")
            == sha256_bytes(canonical_json_bytes(bindings))
            and fit.get("reviewed_inventory_sha256") == inventory_sha
            and isinstance(fit.get("dimensions"), dict)
            and set(fit["dimensions"]) == expected_dimensions
            and all(isinstance(value, str) and bool(value) for value in fit["dimensions"].values())
            and isinstance(fit.get("capability_radar"), dict)
            and set(fit["capability_radar"]) == {"now", "watch"}
            and all(isinstance(value, str) and bool(value) for value in fit["capability_radar"].values())
            and isinstance(fit.get("recovery"), str)
            and bool(fit["recovery"])
            and isinstance(fit.get("limits"), list)
            and all(isinstance(item, str) and bool(item) for item in fit["limits"])
            and len(set(fit["limits"])) == len(fit["limits"])
        ):
            stops = evidence.get("active_stop_conditions")
            triggers = evidence.get("owner_attention_triggers")
            if not (
                str(validation.get("targeted", "")).startswith("PASS_")
                and validation.get("full_gate")
                == "ENFORCED_BY_PROJECT_BOUND_VALIDATION"
                and validation.get("github_ci")
                == "ENFORCED_LIVE_AT_GUARDED_MERGE"
                and isinstance(validation.get("project_checks"), list)
                and all(
                    isinstance(item, str) and item.startswith("PASS_")
                    for item in validation["project_checks"]
                )
            ):
                continue
            expected_trigger_keys = {
                "auth_or_access_recovery",
                "material_owner_decision",
                "user_only_activation",
                "external_material_action",
                "unresolved_safety_or_truth_conflict",
            }
            if not isinstance(stops, list) or any(
                not isinstance(item, str) for item in stops
            ):
                continue
            if not isinstance(triggers, dict) or set(triggers) != expected_trigger_keys:
                continue
            if any(type(value) is not bool for value in triggers.values()):
                continue
            return {
                "factory_fit_pass": True,
                "active_stop_conditions": stops,
                "triggers": triggers,
            }
    return denied


def github_review_threads_resolved(
    repository: str, pr_number: int, root: Path, runner=run_read
) -> bool:
    owner, name = repository.split("/", 1)
    query = (
        "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved}pageInfo{hasNextPage}}}}}"
    )
    value = decode_json_mapping(
        runner(
            [
                "gh", "api", "graphql", "-f", f"query={query}",
                "-F", f"owner={owner}", "-F", f"name={name}",
                "-F", f"number={pr_number}",
            ],
            root,
        ),
        "PR_REVIEW_THREADS_INVALID",
    )
    try:
        threads = value["data"]["repository"]["pullRequest"]["reviewThreads"]
        nodes = threads["nodes"]
        has_next = threads["pageInfo"]["hasNextPage"]
    except (KeyError, TypeError):
        raise ValueError("PR_REVIEW_THREADS_INVALID") from None
    return has_next is False and isinstance(nodes, list) and all(
        isinstance(item, dict) and item.get("isResolved") is True for item in nodes
    )


def build_grounded_merge_request(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    route: str,
    actor: str,
    approval_phrase: str,
    context_receipt: dict[str, Any],
    runner=run_read,
    context_builder=rebuild_context_receipt,
    evidence_builder=bound_delivery_evidence,
    delivery_checks_builder=build_delivery_checks,
) -> dict[str, Any]:
    if type(pr_number) is not int or pr_number < 1:
        raise ValueError("PR_NUMBER_INVALID")
    origin = runner(["git", "remote", "get-url", "origin"], root).decode("utf-8", errors="strict").strip()
    local_head = runner(["git", "rev-parse", "HEAD"], root).decode("ascii", errors="strict").strip()
    local_tree = runner(["git", "rev-parse", "HEAD^{tree}"], root).decode("ascii", errors="strict").strip()
    dirty = bool(runner(["git", "status", "--porcelain=v1"], root).strip())
    try:
        origin_repository = github_repository_from_origin(origin)
    except ValueError:
        origin_repository = None
    if origin_repository != repository or dirty:
        raise ValueError("LOCAL_REPOSITORY_IDENTITY_MISMATCH")
    context_receipt = verify_live_context_receipt(
        root,
        context_receipt,
        route=route,
        context_builder=context_builder,
    )
    expected_base, expected_upstream_oid, _, default_branch = guarded_delivery_scope(
        root, context_receipt, repository=repository, runner=runner
    )
    if live_default_branch_oid(
        root, repository=repository, branch=default_branch, runner=runner
    ) != expected_upstream_oid:
        raise ValueError("FROZEN_BASE_MISMATCH")
    policy = load_base_bound_policy(
        root, expected_base=expected_base, runner=runner
    )
    pr = decode_json_mapping(runner(["gh", "pr", "view", str(pr_number), "--repo", repository, "--json", "number,headRefOid,headRefName,baseRefName,mergeable,reviewDecision,state,isDraft"], root), "PR_READBACK_INVALID")
    check_policy = policy["github_checks"]
    workflow = check_policy["workflow"]
    workflow_file = check_policy["workflow_file"]
    pull_request_event = check_policy["pull_request_event"]
    required_jobs = check_policy["required_jobs"]
    accepted_conclusion = check_policy["accepted_conclusion"]
    workflow_runs = json.loads(
        runner(
            [
                "gh", "run", "list", "--repo", repository,
                "--commit", local_head, "--workflow", workflow_file,
                "--event", pull_request_event, "--limit", "20",
                "--json", "headSha,status,conclusion,databaseId,event,workflowName",
            ],
            root,
        ).decode("utf-8", errors="strict")
    )
    if not isinstance(workflow_runs, list):
        raise ValueError("PR_READBACK_INVALID")
    latest_run = next(
        (
            item for item in workflow_runs
            if isinstance(item, dict)
            and item.get("headSha") == local_head
            and item.get("workflowName") == workflow
            and item.get("event") == pull_request_event
        ),
        None,
    )
    run_id = latest_run.get("databaseId") if isinstance(latest_run, dict) else None
    run = decode_json_mapping(
        runner(
            [
                "gh", "run", "view", str(run_id), "--repo", repository,
                "--json", "headSha,status,conclusion,event,workflowName,jobs",
            ],
            root,
        ),
        "PR_CI_READBACK_INVALID",
    ) if type(run_id) is int else {}
    jobs = run.get("jobs")
    jobs_by_name: dict[str, list[dict[str, Any]]] = {}
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and isinstance(job.get("name"), str):
                jobs_by_name.setdefault(job["name"], []).append(job)
    ci_pass = (
        isinstance(latest_run, dict)
        and latest_run.get("status") == "completed"
        and latest_run.get("conclusion") == accepted_conclusion
        and run.get("headSha") == local_head
        and run.get("status") == "completed"
        and run.get("conclusion") == accepted_conclusion
        and run.get("event") == pull_request_event
        and run.get("workflowName") == workflow
        and all(
            len(jobs_by_name.get(job, [])) == 1
            and jobs_by_name[job][0].get("status") == "completed"
            and jobs_by_name[job][0].get("conclusion") == accepted_conclusion
            for job in required_jobs
        )
    )
    no_unresolved = github_review_threads_resolved(repository, pr_number, root, runner)
    repository_state = decode_json_mapping(
        runner(["gh", "api", f"repos/{repository}"], root),
        "REPOSITORY_READBACK_INVALID",
    )
    receipt_repository = context_receipt.get("repository") if isinstance(context_receipt, dict) else None
    receipt_route = context_receipt.get("route") if isinstance(context_receipt, dict) else None
    receipt_hash = context_receipt.get("receipt_sha256") if isinstance(context_receipt, dict) else None
    context_bound = (
        isinstance(receipt_repository, dict)
        and receipt_repository.get("name") == repository
        and receipt_repository.get("head") == local_head
        and receipt_repository.get("tree") == local_tree
        and receipt_route == route
        and isinstance(receipt_hash, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", receipt_hash))
        and (
            not is_live_pr_head(context_receipt)
            or context_receipt["control_pr"]["pr_number"] == pr_number
        )
    )
    exact_head = (
        pr.get("number") == pr_number
        and pr.get("headRefOid") == local_head
        and pr.get("baseRefName") == default_branch
        and isinstance(pr.get("headRefName"), str)
        and bool(pr.get("headRefName"))
    )
    evidence = evidence_builder(
        root,
        context_receipt,
        expected_base=expected_base,
        head=local_head,
        runner=runner,
    )
    delivery_checks = delivery_checks_builder(
        root,
        context_receipt=context_receipt,
        local_head=local_head,
        local_tree=local_tree,
        ci_pass=ci_pass,
        runner=runner,
    )
    if set(delivery_checks) != {
        "required_tests_pass", "full_gate_pass", "write_set_pass", "secret_scan_pass"
    } or any(type(value) is not bool for value in delivery_checks.values()):
        raise ValueError("DELIVERY_CHECKS_INVALID")
    active_stops = evidence["active_stop_conditions"]
    triggers = evidence["triggers"]
    review_state_pass = pr.get("reviewDecision") != "CHANGES_REQUESTED"
    machine = {
        "pr_number": pr_number, "observed_head_sha": str(pr.get("headRefOid", "")), "observed_tree_sha": local_tree,
        "context_receipt_sha256": receipt_hash if isinstance(receipt_hash, str) else "0" * 64, "context_route": receipt_route if receipt_route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"} else route,
        "exact_pr_head_bound": exact_head, "context_receipt_bound": context_bound,
        "required_tests_pass": delivery_checks["required_tests_pass"],
        "ci_exact_head_pass": exact_head and ci_pass,
        "full_gate_pass": delivery_checks["full_gate_pass"],
        "factory_fit_pass": evidence["factory_fit_pass"],
        "write_set_pass": delivery_checks["write_set_pass"],
        "secret_scan_pass": delivery_checks["secret_scan_pass"],
        "mergeable": pr.get("mergeable") == "MERGEABLE" and pr.get("state") == "OPEN" and pr.get("isDraft") is False,
        "no_unresolved_reviews": no_unresolved and review_state_pass,
        "standard_merge": True,
        "branch_preserved": repository_state.get("delete_branch_on_merge") is False,
        "settings_unchanged": True,
    }
    phrase_match = re.search(r"PR #([1-9][0-9]*), head ([0-9a-f]{40})", approval_phrase)
    approval_pr = int(phrase_match.group(1)) if phrase_match else pr_number
    approval_head = phrase_match.group(2) if phrase_match else local_head
    return {
        "schema": "smial.owner-attention-request", "schema_version": "2.0", "repository": repository,
        "route": route, "actor": actor, "action_class": "MERGE_PULL_REQUEST", "scope_bound": True,
        "stricter_stop_active": bool(active_stops),
        "triggers": triggers,
        "owner_approval": {
            "phrase": approval_phrase,
            "pr_number": approval_pr,
            "head_sha": approval_head,
            "context_receipt_sha256": receipt_hash if isinstance(receipt_hash, str) else "0" * 64,
            "context_route": receipt_route if receipt_route in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"} else route,
        },
        "merge_checks": machine,
    }


def build_post_merge_receipt(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    route: str,
    context_receipt: dict[str, Any],
    submission_receipt: dict[str, Any],
    runner=run_read,
    context_builder=rebuild_context_receipt,
) -> dict[str, Any]:
    verified_context = verify_live_context_receipt(
        root, context_receipt, route=route, context_builder=context_builder
    )
    expected_base, expected_upstream_oid, _, default_branch = guarded_delivery_scope(
        root, verified_context, repository=repository, runner=runner
    )
    repository_state = verified_context.get("repository")
    approved_head = (
        repository_state.get("head") if isinstance(repository_state, dict) else None
    )
    if not isinstance(approved_head, str) or re.fullmatch(r"[0-9a-f]{40}", approved_head) is None:
        raise ValueError("POST_MERGE_READBACK_FAILED")
    submission_keys = {
        "schema", "schema_version", "decision", "reasons", "repository",
        "pr_number", "approved_head", "context_receipt_sha256", "route",
        "merge_submitted", "merge_commit", "post_merge_ci", "branch_deleted",
        "settings_changed", "receipt_sha256",
    }
    unsigned_submission = dict(submission_receipt)
    submission_hash = unsigned_submission.pop("receipt_sha256", None)
    if not (
        set(submission_receipt) == submission_keys
        and submission_receipt.get("schema") == "smial.guarded-merge-submission"
        and submission_receipt.get("schema_version") == "1.0"
        and submission_receipt.get("decision") == "AUTONOMOUS"
        and isinstance(submission_receipt.get("reasons"), list)
        and all(
            isinstance(item, str) and bool(item)
            for item in submission_receipt["reasons"]
        )
        and submission_receipt.get("repository") == repository
        and submission_receipt.get("pr_number") == pr_number
        and submission_receipt.get("approved_head") == approved_head
        and submission_receipt.get("context_receipt_sha256")
        == verified_context["receipt_sha256"]
        and submission_receipt.get("route") == route
        and submission_receipt.get("merge_submitted") is True
        and isinstance(submission_receipt.get("merge_commit"), str)
        and re.fullmatch(r"[0-9a-f]{40}", submission_receipt["merge_commit"])
        and submission_receipt.get("post_merge_ci")
        == "PENDING_EXACT_MAIN_READBACK"
        and submission_receipt.get("branch_deleted") is False
        and submission_receipt.get("settings_changed") is False
        and submission_hash
        == sha256_bytes(canonical_json_bytes(unsigned_submission))
    ):
        raise ValueError("GUARDED_SUBMISSION_INVALID")
    try:
        origin = runner(["git", "remote", "get-url", "origin"], root).decode(
            "utf-8", errors="strict"
        ).strip()
        if github_repository_from_origin(origin) != repository:
            raise ValueError("POST_MERGE_READBACK_FAILED")
    except (UnicodeDecodeError, ValueError):
        raise ValueError("POST_MERGE_READBACK_FAILED") from None
    pr = decode_json_mapping(
        runner(
            [
                "gh", "pr", "view", str(pr_number), "--repo", repository,
                "--json", "number,state,mergedAt,headRefOid,headRefName,baseRefName,mergeCommit",
            ],
            root,
        ),
        "POST_MERGE_READBACK_INVALID",
    )
    merge_commit = pr.get("mergeCommit")
    pr_merge_oid = merge_commit.get("oid") if isinstance(merge_commit, dict) else None
    head_branch = pr.get("headRefName")
    if not (
        pr.get("number") == pr_number
        and pr.get("state") == "MERGED"
        and isinstance(pr.get("mergedAt"), str)
        and pr.get("headRefOid") == approved_head
        and pr.get("baseRefName") == default_branch
        and isinstance(head_branch, str)
        and bool(head_branch)
        and isinstance(pr_merge_oid, str)
        and re.fullmatch(r"[0-9a-f]{40}", pr_merge_oid) is not None
    ):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    remote = runner(
        ["git", "ls-remote", "origin", f"refs/heads/{default_branch}"], root
    ).decode("ascii", errors="strict").strip()
    parts = remote.split()
    if len(parts) != 2 or parts[1] != f"refs/heads/{default_branch}":
        raise ValueError("POST_MERGE_READBACK_FAILED")
    default_head = parts[0]
    head_remote = runner(
        ["git", "ls-remote", "origin", f"refs/heads/{head_branch}"], root
    ).decode("ascii", errors="strict").strip().split()
    if (
        len(head_remote) != 2
        or head_remote[0] != approved_head
        or head_remote[1] != f"refs/heads/{head_branch}"
    ):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    commit = decode_json_mapping(
        runner(["gh", "api", f"repos/{repository}/commits/{default_head}"], root),
        "POST_MERGE_COMMIT_READBACK_INVALID",
    )
    parents = commit.get("parents")
    parent_oids = [
        item.get("sha") for item in parents if isinstance(item, dict)
    ] if isinstance(parents, list) else []
    try:
        policy = load_base_bound_policy(
            root, expected_base=expected_base, runner=runner
        )
    except ValueError:
        raise ValueError("POST_MERGE_READBACK_FAILED") from None
    if not _policy_v2_is_closed(policy):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    check_policy = policy["github_checks"]
    workflow = check_policy["workflow"]
    workflow_file = check_policy["workflow_file"]
    required_jobs = check_policy["required_jobs"]
    accepted_conclusion = check_policy["accepted_conclusion"]
    runs_value = json.loads(runner([
        "gh", "run", "list", "--repo", repository, "--commit", default_head,
        "--workflow", workflow_file, "--event", "push",
        "--limit", "20",
        "--json", "headSha,status,conclusion,databaseId,event,workflowName",
    ], root).decode("utf-8", errors="strict"))
    if not isinstance(runs_value, list):
        raise ValueError("MAIN_CI_READBACK_INVALID")
    latest = next((
        item for item in runs_value
        if isinstance(item, dict)
        and item.get("headSha") == default_head
        and item.get("event") == "push"
        and item.get("workflowName") == workflow
    ), None)
    run_id = latest.get("databaseId") if isinstance(latest, dict) else None
    run = decode_json_mapping(
        runner(
            [
                "gh", "run", "view", str(run_id), "--repo", repository,
                "--json", "headSha,status,conclusion,event,workflowName,jobs",
            ],
            root,
        ),
        "MAIN_CI_READBACK_INVALID",
    ) if type(run_id) is int else {}
    jobs = run.get("jobs")
    jobs_by_name: dict[str, list[dict[str, Any]]] = {}
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and isinstance(job.get("name"), str):
                jobs_by_name.setdefault(job["name"], []).append(job)
    ci_pass = (
        isinstance(latest, dict)
        and latest.get("status") == "completed"
        and latest.get("conclusion") == accepted_conclusion
        and run.get("headSha") == default_head
        and run.get("status") == "completed"
        and run.get("conclusion") == accepted_conclusion
        and run.get("event") == "push"
        and run.get("workflowName") == workflow
        and all(
            len(jobs_by_name.get(job, [])) == 1
            and jobs_by_name[job][0].get("status") == "completed"
            and jobs_by_name[job][0].get("conclusion") == accepted_conclusion
            for job in required_jobs
        )
    )
    if (
        default_head != pr_merge_oid
        or submission_receipt["merge_commit"] != pr_merge_oid
        or parent_oids != [expected_upstream_oid, approved_head]
        or not ci_pass
    ):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    receipt: dict[str, Any] = {
        "schema": "smial.delivery-post-merge-receipt",
        "schema_version": "1.1",
        "repository": repository,
        "pr_number": pr_number,
        "approved_head": approved_head,
        "context_receipt_sha256": verified_context["receipt_sha256"],
        "submission_receipt_sha256": submission_hash,
        "route": route,
        "head_branch": head_branch,
        "base_branch": default_branch,
        "base_head": expected_upstream_oid,
        "default_branch_head": default_head,
        "default_branch_ci": {
            "run_id": run_id,
            "conclusion": run.get("conclusion"),
        },
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def execute_guarded_merge(
    root: Path,
    *,
    repository: str,
    pr_number: int,
    route: str,
    actor: str,
    approval_phrase: str,
    context_receipt: dict[str, Any],
    runner=run_read,
    context_builder=rebuild_context_receipt,
    evidence_builder=bound_delivery_evidence,
    delivery_checks_builder=build_delivery_checks,
) -> dict[str, Any]:
    request = build_grounded_merge_request(
        root,
        repository=repository,
        pr_number=pr_number,
        route=route,
        actor=actor,
        approval_phrase=approval_phrase,
        context_receipt=context_receipt,
        runner=runner,
        context_builder=context_builder,
        evidence_builder=evidence_builder,
        delivery_checks_builder=delivery_checks_builder,
    )
    verified_context = verify_live_context_receipt(
        root, context_receipt, route=route, context_builder=context_builder
    )
    expected_base, expected_upstream_oid, _, default_branch = guarded_delivery_scope(
        root, verified_context, repository=repository, runner=runner
    )
    policy = load_base_bound_policy(
        root, expected_base=expected_base, runner=runner
    )
    observed_head = request["merge_checks"]["observed_head_sha"]
    observed_tree = request["merge_checks"]["observed_tree_sha"]
    if not candidate_identity_unchanged(
        root, head=observed_head, tree=observed_tree, runner=runner
    ) or live_default_branch_oid(
        root, repository=repository, branch=default_branch, runner=runner
    ) != expected_upstream_oid:
        return {
            "schema": "smial.guarded-merge-submission",
            "schema_version": "1.0",
            "decision": "DENY",
            "reasons": ["CANDIDATE_OR_BASE_CHANGED_BEFORE_MERGE"],
            "merge_submitted": False,
        }
    result = evaluate(request, policy)
    if result["decision"] != "AUTONOMOUS":
        return {
            "schema": "smial.guarded-merge-submission",
            "schema_version": "1.0",
            "decision": result["decision"],
            "reasons": result["reasons"],
            "merge_submitted": False,
        }
    rebound_policy = load_base_bound_policy(
        root, expected_base=expected_base, runner=runner
    )
    if canonical_json_bytes(rebound_policy) != canonical_json_bytes(policy) or not (
        candidate_identity_unchanged(
            root, head=observed_head, tree=observed_tree, runner=runner
        )
        and live_default_branch_oid(
            root, repository=repository, branch=default_branch, runner=runner
        ) == expected_upstream_oid
    ):
        return {
            "schema": "smial.guarded-merge-submission",
            "schema_version": "1.0",
            "decision": "DENY",
            "reasons": ["CANDIDATE_OR_BASE_CHANGED_BEFORE_MERGE"],
            "merge_submitted": False,
        }
    runner(
        [
            "gh", "pr", "merge", str(pr_number), "--repo", repository,
            "--merge", "--match-head-commit",
            request["merge_checks"]["observed_head_sha"],
        ],
        root,
    )
    merged = decode_json_mapping(
        runner(
            [
                "gh", "pr", "view", str(pr_number), "--repo", repository,
                "--json", "number,state,mergedAt,headRefOid,headRefName,baseRefName,mergeCommit",
            ],
            root,
        ),
        "POST_MERGE_READBACK_INVALID",
    )
    commit = merged.get("mergeCommit")
    merge_oid = commit.get("oid") if isinstance(commit, dict) else None
    if (
        merged.get("state") != "MERGED"
        or merged.get("number") != pr_number
        or merged.get("headRefOid") != request["merge_checks"]["observed_head_sha"]
        or merged.get("baseRefName") != default_branch
        or not isinstance(merged.get("headRefName"), str)
        or not merged.get("headRefName")
        or not isinstance(merged.get("mergedAt"), str)
        or not isinstance(merge_oid, str)
        or re.fullmatch(r"[0-9a-f]{40}", merge_oid) is None
    ):
        raise ValueError("POST_MERGE_READBACK_FAILED")
    receipt: dict[str, Any] = {
        "schema": "smial.guarded-merge-submission",
        "schema_version": "1.0",
        "decision": "AUTONOMOUS",
        "reasons": result["reasons"],
        "repository": repository,
        "pr_number": pr_number,
        "approved_head": request["merge_checks"]["observed_head_sha"],
        "context_receipt_sha256": request["merge_checks"]["context_receipt_sha256"],
        "route": route,
        "merge_submitted": True,
        "merge_commit": merge_oid,
        "post_merge_ci": "PENDING_EXACT_MAIN_READBACK",
        "branch_deleted": False,
        "settings_changed": False,
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def decision(value: str, *reasons: str, version: str = "1.0") -> dict[str, Any]:
    return {
        "schema": "smial.owner-attention-decision",
        "schema_version": version,
        "decision": value,
        "reasons": list(reasons),
    }


def _evaluate_v1(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema") != REQUEST_SCHEMA:
        return decision("DENY", "INVALID_REQUEST_SCHEMA")
    if str(request.get("schema_version")) != REQUEST_VERSION:
        return decision("DENY", "INVALID_REQUEST_VERSION")

    route = request.get("route")
    actor = request.get("actor")
    action_class = request.get("action_class")
    route_policy = policy.get("route_authority", {}).get(route)
    if not isinstance(route_policy, dict):
        return decision("DENY", "UNKNOWN_ROUTE")
    if actor not in route_policy.get("allowed_actors", []):
        return decision("DENY", "ACTOR_NOT_ALLOWED_FOR_ROUTE")
    if request.get("scope_bound") is not True:
        return decision("DENY", "SCOPE_NOT_BOUND")

    if action_class == "MERGE_PULL_REQUEST" and actor == "CURSOR":
        return decision("DENY", "CURSOR_MERGE_FORBIDDEN")

    triggers = request.get("triggers")
    if not isinstance(triggers, dict):
        return decision("DENY", "TRIGGERS_NOT_BOUND")
    triggered_reasons = [
        trigger_policy["reason"]
        for trigger, trigger_policy in policy.get(
            "owner_attention_triggers", {}
        ).items()
        if triggers.get(trigger) is True
    ]
    if triggered_reasons:
        return decision("OWNER_ATTENTION_REQUIRED", *triggered_reasons)
    if request.get("stricter_stop_active") is True:
        return decision("OWNER_ATTENTION_REQUIRED", "STRICTER_STOP_ACTIVE")

    if action_class == "MERGE_PULL_REQUEST":
        checks = request.get("merge_checks")
        if not isinstance(checks, dict):
            return decision("DENY", "MERGE_CHECKS_NOT_BOUND")
        for check in policy.get("merge_preconditions", []):
            if checks.get(check) is not True:
                return decision("DENY", f"MERGE_CHECK_FAILED:{check}")
        if (
            route == "LOCAL_WORK_CODEX"
            and actor == "CODEX"
            and route_policy.get("ordinary_merge")
            == "AUTONOMOUS_AFTER_MACHINE_GATE"
        ):
            return decision("AUTONOMOUS", "LOCAL_CODEX_MERGE_GATE_PASS")
        return decision(
            "OWNER_ATTENTION_REQUIRED", "ROUTE_HAS_NO_CODEX_AUTO_MERGE"
        )

    if action_class not in route_policy.get("autonomous_action_classes", []):
        return decision("DENY", "ACTION_CLASS_NOT_AUTONOMOUS_FOR_ROUTE")
    return decision("AUTONOMOUS", "ROUTINE_IN_ENVELOPE")


def validate_exact_merge_approval(
    request: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    approval = request.get("owner_approval")
    checks = request.get("merge_checks")
    if not isinstance(approval, dict):
        return ["EXACT_MERGE_APPROVAL_REQUIRED"]
    if not isinstance(checks, dict):
        return ["MERGE_CHECKS_NOT_BOUND"]
    pattern = policy["merge_approval"]["exact_phrase_pattern"]
    match = re.fullmatch(pattern, approval["phrase"])
    if match is None:
        return ["MERGE_APPROVAL_PHRASE_MISMATCH"]
    phrase_pr = int(match.group(1))
    phrase_head = match.group(2)
    if request["repository"] != policy["repository"]:
        return ["MERGE_REPOSITORY_MISMATCH"]
    if not (
        phrase_pr == approval["pr_number"] == checks["pr_number"]
        and phrase_head == approval["head_sha"] == checks["observed_head_sha"]
        and approval["context_receipt_sha256"] == checks["context_receipt_sha256"]
        and approval["context_route"] == checks["context_route"] == request["route"]
    ):
        return ["MERGE_IDENTITY_MISMATCH"]
    return []


def _request_v2_has_exact_types(request: dict[str, Any]) -> bool:
    if type(request.get("scope_bound")) is not bool:
        return False
    if type(request.get("stricter_stop_active")) is not bool:
        return False
    triggers = request.get("triggers")
    if not isinstance(triggers, dict) or any(
        type(value) is not bool for value in triggers.values()
    ):
        return False
    approval = request.get("owner_approval")
    if isinstance(approval, dict) and type(approval.get("pr_number")) is not int:
        return False
    checks = request.get("merge_checks")
    if isinstance(checks, dict):
        if type(checks.get("pr_number")) is not int:
            return False
        for key, value in checks.items():
            if key not in {"pr_number", "observed_head_sha", "observed_tree_sha", "context_receipt_sha256", "context_route"} and type(value) is not bool:
                return False
    return True


def _policy_v2_is_closed(policy: dict[str, Any]) -> bool:
    required = {
        "schema", "schema_version", "policy_id", "as_of", "status", "owner",
        "repository", "purpose", "decisions", "owner_attention_triggers",
        "route_authority", "merge_approval", "github_checks",
        "merge_preconditions", "post_merge", "invariants", "non_claims",
    }
    if set(policy) != required:
        return False
    checks = policy.get("github_checks")
    routes = policy.get("route_authority")
    return bool(
        policy.get("schema") == "smial.owner-attention-gate"
        and policy.get("schema_version") == "2.0"
        and policy.get("policy_id") == "OWNER_ATTENTION_GATE_V2"
        and policy.get("owner") == "GOAL_OWNER"
        and isinstance(policy.get("repository"), str)
        and isinstance(checks, dict)
        and set(checks)
        == {
            "workflow", "workflow_file", "pull_request_event",
            "required_jobs", "accepted_conclusion",
        }
        and isinstance(checks.get("workflow"), str)
        and bool(checks["workflow"])
        and isinstance(checks.get("workflow_file"), str)
        and re.fullmatch(
            r"\.github/workflows/[A-Za-z0-9._/-]+\.ya?ml",
            checks["workflow_file"],
        )
        and checks.get("pull_request_event")
        in {"pull_request", "pull_request_target"}
        and checks.get("accepted_conclusion") == "success"
        and isinstance(checks.get("required_jobs"), list)
        and checks["required_jobs"]
        and isinstance(routes, dict)
        and set(routes)
        == {
            "DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY", "DESIGN_ONLY",
            "LEGACY_GITHUB_BATON_DORMANT",
        }
        and isinstance(policy.get("merge_preconditions"), list)
    )


def _request_v2_is_closed(request: dict[str, Any]) -> bool:
    required = {
        "schema", "schema_version", "repository", "route", "actor",
        "action_class", "scope_bound", "stricter_stop_active", "triggers",
        "owner_approval", "merge_checks",
    }
    if set(request) != required:
        return False
    if not (
        request.get("schema") == "smial.owner-attention-request"
        and request.get("schema_version") == "2.0"
        and isinstance(request.get("repository"), str)
        and re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", request["repository"]
        )
        and request.get("route")
        in {
            "DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY", "DESIGN_ONLY",
            "LEGACY_GITHUB_BATON_DORMANT",
        }
        and request.get("actor") in {"GPT", "CODEX", "CURSOR"}
        and request.get("action_class")
        in {"READ_ONLY", "ROUTINE_ENGINEERING", "GITHUB_TRANSPORT", "MERGE_PULL_REQUEST"}
    ):
        return False
    triggers = request.get("triggers")
    if not isinstance(triggers, dict) or set(triggers) != {
        "auth_or_access_recovery", "material_owner_decision",
        "user_only_activation", "external_material_action",
        "unresolved_safety_or_truth_conflict",
    }:
        return False
    approval = request.get("owner_approval")
    if approval is not None and (
        not isinstance(approval, dict)
        or set(approval)
        != {"phrase", "pr_number", "head_sha", "context_receipt_sha256", "context_route"}
    ):
        return False
    if isinstance(approval, dict) and not (
        isinstance(approval.get("phrase"), str)
        and type(approval.get("pr_number")) is int
        and isinstance(approval.get("head_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", approval["head_sha"])
        and isinstance(approval.get("context_receipt_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", approval["context_receipt_sha256"])
        and approval.get("context_route")
        in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"}
    ):
        return False
    checks = request.get("merge_checks")
    if checks is not None and (
        not isinstance(checks, dict)
        or set(checks)
        != {
            "pr_number", "observed_head_sha", "observed_tree_sha",
            "context_receipt_sha256", "context_route", "exact_pr_head_bound",
            "context_receipt_bound", "required_tests_pass", "ci_exact_head_pass",
            "full_gate_pass", "factory_fit_pass", "write_set_pass",
            "secret_scan_pass", "mergeable", "no_unresolved_reviews",
            "standard_merge", "branch_preserved", "settings_unchanged",
        }
    ):
        return False
    if isinstance(checks, dict) and not (
        isinstance(checks.get("observed_head_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", checks["observed_head_sha"])
        and isinstance(checks.get("observed_tree_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", checks["observed_tree_sha"])
        and isinstance(checks.get("context_receipt_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", checks["context_receipt_sha256"])
        and checks.get("context_route")
        in {"DIRECT_CODEX_DELIVERY", "DIRECT_CURSOR_DELIVERY"}
    ):
        return False
    return _request_v2_has_exact_types(request)


def _evaluate_v2(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if not _policy_v2_is_closed(policy):
        return decision("DENY", "INVALID_POLICY_SCHEMA", version="2.0")
    if not _request_v2_is_closed(request):
        return decision("DENY", "INVALID_REQUEST_SCHEMA", version="2.0")

    route = request["route"]
    actor = request["actor"]
    action_class = request["action_class"]
    route_policy = policy["route_authority"].get(route)
    if not isinstance(route_policy, dict):
        return decision("DENY", "UNKNOWN_ROUTE", version="2.0")
    if actor not in route_policy["allowed_actors"]:
        return decision("DENY", "ACTOR_NOT_ALLOWED_FOR_ROUTE", version="2.0")
    if request["scope_bound"] is not True:
        return decision("DENY", "SCOPE_NOT_BOUND", version="2.0")

    if action_class == "MERGE_PULL_REQUEST":
        if route_policy["ordinary_merge"] == "FORBIDDEN":
            return decision("DENY", "ROUTE_MERGE_FORBIDDEN", version="2.0")
        checks = request["merge_checks"]
        if checks is not None:
            assert isinstance(checks, dict)
            for check in policy["merge_preconditions"]:
                if checks.get(check) is not True:
                    return decision(
                        "DENY", f"MERGE_CHECK_FAILED:{check}", version="2.0"
                    )
        reasons = [
            reason
            for trigger, reason in policy["owner_attention_triggers"].items()
            if request["triggers"][trigger] is True
        ]
        if reasons:
            return decision("OWNER_ATTENTION_REQUIRED", *reasons, version="2.0")
        if request["stricter_stop_active"] is True:
            return decision(
                "OWNER_ATTENTION_REQUIRED", "STRICTER_STOP_ACTIVE", version="2.0"
            )
        if request["owner_approval"] is None:
            return decision(
                "OWNER_ATTENTION_REQUIRED",
                "EXACT_MERGE_APPROVAL_REQUIRED",
                version="2.0",
            )
        approval_errors = validate_exact_merge_approval(request, policy)
        if approval_errors:
            return decision("DENY", *approval_errors, version="2.0")
        checks = request["merge_checks"]
        assert isinstance(checks, dict)
        return decision(
            "AUTONOMOUS", "DIRECT_AGENT_EXACT_MERGE_GATE_PASS", version="2.0"
        )

    reasons = [
        reason
        for trigger, reason in policy["owner_attention_triggers"].items()
        if request["triggers"][trigger] is True
    ]
    if reasons:
        return decision("OWNER_ATTENTION_REQUIRED", *reasons, version="2.0")
    if request["stricter_stop_active"] is True:
        return decision(
            "OWNER_ATTENTION_REQUIRED", "STRICTER_STOP_ACTIVE", version="2.0"
        )
    if action_class not in route_policy["autonomous_action_classes"]:
        return decision("DENY", "ACTION_CLASS_NOT_AUTONOMOUS_FOR_ROUTE", version="2.0")
    return decision("AUTONOMOUS", "ROUTINE_IN_ENVELOPE", version="2.0")


def evaluate(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if str(policy.get("schema_version")) == "1.0":
        return _evaluate_v1(request, policy)
    if str(policy.get("schema_version")) == "2.0":
        return _evaluate_v2(request, policy)
    return decision("DENY", "UNSUPPORTED_POLICY_VERSION", version="2.0")


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f"mapping required: {path}") from None
    if not isinstance(value, dict):
        raise ValueError(f"mapping required: {path}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request", type=Path)
    mode.add_argument("--guarded-merge", action="store_true")
    mode.add_argument("--post-merge-readback", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--repository")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--route")
    parser.add_argument("--actor")
    parser.add_argument("--approval-phrase")
    parser.add_argument("--context-receipt", type=Path)
    parser.add_argument("--submission-receipt", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.post_merge_readback:
        required = (
            args.repository,
            args.pr_number,
            args.route,
            args.context_receipt,
            args.submission_receipt,
        )
        if any(value is None for value in required):
            raise ValueError("POST_MERGE_READBACK_ARGUMENTS_REQUIRED")
        receipt = decode_json_mapping(
            args.context_receipt.read_bytes(), "CONTEXT_RECEIPT_INVALID"
        )
        submission = decode_json_mapping(
            args.submission_receipt.read_bytes(), "GUARDED_SUBMISSION_INVALID"
        )
        result = build_post_merge_receipt(
            args.root.resolve(),
            repository=args.repository,
            pr_number=args.pr_number,
            route=args.route,
            context_receipt=receipt,
            submission_receipt=submission,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.guarded_merge:
        required = (
            args.repository,
            args.pr_number,
            args.route,
            args.actor,
            args.approval_phrase,
            args.context_receipt,
        )
        if any(value is None for value in required):
            raise ValueError("GUARDED_MERGE_ARGUMENTS_REQUIRED")
        receipt = decode_json_mapping(
            args.context_receipt.read_bytes(), "CONTEXT_RECEIPT_INVALID"
        )
        result = execute_guarded_merge(
            args.root.resolve(),
            repository=args.repository,
            pr_number=args.pr_number,
            route=args.route,
            actor=args.actor,
            approval_phrase=args.approval_phrase,
            context_receipt=receipt,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("merge_submitted") is True else 2
    if args.request is None:
        raise ValueError("REQUEST_REQUIRED")
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    result = evaluate(request, load_mapping(args.policy))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] != "DENY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
