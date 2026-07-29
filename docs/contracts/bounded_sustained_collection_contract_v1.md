---
contract_id: CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001
contract_version: "1.0"
task_id: TASK-15
atom_id: T15-A2_FROZEN_BOUNDED_MEASUREMENT_CONTRACT_V1
status: FROZEN_MEASUREMENT_NOT_DUE
as_of: 2026-07-29
cash_cap_usd: 0
provider_calls_in_atom: 0
contains_secrets: false
---

# TASK-15 hypothesis-driven acquisition and measurement contract v1

## 1. Decision

The Alpha Lab is a hypothesis factory, not a permanent market recorder.
Collection follows a named hypothesis and its validation needs; available
infrastructure does not create a reason to collect.

The acquisition order is frozen:

```text
THIN_ONLINE_DECISION_LEDGER
→ HISTORICAL_BATCH_FIRST
→ REUSABLE_CONTENT_ADDRESSED_CACHE
→ HYPOTHESIS_DATASET
→ TRIGGERED_LIVE_CAPTURE_ONLY_IF_HISTORY_IS_INSUFFICIENT
```

No named hypothesis data-requirement manifest exists at this checkpoint.
Therefore a sustained provider measurement is `MEASUREMENT_NOT_DUE`, and the
TASK-14 provider-purchase disposition remains `DEFER`.

## 2. Accepted architecture and prior-task compatibility

`ARCH-INTENT-001` is the current accepted direction:

```text
data spine
→ feature/context layer
→ hypothesis factory
→ falsification and OOS
→ frozen strategy
→ monitored lifecycle
```

TASK-03 through TASK-14 produced reusable primitives: Catalog and lifecycle
registries, PIT/lineage contracts, raw envelopes and storage guards, bounded
provider observations, lifecycle/Touch/quote/entity reducers, an offline
supervisor, an auditor and a provider decision. None requires a global
watchlist or an always-on production collector.

The imported TASK-01 coverage matrix remains useful as a domain taxonomy and
as a warning about irrecoverable evidence. Its `data_option_tiers_v1.yaml`
operational cadences and retention are historical proposals explicitly marked
`PROPOSED_NOT_ENFORCED_BEFORE_TASK16`. This contract supersedes any
interpretation that `T0_CORE` means global, dense or always-on collection.
Historical pre-Git bytes remain unchanged.

## 3. Hypothesis-owned lifecycle

There is no global detailed watchlist. Every detailed watchlist belongs to one
immutable hypothesis version and one validation or activation epoch.

Required ownership:

- `hypothesis_id` and `hypothesis_version`;
- `trial_id` or activation epoch;
- `policy_version`;
- research question, mechanism and falsifier;
- explicit population and control definitions;
- entry, monitoring and exit logic;
- regime/context requirements;
- data-requirement manifest and evidence checkpoint.

A token may belong to zero, one or several hypothesis watchlists. Membership
in one does not authorize data for another. A paused or dormant hypothesis
retains its historical evidence; reactivation creates a new epoch and never
rewrites an older decision.

Every membership/evaluation record retains:

- mint and optional pool identity;
- hypothesis, trial/epoch and policy versions;
- matched rule IDs and input-feature versions;
- admitted, rejected or not-evaluable result;
- reason and missingness codes;
- evaluated, entered and exited times;
- `first_reliable_available_at`;
- source and evidence checkpoint.

## 4. Required hypothesis data manifest

Before batch hydration or live capture, one immutable manifest must freeze:

- named hypothesis/trial consumer and research question;
- candidate population and rejected/control population;
- feature and label definitions;
- required fields, units, keys and timestamp semantics;
- cadence, lookback, validation window and retention;
- point-in-time availability and leakage rules;
- coverage class for every field:
  `RECONSTRUCTIBLE_LATER`, `FORWARD_ONLY`,
  `PARTIAL_OR_VENDOR_DEPENDENT` or `DERIVED_PIT`;
- preferred source, fallback and source revision policy;
- request/credit/storage/time caps;
- cheapest falsifier and stop conditions;
- live-capture justification, if any.

Cadence is not global. One hypothesis may need five-minute bars, another
one-minute liquidity, sparse news events, entity flows or a quote at the
decision checkpoint. A field or cadence without a named consumer is excluded.

## 5. Thin online decision ledger

The common online layer records only the information that cannot be honestly
reconstructed later:

- discovery/evaluation time and candidate identity;
- hypothesis, trial and policy versions;
- exact input feature values used by the rule;
- source revision and point-in-time availability;
- admit/reject/not-evaluable result and reason codes;
- missing fields, provider failures and coverage gaps;
- watchlist membership transitions;
- a quote/liquidity snapshot only when that value participated in the decision.

The ledger does not contain continuous price ticks, all provider envelopes or
rich data for every discovered token. It is append-only because a later
historical API can reconstruct market history but cannot prove what the system
actually knew or why it declined a trade.

## 6. Historical batch first

Reconstructible data is hydrated after the research question is named. A batch
may include:

- admitted watchlist members;
- candidates rejected by later filters;
- an explicitly sampled control cohort;
- a bounded broad historical universe when discovering new patterns rather
  than validating an existing filter.

This prevents winner-only and selected-candidate bias without requiring live
detailed storage for the whole Solana universe.

Fetched bytes are cached by source, query contract, revision and content hash.
Compatible hypotheses reuse the same cached asset. Derived datasets remain
versioned and reproducible; they do not duplicate raw bytes merely because a
new hypothesis consumes them.

Historical reconstruction records when the data was fetched and what history
the source claims. It never backdates `first_reliable_available_at` or claims
that the strategy observed the reconstructed row in the past.

## 7. Triggered live capture

Rich online capture is eligible only when all are true:

1. A named hypothesis manifest requires an exact field and cadence.
2. The field is forward-only, or a bounded historical-source check proves
   inadequate coverage, fidelity, revision behavior or delisted-token access.
3. The missing field can change the hypothesis verdict or execution estimate.
4. A cheaper cadence, narrower filter, batching and an existing cached source
   have been falsified.
5. A frozen watchlist/control fixture, hard budgets and deterministic stop
   conditions exist.
6. A separate external atom is explicitly authorized.

Examples include live quote/slippage, provider latency, transient liquidity,
short-lived news state and evidence needed to manage an open position. Live
capture stops with the hypothesis/epoch unless a separately named consumer
justifies reuse.

## 8. Bounded measurement admission

The acquisition-path gate returns exactly one:

- `HISTORICAL_BATCH_PATH_ACCEPTED`;
- `LIVE_MEASUREMENT_ELIGIBLE`;
- `MEASUREMENT_NOT_DUE`;
- `ACQUISITION_PATH_INCONCLUSIVE`.

At this checkpoint the result is `MEASUREMENT_NOT_DUE`: there is no immutable
hypothesis data manifest, no selected population and no historical-path
falsification. Inventing those inputs would measure an imaginary workload.

If a future hypothesis passes the live gate, the first separately authorized
measurement remains only a safety ceiling, not a default production shape:

| Pilot guard | Hard ceiling |
|---|---:|
| Hypothesis versions | 1 |
| Active candidate mints | 10 |
| Calibration | 1,800 seconds |
| Total window | 86,400 seconds |
| WSS connection attempts | 2 |
| Automatic retries/reconnects | 0 |
| Modeled provider credits | 40,000 |
| Metered uncompressed bytes | 1,999,900,000 |
| Local dataset bytes | 268,435,456 |
| Minimum free disk after allocation | 2,147,483,648 |
| Cash spend | USD 0 |

Actual field, request, subscription and cadence caps come from the named
hypothesis manifest and must be lower than or equal to these ceilings.

Using the accepted TASK-14 Helius convention:

```text
modeled_credits = 2 * ceil(uncompressed_bytes / 100000) + 1
```

`1,999,900,000` bytes model to `39,999` credits. Before any future connection,
the effective cap is further reduced to:

```text
min(40000, floor(0.10 * verified_remaining_monthly_credits))
```

A missing/stale allowance, a cap below 5,000 calibration credits, or a
calibration projection above the effective 24-hour credit/storage cap means
do not start or stop. It does not authorize widening the measurement.

## 9. Provider decision interpretation

Only a decision-valid, hypothesis-owned live measurement may later produce:

- `FREE_TIER_SUFFICIENT_CANDIDATE`;
- `PAID_PROPOSAL_ELIGIBLE_CANDIDATE`;
- `MEASUREMENT_INCONCLUSIVE`.

A free-tier candidate requires complete usage/coverage evidence and headroom.
A paid candidate additionally requires an exact named-consumer blocker and a
falsified historical, narrower and free path. Neither candidate changes an
account or authorizes a purchase.

If the historical batch path satisfies the hypothesis, no sustained provider
measurement is required and TASK-14 remains `DEFER` unless another named
consumer independently reaches its gate.

## 10. Explicit non-authority

Atom A2 authorizes zero:

- network, provider/API/RPC/WSS or dashboard calls;
- credentials, account changes or dependency adoption;
- global watchlist, all-token ticks or indiscriminate warehouse;
- collector, scheduler, deployment, VPS or unattended process;
- historical availability rewrite;
- subscription, prepaid credits, autoscaling or non-zero spend;
- strategy execution, wallet, signer or transaction actions;
- commit, push, PR, merge, settings, force or destructive actions.

Catalog registration and an acceptance receipt are deferred to
`T15-A3_DETERMINISTIC_ACCEPTANCE_AND_CATALOG_V1`.

## 11. Validation

`ADOPT`: `ARCH-INTENT-001`, TASK-01's domain taxonomy and TASK-03…14 reusable
PIT/provider/data-control primitives.

`WRAP`: hypothesis-owned acquisition precedence, an immutable fixture and
targeted deterministic tests.

`FORK`: none.

`BUILD`: no collector, generic feature platform or provider abstraction.

Atom A2 passes only when offline validation proves hypothesis ownership,
batch-first precedence, unbiased retrospective populations, live-capture
admission, bounded fallback measurement, prior-contract precedence and zero
side effects. TASK-15 remains in progress.
