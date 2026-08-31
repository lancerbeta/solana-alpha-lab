# PathRisk recent HTTP class — owner readout

Pre-merge: `PATHRISK_LIVE_RECENT_HTTP_CLASS_PASS_READY_FOR_MERGE_GATE`.

## DONE

HTTP status и `http_class` больше не теряются на новых вызовах. 401/403/429/5xx/timeout/transport на `/recent` — отдельные операционные терминалы, не generic binding miss. Старое окно `ACT-PATHRISK-LIVE-001` не меняли.

Provider calls в этом PR = 0. Ключ не читали.

## BLOCKED

В этом PR запрещены: Jupiter, `--real-provider`, второе PathRisk window, reopen `ACT-PATHRISK-LIVE-001`. GitHub Merge не нажимать.

## NEXT

Только merge gate этого PR. Probe и live-run — не сейчас.

Печать будущей probe phrase (без сети, без ключа, можно сейчас):

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py transport-probe-recent --print-phrase
```

Точная probe phrase (не PathRisk calibration phrase; не исполнять `--real-provider` в этом PR):

```
OK PATHRISK_LIVE_RECENT_TRANSPORT_PROBE_V1: one GET https://api.jup.ag/tokens/v2/recent using a local process-environment JUPITER_API_KEY only; x-api-key header only; no .env; no key in URL/log/receipt/Git; no search, /swap/v2/order, taker, /build, /execute, wallet, signer, transaction, retry or fallback; no PathRisk activation or scientific window; cash cap $0; call cap 1.
```

## AFTER MERGE (не этот PR)

Один GET `/tokens/v2/recent`. Не `live-run`. Не второе PathRisk window. PathRisk calibration phrase даёт `OWNER_PHRASE_MISMATCH`. PowerShell: phrase в одинарных кавычках, иначе `;` и `$0` ломают строку.

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py transport-probe-recent --real-provider --owner-phrase 'OK PATHRISK_LIVE_RECENT_TRANSPORT_PROBE_V1: one GET https://api.jup.ag/tokens/v2/recent using a local process-environment JUPITER_API_KEY only; x-api-key header only; no .env; no key in URL/log/receipt/Git; no search, /swap/v2/order, taker, /build, /execute, wallet, signer, transaction, retry or fallback; no PathRisk activation or scientific window; cash cap $0; call cap 1.'
```

## Терминалы (live-run, не probe)

`R0_RECENT_HTTP_401_UNAUTHORIZED`, `R0_RECENT_HTTP_403_FORBIDDEN`, `R0_RECENT_HTTP_429_RATE_LIMITED`, `R0_RECENT_HTTP_OTHER_4XX`, `R0_RECENT_HTTP_5XX`, `R0_RECENT_TIMEOUT`, `R0_RECENT_TRANSPORT_ERROR`, `R0_RECENT_NO_HTTP_RESPONSE`.

Probe печатает JSON `http_status` / `http_class` / `scientific_window_started: false`, без `terminal`.

Исторический call без сохранённого кода: `UNKNOWN_NOT_RECORDED_AT_TIME`, не 401.

```
Do not authorize the transport probe in this PR. Do not click GitHub Merge.
```
