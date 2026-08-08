# TASK-28 — RC-001 research registry freeze

## Purpose

TASK-28 turns the first three Blueprint experiment families into a small,
versioned, offline research-control record. It gives the future research
operator one answer to a simple question: which hypothesis family is frozen,
which evidence is still missing, and therefore whether a trial is admissible.

It does not collect market data, execute a trial, open a holdout, create a
strategy, or promote alpha.

## Frozen RC-001 sequence

1. `RC001-H13-COMPOSITE-VETO` — H13 baseline with composite toxicity veto.
2. `RC001-H07-H01-LIQUIDITY-RETENTION` — H07/H01 liquidity-retention
   continuation.
3. `RC001-H02-H10-H14-PULLBACK-RECLAIM` — H02/H10/H14 controlled
   pullback/reclaim.

All three definitions belong to `RESEARCH-CYCLE-RC001-001`. A definition may
be referenced later, but it may not be silently broadened: new features,
parameters, outcomes, universes, or data routes require a new versioned
definition and a new owner decision.

## Current truth

TASK-24 retained its entity route as not admissible for a strategy veto.
TASK-27 closed its named public 15-minute history route with 63 of 96 required
bars remaining `MISSING_UNKNOWN`. TASK-25 and TASK-26 preserve useful outcome
and execution boundaries but do not establish actual fills, complete fees,
settlement, or numeric `NetReturn`.

Consequently this task freezes a research plan, not runnable alpha. Its
admissibility records may be blocked; that is correct evidence, not a failed
market hypothesis.

## Definition of done

- exactly three schema-valid frozen groups and one research-cycle identity;
- deterministic offline admissibility evaluation with explicit blocker codes;
- one task-owned, hash-bound register in config/evidence, while TASK-16's
  historical lifecycle skeletons remain byte-for-byte unchanged;
- golden and adversarial tests reject scope expansion, evidence promotion,
  missing-to-zero coercion, trial creation and external authority;
- Catalog registration and a `FULL_REVIEW` Factory Fit receipt;
- no provider/API/RPC/WSS, credential, R2/R3, wallet, transaction, cash,
  dependency, Project Source, or UI action.

## Next boundary

The first operational trial is outside TASK-28. It can be proposed only after
a named future task supplies the blocked evidence under its own data and
authority contract. No blocked state becomes `READY` merely because a future
operator wants to run it.
