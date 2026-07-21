from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/validate_baseline.py"
spec = importlib.util.spec_from_file_location("validate_baseline", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImportStatePolicyTests(unittest.TestCase):
    def expected(self) -> set[str]: return set(module.repository_files())

    def test_staged_state(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid=module.BASE_COMMIT_OID,commit_count=2,parent_oid=module.BASE_PARENT_OID,tracked=expected,staged=set(module.EXPECTED_CHANGED_FILES),untracked=set(),unstaged=set())
        self.assertEqual(state, "PRE_GIT_IMPORT_STAGED")

    def test_committed_state(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid="f"*40,commit_count=3,parent_oid=module.BASE_COMMIT_OID,tracked=expected,staged=set(),untracked=set(),unstaged=set())
        self.assertEqual(state, "PRE_GIT_IMPORT_COMMITTED")

    def test_partial_staging_rejected(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid=module.BASE_COMMIT_OID,commit_count=2,parent_oid=module.BASE_PARENT_OID,tracked=expected,staged={next(iter(module.EXPECTED_CHANGED_FILES))},untracked=set(),unstaged=set())
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_counts(self) -> None:
        self.assertEqual(module.EXPECTED_REPOSITORY_FILE_COUNT, 58)
        self.assertEqual(len(module.EXPECTED_CHANGED_FILES), 40)

    def test_commit_message(self) -> None:
        self.assertEqual(module.RECOMMENDED_COMMIT_MESSAGE, 'feat: import pre-git evidence and register architecture intent')

    def test_exact_import_style_partition(self) -> None:
        self.assertEqual(
            len(module.EXACT_IMPORT_FILES),
            module.EXPECTED_EXACT_IMPORT_COUNT,
        )
        self.assertFalse(
            module.EXACT_IMPORT_FILES
            & module.STYLE_CHECKED_CHANGED_FILES
        )
        self.assertEqual(
            module.EXACT_IMPORT_FILES
            | module.STYLE_CHECKED_CHANGED_FILES,
            module.EXPECTED_CHANGED_FILES,
        )

    def test_exact_import_style_exemption_is_bounded(self) -> None:
        self.assertIn(
            "docs/evidence/pre_git/task01/task_01_completion_record_v1.md",
            module.EXACT_IMPORT_FILES,
        )
        self.assertIn(
            "docs/evidence/pre_git/task01/validation_report.txt",
            module.EXACT_IMPORT_FILES,
        )
        self.assertNotIn("README.md", module.EXACT_IMPORT_FILES)
        self.assertIn("README.md", module.STYLE_CHECKED_CHANGED_FILES)


if __name__ == "__main__": unittest.main()
