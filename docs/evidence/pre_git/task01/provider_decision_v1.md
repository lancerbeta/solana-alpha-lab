---
artifact_id: SMIAL_TASK_01_PROVIDER_DECISION
artifact_version: "1.0"
task_id: TASK-01
task_execution_status: DONE
artifact_status: VALIDATED_DECISION
decision_id: PVD-001
decision_status: FROZEN_FOR_TASK07_SPEC_NOT_IMPLEMENTED
owner: user+assistant
as_of: 2026-07-18
canonical_after_validation: true
canonical_sources_sync: PREPARED_FOR_CANONICAL_HANDOFF_USER_ACTIVATION_PENDING
api_rpc_provider_requests_executed: false
accounts_created: false
purchases_executed: false
contains_secrets: false
state_change: NONE
---

# TASK-01 — Provider decision v1

## 1. Решение простыми словами

Начальный контур должен уничтожать плохую гипотезу максимально дёшево, а не покупать ощущение инфраструктурной готовности. Поэтому принимается **условный бесплатный shortlist для будущего TASK-07**, а не implementation claim:

| Роль | Решение сейчас | Почему |
|---|---|---|
| Protocol semantics | Solana official RPC specification + pinned Pump docs/IDL | Не изобретать собственную трактовку chain/program state |
| Raw RPC/WSS transport | `Helius Free` — primary smoke candidate | 1M documented credits и базовый RPC/WSS достаточны для bounded smoke; реальная надёжность не измерена |
| Indexed discovery/enrichment | `Solana Tracker Data API Free` — primary comparison candidate | Высокий information gain для discovery/holders/bundlers при 10k documented requests; vendor fields не становятся truth |
| Executable quote reality | `Jupiter Swap v2 /order`, quote-only — primary candidate | Exact mint/atomic amount/buy/sell route evidence; без `taker` transaction должен отсутствовать |
| Independent quote comparison | `Raptor hosted GET /quote` — optional matched comparator | Может дешёво отделить Jupiter-specific gap от market route death; public beta не является SLA |
| Secondary indexed provider | `Birdeye Standard` — defer unless measured gap | Дублирует значительную часть indexed coverage |
| Sparse paid indexed path | `Birdeye x402` — defer | Официально существует, но требует wallet-signed USDC payment; initial free smoke не оправдывает signer/payment surface |
| Historical catalog | `Dune Solana catalog` — reference only | Ускоряет discovery/backfill cross-check, но не создаёт прежний `observed_at` или executable evidence |

**Initial cash cap: `$0/month`.** В TASK-01 не создаются аккаунты, не запрашиваются keys, не выполняются calls и не подключается wallet.

## 2. Decision gates

### 2.1. Обязательный порядок

```text
technical/data/execution fit
→ security, terms, replay and failure semantics
→ documented crypto-payment preference
→ full TCO
→ convenience
```

Crypto-payment совместимость не спасает сервис, который проваливает truth/security/DoD. Среди goal-feasible вариантов она получает преимущество. Fiat-only исключение требует отдельного memo и решения пользователя.

### 2.2. Primary не означает «истина обо всём»

- Helius authoritative только для факта своего transport/response; raw chain fields сохраняют slot/commitment и проверяются против protocol contract.
- Solana Tracker authoritative только для факта своего indexed response; risk/entity/bundler labels сохраняют provider/version/confidence.
- Jupiter и Raptor authoritative только для своего exact quote/error в конкретный момент; quote не равен fill.
- Ни candle, ни indexed spot price, ни reserve formula не доказывают executable buy/sell.

## 3. Provider-by-provider verdict

| Provider/product | Verdict | Account gate | TASK-07 role | Upgrade gate |
|---|---|---|---|---|
| Helius Free RPC/WSS | `CONDITIONAL_PRIMARY` | Создать free account только после TASK-02/06 и утверждённого smoke runner | Raw RPC, commitment, failures, one bounded WSS lifecycle | Measured credit/429/coverage bottleneck; Developer `$49` rechecked |
| Helius Enhanced | `OPTIONAL_CROSS_CHECK` | Same account | At most one parsed-vs-raw comparison if credit cap permits | Never replace raw signature/instruction lineage |
| Jupiter Swap v2 | `CONDITIONAL_PRIMARY_QUOTE` | Official docs conflict: Plans lists keyless; Swap overview requires key. Resolve before execution | Quote-only `/order`, no `taker`, no `/execute` or `/submit` | Measured 1 RPS/credit bottleneck; Developer `$25` rechecked |
| Solana Tracker Data Free | `CONDITIONAL_INDEXED_PRIMARY` | Create free account only immediately before TASK-07 | Bounded search/token/holder cases, including lifecycle states | Measured quota/coverage gap; payment rail attested before paid plan |
| Raptor hosted beta | `OPTIONAL_QUOTE_COMPARATOR` | Public docs show hosted beta; auth/terms rechecked before use | Matched GET `/quote` only; health plus bounded pairs | No build/sign/send/self-host; beta change is a stop condition |
| Birdeye Standard | `DEFER_UNLESS_GAP` | No account now | Not in initial request set | Add only for a named Solana Tracker/Helius coverage disagreement |
| Birdeye x402 | `DEFER_PAYMENT_SURFACE` | No wallet/account/request now | Not in TASK-07 initial smoke | Measured data gap + route price + isolated capped research signer + explicit approval |
| Dune | `ADOPT_AS_REFERENCE` | No account now | No live/PIT/execution claim | One bounded query use case must be named before access decision |

## 4. Самый дешёвый путь фальсификации

TASK-07 будет проверять не «есть ли красивый JSON», а четыре risk surfaces:

1. **Universe truth:** возвращаются ли default/graduating/graduated и не скрываются ли dead/non-migrated cases.
2. **Protocol/index disagreement:** совпадают ли mint/decimals/pool/slot/signature там, где сравнение допустимо.
3. **Execution illusion:** существуют ли двусторонние quote-only routes для bounded amounts и сохраняются ли no-route/errors.
4. **Operational feasibility:** credits, 429, latency, response size, timestamp availability и replay envelope.

Если bounded free smoke не может создать honest universe + executable quote/error evidence, решение — не покупать автоматически, а выбрать `RESTRICT_SCOPE`, `REDESIGN_DATA` или `CLOSE` соответствующую hypothesis family.

## 5. Upgrade and stop rules

Платный upgrade допустим только если одновременно существуют:

- measured bottleneck из reproducible report;
- named downstream consumer;
- сравнение free workaround/alternative;
- monthly cash, credits, storage и operator-time cap;
- documented crypto-payment rail либо explicit fiat-only exception;
- cancellation/revoke path;
- решение пользователя до платежа.

Немедленный stop:

- запрос требует sign/send/payment или production wallet;
- secret попал в command, fixture, log, screenshot, chat или Git;
- расход/response count превышает frozen cap;
- endpoint/schema отличается от spec и требует импровизации;
- beta/terms/auth изменились;
- provider error смешивается с market no-route;
- transaction payload появился там, где quote-only case запрещает его.

## 6. Отклонённые альтернативы

| Альтернатива | Решение | Основание |
|---|---|---|
| Купить paid plans заранее | `REJECT` | Нет measured bottleneck или validated edge |
| Сразу Helius gRPC/dedicated | `REJECT_INITIAL` | Преждевременная throughput/ops сложность |
| Только один indexed provider | `REJECT` | Provider schema/revisions создают lock-in и скрытый bias |
| Использовать candle/price как fill | `REJECT` | Execution illusion |
| Adopt Hummingbot как initial spine | `REJECT_INITIAL` | Большой signer/dependency/telemetry surface до доказательства alpha |
| Self-host Raptor сейчас | `DEFER` | Нулевой license price не равен нулевому TCO |
| Платить Birdeye x402 в smoke | `DEFER` | Wallet/signing/payment не нужны для дешёвого первичного falsifier |

## 7. Evidence and limitations

`as_of = 2026-07-18`. Использованы только публичные официальные docs/repos. Runtime claims не делаются.

Открытые evidence states:

- `JUPITER_AUTH_CONFLICT`: official Swap overview требует `x-api-key`, Plans документирует Keyless; разрешить перед TASK-07.
- `SOLANA_TRACKER_PAYMENT_UNKNOWN`: paid payment rail требует sanitized dashboard/user attestation только если upgrade станет реальным кандидатом.
- `RUNTIME_UNMEASURED`: coverage, latency, credit deltas, 429, schema revisions и route overlap не тестировались.
- `FIRST_RELIABLE_AVAILABLE_AT_UNSET`: выставляется только после validated forward observation.

## 8. Handoff

```text
TASK-01: DONE
blocker: NONE
user_action_required_now: NONE
accounts_required_now: NONE
purchase_required_now: NONE
STATE_CHANGE: DELTA-01-001_PENDING_USER_ACTIVATION
next_task_candidate: TASK-02_AFTER_USER_ACTIVATION_AND_NEW_ENTRY_GATE
task03_import_requirement: import validated TASK-01 artifacts, hashes and evidence into the private Git registry
```

Создание этого документа не делает provider выбранным для production и не переводит TASK-01 в DONE.
