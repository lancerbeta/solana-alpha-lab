# FORGE_COMPOSITE_FEATURE_RECIPES_V1 — candidate readout

Обычный Forge принимает raw holder `delta` и `return_ratio` в смешанной query.
Для raw-holder composite с holder delta/return_ratio preview показывает
вычислимость всех объявленных features на полном decision
population до выбора 24 примеров. Target values в preview не загружаются.
Текущий смысл и синтаксис принадлежат
`docs/contracts/forge_composite_feature_recipes_v1.md`
(`DOC-FORGE-COMPOSITE-FEATURE-RECIPES-001`).

Base: `27366b752cd0fae9683dd50373ea8ff8da5a6f6d`, включая lifecycle #373.
Task: `docs/tasks/FORGE_COMPOSITE_FEATURE_RECIPES_V1.md`.
Native acceptance выполнена на implementation commit
`86d0351cbdd38649a5efa01b7f6f9314aebef11f` после owner P1 repair request и clock-copy исправления.
Blueprint V4 — design context; authority — Executor Brief V4, SHA256
`d3abed94024646c2256199d954e28a1971c7e26c5eeb346890810493f53c92fc`.

| Slice | Проверяемый результат |
|---|---|
| A | Raw arithmetic, closed windows/parameters, typed unavailable. Accepted CAP-only проходит draft schema и grounding; unknown/unaccepted CAP отказывает. Legacy preview совпадает с frozen-base golden; legacy grounding/availability/temporal и schema/freeze tests PASS. |
| B | 48 BASE_X; universe 40 PASS / 4 FAIL / 4 UNKNOWN; 36 decision eligible. Joint calculable: delta 24, return_ratio 20. Это полные counts для четырёх cohorts, отдельно от 24 examples. Zero target-value loads; cold preview без values и новой reservation. |
| C | Fresh direct decision-cell tautology/impossible query отвергается до values/reservation. Redundant conjunct в meaningful compound даёт warning; исходный hash сохраняется. Saved result, correction и pending recovery используют прежние owners. |
| D | Public MAIN → saved computed evidence → persist-draft → resume → freeze GROUNDED → свежий isolated Critic → actual finalize → `forge-run --persist`. FEAT bindings=[], accepted temporal CAP bound, unresolved=[], availability denial codes=[]. Unbound/tampered evidence и unknown CAP отказывают без store writes. |
| E | Reply-loss recovery: evaluator calls 0. Cold owner readback: values/evaluator 0, inventory unchanged, operation COMPLETED. Registered numerical replay: evaluator 1, точное равенство сохранённому summary. Следующий legacy cycle завершён SEARCH_EXHAUSTED_CURRENT_EVIDENCE. |
| F | Новый агент без истории чата по actual pre-search packet, skill и operator составил SIMPLE holder return_ratio и COMPOUND_FIRST holder delta + PRICE/LIQ. Обе query проходят validator; descriptor совпадает с production owner. Semantic/Catalog owners coherent. |

Свежий native Critic вернул `KILL_LOW_INFORMATION_VALUE`: в synthetic packet
matched и baseline имеют одинаковые PRICE_RELATIVE_PROXY mean/lower-tail metrics;
удаление holder-condition их сохраняет. Отдельного holder contrast нет.
Существующий owner-final — `NON_SCIENTIFIC_STOP`; classifier на таком KILL не
требуется. Recipe полностью GROUNDED механически, без выдуманного unresolved gap.
Capability binding не даёт authority; научного PASS и вывода о реальном рынке нет.
Прямые DocumentRunner/classification и saved-result revision consumers проходят
на committed implementation; новые формулы обслуживает существующий registered
`CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`.

Изолированный code review выявил и закрыл target-clock order dependence,
потерю operation binding при одинаковом preview и пропуск пустого admitted
cohort. Сравнение target copies теперь использует фактический target selector.
Target conflict не удаляет pre-decision seat и не меняет support denominator.
Завершённые ordinary KILL sessions находятся cold reader вместо возврата к
старому draft; их прежний terminal не меняется и REUSED_VALID не добавляется.

P1-B: query без holder delta/return_ratio сохраняет pre-PR preview projection:
pre-decision points и только point_value features, прежние identity/output.
Новый full joint prefix support owner на неё не распространяется.
Совместимость: old point/PRICE/LIQ recipes, scientific hashes и числа остаются
заморожены, включая их прежнюю обработку conflicting future deliveries.
Новая RAW query использует dependency-prefix integrity в общем membership owner.
Declared feature copies сравниваются по source cells и фактической value/lineage
projection существующего feature owner. Разные bound clocks для elapsed_seconds
или utc_hour дают DELIVERY_CONFLICT независимо от порядка копий, сохраняя
decision seat; оба raw holder operators и оба временных feature проверены.
Это ограничение сохранённой совместимости покрыто public regression и точным
base-output golden. P2 first-match saved preview и UniversePolicyError propagation
сознательно оставлены вне NOW; новый repair PR или backlog не создавались.

Evidence: `docs/evidence/forge_composite_feature_recipes_v1/`:

- `a1_vertical_acceptance_v1.json` — key numbers, output hashes и reproduce commands;
- `a1_native_critic_result_v1.json` — полный неизменённый native verdict;
- `a1_native_agent_queries_v1.json` — обе авторские query;
- `a1_native_isolation_v1.json` — реальные inputs/read sets и границы изоляции;
- delivery completion/review/Factory Fit — точные candidate bindings через Harness.

Slice F выполнена свежим P1 агентом на actual pre-search packet commit
`66abc2bb41db2e7f4cb2704980f74f4aafd0da7b`; exact input locator/hash
сохранён в isolation receipt. После clock-copy patch descriptor сверён с actual
v4/v5 packets и текущим owner; обе query повторно валидированы, skill/operator
bytes остались неизменны. Fresh v5 Critic использовал только собственный v5 packet.

Все 21 current composite tests и 38 arithmetic/clock-copy/legacy pure checks PASS.

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

CI integration: schedule binding refusals сохраняют исторические stderr codes
даже при ранней pre-value/pre-reservation проверке. Legacy optional-export
bookkeeping получает NO_CHANGE без release/activation/smoke. После фикса
`71c017e75eb6c6ae362721e0383379ebbb10a7e3` прошли 36 targeted checks: весь
composite module, оба CI-failing public owner paths и registry bookkeeping.
Native Critic сохраняет фактический execution commit86; valid calculator и
scientific binding не изменились от CLI refusal transport repair.

Owner прямо разрешил 2026-10-04 для PR #375 после нового exact-head CI PASS и
`ready_for_owner_phrase=true` самому подставить свежую machine phrase в guarded
merge. Затем обязательны exact main и post-merge CI readback; это текущий stop.
Этот readout сам не утверждает CI, merge или canonical DONE.
