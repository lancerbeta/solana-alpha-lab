---
task_id: COMPOUND_TEMPORAL_DISCOVERY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-27'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 424e28990478102dc18a259f5509f40ee31d54b1
  expected_upstream: origin/main
  expected_upstream_oid: 424e28990478102dc18a259f5509f40ee31d54b1
  expected_branch: cursor/compound-temporal-discovery-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Let one ordinary hypothesis-forge run move from simple screens to compound
  temporal questions inside the same budget, compute a relative price proxy and
  an explicit cost sensitivity, and carry that meaning into the frozen candidate,
  the independent Critic packet, and the existing fixed-time experiment consumer.
  No second Forge, no market run, and no change to frozen NORMALIZED_TRAJECTORY_V1.

managed_write_set:
  - docs/tasks/COMPOUND_TEMPORAL_DISCOVERY_V1.md
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - scripts/hypothesis_forge.py
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - configs/experiment_capability_registry_v2.yaml
  - catalog/schemas/hfic_temporal_query_v1.schema.json
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/oracle_temporal_arithmetic_v1.py
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_temporal_owner_path_v1.py
  - tests/test_discovery_evidence_release_bridge.py
  - docs/evidence/compound_temporal_discovery/agent_attempt_1_query.json
  - docs/evidence/compound_temporal_discovery/agent_attempt_1_result.json
  - docs/evidence/compound_temporal_discovery/agent_attempt_1_critic.json
  - docs/evidence/compound_temporal_discovery/execution_evidence_v1.json
  - docs/evidence/compound_temporal_discovery/a1_delivery_completion_evidence_v1.json
  - docs/evidence/compound_temporal_discovery/a1_delivery_independent_review_v1.json
  - docs/evidence/compound_temporal_discovery/a1_delivery_factory_fit_v1.json
  - docs/reports/compound_temporal_discovery/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - MARKET_FORGE
  - MARKET_CRITIC
  - PRODUCTION_RDP_EXPERIMENT
  - PROVIDER_API_RPC_WSS
  - HOLDOUT_VALUE_READ
  - NEW_DEPENDENCY
  - WALLET_OR_SIGNER
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
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
    LIFECYCLE:
      - .agents/skills/hypothesis-forge/SKILL.md
      - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
      - docs/contracts/normalized_trajectory_v1_capability_contract.md
    DELIVERY_EVIDENCE:
      - docs/evidence/compound_temporal_discovery/a1_delivery_completion_evidence_v1.json
      - docs/evidence/compound_temporal_discovery/a1_delivery_independent_review_v1.json
      - docs/evidence/compound_temporal_discovery/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COMPOUND_TEMPORAL_DISCOVERY_V1

SPEC_ROUTE=DESIGN_SPEC

Design anchor `c7a081e92443dfd09977aad9f6c7446f79127405`. Execution base is
`origin/main` `424e28990478102dc18a259f5509f40ee31d54b1`, which already contains
merged PR #347. Route `DIRECT_CURSOR_DELIVERY`.

MODEL_EFFORT_RECOMMENDATION: `SOL_XHIGH` for PIT, identity, and claim boundaries.
This session continues on the assigned Cursor executor.

## Task Outcome Brief

- **Owner decision:** one ordinary `/hypothesis-forge` can escalate from a simple
  screen to a compound temporal question before freeze, inside the existing
  6 main + 2 adaptive budget.
- **Named consumer:** the next separately authorized research run, the frozen
  Critic packet, and `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`.
- **Cheapest falsifier:** synthetic publication through the real binder, then
  one temporal query whose relative target and cost label survive freeze and
  the registered offline consumer.
- **Non-goals:** market Forge, market Critic, production RDP experiment,
  provider calls, a new backtester, and any edit to frozen trajectory V1.
- **Evidence budget:** disposable synthetic stores and one isolated agent
  acceptance. No live ResearchStore write.

## Decision record

- **DECISION_DELTA:** compound questions are a pre-freeze tier of ordinary
  discovery, not a new scientific slot.
- **UNCERTAINTY_REMOVED:** relative returns, denominators, and the assumption
  stress proxy are computed by code and labeled apart from `NetReturn`.
- **CAPABILITY_OR_EVIDENCE:** `smial.hfic-temporal-query` version 1.0 on the
  existing ResearchStore and Forge CLI.
- **STOP:** merge still waits for the exact owner phrase. The next scientific
  step is one separately authorized research run.
- **NEXT:** do not build another layer in this atom.
- **REPLAN_TRIGGER:** a second repair of the same seam that needs a new store,
  lifecycle, or provider.
