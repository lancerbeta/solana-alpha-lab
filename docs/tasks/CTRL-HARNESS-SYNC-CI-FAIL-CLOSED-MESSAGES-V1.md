---
task_id: CTRL-HARNESS-SYNC-CI-FAIL-CLOSED-MESSAGES-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 364c9b025167d1c203fb52941f35845761427d45
  expected_upstream: origin/main
  expected_upstream_oid: 364c9b025167d1c203fb52941f35845761427d45
  expected_branch: ctrl-harness-sync-ci-fail-closed-messages-v1
  dirty_mode: ALLOW_REPORTED
objective: When derived hashes drift, CI and pre-commit fail with one actionable remediation line instead of an opaque validator cascade.
managed_write_set:
  - docs/tasks/CTRL-HARNESS-SYNC-CI-FAIL-CLOSED-MESSAGES-V1.md
  - scripts/ci_fail_closed_messages.py
  - scripts/validate_ci.py
  - scripts/validate_baton.py
  - scripts/validate.ps1
  - scripts/harness_sync.py
  - tests/test_ci_messages.py
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - delivery-harness/harness.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - FAIL_OPEN_ON_DERIVED_DRIFT
  - ACTIONABLE_LINE_REPLACES_VALIDATION
  - PRE_COMMIT_FULL_GATE_REGRESSION
  - SECRET_IN_RECEIPTS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
      - docs/evidence/control/a1_harness_sync_derived_hashes_acceptance_v1.json
      - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-HARNESS-SYNC-CI-FAIL-CLOSED-MESSAGES-V1

## Task Outcome Brief

When derived catalog hashes or navigation projections drift, repository
validation surfaces one actionable line such as
`DERIVED_HASH_DRIFT: run uv run ... harness_sync.py --apply` before the
existing validator details. Pre-commit runs a fast scoped
`harness_sync.py --check --paths-from-staging` so agents catch drift before
push. Fail-closed semantics stay unchanged; only presentation improves.

## Decision capsule

- `DECISION_DELTA`: hash-drift failures map to a single remediation command in
  `validate_ci.py`, `validate_baton.py` and pre-commit; scoped staging check
  avoids a full derived sweep on unrelated commits.
- `UNCERTAINTY_REMOVED`: whether agents can diagnose derived-hash CI failures
  without opening validator source.
- `CAPABILITY_OR_EVIDENCE`: `scripts/ci_fail_closed_messages.py` with unit tests;
  pre-commit wiring in `scripts/validate.ps1`; staging scope in
  `harness_sync.py`.

## PRD

- **Outcome:** drift yields one actionable line plus full details below it.
- **Product link:** executor diagnosability; fewer wasted agent cycles on red CI.
- **Downstream consumer:** direct delivery agents and owner log readers.
- **Success observable:** seeded drift prints `DERIVED_HASH_DRIFT` and apply
  command; clean tree passes without extra noise.
- **Cheapest falsifier:** real drift still appears only as a multi-line opaque
  traceback with no remediation command.
- **Non-goals:** no duplicate validator; no full-gate speedup; no policy change.

## SSD

- **Design:** `ci_fail_closed_messages.py` maps known drift markers from child
  validator output; `run_checked` prints the summary before child stdout/stderr.
  Pre-commit calls `harness_sync.py --check --paths-from-staging`.
- **Invariants:** FAIL remains FAIL; summary does not replace validation.
- **Affected surfaces:** `validate_ci.py`, `validate_baton.py`, `validate.ps1`,
  `harness_sync.py`, `tests/test_ci_messages.py`, protocol note, harness prefixes.
- **Validation:** unit tests for mapping, presentation order, staging scope.
- **DoD:** CI log with drift is readable without opening validator source.

## STOP

Open PR with green CI; await owner merge phrase.

## NEXT

Three-atom harness-sync pack complete after merge.
