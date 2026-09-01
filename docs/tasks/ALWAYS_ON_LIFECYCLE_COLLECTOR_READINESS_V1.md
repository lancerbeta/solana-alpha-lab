---
task_id: ALWAYS_ON_LIFECYCLE_COLLECTOR_READINESS_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9b0c4b57b9bc86f87c6aefe7026d21963aa6db3f
  expected_upstream: origin/main
  expected_upstream_oid: 9b0c4b57b9bc86f87c6aefe7026d21963aa6db3f
  expected_branch: cursor/always-on-lifecycle-collector-readiness-v1
  dirty_mode: ALLOW_REPORTED
objective: Prove ObservationSchedule is safe/schedulable as a 24/7 Tokens V2
  lifecycle collector on Free-tier envelope — fairness, HTTP-class persistence,
  capacity oracle, discovery diagnostics, sanctioned credential name, collector
  read model, and zero-network campaign preflight — without providers,
  credential values, VPS deploy, or a second platform.
managed_write_set:
- docs/tasks/ALWAYS_ON_LIFECYCLE_COLLECTOR_READINESS_V1.md
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_schedule_runtime.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/collector_schedulability_oracle.py
- src/solana_alpha_lab/factory/collector_campaign_preflight.py
- src/solana_alpha_lab/factory/collector_read_model.py
- configs/observation_schedule_runtime_v1.yaml
- catalog/schemas/observation_schedule_runtime_v1.schema.json
- scripts/collector_campaign_preflight.py
- scripts/observation_schedule.py
- tests/test_collector_readiness_bridge.py
- tests/test_observation_scheduler.py
- tests/test_observation_schedule_runtime.py
- docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_completion_evidence_v1.json
- docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_independent_review_v1.json
- docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_factory_fit_v1.json
- docs/reports/always_on_lifecycle_collector_readiness/a2_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- .env.example
- configs/factory_remote_ops/secrets.env.example
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_SECOND_SCHEDULER_OR_PLATFORM
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_FREE_TIER_CAPACITY_NOT_PROVEN
- STOP_VERTICAL_PROOF_UNREPAIRABLE
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- A3_OR_LATER_SCOPE_CREEP
- WALLET_BUILD_EXECUTE_TRANSACTION
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
    - docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_completion_evidence_v1.json
    - docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_independent_review_v1.json
    - docs/evidence/always_on_lifecycle_collector_readiness/a2_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# ALWAYS_ON_LIFECYCLE_COLLECTOR_READINESS_V1

## SPEC_ROUTE

`PRD_LITE` — master roadmap
`PRD_SSD_FORGE_EVIDENCE_PLANES_VPS_DISCOVERY_ROADMAP_V2.md` section A2 is the
product authority. This file is the exact frozen task contract on
`main@9b0c4b57b9bc86f87c6aefe7026d21963aa6db3f`.

## Decision capsule

- **DECISION_DELTA:** ObservationSchedule becomes demonstrably safe/schedulable
  as a 24/7 Tokens V2 lifecycle sensor under Free-tier constraints.
- **UNCERTAINTY_REMOVED:** whether source-poll fairness, HTTP-class persistence,
  capacity, credential naming, and operator read model sustain the intended
  campaign without babysitting.
- **CAPABILITY_OR_EVIDENCE:** `CAP-ALWAYS-ON-LIFECYCLE-COLLECTOR-READINESS-V1`
- **STOP:** one PR exact merge gate; zero provider calls / credential values /
  deployment / spend.
- **NEXT:** A3 historical bind then A4 live campaign preflight (operations).

## Required end-state

1. Bounded source-poll fairness under due-work load.
2. `http_status`/`http_class` survive transport → ledger → recovery → health.
3. Deterministic scheduler-aware capacity/schedulability oracle.
4. Free-tier campaign envelope with material headroom (or
   `STOP_FREE_TIER_CAPACITY_NOT_PROVEN`).
5. Discovery lag / coverage quality machine-visible.
6. One unambiguous sanctioned Jupiter credential runtime contract.
7. Existing doctor/status extended into collector read model.
8. Zero-network campaign preflight proposes schedule + authority packet
   (no authorize/activate).

## Non-goals

No provider calls, credential value reads, VPS deploy, new provider, paid plan,
HA, second VPS, Prometheus/Grafana/Sentry, Postgres, quote collection, Forge run,
A3+ historical bind or live activate.

## X point

Prefer X300. Later X only from `{300, 600, 900}` via outcome-blind timing
evidence; otherwise keep X300 and surface discovery lag as commissioning metric.
