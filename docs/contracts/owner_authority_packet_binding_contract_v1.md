# Owner authority packet binding contract v1

`OWNER_AUTHORITY_PACKET_BINDING_V1` — versioned offline contract для одного будущего технического canary. Он не является wallet, transaction builder, order, route request или execution authority.

## Состояния

`DRAFT_OWNER_INPUT_REQUIRED` означает, что exact owner inputs отсутствуют. Их отсутствие не заменяется нулём, default или предположением.

`READY_FOR_OWNER_EXACT_APPROVAL_NOT_EXECUTION` означает, что synthetic форма полна и согласована с лимитом. Это всё ещё review-only: `canary_authority=false`, `task27_authority=false`, `execution_action=NONE`, numeric NetReturn запрещён.

## Обязательные owner inputs

`token`, `program`, `route`, `wallet_public_address`, `proposed_notional_usd_cents`, `maximum_separate_fees_usd_cents`, `quote_basis`, `expires_at`, `monitoring_reference`, `reconciliation_reference`, `stop_and_recovery_procedure`, `exact_owner_approval_phrase`.

Лимит `total_cash_at_risk_cap_usd_cents` строго равен `300`. Отдельный fee cap и estimated total cost не могут быть нулевыми или превышать этот лимит.

## Выход и recovery

Предполагаемый второй этап может иметь только форму `EXIT_LEG_SHAPE_VALIDATED_NOT_AUTHORIZED`. Он требует первого этапа `LANDED_SUCCESS`, reconciliation, здорового monitoring, совпадения inventory, allowlist и fee cap. `UNKNOWN`, любой mismatch либо отсутствие reconciliation блокируют выход и retry до отдельного future reconciliation.

## Непреложные границы

Контракт не предоставляет authority для provider, wallet, signer, transaction, simulation, send, cash, R3, strategy или TASK-27. Exact owner approval остаётся отдельной будущей material action.
