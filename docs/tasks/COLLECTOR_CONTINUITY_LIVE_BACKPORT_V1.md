---
task_id: COLLECTOR_CONTINUITY_LIVE_BACKPORT_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-22'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CODEX_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: b652a66af554d96fb4ce3e2de3410c1d04e8bfd1
  expected_upstream: origin/main
  expected_upstream_oid: 11bdb4349071f1309ca3cd48760d707bbdd06a56
  expected_branch: codex/collector-continuity-live-backport-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Prepare a bounded exact-SHA Factory runtime hotfix from the already merged
  collector continuity repair on the live ZIP64 lineage. Preserve the live
  ZIP64 backup fix and backport only continuity lifecycle selection, late
  successor recovery, continuity-valid successor attention, Telegram
  ATTENTION rendering, fail-closed owner next-actions, required tests, runbook,
  and catalog propagation. Do not deploy or mutate the VPS.

managed_write_set:
  - docs/tasks/COLLECTOR_CONTINUITY_LIVE_BACKPORT_V1.md
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/system_operability.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/remote_ops.py
  - src/solana_alpha_lab/factory/observation_schedule.py
  - src/solana_alpha_lab/factory/observation_scheduler.py
  - scripts/observation_schedule.py
  - tests/test_collector_campaign_continuity_repair_v1.py
  - tests/test_observation_schedule_lifecycle.py
  - tests/test_collector_continuity_boundaries_v1.py
  - tests/test_mutable_backup_zip64_repair_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - BACKPORT_NOT_BOUNDED
  - STOP_VPS_OR_DEPLOY_REQUIRED
  - STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
  - STOP_AUTHORIZE_OR_ACTIVATE_ON_LIVE_VPS
  - SQLITE_SCHEMA_MIGRATION_REQUIRED
  - SOURCE_DATA_STALE_SEMANTICS_CHANGED
  - CURRENT_MAIN_RUNTIME_PREREQUISITE_REQUIRED
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - RUNTIME_HISTORY_REWRITE
  - NEW_SCIENTIFIC_TRIAL_REQUIRED

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
      - src/solana_alpha_lab/factory/research_store.py
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - src/solana_alpha_lab/factory/collector_read_model.py
      - src/solana_alpha_lab/factory/operability_watch.py
    DELIVERY_EVIDENCE:
      - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/collector_continuity_live_backport_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_CONTINUITY_LIVE_BACKPORT_V1

## TASK_OUTCOME_BRIEF

- **Owner decision:** Decide whether to open the separate owner-gated Factory
  deploy step for this exact candidate; this task grants no deploy authority.
- **Product outcome:** A bounded runtime hotfix on the live ZIP64 lineage that
  restores fail-closed continuity selection, forward late recovery, valid
  successor attention, and Telegram ATTENTION rendering.
- **Named consumer:** The Factory operator/owner using lifecycle `status`,
  `doctor`, and scheduled `tick`, plus the existing Telegram owner surface.
- **Cheapest falsifier:** Run the targeted continuity and boundary tests,
  including stale ACTIVE / append-only proof, valid versus historical or
  post-gap authority, late forward recovery, warning severity, and the ZIP64
  regression. Any contradicted invariant denies readiness.
- **Terminal outcomes:** `READY_FOR_BOUNDED_DEPLOY` only with exact-head tests,
  independent reviews, and harness evidence; `BACKPORT_NOT_BOUNDED` for an
  unrelated prerequisite or semantic drift; otherwise `BLOCKED_<exact reason>`.
- **User-visible result:** Exact candidate SHA, bounded path diff, test/review/
  harness receipts, proposed deploy/restart/rollback method, and an explicit
  stop before the separate owner deploy gate.
- **Non-goals:** No VPS mutation or deploy, provider/credential action,
  authorize/activate, scientific trial or alpha claim, or `SOURCE_DATA_STALE`
  semantic change. The only write-set additions are the owner-authorized
  pre-cutover `DRAINING` operational-stop seam in `observation_scheduler.py`
  and the already-required `tests/test_observation_schedule_lifecycle.py`
  proof adaptation. No other scheduler behavior changes.
- **Evidence budget:** One candidate on the exact live parent, the listed
  targeted suites, ZIP64 regression, three required independent review roles,
  targeted Catalog propagation, then exact-head harness CI/readiness. Run any
  full Catalog/hash closure at most once and only after the reviews pass, if a
  final harness gate requires it.

## DECISION_DELTA

Deliver the already reviewed continuity repair on the exact live lineage
`ba7f3b725ff4f609e251a4e57751246636e8f8f7`, preserving its bounded ZIP64
backup fix and excluding intervening research, Forge, and unrelated mainline
runtime changes.

The harness merge base is the live commit's parent
`b652a66af554d96fb4ce3e2de3410c1d04e8bfd1`; the hotfix branch starts at the
unpublished live child `ba7f3b725ff4f609e251a4e57751246636e8f8f7`.

## UNCERTAINTY_REMOVED

Whether the continuity repair can run on the live lineage without a hidden
mainline prerequisite, and whether the resulting candidate preserves ZIP64
behavior while proving current-activation selection, late forward recovery,
successor warning continuity, and Telegram ATTENTION severity.

## CAPABILITY_OR_EVIDENCE

One exact deploy candidate, targeted lifecycle/Telegram/stale-semantics tests,
ZIP64 regression, proportional independent reviews, catalog propagation, and
exact-head CI evidence. This atom never deploys, authorizes, activates, calls a
provider, or mutates the live VPS.

## STOP

Stop after exact candidate and readiness evidence, before the separate owner
deploy gate. A missing bounded prerequisite or semantic drift is
`BACKPORT_NOT_BOUNDED`.

## NEXT

Owner-gated deployment of the exact candidate through the existing Factory
deploy route, followed by the separate live readback atom.

## REPLAN_TRIGGER

Any additional unrelated runtime prerequisite, schema migration, changed
`SOURCE_DATA_STALE` semantics, ZIP64 regression, or need to rewrite immutable
lifecycle history.
