---
task_id: FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-23'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4c46dae3a9fe8f7ed172f34675c18afac2e6d8f8
  expected_upstream: origin/main
  expected_upstream_oid: 4c46dae3a9fe8f7ed172f34675c18afac2e6d8f8
  expected_branch: cursor/factory-v1-live-ops-hardening-commissioning
  dirty_mode: ALLOW_REPORTED
objective: Prove the existing Factory remote host is reproducibly deployable,
  rollbackable, cleanly reconstructable, semantically observable and financially
  non-authoritative, closing the seven A5 readiness predicates without second VPS,
  provider market calls, signer or READY claim.
managed_write_set:
- docs/tasks/FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1.md
- configs/factory_v1_live_ops_hardening_v1.yaml
- configs/factory_v1_operational_readiness_closeout_v1.yaml
- catalog/schemas/factory_v1_live_ops_hardening.schema.json
- catalog/schemas/factory_v1_live_ops_hardening_host_proof.schema.json
- src/solana_alpha_lab/factory/remote_ops.py
- src/solana_alpha_lab/factory/live_ops_hardening.py
- src/solana_alpha_lab/factory/operational_readiness_closeout.py
- scripts/run_factory_v1_live_ops_hardening.py
- scripts/factory_live_release.py
- scripts/factory_remote_doctor.py
- tests/test_factory_v1_live_ops_hardening.py
- tests/test_factory_remote_operations.py
- tests/test_factory_v1_operational_readiness_closeout.py
- docs/operator/FACTORY_REMOTE_HOST.md
- docs/operator/factory_remote_host_v1.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/factory_v1_live_ops_hardening/a1_runtime_receipt_v1.json
- docs/evidence/factory_v1_live_ops_hardening/a1_host_proof_v1.json
- docs/evidence/factory_v1_live_ops_hardening/a1_acceptance_v1.json
- docs/evidence/factory_v1_live_ops_hardening/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_v1_live_ops_hardening/a1_delivery_independent_review_v1.json
- docs/evidence/factory_v1_live_ops_hardening/a1_delivery_factory_fit_v1.json
- docs/reports/factory_v1_live_ops_hardening/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: true
stop_conditions:
- SECOND_VPS_PURCHASE
- PROVIDER_MARKET_CALL_OR_ROUTE_SWITCH
- WALLET_SIGNER_TRANSACTION_OR_CASH
- FACTORY_RUNNER_CHANGE
- SCIENTIFIC_SHADOW_OR_ALPHA_CLAIM
- FACTORY_V1_OPERATIONAL_READY_CLAIM
- A6_POLICY_CERTIFICATION_INSIDE_A5
- SENTRY_K8S_ANSIBLE_PLATFORM
- PUBLIC_ADMIN_OR_PASSWORD_SSH
- SECRETS_IN_GIT_OR_RECEIPT
context_requirements:
  catalog_asset_ids:
  - ARCH-INTENT-005
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001
  - CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001
  - EVIDENCE-FACTORY-REMOTE-OPERATIONS-ACCEPTANCE-001
  - EVIDENCE-FACTORY-UNATTENDED-SHADOW-HOST-PROOF-001
  - EVIDENCE-FACTORY-V1-PIT-DATA-TRUTH-CANONICALIZATION-ACCEPTANCE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles:
  - HISTORICAL_CONTEXT
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - docs/operator/factory_remote_host_v1.yaml
    - docs/operator/FACTORY_REMOTE_HOST.md
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT:
    - docs/evidence/factory_remote_operations/a3_acceptance_v1.json
    - docs/evidence/factory_unattended_shadow/a1_host_proof_v1.json
    - docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json
---

# FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

`ROADMAP_VERDICT=KEEP` for tactical rebase A5 after merged A4
`FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_PASS` (PR #183 / `main@4c46dae`).

## Decision capsule

- `DECISION_DELTA`: existing live Factory host proves release recovery, clean
  rehost, composed provider/data/bot health, alert lifecycle/recurrence and
  positive financial-authority separation.
- `UNCERTAINTY_REMOVED`: whether the seven remaining runtime/monitoring/security
  readiness gaps are missing behavior or only untested wiring.
- `CAPABILITY_OR_EVIDENCE`: one phased live-host commissioning acceptance that
  A6 can rebind without changing closeout evaluator logic.
- `STOP`: before second VPS, provider market call, signer/tx/cash, READY claim,
  or A6 policy work inside this atom.
- `NEXT`: A6 readiness recertification if PASS; exact operational REPLAN if any
  named predicate remains unproved.

`strongest_rejected_alternative`: split release vs monitoring into two live PRs.
Rejected now because they share one host, one external boundary and one recovery
session; two ceremonies amplify intermediate-host risk.

## Exact predicates owned

```text
RUNTIME_LIVE_DEPLOY_ROLLBACK
RUNTIME_LIVE_CLEAN_REHOST
MONITORING_PROVIDER_FAILURE_ALERT
MONITORING_LIVE_STALE_DATA_ALERT
MONITORING_LIVE_BOT_STALL_ALERT
DATA_PROVIDER_HEALTH_VISIBLE
SECURITY_FINANCIAL_GATED
```

## Phases

0. Zero-network local falsifier (release/health/incident/financial)
1. Live-host read-only preflight + state freeze
2. Exact-SHA deploy → rollback → forward restore
3. Clean empty-root rehost on the same real host
4. Composed health clocks (worker ≠ progress ≠ market_data ≠ provider)
5. Diagnostic fault matrix (stale / stall / provider-failed)
6. Incident lifecycle + recurrence redelivery
7. Positive financial-boundary proof + cleanup/readback

## Non-goals

Second VPS, HA, Docker/K8s, Ansible, Sentry, new provider, Jupiter market call,
alpha, scientific SHADOW, REAL_FILL, signer, wallet, transaction, cash, A6 policy
binding, READY claim.
