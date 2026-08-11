# TASK-30 A14P — forward-stream execution adapter design

Status: `SPEC_REVIEW_APPROVED`

Owner design receipt: `A14P_ADAPTER_DESIGN_APPROVED`

Owner spec-review receipt: `A14P_SPEC_REVIEW_APPROVED`

Date: `2026-08-11`

Authority class: `LOCAL_WRITE_ONLY` until a separate exact external owner gate

## 1. Decision

Build one narrow adapter that joins the accepted A14 target-locked request and
classifier to the existing TASK-08 bounded WebSocket transport and an ignored
A4 raw-evidence sink. Do not build a generic streaming collector, scheduler,
decoder, candle builder or provider abstraction.

The adapter is an offline prerequisite to one possible future foreground
Helius capture. Its implementation, tests, commit, PR and CI do not authorize
credentials, provider/API/RPC/WSS execution or raw external-data collection.

## 2. Problem being closed

A14 validates the request binding, caps, owner phrase and terminal semantics,
but its runtime receives an injected exchange and accepts an A14-specific
`RuntimeCapture`. The existing production-safe TASK-08 transport returns
`WssCapture`, and no A14 runner currently:

- connects the two types;
- records an attempt before the connection begins;
- retains exact acknowledgement and notification bytes outside Git;
- binds receipt-time timestamps and hashes to the retained payloads; or
- leaves a durable unresolved marker if the foreground process terminates.

Calling Helius before this seam is closed would make the first material run an
unreceipted one-off operation.

## 3. Frozen inputs and boundaries

- network: `solana`;
- pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`;
- base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`;
- provider candidate: `HELIUS`;
- method: `transactionSubscribe`;
- filter: `accountInclude=[pool]`, `failed=false`, `vote=false`;
- options: `confirmed`, `jsonParsed`, `full`,
  `maxSupportedTransactionVersion=0`;
- one connection and one subscription;
- effective runtime: at most 540 seconds, 500 notifications, 1,000,000 stream
  bytes and 100,000 bytes per frame;
- estimated credit ceiling: 21 under the pinned documentation rule; this is
  not a billing claim;
- `retry=false`, `reconnect=false`, `fallback=false`, `scheduler=false`;
- foreground monitoring owner: `LOCAL_WORK_CODEX_FOREGROUND`;
- retention class: `A4` under logical ignored root
  `local/task30_forward_stream`.

No dependency change is allowed. The existing pinned `websockets` dependency
and TASK-08 transport are the only production transport seam.

## 4. Components

### 4.1 Existing A14 owner

`task30_forward_stream_runtime.py` remains the truth owner for target binding,
safe request construction, exact owner phrase, capture classification and
non-claims.

### 4.2 Existing TASK-08 transport

`websockets_wss_exchange()` remains the only socket implementation. The A14P
adapter passes the frozen effective caps and receives one `WssCapture`. It does
not copy or fork connection, ping, frame-limit or close logic.

### 4.3 Narrow A14P adapter

A new focused module owns only:

- pre-call validation and create-only run identity;
- conversion of `WssCapture` into the A14 classification input;
- exact raw retention and sanitized manifest/receipt creation;
- terminal mapping for authorization, subscription, transport and retention
  failures; and
- the unresolved-attempt rule.

It exposes injected clock, credential loader and transport seams for tests.
Production defaults are supplied only by the CLI runner.

### 4.4 Foreground CLI runner

The runner has two modes:

- `--dry-run`: validates policy, target, raw-root containment and authority
  syntax without reading `HELIUS_API_KEY`, creating output or opening a socket;
- `--execute`: requires the exact future owner phrase, a create-only A4 run
  root and the environment variable `HELIUS_API_KEY`. Credential lookup occurs
  only after every non-secret preflight succeeds.

Standard output contains one sanitized JSON receipt. It never contains an API
key, full endpoint, full URL, request headers or raw provider payload.

## 5. Data flow

1. Load and strictly validate the accepted A14 policy.
2. Parse the exact external authority phrase without normalizing or widening
   it.
3. Resolve the supplied absolute raw root and require it to equal the current
   repository/worktree's ignored logical root `local/task30_forward_stream`.
4. Create a unique `run=<UTC>-<nonce>` directory and atomically publish
   `attempt_started.json` containing only target identity, caps, safe request
   receipt, start time and `UNRESOLVED_EXTERNAL_ATTEMPT`.
5. Read `HELIUS_API_KEY` from the process environment without displaying or
   persisting it.
6. Run exactly one TASK-08 bounded WSS exchange.
7. Retain exact bytes as `acknowledgement.json` and ordered
   `notifications/000001.json` files. Preserve TASK-08 observed-at timestamps
   in the manifest; do not infer event time from receipt time.
8. Build a manifest with byte counts and SHA-256 for every retained object,
   then classify the capture through the A14 classifier.
9. Atomically publish `terminal_receipt.json`. A terminal receipt supersedes
   the started marker semantically but never deletes or rewrites it.

Raw files and local receipts remain ignored and outside Catalog bytes. A later
tracked acceptance receipt may contain only logical locations, hashes, counts,
times and sanitized terminal truth.

## 6. Failure and recovery semantics

| Condition | Result | Retry |
| --- | --- | --- |
| Missing/wrong owner phrase | `PILOT_NOT_AUTHORIZED` before credential read | forbidden |
| Invalid or non-ignored raw root | fail before credential read and socket | forbidden |
| Missing local credential | `CONNECTION_OR_AUTH_REJECTED` with no secret detail | forbidden |
| JSON-RPC subscription error or invalid acknowledgement | `SUBSCRIPTION_REJECTED` | forbidden |
| Clean bound with no notifications | `NO_OBSERVED_TX_NO_EMPTY_CLAIM` | forbidden |
| Clean bound with retained notifications | `OBSERVATION_RETAINED_TECHNICAL_ONLY` | forbidden |
| DNS/TLS/timeout/remote close/transport failure | `TRANSPORT_LOST_UNKNOWN` | forbidden |
| Exact bytes cannot be retained or verified while the receipt path remains writable | `RETENTION_FAILED_STOP` | forbidden |
| Started marker without terminal receipt | `UNRESOLVED_EXTERNAL_ATTEMPT` | blocked pending separate reconciliation |

No automatic reconciliation is introduced. Any second external call requires a
new exact owner gate after the first attempt is terminally understood.
If the entire A4 root becomes unwritable, the adapter cannot honestly claim a
durable terminal receipt: it leaves the previously published started marker as
`UNRESOLVED_EXTERNAL_ATTEMPT` and emits only a sanitized process failure. It
must not reinterpret that condition as `RETENTION_FAILED_STOP` in durable
state.

## 7. Test strategy

All implementation acceptance before the external gate is deterministic and
offline. Tests use a fake credential loader and fake TASK-08 transport.

Required falsifiers:

- dry-run reads no credential, writes nothing and performs no transport call;
- wrong authority fails before credential and transport;
- raw-root escape, symlink or existing run collision fails closed;
- exactly one transport call receives the frozen caps;
- `WssCapture` timestamps and raw bytes survive exact retention;
- manifest hashes and counts reproduce from disk;
- empty capture is not zero volume or an empty interval;
- remote close and timeout remain `UNKNOWN`;
- malformed acknowledgement and subscription drift are rejected;
- notification/frame/stream caps cannot be widened through booleans or floats;
- simulated retention failure emits/retains a safe stopped attempt;
- no safe receipt, exception or object representation exposes a fake secret,
  full endpoint or payload;
- unresolved attempts block another run;
- existing A14 and TASK-08 targeted suites remain green.

## 8. Scope and non-claims

In scope: one adapter, one CLI, one synthetic fixture/test family, versioned
contract/config/schema, acceptance/Factory Fit evidence and necessary Catalog
bindings.

Out of scope: any real WSS call, quota/dashboard read, credential inspection,
historical backfill, parsing trades into candles, interval projection, PIT
admissibility, H07/H01 evidence, trial opening, scheduler, service deployment,
wallet, signer, transaction, execution, settlement, PnL or NetReturn.

`READY_FOR_EXACT_OWNER_EXTERNAL_GATE_WITH_LIMITATIONS` means only that the
offline path is technically ready. It grants no external authority.

## 9. Alternatives considered

1. **Narrow TASK-08 wrapper — selected.** Lowest change amplification and the
   only route that preserves the already-tested socket boundary.
2. **One-off inline script — rejected.** Cheaper in lines but leaves the first
   material run weakly reproducible and easy to mis-retain.
3. **Generic streaming service — rejected.** No second validated consumer,
   scheduler need or production operating model exists yet.

## 10. Acceptance and stop boundary

The offline adapter is acceptable only when its exact committed bytes pass the
new adversarial suite, direct A14/TASK-08 compatibility tests, Catalog and the
repository delivery gate. Factory Fit is `FULL_REVIEW` because the patch
touches credentials, external transport, raw lineage and recovery semantics.

After merge and exact-main CI, stop before credential lookup and provider
execution. The next user action is one exact A14P external authority phrase.
That future phrase authorizes at most one foreground capture under the frozen
caps and does not authorize retry, fallback, wallet, transaction, spend or
TASK-30 acceptance.
