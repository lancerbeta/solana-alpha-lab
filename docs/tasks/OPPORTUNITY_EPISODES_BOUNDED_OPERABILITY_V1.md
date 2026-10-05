---
task_id: OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-06'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 576e8c54715bb8af6b84877b91678ae659a42f88
  expected_upstream: origin/main
  expected_upstream_oid: 576e8c54715bb8af6b84877b91678ae659a42f88
  expected_branch: codex/opportunity-episodes-bounded-operability-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Prove a bounded fresh-process opportunity episode operating path on growing valid
  history, preserve shared ResearchStore identity and integrity, prove pressure/drain,
  workstation-off retry and nonempty detached restore through production owners,
  and prepare an exact commissioning packet without live activation or science.
managed_write_set:
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/research_write_lookup.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/opportunity_episode_release.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/collector_read_model.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_provider_pacing.py
- src/solana_alpha_lab/factory/hot90_storage_admission.py
- src/solana_alpha_lab/factory/operability_watch.py
- src/solana_alpha_lab/factory/live_cohort_vanilla_path.py
- scripts/prove_opportunity_episode_operability.py
- scripts/prepare_research_write_lookup.py
- scripts/prove_opportunity_episode_rehearsals.py
- tests/test_research_write_lookup.py
- tests/test_opportunity_episodes_operability_v1.py
- tests/test_opportunity_episodes_vertical_v1.py
- docs/tasks/OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1.md
- docs/contracts/research_write_lookup_v1.md
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
- docs/evidence/opportunity_episodes_bounded_operability_v1/**
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
- STOP_PRODUCTION_IMPORT_REAL_SCIENTIFIC_LOOK_DESTRUCTIVE_CLEANUP
- STOP_JUPITER_CORE_RESELECTION_OR_SCIENCE_INTEGRITY_WEAKENING
- STOP_NEW_STORAGE_ENGINE_SERVICE_OR_QUOTA_SERVICE
context_requirements:
  catalog_asset_ids: [MODULE-FACTORY-V1-RESEARCH-STORE-001, MODULE-OBSERVATION-SCHEDULER-001, MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001]
  l2_roles: [EXTERNAL_ROUTE_KNOWLEDGE, ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: [CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010]
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/contracts/opportunity_episodes_jupiter_v1.md]
    DELIVERY_EVIDENCE: [docs/evidence/opportunity_episodes_bounded_operability_v1/a1_delivery_completion_evidence_v1.json]
    HISTORICAL_CONTEXT: []
---

# OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH. Route DIRECT_CODEX_DELIVERY,
actor CODEX. MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH.
Authority: the owner's explicit 2026-10-06 instruction and attached
SMIAL_JUPITER_OPERABILITY_PREPARATION_V1_EXECUTOR_2026-10-05.md. The external
readback grant is narrower than external_caps: metadata-only existing canonical
VPS access via SEM-REMOTE-OPS-RECOVERY, no host mutation or secret read. GitHub
ordinary transport is permitted. The design anchor equals live origin/main.
Time gates are resolved/superseded; optional exports do not route work.

DECISION_DELTA: the owner can assess readiness to commission one bounded canary.
UNCERTAINTY_REMOVED: fresh-process history cost and recovery across the ordinary
producer, publication, transport/import and backup owners.
CAPABILITY_OR_EVIDENCE: owner-level bounded exact lookup, R1-R4 evidence,
FACT/MODEL/UNKNOWN readout and one operational commissioning packet outside Git.
Consumers: operator, shared publisher, legacy writer/readers, episode consumer.
Cheapest falsifier: real CLI tick with complete TickPhysicalOverrides on valid
growing history, before changing production owners. Setup is separately timed.
DoD: frozen-base before/after, 1/7/30/doubled-history cold work/bytes counters,
integrity/crash/rollback regression, pressure/drain, fresh capture retry after
72h workstation absence, detached nonempty restore and numerical replay;
every rehearsal yields a result or an exact typed boundary. No live PASS.
Risks: derived lookup stale/corrupt state, lost identity, metadata versus audit
guarantees, resource reserve, profile fragments, unknown shared consumers.
Rollback: owner-gated code revert preserves canonical source/ledger and old
writer readability; old writes invalidate the optional derived lookup.
STOP: merge boundary; never merge in this atom. CI queue is PENDING_INFRA.
NEXT: exact-head machine merge gate, followed only later by separately scoped
OPERATE commissioning and separate science authority.
REPLAN_TRIGGER: repeated seam after owner repair; impossible falsifier; scope,
science/integrity or external authority expansion. Replan inside this atom.
Evidence budget: baseline 0/32/128 transactions; final 1/7/30/60-day equivalent
valid materialization, no 97/365-day materialized run, bounded local synthetic
roots. Freeze numeric proof ceilings before final runs. No normal-population
or runtime-limit adjustment to make evidence pass.
Frozen local final-proof ceilings (before measured R1 final ticks): wall <30 s,
peak RSS <512 MiB, <=7 canonical partitions for the fixed normal work and zero
full manifest inventories. Host observed collector MemoryMax=1 GiB, cadence=60 s,
TimeoutStartUSec=infinity: local ceiling reserves half the unit memory and half
the cadence. These are LOCAL_LIMITS; Linux acceptance remains UNVERIFIED. Baseline
history is valid one-record transactions. R1 ages 3 research transactions per
publication at the 5-minute trajectory grid (288 publications/day): 864/6048/
25920/51840 transactions; setup and explicit preparation timed separately.
Reuse/build: WRAP current ResearchStore, publisher, call ledger, allocation,
release/import, Forge and backup owners. No dependencies or plugin installation.
Tools: existing deterministic scripts + Git/GitHub CLI + existing SSH only.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE;
WATCH=separate single-lane canary after exact-host/account envelope proof.

Required reviews: isolated code, goal/DoD, architecture and owner UX. Architecture
must name passing tests that could still break research validity. No self-review
PASS. Generated sync and evidence binding use the frozen expected base.
