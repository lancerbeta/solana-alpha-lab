---
task_id: FACTORY_V1_COMMISSIONING_HYPOTHESIS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-19'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2cb335dc65360cc8444dd32d7be21ade5fb18c40
  expected_upstream: origin/main
  expected_upstream_oid: 2cb335dc65360cc8444dd32d7be21ade5fb18c40
  expected_branch: cursor/factory-v1-commissioning-hypothesis
  dirty_mode: ALLOW_REPORTED
objective: Freeze and run one Factory-commissioned Jupiter Free-key quote-native experiment through ExperimentSpec and the generic runner by WRAPping existing capture plus classify_audition_terminal, returning the owner packet without a hypothesis-specific core runner, MOVE 3, or an operational-ready claim.
managed_write_set:
  - docs/tasks/FACTORY_V1_COMMISSIONING_HYPOTHESIS_V1.md
  - catalog/schemas/experiment_spec.schema.json
  - catalog/schemas/factory_v1_commissioning.schema.json
  - configs/factory_v1_commissioning_v1.yaml
  - configs/experiment_specs/factory_v1_commissioning_quote_native_free_key_v1.yaml
  - configs/quote_native_factory_commissioning_audition_v1.yaml
  - src/solana_alpha_lab/quote_native_admissible_friction_audition.py
  - src/solana_alpha_lab/factory/capabilities.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/runner.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/workbench.py
  - scripts/run_factory_experiment.py
  - scripts/run_factory_workbench.py
  - scripts/run_factory_commissioning_capture.py
  - tests/test_factory_v1_product_kernel.py
  - tests/test_factory_v1_commissioning.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_runtime_receipt_v1.json
  - docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_acceptance_v1.json
  - docs/evidence/factory_v1_commissioning/a2_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_commissioning/a2_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_commissioning/a2_delivery_factory_fit_v1.json
  - docs/reports/factory_v1_commissioning/a2_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
  - MOVE_3_OR_TREATING_MOVE_2_AS_NEW_RESULT
  - A1_OR_MOVE2_MINT_REUSE_IN_LIVE_COHORT
  - HYPOTHESIS_SPECIFIC_CORE_RUNNER_CHANGE
  - PRODUCTION_REGISTRY_SEED
  - NEW_UI_PACKAGE_ADOPTION
  - VPS_OR_DEPLOYMENT
  - FACTORY_V1_OPERATIONAL_READY_CLAIM
  - WALLET_SIGNER_TX_OR_CASH
  - PAID_PLAN_OR_SECOND_PROVIDER
  - EXECUTE_BUILD_OR_TAKER
  - PIT_OR_HOLDOUT_WEAKENING
  - WORKFLOW_ENGINE_OR_PLUGIN_MARKETPLACE
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-PRODUCT-KERNEL-001
    - EVIDENCE-FACTORY-V1-PRODUCT-KERNEL-ACCEPTANCE-001
    - EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-ACCEPTANCE-001
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v9.yaml
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_v1_product_kernel/a1_factory_v1_product_kernel_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_COMMISSIONING_HYPOTHESIS_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP` with PATCH only on the frozen commissioning hypothesis:
live Git after ATOM 1 and MOVE 2 does not authorize MOVE 3, does not treat
MOVE 2 as a new Factory result, and does not allow a second preparatory-only
atom. This atom is the first market byte after the kernel slice.

Owner trigger: ATOM 2 selected plus `го` to write the exact contract and
execute. Generic `го` is not the Jupiter Free-key phrase.

## PRD-lite

- **Outcome that must become true:** the owner can start from Factory, run one
  bounded Jupiter Free-key quote-native experiment, and receive
  QUESTION / ESTIMAND / POPULATION / DATA / RESULT / UNCERTAINTY / ROBUSTNESS /
  FAILURE / DECISION / NEXT without a hypothesis-specific core runner.
- **Why now:** ATOM 1 proved offline golden replay. The readiness gate still
  requires a real new hypothesis completed end-to-end. A second kernel-only
  atom would trip the preparatory-only replan.
- **Downstream consumer:** ATOM 3 VPS / ATOM 4 Cockpit remain horizon; this
  atom's consumer is the owner operating Factory on one live cycle.
- **Current gap:** the only allowlisted Factory capability is offline receipt
  replay; live capture still lives in the A1 audition module and script.
- **Success observable:** one new live 6+6 Free-key cohort excluding A1 and
  MOVE 2 mints, scored by WRAP of `classify_audition_terminal`, projected by
  `FactoryReadModel`. Scientific FAIL may still be product PASS.
- **Invalidation / cheapest falsifier:** live capture cannot run except by
  copying a new core pipeline, or the runner must embed hypothesis logic, or
  the cohort reuses A1/MOVE 2 mints, or MOVE 3 is started.
- **Non-goals:** `FACTORY_V1_OPERATIONAL_READY`, VPS, Cockpit breadth, alpha,
  NetReturn, MOVE 3, paid plan, second provider, `/build` `/execute` taker,
  wallet/signer/tx, production `hypotheses.yaml` / `research_cycles.yaml` seed,
  NiceGUI/Streamlit/FastAPI package, kernel `provider_calls: true` rewrite.

Frozen commissioning hypothesis:

- ID: `HYP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-V1`
- Experiment: `EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001`
- Capability: `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`
- Product question: can Factory complete one bounded Free-key quote-native
  cycle from ExperimentSpec?
- Estimand vehicle: existing `QuotedRoundTripFriction(t0) -> QuotedLiquidationRecovery(H900)`
  WRAP, not a new research ladder.
- Population: new live outcome-blind Tokens V2 6 RECENT + 6 TRADED, excluding
  A1 and MOVE 2 mints.

## SSD-lite

- **Baseline truth:** `origin/main` `2cb335dc65360cc8444dd32d7be21ade5fb18c40`.
  ATOM 1 golden replay PASS. MOVE 2 `REPLICATED_SIGN_NOT_ALPHA`. MOVE 3 not
  earned. Production registries remain empty.
- **Design:** ADOPT existing Free-key routes; WRAP `run_campaign` +
  `classify_audition_terminal`; FORK only the frozen `(atom_id, owner_phrase)`
  pair and reservation `atom_id` so Factory commissioning is not the consumed
  A1 phrase. BUILD nothing new in the generic runner.
- **Invariants:** Git/Catalog/receipts remain scientific truth; SQLite/UI are
  projection; UI START without the exact phrase never reads `JUPITER_API_KEY`
  and never calls Jupiter; offline replay stays budget 0; live budget max 60;
  cash $0; no `.env`.
- **Affected surfaces:** ExperimentSpec schema (live kinds + bounded budget),
  Factory capability router, application spec selection, audition authority
  pair, Workbench copy, commissioning config. Kernel schema stays ATOM 1
  `provider_calls: false`.
- **Failure modes:** `BLOCKED_AUTHORITY` if phrase absent/mismatch;
  `BLOCKED_DATA` if capture policy or exclusion receipts mismatch; typed
  capture/sample terminals remain scientific, not product FAIL by themselves.
- **Validation:** fail-closed tests with zero network; mocked WRAP of
  `run_campaign` after phrase; live capture only after the exact phrase below;
  then hash-bind receipts and targeted tests.
- **Rollback:** revert the branch; SQLite under `local/` is not Git truth.

## Decision capsule

- `DECISION_DELTA`: freeze the commissioning hypothesis as Factory-composed
  live Free-key capture, not MOVE 3 and not a second kernel slice.
- `UNCERTAINTY_REMOVED`: whether existing capture+scorer can be allowlisted as
  a Factory capability without a hypothesis-specific core runner.
- `CAPABILITY_OR_EVIDENCE`: `CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001`,
  commissioning ExperimentSpec, owner packet, one new market byte.
- `STOP`: before any Jupiter/credential read until the exact phrase; after
  live capture, at exact-head CI for the merge phrase. Never claim
  `FACTORY_V1_OPERATIONAL_READY`.
- `NEXT`: ATOM 3 VPS only after this atom's live commissioning packet exists.
- `ADOPTION_ROUTE=WRAP_EXISTING_AUDITION_CAPTURE_AND_SCORER`
- `REPLAN_TRIGGER`: second consecutive preparatory-only merge; core runner
  must learn audition logic; cheapest falsifier cannot run; second provider
  or paid-plan pivot; evidence/time budget exceeded.

## Exact live-capture owner phrase

This phrase is the credential/network gate. `го` does not satisfy it.

`OK FACTORY_V1_COMMISSIONING_HYPOTHESIS_V1: one Jupiter Free-key Factory-commissioned quote-native campaign; local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED live outcome-blind cohort excluding A1 and MOVE 2 mints; hash-bound row observed_at and attempt reservation before credential read required for capture PASS; WRAP existing classify_audition_terminal; not MOVE 3; not alpha; scientific FAIL may still be product PASS.`

## Definition of Done

1. ExperimentSpec schema accepts bounded live budget and produced capture
   paths without forcing a pre-capture sha256.
2. Offline golden spec remains budget 0 and still replays.
3. Factory allowlists the live capability; missing/mismatched phrase returns
   `BLOCKED_AUTHORITY` with 0 provider calls and 0 credential reads.
4. Application default spec is the commissioning ExperimentSpec; golden tests
   pass an explicit spec path.
5. After the exact phrase: one live capture, hash-bound runtime receipt,
   WRAP classification, owner packet, targeted tests, Catalog propagation.
6. No production registry seed. No operational-ready claim. No MOVE 3.

## Merge evidence

`exact_role_paths.DELIVERY_EVIDENCE` at merge must list exactly one
`smial.delivery-completion-evidence` for this atom:

`docs/evidence/factory_v1_commissioning/a2_delivery_completion_evidence_v1.json`
