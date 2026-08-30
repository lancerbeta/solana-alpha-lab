# PathRisk calibration capability — owner readout

Pre-merge terminal: `EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_CAPABILITY_READY`.

Это **measurement capability**, не alpha, не ranking claim и не доказательство, что `PathRisk`-поверхность информативна. Информативность решает только одно отдельно авторизованное live-окно после merge.

Provider/API/RPC/WSS calls в этом PR = 0. Credential reads = 0. Cash = 0.

## Сейчас — STOP

Не авторизовывать live. Не вызывать provider. Не нажимать GitHub Merge: merge делает elected agent после exact-head CI и exact owner phrase.

```
Do not authorize live PathRisk calibration. Do not click GitHub Merge.
```

Capture packet после guarded merge и exact main read-back печатает агент с already-known 40-hex SHA. Owner эту команду сейчас не запускает. Placeholder SHA CLI отказывает.

## Запрещено сейчас и в будущем window без отдельной phrase

taker, `/build`, `/execute`, wallet, signer, transaction, retry, fallback, second provider, третья notional, второе окно, Hypothesis Forge, Paper, Strategy, Shadow, RealizedVWAP, NetReturn.

## Что умеет capability

Без нового provider/endpoint и без нового scheduler architecture, для runtime-selected mint/notional:

1. T0 BUY SOL → token
2. Immediate dependent T0 reverse того же BUY `outAmount` → SOL
3. H900 dependent SELL **того же** T0 BUY token amount → SOL (новый BUY в H900 запрещён)

Каждое quote observation хранит typed projection: `in_amount`, `out_amount`, `price_impact_pct`, `fee_bps`, `platform_fee`, `router`, `mode`, `route_hop_count`, `route_fee_amounts_present`, raw-response SHA-256 pointer. Missing = `ABSENT | NULL | UNKNOWN`, никогда zero. Raw bytes остаются в RDP, не в Git.

ObservationSchedule уже выражает `2 notionals × (T0 BUY + T0 reverse + H900 dependent SELL)` через отдельные 1M primitives с тем же endpoint. Scheduler state-machine не менялась.

## Два outcome concept (не один scalar)

- `QUOTE_NET_PROXY_N = H900_sell_out_SOL / original_SOL_notional - 1` — quote-only continuity с текущим Y; не fill, не RealizedVWAP, не NetReturn.
- `QUOTE_PATH_CHANGE_N = H900_sell_out_SOL / T0_reverse_out_SOL - 1` — PathRisk proxy после удаления static T0 round-trip. Не profitability.

`QUOTE_PATH_CHANGE_1M` и `QUOTE_PATH_CHANGE_10M` хранятся совместно. Notionals ровно `1000000` и `10000000` lamports. Третьей ступени нет.

## Fixture smoke

Zero-network user scenario PASS: R0 selection with seasoning → dual notional → T0 BUY/reverse bound to BUY `outAmount` → crash/restart sqlite → H900 SELL of the same token amount → enriched projection → RDP → readout with distinct `QUOTE_NET_PROXY` and `QUOTE_PATH_CHANGE` → terminal. Adversarial cases include absent fields, one notional unavailable, T0 reverse missing → path-change UNKNOWN, H900 missing, provider typed failure, same H900 / different T0 reverse, exact path-change zero, same buy-out cross-bind → INVALID, crash/restart, replay without new requests, raw stays in the data-root zone, redaction, no retry/fallback, no taker/`/build`/`/execute`/wallet/signer/transaction.

## Что это не значит

Capability ready ≠ surface informative. Старый v7 quote panel не активирован. Holder concentration не открывалась.

## Future live phrase — только после merge + отдельной owner authority

Не вставлять в этот чат как next step.

```
OK EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_LIVE_V1: one bounded Jupiter Free-key read-only PathRisk calibration using a local process-environment key only; Tokens V2 /recent plus one bulk /tokens/v2/search R0 snapshot plus quote-only /swap/v2/order; x-api-key header only; no .env read; no key in URL/log/receipt/Git; no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; ICP-EARLY-PUMPFUN-V1; first 4 fresh eligible mints or CALIBRATION_ELIGIBLE_BELOW_FLOOR with quote calls 0; notionals 10000000 and 1000000 lamports; T0 BUY + T0 reverse + H900 dependent SELL of the same T0 BUY token amount; one window only; no third notional; Factory runner unchanged; Hypothesis Forge, Paper, Strategy, Shadow, alpha and NetReturn forbidden.
```
