"""Recurring closed-UTC-day archive → Drive → exact SHA. No scientific delete."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from solana_alpha_lab.factory.hot90_activation import (
    Hot90ActivationError,
    load_hot90_activation,
    require_drive_writes_enabled,
)
from solana_alpha_lab.factory.hot90_archive import (
    Hot90ArchiveError,
    list_closed_day_relative_paths,
    package_closed_day_archive,
)
from solana_alpha_lab.factory.hot90_remote_verify import (
    REMOTE_CONTENT_SHA256_VERIFIED,
    probe_remote_sha256,
    verify_remote_content_sha256,
)
from solana_alpha_lab.factory.observation_publication_jobs import iter_open_job_paths
from solana_alpha_lab.factory.observation_schedule import render_utc
from solana_alpha_lab.factory.offhost_backup import (
    OffhostBackupError,
    build_rclone_argv,
    default_rclone_runner,
    load_offhost_config,
)
from solana_alpha_lab.factory.remote_ops import RemoteOpsError, load_config_v1_1

RECEIPT_KIND = "FACTORY_HOT90_CLOSED_DAY_ARCHIVE_RECEIPT"
RECEIPTS_RELATIVE = "local/factory_v1/hot90_archive_receipts"
STAGING_RELATIVE = "local/factory_v1/hot90_archives"
RDP_RELATIVE = "local/factory_v1/observation_rdp"
DEFAULT_MAX_DAYS_PER_RUN = 3
DEFAULT_MAX_RUNTIME_SECONDS = 900
ARCHIVE_ON_CALENDAR = "*-*-* 01:15:00 UTC"
ARCHIVE_CATCH_UP_ON_CALENDAR = (
    "*-*-* 01:15:00 UTC",
    "*-*-* 07:15:00 UTC",
    "*-*-* 13:15:00 UTC",
    "*-*-* 19:15:00 UTC",
)
# Operational latest cache retention is bounded: only the latest CLOSED day may
# keep a rebuildable cache once its day is archived and Drive-verified. Older
# verified days are pruned, so day-over-day retention cannot grow unbounded.
CACHE_RETENTION_CLOSED_DAYS = 1
RcloneRunner = Callable[[list[str]], Any]


class ClosedDayLoopError(ValueError):
    """Typed closed-day durability loop failure."""


def prune_stale_operational_caches(root: Path, *, today: str) -> dict[str, object]:
    """Bound day-over-day operational latest cache retention.

    The rebuildable cache is only meaningful for appending to the newest
    closed day with verified history. Once a day is Drive-archived
    (verified receipt exists) and a newer verified day exists, older cache
    files are removed so retention cannot grow unbounded. The open/current
    day always keeps its working cache. Returns a deterministic report.
    """

    from solana_alpha_lab.factory.members_snapshot_delta import (
        _OPERATIONAL_LATEST_DB,
        _OPERATIONAL_LATEST_META,
        is_operational_cache_name,
    )

    rdp = root / RDP_RELATIVE
    members_root = rdp / "datasets" / "members_snapshot_plus_delta"
    if members_root.is_dir() is False:
        return {"pruned": [], "kept_days": []}
    verified_days: list[str] = []
    for day_dir in sorted(members_root.iterdir()):
        day = normalize_utc_day(day_dir.name)
        if day is None or day_dir.is_dir() is False:
            continue
        if receipt_verified(read_receipt(root, day)):
            verified_days.append(day)
    keep = set(verified_days[-CACHE_RETENTION_CLOSED_DAYS:])
    pruned: list[str] = []
    for day_dir in sorted(members_root.iterdir()):
        day = normalize_utc_day(day_dir.name)
        if day is None or day_dir.is_dir() is False:
            continue
        if day >= today:
            # Open/current day may always keep its working cache, but a crash
            # leftover temporary file is never a working cache; prune it now.
            leftovers = [
                p for p in day_dir.iterdir() if p.is_file() and is_operational_cache_name(p.name)
            ]
            stale = [
                p
                for p in leftovers
                if p.name not in (_OPERATIONAL_LATEST_DB, _OPERATIONAL_LATEST_META)
            ]
            if stale:
                for p in stale:
                    try:
                        p.unlink(missing_ok=True)
                    except OSError:
                        continue
                pruned.append(day)
            continue
        if day in keep:
            continue
        removed = False
        for p in list(day_dir.iterdir()):
            if p.is_file() is False or is_operational_cache_name(p.name) is False:
                continue
            try:
                p.unlink(missing_ok=True)
                removed = True
            except OSError:
                continue
        if removed:
            pruned.append(day)
    return {"pruned": sorted(set(pruned)), "kept_days": sorted(keep)}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def normalize_utc_day(value: object) -> str | None:
    text = str(value or "").strip()
    compact = text.replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return compact
    return None


def current_utc_day(now: datetime) -> str:
    clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return clock.astimezone(UTC).strftime("%Y%m%d")


def receipt_path(root: Path, utc_day: str) -> Path:
    return root / RECEIPTS_RELATIVE / f"{utc_day}.json"


def read_receipt(root: Path, utc_day: str) -> dict[str, Any] | None:
    path = receipt_path(root, utc_day)
    if path.is_file() is False:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def receipt_verified(payload: Mapping[str, Any] | None) -> bool:
    if payload is None:
        return False
    return (
        payload.get("kind") == RECEIPT_KIND
        and payload.get("terminal") == REMOTE_CONTENT_SHA256_VERIFIED
        and len(str(payload.get("local_archive_sha256") or "")) == 64
        and payload.get("local_archive_sha256") == payload.get("remote_content_sha256")
    )


def open_publication_days(rdp: Path) -> set[str]:
    days: set[str] = set()
    for path in iter_open_job_paths(rdp):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(job, dict):
            continue
        day = normalize_utc_day(job.get("utc_day"))
        if day:
            days.add(day)
    return days


def discover_member_days(rdp: Path) -> list[str]:
    root = rdp / "datasets" / "members_snapshot_plus_delta"
    if root.is_dir() is False:
        return []
    days = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "unit.json").is_file():
            day = normalize_utc_day(child.name)
            if day:
                days.append(day)
    return days


def _split_unverified_days(root: Path, *, now: datetime) -> tuple[list[str], list[str]]:
    rdp = root / RDP_RELATIVE
    today = current_utc_day(now)
    blocked = open_publication_days(rdp)
    processable: list[str] = []
    stuck: list[str] = []
    for day in discover_member_days(rdp):
        if day >= today:
            continue
        if day in blocked:
            continue
        receipt = read_receipt(root, day)
        if receipt_verified(receipt):
            continue
        if str((receipt or {}).get("terminal") or "") == "HASH_MISMATCH":
            stuck.append(day)
            continue
        try:
            list_closed_day_relative_paths(rdp, day)
        except (Hot90ArchiveError, json.JSONDecodeError, OSError):
            continue
        processable.append(day)
    return processable, stuck


def eligible_unverified_days(root: Path, *, now: datetime) -> list[str]:
    processable, _stuck = _split_unverified_days(root, now=now)
    return processable


def archive_backlog(root: Path, *, now: datetime) -> dict[str, Any]:
    processable, stuck = _split_unverified_days(root, now=now)
    visible = processable + stuck
    oldest_age = None
    if visible:
        oldest_day = min(visible)
        oldest = datetime.strptime(oldest_day, "%Y%m%d").replace(tzinfo=UTC)
        clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
        oldest_age = int((clock.astimezone(UTC) - oldest).total_seconds())
    verified = []
    receipts_dir = root / RECEIPTS_RELATIVE
    if receipts_dir.is_dir():
        for path in sorted(receipts_dir.glob("*.json")):
            payload = read_receipt(root, path.stem)
            if receipt_verified(payload):
                verified.append(path.stem)
    return {
        "eligible_unverified_days": processable,
        "stuck_hash_mismatch_days": stuck,
        "backlog_days": len(visible),
        "oldest_backlog_age_seconds": oldest_age,
        "latest_verified_day": verified[-1] if verified else None,
        "verified_days": verified,
    }


def _write_failure_receipt(
    root: Path, utc_day: str, code: str, extra: Mapping[str, Any]
) -> dict[str, Any]:
    existing = read_receipt(root, utc_day) or {}
    payload = {
        "kind": RECEIPT_KIND,
        "utc_day": utc_day,
        "terminal": code,
        "last_failure": {"code": code, **dict(extra)},
        "verified_at": existing.get("verified_at"),
        "local_archive_sha256": extra.get("local_archive_sha256")
        or existing.get("local_archive_sha256"),
        "remote_content_sha256": extra.get("remote_content_sha256")
        or existing.get("remote_content_sha256"),
        "inventory_sha256": extra.get("inventory_sha256") or existing.get("inventory_sha256"),
        "remote_object": extra.get("remote_object") or existing.get("remote_object"),
    }
    dumped = json.dumps(payload)
    if any(token in dumped for token in ("access_token", "refresh_token", "BEGIN PRIVATE")):
        raise ClosedDayLoopError("RECEIPT_SECRET_LEAK")
    _atomic_write_json(receipt_path(root, utc_day), payload)
    return payload


def _prune_verified_staging(root: Path, keep_sha256: str) -> list[str]:
    staging = root / STAGING_RELATIVE
    if staging.is_dir() is False:
        return []
    removed: list[str] = []
    for path in sorted(staging.glob("ARCHIVE_*.zip")):
        digest = path.stem.removeprefix("ARCHIVE_")
        if len(digest) != 64 or digest == keep_sha256:
            continue
        owned = False
        for receipt_file in (root / RECEIPTS_RELATIVE).glob("*.json"):
            payload = read_receipt(root, receipt_file.stem)
            if receipt_verified(payload) and payload.get("local_archive_sha256") == digest:
                owned = True
                break
        if owned is False:
            continue
        path.unlink()
        removed.append(path.name)
    return removed


def process_one_day(
    root: Path,
    utc_day: str,
    *,
    now: datetime,
    rclone_runner: RcloneRunner | None = None,
    allow_drive: bool = False,
) -> dict[str, Any]:
    activation = load_hot90_activation(root)
    if activation.get("activation_stage") not in {"DURABILITY_CUTOVER", "RETENTION_ACTIVE"}:
        return {"utc_day": utc_day, "terminal": "STAGE_NOT_CUTOVER", "uploaded": False}
    try:
        require_drive_writes_enabled(activation)
    except Hot90ActivationError:
        return {"utc_day": utc_day, "terminal": "HOT90_DRIVE_WRITES_DISABLED", "uploaded": False}

    if utc_day >= current_utc_day(now):
        return {"utc_day": utc_day, "terminal": "OPEN_UTC_DAY", "uploaded": False}
    if utc_day in open_publication_days(root / RDP_RELATIVE):
        return {"utc_day": utc_day, "terminal": "OPEN_PUBLICATION_JOB", "uploaded": False}

    existing = read_receipt(root, utc_day)
    if str((existing or {}).get("terminal") or "") == "HASH_MISMATCH":
        return {
            "utc_day": utc_day,
            "terminal": "HASH_MISMATCH",
            "uploaded": False,
            "overwrite_forbidden": True,
        }
    rdp = root / RDP_RELATIVE
    relatives = list_closed_day_relative_paths(rdp, utc_day)
    packed = package_closed_day_archive(
        rdp,
        utc_day=utc_day,
        relative_paths=relatives,
        dest_dir=root / STAGING_RELATIVE,
    )
    local_sha = str(packed["sha256"])
    if receipt_verified(existing) and existing.get("local_archive_sha256") == local_sha:
        return {
            "utc_day": utc_day,
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
            "uploaded": False,
            "idempotent": True,
            "local_archive_sha256": local_sha,
        }

    offhost = load_offhost_config(root)
    if offhost is None:
        payload = _write_failure_receipt(
            root, utc_day, "DRIVE_ROUTE_UNCONFIGURED", {"local_archive_sha256": local_sha}
        )
        return {"utc_day": utc_day, "terminal": payload["terminal"], "uploaded": False}

    runner = rclone_runner or default_rclone_runner
    archive_path = Path(packed["path"])
    remote_object = offhost.remote_object(archive_path.name)
    native = probe_remote_sha256(config=offhost, remote_object=remote_object, runner=runner)
    if native == local_sha:
        receipt = {
            "kind": RECEIPT_KIND,
            "utc_day": utc_day,
            "inventory_sha256": packed["inventory_sha256"],
            "local_archive_sha256": local_sha,
            "local_archive_filename": archive_path.name,
            "remote_object": remote_object,
            "remote_content_sha256": native,
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
            "verified_at": render_utc(now),
            "last_failure": None,
            "verify_method": "NATIVE_HASHSUM_PREEXISTING",
        }
        _atomic_write_json(receipt_path(root, utc_day), receipt)
        return {
            "utc_day": utc_day,
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
            "uploaded": False,
            "idempotent": True,
            "local_archive_sha256": local_sha,
        }
    if native is not None:
        payload = _write_failure_receipt(
            root,
            utc_day,
            "HASH_MISMATCH",
            {
                "local_archive_sha256": local_sha,
                "inventory_sha256": packed["inventory_sha256"],
                "remote_object": remote_object,
                "remote_content_sha256": native,
            },
        )
        return {
            "utc_day": utc_day,
            "terminal": payload["terminal"],
            "uploaded": False,
            "overwrite_forbidden": True,
        }
    copied = runner(build_rclone_argv(offhost, "copyto", str(archive_path), remote_object))
    uploaded = getattr(copied, "returncode", 1) == 0
    if uploaded is False:
        payload = _write_failure_receipt(
            root,
            utc_day,
            "DRIVE_WRITE_FAILED",
            {
                "local_archive_sha256": local_sha,
                "inventory_sha256": packed["inventory_sha256"],
                "remote_object": remote_object,
            },
        )
        return {"utc_day": utc_day, "terminal": payload["terminal"], "uploaded": False}

    try:
        verified = verify_remote_content_sha256(
            config=offhost,
            remote_object=remote_object,
            local_sha256=local_sha,
            runner=runner,
            root=root,
            allow_drive=allow_drive,
        )
    except OffhostBackupError as exc:
        code = str(exc)
        terminal = "HASH_MISMATCH" if code == "REMOTE_CONTENT_SHA256_MISMATCH" else "REMOTE_VERIFY_FAILED"
        payload = _write_failure_receipt(
            root,
            utc_day,
            terminal,
            {
                "local_archive_sha256": local_sha,
                "inventory_sha256": packed["inventory_sha256"],
                "remote_object": remote_object,
                "error": code[:80],
            },
        )
        return {"utc_day": utc_day, "terminal": payload["terminal"], "uploaded": True}

    if verified.get("sha256") != local_sha:
        payload = _write_failure_receipt(
            root,
            utc_day,
            "HASH_MISMATCH",
            {"local_archive_sha256": local_sha, "remote_object": remote_object},
        )
        return {"utc_day": utc_day, "terminal": payload["terminal"], "uploaded": True}

    receipt = {
        "kind": RECEIPT_KIND,
        "utc_day": utc_day,
        "inventory_sha256": packed["inventory_sha256"],
        "local_archive_sha256": local_sha,
        "local_archive_filename": archive_path.name,
        "remote_object": remote_object,
        "remote_content_sha256": verified["sha256"],
        "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
        "verified_at": render_utc(now),
        "last_failure": None,
        "verify_method": verified.get("method"),
    }
    _atomic_write_json(receipt_path(root, utc_day), receipt)
    pruned = _prune_verified_staging(root, local_sha)
    return {
        "utc_day": utc_day,
        "terminal": REMOTE_CONTENT_SHA256_VERIFIED,
        "uploaded": True,
        "local_archive_sha256": local_sha,
        "pruned_staging": pruned,
    }


# Mature episode cohorts get one self-contained, content-addressed closure object
# (frozen capture packet + every manifest source byte at its transfer_path), so a
# consumer can seal/import later from offhost bytes only, without this host.
COHORT_RECEIPT_KIND = "FACTORY_EPISODE_COHORT_CLOSURE_RECEIPT"
COHORT_RECEIPTS_RELATIVE = "local/factory_v1/hot90_cohort_closure_receipts"
COHORT_STAGING_RELATIVE = "local/factory_v1/hot90_cohort_closures"
OPS_RELATIVE = "local/factory_v1/observation_schedule_state.sqlite"
# Earlier cohorts were captured and protected by the workstation route.
COHORT_CLOSURE_FROM_COHORT_ID = "REL-20261013T000000Z-20261014T000000Z"
DEFAULT_MAX_COHORTS_PER_RUN = 2
MAX_COHORT_CLOSURE_BYTES = 2 * 1024**3


def cohort_receipt_path(root: Path, cohort_id: str) -> Path:
    if not cohort_id.startswith("REL-") or "/" in cohort_id or ".." in cohort_id:
        raise ClosedDayLoopError("COHORT_ID_INVALID")
    return root / COHORT_RECEIPTS_RELATIVE / f"{cohort_id}.json"


def _cohort_receipts(root: Path) -> list[tuple[str, dict[str, Any] | None]]:
    directory = root / COHORT_RECEIPTS_RELATIVE
    if not directory.is_dir():
        return []
    out: list[tuple[str, dict[str, Any] | None]] = []
    for path in sorted(directory.glob("REL-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if not isinstance(payload, dict) or payload.get("cohort_id") != path.stem:
            payload = None
        out.append((path.stem, payload))
    return out


def _closure_verified(payload: Mapping[str, Any] | None) -> bool:
    import re

    digest = (payload or {}).get("archive_sha256")
    return bool(
        payload
        and payload.get("terminal") == REMOTE_CONTENT_SHA256_VERIFIED
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest)
        and payload.get("remote_content_sha256") == digest
    )


def protected_cohort_ids(root: Path) -> set[str]:
    return {cohort for cohort, payload in _cohort_receipts(root) if _closure_verified(payload)}


RUN_STATE_NAME = "RUN-STATE.json"
# Drive/route outages stop the network part of a run; a cohort-local failure does not.
NETWORK_FAILURES = frozenset({"DRIVE_ROUTE_UNCONFIGURED", "DRIVE_WRITE_FAILED", "REMOTE_VERIFY_FAILED"})
_RUN_LEVEL_FAILURES = frozenset({"COHORT_SELECTION_FAILED", "COHORT_CLOSURE_ERROR"})
_IDLE = frozenset({"NO_MATURE_UNPROTECTED_COHORT", "STAGE_NOT_CUTOVER", "HOT90_DRIVE_WRITES_DISABLED", "NO_EPISODE_OPS_STORE"})


def _age_seconds(now: datetime, stamp: object, path: Path | None) -> int:
    """Age of a failure; an unreadable record ages from its file time, never UNKNOWN."""

    from solana_alpha_lab.factory.observation_schedule import parse_utc

    try:
        return max(0, int((now - parse_utc(str(stamp))).total_seconds()))
    except (TypeError, ValueError):
        pass
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) if path is not None else now
    except OSError:
        mtime = now
    return max(0, int((now - mtime).total_seconds()))


def _run_state_path(root: Path) -> Path:
    return root / COHORT_RECEIPTS_RELATIVE / RUN_STATE_NAME


def _write_run_state(root: Path, terminal: str, code: str, *, now: datetime) -> None:
    path = _run_state_path(root)
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    first = previous.get("failed_at") if isinstance(previous, dict) else None
    _atomic_write_json(path, {"kind": COHORT_RECEIPT_KIND, "scope": "RUN", "terminal": terminal,
                              "code": code[:80], "failed_at": first or render_utc(now), "last_at": render_utc(now)})


def _clear_run_state(root: Path) -> None:
    _run_state_path(root).unlink(missing_ok=True)


def cohort_closure_failures(root: Path, *, now: datetime) -> list[dict[str, Any]]:
    """Every unresolved closure failure (cohort, invalid receipt or run level) with an age."""

    directory = root / COHORT_RECEIPTS_RELATIVE
    out = []
    for cohort, payload in _cohort_receipts(root):
        if _closure_verified(payload):
            continue
        out.append({"cohort_id": cohort, "terminal": str((payload or {}).get("terminal") or "RECEIPT_INVALID"),
                    "age_seconds": _age_seconds(now, (payload or {}).get("failed_at"), directory / f"{cohort}.json")})
    run = _run_state_path(root)
    if run.exists():
        try:
            state = json.loads(run.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = None
        state = state if isinstance(state, dict) else {}
        out.append({"cohort_id": "RUN", "terminal": str(state.get("terminal") or "RUN_STATE_INVALID"),
                    "age_seconds": _age_seconds(now, state.get("failed_at"), run)})
    return out


def cohort_closure_packet_fields(root: Path, *, now: datetime) -> dict[str, Any]:
    """Operability packet fields; an unreadable ledger is a visible failure, not health."""

    try:
        failures = cohort_closure_failures(root, now=now)
    except Exception:
        failures = [{"cohort_id": "RUN", "terminal": "RECEIPTS_UNREADABLE", "age_seconds": 86401}]
    ages = [item["age_seconds"] for item in failures if isinstance(item.get("age_seconds"), int)]
    return {
        "cohort_closure_failures": failures,
        "cohort_closure_oldest_failure_age_seconds": max(ages) if ages else None,
        "cohort_closure_hash_mismatch": any(item.get("terminal") == "HASH_MISMATCH" for item in failures),
    }


def verify_shared_call_claims(
    source_root: Path, entries: list[Mapping[str, Any]], cohort_id: str
) -> dict[str, Any]:
    """Each response-body call this cohort claims: one request/response, its raw body
    inside the closure hashing to the response, and the mints claimed by every cohort
    equal to the ids in that response. Closure bytes only; no neighbour is imported.
    Nomination witness rows (per-mint excerpts, not response bodies) are counted apart."""

    import hashlib

    import duckdb

    from solana_alpha_lab.factory.opportunity_episode_release import _contained

    located = {str(e["path"]): str(e.get("transfer_path") or e["path"]) for e in entries}
    parquets = [_contained(source_root, located[str(e["path"])]).as_posix()
                for e in entries if e.get("source_class") == "observation_parquet"]
    result = {"calls": 0, "shared_calls": 0, "complete": 0, "witness_calls": 0,
              "incomplete_refs": [], "unverifiable_refs": []}
    if not parquets:
        return result
    files = "[" + ",".join("'" + p.replace("'", "''") + "'" for p in parquets) + "]"
    connection = duckdb.connect()
    base = f"FROM read_parquet({files}, union_by_name=true) WHERE call_occurrence_id IS NOT NULL"
    result["witness_calls"] = int(connection.execute(
        f"SELECT COUNT(DISTINCT call_occurrence_id) {base} AND raw_body_rel LIKE '%/witness/%' AND cohort_id = ?",
        [cohort_id]).fetchone()[0])
    rows = connection.execute(
        "SELECT call_occurrence_id, list(DISTINCT mint), list(DISTINCT request_sha256), "
        "list(DISTINCT response_sha256), list(DISTINCT raw_body_rel), COUNT(DISTINCT cohort_id) "
        f"{base} AND COALESCE(raw_body_rel, '') NOT LIKE '%/witness/%' AND call_occurrence_id IN "
        f"(SELECT call_occurrence_id {base} AND cohort_id = ?) GROUP BY 1 ORDER BY 1",
        [cohort_id],
    ).fetchall()
    for ref, mints, requests, responses, raws, cohorts in rows:
        result["calls"] += 1
        result["shared_calls"] += int(int(cohorts) > 1)
        bodies = [r for r in raws if r]
        if len(requests) != 1 or len(responses) != 1 or len(bodies) != 1 or bodies[0] not in located:
            result["incomplete_refs"].append(ref)
            continue
        raw = _contained(source_root, located[bodies[0]]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != responses[0]:
            result["incomplete_refs"].append(ref)
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = None
        if not isinstance(payload, list) or not all(isinstance(item, Mapping) for item in payload):
            result["unverifiable_refs"].append(ref)  # not a batch list: nothing to compare
            continue
        ids = {str(item.get("id") or item.get("mint") or "") for item in payload}
        if ids == {str(m) for m in mints if m}:
            result["complete"] += 1
        else:
            result["incomplete_refs"].append(ref)
    return result


def package_cohort_closure(rdp: Path, packet: Mapping[str, Any], dest_dir: Path) -> dict[str, Any]:
    """Deterministic ZIP: packet.json + source/<transfer_path>; every byte hash-checked."""

    import hashlib
    import zipfile

    from solana_alpha_lab.factory.live_cohort_vanilla_path import validate_episode_transfer_manifest
    from solana_alpha_lab.factory.opportunity_episode_release import _contained

    manifest = packet["transfer_manifest"]
    validate_episode_transfer_manifest(manifest, packet["closure_receipt"])
    entries = sorted(manifest["entries"], key=lambda e: str(e.get("transfer_path") or e["path"]))
    total = sum(int(e["bytes"]) for e in entries)
    if total > MAX_COHORT_CLOSURE_BYTES:
        raise ClosedDayLoopError("COHORT_CLOSURE_TOO_LARGE")
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f".building-{os.getpid()}.zip"
    stamp = (2026, 1, 1, 0, 0, 0)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for entry in entries:
                relative = str(entry.get("transfer_path") or entry["path"])
                source = _contained(rdp, relative)
                if source.is_symlink() or not source.is_file():
                    raise ClosedDayLoopError("COHORT_SOURCE_MISSING")
                if source.stat().st_size != int(entry["bytes"]):
                    raise ClosedDayLoopError("COHORT_SOURCE_SIZE_CHANGED")
                digest = hashlib.sha256()
                with source.open("rb") as stream, archive.open(zipfile.ZipInfo("source/" + relative, stamp), "w", force_zip64=True) as out:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(chunk)
                        out.write(chunk)
                if digest.hexdigest() != entry["sha256"]:
                    raise ClosedDayLoopError("COHORT_SOURCE_HASH_MISMATCH")
            archive.writestr(zipfile.ZipInfo("packet.json", stamp),
                             json.dumps(packet, sort_keys=True, default=str).encode("utf-8"))
        sha = hashlib.sha256()
        with tmp.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                sha.update(chunk)
        final = dest_dir / f"COHORT_CLOSURE_{sha.hexdigest()}.zip"
        os.replace(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)
    return {"path": str(final), "sha256": sha.hexdigest(), "files": len(entries), "source_bytes": total}


def _cohort_receipts_by_id(root: Path) -> dict[str, dict[str, Any] | None]:
    return dict(_cohort_receipts(root))


def _cohort_failure(
    root: Path, cohort_id: str, code: str, extra: Mapping[str, Any] | None = None, *, now: datetime,
    resume: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    previous = dict(_cohort_receipts_by_id(root).get(cohort_id) or {})
    payload = {"kind": COHORT_RECEIPT_KIND, "cohort_id": cohort_id, "terminal": code,
               # first failure time is kept so a persistent failure ages into an incident
               "failed_at": previous.get("failed_at") or render_utc(now),
               "last_failure": {"code": code, "at": render_utc(now), **dict(extra or {})}}
    if resume is not None:
        payload["resume"] = dict(resume)  # same frozen packet and archive identity on retry
    _atomic_write_json(cohort_receipt_path(root, cohort_id), payload)
    return {"cohort_id": cohort_id, "terminal": code, "uploaded": False}


def _resume_archives(root: Path) -> set[str]:
    out = set()
    for _cohort, payload in _cohort_receipts(root):
        resume = (payload or {}).get("resume")
        if not _closure_verified(payload) and isinstance(resume, Mapping):
            out.add(str(resume.get("archive_filename") or ""))
    return out


def _sweep_cohort_staging(root: Path, *, now: datetime) -> list[str]:
    """Remove owned leftovers (oneshot unit: no concurrent writer); keep resumable uploads."""

    staging = root / COHORT_STAGING_RELATIVE
    removed: list[str] = []
    if not staging.is_dir():
        return removed
    keep = _resume_archives(root)
    for stale in staging.glob("*.zip"):
        if stale.is_symlink() or stale.name in keep:
            continue
        if not (stale.name.startswith(".building-") or stale.name.startswith("COHORT_CLOSURE_")):
            continue
        stale.unlink(missing_ok=True)
        removed.append(stale.name)
    return removed


def _resume_from(root: Path, cohort_id: str) -> dict[str, Any] | None:
    import hashlib

    resume = (_cohort_receipts_by_id(root).get(cohort_id) or {}).get("resume")
    if not isinstance(resume, Mapping):
        return None
    path = root / COHORT_STAGING_RELATIVE / str(resume.get("archive_filename") or "")
    if path.is_symlink() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != resume.get("archive_sha256"):
        return None
    return {**dict(resume), "path": str(path)}


def process_next_cohort_closure(
    root: Path,
    *,
    now: datetime,
    rclone_runner: RcloneRunner | None = None,
    allow_drive: bool = False,
    observation_rdp: Path | None = None,
    ops_store: Path | None = None,
    skip_cohorts: set[str] | None = None,
) -> dict[str, Any]:
    """Protect the oldest mature unprotected episode cohort not in ``skip_cohorts``."""

    from solana_alpha_lab.factory.opportunity_episode_release import (
        capture_freeze_export_episodes,
        select_next_mature_episode_cohort,
    )

    activation = load_hot90_activation(root)
    if activation.get("activation_stage") not in {"DURABILITY_CUTOVER", "RETENTION_ACTIVE"}:
        return {"terminal": "STAGE_NOT_CUTOVER", "uploaded": False}
    try:
        require_drive_writes_enabled(activation)
    except Hot90ActivationError:
        return {"terminal": "HOT90_DRIVE_WRITES_DISABLED", "uploaded": False}
    rdp = Path(observation_rdp or root / RDP_RELATIVE)
    ops = Path(ops_store or root / OPS_RELATIVE)
    _sweep_cohort_staging(root, now=now)
    if not ops.is_file():
        return {"terminal": "NO_EPISODE_OPS_STORE", "uploaded": False}
    skip = protected_cohort_ids(root) | set(skip_cohorts or ())
    try:
        for _ in range(256):
            chosen = select_next_mature_episode_cohort(ops_store=ops, observation_rdp=rdp, imported=skip, as_of=now)
            if not chosen or chosen.get("terminal") != "MATURE":
                return {"terminal": "NO_MATURE_UNPROTECTED_COHORT", "uploaded": False}
            if str(chosen["cohort_id"]) >= COHORT_CLOSURE_FROM_COHORT_ID:
                break
            skip.add(str(chosen["cohort_id"]))
        else:
            return {"terminal": "NO_MATURE_UNPROTECTED_COHORT", "uploaded": False}
    except ValueError as exc:  # typed release errors are ValueError subclasses
        _write_run_state(root, "COHORT_SELECTION_FAILED", str(exc), now=now)
        return {"terminal": "COHORT_SELECTION_FAILED", "code": str(exc)[:80], "uploaded": False}
    cohort_id = str(chosen["cohort_id"])
    staging = root / COHORT_STAGING_RELATIVE
    resume = _resume_from(root, cohort_id)
    keep_archive = False
    archive_path: Path | None = None
    try:
        if resume is None:
            try:
                packet = capture_freeze_export_episodes(observation_rdp=rdp, ops_store=ops, imported_cohort_ids=skip, as_of=now)
                if str(packet["cohort_id"]) != cohort_id:
                    return _cohort_failure(root, cohort_id, "COHORT_SELECTION_DRIFT", now=now)
                manifest = packet["transfer_manifest"]
                proof = verify_shared_call_claims(rdp, list(manifest["entries"]), cohort_id)
                packed = package_cohort_closure(rdp, packet, staging)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                return _cohort_failure(root, cohort_id, "COHORT_CLOSURE_BUILD_FAILED", now=now, extra={"error": str(exc)[:80]})
            archive_path = Path(packed["path"])
            resume = {
                "archive_filename": archive_path.name, "archive_sha256": packed["sha256"],
                "files": packed["files"], "source_bytes": packed["source_bytes"],
                "schedule_sha256": str(chosen["schedule_sha256"]), "activation_id": str(chosen["activation_id"]),
                "closure_receipt_sha256": packet["closure_receipt"].get("closure_receipt_sha256"),
                "transfer_manifest_sha256": manifest.get("manifest_sha256"),
                "shared_call_proof": proof,
            }
        else:
            archive_path = Path(resume.pop("path"))
        sha = str(resume["archive_sha256"])
        offhost = load_offhost_config(root)
        if offhost is None:
            keep_archive = True
            return _cohort_failure(root, cohort_id, "DRIVE_ROUTE_UNCONFIGURED", now=now, resume=resume)
        runner = rclone_runner or default_rclone_runner
        remote_object = offhost.remote_object(archive_path.name)
        common = {"archive_sha256": sha, "remote_object": remote_object}
        native = probe_remote_sha256(config=offhost, remote_object=remote_object, runner=runner)
        if native is not None and native != sha:
            return _cohort_failure(root, cohort_id, "HASH_MISMATCH", now=now, extra={**common, "remote_content_sha256": native})
        uploaded = False
        if native is None:
            copied = runner(build_rclone_argv(offhost, "copyto", str(archive_path), remote_object))
            if getattr(copied, "returncode", 1) != 0:
                keep_archive = True
                return _cohort_failure(root, cohort_id, "DRIVE_WRITE_FAILED", common, now=now, resume=resume)
            uploaded = True
            try:
                verified = verify_remote_content_sha256(config=offhost, remote_object=remote_object,
                                                        local_sha256=sha, runner=runner,
                                                        root=root, allow_drive=allow_drive)
            except OffhostBackupError as exc:
                keep_archive = True
                return _cohort_failure(root, cohort_id, "REMOTE_VERIFY_FAILED", now=now,
                                       extra={**common, "error": str(exc)[:80]}, resume=resume)
            native = str(verified.get("sha256") or "")
            if native != sha:
                return _cohort_failure(root, cohort_id, "HASH_MISMATCH", now=now, extra={**common, "remote_content_sha256": native})
        receipt = {
            "kind": COHORT_RECEIPT_KIND, "cohort_id": cohort_id, "collection": "OPPORTUNITY_EPISODES",
            **{key: resume.get(key) for key in ("schedule_sha256", "activation_id", "closure_receipt_sha256",
                                                "transfer_manifest_sha256", "files", "source_bytes", "shared_call_proof")},
            "archive_filename": archive_path.name, "archive_sha256": sha,
            "remote_object": remote_object, "remote_content_sha256": native,
            "terminal": REMOTE_CONTENT_SHA256_VERIFIED, "verified_at": render_utc(now), "last_failure": None,
            "consumer": "unzip; unpack-next-live-cohort --collection OPPORTUNITY_EPISODES "
                        "--capture-packet packet.json --source-rdp source --mirror-rdp <mirror> --data-root <data-root>",
        }
        _atomic_write_json(cohort_receipt_path(root, cohort_id), receipt)
        return {"cohort_id": cohort_id, "terminal": REMOTE_CONTENT_SHA256_VERIFIED, "uploaded": uploaded,
                "archive_sha256": sha, "files": resume.get("files"), "shared_call_proof": resume.get("shared_call_proof")}
    finally:
        # Verified objects live offhost; a resumable upload keeps exactly its archive.
        if archive_path is not None and not keep_archive:
            archive_path.unlink(missing_ok=True)


def run_cohort_closures(
    root: Path,
    *,
    now: datetime,
    rclone_runner: RcloneRunner | None,
    allow_drive: bool,
    within_budget: Callable[[], bool],
    max_cohorts: int = DEFAULT_MAX_COHORTS_PER_RUN,
) -> list[dict[str, Any]]:
    """Bounded queue: a cohort-local failure moves on, a Drive outage stops the network part."""

    attempted: set[str] = set()
    outcomes: list[dict[str, Any]] = []
    run_failed = False
    for _ in range(max_cohorts):
        if not within_budget():
            break
        try:
            outcome = process_next_cohort_closure(root, now=now, rclone_runner=rclone_runner,
                                                  allow_drive=allow_drive, skip_cohorts=attempted)
        except Exception as exc:  # the day archive summary and cache prune must still complete
            outcome = {"terminal": "COHORT_CLOSURE_ERROR", "code": type(exc).__name__, "uploaded": False}
            _write_run_state(root, "COHORT_CLOSURE_ERROR", type(exc).__name__, now=now)
        outcomes.append(outcome)
        terminal = str(outcome["terminal"])
        if outcome.get("cohort_id"):
            attempted.add(str(outcome["cohort_id"]))
        if terminal in _RUN_LEVEL_FAILURES:
            run_failed = True
            break
        if terminal in NETWORK_FAILURES or terminal in _IDLE:
            break
    if outcomes and not run_failed and str(outcomes[-1]["terminal"]) not in {"STAGE_NOT_CUTOVER", "HOT90_DRIVE_WRITES_DISABLED"}:
        _clear_run_state(root)  # selection worked this run
    return outcomes


def run_closed_day_durability(
    root: Path,
    *,
    now: datetime | None = None,
    max_days: int | None = None,
    rclone_runner: RcloneRunner | None = None,
    allow_drive: bool = False,
    deadline: datetime | None = None,
    monotonic: Callable[[], float] | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    loaded_max = DEFAULT_MAX_DAYS_PER_RUN if max_days is None else int(max_days)
    if loaded_max < 1:
        raise ClosedDayLoopError("MAX_DAYS_INVALID")
    tick = monotonic or time.monotonic
    started = tick()
    max_runtime = DEFAULT_MAX_RUNTIME_SECONDS
    try:
        archive_cfg = dict(load_config_v1_1(root).get("archive") or {})
        loaded_runtime = int(archive_cfg.get("max_runtime_seconds") or max_runtime)
        if loaded_runtime >= 1:
            max_runtime = loaded_runtime
        if max_days is None:
            loaded_max = int(archive_cfg.get("max_days_per_run") or loaded_max)
    except (RemoteOpsError, TypeError, ValueError):
        pass
    wall = datetime.now(UTC)
    backlog = archive_backlog(root, now=clock)
    processed = []
    out_of_time = False
    for day in backlog["eligible_unverified_days"][:loaded_max]:
        if (deadline is not None and wall > deadline) or tick() - started > max_runtime:
            out_of_time = True
            break
        processed.append(
            process_one_day(
                root,
                day,
                now=clock,
                rclone_runner=rclone_runner,
                allow_drive=allow_drive,
            )
        )
        wall = datetime.now(UTC)
    cohorts = [] if out_of_time else run_cohort_closures(
        root, now=clock, rclone_runner=rclone_runner, allow_drive=allow_drive,
        within_budget=lambda: not ((deadline is not None and datetime.now(UTC) > deadline)
                                   or tick() - started > max_runtime),
    )
    remaining = archive_backlog(root, now=clock)
    cache_prune = prune_stale_operational_caches(root, today=current_utc_day(clock))
    return {
        "processed": processed,
        "backlog_before": backlog["backlog_days"],
        "backlog_after": remaining["backlog_days"],
        "oldest_unverified_day": (remaining["eligible_unverified_days"] or [None])[0],
        "latest_verified_day": remaining["latest_verified_day"],
        "on_calendar_utc": ARCHIVE_ON_CALENDAR,
        "max_days_per_run": loaded_max,
        "operational_cache_prune": cache_prune,
        "cohort_closures": cohorts,
    }
