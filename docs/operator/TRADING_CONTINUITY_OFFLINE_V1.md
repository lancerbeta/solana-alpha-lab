# Проверка обычного trading-пути offline

Вход: `SEM-OWNER-LIFECYCLE` → этот runbook → `scripts/trading_continuity.py`.
Это локальный PAPER/SHADOW-контур с поддельной внешней стороной. Научная
допустимость, materialization, activation и результат исполнения — разные шаги.
Рабочий хост, provider, LIVE, кошелёк и деньги требуют отдельного разрешения.

Самодостаточное воспроизведение acceptance на существующем locked toolchain:

```powershell
$env:UV_CACHE_DIR='C:\Users\lance\AppData\Local\uv\cache'
$env:UV_PYTHON_DOWNLOADS='never'
$env:UV_OFFLINE='true'
uv run --locked --managed-python python -B scripts/prove_trading_continuity.py --phase fresh
uv run --locked --managed-python python -B scripts/prove_trading_continuity.py --phase clean
```

`fresh` требует отсутствия прежнего campaign root и manifest. Скрипт записывает
ownership до создания ресурсов, использует allowlist окружения и sacrificial
egress canary, исполняет реальные owners в временном root, затем удаляет case.
`clean` проверяет exact root, marker и отсутствие ссылок/junctions, сохраняет
компактный receipt и удаляет остаток campaign. Чужие roots/cache/env не затрагивает.
При отказе realpath не обходить проверку; использовать разрешённый host executor.

Для отдельного sandbox нужен пустой root внутри `<repo>/local`, marker
`offline_runtime.json`, exact StrategyVersion 1.1 и bound ResearchStore в
`<data-root>/research-data`. Frozen source observations находятся в той же
песочнице. `init` создаёт только marker, `load` проверяет handoff и не запускает bot.
Полный порядок команд: `init → load → activate → episode → attempt → result →
exit → attempt → result → readback`. Все команды требуют `--data-root`; кроме
init — `--strategy <repo-relative-file>`. `activate` требует `--epoch`, `--mode`
и `--as-of`. `episode` требует `--episode-id`, `--epoch`, `--mode`, `--as-of` и
`--source <data-root-relative-sqlite>`. `attempt` требует position-id, side,
attempt-key и as-of. `result` и `operator` принимают `--input` только внутри root.
Полный CLI пример и literal arithmetic oracle исполняются в
`tests/test_trading_continuity_v1.py::test_ordinary_full_chain_decimal_oracle`.

Ниже шаблон обычных команд после подготовки **exact** разрешённых offline
inputs. Заменить значения в угловых скобках идентичностями из своих receipts;
это не разрешение использовать production root или реальную стратегию.

```powershell
$OfflineRoot = Join-Path (Get-Location) 'local/offline-example'
$Strategy = 'configs/strategies/<exact-materialized-version>.yaml'
function Invoke-Continuity {
    uv run --locked --managed-python python -B scripts/trading_continuity.py @args --data-root $OfflineRoot --strategy $Strategy
}
Invoke-Continuity init
# Поместить bound ResearchStore и source bytes в этот root, затем:
Invoke-Continuity load
Invoke-Continuity activate --epoch <exact-epoch> --mode PAPER --as-of <activation-time>
Invoke-Continuity episode --episode-id <exact-episode> --epoch <exact-epoch> --mode PAPER --as-of <cutoff>
Invoke-Continuity attempt --position-id <returned-position> --side ENTRY --attempt-key ENTRY-1 --as-of <attempt-time>
Invoke-Continuity result --input entry-result.json
Invoke-Continuity exit --position-id <returned-position> --as-of <exit-cutoff>
Invoke-Continuity attempt --position-id <returned-position> --side EXIT --attempt-key EXIT-1 --as-of <exit-attempt-time>
Invoke-Continuity result --input exit-result.json
Invoke-Continuity readback
```

`entry-result.json` внутри root, пример controlled fake, только когда размер и
fee действительно связаны к такому admitted regime:

```json
{"attempt_id":"<returned-attempt>","result_id":"ENTRY-RESULT-1","outcome":"LANDED_SUCCESS","observed_at":"<result-time>","unit_price_usd":"0.000003","filled_notional_usd":"30","chargeable_cost_usd":"0"}
```

Exit result имеет ту же форму, side определяется attempt; для полного modeled
exit опустить filled_notional_usd и задать unit_price_usd. Для transport UNKNOWN
передать outcome=UNKNOWN_REQUIRES_RECONCILIATION без price/notional: оставить
cost отсутствующим, если он неизвестен. Поздний definitive result получает
новый result_id и ту же attempt_id. Повтор exact result сохраняет result_id.

В operator JSON: `command_type`, `idempotency_key` и bot_instance_id из readback
для PAUSE_NEW_ENTRIES / RESUME_NEW_ENTRIES / STOP_BOT; для
REQUEST_CLOSE_POSITION — position_id. Пример:

```json
{"command_type":"PAUSE_NEW_ENTRIES","idempotency_key":"PAUSE-1","bot_instance_id":"<exact-bot>"}
```

Вызов: `Invoke-Continuity operator --input operator-command.json`. Не изменять
payload под прежним idempotency_key. Код 2 + status=BLOCKED означает отказ;
сначала устранить exact reason_code у его source owner, не повторять вслепую.
Для UNRESOLVED после definitive NO_ROUTE можно открыть **новую** exit attempt
с новым key. Для UNKNOWN сначала reconciliate ту же attempt. Новая версия
обслуживается отдельно; старую позицию закрывает runner её originating version.

Отправлять fake modeled result можно только после `send_permitted=true`.
Повтор attempt возвращает false: сначала выяснить outcome прежней identity.
UNKNOWN требует reconciliation, не новой покупки. NO_ROUTE на выходе сохраняет
inventory. После STOP_BOT отдельно запросить REQUEST_CLOSE_POSITION; остановка
новых входов не является evidence закрытия. Scientific exit после deactivation
заблокирован; operator/reconciliation остаётся доступен. Exact result replay
восстанавливает незавершённый drain после crash.

Readback показывает positions, causal attempts/results, scope, unknown costs,
торговый PnL и дополнительные расходы отдельно. MIXED_SCOPE не имеет общего
денежного headline. BLOCKED/unavailable не означает flat. Missing state не
bootstrap-ится чтением. Для restore использовать native SQLite backup и exact
копии frozen spec, ResearchStore/source dependencies и marker в свежем root;
после integrity_check сверить policy hash, origin lineage и pending identity.

Supported recipes и отказные ветки: `docs/contracts/episode_decision_continuity_v1.md`.
Cleanup относится к среде, product fixes и компактные evidence остаются в Git.
Ни synthetic PROMOTE в disposable fixture, ни modeled PnL не разрешают научное
promotion, commissioning или live trading.
