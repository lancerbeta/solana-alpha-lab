---
contract_id: CONTRACT-T21-FORWARD-COLLECTION-RUN-PLAN-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A2_FROZEN_FORWARD_COLLECTION_RUN_PLAN_V1
status: FROZEN_PLAN_NO_COLLECTION
as_of: "2026-07-30"
contains_secrets: false
---

# TASK-21 forward collection run plan contract v1

## 1. Decision and truth boundary

This contract decides whether one bounded, hypothesis-owned collection window
is specified tightly enough to enter the separate runtime recovery gate. It
does not activate a hypothesis, select or call a provider, admit a token,
start a collector, deploy a service, create a backup, spend cash or produce a
dataset.

The Entry Gate verdict is `START_WITH_PATCH`. The patch prevents three common
forms of false progress:

- interpreting 30–45 elapsed days as continuous market-wide recording;
- inflating the accepted 192-call hypothesis need into a larger budget before
  measurement proves that expansion useful;
- hiding candidate-selection bias by retaining only admitted winners.

The owner decision remains:

```text
can one exact plan collect decision-relevant point-in-time evidence
for HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1
without tuning on the future dataset or exceeding frozen physical caps
```

## 2. Population and generalization

The collection window accepts only candidate nominations with immutable
provenance. Every evaluated candidate is retained as one of:

- `EVALUATED_REJECTED`;
- `EVALUATED_NOT_EVALUABLE`;
- `WATCHLIST_ACTIVE`;
- `WATCHLIST_EXITED`.

Unused watchlist capacity does not authorize discovery, and the plan contains
no global Solana feed. A candidate nomination must bind the source asset,
source version/hash, observation and first-reliable-availability timestamps,
rule inputs, policy version, reason codes and evidence checkpoint.

At most eight unique candidates may be evaluated and at most eight may become
active members. This deliberately narrows the earlier outer member ceiling; a
future need for a broader intake requires a new plan version and owner
decision.

The resulting dataset can generalize only to the documented nomination and
admission process. It cannot establish market-wide prevalence, unbiased token
coverage or cross-domain alpha.

## 3. Time window is not a polling instruction

The run envelope lasts at least 30 and at most 45 calendar days. It is an
opportunity window for forward-only candidate admissions and triggered quote
panels, not permission to poll every token continuously.

For each admitted member:

- exactly three planned foreground panels;
- minimum accepted separation of 1801 seconds;
- all panels close within 86,400 seconds of the first panel;
- four notionals: USD 10, 25, 50 and 100;
- each available buy is followed by an exact-atomic reverse-sell quote;
- no retry and no silent reschedule of a missed panel.

A panel uses at most eight provider calls. Eight members therefore produce an
outer ceiling of 192 calls for the whole 30–45-day task, not per day.

## 4. Physical caps and cost

The authoritative caps are:

| Unit | Hard maximum |
|---|---:|
| unique evaluated candidates | 8 |
| active watchlist members | 8 |
| provider calls | 192 |
| modeled provider credits | 192 |
| received response bytes | 25,165,824 |
| durable raw bytes | 125,829,120 |
| dataset bytes | 268,435,456 |
| concurrency | 1 |
| retries | 0 |
| wall time | 3,888,000 seconds |
| minimum free disk after allocation | 2,147,483,648 bytes |
| cash | USD 0 |

The credit cap is a conservative one-credit-per-attempt model, not a billed
credit claim. Exact attempt, byte, latency and any provider meter observed
later must be retained independently. A provider that cannot fit these caps
fails the plan; the plan does not silently adopt a paid tier.

The current pricing snapshot is dated 2026-07-29 and expires 2026-08-28. A
fresh official documentation and checkout read-back is mandatory before the
live shakedown because the collection window can outlive this snapshot.

## 5. Information sufficiency and stopping

Elapsed time alone never returns `DATASET_READY`.

At day 30 the task may stop successfully only if all are true:

- at least five members have three complete panels each;
- at least 15 complete panels and 60 complete quote pairs exist;
- admitted members span at least three distinct UTC admission dates and three
  distinct UTC weeks;
- coverage, physical caps and runtime recovery health reconcile;
- no hypothesis statement, notionals, outcome rule or watchlist rule changed
  after seeing forward outcomes.

If these conditions are not met, collection may continue unchanged until day
45. At day 45 the task stops regardless. Insufficient evidence produces
`EXTEND_EVIDENCE`, `REDESIGN_DATA`, `COLLECTION_NOT_JUSTIFIED` or
`STOPPED_SAFELY`; extension requires a new owner decision and plan version.

The absence of provider errors, no-route cases or missing data is reported as
an observed limitation. The plan does not manufacture a failure quota.

## 6. Outcome blindness

During collection, operators may inspect only operational fields required to
protect evidence:

- process and recovery health;
- request, byte and disk caps;
- coverage, missingness and freshness;
- terminal-class counts and incident state.

Capacity-curve results, hypothesis verdicts and token ranking are sealed until
collection stops and the dataset freeze begins. TASK-21 cannot change
hypothesis parameters or membership rules in response to those outcomes.
TASK-22 owns the deterministic dataset split and holdout ledger.

## 7. Hard recovery boundary

Before the first forward byte, `TASK21_PRE_COLLECTION_RUNTIME_RECOVERY_GATE`
must prove:

- a private destination in a separate failure domain;
- create-only content-addressed writes;
- exact remote read-back;
- isolated sample restore;
- backup and restore health alerts;
- no secret material in evidence.

Policy text, a local ZIP or a successful upload without restore evidence is
not sufficient. The 24-hour backup target, 26-hour overdue state, 48-hour T2
admission stop and P7D sample restore cadence remain inherited from
`RETENTION-RECOVERY-T20-001`.

## 8. Reuse and build boundary

`ADOPT`:

- TASK-06 immutable raw envelopes, manifests and storage-budget guards;
- TASK-12 deterministic single-process supervisor controls;
- TASK-17 hypothesis identity and 192-call data need;
- TASK-17A quote-panel semantics and pacing lessons;
- TASK-18 content-addressed packaging and isolated restore verifier;
- TASK-20 collection and recovery policies.

`WRAP`: provider-neutral plan binding and deterministic validation.

`FORK`: none.

`BUILD`: none in A2. A4 may build or wrap only missing runtime pieces after a
fresh reuse check. APScheduler, Celery, Temporal, a generic data platform and
a monitoring backend remain unjustified.

## 9. Catalog compatibility debt

The TASK-20 acceptance test still freezes global Catalog version `0.25.0` and
340 assets. Before the first TASK-21 Catalog bump, it must preserve the exact
historical TASK-20 receipt while accepting monotonic current Catalog growth
and continuing to verify TASK-20-owned assets exactly. This is a bounded
compatibility repair, not authority for a broad test refactor.

The three A2 artifacts remain `CATALOG_TRANSACTION_PENDING_T21_A7`.

## 10. Authority and next boundary

A2 writes only:

- `docs/contracts/task21_forward_collection_run_plan_contract_v1.md`;
- `configs/task21_forward_collection_run_plan_v1.yaml`;
- `tests/test_task21_forward_collection_run_plan.py`.

It authorizes no provider/API/RPC/WSS or Drive call, credential, candidate
admission, raw/dataset write, collector execution, backup, restore, purchase,
deployment, dependency change, wallet, signer, transaction, commit, push, PR,
merge, UI change or destructive action.

The next boundary is
`T21-A3_PRE_COLLECTION_RUNTIME_RECOVERY_GATE_V1`. It requires separate exact
destination and write authority and still does not automatically authorize
forward collection.
