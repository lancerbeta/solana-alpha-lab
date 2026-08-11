# TASK-30: пакет owner-review для двухслотового shakedown

## Что подготовлено

Офлайн-пакет для двух независимых foreground-проверок закрытой 15-минутной свечи.

## Предлагаемая граница будущего запроса

- Candidate: GECKOTERMINAL_PUBLIC_KEYLESS для pool URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S.
- Ровно 2 closed slots и 8 публичных GET максимум.
- Offsets: 0, 15, 30 и 60 секунд; retry и fallback запрещены.
- Raw JSON будет храниться вне Git по A4 с manifest/hash после каждого ответа.

## Что это не разрешает

Этот пакет не разрешает внешний запрос, не выбирает provider и не запускает scheduler.
Точные UTC slots и monitoring owner остаются OWNER_INPUT_REQUIRED.
Потеря monitoring или отсутствующий prior receipt означает STOP_RUN, а не тихий restart.

## Следующая граница

Статус: OWNER_APPROVAL_REQUIRED. Нужен отдельный owner gate: EXACT_OWNER_EXTERNAL_READ_AUTHORIZATION.
Ни один результат будущего shakedown сам по себе не разрешит 24-hour capture.
