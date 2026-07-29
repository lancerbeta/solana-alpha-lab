#!/usr/bin/env python3
"""Validate exact TASK-01/02 pre-Git imports and ARCH-INTENT-001."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from validate_catalog import load_and_validate

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'docs/evidence/task03_atom4b_pre_git_import_receipt.json'
EXPECTED_IMPORTS = {'docs/evidence/pre_git/task01/CHECKSUMS_SHA256.txt': '860fd944322d41d6271d8134fc57f034e874191887f87fa794f8456ec2f95442', 'docs/evidence/pre_git/task01/data_option_tiers_v1.yaml': 'f19c0263f94b19135d91d2e61f1f14d158b48c4bd030a514d640041df0210d13', 'docs/evidence/pre_git/task01/hypothesis_data_coverage_matrix_v1.md': '5ba0b904d4ca3942cb701fa28ccbc7c35c8ce580385c6766a2fc4596b2c16814', 'docs/evidence/pre_git/task01/provider_account_checklist_v1.md': '6cd7c4486e2b9562be2404737c3ae37579bfd5c49faa4dfe974b2350478d49aa', 'docs/evidence/pre_git/task01/provider_cost_snapshot_v1.csv': 'ad3339fcf07e4dfb70290803d9ae0c589308ae9792e57e0f4d78cf55f9e52888', 'docs/evidence/pre_git/task01/provider_decision_v1.md': '7ed7462f2b9da4aa7bae31469d2423584b89bd7930767ea4cfdd073980a75ec3', 'docs/evidence/pre_git/task01/provider_smoke_spec_v1.yaml': 'a42c8a20dc31101ce134e277e1a612539f7161411ea8261bb109e5cc64d24ddc', 'docs/evidence/pre_git/task01/reuse_candidate_registry.yaml': '7651eae8991fba3bba22a98cb33b8760c2daa468ee677cdd3423c36a4d458d0a', 'docs/evidence/pre_git/task01/sources_v1.yaml': '48bbe25253a46857f7307ac06df81b42e208a4f336fa220fb48da31846848a3f', 'docs/evidence/pre_git/task01/task_01_completion_record_v1.md': 'f378899260c0e93db8e8075373f90feb1349a675790783b8a519b139a6981f12', 'docs/evidence/pre_git/task01/task_01_final_gap_audit_v1.md': '1ccb45b7275fda9870f57330b82373f8d7bd0fd68e74579b3c032f851aa0f5b2', 'docs/evidence/pre_git/task01/validation_report.txt': '5cadcb942eeb583a39aa6a7bb1f82169f9e67809ff9925d448f3fb1c2199edb3', 'docs/evidence/pre_git/task02/CHECKSUMS_SHA256.txt': 'ed1de0a6a0c30e251c32bd4dbf9ddeb04efc2a28de297ac0c43376fd4c0d4647', 'docs/evidence/pre_git/task02/TASK02_COMPLETION_SUMMARY.md': '3a917f3b6d7e79cda949b49576b51f9b9a87363dd2829cf0605e3c96345f3cd7', 'docs/evidence/pre_git/task02/bootstrap_check.py': 'd53dc4f51fd41ddb817f1e3cf54b9282bfa2ea83eb1c036e0314830b5b24bfdc', 'docs/evidence/pre_git/task02/env_report.txt': '44691c228f19ef6b01580318655461b0191e6fdae9418a15fd3a459847b0fb83', 'docs/evidence/pre_git/task02/operator_observation_receipt.json': '98af4b66c5ff9b885e9afe8774780750d8c6c5efff8a167fdd072d0523991f4e', 'docs/evidence/pre_git/task02/task_02_workstation_bootstrap.md': '3dab690b72008fb242349c5257e8cc2e5ed4fa0fcaeb3c372084eb5e437454a0', 'docs/evidence/pre_git/task02/tool_versions.json': '518e5757fab6711a4364cfc2707e656c913b498d48143d9d529cf4a130367c62', 'docs/evidence/pre_git/task02/validation_receipt.json': '5b50b7c0574d323b8dede7e10456832296ce5ac168cd8859e27c4be4d2707270'}
TASK01_BUNDLE_SHA = '857e87242d9a765f0b39f2ad266a8ec3e2da488b9e019d048d7a0c7a1a304e34'
TASK02_BUNDLE_SHA = 'c0530da2bbf4c33953c86264ae1bb4074b80f41990506901feee92cdd92d6149'
PRE_GIT_EXTERNAL_BUNDLE_IDS = {
    "BUNDLE-TASK01-COMPLETION-001",
    "BUNDLE-TASK02-COMPLETION-001",
}
ARCH_PATH = 'docs/architecture/intents/ARCH-INTENT-001-hypothesis-factory-and-regime-aware-orchestration.md'
ARCH_SHA = '59f810a75bce0c9a55f3e7dd751744a06d2e4a19a0378f47b08fb2b2bc2edad6'
EXACT_IMPORT_WHITESPACE_POLICY = (
    "PRESERVE_EXACT_BYTES_HASH_VERIFIED_STYLE_EXEMPT"
)
EXPECTED_TRAILING_NEWLINE_COUNTS = {
    "docs/evidence/pre_git/task01/task_01_completion_record_v1.md": 2,
    "docs/evidence/pre_git/task01/validation_report.txt": 2,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def secret_like(text: str) -> bool:
    private = "PRIVATE" + " KEY"
    patterns = (
        re.compile(r"-----BEGIN [A-Z0-9 ]*" + private + r"-----"),
        re.compile(r"\b" + ("s" + "k") + r"-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
        re.compile(r"\b" + ("g" + "h") + r"[pousr]_[A-Za-z0-9]{20,}\b"),
        re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+"),
    )
    return any(pattern.search(text) for pattern in patterns)


def assert_check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(name + ((": " + detail) if detail else ""))
    print(f"{name}: PASS")


def pre_git_external_bundles(assets: dict[str, dict]) -> dict[str, dict]:
    """Return only the two historical bundles owned by the pre-Git import."""
    return {
        asset_id: asset
        for asset_id, asset in assets.items()
        if asset_id in PRE_GIT_EXTERNAL_BUNDLE_IDS
    }


def validate() -> None:
    snapshot = load_and_validate()
    assert_check("exact_import_file_count", len(EXPECTED_IMPORTS) == 20)
    for relative, expected in sorted(EXPECTED_IMPORTS.items()):
        path = ROOT / relative
        assert_check(f"file_exists:{relative}", path.is_file())
        assert_check(f"file_hash:{relative}", sha256(path) == expected)
        raw = path.read_bytes()
        assert_check(f"lf_only:{relative}", b"\r" not in raw)
        text = raw.decode("utf-8")
        assert_check(f"secret_path_scan:{relative}", not secret_like(text))
        if relative in EXPECTED_TRAILING_NEWLINE_COUNTS:
            trailing_newlines = len(raw) - len(raw.rstrip(b"\n"))
            assert_check(
                f"exact_eof_newlines_preserved:{relative}",
                trailing_newlines
                == EXPECTED_TRAILING_NEWLINE_COUNTS[relative],
                str(trailing_newlines),
            )

    assert_check("task01_bundle_record", snapshot.assets["BUNDLE-TASK01-COMPLETION-001"]["integrity"]["sha256"] == TASK01_BUNDLE_SHA)
    assert_check("task02_bundle_record", snapshot.assets["BUNDLE-TASK02-COMPLETION-001"]["integrity"]["sha256"] == TASK02_BUNDLE_SHA)
    a028 = snapshot.assets["PRE-GIT-TASK01-A028"]
    assert_check("a028_bundle_only", a028["status"] == "BUNDLE_ONLY_SUPERSEDED" and a028["provenance"]["import_mode"] == "BUNDLE_ONLY" and not (ROOT / "docs/evidence/pre_git/task01/validate_task01_completion.py").exists())

    exact_records = [a for a in snapshot.assets.values() if a["asset_type"] == "pre_git_artifact" and a["provenance"]["import_mode"] == "EXACT_BYTES"]
    assert_check("catalog_exact_record_count", len(exact_records) == 20)
    historical_bundles = pre_git_external_bundles(snapshot.assets)
    assert_check(
        "external_bundle_count",
        set(historical_bundles) == PRE_GIT_EXTERNAL_BUNDLE_IDS
        and all(
            asset["asset_type"] == "external_bundle"
            for asset in historical_bundles.values()
        ),
    )
    assert_check("pre_git_availability_preserved", all(a["provenance"]["past_availability_claim"] == "PRESERVED" for a in exact_records))

    arch = snapshot.assets["ARCH-INTENT-001"]
    assert_check("architecture_intent_status", arch["status"] == "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
    assert_check("architecture_intent_hash", sha256(ROOT / ARCH_PATH) == ARCH_SHA)
    assert_check("architecture_intent_availability", arch["provenance"]["created_at"] == "2026-07-21" and arch["provenance"]["first_reliable_available_at"] == "2026-07-21" and arch["provenance"]["past_availability_claim"] == "NO_PAST_AVAILABILITY_CLAIM")
    text = (ROOT / ARCH_PATH).read_text(encoding="utf-8")
    for marker in ["advisory only", "first_reliable_available_at", "backfill does not create past availability", "L3 — automated lifecycle actions only after measured safety and economics gates"]:
        assert_check("architecture_marker", marker in text)

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    allow_pending = os.environ.get("TASK03_ALLOW_PENDING_IMPORT") == "1"
    assert_check("receipt_identity", receipt.get("task_id") == "TASK-03" and receipt.get("atom_id") == "TASK03-ATOM-4B" and (receipt.get("result") == "PASS" or (allow_pending and receipt.get("result") == "PENDING")))
    assert_check("receipt_source_bundles", receipt.get("task01_bundle_sha256") == TASK01_BUNDLE_SHA and receipt.get("task02_bundle_sha256") == TASK02_BUNDLE_SHA)
    assert_check("receipt_counts", receipt.get("imported_exact_file_count") == 20 and receipt.get("external_bundle_record_count") == 2 and receipt.get("bundle_only_record_count") == 1 and receipt.get("architecture_intent_count") == 1)
    assert_check(
        "receipt_exact_import_style_policy",
        receipt.get("exact_import_whitespace_policy")
        == EXACT_IMPORT_WHITESPACE_POLICY
        and receipt.get("exact_import_style_exempt_file_count") == 20,
    )
    if receipt.get("result") == "PASS":
        assert_check("receipt_import_hashes", receipt.get("imported_file_sha256") == EXPECTED_IMPORTS)
        assert_check("receipt_arch_hash", receipt.get("architecture_intent_sha256") == ARCH_SHA)


def main() -> int:
    print("=== TASK-03 ATOM 4B PRE-GIT IMPORT VALIDATION ===")
    try:
        validate()
    except Exception as exc:
        print("PRE_GIT_IMPORT_RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    print("task01_exact_bytes: 12")
    print("task02_exact_bytes: 8")
    print("pre_git_external_bundle_records: 2")
    print("bundle_only_records: 1")
    print("architecture_intents: 1")
    print("provenance_and_availability: PASS")
    print("PRE_GIT_IMPORT_RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
