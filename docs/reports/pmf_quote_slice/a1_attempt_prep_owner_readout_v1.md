# PMF — attempt-prep: попытка ещё не начата

**Терминальное решение:** `QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED`
**Фраза владельца:** `OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, no execute, no provider`

Это **бумажный контракт попытки**, не кошелёк, не `/order`, не Touch, не Fillable, не execute, не alpha и не canonical DONE.

## Что остаётся истинным

- owner-fork terminal: `QUOTE_OWNER_FORK_MISSING_FACTS_NAMED`
- mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- notional: `10000000`
- утренняя котировка outAmount: `9010943976` в `2026-08-17T02:38:46Z` — это **не** quote попытки
- attempt: `NOT_ATTEMPTED` / `RESERVED_NOT_ISSUED`
- taker сейчас: `OMITTED_QUOTE_ONLY`
- execute: `FORBIDDEN` / `INELIGIBLE`
- provider_requests: `0`

## Что можно сделать вечером (этот атом это не делает)

- later call: `KEYED_JUPITER_V2_ORDER_WITH_TAKER_PUBKEY`
- taker later: `PUBLIC_KEY_ONLY` — только pubkey, не seed
- credential later: named `JUPITER_API_KEY`, здесь не читается
- `/execute` и `/build` запрещены
- байты транзакции не в git

## Неоплаченная следующая фраза

- `OK PMF-QUOTE-ATTEMPT: keyed /order with taker pubkey only, no /execute, no seed in git`

## Не делать

- `JUPITER_EXECUTE_OR_BUILD`
- `SEED_OR_PRIVATE_KEY_IN_GIT`
- `TRANSACTION_BYTES_IN_GIT`
- `FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE`
- `TAKER_OR_SIGNER_SUPPLIED` в этом пакете
- `H11_UNPARK_OR_SAMPLE_CAMPAIGN`
