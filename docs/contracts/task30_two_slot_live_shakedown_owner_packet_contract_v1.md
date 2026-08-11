# TASK-30 Two-slot live shakedown owner-packet contract v1

## Purpose and binding

Контракт задаёт только форму будущего owner-review после A11A. Он привязан к
frozen group `RC001-H07-H01-LIQUIDITY-RETENTION`, 900-second observation grid,
A10 `START_LABELED` receipt и A11A offline acceptance. Он не меняет
hypothesis, не выбирает provider и не разрешает запрос.

## Candidate route

Кандидат — public keyless GeckoTerminal path:

`GET /api/v2/networks/solana/pools/{pool}/ohlcv/minute`

с `aggregate=15`, `currency=usd`, `token=base`,
`include_empty_intervals=false`, `limit=1` и
`before_timestamp=slot_end_utc`. Для ожидаемого closed slot contract требует
`observed_interval_start=slot_start_utc`; semantic mismatch — не
успех. Ключи, credentials, retries и fallback запрещены.

## Future shakedown proposal

Будущий owner-approved run может содержать ровно два slots. Каждый запускается
отдельно в foreground и делает не больше четырёх GETs на offsets `0, 15, 30,
60` seconds after its closed boundary. Total max = 8. Запланированные UTC
границы и monitoring owner остаются `OWNER_INPUT_REQUIRED` до отдельного
gate; A11B не подставляет вымышленные времена.

После каждого ответа будущий run обязан сохранить raw JSON вне Git under A4 и
сразу записать immutable manifest/hash plus health receipt. Второй slot
запрещён, пока receipt первого не читается и не подтверждает health/retention.

## Fail-closed recovery

`PROCESS_NOT_STARTED`, `RECEIPT_WRITE_FAILED`,
`PRIOR_MANIFEST_UNREADABLE` и `MONITORING_LOST` дают `STOP_RUN`.
Они не являются market gap, не позволяют retry/fallback/hidden restart и не
переносятся в следующий slot. `TYPED_GAP` остаётся неизвестностью.

## Future live terminal states

- `SHAKEDOWN_PASSED_TECHNICAL_ONLY`: оба slots имеют retained observations
  and no health failure.
- `SHAKEDOWN_FAILED_ROUTE`: retained response contradicts bound route or
  interval semantics.
- `SHAKEDOWN_INCONCLUSIVE`: typed gap or health failure.

Ни один state не authorises 24-hour capture. Только
`SHAKEDOWN_PASSED_TECHNICAL_ONLY` может породить новый owner gate for that
decision.

## Exact next owner boundary

Перед любым provider action owner packet must bind: provider/endpoint/pool,
two exact UTC slot starts, eight-read maximum, retention A4 location,
monitoring owner, stop/recovery procedure and an exact approval phrase.
Только then can another atom request a separately scoped provider-read
authorization. A11B remains offline.
