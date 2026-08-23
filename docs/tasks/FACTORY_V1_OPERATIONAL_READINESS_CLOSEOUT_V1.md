---
task_id: FACTORY_V1_OPERATIONAL_READINESS_CLOSEOUT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-23'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 22fbcdd23573c5d751b16462c41413f71a32152f
  expected_upstream: origin/main
  expected_upstream_oid: 22fbcdd23573c5d751b16462c41413f71a32152f
  expected_branch: cursor/factory-v1-operational-readiness-closeout
  dirty_mode: ALLOW_REPORTED
objective: Kill-or-freeze Atom 3 — evaluate FACTORY_V1_OPERATIONAL_READY against
  real Git receipts and emit exactly one terminal READY or PRODUCTIZATION_REPLAN
  with named gaps, reconcile stale current_product_stage, and activate Foundation
  Freeze only on READY, without new UI/DB/provider/alpha work.
managed_write_set:
- docs/tasks/FACTORY_V1_OPERATIONAL_READINESS_CLOSEOUT_V1.md
- configs/factory_v1_operational_readiness_closeout_v1.yaml
- configs/factory_v1_operational_readiness_v1.yaml
- src/solana_alpha_lab/factory/operational_readiness_closeout.py
- scripts/run_factory_v1_operational_readiness_closeout.py
- tests/test_factory_v1_operational_readiness_closeout.py
- tests/test_factory_v1_operational_readiness.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/factory_v1_operational_readiness_closeout/a1_acceptance_v1.json
- docs/evidence/factory_v1_operational_readiness_closeout/a1_gate_receipt_v1.json
- docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_independent_review_v1.json
- docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_factory_fit_v1.json
- docs/reports/factory_v1_operational_readiness_closeout/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- NEW_UI_OR_DATABASE_OR_PROVIDER
- NEW_EXPERIMENT_METHOD_OR_DISCOVERY_ENGINE
- ALPHA_OR_SCIENTIFIC_PROMOTION_CLAIM
- FALSE_FACTORY_V1_OPERATIONAL_READY
- MOSTLY_READY_WITHOUT_NAMED_GAP
- DOMAIN_POLICY_HASH_BOUND_MUTATION
- HISTORICAL_PROJECT_SOURCES_ROADMAP_MUTATION
- WALLET_SIGNER_TX_OR_LIVE_FILL
- FACTORY_CORE_RUNNER_CHANGE
context_requirements:
  catalog_asset_ids:
  - ARCH-INTENT-005
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
  - EVIDENCE-FACTORY-UNATTENDED-SHADOW-ACCEPTANCE-001
  - EVIDENCE-FACTORY-REMOTE-OPERATIONS-ACCEPTANCE-001
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
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
    - docs/evidence/factory_unattended_shadow/a1_acceptance_v1.json
    - docs/evidence/factory_v1_product_kernel/a1_factory_v1_product_kernel_acceptance_v1.json
---

# FACTORY_V1_OPERATIONAL_READINESS_CLOSEOUT_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

`ROADMAP_VERDICT=KEEP` for muv-6 Atom 3 after Atom 2
`PRODUCT_PASS_COMMISSIONING_ONLY`.

## Decision capsule

- `DECISION_DELTA`: milestone becomes a falsifiable kill-or-freeze — either
  `FACTORY_V1_OPERATIONAL_READY` or `FACTORY_PRODUCTIZATION_REPLAN(<named gaps>)`
  with Foundation Freeze only on READY.
- `UNCERTAINTY_REMOVED`: whether scattered slice receipts already satisfy the
  canonical readiness gate, or which mandatory capability is still missing.
- `CAPABILITY_OR_EVIDENCE`: predicate evaluator over Git receipts; stage
  reconciliation; closeout acceptance + owner readout.
- `STOP`: after typed terminal receipt and PR merge gate.
- `NEXT`: Atom 4 Discovery only if READY and trigger exists; otherwise close
  named REPLAN gaps before more foundation work.

`strongest_rejected_alternative`: ship another foundation feature before the
gate. Rejected — Atom 3 is read/reconcile; large build forces REPLAN.

`ADOPTION_ROUTE=ADOPT_EXISTING_RECEIPTS_BUILD_PREDICATE_EVALUATOR_ONLY`

## Non-goals

New UI, database, provider, experiment method, discovery engine, alpha,
scientific SHADOW promotion, Cockpit OPERATIONS unhide, runner rewrite,
“mostly ready”.

## Definition of Done

1. Zero-network evaluator binds each mandatory closeout predicate
   (`ready_authority: CLOSEOUT_PREDICATE_SET_ONLY`) to an exact Git receipt
   path/field and returns READY iff all PASS, else REPLAN with named gaps
   (no silent soft-pass / proxy non-claim).
2. `current_product_stage` reconciled to evidence without falsely claiming
   READY; Foundation Freeze ACTIVE only on READY.
3. Delivery trio `integrity.kind=none`; Factory Fit FULL_REVIEW; exact-head
   CI; owner merge phrase.
