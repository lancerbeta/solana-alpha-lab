#!/usr/bin/env python3
"""High-confidence repository secret scan with in-memory rejection tests."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patterns() -> dict[str, re.Pattern[str]]:
    backslash_b = r"\b"
    openai_prefix = "s" + "k"
    github_prefix = "g" + "h"
    jwt_prefix = "e" + "y" + "J"
    private_header = "PRIVATE" + " KEY"
    sensitive_names = (
        "api" + r"[_-]?" + "key"
        + "|access" + r"[_-]?" + "token"
        + "|auth" + r"[_-]?" + "token"
        + "|password"
        + "|secret"
    )

    return {
        "private_key_block": re.compile(
            r"-----BEGIN [A-Z0-9 ]*"
            + private_header
            + r"-----"
        ),
        "openai_key": re.compile(
            backslash_b
            + openai_prefix
            + r"-(?:proj-)?[A-Za-z0-9_-]{16,}"
            + backslash_b
        ),
        "github_token": re.compile(
            backslash_b
            + github_prefix
            + r"[pousr]_[A-Za-z0-9]{20,}"
            + backslash_b
        ),
        "jwt_like": re.compile(
            backslash_b
            + jwt_prefix
            + r"[A-Za-z0-9_-]{16,}\."
            + r"[A-Za-z0-9_-]{10,}\."
            + r"[A-Za-z0-9_-]{10,}"
            + backslash_b
        ),
        "credential_assignment": re.compile(
            r"(?i)(?:"
            + sensitive_names
            + r")[ \t]*[:=][ \t]*['\"]?"
            + r"[A-Za-z0-9+/=_-]{12,}"
        ),
        "credential_url": re.compile(
            r"https?://[^/\s:@]+:[^/\s@]+@"
        ),
    }


def findings_for_text(text: str) -> list[str]:
    return [
        name
        for name, pattern in patterns().items()
        if pattern.search(text)
    ]


def synthetic_cases() -> dict[str, str]:
    return {
        "openai_key": (
            ("s" + "k") + "-" + ("A" * 32)
        ),
        "github_token": (
            ("g" + "h" + "p") + "_" + ("B" * 36)
        ),
        "jwt_like": (
            ("e" + "y" + "J")
            + ("C" * 20)
            + "."
            + ("D" * 16)
            + "."
            + ("E" * 16)
        ),
        "private_key_block": (
            "-----BEGIN "
            + ("PRIVATE" + " KEY")
            + "-----"
        ),
        "credential_assignment": (
            ("api" + "_key")
            + "="
            + ("F" * 24)
        ),
        "credential_url": (
            "https://"
            + "user"
            + ":"
            + ("G" * 16)
            + "@example.invalid/path"
        ),
    }


def run_self_test() -> list[str]:
    failures: list[str] = []

    for expected_rule, candidate in synthetic_cases().items():
        observed = findings_for_text(candidate)
        if expected_rule not in observed:
            failures.append(f"not_rejected:{expected_rule}")

    allowed = (
        "API_KEY=\n"
        "FAKE_TOKEN_FOR_NEGATIVE_TEST\n"
        "USERPROFILE_PROJECTS/solana-alpha-lab\n"
    )
    if findings_for_text(allowed):
        failures.append("false_positive:allowed_control_text")

    return failures


def git_candidate_files() -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("git_inventory_failed")

    result: list[Path] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = ROOT / relative
        if path.is_file():
            result.append(path)

    return sorted(result)


def forbidden_local_config_files() -> list[str]:
    findings: list[str] = []

    direct = ROOT / ".env"
    if direct.exists():
        findings.append(".env")

    for path in ROOT.glob(".env.*"):
        if path.name != ".env.example":
            findings.append(path.name)

    return sorted(set(findings))


def scan_repository() -> list[str]:
    findings: list[str] = []

    for relative in forbidden_local_config_files():
        findings.append(f"{relative}:forbidden_local_config")

    for path in git_candidate_files():
        raw = path.read_bytes()
        if b"\0" in raw:
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(
                f"{path.relative_to(ROOT).as_posix()}:non_utf8_text"
            )
            continue

        relative = path.relative_to(ROOT).as_posix()
        for rule in findings_for_text(text):
            findings.append(f"{relative}:{rule}")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--self-test",
        action="store_true",
    )
    parser.add_argument(
        "--scan-repository",
        action="store_true",
    )
    args = parser.parse_args()

    if not args.self_test and not args.scan_repository:
        parser.error(
            "select --self-test and/or --scan-repository"
        )

    if args.self_test:
        failures = run_self_test()
        if failures:
            print("FAKE_SECRET_REJECTION: FAIL")
            for failure in failures:
                print(f"FAILURE: {failure}")
            return 1
        print("FAKE_SECRET_REJECTION: PASS")

    if args.scan_repository:
        findings = scan_repository()
        if findings:
            print("SECRET_SCAN: FAIL")
            for finding in findings:
                print(f"FINDING: {finding}")
            return 1
        print("SECRET_SCAN: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
