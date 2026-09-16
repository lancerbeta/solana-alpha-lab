"""Bounded historical prior-memory snapshot for current Critic packet 1.3."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256


SCHEMA = "smial.hfic-prior-memory-snapshot"
SCHEMA_VERSION = "1.0"
DEFAULT_MAX_RECORDS = 64
DEFAULT_MAX_BYTES = 65536
CONFIG_RELATIVE = "configs/hypothesis_forge_independent_critic_v1.yaml"

MEMORY_HARD_CLOSE = "HARD_CLOSE"
MEMORY_PARK = "PARK"
MEMORY_NOT_SELECTED = "NOT_SELECTED_IN_SESSION"
MEMORY_AMBIGUOUS = "AMBIGUOUS"
MEMORY_HISTORICAL = "HISTORICAL"
MEMORY_STATUSES = (
    MEMORY_HARD_CLOSE,
    MEMORY_PARK,
    MEMORY_NOT_SELECTED,
    MEMORY_AMBIGUOUS,
    MEMORY_HISTORICAL,
)

_CAPSULE_FIELDS = (
    "claim",
    "mechanism",
    "actor_counterparty",
    "population",
    "decision_timestamp",
    "primary_x_family",
    "primary_y",
    "horizon_notional",
    "negative_control",
    "cheapest_falsifier",
)


class PriorMemoryCapacityError(ValueError):
    """Eligible prior memory cannot be represented inside the declared bound."""

    def __init__(
        self,
        *,
        eligible_count: int,
        emitted_count: int,
        payload_bytes: int,
        max_records: int,
        max_bytes: int,
    ) -> None:
        self.code = "PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED"
        self.eligible_count = eligible_count
        self.emitted_count = emitted_count
        self.payload_bytes = payload_bytes
        self.max_records = max_records
        self.max_bytes = max_bytes
        super().__init__(self.code)


class PriorMemoryUnidentifiedError(ValueError):
    """A committed HYPOTHESIS_VERSION cannot be projected without identity."""

    def __init__(self) -> None:
        self.code = "PRIOR_MEMORY_RECORD_UNIDENTIFIED"
        super().__init__(self.code)


def prior_memory_bounds(
    repo_root: Path | str | None = None,
    *,
    max_records: int | None = None,
    max_bytes: int | None = None,
) -> tuple[int, int]:
    records = DEFAULT_MAX_RECORDS
    nbytes = DEFAULT_MAX_BYTES
    if repo_root is not None:
        path = Path(repo_root) / CONFIG_RELATIVE
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            block = loaded.get("prior_memory") or {}
            if isinstance(block, Mapping):
                if isinstance(block.get("max_records"), int):
                    records = int(block["max_records"])
                if isinstance(block.get("max_bytes"), int):
                    nbytes = int(block["max_bytes"])
    if max_records is not None:
        records = max_records
    if max_bytes is not None:
        nbytes = max_bytes
    return records, nbytes


def classify_memory_status(
    *,
    decision_kind: str | None,
    reason_code: str | None,
    hfic_protocol: str | None,
) -> str:
    kind = str(decision_kind or "")
    reason = str(reason_code or "")
    if reason == MEMORY_NOT_SELECTED:
        return MEMORY_NOT_SELECTED
    if reason.startswith("PARK_") or reason == "OWNER_PRIORITY_PARK" or kind == "PARK":
        return MEMORY_PARK
    if (
        reason.startswith("KILL_")
        or reason.startswith("CLOSE_")
        or (kind == "REJECT" and reason not in {"", MEMORY_NOT_SELECTED})
    ):
        return MEMORY_HARD_CLOSE
    if not kind and not reason:
        if hfic_protocol:
            return MEMORY_AMBIGUOUS
        return MEMORY_HISTORICAL
    return MEMORY_AMBIGUOUS


def empty_prior_memory_snapshot(
    *,
    store_inventory_digest: str,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    return _finalize_snapshot(
        capsules=[],
        eligible_count=0,
        store_inventory_digest=store_inventory_digest,
        max_records=max_records,
        max_bytes=max_bytes,
    )


# Eligibility is currently every committed HYPOTHESIS_VERSION visible in the
# exact preflight-bound store. A later append-only quarantine/rebase filter may
# drop ids before capsule emission without changing capsule schema or ranker.
def build_prior_memory_snapshot(
    store: Any | None,
    *,
    store_inventory_digest: str,
    repo_root: Path | str | None = None,
    max_records: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    records_bound, bytes_bound = prior_memory_bounds(
        repo_root, max_records=max_records, max_bytes=max_bytes
    )
    digest = str(store_inventory_digest or "")
    if store is None:
        return empty_prior_memory_snapshot(
            store_inventory_digest=digest or "0" * 64,
            max_records=records_bound,
            max_bytes=bytes_bound,
        )
    from solana_alpha_lab.factory.hfic_memory_policy import (
        iter_search_memory_hypothesis_payloads,
    )

    decisions = latest_hypothesis_decisions(store)
    capsules_by_id: dict[str, dict[str, Any]] = {}
    for payload in iter_search_memory_hypothesis_payloads(store):
        hyp_id = str(payload.get("hypothesis_version_id") or "")
        if not hyp_id:
            raise PriorMemoryUnidentifiedError()
        capsules_by_id[hyp_id] = _capsule_from_payload(
            hyp_id, payload, decisions.get(hyp_id)
        )
    capsules = [capsules_by_id[item] for item in sorted(capsules_by_id)]
    eligible = len(capsules)
    if eligible > records_bound:
        raise PriorMemoryCapacityError(
            eligible_count=eligible,
            emitted_count=0,
            payload_bytes=0,
            max_records=records_bound,
            max_bytes=bytes_bound,
        )
    snapshot = _finalize_snapshot(
        capsules=capsules,
        eligible_count=eligible,
        store_inventory_digest=digest,
        max_records=records_bound,
        max_bytes=bytes_bound,
    )
    if snapshot["bytes"] > bytes_bound:
        raise PriorMemoryCapacityError(
            eligible_count=eligible,
            emitted_count=0,
            payload_bytes=int(snapshot["bytes"]),
            max_records=records_bound,
            max_bytes=bytes_bound,
        )
    return snapshot


def _require_hypothesis_payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", "") or ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise PriorMemoryUnidentifiedError() from exc
    if not isinstance(payload, dict):
        raise PriorMemoryUnidentifiedError()
    return payload


def _payload_mapping(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", "") or ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_hypothesis_decisions(store: Any) -> dict[str, dict[str, str]]:
    """Latest DECISION_EVENT disposition per hypothesis_version_id.

    Shared read-only resolver for Critic prior-memory capsules and Forge
    Prompt-A ranked-prior projection. Do not fork a second decision walker.
    """
    latest: dict[str, tuple[tuple[str, str], str, str]] = {}
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "DECISION_EVENT":
            continue
        payload = _payload_mapping(record)
        hyp_id = str(
            payload.get("hypothesis_version_id")
            or getattr(record, "hypothesis_version_id", None)
            or ""
        )
        if not hyp_id:
            continue
        record_id = str(getattr(record, "record_id", "") or "")
        effective = str(getattr(record, "effective_at", "") or "")
        key = (effective, record_id)
        previous = latest.get(hyp_id)
        if previous is None or key >= previous[0]:
            latest[hyp_id] = (
                key,
                str(payload.get("decision_kind") or ""),
                str(payload.get("reason_code") or ""),
            )
    return {
        hyp_id: {"decision_kind": kind, "reason_code": reason}
        for hyp_id, (_key, kind, reason) in latest.items()
    }


def _latest_decisions(store: Any) -> dict[str, dict[str, str]]:
    """Compatibility alias; prefer :func:`latest_hypothesis_decisions`."""
    return latest_hypothesis_decisions(store)


def compact_prior_entry(
    hyp_id: str,
    payload: Mapping[str, Any],
    decision: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Critic / history compact capsule; one identity per eligible prior.

    Prompt A ranked-prior projection uses :func:`compact_forge_prior_entry`.
    Do not silently thin this capsule to solve Forge packet capacity.
    """
    return _capsule_from_payload(hyp_id, payload, decision)


_FORGE_LEGACY_KEEP = (
    "family",
    "primary_question",
    "primary_features",
    "park_terminal",
    "park_hypothesis_verdict",
    "science_disposition",
    "priority_disposition",
    "falsifier",
    "feature_id",
    "frozen_definition_id",
    "baseline",
    "data_semantics",
    "universe",
    "outcome_horizon_seconds",
    "live_PIT_claim",
    "group_id",
    "primary_x",
    "mechanism",
    "claim",
)


_FORGE_SCOPE_KEYS = (
    "population",
    "decision_timestamp",
    "horizon_notional",
    "negative_control",
)


def _forge_requires_scope_axes(
    *,
    memory_status: str | None,
    reason_code: str | None,
) -> bool:
    """HARD_CLOSE / PARK (and KILL_/CLOSE_ reasons) need readable scope axes.

    NOT_SELECTED_IN_SESSION is not a negative scientific verdict and may stay
    thinner when a lean distinguisher already exists.
    """
    status = str(memory_status or "")
    reason = str(reason_code or "")
    if status in {MEMORY_HARD_CLOSE, MEMORY_PARK}:
        return True
    if reason.startswith("KILL_") or reason.startswith("CLOSE_"):
        return True
    if reason.startswith("PARK_") or reason == "OWNER_PRIORITY_PARK":
        return True
    return False


def compact_forge_prior_entry(
    hyp_id: str,
    payload: Mapping[str, Any],
    decision: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Prompt-A search-memory projection; thinner than Critic capsules.

    Retains one-to-one identity, disposition, substantive mechanism/claim,
    X/Y axes, actor/falsifier when present, definition hash for traceability,
    and enough legacy_definition for reopenable parks. Omits Critic/audit
    fields Prompt A does not need (session_id, hfic_protocol).

    Scope axes (population / decision_timestamp / horizon_notional /
    negative_control) are retained for HARD_CLOSE and PARK dispositions so
    Prompt A can tell what was killed from the scope in which it was killed.
    NOT_SELECTED_IN_SESSION may omit them when a lean distinguisher remains;
    they are still retained as fallback when they are the only distinguishers.
    """
    full = _capsule_from_payload(hyp_id, payload, decision)
    out: dict[str, Any] = {
        "hypothesis_version_id": hyp_id,
        "memory_status": full.get("memory_status"),
    }
    for key in (
        "decision_kind",
        "reason_code",
        "park_status",
        "definition_sha256",
        "primary_x_family",
        "primary_y",
        "cheapest_falsifier",
    ):
        value = full.get(key)
        if value not in (None, "", [], {}):
            out[key] = value
    # actor_counterparty is retained only when mechanism/claim text is absent;
    # otherwise the causal role is already carried by the substantive field.
    mechanism = full.get("mechanism")
    claim = full.get("claim")
    if isinstance(mechanism, str) and mechanism.strip():
        out["mechanism"] = mechanism
    elif isinstance(claim, str) and claim.strip():
        out["claim"] = claim
    else:
        actor = full.get("actor_counterparty")
        if actor not in (None, "", [], {}):
            out["actor_counterparty"] = actor
    legacy = full.get("legacy_definition")
    if isinstance(legacy, Mapping) and legacy:
        keep = {
            key: legacy[key]
            for key in _FORGE_LEGACY_KEEP
            if key in legacy and legacy[key] not in (None, "", [], {})
        }
        if keep:
            out["legacy_definition"] = keep
    require_scope = _forge_requires_scope_axes(
        memory_status=str(out.get("memory_status") or "") or None,
        reason_code=str(out.get("reason_code") or "") or None,
    )
    if require_scope or not _forge_entry_has_distinguisher(out):
        for key in _FORGE_SCOPE_KEYS:
            value = full.get(key)
            if value not in (None, "", [], {}):
                out[key] = value
    return out


def _forge_entry_has_distinguisher(entry: Mapping[str, Any]) -> bool:
    for key in (
        "mechanism",
        "claim",
        "actor_counterparty",
        "primary_x_family",
        "primary_y",
        "cheapest_falsifier",
        "legacy_definition",
        *_FORGE_SCOPE_KEYS,
    ):
        value = entry.get(key)
        if isinstance(value, Mapping):
            if value:
                return True
        elif value not in (None, "", [], {}):
            return True
    return False


def _capsule_from_payload(
    hyp_id: str,
    payload: Mapping[str, Any],
    decision: Mapping[str, str] | None,
) -> dict[str, Any]:
    protocol = payload.get("hfic_protocol")
    protocol_text = str(protocol) if isinstance(protocol, str) and protocol else None
    decision_kind = decision.get("decision_kind") if decision else None
    reason_code = decision.get("reason_code") if decision else None
    falsifier = payload.get("cheapest_falsifier") or payload.get("falsifier") or ""
    capsule: dict[str, Any] = {
        "hypothesis_version_id": hyp_id,
        "session_id": str(payload.get("session_id") or "") or None,
        "hfic_protocol": protocol_text,
        "definition_sha256": str(payload.get("definition_sha256") or "") or None,
        "memory_status": classify_memory_status(
            decision_kind=decision_kind,
            reason_code=reason_code,
            hfic_protocol=protocol_text,
        ),
        "decision_kind": decision_kind or None,
        "reason_code": reason_code or None,
    }
    for field in _CAPSULE_FIELDS:
        if field == "cheapest_falsifier":
            value = str(falsifier or "")
        elif field == "primary_x_family":
            value = str(payload.get("primary_x_family") or payload.get("primary_x") or "")
        else:
            value = str(payload.get(field) or "")
        capsule[field] = value or None
    legacy = payload.get("legacy_definition")
    if isinstance(legacy, Mapping) and legacy:
        compact_legacy = {
            key: value
            for key, value in legacy.items()
            if value not in (None, "", [], {})
        }
        if compact_legacy:
            capsule["legacy_definition"] = compact_legacy
    provenance = payload.get("provenance")
    if isinstance(provenance, Mapping):
        park_status = provenance.get("park_status")
        if isinstance(park_status, str) and park_status.strip():
            capsule["park_status"] = park_status
    return capsule


def _finalize_snapshot(
    *,
    capsules: list[dict[str, Any]],
    eligible_count: int,
    store_inventory_digest: str,
    max_records: int,
    max_bytes: int,
) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "eligible_count": eligible_count,
        "emitted_count": len(capsules),
        "store_inventory_digest": store_inventory_digest,
        "max_records": max_records,
        "max_bytes": max_bytes,
        "capsules": capsules,
    }
    encoded = canonical_json_bytes(body)
    with_bytes = {
        **body,
        "bytes": len(encoded),
    }
    snapshot = {
        **with_bytes,
        "snapshot_sha256": canonical_sha256(with_bytes),
    }
    return snapshot
