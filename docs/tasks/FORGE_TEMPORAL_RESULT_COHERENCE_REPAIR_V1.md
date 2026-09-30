---
task_id: FORGE_TEMPORAL_RESULT_COHERENCE_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-30'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CLAUDE_CODE_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 6b11fb786ae92e3bad1e6d783e03ed2635348a26
  expected_upstream: origin/main
  expected_upstream_oid: 6b11fb786ae92e3bad1e6d783e03ed2635348a26
  expected_branch: claude/forge-temporal-result-coherence-repair-v1
  dirty_mode: FORBIDDEN

objective: >-
  Make every conditional temporal view (pooled, by_calendar_block, by_cohort)
  read the same matched, observed, integrity-clean sample, and let one saved
  wrong result be corrected by an explicit append-only CALCULATION_REVISION
  on the same spec and frozen input without a new MAIN look. The ordinary
  readback, freeze and downstream consumer then select the corrected
  revision, and an incoherent summary is never science-ready evidence.

managed_write_set:
  - docs/tasks/FORGE_TEMPORAL_RESULT_COHERENCE_REPAIR_V1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/evidence/forge_temporal_result_coherence_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_temporal_result_coherence_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_temporal_result_coherence_repair/a1_delivery_factory_fit_v1.json
  - docs/evidence/forge_temporal_result_coherence_repair/copy_based_revision_acceptance_v1.json
  - docs/evidence/forge_temporal_result_coherence_repair/historical_blast_radius_v1.json
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_temporal_result_coherence_v1.py
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_ordinary_operation_v1.py
  - tests/test_hfic_ordinary_operation_acceptance_v1.py
  - tests/test_hfic_temporal_production_runner_v1.py
  - tests/test_hfic_temporal_operability_repair_v1.py
  - tests/test_hfic_temporal_owner_path_v1.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - NEW_LIVE_LOOK
  - LIVE_STORE_WRITE_BEFORE_MERGE
  - NEW_PROVIDER
  - HOLDOUT_ACCESS
  - PREDICATE_HORIZON_OR_CLOCK_CHANGE
  - REOPEN_CLOSED_355
  - MERGE_BEFORE_OWNER_PHRASE

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
      - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
      - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_temporal_result_coherence_repair/copy_based_revision_acceptance_v1.json
      - docs/evidence/forge_temporal_result_coherence_repair/historical_blast_radius_v1.json
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: NONE

DECISION_DELTA: >-
  A conditional temporal view reads only matched members with an observed
  target and no integrity exclusion. A saved result that breaks this is a
  technical stop with an exact repair action, not a reason to authorize more
  looks. Its correction is an explicit CALCULATION_REVISION bound to the
  source ref and hash; it spends no MAIN.

UNCERTAINTY_REMOVED: >-
  Whether the saved WINDOW_LIQUIDITY_SURVIVAL_15M_TO_4H SIMPLE look can be
  read on correct cohort evidence without a second MAIN, and whether the
  ordinary replay, freeze and consumer pick the corrected revision instead
  of the earliest stored result.

CAPABILITY_OR_EVIDENCE: >-
  Shared conditional selector for pooled, calendar and cohort. Runtime
  coherence check on producer, ordinary replay, readout and freeze.
  Explicit correction on discovery-execute bound to source ref and hash,
  refused on changed spec or input. Version-aware ordinary replay and
  projection. Tier progress keeps the spent SIMPLE but does not let an
  incoherent summary justify a scientific terminal. Copy-based vertical on
  the real saved question, bounded historical blast-radius readout.

STOP: >-
  Stop at exact-head merge-readiness. The live store is read-only before
  merge. Do not merge before the owner phrase.

NEXT: >-
  After the owner phrase, guarded merge and green post-merge CI, one
  append-only revision of HFIC-ART-DISCOVERY-56BEAD6F516806D152E9F91559F6A7EEA4A5CFCE
  on the unchanged spec and frozen input, then evaluation of the same
  question. New MAIN, ADAPTIVE and PREVIEW stay 0. No new threshold,
  horizon or cohort subset.

Live checkpoint verified on an isolated copy before any change:
journal `58d69e43…`, operation `338eb5ff…` (PAUSED_CAP, cap 1/0/0),
spec `cc7e450b…`, result `fa3effb7…` (HFIC_TEMPORAL_DISCOVERY_CALC_V3),
market `ae771cf5…`. Base code on the frozen input reproduces result
`fa3effb7…` byte for byte.
