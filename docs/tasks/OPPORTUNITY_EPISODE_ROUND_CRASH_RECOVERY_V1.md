---
task_id: OPPORTUNITY_EPISODE_ROUND_CRASH_RECOVERY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-06'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5a9d937fc6b9e57c7e157a5862fbcb459efbb1e1
  expected_upstream: origin/main
  expected_upstream_oid: 5a9d937fc6b9e57c7e157a5862fbcb459efbb1e1
  expected_branch: claude/opportunity-episode-round-crash-recovery-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  A process crash inside an opportunity-episode nomination round must not let a
  partially executed deterministic selection later look like a normal
  scientific-ready cohort: fix the selection durably before the first admission,
  reconcile unresolved rounds from durable evidence only, and fail the cohort
  maturity gate closed on unresolved or partial rounds.
managed_write_set:
- src/solana_alpha_lab/factory/opportunity_episodes.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/opportunity_episode_release.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- tests/test_opportunity_episode_round_recovery_v1.py
- docs/tasks/OPPORTUNITY_EPISODE_ROUND_CRASH_RECOVERY_V1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/evidence/opportunity_episode_round_crash_recovery_v1/**
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
- configs/factory_semantic_operability_v1.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_MERGE_DEPLOY_SETTINGS_TIMER_CHANGES
- STOP_PROVIDER_CALLS_NEW_CREDENTIALS_OR_SECRET_ACCESS
- STOP_PRODUCTION_DATA_REAL_SCIENTIFIC_LOOK_DESTRUCTIVE_CLEANUP
- STOP_PROVIDER_REGISTRY_ROUTE_COMMISSIONING_STORAGE_RETENTION_OR_LOOKUP_REDESIGN
- STOP_POPULATION_GRID_CAP_OR_T0_SEMANTIC_CHANGE
context_requirements:
  catalog_asset_ids: [MODULE-OBSERVATION-SCHEDULER-001, MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001]
  l2_roles: [ARCHITECTURE_DECISIONS]
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
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/opportunity_episode_round_crash_recovery_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/opportunity_episode_round_crash_recovery_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/opportunity_episode_round_crash_recovery_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OPPORTUNITY_EPISODE_ROUND_CRASH_RECOVERY_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: PRD_LITE. Route
DIRECT_CLAUDE_CODE_DELIVERY, actor CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION:
SOL_XHIGH (owner-selected). Authority: the owner's explicit 2026-10-06
instruction naming this atom; expected base `5a9d937f` re-verified at Entry as
live `origin/main`.

DECISION_DELTA: the owner can trust that a cohort released for science is
exactly the deterministic selection, never a crash-timing subset.
UNCERTAINTY_REMOVED: whether a `STARTED` nomination round can stay durable after
its slack and whether cohort maturity ignores it.
CAPABILITY_OR_EVIDENCE: pre-admission recovery plan in the existing round owner
row, after-slack reconciliation from durable evidence, fail-closed maturity.
Consumers: producer tick, store, cohort maturity/closure, capture CLI.
Cheapest falsifier (frozen main, run before any change): quota-2 round, crash
after the first committed admission, restart after slack.
FALSIFIER_BEFORE: round stayed durable `STARTED` (report said
`MISSED_NO_REQUEST`), the second planned winner was never admitted, and
`_cohort_status` returned `mature=True, blocking_reasons=[]`.
FALSIFIER_AFTER: the next tick terminalizes the round `INCOMPLETE`
`ROUND_RECOVERY_PARTIAL_ADMISSION`, keeps the committed admission, makes zero
nomination calls, admits nothing late, and the cohort is not mature
(`ROUND_PARTIAL_ADMISSION`).

Required invariant: once durable admissions begin, the completed frame identity,
quota/selection basis, exact ordered winner set chosen before the first
admission and the committed subset are recoverable; crash timing cannot change
the scientific population without explicit evidence. Inside slack the plan is
followed, never recomputed; after slack only durable evidence is read.

DoD: normal round unchanged; STARTED restart inside slack preserved; crash
before any admission after slack gives durable terminal provenance with no calls
or late admissions; quota>=2 partial admission keeps the committed episode,
admits no second one and fails cohort/capture closed; crash after all planned
admissions closes the exact round without calls; missing/corrupt plan, frame,
call evidence or admission is a typed refusal with no healing; unresolved
STARTED or partial rounds are never mature; T0, quota, rolling-24h, active-cap,
accounting, protection, stop-intake and the 139-point semantics are unchanged.

Non-goals: provider registry, Jupiter route commissioning, deploy/systemd,
storage retention/GC, lookup architecture, Forge/scientific query semantics
beyond the fail-closed maturity gate, population/grid/caps, real provider calls,
production data, merge.
Reuse/build: WRAP existing `episode_rounds`, `INCOMPLETE` plus typed terminal
reason and the existing cohort maturity reasons; no new table, service, ledger
or state. No dependencies.
Risks: a legitimate in-flight round blocked by the gate (any `STARTED` relevant
round at maturity time is past its slack by construction); a stuck `STARTED`
round when no tick runs again blocks its cohort (fail-closed, honest).
Rollback: owner-gated code revert; plan-bearing rows stay readable as ordinary
frame JSON; legacy terminal rows without a plan are unchanged (a legacy plan-less
STARTED round that already has admissions is refused, not healed).
STOP: merge boundary; never merge in this atom.
NEXT: exact-head CI, merge-readiness, owner phrase.
REPLAN_TRIGGER: the plan cannot be expressed in `episode_rounds.frame_json`, a
second blocker repeats, or scope reaches a stop condition.
FACTORY_FIT_REVIEW: PROPORTIONAL. PRODUCT_HORIZON_RADAR NOW=NONE.

Required reviews: isolated code, goal/DoD and architecture. Architecture must
answer: can process timing still change the scientific-ready sample without
explicit evidence?
