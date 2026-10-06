---
task_id: FORGE_LIST_AWARE_RESEARCH_VERTICAL_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-07'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417
  expected_upstream: origin/main
  expected_upstream_oid: 77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417
  expected_branch: claude/forge-list-aware-research-vertical-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make source lists a first-class research dimension of the Forge for
  OPPORTUNITY_EPISODES: one owner for list definitions, membership evidence,
  selector grammar and research scope; list-only, numeric-in-scope and mixed
  questions through query 1.2, candidate freeze, Critic, classification,
  DocumentRunner, prior memory and replay; and a real additive episode normalized
  profile through the existing ladder, without a fake CONTROL and without
  changing capture, the frozen newborn normalized trajectory or any live state.
managed_write_set:
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- catalog/generated/asset_edges.json
- catalog/schemas/forge_input_receipt_v1.schema.json
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- configs/hfic_representation_ladder_v1.yaml
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/FACTORY_SEMANTIC_MAP.md
- docs/contracts/forge_list_aware_research_scope_v1.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- docs/tasks/FORGE_LIST_AWARE_RESEARCH_VERTICAL_V1.md
- docs/evidence/forge_list_aware_research_vertical_v1/**
- scripts/hypothesis_forge.py
- src/solana_alpha_lab/factory/forge_input_receipt.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_identity.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_prior_memory.py
- src/solana_alpha_lab/factory/hfic_representation_ladder.py
- src/solana_alpha_lab/factory/hfic_research_scope.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/normalized_trajectory_episodes_v1.py
- tests/benchmark_list_scope_v1.py
- tests/test_forge_representation_ladder_v1.py
- tests/test_hfic_cli.py
- tests/test_hfic_list_aware_vertical_v1.py
- tests/test_hfic_list_scope_executor_v1.py
- tests/test_hfic_research_scope_v1.py
- tests/test_normalized_trajectory_episodes_v1.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_MERGE_DEPLOY_SETTINGS_TIMER_CHANGES
- STOP_VPS_PROVIDER_CALLS_NEW_CREDENTIALS_OR_SECRET_ACCESS
- STOP_PRODUCTION_DATA_REAL_SCIENTIFIC_LOOK_OR_HOLDOUT_VALUES
- STOP_NEW_COLLECTOR_EVALUATOR_DATABASE_SERVICE_OR_DEPENDENCY
- STOP_CAPTURE_POPULATION_GRID_CAP_OR_T0_CHANGE
- STOP_LIVE_BUDGET_RAISE_RETENTION_OR_CLEANUP
- STOP_CHANGE_OF_FROZEN_NEWBORN_NORMALIZED_TRAJECTORY_V1
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-TEMPORAL-DISCOVERY-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
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
    ARCHITECTURE_DECISIONS: [docs/contracts/forge_list_aware_research_scope_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_list_aware_research_vertical_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/forge_list_aware_research_vertical_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/forge_list_aware_research_vertical_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_LIST_AWARE_RESEARCH_VERTICAL_V1

ENTRY_DECISION: START_AS_WRITTEN (PR-A of OPPORTUNITY_EPISODES_SOURCE_STRATIFICATION_V1,
statement 2.0). SPEC_ROUTE: BOTH (owner PRD+SSD V2 plus the contract
`docs/contracts/forge_list_aware_research_scope_v1.md`). Route
DIRECT_CLAUDE_CODE_DELIVERY, actor CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION:
SOL_XHIGH (owner-selected for the chain). Authority: the owner's explicit
2026-10-07 instruction naming this atom; expected base `77eb427a` (design anchor
equals current `origin/main`, re-verified at Entry).

DECISION_DELTA: the owner can ask the Forge about a source-list group (membership
as universe, as the whole signal, or as a fixed slice) and receive a computed,
frozen, replayable result instead of a pooled answer with the lists lost.
UNCERTAINTY_REMOVED: whether list membership already stored in every sealed
release can reach formulation, numerical evaluation, candidate/Critic, experiment
and memory without a second parser, and whether the legacy normalized trajectory
can serve episodes.
CAPABILITY_OR_EVIDENCE: `hfic_research_scope` (one owner), query 1.2, scope-bound
identity through candidate, Critic, classification, recipe replay and prior axes,
`LOCAL_MEMBERSHIP_SNAPSHOT_V1`, additive `NORMALIZED_TRAJECTORY_EPISODES_V1` in the
existing ladder, and a production-shaped synthetic vertical.
Cheapest falsifier (exact base, before any change): a scope field on a 1.1 query is
accepted with unchanged identity; a list-only query is refused `FEATURE_INVALID`;
`overlap` in frames.json is read by no research path; the legacy normalized
projection has no episode path. FALSIFIER_AFTER: the same four boundaries are
refused/served by the owner, verified in `test_hfic_list_aware_vertical_v1`.

Required invariants: UNKNOWN membership is never FALSE and refuses before values;
a rule is hashed by its definitions, never by display names or realized members;
the unscoped path and every legacy hash, recipe and result stay byte-identical;
a reader that does not know query 1.2 refuses instead of computing pooled.

DoD: PRD V2 D01-D24 and D28 as relevant to PR-A (D25-D27 belong to PR-B):
literal oracle of section 17.1; list-only, numeric-in-scope and mixed results;
admission-frame membership with normal, incomplete, tampered and recovered
frames; protected identity never emitted; local snapshots registered once,
future-only, five-source composition without consumer changes; formulation
context in the emitted preflight packet; candidate/Critic/classification/
DocumentRunner exact-scope binding with refusals; scoped prior memory;
episode normalized profile through the ladder and ordinary lifecycle; cold
replay and next-period; bounded benchmark.

Non-goals: PR-B budgets/runtime policy, capture changes, dynamic post-T0
membership, causal or factorial analysis, any live or VPS action, real
scientific looks, new provider/evaluator/service/dependency.
Reuse/build: WRAP existing episode release, temporal evaluator, ordinary
operation, ladder and session owners; the only new modules are the scope owner
and the pure episode profile. No dependency.
Risks: scope lost in a consumer (guarded by binding mismatch refusals), legacy
drift (golden and regression runs), packet capacity (typed refusal),
confusing observational membership with a causal claim (non-claims).
Rollback: owner-gated code revert; stored scoped results stay readable as plain
JSON; an older reader refuses query 1.2.
STOP: merge boundary; never merge in this atom.
NEXT: exact-head CI, merge-readiness, owner phrase; then PR-B on the accepted base.
REPLAN_TRIGGER: a second blocker at the same seam after an owner repair, or scope
reaching a stop condition.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE.

Required reviews: isolated code, goal/DoD, architecture (semantic premise packet)
and owner-UX (new operator commands and readouts).
