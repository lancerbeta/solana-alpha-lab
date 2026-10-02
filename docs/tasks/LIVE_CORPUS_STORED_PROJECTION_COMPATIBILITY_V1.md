---
task_id: LIVE_CORPUS_STORED_PROJECTION_COMPATIBILITY_V1
task_version: '1.0'
status: READY
as_of: '2026-10-02'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5263abdd327455f239767c0c31855909f90435b7
  expected_upstream: origin/main
  expected_upstream_oid: 5263abdd327455f239767c0c31855909f90435b7
  expected_branch: codex/live-corpus-stored-projection-compatibility-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Preserve stored CENSUS-20/OBS-21 scientific claims while admitting current
  OBS-24 and mixed LIVE corpus through existing repair/import/read paths.
managed_write_set:
  - docs/tasks/LIVE_CORPUS_STORED_PROJECTION_COMPATIBILITY_V1.md
  - src/solana_alpha_lab/factory/live_corpus_logical_rows.py
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - tests/test_live_corpus_stored_projection_compatibility_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/live_corpus_stored_projection_compatibility_v1/owner_readout.md
  - docs/reports/live_corpus_stored_projection_compatibility_v1/semantic_premise_packet.json
  - docs/evidence/live_corpus_stored_projection_compatibility_v1/completion.json
  - docs/evidence/live_corpus_stored_projection_compatibility_v1/independent_review.json
  - docs/evidence/live_corpus_stored_projection_compatibility_v1/factory_fit.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - REAL_DATA_PLANE_MUTATION_OR_FULL_REPAIR
  - REAL_C4_OR_NEXT_COHORT_ACCESS
  - REAL_FORGE_OR_SCIENTIFIC_TRIAL_WRITE
  - PROVIDER_OR_DEPLOY
  - HISTORICAL_PARQUET_OR_SEALED_RELEASE_REWRITE
  - PIT_SCIENCE_OR_BUDGET_SEMANTICS_CHANGE
  - GENERIC_SCHEMA_OR_MIGRATION_FRAMEWORK
  - OWNER_MERGE_PHRASE_REQUIRED
context_requirements:
  catalog_asset_ids: [MODULE-LIVE-CORPUS-LOGICAL-ROWS-001, MODULE-LIVE-CORPUS-MANIFEST-PUBLISH-001]
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
      - docs/evidence/live_corpus_stored_projection_compatibility_v1/completion.json
      - docs/evidence/live_corpus_stored_projection_compatibility_v1/independent_review.json
      - docs/evidence/live_corpus_stored_projection_compatibility_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

# LIVE_CORPUS_STORED_PROJECTION_COMPATIBILITY_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE=DESIGN_SPEC.
SEMANTIC_PREMISE_HIGH_RISK: true

Owner decision: unblock historical LIVE metadata repair without changing data
or scientific meaning. Consumers: repair, append import, current selection,
Forge input binding and the actual temporal reader. Route:
SEM-LIVE-EVIDENCE-TO-FORGE. Predecessor is V2; its Git binding remains historical.

- DECISION_DELTA: the existing logical-row module owns frozen partition hash
  projections separately from the current release writer schema.
- UNCERTAINTY_REMOVED: absent historical fields cannot silently become JSON
  null keys and change old content identity after a writer extension.
- CAPABILITY_OR_EVIDENCE: physical OBS-21 RED-to-GREEN; one scratch chain
  v3 repair -> real synthetic seal/verify/import v4 -> cold mixed temporal read
  -> idempotent repair -> ordinary append v5; six real read-only claims.
- CHEAPEST_FALSIFIER: independently pinned OBS-21 fixture hash differs under
  the old current reader, then is reproduced without rewriting parquet.
- USER_VISIBLE_RESULT: existing repair/import paths accept supported mixed
  layouts and fail closed on unsupported layouts or mismatched stored claims.
- STOP: unchanged green exact-head CI and ready_for_owner_phrase=true.
- NEXT: separate OPERATE authority for real repair/verified next import/readback.
- REPLAN_TRIGGER: real data rewrite, changed PIT/science semantics, publication,
  budget or harness redesign, or inability to run the physical falsifier.
- EVIDENCE_BUDGET: focused old/new/mixed/negative tests, reused V2 crash/retry
  suite, six current real partitions read-only, four isolated critics, exact CI.
- FACTORY_FIT: FULL_REVIEW. NOW=NONE; WATCH=separate real OPERATE after merge.
- NON_GOALS: real repair/import, real C4/next cohort, real Forge/trials,
  providers/deploy, new CLI, generic migration/registry, historical backfill.

## Bounded design and acceptance

Freeze exact CENSUS-20, OBS-21 and OBS-24 field names, Arrow types and nullable
semantics in the existing logical-row owner. Match verified physical layout,
never dates/cohort IDs/column count or trial hashes. Preserve canonical row
order/normalization. Current OBS-24 with explicit null clock fields stays
OBS-24; missing old clock fields remain absent and are never inferred.
Historical reconstruction remains bound to the verified root's saved claims;
unsupported layouts/types and claim/hash/PIT mismatch STOP before publication.

The existing LIVE schema descriptor declares the supported mixed projections
and current writer separately. Its digest flows through V2 deterministic
metadata identity. No publication/lineage or market-evidence/budget redesign.
Metadata-only v3 repair preserves all scientific claims, epoch and full budget;
normal verified new composition changes version/epoch. Ordinary append retains
historical manifest-claim reuse and reconstructs only the new cohort.

The frozen historical fixture independently pins expected content hashes and
contains physically OBS-21 parquet. Synthetic current releases carry both null
and non-null clock fields. Cold subprocess checks current selection, Forge
input binding and actual temporal row/PIT/missing semantics. Negative physical
schema/type/nullable drift, altered file bytes and stored content/PIT mismatch
must not change lineage/current root. Reuse V2 fault/retry/target regressions.

Owner permits only a narrow read-only verification of six existing current
partitions. Capture bytes/mtime inventory before/after, save machine evidence
outside tracked Git and the canonical data root, never populate sidecars, copy
the corpus or read another cohort. Git evidence carries compatibility claims
and limitations, not runtime identities or actual market state.

Update the existing operator owner and Catalog/generated relations; no new
semantic route or README entrypoint. Review exact inventory independently;
architecture must attack ABSENT/NULL, mixed descriptor, temporal validity and
what can pass tests while changing history. Ordinary code revert is rollback;
never remove runtime roots or rewrite historical evidence.
