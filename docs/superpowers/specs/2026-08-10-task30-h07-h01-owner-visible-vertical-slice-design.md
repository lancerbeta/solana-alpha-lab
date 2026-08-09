# TASK-30 H07/H01 owner-visible vertical slice — design

## Status and durable re-entry

- Design status: `DESIGN_REVIEW_REQUIRED`.
- Selected atom: `T30-A7_H07_H01_OWNER_VISIBLE_VERTICAL_SLICE_V1`.
- Base main: `6efa3b199f38a52864eadcf035a8cc8568dafb51`.
- Base tree: `4c0c2ba65496fb061d2e00daca2d0cc9917ba7f6`.
- Entry verdict: `START_WITH_PATCH`.
- Primary control plane: `LOCAL_WORK_PRIMARY`.
- Repository route: `LOCAL_WORK_CODEX`.

New-thread rule: read this design, current `AGENTS.md`, the active Project
Sources release registry, TASK-28's RC-001 freeze and T30 A1-A6 receipts.
Continue this atom instead of opening another generic provider-read or
forward-capture atom. Historical A1-A6 evidence is retained and never
rewritten.

## Owner outcome

The first visible product result is not another transport receipt. It is one
Russian-language owner readout answering:

1. What exactly does H07/H01 claim?
2. Which existing evidence can test it, and which facts are still missing?
3. Is any bounded diagnostic honest now?
4. If not, what is the smallest named acquisition that can change the
   decision?
5. What is the one next action and what claim remains forbidden?

This shortens the path from frozen hypothesis to evidence-backed owner
decision. It does not promise positive alpha.

## Why the current next boundary is patched

T30 A6 describes one pool, one closed 15-minute observation per slot and at
most 96 slots over 24 hours. That is useful only as a possible transport
shakedown. It cannot by itself satisfy the frozen H07/H01 definition, which
requires:

- point-in-time liquidity-retention state;
- multi-notional route persistence;
- post-migration continuation context;
- comparison against a named baseline under the same PIT window; and
- settled execution truth before numeric NetReturn or full trial acceptance.

Therefore `EXACT_PROVIDER_SELECTION_AND_24H_CAPTURE_GATE_REQUIRED` is not the
immediate product step. A provider can be selected only after this atom proves
that a named acquisition has decision value.

## Considered approaches

### Selected: decision-first vertical slice

Bind the frozen H07/H01 estimand to an executable offline evidence inventory,
admissibility result and owner readout. Reuse existing evidence first. Open one
provider-specific gate only if the inventory proves a material gap that a
bounded acquisition can actually close.

This is the cheapest route to a visible, falsifiable product result and avoids
building collection capacity without a sufficient consumer contract.

### Rejected now: continue the one-pool 24-hour capture as the main goal

It may prove cadence and storage, but one pool cannot establish matched
cohorts or incremental route-retention effect. A successful capture could
still leave the hypothesis blocked.

### Rejected now: generic multi-provider history platform

It increases integration, monitoring and maintenance before the first trial
has named a sufficient dataset. Existing provider adapters remain reusable
inputs; no new platform is justified.

## Truth owners and inputs

The implementation consumes, without rewriting:

- `configs/task28_rc001_registry_freeze_v1.yaml`, group
  `RC001-H07-H01-LIQUIDITY-RETENTION`;
- TASK-27's accepted `33/96` history result with `63 MISSING_UNKNOWN`;
- TASK-17A/TASK-19 quote-only PIT evidence where its exact scope permits;
- TASK-25/TASK-26 outcome and execution non-claims;
- TASK-26B's missing owner attempt, inventory and settlement truth;
- T30 A1-A6 boundary, reuse, provider and route-hold receipts;
- Project Asset Catalog stable IDs and current lifecycle records.

Absence in a global registry is `CATALOG_GAP` or `MISSING_UNKNOWN`, never proof
that a task-owned frozen definition does not exist.

## Execution shape

The canonical task remains TASK-30. This atom is staged internally but uses
one task branch and one final delivery. Internal stages are not separate owner
approval ceremonies.

### Stage 1 — offline evidence/admissibility slice

Build one deterministic evaluator that resolves the frozen definition and
named evidence, then classifies every requirement as:

- `SUPPORTED`;
- `LIMITED_DIAGNOSTIC_ONLY`;
- `MISSING_UNKNOWN`; or
- `UNSUPPORTED`.

It must reject:

- one-pool price coverage promoted to matched-cohort evidence;
- quote promoted to fill or settlement;
- missing interval promoted to zero or no-trade;
- a provider response promoted to PIT admissibility without availability and
  ingestion time;
- a diagnostic promoted to an H07/H01 trial or numeric NetReturn.

Stage 1 produces the first owner readout even when the decision is negative.

### Stage 2 — conditional named acquisition

This stage exists only if Stage 1 returns `CAPTURE_REQUIRED` and identifies an
acquisition that can close a named requirement. Its contract must bind one
provider surface, exact fields, cohort/watchlist rule, time window, cadence,
request cap, retention path, quality threshold and stop conditions.

Credentialed provider/API/RPC/WSS execution remains a separate exact owner
authority gate. No retry, fallback or provider substitution is inferred.

### Stage 3 — diagnostic or trial

- `LIMITED_DIAGNOSTIC_ONLY` may produce descriptive coverage, route
  availability and missingness results. It cannot select/promote a strategy or
  claim alpha/NetReturn.
- A selection-affecting H07/H01 run is a trial and must be append-only in the
  existing research lifecycle/ledger.
- Full trial admissibility requires the frozen comparison surface and the
  execution-truth boundary specified by TASK-28/TASK-26. The holdout remains
  unopened until its own accepted gate.

## Decision contract

The atom returns exactly one of:

- `RUN_LIMITED_DIAGNOSTIC`;
- `CAPTURE_REQUIRED`;
- `REDESIGN_DATA`;
- `CLOSE_ROUTE`.

Only a later admissible trial may return a hypothesis result. None of these
values grants provider, wallet, signer, transaction, cash, strategy-promotion
or TASK-30 completion authority.

## Minimum implementation surface

Implementation should add only what is needed for the executable slice:

1. one task-level contract/config surface;
2. one deterministic evaluator and thin CLI/read-model entry point;
3. focused tests with synthetic/adversarial cases;
4. one owner-readable Markdown or text report plus structured JSON;
5. one acceptance receipt;
6. Catalog/generated propagation once, at the task-level terminal delivery.

Do not create a new schema, fixture family, ADR, generic adapter, dashboard,
database or additional design/plan document unless a concrete validator or
consumer cannot function without it.

## Owner readout format

The report must lead with the outcome and stay understandable without opening
code:

```text
Question
Decision and evidence class
What data was actually used
What is still missing
What can and cannot be concluded
One next action
```

A compact table or static chart may be added only when it explains a real
comparison. A web UI is out of scope.

## Validation and delivery economy

- Targeted unit/adversarial tests during implementation.
- Secret scan and Catalog/generated checks only when their owned surfaces
  change.
- One tracked-only/full gate owner for the unchanged delivery candidate.
- One branch and one PR for the complete bounded slice.
- Project Sources are changed only if TASK-30 reaches a canonical terminal
  outcome; intermediate atoms remain Git/Catalog evidence.
- A failed invariant is repaired inside the same bounded branch without a new
  design/spec approval loop unless scope, estimand, data contract or safety
  changes materially.

## Scope exclusions

This design authorizes no provider/API/RPC/WSS request, key use, raw external
write, R2/R3 value read, holdout consumption, wallet, signer, transaction,
cash spend, deployment, strategy promotion, numeric NetReturn or TASK-30
acceptance. No generic collector, scheduler, multi-provider abstraction,
Context Capsule service, graph database, dashboard or admin UI is built.

## Recovery and invalidation

- If a referenced evidence hash or frozen definition changes, stop with
  `SOURCE_BINDING_CONFLICT`; do not silently rebase the estimand.
- If no bounded acquisition can close a named requirement, return
  `REDESIGN_DATA` or `CLOSE_ROUTE` instead of collecting more.
- If provider access later fails, preserve the typed failure and return to the
  same decision surface; do not retry automatically.
- If implementation requires more than the minimum surface above, re-run the
  scope check before adding infrastructure.

## Product horizon

`NOW`: deliver the first owner-visible H07/H01 evidence decision through this
vertical slice.

`WATCH`: before any wallet/signer material or unattended external runtime,
add the bounded Solana-specific secret and runtime-capability safety patch.
The Context Capsule remains deferred while Catalog plus this report answer the
owner question without repeated reconstruction.
