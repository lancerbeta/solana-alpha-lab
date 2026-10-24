# Research Shelf V1 — checkpoint первого этапа

**Результат:** реализован и независимо проверен локальный контур хранения полки.
Полный `RESEARCH_SHELF_V1` остаётся `IN_PROGRESS`. В соответствии с правилом
владельца следующий этап начинается после его OK.

Ветка кода: `codex/research-shelf-v1`. Проверенный код:
`49038879eccc2443621f68cf9dfe933fff1a2f48`, исходный main:
`ab13b7efa7efaf9762b6d12eca52e2348d1fe759`.
Финальный commit checkpoint меняет только task/evidence; продуктовые файлы
остаются байт-в-байт на проверенном code head. Remote code/data не публиковались.

| Часть | Проверенный результат |
|---|---|
| Запись | Строгая V1 schema, canonical JSON, hash ревизии, неизменная identity, отдельный mutation_id |
| История | Append-only revisions; fork остаётся конфликтом; явное согласование сохраняет обе истории |
| Git transport | Отдельный bare cache, private index, non-force push, atomic batch и проверки item heads/origin при retry |
| Восстановление | Потерянный ответ после push распознаётся readback; exact retry старой ревизии работает после её потомков |
| Обзор | UTC attention, NEEDS_TRIAGE, UNKNOWN, точный commit/hash, полнота и свежесть снимка; totals и omitted_count |
| CLI | capture/prepare/validate/apply/refresh/review/show/revise/reconcile; просмотр конкурирующих и исторических ревизий |
| Изоляция | Только локальные remotes; UNC/mapped drives и indirect paths отклоняются до обращения к потомкам |

Проверки: **25/25 targeted tests PASS**, Factory static PASS, secret rejection
и secret scan PASS, task schema и pre-commit checks PASS. Четыре независимых
изолированных review — `CODE_REVIEWER`, `GOAL_DOD_CRITIC`,
`ARCHITECTURE_CRITIC`, `OWNER_UX_CRITIC` — дали PASS на этот code head.
Модельное разнообразие не доказано; отдельный контекст проверяющих не выдаётся
за другую модель.

Независимые оракулы: заданные PRD SHA-256, ручная таблица UTC-границ, два
реальных writer'а на disposable Git remote и холодный reader. Дополнительный
durable тест вносит fork в настоящий Git и проверяет явный reconcile:
четыре сохранённые ревизии, два родителя у согласованной версии. Проверенные
найденные ошибки и точный inventory записаны в `storage-checkpoint.json`.

Воспроизведение с существующим locked runtime, `PYTHONPATH=src`:

```text
uv run --locked --managed-python python -B -m unittest discover -s tests -p test_research_shelf_v1.py -v
```

На этой Windows-машине обычная изоляция процесса запрещает запуск MSYS Git
transport. Synthetic Git vertical проверен разрешённым процессом вне этого
ограничения. Все его remotes — временные локальные директории; credentials,
внешний transport, native ResearchStore и science не используются.

Пример безопасного read-only CLI для fixture:

```text
uv run --locked --managed-python python -B scripts/research_shelf.py validate --input tests/fixtures/research_shelf_v1/genesis.json
```

При работе с локальным cache чтение `review/show` требует точный `--commit`.
Оно не делает скрытый fetch. `refresh` — отдельная операция. Даже после refresh
повторный pinned read честно показывает `UNVERIFIED_PINNED`, если свежесть не
была проверена этой операцией. `PREPARED_LOCAL_ONLY` не означает сохранение в Git;
`PENDING_PUBLICATION` требует повторить прежние bytes, не создавать новую мысль
или повторять исследование.

**Границы результата:** native event adapters, MET/NOT_MET evaluation, hard
native expiry, Forge/direct entry hook, semantic route, inverse/provenance
resolver и путь StrategyVersion ещё не подключены. Frozen scientific identity,
cloud explicit-ref reader, actual GitHub no-PR publication и приватность
произвольного текста ещё не доказаны. Сканер ловит заданные классы секретов и
физических путей; он не понимает конфиденциальность исследовательской прозы.

Настоящая `research-log` в SMIAL не создана, текущие seeds не опубликованы,
workstation RFV plans не сверялись и отложенные проверки не запускались.
Данные synthetic remotes не являются operational data commit.

**Следующий шаг:** после OK владельца продолжить этап 2 в этой же задаче:
entry summary/refresh, два узких source adapter, exact links/inverse resolver,
поддерживаемый science→strategy trace, frozen-identity regression и semantic
propagation. Сохранить один eventual engineering PR. Затем общий CI/merge gate;
реальный metadata bootstrap — только после принятия версии и exact scope.
NEXT_MODEL_EFFORT=SOL_XHIGH.

Rollback локального этапа — обычный revert продуктовых изменений. Native
artifacts и публичная data-ветка этим этапом не изменялись. Создавать новую БД,
scheduler, общий package или переносить scientific ownership не требуется.

FACTORY_FIT_REVIEW=FULL_REVIEW / PASS_FOR_STAGE_ONLY: Git решает именованную
metadata-задачу, сохраняет историю и не заменяет научные owners; native admission
остаётся неоценённым. PRODUCT_HORIZON_NOW — закончить этот capability; WATCH —
измеренный рост active set или задержка чтения. CAPABILITY_RADAR_NOW=NONE.
