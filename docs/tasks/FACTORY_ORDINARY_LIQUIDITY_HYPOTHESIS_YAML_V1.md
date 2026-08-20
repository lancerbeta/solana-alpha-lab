---
task_id: FACTORY_ORDINARY_LIQUIDITY_HYPOTHESIS_YAML_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 454741cea139fe757b6c604badf747041aa8d03a
  expected_upstream: origin/main
  expected_upstream_oid: 454741cea139fe757b6c604badf747041aa8d03a
  expected_branch: cursor/factory-ordinary-liquidity-hypothesis-yaml
  dirty_mode: ALLOW_REPORTED
objective: Add a second ordinary ExperimentSpec in the liquidity/execution family as YAML only, classified not-promotable by the existing --spec CLI, with Factory Python and the ordinary-hypothesis CLI unchanged versus origin/main.
managed_write_set:
  - docs/tasks/FACTORY_ORDINARY_LIQUIDITY_HYPOTHESIS_YAML_V1.md
  - configs/experiment_specs/ordinary_liquidity_quote_pressure_v1.yaml
  - tests/test_factory_ordinary_market_hypothesis.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_runtime_receipt_v1.json
  - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_acceptance_v1.json
  - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_ordinary_liquidity_hypothesis_yaml/a1_owner_readout_v1.md
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
  - NEW_CLI_OR_FACTORY_PYTHON
  - FOURTH_COVERAGE_ARCHETYPE
  - QUOTE_KEEP_REOPENED
  - NUMERIC_UNKNOWN_AS_ZERO
  - PIT_READY_CLAIM
  - LOCAL_A24_PANEL_IMPORTED_AS_GIT_TRUTH
  - VPS_OR_DEPLOYMENT
  - ALPHA_OR_NETRETURN
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - DEFAULT_COMMISSIONING_SPEC_REPLACED
context_requirements:
  catalog_asset_ids:
    - CTRL-FACTORY-ORDINARY-HYPOTHESIS-THROUGH-SURFACE-001
    - CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001
    - SCHEMA-EXPERIMENT-SPEC-001
    - MODULE-FACTORY-V1-RUNNER-001
    - SCRIPT-FACTORY-ORDINARY-MARKET-HYPOTHESIS-001
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
      - docs/evidence/factory_ordinary_hypothesis_through_surface/a1_acceptance_v1.json
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json
      - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_ordinary_liquidity_hypothesis_yaml/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_ORDINARY_LIQUIDITY_HYPOTHESIS_YAML_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

`ROADMAP_VERDICT=PATCH`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge.

This is **not MOVE 3**. MOVE 2 already named the next consumer: another
ordinary hypothesis as config. A new platform slice, a new CLI, or
Factory Python would be the bureaucracy loop.

Live `origin/main` is `454741cea139fe757b6c604badf747041aa8d03a` (PR #161).
The `--spec` classifier exists. Factory core Python is unchanged since
the feature surface.

`strongest_rejected_alternative`: label this MOVE 3 and build another
Factory overlay, cockpit Python, or a third price-path YAML. Rejected
because that restates coverage and spends Catalog ceremony on no new
owner uncertainty. A second **family** YAML is the cheapest falsifier
that MOVE 2 claimed.

`ADOPTION_ROUTE=ADOPT_EXISTING_SPEC_CLI_WRAP_ONE_LIQUIDITY_YAML_BUILD_NO_PYTHON`

## PRD-lite

- **Owner decision:** whether a second ordinary hypothesis, liquidity
  family, is YAML-only on the existing CLI.
- **Product outcome:** `EXP-ORDINARY-LIQUIDITY-QUOTE-HYPOTHESIS-001`
  classified `ORDINARY_HYPOTHESIS_COMPOSED_NOT_PROMOTABLE` without
  touching Factory Python or `run_factory_ordinary_market_hypothesis.py`.
- **Named consumer:** the owner adding family-N hypotheses as YAML.
- **Current gap:** MOVE 2 proved one price-path YAML. It did not prove a
  second family reuses the same CLI with zero script changes.
- **Success / cheapest falsifier:** existing CLI `--spec` this file
  returns product terminal not-promotable. Any Factory Python or CLI
  byte change is `FACTORY_PRODUCTIZATION_REPLAN`.
- **Invalidation:** treating this as a fourth liquidity archetype;
  reopening quote KEEP; UNKNOWN friction as 0; new CLI for this spec.
- **Non-goals:** VPS, PIT_READY, alpha, TASK-28 unfreeze, surface
  expansion, default commissioning replacement, creator family,
  cockpit Python.
- **Evidence budget:** Git receipts only; 0 provider calls.
- **Replan trigger:** CLI or Factory Python must change; this YAML only
  duplicates the liquidity archetype question.

## SSD-lite

- **Baseline truth:** `origin/main` `454741ce…`. CLI sha256
  `72d479df06067bc4afae4b4a105e88825963b45b08a57747e64aa1e741a0df72`.
- **Design:** ADOPT surface, capability, existing `--spec` CLI. WRAP one
  liquidity ordinary ExperimentSpec. FORK nothing in Python. BUILD tests
  in the existing test module plus Catalog/evidence.
- **Invariants:** CLI and Factory core hashes unchanged; quote 1.0 is
  `FORWARD_ONLY` not KEEP; UNKNOWN friction/reserves not 0; TASK-28
  empty; `next_safe_action=DO_NOT_PROMOTE`.
- **Affected surfaces:** one YAML spec, existing tests, Catalog,
  receipts, readout. Not: `src/solana_alpha_lab/factory/*`,
  `scripts/run_factory_ordinary_market_hypothesis.py`, surface config,
  archetype specs.
- **Failure modes:** CLI hardcoded to price-path features (would be
  replan); catalog hash drift; CRLF on JSON.
- **Validation:** extend existing tests; isolated code + goal/DoD +
  architecture critics; exact-head CI.
- **Rollback:** revert this branch.

## Decision capsule

- `DECISION_DELTA`: second ordinary hypothesis is YAML on the same CLI,
  not MOVE 3 / not a new Factory slice.
- `UNCERTAINTY_REMOVED`: whether a liquidity-family ordinary spec
  classifies through the MOVE 2 CLI without script changes.
- `CAPABILITY_OR_EVIDENCE`: one liquidity YAML; quote FORWARD_ONLY;
  friction/reserves UNKNOWN; product not-promotable; CLI bytes unchanged.
- `STOP`: PR + exact-head CI; wait for owner merge phrase.
- `NEXT`: not VPS. After two ordinary YAMLs, further YAML-only families
  are optional. The scientific wall remains typed UNKNOWN / no PIT.
  Next material fork is owner: cheaper PIT/local-panel diagnostic, or
  `FACTORY_PRODUCTIZATION_REPLAN`.
- `REPLAN_TRIGGER`: CLI or Factory Python must change; YAML restates
  the liquidity archetype question.

## Definition of Done

1. One liquidity ordinary ExperimentSpec, distinct from
   `EXP-MARKET-FEATURE-LIQUIDITY-ARCHETYPE-001`.
2. Existing `--spec` CLI classifies it not-promotable; CLI file hash
   unchanged versus `454741ce`.
3. No Factory Python and no new script in the diff.
4. Quote availability stays `FORWARD_ONLY`, not KEEP.
5. UNKNOWN friction/reserves are not 0. No PIT_READY/alpha/VPS.
6. TASK-28 skeletons empty.
7. Delivery trio bound in `DELIVERY_EVIDENCE` before merge context.
