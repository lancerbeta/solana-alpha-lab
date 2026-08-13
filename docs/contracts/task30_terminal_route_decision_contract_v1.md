# TASK-30 A19 terminal route decision contract v1

## Consumer and decision

Consumer: `RC001-H07-H01-LIQUIDITY-RETENTION` и следующий owner Entry Gate.

Единственное решение этого offline atom:
`CLOSE_CURRENT_DATA_ROUTE_LIMITED_NEGATIVE_RESULT`.

Оно означает: текущая bounded-ветка поиска пригодной PIT-history и
execution-linked evidence исчерпала самый дешёвый проверенный путь без
достаточного доказательства. Это не означает, что рынок неактивен, любой
провайдер непригоден или H07/H01 опровергнуты.

## Evidence basis

Решение привязано к восьми уже сохранённым repository receipts: Birdeye
OHLCV rate/quota limit, Gecko freshness-route close, Helius
`transactionSubscribe` free-plan rejection, Standard WSS no-observation
UNKNOWN, A16 activity discriminator, A17 route-yield result, A18 offline
readiness и A18 single-signature runtime UNKNOWN. Их exact paths и SHA-256
находятся в config и acceptance receipt. Старые receipts не переписываются.

## Reopen rule

Повторное открытие — только новый named owner gate, если одновременно есть:

1. named consumer и изменившееся решение, которое он примет;
2. конкретный route, дающий PIT-safe history или execution truth;
3. новый budget/cap, retention, monitoring и cheapest falsifier;
4. отсутствие скрытого fallback/retry и явный UNKNOWN recovery.

Без этого следующий атом не должен быть ещё одной подготовкой того же route.

## Authority and non-claims

Этот контракт offline-only. Он разрешает tracked files, deterministic tests,
Catalog и обычную repository delivery. Он не разрешает provider/API/RPC/WSS,
credentials, raw data, R2/R3, scheduler, wallet, signer, transaction, cash,
trial, holdout, strategy promotion, TASK-30 acceptance или Project Sources
change.

`RC001-H07-H01-LIQUIDITY-RETENTION` остаётся `BLOCKED_DATA` из-за отсутствия
непрерывной PIT price history и settled execution truth. Missing/UNKNOWN не
являются zero, flat, inactive, no-trade или settled.
