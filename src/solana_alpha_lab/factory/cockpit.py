"""Owner Cockpit-lite projection. Owns no scientific truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

COCKPIT_CONFIG_RELATIVE = "configs/factory_v1_owner_cockpit_v1.yaml"
PACKET_FIELDS = (
    "QUESTION",
    "ESTIMAND",
    "POPULATION",
    "DATA",
    "RESULT",
    "UNCERTAINTY",
    "ROBUSTNESS",
    "FAILURE",
    "DECISION",
    "NEXT",
)
ATTENTION_FIELDS = ("WHY_NOW", "IMPACT", "EVIDENCE", "NEXT_SAFE_ACTION")
VISIBLE_NAV = ("HOME", "RESEARCH", "SYSTEM")
HIDDEN_NAV = ("MARKET", "OPERATIONS", "ECONOMICS")


class CockpitError(ValueError):
    """Raised when the Cockpit-lite projection cannot proceed fail-closed."""


def load_cockpit_config(root: Path) -> dict[str, Any]:
    path = root / COCKPIT_CONFIG_RELATIVE
    if path.is_file() is False:
        raise CockpitError("COCKPIT_CONFIG_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise CockpitError("COCKPIT_CONFIG_INVALID")
    schema_path = root / "catalog/schemas/factory_v1_owner_cockpit.schema.json"
    if schema_path.is_file():
        import jsonschema

        jsonschema.validate(loaded, json.loads(schema_path.read_text(encoding="utf-8")))
    return loaded


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _attention_item(item_id: str, **fields: str) -> dict[str, str]:
    item = {"id": item_id}
    for key in ATTENTION_FIELDS:
        item[key] = str(fields[key])
    return item


def pinned_produced_gaps(spec: Mapping[str, Any], root: Path) -> list[str]:
    import hashlib

    gaps: list[str] = []
    for item in spec.get("data_requirements") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("kind")) != "PROVIDER_BOUNDED_CAPTURE":
            continue
        expected = item.get("sha256")
        relative = str(item.get("path") or "")
        path = root / relative
        requirement_id = str(item.get("requirement_id") or relative)
        if path.is_file() is False:
            gaps.append(requirement_id)
            continue
        if not expected:
            gaps.append(f"{requirement_id}:UNPINNED")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(expected):
            gaps.append(f"{requirement_id}:HASH_MISMATCH")
    return gaps


def project_cockpit(
    model: Mapping[str, Any],
    *,
    acceptance: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    pinned_produced_gaps: list[str] | None = None,
) -> dict[str, Any]:
    missing = list(model.get("missing_data") or [])
    produced_gaps = list(pinned_produced_gaps or [])
    evidence_gaps = list(dict.fromkeys([*missing, *produced_gaps]))
    criteria = (acceptance or {}).get("criteria") if isinstance((acceptance or {}).get("criteria"), dict) else {}
    cohort = (acceptance or {}).get("cohort") if isinstance((acceptance or {}).get("cohort"), dict) else {}
    failure = (acceptance or {}).get("limitations") or model.get("failure_modes")
    decision = model.get("decision") or (acceptance or {}).get("owner_decision")
    nxt = (acceptance or {}).get("next_boundary") or model.get("next_safe_action")
    result = (
        (acceptance or {}).get("scientific_terminal")
        or model.get("terminal_result")
        or model.get("result")
    )
    uncertainty = (
        (acceptance or {}).get("limitations")
        if acceptance
        else model.get("uncertainty")
    )
    robustness = (
        criteria.get("h3600_role")
        or (acceptance or {}).get("robustness")
        or model.get("robustness")
    )
    data = (
        cohort.get("sample_class")
        or model.get("population")
        or model.get("available_data")
    )
    packet = {
        "QUESTION": _text(model.get("question")),
        "ESTIMAND": _text(model.get("estimand")),
        "POPULATION": _text(model.get("population")),
        "DATA": _text(data),
        "RESULT": _text(result),
        "UNCERTAINTY": _text(uncertainty),
        "ROBUSTNESS": _text(robustness),
        "FAILURE": _text(failure),
        "DECISION": _text(decision),
        "NEXT": _text(nxt),
    }
    archaeology = bool(evidence_gaps)
    attention: list[dict[str, str]] = []
    if archaeology:
        attention.append(
            _attention_item(
                "GIT_ARCHAEOLOGY_REQUIRED",
                WHY_NOW="Required Git-bound evidence is missing or hash-mismatched",
                IMPACT="Owner cannot trust the packet without opening repository files",
                EVIDENCE="; ".join(evidence_gaps),
                NEXT_SAFE_ACTION="RESOLVE_MISSING_EVIDENCE",
            )
        )
    if (not archaeology) and packet["DECISION"] and packet["RESULT"]:
        attention.append(
            _attention_item(
                "DECISION_AVAILABLE",
                WHY_NOW="Git-bound packet projects a scientific result and owner decision",
                IMPACT="Owner can record or park without Git archaeology",
                EVIDENCE=packet["DECISION"],
                NEXT_SAFE_ACTION=packet["NEXT"] or "RECORD_DECISION_OR_PARK",
            )
        )
    if runtime and runtime.get("backup_status") == "EXPLICIT_UNKNOWN":
        attention.append(
            _attention_item(
                "BACKUP_EXPLICIT_UNKNOWN",
                WHY_NOW="Runtime backup is not a Drive read-back pass",
                IMPACT="RPO/RTO remain unproved as backup",
                EVIDENCE="EXPLICIT_UNKNOWN",
                NEXT_SAFE_ACTION="LATER_EXACT_BACKUP_OR_VPS_GATE",
            )
        )
    if runtime and runtime.get("verdict") and runtime.get("verdict") != "HEALTHY":
        attention.append(
            _attention_item(
                "RUNTIME_ATTENTION",
                WHY_NOW=f"Runtime verdict is {runtime.get('verdict')}",
                IMPACT="A live process is not a health pass",
                EVIDENCE=_text(runtime.get("verdict")),
                NEXT_SAFE_ACTION="INSPECT_SYSTEM",
            )
        )
    terminal = (
        "OWNER_COCKPIT_LITE_BLOCKED"
        if archaeology or not packet["RESULT"]
        else "OWNER_COCKPIT_LITE_OPERABILITY_PASS"
    )
    return {
        "visible_nav": list(VISIBLE_NAV),
        "hidden_nav": list(HIDDEN_NAV),
        "packet": packet,
        "attention": attention,
        "git_archaeology_required": archaeology,
        "operational_ready": False,
        "ui_package_adoption": False,
        "backup_status": (runtime or {}).get("backup_status") or "EXPLICIT_UNKNOWN",
        "terminal": terminal,
    }
