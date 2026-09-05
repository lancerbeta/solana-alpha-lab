"""Owner read composition over LifecycleProjectionV1. Owns no source truth."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.owner_language import research_copy
from solana_alpha_lab.factory.lifecycle_projection import (
    LifecycleProjectionError,
    build_lifecycle_projection,
)

RESEARCH_CLASSES = frozenset({"RESEARCH", "EXPERIMENT", "EVIDENCE_DECISION"})
RESEARCH_KINDS = frozenset(
    {
        "HYPOTHESIS_VERSION",
        "TRIAL",
        "DECISION_EVENT",
        "DECISION",
        "NEGATIVE_RESULT",
        "EXPERIMENT_SPEC",
        "EXPERIMENT_RUN",
    }
)
KIND_FILTERS = frozenset(
    {
        "all",
        "hypotheses",
        "experiments",
        "trials",
        "decisions",
        "negative",
        "HYPOTHESIS_VERSION",
        "TRIAL",
        "DECISION_EVENT",
        "DECISION",
        "NEGATIVE_RESULT",
        "EXPERIMENT_SPEC",
        "EXPERIMENT_RUN",
    }
)
TRUTH_PLANES = frozenset({"GIT", "EVIDENCE", "RUNTIME"})
ACTIVE_STATES = frozenset(
    {"RUNNING", "ACTIVE", "RUN_STARTED", "IN_PROGRESS", "STARTED"}
)
ATTENTION_GAP_CODES = frozenset(
    {
        "IDENTITY_CONFLICT",
        "STATE_CONFLICT",
        "SOURCE_INVALID",
        "SOURCE_UNAVAILABLE",
    }
)
ACTIVITY_SOURCE_IDS = frozenset({"SRC-RESEARCH-STORE", "SRC-OPERATIONAL-STORE"})
DEGRADED_SOURCE_STATUSES = frozenset({"NOT_PRESENT", "UNAVAILABLE", "INVALID"})
OBSERVABLE_SOURCE_STATUSES = frozenset({"AVAILABLE", "EMPTY"})
QUERY_MAX = 80
LIMIT_MAX = 200
_UNSAFE_LOCATOR = re.compile(r"[\\/]|^\.\.?$|source_ref|catalog/|\.sqlite|file:", re.I)


class ResearchWorkbenchError(ValueError):
    """Fail-closed research composition error."""


@dataclass(frozen=True, slots=True)
class LifecycleEntityLocatorV1:
    entity_id: str
    truth_plane: str
    native_kind: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.entity_id, self.truth_plane, self.native_kind)


def parse_locator(
    entity_id: str | None,
    truth_plane: str | None,
    native_kind: str | None,
) -> LifecycleEntityLocatorV1 | None:
    if not entity_id and not truth_plane and not native_kind:
        return None
    if not entity_id or not truth_plane or not native_kind:
        raise ResearchWorkbenchError("LOCATOR_INCOMPLETE")
    for part in (entity_id, truth_plane, native_kind):
        if len(part) > 256 or _UNSAFE_LOCATOR.search(part):
            raise ResearchWorkbenchError("LOCATOR_REJECTED")
    if truth_plane not in TRUTH_PLANES or native_kind not in RESEARCH_KINDS:
        raise ResearchWorkbenchError("LOCATOR_REJECTED")
    return LifecycleEntityLocatorV1(entity_id, truth_plane, native_kind)


def _source_by_id(projection: Mapping[str, Any], source_id: str) -> dict[str, Any] | None:
    for item in projection.get("sources") or []:
        if isinstance(item, dict) and item.get("source_id") == source_id:
            return item
    return None


def _research_entities(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in projection.get("entities") or []
        if isinstance(item, dict)
        and item.get("projection_class") in RESEARCH_CLASSES
        and item.get("native_kind") in RESEARCH_KINDS
    ]


def _matches_kind(entity: Mapping[str, Any], kind: str | None) -> bool:
    if not kind or kind == "all":
        return True
    native = str(entity.get("native_kind") or "")
    if kind == "hypotheses":
        return native == "HYPOTHESIS_VERSION"
    if kind == "experiments":
        return native in {"EXPERIMENT_SPEC", "EXPERIMENT_RUN"}
    if kind == "trials":
        return native == "TRIAL"
    if kind == "decisions":
        return native in {"DECISION", "DECISION_EVENT"}
    if kind == "negative":
        return native == "NEGATIVE_RESULT"
    return native == kind


def _text_blob(entity: Mapping[str, Any]) -> str:
    parts = [
        str(entity.get("entity_id") or ""),
        str(entity.get("native_kind") or ""),
        str(entity.get("native_state") or ""),
        str(entity.get("summary") or ""),
        str(entity.get("display_state") or ""),
        str(entity.get("truth_plane") or ""),
        str(entity.get("evidence_class") or ""),
    ]
    return " ".join(parts).casefold()


def _material_blocker(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.upper() in {"NONE", "UNKNOWN"}:
        return None
    return text


def _is_active(entity: Mapping[str, Any]) -> bool:
    if entity.get("truth_plane") not in {"RUNTIME", "EVIDENCE"}:
        return False
    state = str(entity.get("native_state") or "").upper()
    return state in ACTIVE_STATES


def _source_ref_tuple(ref: Any) -> tuple[str, str]:
    if not isinstance(ref, Mapping):
        return ("", "")
    return (str(ref.get("kind") or ""), str(ref.get("value") or ""))


def _activity_observable(projection: Mapping[str, Any]) -> bool:
    for item in projection.get("sources") or []:
        if not isinstance(item, dict):
            continue
        if item.get("source_id") not in ACTIVITY_SOURCE_IDS:
            continue
        if item.get("status") in OBSERVABLE_SOURCE_STATUSES:
            return True
    return False


def _source_attention_rows(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for gap in projection.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        code = str(gap.get("gap_code") or "")
        if code not in {"SOURCE_INVALID", "SOURCE_UNAVAILABLE"}:
            continue
        source_id = str(gap.get("source_id") or "")
        key = (code, source_id or str(gap.get("reason") or ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "locator": {},
                "kind": "SOURCE",
                "title": str(gap.get("reason") or code),
                "native_state": code,
                "display_state": code,
                "truth_plane": "",
                "evidence_class": "",
                "as_of": None,
                "observed_at": None,
                "source": source_id or gap.get("source_ref"),
                "freshness": None,
                "blocker": code,
                "next_safe_action": gap.get("next_safe_action") or "UNKNOWN",
                "attention": True,
            }
        )
    return rows


def _attention_entities(
    projection: Mapping[str, Any], entities: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    attention_ids: set[str] = set()
    for gap in projection.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        if gap.get("gap_code") not in ATTENTION_GAP_CODES:
            continue
        affected = gap.get("affected_entity_id")
        if isinstance(affected, str) and affected:
            attention_ids.add(affected)
    out: list[dict[str, Any]] = []
    for entity in entities:
        if _material_blocker(entity.get("blocker")) or entity.get("display_state") == "CONFLICT":
            out.append(dict(entity))
            continue
        if entity.get("entity_id") in attention_ids:
            out.append(dict(entity))
    return out


def _filter_entities(
    entities: list[dict[str, Any]],
    *,
    q: str | None,
    kind: str | None,
    truth_plane: str | None,
    state: str | None,
    evidence_class: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    if kind and kind not in KIND_FILTERS:
        raise ResearchWorkbenchError("FILTER_REJECTED")
    if truth_plane and truth_plane not in TRUTH_PLANES:
        raise ResearchWorkbenchError("FILTER_REJECTED")
    if q is not None and len(q) > QUERY_MAX:
        raise ResearchWorkbenchError("QUERY_TOO_LONG")
    allowed_states = {str(item.get("native_state") or "") for item in entities}
    allowed_evidence = {str(item.get("evidence_class") or "") for item in entities}
    if evidence_class is not None and (
        len(evidence_class) > 64
        or _UNSAFE_LOCATOR.search(evidence_class)
        or evidence_class not in allowed_evidence
    ):
        raise ResearchWorkbenchError("FILTER_REJECTED")
    if state is not None and (
        len(state) > 64
        or _UNSAFE_LOCATOR.search(state)
        or state not in allowed_states
    ):
        raise ResearchWorkbenchError("FILTER_REJECTED")
    needle = (q or "").strip().casefold()
    selected: list[dict[str, Any]] = []
    for entity in entities:
        if not _matches_kind(entity, kind):
            continue
        if truth_plane and entity.get("truth_plane") != truth_plane:
            continue
        if state and str(entity.get("native_state") or "") != state:
            continue
        if evidence_class and str(entity.get("evidence_class") or "") != evidence_class:
            continue
        if needle and needle not in _text_blob(entity):
            continue
        selected.append(entity)
        if len(selected) >= limit:
            break
    return selected


def _source_panel(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "SRC-EXPERIMENT-SPECS": "Git definitions",
        "SRC-GLOBAL-TRIAL-LEDGER": "Git trial ledger",
        "SRC-DECISIONS-NEGATIVE-RESULTS": "Git decisions",
        "SRC-RESEARCH-STORE": "Research evidence",
        "SRC-OPERATIONAL-STORE": "Experiment runtime",
    }
    gap_by_source: dict[str, dict[str, Any]] = {}
    for gap in projection.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        source_id = str(gap.get("source_id") or "")
        if source_id and source_id not in gap_by_source:
            gap_by_source[source_id] = gap
    rows = []
    for item in projection.get("sources") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        if source_id not in labels:
            continue
        gap = gap_by_source.get(source_id) or {}
        rows.append(
            {
                "label": labels[source_id],
                "source_id": source_id,
                "status": item.get("status"),
                "truth_plane": item.get("truth_plane"),
                "as_of": item.get("as_of"),
                "freshness_basis": item.get("freshness_basis"),
                "error": item.get("error") or gap.get("reason"),
                "next_safe_action": gap.get("next_safe_action") or "UNKNOWN",
            }
        )
    return rows


def _locator_for(entity: Mapping[str, Any]) -> dict[str, str]:
    return {
        "entity_id": str(entity.get("entity_id") or ""),
        "truth_plane": str(entity.get("truth_plane") or ""),
        "native_kind": str(entity.get("native_kind") or ""),
    }


def _row(entity: Mapping[str, Any]) -> dict[str, Any]:
    title = str(entity.get("summary") or entity.get("entity_id") or "")
    return {
        "locator": _locator_for(entity),
        "kind": entity.get("native_kind"),
        "title": title,
        "native_state": entity.get("native_state"),
        "display_state": entity.get("display_state"),
        "truth_plane": entity.get("truth_plane"),
        "evidence_class": entity.get("evidence_class"),
        "as_of": entity.get("as_of"),
        "observed_at": entity.get("observed_at"),
        "source": entity.get("source_owner"),
        "freshness": entity.get("freshness"),
        "blocker": _material_blocker(entity.get("blocker")),
        "next_safe_action": entity.get("next_safe_action") or "UNKNOWN",
        "attention": bool(
            _material_blocker(entity.get("blocker"))
            or entity.get("display_state") == "CONFLICT"
        ),
    }


def compose_research_overview(
    projection: Mapping[str, Any],
    *,
    q: str | None = None,
    kind: str | None = None,
    truth_plane: str | None = None,
    state: str | None = None,
    evidence_class: str | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    if limit < 1 or limit > LIMIT_MAX:
        raise ResearchWorkbenchError("LIMIT_REJECTED")
    entities = _research_entities(projection)
    attention = _attention_entities(projection, entities)
    source_attention = _source_attention_rows(projection)
    attention_rows = [_row(item) for item in attention[:limit]] + source_attention[:limit]
    active = [item for item in entities if _is_active(item)]
    trials = [item for item in entities if item.get("native_kind") == "TRIAL"]
    decisions = [
        item for item in entities if item.get("native_kind") in {"DECISION", "DECISION_EVENT"}
    ]
    negatives = [item for item in entities if item.get("native_kind") == "NEGATIVE_RESULT"]
    structural_gaps = [
        item
        for item in projection.get("gaps") or []
        if isinstance(item, dict)
        and item.get("gap_code")
        in {"RELATION_TARGET_GAP", "SOURCE_NOT_PRESENT", "SOURCE_GAP", "SOURCE_EMPTY"}
    ]
    filtered = _filter_entities(
        entities,
        q=q,
        kind=kind,
        truth_plane=truth_plane,
        state=state,
        evidence_class=evidence_class,
        limit=limit,
    )
    sources = _source_panel(projection)
    research_source = _source_by_id(projection, "SRC-RESEARCH-STORE") or {}
    research_status = str(research_source.get("status") or "NOT_PRESENT")
    degraded = research_status in DEGRADED_SOURCE_STATUSES
    return {
        "schema": "smial.research-overview-view",
        "schema_version": "1.0",
        "authority_granted": False,
        "completeness": projection.get("completeness") or "PARTIAL",
        "projection_id": projection.get("projection_id"),
        "sources": sources,
        "counters": {
            "ACTIVE NOW": len(active) if _activity_observable(projection) else None,
            "TRIALS": len(trials),
            "DECISIONS": len(decisions),
            "NEGATIVES": len(negatives),
            "ATTENTION": len(attention) + len(source_attention),
            "GAPS": len(structural_gaps),
        },
        "counter_scope": "materialized_projection_facts",
        "degraded": degraded,
        "degraded_copy": (research_copy("degraded_copy") if degraded else None),
        "needs_attention": attention_rows[:limit],
        "current_activity": [_row(item) for item in active[:limit]],
        "universe": [_row(item) for item in filtered],
        "filters": {
            "q": q or "",
            "kind": kind or "all",
            "truth_plane": truth_plane or "",
            "state": state or "",
            "evidence_class": evidence_class or "",
            "limit": limit,
        },
    }


def _load_git_record(root: Path, relative: str, record_id: str) -> dict[str, Any] | None:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ResearchWorkbenchError("SOURCE_REF_REJECTED")
    if not path.is_file():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    for record in loaded.get("records") or []:
        if isinstance(record, dict) and record.get("record_id") == record_id:
            return record
    return None


def _experiment_fields(root: Path, entity: Mapping[str, Any]) -> dict[str, Any]:
    source_ref = entity.get("source_ref") if isinstance(entity.get("source_ref"), dict) else {}
    relative = str(source_ref.get("value") or "")
    if not relative or source_ref.get("kind") != "git_path":
        return {}
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ResearchWorkbenchError("SOURCE_REF_REJECTED")
    spec = load_experiment_spec(root, relative)
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), dict) else {}
    return {
        "QUESTION": spec.get("question"),
        "ESTIMAND": spec.get("estimand"),
        "POPULATION": spec.get("population"),
        "FALSIFIER": spec.get("falsifier"),
        "METHOD": spec.get("method"),
        "HOLDOUT POLICY": spec.get("holdout_policy"),
        "TERMINAL OUTCOMES": spec.get("terminal_outcomes"),
        "DATA REQUIREMENTS": spec.get("data_requirements"),
        "CAPABILITIES": spec.get("capabilities"),
        "NEXT SAFE ACTION": parameters.get("next_safe_action")
        or entity.get("next_safe_action")
        or "UNKNOWN",
    }


def _registry_fields(root: Path, entity: Mapping[str, Any]) -> dict[str, Any]:
    source_ref = entity.get("source_ref") if isinstance(entity.get("source_ref"), dict) else {}
    relative = str(source_ref.get("value") or "")
    if source_ref.get("kind") != "git_path" or not relative:
        return {}
    record = _load_git_record(root, relative, str(entity.get("entity_id") or ""))
    if record is None:
        return {}
    kind = str(entity.get("native_kind") or "")
    if kind == "TRIAL":
        return {
            "trial ID": record.get("record_id"),
            "status": record.get("status"),
            "native outcome": record.get("outcome"),
            "hypothesis ID": record.get("hypothesis_id"),
            "created_at": record.get("created_at"),
            "evidence asset IDs": record.get("evidence_asset_ids"),
            "source as_of": entity.get("as_of"),
        }
    return {
        "record kind": record.get("record_kind"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "summary": record.get("summary"),
        "evidence asset IDs": record.get("evidence_asset_ids"),
    }


def _evidence_fields(entity: Mapping[str, Any]) -> dict[str, Any]:
    owned = entity.get("source_owned_fields")
    if isinstance(owned, Mapping) and owned:
        return {key: value for key, value in owned.items() if value not in (None, "")}
    return {}


def _runtime_fields(entity: Mapping[str, Any]) -> dict[str, Any]:
    if entity.get("native_kind") != "EXPERIMENT_RUN":
        return {}
    return {
        "run/job identity": entity.get("entity_id"),
        "native runtime state": entity.get("native_state"),
        "updated_at": entity.get("as_of"),
        "blocker": entity.get("blocker"),
        "terminal": entity.get("display_state"),
        "runtime observed_at": entity.get("observed_at"),
    }


def _relation_belongs_to_locator(
    rel: Mapping[str, Any],
    locator: LifecycleEntityLocatorV1,
    entity: Mapping[str, Any],
) -> bool:
    if locator.entity_id not in {rel.get("from_entity_id"), rel.get("to_entity_id")}:
        return False
    if rel.get("resolution") == "CONFLICT":
        return True
    rel_ref = _source_ref_tuple(rel.get("source_ref"))
    entity_ref = _source_ref_tuple(entity.get("source_ref"))
    if rel_ref != ("", "") and rel_ref == entity_ref:
        return True
    contributing = set(entity.get("contributing_source_ids") or [])
    owner = str(entity.get("source_owner") or "")
    if owner and owner in contributing:
        rel_kind = rel_ref[0]
        plane = locator.truth_plane
        if plane == "GIT" and rel_kind == "git_path":
            return True
        if plane == "EVIDENCE" and rel_kind in {"research_store", "injected"}:
            return True
        if plane == "RUNTIME" and rel_kind in {"sqlite", "injected"}:
            return True
    return False


def _lineage(
    projection: Mapping[str, Any],
    locator: LifecycleEntityLocatorV1,
    entity: Mapping[str, Any],
) -> dict[str, Any]:
    inbound: list[dict[str, Any]] = []
    outbound: list[dict[str, Any]] = []
    for rel in projection.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        if not _relation_belongs_to_locator(rel, locator, entity):
            continue
        edge = {
            "relation_type": rel.get("relation_type"),
            "from_entity_id": rel.get("from_entity_id"),
            "to_entity_id": rel.get("to_entity_id"),
            "resolution": rel.get("resolution"),
            "derivation_method": rel.get("derivation_method"),
        }
        if rel.get("to_entity_id") == locator.entity_id:
            inbound.append(edge)
        if rel.get("from_entity_id") == locator.entity_id:
            outbound.append(edge)
    return {"inbound": inbound, "outbound": outbound}


def _object_gaps(
    projection: Mapping[str, Any],
    locator: LifecycleEntityLocatorV1,
    entity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contributing = set(entity.get("contributing_source_ids") or [])
    entity_ref = _source_ref_tuple(entity.get("source_ref"))
    selected: list[dict[str, Any]] = []
    for item in projection.get("gaps") or []:
        if not isinstance(item, dict):
            continue
        affected = item.get("affected_entity_id")
        if affected != locator.entity_id:
            continue
        code = str(item.get("gap_code") or "")
        if code in {"IDENTITY_CONFLICT", "STATE_CONFLICT"}:
            selected.append(item)
            continue
        source_id = item.get("source_id")
        if source_id and source_id in contributing:
            selected.append(item)
            continue
        if _source_ref_tuple(item.get("source_ref")) == entity_ref:
            selected.append(item)
    return selected


def _timeline(entity: Mapping[str, Any], extra: Mapping[str, Any]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for label, raw in (
        ("created_at", extra.get("created_at")),
        ("effective_at", extra.get("effective_at")),
        ("first_reliable_available_at", extra.get("first_reliable_available_at")),
        ("as_of", entity.get("as_of")),
        ("observed_at", entity.get("observed_at")),
    ):
        if raw in (None, ""):
            continue
        events.append({"clock": label, "value": str(raw)})
    if not events:
        return [{"clock": "TIME_UNKNOWN", "value": "TIME_UNKNOWN"}]
    return events


def compose_research_detail(
    projection: Mapping[str, Any],
    locator: LifecycleEntityLocatorV1,
    *,
    root: Path,
    dossier: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    matches = [
        item
        for item in _research_entities(projection)
        if item.get("entity_id") == locator.entity_id
        and item.get("truth_plane") == locator.truth_plane
        and item.get("native_kind") == locator.native_kind
    ]
    if not matches:
        raise ResearchWorkbenchError("LOCATOR_NOT_IN_PROJECTION")
    if len(matches) > 1:
        raise ResearchWorkbenchError("LOCATOR_AMBIGUOUS")
    entity = matches[0]
    kind = str(entity.get("native_kind") or "")
    if kind == "EXPERIMENT_SPEC":
        fields = _experiment_fields(root, entity)
    elif kind in {"TRIAL", "NEGATIVE_RESULT", "DECISION"} and entity.get("truth_plane") == "GIT":
        fields = _registry_fields(root, entity)
    elif entity.get("truth_plane") == "EVIDENCE":
        fields = _evidence_fields(entity)
        if kind == "EXPERIMENT_RUN" and not fields:
            fields = _runtime_fields(entity)
    elif kind == "EXPERIMENT_RUN":
        fields = _runtime_fields(entity)
    else:
        fields = {}
    object_gaps = _object_gaps(projection, locator, entity)
    next_action = entity.get("next_safe_action") or "UNKNOWN"
    return {
        "schema": "smial.research-detail-view",
        "schema_version": "1.0",
        "authority_granted": False,
        "locator": {
            "entity_id": locator.entity_id,
            "truth_plane": locator.truth_plane,
            "native_kind": locator.native_kind,
        },
        "header": {
            "entity_id": entity.get("entity_id"),
            "native_kind": entity.get("native_kind"),
            "title": entity.get("summary") or entity.get("entity_id"),
            "state": entity.get("native_state") or "UNKNOWN",
            "display_state": entity.get("display_state"),
            "truth_plane": entity.get("truth_plane"),
            "evidence_class": entity.get("evidence_class"),
            "source": entity.get("source_owner"),
            "as_of": entity.get("as_of"),
            "observed_at": entity.get("observed_at"),
            "freshness": entity.get("freshness"),
            "next_safe_action": next_action,
        },
        "fields": fields,
        "lineage": _lineage(projection, locator, entity),
        "gaps": object_gaps,
        "unknown": [
            key
            for key, value in {
                "state": entity.get("native_state"),
                "next_safe_action": next_action if next_action != "UNKNOWN" else None,
                "as_of": entity.get("as_of"),
            }.items()
            if value in (None, "", "UNKNOWN")
        ],
        "provenance": {
            "source_owner": entity.get("source_owner"),
            "source_ref": entity.get("source_ref"),
            "contributing_source_ids": entity.get("contributing_source_ids"),
            "truth_plane": entity.get("truth_plane"),
        },
        "timeline": _timeline(entity, fields),
        "technical": {
            "projection_class": entity.get("projection_class"),
            "state_derivation": entity.get("state_derivation"),
            "authority_required": entity.get("authority_required"),
        },
        "dossier": dict(dossier) if dossier else None,
    }


def build_research_overview(
    root: Path,
    *,
    paper_plane_store: Any | None = None,
    research_store: Any | None = None,
    research_data_root: Path | None = None,
    research_discovery_status: str | None = None,
    research_discovery_error: str | None = None,
    q: str | None = None,
    kind: str | None = None,
    truth_plane: str | None = None,
    state: str | None = None,
    evidence_class: str | None = None,
    limit: int = 80,
    projected_at: str | None = None,
) -> dict[str, Any]:
    try:
        projection = build_lifecycle_projection(
            root,
            paper_plane_store=paper_plane_store,
            research_store=research_store,
            research_data_root=research_data_root,
            research_discovery_status=research_discovery_status,
            research_discovery_error=research_discovery_error,
            projected_at=projected_at,
        )
    except (FileNotFoundError, LifecycleProjectionError, OSError, ValueError) as exc:
        return {
            "schema": "smial.research-overview-view",
            "schema_version": "1.0",
            "authority_granted": False,
            "completeness": "UNAVAILABLE",
            "sources": [],
            "counters": {
                "ACTIVE NOW": None,
                "TRIALS": None,
                "DECISIONS": None,
                "NEGATIVES": None,
                "ATTENTION": None,
                "GAPS": None,
            },
            "degraded": True,
            "degraded_copy": (
                "Lifecycle projection is unavailable to this Workbench. "
                f"({type(exc).__name__})"
            ),
            "needs_attention": [],
            "current_activity": [],
            "universe": [],
            "filters": {"q": q or "", "kind": kind or "all", "limit": limit},
        }
    return compose_research_overview(
        projection,
        q=q,
        kind=kind,
        truth_plane=truth_plane,
        state=state,
        evidence_class=evidence_class,
        limit=limit,
    )


def build_research_detail(
    root: Path,
    locator: LifecycleEntityLocatorV1,
    *,
    paper_plane_store: Any | None = None,
    research_store: Any | None = None,
    research_data_root: Path | None = None,
    research_discovery_status: str | None = None,
    research_discovery_error: str | None = None,
    projected_at: str | None = None,
    write_capability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    projection = build_lifecycle_projection(
        root,
        paper_plane_store=paper_plane_store,
        research_store=research_store,
        research_data_root=research_data_root,
        research_discovery_status=research_discovery_status,
        research_discovery_error=research_discovery_error,
        projected_at=projected_at,
    )
    dossier = None
    if locator.native_kind == "EXPERIMENT_SPEC":
        from solana_alpha_lab.factory.experiment_evidence import compose_experiment_dossier
        from solana_alpha_lab.factory.research_store import ResearchStoreError

        records: tuple[Any, ...] | None = None
        records_status = "NOT_PRESENT"
        if research_store is not None:
            try:
                records = tuple(research_store.iter_committed_records())
                records_status = "AVAILABLE"
            except ResearchStoreError:
                records = None
                records_status = "UNAVAILABLE"
        elif research_discovery_status in {"UNAVAILABLE", "INVALID"}:
            records_status = "UNAVAILABLE"
        dossier = compose_experiment_dossier(
            projection,
            locator,
            root=root,
            records=records,
            records_status=records_status,
            write_capability=write_capability,
        )
    return compose_research_detail(projection, locator, root=root, dossier=dossier)
