---
task_id: FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-10"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 18a1111e07b9edcf19c090fa61b119f80983c894
  expected_upstream: origin/main
  expected_upstream_oid: 18a1111e07b9edcf19c090fa61b119f80983c894
  expected_branch: cursor/factory-operability-signal-calibration-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make collector operability current-state recovery-aware: recovered
  same-primitive provider failures must not stay PROVIDER_FAILED via 24h
  counts, and transient publication_jobs/open bytes must not enter 97d
  resident growth. Monitoring/read-model semantics only; no collector,
  provider, publication, deploy, or live mutation.
managed_write_set:
  - docs/tasks/FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1.md
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/collector_owner_pulse.py
  - tests/test_factory_operability_signal_calibration_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_operability_signal_calibration/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_operability_signal_calibration/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_operability_signal_calibration/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_operability_signal_calibration/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - HARD_EXCLUSION_REQUIRED_FOR_DOD
  - STORAGE_ACCOUNTING_CONFLICT
  - PROJECTION_ACCOUNTING_CONFLICT
  - PRODUCTION_DEPLOY_OR_SYSTEMD_HOST_MUTATION
  - OPERABILITY_WATCH_CHANGED
  - SOURCE_DATA_STALE_CHANGED
  - TARGET40_OR_HARD50_CHANGED
  - INCIDENT_GRACE_CHANGED
  - COLLECTOR_SCHEDULER_PROVIDER_PUBLICATION_CHANGE
  - HISTORY_MIGRATION_OR_REWRITE
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
      - src/solana_alpha_lab/factory/collector_read_model.py
      - src/solana_alpha_lab/factory/collector_operational_packet.py
      - src/solana_alpha_lab/factory/hot90_storage_admission.py
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_operability_signal_calibration/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_operability_signal_calibration/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_operability_signal_calibration/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1

## SPEC_ROUTE

`PRD_LITE` — this file is the exact Git contract. No separate design spec.

## ENTRY VERDICT

`START_AS_WRITTEN`

Fresh Git: `BASE_MAIN=18a1111e07b9edcf19c090fa61b119f80983c894`.

## Task Outcome Brief (PRD_LITE)

- Owner decision: surgically remove two live-proven false-positive
  operability mechanisms (24h provider latch; open-job 97d amplification).
- Named consumer: Factory unattended operability watch / owner Telegram
  health classes derived from the collector operational packet.
- Cheapest falsifier: recovered `/recent` TIMEOUT must keep `TIMEOUT_24h=1`
  and drop current `PROVIDER_FAILED`; +open-job bytes must not be `* 97`.
- User-visible result: recovery-aware monitoring; diagnostics preserved.
- Non-goals: collector/scheduler/provider/publication execution; PIT/missingness;
  retention; HOT90 thresholds; timers; deploy; live VPS;
  `SOURCE_DATA_STALE` / long-tick coupling.
- Evidence budget: focused tests P1–P10 and S1–S10 plus independent review.
- Replan trigger: any HARD EXCLUSION required for DoD;
  `STORAGE_ACCOUNTING_CONFLICT`; `PROJECTION_ACCOUNTING_CONFLICT`.

## DECISION_DELTA

Current provider classes are latest-by-time per primitive in the rolling
call set. 24h counters stay diagnostics only. 97d current footprint uses
`resident_rdp_bytes = max(0, observation_rdp_bytes - publication_jobs_open_bytes)`
and counts open bytes once via `staging_peak_bytes`.

## UNCERTAINTY_REMOVED

Whether recovered same-primitive errors can keep `SUSTAINED_PROVIDER_FAILURE`
and whether in-tick open jobs can trip `DISK_RUNWAY_HARD50`.

## CAPABILITY_OR_EVIDENCE

Recovery-aware `PROVIDER_*` health classes and runway that does not multiply
transient OPEN publication bytes by 97.

## STOP

Exact owner merge phrase after exact-head CI and merge-readiness.
`NO DEPLOY`.

## NEXT

Owner merge phrase. Residual:
`SOURCE_DATA_STALE_LONG_TICK_FALSE_POSITIVE_WATCH`.

## PRODUCT_HORIZON

- NOW: none (this atom is the authorized calibration).
- WATCH: `SOURCE_DATA_STALE_LONG_TICK_FALSE_POSITIVE_WATCH` — healthy ticks
  may last ~5 minutes while period is 60s; reopen only with a live
  falsifier or a separately authorized design.
