---
task_id: FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 961dc963065cb2f428389bb9cb75ac0ebda18c23
  expected_upstream: origin/main
  expected_upstream_oid: 961dc963065cb2f428389bb9cb75ac0ebda18c23
  expected_branch: cursor/factory-v1-readiness-recertification-product
  dirty_mode: ALLOW_REPORTED
objective: Recertify Factory v1 operational readiness and activate foundation freeze after Entry Gate already resolves the bound readiness contract, without control-runtime mutation, alpha, or A7.
managed_write_set:
  - docs/tasks/FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1.md
  - configs/factory_v1_operational_readiness_v1.yaml
  - configs/factory_v1_operational_readiness_closeout_v1.yaml
  - tests/test_factory_v1_operational_readiness.py
  - tests/test_factory_v1_operational_readiness_closeout.py
  - tests/test_factory_v1_production_lite_runtime.py
  - tests/test_factory_v1_readiness_recertification.py
  - tests/test_delivery_harness_factory_v1_readiness_bind.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_v1_readiness_recertification/a1_gate_receipt_v1.json
  - docs/evidence/factory_v1_readiness_recertification/a1_acceptance_v1.json
  - docs/evidence/factory_v1_readiness_recertification/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_v1_readiness_recertification/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_v1_readiness_recertification/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_v1_readiness_recertification/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - DOMAIN_POLICY_HASH_BOUND_MUTATION
  - HISTORICAL_PROJECT_SOURCES_ROADMAP_MUTATION
  - CONTROL_RUNTIME_MUTATION
  - PR_185_MUTATION_OR_MERGE
  - SECOND_VPS_PURCHASE
  - PROVIDER_MARKET_CALL_OR_ROUTE_SWITCH
  - WALLET_SIGNER_TRANSACTION_OR_CASH
  - SCIENTIFIC_SHADOW_OR_ALPHA_CLAIM
  - A7_PLUS_WITHOUT_READY_AND_TRIGGER
  - SECRETS_IN_GIT_OR_RECEIPT
context_requirements:
  catalog_asset_ids:
    - ARCH-INTENT-005
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
    - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001
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
      - docs/evidence/factory_v1_readiness_recertification/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_v1_readiness_recertification/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_v1_readiness_recertification/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

Product slice after CTRL pin and profile bind landed on `main`.

## Decision capsule

- `DECISION_DELTA`: flip readiness stamps and closeout predicates so
  `FACTORY_V1_OPERATIONAL_READY` plus foundation freeze are machine-true.
- `UNCERTAINTY_REMOVED`: whether the last closeout gap was only the unresolved
  Entry Gate stamp after the profile already binds the file.
- `CAPABILITY_OR_EVIDENCE`: live closeout READY + freeze; tests fail if the
  stamp or profile bind is missing.
- `STOP`: no control-runtime edit, no PR #185 mutation, no domain-policy hash
  edit, no A7, no alpha.
- `NEXT`: owner decision whether to keep freeze or trigger a named A7+ atom.

## Exact predicates owned

```text
ENTRY_GATE_RESOLVES_READINESS_CONTRACT
ENTRY_GATE_PROFILE_BINDS_READINESS_CONTRACT
```

## Non-goals

Alpha, scientific SHADOW, REAL_FILL, second VPS, domain-policy file bytes,
historical Project Sources roadmaps, control-runtime files, PR #185 merge,
A7+ unless READY+explicit trigger.
