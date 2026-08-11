# TASK-30 — forward raw trade route

## Решение

Статус: офлайн-контракт проверен; будущий owner packet ещё обязателен.
Он не разрешает внешний запрос, выбор провайдера или использование ключа.

## Что зафиксировано

- Наблюдение, transport loss и unknown coverage различаются явно.
- Unknown не становится пустым интервалом, нулём или complete data.
- Дубликат signature, неверный pool, retry, fallback и reconnect до reconciliation блокируются.

## Следующая граница

Следующая граница — отдельное решение owner о внешнем техническом pilot.
