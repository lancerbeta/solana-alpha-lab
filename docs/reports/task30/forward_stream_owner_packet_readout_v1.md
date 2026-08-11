# Пакет готовности будущего stream-пилота

Это предложение одного технического чтения и не является сделкой.
Цель: пул URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S и base mint DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK.
Возможный поставщик пока только предложен, но не выбран.
Лимиты будущего запуска: 1 соединение, 1 подписка, 1 200 секунд и 500 уведомлений.
Запуск только в foreground; retry, reconnect и fallback запрещены.
Raw-данные могут сохраняться только после отдельного gate по retention A4 вне Git.
Потеря транспорта остаётся UNKNOWN: остановиться, сохранить безопасный receipt и не повторять до отдельного reconcile gate.
Ни пустой интервал, ни нулевой объём, ни полнота покрытия здесь не заявляются.

Точная будущая фраза разрешения:
T30-A13P_FORWARD_STREAM_PILOT_V1; pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND; max_wss_connections=1; max_subscriptions=1; max_open_seconds=1200; max_notifications=500; retention=A4; retry=false; reconnect=false; fallback=false
