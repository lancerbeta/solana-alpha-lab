# LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1 — owner readout

## Итог

Локальная materialization зрелых cohort source-бандлов переведена на
двухуровневый путь: после cold bootstrap точная публикация переиспользует
проверенный non-scientific latest-cache и bounded process-local target cache.
Для современных append-only unit-ов повторное состояние доказывается через
writer-issued cumulative operation proof за O(1); канонический
SNAPSHOT_PLUS_DELTA replay сохранён как cold, cache-miss, corruption,
staleness и audit/recovery fallback.

Работа ограничена веткой
`local-cohort-incremental-materialization-v1` в worktree
`C:\Users\lance\Projects\solana-alpha-lab-wt-pub-wallclock`, базовый SHA
`e79adc0b7b8d765ef14e1560ba81f08efcdcf61a`. Live Factory, VPS, provider,
timer, C1, seal/verify/import и Forge не запускались.

## Что изменено

1. Persistent cache оставлен latest-only, rebuildable и явно
   `scientific_truth=false`; его metadata привязана к dataset id, seq,
   snapshot fingerprint, row count, canonical unit binding и binding
   заявленных canonical-файлов.
2. Exact target cache ограничен восемью состояниями на процесс. Повторная
   materialization той же identity не реконструирует SQLite и не перечитывает
   member rows.
3. Равное fingerprint/row-count состояние в hot path переиспользуется только
   по bounded cumulative proof нового canonical writer contract: endpoint
   sequence/count metadata и append-only rolling binding. Для строгого аудита
   отдельный путь читает canonical delta marker и meta-row, проверяет lineage,
   hashes, sequence и operation counts; при missing/inconsistent proof или
   remove/readd выполняется полный canonical replay.
4. Более новый tail не может удовлетворить более ранний PIT target; старые,
   изменённые и non-monotonic состояния идут через точный replay.
5. Обязательные canonical paths confined внутри data root; symlink/path escape,
   cache mismatch и повреждённые delta закрываются typed fail-closed ошибкой.
6. Stage counters показывают checkpoint hit/miss, reconstruction, full-column
   scan, opened member files, observation decoding, target-cache hits,
   writer binding extensions и bounded no-op proof/fallback activity.

## Проверка

Подтверждённые offline deterministic результаты:

| Проверка | Результат |
|---|---|
| `tests.test_local_cohort_incremental_materialization_v1` | 10/10 PASS |
| `tests.test_live_cohort_memory_bounded_publication_v1` | 9/9 PASS; stress RSS 161,906,688 bytes, 150,000 observations |
| `tests.test_live_cohort_discovery_release_series` | 6/6 PASS |
| `tests.test_live_cohort_to_forge_operational_closure_v1` | 22/22 PASS |
| `tests.test_factory_routine_publication_wallclock_v1` | 13/13 PASS |
| `scripts/bench_local_materialization_v1.py` | all acceptance checks PASS |
| `scripts/validate_factory_static.py` | PASS |
| `compileall` | PASS |

Бенчмарк отдельно подтвердил: warm unchanged depth 10 не реконструирует
цепочку; one-step depth 11 расширяет только нужное новое состояние;
writer-side depth 100 даёт один full binding refresh и 100 O(1) extensions;
deep no-op range даёт один exact reconstruction, 99 bounded proof hits,
нулевые fallback/marker scans и 99 target-cache hits; warm depth 100 остаётся
в том же member-work counter class, что и warm depth 10. Observation panel
остаётся линейным по рассматриваемым historical panels — это измеренный
residual и отдельный будущий atom, а не скрытый PASS этой оптимизации.

Отдельный regression проверяет, что повреждённый `meta_json` zero-op marker
не принимается строгим audit path как no-op.

## Инварианты и non-claims

Научные canonical artifacts и исторический RDP не переписываются. Cache не
является scientific truth и не меняет PIT, membership, missingness, survival,
typed values, lineage, fingerprint или publication identity. Offline fixtures
не доказывают live host SLO, provider availability, C1 readiness, alpha,
экономический результат, seal/verify/import или Forge control readiness.

Rollback — удалить или отключить rebuildable operational cache; canonical
replay остаётся источником истины. Удаление научных данных и cleanup чужого
scratch в scope не входят.

## Delivery boundary

Текущий exact implementation HEAD: `86e753f5` на ветке
`local-cohort-incremental-materialization-v1`; остаётся одна bounded PR с
exact-head CI и merge-readiness. Merge не выполняется: для него нужна
отдельная точная owner-фраза после зелёного PR.
