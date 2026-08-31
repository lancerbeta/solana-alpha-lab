# PathRisk fresh activation identity — owner readout

Pre-merge: `PATHRISK_FRESH_ACTIVATION_IDENTITY_PASS_READY_FOR_MERGE_GATE`.

## DONE

После pre-evidence operational failure у `ACT-PATHRISK-LIVE-001` новый prospective window получает **immutable identity** `ACT-PATHRISK-LIVE-002` из policy contract. Это не resume и не rewrite старого окна. Runtime dir, journal, schedule, binding и call accounting — отдельные.

Provider calls в этом PR = 0. Ключ не читали. Live-run не исполняли.

## BLOCKED

В этом PR запрещены: Jupiter, `--real-provider`, live-run, reopen `ACT-PATHRISK-LIVE-001`. GitHub Merge не нажимать.

## NEXT

Только merge gate этого PR. Replacement window — не сейчас.

Точная future phrase для ACT-002 (не исполнять в этом PR):

```
OK PATHRISK_FRESH_ACTIVATION_IDENTITY_LIVE_V1: exactly one replacement prospective PathRisk window ACT-PATHRISK-LIVE-002; predecessor ACT-PATHRISK-LIVE-001 remains immutable; replacement_reason PRE_EVIDENCE_OPERATIONAL_FAILURE; not a resume of ACT-PATHRISK-LIVE-001; Jupiter Free-key; JUPITER_API_KEY process env only; exactly one /recent; exactly one bulk /tokens/v2/search; quote-only /swap/v2/order; no recurring /recent; x-api-key header only; no .env / secret leakage; no taker, /build, /execute, wallet, signer, transaction; no paid plan / second provider; no retry / fallback; cash cap $0; call cap 26; ICP-EARLY-PUMPFUN-V1; first 4 fresh unconsumed eligible mints or CALIBRATION_ELIGIBLE_BELOW_FLOOR with quote_calls=0; notionals 10000000 and 1000000 lamports; T0 BUY + T0 reverse + H900 dependent SELL of the same T0 BUY token amount; no third notional; Factory runner unchanged; Hypothesis Forge, Paper, Strategy, Shadow, alpha and NetReturn forbidden inside the live window.
```

Старая calibration phrase для ACT-001 **consumed** и даёт `OWNER_PHRASE_CONSUMED` / mismatch.

```
Do not authorize ACT-PATHRISK-LIVE-002 in this PR. Do not click GitHub Merge.
```
