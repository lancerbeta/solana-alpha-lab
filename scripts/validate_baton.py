#!/usr/bin/env python3
"""Deterministic offline validation for the GitHub Baton machine layer."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import (  # noqa: E402
    BEGIN_MARKER,
    END_MARKER,
    BatonContractError,
    extract_contract_payload_bytes,
    parse_contract_json,
    path_in_managed_write_set,
    sha256_bytes,
    validate_expected_revision,
    validate_managed_write_entry,
    validate_payload,
    verify_out_of_band_hash,
)
from baton_receipt import (  # noqa: E402
    BatonReceiptError,
    semantic_validate_acceptance_receipt,
    semantic_validate_execution_receipt,
)
from baton_scope import (  # noqa: E402
    BatonScopeError,
    assert_path_contained,
    parse_porcelain_z,
)
import baton_preflight  # noqa: E402
from validate_baseline import (  # noqa: E402
    CanonicalRepositoryBytesError,
    canonical_catalog_integrity_sweep,
    canonical_repository_content,
)
from unittest import mock  # noqa: E402

SCHEMAS = [
    ROOT / "docs/contracts/atom_contract.schema.json",
    ROOT / "docs/contracts/execution_receipt.schema.json",
    ROOT / "docs/contracts/acceptance_receipt.schema.json",
]
FIXTURE_MANIFEST = ROOT / "tests/fixtures/baton/fixture_manifest.json"
REQUIRED_PATHS = [
    ROOT / "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
    ROOT / "docs/agent/GITHUB_BATON_PROTOCOL.md",
    ROOT / "docs/decisions/ADR-003-gpt-executor-routing.md",
    ROOT / "docs/tasks/CTRL-BATON-SETUP.md",
    ROOT / ".cursor/commands/baton-preflight.md",
    ROOT / ".cursorignore",
    ROOT / ".github/ISSUE_TEMPLATE/control-atom.yml",
    ROOT / ".github/pull_request_template.md",
    ROOT / "scripts/baton_contract.py",
    ROOT / "scripts/baton_preflight.py",
    ROOT / "scripts/baton_scope.py",
    ROOT / "scripts/baton_receipt.py",
    ROOT / "scripts/validate_baton.py",
    ROOT / "tests/fixtures/baton/valid_atom_contract.json",
    ROOT / "tests/fixtures/baton/valid_issue_body.md",
    ROOT / "tests/fixtures/baton/valid_execution_receipt.json",
    ROOT / "tests/fixtures/baton/valid_acceptance_receipt.json",
    FIXTURE_MANIFEST,
]
CURSOR_RULES = [
    ROOT / ".cursor/rules/00-authority.mdc",
    ROOT / ".cursor/rules/05-language-and-reporting.mdc",
    ROOT / ".cursor/rules/10-input-routing.mdc",
    ROOT / ".cursor/rules/20-validation.mdc",
    ROOT / ".cursor/rules/30-security-and-secrets.mdc",
    ROOT / ".cursor/rules/40-catalog-and-evidence.mdc",
    ROOT / ".cursor/rules/50-github-baton.mdc",
]
ACCEPTED_BASE_HEAD = "bd152b3199a9ba5c75374bd798b1e81756cd4d9b"
ACCEPTED_BASE_TREE = "a068018e57ad53340ad94321539ed7d1b411bc10"


class BatonValidationError(RuntimeError):
    """Fail-closed baton machine-layer validation error."""


def assert_check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise BatonValidationError(f"{name}:{detail}" if detail else name)
    print(f"{name}: PASS")


def _raise_if_wrong_error(
    *,
    name: str,
    exc: BaseException,
    expected_error_code: str,
) -> None:
    if isinstance(exc, ValidationError):
        if expected_error_code in {"schema_validation", "ValidationError"}:
            return
        text = str(exc)
        if expected_error_code and expected_error_code in text:
            return
        raise BatonValidationError(
            f"negative_wrong_error_type:{name}:ValidationError:{exc}"
        )
    code = getattr(exc, "code", None)
    if code is None:
        text = str(exc)
        if expected_error_code and expected_error_code in text:
            return
        raise BatonValidationError(
            f"negative_wrong_error_type:{name}:{type(exc).__name__}:{exc}"
        )
    if code != expected_error_code and not str(exc).startswith(expected_error_code):
        raise BatonValidationError(
            f"negative_wrong_error_code:{name}:{code}!={expected_error_code}"
        )


def validate_schemas() -> None:
    for path in SCHEMAS:
        raw = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(raw)
        assert_check(f"schema_load:{path.name}", True)


def _load_manifest() -> dict[str, Any]:
    raw = FIXTURE_MANIFEST.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or "fixtures" not in data:
        raise BatonValidationError("fixture_manifest_invalid")
    return data


def _verify_manifest_entry_hash(entry: dict[str, Any]) -> tuple[Path, bytes]:
    relative = entry["path"]
    path = ROOT / relative
    if not path.is_file():
        raise BatonValidationError(f"fixture_missing:{relative}")
    try:
        resolved = canonical_repository_content(
            relative,
            allow_worktree_candidate=True,
        )
    except CanonicalRepositoryBytesError as exc:
        raise BatonValidationError(
            f"fixture_canonical_bytes_failed:{relative}:{exc}"
        ) from exc
    digest = resolved.sha256
    if digest != entry["sha256"]:
        raise BatonValidationError(
            f"fixture_hash_mismatch:{relative}:{digest}!={entry['sha256']}"
        )
    return path, resolved.content


def _run_fixture_case(entry: dict[str, Any], executed: set[str]) -> None:
    case_id = entry["id"]
    if case_id in executed:
        raise BatonValidationError(f"fixture_duplicate_id:{case_id}")
    path, fixture_bytes = _verify_manifest_entry_hash(entry)
    category = entry["category"]
    expected_outcome = entry["expected_outcome"]
    expected_error = entry.get("expected_error_code") or ""

    def expect_fail(fn: Callable[[], Any], error_code: str) -> None:
        try:
            fn()
        except (
            BatonContractError,
            BatonReceiptError,
            BatonScopeError,
            ValidationError,
        ) as exc:
            _raise_if_wrong_error(
                name=case_id, exc=exc, expected_error_code=error_code
            )
            assert_check(f"fixture:{case_id}", True)
            return
        raise BatonValidationError(f"negative_did_not_fail:{case_id}")

    if category == "valid_contract_bytes":
        payload = fixture_bytes
        expected = entry["contract_sha256"]
        assert_check(f"fixture_hash:{case_id}", sha256_bytes(payload) == expected)
        contract = validate_payload(
            payload,
            expected_contract_sha256=expected,
            expected_revision=entry["contract_revision"],
        )
        assert_check(
            f"fixture:{case_id}",
            contract["contract_id"] == "CTRL-BATON-A62-DEMO-001",
        )
    elif category == "valid_issue_body":
        issue = fixture_bytes.decode("utf-8")
        payload = extract_contract_payload_bytes(issue)
        expected = entry["contract_sha256"]
        assert_check(f"fixture_issue_bytes:{case_id}", sha256_bytes(payload) == expected)
        validate_payload(
            payload,
            expected_contract_sha256=expected,
            expected_revision=entry["contract_revision"],
        )
        assert_check(f"fixture:{case_id}", True)
    elif category == "valid_execution_receipt":
        semantic_validate_execution_receipt(json.loads(fixture_bytes.decode("utf-8")))
        assert_check(f"fixture:{case_id}", True)
    elif category == "valid_acceptance_receipt":
        semantic_validate_acceptance_receipt(json.loads(fixture_bytes.decode("utf-8")))
        assert_check(f"fixture:{case_id}", True)
    elif category == "hash_mismatch":
        payload = fixture_bytes
        expect_fail(
            lambda: validate_payload(
                payload,
                expected_contract_sha256="0" * 64,
                expected_revision=1,
            ),
            expected_error or "contract_hash_mismatch",
        )
    elif category == "revision_mismatch":
        payload = fixture_bytes
        digest = sha256_bytes(payload)
        expect_fail(
            lambda: validate_payload(
                payload,
                expected_contract_sha256=digest,
                expected_revision=entry.get("oob_expected_revision", 1),
            ),
            expected_error or "contract_revision_mismatch",
        )
    elif category == "marker_invalid":
        expect_fail(
            lambda: extract_contract_payload_bytes(fixture_bytes.decode("utf-8")),
            expected_error,
        )
    elif category == "invalid_json_after_markers":
        # Must pass marker extraction and hash/revision setup, fail on JSON parse.
        issue = fixture_bytes.decode("utf-8")
        payload = extract_contract_payload_bytes(issue)
        digest = sha256_bytes(payload)
        verify_out_of_band_hash(payload, digest)
        validate_expected_revision(1)
        expect_fail(lambda: parse_contract_json(payload), expected_error or "payload_json_invalid")
    elif category == "semantic_contract_invalid":
        payload = fixture_bytes
        digest = sha256_bytes(payload)
        revision = entry.get("contract_revision")
        if revision is None:
            revision = json.loads(payload.decode("utf-8"))["contract_revision"]
        expect_fail(
            lambda: validate_payload(
                payload,
                expected_contract_sha256=digest,
                expected_revision=revision,
            ),
            expected_error,
        )
    elif category == "base_head_mismatch":
        _run_preflight_base_mismatch(entry, fixture_bytes, field="base_head")
    elif category == "base_tree_mismatch":
        _run_preflight_base_mismatch(entry, fixture_bytes, field="base_tree")
    elif category == "offline_exact_bytes_crlf":
        canonical_payload = extract_contract_payload_bytes(fixture_bytes)
        crlf_payload = canonical_payload.replace(b"\n", b"\r\n")
        if crlf_payload == canonical_payload:
            raise BatonValidationError(f"crlf_fixture_missing_lf:{case_id}")
        raw = (
            BEGIN_MARKER.encode("utf-8")
            + b"\n"
            + crlf_payload
            + b"\n"
            + END_MARKER.encode("utf-8")
            + b"\n"
        )
        if b"\r" not in raw:
            raise BatonValidationError(f"crlf_fixture_missing_cr:{case_id}")
        expect_fail(
            lambda: extract_contract_payload_bytes(raw),
            expected_error or "payload_contains_cr",
        )
    elif category == "execution_receipt_invalid":
        data = json.loads(fixture_bytes.decode("utf-8"))
        expect_fail(lambda: semantic_validate_execution_receipt(data), expected_error)
    elif category == "acceptance_receipt_invalid":
        data = json.loads(fixture_bytes.decode("utf-8"))
        expect_fail(lambda: semantic_validate_acceptance_receipt(data), expected_error)
    elif category == "scope_outside":
        data = json.loads(fixture_bytes.decode("utf-8"))
        outside = [
            p
            for p in data["observed_paths"]
            if not path_in_managed_write_set(p, data["managed_write_set"])
        ]
        assert_check(f"fixture:{case_id}", outside == data["expected_outside"])
    elif category == "whitespace_hash_drift":
        payload = fixture_bytes
        canonical = canonical_repository_content(
            "tests/fixtures/baton/valid_atom_contract.json",
            allow_worktree_candidate=True,
        ).content
        assert_check(
            f"fixture:{case_id}",
            sha256_bytes(payload) != sha256_bytes(canonical),
        )
    elif category == "adversarial_scope_unit":
        # Executed by dedicated unit checks below; presence still required.
        assert_check(f"fixture:{case_id}", expected_outcome == "COVERED_BY_UNIT")
    else:
        raise BatonValidationError(f"unknown_fixture_category:{category}:{case_id}")

    if expected_outcome == "PASS" and category.endswith("_invalid"):
        raise BatonValidationError(f"fixture_outcome_inconsistent:{case_id}")
    executed.add(case_id)


def _run_preflight_base_mismatch(
    entry: dict[str, Any],
    fixture_bytes: bytes,
    *,
    field: str,
) -> None:
    """Prove mismatch via actual preflight behavior, not fixture inequality alone."""
    contract = json.loads(fixture_bytes.decode("utf-8"))
    payload = json.dumps(contract, indent=2, ensure_ascii=False).encode("utf-8")
    body = (
        b"<!-- SMIAL-BATON-CONTRACT-BEGIN -->\n"
        + payload
        + b"\n<!-- SMIAL-BATON-CONTRACT-END -->\n"
    )
    digest = sha256_bytes(payload)
    observed_head = ACCEPTED_BASE_HEAD
    observed_tree = ACCEPTED_BASE_TREE
    with mock.patch.object(
        baton_preflight,
        "check_local_repository_identity",
        return_value=[],
    ), mock.patch.object(
        baton_preflight,
        "run_git",
        side_effect=["main", observed_head, observed_tree],
    ), mock.patch.object(
        baton_preflight,
        "read_upstream",
        return_value="origin/main",
    ), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
        result = baton_preflight.preflight(
            repository="lancerbeta/solana-alpha-lab",
            issue=1,
            revision=contract.get("contract_revision", 1),
            expected_contract_sha256=digest,
            issue_body=body,
            allow_github_read=False,
        )
    if result["result"] != "BLOCKED":
        raise BatonValidationError(
            f"preflight_mismatch_not_blocked:{entry['id']}:{result['result']}"
        )
    if not result.get("contract_hash_ok"):
        raise BatonValidationError(f"preflight_mismatch_hash_not_ok:{entry['id']}")
    expected_value = contract["repository"][field]
    observed = observed_head if field == "base_head" else observed_tree
    needle = f"{field}:{observed}!={expected_value}"
    if needle not in result["observed_vs_expected"]:
        raise BatonValidationError(
            f"preflight_mismatch_evidence_missing:{entry['id']}:{needle}:"
            f"{result['observed_vs_expected']}"
        )
    assert_check(f"fixture:{entry['id']}", True)


def validate_adversarial_units() -> None:
    # Origin redaction: mismatch codes must never embed raw origin_url/userinfo.
    placeholder_token = "TEST_PLACEHOLDER_TOKEN_NOT_A_SECRET"
    credential_origin = (
        f"https://x-access-token:{placeholder_token}"
        "@github.com/lancerbeta/solana-alpha-lab.git"
    )
    origin_codes = baton_preflight.evaluate_local_repository_identity(
        toplevel=str(baton_preflight.ROOT.resolve()),
        origin_url=credential_origin,
        expected_root=baton_preflight.ROOT,
    )
    assert_check(
        "origin_credential_rejected",
        origin_codes == ["local_repository_identity_mismatch:origin_not_allowed"],
    )
    origin_blob = json.dumps(origin_codes)
    assert_check(
        "origin_credential_redacted",
        credential_origin not in origin_blob
        and placeholder_token not in origin_blob
        and "local_repository_identity_mismatch:origin:" not in origin_blob,
    )
    for allowed in sorted(baton_preflight.ALLOWED_ORIGIN_URLS):
        assert_check(
            f"origin_allowlist_pass:{allowed}",
            baton_preflight.evaluate_local_repository_identity(
                toplevel=str(baton_preflight.ROOT.resolve()),
                origin_url=allowed,
                expected_root=baton_preflight.ROOT,
            )
            == [],
        )

    managed = ["docs/evidence/baton/**"]
    assert_check(
        "prefix_sibling_denied",
        not path_in_managed_write_set("docs/evidence/baton_evil.txt", managed),
    )
    assert_check(
        "terminal_dir_allows_child",
        path_in_managed_write_set("docs/evidence/baton/x.json", managed),
    )
    assert_check(
        "case_bypass_git_denied",
        not path_in_managed_write_set(".GIT/config", ["AGENTS.md"]),
    )
    try:
        validate_managed_write_entry("Wallet/**")
        raise BatonValidationError("wallet_glob_not_rejected")
    except BatonContractError as exc:
        assert_check("case_bypass_wallet_entry", exc.code == "managed_write_forbidden")
    try:
        validate_managed_write_entry("docs/../secrets/x")
        raise BatonValidationError("parent_traversal_not_rejected")
    except BatonContractError as exc:
        assert_check(
            "parent_traversal_entry",
            exc.code
            in {
                "managed_write_path_invalid",
                "managed_write_forbidden",
                "path_empty",
            }
            or "invalid" in exc.code
            or "forbidden" in exc.code,
        )

    # Spaces + Unicode path matching (exact entry).
    spaced = ["docs/evidence/baton/my file.json"]
    assert_check(
        "path_with_spaces_exact",
        path_in_managed_write_set("docs/evidence/baton/my file.json", spaced),
    )
    unicode_entry = ["docs/evidence/baton/тест.json"]
    assert_check(
        "path_with_unicode_exact",
        path_in_managed_write_set("docs/evidence/baton/тест.json", unicode_entry),
    )

    # Rename / conflict porcelain must fail closed.
    try:
        parse_porcelain_z(b"R  new.txt\0old.txt\0")
        raise BatonValidationError("rename_not_rejected")
    except BatonScopeError as exc:
        assert_check("rename_conflict_rename", exc.code == "rename_or_copy_forbidden")
    try:
        parse_porcelain_z(b"UU conflict.txt\0")
        raise BatonValidationError("conflict_not_rejected")
    except BatonScopeError as exc:
        assert_check("rename_conflict_unmerged", exc.code == "conflict_status_forbidden")

    # Critical symlink containment via injectable boundary (must not SKIP).
    root = Path("/repo")
    outside = Path("/tmp/sibling_outside.txt")

    def resolve_escape(path: Path) -> Path:
        if path.as_posix().endswith("/docs/escape.txt"):
            return outside
        return path

    try:
        assert_path_contained(
            "docs/escape.txt",
            root=root,
            resolve_path=resolve_escape,
        )
        raise BatonValidationError("symlink_escape_not_rejected")
    except BatonScopeError as exc:
        assert_check("symlink_escape_injectable", exc.code == "symlink_escape")
    try:
        parse_porcelain_z(
            b"?? docs/escape.txt\0",
            root=root,
            resolve_path=resolve_escape,
        )
        raise BatonValidationError("symlink_escape_porcelain_not_rejected")
    except BatonScopeError as exc:
        assert_check("symlink_escape_porcelain", exc.code == "symlink_escape")

    # Duplicate JSON keys / non-finite.
    try:
        parse_contract_json(b'{"a":1,"a":2}')
        raise BatonValidationError("duplicate_keys_not_rejected")
    except BatonContractError as exc:
        assert_check("duplicate_json_keys", exc.code == "payload_json_duplicate_keys")
    try:
        parse_contract_json(b'{"a":NaN}')
        raise BatonValidationError("nan_not_rejected")
    except BatonContractError as exc:
        assert_check(
            "json_nan_forbidden",
            exc.code in {"payload_json_nonfinite_forbidden", "payload_json_invalid"},
        )
    try:
        parse_contract_json(b'{"a":Infinity}')
        raise BatonValidationError("infinity_not_rejected")
    except BatonContractError as exc:
        assert_check(
            "json_infinity_forbidden",
            exc.code in {"payload_json_nonfinite_forbidden", "payload_json_invalid"},
        )


def validate_fixtures() -> None:
    manifest = _load_manifest()
    fixtures = manifest["fixtures"]
    assert_check("fixture_manifest_nonempty", isinstance(fixtures, list) and bool(fixtures))
    assert_check("fixture_manifest_exact_count", len(fixtures) == 37, str(len(fixtures)))
    executed: set[str] = set()
    for entry in fixtures:
        _run_fixture_case(entry, executed)
    declared = {entry["id"] for entry in fixtures}
    if executed != declared:
        missing = sorted(declared - executed)
        raise BatonValidationError(f"fixture_unexecuted:{missing}")
    assert_check("fixture_manifest_all_executed", len(executed) == len(fixtures), str(len(executed)))

    # Skipped negative case must cause validator FAIL (meta-check).
    try:
        _raise_if_wrong_error(
            name="meta",
            exc=BatonContractError("other_code"),
            expected_error_code="expected_code",
        )
        raise BatonValidationError("meta_skip_check_failed_to_raise")
    except BatonValidationError as exc:
        assert_check("skipped_negative_causes_fail", "negative_wrong_error_code" in str(exc))

    validate_adversarial_units()


def validate_canonical_catalog_integrity() -> None:
    try:
        sweep = canonical_catalog_integrity_sweep(
            allow_worktree_candidate=True
        )
    except CanonicalRepositoryBytesError as exc:
        raise BatonValidationError(f"canonical_catalog_sweep_failed:{exc}") from exc
    assert_check("canonical_catalog_asset_count", sweep.asset_count == 191)
    assert_check("canonical_catalog_sha256_checked", sweep.checked_sha256 > 0)
    if sweep.mismatches:
        detail = ",".join(
            f"{asset_id}:{shard}:{path}:{registered}!={observed}"
            for asset_id, shard, path, registered, observed in sweep.mismatches
        )
        raise BatonValidationError(f"canonical_catalog_hash_mismatch:{detail}")
    assert_check("canonical_catalog_integrity", True)


def validate_cursor_and_templates() -> None:
    for path in REQUIRED_PATHS + CURSOR_RULES:
        assert_check(f"exists:{path.relative_to(ROOT).as_posix()}", path.is_file())
    authority = (ROOT / ".cursor/rules/00-authority.mdc").read_text(encoding="utf-8")
    for needle in [
        (
            "The user skills `start-solana-task` and `finish-solana-task` "
            "are non-executable in Cursor."
        ),
        (
            "Cursor must not use those skills to run an Entry Gate, Finish Gate, "
            "emit `DONE_CONFIRMED`, select a current or next canonical task, "
            "perform a skill auto-chain, or invoke `refactor-solana-lab`."
        ),
        (
            "Conversational cues such as `продолжай`, `что дальше`, or a task "
            "appearing complete grant no lifecycle-skill authority."
        ),
        (
            "Cursor must not claim semantic acceptance, canonical status "
            "changes, or `DONE`."
        ),
        (
            "This isolation does not disable third-party skill import or "
            "unrelated skills."
        ),
    ]:
        assert_check(f"authority_lifecycle_isolation:{needle}", needle in authority)
    cmd = (ROOT / ".cursor/commands/baton-preflight.md").read_text(encoding="utf-8")
    for needle in [
        "expected_contract_sha256",
        "scripts/baton_preflight.py",
        "BLOCKED_AUTHORITY",
        "github_reads",
        "github_writes",
        "--allow-github-read",
    ]:
        assert_check(f"preflight_cmd:{needle}", needle in cmd)
    assert_check(
        "preflight_no_blanket_api_ban",
        "do not call GitHub APIs" not in cmd.lower(),
    )
    ignore = (ROOT / ".cursorignore").read_text(encoding="utf-8")
    for needle in [".env", "!.env.example", ".smial-handoff/**", "wallet/**"]:
        assert_check(f"cursorignore:{needle}", needle in ignore)
    issue = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/control-atom.yml").read_text(encoding="utf-8")
    )
    assert_check("issue_form_name", "name" in issue and "body" in issue)
    body_text = (ROOT / ".github/ISSUE_TEMPLATE/control-atom.yml").read_text(encoding="utf-8")
    assert_check("issue_form_transport_warning", "mutable transport" in body_text.lower())
    assert_check(
        "issue_form_oob_hash",
        "expected_contract_sha256" in body_text,
    )
    pr = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    for needle in [
        "Draft PR is candidate evidence",
        "merge is separately authorized",
        "do not establish DONE",
        "expected SHA-256",
    ]:
        assert_check(f"pr_template:{needle}", needle.lower() in pr.lower())


LIVE_ROUTE_CONTROL_PATHS = (
    "AGENTS.md",
    ".cursor/rules/00-authority.mdc",
    ".cursor/rules/10-input-routing.mdc",
    ".cursor/rules/50-github-baton.mdc",
    "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
    "docs/agent/GITHUB_BATON_PROTOCOL.md",
    "docs/decisions/ADR-003-gpt-executor-routing.md",
    "docs/tasks/CTRL-BATON-SETUP.md",
    "docs/tasks/CTRL-CURSOR-WORKPLACE-RECONCILIATION.md",
)

STALE_ROUTE_PHRASES = (
    "documented future input route",
    "documented future route",
    "future GitHub Atom Contract baton",
    "Documented future input route",
    "protocol-documented only until later",
    "local dirty candidate",
    "not committed, not pushed, not live-piloted",
    "A6.2 machine layer currently exists only as a local dirty candidate",
    "Add `GITHUB_BATON` only as a documented future input route",
    "GITHUB_BATON` is a documented future",
    "Future execution flow",
    "PRE_MERGE_LOCAL_MAIN_REPAIR_CANDIDATE",
    "PROPOSED_LOCAL_CANDIDATE",
    "repository_evidence_status: PRE_MERGE",
    "canonical_status: CANDIDATE_NOT_REGISTERED",
)


def validate_protocol_links() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert_check("agents_github_baton", "GITHUB_BATON" in agents)
    assert_check("agents_execution_only", "EXECUTION_ONLY" in agents)
    assert_check("agents_gpt_control_plane", "GPT control plane" in agents or "control plane" in agents.lower())
    assert_check("agents_live_accepted_route", "live accepted" in agents.lower())
    protocol = (ROOT / "docs/agent/GITHUB_BATON_PROTOCOL.md").read_text(encoding="utf-8")
    assert_check(
        "protocol_oob_hash",
        "expected" in protocol.lower() and "sha-256" in protocol.lower(),
    )
    assert_check("protocol_mutable_transport", "mutable" in protocol.lower())
    assert_check("protocol_live_execution_flow", "Live execution flow" in protocol)
    assert_check("protocol_project_chat_primary", "PROJECT_CHAT_PRIMARY" in protocol)
    assert_check("protocol_transport_and_audit", "TRANSPORT_AND_AUDIT" in protocol)
    router = (ROOT / "docs/agent/EXECUTION_ROUTER_PROTOCOL.md").read_text(encoding="utf-8")
    assert_check("router_live_accepted_route", "Live accepted input route" in router)
    assert_check(
        "router_not_future_only_candidate",
        "not a future-only, local-dirty, pre-merge, or uncommitted candidate" in router,
    )
    authority = (ROOT / ".cursor/rules/00-authority.mdc").read_text(encoding="utf-8")
    assert_check("authority_project_chat_primary", "PROJECT_CHAT_PRIMARY" in authority)
    assert_check("authority_transport_and_audit", "TRANSPORT_AND_AUDIT" in authority)
    baton_rule = (ROOT / ".cursor/rules/50-github-baton.mdc").read_text(encoding="utf-8")
    assert_check("baton_rule_live_accepted", "live accepted input route" in baton_rule.lower())
    adr = (ROOT / "docs/decisions/ADR-003-gpt-executor-routing.md").read_text(encoding="utf-8")
    assert_check("adr_accepted_repository_mirror", "ACCEPTED_REPOSITORY_MIRROR" in adr)
    assert_check("adr_live_accepted_route", "live accepted input route" in adr.lower())
    setup = (ROOT / "docs/tasks/CTRL-BATON-SETUP.md").read_text(encoding="utf-8")
    assert_check("setup_live_route_posture", "Live route posture" in setup)
    assert_check("setup_not_future_only", "future-only, local-dirty" in setup)
    reconciliation = (
        ROOT / "docs/tasks/CTRL-CURSOR-WORKPLACE-RECONCILIATION.md"
    ).read_text(encoding="utf-8")
    assert_check(
        "reconciliation_mirror_exists",
        "CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR" in reconciliation,
    )
    assert_check(
        "reconciliation_current_owner",
        re.search(
            r"^current_owning_surface: LOCAL_WORK_PRIMARY$",
            reconciliation,
            re.MULTILINE,
        )
        is not None,
    )
    assert_check(
        "reconciliation_local_work_control_plane",
        "`LOCAL_WORK_PRIMARY`" in reconciliation,
    )
    assert_check(
        "reconciliation_generic_baton_control_plane",
        "`CONTROL_PLANE` = `PROJECT_CHAT_PRIMARY`" in reconciliation,
    )
    for relative in LIVE_ROUTE_CONTROL_PATHS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for phrase in STALE_ROUTE_PHRASES:
            assert_check(
                f"stale_route_absent:{relative}:{phrase}",
                phrase not in text,
            )


def validate_offline_commands_have_no_hidden_network() -> None:
    request_needle = "requests" + "."
    urllib_needle = "urllib" + ".request"
    for relative in [
        "scripts/baton_contract.py",
        "scripts/baton_scope.py",
        "scripts/baton_receipt.py",
        "scripts/validate_baton.py",
    ]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert_check(
            f"no_hidden_gh:{relative}",
            not re.search(r"\bgh\b", text),
        )
        assert_check(
            f"no_requests:{relative}",
            request_needle not in text and urllib_needle not in text,
        )


def validate() -> None:
    validate_schemas()
    validate_fixtures()
    validate_canonical_catalog_integrity()
    validate_cursor_and_templates()
    validate_protocol_links()
    validate_offline_commands_have_no_hidden_network()
    print("BATON_VALIDATION: PASS")


def main() -> int:
    try:
        validate()
    except BatonValidationError as exc:
        print("BATON_VALIDATION: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    except (BatonContractError, BatonReceiptError, BatonScopeError) as exc:
        print("BATON_VALIDATION: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
