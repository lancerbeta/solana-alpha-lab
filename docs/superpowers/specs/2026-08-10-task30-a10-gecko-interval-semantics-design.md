# TASK-30 A10 Gecko interval-semantics discriminator — design

## Decision and consumer

The consumer is the TASK-30 owner packet.  The only decision is whether the
returned 15-minute OHLCV timestamp can be interpreted as `START_LABELED`,
`END_LABELED`, or remains `INCONCLUSIVE`.  This is a technical timestamp
semantics check only.  It neither opens a research trial nor makes a claim
about H07/H01, panel completeness, pool representativeness, fills, execution,
settlement, PnL, or NetReturn.

T30-A1 retained an ambiguity: one 96-bar response ending at its
`before_timestamp` fit both label models.  Two shifted OHLCV requests would
repeat that ambiguity.  A10 therefore uses two distinct, keyless public
GeckoTerminal GETs for the exact frozen Solana pool:

1. one 15-minute base-token/USD OHLCV request; and
2. one past-24-hour pool-trades request.

The provider documents OHLCV records as timestamp/open/high/low/close/volume
and documents the pool-trades endpoint as individual records with
`block_timestamp` and USD prices.  A trade price can contradict the range of
one of the two candidate bars.  It cannot alone prove a continuous panel.

## Exact safety envelope

- Maximum exactly two external requests, both HTTPS `GET`, no redirects and no
  retry.  A `--dry-run` performs zero network I/O.
- Only `api.geckoterminal.com/api/v2`, network `solana`, and pool
  `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` are allowlisted.
- No key, account, cookie, credential, fallback provider, scheduler,
  background process, R2/R3, wallet, signer, transaction, spend, trial, or
  TASK-30 acceptance action exists in code or config.
- Exact response bytes and an immutable manifest are retained beneath the
  ignored `local/` root.  Tracked evidence holds only relative locations,
  hashes, sizes, timestamps, HTTP/transport classification, and the limited
  decision.
- Any transport, payload, endpoint, price-unit, or evidence-threshold problem
  produces an explicit inconclusive/invalid result; it never retries or
  silently switches source.

## Components and data flow

`task30_gecko_interval_semantics.py` is a pure evaluator.  It validates the
frozen request plan and parses two JSON objects.  For every usable trade it
derives the UTC 900-second slot and tests both candidate label mappings:

```text
trade timestamp -> floor(timestamp / 900) * 900
  START_LABELED -> bar timestamp = slot start
  END_LABELED   -> bar timestamp = slot start + 900
```

A model is contradicted when a mapped bar exists but the trade's base-token USD
price is outside that bar's inclusive low/high range (with only a tiny,
explicit floating-point tolerance).  A model is selected only when it has at
least two usable trades in two distinct slots, no contradictions, and the
other model has at least one contradiction.  Otherwise the result is
`INCONCLUSIVE_*`.  This deliberately favours a false negative over a wrong
one-bar shift.

`run_task30_gecko_interval_semantics.py` builds the one-shot plan from the
closed 15-minute boundary at runtime, prints it in dry-run mode, and only sends
the two requests after an explicit `--execute`.  It stores raw bytes outside
Git, calls the pure evaluator, and writes a sanitized local runtime receipt.
After the exact run, a tracked runtime receipt, Full Factory Fit receipt,
Catalog records, and generated navigation make the decision queryable.

## Verification and stop rules

Synthetic tests cover a start-labelled discriminator, an end-labelled
discriminator, equal-plausibility inconclusive data, malformed payloads,
wrong host/path/method/pool, the two-call cap, zero-I/O dry-run, and every
forbidden authority field.  The runtime script is reviewed before the single
live execution.  The live result may be `INCONCLUSIVE`; that is a valid
technical result and blocks any move to a 24-hour collector until a separate
owner decision.

## Explicit non-claims

`START_LABELED` or `END_LABELED` here means only that this two-endpoint
observation met the discriminator threshold.  It does not establish
historical coverage, empty-interval semantics, provider fitness, a research
dataset, alpha, executable liquidity, execution truth, or economic return.
