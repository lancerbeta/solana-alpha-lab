#!/usr/bin/env python3
"""Validate exact historical through Atom 7 pre-push repair states."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import namedtuple
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT_OID = 'ee6119ae0b7750710c7f822c50137ed95b4977e9'
BASE_TREE_OID = '47181f0595e687858a3c3f790ae2f79415aed4a2'
BASE_PARENT_OID = '399ef0365b017fcd9d7b81389218a63bf1e466c1'
BASE_FILE_COUNT = 32
BASE_COMMIT_COUNT = 2
IMPORT_COMMIT_OID = "e03639f4811d7e40f25b965ab79626c229c0fd8a"
IMPORT_COMMIT_COUNT = BASE_COMMIT_COUNT + 1
CURRENT_RECEIPT = ROOT / 'docs/evidence/task03_atom4b_pre_git_import_receipt.json'
EXPECTED_REPOSITORY_FILE_COUNT = 58
EXPECTED_CHANGED_FILES = {'docs/tasks/TASK-03.md', 'tests/test_baseline.py', 'docs/evidence/pre_git/task02/operator_observation_receipt.json', 'scripts/validate_catalog.py', 'catalog/assets/pre_git.yaml', 'docs/evidence/pre_git/task01/validation_report.txt', 'docs/evidence/pre_git/task02/validation_receipt.json', 'docs/evidence/pre_git/task01/sources_v1.yaml', 'docs/evidence/task03_atom4b_pre_git_import_receipt.json', 'docs/evidence/pre_git/task01/provider_cost_snapshot_v1.csv', 'docs/evidence/pre_git/task01/provider_smoke_spec_v1.yaml', 'catalog/assets/core.yaml', 'catalog/query_recipes.yaml', 'docs/evidence/pre_git/task02/bootstrap_check.py', 'docs/evidence/pre_git/task02/env_report.txt', 'docs/architecture/intents/ARCH-INTENT-001-hypothesis-factory-and-regime-aware-orchestration.md', 'tests/test_pre_git_import.py', 'catalog/schemas/asset_catalog.schema.json', 'docs/evidence/pre_git/task01/provider_decision_v1.md', 'docs/evidence/pre_git/task01/hypothesis_data_coverage_matrix_v1.md', 'docs/evidence/pre_git/task01/task_01_completion_record_v1.md', 'scripts/validate.ps1', 'docs/handoffs/latest.md', 'docs/evidence/pre_git/task02/TASK02_COMPLETION_SUMMARY.md', 'docs/evidence/pre_git/task02/tool_versions.json', 'docs/evidence/pre_git/task01/task_01_final_gap_audit_v1.md', 'catalog/catalog_manifest.yaml', 'catalog/assets/architecture.yaml', 'docs/evidence/pre_git/task02/CHECKSUMS_SHA256.txt', 'scripts/validate_baseline.py', 'scripts/validate_pre_git_import.py', 'tests/test_catalog.py', 'README.md', 'catalog/schemas/catalog_manifest.schema.json', 'docs/evidence/pre_git/task01/provider_account_checklist_v1.md', 'docs/evidence/pre_git/task01/reuse_candidate_registry.yaml', 'docs/evidence/pre_git/task01/CHECKSUMS_SHA256.txt', 'AGENTS.md', 'docs/evidence/pre_git/task01/data_option_tiers_v1.yaml', 'docs/evidence/pre_git/task02/task_02_workstation_bootstrap.md'}
WORK_ACCEPTANCE_SYNC_FILES = {
    "catalog/assets/core.yaml",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
}
WORK_ACCEPTANCE_COMMIT_COUNT = IMPORT_COMMIT_COUNT + 1
WORK_ACCEPTANCE_COMMIT_SUBJECT = "fix: validate Work acceptance checkpoint"
WORK_ACCEPTANCE_COMMIT_OID = "85ab008b762edacd335bba3d9776100bc52775ce"
ATOM5_COMMIT_COUNT = WORK_ACCEPTANCE_COMMIT_COUNT + 1
ATOM5_COMMIT_SUBJECT = "feat: add registry skeletons and generated navigation"
ATOM5_COMMIT_OID = "cd1465ea5de1fb33cee272422863b05d9459bd83"
ATOM5_MODIFIED_FILES = {
    "AGENTS.md",
    "catalog/catalog_manifest.yaml",
    "catalog/assets/core.yaml",
    "catalog/schemas/catalog_manifest.schema.json",
    "catalog/schemas/asset_catalog.schema.json",
    "scripts/validate_catalog.py",
    "scripts/validate.ps1",
    "scripts/validate_baseline.py",
    "tests/test_catalog.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
}
ATOM5_CREATED_FILES = {
    "catalog/assets/lifecycle.yaml",
    "catalog/schemas/lifecycle_registry.schema.json",
    "scripts/generate_navigation.py",
    "tests/test_lifecycle_registries.py",
    "tests/test_generate_navigation.py",
    "registries/research_cycles.yaml",
    "registries/hypotheses.yaml",
    "registries/global_trial_ledger.yaml",
    "registries/feature_catalog.yaml",
    "registries/holdout_consumption.yaml",
    "registries/strategies.yaml",
    "registries/bot_instances.yaml",
    "registries/reuse_candidates.yaml",
    "registries/decisions_negative_results.yaml",
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
}
ATOM5_CHANGED_FILES = ATOM5_MODIFIED_FILES | ATOM5_CREATED_FILES
ATOM5_EXPECTED_REPOSITORY_FILE_COUNT = (
    EXPECTED_REPOSITORY_FILE_COUNT + len(ATOM5_CREATED_FILES)
)
ATOM5_WORK_ACCEPTANCE_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
    "catalog/assets/core.yaml",
}
ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT = ATOM5_COMMIT_COUNT + 1
ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT = (
    "fix: validate Atom 5 Work acceptance"
)
ATOM5_WORK_ACCEPTANCE_COMMIT_OID = "9c021299b83804f5cb744c1d9dc9a8124de43f59"
ATOM7_LOCAL_CI_COMMIT_COUNT = ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT + 1
ATOM7_LOCAL_CI_COMMIT_SUBJECT = "ci: add pinned repository validation"
ATOM7_LOCAL_CI_COMMIT_OID = "4320b621f56bf86c8561be4a379dfc1d0e8937b2"
ATOM7_LOCAL_CI_MODIFIED_FILES = {
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "catalog/catalog_manifest.yaml",
    "catalog/query_recipes.yaml",
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "scripts/validate.ps1",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "docs/tasks/TASK-03.md",
    "docs/handoffs/latest.md",
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
}
ATOM7_LOCAL_CI_CREATED_FILES = {
    ".github/workflows/ci.yml",
    "scripts/validate_ci.py",
    "tests/test_ci.py",
}
ATOM7_LOCAL_CI_FILES = (
    ATOM7_LOCAL_CI_MODIFIED_FILES | ATOM7_LOCAL_CI_CREATED_FILES
)
ATOM7_EXPECTED_REPOSITORY_FILE_COUNT = (
    ATOM5_EXPECTED_REPOSITORY_FILE_COUNT + len(ATOM7_LOCAL_CI_CREATED_FILES)
)
ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT = ATOM7_LOCAL_CI_COMMIT_COUNT + 1
ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT = (
    "fix: validate repository publication states"
)
ATOM7_PRE_PUSH_REPAIR_COMMIT_OID = "a29c7ac2b90c948519d53fd2d6d4c879381dc861"
ATOM7_PRE_PUSH_REPAIR_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
}
ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT = (
    ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT + 1
)
ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT = (
    "fix: make CI and clean clone reproducible"
)
ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID = (
    "21cfe7fb5c0d410bd9c86976ee3c815dca249399"
)
ATOM7_CI_CLEAN_CLONE_REPAIR_FILES = {
    ".github/workflows/ci.yml",
    "README.md",
    "catalog/assets/core.yaml",
    "scripts/validate_baseline.py",
    "scripts/validate_ci.py",
    "tests/test_baseline.py",
    "tests/test_ci.py",
}
ATOM7_FINAL_HANDOFF_COMMIT_COUNT = (
    ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT + 1
)
ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT = (
    "docs: reconcile TASK-03 final handoff"
)
ATOM7_FINAL_HANDOFF_COMMIT_OID = (
    "767d7a8c3eaa108d0b77db69a7182a9bda1f3fe0"
)
ATOM7_FINAL_HANDOFF_FILES = {
    "AGENTS.md",
    "README.md",
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "docs/PROJECT_MAP.md",
    "docs/handoffs/latest.md",
    "docs/tasks/TASK-03.md",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
}
ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT = (
    ATOM7_FINAL_HANDOFF_COMMIT_COUNT + 1
)
ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT = (
    "fix: normalize remote symbolic refs"
)
ATOM7_REF_NORMALIZATION_REPAIR_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
}
ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID = (
    "9c284a25f6f6ce42fa2617f410fbbc9806f84ffd"
)
ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_COUNT = (
    ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT + 1
)
ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT = (
    "fix: support single-branch clean clone refspec"
)
ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES = {
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
}
TASK04_BASE_COMMIT_OID = "f8ff483dbcf00454852a9638466eb4123e2c5809"
TASK04_BASE_TREE_OID = "cfbf181fa2c005cf517a218c70ede51c701b5a43"
TASK04_BASE_PARENT_OID = ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID
TASK04_BASE_COMMIT_COUNT = ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_COUNT
TASK04_BASE_FILE_COUNT = 77
TASK04_MODIFIED_FILES = {
    "AGENTS.md",
    "README.md",
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "catalog/generated/asset_edges.json",
    "catalog/schemas/lifecycle_registry.schema.json",
    "docs/PROJECT_MAP.md",
    "docs/handoffs/latest.md",
    "pyproject.toml",
    "registries/reuse_candidates.yaml",
    "scripts/validate_baseline.py",
    "scripts/validate_catalog.py",
    "scripts/validate_ci.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "tests/test_ci.py",
    "tests/test_lifecycle_registries.py",
    "uv.lock",
}
TASK04_CREATED_FILES = {
    "docs/agent/HANDOFF_PROTOCOL.md",
    "docs/decisions/ADR-002-mvp-stack.md",
    "docs/decisions/TASK04_component_candidate_matrix_v1.json",
    "docs/evidence/task04/EVIDENCE_MANIFEST.json",
    "docs/evidence/task04/TASK04_A5A_CANDIDATE_RECEIPT.json",
    "docs/evidence/task04/a4r/CLEANUP_RECEIPT.json",
    "docs/evidence/task04/a4r/PACKAGE_GRAPH.json",
    "docs/evidence/task04/a4r/PIT_REPLAY_RECEIPT.json",
    "docs/evidence/task04/a4r/SBOM.cdx.json",
    "docs/evidence/task04/a4r/SUPPLY_CHAIN_RECEIPT.json",
    "docs/evidence/task04/a4r/TASK04_A4R_VALIDATION_RECEIPT.json",
    "docs/evidence/task04/a4r/TASK04_A4R_WORK_ACCEPTANCE.md",
    "docs/evidence/task04/a4r/TASK04_A4R_WORK_ACCEPTANCE_RECEIPT.json",
    "docs/evidence/task04/a5a/SBOM.cdx.json",
    "docs/evidence/task04/research/TASK04_RESEARCH_ACCEPTANCE.json",
    "docs/tasks/TASK-04.md",
    "scripts/validate_task04.py",
    "tests/fixtures/task04/pit_fixture_v1.json",
    "tests/test_task04_core_stack.py",
}
TASK04_CHANGED_FILES = TASK04_MODIFIED_FILES | TASK04_CREATED_FILES
TASK04_EXPECTED_REPOSITORY_FILE_COUNT = TASK04_BASE_FILE_COUNT + len(TASK04_CREATED_FILES)
TASK04_ARCHITECTURE_COMMIT_OID = "b2bae357bb5ec84c6b28ceeeb44fb2d6176dbae3"
TASK04_ARCHITECTURE_TREE_OID = "388fa66d0890e1b38122151b808f63a9b463c1b5"
TASK04_ARCHITECTURE_COMMIT_COUNT = TASK04_BASE_COMMIT_COUNT + 1
TASK04_ARCHITECTURE_COMMIT_SUBJECT = (
    "feat: record TASK-04 architecture and reuse decisions"
)
TASK04_POLICY_REPAIR_COMMIT_COUNT = TASK04_ARCHITECTURE_COMMIT_COUNT + 1
TASK04_POLICY_REPAIR_COMMIT_SUBJECT = (
    "fix: recognize TASK-04 architecture commit state"
)
TASK04_POLICY_REPAIR_FILES = {
    "catalog/assets/core.yaml",
    "scripts/validate_baseline.py",
    "tests/test_baseline.py",
}
TASK04_REPOSITORY_STATES = {
    "TASK04_ATOM5A_CANDIDATE_STAGED",
    "TASK04_ATOM5B_ARCHITECTURE_COMMITTED",
    "TASK04_ATOM5B_POLICY_REPAIR_STAGED",
    "TASK04_ATOM5B_POLICY_REPAIR_COMMITTED",
}
TASK04_COMMITTED_STATES = {
    "TASK04_ATOM5B_ARCHITECTURE_COMMITTED",
    "TASK04_ATOM5B_POLICY_REPAIR_COMMITTED",
}
TASK04_EXPECTED_CATALOG_VERSION = "0.3.0"
TASK04_EXPECTED_CATALOG_ASSET_COUNT = 82
TASK04_EXPECTED_RUNTIME_DEPENDENCIES = {
    "PyYAML==6.0.3",
    "jsonschema==4.26.0",
    "duckdb==1.5.5",
    "pyarrow==25.0.0",
    "pydantic==2.13.4",
    "solana==0.40.1",
    "solders==0.28.0",
    "prometheus-client==0.25.0",
}
TASK04_EXPECTED_RUNTIME_VERSIONS = {
    "duckdb": "1.5.5",
    "pyarrow": "25.0.0",
    "pydantic": "2.13.4",
    "pydantic-core": "2.46.4",
    "solana": "0.40.1",
    "solders": "0.28.0",
    "prometheus-client": "0.25.0",
}
TASK05_BASE_COMMIT_OID = "644bda35429ab74b9488d11e78827234d5d438f3"
TASK05_BASE_TREE_OID = "51e29051d1f3d8f43c074ae30b341d543a8b5e59"
TASK05_BASE_PARENT_OID = TASK04_ARCHITECTURE_COMMIT_OID
TASK05_BASE_COMMIT_COUNT = TASK04_POLICY_REPAIR_COMMIT_COUNT
TASK05_BASE_FILE_COUNT = TASK04_EXPECTED_REPOSITORY_FILE_COUNT
TASK05_MODIFIED_FILES = {
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "catalog/generated/asset_edges.json",
    "catalog/query_recipes.yaml",
    "docs/PROJECT_MAP.md",
    "scripts/validate_baseline.py",
    "scripts/validate_task04.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "tests/test_task04_core_stack.py",
}
TASK05_CREATED_FILES = {
    "docs/contracts/data_contract_v1.md",
    "migrations/0001_canonical_schema_v1.sql",
    "migrations/ledger_v1.json",
    "schemas/schema_v1.sql",
    "scripts/query_task05.py",
    "src/solana_alpha_lab/__init__.py",
    "src/solana_alpha_lab/contracts/__init__.py",
    "src/solana_alpha_lab/contracts/migration_ledger.py",
    "src/solana_alpha_lab/contracts/schema_v1.py",
    "tests/fixtures/task05/schema_contract_fixture_v1.json",
    "tests/fixtures/task05/schema_model_roundtrip_fixture_v1.json",
    "tests/test_task05_catalog_queries.py",
    "tests/test_task05_migrations.py",
    "tests/test_task05_models.py",
    "tests/test_task05_schema_contract.py",
}
TASK05_CHANGED_FILES = TASK05_MODIFIED_FILES | TASK05_CREATED_FILES
TASK05_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK05_BASE_FILE_COUNT + len(TASK05_CREATED_FILES)
)
TASK05_COMMIT_COUNT = TASK05_BASE_COMMIT_COUNT + 1
TASK05_COMMIT_SUBJECT = "feat: add TASK-05 canonical data contract"
TASK05_REPOSITORY_STATES = {
    "TASK05_ATOM5A_CANDIDATE_STAGED",
    "TASK05_ATOM5B_CANDIDATE_COMMITTED",
}
TASK05_FINALIZATION_BASE_COMMIT_OID = (
    "b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625"
)
TASK05_FINALIZATION_BASE_TREE_OID = (
    "27d41a8307efdec19faabb82e7be9b5553d3cbdf"
)
TASK05_FINALIZATION_BASE_PARENT_OID = TASK05_BASE_COMMIT_OID
TASK05_FINALIZATION_BASE_COMMIT_COUNT = TASK05_COMMIT_COUNT
TASK05_FINALIZATION_BASE_FILE_COUNT = TASK05_EXPECTED_REPOSITORY_FILE_COUNT
TASK05_FINALIZATION_MODIFIED_FILES = {
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "catalog/generated/asset_edges.json",
    "docs/PROJECT_MAP.md",
    "docs/handoffs/latest.md",
    "scripts/validate_baseline.py",
    "scripts/validate_task04.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "tests/test_task04_core_stack.py",
    "tests/test_task05_catalog_queries.py",
}
TASK05_FINALIZATION_CREATED_FILES = {"docs/tasks/TASK-05.md"}
TASK05_FINALIZATION_FILES = (
    TASK05_FINALIZATION_MODIFIED_FILES | TASK05_FINALIZATION_CREATED_FILES
)
TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK05_FINALIZATION_BASE_FILE_COUNT + len(TASK05_FINALIZATION_CREATED_FILES)
)
TASK05_FINALIZATION_COMMIT_COUNT = TASK05_FINALIZATION_BASE_COMMIT_COUNT + 1
TASK05_FINALIZATION_COMMIT_SUBJECT = (
    "docs: finalize TASK-05 repository handoff"
)
TASK05_FINALIZATION_REPOSITORY_STATES = {
    "TASK05_FINALIZATION_STAGED",
    "TASK05_FINALIZATION_COMMITTED",
}
TASK05_REPOSITORY_STATES |= TASK05_FINALIZATION_REPOSITORY_STATES
TASK05_COMMITTED_STATES = {
    "TASK05_ATOM5B_CANDIDATE_COMMITTED",
    "TASK05_FINALIZATION_COMMITTED",
}
TASK05_EXPECTED_CATALOG_VERSION = "0.4.0"
TASK05_EXPECTED_CATALOG_ASSET_COUNT = 110
TASK05_EXPECTED_CATALOG_QUERY_COUNT = 7
TASK05_FINALIZATION_EXPECTED_CATALOG_VERSION = "0.4.1"
TASK05_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT = 111
TASK05_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT = 7
TASK06_BASE_COMMIT_OID = "1db62c7abc06bcb4ab209b3db7f4eb858f64330a"
TASK06_BASE_TREE_OID = "6ec5e7a10b7c547b02c37436a1f37d0729a6f657"
TASK06_BASE_PARENT_OID = TASK05_FINALIZATION_BASE_COMMIT_OID
TASK06_BASE_COMMIT_COUNT = TASK05_FINALIZATION_COMMIT_COUNT
TASK06_BASE_FILE_COUNT = TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
TASK06_MODIFIED_FILES = {
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
}
TASK06_CREATED_FILES = {
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
}
TASK06_CHANGED_FILES = TASK06_MODIFIED_FILES | TASK06_CREATED_FILES
TASK06_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK06_BASE_FILE_COUNT + len(TASK06_CREATED_FILES)
)
TASK06_COMMIT_COUNT = TASK06_BASE_COMMIT_COUNT + 1
TASK06_COMMIT_SUBJECT = "feat: add TASK-06 raw storage boundary"
TASK06_REPOSITORY_STATES = {
    "TASK06_ATOM7A_CANDIDATE_STAGED",
    "TASK06_ATOM7B_CANDIDATE_COMMITTED",
}
TASK06_FINALIZATION_BASE_COMMIT_OID = (
    "23ead28bfb9fe9c60fd143b7e69267b61bc8512c"
)
TASK06_FINALIZATION_BASE_TREE_OID = (
    "dead22b1d8bae02fead79d3aa7ef27c13f6c840a"
)
TASK06_FINALIZATION_BASE_PARENT_OID = TASK06_BASE_COMMIT_OID
TASK06_FINALIZATION_BASE_COMMIT_COUNT = TASK06_COMMIT_COUNT
TASK06_FINALIZATION_BASE_FILE_COUNT = TASK06_EXPECTED_REPOSITORY_FILE_COUNT
TASK06_FINALIZATION_MODIFIED_FILES = {
    "catalog/assets/core.yaml",
    "catalog/assets/lifecycle.yaml",
    "catalog/catalog_manifest.yaml",
    "catalog/generated/asset_edges.json",
    "docs/PROJECT_MAP.md",
    "docs/handoffs/latest.md",
    "docs/tasks/TASK-06.md",
    "scripts/validate_baseline.py",
    "scripts/validate_task04.py",
    "tests/test_baseline.py",
    "tests/test_catalog.py",
    "tests/test_task04_core_stack.py",
    "tests/test_task05_catalog_queries.py",
    "tests/test_task06_catalog.py",
}
TASK06_FINALIZATION_CREATED_FILES: set[str] = set()
TASK06_FINALIZATION_FILES = (
    TASK06_FINALIZATION_MODIFIED_FILES | TASK06_FINALIZATION_CREATED_FILES
)
TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK06_FINALIZATION_BASE_FILE_COUNT + len(TASK06_FINALIZATION_CREATED_FILES)
)
TASK06_FINALIZATION_COMMIT_COUNT = TASK06_FINALIZATION_BASE_COMMIT_COUNT + 1
TASK06_FINALIZATION_COMMIT_SUBJECT = (
    "docs: finalize TASK-06 repository handoff"
)
TASK06_FINALIZATION_REPOSITORY_STATES = {
    "TASK06_FINALIZATION_STAGED",
    "TASK06_FINALIZATION_COMMITTED",
}
TASK06_REPOSITORY_STATES |= TASK06_FINALIZATION_REPOSITORY_STATES
TASK06_COMMITTED_STATES = {
    "TASK06_ATOM7B_CANDIDATE_COMMITTED",
    "TASK06_FINALIZATION_COMMITTED",
}
TASK06_EXPECTED_CATALOG_VERSION = "0.5.0"
TASK06_EXPECTED_CATALOG_ASSET_COUNT = 128
TASK06_EXPECTED_CATALOG_QUERY_COUNT = 7
TASK06_FINALIZATION_EXPECTED_CATALOG_VERSION = "0.5.1"
TASK06_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT = 128
TASK06_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT = 7
TASK07_BASE_COMMIT_OID = "8c52f16774306f88b332c7641bc5a14c6fda0786"
TASK07_BASE_TREE_OID = "a17836456013f841a49ede261615e390cd41850f"
TASK07_BASE_PARENT_OID = TASK06_FINALIZATION_BASE_COMMIT_OID
TASK07_BASE_COMMIT_COUNT = TASK06_FINALIZATION_COMMIT_COUNT
TASK07_BASE_FILE_COUNT = TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
TASK07_MODIFIED_FILES = {
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
}
TASK07_CREATED_FILES = {
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
}
TASK07_CHANGED_FILES = TASK07_MODIFIED_FILES | TASK07_CREATED_FILES
TASK07_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK07_BASE_FILE_COUNT + len(TASK07_CREATED_FILES)
)
TASK07_COMMIT_COUNT = TASK07_BASE_COMMIT_COUNT + 1
TASK07_COMMIT_SUBJECT = "feat: add TASK-07 bounded provider smoke"
TASK07_REPOSITORY_STATES = {
    "TASK07_ATOM6A_CANDIDATE_STAGED",
    "TASK07_ATOM6B_CANDIDATE_COMMITTED",
}
TASK07_COMMITTED_STATES = {"TASK07_ATOM6B_CANDIDATE_COMMITTED"}
TASK07_EXPECTED_CATALOG_VERSION = "0.6.0"
TASK07_EXPECTED_CATALOG_ASSET_COUNT = 141
TASK07_EXPECTED_CATALOG_QUERY_COUNT = 7
TASK08_BASE_COMMIT_OID = "03731b647ca4d47283a2dcb4154622865b606327"
TASK08_BASE_TREE_OID = "0462d283a5b0a6a1c0a6eab63b2e7e8463757522"
TASK08_BASE_PARENT_OID = TASK07_BASE_COMMIT_OID
TASK08_BASE_COMMIT_COUNT = TASK07_COMMIT_COUNT
TASK08_BASE_FILE_COUNT = TASK07_EXPECTED_REPOSITORY_FILE_COUNT
TASK08_MODIFIED_FILES = {
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
}
TASK08_CREATED_FILES = {
    "docs/contracts/lifecycle_discovery_contract_v1.md",
    "docs/contracts/lifecycle_discovery_probe_transport_contract_v1.md",
    "docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json",
    "docs/evidence/task08/lifecycle_discovery_probe_execution_summary_v1.md",
    "scripts/run_task08_lifecycle_discovery_probe.py",
    "src/solana_alpha_lab/lifecycle_discovery.py",
    "src/solana_alpha_lab/lifecycle_discovery_transport.py",
    "src/solana_alpha_lab/pump_event_decoder.py",
    "tests/fixtures/task08/lifecycle_discovery_contract_v1.json",
    "tests/fixtures/task08/lifecycle_discovery_probe_live_evidence_v1.json",
    "tests/fixtures/task08/pump_event_idl_subset_v1.json",
    "tests/test_task08_catalog.py",
    "tests/test_task08_lifecycle_discovery.py",
    "tests/test_task08_lifecycle_discovery_probe_evidence.py",
    "tests/test_task08_lifecycle_discovery_transport.py",
    "tests/test_task08_pump_event_decoder.py",
}
TASK08_CHANGED_FILES = TASK08_MODIFIED_FILES | TASK08_CREATED_FILES
TASK08_EXPECTED_REPOSITORY_FILE_COUNT = (
    TASK08_BASE_FILE_COUNT + len(TASK08_CREATED_FILES)
)
TASK08_COMMIT_COUNT = TASK08_BASE_COMMIT_COUNT + 1
TASK08_COMMIT_SUBJECT = "feat: add TASK-08 lifecycle discovery probe"
TASK08_REPOSITORY_STATES = {
    "TASK08_ATOM8A_CANDIDATE_STAGED",
    "TASK08_ATOM8B_CANDIDATE_COMMITTED",
}
TASK08_COMMITTED_STATES = {"TASK08_ATOM8B_CANDIDATE_COMMITTED"}
TASK08_EXPECTED_CATALOG_VERSION = "0.7.0"
TASK08_EXPECTED_CATALOG_ASSET_COUNT = 158
TASK08_EXPECTED_CATALOG_QUERY_COUNT = 7
CTRL_BATON_A62_COMMIT_OID = "bd152b3199a9ba5c75374bd798b1e81756cd4d9b"
CTRL_BATON_A62_TREE_OID = "a068018e57ad53340ad94321539ed7d1b411bc10"
CTRL_BATON_A62_FEATURE_OID = "64e184b6a661d379a62179895df422e0700ee79e"
CTRL_BATON_A62_FEATURE_TREE_OID = "59516a7fe01941bf04ed40b3e1d375039b994795"
CTRL_BATON_A612_FEATURE_OID = "0c43dda4209cfeb281d33ac8ed50b07c809a1068"
CTRL_BATON_A612_FEATURE_TREE_OID = "906701eb4d3555a6721ccd721b2b5083152ef3c9"
CTRL_BATON_A617_FEATURE_OID = "57ea966c1afe00d16836f2067e8a2c985289116b"
CTRL_BATON_A617_FEATURE_TREE_OID = "12eb2852fd7b733572464a085fa0cd5091b4ab22"
CTRL_BATON_A62_COMMIT_SUBJECT = "feat(control): add GPT-Cursor GitHub baton"
CTRL_BATON_A69_EXPECTED_CATALOG_VERSION = "0.8.2"
CTRL_BATON_A613_EXPECTED_CATALOG_VERSION = "0.8.3"
CTRL_BATON_A62_EXPECTED_CATALOG_VERSION = "0.8.4"
CTRL_BATON_FEATURE_BRANCH = "ctrl/baton-setup"
CTRL_BATON_FEATURE_UPSTREAM = "origin/ctrl/baton-setup"
CTRL_BATON_EXPECTED_INDEX_PATH_COUNT = 225
# Asset/query counts for dirty candidate are computed from parsed registries;
# these constants are only used as consistency anchors for known checkpoints.
CTRL_BATON_A62_REPOSITORY_STATES = {
    "CTRL_BATON_A62R_CANDIDATE_DIRTY",
    "CTRL_BATON_A62R_CANDIDATE_STAGED",
    "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
    "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
    "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
    "CTRL_BATON_A62_FEATURE_COMMITTED",
    "CTRL_BATON_A62_PR_MERGE_CHECKOUT",
    "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
}
CTRL_BATON_A62_LIFECYCLE_COMBINATIONS = {
    ("CTRL_BATON_A62R_CANDIDATE_DIRTY", "PUBLISHED_LOCAL"),
    ("CTRL_BATON_A62R_CANDIDATE_STAGED", "BATON_FEATURE_LOCAL"),
    (
        "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
        "BATON_FEATURE_PUBLISHED_REPAIR_STAGED",
    ),
    (
        "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
        "BATON_FEATURE_PUBLISHED_RECONCILIATION_STAGED",
    ),
    (
        "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
        "BATON_FEATURE_PUBLISHED_LOCAL_MAIN_REPAIR_STAGED",
    ),
    ("CTRL_BATON_A62_FEATURE_COMMITTED", "BATON_FEATURE_LOCAL"),
    ("CTRL_BATON_A62_FEATURE_COMMITTED", "BATON_FEATURE_AHEAD_OF_PUBLISHED"),
    ("CTRL_BATON_A62_FEATURE_COMMITTED", "BATON_FEATURE_PUBLISHED"),
    ("CTRL_BATON_A62_PR_MERGE_CHECKOUT", "GITHUB_PR_MERGE_CHECKOUT"),
    ("CTRL_BATON_A62_MAIN_MERGE_COMMITTED", "GITHUB_MAIN_PUSH_CHECKOUT"),
    ("CTRL_BATON_A62_MAIN_MERGE_COMMITTED", "BATON_MAIN_LOCAL_POST_MERGE"),
}
CTRL_BATON_A62R_REQUIRED_TRACKED_FILES = frozenset(
    {
        "docs/agent/GITHUB_BATON_PROTOCOL.md",
        "docs/contracts/atom_contract.schema.json",
        "scripts/validate_baton.py",
        "scripts/baton_contract.py",
        "scripts/baton_scope.py",
        "scripts/baton_receipt.py",
        "scripts/baton_preflight.py",
        "tests/fixtures/baton/fixture_manifest.json",
        "tests/fixtures/baton/valid_atom_contract.json",
        ".cursor/rules/00-authority.mdc",
        ".cursorignore",
    }
)
CTRL_BATON_A62R_EXPECTED_MODIFIED = frozenset(
    {
        ".github/workflows/ci.yml",
        "AGENTS.md",
        "catalog/assets/core.yaml",
        "catalog/assets/lifecycle.yaml",
        "catalog/catalog_manifest.yaml",
        "catalog/generated/asset_edges.json",
        "docs/PROJECT_MAP.md",
        "scripts/validate_baseline.py",
        "scripts/validate_ci.py",
        "scripts/validate_task04.py",
        "tests/test_catalog.py",
        "tests/test_ci.py",
        "tests/test_task04_core_stack.py",
        "tests/test_task05_catalog_queries.py",
        "tests/test_task06_catalog.py",
        "tests/test_task07_catalog.py",
        "tests/test_task08_catalog.py",
    }
)
CTRL_BATON_A62R_EXPECTED_UNTRACKED = frozenset(
    {
        ".cursor/commands/baton-preflight.md",
        ".cursor/rules/00-authority.mdc",
        ".cursor/rules/05-language-and-reporting.mdc",
        ".cursor/rules/10-input-routing.mdc",
        ".cursor/rules/20-validation.mdc",
        ".cursor/rules/30-security-and-secrets.mdc",
        ".cursor/rules/40-catalog-and-evidence.mdc",
        ".cursor/rules/50-github-baton.mdc",
        ".cursorignore",
        ".github/ISSUE_TEMPLATE/control-atom.yml",
        ".github/pull_request_template.md",
        "docs/agent/EXECUTION_ROUTER_PROTOCOL.md",
        "docs/agent/GITHUB_BATON_PROTOCOL.md",
        "docs/contracts/acceptance_receipt.schema.json",
        "docs/contracts/atom_contract.schema.json",
        "docs/contracts/execution_receipt.schema.json",
        "docs/decisions/ADR-003-gpt-executor-routing.md",
        "docs/evidence/baton/a62_machine_layer_local_validation.json",
        "docs/tasks/CTRL-BATON-SETUP.md",
        "scripts/baton_contract.py",
        "scripts/baton_preflight.py",
        "scripts/baton_receipt.py",
        "scripts/baton_scope.py",
        "scripts/validate_baton.py",
        "tests/fixtures/baton/expected_contract_sha256.txt",
        "tests/fixtures/baton/fixture_manifest.json",
        "tests/fixtures/baton/invalid/absolute_posix_path.json",
        "tests/fixtures/baton/invalid/absolute_windows_path.json",
        "tests/fixtures/baton/invalid/acceptance_canonical_status_change.json",
        "tests/fixtures/baton/invalid/acceptance_merge_authorized.json",
        "tests/fixtures/baton/invalid/base_head_mismatch_contract.json",
        "tests/fixtures/baton/invalid/base_tree_mismatch_contract.json",
        "tests/fixtures/baton/invalid/contract_revision_mismatch.json",
        "tests/fixtures/baton/invalid/duplicate_markers.md",
        "tests/fixtures/baton/invalid/file_outside_managed_write_set.json",
        "tests/fixtures/baton/invalid/forbidden_wallet_target.json",
        "tests/fixtures/baton/invalid/git_target.json",
        "tests/fixtures/baton/invalid/invalid_authority.json",
        "tests/fixtures/baton/invalid/invalid_json.md",
        "tests/fixtures/baton/invalid/issue_body_whitespace_and_embedded_hash.md",
        "tests/fixtures/baton/invalid/local_write_empty_write_set.json",
        "tests/fixtures/baton/invalid/missing_marker.md",
        "tests/fixtures/baton/invalid/parent_traversal.json",
        "tests/fixtures/baton/invalid/read_only_nonempty_write_set.json",
        "tests/fixtures/baton/invalid/receipt_github_write.json",
        "tests/fixtures/baton/invalid/receipt_secrets_true.json",
        "tests/fixtures/baton/invalid/unsafe_glob.json",
        "tests/fixtures/baton/invalid/whitespace_changed_contract.json",
        "tests/fixtures/baton/invalid/wrong_repository.json",
        "tests/fixtures/baton/valid_acceptance_receipt.json",
        "tests/fixtures/baton/valid_atom_contract.json",
        "tests/fixtures/baton/valid_execution_receipt.json",
        "tests/fixtures/baton/valid_issue_body.md",
        "tests/test_baton_contract.py",
        "tests/test_baton_cursorignore.py",
        "tests/test_baton_preflight.py",
        "tests/test_baton_receipts.py",
        "tests/test_baton_scope.py",
        "tests/test_baton_repository_policy.py",
        "tests/fixtures/baton/invalid/receipt_pass_full_not_run.json",
        "tests/fixtures/baton/invalid/receipt_pass_targeted_skipped.json",
        "tests/fixtures/baton/invalid/receipt_embedded_windows_path.json",
        "tests/fixtures/baton/invalid/receipt_embedded_posix_home.json",
        "tests/fixtures/baton/invalid/receipt_password_assignment.json",
        "tests/fixtures/baton/invalid/receipt_token_assignment.json",
        "tests/fixtures/baton/invalid/receipt_no_change_with_files.json",
        "tests/fixtures/baton/invalid/issue_body_crlf.md",
    }
)
CTRL_BATON_A69_REPAIR_PATHS = frozenset(
    {
        "catalog/assets/core.yaml",
        "catalog/catalog_manifest.yaml",
        "docs/evidence/baton/a62_machine_layer_local_validation.json",
        "docs/tasks/CTRL-BATON-SETUP.md",
        "scripts/validate_baseline.py",
        "scripts/validate_baton.py",
        "scripts/validate_task04.py",
        "tests/fixtures/baton/fixture_manifest.json",
        "tests/test_baton_preflight.py",
        "tests/test_baton_repository_policy.py",
        "tests/test_task04_core_stack.py",
        "tests/test_task05_catalog_queries.py",
        "tests/test_task06_catalog.py",
        "tests/test_task07_catalog.py",
        "tests/test_task08_catalog.py",
    }
)
CTRL_BATON_A613_RECONCILIATION_PATHS = frozenset(
    {
        "catalog/assets/core.yaml",
        "catalog/catalog_manifest.yaml",
        "docs/evidence/baton/a62_machine_layer_local_validation.json",
        "docs/tasks/CTRL-BATON-SETUP.md",
        "scripts/validate_baseline.py",
        "scripts/validate_task04.py",
        "tests/test_baton_repository_policy.py",
        "tests/test_task04_core_stack.py",
        "tests/test_task05_catalog_queries.py",
        "tests/test_task06_catalog.py",
        "tests/test_task07_catalog.py",
        "tests/test_task08_catalog.py",
    }
)
CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS = (
    CTRL_BATON_A613_RECONCILIATION_PATHS
)


def ctrl_baton_a62r_expected_committed_changed() -> frozenset[str]:
    """Exact commit_changed set = modified ∪ previously-untracked."""
    return frozenset(
        CTRL_BATON_A62R_EXPECTED_MODIFIED | CTRL_BATON_A62R_EXPECTED_UNTRACKED
    )


def ctrl_baton_a62r_expected_committed_tracked() -> set[str]:
    """Exact tracked set after clean commit = TASK-08 ∪ previously-untracked."""
    return task08_repository_files() | set(CTRL_BATON_A62R_EXPECTED_UNTRACKED)


def ctrl_baton_a62r_expected_repository_file_count() -> int:
    """Dirty and committed candidates both count TASK-08 + candidate files."""
    return TASK08_EXPECTED_REPOSITORY_FILE_COUNT + len(
        CTRL_BATON_A62R_EXPECTED_UNTRACKED
    )


EXPECTED_DEFERRED_CAPABILITIES = {"GRAPH_DATABASE"}
EXPECTED_ORIGIN_URL = "https://github.com/lancerbeta/solana-alpha-lab.git"
EXPECTED_CI_ORIGIN_URLS = {
    EXPECTED_ORIGIN_URL,
    "https://github.com/lancerbeta/solana-alpha-lab",
}
EXPECTED_GITHUB_REPOSITORY = "lancerbeta/solana-alpha-lab"
EXPECTED_ORIGIN_FETCH_REFSPEC = "+refs/heads/*:refs/remotes/origin/*"
EXPECTED_SINGLE_BRANCH_FETCH_REFSPEC = (
    "+refs/heads/main:refs/remotes/origin/main"
)
REMOTE_REF_PREFIX = "refs/remotes/"
CODEX_CAPTURE_REF_PATTERN = re.compile(
    r"^refs/codex/turn-diffs/captures/[0-9]{13}/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/base$"
)
FINGERPRINT_FILES = EXPECTED_CHANGED_FILES - {'docs/evidence/task03_atom4b_pre_git_import_receipt.json'}
EXACT_IMPORT_FILES = {
    path
    for path in EXPECTED_CHANGED_FILES
    if path.startswith("docs/evidence/pre_git/task01/")
    or path.startswith("docs/evidence/pre_git/task02/")
}
STYLE_CHECKED_CHANGED_FILES = EXPECTED_CHANGED_FILES - EXACT_IMPORT_FILES
EXPECTED_EXACT_IMPORT_COUNT = 20
EXACT_IMPORT_WHITESPACE_POLICY = (
    "PRESERVE_EXACT_BYTES_HASH_VERIFIED_STYLE_EXEMPT"
)
EXPECTED_PYTHON = (3, 13, 14)
EXPECTED_POWERSHELL = "7.6.3"
EXPECTED_JSONSCHEMA = "4.26.0"
EXPECTED_PYYAML = "6.0.3"
RECOMMENDED_COMMIT_MESSAGE = 'feat: import pre-git evidence and register architecture intent'
EXPECTED_GITATTRIBUTES = "* text=auto eol=lf\n*.ps1 text eol=lf\n*.bat text eol=crlf\n*.cmd text eol=crlf\n"
PS1_PROBE = "scripts/validate.ps1"
IGNORED_PARTS = {".git", ".smial-handoff", ".venv", "__pycache__"}
IGNORED_REPOSITORY_PREFIXES = {"data/raw"}
CTRL_BATON_DIRTY_REFS = frozenset(
    {"refs/heads/main", "refs/remotes/origin/main"}
)
CTRL_BATON_FEATURE_LOCAL_REFS = frozenset(
    {
        "refs/heads/main",
        f"refs/heads/{CTRL_BATON_FEATURE_BRANCH}",
        "refs/remotes/origin/main",
    }
)
CTRL_BATON_FEATURE_PUBLISHED_REFS = frozenset(
    CTRL_BATON_FEATURE_LOCAL_REFS
    | {f"refs/remotes/origin/{CTRL_BATON_FEATURE_BRANCH}"}
)

CtrlBatonGitView = namedtuple(
    "CtrlBatonGitView",
    (
        "branch",
        "head_oid",
        "head_parents",
        "feature_parents",
        "head_tree_oid",
        "feature_tree_oid",
        "main_oid",
        "origin_main_oid",
        "feature_local_oid",
        "feature_remote_oid",
        "upstream",
        "remotes",
        "fetch_urls",
        "push_urls",
        "fetch_refspecs",
        "push_refspecs",
        "all_refs",
        "tracked",
        "staged",
        "staged_added",
        "staged_modified",
        "unstaged",
        "untracked",
        "conflicts",
        "base_diff",
        "head_subject",
        "commits_after_base",
        "index_base_diff",
        "index_catalog_version",
        "head_tree_path_count",
        "head_catalog_version",
    ),
    defaults=(None, None, None, None, None, None),
)

CtrlBatonGithubContext = namedtuple(
    "CtrlBatonGithubContext",
    (
        "actions",
        "repository",
        "event_name",
        "ref",
        "sha",
        "base_ref",
        "head_ref",
        "event_number",
        "event_ref",
        "event_base_ref",
        "event_base_sha",
        "event_head_ref",
        "event_head_sha",
        "event_before_sha",
        "event_after_sha",
    ),
)


def run(
    command: list[str],
    *,
    binary: bool = False,
    input_data: bytes | str | None = None,
):
    env = os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"] = "1"; env["UV_MANAGED_PYTHON"] = "1"; env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=not binary,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def command_set(command: list[str]) -> tuple[int, set[str]]:
    result = run(command)
    return result.returncode, {line.strip() for line in result.stdout.splitlines() if line.strip()}


def command_lines(command: list[str]) -> tuple[int, tuple[str, ...]]:
    result = run(command)
    return result.returncode, tuple(
        line.strip() for line in result.stdout.splitlines() if line.strip()
    )


class CanonicalRepositoryBytesError(RuntimeError):
    """Fail-closed error while resolving the bytes Git stores as a blob."""


CanonicalRepositoryContent = namedtuple(
    "CanonicalRepositoryContent",
    ("path", "content", "git_oid", "sha256", "source"),
)
CatalogCanonicalIntegritySweep = namedtuple(
    "CatalogCanonicalIntegritySweep",
    ("asset_count", "checked_sha256", "mismatches"),
)


def _safe_canonical_repository_path(relative: str) -> tuple[str, Path]:
    if (
        not isinstance(relative, str)
        or not relative
        or relative != relative.strip()
        or "\x00" in relative
        or "\\" in relative
        or PurePosixPath(relative).is_absolute()
        or PureWindowsPath(relative).is_absolute()
        or PureWindowsPath(relative).drive
    ):
        raise CanonicalRepositoryBytesError("canonical_path_unsafe")
    parts = relative.split("/")
    if (
        any(part in {"", ".", ".."} for part in parts)
        or any(part.casefold() == ".git" for part in parts)
    ):
        raise CanonicalRepositoryBytesError("canonical_path_unsafe")
    root = ROOT.resolve()
    path = (ROOT / Path(*parts)).resolve(strict=False)
    if path != root and root not in path.parents:
        raise CanonicalRepositoryBytesError("canonical_path_escape")
    return relative, path


def _canonical_git_result(
    command: list[str],
    *,
    binary: bool = False,
    input_data: bytes | str | None = None,
    error_code: str,
):
    try:
        result = run(command, binary=binary, input_data=input_data)
    except OSError as exc:
        raise CanonicalRepositoryBytesError(error_code) from exc
    if result.returncode != 0:
        raise CanonicalRepositoryBytesError(error_code)
    return result


def _canonical_git_attributes(relative: str, *, cached: bool) -> dict[str, str]:
    command = ["git", "check-attr"]
    if cached:
        command.append("--cached")
    command.extend(
        [
            "-z",
            "filter",
            "working-tree-encoding",
            "text",
            "eol",
            "--",
            relative,
        ]
    )
    result = _canonical_git_result(
        command,
        binary=True,
        error_code="canonical_check_attr_failed",
    )
    parts = result.stdout.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) != 12:
        raise CanonicalRepositoryBytesError("canonical_check_attr_malformed")
    attributes: dict[str, str] = {}
    for offset in range(0, len(parts), 3):
        try:
            path_value, name, value = (
                part.decode("utf-8") for part in parts[offset : offset + 3]
            )
        except UnicodeDecodeError as exc:
            raise CanonicalRepositoryBytesError(
                "canonical_check_attr_malformed"
            ) from exc
        if path_value != relative or name in attributes:
            raise CanonicalRepositoryBytesError("canonical_check_attr_malformed")
        attributes[name] = value
    if set(attributes) != {"filter", "working-tree-encoding", "text", "eol"}:
        raise CanonicalRepositoryBytesError("canonical_check_attr_malformed")
    if attributes["filter"] != "unspecified":
        raise CanonicalRepositoryBytesError("canonical_custom_filter_unsupported")
    if attributes["working-tree-encoding"] != "unspecified":
        raise CanonicalRepositoryBytesError(
            "canonical_working_tree_encoding_unsupported"
        )
    if attributes["text"] not in {"auto", "set"} or attributes["eol"] != "lf":
        raise CanonicalRepositoryBytesError("canonical_eol_policy_ambiguous")
    return attributes


def _canonical_index_entry(relative: str) -> tuple[str, str] | None:
    result = _canonical_git_result(
        [
            "git",
            "ls-files",
            "--stage",
            "-z",
            "--",
            f":(literal){relative}",
        ],
        binary=True,
        error_code="canonical_index_read_failed",
    )
    records = [record for record in result.stdout.split(b"\0") if record]
    if not records:
        return None
    if len(records) != 1 or b"\t" not in records[0]:
        raise CanonicalRepositoryBytesError("canonical_index_entry_ambiguous")
    metadata, raw_path = records[0].split(b"\t", 1)
    try:
        mode, oid, stage = metadata.decode("ascii").split()
        indexed_path = raw_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise CanonicalRepositoryBytesError(
            "canonical_index_entry_malformed"
        ) from exc
    if indexed_path != relative or stage != "0":
        raise CanonicalRepositoryBytesError("canonical_index_entry_malformed")
    if mode not in {"100644", "100755"}:
        raise CanonicalRepositoryBytesError("canonical_index_mode_not_blob")
    if re.fullmatch(r"[0-9a-f]+", oid) is None:
        raise CanonicalRepositoryBytesError("canonical_index_oid_invalid")
    return mode, oid


def _git_oid_for_content(content: bytes, object_format: str) -> str:
    if object_format not in {"sha1", "sha256"}:
        raise CanonicalRepositoryBytesError("canonical_object_format_unsupported")
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return hashlib.new(object_format, header + content).hexdigest()


def _canonical_hash_object(
    content: bytes,
    *,
    relative: str | None = None,
) -> str:
    command = ["git", "hash-object"]
    if relative is not None:
        command.append(f"--path={relative}")
    command.append("--stdin")
    result = _canonical_git_result(
        command,
        binary=True,
        input_data=content,
        error_code="canonical_hash_object_failed",
    )
    try:
        oid = result.stdout.strip().decode("ascii")
    except UnicodeDecodeError as exc:
        raise CanonicalRepositoryBytesError(
            "canonical_hash_object_invalid"
        ) from exc
    if re.fullmatch(r"[0-9a-f]+", oid) is None:
        raise CanonicalRepositoryBytesError("canonical_hash_object_invalid")
    return oid


def canonical_repository_content(
    relative: str,
    *,
    allow_worktree_candidate: bool = False,
) -> CanonicalRepositoryContent:
    """Resolve and prove the exact content bytes Git stores or would store.

    Clean tracked paths are read from the stage-0 index blob. A dirty tracked or
    untracked path is accepted only when the caller explicitly permits a
    worktree candidate. Candidate conversion is selected from the only two
    transformations supported by this repository policy (identity or CRLF to
    LF), then proved against Git's own side-effect-free hash-object result.
    """

    relative, worktree_path = _safe_canonical_repository_path(relative)
    index_entry = _canonical_index_entry(relative)
    use_worktree = index_entry is None
    if index_entry is not None:
        diff = run(
            [
                "git",
                "diff-files",
                "--quiet",
                "--",
                f":(literal){relative}",
            ]
        )
        if diff.returncode == 1:
            use_worktree = True
        elif diff.returncode != 0:
            raise CanonicalRepositoryBytesError("canonical_worktree_state_failed")

    if not use_worktree:
        _, oid = index_entry
        _canonical_git_attributes(relative, cached=True)
        object_type = _canonical_git_result(
            ["git", "cat-file", "-t", oid],
            error_code="canonical_cat_file_type_failed",
        ).stdout.strip()
        if object_type != "blob":
            raise CanonicalRepositoryBytesError("canonical_index_object_not_blob")
        content = _canonical_git_result(
            ["git", "cat-file", "blob", oid],
            binary=True,
            error_code="canonical_cat_file_blob_failed",
        ).stdout
        if _canonical_hash_object(content) != oid:
            raise CanonicalRepositoryBytesError("canonical_index_blob_oid_mismatch")
        return CanonicalRepositoryContent(
            relative,
            content,
            oid,
            hashlib.sha256(content).hexdigest(),
            "INDEX_BLOB",
        )

    if not allow_worktree_candidate:
        if index_entry is None:
            raise CanonicalRepositoryBytesError("canonical_index_entry_missing")
        raise CanonicalRepositoryBytesError("canonical_worktree_candidate_forbidden")
    if worktree_path.is_symlink() or not worktree_path.is_file():
        raise CanonicalRepositoryBytesError("canonical_worktree_file_missing")
    _canonical_git_attributes(relative, cached=False)
    raw = worktree_path.read_bytes()
    if b"\r" in raw.replace(b"\r\n", b""):
        raise CanonicalRepositoryBytesError("canonical_bare_cr_unsupported")
    git_oid = _canonical_hash_object(raw, relative=relative)
    object_format = _canonical_git_result(
        ["git", "rev-parse", "--show-object-format"],
        error_code="canonical_object_format_read_failed",
    ).stdout.strip()
    candidates = [raw]
    normalized = raw.replace(b"\r\n", b"\n")
    if normalized != raw:
        candidates.append(normalized)
    matching = [
        candidate
        for candidate in candidates
        if _git_oid_for_content(candidate, object_format) == git_oid
    ]
    if len(matching) != 1:
        raise CanonicalRepositoryBytesError("canonical_clean_proof_failed")
    content = matching[0]
    if _canonical_hash_object(content) != git_oid:
        raise CanonicalRepositoryBytesError("canonical_hash_object_parity_failed")
    return CanonicalRepositoryContent(
        relative,
        content,
        git_oid,
        hashlib.sha256(content).hexdigest(),
        "WORKTREE_CLEAN_CANDIDATE",
    )


def canonical_catalog_integrity_sweep(
    *,
    allow_worktree_candidate: bool = False,
) -> CatalogCanonicalIntegritySweep:
    """Check every Catalog record and every repository-backed SHA-256."""

    manifest = yaml.safe_load(
        (ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8")
    )
    registry_paths = manifest.get("root_resolver", {}).get("asset_registries")
    if not isinstance(registry_paths, list) or not registry_paths:
        raise CanonicalRepositoryBytesError("canonical_catalog_registries_invalid")
    records: list[tuple[str, dict]] = []
    for registry_path in registry_paths:
        _, path = _safe_canonical_repository_path(registry_path)
        if not path.is_file():
            raise CanonicalRepositoryBytesError(
                f"canonical_catalog_registry_missing:{registry_path}"
            )
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        shard_records = document.get("records") if isinstance(document, dict) else None
        if not isinstance(shard_records, list):
            raise CanonicalRepositoryBytesError(
                f"canonical_catalog_registry_invalid:{registry_path}"
            )
        records.extend((registry_path, record) for record in shard_records)

    asset_ids: set[str] = set()
    duplicates: set[str] = set()
    missing: list[str] = []
    mismatches: list[tuple[str, str, str, str, str]] = []
    checked = 0
    for shard, record in records:
        asset_id = record.get("asset_id") if isinstance(record, dict) else None
        if not isinstance(asset_id, str) or not asset_id:
            raise CanonicalRepositoryBytesError("canonical_catalog_asset_id_invalid")
        if asset_id in asset_ids:
            duplicates.add(asset_id)
        asset_ids.add(asset_id)
        location = record.get("location")
        integrity = record.get("integrity")
        if not isinstance(location, dict) or not isinstance(integrity, dict):
            raise CanonicalRepositoryBytesError(
                f"canonical_catalog_record_invalid:{asset_id}"
            )
        if location.get("kind") != "git_path":
            continue
        repository_path = location.get("repository_path")
        if not isinstance(repository_path, str):
            missing.append(asset_id)
            continue
        _, actual_path = _safe_canonical_repository_path(repository_path)
        if not actual_path.is_file():
            missing.append(asset_id)
            continue
        if integrity.get("kind") != "sha256":
            continue
        registered = integrity.get("sha256")
        if not isinstance(registered, str):
            raise CanonicalRepositoryBytesError(
                f"canonical_catalog_sha256_invalid:{asset_id}"
            )
        resolved = canonical_repository_content(
            repository_path,
            allow_worktree_candidate=allow_worktree_candidate,
        )
        checked += 1
        if resolved.sha256 != registered:
            mismatches.append(
                (
                    asset_id,
                    shard,
                    repository_path,
                    registered,
                    resolved.sha256,
                )
            )
    if duplicates:
        raise CanonicalRepositoryBytesError(
            "canonical_catalog_duplicate_asset_ids:" + ",".join(sorted(duplicates))
        )
    if missing:
        raise CanonicalRepositoryBytesError(
            "canonical_catalog_missing_paths:" + ",".join(sorted(missing))
        )
    return CatalogCanonicalIntegritySweep(
        len(records),
        checked,
        tuple(mismatches),
    )


def origin_url_is_safe(url: str, *, github_actions: bool) -> bool:
    parsed = urlsplit(url)
    allowed_urls = EXPECTED_CI_ORIGIN_URLS if github_actions else {EXPECTED_ORIGIN_URL}
    return (
        url in allowed_urls
        and parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and not parsed.query
        and not parsed.fragment
    )


def empty_ctrl_baton_github_context() -> CtrlBatonGithubContext:
    return CtrlBatonGithubContext(
        False,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def read_ctrl_baton_github_context() -> CtrlBatonGithubContext:
    """Read only GitHub-provided environment and event payload fields.

    The event payload is never logged wholesale. Missing or malformed fields
    remain ``None`` and therefore fail the corresponding topology classifier.
    """

    actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    if not actions:
        return empty_ctrl_baton_github_context()

    event_name = os.environ.get("GITHUB_EVENT_NAME") or None
    event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    document: dict = {}
    if event_path:
        try:
            candidate = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            candidate = None
        if isinstance(candidate, dict):
            document = candidate

    event_number = document.get("number")
    if not isinstance(event_number, int) or isinstance(event_number, bool):
        event_number = None
    event_ref = document.get("ref")
    if not isinstance(event_ref, str):
        event_ref = None
    event_before_sha = document.get("before")
    if not isinstance(event_before_sha, str):
        event_before_sha = None
    event_after_sha = document.get("after")
    if not isinstance(event_after_sha, str):
        event_after_sha = None

    event_base_ref = event_base_sha = event_head_ref = event_head_sha = None
    pull_request = document.get("pull_request")
    if isinstance(pull_request, dict):
        base = pull_request.get("base")
        head = pull_request.get("head")
        if isinstance(base, dict):
            if isinstance(base.get("ref"), str):
                event_base_ref = base["ref"]
            if isinstance(base.get("sha"), str):
                event_base_sha = base["sha"]
        if isinstance(head, dict):
            if isinstance(head.get("ref"), str):
                event_head_ref = head["ref"]
            if isinstance(head.get("sha"), str):
                event_head_sha = head["sha"]

    return CtrlBatonGithubContext(
        actions,
        os.environ.get("GITHUB_REPOSITORY") or None,
        event_name,
        os.environ.get("GITHUB_REF") or None,
        os.environ.get("GITHUB_SHA") or None,
        os.environ.get("GITHUB_BASE_REF") or None,
        os.environ.get("GITHUB_HEAD_REF") or None,
        event_number,
        event_ref,
        event_base_ref,
        event_base_sha,
        event_head_ref,
        event_head_sha,
        event_before_sha,
        event_after_sha,
    )


def ctrl_baton_origin_identity_ok(
    view: CtrlBatonGitView, *, github_actions: bool
) -> bool:
    allowed_urls = EXPECTED_CI_ORIGIN_URLS if github_actions else {EXPECTED_ORIGIN_URL}
    return (
        view.remotes == frozenset({"origin"})
        and len(view.fetch_urls) == 1
        and view.fetch_urls == view.push_urls
        and view.fetch_urls[0] in allowed_urls
        and origin_url_is_safe(
            view.fetch_urls[0],
            github_actions=github_actions,
        )
        and view.fetch_refspecs == (EXPECTED_ORIGIN_FETCH_REFSPEC,)
        and not view.push_refspecs
    )


def ctrl_baton_expected_changed() -> frozenset[str]:
    return ctrl_baton_a62r_expected_committed_changed()


def ctrl_baton_expected_tracked() -> frozenset[str]:
    return frozenset(ctrl_baton_a62r_expected_committed_tracked())


def ctrl_baton_clean_candidate(view: CtrlBatonGitView) -> bool:
    return (
        view.tracked == ctrl_baton_expected_tracked()
        and len(view.tracked) == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and not view.staged
        and not view.staged_added
        and not view.staged_modified
        and not view.unstaged
        and not view.untracked
        and not view.conflicts
    )


def classify_ctrl_baton_dirty(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == "main"
        and view.head_oid == CTRL_BATON_A62_COMMIT_OID
        and view.head_tree_oid == CTRL_BATON_A62_TREE_OID
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_local_oid is None
        and view.feature_remote_oid is None
        and view.upstream == "origin/main"
        and view.all_refs == CTRL_BATON_DIRTY_REFS
        and view.tracked == frozenset(task08_repository_files())
        and not view.staged
        and not view.staged_added
        and not view.staged_modified
        and view.unstaged == CTRL_BATON_A62R_EXPECTED_MODIFIED
        and view.untracked == CTRL_BATON_A62R_EXPECTED_UNTRACKED
        and not view.conflicts
        and view.base_diff == frozenset()
    )


def classify_ctrl_baton_staged(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.head_oid == CTRL_BATON_A62_COMMIT_OID
        and view.head_tree_oid == CTRL_BATON_A62_TREE_OID
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_local_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_remote_oid is None
        and view.upstream is None
        and view.all_refs == CTRL_BATON_FEATURE_LOCAL_REFS
        and view.tracked == ctrl_baton_expected_tracked()
        and len(view.tracked) == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.staged == ctrl_baton_expected_changed()
        and view.staged_added == CTRL_BATON_A62R_EXPECTED_UNTRACKED
        and view.staged_modified == CTRL_BATON_A62R_EXPECTED_MODIFIED
        and not view.unstaged
        and not view.untracked
        and not view.conflicts
        and view.base_diff == frozenset()
    )


def ctrl_baton_feature_commit_content_ok(view: CtrlBatonGitView) -> bool:
    return (
        re.fullmatch(r"[0-9a-f]{40}", view.head_oid or "") is not None
        and view.head_oid != CTRL_BATON_A62_COMMIT_OID
        and view.head_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and re.fullmatch(r"[0-9a-f]{40}", view.head_tree_oid or "") is not None
        and view.feature_tree_oid == view.head_tree_oid
        and view.head_tree_path_count == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.head_catalog_version == CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
        and view.feature_local_oid == view.head_oid
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.base_diff == ctrl_baton_expected_changed()
        and view.head_subject == CTRL_BATON_A62_COMMIT_SUBJECT
        and view.commits_after_base == 1
        and ctrl_baton_clean_candidate(view)
    )


def classify_ctrl_baton_a69_repair_staged(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.head_oid == CTRL_BATON_A62_FEATURE_OID
        and view.head_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.head_tree_oid == CTRL_BATON_A62_FEATURE_TREE_OID
        and view.feature_tree_oid == CTRL_BATON_A62_FEATURE_TREE_OID
        and view.head_subject == CTRL_BATON_A62_COMMIT_SUBJECT
        and view.commits_after_base == 1
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_local_oid == CTRL_BATON_A62_FEATURE_OID
        and view.feature_remote_oid == CTRL_BATON_A62_FEATURE_OID
        and view.upstream == CTRL_BATON_FEATURE_UPSTREAM
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
        and view.tracked == ctrl_baton_expected_tracked()
        and len(view.tracked) == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.staged == CTRL_BATON_A69_REPAIR_PATHS
        and not view.staged_added
        and view.staged_modified == CTRL_BATON_A69_REPAIR_PATHS
        and not view.unstaged
        and not view.untracked
        and not view.conflicts
        and view.base_diff == ctrl_baton_expected_changed()
        and view.index_base_diff == ctrl_baton_expected_changed()
        and len(view.index_base_diff) == len(ctrl_baton_expected_changed())
        and view.index_catalog_version == CTRL_BATON_A69_EXPECTED_CATALOG_VERSION
    )


def classify_ctrl_baton_a613_reconciliation_staged(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.head_oid == CTRL_BATON_A612_FEATURE_OID
        and view.head_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.head_tree_oid == CTRL_BATON_A612_FEATURE_TREE_OID
        and view.feature_tree_oid == CTRL_BATON_A612_FEATURE_TREE_OID
        and view.head_subject == CTRL_BATON_A62_COMMIT_SUBJECT
        and view.commits_after_base == 1
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_local_oid == CTRL_BATON_A612_FEATURE_OID
        and view.feature_remote_oid == CTRL_BATON_A612_FEATURE_OID
        and view.upstream == CTRL_BATON_FEATURE_UPSTREAM
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
        and view.tracked == ctrl_baton_expected_tracked()
        and len(view.tracked) == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.staged == CTRL_BATON_A613_RECONCILIATION_PATHS
        and not view.staged_added
        and view.staged_modified == CTRL_BATON_A613_RECONCILIATION_PATHS
        and not view.unstaged
        and not view.untracked
        and not view.conflicts
        and view.base_diff == ctrl_baton_expected_changed()
        and view.index_base_diff == ctrl_baton_expected_changed()
        and len(view.index_base_diff) == len(ctrl_baton_expected_changed())
        and view.index_catalog_version == CTRL_BATON_A613_EXPECTED_CATALOG_VERSION
    )


def classify_ctrl_baton_a618_local_main_repair_staged(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.head_oid == CTRL_BATON_A617_FEATURE_OID
        and view.head_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.head_tree_oid == CTRL_BATON_A617_FEATURE_TREE_OID
        and view.feature_tree_oid == CTRL_BATON_A617_FEATURE_TREE_OID
        and view.head_subject == CTRL_BATON_A62_COMMIT_SUBJECT
        and view.commits_after_base == 1
        and view.main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.origin_main_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_local_oid == CTRL_BATON_A617_FEATURE_OID
        and view.feature_remote_oid == CTRL_BATON_A617_FEATURE_OID
        and view.upstream == CTRL_BATON_FEATURE_UPSTREAM
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
        and view.tracked == ctrl_baton_expected_tracked()
        and len(view.tracked) == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.staged == CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS
        and not view.staged_added
        and view.staged_modified == CTRL_BATON_A618_LOCAL_MAIN_REPAIR_PATHS
        and not view.unstaged
        and not view.untracked
        and not view.conflicts
        and view.base_diff == ctrl_baton_expected_changed()
        and view.index_base_diff == ctrl_baton_expected_changed()
        and len(view.index_base_diff) == len(ctrl_baton_expected_changed())
        and view.index_catalog_version == CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
        and view.head_catalog_version == CTRL_BATON_A613_EXPECTED_CATALOG_VERSION
    )


def classify_ctrl_baton_feature_local(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and ctrl_baton_feature_commit_content_ok(view)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.feature_remote_oid is None
        and view.upstream is None
        and view.all_refs == CTRL_BATON_FEATURE_LOCAL_REFS
    )


def classify_ctrl_baton_feature_published(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and ctrl_baton_feature_commit_content_ok(view)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.feature_remote_oid == view.head_oid
        and view.upstream == CTRL_BATON_FEATURE_UPSTREAM
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
    )


def classify_ctrl_baton_feature_ahead_of_published(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and ctrl_baton_feature_commit_content_ok(view)
        and view.branch == CTRL_BATON_FEATURE_BRANCH
        and view.head_oid != CTRL_BATON_A617_FEATURE_OID
        and view.feature_remote_oid == CTRL_BATON_A617_FEATURE_OID
        and view.upstream == CTRL_BATON_FEATURE_UPSTREAM
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
    )


def _pull_request_number(ref: str | None) -> int | None:
    match = re.fullmatch(r"refs/pull/([1-9][0-9]*)/merge", ref or "")
    return int(match.group(1)) if match else None


def ctrl_baton_pr_refs_ok(view: CtrlBatonGitView, number: int) -> bool:
    allowed = {
        "refs/heads/main",
        "refs/remotes/origin/main",
        f"refs/remotes/origin/{CTRL_BATON_FEATURE_BRANCH}",
        f"refs/remotes/pull/{number}/merge",
    }
    return bool(view.all_refs) and view.all_refs <= allowed


def classify_ctrl_baton_pr_merge_checkout(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    number = _pull_request_number(github.ref)
    if number is None or len(view.head_parents) != 2:
        return False
    base_oid, feature_oid = view.head_parents
    return (
        github.actions
        and github.repository == EXPECTED_GITHUB_REPOSITORY
        and github.event_name == "pull_request"
        and github.sha == view.head_oid
        and github.base_ref == "main"
        and github.head_ref == CTRL_BATON_FEATURE_BRANCH
        and github.event_number == number
        and github.event_base_ref == "main"
        and github.event_base_sha == CTRL_BATON_A62_COMMIT_OID
        and github.event_head_ref == CTRL_BATON_FEATURE_BRANCH
        and github.event_head_sha == feature_oid
        and view.branch is None
        and base_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_tree_oid == view.head_tree_oid
        and view.head_tree_path_count == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.head_catalog_version == CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
        and view.base_diff == ctrl_baton_expected_changed()
        and ctrl_baton_clean_candidate(view)
        and ctrl_baton_origin_identity_ok(view, github_actions=True)
        and view.upstream is None
        and ctrl_baton_pr_refs_ok(view, number)
    )


def ctrl_baton_main_refs_ok(
    view: CtrlBatonGitView,
    feature_oid: str,
) -> bool:
    allowed = {
        "refs/heads/main",
        "refs/remotes/origin/main",
        f"refs/remotes/origin/{CTRL_BATON_FEATURE_BRANCH}",
    }
    if not view.all_refs or not view.all_refs <= allowed:
        return False
    if view.feature_remote_oid not in {None, feature_oid}:
        return False
    return {
        "refs/heads/main",
        "refs/remotes/origin/main",
    } <= view.all_refs


def classify_ctrl_baton_main_merge(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    if len(view.head_parents) != 2:
        return False
    base_oid, feature_oid = view.head_parents
    return (
        github.actions
        and github.repository == EXPECTED_GITHUB_REPOSITORY
        and github.event_name == "push"
        and github.ref == "refs/heads/main"
        and github.sha == view.head_oid
        and github.base_ref is None
        and github.head_ref is None
        and github.event_ref == "refs/heads/main"
        and github.event_before_sha == CTRL_BATON_A62_COMMIT_OID
        and github.event_after_sha == view.head_oid
        and view.branch == "main"
        and base_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_tree_oid == view.head_tree_oid
        and view.head_tree_path_count == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.head_catalog_version == CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
        and view.base_diff == ctrl_baton_expected_changed()
        and ctrl_baton_clean_candidate(view)
        and ctrl_baton_origin_identity_ok(view, github_actions=True)
        and view.main_oid == view.head_oid
        and view.origin_main_oid == view.head_oid
        and view.feature_local_oid is None
        and view.upstream in {None, "origin/main"}
        and ctrl_baton_main_refs_ok(view, feature_oid)
    )


def classify_ctrl_baton_main_merge_local(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> bool:
    if len(view.head_parents) != 2:
        return False
    base_oid, feature_oid = view.head_parents
    return (
        not github.actions
        and ctrl_baton_origin_identity_ok(view, github_actions=False)
        and view.branch == "main"
        and base_oid == CTRL_BATON_A62_COMMIT_OID
        and view.feature_parents == (CTRL_BATON_A62_COMMIT_OID,)
        and view.feature_tree_oid == view.head_tree_oid
        and view.head_tree_path_count == CTRL_BATON_EXPECTED_INDEX_PATH_COUNT
        and view.head_catalog_version == CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
        and view.base_diff == ctrl_baton_expected_changed()
        and ctrl_baton_clean_candidate(view)
        and view.main_oid == view.head_oid
        and view.origin_main_oid == view.head_oid
        and view.feature_local_oid == feature_oid
        and view.feature_remote_oid == feature_oid
        and view.upstream == "origin/main"
        and view.all_refs == CTRL_BATON_FEATURE_PUBLISHED_REFS
    )


def classify_ctrl_baton_state_machine(
    view: CtrlBatonGitView,
    github: CtrlBatonGithubContext,
) -> tuple[str, str]:
    """Return one exact repository-state/topology pair or fail closed."""

    if classify_ctrl_baton_dirty(view, github):
        result = ("CTRL_BATON_A62R_CANDIDATE_DIRTY", "PUBLISHED_LOCAL")
    elif classify_ctrl_baton_staged(view, github):
        result = (
            "CTRL_BATON_A62R_CANDIDATE_STAGED",
            "BATON_FEATURE_LOCAL",
        )
    elif classify_ctrl_baton_a69_repair_staged(view, github):
        result = (
            "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
            "BATON_FEATURE_PUBLISHED_REPAIR_STAGED",
        )
    elif classify_ctrl_baton_a613_reconciliation_staged(view, github):
        result = (
            "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
            "BATON_FEATURE_PUBLISHED_RECONCILIATION_STAGED",
        )
    elif classify_ctrl_baton_a618_local_main_repair_staged(view, github):
        result = (
            "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
            "BATON_FEATURE_PUBLISHED_LOCAL_MAIN_REPAIR_STAGED",
        )
    elif classify_ctrl_baton_feature_local(view, github):
        result = (
            "CTRL_BATON_A62_FEATURE_COMMITTED",
            "BATON_FEATURE_LOCAL",
        )
    elif classify_ctrl_baton_feature_ahead_of_published(view, github):
        result = (
            "CTRL_BATON_A62_FEATURE_COMMITTED",
            "BATON_FEATURE_AHEAD_OF_PUBLISHED",
        )
    elif classify_ctrl_baton_feature_published(view, github):
        result = (
            "CTRL_BATON_A62_FEATURE_COMMITTED",
            "BATON_FEATURE_PUBLISHED",
        )
    elif classify_ctrl_baton_pr_merge_checkout(view, github):
        result = (
            "CTRL_BATON_A62_PR_MERGE_CHECKOUT",
            "GITHUB_PR_MERGE_CHECKOUT",
        )
    elif classify_ctrl_baton_main_merge(view, github):
        result = (
            "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
            "GITHUB_MAIN_PUSH_CHECKOUT",
        )
    elif classify_ctrl_baton_main_merge_local(view, github):
        result = (
            "CTRL_BATON_A62_MAIN_MERGE_COMMITTED",
            "BATON_MAIN_LOCAL_POST_MERGE",
        )
    else:
        return ("INVALID_REPOSITORY_STATE", "INVALID_GIT_TOPOLOGY")

    if result not in CTRL_BATON_A62_LIFECYCLE_COMBINATIONS:
        return ("INVALID_REPOSITORY_STATE", "INVALID_GIT_TOPOLOGY")
    return result


def policy_refs(all_refs: set[str]) -> set[str] | None:
    result = set()
    for ref in all_refs:
        if ref.startswith("refs/codex/"):
            if not CODEX_CAPTURE_REF_PATTERN.fullmatch(ref):
                return None
            continue
        result.add(ref)
    return result


def parse_remote_ref_records(output: str) -> tuple[set[str], str | None]:
    """Parse full Git remote ref records and enforce the exact origin policy."""
    remote_tracking_refs: set[str] = set()
    remote_head_target = None
    allowed_refs = {"origin/HEAD", "origin/main"}
    expected_head_target = "refs/remotes/origin/main"

    for line in output.splitlines():
        if not line:
            continue
        if line.count("\t") != 1:
            raise AssertionError("remote_ref_record_malformed")
        full_name, symref = line.split("\t", 1)
        if full_name != full_name.strip() or symref != symref.strip():
            raise AssertionError("remote_ref_record_whitespace")
        if not full_name.startswith(REMOTE_REF_PREFIX):
            raise AssertionError("remote_ref_prefix_invalid")
        name = full_name[len(REMOTE_REF_PREFIX) :]
        if name not in allowed_refs:
            raise AssertionError(f"remote_ref_not_allowed:{name}")
        if name in remote_tracking_refs:
            raise AssertionError(f"duplicate_remote_ref:{name}")
        if name == "origin/HEAD":
            if symref != expected_head_target:
                raise AssertionError("origin_head_target_invalid")
            remote_head_target = symref
        elif symref:
            raise AssertionError(f"unexpected_remote_symref:{name}")
        remote_tracking_refs.add(name)

    if remote_head_target is not None and "origin/main" not in remote_tracking_refs:
        raise AssertionError("origin_head_target_missing")
    return remote_tracking_refs, remote_head_target


def parse_remote_ref_inventory(output: str) -> tuple[set[str], str | None]:
    """Parse all remote refs without electing an allowed topology."""

    remote_tracking_refs: set[str] = set()
    remote_head_target = None
    for line in output.splitlines():
        if not line:
            continue
        if line.count("\t") != 1:
            raise AssertionError("remote_ref_record_malformed")
        full_name, symref = line.split("\t", 1)
        if full_name != full_name.strip() or symref != symref.strip():
            raise AssertionError("remote_ref_record_whitespace")
        if not full_name.startswith(REMOTE_REF_PREFIX):
            raise AssertionError("remote_ref_prefix_invalid")
        name = full_name[len(REMOTE_REF_PREFIX) :]
        if name in remote_tracking_refs:
            raise AssertionError(f"duplicate_remote_ref:{name}")
        if symref:
            if (
                name != "origin/HEAD"
                or symref != "refs/remotes/origin/main"
            ):
                raise AssertionError(f"unexpected_remote_symref:{name}")
            remote_head_target = symref
        remote_tracking_refs.add(name)
    return remote_tracking_refs, remote_head_target


def optional_git_oid(ref: str) -> str | None:
    result = run(["git", "rev-parse", "--verify", ref])
    value = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        return None
    return value


def git_commit_parents(oid: str | None) -> tuple[str, ...]:
    if oid is None:
        return ()
    result = run(["git", "show", "-s", "--format=%P", oid])
    if result.returncode != 0:
        return ()
    parents = tuple(result.stdout.strip().split())
    if any(re.fullmatch(r"[0-9a-f]{40}", parent) is None for parent in parents):
        return ()
    return parents


def git_tree_oid(oid: str | None) -> str | None:
    if oid is None:
        return None
    result = run(["git", "rev-parse", "--verify", f"{oid}^{{tree}}"])
    value = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        return None
    return value


def git_tree_path_count(oid: str | None) -> int | None:
    if oid is None:
        return None
    code, paths = command_set(["git", "ls-tree", "-r", "--name-only", oid])
    return len(paths) if code == 0 else None


def git_commit_subject(oid: str | None) -> str | None:
    if oid is None:
        return None
    result = run(["git", "show", "-s", "--format=%s", oid])
    return result.stdout.strip() if result.returncode == 0 else None


def git_commit_count_after_base(base_oid: str, target_oid: str) -> int | None:
    result = run(["git", "rev-list", "--count", f"{base_oid}..{target_oid}"])
    value = result.stdout.strip()
    if result.returncode != 0 or not value.isdigit():
        return None
    return int(value)


def git_diff_paths(base_oid: str, target_oid: str) -> frozenset[str] | None:
    code, paths = command_set(
        ["git", "diff", "--name-only", base_oid, target_oid, "--"]
    )
    return frozenset(paths) if code == 0 else None


def git_index_diff_paths(base_oid: str) -> frozenset[str] | None:
    code, paths = command_set(
        ["git", "diff", "--cached", "--name-only", base_oid, "--"]
    )
    return frozenset(paths) if code == 0 else None


def git_index_catalog_version() -> str | None:
    result = run(["git", "show", ":catalog/catalog_manifest.yaml"], binary=True)
    if result.returncode != 0:
        return None
    try:
        manifest = yaml.safe_load(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(manifest, dict):
        return None
    value = manifest.get("catalog_version")
    return str(value) if value is not None else None


def git_commit_catalog_version(oid: str | None) -> str | None:
    if oid is None:
        return None
    result = run(
        ["git", "show", f"{oid}:catalog/catalog_manifest.yaml"],
        binary=True,
    )
    if result.returncode != 0:
        return None
    try:
        manifest = yaml.safe_load(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(manifest, dict):
        return None
    value = manifest.get("catalog_version")
    return str(value) if value is not None else None


def collect_ctrl_baton_git_view(
    *,
    branch: str | None,
    head_oid: str,
    remotes: set[str],
    fetch_urls: tuple[str, ...],
    push_urls: tuple[str, ...],
    fetch_refspecs: tuple[str, ...],
    push_refspecs: tuple[str, ...],
    upstream: str | None,
    all_refs: set[str],
    tracked: set[str],
    staged: set[str],
    unstaged: set[str],
    untracked: set[str],
) -> CtrlBatonGitView:
    head_parents = git_commit_parents(head_oid)
    feature_local_oid = optional_git_oid(
        f"refs/heads/{CTRL_BATON_FEATURE_BRANCH}"
    )
    feature_remote_oid = optional_git_oid(
        f"refs/remotes/origin/{CTRL_BATON_FEATURE_BRANCH}"
    )
    feature_oid = None
    if len(head_parents) == 2:
        feature_oid = head_parents[1]
    elif branch == CTRL_BATON_FEATURE_BRANCH and head_oid != CTRL_BATON_A62_COMMIT_OID:
        feature_oid = head_oid
    elif (
        feature_local_oid is not None
        and feature_local_oid != CTRL_BATON_A62_COMMIT_OID
    ):
        feature_oid = feature_local_oid

    added_code, staged_added = command_set(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"]
    )
    modified_code, staged_modified = command_set(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=M"]
    )
    conflict_code, conflicts = command_set(
        ["git", "diff", "--name-only", "--diff-filter=U"]
    )
    if any(code != 0 for code in (added_code, modified_code, conflict_code)):
        raise AssertionError("ctrl_baton_inventory_read_failed")

    return CtrlBatonGitView(
        branch,
        head_oid,
        head_parents,
        git_commit_parents(feature_oid),
        git_tree_oid(head_oid),
        git_tree_oid(feature_oid),
        optional_git_oid("refs/heads/main"),
        optional_git_oid("refs/remotes/origin/main"),
        feature_local_oid,
        feature_remote_oid,
        upstream,
        frozenset(remotes),
        fetch_urls,
        push_urls,
        fetch_refspecs,
        push_refspecs,
        frozenset(all_refs),
        frozenset(tracked),
        frozenset(staged),
        frozenset(staged_added),
        frozenset(staged_modified),
        frozenset(unstaged),
        frozenset(untracked),
        frozenset(conflicts),
        git_diff_paths(CTRL_BATON_A62_COMMIT_OID, head_oid),
        git_commit_subject(head_oid),
        git_commit_count_after_base(CTRL_BATON_A62_COMMIT_OID, head_oid),
        git_index_diff_paths(CTRL_BATON_A62_COMMIT_OID),
        git_index_catalog_version(),
        git_tree_path_count(head_oid),
        git_commit_catalog_version(head_oid),
    )


def classify_git_topology(
    *,
    branch: str | None,
    head_oid: str,
    remotes: set[str],
    fetch_urls: tuple[str, ...],
    push_urls: tuple[str, ...],
    fetch_refspecs: tuple[str, ...],
    push_refspecs: tuple[str, ...],
    upstream: str | None,
    local_branches: set[str],
    remote_tracking_refs: set[str],
    tags: set[str],
    all_refs: set[str],
    github_actions: bool,
    github_repository: str | None,
    github_ref: str | None,
    github_sha: str | None,
    remote_head_target: str | None = None,
) -> str:
    if tags or push_refspecs:
        return "INVALID_GIT_TOPOLOGY"
    repository_refs = policy_refs(all_refs)
    if repository_refs is None:
        return "INVALID_GIT_TOPOLOGY"

    if github_actions:
        origin_identity_ok = (
            remotes == {"origin"}
            and len(fetch_urls) == 1
            and fetch_urls == push_urls
            and origin_url_is_safe(fetch_urls[0], github_actions=True)
            and remote_head_target is None
        )
        refspec_policy_ok = fetch_refspecs == (
            EXPECTED_ORIGIN_FETCH_REFSPEC,
        )
        refs_ok = (
            branch in {None, "main"}
            and local_branches <= {"main"}
            and remote_tracking_refs <= {"origin/main"}
            and repository_refs
            <= {"refs/heads/main", "refs/remotes/origin/main"}
        )
        upstream_ok = (
            (branch is None and upstream is None)
            or (branch == "main" and upstream in {None, "origin/main"})
        )
        context_ok = (
            github_repository == EXPECTED_GITHUB_REPOSITORY
            and github_ref == "refs/heads/main"
            and github_sha == head_oid
        )
        if origin_identity_ok and refspec_policy_ok and refs_ok and upstream_ok and context_ok:
            return "GITHUB_ACTIONS_CHECKOUT"
        return "INVALID_GIT_TOPOLOGY"

    if branch != "main" or local_branches != {"main"}:
        return "INVALID_GIT_TOPOLOGY"

    if not remotes:
        if (
            not fetch_urls
            and not push_urls
            and not fetch_refspecs
            and upstream is None
            and not remote_tracking_refs
            and remote_head_target is None
            and repository_refs == {"refs/heads/main"}
        ):
            return "PRE_REMOTE"
        return "INVALID_GIT_TOPOLOGY"

    origin_identity_ok = (
        remotes == {"origin"}
        and fetch_urls == (EXPECTED_ORIGIN_URL,)
        and push_urls == (EXPECTED_ORIGIN_URL,)
        and origin_url_is_safe(fetch_urls[0], github_actions=False)
    )
    if not origin_identity_ok:
        return "INVALID_GIT_TOPOLOGY"

    wildcard_refspec_ok = fetch_refspecs == (
        EXPECTED_ORIGIN_FETCH_REFSPEC,
    )
    single_branch_refspec_ok = fetch_refspecs == (
        EXPECTED_SINGLE_BRANCH_FETCH_REFSPEC,
    )

    if (
        wildcard_refspec_ok
        and upstream is None
        and not remote_tracking_refs
        and remote_head_target is None
        and repository_refs == {"refs/heads/main"}
    ):
        return "BOUND_PRE_PUSH"
    if (
        wildcard_refspec_ok
        and upstream == "origin/main"
        and remote_tracking_refs == {"origin/main"}
        and remote_head_target is None
        and repository_refs
        == {"refs/heads/main", "refs/remotes/origin/main"}
    ):
        return "PUBLISHED_LOCAL"
    if (
        (wildcard_refspec_ok or single_branch_refspec_ok)
        and upstream == "origin/main"
        and remote_tracking_refs == {"origin/HEAD", "origin/main"}
        and remote_head_target == "refs/remotes/origin/main"
        and repository_refs
        == {
            "refs/heads/main",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        }
    ):
        return "CLEAN_CLONE"
    return "INVALID_GIT_TOPOLOGY"


def tree_files(treeish: str) -> set[str]:
    code, files = command_set(["git", "ls-tree", "-r", "--name-only", treeish])
    if code != 0:
        raise AssertionError(f"tree_inventory_read_failed:{treeish}")
    return files


def import_repository_files() -> set[str]:
    return tree_files(IMPORT_COMMIT_OID)


def work_acceptance_repository_files() -> set[str]:
    return tree_files(WORK_ACCEPTANCE_COMMIT_OID)


def atom5_repository_files() -> set[str]:
    return tree_files(ATOM5_COMMIT_OID)


def atom5_work_acceptance_repository_files() -> set[str]:
    return tree_files(ATOM5_WORK_ACCEPTANCE_COMMIT_OID)


def atom7_repository_files() -> set[str]:
    return (
        atom5_work_acceptance_repository_files()
        | ATOM7_LOCAL_CI_CREATED_FILES
    )


def task04_repository_files() -> set[str]:
    return tree_files(TASK04_BASE_COMMIT_OID) | TASK04_CREATED_FILES


def task05_repository_files() -> set[str]:
    return tree_files(TASK05_BASE_COMMIT_OID) | TASK05_CREATED_FILES


def task05_finalization_repository_files() -> set[str]:
    return (
        tree_files(TASK05_FINALIZATION_BASE_COMMIT_OID)
        | TASK05_FINALIZATION_CREATED_FILES
    )


def task06_repository_files() -> set[str]:
    return tree_files(TASK06_BASE_COMMIT_OID) | TASK06_CREATED_FILES


def task06_finalization_repository_files() -> set[str]:
    return (
        tree_files(TASK06_FINALIZATION_BASE_COMMIT_OID)
        | TASK06_FINALIZATION_CREATED_FILES
    )


def task07_repository_files() -> set[str]:
    return tree_files(TASK07_BASE_COMMIT_OID) | TASK07_CREATED_FILES


def task08_repository_files() -> set[str]:
    return tree_files(TASK08_BASE_COMMIT_OID) | TASK08_CREATED_FILES


def repository_files() -> set[str]:
    result = set()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        relative_posix = relative.as_posix()
        if (
            not path.is_file()
            or any(part in IGNORED_PARTS for part in relative.parts)
            or path.suffix in {".pyc", ".pyo"}
            or any(
                relative_posix == prefix
                or relative_posix.startswith(f"{prefix}/")
                for prefix in IGNORED_REPOSITORY_PREFIXES
            )
        ):
            continue
        result.add(relative_posix)
    return result


def parse_index_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result = {}
    for record in records.split(b"\0"):
        if not record: continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        if stage != "0": raise AssertionError("non_zero_index_stage")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def parse_tree_entries(records: bytes) -> dict[str, tuple[str, str]]:
    result = {}
    for record in records.split(b"\0"):
        if not record: continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split()
        if object_type != "blob": raise AssertionError("non_blob_tree_entry")
        result[raw_path.decode("utf-8")] = (mode, oid)
    return result


def source_entries(state: str) -> dict[str, tuple[str, str]]:
    if state == "PRE_GIT_IMPORT_STAGED":
        result = run(["git","ls-files","--stage","-z"], binary=True)
        if result.returncode != 0: raise AssertionError("index_read_failed")
        return parse_index_entries(result.stdout)
    result = run(["git","ls-tree","-r","-z",IMPORT_COMMIT_OID], binary=True)
    if result.returncode != 0: raise AssertionError("head_tree_read_failed")
    return parse_tree_entries(result.stdout)


def blob_bytes(state: str, path: str) -> bytes:
    if state == "PRE_GIT_IMPORT_STAGED":
        reference = f":{path}"
    else:
        reference = f"{IMPORT_COMMIT_OID}:{path}"
    result = run(["git","show",reference], binary=True)
    if result.returncode != 0: raise AssertionError(f"blob_read_failed:{path}")
    return result.stdout


def fingerprints(state: str) -> tuple[str, str]:
    entries = source_entries(state); manifest = bytearray(); content = bytearray()
    for path in sorted(FINGERPRINT_FILES):
        mode, oid = entries[path]
        manifest.extend(f"{mode} {oid} {path}\n".encode("utf-8"))
        blob = blob_bytes(state, path); encoded = path.encode("utf-8")
        content.extend(len(encoded).to_bytes(4,"big")); content.extend(encoded); content.extend(len(blob).to_bytes(8,"big")); content.extend(blob)
    return hashlib.sha256(bytes(manifest)).hexdigest(), hashlib.sha256(bytes(content)).hexdigest()


def classify_state(
    *,
    head_oid: str,
    commit_count: int,
    parent_oid: str | None,
    tracked: set[str],
    staged: set[str],
    untracked: set[str],
    unstaged: set[str],
    commit_subject: str | None = None,
    commit_changed: set[str] | None = None,
) -> str:
    import_files = import_repository_files()
    work_files = work_acceptance_repository_files()
    atom5_files = atom5_repository_files()
    atom5_acceptance_files = atom5_work_acceptance_repository_files()
    atom7_files = atom7_repository_files()
    task04_files = task04_repository_files()
    task05_files = task05_repository_files()
    task05_finalization_files = task05_finalization_repository_files()
    task06_files = task06_repository_files()
    task06_finalization_files = task06_finalization_repository_files()
    task07_files = task07_repository_files()
    task08_files = task08_repository_files()
    if (
        head_oid == TASK08_BASE_COMMIT_OID
        and commit_count == TASK08_BASE_COMMIT_COUNT
        and parent_oid == TASK08_BASE_PARENT_OID
        and tracked == task08_files
        and len(tracked) == TASK08_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK08_CHANGED_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK07_COMMIT_SUBJECT
        and commit_changed == TASK07_CHANGED_FILES
    ):
        return "TASK08_ATOM8A_CANDIDATE_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK08_BASE_COMMIT_OID
        and commit_count == TASK08_COMMIT_COUNT
        and parent_oid == TASK08_BASE_COMMIT_OID
        and tracked == task08_files
        and len(tracked) == TASK08_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK08_COMMIT_SUBJECT
        and commit_changed == TASK08_CHANGED_FILES
    ):
        return "TASK08_ATOM8B_CANDIDATE_COMMITTED"
    if (
        head_oid == TASK07_BASE_COMMIT_OID
        and commit_count == TASK07_BASE_COMMIT_COUNT
        and parent_oid == TASK07_BASE_PARENT_OID
        and tracked == task07_files
        and len(tracked) == TASK07_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK07_CHANGED_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK06_FINALIZATION_COMMIT_SUBJECT
        and commit_changed == TASK06_FINALIZATION_FILES
    ):
        return "TASK07_ATOM6A_CANDIDATE_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK07_BASE_COMMIT_OID
        and commit_count == TASK07_COMMIT_COUNT
        and parent_oid == TASK07_BASE_COMMIT_OID
        and tracked == task07_files
        and len(tracked) == TASK07_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK07_COMMIT_SUBJECT
        and commit_changed == TASK07_CHANGED_FILES
    ):
        return "TASK07_ATOM6B_CANDIDATE_COMMITTED"
    if (
        head_oid == TASK06_FINALIZATION_BASE_COMMIT_OID
        and commit_count == TASK06_FINALIZATION_BASE_COMMIT_COUNT
        and parent_oid == TASK06_FINALIZATION_BASE_PARENT_OID
        and tracked == task06_finalization_files
        and len(tracked)
        == TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK06_FINALIZATION_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK06_COMMIT_SUBJECT
        and commit_changed == TASK06_CHANGED_FILES
    ):
        return "TASK06_FINALIZATION_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK06_FINALIZATION_BASE_COMMIT_OID
        and commit_count == TASK06_FINALIZATION_COMMIT_COUNT
        and parent_oid == TASK06_FINALIZATION_BASE_COMMIT_OID
        and tracked == task06_finalization_files
        and len(tracked)
        == TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK06_FINALIZATION_COMMIT_SUBJECT
        and commit_changed == TASK06_FINALIZATION_FILES
    ):
        return "TASK06_FINALIZATION_COMMITTED"
    if (
        head_oid == TASK06_BASE_COMMIT_OID
        and commit_count == TASK06_BASE_COMMIT_COUNT
        and parent_oid == TASK06_BASE_PARENT_OID
        and tracked == task06_files
        and len(tracked) == TASK06_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK06_CHANGED_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK05_FINALIZATION_COMMIT_SUBJECT
        and commit_changed == TASK05_FINALIZATION_FILES
    ):
        return "TASK06_ATOM7A_CANDIDATE_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK06_BASE_COMMIT_OID
        and commit_count == TASK06_COMMIT_COUNT
        and parent_oid == TASK06_BASE_COMMIT_OID
        and tracked == task06_files
        and len(tracked) == TASK06_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK06_COMMIT_SUBJECT
        and commit_changed == TASK06_CHANGED_FILES
    ):
        return "TASK06_ATOM7B_CANDIDATE_COMMITTED"
    if (
        head_oid == TASK05_FINALIZATION_BASE_COMMIT_OID
        and commit_count == TASK05_FINALIZATION_BASE_COMMIT_COUNT
        and parent_oid == TASK05_FINALIZATION_BASE_PARENT_OID
        and tracked == task05_finalization_files
        and len(tracked)
        == TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK05_FINALIZATION_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK05_COMMIT_SUBJECT
        and commit_changed == TASK05_CHANGED_FILES
    ):
        return "TASK05_FINALIZATION_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK05_FINALIZATION_BASE_COMMIT_OID
        and commit_count == TASK05_FINALIZATION_COMMIT_COUNT
        and parent_oid == TASK05_FINALIZATION_BASE_COMMIT_OID
        and tracked == task05_finalization_files
        and len(tracked)
        == TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK05_FINALIZATION_COMMIT_SUBJECT
        and commit_changed == TASK05_FINALIZATION_FILES
    ):
        return "TASK05_FINALIZATION_COMMITTED"
    if (
        head_oid == TASK05_BASE_COMMIT_OID
        and commit_count == TASK05_BASE_COMMIT_COUNT
        and parent_oid == TASK05_BASE_PARENT_OID
        and tracked == task05_files
        and len(tracked) == TASK05_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK05_CHANGED_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK04_POLICY_REPAIR_COMMIT_SUBJECT
        and commit_changed == TASK04_POLICY_REPAIR_FILES
    ):
        return "TASK05_ATOM5A_CANDIDATE_STAGED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK05_BASE_COMMIT_OID
        and commit_count == TASK05_COMMIT_COUNT
        and parent_oid == TASK05_BASE_COMMIT_OID
        and tracked == task05_files
        and len(tracked) == TASK05_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK05_COMMIT_SUBJECT
        and commit_changed == TASK05_CHANGED_FILES
    ):
        return "TASK05_ATOM5B_CANDIDATE_COMMITTED"
    if (
        head_oid == TASK04_ARCHITECTURE_COMMIT_OID
        and commit_count == TASK04_ARCHITECTURE_COMMIT_COUNT
        and parent_oid == TASK04_BASE_COMMIT_OID
        and tracked == task04_files
        and len(tracked) == TASK04_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK04_POLICY_REPAIR_FILES
        and not untracked
        and not unstaged
        and commit_subject == TASK04_ARCHITECTURE_COMMIT_SUBJECT
        and commit_changed == TASK04_CHANGED_FILES
    ):
        return "TASK04_ATOM5B_POLICY_REPAIR_STAGED"
    if (
        head_oid == TASK04_ARCHITECTURE_COMMIT_OID
        and commit_count == TASK04_ARCHITECTURE_COMMIT_COUNT
        and parent_oid == TASK04_BASE_COMMIT_OID
        and tracked == task04_files
        and len(tracked) == TASK04_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK04_ARCHITECTURE_COMMIT_SUBJECT
        and commit_changed == TASK04_CHANGED_FILES
    ):
        return "TASK04_ATOM5B_ARCHITECTURE_COMMITTED"
    if (
        re.fullmatch(r"[0-9a-f]{40}", head_oid) is not None
        and head_oid != TASK04_ARCHITECTURE_COMMIT_OID
        and commit_count == TASK04_POLICY_REPAIR_COMMIT_COUNT
        and parent_oid == TASK04_ARCHITECTURE_COMMIT_OID
        and tracked == task04_files
        and len(tracked) == TASK04_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == TASK04_POLICY_REPAIR_COMMIT_SUBJECT
        and commit_changed == TASK04_POLICY_REPAIR_FILES
    ):
        return "TASK04_ATOM5B_POLICY_REPAIR_COMMITTED"
    if (
        head_oid == TASK04_BASE_COMMIT_OID
        and commit_count == TASK04_BASE_COMMIT_COUNT
        and parent_oid == TASK04_BASE_PARENT_OID
        and tracked == task04_files
        and len(tracked) == TASK04_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == TASK04_CHANGED_FILES
        and not untracked
        and not unstaged
        and commit_subject == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
    ):
        return "TASK04_ATOM5A_CANDIDATE_STAGED"
    if (
        head_oid == BASE_COMMIT_OID
        and commit_count == BASE_COMMIT_COUNT
        and parent_oid == BASE_PARENT_OID
        and tracked == import_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and staged == EXPECTED_CHANGED_FILES
        and not untracked
        and not unstaged
    ):
        return "PRE_GIT_IMPORT_STAGED"
    if (
        head_oid == IMPORT_COMMIT_OID
        and commit_count == IMPORT_COMMIT_COUNT
        and parent_oid == BASE_COMMIT_OID
        and tracked == import_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not untracked
        and not unstaged
        and commit_subject == RECOMMENDED_COMMIT_MESSAGE
        and commit_changed == EXPECTED_CHANGED_FILES
    ):
        return "PRE_GIT_IMPORT_COMMITTED"
    if (
        head_oid == IMPORT_COMMIT_OID
        and commit_count == IMPORT_COMMIT_COUNT
        and parent_oid == BASE_COMMIT_OID
        and tracked == work_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and staged == WORK_ACCEPTANCE_SYNC_FILES
        and not unstaged
        and not untracked
    ):
        return "WORK_ACCEPTANCE_SYNC_STAGED"
    if (
        head_oid == WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == IMPORT_COMMIT_OID
        and tracked == work_files
        and len(tracked) == EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == WORK_ACCEPTANCE_COMMIT_SUBJECT
        and commit_changed == WORK_ACCEPTANCE_SYNC_FILES
    ):
        return "WORK_ACCEPTANCE_SYNC_COMMITTED"
    if (
        head_oid == WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == IMPORT_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM5_CHANGED_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM5_REGISTRIES_NAVIGATION_STAGED"
    if (
        head_oid == ATOM5_COMMIT_OID
        and commit_count == ATOM5_COMMIT_COUNT
        and parent_oid == WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM5_COMMIT_SUBJECT
        and commit_changed == ATOM5_CHANGED_FILES
    ):
        return "ATOM5_REGISTRIES_NAVIGATION_COMMITTED"
    if (
        head_oid == ATOM5_COMMIT_OID
        and commit_count == ATOM5_COMMIT_COUNT
        and parent_oid == WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom5_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM5_WORK_ACCEPTANCE_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM5_WORK_ACCEPTANCE_STAGED"
    if (
        head_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and
        commit_count == ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == ATOM5_COMMIT_OID
        and tracked == atom5_acceptance_files
        and len(tracked) == ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM5_WORK_ACCEPTANCE_COMMIT_SUBJECT
        and commit_changed == ATOM5_WORK_ACCEPTANCE_FILES
    ):
        return "ATOM5_WORK_ACCEPTANCE_COMMITTED"
    if (
        head_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and commit_count == ATOM5_WORK_ACCEPTANCE_COMMIT_COUNT
        and parent_oid == ATOM5_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_LOCAL_CI_FILES
        and not unstaged
        and not untracked
    ):
        return "ATOM7_LOCAL_CI_CANDIDATE_STAGED"
    if (
        commit_count == ATOM7_LOCAL_CI_COMMIT_COUNT
        and parent_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_LOCAL_CI_COMMIT_SUBJECT
        and commit_changed == ATOM7_LOCAL_CI_FILES
    ):
        return "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED"
    if (
        head_oid == ATOM7_LOCAL_CI_COMMIT_OID
        and commit_count == ATOM7_LOCAL_CI_COMMIT_COUNT
        and parent_oid == ATOM5_WORK_ACCEPTANCE_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_PRE_PUSH_REPAIR_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_LOCAL_CI_COMMIT_SUBJECT
        and commit_changed == ATOM7_LOCAL_CI_FILES
    ):
        return "ATOM7_PRE_PUSH_REPAIR_STAGED"
    if (
        commit_count == ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_LOCAL_CI_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_PRE_PUSH_REPAIR_FILES
    ):
        return "ATOM7_PRE_PUSH_REPAIR_COMMITTED"
    if (
        head_oid == ATOM7_PRE_PUSH_REPAIR_COMMIT_OID
        and commit_count == ATOM7_PRE_PUSH_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_LOCAL_CI_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_CI_CLEAN_CLONE_REPAIR_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_PRE_PUSH_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_PRE_PUSH_REPAIR_FILES
    ):
        return "ATOM7_CI_CLEAN_CLONE_REPAIR_STAGED"
    if (
        commit_count == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_PRE_PUSH_REPAIR_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_CI_CLEAN_CLONE_REPAIR_FILES
    ):
        return "ATOM7_CI_CLEAN_CLONE_REPAIR_COMMITTED"
    if (
        head_oid == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID
        and commit_count == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_PRE_PUSH_REPAIR_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_FINAL_HANDOFF_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_CI_CLEAN_CLONE_REPAIR_FILES
    ):
        return "ATOM7_FINAL_HANDOFF_STAGED"
    if (
        commit_count == ATOM7_FINAL_HANDOFF_COMMIT_COUNT
        and parent_oid == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT
        and commit_changed == ATOM7_FINAL_HANDOFF_FILES
    ):
        return "ATOM7_FINAL_HANDOFF_COMMITTED"
    if (
        head_oid == ATOM7_FINAL_HANDOFF_COMMIT_OID
        and commit_count == ATOM7_FINAL_HANDOFF_COMMIT_COUNT
        and parent_oid == ATOM7_CI_CLEAN_CLONE_REPAIR_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_REF_NORMALIZATION_REPAIR_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_FINAL_HANDOFF_COMMIT_SUBJECT
        and commit_changed == ATOM7_FINAL_HANDOFF_FILES
    ):
        return "ATOM7_REF_NORMALIZATION_REPAIR_STAGED"
    if (
        commit_count == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_FINAL_HANDOFF_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_REF_NORMALIZATION_REPAIR_FILES
    ):
        return "ATOM7_REF_NORMALIZATION_REPAIR_COMMITTED"
    if (
        head_oid == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID
        and commit_count == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_FINAL_HANDOFF_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and staged == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_REF_NORMALIZATION_REPAIR_FILES
    ):
        return "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_STAGED"
    if (
        commit_count == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_COUNT
        and parent_oid == ATOM7_REF_NORMALIZATION_REPAIR_COMMIT_OID
        and tracked == atom7_files
        and len(tracked) == ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
        and not staged
        and not unstaged
        and not untracked
        and commit_subject == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMIT_SUBJECT
        and commit_changed == ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES
    ):
        return "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMITTED"
    return "INVALID_REPOSITORY_STATE"


def parse_check_attr_z(output: bytes) -> tuple[str,str,str]:
    parts = output.split(b"\0"); parts = parts[:-1] if parts and parts[-1] == b"" else parts
    if len(parts) != 3: raise AssertionError("check_attr_triplet_invalid")
    return tuple(part.decode("utf-8") for part in parts)


def validate_eol(state: str) -> None:
    if (ROOT/".gitattributes").read_text(encoding="utf-8") != EXPECTED_GITATTRIBUTES: raise AssertionError("gitattributes_policy_mismatch")
    attr = run(["git","check-attr","--cached","-z","eol","--",PS1_PROBE], binary=True)
    if attr.returncode != 0 or parse_check_attr_z(attr.stdout) != (PS1_PROBE,"eol","lf"): raise AssertionError("cached_eol_mismatch")
    if b"\r" in (ROOT/PS1_PROBE).read_bytes() or b"\r" in blob_bytes(state, PS1_PROBE): raise AssertionError("ps1_contains_cr")
    with tempfile.TemporaryDirectory(prefix="smial_atom4b_checkout_") as temporary:
        result = run(["git","checkout-index","--all","--force",f"--prefix={Path(temporary).as_posix().rstrip('/')}/"])
        if result.returncode != 0 or b"\r" in (Path(temporary)/PS1_PROBE).read_bytes(): raise AssertionError("checkout_roundtrip_eol_failed")


def assert_check(name: str, condition: bool, detail: str = "") -> None:
    if not condition: raise AssertionError(name + ((": " + detail) if detail else ""))
    print(f"{name}: PASS")


def validate_staged_style_policy() -> None:
    """Apply whitespace style checks only to repository-authored changes.

    Exact pre-Git evidence is immutable, hash-verified source material. Rewriting
    or rejecting it for style would violate exact-byte provenance. Its hashes, LF
    encoding, secret/path scan, source bundle lineage, and availability are
    validated separately by validate_pre_git_import.py.
    """
    assert_check(
        "exact_import_style_exempt_count",
        len(EXACT_IMPORT_FILES) == EXPECTED_EXACT_IMPORT_COUNT,
        str(len(EXACT_IMPORT_FILES)),
    )
    assert_check(
        "style_policy_partition",
        not (EXACT_IMPORT_FILES & STYLE_CHECKED_CHANGED_FILES)
        and (EXACT_IMPORT_FILES | STYLE_CHECKED_CHANGED_FILES)
        == EXPECTED_CHANGED_FILES,
    )
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(STYLE_CHECKED_CHANGED_FILES),
        ]
    )
    assert_check(
        "staged_style_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )
    print("immutable_exact_import_style_policy: PASS")


def validate_work_acceptance_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(WORK_ACCEPTANCE_SYNC_FILES),
        ]
    )
    assert_check(
        "work_acceptance_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom5_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM5_CHANGED_FILES),
        ]
    )
    assert_check(
        "atom5_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom5_work_acceptance_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM5_WORK_ACCEPTANCE_FILES),
        ]
    )
    assert_check(
        "atom5_work_acceptance_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_local_ci_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_LOCAL_CI_FILES),
        ]
    )
    assert_check(
        "atom7_local_ci_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_pre_push_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_PRE_PUSH_REPAIR_FILES),
        ]
    )
    assert_check(
        "atom7_pre_push_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_ci_clean_clone_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_CI_CLEAN_CLONE_REPAIR_FILES),
        ]
    )
    assert_check(
        "atom7_ci_clean_clone_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_final_handoff_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_FINAL_HANDOFF_FILES),
        ]
    )
    assert_check(
        "atom7_final_handoff_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_ref_normalization_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_REF_NORMALIZATION_REPAIR_FILES),
        ]
    )
    assert_check(
        "atom7_ref_normalization_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_atom7_single_branch_refspec_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_FILES),
        ]
    )
    assert_check(
        "atom7_single_branch_refspec_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task04_atom5a_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK04_CHANGED_FILES),
        ]
    )
    assert_check(
        "task04_atom5a_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task04_atom5b_policy_repair_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK04_POLICY_REPAIR_FILES),
        ]
    )
    assert_check(
        "task04_atom5b_policy_repair_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task05_atom5a_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK05_CHANGED_FILES),
        ]
    )
    assert_check(
        "task05_atom5a_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task05_finalization_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK05_FINALIZATION_FILES),
        ]
    )
    assert_check(
        "task05_finalization_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task06_atom7a_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK06_CHANGED_FILES),
        ]
    )
    assert_check(
        "task06_atom7a_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_task06_finalization_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(TASK06_FINALIZATION_FILES),
        ]
    )
    assert_check(
        "task06_finalization_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate_ctrl_baton_staged_style_policy() -> None:
    diff = run(
        [
            "git",
            "diff",
            "--cached",
            "--check",
            "--",
            *sorted(ctrl_baton_expected_changed()),
        ]
    )
    assert_check(
        "ctrl_baton_staged_diff_check",
        diff.returncode == 0,
        diff.stdout.strip() + diff.stderr.strip(),
    )


def validate() -> None:
    github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    branch_result = run(["git", "symbolic-ref", "--short", "HEAD"])
    branch_name = (
        branch_result.stdout.strip() if branch_result.returncode == 0 else None
    )
    head = run(["git","rev-parse","HEAD"]); assert_check("head_read", head.returncode == 0); head_oid = head.stdout.strip()
    count = run(["git","rev-list","--count","HEAD"]); assert_check("commit_count_read", count.returncode == 0); commit_count = int(count.stdout.strip())
    parent_oid = None
    if commit_count >= 2:
        parent = run(["git","rev-parse","HEAD^"]); assert_check("parent_read", parent.returncode == 0); parent_oid = parent.stdout.strip()
    remote_code, remotes = command_set(["git", "remote"])
    fetch_url_code = push_url_code = fetch_refspec_code = push_refspec_code = 0
    fetch_urls: tuple[str, ...] = ()
    push_urls: tuple[str, ...] = ()
    fetch_refspecs: tuple[str, ...] = ()
    push_refspecs: tuple[str, ...] = ()
    if "origin" in remotes:
        fetch_url_code, fetch_urls = command_lines(
            ["git", "remote", "get-url", "--all", "origin"]
        )
        push_url_code, push_urls = command_lines(
            ["git", "remote", "get-url", "--push", "--all", "origin"]
        )
        fetch_refspec_code, fetch_refspecs = command_lines(
            ["git", "config", "--get-all", "remote.origin.fetch"]
        )
        push_refspec_code, push_refspecs = command_lines(
            ["git", "config", "--get-all", "remote.origin.push"]
        )
    upstream_result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    upstream = (
        upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    )
    local_branch_code, local_branches = command_set(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"]
    )
    remote_ref_result = run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname)%09%(symref)",
            "refs/remotes",
        ]
    )
    remote_ref_code = remote_ref_result.returncode
    remote_tracking_refs, remote_head_target = parse_remote_ref_inventory(
        remote_ref_result.stdout
    )
    tag_code, tags = command_set(["git", "tag", "--list"])
    all_ref_code, all_refs = command_set(
        ["git", "for-each-ref", "--format=%(refname)"]
    )
    tracked_code, tracked = command_set(["git","ls-files"])
    staged_code, staged = command_set(["git","diff","--cached","--name-only"])
    untracked_code, untracked = command_set(["git","ls-files","--others","--exclude-standard"])
    unstaged_code, unstaged = command_set(["git","diff","--name-only"])
    subject = run(["git","show","-s","--format=%s","HEAD"])
    changed_code, commit_changed = command_set(["git","diff-tree","--no-commit-id","--name-only","-r","HEAD"])
    inventory_codes = (
        remote_code,
        fetch_url_code,
        push_url_code,
        fetch_refspec_code,
        local_branch_code,
        remote_ref_code,
        tag_code,
        all_ref_code,
        tracked_code,
        staged_code,
        untracked_code,
        unstaged_code,
        subject.returncode,
        changed_code,
    )
    assert_check(
        "git_inventory_commands",
        all(code == 0 for code in inventory_codes)
        and push_refspec_code in {0, 1}
        and (upstream_result.returncode == 0 or not upstream_result.stdout.strip()),
    )
    github_context = read_ctrl_baton_github_context()
    baton_view = collect_ctrl_baton_git_view(
        branch=branch_name,
        head_oid=head_oid,
        remotes=remotes,
        fetch_urls=fetch_urls,
        push_urls=push_urls,
        fetch_refspecs=fetch_refspecs,
        push_refspecs=push_refspecs,
        upstream=upstream,
        all_refs=all_refs,
        tracked=tracked,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
    )
    baton_state, baton_topology = classify_ctrl_baton_state_machine(
        baton_view,
        github_context,
    )
    legacy_topology = classify_git_topology(
        branch=branch_name,
        head_oid=head_oid,
        remotes=remotes,
        fetch_urls=fetch_urls,
        push_urls=push_urls,
        fetch_refspecs=fetch_refspecs,
        push_refspecs=push_refspecs,
        upstream=upstream,
        local_branches=local_branches,
        remote_tracking_refs=remote_tracking_refs,
        tags=tags,
        all_refs=all_refs,
        github_actions=github_actions,
        github_repository=os.environ.get("GITHUB_REPOSITORY"),
        github_ref=os.environ.get("GITHUB_REF"),
        github_sha=os.environ.get("GITHUB_SHA"),
        remote_head_target=remote_head_target,
    )
    legacy_state = classify_state(
        head_oid=head_oid,
        commit_count=commit_count,
        parent_oid=parent_oid,
        tracked=tracked,
        staged=staged,
        untracked=untracked,
        unstaged=unstaged,
        commit_subject=subject.stdout.strip(),
        commit_changed=commit_changed,
    )
    if (baton_state, baton_topology) in CTRL_BATON_A62_LIFECYCLE_COMBINATIONS:
        state = baton_state
        topology = baton_topology
    else:
        assert_check(
            "branch_main_or_ci_detached",
            (branch_result.returncode == 0 and branch_name == "main")
            or (github_actions and branch_result.returncode != 0),
        )
        state = legacy_state
        topology = legacy_topology
    assert_check(
        "repository_topology",
        topology != "INVALID_GIT_TOPOLOGY",
        topology,
    )
    valid_states = {
        "PRE_GIT_IMPORT_STAGED",
        "PRE_GIT_IMPORT_COMMITTED",
        "WORK_ACCEPTANCE_SYNC_STAGED",
        "WORK_ACCEPTANCE_SYNC_COMMITTED",
        "ATOM5_REGISTRIES_NAVIGATION_STAGED",
        "ATOM5_REGISTRIES_NAVIGATION_COMMITTED",
        "ATOM5_WORK_ACCEPTANCE_STAGED",
        "ATOM5_WORK_ACCEPTANCE_COMMITTED",
        "ATOM7_LOCAL_CI_CANDIDATE_STAGED",
        "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED",
        "ATOM7_PRE_PUSH_REPAIR_STAGED",
        "ATOM7_PRE_PUSH_REPAIR_COMMITTED",
        "ATOM7_CI_CLEAN_CLONE_REPAIR_STAGED",
        "ATOM7_CI_CLEAN_CLONE_REPAIR_COMMITTED",
        "ATOM7_FINAL_HANDOFF_STAGED",
        "ATOM7_FINAL_HANDOFF_COMMITTED",
        "ATOM7_REF_NORMALIZATION_REPAIR_STAGED",
        "ATOM7_REF_NORMALIZATION_REPAIR_COMMITTED",
        "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_STAGED",
        "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMITTED",
    } | (
        TASK04_REPOSITORY_STATES
        | TASK05_REPOSITORY_STATES
        | TASK06_REPOSITORY_STATES
        | TASK07_REPOSITORY_STATES
        | TASK08_REPOSITORY_STATES
        | CTRL_BATON_A62_REPOSITORY_STATES
    )
    assert_check("repository_state", state in valid_states, state)
    if state in CTRL_BATON_A62_REPOSITORY_STATES:
        assert_check(
            "ctrl_baton_state_topology_combination",
            (state, topology) in CTRL_BATON_A62_LIFECYCLE_COMBINATIONS,
            f"{state}/{topology}",
        )
    if state == "ATOM7_FINAL_HANDOFF_STAGED":
        assert_check(
            "atom7_final_handoff_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "ATOM7_FINAL_HANDOFF_COMMITTED":
        assert_check(
            "atom7_final_handoff_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "ATOM7_REF_NORMALIZATION_REPAIR_STAGED":
        assert_check(
            "atom7_ref_normalization_repair_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "ATOM7_REF_NORMALIZATION_REPAIR_COMMITTED":
        assert_check(
            "atom7_ref_normalization_repair_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_STAGED":
        assert_check(
            "atom7_single_branch_refspec_repair_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMITTED":
        assert_check(
            "atom7_single_branch_refspec_repair_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "TASK04_ATOM5A_CANDIDATE_STAGED":
        assert_check(
            "task04_atom5a_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "TASK04_ATOM5B_POLICY_REPAIR_STAGED":
        assert_check(
            "task04_atom5b_policy_repair_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state in TASK04_COMMITTED_STATES:
        assert_check(
            "task04_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "TASK05_ATOM5A_CANDIDATE_STAGED":
        assert_check(
            "task05_atom5a_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "TASK05_FINALIZATION_STAGED":
        assert_check(
            "task05_finalization_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state in TASK05_COMMITTED_STATES:
        assert_check(
            "task05_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "TASK06_ATOM7A_CANDIDATE_STAGED":
        assert_check(
            "task06_atom7a_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state == "TASK06_FINALIZATION_STAGED":
        assert_check(
            "task06_finalization_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state in TASK06_COMMITTED_STATES:
        assert_check(
            "task06_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "TASK07_ATOM6A_CANDIDATE_STAGED":
        assert_check(
            "task07_atom6a_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state in TASK07_COMMITTED_STATES:
        assert_check(
            "task07_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state == "TASK08_ATOM8A_CANDIDATE_STAGED":
        assert_check(
            "task08_atom8a_staged_topology",
            topology == "PUBLISHED_LOCAL",
            topology,
        )
    if state in TASK08_COMMITTED_STATES:
        assert_check(
            "task08_committed_topology",
            topology
            in {"PUBLISHED_LOCAL", "GITHUB_ACTIONS_CHECKOUT", "CLEAN_CLONE"},
            topology,
        )
    if state in TASK08_REPOSITORY_STATES:
        expected_file_count = TASK08_EXPECTED_REPOSITORY_FILE_COUNT
    elif state in CTRL_BATON_A62_REPOSITORY_STATES:
        expected_file_count = ctrl_baton_a62r_expected_repository_file_count()
    elif state in TASK07_REPOSITORY_STATES:
        expected_file_count = TASK07_EXPECTED_REPOSITORY_FILE_COUNT
    elif state in TASK06_FINALIZATION_REPOSITORY_STATES:
        expected_file_count = (
            TASK06_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        )
    elif state in TASK06_REPOSITORY_STATES:
        expected_file_count = TASK06_EXPECTED_REPOSITORY_FILE_COUNT
    elif state in TASK05_FINALIZATION_REPOSITORY_STATES:
        expected_file_count = (
            TASK05_FINALIZATION_EXPECTED_REPOSITORY_FILE_COUNT
        )
    elif state in TASK05_REPOSITORY_STATES:
        expected_file_count = TASK05_EXPECTED_REPOSITORY_FILE_COUNT
    elif state in TASK04_REPOSITORY_STATES:
        expected_file_count = TASK04_EXPECTED_REPOSITORY_FILE_COUNT
    elif state.startswith("ATOM7_"):
        expected_file_count = ATOM7_EXPECTED_REPOSITORY_FILE_COUNT
    elif state.startswith("ATOM5_"):
        expected_file_count = ATOM5_EXPECTED_REPOSITORY_FILE_COUNT
    else:
        expected_file_count = EXPECTED_REPOSITORY_FILE_COUNT
    assert_check("repository_file_count", len(repository_files()) == expected_file_count)
    if state == "PRE_GIT_IMPORT_COMMITTED":
        message = run(["git","log","-1","--pretty=%B"])
        assert_check("import_commit_message", message.returncode == 0 and message.stdout.strip() == RECOMMENDED_COMMIT_MESSAGE, message.stdout.strip())
    if state == "WORK_ACCEPTANCE_SYNC_COMMITTED":
        assert_check("work_acceptance_commit_contract", True)
    if state == "ATOM5_REGISTRIES_NAVIGATION_COMMITTED":
        assert_check("atom5_commit_contract", True)
    if state == "ATOM5_WORK_ACCEPTANCE_COMMITTED":
        assert_check("atom5_work_acceptance_commit_contract", True)
    if state == "ATOM7_LOCAL_CI_CANDIDATE_COMMITTED":
        assert_check("atom7_local_ci_commit_contract", True)
    if state == "ATOM7_PRE_PUSH_REPAIR_COMMITTED":
        assert_check("atom7_pre_push_repair_commit_contract", True)
    if state == "ATOM7_CI_CLEAN_CLONE_REPAIR_COMMITTED":
        assert_check("atom7_ci_clean_clone_repair_commit_contract", True)
    if state == "ATOM7_FINAL_HANDOFF_COMMITTED":
        assert_check("atom7_final_handoff_commit_contract", True)
    if state == "ATOM7_REF_NORMALIZATION_REPAIR_COMMITTED":
        assert_check("atom7_ref_normalization_repair_commit_contract", True)
    if state == "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_COMMITTED":
        assert_check("atom7_single_branch_refspec_repair_commit_contract", True)
    if state == "TASK04_ATOM5B_ARCHITECTURE_COMMITTED":
        assert_check("task04_atom5b_architecture_commit_contract", True)
    if state == "TASK04_ATOM5B_POLICY_REPAIR_COMMITTED":
        assert_check("task04_atom5b_policy_repair_commit_contract", True)
    if state == "TASK05_ATOM5B_CANDIDATE_COMMITTED":
        assert_check("task05_atom5b_commit_contract", True)
    if state == "TASK05_FINALIZATION_COMMITTED":
        assert_check("task05_finalization_commit_contract", True)
    if state == "TASK06_ATOM7B_CANDIDATE_COMMITTED":
        assert_check("task06_atom7b_commit_contract", True)
    if state == "TASK06_FINALIZATION_COMMITTED":
        assert_check("task06_finalization_commit_contract", True)
    if state == "TASK07_ATOM6B_CANDIDATE_COMMITTED":
        assert_check("task07_atom6b_commit_contract", True)
    if state == "TASK08_ATOM8B_CANDIDATE_COMMITTED":
        assert_check("task08_atom8b_commit_contract", True)
    manifest = yaml.safe_load(
        (ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8")
    )
    assert_check(
        "deferred_capabilities",
        set(manifest["deferred_capabilities"])
        == EXPECTED_DEFERRED_CAPABILITIES,
    )
    if state in TASK08_REPOSITORY_STATES:
        assert_check(
            "task08_catalog_version",
            str(manifest.get("catalog_version"))
            == TASK08_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task08_catalog_asset_count",
            asset_count == TASK08_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task08_catalog_query_count",
            query_count == TASK08_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in CTRL_BATON_A62_REPOSITORY_STATES:
        if state == "CTRL_BATON_A69_PR_CI_REPAIR_STAGED":
            expected_ctrl_baton_catalog_version = (
                CTRL_BATON_A69_EXPECTED_CATALOG_VERSION
            )
        elif state == "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED":
            expected_ctrl_baton_catalog_version = (
                CTRL_BATON_A613_EXPECTED_CATALOG_VERSION
            )
        else:
            expected_ctrl_baton_catalog_version = (
                CTRL_BATON_A62_EXPECTED_CATALOG_VERSION
            )
        assert_check(
            "ctrl_baton_a62_catalog_version",
            str(manifest.get("catalog_version"))
            == expected_ctrl_baton_catalog_version,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        schema_registry_files = len(
            list(manifest.get("root_resolver", {}).get("schemas") or [])
        )
        schema_asset_records = 0
        asset_ids: set[str] = set()
        for relative in manifest["root_resolver"]["asset_registries"]:
            document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for record in document["records"]:
                asset_ids.add(record["asset_id"])
                if record.get("asset_type") == "schema":
                    schema_asset_records += 1
        mandatory_ids = list(manifest.get("mandatory_asset_ids") or [])
        print(
            "ctrl_baton_a62_catalog_counts:"
            f" asset_records={asset_count}"
            f" schema_registry_files={schema_registry_files}"
            f" schema_asset_records={schema_asset_records}"
            f" query_records={query_count}"
            f" mandatory_asset_ids={len(mandatory_ids)}"
        )
        assert_check("ctrl_baton_a62_catalog_asset_count_positive", asset_count > 0)
        assert_check("ctrl_baton_a62_catalog_query_count_positive", query_count > 0)
        assert_check(
            "ctrl_baton_a62_mandatory_ids_nonempty",
            len(mandatory_ids) > 0,
        )
        missing_mandatory = sorted(set(mandatory_ids) - asset_ids)
        assert_check(
            "ctrl_baton_a62_mandatory_ids_present",
            not missing_mandatory,
            ",".join(missing_mandatory),
        )
        assert_check(
            "ctrl_baton_a62_no_catalog_tx_script",
            "SCRIPT-BATON-CATALOG-TX-001" not in asset_ids,
        )
        assert_check(
            "ctrl_baton_a62_fixture_suite_registered",
            "FIXTURE-BATON-SUITE-001" in asset_ids,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in TASK07_REPOSITORY_STATES:
        assert_check(
            "task07_catalog_version",
            str(manifest.get("catalog_version"))
            == TASK07_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task07_catalog_asset_count",
            asset_count == TASK07_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task07_catalog_query_count",
            query_count == TASK07_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in TASK06_FINALIZATION_REPOSITORY_STATES:
        assert_check(
            "task06_finalization_catalog_version",
            str(manifest.get("catalog_version"))
            == TASK06_FINALIZATION_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task06_finalization_catalog_asset_count",
            asset_count == TASK06_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task06_finalization_catalog_query_count",
            query_count == TASK06_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in TASK06_REPOSITORY_STATES:
        assert_check(
            "task06_catalog_version",
            str(manifest.get("catalog_version"))
            == TASK06_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task06_catalog_asset_count",
            asset_count == TASK06_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task06_catalog_query_count",
            query_count == TASK06_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in TASK04_REPOSITORY_STATES:
        assert_check(
            "task04_catalog_version",
            str(manifest.get("catalog_version")) == TASK04_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))["records"])
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check("task04_catalog_asset_count", asset_count == TASK04_EXPECTED_CATALOG_ASSET_COUNT)
        lifecycle = [
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    if state in TASK05_FINALIZATION_REPOSITORY_STATES:
        assert_check(
            "task05_finalization_catalog_version",
            str(manifest.get("catalog_version"))
            == TASK05_FINALIZATION_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["records"]
            )
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task05_finalization_catalog_asset_count",
            asset_count == TASK05_FINALIZATION_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(
                yaml.safe_load(
                    (ROOT / relative).read_text(encoding="utf-8")
                )["recipes"]
            )
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task05_finalization_catalog_query_count",
            query_count == TASK05_FINALIZATION_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    elif state in TASK05_REPOSITORY_STATES:
        assert_check(
            "task05_catalog_version",
            str(manifest.get("catalog_version")) == TASK05_EXPECTED_CATALOG_VERSION,
        )
        asset_count = sum(
            len(yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))["records"])
            for relative in manifest["root_resolver"]["asset_registries"]
        )
        assert_check(
            "task05_catalog_asset_count",
            asset_count == TASK05_EXPECTED_CATALOG_ASSET_COUNT,
        )
        query_count = sum(
            len(yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))["recipes"])
            for relative in manifest["root_resolver"]["query_registries"]
        )
        assert_check(
            "task05_catalog_query_count",
            query_count == TASK05_EXPECTED_CATALOG_QUERY_COUNT,
        )
        lifecycle = [
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for relative in manifest["root_resolver"]["lifecycle_registries"]
        ]
        reuse_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] == "reuse_candidates"
        )
        production_count = sum(
            len(document["records"])
            for document in lifecycle
            if document["registry_type"] != "reuse_candidates"
        )
        assert_check("reuse_decision_record_count", reuse_count == 52)
        assert_check("production_lifecycle_record_count", production_count == 0)
    assert_check("venv_present", (ROOT/".venv").is_dir())
    assert_check("runtime_exact", sys.version_info[:3] == EXPECTED_PYTHON)
    assert_check("runtime_is_venv", Path(sys.prefix).resolve() == (ROOT/".venv").resolve())
    assert_check("jsonschema_version", importlib.metadata.version("jsonschema") == EXPECTED_JSONSCHEMA)
    assert_check("pyyaml_version", importlib.metadata.version("PyYAML") == EXPECTED_PYYAML)
    with (ROOT/"pyproject.toml").open("rb") as handle: metadata = tomllib.load(handle)
    expected_dependencies = (
        TASK04_EXPECTED_RUNTIME_DEPENDENCIES
        if state
        in TASK04_REPOSITORY_STATES
        | TASK05_REPOSITORY_STATES
        | TASK06_REPOSITORY_STATES
        | TASK07_REPOSITORY_STATES
        | TASK08_REPOSITORY_STATES
        | CTRL_BATON_A62_REPOSITORY_STATES
        else {f"PyYAML=={EXPECTED_PYYAML}", f"jsonschema=={EXPECTED_JSONSCHEMA}"}
    )
    assert_check("dependency_contract", set(metadata["project"]["dependencies"]) == expected_dependencies)
    if (
        state
        in TASK04_REPOSITORY_STATES
        | TASK05_REPOSITORY_STATES
        | TASK06_REPOSITORY_STATES
        | TASK07_REPOSITORY_STATES
        | TASK08_REPOSITORY_STATES
        | CTRL_BATON_A62_REPOSITORY_STATES
    ):
        assert_check(
            "security_dependency_group",
            metadata.get("dependency-groups") == {"security": ["pip-audit==2.10.1"]},
        )
        assert_check(
            "mutable_tool_metadata_removed",
            not ({"task", "stage", "catalog_version"} & set(metadata["tool"]["solana-alpha-lab"])),
        )
        for distribution, expected in TASK04_EXPECTED_RUNTIME_VERSIONS.items():
            assert_check(
                f"runtime_version:{distribution}",
                importlib.metadata.version(distribution) == expected,
            )
        try:
            importlib.metadata.version("pip-audit")
        except importlib.metadata.PackageNotFoundError:
            print("runtime_security_group_absent: PASS")
        else:
            raise AssertionError("runtime_security_group_present")
    assert_check("uv_version_contract", metadata["tool"]["uv"].get("required-version") == "==0.11.29")
    lock = run(["uv","lock","--check","--managed-python"]); assert_check("uv_lock_check", lock.returncode == 0, lock.stderr.strip())
    receipt = json.loads(CURRENT_RECEIPT.read_text(encoding="utf-8"))
    assert_check("receipt_identity", receipt.get("task_id") == "TASK-03" and receipt.get("atom_id") == "TASK03-ATOM-4B" and receipt.get("result") == "PASS")
    assert_check("receipt_base_commit", receipt.get("base_commit_oid") == BASE_COMMIT_OID and receipt.get("base_tree_oid") == BASE_TREE_OID)
    assert_check("receipt_candidate_contract", receipt.get("candidate_state") == "PRE_GIT_IMPORT_STAGED" and receipt.get("post_commit_state_supported") == "PRE_GIT_IMPORT_COMMITTED" and receipt.get("recommended_commit_message") == RECOMMENDED_COMMIT_MESSAGE)
    assert_check("receipt_counts", receipt.get("repository_file_count") == EXPECTED_REPOSITORY_FILE_COUNT and receipt.get("staged_file_count") == len(EXPECTED_CHANGED_FILES) and receipt.get("imported_exact_file_count") == 20 and receipt.get("catalog_asset_count") == 44)
    assert_check(
        "receipt_exact_import_style_policy",
        receipt.get("exact_import_whitespace_policy")
        == EXACT_IMPORT_WHITESPACE_POLICY
        and receipt.get("exact_import_style_exempt_file_count")
        == EXPECTED_EXACT_IMPORT_COUNT,
    )
    manifest_hash, content_hash = fingerprints(state)
    assert_check("payload_manifest_fingerprint", receipt.get("payload_manifest_sha256") == manifest_hash)
    assert_check("payload_content_fingerprint", receipt.get("payload_content_sha256") == content_hash)
    assert_check(
        "source_inventory",
        set(source_entries(state)) == import_repository_files(),
    )
    assert_check("pre_commit_mode", source_entries(state)[".githooks/pre-commit"][0] == "100755")
    validate_eol(state); print("eol_checkout_contract: PASS")
    if state == "PRE_GIT_IMPORT_STAGED":
        validate_staged_style_policy()
    if state == "WORK_ACCEPTANCE_SYNC_STAGED":
        validate_work_acceptance_staged_style_policy()
    if state == "ATOM5_REGISTRIES_NAVIGATION_STAGED":
        validate_atom5_staged_style_policy()
    if state == "ATOM5_WORK_ACCEPTANCE_STAGED":
        validate_atom5_work_acceptance_staged_style_policy()
    if state == "ATOM7_LOCAL_CI_CANDIDATE_STAGED":
        validate_atom7_local_ci_staged_style_policy()
    if state == "ATOM7_PRE_PUSH_REPAIR_STAGED":
        validate_atom7_pre_push_repair_staged_style_policy()
    if state == "ATOM7_CI_CLEAN_CLONE_REPAIR_STAGED":
        validate_atom7_ci_clean_clone_repair_staged_style_policy()
    if state == "ATOM7_FINAL_HANDOFF_STAGED":
        validate_atom7_final_handoff_staged_style_policy()
    if state == "ATOM7_REF_NORMALIZATION_REPAIR_STAGED":
        validate_atom7_ref_normalization_repair_staged_style_policy()
    if state == "ATOM7_SINGLE_BRANCH_REFSPEC_REPAIR_STAGED":
        validate_atom7_single_branch_refspec_repair_staged_style_policy()
    if state == "TASK04_ATOM5A_CANDIDATE_STAGED":
        validate_task04_atom5a_staged_style_policy()
    if state == "TASK04_ATOM5B_POLICY_REPAIR_STAGED":
        validate_task04_atom5b_policy_repair_staged_style_policy()
    if state == "TASK05_ATOM5A_CANDIDATE_STAGED":
        validate_task05_atom5a_staged_style_policy()
    if state == "TASK05_FINALIZATION_STAGED":
        validate_task05_finalization_staged_style_policy()
    if state == "TASK06_ATOM7A_CANDIDATE_STAGED":
        validate_task06_atom7a_staged_style_policy()
    if state == "TASK06_FINALIZATION_STAGED":
        validate_task06_finalization_staged_style_policy()
    if state in {
        "CTRL_BATON_A62R_CANDIDATE_STAGED",
        "CTRL_BATON_A69_PR_CI_REPAIR_STAGED",
        "CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED",
        "CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED",
    }:
        validate_ctrl_baton_staged_style_policy()
    tests = run([sys.executable,"-B","-m","unittest","discover","-s","tests","-p","test_*.py"])
    if tests.stdout.strip(): print(tests.stdout.strip())
    if tests.stderr.strip(): print(tests.stderr.strip())
    assert_check("unit_tests", tests.returncode == 0)
    print(f"GIT_TOPOLOGY: {topology}")
    print(f"REPOSITORY_STATE: {state}")
    print("RESULT: PASS")


def main() -> int:
    print("=== TASK-03 REPOSITORY STATE VALIDATION ===")
    try: validate()
    except Exception as exc:
        print("RESULT: FAIL"); print(f"ERROR_TYPE: {type(exc).__name__}"); print(f"ERROR: {exc}"); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
