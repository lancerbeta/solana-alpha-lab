"""Canonical production software lineage. Git identity only, not runtime health."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

LEGACY_DIVERGENT_SOURCE = "aaf7f89c3bfc71de9d56618fdda0d3d69cfaf236"
DENY_CANONICAL_MAIN_UNVERIFIED = "DENY_CANONICAL_MAIN_UNVERIFIED"
DENY_NON_MAINLINE_TARGET = "DENY_NON_MAINLINE_TARGET"
DENY_LIVE_MAIN_DIVERGENCE = "DENY_LIVE_MAIN_DIVERGENCE"
DENY_CONVERGENCE_EVIDENCE_INCOMPLETE = "DENY_CONVERGENCE_EVIDENCE_INCOMPLETE"
DENY_ROLLBACK_NOT_MAINLINE = "DENY_ROLLBACK_NOT_MAINLINE"

GitRunner = Callable[[list[str]], str]


class ProductionLineageError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _default_git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ProductionLineageError(DENY_CANONICAL_MAIN_UNVERIFIED)
    return completed.stdout.strip()


def prove_canonical_main(repo: Path, claimed_main: str, *, git: GitRunner | None = None) -> str:
    run = git or (lambda args: _default_git(repo, args))
    if len(claimed_main) != 40:
        raise ProductionLineageError(DENY_CANONICAL_MAIN_UNVERIFIED)
    try:
        resolved = run(["rev-parse", "refs/heads/main"])
    except ProductionLineageError:
        resolved = run(["rev-parse", "main"])
    if resolved != claimed_main:
        raise ProductionLineageError(DENY_CANONICAL_MAIN_UNVERIFIED)
    return resolved


def first_parent_history(repo: Path, main_sha: str, *, git: GitRunner | None = None) -> set[str]:
    run = git or (lambda args: _default_git(repo, args))
    raw = run(["rev-list", "--first-parent", main_sha])
    return {line.strip() for line in raw.splitlines() if line.strip()}


def is_ancestor(repo: Path, older: str, newer: str, *, git: GitRunner | None = None) -> bool:
    run = git or (lambda args: _default_git(repo, args))
    completed_code = run(["merge-base", "--is-ancestor", older, newer])
    return completed_code == "0" or completed_code == ""


def _git_ancestor_status(repo: Path, older: str, newer: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=str(repo),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def load_convergence_evidence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    return payload


def evidence_sha256(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def convergence_evidence_ready(
    payload: dict[str, Any],
    *,
    expected_sha256: str,
    source_sha: str,
    target_sha: str,
) -> None:
    if evidence_sha256(payload) != expected_sha256:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if str(payload.get("source_sha") or "") != source_sha:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if str(payload.get("source_sha") or "") != LEGACY_DIVERGENT_SOURCE:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    dispositions = payload.get("dispositions")
    if not isinstance(dispositions, list) or not dispositions:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if any(str(item.get("disposition") or "") == "UNKNOWN" for item in dispositions if isinstance(item, dict)):
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if any(not isinstance(item, dict) or not item.get("disposition") for item in dispositions):
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if str(payload.get("target_binding") or "") != "CANONICAL_MAINLINE_CONTAINING_THIS_EVIDENCE":
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if target_sha == source_sha:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)


def classify_forward(
    *,
    repo: Path,
    main_sha: str,
    live_sha: str,
    target_sha: str,
    git: GitRunner | None = None,
) -> str:
    prove_canonical_main(repo, main_sha, git=git)
    history = first_parent_history(repo, main_sha, git=git)
    if target_sha not in history:
        raise ProductionLineageError(DENY_NON_MAINLINE_TARGET)
    if live_sha not in history:
        raise ProductionLineageError(DENY_LIVE_MAIN_DIVERGENCE)
    if git is None:
        ancestor = _git_ancestor_status(repo, live_sha, target_sha)
    else:
        ancestor = is_ancestor(repo, live_sha, target_sha, git=git)
    if not ancestor and live_sha != target_sha:
        raise ProductionLineageError(DENY_LIVE_MAIN_DIVERGENCE)
    return "CANONICAL_FORWARD"


def classify_rollback(
    *,
    repo: Path,
    main_sha: str,
    live_sha: str,
    rollback_sha: str,
    git: GitRunner | None = None,
) -> str:
    prove_canonical_main(repo, main_sha, git=git)
    history = first_parent_history(repo, main_sha, git=git)
    if live_sha not in history or rollback_sha not in history:
        raise ProductionLineageError(DENY_ROLLBACK_NOT_MAINLINE)
    return "CANONICAL_ROLLBACK"


def classify_legacy_convergence(
    *,
    repo: Path,
    main_sha: str,
    live_sha: str,
    target_sha: str,
    evidence: dict[str, Any],
    expected_evidence_sha256: str,
    git: GitRunner | None = None,
) -> str:
    prove_canonical_main(repo, main_sha, git=git)
    if live_sha != LEGACY_DIVERGENT_SOURCE:
        raise ProductionLineageError(DENY_LIVE_MAIN_DIVERGENCE)
    history = first_parent_history(repo, main_sha, git=git)
    if target_sha not in history:
        raise ProductionLineageError(DENY_NON_MAINLINE_TARGET)
    convergence_evidence_ready(
        evidence,
        expected_sha256=expected_evidence_sha256,
        source_sha=live_sha,
        target_sha=target_sha,
    )
    return "LEGACY_CONVERGENCE"
