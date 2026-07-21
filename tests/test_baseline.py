from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_baseline.py"

spec = importlib.util.spec_from_file_location("validate_baseline", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CatalogRepositoryStateTests(unittest.TestCase):
    def repository_files(self) -> set[str]:
        return {
            f"file-{index}"
            for index in range(module.EXPECTED_REPOSITORY_FILE_COUNT)
        }

    def test_staged_state(self) -> None:
        files = self.repository_files()
        original = module.repository_files
        module.repository_files = lambda: files
        try:
            state = module.classify_state(
                head_oid=module.BASE_COMMIT_OID,
                commit_count=1,
                parent_oid=None,
                tracked=files,
                staged=set(module.EXPECTED_CHANGED_FILES),
                untracked=set(),
                unstaged=set(),
            )
        finally:
            module.repository_files = original
        self.assertEqual(state, "CATALOG_FOUNDATION_STAGED")

    def test_committed_state(self) -> None:
        files = self.repository_files()
        original = module.repository_files
        module.repository_files = lambda: files
        try:
            state = module.classify_state(
                head_oid="f" * 40,
                commit_count=2,
                parent_oid=module.BASE_COMMIT_OID,
                tracked=files,
                staged=set(),
                untracked=set(),
                unstaged=set(),
            )
        finally:
            module.repository_files = original
        self.assertEqual(state, "CATALOG_FOUNDATION_COMMITTED")

    def test_wrong_parent_rejected(self) -> None:
        files = self.repository_files()
        original = module.repository_files
        module.repository_files = lambda: files
        try:
            state = module.classify_state(
                head_oid="f" * 40,
                commit_count=2,
                parent_oid="e" * 40,
                tracked=files,
                staged=set(),
                untracked=set(),
                unstaged=set(),
            )
        finally:
            module.repository_files = original
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_changed_file_count(self) -> None:
        self.assertEqual(len(module.EXPECTED_CHANGED_FILES), 21)
        self.assertIn(".gitattributes", module.EXPECTED_CHANGED_FILES)

    def test_expected_staged_file_constant(self) -> None:
        self.assertEqual(module.EXPECTED_STAGED_FILES, 21)
        self.assertEqual(
            module.EXPECTED_STAGED_FILES,
            len(module.EXPECTED_CHANGED_FILES),
        )

    def test_parse_eol_attribute(self) -> None:
        output = "scripts/validate.ps1: eol: lf\n"
        self.assertEqual(
            module.parse_eol_attribute(output, "scripts/validate.ps1"),
            "lf",
        )

    def test_parse_eol_attribute_rejects_unexpected(self) -> None:
        with self.assertRaises(AssertionError):
            module.parse_eol_attribute(
                "scripts/validate.ps1: text: set\n",
                "scripts/validate.ps1",
            )

    def test_lf_only_bytes(self) -> None:
        self.assertTrue(module.is_lf_only(b"one\ntwo\n"))
        self.assertFalse(module.is_lf_only(b"one\r\ntwo\r\n"))
        self.assertFalse(module.is_lf_only(b"one\rtwo"))

    def test_eol_rule_constants(self) -> None:
        self.assertEqual(module.EXPECTED_PS1_RULE, "*.ps1 text eol=lf")
        self.assertEqual(module.FORBIDDEN_PS1_RULE, "*.ps1 text eol=crlf")
        self.assertEqual(
            module.EXPECTED_PS1_PATHS,
            {"scripts/validate.ps1"},
        )

    def test_dependency_versions(self) -> None:
        self.assertEqual(module.EXPECTED_JSONSCHEMA, "4.26.0")
        self.assertEqual(module.EXPECTED_PYYAML, "6.0.3")


if __name__ == "__main__":
    unittest.main()
