---
task_id: HFIC_LEGACY_SCIENCE_REBASE_AND_SUPPRESSION_SEMANTICS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-30'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f98d41a4813d0ec73ffcbbb684bbad64577d8ccd
  expected_upstream: origin/main
  expected_upstream_oid: f98d41a4813d0ec73ffcbbb684bbad64577d8ccd
  expected_branch: cursor/hfic-legacy-science-rebase-and-suppression-semantics-v1
  dirty_mode: ALLOW_REPORTED
objective: Rebase Hypothesis Forge suppression semantics so PARK is not a scientific
  hard-close, CLOSE is not silently family-global, and legacy measurement-limited
  verdicts do not block a materially changed estimand, while prior work remains visible.
managed_write_set:
- docs/tasks/HFIC_LEGACY_SCIENCE_REBASE_AND_SUPPRESSION_SEMANTICS_V1.md
- src/solana_alpha_lab/factory/hfic_suppression_semantics.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_session.py
- scripts/hypothesis_forge.py
- tests/test_hfic_legacy_science_rebase.py
- tests/test_hfic_cli.py
- tests/test_hfic_epistemic_memory_semantics.py
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/hfic_legacy_science_rebase/a1_inventory_v1.json
- docs/evidence/hfic_legacy_science_rebase/a1_acceptance_v1.json
- docs/evidence/hfic_legacy_science_rebase/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_legacy_science_rebase/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_legacy_science_rebase/a1_delivery_factory_fit_v1.json
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
- NEW_PROVIDER_OR_DATA_SOURCE
- AMBIGUOUS_MATERIAL_HISTORICAL_DECISION
- PRODUCT_ESTIMAND_CHANGE_BEYOND_CANONICAL_DELTAS
context_requirements:
  catalog_asset_ids:
  - CTRL-HFIC-LEGACY-SCIENCE-REBASE-001
  - TEST-HFIC-LEGACY-SCIENCE-REBASE-001
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
    - docs/evidence/hfic_legacy_science_rebase/a1_delivery_completion_evidence_v1.json
    - docs/evidence/hfic_legacy_science_rebase/a1_delivery_independent_review_v1.json
    - docs/evidence/hfic_legacy_science_rebase/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_LEGACY_SCIENCE_REBASE_AND_SUPPRESSION_SEMANTICS_V1

## SPEC_ROUTE

`NONE` — this file is the exact task contract.

## PRD-lite

- Owner decision: routine `/hypothesis-forge` must remember prior work and
  negative evidence without treating owner-priority PARK as scientific
  refutation, without hard-closing a broader family from a scope-limited
  CLOSE, and without using a legacy measurement-limited verdict as a ban
  on a materially changed estimand.
- Named consumer: `/hypothesis-forge` preflight / freeze closed_family_ledger.
- Cheapest falsifier: tests T1–T10 plus one read-only active-RDP preflight
  after append-only science-memory rebase.
- Non-goals: autonomous generator, experiment execution, new market data,
  holdout, provider/API, H900 estimand repair, rewriting historical receipts.
- Replan trigger: an ambiguous material historical decision whose typed
  meaning cannot be recovered from the source payload.

## DECISION_DELTA

`reopen_forbidden` is derived from typed decision meaning and scope, not
from a `CLOSE_*` / `PARK_*` prefix.

## UNCERTAINTY_REMOVED

Whether PARK_H11 / PARK_H13 and route-scoped CLOSE terminals can force
NO_WORTHY by false scientific suppression.

## CAPABILITY_OR_EVIDENCE

Canonical consumer-layer classifier plus append-only science-rebase
DECISION_EVENT. Historical Git/RDP bytes are not rewritten.

## STOP

Exact-head CI green. Owner merge phrase. No full Forge search.

## NEXT

Routine `/hypothesis-forge` on the post-rebase evidence epoch, only after
merge if the owner invokes it.
