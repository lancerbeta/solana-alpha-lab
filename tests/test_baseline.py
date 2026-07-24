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
