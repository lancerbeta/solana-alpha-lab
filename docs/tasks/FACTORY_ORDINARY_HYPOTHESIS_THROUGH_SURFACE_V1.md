---
task_id: FACTORY_ORDINARY_HYPOTHESIS_THROUGH_SURFACE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2913ef33dfd4c4776628f7005f9c48050e17292b
  expected_upstream: origin/main
  expected_upstream_oid: 2913ef33dfd4c4776628f7005f9c48050e17292b
  expected_branch: cursor/factory-ordinary-hypothesis-through-surface
  dirty_mode: ALLOW_REPORTED
objective: Compose one ordinary price-path hypothesis ExperimentSpec through the existing Factory market feature surface and generic runner, with Factory core Python change target 0, and classify the result as composed-not-promotable because Git-canonical returns stay typed UNKNOWN.
managed_write_set:
  - docs/tasks/FACTORY_ORDINARY_HYPOTHESIS_THROUGH_SURFACE_V1.md
  - configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml
  - tests/test_factory_ordinary_market_hypothesis.py
  - scripts/run_factory_ordinary_market_hypothesis.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_runtime_receipt_v1.json
  - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_acceptance_v1.json
  - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_ordinary_hypothesis_through_surface/a1_owner_readout_v1.md
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
  - FOURTH_COVERAGE_ARCHETYPE
  - FACTORY_CORE_PYTHON_CHANGE
  - DEFAULT_COMMISSIONING_SPEC_REPLACED
  - FEATURE_STORE_SERVICE
  - NEW_UI_PACKAGE_ADOPTION
  - VPS_OR_DEPLOYMENT
  - ALPHA_OR_NETRETURN
  - QUOTE_ONLY_KEEP_SCREENING_REOPENED
  - TOUCH_OR_FEE_OR_EXECUTE
  - WALLET_SIGNER_TX_OR_CASH
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
context_requirements:
  catalog_asset_ids:
    - CTRL-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001
    - CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001
    - SCHEMA-EXPERIMENT-SPEC-001
    - MODULE-FACTORY-V1-RUNNER-001
    - EVIDENCE-T30-A24P-RAW-TO-PIT-001
    - REGISTRY-FEATURE-CATALOG-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: []
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
      - docs/evidence/factory_v1_common_market_feature_surface/a1_factory_v1_common_market_feature_surface_acceptance_v1.json
      - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_ORDINARY_HYPOTHESIS_THROUGH_SURFACE_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge smoke.

Live `origin/main` is `2913ef33dfd4c4776628f7005f9c48050e17292b` (PR #160).
The previous atom's NEXT is this atom. Git does not patch the MOVE 2
premise: the surface exists; three archetypes are coverage consumers;
`runner.py` was not in that diff; Factory default commissioning spec
remains quote-native.

`strongest_rejected_alternative`: a fourth coverage archetype, expanding
the surface, filling TASK-28 skeletons, or importing the local A24 panel.
Rejected because they add no new owner uncertainty. The remaining
question is whether an ordinary hypothesis is YAML-only.

`ADOPTION_ROUTE=ADOPT_EXISTING_SURFACE_CAPABILITY_AND_RUNNER_WRAP_ONE_ORDINARY_SPEC_BUILD_NO_FACTORY_PYTHON`

## PRD-lite

- **Owner decision:** whether a named ordinary price-path hypothesis can
  be added as ExperimentSpec configuration, without a Factory Python
  overlay, and honestly stopped as not-promotable.
- **Product outcome:** one ordinary ExperimentSpec
  `EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001` /
  `HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1` composed through
  `CAP-OFFLINE-MARKET-FEATURE-RESOLVE-001`. Capability terminal stays
  `FEATURE_SURFACE_COMPOSITION_PASS`. Product terminal in CLI/tests/
  readout is `ORDINARY_HYPOTHESIS_COMPOSED_NOT_PROMOTABLE`.
- **Named consumer:** the owner adding the next ordinary hypothesis as
  config. Not a coverage-archetype author. Not VPS. Not TASK-03 populate.
- **Current gap:** archetypes proved feature IDs can be declared. They
  did not prove a hypothesis-shaped question/estimand/stop can ride the
  same surface.
- **Success / cheapest falsifier:** adding this spec requires any change
  to Factory core Python (`runner.py`, `capabilities.py`,
  `read_model.py`, `workbench.py`, `market_feature_surface.py`,
  `application.py`) versus `2913ef3`. That is
  `FACTORY_PRODUCTIZATION_REPLAN`, not a silent core edit.
- **Invalidation:** treating this spec as a fourth archetype; marking
  UNKNOWN returns as 0; claiming PIT_READY/alpha; unfreezing TASK-28;
  replacing the default commissioning spec; importing local A24 as Git
  truth.
- **Non-goals:** new features, feature store, VPS, provider calls,
  Touch/Fee/execute, quote KEEP reopen, operational-ready, NetReturn,
  filling `hypotheses.yaml`.
- **Evidence budget:** Git receipts only; 0 provider/API/RPC/WSS.
- **Replan trigger:** Factory core must change; cheapest falsifier cannot
  run; this atom only restates coverage without a distinct hypothesis
  shape.

## SSD-lite

- **Baseline truth:** `origin/main`
  `2913ef33dfd4c4776628f7005f9c48050e17292b`. Surface config sha256
  `8e51f6e565be137bb1863637121abf5cdf94c8603976eb4b0252371ba650cb39`.
- **Design:** ADOPT existing surface, capability, ExperimentRunner,
  Cockpit required-features table, A24 Git counts. WRAP one ordinary
  ExperimentSpec plus a one-spec CLI. FORK nothing in Factory Python.
  BUILD a generic `--spec` classifier CLI plus tests that pin core
  module hashes, distinguish the ordinary promotion-stop from the
  price-path coverage archetype, and classify not-promotable in
  CLI/tests/readout, not in `runner.py`. The next ordinary YAML reuses
  this CLI.
- **Invariants:** Factory core Python unchanged vs `2913ef3`;
  `UNKNOWN != 0`; no `PIT_READY`; TASK-28 skeletons empty; default
  commissioning spec stays quote-native; capability terminal is not
  forked; `next_safe_action=DO_NOT_PROMOTE`.
- **Affected surfaces:** one ExperimentSpec, one test module, one CLI
  script, Catalog/generated, runtime/acceptance, owner readout, delivery
  evidence. Not: Factory Python, TASK-28 registries, surface config,
  three archetype specs.
- **Failure modes:** hash drift on A24/surface; catalog checkpoint
  drift; Windows CRLF vs git-canonical LF on JSON receipts; treating
  capability PASS as scientific promotion.
- **Validation:** targeted tests pinning Factory core hashes; isolated
  code + goal/DoD + architecture critics; exact-head CI. No local full
  gate before PR.
- **Rollback:** revert this branch. Surface and frozen registries remain.

## Decision capsule

- `DECISION_DELTA`: ordinary hypothesis is a config consumer of the
  existing surface, not another Factory overlay and not a fourth
  archetype.
- `UNCERTAINTY_REMOVED`: whether the owner can introduce a
  hypothesis-shaped ExperimentSpec without Factory Python.
- `CAPABILITY_OR_EVIDENCE`: one ordinary spec composed; Git-computed
  trade count and buy/sell ratio; typed UNKNOWN returns; product
  terminal not-promotable.
- `STOP`: after targeted tests, PR, and exact-head CI. Wait for the
  exact owner merge phrase bound to that PR/head.
- `NEXT`: not VPS; not operational-ready. After merge, either another
  ordinary hypothesis as config, or `FACTORY_PRODUCTIZATION_REPLAN` if
  this only restated coverage.
- `REPLAN_TRIGGER`: any Factory core Python change; UNKNOWN coerced to
  0; TASK-28 unfreeze required for PASS.

## Definition of Done

1. One ordinary ExperimentSpec, distinct from
   `EXP-MARKET-FEATURE-PRICE-PATH-ARCHETYPE-001`.
2. It composes via existing capability + `ExperimentRunner`.
3. No Factory core Python in the diff versus `2913ef3`.
4. TASK-28 skeletons unchanged and empty.
5. Honest typed gaps; no PIT_READY/alpha/VPS.
6. Owner readout: hypothesis composed, not promotable.
7. Delivery completion + independent review + factory-fit bound in
   `DELIVERY_EVIDENCE` before merge context.
