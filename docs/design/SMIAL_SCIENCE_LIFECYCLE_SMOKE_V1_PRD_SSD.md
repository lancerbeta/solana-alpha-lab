---
design_id: SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1
version: '1.0'
status: DESIGN_COMPLETE_NOT_EXECUTED
mode: DESIGN
as_of: '2026-10-14'
expected_repository: lancerbeta/solana-alpha-lab
planning_main: fbac5449f6dd22a7bc066114109be8bbed830447
prerequisite_repair: EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1
prerequisite_pr: 403
origin: SYNTHETIC_LIFECYCLE_AUDITS_401_402_AND_REPAIR_403
recommended_model_effort: SOL_XHIGH
execution_scope: SYNTHETIC_AUDIT_ONLY_AFTER_EXPLICIT_OWNER_COMMAND
product_mutation_authority: NONE
real_market_scientific_authority: NONE
production_runtime_authority: NONE
external_spend_authority: NONE
---

# Science Lifecycle Smoke V1 — PRD + SSD + практические указания исполнителю

## 0. Решение и результат для владельца

**Проверяем оставшийся научный участок на синтетике: от сохранённой готовности Spec 1.4 до реального численного результата, его сохранения и использования следующими потребителями. Отдельно устанавливаем, существует ли исполнимый переход к независимой chronological validation.**

Это продолжение audit → finding → repair → verification, а не повтор большого аудита Кузни и торговли. Данные реального коллектора не нужны. Изменять продукт, научные пороги или разрешения ради успешного сценария нельзя.

После кампании владелец должен получить четыре ясных ответа:

1. Выполняет ли настоящий runner численный расчёт по native episode recipe, а не только принимает его описание или возвращает готовый результат?
2. Верны ли числа, identity, denominator, сохранение, повтор и восстановление — и видит ли это обычный owner dossier?
3. Может ли система принять заранее замороженный вопрос и новые хронологически последующие данные как отдельную проверку, не выдавая discovery/replay за подтверждение?
4. Где заканчивается работающий маршрут: из-за дефекта, отсутствующего producer/contract, корректного научного отказа или ограничения самой проверки? Какой один ремонт нужен следующим?

**Главная поправка к прежней рекомендации:** в прочитанном Git уже есть основания ожидать, что численный replay исполним, а подтверждающий episode producer ещё не реализован. Поэтому нельзя заранее обещать полный положительный OOS-путь. Но нельзя и сдать эту кампанию одним повторением известного `BOUND_CONTRACT_NOT_READY`: численный маршрут и его downstream необходимо действительно проверить либо воспроизвести новый конкретный blocker.

### Три линии одной кампании

| Линия | Обязательный результат | Чего она не доказывает |
|---|---|---|
| **A. Numerical execution** | Настоящий Spec 1.4 → DocumentRunner → evaluator → result/passport/store → cold readback; точный независимый численный oracle | Новую независимую научную попытку, OOS, рыночный эффект |
| **B. Chronological continuation** | Проверенный producer/consumer для нового source-bound подтверждения **или** точная доказанная граница его отсутствия; динамические проверки — только достижимого участка | Что три набора данных автоматически образуют accepted validation |
| **C. Evidence → owner decision** | Настоящие результаты A, а при наличии B — и B, читаются штатным dossier; claims и разрешённые решения не усиливаются без оснований | Что наличие DIRECT records или заполненных полей означает научную истинность |

Успешный итог аудита может включать `A=PASS`, `B=PRODUCT_OR_CONTRACT_BLOCKED`, `C=PASS_WITH_EXPECTED_PROMOTE_BLOCKED`. Это полезный проверенный результат, но не `FULL_SCIENTIFIC_LIFECYCLE`.

## 1. Основание и актуальность

### 1.1. Проверенный planning snapshot

Репозиторий: `lancerbeta/solana-alpha-lab`.

`main` на момент планирования: `fbac5449f6dd22a7bc066114109be8bbed830447`, merge PR #403. Проверенный head самого ремонта: `c1b5bf3cde53e7a43b7640beb5390e39cdc97932`. Это provenance, не требование откатить checkout. При запуске исполнитель заново связывает campaign с текущими Git owners и фиксирует drift.

Источники S01–S16 перечислены в §20. Факты ниже основаны на чтении кода/контрактов и сохранённых evidence; автор этого плана не запускал продуктовые тесты или runtime.

| Подтверждённое | Последствие для smoke |
|---|---|
| #403 добавил version-isolated Spec 1.4 для native `REUSE_ONLY / EXPLORATORY_REUSE`; прежние схемы не стали episode-схемами | Primary path только 1.4, без отката к 1.1 и без E→X/Y |
| Проверен persisted HFIC READY/BLOCKED, но настоящий численный `start_document` в успешном случае не запускался | Линия A должна впервые закрыть именно этот проход, не повторять helper-only proof |
| `run_temporal_fixed_time_from_spec` вызывает настоящий temporal evaluator, но возвращает `status=COMPLETE`, `terminal=INCONCLUSIVE`, `labeled_net_return=false` | Правильные положительные числа совместимы с INCONCLUSIVE; требовать PROMOTE от этой capability неверно |
| Spec 1.4 direct handoff связывается с завершённой HFIC session и exact frozen recipe; `_frozen_hfic_replay_lineage` возвращает `FROZEN_EVIDENCE_REPLAY` и `new_scientific_look=false` | Реальный пересчёт есть, нового научного подтверждения нет; технические исполнения и scientific looks считаются отдельно |
| Capability `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001` зарегистрирована как offline `RESEARCH_ARTIFACT`, `promotion_authority=NONE` | Нельзя получить scientific authority из названия «experiment» или из successful run |
| List A protocol — `DESIGN_VALIDATED_BOUND_CONTRACT_NOT_READY`; sample binding UNBOUND, future execution требует reservation до values и отдельного producer | Проверить существование этого producer до генерации большого validation-корпуса |
| В List A contract generic DocumentRunner RUN_STARTED после capability прямо не считается pre-values gate | Audit-log или поздняя запись RUN_STARTED не заменяют научную reservation |
| Dossier разделяет execution, scientific evidence и decision; `RUN_COMPLETED` не закрывает научные obligations | Линия C проверяет эту границу на результате реального A-run, а не на вручную созданном успешном RUN |

### 1.2. Что нельзя наследовать из прошлых проходов

Сохранённые KILL обоих аудитов не отменяются. Scripted Critic ремонта не становится genuine scientific acceptance. PAPER/reconciliation из BR-01 остаётся отдельным trading-сегментом. Старые allocations — исторические замеры, не размер нынешней среды. Из наличия Spec 1.4 не следует существование accepted chronological runner или готовность реальных когорт.

**UNVERIFIED до выполнения:** успешный численный путь Spec 1.4; соответствие его результата независимой арифметике; реальные crash/resume-свойства этого пути; применимый chronological producer; автоматическая содержательная передача qualifying evidence; health живого коллектора и состояние production.

## 2. Owner outcome, scope и authority

### Desired capability

> В изолированной искусственной среде реальный научный контур либо исполняет разрешённый маршрут с верными результатами и читаемым состоянием, либо точно показывает отсутствующий переход. Ни тест, ни агент не могут незаметно достроить этот переход или повысить силу научного вывода.

**Начало:** валидный native frozen recipe, связанная HFIC session и Spec 1.4, получивший законную классификацию. Вход допускается подготовить existing native fixtures и scripted Critic. Это объявленная граница теста, не проверка способности LLM найти alpha.

**Конец A/C:** реальный numeric artifact + committed run/passport + ordinary dossier + разрешённая synthetic PAUSE/REJECT и правильный запрет необоснованного PROMOTE.

**Расширение B:** независимое chronological подтверждение того же estimand только через реально существующие и принятые product entrypoints. Если их нет, конец B — exact consumer/contract gap, не новый test-only confirmer.

### Разрешено после команды из §19

- Создать один bounded audit task, test-only runner/fixtures/oracles, campaign manifest, compact evidence и report.
- Читать canonical Git; использовать existing locked runtime и native тестовые producers.
- Создавать и читать только принадлежащие campaign synthetic data/stores; исполнять численные расчёты по этим данным. Fixture MAIN looks заранее ограничиваются и учитываются.
- Через штатные методы записывать synthetic classifier/run/result/decision records в отдельный disposable store. Пробовать PROMOTE только как отрицательную проверку на заранее недостаточном dossier; успешный PROMOTE не является целью кампании.
- Воспроизводить сбои owned процессов, изолированную недоступность файлов, потерю ответа и перезапуск. Исторические результаты остаются нетронутыми.
- Исправлять свой audit kit с сохранением invalidated attempts. Routine Git delivery — только по current repository policy и exact write set.

### Не разрешено

Product source/production contracts/schema/registries/guards/thresholds менять нельзя. Также запрещены real data/holdout reads, provider/API/RPC/WSS, grants/credentials, purchases/dependencies, deployment, VPS-операции, signer/wallet/transactions, StrategyVersion/activation/PAPER и любые реальные деньги. Нельзя изменять labels настоящего source, расширять universe, повторно открывать реальные научные попытки или удалять прошлую audit history.

Подмена future source на новый identity при том же просмотренном evidence не освобождает scientific budget. Новые model/prompt/session имена не создают untouched sample.

**Protected gates:** actual external authority, новый scientific protocol/estimand, product repair, merge, destructive action. Audit-only полномочия не обходят machine DENY. Недоступность B не блокирует безопасные A/C.

## 3. Почему выбран именно этот подход

**Выбран:** небольшой risk-weighted vertical smoke с настоящими producers/stores, фазовым доступом к данным, независимыми numeric/membership oracles и точным учётом границ.

Не выбран повтор Forge→Trading: он в основном повторит уже проверенное и расходует время на discovery/LLM/торговую среду. Не выбран «всё замокать и получить PROMOTE»: такой тест подтвердит связность собственных заглушек. Не выбран немедленный build chronological engine: существование/отсутствие потребителя сначала должно быть установлено; новый метод и production implementation требуют другого атома.

Технический default: Python/unittest, уже установленные библиотеки продукта, native SQLite/Parquet/JSON, один owned worktree и local runner. Docker только если существующий проверенный образ реально упрощает изоляцию. Ни новой платформы тестирования, ни сервиса, ни очереди, ни universal simulator.

**Обязательное различие:** проверка арифметики, проверка протокола и проверка существования рыночного эффекта — три разных результата. Даже полностью пройденный synthetic protocol не калибрует его статистическую надёжность на реальном рынке.

## 4. Repository binding и минимальная reconnaissance

Начать с `AGENTS.md`, current delivery profile/policy и semantic routes:

- `SEM-EXPERIMENT-CAPABILITIES` — capability registry и принятые entrypoints;
- `SEM-HYPOTHESIS-FORGE` — frozen session/recipe и native handoff;
- `SEM-OWNER-LIFECYCLE` — dossier и decision consumer;
- `SEM-AUTHORITY-BOUNDARIES` — exact scope/gates.

Не читать все tasks и историю. Ни «самый свежий файл», ни строка `status: READY` в чужом task не выбирают эту работу.

### Конкретные владельцы и точки проверки

| Узел | Текущий owner / вход | Что фиксируется |
|---|---|---|
| Spec | `factory/experiment_spec.py::validate_experiment_document`, schema 1.4 | Exact document, canonical spec hash и отдельный file hash |
| HFIC state | `hfic_session.py::load_session_bundle`, `run_live_classifier`, `apply_classification` | Session/candidate/definition/packet/recipe identity, saved terminal |
| Classifier | `lane_classifier.py::classify_lane` | Real `LaneDecision`, run key, current protection, binding receipt |
| Numeric run | `document_runner.py::DocumentRunner.start_document`, `RunContext` | Не helper-only; actual dispatch, result, passport, commit |
| Capability | `capabilities.py::execute_capability` → `hfic_temporal_discovery.py::execute_fixed_time_proxy_capability` | Реальный registry dispatch; evaluator действительно вызван |
| Frozen source | `bind_frozen_fixed_time_inputs`; `episode_required_outcomes.py::verify_frozen_episode_sources` | Frozen/current protection, manifest/release/schedule/census/obs binding |
| Selection/числа | `hfic_research_scope`, `opportunity_episodes.resolve_point`, `hfic_temporal_discovery` | Native IDs, D/M/C, clocks, formula, masks |
| Durable truth | `ResearchStore`, native run-passport validation | Records и результат после завершения исходного процесса |
| Owner consumer | `compose_experiment_dossier`; `FactoryApplication.research_detail` / `record_research_decision` | Execution/evidence/decision раздельно, lineage и отказ/запись |
| Chronological | `list_a_chronological_confirmation_v1.md` + `.yaml`; registry и exact candidate producer | ACCEPTED executable или точная missing boundary, не фантазия о CLI |

Указанные symbols проверены при планировании. Constructor wiring, CLI flags и exact test setup исполнитель берёт из текущих examples/tests, не из догадки.

Зафиксировать один binding record: base/head, relevant source blob hashes, runtime/version, task write set, выбранные entrypoints, evidence refs #402/#403, доступные retained fixtures, invalidated reuse, known gaps.

**Entry:** `START` при наличии #403 и безопасной среды; `PATCH` при локальном drift путей без смены смысла; `BLOCKED` только для зависимого unsafe/unavailable участка; `SKIP_WITH_EVIDENCE` только при exact применимом доказательстве. Если #403 уже изменён следующим ремонтом, проверить затронутые owners; не проверять старый код под новым заголовком.

## 5. Reuse: что переиспользовать и чего не повторять

Основной reuse surface:

- `tests/fixtures/episode_native_required_outcomes_v1/proof.py`: `prepare`, `load_case`;
- `tests/test_episode_native_required_outcome_contract_v1.py`: native HFIC persistence, current protection и ReaderOracle как исходный шаблон;
- `tests/test_hfic_list_aware_vertical_v1.py`: synthetic market ingress и native capture/import;
- `tests/test_hfic_temporal_production_runner_v1.py`: numerical runner setup;
- `tests/test_fast_lane_runner.py`: runner wiring/replay/failure seams;
- `tests/test_experiment_evidence_decision_v1.py`: ordinary dossier/decision surface.

**Сначала inspect/reuse существующей retained среды**, если её exact fingerprint доступен. Чистый тестовый clone mutable store допустим. Старый store не изменяется и не «чистится от лишних RUN», чтобы вызвать evaluator ещё раз.

Для первой успешной numerical invocation нужен specimen без завершённого DocumentRunner run с этим exact key. Если exact run уже существует, использовать честно зарегистрированный новый synthetic fixture либо зафиксированный pre-run snapshot; не удалять запись, не менять один experiment_id ради обхода replay и не выдавать повтор за первое исполнение.

Числовой oracle старого #403 мира слишком симметричен для новой цели: положительные targets там могли совпадать у всех групп. Для обнаружения перепутанного comparator/знака нужен один **несимметричный** небольшой мир (§7). Это оправданная новая fixture, не повтор discovery campaign.

Не запускать заново 16+84 проверок только ради числа. Использовать применимое exact-candidate evidence для старой границы. Новые checks покрывают новый numerical/downstream риск. Старые тесты запускать лишь там, где они дают независимый контроль конкретного сомнения.

## 6. SSD: среда, роли и фазовые права чтения

### 6.1. Минимальная конструкция

```text
one campaign manifest + frozen oracle specification
          │
          ├── registered synthetic ingress / immutable released sources
          ├── scenario + process-fault schedule
          ▼
real Spec/HFIC/classifier → real DocumentRunner/evaluator
          ▼
real result artifact + ResearchStore/passport
          ▼
fresh-process observer → ordinary dossier → synthetic owner decision

separate conditional branch:
frozen question/protocol → new approved sample binding → pre-values reservation
→ actual chronological producer → substantive evidence → dossier
```

Builder, driver и observer — логические роли; три LLM-процесса не требуются. Driver — детерминированный audit script. Genuine blind Actor и проверка «ума Кузни» вне scope. Scripted Critic допустим на входе A: он задаёт состояние перед проверяемым численным участком, но не засчитывается как scientific acceptance.

### 6.2. Containment

Один owned root; source code read-only во время product run, writable только campaign stores/output. Отдельные HOME/TMP/config, отсутствуют real production roots/keys/credentials. Product egress запрещён; loopback допустим только для local Workbench. Никаких background collectors/watchers, mounts реальных data roots и внешних callbacks.

Если native host runtime проще Docker, достаточно технически ограниченного дочернего процесса/аккаунта с проверяемыми file/network правами. Prompt-запрет сам по себе containment не доказывает. Если надёжная среда недоступна — `BLOCKED_ENVIRONMENT`, не «осторожный запуск на рабочем RDP».

Canaries до product run: harmless запись вне allowed root отказана; внешнее обращение отклонено до provider; child наследует ограничения; источники и неизменяемые файлы не затронуты. Не тестировать безопасность реальной опасной транзакцией.

### 6.3. Read permissions зависят от фазы

| Фаза | Допустимо | Недопустимо |
|---|---|---|
| Metadata / route probe | Разрешённые IDs/hashes/roles/clocks и structural support; opaque hash отдельно от semantic decode | Открыть unseen outcomes/coverage ради поиска удобного validation sample |
| Classify / fresh action revalidation 1.4 | Native prefix values и metadata требуемых outcomes explored source по его контракту | Future target numeric values; считать metadata readiness OOS acceptance |
| A numerical execution | Численные значения **exact frozen explored sources** через native evaluator | Чужой/withheld corpus; новый adaptive look; выдавать replay за untouched evaluation |
| A completed replay action | Необходимая current source/protection revalidation, включая штатные prefix reads | Повтор target evaluator; новые scientific charges/duplicate logical completion |
| Historical readback | Сохранённые receipts/artifacts через обычный reader | Новый target evaluation, изменение scientific state |
| B до reservation | Только metadata, разрешённые accepted confirmation contract | Numeric targets, target coverage/scores, произвольный Parquet preview |
| B после accepted reservation | Только exact разрешённый validation scope в пределах frozen protocol | Адаптация query, замена источников, второй evaluator, reuse exploratory grant |

Старый ReaderOracle #403 запрещает **все** target reads. Его нельзя бездумно поставить вокруг numerical execution: там чтение targets является требуемым поведением. Нужен phase-aware observer. Не удалять защиту целиком: A-classify и A-replay по-прежнему не получают target evaluator.

В A существующий loader может материализовать более широкий набор колонок **внутри уже разрешённых frozen explored sources**. Это не доказательство точечного no-look reader и не OOS leakage само по себе. Для B действуют его отдельные более строгие правила; A bulk-loader нельзя автоматически признать безопасным confirmer.

## 7. Synthetic world A: маленький, но различающий ошибки

### 7.1. Базовая конструкция

Предпочтительно 24 native admissions, два разрешённых weekly cycles, как в #403: по 12 admissions в каждом. В каждом цикле 10 decision-eligible, два законно исключённых по prefix; admitted denominator всегда 24, D=20. Один mint встречается в двух допустимых циклах как два разных episode_id.

Для LIST_CONTRAST: M=10, C=10. Для MIXED_LIST_NUMERIC с существующим `MATCHED_VS_DECISION_ELIGIBLE`: M=10, C=D=20, overlap M/C законен. Numeric condition подобрать к уже используемому native fixture, не вводить новую feature grammar.

Query: native `OPPORTUNITY_EPISODES`, membership `EPISODE_T0`, anchor `NOMINATION_T0`, E1800→E14400, PRICE_RELATIVE_PROXY, `FIRST_RELIABLE_AVAILABLE_AT`. Номинальный интервал между точками 12 600 секунд, не 4 часа после входа. Реальные deadlines/assigned time считает только `resolve_point`.

**Изменяются только входные synthetic market values**, до capture/freeze. Не менять thresholds, admission quota, denominator, source publication labels или recipe после outcomes. Clock injection — existing test clock; системные часы машины не трогать. Все commissioning/import/freeze/as-of clocks должны быть внутренне последовательны; старые несогласованные даты fixtures не наследовать молча.

### 7.2. Независимая численная таблица

Decision PRICE = 1.00. Для пяти M и пяти C в каждом цикле задать следующие returns; outcome PRICE = 1 + return:

| Цикл | M returns | C returns | mean M | mean C | M−C |
|---|---|---|---:|---:|---:|
| A | .10, .11, .12, .13, .14 | −.04, −.03, −.02, −.01, .00 | .12 | −.02 | .14 |
| B | .06, .07, .08, .09, .10 | −.02, −.01, .00, .01, .02 | .08 | .00 | .08 |
| Pooled | 10 observations | 10 observations | .10 | −.01 | **.11** |

Pooled D mean = **.045**. Для MIXED comparator C=D native contrast = **.055**, а не .11. Эти два числа различают ошибочное подставление complementary comparator в numeric route.

Это expected price proxy, не NetReturn/FCF. Native cost/stress profile оставить явно заданным тем же recipe; его output проверять отдельно от raw proxy. Не приписывать модельному haircut статус измеренных trading costs.

Идентичности берутся из native admission. Независимый oracle связывает их с **заранее зафиксированными входными метками**, а не с product matched IDs. Таблицу expected сохранять до первого discovery look. Observer не вызывает production mean/contrast helper для получения expected.

### 7.3. Вариации без размножения кампаний

- **Numeric changed world:** в новом зарегистрированном мире с тем же prefix уменьшить каждый M-return на .20. LIST contrast должен стать −.09, MIXED contrast −.045. D/M/C и их identities в пределах соответствующего мира неизменны по роли; source hashes и numerical artifact изменяются. Старый мир не перезаписывать. Одинаковый hash результата при изменившихся числах — finding.
- **Missingness:** переиспользовать проверенный missing-target specimen #403 для executable refusal. Учитывать, что Spec 1.4 здесь требует 100% required coverage; 19/20 корректно блокирует runner. Не bypass classifier для получения числа на complete cases.
- **Fault overlays:** unavailable exact source, malformed receipt, current protection revoke, response loss — изолированные копии mutable store/owned filesystem faults. Полную native публикацию заново делать только если проверяется именно publication path.

Количество worlds не цель. Базовые LIST+MIXED и один numerical variation обычно достаточны для A. Если reuse exact fixture дешевле подготовки нового, использовать его, но не терять независимый asymmetric witness.

## 8. Линия A: настоящий численный проход

### 8.1. Непрерывная последовательность

1. Проверить native release/frozen candidate, exact recipe и текущую complete protection. `hfic_replay_session_id` включить в final Spec **до** его окончательной классификации/hash binding.
2. Через штатный HFIC path получить и сохранить classification. Не присваивать `LaneDecision` вручную. Scripted Critic — явно обозначенный upstream fixture.
3. Проверить отсутствие completed run для exact run key до первого numerical invocation. Зафиксировать предшествующие MAIN/preview/setup charges.
4. Вызвать настоящий `DocumentRunner.start_document` через существующий operator/CLI path, если он доступен без лишнего слоя. Прямой public application method допустим как product surface; private binder вместо runner — нет.
5. Observe реальный dispatch и evaluator; после вызова прочитать result artifact и committed RUN/passport, а не только returned `status`.
6. Проверить численный oracle, scope/identity/clocks, классификацию результата и source lineage.
7. Завершить исходный процесс. Новый процесс читает те же records/artifact и обычный dossier. Затем выполнить exact repeat и сравнить counters/state.

Ожидаемый текущий технический результат: `COMPLETE / INCONCLUSIVE`, source lineage `FROZEN_EVIDENCE_REPLAY`, `new_scientific_look=false`. Это **PASS A**, если evaluator действительно исполнился и independent numeric/state checks сошлись. Не пытаться «исправить» INCONCLUSIVE на SUPPORTED.

### 8.2. Низкоуровневый ориентир

Следующий фрагмент показывает связку существующих APIs, а не готовый standalone launcher. `runner` создаётся штатным fixture/application setup; driver обязан сохранять real store и traces.

```python
# Внутри уже изолированного audit process; spec/frozen из native producers.
validated = validate_experiment_document(spec, root=repo_root)
packet = {
    "experiment_spec": validated,
    "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
}
lane = classify_lane(packet, root=repo_root, data_root=owned_data_root, as_of=logical_now)
context = RunContext(
    data_root=owned_data_root,
    hypothesis_definition_sha256=packet["hypothesis_definition_sha256"],
    lane_decision=lane,
    classifier_evaluated_at=logical_now,
)
result = runner.start_document(
    validated,
    spec_sha256=experiment_spec_sha256(validated),
    run_context=context,
    capture_hooks={"data_root": owned_data_root},
)
# Следом: отдельный native store/artifact readback и сравнение с independent oracle.
```

`experiment_spec_sha256` — canonical semantic hash; YAML/JSON byte hash dossier и raw file hash — другие domains. Не подменять их друг другом и не менять сериализацию старых receipts.

Во время SC01–SC05 удерживать проверяемый Git HEAD неизменным: `runner_git_sha` участвует в run key. Не коммитить audit evidence между первым вызовом и его exact replay и не писать логи внутрь проверяемого Git root во время run. Evidence накапливается в owned output вне product snapshot и переносится в delivery после серии. Другой commit может законно дать другой run key; такой вызов не доказывает identical replay и не является сам по себе idempotency bug.

### 8.3. Что считать реальным доказательством расчёта

Нужны одновременно: ненулевой actual evaluator invocation; разрешённый target read в его фазе; результат с пересчитанными числами; result digest/manifest; committed passport; source recipe identity; fresh-process readback. `REPLAY_AVAILABLE` на первом вызове не закрывает numerical obligation.

Generated result не должен тащить `.venv`, локальные пути, fixture labels как научную identity, secret values или сведения другой кампании. Никаких manually written RUN_COMPLETED, passport или summary в этой линии.

## 9. Линия B: chronological validation без выдуманного producer

### 9.1. Сначала дешёвый capability probe

До создания длинного validation world найти для **этого** estimand:

- принятый protocol core и source-role policy;
- реальный public producer/entrypoint, принимающий frozen question и новый immutable sample;
- pre-values reservation/charge/exposure owner;
- native substantive result и consumer, который его использует;
- право synthetic execution в current task scope.

Registry entry `SCIENTIFIC_RESULT` не достаточен: canonical receipt replay может только воспроизводить готовое evidence. `verify_contract.py` из List A — evidence-only checker, не production confirmer. Generic DocumentRunner поздние RUN_STARTED/append также не pre-values reservation.

На planning snapshot применимый List A design существует, но его executable producer в прочитанных owners не показан; контракт прямо оставляет его реализацию на будущее. Проверить это по current Git/registry и реальным call sites один раз. Не превращать проверку в поиск по всему репозиторию без stop condition.

**Если producer отсутствует:** сохранить `MISSING_CONFIRMATION_PRODUCER` как **audit classification**, `native_terminal=null`, exact sources, ожидаемый input/output contract, недостижимую границу. Не приписывать этот придуманный audit tag продукту. Если entrypoint есть и сам возвращает blocker — сохранить его настоящий terminal/reason отдельно.

Не запускать низкоуровневый evaluator с вручную подменённым frozen_input, не создавать новую Forge MAIN по validation и не использовать foreign Critic packet для выдачи увиденных outcomes за untouched. Это не обход «мешающей бюрократии», а подмена проверяемого scientific path.

### 9.2. Три независимых blockers, которые нельзя смешивать

| Вопрос | Что доказывает/опровергает |
|---|---|
| Реализован ли producer/consumer? | Код, registry, public entrypoint и valid runtime probe |
| Подходит ли sample/достаточны ли данные? | Exact role, chronology, exposure, structural/actual support по accepted method |
| Разрешён ли запуск? | Current task/Science authority и machine gate |

Синтетика решает нехватку входных данных для технического теста, но не создаёт отсутствующий алгоритм или authority. `UNBOUND` sample не доказывает отсутствия producer; отсутствие producer не надо объяснять tiny N.

### 9.3. Условный positive chronological branch

Только если на старте существует применимый принятый producer и разрешённый native synthetic route, выполнить нижеописанную линию. Иначе scenarios B остаются BLOCKED_PRODUCT/CONTRACT, а не N/A, PASS или бесконечное «ждём данных».

**D, V1, V2 — логические datasets, а не число независимых временных кластеров.** D — development/exposure; V1 — заранее выбранная validation; V2 — отдельный заранее предусмотренный scenario world/recovery input, не запасной рынок для спасения V1.

Порядок: preregister question/protocol/selection rule → preserve complete exposure history → bind точный future source по native rules → pre-values reservation → первый numerical read → inference → substantive evidence → durable commit → cold consumer. Question, target, sign, thresholds и decision rule до чтения V не меняются.

Можно заранее сгенерировать future bytes в закрытой области Builder и передать лишь разрешённые hashes/metadata; нельзя сделать их доступными tested product process до gate. Когда source ещё не существует, freeze содержит правило отбора/временное окно, а не выдуманный content hash. После появления источника нужен настоящий binding producer. Отсутствие такого producer — finding, не повод «дописать hash руками».

Граница истинности этой изоляции: `WITHHELD_FROM_TESTED_PROCESS`. Автор synthetic world знает формулу; `GENUINE_BLIND_ACTOR` не заявляется.

### 9.4. Применимость List A, достаточность и clocks

List A contract не является универсальным протоколом любой гипотезы. Его можно использовать для exact LIST_CONTRAST A vs known complement, E1800→E14400 с неизменённым смыслом. MIXED не получает автоматически те же statistical verdicts.

Если выбран именно этот метод, сохранить принятые значения: оба partitions 24h/48h, ≥30 contributing mint и ≥30 contributing blocks в каждой группе каждого partition, B=4096, coverage ≥.95, gap missingness ≤.05, frozen leave-one и no-reroll. Runtime/seed/core-hash bindings — по его контракту; если locked runtime несовместим, не устанавливать новый и не менять метод ради теста: typed gap.

**Двух-трёх calendar blocks недостаточно.** Компактный conditional confirming specimen обязан занимать как минимум 30 разных 48h blocks с нужным support обеих групп; ориентир — 64 синтетических дня и небольшой достаточный набор admissions, а не тысячи случайных rows. Генерировать его только после доказанной достижимости producer. Если это выходит за envelope, зафиксировать budget boundary; не снижать floors.

Отдельное существенное различие: Spec 1.4 reuse readiness требует 100% required coverage на D; List A inference допускает свой заранее принятый .95 coverage gate и conditional estimand. Не менять один порог под другой и не считать Spec 1.4 готовым confirming contract.

Для эмпирического development/exposure принятый boundary:

```text
boundary = max(dev_target_available_max, dev_decision_max + E)
validation_information_start > boundary
```

E определяется **один раз** bound horizon/grid/lateness/visibility contract. Нельзя заменить E на 12 600 секунд только потому, что это интервал E1800→E14400, прибавить его дважды или ограничиться сортировкой по дате cohort. Проверить equality и пересечение information/label intervals как отрицательные controls.

`FIRST_PREREGISTERED_TEST` без empirical development не получает fake dev clocks. Синтетический D не переписывает реальную development provenance List A. Same mint не удаляется автоматически ради удобства: сохранять episode identity и принятые dependence assumptions. Target missingness не превращать в ноль/-100%.

### 9.5. Контролируемые научные outcomes

В отдельных, зарегистрированных заранее synthetic worlds:

- устойчивый положительный контраст, достаточный по выбранному accepted protocol;
- null/противоположный контраст при валидном sample;
- недостаточность/концентрация/нарушение chronology при неизменной постановке.

Ожидаемые native terminals берутся из конкретного frozen protocol, а не универсального PASS/KILL. Для текущего List A это локальные `ASSOCIATION_SUPPORTED_CONDITIONAL`, `ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY`, `INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION`, `INSUFFICIENT` или более ранний `INVALID_OR_BLOCKED`.

Никакого best-of-seeds: один зарегистрированный метод на мир. Технически невалидный запуск сохраняется; исправление fixture/observer объясняется. B replicates внутри frozen bootstrap — не тысячи новых hypotheses, но новый sample/look не маскируется этим различием.

Если нет production inference consumer, разрешён максимум малый independent reference check **как oracle specification / MODEL_ONLY**, а не самописный полный bootstrap engine. Контрактные synthetic checks из прошлого List A design переиспользовать по fingerprint. Не тратить budget на повтор доказательства уже известной арифметики вместо отсутствующего seam.

## 10. Линия C: реальные results → dossier → честное решение

### 10.1. Positive execution witness

Использовать **actual** result/passport/records, созданные A. Тот же Spec разместить в допустимом synthetic definition slot обычного lifecycle consumer, сохранив experiment_id, canonical hash и file hash. Если нужен Catalog/definition fixture, он test-owned и объявлен; production catalogs/real experiments не перезаписывать.

Ordinary `FactoryApplication.research_detail` должен показать выполнение exact experiment как COMPLETED, если native records это доказывают. Нельзя заменять broken join ручным `EVIDENCE_BINDING`, копированием RUN или «близким» experiment_id.

Definition slot подготавливается штатным test setup либо в disposable definition view с неизменными product source bytes; не в реальном `configs/experiment_specs` владельца и не с подменой identity после freeze. Если регистрацию definition выполнил audit вручную, объявить `DEFINITION_INGRESS_FIXTURE`: C проверяет настоящий consumer на actual result, но не доказывает автоматический producer регистрации. Непроверенный registration edge остаётся SEGMENT/UNKNOWN и не исчезает из итогового claim.

Expected: numeric result доступен, execution завершено, lineage соответствует; scientific obligations остаются MISSING/UNKNOWN/CONFLICT там, где нет qualifying evidence. Точный список читать из current native consumer, не копировать устаревшее количество 13/14.

### 10.2. Решение оператора

Через `FactoryApplication.record_research_decision` сохранить synthetic `PAUSE` с причиной «численный replay проверен; independent confirmation не установлено» и конкретным next condition. Cold process читает decision_history; identical command replay не дублирует решение. Отдельный specimen с `REJECT` нужен только если покрывает иной material mapping; это не автоматический scientific KILL семейства.

Валидный запрос `PROMOTE` на недостаточном dossier должен достичь именно science guard, дать `PROMOTE_BLOCKED` и не создать DECISION_EVENT/StrategyVersion/activation. Предыдущий parser error из-за отсутствующего обязательного поля не является доказательством работы promotion guard.

Если B реально сработал, положительная association не обязана закрыть ENTRY/EXIT/COST/EXECUTION_REGIME. Их нельзя заполнять фиктивными quotes/FCF для красивого terminal.

### 10.3. Подмена и stale state

Один другой experiment с похожим текстом/той же hypothesis остаётся RELATED/foreign, а не DIRECT. Неверный spec version/hash или conflicting run identity не лечится слабым join. Изменившийся evidence snapshot делает старую команду stale и не пишет новое решение.

Проверять claims по contract: dossier guard может проверять наличие и связность полей, а не математическую/рыночную истинность всего evidence. Не приписывать ему больше, чем он обещает. Убедительный authored scientific payload не является доказанным producer. Если для positive consumer test нужны такие records, вынести в отдельный `CONTRACT_ONLY` case и не суммировать с A/B в FULL.

## 11. Замороженная матрица обязательств

Это минимальный предметный набор, а не требование отдельных scripts или полного декартова перебора. До широкого запуска связать каждый case с actual command/method, input, oracle, before/after и expected native outcome. Блокированные случаи остаются в denominator.

| ID | Маршрут / вопрос | Достаточное evidence и правильная граница |
|---|---|---|
| SC00 | Safe binding + контрпример oracle | Real containment, positive valid ingress, испорченная копия result не проходит numeric/hash check |
| SC01 | First actual numeric Spec 1.4, LIST + MIXED | Evaluator reached; .11/.055 и per-cohort values; real artifact/passport/commit; INCONCLUSIVE не скрыт |
| SC02 | Exact repeat + cold read | Тот же logical run; evaluator/target reads=0 на completed replay; new scientific look=0; revalidation prefix reads допустимы |
| SC03 | Missing/foreign/stale source или definition | Правильный native blocker до evaluator; missing 19/20 не сокращает D и не даёт complete-case numerical run |
| SC04 | Current protection меняется после READY | Новая execution/replay revalidates и отказывает до targets; исторический readback остаётся доступен |
| SC05 | Interrupt → resume | Один process fault до durable completion, один lost-response после commit; no duplicate logical completion, orphan/partial state не healthy |
| SC06 | Другая численная реальность при том же prefix | Новый registered world: числа/результат меняются, membership не зависит от future; прошлый result не переиспользован молча |
| SC07 | Actual A output → ordinary dossier → PAUSE | Real execution DIRECT join, сохранённое решение и cold read; science не усилена |
| SC08 | Stale/foreign/unsupported promotion | Target guard достигнут; ноль запрещённых writes; RELATED не усиливает experiment |
| SC09 | Chronological ingress capability probe | Current protocol + producer + reservation + consumer или exact gap, отдельно от sample/authority; no invented native terminal |
| SC10 | Conditional new-validation positive/null/insufficient | Только native B; fixed method/source scope; проверенный oracle и declared terminals, не replay/новая discovery MAIN |
| SC11 | Conditional chronology/exposure/restart/concurrency | До first targets durable reservation; overlap/early read/re-entry refused; crash не сбрасывает charge и не оставляет sample «нетронутым» |
| SC12 | Conditional substantive B evidence consumption | Producer-generated qualifying fields привязаны к exact protocol/spec/sample/run; cold consumer не усиливает association до executable strategy |

**Do not hide reachability:** если SC10–SC12 недостижимы из-за одного отсутствующего producer, это один root finding с несколькими blocked obligations, не три вымышленных бага. Если SC01 падает, сохранить earliest boundary, но выполнить независимые SC09 и доступные contract-level C checks.

## 12. Минимальные независимые oracles

### 12.1. Numeric oracle

Из authored input table через `Fraction`/`Decimal` вычислить price-relative returns, matched/comparator means, contrast, counts и обязательные exposed output summaries. Сопоставление IDs независимо от classifier masks. Для exposed median/downside/calendar/cohort readouts использовать маленькую прямую формулу/сортировку, а не импорт соответствующего production helper.

Пример математического ядра для **таблицы §7**, не production implementation:

```python
from fractions import Fraction

m = [Fraction(x, 100) for x in (10, 11, 12, 13, 14, 6, 7, 8, 9, 10)]
c = [Fraction(x, 100) for x in (-4, -3, -2, -1, 0, -2, -1, 0, 1, 2)]
mean_m, mean_c = sum(m) / len(m), sum(c) / len(c)
mean_d = (sum(m) + sum(c)) / (len(m) + len(c))
assert mean_m - mean_c == Fraction(11, 100)
assert mean_m - mean_d == Fraction(11, 200)
```

Oracle tolerance для serialized finite summaries зафиксировать заранее, например absolute 1e-12 на этой малой таблице. Она не меняет native scientific thresholds и не округляет verdicts. Native IDs/counts/roles/hashes сравниваются точно. Nonfinite/unsupported numbers — typed failure, не NaN, замаскированный `isclose`.

### 12.2. Read/execution oracle

Наблюдать реальные numerical entrypoints и file readers, различая вызов observer и фактический результат native method. Wrapping допускается как telemetry/pass-through/fault injection, но не как замена result. Observer не должен «восстанавливать» отсутствующий commit.

Счётчики отдельно: source opaque bytes; decoded prefix cells; decoded target cells; evaluator invocations; setup MAIN looks; новые scientific reservations/looks; completed replay; ResearchStore writes. Не выводить все эти величины из одного `new_look=false`.

Canaries: намеренный early/foreign target read до phase grant; испорченный numerical summary/contrast; неправильный membership mask; forged COMPLETE. Canary должна провалить соответствующий observer. Сам факт canary detection не доказывает безопасность незадействованного reader.

### 12.3. Durable-state oracle

Считать committed records через штатный read-only путь плюс независимо проверить result file/hash/passport links. Read-after-write другим процессом. Before/after включают logical identities и counts, не только mtime.

Не заявлять writes=0 на основании response. SQLite SHM/OS cache отделять от durable business changes. Unavailable store — UNKNOWN, не empty-success. READ не должен создавать отсутствующую DB или директории.

### 12.4. Chronology oracle

Три отдельные проверки: native time geometry; ordering событий freeze/reservation/read; source interval overlap. Дешёвый hand example считает deadline самостоятельно, не копией resolver. Source metadata корректно связана с producer clocks. Номинальный due, actual availability и process wall clock не взаимозаменяемы.

## 13. Failure/recovery: конкретные seams, без новой инфраструктуры

**SC05-A: result создан, completion ещё не committed.** Остановить owned process на реально наблюдённой границе, сохранить files/store/trace, перезапустить тот же entrypoint. На текущем replay-path допустима повторная детерминированная вычислительная работа по прежним источникам; нельзя назвать orphan artifact готовым scientific run. Новый научный look от технического replay не появляется. Если result файл остаётся orphan/partial — он должен быть обнаружим, а итог не ambiguous healthy.

**SC05-B: commit состоялся, ответ потерян.** Барьер после native commit, до доставки result caller; новый процесс с тем же request читает completed run без target evaluator и без duplicate logical completion. Это дешевле и полезнее, чем kill в произвольную миллисекунду.

**B reservation crash:** только при реальном confirming producer. Остановить после native reservation/первого read, до final commit. Pending attempt остаётся potentially exposed/charged; повтор не получает чистый budget или новую untouched sample identity. Audit ledger сам это записывает, но не заменяет отсутствующую product reservation.

**Concurrency:** для нового confirmer два процесса на exact operation при барьере до first target. По его принятому contract одновременно не более одного evaluator. Для A immutable replay дополнительный concurrent compute сам по себе не scientific defect, если такой запрет не обещан; проверять обещанные idempotency/record semantics, не навязывать лишний глобальный lock.

Использовать существующий fault hook, process barrier или test-only wrapper вокруг настоящей storage boundary. Если hook недоступен без product patch, честно снизить fidelity конкретного case; не добавить test API в продукт под видом аудита. Crash test не требует отдельного chaos framework.

## 14. Budget, accounting и stop conditions

### Рекомендуемый envelope

| Ресурс | Граница |
|---|---|
| Product/service/dependency installs | 0 |
| Provider calls / cash / real-data reads | 0 |
| Genuine LLM science/Actor trials | 0; scripted upstream + необходимые repository reviewers |
| Новые fixture MAIN looks A | Цель 2–4, максимум 6 на campaign; все retained/reused looks видимы отдельно |
| Actual numeric evaluator invocations A | Максимум 12, включая failures/recovery; successful completed replay не должен увеличивать счётчик |
| B new scientific attempts | По одному на каждый из максимум 3 заранее зарегистрированных независимых synthetic worlds; только при accepted route, общий cap 3; bootstrap replicates — внутри method budget |
| Retained incremental owned allocation | Цель ≤256 MiB, stop ≤512 MiB; старые retained worlds отдельно, не копировать целиком без нужды |
| Durable Git evidence | Обычно до 5 MiB; компактные recipes/receipts/traces, не сотни MB snapshot |
| Process bounds | Existing bounded runner; ориентир numeric process 180s, fixture setup 600s; timeout — INVALID/PARTIAL evidence, не scientific KILL |

Числа — предлагаемые **engineering limits этого synthetic audit**, не научные thresholds продукта. Перед запуском зафиксировать их в campaign/task. Не расширять лимит постфактум и не обнулять его перезапуском модели.

Все создание/reuse datasets, viewed candidates, versions, invalid attempts, calculated runs и checks попадают в единый append-only attempt ledger. World generation без просмотра product outcomes не scientific look; native `discovery-execute` с values — look даже ради fixture setup. Наследованные 22 MAIN из ремонта не выдавать за новые и не стирать.

Если прежний fixture содержит два MAIN, не выполнять их заново в `setUp` каждого test. Одна подготовка + безопасные isolated mutable copies. Immutable read-only source blobs можно переиспользовать; mutable SQLite/JSON нельзя hardlink так, чтобы fault одного теста менял другой мир. Allocation измерить с учётом hardlinks отдельно от logical size. Shared cache growth без baseline — UNKNOWN.

**Stop/replan:** опасная изоляция, новые external grants, product mutation, изменение научного смысла/порогов, невозможность valid positive witness после локального исправления kit, повтор одного material blocker без новой информации, превышение envelope. Остановка зависимого узла не отменяет независимые проверки.

**Exit исследования:** A/C дали проверенные результаты или exact repro; для B установлена исполнимость/точный gap; selected material scenarios accounted; следующий запуск не даёт нового различения причин. Не наращивать coverage ради количества тестов.

## 15. Исполнительская последовательность

### P0 — BIND + cheapest path probe

Прочитать current owners, создать exact audit task/write set по repository harness. Проверить saved environment fingerprint. Зафиксировать SC00–SC12 и budget. Сначала установить B capability reachability без target reads, затем довести один valid A specimen до actual runner dispatch. Не строить большой generator, пока этот вход не жизнеспособен.

**Checkpoint:** main/source fingerprints, exact permitted operations, scope B, valid A ingress и safety evidence. Новая owner-пауза между безопасными шагами не нужна.

### P1 — ASYMMETRIC WORLD + SC01

Подготовить один asymmetric native world по §7, prewrite oracle, freeze specimen и принять scripted upstream через настоящее persistence. Исполнить LIST, затем MIXED тем же публичным numeric path. Получить actual artifacts/passports и независимые числа. Если execution падает раньше evaluator, минимизировать repro; не заменять это «успехом функции вычисления».

### P2 — SC02–SC06

Повтор/cold read, один source/protection denial непосредственно на runner, два определённых process-fault checkpoints, numerical variation. Не повторять весь #403 matrix; переиспользовать его доказательства для старой schema/classifier границы, добавить только новые прямые consumers.

### P3 — C actual result consumption

Подключить actual A records к ordinary dossier через допустимый definition slot. Проверить COMPLETED/INCONCLUSIVE/qualifying gaps. Записать synthetic PAUSE, проверить cold/identical repeat; валидные stale/foreign/PROMOTE negative cases. Если native join ломается, это отдельный actionable finding, не пустое «science не готова».

### P4 — Conditional B

Если SC09 доказал accepted executable producer, подготовить достаточные protected synthetic sources и выполнить SC10–SC12. Иначе сформировать один root gap с источниками, заявленной public boundary и точным repair outcome. Не тратить остаток времени на тестовую реализацию отсутствующего confirmer.

### P5 — VALIDATE / HANDOFF

Пересчитать report из evidence/ledger. Проверить source immutability, no product mutation, counts/fidelity, reviewer findings. Остановить только owned processes. Сохранить reproducible minimal kit и footprint, не удалять retained worlds автоматически. Exact-head checks/merge-readiness — по Git policy; merge после отдельной owner phrase.

Это один audit atom. Реальный product repair по его итогам — следующий отдельно разрешённый атом. Не превращать план/runner/evidence/report в несколько обязательных PR без причины.

## 16. Артефакты, write set и повторяемость

Рекомендуемое новое размещение, **предлагаемые пути, не утверждение о текущих файлах**:

```text
docs/tasks/SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1.md
tests/fixtures/science_lifecycle_smoke_v1/
    campaign.py       # небольшой driver / scenarios / existing entrypoint wiring
    oracle.py         # independent table arithmetic, masks, phase/read checks
    campaign.json     # либо YAML: frozen scenario/source/budget manifest
tests/test_science_lifecycle_smoke_v1.py
docs/evidence/science_lifecycle_smoke_v1/
    summary.json      # scopes, counters, executed/blocked, source fingerprints
    attempts.jsonl    # small append-only ledger / refs for larger retained traces
    findings.json    # root boundaries, repro, acceptance
    numerical.json   # actual numbers + expected + comparisons
    readback.json    # run/passport/dossier/decision lineage
    chronology.json  # actual B evidence or precise blocker, not a guessed PASS
docs/reports/science_lifecycle_smoke_v1/
    OWNER_REPORT.md
    REPRODUCE.md
```

Не создавать каждый файл, если existing runner позволяет объединить его без потери смысла. Единый campaign manifest — source, report/coverage — производные. Никакого второго конкурирующего plan/spec в Git: данный документ можно сделать task/spec owner либо referenced design, не копировать его вручную в три каталога.

Expected managed write set: указанные audit/test/docs paths плюс только необходимые existing Catalog registrations/generated views по current policy. Production source, capability registry, schemas, real ExperimentSpec/configs и исторические List A receipts — вне write set. В этот раз продукт не меняется: dependency pins исторического scientific owner обновлять «для зелёного delivery» незачем.

Команды в REPRODUCE должны быть **проверены исполнителем**, например одна для scoped run и одна для `verify-saved`, без новых scientific looks. Не объявлять предлагаемые имена `campaign.py run` существующими API до их реализации. Existing `uv run --locked --managed-python --no-sync python -B -m unittest ...` переиспользовать; один all-tests setup не должен создавать новые worlds при чтении saved evidence.

Вещи, нужные только локальному runtime — env/root/PIDs/resources — остаются в operational manifest. В Git: воспроизводимые rules, fixtures, semantic contract refs, компактные findings и значимое evidence. Физические пути/credentials в portable receipts не входят. Retained external-to-Git artifacts имеют hash, exact locator и retention status; hash без доступных bytes не доказывает воспроизводимость.

## 17. DoD и допустимые итоги

### Обязательное доказательство, не checklist PASS по рассказу

**A:** один настоящий successful numerical Spec 1.4 path с asymmetric independent oracle и actual committed artifacts; repeat/cold/readout проверены. Если вместо этого обнаружен продуктовый defect, нужен valid reproducer с earliest broken boundary и независимый expected outcome. Helper-only успех не закрывает A.

**C:** actual A output потреблён real dossier либо воспроизводимо показан broken join. Правильная техническая классификация не усиливает scientific validity. Хотя бы один разрешённый owner decision и один корректно достигнутый science refusal, если этот consumer доступен.

**B:** конкретное evidence доступного/недоступного confirming producer и accepted contract. При доступности — native conditional scenarios. При недоступности — root finding + blocked downstream. Недостаточно только переписать старый `sample_binding: UNBOUND`: проверить именно producer/consumer и связь с current main после #403.

**Across:** isolation, accurate trial/compute ledger, current-protection recheck, no fabricated internal producers, no loss of failure history, compact replayable kit, один NOW repair или «новый repair по проверенному scope не нужен».

### Отдельные оси результата

```yaml
# Образец report shape; значения вычисляются по actual evidence.
campaign_status: COMPLETE_WITH_FINDINGS | PARTIAL_PRODUCT_BLOCKED | PARTIAL_ENVIRONMENT | INVALID_HARNESS
lanes:
  numerical: PASS | FAIL | BLOCKED | UNVERIFIED
  chronological: PASS | FAIL | BLOCKED_PRODUCT | BLOCKED_CONTRACT | BLOCKED_AUTHORITY | UNVERIFIED
  evidence_consumer: PASS | FAIL | BLOCKED | UNVERIFIED
fidelity_by_edge: FULL_PRODUCT_PATH | SEGMENT_PRODUCT_PATH | CONTRACT_ONLY | MODEL_ONLY
science:
  market_alpha_established: false
  synthetic_protocol_executed: false  # true лишь при actual B execution
  strategy_ready: false
```

`COMPLETE_WITH_FINDINGS` означает, что согласованное исследование выполнено, а не что продукт целиком исправен. `FULL_PRODUCT_PATH` допустим только с явными start/end конкретного edge: «Spec1.4 → saved numeric artifact» не равен «Forge → OOS → Strategy». Несколько SEGMENT не складываются в FULL.

До завершения self-check: не назван ли replay новой validation; не использован ли future MAIN для получения удобного recipe; не понижен ли scientific floor; не скрыт ли target read в metadata loader; не превратилась ли запись carrier в квалифицированное evidence; не заменена ли product reservation audit ledger; не объявлен ли старый approval текущим.

## 18. Findings, review, rollback и handback

Finding содержит: класс, impact/severity, violated promise/source, input preconditions, expected/actual, earliest broken owner boundary, exact repro, hashes/readback, затронутые consumers, confidence, repair outcome, acceptance и rollback. Разделять:

- `PRODUCT_DEFECT`: однозначное текущее обещание нарушено;
- `MISSING_PRODUCT_SEAM / CONTRACT_GAP`: нужный scientific переход не реализован/не определён;
- `EXPECTED_SCIENTIFIC_OR_AUTHORITY_REFUSAL`: правильная защита;
- `HARNESS_DEFECT / INVALID_RUN`: ошибка среды/fixture/oracle;
- `COVERAGE_GAP / UNKNOWN`: граница не достигнута или observation недостаточен.

Не называть contract gap в подтверждающем контуре автоматически «багом #403»: #403 закрывал другой согласованный outcome. Но такой gap может быть NOW по влиянию на фабрику.

Risk-routed review по текущему task: code review audit kit; goal/DoD; architecture/semantic premise — особенно replay vs new evidence, clocks/exposure, producer vs authored carrier; owner-UX для ясности report/next action. Не запускать новый live hypothesis Critic для оценки инженерного теста. Existing independent review не переносить на изменённый oracle без applicability check.

Rollback audit code/docs — ordinary revert. Synthetic stores/attempts/evidence сохраняются; исходные audits и repaired product не изменены. Не удалять .venv/cache/Docker volumes прошлых кампаний. Owned процессы остановить, показать точный footprint и cleanup targets отдельно от retained evidence; shared cache без baseline оставить UNKNOWN.

Первая страница owner report:

1. Что теперь доказано, простыми словами и с границей.
2. Одна таблица A/B/C: status, fidelity, важнейшее evidence.
3. Material findings — подробно лишь там, где проблема.
4. Что остаётся недоказанным и почему; реальная необходимая authority отдельно от product gaps.
5. **Один next step:** bounded repair или готовность к отдельно разрешённому следующему experiment. Никакого списка из десяти инфраструктурных улучшений.

Checkpoint для продолжения: goal/scope/mode; exact Git/source/manifest identities; attempts/charges; completed/invalidated/uncovered; current resources and containment; first blocker; exact следующая безопасная операция. Resume не перезапускает всю campaign и не обнуляет budget.

## 19. Команда исполнителю

Ниже — предлагаемый owner starter для передачи вместе с этим MD. Он разрешает только synthetic audit, не product repair/реальную Science/merge.

```text
Выполни SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1 по приложенному PRD+SSD.
Режим EXECUTE / SYNTHETIC_AUDIT_ONLY.

Цель: после ремонта #403 проверить настоящий численный Spec1.4 путь до
committed result/passport и ordinary dossier, повтор/восстановление; отдельно
доказательно установить исполнимость chronological validation того же estimand.
Не повторяй большой Forge/Trading audit.

Разрешаю в exact audit scope создавать disposable synthetic inputs/stores,
ограниченные fixture MAIN looks по budget документа, реально исполнять native
численный runner, писать test-only код/evidence и synthetic owner decisions
через существующие public methods. Production code/contracts/schema/registry,
реальные market data/holdout, provider, credentials, spend, deploy, strategy,
activation/PAPER и merge этим не разрешены.

Сначала rebind current Git через AGENTS и semantic owners. #403 должен входить
в tested product. Переиспользуй existing locked runtime и подходящие retained
fixtures; сохрани source/attempt identity и историю. Зафиксируй bounded task,
write set, read phases, oracle и engineering envelope.

Первым practically valuable proof сделай настоящий asymmetric numerical run:
не helper-only, не готовый completed-run fixture и не первый REPLAY_AVAILABLE.
Проверь native LIST/MIXED comparator semantics независимой арифметикой, actual
artifacts/records, cold readback, exact repeat, current protection и два
определённых interruption checkpoints. Передай реальные producer records в
ordinary dossier без ручного repair join; сохрани честный PROMOTE_BLOCKED.

Chronological branch: найди accepted protocol, actual producer, pre-values
reservation и substantive consumer. Если они существуют и допускают synthetic
execution в текущем scope, исполни registered positive/null/insufficient cases
без изменения метода/порогов/ролей. Если нет — докажи exact missing boundary,
не строй собственный confirmer и не называй discovery replay OOS. Не заканчивай
весь audit одним пересказом старого UNBOUND: A и доступные C должны быть проверены.

Тестовый мир и fault hooks контролируют внешний вход, время и отказы, но не
подменяют production decisions, numerical output, reservation или committed
state. Сохраняй все failures, invalid runs, scientific/compute counters,
непроверенные edges и точную fidelity. Чини только свой audit kit.

На выходе: воспроизводимый минимальный kit, численный/state/readback evidence,
карта A/B/C, причинный backlog, footprint, лаконичный owner report и один
рекомендуемый repair atom только при доказанной необходимости. Product repair
не выполнять. Между безопасными зависимыми стадиями не останавливаться.
Exact-head CI -> merge-readiness -> отдельная owner phrase по current policy.
```

## 20. Источники и границы заимствования

Все repository paths ниже прочитаны на planning commit `fbac5449f6dd22a7bc066114109be8bbed830447`, если отдельно не указано иное. Это минимальная карта для повторной проверки, не требование читать каждый файл целиком.

| Ref | Source | Что подтверждает |
|---|---|---|
| S01 | `AGENTS.md`; `docs/FACTORY_SEMANTIC_MAP.md`; PR #403 metadata / `refs/heads/main` | Routing, authority, текущую Git-базу |
| S02 | `docs/contracts/episode_native_required_outcomes_v1.md` | Spec1.4 reuse semantics и границу научных claims |
| S03 | `configs/experiment_capability_registry_v2.yaml` | Accepted fixed-time proxy, effect/output/promotion authority |
| S04 | `src/solana_alpha_lab/factory/document_runner.py`, `RunContext`, `_frozen_hfic_replay_lineage`, `start_document` | Actual execution/replay/lineage/persistence порядок |
| S05 | `src/solana_alpha_lab/factory/hfic_temporal_discovery.py`, `bind_frozen_fixed_time_inputs`, `run_temporal_fixed_time_from_spec`, `execute_fixed_time_proxy_capability` | Frozen source binding, настоящий evaluator, COMPLETE/INCONCLUSIVE |
| S06 | `docs/contracts/list_a_chronological_confirmation_v1.md` | Accepted method, sample/authority gaps, obligations отсутствующего producer |
| S07 | `configs/list_a_chronological_confirmation_v1.yaml` | Core/sample status, thresholds, chronology, reserve-before-values, seeds/runtime |
| S08 | `docs/contracts/experiment_evidence_decision_v1.md` | DIRECT/RELATED, execution/evidence/decision, native owner command и no-write read |
| S09 | `tests/fixtures/episode_native_required_outcomes_v1/proof.py` | 24-admission native fixture, explicit current completeness, setup MAIN, Spec/session binding |
| S10 | `tests/test_episode_native_required_outcome_contract_v1.py` | Проверенные prefix/target no-look phases, native guards, применение scripted Critic |
| S11 | `tests/test_hfic_list_aware_vertical_v1.py` | Существующие synthetic external world/native capture/import, list/number inputs |
| S12 | `tests/test_experiment_evidence_decision_v1.py` | `compose_experiment_dossier`, `research_detail`, `record_research_decision`, stale/replay controls |
| S13 | `docs/reports/episode_native_required_outcomes_v1/OWNER_REPORT.md` и linked evidence | Delivered scope #403 и ещё не выполненный numerical success path |
| S14 | `docs/reports/synthetic_lifecycle_targeted_v1/OWNER_REPORT.md`, `contract-boundary.json`, `REPAIR_PRD_SSD.md` | Audit provenance; старые scientific KILL и segment/full ограничения |
| S15 | Предыдущий приложенный `EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1_PRD_SSD.md` | Owner-approved repair framing; не current runtime truth |
| S16 | Project constitution / owner-executor contract / truth protocol | Mission и разделение authority/evidence; текущие paths и результаты ими не доказываются |

### Внешние методические источники, проверенные при планировании

- Antithesis, **Asserting correctness**: `https://antithesis.com/docs/product/writing_tests/assertions/`. Перенесена только идея non-vacuous reachability и отдельного positive witness; SDK/service не нужен.
- Hypothesis, **Stateful tests**: `https://hypothesis.readthedocs.io/en/latest/stateful.html`. Перенесены последовательности действий и invariants после переходов; установка библиотеки не требуется.
- scikit-learn, **TimeSeriesSplit**: `https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`. Использовано только различие time-ordered validation и обычного split, включая ограничение equally-spaced samples. Для SMIAL не предлагается новый splitter: chronology/purge принадлежат native accepted contract, не числу строк или библиотечному `gap`.

Synthetic numbers, envelope, case IDs, orchestration и proposed artifact layout в этом документе — **проектные решения данной кампании**, не найденные продуктовые возможности и не статистические рекомендации для реального рынка.
