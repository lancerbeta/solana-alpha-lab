"""Append-only HFIC provenance-time inventory and correction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    capture_stage_time,
    envelope_time_text,
    is_placeholder_timestamp,
    render_canonical_utc,
    validate_hfic_timestamp,
)
from solana_alpha_lab.factory.hfic_session import HficSessionError, PROMPT_VERSION
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256


CORRECTION_SCHEMA = "smial.hfic-provenance-time-correction"
CORRECTION_SCHEMA_VERSION = "1.0"
CORRECTION_ARTIFACT_KIND = "PROVENANCE_TIME_CORRECTION"
CORRECTION_REASON = "HFIC_PLACEHOLDER_PROVENANCE_TIME"
ORIGINAL_PLACEHOLDER = "1970-01-01T00:00:00Z"
PROVENANCE_VALID = "VALID"
PROVENANCE_CORRECTED = "CORRECTED_ORIGINAL_UNKNOWN"
_ENVELOPE_FIELDS = ("created_at", "effective_at", "first_reliable_available_at")


def _payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", "")
    if not raw:
        return {}
    loaded = json.loads(raw)
    if isinstance(loaded, dict):
        return loaded
    return {}


def is_hfic_record(record: Any, payload: Mapping[str, Any] | None = None) -> bool:
    body = payload if payload is not None else _payload(record)
    if body.get("hfic_protocol"):
        return True
    record_id = str(getattr(record, "record_id", "") or "")
    if record_id.startswith("HFIC-"):
        return True
    session_id = body.get("session_id")
    if isinstance(session_id, str) and session_id.startswith("HFIC-SESS-"):
        return True
    artifact_kind = body.get("artifact_kind")
    if artifact_kind in {"FORGE_CONTEXT_PACKET", CORRECTION_ARTIFACT_KIND}:
        return True
    return False


def _affected_fields(record: Any, payload: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for name in _ENVELOPE_FIELDS:
        text = envelope_time_text(getattr(record, name, None))
        if is_placeholder_timestamp(getattr(record, name, None)) or (
            text is not None and is_placeholder_timestamp(text)
        ):
            fields.append(name)
    created = payload.get("created_at")
    if is_placeholder_timestamp(created):
        fields.append("payload.created_at")
    session_started = payload.get("session_started_at")
    if is_placeholder_timestamp(session_started):
        fields.append("payload.session_started_at")
    inner = payload.get("payload_canonical")
    if isinstance(inner, str) and inner.startswith("{"):
        try:
            nested = json.loads(inner)
        except json.JSONDecodeError:
            nested = None
        if isinstance(nested, dict):
            if is_placeholder_timestamp(nested.get("created_at")):
                fields.append("payload_canonical.created_at")
            if is_placeholder_timestamp(nested.get("session_started_at")):
                fields.append("payload_canonical.session_started_at")
    return sorted(set(fields))


def inventory_placeholder_hfic_records(store: Any) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        payload = _payload(record)
        if payload.get("artifact_kind") == CORRECTION_ARTIFACT_KIND:
            continue
        if not is_hfic_record(record, payload):
            continue
        fields = _affected_fields(record, payload)
        if not fields:
            continue
        records.append(
            {
                "record_id": str(record.record_id),
                "payload_sha256": str(record.payload_sha256),
                "record_kind": str(
                    getattr(record.record_kind, "value", record.record_kind)
                ),
                "artifact_kind": payload.get("artifact_kind"),
                "session_id": payload.get("session_id"),
                "affected_fields": fields,
            }
        )
    records.sort(key=lambda item: (str(item["record_id"]), str(item["payload_sha256"])))
    by_session: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_artifact: dict[str, int] = {}
    by_field: dict[str, int] = {}
    for item in records:
        session = str(item.get("session_id") or "UNBOUND")
        by_session[session] = by_session.get(session, 0) + 1
        kind = str(item["record_kind"])
        by_kind[kind] = by_kind.get(kind, 0) + 1
        artifact = str(item.get("artifact_kind") or "NONE")
        by_artifact[artifact] = by_artifact.get(artifact, 0) + 1
        for field in item["affected_fields"]:
            by_field[field] = by_field.get(field, 0) + 1
    inventory_sha256 = canonical_sha256(
        {
            "records": [
                {
                    "record_id": item["record_id"],
                    "payload_sha256": item["payload_sha256"],
                    "record_kind": item["record_kind"],
                    "artifact_kind": item.get("artifact_kind"),
                    "session_id": item.get("session_id"),
                    "affected_fields": list(item["affected_fields"]),
                }
                for item in records
            ]
        }
    )
    return {
        "record_count": len(records),
        "records": records,
        "counts_by_session_id": by_session,
        "counts_by_record_kind": by_kind,
        "counts_by_artifact_kind": by_artifact,
        "counts_by_affected_field": by_field,
        "inventory_sha256": inventory_sha256,
        "original_placeholder_value": ORIGINAL_PLACEHOLDER,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }


def _load_corrections(store: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        payload = _payload(record)
        if payload.get("artifact_kind") != CORRECTION_ARTIFACT_KIND:
            continue
        raw = payload.get("payload_canonical")
        if not isinstance(raw, str):
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
        expected = payload.get("payload_sha256")
        actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if expected != actual:
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT") from exc
        if not isinstance(body, dict):
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
        found.append(body)
    return found


_CORRECTION_REQUIRED = (
    "schema",
    "schema_version",
    "correction_id",
    "artifact_kind",
    "hfic_protocol",
    "affected_records",
    "original_placeholder_value",
    "original_exact_time_status",
    "chronological_use_forbidden",
    "correction_created_at",
    "producer_git_sha",
    "reason_code",
    "inventory_sha256",
    "authority",
    "non_claims",
)


def _raise_first_correction_error(errors: list[str]) -> None:
    if "PROVENANCE_CORRECTION_PLACEHOLDER" in errors:
        raise HficSessionError("PROVENANCE_CORRECTION_PLACEHOLDER")
    if "PROVENANCE_CORRECTION_CORRUPT" in errors:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if "PROVENANCE_CORRECTION_PARTIAL" in errors:
        raise HficSessionError("PROVENANCE_CORRECTION_PARTIAL")
    if "PROVENANCE_CORRECTION_MISMATCH" in errors:
        raise HficSessionError("PROVENANCE_CORRECTION_MISMATCH")
    raise HficSessionError("PROVENANCE_TIME_UNCOVERED")


def _validate_correction_body(body: Mapping[str, Any], inventory: Mapping[str, Any]) -> None:
    for key in _CORRECTION_REQUIRED:
        if key not in body:
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("schema") != CORRECTION_SCHEMA:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("schema_version") != CORRECTION_SCHEMA_VERSION:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("artifact_kind") != CORRECTION_ARTIFACT_KIND:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("hfic_protocol") != PROMPT_VERSION:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("reason_code") != CORRECTION_REASON:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("original_placeholder_value") != ORIGINAL_PLACEHOLDER:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("original_exact_time_status") != "UNKNOWN":
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("chronological_use_forbidden") is not True:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    correction_id = body.get("correction_id")
    if not isinstance(correction_id, str) or not correction_id.startswith(
        "HFIC-ART-PROVENANCE-CORR-"
    ):
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if is_placeholder_timestamp(body.get("correction_created_at")):
        raise HficSessionError("PROVENANCE_CORRECTION_PLACEHOLDER")
    validate_hfic_timestamp(body.get("correction_created_at"))
    git_sha = body.get("producer_git_sha")
    if not isinstance(git_sha, str) or len(git_sha) != 40 or any(
        char not in "0123456789abcdef" for char in git_sha
    ):
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    authority = body.get("authority")
    if not isinstance(authority, Mapping):
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if (
        authority.get("git_mutation") != 0
        or authority.get("experiment_execution") != 0
        or authority.get("provider_api_rpc_wss_calls") != 0
    ):
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    non_claims = body.get("non_claims")
    if not isinstance(non_claims, list) or not non_claims:
        raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    if body.get("inventory_sha256") != inventory.get("inventory_sha256"):
        raise HficSessionError("PROVENANCE_CORRECTION_MISMATCH")
    affected = body.get("affected_records")
    expected = inventory.get("records")
    if not isinstance(affected, list) or affected != expected:
        raise HficSessionError("PROVENANCE_CORRECTION_PARTIAL")


def resolve_provenance_status(store: Any, inventory: Mapping[str, Any] | None = None) -> str:
    current = inventory if inventory is not None else inventory_placeholder_hfic_records(store)
    records = current.get("records") or []
    if not records:
        return PROVENANCE_VALID
    corrections = _load_corrections(store)
    if not corrections:
        raise HficSessionError("PROVENANCE_TIME_UNCOVERED")
    errors: list[str] = []
    matched = 0
    for body in corrections:
        try:
            _validate_correction_body(body, current)
        except HficSessionError as exc:
            errors.append(str(exc))
            continue
        matched += 1
    if errors:
        _raise_first_correction_error(errors)
    if matched != len(corrections):
        raise HficSessionError("PROVENANCE_TIME_UNCOVERED")
    return PROVENANCE_CORRECTED


def provenance_status_for_session(store: Any, session_id: str) -> str:
    inventory = inventory_placeholder_hfic_records(store)
    session_records = [
        item
        for item in inventory["records"]
        if item.get("session_id") == session_id
    ]
    if not session_records:
        return PROVENANCE_VALID
    return resolve_provenance_status(store, inventory)


def apply_provenance_correction(
    store: Any,
    *,
    repo_root: Any,
    clock: Clock | None = None,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    git_before = repository_git_snapshot(Path(repo_root))
    current = inventory if inventory is not None else inventory_placeholder_hfic_records(store)
    if not current["records"]:
        return {
            "status": PROVENANCE_VALID,
            "correction_appended": False,
            "inventory_sha256": current["inventory_sha256"],
            "record_count": 0,
            "authority": current["authority"],
        }
    existing = _load_corrections(store)
    if existing:
        errors: list[str] = []
        matched_body: Mapping[str, Any] | None = None
        for body in existing:
            try:
                _validate_correction_body(body, current)
            except HficSessionError as exc:
                errors.append(str(exc))
                continue
            matched_body = body
        if errors:
            _raise_first_correction_error(errors)
        if matched_body is None:
            raise HficSessionError("PROVENANCE_CORRECTION_MISMATCH")
        return {
            "status": PROVENANCE_CORRECTED,
            "correction_appended": False,
            "correction_id": matched_body.get("correction_id"),
            "inventory_sha256": current["inventory_sha256"],
            "record_count": current["record_count"],
            "original_exact_time_status": "UNKNOWN",
            "chronological_use_forbidden": True,
            "authority": current["authority"],
        }
    created = capture_stage_time(clock)
    created_text = render_canonical_utc(created)
    inventory_sha = str(current["inventory_sha256"])
    correction_id = "HFIC-ART-PROVENANCE-CORR-" + inventory_sha[:16].upper()
    body = {
        "schema": CORRECTION_SCHEMA,
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "correction_id": correction_id,
        "artifact_kind": CORRECTION_ARTIFACT_KIND,
        "hfic_protocol": PROMPT_VERSION,
        "affected_records": list(current["records"]),
        "original_placeholder_value": ORIGINAL_PLACEHOLDER,
        "original_exact_time_status": "UNKNOWN",
        "chronological_use_forbidden": True,
        "correction_created_at": created_text,
        "producer_git_sha": git_before.head_sha.lower(),
        "reason_code": CORRECTION_REASON,
        "inventory_sha256": inventory_sha,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "non_claims": [
            "NO_RECOVERED_EXACT_TIME",
            "NO_RDP_REWRITE",
            "NO_SESSION_REGENERATION",
        ],
    }
    _validate_correction_body(body, current)
    if repo_root is not None:
        from jsonschema import Draft202012Validator

        schema_path = (
            Path(repo_root) / "catalog/schemas/hfic_provenance_time_correction_v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(body), key=str)
        if errors:
            raise HficSessionError("PROVENANCE_CORRECTION_CORRUPT")
    body_bytes = canonical_json_bytes(body)
    payload = {
        "research_artifact_id": correction_id,
        "hfic_protocol": PROMPT_VERSION,
        "artifact_kind": CORRECTION_ARTIFACT_KIND,
        "payload_canonical": body_bytes.decode("utf-8"),
        "payload_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "inventory_sha256": inventory_sha,
        "reason_code": CORRECTION_REASON,
    }
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    transaction_id = f"RESEARCH-TXN-HFICPROV-{inventory_sha[:16].upper()}"
    event = ResearchEvent(
        record_id=correction_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=correction_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=created,
        first_reliable_available_at=created,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git_before.head_sha.lower(),
        created_at=created,
    )
    store.append([event], transaction_id=transaction_id)
    store.rebuild_projection()
    git_after = repository_git_snapshot(Path(repo_root))
    if not git_before.unchanged(git_after):
        raise HficSessionError("GIT_MUTATION_DETECTED")
    return {
        "status": PROVENANCE_CORRECTED,
        "correction_appended": True,
        "correction_id": correction_id,
        "inventory_sha256": inventory_sha,
        "record_count": current["record_count"],
        "original_exact_time_status": "UNKNOWN",
        "chronological_use_forbidden": True,
        "correction_created_at": created_text,
        "authority": current["authority"],
        "provider_calls_actual": 0,
        "git_unchanged": True,
    }
