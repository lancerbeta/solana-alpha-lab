#!/usr/bin/env python3
"""Validate or build sanitized execution and acceptance receipts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import (  # noqa: E402
    BatonContractError,
    path_is_forbidden_target,
    scan_string_for_absolute_user_path,
    scan_string_for_secrets,
    validate_repository_relative_path,
    walk_strings,
)

SCHEMA = ROOT / "docs/contracts/execution_receipt.schema.json"
ACCEPTANCE_SCHEMA = ROOT / "docs/contracts/acceptance_receipt.schema.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PASS_VALIDATION_STATUSES = frozenset({"PASS"})
PASS_CATALOG_STATUSES = frozenset({"PASS", "NOT_APPLICABLE"})
INCOMPLETE_VALIDATION_STATUSES = frozenset(
    {"NOT_RUN", "SKIPPED", "PENDING", ""}
)


class BatonReceiptError(ValueError):
    """Fail-closed receipt error with deterministic code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_receipt_strings(receipt: dict[str, Any]) -> None:
    def visitor(value: str) -> None:
        try:
            scan_string_for_secrets(value)
            scan_string_for_absolute_user_path(value)
        except BatonContractError as exc:
            raise BatonReceiptError(exc.code, exc.detail) from exc

    walk_strings(receipt, visitor)


def _validate_repo_path_list(paths: list[Any], *, field: str) -> None:
    if not isinstance(paths, list):
        raise BatonReceiptError("path_list_invalid", field)
    for path in paths:
        if not isinstance(path, str):
            raise BatonReceiptError("path_not_string", field)
        try:
            validate_repository_relative_path(path, allow_terminal_dir_glob=False)
        except BatonContractError as exc:
            raise BatonReceiptError("receipt_path_invalid", f"{field}:{path}") from exc
        if path_is_forbidden_target(path):
            raise BatonReceiptError("receipt_path_forbidden", f"{field}:{path}")


def schema_validate_execution_receipt(receipt: dict[str, Any]) -> None:
    Draft202012Validator(load_schema(SCHEMA)).validate(receipt)


def semantic_validate_execution_receipt(receipt: dict[str, Any]) -> None:
    schema_validate_execution_receipt(receipt)
    if receipt.get("contains_secrets") is True:
        raise BatonReceiptError("secrets_true_forbidden")
    if receipt.get("contains_absolute_user_paths") is True:
        raise BatonReceiptError("absolute_paths_true_forbidden")
    _scan_receipt_strings(receipt)

    changes = receipt["changes"]
    _validate_repo_path_list(changes["changed_files"], field="changed_files")
    _validate_repo_path_list(changes["staged_files"], field="staged_files")
    _validate_repo_path_list(
        changes["files_outside_managed_write_set"],
        field="files_outside_managed_write_set",
    )

    side = receipt["side_effects"]
    if side["github_writes"] > 0:
        raise BatonReceiptError("github_writes_not_authorized")
    if side["credential_values_exposed"] > 0:
        raise BatonReceiptError("credentials_exposed")
    if side["wallet_actions"] or side["signer_actions"] or side["transaction_actions"]:
        raise BatonReceiptError("wallet_signer_transaction_forbidden")

    result = receipt["result"]
    validation = receipt["validation"]
    blockers = receipt.get("blockers") or []
    outside = changes["files_outside_managed_write_set"]
    staged = changes["staged_files"]
    commands = validation.get("commands")

    if result == "PASS_CANDIDATE":
        if outside:
            raise BatonReceiptError("pass_with_outside_files")
        if staged:
            raise BatonReceiptError("pass_with_staged_files")
        if blockers:
            raise BatonReceiptError("pass_with_blockers")
        if not isinstance(commands, list) or not commands:
            raise BatonReceiptError("pass_requires_commands")
        for key in ("targeted", "full", "security"):
            value = validation.get(key)
            if value in INCOMPLETE_VALIDATION_STATUSES or value is None:
                raise BatonReceiptError(f"pass_with_{key}_incomplete")
            if value not in PASS_VALIDATION_STATUSES:
                raise BatonReceiptError(f"pass_requires_{key}_pass")
        catalog = validation.get("catalog")
        if catalog in INCOMPLETE_VALIDATION_STATUSES or catalog is None:
            raise BatonReceiptError("pass_with_catalog_incomplete")
        if catalog not in PASS_CATALOG_STATUSES:
            raise BatonReceiptError("pass_requires_catalog_pass_or_na")
        if side["github_writes"] != 0:
            raise BatonReceiptError("pass_requires_github_writes_zero")
        if side["credential_values_exposed"] != 0:
            raise BatonReceiptError("pass_requires_credentials_unexposed")
        if side["provider_calls"] != 0:
            raise BatonReceiptError("pass_with_inconsistent_side_effects")
        if (
            side["wallet_actions"]
            or side["signer_actions"]
            or side["transaction_actions"]
        ):
            raise BatonReceiptError("pass_requires_wallet_signer_tx_zero")

    if result == "NO_CHANGE":
        if changes["changed_files"]:
            raise BatonReceiptError("no_change_with_changed_files")
        if changes.get("diff_sha256") != "NONE":
            raise BatonReceiptError("no_change_with_diff")

    if result == "BLOCKED" and not blockers:
        raise BatonReceiptError("blocked_without_blocker")

    if result == "FAIL_VALIDATION" and validation.get("full") == "PASS":
        raise BatonReceiptError("fail_validation_with_full_pass")

    if validation.get("security") == "FAIL" and result == "PASS_CANDIDATE":
        raise BatonReceiptError("inconsistent_security_result")

    if result == "PASS_CANDIDATE" and validation.get("full") != "PASS":
        raise BatonReceiptError("inconsistent_full_result")
    if result == "NO_CHANGE" and blockers:
        raise BatonReceiptError("no_change_with_blockers")


def schema_validate_acceptance_receipt(receipt: dict[str, Any]) -> None:
    Draft202012Validator(load_schema(ACCEPTANCE_SCHEMA)).validate(receipt)


def semantic_validate_acceptance_receipt(receipt: dict[str, Any]) -> None:
    schema_validate_acceptance_receipt(receipt)
    _scan_receipt_strings(receipt)
    if receipt.get("merge_authorized") is True:
        raise BatonReceiptError("merge_authorized_without_later_boundary")
    if receipt.get("canonical_status_change") != "NONE":
        raise BatonReceiptError("canonical_status_change_forbidden")
    verdict = receipt["verdict"]
    repairs = receipt.get("required_repairs") or []
    if verdict == "PASS":
        if receipt.get("contract_compliance") != "PASS":
            raise BatonReceiptError("pass_requires_contract_compliance")
        if receipt.get("authority_compliance") != "PASS":
            raise BatonReceiptError("pass_requires_authority_compliance")
        if repairs:
            raise BatonReceiptError("pass_requires_empty_repairs")
    if verdict == "PASS_WITH_PATCH" and not repairs:
        raise BatonReceiptError("pass_with_patch_requires_repairs")
    if verdict == "FAIL_REPAIR_REQUIRED" and not repairs:
        raise BatonReceiptError("fail_repair_requires_repairs")
    # Receipt itself never grants merge/status/DONE; enforced by const fields
    # and the explicit checks above.


def build_execution_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt.setdefault("receipt_schema", "smial.github_baton.execution_receipt")
    receipt.setdefault("schema_version", "1.0")
    receipt.setdefault("contains_secrets", False)
    receipt.setdefault("contains_absolute_user_paths", False)
    semantic_validate_execution_receipt(receipt)
    return receipt


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"execution", "acceptance"}:
        print(
            "usage: baton_receipt.py execution|acceptance <json-file>",
            file=sys.stderr,
        )
        return 2
    kind, path = sys.argv[1], Path(sys.argv[2])
    data = json.loads(path.read_text(encoding="utf-8"))
    if kind == "execution":
        semantic_validate_execution_receipt(data)
    else:
        semantic_validate_acceptance_receipt(data)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
