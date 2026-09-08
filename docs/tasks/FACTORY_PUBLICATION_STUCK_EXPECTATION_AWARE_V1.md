---
task_id: FACTORY_PUBLICATION_STUCK_EXPECTATION_AWARE_V1
task_version: "1.0"
status: READY
as_of: "2026-09-08"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ed2bb1be2252581e4d363e89de21da1f8146f341
  expected_upstream: origin/main
  expected_upstream_oid: ed2bb1be2252581e4d363e89de21da1f8146f341
  expected_branch: cursor/factory-publication-stuck-expectation-aware-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make PUBLICATION_STUCK mean publication progress was expected and failed to
  progress. Suppress RDP_PUBLICATION_STALE during proven healthy idle.
  Operability signal semantics only; no collector, publisher, storage, lease,
  deploy, or live mutation.
managed_write_set:
  - docs/tasks/FACTORY_PUBLICATION_STUCK_EXPECTATION_AWARE_V1.md
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - catalog/assets/core.yaml
  - docs/reports/factory_publication_stuck_expectation_aware_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - HARD_EXCLUSION_REQUIRED_FOR_DOD
  - PRODUCTION_DEPLOY_OR_SYSTEMD_HOST_MUTATION
  - LIVE_TELEGRAM_SEND
  - INCIDENT_CLEAR_OR_TIMER_MUTATION
  - THRESHOLD_INFLATION
  - TIMESTAMP_SOURCE_CHANGE
  - OPERABILITY_WATCH_STATE_MACHINE_CHANGE
  - COLLECTOR_SCHEDULER_PUBLISHER_CHANGE
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_publication_stuck_expectation_aware_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_PUBLICATION_STUCK_EXPECTATION_AWARE_V1

## Task Outcome Brief (PRD_LITE)

- Owner decision: Telegram ACTION for `PUBLICATION_STUCK` only when a current
  publication obligation exists and freshness fails (or expectation evidence is
  missing — fail closed).
- Named consumer: Factory unattended operability watch / owner Telegram.
- Cheapest falsifier: exact live idle case (due/claimed/overdue/in-flight/open
  jobs all proven zero, future-not-due > 0, age > 6h and > 24h) must not emit
  `RDP_PUBLICATION_STALE` / `PUBLICATION_STUCK`.
- Non-goals: collector/publisher/storage/lease/deploy; `.published` mtime vs
  job timestamp; watch grace/dedupe/recovery redesign; new incident; new
  threshold.
- `SPEC_ROUTE=NONE` (semantic refinement of existing health class).

## Frozen atom

- `DECISION_DELTA`: idle age alone is not a publication stall.
- `UNCERTAINTY_REMOVED`: 2026-09-07 live `PUBLICATION_STUCK` is classified as
  expectation-unaware false positive; Git predicate must match that.
- `CAPABILITY_OR_EVIDENCE`: expectation-aware `RDP_PUBLICATION_STALE`.
- `STOP`: exact-head CI + merge-readiness; owner merge phrase; no deploy.
- `NEXT`: separate OPERATE deploy decision after merge.
- `REPLAN_TRIGGER`: DoD requires a HARD EXCLUSION file.

## Entry

`START_AS_WRITTEN`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` (health-class contract / fail-closed
safety signal). No production deploy.
