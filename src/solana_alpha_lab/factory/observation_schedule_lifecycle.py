"""Persistent ObservationSchedule lifecycle commands."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema

from solana_alpha_lab.factory.observation_panel_publisher import (
    build_panel_snapshot,
    persist_observation_schedule,
    persist_panel_snapshot_binding,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_schedule_document
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore

AUTHORITY_SCHEMA_RELATIVE = "catalog/schemas/observation_schedule_authority_v1.schema.json"
PRODUCER_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"
APPROVED_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"


class ObservationLifecycleError(ValueError):
    """Typed lifecycle failure."""


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
        hypothesis_version_id=None,
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


def _append_or_replay(data_root: Path, event: ResearchEvent) -> None:
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=event.transaction_id)
    except Exception:
        existing = list(store.iter_committed_records())
        match = next((item for item in existing if item.record_id == event.record_id), None)
        if match is None:
            raise
        if match.payload_sha256 != event.payload_sha256:
            raise ObservationLifecycleError("SCHEDULE_IDENTITY_CONFLICT")


def register_schedule(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    document: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    registry = load_observation_primitive_registry(root)
    registry.verify_implementation_hashes()
    compiled = compile_schedule_document(document, root=root)
    if compiled.schedule is None or compiled.schedule_sha256 is None:
        return {
            "terminal": compiled.terminal,
            "reason_codes": list(compiled.reason_codes),
            "schedule_sha256": None,
        }
    validated = validate_observation_schedule(compiled.schedule, root=root)
    digest = str(validated["schedule_sha256"])
    if digest != compiled.schedule_sha256:
        raise ObservationLifecycleError("INVALID_IDENTITY")
    try:
        outcome = store.persist_registered_schedule(
            schedule_sha256=digest,
            schedule_key=str(validated["schedule_key"]),
            document=validated,
            clock=now,
        )
    except ObservationScheduleStoreError as exc:
        raise ObservationLifecycleError(str(exc)) from exc
    persist_observation_schedule(
        data_root=data_root,
        schedule=validated,
        now=now,
        producer_git_sha=producer_git_sha,
    )
    terminal = "REGISTER_REPLAY" if outcome == "REGISTER_REPLAY" else "REGISTERED"
    return {
        "terminal": terminal,
        "schedule_sha256": digest,
        "schedule_key": validated["schedule_key"],
        "next_action": compiled.next_action,
    }


def authorize_schedule(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    phrase: str,
    now: datetime,
    producer_git_sha: str,
    expires_at: str | None = None,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    document = registered["document"]
    phrase_digest = hashlib.sha256(phrase.strip().encode("utf-8")).hexdigest()
    registry = load_observation_primitive_registry(root)
    routes = sorted(
        {
            str(route)
            for primitive in registry.primitives.values()
            for route in primitive["provider_route_ids"]
        }
    )
    policy = {
        "authority_profile_id": document["authority"]["profile_id"],
        "budgets": document["budgets"],
        "provider_route_ids": routes,
        "approved_capability_ids": [APPROVED_CAPABILITY],
        "allowed_credential_class": "LOCAL_ENV_CREDENTIAL",
    }
    points = [document["x_point"], *list(document["y_points"])]
    horizon = max(
        int(point["due_offset_seconds"]) + int(point["allowed_lateness_seconds"])
        for point in points
    )
    expires = expires_at or render_utc(
        parse_utc(document["activation"]["starts_at"]) + timedelta(seconds=horizon)
    )
    receipt = {
        "schema": "smial.observation-schedule-authority",
        "schema_version": "1.0",
        "authority_id": f"AUTHZ-OBS-{schedule_sha256[:12].upper()}",
        "schedule_sha256": schedule_sha256,
        "schedule_key": document["schedule_key"],
        "activation_starts_at": document["activation"]["starts_at"],
        "activation_stops_admitting_at": document["activation"]["stops_admitting_at"],
        "provider_route_ids": routes,
        "provider_calls_per_utc_day_max": int(document["budgets"]["provider_calls_per_utc_day_max"]),
        "provider_calls_lifetime_max": int(document["budgets"]["provider_calls_lifetime_max"]),
        "modeled_provider_credits_per_utc_day_max": int(
            document["budgets"]["modeled_provider_credits_per_utc_day_max"]
        ),
        "cash_usd_max": "0",
        "retry": False,
        "fallback": False,
        "build_execute_wallet_signer_transaction": False,
        "expires_at": expires,
        "phrase_sha256": phrase_digest,
        "policy_digest": canonical_sha256(policy),
        "approved_capability_ids": [APPROVED_CAPABILITY],
        "allowed_credential_class": "LOCAL_ENV_CREDENTIAL",
    }
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    schema = json.loads((root / AUTHORITY_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    jsonschema.validate(receipt, schema)
    try:
        outcome = store.persist_authority(receipt, clock=now)
    except ObservationScheduleStoreError as exc:
        raise ObservationLifecycleError(str(exc)) from exc
    event = _research_event(
        record_id=f"OBS-AUTHZ-{receipt['receipt_sha256'][:16].upper()}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_AUTHORITY,
        entity_id=schedule_sha256,
        payload=receipt,
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-OBS-AUTHZ-{receipt['receipt_sha256'][:12].upper()}",
    )
    _append_or_replay(data_root, event)
    terminal = "AUTHORIZE_REPLAY" if outcome == "AUTHORIZE_REPLAY" else "AUTHORIZED"
    return {
        "terminal": terminal,
        "schedule_sha256": schedule_sha256,
        "receipt_sha256": receipt["receipt_sha256"],
        "authority_id": receipt["authority_id"],
        "expires_at": expires,
    }


def _require_live_authority(
    store: ObservationScheduleStore,
    *,
    schedule_sha256: str,
    now: datetime,
) -> dict[str, Any]:
    receipt = store.latest_authority_for_schedule(schedule_sha256)
    if receipt is None:
        raise ObservationLifecycleError("AUTHORITY_MISSING")
    if parse_utc(receipt["expires_at"]) <= now:
        raise ObservationLifecycleError("AUTHORITY_EXPIRED")
    stored = store.get_authority(str(receipt["receipt_sha256"]))
    if stored != receipt:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    return receipt


def activate_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    document = registered["document"]
    receipt = _require_live_authority(store, schedule_sha256=schedule_sha256, now=now)
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        siblings = [
            row
            for row in store.list_activations()
            if row["schedule_sha256"] == schedule_sha256
        ]
        if siblings:
            raise ObservationLifecycleError("ACTIVATION_ALREADY_LIVE")
    if existing is not None:
        if str(existing.get("authority_receipt_sha256")) != receipt["receipt_sha256"]:
            raise ObservationLifecycleError("ACTIVATION_IDENTITY_CONFLICT")
        replay_event = _research_event(
            record_id=f"OBS-STATE-{activation_id}",
            record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
            entity_id=schedule_sha256,
            payload={
                "state_event_id": f"OBS-STATE-{activation_id}",
                "activation_id": activation_id,
                "state": "ACTIVE",
                "schedule_sha256": schedule_sha256,
            },
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=activation_id,
            transaction_id=f"RESEARCH-TXN-OBS-ACT-{activation_id.replace('-', '')}",
        )
        _append_or_replay(data_root, replay_event)
        if existing["state"] != "ACTIVE":
            return {
                "terminal": "ACTIVATE_STILL_PAUSED"
                if existing["state"] == "PAUSED_OPERATOR"
                else "ACTIVATE_NOT_ACTIVE",
                "activation_id": activation_id,
                "schedule_sha256": schedule_sha256,
                "state": existing["state"],
                "next_action": "RESUME"
                if existing["state"] == "PAUSED_OPERATOR"
                else "STATUS",
            }
        return {
            "terminal": "ACTIVATE_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": existing["state"],
        }
    store.upsert_activation(
        {
            "schedule_sha256": schedule_sha256,
            "activation_id": activation_id,
            "schedule_key": document["schedule_key"],
            "state": "ACTIVE",
            "authority_receipt_sha256": receipt["receipt_sha256"],
            "starts_at": document["activation"]["starts_at"],
            "stops_admitting_at": document["activation"]["stops_admitting_at"],
            "payload": {"receipt_sha256": receipt["receipt_sha256"]},
        },
        clock=now,
    )
    event = _research_event(
        record_id=f"OBS-STATE-{activation_id}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": f"OBS-STATE-{activation_id}",
            "activation_id": activation_id,
            "state": "ACTIVE",
            "schedule_sha256": schedule_sha256,
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-OBS-ACT-{activation_id.replace('-', '')}",
    )
    _append_or_replay(data_root, event)
    persisted = store.get_activation(schedule_sha256, activation_id)
    if persisted is None or persisted["state"] != "ACTIVE":
        raise ObservationLifecycleError("ACTIVATION_NOT_PERSISTED")
    return {
        "terminal": "ACTIVATED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "ACTIVE",
        "receipt_sha256": receipt["receipt_sha256"],
    }


def pause_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    store.upsert_activation(
        {**existing, "state": "PAUSED_OPERATOR", "payload": {"paused": True}},
        clock=now,
    )
    event = _research_event(
        record_id=f"OBS-PAUSE-{activation_id}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": f"OBS-PAUSE-{activation_id}",
            "activation_id": activation_id,
            "state": "PAUSED_OPERATOR",
            "schedule_sha256": schedule_sha256,
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-OBS-PAUSE-{activation_id.replace('-', '')}",
    )
    _append_or_replay(data_root, event)
    paused = store.get_activation(schedule_sha256, activation_id)
    if paused is None or paused["state"] != "PAUSED_OPERATOR":
        raise ObservationLifecycleError("PAUSE_NOT_PERSISTED")
    return {
        "terminal": "PAUSED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "PAUSED_OPERATOR",
    }


def resume_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    if existing["state"] == "ACTIVE":
        return {
            "terminal": "RESUME_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "ACTIVE",
        }
    if existing["state"] != "PAUSED_OPERATOR":
        raise ObservationLifecycleError("RESUME_NOT_PAUSED")
    receipt = _require_live_authority(store, schedule_sha256=schedule_sha256, now=now)
    store.upsert_activation(
        {
            **existing,
            "state": "ACTIVE",
            "authority_receipt_sha256": receipt["receipt_sha256"],
            "payload": {"resumed": True},
        },
        clock=now,
    )
    event = _research_event(
        record_id=f"OBS-RESUME-{activation_id}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": f"OBS-RESUME-{activation_id}",
            "activation_id": activation_id,
            "state": "ACTIVE",
            "schedule_sha256": schedule_sha256,
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-OBS-RESUME-{activation_id.replace('-', '')}",
    )
    _append_or_replay(data_root, event)
    resumed = store.get_activation(schedule_sha256, activation_id)
    if resumed is None or resumed["state"] != "ACTIVE":
        raise ObservationLifecycleError("RESUME_NOT_PERSISTED")
    return {
        "terminal": "RESUMED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "ACTIVE",
        "receipt_sha256": receipt["receipt_sha256"],
    }


def status_schedule(
    store: ObservationScheduleStore,
    *,
    schedule_sha256: str | None,
    activation_id: str | None,
) -> dict[str, Any]:
    activations = store.list_activations()
    if schedule_sha256 and activation_id:
        row = store.get_activation(schedule_sha256, activation_id)
        if row is None:
            raise ObservationLifecycleError("ACTIVATION_MISSING")
        activations = [row]
    return {
        "terminal": "STATUS",
        "activations": [
            {
                "schedule_sha256": row["schedule_sha256"],
                "activation_id": row["activation_id"],
                "state": row["state"],
            }
            for row in activations
        ],
        "due_counts": store.due_counts(),
        "restore_marker_unresolved": store.restore_marker_unresolved(),
    }


def snapshot_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
    hypothesis_version_id: str | None = None,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    if store.get_activation(schedule_sha256, activation_id) is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    from solana_alpha_lab.factory.observation_panel_coverage import (
        derive_first_y_available_at,
    )

    research = ResearchStore(data_root)
    batch_ids: list[str] = []
    member_ids: set[str] = set()
    for record in research.iter_committed_records():
        payload = json.loads(record.payload_json)
        if payload.get("schedule_sha256") != schedule_sha256:
            continue
        kind = str(record.record_kind)
        if kind == "OBSERVATION_BATCH":
            batch_ids.append(str(payload["dataset_manifest_id"]))
        if kind == "OBSERVATION_MEMBER_BATCH":
            member_ids.add(str(payload["dataset_manifest_id"]))
    dataset_ids = [item for item in batch_ids if item in member_ids]
    if not dataset_ids:
        raise ObservationLifecycleError("SNAPSHOT_NO_PUBLISHED_PANEL")
    marker_dir = data_root / "datasets" / "manifests"
    fingerprints: list[str] = []
    kept: list[str] = []
    for dataset_id in dataset_ids:
        marker_path = marker_dir / f"{dataset_id}.published"
        if not marker_path.is_file():
            continue
        loaded = json.loads(marker_path.read_text(encoding="utf-8"))
        fingerprints.append(str(loaded["dataset_fingerprint"]))
        kept.append(dataset_id)
    if not kept:
        raise ObservationLifecycleError("SNAPSHOT_NO_PUBLISHED_PANEL")
    snapshot = build_panel_snapshot(
        schedule_sha256=schedule_sha256,
        availability_cutoff=now,
        dataset_manifest_ids=kept,
        dataset_fingerprints=fingerprints,
    )
    _first_y, proven = derive_first_y_available_at(data_root, schedule_sha256)
    evidence_role = None if proven else "EXPLORATORY_REUSE"
    persist_panel_snapshot_binding(
        data_root=data_root,
        schedule=registered["document"],
        snapshot=snapshot,
        now=now,
        producer_git_sha=producer_git_sha,
        evidence_role=evidence_role,
        hypothesis_version_id=hypothesis_version_id,
        run_id=activation_id,
    )
    return {
        "terminal": "SNAPSHOT",
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "dataset_manifest_ids": kept,
        "first_y_proven": proven,
        "evidence_role": evidence_role,
    }


__all__ = [
    "ObservationLifecycleError",
    "activate_schedule",
    "authorize_schedule",
    "pause_schedule",
    "register_schedule",
    "resume_schedule",
    "snapshot_schedule",
    "status_schedule",
]
