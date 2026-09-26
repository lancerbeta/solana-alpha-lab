# Часы и одно тело на один id

Сигнал принимается только с явными часами `as_of`. Если `decision_at` позже `as_of` больше чем на 2 секунды, ответ `SIGNAL_DECISION_FROM_FUTURE`. Без `as_of` — `SIGNAL_AS_OF_REQUIRED`. Прогон, который раньше молча подставлял часы из `decision_at`, теперь падает явно.

Один `signal_decision_id` — одно каноническое тело. Другой mint или `NO_ENTER` под id уже открытой позиции дают `SIGNAL_DECISION_IDEMPOTENCY_MISMATCH`. Повтор того же тела остаётся идемпотентным. Старые строки с пустым fingerprint не сравнивают тело ENTER. `canonical_spec_sha256` сортирует ключи; порядок элементов в `evidence_refs` входит в тело: другая перестановка — другое решение.

`start_bot` хранит `strategy_spec_sha256`. Пустой хеш на старом боте дописывается. Другой хеш при той же версии — `STRATEGY_SPEC_DRIFT`. Первый тик heartbeat (`run_shadow_tick`, v1.0) дописывает хеш; следующая правка файла стратегии без смены версии останавливает тик. Это задуманный fail-closed.

ExitDecision с другой `strategy_version`, чем у позиции, — `EXIT_POSITION_VERSION_MISMATCH`. V2 больше не закрывает V1. Причина входа остаётся в `reason_code`, причина выхода пишется в `exit_reason_code`. Событие `EXIT_DECISION_ACCEPTED` видно в трассе на стадии `POSITION`. Время входа в трассе не затирается: у выхода поле `exit_decision_at`.

Часы добавлены в вызовы, которые их не передавали: `tests/test_factory_strategy_execution_boundary_v1.py`, `tests/test_owner_lifecycle_projection_spine_v1.py`, `tests/test_paper_shadow_accounting_and_control_v1.py` (теневой вход). Дымовой скрипт уже передавал `as_of`. Одно старое ожидание сменило код, не ослабло: смена `activation_epoch_id` у того же id меняет тело, поэтому `test_enter_rejects_epoch_mismatch_on_existing_signal` ждёт `SIGNAL_DECISION_IDEMPOTENCY_MISMATCH`.

Не alpha. Живая торговля не включалась. Атомы A4–A6 не начаты.
