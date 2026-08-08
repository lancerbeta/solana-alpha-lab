# ROADMAP — SOLANA MEMECOIN INTRADAY ALPHA LAB

## Версия 4.7 — 8 августа 2026

> **Назначение:** единый control plane проекта для пользователя и ИИ.
> **Канонический research blueprint:** `Solana_Memecoin_Intraday_Alpha_Lab_Synthesis_v2_3_2026-07-18.md`
> **Операционная система:** `Solana_Memecoin_Intraday_Alpha_Lab_Operating_System_v8_5.md`, ожидаемая версия `SOLANA ALPHA LAB OPERATING SYSTEM v8.5`
> **Инструкция проекта:** `PROJECT INSTRUCTION — SOLANA MEMECOIN INTRADAY ALPHA LAB v3.3` — validated UI-field candidate; activation and exact equality remain user-owned.
> **Живое состояние:** `current_system_state.md` v4.2 — фактически существующая архитектура, authority/access, evidence и Project Asset Catalog checkpoint.
> **Общий статус:** `PROCEED_WITH_REDUCED_SCOPE`
> **Главный объект проверки:** распределение **реализуемой чистой доходности**, а не максимумы свечей.
> **Дата последнего bounded provider/pool evidence:** 2026-07-28. TASK-14 pricing snapshot датирован 2026-07-29 и истекает 2026-08-28; перед оплатой или sustained collection повторно проверять official docs и dashboard.

---

# 0. Как читать и использовать этот roadmap

## 0.1. Главный принцип

Проект идёт не по обещанным срокам и не по количеству написанного кода, а по доказательствам:

```text
архитектурное решение
→ работающий артефакт
→ воспроизводимая проверка
→ acceptance evidence
→ следующий gate
```

Наличие файла, скрипта или красивого графика не означает, что задача завершена.

## 0.2. Рабочий режим пользователя

Когда появляется свободный день:

1. Напиши: **«Какая следующая задача? Проверь её актуальность и веди меня по шагам».**
2. ИИ сам восстанавливает Current State, читает `current_system_state.md`, task contract и прямые зависимости.
3. До первой команды ИИ выполняет **Task Entry Gate** и выдаёт один вердикт: `START_AS_WRITTEN`, `START_WITH_PATCH`, `SPLIT`, `REORDER`, `BLOCKED` или `SKIP/CLOSE`.
4. ИИ выдаёт подробную **Beginner Task Brief**: смысл, связь с предыдущим/следующим этапом, необходимую теорию, роли, prerequisites/access, copy-paste microsteps, ожидаемые результаты, проверки, rollback и типичные ошибки.
5. Пользователь выполняет один шаг за раз и присылает только безопасный указанный результат. ИИ объясняет, что произошло, и только затем даёт следующий шаг.
6. За одну сессию выполняется один основной task или один чётко ограниченный кусок.
7. В конце создаются:
   - обновлённый `task_XX_*.md`;
   - необходимые код/config/report artifacts;
   - patch или новая версия `roadmap.md`;
   - обновление `current_system_state.md` либо явное `STATE_CHANGE=NONE`.
8. В Project Sources остаётся только bounded hot set из manifest; завершённые task records компактизируются в phase archive.

Пользователь здесь — владелец цели и junior operator, а не человек, который обязан заранее знать Git, Docker, SQL, ClickHouse или VPS. ИИ работает как senior buddy, стратег, технический руководитель, преподаватель и quality gate: рекомендует один обоснованный путь, не скрывает trade-offs и не перекладывает инженерное проектирование на пользователя.

## 0.3. Что не загружать в память GPT

Никогда не загружать:

- seed-фразы и private keys;
- API keys, пароли, cookies и access tokens;
- `.env`;
- необезличенные wallet secrets;
- гигантские raw Parquet/JSON dumps;
- полные runtime-логи без фильтрации;
- приватные торговые ключи;
- данные, которые уже воспроизводимо лежат в репозитории и описаны commit hash.

Для прогресса достаточно task-record, manifest, небольших config/schema/report файлов и точного commit/file inventory.

---



# 1. Current State

| Поле | Текущее значение |
|---|---|
| `current_phase` | `P4 — BOUNDED PUBLIC-HISTORY FEASIBILITY; NO EXECUTION AUTHORITY` |
| `active_task_id` | `TASK-27` offline A0 foundation |
| `active_task` | A2/A3/A4 freeze a price/volume data contract, collection authority boundary and Source-smoke prerequisite; no data has been collected |
| `active_status` | `SOURCE_RECONCILIATION_CANDIDATE_UI_ACTIVATION_PENDING` |
| `last_validated_task_id` | `T27-A0-A4`; current main `082f3f8184e84c31c876a484cf8e876a40691f62` |
| `next_recommended_task_id` | `T27-A0-A5_PERMANENT_SOURCES_RECONCILIATION_AND_SMOKE_V1`; then a separate owner external-read review, not a provider call |
| `primary_blocker` | A fresh seven-role Source smoke is absent; A4 forbids external-read review readiness without it |
| `product_direction` | Preserve quote/model/observed/UNKNOWN separation and require reconciliation before retry; a completed packet never creates authority |

# 2. Целевая система простыми словами

Мы строим не «бота, который угадывает памп», а дешёвую долгоживущую **Alpha Factory**. Один research cycle выглядит так:

```text
1. Увидеть все релевантные молодые токены, включая умершие
2. Записать состояние рынка так, как оно было доступно в реальном времени
3. Проверить, был ли реальный маршрут купить и продать заданный размер
4. Вычислить простые и проверяемые сигналы
5. Сравнить их с честными baseline
6. Учесть комиссии, задержки, неудачные попытки и деградацию выхода
7. Проверить результат на будущих данных
8. Только затем создать versioned strategy и дать одному bot instance $10
9. Повысить размер лишь при сохранении качества исполнения и cash economics
10. Monitor → recalibrate/challenger/retire; negative result возвращает нас к новой registered family
```

Общая spine ingestion/PIT/execution/risk/observability переиспользуется. Hypothesis-specific code/config остаётся модульным. Первый scope не расширяется: Solana memecoins, 15m–4h, один primary candidate. Второй bot не создаётся «для диверсификации», пока нет второго независимого evidence path.

## 2.1. Что считается успехом

На gate research cycle допустимы:

| Verdict | Значение |
|---|---|
| `PROCEED` | Есть воспроизводимый NetEV после costs и forward evidence; можно переходить к следующему gate |
| `REDESIGN_DATA` | Механизм остаётся правдоподобным, но PIT/data/execution measurement недостаточны |
| `PIVOT_FAMILY` | Текущая family опровергнута; новый механизм получает новый `RC-NNN`, budget и holdout |
| `EXTEND_EVIDENCE` | Результат inconclusive по заранее заданной precision/sample boundary; rules не меняются |
| `PAUSE` | Expected information/economic value сейчас ниже cash/time cost |
| `CLOSE_*` | Закрывается hypothesis, strategy version, bot, family, domain либо project — уровень всегда указан |

`CLOSE_HYPOTHESIS/FAMILY` не является провалом исследования. `CLOSE_DOMAIN/PROJECT` требует отдельного budgeted decision memo; первые три отрицательных теста сами по себе недостаточны.

## 2.2. Business KPI framework

North-star после live: `Realized Project Free Cash Flow` rolling month/90d = settled trading cashflow минус chain/venue/relay/ATA и provider/VPS/storage/software cash costs. Обязательно рядом: capital at risk, drawdown/CVaR, capacity и operator hours. Время пользователя до назначения ставки показывается отдельно как shadow cost.

До revenue управляем leading indicators: time/cash-to-kill hypothesis, PIT data coverage для новой family, backtest→shadow/live realization ratio, break-even cost consumption, reuse spine и `unregistered_trials=0`. Число bots, строк кода, объём data и backtest PnL не KPI.

---


## 2.3. Product operating model and owner journey

```text
idea/source
→ hypothesis dossier + provenance
→ research route/tools
→ reproducible PIT data + trials
→ OOS/walk-forward decision
→ paper/shadow/micro-live
→ trigger/risk/execution/position/exit
→ reconciliation/NetReturn/owner cashflow
→ monitoring/incident/recovery
→ learn/retire/dormant/reactivate/derive
```

Roadmap task ценен только если сокращает или защищает named decision в этой
цепочке. Control/data infrastructure без consumer остаётся deferred.

`OWNER_PULSE` развивается как read model:

- hypotheses, trials, decisions and prior-work links;
- watchlists/candidates and why they are eligible now;
- data freshness, coverage, cost and blockers;
- signals, positions, exits, reconciliation and unresolved inventory;
- Net PnL, drawdown, exposure, capacity and owner cashflow;
- incidents, kill switch, recovery and exact next owner action.

Начальный UX — generated text/CLI/SQL. Web UI появляется после stable read
contracts и повторяющихся operator questions; он не создаёт вторую истину.

## 2.4. Capability owners and activation triggers

| Capability | Immediate owner / trigger | Boundary |
|---|---|---|
| Hypothesis lifecycle, provenance, derivation and prior-work query | `TASK-16` now | Offline contract first; no platform |
| Hypothesis data memo and versioned watchlist | First accepted hypothesis consumer | Historical/cache first; live separately gated |
| Research tool capability registry/router | Second real tool/route or repeated selection cost | Problem/contract-driven; no tool zoo |
| Dataset builder and historical hydration cache | First accepted trial data memo | PIT, reusable and content-addressed |
| Owner pulse read models | Stable registries plus repeated owner questions | Text/SQL before web UI |
| Trigger-to-cashflow execution and position truth | Before paper/shadow engines | Project-owned policy/truth; replaceable transport |
| Monitoring, kill switch, incident and recovery | Before unattended/live authority | Live forbidden without it |
| Documentation foundation and AI/operator runbooks | `TASK-34A`; first unattended runtime, second operator or repeated documentation friction | Generate from contracts/Catalog; no manual wiki bureaucracy |
| Production-lite control plane and Owner Cockpit | `TASK-35A`; stable read contracts and mandatory before TASK-38 | Remote paper/shadow operations only; no wallet or live authority |
| Provider purchase/live collection | Measured named non-reconstructable demand | No automatic seven-day warehouse |

# 3. Бюджет и где брать инструменты

## 3.1. Рекомендуемый стартовый стек

| Компонент | Стартовый выбор | Для чего | Стартовая стоимость | Оплата криптой | Когда покупать/повышать |
|---|---|---|---:|---|---|
| Репозиторий | GitHub Free, private repo | Код, configs, issues, commits | $0 | Не требуется | Сразу |
| Локальная среда | Python 3.12+, `uv`, VS Code, Git, Docker Desktop/Engine | Разработка и воспроизводимость | $0 | Не требуется | Сразу |
| Локальное хранилище | DuckDB + partitioned Parquet | Research dataset | $0 | Не требуется | Сразу |
| RPC / WebSocket | Helius Free | RPC, Webhooks/WSS, первые smoke tests | $0, 1M credits / 10 RPS по pricing page | Да, USDC on Solana на платных планах | Developer $49 только после измерения расхода/429/нужды в enhanced data |
| Indexed token data | Solana Tracker Data API Free | Tokens, pools, risk, holders, trades, bundlers | $0; официальный pricing page указывает 10k req/mo, marketing page — 2.5k; dashboard считать source of truth | Не подтверждено официальной документацией | Advanced €50 только если pilot упирается в quota; Premium €397 с Datastream пока запрещён |
| Cross-check / targeted endpoints | Birdeye Standard + x402 | Независимая проверка price/OHLCV/holder/trader данных | Standard $0; x402 pay-per-request | Да, USDC on Solana; подписки USDC/USDT для длинных периодов | Начать с x402 только для точечных запросов; Lite $39 после cost comparison |
| Executable quotes | Jupiter Developer Platform Free | Swap v2 quotes, `/order`, позже `/execute` | $0, 1 RPS; Developer $25 = 10 RPS | Да, USDC on Solana | Free для pilot; $25 только когда quote logger стабильно упирается в 1 RPS |
| 24/7 runtime | Сначала домашний ПК; позже дешёвый Linux VPS | Непрерывный collector | $0 локально; VPS обычно ~$10–30/mo в нужной конфигурации | BitLaunch принимает BTC/ETH/LTC и тарифицирует почасово | Покупать после 24–48h локального pilot и оценки RAM/disk/network |
| Аналитика cross-check | Dune / explorers / Pump UI / Solscan-подобные инструменты | Ручная верификация | Обычно $0 для базового использования | Не требуется | Только как cross-check, не источник point-in-time truth |
| Уведомления | Telegram Bot API | Paper alerts | $0 | Не требуется | После готовности signal engine |
| Backup | Второй локальный диск или объектное хранилище | Сохранность raw data | $0–несколько долларов | Зависит от провайдера | После первых 7 дней стабильного сбора |

### Практический вывод по оплате

На старте достаточно зарегистрироваться бесплатно. Первая вероятная платная покупка:

```text
Helius Developer $49
или
Jupiter Developer $25
или
точечные Birdeye x402-запросы в USDC
```

Покупка определяется не предпочтением, а измеренным bottleneck в `provider_cost_report.md`.

## 3.2. Бюджетные режимы

| Режим | Состав | Ориентир в месяц | Для чего подходит |
|---|---|---:|---|
| `ZERO_COST_PILOT` | Local + GitHub + Helius Free + Solana Tracker Free + Jupiter Free | $0 | Smoke tests, схема, 24–48h pilot |
| `LEAN_FORWARD_COLLECTION` | Helius Developer + local/cheap VPS + Jupiter Free + Birdeye x402 budget | ~$60–100 | 30–45 дней selective collection |
| `ROBUST_RESEARCH_MVP` | Helius Developer + Solana Tracker Advanced или Birdeye Lite + VPS + Jupiter Developer при необходимости | ~$120–220 | Более плотный collection + quote logging |
| `LOW_LATENCY_RESEARCH` | Helius Business / standalone gRPC / premium streams | $400–700+ | Только после доказательства, что latency materially limits validated edge |
| `HFT_INFRA` | Dedicated nodes/shreds/colocation | $1,300–3,000+ | Запрещено до отдельного economics gate |

Цены — ориентиры на 2026-07-18. Dashboard и invoice перед оплатой имеют приоритет.

## 3.3. Что сейчас не покупать

| Не покупать | До какого evidence | Почему |
|---|---|---|
| Helius Business $499 | Пока WSS/REST pilot не докажет недостаточность Developer |
| Solana Tracker Premium €397 | Пока не доказано, что Datastream заменяет более дешёвый Helius WSS и окупается |
| Standalone Yellowstone gRPC €200+ | Пока latency sensitivity не показывает потерю edge |
| Dedicated node | Пока validated strategy не имеет достаточного NetEV и turnover |
| Kubernetes | Пока один Docker Compose runtime не стал bottleneck |
| ML/GPU infrastructure | Пока простые baselines и veto не проверены |
| Дорогие historical datasets | Пока бесплатные/дешёвые historical/cache sources и named hypothesis data memo не доказали конкретный gap |
| Real-money bot framework | Пока не пройдены `G5` и security gate |

## 3.4. Короткий путь: reuse before build

Перед значимым custom code Task Entry Gate делает current landscape scan и записывает `ADOPT/WRAP/FORK/BUILD`. Проверяются acceptance fit, PIT/execution semantics, license/terms, signer/security, maintainer/releases, dependency/SBOM, pin/hash, integration/operations/exit TCO, lock-in, replay и rollback. Stars/marketing не evidence.

Initial candidates для TASK-01/04: Jupiter official clients/routing; Hummingbot Gateway как execution-plumbing reference/adapter candidate; Dune Solana raw/decoded catalog для historical feasibility/cross-check; Yellowstone gRPC/Vixen для streaming/parsing при measured need; Old Faithful для history access; official IDLs/libraries для decoder primitives. Ни один не выбран заранее. Dataset не создаёт наши historical `observed_at/available_to_strategy_at`; чужой bot не доказывает alpha и не получает signer/real money без независимого audit.

---

# 4. Gate Map

| Gate | Что должно быть доказано | Открывает |
|---|---|---|
| `G0 — CONTROL READY` | Канонические документы, roadmap, repo policy и source manifest согласованы | Реализацию |
| `G1 — HYPOTHESIS FACTORY READY` | Hypothesis lifecycle/provenance, prior-work lookup, trial/decision history и named consumer определены | Bounded hypothesis research cycle |
| `G2 — DEMAND-GATED DATA TRUSTED` | Accepted data memo доказал non-reconstructable need; bounded data quality/coverage/replay/cost известны, нет silent zero/future leakage | Named research dataset or `REDESIGN_DATA/PAUSE` |
| `G3 — RESEARCH DATASET READY` | Достаточная cohort history, labels и quote availability для intended notionals | Frozen experiments |
| `G4 — RESEARCH CANDIDATE` | Стратегия/фильтр показывает устойчивый OOS эффект после costs, не зависит от нескольких winners | Paper trading |
| `G5 — SHADOW VALIDATED` | Live signals, реальные quotes, latency/failure/exit path согласуются с моделью | Security design и micro-live |
| `G6 — MICRO-LIVE VALIDATED` | Tiny-money trades подтверждают paper/shadow assumptions и risk limits | Ограниченное масштабирование |
| `G7 — SCALE OR CLOSE` | Capacity, stability и operational burden измерены | Production-lite или закрытие |

---

# 5. Master Roadmap

## P0 — Project Control & Source Foundation

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-00A` Canonical blueprint | `DONE` | Фиксируем, что именно строим | Synthesis v2 canonical, ALBS isolated | Уже есть | Canonical research baseline | Header/version/status/hash verified | P0 archive | — |
| `TASK-00B` Memory integrity remediation | `DONE` | Устраняем неверные версии и дубликаты | Manifest/header/hash resolution; source cleanup | Локальные файлы | Canonical file set | OS v8 selected; clean retrieval; smoke test PASS | P0 archive | TASK-00A |
| `TASK-00C` Roadmap adoption | `DONE` | Делаем roadmap control plane | State/dependency/new-chat verification | Roadmap | Roadmap v1.1 validated | New chat correctly restored state | P0 archive | TASK-00B |
| `TASK-00D` Project Sources capacity architecture | `DONE` | Не даём Sources превратиться в свалку | Hot set, phase archive, compaction guard, replacement package | Free | OS 8.1, instruction 2.4, manifest/roadmap 1.2 | Six-file set; hashes; static validation | P0 archive + core files | TASK-00C |
| `TASK-00E` Independent canonical audit | `DONE` | Независимо проверяем конституцию до provider work | Hash/YAML/link/graph tests; method/execution/security red team; current-fact verification; rebase | Free | Audit report, replacement bundle, OS 8.2, instruction 2.5, blueprint 2.1, roadmap 1.3 | Mixed versions absent; bundle validators and fresh-context smoke pass; limitations explicit | P0 archive + local audit records | TASK-00D |
| `TASK-00F` Operator onboarding & living system state | `DONE` | Делаем проект исполнимым новичком и не даём реальной обвязке расходиться с документами | Buddy contract; Task Entry Gate; Beginner Task Brief; just-in-time access; component/environment/storage/access inventory; architecture-delta ledger | Free; GitHub plugin установлен, repo access не требуется до TASK-03 | OS 8.3, instruction 2.6, manifest/roadmap 1.4, `current_system_state.md` 1.0, TASK-01 1.2 | Seven-file set согласован; state truth boundaries/statuses определены; validators и fresh-context smoke pass; UI activation честно оставлена user attestation | P0 archive + seven-file core | TASK-00E |
| `TASK-00G` Long-lived Alpha Factory & business economics | `DONE` | Превращаем одно исследование в дешёвый повторяемый конвейер гипотез/стратегий/ботов | Mission/KPI; data option-value; global trial/holdout; separate lifecycles; renewable `RC-NNN`; closure; reuse/wrap/fork/build; cheap-first architecture | Free; design only | OS 8.4, instruction 2.7, blueprint 2.2, roadmap/manifest 1.5, state 1.1, TASK-01 1.3 | Seven-file mixed-version-free bundle; scope unchanged; factory/reuse/graph/hash/YAML/instruction/smoke validators pass; no provider/API/runtime claim | P0 archive + seven-file core | TASK-00F |
| `TASK-01` Source/provider manifest | `DONE` | Создаём проверяемую карту источников без вызова API | Required fields/coverage/tier/cadence/cost; provider + public/OSS historical catalog candidates; timestamp/terms; source contract; controlled smoke spec | `$0`; accounts/calls/purchases = 0 | Eight validated artifacts + final gap audit + completion handoff | 16/16 DoD reconciled; 34 cases/35 attempts/hard cap 50 frozen; no API call claimed; open runtime evidence assigned downstream | P0 archive v5 + immutable completion bundle | TASK-00G; completed |
| `TASK-02` Workstation bootstrap | `DONE` | Устанавливаем и доказываем минимальный toolchain | Windows/PowerShell inventory; Python/uv/Git; per-user Docker WSL2; time/disk/virtualization; deterministic validator | `$0` | Final task 1.2, bootstrap validator, env/tool/validation/operator receipts | 14/14 validator PASS; Docker runtime/container PASS; redaction PASS; exact versions/hashes; no repo/provider/VPS/wallet | P0 archive v7 + immutable TASK-02 completion bundle | TASK-01; completed |
| `TASK-03` Private repository, controls & Project Asset Catalog | `DONE` | Создаём безопасную папку проекта, Git truth layer и карту всех значимых assets | Private repo/remote; uv lock/CI/secret rejection; `AGENTS.md` + task/handoff Work↔Codex bridge; Catalog schemas/root/assets/query recipes/generator/validators; typed registries; import pre-Git TASK-01/02 lineage; graph DB deferred | `$0`; GitHub private repo; bounded Codex atoms | Accepted private main `f8ff483…`; Catalog 60/4/4/5; 9 registry frameworks; imported lineage; generated map/edges | Final local/CI/clean-clone 131/131 PASS; secret/security/catalog gates PASS; Work accepted; calls/spend 0 | P0 archive v8 + Git/catalog checkpoint | TASK-02; completed |
| `TASK-04` Architecture + reuse decision | `DONE` | Ищем безопасные короткие пути и пишем своё только обоснованно | ADR; current OSS/data/vendor landscape; ADOPT/WRAP/FORK/BUILD score by fit/PIT/license/security/maintenance/SBOM/TCO/lock-in/replay; bounded offline evidence | `$0`; provider calls 0 | ADR-002, decision matrix, reuse registry, SBOM and Catalog delta | Architecture/policy commits published; fail-closed validation PASS; Work acceptance received | P0/P1 archive + Git/Catalog | TASK-01, TASK-03; completed |



### Post-TASK-16 control status

- `TASK-00A…16`: accepted at their recorded bounded truth boundaries.
- `TASK-16`: repository accepted through PR #19 merge
  `7423b2b44630e84b58edb5be5331171fd36c4cfc`, tree `123347d6eaf8363f5e3723e2c3fa9fb073be41a4`;
  PR and main CI each passed the exact 1005-test gate.
- TASK-16 adds an append-only lifecycle/provenance/derivation schema,
  deterministic semantic validator and bounded evidence-bearing prior-work
  query without creating production hypotheses or a research platform.
- Empty legacy registries were preserved byte-for-byte; synthetic history
  was not invented.
- The TASK-15 Catalog-count follow-up was closed before the version bump:
  current checkpoint ownership is centralized and validated.
- Catalog: `0.19.0 / 280 / 4 / 4 / 8`; lifecycle registries/records `9 / 52`.
- Factory Fit: `FULL_REVIEW / PASS_WITH_FOLLOWUP`.
- Durable follow-up: TASK-17 exercises the first real bounded hypothesis
  cycle and data-need decision before any seven-day collection.
- Provider/API/RPC/WSS, credentials, collection, cash and
  wallet/signer/transaction actions in TASK-16: zero.

### Gate G0

`G0 = PASS`: `TASK-00B`, `TASK-00C`, `TASK-00D`, `TASK-00E`, `TASK-00F`, `TASK-00G`, `TASK-01`, `TASK-02`, `TASK-03`, `TASK-04` имеют статус `DONE`.

---

## P1 — Data Contracts & 24–48h Pilot

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-05` Canonical schema v1 | `DONE` | Описываем, что именно сохраняет система и как это найти/запросить | Revision-aware DDL/contracts; table/view asset registration; schema/query recipes; raw IDs/revisions, lifecycle/pool/trade/holder/features/regime, quote/execution/outcomes; field tier/first availability/coverage links | DuckDB | Executable schema, strict models, immutable migration, PIT queries and Catalog relations | Mutable facts append revisions; disagreement/missing/no-route semantics preserved; repository and finalization validation PASS | P0/P1 archive + Git/Catalog | TASK-04; completed |
| `TASK-06` Raw event envelope | `DONE` | Создаём универсальную упаковку любого ответа API и manifest целостности raw | Redaction-before-storage; deterministic raw/content identity; append-only revisions; immutable Parquet; dataset/partition manifests; storage-budget and reserve gates | Locked stack; provider calls 0 | Versioned storage module, contracts, fixtures, tests and Catalog records | Implementation/finalization published; CI and clean clone PASS; repository state `TASK06_FINALIZATION_COMMITTED`; Catalog 0.5.1 / 128 / 7 | P0/P1 archive v11 + Git/Catalog | TASK-05; completed |
| `TASK-07` Provider smoke tests | `DONE` | Выполнили frozen безопасный smoke и измерили transport reality | 35 bounded attempts; redacted raw envelope/manifests; sanitized fixture; explicit latency/failure/schema semantics | Helius/Solana Tracker free accounts; Jupiter/Raptor public research surfaces; cash USD 0 | Contracts, launcher/runtime modules, two raw runs outside Git, sanitized receipt/summary/fixture and Catalog records | 32 accepted successes, 1 invalid request, 2 retained provider 5xx; no retry/secret/transaction; local/CI/clean clone PASS | P0/P1 archive v12 + Git/Catalog | TASK-01, TASK-06; completed |
| `TASK-08` Lifecycle discovery pilot | `DONE_WITH_ACCEPTED_EXPLICIT_COVERAGE_BLOCKER` | Проверили, даёт ли bounded discovery probe unbiased lifecycle coverage | Pump event decoder, bounded Helius WSS + Tracker probe, redacted immutable evidence, Catalog registration | Existing free research access; cash USD 0 | 388 evidence records, tracked receipt/summary/fixture, Catalog 0.7.0 | Transport/durability/caps/local/CI/clean clone PASS; lifecycle coverage `NOT_TESTABLE_IN_WINDOW`; no retry/24h pilot; blocker accepted | P0/P1 archive v13 + Git/Catalog | TASK-07; completed |
| `TASK-09` PumpSwap Touch observation pilot | `DONE_TOUCH_ONLY` | Проверили, можно ли воспроизводимо наблюдать PumpSwap trade touch без подмены execution evidence | Touch contract; bounded WSS logs capture; one getTransaction enrichment; raw+virtual reserves; typed failures; immutable raw envelope; offline replay | Public Solana RPC/WSS; one exact authority; cash USD 0 | 258 raw rows; 75 decoded Buy/Sell events; tracked receipt/summary/fixture; Catalog 0.9.0 | One bounded run, no retry; raw outside Git; PR/main CI and local main 753/753 PASS; no fill/route/Net claim | P0/P1 archive v15 + Git/Catalog | TASK-08; completed |
| `TASK-10` Jupiter quote logger pilot | `DONE_QUOTE_COMPATIBILITY_ONLY` | Проверили bounded buy/reverse-sell quote compatibility без подмены quote на fill | Frozen quote contract; typed schema repair; two immutable raw runs; four buys plus four exact reverse sells; PIT/fees/failure semantics | Public keyless Jupiter; two exact authorities; nine GET calls; cash USD 0 | One preserved fail-closed row plus eight accepted quotes; tracked receipts/summaries/fixtures; Catalog 0.13.1 | Raw outside Git; zero retries/keys/accounts/credits/transactions; main CI/local 834/834 PASS; no fill/Net claim | P0/P1 archive v16 + Git/Catalog | TASK-07, TASK-09; completed |
| `TASK-11` Holder/deployer/bundler pilot | `DONE_RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY` | Проверили, можно ли PIT-safe сохранить один сырой entity-input slice без vendor inference | Frozen raw/adjusted/inferred contract; three-call Helius standard RPC snapshot; owner resolution; offline replay; Catalog and publication | Existing free Helius access; 3 calls; modeled 30 credits; cash USD 0 | Partial current snapshot: supply + top 20 token accounts + 20 owners; five projection rows; tracked fixture/receipt/summary; Catalog 0.14.0 | Raw outside Git; exclusions incomplete; adjusted concentration null; deployer/funder/bundler not tested; PR/main CI/local 862/862 PASS | P0/P1 archive v17 + Git/Catalog | TASK-07, TASK-08; completed |
| `TASK-12` Pilot orchestration | `DONE_DETERMINISTIC_OFFLINE_SUPERVISOR_CONTROLS` | Проверили минимальный fail-closed supervisor до sustained collection | `START_WITH_PATCH`; one allowlisted TASK-11 offline-preflight child; deterministic identity/lock; health, timeout, disk, output, lineage and typed stop controls; no auto-retry | Stdlib-first local Python; 7 supervisor attempts and 5 child spawns per acceptance suite; provider calls/cash 0 | Contract, thin module/CLI, seven-vector fixture, receipt/summary/tests; Catalog 0.15.0 | Seven frozen vectors PASS; PR/main CI 905/905 PASS; no automatic restart, 24–48h run, provider execution or production claim | P0/P1 archive v18 + Git/Catalog | TASK-08…11; completed |
| `TASK-13` Pilot audit | `DONE_BOUNDED_HISTORICAL_EVIDENCE_QUALITY` | Проверили качество реально сохранённой bounded history без выдуманного sustained pilot | Frozen 658-row population; deterministic identity/PIT/failure/projection audit; Catalog/publication | Local Python/DuckDB; provider calls/cash 0 | 9 exact files, 4,466,708 bytes, receipt/summary/tests; Catalog 0.16.0 | 658/658 identities complete; 0 duplicate IDs/PIT violations; 4 typed failures preserved; purchase requirement not established | P0/P1 archive v19 + Git/Catalog | TASK-12; completed |

### Gate G1

`G1 = PASS`, если:

- collector работает минимум 24–48 часов;
- raw data append-only;
- каждый record имеет source/timestamps;
- no-route/errors сохранены;
- pipeline воспроизводимо рестартует;
- расходы экстраполированы;
- нет секретов;
- critical data gap либо закрыт, либо оформлен blocker.

---


## P2 — Hypothesis Factory Foundation and Demand-Gated Data

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Зависимости |
|---|---|---|---|---|---|---|---|
| `TASK-14` Provider purchase decision | `DONE_DEFER` | Не покупаем capacity по догадке | Frozen DEFER decision | USD 0 | Accepted decision/receipt | Bounded demand required | TASK-13 |
| `TASK-15` Hypothesis-driven acquisition and Factory operating model | `DONE` | Данные, research, execution и monitoring подчинены hypothesis→cashflow | Contract, ARCH-INTENT-002, Factory Fit, Catalog 0.18.0 | USD 0 | Accepted architecture/receipt | PR/main CI 973/973; Source reconciliation pending | TASK-14 |
| `TASK-16` Hypothesis lifecycle and research memory contract | `DONE` | Не теряем происхождение, trials, negative results и производные идеи | Append-only lifecycle/provenance/derivation contract; bounded prior-work query; forward-only migration | Existing offline stack | Contract, fixture/query, tests, Catalog 0.19.0 | PR/main CI 1005/1005; no synthetic history or authority expansion | TASK-15 |
| `TASK-17` First bounded hypothesis cycle and data-need decision | `DONE` | Впервые использовали фабрику на одном реальном candidate до collection | Immutable family/version/origin/research cycle; reproducible prior-work query; exact live-data verdict | Existing offline stack; USD 0 | `LIVE_NON_RECONSTRUCTABLE_NEED`; future 192-call ceiling remains unauthorized | PR/main CI 1019/1019; Catalog 0.20.0; Factory Fit follow-up routed to TASK-17A | TASK-16 |
| `TASK-17A` Bounded execution-capacity quote panel | `DONE` | Проверили один named live-data need минимальной quote panel | One-member, three-window, four-notional buy/reverse-sell panel; exact timing repair and audit | Existing TASK-10 route; USD 0 | 32 total calls; 24 accepted, 8 excluded-retained; quote-only temporal replication supported | PR/main CI 1041/1041; Catalog 0.22.0; no quality/fill/alpha claim | TASK-17 |
| `TASK-18` Data-quality gate | `DONE` | Решили, годятся ли exact TASK-17A raw data для узкого replay | Deterministic 32-attempt audit; PIT/missingness/revision/overwrite checks; content-addressed backup, Drive raw-byte read-back and isolated restore | Existing offline stack + private Google Drive; USD 0 | `FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND`; exact snapshot recoverable | PR/main CI 1070/1070; Catalog 0.23.0; raw immutable; no general storage-reliability claim | TASK-17A |
| `TASK-19` Replay & leakage test | `DONE` | Восстановили decision-time truth без подсматривания в будущее | Frozen available-at cutoffs; deterministic 32-attempt lineage; 10 adversarial future-row tests | Existing offline stack; USD 0 | `REPLAY_SAFE`; 24 accepted, 8 excluded-retained, 12 complete quote pairs | PR/main CI 1096/1096; Catalog 0.24.0; one-member quote-only scope; no collection, strategy, fill or PnL | TASK-18 |


### Gate G2

`G2` remains a data-evidence gate, not the current next milestone. It can
pass only after an accepted hypothesis/data memo actually triggers bounded
collection and proves:

- dataset quality/coverage and outages are observable;
- revisions do not overwrite history;
- retention/backup and restore are tested for the bounded dataset;
- replay restores decision-time state without leakage;
- credits/storage/cash cost of the accepted bounded window is measured;
  duration follows information sufficiency, not a calendar target.

TASK-17A produced one bounded decision-bearing quote panel. TASK-18 accepted
its narrow offline quality and exact snapshot recovery. TASK-19 proved
deterministic point-in-time replay and frozen future-row leakage resistance.
TASK-20 froze reusable hypothesis-owned T0/T1/T2 collection and recovery
policy. TASK-21 then produced one recoverable 91-file forward dataset with a
known narrow effective sample, explicit gaps and measured bounded usage. G2 is
now satisfied only for this named narrow dataset; it is not a market-wide,
cross-regime, statistical-power or alpha claim.

## P3 — Conditional Hypothesis Data & Frozen Research Dataset

### Post-TASK-25 control status

- TASK-21 is accepted at final PR #29 merge
  `2ff5a9de4e78a8e64b23754ff59680a33c01d3cc`, tree
  `3af1179da534972ccf82073dfe1594858c69516e`.
- Verdict:
  `DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS_WITH_LIMITATIONS`.
- Frozen dataset: 91 files / 13 roots / 1,263,895 bytes; inventory SHA-256
  `aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae`.
- Five complete members span two complete nomination clusters; three
  incomplete members and three missing panels remain explicit evidence.
- Outcomes are unopened. Exact remote read-back and isolated full restore
  passed for recovery ZIP `6d895f259f0316df442932b38abf44a963a79e16e24793a4eb1af2c5f6748361`.
- Catalog: `0.26.1 / 374 / 4 / 4 / 8`; main CI: `1436/1436 PASS`, 51 skips.
- TASK-22 is accepted at PR #30 merge
  `90575accefbba7da534a6bd89b3652b2644a278b`, tree
  `f9cdd82ad8df427abe35e577889adaaca22b2d12`.
- Owner verdict: `SPLIT_READY_WITH_LIMITATIONS`.
- Frozen split `T22-SPLIT-T21-FROZEN-002` assigns exact R2 to development,
  uses no validation fold and keeps exact R3 as untouched default-deny
  holdout. Outcomes remained unopened during TASK-22.
- The actual pre-embargo gap is 1701.306244 seconds against a required 900;
  incomplete/gap evidence remains retained and no additional collection is
  required or authorized.
- Catalog: `0.27.1 / 396 / 4 / 7 / 8`; main CI: `1485/1485 PASS`, 51 skips.
- TASK-23 may begin only with its read-only Entry Gate. Development diagnostics
  cannot tune a strategy, and first R3 outcome access must append `CONSUMED`
  before any value read.
- TASK-23 is accepted at PR #31 merge
  `31c01640499be6b7e86a2fe638d9217c202861cc`, tree
  `6677878eb2b8195018ab217c6a9a429de5726563`.
- Owner verdict: `DIAGNOSTICS_READY_WITH_LIMITATIONS`. Exact R2 produced the
  frozen descriptive projection, but the effective independent cluster count is
  at most one and zero observed failure-state variation is not zero failure
  probability. R3 remained untouched and default deny.
- Catalog after TASK-23: `0.28.0 / 415 / 4 / 7 / 8`; lifecycle `9 / 55`;
  main CI run `30724006887`: `1526/1526 PASS`, 51 skips.
- TASK-24 is accepted at PR #32 merge
  `d82ccc6f673982f3ef214f0ec58396800ac7e167`, tree
  `ce034b4c2bd524cb14232aab2ca902eb19c9d3a5`.
- Owner decision: `STOP_NO_RELIABLE_ENTITY_SIGNAL`. The retained reversible
  partial graph has 4/12 predicted-positive capacity, zero corroborated claims,
  no opened false-positive audit and is `NOT_ADMISSIBLE` downstream.
- Catalog after TASK-24: `0.29.0 / 448 / 4 / 7 / 8`; lifecycle `9 / 56`;
  main CI run `30743164589`: `1626/1626 PASS`, 61 skips.
- Durable reactivation requires both a named consumer and a second independent
  raw event family under a new versioned objective; pagination or relaxed audit
  thresholds cannot reactivate the stopped v1 route.
- TASK-25 is accepted at PR #34 merge
  `a1c7e40f4febeee78ab544ee89edf248c4cd0454`, tree
  `b4280469913ae6463a9fd3f97870f62c594795d8`.
- Owner decision:
  `R2_OUTCOME_SURFACE_READY_FOR_BOUNDED_OWNER_COMPARISON_WITH_LIMITATIONS`.
  Exact R2 produced 108 outcomes: 80 supported and 28 unknown; 35 of 36
  fillable entries and all 36 quote exits are supported, with one explicit
  1030 ms latency exception and nine discrete path-risk outcomes.
- Actual fills, settled cashflow, complete fees, observed NetReturn, owner
  cashflow and strategy promotion remain unsupported. Exact R3 stayed
  `UNTOUCHED` default deny with zero paths or values opened.
- Catalog after TASK-25: `0.30.0 / 476 / 4 / 8 / 8`; lifecycle `9 / 56`;
  main CI run `30754489934` succeeded on the exact merge SHA; tracked-only
  validation passed 1741/1741 tests with 61 skips.

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-20` Freeze collection spec | `DONE_SPEC_READY_WITH_LIMITATIONS` | Заморозили reusable data spine, бюджет и восстановление до forward capture | 40 fields; deterministic universe/watchlist; T0/T1/T2; first availability; retention; create-only backup and restore policy | Existing stack; calls/cash 0 | Versioned spec/policy, coverage matrix, validators and receipt | 38/38 targeted plus 8/8 adversarial PASS; no collector/provider/runtime recovery claim | Archive v27 + Git/Catalog | TASK-19; completed |
| `TASK-21` Forward collection 30–45d | `DONE_DATASET_READY_WITH_LIMITATIONS` | Накопили первый bounded PIT-массив под именованный downstream split consumer | Versioned membership; bounded keyless capture; immutable gaps; freeze/effective sample; remote restore; post-A8 owner route | Existing collector/recovery stack; USD 0 | 91-file dataset + freeze manifest + effective-sample/recovery summary | 5 complete members / 2 clusters; 22 panels / 88 quote pairs / 176 attempts; outcomes unopened; no broad/power/alpha claim | Archive v28 + Git/Catalog/recovery bundle | TASK-20; completed |
| `TASK-22` Dataset freeze & split | `DONE_SPLIT_READY_WITH_LIMITATIONS` | Разделили узкий dataset на development/holdout и заморозили учёт расходования holdout | Exact R2 development / validation NONE / exact R3 untouched holdout; actual-time embargo; append-only access ledger | Existing Python/Catalog stack; external calls 0 | Content-addressed split manifest v2, holdout ledger v2, consumer profile, acceptance receipt | Outcomes unopened; no batch/member leakage; R3 default deny; 49/49 TASK-22 and 1485/1485 main CI PASS | Archive v29 + Git/Catalog | TASK-21; completed |
| `TASK-23` Cohort diagnostics | `DONE_DIAGNOSTICS_READY_WITH_LIMITATIONS` | Описали exact R2 без стратегии и без расходования R3 | Frozen R2-only inventory/quote/panel projections, missingness and dependence limits | Existing Python/Catalog stack; external calls 0 | Accepted report/tables/read receipts plus retained failed attempt | Effective independent clusters ≤1; zero failure variation not generalized; R3 untouched; main CI 1526/1526 PASS | Archive v30 + Git/Catalog | TASK-22; completed |
| `TASK-24` Entity graph v1 | `DONE_STOP_NO_RELIABLE_ENTITY_SIGNAL` | Проверили и остановили слабый entity route до downstream использования | Reversible pseudonymous graph, exact-wire recapture, capacity audit and redesign-or-stop decision | Existing stack; 21 bounded provider calls in A5R1; cash USD 0 | Retained partial evidence plus durable negative result | 4/12 predicted-positive, 0 corroborated, false-positive audit unopened, graph NOT_ADMISSIBLE; main CI 1626/1626 PASS | Archive v31 + Git/Catalog | TASK-21, TASK-23; completed with trigger-only reactivation |
| `TASK-25` Outcome engine | `DONE_OUTCOME_SURFACE_READY_WITH_LIMITATIONS` | Заморозили честные label/PIT/missingness semantics и построили exact R2 quote/path surface | Touch, Fillable(S), QuoteExit(S), unsupported RealizedVWAP/Net, typed missing/no-route/inventory/path states; R3 sealed | Existing Python/Catalog stack; external calls 0 | Frozen contract, deterministic engine, 108-outcome exact R2 surface and receipts | 80 supported / 28 unknown; 35/36 fillable, 36/36 quote exits, 9 path; no fills/settlement/observed NetReturn; main CI SUCCESS | Archive v32 + Git/Catalog | TASK-23, TASK-24; completed with TASK-26 follow-up |

### Gate G3

`G3 = PASS_WITH_ACCEPTED_LIMITATIONS`. TASK-25 consumed only exact R2 after a
frozen contract, kept R3 sealed and retained entity input as unavailable. Its
accepted quote/path surface is sufficient to enter TASK-26 contract work but
does not prove fills, NetReturn, signal, alpha or holdout fitness.

`G3 = PASS`, если:

- forward dataset frozen;
- chronological splits frozen;
- sample size/dependence known и MDE/precision/effective-sample gate выполнен либо принято `EXTEND_EVIDENCE/REDESIGN_DATA/CLOSE_HYPOTHESIS_FAMILY`;
- quote availability exists for intended notionals;
- entity/toxicity inputs point-in-time or clearly unavailable;
- no fatal universe bias.

---

## P4 — Labels, Execution Model and Frozen Experiments

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-25` Outcome engine | `DONE_OUTCOME_SURFACE_READY_WITH_LIMITATIONS` | Научили систему отличать price touch, quote feasibility, exit availability и unsupported fill/Net truth | Frozen label/PIT contract, deterministic synthetic engine, exact R2 reprojection and adversarial acceptance | Python/DuckDB; existing stack | Frozen contract plus 108-outcome R2 surface | 80 supported / 28 unknown; one latency exception; R3 sealed; fills/settlement/Net unsupported | Archive v32 + Git/Catalog | TASK-23, TASK-24; completed |
| `TASK-26` Execution-cost and NetReturn model | `DONE_EXECUTION_COST_MODEL_READY_WITH_LIMITATIONS` | Заморозили честную vocabulary для quote/attempt/landing/fill/fee/inventory/cashflow/NetReturn | Deterministic synthetic model, exact R2 aggregate projection and adversarial acceptance | Python; existing stack | Frozen contract, modules, receipts, schema and Catalog bindings | 35/36 quote-cost inputs ready; 36/36 lack complete fee and settled-cashflow truth; one latency blocker; no numeric/observed NetReturn; R3 sealed | Archive v33 + Git/Catalog | TASK-25; completed; next evidence gate selected separately |
| `TASK-26A` Execution-evidence completion gate | `DONE_EXECUTION_EVIDENCE_GAP_FROZEN_EXTEND_REQUIRED` | Проверили, можно ли честно считать numeric NetReturn из уже tracked evidence | Versioned evidence classes; deterministic inventory/gap matrix; adversarial rejects; Catalog transaction | Existing Python/Catalog/Baton stack; external calls 0 | Contract, schema, inventory, gap matrix, receipts and Factory Fit | 36/35/1 retained; fee/attempt/landing/inventory/settlement complete for 0/36; decision `EXTEND_EXECUTION_EVIDENCE`; TASK-27/R3/NetReturn unauthorized; main CI 1803 PASS | Archive v34 + Git/Catalog | TASK-26; completed; next bounded capture/extension task must be selected separately |
| `TASK-26B` Minimal execution witness route | `OWNED_CANARY_REQUIRED_NO_AUTHORITY` | Проверили historical/cache-first путь и доказали отсутствие owner attempt, retry, inventory и settlement truth | Deterministic route matrix and future witness specification | Existing Python/Catalog stack; external calls 0 | Decision evidence and no-authority witness contract | Historical third-party data covers only selected-chain fragments; owned canary is required but not authorized | Archive v35 + Git/Catalog | TASK-26A; repository merged at PR #39 |
| `TASK-26C` Owned canary readiness and authority gate | `DONE_READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS` | Подготовили предохранители для одного будущего technical canary, не создавая путь исполнения | Threat model, authority model, allowlist, reconciliation-before-retry, fake-only tests and owner packet template | Existing Python/Catalog stack; provider/wallet/transaction actions 0 | Offline readiness contract and 12-case safety matrix | `READY` не даёт authority; user Source smoke and owner acceptance close the task, while exact owner packet and a separate canary gate remain required | Archive v36 + Git/Catalog | TASK-26B; PR #40 merged; closed without execution |
| `OWNER_AUTHORITY_PACKET_BINDING_V1` | `OFFLINE_OWNER_PACKET_READY_NO_EXECUTION_AUTHORITY` | Сделали понятную форму будущего owner-review до любого риска деньгами | Deterministic offline packet; 12 exact inputs; proposed USD 3 all-in cap; adversarial review-only matrix | Existing Python/Catalog stack; provider/wallet/transaction actions 0 | Draft owner packet, exact refusals and Catalog bindings | Packet remains `OWNER_INPUT_REQUIRED`; no wallet, signer, provider, simulation, send, cash or TASK-27 authority | Archive v36 + Git/Catalog | TASK-26C; PR #41 implementation, PR #42/#43 delivery repair; next is exact owner inputs |
| `TASK-27` Baseline suite | `PLANNED_NOT_SELECTED` | Будущая проверка простых правил только на общем честном execution truth | Random eligible, first eligible, momentum, raw reclaim, no-trade, same gate | Python | `baseline_report_v1.md` | TASK-26A/B/C establish that a future owned canary needs authority and complete reconciled witness evidence before any baseline claim; no authority exists now | Future task file + report/config | TASK-25, TASK-26, TASK-26A; blocked pending bounded evidence extension |
| `TASK-28` RC-001 registry freeze | `PLANNED` | До test фиксируем первую family и каждый search degree | RC-001 card; hypotheses; trial ledger; feature catalog; parameters; primary targets; FDR families; invalidation; research budget | YAML/Markdown/Parquet | `research_cycles.yaml`, `hypothesis_registry.yaml`, `trial_ledger`, `feature_catalog.yaml`, `hypotheses_v1.yaml` | H13, H07/H01, H02/H10/H14 frozen; configs/hashes/budget recorded; unregistered trials=0 | Task file + registries/config | TASK-27; 4–7 ч |
| `TASK-29` H13 composite veto | `PLANNED` | Проверяем, убирает ли токсичность худшие убытки без убийства победителей | Baseline vs each veto vs composite; creator/entity/bundle/route/depth | Python | `EXP-H13-report.md` | OOS validation effect, CVaR improvement, right-tail retention, signal frequency; no test tuning | Task file + report | TASK-28; 6–12 ч |
| `TASK-30` H07/H01 liquidity-retention continuation | `PLANNED` | Проверяем, важнее ли сохранённый выход, чем красивый график | Matched price-path cohorts; depth/route retention incremental effect | Python | `EXP-H07-H01-report.md` | Incremental effect after price/age/regime controls; intended-size NetReturn | Task file + report | TASK-28; 6–12 ч |
| `TASK-31` H02/H10/H14 controlled pullback | `PLANNED` | Проверяем исправленную исходную идею отката | Drawdown buckets, reclaim, sell-pressure decay, repeat buyers, route state | Python | `EXP-H02-report.md` | Positive/negative result on frozen validation; no single-week/winner dependence | Task file + report | TASK-28, TASK-30; 6–12 ч |
| `TASK-32` Regime ablation | `PLANNED` | Проверяем, добавляет ли режим ценность или просто маскирует слабый сигнал | SOL/cohort/execution regimes; with/without interaction | Python | `regime_ablation.md` | Incremental effect and stability; no hindsight threshold | Task file + report | TASK-29, TASK-30, TASK-31; 4–8 ч |
| `TASK-33` Frozen test + global multiplicity | `PLANNED` | Один раз открываем отложенную выборку и учитываем весь search | Walk-forward, cluster bootstrap, FDR, global trial count, Reality Check/SPA where applicable, PBO/DSR diagnostics where supported, sensitivity/cost stress | Python | `frozen_test_report_v1.md`, updated holdout/trial ledgers | No retraining; test marked consumed; every run accounted; full negative results retained; uncertainty/kill conditions explicit | Task file + final report/ledgers | TASK-29, TASK-30, TASK-31, TASK-32; 7–14 ч |
| `TASK-34` RC-001 research decision gate | `PLANNED` | Выбираем судьбу candidate/family и следующий самый дешёвый цикл | Red Team Council; evidence, execution, complexity, capacity, research/spend budget, data coverage | Decision memo | `G4_decision.md`, updated strategy/decision-negative registries | Exactly one `PROCEED/REDESIGN_DATA/PIVOT_FAMILY/EXTEND_EVIDENCE/PAUSE/CLOSE_HYPOTHESIS_FAMILY`; one primary paper candidate max; next RC/holdout policy if pivot | Task file + decision/registries | TASK-33; 3–6 ч |
| `TASK-34A` Documentation foundation and AI/operator runbooks | `PLANNED_TRIGGERED` | Делаем фундамент и повторяемые операции понятными владельцу и следующему агенту | Generated contract/Catalog reference, architecture decision index, dataset/replay examples, start/stop/backup/restore/incident runbooks, update check | Repository-native static docs; hosting later | Versioned docs site/source and tested runbooks | Activate by first unattended runtime, second operator or repeated doc friction; generated truth avoids duplicate manual docs | Task file + docs/check | Trigger; before unattended runtime at latest |

### Gate G4

Для `PROCEED` стратегия должна одновременно:

- иметь `NetEV > 0` в большинстве независимых folds;
- не иметь резко отрицательной медианы без обоснованной convexity;
- переживать realistic cost/latency stress;
- не зависеть от одной недели/deployer/regime;
- иметь приемлемый worst fold/CVaR;
- не получать >35% PnL от top-3 trades либо иметь отдельную convexity rationale;
- сохранять edge на $10/$25/$50;
- иметь реальный sell-route evidence;
- пройти leakage/survivorship audit.

Если нет — `REDESIGN_DATA`, `PIVOT_FAMILY`, `EXTEND_EVIDENCE`, `PAUSE` или `CLOSE_HYPOTHESIS_FAMILY`. Ни один из них не открывает paper trading. Новый cycle получает новый `RC-NNN`, trial/negative ledger и forward holdout policy; старый test не становится untouched повторно.

---

## P5 — Paper Trading and Shadow Execution

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-35A` Production-lite Control Plane and Owner Cockpit foundation | `PLANNED_TRIGGERED` | Даём владельцу удалённый пульс paper/shadow системы, alerts и recovery до долгого наблюдения | Reproducible deploy/rollback; provider/data/clock/quote/reconciliation/disk/backup/cost/quota health; deduplicated alerts; read-only owner view | Measured replaceable Linux runtime; purchase/deploy separate | One bounded remote paper/shadow runtime + owner pulse | Stable read contracts; required before TASK-38; no wallet/signer/transaction/strategy activation authority | Task file + runbook/read model | Stable read contracts; before TASK-38 |
| `TASK-35` Live feature engine | `PLANNED` | Переносим ровно те же признаки из backtest в реальное время | Shared feature code, event-time state, config hash, clock/lag metrics; feature-catalog promotion | Existing collector | `live_features.py`, updated feature/strategy registries | Same fixtures produce same historical/live features; no notebook-only logic; strategy version frozen | Task file + tests/registry delta | TASK-34 with decision `PROCEED`; 4–8 ч |
| `TASK-36` Paper signal engine | `PLANNED` | Создаём первый versioned bot instance без денег | Decision record, reason codes, intended entry/exit, Telegram alert; bot registry/environment/risk-zero config | Telegram | `paper_engine.py`, signal ledger, bot registry entry | Every signal immutable; exact strategy/bot/config hashes; no discretionary deletion | Task file + config + sample cards | TASK-35; 4–8 ч |
| `TASK-37` Shadow quote/execution | `PLANNED` | На каждый сигнал получаем реальные buy/sell quotes и имитируем отправку | Jupiter order/build, simulation, quote age, fees, route, hypothetical retries | Jupiter Free/Developer | `shadow_execution_log`, dashboard | Signal→quote latency, quote deterioration, no-route and simulated failures recorded | Task file + weekly report | TASK-36; 5–10 ч |
| `TASK-38` Shadow observation period | `PLANNED` | Даём стратегии торговать «на бумаге» на новых данных | 20–50 signals minimum and preferably ≥30 days; no rule changes mid-version | 24/7 runtime | Live paper/shadow dataset | Sample size/effective cohorts reported; all versions frozen; outages included; owner health/recovery path active | Task file + compact report | TASK-37 and TASK-35A; 30 дней or sample gate |
| `TASK-39` Execution calibration | `PLANNED` | Сверяем модель бэктеста с реальными quotes | Fit latency/landing proxy, slippage distributions, fee state, route survival | Python | `execution_model_v2.md/code` | Predicted vs observed quote/slippage/error distributions within declared tolerance | Task file + calibration report | TASK-38; 4–10 ч |
| `TASK-40` Shadow validation decision | `PLANNED` | Решаем судьбу strategy version и можно ли рисковать $10 | Compare paper NetEV, realization ratio, break-even costs, drift, concentration, operator burden | Decision memo | `G5_decision.md`, registry status | Explicit `PASS/REDESIGN_DATA/RETIRE_STRATEGY/PAUSE`; no fatal security/execution issue; lifecycle updated | Task file + decision | TASK-39; 3–6 ч |

### Gate G5

`G5 = PASS`, если:

- paper rules identical to tested config;
- реальные quotes доступны на вход и выход;
- observed p90 execution cost ниже break-even cost с запасом;
- no-route/failed-exit не уничтожают результат;
- live performance не объясняется только несколькими событиями;
- data/strategy drift понятны;
- strategy-specific execution model откалибрована;
- real-money risk budget может быть ограничен без изменения логики.

---

## P6 — Security and Micro-Live

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-41` Threat model & risk policy | `PLANNED` | До денег описываем, как система может сломаться | Threat model, hot-wallet cap, daily loss, program allowlist, duplicate-send, stale data, provider divergence | Markdown/config | `threat_model.md`, `risk_limits_v1.yaml` | Every critical risk has prevention/detection/response; owner assigned | Task file + sanitized policy | TASK-40 with decision `PASS`; 3–6 ч |
| `TASK-42` Signer isolation | `PLANNED` | Ключ не находится рядом с исследовательским кодом | Separate signer service, least privilege, key storage, transaction policy, no seed in `.env`/chat/repo | Minimal service | `signer_runbook.md`, integration tests | Research process cannot read key; signer rejects policy violations | Task file + interface/tests, без секретов | TASK-41; 6–15 ч |
| `TASK-43` Dry-run and canary transactions | `PLANNED` | Проверяем отправку технических транзакций без торговой стратегии | Devnet where meaningful + tiny mainnet canaries; idempotency; confirmation; failure logs | Helius/Jupiter | `canary_report.md` | No duplicate sends; fee/landing logs correct; kill switch tested | Task file + report | TASK-42; 3–8 ч |
| `TASK-44` Micro-live $10 | `PLANNED` | Запускаем один bot instance на минимальном размере | Manual approval first 20 trades; one immutable strategy version; bot deployment/capital/risk hashes; hard caps; real fills/exits | Hot wallet with limited funds | Live trade ledger + bot registry | Every trade matches strategy/bot/config; daily loss enforced; reconciliation complete; instance independently pausable/retirable | Task file + sanitized performance report | TASK-43; sample-dependent |
| `TASK-45` Micro-live audit | `PLANNED` | Проверяем, совпала ли реальность с paper/shadow | Fill reconciliation, slippage, landed/fail, PnL, drift, incidents | Python | `micro_live_audit_v1.md` | No unexplained discrepancy; actual cost within model band; incidents closed | Task file + report | TASK-44; 3–6 ч |
| `TASK-46` Size step $25/$50 | `PLANNED` | Увеличиваем размер только при неизменном качестве | Capacity test; price impact; fill and exit availability; risk-budget check | Same infra | `size_step_report.md` | No material degradation vs $10; risk limits unchanged or explicitly revised | Task file + decision | TASK-45; sample-dependent |

### Gate G6

Micro-live валидирован, если:

- минимум 20–50 реальных trades либо обоснованный event sample;
- фактические fills и costs согласуются с shadow model;
- нет критического security/duplicate-send incident;
- дневной лимит и kill switches доказанно работают;
- actual NetEV не противоречит paper с учётом uncertainty;
- увеличение notional не разрушает execution.

---

## P7 — Business Economics, Factory Operations, Portfolio or Scoped Closure

| ID | Статус | Что вы делаете простыми словами | Техническая работа | Инструменты / покупка | Выход | Definition of Done | Memory package | Зависимости / трудоёмкость |
|---|---|---|---|---|---|---|---|---|
| `TASK-47` Capacity & full business economics | `PLANNED` | Проверяем, создаёт ли весь проект cash, а не только красивый PnL | Realized project FCF; rolling 30/90d; capital/drawdown/CVaR; capacity curve; cash infra; shadow time cost; operational hours; realization ratio | Reports | `economics_v1.md`, KPI scorecard | Conservative owner FCF/capacity/risk case positive, `PAUSE`, or exact scoped closure condition; no hidden time/infra cost | Task file + report | TASK-46 |
| `TASK-48` Infra upgrade decision | `PLANNED` | Решаем, нужна ли более быстрая инфраструктура | Latency sensitivity, missed opportunities, gRPC/WSS economics | Helius Business / gRPC only if justified | `ADR-infra-upgrade.md` | Upgrade tied to measured incremental NetEV > total cost/risk | Task file + ADR | TASK-47 |
| `TASK-49` Multi-strategy portfolio | `DEFERRED` | Добавляем второй bot только после второго независимого evidence path | Strategy/bot registries; correlation, shared failure/route/capacity risk, conflict resolution, capital allocation | Existing stack | Portfolio simulator + capital policy | ≥2 independently validated strategy versions; joint CVaR/correlation/capacity and incremental FCF validated; no bot-count vanity | Task file + report | TASK-47 plus explicit second validated-strategy decision |
| `TASK-50` Alpha Factory operationalization | `DEFERRED` | Делаем повторяемыми research cycles и production-lite operations | RC templates/automation; registry validators; monitoring, incidents, releases, rollback, backups, calibration/retirement cadence | Depends | Factory operations manual + generated scorecard | Stable releases; automatic registry/holdout/state/KPI checks; one-click pause/rollback; auditable retire/pivot lifecycle | Task file + runbook | TASK-47, TASK-48 |
| `TASK-51` Scoped close or archive | `PLANNED` | Закрываем ровно hypothesis/strategy/bot/family/domain/project, которое опровергнуто | Preserve data/code/trials/negative results; stop spend/runtime; postmortem; reusable assets; next-domain option value | Free | scoped postmortem + registry/state updates | Closure level/evidence/budget defined; no history rewritten; costs stopped; reusable assets and consumed holdouts documented | Task file + postmortem | Event-driven exception: any gate whose exact `CLOSE_*` verdict is recorded; not part of normal DAG |

---

# 6. Parallel Workstreams

Некоторые потоки могут идти параллельно, но не должны обходить gates.

| Workstream | Можно вести параллельно | Нельзя делать раньше времени |
|---|---|---|
| Data collection | Только после accepted hypothesis/data memo; historical/cache first | Нельзя собирать «на всякий случай», запускать automatic seven-day warehouse или менять cadence/fields без version/availability |
| Provider research | Да | Нельзя покупать дорогой тариф без measured bottleneck |
| Entity graph | Да после raw holder/deployer data | Нельзя использовать current PnL labels как historical truth |
| Execution logging | Да, как можно раньше | Нельзя подписывать реальные trades до G5/security |
| Hypothesis ideation | Да, в backlog/registry | Нельзя смотреть variants на data вне trial ledger или использовать consumed test как untouched; новый mechanism → RC/version/holdout policy |
| ALBS campaign scoring | Отдельно | Нельзя переносить ALBS outputs в intraday labels |
| Macro regime | Собирать можно рано | Нельзя использовать как hindsight-фильтр |
| UI/dashboard | Read contracts and owner questions проектируются рано; text/SQL pulse допустим | Web UI не раньше stable truth; UX/operability нельзя откладывать до конца |
| Business economics | Да, cash/time/credits собираются с первого task | Нельзя ждать TASK-47, чтобы заметить, что data/infra path уже не окупаем |

---

# 7. Task Status Rules

| Статус | Однозначное значение |
|---|---|
| `PLANNED` | Задача описана, но зависимости не закрыты |
| `READY` | Все зависимости закрыты, можно начинать |
| `IN_PROGRESS` | Работа начата, owner и next action известны |
| `BLOCKED` | Нельзя продолжить без конкретного внешнего условия |
| `IMPLEMENTED_UNVERIFIED` | Артефакт существует, но DoD/validation не пройдены |
| `VALIDATED` | Acceptance criteria пройдены; может оставаться интеграция |
| `DONE` | Реализовано, проверено, отражено в roadmap, handoff готов |
| `DEFERRED` | Осознанно отложено |
| `REJECTED` | Проверено/рассмотрено и отклонено |
| `SUPERSEDED` | Заменено более новым решением; хранится исторически |

## 7.1. Правило перехода

```text
PLANNED → READY → IN_PROGRESS
→ IMPLEMENTED_UNVERIFIED
→ VALIDATED
→ DONE
```

`BLOCKED`, `REJECTED`, `DEFERRED`, `SUPERSEDED` — отдельные ветки.

---

# 8. Project Sources Runtime Policy

## 8.1. Ограничения и внутренний budget

Официальная OpenAI help page на 2026-07-18 указывает для Plus до 25 файлов на проект и не более 10 файлов в одной upload operation. Это изменяемый внешний факт, а не архитектурная константа. Внутренние thresholds ниже принадлежат `canonical_manifest.yaml` и действуют независимо от UI limit:

```text
TARGET_MAX_SOURCES = 16
WARNING_AT = 18
COMPACTION_REQUIRED_AT = 20
MIN_FREE_RESERVE = 5
```

При `18` Sources перед новой загрузкой обязателен inventory/compaction plan. При `20` новая загрузка запрещена до возврата к `≤16`.

## 8.2. Постоянное ядро

| Категория | Файл |
|---|---|
| Registry | `canonical_manifest.yaml` |
| Constitution | canonical Operating System |
| Control | `roadmap.md` |
| Living reality | `current_system_state.md` |
| Blueprint | текущая canonical research blueprint |
| History | последний `task_archive_P*.md` |
| Work contract | active `task_XX_*.md` |

Нормальный core set: 7 файлов. Седьмой Source оправдан отдельной семантической ролью: он хранит фактическое текущее состояние, которое нельзя надёжно вывести только из плана, ADR или task history. Это всё ещё заметно ниже внутреннего target `≤16`.

## 8.3. Активное рабочее окно

Дополнительно держать только 2–8 materially relevant файлов:

- direct dependency contract;
- schema/data contract;
- current YAML config;
- compact validation/gate report;
- small fixture;
- relevant ADR;
- repository tree/commit manifest.

## 8.4. Lifecycle task artifacts

```text
PLANNED → без отдельного Source, если roadmap достаточен
READY/IN_PROGRESS → отдельный active task record
DONE → decisions интегрированы → record добавлен в phase archive
→ full original/code/evidence сохранены в Git/local archive
→ индивидуальный task Source удалён, если не нужен дальше
```

Один phase archive может содержать несколько завершённых task records. Он immutable по смыслу: новая консолидация создаёт новую версию, старая остаётся во внешнем архиве.

## 8.5. Не держать постоянно

- все индивидуальные task-файлы;
- ALBS и иные specialist modules вне активной задачи;
- superseded OS/roadmaps/manifests;
- raw datasets и verbose logs;
- notebooks с embedded data;
- binaries/container images/virtual environments;
- повторяющиеся reports;
- secrets, `.env`, API keys, private keys.

## 8.6. Источник implementation truth

До создания Git repository полные файлы хранятся в локальном versioned bundle. После TASK-03 source of truth для кода/SQL/config/tests — private Git repository + commit hashes. Project Sources содержат contracts, компактное evidence и active context, но не заменяют repo. `catalog/catalog_manifest.yaml` разрешает stable IDs в Git/data/DB/source/runtime objects, но не переопределяет их bytes или domain truth. `current_system_state.md` — compact catalog checkpoint и отражение repo/runtime evidence; при конфликте оно не переопределяет первичную реальность.

## 8.7. Как ИИ понимает реальный прогресс

Task record или archive entry должен содержать:

```text
task_id/status/objective
inputs/scope/decisions
implementation/artifacts + paths + versions/commit
actual tests and results
Definition of Done
limitations/blockers
architecture/access delta or STATE_CHANGE=NONE
next handoff/change log
```

Без acceptance evidence задача не считается подтверждённо завершённой.

---

# 9. Artifact Naming Convention

```text
roadmap.md
task_00_memory_audit.md
task_01_source_manifest.md
task_02_workstation_bootstrap.md
...
ADR-001-mvp-stack.md
sources_v1.yaml
schema_v1.sql
data_contract_v1.md
collection_spec_v1.yaml
dataset_split_v1.yaml
experiment_registry_v1.md
hypotheses_v1.yaml
hypothesis_data_coverage_matrix_v1.md
research_cycles.yaml
trial_ledger.parquet
feature_catalog.yaml
strategy_registry.yaml
bot_registry.yaml
holdout_ledger_v1.yaml
reuse_candidate_registry.yaml
risk_limits_v1.yaml
G1_pilot_gate_report.md
G2_data_gate_report.md
G4_research_decision.md
G5_shadow_decision.md
G6_micro_live_decision.md
```

Версия повышается только при содержательном изменении, а не при исправлении опечатки.

---

# 10. Структура репозитория

```text
solana_alpha_lab/
├── README.md
├── pyproject.toml
├── Makefile
├── docker-compose.yml
├── .env.example
├── configs/
│   ├── sources_v1.yaml
│   ├── collection_spec_v1.yaml
│   ├── hypotheses_v1.yaml
│   ├── data_option_tiers_v1.yaml
│   └── risk_limits_v1.yaml
├── registries/
│   ├── research_cycles.yaml
│   ├── hypothesis_registry.yaml
│   ├── trial_ledger.parquet
│   ├── feature_catalog.yaml
│   ├── strategy_registry.yaml
│   ├── bot_registry.yaml
│   ├── holdout_ledger.yaml
│   ├── reuse_candidate_registry.yaml
│   └── decision_negative_ledger.md
├── schemas/
│   ├── schema_v1.sql
│   └── data_contract_v1.md
├── data/
│   ├── raw/              # append-only, gitignored
│   ├── canonical/        # gitignored
│   ├── manifests/
│   └── fixtures/         # только маленькие обезличенные samples
├── src/solana_alpha_lab/
│   ├── ingestion/
│   ├── normalization/
│   ├── lifecycle/
│   ├── entity_graph/
│   ├── features/
│   ├── labels/
│   ├── execution/
│   ├── experiments/
│   ├── paper/
│   ├── shadow/
│   ├── signer/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   ├── test_point_in_time.py
│   ├── test_no_future_leakage.py
│   └── test_fee_units.py
├── reports/
│   ├── daily/            # обычно не грузить в GPT
│   ├── gates/
│   ├── experiments/
│   └── business_kpi/
├── docs/
│   ├── current_system_state.md
│   ├── decisions/
│   ├── tasks/
│   └── runbooks/
└── scripts/
```

---

# 11. Acceptance Thresholds — initial, subject to validation

Это не «истинные рыночные пороги», а engineering thresholds для качества конвейера.

| Область | Initial threshold |
|---|---|
| Timestamp completeness | 100% для critical tables |
| Source/version completeness | 100% critical rows |
| Silent exception loss | 0 допустимых |
| Duplicate logical events | <0.1% после dedupe; raw duplicates не удалять физически |
| Clock drift | <1 сек на runtime host либо явно измерено |
| Collector availability pilot | ≥95% без скрытых провалов |
| Raw replay sample | 100% выбранных samples воспроизводятся |
| Future leakage tests | 100% pass |
| Quote notionals | Минимум $10/$25/$50; $100 diagnostic |
| Quote sides | Buy и sell |
| No-route/error preservation | 100% |
| Frozen test reuse | 0 повторных открытий для tuning |
| Unregistered trials/variants | 0; иначе promotion blocked |
| New-field historical backdating | 0; first reliable availability mandatory |
| Hypothesis data coverage | Reported per family; no invented universal pass threshold |
| PnL concentration | Top-k + leave-one-cluster-out обязательны; 35% — diagnostic trigger, не universal pass/fail |
| Paper/shadow minimum | 20–50 signals и желательно ≥30 дней |
| Micro-live initial notional | $10 |
| Real money before G5 | 0 |
| Secrets in repo/project memory | 0 |

Threshold может быть изменён только decision record.

---

# 12. Kill Switches проекта

Немедленно остановить переход к следующему gate, если:

1. невозможно восстановить, какие данные были доступны в decision time;
2. мёртвые/no-route токены исчезают из universe;
3. outcome использует свечную цену без sell execution;
4. API provider silently revises history без raw archive;
5. test fold был использован для настройки;
6. execution cost считается неправильными единицами;
7. global network fail-rate подставлен как фиксированная strategy probability;
8. результат держится только на нескольких winners и это скрыто;
9. private key попал в research environment/chat/repo;
10. provider/strategy drift нельзя отличить от alpha decay;
11. платная инфраструктура покупается без измеренного bottleneck;
12. complexity растёт быстрее evidence;
13. quote/AMM fee или price impact повторно вычитается из уже fee-inclusive output amount;
14. no-route exit удаляет позицию вместо unresolved-inventory/recovery-bound accounting;
15. хотя бы один просмотренный run/variant отсутствует в trial ledger или consumed test назван untouched;
16. новый field/provider/cadence не имеет option-value tier, named consumer, cost cap и first reliable availability;
17. hypothesis, strategy version и bot instance смешаны в один mutable config/status;
18. неудача одной family названа закрытием domain/project без budgeted closure memo;
19. число bots/data/code используется как KPI вместо cashflow/risk/learning economics;
20. значимый component пишется с нуля без current reuse candidate scan и rejected-candidate evidence;
21. third-party code/data принят без license/terms, pin/hash, security/signer, PIT/replay и exit-TCO review.

Действие:

```text
STATUS = BLOCKED
ACTION = REPAIR / REDESIGN_DATA / PIVOT_FAMILY / PAUSE / exact CLOSE_*
```

---

# 13. Execution Session Map

## Completed Session 1 — TASK-01 Source/provider manifest

> Historical execution template. Accepted reality is in P0 archive: accounts/calls/purchases remained `0`; no provider runtime was executed.

### Перед началом

ИИ повторно валидирует постановку через Task Entry Gate и выдаёт полную Beginner Task Brief. Пользователь не обязан сам разбираться, какой provider нужен, регистрироваться во всех сервисах или выбирать между несколькими равноправными вариантами.

### Пользователь

1. После подготовленного ИИ shortlist создаёт только действительно нужные бесплатные аккаунты; платные планы не покупает.
2. Хранит API keys только локально; не вставляет их в чат, screenshots или Project Sources.
3. Сообщает обезличенно и без key fragments:
   - какой free plan виден;
   - dashboard limits/credits;
   - региональные или платёжные blockers;
   - доступность нужных API products.

### ИИ

- объясняет задачу и термины простым языком, затем ведёт по одному copy-paste шагу;
- повторно проверяет official docs/dashboard facts;
- создаёт source-domain matrix;
- создаёт `hypothesis_data_coverage_matrix`: T0/T1/T2, irrecoverability, reuse, first reliable availability, base/trigger cadence, named consumers и cost;
- инвентаризирует готовые public/OSS historical catalogs и явно отделяет discovery/backfill value от отсутствующих live-availability semantics;
- создаёт sanitized `sources_v1.yaml`;
- формирует provider decision/cost snapshot и machine-readable `provider_smoke_spec_v1.yaml`;
- не выполняет provider requests: фактический controlled smoke принадлежит `TASK-07`;
- обновляет TASK-01, roadmap и manifest;
- обновляет `current_system_state.md` и access ledger либо фиксирует `STATE_CHANGE=NONE`;
- компактизирует временные artifacts после DONE.

### Готовность

Оплаченный тариф не нужен. Нужны verified provider roles, account availability, timestamp semantics, bounded reusable-data/quote policy и безопасный smoke-test plan.

## Completed Session 2 — TASK-03 repository, controls and Codex bridge

> Historical execution template. Accepted reality is private `main` at `f8ff483…`, CI PASS and clean-clone `131/131 PASS`.

### Пользователь

- после Entry Gate выбирает обычную локальную папку без передачи absolute path в чат;
- создаёт/подтверждает private GitHub repository только по точному UI-шагу;
- разрешает доступ только к named repository;
- открывает ту же локальную папку в Codex после создания `AGENTS.md` и baseline controls;
- подтверждает push/external writes и не передаёт credentials.

### ИИ

- проверяет актуальность TASK-03 и выдаёт staged Beginner Task Brief;
- создаёт repo/security/dependency baseline;
- фиксирует Work↔Codex bridge через `AGENTS.md`, active task и handoff receipt;
- создаёт Project Asset Catalog schemas/root/initial records/generator/validators;
- импортирует TASK-01/02 с pre-Git provenance и исходными hashes;
- создаёт registry skeletons;
- валидирует fake-secret rejection, generated views, clean clone, CI and commit;
- обновляет living state/catalog checkpoint.

### Готовность

Repository private; clean clone PASS; no secrets; Catalog resolves mandatory assets; TASK-01/02 lineage reconciles; one bounded Codex loop produces a validated diff/test/handoff; provider calls remain zero.

## Historical Session 3 — TASK-04 architecture + reuse decision

### Пользователь

- подтверждает только bounded repository writes/commit/push после read-only Entry Gate;
- не покупает software/infra и не передаёт credentials;
- принимает один рекомендуемый stack verdict после evidence, а не выбирает из необработанного списка.

### ИИ

- фиксирует bounded MVP component list и named consumers;
- читает current official repositories/docs/licenses/releases;
- применяет `ADOPT → WRAP → FORK → BUILD` по fit/PIT/replay/license/security/signer/maintenance/pin/SBOM/TCO/lock-in/exit;
- запускает минимальный offline fixture-based prototype только при неустранимой desk-review неопределённости;
- создаёт ADR-001, decision matrix, append-only reuse registry и catalog delta;
- доказывает tests/CI/handoff и не заявляет TASK-05 implementation.

### Готовность

Every major MVP component has an accepted or rejected candidate, immutable pin/license/owner/exit evidence and an explicit build justification where needed. Provider calls, spend and signer access remain zero.

## Completed Session 4 — TASK-05–07

### Пользователь

- запустил проект локально и выдавал authority по отдельным атомам;
- создал Helius Free и Solana Tracker Free research access;
- сохранил credentials только в локальной user-controlled boundary;
- разрешил exact bounded smoke, не раскрывая keys;
- подтвердил USD 0, отсутствие wallet/signer/transaction actions и принял
  typed provider failures без их маскировки.

### ИИ

- создал и опубликовал schema/data contracts TASK-05;
- создал и опубликовал redaction-first raw storage boundary TASK-06;
- выполнил Entry Gate, runtime/transport contract и 35-attempt smoke TASK-07;
- сохранил 2 immutable raw runs и tracked sanitized evidence;
- измерил response bytes, client elapsed, attempts and modeled credits;
- зарегистрировал TASK-07 outputs в Catalog 0.6.0;
- не рекомендовал paid tier: measured blocker для покупки отсутствует.

## Completed Session 5 — TASK-08 and CTRL-BATON technical control

### Пользователь

- разрешил один bounded TASK-08 lifecycle probe и принял явный coverage
  blocker без retry/24-hour expansion;
- провёл fail-closed staged GitHub Baton publication through PR #1;
- явно отложил GitHub Pro/private branch protection как не оправданные для MVP;
- разрешил merge-commit-only с post-merge GitHub/local validation.

### ИИ

- сохранил TASK-08 transport evidence и
  `NOT_TESTABLE_IN_WINDOW` без подмены на empty/zero/`NO_ROUTE`;
- реализовал GPT-owned Baton routing with Cursor `EXECUTION_ONLY`;
- провёл exact feature/PR/main lifecycle, canonical Git-byte repair and
  local-main topology repair;
- подтвердил merge `a9726de…`, exact parents/tree/84 paths, PR/main CI and
  local validation 607/607 PASS;
- сохранил Catalog 0.8.4 / 190 / 4 / 4 / 7 и не начал TASK-09.

### Готовность

GitHub Baton технически доступен с explicit compensating controls. Platform
branch protection не куплен и не заявлен. TASK-09 остаётся READY/NOT_STARTED;
первый атом только read-only.

## Completed Session 6 — TASK-09 PumpSwap Touch observation

### Пользователь

- принял Entry Gate `START_WITH_PATCH`: TASK-09 измеряет Touch, а executable
  Fillable/`NO_ROUTE` переносится в TASK-10;
- выдал exact local-write, one-run public RPC/WSS, commit, publication and merge
  authority with cash cap USD 0;
- не передавал credentials, wallet, signer or transaction authority.

### ИИ

- заморозил Touch contract and deterministic fixtures before the live run;
- выполнил ровно один bounded run `t09a4-20260727T184740Z` без retry;
- сохранил 258 redacted raw rows outside Git and replayed 75 decoded PumpSwap
  Buy/Sell events while preserving failures and raw/virtual reserves;
- зарегистрировал tracked contracts/evidence in Catalog 0.9.0 / 205 / 4 / 4 / 7;
- опубликовал feature `e4694e4…`, merged PR #7 at `c99c76f…`, and confirmed
  PR/main CI plus local main 753/753 PASS.

### Готовность

TASK-09 закрыт как `DONE_TOUCH_ONLY`. Это доказательство наблюдаемого trade
touch, не fillability, RealizedVWAP, NetReturn или route availability.
TASK-10 READY; его первый атом read-only and separately gated.

## Completed Session 7 — TASK-10 Jupiter quote compatibility

### Пользователь

- принял bounded quote-only estimand and separate Touch/Fillable/Net boundary;
- выдал exact authority для одного fail-closed pilot и затем для
  `T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2`;
- разрешил PR #13 merge после local/full validation;
- не передавал credentials, wallet, signer or transaction authority.

### ИИ

- заморозил typed quote contract, atomic buy panels and dependent exact reverse
  sells before each external run;
- сохранил первый `INVALID_RESPONSE/UNCLASSIFIABLE_SCHEMA_DRIFT` immutable and
  added only the observed typed optional fields offline;
- выполнил accepted v2 panel: four buys plus four reverse sells, zero retries;
- зарегистрировал contracts, raw logical pointers and tracked evidence in
  Catalog 0.13.1 / 228 / 4 / 4 / 7;
- опубликовал feature `d853392…`, merged PR #13 at `f384395…`, and confirmed
  main CI plus local main 834/834 PASS.

### Готовность

TASK-10 закрыт как `DONE_QUOTE_COMPATIBILITY_ONLY`; activation manifest 2.7
подтверждён user smoke. Quote recovery worsened from 96.578340% at USD 10 to
88.811179% at USD 100; this is a capacity warning, not Fillable, realized
loss, NetReturn or alpha.

## Completed Session 8 — TASK-11 raw entity-input feasibility

### Пользователь

- принял `START_WITH_PATCH`: сначала один raw top-account concentration slice,
  без обещания полного holder/deployer/bundler результата;
- выдал exact offline-contract, three-call Helius pilot, publication and PR #14
  merge authority with cash cap USD 0;
- не передавал wallet, signer, transaction, purchase or deployment authority.

### ИИ

- заморозил separate raw/adjusted/vendor/inferred semantics и PIT availability;
- выполнил один three-call run `t11a3-20260728T102537Z`, сохранил raw outside
  Git и воспроизвёл три RPC rows offline;
- разрешил владельцев 20/20 token accounts и создал пять TASK-05-compatible
  projection rows, не подменив account concentration на economic ownership;
- сохранил adjusted concentration null при неполном exclusions inventory и
  оставил deployer/funder/bundler `NOT_TESTED`;
- зарегистрировал contracts/runtime/evidence в Catalog 0.14.0 / 242 / 4 / 4 /
  7 и опубликовал feature `0b04959…` через PR #14 merge `a3047da…`;
- подтвердил main CI и local-main 862/862 PASS.

### Готовность

TASK-11 закрыт как `DONE_RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY`;
activation manifest 2.8 подтверждён user smoke. Это partial current snapshot,
не adjusted holder concentration, ownership graph, historical snapshot,
toxicity veto или alpha.

## Completed Session 9 — TASK-12 deterministic offline supervisor

### Пользователь

- принял `START_WITH_PATCH`: один stdlib-first offline supervisor вместо
  преждевременного Compose/general framework;
- отдельно разрешил bounded local implementation, deterministic acceptance,
  Catalog finalization, publication и exact PR #15 merge;
- не разрешал sustained collection, provider/API/RPC/WSS, purchase/deploy,
  wallet, signer, transaction или real money.

### ИИ

- заморозил one-child contract с deterministic run identity, atomic duplicate
  lock, typed health/failure states, zero retry, timeout, disk and output caps;
- реализовал thin supervisor и beginner-safe CLI без provider execution mode;
- принял семь deterministic vectors: one real TASK-11 offline preflight и
  шесть fail-closed synthetic controls;
- зарегистрировал десять mandatory outputs в Catalog 0.15.0 / 252 / 4 / 4 / 7;
- опубликовал exact 18-file candidate через feature `5fb63d9…`, PR #15 merge
  `2ebef3f…`; PR/main CI выполнили 905/905 PASS.

### Готовность

TASK-12 закрывается после активации этого Source bundle только как
`DONE_DETERMINISTIC_OFFLINE_SUPERVISOR_CONTROLS`. Это offline control
falsifier, не automatic restart, 24–48h operation, unattended collection,
production packaging, strategy, execution или alpha. TASK-13 READY; его первый
атом только read-only data-readiness/audit Entry Gate.

---

## Completed Session 10 — TASK-13 bounded historical evidence audit

### Пользователь

- принял `START_WITH_PATCH`: аудитировать только exact retained TASK-08…11
  history, не изображая 24–48h pilot;
- отдельно разрешил frozen contract, thin offline auditor, deterministic
  acceptance, Catalog finalization, publication и exact PR #16 merge;
- не разрешал provider calls, purchase/deploy, wallet, signer, transaction
  или real money.

### ИИ

- заморозил 9-file / 4,466,708-byte population с 658 raw rows;
- воспроизвёл 658/658 complete identities, zero duplicate raw/idempotency IDs,
  one repeated-content row, four typed failures and zero PIT violations;
- сверил обе TASK-10 projections до 9 quote rows и zero execution rows;
- зарегистрировал десять mandatory outputs в Catalog 0.16.0 / 262 / 4 / 4 / 7;
- опубликовал exact 24-file candidate через feature `eea6ced…`, PR #16 merge
  `b8f64ef…`; PR/main CI выполнили 936/936 PASS.

### Готовность

TASK-13 закрывается после активации этого Source bundle как
`DONE_BOUNDED_HISTORICAL_EVIDENCE_QUALITY`. Результат доказывает integrity,
PIT и reproducibility только bounded retained history. Он не устанавливает
sustained provider reliability, coverage, Fillable, execution, NetReturn,
PathRisk, provider purchase requirement или alpha. TASK-14 READY; его первый
атом только read-only purchase-decision Entry Gate с cash cap USD 0.

---

## Completed Session 11 — TASK-14 provider purchase decision

### Пользователь

- принял read-only pricing/need gate, deterministic decision, Catalog finalization, publication and exact PR #17 merge;
- закрепил продуктовую границу: detailed data only for a changing versioned watchlist, not all Solana-token ticks;
- не разрешал account/provider execution, purchase, deployment, credentials, wallet, signer, transaction or real money.

### ИИ

- принял `DEFER`: provider purchase requirement не установлен;
- заморозил requirement `PROVIDER_PURCHASE_DECISION_REQUIRES_BOUNDED_USAGE_MEASUREMENT`;
- пометил 7-second Helius observation only as non-decision-valid sensitivity, not a monthly forecast;
- закрепил `VERSIONED_WATCHLIST_MEMBERS_ONLY` and `FORWARD_ONLY_NO_HISTORICAL_REWRITE`;
- зарегистрировал four TASK-14 outputs in Catalog 0.17.0 / 266 / 4 / 4 / 7;
- опубликовал feature `f1dccd4…` through PR #17 merge `d1e73a6…`; main CI completed 947/947 PASS.

### Готовность

TASK-14 closes after this Source bundle activation as
`DONE_PROVIDER_PURCHASE_DEFERRED_PENDING_BOUNDED_USAGE_MEASUREMENT`.
No paid plan, provider reliability, production runtime, all-token tick
collection, Fillable, NetReturn, PathRisk or alpha is established. TASK-15 is
READY_NOT_STARTED; its first atom is read-only and freezes the bounded
sustained-collection measurement contract before any external call or deploy.

---


## Completed Session 12 — TASK-15 hypothesis-driven acquisition

### Пользователь

- отклонил global always-on collection без hypothesis consumer;
- задал продуктовую модель: hypothesis lifecycle, research history,
  tool-assisted discovery, watchlists, monitoring, trading bridge and owner
  PnL pulse;
- потребовал proactive expert buddy and proportional pre-DONE critic;
- разрешил bounded local contracts, publication and exact PR #18 merge;
- не разрешал provider execution, purchase/deploy, wallet/signer/transaction
  or real money.

### ИИ

- закрепил historical/cache-first hypothesis-owned acquisition;
- зарегистрировал `ARCH-INTENT-002`, trigger-to-cashflow bridge,
  position/reconciliation truth and live monitoring prerequisites;
- встроил `FAST_PATH/FULL_REVIEW` Factory Fit Critic в finish workflow;
- зарегистрировал six TASK-15 assets in Catalog 0.18.0 / 272 / 4 / 4 / 7;
- опубликовал PR #18 at feature `3b67692e9592f0c04f12323a8bc568c39614802a` and merge
  `a411f986082b1689a57493d6810974982e731e54`; main CI `973/973 PASS`.

### Готовность

TASK-15 closes after Instruction/Source activation as
`DONE_HYPOTHESIS_DRIVEN_ACQUISITION_AND_FACTORY_OPERATING_MODEL`.
No collector, dashboard, research platform, strategy, execution, position
manager, live monitoring, provider purchase, wallet or alpha is established.
TASK-16 is READY_NOT_STARTED and begins with a read-only Entry Gate.

---


## Completed Session 13 — TASK-16 hypothesis lifecycle and research memory

### Пользователь

- разрешил bounded offline contract, deterministic query/fixture,
  migration acceptance, Catalog finalization, exact publication and PR #19
  merge;
- подтвердил продуктовый приоритет durable hypothesis history, negative
  results, derivations and reactivation memory;
- не разрешал provider calls, collection, purchase/deploy,
  wallet/signer/transaction or real money.

### ИИ

- заморозил append-only family/version/origin/trial/decision/derivation/
  activation-epoch schema and semantic invariants;
- реализовал bounded PIT prior-work query with evidence-bearing results and
  no automatic reject/promote authority;
- сохранил четыре empty legacy registries exact bytes and created no
  synthetic history;
- закрыл durable Catalog-count follow-up before bump;
- registered eight TASK-16 assets and one query in Catalog
  `0.19.0 / 280 / 4 / 4 / 8`;
- published feature `8f0d22c4faa149c7c54c0807e560d2f486afeada` and PR #19 merge
  `7423b2b44630e84b58edb5be5331171fd36c4cfc`; PR/main CI passed 1005/1005.

### Готовность

TASK-20 closes after this Source bundle activation as
`DONE_SPEC_READY_WITH_LIMITATIONS`.
It freezes a reusable demand-gated collection and recovery contract, not a
collector, provider decision, backup execution, dataset, signal, position,
NetReturn or alpha claim. TASK-21 starts only with a read-only Entry Gate;
runtime recovery and every external collection action remain separately
gated.

# 14. Source and Purchase References — snapshot 2026-07-18

Перед оплатой открыть официальный dashboard и обновить `as_of`.

| Provider | Official place |
|---|---|
| Helius pricing | `https://www.helius.dev/pricing` |
| Helius crypto billing | `https://www.helius.dev/docs/billing/pay-with-crypto` |
| Jupiter pricing | `https://developers.jup.ag/pricing` |
| Jupiter setup | `https://developers.jup.ag/docs/portal/setup` |
| Jupiter Swap v2 | `https://developers.jup.ag/docs/swap` |
| Solana Tracker pricing | `https://docs.solanatracker.io/pricing` |
| Solana Tracker Data API | `https://www.solanatracker.io/data-api` |
| Birdeye pricing | `https://docs.birdeye.so/docs/pricing` |
| Birdeye crypto payment | `https://docs.birdeye.so/docs/payment` |
| Birdeye x402 | `https://docs.birdeye.so/reference/x402` |
| Pump fee schedule | `https://pump.fun/docs/fees` |
| Pump bonding curve | `https://pump.fun/docs/bonding-curve` |
| Pump public program docs / IDLs | `https://github.com/pump-fun/pump-public-docs` |
| Solana fee structure | `https://solana.com/docs/core/fees/fee-structure` |
| OpenAI Projects file limits | `https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt` |
| GitHub plans | `https://docs.github.com/en/get-started/learning-about-github/githubs-plans` |
| Optional crypto VPS | `https://bitlaunch.io/` |

---

# 15. Roadmap Update Protocol

После каждого task:

1. До начала выполнить Task Entry Gate и записать entry verdict; при `START_WITH_PATCH/SPLIT/REORDER` сначала исправить contract/roadmap.
2. Выдать Beginner Task Brief до первой команды пользователя.
3. Обновить metadata task-файла.
4. Изменить task status в master table.
5. Добавить artifact в registry.
6. Добавить decision, если изменена архитектура/provider/scope.
7. Обновить roadmap Current State:
   - active task;
   - last validated task;
   - next task;
   - blocker.
8. Транзакционно обновить `current_system_state.md`: component/version/location/access/security/monitoring/evidence, Mermaid и Architecture Delta; если фактических изменений нет, записать `STATE_CHANGE=NONE` в task handoff.
9. Если нужен connector/access, запросить его just-in-time: зачем сейчас, target, read/write scope, исключённые данные, ожидаемое evidence, stop/revoke condition и безопасный fallback. Не запрашивать secrets.
10. Перед custom implementation обновить `reuse_candidate_registry` и вынести `ADOPT/WRAP/FORK/BUILD` verdict; затем обновить relevant hypothesis/trial/feature/strategy/bot/holdout/decision-negative registries.
11. Обновить cash/time/credits и KPI delta; purchase/infra требует budget gate.
12. Не менять старые experiment results и не возвращать consumed holdout в untouched.
13. Если blueprint затронут, создать новую canonical version и migration note.
14. Транзакционно обновить validated Project Asset Catalog: mandatory outputs/consumers, stable IDs, logical locations, versions/hashes-or-fingerprints, relations, access/query recipes и validation evidence; expected missing entry=`CATALOG_GAP`, а не Library search.
15. Выполнить Source inventory/compaction: target ≤16, reserve ≥5; catalog/registries живут в Git, не как новые permanent Sources.
16. После technical DoD выполнить proportional `FACTORY_FIT_REVIEW`; `FAIL` блокирует bundle/DONE, follow-up требует durable owner/trigger/destination.
17. Выполнить `PRODUCT_HORIZON_RADAR`: максимум one NOW + one WATCH candidate без silent scope expansion.
18. Сохранить changelog и выполнить cross-document/state/catalog/registry validation.

## Changelog

| Версия | Дата | Изменение |
|---|---|---|
| `4.6` | 2026-08-06 | User-reported TASK-26C Source smoke PASS plus exact OWNER_DONE_ACCEPTANCE closes the offline readiness task without creating canary authority. OWNER_AUTHORITY_PACKET_BINDING_V1 then delivered an offline 12-input review packet with a proposed USD 3 all-in cap. PR #41 implemented it; PR #42/#43 repaired delivery integrity. Exact current main `11cccf6…`, tree `635e6ae…`, CI run `30961800487` SUCCESS, tracked-only 1842 PASS with 61 skips; Catalog `0.35.0 / 544 / 4 / 13 / 8`. No provider, wallet, signer, transaction, cash, R3, numeric NetReturn or TASK-27 action occurred. Next boundary is exact owner packet inputs and a separate material canary gate. |
| `4.5` | 2026-08-04 | TASK-26B found historical/cache-first reconstruction insufficient for owner attempt denominator, retry intent, inventory and settlement and selected `OWNED_CANARY_REQUIRED` without authority; TASK-26C then merged at PR #40 `df06b18…`, tree `f42a98d…`, with an offline threat/authority/witness/reconciliation contract, deny-by-default allowlist, fake-only deterministic 12-case matrix and `READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS`. Catalog is `0.34.0 / 534 / 4 / 12 / 8`; main CI `30948387252` SUCCESS. No provider, wallet, signer, transaction, cash, R3, numeric NetReturn or TASK-27 action occurred. Next owner decision is a review-only exact authority packet; it is not a canary authorization. |
| `4.4` | 2026-08-04 | TASK-26A accepted at commits `de09e9e…` + `8e15bf9…`, PR #37 merge `ccfd5a1…`, tree `e7dbb89…`: tracked-only execution-evidence contract/inventory and adversarial gate retain 36 quote pairs, 35 quote-cost ready and one latency blocker while fee/attempt/landing/inventory/settlement remain complete for 0/36; decision `EXTEND_EXECUTION_EVIDENCE`, numeric/observed NetReturn, R3 and TASK-27 unauthorized; Catalog 0.32.0 / 515 / 4 / 10 / 8, lifecycle 9 / 56; post-merge main CI `30939569637` passed 1803/1803 with 61 skips. Next implementation remains `NEXT_TASK_SELECTION_REQUIRED` for a bounded capture/extension objective. |
| `4.3` | 2026-08-03 | TASK-26 accepted at feature `b279cbf…`, PR #35 merge `6251309…`, tree `f176a90…`: frozen execution-cost/reconciliation/NetReturn contract, golden/adversarial suite and exact R2 aggregate projection; 35/36 quote-cost inputs ready, all 36 lack complete fee/settled-cashflow truth and one pair is latency-blocked; numeric/observed NetReturn remain unsupported, R3 sealed; Catalog 0.31.0 / 499 / 4 / 9 / 8, lifecycle 9 / 56; tracked-only 1788 PASS with 61 skips and main CI SUCCESS. Next implementation is `NEXT_TASK_SELECTION_REQUIRED`. |
| `4.2` | 2026-08-02 | TASK-25 accepted at feature `563826d…`, PR #34 merge `a1c7e40…`, tree `b428046…`: frozen label/PIT contract and exact R2 surface produced 108 outcomes, 80 supported and 28 unknown, including 35/36 fillable, 36/36 quote exits and one explicit latency exception; actual fills, settlement, complete fees and observed NetReturn remain unsupported; R3 paths/values remain zero; Catalog 0.30.0 / 476 / 4 / 8 / 8, lifecycle 9 / 56; main CI SUCCESS and tracked-only 1741/1741 PASS with 61 skips; TASK-26 read-only execution-cost/NetReturn Entry Gate READY. |
| `4.1` | 2026-08-02 | TASK-23 accepted at PR #31 merge `31c0164…`, tree `6677878…`, verdict `DIAGNOSTICS_READY_WITH_LIMITATIONS`, Catalog 0.28.0 / 415 and main CI 1526/1526 PASS with 51 skips; TASK-24 accepted at PR #32 merge `d82ccc6…`, tree `ce034b4…`, decision `STOP_NO_RELIABLE_ENTITY_SIGNAL`, 4/12 predicted-positive capacity, zero corroboration, no false-positive audit and downstream `NOT_ADMISSIBLE`; Catalog 0.29.0 / 448, lifecycle 9 / 56, main CI 1626/1626 PASS with 61 skips; TASK-25 read-only outcome-contract Entry Gate READY while R3 remains default deny. |
| `4.0` | 2026-08-01 | TASK-22 accepted at feature `07e6087…`, PR #30 merge `90575ac…`, tree `f9cdd82…`: split `T22-SPLIT-T21-FROZEN-002` freezes R2 development / validation NONE / R3 untouched holdout before outcome reads; actual embargo 1701.306244s exceeds 900s; no additional collection; Catalog 0.27.1 / 396 / 4 / 7 / 8; main CI 1485/1485 PASS with 51 skips; TASK-23 read-only development-only cohort-diagnostics Entry Gate READY and R3 remains default deny. |
| `3.9` | 2026-08-01 | TASK-21 accepted after final-cohort PR #28 and Finish Gate repair PR #29 merge `2ff5a9d…`, tree `3af1179…`: exact recoverable 91-file dataset, five complete members in two clusters, 22 panels / 88 quote pairs / 176 attempts, outcomes unopened, remote read-back and isolated restore PASS; Catalog 0.26.1 / 374 / 4 / 4 / 8; main CI 1436/1436 PASS with 51 skips; product-vision gate `CANONICALIZED_WITH_PATCH` adds durable TASK-34A/TASK-35A triggers; TASK-22 group-aware split Entry Gate READY. |
| `3.8` | 2026-07-30 | TASK-20 accepted at feature `f017019…`, PR #24 merge `072b98a…`, tree `aa20c6f…`: versioned 40-field T0/T1/T2 collection spec, coverage matrix and recovery policy produced `SPEC_READY_WITH_LIMITATIONS`; 38/38 targeted and 8/8 adversarial checks passed; Catalog 0.25.0 / 340 / 4 / 4 / 8; final main CI 1134/1134 PASS with 14 expected clean-clone raw skips; TASK-21 read-only Entry Gate READY, while runtime backup/read-back/restore/alerts and all forward collection authority remain separate. |
| `3.7` | 2026-07-30 | TASK-19 accepted at feature `39b4e9e…`, PR #23 merge `0284a68…`, tree `8837e88…`: deterministic replay retained 24 accepted and 8 excluded attempts, 12 complete quote pairs and the prior 832.5706 bps median capacity-curvature delta; 10/10 adversarial vectors passed and verdict is `REPLAY_SAFE` within one-member quote-only scope; first CI exposed and the repair removed an obsolete exact-Catalog-count coupling; Catalog 0.24.0 / 331 / 4 / 4 / 8; repaired PR and main CI 1096/1096 PASS; TASK-20 collection-spec gate READY and must consume the versioned backup/restore follow-up before any forward collection. |
| `3.6` | 2026-07-29 | TASK-18 accepted at PR #22 merge `7daa770…`, tree `43b4c49…`: exact 32-attempt audit and one content-addressed 12-file snapshot passed private Google Drive raw-byte read-back and isolated restore; final verdict `FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND`; no general storage-reliability/fill/alpha claim; Catalog 0.23.0 / 321 / 4 / 4 / 8; main CI 1070/1070 PASS with 11 expected clean-clone raw-absence skips; TASK-19 read-only replay/leakage gate READY; future collection backup/restore automation remains owned by TASK-20. |
| `1.0` | 2026-07-18 | Initial execution roadmap based on Synthesis v2, system v8.0 and provider facts current to July 2026 |
| `1.1` | 2026-07-18 | Pre-TASK-01 integrity audit: corrected system ambiguity, task statuses, artifact registry and remediation gate |
| `1.2` | 2026-07-18 | Closed TASK-00B/00C, added TASK-00D, introduced bounded Project Sources hot set/phase archives, activated TASK-01, upgraded OS 8.1 and instruction 2.4 |
| `1.3` | 2026-07-18 | TASK-00E independent rebase: corrected lifecycle state, execution accounting/terminal states, revision lineage, information-sufficiency gate, Pump v2 drift, TASK-01/07 separation, explicit dependencies, OS 8.2/instruction 2.5/blueprint 2.1 |
| `1.4` | 2026-07-18 | TASK-00F: encoded senior-buddy operating model, mandatory Task Entry Gate and Beginner Task Brief, just-in-time least-privilege access protocol, permanent `current_system_state.md`, architecture-delta handoff, seven-file core; TASK-01 remains READY and now depends on TASK-00F |
| `1.5` | 2026-07-18 | TASK-00G: bounded long-lived Alpha Factory; option-value data/RC/global trial+holdout/separate lifecycles/scoped closure/business gates plus mandatory reuse/wrap/fork/build registry; TASK-01 remains READY and depends on TASK-00G |
| `1.6` | 2026-07-18 | TASK-01 completed as a validated source/provider design: zero calls/accounts/purchases; eight artifacts and frozen 34-case smoke design; Raptor D08/D09 fallback mapping repaired; state/archive/task handoff advanced to TASK-02 READY; TASK-03 must import pre-Git TASK-01 artifacts and hashes. |
| `1.7` | 2026-07-18 | Post-TASK-01 control patch: Project Asset Catalog formalized as bounded-memory resolver across Git artifacts, datasets/raw, DuckDB relations, sources, components, evidence and query recipes; TASK-03 expanded to implement schemas/generator/validators and import lineage; graph DB deferred; TASK-02 scope unchanged with mandatory handoff. |
| `1.8` | 2026-07-21 | TASK-02 completed: workstation/toolchain/runtime evidence PASS, sanitized immutable completion bundle, `DELTA-02-001`, state 1.4 and archive 7.0; active task advances to detailed TASK-03 READY with repository security, Asset Catalog, pre-Git TASK-01/02 import and bounded Work↔Codex bridge. |
| `1.9` | 2026-07-22 | TASK-03 DONE at accepted private `main` `f8ff483…`: locked uv/Python runtime, repository security/CI, Project Asset Catalog 60/4/4/5, 9 typed registry frameworks, imported TASK-01/02 lineage, final CI and clean clone 131/131 PASS; state 1.5/archive 8.0; active Source advances to TASK-04 READY; OS 8.5 and blueprint 2.3 unchanged. |
| `2.0` | 2026-07-22 | Prepared, not installed, Project Instruction v3.0: removed historical task bindings, formalized Work↔Codex ownership and separate authority classes, and made UI activation an exact coordinated transaction; state 1.6/archive 9.0; TASK-04, OS, blueprint and repo/remote unchanged. |
| `2.1` | 2026-07-24 | Control-plane finalization after accepted TASK-04 and TASK-05 repository deliveries: G0 PASS; TASK-05 DONE at `1db62c7…`; Catalog 0.4.1 with 111 assets/4 shards/4 schemas/7 queries; active task advances to TASK-06 READY. Coordinated Sources candidate remains `UI_ACTIVATION_PENDING` until the user replaces the five mapped roles and passes the fresh-chat smoke test. |
| `2.2` | 2026-07-24 | TASK-06 accepted after published implementation and finalization at `8c52f167…`; repository state `TASK06_FINALIZATION_COMMITTED`; Catalog 0.5.1 with 128 assets/4 shards/4 schemas/7 queries; provider/API/RPC calls and cash spend remain zero; active task advances to TASK-07 READY with a read-only first atom and exact separate external-call gate. |
| `2.3` | 2026-07-24 | TASK-07 accepted at published `03731b647…`: 35 bounded attempts, 32 accepted successes, one invalid request, two retained provider 5xx, 49,604 response bytes, modeled Helius credits 15, cash USD 0; Catalog 0.6.0 / 141 / 4 / 4 / 7; active task advances to TASK-08 READY with a read-only first atom. |
| `2.4` | 2026-07-25 | TASK-08 accepted at published `bd152b3…`: one bounded run retained 388 records; transport/durability and 470-test local/CI/clean-clone gates PASS; lifecycle coverage `NOT_TESTABLE_IN_WINDOW`; explicit blocker accepted without retry or 24h pilot; Catalog 0.7.0 / 158 / 4 / 4 / 7; active task advances to TASK-09 READY with a read-only first atom. |
| `2.5` | 2026-07-26 | CTRL-BATON technical completion accepted: PR #1 merged at `a9726de…`, tree `b7a010f…`, exact ordered parents and 84-path inventory; PR/main CI and local main 607/607 PASS; Catalog 0.8.4 / 190 / 4 / 4 / 7; GitHub Pro/private protection deferred by owner with compensating controls; TASK-09 v1.1 remains READY/NOT_STARTED; Source activation pending. |
| `4.7` | 2026-08-08 | TASK-27 A0 offline foundation is repository-merged: A2 freezes pool-interval price/volume labels and missing=`UNKNOWN`; A3 freezes capped historical-collection authority; A4 requires a fresh seven-role Source smoke before a separate owner external-read review. PR #48 merged at `082f3f8…`; post-merge CI run `31224401848` SUCCESS. No provider, raw history, wallet, signer, transaction, cash, strategy, PIT, PnL or NetReturn action occurred. A5 is only a Project Sources replacement candidate; UI activation remains user-owned. |
| `2.6` | 2026-07-27 | TASK-09 accepted as Touch-only at feature `e4694e4…` and PR #7 merge `c99c76f…`, tree `d69dba6…`: one bounded run retained 258 raw rows and replayed 75 decoded Buy/Sell events; PR/main CI and local main 753/753 PASS; Catalog 0.9.0 / 205 / 4 / 4 / 7; TASK-10 v1.0 READY with read-only first atom; Source activation pending. |
| `3.5` | 2026-07-29 | TASK-17A accepted at PR #21 merge `67fdb73…`, tree `d74d3fa…`: 32 total public keyless quote calls, 24 accepted and 8 excluded-retained; one-member three-window quote-only temporal replication supported; no quality/fill/alpha claim; Catalog 0.22.0 / 303 / 4 / 4 / 8; PR/main CI 1041/1041 PASS; TASK-18 read-only quality gate READY. |
| `3.4` | 2026-07-29 | TASK-17 accepted at PR #20 merge `55fe5b0…`, tree `edf4df8…`: one immutable execution-capacity hypothesis lifecycle snapshot, reproducible prior-work query and `LIVE_NON_RECONSTRUCTABLE_NEED`; future capture remains capped at 192 calls and unauthorized; Catalog 0.20.0 / 286 / 4 / 4 / 8; PR/main CI 1019/1019 PASS; TASK-17A read-only capture gate READY. |
| `3.3` | 2026-07-29 | TASK-16 accepted at PR #19 merge `7423b2b…`, tree `123347d…`: append-only hypothesis lifecycle/provenance/derivation memory, bounded prior-work query, empty-legacy preservation, Catalog 0.19.0 / 280 / 4 / 4 / 8 and main CI 1005/1005 PASS; TASK-17 first bounded hypothesis cycle/data-need decision READY; activation pending. |
| `3.2` | 2026-07-29 | TASK-15 accepted at PR #18 merge `a411f98…`, tree `c0ea9e3…`: hypothesis-owned historical/cache-first acquisition, research memory, owner pulse, trigger-to-cashflow and monitoring capability owners; Factory Fit FULL_REVIEW; Project Instruction v3.3 candidate; TASK-16 lifecycle/memory contract READY; Catalog 0.18.0 / 272 / 4 / 4 / 7; main CI 973/973 PASS; activation pending. |
| `3.1` | 2026-07-29 | TASK-14 accepted with `DEFER` at feature `f1dccd4…` and PR #17 merge `d1e73a6…`, tree `fb6aac7…`: provider purchase requirement not established; bounded usage measurement required; detailed observation limited to versioned watchlist members with forward-only policy; PR/main CI 947/947 PASS; Catalog 0.17.0 / 266 / 4 / 4 / 7; TASK-15 v1.0 READY with read-only first atom; Source activation pending. |
| `3.0` | 2026-07-29 | TASK-13 accepted as bounded historical evidence quality at feature `eea6ced…` and PR #16 merge `b8f64ef…`, tree `e9ea44c…`: 9 exact files / 4,466,708 bytes / 658 raw rows, complete unique identities, one repeated-content row, four typed failures, zero PIT violations, provider purchase requirement not established; PR/main CI 936/936 PASS; Catalog 0.16.0 / 262 / 4 / 4 / 7; TASK-14 v1.0 READY with read-only purchase-decision Entry Gate; Source activation pending. |
| `2.9` | 2026-07-28 | TASK-12 accepted as deterministic offline supervisor controls at feature `5fb63d9…` and PR #15 merge `2ebef3f…`, tree `e2e3080…`: one allowlisted TASK-11 offline preflight plus six fail-closed vectors, zero retry/provider calls/cash/wallet actions; PR/main CI 905/905 PASS; Catalog 0.15.0 / 252 / 4 / 4 / 7; TASK-13 v1.0 READY with read-only data-readiness Entry Gate; Source activation pending. |
| `2.8` | 2026-07-28 | TASK-11 accepted as raw top-20 account concentration feasibility at feature `0b04959…` and PR #14 merge `a3047da…`, tree `223c019…`: one three-call Helius standard RPC run with zero retries resolved 20/20 token-account owners and five projection rows; exclusions remain incomplete, adjusted concentration null and deployer/funder/bundler NOT_TESTED; main CI and local main 862/862 PASS; Catalog 0.14.0 / 242 / 4 / 4 / 7; TASK-12 v1.0 READY but not started; Source activation pending. |
| `2.7` | 2026-07-28 | TASK-10 accepted as quote compatibility only at feature `d853392…` and PR #13 merge `f384395…`, tree `04c2c75…`: two bounded runs made nine public keyless GET calls with zero retries, preserved one fail-closed schema-drift row and accepted eight buy/reverse-sell quotes; main CI and local main 834/834 PASS; Catalog 0.13.1 / 228 / 4 / 4 / 7; TASK-11 v1.0 READY with read-only first atom; Source activation pending. |
