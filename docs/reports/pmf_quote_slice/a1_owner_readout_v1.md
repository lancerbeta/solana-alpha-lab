# PMF — quote-slice bound, call not authorized

**Терминальное решение:** `PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED`
**Фраза владельца:** `OK PMF-QUOTE-SLICE`

Это **офлайн-привязка PMF-контура цены**, а не котировка с рынка, не execute, не alpha, не PIT и не canonical DONE.

## Что привязано

- intended route: `JUPITER-SOLANA-SWAP-V2-ORDER-001`
- ADOPT: `ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY`
- method/endpoint: `GET` `https://api.jup.ag/swap/v2/order` (без `taker`)
- слой TASK-26: `QUOTE`
- pair: `SOL_TO_A24_BASE_MINT`
- A24 base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- input mint (SOL): `So11111111111111111111111111111111111111112`
- A24 pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- notional: `10000000` lamports (`PMF_QUOTE_SLICE_NOTIONAL_V1`)
- live registry: `PROVIDER-ROUTE-CAPABILITY-REGISTRY-006` = `REGISTRY_GAP`
- call_authorized: `False`
- authority_granted: `False`
- build: `FORBIDDEN`
- persist_transaction_bytes: `False`

## Почему live registry не переписывали

v6 требует observed receipt для обновления маршрута. Строка без наблюдения была бы фальшивой observation. A26 уже фиксирует `jupiter_or_quote_route_present=false` и `REGISTRY_GAP`. Gap закрывается только после отдельного one-shot.

TASK-10 Metis logger отвергнут: это legacy `/swap/v1/quote`, `NETWORK_ENABLED=false`. Официальный quote-only путь — `GET /swap/v2/order` **без** `taker` (transaction = null).

## Можно ли вызывать API?

Нет. Нужна отдельная фраза и portal key. Этот атом ключ не читает.

`OK PMF-QUOTE-SLICE-ONE-SHOT: Jupiter Swap V2 /order without taker, SOL to A24 base mint 0.01 SOL, quote layer only, portal key allowed, no execute`

## Не делать

- `WRAP_TASK10_METIS_LOGGER`
- `JUPITER_EXECUTE_OR_BUILD`
- `SUPPLY_TAKER_OR_SIGNER`
- `FAKE_V7_WITHOUT_OBSERVED_RECEIPT`
- `H11_UNPARK_OR_SAMPLE_CAMPAIGN`
- `H13_TRIAL`
- `H02_H10_H14_TRIAL`
- `NOTIONAL_BUCKET_SET_V1_FREEZE`
- `LIVE_PIT_OR_CASHFLOW_CLAIM`

H11 остаётся parked (`H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`). H07/H01 остаётся parked (`RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`). H13/H02 не стартуют. `NOTIONAL_BUCKET_SET_V1` не замораживается. Это не A18 Orca mint.

## Что этим атомом не утверждается

- живая цена / fill / NetReturn / cashflow
- observed Jupiter route в capability registry
- право читать portal API key
