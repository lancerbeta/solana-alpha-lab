---
task_id: HFIC_CRITIC_PRIOR_MEMORY_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-08'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 19ad057614f0fd4aa4313b409606d205ff9cb290
  expected_upstream: origin/main
  expected_upstream_oid: 19ad057614f0fd4aa4313b409606d205ff9cb290
  expected_branch: cursor/hfic-critic-prior-memory-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Bind a complete bounded historical prior-memory snapshot into the fresh
  HFIC-V1.2 Critic packet so an isolated Critic cannot miss an eligible
  HYPOTHESIS_VERSION solely because Forge lexical top-N omitted it. Fail closed
  on capacity. Do not change rank_prior_candidate_ids or Prompt A search.

managed_write_set:
  - docs/tasks/HFIC_CRITIC_PRIOR_MEMORY_CLOSURE_V1.md
  - src/solana_alpha_lab/factory/hfic_prior_memory.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - .cursor/commands/independent-hypothesis-critic.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_critic_prior_memory_closure_v1.py
  - tests/test_hfic_operational_closure_v1.py
  - tests/test_hfic_session.py
  - tests/test_hypothesis_forge_independent_critic_v1.py
  - docs/reports/hfic_critic_prior_memory_closure/a1_owner_readout_v1.md
  - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - RANKER_OR_MAX_RANKED_PRIORS_CHANGE
  - AUTO_SESSIONS_PER_EPOCH_CHANGE
  - RUNNER_UP_LIFECYCLE_CHANGE
  - RAG_EMBEDDINGS_OR_NEW_DATABASE
  - SILENT_PRIOR_MEMORY_TRUNCATION
  - HISTORICAL_V11_READABILITY_LOST
  - ACTIVE_RDP_WRITE
  - REAL_HYPOTHESIS_FORGE_SLASH
  - PROVIDER_API_RPC_WSS_REQUIRED

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
      - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_critic_prior_memory_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CRITIC_PRIOR_MEMORY_CLOSURE_V1

SPEC_ROUTE=NONE. Exact owner atom: Critic prior-memory closure for F2.

## DECISION_DELTA

Fresh HFIC-V1.2 freeze binds a complete bounded prior-memory snapshot into
`CRITIC_INPUT_PACKET`. Isolated Critic uses that packet as sole research-memory
input. Capacity overflow is `PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED` before
persist. Ranker shortlist unchanged.

## UNCERTAINTY_REMOVED

Whether packet-isolated Critic can miss an eligible historical hypothesis solely
because lexical top-N omitted it.

## CAPABILITY_OR_EVIDENCE

Snapshot builder + v1.2 packet field + T1–T7 + packet-only Critic smoke.

## STOP

Exact-head CI. Merge-readiness. Owner phrase. No active RDP. No real slash.

## NEXT

Owner merge phrase. Residual F3 runner-up lifecycle and calibration rebase remain
out of scope.
