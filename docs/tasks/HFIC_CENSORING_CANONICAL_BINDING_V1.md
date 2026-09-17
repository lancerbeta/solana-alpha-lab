---
task_id: HFIC_CENSORING_CANONICAL_BINDING_V1
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
  expected_base: dc333a29231ae0dbd13374e0c97b5c45e4a4f144
  expected_upstream: origin/main
  expected_upstream_oid: dc333a29231ae0dbd13374e0c97b5c45e4a4f144
  expected_branch: cursor/hfic-censoring-canonical-binding-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Add a fail-closed canonical LIVE CORPUS binding gate to
  CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001 so the diagnostic proves it
  is reading exactly the frozen cohort before any Block A X300 typed_value is
  consumed, without changing release schemas, parquet bytes, or the statistic.

managed_write_set:
  - docs/tasks/HFIC_CENSORING_CANONICAL_BINDING_V1.md
  - configs/hfic_censoring_ignorability_diagnostic_v1.yaml
  - src/solana_alpha_lab/factory/hfic_censoring_ignorability_diagnostic.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - scripts/hypothesis_forge.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/hfic_censoring_canonical_binding/a1_owner_readout_v1.md
  - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - CANONICAL_BINDING_INSUFFICIENT
  - RELEASE_SCHEMA_MUTATION
  - HISTORICAL_PARQUET_REWRITE
  - REAL_148_VS_327_DIAGNOSTIC_RUN
  - Y_POINT_READ
  - PROVIDER_CALL
  - DATASET_MANIFEST_ID_FROZEN_AS_IDENTITY
  - GENERIC_IDENTITY_FRAMEWORK
  - STATISTIC_OR_THRESHOLD_CHANGE
  - REAL_MONEY_OR_PROMOTION

context_requirements:
  catalog_asset_ids: []
  l2_roles: []
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
      - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_censoring_canonical_binding/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CENSORING_CANONICAL_BINDING_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=DESIGN_SPEC. Exact owner atom: canonical input binding only.

## Task Outcome Brief

- **Owner decision:** existing LIVE CORPUS lineage + DatasetManifest +
  PartitionManifest + file SHA-256 + row `release_id`/`cohort_id` are a
  complete fail-closed identity chain. Do not add parquet identity columns.
- **Product outcome:** the existing diagnostic can enter canonical X-read
  only after that gate passes against frozen
  `dataset_id`/`cohort_id`/`release_id`/`census_sha256`/`observations_sha256`.
- **Named consumer:** `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001` /
  `HFIC-SESS-560C4E1A72B4F9E6`.
- **Cheapest falsifier:** synthetic lineage/manifest/parquet fixtures proving
  bind PASS then X-read, and bind FAIL with zero Block A `typed_value` reads.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
- **Non-goals:** real 148-vs-327 run; schema/parquet rewrite; statistic change;
  freezing `dataset_manifest_id`; `release_manifest.json` runtime dependency.
- **SPEC_ROUTE=DESIGN_SPEC**

## Frozen target

- logical dataset: `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`
- cohort: `REL-20260902T111900Z-20260909T111900Z`
- release: `633a57088a5eb16dcc75a56aa2eb2521bbc76d1874aeb75aceb1ecc795bf1154`
- census SHA-256: `cfa7d8404dc5400c4e223c4d5303193ad2209f92cac3af2d61862e384ebfd5bf`
- observations SHA-256: `7b26425c69cc95baf8a9e0b9ea506de1042b98b83d48a2dae07f5a33a7d66d7d`
- consumer provenance: `HFIC-SESS-560C4E1A72B4F9E6` (spec/receipt, not parquet)

## Modes

- Canonical: resolve from LIVE CORPUS `data_root`, never active Observation RDP,
  never caller-selected parquet. Bind PASS → `CANONICAL_COMPARABLE_X_SUBSET`.
- Explicit paths: remain `SYNTHETIC_OR_NONCANONICAL_POPULATION` even if bytes
  match canonical pins. Mixed canonical+explicit invocation fails closed.

## Decision packet

- **DECISION_DELTA:** canonical scope is earned by pre-X-read lineage/manifest/hash
  binding, not by parquet `dataset_id`/`scientific_context_session` columns.
- **UNCERTAINTY_REMOVED:** whether this capability can fail-closed prove it is
  reading the frozen cohort without rewriting release bytes.
- **CAPABILITY_OR_EVIDENCE:** bind-before-X-read gate + spec pins + tests.
- **STOP:** exact-head CI + merge-readiness; no live scientific run.
- **NEXT:** separately bounded read-only canonical diagnostic run.
- **REPLAN_TRIGGER:** `CANONICAL_BINDING_INSUFFICIENT` or any need to mutate
  release schema/parquet.

## DoD

Tests 1–12 in the owner EXECUTE brief. No real 148-vs-327 diagnostic.
`dataset_manifest_id` is runtime provenance only.
