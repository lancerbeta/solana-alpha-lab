# ADR-006: Hypothesis Fast Lane and research data plane

- Status: Accepted
- Date: 2026-08-25
- Decision owner: GOAL_OWNER
- Task: HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1

## Context

The Factory already has Git-owned experiment code, immutable evidence and an
SQLite operational store, but routine scientific runs still induce Git
ceremony. Dynamic hypotheses and run results need a durable, searchable home
without weakening capability review, PIT controls, provider authority or
promotion authority.

## Decision

Adopt three truth planes and one derived read model:

1. Git is the capability plane for executable code, schemas, accepted
   capability descriptors, parameter contracts, guards and promotion artifacts.
2. Immutable Parquet plus content-addressed manifests is the research data
   plane for hypothesis records, lifecycle events, run passports, metrics and
   evidence bindings.
3. The existing SQLite OperationalStore remains the operational plane for job
   state and writer coordination; it does not own scientific truth.
4. DuckDB is a rebuildable derived read model over verified immutable research
   data and owns no irrecoverable truth.

Adopt three execution lanes:

- `FAST_LANE` permits only accepted, hash-resolved capabilities over resolved
  immutable inputs with effects confined to `DATA_ROOT_ONLY`.
- `CHANGE_LANE` is required for a missing or changed capability, schema, query,
  PIT rule, guardrail, provider adapter or output sink.
- `PROMOTION_LANE` is required before retained research can change canonical
  product or trading behavior.

`DENY` is a classifier outcome for invalid submissions, not an execution lane.
The deterministic classifier applies the precedence frozen in the task
contract. Promotion preparation never promotes automatically.

ExperimentSpec v1.0 and the existing Factory runner remain compatible. Fast
Lane submissions use ExperimentSpec v1.1 with stable data, query, capability,
parameter-schema and time bindings. Physical `SMIAL_DATA_ROOT` values are
process-local and are never persisted; durable records use logical
`smial-data://` URIs.

## Safety boundary

`TWO_RUNG_LIVE_H900_V1` remains `FROZEN_PENDING_FAST_LANE`. This foundation
decision authorizes zero provider/API/RPC/WSS calls, zero credential reads,
zero wallet/signer/transaction actions, zero deployment actions and zero cash
spend. A `PROVIDER_READ_ONLY_BOUNDED` descriptor may classify as
`FAST_LANE_OWNER_GATE_REQUIRED`, but classification performs no provider call.

## Consequences

- Accepted offline experiments can eventually execute without Git mutation
  after the storage, resolver and runner tasks are implemented.
- Exact duplicates can be replayed instead of producing a second scientific
  result.
- One writer appends immutable research events; concurrent readers use the
  derived projection.
- New capability work and promotion continue through reviewed Git changes and
  exact-head CI.
- This ADR adds contracts and classification only; it does not add storage,
  execution, commissioning or live authority.
