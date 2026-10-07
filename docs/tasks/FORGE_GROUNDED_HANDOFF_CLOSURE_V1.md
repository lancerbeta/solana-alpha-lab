---
task_id: FORGE_GROUNDED_HANDOFF_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-07'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 04ec8e0286a3dce5999d0687784717ee90fc5dca
  expected_upstream: origin/main
  expected_upstream_oid: 04ec8e0286a3dce5999d0687784717ee90fc5dca
  expected_branch: codex/forge-grounded-handoff-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Accepted fresh grounded cards preserve their declared scope and evidence
  through existing candidate consumers; canonical queries round-trip without
  repinning definitions, durable writers require committed context, and a
  source-bound synthetic native journey proves the supported handoff.
managed_write_set:
- docs/tasks/FORGE_GROUNDED_HANDOFF_CLOSURE_V1.md
- docs/contracts/forge_grounded_handoff_closure_v1.md
- docs/contracts/forge_list_aware_research_scope_v1.md
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_research_scope.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- scripts/hypothesis_forge.py
- src/solana_alpha_lab/factory/observation_schedule_compiler.py
- src/solana_alpha_lab/factory/observation_panel_coverage.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/observation_schedule_capability.py
- src/solana_alpha_lab/factory/scientific_eligibility_projection.py
- src/solana_alpha_lab/factory/document_runner.py
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/experiment_spec.py
- src/solana_alpha_lab/factory/run_passport.py
- catalog/schemas/experiment_spec_v1_3.schema.json
- tests/test_observation_schedule_compiler.py
- tests/test_scientific_eligibility_projection_v1.py
- tests/test_fast_lane_runner.py
- tests/test_hfic_temporal_production_runner_v1.py
- catalog/schemas/hypothesis_forge_draft_v1_2.schema.json
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- .agents/skills/hypothesis-forge/SKILL.md
- .agents/skills/independent-hypothesis-critic/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_forge_grounded_handoff_closure_v1.py
- tests/test_hfic_session.py
- tests/fixtures/forge_grounded_handoff_closure_v1/**
- docs/evidence/forge_grounded_handoff_closure_v1/**
- docs/reports/forge_grounded_handoff_closure_v1/**
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/relations/**
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_REAL_RESEARCH_STORE_OR_REAL_SCIENTIFIC_LOOK
- STOP_SCIENTIFIC_CRITERIA_ESTIMAND_PIT_IDENTITY_OR_BUDGET_CHANGE
- STOP_HISTORY_REWRITE_OR_GIT_FENCE_WEAKENING
- STOP_NEW_PROVIDER_DEPENDENCY_SERVICE_OR_EVALUATOR
- STOP_PRODUCTION_REPAIR_DEPLOY_SETTINGS_STRATEGY_WALLET_OR_MONEY
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: [DOC-HYPOTHESIS-FORGE-OPERATOR-001, MODULE-FACTORY-V1-RESEARCH-STORE-001]
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
    - src/solana_alpha_lab/factory/hfic_research_scope.py
    - src/solana_alpha_lab/factory/hfic_session.py
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# FORGE_GROUNDED_HANDOFF_CLOSURE_V1

Owner authorization: direct request "делай патч", with the supplied
SMIAL_FORGE_GROUNDED_HANDOFF_CLOSURE_V1_PRD_SSD_2026-10-07.md specification.
The document is the bounded implementation specification; its diagnostic
claims must be reproduced, and it grants no merge or production authority.

Continuation authorization: the owner accepted checkpoint
`8a3e9d8e1c848395ac7cee99bc2cf75637417543` as intermediate evidence, then
explicitly requested H08/H09 closure in the same repair atom. Repair only the
shared Critic transport losslessly; reuse the exact persisted native draft,
candidate, market, slot, reservation, look, accounting and typed recipe. Use
existing prefreeze capability recovery, isolated actual Critic and supported
ExperimentSpec 1.3 / DocumentRunner. No new formulation, candidate or look;
no draft rewrite, refund, reroll or softened data/schema semantics. Push/PR/merge
are forbidden before the complete checkpoint. A cheap existing chronological
consumer may consume only an already frozen later/sign-reversed branch; absent
consumer/input is a named gap, not permission to build a new subsystem.

H09 continuation authority: the owner explicitly expanded this same bounded
atom through existing compiler/coverage/canonical-release/replay/ExperimentSpec/
DocumentRunner owners and direct validators/consumers. Routine write-set,
schema/helper/test/contract and generated propagation changes are authorized;
ordinary commits, non-force push/PR, exact-head CI and merge-readiness are
authorized after truthful H09 evidence. Disposable synthetic snapshot/binding
materialization must derive from the existing frozen source lineage and pass
the production contract; it cannot fabricate coverage or release identity.
H08 is retained, not rerun. Same candidate/definition/recipe/source bindings,
slot/reservation/look/accounting and KILL_LOW_INFORMATION_VALUE are immutable.
No new MAIN/ADAPTIVE/PREVIEW/holdout, budget increase or outcome-informed
selection. New evaluator/service/database/dependency, changed scientific
meaning/recipe, live provider/production/VPS/credentials/settings/money or
destructive history remain stops. Existing-owner mismatches are routine repair,
not owner gates. Stop after exact-head CI and machine merge-readiness at the
machine-rendered exact owner phrase; no merge without that separate phrase.
If no lawful existing replay capability can execute the exact recipe, return
H09_UNEXECUTABLE_WITH_CURRENT_CAPABILITY with the proved earliest root cause.

ENTRY_DECISION: START_WITH_PATCH. SPEC_ROUTE: BOTH. MODEL_EFFORT: SOL_XHIGH.
Consumer: ordinary Forge generator, independent Critic and existing experiment
consumer. Tool need: delivery-harness, hypothesis-forge/independent Critic,
installed Git/GitHub CLI and existing deterministic scripts; no adoption.

DECISION_DELTA: remove reproducible technical loss of already-authored scope,
canonical pins and mandatory context before interpreting scientific results.
UNCERTAINTY_REMOVED: fresh public input reaches readable, source-bound consumers.
CAPABILITY_OR_EVIDENCE: H01-H12 in the supplied specification, with honest
PARTIAL/BLOCKED for any unproved native/downstream science boundary.
Cheapest falsifier: nested-only authored target/condition, canonical roundtrip,
and no-auto context receipt through existing production boundaries.
STOP: exact-head CI plus merge-readiness, then one exact owner phrase; or an
evidenced material scope/authority blocker. NEXT: separately authorized science
and remaining whole-Forge audit gaps, never automatic strategy promotion.
REPLAN_TRIGGER: a second state owner, new evaluator, identity migration,
repeated independent blocker or native budget exhausted.

Execution uses an independently cloned current accepted main, preserving the
dirty PR-B checkout. Active time gates are terminal/non-triggering. PR-B is
not merged at Entry; overlapping owners are session, grounded discovery,
preflight, temporal discovery and public CLI. Recheck accepted main at delivery.
No duplicate runtime-policy/continuation implementation; current base uses
its existing six-card limit, and only a supplied accepted policy can change it.

Validation: V0 RED (two repetitions per deterministic defect), minimal repairs
at existing owners, direct negative/legacy/projection tests, connected public
synthetic native journey and cold process readback. Native budget is at most
six substantive outputs: one positive formulation/critique, one overclaim
critique, and at most one lawful primary revision/re-critique. SCRIPTED
mechanical branches remain labeled. Independent review roles are frozen above.
No forced PASS, borrowed hypothesis/result identity, real corpus/provider reads,
new looks on shape retry, historical terminal rewrite or Git composite edits.

Factory Fit: FULL_REVIEW. Product Horizon NOW: this repair; WATCH: named
uncovered science/reliability transitions after the handoff proof.
GLOBAL_FORGE_AUDIT: INCOMPLETE_UNLESS_SEPARATELY_PROVEN.
Evidence policy: compact assertions/hashes/reproduction commands in Git;
synthetic stores and detailed transient logs remain outside tracked content.
Rollback: ordinary owner-authorized revert; no production migration or repair.
