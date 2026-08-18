---
intent_id: ARCH-INTENT-005
intent_version: '1.0'
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
as_of: '2026-08-18'
truth_owner: USER_GOAL_OWNER
projection_kind: PRODUCT_VISION_NOT_IMPLEMENTATION
implementation: NOT_IMPLEMENTED
milestone_id: FACTORY_V1_OPERATIONAL_READY
milestone_status: NOT_TRIGGERED
extends:
  - ARCH-INTENT-002
  - ARCH-INTENT-003
  - ARCH-INTENT-004
  - DELIVERY_HARNESS_V1
authority:
  provider_read: false
  wallet_signer_transaction: false
  cash_spend: false
  project_source_mutation: false
  ui_framework_selection: false
  deployment: false
contains_secrets: false
---

# ARCH-INTENT-005 — Factory v1 Operational Readiness and Owner Experience

This intent accepts a product milestone named `FACTORY_V1_OPERATIONAL_READY`.
It does not implement Owner Cockpit, a generic experiment runner,
production-lite runtime, monitoring product, paper/shadow operations, or
real-money execution. It selects no UI framework and authorizes no purchase
or deploy.

## 1. Product decision

`FACTORY_V1_OPERATIONAL_READY` does not mean a profitable strategy exists,
Alpha/Execution Fit exists, real-money trading is authorized, all planned
infrastructure exists, or every analytical method is implemented.

It means:

> The owner can introduce a new bounded hypothesis, understand its state,
> obtain or reuse the required evidence, run a reproducible experiment,
> receive a decision-bearing result, inspect why the result occurred, and
> stop/recover the system — predominantly through reusable Factory
> capabilities rather than new core-product development.

After this milestone, comparable hypotheses should normally add:

`hypothesis definition + configuration + data/query composition + optional hypothesis-specific analytical module`

rather than another bespoke platform slice.

## 2. Problem

The project already has strong research-truth infrastructure, but a large
portion of product capability is distributed across task-specific contracts,
scripts, evidence records and CLI flows.

This creates three risks:

1. scientifically correct work can continue indefinitely without producing
   an owner-operable product;
2. each new hypothesis may trigger bespoke engineering instead of exercising
   reusable Factory capabilities;
3. the owner may need Git archaeology or agent mediation to answer ordinary
   operating questions.

The missing product is not another research framework. The missing product
is the operating surface around the existing Factory truth.

## 3. Owner / primary user

Primary user: `GOAL_OWNER / SINGLE_OPERATOR`.

The owner is not expected to know repository paths, inspect YAML to
understand normal operating state, manually join evidence tables, remember
which provider or experiment failed last week, infer whether a number is
historical, PIT, modeled or realized, or inspect logs to learn whether the
system needs attention.

The product should preserve engineering/scientific rigor while hiding
irrelevant implementation detail by default.

## 4. Current product stage

```yaml
research_truth_substrate: ADVANCED
hypothesis_lifecycle: FUNCTIONAL
research_memory: FUNCTIONAL
data_evidence_spine: FUNCTIONAL_WITH_GAPS
provider_routes: PARTIAL
generic_hypothesis_runner: NOT_OPERATIONAL_AS_PRODUCT
owner_cockpit: NOT_IMPLEMENTED
production_lite_runtime: NOT_IMPLEMENTED
unattended_monitoring: NOT_IMPLEMENTED
paper_shadow_position_operations: NOT_OPERATIONAL
micro_live: OUT_OF_SCOPE_FOR_FACTORY_V1
```

## 5. Target owner experience

```text
CAPTURE IDEA
    ↓
see related prior hypotheses / evidence / negative results
    ↓
freeze hypothesis + falsifier
    ↓
see:
  AVAILABLE DATA
  MISSING DATA
  COST / TIME
  CHEAPEST FALSIFIER
    ↓
START / PARK / REJECT
    ↓
Factory acquires/reuses bounded evidence
    ↓
experiment runs
    ↓
owner receives:
  result
  uncertainty
  robustness
  failure modes
  evidence links
  recommendation
    ↓
KILL / EXTEND / REDESIGN / PROMOTE
    ↓
all history retained automatically
```

The owner should not need to know which internal task IDs, scripts or table
names executed this journey.

## 6. Required Factory v1 product surfaces

Sections 6.1–6.7 and 8 are an accepted owner-experience map. They are not
the `FACTORY_V1_OPERATIONAL_READY` PASS checklist. That checklist is only
`milestone.requires` plus `gate` in
`configs/factory_v1_operational_readiness_v1.yaml`. Substituting a methods
or cockpit-screen inventory for the commissioning run is a Factory
readiness FAIL or REPLAN.

These surfaces are accepted direction. They are not implemented by this
intent.

### 6.1 Owner Home / Attention Queue

Default screen answers: what needs attention now; which hypothesis is
moving; what changed since the previous visit; whether market/data/provider
/runtime health is normal; whether anything is blocked; what decision
becomes possible next; what is being spent; whether unresolved
market/execution risk exists.

Every attention item contains `WHY_NOW / IMPACT / EVIDENCE / NEXT_SAFE_ACTION`.
No generic red notification dots.

### 6.2 Research Workbench

Required concepts: Idea, Hypothesis Family, Hypothesis Version, Research
Cycle, Data Requirement, Experiment, Trial, Evidence, Decision, Derived
Insight.

Required operations: capture idea, view prior related work, create/freeze
hypothesis, inspect data coverage, prepare experiment, run/stop experiment,
inspect result, compare trials, record decision, derive next hypothesis,
park/reactivate.

AI may propose hypotheses, methods or interpretations. AI may not silently
modify frozen hypotheses, consume holdouts, promote strategies, hide
negative trials, or redefine missing evidence.

### 6.3 Data & Provider Surface

For every named research consumer show field/dataset/route, coverage, first
reliable availability, freshness, missingness, source, PIT status, cost,
quota, latest failure, latest successful evidence, and consumer.

The user should see the semantic distinction between `NO_DATA / UNKNOWN /
PROVIDER_FAILURE / NO_ROUTE / NOT_APPLICABLE`.

### 6.4 Experiment Lab

The Factory should provide reusable experiment composition rather than
one-off task code. A comparable new hypothesis should usually change
`ExperimentSpec`, not the runner.

Owner-experience map (WATCH, not Factory v1 PASS inventory): descriptive
distributions, cohort comparison, event study, path MAE/MFE, route
liquidity surface, missingness and selection audit, chronological
walk-forward, cluster-block bootstrap, sensitivity analysis,
concentration analysis, negative controls/placebos, multiple-testing
accounting. Sequential decision boundary is supported when justified.

Discovery output is hypothesis-generating evidence, not confirmatory
evidence. Unsupervised clustering and AI-assisted pattern generation are
exploration-only. Any value-inspecting search that affects selection must
be recorded in trial/search history.

### 6.5 Evidence / Decision View

Every result page should display without drill-down: QUESTION, ESTIMAND,
POPULATION, N / independent clusters, DATA COVERAGE, MISSINGNESS, RESULT,
UNCERTAINTY, COST ASSUMPTIONS, ROBUSTNESS, WORST CASE / FAILURE MODES,
HOLDOUT STATUS, WHAT WOULD INVALIDATE THIS, DECISION.

Every chart displaying a market or performance result must expose
`as_of / population / n / missingness / units / evidence class`.
No visually impressive chart may hide inadequate effective sample or
`UNKNOWN`.

### 6.6 Provider / Runtime Health

Minimum dimensions: process alive, last successful observation, data
freshness, clock lag, provider status, route status, schema drift, error
rate, quota/credits, cash cost, disk, backup age, restore status,
experiment stalled. "Process alive" alone is never healthy.

### 6.7 Alerts

P0: possible unresolved position, reconciliation failure, kill-switch
failure, monitoring blind while risk may exist.

P1: provider/data stale beyond consumer SLO, experiment stuck,
backup/recovery failure, quota/cost boundary approaching, repeated
schema/route failure.

P2: experiment completed, evidence sufficiency reached, owner decision
available, hypothesis became eligible for re-review.

Notifications must be deduplicated and actionable. An alert must state
`WHAT / WHY IT MATTERS / CURRENT SAFE STATE / REQUIRED ACTION`.

## 7. Trading and position experience

Factory v1 itself does not require real-money execution. The architecture
must already reserve the correct objects and views.

PAPER / SHADOW activation adds: Watchlists, Signals, Execution Intents,
Quotes / Routes, Shadow Attempts, Positions, Exit Readiness, PnL class.

MICRO-LIVE activation later adds: actual fills, fees, inventory,
settlement, capital, exposure, daily loss, kill switch, reconciliation,
realized NetReturn, owner cashflow.

The same conceptual position lifecycle must survive
`replay -> paper -> shadow -> live`. Do not create separate incompatible
models for each mode.

```text
WATCHED
→ SIGNALLED
→ INTENT_CREATED
→ ATTEMPTING
→ OPEN / PARTIAL / UNKNOWN
→ EXIT_REQUIRED
→ EXITING
→ CLOSED / UNRESOLVED
→ RECONCILED
```

No position is silently removed because quote/route disappears.

This lifecycle is the same conceptual chain as ARCH-INTENT-002. Mapping
before any implementation atom: `WATCHED` is not `watchlist_membership`;
`SIGNALLED` is not the trigger object; `strategy_version` and
`activation_epoch` remain separately versioned. Do not spawn a second
incompatible position model.

## 8. Owner Cockpit navigation

```text
HOME
├─ Attention / Today
├─ Factory throughput
└─ System health

RESEARCH
├─ Ideas
├─ Hypotheses
├─ Experiments
├─ Evidence
└─ Decisions

MARKET / DATA
├─ Cohorts
├─ Data explorer
├─ Providers & routes
└─ Data quality

OPERATIONS
├─ Watchlists
├─ Signals
├─ Positions
├─ Execution / exits
└─ Incidents

ECONOMICS
├─ Research cost
├─ Trading result
├─ Infrastructure cost
├─ Capital / risk
└─ Owner FCF

SYSTEM
├─ Runtime
├─ Backups / recovery
├─ Deploy/version
└─ Audit/evidence links
```

Unavailable lifecycle stages should remain hidden or clearly disabled
instead of showing empty enterprise screens. This information architecture
is part of the owner-experience map, not the commissioning PASS checklist.

## 9. UX invariants

```yaml
ux:
  attention_first: true
  progressive_disclosure: true
  evidence_linked: true
  explain_why: true
  what_changed_since_last_view: true
  explicit_unknown: true
  task_oriented_not_crud_oriented: true
  safe_defaults: true
  read_model_not_truth_owner: true
  high_impact_actions_separate_from_read_ui: true
  reversible_where_possible: true
```

The normal owner view prioritizes conclusions and actions. Raw JSON,
hashes, schemas and lineage remain one drill-down away.

## 10. Factory operating metrics

Do not use number of tasks, commits, schemas or bots as factory-success
metrics. Track learning velocity, factory leverage, research quality and
operations as named in
`configs/factory_v1_operational_readiness_v1.yaml`.

## 11. Factory v1 Operational Readiness Gate

`FACTORY_V1_OPERATIONAL_READY = PASS` only when every mandatory condition
in the YAML contract passes. A failure of the commissioning hypothesis may
still be a PASS for Factory readiness. A requirement to build another
bespoke pipeline is a Factory readiness FAIL or REPLAN.

The commissioning hypothesis must deliberately use capabilities the Factory
claims are already reusable. It must not be selected because it requires a
large new component. Its purpose is simultaneously to obtain genuine market
information and to acceptance-test the Factory as a reusable product.

## 12. Foundation freeze after readiness

After `FACTORY_V1_OPERATIONAL_READY`, comparable hypothesis work defaults
to configuration, feature/query, data requirement, experiment-method
composition, or a provider adapter for a named gap. Core product change
requires a reusable capability gap, second named consumer, correctness or
research-truth defect, safety/reliability requirement, measured scale
bottleneck, or material owner-operability problem.

Forbidden justifications: cleaner architecture, future flexibility without
a consumer, generic platform aspiration, hypothesis-specific convenience
only. This is the point where backend development is expected to cool
materially.

## 13. Non-goals for Factory v1

Factory v1 does not require Kubernetes, microservices, a graph or vector
database, generic RAG, ClickHouse, PostgreSQL migration without a measured
transactional/concurrency need, a polished mobile application, multi-user
RBAC beyond the actual operator/security need, real-money execution, a
portfolio optimizer, autonomous AI trading, a broad all-Solana data
warehouse, advanced ML before simple methods fail, or a generic plugin
marketplace.

## 14. Architecture

```text
                        OWNER
                          │
                    Owner Cockpit
                    Research Workbench
                          │
                   ┌──────┴──────┐
                   │ Application │
                   │   Service   │
                   └──────┬──────┘
                          │
          ┌───────────────┼─────────────────┐
          │               │                 │
   Context Capsule   Experiment Runner   Command/Gate
      (read only)        / Scheduler       Boundary
          │               │                 │
          └───────┬───────┴─────────┬──────┘
                  │                 │
            Truth / Evidence      Provider
                Plane             Adapters
                  │                 │
       ┌──────────┼─────────┐       │
       │          │         │       │
      Git       Catalog  Registries │
       │                    │       │
       └────── Parquet / DuckDB ────┘
```

Truth owners remain unchanged:

```yaml
git:
  owns: immutable repository bytes and contracts
catalog:
  owns: discovery, location and relations
lifecycle_registries:
  owns: hypotheses, trials, decisions, strategies and bots
raw_parquet:
  owns: immutable market/provider observations
duckdb:
  owns: reproducible analytical projections and queries
owner_cockpit:
  owns: NOTHING
  role: derived read model + bounded command surface
```

## 15. Application service

Add only when implementation is triggered, consistent with ARCH-INTENT-004
excluding a service today. If started, it is a command gateway over
existing contracts: resolve context, create/freeze product objects through
those contracts, submit experiment jobs, read status, stop bounded jobs,
assemble owner read models, emit decision requests and serve evidence
links. It must not become a second lifecycle truth owner and must not
contain alpha-specific business rules. Hypothesis logic lives in versioned
experiment definitions/modules.

## 16. Generic experiment runner

Target contract:

```text
ExperimentSpec
    ↓
ContextResolver
    ↓
DataResolver
    ↓
CapabilityRouter
    ↓
ExperimentRunner
    ↓
Validation / Falsifier
    ↓
EvidenceRecorder
    ↓
DecisionProjection
```

`ExperimentSpec` should reference stable IDs rather than hard-coded task
paths.

## 17. Storage

Keep the analytical spine: immutable Parquet + DuckDB. Do not migrate
research truth merely to support a UI. For Factory v1, prefer a single
well-defined runtime writer boundary. That writer must not mutate raw
Parquet or lifecycle registries except through existing contracts. A
transactional/remote OLTP database is considered only when a measured
requirement appears. The new operational store, if later introduced, does
not replace Git/Catalog/evidence truth. Job state and attention-queue
bytes may not live only in DuckDB.

## 18. Research Workbench implementation boundary

The Workbench may combine reproducible Python analysis, SQL, interactive
visualization, experiment configuration and evidence browsing. Interactive
notebooks/apps are an implementation candidate, not a new truth owner.
Outputs that affect selection or decisions must be frozen into ordinary
Factory evidence. Hidden notebook state is not admissible evidence.

## 19. UI implementation boundary

Do not build a generic admin CRUD console. Build owner workflows. First
implementation should emphasize read models, attention queue, drill-down,
explicit actions, evidence provenance and safe state. The UI framework is
selected through a future `ADOPT -> WRAP -> FORK -> BUILD` gate. This
intent does not select it.

## 20. Runtime topology

First operational deployment target: one ordinary supported Linux VPS, one
reproducible deployment definition, one persistent data volume, one
independent backup failure domain, one owner-facing web endpoint, one
worker/scheduler boundary, simple alert delivery. No cluster is required.

Preserve `RPO_max: 24h`, `RTO_max: 12h`, clean rehost proof and rollback
proof. Actual VPS/provider/purchase remains a later external-authority
decision.

## 21. Monitoring architecture

Start with project-native observability: structured logs, health
endpoint/read model, freshness metrics, provider/route state, experiment
state, backup/recovery state, cost/quota state, Telegram owner alerts.
External observability is adopted only after a named incident/diagnostic
consumer proves value. Monitoring cannot turn `UNKNOWN` into healthy.

## 22. Analysis tooling architecture

Analytical tools are capabilities behind stable contracts, not brands. Each
tool declares input/output contract, PIT semantics, whether it is
selection-affecting, deterministic or calibrated, limitations, cost, named
consumer and validation evidence. New tools are not installed merely
because the category exists.

## 23. Position architecture

Preserve one event-sourced conceptual lifecycle from WATCHED through
RECONCILED. Mode-specific implementation may differ. Semantic meaning must
not.

## 24. Owner command boundary

Read operations and authority-bearing commands are separate surfaces. A
button is not authority. Material commands remain gated: buy provider plan,
deploy externally, activate strategy, change capital/risk, operate signer,
send transaction, merge destructive/configuration boundary.

## 25. Validation strategy

Factory v1 acceptance is not primarily a test-suite event. Required
sequence: golden historical cycle through generic runner, new real
commissioning hypothesis, new market evidence, experiment result, owner
decision, restart/recovery exercise, provider/data failure exercise, owner
Cockpit read-back, then `FACTORY_V1_OPERATIONAL_READY`.

The real commissioning hypothesis may fail scientifically. The Factory
should still pass if it produces the failure cheaply, honestly and
operably.

## 26. Roadmap integration

Do not insert a new chain of numbered tasks now. Add one triggered
milestone `FACTORY_V1_OPERATIONAL_READY` with status `NOT_TRIGGERED`.

Activation when any of: owner explicitly selects Factory productization;
first unattended remote runtime is next; long-running paper/shadow
observation is next.

Must not preempt the current cheapest decision-bearing market falsifier.

The live Git binding is
`configs/factory_v1_operational_readiness_v1.yaml`, resolved by this
task's harness `roadmap_path`. Historical Project Sources roadmaps are not
modified. Numbered `TASK-35A` in `ROADMAP-PATCH-T21-PRODUCT-VISION-001`
is a historical cockpit candidate, not a parallel activation chain.
Do not start TASK-35A beside this milestone.

## 27. Domain-policy integration

When `FACTORY_V1_OPERATIONAL_READY` is triggered, Entry Gate and Factory
Fit must resolve the readiness contract and prohibit substituting a list of
completed infrastructure components for the commissioning run.
Productization must not preempt a cheaper active market falsifier. After
readiness, comparable hypothesis work defaults to configuration/data/query
composition; repeated hypothesis-specific core code is a Factory Fit
architecture warning.

This atom does not mutate `delivery-harness/policies/solana-alpha-lab.md`
because live tests bind those bytes to historical harness-bootstrap and
TASK-30 A20R1 receipts. The invariant lives in this intent and the YAML
contract. Existing `FACTORY_LEVERAGE_INVARIANT` already covers the
composition default.

## 28. Tool / capability watch

`NOW: NONE`. WATCH entries in the YAML contract grant no installation,
credentials, network, deployment or spend authority.

## 29. Final product invariant

The Factory is not mature because it has many capabilities. It is mature
when adding another hypothesis is mostly research, not software
development, and the owner can understand what the system knows, does not
know, is doing, needs, costs and risks without becoming its system
administrator.

`FACTORY_V1_OPERATIONAL_READY` is the first milestone that proves this.
