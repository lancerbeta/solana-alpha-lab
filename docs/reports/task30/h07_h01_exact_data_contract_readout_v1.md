# TASK-30 — H07/H01: какие данные нужны дальше

## Решение

Можно подготовить только частичный PIT-capture contract.
Он не является trial и не открывает внешние действия.

## Что такой capture может дать

- PIT market: наблюдаемую историю цены и liquidity с явными gaps.
- Route feasibility: доступность route для named notionals.

## Что он не доказывает

- Quote или route feasibility не доказывает settlement.
- Owned execution truth остаётся отдельным future-canary blocker.
- Missing/UNKNOWN не становятся нулём, no-trade или settled.

## Безопасность будущего capture

Decision-critical невосстановимые raw требуют backup/restore route или explicit waiver до owner gate.

## Единственный следующий шаг

`OWNER_GATE_FOR_NAMED_PARTIAL_PIT_OR_ROUTE_CAPTURE`.
