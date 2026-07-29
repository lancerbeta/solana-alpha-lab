from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/validate_pre_git_import.py"
spec = importlib.util.spec_from_file_location("validate_pre_git_import", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreGitImportTests(unittest.TestCase):
    def test_expected_import_count(self) -> None:
        self.assertEqual(len(module.EXPECTED_IMPORTS), 20)

    def test_task01_count(self) -> None:
        self.assertEqual(len([p for p in module.EXPECTED_IMPORTS if "/task01/" in p]), 12)

    def test_task02_count(self) -> None:
        self.assertEqual(len([p for p in module.EXPECTED_IMPORTS if "/task02/" in p]), 8)

    def test_external_bundle_count_is_scoped_to_pre_git_owners(self) -> None:
        assets = {
            "BUNDLE-TASK01-COMPLETION-001": {
                "asset_type": "external_bundle"
            },
            "BUNDLE-TASK02-COMPLETION-001": {
                "asset_type": "external_bundle"
            },
            "BUNDLE-FUTURE-CONTENT-ADDRESSED-001": {
                "asset_type": "external_bundle"
            },
        }
        self.assertEqual(
            set(module.pre_git_external_bundles(assets)),
            module.PRE_GIT_EXTERNAL_BUNDLE_IDS,
        )

    def test_architecture_hash(self) -> None:
        self.assertEqual(module.sha256(ROOT / module.ARCH_PATH), module.ARCH_SHA)

    def test_imported_files_exist_and_hash(self) -> None:
        for relative, expected in module.EXPECTED_IMPORTS.items():
            self.assertEqual(module.sha256(ROOT / relative), expected)

    def test_exact_source_eof_newlines_are_preserved(self) -> None:
        for relative, expected_count in (
            module.EXPECTED_TRAILING_NEWLINE_COUNTS.items()
        ):
            raw = (ROOT / relative).read_bytes()
            observed = len(raw) - len(raw.rstrip(b"\n"))
            self.assertEqual(observed, expected_count)

    def test_exact_import_style_policy_is_explicit(self) -> None:
        self.assertEqual(
            module.EXACT_IMPORT_WHITESPACE_POLICY,
            "PRESERVE_EXACT_BYTES_HASH_VERIFIED_STYLE_EXEMPT",
        )

    def test_no_superseded_validator_imported(self) -> None:
        self.assertFalse((ROOT / "docs/evidence/pre_git/task01/validate_task01_completion.py").exists())

    def test_architecture_is_advisory(self) -> None:
        text = (ROOT / module.ARCH_PATH).read_text(encoding="utf-8")
        self.assertIn("advisory only", text)
        self.assertIn("backfill does not create past availability", text)


if __name__ == "__main__": unittest.main()
