# T27-A0-A6 — Exact owner external-read review: design

## Purpose

`T27-A0-A6_EXACT_OWNER_EXTERNAL_READ_REVIEW_V1` prepares the smallest
offline, machine-checkable review packet that lets the owner decide whether a
future public history request is specified well enough to consider. It does
not make a request, select a live pool, contact a provider, or retain any
provider data.

The resulting packet is a review gate, not a permission slip. Its only useful
positive result is `READY_FOR_OWNER_EXTERNAL_READ_DECISION`; that result keeps
`provider_read_authority=false` and requires a later, separate exact owner
instruction before any GET.

## Why this atom exists now

A4 froze the sole source candidate, Source-smoke prerequisite and maximum
capture shape. The owner has since attested the Source smoke, so the remaining
safe question is no longer whether the Source set is aligned. It is whether a
future request can be shown to the owner without silently filling in its most
important facts or widening the limits.

There is deliberately no actual pool address, frozen selection snapshot, or
provider response in the repository. A6 must preserve that absence. It must
not turn a synthetic snapshot fixture into a real market target.

## Chosen approach

Create one bounded review contract, config, JSON Schema, synthetic fixture,
deterministic test module and acceptance receipt. The packet has three review
outcomes:

- `READY_FOR_OWNER_EXTERNAL_READ_DECISION`;
- `REDESIGN_EXTERNAL_READ_PACKET`; or
- `CLOSE_PUBLIC_HISTORY_ROUTE`.

The positive outcome means only that the packet clearly identifies the facts
which a later owner instruction must supply. It does not set authority to
true, choose a pool, grant a fallback source, or authorise collection.

## Required packet semantics

The contract must bind all of the following:

1. `ACTIVATION_CONFIRMED_USER_SMOKE` and the exact A5R1 activation receipt;
2. the A4 source candidate
   `GECKOTERMINAL_PUBLIC_POOL_OHLCV_CANDIDATE`, with no fallback provider;
3. immutable inherited limits: at most 6 discovery and 24 OHLCV reads,
   15-minute intervals, 24-hour panels and at least 12 complete panels;
4. a future-request identity plus explicit `OWNER_INPUT_REQUIRED` placeholders
   for the actual pool identity, selection-snapshot ID/SHA/time, universe and
   expected raw-evidence manifest;
5. an owner-decision statement, one consumer and a copyable future approval
   phrase that is invalid until every placeholder is filled;
6. retention distinction: A6 retains zero provider responses; any future
   successful or failed capture follows A4's raw-evidence and failure-receipt
   policy;
7. exact non-claims for PIT admissibility, alpha, strategy, quote, fill,
   execution, PnL, NetReturn and owner cashflow.

No field may claim `provider_read_authority=true`, treat a missing datum as
zero, approve an unbounded endpoint, or represent a review template as a
completed provider request.

## Fail-closed checks

The deterministic validator must accept one complete synthetic review template
and reject at least these cases:

- current provider authority asserted as true;
- a provider/API/RPC/WSS call, credential, raw response or raw retention in
  this atom;
- an actual pool or snapshot presented as verified external evidence;
- an empty owner-input placeholder or a mutable/unbound future request;
- fallback-provider, excess-read, interval, panel or threshold widening;
- a missing Source-smoke binding or a false readiness claim;
- a review result that says PIT, alpha, execution, fill, PnL, NetReturn or
  cashflow; and
- an approval phrase that is treated as valid before the exact later request
  is filled and separately approved by the owner.

## Files and responsibilities

- `docs/contracts/task27_exact_owner_external_read_review_contract_v1.md` —
  human-readable decision, inherited bounds and non-authority rule.
- `configs/task27_exact_owner_external_read_review_contract_v1.yaml` —
  machine-readable fields, caps, statuses and placeholder policy.
- `catalog/schemas/task27_exact_owner_external_read_review.schema.json` —
  structural review-packet schema only; no root Catalog registration.
- `tests/fixtures/task27/exact_owner_external_read_review_v1.json` — valid and
  adversarial synthetic packets; never market values or raw responses.
- `tests/test_task27_exact_owner_external_read_review_contract.py` —
  deterministic structural and semantic checks.
- `docs/evidence/task27/a0a6_exact_owner_external_read_review_acceptance_v1.json`
  — artifact hashes, test receipt, zero-side-effect accounting and
  `project_sources_disposition=NO_CHANGE`.

The design and plan files in `docs/superpowers/` record engineering intent;
they are not Project Sources, Catalog assets or external authority.

## Validation and delivery

Write the negative test first and observe it fail because A6 assets do not yet
exist. Implement only the listed files until the targeted test passes. Before
the first push, run the repository's one tracked-only full delivery gate for
the exact committed candidate; then create one Draft PR and read its CI back.

No dependency, Catalog, registry, Source-release, wallet, signer,
transaction, cash, provider or raw-data action is in scope. Ordinary revert
of the isolated branch is the rollback path if the review semantics prove
inadequate. The permitted product outcome is `REDESIGN_EXTERNAL_READ_PACKET`,
not an exploratory external request.
