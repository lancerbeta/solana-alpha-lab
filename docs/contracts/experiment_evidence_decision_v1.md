# Experiment Evidence Decision V1

Owner loop that compresses one existing experiment into a research
decision. Extends Move 0 / Move 1. Does not own lifecycle identity,
ExperimentSpec meaning, or StrategyVersion.

Catalog document: `DOC-EXPERIMENT-EVIDENCE-DECISION-001`
Semantic route: `SEM-OWNER-LIFECYCLE` (existing; no new route)
Visual owner: `SMIAL_VISUAL_OPERATING_SYSTEM_V1`

```text
authority_granted = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
PROMOTE = scientific DECISION_EVENT only
```

## 1. Owner questions

```text
Что именно здесь проверяли и что реально получилось?
Какие доказательства прямые, какие только прошлый контекст?
Чего не хватает для научного решения?
Как зафиксировать REJECT / REVISE / PAUSE / PROMOTE без Git?
```

An incomplete experiment that shows gaps is PASS.
A visually complete page from guessed joins is FAIL.

## 2. Truth boundaries

```text
WHAT THE EXPERIMENT MEANS     → Git / ExperimentSpec
WHAT EXECUTION DID            → OperationalStore / ResearchStore runtime events
SCIENTIFIC EVIDENCE           → append-only ResearchStore
RESEARCH DECISION             → append-only DECISION_EVENT
CURRENT LIFECYCLE STATE       → derived LifecycleProjectionV1
WHAT THE OWNER SEES           → Workbench composition
WHAT THE OWNER COMMANDS       → FactoryApplication
STRATEGY DEFINITION           → Git / StrategyVersion (not this Move)
```

Hard invariants:

```text
UI != truth owner
GET /research != writer
RUN_COMPLETED != scientific validity
scientific PROMOTE != StrategyVersion
RELATED != DIRECT
TRANSLATION != SCIENTIFIC MUTATION
presentation translation owns zero scientific truth
```

## 3. Direct vs related

DIRECT evidence requires an explicit current relation:

```text
experiment_id / experiment_spec_id
run_id belonging to a DIRECT run of this experiment
trial_id belonging to a DIRECT trial of this experiment
evidence_binding targeting this experiment
dataset/result/content hash bound to this experiment
explicit Catalog/contract relation
```

Same-hypothesis historical trials, negatives and decisions without that
relation are `RELATED PRIOR MEMORY`. They must not strengthen this
experiment. Filename, directory, date, prose or LLM similarity is
`EVIDENCE_RELATION_GAP`, not a join.

## 4. Evidence obligations

No quality score. Status vocabulary:

```text
PRESENT | MISSING | UNKNOWN | CONFLICT | NOT_APPLICABLE
```

`NOT_APPLICABLE` requires explicit source semantics. Absence is never
`NOT_APPLICABLE` and never coerced to zero.

Required promotion-consideration obligations:

```text
FALSIFIER
PIT_AVAILABILITY
POPULATION_N
MISSINGNESS
SURVIVAL
HOLDOUT
ENTRY_EXECUTABILITY
EXIT_EXECUTABILITY
COST_EVIDENCE
RESULT
UNCERTAINTY
ROBUSTNESS
EVIDENCE_CLASS
```

Execution, evidence and decision stay three separate planes.

## 5. Decision command

Owner subset of canonical `decision_kind`:

```text
REJECT | REVISE | PAUSE | PROMOTE
```

Path:

```text
dossier snapshot → FactoryApplication → ResearchStore.append
→ read committed DECISION_EVENT → in-memory lifecycle refresh
```

Stale snapshot identity mismatch is `STALE_EVIDENCE_SNAPSHOT` with
zero writes. Same logical decision retries via existing
`transaction_id` replay. Live writer lease is `WRITER_BUSY`.
Unverified append is `DECISION_WRITE_UNVERIFIED` (no auto-retry).

`PROMOTE` fails closed when a required obligation is `MISSING`,
`UNKNOWN` or `CONFLICT`. It does not create StrategyVersion, start
PAPER/SHADOW/LIVE, call providers, deploy, or touch a wallet.

New owner-authored human fields on this command (`rationale`,
`next_condition`) are Russian-first. Machine keys stay English.

## 6. Read vs write availability

Git may describe the capability while this machine cannot write.
That is a separate fact:

```text
READ = AVAILABLE
WRITE = UNAVAILABLE
```

GET remains usable. GET must not mkdir, take a writer lease, append,
rebuild a writable projection, or mutate Git/SQLite.

## 7. Language

Owner-facing Workbench copy for this surface is Russian.
Canonical identifiers, enums, JSON/YAML keys, error codes, Catalog
IDs and semantic route IDs stay English.

Legacy ExperimentSpec / trial / evidence prose is never rewritten
for localization. Original source text remains visible. No runtime
LLM translation. No locale switcher. Presentation translation owns
zero scientific truth.

Bounded UI acceptance: `OWNER_LANGUAGE_RU_PASS`.

## 8. Rollback

Code/config/UI: ordinary Git revert. Do not delete a real
`DECISION_EVENT`. Use superseding/corrective event semantics.
