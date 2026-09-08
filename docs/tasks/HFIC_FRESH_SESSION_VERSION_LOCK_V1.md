---
task_id: HFIC_FRESH_SESSION_VERSION_LOCK_V1
task_version: '1.0'
status: READY
as_of: '2026-09-08'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 9fbe07cde315e49e8b2eec990acff980718869e4
  expected_upstream: origin/main
  expected_upstream_oid: 9fbe07cde315e49e8b2eec990acff980718869e4
  expected_branch: cursor/hfic-fresh-session-version-lock-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Fail-closed fresh HFIC session protocol lock: a current HFIC-V1.2
  START_NEW_SESSION preflight must not accept a newly generated packet_version=1.1
  / HFIC-V1.1 draft. Preserve historical V1.1 readability. Do not coerce or
  auto-upgrade. Do not change scientific search, prior recall, runner-up,
  classifier, or experiment behavior.

managed_write_set:
  - docs/tasks/HFIC_FRESH_SESSION_VERSION_LOCK_V1.md
  - src/solana_alpha_lab/factory/hfic_session.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_fresh_session_version_lock_v1.py
  - tests/test_hfic_operational_closure_v1.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_forge_context_and_no_worthy.py
  - tests/test_hfic_epistemic_memory_semantics.py
  - tests/test_hfic_legacy_science_rebase.py
  - tests/test_hfic_discovery_prospects_and_next_action.py
  - tests/test_hfic_provenance_clock.py
  - tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json
  - docs/reports/hfic_fresh_session_version_lock/a1_owner_readout_v1.md
  - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - HISTORICAL_V11_RDP_REWRITE
  - HISTORICAL_V11_READABILITY_LOST
  - CRITIC_V11_IDENTITY_REDESIGN
  - PRIOR_RECALL_OR_RUNNER_UP_SCOPE
  - PROVIDER_API_RPC_WSS_REQUIRED
  - EXPERIMENT_OR_HOLDOUT
  - ACTIVE_RDP_WRITE
  - REAL_HYPOTHESIS_FORGE_SLASH

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
      - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_fresh_session_version_lock/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FRESH_SESSION_VERSION_LOCK_V1

SPEC_ROUTE=NONE. Exact owner atom: fresh-session protocol identity only.

## DECISION_DELTA

Current `START_NEW_SESSION` / `HFIC-V1.2` preflight no longer accepts a newly
generated `packet_version=1.1` / `HFIC-V1.1` draft. Denial is typed
`FRESH_SESSION_DRAFT_VERSION_MISMATCH` before session/candidate persistence.
Historical V1.1 freeze-without-current-preflight remains readable. No auto-upgrade.

## UNCERTAINTY_REMOVED

Whether a SKILL/operator V1.1 draft can silently occupy the V1.2 AUTO search slot.

## CAPABILITY_OR_EVIDENCE

Machine guard on freeze + canonical START_NEW_SESSION instructions emit V1.2 + T1–T6.

## STOP

Exact-head CI. Merge-readiness. Owner phrase. No active RDP. No real slash.

## NEXT

Owner merge phrase. Residual F2 prior recall and F3 runner-up remain out of scope.
