# Research Shelf: совместимость двух readers

SMIAL принимает уже опубликованные текстовые mutation_id Scout без преобразования
или изменения revision hashes. Scout принимает логические smial-data URI native
ссылок без обращения к ним. Физические paths и повторное использование mutation
identity для других bytes остаются ошибкой. UUID generation остаётся прежним.

Минимальная вертикаль: 2 сохранённых SMIAL + 5 Scout records, обе истории по 9
revisions и один общий synthetic fixture из 2 records читаются обоими readers.
Round-trip bytes, item/mutation/revision IDs и DAG heads совпадают. Восемь literal
review/event projections сохраняют смысл при явных product-specific label aliases.
16 focused SMIAL checks проверяют wire/guards и actual disposable Git retry/
invalid-history reservations. Scout имеет свои focused reader/consumer checks.

Portable fixture `tests/fixtures/research_shelf_v1/compatibility.json` одинаков
в обоих репозиториях: SHA256
`0c65d74ff818372912bbbaea519c975e4f37ae1c0249e975b09e76b451bebec6`.
Это публичный synthetic пример, без private Scout fields. Реальные private rows
не переносятся в public fixtures или evidence; опубликованные bytes не меняются.

Изменение формата — расширение reader acceptance существующего V1, не миграция.
Не переиздавать старые IDs/revisions и не переписывать историю. Повторный запрос
сохраняет свой исходный mutation_id и prepared bytes. Две code changes проходят
собственные CI/merge gates; при одном ещё не принятом reader interoperability
остаётся частичной. Никакого runtime/scheduler cutover в этом PR нет.

Проверки: `validation.json`; canonical delivery bindings — `completion.json`,
`independent-review.json`, `factory-fit.json`. Review/CI/merge readiness и merge
определяются отдельными exact-head gates; этот текст не является merge authority.

Data refs остаются SMIAL `a6f03eb9d81adc93f828b994eea7525814dfa12b` и Scout
`d440b1444741b09e6ed3575bdeba1701b8785e70`. Публикаций данных, scientific runs,
native rebind, изменений reminders/scheduler — 0. Native admission/binding,
TOPTRADED source-byte verification и полный commissioning не утверждаются.

Rollback: обычный code revert, с сохранением immutable data и native history.
При возврате старого reader ожидается прежний typed invalid для чужого формата;
не пытаться «лечить» это переписыванием опубликованных records.

Factory Fit: FULL_REVIEW, инженерная совместимость; научные owners не меняются.
Product Horizon NOW=NONE; WATCH — новый реальный cross-product wire mismatch.
Новая библиотека, registry, database или scheduler не нужны.
