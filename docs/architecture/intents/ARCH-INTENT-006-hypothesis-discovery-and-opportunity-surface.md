---
intent_id: ARCH-INTENT-006
intent_version: '1.0'
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
as_of: '2026-08-22'
truth_owner: USER_GOAL_OWNER
projection_kind: PRODUCT_HORIZON_NOT_IMPLEMENTATION
implementation: NOT_IMPLEMENTED
product_layer_id: HYPOTHESIS_DISCOVERY_AND_OPPORTUNITY_SURFACE
extends:
  - ARCH-INTENT-001
  - ARCH-INTENT-002
  - ARCH-INTENT-005
authority:
  provider_read: false
  wallet_signer_transaction: false
  cash_spend: false
  project_source_mutation: false
  ui_framework_selection: false
  deployment: false
  holdout_consumption: false
  trial_creation: false
  next_hypothesis_selection: false
contains_secrets: false
---

# ARCH-INTENT-006 — Hypothesis Discovery and Opportunity Surface

This intent is a **memory / product-horizon anchor only**. It does not
implement a generator, analytics engine, provider call, data collection, UI,
database, RAG, ML model, or a second feature catalog. It does not claim Factory
readiness, select the next hypothesis, create a trial, consume a holdout, or
authorize external access or spend.

It preserves one future product horizon that existing intents mention only
implicitly:

> After the Factory can accept and honestly test a bounded hypothesis, the next
> potential bottleneck is not hypothesis execution, but high-quality,
> search-budget-limited discovery and ranking of new hypothesis candidates from
> the available market / data / context / mechanism space.

## 1. Product layer

`HYPOTHESIS_DISCOVERY_AND_OPPORTUNITY_SURFACE` is a future product layer
**upstream of** the existing hypothesis / ExperimentSpec lifecycle.

It does not replace:

- `configs/factory_v1_common_market_feature_surface_v1.yaml` as the current
  Factory-owned feature vocabulary;
- TASK-28 frozen assets (`registries/feature_catalog.yaml`,
  `hypotheses.yaml`, `research_cycles.yaml`, or related freeze contracts);
- the append-only hypothesis lifecycle / research-memory path from
  ARCH-INTENT-002 and CONTRACT-T16;
- existing Factory availability semantics.

## 2. Purpose

When activated later under a separate Entry Gate, the layer should:

1. inventory the available space of potential predictors, context variables and
   mechanism priors;
2. bind each item to acquisition feasibility, PIT / availability status,
   provenance, cost and prior research memory;
3. use **bounded** analytical exploration to propose a **small** number of draft
   candidates;
4. rank candidates primarily by expected information gain / falsification value
   per search, data and engineering cost — **not** by presumed alpha;
5. hand an accepted draft into the **existing** hypothesis lifecycle /
   ExperimentSpec path, never into a second research lifecycle.

## 3. Orthogonal vocabularies

Do not collapse these into one taxonomy.

### 3.1 Truth / availability classes (existing Factory owners)

Reuse the current Factory semantics without replacement:

- `PIT_READY` only where proven;
- `HISTORICAL_RECONSTRUCTIBLE`;
- `FORWARD_ONLY`;
- `MISSING`;
- `MISSING_CAPABILITY`;
- typed `UNKNOWN` as value status, never coerced to zero.

These remain owned by the Factory feature surface / research-truth contracts.

### 3.2 Semantic / product tags (discovery inventory only)

Allowed product tags for opportunity inventory, orthogonal to truth class:

- `MARKET_OBSERVABLE`
- `EXECUTION_OBSERVABLE`
- `ENTITY_OBSERVABLE`
- `EXOGENOUS_CHEAP_CONTEXT`
- `MECHANISM_PRIOR`

A tag never asserts availability, PIT safety, alpha, or permission to acquire
data. Tags are not a second truth taxonomy and must not fork
`factory_v1_common_market_feature_surface_v1` or TASK-28 catalogs.

## 4. Draft-candidate minimum contract

A future draft candidate record must carry at least:

- `mechanism`
- `estimand` / research question
- `required_feature_ids`
- `availability` / gaps against existing Factory classes
- `prior_related_work`
- `cheapest_falsifier`
- `search_budget`
- `data_acquisition_cost`
- `engineering_tax`
- `multiplicity` / search-debt impact
- `execution_relevance`
- `kill_if`
- `why_now`
- `recommendation`

Acceptance of a draft means only that it may enter the existing hypothesis
intake. It is not evidence of alpha and not a trial result.

## 5. Research safety

- AI, clustering and pattern mining are **exploration-only**.
- Any outcome-inspecting search that affects selection must be registered
  against the search / trial budget.
- Candidate generation must not use the holdout.
- Candidate generation is not confirmatory evidence and does not bypass
  cheap-kill, PIT, multiplicity or Factory Fit gates.
- Origin prestige (`OWNER_OBSERVATION`, `DATA_ANALYSIS`,
  `AI_ASSISTED_EXPLORATION`, external research, derivation) never substitutes
  for evidence (ARCH-INTENT-002).

## 6. Explicitly allowed low-cost context examples

The following may appear as low-cost candidate context / inventory items
**without asserting impact**:

- weekday / calendar / session / holiday state;
- lifecycle clocks;
- launchpad / program / pool lineage;
- fee regime;
- SOL / cohort regime;
- similar deterministic or exogenous context.

Their product tag is typically `EXOGENOUS_CHEAP_CONTEXT` or
`MECHANISM_PRIOR`. Availability remains an existing Factory class. Presence in
inventory is not a claim that the variable predicts returns.

## 7. Activation trigger

Do **not** build this layer until at least one trigger is observed under a
separate owner Entry Gate:

1. the Factory can execute comparable hypotheses materially faster than the
   owner can supply or prioritize high-quality next hypotheses; **or**
2. the owner must choose the next hypothesis family from a materially large
   candidate space.

Until then this record is WATCH-only horizon memory.

## 8. Non-goals before trigger

Before the activation trigger, do not:

- spray LLM ideas into the repository;
- run an autonomous research agent;
- introduce a vector DB / RAG product;
- build a broad feature store;
- exhaustively test combinatorial feature spaces;
- expand providers without a named draft-candidate consumer;
- unfreeze or rewrite TASK-28 registries;
- create a parallel hypothesis lifecycle;
- alter the active execution roadmap solely because this horizon exists.

## 9. Expected future architecture (not implemented)

```text
Knowledge / Feature Surface + Research Memory
→ bounded Analytics / Discovery
→ Candidate Ranker
→ small draft queue
→ existing Hypothesis Lifecycle
→ ExperimentSpec
```

Truth owners stay Git / Catalog / registries / Factory feature surface. This
intent adds no new authority plane.

## 10. Relation to prior intents

- ARCH-INTENT-001 / 002 already allow observation, data mining and AI-assisted
  exploration as **inputs** to the factory loop. They do not name a bounded
  discovery/ranking product layer, draft-candidate contract, orthogonal product
  tags, or this activation trigger.
- ARCH-INTENT-005 targets operational readiness for executing comparable
  hypotheses through reusable Factory capabilities. This intent preserves the
  **next** bottleneck after that readiness becomes real.

## 11. Current claim

`ACCEPTED_DIRECTION_NOT_IMPLEMENTED`.

No generator, ranker, queue, UI, DB, provider route, trial, holdout use, or
roadmap insertion is authorized by registering this intent.
