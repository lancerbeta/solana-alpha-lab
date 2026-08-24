# EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1 — owner readout

## Verdict

`EARN_ONE_CONFIRMATORY_FRESH_OOS`

Одно authorized Jupiter Free-key окно завершено. Sign-only Kendall tau_b
`X = audit.topHoldersPercentage` (один decision-time search snapshot,
шкала 0–100, ABSENT не ноль) против quote-only H900 Y:

- `tau_b = -0.26984782209025315` (ожидали `< 0`)
- decision-time eligible: 22 (пол 18)
- rankable H900: 19 (пол 14)
- freeze: 24; X MISSING: 2 (не подставлялись нулём)
- provider requests: 46 / 60
- credential reads: 1
- execute / taker / wallet / signer / tx: 0
- retries / fallbacks: 0
- quartile / LOO / threshold / smoothing / second snapshot: не открывались
- `jupiter_top_holders_pool_exclusion = UNKNOWN`

Первый отрицательный знак **не альфа**. Strategy / Bot / Shadow / NetReturn
не открываются. Confirmatory OOS я **не** запускаю: тот же implementation,
новый production/orchestration code = 0, только по отдельной owner-фразе.

## Runtime receipt

`docs/evidence/early_holder_concentration_h900_falsifier/a1_runtime_receipt_v1.json`

SHA-256: `7a6f05aadb29ee277d0eaec9379885b5585f1fc369f9d5d959b993ef6982bcef`

Raw provider bodies остаются вне Git.

## Что дальше

Owner решает, давать ли confirmatory-фразу на **этот же** runner.
Не строить второй campaign module. Не открывать Strategy/Shadow.

Merge этого PR фиксирует scientific terminal на `main`.
Новая merge-фраза понадобится после exact-head CI.

## Non-claims

No alpha, no SHADOW, no NetReturn, no micro-live, no Discovery/A7, no
canonical DONE, no automatic confirmatory OOS.
