---
task_id: FORGE_GROUNDED_DISCOVERY_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
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
  expected_base: 30ee1f561224f91e0557650dc7fecfae5e1603f6
  expected_upstream: origin/main
  expected_upstream_oid: 30ee1f561224f91e0557650dc7fecfae5e1603f6
  expected_branch: cursor/forge-grounded-discovery-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Restore ordinary /hypothesis-forge so a fresh focus is not silently rewritten
  to CONTROL, and so that route computes BASE_X price/liquidity evidence from
  production-shaped rows, records look provenance, and carries those refs
  through freeze. Predictive sketches do not require an actor story. Do not
  run market Prompt A, market Critic, or an experiment. Do not free the
  occupied AUTO slot. CONTROL remains explicit. V1 triggers stay unchanged.

managed_write_set:
  - docs/tasks/FORGE_GROUNDED_DISCOVERY_REPAIR_V1.md
  - docs/reports/forge_grounded_discovery_repair/a1_owner_readout_v1.md
  - docs/evidence/forge_grounded_discovery_repair/a1_state_only_coverage_v1.json
  - docs/evidence/forge_grounded_discovery_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_grounded_discovery_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_grounded_discovery_repair/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - scripts/hypothesis_forge.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - catalog/schemas/hypothesis_forge_draft_v1_2.schema.json
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/schemas/forge_run_receipt_v1.schema.json
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_grounded_discovery_v1.py
  - tests/test_forge_representation_ladder_v1.py
  - tests/test_hfic_operational_closure_v1.py

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - MARKET_PROMPT_A
  - MARKET_CRITIC
  - EXPERIMENT_EXECUTION
  - PROVIDER_API_RPC_WSS
  - HOLDOUT_READ
  - LIVE_RDP_WRITE
  - AUTO_SLOT_RELEASE
  - NEW_DEPENDENCY
  - MERGE_WITHOUT_OWNER_PHRASE

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
      - docs/evidence/forge_grounded_discovery_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_grounded_discovery_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_grounded_discovery_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_GROUNDED_DISCOVERY_REPAIR_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=PRD_LITE

Owner EXECUTE contract. Bound base is `origin/main`
`30ee1f561224f91e0557650dc7fecfae5e1603f6`. Route `DIRECT_CURSOR_DELIVERY`.
MODEL_EFFORT: `SOL_XHIGH`.

Primary route `SEM-HYPOTHESIS-FORGE` is CAPABILITY. It grants no execution
authority. `FORGE_DISCOVERY_SURFACE_AUDIT_V1` is a hint, not this receipt.

## Task Outcome Brief

- **Owner decision:** ordinary Forge must be able to investigate allowed
  numeric discovery on C1–C3 without being rewritten into CONTROL.
- **Named consumer:** a later authorized ordinary `/hypothesis-forge` with
  focus `COHORT_STRATIFIED_LIFECYCLE_PATHS`.
- **Cheapest falsifier:** one public `discovery-execute` path on synthetic
  census and observation rows, plus prior-scope regression cases.
- **Non-goals:** market Prompt A, market Critic, experiment, provider calls,
  holdout reads, live RDP writes, freeing AUTO, changing V1 trigger terminals,
  spending a live focus slot.
- **Evidence budget:** synthetic rows and a temporary ResearchStore.
  `SCIENTIFIC_WRITES=0` on the live store. `LIVE_FOCUS_SLOT_SPENT=0`.

## Decision capsule

- **DECISION_DELTA:** ordinary Forge computes BASE_X price/liquidity from
  production-shaped rows, records the look, and freeze rejects unbound or
  tampered evidence. CONTROL stays explicit. A question-id rename does not
  lift a valid close. A richer ordinary surface is not closed by a CONTROL
  negative. Predictive sketches are 0–6 and do not require an actor story.
- **UNCERTAINTY_REMOVED:** the synthetic path shows a hidden conditional
  split, temporal blocks, empty strata, leakage, missingness, and an
  ineligible mint kept out of the denominator. The two published CONTROL
  closes stay scoped to their own targets.
- **CAPABILITY_OR_EVIDENCE:** `discovery-execute`, durable
  `DISCOVERY_QUERY_LOOK` artifacts, freeze binding check, prior relation,
  aligned Producer/Critic instructions.
- **STOP:** merge phrase. No market discovery in this atom.
- **NEXT:** after merge, one ordinary slash with
  `OWNER_FOCUS=COHORT_STRATIFIED_LIFECYCLE_PATHS`.
- **REPLAN_TRIGGER:** a minimal path with no admissible role or joint support,
  or a requirement for a new platform.

## Feasibility before code

State-only. `typed_value` was not selected. Role `EXPLORATORY_REUSE`.
Budget remains AUTO 1/1 and distinct focus 1/3.

| Cohort | base_x-like | joint X300 price+liquidity | prefix price+liquidity through Y1800 |
|---|---:|---:|---:|
| C1 | 475 | 475 | 332 |
| C2 | 249 | 249 | 128 |
| C3 | 425 | 425 | 342 |

`HFIC-CAND-2E0C5E5A8ABC` is `KILL_PREPARATORY_LOOP` on ticket asymmetry.
`HFIC-CAND-3232D00BED03` is `KILL_MECHANISM` on holder breadth.
Both are CONTROL-scoped. A different price/liquidity state question is
`SCOPED_CONTROL_DOES_NOT_BLOCK`. An exact scope match remains a duplicate.

## Managed write set

See the YAML `managed_write_set`.
