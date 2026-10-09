# Native Forge Lifecycle Closure — checkpoint

**BLOCKED: полный DoD не достигнут, native closure 0/2.** Исчерпаны четыре разрешённых новых Generator-эпизода. Неиспользованные revision slots не дают права повторить новые вопросы; actual Critic вернул STOP. Записи, исходные ответы и потраченные looks сохранены.

Main изменился: PR391 включён обычным merge, база `d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc`; её CI37988774921 завершён SUCCESS, 10/10 jobs. Финальная execution epoch — `838753ba29224a4b4cfc5298637b5a03aa4dc930`, composite `a13130ec4dc5ac1b581f3332bf610df7d09c8f3df9b6615dc1019b8660a45557`. Delivery evidence не перепривязывает старые native runs к новому head.

## Что реально изменено

Public authoring descriptor теперь показывает источники saved-look bindings. Ordinary MAIN публикует существующий `ORDINARY_GROUNDED_DISCOVERY_V1`, если route label отсутствовал. Авторский вопрос, estimand, condition, admission, PIT, budgets и family-close semantics не выводятся из результата. Первый native pair отказал из-за отсутствия mode; адресный regression воспроизвёл отказ до repair. Минимальная исправленная причина проверена, полная capability не принята. После native outcome исправлено противоречие skill: ordinary mode копируется из saved MAIN, если preflight не публикует mode; estimand/condition требуется передавать до MAIN. Исправленный текст не объявлен native-proven на старой epoch.

## Native denominator и остаток

| Epoch/case | MAIN/PREVIEW/ADAPTIVE | Фактический исход | Приёмка |
|---|---|---|---|
| Первый primary | 1/1/0 | UNKNOWN_PRIOR_SCOPE до persist | BLOCKED |
| Первый transfer | 1/1/0 | UNKNOWN_PRIOR_SCOPE до persist | BLOCKED |
| Финальный primary | 1/0/0 | freeze → original independent Critic → finalize → новый reader: SYNTHESIS_COMPLETE/KILL_UNBOUND_EVIDENCE | FAIL: technical terminal |
| Финальный transfer | 1/1/0 | UNKNOWN_PRIOR_SCOPE до persist; session/packet отсутствуют | BLOCKED |

Generator **4/4**, revisions **0/2**, Critic **1/6**, MAIN4, PREVIEW3, ADAPTIVE0. Scripted control был отдельным техническим запуском (1/0/0), не native numerator. Recovery clone переигрывает те же сохранённые артефакты, не добавляет scientific charge. Время, стоимость, модель, seed и token provenance не доступны полностью: UNKNOWN.

Primary: одноусловный положительный holder delta внутри заранее выбранного toptrending universe; observed matched mean +0.30 при 1 observed / 2 eligible против baseline +0.08 при 5/6. Transfer: положительный рост в двух prefix-окнах; позднее условие не добавило observed discrimination относительно раннего. Это tiny-N synthetic proxy, не alpha, causal proof или OOS.

Два остаточных разрыва подтверждены trace. Transfer отправил `{}` как MAIN candidate scope: две смысловые оси были записаны до values отдельно, но не связаны с saved look. Persist видит более широкий card scope, теряет binding вычисленного evidence и отказывает. Нельзя задним числом подставить эти оси исполнителем. Primary содержит historical quote prior с отсутствующими scientific axes; runtime full-archive safety допустил incomplete prior без установленного SCOPE_DISTINCT, public Critic запретил PASS. Applicability prior остаётся UNKNOWN; его несвязанность не доказана. Неизвестность не превращена в отрицательный научный результат или family close. Отказ transfer не называет offending prior; его собственная гипотеза о том prior не подменяет подтверждённую проблему scope ingress.

## Проверки и пределы

V1: primary composite стабилен и fresh readback PASS; transfer PARTIAL до отказа, terminal отсутствует. V2: FAIL, technical KILL исключён приёмкой. V3: BLOCKED до persist. V4: PASS для сохранённого technical terminal — reply loss, новый process reader, identical retry без дополнительных records, different result SESSION_CONFLICT без store changes; MAIN occupancy1 неизменна. V5/V6: PARTIAL — scoped negative/PIT/list/budget evidence и отдельно обозначенное reuse предыдущей epoch; это не вся negative matrix и не native acceptance. V7: PASS на primary technical result, BLOCKED на transfer. Независимый Goal/DoD: primary Q1/Q2/Q3/Q4 PASS в bounded engineering rubric; transfer Q1/Q2/Q4 PASS, Q3 FAIL на empty MAIN authored scope. Это качество вопросов, не native closure PASS. Scientific power/causal control не добавлены к DoD задним числом.

На финальной epoch: 13 focused checks PASS; прежняя epoch: 9 узких lifecycle/PIT/recovery checks PASS плюс baseline12 и static Factory. Full local gate не запускался. Candidate exact-head CI, merge-readiness, completion PASS и owner phrase отсутствуют, потому что mandatory DoD failed. Независимые required reviews приложены к этому checkpoint, их FAIL не переименовывается в готовность к merge.

Оригиналы сохранены локально и в evidence wrappers: `original_utf8_text` восстанавливается byte-identical и проверяется исходным SHA256; машинные пути/воспроизводимые копии метода остаются local-only hash либо отдельной path-redacted projection с явной меткой. Проекция никогда не подавалась обратно как native input. Logical context isolation не доказывает OS isolation/model diversity. Critic встретил unrelated example numbers в разрешённом public method; exposure раскрыт в original report/trace.

## Один следующий шаг

Рекомендуется **один local replan того же task**: проверить полноту authored scope до MAIN и согласовать трактовку incomplete prior с неизвестной applicability в existing owners; затем отдельно разрешить одну новую финальную пару primary/transfer на заранее committed code/method snapshot. Бюджет не сбрасывать: новая пара учитывается сверх сохранённых 4 попыток. До этого новых моделей, looks и merge нет. Это material scope/budget boundary из §11/§16 исходной постановки, а не запрос на обычный engineering microstep.

Exact locators, originals hashes, counters и residual находятся в `checkpoint.json`; canonical session HFIC-SESS-2949E0B69BDF6189 читается на original compatible epoch. Rollback mode-default возвращает подтверждённый persist failure; descriptor rollback возвращает discovery gap. Stored records и spent slots сохраняются при любом rollback.

После независимого review исправлены только доказанные локальные дефекты: explicit malformed mode не превращается в omitted ordinary label; regression проверяет фактический ordinary ingress с None и отдельно условный verified-mode conflict; timeout capture сохраняет partial bytes и UNKNOWN side effect до saved-state readback. Новая code/method epoch не имеет нового native proof: original runs остаются привязаны к838753ba, full DoD FAIL и бюджет4/4 неизменны.

Transfer ordinary readout предлагает `AUTHORIZE_ADDITIONAL_LOOKS` в `PAUSED_CAP`. Это общий operation hint, не полномочие task: MAIN уже1/1 и Generator4/4. Возобновление начинается с exact saved checkpoint и local replan binding, не с дополнительного look. Проверки post-native reviewer repairs: 6 адресных checks PASS, включая7 malformed-mode subcases и capture timeout; исходный RED и исправленная test nesting раскрыты в targeted-validation.json. NEXT_MODEL_EFFORT: SOL_XHIGH.

Безопасное чтение в новом процессе: `<ARTIFACT_HOME>` — папка local-only `local-locators.json`, рядом лежит `readback-primary.ps1` (Git-шаблон в tests/fixtures/forge_native_lifecycle_closure_v1). Выполнить `powershell -NoProfile -File "<ARTIFACT_HOME>/readback-primary.ps1"`. Script сначала сравнивает production composite с original snapshot, затем вызывает существующий show-session; ожидает SYNTHESIS_COMPLETE/KILL_UNBOUND_EVIDENCE и charges1/0/0, после чего останавливается. Локальные абсолютные aliases находятся только в local-locators.json, Git их не публикует. Чтение на новом dev head вместо original compatible epoch запрещено.
