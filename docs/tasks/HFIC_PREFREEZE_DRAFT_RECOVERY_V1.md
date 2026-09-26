---
task_id: HFIC_PREFREEZE_DRAFT_RECOVERY_V1
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

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 72c9dc9827f633d891675e00125699e17f98918d
  expected_upstream: origin/main
  expected_upstream_oid: 72c9dc9827f633d891675e00125699e17f98918d
  expected_branch: cursor/hfic-prefreeze-draft-recovery-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Remove the observed OBSERVABILITY_BLOCKED on the already saved exact
  generated draft so a capability-only repair can freeze it and continue to
  Critic, without a new scientific trial, without rewriting RDP, and without
  releasing the scientific slot. THIS_REPAIR_DOES_NOT_CREATE_A_NEW_SCIENTIFIC_LOOK.
  EXACT_GENERATED_DRAFT_RECOVERY_ONLY.

managed_write_set:
  - docs/tasks/HFIC_PREFREEZE_DRAFT_RECOVERY_V1.md
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - tests/test_research_store.py
  - tests/test_hfic_prefreeze_draft_recovery_v1.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/hfic_prefreeze_draft_recovery/a1_owner_readout_v1.md
  - docs/evidence/hfic_prefreeze_draft_recovery/a1_real_slot_readonly_proof_v1.json
  - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - REAL_RDP_WRITE
  - RDP_REWRITE_OR_SLOT_RELEASE
  - NEW_SCIENTIFIC_TRIAL
  - PROMPT_A_REGENERATION
  - CRITIC_ON_MARKET_EVIDENCE
  - PROVIDER_API_RPC_WSS
  - EXPERIMENT_EXECUTION
  - CAPABILITY_DRIFT_FOR_FROZEN_OR_COMPLETED_SESSIONS
  - NEW_RECOVERY_SERVICE
  - ABSOLUTE_MACHINE_PATHS_IN_DURABLE_RECEIPT
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
      - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_prefreeze_draft_recovery/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_PREFREEZE_DRAFT_RECOVERY_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=PRD_LITE

Owner EXECUTE contract. Bound base is current `origin/main`
`72c9dc9827f633d891675e00125699e17f98918d` (PR #344), not the design-time
`0ecc322a`. Route `DIRECT_CURSOR_DELIVERY`. MODEL_EFFORT: `SOL_XHIGH`.

Primary route `SEM-HYPOTHESIS-FORGE` is CAPABILITY. It grants no execution
authority.

## Task Outcome Brief

- **Owner decision:** the saved generated draft must become freezable after a
  capability-only code repair. The occupied market slot stays occupied.
- **Named consumer:** the next authorized
  `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL` on the same draft.
- **Cheapest falsifier:** disposable-store tests for prose-vs-path, pre-persist
  refusal, capability-B resume of the exact draft, and denial on every other
  identity axis plus an already-frozen session.
- **Non-goals:** mutating the real ResearchStore; Prompt A; Critic execution;
  a second reservation; a new recovery service; slot release.
- **Evidence budget:** synthetic stores plus one read-only inspection of the
  real store. `REAL_RDP_WRITES=0`.

## Decision capsule

- `DECISION_DELTA`: physical-path checks reject filesystem leakage, not prose
  colons. A generated draft with no lifecycle row may resume across a
  capability epoch change. Both epochs stay visible. A lifecycle row returns
  to strict binding.
- `UNCERTAINTY_REMOVED`: `Weak:` no longer poisons a slot, and a poisoned
  pre-freeze slot is not a missing readback.
- `CAPABILITY_OR_EVIDENCE`: the validator, the pre-persist guard, the
  pre-freeze resume, and the read-only real-slot proof.
- `STOP`: merge-readiness and the machine owner phrase. Do not merge in this atom.
- `NEXT`: after merge, one `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`
  resumes draft `a857b48fd253a941...`. It does not regenerate Prompt A.
- `REPLAN_TRIGGER`: recovery requires rewriting or deleting RDP records,
  releasing the slot, or applying the capability exception to a frozen or
  completed session.

## Acceptance statements

- `THIS_REPAIR_DOES_NOT_CREATE_A_NEW_SCIENTIFIC_LOOK`
- `EXACT_GENERATED_DRAFT_RECOVERY_ONLY`

Observed draft `HFIC-ART-FORGE-DRAFT-GENERATED-A857B48FD253A941`, payload
prefix `a857b48fd253a941`, session `HFIC-SESS-481C699406A919C1`, slot
`683b3ed3d3b4840c88406cca80905c0cf04ae1f642dd01afa6b81e5cddbc58f1`, market
`ae771cf5c1e7692c007b442c0048e7547005dc09125eeb9eb75e24406e429749`.
No lifecycle row. One reservation. This atom does not freeze that draft.
