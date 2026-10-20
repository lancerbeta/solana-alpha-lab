---
task_id: HFIC_CLASSIFICATION_INPUT_RECOVERY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-20'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a8ad00859b52e1c99c4926a549b708b62f4254c0
  expected_upstream: origin/main
  expected_upstream_oid: a8ad00859b52e1c99c4926a549b708b62f4254c0
  expected_branch: claude/hfic-classification-input-recovery-v1
  dirty_mode: ALLOW_REPORTED
objective: A malformed ExperimentSpec envelope is refused before any HFIC classification write, and one already recorded envelope refusal (C6 session HFIC-SESS-78F92D0FE3E6BC8E) is corrected append-only on the same session with consistent session, aggregate Forge and Research Fragments readback, without a new look, Critic or session.
managed_write_set:
- docs/tasks/HFIC_CLASSIFICATION_INPUT_RECOVERY_V1.md
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_representation_ladder.py
- src/solana_alpha_lab/factory/research_fragments.py
- scripts/hypothesis_forge.py
- tests/test_episode_native_required_outcome_contract_v1.py
- tests/test_hfic_one_frozen_runner_up_failover_v1.py
- tests/test_observation_fast_lane_p0_addendum.py
- docs/contracts/episode_native_required_outcomes_v1.md
- docs/operator/RESEARCH_FRAGMENTS_V1.md
- .agents/skills/hypothesis-forge/SKILL.md
- .cursor/commands/hypothesis-forge.md
- docs/evidence/hfic_classification_input_recovery_v1/**
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- EXACT_HEAD_CI_AND_MERGE_READINESS_THEN_OWNER_PHRASE_BEFORE_MERGE
- NO_REAL_C6_CORRECTION_OR_FRAGMENT_REGISTRATION_BEFORE_ACCEPTED_MERGE
- NO_NEW_MAIN_PREVIEW_ADAPTIVE_CRITIC_SESSION_OR_NUMERICAL_REPLAY
- NO_POLICY_PROTECTION_ASSIGNMENT_MONITORING_PLAN_OR_BUDGET_MUTATION
- NO_VPS_SCOUT_PROVIDER_TRADING_OR_HISTORY_CHANGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/episode_native_required_outcomes_v1.md
    - docs/contracts/forge_ordinary_operation_lifecycle_v1.md
    - docs/operator/RESEARCH_FRAGMENTS_V1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/hfic_classification_input_recovery_v1/completion.json
    - docs/evidence/hfic_classification_input_recovery_v1/independent-review.json
    - docs/evidence/hfic_classification_input_recovery_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# HFIC classification input refusal and C6 correction

Direct owner EXECUTE (2026-10-20) of the unified PRD+SSD
`SMIAL_C6_Classification_Recovery_PRD_SSD_2026-10-20` authorizes this one
connected atom. The attachment is the requirement source, not merge, scientific
or external authority. No duplicate PRD, SSD or plan document.

ENTRY: START_WITH_PATCH. SPEC_ROUTE: PRD_LITE (owner design exists).
Route/actor DIRECT_CLAUDE_CODE_DELIVERY/CLAUDE_CODE. MODEL_EFFORT_RECOMMENDATION:
SOL_XHIGH. CAPABILITY_RADAR_NOW: NONE. ADOPT the existing lane classifier,
`finalize_session`, ResearchStore append, session loader cycle ranking, aggregate
Forge ladder and fragment shelf. WRAP only a typed envelope refusal and one
proof-bound correction cycle. No new artifact kind, store, service or dependency.

DECISION_DELTA: a Spec envelope error stops before writes instead of closing a
scientific session; one recorded envelope refusal can be corrected on the same
session so the saved MAIN, Critic PASS and candidate reach their ordinary
classification, owner-final and advisory fragment. Named consumer: C6 session
HFIC-SESS-78F92D0FE3E6BC8E, candidate HFIC-CAND-07C58050FC7E, result
HFIC-ART-DISCOVERY-E6D9B0C5F86162A7CCB80D5AEC41B7530EE8CEC9.
UNCERTAINTY_REMOVED: input refusal vs verdict, eligibility proof of a recorded
refusal, field-bounded diff, same-session lineage, stale/duplicate apply,
aggregate completed-readback lift, fragment comparator vs pool.
CAPABILITY_OR_EVIDENCE: native fixture vertical through public CLI (refusal →
pending → correct classify; legacy refusal → preview → apply → cold bundle →
forge-run OWNER_CANDIDATE over persisted NON_SCIENTIFIC_STOP → shelf).
STOP: exact-head CI and merge readiness, then owner phrase. NEXT: after accepted
merge, real C6 preview/apply, forge-run persist, one CONTEXT_FILTER registration,
cold readback. REPLAN_TRIGGER: correction needs a new artifact form the
protection parser does not know, a change to question/recipe/result, a second
correction route, or a repeated blocker.

## Source closure (pre-patch)

Base a8ad00859b52e1c99c4926a549b708b62f4254c0, isolated worktree. No due active
time gate. Real C6 anchors read back from the canonical root: operation
f5d29815… COMPLETED (owner-final NON_SCIENTIFIC_STOP), session SYNTHESIS_COMPLETE,
classifier DENY_INVALID_SPEC / EXPERIMENT_SPEC_INVALID, MAIN=1 ADAPTIVE=0
PREVIEW=0. Cause: Spec `as_of` and `availability_cutoff` 14:30Z versus about
12:48Z evaluation. A read-only lane probe with both fields corrected gives
FAST_LANE_READY/COMPLETE (not a promise for the later apply). Protection
status ALLOW, REVALIDATED; the refused CRITIC_RESULT is a recognized declaration.
Native registration preview already admits the card (writes=false), so no shelf
admission code is added. The shelf `source_terminal` is read live from the
session. Recovery inputs and receipts are preserved outside Temp in
`local/forge_operator_results/c6-classification-recovery-inputs/` with SHA256SUMS.

## Design

- `lane_classifier.spec_input_refusal` returns a typed envelope refusal
  (stage, reason, fields). `_validate_spec` delegates to it. `classify_lane` is unchanged.
- `run_live_classifier` raises `CLASSIFICATION_INPUT_INVALID` before
  `classify_lane`/receipt/decision. `classify` prints one JSON object with
  actual writes. Other DENY reasons keep their semantics.
- `classification-correction-preview/-apply`: eligibility is proved from the
  store: original PASS, refused receipt equal to the stored one, the saved
  request still refused for an envelope reason at its own time, the diff
  limited to the named fields and outside question/recipe/binding keys, the
  corrected time not before the Critic PASS, and a fresh classifier on the
  original inputs. Apply binds parent receipt and proposal SHA, then reuses
  `finalize_session(classification_correction=…)`. It writes a next-sequence
  COMPLETE cycle with its own receipt ids and a correction-scoped git fence.
  The original preflight composite is retained.
- Session loader verifies the correction body hash and loads the receipt bound
  to the active cycle. Ladder lifts a completed readback only for a saved stage
  whose stage_ref equals the correction's refused session receipt.
- Fragment summary carries saved `research_scope`/`scientific_identity`.

Existing tests that used a future Spec to obtain a persisted classifier KILL now
use a bound-hash integrity mismatch (a real classifier deny). The P0b
future-Spec test asserts the stronger pre-write refusal.

Rollback: ordinary revert before any real correction. After a real correction
record, forward-fix only. The reverted loader would pick the first classifier
receipt for the corrected session.
