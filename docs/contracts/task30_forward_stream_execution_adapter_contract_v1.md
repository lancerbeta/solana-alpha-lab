# TASK-30 A14P — forward-stream execution adapter contract v1

## Purpose

Provide one narrow, deterministic adapter for a future single foreground
technical stream capture. The contract makes the first material call
receiptable and recoverable without creating a generic collector or granting
external authority.

## Frozen target and transport

- network: `solana`;
- pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`;
- candidate provider: Helius;
- method: `transactionSubscribe`;
- filter: `accountInclude=[pool]`, `failed=false`, `vote=false`;
- options: `confirmed`, `jsonParsed`, `full`,
  `maxSupportedTransactionVersion=0`;
- exactly one connection and subscription, no retry, reconnect, fallback or
  scheduler.

The existing A14 module remains the target/request/classification truth owner.
The existing TASK-08 `websockets_wss_exchange()` remains the only socket
implementation. A14P owns only attempt state, compatibility mapping, exact
retention, terminal receipts and the CLI boundary.

## Preflight and authority order

Before any credential lookup or transport call, the adapter must validate:

1. the exact closed A14P and A14 runtime policies;
2. the exact owner phrase;
3. an absolute repository root and exact ignored logical raw root
   `local/task30_forward_stream` with no symlink component;
4. absence of any prior unresolved attempt;
5. UTC start time, safe nonce and create-only run identity.

It then publishes `attempt_started.json`. Only afterward may execute mode read
exactly `HELIUS_API_KEY` and perform one injected exchange. Dry-run reads no
environment mapping, writes nothing and calls no transport.

## Retention and terminal truth

Acknowledgement and ordered notification bytes are retained exactly. Their
receipt-time UTC timestamps, byte counts and SHA-256 hashes are reproduced from
disk in `raw_manifest.json`. Provider raw bytes remain ignored outside Git;
tracked evidence may bind only logical paths, counts, hashes, times and
sanitised terminal truth.

- bounded notifications: `OBSERVATION_RETAINED_TECHNICAL_ONLY`;
- bounded zero notifications: `NO_OBSERVED_TX_NO_EMPTY_CLAIM`;
- provider subscription error: `SUBSCRIPTION_REJECTED`;
- transport loss or non-bounded terminal: `TRANSPORT_LOST_UNKNOWN`;
- missing/invalid credential before transport: `CONNECTION_OR_AUTH_REJECTED`;
- raw retention failure with a writable receipt path: `RETENTION_FAILED_STOP`;
- missing or invalid terminal receipt: `UNRESOLVED_EXTERNAL_ATTEMPT`.

UNKNOWN or unresolved truth forbids another attempt until separately
reconciled. No automatic reconciliation or retry is part of this contract.

## Caps and secret safety

Effective adapter caps are 540 seconds, 500 notifications, 1,000,000 stream
bytes and 100,000 bytes per frame. The conservative estimated ceiling remains
21 credits under the pinned documentation rule and is not a billing claim.

Credentials stay in memory and never enter tracked files, raw receipts, safe
output, full URLs, exception text or object representations. Unexpected local
exceptions collapse to a fixed sanitised error class.

## Non-claims and acceptance boundary

The adapter does not establish provider suitability, interval coverage, empty
intervals, zero volume, PIT admissibility, H07/H01 evidence, alpha, strategy,
execution, inventory, settlement, PnL, NetReturn or TASK-30 acceptance.
`READY_FOR_EXACT_OWNER_EXTERNAL_GATE_WITH_LIMITATIONS` means only that the
offline path passed its tests and delivery gates. It authorises no external
call, credential read or raw external-data write.
