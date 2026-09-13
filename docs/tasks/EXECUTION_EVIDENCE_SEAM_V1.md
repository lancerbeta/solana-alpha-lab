---
task_id: EXECUTION_EVIDENCE_SEAM_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-13'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e79adc0b7b8d765ef14e1560ba81f08efcdcf61a
  expected_upstream: origin/main
  expected_upstream_oid: e79adc0b7b8d765ef14e1560ba81f08efcdcf61a
  expected_branch: cursor/execution-evidence-seam-v1
  dirty_mode: ALLOW_REPORTED
objective: Close the scientific-PROMOTE to StrategyVersion execution-regime seam
  with a machine-checkable ExecutionEvidenceBindingV1 so a PROMOTE accepted
  under execution regime A can no longer materialize a StrategyVersion
  requesting a materially different execution regime B. Quotes are never fills.
managed_write_set:
- docs/tasks/EXECUTION_EVIDENCE_SEAM_V1.md
- catalog/schemas/execution_evidence_binding_v1.schema.json
- catalog/schemas/promotion_handoff_manifest_v1_1.schema.json
- src/solana_alpha_lab/factory/promotion_handoff.py
- src/solana_alpha_lab/factory/experiment_evidence.py
- src/solana_alpha_lab/factory/application.py
- src/solana_alpha_lab/factory/owner_language.py
- tests/test_execution_evidence_seam_v1.py
- tests/test_science_to_strategy_handoff_v1.py
- tests/test_experiment_evidence_decision_v1.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- configs/ci_test_shards_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- NO_MERGE_AUTHORITY_STOP_BEFORE_MERGE
- UNRESOLVED_REFERENCE_HANDOFF_92147
- SCIENCE_REDESIGN_REQUESTED
- LIVE_EXECUTION_OR_PROVIDER_CALL
- HISTORICAL_DECISION_EVENT_REWRITE
context_requirements:
  catalog_asset_ids:
  - SCHEMA-EXECUTION-EVIDENCE-BINDING-V1-001
  - SCHEMA-PROMOTION-HANDOFF-MANIFEST-V1-1-001
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# EXECUTION_EVIDENCE_SEAM_V1 — Execution evidence seam

## Objective

Close the scientific-PROMOTE → StrategyVersion execution-regime seam with a
machine-checkable binding: a scientific `PROMOTE` accepted under execution
regime A can no longer lead to a `StrategyVersion` requesting a materially
different execution regime B. Quotes are never fills.

## Material dimensions (V1)

1. Exact `ExperimentSpec` identity (`experiment_id`, `experiment_spec_sha256`).
2. Population scope (`population_ref`).
3. Tested notional (each regime owns its own denominator).
4. Decision-time entry/exit quote evidence (`DECISION_TIME_QUOTE_PAIR_V1`).
5. Failure denominator accounting
   (`two_way_n + entry_only_n + no_entry_n + unknown_n = population_n`).
6. Scientific fee assumption (`strategy_fee_bps_assumption`, never total
   roundtrip friction).
7. Execution-cost evidence provenance (`cost_evidence_refs` with record and
   payload hashes).

## Deliverables

- `smial.execution-evidence-binding` schema v1.0.
- `promotion_handoff_manifest` v1.1 schema with immutable binding reference;
  version dispatch 1.0/1.1; historical v1.0 semantics unchanged.
- PROMOTE payload freezes `ExecutionEvidenceBindingV1`; new scientific
  obligation `EXECUTION_REGIME_BINDING` required for new PROMOTEs.
- Handoff `CHECK/RENDER/VERIFY` compatibility blockers:
  `EXECUTION_EVIDENCE_BINDING_GAP`, `EXECUTION_REGIME_MISMATCH`,
  `NOTIONAL_EVIDENCE_MISMATCH`, `COST_ASSUMPTION_BINDING_GAP`,
  `COST_EVIDENCE_MISMATCH`.
- Owner readout labels for the new obligation, blockers and next actions.
- Catalog/generated propagation and tests T1–T20.

## Non-goals

- No SMIAL science redesign; no LIVE execution; no provider/API/RPC/WSS calls;
  no VPS/runtime access; no wallet/signer/transaction/real money; no
  scientific decision rewrite, historical `DECISION_EVENT` rewrite, or new
  market-data collection; no Trigger/Jupiter/Hummingbot work; no merge or
  deployment authority.

## DoD

- New PROMOTE without a valid binding is blocked fail-closed.
- Old v1.0 manifests keep validating and surface
  `EXECUTION_EVIDENCE_BINDING_GAP` on new materialization; never rewritten.
- `strategy_version_v1_1.schema.json` unchanged (verified by byte identity).
- Local verification green: seam tests, handoff tests, evidence decision
  tests, catalog validation, harness check.
