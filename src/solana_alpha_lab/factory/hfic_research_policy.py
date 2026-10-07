"""Append-only Forge research-policy runtime.

ResearchStore owns three things, each its own append-only artifact kind:

* the ACTIVE policy for *new* runs (``FORGE_RESEARCH_POLICY_V1``, one current
  head, CAS-applied, never blocked by an open operation);
* a per-journal frozen RUN SNAPSHOT taken the first time a journal is ever
  touched (``FORGE_RESEARCH_POLICY_RUN_SNAPSHOT_V1``, first-writer-wins);
* an append-only chain of explicit per-journal EXTENSIONS on top of that
  snapshot (``FORGE_RESEARCH_POLICY_RUN_EXTENSION_V1``).

A journal's effective limits are its frozen snapshot plus its own extension
chain. Changing the active policy never moves an existing journal; only an
explicit, owner-authorized extension against that exact journal does, and it
never resets what is already spent (spend is computed independently, from
recorded looks and reservations, by the ordinary-operation owner).

Git owns the shipped defaults and the hard fuses below. A missing policy
record means the shipped defaults, not an unbounded budget.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStoreError
from solana_alpha_lab.factory.run_passport import canonical_sha256

SCHEMA = "smial.forge-research-policy"
SCHEMA_VERSION = "1.0"
ARTIFACT_KIND = "FORGE_RESEARCH_POLICY_V1"
SNAPSHOT_SCHEMA = "smial.forge-research-policy-run-snapshot"
SNAPSHOT_KIND = "FORGE_RESEARCH_POLICY_RUN_SNAPSHOT_V1"
EXTENSION_SCHEMA = "smial.forge-research-policy-run-extension"
EXTENSION_KIND = "FORGE_RESEARCH_POLICY_RUN_EXTENSION_V1"
GENESIS_HEAD_SHA256 = "0" * 64
REASON_OWNER_POLICY_CHANGE = "OWNER_RESEARCH_POLICY_CHANGE"
REASON_OWNER_EXTENSION = "OWNER_RESEARCH_POLICY_RUN_EXTENSION"
PRODUCER = "CAP-FORGE-RESEARCH-POLICY-001"
NO_CHANGE = "NO_CHANGE"
APPENDED = "APPENDED"

PRESET_MAX_COUNT = 16
PRESET_MAX_BYTES = 4096
PRESETS_TOTAL_MAX_BYTES = 16384
_PRESET_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# Shipped defaults. Never raise these as the state this PR delivers: an
# ABSENT policy record resolves to exactly this body.
DEFAULT_LIMITS: dict[str, int] = {
    "auto_cycles_per_market": 1,
    "distinct_focuses_per_market": 3,
    "main_total": 6,
    "adaptive_total": 2,
    "preview_total": 2,
    "simple_before_compound": 3,
    "max_generated": 6,
    "max_diagnostic_slices": 8,
}

# The highest value any owner action may ever set a field to, regardless of
# preset or extension. `max_diagnostic_slices` is pinned at its shipped
# default: this knob may only be lowered, never raised, in this delivery.
HARD_FUSES: dict[str, int] = {
    "auto_cycles_per_market": 8,
    "distinct_focuses_per_market": 32,
    "main_total": 32,
    "adaptive_total": 8,
    "preview_total": 8,
    "simple_before_compound": 32,
    "max_generated": 16,
    "max_diagnostic_slices": 8,
}

LIMIT_FIELDS = tuple(DEFAULT_LIMITS)


class ResearchPolicyError(ValueError):
    """Fail-closed research-policy error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# --------------------------------------------------------------------------
# Pure validation / arithmetic. No store access.
# --------------------------------------------------------------------------


def validate_limits(body: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(body, Mapping) or set(body) != set(LIMIT_FIELDS):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    out: dict[str, int] = {}
    for key in LIMIT_FIELDS:
        value = body[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > HARD_FUSES[key]:
            raise ResearchPolicyError("RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")
        out[key] = int(value)
    if out["simple_before_compound"] > out["main_total"]:
        raise ResearchPolicyError("RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL")
    return out


def _validate_delta_fields(delta: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(delta, Mapping) or not set(delta) <= set(LIMIT_FIELDS) or not delta:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    out: dict[str, int] = {}
    for key, value in delta.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > HARD_FUSES[key]:
            raise ResearchPolicyError("RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")
        out[str(key)] = int(value)
    return out


def validate_presets(presets: Mapping[str, Any] | None) -> dict[str, dict[str, int]]:
    if presets is None:
        return {}
    if not isinstance(presets, Mapping) or len(presets) > PRESET_MAX_COUNT:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESETS_INVALID")
    out: dict[str, dict[str, int]] = {}
    total_bytes = 0
    for name, delta in presets.items():
        if not isinstance(name, str) or not _PRESET_NAME_RE.match(name):
            raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NAME_INVALID")
        encoded = json.dumps(delta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > PRESET_MAX_BYTES:
            raise ResearchPolicyError("RESEARCH_POLICY_PRESET_TOO_LARGE")
        total_bytes += len(encoded.encode("utf-8"))
        out[name] = _validate_delta_fields(delta)
    if total_bytes > PRESETS_TOTAL_MAX_BYTES:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESETS_TOO_LARGE")
    return out


def semantic_sha256(limits: Mapping[str, Any], presets: Mapping[str, Any]) -> str:
    return canonical_sha256({"limits": validate_limits(limits), "presets": validate_presets(presets)})


def _artifact_body(record: Any) -> dict[str, Any] | None:
    raw = getattr(record, "payload_json", "") or ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        wrapper = json.loads(raw)
        body = json.loads(str(wrapper.get("payload_canonical") or ""))
    except (TypeError, ValueError, AttributeError):
        return None
    return body if isinstance(body, dict) else None


def _iter_artifacts(store: Any, kind: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        record_kind = getattr(record.record_kind, "value", record.record_kind)
        if record_kind != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        body = _artifact_body(record)
        if not isinstance(body, dict) or body.get("artifact_kind") != kind:
            continue
        recorded = getattr(record, "created_at", None)
        body["_recorded_at"] = recorded.isoformat() if hasattr(recorded, "isoformat") else ""
        found.append(body)
    return found


def _append_artifact(
    store: Any,
    *,
    kind: str,
    body: Mapping[str, Any],
    record_prefix: str,
    before_commit: Any = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    try:
        now = capture_stage_time(clock)
        created_at = render_canonical_utc(now)
    except HficClockError as exc:
        raise ResearchPolicyError(str(exc)) from exc
    unsigned = {**dict(body), "created_at": created_at}
    identity = canonical_sha256(unsigned)
    artifact = {"artifact_kind": kind, **unsigned, "policy_artifact_sha256": identity}
    canonical_text = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = {
        "artifact_kind": kind,
        "payload_canonical": canonical_text,
        "payload_sha256": canonical_sha256(artifact),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    record_id = f"{record_prefix}-{identity[:40].upper()}"
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-{record_prefix}-{identity[:24].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=canonical_sha256(payload),
        schema_version="1.0",
        producer_capability_id=PRODUCER,
        producer_git_sha="0" * 40,
        created_at=now,
    )
    store.append([event], transaction_id=event.transaction_id, before_commit=before_commit)
    artifact["record_id"] = record_id
    return artifact


# --------------------------------------------------------------------------
# Active policy for new runs.
# --------------------------------------------------------------------------


def load_policy_records(store: Any) -> list[dict[str, Any]]:
    found = [item for item in _iter_artifacts(store, ARTIFACT_KIND) if item.get("schema") == SCHEMA]
    found.sort(key=lambda item: int(item.get("policy_sequence") or 0))
    return found


def effective_policy(store: Any) -> dict[str, Any]:
    records = load_policy_records(store)
    if not records:
        return {
            "state": "ABSENT",
            "limits": dict(DEFAULT_LIMITS),
            "presets": {},
            "semantic_sha256": semantic_sha256(DEFAULT_LIMITS, {}),
            "policy_head_sha256": GENESIS_HEAD_SHA256,
            "policy_sequence": 0,
            "next_action": "PREVIEW_THEN_AUTHORIZED_APPLY",
        }
    head = records[-1]
    limits = validate_limits(head.get("limits") or {})
    presets = validate_presets(head.get("presets") or {})
    expected = semantic_sha256(limits, presets)
    if str(head.get("semantic_sha256") or "") != expected:
        raise ResearchPolicyError("RESEARCH_POLICY_BINDING_MISMATCH")
    return {
        "state": "ACTIVE",
        "limits": limits,
        "presets": presets,
        "semantic_sha256": expected,
        "policy_head_sha256": head["policy_artifact_sha256"],
        "policy_sequence": int(head.get("policy_sequence") or 0),
        "next_action": "NEW_FORGE_OPERATIONS_USE_THIS_POLICY",
    }


def read_active_policy(store: Any) -> dict[str, Any]:
    return effective_policy(store)


def _resolved_delta(head: Mapping[str, Any], *, limits_delta: Mapping[str, Any] | None, preset_name: str | None) -> dict[str, int]:
    delta: dict[str, int] = {}
    if preset_name is not None:
        presets = dict(head.get("presets") or {})
        if preset_name not in presets:
            raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NOT_FOUND")
        delta.update(presets[preset_name])
    if limits_delta:
        delta.update(_validate_delta_fields(limits_delta))
    if not delta:
        raise ResearchPolicyError("RESEARCH_POLICY_CHANGE_EMPTY")
    return delta


def preview_policy_change(
    store: Any,
    *,
    limits_delta: Mapping[str, Any] | None = None,
    presets_delta: Mapping[str, Any] | None = None,
    preset_name: str | None = None,
) -> dict[str, Any]:
    head = effective_policy(store)
    delta = _resolved_delta(head, limits_delta=limits_delta, preset_name=preset_name)
    limits = validate_limits({**head["limits"], **delta})
    presets = dict(head["presets"])
    if presets_delta is not None:
        presets.update(presets_delta)
    presets = validate_presets(presets)
    after_semantic = semantic_sha256(limits, presets)
    proposal = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "base_policy_head_sha256": head["policy_head_sha256"],
        "base_store_inventory_digest": store.diagnostics().committed_inventory_sha256,
        "limits": limits,
        "presets": presets,
        "semantic_sha256": after_semantic,
        "reason_code": REASON_OWNER_POLICY_CHANGE,
    }
    proposal["proposal_sha256"] = canonical_sha256(proposal)
    return {
        "action": "RESEARCH_POLICY_PREVIEW",
        "status": NO_CHANGE if after_semantic == head["semantic_sha256"] else "PROPOSED",
        "before": {"limits": head["limits"], "presets": head["presets"], "semantic_sha256": head["semantic_sha256"]},
        "after": {"limits": limits, "presets": presets, "semantic_sha256": after_semantic},
        "proposal": proposal,
        "proposal_sha256": proposal["proposal_sha256"],
        "expected_policy_head_sha256": head["policy_head_sha256"],
        "claim_boundary": "A policy change sets a budget ceiling for new runs. It is not a scientific look and reads no market values.",
        "next_action": "AUTHORIZED_APPLY" if after_semantic != head["semantic_sha256"] else "READ_ACTIVE_POLICY",
        "writes": {"research_store": 0},
    }


def apply_policy_change(
    store: Any,
    *,
    proposal: Mapping[str, Any],
    confirm_append_only: bool,
    clock: Clock | None = None,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise ResearchPolicyError("RESEARCH_POLICY_CONFIRM_REQUIRED")
    expected = dict(proposal)
    observed = expected.pop("proposal_sha256", None)
    if canonical_sha256(expected) != observed:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    if expected.get("reason_code") != REASON_OWNER_POLICY_CHANGE:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    limits = validate_limits(expected.get("limits") or {})
    presets = validate_presets(expected.get("presets") or {})
    if expected.get("semantic_sha256") != semantic_sha256(limits, presets):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    head = effective_policy(store)
    inventory = store.diagnostics().committed_inventory_sha256
    if expected.get("base_policy_head_sha256") != head["policy_head_sha256"]:
        raise ResearchPolicyError("RESEARCH_POLICY_PREVIEW_STALE")
    if expected.get("base_store_inventory_digest") != inventory:
        raise ResearchPolicyError("RESEARCH_POLICY_PREVIEW_STALE")
    if head["semantic_sha256"] == expected["semantic_sha256"]:
        return {
            "action": "RESEARCH_POLICY_APPLY",
            "status": NO_CHANGE,
            "appended": False,
            "limits": head["limits"],
            "presets": head["presets"],
            "semantic_sha256": head["semantic_sha256"],
            "policy_head_sha256": head["policy_head_sha256"],
            "writes": {"research_store": 0},
        }
    sequence = int(head.get("policy_sequence") or 0) + 1
    body = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "policy_id": f"FORGE-RESEARCH-POLICY-{sequence:04d}",
        "policy_sequence": sequence,
        "previous_policy_sha256": head["policy_head_sha256"],
        "limits": limits,
        "presets": presets,
        "semantic_sha256": expected["semantic_sha256"],
        "reason_code": REASON_OWNER_POLICY_CHANGE,
        "non_claims": [
            "NOT_A_SCIENTIFIC_LOOK",
            "NOT_STRATEGY_PROMOTION",
            "NEW_FORGE_OPERATIONS_ONLY",
            "DOES_NOT_MOVE_AN_EXISTING_RUN_SNAPSHOT",
        ],
    }

    def _still_current() -> None:
        if effective_policy(store)["policy_head_sha256"] != head["policy_head_sha256"]:
            raise ResearchPolicyError("RESEARCH_POLICY_PREVIEW_STALE")

    try:
        artifact = _append_artifact(
            store,
            kind=ARTIFACT_KIND,
            body=body,
            record_prefix="HFIC-ART-RPOL",
            before_commit=_still_current,
            clock=clock,
        )
    except ResearchStoreError as exc:
        raise ResearchPolicyError(str(exc)) from exc
    return {
        "action": "RESEARCH_POLICY_APPLY",
        "status": APPENDED,
        "appended": True,
        "limits": limits,
        "presets": presets,
        "semantic_sha256": expected["semantic_sha256"],
        "policy_head_sha256": artifact["policy_artifact_sha256"],
        "policy_sequence": sequence,
        "created_at": artifact["created_at"],
        "writes": {"research_store": 1},
    }


# --------------------------------------------------------------------------
# Per-journal frozen run snapshot.
# --------------------------------------------------------------------------


def read_run_snapshot(store: Any, journal_scope: str) -> dict[str, Any] | None:
    rows = [item for item in _iter_artifacts(store, SNAPSHOT_KIND) if item.get("journal_scope") == journal_scope]
    if not rows:
        return None
    return dict(min(rows, key=lambda item: str(item.get("_recorded_at") or "")))


def snapshot_for_new_run(store: Any) -> dict[str, Any]:
    """The limits a brand-new journal would freeze right now. Reads no values."""

    head = effective_policy(store)
    return {"limits": head["limits"], "policy_head_sha256": head["policy_head_sha256"], "policy_semantic_sha256": head["semantic_sha256"]}


def ensure_run_snapshot(store: Any, journal_scope: str, *, clock: Clock | None = None) -> dict[str, Any]:
    """Idempotently freeze this journal's limits at the currently active policy.

    First writer wins: a benign race between two first-touches of the same
    journal converges on whichever row actually committed.
    """

    existing = read_run_snapshot(store, journal_scope)
    if existing is not None:
        return existing
    frozen = snapshot_for_new_run(store)
    body = {
        "schema": SNAPSHOT_SCHEMA,
        "schema_version": "1.0",
        "journal_scope": journal_scope,
        "limits": frozen["limits"],
        "policy_head_sha256": frozen["policy_head_sha256"],
        "policy_semantic_sha256": frozen["policy_semantic_sha256"],
    }

    def _check() -> None:
        if read_run_snapshot(store, journal_scope) is not None:
            raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_RACE_LOST")

    for _attempt in range(8):
        try:
            return _append_artifact(
                store,
                kind=SNAPSHOT_KIND,
                body=body,
                record_prefix="HFIC-ART-RPSNAP",
                before_commit=_check,
                clock=clock,
            )
        except ResearchPolicyError as exc:
            if exc.code != "RESEARCH_POLICY_RUN_SNAPSHOT_RACE_LOST":
                raise
            winner = read_run_snapshot(store, journal_scope)
            if winner is not None:
                return winner
        except ResearchStoreError:
            winner = read_run_snapshot(store, journal_scope)
            if winner is not None:
                return winner
    raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_RACE_UNRESOLVED")


# --------------------------------------------------------------------------
# Per-journal explicit extensions. Append-only, never resets spend.
# --------------------------------------------------------------------------


def read_run_extensions(store: Any, journal_scope: str) -> list[dict[str, Any]]:
    rows = [item for item in _iter_artifacts(store, EXTENSION_KIND) if item.get("journal_scope") == journal_scope]
    rows.sort(key=lambda item: int(item.get("extension_sequence") or 0))
    return rows


def limits_for_frozen_run(store: Any, journal_scope: str) -> dict[str, int]:
    """Effective limits for one journal: its frozen snapshot plus its own extensions.

    A journal this owner has never touched (legacy, pre-dating this policy
    runtime) reads the shipped defaults, unchanged, and writes nothing.
    """

    snapshot = read_run_snapshot(store, journal_scope)
    if snapshot is None:
        return dict(DEFAULT_LIMITS)
    limits = dict(validate_limits(snapshot["limits"]))
    for extension in read_run_extensions(store, journal_scope):
        limits.update(extension["limits_delta"])
    return validate_limits(limits)


def propose_run_extension(
    store: Any,
    *,
    journal_scope: str,
    parent_operation_sha256: str,
    limits_delta: Mapping[str, Any],
) -> dict[str, Any]:
    if len(journal_scope) != 64 or len(parent_operation_sha256) != 64:
        raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_BINDING_INVALID")
    snapshot = read_run_snapshot(store, journal_scope)
    if snapshot is None:
        raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_MISSING")
    extensions = read_run_extensions(store, journal_scope)
    current = dict(validate_limits(snapshot["limits"]))
    for extension in extensions:
        current.update(extension["limits_delta"])
    cleaned_delta = _validate_delta_fields(limits_delta)
    resulting = validate_limits({**current, **cleaned_delta})
    proposal = {
        "schema": EXTENSION_SCHEMA,
        "schema_version": "1.0",
        "journal_scope": journal_scope,
        "parent_operation_sha256": parent_operation_sha256,
        "base_extension_sequence": len(extensions),
        "limits_delta": cleaned_delta,
        "resulting_limits": resulting,
        "reason_code": REASON_OWNER_EXTENSION,
    }
    proposal["proposal_sha256"] = canonical_sha256(proposal)
    return proposal


def apply_run_extension(
    store: Any,
    *,
    proposal: Mapping[str, Any],
    confirm_append_only: bool,
    clock: Clock | None = None,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise ResearchPolicyError("RESEARCH_POLICY_CONFIRM_REQUIRED")
    expected = dict(proposal)
    observed = expected.pop("proposal_sha256", None)
    if canonical_sha256(expected) != observed:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    if expected.get("reason_code") != REASON_OWNER_EXTENSION:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    journal_scope = str(expected.get("journal_scope") or "")
    snapshot = read_run_snapshot(store, journal_scope)
    if snapshot is None:
        raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_MISSING")
    extensions = read_run_extensions(store, journal_scope)
    if int(expected.get("base_extension_sequence") if expected.get("base_extension_sequence") is not None else -1) != len(extensions):
        raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_STALE")
    current = dict(validate_limits(snapshot["limits"]))
    for extension in extensions:
        current.update(extension["limits_delta"])
    cleaned_delta = _validate_delta_fields(expected.get("limits_delta") or {})
    resulting = validate_limits({**current, **cleaned_delta})
    if resulting != expected.get("resulting_limits"):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    sequence = len(extensions) + 1
    body = {**expected, "limits_delta": cleaned_delta, "resulting_limits": resulting, "extension_sequence": sequence}

    def _check() -> None:
        if len(read_run_extensions(store, journal_scope)) != len(extensions):
            raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_STALE")

    try:
        artifact = _append_artifact(
            store,
            kind=EXTENSION_KIND,
            body=body,
            record_prefix="HFIC-ART-RPEXT",
            before_commit=_check,
            clock=clock,
        )
    except ResearchStoreError as exc:
        raise ResearchPolicyError(str(exc)) from exc
    return {
        "action": "RESEARCH_POLICY_EXTENSION_APPLY",
        "status": APPENDED,
        "journal_scope": journal_scope,
        "extension_sequence": sequence,
        "resulting_limits": resulting,
        "created_at": artifact["created_at"],
        "writes": {"research_store": 1},
    }
