# TASK-28 RC-001 registry freeze — design

## Decision

Implement the roadmap's first research-cycle freeze as a small offline
research-control layer. It will preserve the three intended RC-001 experiment
families, their permitted search degrees and their evidence dependencies before
any new trial is created. It will not treat a planned hypothesis as an
executable experiment merely because it appears in the research blueprint.

The selected design is **freeze plus admissibility**: every frozen experiment
has both an immutable definition and an explicit current trial-admissibility
state. A blocked prerequisite remains visible as a blocker; it is never
silently converted into a threshold, zero, flat path, settlement fact or
positive/negative result.

## Context and evidence

- The activated TASK-27 close receipt records a route-specific negative result:
  the named history route supplied 33 of 96 required natural 15-minute bars,
  while 63 remain `MISSING_UNKNOWN`.
- TASK-24's entity route is retained as `NOT_ADMISSIBLE` downstream. It cannot
  supply a ready H13 entity/bundle veto input.
- TASK-25 and TASK-26 preserve quote/path truth but explicitly do not establish
  actual fills, complete fees, settlement or numeric `NetReturn`.
- The immutable Research Blueprint v2.3 names the first three RC-001 families:
  H13 composite veto; H07/H01 liquidity-retention continuation; and
  H02/H10/H14 controlled pullback/reclaim.
- Existing research-cycle, hypothesis and feature registries are still empty;
  the global trial ledger contains only retained earlier diagnostics. No
  RC-001 trial exists.

## Alternatives considered

1. Freeze all three families as immediately runnable. Rejected: it would hide
   known entity, history and settlement gaps and make a future experiment look
   more admissible than the evidence permits.
2. Defer the whole research cycle until every future data surface exists.
   Rejected: that loses the cheap protection against search drift and lets the
   first eventual experiment redefine itself while data are being obtained.
3. Freeze definitions, parameter families and decision rules now; bind each
   family to an explicit `READY`, `LIMITED_DIAGNOSTIC_ONLY`,
   `BLOCKED_DATA`, or `BLOCKED_EXECUTION_TRUTH` admissibility state. Selected:
   it preserves optionality without manufacturing evidence.

## Design

### One RC-001 control record

`RESEARCH-CYCLE-RC001-001` will own the pre-registered question: whether any
of the three named, execution-aware experiment families can survive a frozen
development/validation route and later a separately consumed holdout. Its
business consumer is the owner decision to spend the next unit of research time
on a testable family rather than on an unbounded parameter search.

The record freezes:

- one experiment-family order: H13, then H07/H01, then H02/H10/H14;
- primary outcomes, secondary risk outcomes and explicit non-claims;
- each allowed parameter family and the rule that `null`, unresolved or
  unavailable inputs are not tunable thresholds;
- the single multiplicity family and a global trial-accounting rule;
- a time, cash and trial-count budget with zero provider and cash authority;
- a named invalidation condition and the required next decision after an
  inconclusive or blocked result.

No `trial` record is created by this task. A research plan is not a completed
trial and cannot consume a holdout.

### Three frozen hypothesis groups

The implementation will create one immutable versioned definition for each
group, retaining the Blueprint identifiers as provenance labels:

| Frozen group | Blueprint source | What it may claim now |
|---|---|---|
| `RC001-H13-COMPOSITE-VETO` | H13 over H04/H05/H06/H07/H08/H16 | Only a pre-registered veto comparison; never a ready entity signal or execution result. |
| `RC001-H07-H01-LIQUIDITY-RETENTION` | H07 + H01 | Only a pre-registered incremental liquidity/route question; not a continuous price-path result. |
| `RC001-H02-H10-H14-PULLBACK-RECLAIM` | H02 + H10 + H14 | Only a pre-registered reclaim question; not a price, buyer or NetReturn claim. |

Each version declares its data requirements, evidence asset IDs, allowed
features, unavailable requirements, falsifier, target metrics and downstream
consumer. A version is immutable after its canonical definition hash is
computed. A material change creates a new version and retains the prior record.

### Admissibility is a separate truth layer

The deterministic validator derives and verifies admissibility from declared
requirements and bound evidence. It must distinguish a frozen definition from
a runnable trial:

- `BLOCKED_DATA` for a missing or route-specific unavailable data requirement;
- `BLOCKED_EXECUTION_TRUTH` for a required fill, fee, settlement or numeric
  NetReturn claim without evidence;
- `LIMITED_DIAGNOSTIC_ONLY` when data permit a descriptive, non-promotional
  projection but not the planned experiment;
- `READY` only if all required evidence bindings are present and the contract
  permits the requested trial class.

The first RC-001 snapshot is expected to retain explicit blocks where evidence
is insufficient. That is a valid and useful outcome, not task failure.

### Registry and Catalog boundaries

Reuse the existing TASK-16 lifecycle graph and existing YAML registries; do not
introduce a second research-memory service, database, notebook platform or
generic experiment engine. Add only the records, contract/config/schema,
synthetic fixture, deterministic validator and acceptance evidence necessary to
make RC-001 queryable and reproducible.

Catalog entries will cover every new task-owned artifact and its relations to
the existing TASK-16, TASK-24, TASK-25, TASK-26 and TASK-27 evidence. Generated
navigation is regenerated only through the repository generator.

## Required rejection cases

The acceptance suite must reject at least:

- a completed or planned RC-001 trial that is absent from the global ledger;
- a parameter, feature, metric or FDR family outside the frozen definition;
- a `READY` state that omits a required evidence asset or declares an
  unavailable entity/history input as observed;
- `MISSING_UNKNOWN` converted to zero, flat, continuous, settled or fillable;
- any numeric `NetReturn`, actual-fill, settlement or R3 claim;
- duplicate or mutable frozen-definition identities;
- a feature borrowed from another family without an explicit versioned link;
- any provider/API/RPC/WSS, credential, wallet, signer, transaction, spend,
  dependency or external-service action.

## Delivery shape

The task is staged but remains one bounded offline objective:

1. Contract/config/schema plus golden and adversarial fixture.
2. Deterministic validator and immutable RC-001 registry records.
3. Catalog transaction, generated navigation, Factory Fit review and delivery.

Every behavior change follows a red-green test cycle. The full gate runs once
as a tracked-only delivery preflight after the exact commit; ordinary feature
work uses targeted tests plus the existing full unit-test baseline.

## Out of scope

No provider reads, raw-data retention, R2/R3 access, holdout consumption,
execution simulation, wallet, signer, transaction, cash spend, external
dependency, live/paper strategy, strategy promotion, numeric `NetReturn`,
Project Source replacement or UI action belongs to TASK-28.

## Rollback and stop conditions

Before delivery, rollback is removal of the uncommitted TASK-28 changes. After
delivery, corrections are additive: a superseding frozen version or decision
record; prior research definitions and negative evidence remain intact.

Stop and return to the owner only if a proposed definition needs a material new
data source, a new economic budget, a changed estimand, holdout/R3 access, or
any execution authority. A blocked admissibility result alone does not require
owner intervention; it is the intended evidence output.
