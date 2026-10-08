# Native formulation: одна synthetic карточка

Результат: одна authored `PREDICTIVE` карточка точного уже зарегистрированного `native-main-0`. Научный terminal не присвоен. Реальный Forge run, новый look и эксперимент не запускались.

Сочетание фиксированного роста цены, отката к Y3600 и заданного отношения ликвидности формулируется как проверяемая гипотеза дополнительной предсказательной информации о Y3600 -> Y7200. Это наблюдательная гипотеза: actor/counterparty и причинный механизм `UNKNOWN`. Retention >= 0.1 не называется устойчивой ликвидностью.

## Source-bound receipt

- Source repository HEAD readback: `b29d011994f5e4cf328175dc1a4929d28957e25a`; checkout clean. Product `AUDIT_SHA=0dbe4d4bb5ce9703332a0620987a47eac05c4cdc` supplied by caller, отдельно не переинтерпретирован.
- Method instructions: current `hypothesis-forge` / Prompt A `HFIC-V1.2`, exact flat-card/schema/transport contract referenced by Prompt A.
- Единственный market/evidence input: `generator-input.json`; raw parquet, ResearchStore и новые values не читались.
- Top-level axes: `population=BASE_X`, `decision_timestamp=Y3600`, `target=PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001`, `estimand=price_relative_proxy`, `explanatory_condition=compound`, `representation_scope=TEMPORAL_PRICE_LIQUIDITY`, `evidence_surface_mode=ORDINARY_GROUNDED_DISCOVERY_V1`.
- Fixed predicates: impulse `[0.25,2.0)`, pullback `[-0.4,-0.1)`, retention `>=0.1`; windows, clocks, costs и frozen bindings скопированы из input без tuning.
- Saved evidence ref: `HFIC-ART-DISCOVERY-1B7BDBF7C350EFB65AFC8F2E0F48E42DEFF00D8E`.
- Saved spec SHA256: `140a1c08a720e18a128da1b4b5f6dc48c5950470429f87f7e5f657617d61c0ae`.
- Saved result SHA256: `55a182c49cf7c2fbeee3dd01d780d8845487304d5cb16001aa874551785240dc`.

## Material limitations

Matched, same-decision baseline и все три drop-one-condition ablations содержат одно и то же единственное наблюдение: mean/median PRICE_RELATIVE_PROXY около +0.2. Они не дают отдельного contrast и не доказывают predictive effect. Один calendar block/cohort, independence `UNKNOWN`, independent replication отсутствует. Четыре из пяти unique decisions исключены `NOT_X_ELIGIBLE`; matched missing target=0 не устраняет selection/dependency ограничения.

Downside readout имеет observed_n=1, ES10 около +0.2, события <=-20% и <=-50% равны 0/1; это описательные числа, не оценка надёжного tail-risk и не confidence interval. `worst_negative_share=null` сохранён как отсутствие отрицательного вклада, а не нулевая concentration.

Costs — `ASSUMPTION_NOT_CALIBRATED`, `MARK_NOT_QUOTE`: ESTIMATED_NET_PROXY LOW около +0.164, BASE +0.026, STRESS -0.30. Quotes, fills, live fee schedule, executable notional/capacity отсутствуют. `source_price_event_time=UNKNOWN`; fixed schedule и поздний target не доказывают source-event PIT.

Bounded prior `HYP-QUOTE-NATIVE-FRICTION-H900-V1` имеет `HISTORICAL`, но полный scope/terminal не представлен. Карточка честно обозначает `REFORMULATION` существующего вопроса и не заявляет novel mechanism или отсутствие duplicate.

`freeze_worthy=false` и `READY_TO_FREEZE` прочитаны как routing hints: ни один не преобразован в научный KILL/PASS. Новая information sufficiency, экономическая проверка или сбор данных здесь не авторизованы.

Записаны только `authored-card.json` и этот `formulation-report.md`. Карточка — output 1 из разрешённого audit-budget; в ней нет runner-up или второй гипотезы. Следующий шаг принадлежит caller: source-bound проверка переноса и независимая critique по frozen packet, если pipeline допускает freeze.
