---
task_id: FORGE_TEMPORAL_OPERABILITY_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-28'
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
  expected_base: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_upstream: origin/main
  expected_upstream_oid: 86b24cb1abe5867becc1ead16efb3754044550df
  expected_branch: cursor/forge-temporal-operability-repair-v1
  dirty_mode: FORBIDDEN

objective: >-
  One ordinary Forge explores temporal questions on mixed-lateness schedules,
  distinguishes member anchor from snapshot acquisition clocks under
  PROVIDER_REPORTED_SNAPSHOT_V1, surfaces target-exclusion reasons to consumers,
  and supports a narrow owner-authorized repair continuation after completed
  NO_WORTHY without rewriting history or refreshing spent budget.

managed_write_set:
  - docs/tasks/FORGE_TEMPORAL_OPERABILITY_REPAIR_V1.md
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_repair_continuation.py
  - src/solana_alpha_lab/factory/observation_scheduler.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/live_cohort_source_bundle.py
  - configs/observation_primitive_registry_v1.yaml
  - catalog/schemas/observation_primitive_descriptor_v1.schema.json
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_temporal_operability_repair_v1.py
  - tests/test_hfic_repair_continuation_v1.py
  - scripts/hypothesis_forge.py
  - docs/operator/FORGE_TEMPORAL_OPERABILITY_REPAIR_RUNBOOK_V1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/forge_temporal_operability_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_temporal_operability_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_temporal_operability_repair/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/forge_temporal_operability_repair/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - LIVE_REPAIR_CONTINUATION_APPLY
  - MARKET_HYPOTHESIS_FORGE
  - LIVE_RESEARCH_STORE_MUTATION
  - LIVE_MEMORY_POLICY_CHANGE
  - NEW_PROVIDER_OR_PLATFORM
  - RAW_PARQUET_REWRITE
  - MERGE_IN_THIS_ATOM

context_requirements:
  catalog_asset_ids:
    - MODULE-HFIC-TEMPORAL-DISCOVERY-001
    - DOC-HYPOTHESIS-FORGE-OPERATOR-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - MODULE-HFIC-TEMPORAL-DISCOVERY-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_evidence_identity.py
      - src/solana_alpha_lab/factory/observation_scheduler.py
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_temporal_operability_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_temporal_operability_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_temporal_operability_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

## Decision

DECISION_DELTA: mixed point clocks, PROVIDER_REPORTED_SNAPSHOT_V1 acquisition
semantics, target-exclusion reason transport, and owner-authorized repair
continuation after completed NO_WORTHY.
UNCERTAINTY_REMOVED: short Y horizons are no longer blocked by scalar lateness
equality; snapshot exits stop pretending member-anchor equals market-event time;
completed technical NO_WORTHY can continue on the spent ledger after explicit
disposition.
CAPABILITY_OR_EVIDENCE: disposable vertical path + synthetic continuation prove
the owner route; live S3 apply remains out of scope.
STOP: no live apply, market Forge, memory reset, raw rewrite, or merge.
NEXT: after exact-head CI and machine readiness, hand back the unexecuted
post-merge operational plan for the current parent session.
REPLAN_TRIGGER: estimand change, new provider, or raw-history rewrite.
