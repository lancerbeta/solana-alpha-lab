# Factory v1 kernel — локальный вертикальный срез

## Вердикт

`FACTORY_KERNEL_GOLDEN_REPLAY_PASS`

Существующий admissible friction cycle проходит через generic `ExperimentSpec` /
`ExperimentRunner` без нового provider-вызова и без hypothesis-specific core
pipeline. Это не `FACTORY_V1_OPERATIONAL_READY`, не alpha и не MOVE 3.

## Что видно владельцу

Локальный Workbench (stdlib HTTP, только localhost) показывает:

- hypothesis `HYP-QUOTE-NATIVE-FRICTION-H900-V1` из ExperimentSpec;
  production-реестры hypothesis/cycle остаются пустыми до commissioning freeze
- question / estimand / population
- available vs missing evidence
- experiment status
- blocker
- terminal `DIRECTIONAL_HINT_NOT_CONFIRMATION`
- next safe action: оставить hint без MOVE 3

SQLite хранит только job state. Git/Catalog/receipts остаются научной истиной.

## UI gate

NiceGUI и FastAPI+htmx отложены: нет права на package adoption.
Streamlit отвергнут для этого среза из‑за риска второго truth store.
Выбран `BUILD` тонкого stdlib Workbench.

## Ограничения

Нет VPS, нет monitoring product, нет нового market byte, нет MOVE 3.
ATOM 2 commissioning hypothesis замораживается позже по live Git.
