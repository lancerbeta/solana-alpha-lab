# Factory remote operations — owner readout

Терминал Git-стороны: `FACTORY_REMOTE_OPERATIONS_GIT_READY`.
Живой VPS ещё не куплен и не должен быть куплен до одного пакета ниже.

Это не `FACTORY_V1_OPERATIONAL_READY`, не alpha и не Linux-админка для владельца.

## Что теперь правда

Factory можно оставить без IDE **после** одного внешнего пакета. Пока пакет не выполнен, live `FACTORY_REMOTE_OPERATIONS_PASS` честно не существует.

Уже доказано offline, без сети и без секретов:

- деплой пинится Git SHA; Workbench только `127.0.0.1` + SSH tunnel;
- процесс «просто жив» никогда не HEALTHY;
- sshd: ключи, не пароль, не root; nftables deny-all кроме 22; fail2ban;
- секреты без default в коде и без значений в Git;
- бэкап — content-addressed bundle на sink, который не лежит в том же parent, что live SQLite; isolated restore сходится по hash;
- Telegram-алерт: WHAT / WHY / SAFE STATE / ACTION, один раз на incident_key;
- doctor CLI отдаёт JSON агенту.

SQLite остаётся. Postgres не нужен. Google Drive 5TB — опциональная холодная копия, не DoD и не primary backup.

## Почему не VPS за 9 долларов

Cherry Servers по-прежнему принимает crypto. `CLOUD_VPS_1` (1 GB / ~$3.51) отвергнут: через несколько циклов paper+DuckDB+parquet он станет тесным.

Выбран пол: **Cherry Cloud VPS 4 GEN 2** — 4 vCPU / 4 GB (scale до 6 GB) / 80 GB SSD (до 100 GB) / Ubuntu 24.04 / EU / ~$10.53 в месяц. Апгрейд — штатный Cherry scale-up, потом Cloud VDS, потом уже существующий rehost proof. Не вторая архитектура.

## Один пакет владельца

Я не покупаю VPS, не читаю токены и не логинюсь в панель. Нужны только действия, которые могу сделать только вы:

1. Аккаунт Cherry Servers, оплата crypto, инстанс как в конфиге, Ubuntu 24.04, SSH ключ (не пароль), без публичного 8765.
2. Telegram bot + chat id. Значения только в `/etc/solana-alpha-lab/secrets.env` на хосте, никогда в Git и в чат.
3. Каталог независимого бэкапа (отдельный volume/path). Drive — потом, если захотите холодную копию.

После этого одной фразой верните агенту право на live apply. Точные строки — в следующем сообщении чата, не здесь смешанные с прозой.

## Что дальше

`OWNER_INFRASTRUCTURE_PACKET`, затем live fault injection на реальном хосте. Atom 4 (вторая гипотеза / foundation freeze) не стартует, пока remote ops не hosted.
