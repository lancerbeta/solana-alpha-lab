# PMF — quote observed, execute forbidden

**Терминальное решение:** `QUOTE_OBSERVED`
**Фраза владельца:** `OK PMF-QUOTE-SLICE-ONE-SHOT: Jupiter Swap V2 /order without taker, SOL to A24 base mint 0.01 SOL, quote layer only, portal key allowed, no execute`

Это **одна наблюдаемая котировка**, не execute, не alpha, не PIT и не canonical DONE.

## Что увидели

- GET `https://api.jup.ag/swap/v2/order` без `taker`
- HTTP 200, 1871 байт
- input: `10000000` lamports SOL
- output: `9010943976` A24 base mint (`DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`)
- router: `dflow`
- mode: `manual` (задан `slippageBps=100`)
- `transaction`: отсутствует
- access class: `KEYLESS` (в этом workspace не было `JUPITER_API_KEY`; portal key был разрешён, но не требовался)
- live registry: `PROVIDER-ROUTE-CAPABILITY-REGISTRY-007` = `ROUTE_OBSERVED`
- v6 не переписывали

## Можно ли execute?

Нет. `/execute` и `/build` запрещены. Это не fill и не деньги после издержек.

## Не делать

- `WRAP_TASK10_METIS_LOGGER`
- `JUPITER_EXECUTE_OR_BUILD`
- `SUPPLY_TAKER_OR_SIGNER`
- `H11_UNPARK_OR_SAMPLE_CAMPAIGN`
- `H13_TRIAL`
- `H02_H10_H14_TRIAL`
- `LIVE_PIT_OR_CASHFLOW_CLAIM`
