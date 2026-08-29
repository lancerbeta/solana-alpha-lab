---
task_id: HFIC_END_TO_END_SMOKE_REPAIR_LOOP_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-29'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b0146d6e7a766e7d753b2d09a88e6c8067badd62
  expected_upstream: origin/main
  expected_upstream_oid: b0146d6e7a766e7d753b2d09a88e6c8067badd62
  expected_branch: cursor/hfic-end-to-end-smoke-repair-loop-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair bounded offline Hypothesis Forge integration defects until one
  fresh disposable product-path smoke reaches a legitimate durable terminal,
  without changing research semantics or widening external authority.
managed_write_set:
- docs/tasks/HFIC_END_TO_END_SMOKE_REPAIR_LOOP_V1.md
- scripts/hypothesis_forge.py
- tests/test_hfic_cli.py
- tests/test_hfic_operational_closure_v1.py
- catalog/assets/core.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- CREDENTIAL_ACCESS
- EXPERIMENT_EXECUTION
- LIVE_SCHEDULE_ACTIVATION
- WALLET_SIGNER_TX_OR_CASH
- NEW_DATA_SOURCE_OR_CAPABILITY
- MATERIAL_HYPOTHESIS_OR_ESTIMAND_CHANGE
- DESTRUCTIVE_HISTORY_OR_SETTINGS_CHANGE
- MORE_THAN_THREE_DISTINCT_ARCHITECTURAL_ROOT_CAUSES
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_end_to_end_smoke_repair_loop/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_END_TO_END_SMOKE_REPAIR_LOOP_V1

## Task Outcome Brief

- **Owner decision:** allow one bounded repair loop for offline Hypothesis Forge
  integration defects discovered by fresh disposable product-path smoke.
- **Product outcome:** a fresh smoke reaches one legitimate durable terminal with
  a persisted `SESSION_RECEIPT`, or stops at a real scope boundary.
- **Named consumers:** `/hypothesis-forge`, `preflight`, `freeze`, isolated
  Independent Critic, `finalize`, and deterministic lane classification.
- **Cheapest falsifier:** run preflight with a multiline owner focus containing a
  colon followed by a newline; a physical Windows path must still fail closed,
  while the focus must not be mistaken for one after JSON serialization.
- **Evidence budget:** offline Git-only repair plus fresh disposable smoke; one
  branch, one review, one PR, and stop before merge.
- **Non-goals:** provider/API/RPC/WSS, credentials, money, wallet/signer/tx,
  experiments, new data/capability/estimator/scorer/backend, hypothesis
  selection, live schedule activation, and autonomous generator.

## SPEC_ROUTE=PRD_LITE

The repair preserves existing payload privacy and fail-closed identity behavior;
it does not introduce a new public contract or research capability.

## DECISION_DELTA

`_assert_no_path_leak()` distinguishes raw physical-path values from JSON escape
sequences while preserving detection of physical paths, `SMIAL_DATA_ROOT`, and
exact repository/data-root leakage.

## UNCERTAINTY_REMOVED

Whether the original `PHYSICAL_PATH_LEAK` came from a real public path or the
serialized `:\n` sequence in a multiline owner focus.

## CAPABILITY_OR_EVIDENCE

Focused regression proof plus one fresh end-to-end disposable Forge smoke that
retains all durable RDP artifacts and reaches a legitimate terminal.

## STOP

Stop at exact-head CI and await the exact owner merge phrase for the unchanged
PR/head. Do not merge in this task.

## NEXT

Exact-head CI after the single task PR.

## REPLAN_TRIGGER

Any external boundary, material research/product decision, a fourth distinct
architectural root cause, or an integration failure requiring new capability.
