# PumpSwap Touch observation contract v1 — TASK-09 Atom 2

## Status and purpose

This contract freezes the offline boundary for
`T09-A2_PUMPSWAP_TOUCH_CONTRACT`. It narrows TASK-09 to point-in-time
PumpSwap **Touch** evidence: observed pool state, successful decoded buy/sell
events, reserve components, fee fields and explicit coverage failures.

It does not authorize or implement a provider, API, RPC or WebSocket request,
credential loading, dependency change, dataset write, Catalog update, commit,
push, pull request, wallet, signer, transaction or payment action. Atom 2 is
offline after the exact Git base is fetched. Cash spend is USD 0.

The estimand is:

> Can one bounded, point-in-time PumpSwap observation probe reconstruct the
> required pool, trade, reserve, fee, timestamp and provenance fields without
> pretending that observation means migration, fillability or executable
> routing?

This is not alpha, a strategy, a fill model, a provider SLA or NetReturn.

## Accepted Entry Gate patch

TASK-09 is Touch-only.

- `Touch` means a PumpSwap pool/account/event was observed with explicit
  evidence and availability time.
- `Fillable`, `NO_ROUTE`, executable quotes, route counts, transaction
  payloads, RealizedVWAP and NetReturn belong to TASK-10 or later.
- A failed transaction is retained as typed raw evidence. It does not create a
  successful pool snapshot or trade input.
- Missing, zero, failed, stale, disagreement and not-observed remain distinct.
- TASK-08 `NOT_TESTABLE_IN_WINDOW` remains an accepted lifecycle coverage
  blocker. TASK-09 does not repair it by selecting only visible pools.

## Reuse decision

TASK-09 follows `ADOPT -> WRAP -> FORK -> BUILD`:

- `ADOPT` TASK-05 `pool_state_snapshots`, `trade_orderflow_inputs`,
  `canonical_observations` and point-in-time timestamp semantics;
- read TASK-05 `token_lifecycle_events` only for explicit migration evidence;
- never write TASK-05 `quote_attempts` from TASK-09;
- `WRAP` TASK-06 redaction, raw identity, immutable evidence and manifest
  boundaries;
- `WRAP` TASK-08 lifecycle evidence and its explicit coverage blocker;
- `BUILD` later only a thin PumpSwap decoder/projector after an exact official
  IDL blob is pinned;
- `FORK` nothing and reject a general collector framework before a second real
  consumer.

## Universe separation

The following labels are independent evidence classifications. They must not
be collapsed into one implicit post-migration universe.

### `PUMPSWAP_OBSERVED`

Membership requires a successful, source-pinned PumpSwap pool/account or
buy/sell event observation with:

- PumpSwap program identity;
- transaction signature and instruction/event position when available;
- pool identity;
- context slot;
- event and availability timestamps;
- raw evidence lineage.

Membership proves Touch only. It does not prove Pump migration provenance,
canonical pool status, route availability or representativeness of launches.

### `PUMP_MIGRATION_CONFIRMED`

Membership requires accepted successful Pump lifecycle evidence naming both
the destination PumpSwap program and destination pool. A pool lookup, a
PumpSwap trade or a pool index cannot manufacture this label.

### `CANONICAL_INDEX_CANDIDATE`

Membership requires an observed PumpSwap pool account with `index == 0`.
Official PumpSwap documentation states that pools created by the Pump
`migrate` instruction use canonical index zero. The converse is not accepted:
`index == 0` remains a candidate label until explicit migration evidence links
the token and destination pool.

Launch, signal and execution universes remain unavailable or empty. No
outcome-dependent selection field may be used to admit an observation.

## Official protocol boundary

Official sources observed read-only on 2026-07-27:

- `https://github.com/pump-fun/pump-public-docs`;
- `docs/PUMP_SWAP_README.md`;
- `idl/pump_amm.json`.

The PumpSwap program is:

`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`

The mutable upstream `main` ref is not a decoder pin. Before T09-A3 may decode
bytes, it must bind an exact official IDL blob SHA and freeze only the required
Pool, `BuyEvent`, `SellEvent` and nested type subset. A discriminator,
field-order, Borsh-type, program-address or appended-field mismatch is
`BLOCKED_PROTOCOL_DRIFT`.

Required logical evidence includes:

- Pool identity, index, creator, base/quote mint and vault accounts;
- raw base-vault and raw quote-vault balances;
- `virtual_quote_reserves`;
- buy/sell direction and exact input/output atomic amounts;
- current fee fields carried by the source evidence;
- transaction result, signature, event position and context slot.

Fee rates are not hard-coded. A later observation records source values and
source version; missing fee evidence is a coverage gap, not zero.

## Reserve semantics

PumpSwap effective quote reserves are:

```text
effective_quote_reserves_atomic
= raw_quote_vault_balance_atomic
+ virtual_quote_reserves_atomic
```

The three values are retained separately:

1. `raw_quote_vault_balance_atomic`;
2. signed `virtual_quote_reserves_atomic`;
3. derived `effective_quote_reserves_atomic`.

Base reserves remain the raw base-vault balance. The virtual component must
never overwrite the raw quote balance. The effective value must never be
stored as if it were the raw vault value.

The official Pool field is signed `i128`. Existing canonical integer fields
are non-negative and have narrower physical storage constraints. Therefore:

- exact signed source bytes remain in redacted raw evidence;
- a representable signed virtual value may use
  `canonical_observations.value_decimal`;
- a non-negative representable effective value may use
  `canonical_observations.value_atomic`;
- negative effective reserves, numeric overflow or precision loss yield
  `SCHEMA_GAP_BLOCK_CANONICALIZATION`;
- values are never clamped, wrapped, dropped or converted to zero.

## Canonical schema mapping

| Relation | TASK-09 use |
|---|---|
| `raw_api_events` | Retain redacted log/account/transaction evidence, successful and failed outcomes, exact content identity and source version. |
| `token_lifecycle_events` | Read-only input for `PUMP_MIGRATION_CONFIRMED`; TASK-09 does not infer or rewrite lifecycle history. |
| `pool_state_snapshots` | Write raw base-vault balance to `base_reserve_atomic` and raw quote-vault balance to `quote_reserve_atomic`; never substitute effective reserves. |
| `trade_orderflow_inputs` | Write only successful decoded PumpSwap buy/sell Touch amounts and side; the row is an observed trade, not our fill. |
| `canonical_observations` | Store representable virtual/effective quote reserve, fee and coverage claims with raw lineage and explicit units. |
| `quote_attempts` | Forbidden TASK-09 writer. `NO_ROUTE`, route identity/count and executable quote evidence begin in TASK-10. |

Any mandatory field that cannot be mapped without information loss becomes an
explicit `SCHEMA_GAP`; Atom 2 does not silently add a new relation.

## Identity, time and revisions

Every durable observation preserves:

```text
event_at
<= observed_at
<= first_reliable_available_at
<= available_at
<= ingested_at
```

`available_at` maps to TASK-05 `available_to_strategy_at`. Backfill never moves
`first_reliable_available_at` backward.

Pool observation identity includes source version, pool, slot and evidence
position. Trade identity additionally includes transaction signature and
instruction/event position. Repeated provider claims coexist as revisions or
disagreement; they never overwrite earlier evidence.

## Primary transport and conditional fallback

The later probe's primary spine is provider-agnostic standard Solana
`logsSubscribe`:

- exactly one `mentions` pubkey: the PumpSwap program;
- `confirmed` commitment;
- one connection, one subscription, concurrency one;
- bounded standard `getTransaction` follow-ups only for selected signatures;
- failed transaction notifications remain raw failure evidence.

Official Solana references checked on 2026-07-27:

- `https://solana.com/docs/rpc/websocket/logssubscribe`;
- `https://solana.com/docs/rpc/http/gettransaction`.

Helius `transactionSubscribe` is a conditional fallback, disabled for the first
probe. Official Helius documentation checked on 2026-07-27 places enhanced
WebSocket methods on Developer and higher plans, while Free supports standard
WebSocket methods. No plan purchase or upgrade is justified by Atom 2.

## Cheapest-falsifier envelope

This envelope is a plan, not provider-call authority.

| Dimension | Hard cap |
|---|---:|
| Elapsed time | 30 seconds |
| WSS connections | 1 |
| WSS subscriptions | 1 |
| Notifications | 256 |
| Uncompressed stream bytes | 1,500,000 |
| `getTransaction` follow-ups | 8 |
| Modeled Helius credits | 40 |
| Received plus stored bytes | 4,000,000 |
| Concurrency | 1 |
| Retries | 0 |
| Cash | USD 0 |

The maximum modeled use is 39 credits:

```text
ceil(1,500,000 / 100,000) * 2
+ 8 standard RPC calls
+ 1 connection
= 39
```

One credit of headroom remains. A later external atom must verify the actual
account plan and billing surface before opening a connection.

Terminal classifications are:

- at least one fully mappable Touch event:
  `FIELD_COVERAGE_CANDIDATE`;
- no accepted Touch event before a cap:
  `NOT_TESTABLE_IN_WINDOW`;
- official protocol mismatch:
  `BLOCKED_PROTOCOL_DRIFT`;
- required value cannot fit the canonical mapping:
  `SCHEMA_GAP_BLOCK_CANONICALIZATION`;
- provider/auth failure: typed provider failure, never empty, zero or
  `NO_ROUTE`.

No terminal classification grants a retry, longer run or purchase.

## Security, stop and rollback

Atom 2 immediately fails on:

- any network client, credential lookup or provider call;
- secret-bearing content or an absolute machine path in durable evidence;
- a transaction build/simulate/sign/send, wallet, webhook or payment path;
- non-zero cash, dependency change or file outside the managed set;
- universe collapse, future filtering or Fillable/Touch conflation;
- raw/effective reserve substitution or precision loss;
- timestamp, revision, budget or protocol drift.

Before a later external run, rollback is no action. During a separately
authorized run, stop closes bounded clients and retains only already-redacted
immutable partial evidence with its typed terminal state.

## Catalog impact

Later reconciliation must register:

- `CONTRACT-T09-PUMPSWAP-TOUCH-001`;
- `FIXTURE-T09-PUMPSWAP-TOUCH-001`;
- `TEST-T09-PUMPSWAP-TOUCH-001`.

Named consumers are TASK-10, TASK-13, TASK-18/19, TASK-20..26, TASK-28..40 and
TASK-43..47. Atom 2 does not update Catalog; its expected status is
`CATALOG_GAP_PENDING_T09_RECONCILIATION`.

## Atom 2 Definition of Done

Atom 2 passes only when:

1. the exact JSON fixture hash and three-file managed set agree;
2. the three universes remain separate and migration inference fails closed;
3. Touch cannot become Fillable, `NO_ROUTE`, quote or NetReturn evidence;
4. raw, virtual and effective reserve semantics pass signed boundary tests;
5. TASK-05 schema projections validate without writing `quote_attempts`;
6. point-in-time timestamps, missing/failure states and revisions remain
   explicit;
7. the primary/fallback roles and 39-credit cheapest-falsifier math agree;
8. targeted and full offline validation, secret scan and file hygiene pass;
9. the staged inventory contains exactly the three authorized Atom 2 files.

The next candidate atom is T09-A3: pin the official PumpSwap IDL subset and
implement an offline decoder/projector with synthetic deterministic replay.
That atom requires a separate exact write set and authority.
