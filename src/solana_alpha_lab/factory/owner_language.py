"""Russian-first owner presentation. Owns no scientific or machine truth."""

from __future__ import annotations

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
    "full_legacy": "Полный исходный текст (legacy EN)",
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
        "health": "Краткий статус системы",
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
        "question": "Что работает, какой риск открыт и что я могу безопасно сделать?",
        "summary": "Сводка",
        "bots": "Боты",
        "counts": "Счётчики",
        "positions": "Позиции",
        "attention": "Внимание",
        "recent": "Недавние изменения",
        "commands": "Команды оператора",
        "no_bots": "Нет ботов.",
        "no_positions": "Нет позиций.",
        "no_attention": "Пунктов внимания нет.",
        "no_recent": "Недавних событий исполнения нет.",
        "need_one_bot": "Команды оператора требуют ровно один экземпляр бота.",
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
        "process_down": "не подтверждён",
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
