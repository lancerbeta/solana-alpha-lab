---
task_id: FACTORY_COMMON_MARKET_FEATURE_SURFACE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 38ee8f4c8c2b19a7195a6236bb6e5a9d6ca5efbe
  expected_upstream: origin/main
  expected_upstream_oid: 38ee8f4c8c2b19a7195a6236bb6e5a9d6ca5efbe
  expected_branch: cursor/factory-common-market-feature-surface
  dirty_mode: ALLOW_REPORTED
objective: Derive the minimum reusable PIT-honest market feature surface for three representative intraday archetypes from existing Git-canonical evidence, expose coverage through ExperimentSpec and Cockpit-lite, and prove all three compose on the generic runner without hypothesis-specific runner changes.
managed_write_set:
  - docs/tasks/FACTORY_COMMON_MARKET_FEATURE_SURFACE_V1.md
  - catalog/schemas/factory_v1_common_market_feature_surface.schema.json
  - catalog/schemas/experiment_spec.schema.json
  - configs/factory_v1_common_market_feature_surface_v1.yaml
  - configs/experiment_specs/market_feature_price_path_archetype_v1.yaml
  - configs/experiment_specs/market_feature_liquidity_archetype_v1.yaml
  - configs/experiment_specs/market_feature_creator_pressure_archetype_v1.yaml
  - src/solana_alpha_lab/factory/market_feature_surface.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/workbench.py
  - tests/test_factory_v1_common_market_feature_surface.py
  - scripts/run_factory_market_feature_surface.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_common_market_feature_surface/a1_factory_v1_common_market_feature_surface_runtime_receipt_v1.json
  - docs/evidence/factory_v1_common_market_feature_surface/a1_factory_v1_common_market_feature_surface_acceptance_v1.json
  - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_v1_common_market_feature_surface/a1_owner_readout_v1.md
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
  - TASK28_SKELETON_REGISTRY_REWRITE
  - FEATURE_CATALOG_UNFREEZE
  - LOCAL_A24_PANEL_IMPORTED_AS_GIT_TRUTH
  - PIT_READY_CLAIM_ON_RETROSPECTIVE_BYTES
  - NUMERIC_UNKNOWN_AS_ZERO
  - CREATOR_CLUSTER_RESURRECTION
  - EXPERIMENT_RUNNER_HYPOTHESIS_LOGIC
  - FEATURE_STORE_SERVICE
  - NEW_UI_PACKAGE_ADOPTION
  - VPS_OR_DEPLOYMENT
  - ALPHA_OR_NETRETURN_OR_ATOM_2
  - QUOTE_ONLY_KEEP_SCREENING_REOPENED
  - TOUCH_OR_FEE_OR_EXECUTE
  - WALLET_SIGNER_TX_OR_CASH
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
context_requirements:
  catalog_asset_ids:
    - CTRL-FACTORY-V1-PRODUCT-KERNEL-001
    - SCHEMA-EXPERIMENT-SPEC-001
    - MODULE-FACTORY-V1-RUNNER-001
    - MODULE-FACTORY-V1-COCKPIT-001
    - EVIDENCE-T30-A24P-RAW-TO-PIT-001
    - EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-ACCEPTANCE-001
    - REGISTRY-FEATURE-CATALOG-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: [HISTORICAL_CONTEXT]
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE:
      - registries/feature_catalog.yaml
      - registries/hypotheses.yaml
      - registries/research_cycles.yaml
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a24_raw_to_pit_admissibility_runtime_receipt_v1.json
      - docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json
      - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_v1_common_market_feature_surface/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
      - docs/evidence/pre_git/task01/hypothesis_data_coverage_matrix_v1.md
---

# FACTORY_COMMON_MARKET_FEATURE_SURFACE_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=REBASE`

Owner accepted the Drive strategy note «Мув» as the route, with details
to be Git-cross-validated. Live Git patches the note:

- `origin/main` is `38ee8f4` (PR #159 stay-overlay), not `5975685`.
- Quote-only KEEP screening is already `EXHAUSTED`.
- `registries/feature_catalog.yaml`, `hypotheses.yaml` and
  `research_cycles.yaml` are empty **because TASK-28 froze those
  skeletons**. Filling them would rewrite the freeze. Factory-owned
  surface config is the product vocabulary.
- The A24 96-slot panel lives under `local/`, not Git. Path/return/
  drawdown/volume cannot be computed from the Git receipt. Those
  features stay `HISTORICAL_RECONSTRUCTIBLE` + typed `UNKNOWN`.
- No feature in this atom is `PIT_READY`. A24 is retrospective-only.

`strongest_rejected_alternative`: next quote-native KEEP family, Touch/Fee
capture, or VPS. Rejected because stay-overlay closed quote KEEP and VPS
would host a Factory that still cannot compose an ordinary hypothesis.

`ENTRY_VERDICT` patch is Git truth, not a new owner product fork.

`ADOPTION_ROUTE=ADOPT_EXPERIMENT_SPEC_RUNNER_COCKPIT_AND_A24_A1_RECEIPTS_WRAP_NEW_RESOLVER_BUILD_NO_FEATURE_STORE`

## PRD-lite

- **Owner decision:** whether ordinary price/volume/liquidity/creator
  hypotheses can be declared as required feature IDs against one reusable
  surface, instead of a new Python overlay.
- **Product outcome:** one Factory-owned feature vocabulary, three
  archetype ExperimentSpecs, Cockpit coverage rows, deterministic offline
  composition. Scientific values may be typed gaps. Product PASS is
  composition, not alpha.
- **Named consumers:** three archetypes — price/path, liquidity/execution,
  creator-pressure — as coverage consumers, not commissioned trials.
- **Current gap:** runner is generic; capabilities are still quote-native
  overlays; owner cannot see required vs available vs missing features.
- **Success / cheapest falsifier:** add the second and third ExperimentSpec
  without editing `src/solana_alpha_lab/factory/runner.py`. If the runner
  must learn feature IDs, design FAIL.
- **Invalidation:** marking retrospective A24 bytes `PIT_READY`; treating
  `UNKNOWN` as 0; unfreezing TASK-28 skeletons; resurrecting creator
  cluster; reopening quote KEEP; importing local panel as Git truth.
- **Non-goals:** alpha, NetReturn, Atom 2, VPS, provider calls, entity
  graph, feature store, DuckDB service, ML, new UI package, operational
  ready, Touch/Fee/execute, filling TASK-03 registries.
- **Evidence budget:** Git receipts only; 0 provider/API/RPC/WSS.
- **Replan trigger:** runner coupling; cheapest falsifier cannot run;
  honest coverage requires the local A24 panel in Git; second provider
  route.

## SSD-lite

- **Baseline truth:** `origin/main` `38ee8f4c8c2b19a7195a6236bb6e5a9d6ca5efbe`.
- **Design:** ADOPT ExperimentSpec, ExperimentRunner, Cockpit-lite, A24
  Git runtime (counts/PIT flags), A1 quote receipt (forward-only
  observation). WRAP a new allowlisted capability
  `CAP-OFFLINE-MARKET-FEATURE-RESOLVE-001`. FORK optional
  `required_feature_ids` on ExperimentSpec. BUILD FeatureResolver +
  snapshot only. TASK-28 skeletons stay empty.
- **Invariants:** `UNKNOWN ≠ 0`; `MISSING_CAPABILITY` for
  `FEAT-CREATOR-CLUSTER-SHARE`; no `PIT_READY`; runner has no feature
  logic; kernel `provider_calls` stay false.
- **Affected surfaces:** new surface config/schema/module, three specs,
  capability router, read-model/workbench coverage table, Catalog.
  Not: runner.py, feature_catalog.yaml, hypotheses.yaml,
  research_cycles.yaml, v6/v7, trial ledger.
- **Failure modes:** hash drift on A24/A1; schema rejects old specs;
  cockpit packet grows past 10 fields; catalog checkpoint drift.
- **Validation:** targeted surface tests; existing kernel/cockpit tests;
  isolated code + goal/DoD + architecture critics; exact-head CI.
- **Rollback:** revert this branch. Frozen quote and A24 receipts remain
  create-only.

## Decision capsule

- `DECISION_DELTA`: stop stacking quote-native overlays; make ordinary
  market hypotheses a feature-ID consumer of one offline resolver.
- `UNCERTAINTY_REMOVED`: whether three archetypes can compose through
  ExperimentSpec + generic runner with honest availability, without a
  feature store or TASK-28 unfreeze.
- `CAPABILITY_OR_EVIDENCE`: Factory feature surface, three composing
  specs, Cockpit required-features table, typed gaps including creator
  cluster.
- `STOP`: after targeted tests and PR/CI. Not MOVE 2 hypothesis science.
  Not VPS.
- `NEXT`: MOVE 2 is a later exact contract: one ordinary hypothesis
  through this surface with Factory core change target 0. If core runner
  must change, `FACTORY_PRODUCTIZATION_REPLAN`.
- `REPLAN_TRIGGER`: runner.py must change for the second spec; local
  panel required for any PASS; TASK-28 tests force a skeleton rewrite;
  budget/provider pivot.

## Definition of Done

1. Surface config names 15–20 features bound to TASK-01 domains, with
   availability class, missingness, and consumers.
2. ExperimentSpec may declare `required_feature_ids`; existing specs
   without the field still validate.
3. Three archetype specs resolve through one capability and
   ExperimentRunner; `runner.py` is not in the diff.
4. Computed values come only from Git-canonical A24/A1 receipts.
   Path/return/drawdown/volume/liquidity size stay typed UNKNOWN.
5. Creator cluster is `MISSING_CAPABILITY`. Direct creator share/sell
   are `MISSING`, not zero.
6. Cockpit/workbench shows required feature coverage without adding an
   11th owner-packet field and without a new UI package.
7. TASK-28 empty skeletons and hashes are unchanged.
8. No provider, no alpha, no VPS, no operational-ready claim.
