---
task_id: I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-13'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f8edf94f874484e4cecec61fa53cfca1dc77cbd4
  expected_upstream: origin/main
  expected_upstream_oid: f8edf94f874484e4cecec61fa53cfca1dc77cbd4
  expected_branch: claude/i3-shared-account-budget-bridge-v1
  dirty_mode: ALLOW_REPORTED
objective: Make one durable shared day/credit/cumulative budget for the managed Jupiter account of an ops store, so a new activation cannot reset the account; preserve individual grants, reservation/recovery semantics and the native late-successor overlap; prepare one gated OPERATE packet without deploy, commissioning or provider calls.
managed_write_set:
- docs/tasks/I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1.md
- docs/evidence/i3_episode_shared_account_budget_bridge_v1/**
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- src/solana_alpha_lab/factory/observation_account_budget.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- scripts/observation_schedule.py
- tests/test_observation_shared_account_budget_v1.py
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
- STOP_MATERIAL_SCOPE_SAFETY_OR_TRUTH_CONFLICT
- STOP_PRODUCTION_DEPLOY_COMMISSIONING_REGISTER_AUTHORIZE_ACTIVATE_OR_PROVIDER_CALL_BEFORE_SEPARATE_EXACT_OPERATE_GATE
- STOP_COLLECTOR_GRANT_FROZEN_SCHEDULE_STORAGE_PROTECTION_C1_C2_TIMER_OR_SCIENCE_CHANGE
- REPLAN_REPEATED_SEAM_FAILURE_IMPOSSIBLE_FALSIFIER_SECOND_ROUTE_PIVOT_OR_BUDGET_BREACH
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/i3_episode_shared_account_budget_bridge_v1/completion.json
    - docs/evidence/i3_episode_shared_account_budget_bridge_v1/independent-review.json
    - docs/evidence/i3_episode_shared_account_budget_bridge_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1

Owner EXECUTE selects one bounded atom of SMIAL_MANAGED_COLLECTION_OPERABILITY_V1
(parent sections 6 and 9-12, source copy
`docs/evidence/smial_managed_collection_i1_v1/source-contract.md`, SHA256
`6f3cce30bbea09eeffe286ccb6f9bc3a53dddf46b213dae038be0dc4ab4880e3`). The atom
PRD/SSD `I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1_PRD_SSD.md` (13.10.2026) is
summarized in `docs/evidence/i3_episode_shared_account_budget_bridge_v1/OWNER_READOUT.md`.
Remaining I3 (runtime limits, TARGET acceptance, standing-grant continuation,
operational rollback) stays open; I1 is accepted and not repeated.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH (accepted atom PRD/SSD).
Route/actor: DIRECT_CLAUDE_CODE_DELIVERY/CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
DECISION_DELTA: A tail and B intake can share one account budget without reset.
UNCERTAINTY_REMOVED: account identity, membership, units, fresh gate under lease,
atomic debit, no-reset commissioning, restore and downgrade behavior.
CAPABILITY_OR_EVIDENCE: store-level shared gate over existing debit rows,
native auto-binding of new activations, prepare/apply/revise/status CLI,
DRAINING-first default tick, typed `budget_denial`.
Named consumer: the default `observation_schedule.py tick --once` and the OPERATE agent.
Cheapest falsifier: preflight receipt
`local/i3_episode_continuity_preflight_v1/continuity-preflight-receipt.json`
(self SHA `4f25a20520716dcc2e6121a8ea92d3992c7bc4dd6a2cd9d57791da0aa55744fa`):
A 1200/day + 2000000 lifetime exhausted, B with 4 calls still allowed.
STOP: exact merge gate or material blocker. NEXT: separate OPERATE commissioning
on the running A (packet in evidence), then I2 footprint work.
REPLAN_TRIGGER: repeated seam failure, impossible oracle, second route pivot,
material resource risk or budget breach. Evidence budget: disposable SQLite
fixtures and the existing synthetic episode harness; no provider requests,
no production writes, no pre-PR full local suite.

Planning anchor `f8edf94f874484e4cecec61fa53cfca1dc77cbd4`; reported installed
producer `4378c5b82f2dc309ccd629b267affd5d19b34995`. Protect
ACT-4744D4017AC4B196, its schedule `4744d401…`, authority `c2c937b4…`, storage
envelope `fa6450ba…`, protection `f70a7f2d…` and C1/C2 byte-exact.
Unregistered B proposal ACT-9D3327EB9C791265 is test/fallback, not authority.

Tool Entry: existing delivery-harness, Git/gh, locked Python, SQLite.
New plugin/connector/MCP/automation/package/service: NONE.
Factory Fit: FULL_REVIEW. NOW: shared account accounting. WATCH: I2 footprint,
sustainable successor window, producer V2 before first fresh capture.

DoD before merge: reproduced original falsifier and managed refusal; separate
daily/credit/lifetime/midnight/crash/concurrent-last-call/replay proofs;
native late A->B on the public tick; targeted mutation; contract/runbook
propagation; isolated four-role critics; bound evidence; exact-head CI and
machine readiness; one prepared OPERATE packet. Runtime outcome remains
CODE_READY_RUNTIME_PENDING until a separately authorized commissioning.
