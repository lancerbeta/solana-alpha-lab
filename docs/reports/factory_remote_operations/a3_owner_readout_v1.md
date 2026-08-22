# Factory remote operations — owner readout

Терминал Git-стороны: `FACTORY_REMOTE_OPERATIONS_GIT_READY`.
Живой Cherry-хост `factory-remote-ops` уже стоит (пакет владельца
вернулся). Это не `FACTORY_V1_OPERATIONAL_READY`, не alpha и не «оставьте
и забудьте навсегда без агента».

Локатор для агентов, не для вашей Linux-админки:
`docs/operator/FACTORY_REMOTE_HOST.md` и
`docs/operator/factory_remote_host_v1.yaml`.

## Что теперь правда

- Git-side: doctor, parent-independent backup restore, security templates,
  Telegram HTML, fail-closed HEALTHY, `AllowUsers factory`.
- Health-loop шлёт одну карточку на incident_key. «ЧТО СДЕЛАТЬ» = напишите
  агенту, не SSH.
- Doctor без флагов смотрит `systemctl is-active factory-v1-workbench`.
- Live host: loopback Workbench, root SSH закрыт, Telegram boot+dedup,
  kill/restart Workbench recovered. Байты SQLite на хосте — не Git-истина.
- `FACTORY_BACKUP_SINK` = абсолютный путь на другом volume. Пустой env =
  parent-independent на том же диске, не volume-independent.

## Почему не VPS за 9 долларов

Cherry Servers по-прежнему принимает crypto. `CLOUD_VPS_1` (1 GB / ~$3.51)
отвергнут. Пол: **Cherry Cloud VPS 4 GEN 2**. Апгрейд — Cherry scale-up,
потом Cloud VDS, потом rehost. Не вторая архитектура.

## Что дальше

1. Этот Atom 3: PR → exact-head CI → вы даёте merge-фразу → агент мержит.
   GitHub Merge не нажимайте. Точную фразу пришлю после номера PR и 40-hex.
2. Atom 4 (`muv-5`: вторая гипотеза / foundation freeze) — только после
   `main`, если план ещё актуален. Не commissioning-ready.
3. Paper-движок как отдельный systemd unit — не этот атом.

## Что не утверждается

Нет alpha, NetReturn, DONE, публичного admin, Postgres, Drive-as-primary.
