# T30-A9 — Named partial PIT and route-capture contract: Design

## Status and decision

**Status:** design approved by owner; implementation is not approved yet.

**Recommended design:** prepare one offline, provider-neutral owner packet for
a 24-hour **technical data-route pilot**.  The pilot's reference subject is the
previously identity-checked Solana pool
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, but its role is strictly
`TECHNICAL_DATA_ROUTE_PILOT`, not an H07/H01 population, trial, strategy or
economic observation.

The packet must be specific enough to authorize a later, separately approved
external capture, but it must not itself select a provider, use a credential,
retain raw data, start a scheduler or make a request.

## Context bound by this design

- TASK-27 closed the historical Solana Tracker 15-minute route with only
  33/96 observed bars; the other 63 remain `MISSING_UNKNOWN`.
- TASK-30 A7 selected `CAPTURE_REQUIRED` for the frozen group
  `RC001-H07-H01-LIQUIDITY-RETENTION`.
- TASK-30 A8 selected `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT` and requires a
  backup/restore route or an explicit tracked waiver before decision-critical,
  irrecoverable future capture.
- TASK-26B retains `OWNED_CANARY_REQUIRED`; market or quote data cannot create
  settlement truth.

The downstream owner decision is only: *is one named external data-route pilot
well specified enough to request?*  It is not: *does H07/H01 work?*

## Approaches considered

### 1. Build a general collector now — rejected

A generic scheduler, provider adapter layer and storage runtime would add
unmeasured architecture before one successful bounded observation route.  It
also crosses provider, raw-retention and monitoring boundaries that this atom
does not own.

### 2. Select a provider and begin a capture now — rejected

Provider availability, quota, credentials and current endpoint behaviour are
mutable facts.  Selecting or probing one before the exact fields, caps,
retention and recovery obligations are frozen would make a later failure hard
to interpret and would exceed this offline atom.

### 3. Recommended: technical-pilot contract first

Create one versioned contract and owner-readable approval packet.  It freezes
the requested observation shape and makes every later external action
reviewable.  It reuses TASK-30 A8's lanes and evaluator conventions rather
than creating a second capture framework.

## Proposed contract shape

### Pilot purpose and target role

The packet names the reference pool above only as an instrumentation subject:

- `purpose`: test whether a future route can preserve a bounded, gap-aware
  PIT market and route-feasibility panel;
- `consumer`: a future TASK-30 data-admissibility decision, not a research
  trial or TASK-31 input;
- `frozen_group`: `RC001-H07-H01-LIQUIDITY-RETENTION`;
- `target_role`: `TECHNICAL_DATA_ROUTE_PILOT`;
- `representativeness`: explicitly `NOT_ESTABLISHED`.

This distinction is essential.  A successful one-pool pilot can validate the
collection route; it cannot establish a cohort effect, H07/H01 alpha,
cross-pool generality, fillability, settlement or NetReturn.

### Required future observations

The future packet requests a 24-hour window with 96 closed 15-minute
intervals.  Each expected interval must be present either as an observation or
as a typed gap/failure; silently absent rows are invalid.

`PIT_MARKET` records require the A8 field set: pool/mint/program identity,
closed interval, OHLCV, liquidity state, `observed_at`, `available_at`,
`ingested_at`, source/raw SHA-256 and typed gap/failure.

`ROUTE_FEASIBILITY` is optional only if the exact later owner packet names its
notional buckets and provider request budget.  If enabled, it requires A8's
route fields at each observation: input/output mint, notional,
route identifier or status, quoted amounts, price impact, separate fees,
three timestamps, source/raw hash and typed gap/failure.

No observation may be imputed.  `MISSING_UNKNOWN`, rate-limit, stale,
transport-failure, provider-disagreement and invalid-identity are distinct
states.

### External authority packet, deferred to the next gate

The future owner gate must bind all of the following before one provider call:

1. provider and exact public or credentialed endpoint;
2. exact pool/base/quote/program identity verified immediately before start;
3. UTC start/end and closed-interval rule;
4. enabled lane(s), fixed route-notional bucket set and maximum request count;
5. credential class, quota/cash cap and prohibited fallback/retry behaviour;
6. retention location outside Git, hashing and access boundary;
7. registered backup/restore reference or explicit tracked waiver;
8. monitoring/foreground operator responsibility and stop conditions;
9. expected output, recovery after `UNKNOWN`, and the exact non-claims.

The provider remains `OWNER_INPUT_REQUIRED` until that gate.  The packet must
not smuggle a provider choice into an example URL, default environment variable
or fallback list.

### Stop and recovery rules

The future capture must stop and preserve a typed gap when identity changes,
the interval is not closed, required timestamps are absent, quota/cap is
reached, backup/waiver evidence is unavailable, monitoring is lost, or a
previous route-feasibility observation is unresolved.  It may not retry by
switching provider or inflate a partial panel into a continuous one.

There is no wallet, signer, transaction, simulation, cash, trial, holdout,
strategy, PnL or numeric NetReturn action in either A9 or the future data-route
pilot.

## Minimal implementation boundary after spec approval

Implementation should modify the existing TASK-30 A8 evaluator/test style,
not create a collector.  The expected output is limited to:

- one versioned A9 contract and machine-readable policy;
- one synthetic golden packet and adversarial tests;
- one short Russian owner approval readout;
- one hash-bound offline receipt and normal Catalog registration.

The evaluator must reject: a missing target role, a pilot promoted to H07/H01
evidence, quote-to-settlement, missing-to-zero, unnamed notional buckets,
external authority counters above zero, provider fallback, and capture without
backup/waiver.

## Acceptance criteria for the design implementation

1. A user can read one packet and know exactly what a later external action
   would collect and what it cannot prove.
2. A technical single-pool pilot is visibly separated from research evidence.
3. The future external gate is bounded by target, time, fields, quota,
   retention, recovery and stop rules.
4. Deterministic tests fail closed on false promotion and missing recovery
   protection.
5. A9 itself reports zero provider, credential, raw-data, scheduler, wallet,
   transaction and cash side effects.

## Out of scope

- provider comparison, selection or endpoint probing;
- any API/RPC/WSS call or raw-data write;
- collector/scheduler/deployment/monitoring runtime;
- H07/H01 trial, TASK-31, holdout consumption or parameter tuning;
- execution, canary, settlement, PnL, NetReturn or strategy promotion.

## Validation and handoff

The eventual A9 implementation uses targeted deterministic tests, Catalog
validation and one normal delivery gate only after a committed candidate.  Its
receipt must state `STATE_CHANGE=NONE` and `Project Sources=NO_CHANGE`.

After the owner reviews this written design, the next step is an implementation
plan.  After the resulting offline contract is validated, the only next
decision is whether to authorize the exact external capture packet described
above.
