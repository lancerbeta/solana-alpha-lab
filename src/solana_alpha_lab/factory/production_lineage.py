"""Canonical production software lineage. Git identity only, not runtime health."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

LEGACY_DIVERGENT_SOURCE = "aaf7f89c3bfc71de9d56618fdda0d3d69cfaf236"
LEGACY_MERGE_BASE = "b652a66af554d96fb4ce3e2de3410c1d04e8bfd1"
LEGACY_DELTA_COMMITS = 28
LEGACY_DELTA_PATH_COUNT = 27
CONVERGENCE_EVIDENCE_PATH = (
    "docs/evidence/factory_production_line_convergence_v1/live_delta_disposition_v1.json"
)
CLOSED_DISPOSITIONS = frozenset(
    {
        "EQUIVALENT_ON_MAIN",
        "PORT_REQUIRED",
        "HISTORICAL_ONLY",
        "TEST_OR_EVIDENCE_ONLY",
        "OBSOLETE_NOT_CONSUMED",
    }
)
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


def read_convergence_evidence_blob(repo: Path, target_sha: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "show", f"{target_sha}:{CONVERGENCE_EVIDENCE_PATH}"],
        cwd=str(repo),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE) from exc
    if not isinstance(payload, dict):
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    return payload


def convergence_evidence_ready(
    payload: dict[str, Any],
    *,
    source_sha: str,
    target_sha: str,
    main_sha: str,
    supplemental_sha256: str = "",
) -> None:
    if target_sha != main_sha:
        raise ProductionLineageError(DENY_NON_MAINLINE_TARGET)
    if supplemental_sha256 and evidence_sha256(payload) != supplemental_sha256:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if str(payload.get("source_sha") or "") != source_sha:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if source_sha != LEGACY_DIVERGENT_SOURCE:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if str(payload.get("merge_base") or "") != LEGACY_MERGE_BASE:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    if int(payload.get("live_delta_commits") or 0) != LEGACY_DELTA_COMMITS:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    dispositions = payload.get("dispositions")
    if not isinstance(dispositions, list) or len(dispositions) != LEGACY_DELTA_PATH_COUNT:
        raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
    paths: list[str] = []
    for item in dispositions:
        if not isinstance(item, dict):
            raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
        disposition = str(item.get("disposition") or "")
        path = str(item.get("path") or "")
        if disposition not in CLOSED_DISPOSITIONS or not path:
            raise ProductionLineageError(DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)
        paths.append(path)
    if len(set(paths)) != LEGACY_DELTA_PATH_COUNT:
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
    supplemental_sha256: str = "",
    git: GitRunner | None = None,
) -> str:
    prove_canonical_main(repo, main_sha, git=git)
    if live_sha != LEGACY_DIVERGENT_SOURCE:
        raise ProductionLineageError(DENY_LIVE_MAIN_DIVERGENCE)
    if target_sha != main_sha:
        raise ProductionLineageError(DENY_NON_MAINLINE_TARGET)
    history = first_parent_history(repo, main_sha, git=git)
    if target_sha not in history:
        raise ProductionLineageError(DENY_NON_MAINLINE_TARGET)
    evidence = read_convergence_evidence_blob(repo, target_sha)
    convergence_evidence_ready(
        evidence,
        source_sha=live_sha,
        target_sha=target_sha,
        main_sha=main_sha,
        supplemental_sha256=supplemental_sha256,
    )
    return "LEGACY_CONVERGENCE"
