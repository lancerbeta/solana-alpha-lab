# TASK-23 bounded diagnostics contract v1

Status: `FROZEN_PRE_READ`
Task: `TASK-23`
Atom: `T23-A2_FROZEN_BOUNDED_DIAGNOSTICS_CONTRACT_V1`
Machine-readable authority: `configs/task23_bounded_diagnostics_v1.yaml`

## 1. Purpose and decision

This contract freezes the smallest reproducible diagnostic read of the accepted
TASK-22 development population. It exists to decide whether the three-member R2
cohort contains enough descriptive evidence to proceed, extend evidence, redesign
data collection, or stop. It does not test alpha, profitability, execution, or a
general population claim.

The only allowed terminal decisions for this diagnostic stage are:

- `DIAGNOSTICS_READY_WITH_LIMITATIONS`
- `EXTEND_EVIDENCE`
- `REDESIGN_DATA`
- `STOP_NO_INFORMATION`

No decision is permitted before the A3 outputs pass the frozen denominators,
missingness, provenance, and actual-time checks in this contract.

## 2. Accepted base and pre-read seal

The contract is bound to accepted `origin/main` commit
`90575accefbba7da534a6bd89b3652b2644a278b` and tree
`f9cdd82ad8df427abe35e577889adaaca22b2d12`. Entry Gate verdict is
`START_AS_WRITTEN`; route is `LOCAL_WORK_PRIMARY/LOCAL_WORK_CODEX`.

The frozen dataset identity is inventory
`aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae`,
split `T22-SPLIT-T21-FROZEN-002`, split manifest
`973a9ff6dd2a376e62dee9289a57cbb62f06c8efb5a619fa6b7b2a7914dd0683`,
and split content
`63b6d63895bdd6d25b68501619bca21e10f476a95ad8d27611f356a26cccee2d`.

The R2 raw values remain unopened in A2. Before the first A3 value read, the
operator must write an immutable pre-read receipt that binds the exact contract
and config SHA-256 values, frozen split and input hashes, allowlisted R2 roots,
member set, actor, reason, timestamp, current holdout-ledger hash, and R3 denial.
The receipt must exist before any file-open operation against a value-bearing R2
path. A failed receipt write aborts the read.

## 3. Population boundary

Primary development population is exactly TASK-22 split `R2`, batch `T21-R2`,
one capture cluster and these three members:

- `T21-WATCH-29e2b75994975253bd74`
- `T21-WATCH-6f21dec76d05f5831216`
- `T21-WATCH-61ce24fc3fa04e3eaba7`

Validation population is `NONE`.

R1 is auxiliary gap/coverage metadata only: three members and three missing
panels. R1 values cannot be read, pooled with R2, or included in any R2
denominator.

R3 is the untouched holdout, batch `T21-R3`. R3 access is `DENY`: no path
discovery, value read, outcome read, statistics, labels, joins, or derived
inspection. This A2 contract does not consume a holdout and does not change the
holdout ledger.

## 4. Frozen questions

Only five questions may be answered:

1. `Q1_PANEL_COMPLETENESS`: which planned R2 panels and quote legs are observed,
   absent, dead, stopped, or failed?
2. `Q2_ROUTE_AVAILABILITY`: at which fixed tested notionals do buy and dependent
   sell quotes return routes, with explicit planned and observed denominators?
3. `Q3_QUOTE_NOTIONAL_CAPACITY_PROXY`: what is the largest tested notional with
   both a buy route and its dependent sell route for each member/panel?
4. `Q4_ACTUAL_TIME_CHANGE`: how do the descriptive quote-only measures vary by
   actual elapsed and availability time?
5. `Q5_INFORMATION_LIMITS`: which missingness, dependence, and sample-size limits
   prevent a stronger decision?

New selection-affecting questions require a new version and a trial-ledger entry.

## 5. Actual-time semantics

`P0`, `P1`, and `P2` are capture-window identifiers, not claims of nominal 15m,
30m, 60m, or 4h horizons. Every comparison uses recorded timestamps:
`requested_at`, `response_at`, `first_reliable_available_at`,
`available_to_strategy_at`, and `ingested_at`. Elapsed time is derived from
actual timestamps and reported in seconds. Missing or inconsistent timestamp
ordering is a typed data-quality failure, never silently imputed.

## 6. Quote panel and capacity proxy

Each planned panel contains fixed USDC buy inputs of USD 10, 25, 50, and 100,
represented as 10,000,000; 25,000,000; 50,000,000; and 100,000,000 atomic units.
A sell quote is dependent on an accepted buy quote and uses exactly that buy
output amount. If the buy is unavailable, the sell is `SELL_NOT_ATTEMPTED`; it is
not a zero quote and cannot enter an observed-sell denominator.

`quote_notional_capacity_proxy_usd` is the maximum tested input whose buy and
dependent sell both have `QUOTE_AVAILABLE`. It is a censored quote-notional
proxy on the tested grid. It is not pool liquidity, market depth, fillable size,
realized VWAP, execution capacity, NetReturn, alpha, or owner cashflow.

`roundtrip_quote_retention_bps` equals dependent sell output atomic units times
10,000 divided by the original buy input atomic units. It is quote-only and does
not include execution, settlement, latency, retries, all fees, inventory risk, or
cash costs. Raw `priceImpactPct`, when present, is parsed as an exact decimal and
reported descriptively; it is never a substitute for fill or realized impact.

## 7. Allowed fields and provenance

The A3 reader may open only `raw_events.jsonl` under the three exact R2 roots in
the machine-readable config. It must reject symlinks/reparse escapes and any
resolved path outside those roots. It may retain only the allowlisted envelope,
normalized `quote_attempt`, and validated raw-response fields. Raw route plans are
reduced to route count and a content hash; raw provider payloads are not emitted.

The reader must verify schema, task, atom, batch, member, window, request hash,
raw-content hash, normalized response hash, mint/amount identity, quote side, and
timestamp provenance before deriving a metric. Decimal fields must not pass
through binary floating point.

## 8. Denominators and missingness

Every rate must publish numerator, denominator, denominator definition, and the
excluded typed states. At minimum, planned panels, observed panels, planned buy
legs, observed buy legs, eligible dependent sells, and observed dependent sells
remain separate denominators.

`MISSING` is never `0`. Retained states include `QUOTE_AVAILABLE`, `NO_ROUTE`,
`PROVIDER_ERROR`, `INVALID_RESPONSE`, `TIMEOUT`, `SELL_NOT_ATTEMPTED`,
`PANEL_MISSING`, `CAPTURE_DEAD`, `CAPTURE_STOPPED`, and
`TIMESTAMP_INVALID`. Negative and failed observations remain in reproducible
outputs.

## 9. Dependence and non-claims

There is one capture cluster and three R2 members. Members and repeated windows
may share event, market, provider, and capture-process shocks. The analysis is
descriptive only: no IID assumption, p-values, confidence intervals, standard
errors, statistical power claims, causal language, extrapolation, or population
generalization. Member-level rows and cluster identity stay visible; repeated
observations are not promoted to independent samples.

## 10. Trial and output discipline

Every selection-affecting rerun, parser change, metric change, exclusion change,
or question change must receive an append-only trial record before results are
used. The global trial ledger is read-only in A2. Negative results and failed
runs are retained. Query/config identity is content-addressed.

A3 outputs are limited to reproducible machine-readable tables plus a concise
Markdown diagnostic. Charts, if later requested, are views over those tables and
cannot become truth owners. No web UI, dashboard, provider call, Drive read,
external API, or new dependency is authorized.

## 11. Reuse route

`ADOPT`: TASK-22 split, time profile, holdout ledger, A6 acceptance, TASK-10
Jupiter quote-state classifier, TASK-05 QuoteAttempt schema, PIT/replay/query
primitives, and the global trial ledger.

`WRAP`: this contract, its config, and fail-closed contract tests.

`FORK`: none. `BUILD`: none in A2. A3 may implement only the smallest local
projection required by this frozen contract after a separate continuation gate.
No reusable software acquisition gate is triggered because A2 adds no software
dependency or external service.

## 12. Authority and next boundary

A2 may write only:

- `docs/contracts/task23_bounded_diagnostics_contract_v1.md`
- `configs/task23_bounded_diagnostics_v1.yaml`
- `tests/test_task23_bounded_diagnostics_contract.py`

Catalog registration is deferred to A5. Planned stable IDs are
`CONTRACT-T23-BOUNDED-DIAGNOSTICS-001`,
`CONFIG-T23-BOUNDED-DIAGNOSTICS-001`, and
`TEST-T23-BOUNDED-DIAGNOSTICS-CONTRACT-001`.

This contract authorizes neither A3 nor any data-value read. After A2 validation,
the exact next boundary is a separate owner continuation into
`T23-A3_DETERMINISTIC_R2_DIAGNOSTIC_PROJECTION_V1`, followed by the pre-read
receipt. R3 remains untouched until its own durable activation trigger.
