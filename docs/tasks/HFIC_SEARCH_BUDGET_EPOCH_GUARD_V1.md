---
task_id: HFIC_SEARCH_BUDGET_EPOCH_GUARD_V1
task_version: '1.0'
status: READY
as_of: '2026-09-16'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 6f144de9be51b85195bdffe2c7277580686295fe
  expected_upstream: origin/main
  expected_upstream_oid: 6f144de9be51b85195bdffe2c7277580686295fe
  expected_branch: cursor/hfic-search-budget-epoch-guard-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Make HFIC search-budget accounting conform to the canonical contract
  (auto_sessions_per_evidence_epoch=1, distinct_focus_sessions_per_evidence_epoch=3)
  by counting AUTO and distinct-focus sessions against evidence_epoch_sha256
  only, without resetting budget when memory_eligibility_sha256 changes.
  Keep memory eligibility inside search_key / same_focus / exact replay identity.

managed_write_set:
  - docs/tasks/HFIC_SEARCH_BUDGET_EPOCH_GUARD_V1.md
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - tests/test_hfic_search_budget_epoch_guard_v1.py
  - tests/test_hfic_operational_memory_quarantine_v1.py
  - docs/reports/hfic_search_budget_epoch_guard/a1_owner_readout_v1.md
  - docs/evidence/hfic_search_budget_epoch_guard/a1_active_rdp_preview_v1.json
  - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - catalog/assets/core.yaml

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - SEARCH_IDENTITY_SEMANTICS_CHANGE
  - PACKET_BUDGET_CHANGE
  - PRIOR_MEMORY_ROUTING_CHANGE
  - QUARANTINE_POLICY_CHANGE
  - RANKER_OR_CANDIDATE_POLICY_CHANGE
  - CRITIC_OR_REPRESENTATION_CHANGE
  - ACTIVE_RDP_WRITE
  - REAL_IDENTIFIABLE_NOW_FORGE_SLASH

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
      - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_search_budget_epoch_guard/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_SEARCH_BUDGET_EPOCH_GUARD_V1

SPEC_ROUTE=NONE. Exact owner atom: epoch-scoped search-budget accounting.

## Task Outcome Brief

- **Owner decision:** quarantine/restore must not reset AUTO or distinct-focus
  budget while evidence epoch is unchanged.
- **Product outcome:** budget uses all HFIC sessions with the same
  `evidence_epoch_sha256`; `memory_eligibility_sha256` stays in search identity
  only.
- **Named consumer:** ordinary `/hypothesis-forge` preflight / Prompt A routing.
- **Cheapest falsifier:** `tests/test_hfic_search_budget_epoch_guard_v1.py` plus
  read-only IDENTIFIABLE_NOW preflight preview.
- **Terminal:** reviews, exact-head CI, merge-readiness; owner authorized
  guarded merge for this atom after machine-rendered phrase.
- **Non-goals:** packet bound changes, prior-memory/ranker/Critic/representation
  changes, live IDENTIFIABLE_NOW synthesis.
- **SPEC_ROUTE=NONE**

## Decision capsule

- `DECISION_DELTA`: `same_epoch_for_budget` ignores memory eligibility.
- `UNCERTAINTY_REMOVED`: budget is per evidence epoch as configured.
- `CAPABILITY_OR_EVIDENCE`: unit suite + real-state budget readout.
- `STOP`: post-merge readback after authorized guarded merge.
- `NEXT`: owner may run ordinary IDENTIFIABLE_NOW Forge after merge.
