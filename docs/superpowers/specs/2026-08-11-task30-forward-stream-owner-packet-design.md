# TASK-30 A13 — Forward stream owner-packet readiness design

## Decision in one sentence

Prepare a deterministic offline owner packet for one future, foreground,
credentialed `transactionSubscribe` technical pilot on the frozen pool; do not
connect, collect, add a client library, select a provider as fact, or claim a
coverage result.

The sole decision unlocked by this atom is whether the owner can later grant a
small, explicit external-read gate with all limits visible in one place.  It is
not a data-capture run and it does not make a 15-minute panel, an H07/H01
observation, a trial, an execution, a position, or a cashflow claim.

## Why this is the next smallest useful step

TASK-30 A12 established that repeating provider-owned OHLCV polling will not
repair the named consumer's missing-interval truth.  A forward transaction
stream is the smallest remaining route that could preserve the raw evidence
needed to derive intervals honestly.  But an external pilot without a frozen
target, caps, retained acknowledgement, failure vocabulary and recovery rule
would produce an ambiguous one-shot trace.

This atom removes that ambiguity offline first.  A future technical pilot can
then fail in minutes with a useful receipt, rather than fail after a long
capture with no way to say whether a gap means no transactions or no
observation.

## Reuse-first finding

| Candidate | Evidence | Decision for A13 |
| --- | --- | --- |
| Existing TASK-08 `lifecycle_discovery_transport` | It already has a bounded, no-reconnect Helius WSS exchange, redacted receipts, immutable retention and deterministic test doubles.  Its binding and parser are hard-wired to `logsSubscribe` and Pump logs. | `WRAP_CANDIDATE`, not direct reuse.  A future implementation must prove that its generic capture and receipt boundary fits `transactionSubscribe` without weakening its strict caps. |
| Official Helius `transactionSubscribe` documentation | It defines filtered transaction notifications, subscription acknowledgement and unsubscribe semantics. | Candidate wire contract only; no endpoint, credential or commercial entitlement is asserted. |
| Official Helius indexing guidance | It distinguishes a lightweight WebSocket prototype from replay-capable production paths and requires external gap handling when the stream disconnects. | Make discontinuity fail closed.  The first pilot does not reconnect or backfill. |
| Official Helius SDK | It may offer a maintained client wrapper, but dependency fit, plan support and runtime behaviour are unverified here. | `ADOPT=NO_DECISION`; do not add a dependency. |
| Yellowstone/gRPC or managed replay | They are mature references for later replay and resilience. | `WATCH_ONLY`; disproportionate before one named pool proves technical capture value. |

The result is deliberately small: reuse the *safety pattern*, not the old
Pump-specific implementation.  Building a second collector or generic
streaming platform now would add cost without answering the current decision.

## Exact proposed future pilot envelope

The offline packet proposes, but does not authorize, this one future action:

| Field | Proposed value | Meaning |
| --- | --- | --- |
| Candidate provider | `HELIUS_TRANSACTION_SUBSCRIBE` | Candidate only; the owner gate remains the provider-selection decision. |
| Transport | `WSS_JSON_RPC` | One foreground connection and one subscription; no scheduler. |
| Network | `solana` | Must be asserted again by the provider acknowledgement/route receipt. |
| Target pool | `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` | Frozen identity binding. |
| Base mint | `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` | Frozen identity binding, not an instruction to trade. |
| Candidate wire profile | `transactionSubscribe`, `accountInclude=[URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S]`, `commitment=confirmed`, `encoding=jsonParsed`, `transactionDetails=full`, `maxSupportedTransactionVersion=0`, `failed=false`, `vote=false` | The proposed filter is exactly bound to the frozen pool and must be recorded as the sent body hash if the later pilot is authorised. |
| Connection cap | `1` | A second connection is a separate owner decision. |
| Subscription cap | `1` | No broad or additional filters. |
| Open-duration cap | `1,200` seconds | A short technical evidence window, not a coverage promise. |
| Notification cap | `500` | Stops before uncontrolled retention growth. |
| Raw retention | Existing A4 location outside Git, immutable per-run | The later owner gate must name the exact absolute root without placing a secret in the packet. |
| Retry / reconnect / fallback | `false / false / false` | Any transport loss is preserved as `UNKNOWN`; no automatic repair. |
| Monitoring owner | `LOCAL_WORK_CODEX_FOREGROUND` | The pilot does not run unattended. |
| Cash / wallet / transaction cap | `0 / forbidden / forbidden` | This is a read-only technical probe. |

The DEX program or route must be supplied by a future verified route receipt;
this packet does not invent one from the pool address.

## Terminal truth model

The later pilot must produce exactly one terminal classification.  None means
that market state, interval emptiness or data completeness has been learned
unless its explicit rules are satisfied.

| Terminal state | What it proves | What it does not prove |
| --- | --- | --- |
| `PILOT_NOT_AUTHORIZED` | No external action was permitted. | Nothing about availability. |
| `CONNECTION_OR_AUTH_REJECTED` | The bounded attempt could not open or authenticate. | Provider entitlement, no transactions, or a pool problem. |
| `SUBSCRIPTION_REJECTED` | The candidate request/filters were not accepted. | Lack of pool activity. |
| `NO_OBSERVED_TX_NO_EMPTY_CLAIM` | An acknowledged bounded window emitted no admitted matching notification. | A zero-volume candle, a complete window, or absence of transactions. |
| `OBSERVATION_RETAINED_TECHNICAL_ONLY` | At least one identity-bound raw notification and receipt were retained. | Completeness, parsing correctness, H07/H01 evidence or a trial. |
| `TRANSPORT_LOST_UNKNOWN` | A gap or interruption prevents a coverage conclusion. | That the affected span is empty, flat, zero or recovered. |
| `RETENTION_FAILED_STOP` | A raw/receipt durability check failed before evidence could be trusted. | A usable stream result. |

`UNKNOWN` may only move to `RECONCILED` in a separately authorised
reconciliation action that names its source and residual uncertainty.  A retry,
silent reconnect or another provider response cannot overwrite it.

## Offline deliverable shape

The implementation plan should create only these deterministic artifacts:

1. a versioned task contract, config and JSON schema defining the proposed
   envelope, exact owner phrase, terminal enum and non-claims;
2. a pure Python evaluator plus a human-readable packet renderer; it must make
   no network, credential, raw-file, scheduler or provider call;
3. synthetic fixtures and tests for the happy packet and all rejection paths;
4. an acceptance receipt recording zero external calls, zero credential reads,
   zero raw writes and `STATE_CHANGE=NONE`; and
5. required Catalog/generated bindings after the ordinary repository delivery
   gate.

It explicitly excludes a WebSocket client, Helius SDK adoption, an endpoint,
an API key, a transport implementation, persistent capture, retry logic,
decoder, panel projection, automated monitoring, dashboard, trial and any
wallet-related code.

## Deterministic falsifiers

Tests must reject at minimum:

- any selected/active provider claim rather than `PROPOSED`;
- a credential, endpoint URL, secret-shaped value or credential read flag in a
  durable packet;
- connection/subscription counts other than one, a duration or notification
  cap above the frozen values, or a nonzero cash cap;
- retry, reconnect, fallback, unattended scheduler or raw-write capability;
- target mismatch, absent base-mint binding, or invented DEX program/route;
- `NO_OBSERVED_TX_NO_EMPTY_CLAIM` promoted to empty/zero/complete;
- a `TRANSPORT_LOST_UNKNOWN` followed by retry, projection or acceptance;
- a retained notification promoted to H07/H01 evidence, trial, execution,
  settlement, PnL or NetReturn; and
- a future run packet without the exact owner phrase, A4 retention root,
  monitoring owner, stop procedure and separate reconciliation reference.

## Owner experience and recovery

The rendered packet must be understandable without reading Python.  Before a
future external gate, the owner sees: the exact pool and mint, what the probe
will and will not do, maximum connection time and notification count, storage
location class, stop conditions, and the precise phrase that authorizes only
that bounded pilot.

If the stream closes, monitoring disappears, the target cannot be bound, or
raw evidence cannot be retained, the operator stops.  The next action is not
“try again”; it is to inspect the safe receipt and decide whether a separately
bounded reconcile or redesign is worth it.

## Factory fit and horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW` is appropriate because this touches an
external-data boundary, future retention and coverage truth.  The component is
reusable only as a narrow owner-packet/evaluator pattern: the next hypothesis
may change the target and wire filter without inheriting a false claim of
coverage.

**NOW:** A13 reduces the largest preventable failure mode—an unexplainable
first stream capture—at zero provider or cash cost.

**WATCH:** adopt a replay-capable stream only if a future authorised pilot
retains a technically valid notification yet its coverage/recovery requirements
remain unmet.  That is the trigger; not the mere existence of a higher-powered
tool.

## Boundary and next decision

A13 ends at an offline, tested owner packet.  Its success does not authorize
the later external action.  The next material decision, only after the packet
passes review, is whether to grant the exact single-pilot external-read phrase
with the frozen caps above.
