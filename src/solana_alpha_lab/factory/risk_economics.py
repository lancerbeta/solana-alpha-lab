"""RiskEconomicsProjectionV1. Derived owner economics. Persists nowhere."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.paper_plane import (
    OPEN_RISK_STATES,
    PaperPlaneStore,
    modeled_unrealized_mark,
)
from solana_alpha_lab.factory.paper_shadow_operations import TERMINAL_SETTLED

SCHEMA = "smial.risk-economics-projection"
SCHEMA_VERSION = "1.0"
STRATEGY_ROOT = "configs/strategies"

ACCEPTED_RECONCILED_CLASSES = frozenset(
    {"PAPER_RECONCILED_MODEL", "SHADOW_RECONCILED_QUOTE_MODEL"}
)
ACCEPTED_MARK_CLASSES = frozenset(
    {"PAPER_MARK_TO_MODEL", "SHADOW_EXECUTABLE_QUOTE_MARK"}
)
NOT_DEFINED_POLICIES = (
    "daily_loss_limit",
    "drawdown_limit",
    "capital_limit",
    "capacity_limit",
    "cvar",
    "var",
    "kelly",
)

NON_CLAIMS = (
    "NO ALPHA",
    "NO NETRETURN",
    "NO LIVE PNL",
    "NO OWNER FCF",
    "NO LIVE CAPITAL",
    "NO CAPACITY CLAIM",
    "NO PROMOTION",
    "NO REAL MONEY",
    "NO DEPLOY",
    "NO PROVIDER",
    "NO WALLET",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _parse_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def strategy_version_label_from_bot(bot: Mapping[str, Any]) -> str | None:
    stored = str(bot.get("strategy_version") or "")
    strategy_id = str(bot.get("strategy_id") or "")
    if strategy_id and stored.startswith(f"{strategy_id}-"):
        label = stored[len(strategy_id) + 1 :]
        return label or None
    return stored or None


def _scope_key(
    strategy_id: str | None,
    version: str | None,
    mode: str | None,
    evidence_class: str | None,
) -> tuple[str, str, str, str]:
    return (
        str(strategy_id or "UNKNOWN_STRATEGY"),
        str(version or "UNKNOWN_VERSION"),
        str(mode or "UNKNOWN_MODE"),
        str(evidence_class or "EVIDENCE_CLASS_UNKNOWN"),
    )


def _load_git_strategies(root: Path) -> list[dict[str, Any]]:
    folder = root / STRATEGY_ROOT
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        strategy_id = loaded.get("strategy_id")
        if not strategy_id:
            continue
        rows.append(
            {
                "strategy_id": str(strategy_id),
                "strategy_version": str(loaded.get("strategy_version") or ""),
                "path": path.relative_to(root).as_posix(),
                "document": loaded,
            }
        )
    return rows


def _accounting_invariant(position: Mapping[str, Any]) -> str | None:
    gross = _dec(position.get("realized_gross_pnl_usd_dec"))
    entry_fee = _dec(position.get("entry_fee_usd_dec"))
    exit_fee = _dec(position.get("exit_fee_usd_dec"))
    stored_net = _dec(position.get("realized_net_pnl_usd_dec"))
    if None in {gross, entry_fee, exit_fee, stored_net}:
        return None
    expected = (gross - entry_fee - exit_fee).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if expected != stored_net:
        return "ACCOUNTING_INVARIANT_CONFLICT"
    return None


def _reconciled_row(position: Mapping[str, Any], bot: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = str(position.get("pnl_evidence_class") or "")
    conflict = _accounting_invariant(position)
    net = _dec(position.get("realized_net_pnl_usd_dec"))
    if not evidence or evidence not in ACCEPTED_RECONCILED_CLASSES:
        status = "UNKNOWN"
        trust = False
        gap = "EVIDENCE_CLASS_UNKNOWN"
    elif conflict:
        status = "ACCOUNTING_CONFLICT"
        trust = False
        gap = conflict
        net = None
    elif net is None:
        status = "UNKNOWN"
        trust = False
        gap = "RECONCILED_NET_UNKNOWN"
    else:
        status = "KNOWN"
        trust = True
        gap = None
    version = str(position.get("strategy_version_label") or "") or (
        strategy_version_label_from_bot(bot) if bot else None
    )
    mode = str(bot.get("mode") or "") if bot else ""
    return {
        "position_id": position.get("position_id"),
        "strategy_id": position.get("strategy_id") or (bot.get("strategy_id") if bot else None),
        "strategy_version": version,
        "mode": mode,
        "activation_epoch_id": position.get("activation_epoch_id")
        or (bot.get("activation_epoch_id") if bot else None),
        "bot_instance_id": position.get("bot_instance_id"),
        "pnl_evidence_class": evidence or "EVIDENCE_CLASS_UNKNOWN",
        "entered_notional_usd": _money(_dec(position.get("entered_notional_usd_dec"))),
        "exit_notional_usd": _money(_dec(position.get("exit_notional_usd_dec"))),
        "realized_gross_pnl_usd": _money(_dec(position.get("realized_gross_pnl_usd_dec"))),
        "entry_fee_usd": _money(_dec(position.get("entry_fee_usd_dec"))),
        "exit_fee_usd": _money(_dec(position.get("exit_fee_usd_dec"))),
        "realized_net_after_modeled_fees_usd": _money(net) if trust else None,
        "status": status,
        "trusted": trust,
        "gap": gap,
        "closed_at": position.get("closed_at"),
        "opened_at": position.get("opened_at"),
    }


def _open_mark_row(
    position: Mapping[str, Any],
    bot: Mapping[str, Any] | None,
    *,
    as_of: str,
) -> dict[str, Any]:
    evidence = str(position.get("unrealized_evidence_class") or "")
    version = str(position.get("strategy_version_label") or "") or (
        strategy_version_label_from_bot(bot) if bot else None
    )
    mode = str(bot.get("mode") or "") if bot else ""
    mark_as_of = position.get("mark_as_of")
    mark_price = _dec(position.get("mark_price_dec"))
    qty = _dec(position.get("qty_dec"))
    entered = _dec(position.get("entered_notional_usd_dec"))
    entry_fee = _dec(position.get("entry_fee_usd_dec"))
    fee_bps = position.get("fee_bps")
    gap = None
    derived_from_legacy = False
    net = None
    gross = None
    modeled_exit = None
    mark_age = None
    status = "UNKNOWN"
    if evidence not in ACCEPTED_MARK_CLASSES:
        gap = "EVIDENCE_CLASS_UNKNOWN"
    elif mark_as_of in {None, ""}:
        gap = "MARK_TIME_UNKNOWN"
    elif None in {mark_price, qty, entered, entry_fee} or fee_bps is None:
        gap = "OPEN_MARK_COST_COMPONENT_GAP"
    else:
        derived = modeled_unrealized_mark(
            mark_price=mark_price,
            qty=qty,
            entered_notional=entered,
            entry_fee=entry_fee,
            fee_bps=int(fee_bps),
        )
        gross = derived["unrealized_gross"]
        modeled_exit = derived["modeled_exit_fee_at_mark"]
        net = derived["unrealized_net"]
        status = "KNOWN"
        stored_net = _dec(position.get("unrealized_net_pnl_usd_dec"))
        if stored_net is not None and stored_net != net:
            derived_from_legacy = True
        start = _parse_utc(str(mark_as_of))
        end = _parse_utc(as_of)
        if start is not None and end is not None:
            mark_age = int((end - start).total_seconds())
    return {
        "position_id": position.get("position_id"),
        "strategy_id": position.get("strategy_id") or (bot.get("strategy_id") if bot else None),
        "strategy_version": version,
        "mode": mode,
        "activation_epoch_id": position.get("activation_epoch_id")
        or (bot.get("activation_epoch_id") if bot else None),
        "bot_instance_id": position.get("bot_instance_id"),
        "state": position.get("state"),
        "mark_price": _money(mark_price),
        "mark_as_of": mark_as_of,
        "mark_age_seconds": mark_age,
        "mark_evidence_class": evidence or "EVIDENCE_CLASS_UNKNOWN",
        "unrealized_gross_pnl_usd": _money(gross),
        "modeled_exit_fee_at_mark_usd": _money(modeled_exit),
        "unrealized_net_after_modeled_fees_usd": _money(net),
        "status": status,
        "settlement": "NOT_SETTLED",
        "mark_freshness_policy": "NOT_DEFINED",
        "provenance": "DERIVED_FROM_LEGACY_RAW_COMPONENTS"
        if derived_from_legacy
        else "FORWARD_OR_EQUIVALENT",
        "gap": gap,
    }


def _fee_coverage(rows: list[dict[str, Any]]) -> str:
    trusted = [row for row in rows if row.get("trusted")]
    if not trusted:
        return "UNKNOWN"
    complete = all(
        row.get("entry_fee_usd") not in {None, ""}
        and row.get("exit_fee_usd") not in {None, ""}
        for row in trusted
    )
    return "COMPLETE" if complete else "PARTIAL"


def _drawdown(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"usd": None, "status": "EMPTY", "basis": "RECONCILED_MODEL_PNL_DRAWDOWN_USD"}
    if any(not row.get("trusted") for row in rows):
        return {"usd": None, "status": "UNKNOWN", "basis": "RECONCILED_MODEL_PNL_DRAWDOWN_USD"}
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    for row in rows:
        pnl = _dec(row["realized_net_after_modeled_fees_usd"])
        assert pnl is not None
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return {
        "usd": format(max_dd, "f"),
        "status": "KNOWN",
        "basis": "RECONCILED_MODEL_PNL_DRAWDOWN_USD",
    }


def _loss_streak(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "KNOWN", "count": 0}
    streak = 0
    for row in reversed(rows):
        if not row.get("trusted"):
            return {"status": "UNKNOWN", "count": None}
        pnl = _dec(row["realized_net_after_modeled_fees_usd"])
        assert pnl is not None
        if pnl < 0:
            streak += 1
            continue
        return {"status": "KNOWN", "count": streak}
    return {"status": "KNOWN", "count": streak}


def _reconciled_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "EMPTY"
    if any(row.get("status") == "ACCOUNTING_CONFLICT" for row in rows):
        return "ACCOUNTING_CONFLICT"
    if all(row.get("trusted") for row in rows):
        return "KNOWN"
    if any(row.get("trusted") for row in rows):
        return "PARTIAL_UNKNOWN"
    return "UNKNOWN"


def _declared_risk_scope(
    bot: Mapping[str, Any],
    positions: list[Mapping[str, Any]],
    git_strategies: list[dict[str, Any]],
) -> dict[str, Any]:
    strategy_id = str(bot.get("strategy_id") or "")
    version = strategy_version_label_from_bot(bot)
    count = sum(
        1
        for position in positions
        if str(position.get("bot_instance_id")) == str(bot.get("bot_instance_id"))
        and str(position.get("state")) in OPEN_RISK_STATES
    )
    matches = [
        item
        for item in git_strategies
        if item["strategy_id"] == strategy_id and item["strategy_version"] == version
    ]
    unresolved = any(
        str(position.get("bot_instance_id")) == str(bot.get("bot_instance_id"))
        and str(position.get("state")) in {"EXIT_REQUIRED", "EXITING", "UNRESOLVED"}
        for position in positions
    )
    base = {
        "strategy_id": strategy_id or None,
        "strategy_version": version,
        "mode": bot.get("mode"),
        "bot_instance_id": bot.get("bot_instance_id"),
        "entry_admission_risk_count": count,
        "max_open_positions": None,
        "remaining_entry_slots": None,
        "entry_admission_status": "POLICY_UNKNOWN",
        "other_limits": {name: "NOT_DEFINED" for name in NOT_DEFINED_POLICIES},
        "unresolved_or_exit_inventory": unresolved,
        "all_risk_clear": False,
        "gap": None,
    }
    if not strategy_id or not version:
        base["gap"] = "STRATEGY_POLICY_GAP"
        return base
    if not matches:
        base["gap"] = "STRATEGY_POLICY_GAP"
        return base
    if len(matches) > 1:
        limits = []
        for item in matches:
            policy = item["document"].get("risk_policy")
            if isinstance(policy, dict) and "max_open_positions" in policy:
                limits.append(int(policy["max_open_positions"]))
        if len(set(limits)) > 1:
            base["entry_admission_status"] = "STRATEGY_POLICY_CONFLICT"
            base["gap"] = "STRATEGY_POLICY_CONFLICT"
            return base
    policy = matches[0]["document"].get("risk_policy")
    if not isinstance(policy, dict) or "max_open_positions" not in policy:
        base["gap"] = "STRATEGY_POLICY_GAP"
        return base
    limit = int(policy["max_open_positions"])
    base["max_open_positions"] = limit
    remaining = limit - count
    base["remaining_entry_slots"] = remaining
    if count > limit:
        base["entry_admission_status"] = "DECLARED_ENTRY_LIMIT_BREACH"
    elif count == limit:
        base["entry_admission_status"] = "ENTRY_LIMIT_REACHED"
    else:
        base["entry_admission_status"] = "WITHIN_DECLARED_ENTRY_LIMIT"
    return base


def _exposure_scopes(
    positions: list[Mapping[str, Any]],
    bots: dict[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for position in positions:
        if str(position.get("state")) in TERMINAL_SETTLED:
            continue
        bot = bots.get(str(position.get("bot_instance_id")))
        version = str(position.get("strategy_version_label") or "") or (
            strategy_version_label_from_bot(bot) if bot else "UNKNOWN_VERSION"
        )
        mode = str(bot.get("mode") or "UNKNOWN_MODE") if bot else "UNKNOWN_MODE"
        strategy_id = str(
            position.get("strategy_id") or (bot.get("strategy_id") if bot else "UNKNOWN_STRATEGY")
        )
        key = (strategy_id, str(version), mode)
        bucket = buckets.setdefault(
            key,
            {
                "strategy_id": strategy_id,
                "strategy_version": version,
                "mode": mode,
                "basis": "ENTERED_NOTIONAL_EXPOSURE_USD",
                "known_usd": Decimal("0"),
                "known_count": 0,
                "unknown_count": 0,
            },
        )
        notional = _dec(position.get("entered_notional_usd_dec"))
        if notional is None:
            bucket["unknown_count"] += 1
        else:
            bucket["known_usd"] += notional
            bucket["known_count"] += 1
    scopes = []
    for bucket in buckets.values():
        known = bucket["known_count"]
        unknown = bucket["unknown_count"]
        if known == 0 and unknown == 0:
            status = "EMPTY"
            usd = None
        elif known == 0:
            status = "UNKNOWN"
            usd = None
        elif unknown:
            status = "PARTIAL_KNOWN"
            usd = format(bucket["known_usd"], "f")
        else:
            status = "KNOWN"
            usd = format(bucket["known_usd"], "f")
        scopes.append(
            {
                "strategy_id": bucket["strategy_id"],
                "strategy_version": bucket["strategy_version"],
                "mode": bucket["mode"],
                "basis": "ENTERED_NOTIONAL_EXPOSURE_USD",
                "entered_notional_exposure_usd": usd,
                "status": status,
                "known_count": known,
                "unknown_count": unknown,
            }
        )
    if not scopes:
        return [
            {
                "strategy_id": None,
                "strategy_version": None,
                "mode": None,
                "basis": "ENTERED_NOTIONAL_EXPOSURE_USD",
                "entered_notional_exposure_usd": None,
                "status": "EMPTY",
                "known_count": 0,
                "unknown_count": 0,
            }
        ]
    return scopes


def _evidence_state(
    *,
    source_status: str,
    reconciled: list[dict[str, Any]],
    paper: bool,
    shadow: bool,
) -> str:
    if source_status == "UNAVAILABLE":
        return "SOURCE_UNAVAILABLE"
    if source_status in {"NOT_PRESENT", "SOURCE_NOT_PRESENT"}:
        return "SOURCE_NOT_PRESENT"
    if any(row.get("status") == "ACCOUNTING_CONFLICT" for row in reconciled):
        return "ACCOUNTING_CONFLICT"
    if not reconciled and not paper and not shadow:
        return "NO_ECONOMIC_EVIDENCE"
    if any(not row.get("trusted") for row in reconciled):
        return "PARTIAL_UNKNOWN"
    if paper and shadow:
        return "PAPER_AND_SHADOW_SEPARATE"
    if paper:
        return "PAPER_MODEL_ONLY"
    if shadow:
        return "SHADOW_MODEL_ONLY"
    return "UNKNOWN"


def _next_action(
    *,
    source_status: str,
    evidence_state: str,
    mixed: bool,
    risk_scopes: list[dict[str, Any]],
    mark_rows: list[dict[str, Any]],
) -> str:
    if source_status in {"NOT_PRESENT", "SOURCE_NOT_PRESENT", "UNAVAILABLE"}:
        return "WAIT_FOR_RECONCILED_EVIDENCE"
    if evidence_state == "ACCOUNTING_CONFLICT":
        return "INSPECT_ACCOUNTING_EVIDENCE"
    if any(row.get("gap") == "OPEN_MARK_COST_COMPONENT_GAP" for row in mark_rows):
        return "INSPECT_POSITION_EVIDENCE"
    if any(scope.get("entry_admission_status") == "DECLARED_ENTRY_LIMIT_BREACH" for scope in risk_scopes):
        return "INSPECT_OPERATIONS"
    if evidence_state in {"PARTIAL_UNKNOWN", "UNKNOWN"}:
        return "INSPECT_OPERATIONS"
    if mixed:
        return "INSPECT_EVIDENCE_SCOPES"
    if any(scope.get("unresolved_or_exit_inventory") for scope in risk_scopes):
        return "INSPECT_OPERATIONS"
    if evidence_state == "NO_ECONOMIC_EVIDENCE":
        return "WAIT_FOR_RECONCILED_EVIDENCE"
    return "WAIT_FOR_RECONCILED_EVIDENCE"


def compose_risk_economics(
    root: Path,
    store: PaperPlaneStore | None,
    *,
    source_status: str | None = None,
    as_of: str | None = None,
    operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Owner economics composer. Same object for GET /economics and read-model."""

    del operations  # inventory truth stays on /operations; unused on purpose
    as_of_value = as_of or _now()
    status = source_status or ("PRESENT" if store is not None else "NOT_PRESENT")
    empty = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of_value,
        "source_status": status if status != "NOT_PRESENT" else "SOURCE_NOT_PRESENT",
        "evidence_state": "SOURCE_NOT_PRESENT"
        if status in {"NOT_PRESENT", "SOURCE_NOT_PRESENT"}
        else "SOURCE_UNAVAILABLE",
        "coverage": {
            "reconciled_count_total": 0,
            "reconciled_count_known": 0,
            "reconciled_count_unknown_or_conflict": 0,
            "open_mark_count": 0,
            "open_mark_known_count": 0,
            "open_mark_unknown_count": 0,
        },
        "reconciled_scopes": [],
        "open_mark_scopes": [],
        "declared_risk_scopes": [],
        "exposure_scopes": [],
        "gaps": [
            {
                "code": "SOURCE_NOT_PRESENT"
                if status in {"NOT_PRESENT", "SOURCE_NOT_PRESENT"}
                else "SOURCE_UNAVAILABLE"
            }
        ],
        "local_attention": [],
        "next_safe_action": "WAIT_FOR_RECONCILED_EVIDENCE",
        "reconciled_net_pnl_usd": None,
        "reconciled_net_pnl_status": "SOURCE_NOT_PRESENT"
        if status in {"NOT_PRESENT", "SOURCE_NOT_PRESENT"}
        else "SOURCE_UNAVAILABLE",
        "mixed_evidence": False,
        "netreturn_status": "NOT_ESTABLISHED",
        "owner_fcf_status": "NOT_AVAILABLE",
        "total_real_trading_cost": "NOT_ESTABLISHED",
        "mark_freshness_policy": "NOT_DEFINED",
        "non_claims": list(NON_CLAIMS),
    }
    if store is None:
        return empty

    bots = {str(bot["bot_instance_id"]): bot for bot in store.bots()}
    positions = list(store.positions())
    git_strategies = _load_git_strategies(root)
    reconciled_rows = [
        _reconciled_row(position, bots.get(str(position.get("bot_instance_id"))))
        for position in positions
        if str(position.get("state")) == "RECONCILED"
    ]
    reconciled_rows.sort(
        key=lambda row: (
            str(row.get("closed_at") or ""),
            str(row.get("opened_at") or ""),
            str(row.get("position_id") or ""),
        )
    )
    mark_rows = [
        _open_mark_row(
            position,
            bots.get(str(position.get("bot_instance_id"))),
            as_of=as_of_value,
        )
        for position in positions
        if str(position.get("state")) not in TERMINAL_SETTLED
        and str(position.get("state"))
        in {"OPEN", "PARTIAL", "UNKNOWN", "EXIT_REQUIRED", "EXITING", "UNRESOLVED"}
    ]

    reconciled_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in reconciled_rows:
        key = _scope_key(
            row.get("strategy_id"),
            row.get("strategy_version"),
            row.get("mode"),
            row.get("pnl_evidence_class"),
        )
        reconciled_groups.setdefault(key, []).append(row)

    reconciled_scopes = []
    for key, rows in reconciled_groups.items():
        trusted_net = [
            _dec(row["realized_net_after_modeled_fees_usd"])
            for row in rows
            if row.get("trusted")
        ]
        status_value = _reconciled_status(rows)
        drawdown = _drawdown(rows)
        streak = _loss_streak(rows)
        trusted_headline = (
            format(sum((item for item in trusted_net if item is not None), Decimal("0")), "f")
            if status_value == "KNOWN" and trusted_net
            else None
        )
        reconciled_scopes.append(
            {
                "strategy_id": key[0],
                "strategy_version": key[1],
                "mode": key[2],
                "pnl_evidence_class": key[3],
                "status": status_value,
                "reconciled_count_total": len(rows),
                "reconciled_count_known": sum(1 for row in rows if row.get("trusted")),
                "reconciled_count_unknown_or_conflict": sum(
                    1 for row in rows if not row.get("trusted")
                ),
                "realized_net_after_modeled_fees_usd": trusted_headline,
                "modeled_fee_coverage": _fee_coverage(rows),
                "drawdown": drawdown,
                "loss_streak": streak,
                "rows": rows,
            }
        )

    mark_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in mark_rows:
        key = _scope_key(
            row.get("strategy_id"),
            row.get("strategy_version"),
            row.get("mode"),
            row.get("mark_evidence_class"),
        )
        mark_groups.setdefault(key, []).append(row)
    open_mark_scopes = []
    for key, rows in mark_groups.items():
        known = [row for row in rows if row.get("status") == "KNOWN"]
        nets = [_dec(row["unrealized_net_after_modeled_fees_usd"]) for row in known]
        mark_status = (
            "KNOWN"
            if known and len(known) == len(rows)
            else ("PARTIAL_UNKNOWN" if known else "UNKNOWN")
        )
        open_mark_scopes.append(
            {
                "strategy_id": key[0],
                "strategy_version": key[1],
                "mode": key[2],
                "mark_evidence_class": key[3],
                "status": mark_status,
                "open_mark_count": len(rows),
                "open_mark_known_count": len(known),
                "open_mark_unknown_count": len(rows) - len(known),
                "unrealized_net_after_modeled_fees_usd": (
                    format(sum((item for item in nets if item is not None), Decimal("0")), "f")
                    if mark_status == "KNOWN"
                    else None
                ),
                "mark_freshness_policy": "NOT_DEFINED",
                "settlement": "NOT_SETTLED",
                "rows": rows,
            }
        )

    incompatible = {
        (scope["strategy_id"], scope["strategy_version"], scope["mode"], scope["pnl_evidence_class"])
        for scope in reconciled_scopes
    }
    mixed = len(incompatible) > 1
    trusted_single = [
        scope
        for scope in reconciled_scopes
        if scope["status"] == "KNOWN" and scope["realized_net_after_modeled_fees_usd"] is not None
    ]
    if mixed:
        legacy_net = None
        legacy_status = "MIXED_EVIDENCE_NOT_AGGREGATED"
    elif len(trusted_single) == 1:
        legacy_net = trusted_single[0]["realized_net_after_modeled_fees_usd"]
        legacy_status = "KNOWN"
    elif not reconciled_scopes:
        legacy_net = None
        legacy_status = "EMPTY"
    else:
        legacy_net = None
        legacy_status = reconciled_scopes[0]["status"] if len(reconciled_scopes) == 1 else "UNKNOWN"

    paper = any(scope["mode"] == "PAPER" for scope in reconciled_scopes + open_mark_scopes)
    shadow = any(scope["mode"] == "SHADOW" for scope in reconciled_scopes + open_mark_scopes)
    evidence_state = _evidence_state(
        source_status="PRESENT",
        reconciled=reconciled_rows,
        paper=paper,
        shadow=shadow,
    )
    risk_scopes = [
        _declared_risk_scope(bot, positions, git_strategies) for bot in bots.values()
    ]
    exposure = _exposure_scopes(positions, bots)
    gaps = []
    if mixed:
        gaps.append({"code": "MIXED_EVIDENCE_NOT_AGGREGATED"})
    for row in reconciled_rows:
        if row.get("gap"):
            gaps.append(
                {
                    "code": row["gap"],
                    "position_id": row.get("position_id"),
                }
            )
    for row in mark_rows:
        if row.get("gap"):
            gaps.append({"code": row["gap"], "position_id": row.get("position_id")})
    for scope in risk_scopes:
        if scope.get("gap"):
            gaps.append(
                {
                    "code": scope["gap"],
                    "bot_instance_id": scope.get("bot_instance_id"),
                }
            )
    next_action = _next_action(
        source_status="PRESENT",
        evidence_state=evidence_state,
        mixed=mixed,
        risk_scopes=risk_scopes,
        mark_rows=mark_rows,
    )
    if any(scope.get("entry_admission_status") == "DECLARED_ENTRY_LIMIT_BREACH" for scope in risk_scopes):
        next_action = "INSPECT_OPERATIONS"
    coverage = {
        "reconciled_count_total": len(reconciled_rows),
        "reconciled_count_known": sum(1 for row in reconciled_rows if row.get("trusted")),
        "reconciled_count_unknown_or_conflict": sum(
            1 for row in reconciled_rows if not row.get("trusted")
        ),
        "open_mark_count": len(mark_rows),
        "open_mark_known_count": sum(1 for row in mark_rows if row.get("status") == "KNOWN"),
        "open_mark_unknown_count": sum(1 for row in mark_rows if row.get("status") != "KNOWN"),
    }
    attention = []
    if mixed:
        attention.append(
            {
                "code": "MIXED_EVIDENCE_NOT_AGGREGATED",
                "WHY_NOW": "PAPER and SHADOW (or other scopes) are separate evidence",
                "IMPACT": "No combined total profit",
                "NEXT_SAFE_ACTION": "INSPECT_EVIDENCE_SCOPES",
            }
        )
    if evidence_state == "ACCOUNTING_CONFLICT":
        attention.append(
            {
                "code": "ACCOUNTING_INVARIANT_CONFLICT",
                "WHY_NOW": "Stored net disagrees with gross minus modeled fees",
                "IMPACT": "Conflicting row excluded from trusted net",
                "NEXT_SAFE_ACTION": "INSPECT_ACCOUNTING_EVIDENCE",
            }
        )
    if any(scope.get("entry_admission_status") == "DECLARED_ENTRY_LIMIT_BREACH" for scope in risk_scopes):
        attention.append(
            {
                "code": "DECLARED_ENTRY_LIMIT_BREACH",
                "WHY_NOW": "Open-risk count exceeds declared max_open_positions",
                "IMPACT": "Inspect Operations; /economics does not mutate",
                "NEXT_SAFE_ACTION": "INSPECT_OPERATIONS",
            }
        )
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of_value,
        "source_status": "PRESENT",
        "evidence_state": evidence_state,
        "coverage": coverage,
        "reconciled_scopes": reconciled_scopes,
        "open_mark_scopes": open_mark_scopes,
        "declared_risk_scopes": risk_scopes,
        "exposure_scopes": exposure,
        "gaps": gaps,
        "local_attention": attention,
        "next_safe_action": next_action,
        "reconciled_net_pnl_usd": legacy_net,
        "reconciled_net_pnl_status": legacy_status,
        "mixed_evidence": mixed,
        "netreturn_status": "NOT_ESTABLISHED",
        "owner_fcf_status": "NOT_AVAILABLE",
        "total_real_trading_cost": "NOT_ESTABLISHED",
        "mark_freshness_policy": "NOT_DEFINED",
        "non_claims": list(NON_CLAIMS),
    }
