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
    tmp.replace(path)
    return digest


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
        supersedes_record_id=None,
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
        if any(item.record_id == event.record_id for item in existing):
            return
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
    snapshot_id = str(snapshot["snapshot_id"])
    snapshot_sha = str(snapshot["snapshot_sha256"])
    bind_id = f"BIND-OBS-{snapshot_sha[:12].upper()}"
    txn = f"RESEARCH-TXN-OBS-SNAP-{snapshot_sha[:12].upper()}"
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
            record_id=f"OBS-BIND-{snapshot_sha[:16].upper()}",
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
        store.append(events, transaction_id=txn)
    except Exception:
        existing_ids = {item.record_id for item in store.iter_committed_records()}
        if all(event.record_id in existing_ids for event in events):
            return
        raise


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
) -> dict[str, Any]:
    now = now.astimezone(UTC)
    if not observations or not members:
        raise ObservationPanelPublisherError("PARTIAL_DATASET_FORBIDDEN")
    digest = str(schedule["schedule_sha256"])
    utc_day = now.strftime("%Y%m%d")
    rows = [dict(item) for item in observations]
    member_rows = [dict(item) for item in members]
    content = canonical_sha256({"members": member_rows, "observations": rows})
    dataset_id = f"observation-panel-{digest[:12]}"
    dataset_version = f"{utc_day}-1-{content[:12]}"
    dataset_manifest_id = compute_dataset_manifest_id(dataset_id, dataset_version)
    manifests_dir = data_root / "datasets" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / f"{dataset_manifest_id}.json"
    published_path = manifests_dir / f"{dataset_manifest_id}.published"
    obs_record_id = f"OBS-BATCH-{content[:16].upper()}"
    member_record_id = f"OBS-MEMB-{content[:16].upper()}"
    job = _load_job(data_root, content) or {"stage": None, "content_sha256": content}

    if published_path.is_file():
        if not _rdp_has(data_root, obs_record_id) or not _rdp_has(data_root, member_record_id):
            raise ObservationPanelPublisherError("PUBLICATION_INCOMPLETE")
        loaded = json.loads(published_path.read_text(encoding="utf-8"))
        return {
            "dataset_manifest_id": dataset_manifest_id,
            "dataset_fingerprint": loaded.get("dataset_fingerprint"),
            "replay": True,
        }

    created_at = now
    min_event, max_event, min_available, max_available = _clocks_from_rows(
        rows,
        fallback=created_at,
    )
    parquet_rel = f"datasets/parquet/{dataset_manifest_id}/observations.parquet"
    member_rel = f"datasets/parquet/{dataset_manifest_id}/members.parquet"
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
            "sampling": dict(schedule.get("sampling") or {}),
            "schedule_sha256": digest,
            "observations": rows,
            "members": member_rows,
        }
        _save_job(data_root, content, job)
        _maybe_fault(fault_after, "AFTER_ARTIFACTS")

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
            part_tmp = part_path.with_suffix(".json.tmp")
            part_tmp.write_text(part.model_dump_json(), encoding="utf-8")
            part_tmp.replace(part_path)
        tmp = manifest_path.with_suffix(".json.tmp")
        tmp.write_text(manifest.model_dump_json(), encoding="utf-8")
        tmp.replace(manifest_path)
        job["stage"] = STAGE_MANIFEST
        job["dataset_fingerprint"] = manifest.dataset_fingerprint
        _save_job(data_root, content, job)
        _maybe_fault(fault_after, "AFTER_MANIFEST")

    if job.get("stage") == STAGE_MANIFEST:
        published_path.write_text(
            json.dumps(
                {
                    "dataset_manifest_id": dataset_manifest_id,
                    "dataset_fingerprint": manifest.dataset_fingerprint,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
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
        if job.get("stage") == STAGE_MARKER:
            continue
        observations = list(job.get("observations") or [])
        members = list(job.get("members") or [])
        if not observations or not members:
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
            )
        )
    return repaired


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


__all__ = [
    "ObservationPanelPublisherError",
    "PublicationFault",
    "build_panel_snapshot",
    "persist_observation_schedule",
    "persist_panel_snapshot_binding",
    "publish_observation_batch",
    "repair_open_publication_jobs",
]
