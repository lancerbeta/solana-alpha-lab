# FORGE_COMPOSITE_FEATURE_RECIPES_V1 — candidate readout

Обычный Forge принимает raw holder `delta` и `return_ratio` в смешанной query.
Preview показывает вычислимость всех объявленных features на полном decision
population до выбора 24 примеров. Target values в preview не загружаются.
Текущий смысл и синтаксис принадлежат
`docs/contracts/forge_composite_feature_recipes_v1.md`
(`DOC-FORGE-COMPOSITE-FEATURE-RECIPES-001`).

Base: `27366b752cd0fae9683dd50373ea8ff8da5a6f6d`, включая lifecycle #373.
Task: `docs/tasks/FORGE_COMPOSITE_FEATURE_RECIPES_V1.md`.
Native acceptance выполнена на implementation commit
`bf59202d4ce4e4af556460cba9d5261e79984394`.
Blueprint V4 — design context; authority — Executor Brief V4, SHA256
`d3abed94024646c2256199d954e28a1971c7e26c5eeb346890810493f53c92fc`.

| Slice | Проверяемый результат |
|---|---|
| A | Raw arithmetic; положительный denominator для return; отсутствующие, late, conflict, bool/nonfinite дают unavailable. Bound `start < end <= decision`; лишние новые параметры отвергаются. Старые temporal tests проходят. |
| B | 48 BASE_X; universe 40 PASS / 4 FAIL / 4 UNKNOWN; 36 decision eligible. Joint calculable: delta 24, return_ratio 20. Это полные counts для четырёх cohorts, отдельно от 24 examples. Zero target-value loads; cold preview без values и новой reservation. |
| C | Fresh direct decision-cell tautology/impossible query отвергается до values/reservation. Redundant conjunct в meaningful compound даёт warning; исходный hash сохраняется. Saved result, correction и pending recovery используют прежние owners. |
| D | Public MAIN → persisted grounded evidence → persist-draft → resume → freeze → native isolated Critic → required finalize → `forge-run --persist`. Ни production bindings, ни terminal state не дописаны fixture вручную. |
| E | Reply-loss recovery: evaluator calls 0. Cold owner readback: values/evaluator 0, inventory unchanged, operation COMPLETED. Registered numerical replay: evaluator 1, точное равенство сохранённому summary. Следующий legacy cycle завершён SEARCH_EXHAUSTED_CURRENT_EVIDENCE. |
| F | Агент без истории чата получил actual pre-search packet и текущую инструкцию; после исправления отсутствовавшего полного JSON example составил валидные SIMPLE и COMPOUND_FIRST. EWM и alpha не придуманы. Русские semantic gold queries ведут к действующим owners. |

Native Critic вернул `KILL_UNBOUND_EVIDENCE`; существующий owner-final —
`NON_SCIENTIFIC_STOP`. Это корректное завершение технического synthetic screen.
Classifier на таком KILL не требуется. Market evidence, prior scope и strategy
availability остаются UNKNOWN; RAW_HOLDER_DYNAMIC_EXPLORATORY не превращён в
фиктивный FEAT. Нативный transport и engineering path прошли, научного PASS нет.
Прямые DocumentRunner/classification и saved-result revision consumers проходят
на committed implementation; новые формулы обслуживает существующий registered
`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`.

Изолированный code review выявил и закрыл target-clock order dependence,
потерю operation binding при одинаковом preview и пропуск пустого admitted
cohort. Сравнение target copies теперь использует фактический target selector.
Target conflict не удаляет pre-decision seat и не меняет support denominator.
Завершённые ordinary KILL sessions находятся cold reader вместо возврата к
старому draft; их прежний terminal не меняется и REUSED_VALID не добавляется.

Совместимость: old point/PRICE-only recipes, scientific hashes и числа остаются
заморожены, включая их прежнюю обработку conflicting future deliveries.
Новая RAW query использует dependency-prefix integrity в общем membership owner.
Это ограничение сохранённой совместимости явно покрыто regression witness;
не заявляется новое поведение старого frozen evaluator.

Evidence: `docs/evidence/forge_composite_feature_recipes_v1/`:

- `a1_vertical_acceptance_v1.json` — key numbers, output hashes и reproduce commands;
- `a1_native_critic_result_v1.json` — полный неизменённый native verdict;
- `a1_native_agent_queries_v1.json` — обе авторские query;
- `a1_native_isolation_v1.json` — реальные inputs/read sets и границы изоляции;
- delivery completion/review/Factory Fit — точные candidate bindings через Harness.

Synthetic machine dumps остаются в игнорируемом `local/`; обязательные key
numbers, независимые решения и bindings сохранены в Git. Model diversity
UNPROVEN; cryptographic reviewer identity не заявляется. Полный local gate до
PR не запускается; full-suite owner — exact-head CI по текущему Harness.

Real holder MAIN/adaptive, live ResearchStore/profile/operation writes,
C5/holdout, provider/deploy/settings, budget/estimand expansion: 0.
Результат не подтверждает alpha, net return, live runtime health или PIT_READY.

Rollback baseline содержит #373. До production use возможен отдельно
разрешённый ordinary revert; после появления новых records сохранять readers
и делать forward-fix. Live migration и rollback этим atom не выполнялись.

Product Horizon NOW: закончить этот reusable RAW capability atom для обычного
Forge. WATCH: отдельное owner решение о конкретном real contrast после оценки
support/precision; стоимость и риск — новые scientific exposures. Только новая
явная science authority активирует этот шаг. Tool radar NOW: NONE; существующие
owners и CLI достаточны. Следующий engineering NOW или EWM не предлагаются.

Delivery stop: exact-head CI PASS и machine `ready_for_owner_phrase=true`.
Merge выполняется только после отдельной точной owner phrase, затем обязательный
post-merge readback. Этот readout сам не утверждает CI, merge или canonical DONE.
