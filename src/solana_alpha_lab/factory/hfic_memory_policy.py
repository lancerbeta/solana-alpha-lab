"""Append-only HFIC search-memory eligibility policy.

Quarantine changes only HFIC_SEARCH_MEMORY_ELIGIBILITY. Historical records stay
immutable. Non-HFIC hypothesis versions are never hidden by this policy.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
)
from solana_alpha_lab.factory.hfic_identity import normalize_text
from solana_alpha_lab.factory.hfic_prior_memory import prior_memory_bounds
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


SCHEMA = "smial.hfic-search-memory-policy"
SCHEMA_VERSION = "1.0"
POLICY_ARTIFACT_KIND = "HFIC_SEARCH_MEMORY_POLICY"
GENESIS_POLICY_SHA256 = "0" * 64
REASON_OWNER_CALIBRATION_RESET = "OWNER_CALIBRATION_RESET"
REASON_OWNER_MEMORY_RESTORE = "OWNER_MEMORY_RESTORE"
REASON_PRE_CAPABILITY_BASELINE = "PRE_CAPABILITY_BASELINE_CALIBRATION_RESET"
ALLOWED_REASONS = frozenset(
    {
        REASON_OWNER_CALIBRATION_RESET,
        REASON_OWNER_MEMORY_RESTORE,
        REASON_PRE_CAPABILITY_BASELINE,
    }
)
PRODUCER = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"
NO_CHANGE = "NO_CHANGE"
REPLAY_IDENTICAL = "REPLAY_IDENTICAL"
APPENDED = "APPENDED"

_PENDING_PHASES = frozenset(
    {
        "PREFLIGHT_PROVEN",
        "DRAFT_VALIDATED",
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        "RUNNER_UP_AWAITING_CRITIC",
        "REVISION_REQUIRED",
        "AWAITING_CLASSIFICATION",
        "CRITIC_RESULT_READY",
        "RUNNER_UP_REVISION_REQUIRED",
    }
)


class HficMemoryPolicyError(ValueError):
    """Fail-closed HFIC search-memory policy error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _normalize_session_ids(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
        token = item.strip()
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    out.sort()
    return out


def memory_eligibility_sha256(quarantined_session_ids: Sequence[str]) -> str:
    return canonical_sha256(
        {"quarantined_session_ids": _normalize_session_ids(quarantined_session_ids)}
    )


GENESIS_MEMORY_ELIGIBILITY_SHA256 = canonical_sha256({"quarantined_session_ids": []})


def search_identity_sha256(
    epoch: str,
    owner_focus: str,
    prompt_version: str,
    memory_eligibility: str | None = None,
    evidence_surface_mode: str | None = None,
) -> str:
    eligibility = memory_eligibility or GENESIS_MEMORY_ELIGIBILITY_SHA256
    focus = hashlib.sha256(normalize_text(owner_focus).encode("utf-8")).hexdigest()
    if eligibility == GENESIS_MEMORY_ELIGIBILITY_SHA256:
        payload = f"{epoch}{focus}{prompt_version}"
    else:
        payload = f"{epoch}{focus}{prompt_version}{eligibility}"
    if evidence_surface_mode:
        payload = f"{payload}{evidence_surface_mode}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def session_memory_eligibility(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return GENESIS_MEMORY_ELIGIBILITY_SHA256
    raw = item.get("memory_eligibility_sha256")
    if isinstance(raw, str) and len(raw) == 64:
        return raw
    return GENESIS_MEMORY_ELIGIBILITY_SHA256


def load_policy_records(store: Any) -> list[dict[str, Any]]:
    found: list[tuple[int, str, dict[str, Any]]] = []
    seen_seq: dict[int, str] = {}
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        payload = _payload(record)
        if str(kind) != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        if payload.get("artifact_kind") != POLICY_ARTIFACT_KIND:
            continue
        body = _policy_body(payload)
        seq = int(body["policy_sequence"])
        sha = str(body["policy_sha256"])
        previous = seen_seq.get(seq)
        if previous is not None and previous != sha:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_FORK")
        seen_seq[seq] = sha
        found.append((seq, str(getattr(record, "record_id", "") or ""), body))
    found.sort(key=lambda item: (item[0], item[1]))
    if not found:
        return []
    expected_previous = GENESIS_POLICY_SHA256
    expected_seq = 1
    chain: list[dict[str, Any]] = []
    for seq, _record_id, body in found:
        if seq != expected_seq:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
        if str(body.get("previous_policy_sha256") or "") != expected_previous:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
        recomputed = _policy_sha256(_unsigned(body))
        if recomputed != str(body.get("policy_sha256") or ""):
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
        expected = memory_eligibility_sha256(
            list(body.get("quarantined_session_ids") or [])
        )
        if expected != str(body.get("memory_eligibility_sha256") or ""):
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
        chain.append(body)
        expected_previous = str(body["policy_sha256"])
        expected_seq += 1
    return chain


def genesis_policy_head() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "policy_id": "HFIC-MEMPOL-GENESIS",
        "policy_sequence": 0,
        "previous_policy_sha256": GENESIS_POLICY_SHA256,
        "quarantined_session_ids": [],
        "reason_code": None,
        "created_at": None,
        "producer_git_sha": None,
        "policy_sha256": GENESIS_POLICY_SHA256,
        "memory_eligibility_sha256": GENESIS_MEMORY_ELIGIBILITY_SHA256,
        "authority": _authority_zero(),
        "non_claims": [
            "NOT_SCIENTIFIC_REJECTION",
            "NOT_DELETION",
            "NOT_SUPERSESSION",
            "HFIC_SEARCH_MEMORY_ELIGIBILITY_ONLY",
        ],
        "genesis": True,
    }


def effective_policy(store: Any | None) -> dict[str, Any]:
    if store is None:
        return genesis_policy_head()
    chain = load_policy_records(store)
    if not chain:
        return genesis_policy_head()
    return dict(chain[-1])


def quarantined_session_ids(store: Any | None) -> list[str]:
    return list(effective_policy(store).get("quarantined_session_ids") or [])


def hypothesis_search_eligible(
    payload: Mapping[str, Any],
    quarantined: Sequence[str],
) -> bool:
    protocol = payload.get("hfic_protocol")
    if not isinstance(protocol, str) or not protocol:
        return True
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return True
    return session_id not in set(quarantined)


def iter_search_memory_hypothesis_payloads(store: Any | None) -> list[dict[str, Any]]:
    if store is None:
        return []
    blocked = set(quarantined_session_ids(store))
    latest: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if str(kind) != "HYPOTHESIS_VERSION":
            continue
        payload = _payload(record)
        if not hypothesis_search_eligible(payload, blocked):
            continue
        hyp_id = str(
            payload.get("hypothesis_version_id")
            or getattr(record, "hypothesis_version_id", None)
            or record.entity_id
            or ""
        )
        if not hyp_id:
            continue
        key = (
            str(getattr(record, "effective_at", "") or ""),
            str(getattr(record, "record_id", "") or ""),
        )
        previous = latest.get(hyp_id)
        if previous is None or key >= previous[0]:
            latest[hyp_id] = (key, payload)
    return [latest[item][1] for item in sorted(latest)]


def eligible_counts(store: Any | None) -> dict[str, int]:
    hfic = 0
    non_hfic = 0
    for payload in iter_search_memory_hypothesis_payloads(store):
        protocol = payload.get("hfic_protocol")
        if isinstance(protocol, str) and protocol:
            hfic += 1
        else:
            non_hfic += 1
    return {
        "eligible_hfic_hv_count": hfic,
        "eligible_non_hfic_hv_count": non_hfic,
        "total_eligible_prior_memory_count": hfic + non_hfic,
    }


def quarantined_hfic_hv_count(store: Any | None) -> int:
    if store is None:
        return 0
    blocked = set(quarantined_session_ids(store))
    seen: set[str] = set()
    count = 0
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if str(kind) != "HYPOTHESIS_VERSION":
            continue
        payload = _payload(record)
        protocol = payload.get("hfic_protocol")
        if not isinstance(protocol, str) or not protocol:
            continue
        hyp_id = str(payload.get("hypothesis_version_id") or record.entity_id or "")
        if not hyp_id or hyp_id in seen:
            continue
        seen.add(hyp_id)
        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id in blocked:
            count += 1
    return count


def capacity_status(
    store: Any | None,
    *,
    repo_root: Any | None = None,
) -> dict[str, Any]:
    counts = eligible_counts(store)
    max_records, _max_bytes = prior_memory_bounds(repo_root)
    total = int(counts["total_eligible_prior_memory_count"])
    headroom = max_records - total
    return {
        **counts,
        "max_records": max_records,
        "headroom": headroom,
        "fresh_freeze_capacity": STATUS_PASS if headroom >= 0 else STATUS_BLOCKED,
    }


def memory_policy_status(
    store: Any | None,
    *,
    repo_root: Any | None = None,
) -> dict[str, Any]:
    head = effective_policy(store)
    capacity = capacity_status(store, repo_root=repo_root)
    return {
        "action": "MEMORY_POLICY_STATUS",
        "policy_head_sha256": head["policy_sha256"],
        "memory_eligibility_sha256": head["memory_eligibility_sha256"],
        "policy_sequence": head["policy_sequence"],
        "genesis": bool(head.get("genesis")),
        "quarantined_session_ids": list(head.get("quarantined_session_ids") or []),
        "quarantined_session_count": len(list(head.get("quarantined_session_ids") or [])),
        "quarantined_hfic_hv_count": quarantined_hfic_hv_count(store),
        **capacity,
        "evidence_epoch_binding": "HFIC_MEMORY_POLICY_EXCLUDED",
        "authority": _authority_zero(),
        "non_claims": list(head.get("non_claims") or []),
    }


def preview_memory_policy(
    store: Any,
    *,
    repo_root: Any,
    quarantine_session_ids: Sequence[str] | None = None,
    restore_session_ids: Sequence[str] | None = None,
    quarantine_all_current_hfic: bool = False,
    reason_code: str = REASON_OWNER_CALIBRATION_RESET,
) -> dict[str, Any]:
    head = effective_policy(store)
    before_ids = list(head.get("quarantined_session_ids") or [])
    after_ids = set(before_ids)
    exact_all: list[str] = []
    if quarantine_all_current_hfic:
        exact_all = _current_hfic_session_ids(store)
        _deny_pending(store, exact_all)
        after_ids.update(exact_all)
    added = _normalize_session_ids(quarantine_session_ids or [])
    removed = _normalize_session_ids(restore_session_ids or [])
    if added:
        _assert_sessions_exist(store, added)
        _deny_pending(store, added)
        after_ids.update(added)
    if removed:
        _assert_sessions_exist(store, removed)
        after_ids.difference_update(removed)
    after_list = _normalize_session_ids(sorted(after_ids))
    _deny_pending(store, [item for item in after_list if item not in before_ids])
    before_eligibility = str(head["memory_eligibility_sha256"])
    after_eligibility = memory_eligibility_sha256(after_list)
    affected = _affected_hfic_hv_count(store, before_ids, after_list)
    before_capacity = capacity_status(store, repo_root=repo_root)
    after_eligible_hfic = before_capacity["eligible_hfic_hv_count"]
    # Approximate after-capacity from session HV movement without writing.
    after_eligible_hfic = after_eligible_hfic - _hfic_hv_delta(store, before_ids, after_list)
    after_total = after_eligible_hfic + before_capacity["eligible_non_hfic_hv_count"]
    max_records = int(before_capacity["max_records"])
    after_headroom = max_records - after_total
    inventory = store.diagnostics().committed_inventory_sha256
    proposal = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "base_policy_head_sha256": head["policy_sha256"],
        "base_store_inventory_digest": inventory,
        "quarantined_session_ids": after_list,
        "quarantine_all_current_hfic_resolved": exact_all,
        "reason_code": _require_reason(reason_code),
        "memory_eligibility_sha256": after_eligibility,
    }
    proposal["proposal_sha256"] = canonical_sha256(proposal)
    added_ids = [item for item in after_list if item not in before_ids]
    removed_ids = [item for item in before_ids if item not in after_list]
    noop = after_eligibility == before_eligibility
    return {
        "action": "MEMORY_POLICY_PREVIEW",
        "status": NO_CHANGE if noop else "PROPOSED",
        "before_quarantined_session_ids": before_ids,
        "after_quarantined_session_ids": after_list,
        "added_session_ids": added_ids,
        "removed_session_ids": removed_ids,
        "affected_hypothesis_version_count": affected,
        "memory_eligibility_sha256_before": before_eligibility,
        "memory_eligibility_sha256_after": after_eligibility,
        "capacity_before": before_capacity,
        "capacity_after": {
            "eligible_hfic_hv_count": after_eligible_hfic,
            "eligible_non_hfic_hv_count": before_capacity["eligible_non_hfic_hv_count"],
            "total_eligible_prior_memory_count": after_total,
            "max_records": max_records,
            "headroom": after_headroom,
            "fresh_freeze_capacity": STATUS_PASS if after_headroom >= 0 else STATUS_BLOCKED,
        },
        "base_policy_head_sha256": head["policy_sha256"],
        "base_store_inventory_digest": inventory,
        "proposal": proposal,
        "proposal_sha256": proposal["proposal_sha256"],
        "risk_summary": _risk_summary(noop=noop, added=added_ids, removed=removed_ids),
        "authority": _authority_zero(),
    }


def apply_memory_policy(
    store: ResearchStore,
    *,
    repo_root: Any,
    proposal: Mapping[str, Any],
    confirm_append_only: bool,
    clock: Clock | None = None,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_CONFIRM_REQUIRED")
    expected = dict(proposal)
    observed_hash = expected.pop("proposal_sha256", None)
    if canonical_sha256(expected) != observed_hash:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
    head = effective_policy(store)
    inventory = store.diagnostics().committed_inventory_sha256
    if expected.get("base_policy_head_sha256") != head["policy_sha256"]:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_PREVIEW_STALE")
    if expected.get("base_store_inventory_digest") != inventory:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_PREVIEW_STALE")
    after_ids = _normalize_session_ids(list(expected.get("quarantined_session_ids") or []))
    _assert_sessions_exist(store, after_ids)
    _deny_pending(
        store,
        [item for item in after_ids if item not in set(head.get("quarantined_session_ids") or [])],
    )
    after_eligibility = memory_eligibility_sha256(after_ids)
    if after_eligibility != str(expected.get("memory_eligibility_sha256") or ""):
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
    if after_eligibility == str(head["memory_eligibility_sha256"]):
        return {
            "action": "MEMORY_POLICY_APPLY",
            "status": NO_CHANGE,
            "policy_head_sha256": head["policy_sha256"],
            "memory_eligibility_sha256": head["memory_eligibility_sha256"],
            "quarantined_session_ids": list(head.get("quarantined_session_ids") or []),
            "appended": False,
            "authority": _authority_zero(),
        }
    try:
        now = capture_stage_time(clock)
        created_at = render_canonical_utc(now)
    except HficClockError as exc:
        raise HficMemoryPolicyError(str(exc)) from exc
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    git = repository_git_snapshot(repo_root)
    sequence = int(head.get("policy_sequence") or 0) + 1
    unsigned = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "policy_id": f"HFIC-MEMPOL-{sequence:04d}",
        "policy_sequence": sequence,
        "previous_policy_sha256": head["policy_sha256"],
        "quarantined_session_ids": after_ids,
        "reason_code": _require_reason(str(expected.get("reason_code") or "")),
        "created_at": created_at,
        "producer_git_sha": git.head_sha.lower(),
        "memory_eligibility_sha256": after_eligibility,
        "authority": _authority_zero(),
        "non_claims": [
            "NOT_SCIENTIFIC_REJECTION",
            "NOT_DELETION",
            "NOT_SUPERSESSION",
            "HFIC_SEARCH_MEMORY_ELIGIBILITY_ONLY",
        ],
    }
    policy_sha = _policy_sha256(unsigned)
    body = {**unsigned, "policy_sha256": policy_sha}
    record_id = f"HFIC-MEMPOL-{policy_sha[:16].upper()}"
    transaction_id = f"RESEARCH-TXN-HFIC-MEMPOL-{sequence:04d}"
    artifact = {
        "research_artifact_id": record_id,
        "session_id": None,
        "hfic_protocol": "HFIC-MEMORY-POLICY-V1",
        "artifact_kind": POLICY_ARTIFACT_KIND,
        **body,
    }
    encoded = json.dumps(
        artifact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=encoded,
        payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=PRODUCER,
        producer_git_sha=git.head_sha.lower(),
        created_at=now,
    )
    try:
        store.append([event], transaction_id=transaction_id)
    except ResearchStoreError as exc:
        raise HficMemoryPolicyError(str(exc)) from exc
    store.rebuild_projection()
    return {
        "action": "MEMORY_POLICY_APPLY",
        "status": APPENDED,
        "policy_head_sha256": policy_sha,
        "memory_eligibility_sha256": after_eligibility,
        "policy_sequence": sequence,
        "quarantined_session_ids": after_ids,
        "appended": True,
        "created_at": created_at,
        "authority": _authority_zero(),
    }


def _require_reason(reason: str) -> str:
    if reason not in ALLOWED_REASONS:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
    return reason


def _payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", "") or ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _policy_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "schema",
        "schema_version",
        "policy_id",
        "policy_sequence",
        "previous_policy_sha256",
        "quarantined_session_ids",
        "reason_code",
        "created_at",
        "producer_git_sha",
        "policy_sha256",
        "memory_eligibility_sha256",
    )
    for key in required:
        if key not in payload:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
    if payload.get("schema") != SCHEMA or payload.get("schema_version") != SCHEMA_VERSION:
        raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_INVALID")
    return {key: payload[key] for key in (*required, "authority", "non_claims") if key in payload}


def _unsigned(body: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key != "policy_sha256"}


def _policy_sha256(unsigned: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(unsigned))


def _authority_zero() -> dict[str, int]:
    return {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }


def _session_index(store: Any) -> dict[str, dict[str, Any]]:
    from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

    return {str(item["session_id"]): item for item in list_hfic_sessions(store)}


def _current_hfic_session_ids(store: Any) -> list[str]:
    return _normalize_session_ids(sorted(_session_index(store)))


def _assert_sessions_exist(store: Any, session_ids: Sequence[str]) -> None:
    known = _session_index(store)
    for session_id in session_ids:
        if session_id not in known:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_SESSION_UNKNOWN")


def _deny_pending(store: Any, session_ids: Sequence[str]) -> None:
    known = _session_index(store)
    for session_id in session_ids:
        item = known.get(session_id)
        if item is None:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_SESSION_UNKNOWN")
        state = str(item.get("session_state") or "")
        if state in _PENDING_PHASES:
            raise HficMemoryPolicyError("HFIC_MEMORY_POLICY_PENDING_SESSION")


def _affected_hfic_hv_count(
    store: Any,
    before_ids: Sequence[str],
    after_ids: Sequence[str],
) -> int:
    changed = set(before_ids) ^ set(after_ids)
    return _count_hfic_hv_in_sessions(store, changed)


def _hfic_hv_delta(
    store: Any,
    before_ids: Sequence[str],
    after_ids: Sequence[str],
) -> int:
    added = set(after_ids) - set(before_ids)
    removed = set(before_ids) - set(after_ids)
    return _count_hfic_hv_in_sessions(store, added) - _count_hfic_hv_in_sessions(
        store, removed
    )


def _count_hfic_hv_in_sessions(store: Any, session_ids: Sequence[str]) -> int:
    wanted = set(session_ids)
    if not wanted:
        return 0
    seen: set[str] = set()
    count = 0
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if str(kind) != "HYPOTHESIS_VERSION":
            continue
        payload = _payload(record)
        if not isinstance(payload.get("hfic_protocol"), str) or not payload.get("hfic_protocol"):
            continue
        session_id = payload.get("session_id")
        if session_id not in wanted:
            continue
        hyp_id = str(payload.get("hypothesis_version_id") or record.entity_id or "")
        if not hyp_id or hyp_id in seen:
            continue
        seen.add(hyp_id)
        count += 1
    return count


def _risk_summary(
    *,
    noop: bool,
    added: Sequence[str],
    removed: Sequence[str],
) -> str:
    if noop:
        return "NO_EFFECTIVE_SET_CHANGE"
    bits = []
    if added:
        bits.append(f"quarantine {len(added)} session(s)")
    if removed:
        bits.append(f"restore {len(removed)} session(s)")
    bits.append("historical bytes unchanged")
    bits.append("non-HFIC memory unchanged")
    bits.append("evidence_epoch unchanged")
    return "; ".join(bits)


__all__ = [
    "APPENDED",
    "GENESIS_MEMORY_ELIGIBILITY_SHA256",
    "GENESIS_POLICY_SHA256",
    "HficMemoryPolicyError",
    "NO_CHANGE",
    "POLICY_ARTIFACT_KIND",
    "REASON_OWNER_CALIBRATION_RESET",
    "REASON_OWNER_MEMORY_RESTORE",
    "REASON_PRE_CAPABILITY_BASELINE",
    "apply_memory_policy",
    "capacity_status",
    "effective_policy",
    "eligible_counts",
    "genesis_policy_head",
    "hypothesis_search_eligible",
    "iter_search_memory_hypothesis_payloads",
    "load_policy_records",
    "memory_eligibility_sha256",
    "memory_policy_status",
    "preview_memory_policy",
    "quarantined_session_ids",
    "search_identity_sha256",
    "session_memory_eligibility",
]
