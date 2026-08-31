# PathRisk real wall-clock live execution — owner readout

Pre-merge terminal: `PATHRISK_REAL_WALLCLOCK_LIVE_EXECUTION_PASS_READY_FOR_MERGE_GATE`.

Это **production execution glue** для уже принятой one-window PathRisk калибровки. Estimand, population, notionals, H900 semantics и terminals не менялись. `PATHRISK_SURFACE_INFORMATIVE` не значит alpha, profitability или NetReturn.

Provider/API/RPC/WSS calls в этом PR = 0. Real credential value reads = 0. Cash = 0. Wallet/signer/tx = false. `capture_authorized` в Git остаётся `false`.

## Что закрыто

1. Production CLI: `live-run --real-provider`. Fixture больше не обязателен. `--fake-provider-fixture` и `--real-provider` взаимоисключающие.
2. Production отвергает `--now` и `--stop-after`. Fixture mode требует `--now` и никогда не открывает сеть.
3. Canonical credential name: `JUPITER_API_KEY` (не выдуманный `JUPITER_FREE_API_KEY`). Только process environment, без `.env`.
4. Credential читается только после non-secret gates. Нет ключа → `CREDENTIAL_ENV_MISSING_BEFORE_PROVIDER`, `provider_calls=0`, CLI exit 1.
5. Production clock: `SYSTEM_UTC`. FrozenClock запрещён. H900 ждёт `firstPool.createdAt + 900s` по каждому mint. Пока ждёт, stderr: `PATHRISK_LIVE_WAITING_H900`.
6. Runtime one-window schedule материализуется в DATA_ROOT, не из Git timestamps 2026-09-01/02.
7. Crash/resume: тот же `--data-root`. Не повторяет completed calls и не пересэмплирует R0.
8. Journal: `<DATA_ROOT>/pathrisk_live/ACT-PATHRISK-LIVE-001/journal.json`.

## Этот PR — только preflight

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py live-preflight --main-sha <EXACT_MAIN_40HEX>
```

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py capture-packet --main-sha <EXACT_MAIN_40HEX>
```

`live-preflight` всегда печатает `live_authorized: false` — это Git-истина этого PR, не запрет phrase после merge. Точная phrase: поле `future_owner_phrase` в JSON `capture-packet`. Env: `JUPITER_API_KEY`.

## Production command after merge

Не запускать в этом PR. После guarded merge + read-only preexec. Process будет молчать минуты, пока wall-clock не дойдёт до H900 — это правильно.

```
uv run --locked --managed-python python -B scripts/early_quote_surface_pathrisk_calibration.py live-run --main-sha <EXACT_MAIN_40HEX> --owner-phrase <EXACT_PHRASE> --data-root <DATA_ROOT> --producer-git-sha <PRODUCER_40HEX> --real-provider
```

`--main-sha` = текущий exact main. `--producer-git-sha` = Git SHA процесса-продюсера (не путать с main). Чистый `--data-root`, не leftover fixture window.

## Сейчас — STOP

Не вызывать provider. Не читать реальный ключ. Не нажимать GitHub Merge.

```
Do not authorize live PathRisk capture in this PR. Do not click GitHub Merge.
```
