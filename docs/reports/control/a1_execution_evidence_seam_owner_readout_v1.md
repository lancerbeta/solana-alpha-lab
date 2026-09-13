# EXECUTION_EVIDENCE_SEAM_V1 — owner readout

## Что сделано

Закрыт шов «научный PROMOTE → StrategyVersion»: научное продвижение,
принятое для режима исполнения A (например, котируемая исполняемость при
размере $10), больше не может материализовать StrategyVersion с существенно
иным режимом B ($100, другая fee-гипотеза). Котировки никогда не считаются
филлами.

## Новые машины-контракты

- `ExecutionEvidenceBindingV1` (`smial.execution-evidence-binding` v1.0):
  идентичность эксперимента (`experiment_id` + `experiment_spec_sha256` +
  `population_ref`), режимы по размерам с замыканием знаменателя
  (`two_way_n + entry_only_n + no_entry_n + unknown_n = population_n`),
  научная fee-гипотеза (`strategy_fee_bps_assumption`) и происхождение
  издержек (`cost_evidence_refs` с хэшами записей).
- `promotion_handoff_manifest` v1.1: неизменяемая ссылка на binding
  (`execution_evidence_binding_id` + `..._sha256`). Исторические v1.0
  манифесты валидируются как раньше и не переписываются.
- Новая научная обязанность `EXECUTION_REGIME_BINDING`: без валидного
  binding новый PROMOTE заблокирован fail-closed.

## Блокеры материализации (владелец видит причины)

- `EXECUTION_EVIDENCE_BINDING_GAP` — нет замороженной привязки режима.
- `EXECUTION_REGIME_MISMATCH` — привязка расходится с экспериментом/популяцией.
- `NOTIONAL_EVIDENCE_MISMATCH` — размер стратегии не подтверждён наукой.
- `COST_ASSUMPTION_BINDING_GAP` — в науке нет явной fee-гипотезы для режима.
- `COST_EVIDENCE_MISMATCH` — fee-гипотеза стратегии ≠ научная.

## Проверка

- Тесты T1–T20 + handoff + decision: 50/50 OK локально.
- Расширенный радиус (catalog, semantic operability, baseline): 224/224 OK.
- CI PR #301: 7/7 SUCCESS на head `0c9c588599a2ae8528a339e4b0256c6b0ddbc0a4`.
- `strategy_version_v1_1.schema.json` байт-в-байт не изменён (тест).

## Не-заявления

- Не канонический DONE, не продуктовая приёмка, не alpha.
- Котируемость ≠ исполнение (quotes are not fills).
- Провайдеры/сеть/кошелёк/транзакции: 0 вызовов, 0 операций, $0.

## Остатки

- Ссылка владельца `corrected handoff id 92147` не разрешима в репозитории;
  источником контракта является дословная inline-авторизация
  (`docs/tasks/EXECUTION_EVIDENCE_SEAM_V1.md`).
- Восстановление: обычный revert merge-коммита; исторические решения не
  затронуты.
