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

    def classify(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.IMPORT_COMMIT_OID,
            "commit_count": module.IMPORT_COMMIT_COUNT,
            "parent_oid": module.BASE_COMMIT_OID,
            "tracked": self.expected(),
            "staged": set(module.WORK_ACCEPTANCE_SYNC_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": "",
            "commit_changed": set(),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_staged_state(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid=module.BASE_COMMIT_OID,commit_count=2,parent_oid=module.BASE_PARENT_OID,tracked=expected,staged=set(module.EXPECTED_CHANGED_FILES),untracked=set(),unstaged=set())
        self.assertEqual(state, "PRE_GIT_IMPORT_STAGED")

    def test_committed_state(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid="f"*40,commit_count=3,parent_oid=module.BASE_COMMIT_OID,tracked=expected,staged=set(),untracked=set(),unstaged=set())
        self.assertEqual(state, "PRE_GIT_IMPORT_COMMITTED")

    def test_work_acceptance_staged_state(self) -> None:
        self.assertEqual(self.classify(), "WORK_ACCEPTANCE_SYNC_STAGED")

    def test_work_acceptance_committed_state(self) -> None:
        state = self.classify(
            head_oid="f" * 40,
            commit_count=module.WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.IMPORT_COMMIT_OID,
            staged=set(),
            commit_subject=module.WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.WORK_ACCEPTANCE_SYNC_FILES),
        )
        self.assertEqual(state, "WORK_ACCEPTANCE_SYNC_COMMITTED")

    def test_work_acceptance_missing_allowed_path_rejected(self) -> None:
        staged = set(module.WORK_ACCEPTANCE_SYNC_FILES)
        staged.remove("catalog/assets/core.yaml")
        self.assertEqual(
            self.classify(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_work_acceptance_extra_path_rejected(self) -> None:
        staged = set(module.WORK_ACCEPTANCE_SYNC_FILES) | {"README.md"}
        self.assertEqual(
            self.classify(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_work_acceptance_wrong_parent_rejected(self) -> None:
        state = self.classify(
            head_oid="f" * 40,
            commit_count=module.WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.BASE_COMMIT_OID,
            staged=set(),
            commit_subject=module.WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.WORK_ACCEPTANCE_SYNC_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_work_acceptance_wrong_subject_rejected(self) -> None:
        state = self.classify(
            head_oid="f" * 40,
            commit_count=module.WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.IMPORT_COMMIT_OID,
            staged=set(),
            commit_subject="docs: arbitrary acceptance update",
            commit_changed=set(module.WORK_ACCEPTANCE_SYNC_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_work_acceptance_unstaged_addition_rejected(self) -> None:
        self.assertEqual(
            self.classify(unstaged={"README.md"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_work_acceptance_untracked_addition_rejected(self) -> None:
        self.assertEqual(
            self.classify(untracked={"unexpected.txt"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_arbitrary_docs_only_diff_rejected(self) -> None:
        self.assertEqual(
            self.classify(
                staged={"docs/tasks/TASK-03.md", "docs/handoffs/latest.md"}
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_partial_staging_rejected(self) -> None:
        expected = self.expected()
        state = module.classify_state(head_oid=module.BASE_COMMIT_OID,commit_count=2,parent_oid=module.BASE_PARENT_OID,tracked=expected,staged={next(iter(module.EXPECTED_CHANGED_FILES))},untracked=set(),unstaged=set())
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_counts(self) -> None:
        self.assertEqual(module.EXPECTED_REPOSITORY_FILE_COUNT, 58)
        self.assertEqual(len(module.EXPECTED_CHANGED_FILES), 40)
        self.assertEqual(len(module.WORK_ACCEPTANCE_SYNC_FILES), 5)

    def test_commit_message(self) -> None:
        self.assertEqual(module.RECOMMENDED_COMMIT_MESSAGE, 'feat: import pre-git evidence and register architecture intent')
        self.assertEqual(
            module.WORK_ACCEPTANCE_COMMIT_SUBJECT,
            "fix: validate Work acceptance checkpoint",
        )

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
