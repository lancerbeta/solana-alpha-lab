# SMIAL Science lifecycle smoke: частичный checkpoint

На продукте `fbac5449f6dd22a7bc066114109be8bbed830447`, включающем #403,
доказан настоящий численный путь Spec 1.4 до сохранённого результата, passport
и атомарных ResearchStore records. Эти records потребляет обычный dossier;
он сохраняет PAUSE и отказывает в PROMOTE. В проверенном accepted List A маршруте
нет confirming producer с pre-values reservation. **Полный DoD кампании не закрыт:
SC06 не выполнен из-за замороженного бюджета хранения.** Это
`PARTIAL_ENVIRONMENT`, без научного PASS.

| Ветка | Результат и граница | Основное evidence |
|---|---|---|
| A — числа, повтор, восстановление | PASS engineering. LIST: M=10/C=10, mean M=0.10, contrast=0.11. MIXED: M=10/C=D=20, contrast=0.055. Обе дают COMPLETE / INCONCLUSIVE | [numerical.json](../../evidence/science_lifecycle_smoke_v1/numerical.json), actual artifacts/passports/records; independent Fraction oracle |
| B — подтверждение | BLOCKED_PRODUCT_CONTRACT. Есть принятый List A метод; нет accepted confirming producer с reservation до значений и substantive evidence | [chronology.json](../../evidence/science_lifecycle_smoke_v1/chronology.json): registry, actual dispatch, contract, consumer и source hashes |
| C — ordinary consumer | PASS engineering. Actual A completion DIRECT; planes COMPLETED / BLOCKED / PAUSE. Cold PAUSE — REPLAY_IDENTICAL, без новых business records | [readback.json](../../evidence/science_lifecycle_smoke_v1/readback.json): реальный dossier и native decision guards |

`FULL_PRODUCT_PATH` относится только к явно названным переходам
«Spec1.4 → committed numerical artifact» и «actual RUN → dossier → PAUSE».
Upstream Actor/Critic scripted; регистрация definition slot — явный fixture
(`SEGMENT_PRODUCT_PATH`). Эти части не складываются в Forge→OOS→Strategy.
StrategyVersion, activation и PAPER не запускались.

Числа проверены отдельно от продуктовой реализации: exact episode IDs и D/M/C,
средние/медианы, contrast, downside/type-7 quantiles/ES10, полное покрытие
cohorts/calendar и missing-stress MODEL. [Chronology geometry](../../evidence/science_lifecycle_smoke_v1/chronology-geometry.json)
отдельно пересчитывает расписание и фактическую доступность для 10 matched episodes
и 20 E1800/E14400 ячеек из сохранённых metadata, без чтения `typed_value`.
Корректный comparator важен: MIXED сравнивает M со всем D,
включая M, поэтому contrast вдвое меньше LIST. Costs не измерены, NetReturn false.
Повтор обоих corrected Specs в новом контейнере не вызвал evaluator, не
декодировал future values и не изменил committed inventory.

Guard/fault specimens сохранили expected отказы при missing/stale source,
чужом definition и отзыве текущей protection после READY. Historical completion
сохранилась. В первом process fault записан настоящий result-file до commit;
orphan не признан завершением, recovery пересчитал и сохранил один completion.
Во втором fault commit уже завершился до потери ответа; cold replay вернул его
без evaluator и дубля. Эти проверки — segments на base-v2 с тем же frozen recipe,
sources и masks, что у исправленного primary base-v3.

Во время аудита исправлены ошибки **audit kit**, без product repair: Windows
bind capture превысил 600s; Linux owned volume стал рабочим штатным storage path;
неверное имя response field; неподготовленная mutable store copy; ошибочное
ожидание foreign RUN в RELATED. Последний contract исключает conflicting RUN,
а same-hypothesis PAUSE оставляет RELATED. Затем выявлен унаследованный quote
question/estimand и лишний Catalog binding в base-v2 Spec. Они давали неверный
текст вопроса и PIT CONFLICT в dossier. Новая base-v3 зарегистрирована **до**
classification/run с корректной episode семантикой и corpus binding; старые
Spec, численные результаты и failures сохранены. Никаких refunds.

В corrected dossier PIT/population/HOLDOUT остаются UNKNOWN, квалифицирующие
result/uncertainty/robustness/cost/execution obligations — MISSING. Это ожидаемый
science refusal: технический RUN не становится квалифицированным подтверждением.
Валидные команды достигли `STALE_EVIDENCE_SNAPSHOT` и `PROMOTE_BLOCKED`; ноль
strategy/activation/PAPER writes. Для B проверены короткие альтернативы: frozen
replay, schedule compile, diagnostics и quote capture не выполняют тот же accepted
confirmation estimand. Не построены собственный confirmer, reservation ledger
или scientific carriers.

Учет: **4 MAIN, 8 evaluator invocations, 0 B attempts, 0 LLM science trials**;
старые 22 MAIN из #403 — отдельно. Восемь включают прерванные и failed recovery
вызовы. Unified [ledger](../../evidence/science_lifecycle_smoke_v1/attempts.jsonl)
сохраняет original native sequence и отдельно clocked container attempts;
environment misses до контейнера имеют timestamp UNKNOWN. Его порядок не
выдаётся за восстановленную точную causal chronology.

Footprint на checkpoint: см. [footprint.json](../../evidence/science_lifecycle_smoke_v1/footprint.json).
Это измеренные allocated file blocks host + два owned volumes + container RW,
включая elected checkout: известная сумма **около 509.3 MiB из 512 MiB**,
остаток **около 2.7 MiB** на checkpoint-замере. Собственно сохранённая test environment
без elected checkout — **440.62 MiB**. Только стандартный fresh world до
classification требует около **43 MiB**. Это оценка по выделенным file blocks,
не рост Docker VHD. Shared существующий image 533,691,498 bytes (508.97 MiB)
переиспользован, новых image/dependencies
нет. Docker VHD growth, directory metadata и физическая allocation Docker logs —
UNKNOWN без baseline/доступного readback. Все owned процессы остановлены;
автоматического удаления не было. Retained targets: runtime sibling directory,
volumes `science-lifecycle-v1-product` / `science-lifecycle-v1-output` и только
контейнеры с campaign label. Чужие ресурсы и старый #403 мир не изменены.

**Следующий шаг — закончить SC06 после отдельного budget replan до 640 MiB.**
Не менять MAIN/evaluator caps (6/12), не очищать историю: новая negative market
версия должна дать −0.09 / −0.045 при тех же prefix roles. Это пока предложение,
не authority. По проверенным A/B/C пока выявлен один product seam —
[List A confirming producer atom](REPAIR_PRD_SSD.md), с отдельными
sample/authority gates. SC06 ещё может изменить карту findings.
Guard/threshold/Spec semantics repair по имеющимся данным не нужен. Git
delivery/merge-readiness не объявляются завершёнными на частичном DoD.
