"""Offline park of RC001 H13 from priority while retaining frozen science."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ATOM_ID = "RC001-H13-PARK-FROM-PRIORITY-OFFLINE-V1"
OWNER_DECISION = "PARK_H13_FROM_PRIORITY"
TERMINAL_OUTCOMES = (
    "H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
    "H13_PARK_PREREQUISITES_DRIFT",
)
H13_GROUP_ID = "RC001-H13-COMPOSITE-VETO"
H13_DEFINITION_SHA256 = "f1f020f4fa79acd2f2de667d71b8002d5821f45e9070a0f259c63210b23a16d0"
H13_BLOCKER_CODES = (
    "ENTITY_ROUTE_NOT_ADMISSIBLE",
    "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
    "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
)
H02_GROUP_ID = "RC001-H02-H10-H14-PULLBACK-RECLAIM"
H02_DEFINITION_SHA256 = "fc225417541570aa73814a4cb992f6f801a84bea1baf15696d754c706e0aa9f8"
H02_BLOCKER_CODES = (
    "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
    "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
)
TASK24_STOP_RELATIVE = (
    "docs/evidence/task24/a6_bounded_data_redesign_or_stop_decision_v1.json"
)
TASK24_STOP_SHA256 = "442350624eef0625da3415692c48d2544c4d46c8edd21c5b7051098f7501d455"
TASK28_ACCEPTANCE_RELATIVE = (
    "docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json"
)
TASK28_ACCEPTANCE_SHA256 = (
    "4292df639605f3a6e10c6c02c1b5d1fc63ca3883269d904db323bc42916594f4"
)
TASK28_FREEZE_RELATIVE = "configs/task28_rc001_registry_freeze_v1.yaml"
TASK28_FREEZE_SHA256 = "c4fbb7157a13d1dee0f2b1f163e8f8fc1a38da4bc850275fba25bc0d70a785a7"
H07_H01_PARK_RELATIVE = (
    "docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json"
)
H07_H01_PARK_SHA256 = (
    "b85ee3ff0a7553014977613c624f2295fee3082f7f6c9f5ddf4fa3d6fb64aa42"
)
TRIAL_LEDGER_RELATIVE = "registries/global_trial_ledger.yaml"
RETURN_TRIGGER = (
    "NEW_EXACT_CONTRACT_WITH_EXPLICIT_OWNER_DECISION_AND_SEPARATE_ADMISSIBLE_"
    "ENTITY_PIT_AND_SETTLED_EXECUTION_EVIDENCE"
)
RETURN_PREREQUISITES = {
    "group_id": H13_GROUP_ID,
    "definition_sha256": H13_DEFINITION_SHA256,
    "unresolved_blocker_codes": list(H13_BLOCKER_CODES),
    "required_authority": "NEW_EXACT_CONTRACT_WITH_EXPLICIT_OWNER_DECISION",
}
FORBIDDEN_FOLLOW_ONS = (
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "ENTITY_ROUTE_REDESIGN_OR_CAPTURE",
    "CONTINUOUS_PIT_OR_EXECUTION_CAPTURE",
    "H07_H01_UNPARK",
    "PROVIDER_OR_CREDENTIAL_CALL",
)


class H13ParkError(ValueError):
    """A frozen H13 prerequisite cannot be reconciled fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise H13ParkError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise H13ParkError(code) from exc


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H13ParkError(code) from exc
    return dict(_mapping(value, code))


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    import yaml

    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise H13ParkError(code) from exc
    return dict(_mapping(value, code))


def _group(freeze: Mapping[str, Any], group_id: str, code: str) -> Mapping[str, Any]:
    groups = _sequence(freeze.get("hypothesis_groups"), "RC001_GROUPS_INVALID")
    for candidate in groups:
        group = _mapping(candidate, "RC001_GROUP_INVALID")
        if group.get("group_id") == group_id:
            return group
    raise H13ParkError(code)


def _admissibility(group: Mapping[str, Any], code: str) -> Mapping[str, Any]:
    return _mapping(group.get("expected_admissibility"), code)


def _blocker_codes(group: Mapping[str, Any], code: str) -> list[str]:
    admissibility = _admissibility(group, code)
    return [str(item) for item in _sequence(admissibility.get("blocker_codes"), code)]


def _bind_task24_stop(repo_root: Path) -> dict[str, Any]:
    path = repo_root / TASK24_STOP_RELATIVE
    observed_sha = _sha256_file(path, "TASK24_STOP_RECEIPT_UNREADABLE")
    _require(observed_sha == TASK24_STOP_SHA256, "TASK24_STOP_RECEIPT_DRIFT")
    receipt = _load_json(path, "TASK24_STOP_RECEIPT_INVALID")
    partial = _mapping(
        receipt.get("partial_asset_disposition"),
        "TASK24_PARTIAL_ASSET_DISPOSITION_INVALID",
    )
    _require(
        receipt.get("owner_decision") == "STOP_NO_RELIABLE_ENTITY_SIGNAL",
        "TASK24_STOP_DECISION_DRIFT",
    )
    _require(
        partial.get("downstream_decision_admissibility") == "NOT_ADMISSIBLE",
        "TASK24_ENTITY_ROUTE_ADMISSIBILITY_DRIFT",
    )
    return {
        "path": TASK24_STOP_RELATIVE,
        "sha256": observed_sha,
        "owner_decision": receipt["owner_decision"],
        "entity_route_status": partial["downstream_decision_admissibility"],
    }


def _bind_task28_freeze(repo_root: Path) -> dict[str, Any]:
    acceptance_path = repo_root / TASK28_ACCEPTANCE_RELATIVE
    acceptance_sha = _sha256_file(acceptance_path, "TASK28_ACCEPTANCE_UNREADABLE")
    _require(acceptance_sha == TASK28_ACCEPTANCE_SHA256, "TASK28_RC001_FREEZE_DRIFT")
    acceptance = _load_json(acceptance_path, "TASK28_ACCEPTANCE_INVALID")
    cycle = _mapping(acceptance.get("research_cycle"), "TASK28_RESEARCH_CYCLE_INVALID")
    acceptance_groups = _mapping(cycle.get("groups"), "TASK28_ACCEPTANCE_GROUPS_INVALID")
    acceptance_h13 = _mapping(
        acceptance_groups.get(H13_GROUP_ID), "TASK28_ACCEPTANCE_H13_GROUP_MISSING"
    )
    _require(
        acceptance_h13.get("state") == "BLOCKED_DATA",
        "TASK28_ACCEPTANCE_H13_STATE_DRIFT",
    )
    _require(
        list(acceptance_h13.get("blocker_codes") or []) == list(H13_BLOCKER_CODES),
        "H13_BLOCKER_SET_DRIFT",
    )
    _require(cycle.get("trial_record_count_created_by_task28") == 0, "H13_TRIAL_STARTED")
    _require(cycle.get("holdout_consumed") is False, "H13_HOLDOUT_CONSUMED")

    freeze_path = repo_root / TASK28_FREEZE_RELATIVE
    freeze_sha = _sha256_file(freeze_path, "TASK28_FREEZE_UNREADABLE")
    _require(freeze_sha == TASK28_FREEZE_SHA256, "TASK28_RC001_FREEZE_DRIFT")
    freeze = _load_yaml(freeze_path, "TASK28_FREEZE_INVALID")
    h13 = _group(freeze, H13_GROUP_ID, "H13_GROUP_MISSING")
    h02 = _group(freeze, H02_GROUP_ID, "H02_GROUP_MISSING")
    _require(h13.get("order") == 1, "H13_ORDER_DRIFT")
    _require(h13.get("definition_sha256") == H13_DEFINITION_SHA256, "H13_DEFINITION_DRIFT")
    _require(_admissibility(h13, "H13_ADMISSIBILITY_INVALID").get("state") == "BLOCKED_DATA", "H13_STATE_DRIFT")
    _require(_blocker_codes(h13, "H13_BLOCKERS_INVALID") == list(H13_BLOCKER_CODES), "H13_BLOCKER_SET_DRIFT")
    _require(h02.get("order") == 3, "H02_ORDER_DRIFT")
    _require(h02.get("definition_sha256") == H02_DEFINITION_SHA256, "H02_DEFINITION_DRIFT")
    _require(_admissibility(h02, "H02_ADMISSIBILITY_INVALID").get("state") == "BLOCKED_DATA", "H02_STATE_DRIFT")
    _require(_blocker_codes(h02, "H02_BLOCKERS_INVALID") == list(H02_BLOCKER_CODES), "H02_STATE_DRIFT")
    return {
        "acceptance_path": TASK28_ACCEPTANCE_RELATIVE,
        "acceptance_sha256": acceptance_sha,
        "freeze_path": TASK28_FREEZE_RELATIVE,
        "freeze_sha256": freeze_sha,
        "h13_definition_sha256": h13["definition_sha256"],
        "h13_order": h13["order"],
        "h13_state": _admissibility(h13, "H13_ADMISSIBILITY_INVALID")["state"],
        "h13_blocker_codes": _blocker_codes(h13, "H13_BLOCKERS_INVALID"),
        "h02_definition_sha256": h02["definition_sha256"],
        "h02_order": h02["order"],
        "h02_state": _admissibility(h02, "H02_ADMISSIBILITY_INVALID")["state"],
        "h02_blocker_codes": _blocker_codes(h02, "H02_BLOCKERS_INVALID"),
        "trial_record_count_created_by_task28": cycle["trial_record_count_created_by_task28"],
        "holdout_consumed": cycle["holdout_consumed"],
    }


def _bind_h07_h01_park(repo_root: Path) -> dict[str, Any]:
    path = repo_root / H07_H01_PARK_RELATIVE
    observed_sha = _sha256_file(path, "H07_H01_PARK_RECEIPT_UNREADABLE")
    _require(observed_sha == H07_H01_PARK_SHA256, "H07_H01_PARK_RECEIPT_DRIFT")
    receipt = _load_json(path, "H07_H01_PARK_RECEIPT_INVALID")
    _require(
        receipt.get("decision")
        == "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        "H07_H01_PARK_DECISION_DRIFT",
    )
    _require(
        receipt.get("priority_disposition") == "PARKED_FROM_PRIORITY",
        "H07_H01_PARK_PRIORITY_DRIFT",
    )
    _require(receipt.get("science_disposition") == "RETAINED", "H07_H01_SCIENCE_DRIFT")
    return {
        "path": H07_H01_PARK_RELATIVE,
        "sha256": observed_sha,
        "decision": receipt["decision"],
        "priority_disposition": receipt["priority_disposition"],
        "science_disposition": receipt["science_disposition"],
    }


def _bind_current_rc001_lifecycle(repo_root: Path) -> dict[str, Any]:
    trial_ledger_path = repo_root / TRIAL_LEDGER_RELATIVE
    trial_ledger_sha256 = _sha256_file(
        trial_ledger_path, "TRIAL_LEDGER_UNREADABLE"
    )
    trial_ledger = _load_yaml(trial_ledger_path, "TRIAL_LEDGER_INVALID")
    trial_ledger_as_of = trial_ledger.get("as_of")
    _require(isinstance(trial_ledger_as_of, str), "TRIAL_LEDGER_AS_OF_INVALID")
    trial_records = _sequence(
        trial_ledger.get("records"), "TRIAL_LEDGER_RECORDS_INVALID"
    )
    rc001_trial_record_ids: list[str] = []
    for item in trial_records:
        record = _mapping(item, "TRIAL_LEDGER_RECORD_INVALID")
        record_id = record.get("record_id")
        hypothesis_id = record.get("hypothesis_id")
        if (
            isinstance(record_id, str)
            and record_id.startswith("TRIAL-RC001")
        ) or hypothesis_id in {
            "DEF-RC001-H13-COMPOSITE-VETO-V1",
            "DEF-RC001-H02-H10-H14-PULLBACK-RECLAIM-V1",
        }:
            _require(isinstance(record_id, str), "TRIAL_LEDGER_RECORD_ID_INVALID")
            rc001_trial_record_ids.append(record_id)
    _require(not rc001_trial_record_ids, "RC001_TRIAL_RECORD_FORBIDDEN")

    return {
        "path": TRIAL_LEDGER_RELATIVE,
        "sha256": trial_ledger_sha256,
        "as_of": trial_ledger_as_of,
        "rc001_trial_record_ids": rc001_trial_record_ids,
    }


def decide_park_terminal(result: Mapping[str, Any]) -> str:
    side_effects = _mapping(result.get("side_effects"), "SIDE_EFFECTS_INVALID")
    trial_ledger = _mapping(result.get("trial_ledger"), "TRIAL_LEDGER_RESULT_INVALID")
    if (
        result.get("owner_decision") != OWNER_DECISION
        or result.get("priority_disposition") != "PARKED_FROM_PRIORITY"
        or result.get("science_disposition") != "RETAINED"
        or result.get("deletion") is not False
        or result.get("hypothesis_verdict") != "NOT_REFUTED_NOT_SUPPORTED"
        or result.get("h13_state") != "BLOCKED_DATA"
        or list(result.get("h13_blocker_codes") or []) != list(H13_BLOCKER_CODES)
        or result.get("h07_h01_park_decision")
        != "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED"
        or result.get("h02_state") != "BLOCKED_DATA"
        or result.get("h02_started") is not False
        or result.get("next_family_selection") != "NONE_THIS_ATOM"
        or result.get("return_trigger") != RETURN_TRIGGER
        or dict(result.get("return_prerequisites") or {}) != RETURN_PREREQUISITES
        or list(result.get("forbidden_follow_ons") or [])
        != list(FORBIDDEN_FOLLOW_ONS)
        or list(trial_ledger.get("rc001_trial_record_ids") or []) != []
        or not isinstance(trial_ledger.get("sha256"), str)
        or not isinstance(trial_ledger.get("as_of"), str)
        or side_effects.get("provider_requests") != 0
        or side_effects.get("credential_reads") != 0
        or side_effects.get("cash_spend_usd_cents") != 0
        or side_effects.get("network_requests") != 0
        or side_effects.get("wallet_signer_transaction_actions") != 0
        or side_effects.get("execution_attempts") != 0
    ):
        return "H13_PARK_PREREQUISITES_DRIFT"
    return "H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED"


def bind_h13_park_from_priority(repo_root: Path) -> dict[str, Any]:
    task24 = _bind_task24_stop(repo_root)
    freeze = _bind_task28_freeze(repo_root)
    h07_h01 = _bind_h07_h01_park(repo_root)
    lifecycle = _bind_current_rc001_lifecycle(repo_root)
    result = {
        "atom_id": ATOM_ID,
        "owner_decision": OWNER_DECISION,
        "priority_disposition": "PARKED_FROM_PRIORITY",
        "science_disposition": "RETAINED",
        "deletion": False,
        "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
        "family_status": "PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE",
        "task24_stop": task24,
        "task28_freeze": freeze,
        "h07_h01_park": h07_h01,
        "h13_state": freeze["h13_state"],
        "h13_blocker_codes": freeze["h13_blocker_codes"],
        "h07_h01_park_decision": h07_h01["decision"],
        "h02_state": freeze["h02_state"],
        "h02_started": False,
        "next_family_selection": "NONE_THIS_ATOM",
        "return_trigger": RETURN_TRIGGER,
        "return_prerequisites": {
            **RETURN_PREREQUISITES,
            "unresolved_blocker_codes": list(H13_BLOCKER_CODES),
        },
        "forbidden_follow_ons": list(FORBIDDEN_FOLLOW_ONS),
        "trial_ledger": lifecycle,
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "cash_spend_usd_cents": 0,
            "network_requests": 0,
            "wallet_signer_transaction_actions": 0,
            "execution_attempts": 0,
        },
        "project_sources_disposition": {"kind": "NO_CHANGE"},
    }
    result["terminal"] = decide_park_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    task24 = _mapping(result.get("task24_stop"), "TASK24_STOP_RESULT_INVALID")
    freeze = _mapping(result.get("task28_freeze"), "TASK28_FREEZE_RESULT_INVALID")
    h07_h01 = _mapping(result.get("h07_h01_park"), "H07_H01_PARK_RESULT_INVALID")
    forbidden = "\n".join(
        f"- `{item}`" for item in result.get("forbidden_follow_ons") or []
    )
    return (
        "# RC001 — H13 паркуем с приоритета, науку не удаляем\n"
        "\n"
        f"**Терминальное решение:** `{result.get('terminal')}`\n"
        f"**Решение владельца:** `{result.get('owner_decision')}`\n"
        "\n"
        "Это **снятие H13 с живого приоритета фабрики**, а не опровержение "
        "гипотезы, не подтверждение, не canonical DONE, не alpha и не "
        "разрешение собирать данные или платить за них.\n"
        "\n"
        "## Что припарковано\n"
        "\n"
        f"- family: `{H13_GROUP_ID}`\n"
        f"- priority: `{result.get('priority_disposition')}`\n"
        f"- science: `{result.get('science_disposition')}` (удаление: "
        f"`{str(result.get('deletion')).lower()}`)\n"
        f"- hypothesis verdict: `{result.get('hypothesis_verdict')}`\n"
        f"- family status: `{result.get('family_status')}`\n"
        "\n"
        "## Почему\n"
        "\n"
        "H13 остаётся `BLOCKED_DATA`: entity route не пригоден для "
        "downstream decision, непрерывной PIT-цены нет, settled execution "
        "truth нет. Продолжение без нового exact-контракта превратило бы "
        "неизвестность в иллюзию evidence.\n"
        "\n"
        f"- TASK-24: `{task24.get('owner_decision')}`, entity route: "
        f"`{task24.get('entity_route_status')}`\n"
        f"- TASK-28 H13: `{result.get('h13_state')}` — "
        f"`{', '.join(result.get('h13_blocker_codes') or [])}`\n"
        f"- definition SHA-256: `{freeze.get('h13_definition_sha256')}`\n"
        "\n"
        "## Что с другими RC001 семьями\n"
        "\n"
        f"- H07/H01 historical A27 receipt: `{h07_h01.get('decision')}`; "
        "этот атом не делает unpark\n"
        f"- H02/H10/H14: `{result.get('h02_state')}`; H02/H10/H14 автоматически не стартует.\n"
        "- Этот атом не выбирает следующую RC001 семью.\n"
        "\n"
        "## Когда можно вернуться к H13\n"
        "\n"
        "Только после новой точной owner-задачи, а не по календарю, recency "
        "или частичному кешу:\n"
        f"`{result.get('return_trigger')}`\n"
        "\n"
        f"- group: `{result.get('return_prerequisites', {}).get('group_id')}`\n"
        f"- frozen definition: `{result.get('return_prerequisites', {}).get('definition_sha256')}`\n"
        "- обязательно закрыть каждый исходный blocker: "
        f"`{', '.join(result.get('return_prerequisites', {}).get('unresolved_blocker_codes') or [])}`\n"
        "\n"
        "## Что этим атомом не делается\n"
        "\n"
        f"{forbidden}\n"
        "\n"
        "Нет provider/network/credential/wallet/cash side effects. Этот "
        "атом не меняет RC001 freeze и не запускает trial.\n"
    )
