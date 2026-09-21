---
task_id: COLLECTOR_CAMPAIGN_CONTINUITY_REPAIR_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-21'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 5f658ad9a7a80a33db51dbd83b5e109e0deac1e8
  expected_upstream: origin/main
  expected_upstream_oid: 5f658ad9a7a80a33db51dbd83b5e109e0deac1e8
  expected_branch: cursor/collector-campaign-continuity-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Repair collector campaign continuity on Git/mainline: allow late post-window
  successor activation when the same-family predecessor is proven NON_ADMITTING,
  select current ACTIVE/DRAINING for doctor/status read models, and emit one
  deduped CAMPAIGN_SUCCESSOR_REQUIRED owner attention within 24h of admission
  expiry when no successor is prepared. No VPS mutation, deploy, or provider calls.

managed_write_set:
  - docs/tasks/COLLECTOR_CAMPAIGN_CONTINUITY_REPAIR_V1.md
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - scripts/observation_schedule.py
  - tests/test_collector_campaign_continuity_repair_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - docs/evidence/collector_campaign_continuity_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/collector_campaign_continuity_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/collector_campaign_continuity_repair/a1_delivery_factory_fit_v1.json
  - docs/reports/collector_campaign_continuity_repair/a1_owner_readout_v1.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - STOP_VPS_OR_DEPLOY_REQUIRED
  - STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
  - STOP_AUTHORIZE_OR_ACTIVATE_ON_LIVE_VPS
  - SQLITE_SCHEMA_MIGRATION_REQUIRED
  - SOURCE_DATA_STALE_SEMANTICS_CHANGED
  - AUTO_AUTHORIZE_OR_OWNER_PHRASE
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - RUNTIME_HISTORY_REWRITE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
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
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
      - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - src/solana_alpha_lab/factory/collector_read_model.py
      - src/solana_alpha_lab/factory/operability_watch.py
    DELIVERY_EVIDENCE:
      - docs/evidence/collector_campaign_continuity_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/collector_campaign_continuity_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/collector_campaign_continuity_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_CAMPAIGN_CONTINUITY_REPAIR_V1

## SPEC_ROUTE

`PRD_LITE` — this file is the exact Git contract.

## DECISION_DELTA

Same-family `COHORT_CUTOVER_REQUIRED` must block only while a peer can still
admit; post-window DRAINING recovery may activate a forward successor without a
rollover row. Doctor/status must report current ACTIVE/DRAINING, not a historical
`ABORTED_SAFETY`. Owner Telegram gets one deduped pre-expiry
`CAMPAIGN_SUCCESSOR_REQUIRED` warning.

## UNCERTAINTY_REMOVED

Whether a missed in-window rollover forces a multi-hour admission blackout;
whether historical abort tripwires doctor while DRAINING is current; whether
pre-expiry continuity needs a new daemon.

## CAPABILITY_OR_EVIDENCE

Lifecycle late-successor rule; deterministic current-activation selection;
operability attention with existing incident dedupe; targeted tests 1–17;
runbook + catalog projections.

## STOP

Exact owner merge gate. No VPS deploy, no live ACT-E0CC mutation, no provider
calls, no schema migration, no auto-authorize.

## NEXT

Separate operator atom may deploy repaired main and activate a prepared successor
on the live host.

## REPLAN_TRIGGER

If one-admitting-family cannot be proven without history rewrite, or
`SOURCE_DATA_STALE` must change to cover continuity.
