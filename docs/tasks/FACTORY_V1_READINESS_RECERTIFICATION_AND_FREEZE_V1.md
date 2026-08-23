---
task_id: FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-23'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b785dd13860572b5509cd9a9a0bd5f05babc7ed9
  expected_upstream: origin/main
  expected_upstream_oid: b785dd13860572b5509cd9a9a0bd5f05babc7ed9
  expected_branch: cursor/factory-v1-readiness-recertification-and-freeze
  dirty_mode: ALLOW_REPORTED
objective: Recertify Factory v1 operational readiness by making Entry Gate
  actually resolve the live readiness contract, close the last closeout gap, and
  activate foundation freeze without alpha, second VPS, domain-policy mutation,
  or historical Project Sources roadmap edits.
managed_write_set:
- docs/tasks/FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1.md
- configs/factory_v1_operational_readiness_v1.yaml
- configs/factory_v1_operational_readiness_closeout_v1.yaml
- catalog/schemas/delivery_harness_project_profile.schema.json
- delivery-harness/project-profile.yaml
- delivery-harness/templates/portable-bundle-manifest.json
- scripts/delivery_harness.py
- tests/test_factory_v1_operational_readiness.py
- tests/test_factory_v1_operational_readiness_closeout.py
- tests/test_factory_v1_production_lite_runtime.py
- tests/test_factory_v1_readiness_recertification.py
- docs/evidence/control/delivery_harness_acceptance_v1.json
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
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
- SECOND_VPS_PURCHASE
- PROVIDER_MARKET_CALL_OR_ROUTE_SWITCH
- WALLET_SIGNER_TRANSACTION_OR_CASH
- FACTORY_RUNNER_CHANGE
- SCIENTIFIC_SHADOW_OR_ALPHA_CLAIM
- A7_PLUS_WITHOUT_READY_AND_TRIGGER
- READY_FROM_BOOLEAN_STAMP_WITHOUT_ENTRY_GATE
- SECRETS_IN_GIT_OR_RECEIPT
context_requirements:
  catalog_asset_ids:
  - ARCH-INTENT-005
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles:
  - HISTORICAL_CONTEXT
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
    HISTORICAL_CONTEXT:
    - docs/evidence/factory_v1_live_ops_hardening/a1_acceptance_v1.json
    - docs/evidence/factory_v1_operational_readiness_closeout/a1_acceptance_v1.json
---

# FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP` for tactical rebase A6 after merged A5
`FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_PASS` (PR #184 / `main@b785dd1`).

## Decision capsule

- `DECISION_DELTA`: Entry Gate binds and fail-closes on the live readiness
  YAML; closeout recertifies `FACTORY_V1_OPERATIONAL_READY` and activates
  foundation freeze.
- `UNCERTAINTY_REMOVED`: whether the last closeout gap was a missing Entry Gate
  binding or only an unflipped boolean stamp.
- `CAPABILITY_OR_EVIDENCE`: machine check that fails if Entry Gate ignores the
  readiness contract; live closeout READY + freeze without domain-policy edit.
- `STOP`: before domain-policy hash mutation, historical Project Sources
  roadmaps, alpha/READY-from-stamp, second VPS, or A7+ without READY+trigger.
- `NEXT`: owner decision whether to keep freeze or trigger a named A7+ atom.

`strongest_rejected_alternative`: flip `entry_gate_resolves_this_file` only.
Rejected because A5 already showed stamps that cannot fail independently.

## Exact predicates owned

```text
ENTRY_GATE_RESOLVES_READINESS_CONTRACT
ENTRY_GATE_PROFILE_BINDS_READINESS_CONTRACT
```

## Phases

0. Bind readiness contract in the bound project profile (optional for portable)
1. `check_harness` fail-closes if bound and flag is not true
2. Context receipt always selects the bound readiness file
3. Closeout requires both YAML flag and profile binding
4. Recertify live closeout; apply stage reconciliation only on all-PASS
5. Evidence + catalog; PR; exact merge phrase

## Non-goals

Alpha, scientific SHADOW, REAL_FILL, second VPS, domain-policy file bytes,
historical Project Sources roadmaps, A7+ unless READY+explicit trigger.
