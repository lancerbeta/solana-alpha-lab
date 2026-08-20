# Organic pressure H900 audition: результат

Терминал захвата: `INVALID_EVIDENCE_YIELD`.

Решение по атому: `INVALID_EVIDENCE_REPLAN`.

## Что реально произошло

Один авторизованный Jupiter Free-key read-only прогон прошёл credential-free
preflight и сделал ровно два provider-запроса: `/recent` и один bulk
`/tokens/v2/search` для замороженных 24 mint’ов. Оба ответа наблюдались как
`TOKEN_LIST_OBSERVED`, без retry/fallback.

В decision-time snapshot только 2 из 24 строк имели пригодные organic-поля.
У 22 строк `stats5m.buyOrganicVolume` и/или `stats5m.sellOrganicVolume` были
отсутствующими или непригодными. Минимум для решения — 18 eligible строк.

Поэтому BUY T0 и SELL H900 не вызывались вообще. `X` не превращался в ноль,
`Y` не вычислялся, а гипотеза не получила ни подтверждения, ни опровержения.

Receipt: `a1_ordinary_recent_organic_pressure_h900_audition_runtime_receipt_v1.json`.
Его SHA-256: `20cff315f225f405f2daca493acbc3ff66ef7910d718e769c2e22fdcf0dd4040`.
Hash входного списка ранее потреблённых mint’ов:
`9bb4ea567fad40ea34cd48d77351e98cb839608ff1c36dd992d07cdce12c4ed5`.

## Что это значит

Это gap доступности/пригодности organic-полей в выбранном T+5 snapshot, а не
нулевой pressure, нулевая доходность или `NO_ROUTE`. Данных для порога tau-b,
верхнего квартиля и H900 recovery нет.

## Следующее решение

Не повторять тот же атом автоматически и не переходить к Strategy, Bot, Shadow,
alpha или NetReturn. Для продолжения нужен отдельный replan, который сначала
докажет доступность нужных organic-полей на decision-time; иначе ветка
закрывается как недоказуемая.

## Явные ограничения

- cash spend: `$0`;
- credential reads: `1`;
- execute/build/taker/wallet/signer/transaction: `0`;
- quote calls: `0`;
- raw provider bodies остаются вне Git, в receipt хранятся только hashes/times и типизированный outcome.
