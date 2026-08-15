"""Offline proof that a $5 Helius one-shot cannot falsify frozen H07/H01.

TASK-30 A26 wraps the frozen A25 acceptance and the current provider-route
registry. It never calls a provider, never spends, and never guesses notionals.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import (
    validate_provider_route_capability_registry,
)
from solana_alpha_lab.provider_route_capability_registry_v6 import (
    validate_provider_route_capability_registry_v6,
)

ATOM_ID = "T30-A26_H07_H01_FIVE_DOLLAR_CANNOT_FALSIFY_OWNER_FORK_PACKET_V1"
SCHEMA = "smial.task30.h07-h01-owner-fork-packet.policy"
RESULT_SCHEMA = "smial.task30.a26-h07-h01-owner-fork-packet.result"
TERMINAL_OUTCOMES = (
    "FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY",
    "STOP_INTEGRITY_CONFLICT",
)
JUPITER_NEEDLES = ("JUPITER", "QUOTE")
ILLUSTRATIVE_N1_EVALUATIONS = 4 * 96 * 1


class A26Error(ValueError):
    """Policy or packet identity is invalid."""


class A26IntegrityError(A26Error):
    """Frozen A25, registry or reuse truth cannot be reconciled."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A26Error(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise A26IntegrityError(code)


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
    _require(list(policy.get("quote_operations") or []) == [], "QUOTE_OPERATIONS_MUST_BE_EMPTY")
    return policy


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(_mapping(document, code))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return dict(_mapping(document, code))


def bind_frozen_a25(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = _mapping(policy.get("frozen_a25"), "FROZEN_A25_SPEC_INVALID")
    path = repo_root / _text(spec.get("path"), "FROZEN_A25_PATH_INVALID")
    payload = path.read_bytes()
    observed_sha = sha256_bytes(payload)
    _integrity(observed_sha == _text(spec.get("sha256"), "FROZEN_A25_SHA_INVALID"), "A25_ACCEPTANCE_HASH_DRIFT")
    acceptance = json.loads(payload.decode("utf-8"))
    document = dict(_mapping(acceptance, "A25_ACCEPTANCE_INVALID"))
    _integrity(
        document.get("decision") == spec.get("required_terminal"),
        "A25_TERMINAL_DRIFT",
    )
    _integrity(
        document.get("task_state") == spec.get("required_task_state"),
        "A25_TASK_STATE_DRIFT",
    )
    precision = _mapping(document.get("precision_and_power"), "A25_PRECISION_INVALID")
    required = _mapping(document.get("required_data_specification"), "A25_DATA_SPEC_INVALID")
    parameters = _mapping(document.get("frozen_parameter_resolution"), "A25_PARAMETERS_INVALID")
    cluster = _mapping(policy.get("cluster_requirement"), "CLUSTER_SPEC_INVALID")
    _integrity(
        precision.get("independent_clusters") == cluster.get("frozen_independent_clusters"),
        "A25_CLUSTER_COUNT_DRIFT",
    )
    _integrity(
        required.get("minimum_clusters_for_two_group_cluster_level_test")
        == cluster.get("minimum_clusters_for_variance_calibration"),
        "A25_MINIMUM_CLUSTER_DRIFT",
    )
    _integrity(
        required.get("next_measurement_purpose") == cluster.get("next_measurement_purpose"),
        "A25_MEASUREMENT_PURPOSE_DRIFT",
    )
    notional = _mapping(parameters.get("NOTIONAL_BUCKET_SET_V1"), "A25_NOTIONAL_INVALID")
    expected_notional = _mapping(policy.get("notional_parameter"), "NOTIONAL_SPEC_INVALID")
    _integrity(notional.get("resolved") is False, "NOTIONAL_BUCKETS_ALREADY_RESOLVED")
    _integrity(
        notional.get("unresolved_code") == expected_notional.get("unresolved_code"),
        "NOTIONAL_UNRESOLVED_CODE_DRIFT",
    )
    _integrity(
        notional.get("non_adopted_observed_convention")
        == expected_notional.get("non_adopted_observed_convention"),
        "NOTIONAL_TASK21_CONVENTION_ADOPTED",
    )
    computability = _mapping(document.get("metric_computability"), "A25_COMPUTABILITY_INVALID")
    pit_survival = _mapping(computability.get("PIT_ROUTE_SURVIVAL"), "A25_PIT_ROUTE_INVALID")
    quote_availability = _mapping(computability.get("QUOTE_AVAILABILITY"), "A25_QUOTE_AVAILABILITY_INVALID")
    expected_fields = list(_sequence(policy.get("required_route_feasibility_fields"), "ROUTE_FIELDS_INVALID"))
    _integrity(
        pit_survival.get("missing_fields") == expected_fields,
        "A25_ROUTE_FIELD_SET_DRIFT",
    )
    _integrity(
        quote_availability.get("missing_fields") == expected_fields,
        "A25_QUOTE_FIELD_SET_DRIFT",
    )
    _integrity(
        pit_survival.get("computability") == "NOT_COMPUTABLE"
        and quote_availability.get("computability") == "NOT_COMPUTABLE",
        "A25_ROUTE_METRICS_NOW_COMPUTABLE",
    )
    return {
        "path": spec["path"],
        "sha256": observed_sha,
        "decision": document["decision"],
        "task_state": document["task_state"],
        "independent_clusters": precision["independent_clusters"],
        "minimum_clusters_for_variance_calibration": required[
            "minimum_clusters_for_two_group_cluster_level_test"
        ],
        "notional_bucket_count": required.get("notional_bucket_count"),
        "unresolved_frozen_parameters": list(required.get("unresolved_frozen_parameters") or []),
        "missing_route_feasibility_fields": expected_fields,
    }


def bind_registries(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    current_spec = _mapping(policy.get("current_registry"), "CURRENT_REGISTRY_SPEC_INVALID")
    predecessor_spec = _mapping(policy.get("predecessor_registry"), "PREDECESSOR_REGISTRY_SPEC_INVALID")
    current_path = repo_root / _text(current_spec.get("path"), "CURRENT_REGISTRY_PATH_INVALID")
    predecessor_path = repo_root / _text(predecessor_spec.get("path"), "PREDECESSOR_REGISTRY_PATH_INVALID")
    current = _load_yaml(current_path, "CURRENT_REGISTRY_INVALID")
    predecessor = _load_yaml(predecessor_path, "PREDECESSOR_REGISTRY_INVALID")
    routes = validate_provider_route_capability_registry_v6(current)
    predecessor_routes = validate_provider_route_capability_registry(predecessor)
    _integrity(len(routes) == current_spec.get("route_count"), "REGISTRY_ROUTE_COUNT_DRIFT")
    _integrity(current.get("registry_id") == current_spec.get("registry_id"), "CURRENT_REGISTRY_ID_DRIFT")
    _integrity(
        predecessor.get("registry_id") == predecessor_spec.get("registry_id"),
        "PREDECESSOR_REGISTRY_ID_DRIFT",
    )
    operations = sorted({_text(route.get("operation"), "ROUTE_OPERATION_INVALID") for route in routes})
    providers = sorted({_text(route.get("provider"), "ROUTE_PROVIDER_INVALID") for route in routes})
    route_ids = sorted({_text(route.get("route_id"), "ROUTE_ID_INVALID") for route in routes})
    helius_operations = sorted(
        _text(route.get("operation"), "HELIUS_OPERATION_INVALID")
        for route in routes
        if route.get("provider") == "HELIUS"
    )
    expected_helius = sorted(str(item) for item in _sequence(policy.get("helius_operations"), "HELIUS_OPS_INVALID"))
    _integrity(helius_operations == expected_helius, "HELIUS_OPERATION_SET_DRIFT")
    identity_blob = " ".join(route_ids + providers + operations).upper()
    for needle in JUPITER_NEEDLES:
        _integrity(needle not in identity_blob, f"ROUTE_FEASIBILITY_ROUTE_SILENTLY_INVENTED:{needle}")
    predecessor_blob = " ".join(
        sorted(
            _text(route.get("route_id"), "PREDECESSOR_ROUTE_ID_INVALID")
            + " "
            + _text(route.get("provider"), "PREDECESSOR_PROVIDER_INVALID")
            + " "
            + _text(route.get("operation"), "PREDECESSOR_OPERATION_INVALID")
            for route in predecessor_routes
        )
    ).upper()
    for needle in JUPITER_NEEDLES:
        _integrity(needle not in predecessor_blob, f"PREDECESSOR_ROUTE_FEASIBILITY_INVENTED:{needle}")
    return {
        "current_registry_id": current["registry_id"],
        "predecessor_registry_id": predecessor["registry_id"],
        "route_ids": route_ids,
        "providers": providers,
        "operations": operations,
        "helius_operations": helius_operations,
        "jupiter_or_quote_route_present": False,
        "route_feasibility_registry_status": "REGISTRY_GAP",
        "authority_granted": False,
    }


def bind_reuse_candidate(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = _mapping(policy.get("reuse_candidate"), "REUSE_SPEC_INVALID")
    records = _sequence(
        _load_yaml(repo_root / "registries/reuse_candidates.yaml", "REUSE_REGISTRY_INVALID").get("records"),
        "REUSE_RECORDS_INVALID",
    )
    match = next(
        (
            dict(_mapping(record, "REUSE_RECORD_INVALID"))
            for record in records
            if record.get("record_id") == spec.get("record_id")
        ),
        None,
    )
    _integrity(match is not None, "REUSE_CANDIDATE_MISSING")
    assert match is not None
    _integrity(match.get("verdict") == spec.get("verdict"), "REUSE_VERDICT_DRIFT")
    _integrity(
        match.get("decision_status") == spec.get("decision_status"),
        "REUSE_STATUS_DRIFT",
    )
    _integrity(spec.get("grants_quote_route") is False, "REUSE_CANNOT_GRANT_QUOTE_ROUTE")
    return {
        "record_id": spec["record_id"],
        "verdict": match["verdict"],
        "decision_status": match["decision_status"],
        "grants_quote_route": False,
    }


def assess_spend(
    policy: Mapping[str, Any],
    a25: Mapping[str, Any],
    registries: Mapping[str, Any],
) -> dict[str, Any]:
    spend = _mapping(policy.get("proposed_spend"), "SPEND_SPEC_INVALID")
    cluster = _mapping(policy.get("cluster_requirement"), "CLUSTER_SPEC_INVALID")
    reasons = [
        "WRONG_LANE_HELIUS_IS_TRADE_HISTORY_NOT_ROUTE_FEASIBILITY",
        "FOUR_POOL_DAY_CLUSTERS_NOT_PURCHASABLE_WITH_FIVE_DOLLARS_ON_THIS_ROUTE",
        "NOTIONAL_BUCKET_SET_V1_ABSENT_SO_QUOTE_CALL_BUDGET_UNDEFINED",
        "REGISTRY_GAP_FOR_ROUTE_FEASIBILITY_PROVIDER",
    ]
    _integrity(registries.get("route_feasibility_registry_status") == "REGISTRY_GAP", "REGISTRY_GAP_LOST")
    _integrity(a25.get("notional_bucket_count") is None, "NOTIONAL_BUCKETS_GUESSED")
    _integrity(
        int(a25["independent_clusters"]) < int(cluster["minimum_clusters_for_variance_calibration"]),
        "FOUR_CLUSTERS_ALREADY_PRESENT",
    )
    quote_budget = {
        "formula": "SLOTS_PER_CLUSTER_TIMES_NOTIONAL_BUCKET_COUNT_TIMES_CLUSTERS",
        "slots_per_cluster": 96,
        "clusters_required": cluster["minimum_clusters_for_variance_calibration"],
        "notional_bucket_count": None,
        "quote_evaluations_lower_bound": None,
        "lower_bound_status": "UNDEFINED_NOTIONAL_BUCKET_SET_ABSENT",
        "illustrative_n1_evaluations": ILLUSTRATIVE_N1_EVALUATIONS,
        "illustrative_n1_usage": "ILLUSTRATIVE_N1_NOT_A_FROZEN_PARAMETER",
    }
    return {
        "usd_cents": spend["usd_cents"],
        "provider": spend["provider"],
        "payment_kind": spend["payment_kind"],
        "subscription": spend["subscription"],
        "wallet_or_signer_handling_by_agent": spend["wallet_or_signer_handling_by_agent"],
        "falsifies_estimand": False,
        "can_supply_route_feasibility_fields": False,
        "can_create_four_pool_day_clusters": False,
        "reasons": reasons,
        "quote_call_budget": quote_budget,
    }


def issue_verdict(spend: Mapping[str, Any]) -> str:
    if spend.get("falsifies_estimand") is True:
        raise A26IntegrityError("FIVE_DOLLAR_SPEND_TREATED_AS_FALSIFIER")
    return "FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY"


def execute_packet(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    a25 = bind_frozen_a25(repo_root, policy)
    registries = bind_registries(repo_root, policy)
    reuse = bind_reuse_candidate(repo_root, policy)
    spend = assess_spend(policy, a25, registries)
    terminal = issue_verdict(spend)
    forks = _mapping(policy.get("owner_forks"), "OWNER_FORKS_INVALID")
    _require(forks.get("selected") == "NONE_THIS_ATOM_ONLY_ENCODES_THE_FORK", "OWNER_FORK_PRESELECTED")
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "named_consumer": policy["consumer"],
        "terminal_decision": terminal,
        "task_state": "BLOCKED_DATA",
        "frozen_a25": a25,
        "registries": registries,
        "reuse_candidate": reuse,
        "proposed_spend": spend,
        "owner_forks": {
            "selected": forks["selected"],
            "options": list(_sequence(forks.get("options"), "OWNER_FORK_OPTIONS_INVALID")),
        },
        "claims": dict(_mapping(policy.get("claims"), "CLAIMS_INVALID")),
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
        },
        "non_claims": [
            "NO_TASK30_ACCEPTANCE",
            "NO_RC001_PROMOTION",
            "NO_H07_H01_TRIAL",
            "NO_EFFECT_ESTIMATE",
            "NO_ALPHA",
            "NO_NOTIONAL_BUCKET_GUESS",
            "NO_PROVIDER_CALL",
            "NO_FIVE_DOLLAR_PURCHASE",
        ],
        "project_sources_disposition": dict(
            _mapping(policy.get("project_sources_disposition"), "PROJECT_SOURCES_INVALID")
        ),
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    spend = _mapping(result.get("proposed_spend"), "SPEND_RESULT_INVALID")
    budget = _mapping(spend.get("quote_call_budget"), "BUDGET_RESULT_INVALID")
    a25 = _mapping(result.get("frozen_a25"), "A25_RESULT_INVALID")
    registries = _mapping(result.get("registries"), "REGISTRY_RESULT_INVALID")
    forks = list(_sequence(_mapping(result.get("owner_forks"), "FORK_RESULT_INVALID").get("options"), "FORK_OPTIONS_INVALID"))
    lines = [
        "# TASK-30 A26 — $5 Helius не фальсифицирует H07/H01",
        "",
        f"**Терминальное решение:** `{result['terminal_decision']}`",
        "",
        "Это **доказательство, что дешёвая покупка не закрывает estimand**,",
        "а не испытание гипотезы и не разрешение тратить.",
        "",
        "## Почему не $5 Helius",
        "",
        f"- замороженный терминал A25: `{a25['decision']}`",
        f"- независимых кластеров `POOL_DAY`: `{a25['independent_clusters']}`",
        f"- минимум кластеров для калибровки дисперсии: `{a25['minimum_clusters_for_variance_calibration']}`",
        f"- статус `ROUTE_FEASIBILITY` в реестре: `{registries['route_feasibility_registry_status']}`",
        f"- операции Helius: `{', '.join(registries['helius_operations'])}`",
        "- они дают историю сделок/логов, а не 13 полей полосы котировок",
        f"- `|NOTIONAL_BUCKET_SET_V1|`: отсутствует — `{budget['lower_bound_status']}`",
        f"- иллюстрация `4×96×1={budget['illustrative_n1_evaluations']}` — `{budget['illustrative_n1_usage']}`",
        "- подписка преждевременна; агент не трогает кошелёк, seed, signer, карту",
        "",
        "## Причины",
        "",
    ]
    for reason in _sequence(spend.get("reasons"), "REASONS_INVALID"):
        lines.append(f"- `{reason}`")
    lines.extend(
        [
            "",
            "## Что выбрать после merge этого пакета",
            "",
            "Ни один форк этим атомом не выбран.",
            "",
        ]
    )
    for option in forks:
        item = _mapping(option, "FORK_OPTION_INVALID")
        lines.append(
            f"- `{item['option_id']}` — `{item['owner_phrase']}` — `{item['eligibility']}`"
        )
    lines.extend(
        [
            "",
            "`AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE` остаётся `INELIGIBLE_UNTIL_PRECONDITIONS`:",
            "нужны замороженные нотионалы, строка `ROUTE_FEASIBILITY` в реестре с observed receipt",
            "и отдельный атом на ≥4 кластера `POOL_DAY`.",
            "",
            "`TASK-30` остаётся `BLOCKED_DATA`. Это не DONE, не альфа и не cashflow.",
            "",
        ]
    )
    return "\n".join(lines)
