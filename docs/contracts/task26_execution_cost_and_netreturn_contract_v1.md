# TASK-26 frozen execution-cost and NetReturn contract v1

## 1. Purpose and status

- Task: `TASK-26 Execution cost and NetReturn model`.
- Atom: `T26-A2_FROZEN_EXECUTION_COST_RECONCILIATION_AND_NETRETURN_CONTRACT_V1`.
- Status after validation: `VALIDATED_CONTRACT_ONLY`.
- Route owner: `LOCAL_WORK_PRIMARY`; execution route: `LOCAL_WORK_CODEX`.
- Accepted base commit: `a1c7e40f4febeee78ab544ee89edf248c4cd0454`.
- Accepted base tree: `b4280469913ae6463a9fd3f97870f62c594795d8`.

This atom freezes the execution, fee, inventory, reconciliation and cashflow
vocabulary before any exact R2 value is read or any modeled NetReturn is produced.
It uses synthetic examples only. It does not contact a provider, construct or send a
transaction, simulate an order, inspect R2/R3 values, consume a holdout or establish
actual fill, settled PnL, strategy profitability, alpha or owner cashflow.

The owner decision eventually unlocked by TASK-26 is whether the accepted TASK-25
quote/path surface can support a point-in-time-safe, strategy-specific modeled
execution-cost result without promoting a quote into an execution or settlement fact.

## 2. Simple model: seven different layers

| Layer | Question answered | Minimum truth | It never proves by itself |
|---|---|---|---|
| `QUOTE` | What route and price was quoted for an exact amount? | Exact notional, route, freshness, latency and quote terms | An attempt, landing, fill or cash receipt |
| `ATTEMPT` | What did we intend to do and what retry chain did it belong to? | Stable attempt ID, intent/version and timestamps | That a transaction reached the chain |
| `LANDING` | What terminal state did the submitted attempt reach? | Distinct processed, confirmed, finalized, dropped, expired, failed or unknown state | A fill, flat position or cash result |
| `FILL` | What token deltas were actually observed and reconciled? | Actual deltas and reconciliation, or explicitly typed modeled fill | Complete cashflow or profit |
| `FEES` | Which costs applied and how certain are they? | Component, source, units, charge state and confidence | That an absent component is zero |
| `INVENTORY` | What asset remains under control or recovery? | Exact remaining quantity, state and recovery bounds when unknown | Flat inventory from an exit quote |
| `CASHFLOW / NETRETURN` | What cash settled, and what remains after trading and project costs? | Separate trading and infrastructure cashflow; complete reconciliation for observed NetReturn | Observed profit from a model |

The layers are not a promotion ladder. In particular, `QUOTE` does not imply
`ATTEMPT`, `ATTEMPT` does not imply `LANDING`, `LANDING` does not imply `FILL`, and a
modeled fill or modeled fee does not imply settled cashflow.

## 3. Terminal-state and retry contract

Every attempt has a stable `attempt_id`, one `intent_id`, a declared phase (`ENTRY` or
`EXIT`) and one terminal state:

`NOT_ATTEMPTED`, `PROCESSED`, `CONFIRMED`, `FINALIZED`, `DROPPED`, `EXPIRED`,
`FAILED`, or `UNKNOWN`.

- `PROCESSED`, `CONFIRMED` and `FINALIZED` remain different observations; none
  independently proves a reconciled fill.
- A documented processed failure may carry a network fee.
- A `DROPPED` or `EXPIRED` attempt with unobserved charge state may not be booked as
  zero cost.
- `UNKNOWN` blocks retry and accounting closure until reconciliation; it retains
  unresolved inventory or an explicit no-position basis.
- A retry must name `retry_of` and share a `retry_chain_id`. The same fee ID or
  cashflow reference may not be counted twice across that chain.

## 4. Fill and inventory contract

`ACTUAL_RECONCILED` fill state requires observed token deltas and an execution
reference. A quote is never a substitute. `MODELED_FROM_QUOTE` remains a separately
typed scenario assumption and is not actual execution.

Inventory is durable state:

- `NO_POSITION` means no position was opened under the declared scenario basis.
- `OPEN_MODELED`, `FLAT_MODELED` and `PARTIAL_OPEN` retain modeled quantity.
- `FLAT_ACTUAL` requires reconciled actual inventory evidence.
- `UNRESOLVED_REQUIRES_RECOVERY` requires positive or bounded uncertain remaining
  inventory and blocks accounting closure.

An exit quote, an expired attempt or a missing fee record does not prove a flat position.

## 5. Fee and cashflow contract

Fee components are typed as `BASE_NETWORK`, `PRIORITY`, `RELAY_TIP`,
`RENT_OR_ACCOUNT`, `PLATFORM`, `QUOTE_EMBEDDED` or `INFRASTRUCTURE`. Each keeps its
currency, atomic amount, source, confidence and charge state.

- Quote-embedded impact or fee must be either included in the quote result or charged
  separately, never both.
- `INFRASTRUCTURE` stays outside trade cashflow until project cashflow aggregation;
  it cannot silently alter a trade-only return.
- Trading cashflow, infrastructure cashflow and NetReturn use one explicitly named
  normalized accounting currency and decimals within a scenario. Raw fee components
  retain their original currency and are never summed across currencies implicitly.
- Missing, pending or unknown fees stay typed unknowns. They are never numeric zero.
- Observed NetReturn requires complete settled trading cashflow, complete attributed
  project cash cost and a reconciled flat actual inventory state.
- Modeled NetReturn requires an explicitly modeled-complete scenario, no unresolved
  attempt or inventory and explicit treatment of every required fee category.

## 6. Point-in-time, lineage and units

Every scenario preserves `event_at`, `observed_at`, `first_reliable_available_at`,
`available_to_strategy_at`, `ingested_at` and `measured_as_of`. When event time exists,
the order is:

`event_at <= observed_at <= first_reliable_available_at <= available_to_strategy_at <= ingested_at`.

`measured_as_of <= available_to_strategy_at` always holds. Attempts, quotes, fill
references, fee references and cashflow references are append-only IDs. A derived
scenario becomes available no earlier than its latest required input.

Amounts are represented as decimal strings or atomic integer strings with declared
currency/mint and decimals. Cashflow aggregates additionally declare their normalized
accounting currency and decimals. No component may rely on an implicit unit.

## 7. Synthetic golden matrix and cheapest falsifier

The tracked fixture contains only `SYNTHETIC_GOLDEN` scenarios. It includes valid
examples for a modeled flat round trip, processed failure with documented fee, dropped
charge uncertainty, unknown terminal state, partial inventory, retry/requote lineage,
quote-only evidence, a fully reconciled synthetic observed example and separate
infrastructure cost.

Its adversarial mutations must reject at least:

1. quote-only input promoted to observed NetReturn;
2. unknown terminal state permitting retry or accounting closure;
3. dropped/expired charge state assumed to be zero;
4. partial or unresolved inventory converted to flat;
5. retry chain that reuses a fee identifier;
6. quote-embedded fee counted again as a separate cost;
7. observed NetReturn without reconciled fill and settled cashflow;
8. infrastructure cost hidden inside trade cashflow;
9. incomplete fee model represented as a numeric NetReturn;
10. invalid point-in-time availability ordering;
11. a missing exit converted to a zero remaining inventory;
12. a modeled scenario presented as observed truth.

Only after this contract and its synthetic matrix pass may a later atom assess whether
exact R2 quote evidence can be projected into `MODELED` scenarios. R3 remains sealed.

## 8. Compatibility, reuse and scope

This atom adopts the Python/JSON Schema/YAML toolchain, the TASK-05 outcome relation,
TASK-10 quote-state semantics, TASK-22 split boundary and TASK-25 quote/PIT outcome
contract. It wraps them with a task-specific execution-cost schema. It does not migrate
or replace the canonical outcome relation, adopt a dependency, add a provider, create a
service or use a plugin, connector or MCP.

Catalog registration and generated navigation are intentionally deferred to the later
Catalog reconciliation atom. The A2 schema is a tracked contract artifact, not yet a
registered Catalog asset.

## 9. Authority, non-claims and next boundary

A2 is limited to its declared six-file write set and offline targeted validation. It
authorizes zero R2/R3 value reads, provider/API/RPC/WSS calls, credential use,
dependency changes, Project Source changes, Catalog/registry mutation, wallet/signer/
transaction actions, spend, deployment, commit, push, PR or merge.

This atom establishes no actual execution, landing probability, fill, settlement,
RealizedVWAP, observed NetReturn, owner cashflow, strategy ranking, alpha, capacity or
canonical TASK-26 `DONE`.

The next candidate atom is
`T26-A3_DETERMINISTIC_EXECUTION_COST_AND_GOLDEN_ACCEPTANCE_V1`. Acceptance of A2 does
not authorize it.
