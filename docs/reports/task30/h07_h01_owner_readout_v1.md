# TASK-30 — H07/H01: что нужно дальше

## Решение

Нужен точный gate на получение данных (`CAPTURE_REQUIRED`).

Для H07/H01 пока нужен точный gate на недостающие данные; исследовательский trial не готов к запуску.

## Чего не хватает

- Непрерывная PIT history для liquidity-retention состояния.
- Settled execution truth для проверки route-aware outcome.

## Что из этого не следует

- Текущая price/transport feasibility не является research trial.
- Quote или plan не являются settlement.
- Missing/UNKNOWN не являются zero, no-trade, flat или settled.
- Провайдер не выбран, forward capture не начат.

## Единственный следующий шаг

`EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE`. Он потребует отдельного owner gate; этот readout ничего не запускает.
