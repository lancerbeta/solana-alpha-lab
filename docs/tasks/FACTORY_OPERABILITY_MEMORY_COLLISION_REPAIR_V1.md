---
task_id: FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-11"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base:  c2797a7082c9a01b25fef956be0f4f3d648c13bf
  expected_upstream: origin/main
  expected_upstream_oid:  c2797a7082c9a01b25fef956be0f4f3d648c13bf
  expected_branch: cursor/factory-operability-memory-collision-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make Factory operability watch and daily owner pulse O(metadata) so they
  no longer materialize the live scientific corpus or retain a whole-RDP
  path inventory, and move the daily pulse off the exact :15 watch boundary.
  Monitoring/resource safety only; no collector, provider, publication,
  SOURCE_DATA_STALE, deploy, or live mutation.
managed_write_set:
  - docs/tasks/FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1.md
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/collector_owner_pulse.py
  - configs/factory_remote_ops/factory-collector-owner-pulse.timer
  - tests/test_factory_operability_memory_collision_repair_v1.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_operability_memory_collision_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_operability_memory_collision_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_operability_memory_collision_repair/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_operability_memory_collision_repair/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - COLLECTOR_SCHEDULER_PROVIDER_PUBLICATION_CHANGE
  - SOURCE_DATA_STALE_CHANGED
  - TARGET40_OR_HARD50_CHANGED
  - INCIDENT_GRACE_CHANGED
  - OPERABILITY_WATCH_CADENCE_CHANGED
  - OBSERVATION_TIMER_CHANGED
  - CENSORED_LATE_OR_SCIENTIFIC_DATA_MUTATION
  - SWAP_OR_CGROUP_CAP_WITHOUT_EVIDENCE
  - PRODUCTION_DEPLOY_OR_SYSTEMD_HOST_MUTATION
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
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
      - src/solana_alpha_lab/factory/collector_operational_packet.py
      - src/solana_alpha_lab/factory/collector_owner_pulse.py
      - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
    DELIVERY_EVIDENCE:
      - docs/reports/factory_operability_memory_collision_repair/a1_owner_readout_v1.md
    HISTORICAL_CONTEXT: []
---

# FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1

## SPEC_ROUTE

`PRD_LITE` — this file is the exact Git contract. No separate design spec.

## ENTRY VERDICT

`START_AS_WRITTEN`

`BASE_MAIN=c2797a7082c9a01b25fef956be0f4f3d648c13bf`.
Production remains behind main (`DEPLOYED_SHA=8b230e036613dcc3acab274c83232ec87698a744`).
This atom does not deploy.

## RESOURCE_CAUSE

Confirmed in `build_collector_operational_packet` consumers
(`factory_operability_watch`, `collector_owner_pulse`):

A. `_rdp_total_and_open_json` retains `files: list[tuple[Path, int]]` of every
   regular RDP file before summing. Algorithmic class: `O(file_count)` Path
   inventory.

B. `_live_release_fields` calls `load_observation_rdp_source`, which
   `json.loads` `live_observation_rebuild/source_snapshot.json` and then
   `sha256_bytes(path.read_bytes())` (second full-file read) and materializes
   `members` / `observations`.

C. The same packet then calls `rdp_bytes_excluding_publication_jobs`, a second
   whole-RDP `rglob("*")`. `_live_release_fields` also `glob("**/release_manifest.json")`
   over the scientific tree.

Dominant expensive path is this monitoring packet, not collector tick logic.
No replan.

## Task Outcome Brief (PRD_LITE)

- Owner decision: resource safety of operational monitoring only.
- Named consumer: Factory unattended watch / daily owner pulse packet.
- Cheapest falsifier: ordinary packet completes while
  `load_observation_rdp_source` raises; RDP byte facts match a representative
  tree without retaining a path list; pulse calendar is not 06:15 UTC.
- User-visible result: Git-side monitoring no longer collides with itself at
  06:15 and no longer materializes live science to say UNKNOWN-capable status.
- Non-goals: SOURCE_DATA_STALE; remote-doctor is-active; collector/provider/
  publication execution; CENSORED_LATE rewrite; swap/cgroup caps; deploy.
- Evidence budget: R1–R9 focused tests plus independent review.
- Replan trigger: any HARD EXCLUSION required for DoD; collector behavior change
  required for memory safety.

## DECISION_DELTA

- One streaming RDP walk produces total / OPEN / science-excluding-jobs.
  `resident = total - open`. OPEN includes `*.json.tmp`.
- Ordinary packet does not call `load_observation_rdp_source`. Lifecycle
  fields without bounded manifest truth stay `UNKNOWN`.
- Daily pulse calendar moves to `*-*-* 06:20:00 UTC`. Watch stays
  `*-*-* *:0/15:00 UTC`. Observation timer unchanged.

## UNCERTAINTY_REMOVED

Operability monitoring no longer has to deserialize the live cohort snapshot
or keep every RDP path in RAM to emit owner health.

## CAPABILITY_OR_EVIDENCE

Git-side bounded operational packet + non-colliding daily pulse schedule.
Live MemoryPeak is a post-deploy commissioning plan, not this atom.

## STOP

Exact owner merge phrase after CI and merge-readiness. No deploy.

## NEXT

`FACTORY_SOURCE_DATA_STALE_EXPECTATION_AWARE_V1`

Residuals: `REMOTE_DOCTOR_SINGLE_SAMPLE_FALSE_DOWN_WATCH`.
The 18 SEARCH CENSORED_LATE rows stay untouched historical typed missingness.
