---
task_id: HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1
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
  expected_base: f910e3d19d35e24b954aef0e5948c2f887b0bc33
  expected_upstream: origin/main
  expected_upstream_oid: f910e3d19d35e24b954aef0e5948c2f887b0bc33
  expected_branch: cursor/hfic-forge-prior-context-capacity-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Repair the measured Forge routing dead-end where eligible search-memory
  bodies from a completed HFIC cycle make the next distinct-focus
  FORGE_CONTEXT_PACKET exceed 16384 bytes. Introduce a Forge-specific
  ranked-prior projection, distinguish capacity vs missing-body terminals,
  and leave Critic prior_memory, ranker, budgets, quarantine, and
  representation semantics unchanged.

managed_write_set:
  - docs/tasks/HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1.md
  - src/solana_alpha_lab/factory/hfic_prior_memory.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - tests/test_hfic_forge_prior_context_capacity_repair_v1.py
  - tests/test_hfic_reopened_prior_search_routing_v1.py
  - docs/reports/hfic_forge_prior_context_capacity_repair/a1_owner_readout_v1.md
  - docs/reports/hfic_forge_prior_context_capacity_repair/a1_consumer_map_v1.md
  - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_factory_fit_v1.json
  - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_active_rdp_preview_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - PACKET_LIMIT_RAISE
  - RANKER_OR_SEARCH_BUDGET_CHANGE
  - RANKED_PRIOR_DROP
  - ARBITRARY_TEXT_TRUNCATION
  - CRITIC_PRIOR_MEMORY_SEMANTICS_CHANGE
  - MEMORY_QUARANTINE_OR_RESET
  - REPRESENTATION_SEMANTICS_CHANGE
  - PROVIDER_OR_NEW_DATA
  - NEW_DB_SERVICE_OR_RAG
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
      - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_forge_prior_context_capacity_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1

SPEC_ROUTE=NONE. Exact owner atom: restore next distinct-focus Forge
reachability after CONTROL-enriched search memory without changing Critic
memory, ranker, budgets, quarantine, or representation.

## Task Outcome Brief

- **Owner decision:** Prompt A must not die on capacity after a valid completed
  HFIC cycle keeps eligible prior bodies.
- **Product outcome:** `FORGE_CONTEXT_PACKET <= 16384` with one-to-one ranked
  prior Forge projections; capacity vs missing-body terminals distinguished;
  Critic prior memory unchanged.
- **Named consumer:** ordinary `/hypothesis-forge` with a non-AUTO distinct
  focus on the current first-cohort evidence epoch (e.g. `IDENTIFIABLE_NOW`).
- **Cheapest falsifier:** T1–T7 in
  `tests/test_hfic_forge_prior_context_capacity_repair_v1.py` plus PR308
  reopened-prior / vision / representation isolation suites.
- **Terminal:** `HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_PASS` after reviews,
  exact-head CI and merge-readiness. Stop before owner merge phrase. Do not run
  the real IDENTIFIABLE_NOW slash in this atom.
- **Non-goals:** packet limit raise, ranker/budget change, quarantine of 60FB,
  Critic memory thinning, representation probe, RAG/new memory platform.
- **Evidence budget:** disposable fixtures + read-only local RDP measurement.
  No intentional active-RDP mutation for demo.
- **SPEC_ROUTE=NONE**

## Decision capsule

- `DECISION_DELTA`: Forge-specific ranked-prior projection + typed capacity
  terminal; Critic capsules untouched.
- `UNCERTAINTY_REMOVED`: IDENTIFIABLE_NOW dead-end after 60FB is capacity /
  projection, not missing bodies or search-policy exhaustion.
- `CAPABILITY_OR_EVIDENCE`: measured packet fit + START_NEW_SESSION reachability
  without quarantine.
- `STOP`: merge-readiness; owner phrase gate.
- `NEXT`: after merge, owner may run ordinary IDENTIFIABLE_NOW Forge.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. Restores already-designed lifecycle continuity.
`PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.
