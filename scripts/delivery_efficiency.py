#!/usr/bin/env python3
"""Classify delivery commit mix for ceremony-tax measurement."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTROL_ONLY_PREFIXES = (
    "delivery-harness/",
    "docs/tasks/CTRL-",
    "scripts/validate_",
    "scripts/delivery_harness.py",
    "scripts/harness_sync.py",
    "scripts/owner_attention_gate.py",
    "scripts/ci_fail_closed_messages.py",
    "scripts/delivery_efficiency.py",
    "scripts/validate_factory_static.py",
    "catalog/generated/",
    "docs/agent/DELIVERY_HARNESS",
    "docs/agent/DELIVERY_CONTEXT",
    "docs/evidence/control/",
    "control/owner_attention_gate_v2.yaml",
)

REPAIR_PREFIXES = (
    "catalog/assets/",
    "catalog/catalog_manifest.yaml",
    "docs/PROJECT_MAP.md",
    "docs/OPERATOR_NAVIGATION.md",
)

REPAIR_MESSAGE_NEEDLES = (
    "rebind",
    "harness_sync",
    "derived hash",
    "derived-hash",
    "hash drift",
    "catalog integrity",
    "evidence bind",
    "bind-evidence",
    "repair commit",
)


class DeliveryEfficiencyError(RuntimeError):
    """Git range cannot be classified."""


def _run_git(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise DeliveryEfficiencyError(f"git_failed:{args[0]}")
    return completed.stdout


def _commit_shas(base: str, head: str) -> list[str]:
    output = _run_git(["git", "rev-list", "--reverse", f"{base}..{head}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def _commit_paths(sha: str) -> set[str]:
    output = _run_git(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha])
    return {line.strip() for line in output.splitlines() if line.strip()}


def _commit_subject(sha: str) -> str:
    return _run_git(["git", "log", "-1", "--format=%s", sha]).strip().lower()


def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def classify_commit(*, paths: set[str], subject: str) -> str:
    if not paths:
        return "substantive"
    if all(_matches_prefix(path, CONTROL_ONLY_PREFIXES) for path in paths):
        return "control_only"
    if all(_matches_prefix(path, REPAIR_PREFIXES) for path in paths):
        return "repair"
    if any(needle in subject for needle in REPAIR_MESSAGE_NEEDLES):
        return "repair"
    return "substantive"


def compute_delivery_efficiency(*, base: str, head: str) -> dict[str, int | float]:
    if not re.fullmatch(r"[0-9a-f]{40}", base) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise DeliveryEfficiencyError("OID_INVALID")
    counts = {"substantive_commits": 0, "repair_commits": 0, "control_only_commits": 0}
    for sha in _commit_shas(base, head):
        bucket = classify_commit(paths=_commit_paths(sha), subject=_commit_subject(sha))
        key = {
            "substantive": "substantive_commits",
            "repair": "repair_commits",
            "control_only": "control_only_commits",
        }[bucket]
        counts[key] += 1
    total = sum(counts.values())
    repair_ratio = 0.0
    if total:
        repair_ratio = round(
            (counts["repair_commits"] + counts["control_only_commits"]) / total,
            4,
        )
    counts["repair_ratio"] = repair_ratio
    counts["total_commits"] = total
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="merge-base or expected_base oid")
    parser.add_argument("--head", default="HEAD", help="head oid or HEAD")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    head = args.head
    if head == "HEAD":
        head = _run_git(["git", "rev-parse", "HEAD"]).strip()
    try:
        payload = compute_delivery_efficiency(base=args.base, head=head)
    except DeliveryEfficiencyError as exc:
        print(f"DELIVERY_EFFICIENCY: FAIL", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("DELIVERY_EFFICIENCY: PASS")
        for key in (
            "substantive_commits",
            "repair_commits",
            "control_only_commits",
            "total_commits",
            "repair_ratio",
        ):
            print(f"{key}: {payload[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
