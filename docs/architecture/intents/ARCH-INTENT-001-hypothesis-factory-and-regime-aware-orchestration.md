---
asset_id: ARCH-INTENT-001
title: Hypothesis Factory and Regime-Aware Bot Orchestration
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
owner: user
origin_date: 2026-07-21
first_reliable_available_at: 2026-07-21
truth_owner: ChatGPT_Project_Work_until_coordinated_handoff
contains_secrets: false
---

# ARCH-INTENT-001 — Hypothesis Factory and Regime-Aware Bot Orchestration

## Intent

After the data spine, simulation environment, and orchestration foundation are reliable, the project's main value-creation loop shifts from building infrastructure to operating a continuous data-driven hypothesis factory.

```text
Data spine
→ feature and context layer
→ hypothesis factory
→ simulation and falsification
→ frozen strategy versions
→ bot lifecycle registry
→ regime-aware orchestrator
→ paper / shadow / micro-live execution
```

The business objective remains owner cashflow after trading and infrastructure cash costs. Hypothesis count, bot count, backtest PnL, and automation level are not success metrics by themselves.

## Lifecycle contract

Every candidate follows the existing Alpha Factory lifecycle:

```text
idea
→ mechanism and falsifier
→ data feasibility and cheap kill
→ freeze / OOS
→ paper / shadow
→ micro-live
→ champion / challenger
→ monitor / pause / retire / reformulate
```

A hypothesis is not a strategy. A strategy version is not a bot instance. Bot deployment, capital allocation, and pause/resume state remain separate versioned records.

## Regime-aware orchestration

Bots may be enabled, paused, resumed, or retired only through versioned rules and evidence. Examples of admissible triggers include liquidity-cycle state, market microstructure state, network/execution health, capacity, drawdown, and externally produced macro/regime context.

The orchestrator must preserve these vetoes:

- unavailable or stale context;
- failed risk, execution, capacity, holdout, or economics gates;
- no-route or unresolved inventory state;
- uncalibrated confidence presented as probability;
- data whose `first_reliable_available_at` is later than the decision time.

## External context contract: AOT / ALBS and similar projects

External context is advisory only. External projects may provide advisory context artifacts. They never issue direct trading commands.

Required fields:

```text
artifact_id
source_project
schema_version
generated_at
as_of
first_reliable_available_at
expires_at or ttl
revision
sha256
confidence
calibration_status
regime_state
evidence_refs
allowed_consumers
```

Rules:

- missing lineage or hash → quarantine;
- stale artifact → ignore;
- backfill does not create past availability;
- `regime_state=trade` is still advisory, not an order;
- risk, execution, and inventory controls retain veto authority;
- every consumed revision is logged as decision evidence.

A future stable adapter candidate is `CTX-AOT-ALBS-001`. A future orchestrator candidate is `ORCH-001`. Neither is implemented by this intent.

## Automation ladder

```text
L0 — manual operation and explicit approval
L1 — assisted recommendations with evidence
L2 — semi-automated actions with approval gates
L3 — automated lifecycle actions only after measured safety and economics gates
```

Promotion requires measured false-action rate, recovery behavior, operator burden, cost, replayability, and security evidence. Automation is rolled back when those controls drift.

## Named consumers

- `FACTORY-001` — hypothesis-to-bot lifecycle;
- `REG-RESEARCH-001` — hypotheses, trials, features, holdouts, and negative decisions;
- `REG-DEPLOY-001` — strategy and bot lifecycle truth;
- future `ORCH-001` — regime-aware orchestration;
- future `CTX-AOT-ALBS-001` — advisory external context adapter.

## Current boundaries

This record is an accepted architecture direction, not implementation evidence. It does not authorize a bot, provider call, data collection, trading action, remote service, or real-money execution. Blueprint and roadmap synchronization is deferred to the coordinated TASK-03 handoff after repository and Catalog registration.
