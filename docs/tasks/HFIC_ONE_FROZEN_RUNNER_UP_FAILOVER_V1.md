---
task_id: HFIC_ONE_FROZEN_RUNNER_UP_FAILOVER_V1
task_version: '1.0'
status: READY
as_of: '2026-09-08'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: c0b4c1a70072044545f7c9cec071e1b769024617
  expected_upstream: origin/main
  expected_upstream_oid: c0b4c1a70072044545f7c9cec071e1b769024617
  expected_branch: cursor/hfic-one-frozen-runner-up-failover-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  When the originally selected candidate receives a final KILL_* terminal, the
  one runner-up already selected and frozen BEFORE the first Critic receives
  exactly one independent Critic screening in the same HFIC session / evidence
  epoch / search budget. No regeneration, second AUTO search, candidate shopping,
  or post-C1 C2 mutation.

managed_write_set:
  - docs/tasks/HFIC_ONE_FROZEN_RUNNER_UP_FAILOVER_V1.md
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - schemas/research_memory_projection_v1.sql
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - .cursor/commands/independent-hypothesis-critic.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_one_frozen_runner_up_failover_v1.py
  - tests/test_hfic_session.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_operational_closure_v1.py
  - tests/test_hfic_provenance_clock.py
  - tests/test_observation_fast_lane_routing_closure.py
  - tests/test_hfic_manual_grounding_contract_diagnostics_v1.py
  - tests/test_hfic_epistemic_memory_semantics.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - docs/reports/hfic_one_frozen_runner_up_failover/a1_owner_readout_v1.md
  - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - RUNNER_UP_REGENERATED_AFTER_C1
  - SECOND_AUTO_SEARCH_OR_NEW_FOCUS
  - N_CANDIDATE_TOURNAMENT_MACHINERY
  - PACKET_VERSION_13_SEMANTICS_MUTATED
  - HISTORICAL_SESSION_IDENTITY_REWRITTEN
  - ACTIVE_RDP_WRITE
  - REAL_HYPOTHESIS_FORGE_SLASH
  - PROVIDER_API_RPC_WSS_REQUIRED
  - CALIBRATION_MEMORY_REBASE

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
      - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_one_frozen_runner_up_failover/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_ONE_FROZEN_RUNNER_UP_FAILOVER_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=NONE. Exact owner atom: F3 one frozen runner-up failover.

## DECISION_DELTA

Fresh freeze builds two Critic packets before Critic #1: C1 primary and C2
runner-up, same session/epoch/prior_memory snapshot. Final C1 `KILL_*` parks
the session in `RUNNER_UP_AWAITING_CRITIC` and gives C2 exactly one independent
screen. No C3, no C2 revise, no new AUTO slot.

## UNCERTAINTY_REMOVED

Whether a pre-frozen distinct runner-up is mechanically discarded when the
Forge-selected primary dies on a final KILL.

## CAPABILITY_OR_EVIDENCE

Pre-frozen C2 packet + failover state machine + receipt v1.3 additive identity
+ T1–T11 on disposable ResearchStore.

## STOP

Exact owner merge gate after CI and merge-readiness.

## NEXT

Calibration-memory rebase remains explicit residual, not this atom.
