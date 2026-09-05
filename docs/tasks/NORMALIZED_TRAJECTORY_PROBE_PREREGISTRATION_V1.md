---
task_id: NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1
task_version: '1.0'
status: READY
as_of: '2026-09-05'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: a946e866370464d7980212118f8535ae963fdb1c
  expected_upstream: origin/main
  expected_upstream_oid: a946e866370464d7980212118f8535ae963fdb1c
  expected_branch: cursor/normalized-trajectory-probe-preregistration-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Freeze the first allowed Forge representation challenger NORMALIZED_TRAJECTORY_V1
  as canonical Git scientific contract before any scientific inspection of the first
  fresh lifecycle cohort. No representation code, no Forge experiment, no cohort values.

managed_write_set:
  - docs/tasks/NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1.md
  - docs/contracts/normalized_trajectory_representation_probe_v1.md
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_completion_evidence_v1.json
  - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_independent_review_v1.json
  - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_factory_fit_v1.json
  - docs/reports/normalized_trajectory_probe_preregistration/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - REPRESENTATION_PROJECTION_CODE
  - HFIC_OR_FORGE_PROTOCOL_MUTATION
  - CURRENT_LIVE_COHORT_SCIENTIFIC_CONTENT_ACCESSED
  - HYPOTHESIS_FORGE_OR_SEAL_OR_IMPORT
  - PROVIDER_API_RPC_WSS_REQUIRED
  - GENERATOR_OR_RANKER
  - NINTH_FEATURE_FAMILY
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - docs/contracts/normalized_trajectory_representation_probe_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_completion_evidence_v1.json
      - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_independent_review_v1.json
      - docs/evidence/normalized_trajectory_probe_preregistration/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1

## Entry / outcome

- `DECISION_DELTA`: first representation challenger is preregistered, not implemented
- `UNCERTAINTY_REMOVED`: post-hoc redesign of Probe 1 after seeing first-cohort paths is forbidden
- `CAPABILITY_OR_EVIDENCE`: Git contract + Catalog/semantic discoverability
- `STOP`: exact-head CI + merge-readiness; no runtime/external; no merge without owner phrase
- `NEXT`: wait for first cohort maturation; CONTROL Forge first; then maybe execute the probe

`SPEC_ROUTE=NONE`

## Non-goals

No trajectory projection, HFIC modification, new feature family, generator/ranker,
embeddings/DB/clustering/k-Shape/PELT/GP/neural sequence, provider/data changes,
`/hypothesis-forge`, seal/import, or current-cohort scientific inspection.
