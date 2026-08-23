---
task_id: CTRL-FACTORY-V1-READINESS-PROFILE-BIND-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b13490881f828b7794ebb2f503a75034c44f5f16
  expected_upstream: origin/main
  expected_upstream_oid: b13490881f828b7794ebb2f503a75034c44f5f16
  expected_branch: cursor/ctrl-factory-v1-readiness-profile-bind
  dirty_mode: ALLOW_REPORTED
objective: Bind the Factory v1 readiness YAML in the project profile and make Entry Gate resolve that exact path, without flipping product READY or freeze stamps.
managed_write_set:
  - docs/tasks/CTRL-FACTORY-V1-READINESS-PROFILE-BIND-V1.md
  - catalog/schemas/delivery_harness_project_profile.schema.json
  - delivery-harness/project-profile.yaml
  - scripts/delivery_harness.py
  - tests/test_delivery_harness_factory_v1_readiness_bind.py
  - delivery-harness/harness.yaml
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - catalog/assets/core.yaml
  - delivery-harness/templates/portable-bundle-manifest.json
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/control/a1_factory_v1_readiness_profile_bind_completion_v1.json
  - docs/evidence/control/a1_factory_v1_readiness_profile_bind_review_v1.json
  - docs/evidence/control/a1_factory_v1_readiness_profile_bind_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PRODUCT_READY_OR_FREEZE_STAMP_FLIP
  - DOMAIN_POLICY_HASH_BOUND_MUTATION
  - PR_185_MUTATION_OR_MERGE
  - A7_PLUS_WITHOUT_READY_AND_TRIGGER
  - SECRET_IN_RECEIPTS
  - FORCE_PUSH_OR_HISTORY_REWRITE
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/control/a1_factory_v1_readiness_profile_bind_completion_v1.json
      - docs/evidence/control/a1_factory_v1_readiness_profile_bind_review_v1.json
      - docs/evidence/control/a1_factory_v1_readiness_profile_bind_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-FACTORY-V1-READINESS-PROFILE-BIND-V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

## Task Outcome Brief

Slice 1 made additive live profile keys legal under `LIVE_PR_HEAD`. This control
slice binds `factory_v1_readiness_contract` to
`configs/factory_v1_operational_readiness_v1.yaml`, admits that optional key in
the profile schema, and makes Entry Gate actually resolve the file.

`check` fail-closes on a wrong path, missing file, invalid mapping, or a
present-but-wrong `live_invariant_owner`. It does not require the product stamp
`entry_gate_resolves_this_file: true`. That stamp, READY, and freeze stay on
the product slice so this merge cannot break `main` or claim Factory READY.

## Decision capsule

- `DECISION_DELTA`: bound profile names the readiness YAML; Entry Gate loads it
  into task context and fail-closes on path/file/owner mismatch.
- `UNCERTAINTY_REMOVED`: whether Entry Gate can resolve the live file without
  flipping product READY/freeze stamps.
- `CAPABILITY_OR_EVIDENCE`: tests prove binding, context selection, and
  fail-closed path/file/owner errors; live `check` still PASSes on current YAML.
- `STOP`: no product stamp flip, no PR #185 mutation, no A7, no domain-policy
  hash edit.
- `NEXT`: product slice of A6 via task-receipt (YAML/tests/evidence only).

## PRD

- **Outcome:** Entry Gate binds and resolves the readiness contract path.
- **Downstream consumer:** product A6 slice that may flip
  `entry_gate_resolves_this_file`, closeout READY, and freeze.
- **Success observable:** live profile has the exact binding; task context
  selects that file; `check` PASSes; missing/wrong path still fails closed.
- **Cheapest falsifier:** bound profile with a missing readiness file still
  returns no `FACTORY_V1_READINESS_CONTRACT_MISSING`.
- **Non-goals:** Factory READY, freeze ACTIVE, closeout recertification,
  domain-policy mutation, PR #185 merge, A7, alpha.

## SSD

- Schema optional key `factory_v1_readiness_contract` is `null` or the exact
  path `configs/factory_v1_operational_readiness_v1.yaml`.
- Bound project profile sets that exact path.
- `check_harness` extends with `factory_v1_readiness_contract_errors`.
- Task context always selects the bound file as L0
  `MISSION_AND_INVARIANTS`.
- Product stamps remain unchanged. Portable profiles stay unbound.

## STOP

Open PR, exact-head CI green, isolated reviews, wait for owner merge phrase.
Do not merge PR #185 in this atom.
