---
task_id: HFIC_FRESH_CONTROL_DECISION_INTEGRITY_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-09'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 9044db6b1b65614f55c074c481fb0dfd323ca2e1
  expected_upstream: origin/main
  expected_upstream_oid: 9044db6b1b65614f55c074c481fb0dfd323ca2e1
  expected_branch: cursor/hfic-fresh-control-decision-integrity-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close the three confirmed P1 decision-integrity defects before the first
  fresh lifecycle CONTROL Forge run: critic packet 1.4 freeze-owned grounding
  transport, HFIC ExperimentSpec FEAT bind, F3 effective_control_terminal
  prereg branching, CURRENT_REPRESENTATION_CONTROL_V1 evidence-surface fence,
  and CONTROL-only min usable yield gate. One bounded vertical atom. Do not
  redesign Forge.

managed_write_set:
  - docs/tasks/HFIC_FRESH_CONTROL_DECISION_INTEGRITY_CLOSURE_V1.md
  - src/solana_alpha_lab/factory/hfic_control_integrity.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_memory_policy.py
  - scripts/hypothesis_forge.py
  - catalog/schemas/hypothesis_critic_input_v1.schema.json
  - catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json
  - configs/hypothesis_forge_independent_critic_v1.yaml
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/contracts/normalized_trajectory_representation_probe_v1.md
  - tests/test_hfic_fresh_control_decision_integrity_closure_v1.py
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - tests/test_hfic_cli.py
  - tests/test_hfic_critic_prior_memory_closure_v1.py
  - tests/test_hfic_fresh_session_version_lock_v1.py
  - tests/test_hfic_manual_grounding_contract_diagnostics_v1.py
  - tests/test_hfic_one_frozen_runner_up_failover_v1.py
  - tests/test_hfic_operational_closure_v1.py
  - tests/test_hypothesis_forge_independent_critic_v1.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/hfic_fresh_control_decision_integrity_closure/a1_owner_readout_v1.md
  - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - ACTIVE_RDP_WRITE
  - CURRENT_LIVE_COHORT_SCIENTIFIC_CONTENT_ACCESS
  - REAL_HYPOTHESIS_FORGE_SLASH
  - PROVIDER_API_RPC_WSS
  - EXPERIMENT_EXECUTION
  - HOLDOUT_ACCESS
  - HFIC_CAND_IDENTITY_CHANGE
  - HISTORICAL_PACKET_1_3_REWRITE
  - F3_STATE_MACHINE_REDESIGN
  - GENERIC_EXPERIMENT_SPEC_REQUIRED
  - CONTROL_FILESYSTEM_SANDBOX
  - REPRESENTATION_CHALLENGER_IMPLEMENTED

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
      - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_fresh_control_decision_integrity_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FRESH_CONTROL_DECISION_INTEGRITY_CLOSURE_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=NONE. Exact owner atom: close three P1 decision-integrity defects
before FIRST_FRESH_LIFECYCLE_CONTROL_FORGE.

## Task Outcome Brief

- **Owner decision:** first fresh preregistered CONTROL must not run while the
  three confirmed P1 decision-integrity defects remain.
- **Product outcome:** packet 1.4 freeze-owned grounding is visible to C1/C2;
  HFIC classification binds ExperimentSpec FEAT sets; prereg branches on
  `effective_control_terminal`; CONTROL mode fences Prompt A off raw lifecycle
  sequences and enforces `MIN_USABLE_YIELD_ELIGIBLE=10` before consuming the
  CONTROL search.
- **Named consumer:** `FIRST_FRESH_LIFECYCLE_CONTROL_FORGE`.
- **Cheapest falsifier:** any of T1–T31 fail, or architecture critic answers
  yes to hiding availability, FEAT switch + PASS, unresolved FAST_LANE,
  C1-driven probe after C2, CONTROL raw sequences, low-yield search consume,
  evidence_epoch mutation, or search-budget shopping.
  Executable T1–T31 live in
  `tests/test_hfic_fresh_control_decision_integrity_closure_v1.py`.
- **Terminal outcome:** `PROCEED` only after focused tests, isolated reviews,
  exact-head CI and merge-readiness PASS. Stop before owner merge phrase.
- **Non-goals:** challenger projection, embeddings, generator, C3+, generic
  ExperimentSpec/classifier redesign, live CONTROL, experiment, alpha, UI.
- **Evidence budget:** disposable ResearchStore / synthetic labels only.
  `ACTIVE_RDP_WRITES=0`. No live cohort scientific content.
- **SPEC_ROUTE=NONE**

## Decision capsule

- `DECISION_DELTA`: close grounding transport, F3 effective terminal, CONTROL
  fence and CONTROL yield gate without a Forge redesign.
- `UNCERTAINTY_REMOVED`: first fresh CONTROL can be interpreted without the
  three known P1s.
- `CAPABILITY_OR_EVIDENCE`: packet 1.4 + HFIC spec bind + prereg effective
  terminal + CONTROL preflight mode.
- `STOP`: exact-head CI and merge-readiness; do not ask the owner phrase.
- `NEXT`: owner exact phrase, then guarded merge.
- `SPEC_ROUTE=NONE`

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. This is decision-integrity closure for one
named CONTROL consumer, not a new research platform. `PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.

PASS means only: the first fresh lifecycle CONTROL can run without the three
currently known P1 defects. It does not mean Forge found a good hypothesis,
representation sufficiency, alpha, ranking quality, scientific confirmation,
experiment authority or owner FCF.

## Authority and non-claims

Provider/API/RPC/WSS, credentials, wallet, signer, transaction, cash,
deployment, settings, destructive/history actions and branch deletion are
not authorized. Tests, PR, CI or merge do not establish semantic acceptance,
canonical `DONE`, alpha or cashflow.
