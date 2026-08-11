# TASK-30 A14 — bounded forward-stream runtime harness

## Objective

Prepare a deterministic, offline-only harness for one future foreground
`transactionSubscribe` technical capture.  The harness must make the target,
wire profile, caps, stop rules, accounting estimate and non-claims explicit
before any Helius connection or credential is used.

## Consumer and frozen identity

- Consumer: `FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE`
- Network: `solana`
- Pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- Base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`

## Bounded deliverable

- versioned contract, strict YAML policy and JSON Schema;
- fake-only capture classifier and target-locked request binder;
- Russian owner readout and deterministic CLI renderer;
- synthetic tests for success, no observation, transport loss, target drift,
  cap breach, retry/reconnect prohibition and exact owner phrase;
- acceptance, Factory Fit and Catalog bindings.

## Hard boundaries

This atom performs zero provider/API/RPC/WSS calls, credential reads, raw-data
writes, scheduler/background work, dependency changes, R2/R3 access, wallet or
transaction actions, cash spend, trial/acceptance actions or Project Sources
changes.  The injected exchange in tests is a fake only; no default socket is
wired into the module.

The owner phrase is a future gate, not authority.  Effective runtime caps are
540 seconds, 500 notifications and 1,000,000 stream bytes; retry, reconnect,
fallback and scheduler remain forbidden.  A capture without notifications is
not an empty interval or zero volume.  Transport loss is `UNKNOWN` and cannot
be retried or promoted.  The packet cannot claim coverage, PIT admissibility,
H07/H01 evidence, alpha, execution, settlement, PnL, NetReturn or TASK-30
acceptance.

## Reuse and next gate

Decision: `WRAP_CANDIDATE`.  A future implementation may wrap the existing
bounded TASK-08 WSS safety/receipt boundary, but the Pump `logsSubscribe`
binding and parser are not treated as a direct transaction-stream fit.

The next action is one separate exact owner external-read gate.  A14 stops
before that action and leaves Project Sources unchanged.
