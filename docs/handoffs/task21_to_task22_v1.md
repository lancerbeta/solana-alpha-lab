# TASK-21 to TASK-22 dataset handoff v1

## What TASK-22 receives

- immutable dataset: 91 files, 13 roots, 1,263,895 bytes;
- inventory SHA-256:
  aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae;
- private recovery bundle SHA-256:
  6d895f259f0316df442932b38abf44a963a79e16e24793a4eb1af2c5f6748361;
- five complete P0/P1/P2 members in two complete nomination clusters;
- three incomplete R1 members retained as explicit partial/gap evidence;
- 22 observed panels, 88 quote pairs and 176 quote attempts;
- outcomes unopened and historical bytes unchanged.

## First TASK-22 obligation

Before reading outcomes, create a deterministic dataset split and append-only
holdout-consumption ledger. Preserve nomination batch and member identity as
grouping keys. The default candidate is cluster-aware development versus
holdout separation; TASK-22 must test its feasibility and may choose a safer
design, but must never randomize members across a shared batch silently.

## Allowed claim

The dataset is eligible for narrow conditional analysis and pipeline
validation. It is not market-wide or cross-regime evidence, not a statistical
power claim and not alpha, NetReturn, strategy, position or production proof.

## Stop conditions

Fail closed on any path/hash drift, opened outcome before the split ledger,
silent backfill, member/batch leakage, missing recovery proof or claim
expansion. TASK-22 requires its own Entry Gate after TASK-21 repository delivery
and Finish Gate; this handoff grants no mutation or external authority.
