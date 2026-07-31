# TASK-21 bounded admission and multi-horizon capture contract v1

`T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1` starts the
forward-only TASK-21 observation sequence without turning it into a daemon.
This contract authorizes only the first `H0` stage. Every later horizon remains
a separate foreground execution behind a durable time gate.

## Exact inputs and admission

The companion configuration binds the accepted reconciliation overlay, real
nomination policy, exact T1 replay partition, recovery receipt, proven live
transport and their SHA-256 values.

Only the three nominations already sealed in the T1 replay may be evaluated.
They are ordered by:

1. `first_reliable_available_at`;
2. `observed_at`;
3. `nomination_event_id`.

Evaluation and all three membership events are persisted before the first
quote request. Their `entered_at` is the actual admission time. The original
future T1 close is retained as history and is never used as an admission time.
No price, route, quote, terminal class or hypothesis outcome participates in
admission or ordering.

## H0 panel

Each admitted member receives one create-only H0 panel:

- USD 10, 25, 50 and 100 BUY quotes;
- a dependent reverse SELL only when its corresponding BUY is accepted;
- the SELL input is the exact BUY output atomic amount;
- at most eight requests per member and 24 requests across H0;
- concurrency one, retries zero and at least 2.2 seconds between requests;
- request timeout 20 seconds and total foreground wall cap 300 seconds;
- received response bytes at most 3 MiB;
- durable local evidence at most 16 MiB.

The only provider surface is keyless
`GET https://api.jup.ag/swap/v1/quote`, already proven by TASK-21 A5. A
requirement for authentication, another host/path, a transaction or
instruction payload, an untyped response, a cap breach or stale recovery stops
the run. There is no fallback endpoint.

Every attempted call is retained as raw and typed create-only evidence under
`local/task21_forward/h0_capture`. Partial evidence is not deleted after the
first request. The tracked runtime receipt is sanitized and does not expose
quote values, token ranking, cost curves or a hypothesis verdict.

## Recovery and later horizons

Immediately before H0, the accepted recovery receipt must still report
`HEALTHY`, with backup age at most 24 hours and restore proof age at most seven
days. The private Google Drive recovery destination is frozen by the exact
receipt, but this H0 execution performs no Drive action.

If all three H0 panels close without a contract stop, the actual latest H0
timestamp creates an `H1` gate at `+3600` seconds. The gate has a ten-minute
foreground execution window. Missing it creates an explicit coverage gap; it
does not authorize backfill or rescheduling. `H6`, sentinel `H24/H72/H168`,
backup execution and later tranches remain unexecuted and require their own
exact boundaries.

No scheduler, daemon, cron job or unattended provider process is installed.
The durable marker exists so a future thread cannot silently skip the next
required horizon.

## Authority and non-claims

The exact user phrase
`T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1` authorizes this H0
stage only:

- at most three real T1 admissions;
- at most three H0 panels and 24 provider calls;
- at most 24 modeled credits, with no billed-credit claim;
- one create-only local run, at most 16 MiB;
- one sanitized tracked runtime receipt and one durable time-gate update.

Cash, credentials, account creation, purchase, Drive operations, scheduler,
deployment, wallet, signer, transaction, swap execution, Git transport, A7
Catalog finalization and hypothesis unsealing remain forbidden.

This atom observes quotes. It does not trade, simulate fills, open a position,
calculate PnL, establish alpha, generalize to the market or prove that the
dataset is sufficient.
