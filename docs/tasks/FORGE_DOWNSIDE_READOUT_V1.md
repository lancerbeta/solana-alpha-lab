---
task_id: FORGE_DOWNSIDE_READOUT_V1
task_version: '1.0'
status: READY
as_of: '2026-10-03'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CODEX_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 8e72dbb492d1d430231f9e225e6000be0e1d6922
  expected_upstream: origin/main
  expected_upstream_oid: 8e72dbb492d1d430231f9e225e6000be0e1d6922
  expected_branch: codex/forge-downside-readout-v1
  dirty_mode: FORBIDDEN

objective: >-
  Add one fixed downside description of existing PRICE_RELATIVE_PROXY samples
  to fresh V5 temporal results, persisted replay, Prompt A, Critic and owner
  readout. Permit one explicit source-bound readout-only V4-to-V5 calculation
  revision for a closed ordinary slot without changing its trial, terminal,
  history, budget, input or market identity. Prove the real D2 saved shape in
  a disposable copy and perform bounded blind LLM smoke.

managed_write_set:
  - docs/tasks/FORGE_DOWNSIDE_READOUT_V1.md
  - docs/contracts/forge_downside_descriptive_v1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_temporal_result_coherence_v1.py
  - tests/test_hfic_ordinary_operation_v1.py
  - tests/test_hfic_ordinary_operation_acceptance_v1.py
  - tests/test_hfic_grounded_discovery_v1.py
  - tests/test_hfic_temporal_owner_path_v1.py
  - tests/test_forge_downside_readout_v1.py
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/forge_downside_readout_v1/**

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - REAL_SCIENTIFIC_OR_RUNTIME_WRITE
  - NEW_SCIENTIFIC_LOOK_OR_BUDGET
  - HISTORICAL_TRIAL_OR_TERMINAL_REWRITE
  - MARKET_OR_SPEC_INPUT_IDENTITY_CHANGE
  - NEXT_COHORT_ACCESS
  - PROVIDER_OR_VPS_CALL
  - UNRELATED_AUTO_REPAIR
  - MERGE_BEFORE_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
      - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
      - docs/contracts/forge_downside_descriptive_v1.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: BOTH

Authoritative owner-approved design input: `FORGE_DOWNSIDE_READOUT_V1_PRD_SSD.md`
with calibration `SMIAL-FORGE-CALIB-20261003-G1G6` and gold SHA
`57444d7ffb0f634ea4d2b5075cee1da498c2a94c7c1df76449a1d99b4fa98866`.
The durable product semantics are in
`docs/contracts/forge_downside_descriptive_v1.md`.

DECISION_DELTA: >-
  Existing admitted return samples expose fixed descriptive downside support,
  event rates, quantiles, ES10 and loss concentration. A coherent closed V4
  result may receive an explicit append-only V5 readout revision while its
  scientific slot and frozen assessment remain closed.

UNCERTAINTY_REMOVED: >-
  Whether G3 tail-frequency differences survive the persisted and model
  packet path, and whether the exact closed D2 source can be enriched through
  the public CLI on an isolated copy without new science or history mutation.

CAPABILITY_OR_EVIDENCE: >-
  One V5 calculator and coherence owner; cold replay; real Prompt A, Critic and
  owner packets; public closed-source revision and retry; five vertical proofs
  including isolated D2 and bounded blind LLM smoke.

STOP: >-
  Stop after unchanged exact-head CI and machine merge-readiness reports
  ready_for_owner_phrase=true. No merge or real scientific/runtime writes.

NEXT: >-
  After guarded merge and post-merge readback under a separate owner gate,
  perform one source-bound D2 readout-only enrichment, cold readback and stop.
