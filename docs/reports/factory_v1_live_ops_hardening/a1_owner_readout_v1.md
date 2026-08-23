# A5 — Live ops hardening commissioning

Дата: 2026-08-23
Контракт: `FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1`

## Решение

Существующий host `factory-remote-ops` доказал exact-SHA deploy → rollback →
forward restore, clean empty-root rehost, разделённые health-часы
(worker / progress / market_data / provider), diagnostic fault matrix с
Telegram delivery, incident lifecycle с recurrence, и positive financial
authority = DENIED.

## Receipt

- terminal: `FACTORY_V1_LIVE_OPS_HARDENING_PASS`
- deploy SHA final: `07b628c5ee2a6141e76753e9c859859b3bbecc6d`
- start SHA: `b7f10c77007bd2897d4d044564e93b0f3172ef08`
- doctor after cleanup: `RUNTIME_PROVED_BACKUP_INDEPENDENT`
- stale / stall / provider-failure alerts: PASS
- incident first/dedup/recovery/recurrence: PASS
- shadow financial authority: DENIED
- provider market calls: 0; wallet/signer/tx: 0; cash: 0

## Граница

Семь A5 readiness predicates теперь читают A5 acceptance. Остаётся один
governance gap: `ENTRY_GATE_RESOLVES_READINESS_CONTRACT` → следующий атом A6.

Не утверждает READY, Foundation Freeze, alpha, scientific SHADOW, REAL_FILL.

## Следующий шаг

`FACTORY_V1_READINESS_RECERTIFICATION_AND_FREEZE_V1` (A6).
