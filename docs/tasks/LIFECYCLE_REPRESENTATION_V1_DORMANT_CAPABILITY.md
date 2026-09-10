---
task_id: LIFECYCLE_REPRESENTATION_V1_DORMANT_CAPABILITY
task_version: '1.0'
status: READY
as_of: '2026-09-10'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CODEX_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 18a1111e07b9edcf19c090fa61b119f80983c894
  expected_upstream: origin/main
  expected_upstream_oid: 18a1111e07b9edcf19c090fa61b119f80983c894
  expected_branch: codex/lifecycle-representation-v1-dormant-capability
  dirty_mode: ALLOW_REPORTED

objective: >-
  Implement the dormant MOVE A capability for NORMALIZED_TRAJECTORY_V1 as a
  deterministic synthetic/fixture-only vertical slice. Preserve the frozen
  preregistration, ordinary Hypothesis Forge, CURRENT_REPRESENTATION_CONTROL_V1,
  collector/ObservationSchedule/seal/verify/import behavior, provider routes,
  deployment and current cohort science.

managed_write_set:
  - docs/tasks/LIFECYCLE_REPRESENTATION_V1_DORMANT_CAPABILITY.md
  - docs/contracts/normalized_trajectory_v1_capability_contract.md
  - src/solana_alpha_lab/factory/normalized_trajectory_v1.py
  - src/solana_alpha_lab/factory/hfic_representation_probe.py
  - scripts/hypothesis_forge_representation.py
  - tests/test_normalized_trajectory_v1.py
  - tests/test_hfic_representation_probe.py
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - COLLECTOR_OR_OBSERVATION_SCHEDULE_CHANGE
  - SEAL_VERIFY_OR_IMPORT_CHANGE
  - CURRENT_REPRESENTATION_CONTROL_CHANGE
  - ORDINARY_HYPOTHESIS_FORGE_CHANGE
  - FROZEN_PREREGISTRATION_CHANGE
  - CURRENT_COHORT_SCIENTIFIC_CONTENT_ACCESSED
  - PROVIDER_OR_DEPLOYMENT_REQUIRED
  - ORDINARY_SEARCH_OR_PACKET_BUDGET_CHANGE
  - GENERIC_REPRESENTATION_FRAMEWORK
  - AUTOMATIC_PROBE_EXECUTION
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids:
    - CONTRACT-NORMALIZED-TRAJECTORY-REPRESENTATION-PROBE-001
    - CONFIG-HYPOTHESIS-FORGE-INDEPENDENT-CRITIC-001
    - MODULE-FACTORY-V1-HFIC-SESSION-001
    - MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - CONTRACT-NORMALIZED-TRAJECTORY-REPRESENTATION-PROBE-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - CONFIG-HYPOTHESIS-FORGE-INDEPENDENT-CRITIC-001
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - docs/tasks/NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1.md
      - docs/tasks/HFIC_FRESH_CONTROL_DECISION_INTEGRITY_CLOSURE_V1.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# LIFECYCLE_REPRESENTATION_V1_DORMANT_CAPABILITY

## Task outcome brief

- `DECISION_DELTA`: the first frozen lifecycle representation exists in Git as
  `IMPLEMENTED_DORMANT_NOT_EXECUTED`, with a deterministic projection, a
  baseline-preserving challenger adapter, and a read-only status surface.
- `UNCERTAINTY_REMOVED`: synthetic evidence proves PIT cutoff, missingness,
  volume semantics, anonymous histogram output, exact CONTROL cloning,
  memory isolation and bounded one-run identity without running a cohort or
  changing the current Forge path.
- `CAPABILITY_OR_EVIDENCE`: current implementation contract, pure projection,
  HFIC adapter, existing lifecycle fixture integration, tests and Catalog
  discoverability.
- `NAMED_CONSUMER`: future explicit representation probe after a fresh CONTROL;
  ordinary `/hypothesis-forge` remains the unchanged consumer for current
  behavior.
- `CHEAPEST_FALSIFIER`: any synthetic test observes future-data influence,
  missingness repair, taker-volume inference, mint identity leakage, baseline
  drift, CONTROL memory leakage, ordinary-budget mutation, packet overflow
  repair, or a non-read-only/default Forge path change.
- `SPEC_ROUTE`: `DESIGN_SPEC` — the current capability contract defines a new
  public truth-owner boundary and multi-state read-only workflow; it does not
  replace the frozen scientific preregistration.
- `STOP`: exact-head CI and merge-readiness; stop before the owner phrase.
- `NEXT`: after the exact owner phrase, one guarded merge and post-merge
  readback; scientific CONTROL/challenger execution is a separate atom.

## Non-goals and replan triggers

This atom does not run CONTROL, the challenger, `/hypothesis-forge`, a cohort,
collector, timer, seal/import, provider, deployment, experiment, holdout,
current-cohort science, alpha/PASS interpretation, generator/ranker, feature
store, embeddings, clustering or a generic representation framework.

`REPLAN_REQUIRED` is terminal if any of those boundaries become necessary, if
the frozen preregistration bytes or semantics must change, or if ordinary Forge
budget/context/identity or `CURRENT_REPRESENTATION_CONTROL_V1` must be changed.

## Scientific terminal

The only implementation terminal is:

```text
IMPLEMENTED_DORMANT_NOT_EXECUTED
```

It is not `PROBE_EXECUTED`, `PASS`, `ALPHA`, scientific `DONE`, or runtime
activation. The implementation can be rolled back without touching the
collector, LIVE CORPUS, Forge, Critic, experiment or trading planes.
