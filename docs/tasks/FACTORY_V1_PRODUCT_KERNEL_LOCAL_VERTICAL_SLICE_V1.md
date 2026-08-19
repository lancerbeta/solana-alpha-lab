---
task_id: FACTORY_V1_PRODUCT_KERNEL_LOCAL_VERTICAL_SLICE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: cbf03a8353b9126885f35ddade5c51ef144fae3a
  expected_upstream: origin/main
  expected_upstream_oid: cbf03a8353b9126885f35ddade5c51ef144fae3a
  expected_branch: cursor/factory-v1-product-kernel-local-vertical-slice
  dirty_mode: ALLOW_REPORTED
objective: Create the minimum reusable Factory kernel so one existing golden research cycle can run through ExperimentSpec, a generic runner, SQLite job state, a derived read model, and a thin local owner surface without a hypothesis-specific core pipeline or new market bytes.
managed_write_set:
  - docs/tasks/FACTORY_V1_PRODUCT_KERNEL_LOCAL_VERTICAL_SLICE_V1.md
  - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
  - configs/factory_v1_operational_readiness_v1.yaml
  - configs/factory_v1_product_kernel_v1.yaml
  - configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml
  - catalog/schemas/experiment_spec.schema.json
  - catalog/schemas/factory_v1_product_kernel.schema.json
  - src/solana_alpha_lab/factory/__init__.py
  - src/solana_alpha_lab/factory/experiment_spec.py
  - src/solana_alpha_lab/factory/operational_store.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/runner.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - scripts/run_factory_experiment.py
  - scripts/run_factory_workbench.py
  - tests/test_factory_v1_product_kernel.py
  - tests/test_factory_v1_operational_readiness.py
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - registries/research_cycles.yaml
  - registries/hypotheses.yaml
  - catalog/assets/architecture.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/factory_v1_product_kernel/a1_owner_readout_v1.md
  - docs/evidence/factory_v1_product_kernel/a1_ui_adopt_gate_v1.json
  - docs/evidence/factory_v1_product_kernel/a1_factory_v1_product_kernel_acceptance_v1.json
  - docs/evidence/factory_v1_product_kernel/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_product_kernel/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_product_kernel/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PROVIDER_OR_NETWORK_CALL
  - NEW_UI_PACKAGE_ADOPTION
  - VPS_OR_DEPLOYMENT
  - MARKET_CAPTURE_OR_RECAPTURE
  - MOVE_3_OR_NEW_RESEARCH_LADDER
  - TASK35A_PARALLEL_CHAIN
  - WORKFLOW_ENGINE_OR_PLUGIN_MARKETPLACE
  - SECOND_TRUTH_STORE
  - UI_WRITES_REGISTRIES_DIRECTLY
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - WALLET_SIGNER_TX_OR_CASH
  - PIT_OR_HOLDOUT_WEAKENING
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
    - EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-ACCEPTANCE-001
    - ARCH-INTENT-004
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_admissible_friction_audition/a1_quote_native_admissible_friction_audition_acceptance_v1.json
      - docs/evidence/factory_v1_operational_readiness/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_v1_product_kernel/a1_factory_v1_product_kernel_acceptance_v1.json
      - docs/evidence/factory_v1_product_kernel/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_v1_product_kernel/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_v1_product_kernel/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_PRODUCT_KERNEL_LOCAL_VERTICAL_SLICE_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

Owner trigger `OWNER_EXPLICITLY_SELECTS_FACTORY_PRODUCTIZATION` is accepted.
Live Git patches: base is current `origin/main` including merged MOVE 2
(`cbf03a8`), not the orientation-time `fa3a64e`; MOVE 3 remains parked;
MOVE 2 outcomes are not a new commissioning result.

## Task Outcome Brief

- **Owner decision:** whether an existing golden cycle can leave
  task-specific orchestration and run through an `ExperimentSpec`-driven
  Factory.
- **Product outcome:** a local vertical slice with generic runner, SQLite
  job state, derived read model, and thin owner surface.
- **Named consumer:** ATOM 2 commissioning hypothesis.
- **Cheapest falsifier:** the golden cycle still requires a new bespoke
  pipeline or a hypothesis-specific core runner change.
- **Terminal outcomes:** `FACTORY_KERNEL_GOLDEN_REPLAY_PASS` |
  `FACTORY_KERNEL_REPLAN_BESPOKE_PIPELINE_REQUIRED`.
- **User-visible result:** local Workbench shows one hypothesis, evidence
  requirements, experiment state, blockers, and next safe action.
- **Non-goals:** VPS, production monitoring, broad Cockpit, market capture,
  new provider, new UI package, MOVE 3, `FACTORY_V1_OPERATIONAL_READY`.
- **Evidence budget:** offline repository work; targeted tests; zero
  provider/API/RPC/WSS.
- **Replan trigger:** second preparatory-only atom; golden cycle forces
  hypothesis-specific core change; UI becomes truth owner; PIT/missingness
  weakened.

## Decision capsule

- `DECISION_DELTA`: activate Factory productization; first byte is the
  reusable kernel, not another research campaign.
- `UNCERTAINTY_REMOVED`: whether the admissible-audition cycle can be
  expressed as `ExperimentSpec` and replayed by a generic runner without
  duplicating truth contracts.
- `CAPABILITY_OR_EVIDENCE`: ExperimentSpec, ExperimentRunner,
  FactoryReadModel, SQLite ops state, thin Workbench, offline golden replay.
- `STOP`: after targeted tests and PR/CI; no provider/VPS/market; no
  operational-ready claim.
- `NEXT`: freeze ATOM 2 commissioning hypothesis against then-live Git.
- `ADOPTION_ROUTE=BUILD_STDLIB_WORKBENCH_WRAP_EXISTING_AUDITION_SCORER`

## Golden cycle

Offline replay of merged `QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1`
from Git-canonical receipts. Zero provider calls. Do not recapture.
Do not treat MOVE 2 as this atom's golden.

## UI ADOPT gate

Compare NiceGUI, Streamlit, and FastAPI+htmx. This atom does not adopt a
new package. Verdict is recorded in
`docs/evidence/factory_v1_product_kernel/a1_ui_adopt_gate_v1.json`.
The Workbench is a stdlib HTTP projection over the read model.
