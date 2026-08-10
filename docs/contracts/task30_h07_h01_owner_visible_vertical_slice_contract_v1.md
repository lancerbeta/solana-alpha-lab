# TASK-30 H07/H01 owner-visible vertical slice contract v1

## Контракт

`task30_h07_h01_owner_visible_vertical_slice_v1.yaml` связывает текущий
offline-вывод с неизменяемой группой TASK-28
`RC001-H07-H01-LIQUIDITY-RETENTION` и с тремя prior receipts: TASK-27 route
close, TASK-26B execution witness и TASK-30 A6 forward-capture decision.

Pure evaluator обязан fail-closed проверять:

- идентичность group ID, definition hash и ordered blocker states;
- `MISSING_UNKNOWN` не превращён в zero/no-trade и `UNSUPPORTED` не превращён
  в settlement;
- trial admission, provider selection, background collection и authority не
  появились неявно;
- каждый authority и side-effect counter равен нулю;
- current decision остаётся `CAPTURE_REQUIRED` и открывает только
  `EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE`.

Результат содержит decision, ordered blockers, next boundary, краткое
объяснение и non-claims. Renderer детерминирован: у него нет часов, сети,
записи на диск или доступа к provider/credential.

## Владелец

Владелец читает готовый Markdown либо запускает read-only CLI. Этот contract
не предоставляет authority на новый внешний запрос: если capture будет
оправдан, он получит отдельный exact owner gate.
