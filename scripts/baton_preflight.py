#!/usr/bin/env python3
"""Offline/live Atom Contract preflight. Live GitHub read requires explicit flag."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import (  # noqa: E402
    BatonContractError,
    EXPECTED_REPO,
    extract_contract_payload_bytes,
    resolve_repo_relative_file,
    validate_expected_hash,
    validate_expected_revision,
    validate_issue_number,
    validate_payload,
)

# Exact origin URL forms that normalize to EXPECTED_REPO. No substring matching.
ALLOWED_ORIGIN_URLS = frozenset(
    {
        "https://github.com/lancerbeta/solana-alpha-lab.git",
        "https://github.com/lancerbeta/solana-alpha-lab",
        "git@github.com:lancerbeta/solana-alpha-lab.git",
        "ssh://git@github.com/lancerbeta/solana-alpha-lab.git",
    }
)


def normalize_origin_full_name(origin_url: str) -> str | None:
    """Return EXPECTED_REPO only for exact allowed origin URL forms."""
    if not isinstance(origin_url, str):
        return None
    candidate = origin_url.strip()
    if candidate in ALLOWED_ORIGIN_URLS:
        return EXPECTED_REPO
    return None


def evaluate_local_repository_identity(
    *,
    toplevel: str | None,
    origin_url: str | None,
    expected_root: Path,
) -> list[str]:
    """Return sanitized identity mismatch codes. Never embed absolute user paths."""
    codes: list[str] = []
    if toplevel is None:
        codes.append("local_repository_identity_mismatch:toplevel_unavailable")
    else:
        try:
            observed = Path(toplevel).resolve()
            expected = expected_root.resolve()
        except (OSError, RuntimeError, ValueError):
            codes.append("local_repository_identity_mismatch:toplevel_unresolvable")
        else:
            if observed != expected:
                # Do not include absolute local paths in the evidence string.
                codes.append("local_repository_identity_mismatch:toplevel")
    if origin_url is None:
        codes.append("local_repository_identity_mismatch:origin_missing")
    else:
        normalized = normalize_origin_full_name(origin_url)
        if normalized != EXPECTED_REPO:
            # Never embed raw origin_url (may contain credentials/userinfo).
            codes.append("local_repository_identity_mismatch:origin_not_allowed")
    return codes


def check_local_repository_identity() -> list[str]:
    """Observe local git toplevel + origin and compare to this repository."""
    try:
        toplevel = read_local_toplevel()
    except RuntimeError:
        toplevel = None
    try:
        origin_url = read_local_origin_url()
    except RuntimeError:
        origin_url = None
    return evaluate_local_repository_identity(
        toplevel=toplevel,
        origin_url=origin_url,
        expected_root=ROOT,
    )


def read_local_toplevel() -> str:
    return run_git(["rev-parse", "--show-toplevel"])


def read_local_origin_url() -> str:
    return run_git(["remote", "get-url", "origin"])


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git_failed:{' '.join(args)}:{completed.returncode}")
    return completed.stdout.strip()


def dirty_count() -> int:
    text = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return len([line for line in text.splitlines() if line.strip()])


def fetch_issue_body_live(repo: str, issue: int) -> tuple[str, int, int]:
    """One exact gh issue view. No search/list/discovery."""
    completed = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue),
            "--repo",
            repo,
            "--json",
            "body",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"gh_issue_view_failed:{completed.returncode}")
    payload = json.loads(completed.stdout)
    body = payload.get("body")
    if not isinstance(body, str):
        raise RuntimeError("gh_issue_body_missing")
    return body, 1, 0


def build_result(
    *,
    result: str,
    repository: str,
    issue: int,
    revision: int,
    contract_hash_ok: bool,
    authority_class: str,
    base: dict[str, Any],
    observed_vs_expected: list[str],
    github_reads: int,
    github_writes: int,
) -> dict[str, Any]:
    return {
        "check": "BATON_PREFLIGHT",
        "result": result,
        "repository": repository,
        "issue": issue,
        "revision": revision,
        "contract_hash_ok": contract_hash_ok,
        "authority_class": authority_class,
        "base": base,
        "observed_vs_expected": observed_vs_expected,
        "side_effects": {
            "github_reads": github_reads,
            "github_writes": github_writes,
            "local_writes": 0,
        },
        "next_boundary": "STOP_BEFORE_MUTATION",
    }


def preflight(
    *,
    repository: str,
    issue: int,
    revision: int,
    expected_contract_sha256: str,
    issue_body: str | bytes | None,
    allow_github_read: bool,
) -> dict[str, Any]:
    github_reads = 0
    github_writes = 0
    observed_vs_expected: list[str] = []
    try:
        validate_issue_number(issue)
        validate_expected_revision(revision)
        validate_expected_hash(expected_contract_sha256)
    except BatonContractError as exc:
        return build_result(
            result="BLOCKED",
            repository=repository,
            issue=issue,
            revision=revision,
            contract_hash_ok=False,
            authority_class="",
            base={},
            observed_vs_expected=[exc.code],
            github_reads=0,
            github_writes=0,
        )

    if repository != EXPECTED_REPO:
        return build_result(
            result="BLOCKED",
            repository=repository,
            issue=issue,
            revision=revision,
            contract_hash_ok=False,
            authority_class="",
            base={},
            observed_vs_expected=[f"repository:{repository}!={EXPECTED_REPO}"],
            github_reads=0,
            github_writes=0,
        )

    identity_errors = check_local_repository_identity()
    if identity_errors:
        return build_result(
            result="BLOCKED",
            repository=repository,
            issue=issue,
            revision=revision,
            contract_hash_ok=False,
            authority_class="",
            base={},
            observed_vs_expected=identity_errors,
            github_reads=0,
            github_writes=0,
        )

    if issue_body is None:
        if not allow_github_read:
            return build_result(
                result="BLOCKED_AUTHORITY",
                repository=repository,
                issue=issue,
                revision=revision,
                contract_hash_ok=False,
                authority_class="",
                base={},
                observed_vs_expected=["github_read_not_authorized"],
                github_reads=0,
                github_writes=0,
            )
        issue_body, github_reads, github_writes = fetch_issue_body_live(
            repository, issue
        )

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = run_git(["rev-parse", "HEAD"])
    tree = run_git(["rev-parse", "HEAD^{tree}"])
    upstream = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"])
    dirty = dirty_count()
    base = {
        "branch": branch,
        "head": head,
        "tree": tree,
        "upstream": upstream,
        "dirty": dirty,
    }

    try:
        # Offline bytes stay bytes; live GitHub body may remain str after JSON decode.
        payload = extract_contract_payload_bytes(issue_body)
        contract = validate_payload(
            payload,
            expected_contract_sha256=expected_contract_sha256,
            expected_revision=revision,
        )
    except BatonContractError as exc:
        code = exc.code
        result = (
            "BLOCKED_CONTRACT_MISMATCH"
            if "mismatch" in code
            else "BLOCKED"
        )
        return build_result(
            result=result,
            repository=repository,
            issue=issue,
            revision=revision,
            contract_hash_ok=False,
            authority_class="",
            base=base,
            observed_vs_expected=[str(exc)],
            github_reads=github_reads,
            github_writes=github_writes,
        )

    repo = contract["repository"]
    checks = [
        ("base_branch", branch, repo["base_branch"]),
        ("base_head", head, repo["base_head"]),
        ("base_tree", tree, repo["base_tree"]),
        ("expected_upstream", upstream, repo["expected_upstream"]),
    ]
    for name, observed, expected in checks:
        if observed != expected:
            observed_vs_expected.append(f"{name}:{observed}!={expected}")
    if repo.get("require_clean_worktree") and dirty != 0:
        observed_vs_expected.append(f"dirty:{dirty}!=0")
    if observed_vs_expected:
        return build_result(
            result="BLOCKED",
            repository=repository,
            issue=issue,
            revision=revision,
            contract_hash_ok=True,
            authority_class=contract["execution"]["authority_class"],
            base=base,
            observed_vs_expected=observed_vs_expected,
            github_reads=github_reads,
            github_writes=github_writes,
        )

    return build_result(
        result="PASS_READONLY",
        repository=repository,
        issue=issue,
        revision=revision,
        contract_hash_ok=True,
        authority_class=contract["execution"]["authority_class"],
        base=base,
        observed_vs_expected=[],
        github_reads=github_reads,
        github_writes=github_writes,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baton preflight (offline/live)")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument("--expected-contract-sha256", required=True)
    parser.add_argument("--issue-body-file", default="")
    parser.add_argument("--allow-github-read", action="store_true")
    args = parser.parse_args(argv)

    issue_body: str | bytes | None = None
    if args.issue_body_file:
        try:
            body_path = resolve_repo_relative_file(args.issue_body_file, root=ROOT)
        except BatonContractError as exc:
            result = build_result(
                result="BLOCKED",
                repository=args.repository,
                issue=args.issue,
                revision=args.revision,
                contract_hash_ok=False,
                authority_class="",
                base={},
                observed_vs_expected=[str(exc)],
                github_reads=0,
                github_writes=0,
            )
            print(json.dumps(result, indent=2))
            return 2
        # Exact offline Issue bytes — no text newline normalization.
        issue_body = body_path.read_bytes()

    result = preflight(
        repository=args.repository,
        issue=args.issue,
        revision=args.revision,
        expected_contract_sha256=args.expected_contract_sha256,
        issue_body=issue_body,
        allow_github_read=args.allow_github_read,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["result"] == "PASS_READONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
