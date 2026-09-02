---
task_id: FORGE_DISCOVERY_TRIGGER_B_MEASUREMENT_V1
task_version: '1.0'
status: READY
as_of: '2026-09-03'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: e3ccf6561c3d91720c0234c4255d3385b3f9f8d7
  expected_upstream: origin/main
  expected_upstream_oid: e3ccf6561c3d91720c0234c4255d3385b3f9f8d7
  expected_branch: cursor/forge-discovery-trigger-b-measurement-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Evidence-only measurement of ARCH-INTENT-006 Trigger B (materially large
  currently credible hypothesis-family choice space) from Git/Catalog truth.
  Do not implement generator, Opportunity Projection, ranker, QD, VOI, A1,
  or weaken FORGE_DISCOVERY_RANKER_ENTRY_GATE_V1 terminal.

managed_write_set:
  - docs/tasks/FORGE_DISCOVERY_TRIGGER_B_MEASUREMENT_V1.md
  - docs/evidence/forge_discovery_trigger_b_measurement/a1_trigger_b_measurement_v1.json
  - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_factory_fit_v1.json
  - docs/reports/forge_discovery_trigger_b_measurement/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - GENERATOR_OR_RANKER_OR_OPPORTUNITY_PROJECTION_IMPLEMENTATION
  - A0_TERMINAL_MUTATION
  - A1_START
  - PROVIDER_API_RPC_WSS_REQUIRED
  - EXPERIMENT_OR_HOLDOUT
  - NEW_DB_OR_TRUTH_STORE
  - PURCHASE_OR_DEPLOYMENT

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
      - docs/architecture/intents/ARCH-INTENT-006-hypothesis-discovery-and-opportunity-surface.md
      - docs/architecture/prospects/hfic_scientific_discovery_prospects_v1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_discovery_trigger_b_measurement/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_DISCOVERY_TRIGGER_B_MEASUREMENT_V1

## Entry / outcome

- `DECISION_DELTA`: whether Trigger B (material currently-credible family choice space) is independently supportable now
- `UNCERTAINTY_REMOVED`: measured inventory vs advisory prospect count conflation
- `CAPABILITY_OR_EVIDENCE`: hash-bound Trigger B measurement receipt
- `STOP`: terminal + exact-head CI + merge gate; if PROVEN → report `REOPEN_FORGE_DISCOVERY_RANKER_ENTRY_GATE` only
- `NEXT`: no A1; do not mutate A0

## Pre-registered materiality rule (before counts)

Trigger B is `DISCOVERY_TRIGGER_B_MATERIAL_CANDIDATE_SPACE_PROVEN` only if **all** of:

1. **Cardinality:** `currently_grounded_distinct_families >= 3`, where only class `CURRENTLY_GROUNDED` counts. Class `GROUNDED_WITH_FORWARD_ONLY_EVIDENCE` does **not** satisfy this gate alone (forward-only is not strategy-available). Classes `MISSING_CAPABILITY`, `BLOCKED_BY_RESEARCH_TRUTH`, `CLOSED_OR_DUPLICATIVE`, `ADVISORY_ONLY_NOT_YET_GROUNDED` never count.
2. **Structural diversity:** the counting families differ on ≥2 Forge axes each pair (actor/counterparty, mechanism, state transition, primary observable/X, horizon, payoff asymmetry) and collectively cover ≥3 distinct mechanism classes.
3. **No single dominant next family:** prior-work does not leave exactly one replicated open market mechanism as the unique owner NEXT.
4. **Owner comparison effort:** honest selection among the counting families requires comparing ≥3 competing grounded choices without an automatic ranking from the closed-family ledger.

Otherwise emit `DISCOVERY_TRIGGER_B_NOT_YET_PROVEN` (weak/empty space) or `DISCOVERY_TRIGGER_B_UNRESOLVED` only for genuine truth conflict.

Do not treat 23 HFIC prospects, 19 features, or 28 observation fields as family CHOICES.

## Non-claims

- Does not change A0 terminal `DISCOVERY_GENERATOR_TRIGGER_NOT_YET_PROVEN`
- Does not start A1 / generator / ranker / Opportunity Projection / QD / VOI
- Does not grant provider, experiment, holdout, or deployment authority
- Capability presence ≠ authority to invoke
- Never coerce `X_TIME` → `PIT_READY`
