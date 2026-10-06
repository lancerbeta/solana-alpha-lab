---
task_id: EPISODE_ACTIVATION_BEFORE_START_PROOF_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-06'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e0ceceeb1bed1b56714386181e1a3b220f632b06
  expected_upstream: origin/main
  expected_upstream_oid: e0ceceeb1bed1b56714386181e1a3b220f632b06
  expected_branch: claude/episode-activation-before-start-proof-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  An ordinary activation committed before its schedule's starts_at must keep a
  reachable ACTIVE transition proof, make zero provider calls before the
  boundary without reading as a failed tick, and continue through the ordinary
  tick after the boundary with no pause/resume workaround.
managed_write_set:
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- scripts/observation_schedule.py
- tests/test_episode_activation_before_start_v1.py
- tests/test_opportunity_episodes_harness_v1.py
- docs/tasks/EPISODE_ACTIVATION_BEFORE_START_PROOF_V1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/evidence/episode_activation_before_start_proof_v1/**
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
- STOP_POPULATION_GRID_CAP_FLOOR_STORAGE_PROTECTION_OR_AUTHORITY_CHANGE
context_requirements:
  catalog_asset_ids: [MODULE-OBSERVATION-SCHEDULER-001]
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
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/episode_activation_before_start_proof_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/episode_activation_before_start_proof_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/episode_activation_before_start_proof_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EPISODE_ACTIVATION_BEFORE_START_PROOF_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: NONE (a bounded boundary fix of an
existing lifecycle proof; no new semantics). Route DIRECT_CLAUDE_CODE_DELIVERY,
actor CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH (lifecycle proof is an
authority-adjacent boundary). Authority: the owner's explicit 2026-10-06
instruction naming this P1 repair; expected base `e0ceceeb` re-verified at Entry as
live `origin/main`.

DECISION_DELTA: the owner may activate a frozen episode schedule ahead of its
`starts_at` (authorize, activate, enable the ordinary timer) and rely on the
ordinary tick to wait and then start, instead of a pause/resume workaround.
UNCERTAINTY_REMOVED: whether an activation committed before `starts_at` can ever
reach its ACTIVE transition proof (it could not).
CAPABILITY_OR_EVIDENCE: root cause by RED test on the production CLI tick path:
`activation_transition_research_event_proven` reads lifecycle partitions with
`window_start=starts_at`; the activation's own ACTIVE event is effective at the
activation instant, before `starts_at`, so the bounded reader classifies its
partition as "before the window" and drops it. The tick then refuses with
`TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE` for the whole pre-start period
and after the boundary. Consumers: the next canary activation; any future
schedule activated ahead of its window.
Cheapest falsifier: `tests/test_episode_activation_before_start_v1.py` fails on
`e0ceceeb` (RED: proof False, tick refused) and passes with the fix.

Required invariants:

- The proof still requires the exact committed `OBSERVATION_SCHEDULE_STATE` event
  (event id recomputation, authority receipt, capability, availability, no later
  conflicting event); only the lower bound of the bounded read changes, to
  `min(starts_at, activation row created_at)`.
- A missing, foreign or tampered transition event still refuses closed.
- No provider call, credential read or admission happens before `starts_at`.
- A tick before `starts_at` is an honest idle (`NOT_YET_ACTIVE`, exit 0) so an
  early ordinary timer does not produce a failed unit every minute; every other
  non-`TICK_COMPLETE` terminal keeps exit 2.
- Pause, resume, stop-intake, activation at the boundary and the DRAINING proof
  are unchanged.

DoD: RED-then-GREEN tests for the pre-start owner path (several pre-start ticks,
zero provider calls, no proof refusal; first tick at the boundary admits without
pause/resume; pause then resume still proves; boundary activation unchanged;
missing/foreign event refuses; stop-intake before the boundary keeps its drain
proof); the existing scheduler, lifecycle, store, remote-ops, episode producer,
operability, vertical and production-line suites stay green; the operator runbook
states that an episode activation ahead of `starts_at` is supported and what a
pre-start tick returns.

Non-goals: deploy, any VPS write, provider call, credential read, activation,
population/floor/grid/cap/storage/protection/authority change, rollover windows
(`_prior_active_transition_research_event_proven` and the rollover predecessor/
successor reads start at their own effective cutover and are not changed), the
DRAINING evidence read (already reachable), merge.
Reuse/build: WRAP the existing proof; one private helper, no new framework,
table, dependency or service.
Risks: a pre-start activation keeps the proof read window open slightly earlier
(bounded by the activation creation instant); an early ordinary timer now ends
each pre-start tick with exit 0 instead of 2.
Rollback: owner-gated revert of this commit; no data or schema migration.
STOP: merge boundary; never merge in this atom.
NEXT: exact-head CI, merge-readiness, owner phrase, guarded merge, then the
separate OPERATE deploy decision (producer Git SHA is not part of frozen
activation semantics: no stored identity compares it).
REPLAN_TRIGGER: the fix needs a schema, event-format or authority change, or a
second lifecycle owner.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE.

Required reviews: isolated code, goal/DoD, architecture and owner-UX. Architecture
must answer: can the widened lower bound let a stale or foreign event satisfy the
proof, and what can pass these tests and still break research validity?
