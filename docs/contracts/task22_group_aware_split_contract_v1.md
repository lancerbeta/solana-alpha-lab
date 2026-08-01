# TASK-22 group-aware split and holdout contract v1

## Purpose

TASK-22 must create the exam boundary before anyone sees the answers. This
contract freezes how the accepted TASK-21 dataset may be separated into
development and untouched holdout evidence, and what must be recorded when a
future trial opens that holdout.

This atom reads no outcome values and materializes no split. It converts the
Entry Gate finding into a machine-readable contract for A3.

## Accepted starting point

The exact repository base is main
`2ff5a9de4e78a8e64b23754ff59680a33c01d3cc`, tree
`3af1179da534972ccf82073dfe1594858c69516e`, with Catalog
`0.26.1 / 374 assets / 4 shards / 4 schemas / 8 queries`.

TASK-21 accepted one immutable, remotely recoverable dataset:

- inventory SHA-256
  `aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae`;
- 91 files, 13 roots and 1,263,895 stored bytes;
- five complete members in two complete nomination clusters, R2 and R3;
- three incomplete R1 members retained as partial and gap evidence;
- 22 observed panels, 88 quote pairs, 176 quote attempts and three explicit
  missing panels;
- outcomes remain unopened.

The accepted claim is only narrow conditional analysis and pipeline
validation with limitations. Nothing in this contract upgrades sample size,
market coverage, alpha or executable economics.

## Entry Gate patch

Two complete independent clusters cannot honestly populate three independent,
non-empty roles. Therefore this contract does not force
`development + validation + holdout` merely because those labels are familiar.

For the current two-cluster dataset, the only admissible candidate is:

```text
earliest complete cluster  -> DEVELOPMENT
validation                 -> NONE
latest complete cluster    -> HOLDOUT, initially UNTOUCHED
incomplete R1              -> AUXILIARY_GAP_AND_COVERAGE_EVIDENCE
```

This is provisional until A3 proves chronology and consumer-specific
purge/embargo feasibility. If that proof is missing or fails, the result is
`EXTEND_EVIDENCE`. A forced three-way split, row-level random split or use of
partial R1 as a cosmetic validation fold is forbidden.

## Group identity and deterministic ordering

The primary split unit is `nomination_batch_id`; `member_id` is nested inside
it. No member or shared nomination batch may cross folds. Members are not IID
rows.

Complete groups are ordered by:

1. `source_observed_at` ascending;
2. `batch_id` ascending as the stable tie-break.

With exactly two complete groups, the earlier group is the development
candidate and the later group is the holdout candidate. This rule uses only
frozen provenance, not outcomes. A changed group count, member identity,
timestamp or dataset hash creates a new split decision; it never silently
changes this contract.

R1 remains queryable as incomplete evidence. Its gaps cannot be filled,
dropped or relabelled to improve the sample.

## Chronology, purge and embargo

Batch order alone does not prove temporal independence. R2 and R3 were
observed sequentially on the same day, so an attractive timestamp gap cannot
be treated as an independent regime or as automatic protection against label
overlap.

Before an analysis becomes eligible, its named consumer must declare:

- maximum feature lookback;
- label horizon;
- the rule for `label_first_reliable_available_at`;
- execution or settlement lag when applicable.

A3 must remove development units whose label-availability window overlaps the
holdout feature or label window. Holdout access starts only after the declared
label and availability boundary. Feasibility must be checked across the
project's 15-minute to 4-hour horizon bounds without reading outcome values.

Unknown, ambiguous or infeasible chronology returns `EXTEND_EVIDENCE`. It does
not grant permission to shorten the horizon after seeing results.

## Feasibility verdicts

Exactly one result is permitted:

- `SPLIT_READY_WITH_LIMITATIONS` — two complete groups, exact identities and
  consumer time rules pass; development and untouched holdout are assigned,
  while validation is explicitly `NONE`;
- `EXTEND_EVIDENCE` — a provisional two-group ordering exists but purge,
  embargo or usable evidence is unknown or insufficient;
- `DATASET_NOT_SPLITTABLE` — fewer than two complete groups, identity drift,
  broken freeze or premature outcome access;
- `REDESIGN_SPLIT` — a new dataset identity adds enough complete groups to
  require a new versioned design.

No verdict is statistical power, alpha, NetReturn or production evidence.

## Outcome seal

The current state is `UNOPENED`. A2 permits zero outcome reads. A split is not
accepted until A3 writes content-addressed partition identities and the
holdout access policy while the seal is still intact.

Opening outcomes before that point fails closed as
`DATASET_NOT_SPLITTABLE` for this dataset version. Outcome, feature, threshold
and strategy tuning cannot influence group assignment, chronology rules or
ledger design.

## Append-only holdout consumption

The existing `holdout_consumption` lifecycle registry supplies the stable
append-only destination, but its current generic record schema is too small
for TASK-22. A3 must reuse it through an additive compatible schema or a
validated companion record; historical registry bytes remain valid and are
not rewritten.

Every future access must record at least:

- split and dataset hashes;
- holdout partition hash;
- research cycle, hypothesis version and trial;
- actor, timestamp and reason;
- exact query or code hash and decision receipt;
- prior and resulting holdout state.

The initial state is `UNTOUCHED`. The first actual access changes it to
`CONSUMED`. `CONSUMED` never returns to `UNTOUCHED`; a redesigned experiment
requires a new forward holdout identity.

Read access and authority are separate. A ledger schema never authorizes an
outcome read by itself.

## Reuse and Catalog boundary

`ADOPT`:

- TASK-21 content-addressed dataset and effective-sample evidence;
- the existing holdout registry and lifecycle schema as compatibility inputs;
- existing stable IDs, PIT timestamps and immutable-history rules.

`WRAP`: one TASK-22 split contract plus deterministic contract tests.

`FORK`: none.

`BUILD`: none in A2. A3 may add only the smallest compatible split/ledger
schema and deterministic materializer required by this contract.

Catalog registration is deferred to A4. This does not block freezing the A2
contract, but it blocks TASK-22 DONE.

## Explicit non-claims and authority

A2 authorizes no:

- outcome read, raw-data read beyond frozen identity metadata, dataset write,
  overwrite, backfill or deletion;
- provider/API/RPC/WSS or Google Drive call;
- dependency adoption, collection, scheduler, deployment or purchase;
- hypothesis, feature, threshold or strategy optimization;
- market-wide, cross-regime, power, alpha, Fillable, NetReturn, position, PnL
  or production-readiness claim;
- credential, wallet, signer, transaction or real-money action;
- commit, push, pull request, merge, UI or destructive action.

A2 writes exactly:

- `docs/contracts/task22_group_aware_split_contract_v1.md`;
- `configs/task22_group_aware_split_v1.yaml`;
- `tests/test_task22_group_aware_split_contract.py`.

The next boundary is only
`T22-A3_DETERMINISTIC_SPLIT_AND_HOLDOUT_LEDGER_V1`. A2 does not authorize it.
