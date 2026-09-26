---
task_id: HFIC_FAST_LANE_DEFINITION_HASH_BIND_V1
task_version: '1.0'
status: READY
as_of: '2026-09-26'
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
  expected_base: b6ab5f699ad2b2bee3286171ad2728e1bcee1638
  expected_upstream: origin/main
  expected_upstream_oid: b6ab5f699ad2b2bee3286171ad2728e1bcee1638
  expected_branch: cursor/hfic-fast-lane-definition-hash-bind-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  run_live_classifier must not return FAST_LANE_READY for a bare ExperimentSpec.
  The caller must supply hypothesis_definition_sha256 equal to the frozen
  selected_definition_sha256. Otherwise the typed result is
  HYPOTHESIS_DEFINITION_UNBOUND. The receipt records the spec hypothesis_version.
  Feature-id mismatch stays EXPERIMENT_SPEC_GROUNDING_MISMATCH.

managed_write_set:
  - docs/tasks/HFIC_FAST_LANE_DEFINITION_HASH_BIND_V1.md
  - src/solana_alpha_lab/factory/hfic_session.py
  - tests/test_hfic_fast_lane_definition_hash_bind_v1.py
  - tests/test_hfic_fresh_control_decision_integrity_closure_v1.py
  - tests/test_hfic_packet14_availability_fast_lane_guard_v1.py
  - tests/test_hfic_classification_outcome_integrity_v1.py
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/reports/hfic_fast_lane_definition_hash_bind/a1_owner_readout_v1.md
  - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_factory_fit_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/FACTORY_SEMANTIC_MAP.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - HYPOTHESIS_VERSION_MUST_EQUAL_HFIC_CAND
  - EXPERIMENT_SPEC_PRODUCER_REQUIRED
  - HANDOFF_MANIFEST_1_0_TEXT_CHANGE
  - LANE_CLASSIFIER_TABLE_CHANGE
  - PACKET_SCHEMA_CHANGE
  - EXPERIMENT_SPEC_SCHEMA_CHANGE
  - PROVIDER_OR_RDP_WRITE
  - ACTIVATION_OR_STRATEGY_FILE_WRITE

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
      - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_fast_lane_definition_hash_bind/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FAST_LANE_DEFINITION_HASH_BIND_V1

SPEC_ROUTE=PRD_LITE. FACTORY_FIT=FULL_REVIEW. MODEL_EFFORT=`LUNA_MAX`.
Route `DIRECT_CURSOR_DELIVERY`. Base `b6ab5f699ad2b2bee3286171ad2728e1bcee1638`.

Confirmed defect: `run_live_classifier` copies `frozen.selected_definition_sha256`
onto a bare ExperimentSpec and can return `FAST_LANE_READY` when only feature
ids match. `hypothesis_version` stays a `HYP-*` spec field. It is not rewritten
to an `HFIC-CAND-*` id.

Packet 1.4 fixtures that called classify with a bare spec must pass the real
frozen `selected_definition_sha256`. Their PIT / grounding meaning stays.

## Task Outcome Brief

- **Owner decision:** a bare spec is not Fast-Lane-ready.
- **Named consumer:** HFIC classify after freeze, before any experiment.
- **Cheapest falsifier:** cases A/B/C in
  `tests/test_hfic_fast_lane_definition_hash_bind_v1.py`.
- **Non-goals:** ExperimentSpec producer, equating `HYP-*` with `HFIC-CAND-*`,
  handoff manifest 1.0/1.1 text, `lane_classifier.py`, strategy yaml, activation.
- **Evidence budget:** synthetic fixtures only. No provider, RDP write, or wallet.

## Decision capsule

- `DECISION_DELTA`: голый spec больше не наследует definition hash замороженного кандидата.
- `UNCERTAINTY_REMOVED`: FAST_LANE_READY больше не ставится только из-за совпадения feature ids.
- `CAPABILITY_OR_EVIDENCE`: typed `HYPOTHESIS_DEFINITION_UNBOUND` и `receipt.hypothesis_version`.
- `STOP`: зелёный exact-head CI и `ready_for_owner_phrase` true. Merge не входит в атом.
- `NEXT`: владелец произносит `owner_phrase` отдельным сообщением.
- `REPLAN_TRIGGER`: the fix needs a new ExperimentSpec producer, a schema change,
  a lane-classifier table change, or a manifest 1.0/1.1 edit.

## Behavior

- Do not fill `frozen.selected_definition_sha256` when the caller did not pass it.
- Missing hash, or a hash that is not the frozen `selected_definition_sha256`,
  is `HYPOTHESIS_DEFINITION_UNBOUND`, not `FAST_LANE_READY`.
- A matching hash still reaches the existing PIT gate.
- Feature-id mismatch stays `EXPERIMENT_SPEC_GROUNDING_MISMATCH`.
- The receipt records `hypothesis_version` from the validated spec.
- Setting `hypothesis_version` equal to an `HFIC-CAND-*` id is not the fix.
  The spec schema allows only `^HYP-[A-Z0-9]+(?:-[A-Z0-9]+)+$`.
