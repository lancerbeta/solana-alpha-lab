# BAA-003 — disposition C для выбранного List A recipe

Подтверждён fixed-time exploratory price-relative proxy. Accepted bound protocol
chronological/OOS продолжения этого recipe не найден. Полный положительный
science-to-strategy путь BLOCKED_SCIENTIFIC_PROTOCOL_C. Это точная постановка
следующего scientific contract, а не новый scientific grant или implementation.

Подтверждённый маршрут: `OPPORTUNITY_EPISODES`, `LIST_CONTRAST`, List A membership
на T0, decision E1800, `PRICE_RELATIVE_PROXY` E1800→E14400, comparator — eligible
complement на том же cutoff. Consumer — owner, который решает, оправдана ли
независимая проверка этой association. Это не executable net return.

Source refs:

- `tests/test_forge_research_flow_reliability_v1.py`, EpisodeFlowTests.look и native
  positive test: фактически выбранный query, classify, final runner и replay.
- `docs/contracts/forge_list_aware_research_scope_v1.md`: List-aware scope.
- `configs/experiment_capability_registry_v2.yaml`: accepted temporal capability
  поддерживает deterministic offline/PIT reuse; promotion authority NONE.
- `src/solana_alpha_lab/factory/hfic_temporal_discovery.py`: observed contrasts —
  observational association; cohorts descriptive, не независимые replications;
  COMPLETE может иметь INCONCLUSIVE terminal; replay проверяет bindings.
- `docs/contracts/forge_research_flow_reliability_v1.md`: chronological validation
  UNKNOWN как отдельная capability/authority.
- `docs/contracts/opportunity_episodes_jupiter_v1.md`: repeated mints/selection/
  attrition нельзя объявлять IID или автоматически исправленными.

Вариант A не подтверждён: нет exact accepted consumer/protocol/data-binding для
later validation этого estimand. Вариант B тоже не подтверждён: наличие temporal
engine и synthetic deterministic inputs не доказывает, что protocol принят и
нужно только инженерное подключение. Другая holder/MEU capability не заменяет
protocol этого recipe. Registry entry без реализации не создаётся.

**Единственный предлагаемый decision delta:** заморозить chronological validation
той же List A observational association на exact later cohort/time boundary,
с dependency/attrition rules, one-shot falsifier, uncertainty criterion и exact
data/look authority. Ни один из этих UNKNOWN не выбирается исполнителем за owner.

| Поле контракта | Подтверждено | Предлагаемая граница / требуется owner |
|---|---|---|
| Question/estimand | List A contrast fixed price-relative proxy | сохранить именно этот proxy estimand; separate NetReturn contract нужен для денежного вопроса |
| Unit/universe | episode, eligible complement; repeated mint возможен | unit episode с dependency по mint/time; exact admission universe и правило repeated mint до look |
| PIT clocks | T0 membership, decision E1800, target E14400 | frozen availability cutoff, target никогда не eligibility; future/late input не входит в decision |
| Existing/missing | engine и synthetic proxy data работают | exact later unexposed cohort IDs/time interval, source refs/hashes/coverage UNKNOWN; новый provider не предлагается |
| Chronological split | accepted later split этого recipe отсутствует | later interval строго после frozen development interval; no overlapping episode/horizon; mint overlap явно исключён либо моделируется одним frozen правилом |
| Metric | native group means/contrast и denominators | one fixed contrast без перебора; effect direction и threshold UNKNOWN до owner freeze |
| Uncertainty | descriptive cohorts не IID | frozen dependency-aware interval/estimator, missing/selection/attrition accounting, sensitivity policy; numerical criteria UNKNOWN |
| Insufficiency/falsifier | missing/empty/uncertain остаются typed | заранее заданные coverage/dependency/min effective N и interval rule; failure/insufficiency не положительный result; критерии UNKNOWN |
| Trial/reuse/holdout | native replay не новый look; exposed history остаётся exposed | one preregistered validation MAIN как предложение; exact budget/authority UNKNOWN, no retuning; protected holdout не открывается |
| DIRECT producer | DocumentRunner выдаёт execution identity/passport | accepted science evaluator должен выпускать source-owned metric/binding с experiment ID, canonical version, frozen split/recipe/results refs; RUN_COMPLETED этого не заменяет |
| Downstream | dossier/promote guard сохраняет obligations | DIRECT science consumer, conflict rejection, independent revalidation и frozen handoff; accepted strategy/economics contract отдельно |
| Entry/falsifier | `research-scope-resolve` → `discovery-execute` → classify → native runner работает для exploration | сначала metadata-only resolve exact later bindings/protection/dependencies; cheapest falsifier — нет accepted protocol/data authority или нарушен temporal/overlap cutoff: stop до value read/look |

Implementation можно планировать только после одного frozen owner contract с
перечисленными exact values и полномочиями. Approval repair PR не отвечает на
эти scientific вопросы. Сейчас допустимый next action — подготовить/утвердить
этот protocol; запрещено повторять science, выбирать threshold по observed
result, читать holdout или обещать strategy/cashflow.
