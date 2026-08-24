# EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1 — owner readout

## Verdict

`CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY`

Одно authorized Jupiter Free-key окно завершено. Sign-only Kendall tau_b
`X = ln(R1/R0)` против quote-only H900 Y отрицательный:

- `tau_b = -0.08035714285714286`
- decision-time eligible: 22 (пол 10)
- rankable H900: 20 (пол 8)
- 2 non-rankable: BUY `QUOTE_OBSERVED`, SELL H900 `MARKET_EXECUTION_UNAVAILABLE`, `Y=null`
- provider requests: 47 / 60
- credential reads: 1
- execute / taker / wallet / signer / tx: 0
- quartile / LOO / `tau_b_floor=0.20`: не открывались

Закрытая семья EARLY_STRUCTURAL_BACKING тестировала уровень. Этот candidate
тестировал temporal change и тоже не дал положительного знака.

Discovery / A7 / SHADOW / alpha / Window B / confirmatory OOS — нет.

## Runtime receipt

`docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_runtime_receipt_v1.json`

SHA-256: `a8c8df4a7c02a8e6cf4d2be2fe004f2cfbff170efcf5645064788ea20f12db63`

Raw provider bodies остаются вне Git.

## Что дальше

Не строить ничего вокруг этой гипотезы. Не прыгать к следующей идее.

Короткий Factory economics check (owner, не новый software atom):

следующая prospective temporal hypothesis выражается через уже появившийся
machinery без нового campaign module, или это реальный Factory gap?

Merge этого PR — только чтобы зафиксировать scientific terminal на `main`.
Новая merge-фраза понадобится после exact-head CI на новом head.

## Non-claims

No alpha, no SHADOW, no NetReturn, no micro-live, no Discovery/A7, no
canonical DONE.
