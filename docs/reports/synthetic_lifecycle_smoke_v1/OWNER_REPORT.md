# SMIAL synthetic lifecycle smoke — 14 октября 2026

**Проверенная часть кампании завершена. Сквозной Forge → Science → Trading остаётся BLOCKED.**
Статус кампании: `PARTIAL_ENVIRONMENT_OR_AUTHORITY`; все S00–S14 учтены,
27 неуспешных test records и неуспешные attempts сохранены. Это результат аудита,
а не торговая readiness. Продукт проверялся на неизменном `94b391d658b52035ae88e2da05f1ea25ff17b0f8`.

| Ось | Подтверждённый результат |
|---|---|
| Discovery | 3 positive + 1 null blind trials — `BLOCKED_ENVIRONMENT`: нет свежего актора с нужной OS confinement. Два явно authored положительных контроля прошли native MAIN; это не самостоятельное обнаружение. |
| Continuity | Native authored ingress → MAIN → persisted draft → freeze → настоящий packet-only Critic → finalize → persisted OWNER_FINAL → новый процесс. Далее оба `KILL_UNBOUND_EVIDENCE`; original candidates до Science/Trading не дошли. |
| Operability | Отдельный `BR-01` segment: две разные scientific recipes, обычные PAPER вход/выход и reconciliation. Native successor/old exits, UNKNOWN/no-resend, costs, recovery и human CLI проверены. |
| Scientific boundary | Accepted независимое подтверждение этих двух raw recipes не установлено. Технический STOP не является отрицательным научным результатом. NULL/DECOY validation — только независимый lab oracle. |
| Safety | Изолированные product containers: сеть отключена, source readonly, UID 1000, 2 CPU/2 GiB/128 PIDs. Production data, providers, signer, деньги и deployment не использованы. Все созданные контейнеры остановлены. |

**Для созданной среды учтено примерно 0,58 GiB выделенного места.** В этот объём входят
две отдельные копии репозитория, retained evidence, Docker product volume, небольшие
writable layers/logs и дополнительная `.venv` около 0,16 GiB. Existing runtime image
переиспользован; новых images — 0. Scratch volume после штатного test teardown пуст.
Среда и evidence оставлены; решение об удалении за владельцем. Точные bytes и пределы
учёта — в [campaign.json](../../evidence/synthetic_lifecycle_smoke_v1/campaign.json).
Shared uv cache, уже существующий image и общий Docker VHDX не прибавлены к новым
данным кампании; прирост общего uv cache отдельно не восстановлен (`UNKNOWN`).
Hardlinks могут завышать оценку дополнительной физической аллокации кампании.

**Один NOW:** связать accepted independent confirmation contract для сохранённых raw
recipes: точные dataset/availability/required-outcome bindings, независимое chronological
продолжение, frozen критерии PASS/FAIL/INCONCLUSIVE и фактический consumer результата.
Приёмка ремонта — один неизменённый recipe проходит classify → registered runner →
научный terminal на новом допустимом evidence; replay старого look и presence-only
receipt этого не заменяют. Это отдельная owner-owned научная постановка, не выполненный
ремонт и не разрешение менять population/estimand. Для неё `NEXT_MODEL_EFFORT=SOL_XHIGH`.

164 уникальные existing tests имеют PASS в наблюдённых попытках. Число включает
native integration и contract checks; оно не является процентом готовности или
доказательством полного пути. Повторные PASS не уничтожают ранние FAIL/ERROR.

## Что именно прошло

Мир заморожен до первого MAIN: 320 нейтральных identities, 10 когорт по 32,
128 discovery / 96 validation / 96 PAPER-forward. Seed, пороги и цена ошибки после
получения результатов не менялись. Внутри когорт факторы сбалансированы; joint
interaction проверена четырьмя клетками, а не произведением marginal counts.

| Authored control | Product matched / eligible | Средний target | Контраст к SAME_DECISION_ELIGIBLE |
|---|---:|---:|---:|
| SIMPLE | 64 / 128 | 13,5516% | +6,0320 п.п. |
| COMPOUND | 32 / 128 | 19,4875% | +11,9680 п.п. |

Независимый observer не импортирует product calculator: Decimal arithmetic совпала
по pooled mean/median, baseline, четырём cohort means, type-7 quantiles и fractional
ES10. Численная подмена обнаруживается. Product summary не выдаёт individual selected
IDs: точная row-level membership остаётся `UNVERIFIED`; скрытая сетка проверяет
сам мир и ожидаемую выборку, а не автоматически доказанный выбор продукта.

Оба Critic действительно работали в новых контекстах и получили только свой frozen
packet, public method/schema. Они независимо отказали в scientific PASS: в packet
нет связанного confirmation consumer, outcomes/availability closure и результатов
названных NULL/DECOY controls. Их machine decisions сохранены в Git. После native
finalize оба новых процесса прочитали `OWNER_FINAL / COMPLETED / READ_SAVED_RESULT`;
readback не записал состояние, MAIN не повторялся. `KILL_UNBOUND_EVIDENCE` — technical
stop, без family close или научного отрицательного вывода.

Registered fixed-time proxy воспроизвёл тот же discovery result, а точный повтор
request не загрузил значения и не изменил committed inventory. Это проверка replay,
не независимый OOS. В lab validation positive мир проходит фиксированный порог,
NULL и DECOY его не проходят; эти разделы не были выданы Actor или приняты как
native scientific confirmation.

## Где разорван путь и что значит BR-01

Рабочий runtime consumer требует `episode_query` 1.2 и `OPPORTUNITY_EPISODES`.
Точный raw recipe получает `BOUND_EPISODE_RECIPE_REQUIRED`; episode schema с raw
X/Y-point получает `POINT_NOT_IN_ALLOWLIST`; explicit research cohort selection —
`RUNTIME_COHORT_SELECTION_UNSUPPORTED`; чужая population — `RECIPE_POPULATION_MISMATCH`.
Правильные guards прошли. Подмена X/Y на E-points меняет anchor/population/clock и
не доказывает сохранение научного вопроса.

Поэтому один объявленный cut `BR-01` заменил отсутствующую scientific-confirmation/
raw-to-episode цепочку существующими явно synthetic DIRECT science fixtures.
Они породили две разные episode recipes (`MIXED_LIST_NUMERIC` и `LIST_CONTRAST`),
сохранили spec/manifest/execution bindings и прошли обычный coordinator/CLI.
Исходные SIMPLE/COMPOUND кандидаты ими **не потреблялись**.

Каждый PAPER segment завершил OPEN → RECONCILED с двумя попытками; независимый
денежный oracle по контрактному ROUND_HALF_UP на каждой ноге дал ровно $7,37.
Внешний synthetic price stimulus был опубликован через source, fills не подставлялись.
Снимки двух stores сохранены в разных append-only directories. Это модельный
результат, не NetReturn, прибыль рынка или FCF. Два успешных segments с BR-01
assembler оставляет `SEGMENT_ONLY_LONG_PATH_BLOCKED`.

Selected recovery подтвердил original switch chain и successor с сохранением A exit,
backup/cut/ACK/resume, более строгие envelope/runtime policy и known cost floor
$0,25 при UNKNOWN total. Post-claim плохой ответ оставил B pending под прежним ключом;
healthy A exit завершился, resends=0. Неизвестное не стало flat, нулевыми costs или
свободным headroom. Есть реальный child reply-loss/moved-root restart Forge и
WAL-aware/fresh-process readback. Browser UI и автоматический возврат trading feedback
в новую Forge mission не проверены.

Двухнедельный source stream на Linux volume: 14 identities, 28 уникальных attempts,
14 RECONCILED positions, literal accounting oracle $36,91. Existing test моделирует
только физическую disk capacity; admission guard и продуктовые переходы остаются
native. Это bounded synthetic throughput, без uptime/live или неограниченного SLA.

## Coverage и ошибки аудита

Полная матрица с `reached / oracle_exercised / consumer_accepted / fidelity` и exact
test IDs находится в [coverage.json](../../evidence/synthetic_lifecycle_smoke_v1/coverage.json).
S01/S02 — blind actor blocker; S03 — native NULL/memory неизвестно; S04 — native
confirmation blocked с lab counterexample; S06 — новая maturity до native confirmation
не выполнена; S09 — original candidate handoff blocked, right segment PASS;
S14 — свежий readback/human CLI PASS, feedback consumer UNKNOWN.
Остальные PASS относятся строго к указанной проверенной границе.

Ранние audit-only отказы не спрятаны: stale base в borrowed canary, неверный CLI flag,
несогласованный operation cap, пустой subprocess timeout, слишком маленький tmpfs,
ошибка денежного oracle и первоначальный C16 FAIL на Windows bind storage. Они не
превращены в product defects. Linux C16 replay прошёл; у раннего Windows assertion
не сохранился полный traceback, поэтому причина того FAIL остаётся `UNKNOWN`.
Первый двухнедельный запуск прерван по бюджету; повтор на достаточном Linux volume
прошёл за 70,50 с. До исправления watchdog он превысил бюджет одного scenario;
суммарный runtime остался внутри 120 минут. В раннем Forge attempt ошибка `setUpClass`
исказила последнюю строку suite summary; исходный append-only test terminal сохранил PASS.
Assembler явно отмечает это расхождение; audit callback исправлен, старые bytes сохранены.

Code review исправил unique snapshot retention, independent numeric observer,
180/300-second deadlines, aggregate 120-minute/2-GiB evidence checks, typed failure
terminals, failed subtest identities и SEGMENT aggregation canary. Финальные canaries
прошли; product source не менялся. Один Critic ошибочно создал source `.venv` при
schema validation. Её размер включён; product containers её не использовали, последующие
проверки используют существующий runtime с `--no-sync`. Новых dependency choices нет.

Root findings и точные closure checks:
[findings.jsonl](../../evidence/synthetic_lifecycle_smoke_v1/findings.jsonl).
Replay и retention: [REPLAY.md](REPLAY.md). Все raw stores/logs лежат вне Git;
[retention-pins.json](../../evidence/synthetic_lifecycle_smoke_v1/retention-pins.json)
связывает ключевые фактические receipts и snapshot inventories. Rollback kit — обычный
Git revert новых audit files; cleanup stores/volumes/контейнеров в эту задачу не входит.
