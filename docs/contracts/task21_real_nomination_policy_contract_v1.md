# TASK-21 real nomination policy contract v1

`T21-A6R_FROZEN_REAL_NOMINATION_POLICY_V1` closes the selection gap between a
working collector and a defensible real watchlist. It freezes how candidates
may enter TASK-21; it does not choose tokens or start collection.

## Population and claim

The target population is the documented stream of forward nominations relevant
to the hypothesis factory. It is not all Solana tokens and cannot support a
market-wide prevalence claim.

A nomination may come from a versioned factory hypothesis, an owner research
nomination or a predeclared control cohort. Every source must be content-bound
and available before selection. Manual nominations remain valid, but their
claim is limited to the owner-nominated research population.

## Pre-outcome tranches

One runtime anchor is frozen before the first nomination. Candidate events are
accepted into three non-overlapping seven-day tranches with active-member caps
`3 + 3 + 2`. Each tranche is evaluated only after it closes and before the
first quote panel for that tranche.

Within a closed tranche, events are ordered by
`first_reliable_available_at`, `observed_at`, then `nomination_event_id`.
Unused capacity does not move between tranches. A late or backdated event
cannot reorder an already closed tranche.

This preserves three admission weeks without letting early quote outcomes
choose later members. Operational raw capture remains sealed from hypothesis
outcomes, and nomination inputs may not use route availability, terminal
class, quote output, price, cost, rank, PnL or alpha.

## Eligibility and retention

A member needs valid lineage, a valid non-reference Solana mint, known
decimals, an allowed source class, correct tranche timing and no prior relevant
quote-outcome exposure. No route-availability precheck is allowed: `NO_ROUTE`
is future evidence, not a selection filter.

The first nomination for a mint wins even if it is rejected. Exact duplicate
events deduplicate; conflicting duplicates fail closed. Missing decimals are
`EVALUATED_NOT_EVALUABLE`; reference assets, prior-outcome exposure, duplicate
mints and exhausted tranche capacity are `EVALUATED_REJECTED`. Every state is
retained. A successful member receives a content-addressed identity and an
append-only membership event at tranche close.

The previously observed TASK-10/A5 technical-probe mint is not automatically
carried into the blind primary cohort. Reusing it would require an explicit
non-primary control classification under a new policy version.

## Readiness and boundaries

Dataset sufficiency requires at least five active members across all three
tranches. Falling short does not permit changing the policy, adding
outcome-selected replacements or extending beyond the frozen eight evaluated
nominations.

The offline fixture proves deterministic ordering, admission and rejection
semantics only. It contains no market data and creates no real nomination or
member. Catalog registration remains owned by TASK-21 A7.

This atom performs zero provider/API/RPC/WSS or Drive calls, spends no cash,
uses no credentials, starts no scheduler, writes no forward dataset, and
performs no wallet, signer or transaction action. Real candidate input plus
collection and backup authority belong to the separately gated A6S stage.
