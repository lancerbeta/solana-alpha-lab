---
task_id: HFIC_EPISTEMIC_MEMORY_SEMANTICS_V1
task_version: '1.0'
status: VALIDATED
as_of: '2026-08-30'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 10aa265690c2c7a3fce5cd616b730a23daf34440
  expected_upstream: origin/main
  expected_upstream_oid: 10aa265690c2c7a3fce5cd616b730a23daf34440
  expected_branch: cursor/hfic-epistemic-memory-semantics-v1
  dirty_mode: ALLOW_REPORTED
objective: Make Hypothesis Forge evidence_epoch denote exogenous / decision-bearing
  research truth only, and admit canonical RDP family closures into
  closed_family_ledger without treating HFIC self-memory as new evidence.
managed_write_set:
- docs/tasks/HFIC_EPISTEMIC_MEMORY_SEMANTICS_V1.md
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_provenance.py
- tests/test_hfic_epistemic_memory_semantics.py
- tests/test_hfic_session.py
- tests/test_hfic_forge_context_and_no_worthy.py
- configs/hypothesis_forge_independent_critic_v1.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_factory_fit_v1.json
- docs/evidence/hfic_epistemic_memory_semantics/a1_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- EXPERIMENT_EXECUTION
- HOLDOUT_ACCESS
- DESTRUCTIVE_RDP_MUTATION
- HISTORICAL_RESEARCH_REWRITE
- NEW_FULL_FORGE_SEARCH_TO_PROVE_FIX
- H900_ESTIMAND_REPAIR
- CLOSED_FAMILY_REOPEN
- TWO_RUNG
context_requirements:
  catalog_asset_ids:
  - CTRL-HFIC-EPISTEMIC-MEMORY-SEMANTICS-001
  - TEST-HFIC-EPISTEMIC-MEMORY-SEMANTICS-001
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
    - docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_completion_evidence_v1.json
    - docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_independent_review_v1.json
    - docs/evidence/hfic_epistemic_memory_semantics/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_EPISTEMIC_MEMORY_SEMANTICS_V1

## SPEC_ROUTE

`NONE` — this file is the exact task contract.

## PRD-lite

- Owner decision: Forge must not reopen a completed search because it wrote
  its own candidates/receipts, and must see authoritative RDP family
  closures.
- Named consumer: `/hypothesis-forge` preflight / freeze / Independent Critic.
- Cheapest falsifier: tests A1–A5 plus one read-only active-RDP preflight.
- Non-goals: H900 estimand, holder-concentration veto, provider calls,
  experiment execution, historical rewrite.
- Replan trigger: a historical closure cannot be proven authoritative from
  existing typed RDP truth.

## Invariants

A. `evidence_epoch` changes only when exogenous / decision-bearing research
   truth changes. Endogenous HFIC search memory does not.

B. Canonical decision-bearing family closure already persisted in active RDP
   is visible in `closed_family_ledger`. An arbitrary dataset label cannot
   close a family.

## Authority distinction

Endogenous HFIC memory is identified by existing record semantics in
`is_hfic_record` (protocol field, HFIC identity, session id, Forge artifact
kind). Not by blacklisting one `record_id`.

RDP family closure is admitted only from a typed `smial.*.runtime-receipt`
dataset `.decision.json` sidecar bound to a published dataset fingerprint,
with `scientific_terminal` matching `CLOSE_*` / `PARK_*` and
`outcome_consumed=true`. Labels-only `CLOSE_*` text is fail-closed.
