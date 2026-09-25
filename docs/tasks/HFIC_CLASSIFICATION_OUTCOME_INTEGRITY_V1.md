---
task_id: HFIC_CLASSIFICATION_OUTCOME_INTEGRITY_V1
task_version: '1.0'
status: READY
as_of: '2026-09-25'
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
  expected_base: 6bd7cfca0c33d18149b52cc4e95801952f0736fb
  expected_upstream: origin/main
  expected_upstream_oid: 6bd7cfca0c33d18149b52cc4e95801952f0736fb
  expected_branch: cursor/hfic-classification-outcome-integrity-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  After PASS_TO_CLASSIFICATION or a Critic-claimed final PASS_*, every packet-1.4
  HFIC candidate ends classification in exactly one persisted typed terminal.
  PASS_FAST_LANE_READY is allowed only when every required freeze-owned feature
  binding is PIT_READY and no unresolved requirement remains, on every classifier
  route that maps to PASS_FAST_LANE_READY (derived from the shared mapping, not a
  hand list). A failed availability gate is a persisted KILL_UNBOUND_EVIDENCE with
  typed reasons, never an exception that strands the session. Acceptance includes
  a disposable production-path rehearsal on a copy of the real RDP.

managed_write_set:
  - docs/tasks/HFIC_CLASSIFICATION_OUTCOME_INTEGRITY_V1.md
  - src/solana_alpha_lab/factory/hfic_control_integrity.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - tests/test_hfic_classification_outcome_integrity_v1.py
  - tests/test_hfic_packet14_availability_fast_lane_guard_v1.py
  - tests/test_hfic_fresh_control_decision_integrity_closure_v1.py
  - tests/test_hfic_one_frozen_runner_up_failover_v1.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/reports/hfic_classification_outcome_integrity/a1_owner_readout_v1.md
  - docs/evidence/hfic_classification_outcome_integrity/a1_real_copy_rehearsal_v1.json
  - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - REAL_RDP_WRITE
  - OUTCOME_VALUE_READ_OR_PRINT
  - REAL_HYPOTHESIS_FORGE_SLASH
  - LLM_PROMPT_OR_CRITIC_ON_MARKET_EVIDENCE
  - PROVIDER_API_RPC_WSS
  - EXPERIMENT_EXECUTION
  - GENERIC_LANE_CLASSIFIER_CHANGE
  - SHARED_OBSERVATION_ROUTING_TABLE_CHANGE
  - GENERIC_EXPERIMENT_SPEC_SCHEMA_CHANGE
  - PACKET_SCHEMA_CHANGE
  - A5_IDENTITY_OR_BUDGET_CHANGE
  - LEGACY_READBACK_OR_PLACEHOLDER_TIME_FIX
  - FORWARD_ONLY_DATA_OPTION_SEMANTICS
  - HISTORICAL_RECEIPT_REWRITE
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
      - docs/evidence/hfic_classification_outcome_integrity/a1_real_copy_rehearsal_v1.json
      - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_classification_outcome_integrity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CLASSIFICATION_OUTCOME_INTEGRITY_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=PRD_LITE

Owner-approved PRD «Честный итог классификации» (2026-09-25). Base
`6bd7cfca0c33d18149b52cc4e95801952f0736fb` (merge PR #329). Route
`DIRECT_CURSOR_DELIVERY`. MODEL_EFFORT: `SOL_XHIGH`.

## Task Outcome Brief

- **Owner decision:** recorded packet-1.4 decision (FORWARD_ONLY /
  HISTORICAL_RECONSTRUCTIBLE / MISSING / MISSING_CAPABILITY / PARTIAL / unknown
  cannot map to `PASS_FAST_LANE_READY`; fail-closes to `KILL_UNBOUND_EVIDENCE`)
  plus owner OK on this PRD.
- **Named consumer:** owner; Fast Lane / ObservationSchedule; ladder and budget.
- **Cheapest falsifier:** RED tests T-A and T-B.
- **Non-goals:** `lane_classifier.py`; shared
  `observation_fast_lane_terminals.py`; ExperimentSpec and critic-packet schemas;
  A5 identity, slots, budget, market/capability identity; legacy unreadable
  session F3 and placeholder-time F1; `FORWARD_ONLY` → `PASS_DATA_OPTION_REQUIRED`;
  historical receipt rewrite; real `/hypothesis-forge`; provider/RPC; experiment
  execution; outcome-value reads.
- **Evidence budget:** synthetic fixtures marked `SYNTHETIC_AUDIT_FIXTURE`, plus
  one disposable copy of the real RDP. `REAL_RDP_WRITES=0`.

## Decision capsule

- `DECISION_DELTA`: PIT/unresolved gate applies to the mapped HFIC outcome, not a
  hand-listed classifier terminal set. A failed gate is a persisted terminal, not
  an exception.
- `UNCERTAINTY_REMOVED`: false `PASS_FAST_LANE_READY` through an observation
  route, and the `AWAITING_CLASSIFICATION` deadlock when the gate raises.
- `CAPABILITY_OR_EVIDENCE`: outcome gate + matrix tests + real-copy rehearsal
  receipt.
- `STOP`: merge-readiness and the machine owner phrase. Do not merge in this atom.
- `NEXT`: on GO, the first real `/hypothesis-forge` with a separate owner OK,
  then atom 2 (legacy readback honesty: F3 + F1 + honest diagnostics).
- `REPLAN_TRIGGER`: T-A or T-B does not reproduce the defect on the base; the
  fix requires `lane_classifier.py`, `observation_fast_lane_terminals.py`,
  ExperimentSpec/packet schema, or A5 identity; a new session becomes unreadable
  (F3 class); the same blocker twice; or the work only prepares more work.

## Requirements

- **R1.** On the packet-1.4 classify path, map the raw classifier terminal through
  the existing mapping first. Apply the PIT/unresolved gate if and only if that
  HFIC terminal is `PASS_FAST_LANE_READY`. Do not use a hand list as the gate
  switch. Derive any needed set from the mapping.
- **R2.** A failed gate builds a deterministic classifier receipt: `lane=DENY`,
  `lane_classifier_terminal=DENY_HFIC_AVAILABILITY_GATE`, typed
  `reason_codes` (`REQUIRED_BINDING_NOT_PIT_READY:<FEAT-ID>` and/or
  `UNRESOLVED_REQUIREMENT`), and `classifier_route_terminal` holding the raw
  route. The label maps to `KILL_UNBOUND_EVIDENCE`. Receipt validation rebuilds
  the same receipt; a forged field is `CLASSIFIER_RECEIPT_INVALID`. Primary
  candidate then follows existing runner-up failover; runner-up is final; no C3.
- **R2b.** If the Critic claimed a final `PASS_*` and the live receipt is a gate
  denial, persist `KILL_UNBOUND_EVIDENCE` and keep the claim (for example
  `critic_claimed_terminal`). The machine only downgrades. Other claim/mapping
  disagreements stay `CLASSIFIER_TERMINAL_MISMATCH`.
- **R3.** Honest `PIT_READY` with no unresolved requirement still passes on every
  route. Packet 1.3 behavior is unchanged (packet14 T15). CHANGE_LANE /
  BLOCKED_DATA / DENY / OWNER routes are unchanged.
- **R4.** Tests T-A through T-H, including the full classifier-terminal matrix,
  mapping-source closure, R2b, C2 kill without C3, honest PASS, and receipt
  determinism/forgery.
- **R5.** Session receipt and owner readout show the classifier route and the
  denial reason. No absolute paths.

## Acceptance

- **A1.** T-A and T-B are red on the unmodified base and green after the gate.
- **A2.** Focused regressions pass. Protected cases without edits: honest
  `PANEL_REUSE_READY` → PASS, `tests/test_fast_lane_classifier.py`, packet14 T1
  and T15.
- **A3.** Disposable production-path rehearsal on a copy of the real RDP
  (J1a, J1b, J1c, J2, J3, J5). GO only when every path ends in one persisted
  typed terminal, with zero deadlocks, zero false PASS, readable readback, zero
  writes on rejected inputs, and an unchanged real-RDP manifest.
- **A4.** Isolated reviews PASS for the frozen role set. Architecture names what
  can pass tests and still break research validity.
- **A5.** Exact-head CI success and merge-readiness `ready_for_owner_phrase`.
  Stop before the owner phrase is used.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. Narrow HFIC classify gate.
`PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.

PASS means only: every packet-1.4 candidate ends classification in exactly one
persisted typed terminal, and `PASS_FAST_LANE_READY` requires PIT_READY bindings
with no unresolved requirement on every route that maps to that terminal.
Not alpha. Not experiment execution. Not a scientific market Forge run.
