---
task_id: HFIC_OPERATIONAL_PACKET_GUARD_SIMPLIFICATION_V1
task_version: '1.0'
status: READY
as_of: '2026-09-19'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: "1e4b8e2af3d0309d64947eed44b2642ec42a68f5"
  expected_upstream: origin/main
  expected_upstream_oid: "1e4b8e2af3d0309d64947eed44b2642ec42a68f5"
  expected_branch: cursor/hfic-operational-packet-guard-simplification-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Replace the frozen 16384 CONTROL byte identity and 20480 ordinary clamp
  with one operational envelope (65536 hard cap, 20480 growth warning)
  shared by ordinary Forge, CURRENT_REPRESENTATION_CONTROL, and the
  representation challenger. Prove one imported C2 persist=False CONTROL
  construct is operationally admissible under 65536 with no DROP_SEMANTIC
  or DROP_FEATURE_GROUNDING on that construct; dataset-selection truncated
  remains the CONTROL MAX_DATASETS cap. Not class proof. Do not run
  /hypothesis-forge.

managed_write_set:
  - docs/tasks/HFIC_OPERATIONAL_PACKET_GUARD_SIMPLIFICATION_V1.md
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_representation_probe.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_operational_packet_guard_simplification_v1.py
  - tests/test_hfic_forge_prior_context_capacity_repair_v1.py
  - tests/test_hfic_representation_probe.py
  - tests/test_hfic_vision_integrity_v1.py
  - tests/test_factory_semantic_operability.py
  - tests/test_hfic_reopened_prior_search_routing_v1.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - docs/contracts/normalized_trajectory_v1_capability_contract.md
  - docs/contracts/normalized_trajectory_representation_probe_v1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - docs/reports/hfic_operational_packet_guard_simplification/a1_owner_readout_v1.md
  - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_factory_fit_v1.json
  - docs/evidence/hfic_operational_packet_guard_simplification/a1_c2_packet_acceptance_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - HYPOTHESIS_FORGE_SLASH
  - RESEARCHSTORE_WRITE_ON_ACCEPTANCE
  - MEMORY_POLICY_MUTATION
  - SEARCH_BUDGET_CONSTANT_CHANGE
  - RANKED_PRIOR_DROP_TO_FIT
  - SILENT_SCIENTIFIC_TRUNCATION
  - ADAPTIVE_BUDGET_MANAGER
  - PROVIDER_OR_MODEL_CONTEXT_TABLE
  - ESTIMAND_PIT_OR_MISSINGNESS_CHANGE
  - C2_CORPUS_OR_LINEAGE_MUTATION
  - EPOCH_COUPLING_ARCHITECTURAL_REPAIR

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
      - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_operational_packet_guard_simplification/a1_delivery_factory_fit_v1.json
      - docs/evidence/hfic_operational_packet_guard_simplification/a1_c2_packet_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_OPERATIONAL_PACKET_GUARD_SIMPLIFICATION_V1

SEMANTIC_PREMISE_HIGH_RISK: true

SPEC_ROUTE=NONE. Exact owner atom: replace the frozen 16384 CONTROL↔challenger
byte identity and the 20480 ordinary throughput clamp with one operational
hard cap 65536 and one growth warning 20480. Those numbers were not
estimand/PIT/missingness science; they were byte-identity comparability /
throughput clamps. This atom amends that freeze; it does not claim the old
identity never existed.

SCIENCE_CRITIC is outside `required_review_roles` schema enum and is launched
isolated; answers are bound in the owner readout and architecture findings.

## Task Outcome Brief

- **Owner decision:** `FIXED_16KB_NOT_SCIENTIFIC`. 16384/20480 were frozen
  byte identities, not estimand/PIT/missingness. Replace them with one
  operational envelope. Comparability is no longer equal unused 16KiB
  headroom.
- **Product outcome:** ordinary / CONTROL / challenger share one hard cap
  65536 and one warning threshold 20480. One imported C2 persist=False
  CONTROL construct is `CONTROL_PACKET_OPERATIONALLY_ADMISSIBLE` (18560
  bytes, no `DROP_SEMANTIC` / `DROP_FEATURE_GROUNDING` on that construct).
  That is not a class proof for every 17–20KB packet and not a claim of
  zero information loss: CONTROL dataset-selection cap may still set
  `truncated=true`.
- **Named consumer:** next owner `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`
  after this atom merges. This atom does not run that slash.
- **Cheapest falsifier:** unit suites for shared cap / warning-without-drop /
  fail-closed over 65536, plus read-only real C2 persist=False packet and
  `forge-control-ready`.
- **Terminal:** `DONE_FOR_MERGE` after reviews, exact-head CI and merge-readiness.
  Stop before owner merge phrase.
- **Non-goals:** `/hypothesis-forge`; ResearchStore writes; epoch-coupling
  architecture repair; adaptive budget manager; model/vendor context tables;
  changing selection cardinalities, memory policy, search budget, or trajectory
  science.
- **Evidence budget:** disposable fixtures + one read-only local data_plane
  acceptance. No ResearchStore writes on acceptance.
- **SPEC_ROUTE=NONE**

## Decision capsule

- `DECISION_DELTA`: one `FORGE_OPERATIONAL_PACKET_MAX_BYTES=65536` authority;
  `FORGE_PACKET_GROWTH_WARNING_BYTES=20480` telemetry only; CONTROL↔challenger
  comparability is same admissible-information rules plus exact CONTROL hash,
  not equal unused 16KiB headroom.
- `UNCERTAINTY_REMOVED`: this imported C2 CONTROL construct (18560 bytes) is
  operationally legal under 65536. The atom does not prove every 17–20KB
  packet, and it amends rather than denies the old 16384 CONTROL byte identity.
- `CAPABILITY_OR_EVIDENCE`: CONTROL packet operationally admissible on imported
  C2; `forge-control-ready` remains `FORGE_CONTROL_READY`.
- `STOP`: merge-readiness; owner phrase gate.
- `NEXT`: real C2 `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. Replaces mode-split packet byte identities
with one operational envelope.
`PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.
