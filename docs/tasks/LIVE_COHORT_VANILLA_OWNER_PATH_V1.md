---
task_id: LIVE_COHORT_VANILLA_OWNER_PATH_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-26"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4213755922fec0142a69ba1b0df52268c026240b
  expected_upstream: origin/main
  expected_upstream_oid: 4213755922fec0142a69ba1b0df52268c026240b
  expected_branch: cursor/live-cohort-vanilla-owner-path-v1
  dirty_mode: FORBIDDEN
objective: >-
  Bind the already implemented vanilla owner path from the next mature
  unimported cohort to FORGE_CONTROL_READY. Do not add cohort machinery.
managed_write_set:
  - docs/tasks/LIVE_COHORT_VANILLA_OWNER_PATH_V1.md
  - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_completion_evidence_v1.json
  - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_independent_review_v1.json
  - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_factory_fit_v1.json
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - scripts/discovery_evidence_release.py
  - src/solana_alpha_lab/factory/bounded_cohort_materialization.py
  - src/solana_alpha_lab/factory/forge_input_receipt.py
  - src/solana_alpha_lab/factory/hfic_evidence_identity.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/live_cohort_source_bundle.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/live_cohort_vanilla_path.py
  - src/solana_alpha_lab/factory/live_corpus_manifest_publish.py
  - src/solana_alpha_lab/factory/research_store.py
  - tests/test_bounded_cohort_materialization_v1.py
  - tests/test_forge_evidence_identity_and_owner_gold_v1.py
  - tests/test_forge_input_truth_and_visibility_v1.py
  - tests/test_forge_representation_ladder_v1.py
  - tests/test_live_cohort_vanilla_owner_path_v1.py
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
  - NEW_COHORT_MACHINERY_REQUIRED
  - DEPLOYMENT_REQUIRED
  - PROVIDER_OR_CREDENTIAL_REQUIRED
  - FINANCIAL_ACTION_REQUIRED
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
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
      - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_completion_evidence_v1.json
      - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_independent_review_v1.json
      - docs/evidence/live_cohort_vanilla_owner_path/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_COHORT_VANILLA_OWNER_PATH_V1

## Entry / Outcome

- `DECISION_DELTA`: the ordinary owner command is the already built path from the next mature unimported cohort to `FORGE_CONTROL_READY`. This atom only binds that delivery.
- `UNCERTAINTY_REMOVED`: whether that path is the recorded owner outcome of PR #341, with local heavy materialization and a current-corpus Forge view.
- `CAPABILITY_OR_EVIDENCE`: one command, rollover-safe resolution, frozen closure, mirror fail-closed, source-to-receipt check, and C200-bounded materialization, import, and Forge readiness.
- `STOP`: exact-head CI, then merge-readiness. No deploy and no Forge run.
- `NEXT`: none from this PR. Further cohort machinery needs a new contract and new material evidence.
- `REPLAN_TRIGGER`: a binding gap that requires new cohort machinery, a provider, credentials, or a financial action.

## Non-goals

No new daemon, database, service, or transport framework. No deployment. No provider, credential, or financial authority. No second materializer. No automatic `/hypothesis-forge`.
