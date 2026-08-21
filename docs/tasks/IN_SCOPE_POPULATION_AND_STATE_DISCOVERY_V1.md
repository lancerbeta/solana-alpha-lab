---
task_id: IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-21'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 352197124d49c805a749b5a90bb48dc3dccae0df
  expected_upstream: origin/main
  expected_upstream_oid: 352197124d49c805a749b5a90bb48dc3dccae0df
  expected_branch: cursor/in-scope-population-supply-gate
  dirty_mode: ALLOW_REPORTED
objective: Decision-bearing Stage A supply gate for the frozen EARLY/SEASONED contract. Offline-prove that a memo-literal instant 3-call cannot fill EARLY, freeze wait-then-search harvest, and stop before quotes, X, or live provider calls.
managed_write_set:
  - docs/tasks/IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1.md
  - configs/in_scope_population_and_state_discovery_v1.yaml
  - src/solana_alpha_lab/in_scope_population_supply_gate.py
  - scripts/run_in_scope_population_supply_gate.py
  - tests/test_in_scope_population_supply_gate.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/in_scope_population_and_state_discovery/a1_runtime_receipt_v1.json
  - docs/evidence/in_scope_population_and_state_discovery/a1_acceptance_v1.json
  - docs/evidence/in_scope_population_and_state_discovery/a1_delivery_completion_evidence_v1.json
  - docs/evidence/in_scope_population_and_state_discovery/a1_delivery_independent_review_v1.json
  - docs/evidence/in_scope_population_and_state_discovery/a1_delivery_factory_fit_v1.json
  - docs/reports/in_scope_population_and_state_discovery/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_OR_NETWORK_CALL
  - CREDENTIAL_OR_API_KEY_READ
  - FACTORY_RUNNER_CHANGE
  - QUOTE_OR_H900_IN_THIS_WRITE_SET
  - FOURTH_X_OR_FEATURE_TOURNAMENT
  - TRADED_ACCEPTED_AS_PRODUCT_POPULATION
  - UNKNOWN_AS_ZERO
  - LIVE_CAPTURE_WITHOUT_EXACT_OWNER_PHRASE
  - STAGE_B_STATE_RULES_IN_THIS_WRITE_SET
  - ALPHA_OR_NETRETURN
  - WALLET_SIGNER_TX_OR_CASH
  - ARCHITECTURE_INTENT_OR_ROADMAP
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-IN-SCOPE-POPULATION-FIT-RECONCILIATION-ACCEPTANCE-001
    - EVIDENCE-IN-SCOPE-POPULATION-FIT-RECONCILIATION-RUNTIME-001
    - EVIDENCE-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/in_scope_population_and_state_discovery/a1_runtime_receipt_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_acceptance_v1.json
      - docs/evidence/in_scope_population_fit_reconciliation/a1_runtime_receipt_v1.json
      - docs/evidence/ordinary_recent_early_path_h900_audition/a1_ordinary_recent_early_path_h900_audition_runtime_receipt_v1.json
    HISTORICAL_CONTEXT: []
---

# IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ADOPTION_ROUTE=WRAP_ATOM1_BOUNDS_AND_EARLY_PATH_WAIT_BUILD_OFFLINE_SUPPLY_GATE`

Owner direction: `muv-4.md` ATOM 2. This Git contract is Stage A only.

## Entry patches against live Git

1. Memo-literal instant 3-call (`/recent` + `/toptraded/1h` + bulk search) cannot
   fill product EARLY. Named quote-native `/recent` cells are ultra-fresh
   (~16–69s). Age alone already yields `EARLY_n=0`.
2. Early-path already showed the working harvest for EARLY: wait until pool age
   `>=5m`, then one bulk Tokens V2 search. This atom freezes that harvest. It
   does not rerun the campaign.
3. Product SEASONED may include a `/toptraded` mint after search reclassify
   (source ≠ population). The whole TRADED stratum is still not the product.
   Git `/toptraded` samples have launchpad unknown, so they do not count as
   product SEASONED.
4. Quotes, H900, and the three state X are **out of this write set**. Documenting
   them before a harvest that Git already falsifies is the 2-hour/5-second
   failure the memo wanted to avoid.
5. Live 3-call+wait is `OWNER_DECISION` (credentialed Jupiter). This atom stops
   before any provider call.

## Decision capsule

- `DECISION_DELTA:` Do not live-run the memo-literal instant 3-call. Harvest is
  wait-then-search for EARLY plus search-reclassify of `/toptraded` for SEASONED.
  Stage B (quotes/X) waits for a later write set after live supply PASS.
- `UNCERTAINTY_REMOVED:` whether frozen `[5m,15m)` / `[30m,120m]` can be filled
  from an instant `/recent` snapshot (no).
- `CAPABILITY_OR_EVIDENCE:` offline supply-gate projector over hash-pinned Git
  receipts. Live capture not executed.
- `STOP:` after the offline packet and exact-head CI. No provider. No Stage B.
- `NEXT:` live Stage A only after the exact owner phrase. Stage B only after
  live `SUPPLY_GATE_PASS` (12+12 pump.fun, liq `>=1000`).
- `CHEAPEST_FALSIFIER:` instant `/recent` age band is not ULTRA_FRESH, or
  product membership uses source stratum instead of launchpad+age+liq.
- `REPLAN_TRIGGER:` live capture in this write set; quotes/X documented as if
  harvest were proven; TRADED-as-product; fourth X.
- `strongest_rejected_alternative:` implement the full 51-call campaign now.
  Rejected: Git already shows instant EARLY supply is empty; Stage B would be
  ceremony around a 3-call fail.

## PRD

**Problem.** ATOM 1 froze in-scope EARLY/SEASONED. The memo's ATOM 2 wants one
fresh campaign: 12+12 then quotes then max 3 X. Instant `/recent` is not EARLY.

**Owner decision unlocked.** Exactly one of:

`INSTANT_RECENT_CANNOT_FILL_EARLY`
`INSUFFICIENT_IN_SCOPE_POPULATION_SUPPLY`
`SUPPLY_GATE_PASS`
`LIVE_CAPTURE_BLOCKED_NO_OWNER_PHRASE`

This write set can reach the first and the last. `SUPPLY_GATE_PASS` needs live
search fields.

**Named consumer.** Live Stage A (same task id, new write set) or STOP of the
population branch if harvest cannot be patched.

**Question.** Can the frozen bands be populated from a memo-literal instant
3-call on named Git evidence?

**Unit of replication.** Campaign snapshot, not pooled tokens.

**Exact evidence set.** ATOM 1 acceptance/runtime (frozen bounds + instant
band counts) and the early-path runtime (wait harvest ages). No recency search.

**Success.** Instant `/recent` product EARLY `n=0`; harvest patch recorded;
Factory runner unchanged; zero provider calls.

**Non-goals.** Quotes, H900, X1–X3, ATOM 3, Factory runner, live Jupiter,
alpha/NetReturn.

## SSD

**Baseline.** `origin/main` `352197124d49c805a749b5a90bb48dc3dccae0df`.

**Design.** Thin offline projector. Public `population_band` from ATOM 1.
Product membership = `launchpad==pump.fun` AND age band AND `liquidity>=1000`
AND mint not consumed. Source labels stored separately.

**Invariants.** No `solana_alpha_lab.*` private `_` imports. No network. Missing
launchpad/age/liquidity is not a pass.

**Rollback.** Revert this branch. Preserve ATOM 1 freeze and Factory runner.

**DoD.** Tests lock instant-EARLY empty, wait-ages in EARLY band, TRADED without
launchpad excluded, 12+12 synthetic PASS, runner SHA pin.
