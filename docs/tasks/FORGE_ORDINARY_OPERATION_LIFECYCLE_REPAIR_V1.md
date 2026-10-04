---
task_id: FORGE_ORDINARY_OPERATION_LIFECYCLE_REPAIR_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-04'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CLAUDE_CODE_DELIVERY
required_review_roles:
- CODE_REVIEWER
- GOAL_DOD_CRITIC
- ARCHITECTURE_CRITIC
- OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: fc3db6cf164d73b1289bda8472c21f3d4e3edea7
  expected_upstream: origin/main
  expected_upstream_oid: fc3db6cf164d73b1289bda8472c21f3d4e3edea7
  expected_branch: claude/forge-ordinary-operation-lifecycle-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  An ordinary Forge operation can finish or be cancelled through the public
  path so a terminal or abandoned run no longer blocks the research-universe
  profile forever, without a new verdict, quota reset or store edit; a
  predictable universe-preview refusal is decided before market values load.
managed_write_set:
- docs/tasks/FORGE_ORDINARY_OPERATION_LIFECYCLE_REPAIR_V1.md
- docs/contracts/forge_ordinary_operation_lifecycle_v1.md
- docs/contracts/forge_research_universe_policy_v1.md
- src/solana_alpha_lab/factory/hfic_ordinary_operation.py
- src/solana_alpha_lab/factory/hfic_research_universe_policy.py
- scripts/hypothesis_forge.py
- .agents/skills/hypothesis-forge/SKILL.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_forge_ordinary_operation_lifecycle_v1.py
- tests/test_forge_research_universe_policy_v1.py
- tests/test_hfic_ordinary_operation_v1.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/forge_ordinary_operation_lifecycle_repair_v1/a1_delivery_completion_evidence_v1.json
- docs/evidence/forge_ordinary_operation_lifecycle_repair_v1/a1_delivery_independent_review_v1.json
- docs/evidence/forge_ordinary_operation_lifecycle_repair_v1/a1_delivery_factory_fit_v1.json
- docs/evidence/forge_ordinary_operation_lifecycle_repair_v1/a1_semantic_premise_packet_v1.json
- docs/reports/forge_ordinary_operation_lifecycle_repair_v1/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_LIVE_RESEARCH_STORE_MUTATION_IN_PHASE_A
- STOP_NEW_SCIENTIFIC_VERDICT_OR_FABRICATED_NEGATIVE
- STOP_QUOTA_RETURN_RESET_OR_NEW_JOURNAL
- STOP_HISTORY_DELETE_OR_REWRITE
- STOP_C5_OR_PROTECTED_CORPUS_READ
- STOP_PROVIDER_RPC_OR_NEW_COLLECTION
- STOP_WALLET_SIGNER_OR_REAL_TRADE
- STOP_NEW_SERVICE_LOCK_OR_STORAGE
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids:
  - MODULE-FACTORY-V1-RESEARCH-STORE-001
  - DOC-HYPOTHESIS-FORGE-OPERATOR-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - src/solana_alpha_lab/factory/hfic_ordinary_operation.py
    - src/solana_alpha_lab/factory/hfic_research_universe_policy.py
    - src/solana_alpha_lab/factory/hfic_representation_ladder.py
    - docs/contracts/forge_research_universe_policy_v1.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# FORGE_ORDINARY_OPERATION_LIFECYCLE_REPAIR_V1

ENTRY_DECISION: START_AS_WRITTEN. MODEL_EFFORT: SOL_XHIGH.
Factory Fit: FULL_REVIEW. SPEC_ROUTE: DESIGN_SPEC (contained here; public
semantics land in `docs/contracts/forge_ordinary_operation_lifecycle_v1.md`).
Reuse: WRAP the existing ordinary-operation owner, the persisted
`FORGE_RUN_RECEIPT` owner-final artifact and the ResearchStore writer lease.
No new store, verdict, journal, lock service or provider.

## Task outcome

- DECISION_DELTA: a finished or abandoned ordinary operation stops holding
  the universe-profile gate; the owner has one exact, owner-authorized stop
  and one idempotent reconcile instead of an unbounded "finish the
  operation" with no executable action.
- UNCERTAINTY_REMOVED: whether a SCIENTIFIC_TERMINAL operation can ever
  leave OPEN, and whether cancellation can be told apart from a scientific
  result while quotas and history stay intact.
- CAPABILITY_OR_EVIDENCE: one effective-state owner in
  `hfic_ordinary_operation`, consumed by readback, admission, policy
  status/preview/apply; public `operation-stop-preview` /
  `operation-stop`; preview refusal decided before the value loader.
- Consumer: operator; `forge-run --no-write`; universe policy
  status/preview/apply; ordinary discovery execute/preview; replay/resume;
  the next bounded research run.
- Cheapest falsifier: after a real production-composed SCIENTIFIC_TERMINAL
  run reaches a persisted owner-final, the universe apply is still refused;
  or a stop changes a verdict, frees quota, or lets a new look start.
- STOP: exact-head CI plus `ready_for_owner_phrase=true`. No live store
  mutation in this phase.
- NEXT: phase B OPERATE after guarded merge and post-merge readback, in the
  exact scope of the owner document.
- REPLAN_TRIGGER: completion cannot be verified from existing artifacts
  without a new verdict record; a stop needs a new lock service; the same
  blocker repeats after one owner-level repair.
- Evidence budget: disposable production-published synthetic corpus,
  public CLI only; no real C1–C4 outcome read.
- Product horizon / capability radar NOW: NONE.

## Root cause (observed 2026-10-04 on the live store, read-only)

`hfic_ordinary_operation` writes `OPEN` and, only for `LIMITED_RESULT`,
`OPEN → PAUSED_CAP`. Nothing ever writes a later state for
`SCIENTIFIC_TERMINAL`; readers already expect `STOPPED`. The universe gate
counts every persisted `OPEN`. Live result: one operation with a persisted
`SEARCH_EXHAUSTED_CURRENT_EVIDENCE` owner-final receipt and two unfinished
operations that themselves need an active profile kept apply refused
(`UNIVERSE_POLICY_PENDING_OPERATION`, writes 0). The documented "finish it
or stop it" had no executable stop. Second seam: `universe-policy-preview
--decision-point` loaded and counted values before the preview-allowance
refusal and then reported `values_loaded=false`.

## Design

1. Effective state is derived by one owner, never by a second verdict:
   - `STOPPED` — a persisted owner stop of this exact operation;
   - `PAUSED_CAP` — unchanged;
   - `COMPLETED` — a `SCIENTIFIC_TERMINAL` operation whose bound run has a
     persisted `FORGE_RUN_RECEIPT` with `owner_class=OWNER_FINAL`, recorded
     at or after the operation, for the same scientific slot, market epoch
     and focus, whose BASE stage session carries the operation journal;
   - otherwise `OPEN`.
   Focus name, UI wording or an absent process are not completion. An
   older-market operation is never matched to a current-market readback.
2. `forge-run --persist` is the existing idempotent reconcile: it records
   the owner-final receipt when the run is final; an unfinished run writes
   no owner-final and stays `OPEN`.
3. Owner stop: read-only `operation-stop-preview` then
   `operation-stop --proposal --confirm-append-only`, available without an
   active profile. The proposal binds the exact operation, its latest
   record and the owner text. Apply re-checks under the writer lease.
   Stop writes no verdict, keeps results, reservations and spent looks,
   and refuses a `COMPLETED` operation. After stop no new look, preview or
   resume is admitted; saved results stay replayable.
4. Every operation-state append is compare-before-append so a late
   landing or fingerprint stamp cannot resurrect `OPEN` after a stop.
5. Universe status/preview/apply read the effective state and name each
   blocking operation with its next action. Apply re-checks pending state
   under the writer lease. A predictable preview refusal is decided before
   any value read; a refusal after a read reports `values_loaded=true`.

## Non-goals

Historical `60FB3DA7…` conflict, `NOT_RECORDED` backfill, new limits, C5
management, worktree cleanup, UI, caching, generator/ML, services,
libraries, live store recovery (phase B, separate scope).

## Acceptance

| ID | Prove on the public production path |
|---|---|
| R1 | Saved owner-final receipt + persisted OPEN: readback shows COMPLETED, the profile gate is free, refs/verdict unchanged |
| R2 | Unfinished operation: owner stop without a profile works; without confirm, owner text, or with an unknown/stale id it is refused; no NO_WORTHY, no quota return |
| R3 | 50/5k → real SCIENTIFIC_TERMINAL cycle → cold readback → 50/20k → next cycle → readback, without repair or manual status |
| R4 | LIMITED_RESULT keeps PAUSED_CAP; an OPEN operation blocks apply; after stop no resume/new look/preview |
| R5 | Repeated stop/reconcile adds nothing; a stale proposal is refused at apply; a late landing cannot resurrect OPEN |
| R6 | A predictable preview refusal does not call the value loader; missing profile keeps history readable |
| R7 | Foreign market/journal/receipt, a non-final receipt or a pre-operation receipt does not complete the operation; A→B→A keeps budget |

Rollback: before live lifecycle records, an ordinary revert. After live
stop records exist, keep the reader (older code would read `STOPPED` as not
`OPEN` already); never delete data-plane history.
