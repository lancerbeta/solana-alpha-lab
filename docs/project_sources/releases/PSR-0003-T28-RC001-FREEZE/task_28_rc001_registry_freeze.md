---
task_id: TASK-28
semantic_version: "1.0"
status: FINALIZATION_REQUIRED_SOURCE_CANDIDATE_PENDING
as_of: "2026-08-09"
depends_on: [TASK-27]
contains_secrets: false
---

# TASK-28 — RC-001 research registry freeze

## Purpose

TASK-28 freezes the first three Blueprint experiment families before a future
research task can run them. Its consumer is a future named research-cycle
Entry Gate, which must be able to answer one simple question: is the exact
group admissible for a trial, and if not, why not?

This is not a data-collection task, a backtest, a trading strategy, a wallet
route or a source of PnL, NetReturn or owner cashflow.

## Delivered control record

`RESEARCH-CYCLE-RC001-001` contains exactly three immutable definitions:

1. `RC001-H13-COMPOSITE-VETO` — H13 composite toxicity veto.
2. `RC001-H07-H01-LIQUIDITY-RETENTION` — H07/H01 liquidity-retention continuation.
3. `RC001-H02-H10-H14-PULLBACK-RECLAIM` — H02/H10/H14 controlled pullback/reclaim.

All three are `BLOCKED_DATA`. The record preserves retained negative truth:
TASK-24's entity route is not admissible, TASK-27's named public-history route
has 63 of 96 bars `MISSING_UNKNOWN`, and TASK-25/26 do not prove settled
execution truth. Missing is never zero, flat, a continuous observed path,
fillability, settlement or alpha.

## Repository evidence

The task's offline register, schema, fixture, deterministic validation and
Catalog update were delivered at feature `7be75652ebe8ec9d867148ad42bae2320acc067d`,
PR #64 merge `3c51f02babc072cc5e202a8b15de49e874e9a529`, tree
`5e15f19ae2b5ed1f33dc900c140c80771015e643`, with post-merge main CI run
`31284090722` successful. The Factory Fit review passed with limitations:
the control layer is valid, but it is not evidence that any hypothesis is
ready to test or trade.

## Exact finalization boundary

This PSR-0003 bundle is a repository-validated replacement candidate based on
the already active PSR-0002 release. The owner must replace exactly five
mutable Project Sources (manifest, roadmap, current state, archive and this
active TASK-28 record), keep Operating System v8.5 and Blueprint v2.3
byte-for-byte unchanged, then return the provided manifest-first seven-role
smoke.

Until that smoke passes, the task remains
`FINALIZATION_REQUIRED_SOURCE_CANDIDATE_PENDING`. The smoke activates only the
Source release; it does not authorize a provider call, new data, a trial,
wallet, signer, transaction, cash spend or a next task.

## Hard limits and non-claims

Provider/API/RPC/WSS and credential use, R2/R3 reads, raw data retention,
wallet/signer/transaction/funding/cash/deployment actions, strategy promotion,
trial creation and holdout consumption are zero or forbidden. No next task is
selected by this record.
