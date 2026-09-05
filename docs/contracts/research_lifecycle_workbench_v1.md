# Research Lifecycle Workbench V1

Owner-facing read composition over `LifecycleProjectionV1`.
This document owns presentation and query semantics for `/research`.
It does not own hypothesis, experiment, runtime, evidence, or authority.

Catalog current binding: `ACTIVE-RESEARCH-LIFECYCLE-WORKBENCH`
Semantic route: `SEM-OWNER-LIFECYCLE` (second root binding)
Visual owner: `SMIAL_VISUAL_OPERATING_SYSTEM_V1`

```text
authority_granted = false
```

## 1. Owner questions

```text
Что у нас вообще есть?
Что сейчас реально выполняется?
Что уже проверяли?
Какие результаты/решения уже известны?
Что требует внимания?
Что blocked / unavailable / conflicted?
Откуда взялся конкретный объект?
С чем он явно связан?
Что о нём UNKNOWN?
Какое следующее безопасное действие сообщает source, если сообщает?
```

A partial but truthful page is PASS. A visually complete page from guessed
joins is FAIL.

## 2. Read-only boundary

```text
SOURCE OWNERS
    → LifecycleProjectionV1   (identity / relations / gaps)
    → research overview/detail (owner read composition)
    → /research
```

Workbench owns no lifecycle truth. It may filter/project
`RESEARCH`, `EXPERIMENT`, `EVIDENCE_DECISION` from the current projection.
It must not independently crawl ExperimentSpecs, StrategyVersion,
ResearchStore, or runtime stores to recreate identity or relations.

Source-specific detail lookup is allowed only after the projection has
identified the object and source. Locator parameters from the browser are
never filesystem paths, Catalog paths, SQLite tables, or raw `source_ref`.

Normal GET `/research` must cause:

```text
0 Git writes
0 ResearchStore writes
0 SQLite writes
0 provider calls
0 network calls except the local HTTP response
```

No mutation buttons on the universe/detail workflow.

## 3. Overview semantics

Counters describe materialized projection facts, not all reality.

| Counter | Rule |
| --- | --- |
| `ACTIVE NOW` | Accepted runtime/evidence source explicitly reports active/running. Git ExperimentSpec existence is not activity. If no activity-capable source is `AVAILABLE` or `EMPTY`, the counter is `NOT AVAILABLE`, not `0`. |
| `TRIALS` | Materialized `TRIAL` entities. |
| `DECISIONS` | Materialized `DECISION` / `DECISION_EVENT` entities. |
| `NEGATIVES` | Explicit `NEGATIVE_RESULT` records. Do not derive from generic `FAIL`. |
| `ATTENTION` | Explicit blocker, source `INVALID`/`UNAVAILABLE` with owner impact, identity/state conflict, or other explicit decision-relevant attention. Not every `TARGET_GAP`. |
| `GAPS` | Structural unresolved relations/source gaps. Not an error count. |

Missing runtime/evidence is not shown as zero. `completeness = PARTIAL`
when any accepted source is `NOT_PRESENT` / `UNAVAILABLE` / `INVALID`.
Evidence detail uses `source_owned_fields` copied in the same
LifecycleProjection adapter pass. Detail does not rescan ResearchStore
or match foreign keys from other records. Lineage and object gaps are
scoped to the selected locator plane and source, except `CONFLICT`
edges which remain visible on every involved plane.

Preferred degraded copy when ResearchStore is absent:

```text
Research evidence source is unavailable to this Workbench.
Git-tracked experiments/trials/decisions below remain available.
```

Groups prefer source-native states. Do not invent `KILLED`,
`READY_TO_TEST`, `DECISION_READY`, or `PROMOTION_CANDIDATE` from UI
heuristics. A negative result is not a killed hypothesis. A completed
run is not scientifically valid.

## 4. Locator semantics

A selected item is identified only by:

```text
entity_id + truth_plane + native_kind
```

This is a projection/UI selector, not a new domain identity. The same
`entity_id` on separate truth planes stays as distinct locators.
Request parameters are validated against the current projection.

## 5. Detail semantics

Detail shows source-provided fields only. Missing fields stay absent or
`UNKNOWN`. Next safe action is displayed only when an accepted source or
projection rule supplies it; otherwise `UNKNOWN`.

Lineage is a bounded inbound/outbound neighborhood of Move-0 relations.
`RESOLVED` is a normal TRACE. `TARGET_GAP` / `SOURCE_GAP` interrupt the
TRACE. `CONFLICT` is not a normal connected edge.

Chronology uses source clocks (`effective_at`,
`first_reliable_available_at`, `created_at`, `observed_at`). If
chronology cannot be established: `TIME_UNKNOWN`. Projection build time
and directory order are not event time.

## 6. Search / filter

Server-side GET only: `q`, `kind`, `truth_plane`, `state`,
`evidence_class`, `limit`. `q` length is bounded. Enum filters are
allowlisted. `limit <= 200`. No vector search, no client-side dataset
mirror, no cookies/localStorage.

Mechanism-specific prior-work search remains `SEM-PRIOR-WORK`.

## 7. Visual OS relationship

Shared chrome is `STEEL_SIGNAL` / `DARK_ONLY`. Detail is
`EVIDENCE_EDITORIAL`. Lineage is `COMPUTATIONAL_FIELD` / `TRACE`.
Tokens are read from the canonical Visual OS contract. Cyan is not
success. Red is scarce. `UNKNOWN` has text semantics. No second palette.

## 8. Future extension

Move 2 (`EXPERIMENT_EVIDENCE_DECISION_V1`) may add typed evidence-quality
detail for one real experiment. It must keep LifecycleProjection as the
identity layer. Frontend technology may change without moving truth.
Do not add a cache, theme service, router, or research mutation here.
