---
task_id: I3_MANAGED_COLLECTION_CONTINUITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-14'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 07c81a99f2d0f385df66de2e1a5254e224c6b3b3
  expected_upstream: origin/main
  expected_upstream_oid: 07c81a99f2d0f385df66de2e1a5254e224c6b3b3
  expected_branch: claude/i3-managed-collection-continuity-v1
  dirty_mode: ALLOW_REPORTED
objective: Replace the per-window manual register/authorize/activate of OPPORTUNITY_EPISODES collection by one owner-approved managed profile (standing grant) from which the existing tick derives, activates and keeps committed tails alive for lawful one-UTC-day child schedules, with crash-safe resume, shared account accounting preserved, durable incidents/recovery through the existing watch and operational plan/apply/rollback/stop; ship without deploy, new live grant, provider call or deletion.
managed_write_set:
- docs/tasks/I3_MANAGED_COLLECTION_CONTINUITY_V1.md
- docs/evidence/i3_managed_collection_continuity_v1/**
- docs/contracts/opportunity_episodes_jupiter_v1.md
- docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md
- src/solana_alpha_lab/factory/managed_collection.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/opportunity_episode_tick.py
- src/solana_alpha_lab/factory/hot90_storage_admission.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/operability_watch.py
- scripts/observation_schedule.py
- catalog/schemas/observation_schedule_authority_v1.schema.json
- tests/test_managed_collection_continuity_v1.py
- tests/test_managed_collection_release_seam_v1.py
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
- STOP_PRODUCTION_DEPLOY_COMMISSIONING_PROFILE_APPLY_NEW_LIVE_GRANT_TIMER_CHANGE_DELETION_OR_PROVIDER_CALL_BEFORE_SEPARATE_EXACT_OPERATE_GATE
- STOP_COLLECTOR_GRANT_FROZEN_SCHEDULE_STORAGE_PROTECTION_C1_C2_ARMED_B_TIMER_OR_SCIENCE_CHANGE
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
    - docs/evidence/i3_managed_collection_continuity_v1/completion.json
    - docs/evidence/i3_managed_collection_continuity_v1/independent-review.json
    - docs/evidence/i3_managed_collection_continuity_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# I3_MANAGED_COLLECTION_CONTINUITY_V1

Owner EXECUTE of the atom PRD/SSD `I3_MANAGED_COLLECTION_CONTINUITY_V1_PRD_SSD.md`
(14.10.2026; owner file SHA256
`72d529c1f0155dfd95ee3313732e4d5c91ad30c7e59149d5304bb4e471fb1fdd`), stored as
`docs/evidence/i3_managed_collection_continuity_v1/source-contract.md`
(SHA256 `49abf7967ec9998d200de0130ae7e5c054ca6e470f2e89d6251f955ee150145e`; identical
except trailing markdown hard-break spaces removed on 5 lines for the whitespace hook). It
refines section 6 of the parent `SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`
(`docs/evidence/smial_managed_collection_i1_v1/source-contract.md`). I1 and the
shared-account bridge (`I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1`, merged #400)
are accepted and reused, not repeated.

ENTRY_DECISION: START_AS_WRITTEN. SPEC_ROUTE: BOTH (accepted atom PRD/SSD).
Route/actor: DIRECT_CLAUDE_CODE_DELIVERY/CLAUDE_CODE.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH (authority, schema and lifecycle surfaces).
DECISION_DELTA: Petr approves one profile; the VPS creates, authorizes, activates and
serves one-UTC-day children and their tails without per-window manual steps.
UNCERTAINTY_REMOVED: whether derived child authority, one-owner-per-UTC-day, crash
resume, the managed storage decision (no forged PASS), HOLD-versus-DRAIN and alert
dedup compose on the existing owners over several UTC boundaries.
CAPABILITY_OR_EVIDENCE: `managed_collection.py` plus seams in lifecycle, store, tick,
storage owner, CLI and watch; `collection-status|plan|apply|reconcile|stop-intake|
rollback`; vertical test across three UTC days with one phrase plus a release seam proof (four
managed days across a weekly boundary through the existing verify/import/preflight).
Named consumer: the default `observation_schedule.py tick --once` and the OPERATE agent.
Cheapest falsifier: real CLI flow on a disposable store — approved profile, native
child, actual admissions, natural close, next generated child, mixed tails, no owner
phrase inside the loop (`tests/test_managed_collection_continuity_v1.py`).
STOP: exact merge gate or material blocker.
NEXT: one prepared OPERATE packet (deploy, parent-only apply, B takeover on 18.10 or
the nearest lawful boundary, Telegram TEST incident/recovery readback), then I2 packaging.
REPLAN_TRIGGER: repeated seam failure, impossible oracle, second route pivot, material
resource risk or budget breach. Evidence budget: disposable SQLite stores and the
existing synthetic episode harness; no provider request, no production write, no
pre-PR full local suite.

Tool Entry: existing delivery-harness, Git/gh, locked Python, SQLite, systemd (not
touched). New plugin/connector/MCP/automation/package/service: NONE.
Factory Fit: FULL_REVIEW. NOW: managed continuity. WATCH: I2 packaging (runway is
unproven until applied), admission rate above the V1 episode ceiling (needs a measured
managed adapter), external host-loss watcher.

Protected, unchanged: A `ACT-4744D4017AC4B196` (schedule `4744d401…`, authority
`c2c937b4…`, storage envelope `fa6450ba…`, protection `f70a7f2d…`), armed B
`ACT-A26CF9B0815A36F2` and its `factory-i3-b-activate` timer, C1/C2 and every frozen
identity, V1 human grants, and scientific semantics (filters, seed, T0, grid,
missingness).

Honest scope limits carried into the PR (not silently dropped):
- Admission rate above the frozen V1 validator ceiling (100/day) is refused by `plan`
  with numeric axes; a lifted ceiling needs a separately measured managed adapter.
- One managed lineage per ops store is supported and tested.
- Provider and Telegram transport are not exercised; the incident path is proven up to
  the existing watch's pending-message queue. Live delivery is an OPERATE acceptance.
- Long-runway (`MONTHS_RUNWAY_SUPPORTED`) needs I2 packaging evidence; `plan`/`status`
  report the five I2 metrics and count expected savings as zero until applied.
- The deadman for a lost VPS is not provided here (`HOST_LOSS_ALERT_UNPROVEN`).
- Not proven here, named instead of implied: five or more UTC boundaries and a weekly
  boundary (three child days are proven); 180-day/100-week time-advanced rollover and
  bounded-metadata/RSS at scale; (seal/import/preflight of managed children is now exercised by
  tests/test_managed_collection_release_seam_v1.py on an isolated corpus); a test that an older binary rejects derived
  authority (stated as a rule: no binary rollback after the first managed child); Telegram
  outage retry and delivery health; conservative debit of an uncertain HTTP send inside
  managed scope (covered by the shared-account suite).
- Approval is integrity, not provenance: the phrase hash is derived from the profile, so
  write access to the OPS store equals grant authority, as with V1 phrases. Provenance is the
  OPERATE process and the owner-attention gate, not this code.
- A HOLD round and a window that opens mid-day leave no per-round ResearchEvent: the gap is
  an incident plus the absence of nomination rows, so consumers must treat nomination gaps
  as UNKNOWN, never as "no opportunity", and key cohort statistics on the actual child
  window, not on the UTC date alone.
- The controller runs inside the tick: if the tick timer itself is dead, only the existing
  generic stale-collector and required-timer alerts fire, not a managed-owner incident.
- Backup freshness is what the existing backup owners report; archive content is not
  re-verified here. Whole-factory footprint reuses the collector packet's measurements; a
  volume not visible to them (unrelated residents) stays outside TARGET/HARD and is covered by
  the separate physical free-space reserve only.

DoD before merge: derived child authority limited by the approved grant and tick-time
immutable fit; one owner per UTC day (no fragmented day); crash resume from the saved
intent including ACTIVE-before-event repair; HOLD keeps a managed child open under a
physical shortfall while unmanaged keeps sticky drain; resource decision never reports
PASS it did not earn; plan/apply/rollback/stop/status read-only or fenced as documented;
watch raises one incident and one recovery and no false daily successor alarm; regression
of shared-account, lifecycle, store, scheduler, episode and operability suites; contract
and runbook propagation; four isolated critics; bound evidence; exact-head CI and machine
readiness; one prepared OPERATE packet. Runtime outcome stays
CODE_READY_RUNTIME_PENDING until a separately authorized commissioning.
