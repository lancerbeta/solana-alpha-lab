---
task_id: HFIC_MANUAL_GROUNDING_CONTRACT_DIAGNOSTICS_V1
task_version: '1.0'
status: READY
as_of: '2026-09-03'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 6529a9714e4aa39b51f2b8d964098e32bf81f28b
  expected_upstream: origin/main
  expected_upstream_oid: 6529a9714e4aa39b51f2b8d964098e32bf81f28b
  expected_branch: cursor/hfic-manual-grounding-contract-diagnostics-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Vertical HFIC V1.2 atom: deterministic feature-grounding projection, machine
  candidate contract with unresolved requirements + structural signature,
  session diagnostics and diagnostics --last N readout, offline E2E proof.
  Preserve V1.1 compatibility and HFIC-CAND identity. Do not reopen ARCH-INTENT-006
  or build autonomous generator/ranker.

managed_write_set:
  - docs/tasks/HFIC_MANUAL_GROUNDING_CONTRACT_DIAGNOSTICS_V1.md
  - src/solana_alpha_lab/factory/hfic_grounding.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - scripts/hypothesis_forge.py
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - catalog/schemas/hypothesis_forge_draft_v1_2.schema.json
  - catalog/schemas/hypothesis_forge_session_receipt_v1_2.schema.json
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/schemas/hfic_next_epistemic_action_v1.schema.json
  - catalog/schemas/hfic_provenance_time_correction_v1.schema.json
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - tests/test_hfic_manual_grounding_contract_diagnostics_v1.py
  - tests/test_hfic_operational_closure_v1.py
  - tests/test_hfic_discovery_prospects_and_next_action.py
  - tests/fixtures/hypothesis_forge/draft_v1_2_valid.json
  - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_factory_fit_v1.json
  - docs/reports/hfic_manual_grounding_contract_diagnostics/a1_owner_readout_v1.md
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - ARCH_INTENT_006_REOPEN
  - TRIGGER_A_OR_B_PROOF_ATTEMPT
  - AUTONOMOUS_GENERATOR_OR_RANKER
  - NEW_DB_VECTOR_RAG_OR_FEATURE_STORE
  - PROVIDER_API_RPC_WSS_REQUIRED
  - EXPERIMENT_OR_HOLDOUT
  - HFIC_CAND_IDENTITY_REWRITE

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
      - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_manual_grounding_contract_diagnostics/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_MANUAL_GROUNDING_CONTRACT_DIAGNOSTICS_V1

Design authority: owner pack `HYPOTHESIS_FORGE_MANUAL_GROUNDING_CONTRACT_DIAGNOSTICS_V1_1`.

Phases P1–P4 in one delivery atom. SPEC_ROUTE=BOTH (design pack + implementation).

## DoD (compact)

- FORGE_CONTEXT includes deterministic feature_grounding projection
- V1.2 draft schema + freeze grounding + structural_signature (not identity)
- Session diagnostics + `hypothesis_forge.py diagnostics --last N`
- Offline vertical E2E PASS; V1.1 readable; unknown FEAT/CAP fail-closed
- No ARCH-INTENT-006 activation; no generator/ranker
