# T30-A4 Reuse-first PIT history route decision — design

## Goal

Decide, without another provider-data request, whether any already observed or
officially documented route can justify one narrowly scoped future proof call
for continuous, point-in-time (PIT) 15-minute Solana pool history.

The consumer is the future exact owner provider-authority gate for TASK-30.
The decision may unblock a data-feasibility test; it does not unblock a
research trial, strategy, execution, fill, settlement, PnL, or NetReturn
claim.

## Current evidence

- TASK-28 freezes all three RC-001 research groups as `BLOCKED_DATA`.
  Their shared blocker includes `CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE`.
- The retained Solana Tracker sample for the named pool contains 33 of the 96
  requested 15-minute bars. Missing rows remain `MISSING_UNKNOWN`; a second
  call to that same shape would not test a new proposition.
- Solana Tracker's official pair-chart documentation explicitly lists `15m`
  and binds the route to `token` plus `pool`, but does not turn the sparse
  observed sample into a continuous panel.
- Birdeye V3 pair OHLCV documentation describes pair-scoped candles and
  `padding=true` for empty candles. It does not, by itself, prove the exact
  REST `15m` enum for this task, bind the named Solana pool to a Birdeye pair,
  or attest local API-key availability.

## Options considered

1. Repeat the previous Solana Tracker request. Rejected: it would spend
   quota without addressing the already observed incompleteness.
2. Build a custom reconstructed candle service. Rejected: this would enlarge
   the factory before proving that a maintained provider cannot satisfy the
   narrower need.
3. Record a reusable-provider decision boundary first. Recommended: it uses
   existing evidence and official contracts to name the smallest falsifying
   future proof, or closes the route without fabrication.

## Proposed T30-A4 boundary

T30-A4 will be an offline, deterministic decision package. It will:

- represent each candidate by separately evidenced capability facts;
- distinguish `DOCUMENTED`, `OBSERVED_INSUFFICIENT`, `UNPROVEN`, and
  `NOT_APPLICABLE` facts;
- reject promotion from documentation to actual panel completeness;
- reject a Solana pool address as a Birdeye pair identity without an exact
  independent proof;
- select only one next boundary: `NO_PROVIDER_PILOT`,
  `EXACT_OWNER_PROOF_CALL_REQUIRED`, or `CLOSE_PIT_HISTORY_ROUTE`;
- preserve the prior TASK-27 and T30 evidence byte-for-byte.

The package will register a versioned contract, policy, JSON Schema, synthetic
fixture, evaluator, tests, acceptance receipt, Factory Fit receipt, and
Catalog-derived views. The evaluator consumes only tracked synthetic inputs;
official documentation facts are recorded as concise source references with
an `as_of` date, not as copied pages or raw provider data.

## Authority and exclusions

T30-A4 permits only local tracked documentation, code, tests, Catalog
generation, ordinary Git delivery, and read-only official-document research.
It permits zero provider/API/RPC/WSS calls, credentials, raw-data writes,
R2/R3 access, dependency changes, wallet/signer/transaction actions, cash
spend, task trial, holdout consumption, or Project Sources activation.

An `EXACT_OWNER_PROOF_CALL_REQUIRED` result grants no call authority. It must
state the remaining facts to prove, the one proposed request shape, raw
retention location, no-retry rule, and stop conditions for a later owner
approval.

## Acceptance and failure cases

Tests must reject at least:

- missing or sparse observations promoted to continuous/PIT-ready;
- REST and WebSocket evidence being conflated;
- a documented feature being treated as an observed property of the named
  pair;
- a missing credential, pair identity, or interval enum being silently
  supplied;
- more than one future provider call, any fallback/retry, or authority
  widening;
- research-trial, alpha, execution, fill, settlement, PnL, and numeric
  NetReturn claims;
- Project Sources disposition other than `NO_CHANGE`.

`FULL_REVIEW` must confirm that this is a reuse decision, not a collector or
new data platform. The task is successful if it makes the next owner action
smaller and falsifiable, including the valid outcome that no provider route is
currently worth testing.
