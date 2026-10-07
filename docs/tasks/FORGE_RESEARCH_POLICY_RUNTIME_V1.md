---
task_id: FORGE_RESEARCH_POLICY_RUNTIME_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-07'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 04ec8e0286a3dce5999d0687784717ee90fc5dca
  expected_upstream: origin/main
  expected_upstream_oid: 04ec8e0286a3dce5999d0687784717ee90fc5dca
  expected_branch: claude/forge-research-policy-runtime-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Give the owner a runtime-configurable Forge research policy (MAIN/ADAPTIVE/
  PREVIEW totals, AUTO-cycle and distinct-focus caps, candidate and
  diagnostic-slice ceilings, presets) stored in the existing ResearchStore,
  with one effective-limits resolver reaching every real consumer (the
  ordinary-operation gate, temporal/query classification, AUTO admission,
  the candidate draft and session-receipt schemas), frozen per-journal
  snapshots on first touch, explicit per-journal extensions that never reset
  spend, and 10 real candidates through the ordinary freeze/Critic/finalize
  lifecycle — without raising any shipped default and without touching VPS,
  canary, deploy, provider routing or real science.
managed_write_set:
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/schemas/hypothesis_forge_draft_v1_3.schema.json
- catalog/schemas/hypothesis_forge_session_receipt_v1_4.schema.json
- docs/contracts/forge_research_policy_runtime_v1.md
- docs/tasks/FORGE_RESEARCH_POLICY_RUNTIME_V1.md
- docs/evidence/forge_research_policy_runtime_v1/**
- scripts/hypothesis_forge.py
- src/solana_alpha_lab/factory/hfic_grounded_discovery.py
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
- src/solana_alpha_lab/factory/hfic_research_policy.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/hfic_temporal_discovery.py
- src/solana_alpha_lab/factory/live_cohort_to_forge.py
- tests/test_hfic_research_policy_v1.py
- tests/test_hfic_research_policy_vertical_v1.py
- tests/test_hfic_search_budget_epoch_guard_v1.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_MERGE_DEPLOY_SETTINGS_TIMER_CHANGES
- STOP_VPS_PROVIDER_CALLS_NEW_CREDENTIALS_OR_SECRET_ACCESS
- STOP_PRODUCTION_DATA_REAL_SCIENTIFIC_LOOK_OR_HOLDOUT_VALUES
- STOP_NEW_COLLECTOR_EVALUATOR_DATABASE_SERVICE_OR_DEPENDENCY
- STOP_SHIPPED_DEFAULT_RAISED_FOR_PRODUCTION
- STOP_LIVE_BUDGET_RAISE_RETENTION_OR_CLEANUP
context_requirements:
  catalog_asset_ids: [MODULE-HFIC-TEMPORAL-DISCOVERY-001, MODULE-HFIC-PREFLIGHT-ADMISSION-001]
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
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
    - docs/contracts/forge_research_policy_runtime_v1.md
    - docs/contracts/forge_list_aware_research_scope_v1.md
    DELIVERY_EVIDENCE:
    - docs/evidence/forge_research_policy_runtime_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/forge_research_policy_runtime_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/forge_research_policy_runtime_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FORGE_RESEARCH_POLICY_RUNTIME_V1

ENTRY_DECISION: START_AS_WRITTEN (PR-B of the List-aware Forge program,
following merged PR-A `FORGE_LIST_AWARE_RESEARCH_VERTICAL_V1` at
`04ec8e02`). SPEC_ROUTE: owner PRD/SSD
`SMIAL_PR_B_Forge_Research_Policy_Runtime_V1_PRD_SSD_2026-10-07` plus this
contract. Route DIRECT_CLAUDE_CODE_DELIVERY, actor CLAUDE_CODE.
MODEL_EFFORT_RECOMMENDATION: SOL_XHIGH for the policy/CAS/concurrency design,
LUNA_MAX for the mechanical consumer-wiring. Authority: the owner's explicit
2026-10-07 instruction naming this atom; design anchor `04ec8e02` equals
`origin/main` at Entry.

DECISION_DELTA: the owner can raise MAIN/ADAPTIVE/PREVIEW/AUTO/distinct-focus/
candidate/diagnostic-slice ceilings for new runs and for one exact journal,
through the ordinary ResearchStore, without a code change or redeploy, and
without resetting what any run has already spent.
UNCERTAINTY_REMOVED: whether every real budget-and-admission gate already
reached by a hardcoded constant (`MAX_MAIN_QUERY_SPECS`, `MAX_ADAPTIVE_
REFINEMENTS`, `MAX_PREVIEW_SPECS`, `SIMPLE_MAIN_RESERVE`, `AUTO_SESSIONS_PER_
EPOCH`, `MAX_DISTINCT_FOCUSES_PER_EPOCH`, `MAX_CANDIDATES`) can be re-pointed
at one effective-limits resolver without changing any shipped behavior for a
journal that never touches the new owner; and whether the AUTO admission
counter was a real per-epoch count or a saturating `int(any(...))` that could
never produce a genuine 1→2 raise.
CAPABILITY_OR_EVIDENCE: `hfic_research_policy` (one owner, three CAS
surfaces), the `research-policy` CLI (`show/preview/apply/extension-preview/
extension-apply`), the additive draft `packet_version "1.3"` and session-
receipt `v1_4` schemas, and a production-shaped micro-vertical.
Cheapest falsifier (exact base, before any change; `V0`): a 7th real
synthetic MAIN query is denied (`QUERY_MAIN_BUDGET_EXHAUSTED`) even with
`owner_cap.main=10`; the draft schema rejects a 10-candidate packet
(`candidates.maxItems=6`, `display_ordinal.maximum=6`); no `research-policy`
command exists in the CLI. FALSIFIER_AFTER: the same three boundaries are
served by the owner, verified in `test_hfic_research_policy_vertical_v1`.
A second falsifier found *during* delivery, not anticipated by `V0`: the AUTO
admission counter inside `decide_preflight_action`/`epoch_search_budget_usage`
hardcoded its own copy of `AUTO_SESSIONS_PER_EPOCH` and counted
`int(any(auto_session))`, which saturates at 1 regardless of how many
distinct AUTO journals exist in the epoch — so even with the parameter
threaded in from `resolve_scientific_admission`, no policy raise could ever
produce a real second AUTO admission. Fixed in the same PR (B08).

Required invariants: a journal's frozen snapshot never moves from a bare
active-policy change, only from an explicit extension of that exact journal;
an extension never resets what is already spent (spend stays owned by
`hfic_ordinary_operation.py`, computed from recorded looks/reservations, not
by this module); a legacy journal this owner has never touched reads the
shipped defaults and writes nothing; no field may exceed its hard fuse; a
bare pure-function caller of `classify_temporal_look`/`classify_query_look`/
`decide_preflight_action`/`epoch_search_budget_usage` without the new
`limits` kwarg is byte-for-byte unchanged.

DoD: PRD B01-B09 as relevant to PR-B: owner-settable MAIN/ADAPTIVE/PREVIEW/
AUTO/distinct-focus/candidate/diagnostic-slice limits with hard fuses;
CAS-protected active-policy apply never blocked by an open operation;
per-journal frozen snapshot on first touch; explicit per-journal extension
that never resets spend; a real 7th-10th MAIN executing through the
production gate once raised, with the 11th denied before any value load; a
fresh ResearchStore handle and a moved root both reading durable state, not
anything held in process memory; a real AUTO 1→2 cycle, not a fake
saturating increment; 10 real candidates (primary ordinal 9, runner-up
ordinal 10) through persist/freeze/two-stage-Critic/finalize to
`SYNTHESIS_COMPLETE`; a malformed policy delta refused before any write; a
last-slot race between two concurrent writers converging on exactly one
winner for both the snapshot first-touch and the extension CAS surface; a
legacy journal unchanged at 6/2/2/3/6.

Non-goals: raising a shipped default for production use; VPS/canary/deploy/
provider routing changes; real scientific looks; a new collector, evaluator,
database, service or dependency; reopening PR-A's list-aware scope; a new
prompt version (draft `packet_version "1.3"` carries the same `HFIC-V1.2`
prompt, only a wider structural candidate ceiling).
Reuse/build: WRAP the existing `hfic_research_universe_policy.py` CAS/
ResearchStore pattern for the active-policy owner; ADOPT the existing
`_reserve`-style `WRITER_BUSY` retry/backoff for the new owner's own CAS
writes; the only new module is the policy owner itself. No dependency.
Risks: a consumer left on its old hardcoded constant (guarded by the
explicit consumer-wiring list and the regression sweep across every touched
module); a frozen snapshot silently drifting with the active policy
(guarded by the dedicated "active-policy-does-not-move-an-existing-journal"
tests); lock contention during a race surfacing as a raw store error instead
of a typed refusal or a retry (guarded by the two-thread last-slot tests).
Rollback: owner-gated code revert; a `FORGE_RESEARCH_POLICY_V1`/`_RUN_
SNAPSHOT_V1`/`_RUN_EXTENSION_V1` record is plain JSON in ResearchStore and
stays readable; an older reader that never calls this module keeps reading
the shipped defaults it always read.
STOP: merge boundary; never merge in this atom.
NEXT: exact-head CI, merge-readiness, owner phrase.
REPLAN_TRIGGER: a second blocker at the same seam after an owner repair, or
scope reaching a stop condition.
FACTORY_FIT_REVIEW: FULL_REVIEW. PRODUCT_HORIZON_RADAR NOW=NONE.

Required reviews: isolated code, goal/DoD, architecture (semantic premise
packet; must name what can pass tests and still break research validity —
see the contract's three owner-separation invariants) and owner-UX (the new
`research-policy` CLI surface and its refusal next-actions).
