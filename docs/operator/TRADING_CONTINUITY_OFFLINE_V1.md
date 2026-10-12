# Обычный PAPER/SHADOW: запуск, контроль и восстановление

Вход: `SEM-OWNER-LIFECYCLE` → этот runbook → `scripts/trading_continuity.py`.
Один процесс `run` читает опубликованные source episodes, принимает решения
через shared recipe/PIT owners, создаёт попытки, получает model/quote results
и обслуживает исходные выходы. Ручной JSON на каждый токен не нужен.
Научное разрешение, явная activation и операционное здоровье — разные факты.
Этот software-атом не разрешает рабочие настройки, provider, credentials,
deployment, LIVE, signer, транзакции или деньги.

Поддержанный successor — **A@V1 → B@V1 с разными scientific identities**.
Same-ID V2 остаётся запрещён. Исторические S08/S13 и `REPAIR_PARTIAL_BLOCKED`
сохранены в [предыдущем отчёте](../reports/smial_trading_continuity_v1/REPORT.md).
Новая возможность основана на принятом D1–D4, а не на пересмотре того аудита.

## Подготовка один раз

Используй существующий locked toolchain: `uv run --locked --managed-python
python -B scripts/trading_continuity.py <command> ...`. Далее этот префикс
сокращён до `CLI`; это обозначение, не отдельная установленная команда.

Каждый вызов получает `--repository-root <repo>` и `--data-root <runtime>`.
Для синтетического прогона runtime — отдельный новый child в `<repo>/local`:

```text
CLI init --repository-root <repo> --data-root <repo>/local/<owned-case>
```

Вне синтетического сценария `init-operating` требует уже существующий
`--scope-root <exact-scope>` и явный `--evidence-class OBSERVED`. Runtime
должен быть пустым отдельным child этого scope; aliases, junctions, symlinks
и hardlinked store запрещены. Создание marker не запускает работу.
Для дальнейших вызовов такого root повторяй `--scope-root <exact-scope>`.

В runtime один раз положи **явный operating profile**. Он связывает конкретный
source store/schedule/activation, размер страницы, интервалы polling и freshness,
лимиты незавершённых обязательств и настройки adapters. Пример структуры:

```json
{
  "schema_version": "1.0", "mode": "PAPER",
  "source": {"root": "<absolute-source-root>", "file": "observation_schedule_state.sqlite",
    "schedule_sha256": "<exact-schedule-sha256>", "activation_id": "<exact-source-activation>"},
  "batch_size": 64, "poll_seconds": 1,
  "source_max_age_seconds": 120, "progress_max_age_seconds": 120,
  "observation_max_age_seconds": 120,
  "envelope": {"schema_version": "1.0", "mode": "PAPER", "basis": "OUTSTANDING_OBLIGATIONS_V1",
    "max_outstanding_positions": 1, "max_outstanding_cost_basis_usd": "30"},
  "model": {"version": "TIMELY_OBSERVATION_MODEL_V1", "latency_seconds": 0,
    "additional_cost_usd": "0.01", "missing_input": "UNKNOWN"},
  "quote": {"timeout_seconds": 5, "max_response_bytes": 65536,
    "funding_mint": "<exact-funding-mint>", "asset_metadata_file": null,
    "funding_observation_file": "funding.json", "max_exit_input_raw": null},
  "network_authorized": false
}
```

Числа выше — параметры примера, не разрешённые рабочие defaults. Для SHADOW
mode/envelope должны явно быть SHADOW. `asset_metadata_file: null` получает
decimals автоматически из exact vendor witness raw body исходного episode:
response/object SHA и mint проверяются, metadata сохраняется внутри ENTRY
request. Старый EXIT использует эту запись после retention исходных raw bytes.
Не создавай JSON на каждый токен. Альтернатива — один явно связанный source
metadata file. Файл funding observation обязателен при quote request;
decimals/mint/clock/FX проверяются перед расчётом raw units.
`max_exit_input_raw` явно ограничивает одну выходную ногу либо равен
null. Recipe должен содержать explicit `runtime_execution` с FROZEN_TIME_EXIT
и своим exit point; научный target сам по себе не даёт executable exit.

Оба input paths относительны к **profile.source.root**, не к runtime. Funding
producer атомарно обновляет один `funding.json` для mode; схема:

```json
{"mint":"<funding_mint>","decimals":9,"unit_price_usd":"<observed-positive-USD-price>","observed_at":"<UTC>","available_at":"<UTC>"}
```

Нужен доказанный `observed_at <= available_at <= now`, age не больше
observation_max_age_seconds. Нельзя выводить FX из имени SOL/USDC или quote
номинала. Для file metadata схема — map `<mint>` → `{mint, decimals,
observed_at, available_at}`. У existing native Jupiter Tokens producer уже
есть vendor decimals/price; предоставление отдельного funding observation —
явный контракт producer → adapter, а не ручной result/fill. Commissioning
проверяет разрешённый producer и cadence. Этот атом не подключает провайдера.
`check` и activation проверяют quote input files до работы; отсутствующий
funding input даёт EXECUTION_QUOTE_INPUT_NOT_PRESENT, stale/future —
EXECUTION_OBSERVATION_STALE_OR_FUTURE. Price UNKNOWN не считается inventory=0.

## Проверка и обычный цикл

```text
CLI check --mode PAPER --strategy strategy-a.json --profile profile.json
CLI operating-activate --mode PAPER --strategy strategy-a.json --profile profile.json --epoch A --as-of <UTC> --switch-key activate-A
CLI run --mode PAPER
CLI status --mode PAPER --format human
```

`check` проверяет scientific handoff и profile без activation. Activation
сохраняет strategy/manifest/binding/recipe/original spec bytes, profile и общий
mode envelope одной транзакцией. `run` использует сохранённый epoch; повторный
запуск не создаёт новый. `--ticks N` задаёт ограниченный прогон. Stop signal
закрывает процесс корректно; kernel lock исключает второго sender. `--as-of`
или `--clock-file` для run/tick разрешены только синтетическому root.

PAPER использует timely observation model. SHADOW использует production
Jupiter quote parser; quote никогда не объявляется actual fill. Без отдельного
external grant provider вызов запрещён. Для будущего разрешённого OBSERVED
SHADOW CLI принимает `--quote-grant <runtime-relative-file>` и
`--credential-env <existing-variable-name>`. Grant связывает registry-011 SHA,
route, epoch, strategy SHA, срок, call cap и запрет финансовой/signing authority.
Credentials читаются только после проверки grant, а call claim сохраняется
до HTTP. Используется единственный GET `/swap/v2/order` без taker/transaction;
redirect/retry запрещены. Этот atom такой вызов не выполняет.

## Управление и смена стратегии

```text
CLI pause --mode PAPER --bot-instance-id <bot> --idempotency-key pause-1
CLI resume --mode PAPER --bot-instance-id <bot> --idempotency-key resume-1
CLI drain --mode PAPER --bot-instance-id <bot> --idempotency-key drain-1
CLI close --mode PAPER --position-id <position> --idempotency-key close-1
CLI switch --mode PAPER --strategy strategy-b.json --profile profile-b.json --epoch B --expected-current-epoch A --as-of <UTC> --switch-key A-to-B
```

Стратегия для status/control/result/recovery не нужна. Pause/drain/switch
останавливают новые входы; неотправленные admissions отменяются. Исходные
выходы и выяснение UNKNOWN продолжаются. Invalid B или stale expected epoch
не выключают A; в mode лишь один entry-enabled bot. Незавершённые обязательства
A потребляют общий лимит и после появления B. PAPER и SHADOW имеют отдельные
envelopes. При UNKNOWN headroom не освобождается; auto-shrink отсутствует.
Explicit envelope change использует `envelope --input <request>` с exact
current hash/idempotency key и отдельной фразой authority из policy.

Definitive failed exit сохраняет inventory и допускает новую attempt identity.
UNKNOWN не отправляется повторно: нужен результат той же попытки. Partial exit
уменьшает quantity/cost basis пропорционально и оставляет remaining obligation.
Fee внутри quote не вычитается второй раз. Source/research retention не меняет
originating decision; при недостаточном доказательстве показывается gap.

## Наблюдение

`status` открывает свежий readonly WAL-aware snapshot; не мигрирует DB и не
делает checkpoint. Он раздельно показывает process_alive, inputs_fresh,
work_moving, integrity_verified и exit_obligations_healthy, pause/drain,
current epoch, outstanding inventory и earliest overdue work.
`process_alive` — оценка свежести последнего heartbeat в пределах явного TTL,
а не проверка живого OS process. После graceful shutdown она может оставаться
true до истечения TTL; READY описывает software snapshot, не работу процесса
под host supervision. Ожидание будущего exit point не считается зависанием.
UNKNOWN и missing/corrupt binding не превращаются в healthy.
READY также требует VALID для текущего общего operating envelope и проверенных
входов исполнения. Для SHADOW status заново читает funding/asset inputs и их
clocks: missing, stale, future или повреждённый вход даёт ACTION_REQUIRED с
точным execution_input_status. source_fresh и input_fresh показаны отдельно.
Повреждённый/отсутствующий envelope показывает operating_configuration_status
и VERIFY_OPERATING_ENVELOPE; quote gap — CHECK_EXECUTION_QUOTE_INPUTS. Первое
безопасное действие — readonly readback, затем проверка собственного profile
через описанный CLI check. Это не разрешение менять рабочие настройки.
Здоровье исходных выходов остаётся отдельным показателем: проблема текущих
entry inputs не превращается в отказ обслуживания здорового старого риска.

Economics в status ограничены последними 100 position rows каждого mode;
полный linked readback — `CLI readback`. Trade PnL, дополнительные model costs,
known floor и UNKNOWN раздельны. Synthetic PAPER и quote-only SHADOW не дают
NetReturn, owner FCF или alpha. Scientific monitoring thresholds —
NOT_CONFIGURED, пока owner не задаст их отдельным контрактом.

## Backup и cold recovery

```text
CLI backup --mode PAPER --destination backups/cut.sqlite
CLI export-cut --mode PAPER --backup <exact-backup-path> --input independent-effect-receipts.json --external-cut-id <stable-cut-id> --as-of <cut-UTC> --complete-after-backup --destination external-cut-input.json
CLI init --repository-root <repo> --data-root <repo>/local/<fresh-owned-case>
CLI restore --mode PAPER --backup <exact-backup-path>
CLI status --mode PAPER
CLI seal-cut --mode PAPER --input external-cut-input.json --destination complete-external-cut.json
CLI reconcile --mode PAPER --input complete-external-cut.json
CLI ack-restore --mode PAPER --input complete-external-cut.json --inventory-sha256 <exact-current-inventory-sha256> --as-of <UTC>
```

Каждый вызов использует свой exact runtime. Backup — native SQLite snapshot
с manifest/hash и frozen dependency closure. Future source observations не
входят в этот cut. Restore требует fresh marked root, проверяет snapshot и
ставит fence: новых effects нет до reconciliation. Внешний ledger при restore
DB не откатывается. Complete external cut связывает backup SHA, mode, cut ID/
clock, все original effect receipts после backup, pending attempt/request,
consumed quote grant claims, current entry epoch/generation, полный control
set и frozen operating bindings, включая switch без effects после backup.
Receipt удерживает исходную reservation и verified
originating closure, зафиксированную до эффекта. Так восстанавливается даже
позиция, которой ещё не было в backup. Выходные receipts импортируют исходный
EXIT packet/binding; новый send не выполняется. Cut применяется одним CLI
вызовом; повтор идемпотентен, content conflict запрещён. Naked inventory ACK
отказывает. ACK требует reconciled complete cut, exact known inventory,
отсутствие pending attempts и проверенные bindings. Все восстановленные bots
остаются paused; последующий local STOP/DRAINING не отменяется старым cut.
Quota claims без response также потребляют grant; pending attempt/request
восстанавливаются на прежней identity без выдуманного result/clock. Inventory
остаётся UNKNOWN; SHADOW не отправляется заново и не позволяет ACK. PAPER
детерминированно завершает сохранённый request своим исходным result_at.
После сверки current controls оператор отдельно разрешает
новые входы. Работа с реальным ledger требует отдельной commissioning
authority; software proof использует независимый синтетический ledger.

`status` отдаёт `inventory_sha256`, generation и bot/position IDs; human output
показывает fence, controls, overdue и следующий CLI command. Не вычисляй SHA
вручную. `seal-cut` проверяет данный внешним ledger cut и добавляет canonical
self-hash, но не доказывает полноту самостоятельно. `export-cut` на
сохранившемся исходном runtime читает согласованный readonly snapshot и
экспортирует bindings, controls, quota/pending identities и исходные принятые
result observations с их IDs и physical clocks. Последний UNKNOWN total не
стирает ранее подтверждённый cost floor. В `--input` он
принимает один полный массив original external receipts; флаг
`--complete-after-backup` явно подтверждает независимую полноту. Команда не
доказывает её сама и не считывает provider. Пропуск accepted native результата,
которого ещё нет в backup, или конфликт с ним даёт
RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING: известный факт нельзя спрятать
за флагом полноты. Сохрани output вне откатываемого
runtime вместе с независимым ledger до потери источника. После restore
скопируй input в новый runtime и выполни seal-cut. Если original runtime уже
утрачен, поля берутся из ранее сохранённого независимого cut. Input имеет эти
поля (без `cut_sha256`); замени placeholders фактами независимого cut:

```json
{
  "schema": "smial.operating-external-recovery-cut", "schema_version": "1.0",
  "mode": "PAPER", "backup_sha256": "<database_sha256 из backup manifest>",
  "external_cut_id": "<stable-independent-cut-id>", "as_of": "<cut-UTC>",
  "completeness": "COMPLETE_AFTER_BACKUP",
  "effects": [],
  "result_observations": [],
  "pending_attempts": [], "quote_claims": [],
  "operating_bindings": [{"activation": "<original OFFLINE_ACTIVATION_CREATED event object>", "binding": "<original OPERATING_BINDING_COMMITTED event object>", "profile": "<original OPERATING_PROFILE_COMMITTED event object>"}],
  "current_entry": {"epoch_id": "<actual-current-entry-epoch>", "generation": 1},
  "controls": [{"bot_instance_id": "<actual-bot-id>", "status": "RUNNING", "entries_paused": true}]
}
```

`effects` — полный упорядоченный массив исходных `{attempt, request, result,
receipt_sha256}` objects из независимого durable ledger, не новые ручные
fills. Пустой массив допустим только при доказанном отсутствии effects после
backup. `result_observations` — original MODELED_RESULT_ACCEPTED
event objects после backup в исходном порядке, включая ранние known costs.
Restore проверяет их identity/clock и принимает через прежний accounting owner
до последнего receipt; exact replay не прибавляет стоимость повторно.
Пустой массив допустим только при отсутствии таких принятых наблюдений.
`pending_attempts` содержит original `{attempt, request}` без
definitive result; `quote_claims` — все оригинальные QUOTE_CALL_CLAIMED event
objects; `operating_bindings` — тройку original events для каждого bot mode.
Строковые placeholders выше заменяются **объектами**, не остаются строками;
обычный export-cut уже выдаёт эти поля и не требует их составления вручную.
Receipt request содержит pre-effect recovery_closure; без неё missing
historical reservation не импортируется. `controls` включает все bots mode;
current_entry и control flags берутся из внешнего cut, а не угадываются по
восстановленной DB. Если cut/closure недоступны, fence остаётся, показывается
UNKNOWN; ни inventory=0, ни reassurance его не снимают.

Migration additive; legacy NULL provenance остаётся typed gap. Старый бинарник
не гарантирует безопасное обслуживание ordinary v1.1 store. Rollback code
не откатывает данные: останови entries, используй совместимый closure binary
для drain/export/native restore, сохрани accepted science/runtime history.
Не удаляй DB ради возврата старой версии. Frozen evidence удерживается до
закрытия/выяснения всех originating obligations; current files не нужны.

## Самодостаточный proof и cleanup

```text
uv run --locked --managed-python python -B scripts/prove_trading_core_operational_closure.py --suite --output docs/evidence/smial_trading_core_operational_closure_v1/executed-tests.json
```

Нужен существующий locked toolchain и Git; новые зависимости не устанавливаются.
Suite использует disposable marked roots, собственный scientific producer Git,
обычный coordinator/run, реальные процессы/kill/SQLite backup, fake HTTP bytes
и независимый durable ledger. Двухнедельный source stream исполняется виртуальным
временем; history scale, durations, peak RSS и disk записываются в компактную
receipt. Synthetic results не являются scientific/OOS/live доказательством.
Все выделенные roots очищаются в teardown; receipt отмечает их отсутствие.
Shared cache/.venv, рабочие datasets, чужие roots/branches не удаляются.
Результат, C01–C24 и residual ledger — в
[closure report](../reports/smial_trading_core_operational_closure_v1/REPORT.md).
