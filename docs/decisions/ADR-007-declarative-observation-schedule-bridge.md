# ADR-007: Declarative Observation Schedule Bridge

- Status: Accepted
- Date: 2026-08-28
- Decision owner: GOAL_OWNER
- Task: DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_V1

## Context

ExperimentSpec v1.1, Fast Lane classification, immutable run passports and the
Research Data Plane already exist. Live collection handlers still accept `spec`
and then execute `del spec`; clocks, horizons, population and publication live
in hypothesis-specific runners. A corrected first-hit module proved retained
cohorts, maturity, exact request identity, typed failures, manifest-last
publication and PIT clocks — and also proved the cost of encoding a new clock
or horizon in Python.

The closed early taker-volume-mix family is architectural evidence only. It is
not reopened, rerun, or treated as a fresh holdout.

## Decision

Adopt a governed compiler and one-shot runtime bridge:

1. Git remains the capability plane for schemas, primitive descriptors, parsers,
   field IDs, route allowlists, safety maxima and code.
2. The Research Data Plane owns immutable `ObservationSchedule v1.0` records,
   authority receipts, membership, observation batches, panel snapshots and
   hypothesis bindings.
3. A dedicated SQLite file `observation_schedule_state.sqlite` owns due-work,
   claims, the call ledger and heartbeat only. It is not scientific truth and
   is rebuildable from RDP plus active journals except explicitly indeterminate
   calls.
4. DuckDB remains a rebuildable derived read model.

Compile ExperimentSpec v1.2 `observation_request` documents into content-addressed
schedules. Execute only registered observation primitives through `tick --once`
invoked by existing systemd timers. Do not add Temporal, Celery, Kafka, Airflow,
a daemon, or a second scientific database.

Activated schedules are immutable. A new horizon or parameter compiles a new
hash and applies only to future cohort admissions. Identical or covering active
schedules are reused. Runtime YAML may select registered IDs and bounded
parameters only; it cannot define HTTP, parsing, SQL, Python, URLs or
expressions.

## Rejected alternatives

- Parameterizing the early-mix runner: it remains one hypothesis-specific
  lifecycle with a fixed scorer and single H900 terminal.
- A generic DAG/workflow engine: second control plane and operational cost
  before measured need.

## Safety boundary

This decision authorizes zero provider/API/RPC/WSS calls, zero credential reads,
zero wallet/signer/transaction actions, zero deployment and zero cash spend in
the implementation PR. Live ObservationSchedule activation requires a separate
hash-bound owner phrase after merge. Retry=false, fallback=false, cash=$0.
Existing Jupiter Free-key Tokens V2 recent/search and quote-only Swap V2
BUY/dependent reverse SELL only. No `/build`, `/execute`, or new provider.

## Consequences

- A new population predicate, X/Y horizon, lateness, sampling cap, missingness
  or disappearance choice inside accepted schemas is runtime data: no Python
  change, no Git commit and no new merge.
- A PR is required for a new provider/endpoint/auth, parser, field/feature
  primitive, estimator, schema, sink or safety contract.
- Collection and hypothesis scoring remain separate lifecycles.
- Completed V2, prior SLEEP, PR #211 runner/config/scorer/dataset and the
  consumed mix family remain unmodified.
