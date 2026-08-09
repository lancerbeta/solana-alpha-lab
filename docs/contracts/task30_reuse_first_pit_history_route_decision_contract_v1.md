# TASK-30 reuse-first PIT history route decision contract v1

## Consumer and decision

This offline record gives a future named provider-entry gate one narrow answer:
whether the retained T30-A0 response or already observed alternatives can be
reused as continuous, point-in-time 15-minute history for the frozen target
window. The consumer is `FUTURE_NAMED_PROVIDER_ENTRY_GATE`.

The only permitted decision is `T30_A0_REUSE_CLOSED_NO_PROVIDER_PILOT`.
It closes reuse of one retained response for one target window. It does not
claim that GeckoTerminal, Solana Tracker, Birdeye, or an unexamined provider is
generally unusable.

## Frozen route facts

`GECKO_T30_A0` binds the retained raw digest
`cce29d4e175bc81a474c699e3bb465daf8cb864f3cb195a9812bd0d3c0ca4163`.
Its requested interval is `[1786100400, 1786186800)`, its first observed
timestamp is `1786101300`, and its newest observed timestamp is `1786186800`.
Current official Pool OHLCV documentation says that a candle timestamp marks
the start of its interval and that `before_timestamp` returns data before that
timestamp. The retained newest timestamp equalling that request boundary is an
`OBSERVED_CONFLICT`, not an interpretation to repair by shifting or filling.
The same documentation describes empty-interval output as prior-close OHLC
with zero volume; this is not a verified trade or a new price observation.

`SOLANA_TRACKER_PAIR` remains `OBSERVED_INSUFFICIENT_33_OF_96`. Its official
pair route documents `15m` and an exact token-plus-pool input, but the retained
named-pool sample remains incomplete.

`BIRDEYE_V3_PAIR` remains `CANDIDATE_NOT_READY`. Its official V3 material
documents pair OHLCV and a padding option, but the present record has no exact
pair identity, REST-15m enum proof, local key-presence attestation, or owner
call authority.

## Authority and non-claims

This contract permits local tracked documentation, synthetic fixtures, pure
evaluation, tests, Catalog maintenance, and ordinary Git delivery only. It
permits zero provider/API/RPC/WSS calls, credential access, raw-data writes,
R2/R3 access, dependency changes, wallet/signer/transaction actions, cash,
trial opening, holdout consumption, or Project Sources changes.

It makes no continuous-panel, PIT-admissibility, explicit-no-trade, alpha,
strategy, execution, fill, settlement, PnL, or numeric NetReturn claim.
`NEW_NAMED_PROVIDER_CANDIDATE_REQUIRES_ENTRY_GATE` grants no authority; a
future task needs its own consumer, exact provider route, budget, retention,
falsifier, and owner approval.

## Acceptance

The evaluator must reject a removed Gecko boundary conflict, changed 33-of-96
sample, promoted Birdeye identity, credential-like key, non-zero authority,
provider-call boundary, decision change, claim promotion, or non-`NO_CHANGE`
Source disposition. Historical TASK-27, T30-A0, T30-A1, and T30-A3 artifacts
remain untouched.
