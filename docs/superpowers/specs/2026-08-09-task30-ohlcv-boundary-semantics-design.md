# TASK-30 OHLCV boundary semantics decision — design

## Purpose

`T30-A0_REUSE_FIRST_EMPTY_INTERVAL_DISCRIMINATOR_V1` established one useful
fact and one unresolved one. The frozen GeckoTerminal response contains 96
15-minute records, including 67 zero-volume records, but its newest timestamp
equals the requested `before_timestamp` (`1786186800`). This design prevents a
future TASK-30 consumer from silently deciding whether that timestamp labels
the start or the end of a candle.

The consumer is the next named history-feasibility or TASK-30 entry gate. The
output is a decision record, not a price panel, alpha result, trial, or route
decision.

## Considered approaches

1. **Assume an end-labelled candle.** This would make the observed timestamp
   grid map cleanly to the intended 24-hour interval. It is rejected: one raw
   response does not prove the vendor's timestamp contract.
2. **Shift the grid to fit the frozen target.** This is rejected: it would
   turn an unproven interpretation into a continuous panel and hide a one-bar
   boundary difference.
3. **Preserve both interpretations and fail closed.** Selected. Bind the raw
   response by SHA-256, record the two possible coverage mappings, and require
   independent timestamp-semantics proof before a continuous or PIT claim.

## Design

A small task-owned config binds the A0 raw manifest digest, frozen request
shape and observed response facts. It declares two mutually plausible models:

- `START_LABELED`: timestamp `t` represents `[t, t + 900)`;
- `END_LABELED`: timestamp `t` represents `[t - 900, t)`.

With the observed grid `[1786101300, 1786186800]`, the second model can cover
the requested `[1786100400, 1786186800)` target while the first cannot. That
is a conditional mapping, not a selected truth. The only permitted decision is
`UNRESOLVED_INTERVAL_LABEL_SEMANTICS` and the only next evidence is an
independent exact vendor timestamp-semantics proof. A repeated raw download,
fallback provider, or endpoint probing is not part of this decision.

The deterministic Python evaluator validates that both models remain present,
that their implied coverage differs, and that the config cannot promote the
response to `CONTINUOUS_PANEL`, `PIT_ADMISSIBLE`, `EXPLICIT_NO_TRADE`, or a
TASK-30 trial. A synthetic fixture drives the adversarial cases; the retained
raw JSON stays outside Git and is represented only by its already recorded
SHA-256.

## Files and boundaries

Create a contract, YAML policy, JSON Schema, synthetic fixture, offline
evaluator, targeted test and acceptance receipt. Register the durable
artifacts in the Catalog and regenerate its derived navigation views. The
existing Project Sources release remains unchanged (`NO_CHANGE`): this is an
in-progress offline atom, not canonical TASK-30 acceptance.

No provider/API/RPC/WSS requests, credentials, R2/R3 access, dependency
changes, wallet/signer/transaction actions, cash spending, real data values,
numeric PnL/NetReturn, trial opening, holdout consumption, or Project Source
mutation are allowed.

## Validation and completion

The targeted test must show a valid fail-closed result and reject silent
selection of either timestamp model, a claimed continuous/PIT panel, a
missing-to-zero conversion, and any external or trial authority. The existing
repository policy rejects normal full validation on a non-`main` branch by
design; the delivery candidate will therefore use the tracked-only clean
checkout gate plus exact-head GitHub CI.
