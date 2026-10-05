---
task_id: OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-05'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: de20465e04af13f5226b1e05b4fe6ffd1ed6575a
  expected_upstream: origin/main
  expected_upstream_oid: de20465e04af13f5226b1e05b4fe6ffd1ed6575a
  expected_branch: claude/opportunity-episodes-jupiter-vertical-slice-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  A fresh process receives Jupiter-shaped OPPORTUNITY_EPISODES evidence through
  the ordinary production path: protected nomination frame, committed episode
  T0, versioned 72h schedule with explicit gaps, real publication, capture-side
  freeze/export, workstation build/seal/verify/import, generated population
  card, ordinary Forge mixed PRICE+LIQUIDITY+HOLDERS+TIME question, synthetic
  candidate/Critic lifecycle and detached numerical replay, while legacy
  BASE_X newborn semantics, hashes and readers stay unchanged.
managed_write_set:
- docs/tasks/OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- src/solana_alpha_lab/factory/opportunity_episodes.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/opportunity_episode_release.py
- src/solana_alpha_lab/factory/observation_schedule.py
- src/solana_alpha_lab/factory/observation_schedule_compiler.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_primitives.py
- src/solana_alpha_lab/factory/observation_primitive_registry.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/collector_read_model.py
- src/solana_alpha_lab/factory/tokens_v2_typed_projection.py
- src/solana_alpha_lab/factory/live_cohort_schedule_artifact.py
- src/solana_alpha_lab/factory/live_cohort_vanilla_path.py
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- src/solana_alpha_lab/factory/live_cohort_to_forge.py
- src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
- src/solana_alpha_lab/factory/live_corpus_logical_rows.py
- src/solana_alpha_lab/factory/cohort_import_readback.py
- src/solana_alpha_lab/factory/forge_input_receipt.py
- src/solana_alpha_lab/factory/scientific_eligibility_projection.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_evidence_identity.py
- src/solana_alpha_lab/factory/hfic_research_universe_policy.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_grounding.py
- src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
- scripts/observation_schedule.py
- scripts/discovery_evidence_release.py
- scripts/hypothesis_forge.py
- configs/observation_primitive_registry_v1.yaml
- configs/opportunity_episodes_jupiter_core_v1.yaml
- configs/experiment_capability_registry_v2.yaml
- configs/factory_semantic_operability_v1.yaml
- catalog/schemas/opportunity_episode_schedule_v1.schema.json
- catalog/schemas/observation_primitive_descriptor_v1.schema.json
- catalog/schemas/hypothesis_forge_draft_v1_2.schema.json
- catalog/assets/*.yaml
- catalog/relations/**
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- .agents/skills/hypothesis-forge/SKILL.md
- tests/test_opportunity_episodes_*.py
- tests/fixtures/opportunity_episodes_v1/**
- tests/test_observation_primitive_registry*.py
- tests/test_hfic_cli.py
- docs/evidence/opportunity_episodes_jupiter_vertical_slice_v1/**
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_PROVIDER_API_RPC_WSS_CALL_OR_CREDENTIAL_READ
- STOP_LIVE_ACTIVATION_DEPLOY_SETTINGS_OR_SHARED_DATA_PLANE_WRITE
- STOP_PRODUCTION_IMPORT_REAL_SCIENTIFIC_LOOK_OR_HOLDOUT_VALUE_READ
- STOP_LEGACY_BASE_X_BIRTH_HASH_OR_CALCULATION_SEMANTICS_CHANGE
- STOP_NEW_IMPORTER_EVALUATOR_DB_SERVICE_OR_QUEUE
- STOP_SCIENTIFIC_FLOOR_OR_ACCEPTANCE_WEAKENING
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [MODULE-OBSERVATION-SCHEDULER-001, MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001, MODULE-FACTORY-V1-RESEARCH-STORE-001, DOC-HYPOTHESIS-FORGE-OPERATOR-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/opportunity_episodes_jupiter_v1.md
    - src/solana_alpha_lab/factory/opportunity_episodes.py
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# OPPORTUNITY_EPISODES_JUPITER_VERTICAL_SLICE_V1

ENTRY_DECISION: START_WITH_PATCH. SPEC_ROUTE: BOTH — owner PRD+SSD dated
2026-10-05 (external, outcome/DoD/invariants) and the canonical repository
semantic owner `docs/contracts/opportunity_episodes_jupiter_v1.md`.
Route: DIRECT_CLAUDE_CODE_DELIVERY, actor CLAUDE_CODE. Model effort: SOL_XHIGH.
Authority: owner EXECUTE_LOCAL_CAPABILITY prompt of 2026-10-05 for this exact
outcome; design anchor `de20465e` equals current main at Entry (no drift).
JUPITER_CORE provider choice is fixed; provider arbitration is not reopened.

DECISION_DELTA: the owner can consume an OPPORTUNITY_EPISODES daily cohort with
the ordinary command, see what was selected and when, ask one supported mixed
temporal question and replay it numerically in a detached process.
UNCERTAINTY_REMOVED: whether nomination-anchored episodes survive the existing
producer → publication → split-host release → import → ordinary Forge path
without a new importer/evaluator and without legacy drift.
CAPABILITY_OR_EVIDENCE: additive episode schedule kind, protected closed frame,
deterministic tickets, committed T0, 139-point grid with explicit gaps, release
1.2 strategy, episode corpus, population card, temporal query 1.1 binding,
D1–D12 synthetic proof including three-process cold replay.
Consumer: owner/operator and the ordinary Forge agent. Cheapest falsifier: the
real `scripts/observation_schedule.py::main` tick with complete physical
overrides fails to produce a committed episode whose published rows reach the
existing import path.
STOP: machine-proposed exact-head owner merge phrase, or exactly one evidenced
material authority/outcome boundary.
NEXT: separate OPERATE commissioning (registry route evidence, host envelope,
canary) and separately authorized real science.
REPLAN_TRIGGER: same seam fails twice after owner repair; work only prepares
more work; a second provider pivot; a needed new importer/evaluator/DB/service;
legacy identity/estimand change.
Evidence budget: isolated synthetic data roots under the session scratchpad;
zero provider/network/credential reads; zero shared Factory plane writes.
Reuse: WRAP existing tick composition, due/call ledgers, publisher, HOT raw
plane, split-host vanilla path, release/import owners, ResearchStore, ordinary
operation/session/Critic lifecycle and registered replay. Tool need: existing
deterministic scripts only. Factory Fit: FULL_REVIEW.
Delivery shape: one PR (the producer and readers are one tightly coupled
vertical slice; a reader-only PR would not be independently reviewable against
the owner scenario). Live activation remains NOT_RUN after merge.

## Required behavior

See `docs/contracts/opportunity_episodes_jupiter_v1.md` for the frozen
semantic contract. D1–D12 of the PRD are the acceptance matrix; evidence lives
in `docs/evidence/opportunity_episodes_jupiter_vertical_slice_v1/`.

## Review and delivery

Required isolated roles: code, goal/DoD, architecture and owner UX (CLI,
population card and runbook change). Architecture must name what can pass
tests and still break research validity. Incremental generated sync; local
preflight; exact-head CI; merge readiness; exact machine owner phrase.
No live semantic acceptance from synthetic or CI evidence.
