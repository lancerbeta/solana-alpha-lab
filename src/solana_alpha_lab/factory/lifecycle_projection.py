"""Derived owner lifecycle index. Owns no source truth and never writes stores."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

import yaml
from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version


class ResearchRecordReader(Protocol):
    def iter_committed_records(self) -> Iterable[Any]: ...

CONTRACT_RELATIVE = "configs/owner_lifecycle_projection_v1.yaml"
SCHEMA_RELATIVE = "catalog/schemas/owner_lifecycle_projection_v1.schema.json"
PROJECTION_ID = "OWNER_LIFECYCLE_PROJECTION_V1"
KERNEL_RELATIVE = "configs/factory_v1_product_kernel_v1.yaml"
PAPER_PLANE_STORE_RELATIVE = "local/factory_v1/paper_plane_state.sqlite"


def _ops_store_path(root: Path) -> Path:
    loaded = yaml.safe_load((root / KERNEL_RELATIVE).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise LifecycleProjectionError("KERNEL_INVALID")
    relative = str(loaded["operational_store"]["relative_path"])
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise LifecycleProjectionError("OPS_STORE_PATH_UNSAFE")
    return root / relative

_PROJECTED_RESEARCH_KINDS = frozenset(
    {
        "HYPOTHESIS_VERSION",
        "TRIAL",
        "DECISION_EVENT",
        "RUN_STARTED",
        "RUN_COMPLETED",
        "RUN_ABORTED",
        "RUN_INVALID",
        "ACTIVATION_EPOCH",
    }
)
_RUN_KINDS = frozenset(
    {"RUN_STARTED", "RUN_COMPLETED", "RUN_ABORTED", "RUN_INVALID"}
)
_RESEARCH_CLASS = {
    "HYPOTHESIS_VERSION": ("RESEARCH", "HYPOTHESIS_VERSION"),
    "TRIAL": ("RESEARCH", "TRIAL"),
    "DECISION_EVENT": ("EVIDENCE_DECISION", "DECISION_EVENT"),
    "RUN_STARTED": ("EXPERIMENT", "EXPERIMENT_RUN"),
    "RUN_COMPLETED": ("EXPERIMENT", "EXPERIMENT_RUN"),
    "RUN_ABORTED": ("EXPERIMENT", "EXPERIMENT_RUN"),
    "RUN_INVALID": ("EXPERIMENT", "EXPERIMENT_RUN"),
    "ACTIVATION_EPOCH": ("EXECUTION", "ACTIVATION_EPOCH"),
}


class LifecycleProjectionError(ValueError):
    """Raised when the derived index cannot be validated."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git_sha(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    sha = result.stdout.strip()
    return sha if len(sha) == 40 else None


def load_projection_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise LifecycleProjectionError("CONTRACT_INVALID")
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(loaded)
    if loaded.get("authority_granted") is not False:
        raise LifecycleProjectionError("AUTHORITY_GRANT_FORBIDDEN")
    return loaded


def validate_lifecycle_projection(document: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
    if document.get("authority_granted") is not False:
        raise LifecycleProjectionError("AUTHORITY_GRANT_FORBIDDEN")
    if document.get("schema") != "smial.owner-lifecycle-projection":
        raise LifecycleProjectionError("PROJECTION_SCHEMA_REQUIRED")
    for relation in document.get("relations") or []:
        method = str(relation.get("derivation_method") or "")
        if method.startswith("INFERRED_"):
            raise LifecycleProjectionError("INFERRED_RELATION_FORBIDDEN")
    return dict(document)


def _source(
    *,
    source_id: str,
    truth_plane: str,
    truth_owner: str,
    source_ref: dict[str, str],
    status: str,
    observed_at: str | None,
    freshness_basis: str,
    as_of: str | None = None,
    error: str | None = None,
    adapter_detail: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "truth_plane": truth_plane,
        "truth_owner": truth_owner,
        "source_ref": source_ref,
        "status": status,
        "observed_at": observed_at,
        "as_of": as_of,
        "freshness_basis": freshness_basis,
        "error": error,
        "adapter_detail": adapter_detail,
    }


def _entity(
    *,
    entity_id: str,
    projection_class: str,
    native_kind: str,
    source_owner: str,
    source_ref: dict[str, str],
    truth_plane: str,
    contributing_source_ids: list[str],
    native_state: str | None = None,
    display_state: str | None = None,
    state_derivation: str = "UNKNOWN",
    as_of: str | None = None,
    observed_at: str | None = None,
    evidence_class: str = "NOT_APPLICABLE",
    freshness_status: str = "UNKNOWN",
    freshness_basis: str = "source_defines_no_slo",
    blocker: str | None = None,
    next_safe_action: str | None = "UNKNOWN",
    authority_required: str = "NONE_FOR_READ",
    summary: str | None = None,
    source_owned_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    display = display_state if display_state is not None else native_state
    derivation = state_derivation
    if native_state is not None and derivation == "UNKNOWN":
        derivation = "SOURCE_NATIVE"
        display = native_state
    payload = {
        "entity_id": entity_id,
        "projection_class": projection_class,
        "native_kind": native_kind,
        "native_state": native_state,
        "display_state": display,
        "state_derivation": derivation,
        "source_owner": source_owner,
        "source_ref": source_ref,
        "truth_plane": truth_plane,
        "as_of": as_of,
        "observed_at": observed_at,
        "evidence_class": evidence_class,
        "freshness": {"status": freshness_status, "basis": freshness_basis},
        "blocker": blocker,
        "next_safe_action": next_safe_action,
        "authority_required": authority_required,
        "summary": summary,
        "contributing_source_ids": list(contributing_source_ids),
    }
    if source_owned_fields:
        payload["source_owned_fields"] = source_owned_fields
    return payload


def _relation(
    *,
    relation_type: str,
    from_entity_id: str,
    to_entity_id: str,
    source_ref: dict[str, str],
    derivation_method: str,
    known_ids: set[str],
) -> dict[str, Any]:
    if not from_entity_id or not to_entity_id:
        raise LifecycleProjectionError("MISSING_STABLE_ID")
    if to_entity_id in known_ids:
        resolution = "RESOLVED"
    else:
        resolution = "TARGET_GAP"
    return {
        "relation_type": relation_type,
        "from_entity_id": from_entity_id,
        "to_entity_id": to_entity_id,
        "resolution": resolution,
        "source_ref": source_ref,
        "derivation_method": derivation_method,
    }


def _gap(
    *,
    gap_code: str,
    reason: str,
    source_ref: dict[str, str],
    impact: str,
    next_safe_action: str,
    affected_entity_id: str | None = None,
    source_id: str | None = None,
    relation_type: str | None = None,
) -> dict[str, Any]:
    return {
        "gap_code": gap_code,
        "affected_entity_id": affected_entity_id,
        "source_id": source_id,
        "relation_type": relation_type,
        "reason": reason,
        "source_ref": source_ref,
        "impact": impact,
        "next_safe_action": next_safe_action,
    }


def _yaml_files(root: Path, relative_root: str) -> list[str]:
    directory = root / relative_root
    if not directory.is_dir():
        return []
    out: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        rel = path.relative_to(root).as_posix()
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            continue
        out.append(rel)
    return out


def _load_registry(root: Path, relative: str) -> tuple[str, dict[str, Any] | None, str | None]:
    path = root / relative
    source_ref = {"kind": "git_path", "value": relative}
    if not path.is_file():
        return "NOT_PRESENT", None, None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return "INVALID", None, type(exc).__name__
    if not isinstance(loaded, dict):
        return "INVALID", None, "REGISTRY_NOT_OBJECT"
    records = loaded.get("records")
    if not isinstance(records, list):
        return "INVALID", loaded, "RECORDS_NOT_LIST"
    if not records:
        return "EMPTY", loaded, None
    return "AVAILABLE", loaded, None


def _sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _adapt_legacy_registries(
    root: Path,
    contract: Mapping[str, Any],
    observed_at: str,
    git_sha: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for relative in contract["legacy_empty_registries"]:
        status, _doc, error = _load_registry(root, relative)
        source_id = f"SRC-LEGACY-{Path(relative).stem.upper().replace('_', '-')}"
        source_ref = {"kind": "git_path", "value": relative}
        sources.append(
            _source(
                source_id=source_id,
                truth_plane="GIT",
                truth_owner="lifecycle_registry_envelope",
                source_ref=source_ref,
                status=status,
                observed_at=observed_at,
                as_of=git_sha,
                freshness_basis="CURRENT_AT_COMMIT",
                error=error,
                adapter_detail="empty_envelope_is_not_complete_current_truth",
            )
        )
        if status == "EMPTY":
            gaps.append(
                _gap(
                    gap_code="SOURCE_EMPTY",
                    source_id=source_id,
                    reason=f"{relative} is an empty Git envelope and is not a complete current owner",
                    source_ref=source_ref,
                    impact="consumers_must_use_current_source_owners_via_this_projection",
                    next_safe_action="DO_NOT_BACKFILL",
                )
            )
        elif status == "NOT_PRESENT":
            gaps.append(
                _gap(
                    gap_code="SOURCE_NOT_PRESENT",
                    source_id=source_id,
                    reason=f"{relative} is not present",
                    source_ref=source_ref,
                    impact="legacy_envelope_unavailable",
                    next_safe_action="UNKNOWN",
                )
            )
        elif status == "INVALID":
            gaps.append(
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=error or "invalid registry",
                    source_ref=source_ref,
                    impact="legacy_envelope_unreadable",
                    next_safe_action="FAIL_CLOSED_FOR_SOURCE",
                )
            )
    return sources, gaps


def _adapt_negative_decisions(
    root: Path,
    contract: Mapping[str, Any],
    observed_at: str,
    git_sha: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relative = str(contract["decision_negative_registry"])
    source_id = "SRC-DECISIONS-NEGATIVE-RESULTS"
    source_ref = {"kind": "git_path", "value": relative}
    status, doc, error = _load_registry(root, relative)
    source = _source(
        source_id=source_id,
        truth_plane="GIT",
        truth_owner="decisions_negative_results",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        as_of=str(doc.get("as_of") if doc else git_sha),
        freshness_basis="CURRENT_AT_COMMIT",
        error=error,
    )
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    if status == "NOT_PRESENT":
        gaps.append(
            _gap(
                gap_code="SOURCE_NOT_PRESENT",
                source_id=source_id,
                reason="decision/negative registry is not present",
                source_ref=source_ref,
                impact="no_git_decision_memory",
                next_safe_action="UNKNOWN",
            )
        )
        return source, entities, relations, gaps
    if status == "INVALID":
        gaps.append(
            _gap(
                gap_code="SOURCE_INVALID",
                source_id=source_id,
                reason=error or "invalid registry",
                source_ref=source_ref,
                impact="decision_memory_unreadable",
                next_safe_action="FAIL_CLOSED_FOR_SOURCE",
            )
        )
        return source, entities, relations, gaps
    if status == "EMPTY":
        gaps.append(
            _gap(
                gap_code="SOURCE_EMPTY",
                source_id=source_id,
                reason="decision/negative registry has no records",
                source_ref=source_ref,
                impact="no_recorded_decisions",
                next_safe_action="UNKNOWN",
            )
        )
        return source, entities, relations, gaps
    assert doc is not None
    for record in doc.get("records") or []:
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id") or "")
        kind = str(record.get("record_kind") or "")
        if not record_id:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason="decision/negative record missing record_id",
                    source_ref=source_ref,
                    impact="record_dropped",
                    next_safe_action="FAIL_CLOSED_FOR_RECORD",
                )
            )
            continue
        native_kind = "NEGATIVE_RESULT" if kind == "negative_result" else "DECISION"
        entities.append(
            _entity(
                entity_id=record_id,
                projection_class="EVIDENCE_DECISION",
                native_kind=native_kind,
                native_state=str(record.get("status") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="GIT",
                contributing_source_ids=[source_id],
                as_of=str(record.get("created_at") or doc.get("as_of") or git_sha),
                observed_at=observed_at,
                evidence_class="RETAINED_OFFLINE_DECISION",
                freshness_status="CURRENT_AT_COMMIT",
                freshness_basis="git_registry_record",
                summary=str(record.get("summary") or "") or None,
                next_safe_action="UNKNOWN",
            )
        )
        for evidence_id in record.get("evidence_asset_ids") or []:
            if not isinstance(evidence_id, str) or not evidence_id:
                continue
            relations.append(
                {
                    "relation_type": "REFERENCES_EVIDENCE_ASSET",
                    "from_entity_id": record_id,
                    "to_entity_id": evidence_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
            gaps.append(
                _gap(
                    gap_code="RELATION_TARGET_GAP",
                    affected_entity_id=record_id,
                    source_id=source_id,
                    relation_type="REFERENCES_EVIDENCE_ASSET",
                    reason=f"evidence asset {evidence_id} is not a lifecycle entity",
                    source_ref=source_ref,
                    impact="lineage_to_catalog_evidence_not_materialized_here",
                    next_safe_action="UNKNOWN",
                )
            )
    return source, entities, relations, gaps


def _adapt_global_trial_ledger(
    root: Path,
    contract: Mapping[str, Any],
    observed_at: str,
    git_sha: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relative = str(contract["global_trial_ledger"])
    source_id = "SRC-GLOBAL-TRIAL-LEDGER"
    source_ref = {"kind": "git_path", "value": relative}
    status, doc, error = _load_registry(root, relative)
    source = _source(
        source_id=source_id,
        truth_plane="GIT",
        truth_owner="global_trial_ledger",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        as_of=str(doc.get("as_of") if doc else git_sha),
        freshness_basis="CURRENT_AT_COMMIT",
        error=error,
    )
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    if status == "NOT_PRESENT":
        gaps.append(
            _gap(
                gap_code="SOURCE_NOT_PRESENT",
                source_id=source_id,
                reason="global trial ledger is not present",
                source_ref=source_ref,
                impact="no_git_trial_memory",
                next_safe_action="UNKNOWN",
            )
        )
        return source, entities, relations, gaps
    if status == "INVALID":
        gaps.append(
            _gap(
                gap_code="SOURCE_INVALID",
                source_id=source_id,
                reason=error or "invalid registry",
                source_ref=source_ref,
                impact="trial_memory_unreadable",
                next_safe_action="FAIL_CLOSED_FOR_SOURCE",
            )
        )
        return source, entities, relations, gaps
    if status == "EMPTY":
        gaps.append(
            _gap(
                gap_code="SOURCE_EMPTY",
                source_id=source_id,
                reason="global trial ledger has no records",
                source_ref=source_ref,
                impact="no_recorded_trials",
                next_safe_action="UNKNOWN",
            )
        )
        return source, entities, relations, gaps
    assert doc is not None
    for record in doc.get("records") or []:
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id") or "")
        kind = str(record.get("record_kind") or "")
        if not record_id:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason="trial record missing record_id",
                    source_ref=source_ref,
                    impact="record_dropped",
                    next_safe_action="FAIL_CLOSED_FOR_RECORD",
                )
            )
            continue
        if kind and kind != "trial":
            continue
        outcome = str(record.get("outcome") or "") or None
        hypothesis_id = str(record.get("hypothesis_id") or "")
        summary_parts = []
        if outcome:
            summary_parts.append(f"outcome={outcome}")
        if hypothesis_id:
            summary_parts.append(f"hypothesis_id={hypothesis_id}")
        entities.append(
            _entity(
                entity_id=record_id,
                projection_class="RESEARCH",
                native_kind="TRIAL",
                native_state=str(record.get("status") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="GIT",
                contributing_source_ids=[source_id],
                as_of=str(record.get("created_at") or doc.get("as_of") or git_sha),
                observed_at=observed_at,
                evidence_class="RETAINED_OFFLINE_TRIAL",
                freshness_status="CURRENT_AT_COMMIT",
                freshness_basis="git_registry_record",
                summary=" ".join(summary_parts) or None,
                next_safe_action="UNKNOWN",
            )
        )
        if hypothesis_id:
            relations.append(
                {
                    "relation_type": "REFERENCES_HYPOTHESIS_VERSION",
                    "from_entity_id": record_id,
                    "to_entity_id": hypothesis_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        for evidence_id in record.get("evidence_asset_ids") or []:
            if not isinstance(evidence_id, str) or not evidence_id:
                continue
            relations.append(
                {
                    "relation_type": "REFERENCES_EVIDENCE_ASSET",
                    "from_entity_id": record_id,
                    "to_entity_id": evidence_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
            gaps.append(
                _gap(
                    gap_code="RELATION_TARGET_GAP",
                    affected_entity_id=record_id,
                    source_id=source_id,
                    relation_type="REFERENCES_EVIDENCE_ASSET",
                    reason=f"evidence asset {evidence_id} is not a lifecycle entity",
                    source_ref=source_ref,
                    impact="lineage_to_catalog_evidence_not_materialized_here",
                    next_safe_action="UNKNOWN",
                )
            )
    return source, entities, relations, gaps


def _adapt_experiment_specs(
    root: Path,
    contract: Mapping[str, Any],
    observed_at: str,
    git_sha: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relative_root = str(contract["bounded_roots"]["experiment_specs"])
    source_id = "SRC-EXPERIMENT-SPECS"
    source_ref = {"kind": "git_path", "value": relative_root}
    candidates = _yaml_files(root, relative_root)
    if not (root / relative_root).is_dir():
        source = _source(
            source_id=source_id,
            truth_plane="GIT",
            truth_owner="ExperimentSpec",
            source_ref=source_ref,
            status="NOT_PRESENT",
            observed_at=observed_at,
            as_of=git_sha,
            freshness_basis="CURRENT_AT_COMMIT",
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_NOT_PRESENT",
                    source_id=source_id,
                    reason="experiment spec bounded root is missing",
                    source_ref=source_ref,
                    impact="no_git_experiment_definitions",
                    next_safe_action="UNKNOWN",
                )
            ],
        )
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    loaded = 0
    for rel in candidates:
        file_ref = {"kind": "git_path", "value": rel}
        try:
            spec = load_experiment_spec(root, rel)
        except Exception as exc:  # noqa: BLE001 — fail-closed per candidate
            gaps.append(
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=f"{rel}: {type(exc).__name__}",
                    source_ref=file_ref,
                    impact="candidate_not_projected",
                    next_safe_action="FAIL_CLOSED_FOR_CANDIDATE",
                )
            )
            continue
        experiment_id = str(spec.get("experiment_id") or "")
        if not experiment_id:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason=f"{rel} has no experiment_id",
                    source_ref=file_ref,
                    impact="candidate_not_projected",
                    next_safe_action="FAIL_CLOSED_FOR_CANDIDATE",
                )
            )
            continue
        params = spec.get("parameters") if isinstance(spec.get("parameters"), Mapping) else {}
        terminal = str(params.get("product_terminal") or "") or None
        next_action = str(params.get("next_safe_action") or "") or "UNKNOWN"
        entities.append(
            _entity(
                entity_id=experiment_id,
                projection_class="EXPERIMENT",
                native_kind="EXPERIMENT_SPEC",
                native_state=terminal,
                state_derivation="SOURCE_NATIVE" if terminal else "UNKNOWN",
                source_owner=source_id,
                source_ref=file_ref,
                truth_plane="GIT",
                contributing_source_ids=[source_id],
                as_of=git_sha,
                observed_at=observed_at,
                evidence_class="NOT_APPLICABLE",
                freshness_status="CURRENT_AT_COMMIT",
                freshness_basis="git_definition",
                next_safe_action=next_action,
                summary=str(spec.get("question") or "") or None,
            )
        )
        loaded += 1
        hypothesis = str(spec.get("hypothesis_version") or "")
        if hypothesis:
            relations.append(
                {
                    "relation_type": "REFERENCES_HYPOTHESIS_VERSION",
                    "from_entity_id": experiment_id,
                    "to_entity_id": hypothesis,
                    "resolution": "TARGET_GAP",
                    "source_ref": file_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        relations.append(
            {
                "relation_type": "JOB_FOR_EXPERIMENT",
                "from_entity_id": f"JOB-{experiment_id}",
                "to_entity_id": experiment_id,
                "resolution": "SOURCE_GAP",
                "source_ref": file_ref,
                "derivation_method": "EXPLICIT_CONTRACT_KEY",
            }
        )
    status = "AVAILABLE" if loaded else ("EMPTY" if not candidates else "INVALID")
    source = _source(
        source_id=source_id,
        truth_plane="GIT",
        truth_owner="ExperimentSpec",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        as_of=git_sha,
        freshness_basis="CURRENT_AT_COMMIT",
        adapter_detail=f"loaded={loaded};candidates={len(candidates)}",
    )
    return source, entities, relations, gaps


def _adapt_strategy_versions(
    root: Path,
    contract: Mapping[str, Any],
    observed_at: str,
    git_sha: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relative_root = str(contract["bounded_roots"]["strategy_versions"])
    source_id = "SRC-STRATEGY-VERSIONS"
    source_ref = {"kind": "git_path", "value": relative_root}
    candidates = _yaml_files(root, relative_root)
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    if not (root / relative_root).is_dir():
        source = _source(
            source_id=source_id,
            truth_plane="GIT",
            truth_owner="StrategyVersion",
            source_ref=source_ref,
            status="NOT_PRESENT",
            observed_at=observed_at,
            as_of=git_sha,
            freshness_basis="CURRENT_AT_COMMIT",
        )
        gaps.append(
            _gap(
                gap_code="SOURCE_NOT_PRESENT",
                source_id=source_id,
                reason="strategy bounded root is missing",
                source_ref=source_ref,
                impact="no_git_strategy_definitions",
                next_safe_action="UNKNOWN",
            )
        )
        return source, entities, relations, gaps
    loaded = 0
    for rel in candidates:
        file_ref = {"kind": "git_path", "value": rel}
        try:
            strategy = load_strategy_version(root, rel)
        except Exception as exc:  # noqa: BLE001
            gaps.append(
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=f"{rel}: {type(exc).__name__}",
                    source_ref=file_ref,
                    impact="candidate_not_projected",
                    next_safe_action="FAIL_CLOSED_FOR_CANDIDATE",
                )
            )
            continue
        strategy_id = str(strategy.get("strategy_id") or "")
        version = str(strategy.get("strategy_version") or "")
        if not strategy_id or not version:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason=f"{rel} missing strategy_id/strategy_version",
                    source_ref=file_ref,
                    impact="candidate_not_projected",
                    next_safe_action="FAIL_CLOSED_FOR_CANDIDATE",
                )
            )
            continue
        entity_id = f"{strategy_id}@{version}"
        evidence_class = str(strategy.get("evidence_class") or "UNKNOWN")
        entities.append(
            _entity(
                entity_id=entity_id,
                projection_class="STRATEGY",
                native_kind="STRATEGY_VERSION",
                native_state=version,
                state_derivation="SOURCE_NATIVE",
                source_owner=source_id,
                source_ref=file_ref,
                truth_plane="GIT",
                contributing_source_ids=[source_id],
                as_of=str(strategy.get("created_at") or git_sha),
                observed_at=observed_at,
                evidence_class=evidence_class if evidence_class else "UNKNOWN",
                freshness_status="CURRENT_AT_COMMIT",
                freshness_basis="git_definition",
                summary=str(strategy.get("title") or "") or None,
                next_safe_action="UNKNOWN",
            )
        )
        loaded += 1
        decision_asset = strategy.get("source_decision_asset_id") or (
            (strategy.get("raw") or {}).get("source_decision_asset_id")
            if isinstance(strategy.get("raw"), Mapping)
            else None
        )
        if isinstance(decision_asset, str) and decision_asset:
            relations.append(
                {
                    "relation_type": "REFERENCES_DECISION_ASSET",
                    "from_entity_id": entity_id,
                    "to_entity_id": decision_asset,
                    "resolution": "TARGET_GAP",
                    "source_ref": file_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        refs = list(strategy.get("source_hypothesis_refs") or [])
        raw = strategy.get("raw") if isinstance(strategy.get("raw"), Mapping) else {}
        if not refs:
            refs = list(raw.get("hypothesis_ids") or strategy.get("hypothesis_ids") or [])
        for hyp in refs:
            if not isinstance(hyp, str) or not hyp:
                continue
            relations.append(
                {
                    "relation_type": "REFERENCES_HYPOTHESIS_VERSION",
                    "from_entity_id": entity_id,
                    "to_entity_id": hyp,
                    "resolution": "TARGET_GAP",
                    "source_ref": file_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
    status = "AVAILABLE" if loaded else ("EMPTY" if not candidates else "INVALID")
    source = _source(
        source_id=source_id,
        truth_plane="GIT",
        truth_owner="StrategyVersion",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        as_of=git_sha,
        freshness_basis="CURRENT_AT_COMMIT",
        adapter_detail=f"loaded={loaded};candidates={len(candidates)}",
    )
    return source, entities, relations, gaps


def _adapt_operational_store(
    root: Path,
    *,
    observed_at: str,
    known_experiment_ids: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_id = "SRC-OPERATIONAL-STORE"
    try:
        path = _ops_store_path(root)
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = path.as_posix()
    except Exception as exc:  # noqa: BLE001
        source_ref = {"kind": "git_path", "value": KERNEL_RELATIVE}
        source = _source(
            source_id=source_id,
            truth_plane="RUNTIME",
            truth_owner="OperationalStore",
            source_ref=source_ref,
            status="INVALID",
            observed_at=observed_at,
            freshness_basis="runtime_readback",
            error=type(exc).__name__,
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=type(exc).__name__,
                    source_ref=source_ref,
                    impact="ops_jobs_unreadable",
                    next_safe_action="FAIL_CLOSED_FOR_SOURCE",
                )
            ],
        )
    source_ref = {"kind": "sqlite", "value": relative}
    if not path.is_file():
        source = _source(
            source_id=source_id,
            truth_plane="RUNTIME",
            truth_owner="OperationalStore",
            source_ref=source_ref,
            status="NOT_PRESENT",
            observed_at=observed_at,
            freshness_basis="runtime_readback",
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_NOT_PRESENT",
                    source_id=source_id,
                    reason="OperationalStore sqlite is not present; this is not an empty healthy runtime",
                    source_ref=source_ref,
                    impact="no_experiment_runtime_jobs",
                    next_safe_action="UNKNOWN",
                )
            ],
        )
    try:
        conn = _sqlite_readonly(path)
        try:
            rows = [dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY job_id")]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        source = _source(
            source_id=source_id,
            truth_plane="RUNTIME",
            truth_owner="OperationalStore",
            source_ref=source_ref,
            status="INVALID",
            observed_at=observed_at,
            freshness_basis="runtime_readback",
            error=type(exc).__name__,
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=type(exc).__name__,
                    source_ref=source_ref,
                    impact="ops_jobs_unreadable",
                    next_safe_action="FAIL_CLOSED_FOR_SOURCE",
                )
            ],
        )
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for row in rows:
        job_id = str(row.get("job_id") or "")
        experiment_id = str(row.get("experiment_id") or "")
        if not job_id:
            continue
        entities.append(
            _entity(
                entity_id=job_id,
                projection_class="EXPERIMENT",
                native_kind="EXPERIMENT_RUN",
                native_state=str(row.get("status") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="RUNTIME",
                contributing_source_ids=[source_id],
                as_of=str(row.get("updated_at") or row.get("created_at") or "") or None,
                observed_at=observed_at,
                evidence_class="NOT_APPLICABLE",
                freshness_status="READBACK",
                freshness_basis="operational_store_updated_at",
                blocker=str(row.get("blocker") or "") or None,
                next_safe_action="UNKNOWN",
                summary=str(row.get("spec_relative") or "") or None,
            )
        )
        if experiment_id:
            relations.append(
                {
                    "relation_type": "JOB_FOR_EXPERIMENT",
                    "from_entity_id": job_id,
                    "to_entity_id": experiment_id,
                    "resolution": "RESOLVED" if experiment_id in known_experiment_ids else "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_CONTRACT_KEY",
                }
            )
    status = "AVAILABLE" if rows else "EMPTY"
    source = _source(
        source_id=source_id,
        truth_plane="RUNTIME",
        truth_owner="OperationalStore",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        freshness_basis="runtime_readback",
        adapter_detail=f"jobs={len(rows)}",
    )
    if status == "EMPTY":
        gaps.append(
            _gap(
                gap_code="SOURCE_EMPTY",
                source_id=source_id,
                reason="OperationalStore exists but has no jobs",
                source_ref=source_ref,
                impact="no_runtime_experiment_jobs",
                next_safe_action="UNKNOWN",
            )
        )
    return source, entities, relations, gaps


def _strategy_entity_id_from_bot(bot: Mapping[str, Any]) -> str | None:
    """Invert PaperPlaneStore.start_bot encoding `{strategy_id}-{strategy_version}`."""

    strategy_id = str(bot.get("strategy_id") or "")
    stored = str(bot.get("strategy_version") or "")
    if not strategy_id or not stored:
        return None
    prefix = f"{strategy_id}-"
    if not stored.startswith(prefix):
        return None
    version = stored[len(prefix) :]
    if not version:
        return None
    return f"{strategy_id}@{version}"


def _adapt_paper_plane(
    root: Path,
    contract: Mapping[str, Any],
    *,
    observed_at: str,
    paper_plane_store: PaperPlaneStore | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_id = "SRC-PAPER-PLANE"
    relative = str(contract["paper_plane_store"]["relative_path"]) or PAPER_PLANE_STORE_RELATIVE
    source_ref = {"kind": "sqlite", "value": relative}
    bots: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    if paper_plane_store is not None:
        source_ref = {"kind": "injected", "value": "PaperPlaneStore"}
        bots = paper_plane_store.bots()
        positions = paper_plane_store.positions()
        events = paper_plane_store.execution_events()
        status = "AVAILABLE" if (bots or positions or events) else "EMPTY"
    else:
        path = root / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            source = _source(
                source_id=source_id,
                truth_plane="RUNTIME",
                truth_owner="PaperPlaneStore",
                source_ref=source_ref,
                status="INVALID",
                observed_at=observed_at,
                freshness_basis="runtime_readback",
                error="PAPER_PLANE_STORE_PATH_UNSAFE",
            )
            return source, [], [], [
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason="PAPER_PLANE_STORE_PATH_UNSAFE",
                    source_ref=source_ref,
                    impact="paper_runtime_unreadable",
                    next_safe_action="FAIL_CLOSED_FOR_SOURCE",
                )
            ]
        if not path.is_file():
            source = _source(
                source_id=source_id,
                truth_plane="RUNTIME",
                truth_owner="PaperPlaneStore",
                source_ref=source_ref,
                status="NOT_PRESENT",
                observed_at=observed_at,
                freshness_basis="runtime_readback",
            )
            return (
                source,
                [],
                [],
                [
                    _gap(
                        gap_code="SOURCE_NOT_PRESENT",
                        source_id=source_id,
                        reason="PaperPlaneStore sqlite is not present; this is not an empty healthy runtime",
                        source_ref=source_ref,
                        impact="no_bot_or_position_runtime",
                        next_safe_action="UNKNOWN",
                    )
                ],
            )
        try:
            conn = _sqlite_readonly(path)
            try:
                bots = [dict(row) for row in conn.execute("SELECT * FROM bot_instances ORDER BY bot_instance_id")]
                positions = [dict(row) for row in conn.execute("SELECT * FROM positions ORDER BY position_id")]
                events = [dict(row) for row in conn.execute("SELECT * FROM execution_events ORDER BY rowid")]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            source = _source(
                source_id=source_id,
                truth_plane="RUNTIME",
                truth_owner="PaperPlaneStore",
                source_ref=source_ref,
                status="INVALID",
                observed_at=observed_at,
                freshness_basis="runtime_readback",
                error=type(exc).__name__,
            )
            return source, [], [], [
                _gap(
                    gap_code="SOURCE_INVALID",
                    source_id=source_id,
                    reason=type(exc).__name__,
                    source_ref=source_ref,
                    impact="paper_runtime_unreadable",
                    next_safe_action="FAIL_CLOSED_FOR_SOURCE",
                )
            ]
        status = "AVAILABLE" if (bots or positions or events) else "EMPTY"
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for bot in bots:
        bot_id = str(bot.get("bot_instance_id") or "")
        if not bot_id:
            continue
        entities.append(
            _entity(
                entity_id=bot_id,
                projection_class="EXECUTION",
                native_kind="BOT_INSTANCE",
                native_state=str(bot.get("status") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="RUNTIME",
                contributing_source_ids=[source_id],
                as_of=str(bot.get("started_at") or "") or None,
                observed_at=observed_at,
                evidence_class=str(bot.get("mode") or "UNKNOWN"),
                freshness_status="READBACK",
                freshness_basis="paper_plane_started_at",
                next_safe_action="UNKNOWN",
                summary=str(bot.get("strategy_version") or "") or None,
            )
        )
        strategy_entity = _strategy_entity_id_from_bot(bot)
        if strategy_entity:
            relations.append(
                {
                    "relation_type": "IMPLEMENTS_STRATEGY_VERSION",
                    "from_entity_id": bot_id,
                    "to_entity_id": strategy_entity,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_CONTRACT_KEY",
                }
            )
        elif bot.get("strategy_id") or bot.get("strategy_version"):
            gaps.append(
                _gap(
                    gap_code="MISSING_EXPLICIT_RELATION",
                    affected_entity_id=bot_id,
                    relation_type="IMPLEMENTS_STRATEGY_VERSION",
                    reason="bot strategy_version is not the documented start_bot encoding {strategy_id}-{strategy_version}",
                    source_ref=source_ref,
                    impact="strategy_version_link_not_proven",
                    next_safe_action="DO_NOT_INFER_STRATEGY_VERSION",
                )
            )
        epoch = bot.get("activation_epoch_id")
        if isinstance(epoch, str) and epoch:
            relations.append(
                {
                    "relation_type": "HAS_ACTIVATION_EPOCH",
                    "from_entity_id": bot_id,
                    "to_entity_id": epoch,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
    for position in positions:
        position_id = str(position.get("position_id") or "")
        if not position_id:
            continue
        entities.append(
            _entity(
                entity_id=position_id,
                projection_class="POSITION",
                native_kind="POSITION",
                native_state=str(position.get("state") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="RUNTIME",
                contributing_source_ids=[source_id],
                as_of=str(position.get("opened_at") or "") or None,
                observed_at=observed_at,
                evidence_class=str(
                    position.get("pnl_evidence_class")
                    or position.get("unrealized_evidence_class")
                    or "UNKNOWN"
                ),
                freshness_status="READBACK",
                freshness_basis="paper_plane_opened_at",
                next_safe_action="UNKNOWN",
                summary=str(position.get("mint") or "") or None,
            )
        )
        bot_id = str(position.get("bot_instance_id") or "")
        if bot_id:
            relations.append(
                {
                    "relation_type": "POSITION_OWNED_BY_BOT",
                    "from_entity_id": position_id,
                    "to_entity_id": bot_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
        signal_id = position.get("signal_decision_id")
        if isinstance(signal_id, str) and signal_id:
            relations.append(
                {
                    "relation_type": "FROM_SIGNAL_DECISION",
                    "from_entity_id": position_id,
                    "to_entity_id": signal_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
        exit_id = position.get("exit_decision_id")
        if isinstance(exit_id, str) and exit_id:
            relations.append(
                {
                    "relation_type": "FROM_EXIT_DECISION",
                    "from_entity_id": position_id,
                    "to_entity_id": exit_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
        strategy_id = str(position.get("strategy_id") or "")
        version_label = str(position.get("strategy_version_label") or "")
        if strategy_id and version_label:
            relations.append(
                {
                    "relation_type": "IMPLEMENTS_STRATEGY_VERSION",
                    "from_entity_id": position_id,
                    "to_entity_id": f"{strategy_id}@{version_label}",
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
    for event in events:
        event_id = str(event.get("event_id") or event.get("id") or "")
        if not event_id:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason="execution event has no event_id; refusing synthetic EXEC-EVENT index identity",
                    source_ref=source_ref,
                    impact="execution_event_not_projected",
                    next_safe_action="DO_NOT_SYNTHESIZE_ID",
                )
            )
            continue
        entities.append(
            _entity(
                entity_id=event_id,
                projection_class="EXECUTION",
                native_kind="EXECUTION_EVENT",
                native_state=str(event.get("event_type") or event.get("kind") or event.get("event_kind") or "") or None,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="RUNTIME",
                contributing_source_ids=[source_id],
                as_of=str(event.get("created_at") or event.get("at") or "") or None,
                observed_at=observed_at,
                evidence_class="UNKNOWN",
                freshness_status="READBACK",
                freshness_basis="paper_plane_execution_event",
                next_safe_action="UNKNOWN",
            )
        )
        bot_id = str(event.get("bot_instance_id") or "")
        if bot_id:
            relations.append(
                {
                    "relation_type": "EVENT_FOR_BOT",
                    "from_entity_id": event_id,
                    "to_entity_id": bot_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
        position_id = str(event.get("position_id") or "")
        if position_id:
            relations.append(
                {
                    "relation_type": "EVENT_FOR_POSITION",
                    "from_entity_id": event_id,
                    "to_entity_id": position_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_FOREIGN_KEY",
                }
            )
    source = _source(
        source_id=source_id,
        truth_plane="RUNTIME",
        truth_owner="PaperPlaneStore",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        freshness_basis="runtime_readback",
        adapter_detail=f"bots={len(bots)};positions={len(positions)};events={len(events)}",
    )
    if status == "EMPTY":
        gaps.append(
            _gap(
                gap_code="SOURCE_EMPTY",
                source_id=source_id,
                reason="PaperPlaneStore exists but has no bots/positions/events",
                source_ref=source_ref,
                impact="no_runtime_execution_objects",
                next_safe_action="UNKNOWN",
            )
        )
    return source, entities, relations, gaps


def _research_store_owned_fields(
    record: Any,
    payload: Mapping[str, Any],
    *,
    as_of: str,
    available: str,
) -> dict[str, Any]:
    fields = {
        "claim / statement": payload.get("claim") or payload.get("statement"),
        "mechanism": payload.get("mechanism"),
        "falsifier": payload.get("falsifier"),
        "trial outcome": payload.get("outcome"),
        "decision kind": payload.get("decision_kind") or payload.get("kind"),
        "promotion_handoff_manifest_sha256": (
            (payload.get("promotion_handoff_manifest") or {}).get("manifest_sha256")
            if isinstance(payload.get("promotion_handoff_manifest"), Mapping)
            else None
        ),
        "effective_at": as_of,
        "first_reliable_available_at": available,
        "evidence class": payload.get("evidence_class"),
        "supersedes": getattr(record, "supersedes_record_id", None),
    }
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _research_entity_id(record: Any, payload: Mapping[str, Any]) -> str | None:
    kind = str(record.record_kind)
    if kind in _RUN_KINDS:
        candidate = payload.get("run_id") or record.run_id or record.entity_id
    elif kind == "HYPOTHESIS_VERSION":
        candidate = payload.get("hypothesis_version_id") or record.hypothesis_version_id or record.entity_id
    elif kind == "TRIAL":
        candidate = payload.get("trial_id") or record.entity_id
    elif kind == "DECISION_EVENT":
        candidate = payload.get("decision_event_id") or record.entity_id
    elif kind == "ACTIVATION_EPOCH":
        candidate = payload.get("activation_epoch_id") or record.entity_id
    else:
        candidate = record.entity_id
    return str(candidate) if candidate else None


def _adapt_research_store(
    *,
    observed_at: str,
    research_store: ResearchRecordReader | None,
    research_data_root: Path | None,
    discovery_status: str | None = None,
    discovery_error: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_id = "SRC-RESEARCH-STORE"
    store = research_store
    source_ref = {"kind": "research_store", "value": "NOT_PRESENT"}
    if store is None and discovery_status == "UNAVAILABLE":
        source = _source(
            source_id=source_id,
            truth_plane="EVIDENCE",
            truth_owner="ResearchStore",
            source_ref={"kind": "research_store", "value": "discovery"},
            status="UNAVAILABLE",
            observed_at=observed_at,
            freshness_basis="evidence_clock",
            error=discovery_error or "RESEARCH_STORE_UNAVAILABLE",
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_UNAVAILABLE",
                    source_id=source_id,
                    reason=discovery_error or "research data root is ambiguous or unreadable",
                    source_ref={"kind": "research_store", "value": "discovery"},
                    impact="research_store_not_opened_by_projection",
                    next_safe_action="RESOLVE_DATA_ROOT_AMBIGUITY",
                )
            ],
        )
    if store is None and research_data_root is not None:
        source_ref = {"kind": "research_store", "value": "provided_data_root"}
        if not research_data_root.is_dir():
            store = None
        else:
            source = _source(
                source_id=source_id,
                truth_plane="EVIDENCE",
                truth_owner="ResearchStore",
                source_ref=source_ref,
                status="UNAVAILABLE",
                observed_at=observed_at,
                freshness_basis="evidence_clock",
                error="RESEARCH_STORE_OPEN_WOULD_WRITE",
            )
            return (
                source,
                [],
                [],
                [
                    _gap(
                        gap_code="SOURCE_UNAVAILABLE",
                        source_id=source_id,
                        reason="ResearchStore constructor mutates a data root; inject an existing store instead of opening from path",
                        source_ref=source_ref,
                        impact="research_store_not_opened_by_projection",
                        next_safe_action="INJECT_EXISTING_RESEARCH_STORE",
                    )
                ],
            )
    if store is None:
        source = _source(
            source_id=source_id,
            truth_plane="EVIDENCE",
            truth_owner="ResearchStore",
            source_ref=source_ref,
            status="NOT_PRESENT",
            observed_at=observed_at,
            freshness_basis="evidence_clock",
        )
        return (
            source,
            [],
            [],
            [
                _gap(
                    gap_code="SOURCE_NOT_PRESENT",
                    source_id=source_id,
                    reason="ResearchStore data root is not present; this is not an empty healthy research plane",
                    source_ref=source_ref,
                    impact="no_research_store_lineage",
                    next_safe_action="UNKNOWN",
                )
            ],
        )
    source_ref = {"kind": "injected", "value": "ResearchStore"} if research_store is not None else source_ref
    try:
        records = list(store.iter_committed_records())
    except Exception as exc:  # noqa: BLE001
        source = _source(
            source_id=source_id,
            truth_plane="EVIDENCE",
            truth_owner="ResearchStore",
            source_ref=source_ref,
            status="INVALID",
            observed_at=observed_at,
            freshness_basis="evidence_clock",
            error=type(exc).__name__,
        )
        return source, [], [], [
            _gap(
                gap_code="SOURCE_INVALID",
                source_id=source_id,
                reason=type(exc).__name__,
                source_ref=source_ref,
                impact="research_store_unreadable",
                next_safe_action="FAIL_CLOSED_FOR_SOURCE",
            )
        ]
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    projected = 0
    skipped: dict[str, int] = {}
    for record in records:
        kind = str(record.record_kind)
        if kind not in _PROJECTED_RESEARCH_KINDS:
            skipped[kind] = skipped.get(kind, 0) + 1
            continue
        try:
            payload = json.loads(record.payload_json)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, Mapping):
            payload = {}
        entity_id = _research_entity_id(record, payload)
        if not entity_id:
            gaps.append(
                _gap(
                    gap_code="MISSING_STABLE_ID",
                    source_id=source_id,
                    reason=f"{record.record_id} missing stable id",
                    source_ref=source_ref,
                    impact="record_not_projected",
                    next_safe_action="FAIL_CLOSED_FOR_RECORD",
                )
            )
            continue
        projection_class, native_kind = _RESEARCH_CLASS[kind]
        as_of = record.effective_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        available = record.first_reliable_available_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        native_state = str(payload.get("status") or kind)
        entities.append(
            _entity(
                entity_id=entity_id,
                projection_class=projection_class,
                native_kind=native_kind,
                native_state=native_state,
                source_owner=source_id,
                source_ref=source_ref,
                truth_plane="EVIDENCE",
                contributing_source_ids=[source_id],
                as_of=as_of,
                observed_at=available,
                evidence_class=str(payload.get("evidence_class") or "UNKNOWN"),
                freshness_status="SOURCE_TIMESTAMP",
                freshness_basis="effective_at/first_reliable_available_at",
                next_safe_action="UNKNOWN",
                summary=str(payload.get("claim") or payload.get("summary") or "") or None,
                source_owned_fields=_research_store_owned_fields(
                    record, payload, as_of=as_of, available=available
                ),
            )
        )
        projected += 1
        hyp = record.hypothesis_version_id
        if isinstance(hyp, str) and hyp and hyp != entity_id:
            relations.append(
                {
                    "relation_type": "RESEARCH_HYPOTHESIS_LINK",
                    "from_entity_id": entity_id,
                    "to_entity_id": hyp,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        run_id = record.run_id
        if isinstance(run_id, str) and run_id and run_id != entity_id:
            relations.append(
                {
                    "relation_type": "RESEARCH_RUN_LINK",
                    "from_entity_id": entity_id,
                    "to_entity_id": run_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        trial_id = payload.get("trial_id")
        if isinstance(trial_id, str) and trial_id and trial_id != entity_id:
            relations.append(
                {
                    "relation_type": "RESEARCH_TRIAL_LINK",
                    "from_entity_id": entity_id,
                    "to_entity_id": trial_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
        target_id = payload.get("target_entity_id")
        target_kind = payload.get("target_native_kind")
        if (
            kind == "DECISION_EVENT"
            and isinstance(target_id, str)
            and target_id
            and target_id != entity_id
            and target_kind in {None, "EXPERIMENT_SPEC"}
        ):
            relations.append(
                {
                    "relation_type": "DECISION_FOR_EXPERIMENT",
                    "from_entity_id": entity_id,
                    "to_entity_id": target_id,
                    "resolution": "TARGET_GAP",
                    "source_ref": source_ref,
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                }
            )
    status = "AVAILABLE" if projected else ("EMPTY" if not records else "AVAILABLE")
    detail = f"projected={projected};unprojected={skipped}" if skipped else f"projected={projected}"
    source = _source(
        source_id=source_id,
        truth_plane="EVIDENCE",
        truth_owner="ResearchStore",
        source_ref=source_ref,
        status=status,
        observed_at=observed_at,
        freshness_basis="evidence_clock",
        adapter_detail=detail,
    )
    if projected == 0 and not records:
        gaps.append(
            _gap(
                gap_code="SOURCE_EMPTY",
                source_id=source_id,
                reason="ResearchStore has no committed records",
                source_ref=source_ref,
                impact="no_research_store_lineage",
                next_safe_action="UNKNOWN",
            )
        )
    return source, entities, relations, gaps


def _merge_entities(entities: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for entity in entities:
        key = (
            entity["projection_class"],
            entity["native_kind"],
            entity["entity_id"],
            entity["truth_plane"],
        )
        grouped.setdefault(key, []).append(entity)
    merged: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seen_ids: dict[str, set[str]] = {}
    for key, group in grouped.items():
        entity_id = key[2]
        plane = key[3]
        seen_ids.setdefault(entity_id, set()).add(plane)
        if len(group) == 1:
            merged.append(group[0])
            continue
        states = {item.get("native_state") for item in group}
        evidence = {item.get("evidence_class") for item in group}
        sources: list[str] = []
        refs: list[str] = []
        for item in group:
            for source_id in item.get("contributing_source_ids") or []:
                if source_id not in sources:
                    sources.append(source_id)
            ref = item.get("source_ref") or {}
            encoded = f"{ref.get('kind')}={ref.get('value')}"
            if encoded not in refs:
                refs.append(encoded)
        head = dict(group[0])
        head["contributing_source_ids"] = sources
        if len(states) > 1 or len(evidence) > 1:
            head["native_state"] = None
            head["display_state"] = "CONFLICT"
            head["state_derivation"] = "UNKNOWN"
            head["summary"] = (
                "CONFLICT no timestamp winner; native_states="
                + "|".join(sorted(str(item) for item in states))
                + "; source_refs="
                + "|".join(refs)
            )
            gaps.append(
                _gap(
                    gap_code="STATE_CONFLICT" if len(states) > 1 else "IDENTITY_CONFLICT",
                    affected_entity_id=entity_id,
                    reason="decision-relevant fields conflict across contributing sources; no timestamp winner",
                    source_ref=head["source_ref"],
                    impact="IDENTITY_OR_STATE_CONFLICT",
                    next_safe_action="FAIL_CLOSED_FOR_ENTITY",
                )
            )
        merged.append(head)
    for entity_id, planes in seen_ids.items():
        if len(planes) < 2:
            continue
        sample = next(item for item in merged if item["entity_id"] == entity_id)
        gaps.append(
            _gap(
                gap_code="IDENTITY_CONFLICT",
                affected_entity_id=entity_id,
                reason="same entity_id appears on multiple truth planes without a proving identity contract; entities kept separate",
                source_ref=sample["source_ref"],
                impact="IDENTITY_OR_STATE_CONFLICT",
                next_safe_action="DO_NOT_UNIFY_ACROSS_PLANES",
            )
        )
    merged.sort(
        key=lambda item: (
            item["projection_class"],
            item["native_kind"],
            item["entity_id"],
            item["truth_plane"],
        )
    )
    return merged, gaps


def _entity_id_planes(entities: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    planes: dict[str, set[str]] = {}
    for item in entities:
        planes.setdefault(str(item["entity_id"]), set()).add(str(item["truth_plane"]))
    return planes


def _finalize_relations(
    relations: Iterable[dict[str, Any]],
    id_planes: Mapping[str, set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    finalized: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for relation in relations:
        method = str(relation.get("derivation_method") or "")
        if method not in {
            "EXPLICIT_SOURCE_FIELD",
            "EXPLICIT_FOREIGN_KEY",
            "EXPLICIT_CATALOG_RELATION",
            "EXPLICIT_CONTRACT_KEY",
        }:
            raise LifecycleProjectionError("INFERRED_RELATION_FORBIDDEN")
        from_id = str(relation["from_entity_id"])
        to_id = str(relation["to_entity_id"])
        relation_type = str(relation["relation_type"])
        key = (relation_type, from_id, to_id, method)
        if key in seen:
            continue
        seen.add(key)
        from_count = len(id_planes.get(from_id, ()))
        to_count = len(id_planes.get(to_id, ()))
        if from_count >= 2 or to_count >= 2:
            # RESOLVED requires unambiguous endpoint identity; do not pick a plane.
            resolution = "CONFLICT"
        elif from_count == 0:
            resolution = "SOURCE_GAP"
        elif to_count == 1:
            resolution = "RESOLVED"
        else:
            resolution = "TARGET_GAP"
        item = {
            "relation_type": relation_type,
            "from_entity_id": from_id,
            "to_entity_id": to_id,
            "resolution": resolution,
            "source_ref": relation["source_ref"],
            "derivation_method": method,
        }
        finalized.append(item)
        if resolution == "TARGET_GAP":
            gaps.append(
                _gap(
                    gap_code="RELATION_TARGET_GAP",
                    affected_entity_id=from_id,
                    relation_type=relation_type,
                    reason=f"target {to_id} is not materialized by an accepted owner",
                    source_ref=relation["source_ref"],
                    impact="explicit_edge_retained_without_synthetic_target",
                    next_safe_action="DO_NOT_SYNTHESIZE_TARGET",
                )
            )
        elif resolution == "CONFLICT":
            ambiguous = from_id if from_count >= 2 else to_id
            gaps.append(
                _gap(
                    gap_code="IDENTITY_CONFLICT",
                    affected_entity_id=ambiguous,
                    relation_type=relation_type,
                    reason=(
                        "relation endpoint identity is ambiguous across truth planes; "
                        "RESOLVED requires unambiguous identity in current projection"
                    ),
                    source_ref=relation["source_ref"],
                    impact="IDENTITY_OR_STATE_CONFLICT",
                    next_safe_action="DO_NOT_UNIFY_ACROSS_PLANES",
                )
            )
    finalized.sort(
        key=lambda item: (
            item["relation_type"],
            item["from_entity_id"],
            item["to_entity_id"],
            item["derivation_method"],
        )
    )
    return finalized, gaps


def build_lifecycle_projection(
    root: Path,
    *,
    paper_plane_store: PaperPlaneStore | None = None,
    research_store: ResearchRecordReader | None = None,
    research_data_root: Path | None = None,
    research_discovery_status: str | None = None,
    research_discovery_error: str | None = None,
    projected_at: str | None = None,
    git_sha: str | None = None,
) -> dict[str, Any]:
    contract = load_projection_contract(root)
    observed_at = projected_at or _utc_now()
    sha = git_sha if git_sha is not None else _git_sha(root)
    sources: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    legacy_sources, legacy_gaps = _adapt_legacy_registries(root, contract, observed_at, sha)
    sources.extend(legacy_sources)
    gaps.extend(legacy_gaps)

    neg_source, neg_entities, neg_relations, neg_gaps = _adapt_negative_decisions(
        root, contract, observed_at, sha
    )
    sources.append(neg_source)
    entities.extend(neg_entities)
    relations.extend(neg_relations)
    gaps.extend(neg_gaps)

    trial_source, trial_entities, trial_relations, trial_gaps = _adapt_global_trial_ledger(
        root, contract, observed_at, sha
    )
    sources.append(trial_source)
    entities.extend(trial_entities)
    relations.extend(trial_relations)
    gaps.extend(trial_gaps)

    spec_source, spec_entities, spec_relations, spec_gaps = _adapt_experiment_specs(
        root, contract, observed_at, sha
    )
    sources.append(spec_source)
    entities.extend(spec_entities)
    relations.extend(spec_relations)
    gaps.extend(spec_gaps)

    strat_source, strat_entities, strat_relations, strat_gaps = _adapt_strategy_versions(
        root, contract, observed_at, sha
    )
    sources.append(strat_source)
    entities.extend(strat_entities)
    relations.extend(strat_relations)
    gaps.extend(strat_gaps)

    known_experiments = {
        item["entity_id"] for item in spec_entities if item["native_kind"] == "EXPERIMENT_SPEC"
    }
    ops_source, ops_entities, ops_relations, ops_gaps = _adapt_operational_store(
        root, observed_at=observed_at, known_experiment_ids=known_experiments
    )
    sources.append(ops_source)
    entities.extend(ops_entities)
    relations.extend(ops_relations)
    gaps.extend(ops_gaps)

    paper_source, paper_entities, paper_relations, paper_gaps = _adapt_paper_plane(
        root, contract, observed_at=observed_at, paper_plane_store=paper_plane_store
    )
    sources.append(paper_source)
    entities.extend(paper_entities)
    relations.extend(paper_relations)
    gaps.extend(paper_gaps)

    research_source, research_entities, research_relations, research_gaps = _adapt_research_store(
        observed_at=observed_at,
        research_store=research_store,
        research_data_root=research_data_root,
        discovery_status=research_discovery_status,
        discovery_error=research_discovery_error,
    )
    sources.append(research_source)
    entities.extend(research_entities)
    relations.extend(research_relations)
    gaps.extend(research_gaps)

    merged_entities, merge_gaps = _merge_entities(entities)
    gaps.extend(merge_gaps)
    id_planes = _entity_id_planes(merged_entities)
    known_ids = set(id_planes)
    finalized_relations, relation_gaps = _finalize_relations(relations, id_planes)
    gaps.extend(relation_gaps)

    # Drop spec-declared JOB_FOR_EXPERIMENT SOURCE_GAP when a runtime job already emitted the same edge.
    runtime_jobs = {
        (item["from_entity_id"], item["to_entity_id"])
        for item in finalized_relations
        if item["relation_type"] == "JOB_FOR_EXPERIMENT" and item["from_entity_id"] in known_ids
    }
    cleaned_relations = []
    for item in finalized_relations:
        key = (item["from_entity_id"], item["to_entity_id"])
        if (
            item["relation_type"] == "JOB_FOR_EXPERIMENT"
            and item["resolution"] == "SOURCE_GAP"
            and key in runtime_jobs
            and item["from_entity_id"] not in known_ids
        ):
            continue
        cleaned_relations.append(item)

    unique_gaps: list[dict[str, Any]] = []
    seen_gaps: set[tuple[Any, ...]] = set()
    for item in gaps:
        fingerprint = (
            item["gap_code"],
            item.get("affected_entity_id"),
            item.get("source_id"),
            item.get("relation_type"),
            item["reason"],
        )
        if fingerprint in seen_gaps:
            continue
        seen_gaps.add(fingerprint)
        unique_gaps.append(item)
    unique_gaps.sort(
        key=lambda item: (
            item["gap_code"],
            str(item.get("affected_entity_id") or ""),
            str(item.get("source_id") or ""),
            item["reason"],
        )
    )
    sources.sort(key=lambda item: item["source_id"])

    available = all(item["status"] in {"AVAILABLE", "EMPTY"} for item in sources)
    completeness = "PARTIAL"
    if not sources:
        completeness = "UNAVAILABLE"
    elif available and not unique_gaps:
        completeness = "COMPLETE"

    payload = {
        "schema": "smial.owner-lifecycle-projection",
        "schema_version": "1.0",
        "projection_id": PROJECTION_ID,
        "projected_at": observed_at,
        "completeness": completeness,
        "authority_granted": False,
        "git_sha": sha,
        "sources": sources,
        "entities": merged_entities,
        "relations": cleaned_relations,
        "gaps": unique_gaps,
    }
    return validate_lifecycle_projection(payload, root=root)


def render_lifecycle_projection_table(projection: Mapping[str, Any]) -> str:
    lines = [
        f"completeness={projection['completeness']} authority_granted={projection['authority_granted']}",
        f"entities={len(projection['entities'])} relations={len(projection['relations'])} gaps={len(projection['gaps'])}",
        "",
        "entity_id | class | kind | state | plane | source",
    ]
    for item in projection["entities"]:
        lines.append(
            " | ".join(
                [
                    str(item["entity_id"]),
                    str(item["projection_class"]),
                    str(item["native_kind"]),
                    str(item.get("native_state") or ""),
                    str(item["truth_plane"]),
                    str(item["source_owner"]),
                ]
            )
        )
    lines.extend(["", "from | type | to | resolution | method"])
    for item in projection["relations"]:
        lines.append(
            " | ".join(
                [
                    str(item["from_entity_id"]),
                    str(item["relation_type"]),
                    str(item["to_entity_id"]),
                    str(item["resolution"]),
                    str(item["derivation_method"]),
                ]
            )
        )
    return "\n".join(lines) + "\n"
