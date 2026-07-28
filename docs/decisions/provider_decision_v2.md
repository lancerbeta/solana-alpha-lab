---
decision_id: DEC-T14-PROVIDER-PURCHASE-001
decision_version: "2.0"
task_id: TASK-14
atom_id: T14-A2_FROZEN_DEFERRED_PURCHASE_DECISION_V1
status: DEFER
as_of: 2026-07-29
pricing_snapshot_ttl_days: 30
cash_cap_usd: 0
provider_calls: 0
contains_secrets: false
---

# TASK-14 provider purchase decision v2

## 1. Decision

`DEFER`.

No paid provider plan is decision-valid at this checkpoint. TASK-13 accepted
the integrity of bounded retained evidence, but explicitly did not establish
sustained provider reliability, coverage or a purchase requirement. The
available runs also cannot establish that current free capacity is sufficient
for a sustained collector.

This disposition rejects a purchase now and requires a bounded usage
measurement before selecting either `NO_PURCHASE` or a paid proposal. It does
not authorize a provider call, account or dashboard action, credential use,
subscription, deployment, collector execution, wallet action or real money.

## 2. Why `DEFER`

The current evidence supports neither side of the capacity decision:

```text
seven-second bounded stream
-> useful byte-rate warning
-> not a sustained usage distribution
-> insufficient to prove either free-tier sufficiency or paid-tier need
```

`NO_PURCHASE` would overclaim that free access is sufficient.
`PROPOSE_BOUNDED_PURCHASE` would overclaim that the short sample represents
future usage. `DEFER` is the only decision that preserves both truths while
keeping cash spend at zero.

## 3. Evidence boundary

The decision consumes only tracked, sanitized evidence:

- TASK-07: 35 bounded provider attempts, 32 accepted successes, one invalid
  request and two retained provider 5xx responses; 15 modeled Helius credits
  and USD 0;
- TASK-08: one seven-second Helius stream with 600,238 Helius stream bytes and two
  Solana Tracker `401` access failures; lifecycle coverage remained
  `NOT_TESTABLE_IN_WINDOW`;
- TASK-10: eight public keyless Jupiter quotes passed at a 2.2-second pacing
  floor, below the current documented 0.5 keyless requests/second limit;
- TASK-11: three Helius standard RPC calls succeeded with 30 modeled credits
  and USD 0;
- TASK-13: 658 retained rows passed identity, PIT and projection checks, but
  sustained reliability, coverage and provider purchase remained explicitly
  unestablished.

The two TASK-08 Solana Tracker `401` rows are access-failure evidence. They are
not quota exhaustion, a provider reliability rate or proof that a paid plan
would fix access.

## 4. Observation-universe direction

The future collector must not become an all-token tick warehouse. Preserve two
separate layers:

1. a minimal discovery layer that reads only enough activity to evaluate
   explicit eligibility rules;
2. a detailed observation layer that persists decision-relevant data only for
   mints currently admitted to a versioned watchlist.

Watchlist membership is a first-class point-in-time event. Every admission,
continued membership and removal must preserve:

- `mint`;
- `policy_version`;
- matched rule IDs and linked hypothesis IDs;
- `entered_at`, `exited_at` and `first_reliable_available_at`;
- reason codes and the evidence checkpoint used by the decision.

Eligibility policy may evolve as hypotheses change. New policy versions apply
forward only: they never rewrite historical membership or pretend that a later
rule was available earlier. The ingestion, raw identity, PIT and storage spine
should remain stable while the policy layer changes.

The discovery layer must also be bounded. If standard program-wide
`logsSubscribe` is too broad, the later design must compare narrower
server-side filters, lower cadence, event-specific discovery or another
decision-valid source before paying for more volume.

Ultra-low-latency HFT capture, every Solana token, continuous all-token price
ticks and recording every low-level action are explicitly out of scope. The
current business problem needs reproducible hypothesis evidence, not
competition with colocated HFT infrastructure.

TASK-14 records this direction but does not implement the watchlist engine.
TASK-15/TASK-17 contracts must preserve it before any sustained collector run.

## 5. Current official pricing snapshot

Snapshot date: 2026-07-29. The machine-readable facts and official URLs are
frozen in
`tests/fixtures/task14/provider_purchase_decision_v1.json`.

| Candidate | Free/current boundary | Cheapest paid reference | Decision impact |
|---|---|---|---|
| Helius | USD 0, 1M monthly credits, 10 RPC requests/s, standard WebSockets | Developer list price USD 49/month, 10M credits, 50 requests/s | No sustained usage proves the free allowance insufficient |
| Solana Tracker Data API | EUR 0, 10,000 requests/month, 3 requests/s | Advanced EUR 50/month, 200,000 requests/month | Existing `401` is not a measured quota bottleneck |
| Solana Tracker RPC | EUR 1 one-time, 500,000 monthly credits, 5 requests/s | Developer EUR 35/month, 15M credits, 60 requests/s | Not the selected blocker and no switch is justified |
| Jupiter | Keyless access needs no signup and is documented at 0.5 requests/s; Portal Free is USD 0 at 1 request/s | Developer USD 25/month, 25M credits, 10 requests/s | Existing 0.455 requests/s pilot passed 8/8; no paid limit is hit |
| Birdeye | Standard USD 0, 30,000 compute units, 1 request/s, limited APIs | Lite USD 39/month, 1.5M compute units, 15 requests/s | No accepted consumer or measured gap justifies adding it |
| Raptor | Self-hosted is documented as free; hosted API remains public beta with no published plan price | None established | Optional research candidate, not a paid production SLA |

Helius cancellation is documented: cancellation from the billing dashboard
continues service through the current billing period, then reverts to free
limits. The public pages reviewed for the other paid references do not provide
a complete effective-date/refund/cancellation contract sufficient for a
purchase proposal. A future proposal must read those terms again at checkout.

The Helius docs and pricing page show a promotional Developer price alongside
the USD 49 list price. No proposal may use the promotion until the exact
checkout price, renewal price and cancellation terms are read back.

## 6. Directional Helius sensitivity warning

The only available traffic-volume proxy is deliberately weak:

```text
TASK-08 Helius stream bytes  = 600,238
observed wall window         = 7 seconds
current WSS metering         = 2 credits / 0.1 MB
directional one-day credits  = 148,175
directional seven-day credit = 1,037,213
directional 30-day credits   = 4,445,193
free monthly allowance       = 1,000,000
```

If the exact observed byte rate persisted, one seven-day pilot would consume
about 1.04 times the entire monthly free allowance, while 30 days would
consume about 4.45 times that allowance. Comparing only seven days with the
monthly cap understates the long-running capacity risk.

These values are sensitivity points, not forecasts and not a purchase trigger:

- the source window is only seven seconds;
- activity and message sizes vary;
- the retained byte count is only a proxy for provider-billed uncompressed
  message size;
- current dashboard usage was not read;
- no sustained collector contract has measured a confidence interval,
  peak rate or daily distribution.

The estimate therefore has `NON_DECISION_VALID_SENSITIVITY_ONLY` confidence.
It cannot establish either free-tier sufficiency or a paid-plan requirement.

## 7. Frozen reconsideration gate

A paid proposal becomes eligible only when all of the following are true:

1. A named downstream consumer is blocked by a specific endpoint, quota,
   streaming capability, historical depth or rate limit.
2. At least one separately authorized bounded measurement records usage,
   failures and coverage over a decision-valid window; a seconds-long smoke is
   insufficient.
3. The bottleneck cannot be removed by narrower filters, lower cadence,
   batching, current free/keyless access or an already accepted free
   candidate.
4. Current plan, checkout price, renewal, overage/autoscaling behavior,
   cancellation, refund and downgrade terms are read from official sources
   with a new `as_of`.
5. One cheapest sufficient plan has an explicit monthly and total cash cap,
   success/failure criteria, cancellation date and owner approval.

Until all five conditions hold, the required disposition remains `DEFER`.

## 8. Later zero-cash measurement boundary

This decision does not execute the measurement. A later task may propose a
separate external-run atom with:

- cash cap USD 0;
- explicit provider/API/RPC/WSS call and credit caps;
- a user-provided dashboard allowance read-back without exposing credentials;
- usage alerts and a fail-closed stop below the provider hard limit;
- coverage, latency, failure and byte/credit metrics;
- immutable sanitized receipts and no provider bodies in Git.

The later atom must stop before account changes, autoscaling, prepaid credits,
subscription or any non-zero spend.

## 9. Reuse, Catalog and architecture

`ADOPT`: existing TASK-07 through TASK-13 evidence and official provider docs.

`WRAP`: one frozen decision fixture plus deterministic offline validation.

`FORK`: none.

`BUILD`: no provider adapter, cost service, dashboard, scheduler or generic
procurement framework.

Catalog registration and generated navigation are deferred to a later TASK-14
finalization atom. This decision file and its fixture remain technical
candidates until that transaction and repository delivery pass.

## 10. Validation and next boundary

Atom 2 passes only if offline tests verify:

- the accepted result is exactly `DEFER`;
- paid proposals are ineligible under the current evidence;
- the directional estimate reproduces from frozen inputs;
- official facts are dated and carry a 30-day TTL;
- missing cancellation terms remain unknown rather than inferred;
- cash, provider calls, credentials, dependencies and wallet actions are zero;
- no tracked file contains a secret or machine-specific absolute path.

The next candidate atom is
`T14-A3_DETERMINISTIC_DEFER_ACCEPTANCE_V1`. It may create a sanitized
acceptance receipt and perform the bounded Catalog transaction. It may not
call a provider, read a dashboard, use credentials or spend money.
