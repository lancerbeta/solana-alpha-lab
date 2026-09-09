---
task_id: SYSTEM_OPERABILITY_BOUNDED_READ_PATH_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-09"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 94c3397acf68516d69808e224fb61c4f99142a55
  expected_upstream: origin/main
  expected_upstream_oid: 94c3397acf68516d69808e224fb61c4f99142a55
  expected_branch: cursor/system-operability-bounded-read-path-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make owner-facing HOME and /system a bounded current-health read over a
  scheduled collector-derived snapshot so GET cost does not grow with
  Observation RDP, backup tree or operational history, without a new cache
  service, daemon, deploy or Workbench redesign.
managed_write_set:
  - docs/tasks/SYSTEM_OPERABILITY_BOUNDED_READ_PATH_V1.md
  - docs/contracts/system_operability_surface_v2.md
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/system_operability.py
  - tests/test_system_operability_surface_v2.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/system_operability_bounded_read_path/a1_delivery_completion_evidence_v1.json
  - docs/evidence/system_operability_bounded_read_path/a1_delivery_independent_review_v1.json
  - docs/evidence/system_operability_bounded_read_path/a1_delivery_factory_fit_v1.json
  - docs/reports/system_operability_bounded_read_path/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - PREMISE_PACKET_PATH_NOT_MATERIAL
  - SECOND_MONITORING_STORE_OR_SERVICE_REQUIRED
  - FRESHNESS_CANNOT_FAIL_CLOSED
  - SNAPSHOT_BECOMES_SCIENTIFIC_TRUTH_OWNER
  - COLLECTOR_SCIENTIFIC_SEMANTICS_REQUIRED
  - LIVE_HOST_OR_DEPLOY_MUTATION_REQUIRED
  - BROAD_WORKBENCH_REDESIGN_REQUIRED
  - SECOND_UNBOUNDED_NORMAL_GET_CONSUMER
  - NEW_DEPENDENCY_TIMER_DATABASE_OR_CACHE
  - PROVIDER_CREDENTIAL_WALLET_OR_SPEND_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
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
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - docs/contracts/system_operability_surface_v2.md
      - configs/factory_remote_ops/factory-operability-watch.timer
    DELIVERY_EVIDENCE:
      - docs/evidence/system_operability_bounded_read_path/a1_delivery_completion_evidence_v1.json
      - docs/evidence/system_operability_bounded_read_path/a1_delivery_independent_review_v1.json
      - docs/evidence/system_operability_bounded_read_path/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SYSTEM_OPERABILITY_BOUNDED_READ_PATH_V1

## SPEC_ROUTE

`BOTH` — this file is the exact Git repair contract;
`docs/contracts/system_operability_surface_v2.md` remains the durable
SYSTEM_OPERABILITY_SURFACE_V2 product contract and is patched in this atom.

SYSTEM_OPERABILITY_SURFACE_V2 is capability/contract context, not this
repair's execution identity. Do not inherit its historical SHA/branch.

## ENTRY VERDICT

`START_WITH_PATCH`

Fresh Git:

- live `origin/main` = `94c3397acf68516d69808e224fb61c4f99142a55`
- no due unresolved active-time gate
- SYSTEM_OPERABILITY_SURFACE_V2 composer already exists
- `factory-operability-watch.timer` cadence is `*-*-* *:0/15:00 UTC`
- independent probe: ordinary `compose_system_operability()` without
  `collector_packet=` calls `build_collector_operational_packet` once
  when ObservationSchedule sqlite exists
- MARKET GET still bypasses this path

PATCH versus a naive cache/TTL:

1. ADOPT/WRAP existing operability watch as the heavy-compute producer.
   Do not add Redis, a second SQLite, daemon, queue, timer or cache
   framework.
2. Interactive GET is fail-closed on missing/invalid/stale snapshot.
   Stale never rebuilds synchronously.
3. Snapshot is an explicit allowlist of derived operational fields, not
   `dict(packet)`.

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## PRD-lite

- **Owner decision:** Petr opens HOME and `/system` as an operational
  control surface without the HTTP GET recomputing growing RDP /
  backup / history telemetry.
- **Named consumers:** Petr (HOME, `/system`); SMIAL Operator / future
  Letta observer (read-only live operability); `scripts/show_system_operability.py`.
- **Cheapest falsifier:** spies/call-counts prove interactive GET invokes
  zero `build_collector_operational_packet`, zero full
  `build_collector_read_model` fallback, zero recursive RDP/backup walk.
- **User-visible result:** HOME/`/system` stay honest current-health
  projections; heavy derived evidence is timestamped and freshness-aware.
- **Non-goals:** VPS deploy, systemd User/Group, Redis, new daemon,
  Workbench redesign, collector scientific rewrite, `.venv` root-owned CLI.

## DECISION_DELTA

BEFORE: owner GET → live collector packet recomputation → latency scales
with data/I/O/history.

AFTER: scheduled watch computes the packet once per cycle, persists a
bounded snapshot atomically in `operability_incident_state.json`;
interactive GET reads the snapshot plus bounded live system signals.

## UNCERTAINTY_REMOVED

Whether owner GET can remain current-health honest without synchronously
recomputing data-volume-proportional collector evidence.

## CAPABILITY_OR_EVIDENCE

Bounded interactive SystemOperability read + scheduled derived snapshot
with fail-closed freshness.

## STOP

Exact-head CI + merge-readiness `ready_for_owner_phrase=true`.
Do not deploy. Do not ask the merge phrase before readiness.

## NEXT

WATCH = `LEAST_PRIVILEGE_SMIAL_OPERATOR_VPS_OBSERVER` only after this
repair is merged, separately owner-gated deploy completes, post-deploy
snapshot is fresh, and live `/system` latency/semantics are proven.

Secondary WATCH = `FAST_OPERABILITY_SIGNAL_PLANE` only if PAPER/SHADOW/
MICRO-LIVE needs detection faster than the current 15-minute heavy cycle.

## Freshness

Cadence: 900s (`OnCalendar=*-*-* *:0/15:00 UTC`).
Grace: 180s (covers measured packet compute ~15–100s plus calendar jitter).
Fresh max age: 1080s. Two missed cycles (1800s) cannot remain
collector-derived `OK_OBSERVED`.

## First-deploy transition (design only, do not deploy)

Missing `collector_snapshot` after first future deploy → honest
UNKNOWN / NOT_PRESENT, no synchronous rebuild. Judge normal `/system`
semantics only after one scheduled watch cycle writes a post-deploy
snapshot.
