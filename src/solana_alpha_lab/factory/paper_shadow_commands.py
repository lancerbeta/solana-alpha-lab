"""Bounded PAPER/SHADOW operator commands over PaperPlaneStore. No UI truth."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Mapping

from solana_alpha_lab.factory.paper_plane import PaperPlaneError, PaperPlaneStore
from solana_alpha_lab.factory.paper_shadow_operations import open_position_set_sha256

ACTIVE_INVENTORY = frozenset(
    {
        "WATCHED",
        "SIGNALLED",
        "INTENT_CREATED",
        "ATTEMPTING",
        "OPEN",
        "PARTIAL",
        "UNKNOWN",
        "EXIT_REQUIRED",
        "EXITING",
        "UNRESOLVED",
    }
)
CLOSEABLE = frozenset({"OPEN", "PARTIAL", "UNKNOWN"})
# Operator open-set excludes settled lifecycle ends.
TERMINAL_SETTLED = frozenset({"CLOSED", "RECONCILED"})
# STOP/DRAIN completes only after reconcile (CLOSED alone still needs work).
DRAIN_CLEARED = frozenset({"RECONCILED"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _inventory_position_ids(store: PaperPlaneStore, bot_instance_id: str | None) -> list[str]:
    rows = store.positions()
    out: list[str] = []
    for row in rows:
        if bot_instance_id is not None and row["bot_instance_id"] != bot_instance_id:
            continue
        if str(row["state"]) not in TERMINAL_SETTLED:
            out.append(str(row["position_id"]))
    return sorted(out)


def _drain_remaining_ids(store: PaperPlaneStore, bot_instance_id: str) -> list[str]:
    rows = store.positions()
    out: list[str] = []
    for row in rows:
        if row["bot_instance_id"] != bot_instance_id:
            continue
        if str(row["state"]) not in DRAIN_CLEARED:
            out.append(str(row["position_id"]))
    return sorted(out)


def apply_operator_command(
    store: PaperPlaneStore,
    command: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply one idempotent operator command.

    Required keys: command_type, idempotency_key
    Optional: bot_instance_id, position_id, expected_open_position_set_sha256
    """

    command_type = str(command["command_type"])
    idempotency_key = str(command["idempotency_key"])
    if not idempotency_key:
        raise PaperPlaneError("COMMAND_IDEMPOTENCY_KEY_REQUIRED")

    existing = store.get_operator_command(idempotency_key)
    if existing is not None:
        payload = json.loads(existing["result_json"])
        payload["idempotent"] = True
        payload["idempotency_key"] = idempotency_key
        return payload

    if command_type == "PAUSE_NEW_ENTRIES":
        bot_id = str(command["bot_instance_id"])
        store.set_entries_paused(bot_id, paused=True)
        result = {
            "command_type": command_type,
            "status": "APPLIED",
            "bot_instance_id": bot_id,
            "entries_paused": True,
        }
    elif command_type == "RESUME_NEW_ENTRIES":
        bot_id = str(command["bot_instance_id"])
        bot = store.get_bot(bot_id)
        if bot is None:
            raise PaperPlaneError("BOT_NOT_FOUND")
        if str(bot.get("status")) == "DRAINING":
            raise PaperPlaneError("RESUME_FORBIDDEN_WHILE_DRAINING")
        store.set_entries_paused(bot_id, paused=False)
        result = {
            "command_type": command_type,
            "status": "APPLIED",
            "bot_instance_id": bot_id,
            "entries_paused": False,
        }
    elif command_type == "REQUEST_CLOSE_POSITION":
        position_id = str(command["position_id"])
        position = store.get_position(position_id)
        if position is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        state = str(position["state"])
        if state in CLOSEABLE:
            store.transition(position_id, "EXIT_REQUIRED")
            store.append_execution_event(
                event_type="OPERATOR_COMMAND_APPLIED",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={"command_type": command_type, "from_state": state},
            )
            applied = True
            new_state = "EXIT_REQUIRED"
        elif state == "EXIT_REQUIRED":
            applied = True
            new_state = state
        else:
            raise PaperPlaneError(f"CLOSE_POSITION_STATE_INVALID:{state}")
        result = {
            "command_type": command_type,
            "status": "APPLIED",
            "position_id": position_id,
            "state": new_state,
            "fill_claimed": False,
            "applied": applied,
        }
    elif command_type == "REQUEST_CLOSE_ALL":
        bot_id = command.get("bot_instance_id")
        bot_filter = None if bot_id in {None, "ALL"} else str(bot_id)
        expected = command.get("expected_open_position_set_sha256")
        if not expected:
            raise PaperPlaneError("CLOSE_ALL_SNAPSHOT_REQUIRED")
        live_ids = _inventory_position_ids(store, bot_filter)
        live_sha = open_position_set_sha256(live_ids)
        if str(expected) != live_sha:
            result = {
                "command_type": command_type,
                "status": "STALE_OPERATOR_SNAPSHOT",
                "expected_open_position_set_sha256": str(expected),
                "live_open_position_set_sha256": live_sha,
                "fanout": [],
                "side_effects": 0,
            }
            store.record_operator_command(
                idempotency_key=idempotency_key,
                command_type=command_type,
                request=command,
                result=result,
            )
            return {**result, "idempotent": False, "idempotency_key": idempotency_key}
        fanout: list[dict[str, Any]] = []
        for position_id in live_ids:
            position = store.get_position(position_id)
            assert position is not None
            state = str(position["state"])
            if state in CLOSEABLE:
                store.transition(position_id, "EXIT_REQUIRED")
                store.append_execution_event(
                    event_type="OPERATOR_COMMAND_APPLIED",
                    bot_instance_id=str(position["bot_instance_id"]),
                    position_id=position_id,
                    payload={"command_type": command_type, "from_state": state},
                )
                fanout.append({"position_id": position_id, "state": "EXIT_REQUIRED"})
            elif state in {"EXIT_REQUIRED", "EXITING", "UNRESOLVED"}:
                fanout.append({"position_id": position_id, "state": state, "already": True})
            else:
                fanout.append(
                    {
                        "position_id": position_id,
                        "state": state,
                        "skipped": "PREOPEN_NO_EXIT_INTENT",
                    }
                )
        result = {
            "command_type": command_type,
            "status": "APPLIED",
            "expected_open_position_set_sha256": str(expected),
            "live_open_position_set_sha256": live_sha,
            "fanout": fanout,
            "side_effects": sum(
                1
                for item in fanout
                if not item.get("already") and not item.get("skipped")
            ),
            "fill_claimed": False,
        }
    elif command_type == "STOP_BOT":
        bot_id = str(command["bot_instance_id"])
        bot = store.get_bot(bot_id)
        if bot is None:
            raise PaperPlaneError("BOT_NOT_FOUND")
        inventory = _drain_remaining_ids(store, bot_id)
        store.set_entries_paused(bot_id, paused=True)
        if inventory:
            store.set_bot_status(bot_id, "DRAINING")
            status = "DRAINING"
        else:
            store.set_bot_status(bot_id, "STOPPED", stopped_at=_now())
            status = "STOPPED"
        store.append_execution_event(
            event_type="OPERATOR_COMMAND_APPLIED",
            bot_instance_id=bot_id,
            position_id=None,
            payload={"command_type": command_type, "status": status},
        )
        result = {
            "command_type": command_type,
            "status": "APPLIED",
            "bot_instance_id": bot_id,
            "bot_status": status,
            "remaining_inventory": inventory,
        }
    else:
        raise PaperPlaneError(f"COMMAND_TYPE_INVALID:{command_type}")

    store.record_operator_command(
        idempotency_key=idempotency_key,
        command_type=command_type,
        request=command,
        result=result,
    )
    return {**result, "idempotent": False, "idempotency_key": idempotency_key}


def maybe_finish_drain(store: PaperPlaneStore, bot_instance_id: str) -> dict[str, Any]:
    bot = store.get_bot(bot_instance_id)
    if bot is None:
        raise PaperPlaneError("BOT_NOT_FOUND")
    if str(bot.get("status")) != "DRAINING":
        return {"bot_status": bot.get("status"), "changed": False}
    inventory = _drain_remaining_ids(store, bot_instance_id)
    if inventory:
        return {"bot_status": "DRAINING", "changed": False, "remaining_inventory": inventory}
    store.set_bot_status(bot_instance_id, "STOPPED", stopped_at=_now())
    return {"bot_status": "STOPPED", "changed": True, "remaining_inventory": []}
