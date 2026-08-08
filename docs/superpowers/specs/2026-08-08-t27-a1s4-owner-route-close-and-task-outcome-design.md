# TASK-27 A1S4 — Owner route-close binding and task-outcome decision

**Status:** Design approved by owner on 2026-08-08
**Task:** `TASK-27`
**Atom:** `T27-A1S4_OWNER_ROUTE_CLOSE_BINDING_AND_TASK_OUTCOME_DECISION_V1`

## Purpose

Record the owner's exact decision after the A1S3 evidence review:

```text
ROUTE_CLOSE_ACCEPTED; NO_NEW_PROVIDER_READ
```

The atom makes that decision machine-checkable and turns it into a bounded
TASK-27 outcome proposal.  It prevents a later agent from treating A1S3's
former external-review boundary as an open permission or from silently
restarting the failed Solana Tracker route.

## Decision model

The record binds the exact A1S3 policy and acceptance artifacts, including
their paths and SHA-256 values.  It has exactly these effects:

- `current_route_disposition` remains
  `CLOSE_CURRENT_SOLANA_TRACKER_15M_POOL_HISTORY_ROUTE_NOT_FEASIBLE`;
- `owner_route_close` is `ACCEPTED`;
- `new_provider_read_authority` is `false`;
- `external_actions` remains `0`;
- the only allowed TASK-27 outcome proposal is
  `CLOSE_WITH_LIMITED_NEGATIVE_RESULT`.

The proposal means only that no feasible public-history route was demonstrated
within the frozen, owner-authorized route and read budget.  It does **not**
mean that all public providers, all pools, price/volume research, alpha,
execution, PnL, NetReturn, or cashflow are negative or impossible.

## Scope

The implementation creates a contract, policy configuration, JSON schema,
synthetic fixture, deterministic unit test, and acceptance receipt.  The
receipt is a durable control/evidence artifact; it does not rewrite A1S3,
retain raw provider data, alter a Project Source role, or claim TASK-27 is
already `DONE`.

The later TASK-27 finalization atom may consume this receipt to perform a
Factory Fit review, a Catalog transaction, a Project Sources replacement
candidate, repository delivery, and any required owner-only UI activation.

## Non-goals and hard boundaries

This atom must not:

- call GeckoTerminal, DexScreener, Solana Tracker, Helius, RPC, WSS, or any
  provider;
- select or evaluate another provider, URL, credential, quota, or retry;
- read, copy, retain, or reinterpret raw provider JSON;
- create or use a wallet, signer, transaction, quote, simulation, spend, or
  real-money authority;
- convert missing intervals into zero, flat, continuous, settled, or
  PIT-admissible observations;
- claim a cause for the A1S2 gaps;
- close TASK-27, mutate Project Sources, or edit generated Catalog files.

## Interfaces and validation

The policy is valid only when all of the following hold:

1. the exact A1S3 input paths and SHA-256 values are bound;
2. the owner decision is exactly `ROUTE_CLOSE_ACCEPTED` plus
   `NO_NEW_PROVIDER_READ`;
3. provider selection is null and all external/provider counters are zero;
4. the task outcome is limited to the named route and authorized scope;
5. alpha, execution, PnL, NetReturn, and cashflow claims remain false;
6. the acceptance receipt declares `state_change: NONE` and
   `project_sources_disposition: NO_CHANGE`.

The synthetic fixture and tests must reject a changed A1S3 hash, a provider
name, a non-zero read count, a market-wide conclusion, a positive research or
execution claim, a premature TASK-27 completion claim, and any conversion of
`MISSING_UNKNOWN` to a value.

## Planned files

- `docs/contracts/task27_owner_route_close_and_task_outcome_contract_v1.md`
- `configs/task27_owner_route_close_and_task_outcome_v1.yaml`
- `catalog/schemas/task27_owner_route_close_and_task_outcome.schema.json`
- `tests/fixtures/task27/owner_route_close_and_task_outcome_v1.json`
- `tests/test_task27_owner_route_close_and_task_outcome.py`
- `docs/evidence/task27/a1s4_owner_route_close_and_task_outcome_acceptance_v1.json`

## Recovery

The record is append-only.  Reconsidering public-history data in the future
requires a separate named consumer or hypothesis need, a new external-read
decision, a new bounded data contract, and a new owner authorization.  It
cannot be recovered by changing this record or replaying A1S2 raw data.
