---
task_id: RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9e00d9543224d34a2aa935196694f5afd614f37c
  expected_upstream: origin/main
  expected_upstream_oid: 9e00d9543224d34a2aa935196694f5afd614f37c
  expected_branch: cursor/rc001-h13-park-from-priority
  dirty_mode: ALLOW_REPORTED
objective: Offline-bind the explicit owner selection to park RC001-H13-COMPOSITE-VETO from factory priority, retain TASK-24/TASK-28 science, and state that no RC001 family is eligible to start without a new exact contract.
managed_write_set:
  - docs/tasks/RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1.md
  - src/solana_alpha_lab/rc001_h13_park_from_priority.py
  - tests/test_rc001_h13_park_from_priority.py
  - scripts/run_rc001_h13_park_from_priority.py
  - docs/evidence/rc001_h13_park_from_priority/a1_h13_park_from_priority_acceptance_v1.json
  - docs/reports/rc001_h13_park_from_priority/a1_owner_readout_v1.md
  - docs/evidence/rc001_h13_park_from_priority/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc001_h13_park_from_priority/a1_delivery_independent_review_v1.json
  - docs/evidence/rc001_h13_park_from_priority/a1_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - tests/test_lifecycle_registries.py
  - tests/test_catalog.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - TASK24_STOP_RECEIPT_DRIFT
  - TASK28_RC001_FREEZE_DRIFT_OR_MUTATION
  - H07_H01_PARK_RECEIPT_DRIFT
  - H13_BLOCKER_SET_DRIFT
  - H02_STATE_DRIFT
  - H13_OR_H02_TRIAL_STARTED
  - ENTITY_ROUTE_REDESIGN_OR_CAPTURE_STARTED
  - CONTINUOUS_PIT_OR_EXECUTION_CAPTURE_STARTED
  - H07_H01_UNPARKED
  - PROVIDER_OR_CREDENTIAL_CALL_REQUIRED
  - CASH_OR_WALLET_OR_SIGNER_ACTION
  - HYPOTHESIS_NEGATIVE_OR_POSITIVE_INFERENCE
  - RC001_PROMOTION_OR_CANONICAL_DONE_CLAIM
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T24-A6-STOP-DECISION-001
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T28-A1-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T30-A27-H07-H01-LIQUIDITY-RETENTION-PARK-001
    - REGISTRY-GLOBAL-TRIAL-LEDGER-001
  l2_roles: [DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE:
      - registries/global_trial_ledger.yaml
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task24/a6_bounded_data_redesign_or_stop_decision_v1.json
      - docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json
      - docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1

The owner selected `PARK_H13_FROM_PRIORITY` in the current delivery thread.
Apply that selection only as an offline priority disposition for
`RC001-H13-COMPOSITE-VETO`. Retain the TASK-24 stopped entity-route evidence,
the TASK-28 frozen definition, and the prior H07/H01 park evidence. This does
not alter a hypothesis definition, blocker, trial record, or research
conclusion.

## Task Outcome Brief

- **Owner decision:** remove H13 from active factory priority because the frozen
  group has the unrepaired `ENTITY_ROUTE_NOT_ADMISSIBLE`,
  `CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE`, and
  `SETTLED_EXECUTION_TRUTH_UNAVAILABLE` blockers.
- **Product outcome:** a hash-bound, fail-closed record that H13 is parked and
  science is retained. H02/H10/H14 remains `BLOCKED_DATA`; this atom selects
  no next RC001 family and starts none automatically.
- **Named consumers:** `RC001-H13-COMPOSITE-VETO` and the goal owner.
- **Cheapest falsifier:** any drift in the TASK-24 stop receipt, TASK-28 H13
  definition/blocker set, H07/H01 park receipt, or frozen H02 state; any
  interpretation of park as a hypothesis verdict or a trial.
- **Terminal outcomes:** `H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED` or
  `H13_PARK_PREREQUISITES_DRIFT`.
- **User-visible result:** Russian readout naming what was parked, retained
  science, exact return condition, and why H02 is not auto-started.
- **Evidence budget:** tracked Git bytes and targeted local tests only; zero
  provider, credential, network, wallet, cash, or execution side effects.
- **Non-goals:** RC001 freeze mutation; H13/H02 trial; entity-route redesign;
  PIT/quote/execution capture; H07/H01 unpark; hypothesis
  support/refutation; alpha; NetReturn; cashflow; canonical DONE.
- **Replan trigger:** any frozen input drifts; a second route/provider pivot is
  proposed; or a new exact task contract authorizes a return condition.

## Decision capsule

- `DECISION_DELTA`: H13 leaves the live priority queue. Park is not a
  hypothesis verdict, a data-admissibility repair, or a task-state promotion.
- `UNCERTAINTY_REMOVED`: whether the owner wants to spend the next factory
  priority on H13 despite its three frozen blockers. The owner chose park.
- `CAPABILITY_OR_EVIDENCE`: a fail-closed binder over TASK-24, TASK-28, and
  the H07/H01 park; an append-only lifecycle decision; and a readable owner
  outcome. No data collection, decoder, route, provider, or trial.
- `STOP`: no external side effects, no RC001 mutation, no H13/H02 start, and
  no semantic conclusion beyond the priority disposition.
- `NEXT`: after exact-head CI, stop for the repository merge phrase. After
  merge, do not auto-start H02/H10/H14; a new exact contract must first
  address its still-live `BLOCKED_DATA` requirements.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `ADOPTION_ROUTE=WRAP_FROZEN_TASK24_STOP_TASK28_RC001_FREEZE_AND_T30_A27_PARK`
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `OWNER_CAPTURE=PARK_H13_FROM_PRIORITY`

## Definition of Done

1. The binder reads and hashes the retained TASK-24 stop receipt, TASK-28
   RC001 freeze acceptance/configuration, and H07/H01 park acceptance. Drift
   fails closed as `H13_PARK_PREREQUISITES_DRIFT`.
2. The frozen H13 group remains order `1`, `BLOCKED_DATA`, and carries exactly
   `ENTITY_ROUTE_NOT_ADMISSIBLE`,
   `CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE`, and
   `SETTLED_EXECUTION_TRUTH_UNAVAILABLE`. The freeze is not in the write set.
3. The acceptance binds the current global trial-ledger SHA-256/as-of snapshot.
   The ledger has no `TRIAL-RC001*` or frozen H13/H02 definition trial.
   The retained H07/H01 A27 receipt remains hash-bound, but this atom does not
   claim to resolve later H07/H01 lifecycle state. H02/H10/H14 remains
   `BLOCKED_DATA` and unstarted; this atom selects no next RC001 family.
4. The acceptance and Russian readout record
   `priority_disposition=PARKED_FROM_PRIORITY`,
   `science_disposition=RETAINED`, `hypothesis_verdict=NOT_REFUTED_NOT_SUPPORTED`,
   no deletion, no trial, and the exact return condition.
5. `registries/decisions_negative_results.yaml` and Catalog/generated
   consumers register the new decision without altering TASK-24, TASK-28, or
   H07/H01 evidence.
6. Targeted tests pass and independent code, goal/DoD, and architecture
   reviews produce no `SINGLE_AGENT_REVIEW_FALLBACK`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. This is research-truth and priority
operability, not alpha evidence. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`. `CAPABILITY_RADAR_WATCH=H02_ENTRY_GATE_ONLY_AFTER_NEW_EXACT_CONTRACT`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment, setting, or network action
is authorized. The acceptance records zero provider, credential, network,
wallet/signer, execution, and cash counts; static targeted tests confirm that
the binder and runner import no network client. Passing tests, CI, a PR, or a
merge never make H13 refuted or supported, make H02 ready, produce alpha, or
establish cashflow. The only allowed new semantic claim is H13's
park-from-priority decision with retained science.
