---
task_id: FACTORY_OPERATIONAL_STORE_READONLY_SCHEMA_COMPATIBILITY_V1
task_version: "1.0"
status: READY
as_of: "2026-09-08"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 1f9fbf76555944ab20c51022249922cc6218dc6b
  expected_upstream: origin/main
  expected_upstream_oid: 1f9fbf76555944ab20c51022249922cc6218dc6b
  expected_branch: cursor/factory-operational-store-readonly-schema-compat-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make Workbench GET survive a preserved operational SQLite that has no
  OperationalStore jobs table, without mutating that file on GET. Fail closed
  on incompatible jobs schema. No production deploy.
managed_write_set:
  - docs/tasks/FACTORY_OPERATIONAL_STORE_READONLY_SCHEMA_COMPATIBILITY_V1.md
  - src/solana_alpha_lab/factory/operational_store.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/read_model.py
  - tests/test_factory_operational_store_readonly_schema_compat_v1.py
  - catalog/assets/core.yaml
  - catalog/generated/asset_edges.json
  - docs/reports/factory_operational_store_readonly_schema_compat_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - HARD_EXCLUSION_REQUIRED_FOR_DOD
  - GET_INITIALIZES_OR_MIGRATES_SQLITE
  - INCOMPATIBLE_JOBS_REPORTED_AS_NOT_STARTED
  - ALEMBIC_OR_SCHEMA_REGISTRY_INTRODUCED
  - COLLECTOR_SCIENCE_HOT90_OR_DEPLOY_CHANGE
  - PRODUCTION_DEPLOY_OR_VPS_MUTATION
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
context_requirements:
  catalog_asset_ids:
    - MODULE-FACTORY-V1-OPS-STORE-001
    - MODULE-FACTORY-V1-APPLICATION-001
    - MODULE-FACTORY-V1-READ-MODEL-001
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
      - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_operational_store_readonly_schema_compat_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_OPERATIONAL_STORE_READONLY_SCHEMA_COMPATIBILITY_V1

## Task Outcome Brief (PRD_LITE)

- Owner decision: GET must never crash or mutate a preserved legacy
  `operational_state.sqlite` solely because `jobs` is absent.
- Named consumer: Factory Workbench GET (`/`, `/system`, `/operations`,
  `/economics`, `/research`, `/market`).
- Cheapest falsifier: valid SQLite without `jobs` + GET all surfaces = 200 and
  file SHA256/schema/rows unchanged.
- Non-goals: collector, publication, HOT90, deploy, Alembic, live VPS,
  creating `jobs` on GET.
- `SPEC_ROUTE=NONE` (existing OperationalStore contract seam).

## Frozen atom

- `DECISION_DELTA`: missing `jobs` on a valid existing file is
  `LEGACY_UNINITIALIZED`, not a HTTP crash and not a GET-time CREATE TABLE.
- `UNCERTAINTY_REMOVED`: 2026-09-08 Factory rollout of `1f9fbf76…` crashed GET
  Home/system/operations/economics on `no such table: jobs`.
- `CAPABILITY_OR_EVIDENCE`: readonly sqlite_master / PRAGMA probe + typed
  source status; writable init remains additive.
- `STOP`: exact-head CI + merge-readiness; owner merge phrase; no deploy.
- `NEXT`: separate OPERATE deploy of the merge commit.
- `REPLAN_TRIGGER`: DoD requires a HARD EXCLUSION file, GET mutation, or a
  generic migration framework.

## DoD

PASS only if:

- exact legacy-no-jobs production shape is covered;
- all current Workbench GET surfaces render 200;
- GET performs zero logical DB mutation;
- `get_job` / `latest_job` on that shape do not raise raw sqlite3;
- malformed same-name schema fails closed without HTTP crash and is not
  `NOT_STARTED`;
- current ready schema still reads the stored job payload;
- explicit writable initialization is additive and preserves unrelated data;
- no collector/science/HOT90/deploy changes;
- focused regression tests PASS;
- independent review PASS;
- Factory Fit proportional PASS;
- exact-head CI PASS;
- merge-readiness `ready_for_owner_phrase=true`.
- NO deployment.

## Entry

`START_AS_WRITTEN`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` (schema compatibility / fail-closed
GET purity). No production deploy.

`REUSE_DECISION=WRAP`: reuse stdlib `sqlite_master` / `PRAGMA table_info` and
the existing `OperationalStore(readonly=True)` URI; no new DB platform.
