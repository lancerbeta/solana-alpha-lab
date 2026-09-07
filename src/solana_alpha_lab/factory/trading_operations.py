"""Derived trading-operations owner projection. Owns no durable truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.paper_shadow_operations import (
    build_economics_projection,
    build_operations_projection,
)

SCHEMA = "smial.trading-operations-workbench"
STRATEGY_ROOT = "configs/strategies"
WATCHLIST_STATUS = "WATCHLIST_SOURCE_GAP"
ACTIVATION_PATH = "ACTIVATION_PATH_GAP"
STAGE_ORDER = (
    "SIGNAL_DECISION",
    "PRE_TRADE_RISK",
    "EXECUTION_INTENT",
    "EXECUTION_OBSERVATION",
    "POSITION",
    "EXIT",
    "RECONCILIATION",
)
EVENT_STAGE = {
    "SIGNAL_DECISION_ACCEPTED": "SIGNAL_DECISION",
    "PRE_TRADE_RISK_SNAPSHOT": "PRE_TRADE_RISK",
    "EXECUTION_INTENT_CREATED": "EXECUTION_INTENT",
    "PAPER_SIMULATION_OBSERVED": "EXECUTION_OBSERVATION",
    "SHADOW_EXECUTABLE_OBSERVED": "EXECUTION_OBSERVATION",
    "POSITION_TRANSITION": "POSITION",
    "PAPER_EXIT_OBSERVED": "EXIT",
    "SHADOW_EXIT_EXECUTABLE_OBSERVED": "EXIT",
    "EXIT_UNRESOLVED": "EXIT",
    "RECONCILIATION": "RECONCILIATION",
}
CLOSE_COMMANDS = frozenset({"REQUEST_CLOSE_POSITION", "REQUEST_CLOSE_ALL"})
COMMAND_SPECS = (
    (
        "PAUSE_NEW_ENTRIES",
        "bot_instance_id",
        "Bot PRESENT; not already the intended paused state",
        "entries_paused=true",
        "BOT_NOT_FOUND / SOURCE_NOT_PRESENT",
    ),
    (
        "RESUME_NEW_ENTRIES",
        "bot_instance_id",
        "Bot PRESENT and status != DRAINING",
        "entries_paused=false",
        "RESUME_FORBIDDEN_WHILE_DRAINING / SOURCE_NOT_PRESENT",
    ),
    (
        "REQUEST_CLOSE_POSITION",
        "position_id",
        "Position in OPEN|PARTIAL|UNKNOWN (EXIT_REQUIRED is idempotent)",
        "state=EXIT_REQUIRED; fill_claimed=false",
        "CLOSE_POSITION_STATE_INVALID / SOURCE_NOT_PRESENT",
    ),
    (
        "REQUEST_CLOSE_ALL",
        "bot_instance_id + expected_open_position_set_sha256",
        "Rendered open-set hash equals live inventory hash",
        "fanout close requests or hash mismatch with zero side effects",
        "hash mismatch / CLOSE_ALL_SNAPSHOT_REQUIRED",
    ),
    (
        "STOP_BOT",
        "bot_instance_id",
        "Bot PRESENT",
        "DRAINING while inventory remains; STOPPED only after drain-cleared",
        "BOT_NOT_FOUND / SOURCE_NOT_PRESENT",
    ),
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _payload(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("payload")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def list_git_strategies(root: Path) -> list[dict[str, Any]]:
    folder = root / STRATEGY_ROOT
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        strategy_id = _text(loaded.get("strategy_id"))
        if not strategy_id:
            continue
        rows.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": _text(loaded.get("strategy_version")),
                "schema_version": _text(loaded.get("schema_version")),
                "title": _text(loaded.get("title")),
                "path": path.relative_to(root).as_posix(),
                "runtime_status": "DEFINITION_ONLY",
            }
        )
    return rows


def _attention(
    code: str, *, why: str, impact: str, evidence: str, nxt: str
) -> dict[str, str]:
    return {
        "code": code,
        "WHY_NOW": why,
        "IMPACT": impact,
        "EVIDENCE": evidence,
        "NEXT_SAFE_ACTION": nxt,
    }


def _command_cards(operations: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    cards = []
    ops = operations or {}
    bot_id = _text(ops.get("bot"))
    snapshot = _text(ops.get("open_position_set_sha256"))
    status = _text(ops.get("status"))
    for name, target, precondition, expected, fail_closed in COMMAND_SPECS:
        offered = bool(bot_id) and not (
            name == "RESUME_NEW_ENTRIES" and status == "DRAINING"
        )
        cards.append(
            {
                "command_type": name,
                "target": target,
                "current_precondition": precondition,
                "expected_effect": expected,
                "fail_closed": fail_closed,
                "idempotency": "idempotency_key",
                "post_action_readback": "fresh TradingOperationsProjectionV2",
                "offered": offered,
                "bot_instance_id": bot_id or None,
                "expected_open_position_set_sha256": snapshot or None,
            }
        )
    return cards


def _join_key(event: Mapping[str, Any], position: Mapping[str, Any] | None) -> str:
    payload = _payload(event)
    signal_id = _text(payload.get("signal_decision_id"))
    if signal_id:
        return f"signal:{signal_id}"
    if position is not None:
        pos_signal = _text(position.get("signal_decision_id"))
        if pos_signal:
            return f"signal:{pos_signal}"
    position_id = _text(event.get("position_id") or (position or {}).get("position_id"))
    if position_id:
        return f"position:{position_id}"
    return ""


def _build_traces(store: Any) -> list[dict[str, Any]]:
    positions = {str(row["position_id"]): row for row in store.positions()}
    grouped: dict[str, dict[str, Any]] = {}
    for event in store.execution_events():
        payload = _payload(event)
        position = positions.get(_text(event.get("position_id")))
        key = _join_key(event, position)
        if not key:
            grouped.setdefault(
                f"legacy:{event.get('event_id')}",
                {
                    "join": "LEGACY_TRACE_GAP",
                    "signal_decision_id": None,
                    "position_id": event.get("position_id"),
                    "mint": payload.get("mint"),
                    "stages": {stage: "GAP" for stage in STAGE_ORDER},
                    "events": [],
                    "stop_stage": "SIGNAL_DECISION",
                    "blocker": "LEGACY_TRACE_GAP",
                },
            )
            grouped[f"legacy:{event.get('event_id')}"]["events"].append(
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "created_at": event.get("created_at"),
                    "stage": EVENT_STAGE.get(str(event.get("event_type")), "GAP"),
                }
            )
            continue
        bucket = grouped.setdefault(
            key,
            {
                "join": key,
                "signal_decision_id": None,
                "position_id": None,
                "strategy_id": None,
                "activation_epoch_id": None,
                "mint": None,
                "stages": {stage: "GAP" for stage in STAGE_ORDER},
                "events": [],
                "stop_stage": None,
                "blocker": None,
            },
        )
        for field, value in (
            ("signal_decision_id", payload.get("signal_decision_id") or (position or {}).get("signal_decision_id")),
            ("position_id", event.get("position_id") or (position or {}).get("position_id")),
            ("strategy_id", payload.get("strategy_id") or (position or {}).get("strategy_id")),
            (
                "activation_epoch_id",
                payload.get("activation_epoch_id") or (position or {}).get("activation_epoch_id"),
            ),
            ("mint", payload.get("mint") or (position or {}).get("mint")),
        ):
            if not bucket.get(field) and value not in {None, ""}:
                bucket[field] = value
        event_type = str(event.get("event_type") or "")
        stage = EVENT_STAGE.get(event_type)
        if event_type == "OPERATOR_COMMAND_APPLIED" and payload.get("command_type") in CLOSE_COMMANDS:
            stage = "EXIT"
        if stage:
            decision = payload.get("decision")
            if stage == "PRE_TRADE_RISK" and decision not in {None, "ALLOW"}:
                bucket["blocker"] = "RISK_BLOCK"
            bucket["stages"][stage] = "PROVEN"
        bucket["events"].append(
            {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "created_at": event.get("created_at"),
                "stage": stage or "GAP",
            }
        )
    traces: list[dict[str, Any]] = []
    for bucket in grouped.values():
        proven = [stage for stage in STAGE_ORDER if bucket["stages"][stage] == "PROVEN"]
        bucket["stop_stage"] = proven[-1] if proven else STAGE_ORDER[0]
        if bucket["blocker"] is None and bucket.get("join") == "LEGACY_TRACE_GAP":
            bucket["blocker"] = "LEGACY_TRACE_GAP"
        elif bucket["blocker"] is None and "PRE_TRADE_RISK" in proven and not any(
            bucket["stages"][stage] == "PROVEN"
            for stage in STAGE_ORDER[STAGE_ORDER.index("PRE_TRADE_RISK") + 1 :]
        ):
            pass
        elif bucket["blocker"] is None and not proven:
            bucket["blocker"] = "SIGNAL_TRACE_GAP"
        traces.append(bucket)
    traces.sort(key=lambda row: _text(row.get("signal_decision_id") or row.get("join")))
    return traces


def _contexts(
    git_strategies: list[dict[str, Any]], operations: Mapping[str, Any] | None
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    bots = list((operations or {}).get("bots") or [])
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for bot in bots:
        if not isinstance(bot, dict):
            continue
        by_strategy.setdefault(_text(bot.get("strategy_id")), []).append(bot)
    attention: list[dict[str, str]] = []
    contexts: list[dict[str, Any]] = []
    seen_runtime: set[str] = set()
    for spec in git_strategies:
        strategy_id = spec["strategy_id"]
        matches = by_strategy.get(strategy_id) or []
        if not matches:
            contexts.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_version": spec["strategy_version"],
                    "mode": None,
                    "activation_epoch_id": None,
                    "bot_instance_id": None,
                    "bot_status": "NOT_ACTIVATED",
                    "entries_paused": None,
                    "started_at": None,
                    "stopped_at": None,
                    "open_risk_count": 0,
                    "relation": "ACTIVATION_GAP",
                    "current_blocker": "ACTIVATION_GAP",
                    "next_safe_action": "INSPECT_ACTIVATION_PATH_GAP",
                }
            )
            attention.append(
                _attention(
                    "ACTIVATION_GAP",
                    why=f"Git StrategyVersion {strategy_id} has no runtime bot",
                    impact="Definition exists; nothing is executing",
                    evidence=spec["path"],
                    nxt="Do not infer a running bot; activation is not created here",
                )
            )
            continue
        for bot in matches:
            seen_runtime.add(_text(bot.get("bot_instance_id")))
            contexts.append(_bot_context(bot, operations, relation="EXPLICIT"))
    for bot in bots:
        if not isinstance(bot, dict):
            continue
        bot_id = _text(bot.get("bot_instance_id"))
        if bot_id in seen_runtime:
            continue
        contexts.append(_bot_context(bot, operations, relation="RUNTIME_ONLY"))
    return contexts, attention


def _count_states(rows: list[Mapping[str, Any]], states: set[str]) -> int:
    return sum(1 for row in rows if str(row.get("state") or "") in states)


def _bot_context(
    bot: Mapping[str, Any], operations: Mapping[str, Any] | None, *, relation: str
) -> dict[str, Any]:
    ops = operations or {}
    bot_id = _text(bot.get("bot_instance_id"))
    rows = [
        row
        for row in list(ops.get("position_rows") or [])
        if isinstance(row, dict) and _text(row.get("bot_instance_id")) == bot_id
    ]
    unknown = _count_states(rows, {"UNKNOWN"})
    exit_required = _count_states(rows, {"EXIT_REQUIRED", "EXITING"})
    unresolved = _count_states(rows, {"UNRESOLVED"})
    open_positions = _count_states(rows, {"OPEN"})
    partial = _count_states(rows, {"PARTIAL"})
    status = _text(bot.get("status"))
    paused = bool(int(bot.get("entries_paused") or 0))
    blocker = None
    nxt = "OBSERVE"
    if status == "DRAINING":
        blocker = "BOT_DRAINING"
        nxt = "Wait until inventory is drain-cleared"
    elif paused:
        blocker = "ENTRIES_PAUSED"
        nxt = "RESUME_NEW_ENTRIES when DRAINING is false"
    elif unknown:
        blocker = "POSITION_UNKNOWN"
        nxt = "Inspect mark evidence; UNKNOWN is not zero"
    elif exit_required:
        blocker = "EXIT_REQUIRED"
        nxt = "REQUEST_CLOSE_POSITION / wait for exit observation"
    elif unresolved:
        blocker = "UNRESOLVED_POSITION"
        nxt = "Keep DRAINING; STOPPED is forbidden"
    return {
        "strategy_id": bot.get("strategy_id"),
        "strategy_version": bot.get("strategy_version"),
        "mode": bot.get("mode"),
        "activation_epoch_id": bot.get("activation_epoch_id"),
        "bot_instance_id": bot.get("bot_instance_id"),
        "bot_status": status or "UNKNOWN",
        "entries_paused": paused,
        "started_at": bot.get("started_at"),
        "stopped_at": bot.get("stopped_at"),
        "open_risk_count": open_positions + partial + unknown,
        "open_positions": open_positions,
        "partial_positions": partial,
        "unknown_positions": unknown,
        "exit_required": exit_required,
        "unresolved_positions": unresolved,
        "relation": relation,
        "current_blocker": blocker,
        "next_safe_action": nxt,
    }


def compose_trading_operations(
    root: Path,
    store: Any | None,
    *,
    last_command: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    git_strategies = list_git_strategies(root)
    if store is None:
        contexts, activation_attention = _contexts(git_strategies, None)
        attention = [
            _attention(
                "SOURCE_NOT_PRESENT",
                why="PaperPlane runtime store is absent",
                impact="No bot, position or command truth is available",
                evidence="local/factory_v1/paper_plane_state.sqlite missing",
                nxt="Do not bootstrap runtime from GET; command fail-closes",
            )
        ] + activation_attention
        return {
            "schema": SCHEMA,
            "source_status": "NOT_PRESENT",
            "git_strategies": git_strategies,
            "contexts": contexts,
            "operations": None,
            "economics": None,
            "traces": [],
            "attention": attention,
            "commands": _command_cards(None),
            "recent_changes": [],
            "watchlist_status": WATCHLIST_STATUS,
            "activation_path": ACTIVATION_PATH,
            "last_command": dict(last_command) if last_command else None,
            "non_claims": [
                "NO_ALPHA",
                "NO_LIVE",
                "NO_REAL_MONEY",
                "NO_OWNER_FCF",
                "NO_DEPLOY",
                "NO_PROVIDER",
                "NO_WALLET",
            ],
        }
    operations = build_operations_projection(store)
    economics = build_economics_projection(store, operations=operations)
    contexts, activation_attention = _contexts(git_strategies, operations)
    traces = _build_traces(store)
    attention = list(operations.get("attention") or []) + activation_attention
    if any(row.get("blocker") == "RISK_BLOCK" for row in traces):
        attention.append(
            _attention(
                "RISK_BLOCK",
                why="Pre-trade risk did not ALLOW",
                impact="No position is fabricated from a blocked signal",
                evidence="PRE_TRADE_RISK_SNAPSHOT.decision!=ALLOW",
                nxt="Inspect reason_code; do not infer a fill",
            )
        )
    if any(row.get("join") == "LEGACY_TRACE_GAP" for row in traces):
        attention.append(
            _attention(
                "SIGNAL_TRACE_GAP",
                why="An execution event cannot join by signal_decision_id",
                impact="Stage is GAP, not an inferred transition",
                evidence="LEGACY_TRACE_GAP",
                nxt="Use forward-going events with explicit identity",
            )
        )
    attention.append(
        _attention(
            WATCHLIST_STATUS,
            why="No canonical pre-signal watch source is bound",
            impact="Watchlist is not mocked",
            evidence=WATCHLIST_STATUS,
            nxt="Do not invent watchlist storage in this atom",
        )
    )
    return {
        "schema": SCHEMA,
        "source_status": "PRESENT",
        "git_strategies": git_strategies,
        "contexts": contexts,
        "operations": operations,
        "economics": economics,
        "traces": traces,
        "attention": attention,
        "commands": _command_cards(operations),
        "recent_changes": list(reversed(store.execution_events()[-12:])),
        "watchlist_status": WATCHLIST_STATUS,
        "activation_path": ACTIVATION_PATH,
        "last_command": dict(last_command) if last_command else None,
        "non_claims": [
            "NO_ALPHA",
            "NO_LIVE",
            "NO_REAL_MONEY",
            "NO_OWNER_FCF",
            "NO_DEPLOY",
            "NO_PROVIDER",
            "NO_WALLET",
        ],
    }
