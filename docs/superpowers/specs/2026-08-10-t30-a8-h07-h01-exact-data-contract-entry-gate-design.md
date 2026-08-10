# T30-A8 H07/H01 exact data contract entry gate — design

## Status and durable re-entry

- Design status: `SPEC_REVIEW_REQUIRED`.
- Parent task: `TASK-30`.
- Selected atom: `T30-A8_H07_H01_EXACT_DATA_CONTRACT_ENTRY_GATE_V1`.
- Design approved by owner: `T30_A8_DESIGN_APPROVED`.
- Base main: `bc2740deee558b51e5400f3f3e5de53c764b1bb9`.
- Base tree: `9b9e1f3d520c144b20826ad010666306c85d0131`.
- Entry verdict: `SPLIT`.
- Control plane: `LOCAL_WORK_PRIMARY`; repository route: `LOCAL_WORK_CODEX`.

New-thread rule: read this design, current `AGENTS.md`, the Project Sources
release registry, TASK-28's frozen H07/H01 group, TASK-26B, TASK-27 and
TASK-30 A6/A7 receipts.  This atom does not choose a provider or execute a
capture.  It decides whether an explicitly bounded future data lane could
remove a named blocker, while retaining the independent execution-truth
blocker.

## Owner outcome

The owner gets one short Russian-language answer to a simple question:

> What exact data would make the H07/H01 question less unknown, and what
> would that data still be unable to prove?

The answer must distinguish market history from route feasibility and actual
owned settlement.  It must not call a price panel an experiment, a quote an
execution, or a missing interval a zero.

## Decision and scope

T30 A7 freezes the following requirements:

1. point-in-time liquidity-retention state;
2. multi-notional route persistence;
3. post-migration continuation context; and
4. settled execution truth before a numeric NetReturn or a full trial.

These are different truth classes.  A single OHLCV capture can at most
contribute to the first class.  It cannot establish route persistence and can
never establish owned attempts, inventory or settlement.  Therefore the next
step is an offline data-contract split, not another provider read.

The evaluator returns exactly one of:

- `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT`;
- `REDESIGN_DATA`;
- `CLOSE_ROUTE`.

`PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT` means only that a later owner-approved
PIT market or route-feasibility capture has a named, bounded consumer.  It
does not make H07/H01 trial-admissible and retains
`SETTLED_EXECUTION_TRUTH_UNAVAILABLE` as an independent blocker.

## Considered approaches

### Selected: exact three-lane contract

Bind every frozen requirement to one of three evidence lanes, its fields,
point-in-time timestamps, admissibility and recovery rule.  A pure evaluator
then determines whether a prospective capture can remove a specific
`MISSING_UNKNOWN` state without promoting the whole hypothesis.

This is the cheapest falsifier: if a requirement cannot name a sufficient
lane and fields offline, an external request would be collection without a
decision contract.

### Rejected now: collect another 96 OHLCV bars first

It may test cadence or data availability, but it cannot answer multi-notional
route persistence, migration context or settlement.  The earlier 33/96 panel
already shows why completeness must be specified before collection.

### Rejected now: build a generic capture platform

The current TASK-30 modules are 120–306 lines, substantially smaller than the
older TASK-21 foreground-capture family.  A shared framework has not yet
earned its own abstraction.  Reuse is enforced by a trigger below rather than
by speculative infrastructure.

## Data lanes and minimum fields

| Lane | Frozen consumer | Minimum fields and PIT semantics | May establish | Explicitly cannot establish |
| --- | --- | --- | --- | --- |
| `PIT_MARKET` | liquidity-retention state | pool, mints, DEX/program identity, closed interval, OHLCV, liquidity state, observed/available/ingested times, revision or source hash, typed gap | a bounded market-history input with known completeness | route persistence, fill, fees, inventory or settlement |
| `ROUTE_FEASIBILITY` | multi-notional route persistence | evaluated time, input/output mint, notional, route identifier/status, quoted amounts, price impact, separate fees, observed/available/ingested times, typed failure | route availability at named notionals | a fill or owner settlement |
| `OWNED_EXECUTION` | settled execution truth | stable attempt/retry IDs, signature, terminal state/time, token and SOL deltas, fees, inventory before/after, reconciliation reference and raw hashes | owner attempt, inventory and settlement truth | nothing in this atom; this lane remains future canary-only |

The `POST_MIGRATION_CONTEXT` requirement may consume a bounded `PIT_MARKET`
identity/timeline record only when it binds the migration/program/pool context
and both sides of the continuity boundary.  Price continuity alone is
insufficient.

## Components and data flow

The minimal implementation surface is:

1. a versioned contract and YAML configuration declaring the frozen binding,
   requirements, three lanes, field sets and non-claims;
2. a JSON Schema and tracked synthetic fixture representing a complete and
   incomplete lane matrix;
3. one pure Python evaluator that returns the terminal decision, each
   requirement's state and an owner-oriented explanation;
4. focused unit/adversarial tests;
5. a structured acceptance receipt plus an owner-readable report; and
6. normal Catalog/generated propagation once at final delivery.

```text
TASK-28 frozen definition + T26B/T27/T30 receipts
                         |
                         v
              exact requirement-to-lane matrix
                         |
                         v
                 pure offline evaluator
                         |
         +---------------+----------------+
         |                                |
         v                                v
owner readout                  future owner gate template
no external authority          only if a named lane is sufficient
```

No provider adapter, scheduler, transport, credentials, raw body, database,
wallet, signer or transaction code belongs in this atom.

## Fail-closed and recovery behavior

The evaluator fails with a typed negative result rather than guessing when it
observes any of the following:

- `SOURCE_BINDING_CONFLICT`: a referenced receipt, frozen group or hash is not
  the expected one;
- `UNMAPPED_REQUIREMENT`: a frozen requirement has no lane and field list;
- `AMBIGUOUS_PIT_SEMANTICS`: a proposed field lacks observed, available or
  ingested-time meaning where PIT use needs it;
- `FALSE_PROMOTION`: price-only, quote-only or missing evidence is used to
  claim trial, fill or settlement;
- `UNRECOVERABLE_CAPTURE_WITHOUT_COVERAGE`: a future decision-critical raw
  capture lacks a registered backup/restore route or explicit tracked waiver;
- `REUSE_TRIGGER_UNRESOLVED`: a future capture implementation would duplicate
  more than 150 orchestration-specific lines or introduces a second new
  consumer without a documented `ADOPT → WRAP → FORK → BUILD` assessment.

Only `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT` can lead to a later external
authority packet.  It still requires a separate provider, fields, cadence,
cap, retention and stop-condition decision.  Any unresolved prior execution
attempt remains a block on an owned retry under TASK-26B/26C rules.

## External-audit assimilation

The design preserves the decision-relevant part of the external repository
audit without importing its interview-score narrative or creating a new debt
registry.

- Input SHA-256:
  `9ef775756f35199b073acfea0e52db228da9b4d08c30b1194e3d7b1b88886da1`.
- Accepted now: capture reuse must be checked prospectively; decision-critical
  raw evidence requires restore coverage or a waiver.
- Deferred with trigger: move historical baseline policy into data only if the
  existing fast-path observation window sees recurring repair commits or the
  next 50 commits again touch `scripts/validate_baseline.py` materially.
- Deferred by stage: type checking, scheduled dependency audit, cross-platform
  hook, dependency cleanup and test taxonomy do not advance the current
  H07/H01 evidence bottleneck.

The future acceptance receipt repeats these dispositions and checks the two
active triggers.  This gives the audit a durable, queryable trail without
turning it into a parallel roadmap.

## Deterministic tests

The test suite must prove at least:

1. all frozen requirements are mapped once and only once;
2. a complete `PIT_MARKET` lane remains partial and cannot open a trial;
3. an OHLCV-only lane is rejected for route persistence, migration context and
   settlement;
4. a quote is rejected as settlement and a missing field is rejected as zero;
5. an `OWNED_EXECUTION` claim is rejected unless its canary-only state remains
   explicit;
6. missing PIT timestamps or typed gap handling returns a negative result;
7. decision-critical irrecoverable capture without backup/waiver is rejected;
8. the prospective reuse threshold requires an explicit assessment instead of
   silently copying a task module;
9. every authority and side-effect counter remains zero; and
10. renderer output is deterministic and contains the owner non-claims.

Tests use synthetic fixtures only.  They do not read a provider, local raw
root, credential or wallet.

## Validation, delivery and non-claims

During implementation, run targeted evaluator, contract, Catalog and
generated-view tests.  Before delivery, apply the repository's tracked-only
preflight once to the exact candidate, then use exact-head PR and post-merge
main CI as independent validation owners.

This atom does not authorize provider/API/RPC/WSS calls, credential use,
raw-data capture or retention, R2/R3 access, a scheduler, dependency changes,
wallet/signer/transaction actions, cash spend, numerical NetReturn, trial
admission, strategy promotion, TASK-30 acceptance or Project Sources changes.

## Spec self-review

- Placeholders: none.
- Consistency: the selected partial-PIT result retains the independent
  execution-truth blocker throughout.
- Scope: one contract/evaluator/readout slice; no data collection or generic
  platform.
- Ambiguity resolved: a backup route or explicit waiver is required before
  future decision-critical irrecoverable capture, not for this offline atom.
