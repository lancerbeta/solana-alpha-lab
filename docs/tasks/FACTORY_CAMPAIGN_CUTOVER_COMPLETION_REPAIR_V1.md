---
task_id: FACTORY_CAMPAIGN_CUTOVER_COMPLETION_REPAIR_V1
task_version: "1.0"
status: READY
as_of: "2026-10-04"
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fc3db6cf164d73b1289bda8472c21f3d4e3edea7
  expected_upstream: origin/main
  expected_upstream_oid: fc3db6cf164d73b1289bda8472c21f3d4e3edea7
  expected_branch: codex/factory-campaign-cutover-completion-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Prevent premature campaign COMPLETE before effective admission closure,
  prove the real lifecycle/tick loop offline, deliver and commission the exact
  merged code while preserving live campaign authority and ordinary capture.
managed_write_set:
  - docs/tasks/FACTORY_CAMPAIGN_CUTOVER_COMPLETION_REPAIR_V1.md
  - src/solana_alpha_lab/factory/observation_scheduler.py
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - tests/test_observation_schedule_lifecycle.py
  - tests/test_factory_campaign_cutover_completion_repair_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_campaign_cutover_completion_repair/a1_owner_readout_v1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: true
stop_conditions:
  - FAILED_EFFECTIVE_ADMISSION_OR_IMMUTABLE_PROOF
  - FAILED_EXACT_HEAD_CI_OR_MACHINE_MERGE_GATE
  - FRESH_CANONICAL_RELEASE_PREFLIGHT_DENY
  - MATERIAL_CAMPAIGN_AUTHORITY_OR_SAMPLING_CHANGE_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: [docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md]
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_campaign_cutover_completion_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_CAMPAIGN_CUTOVER_COMPLETION_REPAIR_V1

## SPEC_ROUTE / outcome

`BOTH`: compact PRD and design in one contract. Entry gate START_AS_WRITTEN;
existing Delivery Harness, Git/gh, uv and lifecycle proof helpers are sufficient.
No new dependency, service, plugin or monitor. Consumers: minute collector,
campaign renewal and sole operator. Owner decision: safely resume unattended
capture across a prepared future rollover without weekly manual repair.

Raw DRAINING is a stored future transition, not proof admission already closed.
The scheduler must respect its tick-start UTC as-of view. Completion independently
requires proven effective DRAINING and resolved due/publication/recovery work.
Missing, malformed or uncommitted evidence remains UNKNOWN, without a COMPLETE
mutation. Preserve valid early rollover, window-expiry drain, terminal COMPLETE,
replay, typed absence, deadlines and authority. Reuse bounded immutable readers;
no new full historical payload walk each tick.

## Vertical repair loop

First reproduce RED on the frozen base. Through real register/authorize/activate/
rollover and CLI/tick composition with fake provider and temporary SQLite/RDP,
prove: future cutover plus empty queue remains admitting before boundary; restart
preserves this; one activation admits at boundary; a spanning tick uses tick-start
clock; due/open publication/unresolved work blocks completion; drained completion
has exactly one committed event and replay is idempotent. Test early cutover,
missing/malformed proof, terminal COMPLETE and paused future successor. Inspect
mutable sequence and immutable event, not exit alone. Correct the old test that
expected completion before its future transition became effective.

Focused tests include lifecycle, scheduler, renewal and direct commissioning
consumers. Frozen independent code, goal, architecture and operator-UX reviews;
standard Catalog/generated propagation. Git contains sanitized synthetic proof
and navigation; live receipts/configuration/payload stay outside Git.

## Conditional delivery and live acceptance

Owner explicitly authorizes PR, post-readiness substitution of the exact machine
merge phrase, guarded ordinary merge, and canonical post-merge deploy. Never
assert a failed machine gate passed. Preserve branches/settings and campaign.
Fresh narrow preflight checks live SHA, source clocks, effective activation and
authority, recovery, RAM/disk, timer inventory, verified backup/checkpoints and
both target/rollback objects. Prepare exact canonical-forward and code rollback
commands outside Git; SOURCE_REPO may only advance by verified fast-forward.
Previously accepted full backup-chain content SHA UNKNOWN remains explicit.

Deploy exact merged code with existing canonical release. Preserve current
campaign, limits, authority, data and unit configuration; restore temporarily
stopped units to captured inventory, never enable intentionally disabled units.
Run isolated zero-network Linux loop against installed bytes, observe two ordinary
collector cycles and a new due publication's receipt/manifest/marker/OBS+MEM
lineage, plus fresh watch/transport and OOM/timeout evidence. Existing watch/pulse
gates stay <512 MiB/<120 s; collector keeps its own limits. Do not force production
rollover or an outage as a canary. No due means explicit expected wait, not proof.
PASS_CUTOVER_REPAIR_DEPLOYED requires installed SHA, regression loop and live
capture proof; natural future production rollover remains a later observation.

## Bounded adjacent diagnostic / limits

After core commissioning, spend at most 15 minutes attributing publication lag
using normal-cycle metadata or Linux fixture profiling (provider wait, proof,
append/publication time/RSS and historical payload reads). No extra provider calls
or second live writer. A narrow separate performance fix needs its own RED/GREEN;
otherwise report the precise follow-up. Do not change sampling/lateness to hide lag.

DECISION_DELTA: replace premature terminal completion with proved closure.
UNCERTAINTY_REMOVED: future-transition behavior across ticks/restart/cutover.
CAPABILITY_OR_EVIDENCE: checked merged and deployed repair with live capture.
STOP: failed truth/resource/release gate or material authority decision.
NEXT: natural rollover observation and only a measured publication follow-up.
Evidence budget: focused offline loop, one frozen review set, existing exact-head
CI, one canonical release and bounded ordinary-cycle live readback. Replan on
repeated blocker or scope expansion; no monitoring platform construction.
Factory Fit FULL_REVIEW; horizon NOW this reliability repair, WATCH measured
publication backlog growth. MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH.
