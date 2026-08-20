---
task_id: ORDINARY_MARKET_PIT_PRIMARY_X_BIND_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 370819f7d1c3d339c3920fc722c83975185812e6
  expected_upstream: origin/main
  expected_upstream_oid: 370819f7d1c3d339c3920fc722c83975185812e6
  expected_branch: cursor/ordinary-market-pit-primary-x-bind
  dirty_mode: ALLOW_REPORTED
objective: Freeze ordinary liquidity-coverage primary X as liquidity/mcap and prove
  Git-retained Tokens V2 cells cannot bind it, without Factory Python or live Jupiter
  calls.
managed_write_set:
- docs/tasks/ORDINARY_MARKET_PIT_PRIMARY_X_BIND_V1.md
- configs/ordinary_market_pit_primary_x_bind_v1.yaml
- src/solana_alpha_lab/ordinary_market_pit_primary_x.py
- scripts/run_ordinary_market_pit_primary_x_bind.py
- tests/test_ordinary_market_pit_primary_x_bind.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/ordinary_market_pit_primary_x_bind/a1_runtime_receipt_v1.json
- docs/evidence/ordinary_market_pit_primary_x_bind/a1_acceptance_v1.json
- docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_completion_evidence_v1.json
- docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_independent_review_v1.json
- docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_factory_fit_v1.json
- docs/reports/ordinary_market_pit_primary_x_bind/a1_owner_readout_v1.md
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
- FACTORY_PYTHON_CHANGE
- FDV_USED_AS_MCAP
- NUMERIC_UNKNOWN_AS_ZERO
- PIT_READY_CLAIM
- LIVE_MARKET_SCORING
- THIRD_ORDINARY_YAML
- QUOTE_KEEP_AS_PREDICTOR
- TASK28_SKELETON_REGISTRY_REWRITE
- VPS_OR_DEPLOYMENT
- ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
  - CTRL-FACTORY-ORDINARY-LIQUIDITY-HYPOTHESIS-YAML-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009
  - MODULE-FACTORY-V1-RUNNER-001
  - EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  - LIFECYCLE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE:
    - registries/feature_catalog.yaml
    - registries/hypotheses.yaml
    - registries/research_cycles.yaml
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json
    - docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_completion_evidence_v1.json
    - docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_independent_review_v1.json
    - docs/evidence/ordinary_market_pit_primary_x_bind/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ORDINARY_MARKET_PIT_PRIMARY_X_BIND_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=REORDER`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge.

Muv-2 is right to stop YAML productization after PR #162. It is wrong that
Git already holds a PIT-bindable `liquidity/mcap` feature. Official Tokens V2
documents `mcap` and `liquidity`; Git-retained frozen cells keep only
`liquidity`. Raw token-list bodies are `A4_OUTSIDE_GIT`. A live audition
that reused the current cell shape would spend capture hours and still get
UNKNOWN X.

This atom is the one allowed offline preflight inside Move 1, not a third
ordinary YAML and not live Jupiter.

`strongest_rejected_alternative`: start the full live PIT audition now, or
add another not-promotable YAML. Rejected because Git already falsifies the
retention premise, and live calls need a later owner phrase.

`ADOPTION_ROUTE=ADOPT_TOKENS_V2_ROUTES_WRAP_FAIL_CLOSED_PROJECTOR_BUILD_NO_FACTORY_PYTHON`

## PRD-lite

- **Owner decision:** whether the next capture must retain raw Tokens V2
  envelopes (with `mcap`) before any market scoring.
- **Product outcome:** `GIT_RETAINED_CELLS_CANNOT_BIND_PRIMARY_X` on the
  Git-canonical qualification cells; fixture with `mcap` binds
  `liquidity/mcap`; missing/`fdv` substitute stays UNKNOWN, not 0.
- **Named consumer:** the owner authorizing the first bounded Jupiter
  capture for `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`.
- **Current gap:** Factory can describe ordinary hypotheses; Git cannot bind
  the Muv-2 primary X from retained cells.
- **Success / cheapest falsifier:** Git receipt has 0 `mcap` keys; projector
  never uses `fdv`; Factory `runner.py` hash unchanged. Live bytes or a
  Factory Python change is replan.
- **Invalidation:** treating this as PIT_READY; scoring Y; quoting KEEP as
  X; calling Jupiter.
- **Non-goals:** live capture, VPS, Cockpit, third YAML, TASK-28 unfreeze,
  factory feature-store, `/execute`, alpha.
- **Evidence budget:** Git receipts only; 0 provider calls.
- **Replan trigger:** projector requires Factory core; or Git cells already
  contain bindable `mcap` (then skip this preflight).

## SSD-lite

- **Baseline truth:** `origin/main` `370819f7…` after PR #162.
- **Design:** ADOPT registry v9 Tokens V2 routes. WRAP a fail-closed
  experiment-owned projector. FORK nothing in `src/solana_alpha_lab/factory/*`.
  BUILD tests + Catalog/evidence.
- **Invariants:** `mcap` only, never `fdv`; UNKNOWN ≠ 0; zero mcap → UNKNOWN
  not inf; `FORWARD_SNAPSHOT_NOT_PIT_READY`; TASK-28 empty; 0 provider calls.
- **Affected surfaces:** bind config, projector, CLI, tests, receipts.
  Not Factory Python, not quote-native scorers, not surface YAML.
- **Failure modes:** catalog hash drift; treating snapshot as PIT_READY.
- **Validation:** unit tests + isolated critics; exact-head CI.
- **Rollback:** revert this branch.

## Decision capsule

- `DECISION_DELTA`: REORDER away from YAML/VPS; freeze X bind before live
  capture because retained Git cells cannot compute `liquidity/mcap`.
- `UNCERTAINTY_REMOVED`: whether current Git Tokens V2 cells already contain
  `mcap` (they do not) and whether a fail-closed projector can type that
  without Factory Python.
- `CAPABILITY_OR_EVIDENCE`: 12 qualification cells → UNKNOWN X; fixture
  ratio binds; `fdv` rejected; runner unchanged.
- `STOP`: PR + exact-head CI; wait for owner merge phrase.
- `NEXT`: owner exact phrase for bounded Jupiter read-only capture that
  retains raw token-list envelopes. Not VPS. Not another YAML.
- `REPLAN_TRIGGER`: Factory Python must change; live calls leak into this
  atom; `fdv` used as mcap.

## Definition of Done

1. Frozen hypothesis `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1` with primary X
   `liquidity/mcap`.
2. Git qualification frozen cells cannot bind X; `mcap` key count 0.
3. Fixture with both fields binds a finite ratio; missing/`fdv`/zero mcap
   stay UNKNOWN, not 0.
4. No Factory Python in the diff; `runner.py` hash unchanged.
5. 0 provider calls. No PIT_READY/alpha/VPS/KEEP-as-X.
6. TASK-28 skeletons empty.
7. Delivery trio bound in `DELIVERY_EVIDENCE` before merge context.
