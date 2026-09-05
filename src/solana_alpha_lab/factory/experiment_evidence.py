"""Compose one experiment dossier from existing source owners. Owns no truth."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.owner_language import DEFAULT_RATIONALE
from solana_alpha_lab.factory.research_workbench import (
    LifecycleEntityLocatorV1,
    ResearchWorkbenchError,
)

OWNER_DECISION_KINDS = ("REJECT", "REVISE", "PAUSE", "PROMOTE")
OBLIGATIONS = (
    "FALSIFIER",
    "PIT_AVAILABILITY",
    "POPULATION_N",
    "MISSINGNESS",
    "SURVIVAL",
    "HOLDOUT",
    "ENTRY_EXECUTABILITY",
    "EXIT_EXECUTABILITY",
    "COST_EVIDENCE",
    "RESULT",
    "UNCERTAINTY",
    "ROBUSTNESS",
    "EVIDENCE_CLASS",
)
SCIENCE_GUARD_OBLIGATIONS = OBLIGATIONS
EXECUTION_RECORD_KINDS = frozenset(
    {
        "RUN_STARTED",
        "RUN_COMPLETED",
        "RUN_ABORTED",
        "RUN_INVALID",
    }
)
SCIENTIFIC_EVIDENCE_RECORD_KINDS = frozenset(
    {
        "EXPERIMENT_METRIC",
        "EVIDENCE_BINDING",
        "PROMOTION_CANDIDATE",
    }
)
DIRECT_RECORD_KINDS = EXECUTION_RECORD_KINDS | SCIENTIFIC_EVIDENCE_RECORD_KINDS
RELATED_RECORD_KINDS = frozenset({"TRIAL", "DECISION_EVENT", "HYPOTHESIS_VERSION"})
EXPLICIT_EXPERIMENT_KEYS = (
    "experiment_id",
    "experiment_spec_id",
    "target_entity_id",
)
PRODUCER_CAPABILITY_ID = "FACTORY-APPLICATION-RESEARCH-DECISION-V1"


def _payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", None)
    if isinstance(raw, str) and raw:
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    payload = getattr(record, "payload", None)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _kind(record: Any) -> str:
    value = getattr(record, "record_kind", "")
    return str(getattr(value, "value", value) or "")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence_snapshot_sha256(parts: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_dumps(parts).encode("utf-8")).hexdigest()


def logical_decision_ids(
    *,
    locator: LifecycleEntityLocatorV1,
    decision_kind: str,
    snapshot_sha256: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(
        canonical_dumps(
            {
                "entity_id": locator.entity_id,
                "truth_plane": locator.truth_plane,
                "native_kind": locator.native_kind,
                "decision_kind": decision_kind,
                "evidence_snapshot_sha256": snapshot_sha256,
            }
        ).encode("utf-8")
    ).hexdigest()[:32].upper()
    return (
        f"RESEARCH-TXN-DEC-{digest}",
        f"DECISION-EVENT-{digest}",
    )


def _explicit_experiment_id(payload: Mapping[str, Any], record: Any) -> str | None:
    for key in EXPLICIT_EXPERIMENT_KEYS:
        value = _text(payload.get(key))
        if value:
            if key == "target_entity_id" and _text(payload.get("target_native_kind")) not in {
                None,
                "EXPERIMENT_SPEC",
            }:
                continue
            return value
    binding_target = payload.get("bound_entity_id") or payload.get("target_id")
    return _text(binding_target)


def _collect_direct_ids(experiment_id: str, records: Sequence[Any]) -> tuple[set[str], set[str]]:
    run_ids: set[str] = set()
    trial_ids: set[str] = set()
    for record in records:
        payload = _payload(record)
        if _explicit_experiment_id(payload, record) != experiment_id:
            continue
        run_id = _text(getattr(record, "run_id", None) or payload.get("run_id"))
        trial_id = _text(payload.get("trial_id"))
        if run_id:
            run_ids.add(run_id)
        if trial_id:
            trial_ids.add(trial_id)
    return run_ids, trial_ids


def classify_record(
    record: Any,
    *,
    experiment_id: str,
    hypothesis_version_id: str | None,
    direct_run_ids: set[str],
    direct_trial_ids: set[str],
) -> str | None:
    payload = _payload(record)
    kind = _kind(record)
    explicit = _explicit_experiment_id(payload, record)
    run_id = _text(getattr(record, "run_id", None) or payload.get("run_id"))
    trial_id = _text(payload.get("trial_id"))
    hyp = _text(getattr(record, "hypothesis_version_id", None) or payload.get("hypothesis_version_id"))
    if explicit == experiment_id:
        return "DIRECT"
    if run_id and run_id in direct_run_ids:
        return "DIRECT"
    if trial_id and trial_id in direct_trial_ids:
        return "DIRECT"
    if kind in DIRECT_RECORD_KINDS and explicit is None and run_id is None and trial_id is None:
        return None
    if hypothesis_version_id and hyp == hypothesis_version_id:
        if kind in RELATED_RECORD_KINDS or kind == "TRIAL" or kind == "DECISION_EVENT":
            return "RELATED"
    return None


def _record_card(record: Any, relation: str) -> dict[str, Any]:
    payload = _payload(record)
    return {
        "relation": relation,
        "record_id": getattr(record, "record_id", None),
        "record_kind": _kind(record),
        "entity_id": getattr(record, "entity_id", None),
        "hypothesis_version_id": getattr(record, "hypothesis_version_id", None),
        "run_id": getattr(record, "run_id", None) or payload.get("run_id"),
        "payload_sha256": getattr(record, "payload_sha256", None),
        "effective_at": str(getattr(record, "effective_at", "") or ""),
        "first_reliable_available_at": str(
            getattr(record, "first_reliable_available_at", "") or ""
        ),
        "summary_fields": {
            key: payload.get(key)
            for key in (
                "outcome",
                "decision_kind",
                "metric_id",
                "observed_n",
                "packet_sha256",
                "evidence_class",
            )
            if payload.get(key) not in (None, "")
        },
    }


def _obligation(
    code: str,
    status: str,
    *,
    source: str,
    note: str | None = None,
    values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "source": source,
        "note": note,
        "values": dict(values or {}),
    }


ROBUSTNESS_UNKNOWN_SENTINELS = frozenset({"NOT_TESTED", "UNTESTED", "UNKNOWN"})


def _scientific_cards(direct: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        card
        for card in direct
        if str(card.get("record_kind") or "") in SCIENTIFIC_EVIDENCE_RECORD_KINDS
    ]


def _collect_payload_values(
    cards: Sequence[Mapping[str, Any]],
    records: Sequence[Any],
    *keys: str,
    allow_empty_list: bool = False,
) -> list[Any]:
    by_id = {getattr(record, "record_id", None): record for record in records}
    found: list[Any] = []
    for card in cards:
        record = by_id.get(card.get("record_id"))
        payload = _payload(record) if record is not None else {}
        for key in keys:
            if key not in payload:
                continue
            value = payload[key]
            if value is None or value == "":
                continue
            if value == {} or (value == [] and not allow_empty_list):
                continue
            found.append(value)
            break
    return found


def _first_payload_value(cards: Sequence[Mapping[str, Any]], records: Sequence[Any], *keys: str) -> Any:
    values = _collect_payload_values(cards, records, *keys)
    return values[0] if values else None


def _status_from_values(
    *values: Any,
    source: str = "ResearchStore",
    present_note: str | None = None,
) -> tuple[str, str | None]:
    found = [item for item in values if item is not None and item != ""]
    if not found:
        return "MISSING", None
    texts = {canonical_dumps(item) for item in found}
    if len(texts) > 1:
        return "CONFLICT", "несколько явных значений не совпадают"
    return "PRESENT", present_note


def _holdout_status(
    spec: Mapping[str, Any],
    direct: Sequence[Mapping[str, Any]],
    records: Sequence[Any],
) -> dict[str, Any]:
    id_lists = _collect_payload_values(
        direct, records, "holdout_consumption_ids", allow_empty_list=True
    )
    ids_status, ids_note = _status_from_values(*id_lists)
    ids = id_lists[0] if id_lists else None
    applicable = _first_payload_value(direct, records, "holdout_applicable")
    if applicable is False or str(applicable).upper() in {"FALSE", "NO", "NOT_APPLICABLE"}:
        return _obligation(
            "HOLDOUT",
            "NOT_APPLICABLE",
            source="ResearchStore",
            note="явная семантика источника: holdout не открывался",
            values={"holdout_applicable": applicable, "holdout_consumption_ids": ids},
        )
    if ids_status == "CONFLICT":
        return _obligation(
            "HOLDOUT",
            "CONFLICT",
            source="ResearchStore",
            note=ids_note,
            values={"holdout_consumption_ids": id_lists},
        )
    if isinstance(ids, list) and ids:
        return _obligation(
            "HOLDOUT",
            "PRESENT",
            source="ResearchStore",
            values={"holdout_consumption_ids": ids},
        )
    if isinstance(ids, list):
        return _obligation(
            "HOLDOUT",
            "PRESENT",
            source="ResearchStore",
            note="явный пустой список потребления holdout",
            values={"holdout_consumption_ids": ids},
        )
    policy = _text(spec.get("holdout_policy"))
    if policy:
        return _obligation(
            "HOLDOUT",
            "UNKNOWN",
            source="ExperimentSpec",
            note="политика есть, явной связи потребления нет",
            values={"holdout_policy": policy},
        )
    return _obligation("HOLDOUT", "MISSING", source="ResearchStore")


def _build_obligations(
    spec: Mapping[str, Any],
    *,
    entity: Mapping[str, Any],
    direct: Sequence[Mapping[str, Any]],
    records: Sequence[Any] | None,
    records_status: str,
) -> list[dict[str, Any]]:
    if records_status == "UNAVAILABLE":
        return [
            _obligation(code, "UNKNOWN", source="SRC-RESEARCH-STORE", note="источник недоступен")
            if code != "FALSIFIER"
            else _obligation(
                "FALSIFIER",
                "PRESENT" if _text(spec.get("falsifier")) else "MISSING",
                source="ExperimentSpec",
                values={"falsifier": spec.get("falsifier")},
            )
            for code in OBLIGATIONS
        ]
    store_records = records or ()
    scientific = _scientific_cards(direct)
    falsifier = _text(spec.get("falsifier"))
    pit_cutoffs = _collect_payload_values(
        scientific, store_records, "availability_cutoff", "data_cutoff", "effective_cutoff"
    )
    pit_available_values = _collect_payload_values(
        scientific, store_records, "first_reliable_available_at"
    )
    pit_prov = _first_payload_value(scientific, store_records, "availability_provenance")
    n_values = _collect_payload_values(
        scientific, store_records, "observed_n", "n", "population_n"
    )
    missing_values = _collect_payload_values(
        scientific, store_records, "missing_count", "excluded_count", "missing_n"
    )
    survival_values = _collect_payload_values(
        scientific, store_records, "survival_visible", "survival_n", "survival_visibility"
    )
    entry_values = _collect_payload_values(
        scientific, store_records, "entry_artifact_id", "entry_executability"
    )
    exit_values = _collect_payload_values(
        scientific, store_records, "exit_artifact_id", "exit_executability"
    )
    cost_values = _collect_payload_values(
        scientific, store_records, "cost_assumptions_artifact_id", "cost_evidence_id"
    )
    result_values = _collect_payload_values(
        scientific, store_records, "outcome", "result", "scientific_terminal"
    )
    uncertainty_values = _collect_payload_values(
        scientific, store_records, "uncertainty", "limitation_codes"
    )
    robustness_values = _collect_payload_values(scientific, store_records, "robustness")
    class_values = _collect_payload_values(scientific, store_records, "evidence_class")
    pit_cutoff = pit_cutoffs[0] if pit_cutoffs else None
    pit_available = pit_available_values[0] if pit_available_values else None
    observed_n = n_values[0] if n_values else None
    missing_n = missing_values[0] if missing_values else None
    survival = survival_values[0] if survival_values else None
    entry = entry_values[0] if entry_values else None
    exit_ = exit_values[0] if exit_values else None
    cost = cost_values[0] if cost_values else None
    result = result_values[0] if result_values else None
    uncertainty = uncertainty_values[0] if uncertainty_values else None
    robustness = robustness_values[0] if robustness_values else None
    evidence_class = entity.get("evidence_class")
    if evidence_class in (None, "", "NOT_APPLICABLE") and not direct:
        evidence_status, evidence_note = "MISSING", "нет прямых evidence-записей"
        if entity.get("evidence_class") == "NOT_APPLICABLE":
            evidence_status, evidence_note = (
                "NOT_APPLICABLE",
                "Git ExperimentSpec не является scientific evidence class",
            )
    else:
        evidence_status, evidence_note = _status_from_values(
            *(class_values or [evidence_class])
        )
    pit_status, pit_note = _status_from_values(*(pit_cutoffs + pit_available_values))
    if pit_status == "PRESENT" and not (pit_cutoff and pit_available):
        pit_status = "UNKNOWN"
        pit_note = "cutoff или first_reliable_available_at неполны"
    if pit_status == "MISSING" and direct:
        pit_status = "UNKNOWN"
    n_status, n_note = _status_from_values(*n_values)
    if n_status == "MISSING" and not direct:
        n_status = "MISSING"
    elif n_status == "MISSING":
        n_status = "UNKNOWN"
    missing_status, missing_note = _status_from_values(*missing_values)
    if missing_status == "MISSING" and not direct:
        missing_status = "MISSING"
    survival_status, survival_note = _status_from_values(*survival_values)
    entry_status, entry_note = _status_from_values(*entry_values)
    exit_status, exit_note = _status_from_values(*exit_values)
    cost_status, cost_note = _status_from_values(*cost_values)
    result_status, result_note = _status_from_values(*result_values)
    uncertainty_status, uncertainty_note = _status_from_values(*uncertainty_values)
    robustness_status, robustness_note = _status_from_values(*robustness_values)
    if robustness_status == "PRESENT" and any(
        str(item).upper() in ROBUSTNESS_UNKNOWN_SENTINELS for item in robustness_values
    ):
        robustness_status = "UNKNOWN"
        robustness_note = "NOT_TESTED не равно выполненному robustness"
    population = _text(spec.get("population"))
    pop_status, pop_note = n_status, n_note
    if pop_status == "MISSING" and population:
        pop_note = "имя популяции не заменяет N"
    holdout = _holdout_status(spec, scientific, store_records)
    matrix = [
        _obligation(
            "FALSIFIER",
            "PRESENT" if falsifier else "MISSING",
            source="ExperimentSpec",
            values={"falsifier": spec.get("falsifier")},
        ),
        _obligation(
            "PIT_AVAILABILITY",
            pit_status,
            source="ResearchStore" if direct else "NONE",
            note=pit_note or (
                "RUN_COMPLETED не доказывает PIT" if pit_status != "PRESENT" else None
            ),
            values={
                "availability_cutoff": pit_cutoff,
                "first_reliable_available_at": pit_available,
                "availability_provenance": pit_prov,
            },
        ),
        _obligation(
            "POPULATION_N",
            pop_status,
            source="ExperimentSpec+ResearchStore",
            note=pop_note,
            values={"population": spec.get("population"), "observed_n": observed_n},
        ),
        _obligation(
            "MISSINGNESS",
            missing_status,
            source="ResearchStore",
            note=missing_note or "отсутствие missingness не равно нулю",
            values={"missing_count": missing_n},
        ),
        _obligation(
            "SURVIVAL",
            survival_status,
            source="ResearchStore",
            note=survival_note,
            values={"survival": survival},
        ),
        holdout,
        _obligation(
            "ENTRY_EXECUTABILITY",
            entry_status,
            source="ResearchStore",
            note=entry_note,
            values={"entry": entry},
        ),
        _obligation(
            "EXIT_EXECUTABILITY",
            exit_status,
            source="ResearchStore",
            note=exit_note,
            values={"exit": exit_},
        ),
        _obligation(
            "COST_EVIDENCE",
            cost_status,
            source="ResearchStore",
            note=cost_note or "нарратив про fees не заменяет машинное доказательство",
            values={"cost": cost},
        ),
        _obligation(
            "RESULT",
            result_status,
            source="ResearchStore",
            note=result_note,
            values={"result": result},
        ),
        _obligation(
            "UNCERTAINTY",
            uncertainty_status,
            source="ResearchStore",
            note=uncertainty_note,
            values={"uncertainty": uncertainty},
        ),
        _obligation(
            "ROBUSTNESS",
            robustness_status,
            source="ResearchStore",
            note=robustness_note,
            values={"robustness": robustness},
        ),
        _obligation(
            "EVIDENCE_CLASS",
            evidence_status,
            source="LifecycleProjection/ResearchStore",
            note=evidence_note,
            values={"evidence_class": (class_values[0] if class_values else evidence_class)},
        ),
    ]
    return matrix


def science_guard(obligations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    blocked = [
        item["code"]
        for item in obligations
        if item.get("code") in SCIENCE_GUARD_OBLIGATIONS
        and item.get("status") in {"MISSING", "UNKNOWN", "CONFLICT"}
    ]
    return {
        "allowed": not blocked,
        "blocked_codes": blocked,
        "meaning": "OWNER_MAY_CONSIDER_PROMOTION" if not blocked else "PROMOTE_BLOCKED",
    }


def _execution_state(direct: Sequence[Mapping[str, Any]]) -> str:
    kinds = [str(item.get("record_kind") or "") for item in direct]
    if "RUN_INVALID" in kinds:
        return "INVALID"
    if "RUN_ABORTED" in kinds:
        return "ABORTED"
    if "RUN_COMPLETED" in kinds:
        return "COMPLETED"
    if "RUN_STARTED" in kinds:
        return "RUNNING"
    return "NO_RUN"


def _decision_state(history: Sequence[Mapping[str, Any]]) -> str:
    if not history:
        return "NO_DECISION"
    latest = history[-1]
    return str(latest.get("decision_kind") or "NO_DECISION")


def _evidence_state(guard: Mapping[str, Any], obligations: Sequence[Mapping[str, Any]]) -> str:
    if any(item.get("status") == "CONFLICT" for item in obligations):
        return "CONFLICT"
    if not guard.get("allowed"):
        return "BLOCKED"
    return "GUARD_OPEN"


def _related_from_projection(
    projection: Mapping[str, Any],
    *,
    experiment_id: str,
    hypothesis_version_id: str | None,
    direct_ids: set[str],
) -> list[dict[str, Any]]:
    if not hypothesis_version_id:
        return []
    related_ids: set[str] = set()
    for rel in projection.get("relations") or []:
        if not isinstance(rel, Mapping):
            continue
        ends = {rel.get("from_entity_id"), rel.get("to_entity_id")}
        if hypothesis_version_id in ends:
            related_ids.update(str(item) for item in ends if item and item != experiment_id)
    cards: list[dict[str, Any]] = []
    for entity in projection.get("entities") or []:
        if not isinstance(entity, Mapping):
            continue
        entity_id = str(entity.get("entity_id") or "")
        if entity_id in {experiment_id, hypothesis_version_id} or entity_id in direct_ids:
            continue
        if entity.get("native_kind") not in {"TRIAL", "NEGATIVE_RESULT", "DECISION", "DECISION_EVENT"}:
            continue
        if entity_id not in related_ids:
            continue
        cards.append(
            {
                "relation": "RELATED",
                "record_id": None,
                "record_kind": entity.get("native_kind"),
                "entity_id": entity_id,
                "hypothesis_version_id": hypothesis_version_id,
                "run_id": None,
                "payload_sha256": None,
                "effective_at": entity.get("as_of") or "",
                "first_reliable_available_at": "",
                "summary_fields": {"summary": entity.get("summary")},
                "source": "LifecycleProjection",
            }
        )
    return cards


def compose_experiment_dossier(
    projection: Mapping[str, Any],
    locator: LifecycleEntityLocatorV1,
    *,
    root,
    records: Sequence[Any] | None,
    records_status: str,
    write_capability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if locator.native_kind != "EXPERIMENT_SPEC":
        raise ResearchWorkbenchError("DOSSIER_KIND_REJECTED")
    matches = [
        item
        for item in projection.get("entities") or []
        if isinstance(item, Mapping)
        and item.get("entity_id") == locator.entity_id
        and item.get("truth_plane") == locator.truth_plane
        and item.get("native_kind") == locator.native_kind
    ]
    if not matches:
        raise ResearchWorkbenchError("LOCATOR_NOT_IN_PROJECTION")
    entity = matches[0]
    source_ref = entity.get("source_ref") if isinstance(entity.get("source_ref"), dict) else {}
    relative = str(source_ref.get("value") or "")
    spec = load_experiment_spec(root, relative) if relative else {}
    hypothesis_version_id = _text(spec.get("hypothesis_version"))
    store_records = tuple(records or ())
    direct_run_ids, direct_trial_ids = _collect_direct_ids(locator.entity_id, store_records)
    direct: list[dict[str, Any]] = []
    related: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for record in store_records:
        relation = classify_record(
            record,
            experiment_id=locator.entity_id,
            hypothesis_version_id=hypothesis_version_id,
            direct_run_ids=direct_run_ids,
            direct_trial_ids=direct_trial_ids,
        )
        if relation is None:
            continue
        card = _record_card(record, relation)
        if relation == "DIRECT":
            direct.append(card)
        else:
            related.append(card)
        if _kind(record) == "DECISION_EVENT" and relation == "DIRECT":
            payload = _payload(record)
            history.append(
                {
                    "record_id": getattr(record, "record_id", None),
                    "decision_kind": payload.get("decision_kind"),
                    "evidence_snapshot_sha256": payload.get("evidence_snapshot_sha256"),
                    "rationale": payload.get("rationale"),
                    "effective_at": str(getattr(record, "effective_at", "") or ""),
                    "relation": "DIRECT",
                    "creates_strategy_version": payload.get("creates_strategy_version"),
                }
            )
    related.extend(
        _related_from_projection(
            projection,
            experiment_id=locator.entity_id,
            hypothesis_version_id=hypothesis_version_id,
            direct_ids={str(item.get("entity_id") or item.get("record_id")) for item in direct},
        )
    )
    history.sort(key=lambda item: (str(item.get("effective_at") or ""), str(item.get("record_id") or "")))
    obligations = _build_obligations(
        spec,
        entity=entity,
        direct=direct,
        records=store_records,
        records_status=records_status,
    )
    guard = science_guard(obligations)
    packet = _first_payload_value(direct, store_records, "packet_sha256")
    snapshot = evidence_snapshot_sha256(
        {
            "experiment_id": locator.entity_id,
            "hypothesis_version_id": hypothesis_version_id,
            "spec_as_of": entity.get("as_of"),
            "records_status": records_status,
            "obligations": [
                {"code": item["code"], "status": item["status"]} for item in obligations
            ],
            "direct_record_ids": sorted(str(item.get("record_id") or "") for item in direct),
            "direct_payload_sha256": sorted(
                str(item.get("payload_sha256") or "") for item in direct
            ),
            "promotion_packet_sha256": packet,
        }
    )
    tested = {
        "question": spec.get("question"),
        "estimand": spec.get("estimand"),
        "population": spec.get("population"),
        "falsifier": spec.get("falsifier"),
        "holdout_policy": spec.get("holdout_policy"),
        "method": spec.get("method"),
        "hypothesis_version_id": hypothesis_version_id,
        "legacy_source_language": "EN",
    }
    result_values = next(
        (item["values"] for item in obligations if item["code"] == "RESULT"),
        {},
    )
    return {
        "schema": "smial.experiment-evidence-dossier",
        "schema_version": "1.0",
        "authority_granted": False,
        "locator": {
            "entity_id": locator.entity_id,
            "truth_plane": locator.truth_plane,
            "native_kind": locator.native_kind,
        },
        "planes": {
            "execution": _execution_state(direct),
            "evidence": _evidence_state(guard, obligations),
            "decision": _decision_state(history),
        },
        "tested": tested,
        "obligations": obligations,
        "result": result_values,
        "direct_evidence": direct,
        "related_prior_memory": related,
        "decision_history": history,
        "science_guard": guard,
        "evidence_snapshot_sha256": snapshot,
        "write_capability": dict(write_capability or {"read": "AVAILABLE", "write": "UNKNOWN"}),
        "owner_decision_kinds": list(OWNER_DECISION_KINDS),
        "promote_creates_strategy_version": False,
        "records_status": records_status,
    }


def decision_payload(
    *,
    locator: LifecycleEntityLocatorV1,
    decision_kind: str,
    snapshot_sha256: str,
    hypothesis_version_id: str | None,
    rationale: str | None,
    decision_event_id: str,
) -> dict[str, Any]:
    kind = str(decision_kind or "")
    if kind not in OWNER_DECISION_KINDS:
        raise ResearchWorkbenchError("DECISION_KIND_REJECTED")
    text = _text(rationale) or DEFAULT_RATIONALE[kind]
    return {
        "decision_event_id": decision_event_id,
        "decision_kind": kind,
        "target_entity_id": locator.entity_id,
        "target_native_kind": locator.native_kind,
        "target_truth_plane": locator.truth_plane,
        "hypothesis_version_id": hypothesis_version_id,
        "evidence_snapshot_sha256": snapshot_sha256,
        "scientific_promotion_only": kind == "PROMOTE",
        "creates_strategy_version": False,
        "rationale": text,
        "next_condition": None,
        "decision_owner": "owner",
    }
