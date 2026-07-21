from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "secret_scan.py"

spec = importlib.util.spec_from_file_location(
    "secret_scan",
    MODULE_PATH,
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SecretScannerTests(unittest.TestCase):
    def test_all_synthetic_cases_are_rejected(self) -> None:
        failures = module.run_self_test()
        self.assertEqual(failures, [])

    def test_openai_shape_is_rejected(self) -> None:
        candidate = ("s" + "k") + "-" + ("A" * 32)
        self.assertIn(
            "openai_key",
            module.findings_for_text(candidate),
        )

    def test_github_shape_is_rejected(self) -> None:
        candidate = ("g" + "h" + "p") + "_" + ("B" * 36)
        self.assertIn(
            "github_token",
            module.findings_for_text(candidate),
        )

    def test_jwt_shape_is_rejected(self) -> None:
        candidate = (
            ("e" + "y" + "J")
            + ("C" * 20)
            + "."
            + ("D" * 16)
            + "."
            + ("E" * 16)
        )
        self.assertIn(
            "jwt_like",
            module.findings_for_text(candidate),
        )

    def test_private_key_header_is_rejected(self) -> None:
        candidate = (
            "-----BEGIN "
            + ("PRIVATE" + " KEY")
            + "-----"
        )
        self.assertIn(
            "private_key_block",
            module.findings_for_text(candidate),
        )

    def test_non_empty_credential_assignment_is_rejected(self) -> None:
        candidate = (
            ("api" + "_key")
            + "="
            + ("F" * 24)
        )
        self.assertIn(
            "credential_assignment",
            module.findings_for_text(candidate),
        )

    def test_credential_url_is_rejected(self) -> None:
        candidate = (
            "https://user:"
            + ("G" * 16)
            + "@example.invalid/path"
        )
        self.assertIn(
            "credential_url",
            module.findings_for_text(candidate),
        )

    def test_empty_placeholder_is_allowed(self) -> None:
        self.assertEqual(
            module.findings_for_text("API_KEY=\n"),
            [],
        )

    def test_logical_repository_alias_is_allowed(self) -> None:
        self.assertEqual(
            module.findings_for_text(
                "USERPROFILE_PROJECTS/solana-alpha-lab"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
