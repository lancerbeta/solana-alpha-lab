# TASK-38 RC002 H11 next GTA target from pool-history contract v1

## Decision

After `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT` on TASK-37, decide
whether frozen Helius `getTransactionsForAddress(pool)` bytes can name
a **bounded** next GTA target using the pinned Pump CreateEvent subset.
Do not start a new Helius call. Do not GTA the whole Pump program.
Do not start H13/H02. Do not spend.

Keep research cycle `RESEARCH-CYCLE-RC002-001`. Do not retrofit into
frozen RC-001.

## Frozen unique resolver

Bound in `configs/task38_rc002_h11_next_gta_target_from_pool_history_v1.yaml`
before any candidate inspection:

- allowed kinds: `TOKEN_MINT` | `BONDING_CURVE`
- token-balance owner scope: `SCANNED_POOL_ONLY`
- exclude Pump program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
- exclude the already-scanned pool address
- exclude wrapped-SOL quote `So11111111111111111111111111111111111111112`
- prefer a unique mint; else a unique bonding_curve
- multiple remaining mints without that resolver are
  `CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY`
- naming a target does not authorize network

Incidental token mints on other owners in the same transactions are not
next-GTA candidates. GTA of the Pump program is unbounded and forbidden.

## Adopted route

One provider-route identity:
`HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001` over the already
captured A22/A23 PumpSwap **pool** address. Decode with the pinned
TASK-08 Pump event subset. No new RPC, credential, paid plan, wallet,
signer, transaction or deployment.

## Terminal outcomes

- `NEXT_BOUNDED_GTA_TARGET_NAMED`
- `CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY`

`INCONCLUSIVE` is a valid trial outcome when the bytes cannot name a
unique bounded address. Naming is not GTA authorization.

## Non-claims

No alpha, NetReturn, fillability, strategy, bot, RC-001 mutation,
entity graph, route-feasibility/quote panel, wallet, cockpit,
deployment, unattended collector, live PIT, H11 effect re-screen, or
new `getTransactionsForAddress`. Synthetic protocol tests are not the
live universe.
