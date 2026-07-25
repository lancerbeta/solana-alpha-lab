# Lifecycle discovery contract v1 — TASK-08 Atoms 2–3

## Status and purpose

This contract freezes the offline boundary for the TASK-08 lifecycle discovery
pilot. It turns the accepted Entry Gate into deterministic rules and tests. It
does not authorize or implement a provider, API, RPC or WebSocket request, use
credentials, create a dataset, change dependencies, update Catalog, stage,
commit or push.

The task estimand is coverage and timing of Pump token lifecycle transitions
for an outcome-independent launch cohort. It is not alpha, price performance,
fillability, executable NetReturn or a production-provider SLA.

## Reuse decision

TASK-08 follows `ADOPT -> WRAP -> FORK -> BUILD`:

- `ADOPT` the TASK-05 lifecycle states and point-in-time timestamp contract;
- `WRAP` TASK-06 redaction, raw identity, immutable Parquet/manifest and storage
  budget boundaries;
- `WRAP` the TASK-07 read-only provider runtime and transport safety boundary;
- `BUILD` only a thin project-owned offline lifecycle compiler/reducer;
- `FORK` nothing;
- reject a general collector framework before a second proven consumer.

The offline modules have no HTTP, RPC or WebSocket client and contain no
credential loading. Atom 3 adds only a source-pinned Borsh event decoder.

## Frozen lifecycle vocabulary

| State | Exact evidence rule |
|---|---|
| `DISCOVERED` | First indexed-provider observation. It is not silently promoted to on-chain creation time. |
| `CREATED` | Successful official Pump `CreateEvent` from the primary chain spine. |
| `ACTIVE` | Successful official Pump `TradeEvent` after creation. |
| `MIGRATION_STARTED` | Successful official Pump `CompleteEvent`, meaning the bonding curve completed. |
| `MIGRATED` | Successful official Pump `CompletePumpAmmMigrationEvent` with destination program and pool. |
| `INACTIVE` | At least six hours without accepted Pump activity, only when coverage over that interval is complete. |
| `UNKNOWN` | Insufficient follow-up, a coverage gap, provider disagreement or unresolved protocol/schema drift. |

A failed transaction remains raw failure evidence. It never creates a lifecycle
state. Missing, `UNKNOWN`, provider failure and `INACTIVE` are distinct; none is
converted to zero or `NO_ROUTE`.

The protocol source is the official Pump repository:

`https://github.com/pump-fun/pump-public-docs`

The event vocabulary is pinned to `idl/pump.json` at the GitHub content blob
SHA `062e66f032bb9f295353b573be3400070bd55e5b`, observed read-only on
2026-07-25. The frozen local subset is
`tests/fixtures/task08/pump_event_idl_subset_v1.json`; its byte hash is checked
before decoding. This is `PINNED_OFFICIAL_IDL_BLOB`, not a claim that the
mutable upstream `main` ref can never move.

Any future upstream blob, discriminator, field-order or Borsh-type mismatch is
protocol drift and blocks the external probe. The pinned subset contains only
`CreateEvent`, `TradeEvent`, `CompleteEvent`,
`CompletePumpAmmMigrationEvent` and the nested `Shareholder` type. It does not
vendor the full upstream IDL or authorize transport.

## Universe contract

The primary domain is Pump only.

- Launch universe: every successful Pump `CreateEvent` observed by the primary
  chain spine during the first two hours of the run.
- Follow-up: the same cohort is observed for the remaining 22 hours.
- Post-migration universe: only the migrated subset of that launch universe.
- Signal universe: none.
- Execution universe: none.
- Failed transactions and provider failures: raw evidence only.
- Cohort identity:
  `program_id + signature + instruction_index + mint`.

Selection may not depend on migration outcome, liquidity, volume, market cap,
price return, holder count, risk score, popularity or later availability.
Tokens observed too late or through incomplete coverage are right-censored as
`UNKNOWN`; they are not dropped.

## Time and availability

Every lifecycle claim carries five distinct UTC-aware timestamps:

1. `event_at`;
2. `observed_at`;
3. `first_reliable_available_at`;
4. `available_at`;
5. `ingested_at`.

The accepted order is:

```text
event_at
<= observed_at
<= first_reliable_available_at
<= available_at
<= ingested_at
```

`available_at` maps to TASK-05 `available_to_strategy_at`. Backfill does not
move `first_reliable_available_at` into the past.

## Provider roles

### Primary — Helius standard WebSocket

- standard `logsSubscribe`, not Enhanced WebSockets;
- official Pump program
  `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`;
- exactly one `mentions` pubkey;
- `confirmed` commitment;
- one subscription and concurrency one;
- point `getTransaction` follow-ups only after a pinned candidate event;
- the chain spine owns cohort membership.

Official references checked on 2026-07-25:

- `https://www.helius.dev/docs/api-reference/rpc/websocket/logssubscribe`
- `https://www.helius.dev/docs/billing/credits`
- `https://www.helius.dev/docs/billing/plans`
- `https://www.helius.dev/docs/faqs/websockets`

The current public contract states one credit to open a connection and two
credits per 0.1 MB of uncompressed standard WebSocket traffic. Standard RPC
follow-ups cost one credit each unless Helius documents an exception.

### Fallback/audit — Solana Tracker REST

The fallback reads only:

- `/tokens/latest`;
- `/tokens/multi/graduating`;
- `/tokens/multi/graduated`.

It measures overlap, lag and disagreement. It does not own the launch universe.
Pacing is limited to one request per second even though the published free rate
is higher.

Official references checked on 2026-07-25:

- `https://docs.solanatracker.io/guides/token-discovery`
- `https://docs.solanatracker.io/pricing`
- `https://www.solanatracker.io/data-api`

The two official surfaces conflict: the documentation pricing table states
10,000 free requests per month while the product page states 2,500. The
contract therefore uses 2,500 and requires a dashboard read-back before any
probe. Premium Datastream is excluded.

## Cheapest-falsifier budget

The first external probe, if separately authorized, is bounded by:

| Dimension | Hard cap |
|---|---:|
| Elapsed time | 600 seconds |
| WSS connections | 1 |
| WSS subscriptions | 1 |
| Notifications | 500 |
| Uncompressed stream bytes | 1,000,000 |
| `getTransaction` follow-ups | 20 |
| Helius credits | 41 |
| Solana Tracker requests | 8 |
| Received plus stored bytes | 5,000,000 |
| Concurrency | 1 |
| Retries | 0 |
| Cash | USD 0 |

The Helius cap is deterministic:

```text
ceil(1,000,000 / 100,000) * 2
+ 20 RPC calls
+ 1 connection
= 41 credits
```

No eligible event yields `NOT_TESTABLE_IN_WINDOW`; it does not authorize an
automatic extension or retry.

## Provisional 24-hour outer envelope

The probe must validate or reduce this envelope before a 24-hour run:

| Dimension | Hard cap |
|---|---:|
| Run | 24 hours |
| Intake | 2 hours |
| Follow-up | 22 hours |
| Initial WSS connections | 1 |
| Reconnects | 6 |
| Uncompressed stream bytes | 500,000,000 |
| Transaction follow-ups | 5,000 |
| Helius credits | 16,000 |
| Solana Tracker requests | 1,200 |
| Solana Tracker allowance reserve | 1,300 |
| Dataset bytes | 1,073,741,824 |
| Partition bytes | 67,108,864 |
| Minimum free bytes after write | 21,474,836,480 |
| Concurrency | 1 |
| Cash | USD 0 |

The maximum modeled Helius use is 15,007 credits: 10,000 streaming credits,
5,000 standard RPC calls and seven total connections. The 16,000 cap preserves
explicit headroom. Solana Tracker usage plus reserve equals the conservative
2,500-request allowance.

## Security, stop and recovery

Atom 2 keeps all external actions disabled. Immediate failure applies to:

- any transport import or runtime network enablement;
- any credential value, secret-bearing field or absolute machine path in
  durable metadata;
- a state-changing request, transaction, webhook, payment, wallet or signer
  path;
- cash above zero;
- an outcome-dependent cohort filter;
- unknown or reordered timestamps;
- unpinned Pump IDL use;
- provider endpoint, auth, pricing or schema drift;
- any byte, credit, request, disk, time, retry or concurrency cap breach.

Before a later external run, rollback is no action. During a later authorized
run, stop closes bounded clients and retains only already-redacted immutable
partial evidence with typed failure and coverage status. It does not retry or
delete accepted raw evidence.

## Catalog impact and consumers

Future reconciliation must register:

- `CTRL-TASK-08-001`;
- `CONTRACT-T08-LIFECYCLE-DISCOVERY-001`;
- `MODULE-T08-LIFECYCLE-DISCOVERY-001`;
- `FIXTURE-T08-LIFECYCLE-DISCOVERY-001`;
- `TEST-T08-LIFECYCLE-DISCOVERY-001`.

Named consumers are TASK-09, TASK-11, TASK-12, TASK-13, TASK-18 and TASK-19.
Atom 2 does not update Catalog; registration belongs to a separately authorized
final reconciliation.

## Atom 2 Definition of Done

Atom 2 passes only when:

1. the exact frozen JSON fixture compiles by SHA-256;
2. lifecycle states and protocol events match TASK-05 and official Pump
   semantics;
3. winner-only and other future-outcome filters fail closed;
4. timestamps, right-censoring and missing-state distinctions pass negative
   tests;
5. provider roles and conservative quota conflict handling are exact;
6. credit, request, byte, time, disk and cash guards pass boundary tests;
7. the module contains no transport or credential loading;
8. targeted and full repository tests, secret scan and whitespace/encoding
   checks pass;
9. the worktree delta contains only the four authorized Atom 2 files.
