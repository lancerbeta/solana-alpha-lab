# Холодное чтение сохранённого owner-final

Кандидат устраняет ложную блокировку уже завершённого Forge-run. Новый запуск,
новый результат и новая итоговая запись для этого не нужны.

PR #424 уже создал настоящий owner-final
`11976dcb7fe1a86234492e6ad1628f3f6e6dcddd3a083b5ee35cb67534442893`
для `FORGE-RUN-174FEA4EFD507581`; обе операции получили COMPLETED.
Холодное чтение ошибочно сравнивало версию текущего агрегатора с версиями
его научных стадий. После разделения этих двух смыслов admission дополнительно
требовал доказать совместимость нового исполнения при чтении готовой истории.

Теперь различие версий допустимо только при совпадении представления, сессии,
научного слота и сохранённой ссылки на стадию. Формат всех хешей проверяется,
противоречия между источниками остаются конфликтами. Отказ текущей неявной
execution compatibility допускает только историческое чтение точной завершённой
цепочки с единым frozen source capability и UNKNOWN, без известной source model
или execution binding. Доказательство берётся из discovery до слияния с историей;
сохранённая копия не подтверждает сама себя. Ошибка чтения источника, конфликт
любой сохранённой стадии, известные model/binding требования, явный запрос другого
контекста исполнения, незавершённая работа и другие admission STOP остаются
заблокированы. Проверка происхождения должна независимо принять источники.

Реальный кандидат прочитал тот же итог и повторил обращение без записи:
SEARCH_EXHAUSTED_CURRENT_EVIDENCE, READBACK, HISTORICAL_READBACK_UNKNOWN.
Все 536 существующих записей совпали целиком по хешам. IDs, receipt, история,
результаты, drafts, assessments, reservations и учёт просмотров сохранены.
Новых научных запусков, публикаций, изменений напоминаний и зависимостей нет.

Native command owner кандидата проверен в двух новых процессах с действующими
обычными настройками, без переопределения пути к данным. Штатная рабочая копия
пока остаётся на принятом main; её полный CLI проверяется после guarded merge. Это ограничение
доказательства, не разрешение на публикацию или новый trial.

## Доказательства

`validation.json` — native-вертикаль, прежние G11-контроли, отрицательные проверки
и история исправлений проверочной обвязки. `cold-readback-proof.json` — точный
реальный receipt, равенство всех full-record hashes и нулевые записи. Синтетика
использует только подмену входной capability epoch, а store, writer, lookup,
холодные production evaluations и отдельный native subprocess остаются настоящими.

UNKNOWN не превращается в VERIFIED, научный отрицательный вывод или разрешение
на новые действия. Отдельная старая история с identity conflict не изменяется.
Ни CI, ни этот документ не дают merge authority.

## После принятого merge

Обновить только чистую обычную рабочую копию до exact merge commit. Сначала
снять полные metadata hashes существующего store (ResearchStore требует
абсолютный путь: `Path('local/factory_v1/data_plane').resolve()`).
Ожидаемый run, source IDs и hashes закреплены в текущем task contract.

```powershell
$env:PYTHONUTF8='1'
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write --owner-focus OPPORTUNITY_EPISODES:AUTO
```

Сначала сверить первый ответ: READBACK, точный run и persisted_receipt SHA выше,
все writes равны нулю. При несовпадении остановиться. Только затем повтор:

```powershell
uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --persist --owner-focus OPPORTUNITY_EPISODES:AUTO
uv run --locked --managed-python python -B scripts/hypothesis_forge.py universe-policy-status
```

Оба обращения должны вернуть READBACK, тот же persisted_receipt SHA и нулевые
research_store/forge_run/session writes. Обе исходные операции должны остаться
COMPLETED, blocking_operations — пустым, pending_operation — false. Сверить все
существующие записи целиком по хешам и учёт просмотров; новая запись не нужна.
При несовпадении остановиться: не использовать owner-stop, не редактировать
историю и не запускать науку для восстановления readback.
