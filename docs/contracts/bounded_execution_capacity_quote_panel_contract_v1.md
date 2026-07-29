---
contract_id: CONTRACT-T17A-EXECUTION-CAPACITY-QUOTE-PANEL-001
contract_version: "1.0"
task_id: TASK-17A
atom_id: T17A-A2_FROZEN_CAPTURE_CONTRACT_V1
status: FROZEN_OFFLINE_CONTRACT
as_of: "2026-07-29"
hypothesis_version_id: HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1
watchlist_id: HYP-WATCHLIST-EXECUTION-CAPACITY-V1
current_member_count: 1
current_provider_call_cap: 24
outer_provider_call_ceiling: 192
provider_calls_in_atom: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-17A bounded execution-capacity quote panel contract v1

## 1. Entry verdict and owner decision

The read-only Entry Gate returns `START_WITH_PATCH`.

TASK-17 established `LIVE_NON_RECONSTRUCTABLE_NEED`: historical chain state
cannot reconstruct a provider quote response, route or error class, provider
version, or local request/receipt timing for an unobserved size sweep. The
retained TASK-10 panel is one useful point, not a population estimate.

The current decision is narrower than the TASK-17 outer ceiling:

```text
for the one provenance-safe TASK-10 mint
→ does quote-only round-trip cost still rise from USD 10 to USD 100
→ across three separately invoked point-in-time windows
→ enough to keep or reject a size-curve requirement for this mint
```

This contract cannot generalize the result to other tokens. A cross-token
claim requires another watchlist version, another frozen contract and another
provider authority gate.

## 2. Frozen hypothesis watchlist

`HYP-WATCHLIST-EXECUTION-CAPACITY-V1` has one member:

| Member | Mint | Decimals | Membership reason |
|---|---|---:|---|
| `HYP-WATCH-MEMBER-T10-001` | `4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump` | 6 | `RETAINED_TASK10_CAPACITY_WARNING_WITH_TASK09_PROVENANCE` |

The member is copied from the accepted TASK-10 plan. Its selection rule was
`SOLE_NON_WSOL_MINT_IN_ACCEPTED_TASK09_GETTRANSACTION_TOKEN_BALANCES`.
Selection did not use later price movement, profitability, quote availability
or route quality.

The TASK-17 ceiling of eight members is retained as an outer bound only.
Seven empty slots do not authorize discovery, hydration or arbitrary mint
admission. Adding a member creates a new watchlist version.

## 3. Three bounded trigger windows

The exact window IDs are:

1. `T17A-WINDOW-01`
2. `T17A-WINDOW-02`
3. `T17A-WINDOW-03`

Each window begins only through a foreground control-plane invocation under
the future exact A3 authority. Windows are not a daemon, cron job, background
collector or always-on monitor. Consecutive windows must be separated by at
least 1,800 seconds and all three must start within 86,400 seconds of the
first. A missed window becomes explicit coverage loss; it is not silently
rescheduled.

One future A3 approval may cover all three named windows, but it does not
remove the foreground invocation, separation, total-span or stop conditions.
Each invocation binds its window ID, trigger time and hypothesis/watchlist
versions before the first request.

## 4. Provider surface and pacing

The only compatibility surface is:

```text
GET https://api.jup.ag/swap/v1/quote
provider_version = legacy_metis_v1_quote
claim = LEGACY_QUOTE_COMPATIBILITY_ONLY
```

Official Jupiter documentation observed on 2026-07-29 says:

- Metis Swap v1 is superseded by Swap V2 and is not actively maintained;
- `api.jup.ag` currently allows keyless requests without sign-up;
- keyless access is capped at 0.5 requests per second;
- higher-rate plans require an account/API key and are outside this task.

The frozen request pacing floor is 2.2 seconds, concurrency is one and retries
are zero. Authentication, account creation, an API key, a paid plan, a
fallback host, a V2 transaction/instruction surface or undocumented route
ends the run.

Primary documentation snapshots:

- `https://developers.jup.ag/docs/swap/v1/get-quote`
- `https://developers.jup.ag/docs/portal/setup`
- `https://developers.jup.ag/docs/portal/plans`

Documentation is compatibility evidence, not an endpoint probe. A2 performs
no quote request.

## 5. Panel and sequential legs

The input quote mint is canonical Solana USDC
`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`, with six decimals.

| USD notional | Buy input USDC atomic |
|---:|---:|
| 10 | 10,000,000 |
| 25 | 25,000,000 |
| 50 | 50,000,000 |
| 100 | 100,000,000 |

For every notional:

1. BUY uses the frozen USDC atomic input.
2. SELL uses the exact accepted BUY `outAmount` without float conversion or
   re-rounding.

If BUY is unavailable, SELL is
`NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED`. It is not `NO_ROUTE`.

The planned maximum is:

```text
1 member × 3 windows × 4 notionals × 2 legs = 24 calls
```

The old 192-call value remains an architectural ceiling and cannot be consumed
by this contract.

## 6. Typed outcomes and raw evidence

Every attempted request retains one TASK-06 raw envelope and one exact attempt
ledger row. Allowed terminal classes are:

- `QUOTE_AVAILABLE`;
- `NO_ROUTE`;
- `PROVIDER_ERROR`;
- `INVALID_RESPONSE`;
- `TIMEOUT`;
- `NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED` for a dependent SELL only.

Missing is not zero. Timeout, 4xx, 5xx, rate limit and schema drift are not
`NO_ROUTE`. A transaction or instruction payload is
`INVALID_RESPONSE/TRANSACTION_PAYLOAD_FORBIDDEN` and stops the current panel.

Each retained attempt binds request identity, provider/endpoint version,
hypothesis/watchlist/window/member IDs, exact atomic amounts, response or
failure class, route hash/count when present, context slot, PIT timestamps,
latency, raw-content hash and call ordinal. Raw bodies stay outside Git.

## 7. Caps, retention and observability

Per window:

- at most eight calls;
- request timeout at most 20 seconds;
- wall time at most 300 seconds;
- received bytes at most 1,048,576;
- durable raw bytes at most 5,242,880.

Across the contract:

- at most 24 calls;
- received bytes at most 3,145,728;
- durable raw bytes at most 15,728,640;
- concurrency one;
- retries zero;
- credentials/accounts/API keys zero;
- cash USD 0;
- wallet/signer/transaction actions zero.

Keyless usage has no account meter. The attempt ledger is the authoritative
usage receipt. For cost sensitivity only, the current generic documentation
default of one credit per non-listed request gives a modeled ceiling of 24
credits; it is not a billed-credit claim.

Retention reuses `R1_T0_RAW`: raw quote/error payloads remain hot for 90 days,
then replayable through research-cycle close plus 365 days. Hashes, manifests,
sanitized aggregates and the decision record remain for project lifetime.
No deletion action is performed by A2.

## 8. Stop conditions and authority

Stop before or during A3 on:

- missing exact A3 owner authority;
- hypothesis/watchlist/member/window drift;
- authentication, account or key requirement;
- provider/endpoint or response-schema drift;
- pacing, call, byte, timeout, wall or total-span cap exhaustion;
- a request outside the frozen member/window/notional set;
- dependency, schema or migration change requirement;
- transaction/instruction payload;
- any wallet, signer, transaction, deployment or real-money requirement.

`T17A-A2_FROZEN_CAPTURE_CONTRACT_V1` is offline. It authorizes no
provider/API/RPC/WSS call, raw live write, scheduler, account, credential,
purchase, deployment, wallet, signer, transaction, signal, strategy,
position, fill, PnL, NetReturn or alpha claim.

The exact next boundary is `T17A-A3_BOUNDED_EXTERNAL_QUOTE_PANEL_V1` for no
more than the 24 calls frozen here. It requires separate owner authority.
