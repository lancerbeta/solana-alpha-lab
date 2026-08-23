# A4 — PIT data-truth canonicalization

Дата: 2026-08-23
Контракт: `FACTORY_V1_PIT_DATA_TRUTH_CANONICALIZATION_V1`

## Решение

Принятые свежие prospective-наблюдения Atom 1 можно переиспользовать как
ограниченную каноническую PIT-capability для Factory без нового capture.

Это не новая научная оценка и не новый провайдерский маршрут. Проектор
повторно проверяет уже принятые bytes, lineage, decision-time границу,
missingness и формулу `liquidity / mcap`.

## Receipt

- 24 кандидатных наблюдения;
- 19 `PIT_READY`;
- 5 типизированных `MISSING`;
- `FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO`;
- scope: `MINT_DECISION_SNAPSHOT`;
- `UPDATED_TIMESTAMP_IN_FUTURE` не допускается;
- FDV не используется как substitute для market cap;
- исторический источник и acquisition timing сохранены как lineage, raw batch
  остаётся вне Git;
- текущий A4 прогон: `network_calls=0`, `provider_calls=0`,
  `credential_reads=0`, `cash_spend_usd_cents=0`;
- Factory runner не менялся: SHA `d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f`.

Причины пяти отвергнутых строк: две `FDV_OR_SUBSTITUTE_REJECTED`, две
`UPDATED_TIMESTAMP_IN_FUTURE`, одна `LIQUIDITY_BELOW_ICP_MIN`.

## Граница результата

Изменение закрывает canonicalization gap в data-truth блоке и делает capability
доступной через common market feature surface. Оно не утверждает:

- SHADOW, VPS, micro-live или execution;
- alpha, PnL, NetReturn или cashflow;
- Factory operational READY или Foundation Freeze;
- научное превосходство feature family;
- замену исторического Atom 1 evidence или старого inverse feature ID.

Следующий атом по плану — A5 live-ops hardening commissioning. Он требует
отдельного exact task contract и отдельной проверки boundary перед любым
live-host действием.

## Повторная проверка

```text
uv run --locked --managed-python python -B scripts/run_factory_v1_pit_data_truth_canonicalization.py --root . --write-evidence
uv run --locked --managed-python python -B -m unittest discover -s tests -p "test_factory_v1_pit_data_truth_canonicalization.py" -v
```
