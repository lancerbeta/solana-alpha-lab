---
task_id: FORGE_ORDINARY_OPERATION_CONTRACT_V1
task_version: '1.0'
status: READY
as_of: '2026-09-29'
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
  expected_base: a372f81376a7d77fe2500201739a46a736f2d986
  expected_upstream: origin/main
  expected_upstream_oid: a372f81376a7d77fe2500201739a46a736f2d986
  expected_branch: cursor/forge-ordinary-operation-contract-v1
  dirty_mode: FORBIDDEN

objective: >-
  Bind one explicit ordinary owner request to an existing journal so a single
  SIMPLE look can pause with the search still open, a later process can read
  that state, and a new authorization continues the same journal instead of
  opening a free session or a repair continuation.

managed_write_set:
  - docs/tasks/FORGE_ORDINARY_OPERATION_CONTRACT_V1.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - .agents/skills/hypothesis-forge/SKILL.md
  - docs/evidence/forge_ordinary_operation_contract/a1_delivery_completion_evidence_v1.json
  - docs/evidence/forge_ordinary_operation_contract/a1_delivery_independent_review_v1.json
  - docs/evidence/forge_ordinary_operation_contract/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_ordinary_operation_v1.py
  - tests/test_hfic_grounded_discovery_v1.py
  - tests/test_hfic_temporal_owner_path_v1.py
  - tests/test_hfic_temporal_production_runner_v1.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - NEW_LIVE_LOOK
  - REOPEN_CLOSED_REPAIR_GRANT
  - NEW_PROVIDER
  - MERGE_BEFORE_OWNER_PHRASE

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
      - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
    DELIVERY_EVIDENCE:
      - docs/evidence/forge_ordinary_operation_contract/a1_delivery_completion_evidence_v1.json
      - docs/evidence/forge_ordinary_operation_contract/a1_delivery_independent_review_v1.json
      - docs/evidence/forge_ordinary_operation_contract/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: NONE

DECISION_DELTA: >-
  An ordinary pause is an operation row on the existing journal. It is not a
  scientific NO_WORTHY and not a repair continuation.

UNCERTAINTY_REMOVED: >-
  discovery-execute without an explicit operation no longer spends a look, and
  a cap of one SIMPLE cannot be forced into a search-wide negative terminal
  before values are loaded.

CAPABILITY_OR_EVIDENCE: >-
  One ordinary owner request binds the admitted journal and corpus. Looks
  inside that allowance do not each need a new owner request. A saved
  candidate can still be frozen when the new-look cap is spent. A blocked
  readback is not advertised as a pause, and a scientific terminal is not
  replaced by the operation status. Acceptance scenarios A-F in the tests
  named below are the DoD, not the short coverage table.

STOP: >-
  Stop at exact-head merge-readiness. Do not merge before the owner phrase.
  Do not run the prepared 15m-4h question.

NEXT: >-
  After merge and a separate owner authorization, one live question on a new
  focus. This atom does not start it.

Coverage on synthetic stores through the production CLI:

| Slice | Result |
|---|---|
| V1 | SIMPLE then compound, production freeze `NO_WORTHY_HYPOTHESIS`, new-process forge-run. MAIN 0→1→2. |
| V2 | Positive SIMPLE, exhausted cap, revised spec refused, persist-draft, freeze, scripted critic, finalize. MAIN stays 1. |
| V3 | Closed repair readback with no operation artifact. |
| Guards | Cap 0 before values, preview cap 0, same-operation replay, changed binding refused, blocked run keeps its next_action. |
| Model | One empty-store trial on `gpt-5.6-sol-xhigh` stopped `MARKET_EVIDENCE_BASIS_INCOMPLETE` with no MAIN. Two later trials reported model `UNKNOWN`. |

Ordinary operation contract. Historical scientific contracts stay in place.
The closed repair `4a01bbb755f2097dd99285e619f3699bcb2e7879957d2bfa9bc254dbc64da0f1`
is not reopened. `spent_main_looks` on that disposition stays the apply-time
snapshot; the journal count remains the live spend.
