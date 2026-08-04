# OWNER_AUTHORITY_PACKET_BINDING_V1

## Назначение

Подготовить один offline-пакет для будущего технического canary: `SOL -> одна точная memecoin -> SOL`, с немедленным выходом только после подтверждённого и reconciled первого этапа. Пакет превращает согласованный лимит риска в проверяемую форму для решения владельца; сам он ничего не исполняет.

## Решение владельца и consumer

Consumer — goal owner перед отдельной точной авторизацией будущего canary. Единственное решение, которое поддерживает этот артефакт: заполнить или не заполнять exact owner inputs. Даже заполненный пакет остаётся `READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION` и требует отдельной явной фразы владельца.

## Scope

- Лимит total cash at risk строго USD 3.00 (`300` cents).
- Требуются exact token, program, route, публичный адрес технического wallet, notional, лимит отдельных fees, quote basis, expiry, monitoring/reconciliation references, recovery procedure и approval phrase.
- `UNKNOWN`, отсутствие reconciliation, monitoring, inventory match, allowlist match или fee-cap блокируют planned exit и retry.
- Все fixtures synthetic; они не содержат реальных mint, wallet address, route, quote, signature или secret.

## Non-claims

Этот task не создаёт и не подключает wallet, signer, key, seed, transaction, signed bytes, provider/API/RPC/WSS path, simulation, send, reconciliation call, cash spend, R3 access, numeric NetReturn или TASK-27 authority.

## Definition of Done

Versioned contract/config/schema, deterministic synthetic matrix, offline evaluator, acceptance receipt, targeted tests и затем Catalog/Factory Fit closure. `canary_authority=false` и `task27_authority=false` во всех состояниях.
