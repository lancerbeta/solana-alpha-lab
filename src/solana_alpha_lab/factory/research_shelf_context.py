"""Derived pinned shelf snapshot and entry glance. No Git/native/provider calls.

The envelope carries a bounded observation of a data head, not scientific
authority or an operational registry. It is rebuildable from its Git commit.
"""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from . import research_shelf as wire

REPOSITORY = "lancerbeta/solana-alpha-lab"
MAX_EXPORT_BYTES = 33_554_432
MAX_OBSERVATION_AGE_SECONDS = 86_400
REFRESH_RECIPE = "scripts/research_shelf.py refresh --cache <separate-bare-cache> --output <snapshot.json>"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return wire.sha256(wire.canonical(value))


def export_snapshot(snapshot: Mapping[str, Any], *, repository: str = REPOSITORY,
                    event_states: Mapping[str, Any] | None = None) -> bytes:
    """Preserve a successful refresh witness across an explicit file handoff."""
    files = {path: raw.decode("utf-8") for path, raw in snapshot.get("files", {}).items()}
    head = snapshot.get("commit")
    checked = snapshot.get("source_checked_at")
    freshness = snapshot.get("source_freshness", "UNVERIFIED_PINNED")
    if checked is not None:
        wire.clock(checked)
    witness = dict(repository=repository, branch="research-log", commit=head,
                   checked_at=checked, status=freshness,
                   files_sha256=_digest(files))
    witness["observation_sha256"] = _digest(witness)
    body = dict(schema="smial.research-shelf-snapshot", schema_version="1.0",
        repository=repository, branch="research-log", prefix=wire.PREFIX,
        commit=head, status=snapshot["status"], complete=snapshot["complete"],
        reason=snapshot.get("reason"), files=files, observation=witness,
        event_states=copy.deepcopy(dict(event_states or {})))
    body["snapshot_sha256"] = _digest(body)
    raw = wire.canonical(body) + b"\n"
    wire.require(len(raw) <= MAX_EXPORT_BYTES, "SNAPSHOT_EXPORT_LIMIT")
    return raw


def read_snapshot(raw: bytes, *, now: str, max_age_seconds: int = MAX_OBSERVATION_AGE_SECONDS) -> dict[str, Any]:
    wire.require(len(raw) <= MAX_EXPORT_BYTES, "SNAPSHOT_EXPORT_LIMIT")
    body = json.loads(raw)
    wire.require(isinstance(body, dict) and body.get("schema") == "smial.research-shelf-snapshot"
                 and body.get("schema_version") == "1.0", "SNAPSHOT_SCHEMA_INVALID")
    wire.require(body.get("snapshot_sha256") == _digest({k: v for k, v in body.items() if k != "snapshot_sha256"}),
                 "SNAPSHOT_HASH_MISMATCH")
    wire.require(body["repository"] == REPOSITORY and body["branch"] == "research-log" and body["prefix"] == wire.PREFIX,
                 "SNAPSHOT_NAMESPACE_MISMATCH")
    head = body.get("commit")
    wire.require(head is None or re.fullmatch(r"[0-9a-f]{40}", head), "EXACT_COMMIT_REQUIRED")
    wire.require(isinstance(body.get("complete"), bool) and isinstance(body.get("files"), dict), "SNAPSHOT_SCHEMA_INVALID")
    files = {path: text.encode("utf-8") for path, text in body["files"].items()}
    witness = body["observation"]
    wire.require(witness["observation_sha256"] == _digest({k: v for k, v in witness.items() if k != "observation_sha256"}),
                 "OBSERVATION_HASH_MISMATCH")
    wire.require((witness["repository"], witness["branch"], witness["commit"], witness["files_sha256"]) ==
                 (body["repository"], body["branch"], head, _digest(body["files"])), "OBSERVATION_BINDING_MISMATCH")
    status = body["status"]
    wire.require(status in {"READY", "NOT_INITIALIZED", "UNAVAILABLE", "STALE_AS_OF", "INCOMPLETE"}, "SNAPSHOT_STATUS_INVALID")
    checked = witness["checked_at"]
    freshness = witness["status"]
    reason = body.get("reason")
    age = None
    if checked is not None:
        age = (wire.clock(now) - wire.clock(checked)).total_seconds()
    if freshness == "REMOTE_VERIFIED":
        if head is None or checked is None or age is None or age < 0:
            freshness, reason = "UNVERIFIED_PINNED", "OBSERVATION_UNPROVEN"
        elif age > max_age_seconds:
            status, freshness, reason = "STALE_AS_OF", "STALE_AS_OF", "HEAD_OBSERVATION_TOO_OLD"
    else:
        freshness = "STALE_AS_OF" if status == "STALE_AS_OF" else "UNVERIFIED_PINNED"
    snapshot = wire.fold(files, complete=body["complete"])
    if not snapshot["complete"] and status == "READY":
        status = "INCOMPLETE"
    if head is None:
        wire.require(not files and not body["complete"] and status in {"NOT_INITIALIZED", "UNAVAILABLE"},
                     "MISSING_HEAD_IS_NOT_EMPTY_SHELF")
    states = body.get("event_states", {})
    wire.require(isinstance(states, dict), "EVENT_STATES_INVALID")
    states = copy.deepcopy(states)
    for item, result in states.items():
        wire.require(isinstance(result, dict) and result.get("status") in {"MET", "NOT_MET", "UNKNOWN"}, "EVENT_STATES_INVALID")
        current = snapshot["items"].get(item, {}).get("current")
        event = (current or {}).get("review", {}).get("event")
        bound = current and result.get("item_revision_sha256") == current["revision_sha256"] and result.get("event_sha256") == _digest(event)
        observed = result.get("as_of")
        event_age = (wire.clock(now) - wire.clock(observed)).total_seconds() if observed else None
        if not bound or freshness != "REMOTE_VERIFIED" or event_age is None or not 0 <= event_age <= max_age_seconds:
            result.update(status="UNKNOWN", reason="SOURCE_OBSERVATION_NOT_FRESH_OR_BOUND", execution_deadline=None)
    return dict(snapshot, status=status, commit=head, files=files, source_freshness=freshness,
                source_checked_at=checked, observation_age_seconds=age, reason=reason,
                event_states=states, observation_sha256=witness["observation_sha256"])


def write_snapshot(path: Path, raw: bytes) -> None:
    """Atomic replacement of a disposable derived snapshot, never a user draft."""
    from .research_shelf_git import _local_path
    path = _local_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".pending", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_snapshot(path: Path, *, now: str) -> dict[str, Any]:
    try:
        from .research_shelf_git import _local_path
        path = _local_path(path)
        with path.open("rb") as stream:
            raw = stream.read(MAX_EXPORT_BYTES + 1)
        return read_snapshot(raw, now=now)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, AttributeError, RecursionError):
        return dict(status="UNAVAILABLE", complete=False, items={}, commit=None,
                    source_freshness="UNVERIFIED_PINNED", source_checked_at=None,
                    reason="PINNED_SNAPSHOT_UNAVAILABLE_OR_INVALID")


def glance(repo_root: Path, *, snapshot_path: Path | None = None, now: str | None = None) -> dict[str, Any]:
    """Public run seam: one read, no refresh, native readback or authority decision."""
    at = now or utc_now()
    configured = os.environ.get("SMIAL_RESEARCH_SHELF_SNAPSHOT")
    path = snapshot_path or (Path(configured) if configured else repo_root / "local/research_shelf_v1/snapshot.json")
    snapshot = load_snapshot(path, now=at)
    try:
        summary = wire.attention(snapshot, now=at, source_states=snapshot.get("event_states"))
    except (ValueError, TypeError, KeyError, AttributeError):
        summary = wire.attention(dict(status="UNAVAILABLE", complete=False, items={}, reason="SNAPSHOT_PROJECTION_INVALID"), now=at)
    summary.update(receipt_hash_domain="EXCLUDED_DERIVED_OVERLAY", refresh_recipe=REFRESH_RECIPE)
    return summary


def readout(summary: Mapping[str, Any]) -> str:
    if summary["status"] != "READY" or summary["source_freshness"] != "REMOTE_VERIFIED":
        state = summary["status"] if summary["status"] != "READY" else summary["source_freshness"]
        return f"Полка: {state}; {summary.get('reason') or 'нужна проверка data head'}. Refresh: {REFRESH_RECIPE}"
    totals = summary["totals"]
    due = sum(totals.get(key, 0) for key in ("DUE_REVIEW", "EVENT_REVIEW", "OVERDUE_REVIEW", "EXPIRED_REVIEW_REQUIRED", "NEEDS_TRIAGE"))
    unknown = sum(totals.get(key, 0) for key in ("SOURCE_READBACK_REQUIRED", "ITEM_INVALID", "ITEM_CONFLICT"))
    rows = [f"Полка: {due} требуют внимания, {unknown} ждут сверки; data commit {summary['snapshot_commit']}; научный допуск не проверен."]
    for item in summary.get("items", [])[:5]:
        # Wire bounds the stored title; keep the owner glance compact and one-line.
        title = " ".join(str(item.get("title") or item["item_id"]).split())[:100]
        when = ((item.get("source_observation") or {}).get("execution_deadline") if item["status"] == "EXPIRED_REVIEW_REQUIRED"
                else (item.get("review") or {}).get("review_by" if item["status"] == "OVERDUE_REVIEW" else "review_at"))
        rows.append(f"  {item['status']}: {title} [{item['item_id']}]" + (f"; срок {when}" if when else ""))
        if item.get("next_action"):
            intent = " ".join(str(item["next_action"].get("intent") or "").split())[:100]
            rows.append("    Намерение: " + intent)
    if summary.get("next_review_at"):
        rows.append("Ближайший обзор: " + summary["next_review_at"])
    if summary.get("omitted_count"):
        rows.append(f"Ещё {summary['omitted_count']}; полный обзор: research_shelf.py review --snapshot <snapshot.json> --all")
    if due or unknown:
        rows.append("Далее: review --snapshot <snapshot.json>; сверить exact source, затем решить defer/link/close.")
    return "\n".join(rows)


def private_origin(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("repository") == "lancerbeta/marcopolo-scout" or value.get("owner") == "SCOUT" or value.get("product") == "SCOUT":
            return True
        return any(private_origin(child) for child in value.values())
    if isinstance(value, list):
        return any(private_origin(child) for child in value)
    return isinstance(value, str) and "lancerbeta/marcopolo-scout" in value


def public_payload_guard(value: Mapping[str, Any], *, disclosure: Mapping[str, Any] | None = None) -> None:
    """No confidentiality classifier. Private-origin bytes need exact explicit review.

    The caller supplies an owner-reviewed minimal public payload digest. This
    module never issues such approval and never copies a rich private dossier.
    Any changed text/ref anywhere invalidates that approval, including nested text.
    """
    wire._guard(value)  # Same narrow secret/path guard over every outgoing value.
    if private_origin(value):
        wire.require(isinstance(disclosure, dict) and
                     disclosure.get("disposition") == "EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE" and
                     disclosure.get("payload_sha256") == _digest(value), "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED")
