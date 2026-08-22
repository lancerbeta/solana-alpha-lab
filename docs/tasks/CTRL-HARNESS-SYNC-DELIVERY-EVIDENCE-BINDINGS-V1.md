---
task_id: CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7e529058293c13381c7ef962d9d4a97ef3d220a5
  expected_upstream: origin/main
  expected_upstream_oid: 7e529058293c13381c7ef962d9d4a97ef3d220a5
  expected_branch: ctrl-harness-sync-delivery-evidence-bindings-v1
  dirty_mode: ALLOW_REPORTED
objective: One deterministic bind-evidence command that closes the delivery-evidence hash chain for a task without manual multi-step Python rebinding.
managed_write_set:
  - docs/tasks/CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1.md
  - scripts/harness_sync.py
  - tests/test_harness_sync_bindings.py
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - delivery-harness/harness.yaml
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_acceptance_v1.json
  - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_review_v1.json
  - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_factory_fit_v1.json
  - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - VERDICT_OR_FINDINGS_MUTATION
  - ACCEPTANCE_OR_RUNTIME_RECEIPT_MUTATION
  - BINDING_SCOPE_VIOLATION
  - EVIDENCE_FROZEN
  - SECRET_IN_RECEIPTS
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
      - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json
      - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_review_v1.json
      - docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1

## Task Outcome Brief

Extend `scripts/harness_sync.py` with `bind-evidence` so FINISH closes the
delivery-evidence hash chain in one command: `implementation_bindings` from the
actual git diff base…head, `reviewed_bindings_sha256` and
`reviewed_inventory_sha256` in independent review and factory fit, and nested
review/fit hashes inside completion. Verdicts, findings and non-claims stay
agent-owned; sync only rebinding fields the guard already reads.

## Decision capsule

- `DECISION_DELTA`: delivery-evidence rebinding moves from ad-hoc terminal
  Python to one owned command layered on atom 1 derived-hash sync.
- `UNCERTAINTY_REMOVED`: whether the FULL_REVIEW gate chain can be assembled
  deterministically from task scope without hand-editing four JSON files.
- `CAPABILITY_OR_EVIDENCE`: reuses `delivery_inventory_sha256` and the same
  canonical JSON hashing the guard verifies; fail-closed scope checks against
  task `managed_write_set`.
- `STOP`: never mutates verdicts/findings/non-claims; never touches acceptance
  or runtime receipts; refuses frozen evidence already on `origin/main`.
- `NEXT`: atom 3 improves CI fail-closed messages when drift remains.

## SPEC_ROUTE

`BOTH` — PRD + SSD inside this contract.

## PRD

- **Outcome:** `harness_sync.py bind-evidence --task-id X --apply` deterministically
  assembles the final delivery-evidence chain for task closure.
- **Product link:** cost of closing an atom; correctness of FULL_REVIEW at
  guarded merge.
- **Downstream consumer:** agent FINISH phase; `owner_attention_gate.py`.
- **Success observable:** `--verify` PASS on unchanged tree; live atom closes
  without manual hash commits.
- **Invalidation:** guarded merge still rejects hash-binding after bind-evidence.
- **Non-goals:** verdict generation; acceptance/runtime mutation; out-of-scope
  paths.

## SSD

- **Baseline:** origin/main `7e529058293c13381c7ef962d9d4a97ef3d220a5`.
- **Design:** subcommand on atom 1 core. Invariant order: content-freeze →
  `bind-evidence --apply` (one commit) → critics write verdicts only after
  bindings exist. Excluded inventory paths are the three self-referential
  delivery-evidence JSON files from the task contract. All writes LF JSON.
- **CLI:**
  - `bind-evidence --task-id ID --apply`
  - `bind-evidence --task-id ID --verify`
  - `bind-evidence --verify-all-delivered` (read-only historical audit)
- **Failure modes:** `TASK_NOT_FOUND`, `BINDING_SCOPE_VIOLATION`,
  `EVIDENCE_FROZEN`, `DELIVERY_EVIDENCE_PATHS_INCOMPLETE`.
- **Validation:** integration fixture freeze→bind→guard-readback; negatives for
  scope violation and frozen evidence; historical verify reports mismatches
  without silent repair.
- **Rollback:** revert branch.

## Definition of Done

- Golden bind/verify tests green; protocol doc names bind-evidence.
- Dogfood: control task evidence chain bound via the command.
- PR green on exact head.

## Owner gates

Exact merge phrase only after CI on unchanged head.
