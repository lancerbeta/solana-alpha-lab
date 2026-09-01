"""Manifest-last observation panel publication into the Research Data Plane."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    ObservationPrimitiveRegistry,
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)
from solana_alpha_lab.storage.manifests import (
    build_dataset_manifest,
    build_partition_manifest,
    compute_dataset_manifest_id,
)

SCHEMA_ID = "SCHEMA-OBSERVATION-PANEL-INDEX-001"
PANEL_SCHEMA_RELATIVE = "catalog/schemas/observation_panel_snapshot_v1.schema.json"
MEMBER_SCHEMA_ID = "SCHEMA-OBSERVATION-PANEL-MEMBER-001"
PRODUCER_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"


class ObservationPanelPublisherError(ValueError):
    """Typed panel publication failure."""


class PublicationFault(ObservationPanelPublisherError):
    """Deterministic fault injection after a publication stage."""


STAGE_ARTIFACTS = "ARTIFACTS"
STAGE_RDP_OBS = "RDP_OBSERVATION_BATCH"
STAGE_RDP_MEMBER = "RDP_MEMBER_BATCH"
STAGE_MANIFEST = "MANIFEST"
STAGE_MARKER = "MARKER"


def _schema_sha256(root: Path) -> str:
    path = root / PANEL_SCHEMA_RELATIVE
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([dict(row) for row in rows])
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp)
    payload = tmp.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if path.is_file():
        try:
            existing_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        finally:
            tmp.unlink(missing_ok=True)
        if existing_digest != digest:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
    else:
        tmp.replace(path)
    return digest


def _publish_immutable_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != payload:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        return
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(payload)
    try:
        if path.is_file():
            if path.read_bytes() != payload:
                raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        else:
            tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _registered_output_fields(
    registry: ObservationPrimitiveRegistry,
    primitive_id: str,
) -> dict[str, str]:
    try:
        primitive = registry.require_primitive(primitive_id)
        return {
            str(field_id): str(registry.require_field(str(field_id))["value_kind"])
            for field_id in primitive.get("output_field_ids") or []
        }
    except PrimitiveRegistryError as exc:
        raise ObservationPanelPublisherError("TYPED_VALUE_REGISTRY_INVALID") from exc


def _normalize_observation_row(
    row: Mapping[str, Any],
    *,
    registry: ObservationPrimitiveRegistry | None = None,
) -> dict[str, Any]:
    normalized = dict(row)
    field_values = normalized.get("field_values")
    primitive_id = str(normalized.get("primitive_id") or "")
    declared = (
        _registered_output_fields(registry, primitive_id)
        if registry is not None and primitive_id
        else {}
    )
    supplied = field_values if isinstance(field_values, list) else []
    supplied_by_id: dict[str, dict[str, Any]] = {}
    for value in supplied:
        if not isinstance(value, Mapping):
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        required = {
            "field_id",
            "value_kind",
            "typed_value_or_null",
            "state",
            "missing_reason",
            "primitive_id",
            "point_id",
            "event_time",
            "first_reliable_available_at",
            "request_sha256",
            "call_occurrence_id",
        }
        if not required.issubset(value):
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        field_id = str(value["field_id"])
        if field_id in supplied_by_id:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        if (
            field_id not in declared
            or str(value["value_kind"]) != str(declared[field_id])
            or str(value["primitive_id"]) != primitive_id
            or str(value["point_id"]) != str(normalized.get("point_id"))
            or value["event_time"] != normalized.get("event_time")
            or value["first_reliable_available_at"]
            != normalized.get("first_reliable_available_at")
            or value["request_sha256"] != normalized.get("request_sha256")
            or value["call_occurrence_id"] != normalized.get("call_occurrence_id")
        ):
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        supplied_by_id[field_id] = dict(value)
    if any(field_id not in declared for field_id in supplied_by_id):
        raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
    normalized_values: list[dict[str, Any]] = []
    ordered_fields = list(declared.items())
    for field_id, value_kind in ordered_fields:
        value = supplied_by_id.get(field_id)
        if value is None:
            if field_id == "FIELD-QUOTE-BUY-OUT-AMOUNT-001":
                typed_value = normalized.get("buy_out_amount")
            elif field_id == "FIELD-QUOTE-SELL-OUT-AMOUNT-001":
                typed_value = normalized.get("sell_out_amount")
            else:
                typed_value = None
            present = typed_value is not None and normalized.get("state") == "OBSERVED"
            value = {
                "field_id": field_id,
                "value_kind": value_kind,
                "typed_value_or_null": str(typed_value) if present else None,
                "state": "OBSERVED"
                if present
                else (
                    str(normalized.get("state"))
                    if str(normalized.get("state") or "") != "OBSERVED"
                    else "MISSING_TYPED"
                ),
                "missing_reason": None
                if present
                else normalized.get("missing_reason") or "FIELD_ABSENT",
                "primitive_id": primitive_id,
                "point_id": normalized.get("point_id"),
                "event_time": normalized.get("event_time"),
                "first_reliable_available_at": normalized.get(
                    "first_reliable_available_at"
                ),
                "request_sha256": normalized.get("request_sha256"),
                "call_occurrence_id": normalized.get("call_occurrence_id"),
            }
        typed = value.get("typed_value_or_null")
        state = str(value.get("state") or "")
        if state not in {
            "OBSERVED",
            "MISSING_TYPED",
            "EXCLUDED_AMBIGUOUS",
            "DISAPPEARED",
            "CENSORED",
            "CENSORED_LATE",
            "DEPENDENCY_MISSING",
            "IN_FLIGHT_CALL_INDETERMINATE",
            "BLOCKED_BUDGET",
            "X_POPULATION_INELIGIBLE",
        }:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        row_state = str(normalized.get("state") or "")
        if row_state and row_state != "OBSERVED" and state != row_state:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        if state == "OBSERVED" and typed is None:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        if state != "OBSERVED" and typed is not None:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        if state == "OBSERVED" and value.get("missing_reason") is not None:
            raise ObservationPanelPublisherError("TYPED_VALUE_INVALID")
        normalized_values.append(value)
    normalized["field_values"] = normalized_values
    return normalized


def _clocks_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    fallback: datetime,
) -> tuple[datetime | None, datetime | None, datetime, datetime]:
    events: list[datetime] = []
    available: list[datetime] = []
    for row in rows:
        event_raw = row.get("event_time")
        if isinstance(event_raw, str) and event_raw:
            events.append(parse_utc(event_raw))
        avail_raw = row.get("first_reliable_available_at")
        if isinstance(avail_raw, str) and avail_raw:
            available.append(parse_utc(avail_raw))
    min_event = min(events) if events else None
    max_event = max(events) if events else None
    min_available = min(available) if available else fallback
    max_available = max(available) if available else fallback
    return min_event, max_event, min_available, max_available


def _research_event(
    *,
    record_id: str,
    record_kind: RecordKind,
    entity_id: str,
    payload: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    run_id: str | None,
    transaction_id: str,
    hypothesis_version_id: str | None = None,
    supersedes_record_id: str | None = None,
) -> ResearchEvent:
    payload_json = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=supersedes_record_id,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=PRODUCER_CAPABILITY,
        producer_git_sha=producer_git_sha,
        created_at=now,
    )


def persist_observation_schedule(
    *,
    data_root: Path,
    schedule: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    activation_id: str | None = None,
) -> None:
    digest = str(schedule["schedule_sha256"])
    txn = f"RESEARCH-TXN-OBS-SCHED-{digest[:12].upper()}"
    event = _research_event(
        record_id=f"OBS-SCHED-{digest[:16].upper()}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE,
        entity_id=digest,
        payload={
            "schedule_sha256": digest,
            "schedule_key": schedule.get("schedule_key"),
            "state": "COMPILED",
            "schedule": dict(schedule),
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=txn,
    )
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=txn)
    except Exception:
        existing = list(store.iter_committed_records())
        if any(
            item.record_id == event.record_id
            and item.payload_sha256 == event.payload_sha256
            for item in existing
        ):
            return
        if any(item.record_id == event.record_id for item in existing):
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        raise


def persist_panel_snapshot_binding(
    *,
    data_root: Path,
    schedule: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    evidence_role: str | None,
    hypothesis_version_id: str | None,
    run_id: str | None,
) -> None:
    digest = str(schedule["schedule_sha256"])
    snapshot_schedule = str(snapshot.get("schedule_sha256") or "")
    snapshot_basis = {
        key: snapshot.get(key)
        for key in (
            "schema",
            "schema_version",
            "schedule_sha256",
            "availability_cutoff",
            "dataset_manifest_ids",
            "dataset_fingerprints",
        )
    }
    snapshot_sha = str(snapshot.get("snapshot_sha256") or "")
    if (
        len(snapshot_schedule) != 64
        or any(character not in "0123456789abcdef" for character in snapshot_schedule)
        or canonical_sha256(snapshot_basis)
        != snapshot_sha
        or str(snapshot.get("snapshot_id") or "")
        != f"SNAP-OBS-{snapshot_sha[:12].upper()}"
    ):
        raise ObservationPanelPublisherError("SNAPSHOT_IDENTITY_MISMATCH")
    snapshot_id = str(snapshot["snapshot_id"])
    binding_digest = canonical_sha256(
        {
            "schedule_sha256": digest,
            "snapshot_sha256": snapshot_sha,
        }
    )
    bind_id = f"BIND-OBS-{binding_digest[:12].upper()}"
    txn = f"RESEARCH-TXN-OBS-BIND-{binding_digest[:12].upper()}"
    events = [
        _research_event(
            record_id=f"OBS-SNAP-{snapshot_sha[:16].upper()}",
            record_kind=RecordKind.OBSERVATION_PANEL_SNAPSHOT,
            entity_id=digest,
            payload=dict(snapshot),
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=run_id,
            transaction_id=txn,
            hypothesis_version_id=hypothesis_version_id,
        ),
        _research_event(
            record_id=f"OBS-BIND-{binding_digest[:16].upper()}",
            record_kind=RecordKind.OBSERVATION_SCHEDULE_BINDING,
            entity_id=digest,
            payload={
                "binding_id": bind_id,
                "schedule_sha256": digest,
                "snapshot_sha256": snapshot_sha,
                "snapshot_id": snapshot_id,
                "hypothesis_version_id": hypothesis_version_id,
                "evidence_role": evidence_role,
            },
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=run_id,
            transaction_id=txn,
            hypothesis_version_id=hypothesis_version_id,
        ),
    ]
    store = ResearchStore(data_root)
    try:
        existing_by_id = {
            item.record_id: item for item in store.iter_committed_records()
        }
        missing: list[ResearchEvent] = []
        for event in events:
            existing = existing_by_id.get(event.record_id)
            if existing is None:
                missing.append(event)
            elif existing.payload_sha256 != event.payload_sha256:
                raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        if not missing:
            return
        store.append(missing, transaction_id=txn)
    except ObservationPanelPublisherError:
        raise
    except Exception:
        existing_by_id = {
            item.record_id: item for item in store.iter_committed_records()
        }
        if all(
            event.record_id in existing_by_id
            and existing_by_id[event.record_id].payload_sha256 == event.payload_sha256
            for event in events
        ):
            return
        raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")


def pending_observation_binding_sha256(payload: Mapping[str, Any]) -> str:
    identity = {
        "hypothesis_version_id": payload.get("hypothesis_version_id"),
        "hypothesis_definition_sha256": payload.get("hypothesis_definition_sha256"),
        "experiment_spec_sha256": payload.get("experiment_spec_sha256"),
        "run_key_sha256": payload.get("run_key_sha256"),
        "requested_schedule_sha256": payload.get("requested_schedule_sha256"),
        "covering_schedule_sha256": payload.get("covering_schedule_sha256"),
        "requested_availability_semantics": payload.get(
            "requested_availability_semantics"
        ),
        "required_x_point": payload.get("required_x_point"),
        "required_y_points": payload.get("required_y_points"),
        "evidence_role_basis": payload.get("evidence_role_basis"),
    }
    return canonical_sha256(identity)


def persist_pending_observation_binding(
    *,
    data_root: Path,
    payload: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    identity = dict(payload)
    identity.setdefault("state", "WAITING_FOR_PANEL")
    digest = pending_observation_binding_sha256(identity)
    identity["pending_binding_sha256"] = digest
    identity["state"] = "WAITING_FOR_PANEL"
    record_id = f"OBS-PEND-{digest[:16].upper()}"
    txn = f"RESEARCH-TXN-OBS-PEND-{digest[:12].upper()}"
    event = _research_event(
        record_id=record_id,
        record_kind=RecordKind.OBSERVATION_SCHEDULE_BINDING,
        entity_id=digest,
        payload=identity,
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=run_id,
        transaction_id=txn,
        hypothesis_version_id=identity.get("hypothesis_version_id")
        if isinstance(identity.get("hypothesis_version_id"), str)
        else None,
    )
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=txn)
        return {"terminal": "PENDING_BOUND", "pending_binding_sha256": digest}
    except Exception:
        existing = list(store.iter_committed_records())
        match = next((item for item in existing if item.record_id == event.record_id), None)
        if match is not None and match.payload_sha256 == event.payload_sha256:
            return {"terminal": "PENDING_REPLAY", "pending_binding_sha256": digest}
        if match is not None:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        raise


def satisfy_pending_observation_binding(
    *,
    data_root: Path,
    pending_binding_sha256: str,
    snapshot_sha256: str,
    now: datetime,
    producer_git_sha: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    waiting = None
    for item in load_pending_observation_bindings(data_root):
        if item["pending_binding_sha256"] == pending_binding_sha256:
            waiting = item
            break
    if waiting is None:
        raise ObservationPanelPublisherError("PENDING_BINDING_MISSING")
    if waiting.get("state") == "SATISFIED" and waiting.get("snapshot_sha256") == snapshot_sha256:
        return {
            "terminal": "PENDING_SATISFIED_REPLAY",
            "pending_binding_sha256": pending_binding_sha256,
            "snapshot_sha256": snapshot_sha256,
        }
    satisfied = dict(waiting)
    satisfied["state"] = "SATISFIED"
    satisfied["snapshot_sha256"] = snapshot_sha256
    record_id = f"OBS-PEND-SAT-{pending_binding_sha256[:16].upper()}"
    txn = f"RESEARCH-TXN-OBS-PEND-SAT-{pending_binding_sha256[:12].upper()}"
    event = _research_event(
        record_id=record_id,
        record_kind=RecordKind.OBSERVATION_SCHEDULE_BINDING,
        entity_id=pending_binding_sha256,
        payload=satisfied,
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=run_id,
        transaction_id=txn,
        hypothesis_version_id=satisfied.get("hypothesis_version_id")
        if isinstance(satisfied.get("hypothesis_version_id"), str)
        else None,
        supersedes_record_id=f"OBS-PEND-{pending_binding_sha256[:16].upper()}",
    )
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=txn)
        return {
            "terminal": "PENDING_SATISFIED",
            "pending_binding_sha256": pending_binding_sha256,
            "snapshot_sha256": snapshot_sha256,
        }
    except Exception:
        existing = list(store.iter_committed_records())
        match = next((item for item in existing if item.record_id == event.record_id), None)
        if match is not None and match.payload_sha256 == event.payload_sha256:
            return {
                "terminal": "PENDING_SATISFIED_REPLAY",
                "pending_binding_sha256": pending_binding_sha256,
                "snapshot_sha256": snapshot_sha256,
            }
        if match is not None:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        raise


def load_pending_observation_bindings(data_root: Path) -> list[dict[str, Any]]:
    store = ResearchStore(data_root)
    latest: dict[str, dict[str, Any]] = {}
    for record in store.iter_committed_records():
        if str(record.record_kind) != "OBSERVATION_SCHEDULE_BINDING":
            continue
        payload = json.loads(record.payload_json)
        if not isinstance(payload, Mapping):
            continue
        digest = str(payload.get("pending_binding_sha256") or "")
        if len(digest) != 64:
            continue
        latest[digest] = dict(payload)
    return [latest[key] for key in sorted(latest)]


def _job_path(data_root: Path, content: str) -> Path:
    return data_root / "datasets" / "publication_jobs" / f"{content}.json"


def _load_job(data_root: Path, content: str) -> dict[str, Any] | None:
    path = _job_path(data_root, content)
    if path.is_file() is False:
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ObservationPanelPublisherError("PUBLICATION_JOB_INVALID")
    return loaded


def _save_job(data_root: Path, content: str, payload: Mapping[str, Any]) -> None:
    path = _job_path(data_root, content)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _rdp_has(data_root: Path, record_id: str, payload_sha256: str | None = None) -> bool:
    store = ResearchStore(data_root)
    for item in store.iter_committed_records():
        if item.record_id != record_id:
            continue
        if payload_sha256 is not None and item.payload_sha256 != payload_sha256:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        return True
    return False


def _append_event(data_root: Path, event: ResearchEvent) -> None:
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=event.transaction_id)
    except Exception:
        if _rdp_has(data_root, event.record_id, event.payload_sha256):
            return
        raise


def _maybe_fault(fault_after: str | None, stage: str) -> None:
    if fault_after == stage:
        raise PublicationFault(stage)


def publish_observation_batch(
    *,
    data_root: Path,
    root: Path,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
    members: Sequence[Mapping[str, Any]] | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    fault_after: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    now = now.astimezone(UTC)
    if not members:
        raise ObservationPanelPublisherError("PARTIAL_DATASET_FORBIDDEN")
    digest = str(schedule["schedule_sha256"])
    input_observations = list(observations or [])
    try:
        registry = load_observation_primitive_registry(root)
    except PrimitiveRegistryError as exc:
        raise ObservationPanelPublisherError("TYPED_VALUE_REGISTRY_INVALID") from exc
    rows = [
        _normalize_observation_row(item, registry=registry)
        for item in input_observations
    ]
    member_rows = [dict(item) for item in members]
    # Keep the publication identity bound to the caller's immutable input
    # rows.  Normalization enriches the durable representation but must not
    # make a retry after a calendar boundary look like a new scientific batch.
    computed_content = canonical_sha256(
        {
            "members": member_rows,
            "observations": [dict(item) for item in input_observations],
        }
    )
    content = content_sha256 or computed_content
    if len(content) != 64 or any(
        character not in "0123456789abcdef" for character in content
    ):
        raise ObservationPanelPublisherError("CONTENT_IDENTITY_INVALID")
    job = _load_job(data_root, content)
    if job is not None and (
        str(job.get("schedule_sha256") or "") != digest
        or str(job.get("activation_id") or "") != str(activation_id)
    ):
        raise ObservationPanelPublisherError("PUBLICATION_JOB_CONFLICT")
    if content_sha256 is not None and content != computed_content:
        if (
            job is None
            or job.get("content_sha256") != content
            or job.get("observations") != [dict(item) for item in input_observations]
            or job.get("members") != [dict(item) for item in members]
        ):
            raise ObservationPanelPublisherError("CONTENT_IDENTITY_INVALID")
    job = job or {"stage": None, "content_sha256": content}
    utc_day = str(job.get("utc_day") or now.strftime("%Y%m%d"))
    dataset_id = f"observation-panel-{digest[:12]}"
    dataset_version = str(job.get("dataset_version") or f"{utc_day}-1-{content[:12]}")
    dataset_manifest_id = str(
        job.get("dataset_manifest_id") or compute_dataset_manifest_id(dataset_id, dataset_version)
    )
    manifests_dir = data_root / "datasets" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / f"{dataset_manifest_id}.json"
    published_path = manifests_dir / f"{dataset_manifest_id}.published"
    obs_record_id = f"OBS-BATCH-{content[:16].upper()}"
    member_record_id = f"OBS-MEMB-{content[:16].upper()}"

    if published_path.is_file():
        if not _rdp_has(data_root, obs_record_id) or not _rdp_has(data_root, member_record_id):
            raise ObservationPanelPublisherError("PUBLICATION_INCOMPLETE")
        loaded = json.loads(published_path.read_text(encoding="utf-8"))
        return {
            "dataset_manifest_id": dataset_manifest_id,
            "dataset_fingerprint": loaded.get("dataset_fingerprint"),
            "replay": True,
        }

    created_at = parse_utc(str(job["created_at"])) if job.get("created_at") else now
    min_event, max_event, min_available, max_available = _clocks_from_rows(
        rows,
        fallback=created_at,
    )
    if max_available > created_at:
        created_at = max_available
    parquet_rel = str(
        job.get("parquet_rel") or f"datasets/parquet/{dataset_manifest_id}/observations.parquet"
    )
    member_rel = str(
        job.get("member_rel") or f"datasets/parquet/{dataset_manifest_id}/members.parquet"
    )
    parquet_path = data_root / parquet_rel
    member_path = data_root / member_rel

    if job.get("stage") is None:
        file_sha256 = _write_parquet(parquet_path, rows)
        member_sha256 = _write_parquet(member_path, member_rows)
        existing_obs = parquet_path.read_bytes() if parquet_path.is_file() else b""
        if hashlib.sha256(existing_obs).hexdigest() != file_sha256:
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")
        job = {
            "stage": STAGE_ARTIFACTS,
            "content_sha256": content,
            "file_sha256": file_sha256,
            "member_sha256": member_sha256,
            "observation_count": len(rows),
            "member_count": len(member_rows),
            "dataset_manifest_id": dataset_manifest_id,
            "utc_day": utc_day,
            "dataset_version": dataset_version,
            "parquet_rel": parquet_rel.replace("\\", "/"),
            "member_rel": member_rel.replace("\\", "/"),
            "created_at": render_utc(created_at),
            "sampling": dict(schedule.get("sampling") or {}),
            "schedule_sha256": digest,
            "activation_id": activation_id,
            "observations": [dict(item) for item in input_observations],
            "normalized_observations": rows,
            "members": member_rows,
        }
        _save_job(data_root, content, job)
        _maybe_fault(fault_after, "AFTER_ARTIFACTS")

    for artifact_path, hash_key in (
        (parquet_path, "file_sha256"),
        (member_path, "member_sha256"),
    ):
        if (
            artifact_path.is_file() is False
            or hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            != str(job.get(hash_key))
        ):
            raise ObservationPanelPublisherError("CANONICAL_TARGET_CONFLICT")

    partition = build_partition_manifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=f"utc-day-{utc_day}",
        logical_location=parquet_rel.replace("\\", "/"),
        file_sha256=str(job["file_sha256"]),
        content_sha256=content,
        row_count=len(rows),
        min_event_time=min_event,
        max_event_time=max_event,
        min_available_to_strategy_at=min_available,
        max_available_to_strategy_at=max_available,
        first_reliable_available_at=max_available,
        created_at=created_at,
    )
    member_partition = build_partition_manifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=f"utc-day-{utc_day}-members",
        logical_location=member_rel.replace("\\", "/"),
        file_sha256=str(job["member_sha256"]),
        content_sha256=content,
        row_count=len(member_rows),
        min_event_time=min_event,
        max_event_time=max_event,
        min_available_to_strategy_at=min_available,
        max_available_to_strategy_at=max_available,
        first_reliable_available_at=max_available,
        created_at=created_at,
    )

    obs_event = _research_event(
        record_id=obs_record_id,
        record_kind=RecordKind.OBSERVATION_BATCH,
        entity_id=digest,
        payload={
            "batch_id": f"BATCH-{content[:12].upper()}",
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "observation_sha256": job["file_sha256"],
            "row_count": len(rows),
            "dataset_fingerprint": content,
        },
        now=created_at,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-OBS-{content[:12].upper()}",
    )
    member_event = _research_event(
        record_id=member_record_id,
        record_kind=RecordKind.OBSERVATION_MEMBER_BATCH,
        entity_id=digest,
        payload={
            "batch_id": f"MEMB-{content[:12].upper()}",
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "member_location": member_rel.replace("\\", "/"),
            "content_sha256": job["member_sha256"],
            "row_count": len(member_rows),
            "sampling": dict(schedule.get("sampling") or {}),
        },
        now=created_at,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-MEM-{content[:12].upper()}",
    )

    if job.get("stage") in {STAGE_ARTIFACTS, None}:
        _append_event(data_root, obs_event)
        job["stage"] = STAGE_RDP_OBS
        _save_job(data_root, content, job)
        _maybe_fault(fault_after, "AFTER_ONE_RDP_EVENT")

    if job.get("stage") == STAGE_RDP_OBS:
        _append_event(data_root, member_event)
        job["stage"] = STAGE_RDP_MEMBER
        _save_job(data_root, content, job)

    if not _rdp_has(data_root, obs_record_id) or not _rdp_has(data_root, member_record_id):
        raise ObservationPanelPublisherError("PUBLICATION_INCOMPLETE")

    manifest = build_dataset_manifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_id=SCHEMA_ID,
        schema_sha256=_schema_sha256(root),
        generation_task_id="DECLARATIVE-OBSERVATION-SCHEDULE-BRIDGE-V1",
        generation_run_id=activation_id,
        validation_receipt_sha256=content,
        first_reliable_available_at=max_available,
        created_at=created_at,
        partitions=[partition, member_partition],
    )
    partitions_dir = manifests_dir / "partitions"
    partitions_dir.mkdir(parents=True, exist_ok=True)
    if job.get("stage") == STAGE_RDP_MEMBER:
        for part in (partition, member_partition):
            part_path = partitions_dir / f"{part.partition_manifest_id}.json"
            _publish_immutable_bytes(
                part_path, part.model_dump_json().encode("utf-8")
            )
        _publish_immutable_bytes(
            manifest_path, manifest.model_dump_json().encode("utf-8")
        )
        job["stage"] = STAGE_MANIFEST
        job["dataset_fingerprint"] = manifest.dataset_fingerprint
        _save_job(data_root, content, job)
        _maybe_fault(fault_after, "AFTER_MANIFEST")

    if job.get("stage") == STAGE_MANIFEST:
        _publish_immutable_bytes(
            published_path,
            json.dumps(
                {
                    "dataset_manifest_id": dataset_manifest_id,
                    "dataset_fingerprint": manifest.dataset_fingerprint,
                },
                sort_keys=True,
            ).encode("utf-8"),
        )
        job["stage"] = STAGE_MARKER
        _save_job(data_root, content, job)
        persist_observation_schedule(
            data_root=data_root,
            schedule=schedule,
            now=created_at,
            producer_git_sha=producer_git_sha,
            activation_id=activation_id,
        )
        _maybe_fault(fault_after, "AFTER_MARKER")

    return {
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": manifest.dataset_fingerprint,
        "snapshot_cutoff": render_utc(max_available),
        "min_event_time": None if min_event is None else render_utc(min_event),
        "first_reliable_available_at": render_utc(max_available),
        "replay": False,
        "member_count": len(member_rows),
        "observation_count": len(rows),
    }


def repair_open_publication_jobs(
    *,
    data_root: Path,
    root: Path,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
    fault_after: str | None = None,
) -> list[dict[str, Any]]:
    jobs_dir = data_root / "datasets" / "publication_jobs"
    if jobs_dir.is_dir() is False:
        return []
    digest = str(schedule["schedule_sha256"])
    repaired: list[dict[str, Any]] = []
    for path in sorted(jobs_dir.glob("*.json")):
        job = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(job, dict):
            raise ObservationPanelPublisherError("PUBLICATION_JOB_INVALID")
        if job.get("schedule_sha256") != digest:
            continue
        if str(job.get("activation_id") or "") != str(activation_id):
            if job.get("activation_id") is None:
                raise ObservationPanelPublisherError("PUBLICATION_JOB_INVALID")
            continue
        if job.get("stage") == STAGE_MARKER:
            continue
        observations = list(job.get("observations") or [])
        members = list(job.get("members") or [])
        if not members:
            raise ObservationPanelPublisherError("PUBLICATION_INCOMPLETE")
        repaired.append(
            publish_observation_batch(
                data_root=data_root,
                root=root,
                schedule=schedule,
                activation_id=activation_id,
                now=now,
                producer_git_sha=producer_git_sha,
                members=members,
                observations=observations,
                fault_after=fault_after,
                content_sha256=path.stem,
            )
        )
    return repaired


def has_open_publication_jobs(
    *,
    data_root: Path,
    schedule_sha256: str,
    activation_id: str,
) -> bool:
    """Return whether this activation still has an unresolved publish job."""
    jobs_dir = data_root / "datasets" / "publication_jobs"
    if jobs_dir.is_dir() is False:
        return False
    for path in sorted(jobs_dir.glob("*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        if not isinstance(job, dict):
            return True
        if (
            str(job.get("schedule_sha256")) == schedule_sha256
            and str(job.get("activation_id")) == activation_id
            and job.get("stage") != STAGE_MARKER
        ):
            return True
        if (
            str(job.get("schedule_sha256")) == schedule_sha256
            and job.get("activation_id") is None
            and job.get("stage") != STAGE_MARKER
        ):
            return True
    return False


def build_panel_snapshot(
    *,
    schedule_sha256: str,
    availability_cutoff: datetime,
    dataset_manifest_ids: Sequence[str],
    dataset_fingerprints: Sequence[str],
) -> dict[str, Any]:
    payload = {
        "schema": "smial.observation-panel-snapshot",
        "schema_version": "1.0",
        "schedule_sha256": schedule_sha256,
        "availability_cutoff": render_utc(availability_cutoff),
        "dataset_manifest_ids": list(dataset_manifest_ids),
        "dataset_fingerprints": list(dataset_fingerprints),
    }
    digest = canonical_sha256(payload)
    payload["snapshot_id"] = f"SNAP-OBS-{digest[:12].upper()}"
    payload["snapshot_sha256"] = digest
    payload["first_reliable_available_at"] = render_utc(availability_cutoff)
    return payload


def rebuild_observation_panel_from_rdp(
    *,
    data_root: Path,
    schedule_sha256: str,
) -> dict[str, Any]:
    """Rebuild the durable panel view without consulting operational SQLite."""
    manifests_dir = data_root / "datasets" / "manifests"
    rebuilt_members: dict[
        tuple[str, str], tuple[datetime, str, dict[str, Any]]
    ] = {}
    rebuilt_observations: dict[
        tuple[str, str, str, str, str], tuple[datetime, str, dict[str, Any]]
    ] = {}
    manifest_ids: list[str] = []
    for marker in sorted(manifests_dir.glob("dataset-*.published")):
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        manifest_id = str(marker_payload.get("dataset_manifest_id") or "")
        manifest_path = manifests_dir / f"{manifest_id}.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, Mapping):
            continue
        if str(manifest.get("dataset_id") or "").startswith("observation-panel-") is False:
            continue
        try:
            manifest_order = parse_utc(
                str(
                    manifest.get("created_at")
                    or manifest.get("first_reliable_available_at")
                )
            )
        except Exception:
            manifest_order = datetime.min.replace(tzinfo=UTC)
        partitions = manifest.get("partitions") or []
        if not partitions:
            partitions_dir = manifests_dir / "partitions"
            partitions = []
            for partition_path in sorted(partitions_dir.glob("partition-*.json")):
                partition = json.loads(partition_path.read_text(encoding="utf-8"))
                if (
                    isinstance(partition, Mapping)
                    and str(partition.get("dataset_manifest_id") or "")
                    == manifest_id
                ):
                    partitions.append(partition)
        found = False
        for partition in partitions:
            location = str(partition.get("logical_location") or "")
            path = data_root / location
            if not path.is_file():
                continue
            rows = pq.read_table(path).to_pylist()
            matching_rows = False
            if str(partition.get("partition_id") or "").endswith("-members"):
                for row in rows:
                    if row.get("schedule_sha256") != schedule_sha256:
                        continue
                    key = (
                        str(row.get("activation_id") or ""),
                        str(row.get("entity_id") or ""),
                    )
                    candidate = (manifest_order, manifest_id, row)
                    current = rebuilt_members.get(key)
                    if current is None or candidate[:2] >= current[:2]:
                        rebuilt_members[key] = candidate
                    matching_rows = True
            else:
                for row in rows:
                    if row.get("schedule_sha256") != schedule_sha256:
                        continue
                    key = (
                        str(row.get("activation_id") or ""),
                        str(row.get("entity_id") or ""),
                        str(row.get("point_id") or ""),
                        str(row.get("primitive_id") or ""),
                        str(
                            row.get("call_occurrence_id")
                            or "|".join(
                                str(row.get(key) or "")
                                for key in (
                                    "request_sha256",
                                    "event_time",
                                    "first_reliable_available_at",
                                    "state",
                                )
                            )
                            or ""
                        ),
                    )
                    candidate = (manifest_order, manifest_id, row)
                    current = rebuilt_observations.get(key)
                    if current is None or candidate[:2] >= current[:2]:
                        rebuilt_observations[key] = candidate
                    matching_rows = True
            if matching_rows:
                found = True
        if found:
            manifest_ids.append(manifest_id)
    return {
        "schedule_sha256": schedule_sha256,
        "dataset_manifest_ids": manifest_ids,
        "members": [
            item[2]
            for _key, item in sorted(rebuilt_members.items(), key=lambda entry: entry[0])
        ],
        "observations": [
            item[2]
            for _key, item in sorted(
                rebuilt_observations.items(), key=lambda entry: entry[0]
            )
        ],
    }


__all__ = [
    "ObservationPanelPublisherError",
    "PublicationFault",
    "build_panel_snapshot",
    "has_open_publication_jobs",
    "load_pending_observation_bindings",
    "pending_observation_binding_sha256",
    "persist_observation_schedule",
    "persist_panel_snapshot_binding",
    "persist_pending_observation_binding",
    "publish_observation_batch",
    "rebuild_observation_panel_from_rdp",
    "repair_open_publication_jobs",
    "satisfy_pending_observation_binding",
]
