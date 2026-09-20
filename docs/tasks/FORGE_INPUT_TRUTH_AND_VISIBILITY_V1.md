---
task_id: FORGE_INPUT_TRUTH_AND_VISIBILITY_V1
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
  expected_base: 34fb6be93c68853638e5816626a78e6c020d2392
  expected_upstream: origin/main
  expected_upstream_oid: 34fb6be93c68853638e5816626a78e6c020d2392
  expected_branch: cursor/forge-input-truth-and-visibility-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  One Forge input/visibility builder, actual preflight and compatibility
  adapter without competing truth logic; historical calibration validates
  against its own frozen inputs; real current C1/C2 via a proven no-write path.

managed_write_set:
  - docs/tasks/FORGE_INPUT_TRUTH_AND_VISIBILITY_V1.md
  - src/solana_alpha_lab/factory/forge_input_receipt.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/hfic_selection_robustness_gate.py
  - scripts/hypothesis_forge.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - tests/test_forge_input_truth_and_visibility_v1.py
  - tests/test_hfic_selection_robustness_gate_v1.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - tests/test_live_cohort_discovery_release_series.py
  - tests/test_hfic_preflight.py
  - catalog/schemas/forge_input_receipt_v1.schema.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/reports/forge_input_truth_and_visibility/a1_owner_readout_v1.md
  - docs/evidence/forge_input_truth_and_visibility/a1_c1_c2_forge_input_v1.json
  - docs/evidence/forge_input_truth_and_visibility/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_input_truth_and_visibility/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_input_truth_and_visibility/a1_delivery_factory_fit_v1.json
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
  - PROMPT_A_B_C
  - INDEPENDENT_CRITIC
  - STATISTICAL_DIAGNOSTIC_RUN
  - V1_SCIENTIFIC_PROBE
  - COMMISSIONING
  - HISTORICAL_RECEIPT_REWRITE
  - NEW_TRIAL
  - A4_OR_A5_SCOPE
  - PROVIDER_CALL
  - VPS_DEPLOY
  - ABSOLUTE_MACHINE_PATHS_IN_DURABLE_RECEIPT
  - RECURSIVE_PREFLIGHT_BUILDER
  - MERGE_WITHOUT_OWNER_PHRASE

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - MODULE-LIVE-COHORT-TO-FORGE-001
      - SCRIPT-HYPOTHESIS-FORGE-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_preflight.py
      - src/solana_alpha_lab/factory/live_cohort_to_forge.py
    DELIVERY_EVIDENCE:
      - docs/evidence/cohort_data_root_and_import_readback/a1_c1_c2_readback_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_INPUT_TRUTH_AND_VISIBILITY_V1

ATOM_ID: `FORGE_INPUT_TRUTH_AND_VISIBILITY_V1`

Program: third atom of `SMIAL_FORGE_OWNER_PATH_CONVERGENCE_V2`. Depends on
landed A2 `COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1`. Do not implement A4–A5.

## Task Outcome Brief

- **Owner decision:** before hypothesis search the system proves which
  cohorts it can see, their roles, that the packet did not lose material
  current-corpus information, and whether scientific search may issue a
  verdict.
- **Product outcome:** one `build_forge_input_receipt` builder; actual HFIC
  preflight and `forge-control-ready` are projections of that builder;
  historical C1 calibration stays a scoped caveat against its own frozen
  inputs; ordinary packet selection protects LIVE CORPUS.
- **Named consumer:** `/hypothesis-forge` owner FORGE INPUT block; later A4
  representation ladder.
- **Cheapest falsifier:** compatibility READY disagrees with actual slash
  input checks; historical C1 receipt becomes `integrity_invalid` solely
  because the current cumulative manifest advanced; no-write C1/C2 path
  mutates the plane.
- **Terminal:** targeted tests + real persist=False C1/C2 acceptance +
  reviews + exact-head CI + merge-readiness. Stop before owner phrase.
- **Non-goals:** `/hypothesis-forge` Prompt A/B/C, Critic, statistical
  diagnostic, V1 scientific probe, commissioning, historical receipt
  rewrite, new trial, A4 ladder, A5 identity/gold, VPS/provider.

## Decision capsule

- `DECISION_DELTA`: one scientific input/visibility receipt; adapters share
  it; historical gate identity omits current `dataset_manifest_id` from
  frozen-input comparison; LIVE CORPUS slot is protected in ordinary packet
  selection too.
- `UNCERTAINTY_REMOVED`: whether Forge CONTROL and actual preflight can
  disagree on common input/visibility checks; whether a C2 import silently
  kills C1 historical calibration.
- `CAPABILITY_OR_EVIDENCE`: `smial.forge-input-receipt` 1.0 plus no-write
  C1/C2 counters matching the A2 lineage (1/1, corpus_version=2) when that
  plane is present.
- `STOP`: merge-readiness; no slash execution; no merge without the
  machine-rendered owner phrase.
- `NEXT`: after merge/readback, recommended A4 `FORGE_REPRESENTATION_LADDER_V1`.
- `SPEC_ROUTE`: `DESIGN_SPEC`.
- `REPLAN_TRIGGER`: builder must call `run_preflight`; a second competing
  readiness engine appears; real C1/C2 no-write path cannot run; A4/A5 leak.

## Canonical builder

Focused module `src/solana_alpha_lab/factory/forge_input_receipt.py`.
Does not call `run_preflight` or persist Forge context / session / store
records. Schema `smial.forge-input-receipt` / `1.0`.

Labeled scopes: `ACTIVE_EVIDENCE_SET`, `HISTORICAL_CALIBRATION`,
`REPRESENTATION_INPUT_SCOPE`, `EXPERIMENT_DATA_SCOPE` (search not started).

Owner classes: `FORGE_INPUT_READY` | `INPUT_NOT_READY` |
`OBSERVABILITY_BLOCKED`. No `NO_WORTHY`. `forge_runnable` is input fitness,
not synthesis.

## No competing truth

`forge_control_ready` calls the builder and prints a CONTROL subset plus
operational extras (runtime, yield floor, session enterability, Fast Lane
proof). Actual `run_preflight` attaches the same builder receipt. Common
input/visibility checks cannot disagree.

## Historical calibration

Existing selection receipt remains byte-immutable. Validate against own
frozen inputs (`corpus_id`, `cohort_id`, `release_id`, `census_sha256`,
`observations_sha256`, `spec_file_sha256`). Current corpus head /
`dataset_manifest_id` change alone is not `integrity_invalid`. Tampered
hash or wrong cohort/release/census/observations stays blocked.

## Vertical gold

- G-A3-1 wrong worktree still sees the same C1+C2 after A2 root rules.
- G-A3-2 historical stale manifest remains caveat; does not block current C2.
- G-A3-3 current corpus absent → `INPUT_NOT_READY`, no session from builder/CLI.
- G-A3-4 packet material loss of live corpus → `OBSERVABILITY_BLOCKED`.
- G-A3-5 good current C2 → `forge_runnable=true` with explicit visible cohorts.

## Real acceptance

Canonical data plane, persist=False / `forge-input` no-write. Inventory
digest unchanged. Visible C1 count 1, C2 count 1, corpus_version 2 when
that lineage is already imported. Do not launch slash, Prompt, Critic,
diagnostic, probe, or commissioning.

## Semantic propagation

Primary routes: `SEM-HYPOTHESIS-FORGE`, `SEM-LIVE-EVIDENCE-TO-FORGE`,
`SEM-PRIOR-WORK`. Catalog asset `MODULE-FORGE-INPUT-RECEIPT-001` plus schema
and tests. Skill and Cursor command show `FORGE INPUT` before synthesis.

## Rollback

Ordinary Git revert. Do not rewrite historical gate bytes or destroy
imported runtime data.
