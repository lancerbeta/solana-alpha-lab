# tests/test_baton_preflight.py
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import baton_preflight  # noqa: E402
from baton_contract import (  # noqa: E402
    BEGIN_MARKER,
    END_MARKER,
    BatonContractError,
    EXPECTED_REPO,
    extract_contract_payload_bytes,
)


def _identity_ok():
    return mock.patch.object(
        baton_preflight, "check_local_repository_identity", return_value=[]
    )


class BatonPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fix = ROOT / "tests/fixtures/baton"
        cls.expected = (cls.fix / "expected_contract_sha256.txt").read_text(
            encoding="utf-8"
        ).strip()
        cls.body = (cls.fix / "valid_issue_body.md").read_text(encoding="utf-8")
        cls.body_bytes = (cls.fix / "valid_issue_body.md").read_bytes()

    def test_offline_body_no_github_side_effects(self) -> None:
        with _identity_ok(), mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            "bd152b3199a9ba5c75374bd798b1e81756cd4d9b",
            "a068018e57ad53340ad94321539ed7d1b411bc10",
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=self.body,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "PASS_READONLY")
        self.assertEqual(result["side_effects"]["github_reads"], 0)
        self.assertEqual(result["side_effects"]["github_writes"], 0)
        self.assertEqual(result["side_effects"]["local_writes"], 0)

    def test_offline_exact_bytes_accepted(self) -> None:
        with _identity_ok(), mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            "bd152b3199a9ba5c75374bd798b1e81756cd4d9b",
            "a068018e57ad53340ad94321539ed7d1b411bc10",
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=self.body_bytes,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "PASS_READONLY")

    def test_crlf_offline_issue_body_no_silent_normalization(self) -> None:
        payload = extract_contract_payload_bytes(self.body_bytes)
        crlf_payload = payload.replace(b"\n", b"\r\n")
        raw = (
            BEGIN_MARKER.encode("utf-8")
            + b"\n"
            + crlf_payload
            + b"\n"
            + END_MARKER.encode("utf-8")
            + b"\n"
        )
        self.assertNotEqual(crlf_payload, payload)
        self.assertIn(b"\r", raw)
        with self.assertRaises(BatonContractError) as ctx:
            extract_contract_payload_bytes(raw)
        self.assertEqual(ctx.exception.code, "payload_contains_cr")
        with _identity_ok(), mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            "bd152b3199a9ba5c75374bd798b1e81756cd4d9b",
            "a068018e57ad53340ad94321539ed7d1b411bc10",
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=raw,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED")
        self.assertTrue(
            any("payload_contains_cr" in item for item in result["observed_vs_expected"])
        )

    def test_base_head_mismatch_blocked_with_evidence(self) -> None:
        contract = json.loads(
            (self.fix / "invalid/base_head_mismatch_contract.json").read_text(
                encoding="utf-8"
            )
        )
        # Wrap as issue body markers for preflight extraction path.
        payload = json.dumps(contract, indent=2, ensure_ascii=False).encode("utf-8")
        body = (
            b"<!-- SMIAL-BATON-CONTRACT-BEGIN -->\n"
            + payload
            + b"\n<!-- SMIAL-BATON-CONTRACT-END -->\n"
        )
        observed_head = "bd152b3199a9ba5c75374bd798b1e81756cd4d9b"
        observed_tree = "a068018e57ad53340ad94321539ed7d1b411bc10"
        # Hash must match payload so base mismatch is the blocking cause.
        import hashlib

        digest = hashlib.sha256(payload).hexdigest()
        with _identity_ok(), mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            observed_head,
            observed_tree,
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=digest,
                issue_body=body,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED")
        self.assertTrue(result["contract_hash_ok"])
        evidence = result["observed_vs_expected"]
        self.assertTrue(any(item.startswith("base_head:") for item in evidence))
        self.assertIn(
            f"base_head:{observed_head}!={contract['repository']['base_head']}",
            evidence,
        )

    def test_base_tree_mismatch_blocked_with_evidence(self) -> None:
        contract = json.loads(
            (self.fix / "invalid/base_tree_mismatch_contract.json").read_text(
                encoding="utf-8"
            )
        )
        payload = json.dumps(contract, indent=2, ensure_ascii=False).encode("utf-8")
        body = (
            b"<!-- SMIAL-BATON-CONTRACT-BEGIN -->\n"
            + payload
            + b"\n<!-- SMIAL-BATON-CONTRACT-END -->\n"
        )
        import hashlib

        digest = hashlib.sha256(payload).hexdigest()
        observed_head = "bd152b3199a9ba5c75374bd798b1e81756cd4d9b"
        observed_tree = "a068018e57ad53340ad94321539ed7d1b411bc10"
        with _identity_ok(), mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            observed_head,
            observed_tree,
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=digest,
                issue_body=body,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED")
        self.assertTrue(result["contract_hash_ok"])
        evidence = result["observed_vs_expected"]
        self.assertIn(
            f"base_tree:{observed_tree}!={contract['repository']['base_tree']}",
            evidence,
        )

    def test_issue_number_zero_blocked(self) -> None:
        result = baton_preflight.preflight(
            repository="lancerbeta/solana-alpha-lab",
            issue=0,
            revision=1,
            expected_contract_sha256=self.expected,
            issue_body=self.body,
            allow_github_read=False,
        )
        self.assertEqual(result["result"], "BLOCKED")
        self.assertEqual(result["observed_vs_expected"], ["issue_number_invalid"])

    def test_live_without_flag_is_blocked_authority(self) -> None:
        with _identity_ok():
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=None,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED_AUTHORITY")
        self.assertEqual(result["side_effects"]["github_reads"], 0)
        self.assertEqual(result["side_effects"]["github_writes"], 0)

    def test_live_flag_counts_one_read_zero_writes(self) -> None:
        with _identity_ok(), mock.patch.object(
            baton_preflight,
            "fetch_issue_body_live",
            return_value=(self.body, 1, 0),
        ) as fetch, mock.patch.object(baton_preflight, "run_git", side_effect=[
            "main",
            "bd152b3199a9ba5c75374bd798b1e81756cd4d9b",
            "a068018e57ad53340ad94321539ed7d1b411bc10",
            "origin/main",
        ]), mock.patch.object(baton_preflight, "dirty_count", return_value=0):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=42,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=None,
                allow_github_read=True,
            )
        fetch.assert_called_once_with("lancerbeta/solana-alpha-lab", 42)
        self.assertEqual(result["result"], "PASS_READONLY")
        self.assertEqual(result["side_effects"]["github_reads"], 1)
        self.assertEqual(result["side_effects"]["github_writes"], 0)

    def test_no_latest_discovery_helpers_exist(self) -> None:
        source = (SCRIPTS / "baton_preflight.py").read_text(encoding="utf-8")
        self.assertNotIn("issue list", source.lower())
        self.assertNotIn("newest", source.lower())
        self.assertNotIn("latest", source.lower())
        self.assertIn("gh", source)
        self.assertIn("--allow-github-read", source)
        self.assertIn("read_bytes()", source)

    def test_exact_https_origin_identity_pass(self) -> None:
        for origin in (
            "https://github.com/lancerbeta/solana-alpha-lab.git",
            "https://github.com/lancerbeta/solana-alpha-lab",
        ):
            with self.subTest(origin=origin):
                self.assertEqual(
                    baton_preflight.normalize_origin_full_name(origin),
                    EXPECTED_REPO,
                )
                codes = baton_preflight.evaluate_local_repository_identity(
                    toplevel=str(baton_preflight.ROOT.resolve()),
                    origin_url=origin,
                    expected_root=baton_preflight.ROOT,
                )
                self.assertEqual(codes, [])

    def test_exact_ssh_origin_identity_pass(self) -> None:
        for origin in (
            "git@github.com:lancerbeta/solana-alpha-lab.git",
            "ssh://git@github.com/lancerbeta/solana-alpha-lab.git",
        ):
            with self.subTest(origin=origin):
                self.assertEqual(
                    baton_preflight.normalize_origin_full_name(origin),
                    EXPECTED_REPO,
                )
                codes = baton_preflight.evaluate_local_repository_identity(
                    toplevel=str(baton_preflight.ROOT.resolve()),
                    origin_url=origin,
                    expected_root=baton_preflight.ROOT,
                )
                self.assertEqual(codes, [])

    def test_wrong_owner_origin_fail(self) -> None:
        origin = "https://github.com/evil-owner/solana-alpha-lab.git"
        self.assertIsNone(baton_preflight.normalize_origin_full_name(origin))
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel=str(baton_preflight.ROOT.resolve()),
            origin_url=origin,
            expected_root=baton_preflight.ROOT,
        )
        self.assertEqual(
            codes, ["local_repository_identity_mismatch:origin_not_allowed"]
        )
        self.assertNotIn(origin, " ".join(codes))

    def test_prefix_suffix_lookalike_origin_fail(self) -> None:
        lookalikes = (
            "https://github.com/lancerbeta/solana-alpha-laboratory",
            "https://github.com/lancerbeta/solana-alpha-lab.evil",
            "https://github.com/lancerbeta/solana-alpha-lab.git.evil",
            "https://github.com/lancerbeta/solana-alpha-labx.git",
            "git@github.com:lancerbeta/solana-alpha-lab",  # missing .git
        )
        for origin in lookalikes:
            with self.subTest(origin=origin):
                self.assertIsNone(baton_preflight.normalize_origin_full_name(origin))
                codes = baton_preflight.evaluate_local_repository_identity(
                    toplevel=str(baton_preflight.ROOT.resolve()),
                    origin_url=origin,
                    expected_root=baton_preflight.ROOT,
                )
                self.assertEqual(
                    codes, ["local_repository_identity_mismatch:origin_not_allowed"]
                )
                self.assertNotIn(origin, " ".join(codes))

    def test_wrong_repository_origin_fail(self) -> None:
        origin = "https://github.com/lancerbeta/other-repo.git"
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel=str(baton_preflight.ROOT.resolve()),
            origin_url=origin,
            expected_root=baton_preflight.ROOT,
        )
        self.assertEqual(
            codes, ["local_repository_identity_mismatch:origin_not_allowed"]
        )
        self.assertNotIn(origin, " ".join(codes))

    def test_wrong_hostname_origin_fail(self) -> None:
        origin = "https://evil.example/lancerbeta/solana-alpha-lab.git"
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel=str(baton_preflight.ROOT.resolve()),
            origin_url=origin,
            expected_root=baton_preflight.ROOT,
        )
        self.assertEqual(
            codes, ["local_repository_identity_mismatch:origin_not_allowed"]
        )
        self.assertNotIn(origin, " ".join(codes))

    def test_credential_bearing_https_origin_rejected_and_redacted(self) -> None:
        # Synthetic placeholder only — not a real secret.
        placeholder_user = "x-access-token"
        placeholder_token = "TEST_PLACEHOLDER_TOKEN_NOT_A_SECRET"
        origin = (
            f"https://{placeholder_user}:{placeholder_token}"
            "@github.com/lancerbeta/solana-alpha-lab.git"
        )
        self.assertIsNone(baton_preflight.normalize_origin_full_name(origin))
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel=str(baton_preflight.ROOT.resolve()),
            origin_url=origin,
            expected_root=baton_preflight.ROOT,
        )
        self.assertEqual(
            codes, ["local_repository_identity_mismatch:origin_not_allowed"]
        )
        joined = " ".join(codes)
        self.assertNotIn(origin, joined)
        self.assertNotIn(placeholder_token, joined)
        self.assertNotIn(placeholder_user, joined)
        self.assertNotIn("@github.com", joined)

        with mock.patch.object(
            baton_preflight,
            "check_local_repository_identity",
            return_value=codes,
        ):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=self.body,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED")
        evidence = result["observed_vs_expected"]
        self.assertEqual(
            evidence, ["local_repository_identity_mismatch:origin_not_allowed"]
        )
        blob = json.dumps(result)
        self.assertNotIn(origin, blob)
        self.assertNotIn(placeholder_token, blob)
        self.assertNotIn(placeholder_user + ":", blob)
        self.assertNotIn(f"origin:{origin}", blob)
        self.assertNotRegex(blob, r"local_repository_identity_mismatch:origin:")

    def test_missing_origin_fail(self) -> None:
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel=str(baton_preflight.ROOT.resolve()),
            origin_url=None,
            expected_root=baton_preflight.ROOT,
        )
        self.assertIn("local_repository_identity_mismatch:origin_missing", codes)

    def test_local_toplevel_mismatch_fail(self) -> None:
        codes = baton_preflight.evaluate_local_repository_identity(
            toplevel="/tmp/other-clone",
            origin_url="https://github.com/lancerbeta/solana-alpha-lab.git",
            expected_root=baton_preflight.ROOT,
        )
        self.assertIn("local_repository_identity_mismatch:toplevel", codes)
        joined = " ".join(codes)
        self.assertNotIn("/tmp/other-clone", joined)
        self.assertNotIn(str(baton_preflight.ROOT.resolve()), joined)
        self.assertNotIn("Users", joined)

    def test_preflight_identity_mismatch_sanitized_result(self) -> None:
        with mock.patch.object(
            baton_preflight,
            "check_local_repository_identity",
            return_value=[
                "local_repository_identity_mismatch:toplevel",
                "local_repository_identity_mismatch:origin_not_allowed",
            ],
        ):
            result = baton_preflight.preflight(
                repository="lancerbeta/solana-alpha-lab",
                issue=1,
                revision=1,
                expected_contract_sha256=self.expected,
                issue_body=self.body,
                allow_github_read=False,
            )
        self.assertEqual(result["result"], "BLOCKED")
        evidence = result["observed_vs_expected"]
        self.assertEqual(
            evidence,
            [
                "local_repository_identity_mismatch:toplevel",
                "local_repository_identity_mismatch:origin_not_allowed",
            ],
        )
        blob = json.dumps(result)
        self.assertNotIn(str(baton_preflight.ROOT.resolve()), blob)
        # Windows-style absolute user path must not appear.
        self.assertNotRegex(blob, r"[A-Za-z]:\\\\Users\\\\")
        self.assertNotIn("/Users/", blob)
        self.assertNotIn("/home/", blob)
        self.assertNotIn("https://github.com/", blob)
        self.assertNotRegex(blob, r"local_repository_identity_mismatch:origin:")


if __name__ == "__main__":
    unittest.main()
