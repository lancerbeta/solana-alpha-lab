# SEASONED_30M_H900_BASE_RATE_PROBE_V1 — owner readout

## Verdict

`SEASONED_30M_SURFACE_NO_POSITIVE_MASS`

Одно authorized Jupiter Free-key окно на ~30m seasoned surface закрыто.
Положительной executable H900 массы нет. Это **не** доказательство, что
любая 30–120m seasoned population невозможна. Это закрывает **этот**
~30m probe как immediate escape. Positive-selector search автоматически
не стартую. 45m/60m не открываю.

## Numbers (one window)

- freeze: 24
- decision-time eligible: 19 (пол 18)
- rankable H900: 18 (пол 14)
- `positive_executable_count`: 0
- `median_Y`: `-0.0272814` (среди rankable; diagnostic, hurdle не вычитался)
- near historical friction floor: 14 / 18
- MEU: 1 (без numeric Y, не success)
- provider requests: 40 / 60
- credential reads: 1
- execute / taker / wallet / signer / tx: 0
- retries / fallbacks: 0
- population: `SEASONED_PUMPFUN_30M_PROBE_V1` (не `ICP-EARLY-PUMPFUN-V1`)
- Factory runner unchanged

Допустимое сравнение с 5–15m development surface: positive executable
base-rate снова 0. Нельзя говорить, что «ожидание до 30m улучшает Y».

## Runtime receipt

`docs/evidence/seasoned_30m_h900_base_rate_probe/a1_runtime_receipt_v1.json`

SHA-256: `0dbf58b5c2c061b50bcc850cc31dd42c3b69bfbf5d5d157894f79ef96e4d1087`

Raw provider bodies остаются вне Git (`local/`, A4).

## Что дальше

`NEXT = DESIGN_ONLY_REFRAME`

Owner выбирает, есть ли другой вопрос (другая surface, другой estimand).
Не строить selector. Не комбинировать с `HOLDER_CONCENTRATION_MECHANISM_REPLICATED`.
Не второй sample автоматически.

## Non-claims

No alpha, no NetReturn, no causal wait-treatment, no Strategy/Bot/Shadow,
no Discovery/A7, no canonical DONE beyond this atom's typed terminal.
