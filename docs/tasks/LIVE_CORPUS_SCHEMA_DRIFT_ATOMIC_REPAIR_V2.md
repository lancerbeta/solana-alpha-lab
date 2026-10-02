---
task_id: LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2
task_version: '1.0'
status: READY
as_of: '2026-10-02'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CODEX_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b24ec87f5308377fe7d5543f5db690d9fe8c2532
  expected_upstream: origin/main
  expected_upstream_oid: b24ec87f5308377fe7d5543f5db690d9fe8c2532
  expected_branch: codex/live-corpus-schema-drift-atomic-repair-v2
  dirty_mode: ALLOW_REPORTED
objective: >-
  Repair already-canonical LIVE corpus schema drift with deterministic metadata
  identity and one lineage visibility transition, production current consumers,
  safe retry and unchanged scientific market/budget semantics. Scratch only.
managed_write_set:
  - docs/tasks/LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2.md
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - scripts/discovery_evidence_release.py
  - tests/test_live_corpus_schema_drift_atomic_repair_v2.py
  - tests/test_live_corpus_manifest_contract_repair_v1.py
  - tests/test_hfic_market_evidence_epoch_decision_basis_v2.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - tests/test_hfic_censoring_ignorability_diagnostic_v1.py
  - tests/test_live_cohort_discovery_release_series.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/live_corpus_schema_drift_atomic_repair_v2/owner_readout.md
  - docs/reports/live_corpus_schema_drift_atomic_repair_v2/semantic_premise_packet.json
  - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/completion.json
  - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/independent_review.json
  - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/factory_fit.json
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
  - REAL_DATA_PLANE_ACCESS
  - REAL_C4_ACCESS_OR_IMPORT
  - FORGE_RUN
  - PROVIDER_OR_DEPLOY
  - PARQUET_OR_SEALED_RELEASE_REWRITE
  - MARKET_EVIDENCE_BASIS_V2_REDESIGN
  - GENERIC_IDENTITY_OR_TRANSACTION_FRAMEWORK
  - OWNER_MERGE_PHRASE_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
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
      - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/completion.json
      - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/independent_review.json
      - docs/evidence/live_corpus_schema_drift_atomic_repair_v2/factory_fit.json
    HISTORICAL_CONTEXT: []
---

# LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2

ENTRY_DECISION: START_WITH_PATCH. SPEC_ROUTE=DESIGN_SPEC.
SEMANTIC_PREMISE_HIGH_RISK: true

## Outcome and authority

Owner loop: unchanged C1-C3 composition -> metadata repair -> later verified
cohort import -> canonical readback -> STOP_BEFORE_FORGE.
Semantic route: SEM-LIVE-EVIDENCE-TO-FORGE. Reuse V1 production owners and
TASK-06 identity builders; the predecessor task's frozen Git binding is history.
Named consumers: current LIVE import/readback, Forge input receipt and market
evidence/budget selection. Cheapest falsifier: real scratch imports produce v3
under schema A, then schema B repair must change metadata identity without
changing corpus version, market epoch or consumed AUTO/distinct-focus slots.

- DECISION_DELTA: lineage.current_dataset_manifest_id is the sole current LIVE
  root authority; is_current_corpus_version is a derived cache.
- UNCERTAINTY_REMOVED: schema drift, interrupted preparation or stale labels
  cannot partially change current scientific evidence or require manual recovery.
- CAPABILITY_OR_EVIDENCE: scratch incident, crash/retry/current-consumer,
  synthetic fourth import and existing operator CLI verticals.
- STOP: exact-head CI PASS and ready_for_owner_phrase=true. No merge in this
  continuation; return the newly bound exact owner phrase.
- NEXT: OPERATE C1-C3 repair -> exact C4 import -> canonical readback -> STOP_BEFORE_FORGE.
- REPLAN_TRIGGER: V2 identity redesign, unrelated DatasetManifest redesign,
  new durable transaction infrastructure, real historical migration or an
  unresolved owner decision. Repeated same-class blocker requires replan.
- Evidence budget: focused production-shaped fixtures and direct-consumer
  tests, four isolated critics, existing exact-head PR CI. No local full gate.
- Non-goals: real data-plane access/repair, C4, Forge, provider/VPS/deploy,
  new CLI, registry, lock manager, estimand change or generic framework.
- Factory Fit: FULL_REVIEW. Capability radar NOW=NONE; WATCH=real repair/import
  only after separate owner OPERATE authority.

## Bounded design

OLD_CURRENT -> CANDIDATE_PREPARED -> CANDIDATE_VERIFIED -> NEW_CURRENT.
Use a LIVE-local deterministic metadata-contract digest in dataset_version;
TASK-06 remains the dataset/partition identity algorithm. No clock/random/retry
number in root identity. Composition and effective schema contract bind it;
same composition and contract converge on the same repaired root.
The explicit LIVE metadata projection binds schema identity, logical row profile,
receipt schema/version, publication commit/clock policy, required static labels
and repair generation constants. Repair generation_run_id is target-derived;
candidate labels and receipt do not contain the transition predecessor. Lineage
and result readback retain that transition truth. A partial B interrupted after
receipt/dataset construction, followed by successful C and then B, must reuse
the same B identity and immutable bytes without manual deletion or restore.

Capture old lineage and current root without writes. Reconstruct logical rows
and verify immutable parquet/release composition before preparing replacement.
Candidate metadata has current=false. Never retract or overwrite the old root.
Verify candidate independently of current pointer: TASK-06 manifests, receipt,
marker/clock/labels, cohort/release/content/PIT/availability/version/paths/hash
equality and complete publication. The only visibility commit is atomic replace
of lineage.json. Reconcile derived labels after that commit; stale flags must
not affect current selection, scientific epoch or retry correctness.

Existing repair-live-corpus-manifests retries compatible partial preparation,
verifies/reuses complete candidates, rejects conflicting immutable bytes, and
reconciles current derived flags on IDEMPOTENT_REPAIR. Invalid new current roots
STOP without rollback or historical regeneration. No integrity retry loop.
Metadata-only repair preserves MARKET_EVIDENCE_BASIS_V2 epoch and all historical
occupancy. No ResearchStore writes. A real synthetic next cohort may change
composition, corpus version and epoch through the actual import path.

## Acceptance and independent review

Tests cover already-canonical schema drift/idempotence, faults during labels,
partition/root publication, before/after lineage switch and cleanup; stale-label
adversaries across all actual current consumers; parquet drift, impossible
logical reconstruction, conflicting candidate, safe retry and real synthetic
fourth import (v4, four cohorts once, duplicate zero), and existing CLI terminals.
Historical roots, parquet and sealed fixture releases remain immutable.
Current-root integrity stays strict for legacy synthetic LIVE fixtures: update
their publication to canonical TASK-06 manifests, full receipt/clock/marker.
Partition verification compares exact models in canonical partition-id order;
overlapping campaigns imported in another order retain their composition order.

Architecture answers: second current owners; before/after pointer crashes;
stale-label consumers; metadata-only new budgets; conflicting-byte overwrite;
actual next import; tests passing yet failed repair mutates current; and any
hidden manual recovery requirement. Owner UX checks month-later Git+CLI recovery.
Catalog uses current routes/relations and generated tooling; no redundant routes.
Rollback: ordinary code revert, never erase runtime history or candidate roots.
