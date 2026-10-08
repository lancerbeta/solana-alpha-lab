# CI: 60 минут для PR и main

По прямому запросу owner полные группы CI-тестов получают одинаковый лимит
60 минут и в PR, и на main. Условие только для PR #386 удалено.
Тесты, fail-closed aggregator, source pins и условия merge сохранены.

Исходный audit+PREVIEW repair уже смержен в PR #386. Его K1–K6 PARTIAL,
confounders и отсутствие chronological consumer не изменяются.
Нового product repair или scientific output нет.

Предыдущий main запуск [CANCELLED](https://github.com/lancerbeta/solana-alpha-lab/actions/runs/37798838954/attempts/1):
1154 selected cases завершились с failures=0/errors=0 и 20 existing skips;
общий job всё равно отменён таймаутом, обязательный aggregator — FAILURE.
Это не подменяется PASS. Подробности: ci-timeout-evidence.json.
