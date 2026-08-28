---
task_id: EARLY_ICP_RETAINED_COHORT_MATURITY_CORRECTIVE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-28'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3650b817c42178117c4c497b6ea64f56f5838c1d
  expected_upstream: origin/main
  expected_upstream_oid: 3650b817c42178117c4c497b6ea64f56f5838c1d
  expected_branch: cursor/early-icp-retained-cohort-maturity-corrective-v1
  dirty_mode: ALLOW_REPORTED
objective: In-place corrective of EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1.
  Crash-safe retained candidate pool across the existing 20x60s checks;
  /search from that pool, not only current /recent; R0 only when
  valid_mix_eligible >=10. Frozen ICP/X/Y/age-band, scorer and Factory
  runner unchanged. Zero-network PR. No live provider call before merge.
managed_write_set:
- docs/tasks/EARLY_ICP_RETAINED_COHORT_MATURITY_CORRECTIVE_V1.md
- configs/early_icp_first_hit_mix_falsifier_v1.yaml
- src/solana_alpha_lab/factory/early_icp_first_hit_mix_falsifier.py
- scripts/run_early_icp_first_hit_mix_falsifier.py
- tests/test_early_icp_first_hit_mix_falsifier.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_independent_review_v1.json
- docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- OTHER_EXPERIMENT
- NEW_HYPOTHESIS
- NEW_Y_WINDOW
- NEW_PROVIDER
- PROMOTION
- SHADOW
- TWO_RUNG
- HYPOTHESIS_FORGE_SLASH_INVOKE
- SCORE_FROZEN_MIX_DATASET_MUTATION
- SECOND_SEARCH_AFTER_R0
- V2_COMPLETE_MUTATION
- PRIOR_SLEEP_ARTIFACT_REWRITE
- FACTORY_RUNNER_BYTES_CHANGED
- WALLET_BUILD_EXECUTE_TRANSACTION
- RETRY_OR_FALLBACK
- LIVE_PROVIDER_CALL_BEFORE_MERGE
- DECLARATIVE_BRIDGE
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_independent_review_v1.json
      - docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_completion_evidence_v1.json
      - docs/evidence/early_icp_retained_cohort_maturity_corrective/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_ICP_RETAINED_COHORT_MATURITY_CORRECTIVE_V1

## Task Outcome Brief

- **Owner decision:** fix `RECENT_ONLY_COHORT_RETENTION_GAP` in place
  inside the existing first-hit WRAP. Not a new hypothesis, Y-window,
  provider, scorer, X, Y, R1, trading, Shadow, TWO_RUNG or Forge.
- **Product outcome:** each `/recent` ingests pump.fun mints into a
  journaled retained pool; each check searches that pool (max 100,
  Y-blind); R0 opens only at `valid_mix_eligible >= 10`; quotes only
  those rows; structural invalid-X kept typed; unchanged H900 lifecycle
  and `score_frozen_mix_dataset`.
- **Named consumers:** post-merge one new exact production phrase;
  live-run is owner-executed, not this PR.
- **Cheapest falsifier:** zero-network tests in this contract.
- **Evidence budget:** this PR `provider_calls=0`. Post-merge live cap 60.
- **Non-goals:** declarative bridge; new source; paid provider; new
  scorer; new X/Y; R1; trading; Shadow; TWO_RUNG; `/hypothesis-forge`.

## ROOT_CAUSE

`RECENT_ONLY_COHORT_RETENTION_GAP`. Age gate `[300,600)` is correct;
the sampling frame is not. `/recent` returns enough pump.fun mints and
mix fields, but only at age `<300s`. The runner built `/search` from the
current `/recent` only and forgot prior mints before they entered the
frozen age-band. This is not a reason to lower the age gate, buy a
provider, replay the last SLEEP run, or build a declarative bridge.

## DECISION_DELTA

Keep the scientific population. Journal seen mints between the existing
20x60s checks and re-search them after they mature. First check sees
young mint; about five checks later the same mint can enter a real R0.
If valid_mix still stays below 10, that is an honest supply/quality miss,
not the runner wiping its own queue. Call cap stays 60.

## UNCERTAINTY_REMOVED

Whether R0 can open from a crash-safe retained cohort while keeping
call budgets, frozen ICP/X/Y and the existing scorer byte-identical.

## CAPABILITY_OR_EVIDENCE

In-place WRAP of `CAP-JUPITER-FREE-KEY-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001`.
No new capability id.

## STOP

Exact-head CI green. Isolated code + Goal/DoD + architecture review.
Owner merge phrase. No live provider call before merge.

## NEXT

After merge: reprint one new exact production phrase. Do not auto-run.
Do not open a follow-up PR from SLEEP.

## REPLAN_TRIGGER

Scorer change; second search after R0; V2 COMPLETE or prior SLEEP rewrite;
call cap raise; paid provider; new Y-window.
