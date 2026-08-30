---
task_id: INCREMENTAL_HARNESS_SYNC_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-30'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0b594f5479960d22d22b69098da649ee85e79881
  expected_upstream: origin/main
  expected_upstream_oid: 0b594f5479960d22d22b69098da649ee85e79881
  expected_branch: cursor/incremental-harness-sync-v1
  dirty_mode: ALLOW_REPORTED
objective: "Make routine harness_sync apply incremental and byte-equivalent to full reconciliation. Bare --apply stays the explicit full oracle. Zero provider calls."
managed_write_set:
- docs/tasks/INCREMENTAL_HARNESS_SYNC_V1.md
- scripts/harness_sync.py
- tests/test_harness_sync.py
- docs/agent/DELIVERY_HARNESS_PROTOCOL.md
- scripts/ci_fail_closed_messages.py
- tests/test_ci_messages.py
- delivery-harness/harness.yaml
- docs/evidence/control/delivery_harness_acceptance_v1.json
- docs/evidence/incremental_harness_sync/a1_delivery_completion_evidence_v1.json
- docs/evidence/incremental_harness_sync/a1_delivery_independent_review_v1.json
- docs/evidence/incremental_harness_sync/a1_delivery_factory_fit_v1.json
- docs/evidence/incremental_harness_sync/a1_benchmark_receipt_v1.json
- docs/reports/incremental_harness_sync/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PRIMARY_FILE_MUTATION
- SILENT_STALE_DERIVED_TRUTH
- INCREMENTAL_FULL_EQUIVALENCE_FAILED
- NEW_CACHE_TRUTH_OWNER
- SECRET_IN_RECEIPTS
- PROVIDER_OR_CREDENTIAL_USE
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/incremental_harness_sync/a1_delivery_completion_evidence_v1.json
    - docs/evidence/incremental_harness_sync/a1_delivery_independent_review_v1.json
    - docs/evidence/incremental_harness_sync/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# INCREMENTAL_HARNESS_SYNC_V1

`SPEC_ROUTE=BOTH` from owner PRD/SSD
`c:\Users\lance\Desktop\Backlog\PRD_SSD_INCREMENTAL_HARNESS_SYNC_V1.md`
(authoring copy). This Git contract is the execution authority. Base rebound
from authoring `b5ae41ee` to exact `main`
`0b594f5479960d22d22b69098da649ee85e79881` after PR #220.

## Decision capsule

- `DECISION_DELTA`: routine derived sync hashes only the candidate-impacted
  sha256 assets and skips navigation when Catalog semantics did not change.
- `UNCERTAINTY_REMOVED`: whether a small source delta can be proven
  byte-equivalent to full apply without a 13-minute full Catalog walk.
- `CAPABILITY_OR_EVIDENCE`: `--apply --base-ref <40hex>` incremental path;
  `--apply` / `--apply --full` remain the explicit full oracle.
- `STOP`: after exact-head CI, merge phrase, guarded merge, main read-back.
- `NEXT`: Factory / Hypothesis Forge / evidence acquisition. No extra
  control-plane optimization atom.

## Modes

- Routine FINISH: `scripts/harness_sync.py --apply --base-ref <expected_base>`
- Full oracle / recovery: `scripts/harness_sync.py --apply` or `--apply --full`
- Ambiguous candidate inventory: `FULL_FALLBACK`, never silent skip

## Non-goals

No hash-binding removal, no persistent cache/daemon/remote cache, no
`validate_baseline.py` rewrite, no product/science mutation, no extra owner
micro-step, no wall-clock assertion in CI.

## DoD

1. Candidate inventory vs exact base includes committed, staged, unstaged,
   untracked, deletions.
2. Unaffected assets are not hashed.
3. Integrity-only registry churn does not trigger navigation.
4. Semantic registry/add/remove/move and generator edits do.
5. Incremental tracked derived bytes == full oracle.
6. Ambiguity falls back to full.
7. Protocol/FINISH uses the incremental command.
8. Owner-machine benchmark ≥5× vs measured full baseline; timing lives in
   the benchmark receipt, not CI.
