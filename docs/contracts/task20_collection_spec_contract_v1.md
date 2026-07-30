---
contract_id: CONTRACT-T20-COLLECTION-SPEC-001
contract_version: "1.0"
task_id: TASK-20
atom_id: T20-A2_FROZEN_COLLECTION_SPEC_CONTRACT_V1
status: FROZEN_CONTRACT_NO_COLLECTION
as_of: "2026-07-30"
provider_calls_authorized: 0
cash_cap_usd: 0
contains_secrets: false
---

# TASK-20 collection specification contract v1

## 1. Owner decision

TASK-20 decides whether one versioned collection contract is sufficiently
bounded, hypothesis-owned and recoverable to become the semantic input for a
later collection plan:

```text
SPEC_READY
SPEC_READY_WITH_LIMITATIONS
SPEC_INCOMPLETE
COLLECTION_NOT_JUSTIFIED
```

This atom freezes the contract. It does not instantiate a TASK-21 runtime
plan, start collection or make `SPEC_READY` true by assertion.

## 2. Accepted starting point

TASK-15 already established the acquisition order:

```text
THIN_ONLINE_DECISION_LEDGER
→ HISTORICAL_BATCH_FIRST
→ REUSABLE_CONTENT_ADDRESSED_CACHE
→ HYPOTHESIS_DATASET
→ TRIGGERED_LIVE_CAPTURE_ONLY_IF_HISTORY_IS_INSUFFICIENT
```

TASK-19 proved `REPLAY_SAFE` only for one hypothesis version, one member,
three accepted windows and quote-only capacity curvature. That result proves
decision-time reconstruction for the accepted snapshot. It does not justify
a global watchlist, market-wide ticks or continuous capture.

The exact repository base is main
`0284a684c8791b8a06296e6c5f8546c8dd913198`, tree
`8837e888559be8945fffb4d4110268cc44ad2848`, with Catalog
`0.24.0 / 331 / 4 / 4 / 8`.

## 3. Universe and lifecycle

The collection universe is not all Solana tokens. A mint or pool becomes
eligible only because a named hypothesis version evaluates it under a
versioned candidate policy.

Every logical membership is keyed by:

- hypothesis family and immutable hypothesis version;
- trial or activation epoch;
- policy version;
- mint and optional pool;
- evaluation event and exact evidence checkpoint.

The append-only membership states are:

- `OUTSIDE`;
- `EVALUATED_REJECTED`;
- `EVALUATED_NOT_EVALUABLE`;
- `WATCHLIST_ACTIVE`;
- `WATCHLIST_EXITED`.

Rejected and not-evaluable candidates remain evidence. A token may be active
for several hypotheses, but membership in one never grants data authority to
another. Reactivation after exit requires a new activation epoch. No state
transition rewrites the earlier event.

## 4. Data tiers

### T0 — thin decision ledger

T0 records only evaluated candidates and decision-bearing facts that cannot
be honestly reconstructed later:

- evaluation and membership timestamps;
- hypothesis, trial/epoch and policy versions;
- exact rule inputs and their feature/source versions;
- admit, reject or not-evaluable result;
- reason, missingness and coverage-gap codes;
- membership transition;
- first reliable availability and evidence checkpoint;
- quote or liquidity value only if it participated in the decision.

T0 is event-driven. It is not a continuous price feed and is not authorized
for every discovered token.

### T1 — reusable historical or cached evidence

T1 is hydrated on demand after a named hypothesis consumer exists.
Reconstructible data uses historical batch first and a content-addressed cache
shared by compatible consumers. The initial candidate for bar-based intraday
research is one-minute bars, but `PT1M` is not a global cadence and does not
authorize collection. Every field may select a cheaper or sparser cadence.

Retrospective batches must preserve admitted members, relevant rejected or
not-evaluable candidates and explicit controls where the estimand requires
them. Winner-only hydration is forbidden.

### T2 — triggered live evidence

T2 is eligible only when every condition is true:

1. an immutable hypothesis data-requirement manifest names the field;
2. the field is forward-only or a bounded test proves historical evidence
   inadequate;
3. the field can change the hypothesis or execution verdict;
4. cheaper cadence, narrower population, batching and cache reuse have been
   falsified;
5. exact watchlist/control membership and hard budgets are frozen;
6. a separately authorized external atom exists.

T2 stops with the hypothesis or activation epoch unless another immutable
consumer independently justifies reuse. Speculative T2 and market-wide tick
capture are forbidden.

## 5. Field and availability contract

Every collected or derived field must declare:

- stable field ID, description, units and natural keys;
- tier and named consumers;
- source asset, source version and fallback policy;
- purpose and decision that the field may change;
- event-time, observed-time, ingest-time and availability semantics;
- coverage class:
  `RECONSTRUCTIBLE_LATER`, `FORWARD_ONLY`,
  `PARTIAL_OR_VENDOR_DEPENDENT` or `DERIVED_PIT`;
- cadence mode and exact cadence when scheduled;
- retention and revision policy;
- quality, freshness and missingness checks;
- request, credit, byte, storage and time attribution.

`first_reliable_available_at` is never inferred backward from event time.
Historical hydration records its fetch and source-revision truth and cannot
claim the strategy saw a row in the past. Late, revised, duplicated,
unavailable and not-evaluable data remains typed.

A field without a named consumer, decision purpose, availability rule or
bounded cost attribution is excluded.

## 6. Budget and economics

Budgets use stable physical units:

- provider requests and credits;
- response and stored bytes;
- active entities;
- wall-clock duration;
- concurrency and retry count;
- dataset bytes and minimum free-space reserve.

`UNLIMITED`, missing or negative caps are invalid. Price-plan names and USD
estimates are volatile advisory metadata with an `as_of` and expiry; they
cannot replace physical caps or authorize a purchase.

The TASK-15 40,000-credit, one-hypothesis, ten-candidate, 256 MiB ceiling is
retained only as the maximum inherited pre-TASK21 bounded-measurement
reference. It is not a TASK-21 budget and not collection authority. A future
runtime plan must freeze its own exact caps and remain within the accepted
owner decision.

## 7. Identity, compatibility and history

The canonical YAML is versioned. Any semantic change creates a new version,
decision and hash. Accepted prior bytes remain immutable.

Every future plan, run, raw event, partition, dataset and backup receipt must
bind:

- collection spec ID, version and exact content hash;
- hypothesis data-manifest ID, version and exact content hash;
- hypothesis/trial/epoch and membership evidence;
- source/revision and availability contract;
- budget policy and observed consumption.

No runtime maximum, latest file, mutable alias or UI filename suffix may
silently select a different contract.

## 8. Recovery handoff

TASK-18 proved one content-addressed snapshot can be recovered. It did not
prove periodic backup, overwrite protection for future collection or restore
automation.

TASK-20 A3 must therefore freeze:

- retention class and backup eligibility;
- content-addressed destination identity;
- no-clobber and duplicate behavior;
- backup cadence and trigger;
- manifest/read-back verification;
- isolated restore-test cadence and success evidence;
- degraded, overdue and evidence-loss states;
- owner, escalation and recovery deadline.

Until A3 accepts those rules, this contract authorizes no forward collection.

## 9. Reuse decision

`ADOPT`:

- TASK-15 hypothesis-owned acquisition precedence;
- TASK-05/TASK-06 dataset identity, immutable raw storage and budget guards;
- TASK-16 lifecycle identity;
- TASK-18 content-addressed backup/restore proof;
- TASK-19 point-in-time lineage and replay evidence.

`WRAP`: one declarative collection specification and deterministic tests.

`FORK`: none.

`BUILD`: no collector, scheduler, data warehouse, provider abstraction,
feature platform or monitoring backend.

## 10. Atom authority and next boundary

A2 writes only:

- `docs/contracts/task20_collection_spec_contract_v1.md`;
- `configs/collection_spec_v1.yaml`;
- `tests/test_task20_collection_spec_contract.py`.

It authorizes no provider/API/RPC/WSS or Drive call, raw/data write,
collection, credential, dependency, purchase, deployment, wallet, signer,
transaction, commit, push, PR, merge, UI change or destructive action.

Catalog registration is deferred to A4. The next atom is only
`T20-A3_COVERAGE_RETENTION_AND_RECOVERY_POLICY_V1`.
