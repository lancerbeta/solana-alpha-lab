"""OwnerAttentionProjectionV1. Derived only. Persists nowhere."""

from __future__ import annotations

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


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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
        return ""
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
            "SYSTEM": "FACTORY_V1_RUNTIME_PROJECTION",
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


def _from_local_attention(
    rows: Any, *, source_domain: str, source_status: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _text(row.get("code") or row.get("id") or row.get("blocker"))
        if not code:
            continue
        item = _item(
            source_domain=source_domain,
            code=code,
            native_identity=_text(
                row.get("source_native_identity")
                or row.get("entity_id")
                or row.get("position_id")
                or row.get("bot_instance_id")
                or code
            ),
            why=_text(row.get("WHY_NOW") or row.get("title")),
            impact=_text(row.get("IMPACT")),
            evidence=_text(row.get("EVIDENCE") or row.get("native_state")),
            nxt=_text(row.get("NEXT_SAFE_ACTION") or row.get("next_safe_action")),
            available_at=_text(row.get("observed_at") or row.get("as_of")) or None,
            source_status=source_status,
        )
        if item:
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


def _research_coverage(research: Mapping[str, Any] | None, discovery: str | None) -> dict[str, Any]:
    if research is None:
        status = discovery or "NOT_PRESENT"
        history = "NOT_PRESENT" if status == "NOT_PRESENT" else "UNAVAILABLE"
        if status == "INVALID":
            history = "UNAVAILABLE"
        return _coverage_row("RESEARCH", current=status, history=history)
    sources = research.get("sources") if isinstance(research.get("sources"), list) else []
    statuses = [
        _text(item.get("status"))
        for item in sources
        if isinstance(item, dict) and _text(item.get("status"))
    ]
    if any(item in {"UNAVAILABLE", "INVALID"} for item in statuses):
        current = "INVALID" if "INVALID" in statuses else "UNAVAILABLE"
        return _coverage_row("RESEARCH", current=current, history="UNAVAILABLE")
    if any(item == "NOT_PRESENT" for item in statuses) and not any(
        item in {"AVAILABLE", "EMPTY"} for item in statuses
    ):
        return _coverage_row("RESEARCH", current="NOT_PRESENT", history="NOT_PRESENT")
    if statuses and all(item in {"AVAILABLE", "EMPTY"} for item in statuses):
        return _coverage_row("RESEARCH", current="AVAILABLE", history="AVAILABLE")
    if statuses:
        return _coverage_row("RESEARCH", current="PARTIAL", history="AVAILABLE")
    return _coverage_row("RESEARCH", current="AVAILABLE", history="AVAILABLE")


def _operations_coverage(trading: Mapping[str, Any] | None) -> dict[str, Any]:
    status = _text((trading or {}).get("source_status") or "NOT_PRESENT") or "NOT_PRESENT"
    if status == "PRESENT":
        return _coverage_row("OPERATIONS", current="AVAILABLE", history="AVAILABLE")
    if status == "NOT_PRESENT":
        return _coverage_row("OPERATIONS", current="NOT_PRESENT", history="NOT_PRESENT")
    if status == "UNAVAILABLE":
        return _coverage_row("OPERATIONS", current="UNAVAILABLE", history="UNAVAILABLE")
    return _coverage_row("OPERATIONS", current="INVALID", history="UNAVAILABLE")


def _system_coverage(runtime: Mapping[str, Any] | None) -> dict[str, Any]:
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
        available = _text(event.get("created_at")) or None
        if not event_id:
            continue
        out.append(
            {
                "source_domain": "OPERATIONS",
                "native_identity": event_id,
                "change_available_at": available,
                "effective_at": _text(event.get("effective_at")) or available,
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
        available = _text(record.get("first_reliable_available_at")) or None
        if not identity:
            continue
        out.append(
            {
                "source_domain": "RESEARCH",
                "native_identity": identity,
                "change_available_at": available,
                "effective_at": _text(record.get("effective_at")) or None,
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


def _watermark_tuple(available: str | None, identity: str | None) -> tuple[str, str]:
    return (available or "", identity or "")


def _after_cursor(
    change: Mapping[str, Any], watermark: Mapping[str, Any] | None
) -> bool:
    mark = watermark or empty_watermark()
    return _watermark_tuple(change.get("change_available_at"), change.get("native_identity")) > _watermark_tuple(
        mark.get("change_available_at"), mark.get("native_identity")
    )


def _source_watermark(changes: list[Mapping[str, Any]]) -> dict[str, str | None]:
    best = empty_watermark()
    best_tuple = ("", "")
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


def compose_owner_attention(
    *,
    research: Mapping[str, Any] | None = None,
    trading: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    cockpit: Mapping[str, Any] | None = None,
    research_records: list[dict[str, Any]] | None = None,
    research_discovery: str | None = None,
    cursor: Mapping[str, Any] | None = None,
    cursor_status: str = "MISSING",
) -> dict[str, Any]:
    coverage = {
        "RESEARCH": _research_coverage(research, research_discovery),
        "OPERATIONS": _operations_coverage(trading),
        "SYSTEM": _system_coverage(runtime),
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
    current = [item for item in current if item.get("attention_code") not in NOISE_CODES]
    current = _dedup(current)

    changes: list[dict[str, Any]] = []
    if coverage["RESEARCH"]["CHANGE_HISTORY"] == "AVAILABLE":
        changes.extend(_research_changes(research_records))
    if coverage["OPERATIONS"]["CHANGE_HISTORY"] == "AVAILABLE":
        changes.extend(_operations_changes(trading))

    watermarks = {
        "RESEARCH": _source_watermark(
            [item for item in changes if item["source_domain"] == "RESEARCH"]
        ),
        "OPERATIONS": _source_watermark(
            [item for item in changes if item["source_domain"] == "OPERATIONS"]
        ),
        "SYSTEM": empty_watermark(),
    }
    snapshot = {
        "schema": "smial.owner-review-snapshot",
        "schema_version": "1.0",
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

    cursor_sources = (cursor or {}).get("sources") if isinstance(cursor, Mapping) else {}
    established = cursor_status == "VALID" and isinstance(cursor_sources, dict)
    history_gap = False
    new_changes: list[dict[str, Any]] = []
    if coverage["RESEARCH"]["CHANGE_HISTORY"] != "AVAILABLE" and coverage["OPERATIONS"]["CHANGE_HISTORY"] != "AVAILABLE":
        pass
    for change in changes:
        domain = change["source_domain"]
        if coverage[domain]["CHANGE_HISTORY"] != "AVAILABLE":
            continue
        mark = cursor_sources.get(domain) if established else None
        if established and mark and (
            (mark.get("change_available_at") or "")
            and all(
                _watermark_tuple(item.get("change_available_at"), item.get("native_identity"))
                < _watermark_tuple(mark.get("change_available_at"), mark.get("native_identity"))
                for item in changes
                if item["source_domain"] == domain
            )
        ):
            history_gap = True
        is_new = (not established) or _after_cursor(change, mark if isinstance(mark, dict) else None)
        if not is_new:
            continue
        item = _item(
            source_domain=domain,
            code=change.get("attention_code") or "CHANGE",
            native_identity=change["native_identity"],
            why=change.get("WHY_NOW") or "",
            impact="INFO",
            evidence=change.get("EVIDENCE") or "",
            nxt=change.get("NEXT_SAFE_ACTION") or "",
            available_at=change.get("change_available_at"),
            effective_at=change.get("effective_at"),
            source_status=coverage[domain]["CURRENT_STATE"],
            change_kind=change.get("change_kind"),
        )
        if not item:
            item = {
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
                "source_status": coverage[domain]["CURRENT_STATE"],
                "drilldown_target": change.get("drilldown_target"),
                "change_kind": change.get("change_kind"),
                "new_since_review": True,
            }
        else:
            item["new_since_review"] = True
            item["priority"] = "INFO"
        new_changes.append(item)

    by_native: dict[tuple[str, str], dict[str, Any]] = {}
    for item in current:
        by_native[(item["source_domain"], item["source_native_identity"])] = item
    for change in new_changes:
        key = (change["source_domain"], change["source_native_identity"])
        if key in by_native:
            by_native[key]["new_since_review"] = True
            change["merged_into_current"] = True

    current = _dedup(list(by_native.values()) if by_native else current)
    visible_changes = [
        item for item in new_changes if not item.get("merged_into_current")
    ]

    def _sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
        return (
            PRIORITY_RANK.get(str(item.get("priority")), 9),
            _text(item.get("available_at")),
            _text(item.get("attention_key")),
        )

    current.sort(key=_sort_key)
    visible_changes.sort(key=_sort_key)
    material = [item for item in current if item.get("priority") in {"P0", "P1", "P2", "UNKNOWN"}]
    info = [item for item in current if item.get("priority") == "INFO"] + visible_changes
    info = _dedup(info)

    review_code = None
    if cursor_status == "MISSING":
        review_code = "REVIEW_BASELINE_NOT_ESTABLISHED"
    elif cursor_status == "INVALID":
        review_code = "REVIEW_CURSOR_INVALID"
    elif history_gap:
        review_code = "CHANGE_HISTORY_GAP"

    all_clear = not material
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
    out: dict[str, dict[str, str | None]] = {}
    for domain in SOURCE_DOMAINS:
        row = by_domain.get(domain) or {}
        history = _text(row.get("CHANGE_HISTORY"))
        current_state = _text(row.get("CURRENT_STATE"))
        live = sources.get(domain) if isinstance(sources.get(domain), Mapping) else {}
        can_advance = history == "AVAILABLE" and current_state not in {
            "UNAVAILABLE",
            "INVALID",
            "NOT_PRESENT",
        }
        if can_advance:
            out[domain] = {
                "change_available_at": live.get("change_available_at"),
                "native_identity": live.get("native_identity"),
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
