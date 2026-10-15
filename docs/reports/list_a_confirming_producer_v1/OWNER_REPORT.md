# PR #406 — targeted semantic/integration repair

F01 и F02 исправлены на native synthetic product path. Implementation завершён;
свежие независимые review, exact-head CI и merge-readiness ещё предстоят.
Исторический green/ready head72151 не переносится на этот кандидат. Merge не разрешён.

| Finding | До | После | Independent evidence |
|---|---|---|---|
| F01 multi-schedule | 32 original daily schedules/256 admissions: `NATIVE_ADMISSION_SOURCE_CLOCK_CONFLICT` | Input1.1 сохраняет original schedule/activation/frame; native prepare→authorize→classify→submit→result→cold dossier PASS | `semantic-integration.json#F01`: ownership/population oracle; D128/128, mints127/128, по32 блока86400/172800; contrast0.125; B4096; cold `RESULT=PRESENT`, zero values/evaluator/writes |
| F02 maturity | Поздний отказ после одной reservation/charge и44 target decodes | Пять native entry points: `BOUND_CONTRACT_NOT_READY / TARGET_NOT_MATURE_AT_CUTOFF` до values/reservation | `semantic-integration.json#F02`:0values/evaluator/reservations/charges/writes; grid+grace boundary; зрелый `MISSING_TYPED` сохраняет D128/128 |
| Legacy/science | Single-schedule input1.0, замороженный core, семь historical charges | Canonical1.0/typed result guard6 сохранены; input1.1 проверяет original owners и exact5+N files; core/seeds4096/30-30/95-5/precedence неизменны |67/68 initial checks (единственный F01 result-schema error сохранён), затем7result/maturity и3compat PASS; cold replay; native source-role laundering refusal0values/charges/writes |

F01 отрицательные проверки: foreign schedule, incompatible family, conflicting
duplicate, два owner одного UTC cohort, foreign activation и exploratory role.
Новая упаковка того же acquisition возвращает `ALREADY_RESERVED`, charge1 и
исходный trial; дополнительных values/reservation нет. Одна family использует
один frozen template кроме activation/SHA. Partial first-day intake допускается;
fragmented same-day cohorts запрещены. Virtual aggregate schedule не создаётся.

Независимый review7e16 дал code/goal/UX `NOT_READY` и architecture `PASS`.
Закрыты точечные P2: relocated sample отказывает по общему input/cold layout
до values/reservation; CLI сохраняет UNKNOWN расхода и показывает исходные
scientific limits. Hash owner direction связан с текущими LF bytes; raw CRLF
сохранён отдельно. Два metadata regression PASS; fresh review и cold limits
regression ещё требуются. Первые verdicts сохранены, не переименованы в PASS.

Сохранены все попытки: F02 late-refusal TEST charge1, F01 result-schema failure
charge1, F01 completed engineering TEST charge1. Это отдельные disposable TEST
stores; семь прежних scientific charges/results/attempts не перезапускались.
Ошибки счётчика event carriers, изоляции fixture и Windows parent-PID witness
сохранены с отдельными corrections. Hot/cold process-chain correction — только
read-only проверка без новой scientific attempt. Unit temporary stores учтены
отдельно как обычные tests с автоматической очисткой.

В эксплуатации незрелый frozen cutoff теперь требует ожидания и отдельного
exact rebind по штатной authority; он сам не двигается. Зрелый missing outcome
доходит до coverage evaluator. Совместимые daily children можно подтвердить
одним binding без переписывания исходных identities.

REAL untouched-source availability/integration остаётся `UNKNOWN`: ни REAL
grant/values, ни provider probe не выполнялись. Текущие exploratory captures
не становятся untouched от переупаковки. Synthetic result не доказывает alpha,
causality, empirical bootstrap coverage, net execution или StrategyVersion.
Blind Actor/model diversity/earlyP0 decoder count/clean-host bootstrap и полные
shared infrastructure totals сохраняют прежние UNKNOWN.

Footprint checkpoint d7db:203.716MiB owned;249.702MiB с консервативным reserve всех
общих Git objects, hard cap1024MiB.30owned containers остановлены, owned`.venv`
отсутствует; прежний пустой review-env archive сохранён. Ничего не удалялось.
Docker volume allocation взята из неизменённого snapshot; shared VHDX/logs/runtime
cache physical totals отдельно UNKNOWN. Финальный delivery readback измерит рост.

Основной evidence: `docs/evidence/list_a_confirming_producer_v1/semantic-integration.json`.
Воспроизведение: `REPRODUCE.md`. Новых зависимостей/сервисов/сред нет.
Осталась обычная Git delivery до fresh exact-head CI/native readiness; затем одна
новая exact owner phrase. NOW product repair: NONE, если fresh review не найдёт дефект.
