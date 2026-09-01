---
task_id: LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b70cf48508d0de84bfc5b1df311b41c04ea1d6ea
  expected_upstream: origin/main
  expected_upstream_oid: b70cf48508d0de84bfc5b1df311b41c04ea1d6ea
  expected_branch: cursor/live-cohort-discovery-release-series-v1
  dirty_mode: ALLOW_REPORTED
objective: Close the scientific bridge from ObservationSchedule RDP to repeated
  immutable live lifecycle discovery releases under one stable LIVE LIFECYCLE
  DISCOVERY CORPUS with versioned manifests and HFIC current-version resolution.
managed_write_set:
- docs/tasks/LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1.md
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- scripts/discovery_evidence_release.py
- tests/test_live_cohort_discovery_release_series.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/evidence/live_cohort_discovery_release_series/a1_delivery_completion_evidence_v1.json
- docs/evidence/live_cohort_discovery_release_series/a1_delivery_independent_review_v1.json
- docs/evidence/live_cohort_discovery_release_series/a1_delivery_factory_fit_v1.json
- docs/reports/live_cohort_discovery_release_series/a1_owner_readout_v1.md
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
- STOP_FORGE_OR_EXPERIMENT
- STOP_HISTORICAL_A3_MUTATION
- STOP_SECOND_SCIENTIFIC_PLATFORM
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
    - docs/evidence/live_cohort_discovery_release_series/a1_delivery_completion_evidence_v1.json
    - docs/evidence/live_cohort_discovery_release_series/a1_delivery_independent_review_v1.json
    - docs/evidence/live_cohort_discovery_release_series/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1

## SPEC_ROUTE

`NONE` — wrap existing Discovery Evidence Release + Observation RDP + HFIC.

## Frozen cohort admission clock

**`discovery_first_reliable_available_at`** — the immutable ObservationSchedule
member admission timestamp (RDP member `first_reliable_available_at` /
`discovery_available_at`). Never cohort by later Y-outcome clocks.

Admission windows: non-overlapping **7 UTC-day** buckets on that field.

## Corpus identity

| Field | Value |
|---|---|
| logical `dataset_id` | `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001` |
| per-import `dataset_version` | `corpus-v{N}-{cohort_id}` |
| `dataset_manifest_id` | `compute_dataset_manifest_id(dataset_id, dataset_version)` |
| evidence_role | `EXPLORATORY_REUSE` |
| confirmatory_reuse_forbidden | `true` |

Historical A3 `DATASET-MANIFEST-DISCOVERY-EVIDENCE-RELEASE-001` untouched.

## Decision capsule

- **DECISION_DELTA:** Live multi-point lifecycle cohorts seal into one versioned
  corpus; HFIC resolves current version per logical dataset_id.
- **UNCERTAINTY_REMOVED:** Weekly seal/import no longer needs a new HFIC
  dataset slot each week.
- **CAPABILITY_OR_EVIDENCE:** Zero-network vertical + 12-cohort import proof.
- **STOP:** Exact merge gate. No VPS/Forge/provider.
- **NEXT:** Weekly seal/import ops can run with zero further product code
  (after live collector commissioning).
