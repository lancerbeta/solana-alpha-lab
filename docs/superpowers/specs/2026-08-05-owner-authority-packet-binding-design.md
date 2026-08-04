---
title: Owner Authority Packet Binding v1 — одобренный дизайн
status: DESIGN_APPROVED_PENDING_USER_SPEC_REVIEW
candidate_task_id: OWNER_AUTHORITY_PACKET_BINDING_V1
as_of: 2026-08-05
classification: EPHEMERAL_DESIGN_ARTIFACT_NOT_A_CANARY_AUTHORIZATION
catalog_impact: NONE_UNTIL_IMPLEMENTATION_ARTIFACTS_EXIST
contains_secrets: false
external_actions: 0
wallet_signer_transaction_actions: 0
cash_spend_usd_cents: 0
---

# Owner Authority Packet Binding v1 — дизайн

## Какое решение поддерживает этот дизайн

Владелец цели позже сможет решить, достаточно ли точно описан один
ограниченный технический DEX-canary для рассмотрения. Этот документ не даёт
такого разрешения, не создаёт кошелёк, не подключает signer, не получает
котировку, не строит транзакцию, не тратит деньги и не начинает TASK-27.

## Согласованная форма будущего canary

Будущий технический canary — это двухэтапный круговой маршрут, которым
управляет владелец:

```text
SOL -> one exact memecoin -> SOL
```

Второй этап — немедленный выход для проверки исполнения, а не удержание позиции
ради торговли. Он может начаться только после финального наблюдения первого
этапа и сверки token/SOL inventory. `UNKNOWN`, неудачная сверка, неожиданное
изменение баланса, потеря monitoring, несовпадение route или превышение лимита
останавливают последовательность; они никогда не вызывают автоматический retry
или импровизированный выход.

Выбранный владельцем all-in лимит cash-at-risk — **USD 3.00**. Во время
будущего исполнения он обязан включать input notional, network fees, relay или
priority fees, ATA rent и любое другое отдельное списание. Если свежий
зафиксированный preflight не может доказать, что предложенная последовательность
укладывается в лимит, canary отклоняется до первой отправки.

## Выбранный подход

Использовать вручную созданный отдельный технический кошелёк только после
отдельно одобренного owner-packet. Владелец управляет им через обычное
wallet-приложение и вручную подтверждает каждое будущее действие. Это не должен
быть основной кошелёк владельца с активами; seed phrase и private key никогда
не попадают в чат, репозиторий, логи, URL или файлы проекта.

Это намеренно уже, чем автоматизированный isolated signer. Автоматизация добавит
новую границу работы с ключами и deployment до того, как проект увидит хотя бы
один сверенный маршрут. Основной кошелёк отвергнут: он смешивает ограниченный
canary с несвязанными активами и риском.

## Контракт packet, который будет реализован после review этого дизайна

Будущий offline binding-артефакт обязан иметь два состояния.

1. `DRAFT_OWNER_INPUT_REQUIRED`
   - Хранит согласованный маршрут, правило немедленного выхода и предложенный
     лимит USD 3.00.
   - Оставляет `token`, `program`, `route`, публичный адрес кошелька, точный
     notional, максимум отдельных fees, quote basis, срок действия и процедуру
     stop/recovery явными значениями `OWNER_INPUT_REQUIRED`.
   - Никогда не является исполнимым и должен отвергаться validator'ом как
     authority.

2. `READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION`
   - Существует, только когда каждое обязательное поле связано с одним
     canary ID.
   - Содержит exact action, token mint, program, route, proposed notional,
     all-in cap, максимум отдельных fees, ожидаемые inventory до и после
     каждого этапа, ссылки на monitoring/reconciliation, срок действия и
     точную фразу owner approval.
   - Остаётся packet для review. Перед созданием или funding кошелька,
     запросом котировки, использованием signer, транзакцией, provider call
     или cash-action всё равно требуется отдельное явное одобрение.

Отсутствующие значения — не значения по умолчанию. Они должны оставаться
видимыми как `OWNER_INPUT_REQUIRED`; validator обязан отвергать отсутствующие,
подменённые нулём или неоднозначные поля.

## Будущая последовательность исполнения — не разрешена этим дизайном

1. Повторно выполнить свежий Entry Gate для exact token/program/route и текущих
   условий исполнения.
2. Связать финальный packet и получить точное одноразовое approval владельца.
3. Владелец создаёт и пополняет отдельный кошелёк вне проекта, в пределах
   одобренного лимита и без раскрытия секретного материала.
4. Выполнить первый этап, только если прошли health, monitoring, quote
   freshness, allowlist и cap checks.
5. Провести reconciliation первого этапа. `UNKNOWN` блокирует retry и
   запланированный выход, пока reconciliation не установит фактические
   inventory и fees.
6. Выполнить немедленный выход, только когда первый этап reconciled и все
   health/cap/inventory правила по-прежнему проходят.
7. Провести reconciliation полного round-trip и сохранить witness. Лишь после
   этого новый Entry Gate может оценить допустимость TASK-27.

## Предлагаемая ограниченная реализация

После user review этого дизайна реализовать только offline binding contract,
schema, synthetic fixture, deterministic validator, adversarial tests и Catalog
transaction. Validator как минимум покроет:

- draft с намеренно отсутствующими owner inputs;
- complete packet, остающийся неисполняемым;
- требования USD 3.00 cap и учёта отдельных fees;
- запрет подмены token/program/route;
- immediate exit только после reconciliation первого этапа;
- блокировку при `UNKNOWN`, потере monitoring, inventory mismatch, route
  mismatch или cap breach;
- отсутствие wallet, seed, private key, signed bytes, provider/API/RPC/WSS
  call или transaction path.

Generic execution platform, provider adapter, wallet connector, signer, price
feed, deployment и strategy logic — вне scope.

## Definition of Done будущей implementation-задачи

Offline packet имеет versioned contract и schema; deterministic tests доказывают,
что неполные или небезопасные packet не могут выглядеть готовыми; Catalog и
generated consumers описывают новые assets; а acceptance evidence фиксирует
ноль external, wallet, signer, transaction и cash side effects. Результат
обязан сохранить `TASK-27_authority=false`.

## Чек-лист review

- Лимит USD 3.00 — потолок, а не разрешение тратить.
- Round-trip — проверка исполнения, а не alpha trade.
- Отдельный технический кошелёк — будущее user-only действие, а не output этой
  задачи.
- Каждая неизвестность явная и fail-closed.
- Ни одна формулировка не даёт authority для canary или TASK-27.
