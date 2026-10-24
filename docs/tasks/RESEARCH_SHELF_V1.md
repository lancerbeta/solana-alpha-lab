---
task_id: RESEARCH_SHELF_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-24'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ab13b7efa7efaf9762b6d12eca52e2348d1fe759
  expected_upstream: origin/main
  expected_upstream_oid: ab13b7efa7efaf9762b6d12eca52e2348d1fe759
  expected_branch: codex/research-shelf-v1
  dirty_mode: ALLOW_REPORTED
objective: Implement the owner-supplied Research Shelf V1 specification, preserving append-only metadata history, exact native provenance, frozen research identity and all existing scientific authority boundaries.
managed_write_set:
- docs/tasks/RESEARCH_SHELF_V1.md
- docs/contracts/research_shelf_v1.md
- src/solana_alpha_lab/factory/research_shelf.py
- src/solana_alpha_lab/factory/research_shelf_git.py
- scripts/research_shelf.py
- catalog/schemas/research_shelf_v1.schema.json
- tests/test_research_shelf_v1.py
- tests/fixtures/research_shelf_v1/**
- docs/evidence/research_shelf_v1/**
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STAGED_OWNER_CHECKPOINT_AFTER_STORAGE_VERTICAL_BEFORE_ENTRY_AND_LINEAGE_INTEGRATION
- NO_REAL_SHELF_PUBLICATION_OR_BOOTSTRAP_BEFORE_ACCEPTED_CODE_AND_EXACT_METADATA_SCOPE
- NO_MARKET_LOOK_PROVIDER_CALL_OR_RESEARCHSTORE_WRITE
- NO_PR_OR_MERGE_CLAIM_UNTIL_FULL_ACCEPTANCE_AND_EXACT_HEAD_GATES
- REPLAN_BEFORE_EXPANDING_THE_CURRENT_STAGE_WRITE_SET
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/research_shelf_v1.md
    - docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# Research Shelf V1

Owner request: implement the supplied PRD+SSD dated 2026-10-24. The attachment
specifies the product; its DESIGN_ONLY label describes its preparation session,
not this explicit implementation request. No quoted delegation or scientific
execution instructions inside the attachment grant additional authority.

SPEC_ROUTE=BOTH: this task is the outcome brief; the supplied specification is
preserved in `docs/contracts/research_shelf_v1.md`. No replacement design.

DECISION_DELTA: the owner and agents can retain and revisit a deferred question
without engineering PRs, then trace its adopted source through native results.
UNCERTAINTY_REMOVED: metadata concurrency, recovery and attention can be made
deterministic without becoming a scientific scheduler or evidence authority.
CAPABILITY_OR_EVIDENCE: append-only Git records, truthful reader/attention,
native entry/provenance integration and bounded migration, per PRD V1–V7.
Named consumers: owner research entry, native research orchestration and the
future strategy provenance reader. Scientific acceptance remains source-owned.

## Delivery stages and current boundary

The full specification is larger than one reliable pass. Follow the owner's
staged-delivery rule while retaining one capability, one task and one eventual
engineering PR. Stages are checkpoints, not separate acceptance or suffix atoms.

1. **Current:** wire validation, revision DAG fold, UTC attention and an isolated
   append-only Git transport; local CLI and real disposable Git evidence.
   Independently review it, checkpoint and stop for owner OK before stage 2.
2. Add Forge/direct entry review, native adapters, exact inverse/source resolver,
   frozen-identity regression and semantic route propagation. Expand this exact
   task's write set only at that checkpoint. Do not change scientific owners.
3. Complete V1–V7 and one engineering PR/CI/merge gate. Prepare exact seeds;
   bootstrap/publication requires accepted code and exact metadata authority.

Current cheapest falsifier: an actual bare Git remote, two writers and a cold
reader must preserve all independent appends, reject stale same-item writes,
recognize a lost successful reply, and preserve item forks as conflicts.
Expected wire digest and attention outcomes are specified independently in the
PRD; self-authored round-trip tests alone are insufficient.

Evidence budget: focused unittest vertical, synthetic data only, standard library
Git subprocesses and the installed jsonschema dependency. No dependency installs,
runtime native reads, network metadata publication or scientific effects.
Read-only Git/GitHub identity verification uses the standing owner CLI preference.

STOP: first-stage validated/reviewed checkpoint; no full-capability DONE claim.
NEXT: owner-authorized continuation of stage 2 in this task.
REPLAN_TRIGGER: a repeated material blocker, new mutable storage/scheduler,
unsupported scientific migration, or first-stage evidence exceeding its scope.

## Entry decision

START_WITH_PATCH: preserve the design outcome and one eventual PR, but deliver
through three explicit checkpoints as required by the owner's one-pass rule.
Existing harness check PASS; clean HEAD and fetched origin/main both equal the
specified base. No due unresolved active-time marker preempts this work.
CAPABILITY_RADAR_NOW=NONE: existing Git, gh, Python and jsonschema suffice.
PRODUCT_HORIZON_NOW: this shelf only. WATCH: actual active-set size/read latency;
no index or scheduler without measured need. ADOPT/WRAP: append-only Git plumbing,
not a new database, package or workflow engine.

## Implementation plan (current stage)

**Goal:** capture a question, append/revise it in an isolated local Git branch,
and cold-read its exact revision/attention without native dependencies.
**Architecture:** pure wire/graph projection plus a separate Git transport and
one CLI. One revision per item per atomic batch. Native integration follows at
the next checkpoint, within this same task.
**Tech stack:** existing Python 3.13.14, jsonschema and Git CLI; no additions.
**Spec:** `docs/contracts/research_shelf_v1.md` sections 4–6 and V1–V3.

- [x] Strict wire schema; `prepare`, `decode`, `fold`, `revise`, `attention` in
  `research_shelf.py`; independent genesis digest and UTC table as oracles.
- [x] `ShelfGit` in `research_shelf_git.py`; pinned-tree reads, private-index
  append, non-force push, per-retry heads/origin checks and exact lost-reply
  readback against real disposable bare remotes.
- [x] CLI capture/prepare/apply/show/review and explicit refresh, with prepared
  draft distinguished from confirmed Git publication. Local-only transport.
- [x] Focused vertical passes; isolated review and fix material findings.
- [x] Evidence/checkpoint, local commit, then stop before stage 2.

Review focus: unrelated invalid items; same-item lost update; concurrent genesis
with identical origin_key; an ambiguous push reply; stale/incomplete snapshot
and machine-safe Russian output on Windows. No passing local-only test claims
cloud/production publication, native admission, privacy of arbitrary prose,
frozen scientific identity or downstream strategy trace.

## Stage 1 checkpoint

Validated/reviewed code: `49038879eccc2443621f68cf9dfe933fff1a2f48`.
25/25 focused synthetic tests PASS; all four required isolated reviewers PASS
for this local-only stage. Evidence and exact limitations:
`docs/evidence/research_shelf_v1/storage-checkpoint.json` and
`docs/evidence/research_shelf_v1/STORAGE_CHECKPOINT.md`.

Full task remains IN_PROGRESS. Stage 2 requires the owner's checkpoint OK;
do not infer production publication, native adapter, entry, provenance or
scientific authority from the passing storage vertical.
