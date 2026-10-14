---
spec_id: SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1
version: '1.0'
date: '2026-10-14'
document_kind: SELF_CONTAINED_PRD_SSD_AND_EXECUTOR_BRIEF
planning_mode: DESIGN_ONLY
planning_repository: lancerbeta/solana-alpha-lab
planning_git_ref: 94b391d658b52035ae88e2da05f1ea25ff17b0f8
execution_status: NOT_EXECUTED
execution_entry: REBIND_CURRENT_GIT_AND_AUTHORITY
proposed_execution_scope: AUDIT_KIT_AND_DISPOSABLE_SYNTHETIC_CAMPAIGN_ONLY
production_mutation_authority: NONE
real_market_scientific_authority: NONE
provider_spend_signer_authority: NONE
parent_method: BIG_AGENTIC_AUDIT_PORTABLE_V2
---

# SMIAL: синтетическая репетиция полного жизненного пути
## PRD + SSD + предметные сценарии + передатка исполнителю

**Решение.** Провести одну ограниченную кампанию на настоящем продукте: создать искусственный рынок с двумя заранее известными, но скрытыми от исследующего агента закономерностями; через обычную Кузню найти и оформить их; пройти доступный научный lifecycle и handoff; довести доступные ветви до обычного PAPER-цикла, выходов и восстановления. Внешний рынок и время управляемые. Внутренние решения, guards, persistence и переходы — настоящие.

**Не «проставить зелёные статусы», а дать системе условия для законного продвижения.** Если переход требует данных — предоставить согласованные синтетические данные. Если времени — продвинуть виртуальные часы. Если настоящего эксперимента — вызвать существующий исполнитель. Если отсутствует принятый протокол или producer — зафиксировать разрыв и проверить правую часть отдельным, явно маркированным сегментом. Несколько сегментов не становятся сквозным доказательством.

**Ожидаемый результат:** один воспроизводимый audit kit, карта реально пройденного пути, результат слепого поиска двух паттернов, проверка основных отказов/восстановлений и диагностический backlog. Не новая платформа, не ремонт продукта в той же кампании, не доказательство рыночной alpha.

**Следующий шаг:** исполнитель привязывает этот документ к exact текущему Git, фиксирует audit-only contract и выполняет безопасные этапы до отчёта без промежуточных согласований инженерных мелочей. Передача документа сама по себе не разрешает merge, deploy, реальные операции или расширение расходов.

---

# Часть I. PRD: зачем, что проверяем и какой результат принимаем

## 1. Задача владельца и существенная корректировка постановки

Пока новые реальные данные собираются, проверить недавние ремонты и связность контуров 02–06: не теряются ли значения, идентичности, состояния, право продолжения и старые обязательства при переходах между Кузней, Science, StrategyVersion и Trading. Результат должен помочь выбрать одно следующее исправление, а не загрузить владельца десятками технических решений.

«300 кандидатов» — **около 300 искусственных токенов с наблюдениями**, не 300 hypotheses или MAIN. Базовый дизайн — **320 токенов** для сбалансированных комбинаций признаков; research budget считается отдельно.

«95+% основных сценариев» — приоритет повседневных маршрутов, а не измеренный процент надёжности. Без частот реального использования нельзя честно утверждать покрытие 95% продукта. Вместо этого фиксируется конечный набор существенных переходов: два положительных пути, законный отрицательный результат, недостаточность с продолжением, устаревание/повтор, сбой/восстановление, риск/неизвестное исполнение и согласованность операторских поверхностей.

### Что уже проверено при проектировании

Чтение выполнено на Git `94b391d658b52035ae88e2da05f1ea25ff17b0f8`; это основание плана, не evidence будущего запуска. Источники перечислены в §24.

| Подтверждено источником | Последствие для кампании |
|---|---|
| Обычная Кузня описана как `MANUAL_FALLBACK_UNTIL_GENERATOR`, с реальным агентным authoring и независимым Critic [G03, G04] | Не ожидать, что один Python-вызов сам найдёт две гипотезы. Нужен настоящий агент на обычных tools/prompts. |
| Поддержаны raw holder `point_value`, `delta`, `return_ratio`, сочетания с price/liquidity. EWM/EMA и общий язык выражений отсутствуют [G05] | Заложить два выразимых паттерна; не строить новые representations ради теста. |
| Для ранее проверенного List A recipe зафиксирован `BLOCKED_SCIENTIFIC_PROTOCOL_C`: accepted chronological/OOS successor не установлен [G08] | Больше строк и виртуальное время не устраняют отсутствие научного контракта. Проверить применимость gap к выбранным новым recipes, не переносить verdict автоматически. |
| `RUN_COMPLETED` не заполняет научные obligations, а `PROMOTE` не создаёт StrategyVersion [G06, G07] | Отдельно доказать исполнение, научные записи, решение и materialization. |
| Trading имеет обычный coordinator/run, synthetic virtual clock, frozen originating bindings, PAPER/SHADOW и recovery [G09–G11] | Переиспользовать эту вертикаль. Не собирать второй торговый движок из mocks. |
| Обычная смена — A@V1 → B@V1 с разными scientific identities; same-ID V2 не разрешён данным контрактом [G07, G09] | Для smoke использовать две настоящие synthetic identities. Отказ same-ID V2 не считать регрессией. |
| Прежний Big Audit был частичным; actor и положительный scientific handoff имели пробелы [G12] | Новый результат должен показать приращение evidence, а не выдать старые 56 charters или число tests за новую полноту. |

**UNKNOWN на стадии этого документа:** фактическая изоляция среды исполнителя; доступность слепого genuine actor; достижимость accepted scientific continuation именно для выбранных raw/episode recipes; текущий runtime и любые real-data outcomes. Этот документ их не объявляет проверенными.

## 2. Outcome, потребители и границы

### 2.1. Что должно стать известно владельцу

1. Находит ли обычная Кузня простую и составную закономерности без подсказки правильного ответа; где именно теряется поиск, если не находит.
2. Какие переходы от входных данных до downstream consumer реально достижимы, а какие существуют только как интерфейс или ожидаемое поведение.
3. Можно ли безопасно продолжить после типичного отказа, рестарта, утраты ответа, смены стратегии и восстановления backup.
4. Какое одно source-owner исправление даст наибольшее улучшение целого пути.

Потребители: Пётр; следующий coding executor; независимые reviewers; будущий оператор/агент, который должен повторить проверку без этой переписки. Кампания не производит торгуемую стратегию для рабочего контура.

### 2.2. Scope по продуктовой классификации

| Контур | В scope | Вне scope |
|---|---|---|
| 01. Market Data & Collection | Входной контракт, native import/seal/publication/admission ровно настолько, чтобы создать легальные Forge inputs; PIT/identity/missingness как свойства потребляемых данных | Живые providers, discovery сети, collector service, account quotas, новый сбор, производительность capture |
| 02. Hypothesis Forge | Обычный preflight, representations, bounded search, authored query/card, MAIN, Critic, falsifier, terminal, память попыток, продолжение | Новая модель поиска, генератор, ranker, новые признаки/DSL, максимизация alpha |
| 03. Science & Strategy Lifecycle | Существующие freeze/runner, DIRECT evidence, chronological consumer при его наличии, decision, handoff, StrategyVersion provenance | Принятие нового real-market научного протокола; фиктивный OOS; изменение production thresholds |
| 04. Trading & Execution | CHECK → explicit synthetic activation → обычный PAPER runner → admission → attempt → result → position → exit → reconciliation; ограниченный SHADOW transport/parser segment | MICRO-LIVE/LIVE, настоящие wallet/sign/send/transactions, реальный provider |
| 05. Performance, Risk & Evolution | Корректные labels и арифметика modeled results/costs; exposure/UNKNOWN; существующие pause/drain/retire/feedback consumers | Доказанный NetReturn/FCF; новая система мониторинга; выдуманные thresholds CONTINUE/RETIRE |
| 06. Owner Operations & Control | Канонический CLI/API, существующий Workbench/read model, cold readback, restart, backup/restore, actionable blocker | Полный UI/browser benchmark, весь VPS/deploy/security audit |
| Общая платформа | Изоляция, настоящая SQLite/WAL, exact Git provenance, scoped cleanup, минимальная навигация audit kit | Рефакторинг Harness, CI, инфраструктуры или всей системы backups |

Последний merge на planning ref относится к shared provider-account budget коллектора. Он не превращает collector/account budgeting в предмет этого аудита. **Trading outstanding-obligation envelope и provider call/credit budget — разные сущности.**

### 2.3. Конечная проверяемая точка

Основная правая граница — не только файл стратегии и не только `check=PASS`. Нужен **хотя бы один реально исполненный обычный synthetic PAPER round trip**: источник → signal → admission → committed attempt → modeled result → позиция → originating exit → reconciled modeled accounting, затем fresh-process readback.

Для второй гипотезы достаточно отдельного доказанного handoff/activation и короткого PAPER-прохода; длинные recovery-сценарии не нужно дублировать для обеих. SHADOW — небольшой дополнительный контрактный/процессный маршрут с локальным транспортом; он не блокирует независимый PAPER evidence, но его непроверенность видна.

Если scientific bridge недостижим, runtime-проверка остаётся ценной, но маркируется SEGMENT. Цель максимум вправо не разрешает скрыть разрыв слева.

## 3. Режим, authority и write scope

В этом чате выполнен **DESIGN**, не EXECUTE. При отдельной передаче задачи исполнителю применить действующий `AGENTS.md` и Delivery Harness; зафиксировать exact task contract, маршрут фактического клиента, base/head, write set и resource envelope.

Разрешаемый данным проектом scope выполнения: audit fixtures, адаптеры внешнего мира, observers/oracles, сценарии, отчёт и disposable synthetic state. Разрешённая синтетическая authoring/decision работа относится только к campaign-owned объектам и явно не является новой real-data authority.

**Не включать в audit scope:** изменение product code, production schemas/guards/defaults, рабочего ResearchStore/OperationalStore, реальных policy/profile, научных результатов/holdouts, provider grants, credentials, deploy, внешние записи и деньги. Подготовленные synthetic ExperimentSpec/StrategyVersion допустимы только в audit fixtures и disposable producer repository, не в активных production registries.

Исполнитель вправе чинить собственный fixture/observer/runner, сохраняя invalidated attempts. Продуктовый дефект не «поправляется заодно». Это отдельный repair после аудита. Routine branch/commit/non-force push/PR — только по действующей policy; exact-head CI и merge gate не отменяются.

Самостоятельность исполнителя не расширяет production meaning, science и external authority.

## 4. Три линии проверки, которые нельзя смешивать

| Линия | Что делаем | Что доказывает |
|---|---|---|
| **A — BLIND_NATIVE_DISCOVERY** | Genuine actor, fresh context, обычная Кузня, неизвестные ему planted mechanisms | Способность данного agent+Forge контура найти/выразить различимые закономерности в заданном synthetic мире |
| **B — NATIVE_LIFECYCLE** | Берём реально полученный candidate; через настоящие producers проходим каждый доступный переход | Связность продукта от выбранной входной границы до фактически достигнутого consumer |
| **C — DECLARED_DOWNSTREAM_RESCUE** | После доказанного blocker вводим легальный промежуточный fixture и идём дальше настоящими путями | Работоспособность правого сегмента, но не обходившегося producer, не обнаружение гипотезы и не принятый OOS |

Оси evidence хранятся отдельно:

- `path_fidelity`: `FULL_PRODUCT_PATH | SEGMENT_PRODUCT_PATH | CONTRACT_ONLY | MODEL_ONLY`;
- `actor_fidelity`: `GENUINE_BLIND | GENUINE_UNBLINDED | SCRIPTED | NONE`;
- `external_world`: `SYNTHETIC`;
- `scientific_scope`: `SYNTHETIC_LAB_ONLY`;
- `origin_candidate`: `NATIVE_DISCOVERED | AUDIT_AUTHORED_FIXTURE`.

FULL всегда **относительно явно названных границ**. Полный путь от synthetic StrategyVersion до PAPER не равен полному пути от Forge-ready до PAPER. После bridge все потомки сохраняют его lineage и SEGMENT относительно исходной левой границы.

Внешний LLM — не просто заменяемый transport в линии A: интеллект и authoring здесь являются объектом проверки. Scripted Critic полезен для механических отказов, но не подтверждает качество Critic. Нельзя назвать синтез в той же сессии Builder слепым поиском.

---

# Часть II. SSD: управляемый мир вокруг настоящего продукта

## 5. Reuse-first: конкретные существующие опоры

Сначала повторно разрешить semantic routes и Catalog на execution ref. Приведённые пути проверены при проектировании; это locators, не вечная authority.

| Роль | Существующий locator | Как использовать |
|---|---|---|
| Вход/навигация | `AGENTS.md`; `docs/FACTORY_SEMANTIC_MAP.md`; `catalog/catalog_manifest.yaml` | `SEM-HYPOTHESIS-FORGE`, `SEM-EXPERIMENT-CAPABILITIES`, `SEM-OWNER-LIFECYCLE`, data-feature route |
| Обычный Forge actor | `.agents/skills/hypothesis-forge/SKILL.md`; `scripts/hypothesis_forge.py` | Реальные preflight/query/persist/freeze/finalize/readback; actual emitted authoring contract |
| Native authoring и recovery | `docs/contracts/forge_native_lifecycle_closure_v1.md`; `docs/contracts/forge_ordinary_operation_lifecycle_v1.md` | Не подставлять намерение после MAIN; продолжать saved session, не повторять research |
| Raw composite источник | `docs/contracts/forge_composite_feature_recipes_v1.md`; `tests/test_forge_composite_feature_recipes_v1.py` | Native seal/import/public CLI и supported feature recipe |
| Accepted experiment consumer | `configs/experiment_capability_registry_v2.yaml` | Установить exact capability, вход, выход, scientific limits. Registry entry не равен принятому новому протоколу |
| Science dossier/decision | `docs/contracts/experiment_evidence_decision_v1.md` | DIRECT joins, отдельные execution/science/decision planes, stale snapshot и no-write |
| Strategy handoff | `docs/contracts/science_to_strategy_handoff_v1.md` | Manifest, ExecutionEvidenceBinding, CHECK/RENDER/VERIFY, explicit execution inputs |
| Episode → runtime | `docs/contracts/episode_decision_continuity_v1.md` | Shared feature/PIT semantics, recipe binding, source/admission distinction |
| Обычный Trading | `docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md`; `scripts/trading_continuity.py` | Native init/check/operating-activate/run/status/controls/backup/restore/reconcile |
| Процессная proof-опора | `scripts/prove_trading_core_operational_closure.py` | Настоящие `TradingContinuityRunner`/`TradingCoordinator`, lowest quote transport, отдельный durable ledger |
| Старый audit kit | `tests/fixtures/big_agentic_audit_v1/`; `tests/test_big_agentic_audit_v1.py` | Reuse trace/oracle/coverage controls; старые verdicts не наследовать |
| Предыдущие gaps | `docs/reports/big_agentic_audit_v1/REPORT.md`; `docs/reports/forge_trust_closure_v1/SCIENTIFIC_DECISION.md` | Узко проверить сохраняющийся gap, не перепроверять всю историю PR |

В proof script найдены trading suites: `test_trading_core_operational_closure_v1`, `test_trading_operational_adapters_v1`, `test_trading_operational_obligations_v1`, `test_trading_operational_recovery_v1`, `test_trading_continuity_v1`. Сначала выбрать полезные точные tests/fixtures, а не автоматически гонять все suites на каждом шаге.

## 6. Архитектура kit — максимум пять логических ролей

```text
Private world recipe + hidden oracle
                │
                ├── source events / cohorts / time / local quote bytes
                ▼
       Existing native ingress + actual product
       Forge → Science → Strategy → Trading → read models
                │                       │
                │                       └── independent external-effect ledger
                ▼
       Fresh-process observer + independent checks
                │
                ▼
       attempt ledger → coverage/findings → OWNER_REPORT

Genuine Actor ↔ обычные продуктовые tools и разрешённые public inputs
Genuine Actor ✕ private recipe / oracle / unreleased OOS / старые ответы
```

Достаточны существующий runner, Python из locked toolchain, реальные product stores, небольшие JSON/YAML/JSONL, Markdown. Не добавлять сервис, очереди, graph DB, агентный framework или новый test dependency по умолчанию.

Роли Builder, Actor, Observer разделяются доступом и контекстом; они не требуют трёх новых подписок. Observer может быть детерминированным скриптом. Отдельный fake-effect ledger — только там, где нужен независимый от откатываемой runtime DB свидетель submit/result/recovery.

### Single source кампании

Один `campaign.json` или YAML хранит bindings, сценарии, обязательства, worlds, budgets, fingerprints и bridge declarations. Coverage и отчёт — производные. Не создавать одновременно разные PRD, plan и registry с расходящимися списками сценариев.

## 7. Изоляция, слепота и provenance

### 7.1. Минимальные независимые пространства

1. **Private builder/scorer root:** generator, ground truth, oracle, unreleased partitions, старые actor outputs. Actor его не видит.
2. **Immutable product execution root:** exact product commit и необходимые schemas/docs; code/provenance не меняются во время lifecycle. Нужный product Git context сохраняется, а не имитируется фиктивным SHA.
3. **Disposable data roots:** отдельные настоящие stores каждого trial/world. Где native Trading требует child `<repo>/local/<owned-case>`, выполнить этот контракт внутри изолированной среды; не отключать root validator ради удобного пути.
4. **Independent effect/evidence root:** переживает откат runtime backup; не используется как скрытый writer product state.

Это логические границы, не требование четырёх контейнеров. Предпочтителен existing confined test runner. Один контейнер/процессная среда достаточен, если запреты проверяются и Actor не может читать scorer через общий shell.

### 7.2. Обязательный preflight до product run

Проверить effective mounts/roots, запрет product egress, отсутствие real datasets/holdouts/credentials/signer/SSH agent/Docker socket, child-process inheritance и очистку только собственных ресурсов. Сделать безвредный probe записи вне разрешённого root и локальный probe blocked egress, без запроса к настоящему provider.

Synthetic marker — не единственная защита. Native runtime root, конфигурация/режим и физическая недоступность production должны согласоваться. Идентификаторы mint могут иметь валидную форму публичного адреса, но не требуют генерации private key или кошелька.

### 7.3. Как получить действительно слепого Actor

Приоритет: существующий fresh client/agent runtime с ограниченными product tools → имеющийся sandboxed invocation → явно неподтверждённая actor-линия. Не устанавливать платформу ради этого.

Actor получает продуктовую миссию из §11, обычные semantic docs/preflight и разрешённые synthetic inputs. Он не получает этот полный документ, рецепт §8, oracle, тестовые ожидаемые значения, имена hidden families или историю предыдущего решения. Доступ к `tests/fixtures`, private campaign kit, git history с ответами и произвольным host tools закрыт.

Продуктовый процесс может иметь полный exact checkout для provenance. Actor должен видеть только обычные product tools/нужные docs, а не всё файловое пространство процесса. Ограничение только словами в prompt при свободном shell не считается слепотой.

Использовать уже разрешённый model/client entitlement. API key, новый model/provider, новый платёж или расширение network scope не создавать. При доступном model transport отделить его от product-side network и передавать только synthetic данные. Если fresh context и confinement недоступны, поставить `AGENT_BEHAVIOR_UNVERIFIED` и продолжить B/C; это не основание остановить всю кампанию.

### 7.4. Неизменяемые fingerprints

До native preflight зафиксировать product commit/composite, method/schema hashes, world version, source hashes, runtime dependency lock, scenario schedule. В исполняемом checkout не коммитить/не fetch/не регенерировать навигацию во время session. Evidence-only delivery делается отдельно.

Перезапуск Actor — новый trial с fresh state, но внутри одного trial restart/resume не обнуляет spent looks, journal, epoch, reservations или Critic identity. Изменение world после наблюдения Actor — новая версия benchmark, не исправление истории.

## 8. Synthetic world: две очевидные для проверки, но не подсказанные Кузне закономерности

**Весь раздел — предложенный test design, не утверждение о рынке и не production science contract.** Эти параметры известны Builder/Observer, но не Actor.

### 8.1. Базовая конструкция W-POS

320 уникальных mint, 10 хронологических когорт по 32. В каждой когорте равномерно представлены восемь комбинаций трёх независимых двоичных факторов S/A/B: по четыре разных токена на комбинацию. Neutral IDs перемешаны независимо от группы.

Факторы кодируются обычными наблюдаемыми pre-decision признаками:

| Фактор | True | False | Поддержанный raw смысл |
|---|---|---|---|
| S | holder growth примерно +22…36% | примерно −5…+10% | `return_ratio(H, start, end)` |
| A | price return примерно −5…−3% | примерно 0…+2% | Pre-decision price `return_ratio` |
| B | liquidity ratio примерно 1.08…1.20 | примерно 0.94…0.99 | Pre-decision liquidity `ratio` |

**H-SIMPLE:** сильный прирост holders связан с более высоким последующим price-relative return. Удобный hidden discriminator: holder return ≥ 0.20.

**H-COMPOUND:** небольшой ценовой откат **в сочетании** с ростом/устойчивым увеличением liquidity связан с дополнительным последующим результатом. Hidden discriminator: price return ≤ −0.02 AND liquidity ratio ≥ 1.05.

Порог — не пароль для grading. Любой поддержанный predicate, который на независимой контрольной сетке выделяет те же группы и сохраняет смысл, допустим. Сам факт, что Actor назвал слова «holders» или «ликвидность», не является discovery.

Пример генеративной зависимости только после decision:

```text
future_price_relative_return = -0.025 + 0.12*S + 0.16*(A AND B) + epsilon
|epsilon| <= 0.008
```

Это намеренно сильные инженерные positive controls. Не оценка реальной доходности. Noise и базовые уровни независимы от neutral IDs, cohort labels и технического порядка строк; balance сохраняется across splits. Новые токены получают собственные значения, а не копии одной успешной записи.

Составной механизм должен отличаться от простой корреляции одного компонента: Observer заранее проверяет четыре клетки A/B, условный вклад B при A и отсутствие такого вклада при not-A. Однофакторная находка A не засчитывается как обнаруженная составная гипотеза, даже если у A есть положительный marginal contrast.

### 8.2. Времена и units

Builder разрешает реальные schedule points из действующего descriptor: `t_start < t_feature_end <= t_decision < t_entry <= t_exit`. Поддержанные names вроде X300/Y900 — только пример; не навязывать несуществующий point или другой target.

Различать birth/age токена, observation window, decision time, entry latency, holding/exit и evaluation/maturity. Возраст токена не служит скрытой меткой успеха. Глобальный горизонт 15m–4h не вводится этим тестом: выбранные точки следуют проверяемому current contract.

Сначала задать независимые исходные цены, integer holders и liquidity, затем получить производные. Holder ratio считается из фактических integer значений; rounding не должен случайно пересечь hidden boundary. Price/liquidity — положительные конечные Decimal-совместимые значения; return fraction и percent не путать.

Все материализованные cells несут native identity, source refs, event/observed/available/visibility clocks и необходимые witnesses. Native статус отдельной ячейки `OBSERVED` внутри simulation не превращает внешнюю evidence-class кампании в реальные наблюдения рынка.

### 8.3. Разбиение во времени

| Partition | Когорты | Уникальные mint | Доступ Actor |
|---|---|---:|---|
| DISCOVERY | C01–C04 | 128 | Через обычные инструменты после native admission |
| VALIDATION | C05–C07 | 96 | Не раскрывается до freeze проверяемого candidate/protocol |
| PAPER_FORWARD | C08–C10 | 96 | Публикуется event-by-event после synthetic activation |

Хронологические блоки не пересекаются с учётом полного observation/target/holding horizon и publication delay. Между partition — достаточный gap по реальным schedule semantics. Mint disjoint в базовом мире; сценарий repeated mint проверяется отдельно. Физическая изоляция unopened partition защищает исследование дополнительно к PIT-фильтрам.

**Два разных holdout:** физически закрытая VALIDATION проверяет продуктовый freeze/chronology; скрытая scoring grid проверяет семантику найденного predicate. Ни один не является настоящим market holdout. Нельзя скормить Actor весь mature мир и потом объявить его часть нетронутым OOS.

### 8.4. Почему размера может не хватить

128/96/96 — стартовый fixture, не гарантия scientific sufficiency. До первого Actor trial прочитать текущие gate requirements по cohort count, effective N, coverage, horizons и constraints. Если fixture не достигает legitimate positive preconditions, увеличить **целые новые сбалансированные блоки** до заранее установленного cap либо зафиксировать несовместимость. Не уменьшать guard и не считать повторные строки независимыми токенами.

Статистическая мощность настоящего рынка не оценивается. Positive fixture должен иметь заметный запас относительно уже существующих проверяемых требований. Калибровка допустима до freeze benchmark, с записью recipe revisions; после просмотра actor outcome нельзя менять эффект/seed/threshold ради PASS.

### 8.5. Четыре компактных семейства миров

- **W-POS:** описанный положительный мир. Для transfer trial — новые IDs/base levels/noise seed с теми же механизмами.
- **W-NULL:** те же pre-decision distributions, но future effect S/A/B отсутствует; результат ниже заранее заданного lab practical floor. Проверяется отсутствие необоснованного положительного вывода, не отсутствие любых предложенных идей.
- **W-DECOY:** эффект существует в DISCOVERY, исчезает или меняет знак в VALIDATION. Проверяется честная реакция на провал переноса, а не «дожим до PROMOTE».
- **W-FAULT overlays:** missing/late/dead/no-route/duplicates/clock/fault/cost perturbations поверх тех же recipes. Не создавать новый огромный dataset для каждого отказа.

Основной W-POS не перегружать missingness и fault combinations: сначала доказать достижимость, затем ломать по одной существенной предпосылке и по нескольким выбранным взаимодействиям.

## 9. Ускорение времени: дать недостающее, не отключать проверку

Event driver доставляет только разрешённые события, продвигает synthetic clock до следующего существенного события и вызывает настоящий worker/consumer. Не нужен sleep на часы; не нужен глобальный monkeypatch времени всей машины.

```text
next := earliest(source_event, publication, due_exit, retry_due, TTL_boundary)
advance synthetic business clock to next
publish due external-world stimuli via native ingress
invoke existing product cycle / worker
read committed state independently
check obligations; record progress or typed blocker
```

Это логика runner, не имена новых product API. Для конкретного шага использовать реальные flags/hooks. Clock инъектируется только на существующей внешней границе; отдельный monotonic wall watchdog ограничивает зависший процесс.

| Product blocker | Разрешённое действие в simulation | Что запрещено |
|---|---|---|
| Нужно созревание target/cohort | Доставить native observations, продвинуть logical time, вызвать настоящий seal/release | Записать READY/complete вручную |
| Недостаточно N | До benchmark freeze обеспечить больше новых synthetic units; в отдельном scenario зарегистрировать later evidence и законное продолжение | Снизить threshold; клонировать N; переписать старый result |
| Нужен ExperimentSpec | Author в disposable producer repo по текущему schema и реальной найденной гипотезе, до validation values | Подменить intent после MAIN или менять frozen spec |
| Нужен accepted evaluator/protocol | Разрешить exact существующий consumer; вызвать на synthetic inputs | Объявить новый protocol принятым из-за наличия данных |
| Нужен quote/funding input | Native-shaped локальный внешний ответ с согласованными clocks/units | Реальный HTTP, fabricated final fill/PnL в DB |
| Истёк TTL/нет свежего input | Доставить новую своевременную запись для будущего решения | Делать старую запись своевременной задним числом |
| Нужен реальный owner/external gate | Сохранить настоящий gate. Для отдельного synthetic segment использовать явно тестовую роль/fixture | Подделать реальное разрешение или замаскировать денежный action |

Использовать synthetic `--as-of`/`--clock-file` только там, где они разрешены. `OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK` для observed-root — правильный отказ, не препятствие, которое нужно убрать. Virtual wall compression не доказывает real-time performance, scheduler reliability или сетевую latency.

## 10. Oracle и предварительная проверка самого мира

Oracle — независимый способ понять правильный результат. Он не должен вызывать проверяемую product function для получения expected.

### 10.1. До широкого запуска

Проверить реальными validators shape входа. Отдельным простым Decimal-расчётом проверить selected counts, missing counts, returns и contrasts по маленькой literal таблице; затем sanity-check full recipe. Для каждого сравнения использовать **фактический canonical baseline**: eligible complement, pooled population или другой declared comparator. Не подменять его удобной группой.

На уровне worlds подтвердить hidden mechanisms во всех planned partitions, support каждой комбинации, нейтральность IDs/порядка, отсутствие future input в decision и согласованность ценового пути с моделью quote/entry/exit. Это валидация тестовой задачи, а не поиск удачного seed после того, как Actor не справился.

### 10.2. Границы независимости

Разрешено reuse product serializers и native schema validation. Expected arithmetic, membership контрольных случаев и причинная конструкция мира остаются независимыми. Для сложного downstream result предпочтительнее invariant/hand calculation, чем вторая реализация всего trader.

Пример простого accounting oracle: entry фактически моделирует cash debit 30.060, exit cash credit 32.934, отдельно начисленный cost 0.020. Итоговый **modeled** PnL = 32.934 − 30.060 − 0.020 = 2.854. Price-leg fees уже учтены в debit/credit и не вычитаются повторно. Это пример соглашения теста; фактический oracle обязан следовать текущим полям и units.

Обязательные парные отношения, когда их предусловия соблюдены:

- одинаковый decision prefix + изменённое будущее → прежнее decision не меняется;
- тот же committed logical request/reply loss → нет второй semantic операции/charge;
- одинаковые fixed fills и quantities + больше дополнительного cost → modeled net не улучшается;
- rename нейтральных labels/перестановка независимых deliveries → scientific identity и membership сохраняются;
- сброс только derived cache → тот же read model из authoritative records.

Это не требует нового property-testing framework. Достаточно нескольких выбранных пар и точных assertions.

### 10.3. Harness canaries

Перед массовой campaign должны пройти: легальный native positive witness; отказ, реально достигший target guard; намеренно испорченный readout/fixture, который Observer обнаружит. Также empty trace, unvisited edge, truncated tail и две SEGMENT цепочки не должны агрегироваться в FULL/PASS.

Если canary не поймана, это `INVALID_HARNESS`; сначала исправить audit kit и аннулировать зависимое evidence. Не «проверять продукт» слепым измерителем.

# Часть III. Исполнение настоящего пути

## 11. Genuine Actor: миссия, бюджет и grading

### 11.1. Public mission — передать только этот блок и обычный product context

> Выполни обычный `/hypothesis-forge` только для выделенного synthetic campaign root и разрешённого focus. По доступным данным и каноническим инструментам сформулируй различимые, проверяемые предсказательные гипотезы. Используй текущую supported vocabulary, research policy и учёт попыток. Обоснуй наблюдаемую связь, сравнение, сильную альтернативу, falsifier и ограничения. Доведи достойные candidates до обычного сохранённого terminal либо сохрани точный научный/технический отрицательный результат. Не меняй продукт, guards, скрытые файлы или права; не обращайся к реальному рынку. Сначала читай saved state при потере процесса/ответа. Не требуется придумать гипотезу любой ценой. Верни refs реальных результатов и следующий разрешённый шаг.

Не сообщать Actor, что обязательно существуют ровно два planted механизма, их признаки, пороги или ожидаемый verdict. Обычный preflight раскрывает доступные поля и capability — это нормальная product legibility, не подсказка ответа.

### 11.2. Практическая ограниченность

До открытия numerical values создать явный **synthetic** research profile/operation через штатный ingress. Ceilings, candidate count, MAIN/ADAPTIVE/PREVIEW allowances и одна возможность продолжения должны быть достаточны для двух различимых candidates и соответствовать current policy. Не переносить live minima и не расширять production policy.

Ориентир budget design: не более 6 содержательно разных candidate formulations, до 4 MAIN и до 2 support PREVIEW на один положительный trial, только если такие размеры допустимы текущим контрактом. Это proposal для sandbox, не новые shipped defaults; точные scope fields/ceilings зафиксировать перед values. Узкий лимит, разрешающий только одну гипотезу, несовместим с clean claim «проверили нахождение обеих» — исправить fixture policy до запуска или честно сузить claim.

Default — три независимых positive trials с fresh Actor contexts и fresh world states; один из них проходит правую вертикаль полностью, остальные могут завершаться после genuine Forge terminal. Один отдельный W-NULL actor trial. Дополнительные trials — только по конкретной неразрешённой причине и внутри envelope, не best-of-N до зелёного.

Сохранить исходные outputs, видимые tool calls, accepted artifacts, доступные model/client/version параметры, counts и terminal. Недоступные model seed/стоимость — UNKNOWN; скрытый chain-of-thought не запрашивать. Оригинальный Critic вызывается в отдельном контексте на его фактическом frozen packet. Его отрицательный вывод не заменять scripted PASS.

### 11.3. Что считать обнаружением

Для каждой hidden family отдельно фиксировать:

`OBSERVED_IN_DATA → EXPRESSED_AS_SUPPORTED_QUERY → NATIVE_GROUNDED → CRITIC_TERMINAL → OWNER_FINAL_PERSISTED`.

Scorer проверяет authored executable condition на небольшой закрытой контрольной сетке с независимыми expected memberships, направление сравнения, неизменность question/estimand и evidence refs. Допускаются эквивалентные пороги внутри зазоров и формулировки. Один смешанный candidate засчитывает обе families только при явном разделении обоих механизмов и проверяемых contrasts, а не по общему позитивному результату.

Если найден другой действительный паттерн — сохранить как incidental synthetic finding. Не расширять search budget и не выдавать его за market discovery. Если получен содержательный KILL, разделить «Actor заметил/выразил паттерн» и «candidate прошёл Critic»: обнаружение не обязано означать promotion.

Итог: H-SIMPLE и H-COMPOUND по каждому из трёх trials; first-attempt outcomes; все failures/revisions. 3/3 — повторяемость на этих synthetic задачах, не оценка 95% reliability.

## 12. Native lifecycle: точные смысловые переходы

Ниже операции описаны семантически. Реальные CLI/API аргументы исполнитель связывает из текущих `--help`, schemas и callers в `campaign` **до первого широкого прогона**. Не придумывать отсутствующую команду или hand-bind, чтобы заполнить таблицу.

| Шаг | Настоящее действие | Обязательный независимый witness |
|---|---|---|
| N0. Source acceptance | Создать synthetic source events; native seal/import/release/admission выбранного ingress | Схема, IDs, counts, source hashes, clocks; actual Forge input receipt |
| N1. Preflight/context | Обычный scope/capability/policy/prior resolver | Реально опубликованные representations и ограничения; только DISCOVERY доступен |
| N2. Search/look | Actor фиксирует query, estimand и condition до MAIN; реальный reservation/evaluator | Query/scope hashes, журнал и charge, actual descriptive readout, denominator |
| N3. Candidate/critique | `persist-draft` → refreshed bound preflight → freeze → isolated genuine Critic → допустимые classify/revise/finalize | Сохранённые draft/packet/result/terminal; causal story не навязывается PREDICTIVE |
| N4. Run completion | Ordinary `forge-run --persist` для правильного focus, затем cold `--no-write` | Run owner-final и session terminal различены; effective operation state и charges согласованы |
| N5. Experiment definition | Author exact ExperimentSpec найденного candidate в disposable definition plane; frozen recipe/target/split/cost/exit | Definition commit/hash, candidate lineage, runtime recipe compatibility, unopened validation |
| N6. Experiment execution | Actual registered runner и accepted chronological consumer, если он существует | RUN identities/passport, DIRECT result records, отдельный source-backed science readout |
| N7. Decision | Прочитать dossier; обычная synthetic decision command по актуальному snapshot | DECISION_EVENT; stale refusal/no-write; obligations не взяты из RUN_* или RELATED |
| N8. Strategy materialization | Actual CHECK/RENDER/VERIFY по manifest и explicit execution inputs | Exact StrategyVersion bytes + source decision/spec/recipe/binding; конфликт не перезаписан |
| N9. Runtime acceptance | Native CHECK, explicit synthetic activation и обычный run | Реально сохранённая activation/operating closure; source → position → exit → accounting |
| N10. Owner visibility | Новый процесс читает status/readback и material Workbench/API view | Совпадение с committed truth; корректные labels, точный blocker/next action |

**Два опасных перехода проверить отдельно:**

- Raw discovery query → `ExperimentSpec.parameters.episode_query` → runtime interpretation. Наличие raw research operator не доказывает поддержку тем же runtime. Пример должен пройти реальный validator, а не быть переведён вручную с потерей смысла.
- Выбор training cohorts → runtime universe. Runtime явно отказывает research-corpus cohort selection (`RUNTIME_COHORT_SELECTION_UNSUPPORTED`). Не удалить cohort selector молча. Разделение research split и будущего executable universe должно быть выражено существующим контрактом до freeze. Отсутствующий mapper/contract — finding, не косметический adapter.

Если definition commit нужен по native provenance, выполнять его в разрешённой disposable definition plane на границе завершённой стадии; не менять composite внутри незавершённой Forge session. Каждый stage сохраняет свою exact producer identity.

## 13. Science: максимальное продвижение без фиктивного OOS

### 13.1. Сначала проверить наличие принятого continuation

Для exact candidate recipe разрешить capability, protocol owner, split, estimand, evaluator, uncertainty/robustness rule и DIRECT output producer. Не считать список capabilities или наличие произвольного chronological algorithm достаточным.

Ранее зафиксированный BAA-003 относится к конкретному List A proxy [G08]. Он не доказывает отсутствие всех путей и не даёт права подобрать другой estimand незаметно. Проверка текущего выбранного пути должна закончиться либо exact binding, либо узким `SCIENTIFIC_PROTOCOL_GAP`/`PRODUCER_GAP`.

При accepted continuation: исполнить его на закрытой до freeze VALIDATION, без retune. При достаточном synthetic evidence продвигать через штатное решение. При legitimate insufficiency/KILL/PAUSE сохранить результат и проверить его downstream readout. Не требовать PROMOTE вопреки evidence.

### 13.2. Независимая lab validation при отсутствующем production protocol

Не терять возможность проверить planted world. Простой audit-only reference evaluator может сравнить frozen predicate на C05–C07, показать support/contrast/исчезновение эффекта W-DECOY и корректность скрытого split.

Lab-only positive criterion фиксируется до values: не менее 12 calculable matched units суммарно, representation присутствует во всех трёх validation cohorts, contrast к canonical comparator ≥ 0.05 в сумме и положителен в каждой когорте. Это инженерная проверка seeded эффекта, не confidence interval или принятый научный threshold. W-NULL/W-DECOY не должны пройти её. Native protocol сохраняет собственные правила.

Результат — `MODEL_ONLY / SYNTHETIC_LAB_ONLY`, не native OOS и не право PROMOTE. Это oracle для **авторского** downstream fixture. Не регистрировать accepted production capability и не заполнять obligations одним JSON ради gate.

### 13.3. Контролируемый rescue, если native цепочка остановилась

После воспроизводимого earliest blocker:

1. Сохранить native attempt и недостигнутые obligations. Не продолжать перебирать обходы одного seam.
2. Выбрать **ближайшую правую легальную входную границу**, где existing tests уже принимают synthetic scientific fixture.
3. Подготовить такой fixture как audit-authored внешнее основание этой границы. Все значения имеют refs на synthetic lab evidence или явно указанные test assumptions. Отсутствие настоящего producer не скрывается.
4. Далее вызвать реальные decision/materialization/activation consumers. Если необходима авторская запись DIRECT evidence через native writer — это объявленный bridge; её наличие не является доказательством scientific producer. Не делать прямой SQL final-state update.
5. Записать bridge record и распространить SEGMENT fidelity на всех потомков.

Минимальный bridge record:

```yaml
bridge_id: BR-01
reason: SCIENTIFIC_PROTOCOL_GAP
native_last_verified_boundary: <resolved boundary>
rescue_ingress: <real accepted fixture input>
bypassed_edges: [<exact edge IDs>]
origin: AUDIT_AUTHORED_FIXTURE
source_refs: [<synthetic evidence and assumption refs>]
claim_limit: DOWNSTREAM_MECHANICS_ONLY
forbidden_claims: [NATIVE_OOS, NATIVE_END_TO_END_FROM_FORGE, MARKET_ALPHA]
```

В основной positive цепочке допускается один такой rescue cut для отсутствующего scientific bridge; additional cut нужен только для действительно другого material gap и обязан остаться видимым. Десятки промежуточных подстановок — повод остановить попытку назвать это long path и сдать честную карту отдельных сегментов.

Внешняя метка synthetic/fidelity может жить в audit manifest, если closed product schema её не допускает. Не расширять production schema только ради маркировки; при этом каждая audit-produced сущность должна однозначно находиться по sidecar lineage и disposable root.

## 14. PAPER/SHADOW: действительно использовать то, что подготовлено

### 14.1. Положительный обычный PAPER spine

Использовать `scripts/trading_continuity.py`: `init`, `check`, `operating-activate`, `run`, `status`, `readback`. Общий проверенный префикс: `uv run --locked --managed-python python -B`; exact обязательные arguments взять из current CLI. Не вызывать `episode`/`attempt` вручную как единственное доказательство автоматического coordinator.

Для каждой synthetic strategy явно задать допустимый notional, fee model, risk limits, max age, source root/schedule, funding/metadata inputs и operating envelope. Числа — **test configuration**, не production defaults. Рецепт содержит отдельный `runtime_execution` с поддержанным `FROZEN_TIME_EXIT`: научный target не заменяет executable exit rule.

Forward source публикуется по logical времени. Сценарий должен гарантированно иметь своевременный подходящий сигнал и ресурсный headroom хотя бы для одного полного round trip каждой стратегии. Не сделать safety-only систему, где всё отказывается и поэтому кажется безопасным. Для первого spine планировать разнесённые входы/выходы; deliberate contention проверяется отдельной ветвью.

Modeled result выдаёт штатный PAPER adapter из timely source inputs. В SHADOW использовать существующий lowest quote transport, а parser, decimal conversion, intent/attempt identity, costs и result acceptance оставить production-owned. Локальные bytes согласовать с исходным price path, amounts, mint/decimals и funding FX; `quote != fill`.

### 14.2. Переключение и общий риск

A@V1 → B@V1 с разными scientific identities, пока у A остаётся обязательство. Проверить: entry-enabled только допустимый current bot; старый A exit использует исходные recipe/epoch/binding; обязательство A продолжает занимать общий mode envelope; отказ нового B entry не останавливает healthy A exits.

Проверить тот же запрет через legacy public `episode/attempt` ingress после ordinary activation: пропуск operating flag не должен обходить operating limits. Не переносить правила ordinary mode на genuine isolated legacy fixture, где контракт сохраняет иную совместимость.

`PAPER` и `SHADOW` не объединяются в один cashflow. Policy-tightening не переписывает StrategyVersion. Missing/invalid current entry policy не должна уничтожать известное старое inventory или блокировать здоровый originating exit сверх своего фактического scope.

### 14.3. UNKNOWN, partial и cost floor

Fault вводится после доказанного нужного commit: например attempt сохранён, внешний ответ потерян. Observer должен видеть pending/UNKNOWN, сохранённую reservation и отсутствие повторного dispatch под новым ключом. Definitive nonfill освобождает только доказанное обязательство; failed exit не делает позицию flat.

В ordinary v1.1 поддержанный partial exit уменьшает quantity/cost basis пропорционально; остаток и additional costs сохраняются. Не переносить старое legacy `PARTIAL_EXIT_MODEL_UNSUPPORTED` на новый ordinary seam без проверки actual owner. Cumulative additional cost не уменьшается; UNKNOWN total не стирает прежний known floor; quote fees не списываются второй раз.

### 14.4. Recovery без ручного восстановления «правильного» состояния

Один приоритетный process/backup scenario: native backup → новый effect/switch/control после backup → crash → restore в fresh marked root → independent complete external cut → reconcile → exact ACK → старые obligations обслуживаются. External ledger не откатывается вместе с DB.

Проверить, что naked inventory ACK и неполный/conflicting cut оставляют fence. Изменения operating envelope/policy после backup не должны потеряться при restore. Все restored bots остаются paused до отдельного допустимого resume. Отсутствующий cut — UNKNOWN и blocker, не повод собрать его вручную из желаемого inventory.

Это один составной сценарий с variants, а не отдельная backup-платформа. Reuse existing recovery fixture и реальный процессный seam; teardown не удаляет retained forensic evidence.

## 15. Обязательная исходная матрица сценариев

Сценарий — проверяемое обещание, не обязательно отдельный test file. Несколько строк можно закрыть одним trace. До широкого sweep связать все строки с exact owners/entrypoints/oracle. `N/A` требует current contract reason; неудобная реализация — не N/A.

| ID | Мир / маршрут | Должно наблюдаться | Главный запрещённый исход |
|---|---|---|---|
| S00 | Harness/safety canaries | Positive reaches, negative reaches target guard, corruption detected, effective isolation | PASS без посещения границы или при доступе к production |
| S01 | Blind W-POS: simple | Реальный query/card/MAIN/critique/terminal; recovered H-SIMPLE по независимой сетке | Подсказанный recipe или scripted success объявлен discovery |
| S02 | Blind W-POS: compound | Реальная conjunction и joint support, отличие от marginal single-factor результата | Перемножение marginal coverage или потерянный conjunct |
| S03 | W-NULL и negative memory | Можно предлагать идеи, но нет unsupported positive verdict; negative/disposition читается новым процессом | Cap/technical stop назван научным исчерпанием; blank prior исчез |
| S04 | W-DECOY: discovery → validation | Frozen проверка ловит непереносимость; правильный native outcome либо явный protocol gap + lab counterexample | Подгонка spec после validation; REAL/market promotion из simulation |
| S05 | PIT/late/future poison | Future-only change не меняет prefix decision; missing/late не становится 0; dead/no-route остаются в своём denominator | Future target влияет на eligibility, поздняя публикация лечит старое решение |
| S06 | Insufficient → later evidence | Typed stop; новая законная maturity/release или continuation продвигает; старый результат сохранён | Ручное READY, снижение N, воскресший CLOSED/STOPPED, hidden new look |
| S07 | Forge crash/ACK/restart | Saved draft/result/terminal, один logical charge, monotone completion и корректный operation gate | Повтор MAIN/Critic без необходимости, новый focus обнуляет budget |
| S08 | Stale/foreign/identity | Same request replay, changed-content conflict, RELATED≠DIRECT, stale decision zero-write | Подбор evidence по названию/latest, «тот же mint» как полная identity |
| S09 | Science→Strategy handoff | Manifest/decision clock/spec/binding сохраняются; exact materialization принимается downstream | RUN_COMPLETED заполняет science; fixture bridge скрыт как FULL |
| S10 | Ordinary PAPER + two strategies | Source→position→exit, A→B, old A obligation в общем envelope | B получает освобождённый headroom при UNKNOWN A; старый exit пропал |
| S11 | Entry blocker × old exit × legacy API | Локальный B отказ не останавливает здоровый A exit; operating limits нельзя обойти legacy входом | Fatal всего runner из-за обычного отказа нового ENTRY |
| S12 | No-route/partial/UNKNOWN/costs | Реальные attempt/result transitions, no resend, exact remainder/known cost floor | Flat/fill/0 costs из UNKNOWN; повторный external dispatch |
| S13 | Backup→post-cut effects→restore | Fence, original identities, complete cut, preserved tightened config, old exits | ACK по одной цифре inventory, loss/duplicate или менее строгий лимит |
| S14 | Fresh readback/оператор/feedback | Committed WAL виден с живым writer; CLI/API/Workbench не усиливают claim; actionable next step | UI ready при source gap; GET пишет business state; simulated FCF |

Для S14 достаточно одного действительно используемого owner surface и machine source readback. Если проверяется Workbench interaction — использовать существующий browser path; direct API не выдавать за human UI proof. Если browser недоступен, API/store evidence сохраняется, UI остаётся UNKNOWN.

Feedback к Forge проверяется через существующий negative/disposition/prior consumer. Если automated monitor→PAUSE/RETIRE/feedback отсутствует или thresholds `NOT_CONFIGURED`, фиксировать это как границу capability, не придумывать мониторинг. Можно доказать механический explicit pause/drain и сохранность history; нельзя назвать это автоматическим обнаружением degradation.

## 16. Низкоуровневые controls с высоким выигрышем

Применить на соответствующих сценариях, не строить полное декартово произведение:

**Replay after commit.** Взять writer barrier после durable append и до reply; убить owned child, открыть новый процесс, прочитать authoritative record, повторить тот же request. Проверять IDs, число material events/charges и следующую допустимую операцию, а не только exit code.

**WAL readback.** Writer держит connection; commit фиксируется barrier. Независимый readonly SQLite и новый product read transaction должны видеть один state. Уже открытый snapshot вправе сохранять старый view. GET не делает migration/checkpoint; SHM coordination учитывать отдельно от durable business writes.

**PIT differential.** Скопировать один legal decision-prefix; менять только target/future-only cells. Сравнить decision packets и eligible denominator до будущего release. Для late/revision отдельно проверить доступность по time, а не пытаться потребовать неизменность там, где frozen input законно изменился.

**Unknown accounting.** Сверить attempt ledger, external call ledger, quantity/cost events и current projection. Удаление ответа не означает отсутствие call; не создавать второй call для получения удобного witness.

**Fingerprint conflict.** Сохранить identity, изменить material body без обновления hash/или с несовместимым hash; native consumer должен отказать в точной границе. Негативный fixture сохраняет валидный upstream shape, иначе проверяется parser, не нужный guard.

**Interacting factors.** Приоритетные тройки: `switch × UNKNOWN old obligation × new ENTRY`; `backup × policy/envelope tightening × late effect`; `MAIN commit × lost reply × restart`. Их нельзя засчитать по трём отдельным unit tests.

---

# Часть IV. Evidence, сдача и продолжение

## 17. Что записывать — и чего не записывать

Reuse existing product traces; audit JSONL добавляет только недостающие связи. На каждый material transition:

```text
campaign / scenario / trial / attempt / monotonic sequence
product + world + recipe + policy fingerprints
boundary + real entrypoint + logical clock + observed wall clock
input/output refs and hashes; actor kind; injected fault point
source identity → experiment → decision → strategy → epoch → attempt/position
returned status AND independent persisted-state readback
oracle assertion/result; fidelity; bridge IDs; terminal/resume marker
```

Не хранить токены доступа, private endpoints, реальные wallets/customer data; не требовать скрытых рассуждений модели. Большие bodies — отдельно с hashes; в отчёте только существенные excerpts.

Каждый выполненный сценарий имеет воспроизводимую команду, environment fingerprint и сравнимый observed outcome. Для nondeterministic ordering нужны barriers/schedule/actual interleaving, а не один seed. Original actor transcript сохраняется; replay transcript не считается новым genuine discovery.

До/после кампании подтвердить отсутствие product-code mutation и выхода за owned roots. Не нужно читать реальные sensitive stores ради красивого «no changes»: их отсутствие в разрешённой среде и проверенные access barriers — основное containment evidence.

## 18. Coverage и verdict без ложной зелени

Freeze denominator до wide sweep: material obligations + selected scenarios + exclusions. Добавления — append-only revision; failures не уменьшают знаменатель.

Для каждого obligation учитывать `reached`, `oracle_exercised`, `consumer_accepted`, result и fidelity. Guard отказался корректно — PASS самого guard; положительная downstream достижимость при этом остаётся BLOCKED/UNVERIFIED.

Отдельные оси итогового readout:

| Ось | Что именно оценивается |
|---|---|
| DISCOVERY | Какие hidden families реально найдены, authored, grounded и сохранены; результаты всех genuine trials |
| CONTINUITY | Последняя FULL граница от Forge ingress; все rescue cuts и правые SEGMENT результаты |
| OPERABILITY | PAPER loop, admission, old exits, recovery и operator readback в tested synthetic среде |
| SCIENTIFIC_BOUNDARY | Какие accepted protocols действительно вызваны; какие остаются gap; real-market evidence = NONE |
| SAFETY | No production/provider/money actions и проверенная isolation; нарушения invalidate зависимые результаты |

Campaign status: `COMPLETE_VERIFIED_SCOPE`, `COMPLETE_WITH_FINDINGS`, `PARTIAL_PRODUCT_BLOCKED`, `PARTIAL_ENVIRONMENT_OR_AUTHORITY`, `PARTIAL_BUDGET_BOUND`, `INVALID_HARNESS`. Это статусы аудита, не торговой readiness.

`COMPLETE_WITH_FINDINGS` допустим, когда вся agreed проверка выполнена и failures доказаны. Недостигнутый обязательный native long path отдельно остаётся BLOCKED; завершённый отчёт не делает его PASS. Полный список tests никогда не заменяет coverage этой матрицы.

## 19. Findings и диагностическая глубина

По успешной области: одна строка outcome/fidelity и evidence refs. Подробный текст — для проблем, uncertainty и material limitations.

Каждый material finding содержит:

```yaml
finding_id: SLS-F-001
classification: PRODUCT_DEFECT | CONTRACT_GAP | MISSING_PRODUCT_SEAM |
                AGENT_BEHAVIOR_GAP | OBSERVABILITY_GAP | HARNESS_DEFECT | COVERAGE_GAP
severity: <current project taxonomy>
violated_obligation: <ID and source contract>
first_broken_boundary: <producer -> consumer>
expected: <observable source-backed outcome>
actual: <readback, not only log>
reproducer: <exact executed command + fixture/schedule fingerprint>
evidence: [<trace>, <state diff>, <oracle>, <consumer readback>]
fidelity_and_bridges: <exact>
root_cause_status: SUPPORTED | HYPOTHESIS | UNKNOWN
impact: <which owner outcome breaks>
repair_outcome: <minimal desired capability>
closure_check: <same path + independent oracle>
```

Различать bad fixture, product violation, честный научный отрицательный результат, отсутствующий accepted protocol и недоступную среду. Если контракт проверяет только presence evidence, нельзя приписывать ему отсутствующий statistical decision engine и объявлять любой нежелательный verdict implementation bug; это может быть semantic/capability gap.

Дедуплицировать по earliest broken owner/invariant. Один root seam с пятью симптомами — одно основное исправление. Severity выводить из реального impact/reachability, не называть каждый непокрытый тест P1. Сохранить все неудачи; не переписывать прежний audit verdict новым удачным запуском.

## 20. План выполнения одного bounded atom

| Этап | Действия | Достаточный checkpoint |
|---|---|---|
| P0. BIND | Current Git/authority/routes, existing reuse, actual actor isolation, exact ingress/egress; проверить raw→episode→runtime и scientific successor | Filled bindings; START/PATCH/SPLIT/BLOCKED; узкие gaps; audit write set |
| P1. PREPARE | World recipe и hidden oracle, native fixture schema, allowed synthetic policy, partitions, сценарии, safety/canaries | Невакуумный positive seam; исправный oracle; sealed benchmark; frozen denominator |
| P2. DISCOVER | Genuine blind positive/transfer/null trials, обычный Forge lifecycle, saved outputs/charges/critique | Family-level results всех trials; candidate artifacts или earliest blocker |
| P3. ADVANCE | Native experiment/decision/handoff; actual PAPER spine; при gap — declared rescue; короткий второй strategy path | Trace достижимости до правой границы и все bridge disclosures |
| P4. BREAK/RECOVER | S05–S14 targeted variants, actual child crash/WAL/unknown/restore, selected interactions | Проверенные разрешённые и запрещённые outcomes либо точные blockers |
| P5. HANDOFF | Reproduce/shrink material failures, coverage из ledger, owner report, один NOW repair, scoped cleanup | Проверяемый kit и replay; остатки не спрятаны; точный resume при partial |

Не делать отдельный owner gate между P0–P5. Phase checkpoints — механизм восстановления и контроля полноты, а не серия просьб «продолжать?». Не выпускать PR только с планом вместо согласованной audit campaign. Возможен SPLIT исполнения по ресурсам, но campaign identity, coverage и конечный outcome общие; несколько delivery PR — только по реальной policy/size boundary.

При первой невозможности связать path не проводить бесконечную археологию. Проверить owner + implementation + один existing proof; сохранить root gap и идти к безопасным независимым сценариям/segment. Новый accepted scientific protocol в этой кампании не изобретать.

## 21. Budget, остановки и degrees of freedom

Ресурсные числа ниже — **предлагаемые ceilings для audit contract**, не обещание продолжительности и не разрешение расходовать деньги. Более строгая current authority сохраняется.

| Ресурс | Default plan |
|---|---|
| Generated base world | 320 unique mint; при unmet legal preconditions до benchmark freeze — до 1280 целыми сбалансированными blocks |
| Genuine Actor | 3 positive + 1 null mission; Critic по штатному protocol; без best-of-N и новых entitlement |
| Дополнительные stateful sequences | Только после основной матрицы и при новом coverage; начальная партия до 12, суммарно до 36 |
| Product execution | Existing environment; ориентир 2–4 CPU, до 4 GiB RAM, до 2 GiB retained evidence; снизить по measured need |
| Compute watchdog | Bounded per-process deadline и общий product-run cap, например 120 активных минут; exact значения связать после малого preflight, до wide run |
| Real market/provider/chain calls | 0 |
| New paid API/dependency/platform | 0; отдельно разрешённый существующий model transport не даёт product egress |
| Product fixes / real state writes | 0 |

Generator expansion не заменяет genuine trial budget. Invalid harness attempt сохраняется; rerun допускается после исправления его причины. Product/scientific failure не даёт бесплатную повторную попытку или новый focus. Synthetic attempts отделены от real scientific ledger физически, но внутри своего мира учёт не выключается.

Адаптивный probe нужен только для нового material edge, различения причин или closure реального failure. Если всё selected достигнуто и classified, остановиться. Если envelope исчерпан — checkpoint и честный PARTIAL, не урезание denominator. При обнаружении contamination остановить затронутые lanes, сохранить evidence; не исправлять реальные данные.

### Исполнитель свободен

Выбирать layout kit, existing unittest/runner, JSON/YAML, source adapters, точные compatible points, neutral IDs, минимальный scale, fault barriers, количество полезных replay и форму короткого отчёта. Можно заменить 320 на другой размер при сохранении factorial balance и freeze provenance. Можно использовать одну функцию/сценарий вместо нескольких, если сохраняется evidence.

Нельзя незаметно менять задачу на unit-only tests, выбирать неподдержанную гипотезу, маскировать новые data/science permissions, снижать guards, писать отсутствующий product seam, заводить новый сервис, передавать Actor oracle или выбирать лучший из скрытых attempts.

MODEL_EFFORT_RECOMMENDATION: `SOL_XHIGH` для initial binding, PIT/science/lineage и root-cause анализа; обычное создание fixtures/отчёта — на выбранном клиенте без постоянных переключений. Это проектный effort label, не требование приобрести конкретную модель.

## 22. Артефакты, durable truth и rollback

Одна компактная возможная структура; exact placement следует текущему repo contract:

```text
<scoped-audit-root>/
  campaign.json              # bindings, obligations, scenario/world fingerprints
  world_recipe.*             # builder-only during blind trials
  runner_or_existing_tests   # native entrypoints, controlled world, observers
  attempts.jsonl             # authoritative execution ledger
  coverage.json              # derived
  findings.jsonl             # deduplicated backlog
  OWNER_REPORT.md             # first screen + details only where needed
  REPLAY.md                   # actual verified commands
  CHECKPOINT.md               # only for interrupted/partial work
```

Предлагаемый Git scope: новая task contract, `tests/fixtures/synthetic_lifecycle_smoke_v1/**`, при material regression один существующий/новый test module, `docs/evidence/synthetic_lifecycle_smoke_v1/**`, один report/replay route. Catalog/navigation меняются только для реально нового durable entrypoint и через штатный generator. `src/**`, production configs/schemas/registries и kernel по умолчанию вне write set.

Большие runtime DB/logs — вне Git с hashes и retention refs. Durable — compact recipes, exact source pins, meaningful failed/passed receipts, воспроизводимые команды и diagnosis. Private oracle может быть сохранён после campaign; будущие Actor trials всё равно не получают доступ к нему или истории. Не коммитить ответы в путь, который future Actor автоматически читает.

Rollback audit kit — удалить/отключить только новый test entrypoint по обычной Git policy. Cleanup runtime — только exact owned PIDs/roots/containers после сохранения evidence. Не deleting branches/history, shared cache, `.venv`, реальные datasets или чужие backups. Synthetic StrategyVersion не попадает в active production catalog. Старые reports/negative evidence не переписываются.

## 23. Definition of Done и формат handback

### 23.1. Приёмка кампании

- Current bindings, scope, isolation, clocks и actor fidelity доказаны или имеют точный узкий blocker; нет guessed API вместо required route.
- Positive world прошёл native input validation и independent oracle; expected был frozen до actor/actual outcomes.
- Simple/compound assessed отдельно по всем planned trials. Scripted/unblinded результат не засчитан как blind discovery.
- Все S00–S14 accounted; каждый material transition имеет observed evidence либо explicit FAIL/BLOCKED/UNKNOWN. Недостигнутый N9 не называется readiness.
- Native last full boundary показана. Rescue cuts, manually authored science fixtures и потерянные producers перечислены; descendants не повышают fidelity.
- Обычный PAPER runner, законные отказы, old exits, UNKNOWN и recovery проверены в максимально достижимом scope, а не только direct internal calls.
- Material findings имеют actual replay, oracle, before/after, root-boundary classification и acceptance для repair.
- Нет production mutation/provider/money/secret actions. Cleanup не уничтожил forensic evidence.
- Coverage/readout воспроизводятся из ledger. Пустая или усечённая campaign не даёт PASS. Report не выдаёт modeled PnL за NetReturn/FCF.
- Semantic navigation обновлена только по реальному impact; обязательные review/CI/merge gates сохранены. Ноль новых tests допустим, если existing checks действительно закрывают новые material claims; число tests не является DoD.

### 23.2. Первая страница OWNER_REPORT

```text
VERDICT: <campaign status>
PRODUCT REF / WORLD REF / ACTOR: <exact scope>

Обнаружение: SIMPLE <по trial>; COMPOUND <по trial>.
Настоящий полный путь: <откуда → последняя verified boundary>.
Дальше проверено сегментом: <cut, причина, достигнутый consumer>.
PAPER: <activation / admitted / opened / exited / reconciled, exact scope>.
Главный риск: <конкретное wrong behavior или существенный UNKNOWN>.

NOW: <один bounded repair outcome + почему первым>.
WATCH: <один trigger, не список будущих проектов>.

Реальные данные / alpha / live readiness / FCF: не проверялись.
```

После первой страницы — небольшая таблица «контур / outcome / fidelity / evidence», подробные findings, uncovered и replay. Сотни log lines в основной текст не переносить. Для нормальной области достаточно конкретного «что прошло», без многостраничного success narrative.

При partial handoff дополнительно: goal/scope/mode; product and world hashes; spent budgets; complete/invalid attempts; bridge/gap ledger; safety/cleanup state; exact следующая исполнимая команда или одна реальная owner boundary. Возобновление не перечитывает весь repo и не сбрасывает attempts.

---

# 24. Основания и provenance

## 24.1. Source policy

Этот документ самодостаточен для design intent и audit requirements. Current `AGENTS.md`, semantic owners и schemas при execution определяют фактические пути и authority. Приложенный Portable Audit использован как методическая основа; не требуется читать его ещё раз целиком, чтобы исполнить эту специализацию.

Факты ниже — read-only design binding на commit `94b391d658b52035ae88e2da05f1ea25ff17b0f8`, полученный 14 октября 2026. Product/runtime tests в подготовке документа не запускались. Чтение contracts и test harness code не доказывает live health или closure их DoD.

| Ref | Источник в `lancerbeta/solana-alpha-lab` | Что заимствовано |
|---|---|---|
| G01 | `AGENTS.md`; `delivery-harness/harness.yaml`; `delivery-harness/project-profile.yaml`; `delivery-harness/policies/solana-alpha-lab.md` | Mode, bounded authority, validation economy, effort, delivery boundaries |
| G02 | `docs/FACTORY_SEMANTIC_MAP.md`; `catalog/catalog_manifest.yaml`; `delivery-harness/context-map.yaml` | Semantic routes и current owner bindings |
| G03 | `.agents/skills/hypothesis-forge/SKILL.md`, прочитанный ordinary/raw-composite раздел | Manual fallback, native authoring, runtime policy, cold readback |
| G04 | `docs/contracts/forge_native_lifecycle_closure_v1.md`; `docs/contracts/forge_ordinary_operation_lifecycle_v1.md` | Authored meaning before MAIN, genuine contexts, immutable execution, monotone completion |
| G05 | `docs/contracts/forge_composite_feature_recipes_v1.md` | Raw operators/units, joint support, PIT, supported refusal, native proof locator |
| G06 | `docs/contracts/experiment_evidence_decision_v1.md` | DIRECT/RELATED, scientific obligations, stale decision, WAL-aware readback |
| G07 | `docs/contracts/science_to_strategy_handoff_v1.md` | Handoff manifest, explicit execution inputs, v1.1 strategy, materialization≠activation |
| G08 | `docs/reports/forge_trust_closure_v1/SCIENTIFIC_DECISION.md` | BAA-003 disposition C только для названного List A recipe |
| G09 | `docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md` | Ordinary run, synthetic clock, current controls/backup/recovery, modeled claim limits |
| G10 | `docs/contracts/episode_decision_continuity_v1.md` | Episode recipe/runtime compatibility, shared semantics, ordinary vs legacy behavior |
| G11 | `scripts/prove_trading_core_operational_closure.py`, строки 1–150 | Реальные runner/coordinator, suites, lowest quote transport, external ledger |
| G12 | `docs/reports/big_agentic_audit_v1/REPORT.md`; `docs/tasks/BIG_AGENTIC_AUDIT_V1.md` | Старый partial baseline, исходные failure types, ограничения старой campaign |
| G13 | `tests/test_big_agentic_audit_v1.py` | Existing empty/unvisited/truncated/aggregation oracle controls |
| G14 | `configs/experiment_capability_registry_v2.yaml` | Accepted capability enumeration; fixed-time proxy не является самостоятельным promotion authority |
| G15 | Поисковые excerpts task/completion `I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1` | Collector provider-account budget не путать с Trading envelope; детальный аудит I3 не проводился |

Дополнительные source locators для исполнителя опубликованы самими прочитанными owners; их точное содержимое нужно разрешать на execution ref, а не считать все такие файлы уже проверенными этим проектированием.

## 24.2. Приложенные материалы

`BIG_AGENTIC_AUDIT_PORTABLE_V2` из файла `Вставленный текст(20261013-215916).txt`, SHA256:
`aa7191bfc7218050476e6c6c4adf42499da0b7916ff3de9302408e74abd20a9d`.

Сохранены его существенные принципы: mock external world, real product paths; frozen denominator; independent oracle/readback; FULL≠SEGMENT; genuine actor отдельно от scripted; audit-only без product repair; воспроизводимый root-boundary backlog. Специализация здесь добавляет hidden planted mechanisms, закрытые temporal partitions, конкретные SMIAL seams и bounded PAPER/recovery scope.

Пять project sources 01–05 использованы для mission/roles/truth/operability и scientific anti-claims. Их старые фиксированные horizon/age формулировки не расширяют текущий user kernel: конкретные горизонты задаются данными, гипотезой и frozen experiment; источники не владеют текущим runtime.

## 24.3. Проверенные внешние первоисточники — метод, не зависимости

- **E01 — Anthropic, “Demystifying evals for AI agents”**, 9 января 2026; проверен 14 октября 2026. Различение task/trial/trace/outcome, fresh trials, grading по состоянию среды и баланс positive/negative. Использован принцип; числа этой кампании — собственный design, не industry standard. URL: `https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents`.
- **E02 — TigerBeetle, Deterministic Simulation Testing / VOPR**, проверен 14 октября 2026. Настоящий production code при управляемых внешних условиях и ускоряемом времени. SMIAL не получает от этого полную детерминированность concurrency/LLM. URL: `https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/internals/vopr.md`.
- **E03 — Antithesis, Asserting correctness**, проверен 14 октября 2026. Reachability и positive witness не позволяют принять непосещённый безопасный путь за доказанный. SDK/SaaS не предлагаются. URL: `https://antithesis.com/docs/product/writing_tests/assertions/`.
- **E04 — Hypothesis, Stateful tests**, проверен 14 октября 2026. Полезные sequences действий и invariants между шагами; библиотека не требуется для нескольких ручных targeted scenarios. URL: `https://hypothesis.readthedocs.io/en/latest/stateful.html`.

Параметры synthetic world, scoring grid, сценарии, budgets и порядок P0–P5 — проектные рекомендации этого документа. Они не представлены как рыночные факты или обязательный стандарт отрасли.

# 25. Команда для передачи исполнителю

> Выполни `SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1` по этому файлу как один bounded audit-only atom. Сначала перепривяжи current Git/authority/semantic owners и проверь exact native seams; затем подготовь и исполни изолированную synthetic campaign. Используй genuine blind Actor для поиска hidden simple/compound patterns и настоящие product producers для lifecycle. Ускоряй внешний мир и время, не внутренние решения. При непреодолимом scientific/product gap сохрани earliest blocker и проверь правую часть через объявленный SEGMENT, не выдавая её за FULL. Reuse существующие Big Audit и Trading proof-опоры. Продукт не ремонтируй, реальные данные/системы/провайдеры/деньги не трогай. На выходе — replayable kit, coverage/readbacks, подробные material findings, короткий owner report и один NOW repair. Без пауз на безопасных инженерных шагах; actual authority, budget, exact-head CI и merge gates сохраняются.
