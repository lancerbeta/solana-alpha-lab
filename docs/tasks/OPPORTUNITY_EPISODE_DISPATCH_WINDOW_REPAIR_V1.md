---
task_id: OPPORTUNITY_EPISODE_DISPATCH_WINDOW_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-07'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417
  expected_upstream: origin/main
  expected_upstream_oid: 77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417
  expected_branch: codex/opportunity-episode-dispatch-window-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Give every admitted episode slot one fair dispatch opportunity inside its
  immutable dispatch window under the supported ordinary wake/runtime model;
  never send early, catch up late, duplicate an indeterminate send, or conceal
  genuine budget, pace, provider and missed-window gaps.
managed_write_set:
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/observation_provider_pacing.py
- scripts/observation_schedule.py
- configs/factory_remote_ops/factory-observation-schedule.timer
- configs/factory_remote_ops/factory-observation-schedule.service
- tests/test_opportunity_episode_dispatch_window_repair_v1.py
- tests/test_opportunity_episodes_harness_v1.py
- tests/test_opportunity_episodes_producer_v1.py
- tests/test_observation_schedule_remote_ops.py
- tests/test_factory_operability_memory_collision_repair_v1.py
- docs/tasks/OPPORTUNITY_EPISODE_DISPATCH_WINDOW_REPAIR_V1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/evidence/opportunity_episode_dispatch_window_repair_v1/**
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
  deployment: true
stop_conditions:
- STOP_UNLESS_EXACT_HEAD_CI_REVIEWS_READINESS_AND_MACHINE_OWNER_PHRASE_MATCH
- STOP_MANUAL_PROVIDER_CALLS_CREDENTIAL_ACCESS_NEW_ACTIVATION_OR_RENEWAL
- STOP_POPULATION_CAP_FLOOR_T0_GRID_PROTECTION_STORAGE_RETENTION_CHANGE
- STOP_HISTORY_REPAIR_BACKFILL_OR_SCIENTIFIC_LOOK
context_requirements:
  catalog_asset_ids: [MODULE-OPPORTUNITY-EPISODES-001, MODULE-OBSERVATION-SCHEDULER-001]
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
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md, docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md]
    DELIVERY_EVIDENCE:
    - docs/evidence/opportunity_episode_dispatch_window_repair_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/opportunity_episode_dispatch_window_repair_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/opportunity_episode_dispatch_window_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OPPORTUNITY_EPISODE_DISPATCH_WINDOW_REPAIR_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: PRD_LITE, with the runtime design
and supported coverage model recorded here after the cheapest RED reproduction.
Route DIRECT_CODEX_DELIVERY, actor CODEX. Owner authority: explicit bounded P1
repair request and expanded EXECUTE + bounded OPERATE authorization on
2026-10-07. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.

DECISION_DELTA: the owner can rely on the existing episode activation for future
scheduled observations after a separately authorized compatible deployment.
UNCERTAINTY_REMOVED: whether ordinary wake/tick timing can miss the entire frozen
dispatch window while returning TICK_COMPLETE.
CAPABILITY_OR_EVIDENCE: deterministic RED/GREEN production-composition trace,
effective wake/dispatch coverage invariant, exact-head reviewed repair PR.
Consumer: ordinary episode scheduler and its existing canary activation.

Live incident input (owner-provided operational evidence, not a scientific look):
episode EP-95f653990f809a77b0f823ec95b0a3d5, E300 window
[2026-10-07T00:55:00Z, 2026-10-07T00:56:00Z); prior service start
00:54:58.627882, next terminalization 00:56:00.389428,
CENSORED/SLOT_NOT_EXECUTED, zero SEARCH calls. Preserve that gap forever.

Cheapest falsifier: replay this clock/wake trace through the existing production
CLI composition with synthetic provider transport. A manually chosen tick inside
the window is not scheduler coverage proof. RED must precede product changes.

DoD: cover pre-window entry and live boundary crossing; delayed next wake;
nomination/workload crossing due; exactly one in-window SEARCH; zero early/late
sends; same-assigned batching at max batch size; crash/intent/restart no duplicate;
fail-closed pace/budget/provider failures; unchanged nomination/admission/E0;
explicit acceptance bound on effective dispatch gaps, including blocking work;
publication of OBSERVED or honest typed gaps from the same production vertical.
Root cause, chosen invariant, supported-model limits and deployment compatibility
must be explicit. No unlimited latency or capacity guarantee may be invented.

Reuse: WRAP existing store, pacing clock, timer and production harness; no new
dependency/service/provider/schema. Entry tooling: existing scripts and Delivery
Harness only; no installation, connector or automation needed.
Evidence budget: focused deterministic suites, directly affected consumers,
one independent risk-routed review wave plus bounded repair if warranted; GitHub
exact-head CI owns the full suite. No pre-PR local full gate.
REPLAN_TRIGGER: coverage requires a new runtime/service or stored schedule change,
the cheapest falsifier cannot run, or a second independent blocker appears.
STOP: any material different boundary or failed machine gate. The owner's
expanded 2026-10-07 EXECUTE + bounded OPERATE authority permits the exact
machine-rendered phrase after unchanged-head readiness, guarded merge,
post-merge readback, canonical-forward deploy and at most 20 minutes of
naturally scheduled live proof. No manual provider probe or activation change.
NEXT: operationally proved continuity or a bounded honest live-slot wait result.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE,
WATCH=ordinary dispatch coverage and honest failure classes after gated deploy.

Required isolated reviews: code, goal/DoD, architecture and owner-UX. Architecture
must identify timing behavior that can pass example tests yet change research
availability or silently select a timing-dependent sample.

Supported-model invariant and timeout delta are fixed in the bound readout and
episode operator runbook: effective checkpoint gaps strictly <60s (idle31s,
category23s), finite local overhead, shared SEARCH time for remaining batches,
and exact send-window guards. OS/GIL stalls and budget failures remain typed.
The owner authorization covers the exact machine-rendered phrase only after
unchanged-head CI/reviews/readiness, then merged-main readback and canonical
deploy. A different material boundary stops the atom. At most one follow-up
repair is authorized only if this same root boundary recurs after first deploy.
