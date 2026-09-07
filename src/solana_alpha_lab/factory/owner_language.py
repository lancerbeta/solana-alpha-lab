"""Russian-first owner presentation. Owns no scientific or machine truth."""

from __future__ import annotations

from typing import Any, Mapping

PRESENTATION_LANGUAGE = "RU"
MACHINE_LANGUAGE = "EN"

NAV_LABELS = {
    "HOME": "Главная",
    "RESEARCH": "Исследования",
    "OPERATIONS": "Операции",
    "ECONOMICS": "Экономика",
    "SYSTEM": "Система",
}

COUNTER_LABELS = {
    "ACTIVE NOW": "Активно сейчас",
    "TRIALS": "Проверки",
    "DECISIONS": "Решения",
    "NEGATIVES": "Отрицательные результаты",
    "ATTENTION": "Требует внимания",
    "GAPS": "Пробелы",
    "SCIENTIFIC PROMOTE": "Научно продвинуто",
    "READY TO STRATEGY": "Готово к стратегии",
    "HANDOFF BLOCKED": "Переход заблокирован",
    "STRATEGY MATERIALIZED": "StrategyVersion создана",
}

RESEARCH_COPY = {
    "title": "Исследования",
    "projection": "Проекция",
    "source": "Источник",
    "status": "Статус",
    "plane": "Плоскость",
    "error": "Ошибка",
    "next": "Дальше",
    "needs_attention": "Требует внимания",
    "current_activity": "Сейчас выполняется",
    "universe": "Объекты",
    "all": "все",
    "hypotheses": "гипотезы",
    "experiments": "эксперименты",
    "trials": "проверки",
    "decisions": "решения",
    "negative": "отрицательные",
    "search": "найти",
    "search_aria": "поиск по исследованиям",
    "col_kind": "вид",
    "col_title": "название",
    "col_state": "состояние",
    "col_plane": "плоскость",
    "col_evidence_class": "evidence_class",
    "col_as_of": "as_of",
    "col_source": "источник",
    "col_marker": "метка",
    "col_id": "id",
    "back": "← Исследования",
    "detail": "Карточка",
    "lineage": "Связи",
    "inbound": "Входящие",
    "outbound": "Исходящие",
    "gaps_unknown": "Пробелы / неизвестно",
    "source_provenance": "Источник / происхождение",
    "timeline": "Хронология",
    "technical": "Технические детали",
    "none": "нет",
    "not_available": "недоступно",
    "degraded_copy": (
        "Источник ResearchStore этой рабочей панели недоступен. "
        "Git-эксперименты, проверки и решения ниже остаются видимы."
    ),
    "what_was_tested": "Что проверяли",
    "evidence": "Доказательства",
    "result": "Результат",
    "direct_evidence": "Прямые доказательства",
    "related_prior_memory": "Связанные прошлые исследования",
    "related_not_direct": (
        "Это контекст той же гипотезы. Он не усиливает текущий эксперимент."
    ),
    "decision_history": "История решений",
    "owner_decision": "Решение",
    "execution": "Выполнение",
    "decision": "Решение",
    "read_available": "чтение доступно",
    "write_unavailable": (
        "Запись решения на этой машине недоступна. Карточка остаётся "
        "только для чтения."
    ),
    "write_off": "запись недоступна",
    "write_available": "запись доступна",
    "record_decision": "Зафиксировать решение",
    "decision_recorded": "Решение записано и подтверждено readback.",
    "stale_next": "Форма ниже уже со свежим снимком — повторите решение.",
    "writer_busy_next": "Чтение карточки живо. Подождите и нажмите снова.",
    "unverified_next": "Не нажимайте повторно, пока история не покажет событие.",
    "current_object": "текущий объект",
    "trace": "TRACE",
    "rationale": "Пояснение (по-русски)",
    "next_condition": "Следующее условие (по-русски)",
    "promote_confirm": (
        "Понимаю: PROMOTE — только научное решение. StrategyVersion, "
        "PAPER/SHADOW/LIVE и деплой не создаются."
    ),
    "promote_blocked": "PROMOTE закрыт: не хватает обязательных доказательств",
    "snapshot": "Снимок доказательств",
    "no_direct": "Прямых доказательств нет",
    "no_related": "Связанных прошлых исследований нет",
    "no_decisions": "Решений ещё нет",
    "original_source": "оригинал источника",
    "legacy_en": "legacy EN",
    "handoff_title": "Переход в стратегию",
    "handoff_status": "Статус",
    "handoff_decision": "Научное решение",
    "handoff_frozen": "Что было зафиксировано в момент решения",
    "handoff_carries": "Что переносится в стратегию",
    "handoff_required": "Что ещё требуется",
    "handoff_blocked_why": "Почему переход заблокирован",
    "handoff_strategy": "Созданная StrategyVersion",
    "handoff_next": "Следующее безопасное действие",
    "handoff_not_started": "Что НЕ было запущено",
    "handoff_not_started_body": (
        "StrategyVersion не запускает PAPER, SHADOW, LIVE, бота, провайдера "
        "или кошелёк. Это только определение."
    ),
    "handoff_ready_copy": (
        "Научный переход готов. Для создания StrategyVersion нужен bounded Git "
        "materialization step."
    ),
    "handoff_frozen_present": (
        "Научные входы на момент решения заморожены в handoff-манифесте."
    ),
    "handoff_frozen_absent": "Замороженного handoff-манифеста нет.",
    "handoff_carries_science": (
        "population_ref, hypothesis и source_decision_asset_id из научного решения"
    ),
    "handoff_none": "Научного продвижения ещё нет.",
    "handoff_legacy": (
        "Старый PROMOTE без замороженного handoff. Текущие доказательства "
        "нельзя подставить вместо решения того момента."
    ),
    "handoff_execution_gap": (
        "Научное решение есть. Не хватает явных параметров исполнения/риска. "
        "Значения по умолчанию не подставляются."
    ),
    "handoff_materialized": "StrategyVersion уже есть. Ничего не запущено.",
    "handoff_conflict": "Конфликт содержимого. Существующую StrategyVersion нельзя перезаписать.",
    "handoff_machine": "Машинные идентификаторы",
}

OBLIGATION_LABELS = {
    "FALSIFIER": "Фальсификатор",
    "PIT_AVAILABILITY": "PIT / доступность",
    "POPULATION_N": "Популяция / N",
    "MISSINGNESS": "Пропуски",
    "SURVIVAL": "Выживаемость",
    "HOLDOUT": "Holdout",
    "ENTRY_EXECUTABILITY": "Исполняемость входа",
    "EXIT_EXECUTABILITY": "Исполняемость выхода",
    "COST_EVIDENCE": "Доказательства издержек",
    "RESULT": "Результат",
    "UNCERTAINTY": "Неопределённость",
    "ROBUSTNESS": "Устойчивость",
    "EVIDENCE_CLASS": "Класс доказательств",
}

DECISION_KIND_LABELS = {
    "REJECT": "Отклонить",
    "REVISE": "Доработать",
    "PAUSE": "Пауза",
    "PROMOTE": "Научно продвинуть",
}

HANDOFF_STATE_LABELS = {
    "NOT_PROMOTED": "Нет научного продвижения",
    "BLOCKED": "Переход заблокирован",
    "READY_TO_MATERIALIZE": "Готово к StrategyVersion",
    "MATERIALIZED": "StrategyVersion создана",
    "CONFLICT": "Конфликт",
}

BLOCKER_LABELS = {
    "LEGACY_PROVENANCE_GAP": "Нет замороженного решения того момента",
    "HANDOFF_MANIFEST_INVALID": "Handoff-манифест недействителен",
    "EXPERIMENT_SPEC_BINDING_GAP": "Нет привязки ExperimentSpec на момент решения",
    "EVIDENCE_RELATION_GAP": "Нет явной связи с доказательствами",
    "EVIDENCE_HASH_CONFLICT": "Хеш доказательств не совпадает с решением",
    "EXECUTION_INPUT_GAP": "Нет явных параметров исполнения/риска",
    "STRATEGY_IDENTITY_CONFLICT": "Конфликт идентификатора стратегии",
    "STRATEGY_CONTENT_CONFLICT": "Конфликт содержимого StrategyVersion",
    "SOURCE_UNAVAILABLE": "Исходный ResearchStore сейчас недоступен",
}

UNKNOWN_CANONICAL = frozenset(
    {
        "UNKNOWN",
        "MISSING",
        "EMPTY",
        "EXPLICIT_UNKNOWN",
        "UNAVAILABLE",
        "NOT_PRESENT",
    }
)

VERDICT_GLOSS = {
    "UNHEALTHY_NOT_RUNNING": "процесс не запущен",
    "UNHEALTHY_VERSION_MISSING": "версия не найдена",
    "UNHEALTHY_EVIDENCE_MISSING": "нет Git-доказательств",
    "DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN": "деградирован",
    "RUNTIME_PROVED_BACKUP_UNKNOWN": "процесс доказан, бэкап неизвестен",
    "UNAVAILABLE": "недоступен",
    "UNKNOWN": "неизвестно",
}

BACKUP_GLOSS = {
    "EXPLICIT_UNKNOWN": "не подтверждён",
    "UNKNOWN": "неизвестно",
}

ROLLBACK_GLOSS = {
    "PRESENT": "есть",
    "MISSING": "отсутствует",
    "UNKNOWN": "неизвестно",
}

NEXT_ACTION_GLOSS = {
    "INSPECT_SYSTEM": "Откройте экран Система",
    "RESOLVE_MISSING_EVIDENCE": "Восстановите недостающие Git-доказательства",
    "RUN_RUNTIME_PROOFS": "Запустите runtime proofs",
    "DO_NOT_PROMOTE": "Не продвигать в стратегию",
    "NO_SCIENTIFIC_PROMOTE": "Научного продвижения ещё нет — ничего не делать",
    "SUPPLY_EXPLICIT_EXECUTION_INPUTS": (
        "Нужен bounded шаг с явными параметрами исполнения/риска"
    ),
    "DO_NOT_RECONSTRUCT_DECISION_TIME_EVIDENCE": (
        "Не восстанавливать доказательства того момента из текущих записей"
    ),
    "FAIL_CLOSED_INVALID_MANIFEST": "Handoff-манифест недействителен — не материализовать",
    "FAIL_CLOSED_EVIDENCE_HASH_CONFLICT": "Конфликт хеша доказательств — не материализовать",
    "RESOLVE_RESEARCH_STORE": "Восстановить доступ к ResearchStore",
    "INSPECT_HANDOFF_BLOCKER": "Разобрать указанный blocker перехода",
    "BOUNDED_GIT_MATERIALIZATION_STEP": (
        "Научный переход готов. Для создания StrategyVersion нужен bounded Git "
        "materialization step."
    ),
    "INSPECT_STRATEGY_VERSION_NO_ACTIVATION": (
        "StrategyVersion уже есть. Не запускать PAPER/SHADOW/LIVE."
    ),
    "DO_NOT_OVERWRITE_STRATEGY_VERSION": (
        "Конфликт содержимого. Существующую StrategyVersion нельзя перезаписать."
    ),
    "OBSERVE": "Наблюдать",
    "INSPECT_ACTIVATION_PATH_GAP": (
        "Не считать бота запущенным; активация здесь не создаётся"
    ),
    "WAIT_DRAIN": "Ждать, пока инвентарь не будет drain-cleared",
    "RESUME_WHEN_NOT_DRAINING": "RESUME_NEW_ENTRIES, если статус не DRAINING",
    "INSPECT_MARK": "Смотреть evidence марки; UNKNOWN — не ноль",
    "REQUEST_CLOSE_OR_WAIT_EXIT": (
        "REQUEST_CLOSE_POSITION или ждать observation выхода"
    ),
    "KEEP_DRAINING": "Оставить DRAINING; STOPPED при неразрешённом инвентаре запрещён",
    "DO_NOT_BOOTSTRAP": "Не создавать runtime чтением; команда закрывается fail-closed",
    "INSPECT_VERSION_GAP": "Не сливать Git-версию с этим BotInstance",
    "INSPECT_REASON_CODE": "Смотреть reason_code; не выводить fill",
    "USE_EXPLICIT_IDENTITY": "Использовать события с явной identity",
    "DO_NOT_INVENT_WATCHLIST": "Не изобретать watchlist storage",
    "REVIEW_PAUSE_CLOSE_POLICY": "Просмотреть политику pause/close",
}

STATUS_GLOSS = {
    "PRESENT": "есть",
    "MISSING": "нет данных",
    "UNKNOWN": "неизвестно",
    "CONFLICT": "конфликт",
    "NOT_APPLICABLE": "не применимо",
    "EMPTY": "пусто",
    "KNOWN": "известно",
    "AVAILABLE": "доступен",
    "INVALID": "недействителен",
    "NOT_PRESENT": "отсутствует",
    "PARTIAL": "частично",
}

KIND_LABELS = {
    "DECISION": "Решение",
    "EXPERIMENT_SPEC": "Эксперимент",
    "EXPERIMENT": "Эксперимент",
    "TRIAL": "Проверка",
    "NEGATIVE_RESULT": "Отрицательный результат",
    "HYPOTHESIS": "Гипотеза",
    "SOURCE": "Источник",
}

SHELL_COPY = {
    "note": (
        "Локальная проекция. UI не владеет научной истиной. "
        "Команды на экране не подставляют owner phrase и не вызывают Jupiter."
    ),
    "copy": "Копировать",
    "copied": "Скопировано",
    "technical": "Технические детали",
    "full_legacy": "Полный исходный текст",
    "copy_hint": (
        "Справа кнопка «Копировать». START на этой странице фразу не подставляет "
        "и Jupiter не вызывает."
    ),
    "safe_state": "Сейчас безопасно: отдельных срочных действий нет.",
    "generic_error": "Источник вернул ошибку. Точный текст сохранён в технических деталях.",
}

SURFACE_COPY = {
    "HOME": {
        "h1": "Главная",
        "question": "Что сейчас действительно требует моего внимания?",
        "attention": "Что требует внимания",
        "known": "Что известно",
        "next": "Следующее безопасное действие",
        "phrase": "Точные команды владельца",
        "cycle_commands": "Технические команды цикла",
        "packet": "Пакет / признаки",
        "features": "Требуемые признаки",
        "health": "Вердикт runtime",
        "recent": "Недавние изменения",
        "no_attention": "Отдельных пунктов внимания нет.",
        "no_recent": "Недавних событий исполнения нет.",
        "phrase_not_urgent": (
            "Фраза ниже — точный текст для чата, не срочная кнопка этого экрана."
        ),
    },
    "RESEARCH": {
        "h1": "Исследования",
        "question": "Что мы проверяем / что знаем / что мне решать?",
        "sources": "Источники проекции",
    },
    "OPERATIONS": {
        "h1": "Операции",
        "question": "Что исполняется, где остановился путь и что безопасно сделать?",
        "now": "Сейчас",
        "summary": "Сводка",
        "bots": "Боты",
        "strategies_bots": "Стратегии / боты",
        "trace": "Signal → Risk → Execution",
        "counts": "Счётчики",
        "positions": "Позиции",
        "positions_exit": "Позиции / Exit / Reconciliation",
        "attention": "Требует внимания",
        "recent": "Недавние изменения",
        "commands": "Допустимые действия",
        "no_bots": "Нет runtime-ботов.",
        "no_positions": "Нет позиций.",
        "no_attention": "Пунктов внимания нет.",
        "no_recent": "Недавних событий исполнения нет.",
        "no_traces": "Нет доказанного пути Signal → Risk → Execution.",
        "need_one_bot": "Команды оператора требуют ровно один экземпляр бота.",
        "source_absent": "Источник runtime отсутствует. Это не пустая здоровая система.",
        "not_present": "PaperPlane отсутствует (NOT_PRESENT).",
        "activation_gap": "StrategyVersion есть в Git, активации/бота нет.",
        "not_activated": "не активировано",
        "git_definition": "Git-определение",
        "runtime_bot": "Runtime-бот",
        "activation_path": "Активация здесь не создаётся (ACTIVATION_PATH_GAP).",
        "watchlist": "Watchlist",
        "last_command": "Результат команды",
        "readback": "Ниже — свежая проекция runtime, не HTTP 200.",
        "no_start": "Команд активации PAPER/SHADOW на этом экране нет.",
        "bots_count": "Боты",
        "open_positions": "Открытые позиции",
        "entries_paused": "Новые входы",
        "paused": "приостановлены",
        "not_paused": "не приостановлены",
        "exit_required": "Требуется выход",
        "unresolved": "Неразрешённые",
        "pause_entries": "Приостановить новые входы",
        "resume_entries": "Возобновить новые входы",
        "close_one": "Закрыть одну позицию",
        "close_all": "Закрыть все позиции",
        "stop_bot": "Остановить бота",
        "confirm_close_all": "Подтверждаю REQUEST_CLOSE_ALL против показанного снимка открытых позиций",
        "bulk": "Массовые / стоп (локальное подтверждение)",
        "position_id": "position_id",
        "idempotency": "idempotency_key",
        "snapshot": "Снимок открытых позиций",
        "machine": "Machine detail",
        "target": "Цель",
        "precondition": "Предусловие",
        "expected": "Ожидаемый эффект",
        "fail_closed": "Fail-closed",
        "stop_stage": "Где путь остановился",
        "select_bot": "Выберите BotInstance",
        "source_unavailable": "Runtime файл есть, но прочитать его нельзя (RUNTIME_SOURCE_UNAVAILABLE).",
        "open_risk": "Открытый риск",
        "unknown_positions": "UNKNOWN",
        "pnl_unknown": "PnL UNKNOWN",
        "next_observe": "Наблюдать",
        "next_inspect_activation": "Не считать бота запущенным; активация здесь не создаётся",
        "next_wait_drain": "Ждать, пока инвентарь не будет drain-cleared",
        "next_resume": "RESUME_NEW_ENTRIES, если статус не DRAINING",
        "next_inspect_mark": "Смотреть evidence марки; UNKNOWN — не ноль",
        "next_close_or_wait": "REQUEST_CLOSE_POSITION или ждать observation выхода",
        "next_keep_draining": "Оставить DRAINING; STOPPED при неразрешённом инвентаре запрещён",
        "next_do_not_bootstrap": "Не создавать runtime чтением; команда закрывается fail-closed",
        "next_inspect_version": "Не сливать Git-версию с этим BotInstance",
        "next_inspect_reason": "Смотреть reason_code; не выводить fill",
        "next_use_identity": "Использовать события с явной identity",
        "next_no_watchlist": "Не изобретать watchlist storage",
    },
    "ECONOMICS": {
        "h1": "Экономика",
        "question": "Есть ли уже экономический результат и насколько ему можно доверять?",
        "pnl": "Подтверждённый PnL",
        "evidence": "Класс доказательств",
        "known_count": "Известных",
        "unknown_count": "Неизвестных",
        "exposure": "Открытая экспозиция",
        "drawdown": "Просадка",
        "streak": "Серия убытков",
        "non_claims": "Явные non-claims",
        "all_unknown": "Экономический результат сейчас неизвестен. Это не ноль.",
        "not_zero": "Отсутствующие live-метрики не показываются как $0.",
        "model": "Модель PAPER/SHADOW",
    },
    "SYSTEM": {
        "h1": "Система",
        "question": "Система сейчас в каком состоянии и что не доказано?",
        "process": "Процесс",
        "process_up": "запущен",
        "process_down": "не запущен",
        "backup": "Бэкап",
        "backup_unproven": "не подтверждён",
        "rollback": "Rollback snapshot",
        "rollback_missing": "отсутствует",
        "verdict": "Общий статус",
        "next": "Следующее действие",
        "not_healthy": "Запущенный процесс не означает, что система исправна.",
        "deployed": "Развёрнутая версия",
        "runtime": "Точные runtime-значения",
    },
}

ATTENTION_LABELS = {
    "WHY_NOW": "Почему сейчас",
    "IMPACT": "Влияние",
    "EVIDENCE": "Доказательства",
    "NEXT_SAFE_ACTION": "Следующее безопасное действие",
}

COMMAND_LABELS = {
    "PAUSE_NEW_ENTRIES": "Приостановить новые входы",
    "RESUME_NEW_ENTRIES": "Возобновить новые входы",
    "REQUEST_CLOSE_POSITION": "Закрыть одну позицию",
    "REQUEST_CLOSE_ALL": "Закрыть все позиции",
    "STOP_BOT": "Остановить бота",
    "FREEZE": "Заморозить",
    "START": "Старт",
    "STOP": "Стоп",
    "PARK": "Парковка",
    "RECORD_DECISION": "Записать решение",
}

FIELD_LABELS = {
    "QUESTION": "Вопрос",
    "ESTIMAND": "Оценка (estimand)",
    "POPULATION": "Популяция",
    "FALSIFIER": "Фальсификатор",
    "METHOD": "Метод",
    "HOLDOUT POLICY": "Политика holdout",
    "result": "Результат",
    "TERMINAL OUTCOMES": "Терминальные исходы",
    "DATA REQUIREMENTS": "Требования к данным",
    "CAPABILITIES": "Capabilities",
    "NEXT SAFE ACTION": "Следующее безопасное действие",
    "STATE": "Состояние",
    "TRUTH PLANE": "Плоскость истины",
    "EVIDENCE CLASS": "Класс доказательств",
    "SOURCE": "Источник",
    "AS OF": "На момент",
    "OBSERVED AT": "Наблюдено",
    "FRESHNESS": "Свежесть",
}

OWNER_ERRORS = {
    "STALE_EVIDENCE_SNAPSHOT": (
        "Снимок доказательств устарел. Решение не записано. "
        "Форма ниже уже со свежим снимком — повторите."
    ),
    "WRITER_BUSY": (
        "ResearchStore сейчас занят другим писателем. Решение не записано. "
        "Чтение карточки живо. Подождите и нажмите снова."
    ),
    "DECISION_WRITE_UNVERIFIED": (
        "Запись могла пройти, но readback не подтвердил событие. "
        "Повтор не выполняется. Смотрите историю, не нажимайте снова."
    ),
    "PROMOTE_BLOCKED": "Научный PROMOTE закрыт: не хватает обязательных доказательств.",
    "PROMOTE_BOUNDARY_CONFIRMATION_REQUIRED": (
        "Для PROMOTE нужно явное подтверждение: это только наука, "
        "не StrategyVersion."
    ),
    "WRITE_UNAVAILABLE": "Запись решения на этой машине недоступна.",
    "DECISION_KIND_REJECTED": "Этот вид решения здесь не предлагается.",
    "FILTER_REJECTED": "Фильтр отклонён. Сбросьте поиск или выберите значение из списка.",
    "QUERY_TOO_LONG": "Слишком длинный поиск. Укоротите запрос.",
    "LIMIT_REJECTED": "Недопустимый limit.",
    "LOCATOR_AMBIGUOUS": "Локатор неоднозначен. Нужны entity_id, плоскость и native_kind.",
    "LOCATOR_INCOMPLETE": "Неполный локатор объекта.",
    "LOCATOR_REJECTED": "Локатор отклонён.",
    "LOCATOR_NOT_IN_PROJECTION": "Объект не найден в текущей проекции.",
    "COMMAND_NOT_ALLOWLISTED": "Команда не из списка разрешённых.",
    "COMMAND_PATH_INVALID": "Эта команда на этом экране недоступна.",
    "CLOSE_ALL_CONFIRMATION_REQUIRED": (
        "Нужно локальное подтверждение CLOSE_ALL. Команда не отправлена."
    ),
    "BOT_INSTANCE_ID_REQUIRED": "Нужен bot_instance_id. Команда не отправлена.",
    "STALE_OPERATOR_SNAPSHOT": "Снимок оператора устарел. Команда не отправлена.",
    "SOURCE_NOT_PRESENT": (
        "PaperPlane отсутствует. Команда не выполнена и runtime не создан."
    ),
    "RUNTIME_SOURCE_UNAVAILABLE": (
        "Runtime файл есть, но прочитать его нельзя. Команда не выполнена."
    ),
    "RESEARCH_STORE_NOT_PRESENT": "ResearchStore на этой машине отсутствует.",
}

DEFAULT_RATIONALE = {
    "REJECT": "Отклонить по текущему снимку доказательств.",
    "REVISE": "Нужна доработка гипотезы или эксперимента.",
    "PAUSE": "Пауза: решение отложено.",
    "PROMOTE": (
        "Научное продвижение по текущему снимку. StrategyVersion не создаётся."
    ),
}

FORBIDDEN_RESEARCH_FIXED_LABELS = (
    "ACTIVE NOW",
    "Needs attention",
    "Current activity",
    "Research universe",
    "DIRECT EVIDENCE",
    "RELATED PRIOR MEMORY",
    "WHAT WAS TESTED",
    "DECISION HISTORY",
    "OWNER DECISION",
    "<th>kind</th>",
    "<th>title</th>",
    "<p class=\"empty\">NONE</p>",
    "CURRENT OBJECT",
    "Git definitions",
)


def nav_label(surface: str) -> str:
    return NAV_LABELS.get(surface, surface)


def counter_label(key: str) -> str:
    return COUNTER_LABELS.get(key, key)


def research_copy(key: str) -> str:
    return RESEARCH_COPY.get(key, key)


def obligation_label(code: str) -> str:
    return OBLIGATION_LABELS.get(code, code)


def decision_kind_label(kind: str) -> str:
    return DECISION_KIND_LABELS.get(kind, kind)


def handoff_state_label(state: str) -> str:
    return HANDOFF_STATE_LABELS.get(state, state)


def blocker_label(code: str) -> str:
    return BLOCKER_LABELS.get(code, code)


def field_label(key: str) -> str:
    return FIELD_LABELS.get(key, key)


def status_display(status: str) -> str:
    canonical = str(status or "UNKNOWN")
    gloss = STATUS_GLOSS.get(canonical)
    if gloss:
        return f"{gloss} ({canonical})"
    return canonical


def owner_error(code: str, details: str | None = None) -> str:
    message = OWNER_ERRORS.get(code, "Команда не выполнена.")
    suffix = f" ({code})"
    if details and details != code:
        return f"{message}{suffix}: {details}"
    return f"{message}{suffix}"


def surface_copy(surface: str, key: str) -> str:
    block = SURFACE_COPY.get(surface) or {}
    return str(block.get(key) or key)


def shell_copy(key: str) -> str:
    return SHELL_COPY.get(key, key)


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


def attention_label(key: str) -> str:
    return ATTENTION_LABELS.get(key, key)


def command_label(value: str) -> str:
    return COMMAND_LABELS.get(value, value)


def status_gloss(status: str) -> str | None:
    return STATUS_GLOSS.get(str(status or "UNKNOWN"))


def token_gloss(
    table: Mapping[str, str],
    value: Any,
    *,
    empty: str = "UNKNOWN",
) -> tuple[str, str, bool]:
    if value is None or value == "":
        canonical = empty
    else:
        canonical = str(value)
    gloss = table.get(canonical) or ""
    unknown = canonical in UNKNOWN_CANONICAL
    return gloss, canonical, unknown
