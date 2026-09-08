"""Russian-first owner presentation. Owns no scientific or machine truth."""

from __future__ import annotations

from typing import Any, Mapping

PRESENTATION_LANGUAGE = "RU"
MACHINE_LANGUAGE = "EN"

NAV_LABELS = {
    "HOME": "Главная",
    "RESEARCH": "Исследования",
    "MARKET": "Рынок",
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
    "col_evidence_class": "класс evidence",
    "col_as_of": "на момент",
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
    "OPEN_OPERATIONS": "Открыть Операции",
    "OPEN_RESEARCH": "Открыть Исследования",
    "OPEN_SYSTEM": "Открыть Систему",
    "MARK_HOME_REVIEWED": "Отметить просмотр Главной",
    "LEAVE_UNATTENDED": "Можно оставить без вмешательства — при текущем покрытии",
    "FOLLOW_UNATTENDED_TIMER_RECOVERY": "Таймер не active — смотрите unattended runbook, не SSH сами",
    "FOLLOW_UNATTENDED_WORKBENCH_RECOVERY": "Workbench unit не active — смотрите unattended runbook",
    "FOLLOW_DEPLOY_BOUNDARY": "Deploy SHA не совпадает с Git HEAD — смотрите remote-host runbook",
    "FOLLOW_STORAGE_RUNWAY_RECOVERY": "Диск/runway — смотрите storage в unattended runbook",
    "FOLLOW_DURABILITY_RUNBOOK": "Backup/off-host/archive — смотрите durability в unattended runbook",
    "INSPECT_COLLECTOR_FRESHNESS": "Сбор устарел или застрял — смотрите collector freshness",
    "INSPECT_COVERAGE_GAPS": "Покрытие неполное. UNKNOWN/NOT_PRESENT — это не «всё чисто»",
    "INSPECT_ACCOUNTING_EVIDENCE": "Смотреть исходные gross/fee/net; конфликт не пересчитывать",
    "INSPECT_POSITION_EVIDENCE": "Смотреть mark/qty/fee компоненты позиции",
    "INSPECT_OPERATIONS": "Открыть Операции; /economics команд не даёт",
    "INSPECT_EVIDENCE_SCOPES": "Смотреть PAPER и SHADOW раздельно, не складывать",
    "WAIT_FOR_RECONCILED_EVIDENCE": "Ждать reconciled evidence; отсутствие — не ноль",
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
    "UNAVAILABLE": "недоступен",
    "NOT_CONFIGURED": "не настроено",
    "CONFIGURED": "настроено, доставка не доказана",
    "DEGRADED": "деградировано",
    "ACTION_REQUIRED": "нужно действие",
    "OK_OBSERVED": "наблюдается как работающее",
    "SERVING": "этот HTTP сейчас отвечает",
    "SERVING_NOW": "этот HTTP сейчас отвечает",
    "MATCH": "совпадает",
    "MISMATCH": "не совпадает",
    "COMPARABLE": "сопоставима",
    "HIGH_RELATIVE": "выше недавней истории",
    "LOW_RELATIVE": "ниже недавней истории",
    "MID_RELATIVE": "в середине недавней истории",
    "CURRENT_SCOPE_MIXED": "смешаны разные текущие scope",
    "REFERENCE_SCOPE_MISMATCH": "история несопоставима",
    "COVERAGE_INSUFFICIENT": "покрытие недостаточно",
    "REFERENCE_INSUFFICIENT": "мало сопоставимой истории",
    "SCHEDULE_SEMANTICS_MISSING": "нет семантики расписания",
    "MEMBER_EVIDENCE_INCOMPLETE": "неполный список выборки",
    "SOURCE_NOT_PRESENT": "отсутствует",
    "NO_CURRENT_OBSERVATIONS": "нет текущих наблюдений",
    "OBSERVATION_PARTITION_MISSING": "нет файла observation partition",
    "OBSERVATION_PARTITION_UNREADABLE": "не читается observation partition",
    "GIT_CAPABILITY": "Git-доступность, не live market",
    "PIT_CLOCK_MISSING": "нет PIT-часов",
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
        "question": "Что требует меня сейчас, и что стало новым с просмотра?",
        "attention": "Требует внимания",
        "changed": "Изменилось с просмотра",
        "info_changes": "Изменения без действия",
        "coverage": "Полнота источников",
        "known": "Сводка Factory",
        "next": "Следующее безопасное действие",
        "phrase": "Точные команды владельца",
        "cycle_commands": "Технические команды цикла",
        "packet": "Пакет / признаки",
        "features": "Требуемые признаки",
        "health": "Покрытие источников, не вердикт healthy",
        "recent": "Недавние изменения",
        "no_attention": "Сейчас нет пункта, который требует Петра.",
        "no_changed": "Новых событий с просмотра не показано.",
        "no_info": "Нет изменений без действия.",
        "mark_reviewed": "Отметить просмотр",
        "do_nothing": "Ничего делать не нужно.",
        "new_since_review": "НОВОЕ С ПРОСМОТРА",
        "open_source": "Открыть источник",
        "coverage_source": "Источник",
        "coverage_state": "Состояние",
        "coverage_history": "История изменений",
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
        "unknown_positions": "Позиции UNKNOWN",
        "pnl_unknown": "PnL неизвестен",
        "mode": "Режим",
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
        "question": "Что доказано экономически, где UNKNOWN, и чего из цифр нельзя заключать?",
        "proven": "Что доказано",
        "state": "Состояние evidence",
        "pnl": "Reconciled net (один совместимый scope)",
        "net": "Модельный net после комиссий",
        "marked_net": "Open-mark net после комиссий",
        "evidence": "Класс доказательств",
        "mode": "Mode",
        "status": "Статус scope",
        "known_count": "Известных",
        "unknown_count": "Неизвестных / конфликт",
        "exposure": "Entered notional",
        "drawdown": "Просадка model-PnL",
        "streak": "Серия убытков",
        "fee_coverage": "Покрытие modeled fees",
        "fcf": "Owner FCF",
        "netreturn": "NetReturn",
        "reconciled": "Сведённая экономика",
        "open_mark": "Open-mark экономика",
        "mark_subordinate": "Open mark — as-of оценка, не settled cash. Не складывается со сведённой.",
        "declared_risk": "Объявленный риск входа",
        "strategy_binding": "StrategyVersion",
        "entry_limit": "max_open_positions",
        "headroom": "Оставшиеся entry slots",
        "daily_loss": "Daily loss limit",
        "capital_limit": "Capital limit",
        "dd_limit": "Drawdown limit",
        "capacity": "Capacity",
        "coverage_h": "Покрытие / UNKNOWN",
        "real_cost": "Total real trading cost",
        "freshness": "Mark freshness policy",
        "mark_as_of": "mark_as_of",
        "mark_age": "mark_age_seconds",
        "settled": "Settlement",
        "not_included": "Что не учтено",
        "not_included_body": (
            "Priority fee, failed tx, MEV, route impact, retry, latency, RPC, "
            "infrastructure, operator time, tax и owner cash settlement здесь не считаются."
        ),
        "next": "Следующее безопасное действие",
        "no_reconciled": "Нет reconciled rows.",
        "no_marks": "Нет open marks.",
        "no_risk": "Нет bot/policy readback.",
        "mixed": "Несколько несовместимых evidence scopes. Это не одна сумма.",
        "inventory_ops": "Unresolved / EXIT inventory остаётся на Операциях.",
        "open_operations": "Открыть Операции",
        "non_claims": "Явные non-claims",
        "all_unknown": "Экономический результат сейчас неизвестен. Это не ноль.",
        "not_zero": "Отсутствующие live-метрики не показываются как $0.",
        "model": "RiskEconomicsProjectionV1 — model evidence, не LIVE cash",
        "machine": "Точные machine-значения",
    },
    "SYSTEM": {
        "h1": "Система",
        "question": "Можно ли сейчас оставить Factory технически работать без меня?",
        "now": "Сейчас",
        "attention": "Требует внимания",
        "collection": "Сбор и свежесть",
        "processes": "Процессы и таймеры",
        "storage": "Хранилище и runway",
        "durability": "Backup / off-host / архив",
        "deploy": "Идентичность deploy",
        "alerting": "Инцидент / alert",
        "coverage": "Покрытие",
        "next": "Следующее безопасное действие",
        "machine": "Точные machine-значения",
        "process": "Процесс",
        "process_up": "запущен",
        "process_down": "не запущен",
        "backup": "Бэкап",
        "backup_unproven": "не подтверждён",
        "rollback": "Rollback snapshot",
        "rollback_missing": "отсутствует",
        "verdict": "Общий статус",
        "not_healthy": "Запущенный HTTP-процесс не означает, что система исправна.",
        "deployed": "Развёрнутая версия",
        "runtime": "Точные runtime-значения",
        "http_self": "HTTP сейчас",
        "managed_unit": "Управляемый unit",
        "no_attention": "Сейчас нет системных пунктов, которые требуют Петра.",
        "unknown_attention": "Пунктов внимания нет, но покрытие неполное — это не «можно оставить».",
        "authority_yes": "Нужен агент / не SSH и не systemctl сами.",
        "authority_no": "Маршрут описательный, кнопок мутации здесь нет.",
        "leave": "Можно оставить без вмешательства — при текущем покрытии.",
        "residual": "Workbench не может сам увидеть смерть своего VPS.",
    },
    "MARKET": {
        "h1": "Рынок",
        "question": (
            "Какой контекст сейчас наблюдается в моей торгуемой части рынка, "
            "насколько он отличается от недавней сопоставимой истории, "
            "насколько этот вывод покрыт данными, и что из этого нельзя заключать?"
        ),
        "now": "Контекст сейчас",
        "matrix": "Матрица возраста",
        "default_detail": "Деталь 30м",
        "coverage": "Покрытие и пропуски",
        "scope": "Scope, источник и as-of",
        "capability": "Какие данные Factory может использовать",
        "capability_note": (
            "Это Git-доступность признаков, не текущие рыночные значения."
        ),
        "non_claims": "Что это не означает",
        "machine": "Точные machine-значения",
        "unknown_why": "Почему UNKNOWN",
        "relative": "Относительно недавней сопоставимой истории",
        "raw": "Сырое значение",
        "as_of": "На момент",
        "latest": "Последняя доступность evidence",
        "population": "Популяция",
        "not_all_market": "Это не весь рынок Solana / memecoin / pump.fun.",
        "system_link": "Свежесть runtime → Система",
        "research_link": "Исследования",
        "operations_link": "Операции",
        "economics_link": "Экономика",
        "no_source": "Источник immutable market evidence сейчас отсутствует. LOW не выдуман.",
        "no_current_detail": (
            "Текущего контекста нет: источник evidence отсутствует. "
            "LOW не выдуман. HIGH/LOW на этом экране не читать."
        ),
        "mismatch": (
            "История несопоставима с текущим контекстом. Сырые значения видны, "
            "относительная полоса закрыта. HIGH/LOW читать нельзя."
        ),
        "mixed": (
            "Смешаны разные текущие scope. Сырые значения и покрытие не смешиваются. "
            "HIGH/LOW читать нельзя."
        ),
        "incomplete_members": (
            "Список выборки за исторические дни неполный. HIGH/LOW читать нельзя."
        ),
        "no_current": (
            "В текущем окне нет допущенных наблюдений. LOW не выдуман."
        ),
        "gaps": "Пробелы",
        "interpretation": "Что это означает как context",
        "vector": "Вектор осей, не один regime score.",
        "high_means": (
            "HIGH_RELATIVE значит только: выше недавней сопоставимой истории. "
            "Не return и не trade."
        ),
        "tested": "Проверенная привязка стратегии к context",
        "sampling": "Политика выборки",
        "compat": "context_compatibility_sha256",
        "snapshot": "context_snapshot_sha256",
        "n_obs": "N observed",
        "n_metric": "N metric",
        "n_scope": "N in scope",
        "missing": "missing / censored / excluded",
        "coverage_point": "Возраст",
        "coverage_axis": "Ось",
        "coverage_classes": "Классы покрытия",
        "coverage_missing": "Пропуски",
        "coverage_fraction": "Доля observed",
        "unit": "Единица",
        "reference": "Статус сопоставления",
        "source": "Статус источника",
        "freshness": "Возраст evidence — это не здоровье collector.",
        "leave": "Необычный context сам по себе не требует действия.",
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

AXIS_UNITS = {
    "USD": "USD",
    "TRADERS": "трейдеры",
    "UP_SHARE": "доля UP",
    "BALANCE": "баланс",
}

COVERAGE_CLASS_LABELS = {
    "observed": "наблюдено",
    "typed_missing": "typed missing",
    "disappeared": "исчезло",
    "censored": "цензура",
    "capacity_excluded": "capacity excluded",
    "sampling_excluded": "sampling excluded",
    "x_ineligible": "X-ineligible",
    "unknown": "unknown",
}

NONCLAIM_LABELS = {
    "NO_MARKET_WIDE_CLAIM": "Это не весь рынок",
    "NO_EXPECTED_RETURN": "Не ожидаемая доходность",
    "NO_TRADE_OR_NO_TRADE": "Не сигнал trade / no-trade",
    "NO_BULL_BEAR_OR_COMPOSITE_REGIME": "Не BULL/BEAR и не composite regime",
    "NO_TESTED_STRATEGY_CONTEXT_BINDING": "Нет проверенной привязки стратегии",
    "NO_BOT_AUTHORITY": "Нет команд боту",
    "NO_COLLECTOR_HEALTH_INFERENCE": "Не здоровье collector",
    "NO_ORCH_001": "Не ORCH-001",
    "NO_DISCOVERY_RANKER": "Не discovery ranker",
    "NO_PROVIDER": "Не вызов провайдера",
    "NO_DEPLOY": "Не deploy",
    "NO_LIVE_OR_WALLET": "Не LIVE и не wallet",
}

AXIS_LABELS = {
    "LIQUIDITY_LEVEL": "Ликвидность",
    "LIQUIDITY_BREADTH": "Ширина ликвидности",
    "PARTICIPATION": "Участие трейдеров",
    "BUY_SELL_ACTIVITY_BALANCE": "Баланс покупок/продаж",
    "PRICE_BREADTH": "Ширина цены",
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
    "MARKET_HAS_NO_COMMANDS": "Экран Рынок не отдаёт команд боту и не меняет runtime.",
    "COMMAND_PATH_INVALID": "Эта команда на этом экране недоступна.",
    "CLOSE_ALL_CONFIRMATION_REQUIRED": (
        "Нужно локальное подтверждение CLOSE_ALL. Команда не отправлена."
    ),
    "BOT_INSTANCE_ID_REQUIRED": "Нужен bot_instance_id. Команда не отправлена.",
    "STALE_OPERATOR_SNAPSHOT": "Снимок оператора устарел. Команда не отправлена.",
    "STALE_REVIEW_SNAPSHOT": "Снимок просмотра устарел. Курсор не записан.",
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


def axis_label(axis_id: str) -> str:
    return AXIS_LABELS.get(str(axis_id or ""), str(axis_id or ""))


def axis_unit_label(unit: str) -> str:
    return AXIS_UNITS.get(str(unit or ""), str(unit or ""))


def coverage_class_label(key: str) -> str:
    canonical = str(key or "")
    gloss = COVERAGE_CLASS_LABELS.get(canonical)
    if gloss and gloss != canonical:
        return f"{gloss} ({canonical})"
    return canonical


def nonclaim_label(code: str) -> str:
    canonical = str(code or "")
    gloss = NONCLAIM_LABELS.get(canonical)
    if gloss:
        return f"{gloss} ({canonical})"
    return canonical


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
