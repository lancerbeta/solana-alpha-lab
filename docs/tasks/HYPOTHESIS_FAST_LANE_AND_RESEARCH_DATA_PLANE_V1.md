---
task_id: HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-25'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 016904b4991a0c8f3e81daf821de90eebf0cea79
  expected_upstream: origin/main
  expected_upstream_oid: 016904b4991a0c8f3e81daf821de90eebf0cea79
  expected_branch: cursor/hypothesis-fast-lane-research-data-plane
  dirty_mode: ALLOW_REPORTED
objective: Build one governed no-Git Fast Lane so a structured hypothesis can be
  validated, executed with already accepted capabilities and fingerprinted data,
  recorded, searched, replayed, rejected, retained, or nominated without a branch,
  pull request, or repository CI run.
managed_write_set:
- docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md
- docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
- catalog/schemas/experiment_spec_v1_1.schema.json
- catalog/schemas/experiment_capability_descriptor.schema.json
- catalog/schemas/research_event_envelope.schema.json
- catalog/schemas/run_passport.schema.json
- configs/experiment_capability_registry_v1.yaml
- configs/hypothesis_fast_lane_v1.yaml
- schemas/research_memory_projection_v1.sql
- src/solana_alpha_lab/factory/data_resolver.py
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/prior_work.py
- src/solana_alpha_lab/factory/run_passport.py
- src/solana_alpha_lab/factory/experiment_spec.py
- src/solana_alpha_lab/factory/runner.py
- src/solana_alpha_lab/factory/document_runner.py
- scripts/hypothesis_fast_lane.py
- scripts/query_hypothesis_research_memory.py
- tests/test_fast_lane_classifier.py
- tests/test_research_store.py
- tests/test_research_projection.py
- tests/test_fast_lane_runner.py
- tests/test_fast_lane_cli.py
- tests/test_task16_hypothesis_research_memory_query.py
- tests/fixtures/fast_lane/**
- catalog/query_recipes.yaml
- catalog/assets/lifecycle.yaml
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/hypothesis_fast_lane/a1_delivery_completion_evidence_v1.json
- docs/evidence/hypothesis_fast_lane/a1_delivery_independent_review_v1.json
- docs/evidence/hypothesis_fast_lane/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- TWO_RUNG_LIVE_H900_V1
- PROVIDER_API_RPC_WSS
- KCDN_ATOM_A2_OR_LATER
- COLLECTOR_DISCOVERY_RAG_VECTOR_GRAPH
- CLICKHOUSE_POSTGRES_UI
- DELIVERY_HARNESS_CONTROL_RUNTIME
- DYNAMIC_HYPOTHESIS_OR_RUN_IN_GIT
- NEW_DEPENDENCY_OR_DEPLOYMENT
- WALLET_SIGNER_TX_OR_CASH
- AUTOMATIC_PROMOTION
- SECOND_IMPLEMENTATION_ATOM
context_requirements:
  catalog_asset_ids:
  - ADR-MVP-STACK-002
  - CONTRACT-T16-HYPOTHESIS-LIFECYCLE-RESEARCH-MEMORY-001
  - SCHEMA-T16-HYPOTHESIS-LIFECYCLE-RESEARCH-MEMORY-001
  - SCHEMA-EXPERIMENT-SPEC-001
  - MODULE-FACTORY-V1-EXPERIMENT-SPEC-001
  - MODULE-FACTORY-V1-RUNNER-001
  - CONTRACT-T06-RAW-PARQUET-001
  - SCRIPT-T16-PRIOR-WORK-QUERY-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - ADR-MVP-STACK-002
    DELIVERY_EVIDENCE:
    - EVIDENCE-T16-HYPOTHESIS-RESEARCH-MEMORY-ACCEPTANCE-001
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/hypothesis_fast_lane/a1_delivery_completion_evidence_v1.json
    - docs/evidence/hypothesis_fast_lane/a1_delivery_independent_review_v1.json
    - docs/evidence/hypothesis_fast_lane/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1

## Task Outcome Brief

Git remains the capability plane. Immutable Parquet plus manifests become the
research data plane. DuckDB is a rebuildable read model. SQLite stays job-state
only. Deliver one foundation PR and stop at the exact merge gate.

## Decision packet

- **DECISION_DELTA:** three-plane, three-lane operating model with a deterministic
  lane classifier and a no-Git write fence.
- **UNCERTAINTY_REMOVED:** whether an already-accepted offline capability can be
  classified, executed, stored, searched, and replayed without Git mutation.
- **CAPABILITY_OR_EVIDENCE:** Fast Lane classifier, immutable research store,
  DuckDB projection, run passport, document runner, operator CLI, and fixture proof.
- **STOP:** FAST_LANE_FOUNDATION_READY_FOR_MERGE; no commissioning; no TWO_RUNG.
- **NEXT:** merge exact PR head only.
- **SPEC_ROUTE:** BOTH
- **REPLAN_TRIGGER:** Atom B absent; foundation contract conflict; scope breach;
  repeated blocker; second atom requested.

## Non-goals

TWO_RUNG execution, KCDN Atom A2/C/D/E, collectors, Discovery, RAG, vector or
graph storage, ClickHouse, PostgreSQL, UI, new dependency, harness control
runtime mutation, dynamic hypothesis/run Git records, automatic promotion.

The attached PRD/SSD below is the controlling implementation plan and acceptance
contract.

# Hypothesis Fast Lane and Research Data Plane — PRD + SSD + Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build one governed no-Git fast lane in which a structured hypothesis can be validated, executed with already accepted capabilities and already fingerprinted data, recorded, searched, replayed, rejected, retained, or nominated for promotion without a branch, pull request, or repository CI run.

**Architecture:** Git remains the capability plane: code, schemas, guards, stable capability descriptors, query implementations, and promotion artifacts. Immutable Parquet event partitions and content-addressed manifests become the durable research data plane; DuckDB is a rebuildable read-only projection; the existing SQLite OperationalStore remains job-state only. A deterministic lane classifier permits runtime execution only when the requested experiment is fully covered by already accepted Git capabilities and immutable data.

**Tech Stack:** CPython 3.13.14, uv 0.11.29 and the existing uv.lock, Pydantic v2, JSON Schema 2020-12, PyArrow 25.0.0, DuckDB 1.5.5, stdlib SQLite for operational job state, existing Catalog and Delivery Harness contracts. No new dependency, network service, database server, vector store, graph database, scheduler, provider, paid plan, or deployment is adopted.

**Spec:** This file is the controlling PRD, SSD, implementation plan, acceptance contract, and owner runbook for HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.

## Global Constraints

- Base work on a fresh read of current main after KCDN Atom B has merged successfully.
- Treat TWO_RUNG_LIVE_H900_V1 as FROZEN_PENDING_FAST_LANE throughout this atom.
- Provider/API/RPC/WSS calls in the foundation atom: exactly 0.
- Cash spend, credential reads, wallet, signer, transaction, deployment, account, and repository-setting actions: exactly 0.
- GitHub delivery transport for the one foundation PR is allowed by the repository workflow; it grants no market/provider authority.
- Do not execute, simulate as new evidence, or silently redesign TWO_RUNG_LIVE_H900_V1.
- Do not start KCDN Atom A2, C, D, E, a collector, Discovery, RAG, vector search, graph storage, ClickHouse, PostgreSQL, or a UI.
- Do not modify Delivery Harness control runtime, merge policy, GitHub workflow, or harness_control_write_prefixes.
- Do not add one Git asset, Catalog record, evidence file, or PR per hypothesis or per run.
- Preserve all historical Git registries and receipts byte-for-byte unless an exact compatibility fix is required by this atom and proven in the write set.
- New dynamic research records must never contain absolute machine paths, secrets, raw credentials, private endpoints, wallet material, or raw chat transcripts.
- Durable research history is append-only. Correction means a new record with a supersedes link.
- DuckDB is derived state and must be fully rebuildable from immutable Parquet partitions and manifests.
- The existing SQLite OperationalStore continues to own job state only and must not become scientific truth.
- One writer is allowed. Any second writer must fail closed with WRITER_BUSY; concurrent readers remain allowed.
- Existing supported capability plus existing immutable inputs means no Git mutation, no branch, no PR, and no repository CI.
- A new capability, feature calculation, runner, provider adapter, query implementation, schema, PIT rule, guardrail, or promotion artifact means Git Change Lane.
- Parameter values inside an already accepted parameter schema are runtime data, not code changes.
- A recommendation to promote is not promotion. Only an owner-selected Git Promotion Lane may create canonical trading/product logic.

---

## 0. Owner runbook in plain Russian

### 0.1 What is frozen now

TWO_RUNG_LIVE_H900_V1 is not the next command. It remains frozen. No live calls, no collection, and no attempt to squeeze it into the current Git-heavy workflow.

### 0.2 What the owner gives the executor after Atom B merges

Use this exact instruction with this document attached:

~~~text
EXECUTE HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1

Use HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_PRD_SSD_V1.md as the exact
PRD, SSD, implementation plan, write-set boundary, and acceptance contract.
Start from fresh main after successful KCDN Atom B merge.
TWO_RUNG_LIVE_H900_V1 remains frozen.
Foundation provider calls = 0.
Deliver one foundation PR and stop at the exact merge gate.
Do not start a second atom.
~~~

Recommended effort for this foundation atom: SOL_XHIGH. The work changes architecture, schemas, provenance, and PIT/replay behavior, but is reversible and contains no live authority.

### 0.3 What should come back

The executor must return:

1. one PR URL and exact 40-character head;
2. exact-head CI status;
3. terminal FAST_LANE_FOUNDATION_READY_FOR_MERGE or one typed blocker;
4. proof that TWO_RUNG provider calls remained 0;
5. the exact owner merge phrase bound to that head;
6. exactly one next action: merge only.

### 0.4 What happens after a successful merge

The next instruction is not a Git task:

~~~text
COMMISSION HYPOTHESIS_FAST_LANE_OFFLINE_V1

Use the accepted offline canonical-receipt replay capability and existing
fingerprinted Git evidence. Create the hypothesis/spec and store the run only
in the research data plane. Provider calls = 0. Do not modify Git, create a
branch, open a PR, or run repository CI. Prove projection rebuild, deterministic
search, exact replay, and unchanged pre/post Git status.
~~~

Expected terminal: NO_GIT_FAST_LANE_PROVEN.

### 0.5 Only after that proof

Run classification, not execution:

~~~text
CLASSIFY TWO_RUNG_LIVE_H900_V1 FOR FAST_LANE ONLY

No provider calls. No Git mutation. Return one lane decision and one NEXT.
~~~

Possible results:

| Classifier terminal | Meaning | Next owner action |
|---|---|---|
| FAST_LANE_OWNER_GATE_REQUIRED | The accepted runner and storage path already exist; only exact live authority is missing | Review the bounded call/budget packet, then provide the exact owner phrase if desired |
| CHANGE_LANE_CAPABILITY_GAP | The reusable two-rung runner, data sink, or parameter contract does not yet exist | Authorize one narrow implementation PR once; after merge, future notional runs use Fast Lane |
| BLOCKED_DATA | Required immutable inputs are absent or do not match their manifests | Resolve the named data binding; no code PR unless the missing item is a new capability |
| DENY_INVALID_SPEC | The hypothesis or estimand is incoherent | Correct the data-plane spec; no Git |
| PROMOTION_LANE_REQUIRED | The command asks to change canonical product/trading behavior | Prepare a promotion packet, then authorize a separate Git task |

This order removes the current ambiguity: foundation once, offline proof once, then classify TWO_RUNG from facts.

## 1. Executive decision

Adopt a three-plane, three-lane operating model.

### 1.1 Three planes

| Plane | Truth owned | Physical implementation |
|---|---|---|
| Capability plane | Executable code, schemas, accepted runner/query/provider capabilities, parameter contracts, guards, Catalog bindings, promotion artifacts | Git |
| Research data plane | Hypothesis definitions, append-only lifecycle events, run passports, results, metrics, evidence bindings, negative/inconclusive/invalid memory, promotion nominations | Immutable Parquet plus manifests outside Git |
| Operational plane | Current job state, command log, heartbeats, stop/park state, writer lease metadata | Existing SQLite OperationalStore; explicitly not scientific truth |
| Read model | Current hypothesis state, prior-work search, run lookup, metrics, promotion queue | Rebuildable DuckDB projection |

### 1.2 Three lanes

| Lane | Entry condition | Git/CI |
|---|---|---|
| FAST_LANE | All required code, data, schemas, query recipes, guards, and effects are already accepted and hash-resolved | No |
| CHANGE_LANE | A capability or truth contract is missing or must change | One bounded PR and exact-head CI |
| PROMOTION_LANE | A retained hypothesis is being made canonical product/trading logic or a durable monitor | One owner-selected PR and exact-head CI |

The classifier, not an agent narrative, chooses the lane.

## 2. Why the current system needs this atom

### 2.1 Confirmed reusable foundation

The repository already contains the right primitives:

- ADR-002 selects immutable Parquet plus manifests, a rebuildable embedded DuckDB projection, and a one-writer coordinator.
- TASK-05 defines 15 PIT-aware DuckDB relations, dataset and partition manifests, and bounded read-only queries.
- TASK-06 implements immutable raw-event Parquet publication and content-addressed manifests.
- TASK-16 freezes immutable hypothesis definitions, append-only lifecycle events, typed trial outcomes, as-of projection, prior-work query semantics, and negative memory.
- FactoryApplication, ExperimentRunner, capability routing, and an SQLite OperationalStore already exist.
- KCDN Atom A and Atom B provide deterministic Catalog discovery and stable context references for static Git assets.

This atom must connect those pieces; it must not replace them.

### 2.2 Confirmed operational gaps

Current behavior is Git-heavy for structural reasons:

1. ExperimentSpec is loaded only from a repository-relative file.
2. Its data requirements resolve only repository paths and a small fixed enum of Git/capture kinds.
3. The T16 prior-work reader accepts only a repository-contained JSON snapshot.
4. The Catalog T16 query recipe hard-codes two Git memory paths.
5. ExperimentRunner records job state in SQLite, but no durable scientific run store exists.
6. Current live capability code can write runtime receipts under docs/evidence, making a routine run a Git mutation.
7. Several recent raw provider bodies live in gitignored local directories; useful fields exist there but are not reproducible from Git or a canonical data manifest.
8. Git registries preserve trial and negative-result history, but each append induces repository delivery ceremony.

The root gap is not missing RAG, graph traversal, ClickHouse, or another orchestrator. It is the absence of a governed runtime research-write boundary.

### 2.3 What must not happen

- Do not move arbitrary Python or SQL into the data plane and call it a hypothesis.
- Do not make DuckDB the only durable copy.
- Do not let an agent decide by prose that a new capability is close enough to an existing one.
- Do not write dynamic run records into Catalog.
- Do not treat local bare JSON as immutable evidence.
- Do not remove live/provider authority gates merely because Git is skipped.
- Do not auto-promote a positive or retained result.

## 3. Product goals

### 3.1 Primary goals

1. Submit a new structured hypothesis without editing Git.
2. Validate definition, estimand, population, falsifier, PIT cutoff, budget, data bindings, capability bindings, parameter schema, and output effects in seconds.
3. Deterministically classify the submission into FAST_LANE, CHANGE_LANE, PROMOTION_LANE, or DENY.
4. Execute an eligible offline experiment without repository mutation.
5. Execute an eligible bounded read-only live experiment without repository mutation only after its existing exact authority gate passes.
6. Store every completed scientific result, including negative, inconclusive, and invalid outcomes, outside Git with a reconstructable passport.
7. Prevent accidental duplicate experiments when exact prior work already exists.
8. Rebuild DuckDB from Parquet and recover the same searchable state.
9. Produce a narrow capability-gap packet when a reusable tool is missing.
10. Produce a promotion candidate packet without opening a branch or PR.

### 3.2 Secondary goals

- Make the same data root portable from a Windows workstation to one Linux VPS.
- Support many concurrent read-only agents with one governed writer.
- Keep physical paths out of durable evidence through logical URIs.
- Allow future migration of metadata writes to PostgreSQL without changing research identifiers or Parquet evidence.
- Give KCDN stable static entrypoints while dynamic run history stays in its proper data plane.

### 3.3 Non-goals

- autonomous hypothesis generation;
- automatic strategy selection or activation;
- arbitrary notebook/SQL execution as accepted evidence;
- new feature engineering;
- a generic workflow engine;
- a web UI or dashboard;
- new market-data collection;
- TWO_RUNG execution;
- multi-host writes;
- ClickHouse, PostgreSQL, DuckLake, object storage, RAG, embeddings, or a graph database;
- migration or deletion of historical Git receipts;
- trading, wallet, signer, transaction, execution, PnL, NetReturn, or alpha claims.

## 4. Users and forward use cases

### 4.1 Primary user

One owner working with one or more agents. The owner chooses product meaning, estimand, risk, budgets, external authority, and promotion. Agents validate and execute accepted capabilities.

### 4.2 Required use cases

#### UC-1 — New offline hypothesis, existing everything

An agent submits a new definition and an experiment using an existing feature set, dataset manifest, query recipe, runner, and parameter schema. The classifier returns FAST_LANE_READY. The run completes, writes no Git files, and stores a negative result.

#### UC-2 — Threshold or notional variation

The runner and parameter schema already permit the requested values. Only parameter values differ. This remains Fast Lane; no PR is allowed.

#### UC-3 — Missing feature calculator

The hypothesis references a feature whose calculator is not an accepted capability. The classifier returns CHANGE_LANE_CAPABILITY_GAP with the exact missing capability and no experiment execution.

#### UC-4 — Existing live quote capability

The runner, provider adapter, output data sink, budget policy, and schemas are accepted. Classification succeeds but execution returns FAST_LANE_OWNER_GATE_REQUIRED until the exact owner phrase is supplied. No PR is needed for the run.

#### UC-5 — Legacy runner writes to Git

Code exists but its declared output zone includes the repository or bare local JSON. The classifier returns CHANGE_LANE_CAPABILITY_GAP: OUTPUT_SINK_NOT_DATA_PLANE. Existence of code alone is insufficient.

#### UC-6 — Exact duplicate

The same spec, capability closure, inputs, config, and as-of cutoff already produced a completed run. The system returns REPLAY_AVAILABLE with the prior run ID and does not execute again.

#### UC-7 — Meaningful repetition

A new immutable dataset fingerprint, as-of cutoff, population, parameter, regime, or capability version changes the run key. A new run is allowed and what_changed is recorded.

#### UC-8 — Promotion candidate

A retained result passes promotion-candidate checks. The data plane stores a nomination and generates a content-addressed packet. Git remains unchanged until the owner explicitly selects Promotion Lane.

#### UC-9 — Local-to-VPS move

Immutable data directories and manifests move to the VPS. SMIAL_DATA_ROOT changes; logical URIs and hashes do not. DuckDB rebuilds locally on the VPS.

#### UC-10 — Multiple agents

Many agents query the read-only DuckDB projection. Exactly one append writer operates. A second writer receives WRITER_BUSY without corrupting data.

## 5. Success criteria and SLOs

### 5.1 Hard acceptance

- One foundation PR only.
- Foundation provider calls = 0.
- A post-merge offline commissioning run creates zero Git diff, zero branch, zero PR, and zero CI run.
- Every completed run has a valid immutable passport and result digest.
- DuckDB can be deleted and rebuilt from the data root with the same projection digest.
- Exact duplicate submission returns REPLAY_AVAILABLE.
- A missing capability returns a typed Change Lane packet without generating code.
- A promotion request cannot execute in Fast Lane.
- A live-capable request cannot call a provider without its exact authority phrase.
- No absolute paths or secrets appear in persisted rows, manifests, receipts, or CLI output.

### 5.2 Performance targets

These targets cover Fast Lane overhead, not the scientific query itself:

| Operation | Acceptance target |
|---|---|
| Validate and classify one submission | p95 at or below 2 seconds on the 10,000-event acceptance fixture |
| Append one terminal run bundle | p95 at or below 3 seconds excluding experiment runtime |
| Bounded prior-work search, max 50 results | p95 at or below 2 seconds on the 10,000-event acceptance fixture |
| Rebuild projection | at or below 60 seconds on the 10,000-event acceptance fixture |
| Duplicate lookup by run_key_sha256 | at or below 250 ms on the same fixture |

Performance tests must use a deterministic generated fixture and must not depend on internet speed or provider availability.

### 5.3 Operating metrics

The read model must expose:

- fast_lane_submissions_total;
- fast_lane_runs_total by scientific terminal;
- lane_decisions_total by lane and reason code;
- duplicate_replays_avoided_total;
- git_mutation_attempts_denied_total;
- writer_busy_total;
- projection_rebuild_seconds;
- prior_work_query_seconds;
- provider_calls_total and provider_budget_remaining for live-capable runs;
- orphan_run_starts_total;
- invalid_evidence_total;
- promotion_candidates_total.

## 6. Options considered

### Option A — Keep every hypothesis and run in Git

Rejected as the steady-state model. It gives audit history but turns exploration into a PR factory, couples scientific throughput to CI, and encourages bare local data to sit outside the actual provenance chain.

### Option B — Store everything directly in one DuckDB file

Rejected as durable truth. It is operationally simple, but it creates a mutable single file, weakens append-only recovery, complicates multi-agent safety, and contradicts ADR-002.

### Option C — Immutable Parquet event log, DuckDB projection, SQLite job state

Accepted. It reuses existing architecture, gives fast local SQL, keeps evidence portable, permits exact replay, and leaves a measured upgrade path to PostgreSQL or ClickHouse.

## 7. Truth ownership and mutation matrix

| Entity | Durable owner | Mutable? | Catalog entry per instance? | PR per instance? |
|---|---|---|---|---|
| Capability implementation | Git | Through reviewed commits | Yes, static | Yes |
| Capability descriptor and parameter schema | Git | Through reviewed commits | Yes, static | Yes |
| Query implementation/recipe | Git | Through reviewed commits | Yes, static | Yes |
| Hypothesis family/version/origin/cycle | Research data plane | Append-only versions | No | No |
| Experiment parameter instance | Research data plane | Immutable per spec hash | No | No |
| Run start/terminal/metric/evidence binding | Research data plane | Append-only events | No | No |
| Raw/canonical market bytes | Immutable dataset Parquet | No in-place mutation | One dataset/schema capability, not each file | No |
| DuckDB projection | Derived cache | Rebuildable | No | No |
| SQLite job state | Operational cache | Yes | No | No |
| Promotion nomination | Research data plane | Append-only | No | No |
| Promoted strategy/monitor/product behavior | Git | Through reviewed commits | Yes | Yes |

## 8. Stable identity model

Preserve the TASK-16 identity families:

- HYP-FAMILY-*;
- HYP-VERSION-*-Vn;
- HYP-ORIGIN-*;
- RESEARCH-CYCLE-*;
- RESEARCH-ARTIFACT-*;
- TRIAL-*;
- DECISION-EVENT-*;
- HYP-DERIVATION-*;
- ACTIVATION-EPOCH-*.

Add runtime identities:

- RUN-* for one execution identity;
- RUN-EVENT-* for append-only operational/scientific events;
- METRIC-* for a metric observation;
- EVIDENCE-BINDING-* for one exact input/output binding;
- PROMOTION-CANDIDATE-* for a nomination;
- CAPABILITY-GAP-* for a machine-readable Change Lane result;
- RESEARCH-TXN-* for one atomic event partition.

### 8.1 Deterministic run key

Compute run_key_sha256 over canonical JSON containing:

~~~text
hypothesis_definition_sha256
experiment_spec_sha256
capability_id
capability_closure_sha256
runner_git_sha
uv_lock_sha256
ordered_input_dataset_manifest_ids
ordered_input_dataset_fingerprints
ordered_query_recipe_ids
ordered_query_recipe_sha256s
config_sha256
as_of
availability_cutoff
holdout_consumption_ids
random_seed_or_null
~~~

RUN identity is RUN- followed by the first 24 uppercase hex characters of run_key_sha256. An exact duplicate is idempotent and cannot create a second scientific result.

### 8.2 Canonicalization

- UTF-8;
- lexicographically sorted object keys;
- separators comma and colon without spaces;
- Unicode not ASCII-escaped;
- finite numbers only;
- Decimal values serialized as canonical strings;
- set-valued arrays sorted;
- timestamps normalized to UTC RFC3339 with Z;
- no physical paths.

## 9. Research event log SSD

### 9.1 Durable event envelope

Store one typed envelope schema in Parquet:

~~~text
record_id                       VARCHAR, primary logical identity
record_kind                     VARCHAR, closed enum
entity_id                       VARCHAR
hypothesis_version_id           VARCHAR nullable
run_id                          VARCHAR nullable
transaction_id                  VARCHAR
effective_at                    TIMESTAMPTZ
first_reliable_available_at     TIMESTAMPTZ
supersedes_record_id            VARCHAR nullable
payload_json                    VARCHAR
payload_sha256                  VARCHAR length 64
schema_version                  VARCHAR
producer_capability_id          VARCHAR
producer_git_sha                VARCHAR length 40
created_at                      TIMESTAMPTZ
~~~

Allowed record_kind values:

~~~text
HYPOTHESIS_FAMILY
HYPOTHESIS_ORIGIN
RESEARCH_CYCLE
HYPOTHESIS_VERSION
RESEARCH_ARTIFACT
TRIAL
DECISION_EVENT
DERIVATION_EDGE
ACTIVATION_EPOCH
RUN_STARTED
RUN_COMPLETED
RUN_ABORTED
RUN_INVALID
EXPERIMENT_METRIC
EVIDENCE_BINDING
PROMOTION_CANDIDATE
CAPABILITY_GAP
~~~

Shape validation uses JSON Schema/Pydantic; cross-record validation reuses TASK-16 semantics.

### 9.2 Atomic append

One append transaction:

1. acquires the one-writer lease;
2. validates all records and references against the current committed projection;
3. canonicalizes and hashes every payload;
4. writes all transaction rows into one temporary Parquet file under the data root;
5. reads it back and validates schema, rows, hashes, and ordering;
6. creates a PartitionManifest with existing manifest primitives;
7. publishes the Parquet file with create-only no-clobber semantics;
8. publishes the partition manifest last;
9. releases the lease;
10. refreshes or incrementally rebuilds DuckDB.

Readers include only partitions with a valid published manifest. A crash before manifest publication leaves an orphan that doctor reports and normal queries ignore.

### 9.3 Single-writer lease

Implement a cross-platform create-exclusive lease file under the data root. The lease contains a random token, host, PID, opened_at, and expiry. Only the token owner can release it.

- A live lease returns WRITER_BUSY.
- A same-host dead PID may be reclaimed by doctor after validating no published partial transaction.
- A foreign-host or unverifiable lease is never auto-stolen.
- Manual recovery appends a recovery event; it never deletes committed evidence.

### 9.4 Logical storage layout

~~~text
SMIAL_DATA_ROOT/
  research/
    events/date=YYYY-MM-DD/RESEARCH-TXN-*.parquet
    manifests/partitions/partition-*.json
    manifests/datasets/dataset-*.json
    artifacts/RUN-*/
  datasets/
    raw_api_events/...
    canonical_observations/...
    quote_attempts/...
  projections/
    research_memory.duckdb
  ops/
    operational_state.sqlite
  locks/
    research-writer.lock
  snapshots/
    inventory-*.json
~~~

Persisted logical URIs use smial-data://research/... or smial-data://datasets/... and never the physical SMIAL_DATA_ROOT.

### 9.5 Data root resolution

- If SMIAL_DATA_ROOT is set, resolve it as the physical root.
- Otherwise use repository-local local/factory_v1/data_plane for workstation compatibility.
- The resolved root must be absolute, non-symlinked at its root boundary, outside tracked Git paths, and writable only for commands that declare data-plane writes.
- The value is never persisted.

## 10. DuckDB projection SSD

### 10.1 Role

DuckDB is a read model only. It may be deleted at any time. No accepted run may depend on a row that cannot be reconstructed from a committed Parquet event and manifest.

### 10.2 Required logical views

Expose exactly these owner-facing views:

| View | Content |
|---|---|
| hypotheses | family, immutable version, origin, research cycle, definition hash, derived state |
| hypothesis_events | decisions, derivations, activation epochs, corrections |
| experiment_runs | run passport, status, outcome, scientific terminal, result digest |
| experiment_metrics | typed scalar metrics and units |
| evidence_bindings | exact data/query/code/config/input/output hashes and logical URIs |
| promotion_candidates | nominations and owner state |
| prior_work | deterministic flattened search surface |
| capability_gaps | typed missing-capability packets |

### 10.3 PIT and lifecycle projection

- Exclude records whose first_reliable_available_at is after as_of.
- Apply TASK-16 decision events in ascending effective_at, first_reliable_available_at, record_id order.
- A future correction cannot alter an earlier projection.
- Missing is never coerced to zero or false.
- INVALID evidence is not a NEGATIVE market result.
- Promotion nomination is not PROMOTED state.

### 10.4 Rebuild contract

The rebuild command:

1. verifies every visible partition and manifest;
2. creates a new DuckDB file beside the current projection;
3. applies tracked DDL with extensions and external network access disabled;
4. loads only verified committed partitions;
5. runs semantic validation and gold queries;
6. computes projection_digest_sha256 from deterministic bounded exports;
7. atomically swaps the derived file;
8. retains the previous derived projection until the new one passes.

## 11. Capability registry and lane classifier

### 11.1 Static capability descriptor

Every Fast Lane-capable runner must resolve to one Git-owned descriptor:

~~~yaml
capability_id: CAP-...
status: ACCEPTED
entrypoint: package.module:function
implementation_asset_ids: []
parameter_schema_asset_id: SCHEMA-...
input_kinds: []
output_kinds: []
effect_class: OFFLINE_READ_ONLY
output_zone: DATA_ROOT_ONLY
provider_policy_asset_id: null
max_provider_calls: 0
supports_pit: true
determinism_class: DETERMINISTIC
promotion_authority: NONE
~~~

Closed effect_class values:

- OFFLINE_READ_ONLY;
- OFFLINE_DATA_PLANE_WRITE;
- PROVIDER_READ_ONLY_BOUNDED;
- PROMOTION_PREPARE_ONLY.

Any unknown effect, repository write, deployment, account mutation, wallet/signer/transaction action, or arbitrary subprocess makes the capability ineligible.

### 11.2 Classification algorithm

Given one immutable submission:

1. validate the TASK-16 hypothesis records;
2. validate ExperimentSpec v1.1;
3. resolve the exact capability descriptor by stable Catalog asset ID;
4. verify descriptor status ACCEPTED;
5. verify every implementation file hash against the named Git SHA;
6. validate parameters against the capability parameter schema;
7. resolve every dataset manifest and fingerprint;
8. resolve every declared query recipe and hash, or prove that the capability descriptor permits an empty recipe set;
9. validate PIT/as-of, availability, holdout, and search budget;
10. verify output_zone DATA_ROOT_ONLY;
11. compare requested effects and budgets to descriptor limits;
12. query exact and related prior work;
13. compute run_key_sha256;
14. return exactly one lane decision.

### 11.3 Decision precedence

Apply this precedence:

~~~text
DENY_INVALID_SPEC
> PROMOTION_LANE_REQUIRED
> CHANGE_LANE_CAPABILITY_GAP
> BLOCKED_DATA
> REPLAY_AVAILABLE
> FAST_LANE_OWNER_GATE_REQUIRED
> FAST_LANE_READY
~~~

Lane and terminal are separate. A request whose capability is already accepted
but whose named immutable input is temporarily absent remains Lane.FAST_LANE
with terminal BLOCKED_DATA and cannot execute. If obtaining that input requires
a new collector, adapter, feature calculator, or schema, the result is instead
Lane.CHANGE_LANE with the corresponding capability-gap reason. REPLAY_AVAILABLE
is Lane.FAST_LANE with no new execution.

### 11.4 Fast Lane eligibility

FAST_LANE_READY requires all of:

- immutable valid hypothesis definition;
- accepted capability descriptor;
- exact implementation closure at runner_git_sha;
- parameter schema pass;
- exact immutable inputs;
- query recipe resolved;
- PIT/availability/holdout pass;
- no exact completed duplicate;
- declared write effects confined to data root;
- no promotion or product behavior change;
- no unapproved provider call.

### 11.5 Change Lane reasons

Closed reason codes:

~~~text
CAPABILITY_NOT_REGISTERED
CAPABILITY_NOT_ACCEPTED
IMPLEMENTATION_HASH_MISMATCH
PARAMETER_SCHEMA_MISSING
PARAMETER_OUTSIDE_ACCEPTED_SCHEMA
QUERY_IMPLEMENTATION_MISSING
FEATURE_CALCULATOR_MISSING
PROVIDER_ADAPTER_MISSING
PIT_LOGIC_CHANGE_REQUIRED
SCHEMA_CHANGE_REQUIRED
GUARDRAIL_CHANGE_REQUIRED
OUTPUT_SINK_NOT_DATA_PLANE
ARBITRARY_CODE_OR_SQL_REQUESTED
~~~

The classifier writes a CAPABILITY_GAP event and stops. It must not invent code, create a task, or open a PR.

## 12. Hypothesis submission and ExperimentSpec v1.1

### 12.1 Submission packet

One submission contains:

- one TASK-16-compatible research cycle;
- one hypothesis family;
- one origin;
- one immutable hypothesis version;
- one ExperimentSpec v1.1;
- optional derivation edges;
- optional what_changed claim.

The validator constructs a minimal TASK-16 snapshot and reuses the existing semantic validator. It must not fork a competing hypothesis ontology.

### 12.2 ExperimentSpec v1.1

Preserve all v1.0 meaning and add stable bindings:

~~~text
data_bindings[]:
  binding_id
  source_kind = CATALOG_ASSET | DATASET_MANIFEST | RESEARCH_ARTIFACT
  stable_id
  expected_content_sha256_or_dataset_fingerprint

query_recipe_ids
capability_id
parameter_schema_asset_id
as_of
availability_cutoff
what_changed
~~~

Legacy v1.0 repository specs remain valid. Fast Lane accepts only v1.1 or a deterministic in-memory upgrade whose source hash is preserved.

### 12.3 Query parameters versus query implementation

- Selecting an accepted recipe and supplying validated parameters is Fast Lane.
- Changing SQL, Python, ranking, feature logic, or recipe semantics is Change Lane.
- Ad hoc exploration may occur in a scratch sandbox, but it cannot become an accepted trial until it resolves to an accepted query capability.

## 13. Run passport

Every RUN_COMPLETED or RUN_INVALID record must contain:

~~~text
run_id
run_key_sha256
trial_id
hypothesis_version_id
hypothesis_definition_sha256
experiment_spec_sha256
runner_capability_id
runner_git_sha
capability_closure_sha256
uv_lock_sha256
dataset_manifest_ids
dataset_fingerprints
query_recipe_ids
query_recipe_sha256s
config_sha256
as_of
availability_cutoff
holdout_consumption_ids
random_seed_or_null
started_at
completed_at
first_reliable_available_at
provider_calls_planned
provider_calls_actual
cash_spend_usd_cents
execution_status
trial_outcome
scientific_terminal
result_digest_sha256
artifact_manifest_sha256
limitations
non_claims
~~~

### 13.1 Separate operational and scientific truth

Execution status:

~~~text
COMPLETE
FAILED_INFRA
BLOCKED_DATA
BLOCKED_AUTHORITY
ABORTED
INVALID_EVIDENCE
~~~

TASK-16 trial outcome:

~~~text
POSITIVE
NEGATIVE
INCONCLUSIVE
INVALID
~~~

Owner-facing scientific terminal:

~~~text
REJECTED
RETAINED
INCONCLUSIVE
PROMOTION_CANDIDATE
INVALID
~~~

CAPABILITY_GAP and BLOCKED_AUTHORITY are not market results and must not create NEGATIVE trials.

A capability descriptor declares query_recipe_required. If true, at least one
recipe is mandatory. If false, the ordered query-recipe arrays may be empty;
this covers pure bounded capture capabilities without inventing a fake query.

## 14. Search, navigation, and duplicate prevention

### 14.1 Deterministic prior-work query

Refactor the existing T16 query engine into reusable logic with two read-only adapters:

1. legacy Git snapshot/registry adapter;
2. DuckDB research data-plane adapter.

Return the existing stable IDs, matched_by reasons, supporting records, and content-addressed evidence. Preserve deterministic scoring and stable-ID tie breaks.

### 14.2 Required predicates

- exact hypothesis version or definition hash;
- mechanism terms;
- falsifier terms;
- regime terms;
- origin kind;
- dataset manifest or fingerprint;
- capability ID;
- query recipe ID;
- trial outcome;
- scientific terminal;
- decision kind;
- as_of;
- what_changed;
- max_results from 1 through 50.

### 14.3 Duplicate rules

- Exact run_key_sha256 plus completed result returns REPLAY_AVAILABLE.
- Same definition with different dataset/as_of/config/capability creates a new run and records the machine-derived delta.
- Changed statement, mechanism, falsifier, features, labels, or population requires a new hypothesis version.
- A prose-only what_changed claim cannot override an identical run key.
- Negative, inconclusive, invalid, dormant, paused, and retired evidence remains searchable.

### 14.4 KCDN boundary

KCDN owns static Git asset discovery and stable references. This atom adds only:

- one static data-plane root capability record;
- static schemas and capability descriptors;
- bounded query recipes for Fast Lane classify, show, and prior-work search.

Dynamic hypotheses and runs are not Catalog assets. This atom does not start general KCDN federation Atom A2.

## 15. CLI contract

Create one CLI: scripts/hypothesis_fast_lane.py.

Required commands:

~~~text
doctor
verify-store
submit --packet PATH [--run]
classify --packet PATH
show-hypothesis --hypothesis-version-id ID --as-of UTC
show-run --run-id ID
search-prior-work --as-of UTC --max-results N [bounded predicates]
replay --run-id ID
prepare-promotion --run-id ID
rebuild-projection
commission-offline
~~~

### 15.1 Output contract

- stdout: one deterministic JSON object;
- stderr: typed error only;
- success exit 0;
- blocked/deny exit 2;
- scientific negative/inconclusive remains successful execution exit 0;
- no physical paths;
- no raw provider body;
- exactly one lane, terminal, and next_action.

doctor and verify-store must include the committed inventory hash, orphan count,
lease state, projection digest, and a boolean stating whether a cold rebuild is
currently possible.

### 15.2 Simple owner output

Each command must end with:

~~~text
lane
status
scientific_terminal
reason_codes
run_id_or_null
git_mutation_count
provider_calls_actual
next_action
~~~

## 16. No-Git write fence

Fast Lane must enforce, not merely promise, no repository mutation.

1. Capture the repository status fingerprint before execution.
2. Resolve every allowed output under SMIAL_DATA_ROOT or an OS temp directory.
3. Reject any capability descriptor whose output zone is not DATA_ROOT_ONLY.
4. Reject absolute or parent-traversal output paths.
5. Run the capability through an output resolver that exposes no repository write target.
6. Capture the repository status fingerprint after execution.
7. If it differs, append RUN_INVALID with GIT_MUTATION_DETECTED, preserve diagnostic hashes, and return DENY.
8. Never auto-revert user or executor files.

The status comparison uses the complete pre/post porcelain byte sequence, so an already dirty but unchanged worktree can still be proven unchanged. Referenced implementation files must independently match runner_git_sha.

## 17. Live/provider boundary

No-Git does not mean no authority.

A PROVIDER_READ_ONLY_BOUNDED capability is Fast Lane-capable only if its descriptor binds:

- provider route registry asset ID;
- exact request class;
- exact maximum calls;
- retries;
- timeout;
- cash cap;
- credential read policy;
- raw retention sink;
- redaction schema;
- allowed terminal outcomes;
- exact owner authority phrase contract.

Without the exact phrase, classification may succeed but execution returns FAST_LANE_OWNER_GATE_REQUIRED with provider_calls_actual = 0.

Any runner that stores raw responses only as bare local JSON is not Fast Lane-capable. It must first be wrapped once to write RawApiEvent Parquet plus manifests.

## 18. Promotion Lane

prepare-promotion performs no Git mutation. It creates a packet under the data root containing:

- hypothesis and run IDs;
- exact result and evidence hashes;
- promotion rationale;
- limitations and invalidating conditions;
- shadow/paper/live target class;
- proposed strategy/monitor/product acceptance criteria;
- required owner decisions;
- proposed Git write set;
- rollback condition.

Only a later exact owner command may start a Git promotion task. The promoted artifact references data-plane hashes and logical URIs; it does not copy raw or massive data into Git.

## 19. Historical cutover and compatibility

### 19.1 Forward-only cutover

- Historical Git registries and evidence remain unchanged.
- New Fast Lane records begin after a cutover timestamp recorded in the foundation config.
- Prior-work queries union legacy Git history with new data-plane history.
- If the same stable ID appears in both planes, hashes must match or the query fails with CROSS_PLANE_ID_CONFLICT.
- No synthetic backfill is invented.
- A later optional migration may copy historical records only with source path, source SHA, and first reliable availability preserved.
- Legacy PASS and FAIL labels are not automatically translated into POSITIVE
  and NEGATIVE. The adapter preserves the original label and emits
  LEGACY_OUTCOME_UNRESOLVED unless exact retained semantics prove a scientific
  mapping. A technical failure must never become a negative market result.

### 19.2 Existing Factory compatibility

- FactoryApplication and repository ExperimentSpec v1.0 continue to work.
- ExperimentRunner.start retains its public behavior.
- Add document-based execution as a new path; do not replace legacy behavior.
- OperationalStore remains compatible and owns no scientific truth.
- Existing tests must pass unchanged.
- Fast Lane reuses the OperationalStore class at
  SMIAL_DATA_ROOT/ops/operational_state.sqlite. Legacy Factory paths remain
  unchanged.

### 19.3 Cold-copy recovery

Because committed data files are immutable, a backup tool needs only the
verified inventory and missing content-addressed files. Foundation doctor must
produce an inventory hash, and acceptance must copy committed bytes to a fresh
temporary root, rebuild DuckDB there, and obtain the same projection digest.
Choosing or deploying a remote backup service remains outside this atom.

## 20. Security and failure model

| Failure | Required behavior |
|---|---|
| Invalid schema or duplicate ID | DENY_INVALID_SPEC; no write except optional invalid submission event |
| Missing data manifest | BLOCKED_DATA |
| Hash mismatch | DENY_INTEGRITY_MISMATCH |
| Missing capability | CHANGE_LANE_CAPABILITY_GAP |
| Dirty referenced implementation | IMPLEMENTATION_HASH_MISMATCH |
| Exact duplicate | REPLAY_AVAILABLE |
| Second writer | WRITER_BUSY |
| Crash before manifest publish | Orphan ignored by readers; doctor reports it |
| Crash after manifest publish | Transaction visible and idempotent |
| DuckDB corruption | Delete and rebuild from Parquet |
| Repository write attempt | GIT_MUTATION_DETECTED; RUN_INVALID; do not auto-revert |
| Provider phrase absent | FAST_LANE_OWNER_GATE_REQUIRED; zero calls |
| Provider budget exceeded | abort capability; INVALID_EVIDENCE |
| Unknown outcome | INVALID, never NEGATIVE |
| Promotion requested in Fast Lane | PROMOTION_LANE_REQUIRED |
| Physical path leaks into record | deny persistence |
| Secret-like material detected | deny persistence and redact diagnostics |

## 21. Scale-up triggers

### 21.1 PostgreSQL

Move transactional metadata/writer coordination from local files only when one of these is measured:

- two or more required concurrent writers;
- writes from more than one host;
- writer-lock denials above 1 percent of submissions over 14 days;
- operational recovery cannot meet the existing RPO/RTO.

Parquet remains evidence truth unless a separate ADR changes it.

### 21.2 ClickHouse

Consider ClickHouse only when:

- common partition-pruned analytical queries exceed 5 seconds p95 for 14 days;
- retained analytical data exceeds 100 GB;
- or more than 10 concurrent analytical readers are operationally required.

First attempt Parquet partitioning, DuckDB projection indexes/materialization, and query repair.

### 21.3 Object storage

Adopt object storage only when one-host filesystem durability or replication fails measured RPO/RTO. Logical URIs and manifest identities must remain unchanged.

### 21.4 RAG or vector search

Do not add RAG because the corpus grew. Trigger a design review only after at least 20 real bounded prior-work queries demonstrate that the needed record existed, deterministic structured search and term normalization could not retrieve it, and gold-query repair cannot close the gap.

### 21.5 Graph database

Do not add a graph database for declared edges. Trigger a review only if bounded depth-two relation queries become a measured bottleneck or required questions cannot be expressed with the existing relation/event tables.

## 22. Proposed repository topology

### Create

~~~text
docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md
catalog/schemas/experiment_spec_v1_1.schema.json
catalog/schemas/experiment_capability_descriptor.schema.json
catalog/schemas/research_event_envelope.schema.json
catalog/schemas/run_passport.schema.json
configs/experiment_capability_registry_v1.yaml
configs/hypothesis_fast_lane_v1.yaml
schemas/research_memory_projection_v1.sql
src/solana_alpha_lab/factory/data_resolver.py
src/solana_alpha_lab/factory/lane_classifier.py
src/solana_alpha_lab/factory/research_store.py
src/solana_alpha_lab/factory/run_passport.py
scripts/hypothesis_fast_lane.py
tests/test_fast_lane_classifier.py
tests/test_research_store.py
tests/test_research_projection.py
tests/test_fast_lane_runner.py
tests/test_fast_lane_cli.py
tests/fixtures/fast_lane/
~~~

### Modify

~~~text
src/solana_alpha_lab/factory/experiment_spec.py
src/solana_alpha_lab/factory/runner.py
scripts/query_hypothesis_research_memory.py
catalog/query_recipes.yaml
catalog/assets/lifecycle.yaml
catalog/catalog_manifest.yaml
catalog/generated/asset_edges.json
docs/PROJECT_MAP.md
tests/test_task16_hypothesis_research_memory_query.py
~~~

Generated Catalog/navigation files must be regenerated by the accepted generator, never hand-edited.

### Must not modify

~~~text
delivery-harness/**
.github/**
scripts/delivery_harness.py
control/owner_attention_gate_v2.yaml
registries/hypotheses.yaml
registries/research_cycles.yaml
registries/global_trial_ledger.yaml
registries/decisions_negative_results.yaml
existing docs/evidence/**
~~~

## 23. Exact module interfaces

### 23.1 Experiment document

~~~python
def validate_experiment_document(
    document: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    """Return a canonical validated copy or raise ExperimentSpecError."""
~~~

Legacy load_experiment_spec calls this function after reading repository bytes.

### 23.2 Resolver

~~~python
@dataclass(frozen=True, slots=True)
class ResolvedEvidence:
    binding_id: str
    source_kind: str
    stable_id: str
    logical_uri: str
    content_sha256: str | None
    dataset_fingerprint: str | None
    first_reliable_available_at: datetime
    physical_path: Path


def resolve_evidence_bindings(
    spec: Mapping[str, Any],
    *,
    root: Path,
    data_root: Path,
) -> tuple[ResolvedEvidence, ...]:
    ...
~~~

physical_path is process-local and must never enter durable serialization.

### 23.3 Classifier

~~~python
class Lane(StrEnum):
    FAST_LANE = "FAST_LANE"
    CHANGE_LANE = "CHANGE_LANE"
    PROMOTION_LANE = "PROMOTION_LANE"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class LaneDecision:
    lane: Lane
    terminal: str
    reason_codes: tuple[str, ...]
    run_key_sha256: str | None
    prior_run_id: str | None
    next_action: str


def classify_lane(
    submission: Mapping[str, Any],
    *,
    root: Path,
    data_root: Path,
    as_of: datetime,
) -> LaneDecision:
    ...
~~~

### 23.4 Research store

~~~python
class ResearchStore:
    def append(
        self,
        records: Sequence[ResearchEvent],
        *,
        transaction_id: str,
    ) -> CommitReceipt:
        ...

    def rebuild_projection(self) -> ProjectionReceipt:
        ...

    def find_completed_run(self, run_key_sha256: str) -> RunPassport | None:
        ...
~~~

### 23.5 Runner compatibility

~~~python
def start_document(
    self,
    spec: Mapping[str, Any],
    *,
    spec_sha256: str,
    run_context: RunContext,
    authority_phrase: str | None = None,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ...
~~~

Existing start(spec_relative, ...) loads and delegates without changing behavior.

## 24. Implementation plan

The implementation is one bounded product atom and one PR. Tasks below are internal commits, not owner checkpoints and not separate atoms.

### Task 1: Freeze contracts, compatibility seams, and failing classification matrix

**Files:**

- Create: docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
- Create: docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md
- Create: catalog/schemas/experiment_spec_v1_1.schema.json
- Create: catalog/schemas/experiment_capability_descriptor.schema.json
- Create: configs/experiment_capability_registry_v1.yaml
- Create: configs/hypothesis_fast_lane_v1.yaml
- Create: src/solana_alpha_lab/factory/lane_classifier.py
- Create: tests/test_fast_lane_classifier.py

**Interfaces:**

- Consumes: existing ExperimentSpec v1.0, TASK-16 schema, Catalog stable asset IDs.
- Produces: Lane, LaneDecision, closed capability descriptor schema, v1.1 spec schema.

- [ ] **Step 1: Verify entry gates**

Read fresh main, prove KCDN Atom B assets resolve, prove current Factory files match the repository state, and record TWO_RUNG frozen with provider calls 0. If Atom B is absent, stop with DEPENDENCY_NOT_MERGED.

- [ ] **Step 2: Write the failing classifier matrix**

Include tests for FAST_LANE_READY, owner-gated live, missing capability, Git-writing capability, invalid spec, blocked data, exact duplicate, and promotion request.

~~~python
def test_existing_offline_capability_is_fast_lane() -> None:
    decision = classify_fixture("offline_existing_everything")
    assert decision.lane is Lane.FAST_LANE
    assert decision.terminal == "FAST_LANE_READY"


def test_repo_writing_capability_requires_change_lane() -> None:
    decision = classify_fixture("legacy_repo_receipt_writer")
    assert decision.lane is Lane.CHANGE_LANE
    assert decision.reason_codes == ("OUTPUT_SINK_NOT_DATA_PLANE",)
~~~

- [ ] **Step 3: Run the focused test and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_classifier
~~~

Expected: import or missing-interface failure; no provider call.

- [ ] **Step 4: Implement schemas, config, and minimal classifier types**

Implement only the closed enums and validation needed for the failing matrix. Do not add storage or execution yet.

- [ ] **Step 5: Re-run focused tests**

Expected: classification shape tests pass; execution cases remain fixture-stubbed.

- [ ] **Step 6: Commit**

~~~text
git add docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md catalog/schemas/experiment_spec_v1_1.schema.json catalog/schemas/experiment_capability_descriptor.schema.json configs/experiment_capability_registry_v1.yaml configs/hypothesis_fast_lane_v1.yaml tests/test_fast_lane_classifier.py src/solana_alpha_lab/factory/lane_classifier.py
git commit -m "feat(factory): define governed hypothesis fast lane"
~~~

### Task 2: Immutable research event store and writer lease

**Files:**

- Create: catalog/schemas/research_event_envelope.schema.json
- Create: src/solana_alpha_lab/factory/research_store.py
- Create: tests/test_research_store.py
- Reuse: src/solana_alpha_lab/storage/manifests.py
- Reuse patterns from: src/solana_alpha_lab/storage/parquet_store.py

**Interfaces:**

- Consumes: ResearchEvent, PartitionManifest, DatasetManifest.
- Produces: ResearchStore.append, CommitReceipt, writer lease, verified committed-partition iterator.

- [ ] **Step 1: Write failing atomicity and integrity tests**

Cover create-only publication, identical replay, conflicting transaction ID, path traversal, absolute-path rejection, payload hash mismatch, duplicate record ID, second writer, crash before manifest, and read-after-publish.

~~~python
def test_orphan_partition_is_not_visible(tmp_path: Path) -> None:
    store = research_store(tmp_path)
    store.test_write_partition_without_manifest([event_fixture()])
    assert tuple(store.iter_committed_records()) == ()


def test_second_writer_fails_closed(tmp_path: Path) -> None:
    first = research_store(tmp_path)
    second = research_store(tmp_path)
    with first.writer_lease():
        with self.assertRaisesRegex(ResearchStoreError, "WRITER_BUSY"):
            second.append([event_fixture()], transaction_id="RESEARCH-TXN-002")
~~~

- [ ] **Step 2: Run and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_research_store
~~~

- [ ] **Step 3: Implement deterministic Arrow schema and canonical payload hashing**

Use compression NONE, dictionary disabled, microsecond UTC timestamps, deterministic row ordering, and read-back validation as in the existing raw Parquet writer.

- [ ] **Step 4: Implement create-exclusive writer lease and manifest-last publication**

No dependency adoption. Never auto-steal a foreign/unverifiable lease.

- [ ] **Step 5: Pass storage tests on Windows-compatible and Linux-compatible paths**

Use pathlib and stdlib primitives only; tests must not rely on fcntl.

- [ ] **Step 6: Commit**

~~~text
git add catalog/schemas/research_event_envelope.schema.json src/solana_alpha_lab/factory/research_store.py tests/test_research_store.py
git commit -m "feat(factory): add immutable research event store"
~~~

### Task 3: DuckDB projection and deterministic prior-work search

**Files:**

- Create: schemas/research_memory_projection_v1.sql
- Create: tests/test_research_projection.py
- Modify: scripts/query_hypothesis_research_memory.py
- Modify: tests/test_task16_hypothesis_research_memory_query.py

**Interfaces:**

- Consumes: committed ResearchEvent partitions.
- Produces: rebuild_projection, seven owner-facing views, legacy/data-plane query adapters.

- [ ] **Step 1: Write failing projection tests**

Cover all required views, as-of exclusion, state ordering, invalid-not-negative, promotion-candidate-not-promoted, duplicate stable ID conflict, cross-plane hash conflict, bounded output, and deterministic tie break.

~~~python
def test_future_event_does_not_change_past_projection(tmp_path: Path) -> None:
    store = seeded_store(tmp_path, include_future_reject=True)
    rows = query_hypotheses(store, as_of="2026-08-25T00:00:00Z")
    assert rows[0]["derived_state"] == "RETAINED"


def test_invalid_run_is_not_negative_result(tmp_path: Path) -> None:
    rows = query_runs(seeded_store(tmp_path, terminal="INVALID"))
    assert rows[0]["trial_outcome"] == "INVALID"
    assert rows[0]["scientific_terminal"] == "INVALID"
~~~

- [ ] **Step 2: Run and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_research_projection tests.test_task16_hypothesis_research_memory_query
~~~

- [ ] **Step 3: Implement tracked DDL and rebuild**

Disable external access and unsigned extensions. Build beside the current projection, validate, then atomically replace derived state.

- [ ] **Step 4: Refactor T16 query logic without changing legacy output**

Move reusable scoring/validation into importable functions. Preserve current CLI and tests, then add a data-plane adapter.

- [ ] **Step 5: Add deterministic 10,000-event performance fixture**

Generate it inside the test temp directory from a fixed seed; do not commit 10,000 rows.

- [ ] **Step 6: Run projection, legacy query, and performance tests**

All must pass with zero network calls.

- [ ] **Step 7: Commit**

~~~text
git add schemas/research_memory_projection_v1.sql scripts/query_hypothesis_research_memory.py tests/test_research_projection.py tests/test_task16_hypothesis_research_memory_query.py
git commit -m "feat(factory): project and search research memory"
~~~

### Task 4: Stable evidence resolver, run passport, and classifier completion

**Files:**

- Create: catalog/schemas/run_passport.schema.json
- Create: src/solana_alpha_lab/factory/data_resolver.py
- Create: src/solana_alpha_lab/factory/run_passport.py
- Modify: src/solana_alpha_lab/factory/lane_classifier.py
- Modify: tests/test_fast_lane_classifier.py

**Interfaces:**

- Consumes: Catalog stable IDs, dataset manifests, query recipes, capability descriptors.
- Produces: ResolvedEvidence, run_key_sha256, RunPassport, full LaneDecision.

- [ ] **Step 1: Write failing resolver/passport tests**

Cover Catalog asset hash, dataset fingerprint, query recipe hash, PIT cutoff, physical-path omission, canonical Decimal, order-independent set fields, uv.lock hash, exact duplicate, and dirty referenced implementation.

- [ ] **Step 2: Run and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_classifier
~~~

- [ ] **Step 3: Implement resolver with stable logical URIs**

Do not accept arbitrary filesystem paths for Fast Lane bindings. A process-local physical path may exist only inside ResolvedEvidence.

- [ ] **Step 4: Implement canonical passport and deterministic run key**

Validate with JSON Schema and Pydantic. Reject non-finite numbers and absolute paths.

- [ ] **Step 5: Complete classification precedence and reason codes**

The same input must produce byte-identical LaneDecision JSON.

- [ ] **Step 6: Run focused tests and commit**

~~~text
git add catalog/schemas/run_passport.schema.json src/solana_alpha_lab/factory/data_resolver.py src/solana_alpha_lab/factory/run_passport.py src/solana_alpha_lab/factory/lane_classifier.py tests/test_fast_lane_classifier.py
git commit -m "feat(factory): resolve fast-lane evidence and passports"
~~~

### Task 5: Backward-compatible document execution and no-Git write fence

**Files:**

- Modify: src/solana_alpha_lab/factory/experiment_spec.py
- Modify: src/solana_alpha_lab/factory/runner.py
- Create: tests/test_fast_lane_runner.py

**Interfaces:**

- Consumes: validated ExperimentSpec document, LaneDecision, RunContext, ResearchStore.
- Produces: ExperimentRunner.start_document; legacy start delegates unchanged.

- [ ] **Step 1: Write failing compatibility and execution tests**

Cover legacy spec path behavior, external data-plane spec, completed offline result, negative result as exit success, output confinement, pre/post Git status equality, capability gap no execution, live phrase missing zero calls, and provider budget accounting through hooks.

~~~python
def test_offline_document_run_does_not_mutate_repo(tmp_path: Path) -> None:
    before = repository_status_bytes(ROOT)
    result = run_offline_document(tmp_path)
    after = repository_status_bytes(ROOT)
    assert result["status"] == "COMPLETE"
    assert before == after
    assert result["git_mutation_count"] == 0
    assert result["provider_calls_actual"] == 0
~~~

- [ ] **Step 2: Run and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_runner
~~~

- [ ] **Step 3: Add validate_experiment_document and start_document**

Keep existing public functions. Do not broaden CAPABILITY_ROUTER implicitly; capability registry and router must agree exactly.

- [ ] **Step 4: Implement RUN_STARTED and atomic terminal bundle**

Terminal bundle contains run, metrics, evidence bindings, optional trial, and optional decision event in one transaction partition.

- [ ] **Step 5: Implement repository status write fence**

On mismatch, do not revert. Persist only hashes and typed diagnostics under data root.

- [ ] **Step 6: Pass legacy and new tests**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_runner tests.test_factory_v1_product_kernel tests.test_factory_v1_commissioning
~~~

- [ ] **Step 7: Commit**

~~~text
git add src/solana_alpha_lab/factory/experiment_spec.py src/solana_alpha_lab/factory/runner.py tests/test_fast_lane_runner.py
git commit -m "feat(factory): execute accepted hypotheses outside git"
~~~

### Task 6: Operator CLI, commissioning proof, and promotion preparation

**Files:**

- Create: scripts/hypothesis_fast_lane.py
- Create: tests/test_fast_lane_cli.py
- Create: tests/fixtures/fast_lane/

**Interfaces:**

- Consumes: classifier, resolver, runner, research store, projection.
- Produces: deterministic CLI JSON and offline commissioning command.

- [ ] **Step 1: Write failing CLI contract tests**

Test every required command, exit code, bounded output, no path leak, one terminal, one next action, and promotion prepare-only behavior.

- [ ] **Step 2: Run and confirm failure**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_cli
~~~

- [ ] **Step 3: Implement doctor, classify, submit, run, show, search, replay, rebuild, and prepare-promotion**

Use one parser and one JSON output function. Never emit a raw exception traceback for a contract failure.

- [ ] **Step 4: Implement commission-offline**

Use CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001 and existing immutable evidence. It must verify:

~~~text
provider calls = 0
Git pre/post status identical
run persisted outside Git
projection rebuild succeeds
prior-work search returns run
replay digest matches
~~~

- [ ] **Step 5: Pass CLI tests and run the fixture commissioning proof**

The fixture proof is part of PR validation. The real post-merge commissioning remains a no-Git runtime action.

- [ ] **Step 6: Commit**

~~~text
git add scripts/hypothesis_fast_lane.py tests/test_fast_lane_cli.py tests/fixtures/fast_lane
git commit -m "feat(factory): add hypothesis fast-lane operator CLI"
~~~

### Task 7: Catalog integration, generated navigation, acceptance, and one PR

**Files:**

- Modify: catalog/query_recipes.yaml
- Modify: catalog/assets/lifecycle.yaml
- Modify through generator: catalog/catalog_manifest.yaml
- Modify through generator: catalog/generated/asset_edges.json
- Modify through generator: docs/PROJECT_MAP.md
- Modify: docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md

**Interfaces:**

- Consumes: accepted modules, schemas, tests, and query recipes.
- Produces: static Catalog discovery and exact foundation completion evidence inside the task contract or the repository’s normal completion packet; no dynamic hypothesis/run Catalog entries.

- [x] **Step 1: Add only static Catalog assets and bounded query recipes**

Register the CLI, schemas, DDL, config, capability registry, tests, ADR, and task. Do not register runtime records.

- [x] **Step 2: Generate Catalog/navigation outputs**

Use the accepted generator. Never hand-edit generated files.

- [x] **Step 3: Run targeted complete behavior suite**

~~~text
uv run --locked --managed-python python -B -m unittest tests.test_fast_lane_classifier tests.test_research_store tests.test_research_projection tests.test_fast_lane_runner tests.test_fast_lane_cli tests.test_task16_hypothesis_research_memory_query tests.test_factory_v1_product_kernel tests.test_factory_v1_commissioning
uv run --locked --managed-python python -B scripts/validate_catalog.py
~~~

- [x] **Step 4: Run existing repository-prescribed proportional validation**

Use Delivery Harness routing for the exact task. Do not change Harness to make the task pass.

- [x] **Step 5: Perform self-review**

Verify:

~~~text
foundation provider calls = 0
TWO_RUNG untouched and unexecuted
no new dependency
no dynamic run in Git
no absolute paths
no secret-like values
legacy Factory behavior preserved
DuckDB rebuild equality proven
exact duplicate prevented
promotion not automatic
~~~

- [x] **Step 6: Commit final generated/contract changes**

~~~text
git add catalog/query_recipes.yaml catalog/assets/lifecycle.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md docs/tasks/HYPOTHESIS_FAST_LANE_AND_RESEARCH_DATA_PLANE_V1.md
git commit -m "docs(factory): register hypothesis fast-lane foundation"
~~~

- [x] **Step 7: Push one task branch and open one PR**

Do not open intermediate PRs. Let exact-head CI run once on the completed candidate.

- [ ] **Step 8: Stop at the exact merge gate**

Return FAST_LANE_FOUNDATION_READY_FOR_MERGE, PR URL, exact head, CI, provider-call count 0, and the exact merge phrase. Do not start offline commissioning before main contains the merge.

## 25. Required acceptance tests

### 25.1 Classification

- all seven decision precedence branches;
- capability descriptor status and hash;
- parameter schema;
- query recipe binding;
- PIT/as-of;
- output zone;
- provider authority;
- promotion intent;
- exact duplicate.

### 25.2 Storage

- create-only publication;
- replay-identical;
- conflict;
- manifest-last visibility;
- orphan detection;
- two writers;
- stale same-host lease recovery;
- foreign lease denial;
- path/symlink traversal;
- deterministic Parquet bytes;
- payload/manifest/read-back hash.

### 25.3 Projection

- rebuild from empty and populated store;
- seven required views plus capability_gaps;
- as-of state;
- correction/supersession;
- future event exclusion;
- invalid versus negative;
- nomination versus promotion;
- cross-plane conflict;
- deterministic digest.

### 25.4 Runner

- legacy path compatibility;
- external spec document;
- zero Git mutation;
- scientific negative as completed run;
- blocked data;
- missing authority zero calls;
- exact provider call accounting through test hooks;
- terminal transaction atomicity;
- replay.

### 25.5 Search

- exact IDs and hashes;
- mechanism/falsifier/regime terms;
- dataset and capability;
- negative/inconclusive/invalid/dormant;
- stable tie break;
- max 50;
- what_changed;
- legacy plus data-plane union.

### 25.6 Promotion

- only RETAINED may be nominated;
- nomination is not PROMOTE;
- packet contains hashes and no raw data;
- no Git mutation;
- owner decision remains required.

## 26. Definition of done

Foundation is done only if:

1. all hard acceptance criteria pass;
2. exact-head CI is green;
3. one foundation PR is ready for merge;
4. no provider call occurred;
5. TWO_RUNG remained frozen;
6. dynamic research data is absent from the Git diff;
7. existing v1.0 Factory and T16 query behavior remains compatible;
8. one offline fixture demonstrates the entire path;
9. the post-merge command is exactly COMMISSION HYPOTHESIS_FAST_LANE_OFFLINE_V1;
10. no second implementation atom is started.

## 27. Foundation terminal and NEXT map

| Terminal | Meaning | Exactly one NEXT |
|---|---|---|
| FAST_LANE_FOUNDATION_READY_FOR_MERGE | Implementation and exact-head CI pass | Merge exact PR head |
| DEPENDENCY_NOT_MERGED | Atom B not on fresh main | Finish Atom B only |
| FOUNDATION_CONTRACT_CONFLICT | Current repository truth contradicts this contract materially | Return conflict evidence for owner reframe |
| FOUNDATION_VALIDATION_FAILED | Candidate implementation fails tests/CI | Fix inside the same atom and same PR; do not create suffix atom |
| FOUNDATION_SCOPE_BREACH | Provider/live/TWO_RUNG/new dependency/control-runtime mutation attempted | Stop and report |

After successful merge:

| Runtime terminal | Exactly one NEXT |
|---|---|
| NO_GIT_FAST_LANE_PROVEN | CLASSIFY TWO_RUNG_LIVE_H900_V1 FOR FAST_LANE ONLY |
| FAST_LANE_COMMISSIONING_FAILED | Repair the foundation only if the failure is a capability-plane defect; otherwise correct data-root/config and rerun without Git |

## 28. Future operating policy

For every new hypothesis, the owner/agent asks one machine question first:

~~~text
Can the exact structured request be satisfied by accepted capabilities,
accepted parameter schemas, immutable inputs, and allowed effects?
~~~

If yes, run it. If no, produce the exact missing capability. If it changes product behavior, prepare promotion. No agent may substitute a PR by habit or skip a necessary PR by optimism.

The desired steady-state loop is:

~~~text
submit structured hypothesis
→ deterministic classify
→ instant contract preflight
→ execute accepted capability
→ append immutable result
→ rebuild/read projection
→ reject, retain, or nominate
~~~

No branch, PR, or full CI exists inside that loop.

## 29. Final guardrails

- Git stores the factory, not every product of the factory.
- Parquet stores durable research events and data, not executable code.
- DuckDB accelerates reads and owns no irrecoverable truth.
- SQLite coordinates jobs and owns no scientific conclusion.
- Catalog indexes static capabilities and entrypoints, not every run.
- A local file without a manifest is not accepted evidence.
- A positive run is not alpha.
- A nomination is not promotion.
- No-Git is not no-governance.
- Existing capability means accepted, hash-resolved, parameter-bounded, PIT-safe, and data-plane-writing capability; merely having a script is insufficient.
- TWO_RUNG stays frozen until the foundation is merged, offline no-Git commissioning passes, and classification names its actual lane.
