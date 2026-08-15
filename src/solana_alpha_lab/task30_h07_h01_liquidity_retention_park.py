"""Offline park of RC001 H07/H01 from priority, retaining A24/A25/A26 science.

TASK-30 A27 wraps the frozen A26 owner-fork packet. It never deletes
evidence, never mutates the RC001 freeze, and never starts a trial.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ATOM_ID = "T30-A27_RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION_V1"
SCHEMA = "smial.task30.h07-h01-liquidity-retention-park.policy"
RESULT_SCHEMA = "smial.task30.a27-h07-h01-liquidity-retention-park.result"
AUTHORITY_PHRASE = "OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION"
TERMINAL_OUTCOMES = (
    "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
    "STOP_INTEGRITY_CONFLICT",
)
SELECTED_FORK = "RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION"


class A27Error(ValueError):
    """Policy or packet identity is invalid."""


class A27IntegrityError(A27Error):
    """Frozen A26, retained evidence or RC001 freeze cannot be reconciled."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A27Error(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise A27IntegrityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return value


def _text(value: object, code: str) -> str:
    _require(isinstance(value, str) and value, code)
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    _require(policy.get("selected_fork") == SELECTED_FORK, "SELECTED_FORK_DRIFT")
    _require(policy.get("deletion") is False, "SCIENCE_DELETION_ATTEMPTED")
    _require(policy.get("priority_disposition") == "PARKED_FROM_PRIORITY", "PRIORITY_DISPOSITION_DRIFT")
    _require(policy.get("science_disposition") == "RETAINED", "SCIENCE_DISPOSITION_DRIFT")
    return policy


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(_mapping(document, code))


def bind_frozen_a26(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = _mapping(policy.get("frozen_a26"), "FROZEN_A26_SPEC_INVALID")
    path = repo_root / _text(spec.get("path"), "FROZEN_A26_PATH_INVALID")
    _integrity(path.is_file(), "A26_ACCEPTANCE_MISSING")
    payload = path.read_bytes()
    observed_sha = sha256_bytes(payload)
    _integrity(observed_sha == _text(spec.get("sha256"), "FROZEN_A26_SHA_INVALID"), "A26_ACCEPTANCE_HASH_DRIFT")
    document = dict(_mapping(json.loads(payload.decode("utf-8")), "A26_ACCEPTANCE_INVALID"))
    _integrity(
        document.get("decision") == spec.get("required_terminal"),
        "A26_TERMINAL_DRIFT",
    )
    _integrity(
        document.get("task_state") == spec.get("required_task_state"),
        "A26_TASK_STATE_DRIFT",
    )
    forks = _mapping(document.get("owner_forks"), "A26_OWNER_FORKS_INVALID")
    options = list(_sequence(forks.get("options"), "A26_OWNER_FORK_OPTIONS_INVALID"))
    option_ids = [
        _text(_mapping(item, "A26_FORK_OPTION_INVALID").get("option_id"), "A26_FORK_OPTION_ID_INVALID")
        for item in options
    ]
    _integrity(
        spec.get("required_selected_fork_option") in option_ids,
        "A26_RETIRE_OPTION_MISSING",
    )
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    _integrity(
        authority.get("owner_phrase") == AUTHORITY_PHRASE,
        "OWNER_PHRASE_DRIFT",
    )
    return {
        "path": spec["path"],
        "sha256": observed_sha,
        "decision": document["decision"],
        "task_state": document["task_state"],
        "encoded_selected": forks.get("selected"),
        "retire_option_present": True,
    }


def bind_retained_evidence(repo_root: Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    for item in _sequence(policy.get("retained_evidence"), "RETAINED_EVIDENCE_INVALID"):
        spec = _mapping(item, "RETAINED_EVIDENCE_ITEM_INVALID")
        relative = _text(spec.get("path"), "RETAINED_EVIDENCE_PATH_INVALID")
        path = repo_root / relative
        _integrity(path.is_file(), f"RETAINED_EVIDENCE_MISSING:{spec.get('asset_id')}")
        observed_sha = sha256_bytes(path.read_bytes())
        _integrity(
            observed_sha == _text(spec.get("sha256"), "RETAINED_EVIDENCE_SHA_INVALID"),
            f"RETAINED_EVIDENCE_HASH_DRIFT:{spec.get('asset_id')}",
        )
        retained.append(
            {
                "asset_id": spec["asset_id"],
                "path": relative,
                "sha256": observed_sha,
                "disposition": "RETAINED",
            }
        )
    _integrity(len(retained) == 3, "RETAINED_EVIDENCE_COUNT_DRIFT")
    return retained


def bind_rc001_freeze(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = _mapping(policy.get("rc001_freeze"), "RC001_FREEZE_SPEC_INVALID")
    _integrity(spec.get("mutation_authorized") is False, "RC001_FREEZE_MUTATION_AUTHORIZED")
    path = repo_root / _text(spec.get("path"), "RC001_FREEZE_PATH_INVALID")
    _integrity(path.is_file(), "RC001_FREEZE_MISSING")
    freeze = _load_yaml(path, "RC001_FREEZE_INVALID")
    groups = list(_sequence(freeze.get("hypothesis_groups"), "RC001_GROUPS_INVALID"))
    match = next(
        (
            dict(_mapping(group, "RC001_GROUP_INVALID"))
            for group in groups
            if group.get("group_id") == spec.get("group_id")
        ),
        None,
    )
    _integrity(match is not None, "RC001_H07_H01_GROUP_MISSING")
    assert match is not None
    _integrity(
        match.get("definition_sha256") == spec.get("required_definition_sha256"),
        "RC001_FREEZE_MUTATED",
    )
    return {
        "path": spec["path"],
        "group_id": spec["group_id"],
        "definition_sha256": match["definition_sha256"],
        "mutation_authorized": False,
        "admissibility_state": _mapping(
            match.get("expected_admissibility"), "RC001_ADMISSIBILITY_INVALID"
        ).get("state"),
    }


def refuse_forbidden_follow_ons(policy: Mapping[str, Any]) -> list[str]:
    forbidden = [
        _text(item, "FORBIDDEN_FOLLOW_ON_INVALID")
        for item in _sequence(policy.get("forbidden_follow_ons"), "FORBIDDEN_FOLLOW_ONS_INVALID")
    ]
    claims = _mapping(policy.get("claims"), "CLAIMS_INVALID")
    _integrity(claims.get("notional_buckets_frozen") is False, "NOTIONAL_BUCKETS_FROZEN")
    _integrity(claims.get("route_feasibility") is False, "ROUTE_FEASIBILITY_CAPTURE_AUTHORIZED")
    _integrity(claims.get("h13_trial") is False, "H13_OR_H02_TRIAL_STARTED")
    _integrity(claims.get("h02_trial") is False, "H13_OR_H02_TRIAL_STARTED")
    _integrity(claims.get("h07_h01_trial") is False, "H07_H01_TRIAL_STARTED")
    _integrity(claims.get("task30_canonical_done") is False, "TASK30_OR_RC001_PROMOTION")
    _integrity(claims.get("task30_acceptance") is False, "TASK30_OR_RC001_PROMOTION")
    _integrity(claims.get("rc001_definition_changed") is False, "RC001_FREEZE_MUTATED")
    _integrity(claims.get("science_deleted") is False, "SCIENCE_DELETION_ATTEMPTED")
    expected = [
        "FREEZE_NOTIONAL_BUCKET_SET_V1",
        "AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE",
        "ROUTE_FEASIBILITY_CAPTURE",
        "H13_TRIAL",
        "H02_H10_H14_TRIAL",
        "PROVIDER_PURCHASE",
    ]
    _integrity(forbidden == expected, "FORBIDDEN_FOLLOW_ON_SET_DRIFT")
    return forbidden


def execute_park(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    a26 = bind_frozen_a26(repo_root, policy)
    retained = bind_retained_evidence(repo_root, policy)
    freeze = bind_rc001_freeze(repo_root, policy)
    forbidden = refuse_forbidden_follow_ons(policy)
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "named_consumer": policy["consumer"],
        "terminal_decision": "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        "task_state": "BLOCKED_DATA",
        "family_status": "PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE",
        "selected_fork": SELECTED_FORK,
        "priority_disposition": "PARKED_FROM_PRIORITY",
        "science_disposition": "RETAINED",
        "deletion": False,
        "frozen_a26": a26,
        "retained_evidence": retained,
        "rc001_freeze": freeze,
        "forbidden_follow_ons": forbidden,
        "claims": dict(_mapping(policy.get("claims"), "CLAIMS_INVALID")),
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
        },
        "non_claims": [
            "NO_TASK30_ACCEPTANCE_OR_DONE",
            "NO_RC001_PROMOTION_OR_DEFINITION_CHANGE",
            "NO_SCIENCE_DELETION",
            "NO_H07_H01_TRIAL",
            "NO_H13_OR_H02_TRIAL",
            "NO_NOTIONAL_BUCKET_FREEZE",
            "NO_ROUTE_FEASIBILITY_CAPTURE",
            "NO_PROVIDER_CALL_OR_PURCHASE",
            "NO_ALPHA_EXECUTION_PNL_OR_NETRETURN",
        ],
        "project_sources_disposition": dict(
            _mapping(policy.get("project_sources_disposition"), "PROJECT_SOURCES_INVALID")
        ),
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    freeze = _mapping(result.get("rc001_freeze"), "FREEZE_RESULT_INVALID")
    a26 = _mapping(result.get("frozen_a26"), "A26_RESULT_INVALID")
    retained = list(_sequence(result.get("retained_evidence"), "RETAINED_RESULT_INVALID"))
    lines = [
        "# TASK-30 A27 — H07/H01 паркуем, науку не удаляем",
        "",
        f"**Терминальное решение:** `{result['terminal_decision']}`",
        "",
        "Это **снятие семьи с приоритета**, а не удаление evidence и не DONE.",
        "Фраза `RETIRE` здесь значит: закрыть будущее использование политикой,",
        "сохранив A24/A25/A26 в git.",
        "",
        "## Что зафиксировано",
        "",
        f"- выбранный форк A26: `{result['selected_fork']}`",
        f"- приоритет: `{result['priority_disposition']}`",
        f"- наука: `{result['science_disposition']}`",
        f"- удаление: `{str(result['deletion']).lower()}`",
        f"- замороженный терминал A26: `{a26['decision']}`",
        f"- `TASK-30` state: `{result['task_state']}`",
        f"- family status: `{result['family_status']}`",
        f"- RC001 group: `{freeze['group_id']}`",
        f"- RC001 definition SHA-256: `{freeze['definition_sha256']}`",
        f"- freeze mutation authorized: `{str(freeze['mutation_authorized']).lower()}`",
        "",
        "## Сохранённые evidence",
        "",
    ]
    for item in retained:
        record = _mapping(item, "RETAINED_ITEM_INVALID")
        lines.append(
            f"- `{record['asset_id']}` — `{record['sha256']}` — `{record['disposition']}`"
        )
    lines.extend(
        [
            "",
            "## Что этим атомом не делается",
            "",
        ]
    )
    for code in _sequence(result.get("forbidden_follow_ons"), "FORBIDDEN_RESULT_INVALID"):
        lines.append(f"- `{code}`")
    lines.extend(
        [
            "",
            "`TASK-30` остаётся `BLOCKED_DATA`. Это не DONE, не альфа и не cashflow.",
            "Следующая семья не стартует этим атомом.",
            "",
        ]
    )
    return "\n".join(lines)
