# PMF — stay-overlay: quote-only KEEP screening exhausted

**Терминальное решение:** `QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED`
**Фраза владельца:** `OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced`

Это **stay-overlay поверх owner-fork и confirmatory family-close**, не Touch, не Fillable, не новый 6+6, не execute, не alpha и не canonical DONE.

## Что остаётся истинным

- owner-fork terminal: `QUOTE_OWNER_FORK_MISSING_FACTS_NAMED`
- overlay terminal: `QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED`
- confirmatory scientific terminal: `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`
- quote-only KEEP screening: `EXHAUSTED`
- fillable-named KEEP on quote-only: `FORBIDDEN`
- quoted-path 6+6: `NOT_AUTHORIZED`
- execute: `FORBIDDEN` / `INELIGIBLE` в этом пакете
- provider_requests: `0`
- factory_v1_operational_ready: `False`
- atom_2: `False`

## Слои, которые quote по-прежнему не доказывает

- Touch: `NOT_EVIDENCED` (`QUOTE_IS_NOT_TOUCH`). Quote не есть Touch.
- Fillable: `NOT_EVIDENCED` (`NO_TAKER_NO_TRANSACTION_NO_SIMULATE`). KEEP с именем fillable над `/order` запрещён.
- fees: `NOT_COMPUTABLE` (`SANITIZED_RECEIPT_HAS_NO_FEE_COMPONENTS`). отсутствие не есть ноль.

## Дизайн-зонд (не наука, не новый KEEP)

На confirmatory C1 path-risk как KEEP не имеет контраста, а hop_count==1 не даёт мощности на свежий 6+6.

- science: `False`
- y_path_risk true n: `0`
- BUY_H900 hop_count==1 RECENT/TRADED: `6` / `3`
- why not quoted-path KEEP: `RECENT_NO_CONTRAST_TRADED_BELOW_FLOOR`

## Оставшиеся неоплаченные фразы (этот атом их не исполняет)

- `OK PMF-QUOTE-TOUCH-FACT: authorize a non-execute Touch observation`
- `OK PMF-QUOTE-FEE-FACT: authorize a quote-layer fee-field observation, no execute`

## Jupiter / execute

Нет. Stay-overlay не стартует Free-key 6+6. `/execute` и `/build` запрещены.

## Не делать

- `FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY`
- `QUOTE_ONLY_KEEP_SCREENING_REOPENED`
- `QUOTED_PATH_QUALITY_6_PLUS_6_WITHOUT_NEW_PHRASE`
- `TOUCH_FACT_AUTO_STARTED` / `FEE_FACT_AUTO_STARTED`
- `PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE`
- `ATOM_2_FROM_RETENTION`
- `FACTORY_V1_OPERATIONAL_READY_CLAIM`
- `JUPITER_EXECUTE_OR_BUILD`
