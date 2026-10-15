# Factory remote host — operator locator

Канон для любого агента, включая слабый Auto. Сначала этот файл и
`docs/operator/factory_remote_host_v1.yaml`. Не искать «текущий VPS» по
чату, Issues или recency.

Это не `FACTORY_V1_OPERATIONAL_READY` и не alpha. Секреты в Git и в чат
не попадают.

ObservationSchedule / lifecycle collector protocol:
`docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md` (не дублировать сюда).
Off-host Google Drive durability recovery: см. раздел **Durability recovery**
в том же collector runbook (`factory_remote_doctor.py --offhost-status`).

## Где хост

| Поле | Значение |
|---|---|
| Provider | Cherry Servers, EU / Lithuania |
| SKU | `CLOUD_VPS_6_GEN2` (не VPS 1) |
| Hostname | `factory-remote-ops` |
| Instance | `973818` |
| IPv4 | `5.199.174.153` |
| OS | Ubuntu 24.04 |
| Deploy | `/opt/solana-alpha-lab` |
| Portal | `https://portal.cherryservers.com/` |

IPv4 меняется только сменой этого YAML + этой таблицы одним коммитом.
Doctor JSON может ещё показывать purchase-floor `CLOUD_VPS_4_GEN2` до
отдельного schema unfreeze; для размера хоста канон — SKU в таблице/YAML выше.

## Как зайти

Ключ только `id_ed25519_factory` в `~/.ssh/` оператора (Windows:
`$env:USERPROFILE\.ssh\id_ed25519_factory`). Приватный ключ не копировать.

Пользователь только `factory`. `root` по SSH закрыт (`PermitRootLogin no`).
Cherry web-console — аварийный вход, не штатный.

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153
```

## Как дергать doctor / backup / units

На хосте, из `/opt/solana-alpha-lab`:

```
/usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/run_factory_unattended_shadow_tick.py
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --backup
```

Локальный full: каждые 12h UTC, retain 1 verified `BACKUP_*.zip`. Off-host: daily incremental checkpoint + weekly full, discovery via `RECOVERY_CHECKPOINT_<UTC>_<sha256>.json`. Подробности — collector runbook, раздел Durability recovery.

```
systemctl is-active factory-v1-workbench.service factory-remote-health.service nftables fail2ban
```

Однострочник doctor с ПК оператора:

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153 "cd /opt/solana-alpha-lab && sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py"
```

JSON doctor никогда не должен содержать токен. Вердикт `HEALTHY` запрещён.

## Workbench

Только `127.0.0.1:8765` на хосте. С ПК:

```
ssh -N -L 8765:127.0.0.1:8765 -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes factory@5.199.174.153
```

Потом `http://127.0.0.1:8765/`. Не открывать 8765 в nftables.

Telegram владельцу — HTML-карточка: тема FACTORY, классы
`OPS` 🔵🛠️ / `TRADE` 🟢📈 / `SEC` 🔴🛡️, цветные заголовки кружками
(в Bot API нет цветного текста). Блок ТОРГОВЛЯ зарезервирован. Не alpha.

## Секреты

| Где | Что |
|---|---|
| Хост | `/etc/solana-alpha-lab/secrets.env` mode `0600` |
| ПК оператора | `local/factory_remote_ops/secrets.env` (gitignored) |
| Notes | `local/factory_remote_ops/OWNER_PACKET_NOTES.txt` (gitignored) |

Не `cat` эти файлы в чат. Не коммитить `local/`. Telegram token и chat id
только там. `FACTORY_BACKUP_SINK` обязан быть **абсолютным путём на другом
volume/mount**. Пустой env = Git-side parent-independent sink под
`local/factory_v1_backup_sink` (тот же диск, другой parent). Это не
volume-independent и не DoD live RPO.

## Production software line

Git identity of the deploy tree is `.factory_deploy_sha`. That pin is not
health and not acceptance. Runtime health is a fresh doctor / status /
operational-packet readback.

Steady state: the pin is on the first-parent history of canonical `main`.
Production may lag `main`. It may not run a side branch. `local/` and host
secrets stay outside Git.

Normal release is one forward `--mode canonical-forward` via
`scripts/factory_live_release.py`. It stops scheduled code timers, waits for
an already running oneshot, and stops long-running workbench/health only when
they are `active`. `inactive`, `failed`, and `not-found` are already quiesced:
a SIGTERM that leaves the unit `failed` means no process remains, and the
release does not wait for `failed` to become `inactive`. A transitional or
`unknown` long-running state aborts before the tree changes. It then installs
one exact archive and restores the prior timer and service state. It does not
kill a collector tick and does not run target-rollback-target.
`--mode canonical-rollback` is an explicit owner rollback. Automatic recovery
after a failed install is not that mode: it puts the previous tree back before
any unit is started again. `ABORT_DEPLOY` means a oneshot or long-running unit
did not reach a non-running terminal, or a long-running unit was transitional;
the tree was not changed, and triggers were put back. `UNRESOLVED_RECOVERY` means the new tree failed and the previous
tree could not be verified; timers and long-running services stay stopped.
The one divergent host SHA
`aaf7f89c3bfc71de9d56618fdda0d3d69cfaf236` may move only onto the current
`main` that contains this repair, as `--mode legacy-convergence`.

## Live apply

Фраза `OK FACTORY_REMOTE_OPERATIONS_V1 LIVE HOST:` уже получена.
Владелец дал standing-право на мутацию этого хоста в рамках Atom 3:
SSH/scp/пакеты/systemd/nftables/fail2ban/doctor/backup/fault injection
без микроподтверждений. Не дергать владельца на каждый шаг.

Стоп только: секреты в чат/Git, кошелёк/signer/tx, смена провайдера,
новый атом.

## Запрещено

- парольный SSH, root login как цель (после apply)
- публичный admin / `0.0.0.0:8765`
- печатать или коммитить секреты
- абсолютные пути дома оператора в Git
- называть это operational-ready / alpha / DONE

## I2 backup / retirement / reclaim

Точный resume — `docs/tasks/I2_BACKUP_LEGACY_STORAGE_V1.md`; staged внедрение и
destructive APPLY — `docs/evidence/i2_backup_legacy_storage_v1/OPERATE_PACKET.md`.
Этот раздел не продлевает historical Atom 3 standing authority на I2.
Без отдельного exact OPERATE запрещены deploy/upload, live retirement/reclaim,
remote deletion, включение maintenance и изменение effective policy.

Backup использует один immutable capture для inventory и ZIP, DEFLATE level 1
и ZIP64. В mutable-only режиме capture также замыкает native authority/state
events и open publication dependencies. Captured SQLite sidecars не пакуются.
Reader принимает legacy STORED full вместе с новыми DEFLATE deltas; проверяет
actual extracted inventory каждого шага, затем final inventory, затем ставит
unresolved restore marker. Восстановленный collector требует reconciliation.
Для actual legacy mutable-only full без authority/state ResearchEvents final
control closure проверяется после новой delta, не раньше. Неполный standalone
full или final missing event отказывается без marker; old bytes не переписываются.

Offhost caller сохраняет immutable pending operation: после unknown upload
следующий запуск продолжает те же bytes и checkpoint. Last-good и failed attempt
показываются отдельно. CURRENT считается от snapshot data-as-of, а не от конца
upload; baseline revision 1 остаётся 24h. Revision 2 требует совместных 30h
CURRENT и RPO, но не редактирует APPLIED profile. Unknown/живой lock не снимать.
Штатный caller сам повторяет busy до120min с шагом30s; weekly/daily overlap
принимает один проверенный новый checkpoint без второго capture/upload.
Исчерпание — exit2/COPY_FAILED/OFFHOST_BUSY_RETRY_EXHAUSTED с exact resume,
last-good сохраняется. Actual unit/drop-in timeouts проверяются при OPERATE;
retry не продлевает RPO и freshness. Два bounded scheduler incident receipts
находятся рядом с существующим receipt.
`BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED` означает сохранённый staging с
неподтверждённым владельцем: inspect exact owner/bytes в отдельном recovery scope,
не удалять каталог вслепую. Known-dead owned capture восстанавливает обычный caller.

`factory_offhost_backup_copy.py --mode verify-remote-restore` скачивает exact
checkpoint closure в новый явно выделенный isolated root. Remote pruning
сначала связывает retained checkpoint graph и durable restore-proof artifacts
в plan hash; отдельный apply повторяет raw reconstruction/SQLite oracle и
remote identity. Удаление требует dedicated explicit permission. Для prune
учитывать дополнительную временную raw copy внутри owned `.prune-verify`.

Reclaim пишет durable ALLOCATING intent до new DB; ordinary native writable
opens/ticks и уже открытые writers отказывают при unfinished recovery до записи
или bootstrap исчезнувшего main. Exact `reclaim-resume`/`reclaim-rollback`
выполняются по staged OPERATE. После durable resume decision rollback запрещён;
повтор resume заканчивает owned cleanup и оставляет небольшой FINALIZED receipt,
удаляя точные rollback/staging bytes. Не удалять intent/staging вручную.
Первый fsynced intent.tmp штатно принимает exact rollback. Для torn first JSON
передать сохранённый approved `--plan` с теми же roots/hash; отсутствие plan даёт
`RECLAIM_INITIAL_PLAN_REQUIRED`. Проверяются original inode/native fingerprint,
отсутствие stages и точный plan self-hash. Backup отказывает при unfinished
reclaim; проверенная terminal inode-bound квитанция в portable payload не входит.
