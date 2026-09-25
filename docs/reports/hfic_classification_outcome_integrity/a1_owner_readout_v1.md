# Честный итог классификации

Кандидат packet 1.4 больше не получает `PASS_FAST_LANE_READY`, если обязательный признак не `PIT_READY` или осталось unresolved requirement. Это верно для каждого маршрута, который отображается в `PASS_FAST_LANE_READY`, включая `PANEL_REUSE_READY` и `ATTACHED_TO_ACTIVE_SCHEDULE`.

Отказ гейта сохраняется как `KILL_UNBOUND_EVIDENCE`, это не сбой и не застрявшая сессия. Если Критик заявил финальный `PASS_*`, машина может только понизить его до этого KILL. В чтении сессии видны маршрут и причина, например `route=FAST_LANE_READY` и `reasons=REQUIRED_BINDING_NOT_PIT_READY:FEAT-QUOTE-AVAILABILITY`. После экрана запасного кандидата строка разделяет `primary_terminal` и `final_terminal` и не смешивает причину второго экрана с отказом первого.

Репетиция на копиях реального RDP: **GO**. Честный `PIT_READY` завершился `PASS_FAST_LANE_READY`. `FORWARD_ONLY` на `FAST_LANE_READY` сохранился как `KILL_UNBOUND_EVIDENCE`, затем запасной `HISTORICAL_RECONSTRUCTIBLE` тоже закрылся `KILL` (`critic_screen_count=2`). Observation-маршрут на копии дал `SCHEDULE_ACTIVATION_REQUIRED` → `OWNER_DECISION_REQUIRED`, без ложного PASS. Реальный RDP не изменился.

Это не alpha и не запуск эксперимента. `prove-runtime` на честном PASS вернул `PROVENANCE_CORRECTION_CORRUPT` — это атом 2, здесь не чинилось. Первый реальный `/hypothesis-forge` — только после merge и отдельного OK.
