---
task_id: CTRL-PROFILE-PIN-VALIDATION-SUBSET-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-23'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b785dd13860572b5509cd9a9a0bd5f05babc7ed9
  expected_upstream: origin/main
  expected_upstream_oid: b785dd13860572b5509cd9a9a0bd5f05babc7ed9
  expected_branch: cursor/ctrl-profile-pin-validation-subset
  dirty_mode: ALLOW_REPORTED
objective: Relax guarded-merge project-profile pin so live-only additive keys no longer raise PROJECT_PROFILE_BASE_BINDING_INVALID, while every expected-base key including validation commands and repository identity still fail closed.
managed_write_set:
  - docs/tasks/CTRL-PROFILE-PIN-VALIDATION-SUBSET-V1.md
  - scripts/owner_attention_gate.py
  - tests/test_delivery_harness_merge_guard.py
  - delivery-harness/harness.yaml
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - catalog/assets/core.yaml
  - docs/evidence/control/a1_profile_pin_validation_subset_completion_v1.json
  - docs/evidence/control/a1_profile_pin_validation_subset_review_v1.json
  - docs/evidence/control/a1_profile_pin_validation_subset_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - VALIDATION_COMMAND_PIN_REMOVED
  - REPOSITORY_IDENTITY_PIN_REMOVED
  - PRODUCT_FACTORY_V1_SLICE_IN_THIS_ATOM
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
      - docs/evidence/control/a1_profile_pin_validation_subset_completion_v1.json
      - docs/evidence/control/a1_profile_pin_validation_subset_review_v1.json
      - docs/evidence/control/a1_profile_pin_validation_subset_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-PROFILE-PIN-VALIDATION-SUBSET-V1

## Task Outcome Brief

Guarded merge currently compares the entire `delivery-harness/project-profile.yaml`
to `origin/main`. That machine `DENY` (`PROJECT_PROFILE_BASE_BINDING_INVALID`)
blocks any additive profile key, including a later Factory v1 readiness
binding, even on `LIVE_PR_HEAD`. This atom keeps every expected-base key
identical and allows live-only additive keys. Changing validation commands or
repository identity still fails closed. Existing non-validation keys such as
`bindings` still fail closed if they drift.

This is the freeze exception for a confirmed merge-gate blocker on the active
Factory v1 recertification chain. It does not land Factory YAML, schema, or
Entry Gate wiring.

## Decision capsule

- `DECISION_DELTA`: merge pin keeps every expected-base profile key identical;
  live-only additive keys may differ. `repository` and `validation` stay
  fail-closed.
- `UNCERTAINTY_REMOVED`: whether an additive optional profile key can pass
  `load_base_bound_profile` while validation bytes stay identical to base.
- `CAPABILITY_OR_EVIDENCE`: unit tests prove extra top-level keys pass and
  validation/repository drift still raises `PROJECT_PROFILE_BASE_BINDING_INVALID`.

## PRD

- **Outcome:** control PRs may add optional profile keys without rewriting the
  merge-validation contract.
- **Downstream consumer:** next control slice that binds
  `factory_v1_readiness_contract` under `LIVE_PR_HEAD`.
- **Success observable:** additive-key test green; mutated `validation` test
  still fails closed.
- **Cheapest falsifier:** extra top-level key still raises
  `PROJECT_PROFILE_BASE_BINDING_INVALID`.
- **Non-goals:** no Factory v1 recertification, no schema extraProperties
  change, no Entry Gate wiring, no PR #185 mutation, no A7.

## SSD

- `load_base_bound_profile` requires every expected-base profile key to match
  live; live-only additive keys are allowed; then keeps the existing live
  repository identity checks.
- `LIVE_PR_HEAD` still allows `CONTROL_RUNTIME_CHANGED`; product paths remain
  outside harness prefixes.
- Harness prefixes gain this task path so the control PR write-set can include
  the contract.

## STOP

Open PR, exact-head CI green, isolated reviews, wait for owner merge phrase.
Do not merge PR #185 in this atom.

## NEXT

Control slice of Factory v1 recertification: harness + profile schema + profile
binding via `LIVE_PR_HEAD`, after this pin lands on `main`.
