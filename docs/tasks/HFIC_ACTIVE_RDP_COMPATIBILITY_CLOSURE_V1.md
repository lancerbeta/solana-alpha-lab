---
task_id: HFIC_ACTIVE_RDP_COMPATIBILITY_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-29'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 811d79c6c5343a14451f4309b6b1de1a35a387c1
  expected_upstream: origin/main
  expected_upstream_oid: 811d79c6c5343a14451f4309b6b1de1a35a387c1
  expected_branch: cursor/hfic-active-rdp-compatibility-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Make routine /hypothesis-forge succeed on the existing active historical
  Research Data Plane by a deterministic append-only compatibility repair of the
  commissioning HYPOTHESIS_VERSION proof-link, without owner repair, rewrite or
  disposable-root substitution.
managed_write_set:
- docs/tasks/HFIC_ACTIVE_RDP_COMPATIBILITY_CLOSURE_V1.md
- src/solana_alpha_lab/factory/commissioning_proof.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- scripts/hypothesis_forge.py
- tests/test_hfic_preflight.py
- tests/test_hfic_cli.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_factory_fit_v1.json
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
- REAL_DATA_MIGRATION_AMBIGUOUS
- MORE_THAN_THREE_DISTINCT_ARCHITECTURAL_ROOT_CAUSES
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids:
  - CTRL-HFIC-ACTIVE-RDP-COMPATIBILITY-CLOSURE-001
  - TEST-HFIC-COMMISSIONING-COMPATIBILITY-001
  l2_roles: []
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
    - docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/hfic_active_rdp_compatibility_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_ACTIVE_RDP_COMPATIBILITY_CLOSURE_V1

## Task Outcome Brief

- **Owner decision:** close the real-path `/hypothesis-forge` blocker on the
  existing active historical Research Data Plane so the owner can invoke the
  slash again without commissioning, backfill or repair.
- **Product outcome:** preflight proves `NO_GIT_FAST_LANE_PROVEN` on the actual
  active RDP, then a fresh routine Forge cycle reaches a legitimate durable
  terminal.
- **Named consumers:** `/hypothesis-forge`, `preflight`, commissioning proof,
  isolated Independent Critic, `finalize`.
- **Cheapest falsifier:** a store with an otherwise-valid historical
  commissioning run whose `HYPOTHESIS_VERSION` is not run/txn-bound must become
  `NO_GIT_FAST_LANE_PROVEN` after one automatic append-only compatibility
  action; an ambiguous store must fail closed with
  `REAL_DATA_MIGRATION_AMBIGUOUS` and no invented records.
- **Evidence budget:** offline Git-only repair plus real active-RDP operator
  path; one branch, one review, one PR; stop before merge.
- **Non-goals:** provider/API/RPC/WSS, credentials, money, wallet/signer/tx,
  experiment execution, live collection/schedule, destructive RDP rewrite,
  disposable-root substitution, autonomous generator.

## SPEC_ROUTE=PRD_LITE

Compatibility is an operational proof-link, not a new public research
contract. No DESIGN_SPEC.

## DECISION_DELTA

Routine preflight must distinguish `FAST_LANE_NOT_COMMISSIONED` from a
historical commissioning run that is otherwise valid except for a missing
`HYPOTHESIS_VERSION` run/txn binding, and must repair the latter
append-only when the link is uniquely recoverable.

## UNCERTAINTY_REMOVED

Whether the active RDP missing link can be reconstructed uniquely from
existing commissioning run/passport/transaction evidence, or must stop as
`REAL_DATA_MIGRATION_AMBIGUOUS`.

## CAPABILITY_OR_EVIDENCE

Automatic idempotent compatibility on historical commissioning stores, plus
one real `/hypothesis-forge` on the actual active RDP.

## STOP

Stop at exact-head CI and await the exact owner merge phrase. Do not merge
in this task. Stop immediately on ambiguous reconstruction.

## NEXT

Exact-head CI after the single task PR.

## REPLAN_TRIGGER

Destructive rewrite, ambiguous historical reconstruction, new provider or
data source, experiment execution, or a fourth distinct architectural root
cause.
