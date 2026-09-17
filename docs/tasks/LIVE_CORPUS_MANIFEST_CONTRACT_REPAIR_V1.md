---
task_id: LIVE_CORPUS_MANIFEST_CONTRACT_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-17'
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
  expected_base: 4ff632e0ab4f7033e728232dd39dd88638710a6e
  expected_upstream: origin/main
  expected_upstream_oid: 4ff632e0ab4f7033e728232dd39dd88638710a6e
  expected_branch: cursor/live-corpus-manifest-contract-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Repair the LIVE CORPUS metadata publication owner so the current composition
  can be republished as a TASK-06-valid DatasetManifest/PartitionManifest root
  without changing parquet or sealed release bytes, and so every future
  import_live_cohort emits TASK-06-valid cumulative metadata by construction.

managed_write_set:
  - docs/tasks/LIVE_CORPUS_MANIFEST_CONTRACT_REPAIR_V1.md
  - src/solana_alpha_lab/factory/live_corpus_logical_rows.py
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - scripts/discovery_evidence_release.py
  - tests/test_live_corpus_manifest_contract_repair_v1.py
  - tests/test_live_cohort_discovery_release_series.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/live_corpus_manifest_contract_repair/a1_owner_readout_v1.md
  - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE
  - HISTORICAL_PARQUET_REWRITE
  - SEALED_RELEASE_REWRITE
  - REAL_DATA_PLANE_MUTATION
  - TASK_06_WEAKENING
  - GENERIC_IDENTITY_FRAMEWORK
  - NEW_SCIENTIFIC_COHORT
  - PROVIDER_CALL
  - Y_POINT_READ
  - FORGE_SESSION
  - REAL_MONEY_OR_DEPLOYMENT

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/live_corpus_manifest_contract_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_CORPUS_MANIFEST_CONTRACT_REPAIR_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=DESIGN_SPEC. Exact owner atom: LIVE CORPUS metadata publication
repair only. Do not mutate real `local/factory_v1/data_plane`.

## Task Outcome Brief

- **Owner decision:** current LIVE CORPUS producer metadata is inconsistent with
  TASK-06 `dataset_manifest_contract_v1`. Repair the producer and add a
  metadata-only republish of the same scientific composition.
- **Product outcome:** fixture-proven canonical republish + future
  `import_live_cohort` emits TASK-06-valid cumulative manifests.
- **Named consumer:** `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001` (later
  OPERATE retry) and Forge current-version selection.
- **Cheapest falsifier:** tmp fixture with legacy manifests; parquet bytes
  unchanged; `verify_partition_manifest` / `verify_dataset_manifest` pass.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
- **Non-goals:** real data_plane republish; diagnostic run; parquet/release
  rewrite; TASK-06 weakening; Forge.

## Decision packet

- **DECISION_DELTA:** LIVE CORPUS metadata identity is TASK-06 builders plus a
  local census/obs logical-row profile; not `_partition_rebind_id`.
- **UNCERTAINTY_REMOVED:** whether the existing composition can obtain a
  contract-valid current root without a second market cohort.
- **CAPABILITY_OR_EVIDENCE:** repair + import path + tests 1–15.
- **STOP:** merge-readiness; no real corpus mutation.
- **NEXT:** OPERATE canonical metadata republish of current LIVE CORPUS, then
  censoring diagnostic retry.
- **REPLAN_TRIGGER:** `LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE` or any
  need to change parquet/release bytes or weaken TASK-06.
