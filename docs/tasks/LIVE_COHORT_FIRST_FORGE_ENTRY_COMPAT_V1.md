---
task_id: LIVE_COHORT_FIRST_FORGE_ENTRY_COMPAT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-11'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 8b230e036613dcc3acab274c83232ec87698a744
  expected_upstream: origin/main
  expected_upstream_oid: 8b230e036613dcc3acab274c83232ec87698a744
  expected_branch: cursor/live-cohort-first-forge-entry-compat-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair SEM-LIVE-EVIDENCE-TO-FORGE so production candidate
  discovery_available_at, mixed cumulative MEMBER_BATCH, frozen C1 identity,
  split-host import, and CONTROL-bounded packet selection reach
  FORGE_CONTROL_READY without live seal/import or /hypothesis-forge.
managed_write_set:
- docs/tasks/LIVE_COHORT_FIRST_FORGE_ENTRY_COMPAT_V1.md
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- src/solana_alpha_lab/factory/live_cohort_to_forge.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- scripts/discovery_evidence_release.py
- tests/test_live_cohort_to_forge_operational_closure_v1.py
- tests/test_live_cohort_discovery_release_series.py
- tests/test_hfic_preflight.py
- tests/test_observation_scheduler.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_completion_evidence_v1.json
- docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_independent_review_v1.json
- docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_factory_fit_v1.json
- docs/reports/live_cohort_first_forge_entry_compat/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_VPS_WRITE_DEPLOY_SEAL_IMPORT
- STOP_HYPOTHESIS_FORGE_SLASH
- STOP_RDP_REWRITE_OR_SQLITE_MUTATION
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- OWNER_DECISION_REQUIRED
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- WALLET_BUILD_EXECUTE_TRANSACTION
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
    - docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_completion_evidence_v1.json
    - docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_independent_review_v1.json
    - docs/evidence/live_cohort_first_forge_entry_compat/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_COHORT_FIRST_FORGE_ENTRY_COMPAT_V1

## SPEC_ROUTE

`NONE` — repair existing SEM-LIVE-EVIDENCE-TO-FORGE consumers/producers.

## Decision capsule

- **DECISION_DELTA:** One shared admission resolver (`discovery_available_at`
  ≡ canonical `discovery_first_reliable_available_at`); row-level mixed
  MEMBER_BATCH extraction; machine `closure_cutoff_at` freezes C1 against
  later C2; CONTROL packet selection protects LIVE CORPUS inside MAX_DATASETS.
- **UNCERTAINTY_REMOVED:** `CLOSED_RECEIPT_INCOMPLETE` from live payload keys
  is a software mismatch, not missing science. C-pure batch rejection and
  publish-time admission fallback cannot silently re-cohort.
- **CAPABILITY_OR_EVIDENCE:** Production-shaped zero-network chain to
  `FORGE_CONTROL_READY` without live VPS mutation or `/hypothesis-forge`.
- **STOP:** Exact merge gate. No deploy, no live seal/import, no slash.
- **NEXT:** Post-merge deploy of merged SHA and repeat cohort-1 acceptance.

## Non-goals

No new scientific pipeline, no estimand change, no `first_seen_at` fallback,
no RDP rewrite, no Factory redesign.
