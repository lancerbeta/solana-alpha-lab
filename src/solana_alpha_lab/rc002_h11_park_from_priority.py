"""Offline park of RC002 H11 from priority, retaining science.

Wraps the public cohort-eligibility binder. Does not mutate the pinned
TASK-08 decoder, TASK-36/37/40 science receipts, TASK-37 clock yaml, or
the trial ledger. Park is not a hypothesis verdict.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.rc002_h11_cohort_eligibility_after_task40_close import (
    bind_cohort_eligibility_after_task40_close,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
)

ATOM_ID = "RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1"
AUTHORITY_PHRASE = "H11 паркуем"
COHORT_TERMINAL = "H11_COHORT_NOT_READY_SCREEN_FORBIDDEN"
TASK36_TERMINAL = "HISTORICAL_ROUTE_INADEQUATE_REPLAN"
TASK37_TERMINAL = "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
COHORT_ACCEPTANCE_RELATIVE = (
    "docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/"
    "a1_cohort_eligibility_after_task40_close_acceptance_v1.json"
)
EXPECTED_COHORT_ACCEPTANCE_SHA256 = (
    "c9658b93697f26678cb3d53db3fecfade895163ff8205c71beddfa8b0809957a"
)
TERMINAL_OUTCOMES = (
    "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
    "H11_PARK_PREREQUISITES_DRIFT",
)
RETURN_TRIGGER = (
    "NEW_EXACT_CONTRACT_FOR_SAMPLE_CAMPAIGN_BRIEF_EIGHT_PLUS_POOLS_"
    "BONDING_CURVE_OR_MINT_HISTORY_OLDER_COMPLETE_MIGRATION_LAYOUT_"
    "RETROSPECTIVE_PEAK_PATH_AND_900S_OUTCOMES_WITH_COST_CAP_AND_"
    "STOP_IF_METHOD_FAILS_ON_SECOND_IDENTITY"
)
FORBIDDEN_FOLLOW_ONS = (
    "ONE_MINT_DECODE_RESUME",
    "MORE_CREATES_OPTION_C",
    "POOL_GTA_REPLAY",
    "PINNED_DECODER_MINT_OR_BONDING_CURVE_GTA",
    "H11_EFFECT_SCREEN_RERUN",
    "LOWER_MINIMA_8_2_2",
    "COHORT_READY_FROM_N1",
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "PAID_CAPTURE_ON_FALSIFIED_ROUTES",
    "CALENDAR_ELAPSED_UNPARK",
)


class H11ParkError(ValueError):
    """A prerequisite receipt cannot be bound fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise H11ParkError(code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise H11ParkError(code) from exc


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H11ParkError(code) from exc
    return dict(_mapping(document, code))


def decide_park_terminal(result: Mapping[str, Any]) -> str:
    if (
        result.get("owner_phrase") != AUTHORITY_PHRASE
        or result.get("named_mint") != EXPECTED_NAMED_MINT
        or result.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or result.get("cohort_terminal") != COHORT_TERMINAL
        or result.get("task36_terminal") != TASK36_TERMINAL
        or result.get("task36_n") != 0
        or result.get("task37_capture_terminal") != TASK37_TERMINAL
        or result.get("effect_screen_eligible") is not False
        or result.get("cohort_acceptance_sha256") != EXPECTED_COHORT_ACCEPTANCE_SHA256
        or result.get("return_trigger") != RETURN_TRIGGER
        or list(result.get("forbidden_follow_ons") or []) != list(FORBIDDEN_FOLLOW_ONS)
        or result.get("calendar_elapsed_is_return_trigger") is not False
        or result.get("hypothesis_verdict") != "NOT_REFUTED_NOT_SUPPORTED"
        or result.get("priority_disposition") != "PARKED_FROM_PRIORITY"
        or result.get("science_disposition") != "RETAINED"
        or result.get("deletion") is not False
    ):
        return "H11_PARK_PREREQUISITES_DRIFT"
    return "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED"


def bind_h11_park_from_priority(repo_root: Path) -> dict[str, Any]:
    cohort = bind_cohort_eligibility_after_task40_close(repo_root)
    cohort_path = repo_root / COHORT_ACCEPTANCE_RELATIVE
    receipt = _load_json(cohort_path, "COHORT_ACCEPTANCE_INVALID")
    observed_sha = _sha256_file(cohort_path, "COHORT_ACCEPTANCE_UNREADABLE")
    if (
        cohort.get("terminal") != COHORT_TERMINAL
        or receipt.get("terminal") != COHORT_TERMINAL
        or cohort.get("named_mint") != EXPECTED_NAMED_MINT
        or receipt.get("named_mint") != EXPECTED_NAMED_MINT
        or cohort.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or receipt.get("bonding_curve") != EXPECTED_BONDING_CURVE
        or observed_sha != EXPECTED_COHORT_ACCEPTANCE_SHA256
    ):
        raise H11ParkError("COHORT_ACCEPTANCE_DRIFT")
    result = {
        "owner_phrase": AUTHORITY_PHRASE,
        "named_mint": cohort["named_mint"],
        "bonding_curve": cohort["bonding_curve"],
        "cohort_terminal": cohort["terminal"],
        "task36_terminal": cohort["task36_terminal"],
        "task36_n": cohort["task36_n"],
        "task37_capture_terminal": cohort["task37_capture_terminal"],
        "effect_screen_eligible": cohort["effect_screen_eligible"],
        "create_at_status": cohort["create_at_status"],
        "migration_at": cohort["migration_at"],
        "reconstructed_units": cohort["reconstructed_units"],
        "required_units": cohort["required_units"],
        "priority_disposition": "PARKED_FROM_PRIORITY",
        "science_disposition": "RETAINED",
        "deletion": False,
        "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
        "family_status": "PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE",
        "return_trigger": RETURN_TRIGGER,
        "forbidden_follow_ons": list(FORBIDDEN_FOLLOW_ONS),
        "calendar_elapsed_is_return_trigger": False,
        "h13_or_h02_started": False,
        "paid_capture_authorized": False,
        "cohort_acceptance": COHORT_ACCEPTANCE_RELATIVE,
        "cohort_acceptance_sha256": observed_sha,
        "consumer": "RC002-H11-LIFECYCLE-CLOCK",
        "research_cycle_id": "RESEARCH-CYCLE-RC002-001",
        "hypothesis_id": "HYP-RC002-H11-LIFECYCLE-CLOCK-V1",
    }
    result["terminal"] = decide_park_terminal(result)
    if result["terminal"] != "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED":
        result["migration_at"] = None
        result["create_at_status"] = None
        result["reconstructed_units"] = None
        result["required_units"] = None
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    units = dict(result.get("reconstructed_units") or {})
    required = dict(result.get("required_units") or {})
    forbidden = "\n".join(f"- `{item}`" for item in result.get("forbidden_follow_ons") or [])
    return (
        "# RC002 — H11 паркуем с приоритета, науку не удаляем\n"
        "\n"
        f"**Терминальное решение:** `{result.get('terminal')}`\n"
        f"**Фраза владельца:** `{result.get('owner_phrase')}`\n"
        "\n"
        "Это **снятие H11 с живого приоритета фабрики**, а не опровержение "
        "гипотезы, не подтверждение, не canonical DONE, не alpha и не "
        "разрешение платить за данные.\n"
        "\n"
        "## Что именно припарковано\n"
        "\n"
        f"- гипотеза: `{result.get('hypothesis_id')}`\n"
        f"- цикл: `{result.get('research_cycle_id')}`\n"
        f"- consumer: `{result.get('consumer')}`\n"
        f"- приоритет: `{result.get('priority_disposition')}`\n"
        f"- наука: `{result.get('science_disposition')}` (удаление: "
        f"`{str(result.get('deletion')).lower()}`)\n"
        f"- вердикт по гипотезе: `{result.get('hypothesis_verdict')}`\n"
        f"- family status: `{result.get('family_status')}`\n"
        "\n"
        "Экран H11 **не бежал** на живой вселенной: TASK-36 остаётся "
        f"`{result.get('task36_terminal')}`, `n={result.get('task36_n')}`. "
        "Это не `H11_SCREEN_NEGATIVE` и не "
        "`H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION`.\n"
        "\n"
        "## Почему так\n"
        "\n"
        "Цель владельца — быстрее и качественнее product-market fit: "
        "короткое окно 15 минут–4 часа, где видно цену, можно коснуться "
        "рынка и понять деньги после издержек. H11 отвечает на другой "
        "вопрос (добавляют ли часы после миграции информацию сверх "
        "времени суток). Даже идеальный PASS экрана даёт только право "
        "*потом* проверять это вперёд — не стратегию и не выручку.\n"
        "\n"
        "Дешёвый уже лежащий кэш (история PumpSwap pool) структурно не "
        "содержит Create/CompletePumpAmmMigration. Один mint после "
        "офлайн-разбора дал "
        f"{units.get('pools')} pool / {units.get('days')} days / "
        f"{units.get('deployers')} deployers против минимума "
        f"{required.get('pools')} / {required.get('days')} / "
        f"{required.get('deployers')}. `create_at` остаётся "
        f"`{result.get('create_at_status')}`. Второго признака экрана "
        "(running peak) нет. Effect screen запрещён.\n"
        "\n"
        "Доделывать этот mint или платить за уже опровергнутые маршруты "
        "не приближает PMF.\n"
        "\n"
        "## Что остаётся истинным (не переписывать)\n"
        "\n"
        f"- TASK-36: `{result.get('task36_terminal')}`, n=0, trial "
        "INCONCLUSIVE\n"
        f"- TASK-37 capture: `{result.get('task37_capture_terminal')}`, "
        "trial INCONCLUSIVE; определения часов заморожены\n"
        f"- cohort after TASK-40 close: `{result.get('cohort_terminal')}`\n"
        f"- mint: `{result.get('named_mint')}`\n"
        f"- bonding_curve: `{result.get('bonding_curve')}`\n"
        f"- migration_at bound: `{result.get('migration_at')}`\n"
        "- TASK-39/40 science receipts и pinned decoder не менялись\n"
        "- trial ledger не менялся\n"
        "\n"
        "## Стоит ли вернуться к H11?\n"
        "\n"
        "Только по **новой точной фразе** и **новому exact-контракту**. "
        "Календарь сам по себе не триггер "
        f"(`calendar_elapsed_is_return_trigger="
        f"{str(result.get('calendar_elapsed_is_return_trigger')).lower()}`).\n"
        "\n"
        "### Возвращаться когда\n"
        "\n"
        f"`{result.get('return_trigger')}`\n"
        "\n"
        "Иными словами: владелец отдельно авторизует бриф кампании "
        "выборки (ещё не оплату), который сразу называет ≥8 "
        "outcome-independent pools, историю bonding_curve или mint "
        "(не pool GTA), layout Complete/Migration который уже consume-ится "
        "на retained A4, ретроспективный price path для peak, исходы 900s, "
        "кап стоимости и stop «метод падает на 2-й identity».\n"
        "\n"
        "### Не возвращаться когда\n"
        "\n"
        f"{forbidden}\n"
        "\n"
        "H13 и H02 сами не оживают: в TASK-28 они `BLOCKED_DATA` (нет "
        "непрерывной PIT-цены и settled execution). Этот атом их не "
        "стартует "
        f"(`h13_or_h02_started="
        f"{str(result.get('h13_or_h02_started')).lower()}`).\n"
        "\n"
        "## Что этим атомом не делается\n"
        "\n"
        "- paid capture / второй провайдер "
        f"(`paid_capture_authorized="
        f"{str(result.get('paid_capture_authorized')).lower()}`)\n"
        "- rerun H11 effect screen "
        f"(`effect_screen_eligible="
        f"{str(result.get('effect_screen_eligible')).lower()}`)\n"
        "- PMF-контур цены и исполнения (нужна отдельная фраза)\n"
        "- canonical DONE / PIT / alpha / cashflow\n"
        "\n"
        "Следующий ход после merge этот атом не выбирает.\n"
    )
