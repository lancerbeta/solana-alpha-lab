---
task_id: HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-26'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e1c8c3f4f31707fa2ae2de7b161e5954f517fd7a
  expected_upstream: origin/main
  expected_upstream_oid: e1c8c3f4f31707fa2ae2de7b161e5954f517fd7a
  expected_branch: cursor/hypothesis-forge-independent-critic-v1
  dirty_mode: ALLOW_REPORTED
objective: Wire manual Hypothesis Forge (explicit slash only) and mandatory Independent Critic auto-handoff after synthesis in new context under MANUAL_FALLBACK_UNTIL_GENERATOR, with schemas, operator pack, skills and tests; design/discovery only with zero provider, Git mutation or experiment execution.
managed_write_set:
  - docs/tasks/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/schemas/hypothesis_forge_synthesis_handoff_v1.schema.json
  - .cursor/commands/hypothesis-forge.md
  - .cursor/commands/independent-hypothesis-critic.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - tests/test_hypothesis_forge_independent_critic_v1.py
  - tests/test_delivery_harness_adapters.py
  - tests/fixtures/hypothesis_forge/critic_input_packet_valid_v1.json
  - tests/fixtures/hypothesis_forge/synthesis_handoff_pending_critic_v1.json
  - tests/fixtures/hypothesis_forge/synthesis_handoff_complete_v1.json
  - catalog/assets/core.yaml
  - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_independent_review_v1.json
  - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  AUTONOMOUS_HYPOTHESIS_GENERATOR
  PROVIDER_API_RPC_WSS
  GIT_MUTATION_FROM_FORGE_OR_CRITIC
  EXPERIMENT_EXECUTION
  WALLET_SIGNER_TX_OR_CASH
  AUTOMATIC_PROMOTION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_independent_review_v1.json
      - docs/evidence/hypothesis_forge_independent_critic/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_V1

## Task Outcome Brief

- **Owner decision:** after Fast Lane foundation (#197), DDL eligibility (#198),
  and Jupiter registry (#199), commission a manual Hypothesis Forge + Independent
  Critic contour without an autonomous generator. Forge runs only on explicit
  slash; Critic auto-launches after synthesis so the owner cannot forget step 2.
- **Product outcome:** repository exposes `/hypothesis-forge`,
  `/independent-hypothesis-critic`, skills, HFIC-V1.0 operator pack, machine
  schemas for `CRITIC_INPUT_PACKET` and synthesis handoff, and tests proving
  `SYNTHESIS_COMPLETE` requires critic terminal. Runtime contour remains
  design/discovery only.
- **Named consumers:** owner evening hypothesis cycle; future scheduler only after
  measured operational gaps (not this atom).
- **Cheapest falsifier:** slash/skill docs exist but handoff schema allows
  `SYNTHESIS_COMPLETE` without critic, or Forge skill omits mandatory auto-launch.
- **Terminal outcome:** one PR, green exact-head CI, stop before merge for exact
  owner phrase.
- **Non-goals:** no Hypothesis Generator; no provider/network; no Git mutation from
  Forge/Critic runs; no experiment execution; no insider research series; no RAG/graph
  orchestration.
- **Evidence budget:** offline schema/skill contract tests + catalog validate +
  exact-head CI at merge.
- **Replan trigger:** auto-critic handoff cannot be expressed in skill/command
  contract without violating new-context isolation.

## Decision capsule

- `DECISION_DELTA`: manual Forge via slash + mandatory Critic auto-handoff replaces
  ad-hoc Downloads starter as in-repo operator contour.
- `UNCERTAINTY_REMOVED`: owner can run one bounded evening cycle with enforced
  critic gate before any execution atom.
- `CAPABILITY_OR_EVIDENCE`: config, schemas, operator pack, slash commands, skills,
  handoff invariant tests, delivery evidence.
- `STOP`: after green CI; do not merge; do not run live Forge against provider.
- `NEXT`: owner exact phrase → guarded merge → first manual `/hypothesis-forge`
  session on `main`.
- `SPEC_ROUTE=NONE`

## UX contract (owner-approved)

| Component | Behavior |
|---|---|
| Forge | **Explicit slash only** (`/hypothesis-forge`) |
| Critic | **Auto after synthesis** in new/isolated context |
| Generator | **Forbidden** — `MANUAL_FALLBACK_UNTIL_GENERATOR` |
| Boundaries | No provider, Git mutation, experiment execution |

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
