---
task_id: NORMALIZED_TRAJECTORY_V1_EXECUTION_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-20'
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
  expected_base: 6bd0aa1dfe072d281bebd42cf4e7ddbf281b2c26
  expected_upstream: origin/main
  expected_upstream_oid: 6bd0aa1dfe072d281bebd42cf4e7ddbf281b2c26
  expected_branch: cursor/normalized-trajectory-v1-execution-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close the two proven NORMALIZED_TRAJECTORY_V1 execution-seam defects so a
  real completed NO_WORTHY CONTROL plus a verified C2 release can produce a
  hash-bound representation payload and challenger envelope without a fake
  critic packet, without future-only members failing the whole cohort, and
  without running the scientific probe.

managed_write_set:
  - docs/tasks/NORMALIZED_TRAJECTORY_V1_EXECUTION_CLOSURE_V1.md
  - docs/contracts/normalized_trajectory_v1_capability_contract.md
  - src/solana_alpha_lab/factory/hfic_representation_probe.py
  - src/solana_alpha_lab/factory/hfic_released_trajectory_projection.py
  - src/solana_alpha_lab/factory/normalized_trajectory_v1.py
  - tests/test_normalized_trajectory_v1.py
  - tests/test_normalized_trajectory_v1_execution_closure_v1.py
  - tests/test_hfic_released_trajectory_projection_v1.py
  - tests/test_hfic_representation_probe.py
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/normalized_trajectory_v1_execution_closure/a1_owner_readout_v1.md
  - docs/evidence/normalized_trajectory_v1_execution_closure/a1_c2_persist_false_handback_v1.json
  - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_completion_evidence_v1.json
  - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_independent_review_v1.json
  - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - SCIENTIFIC_PROBE_EXECUTION
  - PROMPT_A_CHALLENGER_RUN
  - INDEPENDENT_CRITIC_LAUNCH
  - FAKE_CRITIC_PACKET_SYNTHESIS
  - FROZEN_V1_GEOMETRY_CHANGE
  - SURVIVOR_FILTER_BY_FUTURE
  - FUTURE_AS_X
  - IMPUTATION_OR_MISSINGNESS_REPAIR
  - PROVIDER_CALL
  - A2_OR_LATER_SCOPE
  - THIRD_SEMANTIC_SCIENTIFIC_BLOCKER
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - CONTRACT-NORMALIZED-TRAJECTORY-V1-CAPABILITY-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - CONTRACT-NORMALIZED-TRAJECTORY-REPRESENTATION-PROBE-001
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_completion_evidence_v1.json
      - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_independent_review_v1.json
      - docs/evidence/normalized_trajectory_v1_execution_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# NORMALIZED_TRAJECTORY_V1_EXECUTION_CLOSURE_V1

ATOM_ID: `NORMALIZED_TRAJECTORY_V1_EXECUTION_CLOSURE_V1`

Program context: first atom of owner-path convergence
(`publish/import → one readback → /hypothesis-forge`). This atom does not
implement A2–A5.

## Task Outcome Brief

- **Owner decision:** a completed `NO_WORTHY` CONTROL plus a verified C2
  release must reach a hash-bound V1 representation payload and exact
  challenger envelope without reconstructing a critic packet and without
  future-only members failing the whole cohort.
- **Product outcome:** runtime-ready V1 seam
  (`NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED`) on real C2
  `persist=False`.
- **Named consumer:** later `/hypothesis-forge` representation ladder (A4);
  current consumer is the CONTROL→V1 adapter.
- **Cheapest falsifier:** completed NO_WORTHY receipt cannot build a
  baseline without a critic packet; a member with only points `> Y1800`
  raises a batch-killing error; envelope hash does not match persisted
  BASE context; frozen T/prefix/U-F-D-M/no-mint invariants drift.
- **Terminal:** targeted tests + real C2 read-only handback + reviews +
  exact-head CI + merge-readiness. Stop before owner phrase. Do not run
  Prompt A or Critic.
- **Non-goals:** A2 data-root/readback; A3 forge-input receipt; A4
  automatic ladder; A5 evidence-identity split; scientific probe
  execution; new data; provider; Git hack after the fact.

## Decision capsule

- `DECISION_DELTA`: V1 adapter accepts canonical exact BASE
  `FORGE_CONTEXT_PACKET` for completed `NO_WORTHY`, and release projection
  selects only schedule-bound prefix input through `T=Y1800`.
- `UNCERTAINTY_REMOVED`: whether the two proven seam defects block
  real-C2 envelope construction without a new scientific definition.
- `CAPABILITY_OR_EVIDENCE`: hash-bound payload + challenger envelope on
  real completed CONTROL + verified C2, with typed regressions.
- `STOP`: merge-readiness; scientific probe remains a later atom.
- `NEXT`: after guarded merge/readback, recommended A2
  `COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1`.
- `SPEC_ROUTE`: `DESIGN_SPEC` — capability-status change from dormant
  packet-only to runtime-ready seam; frozen preregistration bytes stay.
- `REPLAN_TRIGGER`: third independent semantic/scientific blocker on
  real-C2 acceptance; frozen V1 geometry/PIT change required; fake critic
  packet becomes necessary; A2+ scope leaks in.

## Proven defects

### D1 — completed `NO_WORTHY` baseline transport

Completed no-worthy session stores `critic_input_packet = null` and the
exact persisted BASE `forge_context_packet`. The adapter currently
requires a critic-shaped packet.

Target: `ControlBaseline` accepts canonical BASE context kind allowed for
`NO_WORTHY`. Hash-bind to actual persisted Forge context. Do not create a
fake selected candidate. Do not synthesize a critic packet.

### D2 — future-only rows before prefix projection

`resolve_release_projection_input()` forwards members whose only points
are `> Y1800` into the prefix lens and fails the whole batch.

Target: verified release → select only schedule-bound representation
input through T → preserve legitimate missingness → projector. A member
with no admissible prefix row must not fail the cohort. No survivor
filtering by future, no imputation, no future-as-X.

## Frozen scientific invariants

Do not change: `T = Y1800`; prefix geometry; PRICE / LIQUIDITY /
activity volume / TRADERS; first reliable availability; U/F/D/M;
missing→M; own-history normalization; max 8 motifs; no mint identity;
no PnL; no tuned thresholds; one registered V1.

## Vertical scenario

Read-only / `persist=False`:

```text
real completed baseline
→ verified real C2 release
→ representation
→ payload hash
→ challenger envelope
```

Required handback fields: `CONTROL_SESSION`, `CONTROL_CONTEXT_KIND`,
`CONTROL_CONTEXT_SHA256`, market/legacy evidence id, `C2_RELEASE_ID`,
`C2_SOURCE_SHA256`, `REPRESENTATION_PAYLOAD_SHA256`, eligible member
count, prefix slots, volume mode, motif tuple count, packet bytes,
probe identity sha256, `GIT_MUTATION_DURING_ACCEPTANCE=0`,
`PROVIDER_CALLS=0`, `REPRESENTATION_SCIENTIFIC_RUN=0`.

Do not commit current runtime outputs or absolute machine paths.

## Semantic propagation

If capability status moves from dormant packet-only to runtime-ready
seam, update the V1 capability contract, operator pack, Forge skill,
`SEM-HYPOTHESIS-FORGE` description/status if materially changed, Catalog
asset status, and generated views. Do not change root `AGENTS.md`.

## Owner gates

Exact merge phrase after exact-head CI and merge-readiness. No
provider/deploy/wallet. Post-merge: stop before actual scientific
representation probe.

## Rollback

Ordinary Git revert. Runtime evidence is unchanged.

## Deferred program addendum (not this atom)

Owner addendum to `SMIAL_FORGE_OWNER_PATH_CONVERGENCE_V2`. Do not implement
here. Carry into A4 comparative runs and primarily A5 identity/gold.

1. Forge run provenance records `model_profile` and `reasoning_profile` as
   capability/run provenance, not market evidence. A model or reasoning-level
   change must not mint a new `market_evidence_epoch`.
2. Comparative representation runs (BASE vs `NORMALIZED_TRAJECTORY_V1`/Vn)
   must share the same generator `model_profile`, `reasoning_profile`, prompt
   family, and search constraints.
3. Independent Critic may use the same or another strong model, but stays
   isolated: fresh context + only the frozen critic packet. Critic model
   identity is also run provenance.
4. After the OWNER_PATH_CONVERGENCE chain, do not spawn an inertial
   improvement atom. Next acceptance is one real normal-path
   `/hypothesis-forge`: visible cohorts / active evidence / visibility PASS,
   then BASE → active representation ladder.
5. A clean-run technical/visibility blocker is
   `OWNER_PATH_REGRESSION` / `OBSERVABILITY_BLOCKED`, not scientific
   `NO_WORTHY`, and is not a manual bypass.
6. `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` is a decision-bearing result. Do not
   auto-build V2. Separate scientific exhaustion review first; V2 only on a
   proved representation blind spot.
