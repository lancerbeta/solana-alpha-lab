# TASK-30 A23 Helius bounded pagination complete-batch contract v1

## Decision

Determine whether the immutable A22 page plus at most two sequential Helius
continuation pages form a complete raw-transaction batch for the frozen pool
and UTC day. This is a technical completeness decision, not a PIT or hypothesis
result.

## Frozen input and request

Page 0 is read only from the exact A22 raw path and must match its tracked byte
count, SHA-256, 520-row count and cursor SHA-256 before a credential is used.
It is never refetched. Every continuation preserves the A22 address, closed
block-time window, chronological full-transaction mode, finalized/succeeded
filter, transaction-version cap and 1,000-row limit. Only the JSON-RPC id and
the opaque prior-page `paginationToken` vary.

Raw cursors may exist only in process memory and ignored response bytes.
Tracked evidence stores cursor presence and SHA-256. All pages must preserve
strictly increasing `(slot, transactionIndex)`, nondecreasing `blockTime`,
unique transaction keys and primary signatures, target-pool binding, full
transaction/meta shape and `meta.err=null`.

## Bounded execution

One credential-free DNS/TCP/TLS preflight precedes one `HELIUS_API_KEY` read.
The foreground runner issues at most two sequential POSTs, with no retry,
redirect, fallback, scheduler or second provider. Each page is capped at
25,000,000 bytes and a 100-credit upper bound; new pages together are capped
at 50,000,000 bytes and 200 credits. Each call times out after 30 seconds.

`COMPLETE_RAW_BATCH_CANDIDATE` requires a null cursor within those two calls and
all global validations passing. A non-null cursor after call 2 yields
`BOUNDED_PAGINATION_INCOMPLETE_STOP`. Any binding, transport, provider, schema,
budget, order, duplicate or cursor-cycle error is terminal and consumes no
retry authority.

## Claim boundary

Completion only supplies a candidate input to a separately authorized
data-admissibility atom. It establishes neither a complete 96-slot market
panel nor PIT safety, H07/H01 evidence, route feasibility, fillability, PnL,
NetReturn, alpha, strategy promotion or TASK-30 acceptance. `TASK-30` remains
`BLOCKED_DATA` in every A23 terminal outcome.
