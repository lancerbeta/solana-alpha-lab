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


class RepositoryStatePolicyTests(unittest.TestCase):
    def classify_atom5(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.WORK_ACCEPTANCE_COMMIT_OID,
            "commit_count": module.WORK_ACCEPTANCE_COMMIT_COUNT,
            "parent_oid": module.IMPORT_COMMIT_OID,
            "tracked": module.atom5_repository_files(),
            "staged": set(module.ATOM5_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.WORK_ACCEPTANCE_COMMIT_SUBJECT,
            "commit_changed": set(module.WORK_ACCEPTANCE_SYNC_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_atom5_acceptance(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM5_COMMIT_OID,
            "commit_count": module.ATOM5_COMMIT_COUNT,
            "parent_oid": module.WORK_ACCEPTANCE_COMMIT_OID,
            "tracked": module.atom5_repository_files(),
            "staged": set(module.ATOM5_WORK_ACCEPTANCE_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM5_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM5_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_pre_git_import_staged_state_remains_valid(self) -> None:
        state = module.classify_state(
            head_oid=module.BASE_COMMIT_OID,
            commit_count=module.BASE_COMMIT_COUNT,
            parent_oid=module.BASE_PARENT_OID,
            tracked=module.import_repository_files(),
            staged=set(module.EXPECTED_CHANGED_FILES),
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "PRE_GIT_IMPORT_STAGED")

    def test_pre_git_import_committed_state_remains_valid(self) -> None:
        state = module.classify_state(
            head_oid=module.IMPORT_COMMIT_OID,
            commit_count=module.IMPORT_COMMIT_COUNT,
            parent_oid=module.BASE_COMMIT_OID,
            tracked=module.import_repository_files(),
            staged=set(),
            untracked=set(),
            unstaged=set(),
            commit_subject=module.RECOMMENDED_COMMIT_MESSAGE,
            commit_changed=set(module.EXPECTED_CHANGED_FILES),
        )
        self.assertEqual(state, "PRE_GIT_IMPORT_COMMITTED")

    def test_work_acceptance_staged_state_remains_valid(self) -> None:
        state = module.classify_state(
            head_oid=module.IMPORT_COMMIT_OID,
            commit_count=module.IMPORT_COMMIT_COUNT,
            parent_oid=module.BASE_COMMIT_OID,
            tracked=module.work_acceptance_repository_files(),
            staged=set(module.WORK_ACCEPTANCE_SYNC_FILES),
            untracked=set(),
            unstaged=set(),
        )
        self.assertEqual(state, "WORK_ACCEPTANCE_SYNC_STAGED")

    def test_work_acceptance_committed_state_remains_valid(self) -> None:
        state = module.classify_state(
            head_oid=module.WORK_ACCEPTANCE_COMMIT_OID,
            commit_count=module.WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.IMPORT_COMMIT_OID,
            tracked=module.work_acceptance_repository_files(),
            staged=set(),
            untracked=set(),
            unstaged=set(),
            commit_subject=module.WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.WORK_ACCEPTANCE_SYNC_FILES),
        )
        self.assertEqual(state, "WORK_ACCEPTANCE_SYNC_COMMITTED")

    def test_atom5_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom5(),
            "ATOM5_REGISTRIES_NAVIGATION_STAGED",
        )

    def test_atom5_exact_committed_state_passes(self) -> None:
        state = self.classify_atom5(
            head_oid=module.ATOM5_COMMIT_OID,
            commit_count=module.ATOM5_COMMIT_COUNT,
            parent_oid=module.WORK_ACCEPTANCE_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM5_CHANGED_FILES),
        )
        self.assertEqual(state, "ATOM5_REGISTRIES_NAVIGATION_COMMITTED")

    def test_atom5_work_acceptance_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom5_acceptance(),
            "ATOM5_WORK_ACCEPTANCE_STAGED",
        )

    def test_atom5_work_acceptance_exact_committed_state_passes(self) -> None:
        state = self.classify_atom5_acceptance(
            head_oid="f" * 40,
            commit_count=module.ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.ATOM5_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM5_WORK_ACCEPTANCE_FILES),
        )
        self.assertEqual(state, "ATOM5_WORK_ACCEPTANCE_COMMITTED")

    def test_atom5_work_acceptance_missing_core_fails(self) -> None:
        staged = set(module.ATOM5_WORK_ACCEPTANCE_FILES)
        staged.remove("catalog/assets/core.yaml")
        self.assertEqual(
            self.classify_atom5_acceptance(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_work_acceptance_extra_path_fails(self) -> None:
        staged = set(module.ATOM5_WORK_ACCEPTANCE_FILES) | {"README.md"}
        self.assertEqual(
            self.classify_atom5_acceptance(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_work_acceptance_wrong_parent_fails(self) -> None:
        state = self.classify_atom5_acceptance(
            head_oid="f" * 40,
            commit_count=module.ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.WORK_ACCEPTANCE_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM5_WORK_ACCEPTANCE_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_atom5_work_acceptance_wrong_subject_fails(self) -> None:
        state = self.classify_atom5_acceptance(
            head_oid="f" * 40,
            commit_count=module.ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.ATOM5_COMMIT_OID,
            staged=set(),
            commit_subject="docs: arbitrary acceptance",
            commit_changed=set(module.ATOM5_WORK_ACCEPTANCE_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_atom5_work_acceptance_mixed_staged_unstaged_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5_acceptance(unstaged={"docs/tasks/TASK-03.md"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_work_acceptance_untracked_addition_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5_acceptance(untracked={"unexpected.txt"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_work_acceptance_arbitrary_docs_only_diff_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5_acceptance(
                staged={"docs/tasks/TASK-03.md", "docs/handoffs/latest.md"}
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_missing_path_fails(self) -> None:
        staged = set(module.ATOM5_CHANGED_FILES)
        staged.remove("catalog/assets/lifecycle.yaml")
        self.assertEqual(
            self.classify_atom5(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_extra_path_fails(self) -> None:
        staged = set(module.ATOM5_CHANGED_FILES) | {"README.md"}
        self.assertEqual(
            self.classify_atom5(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_mixed_staged_and_unstaged_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5(unstaged={"AGENTS.md"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_unstaged_addition_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5(staged=set(), unstaged={"README.md"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_untracked_addition_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5(untracked={"unexpected.txt"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom5_wrong_parent_fails(self) -> None:
        state = self.classify_atom5(
            head_oid="f" * 40,
            commit_count=module.ATOM5_COMMIT_COUNT,
            parent_oid=module.IMPORT_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM5_CHANGED_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_atom5_wrong_subject_fails(self) -> None:
        state = self.classify_atom5(
            head_oid="f" * 40,
            commit_count=module.ATOM5_COMMIT_COUNT,
            parent_oid=module.WORK_ACCEPTANCE_COMMIT_OID,
            staged=set(),
            commit_subject="docs: arbitrary update",
            commit_changed=set(module.ATOM5_CHANGED_FILES),
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_atom5_wrong_committed_file_set_fails(self) -> None:
        changed = set(module.ATOM5_CHANGED_FILES)
        changed.remove("docs/PROJECT_MAP.md")
        state = self.classify_atom5(
            head_oid="f" * 40,
            commit_count=module.ATOM5_COMMIT_COUNT,
            parent_oid=module.WORK_ACCEPTANCE_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_COMMIT_SUBJECT,
            commit_changed=changed,
        )
        self.assertEqual(state, "INVALID_REPOSITORY_STATE")

    def test_arbitrary_docs_only_diff_fails(self) -> None:
        self.assertEqual(
            self.classify_atom5(
                staged={"docs/tasks/TASK-03.md", "docs/handoffs/latest.md"}
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_exact_counts_and_subjects(self) -> None:
        self.assertEqual(module.EXPECTED_REPOSITORY_FILE_COUNT, 58)
        self.assertEqual(module.ATOM5_EXPECTED_REPOSITORY_FILE_COUNT, 74)
        self.assertEqual(len(module.EXPECTED_CHANGED_FILES), 40)
        self.assertEqual(len(module.WORK_ACCEPTANCE_SYNC_FILES), 5)
        self.assertEqual(len(module.ATOM5_MODIFIED_FILES), 12)
        self.assertEqual(len(module.ATOM5_CREATED_FILES), 16)
        self.assertEqual(len(module.ATOM5_CHANGED_FILES), 28)
        self.assertEqual(len(module.ATOM5_WORK_ACCEPTANCE_FILES), 5)
        self.assertEqual(
            module.ATOM5_COMMIT_SUBJECT,
            "feat: add registry skeletons and generated navigation",
        )
        self.assertEqual(
            module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            "fix: validate Atom 5 Work acceptance",
        )

    def test_exact_import_style_partition(self) -> None:
        self.assertEqual(
            len(module.EXACT_IMPORT_FILES),
            module.EXPECTED_EXACT_IMPORT_COUNT,
        )
        self.assertFalse(
            module.EXACT_IMPORT_FILES & module.STYLE_CHECKED_CHANGED_FILES
        )
        self.assertEqual(
            module.EXACT_IMPORT_FILES | module.STYLE_CHECKED_CHANGED_FILES,
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


if __name__ == "__main__":
    unittest.main()
