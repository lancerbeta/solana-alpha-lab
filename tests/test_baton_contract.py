# tests/test_baton_contract.py
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baton_contract import (  # noqa: E402
    BatonContractError,
    extract_contract_payload_bytes,
    parse_contract_json,
    path_in_managed_write_set,
    resolve_repo_relative_file,
    scan_string_for_absolute_user_path,
    sha256_bytes,
    validate_managed_write_entry,
    validate_payload,
    validate_repository_relative_path,
)


class BatonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fix = ROOT / "tests/fixtures/baton"
        cls.payload = (cls.fix / "valid_atom_contract.json").read_bytes()
        cls.expected = (cls.fix / "expected_contract_sha256.txt").read_text(
            encoding="utf-8"
        ).strip()

    def test_exact_payload_bytes_determine_sha256(self) -> None:
        self.assertEqual(sha256_bytes(self.payload), self.expected)
        ws = (self.fix / "invalid/whitespace_changed_contract.json").read_bytes()
        self.assertNotEqual(sha256_bytes(ws), self.expected)

    def test_issue_extraction_preserves_exact_bytes(self) -> None:
        issue = (self.fix / "valid_issue_body.md").read_text(encoding="utf-8")
        extracted = extract_contract_payload_bytes(issue)
        self.assertEqual(extracted, self.payload)
        self.assertEqual(sha256_bytes(extracted), self.expected)

    def test_whitespace_and_embedded_hash_still_fail_oob_expected(self) -> None:
        issue = (
            self.fix / "invalid/issue_body_whitespace_and_embedded_hash.md"
        ).read_text(encoding="utf-8")
        extracted = extract_contract_payload_bytes(issue)
        with self.assertRaises(BatonContractError) as ctx:
            validate_payload(
                extracted,
                expected_contract_sha256=self.expected,
                expected_revision=1,
            )
        self.assertEqual(ctx.exception.code, "contract_hash_mismatch")

    def test_duplicate_and_missing_markers_fail(self) -> None:
        with self.assertRaises(BatonContractError) as dup:
            extract_contract_payload_bytes(
                (self.fix / "invalid/duplicate_markers.md").read_text(encoding="utf-8")
            )
        self.assertEqual(dup.exception.code, "begin_marker_count_invalid")
        with self.assertRaises(BatonContractError) as missing:
            extract_contract_payload_bytes(
                (self.fix / "invalid/missing_marker.md").read_text(encoding="utf-8")
            )
        self.assertEqual(missing.exception.code, "begin_marker_count_invalid")

    def test_managed_write_prefixes_cannot_escape_root(self) -> None:
        managed = ["docs/evidence/baton/**"]
        self.assertTrue(
            path_in_managed_write_set("docs/evidence/baton/x.json", managed)
        )
        self.assertFalse(path_in_managed_write_set("AGENTS.md", managed))
        self.assertFalse(path_in_managed_write_set("../secrets/x", managed))
        self.assertFalse(path_in_managed_write_set(".git/config", managed))
        self.assertFalse(path_in_managed_write_set("docs/evidence/baton_evil.txt", managed))

    def test_duplicate_keys_nan_infinity(self) -> None:
        with self.assertRaises(BatonContractError) as dup:
            parse_contract_json(b'{"a":1,"a":2}')
        self.assertEqual(dup.exception.code, "payload_json_duplicate_keys")
        with self.assertRaises(BatonContractError) as nan:
            parse_contract_json(b'{"a":NaN}')
        self.assertIn(
            nan.exception.code,
            {"payload_json_nonfinite_forbidden", "payload_json_invalid"},
        )
        with self.assertRaises(BatonContractError) as inf:
            parse_contract_json(b'{"a":Infinity}')
        self.assertIn(
            inf.exception.code,
            {"payload_json_nonfinite_forbidden", "payload_json_invalid"},
        )

    def test_issue_body_path_must_be_explicit_repo_relative(self) -> None:
        with self.assertRaises(BatonContractError) as abs_ctx:
            resolve_repo_relative_file("C:/Users/someone/body.md")
        self.assertIn(abs_ctx.exception.code, {"path_absolute", "issue_body_path_absolute"})
        with self.assertRaises(BatonContractError):
            resolve_repo_relative_file("../README.md")
        ok = resolve_repo_relative_file("tests/fixtures/baton/valid_issue_body.md")
        self.assertTrue(ok.is_file())

    def test_semantic_negatives_exact_codes(self) -> None:
        cases = {
            "read_only_nonempty_write_set.json": "read_only_nonempty_write_set",
            "local_write_empty_write_set.json": "local_write_empty_write_set",
            "absolute_windows_path.json": "path_absolute",
            "absolute_posix_path.json": "path_absolute",
            "parent_traversal.json": "managed_write_path_invalid",
            "git_target.json": "managed_write_forbidden",
            "forbidden_wallet_target.json": "managed_write_forbidden",
            "unsafe_glob.json": "managed_write_unsafe_glob",
        }
        for name, code in cases.items():
            with self.subTest(name=name):
                raw = (self.fix / "invalid" / name).read_bytes()
                with self.assertRaises(BatonContractError) as ctx:
                    validate_payload(
                        raw,
                        expected_contract_sha256=hashlib.sha256(raw).hexdigest(),
                        expected_revision=json.loads(raw.decode("utf-8"))[
                            "contract_revision"
                        ],
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_wallet_case_variant_entry_rejected(self) -> None:
        with self.assertRaises(BatonContractError) as ctx:
            validate_managed_write_entry("Wallet/**")
        self.assertEqual(ctx.exception.code, "managed_write_forbidden")

    def test_https_uri_allowed_in_string_scan(self) -> None:
        scan_string_for_absolute_user_path("https://example.com/docs")
        scan_string_for_absolute_user_path("see http://example.com/docs for detail")

    def test_repo_uri_allowed_in_string_scan(self) -> None:
        scan_string_for_absolute_user_path("repo://docs/contracts/example")
        scan_string_for_absolute_user_path("catalog://asset/example")

    def test_git_uri_allowed_in_string_scan(self) -> None:
        scan_string_for_absolute_user_path("git://commit/example")

    def test_real_forward_slash_unc_rejected(self) -> None:
        with self.assertRaises(BatonContractError) as ctx:
            scan_string_for_absolute_user_path("//server/share")
        self.assertEqual(ctx.exception.code, "absolute_user_path_in_contract_string")
        with self.assertRaises(BatonContractError) as ctx2:
            scan_string_for_absolute_user_path("prefix //server/share suffix")
        self.assertEqual(ctx2.exception.code, "absolute_user_path_in_contract_string")

    def test_real_backslash_unc_rejected(self) -> None:
        with self.assertRaises(BatonContractError) as ctx:
            scan_string_for_absolute_user_path(r"\\server\share")
        self.assertEqual(ctx.exception.code, "absolute_user_path_in_contract_string")

    def test_embedded_windows_and_posix_user_paths_rejected(self) -> None:
        cases = (
            r"note C:\Users\name\secret.txt",
            "note /home/name/secret.txt",
            "note /Users/name/secret.txt",
            "note /root/secret.txt",
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(BatonContractError) as ctx:
                    scan_string_for_absolute_user_path(value)
                self.assertEqual(
                    ctx.exception.code, "absolute_user_path_in_contract_string"
                )

    def test_managed_write_uri_still_rejected(self) -> None:
        uris = (
            "https://example.com/docs",
            "repo://docs/contracts/example",
            "git://commit/example",
        )
        for uri in uris:
            with self.subTest(uri=uri):
                with self.assertRaises(BatonContractError) as ctx:
                    validate_managed_write_entry(uri)
                self.assertIn(
                    ctx.exception.code,
                    {
                        "path_absolute",
                        "managed_write_path_invalid",
                        "managed_write_forbidden",
                    },
                )
                with self.assertRaises(BatonContractError) as ctx2:
                    validate_repository_relative_path(uri)
                self.assertIn(
                    ctx2.exception.code,
                    {
                        "path_absolute",
                        "managed_write_path_invalid",
                        "managed_write_forbidden",
                    },
                )


class LiveRouteContractTests(unittest.TestCase):
    def test_control_contracts_reject_stale_future_route_language(self) -> None:
        from validate_baton import (  # noqa: WPS433
            LIVE_ROUTE_CONTROL_PATHS,
            STALE_ROUTE_PHRASES,
            validate_protocol_links,
        )

        validate_protocol_links()
        for relative in LIVE_ROUTE_CONTROL_PATHS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in STALE_ROUTE_PHRASES:
                with self.subTest(path=relative, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_live_route_role_invariants_are_present(self) -> None:
        authority = (ROOT / ".cursor/rules/00-authority.mdc").read_text(encoding="utf-8")
        protocol = (ROOT / "docs/agent/GITHUB_BATON_PROTOCOL.md").read_text(
            encoding="utf-8"
        )
        reconciliation = (
            ROOT / "docs/tasks/CTRL-CURSOR-WORKPLACE-RECONCILIATION.md"
        ).read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("PROJECT_CHAT_PRIMARY", authority)
        self.assertIn("TRANSPORT_AND_AUDIT", authority)
        self.assertIn("EXECUTION_ONLY", authority)
        self.assertIn("PROJECT_CHAT_PRIMARY", protocol)
        self.assertIn(
            "current_owning_surface: LOCAL_WORK_PRIMARY",
            reconciliation,
        )
        self.assertIn("`LOCAL_WORK_PRIMARY`", reconciliation)
        self.assertIn(
            "`CONTROL_PLANE` = `PROJECT_CHAT_PRIMARY`",
            reconciliation,
        )
        self.assertIn(
            "CWR-A4_WORK_REELECTION_FAIL_CLOSED_REPAIR",
            reconciliation,
        )
        self.assertIn("live accepted", agents.lower())


if __name__ == "__main__":
    unittest.main()
