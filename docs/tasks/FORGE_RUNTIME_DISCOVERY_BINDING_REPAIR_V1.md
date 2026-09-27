---
task_id: FORGE_RUNTIME_DISCOVERY_BINDING_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-27'
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
  expected_base: c7a081e92443dfd09977aad9f6c7446f79127405
  expected_upstream: origin/main
  expected_upstream_oid: c7a081e92443dfd09977aad9f6c7446f79127405
  expected_branch: cursor/forge-runtime-discovery-binding-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Resolve a discovery admission binding from the published live-corpus labels
  and partition hashes so ordinary Forge does not stop on a missing holdout
  boolean, and carry recoverable prior scope into both Forge and Critic
  projections. Do not run market Prompt A, market Critic, or an experiment.
  Do not write the live ResearchStore.

managed_write_set:
  - docs/tasks/FORGE_RUNTIME_DISCOVERY_BINDING_REPAIR_V1.md
  - docs/reports/forge_runtime_discovery_binding_repair/a1_owner_readout_v1.md
  - docs/evidence/forge_runtime_discovery_binding_repair/a1_live_binding_readback_v1.json
  - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_prior_memory.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - scripts/hypothesis_forge.py
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - .cursor/commands/hypothesis-forge.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_forge_runtime_discovery_binding_v1.py
  - tests/test_hfic_grounded_discovery_v1.py

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
      - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_runtime_discovery_binding_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_RUNTIME_DISCOVERY_BINDING_REPAIR_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=PRD_LITE

Owner EXECUTE contract. Bound base is `origin/main`
`c7a081e92443dfd09977aad9f6c7446f79127405`. Route `DIRECT_CURSOR_DELIVERY`.
MODEL_EFFORT: `SOL_XHIGH`.

## Task Outcome Brief

- **Owner decision:** ordinary `/hypothesis-forge` must obtain its discovery
  binding from the published corpus contract, and prior scope that can be
  recovered must reach both Prompt A and Critic.
- **Named consumer:** the next authorized ordinary slash
  `OWNER_FOCUS=COHORT_STRATIFIED_LIFECYCLE_PATHS`.
- **Cheapest falsifier:** seal/verify/import a synthetic cohort, then
  `discovery-binding` without a hand-written `holdout`.
- **Non-goals:** market Prompt A, market Critic, experiment, provider calls,
  holdout value reads, live RDP writes, freeing a scientific slot.
- **Evidence budget:** synthetic publication and a temporary ResearchStore.
  Live readback is metadata and streaming hashes only.

## Decision capsule

- **DECISION_DELTA:** `holdout=false` is derived only when published labels
  match `REQUIRED_LABELS` and no protected holdout assignment is present.
  Unknown, forbidden, conflicting, or hash-mismatched publications stop
  before the value loader. Canonical prior memory is compared even when the
  caller prior list is empty. PARK, NOT_SELECTED, NO_WORTHY and technical
  stops do not ban a family. A valid same-scope close still blocks.
- **UNCERTAINTY_REMOVED:** the live corpus binding is admissible without
  republishing, and a representation-bound CONTROL close does not become an
  ordinary close merely by dropping scope fields.
- **CAPABILITY_OR_EVIDENCE:** `discovery-binding`, partition-aware
  `discovery-execute`, scope fields on prior capsules.
- **STOP:** merge phrase. No market discovery in this atom.
- **NEXT:** after merge, one ordinary slash with
  `OWNER_FOCUS=COHORT_STRATIFIED_LIFECYCLE_PATHS`.
- **REPLAN_TRIGGER:** published labels contradict `REQUIRED_LABELS`, or a
  protected holdout assignment appears on the live corpus.

## Memory outcome

`SCOPED_MEMORY_REPAIR`. Hypothesis versions and cycles now persist scope axes
that the draft already had. The reader fills gaps from the immutable cycle
without overwriting a stored field. Empty caller priors do not skip that
comparison. An incomplete unrelated prior stays `UNKNOWN_SCOPE_NEEDS_RESOLUTION`
and does not stop the forge. Historical packets stay readable.

## Managed write set

See the YAML `managed_write_set`.
