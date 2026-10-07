"""Append-only Forge research-policy runtime.

ResearchStore owns three append-only artifact kinds, one owner module, three
distinct CAS surfaces:

* the ACTIVE policy for *new* scopes (``FORGE_RESEARCH_POLICY_V1``: one
  current head; applied against the head it was previewed from; never blocked
  by an open operation);
* a frozen SNAPSHOT of one accounting scope, taken the first time that scope
  is touched through a write path (``FORGE_RESEARCH_POLICY_RUN_SNAPSHOT_V1``,
  first-writer-wins);
* an append-only chain of explicit EXTENSIONS of that scope's frozen limits
  (``FORGE_RESEARCH_POLICY_RUN_EXTENSION_V1``).

A scope is either a JOURNAL (one query accounting domain: MAIN, ADAPTIVE,
PREVIEW, allocation, candidate and slice limits) or a market EPOCH (a shared
pool: AUTO cycles and distinct focuses). A shared pool must be frozen per
epoch, never per journal, or a new journal could bring its own cap into an
epoch whose budget is already spent.

Effective limits of a scope are its frozen snapshot plus its own extensions.
Changing the active policy never moves a frozen scope; only an explicit
extension of that exact scope does, and it never resets spend (spend is
computed by the ordinary-operation owner from recorded looks and
reservations). A scope that already has history but no snapshot (it pre-dates
this runtime) freezes at the shipped defaults, never at today's raised policy.

Git owns the shipped defaults, ranges and hard fuses below. Present-invalid
state (a corrupt, forked or hash-mismatched record) is a typed refusal, never
a silent fall back to the defaults.
"""

from __future__ import annotations

import copy
import json
import re
import time
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
ALREADY_APPLIED = "ALREADY_APPLIED"

SOURCE_DEFAULTS = "DEFAULTS_V1"
SOURCE_LEGACY = "LEGACY_DEFAULTS_V1"
SOURCE_STORE = "STORE_REVISION"
BASIS_ACTIVE_POLICY = "ACTIVE_POLICY_AT_FIRST_TOUCH"
BASIS_LEGACY_DEFAULTS = "LEGACY_DEFAULTS_AT_FIRST_TOUCH"

SCOPE_JOURNAL = "JOURNAL"
SCOPE_EPOCH = "EPOCH"
EPOCH_PREFIX = "EPOCH:"

PRESET_MAX_COUNT = 16
PRESET_MAX_BYTES = 4096
POLICY_MAX_BYTES = 16384
_PRESET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA64_RE = re.compile(r"^[0-9a-f]{64}$")

# Shipped defaults. This delivery never raises them: an ABSENT policy resolves
# to exactly these values.
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

# (minimum, hard fuse). 0 forbids new actions of that kind; it is not unlimited.
FIELD_RANGES: dict[str, tuple[int, int]] = {
    "auto_cycles_per_market": (0, 8),
    "distinct_focuses_per_market": (0, 32),
    "main_total": (0, 32),
    "adaptive_total": (0, 8),
    "preview_total": (0, 8),
    "simple_before_compound": (0, 32),
    "max_generated": (1, 16),
    "max_diagnostic_slices": (0, 8),
}
HARD_FUSES: dict[str, int] = {key: high for key, (_low, high) in FIELD_RANGES.items()}
LIMIT_FIELDS = tuple(DEFAULT_LIMITS)
EPOCH_FIELDS = ("auto_cycles_per_market", "distinct_focuses_per_market")
JOURNAL_FIELDS = tuple(key for key in LIMIT_FIELDS if key not in EPOCH_FIELDS)

PRESET_REQUIRED = ("preset_id", "population", "hypothesis_kind", "research_scope")
PRESET_OPTIONAL = ("representation_id", "list_condition", "diagnostic_slices", "label")
PRESET_HYPOTHESIS_KINDS = ("NUMERIC_IN_SCOPE", "LIST_CONTRAST", "MIXED_LIST_NUMERIC")
_PRESET_NESTING_KEYS = frozenset({"preset", "preset_ref", "presets", "extends", "include", "$ref"})


class ResearchPolicyError(ValueError):
    """Fail-closed research-policy error. ``detail`` names the failing field."""

    def __init__(self, code: str, **detail: Any) -> None:
        self.code = code
        self.detail = dict(detail)
        super().__init__(code)


# --------------------------------------------------------------------------
# Scope keys.
# --------------------------------------------------------------------------


def epoch_scope_key(market_evidence_epoch_sha256: str) -> str:
    if not isinstance(market_evidence_epoch_sha256, str) or not _SHA64_RE.match(market_evidence_epoch_sha256):
        raise ResearchPolicyError("RESEARCH_POLICY_SCOPE_INVALID")
    return EPOCH_PREFIX + market_evidence_epoch_sha256


def scope_kind(scope_key: str) -> str:
    if isinstance(scope_key, str) and scope_key.startswith(EPOCH_PREFIX) and _SHA64_RE.match(scope_key[len(EPOCH_PREFIX):]):
        return SCOPE_EPOCH
    if isinstance(scope_key, str) and _SHA64_RE.match(scope_key):
        return SCOPE_JOURNAL
    raise ResearchPolicyError("RESEARCH_POLICY_SCOPE_INVALID")


def scope_fields(scope_key: str) -> tuple[str, ...]:
    return EPOCH_FIELDS if scope_kind(scope_key) == SCOPE_EPOCH else JOURNAL_FIELDS


# --------------------------------------------------------------------------
# Pure validation. No store access.
# --------------------------------------------------------------------------


def _check_value(key: str, value: Any) -> int:
    low, high = FIELD_RANGES[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < low or value > high:
        raise ResearchPolicyError(
            "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE", field=key, minimum=low, hard_fuse=high
        )
    return int(value)


def validate_limits(body: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(body, Mapping) or set(body) != set(LIMIT_FIELDS):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID")
    out = {key: _check_value(key, body[key]) for key in LIMIT_FIELDS}
    if out["simple_before_compound"] > out["main_total"]:
        raise ResearchPolicyError(
            "RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL",
            field="simple_before_compound",
            hard_fuse=out["main_total"],
        )
    return out


def validate_delta(delta: Mapping[str, Any], *, allowed: tuple[str, ...] = LIMIT_FIELDS) -> dict[str, int]:
    if not isinstance(delta, Mapping) or not delta:
        raise ResearchPolicyError("RESEARCH_POLICY_CHANGE_EMPTY")
    unknown = sorted(str(key) for key in delta if key not in LIMIT_FIELDS)
    if unknown:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID", field=unknown[0])
    foreign = sorted(str(key) for key in delta if key not in allowed)
    if foreign:
        raise ResearchPolicyError("RESEARCH_POLICY_FIELD_NOT_IN_SCOPE", field=foreign[0], allowed=list(allowed))
    return {str(key): _check_value(str(key), value) for key, value in delta.items()}


def _walk_for_nesting(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(key in _PRESET_NESTING_KEYS or _walk_for_nesting(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_walk_for_nesting(item) for item in value)
    return False


def validate_preset(preset_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """One expanded draft-input body. The PR-A resolver still runs at use."""

    if not isinstance(preset_id, str) or not _PRESET_ID_RE.match(preset_id):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NAME_INVALID", field="preset_id")
    if not isinstance(body, Mapping):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field=preset_id)
    unknown = sorted(str(key) for key in body if key not in PRESET_REQUIRED + PRESET_OPTIONAL)
    if unknown:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field=unknown[0])
    missing = [key for key in PRESET_REQUIRED if key not in body]
    if missing:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field=missing[0])
    if body["preset_id"] != preset_id:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field="preset_id")
    if body["hypothesis_kind"] not in PRESET_HYPOTHESIS_KINDS:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field="hypothesis_kind")
    if not isinstance(body["research_scope"], Mapping):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field="research_scope")
    list_condition = body.get("list_condition")
    if list_condition is not None and not isinstance(list_condition, Mapping):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field="list_condition")
    slices = body.get("diagnostic_slices", [])
    if not isinstance(slices, list):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_INVALID", field="diagnostic_slices")
    if _walk_for_nesting(dict(body)):
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NESTING_FORBIDDEN", field=preset_id)
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > PRESET_MAX_BYTES:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_TOO_LARGE", field=preset_id, maximum=PRESET_MAX_BYTES)
    return json.loads(encoded)


def validate_presets(presets: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if presets is None:
        return {}
    if not isinstance(presets, Mapping) or len(presets) > PRESET_MAX_COUNT:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESETS_INVALID", maximum=PRESET_MAX_COUNT)
    return {str(preset_id): validate_preset(str(preset_id), body) for preset_id, body in sorted(presets.items())}


def _check_body_size(limits: Mapping[str, Any], presets: Mapping[str, Any]) -> None:
    encoded = json.dumps({"limits": limits, "presets": presets}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > POLICY_MAX_BYTES:
        raise ResearchPolicyError("RESEARCH_POLICY_TOO_LARGE", maximum=POLICY_MAX_BYTES)


def semantic_sha256(limits: Mapping[str, Any], presets: Mapping[str, Any]) -> str:
    checked_limits = validate_limits(limits)
    checked_presets = validate_presets(presets)
    _check_body_size(checked_limits, checked_presets)
    return canonical_sha256({"limits": checked_limits, "presets": checked_presets})


def expand_preset(
    presets: Mapping[str, Any], preset_id: str, explicit_fields: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """A preset applied to explicit fields. A conflicting field is refused, never deep-merged."""

    if preset_id not in presets:
        raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NOT_FOUND", field=preset_id)
    expanded = {key: copy.deepcopy(value) for key, value in presets[preset_id].items() if key != "preset_id"}
    for key, value in (explicit_fields or {}).items():
        if key in expanded and expanded[key] != value:
            raise ResearchPolicyError("RESEARCH_POLICY_PRESET_CONFLICT", field=str(key), preset_id=preset_id)
        expanded[key] = value
    return expanded


# --------------------------------------------------------------------------
# Store access: verified artifact readers and the append helper.
# --------------------------------------------------------------------------

_NON_IDENTITY_KEYS = frozenset({"artifact_kind", "policy_artifact_sha256", "_recorded_at"})


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


def _verified(body: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in body.items() if key not in _NON_IDENTITY_KEYS}
    if canonical_sha256(unsigned) != body.get("policy_artifact_sha256"):
        raise ResearchPolicyError("RESEARCH_POLICY_CHAIN_CORRUPT", kind=str(body.get("artifact_kind")))
    return body


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
        found.append(_verified(body))
    return found


def _public(body: Mapping[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in body.items() if not str(key).startswith("_")}


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
    return _public(artifact)


def _append_with_busy_retry(store: Any, *, recheck: Any, **kwargs: Any) -> dict[str, Any]:
    """Retry only transient writer-lease contention; re-check the real CAS each time."""

    for attempt in range(40):
        try:
            return _append_artifact(store, before_commit=recheck, **kwargs)
        except ResearchPolicyError:
            raise
        except ResearchStoreError as exc:
            if getattr(exc, "code", str(exc)) != "WRITER_BUSY":
                raise ResearchPolicyError(str(getattr(exc, "code", exc))) from exc
            recheck()
            if attempt >= 39:
                raise ResearchPolicyError("WRITER_BUSY") from exc
            time.sleep(0.05)
    raise ResearchPolicyError("WRITER_BUSY")


# --------------------------------------------------------------------------
# Active policy for new scopes.
# --------------------------------------------------------------------------


def load_policy_records(store: Any) -> list[dict[str, Any]]:
    found = [item for item in _iter_artifacts(store, ARTIFACT_KIND) if item.get("schema") == SCHEMA]
    found.sort(key=lambda item: int(item.get("policy_sequence") or 0))
    previous = GENESIS_HEAD_SHA256
    for index, record in enumerate(found, start=1):
        if int(record.get("policy_sequence") or 0) != index or record.get("previous_policy_sha256") != previous:
            raise ResearchPolicyError("RESEARCH_POLICY_CHAIN_CORRUPT", kind=ARTIFACT_KIND, sequence=index)
        previous = str(record.get("policy_artifact_sha256"))
    return found


def effective_policy(store: Any) -> dict[str, Any]:
    records = load_policy_records(store)
    if not records:
        return {
            "state": "ABSENT",
            "source": SOURCE_DEFAULTS,
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
        "source": SOURCE_STORE,
        "limits": limits,
        "presets": presets,
        "semantic_sha256": expected,
        "policy_head_sha256": str(head["policy_artifact_sha256"]),
        "policy_sequence": int(head.get("policy_sequence") or 0),
        "next_action": "NEW_FORGE_SCOPES_USE_THIS_POLICY",
    }


def read_active_policy(store: Any) -> dict[str, Any]:
    return effective_policy(store)


def _claim_boundary(kind: str) -> dict[str, Any]:
    if kind == "POLICY":
        return {
            "claim_boundary": "A budget ceiling for scopes not yet frozen. Not a scientific look; reads no market values.",
            "unchanged": [
                "every journal and market epoch already frozen keeps its own limits",
                "spent and reserved attempts are not reset",
                "no research was run and the VPS is not changed",
            ],
            "next_action": "TO_RAISE_AN_OPEN_JOURNAL_OR_EPOCH_USE_research-policy-extension-preview",
        }
    return {
        "claim_boundary": "Raises the ceiling of this exact scope only. Total is the whole ceiling of the scope, not an extra allowance; spend is not reset.",
        "unchanged": [
            "other journals and epochs",
            "the active policy for new scopes",
            "what this scope has already spent or reserved",
        ],
        "next_action": "RUN_THE_NEXT_AUTHORIZED_LOOK_OR_CYCLE",
    }


def preview_policy_change(
    store: Any,
    *,
    limits_delta: Mapping[str, Any] | None = None,
    presets_delta: Mapping[str, Any] | None = None,
    presets_remove: list[str] | None = None,
) -> dict[str, Any]:
    head = effective_policy(store)
    delta = validate_delta(limits_delta) if limits_delta else {}
    if not delta and not presets_delta and not presets_remove:
        raise ResearchPolicyError("RESEARCH_POLICY_CHANGE_EMPTY")
    limits = validate_limits({**head["limits"], **delta})
    presets = dict(head["presets"])
    for preset_id in presets_remove or []:
        if preset_id not in presets:
            raise ResearchPolicyError("RESEARCH_POLICY_PRESET_NOT_FOUND", field=str(preset_id))
        del presets[preset_id]
    if presets_delta:
        for preset_id, body in presets_delta.items():
            presets[str(preset_id)] = validate_preset(str(preset_id), body)
    presets = validate_presets(presets)
    after_semantic = semantic_sha256(limits, presets)
    proposal = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "base_policy_head_sha256": head["policy_head_sha256"],
        "limits": limits,
        "presets": presets,
        "semantic_sha256": after_semantic,
        "reason_code": REASON_OWNER_POLICY_CHANGE,
    }
    proposal["proposal_sha256"] = canonical_sha256(proposal)
    changed = sorted(key for key in LIMIT_FIELDS if limits[key] != head["limits"][key])
    return {
        "action": "RESEARCH_POLICY_PREVIEW",
        "status": NO_CHANGE if after_semantic == head["semantic_sha256"] else "PROPOSED",
        "applies_to": "NEW_SCOPES_ONLY",
        "before": {"source": head["source"], "limits": head["limits"], "preset_ids": sorted(head["presets"]), "semantic_sha256": head["semantic_sha256"]},
        "after": {"limits": limits, "preset_ids": sorted(presets), "semantic_sha256": after_semantic},
        "changed_limits": {key: {"from": head["limits"][key], "to": limits[key]} for key in changed},
        "proposal": proposal,
        "proposal_sha256": proposal["proposal_sha256"],
        "expected_policy_head_sha256": head["policy_head_sha256"],
        **_claim_boundary("POLICY"),
        "next_action": "AUTHORIZED_APPLY" if after_semantic != head["semantic_sha256"] else "READ_ACTIVE_POLICY",
        "writes": {"research_store": 0},
        "market_values_read": 0,
    }


def _verify_proposal(proposal: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    expected = dict(proposal)
    observed = expected.pop("proposal_sha256", None)
    if canonical_sha256(expected) != observed:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID", field="proposal_sha256")
    if expected.get("reason_code") != reason:
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID", field="reason_code")
    expected["proposal_sha256"] = observed
    return expected


def apply_policy_change(
    store: Any,
    *,
    proposal: Mapping[str, Any],
    confirm_append_only: bool,
    clock: Clock | None = None,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise ResearchPolicyError("RESEARCH_POLICY_CONFIRM_REQUIRED")
    checked = _verify_proposal(proposal, reason=REASON_OWNER_POLICY_CHANGE)
    limits = validate_limits(checked.get("limits") or {})
    presets = validate_presets(checked.get("presets") or {})
    if checked.get("semantic_sha256") != semantic_sha256(limits, presets):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID", field="semantic_sha256")
    records = load_policy_records(store)
    for record in records:
        if record.get("proposal_sha256") == checked["proposal_sha256"]:
            return {
                "action": "RESEARCH_POLICY_APPLY",
                "status": ALREADY_APPLIED,
                "appended": False,
                "limits": limits,
                "preset_ids": sorted(presets),
                "semantic_sha256": checked["semantic_sha256"],
                "policy_head_sha256": str(record["policy_artifact_sha256"]),
                "policy_sequence": int(record.get("policy_sequence") or 0),
                "applies_to": "NEW_SCOPES_ONLY",
                **_claim_boundary("POLICY"),
                "writes": {"research_store": 0},
            }
    head = effective_policy(store)
    if checked.get("base_policy_head_sha256") != head["policy_head_sha256"]:
        raise ResearchPolicyError("RESEARCH_POLICY_PREVIEW_STALE", current_policy_head_sha256=head["policy_head_sha256"])
    if head["semantic_sha256"] == checked["semantic_sha256"]:
        return {
            "action": "RESEARCH_POLICY_APPLY",
            "status": NO_CHANGE,
            "appended": False,
            "limits": head["limits"],
            "preset_ids": sorted(head["presets"]),
            "semantic_sha256": head["semantic_sha256"],
            "policy_head_sha256": head["policy_head_sha256"],
            "applies_to": "NEW_SCOPES_ONLY",
            **_claim_boundary("POLICY"),
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
        "semantic_sha256": checked["semantic_sha256"],
        "proposal_sha256": checked["proposal_sha256"],
        "reason_code": REASON_OWNER_POLICY_CHANGE,
        "non_claims": [
            "NOT_A_SCIENTIFIC_LOOK",
            "NOT_STRATEGY_PROMOTION",
            "NEW_SCOPES_ONLY",
            "DOES_NOT_MOVE_A_FROZEN_SCOPE",
        ],
    }

    def _still_current() -> None:
        if effective_policy(store)["policy_head_sha256"] != head["policy_head_sha256"]:
            raise ResearchPolicyError("RESEARCH_POLICY_PREVIEW_STALE")

    artifact = _append_with_busy_retry(
        store, recheck=_still_current, kind=ARTIFACT_KIND, body=body, record_prefix="HFIC-ART-RPOL", clock=clock
    )
    return {
        "action": "RESEARCH_POLICY_APPLY",
        "status": APPENDED,
        "appended": True,
        "limits": limits,
        "preset_ids": sorted(presets),
        "semantic_sha256": checked["semantic_sha256"],
        "policy_head_sha256": artifact["policy_artifact_sha256"],
        "policy_sequence": sequence,
        "created_at": artifact["created_at"],
        "applies_to": "NEW_SCOPES_ONLY",
        **_claim_boundary("POLICY"),
        "writes": {"research_store": 1},
    }


# --------------------------------------------------------------------------
# Frozen scope snapshots and the shared effective-limits resolver.
# --------------------------------------------------------------------------


def read_scope_snapshot(store: Any, scope_key: str) -> dict[str, Any] | None:
    scope_kind(scope_key)
    rows = [item for item in _iter_artifacts(store, SNAPSHOT_KIND) if item.get("scope_key") == scope_key]
    if not rows:
        return None
    return _public(min(rows, key=lambda item: str(item.get("_recorded_at") or "")))


def read_run_snapshot(store: Any, journal_scope: str) -> dict[str, Any] | None:
    return read_scope_snapshot(store, journal_scope)


def read_scope_extensions(store: Any, scope_key: str) -> list[dict[str, Any]]:
    scope_kind(scope_key)
    rows = [item for item in _iter_artifacts(store, EXTENSION_KIND) if item.get("scope_key") == scope_key]
    rows.sort(key=lambda item: int(item.get("extension_sequence") or 0))
    for index, row in enumerate(rows, start=1):
        if int(row.get("extension_sequence") or 0) != index:
            raise ResearchPolicyError("RESEARCH_POLICY_CHAIN_CORRUPT", kind=EXTENSION_KIND, sequence=index)
    return [_public(row) for row in rows]


def read_run_extensions(store: Any, journal_scope: str) -> list[dict[str, Any]]:
    return read_scope_extensions(store, journal_scope)


def _limits_of(snapshot: Mapping[str, Any], extensions: list[dict[str, Any]]) -> dict[str, int]:
    limits = dict(validate_limits(snapshot["limits"]))
    for extension in extensions:
        limits.update(extension["limits_delta"])
    return validate_limits(limits)


def limits_for_frozen_run(store: Any, scope_key: str) -> dict[str, int]:
    """Frozen limits of one scope. A scope never frozen reads the shipped defaults (legacy)."""

    snapshot = read_scope_snapshot(store, scope_key)
    if snapshot is None:
        return dict(DEFAULT_LIMITS)
    return _limits_of(snapshot, read_scope_extensions(store, scope_key))


def limits_or_defaults(store: Any, scope_key: object) -> dict[str, int]:
    """Frozen limits when the key names a scope; the shipped defaults for no store or a non-key.

    A corrupt record is never swallowed: only an absent store or a value that is
    not a scope key reads the defaults.
    """

    if store is None or not isinstance(scope_key, str):
        return dict(DEFAULT_LIMITS)
    try:
        scope_kind(scope_key)
    except ResearchPolicyError:
        return dict(DEFAULT_LIMITS)
    return limits_for_frozen_run(store, scope_key)


def resolve_scope_limits(store: Any, scope_key: str, *, has_history: bool = False) -> dict[str, Any]:
    """Read-only: what this scope uses now, or exactly what a first touch would freeze."""

    snapshot = read_scope_snapshot(store, scope_key)
    extensions = read_scope_extensions(store, scope_key) if snapshot is not None else []
    if snapshot is not None:
        return {
            "scope_key": scope_key,
            "scope_kind": scope_kind(scope_key),
            "frozen": True,
            "source": str(snapshot.get("source") or SOURCE_STORE),
            "freeze_basis": snapshot.get("freeze_basis"),
            "limits": _limits_of(snapshot, extensions),
            "frozen_limits": dict(snapshot["limits"]),
            "extension_count": len(extensions),
            "policy_head_sha256": snapshot.get("policy_head_sha256"),
            "policy_semantic_sha256": snapshot.get("policy_semantic_sha256"),
        }
    if has_history:
        return {
            "scope_key": scope_key,
            "scope_kind": scope_kind(scope_key),
            "frozen": False,
            "source": SOURCE_LEGACY,
            "would_freeze_basis": BASIS_LEGACY_DEFAULTS,
            "limits": dict(DEFAULT_LIMITS),
            "extension_count": 0,
        }
    active = effective_policy(store)
    return {
        "scope_key": scope_key,
        "scope_kind": scope_kind(scope_key),
        "frozen": False,
        "source": active["source"],
        "would_freeze_basis": BASIS_ACTIVE_POLICY,
        "limits": dict(active["limits"]),
        "extension_count": 0,
        "policy_head_sha256": active["policy_head_sha256"],
        "policy_semantic_sha256": active["semantic_sha256"],
    }


def pool_limits_read_only(store: Any, market_evidence_epoch_sha256: object, sessions: Any = ()) -> dict[str, int]:
    """AUTO/distinct-focus pool of one epoch for a read-only caller; never writes.

    An epoch with no frozen pool reports exactly what its first touch would
    freeze: the active policy for a new epoch, the shipped defaults for an epoch
    that already has sessions.
    """

    try:
        scope = epoch_scope_key(str(market_evidence_epoch_sha256))
    except ResearchPolicyError:
        return dict(DEFAULT_LIMITS)
    has_history = any(
        isinstance(item, Mapping)
        and market_evidence_epoch_sha256 in (item.get("market_evidence_epoch_sha256"), item.get("evidence_epoch_sha256"))
        for item in (sessions or [])
    )
    return resolve_scope_limits(store, scope, has_history=has_history)["limits"]


def snapshot_for_new_run(store: Any) -> dict[str, Any]:
    """The limits a brand-new scope would freeze right now. Reads no values."""

    head = effective_policy(store)
    return {"limits": head["limits"], "policy_head_sha256": head["policy_head_sha256"], "policy_semantic_sha256": head["semantic_sha256"]}


def ensure_scope_snapshot(
    store: Any, scope_key: str, *, has_history: bool = False, clock: Clock | None = None
) -> dict[str, Any]:
    """Idempotently freeze one scope on its first touch through a write path.

    A scope that already has history (it pre-dates this runtime) freezes at the
    shipped defaults. A new scope freezes at the active policy. First writer
    wins: a benign race converges on whichever row actually committed.
    """

    kind = scope_kind(scope_key)
    existing = read_scope_snapshot(store, scope_key)
    if existing is not None:
        return existing
    active = effective_policy(store)
    if has_history:
        limits, source, basis = dict(DEFAULT_LIMITS), SOURCE_LEGACY, BASIS_LEGACY_DEFAULTS
    else:
        limits, source, basis = dict(active["limits"]), active["source"], BASIS_ACTIVE_POLICY
    body = {
        "schema": SNAPSHOT_SCHEMA,
        "schema_version": "1.0",
        "scope_key": scope_key,
        "scope_kind": kind,
        "source": source,
        "freeze_basis": basis,
        "limits": limits,
        "presets": active["presets"],
        "policy_head_sha256": active["policy_head_sha256"],
        "policy_semantic_sha256": active["semantic_sha256"],
    }

    def _check() -> None:
        if read_scope_snapshot(store, scope_key) is not None:
            raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_RACE_LOST")

    for attempt in range(40):
        try:
            return _append_artifact(
                store, kind=SNAPSHOT_KIND, body=body, record_prefix="HFIC-ART-RPSNAP", before_commit=_check, clock=clock
            )
        except ResearchPolicyError as exc:
            if exc.code != "RESEARCH_POLICY_RUN_SNAPSHOT_RACE_LOST":
                raise
            winner = read_scope_snapshot(store, scope_key)
            if winner is not None:
                return winner
        except ResearchStoreError as exc:
            if getattr(exc, "code", str(exc)) != "WRITER_BUSY":
                raise ResearchPolicyError(str(getattr(exc, "code", exc))) from exc
            winner = read_scope_snapshot(store, scope_key)
            if winner is not None:
                return winner
        if attempt < 39:
            time.sleep(0.05)
    raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_RACE_UNRESOLVED")


def ensure_run_snapshot(store: Any, scope_key: str, *, has_history: bool = False, clock: Clock | None = None) -> dict[str, Any]:
    return ensure_scope_snapshot(store, scope_key, has_history=has_history, clock=clock)


def ensure_epoch_snapshot(
    store: Any, market_evidence_epoch_sha256: str, *, has_history: bool = False, clock: Clock | None = None
) -> dict[str, Any]:
    return ensure_scope_snapshot(store, epoch_scope_key(market_evidence_epoch_sha256), has_history=has_history, clock=clock)


def epoch_limits(store: Any, market_evidence_epoch_sha256: str) -> dict[str, int]:
    """Frozen AUTO/distinct-focus pool of one market epoch (read-only)."""

    return limits_for_frozen_run(store, epoch_scope_key(market_evidence_epoch_sha256))


# --------------------------------------------------------------------------
# Explicit extensions of one frozen scope. Append-only; never reset spend.
# --------------------------------------------------------------------------


def propose_run_extension(
    store: Any,
    *,
    scope_key: str,
    parent_operation_sha256: str,
    limits_delta: Mapping[str, Any],
) -> dict[str, Any]:
    kind = scope_kind(scope_key)
    if not isinstance(parent_operation_sha256, str) or not _SHA64_RE.match(parent_operation_sha256):
        raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_BINDING_INVALID", field="parent_operation_sha256")
    snapshot = read_scope_snapshot(store, scope_key)
    if snapshot is None:
        raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_MISSING", scope_key=scope_key)
    extensions = read_scope_extensions(store, scope_key)
    before = _limits_of(snapshot, extensions)
    cleaned = validate_delta(limits_delta, allowed=scope_fields(scope_key))
    resulting = validate_limits({**before, **cleaned})
    proposal = {
        "schema": EXTENSION_SCHEMA,
        "schema_version": "1.0",
        "scope_key": scope_key,
        "scope_kind": kind,
        "parent_operation_sha256": parent_operation_sha256,
        "base_extension_sequence": len(extensions),
        "limits_delta": cleaned,
        "before_limits": before,
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
    checked = _verify_proposal(proposal, reason=REASON_OWNER_EXTENSION)
    scope_key = str(checked.get("scope_key") or "")
    scope_kind(scope_key)
    snapshot = read_scope_snapshot(store, scope_key)
    if snapshot is None:
        raise ResearchPolicyError("RESEARCH_POLICY_RUN_SNAPSHOT_MISSING", scope_key=scope_key)
    extensions = read_scope_extensions(store, scope_key)
    for extension in extensions:
        if extension.get("proposal_sha256") == checked["proposal_sha256"]:
            return {
                "action": "RESEARCH_POLICY_EXTENSION_APPLY",
                "status": ALREADY_APPLIED,
                "scope_key": scope_key,
                "extension_sequence": int(extension["extension_sequence"]),
                "resulting_limits": extension["resulting_limits"],
                **_claim_boundary("EXTENSION"),
                "writes": {"research_store": 0},
            }
    base_sequence = checked.get("base_extension_sequence")
    if isinstance(base_sequence, bool) or not isinstance(base_sequence, int) or base_sequence != len(extensions):
        raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_STALE", current_extension_sequence=len(extensions))
    before = _limits_of(snapshot, extensions)
    cleaned = validate_delta(checked.get("limits_delta") or {}, allowed=scope_fields(scope_key))
    resulting = validate_limits({**before, **cleaned})
    if resulting != checked.get("resulting_limits") or before != checked.get("before_limits"):
        raise ResearchPolicyError("RESEARCH_POLICY_INVALID", field="resulting_limits")
    sequence = len(extensions) + 1
    body = {**{key: value for key, value in checked.items()}, "extension_sequence": sequence}

    def _check() -> None:
        if len(read_scope_extensions(store, scope_key)) != len(extensions):
            raise ResearchPolicyError("RESEARCH_POLICY_EXTENSION_STALE")

    artifact = _append_with_busy_retry(
        store, recheck=_check, kind=EXTENSION_KIND, body=body, record_prefix="HFIC-ART-RPEXT", clock=clock
    )
    return {
        "action": "RESEARCH_POLICY_EXTENSION_APPLY",
        "status": APPENDED,
        "scope_key": scope_key,
        "extension_sequence": sequence,
        "before_limits": before,
        "resulting_limits": resulting,
        "created_at": artifact["created_at"],
        **_claim_boundary("EXTENSION"),
        "writes": {"research_store": 1},
    }


# --------------------------------------------------------------------------
# Owner readout: what applies to new scopes versus what a scope is frozen at.
# --------------------------------------------------------------------------


def policy_readout(store: Any, *, scope_keys: list[str] | None = None, has_history: dict[str, bool] | None = None) -> dict[str, Any]:
    active = effective_policy(store)
    out: dict[str, Any] = {
        "active_policy_for_new_runs": {
            "source": active["source"],
            "limits": active["limits"],
            "preset_ids": sorted(active["presets"]),
            "semantic_sha256": active["semantic_sha256"],
            "policy_head_sha256": active["policy_head_sha256"],
            "policy_sequence": active["policy_sequence"],
        },
        "shipped_defaults": dict(DEFAULT_LIMITS),
        "frozen_policy": {},
    }
    for scope_key in scope_keys or []:
        resolved = resolve_scope_limits(store, scope_key, has_history=bool((has_history or {}).get(scope_key)))
        fields = scope_fields(scope_key)
        out["frozen_policy"][scope_key] = {
            **{key: value for key, value in resolved.items() if key != "frozen_limits"},
            "differs": any(resolved["limits"][key] != active["limits"][key] for key in fields),
        }
    return out
