# TASK-26C owned execution canary readiness contract v1

## 1. Purpose

TASK-26B established that historical/cache-first evidence cannot prove the owner
attempt denominator, retry intent, inventory or settlement. TASK-26C freezes the
minimum pre-authority safety contract for one future technical canary without
creating an executable transaction path.

## 2. Threat model

The readiness package must block or retain an explicit recovery state for:

1. secret or key compromise;
2. wrong program or route;
3. stale quote or blockhash;
4. duplicate send;
5. timeout or `UNKNOWN` transaction;
6. retry before reconciliation;
7. unexpected token or SOL delta;
8. residual inventory;
9. monitoring loss;
10. provider divergence; and
11. fee or cash-cap breach.

No threat is converted into a safe default, zero fee, flat inventory or settled
cashflow merely because a record is absent.

## 3. Authority model

| Role | May do in this task | Always prohibited or owner-gated |
|---|---|---|
| Research process | Evaluate synthetic readiness records and write offline receipts | Wallet, build, sign, send, provider execution, cash action |
| Transaction builder | Future isolated component only; validate an approved intent shape | Key access, signing, sending, route expansion, authority assignment |
| Isolated signer | Future owner-controlled boundary only | Activation, key creation, key export, signing in TASK-26C |
| Goal owner | May later give one exact, bounded approval | Approval is never inferred from readiness, code, CI or this contract |

## 4. Future witness contract

Every future owned attempt must retain: `stable_attempt_id`, `retry_chain_id`,
quote/build context, `submitted_at`, `terminal_at`, `terminal_state`, transaction
signature reference, processed-on-chain state, token and SOL deltas, network,
relay/tip and ATA/rent/separate fees, inventory before/after, settlement accounting
basis, reconciliation reference, source/raw hashes and an `UNKNOWN` recovery path.

The fields are a future evidence contract. They do not assert that an attempt,
signature, fill, settlement or NetReturn exists now.

## 5. Reconciliation-before-retry

`UNKNOWN_REQUIRES_RECONCILIATION`, dropped/expired, landed-failed, landed-success,
unexpected delta, residual inventory, fee breach, route mismatch, provider
disagreement or monitoring loss blocks a new action. A retry becomes eligible only
after a bound reconciliation record establishes the prior attempt's terminal state,
fee treatment and inventory basis. `UNKNOWN` always remains non-retryable until
that reconciliation succeeds.

## 6. Allowlist, health and owner packet

Program and route allowlists start empty and deny by default. A future owner packet
must bind one exact action, token, program, route, proposed notional, total
cash-at-risk cap, maximum separately charged fees, expected inventory before/after,
stop/recovery procedure and the approval phrase below. Every numeric or identifying
input is `OWNER_INPUT_REQUIRED` until a future exact authority gate.

Approval phrase template, not an approval:

`I APPROVE ONE EXACT TECHNICAL CANARY {canary_id}; token={token}; program={program}; route={route}; notional={notional}; total_cash_at_risk_cap={cap}; max_separate_fees={fees}. This approval expires on {expires_at} and does not authorize strategy trading, retries before reconciliation, or any different route.`

## 7. Decision enum and non-claims

Exactly one task result is emitted:

- `READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS`;
- `REDESIGN_CANARY`;
- `PAUSE`; or
- `CLOSE_CANARY_ROUTE`.

`READY_FOR_OWNER_CANARY_AUTHORITY_WITH_LIMITATIONS` has `canary_authority=false`.
It does not authorize provider calls, wallet/signer activation, transaction build,
sign, simulation or send, cash spend, R3, numeric modeled/observed NetReturn,
strategy promotion or TASK-27.
