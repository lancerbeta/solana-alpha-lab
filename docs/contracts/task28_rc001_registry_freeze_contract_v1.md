# TASK-28 — RC-001 registry freeze contract v1

## Consumer and decision

The consumer is the next named research-cycle entry gate. This contract tells
that gate whether it may open a trial for one of the three frozen RC-001
families. It is a control contract, not a signal generator, data collector,
backtest, execution adapter, or strategy promotion decision.

## Immutable definition boundary

`RESEARCH-CYCLE-RC001-001` contains exactly these ordered groups:

| Order | Group | Blueprint hypotheses |
| --- | --- | --- |
| 1 | `RC001-H13-COMPOSITE-VETO` | H13 |
| 2 | `RC001-H07-H01-LIQUIDITY-RETENTION` | H07, H01 |
| 3 | `RC001-H02-H10-H14-PULLBACK-RECLAIM` | H02, H10, H14 |

A group's canonical definition hash covers its identifier, blueprint
hypotheses, definition inputs, falsifier, target metrics, parameter policy,
requirements and explicit non-claims. A changed hash is a new definition; it
cannot be written over the old one.

The RC-001 register is task-owned: the config/evidence pair is the durable
record. TASK-16's empty lifecycle YAML skeletons are historical inputs and must
remain byte-for-byte unchanged. TASK-28 does not backfill, repurpose, or infer
new lifecycle history from them.

The global policy forbids trial record creation, holdout consumption, parameter
tuning, feature expansion, metric expansion, cross-group combination and
numeric `NetReturn` claims in TASK-28.

## Admissibility

The only admissibility states are `READY`, `LIMITED_DIAGNOSTIC_ONLY`,
`BLOCKED_DATA`, and `BLOCKED_EXECUTION_TRUTH`.

An unavailable or `MISSING_UNKNOWN` data/entity requirement produces
`BLOCKED_DATA`; an unsupported execution-settlement requirement produces
`BLOCKED_EXECUTION_TRUTH` only when no data/entity blocker exists. `READY`
requires every declared requirement to be `AVAILABLE` and is not permission to
collect, trade, or spend.

TASK-24's entity result, TASK-27's incomplete history panel, and TASK-25/26's
execution limitations are bound as negative constraints. They cannot be
reinterpreted as observed values, flat paths, fillability, settlement, or
alpha.

## Authority and non-claims

This contract permits only tracked local files, deterministic tests, Catalog
generation, ordinary Git delivery, and evidence review. Provider/API/RPC/WSS,
credentials, R2/R3, raw-data retention, wallet/signer/transaction actions,
cash spend, deployment, UI activation and Project Source modification are
forbidden.

TASK-28 makes no market, alpha, fill, fee, PnL, cashflow, `NetReturn`,
continuous-path, entity-membership, or holdout-consumption claim. Missing data
remains `MISSING_UNKNOWN`.

## Acceptance

Acceptance requires a strict schema, deterministic hashes, a golden three-group
fixture, task-owned register validation, preserved historical skeletons and an unchanged global trial ledger, and
adversarial rejection of a numeric `NetReturn` promotion, any external
authority, missing-to-zero coercion, duplicate definition, foreign feature,
unregistered parameter and premature `READY` state. The Factory Fit review is
`FULL_REVIEW` because this creates a durable research-control surface.
