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
  expected_base: 93d8d8552f09b4e08bc2b62d1bf81e14fe07e10c
  expected_upstream: origin/main
  expected_upstream_oid: 93d8d8552f09b4e08bc2b62d1bf81e14fe07e10c
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
  - docs/evidence/forge_ordinary_operation_contract/operator_trials_4_to_8_v1.json
  - docs/evidence/forge_ordinary_operation_contract/replacement_acceptance_v1.json
  - docs/evidence/forge_ordinary_operation_contract/replacement_10_acceptance_v1.json
  - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/research_store.py
  - scripts/hypothesis_forge.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - tests/test_hfic_ordinary_operation_v1.py
  - tests/test_hfic_ordinary_operation_acceptance_v1.py
  - tests/test_research_store.py
  - tests/test_hfic_grounded_discovery_v1.py
  - tests/test_hfic_temporal_owner_path_v1.py
  - tests/test_hfic_temporal_production_runner_v1.py
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_temporal_operability_repair_v1.py
  - tests/test_hfic_legacy_parent_continuation_compat_v1.py
  - .cursor/commands/hypothesis-forge.md
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
  Operator trials 4-8 stay recorded. Trial 7 stays MISSING_INPUT.
  Replacement 9 stays BLOCKED_GIT_COMPOSITE_CHANGED and is not rewritten.
  Session HFIC-SESS-0E1065476AE7A9D6 stays FROZEN_AWAITING_CRITIC.
  Replacement 10 is OPERATIONAL_PASS, not a scientific PASS.
  Isolated Critic terminal KILL_UNBOUND_EVIDENCE, session
  SYNTHESIS_COMPLETE, ordinary entry RETURN_EXISTING_SESSION.
  acceptance_code_head is c907e76ce96bb774030f88aa1b93a1f315a503a5.
  Merging main 93d8d855 did not change Forge runtime. A later
  ordinary-path fix did: exact REPLAY and pending RESUME now precede
  ORDINARY_OPERATION_SLOT_CLOSED. Acceptance 10 was not rerun and does
  not cover that runtime delta.
  No second replacement.
  Do not regenerate trial 7. Do not weaken the git fence.
  After merge, use Forge. Do not open another ordinary-path audit.
  Do not execute the prepared liquidity-retention launch.
  Do not reopen CLOSED #355.

Published-corpus acceptance on `_publish` (one data root per scenario):

| Scenario | Result |
|---|---|
| A | PASS. Negative SIMPLE, cap 1, pause, cold `forge-run` `AUTHORIZE_ADDITIONAL_LOOKS`, exact replay, spec change refused, new grant, compound, freeze `NO_WORTHY_HYPOTHESIS`, terminal readback. MAIN 0→1→1→2. |
| B | PASS. One request, cap 2, two CLI calculations, third `OWNER_CAP_EXHAUSTED`. |
| C | PASS. Scripted critic `PASS_TO_CLASSIFICATION` (`SCRIPTED_CRITIC_MECHANICAL`), then standard classification `PASS_FAST_LANE_READY` / `FAST_LANE_READY`. MAIN stays 1. |
| D | PASS. Reply-lost, transition-lost, and reserve-only resume do not recompute a committed look. Last allowance unit: one `RESERVED`, one `OWNER_CAP_EXHAUSTED`. |
| E | PASS. Foreign market, journal, and corpus refuse before values. Missing operation refuses. MAIN, ADAPTIVE, and PREVIEW caps refuse before values. Zero-match, feature-unknown, and invalid spec stay distinct. |
| F | PASS. Existing closed-repair readback, no new operation. |
| Journal isolation | PASS. A foreign journal reservation does not reduce this journal's protocol remainder. |

Ordinary operation contract. Historical scientific contracts stay in place.
The closed repair `4a01bbb755f2097dd99285e619f3699bcb2e7879957d2bfa9bc254dbc64da0f1`
is not reopened. `spent_main_looks` on that disposition stays the apply-time
snapshot; the journal count remains the live spend.
