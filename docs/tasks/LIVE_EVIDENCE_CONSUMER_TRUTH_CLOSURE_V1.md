---
task_id: LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 669745ec8de59c6db4aa04418af845253872bfde
  expected_upstream: origin/main
  expected_upstream_oid: 669745ec8de59c6db4aa04418af845253872bfde
  expected_branch: cursor/live-evidence-consumer-truth-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Close the scientific consumer path from immutable Observation RDP to
  campaign-aligned live cohort release and cumulative LIVE LIFECYCLE CORPUS
  current version without pausing C4 or calling providers.
managed_write_set:
- docs/tasks/LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_V1.md
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- scripts/discovery_evidence_release.py
- tests/test_live_cohort_discovery_release_series.py
- tests/test_live_evidence_consumer_truth_closure.py
- tests/test_collector_operability_retention_and_owner_pulse.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_independent_review_v1.json
- docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_factory_fit_v1.json
- docs/reports/live_evidence_consumer_truth_closure/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
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
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_AUTHORIZE_OR_ACTIVATE
- STOP_C4_COLLECTOR_MUTATION
- STOP_FORGE_OR_LIVE_SEAL
- STOP_HISTORICAL_A3_MUTATION
- LIVE_SOURCE_LINEAGE_CONFLICT
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- WALLET_BUILD_EXECUTE_TRANSACTION
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
    - docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/live_evidence_consumer_truth_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_V1

## SPEC_ROUTE

`NONE` — close gaps on existing live cohort / Observation RDP / HFIC path.

## DECISION_DELTA

1. Real immutable Observation RDP → deterministic live source adapter (no SQLite).
2. Campaign-relative 3×7d cohort windows from schedule activation clock.
3. Cumulative LIVE CORPUS current version exposes all accepted cohort rows.

## NON-GOALS

No C4 pause/deploy/authorize/activate/provider calls; no live Forge seal; no Drive.

## DONE

`LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_READY_FOR_MERGE` with proof:

```text
REAL_RDP_TO_LIVE_SOURCE = PASS
SQLITE_REQUIRED = false
C4_COHORT_WINDOWS = CAMPAIGN_RELATIVE_3X7_PASS
CURRENT_CORPUS_CUMULATIVE_ROWS = PASS
LATEST_ONLY_FALSE_POSITIVE = KILLED
12_COHORT_CURRENT_VIEW = ALL_12_PRESENT
FORGE_CURRENT_DATASET_COUNT = 1
PARQUET_HISTORY_DUPLICATION = NO
HISTORICAL_VERSIONS_IMMUTABLE = PASS
CONFIRMATORY_REUSE_FORBIDDEN = true
PROVIDER_CALLS = 0
CREDENTIAL_READS = 0
VPS_MUTATIONS = 0
```
