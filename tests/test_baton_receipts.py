# tests/test_baton_receipts.py
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_receipt import (  # noqa: E402
    BatonReceiptError,
    semantic_validate_acceptance_receipt,
    semantic_validate_execution_receipt,
)
from jsonschema.exceptions import ValidationError


class BatonReceiptTests(unittest.TestCase):
    def test_valid_receipts_pass(self) -> None:
        semantic_validate_execution_receipt(
            json.loads(
                (
                    ROOT / "tests/fixtures/baton/valid_execution_receipt.json"
                ).read_text(encoding="utf-8")
            )
        )
        semantic_validate_acceptance_receipt(
            json.loads(
                (
                    ROOT / "tests/fixtures/baton/valid_acceptance_receipt.json"
                ).read_text(encoding="utf-8")
            )
        )

    def test_github_write_receipt_fails(self) -> None:
        data = json.loads(
            (
                ROOT / "tests/fixtures/baton/invalid/receipt_github_write.json"
            ).read_text(encoding="utf-8")
        )
        with self.assertRaises(BatonReceiptError) as ctx:
            semantic_validate_execution_receipt(data)
        self.assertEqual(ctx.exception.code, "github_writes_not_authorized")

    def test_secrets_true_fails(self) -> None:
        data = json.loads(
            (
                ROOT / "tests/fixtures/baton/invalid/receipt_secrets_true.json"
            ).read_text(encoding="utf-8")
        )
        with self.assertRaises(ValidationError):
            semantic_validate_execution_receipt(data)

    def test_acceptance_canonical_and_merge_fail(self) -> None:
        for name in [
            "acceptance_canonical_status_change.json",
            "acceptance_merge_authorized.json",
        ]:
            with self.subTest(name=name):
                data = json.loads(
                    (ROOT / "tests/fixtures/baton/invalid" / name).read_text(
                        encoding="utf-8"
                    )
                )
                with self.assertRaises(ValidationError):
                    semantic_validate_acceptance_receipt(data)

    def test_pass_candidate_inconsistency(self) -> None:
        data = json.loads(
            (
                ROOT / "tests/fixtures/baton/valid_execution_receipt.json"
            ).read_text(encoding="utf-8")
        )
        bad = copy.deepcopy(data)
        bad["changes"]["files_outside_managed_write_set"] = ["AGENTS.md"]
        with self.assertRaises(BatonReceiptError) as ctx:
            semantic_validate_execution_receipt(bad)
        self.assertEqual(ctx.exception.code, "pass_with_outside_files")

        staged = copy.deepcopy(data)
        staged["changes"]["staged_files"] = ["docs/evidence/baton/x.json"]
        with self.assertRaises(BatonReceiptError) as ctx2:
            semantic_validate_execution_receipt(staged)
        self.assertEqual(ctx2.exception.code, "pass_with_staged_files")

        fail_val = copy.deepcopy(data)
        fail_val["result"] = "FAIL_VALIDATION"
        fail_val["validation"]["full"] = "PASS"
        with self.assertRaises(BatonReceiptError) as ctx3:
            semantic_validate_execution_receipt(fail_val)
        self.assertEqual(ctx3.exception.code, "fail_validation_with_full_pass")

        blocked = copy.deepcopy(data)
        blocked["result"] = "BLOCKED"
        blocked["blockers"] = []
        with self.assertRaises(BatonReceiptError) as ctx4:
            semantic_validate_execution_receipt(blocked)
        self.assertEqual(ctx4.exception.code, "blocked_without_blocker")

    def test_adversarial_fixture_exact_error_codes(self) -> None:
        cases = [
            ("receipt_pass_full_not_run.json", "pass_with_full_incomplete"),
            ("receipt_pass_targeted_skipped.json", "pass_with_targeted_incomplete"),
            (
                "receipt_embedded_windows_path.json",
                "absolute_user_path_in_contract_string",
            ),
            (
                "receipt_embedded_posix_home.json",
                "absolute_user_path_in_contract_string",
            ),
            ("receipt_password_assignment.json", "credential_value_in_contract_string"),
            ("receipt_token_assignment.json", "credential_value_in_contract_string"),
            ("receipt_no_change_with_files.json", "no_change_with_changed_files"),
        ]
        for name, code in cases:
            with self.subTest(name=name):
                data = json.loads(
                    (ROOT / "tests/fixtures/baton/invalid" / name).read_text(
                        encoding="utf-8"
                    )
                )
                with self.assertRaises(BatonReceiptError) as ctx:
                    semantic_validate_execution_receipt(data)
                self.assertEqual(ctx.exception.code, code)

    def test_safe_token_budget_words_allowed(self) -> None:
        data = json.loads(
            (
                ROOT / "tests/fixtures/baton/valid_execution_receipt.json"
            ).read_text(encoding="utf-8")
        )
        data = copy.deepcopy(data)
        data["limitations"] = ["token budget remains advisory only"]
        semantic_validate_execution_receipt(data)

    def test_acceptance_pass_requires_empty_repairs(self) -> None:
        data = json.loads(
            (
                ROOT / "tests/fixtures/baton/valid_acceptance_receipt.json"
            ).read_text(encoding="utf-8")
        )
        bad = copy.deepcopy(data)
        bad["required_repairs"] = ["fix path matching"]
        with self.assertRaises(BatonReceiptError) as ctx:
            semantic_validate_acceptance_receipt(bad)
        self.assertEqual(ctx.exception.code, "pass_requires_empty_repairs")


if __name__ == "__main__":
    unittest.main()
