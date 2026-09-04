---
task_id: FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 52be82091af859171de2c062b1a08e05f5eb325e
  expected_upstream: origin/main
  expected_upstream_oid: 52be82091af859171de2c062b1a08e05f5eb325e
  expected_branch: cursor/factory-97d-storage-architecture-proof-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Research and design a lossless 97-day local residency architecture so the
  Factory stays operable on the current ~100 GiB-class VPS: latest 90 days of
  all material RAW + transformed scientific data locally, weekly age-based
  eviction, TARGET <=40 GiB and HARD <=50 GiB inclusive of same-volume data
  footprint, cold history on the existing Google Drive route. Produce one
  PRD+SSD and owner readout. Do not implement the architecture in this atom.

managed_write_set:
  - docs/tasks/FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1.md
  - docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md
  - docs/reports/factory_97d_storage_architecture_proof_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_live_byte_forensics_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_structural_97d_model_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_format_benchmark_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_adopt_wrap_decision_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_factory_fit_v1.json
  - tests/test_factory_97d_storage_architecture_proof_v1.py
  - tests/test_factory_97d_storage_format_benchmark_v1.py
  - configs/ci_test_shards_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json

external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - PRODUCTION_CODE_IMPLEMENTATION_OF_ARCHITECTURE
  - RETENTION_APPLY_OR_VACUUM
  - GOOGLE_DRIVE_WRITE
  - LOCAL_FACTORY_DATA_DELETE
  - CREDENTIAL_VALUE_READ
  - CAPTURE_OR_SAMPLING_CHANGE
  - NEW_CLOUD_PROVIDER_OR_OBJECT_STORE
  - NEW_TABLE_PLATFORM_WITHOUT_MEASURED_NECESSITY
  - PACKAGE_ADOPTION_REQUIRED
  - SECOND_ARCHITECTURE_PIVOT
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
    - ARCHITECTURE_DECISIONS
    - LIFECYCLE
    - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE:
      - docs/operator/FACTORY_REMOTE_HOST.md
      - docs/operator/factory_remote_host_v1.yaml
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - configs/factory_remote_operations_v1_1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_97d_storage_architecture_proof_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Decision delta

Can the Factory keep 90 days of all material RAW + transformed scientific
evidence locally on the current ~100 GiB VPS, with weekly eviction (97-day
capacity horizon), TARGET <=40 GiB and HARD <=50 GiB inclusive of same-volume
data footprint, without a capture-policy change — and which standard
ADOPT/WRAP architecture should the next implementation atom build?

## Binding

- Base: `52be82091af859171de2c062b1a08e05f5eb325e`
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `BOTH`
- Entry: `START_AS_WRITTEN`
- `MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`

Predecessor `FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1` answered
"change topology/retention/resolution *now*?" with
`NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED` under the then-current 31d operational
raw + immutable RDP contracts. This atom is a **new owner product requirement**:
90-day local residency of all material RAW + science, 40/50 GiB data budget.
It does not silently rewrite that predecessor terminal.

## Named consumer

Owner and the next implementation atom, deciding the storage architecture
before any production mutation, retention APPLY, Drive write, or eviction.

## Cheapest falsifier

- Live byte attribution cannot reconcile Factory data-related disk usage.
- A design "passes" 40/50 GiB only by excluding same-volume backup/staging.
- Lossless compression/batching/dedup is claimed without a real-corpus
  benchmark that preserves semantic equality.
- Scientific identity/reproducibility after local eviction is unspecified.
- Remote verification is size-only.
- Eviction age uses filesystem mtime.
- Architecture implementation, deploy, retention APPLY, Drive write, local
  Factory-data delete, credential-value read, or capture change occurs in
  this atom.

## Non-goals

No production-code implementation of the final architecture. No deploy. No
retention APPLY. No Google Drive write. No local Factory-data delete. No
credential-value read. No capture/sampling change. No Kafka/Redis/MinIO/
PostgreSQL/Iceberg/Delta/Hudi/new cloud provider merely because they exist.

## Terminals

Exactly one, this atom:

`STORAGE_97D_ARCHITECTURE_READY`

Typical 97d selected footprint passes TARGET 40 GiB and HARD 50 GiB.
Conservative measured stress passes HARD and misses TARGET, so
`STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN` is not selected.
`STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE` is not selected.
Historical `HOST_UNREACHABLE` remains in evidence and does not stay the
capacity terminal.

Defined but not this atom's terminal:

- `STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN`
- `STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE`
- `STORAGE_ARCHITECTURE_BLOCKED`

## STOP / NEXT

STOP after the research/design PR and owner readout. No architecture
implementation. No merge from this handoff until exact-head CI and owner
phrase. NEXT is `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` after this
research PR merges. Destructive eviction remains a later gate.
