---
task_id: BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-25'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: c4846bc19947ac80363bbfd04555e8bf8655ae11
  expected_upstream: origin/main
  expected_upstream_oid: c4846bc19947ac80363bbfd04555e8bf8655ae11
  expected_branch: cursor/buy-decision-time-quote-microstructure-association
  dirty_mode: ALLOW_REPORTED
objective: Test whether decision-time BUY_T0 quote microstructure is associated with
  frozen H900 better-than-floor and worse-than-floor tails strongly enough to earn
  prospective replication, without building a selector.
managed_write_set:
- docs/tasks/BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1.md
- configs/buy_decision_time_quote_microstructure_association_v1.yaml
- src/solana_alpha_lab/buy_decision_time_quote_microstructure_association.py
- scripts/run_buy_decision_time_quote_microstructure_association.py
- tests/test_buy_decision_time_quote_microstructure_association.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_derived_capsule_v1.jsonl
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_association_input_v1.json
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_runtime_receipt_v1.json
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_completion_evidence_v1.json
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_independent_review_v1.json
- docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_factory_fit_v1.json
- docs/reports/buy_decision_time_quote_microstructure_association/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_PROVIDER_OR_NETWORK_CALL
- CREDENTIAL_OR_API_KEY_READ
- SELECTOR_OR_FEATURE_SEARCH
- COMBINED_NOT_FLOOR_TERMINAL
- ABSOLUTE_X_THRESHOLD
- W_VL_IN_PRIMARY_OR_TERMINAL_VOTE
- RAW_A4_COMMIT
- P_VALUE_THEATRE
- Y_RELABEL_OR_RECOMPUTE
- REGISTRY_OR_CONTEXT_MAP_MIGRATION
- CRYSTALLIZATION_PACKET
- USDPRICE_SECOND_NEXT
- AUTOMATIC_NEXT_ATOM
- ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
  - CTRL-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001
  - CTRL-EARLY-STRUCTURAL-BACKING-PIT-COMMISSIONING-001
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-FALSIFIER-001
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-OOS-001
  - ARCH-INTENT-005
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
    - docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_completion_evidence_v1.json
    - docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_independent_review_v1.json
    - docs/evidence/buy_decision_time_quote_microstructure_association/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

Owner clarifications patch the design-time PRD: direction is within-window
contrast only; better/worse tails are not a combined NOT_FLOOR class for the
mutex terminal; FRACTION is a working assumption; drop-window may only
downgrade; W-VL is excluded from primary and from the terminal vote.

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge.

## Atom identity

```text
DECISION_DELTA: whether BUY_T0 priceImpactPct is associated with frozen
  H900 better-than-floor and worse-than-floor tails across original windows
UNCERTAINTY_REMOVED: one mutex research terminal; no production selector
CAPABILITY_OR_EVIDENCE: Git-trackable derived capsule plus typed terminal
STOP: no live calls, no selector, no automatic NEXT
NEXT: exactly one of the five required terminals
REPLAN_TRIGGER: semantics unresolved; capsule not Git-verifiable;
  combined NOT_FLOOR used for decision; absolute X threshold
```

## Estimand (execution freeze)

Primary population: literal `BUY_T0` on W-EP, W-SB, W-HC-A, W-HC-B, W-S30.
W-VL is appendix only and cannot change the terminal.

X: decision-time BUY `priceImpactPct` after string Decimal parse. `routePlan`
count/percent are eligibility gates, not predictors.

Y: frozen Git H900 `y` copied verbatim. Tails: FLOOR / WORSE / BETTER using
`9727186 ± 20` lamports. No relabel to a profitability selector.

Direction: `median(X|family) - median(X|FLOOR)` per window. Sign of that
contrast only. Invariant to `x -> 100*x`. No absolute impact threshold.

Inference: token rows are nested in windows. Report N rows, N tokens, N
informative windows per family. Overall terminal is the weaker of the two
family terminals after drop-only-downgrade on the full eligible primary cohort.
