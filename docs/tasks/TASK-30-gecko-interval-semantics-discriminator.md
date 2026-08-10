# TASK-30 A10 — Gecko interval-semantics discriminator

## Objective

Run one bounded, two-endpoint technical check that can distinguish whether
GeckoTerminal's 15-minute OHLCV timestamp is start- or end-labelled for the
frozen pool, or record that the evidence remains inconclusive.

## Consumer

The TASK-30 owner packet needs a small, auditable answer before considering any
future collection design.  It does not consume or create a research trial.

## Scope

One public keyless GeckoTerminal OHLCV GET and one public keyless pool-trades
GET for pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` on Solana.  The
OHLCV query uses the closed 15-minute boundary calculated only at run time.
The raw JSON and local receipt are retained outside Git under retention A4.

## Stop conditions and non-claims

No retry, fallback, credential, scheduler, R2/R3, wallet, transaction, spend,
trial, or TASK-30 acceptance action is permitted.  HTTP failure, malformed
payload, too few usable trades, or two viable models yields an explicit
inconclusive result.  A selected label does not establish continuous coverage,
empty interval semantics, historical data fitness, H07/H01 evidence, alpha,
execution, settlement, PnL, or NetReturn.

## Terminal decisions

`START_LABELED`, `END_LABELED`,
`INCONCLUSIVE_INSUFFICIENT_CROSS_ENDPOINT_EVIDENCE`, or
`INCONCLUSIVE_NO_UNIQUE_MODEL`.  Every result has `STATE_CHANGE=NONE` and
does not grant a future external action.
