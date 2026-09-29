---
task_id: FORGE_LEGACY_PARENT_CONTINUATION_COMPAT_V1
task_version: '1.0'
status: READY
as_of: '2026-09-29'
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
  expected_base: 9727192d788642a17d62af772640c9a2d68b43c4
  expected_upstream: origin/main
  expected_upstream_oid: 9727192d788642a17d62af772640c9a2d68b43c4
  expected_branch: cursor/forge-legacy-parent-continuation-compat-v1
  dirty_mode: FORBIDDEN

objective: >-
  A completed NO_WORTHY parent with no aggregate FORGE_RUN_RECEIPT gets one
  hash-bound legacy parent binding, established now, so draft, plan, apply,
  continuation, close and ordinary readback share one contract without
  inventing a historical run receipt.

managed_write_set:
  - docs/tasks/FORGE_LEGACY_PARENT_CONTINUATION_COMPAT_V1.md
  - src/solana_alpha_lab/factory/hfic_repair_continuation.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - scripts/hypothesis_forge.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - tests/test_hfic_legacy_parent_continuation_compat_v1.py
  - docs/operator/FORGE_TEMPORAL_OPERABILITY_REPAIR_RUNBOOK_V1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_factory_fit_v1.json
  - docs/reports/forge_legacy_parent_continuation_compat/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - LIVE_REPAIR_CONTINUATION_APPLY
  - LIVE_RESEARCH_STORE_MUTATION
  - INVENTED_HISTORICAL_FORGE_RUN_RECEIPT
  - MARKET_HYPOTHESIS_FORGE
  - MERGE_IN_THIS_ATOM

context_requirements:
  catalog_asset_ids:
    - DOC-HYPOTHESIS-FORGE-OPERATOR-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - DOC-HYPOTHESIS-FORGE-OPERATOR-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_repair_continuation.py
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_legacy_parent_continuation_compat/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

## Decision

DECISION_DELTA: a missing aggregate receipt may be replaced only by an
ESTABLISHED_NOW legacy parent binding derived from durable session, terminal,
journal, slot, market, corpus and the admission's own representation.
UNCERTAINTY_REMOVED: caller run ids and the current ladder identity are not
historical proof; partial or damaged aggregates block fallback; close cannot
report DONE without a readable repair result receipt.
CAPABILITY_OR_EVIDENCE: disposable verticals cover NO_WORTHY and runner-up
PASS, budget 2→3 with replay delta 0, and the live store no-write plan.
STOP: no live apply, store mutation, invented historical receipt, or merge.
NEXT: after exact-head CI and merge-readiness, the owner phrase for this PR.
REPLAN_TRIGGER: a contradicting live aggregate appears, or the admission
representation cannot be recomputed from its own stored version.
SPEC_ROUTE: NONE
