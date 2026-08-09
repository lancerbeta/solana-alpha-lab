# TASK-30: hold historical route and prepare forward price capture — design

**Status:** `DESIGN_APPROVED_2026-08-10`
**Atom:** `T30-A6_BIRDEYE_ROUTE_HOLD_AND_FORWARD_PRICE_CAPTURE_DECISION_V1`
**Mode:** offline decision only; no provider request, credential use, raw-data write, scheduler, wallet, transaction, cash spend, TASK-30 trial, acceptance, or Project Sources change.

## 1. Decision being made

TASK-30 needs a trustworthy 15-minute price/volume input. The current
historical routes do not supply it:

- Gecko returned 96 records, but the timestamp label and zero-volume semantics
  remain unresolved;
- Solana Tracker returned 33 of the required 96 records;
- Birdeye accepted the pair-level input but returned HTTP 429 for the one
  permitted OHLCV read.

The Birdeye result is neither proof that the pair lacks history nor proof that
Birdeye lacks the required surface. It is an exact, rate-or-quota-limited
observation.

The owner wants to convert this uncertainty into a steadily growing usable
history. The correct response is a narrow forward-capture candidate, not
unbounded retries or market-wide polling.

## 2. Alternatives considered

### A. Wait and retry Birdeye automatically

Rejected. A recovered quota would only remove one access blocker. It would not
resolve the existing timestamp, coverage, availability, or no-trade semantics.
Automatic retries also make free-tier quota consumption unbounded.

### B. Begin broad, high-frequency collection from every available provider

Rejected. It creates a large, incomparable cache before there is a named data
contract. More calls do not establish price units, candle boundaries,
availability, or empty-interval semantics. The result would be expensive in
quota and operator attention even if cash cost remains zero.

### C. Hold the historical Birdeye route and design one bounded forward panel

Recommended. It preserves the exact negative evidence, lets the project own
the observation timestamp going forward, and makes the next external decision
small and reversible.

## 3. Recommended design

### 3.1 Historical Birdeye route

Set the route state to `HOLD_NO_AUTORETRY`.

This is not a permanent provider rejection. Reopening it requires both:

1. evidence that the applicable quota or access condition has changed; and
2. a new exact owner authorization that names the provider, pair, request cap,
   endpoint and retention rule.

No retry, fallback, or interpretation of HTTP 429 is permitted by this atom.

### 3.2 Forward price/volume capture candidate

The candidate is deliberately small:

| Property | Frozen candidate rule |
| --- | --- |
| Consumer | A future TASK-30 history-feasibility decision, not a trial or strategy |
| Population | One already frozen public pool only: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` |
| Research unit | A received observation associated with one closed 15-minute UTC slot |
| Initial horizon | One 24-hour pilot, at most 96 scheduled observations |
| Provider | Not selected by this atom; one provider only in the later exact gate |
| Storage | Existing local, content-addressed raw/manifest and recovery patterns; outside Git |
| Retention of failure | A missed slot, malformed response or quota refusal remains a typed gap |
| Expansion | No second pool, provider, day, cadence change or background extension without a new decision |

The panel records the fact that a source response was observed after a known
slot. It must retain at least `slot_open_at`, `slot_close_at`, `observed_at`,
`ingested_at`, request identity, response hash, provider response timestamp if
present, and a typed terminal state. A source's candle timestamp is retained
as received; it is not silently re-labelled as start or end of interval.

### 3.3 How 96 observations are made without manual work

The later implementation will use one local scheduled runner on the owner
machine. It starts a single bounded command shortly after each 15-minute UTC
slot closes, writes one idempotent receipt, and exits. It is not an always-on
bot, does not discover tokens, and does not trade.

The runner will have a visible daily health receipt. If the machine is asleep,
the network is down, the provider refuses the request, or the run is late, the
affected slot is recorded as a gap. It is never backfilled and never converted
to a zero-volume or flat-price bar. The owner therefore does not need to click
96 times, while the data remains honest about what was actually observed.

The scheduler itself is not built or activated by this atom. It is an external
and operational boundary for the later, separately authorized pilot.

### 3.4 Cadence and quota discipline

One observation per completed 15-minute slot is the minimum cadence that can
form a 15-minute forward panel. Sampling every minute is not a default
improvement: it multiplies quota use sixteenfold without solving the data
contract. A denser revision/availability audit is allowed only when a future
consumer specifically needs to measure revisions and has a separately frozen
quota cap.

The later pilot must freeze a maximum request count before the first call. The
candidate ceiling is 96 provider requests for the 24-hour, single-pool pilot,
with zero retries and concurrency one. Provider-specific credit accounting
remains unknown until the provider is selected; a free account is not treated
as an unlimited budget.

### 3.5 Reuse boundary

Adopt from TASK-20/TASK-21:

- content-addressed raw manifests and retention boundaries;
- idempotent slot/run identity and conflicting-duplicate rejection;
- physical caps, typed gaps and no-silent-reschedule behavior;
- recovery and daily health concepts.

Do not reuse as price data:

- Jupiter quote values or the TASK-21 execution-capacity panel;
- its technical probe as a watchlist admission;
- its provider endpoint or its 30–45-day collection plan.

No generic data platform, multi-provider abstraction, dashboard, dependency or
background service is in scope.

## 4. Future external decision boundary

After this offline decision, a separate Entry Gate may inspect official
documentation for the already available providers and choose one surface. A
later owner authorization must state the exact provider, endpoint, credential
transport if any, pool, 24-hour request cap, schedule, raw retention location,
and stop rules.

Before it can start, deterministic tests must show that the runner rejects:

- a second pool or provider;
- a duplicate slot with changed bytes;
- a retry after a non-success response;
- a request beyond the daily cap;
- a source timestamp promoted to unproven candle semantics;
- a missing slot promoted to no trade, zero volume or flat price;
- a run when health or recovery evidence is missing.

## 5. Non-claims

This design does not establish a historical panel, an admissible OHLCV
contract, no-trade semantics, alpha, a strategy, execution, fills, settlement,
PnL, numeric NetReturn, a working scheduler, provider access, or TASK-30
acceptance.

## 6. Delivery shape after spec approval

The implementation plan will create a compact offline decision contract,
configuration, schema, synthetic fixture, pure evaluator, acceptance receipt,
Catalog bindings and targeted tests. It will make no network request and will
not start forward capture. A full implementation/activation of the scheduled
pilot is intentionally a later, separately authorized task.
