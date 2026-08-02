# TASK-25 frozen outcome label and PIT contract v1

## 1. Purpose and status

- Task: `TASK-25 Outcome engine v1`.
- Atom: `T25-A2_FROZEN_OUTCOME_LABEL_AND_PIT_CONTRACT_V1`.
- Status after validation: `VALIDATED_CONTRACT_ONLY`.
- Route owner: `LOCAL_WORK_PRIMARY`; execution route: `LOCAL_WORK_CODEX`.
- Accepted base commit: `be15889e103caaf92b7e34c9f98b7fd6378eed2e`.
- Accepted base tree: `ed5d2a788080f1535074e78e0f66ffbe07afbab8`.

This atom freezes the meaning of outcome labels before any TASK-21 R2 outcome values are
opened. It uses synthetic examples only. It does not calculate a cohort outcome, consume a
holdout, inspect R3, call a provider, or establish alpha, PnL, NetReturn or owner cashflow.

The owner decision eventually unlocked by TASK-25 is whether frozen R2 evidence can support
a narrow, point-in-time-safe outcome comparison without turning a price observation into an
execution claim. The contract deliberately keeps `Touch`, `Fillable`, `QuoteExit`,
`RealizedVWAP`, `Net` and `PathRisk` separate.

## 2. Simple model: six different questions

| Label | Question answered | Minimum admissible evidence | What it never proves by itself |
|---|---|---|---|
| `TOUCH` | Did an admissible reference price reach the frozen threshold in the declared horizon? | A complete reference path, or an actually observed grid point that crosses the threshold | A route, quote, fill, settlement or profit |
| `FILLABLE` | Was a buy route quoted for one exact input notional within frozen freshness and latency limits? | A contemporaneous `QUOTE_AVAILABLE` observation at the exact atomic notional | An attempted or settled trade |
| `QUOTE_EXIT` | Was a sell route quoted for the exact declared inventory amount? | A contemporaneous sell `QUOTE_AVAILABLE` observation at the exact atomic amount | Liquidation, flat inventory or settlement |
| `REALIZED_VWAP` | What return was realized by actual executions? | Reconciled actual fills and execution references | Net return after all costs |
| `NET` | What remained after settled trading and project cash costs? | Complete settled cashflow and cost attribution | A value when the fee/cashflow model is incomplete |
| `PATH_RISK` | What adverse path evidence was observed? | An explicitly scoped complete path, discrete grid, or terminal path-state observation | Continuous MAE/MFE from sparse panels |

The labels are not a ladder whose upper rungs may be inferred from lower ones. In
particular, `TOUCH` does not imply `FILLABLE`, a quote does not imply `REALIZED_VWAP`, and
missing evidence does not imply the numeric value zero.

## 3. Truth axes are independent

Every evidence row carries an `assessment` and four independent state axes:

- `assessment`: `SUPPORTED`, `REFUTED`, `UNKNOWN` or `NOT_APPLICABLE`;
- `route_state`: quote availability, explicit no-route, stale observation, provider error,
  invalid response, timeout or not applicable;
- `fill_state`: actual reconciled fills, actual fills not observed or not applicable;
- `cashflow_state`: settled complete, fee model unavailable, cashflow not observed or not
  applicable;
- `path_state`: continuous complete, sparse discrete, pool dead, missing exit, unobserved or
  not applicable.

These axes cannot repair one another. A provider error is not `NO_ROUTE`. A quote with no
fills remains a quote. A zero remaining inventory cannot be claimed while recovery is
unresolved. `UNKNOWN` and `NOT_APPLICABLE` require `value_decimal = null` and `unit = null`.

## 4. Sparse panels and path claims

TASK-23 produced sparse discrete quote panels, not a continuous price path. Therefore:

- an observed grid point crossing a threshold may support the narrow fact
  `OBSERVED_GRID_CROSSING`;
- if no sampled point crosses, continuous `TOUCH_WITHIN_HORIZON` remains `UNKNOWN`; it is
  not refuted because the path between panels was unobserved;
- sparse panels may support only `DISCRETE_PATH_GRID` path-risk summaries;
- `CONTINUOUS_PATH_METRICS`, continuous MAE/MFE and “no crossing anywhere” claims are
  forbidden from sparse panels.

`POOL_DEAD` and `MISSING_EXIT` are retained as path states. They are not dropped rows and
are never converted to a zero return.

## 5. Exact quote identity

`FILLABLE` and `QUOTE_EXIT` require a non-null exact-notional block containing input amount
in atomic units, input and quote mints and decimals, latency budget, freshness limit and
observed quote age. `SUPPORTED` requires `QUOTE_AVAILABLE` and observed age no greater than
the frozen freshness limit. `REFUTED` is allowed only with an explicit `NO_ROUTE` response.
`PROVIDER_ERROR`, `INVALID_RESPONSE`, `TIMEOUT` and `STALE_QUOTE` remain `UNKNOWN`.

The quote is point-in-time evidence. It does not imply a transaction was built, submitted,
filled, reconciled or settled.

## 6. Actual fills, settlement and inventory

`REALIZED_VWAP = SUPPORTED` requires `ACTUAL_FILLS_RECONCILED`, the
`ACTUAL_RECONCILED_FILLS` basis and at least one execution reference. Quote identifiers may
be retained as lineage but cannot substitute for execution evidence.

`NET = SUPPORTED` requires `SETTLED_COMPLETE`, the `SETTLED_CASHFLOW` basis and at least one
cashflow reference. Until TASK-26 supplies a complete settled cashflow model, a missing fee
or cost component leaves `NET` unknown.

Inventory is durable state, not a side note:

- `FLAT`, `RECOVERED` and `NOT_APPLICABLE` require zero remaining inventory;
- `OPEN` requires a positive atomic amount and exact mint/decimals;
- `UNRESOLVED_REQUIRES_RECOVERY` additionally requires lower and upper recovery bounds,
  their unit/currency, and a failed-exit state such as `NO_ROUTE` or `POOL_DEAD`;
- lower bounds cannot exceed upper bounds.

An exit quote alone leaves inventory open. Only reconciled execution and inventory evidence
may establish that a position is flat.

## 7. Point-in-time and lineage contract

Every row carries:

- `event_at`: underlying event time or `null` when no defensible event time exists;
- `observed_at`: when the source observation occurred;
- `first_reliable_available_at`: earliest defensible availability;
- `available_to_strategy_at`: when the project could consume it;
- `ingested_at`: when persistence completed;
- `measured_as_of`: the cutoff used to form the label.

The required order is
`event_at <= observed_at <= first_reliable_available_at <= available_to_strategy_at <= ingested_at`
when `event_at` exists, and always
`measured_as_of <= available_to_strategy_at`. A derived result cannot become available
before its latest required input. Lineage retains stable source asset IDs, quote, execution
and cashflow references, content SHA-256 and quality flags.

## 8. Synthetic golden matrix and cheapest falsifier

The tracked fixture contains only `SYNTHETIC_GOLDEN` rows. Its adversarial mutation matrix
must reject at least:

1. `TOUCH -> FILLABLE` promotion;
2. quote evidence -> `REALIZED_VWAP` or settlement promotion;
3. missing/unknown -> numeric zero;
4. sparse no-cross -> continuous touch refutation;
5. sparse grid -> continuous path metrics;
6. provider failure -> no-route;
7. stale quote -> supported fillability;
8. invalid PIT ordering;
9. exact-notional removal;
10. realized return without execution references;
11. net return without settled cashflow;
12. unresolved recovery with zero remaining inventory.

The JSON Schema freezes structure. The independent semantic checks in the test suite freeze
cross-field meaning. A3 may implement the deterministic engine only after both layers pass.

## 9. R2/R3, compatibility and reuse

R2 is metadata-bound but value-sealed in A2. Its known capability is sparse discrete panels,
quotes and terminal availability states. It does not contain actual fills or complete settled
cashflow. R3 remains default-deny and unopened. Entity graph outputs from TASK-24 are
inadmissible and no entity feature appears in this schema or fixture.

This atom adopts Python, JSON Schema, YAML, the TASK-05 `strategy_outcomes` relation, the
TASK-10 quote state contract, the TASK-22 split/holdout boundary and the TASK-23 sparse-panel
limitations. It wraps the broad TASK-05 relation with a stricter task-specific evidence
schema; it does not migrate or replace the canonical relation. No dependency, service,
plugin, connector, MCP or graph database is required.

The schema is intentionally not added to the Catalog root resolver in A2. Registration,
stable asset IDs and generated navigation belong to the later Catalog reconciliation atom.

## 10. Authority, non-claims and next boundary

A2 is limited to its declared six-file write set and offline targeted validation. It
authorizes zero R2/R3 value reads, provider/API/RPC/WSS calls, credential use, dependency
changes, Project Source changes, entity-graph reads, Catalog/registry mutation,
wallet/signer/transaction actions, spend, deployment, release, commit, push, PR or merge.

This atom establishes no actual R2 outcome, strategy ranking, statistical significance,
generalization, alpha, causality, execution, realized PnL, NetReturn, owner cashflow or
canonical TASK-25 `DONE`.

The next candidate atom is
`T25-A3_DETERMINISTIC_OUTCOME_ENGINE_AND_GOLDEN_ACCEPTANCE_V1`. Acceptance of A2 does not
authorize it.
