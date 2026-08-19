"""Derived Factory read model. Owns no scientific truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.capabilities import (
    CAP_JUPITER_FREE_KEY_QUOTE_NATIVE_BOUNDED_CAPTURE,
    execute_capability,
    resolve_data_requirements,
)
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec, requirement_map
from solana_alpha_lab.factory.operational_store import OperationalStore


def _load_json(root: Path, relative: str) -> dict[str, Any] | None:
    path = root / relative
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else None


def project_read_model(
    *,
    root: Path,
    store: OperationalStore,
    spec_relative: str,
    hypothesis_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = load_experiment_spec(root, spec_relative)
    job = store.get_job(f"JOB-{spec['experiment_id']}")
    requirements = requirement_map(spec)
    acceptance_item = requirements.get("ACCEPTANCE")
    acceptance = None
    if acceptance_item is not None:
        acceptance = _load_json(root, str(acceptance_item["path"]))
    hypothesis_id = str(spec["hypothesis_version"])
    hypothesis_status = "UNKNOWN"
    if isinstance(hypothesis_registry, Mapping):
        records = hypothesis_registry.get("records")
        if isinstance(records, list):
            for record in records:
                if isinstance(record, Mapping) and record.get("record_id") == hypothesis_id:
                    hypothesis_status = str(record.get("status") or "UNKNOWN")
                    break
    coverage = resolve_data_requirements(spec, root=root)
    available = list(coverage["available"])
    missing = list(coverage["missing"])
    produced_missing = list(coverage.get("produced_missing") or [])
    operational_status = str(job["status"]) if job else "NOT_STARTED"
    evidence: dict[str, Any] = {"coverage": coverage}
    terminal = None
    capabilities = list(spec.get("capabilities") or [])
    live_capture = CAP_JUPITER_FREE_KEY_QUOTE_NATIVE_BOUNDED_CAPTURE in capabilities
    stored_statuses = {"COMPLETE", "FAILED", "BLOCKED_AUTHORITY", "BLOCKED_DATA", "STOPPED", "PARKED"}
    if operational_status in {"STOPPED", "PARKED"}:
        status = operational_status
        blocker = str(job["blocker"]) if job else "OWNER_STOP"
        terminal = job.get("terminal") if job else None
        evidence = dict(job.get("evidence") or evidence)
    elif job and operational_status in stored_statuses:
        status = operational_status
        blocker = str(job.get("blocker") or "NONE")
        terminal = job.get("terminal")
        evidence = dict(job.get("evidence") or evidence)
    elif missing:
        status = "BLOCKED_DATA" if operational_status != "NOT_STARTED" else "NOT_STARTED"
        blocker = "MISSING_OR_MISMATCHED_EVIDENCE"
    elif operational_status == "NOT_STARTED":
        status = "NOT_STARTED"
        blocker = "NONE"
    else:
        derived = execute_capability(spec, root=root)
        evidence = derived
        status = str(derived["status"])
        blocker = str(derived.get("blocker") or "NONE")
        terminal = derived.get("terminal")
    next_action = str(spec.get("parameters", {}).get("next_safe_action") or "INSPECT_READ_MODEL")
    if status == "NOT_STARTED" and missing:
        next_action = "RESOLVE_MISSING_EVIDENCE"
    elif status == "NOT_STARTED" and live_capture:
        next_action = "WAIT_EXACT_OWNER_PHRASE"
    elif status == "NOT_STARTED":
        next_action = "START_EXPERIMENT"
    elif status == "BLOCKED_DATA":
        next_action = "RESOLVE_MISSING_EVIDENCE"
    elif status == "BLOCKED_AUTHORITY":
        next_action = "WAIT_EXACT_OWNER_PHRASE"
    elif status == "COMPLETE" and terminal:
        next_action = str(spec["parameters"]["next_safe_action"])
        if live_capture:
            next_action = "RECORD_DECISION_OR_PARK"
    recommendation = "NO_ALPHA_CLAIM"
    if terminal:
        recommendation = str(terminal)
    packet_decision = None
    if status == "COMPLETE":
        packet_decision = (acceptance or {}).get("owner_decision") or (acceptance or {}).get("terminal")
    return {
        "hypothesis": hypothesis_id,
        "hypothesis_status": hypothesis_status,
        "status": status,
        "question": spec["question"],
        "estimand": spec["estimand"],
        "population": spec["population"],
        "available_data": available,
        "missing_data": missing,
        "produced_missing": produced_missing,
        "data": {
            "available": available,
            "missing": missing,
            "produced_missing": produced_missing,
        },
        "running_experiment": spec["experiment_id"] if status == "RUNNING" else None,
        "evidence_sufficiency": not missing and status in {
            "COMPLETE",
            "FAILED",
            "PARKED",
            "STOPPED",
            "BLOCKED_AUTHORITY",
        },
        "blocker": blocker,
        "terminal_result": terminal,
        "result": evidence.get("result") or terminal,
        "uncertainty": evidence.get("uncertainty") or "EXPLICIT_UNKNOWN",
        "robustness": evidence.get("robustness") or "UNKNOWN",
        "failure_modes": evidence.get("failure_modes") or [],
        "decision": packet_decision,
        "recommendation": recommendation,
        "next_safe_action": next_action,
        "next": next_action,
        "git_archaeology_required": bool(missing),
    }
