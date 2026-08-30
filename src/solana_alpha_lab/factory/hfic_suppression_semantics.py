"""Typed Hypothesis Forge suppression semantics.

PARK/CLOSE prefixes are not scientific authority. Classification reads typed
decision meaning, provenance and scope from the source payload.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)


TAXONOMY_VERSION = "1.0"
REBASE_DECISION_ID = "DECISION-HFIC-LEGACY-SCIENCE-REBASE-001"
REBASE_RECORD_ID = "SCIENCE-REBASE-SUPPRESSION-SEMANTICS-V1"
REBASE_ARTIFACT_ID = "SCIENCE-REBASE-ART-SUPPRESSION-SEMANTICS-V1"
REBASE_TRANSACTION_ID = "RESEARCH-TXN-SCIENCE-REBASE-SUPPRESSION-V1"
REBASE_PRODUCER = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"

SCIENTIFIC_CLOSE_VALID = "SCIENTIFIC_CLOSE_VALID"
SCOPE_LIMITED_CLOSE = "SCOPE_LIMITED_CLOSE"
OWNER_PRIORITY_PARK = "OWNER_PRIORITY_PARK"
LEGACY_MEASUREMENT_LIMITED = "LEGACY_MEASUREMENT_LIMITED"
REPLAYABLE_UNDER_CURRENT_SCIENCE = "REPLAYABLE_UNDER_CURRENT_SCIENCE"
NON_IDENTIFIABLE_NEEDS_NEW_EVIDENCE = "NON_IDENTIFIABLE_NEEDS_NEW_EVIDENCE"
SUPERSEDED_BY_LATER_EVIDENCE = "SUPERSEDED_BY_LATER_EVIDENCE"
AMBIGUOUS_REQUIRES_OWNER = "AMBIGUOUS_REQUIRES_OWNER"

SCOPE_FAMILY = "FAMILY"
SCOPE_ROUTE = "ROUTE"
SCOPE_RULE = "RULE"
SCOPE_VERSION = "VERSION"
SCOPE_CANDIDATE = "CANDIDATE"
SCOPE_PRIORITY_PARK = "PRIORITY_PARK"
SCOPE_MEASUREMENT = "MEASUREMENT"
SCOPE_AMBIGUOUS = "AMBIGUOUS"

_TYPED_RUNTIME_RECEIPT_RE = re.compile(
    r"^smial\.[a-z0-9]+(?:[.-][a-z0-9]+)*\.runtime-receipt$"
)
_CLOSE_RE = re.compile(r"^CLOSE_[A-Z0-9_]+$")
_PARK_RE = re.compile(r"^PARK_[A-Z0-9_]+$")
_STEM_RE = re.compile(r"^(?:CLOSE|PARK)_(.+?)(?:_FAMILY)?$")
_NON_ALNUM = re.compile(r"[^A-Z0-9]")

_CLASS_RANK = {
    SCIENTIFIC_CLOSE_VALID: 0,
    SCOPE_LIMITED_CLOSE: 1,
    OWNER_PRIORITY_PARK: 2,
    LEGACY_MEASUREMENT_LIMITED: 3,
    REPLAYABLE_UNDER_CURRENT_SCIENCE: 4,
    NON_IDENTIFIABLE_NEEDS_NEW_EVIDENCE: 5,
    SUPERSEDED_BY_LATER_EVIDENCE: 6,
    AMBIGUOUS_REQUIRES_OWNER: 7,
}


class HficSuppressionError(ValueError):
    """Fail-closed suppression-semantics error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _compact(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    return _NON_ALNUM.sub("", value.upper())


def _ledger_item(
    *,
    terminal: str,
    source_receipt: str,
    reopen_forbidden: bool,
    suppression_class: str,
    scope_kind: str,
    scope_id: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "terminal": terminal,
        "source_receipt": source_receipt,
        "reopen_forbidden": bool(reopen_forbidden),
        "suppression_class": suppression_class,
        "scope_kind": scope_kind,
        "visible_as_prior_work": True,
    }
    if isinstance(scope_id, str) and scope_id.strip():
        item["scope_id"] = scope_id.strip()
    return item


def _scope_id(payload: Mapping[str, Any]) -> str | None:
    for key in ("atom_id", "rule_id", "hypothesis_id", "task_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_typed_park(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("priority_disposition") == "PARKED_FROM_PRIORITY"
        and payload.get("science_disposition") == "RETAINED"
        and payload.get("hypothesis_verdict") == "NOT_REFUTED_NOT_SUPPORTED"
    )


def _family_close_declared(payload: Mapping[str, Any], terminal: str) -> bool:
    if payload.get("family_close") is True:
        return True
    if terminal.endswith("_FAMILY"):
        return True
    for key in (
        "scientific_terminal",
        "confirmatory_scientific_terminal",
        "verdict",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.endswith("_FAMILY"):
            return True
    return False


def _is_typed_runtime_receipt(payload: Mapping[str, Any]) -> bool:
    schema = payload.get("schema")
    return isinstance(schema, str) and _TYPED_RUNTIME_RECEIPT_RE.fullmatch(schema) is not None


def _is_legacy_measurement(payload: Mapping[str, Any]) -> bool:
    terminal = payload.get("terminal")
    rule_id = payload.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        return False
    if payload.get("survived") is False and isinstance(terminal, str):
        if "NOT_ACTIONABLE" in terminal:
            return True
    return False


def classify_source_payload(
    payload: Mapping[str, Any] | None,
    *,
    terminal: str,
    source_receipt: str,
) -> dict[str, Any]:
    body = payload if isinstance(payload, Mapping) else {}
    if _is_typed_park(body):
        return _ledger_item(
            terminal=terminal,
            source_receipt=source_receipt,
            reopen_forbidden=False,
            suppression_class=OWNER_PRIORITY_PARK,
            scope_kind=SCOPE_PRIORITY_PARK,
            scope_id=_scope_id(body),
        )
    if _is_legacy_measurement(body) and not _CLOSE_RE.fullmatch(terminal):
        return _ledger_item(
            terminal=terminal,
            source_receipt=source_receipt,
            reopen_forbidden=False,
            suppression_class=LEGACY_MEASUREMENT_LIMITED,
            scope_kind=SCOPE_MEASUREMENT,
            scope_id=str(body.get("rule_id") or ""),
        )
    if _CLOSE_RE.fullmatch(terminal):
        if _family_close_declared(body, terminal) or (
            _is_typed_runtime_receipt(body) and terminal.endswith("_FAMILY")
        ):
            return _ledger_item(
                terminal=terminal,
                source_receipt=source_receipt,
                reopen_forbidden=True,
                suppression_class=SCIENTIFIC_CLOSE_VALID,
                scope_kind=SCOPE_FAMILY,
                scope_id=_scope_id(body),
            )
        if _scope_id(body) or _is_typed_runtime_receipt(body):
            scope_kind = SCOPE_CANDIDATE if "CANDIDATE" in terminal else SCOPE_ROUTE
            if "RULE" in terminal or isinstance(body.get("rule_id"), str):
                scope_kind = SCOPE_RULE
            return _ledger_item(
                terminal=terminal,
                source_receipt=source_receipt,
                reopen_forbidden=True,
                suppression_class=SCOPE_LIMITED_CLOSE,
                scope_kind=scope_kind,
                scope_id=_scope_id(body),
            )
        return _ledger_item(
            terminal=terminal,
            source_receipt=source_receipt,
            reopen_forbidden=True,
            suppression_class=AMBIGUOUS_REQUIRES_OWNER,
            scope_kind=SCOPE_AMBIGUOUS,
        )
    if _PARK_RE.fullmatch(terminal):
        return _ledger_item(
            terminal=terminal,
            source_receipt=source_receipt,
            reopen_forbidden=True,
            suppression_class=AMBIGUOUS_REQUIRES_OWNER,
            scope_kind=SCOPE_AMBIGUOUS,
        )
    return _ledger_item(
        terminal=terminal,
        source_receipt=source_receipt,
        reopen_forbidden=True,
        suppression_class=AMBIGUOUS_REQUIRES_OWNER,
        scope_kind=SCOPE_AMBIGUOUS,
    )


def _source_rank(source: str) -> int:
    if source.startswith("datasets/"):
        return 0
    if source.startswith("docs/"):
        return 1
    if source.startswith("registries/"):
        return 2
    return 3


def dedupe_suppression_ledger(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        (dict(item) for item in items if isinstance(item, Mapping)),
        key=lambda item: (
            str(item.get("terminal") or ""),
            _CLASS_RANK.get(str(item.get("suppression_class") or ""), 99),
            _source_rank(str(item.get("source_receipt") or "")),
            str(item.get("source_receipt") or ""),
        ),
    )
    unique: dict[str, dict[str, Any]] = {}
    for item in ranked:
        terminal = str(item.get("terminal") or "")
        if not terminal or terminal in unique:
            continue
        unique[terminal] = item
    return [unique[key] for key in sorted(unique)]


def family_hard_close_terminals(ledger: Sequence[Mapping[str, Any]]) -> list[str]:
    terminals: list[str] = []
    seen: set[str] = set()
    for item in ledger:
        if not isinstance(item, Mapping):
            continue
        if item.get("reopen_forbidden") is not True:
            continue
        scope = str(item.get("scope_kind") or "")
        if scope not in {SCOPE_FAMILY, SCOPE_AMBIGUOUS}:
            continue
        terminal = item.get("terminal")
        if not isinstance(terminal, str) or not terminal or terminal in seen:
            continue
        seen.add(terminal)
        terminals.append(terminal)
    return terminals


def exact_scope_close_entries(ledger: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in ledger:
        if not isinstance(item, Mapping):
            continue
        if item.get("reopen_forbidden") is not True:
            continue
        if str(item.get("scope_kind") or "") not in {
            SCOPE_ROUTE,
            SCOPE_RULE,
            SCOPE_VERSION,
            SCOPE_CANDIDATE,
        }:
            continue
        found.append(dict(item))
    return found


def _family_stems(terminal: str) -> list[str]:
    match = _STEM_RE.fullmatch(terminal.strip())
    if match is None:
        return []
    stem = match.group(1)
    stems = [stem]
    parts = stem.split("_")
    if len(parts) >= 3:
        stems.append("_".join(parts[1:]))
    return stems


def candidate_matches_hard_close(
    card: Mapping[str, Any],
    ledger: Sequence[Mapping[str, Any]],
) -> str | None:
    blob = _compact(
        " ".join(
            str(card.get(key) or "")
            for key in ("primary_x_family", "claim", "mechanism")
        )
    )
    if not blob:
        return None
    for terminal in family_hard_close_terminals(ledger):
        for stem in _family_stems(terminal):
            compact = _compact(stem)
            if len(compact) < 12:
                continue
            if compact in blob:
                return terminal
    for item in exact_scope_close_entries(ledger):
        terminal = str(item.get("terminal") or "")
        tokens = [terminal]
        scope_id = item.get("scope_id")
        if isinstance(scope_id, str) and scope_id.strip():
            tokens.append(scope_id)
        for token in tokens:
            compact = _compact(token)
            if len(compact) < 12:
                continue
            if compact in blob:
                return terminal
    return None


def ledger_from_receipt(receipt: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(receipt, Mapping):
        return []
    packet = receipt.get("forge_context_packet")
    if not isinstance(packet, Mapping):
        return []
    ledger = packet.get("closed_family_ledger")
    if not isinstance(ledger, list):
        return []
    items = [dict(item) for item in ledger if isinstance(item, Mapping)]
    return items


def suppression_counts(ledger: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "suppressors_total": 0,
        SCIENTIFIC_CLOSE_VALID: 0,
        SCOPE_LIMITED_CLOSE: 0,
        OWNER_PRIORITY_PARK: 0,
        LEGACY_MEASUREMENT_LIMITED: 0,
        REPLAYABLE_UNDER_CURRENT_SCIENCE: 0,
        NON_IDENTIFIABLE_NEEDS_NEW_EVIDENCE: 0,
        SUPERSEDED_BY_LATER_EVIDENCE: 0,
        AMBIGUOUS_REQUIRES_OWNER: 0,
        "hard_closed": 0,
        "priority_park_hard_close_count": 0,
        "scope_overclosure_count": 0,
    }
    for item in ledger:
        if not isinstance(item, Mapping):
            continue
        counts["suppressors_total"] += 1
        klass = str(item.get("suppression_class") or "")
        if klass in counts:
            counts[klass] += 1
        if item.get("reopen_forbidden") is True:
            counts["hard_closed"] += 1
        if klass == OWNER_PRIORITY_PARK and item.get("reopen_forbidden") is True:
            counts["priority_park_hard_close_count"] += 1
        if (
            klass == SCOPE_LIMITED_CLOSE
            and str(item.get("scope_kind") or "") == SCOPE_FAMILY
        ):
            counts["scope_overclosure_count"] += 1
    return counts


def ledger_delta(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_map = {
        str(item.get("terminal") or ""): dict(item)
        for item in before
        if isinstance(item, Mapping) and item.get("terminal")
    }
    after_map = {
        str(item.get("terminal") or ""): dict(item)
        for item in after
        if isinstance(item, Mapping) and item.get("terminal")
    }
    hard_before = sorted(
        key for key, item in before_map.items() if item.get("reopen_forbidden") is True
    )
    hard_after = sorted(
        key for key, item in after_map.items() if item.get("reopen_forbidden") is True
    )
    parks_removed = sorted(
        key
        for key, item in after_map.items()
        if item.get("suppression_class") == OWNER_PRIORITY_PARK
        and item.get("reopen_forbidden") is not True
        and before_map.get(key, {}).get("reopen_forbidden") is True
    )
    narrowed = sorted(
        key
        for key, item in after_map.items()
        if item.get("suppression_class") == SCOPE_LIMITED_CLOSE
        and (
            before_map.get(key, {}).get("prefix_era") is True
            or before_map.get(key, {}).get("suppression_class") != SCOPE_LIMITED_CLOSE
            or before_map.get(key, {}).get("scope_kind") == SCOPE_FAMILY
        )
    )
    legacy = sorted(
        key
        for key, item in after_map.items()
        if item.get("suppression_class") == LEGACY_MEASUREMENT_LIMITED
    )
    unchanged = sorted(
        key
        for key, item in after_map.items()
        if item.get("suppression_class") == SCIENTIFIC_CLOSE_VALID
        and before_map.get(key, {}).get("reopen_forbidden") is True
    )
    ambiguous = sorted(
        key
        for key, item in after_map.items()
        if item.get("suppression_class") == AMBIGUOUS_REQUIRES_OWNER
    )
    return {
        "hard_closed_before": hard_before,
        "hard_closed_after": hard_after,
        "priority_parks_removed_from_hard_close": parks_removed,
        "scope_limited_closes_narrowed": narrowed,
        "legacy_measurement_closes_reclassified": legacy,
        "unchanged_valid_closes": unchanged,
        "ambiguous_items": ambiguous,
    }


def _existing_rebase_record(store: ResearchStore) -> dict[str, Any] | None:
    for record in store.iter_committed_records():
        if str(getattr(record, "record_id", "")) != REBASE_RECORD_ID:
            continue
        try:
            payload = json.loads(record.payload_json)
        except (ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def prefix_era_hard_close_view(ledger: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Prefix-era view: every scraped CLOSE_/PARK_ terminal was hard-closed."""
    out: list[dict[str, Any]] = []
    for item in ledger:
        if not isinstance(item, Mapping):
            continue
        cloned = dict(item)
        cloned["reopen_forbidden"] = True
        cloned["prefix_era"] = True
        out.append(cloned)
    return out


def run_science_memory_rebase(
    store: ResearchStore,
    *,
    repo_root: Path,
    data_root: Path,
    clock: Clock | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_preflight import (
        enumerate_closed_park_terminals,
        evidence_epoch_material,
    )
    from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256

    after_ledger = enumerate_closed_park_terminals(Path(repo_root), Path(data_root))
    before_ledger = prefix_era_hard_close_view(after_ledger)
    epoch_before = evidence_epoch_sha256(
        evidence_epoch_material(Path(repo_root), Path(data_root))
    )
    persisted = persist_science_memory_rebase(
        store,
        repo_root=Path(repo_root),
        before_ledger=before_ledger,
        after_ledger=after_ledger,
        evidence_epoch_before=epoch_before,
        evidence_epoch_after=epoch_before,
        clock=clock,
    )
    epoch_after = evidence_epoch_sha256(
        evidence_epoch_material(Path(repo_root), Path(data_root))
    )
    rebuilt = enumerate_closed_park_terminals(Path(repo_root), Path(data_root))
    return {
        **persisted,
        "evidence_epoch_before": epoch_before,
        "evidence_epoch_after": epoch_after,
        "after_counts": suppression_counts(after_ledger),
        "before_counts": suppression_counts(before_ledger),
        "ledger_identical_after_rebuild": rebuilt == after_ledger,
        "after_ledger": after_ledger,
    }


def persist_science_memory_rebase(
    store: ResearchStore,
    *,
    repo_root: Path,
    before_ledger: Sequence[Mapping[str, Any]],
    after_ledger: Sequence[Mapping[str, Any]],
    evidence_epoch_before: str,
    evidence_epoch_after: str,
    clock: Clock | None = None,
) -> dict[str, Any]:
    existing = _existing_rebase_record(store)
    if existing is not None:
        return {
            "status": "REPLAY_IDENTICAL",
            "decision_event_id": REBASE_DECISION_ID,
            "record_id": REBASE_RECORD_ID,
            **ledger_delta(before_ledger, after_ledger),
            "evidence_epoch_before": evidence_epoch_before,
            "evidence_epoch_after": evidence_epoch_after,
        }
    try:
        now = capture_stage_time(clock)
        render_canonical_utc(now)
    except HficClockError as exc:
        raise HficSuppressionError(str(exc)) from exc
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    git = repository_git_snapshot(Path(repo_root))
    delta = ledger_delta(before_ledger, after_ledger)
    decision_payload = {
        "decision_event_id": REBASE_DECISION_ID,
        "decision_kind": "SCIENCE_MEMORY_REBASE",
        "reason_code": "HFIC_SUPPRESSION_SEMANTICS_V1",
        "taxonomy_version": TAXONOMY_VERSION,
        "named_consumer": "HFIC-PREFLIGHT-CLOSED-FAMILY-LEDGER",
        "historical_bytes_rewritten": False,
        "hfic_self_memory": False,
    }
    artifact_payload = {
        "research_artifact_id": REBASE_ARTIFACT_ID,
        "artifact_kind": "SCIENCE_MEMORY_REBASE_RECEIPT",
        "taxonomy_version": TAXONOMY_VERSION,
        "decision_event_id": REBASE_DECISION_ID,
        "delta": delta,
        "after_counts": suppression_counts(after_ledger),
        "evidence_epoch_before": evidence_epoch_before,
        "named_consumer": "HFIC-PREFLIGHT-CLOSED-FAMILY-LEDGER",
    }

    def _event(
        record_id: str,
        kind: RecordKind,
        entity_id: str,
        payload: Mapping[str, Any],
    ) -> ResearchEvent:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return ResearchEvent(
            record_id=record_id,
            record_kind=kind,
            entity_id=entity_id,
            hypothesis_version_id=None,
            run_id=None,
            transaction_id=REBASE_TRANSACTION_ID,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=encoded,
            payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id=REBASE_PRODUCER,
            producer_git_sha=git.head_sha.lower(),
            created_at=now,
        )

    records = [
        _event(
            REBASE_RECORD_ID,
            RecordKind.DECISION_EVENT,
            REBASE_DECISION_ID,
            decision_payload,
        ),
        _event(
            REBASE_ARTIFACT_ID,
            RecordKind.RESEARCH_ARTIFACT,
            REBASE_ARTIFACT_ID,
            artifact_payload,
        ),
    ]
    from solana_alpha_lab.factory.hfic_provenance import is_hfic_record

    for record in records:
        payload = json.loads(record.payload_json)
        if is_hfic_record(record, payload):
            raise HficSuppressionError("REBASE_MUST_NOT_BE_HFIC_SELF_MEMORY")
    try:
        store.append(records, transaction_id=REBASE_TRANSACTION_ID)
    except ResearchStoreError as exc:
        raise HficSuppressionError(str(exc)) from exc
    store.rebuild_projection()
    return {
        "status": "APPENDED",
        "decision_event_id": REBASE_DECISION_ID,
        "record_id": REBASE_RECORD_ID,
        **delta,
        "evidence_epoch_before": evidence_epoch_before,
        "evidence_epoch_after": evidence_epoch_after,
        "created_at": render_canonical_utc(now),
    }
