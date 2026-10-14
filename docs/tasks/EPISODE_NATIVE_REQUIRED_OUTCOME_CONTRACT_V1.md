---
task_id: EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1
task_version: '1.1'
status: READY
as_of: '2026-10-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: dbe491595c7122735a418e67341be5cad9dbf45e
  expected_upstream: origin/main
  expected_upstream_oid: dbe491595c7122735a418e67341be5cad9dbf45e
  expected_branch: codex/episode-native-required-outcome-contract-v1
  dirty_mode: ALLOW_REPORTED
objective: Implement version-isolated ExperimentSpec 1.4 native episode REUSE_ONLY handoff through source-bound metadata coverage, authoritative persisted HFIC classification and cold readback, preserving episode identities, decision denominators, native clocks, protection and scientific authority.
managed_write_set:
- docs/tasks/EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1.md
- docs/design/EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1_PRD_SSD.md
- catalog/schemas/experiment_spec_v1_4.schema.json
- src/solana_alpha_lab/factory/experiment_spec.py
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/episode_required_outcomes.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/document_runner.py
- src/solana_alpha_lab/factory/run_passport.py
- src/solana_alpha_lab/factory/data_resolver.py
- tests/test_episode_native_required_outcome_contract_v1.py
- tests/fixtures/episode_native_required_outcomes_v1/**
- docs/contracts/episode_native_required_outcomes_v1.md
- docs/evidence/episode_native_required_outcomes_v1/**
- docs/evidence/list_a_confirmation_protocol_freeze_v1/main-refresh.json
- docs/reports/episode_native_required_outcomes_v1/**
- .agents/skills/independent-hypothesis-critic/SKILL.md
- .agents/skills/hypothesis-forge/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- catalog/assets/**
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_CHANGED_ESTIMAND_POPULATION_CLOCK_POLICY_OR_SCIENTIFIC_THRESHOLDS
- STOP_PROVIDER_REAL_DATA_PRODUCTION_DEPLOY_CREDENTIALS_OR_MONEY
- STOP_NEW_CAPABILITY_CONFIRMATION_STRATEGY_OR_PAPER
- STOP_NO_REWRITE_OF_PRIOR_KILL_OR_AUDIT_HISTORY
- STOP_NO_NEW_ENVIRONMENT_DEPENDENCIES_OR_DESTRUCTIVE_CLEANUP
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_OWNER_MERGE_PHRASE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    HISTORICAL_CONTEXT: []
    ARCHITECTURE_DECISIONS:
    - docs/design/EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1_PRD_SSD.md
    DELIVERY_EVIDENCE:
    - docs/evidence/episode_native_required_outcomes_v1/completion.json
    - docs/evidence/episode_native_required_outcomes_v1/independent-review.json
    - docs/evidence/episode_native_required_outcomes_v1/factory-fit.json
---

Owner EXECUTE on 2026-10-14: repair according to the attached exact PRD+SSD.
ENTRY=START_AS_WRITTEN; SPEC_ROUTE=BOTH; route DIRECT_CODEX_DELIVERY / CODEX.
MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH. Existing delivery-harness, Git/gh,
locked host runtime and native synthetic producers; new tools/dependencies NONE.

DECISION_DELTA: remove the proved episode required-outcome contract gap without
claiming acceptance of the old hypothesis or chronological confirmation.
UNCERTAINTY_REMOVED: whether the strict native recipe reaches durable classifier
readiness without target-value reads, population collapse or stale protection.
CAPABILITY_OR_EVIDENCE: source-bound Spec 1.4 artifact-route classification,
exact membership/coverage, reader traces and fresh-process stored readback.
Consumers: Critic authoring, HFIC classifier, direct runner handoff and owner.
Cheapest falsifier: whole valid Spec 1.3 Y control / E14400 pattern failure,
then one native positive persisted classifier witness before delivery ceremony.

DoD is the attached sections 10-11, including material T1-T11 counterexamples,
independent membership and no-look canaries, numeric-in-scope and list-only,
legacy regression, current protection before READY/REPLAY and durable navigation.
No product import of evidence/test helpers. Existing value/hash/clock owners reused.
Synthetic fixture preparation looks separately counted; classification does not
evaluate targets, run experiments, produce qualifying evidence or promote.
Evidence budget: one compact two-cycle native world plus bounded variants;
individual proof process 180 seconds, native fixture setup 600 seconds,
retained owned artifacts <= 512 MiB; no full local pre-PR gate.
REPLAN_TRIGGER: material semantic/authority change, impossible positive witness,
repeated material blocker or evidence cap breach.
STOP: delivery-ready exact candidate at owner merge phrase or material replan.
NEXT: separately authorize accepted chronological producer/consumer analysis.
Factory Fit FULL_REVIEW. Horizon NOW=this seam; WATCH=chronological continuation.
Git task transport is the repository policy exception to network=false.

Dependent delivery binding refresh: preflight found a SEPARATE historical pin
from List A main-refresh.json to the shared temporal owner changed by this seam.
Only append a dated implementation-change record to that exact receipt. Preserve
every original historical field/value and source-commit pin; reference the whole
original receipt through frozen Git ref/hash. No previous List A check is rerun,
no List A compatibility or scientific acceptance is inferred, and its historical
owner authorization does not apply to this repair. Machine guard policy remains
unchanged. The final expanded inventory requires fresh independent reviews.
