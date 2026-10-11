---
task_id: SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-11'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d244af69bfd7ddc2850b9e5e5823323956e325c4
  expected_upstream: origin/main
  expected_upstream_oid: d244af69bfd7ddc2850b9e5e5823323956e325c4
  expected_branch: codex/smial-trading-continuity-v1
  dirty_mode: ALLOW_REPORTED
objective: Audit and repair confirmed gaps in the ordinary scientific handoff to timely source-bound PAPER/SHADOW decision, attempt/result, position, exit, reconciliation and truthful operator readback path, independently verify the offline chain and clean all campaign-owned disposable resources.
managed_write_set:
- docs/tasks/SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1.md
- docs/evidence/smial_trading_continuity_v1/**
- docs/reports/smial_trading_continuity_v1/**
- docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md
- docs/contracts/science_to_strategy_handoff_v1.md
- docs/contracts/trading_runtime_policy_v1.md
- docs/contracts/risk_and_economics_v1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/contracts/episode_decision_continuity_v1.md
- docs/contracts/owner_lifecycle_projection_spine_v1.md
- src/solana_alpha_lab/factory/episode_decision.py
- src/solana_alpha_lab/factory/trading_runner.py
- src/solana_alpha_lab/factory/strategy_runtime.py
- src/solana_alpha_lab/factory/promotion_handoff.py
- src/solana_alpha_lab/factory/hfic_research_scope.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/normalized_trajectory_v1.py
- src/solana_alpha_lab/factory/normalized_trajectory_episodes_v1.py
- src/solana_alpha_lab/factory/opportunity_episodes.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/opportunity_episode_release.py
- src/solana_alpha_lab/factory/paper_plane.py
- src/solana_alpha_lab/factory/paper_shadow_operations.py
- src/solana_alpha_lab/factory/paper_shadow_commands.py
- src/solana_alpha_lab/factory/trading_operations.py
- src/solana_alpha_lab/factory/risk_economics.py
- src/solana_alpha_lab/factory/trading_runtime_policy.py
- src/solana_alpha_lab/factory/application.py
- src/solana_alpha_lab/factory/lifecycle_projection.py
- scripts/trading_continuity.py
- scripts/prove_trading_continuity.py
- configs/execution_domain_v1.json
- configs/factory_semantic_operability_v1.yaml
- tests/test_trading_continuity_v1.py
- tests/test_science_to_strategy_handoff_v1.py
- tests/test_execution_evidence_handoff_binding_v1.py
- tests/test_execution_evidence_seam_v1.py
- tests/test_hfic_research_scope_v1.py
- tests/test_opportunity_episodes_contract_v1.py
- tests/test_paper_shadow_execution_integrity_vertical_v1.py
- tests/test_factory_strategy_execution_boundary_v1.py
- tests/test_paper_shadow_accounting_and_control_v1.py
- tests/test_trading_runtime_admission_concurrency_v1.py
- tests/test_trading_runtime_policy_backup_restore_v1.py
- tests/test_trading_runtime_policy_v1.py
- tests/test_risk_and_economics_v1.py
- tests/test_execution_domain_modularity_and_fast_ci_v1.py
- tests/fixtures/trading_continuity_v1/**
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
- STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
- STOP_MATERIAL_RISK_POLICY_SCIENTIFIC_MEANING_OR_COMPETING_TRUTH_OWNER
- STOP_REAL_RUNTIME_PROTECTED_DATA_PROVIDER_DEPLOY_SETTINGS_CREDENTIALS_MONEY_OR_HISTORY_REWRITE
- STOP_NEW_DEPENDENCY_OR_UNOWNED_DESTRUCTIVE_CLEANUP
- REPLAN_REPEATED_SEAM_FAILURE_IMPOSSIBLE_FALSIFIER_OR_RESOURCE_SAFETY_LIMIT
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/science_to_strategy_handoff_v1.md
    - docs/contracts/trading_runtime_policy_v1.md
    - docs/contracts/risk_and_economics_v1.md
    - docs/evidence/smial_trading_continuity_v1/source-contract.md
    DELIVERY_EVIDENCE:
    - docs/evidence/smial_trading_continuity_v1/completion.json
    - docs/evidence/smial_trading_continuity_v1/independent-review.json
    - docs/evidence/smial_trading_continuity_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1

Owner explicitly authorized EXECUTE according to the supplied MD. Exact source
bytes are retained at docs/evidence/smial_trading_continuity_v1/source-contract.md,
SHA256 fa27010cd06336d7e962798ce29cf04427ba8a3a23b420a3878357094fc6274c.
The source is the single PRD/SSD; this contract binds delivery and does not
duplicate its design. S00-S23 and O1-O8 remain the acceptance denominator.

ENTRY_DECISION: START_WITH_PATCH (materialize exact contract and isolate fixtures).
SPEC_ROUTE: BOTH (reuse attached PRD/SSD). Route/actor: DIRECT_CODEX_DELIVERY/CODEX.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: establish and repair ordinary downstream continuity, preserving
separate scientific eligibility, Git definition, sandbox activation and runtime.
UNCERTAINTY_REMOVED: actual callers, timely source provenance, result persistence,
recovery and accounting instead of historical designs or injected engine objects.
CAPABILITY_OR_EVIDENCE: reproducible ordinary offline chain, independent literal
oracles, confirmed repair ledger, truthful residual gates and ownership cleanup.
Named consumers: eligible future strategy, ordinary producer/runner, PaperPlane,
operator readback and a separately authorized commissioning decision.
Cheapest falsifier: O1/O5/O8 source-shaped inputs through the ordinary caller,
paired with invalid handoff and independent committed SQLite state readback.
STOP: material science/risk/authority boundary or machine-ready owner merge phrase.
NEXT: baseline, confirmed repairs, fresh-root verification, cleanup, exact reviews,
evidence binding and ordinary PR/CI within the frozen base policy.
REPLAN_TRIGGER: repeated seam failure, competing truth, symptomatic adapters,
missing ordinary path, impossible oracle or resource safety limit.

Engineering effort is outcome-bound; fixtures remain compact, mutable stores
disposable, allocations ownership-recorded before creation. No live data roots,
credentials, actual science trials, external attempts, wallets or transactions.
Known inventory/admission risk-policy forks retain existing semantics and are
reported separately for owner decision. Independent safe repairs continue.

Tool Entry: existing delivery-harness, Git/gh, locked Python, real disposable
SQLite and current source/list/recipe owners. New plugin/connector/MCP/automation,
package, Docker image or service: NONE. Factory Fit: FULL_REVIEW.
Product Horizon NOW=this named offline chain; WATCH=separately authorized
commissioning after actual scientific eligibility and offline acceptance.
No local full gate before PR. Code, goal/DoD, architecture and owner-UX reviews
run independently on the exact final inventory. No scientific/live/alpha/FCF claim.

Baseline: main d244af69bfd7ddc2850b9e5e5823323956e325c4; clean input tree; no
planning-anchor drift. Previous task branch preserved. One checkout root only.
Generated Catalog/navigation propagation uses the sanctioned generator.

Owner-authorized PR #396 PATCH on 2026-10-11 reuses this exact contract. Review
handoff bytes: docs/evidence/smial_trading_continuity_v1/review-handoff.md,
SHA256 00f9589bcecac9e12d83ec8837be6b4398448c8f234d6851a4110cc8a23505d7.
This is a bounded correction to the existing outcome, not a new PRD or task.
DECISION_DELTA_PATCH: a normal admission refusal/cancellation must commit its
source and outcome atomically; only actual errors roll back the transaction.
Cheapest falsifier: ordinary episode on the existing source-shaped fixture,
then a new readonly connection after disabled-policy denial and stale WATCHED
replay. Independently enumerate source ENTER, admitted and denied evaluations.
Preserve existing policy, successful reservation atomicity, legacy callers and
ATTEMPTING/UNKNOWN reconciliation. Re-evaluation after a policy revision does
not erase an earlier denial. Refresh impacted tests, evidence, all four isolated
reviews and exact-head bindings. V2/successor lifecycle and risk-policy changes
remain excluded; REPAIR_PARTIAL_BLOCKED and open S08/S13 are unchanged.
STOP_PATCH: exact-head CI then merge-readiness PASS and its machine owner phrase;
the PATCH instruction explicitly grants no merge authority.
