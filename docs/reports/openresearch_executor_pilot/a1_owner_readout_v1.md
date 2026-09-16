# OpenResearch Executor Pilot — Owner Readout (a1)

Task: `OPENRESEARCH_EXECUTOR_PILOT_V1` · Date: 2026-09-16 · Mode: `PILOT_REPLAY_ONLY`
Verdict: **`KEEP_EXTERNAL_EXPERIMENTAL`**

## Что проверяли

Полезен ли `alphaXiv/OpenResearch` (orx) как внешний execution-воркер Кузницы после готового `ExperimentSpec`: несколько изолированных вариантов → параллельное/независимое исполнение → полный provenance → воспроизводимый результат — при неизменных scientific semantics, authority и Git truth Кузницы. Не качество генерации гипотез, а executor-capability.

## Exact inputs / versions

| Что | Значение |
|---|---|
| OpenResearch repo | shallow clone @ `325eb509dc8e4ca7074568cf0ae1f0f98704eac0` (2026-09-15) |
| orx CLI | `0.2.3` (Windows x86_64 release zip); telemetry off |
| Canonical source | bare mirror + lab clone (без remote) @ `661229914718727e3208df2562ee8a69697e905f` |
| Dataset | immutable snapshot 9 файлов; все sha256 сверены до и после прогонов (0 drift) |
| Базовый эксперимент | `EXP-MARKET-FEATURE-PRICE-PATH-ARCHETYPE-001` (offline, budget 0, sealed A24 receipts) |
| Siblings | `EXP-MARKET-FEATURE-LIQUIDITY-ARCHETYPE-001`, `EXP-MARKET-FEATURE-CREATOR-PRESSURE-ARCHETYPE-001` |
| Method (общий) | `resolve_market_feature_snapshot` через `CAP-OFFLINE-MARKET-FEATURE-RESOLVE-001` |

## Как запускали

`orx up --no-browser --no-agent` (loopback 4791) → проект через `POST /api/projects` → `orx create-experiment` (baseline + 2 children, одинаковая форма run-command, разные sealed specs) → три независимых `orx exp run --backend local`. Каждый run: собственный каталог, распаковка immutable content-addressed tar `<hash>.tar` зафиксированного commit'а, свежий `.venv`, `run.sh` → `log` + `exit_code`.

## Результаты вариантов

| Run | Эксперимент | Status | Terminal | Совпадение с canonical |
|---|---|---|---|---|
| `eff0915c…` | Baseline price-path | COMPLETE | `FEATURE_SURFACE_COMPOSITION_PASS` | = acceptance A24 |
| `64daedfc…` | Sibling A liquidity | COMPLETE | `FEATURE_SURFACE_COMPOSITION_PASS` | ожидаемый для этой spec |
| `48c7162c…` | Sibling B creator-pressure | COMPLETE | `FEATURE_SURFACE_COMPOSITION_PASS` | ожидаемый для этой spec |

Оговорка: siblings — вариации на уровне семейства (общий метод/capability/surface/класс estimand, один snapshot-tar), а не повторение одного literal-вопроса; каждая spec несёт свой вопрос, feature-набор и sealed-входы. Конструкция зафиксирована в READY task-контракте до исполнения; для executor-pilot это более сильный тест изоляции/lineage, чем косметические клоны.

## Isolation / parallelism

- A/B/Baseline не видели transient-артефакты друг друга (разделённые run-dir + собственная распаковка repo из одного tar).
- Failure-изоляция: каждый run завершается в свой `exit_code`; падение одного не затрагивает другие.
- Lineage: run → experiment node → branch (`orx/<slug>`) → commit `6612299` → source-snapshot tar hash; run-command зафиксирован в узле; provenance-полнота — см. ограничение ниже.
- Все три запущены фактически параллельно (по 5 сек каждый).

## Clean replay

Новый чистый каталог, только saved evidence (tar + команда): статус/блокер/терминал/метрики идентичны; отличаются ровно 4 wall-clock поля (`economics.as_of`, `system_operability.observed_at`, `owner_attention.current_attention`, `system_operability.attention` — время-несущие поля/подборки). **`REPLAY_PASS`** (детерминированные выходы совпали; tolerance не изобретался — различия по конструкции время-несущие).

## Canonical integrity

- Canonical working copy: чиста, HEAD `6612299` до/после; 0 правок.
- Remote: лабораторный клон без remote; push/PR из ORX невозможны (GitHub publication off в проекте).
- Провайдер/сеть: 0 вызовов из экспериментов; сеть — только одноразовый публичный fetch OpenResearch.
- HFIC/RDP/Forge: не тронуты; научная семантика не делегирована (терминалы — replay известных результатов).

## Operator burden vs обычный агентный путь

- ✅ Снимает: ручное создание N веток/worktree на вариант; ручной запуск и слежение за прогонами (`exp run/wait/logs`); ручной сбор run-логов; immutable per-run snapshot-архив бесплатно; локальная БД истории экспериментов.
- ⚠️ Не снимает: выбор/валидацию specs (наша семантика), интерпретацию терминалов (остаётся у Кузницы/владельца), перенос результатов в canonical evidence.
- ➕ Добавляет: установка бинаря + dashboard-процесс; регистрация проекта только через UI/HTTP API (CLI не импортирует проект); своё SQLite-состояние вне Git (частичный перенос state из Git в orx-store); Windows-beta зрелость; обновления версий orx.

Честный контрфактический ответ: для 3 однотипных offline-прогонов обычный агент сделал бы то же дешевле (одна петля `uv run` × 3 + логи); выигрыш ORX появляется при большем числе вариантов/длинных прогонах/удалённом compute. Provenance-модель orx (tar-snapshot + run-log) не хуже нашей для replay, но не покрывает наш receipt-уровень (acceptance/runtime receipts, evidence-цепочки) — двойной учёт неизбежен без интеграции, которая выходит за рамки пилота.

## Существенные проблемы

1. Импорт проекта — только dashboard/HTTP API (нет CLI-команды `project import`).
2. Run-command исполняется в bash (Git-for-Windows); `uv` должен быть на PATH — ок для нас, но это Windows-beta условность.
3. orx-состояние (SQLite, local-runs) живёт вне Git — «перенос работы из Git в собственный state», что противоречит our-Git-as-working-memory по мере роста использования.
4. Логи прогонов содержат полный JSON read-model — больших объёмов не было, но для длинных прогонов потребуются указатели, не копии.

## Почему `KEEP_EXTERNAL_EXPERIMENTAL`

Hard-гейты (изоляция, целостность данных, replay, чистота canonical, отсутствие scientific leak) — все пройдены, т.е. инструмент надёжен как внешняя лаборатория. Но критерий material advantage для постоянной интеграции не достигнут: для текущего профиля экспериментов Кузницы (короткие offline replay, немного вариантов) агентный путь не дороже, а новая зависимость (бинарь, dashboard, вне-Git state, Windows-beta) — реальная стоимость. Ни один hard-failure не сработал, поэтому не `DROP`; не `ADOPT_EXECUTOR`, потому что ни один из шести критериев adoption не перевешивает burden при текущем масштабе. ORX остаётся доступным внешним инструментом для отдельных длинных/многовариантных research jobs; повторная оценка — если профиль исполнения изменится (серия 5+ вариантов, длинные прогоны, удалённый compute).

## Non-claims

NO_ALPHA · NO_NETRETURN · NO_EXECUTE · NO_NEW_SCIENCE · PILOT_REPLAY_ONLY · NO_HFIC_WRITE · NO_FORGE_CHANGE · NO_PROVIDER_CALLS · ORX_WINNER_NEVER_FORGE_PASS
