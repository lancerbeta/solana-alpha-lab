# TASK-30 A14 — bounded forward-stream runtime harness contract v1

## Purpose

Prepare one deterministic, fail-closed runtime boundary for a future technical
`transactionSubscribe` pilot on the frozen H07/H01 pool. A14 validates the
request binding, adapter caps and terminal truth offline; it does not connect
to Helius or retain raw data.

## Frozen target and wire profile

- network: `solana`;
- pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`;
- proposed provider: Helius, still owner-selected at execution time;
- method: `transactionSubscribe`;
- filter: `accountInclude=[pool]`, `failed=false`, `vote=false`;
- options: `confirmed`, `jsonParsed`, `full`, `maxSupportedTransactionVersion=0`.

The request binder keeps the API key in memory only. Its safe receipt contains
host, path, method, body hash and body size, never the query value or full URL.

## Runtime limits

The future owner-authorised call is allowed at most one connection, one
subscription, 1,200 seconds and 500 notifications. The A14 reusable runtime
executes a stricter effective 540-second cap, 500 notifications and 1,000,000
stream bytes. The byte ceiling implies a conservative estimated budget of 21
credits under the pinned documentation rule (one connection credit plus two per
100,000 bytes); this is an estimate, not a billing assertion. A later owner
gate must verify actual dashboard headroom without exposing the key.

Retry, reconnect, fallback and scheduler are false. A frame above 100,000 bytes
or any cap breach stops the run before promotion.

## Terminal truth and non-claims

- acknowledgement/notifications are technical observations only;
- no notifications is `NO_OBSERVED_TX_NO_EMPTY_CLAIM`, not an empty interval or
  zero volume;
- a closed or failed transport after acknowledgement is
  `TRANSPORT_LOST_UNKNOWN` and requires reconciliation before any retry;
- a bounded observation is `OBSERVATION_RETAINED_TECHNICAL_ONLY`;
- no output claims PIT admissibility, interval coverage, H07/H01 evidence,
  alpha, strategy, execution, settlement, PnL or NetReturn;
- raw retention remains a separate owner-authorised A4 action outside Git.

## Reuse and stop boundary

A14 wraps the existing TASK-08 `BoundProbeRequest`, `WssCapture` and bounded
WSS exchange safety boundary. It does not reuse the Pump `logsSubscribe` parser
or create a generic streaming platform. The first real Helius call requires the
exact future owner phrase in the versioned config and is outside A14 authority.
