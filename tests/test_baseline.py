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


class GenericControlBranchPolicyTests(unittest.TestCase):
    def test_accepts_task_and_single_letter_subtask_branches(self) -> None:
        self.assertTrue(module.is_ctrl_generic_control_branch("task17/pilot"))
        self.assertTrue(
            module.is_ctrl_generic_control_branch(
                "task17a/bounded-execution-capacity-panel"
            )
        )

    def test_rejects_ambiguous_subtask_suffixes(self) -> None:
        self.assertFalse(module.is_ctrl_generic_control_branch("task17aa/pilot"))
        self.assertFalse(module.is_ctrl_generic_control_branch("task1a/pilot"))
        self.assertFalse(module.is_ctrl_generic_control_branch("task17A/pilot"))


class TrackedOnlyDeliveryStateTests(unittest.TestCase):
    def test_tracked_only_delivery_uses_current_runtime_contract(self) -> None:
        self.assertTrue(
            module.uses_current_runtime_contract(
                "TRACKED_ONLY_DELIVERY_CANDIDATE"
            )
        )
        self.assertFalse(module.uses_current_runtime_contract("ATOM5_STAGED"))

    def test_accepts_only_clean_attached_delivery_clone(self) -> None:
        self.assertEqual(
            module.classify_tracked_only_delivery_state(
                marker=True,
                branch="main",
                head_oid="a" * 40,
                topology="CLEAN_CLONE",
                staged=set(),
                untracked=set(),
                unstaged=set(),
            ),
            "TRACKED_ONLY_DELIVERY_CANDIDATE",
        )

    def test_rejects_missing_marker_dirty_or_non_clean_clone(self) -> None:
        baseline = {
            "marker": True,
            "branch": "main",
            "head_oid": "a" * 40,
            "topology": "CLEAN_CLONE",
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
        }
        for override in (
            {"marker": False},
            {"branch": "topic"},
            {"head_oid": "not-a-commit"},
            {"topology": "PUBLISHED_LOCAL"},
            {"staged": {"tests/test_ci.py"}},
            {"untracked": {"local/receipt.json"}},
            {"unstaged": {"scripts/validate_ci.py"}},
        ):
            with self.subTest(override=override):
                self.assertIsNone(
                    module.classify_tracked_only_delivery_state(
                        **{**baseline, **override}
                    )
                )


class GitHubActionsPullRequestStateTests(unittest.TestCase):
    def test_accepts_only_clean_detached_pull_request_merge_checkout(self) -> None:
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs={"pull/41/merge"},
            tags=set(),
            all_refs={"refs/remotes/pull/41/merge"},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/pull/41/merge",
            github_sha="a" * 40,
        )
        self.assertEqual(topology, "GITHUB_ACTIONS_PR_CHECKOUT")
        self.assertEqual(
            module.classify_github_actions_runtime_state(
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/pull/41/merge",
                github_sha="a" * 40,
                branch=None,
                head_oid="a" * 40,
                topology=topology,
                staged=set(),
                untracked=set(),
                unstaged=set(),
            ),
            "GITHUB_ACTIONS_PR_CANDIDATE",
        )
        self.assertTrue(
            module.uses_current_runtime_contract(
                "GITHUB_ACTIONS_PR_CANDIDATE"
            )
        )

    def test_accepts_fetch_depth_zero_origin_inventory_for_merge_checkout(self) -> None:
        remote_tracking_refs = {
            "origin/HEAD",
            "origin/main",
            "origin/owner-authority-packet-binding",
            "pull/41/merge",
        }
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs=remote_tracking_refs,
            tags=set(),
            all_refs={f"refs/remotes/{ref}" for ref in remote_tracking_refs},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/pull/41/merge",
            github_sha="a" * 40,
            remote_head_target="refs/remotes/origin/main",
        )
        self.assertEqual(topology, "GITHUB_ACTIONS_PR_CHECKOUT")

    def test_rejects_extra_pull_ref_in_merge_checkout(self) -> None:
        remote_tracking_refs = {"pull/41/merge", "pull/41/head"}
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs=remote_tracking_refs,
            tags=set(),
            all_refs={f"refs/remotes/{ref}" for ref in remote_tracking_refs},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/pull/41/merge",
            github_sha="a" * 40,
        )
        self.assertEqual(topology, "INVALID_GIT_TOPOLOGY")

    def test_rejects_non_merge_ref_and_dirty_pull_request_checkout(self) -> None:
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs={"pull/41/merge"},
            tags=set(),
            all_refs={"refs/remotes/pull/41/merge"},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/pull/41/head",
            github_sha="a" * 40,
        )
        self.assertEqual(topology, "INVALID_GIT_TOPOLOGY")
        self.assertIsNone(
            module.classify_github_actions_runtime_state(
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/pull/41/merge",
                github_sha="a" * 40,
                branch=None,
                head_oid="a" * 40,
                topology="GITHUB_ACTIONS_PR_CHECKOUT",
                staged={"scripts/validate_baseline.py"},
                untracked=set(),
                unstaged=set(),
            )
        )


class GitHubActionsMainStateTests(unittest.TestCase):
    def test_classifies_clean_full_depth_main_checkout_as_runtime_candidate(self) -> None:
        state = module.classify_github_actions_runtime_state(
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/heads/main",
            github_sha="a" * 40,
            branch=None,
            head_oid="a" * 40,
            topology="GITHUB_ACTIONS_CHECKOUT",
            staged=set(),
            untracked=set(),
            unstaged=set(),
        )

        self.assertEqual("GITHUB_ACTIONS_MAIN_CANDIDATE", state)

    def test_accepts_fetch_depth_zero_origin_inventory_for_main_checkout(self) -> None:
        remote_tracking_refs = {
            "origin/HEAD",
            "origin/main",
            "origin/owner-authority-packet-binding",
        }
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs=remote_tracking_refs,
            tags=set(),
            all_refs={f"refs/remotes/{ref}" for ref in remote_tracking_refs},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/heads/main",
            github_sha="a" * 40,
            remote_head_target="refs/remotes/origin/main",
        )
        self.assertEqual(topology, "GITHUB_ACTIONS_CHECKOUT")

    def test_rejects_pull_ref_in_full_depth_main_checkout(self) -> None:
        remote_tracking_refs = {"origin/main", "pull/41/merge"}
        topology = module.classify_git_topology(
            branch=None,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=None,
            local_branches=set(),
            remote_tracking_refs=remote_tracking_refs,
            tags=set(),
            all_refs={f"refs/remotes/{ref}" for ref in remote_tracking_refs},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/heads/main",
            github_sha="a" * 40,
        )
        self.assertEqual(topology, "INVALID_GIT_TOPOLOGY")

    def test_rejects_dirty_main_checkout(self) -> None:
        self.assertIsNone(
            module.classify_github_actions_runtime_state(
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/heads/main",
                github_sha="a" * 40,
                branch=None,
                head_oid="a" * 40,
                topology="GITHUB_ACTIONS_CHECKOUT",
                staged=set(),
                untracked={"local/receipt.json"},
                unstaged=set(),
            )
        )


class GitHubActionsManualDispatchStateTests(unittest.TestCase):
    def test_accepts_only_clean_manual_checkout_of_its_exact_feature_branch(self) -> None:
        branch = "ci-recovery-trigger"
        remote_tracking_refs = {"origin/HEAD", "origin/main", f"origin/{branch}"}
        topology = module.classify_git_topology(
            branch=branch,
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream=f"origin/{branch}",
            local_branches={branch},
            remote_tracking_refs=remote_tracking_refs,
            tags=set(),
            all_refs={f"refs/heads/{branch}"}
            | {f"refs/remotes/{ref}" for ref in remote_tracking_refs},
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref=f"refs/heads/{branch}",
            github_sha="a" * 40,
            remote_head_target="refs/remotes/origin/main",
        )

        self.assertEqual("GITHUB_ACTIONS_BRANCH_CHECKOUT", topology)
        self.assertEqual(
            "GITHUB_ACTIONS_MANUAL_CANDIDATE",
            module.classify_github_actions_runtime_state(
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref=f"refs/heads/{branch}",
                github_sha="a" * 40,
                github_event_name="workflow_dispatch",
                branch=branch,
                head_oid="a" * 40,
                topology=topology,
                staged=set(),
                untracked=set(),
                unstaged=set(),
            ),
        )
        self.assertTrue(
            module.uses_current_runtime_contract(
                "GITHUB_ACTIONS_MANUAL_CANDIDATE"
            )
        )

    def test_rejects_feature_branch_checkout_without_manual_dispatch_event(self) -> None:
        self.assertIsNone(
            module.classify_github_actions_runtime_state(
                github_actions=True,
                github_repository=module.EXPECTED_GITHUB_REPOSITORY,
                github_ref="refs/heads/ci-recovery-trigger",
                github_sha="a" * 40,
                github_event_name="push",
                branch="ci-recovery-trigger",
                head_oid="a" * 40,
                topology="GITHUB_ACTIONS_BRANCH_CHECKOUT",
                staged=set(),
                untracked=set(),
                unstaged=set(),
            )
        )

    def test_rejects_manual_checkout_when_ref_and_branch_differ(self) -> None:
        topology = module.classify_git_topology(
            branch="ci-recovery-trigger",
            head_oid="a" * 40,
            remotes={"origin"},
            fetch_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            push_urls=("https://github.com/lancerbeta/solana-alpha-lab",),
            fetch_refspecs=(module.EXPECTED_ORIGIN_FETCH_REFSPEC,),
            push_refspecs=(),
            upstream="origin/ci-recovery-trigger",
            local_branches={"ci-recovery-trigger"},
            remote_tracking_refs={
                "origin/HEAD",
                "origin/main",
                "origin/ci-recovery-trigger",
            },
            tags=set(),
            all_refs={
                "refs/heads/ci-recovery-trigger",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
                "refs/remotes/origin/ci-recovery-trigger",
            },
            github_actions=True,
            github_repository=module.EXPECTED_GITHUB_REPOSITORY,
            github_ref="refs/heads/other-branch",
            github_sha="a" * 40,
            remote_head_target="refs/remotes/origin/main",
        )

        self.assertEqual("INVALID_GIT_TOPOLOGY", topology)


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

    def classify_atom7_ci_repair(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_OID,
            "commit_count": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_LOCAL_CI_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_PRE_PUSH_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_atom7_final_handoff(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID,
            "commit_count": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_FINAL_HANDOFF_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_atom7_ref_repair(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.ATOM7_FINAL_HANDOFF_COMMIT_OID,
            "commit_count": module.ATOM7_FINAL_HANDOFF_COMMIT_COUNT,
            "parent_oid": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_FINAL_HANDOFF_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_atom7_single_branch_refspec_repair(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID,
            "commit_count": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_FINAL_HANDOFF_COMMIT_OID,
            "tracked": module.atom7_repository_files(),
            "staged": set(module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task04_atom5a(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK04_BASE_COMMIT_OID,
            "commit_count": module.TASK04_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK04_BASE_PARENT_OID,
            "tracked": module.task04_repository_files(),
            "staged": set(module.TASK04_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task04_architecture_committed(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK04_ARCHITECTURE_COMMIT_OID,
            "commit_count": module.TASK04_ARCHITECTURE_COMMIT_COUNT,
            "parent_oid": module.TASK04_BASE_COMMIT_OID,
            "tracked": module.task04_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK04_ARCHITECTURE_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK04_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task04_policy_repair_staged(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK04_ARCHITECTURE_COMMIT_OID,
            "commit_count": module.TASK04_ARCHITECTURE_COMMIT_COUNT,
            "parent_oid": module.TASK04_BASE_COMMIT_OID,
            "tracked": module.task04_repository_files(),
            "staged": set(module.TASK04_POLICY_REPAIR_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK04_ARCHITECTURE_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK04_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task04_policy_repair_committed(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK04_POLICY_REPAIR_COMMIT_COUNT,
            "parent_oid": module.TASK04_ARCHITECTURE_COMMIT_OID,
            "tracked": module.task04_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK04_POLICY_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK04_POLICY_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task05_atom5a(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK05_BASE_COMMIT_OID,
            "commit_count": module.TASK05_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK05_BASE_PARENT_OID,
            "tracked": module.task05_repository_files(),
            "staged": set(module.TASK05_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK04_POLICY_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK04_POLICY_REPAIR_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task05_committed(self, **overrides: object) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK05_COMMIT_COUNT,
            "parent_oid": module.TASK05_BASE_COMMIT_OID,
            "tracked": module.task05_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK05_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK05_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task05_finalization_staged(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": module.TASK05_FINALIZATION_BASE_COMMIT_OID,
            "commit_count": module.TASK05_FINALIZATION_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK05_FINALIZATION_BASE_PARENT_OID,
            "tracked": module.task05_finalization_repository_files(),
            "staged": set(module.TASK05_FINALIZATION_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK05_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK05_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task05_finalization_committed(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK05_FINALIZATION_COMMIT_COUNT,
            "parent_oid": module.TASK05_FINALIZATION_BASE_COMMIT_OID,
            "tracked": module.task05_finalization_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK05_FINALIZATION_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK05_FINALIZATION_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task06_atom7a(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK06_BASE_COMMIT_OID,
            "commit_count": module.TASK06_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK06_BASE_PARENT_OID,
            "tracked": module.task06_repository_files(),
            "staged": set(module.TASK06_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK05_FINALIZATION_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK05_FINALIZATION_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task06_atom7b(self, **overrides: object) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK06_COMMIT_COUNT,
            "parent_oid": module.TASK06_BASE_COMMIT_OID,
            "tracked": module.task06_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK06_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK06_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task06_finalization_staged(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": module.TASK06_FINALIZATION_BASE_COMMIT_OID,
            "commit_count": module.TASK06_FINALIZATION_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK06_FINALIZATION_BASE_PARENT_OID,
            "tracked": module.task06_finalization_repository_files(),
            "staged": set(module.TASK06_FINALIZATION_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK06_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK06_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task06_finalization_committed(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK06_FINALIZATION_COMMIT_COUNT,
            "parent_oid": module.TASK06_FINALIZATION_BASE_COMMIT_OID,
            "tracked": module.task06_finalization_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK06_FINALIZATION_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK06_FINALIZATION_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task07_atom6a(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK07_BASE_COMMIT_OID,
            "commit_count": module.TASK07_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK07_BASE_PARENT_OID,
            "tracked": module.task07_repository_files(),
            "staged": set(module.TASK07_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK06_FINALIZATION_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK06_FINALIZATION_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task07_atom6b(self, **overrides: object) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK07_COMMIT_COUNT,
            "parent_oid": module.TASK07_BASE_COMMIT_OID,
            "tracked": module.task07_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK07_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK07_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task08_atom8a(self, **overrides: object) -> str:
        arguments = {
            "head_oid": module.TASK08_BASE_COMMIT_OID,
            "commit_count": module.TASK08_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK08_BASE_PARENT_OID,
            "tracked": module.task08_repository_files(),
            "staged": set(module.TASK08_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK07_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK07_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task08_atom8b(self, **overrides: object) -> str:
        arguments = {
            "head_oid": "1" * 40,
            "commit_count": module.TASK08_COMMIT_COUNT,
            "parent_oid": module.TASK08_BASE_COMMIT_OID,
            "tracked": module.task08_repository_files(),
            "staged": set(),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK08_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK08_CHANGED_FILES),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def classify_task09_atom2_policy_repair(
        self,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": module.TASK09_BASE_COMMIT_OID,
            "commit_count": module.TASK09_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK09_BASE_PARENT_OID,
            "tracked": module.task09_atom2_repository_files(),
            "staged": set(module.TASK09_CHANGED_FILES),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": module.TASK09_BASE_COMMIT_SUBJECT,
            "commit_changed": set(),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_task09_atom2_policy_repair_exact_staged_state_passes(
        self,
    ) -> None:
        self.assertEqual(
            self.classify_task09_atom2_policy_repair(),
            "TASK09_ATOM2_POLICY_REPAIR_STAGED",
        )

    def test_task09_atom2_policy_repair_state_is_fail_closed(self) -> None:
        missing = set(module.TASK09_CHANGED_FILES)
        missing.remove("tests/test_baton_repository_policy.py")
        tracked_missing = module.task09_atom2_repository_files()
        tracked_missing.remove(
            "docs/contracts/pumpswap_touch_observation_contract_v1.md"
        )
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK09_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"tracked": tracked_missing},
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"scripts/validate_baseline.py"}},
            {"head_oid": module.TASK09_BASE_PARENT_OID},
            {"parent_oid": module.TASK09_BASE_PARENT_OIDS[1]},
            {"commit_subject": "Merge pull request #6"},
            {"commit_changed": {"unexpected.txt"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task09_atom2_policy_repair(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task09_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK09_FEATURE_BRANCH,
            "task09/pumpswap-touch-pilot",
        )
        self.assertEqual(
            module.TASK09_BASE_COMMIT_OID,
            "d85c99e17be5a190687122374a6ff818d2215f72",
        )
        self.assertEqual(
            module.TASK09_BASE_TREE_OID,
            "c8464fd64fc24b09a83c973a4a4966884437f32d",
        )
        self.assertEqual(
            module.TASK09_BASE_PARENT_OIDS,
            (
                "308a062f3c5cb28c1ac9ba1c1fc5fc368f74bd8a",
                "c777c6ae8cee28f14ad35e3243689659210ebbb8",
            ),
        )
        self.assertEqual(module.TASK09_BASE_COMMIT_COUNT, 39)
        self.assertEqual(module.TASK09_BASE_FILE_COUNT, 226)
        self.assertEqual(
            module.TASK09_POLICY_REPAIR_MODIFIED_FILES,
            {
                "catalog/assets/core.yaml",
                "catalog/catalog_manifest.yaml",
                "scripts/validate_baseline.py",
                "scripts/validate_task04.py",
                "tests/test_baseline.py",
                "tests/test_baton_repository_policy.py",
                "tests/test_task04_core_stack.py",
                "tests/test_task05_catalog_queries.py",
                "tests/test_task06_catalog.py",
                "tests/test_task07_catalog.py",
                "tests/test_task08_catalog.py",
            },
        )
        self.assertEqual(
            module.TASK09_ATOM2_CREATED_FILES,
            {
                "docs/contracts/pumpswap_touch_observation_contract_v1.md",
                "tests/fixtures/task09/"
                "pumpswap_touch_observation_contract_v1.json",
                "tests/test_task09_pumpswap_touch_observation_contract.py",
            },
        )
        self.assertEqual(len(module.TASK09_CHANGED_FILES), 14)
        self.assertEqual(
            module.TASK09_ATOM2_EXPECTED_REPOSITORY_FILE_COUNT,
            229,
        )
        self.assertEqual(
            module.TASK09_ATOM2_COMMIT_OID,
            "fca6b3ee581954b0a4e5e3972c74db09c5f921e5",
        )
        self.assertEqual(
            module.TASK09_ATOM2_TREE_OID,
            "1fe2784ebe199c6b71c16c059ea8413397195593",
        )
        self.assertEqual(module.TASK09_ATOM2_COMMIT_COUNT, 40)
        self.assertEqual(
            module.TASK09_ATOM2_COMMIT_SUBJECT,
            "feat: freeze TASK-09 PumpSwap Touch contract",
        )
        self.assertEqual(
            module.TASK09_ATOM3_CREATED_FILES,
            {
                "src/solana_alpha_lab/pumpswap_touch_decoder.py",
                "tests/fixtures/task09/pumpswap_idl_subset_v1.json",
                "tests/test_task09_pumpswap_touch_decoder.py",
            },
        )
        self.assertEqual(
            module.TASK09_ATOM3_MODIFIED_FILES,
            {
                "catalog/assets/core.yaml",
                "catalog/catalog_manifest.yaml",
                "docs/contracts/pumpswap_touch_observation_contract_v1.md",
                "scripts/validate_baseline.py",
                "scripts/validate_task04.py",
                "tests/test_baseline.py",
                "tests/test_baton_repository_policy.py",
                "tests/test_task04_core_stack.py",
                "tests/test_task05_catalog_queries.py",
                "tests/test_task06_catalog.py",
                "tests/test_task07_catalog.py",
                "tests/test_task08_catalog.py",
            },
        )
        self.assertEqual(len(module.TASK09_ATOM3_CHANGED_FILES), 15)
        self.assertEqual(
            module.TASK09_ATOM3_COMMIT_OID,
            "d5e9545e99111b035def4b8a95223635ba9e724a",
        )
        self.assertEqual(
            module.TASK09_ATOM3_TREE_OID,
            "f527e00c4276f670429da9567b689ac669084da9",
        )
        self.assertEqual(
            module.TASK09_ATOM4_CREATED_FILES,
            {
                "scripts/run_task09_pumpswap_touch_probe.py",
                "src/solana_alpha_lab/pumpswap_touch_probe.py",
                "tests/test_task09_pumpswap_touch_probe.py",
            },
        )
        self.assertEqual(
            module.TASK09_ATOM4_MODIFIED_FILES,
            module.TASK09_ATOM3_MODIFIED_FILES,
        )
        self.assertEqual(len(module.TASK09_ATOM4_CHANGED_FILES), 15)
        self.assertEqual(
            module.TASK09_ATOM4_COMMIT_OID,
            "c02294407b17f71b44725ef61cc022fecd7ba80f",
        )
        self.assertEqual(
            module.TASK09_ATOM4_TREE_OID,
            "c1cd3540368d9e93e16ad2e8fa00a5eff1e67daa",
        )
        self.assertEqual(
            module.TASK09_FINALIZATION_CREATED_FILES,
            {
                "docs/evidence/task09/pumpswap_touch_probe_execution_receipt_v1.json",
                "docs/evidence/task09/pumpswap_touch_probe_execution_summary_v1.md",
                "tests/fixtures/task09/pumpswap_touch_probe_live_evidence_v1.json",
                "tests/test_task09_pumpswap_touch_probe_evidence.py",
            },
        )
        self.assertEqual(
            module.TASK09_FINALIZATION_DOMAIN_MODIFIED_FILES,
            {
                "docs/contracts/pumpswap_touch_observation_contract_v1.md",
                "src/solana_alpha_lab/pumpswap_touch_probe.py",
                "tests/test_task09_pumpswap_touch_probe.py",
            },
        )
        self.assertEqual(
            len(module.TASK09_FINALIZATION_CHANGED_FILES),
            23,
        )
        self.assertEqual(
            module.TASK09_ATOM3_EXPECTED_REPOSITORY_FILE_COUNT,
            232,
        )
        self.assertEqual(
            module.TASK09_ATOM4_EXPECTED_REPOSITORY_FILE_COUNT,
            235,
        )
        self.assertEqual(module.TASK09_EXPECTED_REPOSITORY_FILE_COUNT, 239)
        self.assertEqual(module.TASK09_BASE_CATALOG_VERSION, "0.8.5")
        self.assertEqual(
            module.TASK09_ATOM2_EXPECTED_CATALOG_VERSION,
            "0.8.6",
        )
        self.assertEqual(
            module.TASK09_ATOM3_EXPECTED_CATALOG_VERSION,
            "0.8.7",
        )
        self.assertEqual(
            module.TASK09_ATOM4_EXPECTED_CATALOG_VERSION,
            "0.8.8",
        )
        self.assertEqual(
            module.TASK09_ATOM4_EXPECTED_CATALOG_ASSET_COUNT,
            191,
        )
        self.assertEqual(module.TASK09_EXPECTED_CATALOG_VERSION, "0.9.0")
        self.assertEqual(module.TASK09_EXPECTED_CATALOG_ASSET_COUNT, 205)
        self.assertEqual(module.TASK09_EXPECTED_CATALOG_QUERY_COUNT, 7)

    def classify_task09_atom3(
        self,
        *,
        committed: bool = False,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": (
                "1" * 40 if committed else module.TASK09_ATOM2_COMMIT_OID
            ),
            "commit_count": (
                module.TASK09_ATOM3_COMMIT_COUNT
                if committed
                else module.TASK09_ATOM2_COMMIT_COUNT
            ),
            "parent_oid": (
                module.TASK09_ATOM2_COMMIT_OID
                if committed
                else module.TASK09_BASE_COMMIT_OID
            ),
            "tracked": module.task09_atom3_repository_files(),
            "staged": (
                set() if committed else set(module.TASK09_ATOM3_CHANGED_FILES)
            ),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": (
                module.TASK09_ATOM3_COMMIT_SUBJECT
                if committed
                else module.TASK09_ATOM2_COMMIT_SUBJECT
            ),
            "commit_changed": (
                set(module.TASK09_ATOM3_CHANGED_FILES)
                if committed
                else set(module.TASK09_CHANGED_FILES)
            ),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_task09_atom3_staged_and_committed_states_pass(self) -> None:
        self.assertEqual(
            self.classify_task09_atom3(),
            "TASK09_ATOM3_DECODER_STAGED",
        )
        self.assertEqual(
            self.classify_task09_atom3(committed=True),
            "TASK09_ATOM3_DECODER_COMMITTED",
        )

    def test_task09_atom3_state_is_fail_closed(self) -> None:
        missing = set(module.TASK09_ATOM3_CHANGED_FILES)
        missing.remove("src/solana_alpha_lab/pumpswap_touch_decoder.py")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK09_ATOM3_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"tests/test_baseline.py"}},
            {"parent_oid": module.TASK09_BASE_PARENT_OID},
            {"commit_subject": "feat: add decoder"},
            {"commit_changed": {"unexpected.txt"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task09_atom3(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def classify_task09_atom4(
        self,
        *,
        committed: bool = False,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": (
                "2" * 40 if committed else module.TASK09_ATOM3_COMMIT_OID
            ),
            "commit_count": (
                module.TASK09_ATOM4_COMMIT_COUNT
                if committed
                else module.TASK09_ATOM3_COMMIT_COUNT
            ),
            "parent_oid": (
                module.TASK09_ATOM3_COMMIT_OID
                if committed
                else module.TASK09_ATOM2_COMMIT_OID
            ),
            "tracked": module.task09_repository_files(),
            "staged": (
                set() if committed else set(module.TASK09_ATOM4_CHANGED_FILES)
            ),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": (
                module.TASK09_ATOM4_COMMIT_SUBJECT
                if committed
                else module.TASK09_ATOM3_COMMIT_SUBJECT
            ),
            "commit_changed": (
                set(module.TASK09_ATOM4_CHANGED_FILES)
                if committed
                else set(module.TASK09_ATOM3_CHANGED_FILES)
            ),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_task09_atom4_staged_and_committed_states_pass(self) -> None:
        self.assertEqual(
            self.classify_task09_atom4(),
            "TASK09_ATOM4_PROBE_STAGED",
        )
        self.assertEqual(
            self.classify_task09_atom4(committed=True),
            "TASK09_ATOM4_PROBE_COMMITTED",
        )

    def test_task09_atom4_state_is_fail_closed(self) -> None:
        missing = set(module.TASK09_ATOM4_CHANGED_FILES)
        missing.remove("src/solana_alpha_lab/pumpswap_touch_probe.py")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK09_ATOM4_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"tests/test_baseline.py"}},
            {"parent_oid": module.TASK09_BASE_COMMIT_OID},
            {"commit_subject": "feat: add probe"},
            {"commit_changed": {"unexpected.txt"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task09_atom4(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def classify_task09_finalization(
        self,
        *,
        committed: bool = False,
        **overrides: object,
    ) -> str:
        arguments = {
            "head_oid": (
                "3" * 40 if committed else module.TASK09_ATOM4_COMMIT_OID
            ),
            "commit_count": (
                module.TASK09_FINALIZATION_COMMIT_COUNT
                if committed
                else module.TASK09_ATOM4_COMMIT_COUNT
            ),
            "parent_oid": (
                module.TASK09_ATOM4_COMMIT_OID
                if committed
                else module.TASK09_ATOM3_COMMIT_OID
            ),
            "tracked": module.task09_finalization_repository_files(),
            "staged": (
                set()
                if committed
                else set(module.TASK09_FINALIZATION_CHANGED_FILES)
            ),
            "untracked": set(),
            "unstaged": set(),
            "commit_subject": (
                module.TASK09_FINALIZATION_COMMIT_SUBJECT
                if committed
                else module.TASK09_ATOM4_COMMIT_SUBJECT
            ),
            "commit_changed": (
                set(module.TASK09_FINALIZATION_CHANGED_FILES)
                if committed
                else set(module.TASK09_ATOM4_CHANGED_FILES)
            ),
        }
        arguments.update(overrides)
        return module.classify_state(**arguments)

    def test_task09_finalization_staged_and_committed_states_pass(self) -> None:
        self.assertEqual(
            self.classify_task09_finalization(),
            "TASK09_FINALIZATION_STAGED",
        )
        self.assertEqual(
            self.classify_task09_finalization(committed=True),
            "TASK09_FINALIZATION_COMMITTED",
        )

    def test_task09_finalization_state_is_fail_closed(self) -> None:
        missing = set(module.TASK09_FINALIZATION_CHANGED_FILES)
        missing.remove(
            "docs/evidence/task09/"
            "pumpswap_touch_probe_execution_receipt_v1.json"
        )
        cases = (
            {"staged": missing},
            {
                "staged": (
                    set(module.TASK09_FINALIZATION_CHANGED_FILES)
                    | {"unexpected.txt"}
                )
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"tests/test_baseline.py"}},
            {"parent_oid": module.TASK09_BASE_COMMIT_OID},
            {"commit_subject": "feat: accept evidence"},
            {"commit_changed": {"unexpected.txt"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task09_finalization(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task08_atom8a_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task08_atom8a(),
            "TASK08_ATOM8A_CANDIDATE_STAGED",
        )

    def test_task08_atom8a_state_is_fail_closed(self) -> None:
        missing = set(module.TASK08_CHANGED_FILES)
        missing.remove("tests/test_task08_catalog.py")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK08_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"catalog/assets/core.yaml"}},
            {"parent_oid": module.TASK07_BASE_PARENT_OID},
            {
                "commit_changed":
                set(module.TASK07_CHANGED_FILES)
                - {"tests/test_task07_provider_smoke_transport.py"}
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task08_atom8a(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task08_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task08_atom8b(head_oid=future_oid),
                    "TASK08_ATOM8B_CANDIDATE_COMMITTED",
                )

    def test_task08_future_commit_contract_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK08_BASE_COMMIT_OID,
            "commit_count": module.TASK08_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK08_BASE_PARENT_OID,
            "commit_subject": "feat: arbitrary lifecycle probe",
            "commit_changed":
                set(module.TASK08_CHANGED_FILES)
                - {"tests/test_task08_catalog.py"},
            "staged": set(module.TASK08_CHANGED_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"catalog/assets/core.yaml"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task08_atom8b(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task08_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK08_BASE_COMMIT_OID,
            "03731b647ca4d47283a2dcb4154622865b606327",
        )
        self.assertEqual(
            module.TASK08_BASE_TREE_OID,
            "0462d283a5b0a6a1c0a6eab63b2e7e8463757522",
        )
        self.assertEqual(module.TASK08_BASE_COMMIT_COUNT, 19)
        self.assertEqual(module.TASK08_BASE_FILE_COUNT, 142)
        self.assertEqual(
            module.TASK08_MODIFIED_FILES,
            {
                "catalog/assets/core.yaml",
                "catalog/assets/lifecycle.yaml",
                "catalog/catalog_manifest.yaml",
                "catalog/generated/asset_edges.json",
                "docs/PROJECT_MAP.md",
                "scripts/validate_baseline.py",
                "scripts/validate_task04.py",
                "tests/test_baseline.py",
                "tests/test_catalog.py",
                "tests/test_task04_core_stack.py",
                "tests/test_task05_catalog_queries.py",
                "tests/test_task06_catalog.py",
                "tests/test_task07_catalog.py",
            },
        )
        self.assertEqual(
            module.TASK08_CREATED_FILES,
            {
                "docs/contracts/lifecycle_discovery_contract_v1.md",
                "docs/contracts/lifecycle_discovery_probe_transport_contract_v1.md",
                "docs/evidence/task08/"
                "lifecycle_discovery_probe_execution_receipt_v1.json",
                "docs/evidence/task08/"
                "lifecycle_discovery_probe_execution_summary_v1.md",
                "scripts/run_task08_lifecycle_discovery_probe.py",
                "src/solana_alpha_lab/lifecycle_discovery.py",
                "src/solana_alpha_lab/lifecycle_discovery_transport.py",
                "src/solana_alpha_lab/pump_event_decoder.py",
                "tests/fixtures/task08/lifecycle_discovery_contract_v1.json",
                "tests/fixtures/task08/"
                "lifecycle_discovery_probe_live_evidence_v1.json",
                "tests/fixtures/task08/pump_event_idl_subset_v1.json",
                "tests/test_task08_catalog.py",
                "tests/test_task08_lifecycle_discovery.py",
                "tests/test_task08_lifecycle_discovery_probe_evidence.py",
                "tests/test_task08_lifecycle_discovery_transport.py",
                "tests/test_task08_pump_event_decoder.py",
            },
        )
        self.assertEqual(len(module.TASK08_CHANGED_FILES), 29)
        self.assertEqual(module.TASK08_EXPECTED_REPOSITORY_FILE_COUNT, 158)
        self.assertEqual(module.TASK08_COMMIT_COUNT, 20)
        self.assertEqual(
            module.TASK08_COMMIT_SUBJECT,
            "feat: add TASK-08 lifecycle discovery probe",
        )
        self.assertEqual(module.TASK08_EXPECTED_CATALOG_VERSION, "0.7.0")
        self.assertEqual(module.TASK08_EXPECTED_CATALOG_ASSET_COUNT, 158)
        self.assertEqual(module.TASK08_EXPECTED_CATALOG_QUERY_COUNT, 7)
        self.assertEqual(
            module.IGNORED_REPOSITORY_PREFIXES,
            {"data/raw"},
        )

    def test_task07_atom6a_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task07_atom6a(),
            "TASK07_ATOM6A_CANDIDATE_STAGED",
        )

    def test_task07_atom6a_state_is_fail_closed(self) -> None:
        missing = set(module.TASK07_CHANGED_FILES)
        missing.remove("tests/test_task07_provider_smoke_transport.py")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK07_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"catalog/assets/core.yaml"}},
            {
                "commit_changed":
                set(module.TASK06_FINALIZATION_FILES)
                - {"docs/tasks/TASK-06.md"}
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task07_atom6a(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task07_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task07_atom6b(head_oid=future_oid),
                    "TASK07_ATOM6B_CANDIDATE_COMMITTED",
                )

    def test_task07_future_commit_contract_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK07_BASE_COMMIT_OID,
            "commit_count": module.TASK07_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK07_BASE_PARENT_OID,
            "commit_subject": "feat: arbitrary provider smoke",
            "commit_changed":
                set(module.TASK07_CHANGED_FILES)
                - {"tests/test_task07_provider_smoke_transport.py"},
            "staged": set(module.TASK07_CHANGED_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"catalog/assets/core.yaml"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task07_atom6b(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task07_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK07_BASE_COMMIT_OID,
            "8c52f16774306f88b332c7641bc5a14c6fda0786",
        )
        self.assertEqual(
            module.TASK07_BASE_TREE_OID,
            "a17836456013f841a49ede261615e390cd41850f",
        )
        self.assertEqual(module.TASK07_BASE_COMMIT_COUNT, 18)
        self.assertEqual(module.TASK07_BASE_FILE_COUNT, 129)
        self.assertEqual(
            module.TASK07_MODIFIED_FILES,
            {
                "catalog/assets/core.yaml",
                "catalog/assets/lifecycle.yaml",
                "catalog/catalog_manifest.yaml",
                "catalog/generated/asset_edges.json",
                "docs/PROJECT_MAP.md",
                "scripts/validate_baseline.py",
                "scripts/validate_task04.py",
                "tests/test_baseline.py",
                "tests/test_catalog.py",
                "tests/test_task04_core_stack.py",
                "tests/test_task05_catalog_queries.py",
                "tests/test_task06_catalog.py",
            },
        )
        self.assertEqual(
            module.TASK07_CREATED_FILES,
            {
                "docs/contracts/provider_smoke_runtime_contract_v1.md",
                "docs/contracts/provider_smoke_transport_contract_v1.md",
                "docs/evidence/task07/provider_smoke_execution_receipt_v1.json",
                "docs/evidence/task07/provider_smoke_execution_summary_v1.md",
                "scripts/run_task07_provider_smoke.py",
                "src/solana_alpha_lab/provider_smoke.py",
                "src/solana_alpha_lab/provider_smoke_transport.py",
                "tests/fixtures/task07/provider_smoke_contract_v1.json",
                "tests/fixtures/task07/provider_smoke_live_evidence_v1.json",
                "tests/test_task07_catalog.py",
                "tests/test_task07_provider_smoke.py",
                "tests/test_task07_provider_smoke_evidence.py",
                "tests/test_task07_provider_smoke_transport.py",
            },
        )
        self.assertEqual(len(module.TASK07_CHANGED_FILES), 25)
        self.assertEqual(module.TASK07_EXPECTED_REPOSITORY_FILE_COUNT, 142)
        self.assertEqual(module.TASK07_COMMIT_COUNT, 19)
        self.assertEqual(
            module.TASK07_COMMIT_SUBJECT,
            "feat: add TASK-07 bounded provider smoke",
        )
        self.assertEqual(module.TASK07_EXPECTED_CATALOG_VERSION, "0.6.0")
        self.assertEqual(module.TASK07_EXPECTED_CATALOG_ASSET_COUNT, 141)
        self.assertEqual(module.TASK07_EXPECTED_CATALOG_QUERY_COUNT, 7)
        self.assertEqual(
            module.IGNORED_REPOSITORY_PREFIXES,
            {"data/raw"},
        )

    def test_task06_atom7a_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task06_atom7a(),
            "TASK06_ATOM7A_CANDIDATE_STAGED",
        )

    def test_task06_atom7a_state_is_fail_closed(self) -> None:
        missing = set(module.TASK06_CHANGED_FILES)
        missing.remove("tests/test_task06_storage_budget.py")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK06_CHANGED_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"catalog/assets/core.yaml"}},
            {
                "commit_changed":
                set(module.TASK05_FINALIZATION_FILES)
                - {"docs/tasks/TASK-05.md"}
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task06_atom7a(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task06_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task06_atom7b(head_oid=future_oid),
                    "TASK06_ATOM7B_CANDIDATE_COMMITTED",
                )

    def test_task06_future_commit_contract_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK06_BASE_COMMIT_OID,
            "commit_count": module.TASK06_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK06_BASE_PARENT_OID,
            "commit_subject": "feat: arbitrary storage boundary",
            "commit_changed":
                set(module.TASK06_CHANGED_FILES)
                - {"tests/test_task06_storage_budget.py"},
            "staged": set(module.TASK06_CHANGED_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"catalog/assets/core.yaml"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task06_atom7b(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task06_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK06_BASE_COMMIT_OID,
            "1db62c7abc06bcb4ab209b3db7f4eb858f64330a",
        )
        self.assertEqual(
            module.TASK06_BASE_TREE_OID,
            "6ec5e7a10b7c547b02c37436a1f37d0729a6f657",
        )
        self.assertEqual(module.TASK06_BASE_COMMIT_COUNT, 16)
        self.assertEqual(module.TASK06_BASE_FILE_COUNT, 112)
        self.assertEqual(
            module.TASK06_MODIFIED_FILES,
            {
                "catalog/assets/core.yaml",
                "catalog/assets/lifecycle.yaml",
                "catalog/catalog_manifest.yaml",
                "catalog/generated/asset_edges.json",
                "docs/PROJECT_MAP.md",
                "scripts/validate_baseline.py",
                "scripts/validate_task04.py",
                "tests/test_baseline.py",
                "tests/test_catalog.py",
                "tests/test_task04_core_stack.py",
                "tests/test_task05_catalog_queries.py",
            },
        )
        self.assertEqual(
            module.TASK06_CREATED_FILES,
            {
                "docs/contracts/dataset_manifest_contract_v1.md",
                "docs/contracts/raw_parquet_store_contract_v1.md",
                "docs/contracts/raw_storage_contract_v1.md",
                "docs/contracts/storage_budget_contract_v1.md",
                "docs/tasks/TASK-06.md",
                "src/solana_alpha_lab/storage/__init__.py",
                "src/solana_alpha_lab/storage/budget.py",
                "src/solana_alpha_lab/storage/manifests.py",
                "src/solana_alpha_lab/storage/parquet_store.py",
                "src/solana_alpha_lab/storage/raw_envelope.py",
                "tests/fixtures/task06/manifest_identity_v1.json",
                "tests/fixtures/task06/raw_envelope_v1.json",
                "tests/test_task06_catalog.py",
                "tests/test_task06_manifests.py",
                "tests/test_task06_parquet_store.py",
                "tests/test_task06_raw_envelope.py",
                "tests/test_task06_storage_budget.py",
            },
        )
        self.assertEqual(len(module.TASK06_CHANGED_FILES), 28)
        self.assertEqual(module.TASK06_EXPECTED_REPOSITORY_FILE_COUNT, 129)
        self.assertEqual(module.TASK06_COMMIT_COUNT, 17)
        self.assertEqual(
            module.TASK06_COMMIT_SUBJECT,
            "feat: add TASK-06 raw storage boundary",
        )
        self.assertEqual(module.TASK06_EXPECTED_CATALOG_VERSION, "0.5.0")
        self.assertEqual(module.TASK06_EXPECTED_CATALOG_ASSET_COUNT, 128)
        self.assertEqual(module.TASK06_EXPECTED_CATALOG_QUERY_COUNT, 7)

    def test_task06_finalization_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task06_finalization_staged(),
            "TASK06_FINALIZATION_STAGED",
        )

    def test_task06_finalization_staged_state_is_fail_closed(self) -> None:
        missing = set(module.TASK06_FINALIZATION_FILES)
        missing.remove("docs/tasks/TASK-06.md")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK06_FINALIZATION_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"docs/handoffs/latest.md"}},
            {
                "commit_changed":
                set(module.TASK06_CHANGED_FILES)
                - {"tests/test_task06_storage_budget.py"}
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task06_finalization_staged(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task06_finalization_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task06_finalization_committed(
                        head_oid=future_oid
                    ),
                    "TASK06_FINALIZATION_COMMITTED",
                )

    def test_task06_finalization_future_commit_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK06_FINALIZATION_BASE_COMMIT_OID,
            "commit_count": module.TASK06_FINALIZATION_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK06_FINALIZATION_BASE_PARENT_OID,
            "commit_subject": "docs: arbitrary handoff",
            "commit_changed":
                set(module.TASK06_FINALIZATION_FILES)
                - {"docs/tasks/TASK-06.md"},
            "staged": set(module.TASK06_FINALIZATION_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"docs/handoffs/latest.md"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task06_finalization_committed(
                        **{key: value}
                    ),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task06_finalization_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK06_FINALIZATION_BASE_COMMIT_OID,
            "23ead28bfb9fe9c60fd143b7e69267b61bc8512c",
        )
        self.assertEqual(
            module.TASK06_FINALIZATION_BASE_TREE_OID,
            "dead22b1d8bae02fead79d3aa7ef27c13f6c840a",
        )
        self.assertEqual(module.TASK06_FINALIZATION_BASE_COMMIT_COUNT, 17)
        self.assertEqual(module.TASK06_FINALIZATION_BASE_FILE_COUNT, 129)
        self.assertEqual(len(module.TASK06_FINALIZATION_MODIFIED_FILES), 14)
        self.assertEqual(len(module.TASK06_FINALIZATION_CREATED_FILES), 0)
        self.assertEqual(len(module.TASK06_FINALIZATION_FILES), 14)
        self.assertEqual(
            module.TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT,
            129,
        )
        self.assertEqual(module.TASK06_FINALIZATION_COMMIT_COUNT, 18)
        self.assertEqual(
            module.TASK06_FINALIZATION_COMMIT_SUBJECT,
            "docs: finalize TASK-06 repository handoff",
        )
        self.assertEqual(
            module.TASK06_FINALIZATION_EXPECTED_CATALOG_VERSION,
            "0.5.1",
        )
        self.assertEqual(
            module.TASK06_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT,
            128,
        )
        self.assertEqual(
            module.TASK06_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT,
            7,
        )

    def test_task04_atom5a_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task04_atom5a(),
            "TASK04_ATOM5A_CANDIDATE_STAGED",
        )

    def test_task04_atom5a_missing_or_extra_staged_file_fails(self) -> None:
        missing = set(module.TASK04_CHANGED_FILES)
        missing.remove(next(iter(missing)))
        self.assertEqual(
            self.classify_task04_atom5a(staged=missing),
            "INVALID_REPOSITORY_STATE",
        )
        extra = set(module.TASK04_CHANGED_FILES) | {"unexpected.txt"}
        self.assertEqual(
            self.classify_task04_atom5a(staged=extra),
            "INVALID_REPOSITORY_STATE",
        )

    def test_task04_atom5a_untracked_or_unstaged_file_fails(self) -> None:
        self.assertEqual(
            self.classify_task04_atom5a(untracked={"unexpected.txt"}),
            "INVALID_REPOSITORY_STATE",
        )
        self.assertEqual(
            self.classify_task04_atom5a(unstaged={"README.md"}),
            "INVALID_REPOSITORY_STATE",
        )

    def test_task04_atom5a_base_constants_are_exact(self) -> None:
        self.assertEqual(module.TASK04_BASE_COMMIT_OID, "f8ff483dbcf00454852a9638466eb4123e2c5809")
        self.assertEqual(module.TASK04_BASE_TREE_OID, "cfbf181fa2c005cf517a218c70ede51c701b5a43")
        self.assertEqual(module.TASK04_BASE_FILE_COUNT, 77)
        self.assertEqual(len(module.TASK04_CHANGED_FILES), 38)
        self.assertEqual(module.TASK04_EXPECTED_REPOSITORY_FILE_COUNT, 96)

    def test_task04_architecture_committed_state_is_exact(self) -> None:
        self.assertEqual(
            self.classify_task04_architecture_committed(),
            "TASK04_ATOM5B_ARCHITECTURE_COMMITTED",
        )

    def test_task04_architecture_committed_identity_drift_fails(self) -> None:
        cases = {
            "head_oid": "0" * 40,
            "commit_count": module.TASK04_ARCHITECTURE_COMMIT_COUNT + 1,
            "parent_oid": module.TASK04_BASE_PARENT_OID,
            "commit_subject": "wrong subject",
            "commit_changed": set(module.TASK04_CHANGED_FILES) - {"AGENTS.md"},
            "staged": {"unexpected.txt"},
            "untracked": {"unexpected.txt"},
            "unstaged": {"README.md"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task04_architecture_committed(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task04_policy_repair_staged_state_is_exact(self) -> None:
        self.assertEqual(
            self.classify_task04_policy_repair_staged(),
            "TASK04_ATOM5B_POLICY_REPAIR_STAGED",
        )

    def test_task04_policy_repair_staged_inventory_or_dirty_tree_fails(self) -> None:
        missing = set(module.TASK04_POLICY_REPAIR_FILES)
        missing.remove("catalog/assets/core.yaml")
        cases = (
            {"staged": missing},
            {"staged": set(module.TASK04_POLICY_REPAIR_FILES) | {"unexpected.txt"}},
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"scripts/validate_baseline.py"}},
            {"commit_changed": set(module.TASK04_CHANGED_FILES) - {"README.md"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task04_policy_repair_staged(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task04_policy_repair_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task04_policy_repair_committed(
                        head_oid=future_oid
                    ),
                    "TASK04_ATOM5B_POLICY_REPAIR_COMMITTED",
                )

    def test_task04_policy_repair_future_commit_contract_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK04_ARCHITECTURE_COMMIT_OID,
            "commit_count": module.TASK04_ARCHITECTURE_COMMIT_COUNT,
            "parent_oid": module.TASK04_BASE_COMMIT_OID,
            "commit_subject": module.TASK04_ARCHITECTURE_COMMIT_SUBJECT,
            "commit_changed": set(module.TASK04_POLICY_REPAIR_FILES)
            - {"tests/test_baseline.py"},
            "staged": set(module.TASK04_POLICY_REPAIR_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"catalog/assets/core.yaml"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task04_policy_repair_committed(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task04_atom5b_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK04_ARCHITECTURE_COMMIT_OID,
            "b2bae357bb5ec84c6b28ceeeb44fb2d6176dbae3",
        )
        self.assertEqual(
            module.TASK04_ARCHITECTURE_TREE_OID,
            "388fa66d0890e1b38122151b808f63a9b463c1b5",
        )
        self.assertEqual(module.TASK04_ARCHITECTURE_COMMIT_COUNT, 13)
        self.assertEqual(module.TASK04_POLICY_REPAIR_COMMIT_COUNT, 14)
        self.assertEqual(
            module.TASK04_POLICY_REPAIR_COMMIT_SUBJECT,
            "fix: recognize TASK-04 architecture commit state",
        )
        self.assertEqual(
            module.TASK04_POLICY_REPAIR_FILES,
            {
                "catalog/assets/core.yaml",
                "scripts/validate_baseline.py",
                "tests/test_baseline.py",
            },
        )

    def test_task05_atom5a_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task05_atom5a(),
            "TASK05_ATOM5A_CANDIDATE_STAGED",
        )

    def test_task05_atom5a_inventory_or_dirty_tree_fails(self) -> None:
        missing = set(module.TASK05_CHANGED_FILES)
        missing.remove("scripts/query_task05.py")
        cases = (
            {"staged": missing},
            {"staged": set(module.TASK05_CHANGED_FILES) | {"unexpected.txt"}},
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"catalog/assets/core.yaml"}},
            {"commit_changed": set(module.TASK04_POLICY_REPAIR_FILES)
                - {"tests/test_baseline.py"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task05_atom5a(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task05_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task05_committed(head_oid=future_oid),
                    "TASK05_ATOM5B_CANDIDATE_COMMITTED",
                )

    def test_task05_future_commit_contract_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK05_BASE_COMMIT_OID,
            "commit_count": module.TASK05_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK05_BASE_PARENT_OID,
            "commit_subject": "feat: arbitrary data contract",
            "commit_changed": set(module.TASK05_CHANGED_FILES)
            - {"scripts/query_task05.py"},
            "staged": set(module.TASK05_CHANGED_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"catalog/assets/core.yaml"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task05_committed(**{key: value}),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task05_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK05_BASE_COMMIT_OID,
            "644bda35429ab74b9488d11e78827234d5d438f3",
        )
        self.assertEqual(
            module.TASK05_BASE_TREE_OID,
            "51e29051d1f3d8f43c074ae30b341d543a8b5e59",
        )
        self.assertEqual(module.TASK05_BASE_COMMIT_COUNT, 14)
        self.assertEqual(module.TASK05_BASE_FILE_COUNT, 96)
        self.assertEqual(len(module.TASK05_MODIFIED_FILES), 11)
        self.assertEqual(len(module.TASK05_CREATED_FILES), 15)
        self.assertEqual(len(module.TASK05_CHANGED_FILES), 26)
        self.assertEqual(module.TASK05_EXPECTED_REPOSITORY_FILE_COUNT, 111)
        self.assertEqual(module.TASK05_COMMIT_COUNT, 15)
        self.assertEqual(
            module.TASK05_COMMIT_SUBJECT,
            "feat: add TASK-05 canonical data contract",
        )
        self.assertIn(".smial-handoff", module.IGNORED_PARTS)

    def test_task05_finalization_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_task05_finalization_staged(),
            "TASK05_FINALIZATION_STAGED",
        )

    def test_task05_finalization_staged_state_is_fail_closed(self) -> None:
        missing = set(module.TASK05_FINALIZATION_FILES)
        missing.remove("docs/tasks/TASK-05.md")
        cases = (
            {"staged": missing},
            {
                "staged":
                set(module.TASK05_FINALIZATION_FILES) | {"unexpected.txt"}
            },
            {"untracked": {"unexpected.txt"}},
            {"unstaged": {"docs/handoffs/latest.md"}},
            {
                "commit_changed":
                set(module.TASK05_CHANGED_FILES)
                - {"scripts/query_task05.py"}
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_task05_finalization_staged(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task05_finalization_future_commit_has_no_self_oid_pin(self) -> None:
        for future_oid in ("1" * 40, "2" * 40):
            with self.subTest(future_oid=future_oid):
                self.assertEqual(
                    self.classify_task05_finalization_committed(
                        head_oid=future_oid
                    ),
                    "TASK05_FINALIZATION_COMMITTED",
                )

    def test_task05_finalization_future_commit_is_fail_closed(self) -> None:
        cases = {
            "head_oid": module.TASK05_FINALIZATION_BASE_COMMIT_OID,
            "commit_count": module.TASK05_FINALIZATION_BASE_COMMIT_COUNT,
            "parent_oid": module.TASK05_FINALIZATION_BASE_PARENT_OID,
            "commit_subject": "docs: arbitrary handoff",
            "commit_changed":
                set(module.TASK05_FINALIZATION_FILES)
                - {"docs/tasks/TASK-05.md"},
            "staged": set(module.TASK05_FINALIZATION_FILES),
            "untracked": {"unexpected.txt"},
            "unstaged": {"docs/handoffs/latest.md"},
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.classify_task05_finalization_committed(
                        **{key: value}
                    ),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_task05_finalization_policy_constants_are_exact(self) -> None:
        self.assertEqual(
            module.TASK05_FINALIZATION_BASE_COMMIT_OID,
            "b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625",
        )
        self.assertEqual(
            module.TASK05_FINALIZATION_BASE_TREE_OID,
            "27d41a8307efdec19faabb82e7be9b5553d3cbdf",
        )
        self.assertEqual(module.TASK05_FINALIZATION_BASE_COMMIT_COUNT, 15)
        self.assertEqual(module.TASK05_FINALIZATION_BASE_FILE_COUNT, 111)
        self.assertEqual(len(module.TASK05_FINALIZATION_MODIFIED_FILES), 12)
        self.assertEqual(len(module.TASK05_FINALIZATION_CREATED_FILES), 1)
        self.assertEqual(len(module.TASK05_FINALIZATION_FILES), 13)
        self.assertEqual(
            module.TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT,
            112,
        )
        self.assertEqual(module.TASK05_FINALIZATION_COMMIT_COUNT, 16)
        self.assertEqual(
            module.TASK05_FINALIZATION_COMMIT_SUBJECT,
            "docs: finalize TASK-05 repository handoff",
        )
        self.assertEqual(
            module.TASK05_FINALIZATION_EXPECTED_CATALOG_VERSION,
            "0.4.1",
        )
        self.assertEqual(
            module.TASK05_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT,
            111,
        )
        self.assertEqual(
            module.TASK05_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT,
            7,
        )

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

    def test_atom7_ci_repair_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_ci_repair(),
            "ATOM7_CI_CLEAN_CLONE_REPAIR_STAGED",
        )

    def test_atom7_ci_repair_exact_committed_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_ci_repair(
                head_oid="f" * 40,
                commit_count=module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT,
                parent_oid=module.ATOM7_PRE_PUSH_REPAIR_COMMIT_OID,
                staged=set(),
                commit_subject=module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT,
                commit_changed=set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES),
            ),
            "ATOM7_CI_CLEAN_CLONE_REPAIR_COMMITTED",
        )

    def test_atom7_ci_repair_wrong_inventory_fails(self) -> None:
        missing = set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES)
        missing.remove("catalog/assets/core.yaml")
        for overrides in (
            {"staged": missing},
            {
                "staged": set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES)
                | {"unexpected.txt"}
            },
            {"unstaged": {"README.md"}},
            {"untracked": {"unexpected.txt"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_ci_repair(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_ci_repair_wrong_commit_contract_fails(self) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_OID,
            "staged": set(),
            "commit_subject": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES),
        }
        for overrides in (
            {"parent_oid": module.ATOM7_LOCAL_CI_COMMIT_OID},
            {"commit_subject": "fix: arbitrary CI repair"},
            {"commit_changed": {"scripts/validate_ci.py"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_ci_repair(**(committed | overrides)),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_final_handoff_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_final_handoff(),
            "ATOM7_FINAL_HANDOFF_STAGED",
        )

    def test_atom7_final_handoff_exact_committed_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_final_handoff(
                head_oid="f" * 40,
                commit_count=module.ATOM7_FINAL_HANDOFF_COMMIT_COUNT,
                parent_oid=module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID,
                staged=set(),
                commit_subject=module.ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT,
                commit_changed=set(module.ATOM7_FINAL_HANDOFF_FILES),
            ),
            "ATOM7_FINAL_HANDOFF_COMMITTED",
        )

    def test_atom7_final_handoff_wrong_inventory_fails(self) -> None:
        missing = set(module.ATOM7_FINAL_HANDOFF_FILES)
        missing.remove("catalog/catalog_manifest.yaml")
        for overrides in (
            {"staged": missing},
            {
                "staged": set(module.ATOM7_FINAL_HANDOFF_FILES)
                | {"unexpected.txt"}
            },
            {"unstaged": {"README.md"}},
            {"untracked": {"unexpected.txt"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_final_handoff(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_final_handoff_wrong_commit_contract_fails(self) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": module.ATOM7_FINAL_HANDOFF_COMMIT_COUNT,
            "parent_oid": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID,
            "staged": set(),
            "commit_subject": module.ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_FINAL_HANDOFF_FILES),
        }
        for overrides in (
            {"parent_oid": module.ATOM7_PRE_PUSH_REPAIR_COMMIT_OID},
            {"commit_subject": "docs: arbitrary final handoff"},
            {"commit_changed": {"docs/handoffs/latest.md"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_final_handoff(**(committed | overrides)),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_ref_repair_exact_staged_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_ref_repair(),
            "ATOM7_REF_NORMALIZATION_REPAIR_STAGED",
        )

    def test_atom7_ref_repair_exact_committed_state_passes(self) -> None:
        self.assertEqual(
            self.classify_atom7_ref_repair(
                head_oid="f" * 40,
                commit_count=module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT,
                parent_oid=module.ATOM7_FINAL_HANDOFF_COMMIT_OID,
                staged=set(),
                commit_subject=module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT,
                commit_changed=set(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES),
            ),
            "ATOM7_REF_NORMALIZATION_REPAIR_COMMITTED",
        )

    def test_atom7_ref_repair_wrong_inventory_fails(self) -> None:
        for overrides in (
            {"staged": {"scripts/validate_baseline.py"}},
            {
                "staged": set(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES)
                | {"unexpected.txt"}
            },
            {"unstaged": {"tests/test_baseline.py"}},
            {"untracked": {"unexpected.txt"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_ref_repair(**overrides),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_ref_repair_wrong_commit_contract_fails(self) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT,
            "parent_oid": module.ATOM7_FINAL_HANDOFF_COMMIT_OID,
            "staged": set(),
            "commit_subject": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT,
            "commit_changed": set(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES),
        }
        for overrides in (
            {"parent_oid": module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID},
            {"commit_subject": "fix: arbitrary remote refs"},
            {"commit_changed": {"tests/test_baseline.py"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_ref_repair(**(committed | overrides)),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_single_branch_refspec_repair_exact_staged_state_passes(
        self,
    ) -> None:
        self.assertEqual(
            self.classify_atom7_single_branch_refspec_repair(),
            "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_STAGED",
        )

    def test_atom7_single_branch_refspec_repair_exact_committed_state_passes(
        self,
    ) -> None:
        self.assertEqual(
            self.classify_atom7_single_branch_refspec_repair(
                head_oid="f" * 40,
                commit_count=(
                    module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_COUNT
                ),
                parent_oid=module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID,
                staged=set(),
                commit_subject=(
                    module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT
                ),
                commit_changed=set(
                    module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
                ),
            ),
            "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMITTED",
        )

    def test_atom7_single_branch_refspec_repair_wrong_inventory_fails(
        self,
    ) -> None:
        for overrides in (
            {"staged": {"scripts/validate_baseline.py"}},
            {
                "staged": set(
                    module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
                )
                | {"unexpected.txt"}
            },
            {"unstaged": {"tests/test_baseline.py"}},
            {"untracked": {"unexpected.txt"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_single_branch_refspec_repair(
                        **overrides
                    ),
                    "INVALID_REPOSITORY_STATE",
                )

    def test_atom7_single_branch_refspec_repair_wrong_commit_contract_fails(
        self,
    ) -> None:
        committed = {
            "head_oid": "f" * 40,
            "commit_count": (
                module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_COUNT
            ),
            "parent_oid": module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID,
            "staged": set(),
            "commit_subject": (
                module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT
            ),
            "commit_changed": set(
                module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
            ),
        }
        for overrides in (
            {"parent_oid": module.ATOM7_FINAL_HANDOFF_COMMIT_OID},
            {"commit_subject": "fix: arbitrary single-branch refspec"},
            {"commit_changed": {"tests/test_baseline.py"}},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_atom7_single_branch_refspec_repair(
                        **(committed | overrides)
                    ),
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
        self.assertEqual(len(module.ATOM7_CI_CLEAN_CLONE_REPAIR_FILES), 7)
        self.assertEqual(len(module.ATOM7_FINAL_HANDOFF_FILES), 11)
        self.assertEqual(len(module.ATOM7_REF_NORMALIZATION_REPAIR_FILES), 2)
        self.assertEqual(
            len(module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES),
            2,
        )
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
        self.assertEqual(
            module.ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT,
            "fix: make CI and clean clone reproducible",
        )
        self.assertEqual(
            module.ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT,
            "docs: reconcile TASK-03 final handoff",
        )
        self.assertEqual(
            module.ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT,
            "fix: normalize remote symbolic refs",
        )
        self.assertEqual(
            module.ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT,
            "fix: support single-branch clean clone refspec",
        )
        self.assertEqual(
            module.EXPECTED_DEFERRED_CAPABILITIES,
            {"GRAPH_DATABASE"},
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


class RemoteRefParserTests(unittest.TestCase):
    def test_exact_symbolic_head_and_main_records_pass(self) -> None:
        output = (
            "refs/remotes/origin/HEAD\trefs/remotes/origin/main\n"
            "refs/remotes/origin/main\t\n"
        )
        refs, target = module.parse_remote_ref_records(output)
        self.assertEqual(refs, {"origin/HEAD", "origin/main"})
        self.assertEqual(target, "refs/remotes/origin/main")

    def test_origin_head_missing_or_incorrect_target_fails(self) -> None:
        for target in ("", "refs/remotes/origin/other"):
            with self.subTest(target=target):
                output = (
                    f"refs/remotes/origin/HEAD\t{target}\n"
                    "refs/remotes/origin/main\t\n"
                )
                with self.assertRaisesRegex(
                    AssertionError,
                    "origin_head_target_invalid",
                ):
                    module.parse_remote_ref_records(output)

    def test_truncated_short_remote_name_fails(self) -> None:
        with self.assertRaisesRegex(
            AssertionError,
            "remote_ref_prefix_invalid",
        ):
            module.parse_remote_ref_records(
                "origin\trefs/remotes/origin/main\n"
            )

    def test_extra_remote_ref_fails(self) -> None:
        output = (
            "refs/remotes/origin/main\t\n"
            "refs/remotes/origin/other\t\n"
        )
        with self.assertRaisesRegex(
            AssertionError,
            "remote_ref_not_allowed:origin/other",
        ):
            module.parse_remote_ref_records(output)


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

    def test_clean_clone_state_passes(self) -> None:
        self.assertEqual(
            self.classify_topology(
                upstream="origin/main",
                remote_tracking_refs={"origin/HEAD", "origin/main"},
                remote_head_target="refs/remotes/origin/main",
                all_refs={
                    "refs/heads/main",
                    "refs/remotes/origin/HEAD",
                    "refs/remotes/origin/main",
                },
            ),
            "CLEAN_CLONE",
        )

    def test_clean_clone_single_branch_refspec_passes(self) -> None:
        self.assertEqual(
            self.classify_topology(
                fetch_refspecs=(
                    module.EXPECTED_SINGLE_BRANCH_FETCH_REFSPEC,
                ),
                upstream="origin/main",
                remote_tracking_refs={"origin/HEAD", "origin/main"},
                remote_head_target="refs/remotes/origin/main",
                all_refs={
                    "refs/heads/main",
                    "refs/remotes/origin/HEAD",
                    "refs/remotes/origin/main",
                },
            ),
            "CLEAN_CLONE",
        )

    def test_single_branch_refspec_fails_outside_clean_clone(self) -> None:
        narrow = (module.EXPECTED_SINGLE_BRANCH_FETCH_REFSPEC,)
        cases = (
            {"fetch_refspecs": narrow},
            {
                "fetch_refspecs": narrow,
                "upstream": "origin/main",
                "remote_tracking_refs": {"origin/main"},
                "all_refs": {
                    "refs/heads/main",
                    "refs/remotes/origin/main",
                },
            },
            {
                "branch": None,
                "fetch_refspecs": narrow,
                "local_branches": set(),
                "remote_tracking_refs": {"origin/main"},
                "all_refs": {"refs/remotes/origin/main"},
                "github_actions": True,
                "github_repository": module.EXPECTED_GITHUB_REPOSITORY,
                "github_ref": "refs/heads/main",
                "github_sha": self.HEAD_OID,
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_topology(**overrides),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_clean_clone_wrong_or_malformed_refspec_fails(self) -> None:
        common = {
            "upstream": "origin/main",
            "remote_tracking_refs": {"origin/HEAD", "origin/main"},
            "remote_head_target": "refs/remotes/origin/main",
            "all_refs": {
                "refs/heads/main",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            },
        }
        refspecs = (
            ("+refs/heads/other:refs/remotes/origin/main",),
            ("+refs/heads/main:refs/remotes/origin/other",),
            ("+refs/heads/main",),
            (
                module.EXPECTED_ORIGIN_FETCH_REFSPEC,
                module.EXPECTED_SINGLE_BRANCH_FETCH_REFSPEC,
            ),
        )
        for fetch_refspecs in refspecs:
            with self.subTest(fetch_refspecs=fetch_refspecs):
                self.assertEqual(
                    self.classify_topology(
                        **common,
                        fetch_refspecs=fetch_refspecs,
                    ),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_clean_clone_extra_remote_ref_branch_or_tag_fails(self) -> None:
        common = {
            "upstream": "origin/main",
            "remote_tracking_refs": {"origin/HEAD", "origin/main"},
            "remote_head_target": "refs/remotes/origin/main",
            "all_refs": {
                "refs/heads/main",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            },
        }
        cases = (
            {"remotes": {"origin", "backup"}},
            {
                "local_branches": {"main", "other"},
                "all_refs": common["all_refs"] | {"refs/heads/other"},
            },
            {
                "remote_tracking_refs": {
                    "origin/HEAD",
                    "origin/main",
                    "origin/other",
                },
                "all_refs": common["all_refs"]
                | {"refs/remotes/origin/other"},
            },
            {
                "tags": {"v1"},
                "all_refs": common["all_refs"] | {"refs/tags/v1"},
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.classify_topology(**(common | overrides)),
                    "INVALID_GIT_TOPOLOGY",
                )

    def test_clean_clone_origin_head_must_be_exact_symbolic_ref(self) -> None:
        common = {
            "upstream": "origin/main",
            "remote_tracking_refs": {"origin/HEAD", "origin/main"},
            "all_refs": {
                "refs/heads/main",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            },
        }
        for target in (None, "", "refs/remotes/origin/other"):
            with self.subTest(target=target):
                self.assertEqual(
                    self.classify_topology(
                        **common,
                        remote_head_target=target,
                    ),
                    "INVALID_GIT_TOPOLOGY",
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
