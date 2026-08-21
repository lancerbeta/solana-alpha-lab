# Early-path H900 audition: результат

Терминал захвата: `INVALID_EVIDENCE_YIELD`.

Решение по атому: `INVALID_EVIDENCE_REPLAN`.

## Что реально произошло

Один авторизованный Jupiter Free-key read-only прогон прошёл credential-free
preflight и сделал 44 provider-запроса: `/recent`, один bulk
`/tokens/v2/search` после ожидания pool age ≥ 5m, 21 quote-only BUY T0 и
21 quote-only SELL H900. Retry/fallback, `/build`, `/execute`, taker, wallet
и второй провайдер не использовались.

Заморожены 24 свежих project-eligible mint’а, исключая ранее потреблённые,
включая когорту `ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1`.
`X = (mcap_T5 / mcap_recent) - 1` был пригоден у 21 из 24 строк. У 3 строк
mcap отсутствовал или был непригоден (`MCAP_FIELD_MISSING_OR_INVALID`) и не
заменялся нулём. У 6 eligible строк `X = 0` как наблюдаемое равенство двух
mcap, а не как импутация UNKNOWN.

Все 21 T0 BUY получили `QUOTE_OBSERVED`. На H900: 17 `QUOTE_OBSERVED` и
4 `UNKNOWN_TYPED_FAILURE` (HTTP 400). Rankable H900 = 17, что выше пола 14.

Замороженное правило не применялось: в верхнем квартиле X есть строка без
H900 `QUOTE_OBSERVED` (`selected_top_quartile_non_quote`). Машинный терминал
поэтому `INVALID_EVIDENCE_YIELD`, а не `EARN_FRESH_OOS` и не
`CLOSE_EARLY_PATH_CANDIDATE`. Числа tau-b / квартильных Y на rankable
подвыборке не являются прохождением или провалом правила.

Receipt: `a1_ordinary_recent_early_path_h900_audition_runtime_receipt_v1.json`.
Его SHA-256: `0acdc847eaf404bf61845cd471b17b91cf6255f24edc82363c2f10a74e7d786b`.
Hash входного списка ранее потреблённых mint’ов:
`f7f88369804c4f7794e31e47bb3b2ac041cddd2a38755480ef6b9d13aeddeb9d`.
`/recent` body SHA-256: `a2a61a3622cd398bf59c9154c98eb413d410926d52890fd0833fb19fafa56792`.
T0 search body SHA-256: `213aaa5dd8e301555e68e96fabbe27c8bc2db950bdd332fc8f7bff932f41fd9b`.

## Что это значит

Это gap полноты H900 quote на выбранном верхнем квартиле X, а не нулевой
early-path, нулевая доходность, alpha или `NO_ROUTE`. Гипотеза не получила ни
подтверждения, ни закрытия по замороженному правилу.

## Следующее решение

Не повторять тот же атом автоматически и не переходить к Strategy, Bot, Shadow,
organic/flow, TX_IMBALANCE, H3600/H4, alpha или NetReturn. Для продолжения
нужен отдельный replan; иначе эта two-point mcap-path ветка остаётся
недоказуемой на текущем quote-complete правиле.

## Явные ограничения

- cash spend: `$0`;
- credential reads: `1`;
- execute/build/taker/wallet/signer/transaction: `0`;
- provider requests: `44` (лимит 60);
- raw provider bodies остаются вне Git, в receipt хранятся только hashes/times и типизированный outcome.
