---
task_id: EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-28'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3398ff19ae52d91296e6eff941878d8c5ff3f540
  expected_upstream: origin/main
  expected_upstream_oid: 3398ff19ae52d91296e6eff941878d8c5ff3f540
  expected_branch: cursor/early-icp-first-hit-mix-falsifier-v1
  dirty_mode: ALLOW_REPORTED
objective: One WRAP falsifier over the V2 capture primitives. Bounded
  quote-free density checks, first eligible>=10 search as the sole R0,
  BUY then absolute H900 SELL, immutable dataset plus unchanged
  score_frozen_mix_dataset, one scientific terminal. Zero-network PR.
managed_write_set:
- docs/tasks/EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1.md
- configs/early_icp_first_hit_mix_falsifier_v1.yaml
- configs/experiment_capability_registry_v1.yaml
- src/solana_alpha_lab/factory/early_icp_first_hit_mix_falsifier.py
- src/solana_alpha_lab/factory/capabilities.py
- scripts/run_early_icp_first_hit_mix_falsifier.py
- tests/test_early_icp_first_hit_mix_falsifier.py
- tests/test_factory_ordinary_market_hypothesis.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_independent_review_v1.json
- docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- OTHER_EXPERIMENT
- PROMOTION
- SHADOW
- TWO_RUNG
- HYPOTHESIS_FORGE_SLASH_INVOKE
- SCORE_FROZEN_MIX_DATASET_MUTATION
- SECOND_SEARCH_AFTER_R0
- SECOND_Y_WINDOW
- V2_COMPLETE_MUTATION
- FACTORY_RUNNER_BYTES_CHANGED
- WALLET_BUILD_EXECUTE_TRANSACTION
- RETRY_OR_FALLBACK
- LIVE_PROVIDER_CALL_BEFORE_MERGE
- STANDALONE_WAKE_COMMAND
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
      - docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_independent_review_v1.json
      - docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_completion_evidence_v1.json
      - docs/evidence/early_icp_first_hit_mix_falsifier/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1

## Task Outcome Brief

- **Owner decision:** implement the accepted WRAP falsifier with
  `density_check_period_seconds=60`. This PR is code and zero-network
  proof only. Live run is a separate post-merge phrase.
- **Product outcome:** one owner phrase runs density checks → first
  `select_eligible>=10` search as sole R0 → BUY → absolute H900 SELL →
  internal `CAPTURE_COMPLETE` → commit-marker dataset bundle → unchanged
  `score_frozen_mix_dataset` → one scientific terminal.
- **Named consumers:** post-merge one authorized live falsifier; HFIC
  evidence epoch via published dataset only after commit-marker.
- **Cheapest falsifier:** zero-network tests listed below.
- **Evidence budget:** this PR `provider_calls=0`. Post-merge live cap 60.
- **Non-goals:** other experiments; promotion; Shadow; TWO_RUNG;
  `/hypothesis-forge`; confirmatory second window; scorer mutation;
  standalone wake-command; Factory runner mutation; V2 COMPLETE rewrite.

## Cadence freeze

- `max_density_checks=20` and `quote_call_reserve=20` from call-cap
  arithmetic `(60-20)/2`.
- `density_check_period_seconds=60` is the owner-accepted period
  (route history only proves pace ≥3s; V2 was one empty PIT).
- `provider_pace_seconds=3`.

## DECISION_DELTA

The mix family gets a first Y-bearing falsifier that waits in-process
for supply without a second `/search` or mid-run phrase.

## UNCERTAINTY_REMOVED

Whether V2 primitives can be wrapped into one crash-safe, epoch-honest
falsifier with 20×60s checks inside cap 60.

## CAPABILITY_OR_EVIDENCE

`CAP-JUPITER-FREE-KEY-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001` wrapping
`select_eligible`, V2 quote loop, and unchanged
`score_frozen_mix_dataset`.

## STOP

Exact-head CI green. Owner merge phrase. No live provider call before
merge.

## NEXT

After merge: the exact live execution phrase with cadence=60s. Do not
auto-run.

## REPLAN_TRIGGER

Scorer change; second search after R0; V2 COMPLETE mutation; call cap
raise; background scheduler.

## Owner live phrase (post-merge only; do not execute in this PR)

See the operator block in the WRAP module / CLI help. The merge-gate
reply reprints it. This PR does not authorize the live run.
