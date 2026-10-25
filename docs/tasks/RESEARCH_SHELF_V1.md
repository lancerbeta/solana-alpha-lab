---
task_id: RESEARCH_SHELF_V1
task_version: '1.5'
status: IN_PROGRESS
as_of: '2026-10-25'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CODEX_DELIVERY]
required_review_roles: [CODE_REVIEWER, GOAL_DOD_CRITIC, ARCHITECTURE_CRITIC, OWNER_UX_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9adc2f4b5a57ac10db7102a7766ae42a3103fc5f
  expected_upstream: origin/main
  expected_upstream_oid: 9adc2f4b5a57ac10db7102a7766ae42a3103fc5f
  expected_branch: codex/shelf-wire-compat
  dirty_mode: ALLOW_REPORTED
objective: Repair Research Shelf V1 native URI and opaque mutation identity compatibility with Scout, preserving all published bytes, IDs, history and scientific authority.
managed_write_set:
- docs/tasks/RESEARCH_SHELF_V1.md
- docs/contracts/research_shelf_v1.md
- catalog/schemas/research_shelf_v1.schema.json
- tests/test_research_shelf_v1.py
- tests/fixtures/research_shelf_v1/**
- docs/evidence/research_shelf_v1/wire-compat/**
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/**
- docs/generated/**
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/FACTORY_SEMANTIC_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_AFTER_EXACT_HEAD_CI_AND_MERGE_READINESS_BEFORE_OWNER_PHRASE
- NO_REAL_SHELF_PUBLICATION_OR_BOOTSTRAP_BEFORE_ACCEPTED_CODE_AND_EXACT_METADATA_SCOPE
- NO_MARKET_LOOK_PROVIDER_CALL_OR_RESEARCHSTORE_WRITE
- NO_MERGE_BEFORE_EXACT_HEAD_CI_READINESS_AND_OWNER_PHRASE
- NO_CANONICAL_CAPABILITY_DONE_BEFORE_COMMISSIONING_ACCEPTANCE
- REPLAN_IF_SCIENTIFIC_SCHEMAS_OR_NEW_PLATFORM_ARE_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles: [ARCHITECTURE_DECISIONS, DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/contracts/research_shelf_v1.md
    - docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
    DELIVERY_EVIDENCE:
    - docs/evidence/research_shelf_v1/completion.json
    - docs/evidence/research_shelf_v1/independent-review.json
    - docs/evidence/research_shelf_v1/factory-fit.json
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

1. **Complete:** wire validation, revision DAG fold, UTC attention and an isolated
   append-only Git transport; local CLI and real disposable Git evidence.
   Independently review it, checkpoint and stop for owner OK before stage 2.
2. **Current, owner OK:** add Forge/direct entry review, native adapters, exact inverse/source resolver,
   frozen-identity regression and semantic route propagation. Expand this exact
   task's write set only at that checkpoint. Do not change scientific owners.
3. After accepted code and explicit metadata scope: bounded seed reconciliation,
   bootstrap/publication and cloud readback; joint Scout conformance acceptance.

Stage 1 cheapest falsifier: an actual bare Git remote, two writers and a cold
reader must preserve all independent appends, reject stale same-item writes,
recognize a lost successful reply, and preserve item forks as conflicts.
Expected wire digest and attention outcomes are specified independently in the
PRD; self-authored round-trip tests alone are insufficient.

Evidence budget: focused unittest vertical, synthetic data only, standard library
Git subprocesses and the installed jsonschema dependency. No dependency installs,
runtime native reads, network metadata publication or scientific effects.
Read-only Git/GitHub identity verification uses the standing owner CLI preference.

STOP: reviewed stage 2 engineering PR; no full-capability DONE claim.
NEXT: external validator on the published diff, then exact merge/metadata gates.
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

Full task remains IN_PROGRESS. Owner explicitly authorized stage 2 in the next
turn with the supplied validator addendum. The original checkpoint remains
immutable evidence; it grants no publication or scientific authority.

## Stage 2 owner addendum and plan

Owner OK: continue this exact branch/task; do not repeat stage 1 tests/reviews
without changed behavior. The validator's reported evidence is not independent
code acceptance; final external code review is on the eventual engineering PR.
Current code/main/route were revalidated; main is still the frozen base.

START_AS_WRITTEN with the validator's narrow amendments. SPEC_ROUTE=BOTH;
existing PRD remains authoritative for product meaning. No replacement design.

DECISION_DELTA: research entry sees a short trustworthy pinned shelf glance and
can resolve its retained question to exact existing native evidence/strategy.
UNCERTAINTY_REMOVED: metadata can cross the entry boundary without entering
scientific hash domains, granting execution or copying private Scout content.
CAPABILITY_OR_EVIDENCE: actual Forge/direct entry overlays, two bounded saved
source adapters, exact adopted revision/native/strategy resolver, privacy guard,
semantic navigation and focused synthetic verticals. STOP: reviewed stage 2
checkpoint and one eventual engineering PR; no merge/commissioning/seeds.
NEXT: exact-head delivery gates then separately scoped metadata commissioning.

- [x] Carry a hash-bound head observation through refresh -> exported snapshot
  -> pinned read. A bounded TTL describes cached observation freshness only.
  One top-level refresh; no ref movement or source adapters inside native run.
- [x] Attach a derived summary after Forge receipt hashing on success and every
  blocked/missing-root exit. Direct experiment/operator CLIs use the same reader.
  Frozen resume/RFV uses a separate metadata CLI and keeps frozen inputs.
- [x] Read SMIAL fragment/plan and exact Scout saved status through existing
  owners; MET/NOT_MET/UNKNOWN with acknowledgement and native expiry kept apart.
- [x] Add exact native links/inverse lookup, adopted immutable content, revoked
  links and retryable adoption keys. Strategy resolver starts at its exact
  source decision, validates manifest/direct passport/spec/lineage, never latest.
- [x] Publish only explicitly reviewed minimal public wording/pointers for a
  private origin; check the complete outgoing payload/dossier. An unapproved
  private-origin export is refused and leaves prepared bytes untouched.
- [x] Add one excluded reference-only semantic route, max_routes 13 -> 14 in
  config and schema; preserve every other limit and existing scientific owners.
  Register canonical Catalog owners and regenerate navigation with its generator.
- [ ] Exercise real entry, frozen identity, saved native->strategy lineage with
  two PROMOTE decisions, metadata-only link recovery, private sentinel and cold
  semantic/cloud read. Finish/review and prepare one engineering PR through
  existing preflight/CI gates; no operational data branch publication.

ADOPT/WRAP: existing native readers and promotion validators; Git metadata cache
is the only shelf storage. No new dependencies, DB, ACL engine, DSL or scheduler.
Freshness witness is a derived snapshot envelope, not an operational registry.
CAPABILITY_RADAR_NOW=NONE. MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH.

Measured navigation constraint: the 14-route resolved overview was 17804 bytes
against the unchanged 16384-byte limit. Keep one canonical operator root for
the shelf (it names config/CLI explicitly) and shorten the repeated Catalog
status disclaimer without changing its meaning/schema. Do not raise the byte
budget or remove existing route roots. The 14 existing canonical bindings stay.

Transport implementation delta: preserve the stage-1 local-only class/append
algorithm and wrap its destination seam for the exact public namespace. The
wrapper requires an explicit metadata scope plus accepted policy bytes on an
ancestor of origin/main, isolated cache, existing transport and whole-payload
public guard. Implementing/testing that refusal path grants no real refresh,
publication, bootstrap or commissioning. One engineering PR can therefore land
the implementation before the owner authorizes operational metadata use.

Delivery placement replan: preflight found historical shadow pins to AGENTS.md
and context-map.yaml in TASK21/TASK30 acceptance evidence. Preserve those root
control bytes and pins. The existing semantic front door resolves the new route;
Forge skill/command, actual machine CLI glances and native operator links carry
the shelf entry. No guard exemptions, historical retagging or new registry.

## External semantic REVISE on PR 422

Owner requests six bounded corrections on published head 55e7835b: fail-closed
identity reservations across unreadable history; historical private provenance;
exact saved Critic findings/non-claims in dossier; dated WAITING priority;
compatible hash-bound SOURCE_CHANGED baseline; scoped post-commission refresh
recipe with a separate local-only route. Keep one PR and architecture/authority.
Also propagate approved route count 14 to the execution-domain test consumer
identified by CI. Do not merge or request owner phrase before the new exact-head
checks and semantic review PASS. No real science, data/seeds or reminder writes.
CI repairs also create the owned disposable test parent in a clean checkout,
pin fragment-test administrative clock inside its synthetic fixed plan, and
update the explicitly current engineering CLI pin for the derived entry overlay.
Production expiry gates, scientific schemas and frozen historical pins remain.

## Current bounded repair: cross-product wire compatibility

Owner request, 2026-10-25: repair native URI and mutation_id compatibility
between Scout and SMIAL; preserve published IDs/history; prove both directions.
No data publication, scientific run or reminder change. Analysis and execution
are authorized in one bounded chain, with minimal sufficient vertical evidence.
Earlier implementation/commissioning stages above are historical context.

SPEC_ROUTE=NONE: clarify two existing wire fields in the canonical contract.
DECISION_DELTA: both readers accept already-published valid records unchanged.
UNCERTAINTY_REMOVED: separate green fixtures conceal real reader incompatibility.
CAPABILITY_OR_EVIDENCE: opaque stable mutation IDs in SMIAL; logical smial-data URI
support in Scout; bidirectional saved-byte decode/fold/attention and negatives.
STOP: reviewed engineering changes and exact-head CI/merge readiness; no merge
without a new exact owner phrase, no data pushes, native rebind or full DONE claim.
NEXT: owner reviews concrete code candidates; remaining native UNKNOWN stays.
REPLAN: any need for rewriting IDs/history, new dependencies, scientific schema,
runtime/scheduler changes or broader scientific execution is out of scope.

Design choice: extend readers rather than migrate immutable records. mutation_id
is a nonblank opaque string compared exactly; no trim/reformat and no new length
limit beyond the existing revision budget. Existing UUID generation stays.
Scout accepts the actually emitted smial-data logical URI plus prior relative
locators, retains physical/control/path refusal and never dereferences the URI.
No shared package, adapter service, registry, URI resolver or schema-version bump.

Plan: (1) freeze existing code/data pins and task contracts; (2) one focused
SMIAL schema/test change plus independent Scout helper/test change; (3) run both
readers on the same synthetic vertical and locally saved 2 SMIAL + 5 Scout records,
checking unchanged bytes/IDs, invalid-history reservations, conflicts and physical
path negatives; (4) proportional reviews and existing engineering delivery gates.
No TDD order/new broad suite requirement; no scientific fixtures/evaluators needed.

Pinned data remains SMIAL a6f03eb9d81adc93f828b994eea7525814dfa12b and
Scout d440b1444741b09e6ed3575bdeba1701b8785e70. Private Scout bodies stay local;
only synthetic portable fixtures and sanitized hashes/counts enter this public PR.
Source audit: local/research_shelf_v1/commissioning/acceptance/acceptance-receipt.json
in the original checkout, hash 6ed0c4b29216809e928743a19d0434c230b0dac31ddb609867cc260b82b0d83c.
New tooling=NONE; existing validators, CLI, Git/gh and independent critics suffice.
