---
task_id: HFIC_LEGACY_READBACK_HONESTY_V1
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
  expected_base: 94a4ea74afb6c921f4972312840be2de5eeba4f9
  expected_upstream: origin/main
  expected_upstream_oid: 94a4ea74afb6c921f4972312840be2de5eeba4f9
  expected_branch: cursor/hfic-legacy-readback-honesty-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  History written by earlier HFIC protocol versions or earlier code is read as
  typed historical truth: owner read surfaces never crash, unknown times never
  become prospective evidence, no session disappears silently, a fresh
  session's runtime proof is not falsified by unrelated legacy provenance, and
  A5 admission/budget strictness for the current market is unchanged.
  Acceptance includes a FIRST_REAL_RUN_READINESS rehearsal on a disposable
  copy of the real RDP.

managed_write_set:
  - docs/tasks/HFIC_LEGACY_READBACK_HONESTY_V1.md
  - src/solana_alpha_lab/factory/hfic_provenance.py
  - src/solana_alpha_lab/factory/observation_panel_coverage.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - src/solana_alpha_lab/factory/hfic_representation_ladder.py
  - src/solana_alpha_lab/factory/hfic_grounding.py
  - scripts/hypothesis_forge.py
  - tests/test_hfic_legacy_readback_honesty_v1.py
  - tests/fixtures/hypothesis_forge/legacy_shapes/l1_provenance_correction_v1_1.json
  - tests/fixtures/hypothesis_forge/legacy_shapes/l2_runner_up_identity_cycles.json
  - tests/fixtures/hypothesis_forge/legacy_shapes/l3_hypothesis_placeholder_created_at.json
  - tests/test_hfic_provenance_clock.py
  - .agents/skills/hypothesis-forge/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/hfic_legacy_readback_honesty/a1_owner_readout_v1.md
  - docs/evidence/hfic_legacy_readback_honesty/a1_real_copy_rehearsal_v1.json
  - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - REAL_RDP_WRITE
  - HISTORICAL_RECORD_REWRITE
  - OUTCOME_VALUE_READ_OR_PRINT
  - REAL_HYPOTHESIS_FORGE_SLASH
  - LLM_PROMPT_OR_CRITIC_ON_MARKET_EVIDENCE
  - PROVIDER_API_RPC_WSS
  - EXPERIMENT_EXECUTION
  - A5_ADMISSION_OR_BUDGET_WEAKENING
  - CLASSIFICATION_CHANGE
  - GENERIC_LANE_CLASSIFIER_CHANGE
  - SHARED_OBSERVATION_ROUTING_TABLE_CHANGE
  - SCHEMA_CHANGE_FORGE_INPUT_OR_FORGE_RUN
  - NEW_COMMAND_OR_SERVICE
  - FORWARD_ONLY_DATA_OPTION_SEMANTICS
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
      - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_legacy_readback_honesty/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_LEGACY_READBACK_HONESTY_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=PRD_LITE

Owner-approved PRD «Честное чтение истории» (full R1–R7, 2026-09-25). Base
`971e0a09e600ae3210b07094dd071824708d6bbd` (merge PR #333). Post-merge CI
success after retry of `validate-tests (3)` on run 36153861551. Route
`DIRECT_CURSOR_DELIVERY`. MODEL_EFFORT: `SOL_XHIGH`.

## Task Outcome Brief

- **Owner decision:** OK on the PRD plus already recorded contracts: the
  correction-record schema enum of protocol versions, provenance
  «placeholder = UNKNOWN, chronological_use_forbidden», and the A5 owner table
  «legacy row → HISTORICAL_ONLY / UNRESOLVED_BINDING — readable history».
- **Named consumer:** owner; Fast Lane / ObservationSchedule (`evidence_role`);
  A5 admission; future protocol-version changes.
- **Cheapest falsifier:** RED tests T1–T5.
- **Non-goals:** rewriting RDP history or writing a new correction record;
  `hfic_evidence_identity.py`; forge-input / forge-run receipt schemas;
  `run_live_classifier`, the availability gate, `_classifier_to_hfic_terminal`;
  `lane_classifier.py`; `observation_fast_lane_terminals.py`; new CLI commands;
  weakening A5 admission or budget; real `/hypothesis-forge`; provider/RPC;
  experiment execution; outcome-value reads.
- **Evidence budget:** synthetic fixtures marked `SYNTHETIC_AUDIT_FIXTURE`, plus
  one disposable copy of the real RDP. `REAL_RDP_WRITES=0`.

## Decision capsule

- `DECISION_DELTA`: history is checked against the protocol version that wrote
  it. Strictness stays only on admission.
- `UNCERTAINTY_REMOVED`: false `PROVENANCE_CORRECTION_CORRUPT`, false
  `PROSPECTIVE_OOS`, unreadable history, silent session drops.
- `CAPABILITY_OR_EVIDENCE`: the readback fixes, a permanent legacy corpus, and
  a `FIRST_REAL_RUN_READINESS` receipt.
- `STOP`: merge-readiness and the machine owner phrase. Do not merge in this atom.
- `NEXT`: on GO, the first real `/hypothesis-forge` with a separate owner OK.
- `REPLAN_TRIGGER`: any of T1–T5 fails to reproduce the defect on the base; the
  fix requires `hfic_evidence_identity.py`, forge-input/forge-run schemas,
  classification, `lane_classifier.py`, or `observation_fast_lane_terminals.py`;
  read mode is possible only by editing A5 tests; the rehearsal shows a new
  session on current code becomes unreadable for a cause outside the write set;
  the same blocker twice; or the work only prepares more work.

## Requirements

- **R1.** Validate correction records against the supported-protocol set, one
  constant equal to the schema enum. Do not use `PROMPT_VERSION` for reading.
  Coverage is by identity (`record_id` + `payload_sha256`). `inventory_sha256`
  is additional confirmation, not the only key. Extra historical
  `affected_records` are allowed. An uncovered current placeholder is
  `PROVENANCE_TIME_UNCOVERED` or `PARTIAL` with an uncovered count. Forgery
  stays `CORRUPT`. `apply_provenance_correction` writes are unchanged.
- **R2.** `resolve_authoritative_hypothesis_registered_at` skips placeholder
  instants in both `record.created_at` and `payload.created_at`. No real
  instant left returns `None`. `compute_evidence_role` is unchanged. No other
  semantic edit in that module.
- **R3.** Default `load_session_bundle` stays strict for admission and
  lifecycle. An explicit read mode is only for `show_session`, `prove_runtime`,
  and diagnostics session collection. The ladder does not use it. A conflict
  on a durable identity field yields `identity_status=UNRESOLVED_BINDING`,
  disputed fields `None`, and `identity_conflict_fields`, without guessing.
  New sessions must write those fields consistently (T10).
- **R4.** Diagnostics reports `sessions_listed`, `sessions_readable`,
  `sessions_unresolved`, `sessions_unreadable` with codes, and store
  `provenance_time_status`. Prior fields stay. The ladder records a typed skip
  instead of `except Exception: continue`. `forge-run` `owner_readout` includes
  `history: readable X/Y; unresolved N; skipped M (codes); provenance: STATUS`
  without a forge-run schema change. A skipped session stamped with the
  current market is `BLOCKED`, never `START`. Other markets and legacy rows
  are a visible skip only. Current-market identity conflict remains
  `STOP SCIENTIFIC_IDENTITY_CONFLICT`.
- **R5.** `prove_runtime` stays strict about the session's own artifacts.
  Session provenance uses `provenance_status_for_session`. Store-wide
  provenance is a separate field `VALID | CORRECTED | INVALID:<code>` plus a
  readout line. A clean fresh session over an `INVALID` store is `PROVEN`
  with an explicit warning. A legacy session whose placeholders sit under an
  invalid correction is a typed failure.
- **R6.** Permanent legacy corpus. T8 swaps `PROMPT_VERSION` to a hypothetical
  `HFIC-V1.3` in `hfic_session` and `hfic_provenance`: L1 stays valid, L2 is
  readable in read mode, L3 is `EXPLORATORY_REUSE`. T9 pins the supported
  protocol constant to the schema enum.
- **R7.** Skill and operator pack (outside `BEGIN/END PROMPT` blocks): the
  `history` line in `FORGE RUN` must be shown; an unreadable current market or
  `INVALID` provenance is `STOP` before Prompt A; everything else is a visible
  warning. `FIRST_REAL_RUN_READINESS` comes from the rehearsal.

## Why identity coverage is stronger than an inventory-hash equality

A correction written by an earlier protocol names the placeholder rows it
actually saw: `record_id` plus `payload_sha256`. That pair is the identity of
a committed record. Requiring the stored `inventory_sha256` to equal today's
inventory makes a later, still-covered store look corrupt whenever the hash
input grew or shrank, even though every current placeholder is named. Identity
coverage checks the invariant directly: every current placeholder pair is in
`affected_records`. The inventory hash remains a visible confirmation
(`inventory_digest_drift` when it disagrees) and is not a second admission
key. Extra `affected_records` are conservative only when each one still
points at a committed record with that same payload hash. A pair that was
never committed is a phantom and stays `PROVENANCE_CORRECTION_CORRUPT`. An
extra real historical row cannot grant coverage to a current row that is
absent, and it cannot invent a payload the store does not hold.

## Provenance-clock test edit

`tests/test_hfic_provenance_clock.py` is edited only for the R5 coupling that
this atom changes on purpose.
`HficProvenanceCorrectionTests.test_show_session_and_prove_runtime_correction_contract`
appends an uncovered placeholder on a different session and expects
`prove_runtime` of the clean fresh session to raise
`PROVENANCE_TIME_UNCOVERED`. After R5 that proof is `PROVEN` with store
provenance `INVALID:PROVENANCE_TIME_UNCOVERED`. A placeholder on the session
under proof still fails closed.

## Acceptance

- **A1.** T1–T5 are red on the unmodified base and green after the fix.
- **A2–A4, A6.** Disposable real-RDP-copy rehearsal. GO only when H1–H4 hold,
  every path ends in one persisted terminal, read surfaces do not crash, there
  are no silent drops, unknown time never becomes `PROSPECTIVE_*`, a fresh
  session's `prove-runtime` is `PROVEN`, and the real RDP manifest is unchanged.
- **A5.** Focused regressions pass. Protected without edits:
  `tests/test_forge_evidence_identity_and_owner_gold_v1.py`,
  `tests/test_hfic_classification_outcome_integrity_v1.py`,
  `tests/test_observation_fast_lane_routing_closure.py`.
- Isolated reviews PASS for the frozen role set. Exact-head CI success and
  merge-readiness `ready_for_owner_phrase`. Stop before the owner phrase is used.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=PROPORTIONAL`. Narrow HFIC legacy readback.
`PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.

PASS means only: history written by earlier protocol versions or earlier code
is read as typed historical truth, and A5 admission/budget strictness for the
current market is unchanged. Not alpha. Not experiment execution. Not a
scientific market Forge run. History is not rewritten.
