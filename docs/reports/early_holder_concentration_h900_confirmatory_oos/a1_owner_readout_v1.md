# EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1 — owner readout

## Verdict

`HOLDER_CONCENTRATION_MECHANISM_REPLICATED`

Одно authorized Jupiter Free-key confirmatory окно завершено на fresh
non-overlapping EARLY выборке. Тот же frozen mechanism
`X = audit.topHoldersPercentage` (один decision-time search snapshot,
шкала 0–100, ABSENT не ноль) против quote-only H900 Y:

- `tau_b = -0.16468280637257554` (ожидали `< 0`)
- decision-time eligible: 22 (пол 18)
- rankable H900: 18 (пол 14)
- freeze: 24; X MISSING: 2 (не подставлялись нулём)
- overlap с PR #190 holder cohort: 0
- overlap с EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1: 0
- provider requests: 46 / 60
- credential reads: 1
- execute / taker / wallet / signer / tx: 0
- retries / fallbacks: 0
- quartile / LOO / threshold / smoothing / second snapshot: не открывались
- `jupiter_top_holders_pool_exclusion = UNKNOWN`

Это **same-direction replication** на новой независимой выборке.
Это **не** alpha, не profitable strategy, не actionable threshold,
не NetReturn, не Shadow / Strategy / micro-live.

## Residual limits (не rescue)

Kendall считается только среди rankable quote-пар (n=18). Четыре eligible
имени выпали как `MARKET_EXECUTION_UNAVAILABLE` на H900 и не входят в tau_b.
X остаётся Jupiter `audit.topHoldersPercentage`; pool/curve exclusion
не установлен. Y — quote-only recovery, не fill.

Третий sample, threshold search и Strategy/Shadow **запрещены**.

## Runtime receipt

`docs/evidence/early_holder_concentration_h900_confirmatory_oos/a1_runtime_receipt_v1.json`

SHA-256: `9fd3408ff9e18ecda9fde0108c6d217fd4a3819738d0b4a0bb2129bcbaec895a`

Raw provider bodies остаются вне Git.

## Что дальше

`NEXT = DESIGN_ONLY_HOLDER_CONCENTRATION_ACTIONABILITY_ADJUDICATION`

Только если owner отдельно выберет эту DESIGN_ONLY фазу: можно ли
превратить replicated monotonic relation в одно frozen economically
meaningful entry/risk rule для нового fresh OOS. Правило здесь не
выбирается и не оптимизируется.

## Non-claims

No alpha, no SHADOW, no NetReturn, no micro-live, no Discovery/A7, no
canonical DONE, no third sample, no validated threshold.
