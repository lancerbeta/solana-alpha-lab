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

    def classify_atom7(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
            "commit_count": module.ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT,
            "parent_oid": module.ATOM5_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_LOCAL_CI_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM5_WORK_ACCEPTANCE_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_atom7_repair(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM7_LOCAL_CI_COMMIT_OID,
            "commit_count": module.ATOM7_LOCAL_CI_COMMIT_COUNT,
            "parent_oid": module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_PRE_PUSH_REPAIR_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_LOCAL_CI_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_LOCAL_CI_FILES),
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
            head_oid=module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
            commit_count=module.ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT,
            parent_oid=module.ATOM5_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM5_WORK_ACCEPTANCE_FILES),
        )
        self.assertEqual(state, "ATOM5_WORK_ACCEPTANCE_COMMITTED")

    def test_atom7_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7(),
            "ATOM7_LOCAL_CI_CANDIDATE_STAGED",
        )

    def test_atom7_exact_committed_state_passes(self) -> None:
        state = self.classify_atom7(
            head_oid="f" * 40,
            commit_count=module.ATOM7_LOCAL_CI_COMMIT_COUNT,
            parent_oid=module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
            staged=set(),
            commit_subject=module.ATOM7_LOCAL_CI_COMMIT_SUBJECT,
            commit_changed=set(module.ATOM7_LOCAL_CI_FILES),
        )
        self.assertEqual(state, "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED")

    def test_atom7_missing_path_fails(self) -> None:
        staged = set(module.ATOM7_LOCAL_CI_FILES)
        staged.remove(".github/workflows/ci.yml")
        self.assertEqual(
            self.classify_atom7(staged=staged),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_extra_path_fails(self) -> None:
        self.assertEqual(
            self.classify_atom7(
                staged=set(module.ATOM7_LOCAL_CI_FILES) | {"unexpected.txt"}
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_mixed_or_untracked_state_fails(self) -> None:
        self.assertEqual(
            self.classify_atom7(unstaged={"README.md"}),
            "INVALID_REPOSITORY_STATE",
        )
        self.assertEqual(
            self.classify_atom7(untracked={"unexpected.txt"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_unstaged_only_state_fails(self) -> None:
        self.assertEqual(
            self.classify_atom7(
                staged=set(),
                unstaged=set(module.ATOM7_LOCAL_CI_FILES),
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_wrong_parent_or_subject_fails(self) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": module.ATOM7_LOCAL_CI_COMMIT_COUNT,
            "parent_oid": module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
            "staged": set(),
            "commit_subject": module.ATOM7_LOCAL_CI_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_LOCAL_CI_FILES),
        }
        self.assertEqual(
            self.classify_atom7(**(committed | {"parent_oid": module.ATOM5_COMMIT_OID})),
            "INVALID_REPOSITORY_STATE",
        )
        self.assertEqual(
            self.classify_atom7(**(committed | {"commit_subject": "ci: arbitrary"})),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_wrong_committed_file_set_fails(self) -> None:
        changed = set(module.ATOM7_LOCAL_CI_FILES)
        changed.remove("catalog/generated/asset_edges.json")
        self.assertEqual(
            self.classify_atom7(
                head_oid="f" * 40,
                commit_count=module.ATOM7_LOCAL_CI_COMMIT_COUNT,
                parent_oid=module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID,
                staged=set(),
                commit_subject=module.ATOM7_LOCAL_CI_COMMIT_SUBJECT,
                commit_changed=changed,
            ),
            "INVALID_REPOSITORY_STATE",
        )

    def test_atom7_repair_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_repair(),
            "ATOM7_PRE_PUSH_REPAIR_STAGED",
        )

    def test_atom7_repair_exact_committed_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_repair(
                head_oid="f" * 40,
                commit_count=module.ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT,
                parent_oid=module.ATOM7_LOCAL_CI_COMMIT_OID,
                staged=set(),
                commit_subject=module.ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT,
                commit_changed=set(module.ATOM7_PRE_PUSH_REPAIR_FILES),
            ),
            "ATOM7_PRE_PUSH_REPAIR_COMMITTED",
        )

    def test_atom7_repair_wrong_inventory_fails(self) -> None:
        for overrides in (
            {"staged": {"scripts/validate_baseline.py"}},
            {
                "staged": set(module.ATOM7_PRE_PUSH_REPAIR_FILES)
                | {"unexpected.txt"}
            },
            {"unstaged": {"scripts/validate_baseline.py"}},
            {"untracked": {"unexpected.txt"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_repair(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_repair_wrong_parent_subject_or_changed_set_fails(self) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_LOCAL_CI_COMMIT_OID,
            "staged": set(),
            "commit_subject": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_PRE_PUSH_REPAIR_FILES),
        }
        for overrides in (
            {"parent_oid": module.ATOM5_WORK_ACCEPTANCE_COMMIT_OID},
            {"commit_subject": "fix: arbitrary repository state"},
            {"commit_changed": {"scripts/validate_baseline.py"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_repair(**(committed | overrides)),
                    "INVALID_REPOSITORY_STATE",
                )

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
        self.assertEqual(len(module.ATOM7_LOCAL_CI_MODIFIED_FILES), 15)
        self.assertEqual(len(module.ATOM7_LOCAL_CI_CREATED_FILES), 3)
        self.assertEqual(len(module.ATOM7_LOCAL_CI_FILES), 18)
        self.assertEqual(len(module.ATOM7_PRE_PUSH_REPAIR_FILES), 2)
        self.assertEqual(module.ATOM7_EXPECTED_REPOSITORY_FILE_COUNT, 77)
        self.assertEqual(
            module.ATOM5_COMMIT_SUBJECT,
            "feat: add registry skeletons and generated navigation",
        )
        self.assertEqual(
            module.ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT,
            "fix: validate Atom 5 Work acceptance",
        )
        self.assertEqual(
            module.ATOM7_LOCAL_CI_COMMIT_SUBJECT,
            "ci: add pinned repository validation",
        )
        self.assertEqual(
            module.ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT,
            "fix: validate repository publication states",
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


class GitTopologyPolicyTests(unittest.TestCase):
    HEAD_OID = "a" * 40

    def classify_topology(self, **overrides: object) -> str:
        arguments = {
            "branch": "main",
            "head_oid": self.HEAD_OID,
            "remotes": {"origin"},
            "fetch_urls": (module.EXPECTED_ORIGIN_URL,),
            "push_urls": (module.EXPECTED_ORIGIN_URL,),
            "fetch_refspecs": (module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            "push_refspecs": (),
            "upstream": None,
            "local_branches": {"main"},
            "remote_tracking_refs": set(),
            "tags": set(),
            "all_refs": {"refs/heads/main"},
            "github_actions": False,
            "github_repository": None,
            "github_ref": None,
            "github_sha": None,
        }
        arguments.update(overrides)
        return module.classify_git_topology(**arguments)

    def test_pre_remote_state_passes(self) -> None:
        self.assertEqual(
            self.classify_topology(
                remotes=set(),
                fetch_urls=(),
                push_urls=(),
                fetch_refspecs=(),
            ),
            "PRE_REMOTE",
        )

    def test_bound_pre_push_state_passes(self) -> None:
        self.assertEqual(self.classify_topology(), "BOUND_PRE_PUSH")

    def test_bounded_codex_capture_ref_passes(self) -> None:
        capture_ref = (
            "refs/codex/turn-diffs/captures/1784666116506/"
            "3b3a026a-b911-4c68-824d-961a1d1aa611/base"
        )
        self.assertEqual(
            self.classify_topology(
                all_refs={"refs/heads/main", capture_ref},
            ),
            "BOUND_PRE_PUSH",
        )

    def test_published_local_state_passes(self) -> None:
        self.assertEqual(
            self.classify_topology(
                upstream="origin/main",
                remote_tracking_refs={"origin/main"},
                all_refs={"refs/heads/main", "refs/remotes/origin/main"},
            ),
            "PUBLISHED_LOCAL",
        )

    def test_github_actions_detached_checkout_passes(self) -> None:
        ci_url = "https://github.com/lancerbeta/solana-alpha-lab"
        self.assertEqual(
            self.classify_topology(
                branch=None,
                fetch_urls=(ci_url,),
                push_urls=(ci_url,),
                local_branches=set(),
                remote_tracking_refs={"origin/main"},
                all_refs={"refs/remotes/origin/main"},
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/heads/main",
                github_sha=self.HEAD_OID,
            ),
            "GITHUB_ACTIONS_CHECKOUT",
        )

    def test_github_actions_attached_checkout_passes(self) -> None:
        self.assertEqual(
            self.classify_topology(
                upstream="origin/main",
                remote_tracking_refs={"origin/main"},
                all_refs={"refs/heads/main", "refs/remotes/origin/main"},
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/heads/main",
                github_sha=self.HEAD_OID,
            ),
            "GITHUB_ACTIONS_CHECKOUT",
        )

    def test_credential_bearing_origin_fails(self) -> None:
        unsafe_url = "https://credential@github.com/lancerbeta/solana-alpha-lab.git"
        self.assertEqual(
            self.classify_topology(
                fetch_urls=(unsafe_url,),
                push_urls=(unsafe_url,),
            ),
            "INVALID_GIT_TOPOLOGY",
        )

    def test_wrong_owner_or_repository_fails(self) -> None:
        for url in (
            "https://github.com/other/solana-alpha-lab.git",
            "https://github.com/lancerbeta/other.git",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    self.classify_topology(
                        fetch_urls=(url,),
                        push_urls=(url,),
                    ),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_extra_remote_or_url_fails(self) -> None:
        self.assertEqual(
            self.classify_topology(remotes={"origin", "backup"}),
            "INVALID_GIT_TOPOLOGY",
        )
        self.assertEqual(
            self.classify_topology(
                fetch_urls=(module.EXPECTED_ORIGIN_URL,) * 2,
                push_urls=(module.EXPECTED_ORIGIN_URL,) * 2,
            ),
            "INVALID_GIT_TOPOLOGY",
        )

    def test_unexpected_refs_fail(self) -> None:
        for overrides in (
            {
                "local_branches": {"main", "other"},
                "all_refs": {"refs/heads/main", "refs/heads/other"},
            },
            {
                "remote_tracking_refs": {"origin/other"},
                "all_refs": {
                    "refs/heads/main",
                    "refs/remotes/origin/other",
                },
            },
            {
                "tags": {"v1"},
                "all_refs": {"refs/heads/main", "refs/tags/v1"},
            },
            {"all_refs": {"refs/heads/main", "refs/notes/unexpected"}},
            {
                "all_refs": {
                    "refs/heads/main",
                    "refs/codex/turn-diffs/captures/not-bounded/base",
                }
            },
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_topology(**overrides),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_unexpected_refspec_or_upstream_fails(self) -> None:
        for overrides in (
            {
                "fetch_refspecs": (
                    module.EXPECTED_ORIGIN_FETCH_REFSPEC,
                    "+refs/pull/*:refs/remotes/origin/pull/*",
                )
            },
            {"push_refspecs": ("refs/heads/main:refs/heads/main",)},
            {"upstream": "origin/other"},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_topology(**overrides),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_detached_head_outside_github_actions_fails(self) -> None:
        self.assertEqual(
            self.classify_topology(branch=None, local_branches=set()),
            "INVALID_GIT_TOPOLOGY",
        )

    def test_wrong_github_actions_context_fails(self) -> None:
        common = {
            "branch": None,
            "local_branches": set(),
            "github_actions": True,
            "github_repository": module.EXPECTED_GITHUB_REPOSITORY,
            "github_ref": "refs/heads/main",
            "github_sha": self.HEAD_OID,
        }
        for overrides in (
            {"github_repository": "other/solana-alpha-lab"},
            {"github_ref": "refs/heads/other"},
            {"github_sha": "b" * 40},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_topology(**(common | overrides)),
                    "INVALID_GIT_TOPOLOGY",
                )


if __name__ == "__main__":
    unittest.main()
