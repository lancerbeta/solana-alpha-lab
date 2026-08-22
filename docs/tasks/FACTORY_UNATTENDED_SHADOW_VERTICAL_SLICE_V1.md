---
task_id: FACTORY_UNATTENDED_SHADOW_VERTICAL_SLICE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-22'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3d8a3762575507fa6bb9fc6032dedab8a1c65005
  expected_upstream: origin/main
  expected_upstream_oid: 3d8a3762575507fa6bb9fc6032dedab8a1c65005
  expected_branch: cursor/factory-unattended-shadow-vertical-slice
  dirty_mode: ALLOW_REPORTED
objective: Prove one COMMISSIONING_ONLY StrategyVersion can run as an unattended
  SHADOW worker on the existing factory-remote-ops host through market-cohort
  signal to position lifecycle, heartbeat with real progress, restart recovery,
  and isolated live-SQLite backup restore, without signing or rewriting Factory
  runner.
managed_write_set:
- docs/tasks/FACTORY_UNATTENDED_SHADOW_VERTICAL_SLICE_V1.md
- configs/factory_unattended_shadow_vertical_slice_v1.yaml
- configs/factory_unattended_shadow_cohort_fixture_v1.json
- src/solana_alpha_lab/factory/paper_plane.py
- src/solana_alpha_lab/factory/remote_ops.py
- src/solana_alpha_lab/factory/unattended_shadow.py
- scripts/run_factory_unattended_shadow_tick.py
- configs/factory_remote_ops/factory-paper-heartbeat.service
- docs/operator/factory_remote_host_v1.yaml
- docs/operator/FACTORY_REMOTE_HOST.md
- tests/test_factory_unattended_shadow_vertical_slice.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/factory_unattended_shadow/a1_runtime_receipt_v1.json
- docs/evidence/factory_unattended_shadow/a1_acceptance_v1.json
- docs/evidence/factory_unattended_shadow/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_unattended_shadow/a1_delivery_independent_review_v1.json
- docs/evidence/factory_unattended_shadow/a1_delivery_factory_fit_v1.json
- docs/reports/factory_unattended_shadow/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: true
stop_conditions:
- FACTORY_RUNNER_CHANGE
- REAL_FILL_OR_SIGNER_OR_WALLET_TX
- MICRO_LIVE_PATH
- STRATEGY_SPECIFIC_SERVICE_UNIT
- COCKPIT_OPERATIONS_UNHIDE
- SCIENTIFIC_SHADOW_PROMOTION_AFTER_ATOM1_FAIL
- POST_HOC_STRATEGY_TUNING
- PUBLIC_ADMIN_OR_PASSWORD_SSH
- SECRETS_IN_GIT_OR_RECEIPT
- SECOND_SCHEDULER_OR_ORCHESTRATOR
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-STRUCTURAL-BACKING-PIT-COMMISSIONING-001
  - MODULE-PAPER-PLANE-ENGINE-001
  - STRAT-V-EARLY-LIQ-FLOOR-V1-001
  - EVIDENCE-FACTORY-REMOTE-OPERATIONS-A3-ACCEPTANCE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - docs/operator/factory_remote_host_v1.yaml
    - configs/provider_route_capability_registry_v10.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/factory_unattended_shadow/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_unattended_shadow/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_unattended_shadow/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
    - docs/evidence/early_structural_backing_pit_commissioning/a1_family_decision_v1.json
    - docs/evidence/early_state_paper/a1_acceptance_v1.json
---

# FACTORY_UNATTENDED_SHADOW_VERTICAL_SLICE_V1

`ENTRY_VERDICT=START`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=LUNA_MAX`

`ROADMAP_VERDICT=KEEP` for muv-6 Atom 2 after Atom 1
`CLOSE_EARLY_STRUCTURAL_BACKING_FAMILY`.

## Decision capsule

- `DECISION_DELTA`: product line `cohort → SHADOW bot → position lifecycle →
  heartbeat progress → restart → isolated backup restore` becomes true on the
  existing Cherry host using an immutable `COMMISSIONING_ONLY` StrategyVersion.
- `UNCERTAINTY_REMOVED`: whether Factory ops can run unattended shadow workload
  without IDE and without rewriting `factory/runner.py`.
- `CAPABILITY_OR_EVIDENCE`: generic shadow tick WRAP of paper heartbeat;
  offline-pinned cohort (tactical) plus one live remote fault-injection run.
- `STOP`: after typed product PASS/FAIL receipt and PR merge gate.
- `NEXT`: Atom 3 `FACTORY_V1_OPERATIONAL_READY` + foundation freeze only if
  this atom product-passes.

`strongest_rejected_alternative`: live Jupiter quote loop inside this atom.
Rejected now because Atom 1 already closed the scientific family; the named
uncertainty is the unattended ops line, cheaper to prove with pinned cohort +
host restart/backup than with a second provider ceremony.

`ADOPTION_ROUTE=ADOPT_PAPER_PLANE_AND_REMOTE_OPS_WRAP_HEARTBEAT_INTO_SHADOW_TICK_BUILD_NO_RUNNER`

## Non-goals

Alpha, NetReturn, REAL_FILL, micro-live, scientific SHADOW promotion,
Cockpit OPERATIONS unhide, Postgres, Kubernetes, strategy tuning, new provider.

## Definition of Done

1. Zero-network tests: SHADOW≠REAL_FILL, runner SHA pin, heartbeat
   `progress_at` from store, restart preserves bots/positions, isolated
   backup restore hash-equivalent.
2. Live host: shadow tick unit/timer applied; one kill/restart; one backup +
   isolated restore of live paper SQLite; doctor sees non-stale progress.
3. Delivery trio with `integrity.kind=none`; Factory Fit FULL_REVIEW;
   exact-head CI; owner merge phrase.
