"""Derived PAPER/SHADOW operations projection. Owns no truth."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from solana_alpha_lab.factory.paper_plane import OPEN_RISK_STATES, PaperPlaneStore

OPEN_LIKE = frozenset({"OPEN", "PARTIAL"})
UNKNOWN_LIKE = frozenset({"UNKNOWN"})
EXIT_REQUIRED_LIKE = frozenset({"EXIT_REQUIRED", "EXITING"})
UNRESOLVED_LIKE = frozenset({"UNRESOLVED"})
TERMINAL_SETTLED = frozenset({"CLOSED", "RECONCILED"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def open_position_set_sha256(position_ids: list[str]) -> str:
    ordered = sorted(position_ids)
    payload = json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def position_pnl_view(position: dict[str, Any]) -> dict[str, Any]:
    """Map store columns to operator pnl_status / net_pnl_usd."""

    state = str(position.get("state"))
    evidence = position.get("pnl_evidence_class")
    net = position.get("realized_net_pnl_usd_dec")
    if state == "RECONCILED" and net is not None and evidence:
        return {
            "net_pnl_usd": format(Decimal(str(net)), "f"),
            "pnl_status": "KNOWN",
            "pnl_evidence_class": evidence,
        }
    if state in {"RECONCILED", "CLOSED", "UNRESOLVED"} and net is None:
        return {
            "net_pnl_usd": None,
            "pnl_status": "UNKNOWN",
            "pnl_evidence_class": evidence,
        }
    if state in OPEN_LIKE | UNKNOWN_LIKE | EXIT_REQUIRED_LIKE:
        mark_class = position.get("unrealized_evidence_class")
        if mark_class == "UNKNOWN" or position.get("mark_price_dec") is None:
            return {
                "net_pnl_usd": None,
                "pnl_status": "UNKNOWN",
                "pnl_evidence_class": mark_class or evidence,
            }
        if position.get("mark_as_of") in {None, ""}:
            return {
                "net_pnl_usd": None,
                "pnl_status": "UNKNOWN",
                "pnl_evidence_class": mark_class or evidence,
            }
        unreal = position.get("unrealized_net_pnl_usd_dec")
        return {
            "net_pnl_usd": None if unreal is None else format(Decimal(str(unreal)), "f"),
            "pnl_status": "UNKNOWN" if unreal is None else "MARK",
            "pnl_evidence_class": mark_class or evidence,
        }
    return {
        "net_pnl_usd": None if net is None else format(Decimal(str(net)), "f"),
        "pnl_status": "UNKNOWN" if net is None else "KNOWN",
        "pnl_evidence_class": evidence,
    }


def compute_loss_streak(reconciled_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Trailing reconciled outcomes only. UNKNOWN status when latest PnL unknown."""

    if not reconciled_rows:
        return {
            "current_loss_streak_status": "KNOWN",
            "current_loss_streak_count": 0,
        }
    latest = reconciled_rows[-1]
    if latest.get("pnl_status") == "UNKNOWN" or latest.get("net_pnl_usd") is None:
        return {
            "current_loss_streak_status": "UNKNOWN",
            "current_loss_streak_count": None,
        }
    streak = 0
    for row in reversed(reconciled_rows):
        if row.get("pnl_status") == "UNKNOWN" or row.get("net_pnl_usd") is None:
            break
        pnl = _dec(row["net_pnl_usd"])
        assert pnl is not None
        if pnl < 0:
            streak += 1
            continue
        break
    return {
        "current_loss_streak_status": "KNOWN",
        "current_loss_streak_count": streak,
    }


def compute_max_drawdown_usd(reconciled_rows: list[dict[str, Any]]) -> str | None:
    """Drawdown over cumulative known reconciled model PnL (USD string)."""

    known = [
        row
        for row in reconciled_rows
        if row.get("pnl_status") != "UNKNOWN" and row.get("net_pnl_usd") is not None
    ]
    if not known:
        return None
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    for row in known:
        pnl = _dec(row["net_pnl_usd"])
        assert pnl is not None
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return format(max_dd, "f")


def build_operations_projection(
    store: PaperPlaneStore,
    *,
    as_of: str | None = None,
    bot_instance_id: str | None = None,
) -> dict[str, Any]:
    as_of_value = as_of or _now()
    bots = store.bots()
    if bot_instance_id is not None:
        bots = [b for b in bots if b["bot_instance_id"] == bot_instance_id]
    positions = store.positions()
    if bot_instance_id is not None:
        positions = [p for p in positions if p["bot_instance_id"] == bot_instance_id]

    open_ids = [
        str(p["position_id"])
        for p in positions
        if str(p["state"]) not in TERMINAL_SETTLED
    ]
    open_ids_by_bot: dict[str, list[str]] = {}
    for bot in bots:
        open_ids_by_bot[str(bot["bot_instance_id"])] = []
    for p in positions:
        if str(p["state"]) in TERMINAL_SETTLED:
            continue
        open_ids_by_bot.setdefault(str(p["bot_instance_id"]), []).append(
            str(p["position_id"])
        )

    reconciled_raw = [p for p in positions if str(p["state"]) == "RECONCILED"]
    reconciled_raw.sort(
        key=lambda p: (str(p.get("closed_at") or ""), str(p.get("opened_at") or ""), str(p["position_id"]))
    )
    reconciled = []
    for p in reconciled_raw:
        view = position_pnl_view(p)
        reconciled.append(
            {
                "position_id": p["position_id"],
                "net_pnl_usd": view["net_pnl_usd"],
                "pnl_status": view["pnl_status"],
                "pnl_evidence_class": view["pnl_evidence_class"],
                "closed_at": p.get("closed_at"),
            }
        )

    streak = compute_loss_streak(reconciled)

    known_pnl = [
        _dec(row["net_pnl_usd"])
        for row in reconciled
        if row.get("pnl_status") != "UNKNOWN" and row.get("net_pnl_usd") is not None
    ]
    unknown_reconciled = any(
        row.get("pnl_status") == "UNKNOWN" or row.get("net_pnl_usd") is None for row in reconciled
    )
    if not reconciled:
        reconciled_net = None
        reconciled_net_status = "EMPTY"
    elif unknown_reconciled and not known_pnl:
        reconciled_net = None
        reconciled_net_status = "UNKNOWN"
    elif unknown_reconciled:
        reconciled_net = sum(known_pnl, Decimal("0"))
        reconciled_net_status = "PARTIAL_KNOWN"
    else:
        reconciled_net = sum(known_pnl, Decimal("0"))
        reconciled_net_status = "KNOWN"

    max_dd = compute_max_drawdown_usd(reconciled) if known_pnl else None
    if not reconciled:
        max_dd_status = "EMPTY"
    elif not known_pnl:
        max_dd_status = "UNKNOWN"
    elif unknown_reconciled:
        max_dd_status = "PARTIAL_KNOWN"
    else:
        max_dd_status = "KNOWN"

    known_open_exposure = Decimal("0")
    known_open_exposure_status = "KNOWN"
    open_priced = 0
    open_unpriced = 0
    for p in positions:
        if str(p["state"]) in TERMINAL_SETTLED:
            continue
        if str(p["state"]) in UNKNOWN_LIKE or not p.get("entry_price_dec"):
            open_unpriced += 1
            known_open_exposure_status = "PARTIAL_KNOWN"
            continue
        notional = _dec(p.get("entered_notional_usd_dec"))
        if notional is None:
            open_unpriced += 1
            known_open_exposure_status = "PARTIAL_KNOWN"
            continue
        known_open_exposure += notional
        open_priced += 1
    if open_priced == 0 and open_unpriced > 0:
        known_open_exposure_status = "UNKNOWN"
    elif open_priced == 0 and open_unpriced == 0:
        known_open_exposure_status = "EMPTY"

    attention: list[dict[str, str]] = []
    if any(str(p["state"]) in UNKNOWN_LIKE for p in positions):
        attention.append(
            {
                "code": "POSITION_UNKNOWN",
                "WHY_NOW": "At least one position is in UNKNOWN state",
                "IMPACT": "PnL/exposure may be incomplete",
                "EVIDENCE": "positions.state=UNKNOWN",
                "NEXT_SAFE_ACTION": "INSPECT_MARK",
            }
        )
    if any(str(p["state"]) in EXIT_REQUIRED_LIKE for p in positions):
        attention.append(
            {
                "code": "EXIT_REQUIRED",
                "WHY_NOW": "Exit requested but not settled",
                "IMPACT": "Inventory still open/unresolved",
                "EVIDENCE": "positions.state in EXIT_REQUIRED|EXITING",
                "NEXT_SAFE_ACTION": "REQUEST_CLOSE_OR_WAIT_EXIT",
            }
        )
    if any(str(p["state"]) in UNRESOLVED_LIKE for p in positions):
        attention.append(
            {
                "code": "UNRESOLVED_POSITION",
                "WHY_NOW": "Unresolved inventory remains",
                "IMPACT": "Cannot treat bot as stopped",
                "EVIDENCE": "positions.state=UNRESOLVED",
                "NEXT_SAFE_ACTION": "KEEP_DRAINING",
            }
        )
    decision_states = {
        "OPEN",
        "PARTIAL",
        "UNKNOWN",
        "EXIT_REQUIRED",
        "EXITING",
        "UNRESOLVED",
        "CLOSED",
        "RECONCILED",
    }
    if any(
        position_pnl_view(p)["pnl_status"] == "UNKNOWN"
        and str(p["state"]) in decision_states
        for p in positions
    ):
        attention.append(
            {
                "code": "PNL_UNKNOWN_OR_STALE",
                "WHY_NOW": "Known inventory lacks a known mark or reconciled PnL",
                "IMPACT": "Exposure/PnL cannot be treated as zero",
                "EVIDENCE": "pnl_status=UNKNOWN",
                "NEXT_SAFE_ACTION": "INSPECT_MARK",
            }
        )
    if streak.get("current_loss_streak_status") == "KNOWN" and int(
        streak.get("current_loss_streak_count") or 0
    ) > 0:
        attention.append(
            {
                "code": "LOSS_STREAK",
                "WHY_NOW": f"Trailing loss streak={streak['current_loss_streak_count']}",
                "IMPACT": "Operator risk attention",
                "EVIDENCE": "reconciled net_pnl sequence",
                "NEXT_SAFE_ACTION": "REVIEW_PAUSE_CLOSE_POLICY",
            }
        )

    bot = bots[0] if len(bots) == 1 else None
    for b in bots:
        if str(b.get("status")) == "DRAINING":
            attention.append(
                {
                    "code": "BOT_DRAINING",
                    "WHY_NOW": "Bot stop requested with remaining inventory",
                    "IMPACT": "Entries blocked; exits continue",
                    "EVIDENCE": f"bot.status=DRAINING:{b['bot_instance_id']}",
                    "NEXT_SAFE_ACTION": "WAIT_DRAIN",
                }
            )
        if int(b.get("entries_paused") or 0) == 1:
            attention.append(
                {
                    "code": "ENTRIES_PAUSED",
                    "WHY_NOW": "New entries paused",
                    "IMPACT": "ENTER blocked; exits continue",
                    "EVIDENCE": f"entries_paused=1:{b['bot_instance_id']}",
                    "NEXT_SAFE_ACTION": "RESUME_WHEN_NOT_DRAINING",
                }
            )

    position_rows = []
    for p in positions:
        view = position_pnl_view(p)
        position_rows.append(
            {
                "position_id": p["position_id"],
                "bot_instance_id": p["bot_instance_id"],
                "strategy_id": p.get("strategy_id"),
                "strategy_version": p.get("strategy_version_label"),
                "activation_epoch_id": p.get("activation_epoch_id"),
                "mint": p["mint"],
                "state": p["state"],
                "opened_at": p.get("opened_at"),
                "closed_at": p.get("closed_at"),
                "entered_notional_usd": None
                if p.get("entered_notional_usd_dec") is None
                else format(Decimal(str(p["entered_notional_usd_dec"])), "f"),
                "net_pnl_usd": view["net_pnl_usd"],
                "pnl_status": view["pnl_status"],
                "pnl_evidence_class": view["pnl_evidence_class"],
                "exit_decision_id": p.get("exit_decision_id"),
            }
        )

    return {
        "as_of": as_of_value,
        "strategy": bot.get("strategy_id") if bot else None,
        "strategy_version": bot.get("strategy_version") if bot else None,
        "activation_epoch": bot.get("activation_epoch_id") if bot else None,
        "bot": bot.get("bot_instance_id") if bot else None,
        "mode": bot.get("mode") if bot else None,
        "status": bot.get("status") if bot else None,
        "entries_paused": bool(int(bot.get("entries_paused") or 0)) if bot else False,
        "bots": bots,
        "open_positions": sum(1 for p in positions if str(p["state"]) in OPEN_LIKE),
        "partial_positions": sum(1 for p in positions if str(p["state"]) == "PARTIAL"),
        "unknown_positions": sum(1 for p in positions if str(p["state"]) in UNKNOWN_LIKE),
        "exit_required": sum(1 for p in positions if str(p["state"]) in EXIT_REQUIRED_LIKE),
        "unresolved_positions": sum(1 for p in positions if str(p["state"]) in UNRESOLVED_LIKE),
        "known_open_exposure_usd": None
        if known_open_exposure_status in {"UNKNOWN", "EMPTY"}
        else format(known_open_exposure, "f"),
        "known_open_exposure_status": known_open_exposure_status,
        "pnl_known_count": len(known_pnl),
        "pnl_unknown_count": sum(
            1
            for p in positions
            if position_pnl_view(p)["pnl_status"] == "UNKNOWN"
            and str(p["state"]) not in {"WATCHED", "SIGNALLED", "INTENT_CREATED", "ATTEMPTING"}
        ),
        "reconciled_net_pnl_usd": None
        if reconciled_net is None
        else format(reconciled_net, "f"),
        "reconciled_net_pnl_status": reconciled_net_status,
        "current_loss_streak_status": streak["current_loss_streak_status"],
        "current_loss_streak_count": streak["current_loss_streak_count"],
        "max_drawdown_usd": max_dd,
        "max_drawdown_status": max_dd_status,
        "position_rows": position_rows,
        "attention": attention,
        "open_position_set_sha256": open_position_set_sha256(open_ids),
        "open_position_ids": sorted(open_ids),
        "open_position_set_sha256_by_bot": {
            bot_id: open_position_set_sha256(ids)
            for bot_id, ids in sorted(open_ids_by_bot.items())
        },
        "open_risk_count": sum(
            1 for p in positions if str(p["state"]) in OPEN_RISK_STATES
        ),
    }


def build_economics_projection(
    store: PaperPlaneStore,
    *,
    operations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bounded PAPER/SHADOW model economics. Never claims live/FCF/NetReturn."""

    ops = operations or build_operations_projection(store)
    by_class: dict[str, Decimal] = {}
    for row in ops.get("position_rows") or []:
        if row.get("pnl_status") != "KNOWN" or row.get("net_pnl_usd") is None:
            continue
        evidence = str(row.get("pnl_evidence_class") or "UNKNOWN_CLASS")
        by_class[evidence] = by_class.get(evidence, Decimal("0")) + Decimal(
            str(row["net_pnl_usd"])
        )
    return {
        "as_of": ops.get("as_of"),
        "reconciled_net_pnl_usd": ops.get("reconciled_net_pnl_usd"),
        "reconciled_net_pnl_status": ops.get("reconciled_net_pnl_status"),
        "pnl_known_count": ops.get("pnl_known_count"),
        "pnl_unknown_count": ops.get("pnl_unknown_count"),
        "known_open_exposure_usd": ops.get("known_open_exposure_usd"),
        "known_open_exposure_status": ops.get("known_open_exposure_status"),
        "current_loss_streak_status": ops.get("current_loss_streak_status"),
        "current_loss_streak_count": ops.get("current_loss_streak_count"),
        "max_drawdown_usd": ops.get("max_drawdown_usd"),
        "max_drawdown_status": ops.get("max_drawdown_status"),
        "pnl_by_evidence_class": {
            key: format(value, "f") for key, value in sorted(by_class.items())
        },
        "non_claims": [
            "NO_REALIZED_LIVE_PNL",
            "NO_OWNER_FCF",
            "NO_LIVE_CAPITAL",
            "NO_NETRETURN_CLAIM",
        ],
    }
