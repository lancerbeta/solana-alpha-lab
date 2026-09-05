# OWNER_LIFECYCLE_PROJECTION_SPINE_V1 — owner readout

Это derived index, не Owner Workbench, не миграция lifecycle, не alpha и не экономика.

## VERDICT

```text
OWNER_LIFECYCLE_PROJECTION_SPINE_V1_PASS
```

Entry: `START_AS_WRITTEN`. Route: `DIRECT_CURSOR_DELIVERY`.
Factory Fit: `OWNER_LIFECYCLE_PROJECTION_SPINE_FACTORY_FIT_PASS`.

## EXACT BASE / HEAD / PR

```text
BASE = 5e9779e448543752ed19d5209b3f7184ae5d2196
HEAD = (bind after evidence commit)
PR   = (opened after push)
```

## ЧТО ТЕПЕРЬ УМЕЕТ FACTORY

Свежий consumer может спросить, какие lifecycle-объекты SMIAL знает, откуда каждый факт, и какие явные связи их соединяют — без ручной археологии Git/SQLite и без второго truth owner.

Ответ — `LifecycleProjectionV1`: derived envelope. Incomplete graph с `GAP`/`UNKNOWN` — успех, когда так говорит текущая истина.

## SOURCE OWNERS

Подключены read-only адаптеры:

- Git ExperimentSpec (`configs/experiment_specs/*.yaml`)
- Git StrategyVersion (`configs/strategies/*.yaml`)
- Git negative/decision registry
- empty legacy envelopes (`hypotheses` / `research_cycles` / `strategies` / `bot_instances`) as `EMPTY`, not complete truth
- OperationalStore sqlite `mode=ro` when the file already exists, else `NOT_PRESENT`
- PaperPlaneStore sqlite `mode=ro` when the file already exists, else `NOT_PRESENT`
- ResearchStore only when an existing store is injected; opening from a data-root path is `UNAVAILABLE` (`RESEARCH_STORE_OPEN_WOULD_WRITE`)

`authority_granted = false`. Projection owns no truth.

## ACCEPTANCE CHAINS

1. `NEGATIVE-T30-CURRENT-DATA-ROUTE-001` — entity from Git registry. Hypothesis link not invented from `summary`.
2. `EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001` → `HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1` explicit field, `TARGET_GAP` (hypothesis not synthesized).
3. `STRAT-V-EARLY-LIQ-FLOOR@V1` provenance (`hypothesis_ids`, `source_decision_asset_id`); empty `registries/strategies.yaml` stays empty.
4. Disposable PaperPlane: bot → StrategyVersion via `EXPLICIT_CONTRACT_KEY` invert of `start_bot` `{strategy_id}-{strategy_version}`; position → bot via FK. No persistent `local/` write.
5. Disposable ResearchStore: `HYPOTHESIS_VERSION` → `TRIAL` → `DECISION_EVENT` from envelope fields.

## ЧТО СТАЛО КАНОНИЧЕСКИМ В GIT

- contract: `docs/contracts/owner_lifecycle_projection_spine_v1.md`
- machine: `configs/owner_lifecycle_projection_v1.yaml`
- schema: `catalog/schemas/owner_lifecycle_projection_v1.schema.json`
- module: `src/solana_alpha_lab/factory/lifecycle_projection.py`
- API: `FactoryApplication.lifecycle_projection()` (independent of selected ExperimentSpec; does not construct runtime stores)
- inspection: `scripts/show_owner_lifecycle_projection.py`
- Catalog binding: `ACTIVE-OWNER-LIFECYCLE-PROJECTION`
- semantic route: `SEM-OWNER-LIFECYCLE`

## КАК БУДУЩИЙ АГЕНТ ЭТО НАХОДИТ

```text
AGENTS
→ catalog_cli.py search-routes / resolve-route
→ SEM-OWNER-LIFECYCLE
→ CONFIG-OWNER-LIFECYCLE-PROJECTION-001
→ docs/contracts/owner_lifecycle_projection_spine_v1.md
→ source owners (Git / ResearchStore / OperationalStore / PaperPlaneStore)
```

Also: generated `docs/FACTORY_SEMANTIC_MAP.md`.

## КАК СОБЛЮДЕНО

```text
runtime != Git
projection != truth owner
UNKNOWN != zero
EMPTY != NOT_PRESENT != FAILURE
```

Same `entity_id` on different `truth_plane` stays separate + `IDENTITY_CONFLICT`. Conflicting same-plane state: `native_state=null`, `display_state=CONFLICT`, no timestamp winner.

## TEST / REVIEW EVIDENCE

Focused unittest green: lifecycle Cases A–E, schema, gaps, FactoryApplication lazy stores, semantic EN/RU + anti-hijack, Catalog bindings, Visual OS regression. Isolated critics PASS (code / goal / architecture; packet `c21454c3…`). Factory Fit `FULL_REVIEW` PASS. Exact-head CI remains the live machine gate.

## ЧТО НЕ МЕНЯЛОСЬ

`workbench.py`, `research_store.py`, `paper_plane.py`, `operational_store.py`, `experiment_spec.py`, `strategy_runtime.py`, root `AGENTS.md`, `README.md`. Empty legacy registries not backfilled. No provider/VPS/wallet/deploy.

## RESIDUAL GAPS

- Default CLI/API does not inject ResearchStore; research lineage is `NOT_PRESENT` until a caller passes an existing store.
- `registries/global_trial_ledger.yaml` is not adapted (not a V1 source).
- `RESOLVED` requires unambiguous endpoint identity in the current projection; a shared `entity_id` on multiple `truth_plane`s stays as separate entities plus `IDENTITY_CONFLICT` and `relation.resolution = CONFLICT`.
- Move 1 consumption is a documented obligation, not a runtime lock.
- Gold question «где каноническая карта lifecycle?» still routes here; the route purpose says derived index, not source truth.

## ROLLBACK

Ordinary Git revert of this Move. No runtime or data migration. Projection is recreatable from owners.

## NEXT RECOMMENDED MOVE

```text
RESEARCH_LIFECYCLE_WORKBENCH_V1
```

Do not auto-start. Project Chat reviews merged contract, discovered gaps, and current main first.

## MERGE READINESS

Stop at `OWNER_ATTENTION_GATE_V2`. Do not merge until exact-head CI is green and `--merge-readiness` reports `ready_for_owner_phrase: true` for this unchanged PR/head. Owner supplies the exact phrase; the elected agent merges.

## Factory Fit answers

```text
Does this create a second truth owner?       NO
Does ordinary runtime create Git writes?     NO
Does it reuse current source contracts?       YES
Can Move 1 consume it without archaeology?   YES
Are missing relations explicit?              YES
Did we migrate empty legacy registries?       NO
Did we add speculative infrastructure?        NO
```
