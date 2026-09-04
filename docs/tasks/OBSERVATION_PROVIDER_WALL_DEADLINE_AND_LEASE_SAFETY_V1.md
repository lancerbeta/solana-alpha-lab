---
task_id: OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 6a3a8734a51c27be4a49cae6d81513c1720e83e6
  expected_upstream: origin/main
  expected_upstream_oid: 6a3a8734a51c27be4a49cae6d81513c1720e83e6
  expected_branch: cursor/observation-provider-wall-deadline-lease-safety-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Ensure a stalled Jupiter read-only provider operation cannot outlive the
  ObservationSchedule safety envelope: introduce one hard wall-clock provider-call
  deadline (end-to-end, not socket inactivity alone), keep lease ownership without
  self-fencing during bounded waits, map hard deadline to typed TIMEOUT/missingness,
  and keep STARTED-call restart semantics fail-closed via IN_FLIGHT_CALL_INDETERMINATE.
  No VPS deploy in this atom.

managed_write_set:
  - docs/tasks/OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1.md
  - src/solana_alpha_lab/factory/observation_provider_wall_deadline.py
  - src/solana_alpha_lab/factory/observation_scheduler.py
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - scripts/observation_schedule.py
  - configs/observation_schedule_runtime_v1.yaml
  - catalog/schemas/observation_schedule_runtime_v1.schema.json
  - tests/test_observation_provider_wall_deadline_and_lease_safety_v1.py
  - configs/ci_test_shards_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/observation_provider_wall_deadline_and_lease_safety_v1/a1_owner_readout_v1.md
  - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - EQUIVALENT_CAPABILITY_ALREADY_EXISTS
  - PRODUCTION_CONFIG_OR_SCHEMA_WIDENING_BEYOND_WALL_FIELD
  - PROVIDER_ROUTE_OR_CREDENTIAL_CHANGE_REQUIRED
  - RETRY_OR_FALLBACK_AUTHORITY_WIDENING
  - SCIENTIFIC_ESTIMAND_OR_SAMPLING_CHANGE_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - DEPLOYMENT_OR_VPS_ACTION_REQUIRED
  - SECOND_ARCHITECTURE_PIVOT
  - REPEATED_MATERIAL_BLOCKER
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - LEASE_SECONDS_INCREASE_AS_SOLE_FIX

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
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/observation_provider_wall_deadline_and_lease_safety_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1

## Decision delta

Can a stalled provider I/O operation outlive `LEASE_SECONDS` and self-fence the
scheduler, stopping scientific RDP progress — and can one hard wall-clock
provider-call deadline close that envelope without inventing retries or raising
lease TTL as the sole fix?

## Binding

- Base: `6a3a8734a51c27be4a49cae6d81513c1720e83e6` (post-#255 main)
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `BOTH`
- Live VPS deploy remains separate owner gate

## Terminal

`OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_PASS`

## Non-claims

No VPS deploy/commissioning, no provider forever-compat, no alpha/cashflow,
no systemd timer retune as primary repair, no historical evidence rewrite.
