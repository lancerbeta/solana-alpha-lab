# Owner Lifecycle Projection Spine V1

Derived index envelope for Solana Memecoin Intraday Alpha Lab (SMIAL).
Machine tokens live in `configs/owner_lifecycle_projection_v1.yaml`.
This document explains meaning. It owns no lifecycle, science, risk,
authority, or economics.

Catalog current binding: `ACTIVE-OWNER-LIFECYCLE-PROJECTION`
Semantic route: `SEM-OWNER-LIFECYCLE`
Schema: `smial.owner-lifecycle-projection` / `1.0`

## 1. Job

Answer, deterministically:

```text
WHAT IS THIS?
WHERE DID IT COME FROM?
WHAT STATE DOES ITS OWNER EXPLICITLY REPORT?
WHAT IS IT EXPLICITLY LINKED TO?
HOW FRESH / AVAILABLE IS THAT INFORMATION?
WHAT IS UNKNOWN?
```

The projection is rebuilt from source owners every call. It is not a second
truth store. A rendered snapshot is never canonical.

```text
SOURCE OWNERS
    → adapters (read only)
    → LifecycleProjectionV1  (OWNS NO TRUTH)
    → FactoryApplication.lifecycle_projection()
    → inspection CLI / future Workbench Moves 1+
```

`authority_granted = false` always. `authority_required` is descriptive only.

## 2. Conceptual spine (only where contracts prove it)

```text
research / hypothesis
        ↓
experiment
        ↓
evidence / decision
        ↓
StrategyVersion
        ↓
activation / bot
        ↓
signal / execution
        ↓
position / exit
        ↓
reconciliation / economics
```

An incomplete graph with explicit `GAP` / `UNKNOWN` is success when that is
what current truth supports. A visually complete graph built from guesses is
failure.

## 3. Current source owners

| Source | Truth plane | Current role |
| --- | --- | --- |
| `configs/experiment_specs/*.yaml` | GIT | ExperimentSpec identity and explicit `hypothesis_version` |
| `configs/strategies/*.yaml` | GIT | StrategyVersion identity and explicit provenance |
| `registries/decisions_negative_results.yaml` | GIT | Decision / negative-result records |
| `registries/global_trial_ledger.yaml` | GIT | Historical trial records; native `outcome` preserved |
| `registries/hypotheses.yaml` | GIT | EMPTY envelope; not complete current research truth |
| `registries/research_cycles.yaml` | GIT | EMPTY envelope; not complete current research-cycle truth |
| `registries/strategies.yaml` | GIT | EMPTY envelope; not complete current strategy truth |
| `registries/bot_instances.yaml` | GIT | EMPTY envelope; not complete current bot truth |
| ResearchStore | EVIDENCE | Typed research events when a data root already exists |
| OperationalStore | RUNTIME | `JOB-{experiment_id}` when the sqlite file already exists |
| PaperPlaneStore | RUNTIME | Bots / positions / events when the sqlite file already exists |

Do not backfill the four empty registries to make architecture symmetrical.
Current research truth lives in ResearchStore (when present) and Git
ExperimentSpec / negative-decision memory. Current strategy truth lives in
Git StrategyVersion configs. Current bot/position truth lives in
PaperPlaneStore.

## 4. Identity

Allowed:

- exact stable domain ID (`EXP-…`, `HYP-…`, `STRAT-…@V1`, `NEGATIVE-…`, `BOT-…`, `POS-…`, `JOB-…`)
- explicit source foreign key
- documented deterministic contract key (`JOB-{experiment_id}`)

Forbidden: filename stem, nearby directory, similar title, temporal
proximity, mint alone, narrative similarity, regex on `summary`, LLM match.

StrategyVersion identity is `{strategy_id}@{strategy_version}`.
PaperPlane `start_bot` stores `strategy_version` as
`{strategy_id}-{strategy_version}`; inverting that encoding is
`EXPLICIT_CONTRACT_KEY`, not filename inference.

Exact-merge of facets is allowed only when
`(projection_class, native_kind, entity_id, truth_plane)` match and source
contracts establish that identity. The same `entity_id` on different truth
planes stays as separate entities plus `IDENTITY_CONFLICT`. Conflicting
decision-relevant fields on one plane emit `STATE_CONFLICT` with
`native_state=null` and `display_state=CONFLICT`. Newer timestamp must not
win across planes. Execution events without `event_id` are omitted with
`MISSING_STABLE_ID`; no synthetic `EXEC-EVENT-{index}`.

## 5. Relations

First-class outputs. `derivation_method` only:

- `EXPLICIT_SOURCE_FIELD`
- `EXPLICIT_FOREIGN_KEY`
- `EXPLICIT_CATALOG_RELATION`
- `EXPLICIT_CONTRACT_KEY`

No `INFERRED_BY_NAME`, `INFERRED_BY_TIME`, or text similarity.

`resolution`: `RESOLVED` | `TARGET_GAP` | `SOURCE_GAP` | `CONFLICT`

```text
RESOLVED = endpoint identity unambiguous in current projection
```

If `from_entity_id` or `to_entity_id` is materialized on more than one
`truth_plane` without a proving identity contract, `resolution = CONFLICT`.
Entities stay separate. Existing `IDENTITY_CONFLICT` remains visible.
Do not pick a plane by timestamp, source order, or source priority.

A relation to a stable ID whose target is not materialized remains visible
with `TARGET_GAP`. Do not synthesize the target.

## 6. Gaps

Top-level `gaps[]` is product output. Missing is not zero.

Source status distinguishes `EMPTY` ≠ `NOT_PRESENT` ≠ `UNAVAILABLE` ≠ `INVALID`.

Freshness does not collapse Git currentness, evidence clocks, and runtime
readback into one boolean. If a source defines no SLO, `freshness.status = UNKNOWN`.

Evidence classes stay explicit. No BACKTEST/PAPER/SHADOW/LIVE blending.

## 7. Application boundary

```text
FactoryApplication.read_model()
    = selected ExperimentSpec / cockpit / optional PAPER surfaces

FactoryApplication.lifecycle_projection()
    = whole known lifecycle universe; independent of selected spec
```

Inspection CLI `scripts/show_owner_lifecycle_projection.py` is for
acceptance, agent debugging, and recovery. Machine JSON is the inspection
format, not a second truth owner. It is not the owner UX.
Move 1 provides the Research Workbench.

Workbench (`src/solana_alpha_lab/factory/workbench.py`) consumes this
index for `/research` presentation. It does not own lifecycle joins or
source truth. Visual presentation is owned by
`SMIAL_VISUAL_OPERATING_SYSTEM_V1` / `SEM-VISUAL-OPERATING-SYSTEM`.
This spine supplies semantics, not CSS.

## 8. Git vs operational state

```text
CHANGE WHAT PRODUCT MEANS     → Git / version
OPERATE ACCEPTED PRODUCT      → runtime event / command
OBSERVE WHAT ACTUALLY HAPPENED → evidence / machine readback
```

Git may contain schema, adapters, Catalog, tests, and this contract.
Git must not receive current bot/position/run/alert/PnL snapshots.
Ordinary research or trading operation must not open a PR to refresh the
projection. There is no `lifecycle_projection.sqlite`.

## 9. Future Moves

| Move | Must |
| --- | --- |
| 1 `RESEARCH_LIFECYCLE_WORKBENCH_V1` | Consume this index; do not rebuild joins from empty registries |
| 2 `EXPERIMENT_EVIDENCE_DECISION_V1` | Index = identity/link/status; science stays ExperimentSpec/Runner |
| 3 `SCIENCE_TO_STRATEGY_HANDOFF_V1` | Explicit decision → StrategyVersion only |
| 4 `TRADING_OPERATIONS_WORKBENCH_V2` | Git StrategyVersion + PaperPlane via projections; commands via FactoryApplication |
| 5 `OWNER_ATTENTION_AND_CHANGE_FEED_V1` | Attention derived from sources; no attention database |
| 6 `SYSTEM_OPERABILITY_SURFACE_V2` | Runtime health from machine readback, never Git capability |
| 7 `RISK_AND_ECONOMICS_V1` | Evidence class remains explicit |
| 8 `MARKET_DATA_AWARENESS_V1` | Remains trigger-gated |

Do not auto-start Move 1 from this atom.

## 10. Extension

New source: prove named consumer → narrow adapter → keep V1 entity envelope
→ bump compatibly → no new truth store. If a relation is missing, emit GAP
first. Repair only when a named owner workflow needs it.
