# Early-path Failed-to-get-quotes → MEU: результат

Терминал репроекции: `CLOSE_EARLY_PATH_CANDIDATE`.

## Что сделано

Без нового Jupiter-захвата. Исторический runtime receipt
`ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1` (SHA
`0acdc847eaf404bf61845cd471b17b91cf6255f24edc82363c2f10a74e7d786b`) и четыре
H900 body с текстом `Failed to get quotes` зафиксированы как Git fixtures.

В общем `project_quote` сообщение `Failed to get quotes` связано с
`MARKET_EXECUTION_UNAVAILABLE` (раньше уходило в `UNKNOWN_TYPED_FAILURE` и
блокировало правило выбранного верхнего квартиля). Offline reproject дал:

- 4/4 remaps → MEU;
- `selected_market_execution_unavailable=true`;
- terminal `CLOSE_EARLY_PATH_CANDIDATE`;
- provider_requests `0`, credential_reads `0`, cash `$0`.

Исторический owner decision `INVALID_EVIDENCE_REPLAN` на исходном acceptance
не переписывался.

## Что это значит

Early-path mcap X измерим, но гипотеза «ранний mcap-path предсказывает
восстановимый H900 exit» закрывается: в выбранном верхнем квартиле X есть
неисполнимый H900 SELL, а у всех 17 rankable Y наблюдаемый знак отрицательный.
Это не EARN и не alpha.

## Следующее решение

Не повторять early-path live campaign. Не возвращать organic/flow/`TX_IMBALANCE`.
Следующий атом — новый простой market-state estimand под ту же H900 quote-only
рамку, либо явный stop этой ветки на уровне roadmap.

## Явные ограничения

- новый capture запрещён этим атомом;
- source yield receipt immutable;
- Strategy/Bot/Shadow/H3600/H4/alpha/NetReturn не заявлены.
