"""OwnerAttentionProjectionV1. Derived only. Persists nowhere."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from solana_alpha_lab.factory.owner_review_cursor import (
    SOURCE_DOMAINS,
    empty_watermark,
    snapshot_sha256,
)

SCHEMA = "smial.owner-attention-projection"
NOISE_CODES = frozenset(
    {
        "ACTIVATION_PATH_GAP",
        "WATCHLIST_SOURCE_GAP",
        "ACTIVATION_GAP",
        "LEGACY_TRACE_GAP",
        "SIGNAL_TRACE_GAP",
        "TARGET_GAP",
        "SOURCE_NOT_PRESENT",
        "BACKUP_EXPLICIT_UNKNOWN",
        "RUNTIME_ATTENTION",
    }
)
COCKPIT_RESEARCH_CODES = frozenset(
    {"GIT_ARCHAEOLOGY_REQUIRED", "DECISION_AVAILABLE"}
)
COCKPIT_SYSTEM_CODES = frozenset(
    {"BACKUP_EXPLICIT_UNKNOWN", "RUNTIME_ATTENTION"}
)
P0_CODES = frozenset(
    {
        "UNRESOLVED_POSITION",
        "POSITION_UNKNOWN",
        "EXIT_REQUIRED",
        "PNL_UNKNOWN_OR_STALE",
    }
)
P1_OPERATION_CODES = frozenset(
    {
        "RUNTIME_SOURCE_UNAVAILABLE",
        "BOT_DRAINING",
        "SOURCE_UNAVAILABLE",
        "SOURCE_INVALID",
        "IDENTITY_CONFLICT",
        "STATE_CONFLICT",
        "GIT_ARCHAEOLOGY_REQUIRED",
    }
)
P2_CODES = frozenset({"DECISION_AVAILABLE"})
INFO_CODES = frozenset({"ENTRIES_PAUSED", "LOSS_STREAK", "RISK_BLOCK"})
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "UNKNOWN": 3, "INFO": 4}
DRILLDOWN = {
    "RESEARCH": "/research",
    "OPERATIONS": "/operations",
    "SYSTEM": "/system",
}
CHANGE_FEED_LIMIT = 12
RESEARCH_STORE_SOURCE_ID = "SRC-RESEARCH-STORE"
BLOCKING_STATE = frozenset({"UNAVAILABLE", "INVALID"})
HISTORY_COMPLETE = "AVAILABLE"
_WATERMARK_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _utc_iso(value: Any) -> str | None:
    parsed = _utc_dt(value)
    if parsed is None:
        text = _text(value)
        return text or None
    spec = "microseconds" if parsed.microsecond else "seconds"
    return parsed.isoformat(timespec=spec).replace("+00:00", "Z")


def _utc_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if hasattr(value, "astimezone"):
        return value.astimezone(timezone.utc)
    text = _text(value)
    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _priority_for(code: str, *, source_domain: str) -> str:
    if code in NOISE_CODES:
        return ""
    if code in P0_CODES:
        return "P0"
    if code in P1_OPERATION_CODES:
        return "P1"
    if code in P2_CODES:
        return "P2"
    if code in INFO_CODES:
        return "INFO"
    if source_domain == "SYSTEM":
        return "P1"
    return "UNKNOWN"


def _item(
    *,
    source_domain: str,
    code: str,
    native_identity: str,
    why: str,
    impact: str,
    evidence: str,
    nxt: str,
    available_at: str | None = None,
    effective_at: str | None = None,
    source_status: str = "AVAILABLE",
    change_kind: str | None = None,
) -> dict[str, Any]:
    priority = _priority_for(code, source_domain=source_domain)
    if not priority:
        return {}
    key = f"{source_domain}:{code}:{native_identity or code}"
    return {
        "attention_key": key,
        "source_domain": source_domain,
        "source_owner": {
            "RESEARCH": "RESEARCH_LIFECYCLE_WORKBENCH_V1",
            "OPERATIONS": "TRADING_OPERATIONS_WORKBENCH_V2",
            "SYSTEM": "SYSTEM_OPERABILITY_SURFACE_V2",
        }[source_domain],
        "source_native_identity": native_identity or code,
        "entity_locator": native_identity or None,
        "attention_code": code,
        "priority": priority,
        "WHAT": code,
        "WHY_NOW": why or "UNKNOWN",
        "IMPACT": impact or "UNKNOWN",
        "EVIDENCE": evidence or "UNKNOWN",
        "CURRENT_SAFE_STATE": "UNKNOWN",
        "NEXT_SAFE_ACTION": nxt or "UNKNOWN",
        "AUTHORITY_REQUIRED": False,
        "observed_at": available_at,
        "available_at": available_at,
        "effective_at": effective_at,
        "source_status": source_status,
        "drilldown_target": DRILLDOWN[source_domain],
        "change_kind": change_kind,
        "new_since_review": False,
    }


def _locator_entity(row: Mapping[str, Any]) -> str:
    locator = row.get("locator")
    if isinstance(locator, Mapping):
        return _text(locator.get("entity_id"))
    return ""


def _attention_code(row: Mapping[str, Any]) -> str:
    code = _text(
        row.get("attention_code")
        or row.get("code")
        or row.get("id")
        or row.get("blocker")
        or row.get("gap_code")
    )
    if code:
        return code
    if _text(row.get("display_state")) == "CONFLICT":
        native = _text(row.get("native_state"))
        if native in {"IDENTITY_CONFLICT", "STATE_CONFLICT"}:
            return native
        return "IDENTITY_CONFLICT"
    native = _text(row.get("native_state"))
    if native in P0_CODES | P1_OPERATION_CODES | P2_CODES | INFO_CODES:
        return native
    return ""


def _native_identity(row: Mapping[str, Any], code: str) -> str:
    identity = _text(
        row.get("native_identity")
        or row.get("source_native_identity")
        or row.get("entity_id")
        or row.get("position_id")
        or row.get("bot_instance_id")
        or _locator_entity(row)
        or row.get("source_id")
    )
    if identity:
        return identity
    source = row.get("source")
    if isinstance(source, str) and source:
        return source
    if isinstance(source, Mapping):
        nested = _text(source.get("source_id") or source.get("value") or source.get("kind"))
        if nested:
            return nested
    evidence = _text(row.get("EVIDENCE") or row.get("evidence"))
    if evidence and evidence != code:
        return evidence
    return ""


def _from_local_attention(
    rows: Any, *, source_domain: str, source_status: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _attention_code(row)
        if not code:
            continue
        identity = _native_identity(row, code)
        if not identity:
            continue
        item = _item(
            source_domain=source_domain,
            code=code,
            native_identity=identity,
            why=_text(row.get("WHY_NOW") or row.get("title")),
            impact=_text(row.get("IMPACT")),
            evidence=_text(row.get("EVIDENCE") or row.get("native_state") or identity),
            nxt=_text(row.get("NEXT_SAFE_ACTION") or row.get("next_safe_action")),
            available_at=_utc_iso(row.get("observed_at") or row.get("as_of")),
            source_status=source_status,
        )
        if item:
            if source_domain == "SYSTEM":
                item["CURRENT_SAFE_STATE"] = _text(row.get("CURRENT_SAFE_STATE")) or "UNKNOWN"
                item["AUTHORITY_REQUIRED"] = bool(row.get("AUTHORITY_REQUIRED"))
                route = _text(row.get("RECOVERY_ROUTE"))
                if route:
                    item["RECOVERY_ROUTE"] = route
            out.append(item)
    return out


def _coverage_row(
    domain: str,
    *,
    current: str,
    history: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "source_domain": domain,
        "CURRENT_STATE": current,
        "CHANGE_HISTORY": history,
        "reason": reason,
        "drilldown_target": DRILLDOWN[domain],
    }


def _store_source(sources: list[Any]) -> dict[str, Any] | None:
    labeled: list[dict[str, Any]] = []
    unlabeled: list[dict[str, Any]] = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        source_id = _text(item.get("source_id"))
        if source_id == RESEARCH_STORE_SOURCE_ID or _text(item.get("truth_plane")) == "EVIDENCE":
            return item
        if source_id:
            labeled.append(item)
        else:
            unlabeled.append(item)
    if not labeled and len(unlabeled) == 1:
        return unlabeled[0]
    return None


def _history_for_store(status: str) -> str:
    if status in {"AVAILABLE", "EMPTY"}:
        return "AVAILABLE"
    if status == "NOT_PRESENT":
        return "NOT_PRESENT"
    return "UNAVAILABLE"


def _research_coverage(
    research: Mapping[str, Any] | None,
    discovery: str | None,
    *,
    records_status: str | None = None,
) -> dict[str, Any]:
    if records_status in BLOCKING_STATE:
        current = records_status if records_status in BLOCKING_STATE else "UNAVAILABLE"
        return _coverage_row("RESEARCH", current=current, history="UNAVAILABLE")
    if discovery in BLOCKING_STATE:
        return _coverage_row("RESEARCH", current=str(discovery), history="UNAVAILABLE")
    if research is None:
        status = discovery or "NOT_PRESENT"
        history = _history_for_store(status)
        return _coverage_row("RESEARCH", current=status, history=history)
    completeness = _text(research.get("completeness"))
    sources = research.get("sources") if isinstance(research.get("sources"), list) else []
    store = _store_source(sources)
    if not sources:
        if completeness in BLOCKING_STATE:
            current = completeness
        elif discovery:
            current = discovery
        else:
            current = "UNAVAILABLE"
        return _coverage_row(
            "RESEARCH",
            current=current,
            history=_history_for_store(current),
        )
    store_status = _text(store.get("status")) if store is not None else ""
    other_statuses = [
        _text(item.get("status"))
        for item in sources
        if isinstance(item, dict) and item is not store and _text(item.get("status"))
    ]
    if store is None:
        return _coverage_row("RESEARCH", current="PARTIAL", history="NOT_PRESENT")
    if store_status in BLOCKING_STATE:
        return _coverage_row("RESEARCH", current=store_status, history="UNAVAILABLE")
    history = _history_for_store(store_status)
    if store_status == "NOT_PRESENT":
        current = "PARTIAL" if any(item in {"AVAILABLE", "EMPTY"} for item in other_statuses) else "NOT_PRESENT"
        return _coverage_row("RESEARCH", current=current, history="NOT_PRESENT")
    if other_statuses and any(item not in {"AVAILABLE", "EMPTY"} for item in other_statuses):
        return _coverage_row("RESEARCH", current="PARTIAL", history=history)
    return _coverage_row("RESEARCH", current=store_status or "AVAILABLE", history=history)


def _operations_coverage(trading: Mapping[str, Any] | None) -> dict[str, Any]:
    status = _text((trading or {}).get("source_status") or "NOT_PRESENT") or "NOT_PRESENT"
    if status == "PRESENT":
        return _coverage_row("OPERATIONS", current="AVAILABLE", history="AVAILABLE")
    if status == "NOT_PRESENT":
        return _coverage_row("OPERATIONS", current="NOT_PRESENT", history="NOT_PRESENT")
    if status == "UNAVAILABLE":
        return _coverage_row("OPERATIONS", current="UNAVAILABLE", history="UNAVAILABLE")
    return _coverage_row("OPERATIONS", current="INVALID", history="UNAVAILABLE")


def _system_coverage(
    runtime: Mapping[str, Any] | None,
    system: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(system, dict) and system:
        groups = system.get("coverage") if isinstance(system.get("coverage"), dict) else {}
        collector = _text((groups.get("COLLECTOR") or {}).get("status"))
        systemd = _text((groups.get("SYSTEMD") or {}).get("status"))
        if collector in {"UNAVAILABLE", "INVALID"}:
            current = collector
        elif _text(system.get("state")) in {"UNKNOWN", "DEGRADED", "ACTION_REQUIRED"}:
            current = "PARTIAL"
        elif systemd == "UNAVAILABLE" or collector in {"NOT_PRESENT", "PARTIAL", ""}:
            current = "PARTIAL"
        else:
            current = "AVAILABLE"
        return _coverage_row(
            "SYSTEM",
            current=current,
            history="STATE_ONLY",
            reason="CHANGE_HISTORY_UNAVAILABLE",
        )
    if not isinstance(runtime, dict) or not runtime:
        return _coverage_row(
            "SYSTEM",
            current="PARTIAL",
            history="STATE_ONLY",
            reason="CHANGE_HISTORY_UNAVAILABLE",
        )
    return _coverage_row(
        "SYSTEM",
        current="PARTIAL",
        history="STATE_ONLY",
        reason="CHANGE_HISTORY_UNAVAILABLE",
    )


def _operations_changes(trading: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    events = (trading or {}).get("recent_changes")
    if not isinstance(events, list):
        return out
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = _text(event.get("event_id"))
        available = _utc_iso(event.get("created_at"))
        if not event_id:
            continue
        out.append(
            {
                "source_domain": "OPERATIONS",
                "native_identity": event_id,
                "change_available_at": available,
                "effective_at": _utc_iso(event.get("effective_at")) or available,
                "change_kind": _text(event.get("event_type") or "EXECUTION_EVENT"),
                "attention_code": _text(event.get("event_type") or "EXECUTION_EVENT"),
                "drilldown_target": "/operations",
                "WHY_NOW": _text(event.get("event_type") or "EXECUTION_EVENT"),
                "IMPACT": "INFO",
                "EVIDENCE": event_id,
                "NEXT_SAFE_ACTION": "OPEN_OPERATIONS",
            }
        )
    return out


def _research_changes(records: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(records, list):
        return out
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = _text(record.get("record_id"))
        available = _utc_iso(record.get("first_reliable_available_at"))
        if not identity:
            continue
        out.append(
            {
                "source_domain": "RESEARCH",
                "native_identity": identity,
                "change_available_at": available,
                "effective_at": _utc_iso(record.get("effective_at")),
                "change_kind": _text(record.get("record_kind") or "RESEARCH_EVENT"),
                "attention_code": _text(record.get("record_kind") or "RESEARCH_EVENT"),
                "drilldown_target": "/research",
                "WHY_NOW": _text(record.get("record_kind") or "RESEARCH_EVENT"),
                "IMPACT": "INFO",
                "EVIDENCE": identity,
                "NEXT_SAFE_ACTION": "OPEN_RESEARCH",
            }
        )
    return out


def _watermark_tuple(available: str | None, identity: str | None) -> tuple[datetime, str]:
    return (_utc_dt(available) or _WATERMARK_EPOCH, identity or "")


def _after_cursor(
    change: Mapping[str, Any], watermark: Mapping[str, Any] | None
) -> bool:
    mark = watermark or empty_watermark()
    return _watermark_tuple(change.get("change_available_at"), change.get("native_identity")) > _watermark_tuple(
        mark.get("change_available_at"), mark.get("native_identity")
    )


def _source_watermark(changes: list[Mapping[str, Any]]) -> dict[str, str | None]:
    best = empty_watermark()
    best_tuple: tuple[datetime, str] = (_WATERMARK_EPOCH, "")
    for change in changes:
        current = _watermark_tuple(change.get("change_available_at"), change.get("native_identity"))
        if current > best_tuple:
            best_tuple = current
            best = {
                "change_available_at": change.get("change_available_at"),
                "native_identity": change.get("native_identity"),
            }
    return best


def _dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        key = item["attention_key"]
        if key in seen:
            if item.get("new_since_review"):
                seen[key]["new_since_review"] = True
            continue
        seen[key] = item
        order.append(key)
    return [seen[key] for key in order]


def _domain_changes(changes: list[Mapping[str, Any]], domain: str) -> list[Mapping[str, Any]]:
    return [item for item in changes if item.get("source_domain") == domain]


def _window_hole(
    domain_changes: list[Mapping[str, Any]],
    mark: Mapping[str, Any] | None,
    *,
    established: bool,
) -> bool:
    if not established or not isinstance(mark, Mapping):
        return False
    mark_tuple = _watermark_tuple(mark.get("change_available_at"), mark.get("native_identity"))
    if not _text(mark.get("change_available_at")) and not _text(mark.get("native_identity")):
        return False
    if len(domain_changes) < CHANGE_FEED_LIMIT:
        return False
    oldest = min(
        (
            _watermark_tuple(item.get("change_available_at"), item.get("native_identity"))
            for item in domain_changes
        ),
        default=(_WATERMARK_EPOCH, ""),
    )
    return oldest > mark_tuple


def _coverage_blocker_item(domain: str, state: str) -> dict[str, Any]:
    if domain == "OPERATIONS":
        code = "SOURCE_INVALID" if state == "INVALID" else "RUNTIME_SOURCE_UNAVAILABLE"
        nxt = "OPEN_OPERATIONS"
        identity = "PAPER_PLANE"
    else:
        code = "SOURCE_INVALID" if state == "INVALID" else "SOURCE_UNAVAILABLE"
        nxt = "RESOLVE_RESEARCH_STORE"
        identity = RESEARCH_STORE_SOURCE_ID
    return _item(
        source_domain=domain,
        code=code,
        native_identity=identity,
        why=code,
        impact="named consumer blocked",
        evidence=state,
        nxt=nxt,
        source_status=state,
    )


def _ensure_coverage_blockers(
    current: list[dict[str, Any]], coverage: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    existing = {
        (item.get("source_domain"), item.get("attention_code"))
        for item in current
    }
    out = list(current)
    for domain in ("RESEARCH", "OPERATIONS"):
        state = _text(coverage[domain].get("CURRENT_STATE"))
        if state not in BLOCKING_STATE:
            continue
        codes = (
            {"RUNTIME_SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE", "SOURCE_INVALID"}
            if domain == "OPERATIONS"
            else {"SOURCE_UNAVAILABLE", "SOURCE_INVALID"}
        )
        if any((domain, code) in existing for code in codes):
            continue
        item = _coverage_blocker_item(domain, state)
        if item:
            out.append(item)
    return out


def _change_item(change: Mapping[str, Any], *, source_status: str) -> dict[str, Any]:
    domain = str(change["source_domain"])
    item = _item(
        source_domain=domain,
        code=change.get("attention_code") or "CHANGE",
        native_identity=str(change["native_identity"]),
        why=change.get("WHY_NOW") or "",
        impact="INFO",
        evidence=change.get("EVIDENCE") or "",
        nxt=change.get("NEXT_SAFE_ACTION") or "",
        available_at=change.get("change_available_at"),
        effective_at=change.get("effective_at"),
        source_status=source_status,
        change_kind=change.get("change_kind"),
    )
    if item:
        item["new_since_review"] = True
        item["priority"] = "INFO"
        return item
    return {
        "attention_key": f"{domain}:CHANGE:{change['native_identity']}",
        "source_domain": domain,
        "source_owner": "TRADING_OPERATIONS_WORKBENCH_V2"
        if domain == "OPERATIONS"
        else "RESEARCH_LIFECYCLE_WORKBENCH_V1",
        "source_native_identity": change["native_identity"],
        "entity_locator": change["native_identity"],
        "attention_code": change.get("attention_code") or "CHANGE",
        "priority": "INFO",
        "WHAT": change.get("change_kind") or "CHANGE",
        "WHY_NOW": change.get("WHY_NOW") or "UNKNOWN",
        "IMPACT": "INFO",
        "EVIDENCE": change.get("EVIDENCE") or "UNKNOWN",
        "CURRENT_SAFE_STATE": "UNKNOWN",
        "NEXT_SAFE_ACTION": change.get("NEXT_SAFE_ACTION") or "UNKNOWN",
        "AUTHORITY_REQUIRED": False,
        "observed_at": change.get("change_available_at"),
        "available_at": change.get("change_available_at"),
        "effective_at": change.get("effective_at"),
        "source_status": source_status,
        "drilldown_target": change.get("drilldown_target"),
        "change_kind": change.get("change_kind"),
        "new_since_review": True,
    }


def _identity_token(item: Mapping[str, Any]) -> str:
    return "|".join(
        [
            _text(item.get("source_domain")),
            _text(item.get("native_identity") or item.get("source_native_identity")),
            _text(item.get("change_available_at") or item.get("available_at")),
        ]
    )


def compose_owner_attention(
    *,
    research: Mapping[str, Any] | None = None,
    trading: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    system: Mapping[str, Any] | None = None,
    cockpit: Mapping[str, Any] | None = None,
    research_records: list[dict[str, Any]] | None = None,
    research_records_status: str | None = None,
    research_discovery: str | None = None,
    cursor: Mapping[str, Any] | None = None,
    cursor_status: str = "MISSING",
) -> dict[str, Any]:
    coverage = {
        "RESEARCH": _research_coverage(
            research, research_discovery, records_status=research_records_status
        ),
        "OPERATIONS": _operations_coverage(trading),
        "SYSTEM": _system_coverage(runtime, system),
    }
    research_status = coverage["RESEARCH"]["CURRENT_STATE"]
    ops_status = coverage["OPERATIONS"]["CURRENT_STATE"]
    current: list[dict[str, Any]] = []
    current.extend(
        _from_local_attention(
            (research or {}).get("needs_attention"),
            source_domain="RESEARCH",
            source_status=research_status,
        )
    )
    current.extend(
        _from_local_attention(
            (trading or {}).get("attention"),
            source_domain="OPERATIONS",
            source_status=ops_status,
        )
    )
    cockpit_rows = (cockpit or {}).get("attention")
    cockpit_research: list[Any] = []
    cockpit_system: list[Any] = []
    if isinstance(cockpit_rows, list):
        for row in cockpit_rows:
            if not isinstance(row, dict):
                continue
            code = _text(row.get("code") or row.get("id") or row.get("blocker"))
            if code in COCKPIT_SYSTEM_CODES:
                cockpit_system.append(row)
            elif code in COCKPIT_RESEARCH_CODES or code:
                cockpit_research.append(row)
    current.extend(
        _from_local_attention(
            cockpit_research,
            source_domain="RESEARCH",
            source_status=research_status,
        )
    )
    current.extend(
        _from_local_attention(
            cockpit_system,
            source_domain="SYSTEM",
            source_status=coverage["SYSTEM"]["CURRENT_STATE"],
        )
    )
    current.extend(
        _from_local_attention(
            (system or {}).get("attention"),
            source_domain="SYSTEM",
            source_status=coverage["SYSTEM"]["CURRENT_STATE"],
        )
    )
    current = [item for item in current if item.get("attention_code") not in NOISE_CODES]
    current = _ensure_coverage_blockers(current, coverage)
    current = _dedup(current)

    feed_ok = {
        domain: coverage[domain]["CHANGE_HISTORY"] == HISTORY_COMPLETE
        for domain in ("RESEARCH", "OPERATIONS")
    }
    changes: list[dict[str, Any]] = []
    if feed_ok["RESEARCH"]:
        changes.extend(_research_changes(research_records))
    if feed_ok["OPERATIONS"]:
        changes.extend(_operations_changes(trading))

    cursor_sources = (cursor or {}).get("sources") if isinstance(cursor, Mapping) else {}
    established = cursor_status == "VALID" and isinstance(cursor_sources, dict)
    history_gap = False
    gapped_domains: set[str] = set()
    for domain in ("RESEARCH", "OPERATIONS"):
        if not feed_ok[domain]:
            continue
        domain_rows = _domain_changes(changes, domain)
        mark = cursor_sources.get(domain) if established else None
        if _window_hole(domain_rows, mark if isinstance(mark, dict) else None, established=established):
            history_gap = True
            gapped_domains.add(domain)
        elif (
            established
            and isinstance(mark, dict)
            and (mark.get("change_available_at") or "")
            and domain_rows
            and all(
                _watermark_tuple(item.get("change_available_at"), item.get("native_identity"))
                < _watermark_tuple(mark.get("change_available_at"), mark.get("native_identity"))
                for item in domain_rows
            )
        ):
            history_gap = True
            gapped_domains.add(domain)

    watermarks = {
        "RESEARCH": _source_watermark(
            [item for item in changes if item["source_domain"] == "RESEARCH"]
        ),
        "OPERATIONS": _source_watermark(
            [item for item in changes if item["source_domain"] == "OPERATIONS"]
        ),
        "SYSTEM": empty_watermark(),
    }

    new_changes: list[dict[str, Any]] = []
    for change in changes:
        domain = change["source_domain"]
        if not feed_ok[domain]:
            continue
        mark = cursor_sources.get(domain) if established else None
        is_new = (not established) or _after_cursor(change, mark if isinstance(mark, dict) else None)
        if not is_new:
            continue
        new_changes.append(
            _change_item(change, source_status=coverage[domain]["CURRENT_STATE"])
        )

    overflow = False
    if len(new_changes) > CHANGE_FEED_LIMIT:
        overflow = True
        history_gap = True
        for item in new_changes:
            gapped_domains.add(str(item.get("source_domain")))
        new_changes.sort(
            key=lambda item: _watermark_tuple(item.get("available_at"), item.get("source_native_identity")),
            reverse=True,
        )
        new_changes = list(reversed(new_changes[:CHANGE_FEED_LIMIT]))

    for domain in gapped_domains:
        coverage[domain]["CHANGE_HISTORY"] = "UNAVAILABLE"
        coverage[domain]["reason"] = "CHANGE_HISTORY_GAP"

    for change in new_changes:
        for item in current:
            if (
                item["source_domain"] == change["source_domain"]
                and item["source_native_identity"] == change["source_native_identity"]
            ):
                item["new_since_review"] = True
                change["merged_into_current"] = True

    current = _dedup(current)
    visible_changes = [item for item in new_changes if not item.get("merged_into_current")]

    def _sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
        return (
            PRIORITY_RANK.get(str(item.get("priority")), 9),
            _text(item.get("available_at")),
            _text(item.get("attention_key")),
        )

    current.sort(key=_sort_key)
    visible_changes.sort(key=_sort_key)
    material = [item for item in current if item.get("priority") in {"P0", "P1", "P2", "UNKNOWN"}]
    info = _dedup([item for item in current if item.get("priority") == "INFO"])

    review_code = None
    if cursor_status == "MISSING":
        review_code = "REVIEW_BASELINE_NOT_ESTABLISHED"
    elif cursor_status == "INVALID":
        review_code = "REVIEW_CURSOR_INVALID"
    elif history_gap:
        review_code = "CHANGE_HISTORY_GAP"

    blocking = any(
        coverage[domain]["CURRENT_STATE"] in BLOCKING_STATE for domain in ("RESEARCH", "OPERATIONS")
    )
    history_complete = not history_gap and not overflow
    snapshot = {
        "schema": "smial.owner-review-snapshot",
        "schema_version": "1.0",
        "history_complete": history_complete,
        "reviewed_identities": sorted(_identity_token(item) for item in changes),
        "sources": {
            domain: {
                "CURRENT_STATE": coverage[domain]["CURRENT_STATE"],
                "CHANGE_HISTORY": coverage[domain]["CHANGE_HISTORY"],
                **watermarks[domain],
            }
            for domain in SOURCE_DOMAINS
        },
    }
    digest = snapshot_sha256(snapshot)
    all_clear = (not material) and (not blocking) and history_complete
    return {
        "schema": SCHEMA,
        "schema_version": "1.0",
        "current_attention": material,
        "info_items": info,
        "changes": visible_changes,
        "coverage": [coverage[domain] for domain in SOURCE_DOMAINS],
        "review": {
            "code": review_code,
            "cursor_status": cursor_status,
            "since_previous_review": established and review_code is None,
        },
        "review_snapshot": snapshot,
        "review_snapshot_sha256": digest,
        "all_clear": all_clear,
        "healthy_claim": False,
    }


def persistable_watermarks(
    snapshot: Mapping[str, Any],
    *,
    previous: Mapping[str, Any] | None,
    coverage: list[Mapping[str, Any]],
) -> dict[str, dict[str, str | None]]:
    """Do not advance a source that cannot currently prove reviewable history."""

    previous_sources = (previous or {}).get("sources") if isinstance(previous, Mapping) else {}
    by_domain = {
        str(row.get("source_domain")): row
        for row in coverage
        if isinstance(row, Mapping)
    }
    sources = snapshot.get("sources") if isinstance(snapshot.get("sources"), Mapping) else {}
    history_complete = snapshot.get("history_complete", True)
    out: dict[str, dict[str, str | None]] = {}
    for domain in SOURCE_DOMAINS:
        row = by_domain.get(domain) or {}
        history = _text(row.get("CHANGE_HISTORY"))
        current_state = _text(row.get("CURRENT_STATE"))
        live = sources.get(domain) if isinstance(sources.get(domain), Mapping) else {}
        live_at = live.get("change_available_at")
        live_id = live.get("native_identity")
        can_advance = (
            bool(history_complete)
            and history == HISTORY_COMPLETE
            and _text(row.get("reason")) != "CHANGE_HISTORY_GAP"
            and current_state not in {"UNAVAILABLE", "INVALID", "NOT_PRESENT"}
            and bool(live_at or live_id)
        )
        if can_advance:
            out[domain] = {
                "change_available_at": live_at,
                "native_identity": live_id,
            }
            continue
        kept = previous_sources.get(domain) if isinstance(previous_sources, Mapping) else None
        if isinstance(kept, Mapping):
            out[domain] = {
                "change_available_at": kept.get("change_available_at"),
                "native_identity": kept.get("native_identity"),
            }
        else:
            out[domain] = empty_watermark()
    return out
