---
task_id: COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1
task_version: '1.0'
status: READY
as_of: '2026-09-20'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 70f6a97399118a55bb655886ddbbeb01ebda0fcb
  expected_upstream: origin/main
  expected_upstream_oid: 70f6a97399118a55bb655886ddbbeb01ebda0fcb
  expected_branch: cursor/cohort-data-root-and-import-readback-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Resolve one canonical Research Data Plane from any linked worktree and print
  one operational cohort import readback after publish-live-cohort or
  import-live, without a second import of an exact already-present lineage.

managed_write_set:
  - docs/tasks/COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1.md
  - src/solana_alpha_lab/factory/data_root.py
  - src/solana_alpha_lab/factory/cohort_import_readback.py
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - scripts/discovery_evidence_release.py
  - tests/test_cohort_data_root_and_import_readback_v1.py
  - tests/test_hfic_preflight.py
  - tests/test_research_lifecycle_workbench_v1.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/cohort_data_root_and_import_readback/a1_owner_readout_v1.md
  - docs/evidence/cohort_data_root_and_import_readback/a1_c1_c2_readback_v1.json
  - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_completion_evidence_v1.json
  - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_independent_review_v1.json
  - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - A3_OR_LATER_SCOPE
  - FORGE_EXECUTION
  - SCIENTIFIC_PROBE_EXECUTION
  - ADDENDUM_IMPLEMENTATION
  - PROVIDER_CALL
  - VPS_DEPLOY
  - COLLECTOR_RUNTIME_MUTATION
  - DESTRUCTIVE_RUNTIME_DATA_ROLLBACK
  - ABSOLUTE_MACHINE_PATHS_IN_DURABLE_RECEIPT
  - DISK_CRAWL_OR_SIBLING_GUESS
  - NEW_PARALLEL_EXECUTABLE
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/data_root.py
    DELIVERY_EVIDENCE:
      - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_completion_evidence_v1.json
      - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_independent_review_v1.json
      - docs/evidence/cohort_data_root_and_import_readback/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1

ATOM_ID: `COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1`

Program: second atom of owner-path convergence. Do not implement A3–A5
or the 2026-09-20 provenance addendum.

## Task Outcome Brief

- **Owner decision:** publish/import from any linked worktree lands in one
  project Research Data Plane and immediately prints one operational
  readback.
- **Product outcome:** default data root is the Git principal checkout
  `local/factory_v1/data_plane`; `publish-live-cohort` and `import-live`
  share `COHORT_IMPORT_READBACK_V1`.
- **Named consumer:** later A3 Forge input/visibility; current consumer is
  the owner import loop.
- **Cheapest falsifier:** a linked worktree resolves a different default
  root; a second exact import creates a duplicate lineage; durable
  readback contains an absolute machine path.
- **Terminal:** targeted tests + persist=False C1/C2 lineage readback +
  reviews + exact-head CI + merge-readiness. Stop before owner phrase.
- **Non-goals:** A3 scientific visibility; A4 ladder; A5 identity/gold;
  Forge run; collector/VPS mutation; destructive rollback of imported
  bytes; addendum `model_profile` / `reasoning_profile`.

## Decision capsule

- `DECISION_DELTA`: default root = Git common principal checkout data
  plane, not the current worktree; one shared import readback; exact
  re-import is `PASS_ALREADY_PRESENT_EXACT`.
- `UNCERTAINTY_REMOVED`: whether two worktrees and a duplicate import
  still split the owner corpus view.
- `CAPABILITY_OR_EVIDENCE`: hash-bound C1/C2 readback with counts 1/1
  and `corpus_version=2` when that lineage is already imported.
- `STOP`: merge-readiness; no `/hypothesis-forge`.
- `NEXT`: after merge/readback, recommended A3
  `FORGE_INPUT_TRUTH_AND_VISIBILITY_V1`.
- `SPEC_ROUTE`: `DESIGN_SPEC`.
- `REPLAN_TRIGGER`: disk crawl/sibling guess required; new executable
  required; A3 visibility leaks in; third independent scientific
  blocker on real C1/C2 readback.

## Canonical root

Priority unchanged:

1. explicit `--data-root`
2. `SMIAL_DATA_ROOT`

Default: `git rev-parse --git-common-dir` parent (principal checkout)
plus `local/factory_v1/data_plane`. No crawl, no sibling guess, no
folder-name heuristic. Non-Git without explicit/env is a typed stop.
Do not persist the physical path into durable scientific/operational
receipts. Console may show a local human path.

## Readback

Schema `smial.cohort-import-readback` / `1.0`. Fields: fingerprint,
corpus dataset id, corpus version, current manifest id, visible
cohorts (id, release_id, source/schedule hashes, lineage_count,
PRESENT_ONCE), lineage_integrity, duplicate_cohort_count, next owner
action. No scientific conclusions.

## Idempotency

Exact already-imported lineage: `PASS_ALREADY_PRESENT_EXACT`.
Identity conflict: `STOP_IDENTITY_CONFLICT`.

## Vertical acceptance

1. Principal checkout + linked worktree resolve one logical root.
2. persist=False current C1/C2: count 1 and 1, corpus_version 2.
3. Duplicate exact import does not add a second lineage.

## Semantic propagation

Primary route `SEM-LIVE-EVIDENCE-TO-FORGE`. Update search terms /
owner questions / operator navigation if the normal path changes.
`forge-control-ready` stays expert diagnostic, not obligatory owner
next.

## Rollback

Ordinary Git revert. Do not automatically destroy imported runtime data.
