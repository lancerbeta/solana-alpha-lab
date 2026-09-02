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
