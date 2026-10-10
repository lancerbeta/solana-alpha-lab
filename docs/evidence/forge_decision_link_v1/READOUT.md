# FORGE_DECISION_LINK_V1 — S0 checkpoint

**Новый слой хранения для проверенной single-test вертикали не обоснован.**
На базе `76993054cfaeeee7e9fb6e7b718add8cf27e404a` публичный план уже
сохраняется в supported `question_text`. Native writers связывают его
с exact operation/spec, reservation, result и scientific disposition.
Холодный reader возвращает оригинальный план, результат и условный вывод.
Диагноз: `NO_GAP` **только для exact single-test ordinary
OPPORTUNITY_EPISODES / BASE**. Общий multi-look outcome этим не закрыт.

## Что действительно выполнено

Existing production-produced synthetic episode fixture, public scope-resolve,
preflight, discovery-execute и disposition-record. Авторский план записан
до native test через существующий public carrier; отдельное предложенное
поле `decision_basis` не объявляется существующим API.

Независимый literal oracle: A subset 4, observed 3, missing 1, mean 0.10;
observed contrast 0.20. Missing target остаётся missing. Оценка записана как
допустимый `INSUFFICIENT_EVIDENCE`, а не отрицательный факт или candidate.
В rationale сохранены сравнение с планом, `NOT_ESTABLISHED` и условие
пересмотра; caveats исключают NetReturn/alpha/family close/reopen.

Existing disposition writer сам заполнил `basis.operation_sha256` по
настоящему result. Никакого ручного внесения link в store не было.
В отдельном публичном процессе адресный saved replay прочитал original
`ordinary_operation_readout.question_text`, сохранил result refs/hash и
не вызвал evaluator/values. Canonical query извлечён из **сохранённого
operation.spec_canonical**, scope — из **сохранённого result**; исходный
author request не передавался в этот cold replay.

Доказанный маршрут consumer:

```text
disposition-show --owner-focus <exact collection-prefixed focus>
  -> body.basis.operation_sha256 + result_refs
  -> existing get_operation / list_discovery_looks exact source read
  -> operation.spec_canonical + saved candidate_scope
  -> discovery-execute --operation-sha256 <bound operation hash>
       --spec <source-derived query> --candidate-scope <saved scope>
  -> original outward plan + saved descriptive result
```

Это составной путь через существующих source owners, а не новый turnkey
read command. One-command owner navigation convenience не квалифицировалась.
`research-policy-status --for-operation` показывает бюджет, план не отдаёт.
Обычный `preflight` — **context writer**, наблюдался append; zero-write
доказательство относится отдельно к disposition detail, status и saved replay.
В этом envelope committed inventory и все file bytes store совпали до/после.
Market, journal, operation/slot/accounting keys и occupancy сохранились.

## Evidence и ограничения

- [Manifest/denominator](obligations.json): V01–V18 остаются `NOT_RUN` для candidate implementation.
- [Entry result](entry-result.json): compact exact refs/checks; полный retained terminal —
  `local/forge_decision_link_v1/entry-a03/terminal.json`, sha256
  `28bcfa38d92473f2d45bbd5d24c2f72073ea4fe99cba9a192b97e317e5d1edef`.
- [Repair history](repair-history.json): все три fixture attempts и пять cold repairs,
  включая сохранённые отказы и явно transcript-derived ранние наблюдения.
- [Reproducer](../../../tests/fixtures/forge_decision_link_v1/entry_probe.py): native owners,
  независимый численный oracle и сравнение inventories.
- [Исходный PRD/SSD](source-contract.md) сохранён побайтово; второй дизайн не создан.
- [Независимое S0 review](stage-review.json): checkpoint допустим с раскрытыми
  ограничениями; итоговое delivery review всего атома не выполнялось.

Fidelity: `SEGMENT_PRODUCT_PATH`. Actor selection, positive candidate/Critic,
multi-look plan, supported-text edits/V05, pending/crash/races, rollback и
near-cap qualification не выполнялись. Изменение только **игнорируемого
предложенного** поля replay не доказывает инварианты нового поля или V05.
Comparison с A9/A10: `UNVERIFIED`; модельных choice outputs нет. A9/A10 уже
содержат decision/information value, strongest alternative и falsifier;
новый treatment не доказан. Live use `NOT_EXECUTED`, alpha/OOS/economics
`NOT_EVALUATED`. Production/source schemas не изменялись; PR/CI/readiness
и завершение всего атома не заявляются.

Retained attempts: 43,941,699 bytes. По файловым clock metadata fixture campaign заняла
935.136 секунд при выбранном cap 900: **cap превышен, product work остановлена**.
Суммарное время процессов, CPU/RAM и стоимость review — `UNKNOWN`.
9.811 секунды в terminal — только последний cold resume, не весь S0.
Ранние cold outputs были перезаписаны до исправления retention; их наблюдаемые
отказы сохранены в normalized repair ledger, exact raw replay history неполна.
В raw terminal один hash для `resume-commands.json` остался от предыдущего
resume: сохранённый список команд полностью совпадает с `terminal.commands`,
но byte hash различается. Остальные 20 artifact hashes и 7 source fingerprints
совпали. Расхождение сохранено явно; raw terminal не переписан. В helper
исправлены retention и обновление hash журнала команд; после cap breach
повторный product run не выполнялся, проверен только синтаксис.
Это границы engineering evidence, а не скрытое product PASS.

## Решение и следующий этап

`S0_COMPLETE_WITH_LIMITATIONS`. Existing-first requirement дала reuse,
поэтому новый reservation payload или disposition schema сейчас не вводить.
Factory Fit: узкий source-owner reuse полезен; новый storage seam не доказан.
Product Horizon NOW: проверить оставшуюся **multi-look** предпосылку;
WATCH: менять policy выбора лишь после distinct-treatment и comparative gain.
Tools/plugins/connectors/automation/dependencies: `NONE` сверх уже используемых.

Следующий этап после owner OK — один adversarial probe: **одна ordinary
operation, два поддержанных native теста, авторское изменение плана между
ними и cold restart** на synthetic данных. Сначала зафиксировать новый ресурсный бюджет,
обеспечить накопительный учёт времени между resume и
ответить, достаточны ли существующие per-look/source links. Новый look
только synthetic; science/query/budget/authority invariants остаются прежними.
Лишь доказанная потеря позволит выбирать минимальный patch или projection.
`NEXT_MODEL_EFFORT: SOL_XHIGH`.
