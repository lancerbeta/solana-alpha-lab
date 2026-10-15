"""Archive-bound retirement and bounded native ObservationSchedule maintenance.

Scientific state, clocks, accounting and row identities remain source-owned.
All destructive entry points require exact plans; routine maintenance is off
until an exact policy is commissioned. Cold artifacts are never routine sources.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.observation_panel_coverage import SCIENTIFIC_CLOSED_DUE_STATES
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import (
    GLOBAL_LEASE_ID, ObservationScheduleStore, ObservationScheduleStoreError,
)

COMPACTION_MARKER = "COMPACTED_PROVENANCE_ONLY"
BODY_KEYS = frozenset({"rows", "body", "raw_body", "response_body", "payload_rows"})
POLICY_SCHEMA = "smial.observation-maintenance-policy.v1"
PLAN_SCHEMA = "smial.observation-retirement-plan.v1"
MAX_PLAN_ROWS = 1000
MAX_PLAN_BYTES = 8 * 1024 * 1024


class ObservationScheduleRetentionError(ValueError):
    """Stable typed refusal, without source payloads or private paths."""


@contextmanager
def _sqlite_connection(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_parse(raw: object) -> datetime | None:
    try:
        return parse_utc(str(raw))
    except (TypeError, ValueError):
        return None


def retention_cutoff(*, now: datetime, raw_retention_days: int) -> datetime:
    if raw_retention_days < 1:
        raise ObservationScheduleRetentionError("RAW_RETENTION_DAYS_INVALID")
    return now.replace(tzinfo=now.tzinfo or UTC).astimezone(UTC) - timedelta(days=raw_retention_days)


def _payload_has_compactable_body(payload: Mapping[str, Any]) -> bool:
    return payload.get("raw_payload_retention") != COMPACTION_MARKER and any(
        key in payload and payload[key] not in (None, [], {}, "") for key in BODY_KEYS | {"entities"})


def compact_payload(payload: Mapping[str, Any], *, compacted_at: str,
                    archive_locator: Mapping[str, Any] | None = None,
                    retire_entities: bool = False) -> dict[str, Any]:
    # Keep reader-owned entities/raw_body_rel, unknown diagnostics and missingness.
    removed = BODY_KEYS | ({"entities"} if retire_entities else set())
    kept = {key: value for key, value in payload.items() if key not in removed}
    if retire_entities and payload.get("entities"):
        kept["entities_retention"] = COMPACTION_MARKER
        kept["entities_projection_sha256"] = _hash(payload["entities"])
    kept.update(raw_payload_retention=COMPACTION_MARKER, raw_payload_compacted_at=compacted_at,
                raw_retention_substrate="DECODED_CANONICAL_PROVIDER_JSON_NOT_BYTE_IDENTICAL_HTTP")
    if archive_locator is not None:
        kept["retirement_archive"] = dict(archive_locator)
    return kept


def _control(store: ObservationScheduleStore, key: str, default: Any = None) -> Any:
    if store._conn.execute("SELECT 1 FROM sqlite_master WHERE name='retention_control'").fetchone() is None:
        return default
    row = store._conn.execute("SELECT payload_json FROM retention_control WHERE control_key=?", (key,)).fetchone()
    return default if row is None else json.loads(row[0])


def _set_control(store: ObservationScheduleStore, key: str, payload: Any) -> None:
    store._conn.execute("INSERT INTO retention_control VALUES(?,?) ON CONFLICT(control_key) DO UPDATE SET payload_json=excluded.payload_json", (key, _json(payload)))


def _schema_identity(conn: sqlite3.Connection) -> str:
    return _hash([list(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")])


def _root_binding(path: Path) -> dict[str, int]:
    stat = path.resolve().stat()
    return {"device": stat.st_dev, "inode": stat.st_ino}


def _archive_binding(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {**_root_binding(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _source_identity(store: ObservationScheduleStore) -> dict[str, Any]:
    identity = _control(store, "source_identity")
    if not identity:
        raise ObservationScheduleRetentionError("SOURCE_IDENTITY_UNCOMMISSIONED")
    return {"source_id": identity["source_id"], "schema_sha256": _schema_identity(store._conn),
            "root_binding": _root_binding(store.path.parent), "db_binding": _root_binding(store.path)}


def _within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def create_cold_archive(store: ObservationScheduleStore, *, archive_path: Path,
                        restored_path: Path, routine_roots: list[Path]) -> dict[str, Any]:
    """Capture original SQLite once and verify a separately opened local copy.

    LOCAL_REHEARSAL is explicit. Commissioning additionally requires actual
    independent-sink content readback; a second path alone is no off-host proof.
    """
    if not routine_roots or any(_within(p, root) for p in (archive_path, restored_path) for root in routine_roots):
        raise ObservationScheduleRetentionError("COLD_ARCHIVE_IN_ROUTINE_SOURCE")
    if archive_path.resolve() == restored_path.resolve() or archive_path.exists() or restored_path.exists():
        raise ObservationScheduleRetentionError("ARCHIVE_TARGET_EXISTS_OR_ALIASED")
    for path in (archive_path, restored_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    with _sqlite_connection(archive_path) as captured:
        store._conn.backup(captured)
    shutil.copyfile(archive_path, restored_path)
    proof = {"archive_path": str(archive_path.resolve()), "restored_path": str(restored_path.resolve()),
             "archive_sha256": _file_hash(archive_path), "source_id": _source_identity(store)["source_id"],
             "proof_class": "LOCAL_REHEARSAL", "routine_roots": [str(p.resolve()) for p in routine_roots]}
    proof["file_bindings"] = [_archive_binding(p) for p in (archive_path, restored_path)]
    verify_cold_archive(proof)
    return proof


def verify_cold_archive(proof: Mapping[str, Any], *, deep: bool = True) -> None:
    """Verify actual bytes and SQLite, never a supplied 'verified: true'."""
    try:
        if proof.get("proof_class") == "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
            _verify_checkpoint_archive(proof, deep=deep)
            return
        paths = [Path(str(proof[k])).resolve() for k in ("archive_path", "restored_path")]
        roots = [Path(p) for p in proof["routine_roots"]]
        if not roots or paths[0] == paths[1] or any(_within(p, root) for p in paths for root in roots):
            raise ObservationScheduleRetentionError("COLD_ARCHIVE_IN_ROUTINE_SOURCE")
        if [_archive_binding(path) for path in paths] != proof.get("file_bindings"):
            raise ObservationScheduleRetentionError("COLD_ARCHIVE_BINDING_CHANGED")
        if not deep:
            return
        for path in paths:
            if _file_hash(path) != proof["archive_sha256"]:
                raise ObservationScheduleRetentionError("COLD_ARCHIVE_BYTES_MISMATCH")
            with _sqlite_connection(path.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ObservationScheduleRetentionError("COLD_ARCHIVE_INTEGRITY")
                identity = json.loads(conn.execute("SELECT payload_json FROM retention_control WHERE control_key='source_identity'").fetchone()[0])
                if identity["source_id"] != proof["source_id"]:
                    raise ObservationScheduleRetentionError("COLD_ARCHIVE_SOURCE_MISMATCH")
    except (OSError, KeyError, TypeError, sqlite3.Error) as exc:
        raise ObservationScheduleRetentionError("COLD_ARCHIVE_PROOF_UNAVAILABLE") from exc


def _validate_operation_mode(operation_mode: str | None) -> None:
    if operation_mode is not None and operation_mode not in {"ISOLATED_REHEARSAL", "OPERATE"}:
        raise ObservationScheduleRetentionError("EXACT_OPERATION_MODE_REQUIRED")


def _effective_operation_mode(store: ObservationScheduleStore, operation_mode: str | None) -> str | None:
    _validate_operation_mode(operation_mode)
    commissioned = _control(store, "policy", {}).get("operation_mode")
    _validate_operation_mode(commissioned)
    if commissioned is not None and operation_mode is not None and commissioned != operation_mode:
        raise ObservationScheduleRetentionError("OPERATION_MODE_MISMATCH")
    return commissioned if commissioned is not None else operation_mode


def _check_retirement_operation_mode(store: ObservationScheduleStore, retirement: Mapping[str, Any],
                                     operation_mode: str | None) -> None:
    if operation_mode is None:
        return  # Preserve native callers of policies commissioned before mode binding.
    if retirement.get("operation_mode") != operation_mode:
        raise ObservationScheduleRetentionError("OPERATION_MODE_MISMATCH")
    if operation_mode == "OPERATE":
        proof = retirement.get("archive_proof", {})
        if (proof.get("proof_class") not in {"INDEPENDENT_SINK_CONTENT_READBACK", "REMOTE_CHECKPOINT_RESTORE_VERIFIED"}
                or (not retirement.get("automatic") and not retirement.get("operate_authority_sha256"))):
            raise ObservationScheduleRetentionError("INDEPENDENT_COLD_OPERATE_PROOF_REQUIRED")
        if _control(store, "checkpoint_archive") != proof:
            raise ObservationScheduleRetentionError("REGISTERED_CHECKPOINT_OPERATE_PROOF_REQUIRED")


def validate_retention_operation_mode(store: ObservationScheduleStore, *, operation_mode: str | None,
                                      policy: Mapping[str, Any] | None = None,
                                      retirement: Mapping[str, Any] | None = None,
                                      plan: Mapping[str, Any] | None = None,
                                      now: datetime | None = None,
                                      commissioning: bool = False) -> str | None:
    """Read-only authority check, repeated by native writers under their fence.

    Mode belongs to the installed control wrapper, never to a rewritten signed
    policy. A legacy wrapper without mode keeps its existing native semantics.
    """
    _validate_operation_mode(operation_mode)
    mode = operation_mode if commissioning else _effective_operation_mode(store, operation_mode)
    if retirement is not None:
        _check_retirement_operation_mode(store, retirement, mode)
    if mode is None:
        return mode
    if policy is not None and policy.get("enabled"):
        for scope in policy.get("allowed_scopes", []):
            row = store._conn.execute("SELECT payload_json FROM retirement_scopes WHERE schedule_sha256=? AND activation_id=?",
                (scope["schedule_sha256"], scope["activation_id"])).fetchone()
            if row is not None:
                retired = json.loads(row[0])
                if retired.get("automatic") or retired.get("archive_proof", {}).get("proof_class") == "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
                    current = _control(store, "checkpoint_archive")
                    if current:
                        retired = {**retired, "archive_proof": current}
                _check_retirement_operation_mode(store, retired, mode)
    if plan is not None:
        if mode == "OPERATE":
            for proof in plan.get("archive_registry", {}).values():
                if proof.get("proof_class") not in {"INDEPENDENT_SINK_CONTENT_READBACK", "REMOTE_CHECKPOINT_RESTORE_VERIFIED"}:
                    raise ObservationScheduleRetentionError("INDEPENDENT_COLD_OPERATE_PROOF_REQUIRED")
                if _control(store, "checkpoint_archive") != proof:
                    raise ObservationScheduleRetentionError("REGISTERED_CHECKPOINT_OPERATE_PROOF_REQUIRED")
        for candidate in plan.get("candidates", []):
            _, retirements = _protect(store, candidate["row"], candidate["table"], plan["policy"], now)
            for retired in retirements:
                _check_retirement_operation_mode(store, retired, mode)
    return mode


def install_retirement(store: ObservationScheduleStore, *, retirement: Mapping[str, Any],
                       approved_sha256: str, now: datetime,
                       operation_mode: str | None = None) -> dict[str, Any]:
    """Exact approved no-resume record; lifecycle and due states remain original."""
    document = dict(retirement)
    if _hash(document) != approved_sha256 or document.get("disallow_resume") is not True:
        raise ObservationScheduleRetentionError("RETIREMENT_APPROVAL_MISMATCH")
    verify_cold_archive(document["archive_proof"])
    mode = document.get("operation_mode")
    if mode not in {"ISOLATED_REHEARSAL", "OPERATE"}:
        raise ObservationScheduleRetentionError("EXACT_OPERATION_MODE_REQUIRED")
    validate_retention_operation_mode(store, operation_mode=operation_mode, retirement=document)
    if mode == "OPERATE" and (document["archive_proof"].get("proof_class") not in {"INDEPENDENT_SINK_CONTENT_READBACK", "REMOTE_CHECKPOINT_RESTORE_VERIFIED"} or not document.get("operate_authority_sha256")):
        raise ObservationScheduleRetentionError("INDEPENDENT_COLD_OPERATE_PROOF_REQUIRED")
    if mode == "OPERATE" and _control(store, "checkpoint_archive") != document["archive_proof"]:
        raise ObservationScheduleRetentionError("REGISTERED_CHECKPOINT_OPERATE_PROOF_REQUIRED")
    if document["archive_proof"]["source_id"] != _source_identity(store)["source_id"]:
        raise ObservationScheduleRetentionError("RETIREMENT_SOURCE_MISMATCH")
    scope = (str(document["schedule_sha256"]), str(document["activation_id"]))
    lease = store.acquire_lease("i2-retirement", clock=now)
    if lease is None:
        raise ObservationScheduleRetentionError("WRITER_BUSY")
    try:
        store._conn.execute("BEGIN IMMEDIATE")
        store._require_write_lease(now, within_transaction=True)
        validate_retention_operation_mode(store, operation_mode=operation_mode, retirement=document)
        _check_retirement_operation_mode(store, document, mode)
        activation = store._conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
        if activation is None or activation[0] not in {"PAUSED_OPERATOR", "COMPLETE", "ABORTED_SAFETY", "BLOCKED_AUTHORITY", "BLOCKED_BUDGET"}:
            raise ObservationScheduleRetentionError("RETIREMENT_SCOPE_ACTIVE_OR_UNKNOWN")
        existing = store._conn.execute("SELECT payload_json FROM retirement_scopes WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
        if existing is not None and json.loads(existing[0]) != document:
            raise ObservationScheduleRetentionError("RETIREMENT_RECORD_IMMUTABLE")
        store._conn.execute("INSERT OR IGNORE INTO retirement_scopes VALUES(?,?,?)", (*scope, _json(document)))
        store._conn.commit()
    except Exception:
        store._conn.rollback()
        raise
    finally:
        store.release_lease(lease)
    return {"status": "RETIRED_DISALLOW_RESUME", "retirement_sha256": approved_sha256}


def policy_sha256(policy: Mapping[str, Any]) -> str:
    return _hash(dict(policy))


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA or type(policy.get("revision")) is not int or policy["revision"] < 1:
        raise ObservationScheduleRetentionError("MAINTENANCE_POLICY_INVALID")
    if not isinstance(policy.get("enabled"), bool) or not (policy.get("allowed_scopes") or policy.get("allowed_managed_lineages")):
        raise ObservationScheduleRetentionError("MAINTENANCE_POLICY_INVALID")
    if not set(policy.get("allowed_classes", [])).issubset({"call_ledger", "poll_slots"}) or not policy.get("allowed_classes"):
        raise ObservationScheduleRetentionError("MAINTENANCE_POLICY_CLASSES_INVALID")
    for key, maximum in (("max_rows", MAX_PLAN_ROWS), ("max_bytes", MAX_PLAN_BYTES), ("max_wall_seconds", 30)):
        value = policy.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0 or value > maximum:
            raise ObservationScheduleRetentionError("MAINTENANCE_BUDGET_INVALID")
        if key in {"max_rows", "max_bytes"} and type(value) is not int:
            raise ObservationScheduleRetentionError("MAINTENANCE_BUDGET_INVALID")
    if any(type(policy.get(key)) is not int for key in ("min_age_days", "frozen_min_age_days")):
        raise ObservationScheduleRetentionError("FROZEN_RETENTION_LOWER_BOUND")
    if int(policy.get("min_age_days", 0)) < int(policy.get("frozen_min_age_days", 1)) or int(policy.get("frozen_min_age_days", 0)) < 1:
        raise ObservationScheduleRetentionError("FROZEN_RETENTION_LOWER_BOUND")
    if policy.get("physical_reclaim") is not False or int(policy.get("cadence_seconds", 0)) < 1:
        raise ObservationScheduleRetentionError("MAINTENANCE_POLICY_INVALID")
    if not isinstance(policy.get("retained_restore_points"), int) or policy["retained_restore_points"] < 1:
        raise ObservationScheduleRetentionError("RESTORE_POINT_POLICY_REQUIRED")
    refresh = policy.get("archive_refresh", {})
    if refresh.get("enabled") is True:
        raw_relative = str(refresh.get("cold_root_relative", "")).replace("\\", "/")
        relative = Path(raw_relative)
        if (not relative.parts or relative.is_absolute() or any(p in {"", ".", ".."} for p in raw_relative.split("/")) or ":" in raw_relative
                or not 0 < int(refresh.get("max_objects", 0)) <= 128
                or int(refresh.get("max_bytes", 0)) <= 0
                or not 0 < float(refresh.get("max_wall_seconds", 0)) <= 300
                or int(refresh.get("minimum_interval_seconds", 0)) < 1):
            raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_BUDGET_INVALID")


def _supersede_stale_policy_plan(store: ObservationScheduleStore, *,
        approved_policy_sha256: str, now: datetime) -> bool:
    """Retire an obsolete intent, never its effects or immutable cold pins.

    Called inside the native lease and transaction. A new approval is not
    permission to erase a changed candidate, corrupt archive or altered effect.
    The old bounded plan is checked before its unapplied remainder is abandoned.
    """
    plan = _control(store, "active_plan")
    if not plan or plan.get("policy_sha256") == approved_policy_sha256:
        return False
    document = {key: value for key, value in plan.items() if key != "plan_id"}
    if (plan.get("schema") != PLAN_SCHEMA or plan.get("plan_id") != _hash(document)
            or policy_sha256(plan["policy"]) != plan["policy_sha256"]):
        raise ObservationScheduleRetentionError("PLAN_APPROVAL_OR_IDENTITY_MISMATCH")
    if _source_identity(store) != plan["source"]:
        raise ObservationScheduleRetentionError("PLAN_STALE_SOURCE_OR_SCHEMA")
    old_policy = plan["policy"]
    validate_policy(old_policy)
    candidates = plan["candidates"]
    if (len(candidates) > int(old_policy["max_rows"])
            or sum(int(c["row"]["payload_bytes"]) + int(c.get("dependency_bytes", 0)) for c in candidates) > int(old_policy["max_bytes"])):
        raise ObservationScheduleRetentionError("PLAN_BUDGET_EXCEEDED")
    progress = store._conn.execute("SELECT next_candidate,payload_json FROM retention_progress WHERE plan_id=?", (plan["plan_id"],)).fetchone()
    offset = int(progress[0]) if progress else 0
    if not 0 <= offset <= len(candidates):
        raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
    started = time.monotonic()
    proofs = plan.get("archive_registry", {})
    for proof in proofs.values():
        verify_cold_archive(proof, deep=False)
    current_bytes = 0
    # Provenance can exceed a tiny original body. Bound commissioning readback
    # by frozen input + bounded intent/metadata, rather than rejecting a valid
    # already-committed effect solely because it grew operational metadata.
    current_read_budget = int(old_policy["max_bytes"]) + len(_json(plan).encode()) + len(candidates)*2048
    for index, original in enumerate(candidates):
        if time.monotonic() - started >= float(old_policy["max_wall_seconds"]):
            raise ObservationScheduleRetentionError("POLICY_RECONCILIATION_BUDGET_EXCEEDED")
        candidate = {**original, "archive_proofs": [proofs[p] if isinstance(p, str) else p for p in original["archive_proofs"]]}
        table, rowid = candidate["table"], candidate["row"]["source_rowid"]
        if table not in {"call_ledger", "poll_slots"}:
            raise ObservationScheduleRetentionError("PLAN_TABLE_INVALID")
        size = store._conn.execute(f"SELECT length(CAST(payload_json AS BLOB)) FROM {table} WHERE rowid=?", (rowid,)).fetchone()
        current_bytes += int(size[0]) if size else 0
        if size is None or current_bytes > current_read_budget:
            raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE")
        row = dict(store._conn.execute(f"SELECT rowid AS source_rowid,* FROM {table} WHERE rowid=?", (rowid,)).fetchone())
        if any(row[key] != value for key, value in candidate["row"].items() if key != "payload_bytes"):
            raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE")
        if index >= offset:
            if size[0] != candidate["row"]["payload_bytes"] or hashlib.sha256(row["payload_json"].encode()).hexdigest() != candidate["payload_sha256"]:
                raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE")
        _archive_candidate_matches(candidate)
        if index < offset:
            actual = json.loads(row["payload_json"])
            effect_hashes = json.loads(progress[1]).get("effect_hashes", {}) if progress else {}
            effect = effect_hashes.get(f"{table}:{rowid}")
            if effect and _hash({**row,"payload_bytes":size[0]}) != effect:
                raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
            reason, retirements = _protect(store, row, table, old_policy, now)
            if reason or [_hash(item) for item in retirements] != candidate["retirement_sha256"]:
                raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
            proof = candidate["archive_proofs"][0]
            with _sqlite_connection(Path(proof["archive_path"]).as_uri()+"?mode=ro&immutable=1", uri=True) as archived:
                source = json.loads(archived.execute(f"SELECT payload_json FROM {table} WHERE rowid=?", (rowid,)).fetchone()[0])
            expected = compact_payload(source, compacted_at=actual.get("raw_payload_compacted_at"),
                archive_locator={"archive_sha256": proof["archive_sha256"], "source_rowid": rowid,
                    "plan_id": plan["plan_id"], "archive_locator": retirements[0].get("archive_locator", "COLD_ARCHIVE_OPERATOR_INDEX")},
                retire_entities=all(r.get("retire_entities") is True for r in retirements))
            if table == "poll_slots":
                expected["poll_slot_retention"] = COMPACTION_MARKER
            if actual != expected:
                raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
    history = json.loads(progress[1]) if progress else {}
    history.update(state="SUPERSEDED_POLICY", superseded_at=render_utc(now),
        previous_policy_sha256=plan["policy_sha256"], approved_policy_sha256=approved_policy_sha256,
        abandoned_candidates=len(candidates)-offset)
    store._conn.execute("INSERT INTO retention_progress VALUES(?,?,?) ON CONFLICT(plan_id) DO UPDATE SET payload_json=excluded.payload_json",
        (plan["plan_id"], offset, _json(history)))
    store._conn.execute("DELETE FROM retention_control WHERE control_key='active_plan'")
    state = _control(store, "maintenance", {})
    state.update(state="YIELD", last_reason="POLICY_RECONCILED", active_plan_id=None,
        superseded_plan_id=plan["plan_id"], next_cursor={"call_ledger":0, "poll_slots":0}, archive_discovery=[])
    state.pop("last_run_at", None)
    _set_control(store, "maintenance", state)
    return True


def _reconcile_pending_refresh_policy(store: ObservationScheduleStore, *,
        policy: Mapping[str, Any], approved_policy_sha256: str, now: datetime) -> bool:
    """Rebind immutable readback under new approval, never an old apply plan.

    Native lease/transaction belongs to the caller. Only bounded metadata is
    read here; the existing independent restore still owns every byte oracle.
    Incompatible limits suspend the same target visibly, retaining its cache
    and pins instead of allocating an orphan generation or widening authority.
    """
    pending = _control(store, "checkpoint_archive_refresh_pending")
    if not pending or pending.get("policy_sha256") == approved_policy_sha256:
        return False
    from solana_alpha_lab.factory.offhost_backup import _checkpoint_canonical, CHECKPOINT_SCHEMA
    try:
        payload = pending["checkpoint"]
        encoded = _checkpoint_canonical(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        if (len(_json(pending).encode()) > MAX_PLAN_BYTES or payload.get("schema") != CHECKPOINT_SCHEMA
                or payload.get("schema_version") != "1.0" or digest != pending["checkpoint_sha256"]
                or not re.fullmatch(r"RECOVERY_CHECKPOINT_\d{8}T\d{6}Z_"+digest+r"\.json", pending["checkpoint_filename"])):
            raise ValueError("checkpoint")
        names = {pending["checkpoint_filename"]}
        known_bytes = len(encoded)
        for index,item in enumerate([payload["base_full"], *payload["ordered_deltas"]]):
            expected = ("BACKUP_" if index == 0 else "DELTA_")+item["sha256"]+".zip"
            if (not re.fullmatch(r"(?:BACKUP|DELTA)_[0-9a-f]{64}\.zip",expected)
                    or item["filename"] != expected or expected in names
                    or type(item["bytes"]) is not int or item["bytes"] <= 0):
                raise ValueError("reference")
            names.add(expected)
            known_bytes += item["bytes"]
        raw_members = 0
        for item in pending.get("supplemental_archives", []):
            name = item["filename"]
            if (not re.fullmatch(r"ARCHIVE_[0-9a-f]{64}\.zip",name)
                    or item["sha256"] != name[8:-4] or name in names):
                raise ValueError("supplement")
            names.add(name)
            raw_members += len(item["raw_entries"])
        if (len(names) > 128 or raw_members > MAX_PLAN_ROWS or sorted(names) != pending["pin_objects"]
                or not re.fullmatch(r"[0-9a-f]{64}",pending["policy_sha256"])):
            raise ValueError("closure")
        if pending.get("source_id") and pending["source_id"] != _source_identity(store)["source_id"]:
            raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_PENDING_SOURCE_CHANGED")
        # Historical intents predate source_id. Their actual reconstructed
        # source UUID is still checked before native registration or retirement.
        for name in names:
            if store._conn.execute("SELECT 1 FROM retention_archive_pins WHERE object_name=?",(name,)).fetchone() is None:
                raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_PENDING_PINS_MISSING")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ObservationScheduleRetentionError):
            raise
        raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_PENDING_IDENTITY_CONFLICT") from exc
    refresh = policy.get("archive_refresh", {})
    enabled = policy.get("enabled") and policy.get("auto_retire_terminal") and refresh.get("enabled") is True
    blocked = None
    if enabled:
        if pending["cold_root_relative"] != refresh["cold_root_relative"]:
            blocked = "ARCHIVE_REFRESH_PENDING_COLD_ROOT_CHANGED"
        elif len(names) > int(refresh["max_objects"]) or known_bytes > int(refresh["max_bytes"]):
            blocked = "ARCHIVE_REFRESH_PENDING_BUDGET_EXCEEDED"
    rebound = {**pending, "policy_sha256": approved_policy_sha256,
        "previous_policy_sha256": pending["policy_sha256"], "policy_reconciled_at": render_utc(now),
        "reconciliation_state": "BLOCKED_POLICY" if blocked else ("READY" if enabled else "SUSPENDED_POLICY"),
        "reconciliation_reason": blocked}
    _set_control(store, "checkpoint_archive_refresh_pending", rebound)
    state = _control(store, "maintenance", {})
    state.update(state="FAILED" if blocked else "YIELD", last_reason=blocked or "POLICY_RECONCILED",
        next_cursor={"call_ledger":0,"poll_slots":0}, archive_discovery=[])
    state.pop("last_run_at", None)
    _set_control(store, "maintenance", state)
    return True


def install_maintenance_policy(store: ObservationScheduleStore, *, policy: Mapping[str, Any],
                               approved_sha256: str, now: datetime,
                               operation_mode: str | None = None) -> dict[str, Any]:
    validate_policy(policy)
    _check_frozen_lower_bounds(store, policy)
    if policy_sha256(policy) != approved_sha256:
        raise ObservationScheduleRetentionError("POLICY_APPROVAL_MISMATCH")
    previous = _control(store, "policy", {})
    mode = operation_mode if operation_mode is not None else previous.get("operation_mode")
    validate_retention_operation_mode(store, operation_mode=mode, policy=policy, commissioning=True)
    lease = store.acquire_lease("i2-maintenance-policy", clock=now)
    if lease is None:
        raise ObservationScheduleRetentionError("WRITER_BUSY")
    try:
        store._conn.execute("BEGIN IMMEDIATE")
        store._require_write_lease(now, within_transaction=True)
        previous = _control(store, "policy")
        mode = operation_mode if operation_mode is not None else (previous or {}).get("operation_mode")
        validate_retention_operation_mode(store, operation_mode=mode, policy=policy, commissioning=True)
        if previous and (policy != previous["policy"] or mode != previous.get("operation_mode")) and int(policy["revision"]) <= int(previous["policy"]["revision"]):
            raise ObservationScheduleRetentionError("POLICY_REVISION_NOT_MONOTONIC")
        _check_frozen_lower_bounds(store, policy)
        _supersede_stale_policy_plan(store, approved_policy_sha256=approved_sha256, now=now)
        _reconcile_pending_refresh_policy(store, policy=policy, approved_policy_sha256=approved_sha256, now=now)
        wrapper = {"policy": dict(policy), "approved_policy_sha256": approved_sha256}
        if mode is not None:
            wrapper["operation_mode"] = mode
        _set_control(store, "policy", wrapper)
        # Explicit commissioning, never startup, owns these consumer indices.
        store._conn.execute("CREATE INDEX IF NOT EXISTS idx_due_retention_occurrence ON due_observations(call_occurrence_id)")
        store._conn.execute("CREATE INDEX IF NOT EXISTS idx_due_retention_request ON due_observations(request_sha256)")
        store._conn.execute("CREATE INDEX IF NOT EXISTS idx_call_retention_pending ON call_ledger(call_occurrence_id) WHERE json_extract(payload_json,'$.raw_payload_retention') IS NULL AND (json_extract(payload_json,'$.rows') NOT IN ('[]','{}','') OR json_extract(payload_json,'$.body') NOT IN ('[]','{}','') OR json_extract(payload_json,'$.raw_body') NOT IN ('[]','{}','') OR json_extract(payload_json,'$.response_body') NOT IN ('[]','{}','') OR json_extract(payload_json,'$.payload_rows') NOT IN ('[]','{}','') OR json_extract(payload_json,'$.entities') NOT IN ('[]','{}',''))")
        store._conn.execute("CREATE INDEX IF NOT EXISTS idx_admission_retention_witness ON episode_admissions(json_extract(record_json,'$.witness_call_occurrence_id'))")
        for number in range(3):
            for kind, prefix in (("source", "$.sources"), ("recovery", "$.recovery_plan.frame_receipt.sources")):
                store._conn.execute(f"CREATE INDEX IF NOT EXISTS idx_round_retention_{kind}_{number} ON episode_rounds(json_extract(frame_json,'{prefix}[{number}].call_occurrence_id'))")
        store._conn.commit()
    except Exception:
        store._conn.rollback()
        raise
    finally:
        store.release_lease(lease)
    return {"status": "POLICY_INSTALLED", "enabled": policy["enabled"], "approved_policy_sha256": approved_sha256}


def retention_status(store: ObservationScheduleStore) -> dict[str, Any]:
    installed = _control(store, "policy", {})
    policy = installed.get("policy", {})
    pending = _control(store, "checkpoint_archive_refresh_pending")
    return {"enabled": bool(policy.get("enabled", False)), "policy_revision": policy.get("revision"),
            "approved_policy_sha256": installed.get("approved_policy_sha256"), **_control(store, "maintenance", {}),
            "archive_refresh_pending": pending is not None,
            "archive_refresh_checkpoint_sha256": pending.get("checkpoint_sha256") if pending else None}


_CHECKPOINT_CONTEXT_KEYS = (
    "source_identity", "policy", "active_plan", "checkpoint_archive_refresh_pending",
    "checkpoint_archive", "checkpoint_archive_cache_release", "archive_refreshed_at", "maintenance",
)
_CHECKPOINT_CONTEXT_REASONS = (
    "SOURCE_CHANGED", "POLICY_CHANGED", "ACTIVE_PLAN_CHANGED", "PENDING_CHECKPOINT_CHANGED",
    "CHECKPOINT_ARCHIVE_CHANGED", "CACHE_RELEASE_CHANGED", "CHECKPOINT_ARCHIVE_CHANGED", "MAINTENANCE_STATE_CHANGED",
)
CHECKPOINT_MAINTENANCE_YIELD_REASONS = frozenset({*_CHECKPOINT_CONTEXT_REASONS, "WRITER_BUSY",
    "RECLAIM_RECOVERY_REQUIRED", "RECLAIM_CONNECTION_REOPEN_REQUIRED", "CACHE_RELEASE_BUDGET"})


def checkpoint_maintenance_context(store: ObservationScheduleStore) -> dict[str, Any]:
    """Bounded local CAS token; never serialize this internal context in receipts.

    One SQLite statement observes the exact native control bytes together.
    The source UUID and physical incarnation prevent a resumed old caller from
    attributing an outcome to a replaced OPS store. Collector row writes do
    not invalidate the token or hold a lease across remote readback.
    """
    keys = ",".join("?" for _ in _CHECKPOINT_CONTEXT_KEYS)
    rows = dict(store._conn.execute(
        f"SELECT control_key,payload_json FROM retention_control WHERE control_key IN ({keys})",
        _CHECKPOINT_CONTEXT_KEYS))
    return {"source_binding": {"database": _root_binding(store.path), "root": _root_binding(store.path.parent)},
            "controls": {key: rows.get(key) for key in _CHECKPOINT_CONTEXT_KEYS}}


def _checkpoint_context_conflict(store: ObservationScheduleStore, expected: Mapping[str, Any]) -> str | None:
    current = checkpoint_maintenance_context(store)
    if current["source_binding"] != expected.get("source_binding"):
        return "SOURCE_CHANGED"
    for key, reason in zip(_CHECKPOINT_CONTEXT_KEYS, _CHECKPOINT_CONTEXT_REASONS):
        if current["controls"][key] != expected.get("controls", {}).get(key):
            return reason
    return None


def _commit_checkpoint_context(store: ObservationScheduleStore, expected: dict[str, Any]) -> None:
    # Capture our own bytes before commit releases the transaction. A read
    # after commit could bless a peer's intervening policy/plan/outcome.
    advanced = checkpoint_maintenance_context(store)
    store._conn.commit()
    expected.clear()
    expected.update(advanced)


@contextmanager
def checkpoint_maintenance_write(store: ObservationScheduleStore, *, expected_context: dict[str, Any],
                                 now: datetime, lease_owner: str):
    """Short native metadata fence shared by checkpoint phases; no network."""
    lease = store.acquire_lease(lease_owner, clock=now)
    if lease is None:
        raise ObservationScheduleRetentionError("WRITER_BUSY")
    try:
        store._conn.execute("BEGIN IMMEDIATE")
        store._require_write_lease(now, within_transaction=True)
        conflict = _checkpoint_context_conflict(store, expected_context)
        if conflict:
            raise ObservationScheduleRetentionError(conflict)
        yield
        _commit_checkpoint_context(store, expected_context)
    except Exception:
        store._conn.rollback()
        raise
    finally:
        store.release_lease(lease)


def record_maintenance_outcome(store: ObservationScheduleStore, *, state: str, reason: str, now: datetime,
                               expected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if state not in {"FAILED", "READY", "YIELD"} or not re.fullmatch(r"[A-Z0-9_:]+", reason):
        raise ObservationScheduleRetentionError("MAINTENANCE_OUTCOME_INVALID")
    expected = checkpoint_maintenance_context(store) if expected_context is None else expected_context
    try:
        with checkpoint_maintenance_write(store, expected_context=expected, now=now,
                lease_owner="i2-maintenance-outcome"):
            value = _control(store, "maintenance", {})
            value.update(state=state, last_reason=reason, last_run_at=render_utc(now))
            if state == "READY":
                value["last_success_at"] = render_utc(now)
            _set_control(store, "maintenance", value)
    except (ObservationScheduleRetentionError, ObservationScheduleStoreError) as exc:
        if str(exc) in CHECKPOINT_MAINTENANCE_YIELD_REASONS:
            return {"status": "YIELD", "reason": str(exc)}
        raise
    return {"status": "RECORDED", "state": state, "reason": reason}


def register_checkpoint_retirement_archive(store: ObservationScheduleStore, *,
        proof: Mapping[str, Any], isolated_root: Path, source_root: Path, now: datetime,
        expected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap the existing independent checkpoint restore as a durable cold pin.

    Called by the normal checkpoint owner after actual remote content readback;
    no new provider/service. The independent restored source files remain COLD.
    A disk-backed path index keeps future candidate checks bounded.
    """
    expected = checkpoint_maintenance_context(store) if expected_context is None else expected_context
    conflict = _checkpoint_context_conflict(store, expected)
    if conflict:
        raise ObservationScheduleRetentionError(conflict)
    if proof.get("terminal") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
        raise ObservationScheduleRetentionError("INDEPENDENT_CHECKPOINT_RESTORE_REQUIRED")
    if proof.get("result_inventory_sha256") != (proof.get("restore") or {}).get("raw_inventory_sha256"):
        raise ObservationScheduleRetentionError("CHECKPOINT_SOURCE_INVENTORY_MISMATCH")
    if proof.get("restored_data_root_relative") != "restored" or proof.get("objects_relative") != "objects":
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_OWNER_LAYOUT_REQUIRED")
    restored_root = isolated_root / str(proof.get("restored_data_root_relative", "restored"))
    objects_root = isolated_root / str(proof.get("objects_relative", "objects"))
    if not _within(restored_root, isolated_root) or not _within(objects_root, isolated_root):
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_PATH_UNSAFE")
    source_relative = store.path.relative_to(source_root).as_posix()
    archived_db = restored_root / source_relative
    if not archived_db.is_file():
        raise ObservationScheduleRetentionError("CHECKPOINT_SQLITE_CLOSURE_MISSING")
    with _sqlite_connection(archived_db.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
        source_id = json.loads(connection.execute("SELECT payload_json FROM retention_control WHERE control_key='source_identity'").fetchone()[0])["source_id"]
    if source_id != _source_identity(store)["source_id"]:
        raise ObservationScheduleRetentionError("CHECKPOINT_SOURCE_IDENTITY_MISMATCH")
    # Reuse the checkpoint owner's actual local reconstruction exactly once at
    # registration. A forged operational_inventory is only a JSON assertion;
    # source rows must also belong to the independently downloaded ZIP bytes.
    from solana_alpha_lab.factory.offhost_backup import (
        OffhostBackupError, _load_prune_proof_artifacts, _verify_prune_proof_oracle,
    )
    source_binding = _archive_binding(archived_db)
    reconstructed_source = None
    def verify_source_tree(actual_root: Path, reconstructed_root: Path) -> None:
        nonlocal reconstructed_source
        actual_db, reconstructed_db = actual_root / source_relative, reconstructed_root / source_relative
        if actual_db.resolve() != archived_db.resolve() or not reconstructed_db.is_file():
            raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_RECONSTRUCTION_MISMATCH")
        with _sqlite_connection(actual_db.as_uri() + "?mode=ro&immutable=1", uri=True) as actual, \
                _sqlite_connection(reconstructed_db.as_uri() + "?mode=ro&immutable=1", uri=True) as reconstructed:
            actual_fingerprint = native_identity_fingerprint(actual, recovery_causal=True)
            reconstructed_source = native_identity_fingerprint(reconstructed, recovery_causal=True)
            if actual_fingerprint != reconstructed_source:
                raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_RECONSTRUCTION_MISMATCH")
    try:
        artifacts = _load_prune_proof_artifacts([isolated_root / ".remote-restore-proof.json"])
        artifact = artifacts[str(proof["checkpoint_filename"])]
        if artifact["payload"] != dict(proof):
            raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_PROOF_ARTIFACT_MISMATCH")
        _verify_prune_proof_oracle(artifact, objects_root / str(proof["checkpoint_filename"]),
            verified_tree_consumer=verify_source_tree)
    except OffhostBackupError as exc:
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_RECONSTRUCTION_UNAVAILABLE") from exc
    if reconstructed_source is None or _archive_binding(archived_db) != source_binding:
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_RECONSTRUCTION_MISMATCH")
    inventory_path = isolated_root / "retirement-inventory.sqlite"
    existing_index = inventory_path.exists()
    with _sqlite_connection(inventory_path) as index:
        index.execute("CREATE TABLE IF NOT EXISTS inventory(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL)")
        entries = {str(entry["path"]): entry for entry in [*proof["restore"]["restored"], *proof.get("supplemental_raw_inventory", [])]}
        for entry in entries.values():
            relative = str(entry["path"])
            actual = (restored_root / relative).resolve()
            if not _within(actual, restored_root) or actual.is_symlink():
                raise ObservationScheduleRetentionError("CHECKPOINT_SOURCE_PATH_UNSAFE")
            # The owner has already checked raw inventory before decorating the
            # operational SQLite marker; retain its original hash separately.
            values = (relative, entry["sha256"], int(entry["bytes"]))
            if existing_index:
                found = index.execute("SELECT path,sha256,bytes FROM inventory WHERE path=?", (relative,)).fetchone()
                if found != values:
                    raise ObservationScheduleRetentionError("CHECKPOINT_INVENTORY_RETRY_MISMATCH")
            else:
                index.execute("INSERT INTO inventory VALUES(?,?,?)", values)
        if index.execute("SELECT count(*) FROM inventory").fetchone()[0] != len(entries):
            raise ObservationScheduleRetentionError("CHECKPOINT_INVENTORY_RETRY_MISMATCH")
    record = {"proof_class": "REMOTE_CHECKPOINT_RESTORE_VERIFIED", "source_id": source_id,
              "archive_path": str(archived_db.resolve()), "archive_sha256": proof["checkpoint_sha256"],
              "checkpoint_filename": proof["checkpoint_filename"], "checkpoint_sha256": proof["checkpoint_sha256"],
              "result_inventory_sha256": proof["result_inventory_sha256"],
              "objects_root": str(objects_root.resolve()), "restored_root": str(restored_root.resolve()),
              "cache_root": str(isolated_root.resolve()),
              "source_root": str(source_root.resolve()), "inventory_path": str(inventory_path.resolve()),
              "raw_source_root_relative": "local/factory_v1/observation_rdp",
              "verified_objects": list(proof["verified_objects"]),
              "source_reconstruction": {"checkpoint_sha256": proof["checkpoint_sha256"],
                  "fingerprint": reconstructed_source},
              "pin_objects": sorted({str(p["filename"]) for p in proof["verified_objects"]} | {str(proof["checkpoint_filename"])}),
              "file_bindings": [_archive_binding(archived_db), _archive_binding(inventory_path)]}
    with _sqlite_connection(archived_db.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
        record["call_highwater"] = int(connection.execute("SELECT COALESCE(MAX(rowid),0) FROM call_ledger").fetchone()[0])
    _verify_checkpoint_archive(record, deep=True)
    from solana_alpha_lab.factory.remote_ops import backup_plane_lock
    with backup_plane_lock(source_root, timeout_seconds=0):
        with checkpoint_maintenance_write(store, expected_context=expected, now=now,
                lease_owner="i2-verified-checkpoint-pin"):
            previous = _control(store, "checkpoint_archive")
            previous_release = _control(store, "checkpoint_archive_cache_release")
            if previous_release and (not previous or previous["checkpoint_sha256"] != record["checkpoint_sha256"]):
                raise ObservationScheduleRetentionError("PRIOR_CHECKPOINT_CACHE_RELEASE_REQUIRED")
            if previous and previous.get("cache_root") != record["cache_root"]:
                _set_control(store, "checkpoint_archive_cache_release", {
                    "checkpoint_sha256": previous["checkpoint_sha256"], "cache_root": previous["cache_root"],
                    "file_bindings": previous["file_bindings"], "archive_path": previous["archive_path"],
                    "inventory_path": previous["inventory_path"], "pin_objects": previous["pin_objects"]})
            _set_control(store, "checkpoint_archive", record)
            # Retry rescan preserves effects and the former durable cursor.
            store._conn.execute("DELETE FROM retention_control WHERE control_key='active_plan'")
            store._conn.executemany("INSERT OR IGNORE INTO retention_archive_pins VALUES(?,?)", [(name, record["checkpoint_sha256"]) for name in record["pin_objects"]])
            pending = _control(store, "checkpoint_archive_refresh_pending")
            if pending and pending.get("checkpoint_sha256") == record["checkpoint_sha256"]:
                store._conn.execute("DELETE FROM retention_control WHERE control_key='checkpoint_archive_refresh_pending'")
            _set_control(store, "archive_refreshed_at", render_utc(now))
            maintenance = _control(store, "maintenance", {})
            if maintenance.get("archive_discovery"):
                maintenance["archive_discovery"] = []
                _set_control(store, "maintenance", maintenance)
    release = checkpoint_archive_cache_releasable(store)
    return {"status": "CHECKPOINT_COLD_PIN_REGISTERED", "checkpoint_sha256": record["checkpoint_sha256"], "pin_objects": record["pin_objects"],
            "previous_cache_release": release.get("token")}


def checkpoint_archive_cache_releasable(store: ObservationScheduleStore, isolated_root: Path | None = None) -> dict[str, Any]:
    token = _control(store, "checkpoint_archive_cache_release")
    if not token:
        return {"status": "NONE"}
    if isolated_root is not None and Path(token["cache_root"]).resolve() != isolated_root.resolve():
        raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_IDENTITY_MISMATCH")
    plan = _control(store, "active_plan") or {}
    for proof in plan.get("archive_registry", {}).values():
        if (proof.get("cache_root") == token["cache_root"]
                or proof.get("archive_path") == token["archive_path"]):
            return {"status": "WAIT", "reason": "CHECKPOINT_CACHE_ACTIVE_CONSUMER"}
    pending = _control(store, "checkpoint_archive_refresh_pending") or {}
    if pending.get("checkpoint_sha256") == token["checkpoint_sha256"]:
        return {"status": "WAIT", "reason": "CHECKPOINT_CACHE_ACTIVE_CONSUMER"}
    # Untouched bodies remain HOT. An absent raw dependency in both caches is
    # not a consumer of the old cache: its pinned immutable day archive can be
    # downloaded for the next bounded batch. Only exact consumers block release.
    current = _control(store, "checkpoint_archive")
    if not current or current.get("cache_root") == token["cache_root"]:
        return {"status": "WAIT", "reason": "CHECKPOINT_CACHE_REPLACEMENT_MISSING"}
    _verify_checkpoint_archive(current, deep=False)
    pins = token.get("pin_objects") or []
    if (not pins or len(pins) > 128 or any(store._conn.execute(
            "SELECT 1 FROM retention_archive_pins WHERE object_name=?", (name,)).fetchone() is None for name in pins)):
        return {"status": "WAIT", "reason": "CHECKPOINT_CACHE_REMOTE_PINS_REQUIRED"}
    if not Path(token["cache_root"]).exists():
        return {"status": "RELEASABLE", "token": token}  # Delete-before-ack recovery.
    deleting = token.get("deletion_started")
    if deleting is not None:
        # Missing archive/index/owner-intent files are expected only after
        # this exact native deletion intent was committed before filesystem
        # mutation. An arbitrary incomplete restore never gains this bypass.
        if (not isinstance(deleting, dict) or deleting.get("checkpoint_sha256") != token["checkpoint_sha256"]
                or not re.fullmatch(r"[0-9a-f]{64}",str(deleting.get("intent_sha256", "")))
                or deleting.get("cache_binding") != _root_binding(Path(token["cache_root"]))):
            raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_DELETION_IDENTITY_CONFLICT")
        intent_path = Path(token["cache_root"]) / ".remote-restore-intent.json"
        if intent_path.is_symlink() or (intent_path.exists() and _file_hash(intent_path) != deleting["intent_sha256"]):
            raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_DELETION_IDENTITY_CONFLICT")
    elif [_archive_binding(Path(token[key])) for key in ("archive_path", "inventory_path")] != token["file_bindings"]:
        raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_BINDING_CHANGED")
    return {"status": "RELEASABLE", "token": token}


def start_checkpoint_archive_cache_deletion(store: ObservationScheduleStore, *,
        token: Mapping[str, Any], now: datetime) -> None:
    """Persist exact partial-delete recovery inside the caller's native fence."""
    if not store._conn.in_transaction:
        raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_FENCE_REQUIRED")
    store._require_write_lease(now, within_transaction=True)
    if _control(store, "checkpoint_archive_cache_release") != dict(token):
        raise ObservationScheduleRetentionError("CACHE_RELEASE_CHANGED")
    target = Path(token["cache_root"])
    encoded = (target / ".remote-restore-intent.json").read_bytes()
    if json.loads(encoded).get("checkpoint_sha256") != token["checkpoint_sha256"]:
        raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_IDENTITY_CONFLICT")
    _set_control(store, "checkpoint_archive_cache_release", {**token, "deletion_started": {
        "checkpoint_sha256": token["checkpoint_sha256"], "cache_binding": _root_binding(target),
        "intent_sha256": hashlib.sha256(encoded).hexdigest(), "started_at": render_utc(now)}})


def _acknowledge_checkpoint_archive_cache_release(store: ObservationScheduleStore, *, checkpoint_sha256: str) -> None:
    token = _control(store, "checkpoint_archive_cache_release")
    if not token or token["checkpoint_sha256"] != checkpoint_sha256 or Path(token["cache_root"]).exists():
        raise ObservationScheduleRetentionError("CHECKPOINT_CACHE_RELEASE_NOT_COMPLETED")
    store._conn.execute("DELETE FROM retention_control WHERE control_key='checkpoint_archive_cache_release'")


def acknowledge_checkpoint_archive_cache_release(store: ObservationScheduleStore, *, checkpoint_sha256: str, now: datetime,
                                                expected_context: dict[str, Any] | None = None) -> None:
    expected = checkpoint_maintenance_context(store) if expected_context is None else expected_context
    with checkpoint_maintenance_write(store, expected_context=expected, now=now, lease_owner="i2-cache-release-ack"):
        _acknowledge_checkpoint_archive_cache_release(store, checkpoint_sha256=checkpoint_sha256)


def _verify_checkpoint_archive(record: Mapping[str, Any], *, deep: bool) -> None:
    reconstruction = record.get("source_reconstruction") or {}
    if (reconstruction.get("checkpoint_sha256") != record.get("checkpoint_sha256")
            or not isinstance(reconstruction.get("fingerprint"), dict)):
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_RECONSTRUCTION_REQUIRED")
    archived = Path(record["archive_path"])
    inventory = Path(record["inventory_path"])
    if [_archive_binding(archived), _archive_binding(inventory)] != record["file_bindings"]:
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_BINDING_CHANGED")
    from solana_alpha_lab.factory.offhost_backup import validate_recovery_checkpoint
    object_root = Path(record["objects_root"])
    if not deep:
        return
    for item in record["verified_objects"]:
        path = object_root / str(item["filename"])
        if not _within(path, object_root) or _file_hash(path) != item["sha256"]:
            raise ObservationScheduleRetentionError("CHECKPOINT_REMOTE_CONTENT_PROOF_MISMATCH")
    checkpoint = object_root / str(record["checkpoint_filename"])
    document = validate_recovery_checkpoint(checkpoint)
    if _file_hash(checkpoint) != record["checkpoint_sha256"] or document["result_inventory_sha256"] != record["result_inventory_sha256"]:
        raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_INVENTORY_MISMATCH")
    with _sqlite_connection(archived.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ObservationScheduleRetentionError("CHECKPOINT_ARCHIVE_SQLITE_CORRUPT")


def _verify_archived_raw(proof: Mapping[str, Any], relative: str, *, max_bytes: int = MAX_PLAN_BYTES) -> None:
    root = Path(proof["restored_root"])
    relative = str(Path(proof["raw_source_root_relative"]) / relative).replace("\\", "/")
    path = root / relative
    if not _within(path, root) or path.is_symlink():
        raise ObservationScheduleRetentionError("RAW_ARCHIVE_DEPENDENCY_PATH_UNSAFE")
    with _sqlite_connection(Path(proof["inventory_path"]).as_uri() + "?mode=ro", uri=True) as inventory:
        row = inventory.execute("SELECT sha256,bytes FROM inventory WHERE path=?", (relative,)).fetchone()
    if row is not None and row[1] > max_bytes:
        raise ObservationScheduleRetentionError("RAW_ARCHIVE_DEPENDENCY_OVERSIZE_REFUSED")
    if row is None or not path.is_file() or path.stat().st_size != row[1] or _file_hash(path) != row[0]:
        raise ObservationScheduleRetentionError("RAW_ARCHIVE_DEPENDENCY_NOT_VERIFIED")


def checkpoint_archive_refresh_required(root: Path, *, now: datetime,
                                        expected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure bounded signal; external readback needs approved refresh policy.

    A previously independently restored checkpoint remains sufficient for rows
    it already contains. New calls do not force daily full-chain downloading.
    """
    from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
    runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
    path = (root / str(runtime["ops_store_relative"])).resolve()
    if not path.is_file():
        return {"required": False, "reason": "SOURCE_NOT_PRESENT"}
    store = ObservationScheduleStore(path, readonly=True, immutable=False)
    try:
        if expected_context is not None:
            if not expected_context:
                expected_context.update(checkpoint_maintenance_context(store))
            conflict = _checkpoint_context_conflict(store, expected_context)
            if conflict:
                raise ObservationScheduleRetentionError(conflict)
        installed = _control(store, "policy", {})
        policy = installed.get("policy", {})
        refresh = policy.get("archive_refresh", {})
        if not policy.get("enabled") or not policy.get("auto_retire_terminal") or refresh.get("enabled") is not True:
            return {"required": False, "reason": "ARCHIVE_REFRESH_NOT_COMMISSIONED"}
        pending = _control(store, "checkpoint_archive_refresh_pending")
        if pending:
            if pending.get("policy_sha256") != installed["approved_policy_sha256"]:
                return {"required": False, "reason": "ARCHIVE_REFRESH_PENDING_POLICY_CHANGED"}
            if pending.get("reconciliation_state") == "BLOCKED_POLICY":
                return {"required": False, "reason": pending["reconciliation_reason"]}
            return {"required": True, "reason": "RESUME_EXACT_ARCHIVE_REFRESH", "pending": pending,
                    "budget": dict(refresh), "policy_sha256": installed["approved_policy_sha256"]}
        state = _control(store, "maintenance", {})
        if state.get("archive_discovery"):
            return {"required": True, "reason": "DURABLE_TERMINAL_ARCHIVE_DISCOVERY", "budget": dict(refresh), "policy_sha256": installed["approved_policy_sha256"]}
        if state.get("last_reason") in {"RAW_ARCHIVE_DEPENDENCY_NOT_VERIFIED", "COLD_ARCHIVE_CANDIDATE_MISMATCH", "RAW_BODY_DEPENDENCY_NOT_ARCHIVED"} and _control(store, "active_plan"):
            return {"required": True, "reason": "EXACT_CANDIDATE_ARCHIVE_CLOSURE_MISSING", "budget": dict(refresh), "policy_sha256": installed["approved_policy_sha256"]}
        refreshed = _control(store, "archive_refreshed_at")
        if refreshed and (now - parse_utc(refreshed)).total_seconds() < int(refresh["minimum_interval_seconds"]):
            return {"required": False, "reason": "ARCHIVE_REFRESH_CADENCE_WAIT"}
        archive = _control(store, "checkpoint_archive", {})
        after = int(archive.get("call_highwater", 0))
        cutoff = render_utc(retention_cutoff(now=now, raw_retention_days=int(policy["min_age_days"])))
        for row in store._conn.execute("SELECT rowid,request_sha256,call_occurrence_id FROM call_ledger WHERE rowid>? AND state='COMPLETED' AND updated_at<? ORDER BY rowid LIMIT ?", (after, cutoff, int(policy["max_rows"]))):
            for scope in _call_owner_scopes(store, occurrence=str(row[2]), request=str(row[1]), limit=int(policy["max_rows"])):
                activation = store._conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
                if activation is not None and activation[0] == "COMPLETE" and _scope_allowed(store, scope, policy):
                    return {"required": True, "reason": "UNCOVERED_TERMINAL_SOURCE", "budget": dict(refresh), "policy_sha256": installed["approved_policy_sha256"]}
        return {"required": False, "reason": "ARCHIVE_COVERAGE_SUFFICIENT"}
    finally:
        store.close()


def checkpoint_archive_refresh_intent(store: ObservationScheduleStore, *, checkpoint: Mapping[str, Any],
        cold_relative: str, now: datetime, source_root: Path,
        expected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pre-pin exact recovery closure before network; retries reuse this target."""
    expected = checkpoint_maintenance_context(store) if expected_context is None else expected_context
    installed = _control(store, "policy", {})
    policy = installed.get("policy", {})
    refresh = policy.get("archive_refresh", {})
    if not policy.get("enabled") or refresh.get("enabled") is not True or cold_relative != refresh.get("cold_root_relative"):
        raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_NOT_COMMISSIONED")
    validate_policy(policy)
    payload = dict(checkpoint.get("checkpoint", checkpoint))
    filename = str(checkpoint.get("checkpoint_filename", checkpoint.get("filename", "")))
    digest = str(checkpoint.get("checkpoint_sha256", checkpoint.get("sha256", "")))
    if not filename or Path(filename).name != filename or len(digest) != 64:
        raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_CHECKPOINT_IDENTITY_INVALID")
    names = {filename}
    for item in [payload.get("base_full", {}), *payload.get("ordered_deltas", [])]:
        name = str(item.get("filename", ""))
        if not name or Path(name).name != name:
            raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_CHECKPOINT_CLOSURE_INVALID")
        names.add(name)
    supplemental = list(checkpoint.get("supplemental_archives", []))
    for item in supplemental:
        name = str(item.get("filename", ""))
        if not re.fullmatch(r"ARCHIVE_[0-9a-f]{64}\.zip", name) or item.get("sha256") != name[8:-4]:
            raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_RAW_CLOSURE_INVALID")
        names.add(name)
    if len(names) > int(refresh["max_objects"]):
        raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_OBJECT_BUDGET_EXCEEDED")
    intent = {"checkpoint_filename": filename, "checkpoint_sha256": digest,
              "checkpoint": payload, "cold_root_relative": cold_relative, "pin_objects": sorted(names),
              "supplemental_archives": supplemental,
              "policy_sha256": installed["approved_policy_sha256"], "created_at": render_utc(now),
              "source_id": _source_identity(store)["source_id"]}
    from solana_alpha_lab.factory.remote_ops import backup_plane_lock
    with backup_plane_lock(source_root, timeout_seconds=0):
        with checkpoint_maintenance_write(store, expected_context=expected, now=now,
                lease_owner="i2-archive-refresh-intent"):
            pending = _control(store, "checkpoint_archive_refresh_pending")
            if pending is not None:
                if pending.get("policy_sha256") != installed["approved_policy_sha256"]:
                    raise ObservationScheduleRetentionError("ARCHIVE_REFRESH_PENDING_POLICY_CHANGED")
                if pending.get("reconciliation_state") == "BLOCKED_POLICY":
                    raise ObservationScheduleRetentionError(pending["reconciliation_reason"])
                return pending
            store._conn.executemany("INSERT OR IGNORE INTO retention_archive_pins VALUES(?,?)", [(name, digest) for name in names])
            _set_control(store, "checkpoint_archive_refresh_pending", intent)
            return intent


def retirement_raw_archive_dependencies(store: ObservationScheduleStore, *, source_root: Path,
                                         now: datetime) -> dict[str, Any]:
    """Resolve exact HOT90 archives for bounded naturally terminal raw readers.

    The existing closed-day receipt owns remote identity. This is a read-only
    source lookup, not a new raw retention/eviction authority or whole-RDP scan.
    Caller downloads exact archives and validates their manifests before hydrate.
    """
    from solana_alpha_lab.factory.hot90_closed_day_loop import read_receipt, receipt_verified
    installed = _control(store, "policy", {})
    policy = installed.get("policy", {})
    if not policy.get("enabled") or not policy.get("auto_retire_terminal"):
        return {"archives": [], "raw_bytes": 0}
    validate_policy(policy)
    archive = _control(store, "checkpoint_archive", {})
    after = int(archive.get("call_highwater", 0))
    cutoff = render_utc(retention_cutoff(now=now, raw_retention_days=int(policy["min_age_days"])))
    archives: dict[str, dict[str, Any]] = {}
    remaining = int(policy["max_bytes"])
    started = time.monotonic()
    rdp = source_root / "local/factory_v1/observation_rdp"
    active_plan = _control(store, "active_plan")
    if active_plan:
        progress = store._conn.execute("SELECT next_candidate FROM retention_progress WHERE plan_id=?", (active_plan["plan_id"],)).fetchone()
        offset = int(progress[0]) if progress else 0
        candidate_ids = [c["row"]["source_rowid"] for c in active_plan["candidates"][offset:] if c["table"] == "call_ledger"]
        rows = [store._conn.execute("SELECT rowid,request_sha256,length(CAST(payload_json AS BLOB)),call_occurrence_id FROM call_ledger WHERE rowid=?", (rowid,)).fetchone() for rowid in candidate_ids]
    elif _control(store, "maintenance", {}).get("archive_discovery"):
        discovered = _control(store, "maintenance")["archive_discovery"]
        rows = [store._conn.execute("SELECT rowid,request_sha256,length(CAST(payload_json AS BLOB)),call_occurrence_id FROM call_ledger WHERE rowid=?", (item["source_rowid"],)).fetchone() for item in discovered if item["table"] == "call_ledger"]
    else:
        rows = store._conn.execute("SELECT rowid,request_sha256,length(CAST(payload_json AS BLOB)),call_occurrence_id FROM call_ledger WHERE rowid>? AND state='COMPLETED' AND updated_at<? ORDER BY rowid LIMIT ?", (after, cutoff, int(policy["max_rows"])))
    for row in rows:
        if row is None:
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_RESOLVER_CANDIDATE_STALE")
        if time.monotonic() - started >= float(policy["max_wall_seconds"]):
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_RESOLVER_WALL_BUDGET")
        if row[2] > remaining:
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_RESOLVER_BYTE_BUDGET")
        remaining -= row[2]
        scopes = _call_owner_scopes(store, occurrence=str(row[3]), request=str(row[1]), limit=int(policy["max_rows"]))
        if not scopes:
            continue
        eligible = True
        for scope in scopes:
            activation = store._conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
            if not _scope_allowed(store, scope, policy) or activation is None or activation[0] != "COMPLETE":
                eligible = False
                break
        if not eligible:
            continue
        payload = json.loads(store._conn.execute("SELECT payload_json FROM call_ledger WHERE rowid=?", (row[0],)).fetchone()[0])
        relative = payload.get("raw_body_rel")
        if not relative or not _payload_has_compactable_body(payload):
            continue
        match = re.match(r"datasets/raw_evidence/(\d{8})/", str(relative))
        if match is None:
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_DAY_OWNERSHIP_UNKNOWN")
        path = (rdp / str(relative)).resolve()
        if not _within(path, rdp) or path.is_symlink() or not path.is_file():
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_SOURCE_MISSING")
        size = path.stat().st_size
        if size > remaining:
            raise ObservationScheduleRetentionError("RAW_ARCHIVE_RESOLVER_BYTE_BUDGET")
        remaining -= size
        receipt = read_receipt(source_root, match[1])
        if not receipt_verified(receipt):
            raise ObservationScheduleRetentionError("HOT90_INDEPENDENT_ARCHIVE_REQUIRED")
        filename = str(receipt.get("local_archive_filename", ""))
        digest = str(receipt["local_archive_sha256"])
        if filename != f"ARCHIVE_{digest}.zip":
            raise ObservationScheduleRetentionError("HOT90_ARCHIVE_IDENTITY_MISMATCH")
        archive = archives.setdefault(filename, {"filename": filename, "sha256": digest,
            "inventory_sha256": receipt["inventory_sha256"], "remote_object": receipt["remote_object"], "raw_entries": []})
        entry = {"path": str(relative), "sha256": _file_hash(path), "bytes": size}
        if entry not in archive["raw_entries"]:
            archive["raw_entries"].append(entry)
    return {"archives": list(archives.values()), "raw_bytes": int(policy["max_bytes"]) - remaining}


def _scope_retirement(store: ObservationScheduleStore, scope: tuple[str, str]) -> dict[str, Any] | None:
    if store._conn.execute("SELECT 1 FROM sqlite_master WHERE name='retirement_scopes'").fetchone() is None:
        return None
    row = store._conn.execute("SELECT payload_json FROM retirement_scopes WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
    return None if row is None else json.loads(row[0])


def _check_frozen_lower_bounds(store: ObservationScheduleStore, policy: Mapping[str, Any]) -> None:
    for lineage in policy.get("allowed_managed_lineages", []):
        row = store._conn.execute("SELECT p.payload_json FROM managed_profiles p JOIN managed_control c ON c.collection_lineage_id=p.collection_lineage_id AND c.current_revision=p.revision WHERE p.collection_lineage_id=?", (str(lineage),)).fetchone()
        if row is None:
            raise ObservationScheduleRetentionError("FROZEN_MANAGED_TEMPLATE_UNAVAILABLE")
        template = json.loads(row[0]).get("profile", {}).get("template", {})
        minimum = (template.get("retention") or {}).get("raw_retention_days")
        if not isinstance(minimum, int) or minimum < 1:
            raise ObservationScheduleRetentionError("FROZEN_SOURCE_RETENTION_UNAVAILABLE")
        if int(policy["min_age_days"]) < minimum or int(policy["frozen_min_age_days"]) < minimum:
            raise ObservationScheduleRetentionError("FROZEN_RETENTION_LOWER_BOUND")
    for scope in policy.get("allowed_scopes", []):
        if scope["schedule_sha256"] == "UNAPPROVED":
            continue
        row = store._conn.execute("SELECT document_json FROM registered_schedules WHERE schedule_sha256=?", (scope["schedule_sha256"],)).fetchone()
        if row is None:
            raise ObservationScheduleRetentionError("FROZEN_SOURCE_CONTRACT_UNAVAILABLE")
        source = json.loads(row[0])
        retention = source.get("retention", {})
        minimum = retention.get("raw_retention_days")
        if not isinstance(minimum, int) or minimum < 1:
            raise ObservationScheduleRetentionError("FROZEN_SOURCE_RETENTION_UNAVAILABLE")
        if int(policy["min_age_days"]) < minimum or int(policy["frozen_min_age_days"]) < minimum:
            raise ObservationScheduleRetentionError("FROZEN_RETENTION_LOWER_BOUND")


def _scope_allowed(store: ObservationScheduleStore, scope: tuple[str, str], policy: Mapping[str, Any]) -> bool:
    if scope in {(str(p["schedule_sha256"]), str(p["activation_id"])) for p in policy.get("allowed_scopes", [])}:
        return True
    for lineage in policy.get("allowed_managed_lineages", []):
        child = store._conn.execute("SELECT profile_revision FROM managed_children WHERE collection_lineage_id=? AND schedule_sha256=? AND activation_id=? AND state IN ('ACTIVATED','INTAKE_COMPLETE','TAIL_COMPLETE')", (str(lineage), *scope)).fetchone()
        if child:
            # Reuse the actual historical profile approval owner. A hand-made
            # managed_child row or fake profile_hash cannot grant retirement.
            from solana_alpha_lab.factory.managed_collection import _approval_valid, validate_profile
            profile = store.managed_profile(str(lineage), int(child[0]))
            if profile is None:
                return False
            try:
                validate_profile(profile["payload"]["profile"])
                if not _approval_valid(store, str(lineage), profile):
                    return False
            except (ValueError, KeyError, TypeError):
                return False
            authority = store._conn.execute("SELECT r.payload_json FROM schedule_activations a JOIN authority_receipts r ON r.receipt_sha256=a.authority_receipt_sha256 WHERE a.schedule_sha256=? AND a.activation_id=?", scope).fetchone()
            if authority is None or json.loads(authority[0]).get("standing_grant_sha256") != profile["profile_sha256"]:
                return False
            source_policy = {**dict(policy), "allowed_scopes": [{"schedule_sha256": scope[0], "activation_id": scope[1]}]}
            _check_frozen_lower_bounds(store, source_policy)
            return True
    return False


def _automatic_retirement(store: ObservationScheduleStore, scope: tuple[str, str], policy: Mapping[str, Any]) -> dict[str, Any] | None:
    if not policy.get("auto_retire_terminal") or not _scope_allowed(store, scope, policy):
        return None
    row = store._conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
    archive = _control(store, "checkpoint_archive")
    if row is None or row[0] != "COMPLETE" or not archive:
        return None
    return {"schedule_sha256": scope[0], "activation_id": scope[1], "disallow_resume": True,
            "automatic": True, "retire_pending_due": False, "retire_entities": True,
            "operation_mode": _effective_operation_mode(store, None) or "OPERATE", "archive_proof": archive,
            "policy_sha256": policy_sha256(policy), "archive_locator": archive["checkpoint_filename"]}


def _call_owner_scopes(store: ObservationScheduleStore, *, occurrence: str, request: str,
                       limit: int) -> set[tuple[str, str]]:
    """Exact indexed links from the native due, witness and round owners."""
    scopes: set[tuple[str, str]] = set()
    queries = [("SELECT schedule_sha256,activation_id FROM due_observations WHERE request_sha256=? AND (call_occurrence_id=? OR call_occurrence_id IS NULL OR call_occurrence_id='') LIMIT ?", (request, occurrence, limit + 1)),
               ("SELECT schedule_sha256,activation_id FROM episode_admissions WHERE json_extract(record_json,'$.witness_call_occurrence_id')=? LIMIT ?", (occurrence, limit + 1))]
    for number in range(3):
        for prefix in ("$.sources", "$.recovery_plan.frame_receipt.sources"):
            queries.append((f"SELECT schedule_sha256,activation_id FROM episode_rounds WHERE json_extract(frame_json,'{prefix}[{number}].call_occurrence_id')=? LIMIT ?", (occurrence, limit + 1)))
    examined = 0
    for sql, parameters in queries:
        for row in store._conn.execute(sql, parameters):
            examined += 1
            if examined > limit:
                raise ObservationScheduleRetentionError("CALL_OWNER_SCOPE_BUDGET_REFUSED")
            scopes.add((str(row[0]), str(row[1])))
    return scopes


def _protect(store: ObservationScheduleStore, row: Mapping[str, Any], table: str,
             policy: Mapping[str, Any], now: datetime) -> tuple[str | None, list[dict[str, Any]]]:
    conn = store._conn
    request = str(row["request_sha256"])
    occurrence = str(row.get("call_occurrence_id", ""))
    if table == "call_ledger" and row["state"] != "COMPLETED":
        return "NOT_COMPLETED", []
    stamp = _safe_parse(row["updated_at"] if table == "call_ledger" else row["created_at"])
    if stamp is None or stamp >= retention_cutoff(now=now, raw_retention_days=int(policy["min_age_days"])):
        return "YOUNGER_THAN_RETENTION", []
    if occurrence in policy.get("protected_occurrence_ids", []) or request in policy.get("protected_request_sha256", []):
        return "FROZEN_EXPORT_CAPTURE_PIN", []
    if conn.execute("SELECT 1 FROM call_ledger WHERE request_sha256=? AND state <> 'COMPLETED' LIMIT 1", (request,)).fetchone():
        return "STARTED_UNKNOWN_OR_NONTERMINAL_ATTEMPT", []
    # Occurrence-less legacy links are ambiguous shared-request consumers.
    projection = "schedule_sha256,activation_id,state,length(CAST(payload_json AS BLOB)) AS payload_bytes,(instr(payload_json,'\"frozen') OR instr(payload_json,'\"export') OR instr(payload_json,'\"capture') OR instr(payload_json,'\"raw_member')) AS dependency_pin"
    query = f"SELECT {projection} FROM due_observations WHERE request_sha256=?"
    params: tuple = (request,)
    if table == "call_ledger":
        query += " AND (call_occurrence_id=? OR call_occurrence_id IS NULL OR call_occurrence_id='')"
        params = (request, occurrence)
    due = [dict(item) for item in conn.execute(query + " LIMIT ?", (*params, int(policy["max_rows"]) + 1))]
    if len(due) > int(policy["max_rows"]) or sum(int(item["payload_bytes"]) for item in due) > int(policy["max_bytes"]):
        return "DEPENDENCY_SCAN_BUDGET_REFUSED", []
    scopes = {(str(item["schedule_sha256"]), str(item["activation_id"])) for item in due}
    if table == "call_ledger":
        scopes.update(_call_owner_scopes(store, occurrence=occurrence, request=request, limit=int(policy["max_rows"])))
    if not scopes:
        # No due row is NOT proof of no consumers. An exact orphan identity
        # named by retirement is the sole alternate ownership path.
        for allowed in policy.get("allowed_scopes", []):
            scope = (str(allowed["schedule_sha256"]), str(allowed["activation_id"]))
            retired = _scope_retirement(store, scope)
            ids = (retired or {}).get("call_occurrence_ids" if table == "call_ledger" else "poll_slot_ids", [])
            if (occurrence if table == "call_ledger" else row["poll_slot_id"]) in ids:
                scopes.add(scope)
    if not scopes:
        return "UNKNOWN_OWNERSHIP", []
    retirements = []
    for scope in sorted(scopes):
        if not _scope_allowed(store, scope, policy):
            return "SCOPE_NOT_ALLOWED", []
        retired = _scope_retirement(store, scope) or _automatic_retirement(store, scope, policy)
        if not retired and policy.get("auto_retire_terminal"):
            activation = conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
            if activation is not None and activation[0] == "COMPLETE":
                # Discovery follows the same bounded native cursor as selection.
                # It does not invent an archive or permit a mutation.
                retired = {"schedule_sha256": scope[0], "activation_id": scope[1],
                           "disallow_resume": True, "automatic": True,
                           "archive_missing": True, "retire_pending_due": False}
        if not retired or retired.get("disallow_resume") is not True:
            return "EXPLICIT_RETIREMENT_REQUIRED", []
        if retired.get("automatic") or (retired.get("archive_proof") or {}).get("proof_class") == "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
            # Remote provenance stays immutable; current verified source closure
            # supplies any still-uncompacted rows after an old local cache exits.
            current_archive = _control(store, "checkpoint_archive")
            if current_archive:
                retired = {**retired, "archive_proof": current_archive}
        activation = conn.execute("SELECT state FROM schedule_activations WHERE schedule_sha256=? AND activation_id=?", scope).fetchone()
        if activation is None or activation[0] in {"ACTIVE", "DRAINING", "UNREGISTERED"}:
            return "ACTIVE_OR_TAIL_SCOPE", []
        for item in due:
            if (item["schedule_sha256"], item["activation_id"]) != scope:
                continue
            if item["state"] not in SCIENTIFIC_CLOSED_DUE_STATES:
                if item["state"] != "PENDING" or retired.get("retire_pending_due") is not True:
                    return "UNRESOLVED_OR_NONTERMINAL_DUE", []
            if item["dependency_pin"]:
                return "FROZEN_EXPORT_CAPTURE_PIN", []
        if conn.execute("SELECT 1 FROM episode_admissions WHERE schedule_sha256=? AND activation_id=? AND final_deadline_at>=? LIMIT 1", (*scope, render_utc(now))).fetchone():
            return "EPISODE_TAIL", []
        if conn.execute("SELECT 1 FROM episode_rounds WHERE schedule_sha256=? AND activation_id=? AND state='STARTED' LIMIT 1", scope).fetchone():
            return "ROUND_RECOVERY", []
        if conn.execute("SELECT 1 FROM episode_outbox WHERE schedule_sha256=? AND activation_id=? AND published_content_sha256 IS NULL LIMIT 1", scope).fetchone():
            return "PENDING_OUTBOX", []
        if conn.execute("SELECT 1 FROM episode_admissions WHERE schedule_sha256=? AND activation_id=? LIMIT 1", scope).fetchone() and not retired.get("archive_missing") and retired["archive_proof"].get("proof_class") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
            return "EPISODE_INDEPENDENT_SOURCE_CLOSURE_REQUIRED", []
        # Jobs have no typed scope key; unknown unfinished ownership protects.
        if conn.execute("SELECT 1 FROM publication_jobs WHERE stage NOT IN ('COMPLETED','PUBLISHED','COMPLETE') LIMIT 1").fetchone():
            return "PUBLICATION_JOB_OR_UNKNOWN_DEPENDENCY", []
        if retired.get("unresolved_dependency_pins") or retired.get("frozen_dependency_pins"):
            return "FROZEN_EXPORT_CAPTURE_PIN", []
        if retired.get("archive_missing"):
            return "AUTOMATIC_ARCHIVE_PROOF_REQUIRED", []
        retirements.append(retired)
    return None, retirements


def _metadata_page(store: ObservationScheduleStore, table: str, after: int, highwater: int, limit: int):
    identity = "call_occurrence_id" if table == "call_ledger" else "poll_slot_id"
    extra = ",attempt_id,state,primitive_id,updated_at" if table == "call_ledger" else ""
    hint = predicate = ""
    if table == "call_ledger":
        indexed = store._conn.execute("SELECT sql FROM sqlite_master WHERE name='idx_call_retention_pending'").fetchone()
        if indexed:
            hint = " INDEXED BY idx_call_retention_pending"
            predicate = " AND " + str(indexed[0]).split(" WHERE ", 1)[1]
    return store._conn.execute(f"SELECT rowid AS source_rowid,{identity},request_sha256,created_at,length(CAST(payload_json AS BLOB)) AS payload_bytes{extra} FROM {table}{hint} WHERE rowid>? AND rowid<=?{predicate} ORDER BY rowid LIMIT ?", (after, highwater, limit))


def build_retirement_plan(store: ObservationScheduleStore, *, now: datetime, policy: Mapping[str, Any],
                          after: Mapping[str, int] | None = None,
                          operation_mode: str | None = None) -> dict[str, Any]:
    validate_policy(policy)
    mode = validate_retention_operation_mode(store, operation_mode=operation_mode, policy=policy)
    _check_frozen_lower_bounds(store, policy)
    if store._conn.execute("SELECT 1 FROM sqlite_master WHERE name='idx_admission_retention_witness'").fetchone() is None:
        raise ObservationScheduleRetentionError("RETENTION_OWNER_INDICES_UNCOMMISSIONED")
    started = time.monotonic()
    remaining = int(policy["max_bytes"])
    max_rows = int(policy["max_rows"])
    candidates, exclusions = [], {}
    archive_discovery = []
    refusals, refusal_resolutions = [], []
    archive_registry: dict[str, dict[str, Any]] = {}
    cursor = {"call_ledger": 0, "poll_slots": 0, **dict(after or {})}
    scanned = 0
    exhausted = True
    store._conn.execute("BEGIN")
    try:
        highwater = {table: int(store._conn.execute(f"SELECT COALESCE(MAX(rowid),0) FROM {table}").fetchone()[0]) for table in ("call_ledger", "poll_slots")}
        source = _source_identity(store)
        for table in policy["allowed_classes"]:
            for raw in _metadata_page(store, table, int(cursor[table]), highwater[table], max_rows + 1):
                row = dict(raw)
                prior_cursor = cursor[table]
                if scanned >= max_rows or time.monotonic() - started >= float(policy["max_wall_seconds"]):
                    exhausted = False
                    break
                size = int(row["payload_bytes"])
                if size > int(policy["max_bytes"]):
                    # Refuse before materializing even one oversized JSON value.
                    exclusions["OVERSIZE_PAYLOAD_REFUSED"] = exclusions.get("OVERSIZE_PAYLOAD_REFUSED", 0) + 1
                    refusals.append({"table": table, "row": row, "reason": "OVERSIZE_PAYLOAD_REFUSED"})
                    scanned += 1
                    cursor[table] = row["source_rowid"]
                    continue
                refusal_key = f"refusal:{table}:{row['source_rowid']}"
                if _control(store, refusal_key):
                    refusal_resolutions.append({"key": refusal_key, "table": table, "row": row})
                if size > remaining:
                    exhausted = False
                    break
                reason, retirements = _protect(store, row, table, policy, now)
                scanned += 1
                remaining -= size
                cursor[table] = row["source_rowid"]
                if reason:
                    exclusions[reason] = exclusions.get(reason, 0) + 1
                    if reason == "AUTOMATIC_ARCHIVE_PROOF_REQUIRED":
                        archive_discovery.append({"table": table, "source_rowid": row["source_rowid"],
                            "request_sha256": row["request_sha256"],
                            "call_occurrence_id": row.get("call_occurrence_id"),
                            "payload_bytes": row["payload_bytes"]})
                    continue
                payload_text = store._conn.execute(f"SELECT payload_json FROM {table} WHERE rowid=?", (row["source_rowid"],)).fetchone()[0]
                payload = json.loads(payload_text)
                if payload.get("raw_body_rel") and any(r["archive_proof"].get("proof_class") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED" for r in retirements):
                    exclusions["RAW_BODY_DEPENDENCY_NOT_ARCHIVED"] = exclusions.get("RAW_BODY_DEPENDENCY_NOT_ARCHIVED", 0) + 1
                    continue
                if not _payload_has_compactable_body(payload):
                    exclusions["ALREADY_COMPACT_OR_NO_BODY"] = exclusions.get("ALREADY_COMPACT_OR_NO_BODY", 0) + 1
                    continue
                for retired in retirements:
                    _check_retirement_operation_mode(store, retired, mode)
                if any(token in payload for token in ("frozen_release_pin", "export_pin", "capture_pin", "member_chain_pin")):
                    exclusions["FROZEN_EXPORT_CAPTURE_PIN"] = exclusions.get("FROZEN_EXPORT_CAPTURE_PIN", 0) + 1
                    continue
                dependency_bytes = 0
                if payload.get("raw_body_rel"):
                    proof = retirements[0]["archive_proof"]
                    relative = str(Path(proof["raw_source_root_relative"]) / str(payload["raw_body_rel"])).replace("\\", "/")
                    with _sqlite_connection(Path(proof["inventory_path"]).as_uri() + "?mode=ro", uri=True) as index:
                        dependency = index.execute("SELECT bytes FROM inventory WHERE path=?", (relative,)).fetchone()
                    dependency_bytes = int(dependency[0]) if dependency else 0
                    if dependency_bytes > remaining:
                        exclusions["DEPENDENCY_BYTE_BUDGET_REFUSED"] = exclusions.get("DEPENDENCY_BYTE_BUDGET_REFUSED", 0) + 1
                        cursor[table] = prior_cursor
                        exhausted = False
                        break
                    remaining -= dependency_bytes
                proof_ids = []
                for retired in retirements:
                    proof = retired["archive_proof"]
                    proof_id = _hash(proof)
                    archive_registry.setdefault(proof_id, proof)
                    if proof_id not in proof_ids:
                        proof_ids.append(proof_id)
                candidates.append({"table": table, "row": row, "payload_sha256": hashlib.sha256(payload_text.encode()).hexdigest(),
                                   "retirement_sha256": [_hash(item) for item in retirements],
                                   "archive_proofs": proof_ids, "dependency_budget_bytes": dependency_bytes,
                                   "dependency_bytes": dependency_bytes})
            if not exhausted:
                break
        plan = {"schema": PLAN_SCHEMA, "source": source, "policy": dict(policy), "policy_sha256": policy_sha256(policy),
                "cutoff_at": render_utc(retention_cutoff(now=now, raw_retention_days=int(policy["min_age_days"]))),
                "observed_at": render_utc(now), "highwater": highwater, "after": dict(after or {}), "next_cursor": cursor,
                "scanned_rows": scanned, "scanned_bytes": int(policy["max_bytes"]) - remaining,
                "selection_complete": exhausted, "exclusions": exclusions, "candidates": candidates,
                "archive_registry": archive_registry}
        plan["archive_discovery"] = archive_discovery
        plan["refusals"] = refusals
        plan["refusal_resolutions"] = refusal_resolutions
        plan["plan_id"] = _hash(plan)
        return plan
    finally:
        store._conn.rollback()


def _archive_candidate_matches(candidate: Mapping[str, Any]) -> None:
    table = candidate["table"]
    rowid = candidate["row"]["source_rowid"]
    for proof in candidate["archive_proofs"]:
        with _sqlite_connection(Path(proof["archive_path"]).resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as archived:
            identity = "call_occurrence_id" if table == "call_ledger" else "poll_slot_id"
            row = archived.execute(f"SELECT payload_json,{identity} FROM {table} WHERE rowid=?", (rowid,)).fetchone()
            if row is None or hashlib.sha256(row[0].encode()).hexdigest() != candidate["payload_sha256"]:
                raise ObservationScheduleRetentionError("COLD_ARCHIVE_CANDIDATE_MISMATCH")
            if row[1] != candidate["row"][identity]:
                raise ObservationScheduleRetentionError("COLD_ARCHIVE_CANDIDATE_IDENTITY_MISMATCH")
            payload = json.loads(row[0])
            if payload.get("raw_body_rel"):
                if proof.get("proof_class") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
                    raise ObservationScheduleRetentionError("RAW_BODY_DEPENDENCY_NOT_ARCHIVED")
                _verify_archived_raw(proof, str(payload["raw_body_rel"]), max_bytes=int(candidate.get("dependency_budget_bytes", MAX_PLAN_BYTES)))


def apply_retirement_plan(store: ObservationScheduleStore, *, plan: Mapping[str, Any],
                          approved_plan_sha256: str, now: datetime,
                          operation_mode: str | None = None) -> dict[str, Any]:
    document = dict(plan)
    plan_id = document.pop("plan_id", None)
    if plan_id != _hash(document) or plan_id != approved_plan_sha256 or document.get("schema") != PLAN_SCHEMA:
        raise ObservationScheduleRetentionError("PLAN_APPROVAL_OR_IDENTITY_MISMATCH")
    if _source_identity(store) != plan["source"]:
        raise ObservationScheduleRetentionError("PLAN_STALE_SOURCE_OR_SCHEMA")
    policy = plan["policy"]
    validate_policy(policy)
    _check_frozen_lower_bounds(store, policy)
    installed = _control(store, "policy")
    if not installed or installed["approved_policy_sha256"] != plan["policy_sha256"] or installed["policy"] != policy:
        raise ObservationScheduleRetentionError("PLAN_STALE_POLICY")
    validate_retention_operation_mode(store, operation_mode=operation_mode, policy=policy, plan=plan, now=now)
    progress = store._conn.execute("SELECT next_candidate FROM retention_progress WHERE plan_id=?", (plan_id,)).fetchone()
    offset = int(progress[0]) if progress else 0
    if len(plan["candidates"]) > int(policy["max_rows"]) or sum(int(c["row"]["payload_bytes"]) + int(c.get("dependency_bytes", 0)) for c in plan["candidates"]) > int(policy["max_bytes"]):
        raise ObservationScheduleRetentionError("PLAN_BUDGET_EXCEEDED")
    proofs = dict(plan.get("archive_registry", {}))
    for proof in proofs.values():
        verify_cold_archive(proof, deep=False)
    started = time.monotonic()
    lease = store.acquire_lease("i2-retention-chunk", clock=now)
    if lease is None:
        return {"status": "YIELD", "reason": "WRITER_BUSY", "plan_id": plan_id}
    calls = polls = count = size = 0
    try:
        installed = _control(store, "policy")
        if not installed or installed["approved_policy_sha256"] != plan["policy_sha256"] or installed["policy"] != policy:
            raise ObservationScheduleRetentionError("PLAN_STALE_POLICY")
        # Read durable progress only under the lease: concurrent retries cannot
        # use an offset read before another admitted chunk committed.
        progress = store._conn.execute("SELECT next_candidate,payload_json FROM retention_progress WHERE plan_id=?", (plan_id,)).fetchone()
        offset = int(progress[0]) if progress else 0
        effect_hashes = json.loads(progress[1]).get("effect_hashes", {}) if progress else {}
        for applied in plan["candidates"][:offset]:
            table = applied["table"]
            check = store._conn.execute(f"SELECT json_extract(payload_json,'$.raw_payload_retention'),json_extract(payload_json,'$.retirement_archive.plan_id') FROM {table} WHERE rowid=?", (applied["row"]["source_rowid"],)).fetchone()
            if check is None or check[0] != COMPACTION_MARKER or check[1] != plan_id:
                raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
            expected_effect = effect_hashes.get(f"{table}:{applied['row']['source_rowid']}")
            if expected_effect:
                metadata_size = store._conn.execute(f"SELECT length(CAST(payload_json AS BLOB)) FROM {table} WHERE rowid=?", (applied["row"]["source_rowid"],)).fetchone()[0]
                if metadata_size > int(policy["max_bytes"]) + len(_json(plan).encode()) + 2048:
                    raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
                actual_effect = dict(store._conn.execute(f"SELECT rowid AS source_rowid,* FROM {table} WHERE rowid=?", (applied["row"]["source_rowid"],)).fetchone())
                if _hash({**actual_effect,"payload_bytes":metadata_size}) != expected_effect:
                    raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE_AFTER_EFFECT")
        for index, candidate in enumerate(plan["candidates"][offset:], start=offset):
            candidate = {**candidate, "archive_proofs": [proofs[p] if isinstance(p, str) else p for p in candidate["archive_proofs"]]}
            if count >= int(policy["max_rows"]) or size + candidate["row"]["payload_bytes"] + int(candidate.get("dependency_bytes", 0)) > int(policy["max_bytes"]) or time.monotonic() - started >= float(policy["max_wall_seconds"]):
                break
            table = candidate["table"]
            if table not in {"call_ledger", "poll_slots"}:
                raise ObservationScheduleRetentionError("PLAN_TABLE_INVALID")
            store._conn.execute("BEGIN IMMEDIATE")
            try:
                store._require_write_lease(now, within_transaction=True)
                current_policy = _control(store, "policy")
                if not current_policy or current_policy["approved_policy_sha256"] != plan["policy_sha256"] or current_policy["policy"] != policy:
                    raise ObservationScheduleRetentionError("PLAN_STALE_POLICY")
                mode = _effective_operation_mode(store, operation_mode)
                rowid = candidate["row"]["source_rowid"]
                # Recheck byte size before fetching a possibly enlarged payload.
                current_size = store._conn.execute(f"SELECT length(CAST(payload_json AS BLOB)) FROM {table} WHERE rowid=?", (rowid,)).fetchone()
                if current_size is None or current_size[0] != candidate["row"]["payload_bytes"]:
                    raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE")
                row = store._conn.execute(f"SELECT rowid AS source_rowid,* FROM {table} WHERE rowid=?", (rowid,)).fetchone()
                actual = dict(row)
                actual["payload_bytes"] = current_size[0]
                metadata = {key: actual[key] for key in candidate["row"]}
                if metadata != candidate["row"] or hashlib.sha256(actual["payload_json"].encode()).hexdigest() != candidate["payload_sha256"]:
                    raise ObservationScheduleRetentionError("PLAN_STALE_CANDIDATE")
                reason, retirements = _protect(store, actual, table, policy, now)
                if reason or [_hash(item) for item in retirements] != candidate["retirement_sha256"]:
                    raise ObservationScheduleRetentionError("PLAN_STALE_PROTECTED:" + (reason or "RETIREMENT_CHANGED"))
                for retired in retirements:
                    _check_retirement_operation_mode(store, retired, mode)
                _archive_candidate_matches(candidate)
                for retired in retirements:
                    if retired.get("automatic"):
                        store._conn.execute("INSERT OR IGNORE INTO retirement_scopes VALUES(?,?,?)", (retired["schedule_sha256"], retired["activation_id"], _json(retired)))
                for proof in candidate["archive_proofs"]:
                    for name in proof.get("pin_objects", []):
                        if store._conn.execute("SELECT 1 FROM retention_archive_pins WHERE object_name=?", (name,)).fetchone() is None:
                            raise ObservationScheduleRetentionError("COLD_CHECKPOINT_PIN_NOT_REGISTERED")
                locator = {"archive_sha256": candidate["archive_proofs"][0]["archive_sha256"], "source_rowid": rowid,
                           "plan_id": plan_id, "archive_locator": retirements[0].get("archive_locator", "COLD_ARCHIVE_OPERATOR_INDEX")}
                compacted = compact_payload(json.loads(actual["payload_json"]), compacted_at=render_utc(now), archive_locator=locator,
                    retire_entities=all(r.get("retire_entities") is True for r in retirements))
                if table == "poll_slots":
                    compacted["poll_slot_retention"] = COMPACTION_MARKER
                compacted_json = _json(compacted)
                store._conn.execute(f"UPDATE {table} SET payload_json=? WHERE rowid=?", (compacted_json, rowid))
                store._conn.execute("DELETE FROM retention_control WHERE control_key=?", (f"refusal:{table}:{rowid}",))
                effect_hashes[f"{table}:{rowid}"] = _hash({**actual,"payload_json":compacted_json,"payload_bytes":len(compacted_json.encode())})
                store._conn.execute("INSERT INTO retention_progress VALUES(?,?,?) ON CONFLICT(plan_id) DO UPDATE SET next_candidate=excluded.next_candidate,payload_json=excluded.payload_json", (plan_id, index + 1, _json({"next_cursor": plan["next_cursor"], "updated_at": render_utc(now), "effect_hashes":effect_hashes})))
                store._conn.commit()
                count += 1
                size += actual["payload_bytes"] + int(candidate.get("dependency_bytes", 0))
                calls += int(table == "call_ledger")
                polls += int(table == "poll_slots")
                offset = index + 1
            except Exception:
                store._conn.rollback()
                raise
        store._conn.execute("BEGIN IMMEDIATE")
        try:
            store._require_write_lease(now, within_transaction=True)
            validate_retention_operation_mode(store, operation_mode=operation_mode, policy=policy, plan=plan, now=now)
            for refused in plan.get("refusals", []):
                table = refused["table"]
                rowid = refused["row"]["source_rowid"]
                current = store._conn.execute(f"SELECT length(CAST(payload_json AS BLOB)) FROM {table} WHERE rowid=?", (rowid,)).fetchone()
                if current is not None and current[0] > int(policy["max_bytes"]):
                    _set_control(store, f"refusal:{table}:{rowid}", {**refused, "policy_sha256": plan["policy_sha256"]})
            for resolution in plan.get("refusal_resolutions", []):
                current = store._conn.execute(f"SELECT length(CAST(payload_json AS BLOB)) FROM {resolution['table']} WHERE rowid=?", (resolution["row"]["source_rowid"],)).fetchone()
                if current is not None and current[0] <= int(policy["max_bytes"]):
                    store._conn.execute("DELETE FROM retention_control WHERE control_key=?", (resolution["key"],))
            store._conn.commit()
        except Exception:
            store._conn.rollback()
            raise
    finally:
        store.release_lease(lease)
    blocked = store._conn.execute("SELECT count(*) FROM retention_control WHERE control_key>='refusal:' AND control_key<'refusal;'").fetchone()[0]
    return {"status": "COMPLETE" if offset == len(plan["candidates"]) and not blocked else "PROGRESS", "plan_id": plan_id,
            "applied_call_compactions": calls, "applied_poll_slot_compactions": polls,
            "next_candidate": offset, "next_cursor": plan["next_cursor"], "scanned_rows": count, "scanned_bytes": size,
            "refused_rows": int(blocked), "selection_complete": plan["selection_complete"],
            "candidates_complete": offset == len(plan["candidates"])}


def _preview_policy(days: int, *, max_rows: int, max_bytes: int, max_wall_seconds: float) -> dict[str, Any]:
    return {"schema": POLICY_SCHEMA, "revision": 1, "enabled": False, "allowed_scopes": [{"schedule_sha256": "UNAPPROVED", "activation_id": "UNAPPROVED"}],
            "allowed_classes": ["call_ledger", "poll_slots"], "min_age_days": days, "frozen_min_age_days": days,
            "max_rows": max_rows, "max_bytes": max_bytes, "max_wall_seconds": max_wall_seconds,
            "cadence_seconds": 86400, "due_guard_seconds": 120, "physical_reclaim": False, "retained_restore_points": 2}


def evaluate_retention(store: ObservationScheduleStore, *, now: datetime, raw_retention_days: int,
                       max_rows: int = 256, max_bytes: int = MAX_PLAN_BYTES,
                       max_wall_seconds: float = 1, after: Mapping[str, int] | None = None) -> dict[str, Any]:
    installed = _control(store, "policy")
    if not installed:
        return {"schema": "smial.observation-schedule-retention-status", "mode": "status",
                "status": "EXPLICIT_APPROVED_POLICY_REQUIRED", "eligible_call_compactions": 0,
                "eligible_poll_slot_compactions": 0, "eligible_call_ids": [], "eligible_poll_slot_ids": [],
                "scanned_rows": 0, "scanned_bytes": 0, "selection_complete": False,
                "maintenance": retention_status(store)}
    if (type(max_rows) is not int or type(max_bytes) is not int or max_rows < 1 or max_bytes < 1
            or not isinstance(max_wall_seconds, (int, float)) or isinstance(max_wall_seconds, bool)
            or not math.isfinite(max_wall_seconds) or max_wall_seconds <= 0):
        raise ObservationScheduleRetentionError("MAINTENANCE_BUDGET_INVALID")
    approved_policy = installed["policy"]
    policy = {**approved_policy, "max_rows": min(max_rows, int(approved_policy["max_rows"])),
              "max_bytes": min(max_bytes, int(approved_policy["max_bytes"])),
              "max_wall_seconds": min(max_wall_seconds, float(approved_policy["max_wall_seconds"]))}
    if not _control(store, "source_identity"):
        return {"schema": "smial.observation-schedule-retention-status", "mode": "status", "status": "SOURCE_IDENTITY_UNCOMMISSIONED", "eligible_call_compactions": 0}
    plan = build_retirement_plan(store, now=now, policy=policy, after=after)
    calls = [item for item in plan["candidates"] if item["table"] == "call_ledger"]
    polls = [item for item in plan["candidates"] if item["table"] == "poll_slots"]
    return {"schema": "smial.observation-schedule-retention-status", "schema_version": "2.0", "mode": "status",
            "raw_retention_days": policy["min_age_days"], "retention_cutoff_at": plan["cutoff_at"],
            "eligible_call_compactions": len(calls), "eligible_poll_slot_compactions": len(polls),
            "eligible_call_payload_bytes": sum(c["row"]["payload_bytes"] for c in calls),
            "eligible_call_ids": [c["row"]["call_occurrence_id"] for c in calls],
            "eligible_poll_slot_ids": [c["row"]["poll_slot_id"] for c in polls],
            "protected_calls": sum(plan["exclusions"].values()), "protected_sample": [], "exclusions": plan["exclusions"],
            "sqlite_file_bytes": store.path.stat().st_size,
            "sqlite_wal_bytes": Path(str(store.path) + "-wal").stat().st_size if Path(str(store.path) + "-wal").exists() else 0,
            "scanned_rows": plan["scanned_rows"], "scanned_bytes": plan["scanned_bytes"], "next_cursor": plan["next_cursor"],
            "selection_complete": plan["selection_complete"], "maintenance": retention_status(store),
            "read_only_budget": {key: policy[key] for key in ("max_rows", "max_bytes", "max_wall_seconds")},
            "expected_reclaim_reuse_class": "SQLITE_FREELIST_REUSE_WITHOUT_VACUUM", "observed_at": render_utc(now)}


def apply_retention(store: ObservationScheduleStore, *, now: datetime, raw_retention_days: int,
                    dry_run: bool = True, plan: Mapping[str, Any] | None = None,
                    approved_plan_sha256: str | None = None) -> dict[str, Any]:
    if dry_run:
        result = evaluate_retention(store, now=now, raw_retention_days=raw_retention_days)
        result.update(mode="dry-run", applied_call_compactions=0, applied_poll_slot_compactions=0)
        return result
    if plan is None or approved_plan_sha256 is None:
        raise ObservationScheduleRetentionError("EXACT_ARCHIVE_BOUND_PLAN_REQUIRED")
    result = apply_retirement_plan(store, plan=plan, approved_plan_sha256=approved_plan_sha256, now=now)
    result.update(mode="apply", idempotent=True)
    return result


def run_maintenance_step(store: ObservationScheduleStore, *, now: datetime,
                         policy: Mapping[str, Any] | None = None, pressure: Mapping[str, Any] | None = None,
                         checkpoint_active: bool = False,
                         expected_context: dict[str, Any] | None = None,
                         operation_mode: str | None = None) -> dict[str, Any]:
    expected = checkpoint_maintenance_context(store) if expected_context is None else expected_context
    if not expected:
        expected.update(checkpoint_maintenance_context(store))
    conflict = _checkpoint_context_conflict(store, expected)
    if conflict:
        return {"status": "YIELD", "reason": conflict}
    installed = _control(store, "policy")
    mode = validate_retention_operation_mode(store, operation_mode=operation_mode,
        policy=(installed or {}).get("policy"), plan=_control(store, "active_plan"), now=now)
    if not installed or not installed["policy"].get("enabled"):
        return {"status": "DISABLED", "reason": "MAINTENANCE_NOT_COMMISSIONED"}
    effective = installed["policy"]
    if policy is not None and dict(policy) != effective:
        raise ObservationScheduleRetentionError("POLICY_APPROVAL_MISMATCH")
    validate_policy(effective)
    state = _control(store, "maintenance", {})
    reason = None
    if checkpoint_active:
        reason = "CHECKPOINT_ACTIVE"
    elif pressure is None or any(pressure.get(key) is not True for key in ("safe", "cpu_safe", "ram_safe", "io_safe")):
        reason = "PRESSURE_UNKNOWN_OR_UNSAFE"
    elif store.restore_marker_unresolved():
        reason = "RESTORE_UNRESOLVED"
    elif store._conn.execute("SELECT 1 FROM due_observations WHERE state IN ('PENDING','STARTED','IN_FLIGHT','UNKNOWN','RETRY_PENDING') AND due_at<=? AND deadline_at>=? LIMIT 1", (render_utc(now + timedelta(seconds=int(effective.get("due_guard_seconds", 120)))), render_utc(now))).fetchone():
        reason = "DUE_OR_TAIL_PRIORITY"
    elif state.get("last_run_at") and (now - parse_utc(state["last_run_at"])).total_seconds() < int(effective["cadence_seconds"]):
        reason = "CADENCE_WAIT"
    if reason:
        return {"status": "YIELD", "reason": reason, **retention_status(store)}
    plan = _control(store, "active_plan")
    pending_refresh = _control(store, "checkpoint_archive_refresh_pending")
    if ((plan and plan.get("policy_sha256") != installed["approved_policy_sha256"])
            or (pending_refresh and pending_refresh.get("policy_sha256") != installed["approved_policy_sha256"])):
        # Upgrade recovery for a policy installed by a previous binary. The
        # same strict check as commissioning runs once under the native fence;
        # arbitrary candidate/integrity failures never trigger replanning.
        lease = store.acquire_lease("i2-policy-plan-reconcile", clock=now)
        if lease is None:
            return {"status": "YIELD", "reason": "WRITER_BUSY"}
        try:
            store._conn.execute("BEGIN IMMEDIATE")
            store._require_write_lease(now, within_transaction=True)
            conflict = _checkpoint_context_conflict(store, expected)
            if conflict:
                store._conn.rollback()
                return {"status": "YIELD", "reason": conflict}
            current = _control(store, "policy")
            if current != installed:
                store._conn.rollback()
                return {"status": "YIELD", "reason": "POLICY_CHANGED"}
            _supersede_stale_policy_plan(store, approved_policy_sha256=installed["approved_policy_sha256"], now=now)
            _reconcile_pending_refresh_policy(store, policy=effective,
                approved_policy_sha256=installed["approved_policy_sha256"], now=now)
            _commit_checkpoint_context(store, expected)
            plan = _control(store, "active_plan")
            state = _control(store, "maintenance", {})
        except ObservationScheduleRetentionError as exc:
            store._conn.rollback()
            store._conn.execute("BEGIN IMMEDIATE")
            store._require_write_lease(now, within_transaction=True)
            conflict = _checkpoint_context_conflict(store, expected)
            if conflict:
                store._conn.rollback()
                return {"status": "YIELD", "reason": conflict}
            _set_control(store, "maintenance", {**state, "state":"FAILED", "last_reason":str(exc),
                "last_run_at":render_utc(now), "active_plan_id":plan["plan_id"] if plan else None})
            _commit_checkpoint_context(store, expected)
            return {"status":"FAILED", "reason":str(exc), "plan_id":plan["plan_id"] if plan else None}
        except Exception:
            store._conn.rollback()
            raise
        finally:
            store.release_lease(lease)
    pending_refresh = _control(store, "checkpoint_archive_refresh_pending")
    if pending_refresh and pending_refresh.get("reconciliation_state") == "BLOCKED_POLICY":
        return {"status":"FAILED", "reason":pending_refresh["reconciliation_reason"], **retention_status(store)}
    if plan is None:
        try:
            plan = build_retirement_plan(store, now=now, policy=effective, after=state.get("next_cursor"), operation_mode=mode)
        except Exception as exc:
            if isinstance(exc, ObservationScheduleRetentionError) and str(exc) in {
                    "OPERATION_MODE_MISMATCH", "EXACT_OPERATION_MODE_REQUIRED",
                    "INDEPENDENT_COLD_OPERATE_PROOF_REQUIRED", "REGISTERED_CHECKPOINT_OPERATE_PROOF_REQUIRED"}:
                raise
            # Selection is bounded and read-only, but its refusal is an actual
            # maintenance incident too. Never leave the last-good READY signal
            # masquerading as the current attempt's outcome after restart.
            reason = str(exc) if (isinstance(exc, ObservationScheduleRetentionError)
                and re.fullmatch(r"[A-Z0-9_:]+", str(exc))) else "OPTIONAL_MAINTENANCE_FAILED"
            lease = store.acquire_lease("i2-maintenance-plan-incident", clock=now)
            if lease is None:
                return {"status": "YIELD", "reason": "WRITER_BUSY"}
            try:
                store._conn.execute("BEGIN IMMEDIATE")
                store._require_write_lease(now, within_transaction=True)
                conflict = _checkpoint_context_conflict(store, expected)
                if conflict:
                    store._conn.rollback()
                    return {"status": "YIELD", "reason": conflict}
                if _control(store, "policy") != installed:
                    store._conn.rollback()
                    return {"status": "YIELD", "reason": "POLICY_CHANGED"}
                if _control(store, "active_plan") is not None:
                    store._conn.rollback()
                    return {"status": "YIELD", "reason": "ACTIVE_PLAN_CHANGED"}
                current = _control(store, "maintenance", {})
                _set_control(store, "maintenance", {**current, "state": "FAILED",
                    "last_reason": reason, "last_run_at": render_utc(now)})
                _commit_checkpoint_context(store, expected)
            except Exception:
                store._conn.rollback()
                raise
            finally:
                store.release_lease(lease)
            return {"status": "FAILED", "reason": reason}
        lease = store.acquire_lease("i2-maintenance-plan", clock=now)
        if lease is None:
            return {"status": "YIELD", "reason": "WRITER_BUSY"}
        try:
            store._conn.execute("BEGIN IMMEDIATE")
            store._require_write_lease(now, within_transaction=True)
            conflict = _checkpoint_context_conflict(store, expected)
            if conflict:
                store._conn.rollback()
                return {"status": "YIELD", "reason": conflict}
            if _control(store, "policy") != installed:
                store._conn.rollback()
                return {"status": "YIELD", "reason": "POLICY_CHANGED"}
            if _control(store, "active_plan") is not None:
                store._conn.rollback()
                return {"status": "YIELD", "reason": "ACTIVE_PLAN_CHANGED"}
            validate_retention_operation_mode(store, operation_mode=mode, policy=effective, plan=plan, now=now)
            _set_control(store, "active_plan", plan)
            _commit_checkpoint_context(store, expected)
        except Exception:
            store._conn.rollback()
            raise
        finally:
            store.release_lease(lease)
    def current_outcome_state():
        # Apply commits row effects/progress, never the maintenance control.
        # A peer may own a newer outcome after the chunk releases its lease.
        conflict = _checkpoint_context_conflict(store, expected)
        if conflict:
            return conflict, None
        current = _control(store, "maintenance", {})
        return None, current

    try:
        result = apply_retirement_plan(store, plan=plan, approved_plan_sha256=plan["plan_id"], now=now, operation_mode=mode)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ObservationScheduleRetentionError) else "OPTIONAL_MAINTENANCE_FAILED"
        closure_deficit = reason in {"RAW_ARCHIVE_DEPENDENCY_NOT_VERIFIED", "COLD_ARCHIVE_CANDIDATE_MISMATCH", "RAW_BODY_DEPENDENCY_NOT_ARCHIVED"}
        lease = store.acquire_lease("i2-maintenance-incident", clock=now)
        if lease is None:
            return {"status": "YIELD", "reason": "WRITER_BUSY", "plan_id": plan["plan_id"]}
        try:
            store._conn.execute("BEGIN IMMEDIATE")
            store._require_write_lease(now, within_transaction=True)
            conflict, current = current_outcome_state()
            if conflict:
                store._conn.rollback()
                return {"status": "YIELD", "reason": conflict, "plan_id": plan["plan_id"]}
            _set_control(store, "maintenance", {**current, "state": "YIELD" if closure_deficit else "FAILED", "last_reason": reason,
                         "last_run_at": render_utc(now), "active_plan_id": plan["plan_id"]})
            _commit_checkpoint_context(store, expected)
        except Exception:
            store._conn.rollback()
            raise
        finally:
            store.release_lease(lease)
        return {"status": "YIELD" if closure_deficit else "FAILED", "reason": "ARCHIVE_REFRESH_REQUIRED" if closure_deficit else "OPTIONAL_MAINTENANCE_FAILED", "plan_id": plan["plan_id"]}
    if result["status"] == "YIELD":
        return result
    lease = store.acquire_lease("i2-maintenance-cursor", clock=now)
    if lease is None:
        return {**result, "status": "YIELD", "reason": "WRITER_BUSY"}
    try:
        store._conn.execute("BEGIN IMMEDIATE")
        store._require_write_lease(now, within_transaction=True)
        conflict, state = current_outcome_state()
        if conflict:
            store._conn.rollback()
            return {**result, "status": "YIELD", "reason": conflict}
        state.update(state="FAILED" if result.get("refused_rows") else "READY", last_run_at=render_utc(now),
                     last_reason="OVERSIZE_PAYLOAD_REFUSED" if result.get("refused_rows") else result["status"], active_plan_id=plan["plan_id"])
        if not result.get("refused_rows"):
            state["last_success_at"] = render_utc(now)
        if plan.get("archive_discovery"):
            state["archive_discovery"] = plan["archive_discovery"]
        if result.get("candidates_complete"):
            state["next_cursor"] = {"call_ledger": 0, "poll_slots": 0} if plan["selection_complete"] else plan["next_cursor"]
            state["active_plan_id"] = None
            store._conn.execute("DELETE FROM retention_control WHERE control_key='active_plan'")
        _set_control(store, "maintenance", state)
        _commit_checkpoint_context(store, expected)
    except Exception:
        store._conn.rollback()
        raise
    finally:
        store.release_lease(lease)
    if result.get("refused_rows"):
        result.update(status="PROGRESS", reason="OVERSIZE_PAYLOAD_REFUSED")
    return result


def maintenance_after_checkpoint(root: Path, *, now: datetime,
                                 expected_context: dict[str, Any] | None = None) -> dict[str, Any]:
    from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
    runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
    path = (root / str(runtime["ops_store_relative"])).resolve()
    if not path.is_file():
        return {"status": "DISABLED", "reason": "SOURCE_NOT_PRESENT"}
    store = ObservationScheduleStore(path, readonly=True, immutable=False)
    try:
        if not retention_status(store)["enabled"]:
            return {"status": "DISABLED", "reason": "MAINTENANCE_NOT_COMMISSIONED"}
    finally:
        store.close()
    from solana_alpha_lab.factory.remote_ops import backup_plane_lock
    # Backup-plane -> OPS is the shared global lock order. No network is held.
    with backup_plane_lock(root, timeout_seconds=0):
        stat = shutil.disk_usage(path.parent)
        pressure = {"safe": stat.free >= max(path.stat().st_size, 64 * 1024 * 1024),
                    "cpu_safe": False, "ram_safe": False, "io_safe": False}
        try:
            pressure["cpu_safe"] = os.getloadavg()[0] <= max(1, os.cpu_count() or 1)
            memory = Path("/proc/meminfo").read_text(encoding="ascii")
            available = int(re.search(r"MemAvailable:\s+(\d+)", memory).group(1)) * 1024
            pressure["ram_safe"] = available >= 256 * 1024 * 1024
            io = Path("/proc/pressure/io").read_text(encoding="ascii")
            pressure["io_safe"] = float(re.search(r"some avg10=([\d.]+)", io).group(1)) < 10
        except (OSError, AttributeError, ValueError):
            pass  # Unknown pressure yields; no ad-hoc aggressive cleanup.
        store = ObservationScheduleStore(path)
        try:
            return run_maintenance_step(store, now=now, pressure=pressure, expected_context=expected_context)
        finally:
            store.close()


# Explicit native ObservationSchedule tables. An unexpected plugin/virtual table
# is a named refusal, never an invitation to a generic migration framework.
_NATIVE_TABLES = frozenset({
    "schedule_activations", "candidate_members", "due_observations", "call_ledger",
    "scheduler_leases", "publication_batches", "runtime_events", "restore_markers",
    "registered_schedules", "schedule_aliases", "schedule_rollovers", "authority_receipts",
    "accounting_counters", "lifetime_counters", "poll_slots", "publication_jobs",
    "episode_admissions", "episode_rounds", "episode_outbox", "episode_publications",
    "episode_publication_cohorts", "account_budget_scopes", "account_budget_policies",
    "account_budget_members", "managed_profiles", "managed_control", "managed_children",
    "managed_incidents", "retention_control", "retirement_scopes", "retention_progress", "retention_archive_pins",
})


def _tables(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = [(str(row[0]), str(row[1])) for row in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if any(name not in _NATIVE_TABLES or "VIRTUAL TABLE" in sql.upper() or "WITHOUT ROWID" in sql.upper() for name, sql in rows):
        raise ObservationScheduleRetentionError("RECLAIM_UNSUPPORTED_NATIVE_SCHEMA")
    return rows


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def native_identity_fingerprint(conn: sqlite3.Connection, *, deadline: float | None = None,
                                recovery_causal: bool = False) -> dict[str, Any]:
    """All rowids, values, sequence highwaters and schema; stable across fences.

    episode_admissions.rowid is a durable trading_coordinator discovery cursor;
    call_ledger.rowid is also read by native operability projection.
    """
    # The independently restored SQLite receives a restore marker. Registering
    # that proof then changes only the archive cache, pin and scan bookkeeping.
    # Exclude those exact mechanisms from the recovery oracle, while preserving
    # policy, disallow-resume records, all business rows and sequence highwaters.
    excluded_tables = {"scheduler_leases"}
    if recovery_causal:
        excluded_tables |= {"restore_markers", "retention_progress", "retention_archive_pins"}
    mechanical_controls = ("checkpoint_archive", "checkpoint_archive_cache_release",
        "checkpoint_archive_refresh_pending", "archive_refreshed_at", "active_plan", "maintenance")
    digest = hashlib.sha256()
    counts = {}
    schemas = []
    for name, sql in _tables(conn):
        if deadline is not None and time.monotonic() > deadline:
            raise ObservationScheduleRetentionError("RECLAIM_WINDOW_EXCEEDED")
        if name in excluded_tables:
            continue
        schemas.append([name, sql])
        digest.update(name.encode())
        count = 0
        columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote(name)})")]
        # Hash large TEXT/BLOB cells incrementally via SQLite's blob reader.
        expressions = ",".join(f"typeof({_quote(c)}),length(CAST({_quote(c)} AS BLOB))" for c in columns)
        where = ""
        parameters = ()
        if recovery_causal and name == "retention_control":
            where = " WHERE control_key NOT IN (" + ",".join("?" for _ in mechanical_controls) + ") AND control_key NOT LIKE 'refusal:%'"
            parameters = mechanical_controls
        for descriptor in conn.execute(f"SELECT rowid,{expressions} FROM {_quote(name)}{where} ORDER BY rowid", parameters):
            if deadline is not None and time.monotonic() > deadline:
                raise ObservationScheduleRetentionError("RECLAIM_WINDOW_EXCEEDED")
            rowid = int(descriptor[0])
            digest.update(_json(rowid).encode())
            for i, column in enumerate(columns):
                kind, length = descriptor[1 + 2 * i:3 + 2 * i]
                digest.update(_json([column, kind, length]).encode())
                if kind in {"text", "blob"} and length and length > 65536:
                    with conn.blobopen(name, column, rowid, readonly=True) as blob:
                        while block := blob.read(65536):
                            if deadline is not None and time.monotonic() > deadline:
                                raise ObservationScheduleRetentionError("RECLAIM_WINDOW_EXCEEDED")
                            digest.update(block)
                else:
                    value = conn.execute(f"SELECT {_quote(column)} FROM {_quote(name)} WHERE rowid=?", (rowid,)).fetchone()[0]
                    digest.update(value if isinstance(value, bytes) else _json(value).encode())
            count += 1
        counts[name] = count
    sequences = [list(row) for row in conn.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name")
                 if not recovery_causal or row[0] not in excluded_tables]
    return {"content_sha256": digest.hexdigest(), "row_counts": counts,
            "schema_sha256": _hash(schemas) if recovery_causal else _schema_identity(conn), "sequences": sequences}


def build_reclaim_plan(store: ObservationScheduleStore, *, data_root: Path,
                        max_wall_seconds: float = 60, backup_root: Path | None = None,
                        operation_mode: str = "ISOLATED_REHEARSAL") -> dict[str, Any]:
    if max_wall_seconds <= 0 or max_wall_seconds > 90:
        raise ObservationScheduleRetentionError("RECLAIM_WINDOW_INVALID")
    nested = store.path.resolve().is_relative_to(data_root.resolve())
    sibling = store.path.parent.resolve() == data_root.parent.resolve()
    if not nested and not sibling:
        raise ObservationScheduleRetentionError("RECLAIM_ROOT_BINDING_MISMATCH")
    backup_root = backup_root or store.path.parent
    if operation_mode not in {"ISOLATED_REHEARSAL", "OPERATE"} or not store.path.is_relative_to(backup_root):
        raise ObservationScheduleRetentionError("RECLAIM_FACTORY_ROOT_OR_MODE_INVALID")
    store._conn.execute("BEGIN")
    started = time.monotonic()
    store._conn.set_progress_handler(lambda: int(time.monotonic() - started > max_wall_seconds), 1000)
    try:
        source = _source_identity(store)
        fingerprint = native_identity_fingerprint(store._conn, deadline=started + max_wall_seconds)
        recovery_fingerprint = native_identity_fingerprint(store._conn,
            deadline=started + max_wall_seconds, recovery_causal=True)
    except sqlite3.OperationalError as exc:
        raise ObservationScheduleRetentionError("RECLAIM_WINDOW_EXCEEDED") from exc
    finally:
        store._conn.set_progress_handler(None, 0)
        store._conn.rollback()
    plan = {"schema": "smial.observation-reclaim-plan.v1", "source": source,
            "data_root_binding": _root_binding(data_root),
            "layout": "DB_IN_DATA_ROOT" if nested else "DB_SIBLING_TO_DATA_ROOT",
            "backup_root_binding": _root_binding(backup_root), "operation_mode": operation_mode,
            "database_relative": store.path.relative_to(data_root).as_posix() if nested else store.path.name,
            "fingerprint": fingerprint, "recovery_fingerprint": recovery_fingerprint, "max_wall_seconds": max_wall_seconds,
            "required_free_bytes": store.path.stat().st_size * 2 + 16 * 1024 * 1024,
            "technique": "NATIVE_ROWID_EXPLICIT_REBUILD", "rollback_boundary": "BEFORE_RESUME_OR_NEW_WRITES"}
    plan["plan_id"] = _hash(plan)
    return plan


def _reclaim_paths(path: Path) -> tuple[Path, Path, Path]:
    prefix = path.parent / ("." + path.name + ".i2-reclaim")
    return Path(str(prefix) + "-new.sqlite"), Path(str(prefix) + "-rollback.sqlite"), Path(str(prefix) + ".intent.json")


def _write_intent(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(_json(dict(payload)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    # Windows does not expose POSIX directory fsync. File fsync + replace still
    # applies there; on POSIX the directory entry must survive a power loss too.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _reclaim_replace(source: Path, target: Path) -> None:
    os.replace(source, target)
    _fsync_directory(target.parent)


def _reclaim_unlink(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_symlink() or not path.is_file():
        raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
    size = path.stat().st_size
    path.unlink()
    _fsync_directory(path.parent)
    return size


def apply_physical_reclaim(store: ObservationScheduleStore, *, plan: Mapping[str, Any],
                           approved_plan_sha256: str, data_root: Path, writers_quiesced: bool,
                           independent_recovery_proof: Mapping[str, Any], now: datetime,
                           checkpoint_active: bool = False, failpoint: str | None = None,
                           backup_root: Path | None = None,
                           operation_mode: str | None = None) -> dict[str, Any]:
    from solana_alpha_lab.factory.remote_ops import backup_plane_lock
    _validate_operation_mode(plan.get("operation_mode"))
    _validate_operation_mode(operation_mode)
    if operation_mode is not None and plan.get("operation_mode") != operation_mode:
        raise ObservationScheduleRetentionError("OPERATION_MODE_MISMATCH")
    backup_root = backup_root or store.path.parent
    if _root_binding(backup_root) != plan.get("backup_root_binding"):
        raise ObservationScheduleRetentionError("RECLAIM_BACKUP_ROOT_BINDING_MISMATCH")
    if plan.get("operation_mode") == "OPERATE" and independent_recovery_proof.get("proof_class") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
        raise ObservationScheduleRetentionError("RECLAIM_INDEPENDENT_OPERATE_PROOF_REQUIRED")
    if plan.get("operation_mode") == "OPERATE" and _control(store, "checkpoint_archive") != dict(independent_recovery_proof):
        raise ObservationScheduleRetentionError("RECLAIM_REGISTERED_OPERATE_PROOF_REQUIRED")
    with backup_plane_lock(backup_root, timeout_seconds=0):
        return _apply_physical_reclaim(store, plan=plan, approved_plan_sha256=approved_plan_sha256,
            data_root=data_root, writers_quiesced=writers_quiesced,
            independent_recovery_proof=independent_recovery_proof, now=now,
            checkpoint_active=checkpoint_active, failpoint=failpoint)


def _apply_physical_reclaim(store: ObservationScheduleStore, *, plan: Mapping[str, Any],
                           approved_plan_sha256: str, data_root: Path, writers_quiesced: bool,
                           independent_recovery_proof: Mapping[str, Any], now: datetime,
                           checkpoint_active: bool = False, failpoint: str | None = None) -> dict[str, Any]:
    """Explicit same-filesystem cutover. Caller must quiesce all actual writers.

    Leaves SWITCHED intent and retained final-current rollback until the caller
    performs native readback and explicitly marks resume. Never stops intake or
    edits desired RUN/profile/grant. Existing lease fences cooperating writers.
    """
    document = dict(plan)
    plan_id = document.pop("plan_id", None)
    if plan_id != _hash(document) or plan_id != approved_plan_sha256:
        raise ObservationScheduleRetentionError("RECLAIM_APPROVAL_MISMATCH")
    if not writers_quiesced or checkpoint_active or store.restore_marker_unresolved():
        raise ObservationScheduleRetentionError("RECLAIM_NOT_QUIESCENT")
    if _source_identity(store) != plan["source"] or _root_binding(data_root) != plan["data_root_binding"]:
        raise ObservationScheduleRetentionError("RECLAIM_SOURCE_ROOT_OR_SCHEMA_STALE")
    verify_cold_archive(independent_recovery_proof, deep=False)
    if independent_recovery_proof["source_id"] != plan["source"]["source_id"]:
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_SOURCE_MISMATCH")
    path = store.path
    compact, rollback, intent_path = _reclaim_paths(path)
    # A small terminal receipt may be replaced by the next exact operation;
    # unfinished stages always remain owned by recovery.
    previous = json.loads(intent_path.read_text(encoding="utf-8")) if intent_path.exists() else None
    if compact.exists() or rollback.exists() or (previous and previous.get("state") not in {"FINALIZED", "ROLLBACK_FINALIZED"}):
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_REQUIRED")
    if shutil.disk_usage(path.parent).free < int(plan["required_free_bytes"]):
        raise ObservationScheduleRetentionError("RECLAIM_CAPACITY_REFUSED")
    started = time.monotonic()
    lease = store.acquire_lease("i2-physical-reclaim", clock=now)
    if lease is None:
        raise ObservationScheduleRetentionError("WRITER_BUSY")
    attached = False
    closed = False
    intent = {"schema": "smial.observation-reclaim-intent.v1", "state": "ALLOCATING", "plan_id": plan_id,
              "operation_mode": plan["operation_mode"],
              "fingerprint": plan["fingerprint"], "source": plan["source"],
              "data_root_binding": plan["data_root_binding"], "lease_token": lease,
              "before_bytes": path.stat().st_size}
    try:
        # Reboot guards must exist before ATTACH can allocate any new DB bytes.
        store._reclaim_guard_token = lease
        _write_intent(intent_path, intent)
        store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        store._conn.execute("ATTACH DATABASE ? AS reclaimed", (str(compact),))
        attached = True
        store._conn.execute("PRAGMA reclaimed.journal_mode=DELETE")
        store._conn.execute("BEGIN EXCLUSIVE")
        store._require_write_lease(now, within_transaction=True)
        store._conn.set_progress_handler(lambda: int(time.monotonic() - started > float(plan["max_wall_seconds"])), 1000)
        fingerprint = native_identity_fingerprint(store._conn, deadline=started + float(plan["max_wall_seconds"]))
        if fingerprint != plan["fingerprint"]:
            raise ObservationScheduleRetentionError("RECLAIM_FINAL_CURRENT_STATE_STALE")
        recovery_fingerprint = native_identity_fingerprint(store._conn,
            deadline=started + float(plan["max_wall_seconds"]), recovery_causal=True)
        if recovery_fingerprint != plan.get("recovery_fingerprint"):
            raise ObservationScheduleRetentionError("RECLAIM_FINAL_CURRENT_STATE_STALE")
        with _sqlite_connection(Path(independent_recovery_proof["archive_path"]).as_uri() + "?mode=ro&immutable=1", uri=True) as recovered:
            recovered.set_progress_handler(lambda: int(time.monotonic() - started > float(plan["max_wall_seconds"])), 1000)
            if native_identity_fingerprint(recovered, deadline=started + float(plan["max_wall_seconds"]),
                    recovery_causal=True) != recovery_fingerprint:
                raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_NOT_FINAL_CURRENT")
        for name, sql in _tables(store._conn):
            # Qualify only the CREATE TABLE name; the schema body stays exact.
            qualified = re.sub(r"^(CREATE TABLE\s+)(?:IF NOT EXISTS\s+)?", r"\1reclaimed.", sql, count=1, flags=re.IGNORECASE)
            store._conn.execute(qualified)
            columns = [str(row[1]) for row in store._conn.execute(f"PRAGMA main.table_info({_quote(name)})")]
            names = "rowid," + ",".join(_quote(c) for c in columns)
            store._conn.execute(f"INSERT INTO reclaimed.{_quote(name)}({names}) SELECT {names} FROM main.{_quote(name)}")
        store._conn.execute("DELETE FROM reclaimed.sqlite_sequence")
        store._conn.execute("INSERT INTO reclaimed.sqlite_sequence SELECT * FROM main.sqlite_sequence")
        for name, sql in store._conn.execute("SELECT name,sql FROM main.sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name").fetchall():
            # All supported native explicit indices use CREATE INDEX ... ON ... .
            qualified = re.sub(r"^(CREATE (?:UNIQUE )?INDEX\s+)(?:IF NOT EXISTS\s+)?", r"\1reclaimed.", sql, count=1, flags=re.IGNORECASE)
            store._conn.execute(qualified)
        # Native owner currently defines no views/triggers; refuse new seams.
        if store._conn.execute("SELECT 1 FROM main.sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
            raise ObservationScheduleRetentionError("RECLAIM_UNSUPPORTED_NATIVE_SCHEMA")
        store._conn.commit()
        store._conn.set_progress_handler(None, 0)
        store._conn.execute("DETACH DATABASE reclaimed")
        attached = False
        with _sqlite_connection(compact) as verify:
            if verify.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or native_identity_fingerprint(verify, deadline=started + float(plan["max_wall_seconds"])) != fingerprint:
                raise ObservationScheduleRetentionError("RECLAIM_IDENTITY_MISMATCH")
        with compact.open("r+b") as durable_compact:
            os.fsync(durable_compact.fileno())
        intent.update(state="PREPARED", after_bytes=compact.stat().st_size, compact_binding=_root_binding(compact))
        _write_intent(intent_path, intent)
        if failpoint == "PREPARED":
            raise ObservationScheduleRetentionError("RECLAIM_INJECTED_CRASH")
        store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        store.close()
        closed = True
        if any(Path(str(path) + suffix).exists() and Path(str(path) + suffix).stat().st_size for suffix in ("-wal",)):
            raise ObservationScheduleRetentionError("RECLAIM_WRITER_STILL_OPEN")
        _reclaim_replace(path, rollback)
        intent["state"] = "ORIGINAL_MOVED"
        _write_intent(intent_path, intent)
        if failpoint == "ORIGINAL_MOVED":
            raise ObservationScheduleRetentionError("RECLAIM_INJECTED_CRASH")
        _reclaim_replace(compact, path)
        intent["state"] = "SWITCHED"
        _write_intent(intent_path, intent)
        if failpoint == "SWITCHED":
            raise ObservationScheduleRetentionError("RECLAIM_INJECTED_CRASH")
        return {"status": "SWITCHED_AWAITING_NATIVE_READBACK", "plan_id": plan_id,
                "before_bytes": intent["before_bytes"], "after_bytes": intent["after_bytes"],
                "identity_sha256": fingerprint["content_sha256"], "rollback_allowed": True}
    except Exception:
        if not closed:
            store._conn.set_progress_handler(None, 0)
            store._conn.rollback()
            if attached:
                store._conn.execute("DETACH DATABASE reclaimed")
            store.release_lease(lease)
        # A handled allocation failure never renamed the source. A process death
        # cannot execute this cleanup: its durable ALLOCATING intent owns retry.
        if intent["state"] == "ALLOCATING" and not rollback.exists():
            for suffix in ("", "-journal", "-wal", "-shm"):
                _reclaim_unlink(Path(str(compact) + suffix))
            _reclaim_unlink(intent_path.with_suffix(intent_path.suffix + ".tmp"))
            if previous is None:
                _reclaim_unlink(intent_path)
            else:
                _write_intent(intent_path, previous)
        store._reclaim_guard_token = None
        raise


def _initial_reclaim_intent_from_plan(path: Path, data_root: Path, plan: Mapping[str, Any],
                                      approved_plan_sha256: str) -> dict[str, Any]:
    """Recover a torn first temp write only from the exact approved native plan."""
    document = dict(plan)
    plan_id = document.pop("plan_id", None)
    if (plan_id != approved_plan_sha256 or plan_id != _hash(document)
            or _root_binding(data_root) != document.get("data_root_binding")
            or path.is_symlink() or not path.is_file()):
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
    source = document.get("source", {})
    if (_root_binding(path) != source.get("db_binding")
            or _root_binding(path.parent) != source.get("root_binding")):
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
    with _sqlite_connection(path.as_uri() + "?mode=ro", uri=True) as connection:
        if native_identity_fingerprint(connection) != document.get("fingerprint"):
            raise ObservationScheduleRetentionError("RECLAIM_NEW_WRITES_FORWARD_REPAIR_REQUIRED")
        row = connection.execute("SELECT payload_json FROM retention_control WHERE control_key='source_identity'").fetchone()
        if row is None or json.loads(row[0]).get("source_id") != source.get("source_id"):
            raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
        lease = connection.execute("SELECT owner,lease_token FROM scheduler_leases WHERE lease_id=?", (GLOBAL_LEASE_ID,)).fetchone()
        if lease is not None and lease[0] != "i2-physical-reclaim":
            raise ObservationScheduleRetentionError("WRITER_BUSY")
    return {"schema":"smial.observation-reclaim-intent.v1", "state":"ALLOCATING", "plan_id":plan_id,
            "operation_mode":document["operation_mode"],
            "fingerprint":document["fingerprint"], "source":source,
            "data_root_binding":document["data_root_binding"], "lease_token":lease[1] if lease else "",
            "before_bytes":path.stat().st_size, "initial_recovery_from_approved_plan":True}


def recover_physical_reclaim(path: Path, *, data_root: Path, action: str,
                             approved_plan_sha256: str,
                             plan: Mapping[str, Any] | None = None,
                             operation_mode: str | None = None) -> dict[str, Any]:
    _validate_operation_mode(operation_mode)
    compact, rollback, intent_path = _reclaim_paths(path)
    temporary = intent_path.with_suffix(intent_path.suffix + ".tmp")
    if intent_path.is_symlink() or temporary.is_symlink():
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
    reconstructed = False
    try:
        intent = json.loads(intent_path.read_text(encoding="utf-8")) if intent_path.exists() else None
        unpublished = (intent is None or (intent.get("plan_id") != approved_plan_sha256
                       and intent.get("state") in {"FINALIZED", "ROLLBACK_FINALIZED"}))
        if unpublished:
            if temporary.is_symlink() or not temporary.is_file():
                raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
            previous = intent
            try:
                intent = json.loads(temporary.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError):
                if plan is None:
                    raise ObservationScheduleRetentionError("RECLAIM_INITIAL_PLAN_REQUIRED")
                intent = _initial_reclaim_intent_from_plan(path, data_root, plan, approved_plan_sha256)
                reconstructed = True
            # Only the first durable ALLOCATING publication may precede the
            # final intent. No allocation/rename is authorized before it.
            if (intent.get("state") != "ALLOCATING"
                    or any(Path(str(item) + suffix).exists() for item in (compact, rollback)
                           for suffix in ("", "-wal", "-shm", "-journal"))
                    or (previous is not None and (previous.get("schema") != "smial.observation-reclaim-intent.v1"
                        or previous.get("final_db_binding") != _root_binding(path)))):
                raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
    except ObservationScheduleRetentionError:
        raise
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH") from exc
    try:
        identity_matches = (intent.get("schema") == "smial.observation-reclaim-intent.v1"
            and intent["plan_id"] == approved_plan_sha256
            and _root_binding(data_root) == intent["data_root_binding"]
            and _root_binding(path.parent) == intent["source"]["root_binding"])
    except (KeyError, TypeError, AttributeError):
        identity_matches = False
    if not identity_matches:
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
    recorded_mode = intent.get("operation_mode")
    _validate_operation_mode(recorded_mode)
    if plan is not None:
        document = dict(plan)
        plan_id = document.pop("plan_id", None)
        if plan_id != approved_plan_sha256 or plan_id != _hash(document):
            raise ObservationScheduleRetentionError("RECLAIM_APPROVAL_MISMATCH")
        plan_mode = document.get("operation_mode")
        _validate_operation_mode(plan_mode)
        if plan_mode is None:
            raise ObservationScheduleRetentionError("EXACT_OPERATION_MODE_REQUIRED")
        if recorded_mode is not None and recorded_mode != plan_mode:
            raise ObservationScheduleRetentionError("OPERATION_MODE_MISMATCH")
        recorded_mode = plan_mode
    if operation_mode is not None:
        if recorded_mode is None:
            raise ObservationScheduleRetentionError("RECLAIM_OPERATION_MODE_PLAN_REQUIRED")
        if recorded_mode != operation_mode:
            raise ObservationScheduleRetentionError("OPERATION_MODE_MISMATCH")
    if action not in {"rollback", "resume"}:
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_ACTION_INVALID")
    state = intent["state"]
    if state in {"RESUMED", "FINALIZED"} and action == "rollback":
        raise ObservationScheduleRetentionError("RECLAIM_ROLLBACK_AFTER_RESUME_DENIED")
    if state in {"ROLLING_BACK", "ROLLED_BACK", "ROLLBACK_FINALIZED"} and action == "resume":
        raise ObservationScheduleRetentionError("RECLAIM_RESUME_AFTER_ROLLBACK_DENIED")
    if state in {"FINALIZED", "ROLLBACK_FINALIZED"}:
        if temporary.exists():
            raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_REQUIRED")
        if not path.is_file() or _root_binding(path) != intent.get("final_db_binding"):
            raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
        if any(item.exists() for item in (compact, rollback)):
            raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
        return {"status": "RESUMED" if state == "FINALIZED" else "ROLLED_BACK",
                "plan_id": intent["plan_id"], "idempotent": True,
                "rollback_allowed": False, "byte_disposition": intent["byte_disposition"]}
    if state not in {"ALLOCATING", "PREPARED", "ORIGINAL_MOVED", "SWITCHED", "RESUMED", "ROLLING_BACK", "ROLLED_BACK"}:
        raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_STATE_INVALID")

    def verify(candidate: Path, expected_binding: Mapping[str, int] | None = None) -> None:
        if candidate.is_symlink() or not candidate.is_file():
            raise ObservationScheduleRetentionError("RECLAIM_FINAL_CURRENT_ROLLBACK_MISSING")
        if expected_binding is not None and _root_binding(candidate) != expected_binding:
            raise ObservationScheduleRetentionError("RECLAIM_RECOVERY_IDENTITY_MISMATCH")
        # Recovery is the only narrow writer bypass. Validation itself is ro,
        # WAL-aware, and cannot create the missing native source.
        with _sqlite_connection(candidate.as_uri() + "?mode=ro", uri=True) as current:
            if native_identity_fingerprint(current) != intent["fingerprint"]:
                raise ObservationScheduleRetentionError("RECLAIM_NEW_WRITES_FORWARD_REPAIR_REQUIRED")

    # Infer each rename from actual inode identities too: the process can die
    # before the corresponding durable state update.
    if path.exists():
        verify(path)
    if rollback.exists():
        verify(rollback, intent["source"]["db_binding"])
    elif not path.exists():
        raise ObservationScheduleRetentionError("RECLAIM_FINAL_CURRENT_ROLLBACK_MISSING")
    if unpublished:
        verify(path, intent["source"]["db_binding"])
        if action != "rollback":
            raise ObservationScheduleRetentionError("RECLAIM_SWITCH_INCOMPLETE_USE_ROLLBACK")
        # Publish the fully validated, fsynced initial bytes before any recovery
        # transition overwrites the temp file. Repeated kills now have a durable
        # final intent, and the ordinary exact rollback owns all cleanup.
        if reconstructed:
            _write_intent(intent_path, intent)
        else:
            _reclaim_replace(temporary, intent_path)
    if action == "resume":
        if state != "RESUMED":
            if compact.exists():
                if state == "ALLOCATING":
                    raise ObservationScheduleRetentionError("RECLAIM_SWITCH_INCOMPLETE_USE_ROLLBACK")
                verify(compact, intent.get("compact_binding"))
                if path.exists():
                    if rollback.exists():
                        raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
                    verify(path, intent["source"]["db_binding"])
                    _reclaim_replace(path, rollback)
                    intent["state"] = "ORIGINAL_MOVED"
                    _write_intent(intent_path, intent)
                _reclaim_replace(compact, path)
                intent["state"] = "SWITCHED"
                _write_intent(intent_path, intent)
            elif not (path.exists() and rollback.exists()):
                raise ObservationScheduleRetentionError("RECLAIM_SWITCH_INCOMPLETE_USE_ROLLBACK")
            verify(path, intent.get("compact_binding"))
            intent["state"] = "RESUMED"
            _write_intent(intent_path, intent)
    else:
        if state != "ROLLED_BACK":
            intent["state"] = "ROLLING_BACK"
            _write_intent(intent_path, intent)
            if rollback.exists():
                if path.exists():
                    if compact.exists():
                        raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
                    _reclaim_replace(path, compact)
                _reclaim_replace(rollback, path)
            verify(path, intent["source"]["db_binding"])
            intent["state"] = "ROLLED_BACK"
            _write_intent(intent_path, intent)
    # Durable acceptance forbids rollback before releasing the fence or any
    # original bytes. Ordinary native writes stay blocked until final cleanup.
    with _sqlite_connection(path.as_uri() + "?mode=rw", uri=True) as connection:
        connection.execute("DELETE FROM scheduler_leases WHERE lease_token=?", (intent["lease_token"],))
    if "cleanup_files" not in intent:
        disposition = {"rollback_bytes_released": 0, "staging_bytes_released": 0}
        cleanup_files = []
        for candidate, key in ((rollback, "rollback_bytes_released"), (compact, "staging_bytes_released")):
            for suffix in ("", "-journal", "-wal", "-shm"):
                item = Path(str(candidate) + suffix)
                if item.exists():
                    cleanup_files.append({"name": item.name, "binding": _archive_binding(item)})
                    disposition[key] += item.stat().st_size
        intent.update(cleanup_files=cleanup_files, byte_disposition=disposition)
        _write_intent(intent_path, intent)
    disposition = intent["byte_disposition"]
    allowed_cleanup = {Path(str(candidate) + suffix).name for candidate in (compact, rollback)
                       for suffix in ("", "-journal", "-wal", "-shm")}
    for entry in intent["cleanup_files"]:
        if entry["name"] not in allowed_cleanup:
            raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
        item = path.parent / entry["name"]
        if item.exists() and _archive_binding(item) != entry["binding"]:
            raise ObservationScheduleRetentionError("RECLAIM_STAGING_BINDING_INVALID")
        _reclaim_unlink(item)
    _reclaim_unlink(intent_path.with_suffix(intent_path.suffix + ".tmp"))
    intent.update(state="FINALIZED" if action == "resume" else "ROLLBACK_FINALIZED",
                  final_db_binding=_root_binding(path), byte_disposition=disposition)
    _write_intent(intent_path, intent)
    return {"status": "RESUMED" if action == "resume" else "ROLLED_BACK", "plan_id": intent["plan_id"],
            "rollback_allowed": False, "byte_disposition": disposition}
